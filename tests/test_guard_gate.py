"""The gate (P3, lib/adapters/guard_gate.py): checks that block. A change is read as its commits against a base branch;
what could not run is "not run", never green."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from test_githooks import TRAILER, git, on_path

NO_GITLEAKS = "gitleaks is not installed"


@pytest.fixture
def gate(kit):
    return kit.services.guard_gate


@pytest.fixture
def repo(kit, tmp_path):
    r = tmp_path / "service"
    r.mkdir()
    git(r, "init", "-q", "-b", "main")
    write(r, "README.md", "# service\n")
    save(r, "chore: base")
    git(r, "switch", "-q", "-c", "topic")
    return r


def write(repo: Path, rel: str, text: str) -> None:
    f = repo / rel
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(text, encoding="utf-8")


def save(repo: Path, msg: str) -> str:
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "--no-verify", "-m", msg)
    return git(repo, "rev-parse", "--short", "HEAD").stdout.strip()


def run_gate(kit, gate, repo: Path, **kw) -> dict:
    return gate.gate("service", repo, kit.services.workspace.workspace(), base=kw.pop("base", "main"), log=lambda _: None, **kw)


def check(report: dict, id_: str) -> dict:
    return next(c for c in report["checks"] if c["id"] == id_)


FAKE_GITLEAKS = '''import json, sys
args = sys.argv[1:]
if {code} == 99:
    with open(args[args.index("--report-path") + 1], "w", encoding="utf-8") as f:
        json.dump([{{"File": "app.env", "StartLine": 3, "RuleID": "fake-rule", "Commit": "abcdef0123456789"}}], f)
sys.exit({code})
'''


def fake_gitleaks(directory: Path, code: int) -> Path:
    """A gitleaks that writes one finding to --report-path (when told to find one) and exits `code`. A Python script
    behind a launcher the OS can run from Python: Windows cannot start an extensionless shell script."""
    directory.mkdir(parents=True, exist_ok=True)
    script = directory / "fake_gitleaks.py"
    script.write_text(FAKE_GITLEAKS.format(code=code), encoding="utf-8")
    if sys.platform == "win32":
        (directory / "gitleaks.cmd").write_text(f'@"{sys.executable}" "{script}" %*\r\n', encoding="utf-8")
    else:
        exe = directory / "gitleaks"
        exe.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{script}" "$@"\n', encoding="utf-8")
        exe.chmod(0o755)
    return directory


# ---- the range ----

def test_a_report_names_the_repo_the_range_and_a_verdict(kit, gate, repo):
    write(repo, "src/app.py", "print(1)\n")
    save(repo, "feat: app")
    report = run_gate(kit, gate, repo)
    assert (report["repo"], report["base"], report["head"]) == ("service", "main", "HEAD")
    assert [c["id"] for c in report["checks"]] == ["credit", "secrets", "paths", "vulns", "outdated", "sonar"]
    assert report["verdict"] in ("pass", "not-run")


def test_without_a_base_the_range_checks_did_not_run(kit, gate, repo):
    git(repo, "branch", "-m", "work")
    report = run_gate(kit, gate, repo, base="nope")
    assert {check(report, i)["status"] for i in ("credit", "secrets", "paths", "vulns")} == {"not-run"}
    assert report["verdict"] == "not-run"


def test_the_base_is_origin_head_then_main(kit, gate, repo, tmp_path):
    assert gate.base_ref(repo) == "main"
    remote = tmp_path / "remote.git"
    git(tmp_path, "init", "-q", "--bare", "-b", "main", str(remote))
    git(repo, "push", "-q", str(remote), "main")
    clone = tmp_path / "clone"
    git(tmp_path, "clone", "-q", str(remote), str(clone))
    assert gate.base_ref(clone) == "origin/main"


# ---- AI credit, forbidden paths ----

def test_a_commit_that_credits_ai_fails_the_gate(kit, gate, repo):
    write(repo, "a.txt", "a")
    sha = save(repo, f"feat: sneaky\n\n{TRAILER}")
    c = check(run_gate(kit, gate, repo), "credit")
    assert c["status"] == "fail" and any(sha in line for line in c["detail"])


def test_clean_commits_pass_the_credit_check(kit, gate, repo):
    write(repo, "a.txt", "a")
    save(repo, "feat: clean")
    assert check(run_gate(kit, gate, repo), "credit")["status"] == "pass"


def test_forbidden_paths_fail_and_placeholders_pass(kit, gate, repo):
    write(repo, ".env", "TOKEN=1")
    write(repo, "certs/site.pem", "x")
    write(repo, ".env.example", "TOKEN=")
    save(repo, "feat: config")
    c = check(run_gate(kit, gate, repo), "paths")
    assert c["status"] == "fail" and sorted(c["detail"]) == [".env", "certs/site.pem"]


def test_ordinary_paths_pass(kit, gate, repo):
    write(repo, "src/a.py", "x")
    save(repo, "feat: a")
    assert check(run_gate(kit, gate, repo), "paths")["status"] == "pass"


# ---- secrets ----

def test_a_leaked_secret_in_the_range_fails_and_a_clean_range_passes(kit, gate, repo, tmp_path, monkeypatch):
    write(repo, "app.env", "x")
    save(repo, "feat: env")
    on_path(monkeypatch, fake_gitleaks(tmp_path / "leak", 99))
    c = check(run_gate(kit, gate, repo), "secrets")
    assert c["status"] == "fail" and any("fake-rule" in line and "app.env:3" in line for line in c["detail"])
    on_path(monkeypatch, fake_gitleaks(tmp_path / "clean", 0))
    assert check(run_gate(kit, gate, repo), "secrets")["status"] == "pass"


def test_no_scanner_or_a_broken_one_is_not_run_never_pass(kit, gate, repo, tmp_path, monkeypatch):
    write(repo, "a.txt", "a")
    save(repo, "feat: a")
    c = check(run_gate(kit, gate, repo), "secrets")
    assert c["status"] == "not-run" and NO_GITLEAKS in c["detail"][0]
    on_path(monkeypatch, fake_gitleaks(tmp_path / "broken", 2))
    assert check(run_gate(kit, gate, repo), "secrets")["status"] == "not-run"


# ---- vulnerable dependencies: new, high or critical, in the files the change touches ----

def osv_result(path: Path, found: list[tuple[str, str, str, float]]) -> dict:
    pkgs = [{"package": {"name": n, "version": v, "ecosystem": "npm"},
             "vulnerabilities": [{"id": i, "aliases": [], "summary": f"{n} flaw", "affected": []}],
             "groups": [{"ids": [i], "max_severity": str(score)}]} for n, v, i, score in found]
    return {"results": [{"source": {"path": str(path), "type": "lockfile"}, "packages": pkgs}]} if found else {"results": []}


@pytest.fixture
def osv(kit, monkeypatch, tmp_path):
    """A scanner that reads `vulnerable: [[name, version, id, score]]` from the tree's package-lock.json."""
    calls: list[Path] = []

    def scan(exe, name, path=None):
        calls.append(path)
        lock = path / "package-lock.json"
        found = [tuple(x) for x in json.loads(lock.read_text(encoding="utf-8")).get("vulnerable", [])] if lock.is_file() else []
        return osv_result(lock, found)

    import lib.binaries as binaries
    import lib.osv as real_osv
    monkeypatch.setattr(real_osv, "scan_repo", scan)
    monkeypatch.setattr(binaries, "ensure", lambda name, log=print: "osv-scanner")
    return calls


def lock(*found) -> str:
    return json.dumps({"vulnerable": [list(f) for f in found]})


def test_a_new_critical_vulnerability_in_a_touched_lockfile_fails(kit, gate, repo, osv):
    write(repo, "package-lock.json", lock(("lodash", "4.17.0", "GHSA-1", 9.8)))
    save(repo, "feat: add lodash")
    c = check(run_gate(kit, gate, repo), "vulns")
    assert c["status"] == "fail" and any("lodash" in line and "GHSA-1" in line and "critical" in line for line in c["detail"])


def test_a_vulnerability_the_base_already_had_is_not_the_changes(kit, gate, repo, osv):
    git(repo, "switch", "-q", "main")
    write(repo, "package-lock.json", lock(("lodash", "4.17.0", "GHSA-1", 9.8)))
    save(repo, "chore: old debt")
    git(repo, "switch", "-q", "-c", "next")
    write(repo, "package-lock.json", lock(("lodash", "4.17.0", "GHSA-1", 9.8), ("left-pad", "1.0.0", "GHSA-2", 3.1)))
    save(repo, "feat: left-pad")
    c = check(run_gate(kit, gate, repo), "vulns")
    assert c["status"] == "pass"                                       # the new one is low; the critical one is old


def test_a_change_with_no_dependency_file_never_runs_the_scanner(kit, gate, repo, osv):
    write(repo, "src/a.py", "x")
    save(repo, "feat: a")
    assert check(run_gate(kit, gate, repo), "vulns")["status"] == "n/a" and osv == []


def test_no_scanner_binary_or_a_failed_scan_is_not_run(kit, gate, repo, osv, monkeypatch):
    write(repo, "package-lock.json", lock())
    save(repo, "feat: lock")
    import lib.binaries as binaries
    import lib.osv as real_osv
    monkeypatch.setattr(binaries, "ensure", lambda name, log=print: None)
    assert check(run_gate(kit, gate, repo), "vulns")["status"] == "not-run"
    monkeypatch.setattr(binaries, "ensure", lambda name, log=print: "osv-scanner")
    monkeypatch.setattr(real_osv, "scan_repo", lambda *a, **k: None)
    assert check(run_gate(kit, gate, repo), "vulns")["status"] == "not-run"


# ---- outdated libraries: opt in, the ones the change adds or bumps ----

@pytest.fixture
def registry(monkeypatch):
    import lib.latest as latest
    seen = {"rows": None, "answer": {"npm|left-pad": "3.2.0"}, "failed": []}

    def lookup(rows, owned, log=print, fetch=None):
        seen["rows"] = rows
        return {"versions": seen["answer"], "failed": seen["failed"], "checked": len(rows), "found": 1, "at": ""}

    monkeypatch.setattr(latest, "lookup", lookup)
    return seen


def manifest(**deps: str) -> str:
    return json.dumps({"name": "svc", "dependencies": deps})


def test_the_outdated_check_is_off_until_asked_and_off_is_not_not_run(kit, gate, repo, registry):
    write(repo, "package.json", manifest(**{"left-pad": "^1.0.0"}))
    save(repo, "feat: left-pad")
    c = check(run_gate(kit, gate, repo), "outdated")
    assert c["status"] == "n/a" and registry["rows"] is None


def test_a_library_the_change_adds_a_major_behind_fails(kit, gate, repo, registry):
    write(repo, "package.json", manifest(**{"left-pad": "^1.0.0"}))
    save(repo, "feat: left-pad")
    c = check(run_gate(kit, gate, repo, latest=True), "outdated")
    assert c["status"] == "fail" and any("left-pad" in line and "3.2.0" in line for line in c["detail"])


def test_the_team_can_switch_the_check_on_in_workspace_yaml(kit, gate, repo, registry):
    ws = kit.services.workspace.workspace()
    ws["guard"] = {"outdated": True}
    kit.services.workspace.save_workspace(ws)
    write(repo, "package.json", manifest(**{"left-pad": "^1.0.0"}))
    save(repo, "feat: left-pad")
    assert check(run_gate(kit, gate, repo), "outdated")["status"] == "fail"


def test_libraries_the_change_did_not_touch_or_that_are_current_pass(kit, gate, repo, registry):
    git(repo, "switch", "-q", "main")
    write(repo, "package.json", manifest(**{"left-pad": "^1.0.0"}))
    save(repo, "chore: old debt")
    git(repo, "switch", "-q", "-c", "next")
    write(repo, "package.json", manifest(**{"left-pad": "^1.0.0", "right-pad": "^3.1.0"}))
    save(repo, "feat: right-pad")
    registry["answer"] = {"npm|left-pad": "3.2.0", "npm|right-pad": "3.2.0"}
    c = check(run_gate(kit, gate, repo, latest=True), "outdated")
    assert c["status"] == "pass" and [r["name"] for r in registry["rows"]] == ["right-pad"]


def test_a_registry_that_did_not_answer_is_not_run(kit, gate, repo, registry):
    write(repo, "package.json", manifest(**{"left-pad": "^1.0.0"}))
    save(repo, "feat: left-pad")
    registry["answer"], registry["failed"] = {}, ["npm"]
    assert check(run_gate(kit, gate, repo, latest=True), "outdated")["status"] == "not-run"


def test_no_manifest_touched_means_nothing_to_look_up(kit, gate, repo, registry):
    write(repo, "src/a.py", "x")
    save(repo, "feat: a")
    assert check(run_gate(kit, gate, repo, latest=True), "outdated")["status"] == "n/a" and registry["rows"] is None


# ---- Sonar's quality gate ----

SONAR_PROPS = "sonar.projectKey=svc\nsonar.host.url=https://sonar.example.com\n"


@pytest.fixture
def sonar(monkeypatch):
    import lib.sonar as real
    seen = {"block": {}}
    monkeypatch.setattr(real, "read", lambda repo_sonar, previous, ws, session=None: {**repo_sonar, **seen["block"]})
    return seen


def with_sonar(repo: Path) -> None:
    write(repo, "sonar-project.properties", SONAR_PROPS)
    save(repo, "chore: sonar")


@pytest.mark.parametrize("block,status", [({"server": {"gate": "ERROR"}}, "fail"), ({"server": {"gate": "OK"}}, "pass"),
                                          ({"server": {"gate": "WARN"}}, "pass"), ({"connect": True}, "not-run"),
                                          ({"error": "sin conexión"}, "not-run"), ({"server": {"gate": None}}, "not-run")])
def test_the_quality_gate_decides_and_a_server_that_did_not_say_is_not_run(kit, gate, repo, sonar, block, status):
    with_sonar(repo)
    sonar["block"] = block
    assert check(run_gate(kit, gate, repo), "sonar")["status"] == status


def test_a_repo_with_no_sonar_project_is_not_applicable(kit, gate, repo, sonar):
    write(repo, "a.txt", "a")
    save(repo, "feat: a")
    assert check(run_gate(kit, gate, repo), "sonar")["status"] == "n/a"


def test_a_red_gate_names_the_server_and_the_project(kit, gate, repo, sonar):
    with_sonar(repo)
    sonar["block"] = {"server": {"gate": "ERROR"}}
    detail = " ".join(check(run_gate(kit, gate, repo), "sonar")["detail"])
    assert "svc" in detail and "sonar.example.com" in detail
