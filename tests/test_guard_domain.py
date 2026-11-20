"""The pure rules of the guardrails (lib/domain/guard.py): what counts as an AI credit, a forbidden path, attribution
turned off, and when a set of gate checks is green."""
from __future__ import annotations

import pytest
from conftest import KIT_DIR  # noqa: F401  (puts .camarones on sys.path)

from lib.domain import guard

TRAILER = "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
GENERATED = "🤖 Generated with [Claude Code](https://claude.com/claude-code)"


@pytest.mark.parametrize("text", [TRAILER, GENERATED, "feat: x\n\nbody\n\nco-authored-by: claude <a@b.c>",
                                  "Co-authored-by: Some Bot <bot@anthropic.com>", "  Generated with Claude Code"])
def test_an_ai_credit_is_found(text):
    assert guard.has_ai_credit(text)


@pytest.mark.parametrize("text", ["Co-Authored-By: Ana Pérez <ana@example.com>", "Co-Authored-By: Claudia Ruiz <c@x.com>",
                                  "feat(runners): the claude runner reads its model", "docs: how Claude Code generated with care"])
def test_people_and_mentions_of_claude_are_not(text):
    assert not guard.has_ai_credit(text)


@pytest.mark.parametrize("path", [".env", ".env.local", "api/.env.production", "certs/site.pem", "a/b/server.key",
                                  "id_rsa", "home/.ssh/id_rsa.pub", "secrets/db.txt", "deploy/secrets/x.yaml"])
def test_forbidden_paths(path):
    assert guard.forbidden(path)


@pytest.mark.parametrize("path", [".env.example", "api/.env.sample", "docs/secrets.md", "src/keyboard.ts", "README.md",
                                  "src/secretsmanager/client.py"])
def test_ordinary_paths(path):
    assert not guard.forbidden(path)


def test_attribution_off_keeps_everything_else():
    st = {"permissions": {"deny": ["Skill(x)"]}, "attribution": {"commit": "mine", "sessionUrl": False}}
    out = guard.attribution_off(st)
    assert out == {"permissions": {"deny": ["Skill(x)"]}, "attribution": {"commit": "", "pr": "", "sessionUrl": False}}
    assert st["attribution"]["commit"] == "mine"                       # the input is not edited
    assert guard.attribution_is_off(out) and guard.attribution_off(out) == out


@pytest.mark.parametrize("st,off", [({}, False), ({"attribution": {"commit": ""}}, False), ({"attribution": False}, True),
                                    ({"attribution": {"commit": "", "pr": ""}}, False),    # a session link would still go in
                                    ({"attribution": {"commit": "", "pr": "", "sessionUrl": False}}, True),
                                    ({"attribution": {"commit": "x", "pr": ""}}, False), ({"attribution": "weird"}, False)])
def test_attribution_is_off(st, off):
    assert guard.attribution_is_off(st) is off


def test_a_non_dict_attribution_is_replaced():
    assert guard.attribution_off({"attribution": "weird"}) == {"attribution": {"commit": "", "pr": "", "sessionUrl": False}}


def check(status):
    return {"id": "c", "status": status, "detail": []}


@pytest.mark.parametrize("statuses,verdict,code", [(["pass", "n/a"], "pass", 0), ([], "pass", 0),
                                                   (["pass", "not-run"], "not-run", 3),
                                                   (["fail", "not-run"], "fail", 1), (["fail"], "fail", 1)])
def test_a_check_that_did_not_run_is_never_green(statuses, verdict, code):
    checks = [check(s) for s in statuses]
    assert guard.overall(checks) == verdict and guard.exit_code(checks) == code


@pytest.mark.parametrize("current,latest,behind", [("1.2.3", "3.0.0", 2), ("v2.0", "2.9.9", 0), ("^4.1", "6.0.1", 2),
                                                   ("~1.0.0", "1.0.5", 0), ("", "3.0", 0), ("1", "x", 0), ("3.0", "1.0", 0)])
def test_majors_behind(current, latest, behind):
    assert guard.majors_behind(current, latest) == behind
