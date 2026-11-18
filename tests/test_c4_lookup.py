"""Agents get the C4 with its evidence (spec §5.2, §7): the prompt hook, the MCP `architecture` tool and the pre-edit
stop name an element, its state and its decisions, and withhold what the code does not back."""
from __future__ import annotations

import importlib

import pytest

from test_method_hooks import edit
from test_prompt_context import MODEL, PAGE, UNSOURCED, node, write_graph, write_model

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
    assert "decisions/0001-retries.md" in text


def test_the_context_stays_under_its_cap_with_decisions(ctx_world, ctx):
    for n in range(2, 8):
        (ctx_world.root / "docs" / "decisions" / f"000{n}-more.md").write_text(
            DECISION.replace("Retry failed", f"Long title {n} " + "word " * 80), encoding="utf-8", newline="\n")
    prompt = "why does Api.java retry payments with backoff"
    natural = len(ctx.build(prompt)["text"])
    ctx.CAP = natural - 120                                                   # the C4 part is the one that gets cut
    try:
        out = ctx.build(prompt)
    finally:
        ctx.CAP = 6000
    assert len(out["text"]) <= natural - 120 < natural
    assert all("· fresh" in line for line in out["text"].splitlines() if line.startswith("- shop.payments"))


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


def test_short_names_as_pages_wrote_them_before_name_their_element(ctx_world):
    from lib.app import c4_lookup
    docs = ctx_world.root / "docs"
    (docs / "decisions" / "0001-retries.md").write_text(DECISION.replace("c4:shop.payments", "c4:payments"),
                                                        encoding="utf-8", newline="\n")
    (docs / "flows" / "charges.md").write_text(PAGE.replace("api:src/main/java/demo/Api.java", "c4:payments"),
                                               encoding="utf-8", newline="\n")
    assert [d["path"] for d in c4_lookup.decisions_about("shop.payments")] == ["decisions/0001-retries.md"]
    assert c4_lookup.lookup("shop.payments")["elements"][0]["pages"] == ["flows/charges.md"]


def test_covering_is_most_specific_first_and_ends_with_the_repo_container(ctx_world):
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
    assert c4_lookup.covering("api", "src/main/java/demo/Other.java") == ["shop.api"]
    assert c4_lookup.covering("api", "README.md") == ["shop.api"]
    assert c4_lookup.covering("web", "README.md") == []


def test_a_file_only_a_repo_container_covers_returns_the_container(ctx_world):
    from lib.app import c4_lookup
    write_model(ctx_world, """model {
  shop = system 'Shop' {
    orders = service 'Orders' {
      metadata { repo 'api' }
    }
  }
}
""")
    assert c4_lookup.covering("api", "src/Anything.java") == ["shop.orders"]


API = "src/main/java/demo/Api.java"
RELATED = """model {
  shop = system 'Shop' {
    payments = service 'Payments' {
      description 'Charges cards'
      metadata { evidence 'api:src/main/java/demo/Api.java' }
    }
    billing = service 'Billing' {
      description 'Sends invoices'
    }
    ledger = service 'Ledger' {
      description 'Books entries'
    }
    payments -> billing 'notifies'
    payments -> ledger 'books' {
      #confirmed
    }
    payments -> billing 'audits' {
      metadata { code 'api:src/main/java/demo/Api.java#L1' }
    }
  }
}
"""


def test_relations_are_served_by_their_own_evidence(ctx_world):
    import lib.mcp as mcp
    write_model(ctx_world, RELATED)
    text = mcp.architecture("shop.payments")
    assert "-> shop.billing — withheld:" in text and "'notifies'" not in text            # no evidence, nobody vouched
    assert "-> shop.billing 'audits' (fresh)" in text                                       # backed by its own anchor
    assert "-> shop.ledger 'books' (no-evidence) · vouched for by a person" in text         # confirmed, labelled
    assert "withheld" in mcp.architecture("shop.billing") and "'audits'" not in mcp.architecture("shop.billing")


def test_a_broken_element_names_the_code_to_read(ctx_world, ctx):
    import lib.mcp as mcp
    write_model(ctx_world, MODEL.replace("api:src/main/java/demo/Api.java", "api:src/gone/Old.java"))
    out = ctx.build("change how payments retry")
    assert "withheld: shop.payments" in out["text"] and "Read the code instead: api:src/gone/Old.java (missing)" in out["text"]
    assert "Read the code instead: api:src/gone/Old.java (missing)" in mcp.architecture("shop.payments")


def test_a_named_file_under_a_folder_anchor_reaches_its_element(ctx_world, ctx):
    write_model(ctx_world, MODEL.replace("'api:src/main/java/demo/Api.java'", "'api:src/main/java/demo/'")
                .replace("Charges cards and retries failed payments", "Settles"))
    assert ctx.build("explain src/main/java/demo/Api.java please")["c4"] == ["shop.payments"]
    assert ctx.build("explain api:src/main/java/demo/Api.java please")["c4"] == ["shop.payments"]
    write_graph(ctx_world, "api", [node("Api", API)])
    assert ctx.build("explain what Api.java does please")["c4"] == ["shop.payments"]


def test_a_named_path_under_a_dot_folder_keeps_its_dot(ctx_world, ctx):
    ci = ctx_world.ws / "api" / ".github" / "workflows" / "ci.yml"
    ci.parent.mkdir(parents=True)
    ci.write_text("on: push\n", encoding="utf-8", newline="\n")
    write_model(ctx_world, MODEL.replace("'api:src/main/java/demo/Api.java'", "'api:.github/workflows/'")
                .replace("Charges cards and retries failed payments", "Settles"))
    assert ctx.build("explain .github/workflows/ci.yml please")["c4"] == ["shop.payments"]
    assert ctx.build("explain ./.github/workflows/ci.yml please")["c4"] == ["shop.payments"]


def test_a_named_path_that_cannot_be_looked_up_leaves_the_rest_of_the_context(ctx_world, ctx, monkeypatch):
    monkeypatch.setattr(ctx, "_named_paths", lambda *a: (_ for _ in ()).throw(OSError(63, "File name too long")))
    out = ctx.build("why does Api.java retry payments with backoff")
    assert out["pages"] and "shop.payments" in out["c4"]


def test_withheld_elements_do_not_take_the_slots_of_served_ones(ctx_world, ctx):
    held = "".join(f"    bill{n} = service 'Billing {n}' {{\n      description 'Sends invoices'\n    }}\n"
                   for n in range(5))
    write_model(ctx_world, MODEL.replace("    billing = service", held + "    billing = service")
                .replace("Charges cards and retries failed payments", "Billing invoices"))
    out = ctx.build("change how billing invoices are sent")
    assert out["c4"] == ["shop.payments"] and out["text"].count("withheld: shop.") == ctx.C4_TOP


def test_a_confirmed_element_without_evidence_is_served_with_its_notice(ctx_world, ctx):
    write_model(ctx_world, MODEL.replace("    billing = service 'Billing' {", "    billing = service 'Billing' {\n      #confirmed"))
    out = ctx.build("change how billing sends invoices")
    assert out["c4"] == ["shop.billing"] and "vouched for by a person" in out["text"]


def test_the_warn_policy_serves_what_block_withholds(ctx_world, ctx):
    ws = ctx_world.services.workspace.workspace()
    ws["freshness"] = {"ai_policy": "warn"}
    ctx_world.services.workspace.save_workspace(ws)
    served, held = ctx._c4("billing", ["billing"], set(), [])
    assert [e["fqn"] for e in served] == ["shop.billing"] and held == []
    assert served[0]["notice"] == "unreviewed: nothing in the code backs it."


def test_a_changed_file_makes_its_element_suspect(ctx_world, ctx):
    from lib.harness import freshness
    write_model(ctx_world, MODEL.replace("'api:src/main/java/demo/Api.java'", "'api:src/main/java/demo/Api.java#L3'"))
    freshness.c4_states()
    api = ctx_world.ws / "api" / API
    api.write_text(api.read_text(encoding="utf-8").replace("public class Api", "public class Moved"), encoding="utf-8")
    out = ctx.build("why does Api.java retry payments with backoff")
    assert "shop.payments" in out["c4"] and "suspect" in out["text"] and "its code changed: verify." in out["text"]


def test_an_element_whose_repo_is_not_here_is_unchecked(ctx_world, ctx, monkeypatch):
    from lib.harness import freshness
    real = freshness.element_states
    monkeypatch.setattr(freshness, "element_states", lambda fqns: {
        f: {**s, "state": "unchecked"} for f, s in real(fqns).items()})
    out = ctx.build("why does Api.java retry payments with backoff")
    assert "unchecked" in out["text"] and "not checked here." in out["text"]


def test_targets_are_normalised_and_a_missing_element_is_the_error(ctx_world):
    import lib.mcp as mcp
    for target in ("api:./src/main/java/demo/Api.java#L3", "api:/src/main/java/demo/Api.java"):
        assert "shop.payments" in mcp.architecture(target)
    assert mcp.architecture("shop.nothing").startswith("no C4 element 'shop.nothing'")
    assert "Empty target" in mcp.architecture(" ")


def test_a_repo_container_reads_as_the_whole_repo(ctx_world):
    import lib.mcp as mcp
    write_model(ctx_world, "model {\n  shop = system 'Shop' {\n    orders = service 'Orders' {\n"
                "      metadata { repo 'api' code 'api:src/main/java/demo/Api.java' }\n    }\n  }\n}\n")
    assert "whole repo api" in mcp.architecture("shop.orders")
