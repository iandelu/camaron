"""share.push and share.share: upload cam-docs work, never beside a catch-up or over a rebase left half way."""
from __future__ import annotations

import contextlib, subprocess, threading

import pytest

from test_team_repo import bare, git, publish
from test_share_pull import mate_commits

UPLOADS = ["push", "share"]


@contextlib.contextmanager
def catch_up_running(kit):
    from lib.core.locks import FileLock
    held, done = threading.Event(), threading.Event()

    def hold():                                   # FileLock is re-entrant per thread: hold it from another one
        with FileLock(kit.services.catchup.LOCK, wait=0):
            held.set(); done.wait(30)
    t = threading.Thread(target=hold); t.start(); held.wait(30)
    try:
        yield
    finally:
        done.set(); t.join()


@pytest.mark.parametrize("action", UPLOADS)
def test_an_upload_beside_a_catch_up_is_busy_and_touches_nothing(kit, tmp_path, action):
    remote = bare(tmp_path); publish(kit, remote)
    (kit.root / "docs" / "mine.md").write_text("# Mine\n", encoding="utf-8")
    head, theirs = git(kit.root, "rev-parse", "HEAD"), git(remote, "rev-parse", "main")
    with catch_up_running(kit):
        r = getattr(kit.services.share, action)(log=lambda _: None)
    assert (r["status"], r["detail"]) == ("busy", "catch-up")
    assert git(kit.root, "rev-parse", "HEAD") == head and git(remote, "rev-parse", "main") == theirs


@pytest.mark.parametrize("action", UPLOADS)
def test_an_upload_leaves_a_rebase_left_half_way_alone(kit, tmp_path, action):
    remote = bare(tmp_path)
    page = kit.root / "docs" / "page.md"
    page.parent.mkdir(parents=True, exist_ok=True); page.write_text("base\n", encoding="utf-8")
    publish(kit, remote)
    mate_commits(kit, remote, tmp_path, "docs/page.md", "theirs\n")
    page.write_text("mine\n", encoding="utf-8"); git(kit.root, "commit", "-qam", "mine")
    git(kit.root, "fetch", "-q", "origin")
    assert subprocess.run(["git", "rebase", "origin/main"], cwd=kit.root, capture_output=True).returncode
    head = git(kit.root, "rev-parse", "HEAD")
    r = getattr(kit.services.share, action)(log=lambda _: None)
    assert (r["status"], r["detail"]) == ("busy", "git")
    assert git(kit.root, "rev-parse", "HEAD") == head
    assert git(kit.root, "diff", "--name-only", "--diff-filter=U") == "docs/page.md"      # still the person's to resolve


FETCHES = {"push": lambda s: s.push(log=lambda _: None), "share": lambda s: s.share(log=lambda _: None),
           "check for news": lambda s: s.sync_status(fetch=True)}


@pytest.mark.parametrize("step", FETCHES)
def test_every_fetch_is_bounded_and_ssh_never_asks(kit, tmp_path, monkeypatch, step):
    from test_share_pull import _spy_fetch
    publish(kit, bare(tmp_path))
    for name in ("GIT_SSH_COMMAND", "GIT_SSH"):
        monkeypatch.delenv(name, raising=False)
    seen = _spy_fetch(kit, monkeypatch)
    FETCHES[step](kit.services.share)
    assert seen and seen[-1]["timeout"] == kit.services.share.FETCH_TIMEOUT
    assert "BatchMode=yes" in seen[-1]["env"]["GIT_SSH_COMMAND"]


@pytest.mark.parametrize("step", FETCHES)
def test_a_fetch_that_hangs_is_a_network_error_everywhere(kit, tmp_path, monkeypatch, step):
    import sys
    from test_share_pull import _spy_fetch
    publish(kit, bare(tmp_path))
    monkeypatch.setattr(kit.services.share, "FETCH_TIMEOUT", 0.5, raising=False)
    _spy_fetch(kit, monkeypatch, instead=[sys.executable, "-c", "import time; time.sleep(5)"])
    r = FETCHES[step](kit.services.share)
    r = r["fetched"] if step == "check for news" else r
    assert r["reason"] == "network" and "timed out" in r["detail"]


def test_push_without_a_remote_says_so(kit):
    kit.services.templates.init_templates("demo", log=lambda _: None)
    assert kit.services.share.push(log=lambda _: None) == {"status": "no-remote", "detail": ""}


def test_push_on_a_detached_head_says_so_and_uploads_nothing(kit, tmp_path):
    remote = bare(tmp_path); publish(kit, remote)
    (kit.root / "docs" / "mine.md").write_text("# Mine\n", encoding="utf-8")
    kit.services.share.checkpoint_commit("mine")
    git(kit.root, "checkout", "-q", "--detach")
    theirs = git(remote, "rev-parse", "main")
    r = kit.services.share.push(log=lambda _: None)
    assert r["status"] == "error" and r["detail"].startswith("detached HEAD")
    assert git(remote, "rev-parse", "main") == theirs


def test_the_first_push_publishes_the_branch_and_tracks_it(kit, tmp_path):
    from test_team_repo import remote_files
    remote = bare(tmp_path)
    kit.services.templates.init_templates("demo", log=lambda _: None)
    kit.plan.sync()
    kit.services.share.set_remote(str(remote))
    assert kit.services.share.push(log=lambda _: None) == {"status": "pushed", "detail": "main"}
    assert ".camarones/workspace.yaml" in remote_files(remote)
    assert git(kit.root, "rev-parse", "--abbrev-ref", "@{u}") == "origin/main"
