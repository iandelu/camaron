"""`camaron arch-verify` and the C4 findings of `check` (spec §5.2, §5.5)."""
from __future__ import annotations

import argparse
import importlib
import json
import os
import subprocess
import sys

import pytest
from test_c4_evidence import API, CODE, COMMENT, FRAGMENT, GHOST, MODEL, READS, edit, element, model


def cli(kit, *args):
    e = {**os.environ, "CAMARONES_ROOT": str(kit.root)}
    return subprocess.run([sys.executable, str(kit.kit_dir / "camarones.py"), *args], env=e, capture_output=True,
                          text=True, encoding="utf-8")


OLD = "src/gone/Old.java"
HELPER = "src/main/java/demo/util/Helper.java"
WORKER = "    worker = service 'Worker' {\n      metadata { repo 'worker' }\n    }\n"


def graph(kit, *links, commit=None):
    """api's code graph: Api.java (shop.api.orders), src/gone/Old.java (shop.api.legacy's folder), a file no element
    covers and a test; `links` are (from file, to file, relation, line)."""
    files = [API, OLD, HELPER, "src/test/java/demo/ApiTest.java"]
    data = {"nodes": [{"id": f, "label": f.rsplit("/", 1)[-1], "source_file": f, "source_location": "L1",
                       "file_type": "code"} for f in files],
            "links": [{"source": a, "target": b, "relation": rel, "source_location": line} for a, b, rel, line in links]}
    if commit:
        data["built_at_commit"] = commit
    g = kit.services.code.repo_graph("api")
    g.parent.mkdir(parents=True, exist_ok=True)
    g.write_text(json.dumps(data), encoding="utf-8")


@pytest.fixture
def verify_world(kit):
    model(kit, MODEL)
    model(kit, FRAGMENT, "repos/api.c4")
    return kit, importlib.import_module("lib.app.c4_verify")


def test_check_warns_and_strict_fails(verify_world):
    kit, _ = verify_world
    errors, warns = kit.services.doc_status.check()
    assert any("C4 shop.db: no-evidence" in w for w in warns) and not any("C4 " in e for e in errors)
    errors, _ = kit.services.doc_status.check(strict=True)
    assert any("C4 shop.db: no-evidence" in e for e in errors)


def test_findings_name_file_line_and_what_is_wrong(verify_world):
    _, v = verify_world
    _, warns = v.findings(False)
    assert any(w.startswith("repos/api.c4:") and "C4 shop.api.legacy: broken" in w and "src/gone/" in w for w in warns)


def test_unchecked_never_fails(verify_world):
    kit, v = verify_world
    kit.common.rmtree(kit.ws / "api")
    errors, warns = v.findings(True)
    assert not any("unchecked" in e for e in errors)
    assert sum("unchecked" in w for w in warns) == 1


def test_a_confirmed_element_without_evidence_is_not_a_finding(verify_world):
    _, v = verify_world
    errors, warns = v.findings(True)
    assert not any("shop.ghost" in x for x in errors + warns)


def test_an_undrawn_import_is_drift_and_strict_makes_it_an_error(verify_world):
    kit, v = verify_world
    graph(kit, (OLD, API, "imports", "L3"), ("src/test/java/demo/ApiTest.java", OLD, "calls", "L2"))
    api = v.report()["repos"]["api"]
    assert api["graph"] == "ok" and api["overlaps"] == []
    assert api["in_code_not_model"] == [{"from": "shop.api.legacy", "to": "shop.api.orders", "count": 1,
                                         "example": f"{OLD}:L3"}]
    assert api["coverage"] == [{"folder": "src/main/java/demo/util", "files": 1}]
    line = "C4 drift in api: shop.api.legacy -> shop.api.orders"
    errors, warns = v.findings(False)
    assert not errors and any(line in w and f"{OLD}:L3" in w for w in warns)
    errors, _ = v.findings(True)
    assert any(line in e for e in errors)


def test_a_drawn_relation_nothing_backs_is_no_evidence(verify_world):
    kit, v = verify_world
    graph(kit, (OLD, API, "imports", "L3"))
    rel = v.report()["relations"]
    assert rel and all(r["state"] == "no-evidence" and r["backing"] == [] for r in rel.values())
    errors, _ = v.findings(True)
    assert any(f"C4 {READS}: no-evidence" in e for e in errors)


def test_an_edge_in_the_code_backs_the_drawn_relation(verify_world):
    kit, v = verify_world
    graph(kit, (API, OLD, "calls", "L4"))
    rep = v.report()
    assert rep["relations"][READS]["state"] == "fresh"
    assert rep["relations"][READS]["backing"] == [{"by": "graph", "repo": "api", "from": "shop.api.orders",
                                                   "to": "shop.api.legacy", "count": 1, "example": f"{API}:L4"}]
    assert rep["repos"]["api"]["in_code_not_model"] == []
    errors, warns = v.findings(True)
    assert not any(READS in x for x in errors + warns)


def test_without_a_graph_relations_are_unchecked_and_never_fail(verify_world):
    _, v = verify_world
    rep = v.report()
    assert rep["repos"]["api"] == {"graph": "missing", "in_code_not_model": [], "overlaps": [], "coverage": []}
    assert rep["relations"] and all(r["state"] == "unchecked" for r in rep["relations"].values())
    errors, warns = v.findings(True)
    assert not any(READS in e or "graph" in e for e in errors)
    assert any("api has no code graph" in w and "camaron graph" in w for w in warns)
    assert any("unchecked" in w and "no code graph" in w for w in warns)


def test_a_missing_graph_leaves_container_relations_to_the_scan(verify_world):
    kit, v = verify_world
    model(kit, MODEL.replace(GHOST, GHOST + "    api -> db 'stores'\n"))
    rel = v.report()["relations"]
    assert rel["shop.api -> shop.db 'stores'"]["state"] == "no-evidence" and rel[READS]["state"] == "unchecked"


def test_a_stale_graph_is_said_and_never_an_error(verify_world):
    kit, v = verify_world
    graph(kit, (API, OLD, "calls", "L4"), commit="0000000")
    api = v.report()["repos"]["api"]
    assert api["graph"] == "stale" and api["note"].startswith("built at 0000000, the repo is at ")
    errors, warns = v.findings(True)
    assert not any("graph" in e for e in errors)
    assert any("code graph of api was built at 0000000" in w for w in warns)


def test_a_relation_anchored_to_a_line_needs_no_graph(verify_world):
    kit, v = verify_world
    anchored = "    orders -> legacy 'calls' {\n      metadata { code 'api:src/main/java/demo/Api.java#L4' }\n    }\n"
    model(kit, FRAGMENT.replace("    orders -> legacy 'reads'\n", anchored, 1), "repos/api.c4")
    rel = v.report()["relations"]
    assert rel["shop.api.orders -> shop.api.legacy 'calls'"]["state"] == "fresh"
    assert rel[READS]["state"] == "unchecked"


def test_the_scan_compares_the_containers(verify_world):
    kit, v = verify_world
    box = v.report()["containers"]
    assert box == {"in_code_not_model": [], "not_compared": [{"from": "api", "to": "worker", "label": "calls (HTTP)",
                                                              "unmatched": ["worker"]}]}
    assert not any("worker" in x for x in sum(v.findings(True), []))      # not compared is never drift
    model(kit, MODEL.replace(GHOST, GHOST + WORKER))
    box = v.report()["containers"]
    assert box == {"in_code_not_model": [{"from": "shop.api", "to": "shop.worker", "label": "calls (HTTP)",
                                          "example": f"api:{API}#L4"}], "not_compared": []}
    drawn = f"C4 drift: shop.api -> shop.worker 'calls (HTTP)' is in the code (api:{API}#L4) but not in the model"
    assert any(drawn in w for w in v.findings(False)[1]) and any(drawn in e for e in v.findings(True)[0])


def test_a_container_edge_backs_a_relation_between_their_parts(verify_world):
    kit, v = verify_world
    model(kit, MODEL.replace(GHOST, GHOST + WORKER + "    api.orders -> worker 'asks'\n"))
    rep = v.report()
    key = "shop.api.orders -> shop.worker 'asks'"
    assert rep["relations"][key]["state"] == "fresh"
    assert rep["relations"][key]["backing"] == [{"by": "scan", "from": "shop.api", "to": "shop.worker",
                                                 "label": "calls (HTTP)", "example": f"api:{API}#L4"}]
    assert rep["containers"]["in_code_not_model"] == []


def test_worst_first_names_every_state():
    v = importlib.import_module("lib.app.c4_verify")
    states = importlib.import_module("lib.domain.c4.verdict").STATES
    assert sorted(v.WORST_FIRST) == sorted(states) and len(v.WORST_FIRST) == len(states)


def test_arch_verify_json_and_ack(verify_world):
    kit, _ = verify_world
    r = cli(kit, "arch-verify", "--json")
    data = json.loads(r.stdout)
    assert r.returncode == 0 and data["elements"]["shop.db"]["state"] == "no-evidence"
    assert data["repos"]["api"]["graph"] == "missing" and data["containers"]["in_code_not_model"] == []
    assert cli(kit, "arch-verify", "--ack", "shop.api.orders").returncode != 0


def test_ack_re_stamps_the_element(verify_world):
    kit, _ = verify_world
    fresh = importlib.import_module("lib.harness.freshness")
    fresh.c4_stamp_all()
    edit(kit, "api", API, COMMENT, CODE)
    assert fresh.c4_states()["elements"]["shop.api.orders"]["state"] == "suspect"
    r = cli(kit, "arch-verify", "--ack", "shop.api.orders", "--by", "ana")
    assert r.returncode == 0 and "shop.api.orders" in r.stdout
    assert fresh.c4_states()["elements"]["shop.api.orders"]["state"] == "fresh"


def test_ack_of_an_unknown_name_exits_1(verify_world):
    kit, _ = verify_world
    r = cli(kit, "arch-verify", "--ack", "shop.api.orders", "shop.nope", "--by", "ana")
    assert r.returncode == 1 and "shop.nope" in r.stderr


def test_an_ack_that_cannot_save_exits_1(verify_world, monkeypatch, capsys):
    kit, _ = verify_world
    fresh = importlib.import_module("lib.harness.freshness")
    monkeypatch.setattr(fresh, "c4_ack", lambda *a, **k: (_ for _ in ()).throw(OSError("disk full")))
    registry = importlib.import_module("lib.interfaces.cli.registry")
    cmd = importlib.import_module("lib.interfaces.cli.commands.check").ArchVerify()
    args = argparse.Namespace(json=False, ack=["shop.api.orders"], by="ana")
    assert cmd.run(args, registry.CliContext(argparse.ArgumentParser(), kit.services)) == 1
    assert "disk full" in capsys.readouterr().err


def test_suspect_is_only_ever_a_warning(verify_world):
    kit, v = verify_world
    fresh = importlib.import_module("lib.harness.freshness")
    fresh.c4_stamp_all()
    edit(kit, "api", API, COMMENT, CODE)
    errors, warns = v.findings(True)
    assert any("C4 shop.api.orders: suspect" in w for w in warns)
    assert not any("C4 shop.api.orders:" in e for e in errors)


def test_unreadable_entries_follow_strict(verify_world):
    kit, v = verify_world
    model(kit, MODEL.replace(GHOST, GHOST + element("loose", "src/A.java")))
    errors, warns = v.findings(True)
    assert any("shop.loose: unreadable evidence entry 'src/A.java'" in e for e in errors)
    errors, warns = v.findings(False)
    assert not errors and any("shop.loose: unreadable evidence entry" in w for w in warns)


def test_an_unreadable_line_without_a_file_has_no_prefix(verify_world):
    _, v = verify_world
    assert v._where({}) == ""


def test_arch_verify_text_lists_worst_first(verify_world):
    kit, _ = verify_world
    out = cli(kit, "arch-verify").stdout
    assert out.index("broken (") < out.index("no-evidence (")
    legacy = out[out.index("turn into `code`"):]
    assert "shop.api.legacy" in legacy and "shop.db" not in legacy


def test_arch_verify_text_prints_the_drift_and_the_candidates(verify_world):
    kit, _ = verify_world
    graph(kit, (OLD, API, "imports", "L3"))
    out = cli(kit, "arch-verify").stdout
    drift = out[out.index("drift in api"):]
    assert "in the code, not in the model (1)" in drift and "shop.api.legacy -> shop.api.orders" in drift
    assert "candidate components" in drift and "src/main/java/demo/util/" in drift
    assert "not compared" in out


def test_arch_verify_text_says_what_it_could_not_compare(verify_world):
    kit, _ = verify_world
    out = cli(kit, "arch-verify").stdout
    api = out[out.index("drift in api"):out.index("containers")]
    assert "no code graph, not compared" in api and "in the code" not in api and "candidate" not in api


def test_no_model_no_findings(kit):
    v = importlib.import_module("lib.app.c4_verify")
    assert v.findings(False) == ([], []) and v.findings(True) == ([], [])


def test_a_model_that_does_not_parse_warns_once(verify_world, monkeypatch):
    kit, v = verify_world
    c4edit = importlib.import_module("lib.c4edit")
    monkeypatch.setattr(c4edit, "index", lambda *a, **k: (_ for _ in ()).throw(ValueError("boom")))
    importlib.import_module("lib.harness.freshness")._parsed.cache_clear()
    errors, warns = v.findings(True)
    assert not errors and sum("C4 model could not be read" in w for w in warns) == 1
