"""Freshness (R23, R30: H14, H27). When a page is written, each of its x-sources is fingerprinted: its lines without
whitespace, blank or comment-only lines. L1: `repo:path#Lx-Ly` or a whole file. L2: `repo:path#Class.method`, a
symbol found again wherever it moved (lib/harness/symbols.py). L3: `docs/<page>.md` and `c4:<element>`, the pages and
C4 elements a derived page builds on. Later the page is `fresh`, `suspect` (the cited code or element changed, a cited
page is suspect, or a cited element lost its evidence), `stale` (gone) or `unverified` (no sources). Fingerprints live
in docs/.work/fresh.json (main cam-docs, never in unit worktrees).

C4 evidence (spec §5): every element and relation gets a state from the code anchors it names (lib/domain/c4). Its
stamps live under `c4` in the same file, taken again when its block in the .c4 changes or a person acknowledges it.

The AI gate: with `freshness: {ai_policy: block}` (the default) agents never get suspect or stale pages, nor
unreviewed pages without sources — better no information than wrong information. People still see them."""
from __future__ import annotations

import datetime as dt
import functools
import hashlib
import os
import re
from pathlib import Path, PurePosixPath

from .. import adr_doc, c4edit
from ..common import CAM_DIR, CTX, ROOT, WORK, load_json, repo_dir, save_json
from .locks import FileLock, LockBusy
from ..domain.c4 import anchors, evidence
from ..domain.c4.evidence import relation_key  # noqa: F401  (callers name it freshness.relation_key)
from ..domain.docs import frontmatter, logical_paths
from ..app import services

FILE = WORK / "fresh.json"
LOCK = CTX.state_root / ".camarones" / ".cache" / "locks" / "fresh.lock"
COMMENT = re.compile(r"^(//|#|/\*|\*|<!--|-->|--\s|;)")
OUT_OF_DATE = ("suspect", "stale")
META_BLOCK = re.compile(rf"\bmetadata\s*\{{(?:{c4edit.STR}|[^{{}}'\"])*\}}")
FINGERPRINTED = ("lines", "symbol")             # the other anchors are checked for existence only (spec §5.3)
SECTIONS = ("elements", "relations")
SKIP_DIRS = frozenset({".git", "node_modules", "target", "build", "dist", ".gradle", ".idea", ".venv", "venv",
                       "__pycache__", ".next", "coverage", "vendor"})     # quickarch.SKIP_DIRS' build and tool folders
NO_MODEL = {"elements": {}, "relations": []}


def _now() -> str:
    return dt.datetime.now().replace(microsecond=0).isoformat()


def parse(ref: str) -> tuple[str | None, str, tuple[int, int] | None]:
    ref = str(ref).strip()
    if ref.startswith("repo://"):
        ref = ref[len("repo://"):].replace("/", ":", 1)
    ref, _, anchor = ref.partition("#")
    repo, _, path = ref.partition(":") if ":" in ref else (None, "", ref)
    m = re.fullmatch(r"L(\d+)(?:-L?(\d+))?", anchor or "")
    span = (int(m.group(1)), int(m.group(2) or m.group(1))) if m else None
    return repo, path, span


def _file(repo: str | None, path: str) -> Path:
    if repo in (None, "", "umbrella", ".", CAM_DIR):
        return ROOT / path
    return repo_dir(repo) / path


def _norm(lines: list[str]) -> list[str]:
    out = []
    for line in lines:
        s = re.sub(r"\s+", " ", line.strip())
        if s and not COMMENT.match(s):
            out.append(s)
    return out


def _hash(lines: list[str]) -> str:
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()[:16]


def kind(ref: str) -> str:
    """code | symbol | doc | c4, from how the source is written."""
    raw = str(ref).strip()
    if raw.startswith("c4:"):
        return "c4"
    repo, path, span = parse(raw)
    if repo in (None, "", "umbrella", ".", CAM_DIR) and path.startswith("docs/") and path.endswith(".md"):
        return "doc"
    from .symbols import PY, BRACES
    anchor = raw.partition("#")[2]
    return "symbol" if anchor and span is None and Path(path).suffix.lower() in (*PY, *BRACES) else "code"


def _c4_lines(element: str) -> list[str] | None:
    """The element's lines as the v1 fingerprint found them (one file, no `extend`): only to migrate v1 stamps."""
    from .symbols import locate
    arch = services.current().diagrams.arch_dir()          # docs/architecture, or the repo folder workspace.yaml names
    for f in sorted(arch.rglob("*.c4")) if arch.is_dir() else []:
        lines = f.read_text(encoding="utf-8", errors="replace").splitlines()
        found = locate(lines, element, ".c4")
        if found:
            return lines[found[0]:found[1] + 1]
    return None


@functools.lru_cache(maxsize=1)
def _parsed(texts: tuple[tuple[str, str], ...]) -> tuple[dict, str | None]:
    try:
        return c4edit.index(dict(texts)), None
    except Exception as e:                       # a model c4edit cannot read: no states, and why
        return NO_MODEL, str(e) or type(e).__name__


def _model() -> tuple[dict[str, list[str]], dict, str | None]:
    """Each .c4 file's lines, c4edit's index of them and why it could not be read; parsed again only when a file
    changed. A caller that needs it more than once (states()) reads it once and passes it on as `model`."""
    arch = services.current().diagrams.arch_dir()
    try:
        texts = tuple((f.relative_to(arch).as_posix(), f.read_text(encoding="utf-8", errors="replace"))
                      for f in (sorted(arch.rglob("*.c4")) if arch.is_dir() else []))
    except OSError as e:
        return {}, NO_MODEL, f"C4 model not read: {e}"
    return {rel: text.split("\n") for rel, text in texts}, *_parsed(texts)


def _c4_text(block: list[str]) -> list[str]:
    """An element's block as its v2 fingerprint reads it: no metadata blocks, tags or braces, so adding evidence or
    confirming it (which turns a one-line element into a block) is no change."""
    parts = re.split(f"({c4edit.STR})", META_BLOCK.sub(" ", "\n".join(block)))
    return _norm("".join(p if i % 2 else re.sub(r"#[\w-]+|[{}]", " ", p) for i, p in enumerate(parts)).split("\n"))


def c4_exists(element: str, model=None) -> bool:
    """`c4:<element>` names an element the C4 model still has (fragments and `extend` included)."""
    return element.strip() in (model or _model())[1]["elements"]


def _block(ref: str, read=None) -> list[str] | None:
    """The lines a symbol source stands for now, or None when it is gone."""
    from .symbols import locate
    repo, path, _ = parse(ref)
    lines = (read or _lines)(repo, path)
    if lines is None:
        return None
    found = locate(lines, str(ref).partition("#")[2].strip(), Path(path).suffix)
    return lines[found[0]:found[1] + 1] if found else None


def _lines(repo, path) -> list[str] | None:
    f = _file(repo, path)
    try:
        return f.read_text(encoding="utf-8", errors="replace").splitlines()
    except (OSError, ValueError):
        return None


def fingerprint(ref: str, read=None, model=None) -> dict | None:
    """The cited code as {h, n}: hash and number of meaningful lines. None when the file or the range is missing.
    `read(repo, path)` gives the file's lines some other way (another commit); default: the working tree. `model`:
    the C4 model as _model() read it, for `c4:` sources."""
    k = kind(ref)
    if k == "doc":
        return {"k": "doc"}                         # L3: a cited page counts through its own state, not its text
    if k == "c4":
        files, idx, _ = model or _model()
        el = idx["elements"].get(str(ref).strip()[3:].strip())
        if el is None:
            return None
        text = _c4_text(files[el["file"]][el["start"]:el["end"] + 1])
        return {"h": _hash(text), "n": len(text), "k": "c4", "v": 2}
    if k == "symbol":
        block = _block(ref, read)
        return {"h": _hash(_norm(block)), "n": len(_norm(block)), "k": k} if block is not None else None
    repo, path, span = parse(ref)
    lines = (read or _lines)(repo, path)
    if lines is None or (span and span[1] > len(lines)):
        return None
    block = _norm(lines[span[0] - 1:span[1]] if span else lines)
    return {"h": _hash(block), "n": len(block)}


def check_source(ref: str, stamp: dict | None, read=None, model=None) -> str:
    """fresh | changed | missing, for one source against its fingerprint."""
    if not isinstance(stamp, dict):
        return "missing"
    k = kind(ref)
    if k in ("symbol", "c4") and stamp.get("k"):
        now = fingerprint(ref, read, model)
        return "missing" if now is None else "fresh" if now["h"] == stamp["h"] else "changed"
    repo, path, span = parse(ref)
    if k == "symbol":                               # stamped before L2: the whole file was fingerprinted
        lines = (read or _lines)(repo, path)
        return "missing" if lines is None else "fresh" if _hash(_norm(lines)) == stamp["h"] else "changed"
    lines = (read or _lines)(repo, path)
    if lines is None:
        return "missing"
    now = fingerprint(ref, read)
    if now and now["h"] == stamp["h"]:
        return "fresh"
    if span:                                    # the same code moved inside the file (lines added above it)
        norm, n = _norm(lines), stamp["n"]
        if n and any(_hash(norm[i:i + n]) == stamp["h"] for i in range(0, len(norm) - n + 1)):
            return "fresh"
        if span[1] > len(lines):
            return "missing"
    return "changed"


def _pages() -> dict:
    """logical path → (frontmatter, body sha) for every page."""
    out = {}
    for logical, f in services.current().docs.iter_docs():
        fm, body = frontmatter.split_fm(f.read_text(encoding="utf-8"))
        out[logical] = (fm or {}, frontmatter.body_sha(body))
    return out


def docs_alias(logical: str, known) -> str:
    """The page's logical path today for one written as `docs/…` or a wiki page's pre-4.81 repos/<repo>/…."""
    return logical_paths.link_target(logical, known)


def _sources(fm: dict) -> list[str]:
    return [str(s) for s in (fm.get("x-sources") or []) if s]


def _load() -> dict:
    data = load_json(FILE, {})
    return data if isinstance(data, dict) and isinstance(data.get("pages"), dict) else {"v": 1, "pages": {}}


def _stamp(entry_for: dict, logical: str, fm: dict, sha: str, by: str | None = None, model=None) -> None:
    entry_for[logical] = {"body_sha": sha, "at": _now(), **({"by": by} if by else {}),
                          "sources": {s: fingerprint(s, model=model) for s in _sources(fm)}}


def _migrate_c4(entry: dict, model=None) -> int:
    """A `c4:` source stamped before v2 takes the v2 fingerprint when its element did not change since (the v1 hash
    still matches), or, for a null stamp (v1 never found an element declared through `extend`), when the model has
    the element now. Otherwise it is marked `v: 1` (still `changed`, or `missing`), so it is looked at only once."""
    sources = entry.get("sources") if isinstance(entry, dict) else None
    n = 0
    for s, st in (sources.items() if isinstance(sources, dict) else ()):
        if kind(s) != "c4" or not (st is None or isinstance(st, dict) and "v" not in st):
            continue
        if st is None:
            now = fingerprint(s, model=model)
        else:
            old = _c4_lines(str(s).strip()[3:])
            now = fingerprint(s, model=model) if old is not None and _hash(_norm(old)) == st.get("h") else None
        sources[s] = now or {**(st or {"h": "", "n": 0, "k": "c4"}), "v": 1}
        n += 1
    return n


def stamp_all(pages: dict | None = None, model=None) -> int:
    """Fingerprint pages that are new, rewritten, or cite other sources since their last stamp: a page written now
    reflects the code as it is now. Pages that did not change keep their old fingerprints."""
    pages = pages if pages is not None else _pages()
    with FileLock(LOCK):
        data = _load()
        n = sum(_migrate_c4(e, model) for e in data["pages"].values())
        for old in [k for k in data["pages"] if k not in pages]:       # a wiki page's pre-4.81 path: keep its stamp
            new = docs_alias(old, pages)
            if new != old and new not in data["pages"]:
                data["pages"][new] = data["pages"].pop(old)
                n += 1
        for logical, (fm, sha) in pages.items():
            srcs = _sources(fm)
            e = data["pages"].get(logical)
            if srcs and (not e or e.get("body_sha") != sha or set(e.get("sources", {})) != set(srcs)):
                _stamp(data["pages"], logical, fm, sha, model=model)
                n += 1
        for gone in set(data["pages"]) - set(pages):
            del data["pages"][gone]
            n += 1
        if n or not FILE.exists():
            save_json(FILE, data)
        return n


def ack(logicals: list[str], by: str) -> list[str]:
    """A person says the page still holds for the current code: take today's code as its reference."""
    pages = _pages()
    with FileLock(LOCK):
        data = _load()
        done = []
        for logical in logicals:
            logical = docs_alias(logical, pages)
            if logical in pages:
                _stamp(data["pages"], logical, *pages[logical], by=by)
                done.append(logical)
        save_json(FILE, data)
    return done


def flag(logical: str, reason: str, by: str = "agent") -> None:
    """Someone (an agent through the MCP) says the page no longer matches the code: suspect until it is rewritten or
    acknowledged — both stamp it again, which drops the flag."""
    logical = docs_alias(logical, _pages())
    with FileLock(LOCK):
        data = _load()
        data["pages"].setdefault(logical, {"sources": {}})["flag"] = {"reason": reason, "by": by, "at": _now()}
        save_json(FILE, data)


# ---------- C4 evidence (spec §5.1–§5.3) ----------
def _c4_items(model=None) -> list[tuple]:
    files, idx, _ = model or _model()
    return evidence.items(files, idx)


def _repos() -> set[str]:
    return set(services.current().workspace.repo_names())


def _ref(a: anchors.Anchor) -> str:
    return f"{a.repo}:{a.path}" + (f"#{a.anchor}" if a.anchor else "")


def _reach(a: anchors.Anchor, repos: set[str]) -> str | None:
    """`missing` for a repo workspace.yaml does not list, `unchecked` for one not cloned here, None if readable."""
    if a.repo not in repos:
        return "missing"
    return None if repo_dir(a.repo).is_dir() else "unchecked"


def _any_file(root: Path, base: Path, glob: anchors.Anchor | None = None) -> bool:
    """A file under `base` (one `glob` covers, on its repo-relative posix path), outside build and tool folders; the
    first one ends the walk."""
    for top, dirs, names in os.walk(base):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in names:
            if glob is None or anchors.covers(glob, glob.repo, (Path(top) / name).relative_to(root).as_posix()):
                return True
    return False


def _result(a: anchors.Anchor, fps: dict, repos: set[str]) -> str:
    """fresh | changed | missing | unchecked, for one anchor: lines and symbols against their fingerprint, the rest by
    existence."""
    if why := _reach(a, repos):
        return why
    if a.kind in FINGERPRINTED:
        return check_source(_ref(a), fps.get(a.raw))
    root, parts = repo_dir(a.repo), PurePosixPath(a.path).parts
    if a.kind == "repo":
        return "fresh"
    if a.kind == "file":
        return "fresh" if root.joinpath(*parts).is_file() else "missing"
    if a.kind == "glob":                          # walk only below the part before the first wildcard
        parts = parts[:next(i for i, p in enumerate(parts) if any(c in p for c in anchors.GLOB_CHARS))]
    return "fresh" if _any_file(root, root.joinpath(*parts), a if a.kind == "glob" else None) else "missing"


def _c4_of(data: dict) -> dict:
    """fresh.json's `c4` key, with what is not a dict (a merge resolved by hand) read as no stamp."""
    c4 = data["c4"] = data["c4"] if isinstance(data.get("c4"), dict) else {}
    for section in SECTIONS:
        entries = c4.get(section) if isinstance(c4.get(section), dict) else {}
        c4[section] = {k: e for k, e in entries.items() if isinstance(e, dict)}
        for e in c4[section].values():
            fps = e.get("anchors") if isinstance(e.get("anchors"), dict) else {}
            e["anchors"] = {raw: fp for raw, fp in fps.items() if fp is None or isinstance(fp, dict)}
    return c4


def _c4_stamp(block: list[str], got: list, repos: set[str], old: dict, by: str | None) -> dict:
    """An anchor whose repo is not cloned here keeps the fingerprint another machine took (fresh.json is shared)."""
    fps = {}
    for a in (a for a in got if a.kind in FINGERPRINTED):
        why = _reach(a, repos)
        if why is None:
            fps[a.raw] = fingerprint(_ref(a))
        elif why == "unchecked" and a.raw in old:
            fps[a.raw] = old[a.raw]
    return {"sha": _hash(block), "at": _now(), **({"by": by} if by else {}), "anchors": fps}


def _apply(c4: dict, items: list, repos: set[str], ack: set[str], by: str | None, prune: bool) -> int:
    n = 0
    for section, key, _, block, got, _ in items:
        e = c4[section].get(key)
        if not e or e.get("sha") != _hash(block) or key in ack:
            c4[section][key] = _c4_stamp(block, got, repos, (e or {}).get("anchors", {}), by if key in ack else None)
            n += 1
            continue
        for a in got:
            if a.kind in FINGERPRINTED and a.raw not in e["anchors"] and not _reach(a, repos):
                e["anchors"][a.raw] = fingerprint(_ref(a))
                n += 1
    for section in SECTIONS if prune else ():
        for gone in set(c4[section]) - {key for s, key, *_ in items if s == section}:
            del c4[section][gone]
            n += 1
    return n


def _c4_sync(items: list, repos: set[str], ack: set[str] = frozenset(), by: str | None = None,
             prune: bool = False) -> tuple[dict, int, str | None]:
    """Stamp what is new, was edited or is acknowledged; fingerprint an anchor whose repo is first seen here; with
    `prune`, drop what is gone. Nothing to change: no lock, no write. Returns the stamps, how many changed and why they
    could not be read or saved (then the stamps are this call's own)."""
    c4, error = _c4_of({}), None
    try:
        c4 = _c4_of(_load())
    except OSError as e:
        error = f"C4 stamps not read: {e}"
    if not items or not _apply(c4, items, repos, ack, by, prune) or error:
        return c4, 0, error
    try:
        with FileLock(LOCK):
            data = _load()
            n = _apply(_c4_of(data), items, repos, ack, by, prune)
            if n:
                save_json(FILE, data)
            return data["c4"], n, None
    except (OSError, LockBusy) as e:
        return c4, 0, f"C4 stamps not saved: {e}"


def _evaluate(items: list, repos: set[str], prune: bool = False) -> dict:
    stamps, _, error = _c4_sync(items, repos, prune=prune)
    out: dict = {"elements": {}, "relations": {}, "error": error}
    for item in items:
        fps = (stamps[item[0]].get(item[1]) or {}).get("anchors") or {}
        out[item[0]][item[1]] = evidence.report(item, [_result(a, fps, repos) for a in item[4]])
    return out


def c4_stamp_all() -> int:
    """Stamp the C4 elements and relations that are new or whose block changed; drop the stamps of the gone ones."""
    return _c4_sync(_c4_items(), _repos(), prune=True)[1]


def c4_ack(fqns: list[str], by: str) -> list[str]:
    """A person says these elements (or relations, by key) still hold for the current code: take today's code as their
    reference."""
    items = [i for i in _c4_items() if i[1] in fqns]
    done = {i[1] for i in items}
    _c4_sync(items, _repos(), done, by)
    return [f for f in fqns if f in done]


def c4_states() -> dict:
    """Every element's and relation's evidence state (spec §5.2): {elements, relations, error}. New or edited ones get
    their stamps first."""
    model = _model()
    out = _evaluate(_c4_items(model), _repos(), prune=True)
    out["error"] = model[2] or out["error"]
    return out


def _cited_states(model, fqns: set[str]) -> dict:
    """The states of the elements pages cite, and only those: relations and the rest of the model stay out of a gate."""
    files, idx, _ = model
    items = [evidence.element_item(f, idx["elements"], files) for f in sorted(fqns)]
    return _evaluate([i for i in items if i], _repos())["elements"]


def states() -> dict[str, dict]:
    """Every page's freshness: {state, changed, missing}. New or rewritten pages get their fingerprints first."""
    pages = _pages()
    decisions = {logical for logical, (fm, _) in pages.items() if adr_doc.is_decision(logical, fm.get("type"))}
    cited = {logical: [s.strip()[3:].strip() for s in _sources(fm) if kind(s) == "c4"]
             for logical, (fm, _) in pages.items()}
    model = _model() if any(cited.values()) else None
    stamp_all(pages, model)
    data = _load()["pages"]
    c4 = {"model": model, "cited": {f for logical, fqns in cited.items() if logical not in decisions for f in fqns}}
    out = {}
    for logical, (fm, _) in pages.items():
        srcs = _sources(fm)
        if srcs:                                     # pages without sources stay out: _settle calls them unverified
            stamps = (data.get(logical) or {}).get("sources", {})
            out[logical] = {s: _check_page_source(s, stamps.get(s), logical in decisions, c4) for s in srcs
                            if kind(s) != "doc"}
        flagged = (data.get(logical) or {}).get("flag")
        if flagged:
            out.setdefault(logical, {})[f"flagged: {flagged['reason']} ({flagged.get('by', '?')})"] = "changed"
    return _settle(pages, out)


def _check_page_source(s: str, stamp: dict | None, decision: bool, c4: dict) -> str:
    """check_source, plus spec §5.4 for `c4:` sources: a decision only needs its element to exist; another page goes
    suspect when its element is broken, or has no evidence and no person vouched for it. `c4` holds this call's model,
    the cited elements and, once first needed, their states."""
    if kind(s) != "c4":
        return check_source(s, stamp)
    fqn = s.strip()[3:].strip()
    if decision:
        return "fresh" if c4_exists(fqn, c4["model"]) else "missing"
    result = check_source(s, stamp, model=c4["model"])
    if result == "fresh":
        if "elements" not in c4:
            c4["elements"] = _cited_states(c4["model"], c4["cited"])
        el = c4["elements"].get(fqn) or {}
        if el.get("state") == "broken" or (el.get("state") == "no-evidence" and not el.get("confirmed")):
            return "changed"
    return result


def _settle(pages: dict, own: dict) -> dict[str, dict]:
    """L3: a cited page passes on its state. Repeated until nothing changes, so chains and cycles settle."""
    docs_of = {logical: [s for s in _sources(fm) if kind(s) == "doc"] for logical, (fm, _) in pages.items()}
    result: dict[str, dict] = {}

    def summarise(logical: str) -> dict:
        if logical not in own:
            return {"state": "unverified", "changed": [], "missing": []}
        res = dict(own[logical])
        for s in docs_of[logical]:
            cited = parse(s)[1][len("docs/"):]
            if cited not in pages:
                res[s] = "missing"
            else:
                res[s] = "changed" if result.get(cited, {}).get("state") in OUT_OF_DATE else "fresh"
        changed = [s for s, r in res.items() if r == "changed"]
        missing = [s for s, r in res.items() if r == "missing"]
        return {"state": "stale" if missing else "suspect" if changed else "fresh", "changed": changed,
                "missing": missing}
    for _ in range(len(pages) + 1):
        new = {logical: summarise(logical) for logical in pages}
        if new == result:
            break
        result = new
    return result


def stamped(logical: str) -> dict | None:
    """When the page's sources were last fingerprinted, and by whom when a person acknowledged it: {at, by?}."""
    pages = _load()["pages"]
    e = pages.get(docs_alias(logical, pages)) or {}
    return {k: e[k] for k in ("at", "by") if e.get(k)} or None


def status(logical: str) -> dict:
    st = states()
    return st.get(docs_alias(logical, st), {"state": "unverified", "changed": [], "missing": []})


def policy() -> str:
    return (services.current().workspace.workspace().get("freshness") or {}).get("ai_policy", "block")


def code_paths(refs: list[str]) -> list[str]:
    """Sources as paths an agent can open from the workspace: <repo>/<path>[#Lx-Ly]."""
    out = []
    for ref in refs:
        k = kind(ref)
        if k == "c4":
            out.append(str(ref).strip())
            continue
        repo, path, span = parse(ref)
        anchor = f"#L{span[0]}-L{span[1]}" if span else f"#{str(ref).partition('#')[2]}" if k == "symbol" else ""
        out.append(f"{repo + '/' if repo else ''}{path}{anchor}")
    return out


def gate(logical: str, trust: str, state: dict | None = None) -> tuple[bool, str | None]:
    """Whether an agent may read this page, and the notice to show with it (or instead of it)."""
    st = state or status(logical)
    blocking = policy() == "block"
    if st["state"] in OUT_OF_DATE:
        what = st["missing"] + st["changed"]
        why = ("its code is gone" if st["state"] == "stale" else "its code changed since it was written")
        notice = (f"{'withheld' if blocking else 'may be out of date'}: {logical} — {why}. Read the code instead: "
                  + ", ".join(code_paths(what)))
        return (not blocking), notice
    if st["state"] == "unverified" and trust != "confirmed":
        notice = (f"{'withheld' if blocking else 'unreviewed'}: {logical} has no sources to check it against and "
                  "awaits review by a person.")
        return (not blocking), notice
    return True, None


def refresh_unit() -> dict:
    """An agent unit that re-documents the out-of-date pages (what changed is in its note)."""
    from .. import plan
    out = {p: s for p, s in states().items() if s["state"] in OUT_OF_DATE}
    note = "; ".join(f"{p} ({s['state']}: {', '.join(code_paths(s['missing'] + s['changed']))})" for p, s in out.items())
    u = plan.ensure("refresh-docs", "refresh-docs", title="Refresh the pages whose code changed")
    return plan.set_status(u["id"], "todo", note or "nothing out of date", record=False)
