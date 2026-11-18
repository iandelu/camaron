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
