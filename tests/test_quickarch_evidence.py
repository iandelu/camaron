"""The first-look C4 draft (quickarch) carries the code it was read from: `repo:path#Ln` anchors on elements and relations."""
from __future__ import annotations

API = "src/main/java/demo/Api.java"


def test_relations_carry_the_line_they_were_read_from(kit):
    from lib import quickarch
    scan = quickarch.scan()
    assert scan["edge_evidence"][("api", "worker", "calls (HTTP)")] == f"api:{API}#L4"
    model = quickarch.render_c4(scan, "demo")["model.c4"]
    assert f"'calls (HTTP)' {{ metadata {{ code 'api:{API}#L4' }} }}" in model


def test_elements_carry_full_anchors_and_the_scan_is_a_port(kit):
    from lib import quickarch
    scan = quickarch.scan()
    assert scan["repo_evidence"]["api"] == ["api:pom.xml"]
    model = quickarch.render_c4(scan, "demo")["model.c4"]
    assert model.count("metadata") >= 1 and "metadata { repo 'api' code ['api:pom.xml'] }" in model
    block = model[model.index("api = service"):].split("    }", 1)[0]
    assert block.count("metadata") == 1
    assert kit.services.arch_scan.scan is quickarch.scan


def test_an_element_names_at_most_three_sorted_anchors(kit):
    from lib import quickarch
    model = {"repos": {"api": {"kind": "service", "tech": "Java"}}, "dbs": {}, "brokers": set(), "idps": set(),
             "edges": [], "caches": set(), "repo_evidence": {"api": ["api:d", "api:b", "api:a", "api:c"]}}
    assert "metadata { repo 'api' code ['api:a', 'api:b', 'api:c'] }" in quickarch.render_c4(model, "demo")["model.c4"]


def test_a_path_with_a_quote_is_written_exactly_as_it_is(kit):
    from lib import quickarch
    model = {"repos": {"api": {"kind": "service", "tech": "Java"}, "w": {"kind": "service", "tech": "Java"}}, "dbs": {},
             "brokers": set(), "idps": set(), "caches": set(), "edges": [("api", "w", "sync", "calls (HTTP)")],
             "repo_evidence": {"api": ["api:it's/pom.xml"]}, "edge_evidence": {("api", "w", "calls (HTTP)"): "api:it's/A.java#L2"}}
    text = quickarch.render_c4(model, "demo")["model.c4"]
    assert "metadata { repo 'api' code [\"api:it's/pom.xml\"] }" in text
    assert "{ metadata { code \"api:it's/A.java#L2\" } }" in text


def test_a_match_on_a_header_line_gives_no_anchor_and_a_later_line_is_numbered():
    from lib import quickarch
    blob = "\n### src/worker/Api.java\nint a;\n// worker\n"
    paths = {"src/worker/Api.java"}
    assert quickarch._anchor("api", blob, blob.index("worker/Api"), paths) is None
    assert quickarch._anchor("api", blob, blob.index("// worker"), paths) == "api:src/worker/Api.java#L2"


def test_a_header_like_line_inside_a_scanned_file_is_not_a_file():
    from lib import quickarch
    blob = "\n### cache.properties\n### Cache\nclient=jedis\n"
    at = blob.index("jedis")
    assert quickarch._source(blob, at, {"cache.properties"}) == "cache.properties"
    assert quickarch._anchor("api", blob, at, {"cache.properties"}) == "api:cache.properties#L2"


def test_the_scan_cites_the_file_a_header_like_line_sits_in(kit):
    from lib import quickarch
    (kit.ws / "api" / "cache.properties").write_text("### Cache\nclient=jedis\n", encoding="utf-8", newline="\n")
    scan = quickarch.scan()
    assert "api:cache.properties#L2" in scan["evidence"]["cache"]
    assert not any(a.startswith("api:Cache") for found in scan["evidence"].values() for a in found)


def test_a_relation_takes_the_earliest_line_numerically(kit):
    from lib import quickarch
    url = "spring.datasource.url=jdbc:postgresql://db:5432/orders\n"
    (kit.ws / "api" / "db.properties").write_text("# db\n" + url + "#\n" * 7 + url, encoding="utf-8", newline="\n")
    scan = quickarch.scan()
    assert {"api:db.properties#L2", "api:db.properties#L10"} <= set(scan["evidence"]["PostgreSQL:orders"])
    assert scan["edge_evidence"][("api", "PostgreSQL:orders", "reads/writes")] == "api:db.properties#L2"


def test_the_cache_dependency_stays_out_of_the_first_look_sources(kit):
    from lib import quickarch
    (kit.ws / "api" / "cache.properties").write_text("client=jedis\n", encoding="utf-8")
    scan = quickarch.scan()
    assert "api" in scan["caches"] and "cache" in scan["evidence"]
    assert "api:cache.properties" not in scan["sources"]


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


def test_a_drafted_repo_reads_back_with_its_repo_and_its_code(kit, monkeypatch):
    from lib import c4edit, quickarch
    monkeypatch.setattr(quickarch, "which", lambda name: None)
    quickarch.save(quickarch.draft(log=lambda _: None))
    assert c4edit.index()["elements"]["demo.api"]["metadata"] == {"repo": "api", "code": ["api:pom.xml"]}
