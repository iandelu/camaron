"""What the code shows between C4 elements (spec §6.1, §6.3): files mapped to the element whose anchors cover them most
specifically, structural graph edges lifted to relations, which of them the drawn relations cover, and the code no
element covers."""
from __future__ import annotations

import importlib

from lib.domain.c4 import anchors, drift


def code(*entries):
    return anchors.parse_code(list(entries))[0]


def test_imports_between_components_become_relations():
    file_of = {"src/geo/GeoRoute.java": "gw.geo", "src/err/ExceptionRoute.java": "gw.err"}
    graph = {"nodes": [{"id": "a", "source_file": "src/geo/GeoRoute.java"},
                       {"id": "b", "source_file": "src/err/ExceptionRoute.java"}],
             "links": [{"source": "a", "target": "b", "relation": "extends", "source_location": "L5"}]}
    got = drift.derive(graph, file_of)
    assert got[("gw.geo", "gw.err")]["count"] == 1 and got[("gw.geo", "gw.err")]["example"] == "src/geo/GeoRoute.java:L5"
    assert got[("gw.geo", "gw.err")]["relations"] == ["extends"]


def test_external_nodes_never_become_relations():
    graph = {"nodes": [{"id": "a", "source_file": "src/geo/GeoRoute.java"}, {"id": "x", "label": "java.util"}],
             "links": [{"source": "a", "target": "x", "relation": "imports"}]}
    assert drift.derive(graph, {"src/geo/GeoRoute.java": "gw.geo"}) == {}


def test_only_structural_edges_between_two_elements_count():
    file_of = {"a/A.java": "s.a", "a/A2.java": "s.a", "b/B.java": "s.b"}
    graph = {"nodes": [{"id": i, "source_file": f} for i, f in (("a", "a/A.java"), ("a2", "a/A2.java"),
                                                                 ("b", "b/B.java"))],
             "links": [{"source": "a", "target": "a2", "relation": "calls"},           # inside one element
                       {"source": "a", "target": "b", "relation": "contains"},         # not structural
                       {"source": "a", "target": "b", "relation": "calls", "source_location": "L9"},
                       {"source": "a2", "target": "b", "relation": "imports", "source_location": "L1"},
                       {"source": "b", "target": "ghost", "relation": "calls"}]}
    assert drift.derive(graph, file_of) == {("s.a", "s.b"): {"count": 2, "example": "a/A.java:L9",
                                                             "relations": ["calls", "imports"]}}


def test_a_relation_drawn_between_parents_covers_the_children():
    assert drift.covered_by(("s.gw.geo", "s.cs.client"), {("s.gw", "s.cs")})
    assert drift.covered_by(("s.gw.geo", "s.cs"), {("s.gw.geo", "s.cs")})
    assert not drift.covered_by(("s.gw.geo", "s.cs.client"), {("s.cs", "s.gw")})            # direction counts
    assert not drift.covered_by(("s.gwx.geo", "s.cs"), {("s.gw", "s.cs")})                  # a prefix is not a parent
    assert not drift.covered_by(("s.gw", "s.cs"), {("s.gw.geo", "s.cs.client")})


def test_the_most_specific_anchor_wins_and_ties_are_overlaps():
    by_fqn = {"gw": code("api:src/"),
              "gw.geo": code("api:src/geo/", "api:src/shared/Util.java"),
              "gw.err": code("api:src/err/ExceptionRoute.java#ExceptionRoute", "api:src/shared/Util.java"),
              "gw.route": code("api:src/*/*Route.java")}
    files = ["src/geo/GeoRoute.java", "src/geo/Geo.java", "src/err/ExceptionRoute.java", "src/shared/Util.java",
             "src/Main.java", "lib/Other.java"]
    file_of, overlaps = drift.map_files(files, by_fqn, "api")
    assert file_of == {"src/geo/GeoRoute.java": "gw.route",          # a glob deeper than the folder
                       "src/geo/Geo.java": "gw.geo",                 # the deeper folder over src/
                       "src/err/ExceptionRoute.java": "gw.err",      # a symbol over the glob
                       "src/shared/Util.java": "gw.err",             # a tie: the first, and listed
                       "src/Main.java": "gw"}
    assert overlaps == [{"file": "src/shared/Util.java", "elements": ["gw.err", "gw.geo"]}]


def test_a_parent_and_its_child_tied_go_to_the_child():
    by_fqn = {"gw": code("api:src/geo/"), "gw.geo": code("api:src/geo/")}
    assert drift.map_files(["src/geo/G.java"], by_fqn, "api") == ({"src/geo/G.java": "gw.geo"}, [])


def test_anchors_of_another_repo_cover_nothing():
    assert drift.map_files(["src/A.java"], {"gw": code("web:src/")}, "api") == ({}, [])


def test_uncovered_files_group_by_folder():
    files = ["src/geo/A.java", "src/util/B.java", "src/util/C.java", "src/x/D.java", "Main.java"]
    assert drift.coverage(files, {"src/geo/A.java": "gw.geo"}) == [{"folder": "src/util", "files": 2},
                                                                     {"folder": ".", "files": 1},
                                                                     {"folder": "src/x", "files": 1}]


def test_source_files_leave_out_tests_build_output_and_non_code():
    graph = {"nodes": [{"source_file": "src/A.java", "file_type": "code"},
                       {"source_file": "src/A.java", "file_type": "code"},
                       {"source_file": "src/test/java/ATest.java", "file_type": "code"},
                       {"source_file": "target/gen/G.java", "file_type": "code"},
                       {"source_file": "README.md", "file_type": "document"},
                       {"source_file": "", "file_type": "code"},
                       {"source_file": "src/B.py"}]}
    assert drift.source_files(graph) == ["src/A.java", "src/B.py"]


def test_prompt_context_keeps_its_filters(kit):
    pc, moved = (importlib.import_module(m) for m in ("lib.app.prompt_context", "lib.domain.c4.drift"))
    assert pc.NOT_SOURCE is moved.NOT_SOURCE and pc.TEST_FILE is moved.TEST_FILE


def test_a_call_between_a_parent_and_its_child_is_no_relation():
    graph = {"nodes": [{"id": "m", "source_file": "src/Main.java"}, {"id": "g", "source_file": "src/geo/G.java"}],
             "links": [{"source": "m", "target": "g", "relation": "calls"},
                       {"source": "g", "target": "m", "relation": "imports"}]}
    assert drift.derive(graph, {"src/Main.java": "gw", "src/geo/G.java": "gw.geo"}) == {}


def test_windows_paths_read_as_posix():
    graph = {"nodes": [{"id": "a", "source_file": "src\\geo\\A.java"}, {"id": "b", "source_file": "src\\err\\B.java"}],
             "links": [{"source": "a", "target": "b", "relation": "calls", "source_location": "L2"}]}
    assert drift.source_files(graph) == ["src/err/B.java", "src/geo/A.java"]
    got = drift.derive(graph, {"src/geo/A.java": "gw.geo", "src/err/B.java": "gw.err"})
    assert got[("gw.geo", "gw.err")]["example"] == "src/geo/A.java:L2"


def test_a_graph_that_is_not_node_link_derives_nothing():
    odd_ids = {"nodes": [{"id": ["a"], "source_file": "a/A.java"}, {"id": "b", "source_file": "b/B.java"}],
               "links": [{"source": ["a"], "target": "b", "relation": "calls"},
                         {"source": "b", "target": {"x": 1}, "relation": ["calls"]}]}
    for graph, files in (({"nodes": {"a": 1}, "links": "x"}, []), ({"nodes": ["x"], "links": [1]}, []),
                         (odd_ids, ["a/A.java", "b/B.java"])):
        assert drift.source_files(graph) == files
        assert drift.derive(graph, {"a/A.java": "s.a", "b/B.java": "s.b"}) == {}


def el(kind, title, technology="", repo=None):
    return {"kind": kind, "title": title, "technology": technology, "metadata": {"repo": repo} if repo else {}}


SCAN = {"repos": {"api": {}, "app": {}, "app Cloud Functions": {"repo": "app"}},
        "dbs": {"PostgreSQL:orders": {"label": "PostgreSQL", "name": "orders"},
                "PostgreSQL:shop": {"label": "PostgreSQL", "name": "shop"}}}


def test_a_datastore_matches_on_its_technology_or_title():
    els = {"s": el("system", "Shop"), "s.api": el("service", "Api", repo="api"),
           "s.db": el("database", "Orders", "PostgreSQL"), "s.bus": el("queue", "Kafka events")}
    match = drift.matcher(SCAN, els)
    assert (match("api"), match("PostgreSQL:orders"), match("Kafka")) == ("s.api", "s.db", "s.bus")


def test_a_name_alone_or_a_person_matches_nothing():
    els = {"shop": el("system", "Shop"), "shop.api": el("service", "Api", repo="api"),
           "admin": el("externalSystem", "Shop admin"), "ops": el("actor", "Keycloak operator", "Keycloak")}
    match = drift.matcher(SCAN, els)
    assert match("PostgreSQL:shop") is None and match("Keycloak") is None


def test_two_datastores_alike_tie_unless_the_name_tells_them_apart():
    els = {"s.a": el("database", "Billing", "PostgreSQL"), "s.b": el("database", "Ledger", "PostgreSQL")}
    assert drift.matcher(SCAN, els)("PostgreSQL:orders") is None
    els["s.b"] = el("database", "Orders ledger", "PostgreSQL")
    assert drift.matcher(SCAN, els)("PostgreSQL:orders") == "s.b"


def test_a_repo_goes_to_its_outermost_element_then_to_its_title():
    els = {"s.api": el("service", "Api", repo="api"), "s.api.inner": el("component", "Inner", repo="api"),
           "s.app": el("mobileApp", "app", repo="app"), "s.fn": el("service", "app Cloud Functions", repo="app")}
    assert drift.repo_boxes(els) == {"api": ["s.api"], "app": ["s.app", "s.fn"]}
    match = drift.matcher(SCAN, els)
    assert (match("api"), match("app"), match("app Cloud Functions")) == ("s.api", "s.app", "s.fn")
