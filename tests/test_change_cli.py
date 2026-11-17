"""`camaron change`: the CLI over lib/app/change (WI-21). Run as subprocesses, like the other command tests. Exit 0
done, 1 blocked (the reason on stderr), 2 a usage error; --json output carries no prose."""
from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest


def cli(kit, *args, cwd=None):
    e = {**os.environ, "CAMARONES_ROOT": str(kit.root)}
    return subprocess.run([sys.executable, str(kit.kit_dir / "camarones.py"), "change", *args], env=e,
                          capture_output=True, text=True, encoding="utf-8", cwd=cwd)


def git(path, *args):
    return subprocess.run(["git", *args], cwd=path, capture_output=True, text=True, encoding="utf-8",
                          check=True).stdout.strip()


@pytest.fixture
def proj(wired):
    from lib.kanban import ops
    ops.init(log=lambda _: None)
    ops.add("story", "Retry failed payments", repos=["api"])
    git(wired.root, "add", "-A")
    git(wired.root, "commit", "-qm", "board")
    return wired


def test_a_change_from_start_to_close_in_json(proj):
    r = cli(proj, "start", "Retry", "failed", "payments", "--item", "WI-1", "--json")
    assert r.returncode == 0, r.stderr
    started = json.loads(r.stdout)
    assert started["change"]["id"] == "wi-1" and started["again"] is False and "to_read" in started
    assert json.loads(cli(proj, "phase", "wi-1", "assess", "--json").stdout)["phase"] == "assess"
    rows = json.loads(cli(proj, "status", "--json").stdout)["changes"]
    assert [(c["id"], c["phase"], c["state"]) for c in rows] == [("wi-1", "assess", "open")]
    linked = json.loads(cli(proj, "link", "https://github.com/acme/api/pull/7", "--json").stdout)
    assert linked["prs"] == {"api": "https://github.com/acme/api/pull/7"} and linked["state"] == "in-review"
    closed = json.loads(cli(proj, "close", "wi-1", "--abandon", "--json").stdout)
    assert closed["state"] == "closed" and closed["closed"]["how"] == "abandoned"
    assert "🦐" not in r.stdout


def test_start_says_what_to_read_and_the_next_step(proj):
    r = cli(proj, "start", "Retry failed payments", "--item", "WI-1")
    assert r.returncode == 0, r.stderr
    assert "api: cam/wi-1-retry-failed-payments (from main)" in r.stdout                # the skills read <base> here
    assert "(cam/wi-1-retry-failed-payments, from main)" in r.stdout                     # and the docs' <base>
    assert "camaron change phase wi-1 assess" in r.stdout
    status = cli(proj, "status").stdout
    assert "wi-1" in status and "docs" in status and "api: cam/wi-1-retry-failed-payments (from main)" in status
    assert json.loads(cli(proj, "status", "wi-1", "--json").stdout)["changes"][0]["bases"] == {"api": "main",
                                                                                           "docs": "main"}


def test_the_change_is_found_from_the_folder(proj):
    cli(proj, "start", "Retry failed payments", "--item", "WI-1")
    r = cli(proj, "phase", "plan", cwd=proj.ws / "api")
    assert r.returncode == 0, r.stderr
    assert "plan" in r.stdout


def test_blocked_exits_1_with_the_reason(proj):
    (proj.ws / "api" / "wip.txt").write_text("wip", encoding="utf-8")
    r = cli(proj, "start", "Retry failed payments", "--item", "WI-1")
    assert r.returncode == 1 and r.stderr.startswith("✖") and "api has uncommitted changes" in r.stderr
    (proj.ws / "api" / "wip.txt").unlink()
    cli(proj, "start", "Retry failed payments", "--item", "WI-1")
    cli(proj, "phase", "wi-1", "verify")
    r = cli(proj, "phase", "wi-1", "code")
    assert r.returncode == 1 and "never goes back" in r.stderr and "🦐" not in r.stderr


@pytest.mark.parametrize("args", [
    ("phase", "wi-1", "deploy"),               # not a phase
    ("close",),                                # close names its change
    ("start",),                                # a title is needed
    ("status", "--abandon"),                   # a flag of another action
    ("link", "wi-1", "https://x/pull/1", "--repo", "api", "--repo", "web"),
])
def test_usage_errors_exit_2(proj, args):
    cli(proj, "start", "Retry failed payments", "--item", "WI-1")
    r = cli(proj, *args)
    assert r.returncode == 2 and r.stderr.startswith("✖"), (r.stdout, r.stderr)


def test_without_an_open_change(proj):
    r = cli(proj, "status")
    assert r.returncode == 0 and "change start" in r.stdout
    assert json.loads(cli(proj, "status", "--json").stdout) == {"changes": []}
    r = cli(proj, "phase", "assess")
    assert r.returncode == 2 and "no open change" in r.stderr
