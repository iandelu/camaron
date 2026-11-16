"""Page writes to cam-docs (the portal's save, new page and confirm; the MCP's propose_edit; agent sessions writing files
directly). Two writers on one page never lose each other's change silently: every read-check-write the kit does holds
the page's lock, and a writer that loaded the page earlier (the portal) says which version it loaded, so a page that
changed underneath (an agent, another tab) is a 409 instead of being overwritten."""
from __future__ import annotations

import importlib
import json
import threading
import time

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


# ---------- two writers on one page ----------
def test_two_writers_on_one_page_the_save_from_an_old_version_is_refused(kit, portal):
    """The portal opens the page, an agent session rewrites the file meanwhile, the portal saves: last writer wins no
    more. The save is a 409 carrying the version the file has now, the agent's text stays, and a save made from that
    version goes through (the person chose to save over it)."""
    f = page(kit)
    _, loaded = call(portal, "GET", "/api/doc?path=flows/pay.md")
    agent = PAGE.replace("Pay once.", "Pay once; retry twice.")
    f.write_text(agent, encoding="utf-8", newline="\n")                     # an agent session, straight to the file

    code, d = call(portal, "POST", "/api/doc", {"path": "flows/pay.md", "raw": "# Mine\n", "sha": loaded["sha"]})
    assert code == 409 and "changed" in d["error"]
    assert f.read_text(encoding="utf-8") == agent
    assert d["sha"] == call(portal, "GET", "/api/doc?path=flows/pay.md")[1]["sha"] != loaded["sha"]

    code, d = call(portal, "POST", "/api/doc", {"path": "flows/pay.md", "raw": "# Mine\n", "sha": d["sha"]})
    assert code == 200 and f.read_text(encoding="utf-8") == "# Mine\n"


def test_a_save_from_the_version_on_disk_goes_through(kit, portal):
    f = page(kit)
    _, loaded = call(portal, "GET", "/api/doc?path=flows/pay.md")
    code, d = call(portal, "POST", "/api/doc", {"path": "flows/pay.md", "raw": "# Mine\n", "sha": loaded["sha"]})
    assert code == 200 and f.read_text(encoding="utf-8") == "# Mine\n" and d["sha"] != loaded["sha"]


def test_the_version_covers_the_front_matter(kit, portal):
    """A confirmation landing while a person edits changes only the front matter: saving over it would wipe it."""
    f = page(kit)
    _, loaded = call(portal, "GET", "/api/doc?path=flows/pay.md")
    kit.services.doc_review.confirm([str(f)], "ana")
    code, _ = call(portal, "POST", "/api/doc", {"path": "flows/pay.md", "raw": PAGE + "More.\n", "sha": loaded["sha"]})
    assert code == 409 and "x-confirmed" in f.read_text(encoding="utf-8")


def test_a_save_to_a_translation_checks_the_translation(kit, portal):
    page(kit)
    t = page(kit, "i18n/es/flows/pay.md", "---\ntitle: Pagar\n---\n# Pagar\n")
    _, loaded = call(portal, "GET", "/api/doc?path=flows/pay.md&lang=es")
    t.write_text("# Pagar (agente)\n", encoding="utf-8", newline="\n")
    code, _ = call(portal, "POST", "/api/doc",
                   {"path": "flows/pay.md", "lang": "es", "raw": "# Mio\n", "sha": loaded["sha"]})
    assert code == 409 and t.read_text(encoding="utf-8") == "# Pagar (agente)\n"


def test_a_save_that_names_no_version_still_saves(kit, portal):
    """An older client or a script: no check, but the write still holds the page's lock."""
    f = page(kit)
    assert call(portal, "POST", "/api/doc", {"path": "flows/pay.md", "raw": "# Theirs\n"})[0] == 200
    assert f.read_text(encoding="utf-8") == "# Theirs\n"


def test_a_confirm_of_a_body_that_changed_since_it_was_read_is_refused(kit, portal):
    f = page(kit)
    _, loaded = call(portal, "GET", "/api/doc?path=flows/pay.md")
    f.write_text(PAGE.replace("Pay once.", "Pay never."), encoding="utf-8", newline="\n")
    code, d = call(portal, "POST", "/api/confirm", {"path": "flows/pay.md", "by": "ana", "body_sha": loaded["body_sha"]})
    assert code == 409 and "x-confirmed" not in f.read_text(encoding="utf-8")
    assert d["body_sha"] != loaded["body_sha"]
    code, d = call(portal, "POST", "/api/confirm", {"path": "flows/pay.md", "by": "ana", "body_sha": d["body_sha"]})
    assert code == 200 and d["trust"] == "confirmed"


def test_the_review_queue_says_which_body_each_page_has(kit, portal):
    page(kit)
    _, loaded = call(portal, "GET", "/api/doc?path=flows/pay.md")
    _, st = call(portal, "GET", "/api/status?check=0")
    assert next(r for r in st["queue"] if r["path"] == "flows/pay.md")["body_sha"] == loaded["body_sha"]


def test_a_portal_save_writes_unix_line_endings_on_every_os(kit, portal, monkeypatch):
    from test_frontmatter import windows_newlines
    f = page(kit)
    windows_newlines(monkeypatch)
    assert call(portal, "POST", "/api/doc", {"path": "flows/pay.md", "raw": "# A\n\nB\n"})[0] == 200
    assert f.read_bytes() == b"# A\n\nB\n"


# ---------- one writer at a time ----------
def held_while(kit, f, write, changes=True):
    """Hold the page's lock in this thread while `write` runs in another one: nothing lands until it is released."""
    before, out = f.read_text(encoding="utf-8"), {}
    with kit.services.docs.page_lock(f):
        t = threading.Thread(target=lambda: out.setdefault("r", write()), daemon=True)
        t.start()
        time.sleep(0.6)
        assert f.read_text(encoding="utf-8") == before, "a writer did not wait for the page's lock"
    t.join(20)
    assert not t.is_alive()
    if changes:
        assert f.read_text(encoding="utf-8") != before
    return out.get("r")


def test_a_portal_save_waits_for_the_page_lock(kit, portal):
    f = page(kit)
    code, _ = held_while(kit, f, lambda: call(portal, "POST", "/api/doc", {"path": "flows/pay.md", "raw": "# Mine\n"}))
    assert code == 200


def test_a_confirm_waits_for_the_page_lock(kit):
    f = page(kit)
    held_while(kit, f, lambda: kit.services.doc_review.confirm([str(f)], "ana"))
    assert "x-confirmed" in f.read_text(encoding="utf-8")


def test_propose_edit_waits_for_the_page_lock(kit):
    mcp = importlib.import_module("lib.mcp")
    f = page(kit)
    out = held_while(kit, f, lambda: mcp.propose_edit("flows/pay.md", "Pay twice.", section="steps"))
    assert "applied" in out and "Pay twice." in f.read_text(encoding="utf-8")


def test_a_page_lock_held_too_long_is_a_409_busy(kit, portal, monkeypatch):
    monkeypatch.setattr("lib.adapters.stores.doc_store.PAGE_LOCK_WAIT", 0.3)
    f = page(kit)
    code, d = held_while(kit, f, lambda: call(portal, "POST", "/api/doc", {"path": "flows/pay.md", "raw": "# Mine\n"}),
                         changes=False)
    assert code == 409 and "try again" in d["error"] and f.read_text(encoding="utf-8") == PAGE


def test_the_page_locks_live_in_the_cache_outside_git(kit):
    f = page(kit)
    with kit.services.docs.page_lock(f) as lock:
        assert lock.path.parent == kit.root / ".camarones" / ".cache" / "locks" / "pages"
        assert lock.path.exists()
    assert not lock.path.exists()


def test_a_page_and_its_translation_have_their_own_locks(kit):
    f, t = page(kit), page(kit, "i18n/es/flows/pay.md", "# Pagar\n")
    got = []

    def other():
        with kit.services.docs.page_lock(t):
            got.append(True)
    with kit.services.docs.page_lock(f):
        th = threading.Thread(target=other)
        th.start()
        th.join(5)
    assert got == [True]


def test_propose_edit_decides_on_the_page_as_it_is_under_the_lock(kit, monkeypatch):
    """The trust row is read before the lock: a person confirming in between must not see the agent rewrite the page
    they just confirmed. The agent's text becomes a proposal."""
    mcp = importlib.import_module("lib.mcp")
    f = page(kit)
    stale = mcp._rows()                                     # read while the page was still a draft
    kit.services.doc_review.confirm([str(f)], "ana")
    confirmed = f.read_text(encoding="utf-8")
    monkeypatch.setattr(mcp, "_rows", lambda: stale)
    out = mcp.propose_edit("flows/pay.md", "Pay twice.", section="steps", reason="retries")
    assert "waits for review" in out and f.read_text(encoding="utf-8") == confirmed


def test_two_threads_editing_sections_of_one_draft_lose_nothing(kit, monkeypatch):
    mcp = importlib.import_module("lib.mcp")
    f = page(kit)
    real_split = mcp.frontmatter.split_fm

    def slow_split(text):                                   # widen the read-to-write window a racing writer needs
        time.sleep(0.05)
        return real_split(text)
    monkeypatch.setattr("lib.domain.docs.frontmatter.split_fm", slow_split)

    def edits(section, word):
        for i in range(4):
            mcp.propose_edit("flows/pay.md", f"{word} {i}.", section=section)
    threads = [threading.Thread(target=edits, args=a) for a in (("steps", "Step"), ("data-touched", "Table"))]
    for t in threads:
        t.start()
    for t in threads:
        t.join(60)
    text = f.read_text(encoding="utf-8")
    assert "Step 3." in text and "Table 3." in text


def test_add_feedback_waits_for_the_feedback_lock(kit):
    from lib.core.locks import FileLock
    store = importlib.import_module("lib.adapters.stores.doc_store")
    done = []
    with FileLock(store.FEEDBACK_LOCK):
        t = threading.Thread(target=lambda: done.append(kit.services.docs.add_feedback("docs/flows/pay.md", "Hi", "ana")))
        t.start()
        time.sleep(0.4)
        assert not done
    t.join(10)
    assert done and "Hi" in store.FEEDBACK.read_text(encoding="utf-8")
