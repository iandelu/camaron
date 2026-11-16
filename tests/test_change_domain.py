"""lib/domain/change: a change's pure rules (WI-21). The phases and their order, the board rules the kit follows, ids,
slugs and branch names, which change a command means. Values in, values out: no `kit` fixture, no git, no files."""
from __future__ import annotations

import importlib

import pytest


def change():
    return importlib.import_module("lib.domain.change")


def test_the_phases_in_order():
    assert change().PHASES == ("docs", "assess", "plan", "code", "docs-update", "verify", "ship", "retro")


def test_a_phase_moves_forward_and_may_skip_ahead():
    c = change()
    assert c.advance("docs", "assess") is True
    assert c.advance("assess", "code") is True                   # a low change has its plan in chat
    assert c.advance("code", "code") is False                    # the same phase again: nothing to do


def test_a_phase_never_goes_back():
    with pytest.raises(ValueError, match="never goes back"):
        change().advance("verify", "code")


def test_an_unknown_phase_is_refused_with_the_list():
    with pytest.raises(ValueError, match="docs, assess, plan"):
        change().advance("docs", "review")


@pytest.mark.parametrize("rule, status, target", [
    ("start", "Backlog", "In Progress"), ("start", "Ready", "In Progress"), ("start", "Done", "In Progress"),
    ("start", "In Progress", None), ("start", "In Review", None),
    ("pr", "In Progress", "In Review"), ("pr", "Backlog", "In Review"), ("pr", "In Review", None), ("pr", "Done", None),
    ("merged", "In Review", "Done"), ("merged", "In Progress", "Done"), ("merged", "Done", None),
    ("abandon", "In Progress", "Ready"), ("abandon", "In Review", "Ready"), ("abandon", "Ready", None),
    ("abandon", "Done", None),
])
def test_the_board_rules(rule, status, target):
    assert change().board_target(rule, status) == target


def test_the_rules_are_the_ones_the_epic_names():
    assert change().RULES == {"start": "In Progress", "pr": "In Review", "merged": "Done", "abandon": "Ready"}


def test_slug_takes_the_first_words_of_the_title():
    c = change()
    assert c.slugify("Retry failed payments twice, then alert") == "retry-failed-payments-twice"
    assert c.slugify("¡Añadir botón «Empezar»!") == "anadir-boton-empezar"
    assert len(c.slugify("a" * 80)) <= 30
    assert c.slugify("!!!") == "change"


def test_id_is_the_item_in_lower_case_else_slug_and_hex():
    c = change()
    assert c.change_id("WI-21", "change-phases", "3f9a") == "wi-21"
    assert c.change_id(None, "change-phases", "3f9a") == "change-phases-3f9a"


def test_branch_from_the_template():
    c = change()
    assert c.branch_name("cam/{id}-{slug}", "wi-21", "change-phases") == "cam/wi-21-change-phases"
    assert c.branch_name("feature/{id}", "wi-21", "change-phases") == "feature/wi-21"
    # without an item the id already carries the slug: no slug twice, no dangling dash
    assert c.branch_name("cam/{id}-{slug}", "change-phases-3f9a", "") == "cam/change-phases-3f9a"


def test_a_template_that_cannot_make_a_branch_is_refused():
    c = change()
    with pytest.raises(ValueError, match=r"\{id\}"):
        c.branch_name("cam/{slug}", "wi-21", "x")
    with pytest.raises(ValueError, match="change.branch"):
        c.branch_name("cam/{nope}", "wi-21", "x")


def test_pick_by_id_then_by_branch_then_the_only_one():
    c = change()
    a = {"id": "wi-1", "repos": {"api": {"branch": "cam/wi-1-a"}}, "docs": {"branch": "cam/wi-1-a"}}
    b = {"id": "wi-2", "repos": {"web": {"branch": "cam/wi-2-b"}}, "docs": {"branch": "cam/wi-2-b"}}
    assert c.pick([a, b], "WI-2", []) is b
    assert c.pick([a, b], None, ["cam/wi-1-a"]) is a
    assert c.pick([a], None, []) is a
    with pytest.raises(LookupError, match="wi-1, wi-2"):
        c.pick([a, b], None, ["main"])
    with pytest.raises(LookupError, match="no open change"):
        c.pick([], None, [])
    with pytest.raises(LookupError, match="wi-9"):
        c.pick([a, b], "wi-9", [])


def test_next_step_follows_the_phase():
    c = change()
    rec = {"id": "wi-21", "phase": "docs", "state": "open", "prs": {}}
    assert "change phase wi-21 assess" in c.next_step(rec)
    assert "change link wi-21" in c.next_step({**rec, "phase": "ship"})
    assert "change close wi-21" in c.next_step({**rec, "phase": "retro", "state": "in-review"})
    assert c.next_step({**rec, "state": "closed"}) == ""
