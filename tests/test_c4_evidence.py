"""C4 evidence in freshness (spec §5.1–§5.4): every element and relation gets a state from the anchors it names, its
stamps live under `c4` in docs/.work/fresh.json, pages citing `c4:<fqn>` follow their element, and the element-text
fingerprint leaves out tags and metadata so adding evidence or confirming does not make those pages suspect."""
from __future__ import annotations

import importlib
import json

import pytest

API = "src/main/java/demo/Api.java"
COMMENT = "    // calls worker over HTTP"
CODE = "    void call() { }"
DB = "    db = database 'Orders DB'\n"
GHOST = "    ghost = service 'Ghost' { #confirmed }\n"

MODEL = """model {
  shop = system 'Shop' {
    api = service 'Api' {
      metadata { repo 'api' }
    }
    db = database 'Orders DB'
    ghost = service 'Ghost' { #confirmed }
  }
}
"""
FRAGMENT = """model {
  extend shop.api {
    orders = component 'Orders' {
      metadata { code ['api:src/main/java/demo/Api.java', 'api:src/main/java/demo/Api.java#Api'] }
    }
    legacy = component 'Legacy' {
      metadata { evidence 'src/main/java/demo/Api.java, src/gone/' }
    }
    orders -> legacy 'reads'
    orders -> legacy 'reads'
  }
}
"""
READS = "shop.api.orders -> shop.api.legacy 'reads'"


def model(kit, text, name="model.c4"):
    f = kit.services.diagrams.arch_dir().joinpath(*name.split("/"))
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(text, encoding="utf-8", newline="\n")


def element(name, code):
    return f"    {name} = service '{name.title()}' {{\n      metadata {{ code '{code}' }}\n    }}\n"


def page(kit, rel, sources, kind=None):
    f = kit.root / "docs" / rel
    f.parent.mkdir(parents=True, exist_ok=True)
    head = f"---\ntitle: {rel}\n" + (f"type: {kind}\n" if kind else "")
    f.write_text(head + "x-sources:\n" + "".join(f"  - {s}\n" for s in sources) + "---\n# P\n\nText.\n",
                 encoding="utf-8")
    return f


def edit(kit, repo, rel, old, new):
    f = kit.ws / repo / rel
    text = f.read_text(encoding="utf-8")
    assert old in text
    f.write_text(text.replace(old, new), encoding="utf-8", newline="\n")


def stamps(c4):
    return json.loads(c4.FILE.read_text(encoding="utf-8"))


@pytest.fixture
def c4(kit):
    model(kit, MODEL)
    model(kit, FRAGMENT, "repos/api.c4")
    return importlib.import_module("lib.harness.freshness")


def test_each_element_gets_its_state(c4):
    st = c4.c4_states()["elements"]
    assert st["shop.api"]["state"] == "fresh"                       # its repo
    assert st["shop.api.orders"]["state"] == "fresh"
    assert st["shop.api.legacy"]["state"] == "broken"               # src/gone/ matches nothing
    assert st["shop.db"]["state"] == "no-evidence"
    assert st["shop.ghost"]["state"] == "no-evidence" and st["shop.ghost"]["confirmed"] is True
    assert st["shop.api.legacy"]["legacy_only"] is True
    assert st["shop.api.orders"]["legacy_only"] is False and st["shop.db"]["legacy_only"] is False
    assert [(a["kind"], a["result"]) for a in st["shop.api.legacy"]["anchors"]] == [("file", "fresh"),
                                                                                   ("folder", "missing")]
    assert (st["shop.api.orders"]["file"], st["shop.api.orders"]["line"]) == ("repos/api.c4", 3)


def test_stamps_live_under_their_own_key_and_stamping_again_changes_nothing(c4):
    assert c4.c4_stamp_all() > 0
    assert c4.c4_stamp_all() == 0
    data = stamps(c4)
    assert data["v"] == 1 and data["pages"] == {}
    orders = data["c4"]["elements"]["shop.api.orders"]
    assert set(orders["anchors"]) == {f"api:{API}#Api"}                   # only lines and symbols are fingerprinted
    assert orders["sha"] and orders["at"] and "by" not in orders


def test_a_symbol_anchor_goes_suspect_a_file_anchor_does_not(c4, kit):
    c4.c4_stamp_all()
    edit(kit, "api", API, COMMENT, CODE)
    assert c4.c4_states()["elements"]["shop.api.orders"]["state"] == "suspect"
    c4.c4_ack(["shop.api.orders"], by="ana")
    assert c4.c4_states()["elements"]["shop.api.orders"]["state"] == "fresh"
    assert stamps(c4)["c4"]["elements"]["shop.api.orders"]["by"] == "ana"


def test_ack_names_only_what_the_model_has(c4):
    assert c4.c4_ack(["shop.api.orders", "shop.nope", READS], by="ana") == ["shop.api.orders", READS]


def test_confirming_in_the_editor_stamps_again(c4, kit):
    c4.c4_stamp_all()
    edit(kit, "api", API, COMMENT, CODE)
    importlib.import_module("lib.c4edit").confirm(["shop.api.orders"], by="ana", today="2026-11-18")
    assert c4.c4_states()["elements"]["shop.api.orders"]["state"] == "fresh"   # its block changed: stamped again


def test_a_repo_not_cloned_here_is_unchecked(c4, kit):
    kit.common.rmtree(kit.ws / "api")                 # git objects are read-only: Windows refuses shutil.rmtree
    st = c4.c4_states()["elements"]
    assert st["shop.api.orders"]["state"] == "unchecked" and st["shop.api"]["state"] == "unchecked"


def test_an_anchor_first_seen_here_is_fingerprinted_then(c4, kit):
    backup = kit.ws / "api-away"
    (kit.ws / "api").rename(backup)
    c4.c4_stamp_all()                                 # stamped where api is not cloned: nothing to fingerprint
    assert stamps(c4)["c4"]["elements"]["shop.api.orders"]["anchors"] == {}
    backup.rename(kit.ws / "api")
    assert c4.c4_states()["elements"]["shop.api.orders"]["state"] == "fresh"
    edit(kit, "api", API, COMMENT, CODE)
    assert c4.c4_states()["elements"]["shop.api.orders"]["state"] == "suspect"


def test_a_repo_not_in_the_workspace_is_broken(c4, kit):
    model(kit, MODEL.replace(GHOST, GHOST + element("stray", "nope:src/A.java")))
    st = c4.c4_states()["elements"]["shop.stray"]
    assert st["state"] == "broken" and [a["result"] for a in st["anchors"]] == ["missing"]


def test_unreadable_entries_count_as_no_evidence_and_are_reported(c4, kit):
    model(kit, MODEL.replace(GHOST, GHOST + element("loose", "src/A.java")))
    st = c4.c4_states()["elements"]["shop.loose"]
    assert st["state"] == "no-evidence" and st["unreadable"] == ["src/A.java"] and st["anchors"] == []


def test_duplicate_relations_get_their_own_keys(c4):
    rels = c4.c4_states()["relations"]
    assert sorted(rels) == [READS, f"{READS} [2]"]
    r = rels[READS]
    assert (r["from"], r["to"], r["label"], r["own"], r["confirmed"]) == (
        "shop.api.orders", "shop.api.legacy", "reads", None, False)
    assert (r["file"], r["line"], rels[f"{READS} [2]"]["line"]) == ("repos/api.c4", 9, 10)


def test_relation_key_counts_repeats_in_order():
    from collections import Counter
    from lib.harness import freshness
    seen = Counter()
    rel = {"from": "a", "to": "b", "label": "calls"}
    assert [freshness.relation_key(rel, seen) for _ in range(3)] == ["a -> b 'calls'", "a -> b 'calls' [2]",
                                                                     "a -> b 'calls' [3]"]
    assert freshness.relation_key({"from": "a", "to": "b", "label": ""}, seen) == "a -> b ''"


def test_a_relation_is_checked_against_its_own_anchors(c4, kit):
    model(kit, FRAGMENT.replace("    orders -> legacy 'reads'\n    orders -> legacy 'reads'\n",
                                "    orders -> legacy 'reads' {\n"
                                f"      metadata {{ code 'api:{API}#Api' }}\n"
                                "    }\n"
                                "    legacy -> orders 'calls' {\n"
                                "      metadata { evidence 'src/gone.java' }\n"
                                "    }\n"
                                "    orders -> legacy 'writes' { #confirmed }\n"), "repos/api.c4")
    rels = c4.c4_states()["relations"]
    reads, calls = rels[READS], rels["shop.api.legacy -> shop.api.orders 'calls'"]
    assert reads["own"] == "fresh" and [a["kind"] for a in reads["anchors"]] == ["symbol"]
    assert calls["own"] == "broken" and calls["anchors"][0]["legacy"] is True       # api, from its `from`'s container
    writes = rels["shop.api.orders -> shop.api.legacy 'writes'"]
    assert writes["own"] is None and writes["confirmed"] is True


def test_a_renamed_element_is_stamped_again(c4, kit):
    c4.c4_stamp_all()
    edit(kit, "api", API, COMMENT, CODE)
    assert c4.c4_states()["elements"]["shop.api.orders"]["state"] == "suspect"
    model(kit, FRAGMENT.replace("orders", "checkout"), "repos/api.c4")
    st = c4.c4_states()
    assert "shop.api.orders" not in st["elements"] and st["elements"]["shop.api.checkout"]["state"] == "fresh"
    kept = stamps(c4)["c4"]
    assert "shop.api.orders" not in kept["elements"] and "shop.api.checkout" in kept["elements"]
    assert sorted(kept["relations"]) == ["shop.api.checkout -> shop.api.legacy 'reads'",
                                         "shop.api.checkout -> shop.api.legacy 'reads' [2]"]


def test_folder_and_glob_anchors_match_posix_paths(c4, kit):
    (kit.ws / "api" / "src" / "empty").mkdir()
    model(kit, MODEL.replace(GHOST, GHOST + element("shelf", "api:src/main/")
                             + element("pattern", "api:src/*/java/demo/*.java")
                             + element("hollow", "api:src/empty/")
                             + element("stray", "api:src/*/kotlin/*.kt")))
    st = c4.c4_states()["elements"]
    assert st["shop.shelf"]["state"] == "fresh" and st["shop.pattern"]["state"] == "fresh"
    assert st["shop.hollow"]["state"] == "broken" and st["shop.stray"]["state"] == "broken"


def test_a_model_that_does_not_parse_leaves_no_states_and_one_error(c4, kit, monkeypatch):
    c4.c4_stamp_all()
    model(kit, MODEL + "  oops {\n")
    monkeypatch.setattr(importlib.import_module("lib.c4edit"), "index", lambda *a, **k: 1 / 0)
    st = c4.c4_states()
    assert st["elements"] == {} and st["relations"] == {} and st["error"]
    assert "shop.api.orders" in stamps(c4)["c4"]["elements"]          # a model that does not parse drops no stamp


def test_no_model_no_states(kit):
    from lib.harness import freshness
    assert freshness.c4_states() == {"elements": {}, "relations": {}, "error": None}
    assert freshness.c4_stamp_all() == 0


def test_pages_follow_their_element(c4, kit):                   # spec §5.4
    page(kit, "flows/a.md", ["c4:shop.db"])                     # no evidence, not confirmed → suspect
    page(kit, "flows/b.md", ["c4:shop.ghost"])                  # vouched for by a person → fresh
    page(kit, "flows/c.md", ["c4:shop.api.orders"])
    page(kit, "flows/d.md", ["c4:shop.api.legacy"])             # broken → suspect
    c4.stamp_all()
    assert [c4.status(p)["state"] for p in ("flows/a.md", "flows/b.md", "flows/c.md", "flows/d.md")] == [
        "suspect", "fresh", "fresh", "suspect"]
    assert c4.status("flows/a.md")["changed"] == ["c4:shop.db"]


def test_adding_anchors_or_confirming_leaves_citing_pages_fresh(c4, kit):
    page(kit, "flows/a.md", ["c4:shop.db"])
    page(kit, "flows/b.md", ["c4:shop.ghost"])
    c4.stamp_all()
    assert c4.status("flows/a.md")["state"] == "suspect"
    with_code = MODEL.replace(DB, "    db = database 'Orders DB' {\n      #confirmed\n"
                                  f"      metadata {{ code 'api:{API}' }}\n    }}\n")
    model(kit, with_code)
    assert c4.status("flows/a.md")["state"] == "fresh"
    importlib.import_module("lib.c4edit").confirm(["shop.ghost"], by="ana", today="2026-11-18")
    assert "confirmed-by 'ana'" in kit.services.diagrams.arch_dir().joinpath("model.c4").read_text(encoding="utf-8")
    assert c4.status("flows/b.md")["state"] == "fresh"
    model(kit, with_code.replace("'Orders DB'", "'Order store'"))
    assert c4.status("flows/a.md")["state"] == "suspect"                # a new title still counts


def test_decisions_check_elements_for_existence_only(c4, kit):
    page(kit, "decisions/0001-orders-db.md", ["c4:shop.db"], kind="decision")
    c4.stamp_all()
    assert c4.status("decisions/0001-orders-db.md")["state"] == "fresh"      # no evidence, still not withheld
    model(kit, MODEL.replace(DB, "    db = database 'Orders DB' 'Keeps the orders'\n"))
    assert c4.status("decisions/0001-orders-db.md")["state"] == "fresh"      # a new text is no decision's concern
    model(kit, MODEL.replace(DB, ""))
    assert c4.status("decisions/0001-orders-db.md")["state"] == "stale"


def test_c4_sources_resolve_through_fragments(c4):
    assert c4.c4_exists("shop.api.orders") and c4.c4_exists("shop.db")
    assert not c4.c4_exists("shop.nope") and not c4.c4_exists("  ")


def test_stamps_from_the_current_kit_migrate(c4, kit):
    """A fresh.json written before v2 (no "v" in a c4 stamp): unchanged elements are re-stamped silently, once."""
    from lib.common import save_json
    page(kit, "flows/a.md", ["c4:shop.api"])
    page(kit, "flows/b.md", ["c4:shop.api"])
    old = c4._c4_lines("shop.api")
    assert old is not None
    v1 = {"h": c4._hash(c4._norm(old)), "n": len(c4._norm(old)), "k": "c4"}
    shas = {p: sha for p, (_, sha) in c4._pages().items()}
    save_json(c4.FILE, {"v": 1, "pages": {
        "flows/a.md": {"body_sha": shas["flows/a.md"], "at": "2026-11-01T10:00:00", "sources": {"c4:shop.api": v1}},
        "flows/b.md": {"body_sha": shas["flows/b.md"], "at": "2026-11-01T10:00:00",       # the element changed since
                       "sources": {"c4:shop.api": {**v1, "h": "0" * 16}}}}})
    for _ in range(2):
        assert c4.status("flows/a.md")["state"] == "fresh"
        assert c4.status("flows/b.md")["state"] == "suspect"
    pages = stamps(c4)["pages"]
    assert pages["flows/a.md"]["sources"]["c4:shop.api"]["v"] == 2
    assert pages["flows/a.md"]["sources"]["c4:shop.api"] == c4.fingerprint("c4:shop.api")
    assert "v" not in pages["flows/b.md"]["sources"]["c4:shop.api"]
