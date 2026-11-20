"""The guardrails against the real gitleaks and OSV-Scanner, where this machine has them (the kit's pinned copies in
~/.camarones/bin or on PATH; the OSV npm database already downloaded: a test never goes to the network). The fakes of the
other guard tests assume these tools' output; this file is what checks the assumption."""
from __future__ import annotations

import glob
import os
import shutil
from pathlib import Path

import pytest
from test_githooks import GENERATED, TOKEN, git, on_path
from test_guard_gate import check, run_gate, save, write

BIN = Path("~/.camarones/bin").expanduser()
# found before isolated_env moves HOME and takes the tools off PATH
GITLEAKS = shutil.which("gitleaks") or next(iter(sorted(glob.glob(str(BIN / "gitleaks-*" / "gitleaks*")))), "")
OSV = shutil.which("osv-scanner") or next(iter(sorted(glob.glob(str(BIN / "osv-scanner-*" / "osv-scanner*")))), "")
OSV_DB = Path("~/.camarones/osv-db").expanduser()
HAVE_OSV = bool(OSV) and (OSV_DB / "osv-scalibr" / "npm" / "all.zip").is_file()
# lodash 4.17.15 has three known advisories, two of them high
LODASH = ('{"name":"x","version":"1.0.0","lockfileVersion":3,"requires":true,"packages":{"":{"name":"x","version":"1.0.0",'
          '"dependencies":{"lodash":"4.17.15"}},"node_modules/lodash":{"version":"4.17.15"}}}')


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


@pytest.mark.skipif(not GITLEAKS, reason="gitleaks not installed")
def test_the_gate_finds_a_token_in_the_commits_with_the_real_gitleaks(kit, gate, repo, monkeypatch):
    on_path(monkeypatch, Path(GITLEAKS).parent)
    write(repo, "notes.md", f"# notes\n\ntoken: {TOKEN}\n")
    save(repo, "feat: notes")
    c = check(run_gate(kit, gate, repo), "secrets")
    assert c["status"] == "fail" and any(line.startswith("notes.md:3 ") and "github" in line.lower() for line in c["detail"])
    assert TOKEN not in " ".join(c["detail"])                                              # redacted, and never printed
    git(repo, "switch", "-q", "main")
    git(repo, "switch", "-q", "-c", "clean")
    write(repo, "a.txt", "nothing secret\n")
    save(repo, "feat: a")
    assert check(run_gate(kit, gate, repo), "secrets")["status"] == "pass"


@pytest.mark.skipif(not GITLEAKS, reason="gitleaks not installed")
def test_the_installed_hook_stops_a_staged_token_with_the_real_gitleaks(kit, repo, monkeypatch):
    on_path(monkeypatch, Path(GITLEAKS).parent)
    kit.services.guard.install_hooks()
    kit.services.guard.install_repo(repo)
    write(repo, "notes.md", f"token: {TOKEN}\n")
    git(repo, "add", "notes.md")
    note = repo.parent / "msg.txt"
    note.write_text(f"feat: token\n\n{GENERATED}\n", encoding="utf-8")
    refused = git(repo, "commit", "-q", "-F", str(note), check=False)
    assert refused.returncode != 0 and "notes.md" in refused.stderr and TOKEN not in refused.stdout + refused.stderr


@pytest.mark.skipif(not HAVE_OSV, reason="OSV-Scanner or its npm database is not on this machine")
def test_a_new_high_vulnerability_in_a_touched_lockfile_fails_with_the_real_scanner(kit, gate, repo, monkeypatch):
    import lib.binaries as binaries
    import lib.osv as osv
    monkeypatch.setattr(osv, "DB_DIR", OSV_DB)                                              # the database it already has
    monkeypatch.setattr(binaries, "ensure", lambda name, log=print: OSV)
    write(repo, "package-lock.json", LODASH)
    save(repo, "feat: add lodash")
    c = check(run_gate(kit, gate, repo), "vulns")
    assert c["status"] == "fail" and any("lodash" in line and "GHSA-" in line and "high" in line for line in c["detail"])
    git(repo, "switch", "-q", "main")                                                       # the same debt on the base: not new
    write(repo, "package-lock.json", LODASH)
    save(repo, "chore: old debt")
    git(repo, "switch", "-q", "-c", "next")
    write(repo, "src/a.js", "x")
    write(repo, "package-lock.json", LODASH.replace('"name":"x"', '"name":"y"', 1))
    save(repo, "feat: a")
    assert check(run_gate(kit, gate, repo), "vulns")["status"] == "pass"
