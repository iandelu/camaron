"""share.pull: bring in the team's cam-docs work, never push, never lose local work."""
from __future__ import annotations

from test_team_repo import bare, git, publish


def mate_commits(kit, remote, tmp_path, path="docs/theirs.md", text="# Theirs\n"):
    mate, _ = kit.projects.join(str(remote), tmp_path / "mate")
    f = mate / path
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(text, encoding="utf-8")
    git(mate, "add", "-A"); git(mate, "commit", "-q", "-m", "theirs"); git(mate, "push", "-q", "origin", "main")
    return mate


def test_up_to_date(kit, tmp_path):
    publish(kit, bare(tmp_path))
    assert kit.services.share.pull(log=lambda _: None)["status"] == "up-to-date"


def test_brings_in_the_teams_commits_and_never_pushes(kit, tmp_path):
    remote = bare(tmp_path); publish(kit, remote)
    (kit.root / "docs" / "mine.md").write_text("# Mine\n", encoding="utf-8"); kit.services.share.checkpoint_commit("mine")
    mate_commits(kit, remote, tmp_path)
    before = git(remote, "rev-parse", "main")
    r = kit.services.share.pull(log=lambda _: None)
    assert r["status"] == "pulled" and r["commits"] == 1
    assert (kit.root / "docs" / "theirs.md").exists() and (kit.root / "docs" / "mine.md").exists()
    assert git(remote, "rev-parse", "main") == before                       # nothing pushed
    assert git(kit.root, "rev-list", "--count", "origin/main..HEAD") == "1"   # mine rebased on top


def test_uncommitted_work_stays_where_it_was(kit, tmp_path):
    remote = bare(tmp_path); publish(kit, remote); mate_commits(kit, remote, tmp_path)
    (kit.root / "docs" / "draft.md").write_text("# Draft\n", encoding="utf-8")
    assert kit.services.share.pull(log=lambda _: None)["status"] == "pulled"
    assert (kit.root / "docs" / "draft.md").read_text(encoding="utf-8") == "# Draft\n"
    assert git(kit.root, "stash", "list") == ""


def test_uncommitted_change_to_a_file_the_team_changed_is_a_conflict_and_changes_nothing(kit, tmp_path):
    remote = bare(tmp_path); publish(kit, remote)
    mate_commits(kit, remote, tmp_path, "docs/shared.md", "# Team\n")
    (kit.root / "docs" / "shared.md").write_text("# Mine\n", encoding="utf-8")
    head = git(kit.root, "rev-parse", "HEAD")
    r = kit.services.share.pull(log=lambda _: None)
    assert r["status"] == "conflict" and r["files"] == ["docs/shared.md"]
    assert git(kit.root, "rev-parse", "HEAD") == head
    assert (kit.root / "docs" / "shared.md").read_text(encoding="utf-8") == "# Mine\n"


def test_a_clash_between_commits_is_undone(kit, tmp_path):
    remote = bare(tmp_path); publish(kit, remote)
    mate_commits(kit, remote, tmp_path, "docs/shared.md", "# Team\n")
    (kit.root / "docs" / "shared.md").write_text("# Mine\n", encoding="utf-8"); kit.services.share.checkpoint_commit("mine")
    head = git(kit.root, "rev-parse", "HEAD")
    r = kit.services.share.pull(log=lambda _: None)
    assert r["status"] == "conflict" and "docs/shared.md" in r["files"]
    assert git(kit.root, "rev-parse", "HEAD") == head and not (kit.root / ".git" / "rebase-merge").exists()


def test_a_clash_only_in_derived_files_takes_the_teams_and_regenerates(kit, tmp_path):
    remote = bare(tmp_path); publish(kit, remote)
    mate_commits(kit, remote, tmp_path, "docs/llms.txt", "team\n")
    (kit.root / "docs" / "llms.txt").write_text("mine\n", encoding="utf-8"); kit.services.share.checkpoint_commit("mine")
    r = kit.services.share.pull(log=lambda _: None)
    assert r["status"] == "pulled" and "docs/llms.txt" in r["regenerated"]
    assert "<<<<<<<" not in (kit.root / "docs" / "llms.txt").read_text(encoding="utf-8")


def test_history_rewritten_by_the_team_is_a_conflict_and_changes_nothing(kit, tmp_path):
    remote = bare(tmp_path); publish(kit, remote)
    (kit.root / "docs" / "a.md").write_text("# A\n", encoding="utf-8"); kit.services.share.checkpoint_commit("a")
    git(kit.root, "push", "-q", "origin", "main")
    mate, _ = kit.projects.join(str(remote), tmp_path / "mate")
    git(mate, "reset", "-q", "--hard", "HEAD~1")
    (mate / "docs" / "a.md").write_text("# Rewritten\n", encoding="utf-8")
    git(mate, "add", "-A"); git(mate, "commit", "-q", "-m", "rewrite"); git(mate, "push", "-q", "-f", "origin", "main")
    (kit.root / "docs" / "a.md").write_text("# A2\n", encoding="utf-8"); kit.services.share.checkpoint_commit("a2")
    head = git(kit.root, "rev-parse", "HEAD")
    assert kit.services.share.pull(log=lambda _: None)["status"] == "conflict"
    assert git(kit.root, "rev-parse", "HEAD") == head


def test_a_rebase_left_half_way_is_left_alone(kit, tmp_path):
    publish(kit, bare(tmp_path))
    (kit.root / ".git" / "rebase-merge").mkdir()
    r = kit.services.share.pull(log=lambda _: None)
    assert (r["status"], r["detail"]) == ("busy", "git")


def test_no_remote_and_no_branch_on_the_remote(kit, tmp_path):
    kit.services.templates.init_templates("demo", log=lambda _: None)
    assert kit.services.share.pull(log=lambda _: None)["status"] == "no-remote"
    kit.services.share.set_remote(str(bare(tmp_path))); kit.services.share.checkpoint_commit("first")
    assert kit.services.share.pull(log=lambda _: None)["status"] == "nothing"


def test_an_unreachable_remote_says_why(kit, tmp_path):
    kit.services.templates.init_templates("demo", log=lambda _: None)
    kit.services.share.set_remote(str(tmp_path / "missing.git")); kit.services.share.checkpoint_commit("first")
    r = kit.services.share.pull(log=lambda _: None)
    assert r["status"] == "error" and r["reason"] == "not-found" and r["detail"].startswith("fatal: ")


def _stashes(kit):
    return git(kit.root, "stash", "list")


def test_a_non_ascii_page_edited_by_both_is_a_conflict_with_no_stash(kit, tmp_path):
    remote = bare(tmp_path); publish(kit, remote)
    (kit.root / "docs" / "visión.md").write_text("# Base\n", encoding="utf-8"); kit.services.share.checkpoint_commit("v")
    git(kit.root, "push", "-q", "origin", "main")
    mate_commits(kit, remote, tmp_path, "docs/visión.md", "# Team\n")
    (kit.root / "docs" / "visión.md").write_text("# Mine\n", encoding="utf-8")
    r = kit.services.share.pull(log=lambda _: None)
    assert r["status"] == "conflict" and r["files"] == ["docs/visión.md"]
    assert _stashes(kit) == ""
    assert (kit.root / "docs" / "visión.md").read_text(encoding="utf-8") == "# Mine\n"


def test_a_page_the_team_renamed_and_i_edited_is_a_conflict(kit, tmp_path):
    remote = bare(tmp_path); publish(kit, remote)
    (kit.root / "docs" / "plain.md").write_text("# Plain\nline\n" * 5, encoding="utf-8"); kit.services.share.checkpoint_commit("p")
    git(kit.root, "push", "-q", "origin", "main")
    mate, _ = kit.projects.join(str(remote), tmp_path / "mate")
    git(mate, "mv", "docs/plain.md", "docs/moved.md")
    with (mate / "docs" / "moved.md").open("a", encoding="utf-8") as f:
        f.write("more\n")
    git(mate, "add", "-A"); git(mate, "commit", "-q", "-m", "rename"); git(mate, "push", "-q", "origin", "main")
    with (kit.root / "docs" / "plain.md").open("a", encoding="utf-8") as f:
        f.write("mine\n")
    r = kit.services.share.pull(log=lambda _: None)
    assert r["status"] == "conflict" and "docs/plain.md" in r["files"]
    assert _stashes(kit) == ""
    assert "mine" in (kit.root / "docs" / "plain.md").read_text(encoding="utf-8")


def test_a_rebase_that_cannot_start_is_an_error_and_changes_nothing(kit, tmp_path):
    remote = bare(tmp_path); publish(kit, remote); mate_commits(kit, remote, tmp_path)
    head = git(kit.root, "rev-parse", "HEAD")
    lock = kit.root / ".git" / "index.lock"
    lock.write_text("", encoding="utf-8")
    try:
        r = kit.services.share.pull(log=lambda _: None)
    finally:
        lock.unlink(missing_ok=True)
    assert r["status"] == "error" and r["detail"]
    assert git(kit.root, "rev-parse", "HEAD") == head


def test_a_conflict_after_a_derived_reset_leaves_the_derived_file_regenerated(kit, tmp_path):
    remote = bare(tmp_path); publish(kit, remote)
    mate_commits(kit, remote, tmp_path, "docs/llms.txt", "team\n")
    mate_commits(kit, remote, tmp_path, "docs/shared.md", "# Team\n")
    (kit.root / "docs" / "shared.md").write_text("# Mine\n", encoding="utf-8"); kit.services.share.checkpoint_commit("mine")
    (kit.root / "docs" / "llms.txt").write_text("local edit\n", encoding="utf-8")
    r = kit.services.share.pull(log=lambda _: None)
    assert r["status"] == "conflict"
    text = (kit.root / "docs" / "llms.txt").read_text(encoding="utf-8")
    assert text and "<<<<<<<" not in text and text != "local edit\n"


def test_push_uploads_local_work(kit, tmp_path):
    remote = bare(tmp_path); publish(kit, remote)
    (kit.root / "docs" / "mine.md").write_text("# Mine\n", encoding="utf-8")
    assert kit.services.share.push(log=lambda _: None)["status"] == "pushed"
    assert "docs/mine.md" in git(remote, "ls-tree", "-r", "--name-only", "main").splitlines()
    assert kit.services.share.sync_status()["last_share"]


def test_push_with_nothing_new(kit, tmp_path):
    publish(kit, bare(tmp_path))
    assert kit.services.share.push(log=lambda _: None)["status"] == "nothing"


def test_push_refuses_when_the_team_moved_and_rebases_nothing(kit, tmp_path):
    remote = bare(tmp_path); publish(kit, remote); mate_commits(kit, remote, tmp_path)
    (kit.root / "docs" / "mine.md").write_text("# Mine\n", encoding="utf-8")
    head_remote = git(remote, "rev-parse", "main")
    assert kit.services.share.push(log=lambda _: None)["status"] == "behind"
    assert git(remote, "rev-parse", "main") == head_remote
    assert not (kit.root / "docs" / "theirs.md").exists()


def test_push_blocked_by_staged_secrets(kit, tmp_path, monkeypatch):
    publish(kit, bare(tmp_path))
    import lib.quality
    monkeypatch.setattr(lib.quality, "staged_secrets", lambda: ["docs/mine.md:1 generic-api-key"])
    (kit.root / "docs" / "mine.md").write_text("# Mine\n", encoding="utf-8")
    assert kit.services.share.push(log=lambda _: None)["status"] == "blocked"


def _tracked(kit, path, text="local\n"):
    """A derived file committed and pushed, so HEAD and the team both have it."""
    f = kit.root / path
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(text, encoding="utf-8")
    git(kit.root, "add", "-f", "--", path); git(kit.root, "commit", "-q", "-m", "derived")
    git(kit.root, "push", "-q", "origin", "main")


def _no_markers(kit, *paths):
    return all("<<<<<<<" not in (kit.root / p).read_text(encoding="utf-8") for p in paths if (kit.root / p).exists())


def test_an_uncommitted_tracked_derived_file_the_team_changed_is_reset_and_regenerated(kit, tmp_path):
    remote = bare(tmp_path); publish(kit, remote)
    _tracked(kit, "docs/llms.txt", "base\n")
    mate_commits(kit, remote, tmp_path, "docs/llms.txt", "team\n")
    (kit.root / "docs" / "llms.txt").write_text("local edit\n", encoding="utf-8")
    r = kit.services.share.pull(log=lambda _: None)
    assert r["status"] == "pulled" and "docs/llms.txt" in r["regenerated"]
    assert _stashes(kit) == "" and _no_markers(kit, "docs/llms.txt")
    assert (kit.root / "docs" / "llms.txt").read_text(encoding="utf-8") != "local edit\n"


def test_a_staged_derived_file_the_team_changed_is_reset_from_head_not_stashed(kit, tmp_path):
    remote = bare(tmp_path); publish(kit, remote)
    _tracked(kit, "docs/.status.json", "{}\n")
    mate_commits(kit, remote, tmp_path, "docs/.status.json", '{"team": 1}\n')
    (kit.root / "docs" / ".status.json").write_text('{"mine": 1}\n', encoding="utf-8")
    git(kit.root, "add", "-f", "--", "docs/.status.json")            # left staged by a checkpoint gitleaks blocked
    head = git(kit.root, "rev-parse", "HEAD")
    r = kit.services.share.pull(log=lambda _: None)
    assert r["status"] == "pulled" and "docs/.status.json" in r["regenerated"]
    assert git(kit.root, "rev-parse", "HEAD") != head
    assert _stashes(kit) == "" and _no_markers(kit, "docs/.status.json")
    assert "UU" not in git(kit.root, "status", "--porcelain")


def test_a_derived_file_staged_as_new_that_the_team_added_is_dropped_not_stashed(kit, tmp_path):
    remote = bare(tmp_path); publish(kit, remote)
    git(kit.root, "rm", "-q", "--cached", "--ignore-unmatch", "--", "docs/llms-full.txt")
    if git(kit.root, "status", "--porcelain"):
        git(kit.root, "commit", "-q", "-m", "untrack"); git(kit.root, "push", "-q", "origin", "main")
    mate_commits(kit, remote, tmp_path, "docs/llms-full.txt", "team\n")
    (kit.root / "docs" / "llms-full.txt").write_text("mine\n", encoding="utf-8")
    git(kit.root, "add", "-f", "--", "docs/llms-full.txt")
    r = kit.services.share.pull(log=lambda _: None)
    assert r["status"] == "pulled" and "docs/llms-full.txt" in r["regenerated"]
    assert _stashes(kit) == "" and _no_markers(kit, "docs/llms-full.txt")


def test_changes_the_autostash_could_not_put_back_are_stashed_not_a_conflict(kit, tmp_path, monkeypatch):
    remote = bare(tmp_path); publish(kit, remote)
    _tracked(kit, "docs/shared.md", "# Base\n")
    mate_commits(kit, remote, tmp_path, "docs/shared.md", "# Team\n")
    (kit.root / "docs" / "shared.md").write_text("# Mine\n", encoding="utf-8")
    monkeypatch.setattr(kit.services.share, "_dirty", lambda: {})     # the pre-check misses it: the rebase's autostash clashes
    r = kit.services.share.pull(log=lambda _: None)
    assert r["status"] == "stashed" and r["files"] == ["docs/shared.md"]
    assert "stash" in r["detail"]
    assert "autostash" in _stashes(kit)
    assert "# Mine" in git(kit.root, "stash", "show", "-p", "stash@{0}")


def test_changes_kept_in_the_stash_leave_no_markers_for_a_checkpoint_to_commit(kit, tmp_path, monkeypatch):
    remote = bare(tmp_path); publish(kit, remote)
    _tracked(kit, "docs/shared.md", "# Base\n")
    mate_commits(kit, remote, tmp_path, "docs/shared.md", "# Team\n")
    (kit.root / "docs" / "shared.md").write_text("# Mine\n", encoding="utf-8")
    (kit.root / "docs" / "own.md").write_text("# Own\n", encoding="utf-8")
    monkeypatch.setattr(kit.services.share, "_dirty", lambda: {})
    assert kit.services.share.pull(log=lambda _: None)["status"] == "stashed"
    assert (kit.root / "docs" / "shared.md").read_text(encoding="utf-8") == "# Team\n"
    assert not [ln for ln in git(kit.root, "status", "--porcelain").splitlines() if ln[:2] in ("UU", "AA", "DU", "UD")]
    assert (kit.root / "docs" / "own.md").read_text(encoding="utf-8") == "# Own\n"     # what did not clash stays put
    kit.services.share.checkpoint_commit("after")
    assert "<<<<<<<" not in git(kit.root, "show", "HEAD:docs/shared.md")


def _spy_fetch(kit, monkeypatch, instead=None):
    """Every `git fetch` pull runs, with its keyword arguments; `instead` runs in its place."""
    share = kit.services.share
    real, seen = share.run, []

    def spy(cmd, **kw):
        if cmd[:2] == ["git", "fetch"]:
            seen.append(kw)
            if instead:
                return real(instead, **kw)
        return real(cmd, **kw)
    monkeypatch.setattr(share, "run", spy)
    return seen


def test_a_fetch_that_hangs_gives_up_as_a_network_error(kit, tmp_path, monkeypatch):
    import sys
    publish(kit, bare(tmp_path))
    _spy_fetch(kit, monkeypatch, instead=[sys.executable, "-c", "import time; time.sleep(5)"])
    r = kit.services.share.pull(log=lambda _: None, timeout=0.5)
    assert r["status"] == "error" and r["reason"] == "network" and "timed out" in r["detail"]


def test_a_bounded_fetch_never_lets_ssh_ask_unless_ssh_was_set_up(kit, tmp_path, monkeypatch):
    publish(kit, bare(tmp_path))
    for name in ("GIT_SSH_COMMAND", "GIT_SSH"):
        monkeypatch.delenv(name, raising=False)
    seen = _spy_fetch(kit, monkeypatch)
    pull = lambda **kw: kit.services.share.pull(log=lambda _: None, **kw)      # noqa: E731
    pull(timeout=30)
    assert seen[-1]["timeout"] == 30 and "BatchMode=yes" in seen[-1]["env"]["GIT_SSH_COMMAND"]
    pull()
    assert seen[-1]["timeout"] is None and "GIT_SSH_COMMAND" not in seen[-1]["env"]
    monkeypatch.setenv("GIT_SSH_COMMAND", "ssh -i mine")
    pull(timeout=30)
    assert "GIT_SSH_COMMAND" not in seen[-1]["env"]
    monkeypatch.delenv("GIT_SSH_COMMAND")
    git(kit.root, "config", "core.sshCommand", "ssh -i mine")
    pull(timeout=30)
    assert "GIT_SSH_COMMAND" not in seen[-1]["env"]
