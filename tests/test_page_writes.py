"""Page writes to cam-docs (the portal's save, new page and confirm; the MCP's propose_edit; agent sessions writing files
directly). Two writers on one page never lose each other's change silently: every read-check-write the kit does holds
the page's lock, and a writer that loaded the page earlier (the portal) says which version it loaded, so a page that
changed underneath (an agent, another tab) is a 409 instead of being overwritten."""
from __future__ import annotations

import json

import pytest

from fixtures.http_probe import arm, request, serving

PAGE = "---\ntitle: Pay\n---\n# Pay\n\n> **TL;DR:** Pay once.\n\n## Steps\nPay once.\n\n## Data touched\nThe `orders` table.\n"


def page(kit, rel="flows/pay.md", text=PAGE):
    f = kit.root / "docs" / rel
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(text, encoding="utf-8", newline="\n")
    return f


def call(base, method, path, body=None):
    status, _, raw = request(base, method, path, json.dumps(body).encode() if body is not None else None)
    return status, json.loads(raw or b"{}")


@pytest.fixture
def portal(kit, monkeypatch):
    arm(monkeypatch)
    with serving(kit.serve.Handler) as base:
        yield base


# ---------- what the portal does today (characterization) ----------
def test_the_portal_saves_a_page_and_answers_with_it(kit, portal):
    f = page(kit)
    code, d = call(portal, "GET", "/api/doc?path=flows/pay.md")
    assert code == 200 and d["raw"] == PAGE
    code, d = call(portal, "POST", "/api/doc", {"path": "flows/pay.md", "raw": PAGE.replace("Pay once.", "Pay twice.")})
    assert code == 200 and "Pay twice." in d["raw"]
    assert f.read_text(encoding="utf-8") == PAGE.replace("Pay once.", "Pay twice.")


def test_a_saved_page_ends_with_a_newline(kit, portal):
    f = page(kit)
    assert call(portal, "POST", "/api/doc", {"path": "flows/pay.md", "raw": "# Pay"})[0] == 200
    assert f.read_text(encoding="utf-8") == "# Pay\n"


def test_a_save_to_a_page_the_docs_do_not_know_is_refused(kit, portal):
    page(kit)
    assert call(portal, "POST", "/api/doc", {"path": "flows/nope.md", "raw": "# x"})[0] == 400
    assert not (kit.root / "docs" / "flows" / "nope.md").exists()


def test_a_new_page_is_created_owned_by_a_person_and_refused_when_it_exists(kit, portal):
    code, d = call(portal, "POST", "/api/new", {"path": "guides/howto.md", "title": "How to"})
    assert code == 200 and d["path"] == "guides/howto.md" and "x-owner: human" in d["raw"]
    code, d = call(portal, "POST", "/api/new", {"path": "guides/howto.md", "title": "Again"})
    assert code == 400 and "already exists" in d["error"]


def test_the_portal_confirms_a_page(kit, portal):
    page(kit)
    code, d = call(portal, "POST", "/api/confirm", {"path": "flows/pay.md", "by": "ana"})
    assert code == 200 and d["trust"] == "confirmed" and d["confirmed"]["by"]
