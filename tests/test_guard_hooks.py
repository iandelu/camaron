"""The guardrails' git hooks (P3): `core.hooksPath` points at the kit's folder, a repo that already has hooks keeps them
(decision D5, the chain), nothing is written into a tracked file, and the docs repo's push runs the docs check."""
from __future__ import annotations

from pathlib import Path

import pytest
from test_githooks import GENERATED, HUMAN, TRAILER, commit, fake_gitleaks, git, message, on_path

from conftest import REPO

GENERIC = REPO / ".camarones" / "lib" / "githooks"


def hook(path: Path, body: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(f"#!/bin/sh\n{body}\n")
    path.chmod(0o755)
    return path


@pytest.fixture
def guard(kit):
    return kit.services.guard


@pytest.fixture
def repo(kit, tmp_path):
    r = tmp_path / "service"
    r.mkdir()
    git(r, "init", "-q", "-b", "main")
    return r


def installed(guard, repo: Path, docs: bool = False) -> Path:
    guard.install_hooks()
    guard.install_repo(repo, docs=docs)
    return repo


def remote_of(repo: Path, tmp_path: Path) -> Path:
    remote = tmp_path / "remote.git"
    git(tmp_path, "init", "-q", "--bare", "-b", "main", str(remote))
    git(repo, "remote", "add", "origin", str(remote))
    return remote


def config(repo: Path, key: str) -> str:
    return git(repo, "config", "--local", "--get", key, check=False).stdout.strip()


# ---- the kit's checks, through the dispatcher ----

def test_install_writes_only_local_config(guard, repo):
    installed(guard, repo)
    assert config(repo, "core.hooksPath") == guard.HOOKS_DIR.as_posix()
    assert git(repo, "status", "--porcelain").stdout == ""                       # nothing tracked, nothing untracked
    assert not (repo / ".githooks").exists() and not (repo / ".husky").exists()


def test_commit_drops_the_ai_credit_and_keeps_people(guard, repo):
    installed(guard, repo)
    assert commit(repo, f"feat: x\n\n{GENERATED}\n\n{TRAILER}\n{HUMAN}\n").returncode == 0
    assert message(repo) == f"feat: x\n\n{HUMAN}"


def test_push_refuses_a_commit_that_still_credits_ai(guard, repo, tmp_path):
    installed(guard, repo)
    remote_of(repo, tmp_path)
    commit(repo, f"feat: sneaky\n\n{TRAILER}", "--no-verify")
    sha = git(repo, "rev-parse", "--short", "HEAD").stdout.strip()
    result = git(repo, "push", "-q", "origin", "main", check=False)
    assert result.returncode != 0 and sha in result.stderr


def test_a_secret_stops_the_commit_and_no_scanner_only_warns(guard, repo, tmp_path, monkeypatch):
    installed(guard, repo)
    warned = commit(repo, "feat: unscanned")
    assert warned.returncode == 0 and "gitleaks not found" in warned.stderr
    on_path(monkeypatch, fake_gitleaks(tmp_path / "bin", 99))
    refused = commit(repo, "feat: leaks")
    assert refused.returncode != 0 and "possible secret" in refused.stderr


def test_the_install_is_idempotent_and_heals(guard, repo):
    assert guard.install_hooks() and guard.install_repo(repo)
    assert not guard.install_hooks() and not guard.install_repo(repo)
    assert guard.hooks_off(repo) is None
    (guard.HOOKS_DIR / "pre-push").unlink()
    assert guard.hooks_off(repo) and guard.install_hooks() and guard.hooks_off(repo) is None


def test_every_hook_name_git_knows_has_a_dispatcher(guard):
    guard.install_hooks()
    for name in ("pre-commit", "commit-msg", "pre-push", "post-checkout", "post-merge", "post-commit", "prepare-commit-msg"):
        assert (guard.HOOKS_DIR / name).read_bytes() == (GENERIC / "dispatch").read_bytes().replace(b"\r\n", b"\n")


# ---- a repo that already has hooks keeps them (D5) ----

def test_a_repos_own_git_hooks_still_run_after_the_kit_checks(guard, repo):
    own = repo / ".git" / "hooks"
    hook(own / "pre-commit", 'echo ran > "$(git rev-parse --show-toplevel)/pre-commit-ran"\n[ -f block ] || exit 0\n'
                             'echo "own hook says no" >&2\nexit 1')
    hook(own / "commit-msg", 'cp "$1" "$(git rev-parse --show-toplevel)/seen-message"')
    installed(guard, repo)
    assert commit(repo, f"feat: own\n\n{TRAILER}").returncode == 0
    assert (repo / "pre-commit-ran").is_file()
    assert "Claude" not in (repo / "seen-message").read_text(encoding="utf-8")        # theirs sees the kit's cleaned message
    (repo / "block").write_text("x", encoding="utf-8")
    refused = commit(repo, "feat: blocked by the repo's own hook")
    assert refused.returncode != 0 and "own hook says no" in refused.stderr


def test_a_husky_repo_keeps_its_hooks_and_gets_its_path_back(guard, repo):
    hook(repo / ".husky" / "_" / "pre-commit", 'echo husky > "$(git rev-parse --show-toplevel)/husky-ran"')
    git(repo, "config", "core.hooksPath", ".husky/_")
    installed(guard, repo)
    assert config(repo, "camaron.chain") == ".husky/_" and config(repo, "core.hooksPath") == guard.HOOKS_DIR.as_posix()
    assert commit(repo, f"feat: husky\n\n{TRAILER}").returncode == 0
    assert (repo / "husky-ran").is_file() and message(repo) == "feat: husky"
    assert guard.uninstall_repo(repo) and not guard.uninstall_repo(repo)
    assert config(repo, "core.hooksPath") == ".husky/_" and config(repo, "camaron.chain") == ""


def test_husky_setting_its_path_again_is_drift_and_install_chains_it_again(guard, repo):
    installed(guard, repo)
    git(repo, "config", "core.hooksPath", ".husky/_")                    # `npm install` runs husky's prepare script
    assert ".husky/_" in guard.hooks_off(repo)
    assert guard.install_repo(repo) and config(repo, "camaron.chain") == ".husky/_"
    assert guard.hooks_off(repo) is None


def test_the_pushed_refs_reach_both_the_kit_and_the_repos_pre_push(guard, repo, tmp_path):
    hook(repo / ".git" / "hooks" / "pre-push", 'cat > "$(git rev-parse --show-toplevel)/pushed-refs"')
    installed(guard, repo)
    remote_of(repo, tmp_path)
    commit(repo, "feat: start")
    assert git(repo, "push", "-q", "origin", "main", check=False).returncode == 0
    assert "refs/heads/main" in (repo / "pushed-refs").read_text(encoding="utf-8")
    (repo / "pushed-refs").unlink()
    commit(repo, f"feat: sneaky\n\n{TRAILER}", "--no-verify")
    assert git(repo, "push", "-q", "origin", "main", check=False).returncode != 0
    assert not (repo / "pushed-refs").exists()                           # the kit refused first: theirs never ran


def test_a_hook_the_repo_has_and_the_kit_has_no_check_for_still_runs(guard, repo):
    hook(repo / ".git" / "hooks" / "post-commit", 'echo done > "$(git rev-parse --show-toplevel)/post-commit-ran"')
    installed(guard, repo)
    assert commit(repo, "feat: x").returncode == 0 and (repo / "post-commit-ran").is_file()


def test_uninstall_leaves_a_repo_with_no_hooks_as_it_was(guard, repo):
    before = git(repo, "config", "--local", "--list").stdout
    installed(guard, repo, docs=True)
    assert guard.uninstall_repo(repo)
    assert git(repo, "config", "--local", "--list").stdout == before


# ---- cam-docs: the docs check on push ----

def fake_kit(guard, tmp_path: Path, code: int) -> None:
    fake = hook(tmp_path / "fake-camaron", f'echo "ERROR page.md: broken link ($1)"\nexit {code}')
    (guard.HOOKS_DIR / "kit-cmd").write_text(f'"{fake.as_posix()}"\n', encoding="utf-8")


def pushable(guard, repo: Path, tmp_path: Path, docs: bool) -> None:
    installed(guard, repo, docs=docs)
    remote_of(repo, tmp_path)
    commit(repo, "docs: start")


def test_a_docs_push_stops_on_a_check_error_and_goes_when_it_passes(guard, repo, tmp_path):
    pushable(guard, repo, tmp_path, docs=True)
    fake_kit(guard, tmp_path, 1)
    refused = git(repo, "push", "-q", "origin", "main", check=False)
    assert refused.returncode != 0 and "broken link (check)" in refused.stderr and "--no-verify" in refused.stderr
    fake_kit(guard, tmp_path, 0)
    assert git(repo, "push", "-q", "origin", "main", check=False).returncode == 0


def test_a_service_repos_push_never_runs_the_docs_check(guard, repo, tmp_path):
    pushable(guard, repo, tmp_path, docs=False)
    fake_kit(guard, tmp_path, 1)
    assert git(repo, "push", "-q", "origin", "main", check=False).returncode == 0


def test_a_docs_worktrees_push_says_the_check_did_not_run(guard, repo, tmp_path):
    pushable(guard, repo, tmp_path, docs=True)
    fake_kit(guard, tmp_path, 1)
    wt = tmp_path / "cw"
    git(repo, "worktree", "add", "-q", "-b", "side", str(wt))
    commit(wt, "docs: side")
    pushed = git(wt, "push", "-q", "origin", "side", check=False)
    assert pushed.returncode == 0 and "docs check not run in a worktree" in pushed.stderr


def test_a_docs_push_without_the_kit_says_so_and_goes(guard, repo, tmp_path):
    pushable(guard, repo, tmp_path, docs=True)
    (guard.HOOKS_DIR / "kit-cmd").unlink()
    pushed = git(repo, "push", "-q", "origin", "main", check=False)
    assert pushed.returncode == 0 and "docs check not run" in pushed.stderr


# ---- this repo's own hooks are the generic ones ----

PATTERN = ("pattern='^[[:space:]]*co-authored-by:([[:space:]]*claude([^[:alpha:]]|$)|.*@anthropic\\.com)"
           "|^[^[:alnum:]]*generated with \\[?claude code'")


@pytest.mark.parametrize("name", ["commit-msg", "pre-commit", "pre-push"])
def test_the_kit_repos_own_hooks_are_the_generic_ones(name):
    own, generic = (REPO / ".githooks" / name).read_bytes(), (GENERIC / "kit" / name).read_bytes()
    assert own.replace(b"\r\n", b"\n") == generic.replace(b"\r\n", b"\n")


@pytest.mark.parametrize("name", ["commit-msg", "pre-push"])
def test_the_credit_pattern_is_the_same_in_every_hook(name):
    assert PATTERN in (GENERIC / "kit" / name).read_text(encoding="utf-8")


def test_the_kits_own_push_says_so_and_skips_the_docs_check(guard, repo, tmp_path, monkeypatch):
    pushable(guard, repo, tmp_path, docs=True)
    fake_kit(guard, tmp_path, 1)
    monkeypatch.setenv("CAMARONES_SHARE", "1")
    assert git(repo, "push", "-q", "origin", "main", check=False).returncode == 0
    commit(repo, f"docs: sneaky\n\n{TRAILER}", "--no-verify")
    assert git(repo, "push", "-q", "origin", "main", check=False).returncode != 0         # the AI credit is refused all the same
