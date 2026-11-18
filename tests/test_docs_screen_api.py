"""What the desktop app's Docs screen reads from the project server beyond the portal's own routes: the questions nobody
could answer (GET /api/misses), the same list the KPIs dashboard carries, without the rest of the dashboard."""
from __future__ import annotations

from datetime import datetime

from test_portal_actions import get, server  # noqa: F401 — the portal server fixture

NOW = datetime(2026, 10, 20, 11, 0)


def test_the_misses_are_the_questions_no_page_answered(wired, server):
    u = wired.usage
    u.record("portal:ask", channel="human", hit=False, query="how are refunds made", now=NOW)
    u.record("portal:ask", channel="human", hit=False, query="How are refunds made", now=NOW)
    u.record("mcp:search", channel="agent", hit=False, query="who owns billing", now=NOW)
    u.record("portal:ask", channel="human", hit=True, query="checkout flow", now=NOW)
    rows = get(f"{server}/api/misses")["misses"]
    assert rows == [{"q": "who owns billing", "n": 1, "last": "2026-10-20"},
                    {"q": "how are refunds made", "n": 2, "last": "2026-10-20"}]
    assert rows == u.misses()


def test_no_misses_is_an_empty_list(wired, server):
    assert get(f"{server}/api/misses") == {"misses": []}
