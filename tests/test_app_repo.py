"""GET /api/app/repo and /api/app/repos: one repo's dashboard and every repo's card, from the health snapshot, the repo's
facts, freshness, the wikis, the C4 model, the board and the decisions."""
from __future__ import annotations

import importlib, json, shutil, threading, urllib.error, urllib.request
from http.server import ThreadingHTTPServer

import pytest

TOKEN = "repo-tok"
KEYS = {"name", "cloned", "state", "at", "head", "stack", "build", "sonar", "trend", "activity", "libs", "docs", "wiki",
        "c4", "graph", "work", "adrs"}


@pytest.fixture
def app(wired, monkeypatch):
    monkeypatch.setattr("lib.interfaces.http.server.APP_TOKEN", TOKEN)
    srv = ThreadingHTTPServer(("127.0.0.1", 0), wired.serve.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def get(url, token=TOKEN):
    req = urllib.request.Request(url, headers={"X-Camarones": "1", **({"X-Camaron-Token": token} if token else {})})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


@pytest.fixture
def dash(wired, monkeypatch):
    mod = importlib.import_module("lib.app.repo_dashboard")
    monkeypatch.setattr(importlib.import_module("lib.kanban.ops"), "list_items", lambda **kw: {"cards": []})
    monkeypatch.setattr(importlib.import_module("lib.adr"), "list_adrs", lambda: [])
    monkeypatch.setattr(importlib.import_module("lib.c4edit"), "index", lambda: {"elements": {}, "relations": []})
    monkeypatch.setattr(importlib.import_module("lib.harness.freshness"), "by_repo", lambda: {})
    return mod


def snapshot(kit, repos, **extra):
    health = importlib.import_module('lib.health')
    kit.common.save_json(health.SNAPSHOT, {"v": 1, "at": "2026-11-18T10:00:00Z", "repos": repos,
                                              "repo_state": extra.pop("repo_state", {}), **extra})


def test_the_repo_page_with_sonar_figures(wired, dash):
    server = {"gate": "ERROR", "coverage": 41.0, "bugs": 12, "vulnerabilities": 2, "debt_minutes": 1960,
              "at": "2026-11-18T09:00:00Z"}
    snapshot(wired, {"api": {"cloned": True, "sonar": {"used": True, "link": "https://s/x", "server": server}}},
             repo_state={"api": "bad"})
    r = dash.repo("api")
    assert r["state"] == "bad" and r["at"] == "2026-11-18T10:00:00Z"
    assert r["sonar"] == {"source": "sonar", "gate": "ERROR", "coverage": 41.0, "coverageSource": "sonar",
                          "coverageAt": "2026-11-18T09:00:00Z", "bugs": 12, "vulnerabilities": 2, "debtMinutes": 1960,
                          "link": "https://s/x", "host": "", "connect": False, "error": None}


def test_without_sonar_the_estimate_reads_the_report(wired, dash):
    snapshot(wired, {"api": {"cloned": True, "sonar": {"used": False},
                             "coverage": {"percent": 64.0, "source": "report", "at": "2026-11-15"}}})
    s = dash.repo("api")["sonar"]
    assert (s["source"], s["coverage"], s["coverageSource"], s["gate"], s["bugs"]) == ("estimated", 64.0, "report", None, None)


def test_the_trend_is_the_last_8_figures(wired, dash):
    rows = [{"at": f"d{i:02d}", "repos": {"api": float(i)}} for i in range(10)]
    rows.insert(4, {"at": "x", "repos": {"web": 1.0}})
    health = importlib.import_module('lib.health')
    health.HISTORY.parent.mkdir(parents=True, exist_ok=True)
    health.HISTORY.write_text("\n".join(map(json.dumps, rows)) + "\n", encoding="utf-8")
    t = dash.repo("api")["trend"]
    assert [p["coverage"] for p in t] == [float(i) for i in range(2, 10)]


def test_work_counts_cards_by_column_and_lists_its_adrs(wired, dash, monkeypatch):
    cards = [{"status": "Backlog", "repos": ["api"]}, {"status": "Done", "repos": ["api", "web"]}]
    monkeypatch.setattr(importlib.import_module("lib.kanban.ops"), "list_items", lambda **kw: {"cards": cards})
    adrs = [{"id": "0002", "title": "B", "chip": "x", "status": "accepted", "repos": ["web"]},
            {"id": "0001", "title": "A", "chip": "y", "status": "proposed", "repos": ["api"]}]
    monkeypatch.setattr(importlib.import_module("lib.adr"), "list_adrs", lambda: adrs)
    r = dash.repo("api")
    assert r["work"] == {"columns": [{"status": s, "n": n} for s, n in
                                     [("Backlog", 1), ("Ready", 0), ("In Progress", 0), ("In Review", 0), ("Done", 1), ("Blocked", 0)]],
                         "total": 2}
    assert [a["id"] for a in r["adrs"]] == ["0001"]


def test_the_mini_c4_is_what_calls_it_and_what_it_calls(wired, dash, monkeypatch):
    c4 = importlib.import_module("lib.c4edit")
    els = {"browser": {"title": "Browser"}, "sys.api": {"title": "API", "technology": "Java", "metadata": {"repo": "api"}},
           "sys.db": {"title": "DB"}}
    rels = [{"from": "browser", "to": "sys.api", "label": "", "kind": ""}, {"from": "sys.api", "to": "sys.db"}]
    monkeypatch.setattr(c4, "index", lambda: {"elements": els, "relations": rels})
    r = dash.repo("api")["c4"]
    assert r["in"] == [{"fqn": "browser", "title": "Browser"}] and r["out"] == [{"fqn": "sys.db", "title": "DB"}]
    assert dash.repo("web")["c4"] is None


def test_a_repo_not_cloned(wired, dash):
    shutil.rmtree(wired.ws / "worker")
    r = dash.repo("worker")
    assert r["cloned"] is False and r["head"] is None and r["activity"] is None and r["stack"] == []


def test_no_snapshot_yet(wired, dash, monkeypatch):
    cards = [{"status": "Ready", "repos": ["api"]}]
    monkeypatch.setattr(importlib.import_module("lib.kanban.ops"), "list_items", lambda **kw: {"cards": cards})
    r = dash.repo("api")
    assert (r["state"], r["sonar"], r["at"], r["trend"]) == (None, None, None, [])
    assert r["work"]["total"] == 1


def test_a_failed_sonar_block(wired, dash):
    snapshot(wired, {"api": {"cloned": True, "sonar": {"error": "sin conexión"}}})
    assert dash.repo("api")["sonar"] is None
    snapshot(wired, {"api": {"cloned": True, "sonar": {"used": True, "error": "token no válido", "server": {"gate": "OK"}}}})
    s = dash.repo("api")["sonar"]
    assert s["source"] == "sonar" and s["error"] == "token no válido"


def test_one_failing_source_nulls_only_its_block(wired, dash, monkeypatch):
    def boom():
        raise RuntimeError("x")
    monkeypatch.setattr(importlib.import_module("lib.adr"), "list_adrs", boom)
    monkeypatch.setattr(importlib.import_module("lib.harness.freshness"), "by_repo", boom)
    r = dash.repo("api")
    assert r["adrs"] == [] and r["docs"] is None and r["work"]["total"] == 0


def test_the_routes(app, wired, monkeypatch):
    monkeypatch.setattr(importlib.import_module("lib.harness.freshness"), "by_repo", lambda: {})
    code, body = get(f"{app}/api/app/repo?name=api")
    assert code == 200 and set(body) == KEYS
    assert get(f"{app}/api/app/repo?name=api", token=None)[0] == 403
    for name in ("nope", "..%2Fapi"):
        assert get(f"{app}/api/app/repo?name={name}") == (404, {"error": "unknown repo"})
    code, body = get(f"{app}/api/app/repos")
    assert code == 200 and [r["name"] for r in body["repos"]] == ["api", "web", "worker"]
    assert get(f"{app}/api/app/repos", token=None)[0] == 403
