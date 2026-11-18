"""X11: the repos' git history read without AI — hotspots, who knows each repo, files that change together (and work
that spans repos through a shared ticket key), commit conventions — into docs/overview/history.md."""
from __future__ import annotations

import os, subprocess, sys

from conftest import KIT_DIR


def commit(repo, author, files, msg):
    for rel, text in files.items():
        f = repo / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "-c", f"user.name={author}", "-c", "user.email=x@example.com", "commit", "-q", "-m", msg],
                   cwd=repo, check=True, capture_output=True)


def history_repos(kit):
    api, web = kit.ws / "api", kit.ws / "web"
    commit(api, "Ana", {"src/Order.java": "1", "src/OrderService.java": "1"}, "feat(orders): place order ORD-12")
    commit(api, "Ana", {"src/Order.java": "2", "src/OrderService.java": "2"}, "fix(orders): empty cart ORD-13")
    commit(api, "Bob", {"src/Payment.java": "1", "package-lock.json": "{}"}, "feat(pay): charge PAY-3")
    commit(api, "Bob", {"src/Order.java": "3"}, "fix: order rounding")
    commit(api, "dependabot[bot]", {"pom.xml": "<x/>"}, "chore(deps): bump")
    commit(web, "Cleo", {"src/cart.tsx": "1"}, "feat(cart): show order ORD-12")
    commit(web, "Cleo", {"src/cart.tsx": "2"}, "update stuff")


def test_mining_finds_hotspots_owners_and_co_change(kit):
    history_repos(kit)
    from lib import history
    h = history.mine(months=12)
    api = h["repos"]["api"]
    assert api["hotspots"][0] == ("src/Order.java", 3)
    assert all(f != "package-lock.json" for f, _ in api["hotspots"])                  # lockfiles are noise
    assert [a for a, _ in api["owners"]][:2] == ["Ana", "Bob"]
    assert not any("bot" in a for a, _ in api["owners"])
    assert (("src/Order.java", "src/OrderService.java"), 2) in api["co_change"]
    assert api["conventional"] == (4, 5)                                             # bot excluded, 'initial' is not
    assert h["across"] == [("ORD-12", ["api", "web"])]


def test_the_page_reads_well_and_passes_the_structure_check(kit):
    history_repos(kit)
    from lib import history
    page = history.write(months=12)
    text = page.read_text(encoding="utf-8")
    assert page == kit.root / "docs" / "overview" / "history.md"
    for s in ("## Hotspots", "## Who to ask", "## Changed together", "## Commit conventions", "Ana", "ORD-12"):
        assert s in text, s
    assert "x@example.com" not in text                                              # names only
    _, warns = kit.quality.check_structure(kit.services.doc_status.collect())
    assert not [w for w in warns if "history.md" in w], warns


def test_cli(kit):
    history_repos(kit)
    env = {**os.environ, "CAMARONES_ROOT": str(kit.root)}
    r = subprocess.run([sys.executable, str(KIT_DIR / "camarones.py"), "history", "--months", "6"], env=env,
                       capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0 and "history.md" in r.stdout, r.stderr


def test_no_history_says_so(kit):
    from lib import history
    text = history.render(history.mine(months=1, top=10) | {"repos": {}})
    assert "No repo with git history" in text and "| Repo |" not in text


def test_spanish_twin_and_folders(kit):
    history_repos(kit)
    ws = kit.services.workspace.workspace(); ws["project"]["translations"] = ["es"]; kit.services.workspace.save_workspace(ws)
    from lib import history
    assert history.mine(12)["repos"]["api"]["areas"]["Ana"] == "src"
    history.write(12)
    es = (kit.root / "docs" / "i18n" / "es" / "overview" / "history.md").read_text(encoding="utf-8")
    assert "## A quién preguntar" in es
    row = next(r for r in kit.services.doc_status.collect() if r["path"] == "overview/history.md")
    assert row["i18n"] == {"es": "current"}


def test_commits_are_public_and_empty_without_history(kit):
    history_repos(kit)
    from lib import history
    api = history.commits("api", 12)
    assert [c["subject"] for c in api][:2] == ["fix: order rounding", "feat(pay): charge PAY-3"]
    assert all("dependabot[bot]" != c["author"] for c in api) and api[0]["files"] == ["src/Order.java"]
    assert history.commits("nowhere", 12) == []


def test_the_newest_commit_of_a_repo_is_read(kit):
    history_repos(kit)
    from lib import history
    assert [c["subject"] for c in history.commits("web", 12)] == ["update stuff", "feat(cart): show order ORD-12", "initial"]
    assert history.mine(months=12)["repos"]["web"]["commits"] == 3


def dated_commit(repo, author, msg, when):
    env = {**os.environ, "GIT_AUTHOR_DATE": when, "GIT_COMMITTER_DATE": when}
    (repo / f"{abs(hash((msg, when)))}.txt").write_text(msg, encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "-c", f"user.name={author}", "-c", "user.email=x@example.com", "commit", "-q", "-m", msg],
                   cwd=repo, check=True, capture_output=True, env=env)


def test_weekly_buckets_by_iso_week_in_utc(kit):
    from datetime import date, datetime, timezone
    from lib import history

    def at(s):
        return int(datetime.fromisoformat(s).replace(tzinfo=timezone.utc).timestamp())

    empty = history.weekly([], date(2026, 11, 18))
    assert len(empty) == 12 and empty[-1] == {"start": "2026-11-16", "n": 0} and empty[0]["start"] == "2026-08-31"
    got = history.weekly([at("2026-11-15T23:59:59"), at("2026-11-16T00:00:00"), at("2026-08-30T12:00:00")],
                         date(2026, 11, 18))
    by = {w["start"]: w["n"] for w in got}
    assert by["2026-11-09"] == 1 and by["2026-11-16"] == 1 and sum(by.values()) == 2


def test_activity_counts_humans_and_names_the_last_one(kit):
    from datetime import date
    from lib import history
    api = kit.ws / "fresh"
    api.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=api, check=True, capture_output=True)
    dated_commit(api, "Ana", "one", "2026-11-02T10:00:00Z")
    dated_commit(api, "Bob", "two", "2026-11-09T10:00:00Z")
    dated_commit(api, "Ana", "three", "2026-11-12T10:00:00Z")
    dated_commit(api, "dependabot[bot]", "bump", "2026-11-13T10:00:00Z")
    got = history.activity("fresh", today=date(2026, 11, 18))
    assert got["total"] == 3 and got["people"] == 2 and len(got["weeks"]) == 12
    assert got["last"]["subject"] == "three" and got["last"]["author"] == "Ana"


def test_activity_of_a_folder_without_git_is_none(kit):
    from lib import history
    (kit.ws / "plain").mkdir()
    assert history.activity("plain") is None
