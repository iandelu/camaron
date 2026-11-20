"""The team's repos found by their remote, not their folder name (spec 2026-11-18 §6.3): a clone kept under another
name is linked as <workspace>/<name>, a folder holding something else is left alone, and the links are this
machine's, recorded in the git-ignored cache."""
from __future__ import annotations

import importlib
import os
from pathlib import Path

from test_team_repo import git

QUIET = dict(log=lambda _: None)


def rh():
    return importlib.import_module("lib.app.repos_here")


def team_repos(kit, tmp_path: Path) -> dict[str, str]:
    """Each fixture repo gets a bare remote as its origin, and workspace.yaml that url."""
    ws = kit.services.workspace.workspace()
    for r in ws["repos"]:
        remote = tmp_path / "remotes" / f"{r['name']}.git"
        git(tmp_path, "clone", "-q", "--bare", str(kit.ws / r["name"]), str(remote))
        git(kit.ws / r["name"], "remote", "add", "origin", str(remote))
        r["url"] = str(remote)
    kit.services.workspace.save_workspace(ws)
    return {r["name"]: r["url"] for r in ws["repos"]}


def row(res: dict, name: str) -> dict:
    return next(r for r in res["rows"] if r["name"] == name)


def same(a: Path, b: Path) -> bool:
    return os.path.realpath(a) == os.path.realpath(b)


def test_a_clone_under_its_own_name_is_here(kit, tmp_path):
    team_repos(kit, tmp_path)
    res = rh().find(**QUIET)
    assert res["here"] == ["api", "web", "worker"]
    assert res["linked"] == res["missing"] == res["taken"] == []


def test_a_repo_without_url_is_here_when_its_folder_is(kit):
    """Every project made before 4.94 that lists local repos with no url."""
    assert rh().find(**QUIET)["here"] == ["api", "web", "worker"]


def test_a_clone_under_another_name_is_linked(kit, tmp_path):
    team_repos(kit, tmp_path)
    (kit.ws / "api").rename(kit.ws / "api-svc")
    res = rh().find(**QUIET)
    assert res["linked"] == ["api"]
    assert same(kit.ws / "api", kit.ws / "api-svc") and (kit.ws / "api" / "pom.xml").is_file()
    assert Path(row(res, "api")["path"]) == (kit.ws / "api-svc").resolve()
    assert rh().load()["links"] == {"api": str((kit.ws / "api-svc").resolve())}


def test_a_clone_in_a_search_folder_is_linked(kit, tmp_path):
    team_repos(kit, tmp_path)
    elsewhere = tmp_path / "IdeaProjects"
    elsewhere.mkdir()
    (kit.ws / "web").rename(elsewhere / "frontend")
    assert rh().find(**QUIET)["missing"] == ["web"]
    rh().add_search(elsewhere)
    assert rh().find(**QUIET)["linked"] == ["web"]
    assert same(kit.ws / "web", elsewhere / "frontend")


def test_a_search_folder_must_be_a_folder(kit, tmp_path):
    try:
        rh().add_search(tmp_path / "nope")
    except ValueError as e:
        assert str(e) == "folder"
    else:
        raise AssertionError("a missing folder was accepted")
    assert rh().load()["search"] == []


def test_a_folder_with_another_repo_is_taken_and_left_alone(kit, tmp_path):
    team_repos(kit, tmp_path)
    git(kit.ws / "api", "remote", "set-url", "origin", "https://example.com/other.git")
    kit.common.rmtree(kit.ws / "worker")
    (kit.ws / "worker").mkdir()
    (kit.ws / "worker" / "notes.txt").write_text("mine\n", encoding="utf-8")
    res = rh().find(**QUIET)
    assert res["taken"] == ["api", "worker"]
    assert git(kit.ws / "api", "remote", "get-url", "origin") == "https://example.com/other.git"
    assert sorted(p.name for p in (kit.ws / "worker").iterdir()) == ["notes.txt"]


def test_a_repo_nowhere_is_missing(kit, tmp_path):
    team_repos(kit, tmp_path)
    kit.common.rmtree(kit.ws / "worker")
    res = rh().find(**QUIET)
    assert res["missing"] == ["worker"] and row(res, "worker")["path"] == ""
    assert not os.path.lexists(kit.ws / "worker")


def test_a_kit_link_whose_clone_moved_is_linked_again(kit, tmp_path):
    team_repos(kit, tmp_path)
    (kit.ws / "api").rename(kit.ws / "api-svc")
    rh().find(**QUIET)
    (kit.ws / "api-svc").rename(kit.ws / "api-new")
    res = rh().find(**QUIET)
    assert res["linked"] == ["api"] and same(kit.ws / "api", kit.ws / "api-new")
    assert rh().load()["links"] == {"api": str((kit.ws / "api-new").resolve())}


def test_a_kit_link_whose_clone_is_gone_is_dropped(kit, tmp_path):
    team_repos(kit, tmp_path)
    (kit.ws / "api").rename(kit.ws / "api-svc")
    rh().find(**QUIET)
    kit.common.rmtree(kit.ws / "api-svc")
    res = rh().find(**QUIET)
    assert res["missing"] == ["api"]
    assert not os.path.lexists(kit.ws / "api") and rh().load()["links"] == {}


def test_find_is_idempotent(kit, tmp_path):
    team_repos(kit, tmp_path)
    (kit.ws / "api").rename(kit.ws / "api-svc")
    assert rh().find(**QUIET) == rh().find(**QUIET)


def test_a_link_that_cannot_be_made_stays_missing_with_its_path(kit, tmp_path, monkeypatch):
    """Windows without symlink rights or junctions: the clone is not linked, and its path says where it is."""
    team_repos(kit, tmp_path)
    (kit.ws / "api").rename(kit.ws / "api-svc")
    monkeypatch.setattr(kit.services.links, "link", lambda dst, target, log=print: False)
    res = rh().find(**QUIET)
    assert res["missing"] == ["api"]
    assert Path(row(res, "api")["path"]) == (kit.ws / "api-svc").resolve()
    assert not os.path.lexists(kit.ws / "api") and rh().load()["links"] == {}


def test_unlink_all_removes_only_the_kit_links(kit, tmp_path):
    team_repos(kit, tmp_path)
    (kit.ws / "api").rename(kit.ws / "api-svc")
    rh().find(**QUIET)
    assert kit.services.links.link(kit.ws / "mine", kit.ws / "web")       # a link of the person's own
    assert rh().links_made() == {"api": str((kit.ws / "api-svc").resolve())}
    assert rh().unlink_all(**QUIET) == ["api"]
    assert not os.path.lexists(kit.ws / "api") and (kit.ws / "api-svc" / "pom.xml").is_file()
    assert kit.services.links._is_link(kit.ws / "mine")
    assert rh().load()["links"] == {}


def test_a_link_in_a_workspace_under_git_is_excluded_until_unlinked(kit, tmp_path):
    git(kit.ws, "init", "-q")
    exclude = kit.ws / ".git" / "info" / "exclude"
    exclude.parent.mkdir(parents=True, exist_ok=True)
    exclude.write_text("/web\n", encoding="utf-8")                        # the person's own line stays
    team_repos(kit, tmp_path)
    (kit.ws / "api").rename(kit.ws / "api-svc")
    (kit.ws / "web").rename(kit.ws / "web-app")
    rh().find(**QUIET)
    assert {"/api", "/web"} <= set(exclude.read_text(encoding="utf-8").splitlines())
    rh().unlink_all(**QUIET)
    assert exclude.read_text(encoding="utf-8").splitlines() == ["/web"]


# ---------- setup and catch-up use it ----------
def offline_setup(kit, monkeypatch):
    """setup with nothing to install: the repos part runs for real against the local remotes."""
    monkeypatch.setattr(kit.services.setup, "prerequisites", lambda: {})
    return lambda: kit.services.setup.setup(log=lambda _: None, comps=[])


def names(ws: Path) -> list[str]:
    return sorted(p.name for p in ws.iterdir() if not p.name.startswith("."))


def test_setup_links_a_renamed_clone_and_clones_only_what_is_missing(kit, tmp_path, monkeypatch):
    team_repos(kit, tmp_path)
    (kit.ws / "api").rename(kit.ws / "api-svc")
    kit.common.rmtree(kit.ws / "worker")
    assert offline_setup(kit, monkeypatch)()
    assert same(kit.ws / "api", kit.ws / "api-svc")
    assert (kit.ws / "worker" / ".git").is_dir() and not kit.services.links._is_link(kit.ws / "worker")
    assert names(kit.ws) == ["api", "api-svc", "cam-docs", "web", "worker"]


def test_setup_does_not_clone_over_an_unlinkable_clone(kit, tmp_path, monkeypatch):
    team_repos(kit, tmp_path)
    (kit.ws / "api").rename(kit.ws / "api-svc")
    monkeypatch.setattr(kit.services.links, "link", lambda dst, target, log=print: False)
    assert offline_setup(kit, monkeypatch)()
    assert names(kit.ws) == ["api-svc", "cam-docs", "web", "worker"]


def test_setup_skips_a_taken_folder_without_failing(kit, tmp_path, monkeypatch):
    team_repos(kit, tmp_path)
    kit.common.rmtree(kit.ws / "worker")
    (kit.ws / "worker").mkdir()
    (kit.ws / "worker" / "notes.txt").write_text("mine\n", encoding="utf-8")
    assert offline_setup(kit, monkeypatch)()
    assert sorted(p.name for p in (kit.ws / "worker").iterdir()) == ["notes.txt"]


def test_the_catch_up_finds_the_repos(kit, tmp_path):
    team_repos(kit, tmp_path)
    (kit.ws / "api").rename(kit.ws / "api-svc")
    r = kit.services.catchup.run(log=lambda _: None)
    assert r["repos"] == {"here": ["web", "worker"], "linked": ["api"], "missing": [], "taken": []}
    assert same(kit.ws / "api", kit.ws / "api-svc")
