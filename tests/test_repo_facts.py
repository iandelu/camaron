"""Static repo facts (adapter behind ports.repo_facts): stack pills, build tool, head, outdated libraries, graph size."""
from __future__ import annotations

import json
import subprocess

import pytest

POM = ("<project><properties><java.version>17</java.version></properties><dependencies>"
       "<dependency><artifactId>spring-boot-starter-web</artifactId></dependency>"
       "<dependency><artifactId>postgresql</artifactId></dependency></dependencies></project>\n")


@pytest.fixture
def rf(kit):
    from lib.adapters import repo_facts
    return repo_facts


def git(repo, *args):
    subprocess.run(["git", "-c", "user.name=Ana", "-c", "user.email=x@example.com", *args], cwd=repo, check=True,
                   capture_output=True)


def commit(repo, files, msg="c"):
    for rel, text in files.items():
        f = repo / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", msg)


@pytest.mark.parametrize("files, tool", [
    ({"pom.xml": "<x/>"}, "maven"),
    ({"build.gradle.kts": ""}, "gradle"),
    ({"package.json": "{}", "pnpm-lock.yaml": ""}, "pnpm"),
    ({"package.json": "{}", "yarn.lock": ""}, "yarn"),
    ({"package.json": "{}"}, "npm"),
    ({"pyproject.toml": "", "uv.lock": ""}, "uv"),
    ({"pyproject.toml": "", "poetry.lock": ""}, "poetry"),
    ({"requirements.txt": ""}, "pip"),
    ({"go.mod": ""}, "go"),
    ({}, None),
])
def test_build_tool(rf, tmp_path, files, tool):
    for rel, text in files.items():
        (tmp_path / rel).write_text(text, encoding="utf-8")
    assert rf.build_tool(tmp_path) == tool


def test_facts_lists_the_stack_in_role_order(rf, kit):
    commit(kit.ws / "api", {"pom.xml": POM, "Dockerfile": "FROM x\n", ".github/workflows/ci.yml": "on: push\n"})
    got = rf.facts("api")
    assert got["stack"] == [{"role": "language", "label": "Java 17"}, {"role": "framework", "label": "Spring Boot"},
                            {"role": "build", "label": "Maven"}, {"role": "data", "label": "PostgreSQL"},
                            {"role": "container", "label": "Docker"}, {"role": "ci", "label": "GitHub Actions"}]
    assert got["build"] == "maven" and got["head"]["sha"] and len(got["head"]["sha"]) == 7
    assert got["activity"]["total"] >= 1


def test_workspace_stack_override_wins(rf, kit):
    from lib.adapters.stores import workspace
    ws = workspace.workspace()
    next(r for r in ws["repos"] if r["name"] == "api")["stack"] = "Kotlin · Ktor"
    workspace.save_workspace(ws)
    commit(kit.ws / "api", {"pom.xml": POM})
    labels = [(s["role"], s["label"]) for s in rf.facts("api")["stack"]]
    assert labels[:2] == [("language", "Kotlin"), ("framework", "Ktor")]


def test_facts_are_cached_per_head(rf, kit, monkeypatch):
    from lib import quickarch
    commit(kit.ws / "api", {"pom.xml": POM})
    calls = []
    real = quickarch.repo_blob
    monkeypatch.setattr(quickarch, "repo_blob", lambda p: calls.append(p) or real(p))
    rf.facts("api")
    rf.facts("api")
    assert len(calls) == 1
    commit(kit.ws / "api", {"extra.txt": "x"}, "second")
    rf.facts("api")
    assert len(calls) == 2


def test_two_requests_at_once_read_the_repo_once(rf, kit, monkeypatch):
    import threading, time
    from lib import quickarch
    commit(kit.ws / "api", {"pom.xml": POM})
    calls, real = [], quickarch.repo_blob

    def slow(p):
        calls.append(p)
        time.sleep(0.2)
        return real(p)
    monkeypatch.setattr(quickarch, "repo_blob", slow)
    got = []
    threads = [threading.Thread(target=lambda: got.append(rf.facts("api"))) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(calls) == 1 and len(got) == 2 and got[0] == got[1]


def test_a_cache_hit_costs_one_git_process_and_follows_the_branch(rf, kit, monkeypatch):
    from lib.core import process
    commit(kit.ws / "api", {"pom.xml": POM})
    first = rf.facts("api")
    seen, real = [], process.run
    monkeypatch.setattr(process, "run", lambda cmd, *a, **kw: seen.append(cmd) or real(cmd, *a, **kw))
    assert rf.facts("api") == first
    assert len(seen) == 1
    monkeypatch.setattr(process, "run", real)
    git(kit.ws / "api", "checkout", "-q", "-b", "feature")
    assert rf.facts("api")["head"]["branch"] == "feature"


def test_editing_the_stack_override_shows_at_once(rf, kit):
    from lib.adapters.stores import workspace
    commit(kit.ws / "api", {"pom.xml": POM})
    assert rf.facts("api")["stack"][0] == {"role": "language", "label": "Java 17"}
    ws = workspace.workspace()
    next(r for r in ws["repos"] if r["name"] == "api")["stack"] = "Kotlin · Ktor"
    workspace.save_workspace(ws)
    assert rf.facts("api")["stack"][:2] == [{"role": "language", "label": "Kotlin"}, {"role": "framework", "label": "Ktor"}]


def test_an_override_of_only_separators_draws_no_language_pill(rf, kit):
    from lib.adapters.stores import workspace
    ws = workspace.workspace()
    next(r for r in ws["repos"] if r["name"] == "api")["stack"] = " · "
    workspace.save_workspace(ws)
    commit(kit.ws / "api", {"pom.xml": POM})
    stack = rf.facts("api")["stack"]
    assert not any(p["role"] in ("language", "framework") for p in stack)
    assert {"role": "build", "label": "Maven"} in stack


def test_a_repo_not_cloned_has_no_facts(rf, kit):
    assert rf.facts("missing") == {"head": None, "stack": [], "build": None, "activity": None}


def test_outdated_counts_distinct_libraries_with_a_newer_version(rf, kit, monkeypatch):
    from lib import inventory
    rows = [{"repo": "api", "ecosystem": "npm", "name": "a", "version": "1.0.0"},
            {"repo": "api", "ecosystem": "npm", "name": "a", "version": "1.0.0"},
            {"repo": "api", "ecosystem": "npm", "name": "b", "version": "2.0.0"},
            {"repo": "web", "ecosystem": "npm", "name": "c", "version": "1.0.0"}]
    monkeypatch.setattr(inventory, "load", lambda: {"libraries": rows, "latest": {"versions": {
        "npm|a": "1.1.0", "npm|b": "2.0.0", "npm|c": "9.0.0"}}})
    assert rf.outdated("api") == 1
    monkeypatch.setattr(inventory, "load", lambda: {"libraries": rows, "latest": None})
    assert rf.outdated("api") is None


def test_graph_nodes(rf, kit):
    from lib.adapters import graphify
    assert rf.graph_nodes("api") is None
    path = graphify.repo_graph("api")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"nodes": [{}, {}, {}]}), encoding="utf-8")
    assert rf.graph_nodes("api") == 3
