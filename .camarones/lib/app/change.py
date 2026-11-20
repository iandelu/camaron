"""Coding changes (WI-21): one record per change in the cache (`changes/<id>.json`, written only here and under a
lock), the change's branch in each repo it touches and its cam-docs worktree (`<workspace>/.cw/<id>`), its phase, and
the board card the kit moves by the fixed rules of lib/domain/change.py (`kanban.ops.move`, surface `change`). Git runs
through lib/core/process as argv; the worktree through `services.worktrees`. The record stays on this machine: the
cache is git-ignored. Its shape is what WI-22 (start from the board), WI-24 (PRs) and WI-25 (git hooks) build on."""
from __future__ import annotations

import re
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

from ..core import paths
from ..core.fsutil import load_json, save_json
from ..core.locks import FileLock
from ..core.process import out, run
from ..domain import change as rules
from ..domain.docs import derived, frontmatter, trust_levels
from . import services

WORKTREES = ".cw"           # the workspace folder that holds cam-docs worktrees (as lib/harness/worktrees.py)
TO_READ = 12                # docs listed at start, at most
DOCS = "docs"               # the docs side of a change: `link --repo docs`, its base in `row`


class ChangeError(Exception):
    """The command is blocked; the message says why and what to do. Nothing was written."""


# ---------- the record ----------
def _dir() -> Path:
    return paths.CACHE / "changes"


def _lock() -> FileLock:
    return FileLock(paths.CACHE / "locks" / "changes.lock")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _who() -> str:
    from ..kanban import ops
    return ops.who()


def load(id_: str) -> dict | None:
    return load_json(_dir() / f"{id_.strip().lower()}.json", None)


def _save(rec: dict) -> None:
    save_json(_dir() / f"{rec['id']}.json", rec)


def records() -> list[dict]:
    if not _dir().is_dir():
        return []
    found = [load_json(f, None) for f in sorted(_dir().glob("*.json"))]
    return sorted((r for r in found if isinstance(r, dict) and r.get("id")), key=lambda r: r.get("created") or "")


def open_records() -> list[dict]:
    return [r for r in records() if r.get("state") in rules.OPEN]


def _branches_here(cwd: Path | None) -> list[str]:
    b = out(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=cwd or Path.cwd())
    return [b] if b and b != "HEAD" else []


def _pick(id_: str | None, cwd: Path | None) -> dict:
    """The open change a command means (LookupError says why none fits: a usage error, not a block)."""
    return rules.pick(open_records(), id_, [] if id_ else _branches_here(cwd))


def row(rec: dict) -> dict:
    """What `status` and the Board show of a change."""
    repos, docs = rec.get("repos") or {}, rec.get("docs") or {}
    bases = {n: r.get("base_ref") for n, r in repos.items()}
    if docs:
        bases[DOCS] = docs.get("base_ref")
    return {"id": rec["id"], "title": rec.get("title"), "item": rec.get("item"), "phase": rec.get("phase"),
            "state": rec.get("state"), "repos": {n: r.get("branch") for n, r in repos.items()}, "bases": bases,
            "worktree": docs.get("worktree"), "docs_branch": docs.get("branch"), "prs": dict(rec.get("prs") or {}),
            "closed": rec.get("closed"), "next": rules.next_step(rec)}


# ---------- the board ----------
def _follow(rec: dict, rule: str, *, force: bool = False, by: str | None = None) -> dict | None:
    """Move the change's card as `rule` says (nothing without an item, or when the card is already past it) and note
    the move in the record. A card that went away is noted, not an error: the change goes on."""
    if not rec.get("item"):
        return None
    from ..kanban import ops
    try:
        now = ops.status_of(rec["item"])
        target = rules.board_target(rule, now)
        if target is None:
            return None
        if rule == "start":
            forced = bool(ops.start_gate(rec["item"], surface="change"))
        else:
            forced = False
        ops.move(rec["item"], target, by=by, surface="change", force=force)
    except ops.BoardError as e:
        entry = {"rule": rule, "to": None, "at": _now(), "forced": False, "error": str(e)}
    else:
        entry = {"rule": rule, "to": target, "from": now, "at": _now(), "forced": forced}
    rec.setdefault("board", []).append(entry)
    return entry


def by_item() -> dict[str, dict]:
    """The open change of each board item: `{ITEM: row}` (the Board's phase pill)."""
    return {r["item"]: row(r) for r in open_records() if r.get("item")}


def of_item(item_id: str) -> dict | None:
    """The open change of one item (the Board's side panel), or None."""
    return by_item().get(item_id.strip().upper())


# ---------- start ----------
def _default_branch(name: str, repo: Path) -> str:
    for r in services.current().workspace.workspace().get("repos") or []:
        if isinstance(r, dict) and r.get("name") == name and r.get("branch"):
            return str(r["branch"])
    head = out(["git", "symbolic-ref", "--short", "refs/remotes/origin/HEAD"], cwd=repo)
    return head.removeprefix("origin/") or "main"


def _ref_exists(repo: Path, ref: str) -> bool:
    return run(["git", "rev-parse", "--verify", "--quiet", ref], cwd=repo, check=False, capture=True).returncode == 0


def _kit_only(repo: Path, line: str) -> bool:
    """A `git status --porcelain` line that is only the kit's own pointer block in the repo's CLAUDE.md
    (`project.repo_pointer`, app.setup.add_repo_pointer): not someone's work, so it does not make the tree dirty."""
    if line[3:].strip('"') != "CLAUDE.md" or line[:2] not in (" M", "??"):
        return False
    s = services.current().setup
    block = re.compile(rf"\n*{re.escape(s.POINTER_START)}.*?{re.escape(s.POINTER_END)}\n?", re.S)
    text = (repo / "CLAUDE.md").read_text(encoding="utf-8", errors="replace")
    if s.POINTER_START not in text:
        return False
    head = run(["git", "show", "HEAD:CLAUDE.md"], cwd=repo, check=False, capture=True)
    before = head.stdout if head.returncode == 0 else ""
    return block.sub("", text).strip() == before.replace("\r\n", "\n").strip()


def _dirty(repo: Path) -> list[str]:
    """The repo's uncommitted paths, the kit's pointer block aside."""
    st = run(["git", "status", "--porcelain"], cwd=repo, check=False, capture=True).stdout or ""
    return [ln for ln in st.splitlines() if ln.strip() and not _kit_only(repo, ln)]


def _plan_repo(name: str, branch: str, base: str | None) -> dict:
    """What `start` will do in one repo, or why it cannot (`blocked`). Reads only."""
    d = paths.repo_dir(name)
    if not (d / ".git").exists():
        return {"blocked": f"{name}: no git repo at {d}"}
    current = out(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=d)
    default = _default_branch(name, d)
    base_ref = base or next((r for r in (f"origin/{default}", default) if _ref_exists(d, r)), "HEAD")
    if base and not _ref_exists(d, base):
        return {"blocked": f"{name}: no ref {base}"}
    p = {"name": name, "dir": d, "branch": branch, "base_ref": base_ref,
         "base": out(["git", "rev-parse", base_ref], cwd=d), "adopted": False, "act": "keep"}
    if current == branch:
        return p
    if _dirty(d):
        return {"blocked": f"{name} has uncommitted changes: commit or stash them, then start again"}
    if current not in (default, "HEAD", ""):
        return {**p, "branch": current, "adopted": True}
    return {**p, "act": "switch" if _ref_exists(d, f"refs/heads/{branch}") else "create"}


def _branch(p: dict) -> None:
    cmd = {"create": ["git", "switch", "-c", p["branch"], p["base_ref"]], "switch": ["git", "switch", p["branch"]]}
    if p["act"] in cmd:
        try:
            run(cmd[p["act"]], cwd=p["dir"], capture=True)
        except RuntimeError as e:
            raise ChangeError(f"{p['name']}: {e}") from None


def _sources(fm: dict) -> list[str]:
    return [str(s).split("#", 1)[0].strip() for s in (fm.get("x-sources") or []) if s]


def docs_to_read(title: str, files: Sequence[str] = (), limit: int = TO_READ) -> list[dict]:
    """The pages to read before coding, without AI: those whose `x-sources` cite a file in scope (`repo:path`, a
    folder covers what is under it), then a docs search on the title. Each with its trust and why it is listed."""
    want = [f.strip().replace("\\", "/") for spec in files for f in str(spec).split(",") if f.strip()]
    hits: list[dict] = []
    if want:
        for logical, f in services.current().docs.iter_docs():
            fm, body = frontmatter.split_fm(f.read_text(encoding="utf-8", errors="replace"))
            srcs = _sources(fm)
            cited = next((w for w in want if any(s == w or s.startswith(w.rstrip("/") + "/") for s in srcs)), None)
            if cited:
                hits.append({"path": logical, "section": None, "why": f"cites {cited}",
                             "trust": trust_levels.trust_of(fm, frontmatter.body_sha(body))})
    seen = {h["path"] for h in hits}
    for h in services.current().search.search(title, limit=limit):
        if h["path"] not in seen:
            hits.append({"path": h["path"], "section": h.get("section"), "trust": h["trust"], "why": "search"})
            seen.add(h["path"])
    return hits[:limit]


def start(title: str, *, item: str | None = None, repos: Sequence[str] = (), files: Sequence[str] = (),
          base: str | None = None, force: bool = False, by: str | None = None) -> dict:
    """Start a change: check everything first (repos known and present, trees clean, the item and its start gate),
    then the branch in each repo, the docs worktree, the record, and the card In Progress. A change already open for
    the same id is returned as it is (`again`). ChangeError when blocked, with nothing written."""
    from ..kanban import ops
    title = title.strip()
    if not title:
        raise ChangeError("a title is needed")
    by = by or _who()
    key = item.strip().upper() if item else None
    with _lock():
        slug = rules.slugify(title)
        id_ = rules.change_id(key, slug, secrets.token_hex(2))
        have = load(id_) if key else next((r for r in open_records() if not r.get("item") and r.get("slug") == slug
                                           and r.get("title") == title), None)
        if have and have.get("state") in rules.OPEN:
            return {"change": have, "again": True, "to_read": have.get("to_read") or [], "next": rules.next_step(have)}
        shown = None
        if key:
            try:
                shown = ops.show(key)
            except ops.BoardError as e:
                raise ChangeError(str(e)) from None
        ws = services.current().workspace
        known = ws.repo_names()
        names = list(dict.fromkeys(repos)) or list(shown["repos"] if shown else [])
        unknown = [n for n in names if n not in known]
        if unknown:
            raise ChangeError(f"unknown repo {', '.join(unknown)} (repos: {', '.join(known) or 'none'})")
        template = (ws.workspace().get("change") or {}).get("branch") or rules.BRANCH
        try:
            branch = rules.branch_name(str(template), id_, slug if key else "")
        except ValueError as e:
            raise ChangeError(str(e)) from None
        plans = [_plan_repo(n, branch, base) for n in names]
        blocked = [p["blocked"] for p in plans if "blocked" in p]
        docs_repo = paths.CTX.state_root
        if not (docs_repo / ".git").exists():
            blocked.append("cam-docs is not a git repo: a change keeps its docs in a worktree of it")
        if blocked:
            raise ChangeError("cannot start: " + "; ".join(blocked))
        gate = ops.start_gate(key, surface="change") if key else []
        if gate and not force:
            raise ChangeError(f"{ops.GateError(key, gate)} (a person can start it anyway: --force)")
        for p in plans:
            _branch(p)
        wt = paths.WORKSPACE / WORKTREES / id_
        docs_ref = out(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=docs_repo) or "HEAD"
        docs_base = out(["git", "rev-parse", "HEAD"], cwd=docs_repo)
        try:
            services.current().worktrees.attach(docs_repo, wt, branch, "HEAD")
        except RuntimeError as e:
            raise ChangeError(f"cam-docs worktree: {e}") from None
        now = _now()
        rec = {"v": 1, "id": id_, "title": title, "item": key, "slug": slug, "created": now, "by": by,
               "repos": {p["name"]: {"branch": p["branch"], "base": p["base"], "base_ref": p["base_ref"],
                                     "adopted": p["adopted"]} for p in plans},
               "docs": {"worktree": str(wt), "branch": branch, "base": docs_base, "base_ref": docs_ref},
               "phase": rules.PHASES[0], "phases": [{"phase": rules.PHASES[0], "at": now, "by": by}],
               "board": [], "prs": {}, "state": "open", "closed": None,
               "to_read": docs_to_read(" ".join([title, (shown or {}).get("description") or ""]).strip(), files)}
        _follow(rec, "start", force=force, by=by)
        _save(rec)
    return {"change": rec, "again": False, "to_read": rec["to_read"], "next": rules.next_step(rec)}


# ---------- phase, status ----------
def phase(id_: str | None, new: str, *, cwd: Path | None = None, by: str | None = None) -> dict:
    """Set the change's phase: forward only (it may skip ahead); the same phase again changes nothing."""
    with _lock():
        rec = _pick(id_, cwd)
        try:
            changed = rules.advance(rec.get("phase") or "", new)
        except ValueError as e:
            raise ChangeError(str(e)) from None
        if changed:
            rec["phase"] = new
            rec.setdefault("phases", []).append({"phase": new, "at": _now(), "by": by or _who()})
            _save(rec)
    return rec


def status(id_: str | None = None) -> list[dict]:
    """One row per open change, or the named one (open or closed)."""
    if id_:
        rec = load(id_)
        if rec is None:
            raise LookupError(f"no change {id_.strip().lower()}")
        return [row(rec)]
    return [row(r) for r in open_records()]


# ---------- link, close ----------
def link(id_: str | None, url: str, *, repo: str | None = None, cwd: Path | None = None,
         by: str | None = None) -> dict:
    """Record the change's PR for `repo` (the only repo when it has one; `docs` for the docs PR): the change is in
    review and its card goes In Review. LookupError when the repo cannot be told; ChangeError for a bad URL."""
    url = url.strip()
    if not url.startswith(("https://", "http://")):
        raise ChangeError(f"a PR is linked by its URL (https://…), not {url!r}")
    with _lock():
        rec = _pick(id_, cwd)
        names = list(rec.get("repos") or {})
        if repo is None:
            if len(names) != 1:
                raise LookupError(f"which repo is this PR for? --repo one of: {', '.join([*names, DOCS])}")
            repo = names[0]
        if repo not in (*names, DOCS):
            raise LookupError(f"{rec['id']} has no repo {repo} (--repo one of: {', '.join([*names, DOCS])})")
        rec.setdefault("prs", {})[repo] = url
        rec["state"] = "in-review"
        _follow(rec, "pr", by=by or _who())
        _save(rec)
    return rec


def _merged(repo: Path, branch: str, base_ref: str) -> bool:
    return run(["git", "merge-base", "--is-ancestor", f"refs/heads/{branch}", base_ref], cwd=repo, check=False,
               capture=True).returncode == 0


def unmerged(rec: dict) -> list[str]:
    """`repo: branch → base_ref` for each of the change's branches (and its docs branch) not yet merged into its base."""
    sides = [(n, paths.repo_dir(n), r) for n, r in (rec.get("repos") or {}).items()]
    if rec.get("docs"):
        sides.append((DOCS, paths.CTX.state_root, rec["docs"]))
    return [f"{n}: {r['branch']} → {r['base_ref']}" for n, d, r in sides
            if not (d.is_dir() and _merged(d, r["branch"], r["base_ref"]))]


def _work_in(wt: Path) -> list[str]:
    """Uncommitted paths in the docs worktree, the derived files aside."""
    if not wt.is_dir():
        return []
    st = run(["git", "status", "--porcelain", "--untracked-files=all"], cwd=wt, check=False, capture=True).stdout or ""
    found = [ln[3:].strip('"') for ln in st.splitlines() if ln.strip()]
    return [p for p in found if not derived.kit_written(p)]


def close(id_: str | None, *, abandon: bool = False, cwd: Path | None = None, by: str | None = None) -> dict:
    """Close the change. Merged (every branch an ancestor of its base, read from git, no forge): card Done.
    `abandon`: card Ready. Both remove the docs worktree, refused while it holds uncommitted work; branches stay."""
    by = by or _who()
    with _lock():
        rec = _pick(id_, cwd)
        if not abandon and (left := unmerged(rec)):
            raise ChangeError(f"{rec['id']} is not merged yet ({'; '.join(left)}): fetch, merge, or close it with "
                              "--abandon")
        wt = Path((rec.get("docs") or {}).get("worktree") or "")
        if wt.parts and (work := _work_in(wt)):
            raise ChangeError(f"the docs worktree {wt} has uncommitted work ({', '.join(work)}): commit or drop it, "
                              "then close again")
        if wt.parts and wt.exists():
            services.current().worktrees.detach(paths.CTX.state_root, wt)
        _follow(rec, "abandon" if abandon else "merged", by=by)
        rec["state"] = "closed"
        rec["closed"] = {"at": _now(), "how": "abandoned" if abandon else "merged", "by": by}
        _save(rec)
    return rec
