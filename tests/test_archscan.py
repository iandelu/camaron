from pathlib import Path

from conftest import KIT_DIR
from fixtures import archscan

TREE = {
    "lib/__init__.py": "",
    "lib/a.py": "from .pkg import b\nimport json\n",
    "lib/pkg/__init__.py": "from .c import Y\n",
    "lib/pkg/b.py": "from ..a import X\n\ndef f():\n    from . import c\n",
    "lib/pkg/c.py": "Y = 1\nfrom typing import TYPE_CHECKING\nif TYPE_CHECKING:\n    from . import Y as _\n",
    "camarones.py": "from lib import a\nfrom lib.pkg import c\nimport lib.pkg.b\n",
}


def build(tmp_path: Path, tree: dict[str, str]) -> Path:
    kit = tmp_path / "kit"
    for rel, text in tree.items():
        path = kit / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return kit


def test_modules_are_named_from_lib(tmp_path):
    assert set(archscan.modules(build(tmp_path, TREE))) == {"a", "pkg", "pkg.b", "pkg.c", "camarones"}


def test_edges_resolve_relative_absolute_and_nested_imports(tmp_path):
    mods = archscan.modules(build(tmp_path, TREE))
    assert archscan.edges(mods) == {
        ("a", "pkg.b"), ("pkg", "pkg.c"), ("pkg.b", "a"), ("pkg.b", "pkg.c"), ("pkg.c", "pkg"),
        ("camarones", "a"), ("camarones", "pkg.c"), ("camarones", "pkg.b")}


def test_largest_cycle_is_the_biggest_strongly_connected_component(tmp_path):
    mods = archscan.modules(build(tmp_path, TREE))
    assert archscan.largest_cycle(mods, archscan.edges(mods)) == 2
    assert archscan.largest_cycle(["x", "y"], {("x", "y")}) == 0


def test_imports_inside_functions_count_on_the_real_kit():
    found = archscan.edges(archscan.modules(KIT_DIR))
    assert ("interfaces.cli.middleware", "usage") in found and ("interfaces.http.routes.docs", "answers") in found


def test_core_escapes_reports_an_edge_leaving_the_core_folder():
    found = {("core.process", "common"), ("core.paths", "harness.locks"), ("core.a", "core.b"), ("common", "core.a"),
             ("coreish", "a")}
    assert archscan.core_escapes(found) == {("core.process", "common"), ("core.paths", "harness.locks")}


def test_cycle_modules_counts_every_module_inside_a_cycle(tmp_path):
    mods = archscan.modules(build(tmp_path, TREE))
    assert archscan.cycle_modules(mods, archscan.edges(mods)) == 4
    assert archscan.cycle_modules(["x", "y"], {("x", "y")}) == 0


def test_arch_draft_relations_carry_the_line_they_were_read_from(kit):
    from lib import quickarch
    scan = quickarch.scan()
    assert scan["edge_evidence"][("api", "worker", "calls (HTTP)")] == "api:src/main/java/demo/Api.java#L4"
    model = quickarch.render_c4(scan, "demo")["model.c4"]
    assert "'calls (HTTP)' { metadata { code 'api:src/main/java/demo/Api.java#L4' } }" in model


def test_arch_draft_elements_with_evidence_name_up_to_three_anchors_and_the_scan_is_a_port(kit):
    from lib import quickarch
    scan = quickarch.scan()
    for key, anchors in scan["evidence"].items():
        assert 1 <= len(anchors) and all(a.split(":", 1)[0] in {"api", "web", "worker"} for a in anchors)
    assert scan["evidence"]["api"] == ["api:pom.xml"]
    model = quickarch.render_c4(scan, "demo")["model.c4"]
    assert scan["evidence"] and "metadata { code ['api:" in model
    assert kit.services.arch_scan.scan is quickarch.scan


def test_a_saved_draft_leaves_no_repo_or_relation_without_evidence(kit, monkeypatch):
    from lib import quickarch
    from lib.harness import freshness
    monkeypatch.setattr(quickarch, "which", lambda name: None)
    quickarch.save(quickarch.draft(log=lambda _: None))
    states = freshness.c4_states()
    repos = {fqn: e["state"] for fqn, e in states["elements"].items() if fqn.startswith("demo.")}
    assert repos and "no-evidence" not in repos.values()
    call = next(r for r in states["relations"].values() if r["label"] == "calls (HTTP)")
    assert call["own"] == "fresh"
