"""P3 wired into the project: setup and repair install the guardrails in every repo and cam-docs, `doctor` reports drift,
uninstall puts the repos back as they were, `camaron guard` runs them from the command line. Nothing is written into a
tracked file of a service repo."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from test_githooks import TRAILER, commit, git, message
from test_guard_hooks import hook
from test_install_state import fake_tools

from conftest import KIT_DIR
from fixtures.builder import snapshot

OFF = {"commit": "", "pr": "", "sessionUrl": False}
QUIET = lambda _: None                                   # noqa: E731


def local_settings(repo: Path) -> dict:
    f = repo / ".claude" / "settings.local.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.is_file() else {}


def hooks_path(repo: Path) -> str:
    return git(repo, "config", "--local", "--get", "core.hooksPath", check=False).stdout.strip()


def test_wiring_a_repo_installs_the_guardrails_and_writes_no_tracked_file(kit):
    repo, before = kit.ws / "api", snapshot(kit.ws / "api")
    kit.services.setup.wire_one("api", QUIET, comps=[])
    assert hooks_path(repo) == kit.services.guard.HOOKS_DIR.as_posix()
    assert local_settings(repo)["attribution"] == OFF
    assert git(repo, "status", "--porcelain").stdout == ""
    assert git(repo, "check-ignore", "-q", ".claude/settings.local.json", check=False).returncode == 0
    assert {k for k in snapshot(repo) if k not in before} == {".claude/settings.local.json"}      # the ignored file, nothing else
    assert commit(repo, f"feat: x\n\n{TRAILER}").returncode == 0 and message(repo) == "feat: x"


def test_wiring_the_umbrella_guards_cam_docs_and_its_push_runs_the_docs_check(wired):
    docs = wired.root
    wired.services.setup.wire_umbrella(QUIET, comps=["agents"])
    assert hooks_path(docs) == wired.services.guard.HOOKS_DIR.as_posix()
    assert git(docs, "config", "--local", "--get", "camaron.check").stdout.strip() == "true"
    assert local_settings(docs)["attribution"] == OFF
    assert local_settings(wired.ws)["attribution"] == OFF                   # where agents open


def test_a_repo_that_already_has_its_own_hooks_keeps_them_through_setup(kit):
    repo = kit.ws / "web"
    hook(repo / ".husky" / "_" / "pre-commit", 'echo husky > "$(git rev-parse --show-toplevel)/husky-ran"')
    git(repo, "config", "core.hooksPath", ".husky/_")
    kit.services.setup.wire_one("web", QUIET, comps=[])
    kit.services.setup.wire_one("web", QUIET, comps=[])                                          # twice: still one chain
    assert git(repo, "config", "--local", "--get", "camaron.chain").stdout.strip() == ".husky/_"
    assert commit(repo, f"feat: husky\n\n{TRAILER}").returncode == 0
    assert (repo / "husky-ran").is_file() and message(repo) == "feat: husky"


def test_doctor_sees_a_repo_whose_hooks_went_and_repair_puts_them_back(wired, monkeypatch):
    from lib import install_state
    fake_tools(wired, monkeypatch)
    install_state.repair(log=QUIET)
    assert install_state.drift() == []
    git(wired.ws / "api", "config", "--local", "--unset", "core.hooksPath")
    (wired.root / ".claude" / "settings.local.json").write_text("{}\n", encoding="utf-8")
    got = {(d["path"], d["what"]) for d in install_state.drift()}
    assert ("api", "git hooks") in got and ("cam-docs", "Claude Code attribution") in got
    assert install_state.repair(log=QUIET) == []
    assert hooks_path(wired.ws / "api")


def test_a_project_can_leave_the_guardrails_out(wired, monkeypatch):
    from lib import install_state
    fake_tools(wired, monkeypatch)
    ws = wired.services.workspace.workspace()
    ws["guard"] = {"install": False}
    wired.services.workspace.save_workspace(ws)
    install_state.repair(log=QUIET)
    assert hooks_path(wired.ws / "api") == "" and install_state.drift() == []


def test_uninstall_puts_a_repo_back_as_it_was(kit):
    from lib import uninstall
    repo = kit.ws / "worker"
    git(repo, "config", "core.hooksPath", ".husky/_")
    before, config = snapshot(repo), git(repo, "config", "--local", "--list").stdout
    kit.services.setup.wire_one("worker", QUIET, comps=[])
    plan = uninstall.RepoCleaner("worker", dry=True).run()
    assert any(".git/config" in a for a in plan) and any("settings.local.json" in a for a in plan)
    assert hooks_path(repo) != ".husky/_"                                                        # a dry run changes nothing
    uninstall.RepoCleaner("worker", dry=False).run()
    assert git(repo, "config", "--local", "--list").stdout == config
    assert snapshot(repo) == before and not (repo / ".claude").exists()


def test_uninstall_leaves_the_attribution_a_person_set_alone(kit):
    from lib import uninstall
    repo = kit.ws / "worker"
    (repo / ".claude").mkdir()
    (repo / ".claude" / "settings.local.json").write_text(json.dumps({"attribution": {"commit": "mine", "pr": ""}}), encoding="utf-8")
    kit.services.guard.install_attribution([repo / ".claude" / "settings.local.json"])
    assert local_settings(repo)["attribution"]["commit"] == ""                                   # install overrode it: the guardrail
    (repo / ".claude" / "settings.local.json").write_text(json.dumps({"attribution": {"commit": "mine", "pr": ""}, "x": 1}),
                                                          encoding="utf-8")
    uninstall.RepoCleaner("worker", dry=False).run()
    assert local_settings(repo) == {"attribution": {"commit": "mine", "pr": ""}, "x": 1}          # not what the kit wrote: kept


# ---- camaron guard ----

def cli(kit, *args: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "CAMARONES_ROOT": str(kit.root), "CAMARONES_WORKSPACE": str(kit.ws)}
    return subprocess.run([sys.executable, str(KIT_DIR / "camarones.py"), "guard", *args], env=env, cwd=kit.ws,
                          capture_output=True, text=True, encoding="utf-8")


def test_guard_install_and_status_from_the_command_line(wired):
    kit = wired
    before = cli(kit, "status", "--json")
    assert before.returncode == 0, before.stderr
    assert {r["name"] for r in json.loads(before.stdout)["repos"]} == {"api", "web", "worker", "cam-docs"}
    assert all(r["hooks"] for r in json.loads(before.stdout)["repos"])                           # nothing installed yet
    done = cli(kit, "install")
    assert done.returncode == 0, done.stderr
    after = json.loads(cli(kit, "status", "--json").stdout)["repos"]
    assert all(r["hooks"] is None and r["attribution"] for r in after)
    again = cli(kit, "install").stdout
    assert any(w in again for w in ("already", "ya instaladas"))
    gone = cli(kit, "uninstall", "--repo", "api")
    assert gone.returncode == 0 and hooks_path(kit.ws / "api") == "" and hooks_path(kit.ws / "web")


def test_guard_gate_is_red_on_a_forbidden_file_and_never_green_when_a_check_did_not_run(kit):
    api = kit.ws / "api"
    git(api, "switch", "-q", "-c", "topic")
    (api / "README.txt").write_text("x", encoding="utf-8")
    git(api, "add", "-A")
    git(api, "commit", "-q", "--no-verify", "-m", "feat: x")
    unscanned = cli(kit, "gate", "--repo", "api", "--base", "main")
    assert unscanned.returncode == 3 and any(w in unscanned.stdout for w in ("not green", "no está en verde"))
    (api / ".env").write_text("TOKEN=1", encoding="utf-8")
    git(api, "add", "-A")
    git(api, "commit", "-q", "--no-verify", "-m", "feat: env")
    red = cli(kit, "gate", "--repo", "api", "--base", "main", "--json")
    report = json.loads(red.stdout)
    assert red.returncode == 1 and report["verdict"] == "fail"
    assert [c["detail"] for c in report["repos"][0]["checks"] if c["id"] == "paths"] == [[".env"]]


def test_guard_usage_errors_are_exit_2(kit):
    assert cli(kit, "status", "--base", "main").returncode == 2
    assert cli(kit, "gate", "--repo", "nope").returncode == 2


def test_sharing_cam_docs_is_not_stopped_by_the_docs_check_on_push(kit, tmp_path):
    from test_team_repo import bare, publish
    remote = bare(tmp_path)
    kit.services.guard.install_hooks()
    publish(kit, remote)
    kit.services.guard.install_repo(kit.root, docs=True)
    (kit.services.guard.HOOKS_DIR / "kit-cmd").write_text("false\n", encoding="utf-8")        # a docs check that always fails
    (kit.root / "docs" / "mine.md").write_text("# Mine\n", encoding="utf-8")
    assert kit.services.share.push(log=QUIET)["status"] == "pushed"                            # the kit's own upload goes through
    (kit.root / "docs" / "again.md").write_text("# Again\n", encoding="utf-8")
    git(kit.root, "add", "-A")
    git(kit.root, "commit", "-q", "-m", "docs: again")
    assert git(kit.root, "push", "-q", "origin", "main", check=False).returncode != 0         # a person's push is checked
