"""The gate (P3): checks a change must pass, each one `{id, status, detail}` with a status of pass, fail, not-run or
n/a. A change is its commits against a base branch, read from git objects, not from the working tree. A check that
could not run says `not-run` and the verdict is never `pass` (domain/guard.py): a missing scanner, no Sonar token or a
registry that did not answer is not green.

credit (an AI co-author trailer), secrets (gitleaks over the range), paths (`.env*`, keys, `secrets/`), vulns (OSV on
the lockfiles the change touches: only what the base did not already have, high or critical), outdated (opt in: sends
library names to public registries; a library the change adds or bumps that is a major behind), sonar (the project's
quality gate)."""
from __future__ import annotations

import tempfile
import zipfile
from pathlib import Path

from lib import binaries, inventory, latest as registries, osv, radar, sonar
from lib.common import load_json, out, run
from lib.domain import guard

BLOCKING = ("high", "critical")


def _check(id_: str, status: str, *detail: str) -> dict:
    return {"id": id_, "status": status, "detail": list(detail)}


def _commit(repo: Path, ref: str) -> str:
    return out(["git", "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"], cwd=repo)


def base_ref(repo: Path) -> str | None:
    """The branch a change is compared with: origin's HEAD, else origin/main, origin/master, main, master."""
    head = out(["git", "symbolic-ref", "--quiet", "refs/remotes/origin/HEAD"], cwd=repo).removeprefix("refs/remotes/")
    return next((r for r in (head, "origin/main", "origin/master", "main", "master") if r and _commit(repo, r)), None)


def _changed(repo: Path, base: str, head: str) -> list[str] | None:
    r = run(["git", "-c", "core.quotepath=off", "diff", "--name-only", "--diff-filter=ACMR", f"{base}...{head}"],
            cwd=repo, check=False, capture=True)
    return [p for p in r.stdout.splitlines() if p] if r.returncode == 0 else None


def _credit(repo: Path, rng: str) -> dict:
    r = run(["git", "log", "--format=%h%x1f%B%x1e", rng], cwd=repo, check=False, capture=True)
    if r.returncode:
        return _check("credit", "not-run", "git could not list the commits")
    bad = []
    for entry in r.stdout.split("\x1e"):
        sha, _, body = entry.strip().partition("\x1f")
        if body and guard.has_ai_credit(body):
            bad.append(f"{sha} {body.splitlines()[0]}")
    return _check("credit", "fail", *bad) if bad else _check("credit", "pass")


def _secrets(repo: Path, rng: str) -> dict:
    exe = binaries.bin_path("gitleaks")
    if not exe:
        return _check("secrets", "not-run", "gitleaks is not installed (camaron setup installs it)")
    with tempfile.TemporaryDirectory() as tmp:
        report = Path(tmp) / "report.json"
        r = run([str(exe), "git", "--no-banner", "--no-color", "--redact", "--exit-code", "99", "--log-opts", rng,
                 "--report-format", "json", "--report-path", str(report), str(repo)], check=False, capture=True)
        found = load_json(report, [])
    if r.returncode not in (0, 99) or not isinstance(found, list):
        return _check("secrets", "not-run", f"gitleaks could not scan the commits ({(r.stderr or '').strip()[-200:]})")
    lines = [f"{f.get('File')}:{f.get('StartLine')} {f.get('RuleID')} ({str(f.get('Commit'))[:8]})" for f in found]
    return _check("secrets", "fail", *lines) if r.returncode == 99 or lines else _check("secrets", "pass")


def _paths(touched: list[str]) -> dict:
    bad = [p for p in touched if guard.forbidden(p)]
    return _check("paths", "fail", *bad) if bad else _check("paths", "pass")


def _extract(repo: Path, ref: str, dest: Path) -> Path | None:
    """The manifests and lockfiles of `ref` (all of them: a pom needs its parents) in a folder; None if git failed."""
    tree = dest / "tree"
    tree.mkdir(parents=True)
    listed = run(["git", "-c", "core.quotepath=off", "ls-tree", "-r", "--name-only", ref], cwd=repo, check=False, capture=True)
    if listed.returncode:
        return None
    wanted = [p for p in listed.stdout.splitlines()
              if guard.is_lockfile(p) or any(radar.matches(p, m) for m in inventory.MANIFEST_NAMES)]
    if wanted:
        archive = dest / "tree.zip"
        if run(["git", "archive", "--format=zip", "-o", str(archive), ref, "--", *wanted], cwd=repo, check=False,
               capture=True).returncode:
            return None
        with zipfile.ZipFile(archive) as z:
            z.extractall(tree)
    return tree


def _rel(path: str, tree: Path) -> str | None:
    try:
        return Path(path).resolve().relative_to(tree.resolve()).as_posix()
    except ValueError:
        return None


def _hits(data: dict, tree: Path, touched: set[str]) -> dict[tuple, dict]:
    """(file, ecosystem, library, advisory) → advisory, for the lockfiles of `touched` only."""
    found = {}
    for result in data.get("results") or []:
        rel = _rel(str((result.get("source") or {}).get("path") or ""), tree)
        if rel in touched:
            for (eco, pkg), vulns in osv.parse({"results": [result]}).items():
                found.update({(rel, eco, pkg, v["id"]): v for v in vulns})
    return found


def _vulns(name: str, repo: Path, base: str, head: str, touched: list[str], log) -> dict:
    locks = {p for p in touched if guard.is_lockfile(p)}
    if not locks:
        return _check("vulns", "n/a", "no dependency file changed")
    exe = binaries.ensure("osv-scanner", log=log)
    if not exe:
        return _check("vulns", "not-run", "OSV-Scanner is not available on this machine")
    hits = {}
    with tempfile.TemporaryDirectory() as tmp:
        for label, ref in (("base", base), ("head", head)):
            tree = _extract(repo, ref, Path(tmp) / label)
            data = osv.scan_repo(exe, name, tree) if tree else None
            if data is None:
                return _check("vulns", "not-run", f"the scan of {ref} failed")
            hits[label] = _hits(data, tree, locks)
    new = [(k, v) for k, v in hits["head"].items() if k not in hits["base"] and v["severity"] in BLOCKING]
    lines = [f"{k[0]}: {k[2]} {v.get('version') or ''} {k[3]} ({v['severity']})"
             + (f", fixed in {v['fixed']}" if v.get("fixed") else "") for k, v in new]
    return _check("vulns", "fail", *lines) if lines else _check("vulns", "pass")


def _source(row: dict) -> str:
    return row["source"].split(":", 1)[1]


def _outdated(name: str, repo: Path, base: str, head: str, touched: list[str], asked: bool) -> dict:
    if not asked:
        return _check("outdated", "n/a", "registry lookups are off (guard: {outdated: true} in workspace.yaml, or --latest)")
    manifests = {p for p in touched if any(radar.matches(p, m) for m in inventory.MANIFEST_NAMES)}
    if not manifests:
        return _check("outdated", "n/a", "no manifest changed")
    rows: dict[str, list[dict]] = {}
    with tempfile.TemporaryDirectory() as tmp:
        for label, ref in (("base", base), ("head", head)):
            tree = _extract(repo, ref, Path(tmp) / label)
            if tree is None:
                return _check("outdated", "not-run", f"git could not read the manifests of {ref}")
            rows[label] = [r for r in inventory.scan_repo(name, tree) if _source(r) in manifests]
    had = {(_source(r), r["ecosystem"], r["name"], r["declared"]) for r in rows["base"]}
    changed = [{**r, "registry": inventory.from_registry(r["ecosystem"], r["declared"])} for r in rows["head"]
               if (_source(r), r["ecosystem"], r["name"], r["declared"]) not in had]
    answer = registries.lookup(changed, inventory.owned(), log=lambda _: None)
    versions, behind, silent = answer.get("versions") or {}, [], []
    for r in changed:
        newest = versions.get(f"{r['ecosystem']}|{r['name']}")
        current = r["version"] or r["declared"]
        if newest and (n := guard.majors_behind(current, newest)):
            behind.append(f"{_source(r)}: {r['name']} {current} → {newest} ({n} major{'s' if n > 1 else ''} behind)")
        elif not newest and r["ecosystem"] in (answer.get("failed") or []):
            silent.append(r["name"])
    if behind:
        return _check("outdated", "fail", *behind)
    if silent:
        return _check("outdated", "not-run", f"the registry did not answer for: {', '.join(silent)}")
    return _check("outdated", "pass")


def _sonar(name: str, repo: Path, ws: dict) -> dict:
    tool = next((t for t in radar.scan_repo(name, repo) if t["id"] == "sonar"), None)
    info = tool["info"] if tool else {}
    if not (tool and info.get("project")):
        return _check("sonar", "n/a", "no Sonar project in this repo")
    block = {"used": True, "project": info["project"], "organization": info.get("organization", ""),
             "host": info.get("host", ""), "link": info.get("link", "")}
    res = sonar.read(block, None, ws)
    where = f"{info['project']} on {res.get('host') or info.get('host') or 'no server'}"
    gate_status = (res.get("server") or {}).get("gate")
    if res.get("connect"):
        return _check("sonar", "not-run", f"no token for {where} is saved on this machine")
    if res.get("error"):
        return _check("sonar", "not-run", f"{where}: {res['error']}")
    if gate_status == "ERROR":
        return _check("sonar", "fail", f"quality gate ERROR for {where}")
    if gate_status in ("OK", "WARN"):
        return _check("sonar", "pass", f"quality gate {gate_status} for {where}")
    return _check("sonar", "not-run", f"{where}: no quality gate reported (is the server set in sonar.host.url or workspace.yaml?)")


def gate(name: str, repo: Path, ws: dict, *, base: str | None = None, head: str = "HEAD", latest: bool = False,
         log=print) -> dict:
    """Every check for one repo's change. `latest` (or `guard: {outdated: true}` in workspace.yaml) switches on the
    registry lookups. What fails to run is `not-run`."""
    base = base or base_ref(repo)
    ok = bool(base and _commit(repo, base) and _commit(repo, head))
    touched = _changed(repo, base, head) if ok else None
    why = f"no base to compare with ({base or 'origin/HEAD, main or master'} not found)"
    rng = f"{base}..{head}"
    asked = latest or bool((ws.get("guard") or {}).get("outdated"))
    checks = [_credit(repo, rng) if ok else _check("credit", "not-run", why),
              _secrets(repo, rng) if ok else _check("secrets", "not-run", why),
              _paths(touched) if touched is not None else _check("paths", "not-run", why),
              _vulns(name, repo, base, head, touched, log) if touched is not None else _check("vulns", "not-run", why),
              _outdated(name, repo, base, head, touched, asked) if touched is not None
              else _check("outdated", "not-run", why),
              _sonar(name, repo, ws)]
    return {"repo": name, "base": base, "head": head, "checks": checks, "verdict": guard.overall(checks)}
