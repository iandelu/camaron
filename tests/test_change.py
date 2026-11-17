"""`camaron change` use cases (WI-21, lib/app/change.py): a coding change's record in the cache, its branch in each
repo and its cam-docs worktree, its phase (forward only), and the board card the kit moves by fixed rules: start → In
Progress, a PR linked → In Review, merged → Done, abandoned → Ready. Offline: the repos are the fixture's, a "remote"
is a local bare clone."""
from __future__ import annotations

import json
import subprocess

import pytest


def git(path, *args, check=True):
    return subprocess.run(["git", *args], cwd=path, capture_output=True, text=True, encoding="utf-8",
                          check=check).stdout.strip()


@pytest.fixture
def proj(wired):
    """A documented project with a board and one story on `api`."""
    from lib.kanban import ops
    ops.init(log=lambda _: None)
    ops.add("story", "Retry failed payments", repos=["api"])
    git(wired.root, "add", "-A")
    git(wired.root, "commit", "-qm", "board")
    return wired


def chg():
    from lib.app import change
    return change


def status_of(item):
    from lib.kanban import ops
    return ops.show(item)["status"]


def record(proj, id_):
    return json.loads((proj.root / ".camarones" / ".cache" / "changes" / f"{id_}.json").read_text(encoding="utf-8"))


# ---------- start ----------
def test_start_writes_the_record_branches_the_repo_opens_the_worktree_and_starts_the_card(proj):
    base = git(proj.ws / "api", "rev-parse", "HEAD")
    res = chg().start("Retry failed payments", item="WI-1")
    rec = res["change"]
    assert rec["id"] == "wi-1" and rec["item"] == "WI-1" and rec["phase"] == "docs" and rec["state"] == "open"
    assert rec["repos"] == {"api": {"branch": "cam/wi-1-retry-failed-payments", "base": base, "base_ref": "main",
                                    "adopted": False}}
    assert git(proj.ws / "api", "rev-parse", "--abbrev-ref", "HEAD") == "cam/wi-1-retry-failed-payments"
    wt = proj.ws / ".cw" / "wi-1"
    assert rec["docs"]["worktree"] == str(wt) and rec["docs"]["branch"] == "cam/wi-1-retry-failed-payments"
    assert git(wt, "rev-parse", "--abbrev-ref", "HEAD") == "cam/wi-1-retry-failed-payments"
    assert status_of("WI-1") == "In Progress"
    assert [(b["rule"], b["to"], b["forced"]) for b in rec["board"]] == [("start", "In Progress", False)]
    assert [p["phase"] for p in rec["phases"]] == ["docs"]
    assert record(proj, "wi-1") == rec                                    # what it returns is what it keeps
    assert "change phase wi-1 assess" in res["next"]


def test_start_names_the_repos_it_is_given(proj):
    rec = chg().start("Retry failed payments", item="WI-1", repos=["api", "web"])["change"]
    assert sorted(rec["repos"]) == ["api", "web"]
    assert git(proj.ws / "web", "rev-parse", "--abbrev-ref", "HEAD") == "cam/wi-1-retry-failed-payments"


def test_a_dirty_repo_stops_the_start_before_anything_is_written(proj):
    (proj.ws / "api" / "notes.txt").write_text("wip", encoding="utf-8")
    with pytest.raises(chg().ChangeError, match="api"):
        chg().start("Retry failed payments", item="WI-1")
    assert git(proj.ws / "api", "rev-parse", "--abbrev-ref", "HEAD") == "main"
    assert not (proj.ws / ".cw" / "wi-1").exists()
    assert not (proj.root / ".camarones" / ".cache" / "changes" / "wi-1.json").exists()
    assert status_of("WI-1") == "Backlog"


def test_the_kits_own_pointer_block_does_not_make_a_repo_dirty(proj):
    claude = proj.ws / "api" / "CLAUDE.md"
    assert "cam-docs:start" in claude.read_text(encoding="utf-8")         # wire_project left it, uncommitted
    assert git(proj.ws / "api", "status", "--porcelain") == "M CLAUDE.md"
    chg().start("Retry failed payments", item="WI-1")
    assert git(proj.ws / "api", "rev-parse", "--abbrev-ref", "HEAD") == "cam/wi-1-retry-failed-payments"


def test_an_edit_of_ones_own_next_to_the_pointer_block_is_dirty(proj):
    claude = proj.ws / "api" / "CLAUDE.md"
    claude.write_text("# api notes, edited\n\n" + claude.read_text(encoding="utf-8"), encoding="utf-8")
    with pytest.raises(chg().ChangeError, match="api has uncommitted changes"):
        chg().start("Retry failed payments", item="WI-1")


def test_a_clean_feature_branch_is_adopted(proj):
    git(proj.ws / "api", "switch", "-qc", "feat/retries")
    rec = chg().start("Retry failed payments", item="WI-1")["change"]
    assert rec["repos"]["api"]["branch"] == "feat/retries" and rec["repos"]["api"]["adopted"] is True
    assert git(proj.ws / "api", "rev-parse", "--abbrev-ref", "HEAD") == "feat/retries"


def test_the_start_gate_refuses_and_force_overrides(proj):
    from lib.kanban import ops
    ops.add("story", "Alert on failures", repos=["api"], dependencies=["WI-1"])
    with pytest.raises(chg().ChangeError, match="WI-1"):
        chg().start("Alert on failures", item="WI-2")
    assert git(proj.ws / "api", "rev-parse", "--abbrev-ref", "HEAD") == "main"
    assert status_of("WI-2") == "Backlog"
    rec = chg().start("Alert on failures", item="WI-2", force=True)["change"]
    assert status_of("WI-2") == "In Progress" and rec["board"][0]["forced"] is True


def test_a_rerun_returns_the_open_change(proj):
    first = chg().start("Retry failed payments", item="WI-1")["change"]
    again = chg().start("Retry failed payments", item="WI-1")
    assert again["again"] is True and again["change"] == first


def test_an_unknown_repo_or_item_is_refused(proj):
    with pytest.raises(chg().ChangeError, match="nope"):
        chg().start("x", item="WI-1", repos=["nope"])
    with pytest.raises(chg().ChangeError, match="WI-9"):
        chg().start("x", item="WI-9")


def test_without_an_item_the_id_carries_the_slug_and_no_card_moves(proj):
    rec = chg().start("Tidy the logs", repos=["worker"])["change"]
    assert rec["id"].startswith("tidy-the-logs-") and rec["item"] is None
    assert rec["repos"]["worker"]["branch"] == f"cam/{rec['id']}" and rec["board"] == []
    again = chg().start("Tidy the logs", repos=["worker"])                # a rerun finds it by its title
    assert again["again"] is True and again["change"]["id"] == rec["id"]


def test_a_branch_template_from_workspace_yaml(proj):
    ws = proj.services.workspace.workspace()
    ws["change"] = {"branch": "feature/{id}"}
    proj.services.workspace.save_workspace(ws)
    rec = chg().start("Retry failed payments", item="WI-1")["change"]
    assert rec["repos"]["api"]["branch"] == "feature/wi-1"


def test_start_lists_the_docs_to_read(proj):
    page = proj.root / "docs" / "flows" / "payments.md"
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text("---\ntitle: Payments\nx-sources:\n  - api:src/main/java/demo/Api.java#Api\n---\n"
                    "# Payments\n\n## Calls\n\nThe api calls the worker.\n", encoding="utf-8")
    (proj.root / "docs" / "retries.md").write_text("---\ntitle: Retries\n---\n# Retries\n\nFailed payments are "
                                                     "retried.\n", encoding="utf-8")
    res = chg().start("Retry failed payments", item="WI-1", files=["api:src/main/java/demo/Api.java"])
    paths = {d["path"]: d for d in res["to_read"]}
    assert paths["flows/payments.md"]["why"] == "cites api:src/main/java/demo/Api.java"
    assert paths["retries.md"]["why"] == "search" and paths["retries.md"]["trust"] == "draft"
    assert len(res["to_read"]) <= 12 and res["change"]["to_read"] == res["to_read"]


# ---------- phase ----------
def test_phase_moves_forward_and_keeps_the_history(proj):
    chg().start("Retry failed payments", item="WI-1")
    chg().phase("wi-1", "assess")
    rec = chg().phase("wi-1", "code")                                    # a skip ahead is fine
    assert rec["phase"] == "code" and [p["phase"] for p in rec["phases"]] == ["docs", "assess", "code"]
    assert record(proj, "wi-1")["phase"] == "code"


def test_phase_never_goes_back(proj):
    chg().start("Retry failed payments", item="WI-1")
    chg().phase("wi-1", "verify")
    with pytest.raises(chg().ChangeError, match="never goes back"):
        chg().phase("wi-1", "code")
    assert record(proj, "wi-1")["phase"] == "verify"


def test_the_change_is_found_from_the_branch_checked_out_in_the_folder(proj):
    from lib.kanban import ops
    ops.add("story", "Alert on failures", repos=["web"])
    chg().start("Retry failed payments", item="WI-1")
    chg().start("Alert on failures", item="WI-2")
    assert chg().phase(None, "assess", cwd=proj.ws / "web")["id"] == "wi-2"
    with pytest.raises(LookupError, match="wi-1, wi-2"):
        chg().phase(None, "plan", cwd=proj.ws / "worker")


# ---------- status ----------
def test_status_lists_open_changes_with_their_next_step(proj):
    chg().start("Retry failed payments", item="WI-1")
    rows = chg().status()
    assert [(r["id"], r["phase"], r["state"]) for r in rows] == [("wi-1", "docs", "open")]
    assert rows[0]["repos"] == {"api": "cam/wi-1-retry-failed-payments"}
    assert "change phase wi-1 assess" in rows[0]["next"]
    assert chg().status("wi-1")[0]["id"] == "wi-1"


def test_the_board_reads_the_phase_of_each_item(proj):
    chg().start("Retry failed payments", item="WI-1")
    chg().phase("wi-1", "code")
    assert {k: v["phase"] for k, v in chg().by_item().items()} == {"WI-1": "code"}
