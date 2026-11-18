"""This repo credits people only: .githooks/commit-msg drops AI co-author trailers, pre-push refuses any that slipped
in, and scripts/githooks.py installs them where every worktree finds them. .githooks/pre-commit keeps secrets out of a
commit: it runs gitleaks on what is staged, and lets the commit go with a warning when there is no gitleaks to run."""
from __future__ import annotations

import glob, importlib.util, os, shutil, subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
HOOKS = REPO / ".githooks"
TRAILER = "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
GENERATED = "🤖 Generated with [Claude Code](https://claude.com/claude-code)"
HUMAN = "Co-Authored-By: Ana Pérez <ana@example.com>"
# Shaped like a GitHub token and a Google API key, belonging to nobody; built in two pieces so this very file passes the hook.
TOKEN = "ghp_" + "aB3dE5gH7jK9mN1pQ3sT5vW7yZ9bD1fH3jL5"
GCP_KEY = "AIza" + "SyA1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q"
# The machine's own gitleaks, found before isolated_env takes it off PATH: the pinned copy of the kit, else PATH's.
REAL_GITLEAKS = shutil.which("gitleaks") or next(iter(sorted(glob.glob(os.path.expanduser("~/.camarones/bin/gitleaks-*/gitleaks")))), "")


def git(cwd: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=cwd, check=check, capture_output=True, text=True, encoding="utf-8")


def commit(repo: Path, msg: str, *extra: str) -> subprocess.CompletedProcess:
    note = repo.parent / "msg.txt"
    note.write_text(msg, encoding="utf-8")
    target = repo / "f.txt"
    target.write_text(target.read_text(encoding="utf-8") + "x" if target.exists() else "x", encoding="utf-8")
    git(repo, "add", "f.txt")
    return git(repo, "commit", "-q", "-F", str(note), *extra, check=False)


def message(repo: Path, rev: str = "HEAD") -> str:
    return git(repo, "log", "-1", "--format=%B", rev).stdout.strip()


@pytest.fixture
def repo(isolated_env, tmp_path):
    r = tmp_path / "repo"
    r.mkdir()
    git(r, "init", "-q", "-b", "main")
    git(r, "config", "core.hooksPath", str(HOOKS))
    return r


@pytest.fixture
def pushed(repo, tmp_path):
    remote = tmp_path / "remote.git"
    git(tmp_path, "init", "-q", "--bare", "-b", "main", str(remote))
    git(repo, "remote", "add", "origin", str(remote))
    commit(repo, "feat: start")
    git(repo, "push", "-q", "-u", "origin", "main")
    return repo, remote


def test_commit_drops_claude_trailer_and_generated_line(repo):
    assert commit(repo, f"feat: x\n\nbody\n\n{GENERATED}\n\n{TRAILER}\n{HUMAN}\n").returncode == 0
    assert message(repo) == f"feat: x\n\nbody\n\n{HUMAN}"


def test_commit_keeps_people_and_mentions_of_claude(repo):
    msg = "feat(runners): the claude runner reads its model\n\nCo-Authored-By: Claudia Ruiz <claudia@example.com>"
    assert commit(repo, msg).returncode == 0
    assert message(repo) == msg


def test_merge_commit_drops_claude_trailer(repo):
    commit(repo, "feat: base")
    git(repo, "switch", "-q", "-c", "topic")
    commit(repo, "feat: topic")
    git(repo, "switch", "-q", "main")
    git(repo, "merge", "-q", "--no-ff", "topic", "-m", f"Merge topic into main\n\n{TRAILER}")
    assert message(repo) == "Merge topic into main"


@pytest.mark.parametrize("credit", [TRAILER, GENERATED], ids=["trailer", "generated"])
def test_push_refuses_a_commit_that_still_credits_claude(pushed, credit):
    repo, remote = pushed
    commit(repo, f"feat: sneaky\n\n{credit}", "--no-verify")
    sha = git(repo, "rev-parse", "--short", "HEAD").stdout.strip()
    result = git(repo, "push", "-q", "origin", "main", check=False)
    assert result.returncode != 0
    assert sha in result.stderr
    assert git(remote, "rev-parse", "main").stdout != git(repo, "rev-parse", "HEAD").stdout


def test_push_checks_only_commits_the_remote_lacks(pushed):
    repo, _ = pushed
    commit(repo, f"feat: old\n\n{TRAILER}", "--no-verify")
    git(repo, "push", "-q", "--no-verify", "origin", "main")
    commit(repo, "feat: clean")
    assert git(repo, "push", "-q", "origin", "main", check=False).returncode == 0
    git(repo, "switch", "-q", "-c", "topic")
    commit(repo, "feat: topic")
    assert git(repo, "push", "-q", "origin", "topic", check=False).returncode == 0


def test_installer_puts_hooks_where_every_worktree_runs_them(isolated_env, tmp_path):
    main = tmp_path / "main"
    main.mkdir()
    git(main, "init", "-q", "-b", "main")
    commit(main, "feat: start")
    wt = tmp_path / "wt"
    git(main, "worktree", "add", "-q", "-b", "side", str(wt))
    spec = importlib.util.spec_from_file_location("githooks", REPO / "scripts" / "githooks.py")
    githooks = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(githooks)

    installed = githooks.install(wt)

    shared = (main / ".git" / "hooks").resolve()
    assert sorted(p.name for p in installed) == ["commit-msg", "pre-commit", "pre-push"]
    assert all(p.resolve().parent == shared for p in installed)
    assert commit(wt, f"feat: side\n\n{TRAILER}").returncode == 0
    assert message(wt) == "feat: side"


# ---- pre-commit: no secret in a commit ----

LEAK, CLEAN, BROKEN = 99, 0, 2              # the hook asks gitleaks for 99 when it finds something; 2: it failed on its own


def fake_gitleaks(directory: Path, code: int) -> Path:
    """A `gitleaks` that prints one redacted finding and exits `code`, in `directory`; returns the folder."""
    directory.mkdir(parents=True, exist_ok=True)
    exe = directory / "gitleaks"
    with open(exe, "w", encoding="utf-8", newline="\n") as f:
        f.write(f'#!/bin/sh\necho "Finding: REDACTED  File: f.txt  RuleID: fake-rule" >&2\nexit {code}\n')
    exe.chmod(0o755)
    return directory


def on_path(monkeypatch, directory: Path) -> None:
    monkeypatch.setenv("PATH", f"{directory}{os.pathsep}{os.environ['PATH']}")


def has_commits(repo: Path) -> bool:
    return git(repo, "rev-parse", "--verify", "-q", "HEAD", check=False).returncode == 0


def test_commit_is_refused_when_gitleaks_finds_a_secret(repo, tmp_path, monkeypatch):
    on_path(monkeypatch, fake_gitleaks(tmp_path / "bin", LEAK))
    result = commit(repo, "feat: leaks")
    assert result.returncode != 0
    assert "fake-rule" in result.stderr                                # what gitleaks said reaches the person
    assert "--no-verify" in result.stderr                              # and how to go past a false positive
    assert not has_commits(repo)


def test_no_verify_goes_past_a_false_positive(repo, tmp_path, monkeypatch):
    on_path(monkeypatch, fake_gitleaks(tmp_path / "bin", LEAK))
    assert commit(repo, "feat: it is a placeholder", "--no-verify").returncode == 0


def test_commit_goes_through_when_gitleaks_finds_nothing(repo, tmp_path, monkeypatch):
    on_path(monkeypatch, fake_gitleaks(tmp_path / "bin", CLEAN))
    assert commit(repo, "feat: clean").returncode == 0
    assert has_commits(repo)


def test_commit_goes_through_with_a_warning_when_there_is_no_gitleaks(repo):
    assert shutil.which("gitleaks") is None
    result = commit(repo, "feat: unscanned")
    assert result.returncode == 0
    assert "gitleaks not found" in result.stderr


def test_commit_goes_through_with_a_warning_when_gitleaks_itself_fails(repo, tmp_path, monkeypatch):
    on_path(monkeypatch, fake_gitleaks(tmp_path / "bin", BROKEN))
    result = commit(repo, "feat: scanner broke")
    assert result.returncode == 0
    assert "could not scan" in result.stderr


def test_the_kits_pinned_gitleaks_wins_over_the_one_on_path(repo, isolated_env, tmp_path, monkeypatch):
    on_path(monkeypatch, fake_gitleaks(tmp_path / "bin", CLEAN))
    fake_gitleaks(isolated_env / ".camarones" / "bin" / "gitleaks-8.30.1", LEAK)
    assert commit(repo, "feat: pinned says no").returncode != 0


@pytest.mark.skipif(not REAL_GITLEAKS, reason="gitleaks not installed")
def test_the_real_gitleaks_stops_a_token_and_never_prints_it(repo, monkeypatch):
    on_path(monkeypatch, Path(REAL_GITLEAKS).parent)
    note = repo.parent / "msg.txt"
    note.write_text("feat: token", encoding="utf-8")
    (repo / "notes.md").write_text(f"# notes\n\ntoken: {TOKEN}\n", encoding="utf-8")
    git(repo, "add", "notes.md")
    leak = git(repo, "commit", "-q", "-F", str(note), check=False)
    assert leak.returncode != 0
    assert "notes.md" in leak.stderr and "github" in leak.stderr.lower()
    assert TOKEN not in leak.stdout + leak.stderr
    assert not has_commits(repo)
    git(repo, "rm", "-q", "--cached", "notes.md")
    assert commit(repo, "feat: clean").returncode == 0


@pytest.mark.skipif(not REAL_GITLEAKS, reason="gitleaks not installed")
def test_the_repos_config_lets_generated_bundles_through_and_nothing_else(repo, monkeypatch):
    on_path(monkeypatch, Path(REAL_GITLEAKS).parent)
    shutil.copy(REPO / ".gitleaks.toml", repo / ".gitleaks.toml")
    note = repo.parent / "msg.txt"
    note.write_text("feat: bundle", encoding="utf-8")
    bundle = repo / ".camarones" / "portal" / "app-build" / "assets" / "BoardCanvas-x.js"
    bundle.parent.mkdir(parents=True)
    bundle.write_text(f'const k="{GCP_KEY}";\n', encoding="utf-8")
    git(repo, "add", ".gitleaks.toml", str(bundle.relative_to(repo)))
    assert git(repo, "commit", "-q", "-F", str(note), check=False).returncode == 0
    (repo / "src.js").write_text(f'const k="{GCP_KEY}";\n', encoding="utf-8")        # the same key anywhere else is a finding
    git(repo, "add", "src.js")
    assert git(repo, "commit", "-q", "-F", str(note), check=False).returncode != 0
