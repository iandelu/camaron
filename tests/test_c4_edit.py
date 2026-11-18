"""Editing and confirming the C4 model from the portal (S13): each change rewrites only the element's own block (or
one relation line), keeps everything else byte for byte, is refused before writing when it cannot be valid, and is
rolled back when LikeC4 rejects the result. Confirming removes #ai-draft, tags #confirmed and records who and when."""
from __future__ import annotations

import json, shutil, threading, urllib.error, urllib.request
from http.server import ThreadingHTTPServer

import pytest

from fixtures.host_tools import needs

needs_likec4 = needs("likec4")

MODEL = """// first look
model {
  user = actor 'User' 'Uses the shop' { #ai-draft }

  shop = system 'Shop' {
    orders = service 'Orders' {
      #ai-draft
      technology 'Java · Spring Boot'
      metadata { repo 'orders' }
      -> billing 'charges'
    }
    billing = service 'Billing'
    db = database 'PostgreSQL: shop' {
      #ai-draft #shared-db
      technology 'PostgreSQL'
    }
  }

  user -> shop.orders 'places orders'
  shop.orders -[sync]-> shop.db 'reads/writes'
}
"""
FRAGMENT = """model {
  extend shop.orders {
    api = component 'REST API' {
      #ai-draft
      description 'Endpoints for orders'
    }
  }
}
"""
VIEWS = """views {
  view index {
    include *
  }
  view shop_containers of shop {
    include *
  }
}
"""


@pytest.fixture
def arch(kit, monkeypatch):
    d = kit.services.diagrams.arch_dir()
    spec = (kit.kit_dir / "templates" / "docs" / "architecture" / "spec.c4").read_text(encoding="utf-8")
    for rel, text in {"likec4.config.json": '{"name": "shop"}', "spec.c4": spec, "model.c4": MODEL,
                      "views.c4": VIEWS, "repos/orders.c4": FRAGMENT}.items():
        f = d / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8", newline="\n")
    from lib import c4edit
    if not shutil.which("likec4"):
        monkeypatch.setattr(c4edit, "validate", lambda: (True, ""))
    return d


def lines_outside(text: str, start: int, end: int) -> list[str]:
    ls = text.splitlines()
    return ls[:start] + ls[end + 1:]


def test_the_index_reads_elements_fragments_and_relations(arch):
    from lib import c4edit
    idx = c4edit.index()
    orders = idx["elements"]["shop.orders"]
    assert (orders["kind"], orders["title"], orders["technology"]) == ("service", "Orders", "Java · Spring Boot")
    assert orders["tags"] == ["ai-draft"] and orders["metadata"] == {"repo": "orders"} and orders["file"] == "model.c4"
    assert idx["elements"]["user"]["description"] == "Uses the shop" and idx["elements"]["user"]["draft"]
    assert idx["elements"]["shop.db"]["tags"] == ["ai-draft", "shared-db"]
    api = idx["elements"]["shop.orders.api"]
    assert api["file"] == "repos/orders.c4" and api["description"] == "Endpoints for orders"
    rels = {(r["from"], r["to"], r["label"]) for r in idx["relations"]}
    assert rels == {("shop.orders", "shop.billing", "charges"), ("user", "shop.orders", "places orders"),
                    ("shop.orders", "shop.db", "reads/writes")}
    assert "service" in idx["kinds"] and "database" in idx["kinds"]


def test_an_edit_rewrites_only_that_element(arch):
    from lib import c4edit
    before = (arch / "model.c4").read_text(encoding="utf-8")
    el = c4edit.index()["elements"]["shop.orders"]
    c4edit.edit("shop.orders", title="Order service", technology="Kotlin", description="Takes the orders")
    after = (arch / "model.c4").read_text(encoding="utf-8")
    new = c4edit.index()["elements"]["shop.orders"]
    assert (new["title"], new["technology"], new["description"]) == ("Order service", "Kotlin", "Takes the orders")
    assert new["tags"] == ["ai-draft"] and new["metadata"] == {"repo": "orders"}
    assert lines_outside(before, el["start"], el["end"]) == lines_outside(after, new["start"], new["end"])
    assert "      -> billing 'charges'" in after                                  # what the block holds is kept
    assert (arch / "repos" / "orders.c4").read_text(encoding="utf-8") == FRAGMENT


def test_a_one_line_element_becomes_a_block_when_it_needs_one(arch):
    from lib import c4edit
    c4edit.edit("user", technology="Browser")
    user = c4edit.index()["elements"]["user"]
    assert (user["title"], user["description"], user["technology"], user["tags"]) == \
        ("User", "Uses the shop", "Browser", ["ai-draft"])
    c4edit.edit("shop.billing", description="Charges cards")
    assert c4edit.index()["elements"]["shop.billing"]["description"] == "Charges cards"


def test_quotes_in_values_survive(arch):
    from lib import c4edit
    c4edit.edit("shop.billing", title="Billing's API", description='The "money" part')
    b = c4edit.index()["elements"]["shop.billing"]
    assert (b["title"], b["description"]) == ("Billing's API", 'The "money" part')


@pytest.mark.parametrize("change, error", [
    ({"title": "two\nlines"}, ValueError),
    ({"kind": "spaceship"}, ValueError),
    ({"title": ""}, ValueError),
])
def test_impossible_edits_are_refused_before_writing(arch, change, error):
    from lib import c4edit
    before = (arch / "model.c4").read_text(encoding="utf-8")
    with pytest.raises(error):
        c4edit.edit("shop.orders", **change)
    assert (arch / "model.c4").read_text(encoding="utf-8") == before
    with pytest.raises(KeyError):
        c4edit.edit("shop.nope", title="x")


def test_a_change_likec4_rejects_is_rolled_back(arch, monkeypatch):
    from lib import c4edit
    before = (arch / "model.c4").read_text(encoding="utf-8")
    monkeypatch.setattr(c4edit, "validate", lambda: (False, "Line 7: something broke"))
    with pytest.raises(c4edit.C4Error, match="something broke"):
        c4edit.edit("shop.orders", technology="Kotlin")
    assert (arch / "model.c4").read_text(encoding="utf-8") == before


def test_confirm_tags_the_element_and_records_who_and_when(arch):
    from lib import c4edit
    c4edit.confirm(["shop.orders", "shop.db"], by="ana", today="2026-10-23")
    els = c4edit.index()["elements"]
    assert els["shop.orders"]["tags"] == ["confirmed"] and els["shop.db"]["tags"] == ["shared-db", "confirmed"]
    assert els["shop.orders"]["metadata"] == {"repo": "orders", "confirmed-by": "ana", "confirmed-at": "2026-10-23"}
    assert els["shop.orders"]["confirmed"] and not els["shop.orders"]["draft"]
    text = (arch / "model.c4").read_text(encoding="utf-8")
    c4edit.confirm(["shop.orders"], by="ana", today="2026-10-23")                    # idempotent
    assert (arch / "model.c4").read_text(encoding="utf-8") == text
    assert els["user"]["draft"]                                                       # others untouched


def test_confirm_a_whole_view(arch):
    from lib import c4edit
    shown = c4edit.view_elements("shop_containers")
    assert set(shown) == {"shop", "shop.orders", "shop.billing", "shop.db"}
    assert set(c4edit.view_elements("index")) == {"user", "shop"}
    done = c4edit.confirm_view("shop_containers", by="ana", today="2026-10-23")
    els = c4edit.index()["elements"]
    assert set(done) == {"shop", "shop.orders", "shop.billing", "shop.db"}
    assert all(els[f]["confirmed"] for f in done) and els["user"]["draft"] and els["shop.orders.api"]["draft"]


def test_relations_are_added_and_removed(arch):
    from lib import c4edit
    c4edit.add_relation("shop.billing", "shop.db", "stores payments", kind="async")
    text = (arch / "model.c4").read_text(encoding="utf-8")
    assert "  shop.billing -[async]-> shop.db 'stores payments'\n}" in text
    rels = {(r["from"], r["to"], r["label"]) for r in c4edit.index()["relations"]}
    assert ("shop.billing", "shop.db", "stores payments") in rels
    c4edit.remove_relation("shop.orders", "shop.billing", "charges")                   # one declared inside a block
    c4edit.remove_relation("user", "shop.orders", "places orders")
    after = (arch / "model.c4").read_text(encoding="utf-8")
    assert "-> billing 'charges'" not in after and "places orders" not in after
    with pytest.raises(ValueError):
        c4edit.add_relation("shop.billing", "shop.nowhere", "x")
    with pytest.raises(ValueError):
        c4edit.add_relation("shop.billing", "shop.db", "x", kind="teleport")
    with pytest.raises(KeyError):
        c4edit.remove_relation("user", "shop.db", "never declared")


@needs_likec4
def test_the_edited_model_stays_valid_for_likec4(arch):
    from lib import c4edit
    c4edit.edit("user", technology="Browser")
    c4edit.edit("shop.billing", title="Billing's API", description='The "money" part')
    c4edit.confirm_view("shop_containers", by="ana", today="2026-10-23")
    c4edit.add_relation("shop.billing", "shop.db", "stores payments", kind="async")
    ok, msg = c4edit.validate()
    assert ok, msg


# ---------- the portal API ----------
@pytest.fixture
def portal(kit, arch):
    srv = ThreadingHTTPServer(("127.0.0.1", 0), kit.serve.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def call(url, body=None, header=True):
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body is not None else None,
                                 method="POST" if body is not None else "GET",
                                 headers={"Content-Type": "application/json", **({"X-Camarones": "1"} if header else {})})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def test_the_portal_reads_edits_and_confirms_a_view(kit, portal):
    code, v = call(f"{portal}/api/c4/view?id=shop_containers")
    assert code == 200 and {e["fqn"] for e in v["elements"]} == {"shop", "shop.orders", "shop.billing", "shop.db"}
    orders = next(e for e in v["elements"] if e["fqn"] == "shop.orders")
    assert {"to": "shop.billing", "label": "charges", "kind": None} in [
        {k: r[k] for k in ("to", "label", "kind")} for r in orders["out"]]
    assert "service" in v["kinds"] and v["editable"] is True
    code, el = call(f"{portal}/api/c4/element", {"fqn": "shop.orders", "technology": "Kotlin"})
    assert code == 200 and el["technology"] == "Kotlin"
    assert call(f"{portal}/api/c4/element", {"fqn": "shop.orders", "title": "a\nb"})[0] == 400
    assert call(f"{portal}/api/c4/element", {"fqn": "shop.orders", "technology": "x"}, header=False)[0] == 403
    code, r = call(f"{portal}/api/c4/confirm", {"view": "shop_containers", "by": "ana"})
    assert code == 200 and set(r["confirmed"]) == {"shop", "shop.orders", "shop.billing", "shop.db"}
    code, r = call(f"{portal}/api/c4/relation", {"action": "add", "from": "shop.billing", "to": "shop.db",
                                                 "label": "stores payments"})
    assert code == 200
    assert call(f"{portal}/api/c4/relation", {"action": "remove", "from": "user", "to": "shop.db", "label": "x"})[0] == 404


# ---------- removing an element ----------
PICKED = """views {
  view index {
    include *
  }
  view shop_containers of shop {
    include *
  }
  view picked {
    include user, shop.billing,
      shop.orders
    exclude shop.billing -> *
  }
  dynamic view checkout {
    user -> shop.orders 'buys'
    shop.orders -> shop.billing 'charges'
  }
}
"""


def test_removing_an_element_takes_its_children_relations_and_view_mentions(arch):
    from lib import c4edit
    (arch / "views.c4").write_text(PICKED, encoding="utf-8", newline="\n")
    r = c4edit.remove_element("shop.billing")
    assert r["removed"] == ["shop.billing"]
    idx = c4edit.index()
    assert "shop.billing" not in idx["elements"] and "shop.orders" in idx["elements"]
    assert all("shop.billing" not in (x["from"], x["to"]) for x in idx["relations"])
    model = (arch / "model.c4").read_text(encoding="utf-8")
    assert "billing" not in model and "    orders = service 'Orders' {" in model
    views = (arch / "views.c4").read_text(encoding="utf-8")
    assert "    include user,\n      shop.orders\n" in views and "exclude" not in views
    assert "    user -> shop.orders 'buys'\n  }" in views and "charges" not in views

    r = c4edit.remove_element("shop.orders")                       # a fragment's children go with it
    assert r["removed"] == ["shop.orders", "shop.orders.api"]
    idx = c4edit.index()
    assert not [f for f in idx["elements"] if f.startswith("shop.orders")] and not idx["relations"]
    assert "REST API" not in (arch / "repos" / "orders.c4").read_text(encoding="utf-8")
    views = (arch / "views.c4").read_text(encoding="utf-8")
    assert "    include user\n" in views and "buys" not in views
    with pytest.raises(KeyError):
        c4edit.remove_element("shop.orders")


def test_an_element_a_view_is_scoped_to_is_not_removed(arch):
    from lib import c4edit
    before = {f: f.read_text(encoding="utf-8") for f in arch.rglob("*.c4")}
    with pytest.raises(ValueError, match="shop_containers"):
        c4edit.remove_element("shop")
    assert {f: f.read_text(encoding="utf-8") for f in arch.rglob("*.c4")} == before


def test_the_portal_removes_an_element(kit, portal):
    code, r = call(f"{portal}/api/c4/remove", {"fqn": "shop.db"})
    assert code == 200 and r["removed"] == ["shop.db"]
    assert call(f"{portal}/api/c4/remove", {"fqn": "shop.db"})[0] == 404
    assert call(f"{portal}/api/c4/remove", {"fqn": "shop"})[0] == 400


LISTED = MODEL.replace("      metadata { repo 'orders' }",
                       "      metadata {\n        repo 'orders'\n        code ['orders:src/A.java', 'orders:src/b/']\n      }")


def test_list_metadata_is_read_and_kept_on_confirm(arch):
    from lib import c4edit
    (arch / "model.c4").write_text(LISTED, encoding="utf-8", newline="\n")
    assert c4edit.index()["elements"]["shop.orders"]["metadata"]["code"] == ["orders:src/A.java", "orders:src/b/"]
    c4edit.confirm(["shop.orders"], by="ana", today="2026-11-18")
    meta = c4edit.index()["elements"]["shop.orders"]["metadata"]
    assert meta["code"] == ["orders:src/A.java", "orders:src/b/"] and meta["confirmed-by"] == "ana"


def test_relation_metadata_and_tags_are_read(arch):
    from lib import c4edit
    text = MODEL.replace("      -> billing 'charges'\n",
                         "      -> billing 'charges' {\n        #confirmed\n        metadata { code 'orders:src/Pay.java#L3' }\n      }\n")
    (arch / "model.c4").write_text(text, encoding="utf-8", newline="\n")
    rel = next(r for r in c4edit.index()["relations"] if r["to"] == "shop.billing")
    assert rel["metadata"] == {"code": "orders:src/Pay.java#L3"} and rel["tags"] == ["confirmed"]


def _with_orders_meta(arch, body):
    from lib import c4edit
    text = MODEL.replace("      metadata { repo 'orders' }", f"      metadata {{ {body} }}")
    (arch / "model.c4").write_text(text, encoding="utf-8", newline="\n")
    return c4edit.index()


def test_list_metadata_trailing_comma_and_apostrophe(arch):
    meta = _with_orders_meta(arch, "code ['a', 'b',]")["elements"]["shop.orders"]["metadata"]
    assert meta["code"] == ["a", "b"]
    meta = _with_orders_meta(arch, 'code ["it\'s here"]')["elements"]["shop.orders"]["metadata"]
    assert meta["code"] == ["it's here"]


def _relation(arch, replacement):
    from lib import c4edit
    text = MODEL.replace("      -> billing 'charges'\n", replacement)
    (arch / "model.c4").write_text(text, encoding="utf-8", newline="\n")
    return next(r for r in c4edit.index()["relations"] if r["to"] == "shop.billing")


def test_relation_list_metadata_is_read(arch):
    rel = _relation(arch, "      -> billing 'charges' {\n        metadata {\n          code ['a:x', 'b:y']\n        }\n      }\n")
    assert rel["metadata"] == {"code": ["a:x", "b:y"]}


def test_one_line_relation_block_is_read(arch):
    rel = _relation(arch, "      -> billing 'charges' { metadata { code 'api:src/A.java#L4' } }\n")
    assert rel["metadata"] == {"code": "api:src/A.java#L4"} and rel["tags"] == []
    rel = _relation(arch, "      -> billing 'charges' { #confirmed }\n")
    assert rel["tags"] == ["confirmed"] and rel["metadata"] == {}


def test_relation_without_block_has_no_metadata(arch):
    from lib import c4edit
    (arch / "model.c4").write_text(MODEL, encoding="utf-8", newline="\n")
    assert all(r["metadata"] == {} and r["tags"] == [] for r in c4edit.index()["relations"])


TWO_BLOCKS = """model {
  shop = system 'Shop' {
    api = service 'Api' {
      #ai-draft
      metadata { repo 'api' }
      metadata { code ['api:pom.xml'] }
    }
  }
}
"""


def test_repeated_metadata_blocks_are_read_as_one_and_a_confirm_leaves_one_block(arch):
    from lib import c4edit
    (arch / "repos" / "orders.c4").unlink()
    (arch / "model.c4").write_text(TWO_BLOCKS, encoding="utf-8", newline="\n")
    assert c4edit.index()["elements"]["shop.api"]["metadata"] == {"repo": "api", "code": ["api:pom.xml"]}
    c4edit.confirm(["shop.api"], by="ana", today="2026-10-23")
    text = (arch / "model.c4").read_text(encoding="utf-8")
    assert text.count("metadata") == 1
    assert c4edit.index()["elements"]["shop.api"]["metadata"] == {
        "repo": "api", "code": ["api:pom.xml"], "confirmed-by": "ana", "confirmed-at": "2026-10-23"}
