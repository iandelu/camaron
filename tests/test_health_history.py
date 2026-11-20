"""Coverage history: one line per health build, the last 26 kept, for a repo page's sparkline."""
from __future__ import annotations

JACOCO = ('<?xml version="1.0" encoding="UTF-8"?><report name="app">'
          '<counter type="LINE" missed="20" covered="80"/></report>\n')


def snap(at, repos):
    return {"v": 1, "at": at, "repos": repos}


def test_a_build_adds_one_line_per_repo_figure(kit):
    from lib import health
    health.append_history(snap("2026-11-01T10:00:00Z", {
        "api": {"cloned": True, "coverage": {"percent": 71.5}},
        "web": {"cloned": True, "coverage": None},
        "worker": {"cloned": False}}))
    assert health.history() == [{"at": "2026-11-01T10:00:00Z", "repos": {"api": 71.5}}]


def test_only_the_last_26_are_kept(kit):
    from lib import health
    for i in range(30):
        health.append_history(snap(f"2026-11-{i + 1:02d}T00:00:00Z", {"api": {"cloned": True, "coverage": {"percent": float(i)}}}))
    rows = health.history()
    assert len(rows) == 26
    assert rows[0]["at"] == "2026-11-05T00:00:00Z" and rows[-1]["at"] == "2026-11-30T00:00:00Z"


def test_a_broken_line_is_skipped(kit):
    from lib import health
    health.HISTORY.parent.mkdir(parents=True, exist_ok=True)
    health.HISTORY.write_text("not json\n", encoding="utf-8")
    health.append_history(snap("2026-11-01T00:00:00Z", {"api": {"cloned": True, "coverage": {"percent": 50.0}}}))
    assert len(health.history()) == 1


def test_a_failed_repos_block_writes_nothing(kit):
    from lib import health
    health.append_history(snap("x", {"error": "boom"}))
    assert health.history() == []


def test_history_of_a_missing_file_is_empty(kit):
    from lib import health
    assert health.history() == []


def test_build_appends(wired):
    from lib import health
    from lib.common import repo_dir
    report = repo_dir("api") / "target/site/jacoco/jacoco.xml"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(JACOCO, encoding="utf-8")
    health.build(log=lambda _: None)
    health.build(log=lambda _: None)
    rows = health.history()
    assert len(rows) == 2 and rows[-1]["repos"]["api"] == 80.0
