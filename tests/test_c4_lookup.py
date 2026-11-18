"""Agents get the C4 with its evidence (spec §5.2, §7): the prompt hook, the MCP `architecture` tool and the pre-edit
stop name an element, its state and its decisions, and withhold what the code does not back."""
from __future__ import annotations

import importlib

import pytest

from test_method_hooks import edit
from test_prompt_context import PAGE, UNSOURCED, write_model

DECISION = """---
title: Retry failed payments with backoff
type: decision
x-sources:
  - c4:shop.payments
---
# Retry failed payments with backoff

## Status

Accepted (2026-11-18)

## Context

Charges fail now and then.
"""


@pytest.fixture
def ctx_world(wired):
    docs = wired.root / "docs"
    for rel, text in (("flows/payments.md", PAGE), ("notes/payment-notes.md", UNSOURCED),
                      ("decisions/0001-retries.md", DECISION)):
        (docs / rel).parent.mkdir(parents=True, exist_ok=True)
        (docs / rel).write_text(text, encoding="utf-8", newline="\n")
    write_model(wired)
    return wired


@pytest.fixture
def ctx(ctx_world):
    return importlib.import_module("lib.app.prompt_context")


def test_a_file_named_in_the_prompt_brings_its_element_state_and_decision(ctx_world, ctx):
    out = ctx.build("why does Api.java retry payments with backoff")
    assert "shop.payments" in out["c4"] and "fresh" in out["text"] and "decisions/0001-retries.md" in out["text"]


def test_an_element_with_no_evidence_is_withheld_with_a_notice(ctx_world, ctx):
    out = ctx.build("change how billing sends invoices")
    assert "shop.billing" not in out["c4"] and "withheld: shop.billing" in out["text"]
    assert "Sends invoices" not in out["text"]


def test_a_file_alone_reaches_its_element_without_naming_it(ctx_world, ctx):
    out = ctx.build("explain what Api.java does please")
    assert out["c4"] == ["shop.payments"]


def test_the_mcp_tool_answers_for_an_element_and_a_file(ctx_world):
    import lib.mcp as mcp
    assert "evidence" in mcp.architecture("shop.payments")
    assert "decisions/0001-retries.md" in mcp.architecture("shop.payments")
    assert "shop.payments" in mcp.architecture("api:src/main/java/demo/Api.java")
    assert "withheld" in mcp.architecture("shop.billing")
    assert "Sends invoices" not in mcp.architecture("shop.billing")
    assert "no C4 element" in mcp.architecture("shop.nothing")
    assert any(t["name"] == "architecture" for t in mcp.TOOLS) and "architecture" in mcp.HANDLERS


def test_the_pre_edit_stop_names_the_element(ctx_world):
    rh = importlib.import_module("lib.app.retrieval_hooks")
    code, text = rh.pre_edit(edit(ctx_world, "c4-1"))
    assert code == 2 and 'architecture("api:src/main/java/demo/Api.java")' in text and "shop.payments" in text


def test_the_context_stays_under_its_cap_with_decisions(ctx_world, ctx):
    for n in range(2, 8):
        (ctx_world.root / "docs" / "decisions" / f"000{n}-more.md").write_text(
            DECISION.replace("Retry failed", f"Long title {n} " + "word " * 80), encoding="utf-8", newline="\n")
    out = ctx.build("why does Api.java retry payments with backoff")
    assert 0 < len(out["text"]) <= ctx.CAP


def test_decisions_come_accepted_first_and_by_citation_then_by_code(ctx_world):
    from lib.app import c4_lookup
    docs = ctx_world.root / "docs" / "decisions"
    (docs / "0002-by-code.md").write_text(
        DECISION.replace("c4:shop.payments", "api:src/main/java/demo/Api.java"), encoding="utf-8", newline="\n")
    (docs / "0003-proposed.md").write_text(DECISION.replace("Accepted (2026-11-18)", "Proposed"), encoding="utf-8",
                                           newline="\n")
    got = c4_lookup.decisions_about("shop.payments", 5)
    assert [d["path"] for d in got] == ["decisions/0001-retries.md", "decisions/0002-by-code.md",
                                        "decisions/0003-proposed.md"]
    assert c4_lookup.decisions_about("shop.payments", 1)[0]["status"] == "accepted"
    assert c4_lookup.decisions_about("shop.billing") == []


def test_covering_is_most_specific_first_and_skips_the_repo_anchor(ctx_world):
    from lib.app import c4_lookup
    write_model(ctx_world, """model {
  shop = system 'Shop' {
    api = service 'Api' {
      metadata { repo 'api' code ['api:src/main/java/demo/'] }
    }
    payments = service 'Payments' {
      metadata { code ['api:src/main/java/demo/Api.java'] }
    }
  }
}
""")
    assert c4_lookup.covering("api", "src/main/java/demo/Api.java") == ["shop.payments", "shop.api"]
    assert c4_lookup.covering("api", "README.md") == []
