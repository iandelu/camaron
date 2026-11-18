"""P1 of the turning point (docs/superpowers/specs/2026-11-17-core-turning-point-design.md): what an agent should know
before it acts on a prompt, built with no model call — the best doc sections through the same freshness gate as the
MCP, the C4 elements behind them and the code-graph nodes the prompt names, under a fixed size."""
from __future__ import annotations

import json

import pytest

PAGE = """---
title: Payments
type: business-flow
description: How a card payment is charged and retried.
x-sources:
  - api:src/main/java/demo/Api.java
---
# Payments

> **TL;DR:** The api charges the card; a failed charge is retried.

## Retry policy

A failed payment is retried three times with exponential backoff before the order is cancelled.

## Refunds

Refunds go back to the original card.
"""

UNSOURCED = """---
title: Payment notes
type: guide
---
# Payment notes

> **TL;DR:** Loose notes.

## Ideas

Payments retry with backoff when the charge fails; the backoff could be longer one day.
"""

MODEL = """model {
  shop = system 'Shop' {
    payments = service 'Payments' {
      description 'Charges cards and retries failed payments'
      metadata { evidence 'api:src/main/java/demo/Api.java' }
    }
    billing = service 'Billing' {
      description 'Sends invoices'
    }
  }
}
"""


@pytest.fixture
def ctx(wired):
    import importlib
    docs = wired.root / "docs"
    (docs / "flows").mkdir(parents=True, exist_ok=True)
    (docs / "flows" / "payments.md").write_text(PAGE, encoding="utf-8", newline="\n")
    (docs / "notes").mkdir(parents=True, exist_ok=True)
    (docs / "notes" / "payment-notes.md").write_text(UNSOURCED, encoding="utf-8", newline="\n")
    return importlib.import_module("lib.app.prompt_context")


def write_model(kit, text=MODEL):
    d = kit.services.diagrams.arch_dir()
    d.mkdir(parents=True, exist_ok=True)
    (d / "payments.c4").write_text(text, encoding="utf-8", newline="\n")


def write_graph(kit, repo, nodes, commit="0000000"):
    g = kit.services.code.repo_graph(repo)
    g.parent.mkdir(parents=True, exist_ok=True)
    g.write_text(json.dumps({"directed": False, "nodes": nodes, "links": [], "built_at_commit": commit}),
                 encoding="utf-8")


def node(label, path, line="L1", kind="code"):
    return {"id": label.lower(), "label": label, "norm_label": label.lower(), "source_file": path,
            "source_location": line, "file_type": kind}


def test_a_matching_prompt_gets_the_cited_section(ctx):
    out = ctx.build("change how payments retry with backoff when the charge fails")
    assert "flows/payments.md#" in out["text"]
    assert "three times with exponential backoff" in out["text"]
    assert "draft" in out["text"]
    served = [p for p in out["pages"] if p["served"]]
    assert served and served[0]["path"] == "flows/payments.md"


def test_a_page_the_gate_holds_back_shows_only_its_notice(ctx):
    out = ctx.build("change how payments retry with backoff when the charge fails")
    held = [p for p in out["pages"] if not p["served"]]
    assert [p["path"] for p in held] == ["notes/payment-notes.md"]
    assert "notes/payment-notes.md" in out["text"] and "withheld" in out["text"]
    assert "longer one day" not in out["text"]


@pytest.mark.parametrize("prompt", ["", "hi there", "quantum chromodynamics lattice gauge"])
def test_a_short_or_unmatched_prompt_adds_nothing(ctx, prompt):
    out = ctx.build(prompt)
    assert out["text"] == "" and out["pages"] == [] and out["c4"] == [] and out["nodes"] == []


def test_the_c4_elements_behind_the_pages(ctx, wired):
    write_model(wired)
    out = ctx.build("change how payments retry with backoff when the charge fails")
    assert out["c4"] == ["shop.payments"]
    assert "shop.payments" in out["text"] and "Charges cards" in out["text"]
    assert "shop.billing" not in out["text"]


def test_the_graph_nodes_the_prompt_names(ctx, wired):
    write_graph(wired, "api", [node("RetryPolicy", "src/main/java/demo/RetryPolicy.java", "L3"),
                               node("Invoice", "src/main/java/demo/Invoice.java")])
    out = ctx.build("change the RetryPolicy so payments retry with a longer backoff")
    assert [n["label"] for n in out["nodes"]] == ["RetryPolicy"]
    assert "RetryPolicy" in out["text"] and "api/src/main/java/demo/RetryPolicy.java:L3" in out["text"]
    assert "Invoice" not in out["text"]
    assert "0000000" in out["text"]                                  # the graph is older than the repo's HEAD


def test_a_file_named_in_the_prompt_finds_its_nodes(ctx, wired):
    write_graph(wired, "api", [node("Api", "src/main/java/demo/Api.java"),
                               node("Invoice", "src/main/java/demo/Invoice.java")])
    out = ctx.build("why does Api.java retry payments with backoff")
    assert [n["label"] for n in out["nodes"]] == ["Api"]


@pytest.mark.parametrize("path", ["tests/test_retry.py", "src/test/java/demo/RetryPolicyTest.java",
                                  "web/src/retry.test.js", "worker/retry_test.go", "__tests__/retry.js"])
def test_test_files_stay_out_unless_the_prompt_is_about_tests(ctx, wired, path):
    write_graph(wired, "api", [node("test_payments_retry_policy", path),
                               node("RetryPolicy", "src/main/java/demo/RetryPolicy.java")])
    out = ctx.build("change the retry policy for payments")
    assert [n["label"] for n in out["nodes"]] == ["RetryPolicy"]
    about_tests = ctx.build("fix the test for the retry policy of payments")
    assert "test_payments_retry_policy" in [n["label"] for n in about_tests["nodes"]]


def test_one_common_word_is_not_enough(ctx, wired):
    write_graph(wired, "api", [node("RetryLoop", "src/main/java/demo/RetryLoop.java"),
                               node("ChangeRetry", "src/main/java/demo/ChangeRetry.java"),   # "change" is the verb
                               node("RetryPolicy", "src/main/java/demo/RetryPolicy.java")])
    out = ctx.build("change the retry policy for payments")
    assert [n["label"] for n in out["nodes"]] == ["RetryPolicy"]


def test_one_word_is_enough_in_a_file_the_pages_cite(ctx, wired):
    write_graph(wired, "api", [node("charge", "src/main/java/demo/Api.java"),
                               node("charge", "src/main/java/demo/Other.java"),
                               node("chargeback", "src/main/java/demo/Api.java")])   # a longer word, not a plural
    out = ctx.build("change how payments retry with backoff when the charge fails")
    assert [n["file"] for n in out["nodes"]] == ["src/main/java/demo/Api.java"]


@pytest.mark.parametrize("label,path", [("RetryPolicy", ""), ("RetryPolicy", "worker/"),
                                        ("RetryPolicy", "web/dist/app-1a2b3c4d.js"),
                                        ("RetryPolicy", "desktop/renderer-build/assets/x.js"),
                                        ("RetryPolicy", "web/node_modules/lib/retry.js"),
                                        ("{ retry, policy }", "web/src/App.jsx")])
def test_imports_build_output_and_vendored_code_stay_out(ctx, wired, label, path):
    write_graph(wired, "api", [node(label, path), node("RetryPolicy", "src/main/java/demo/RetryPolicy.java")])
    out = ctx.build("change the retry policy for payments")
    assert [n["file"] for n in out["nodes"]] == ["src/main/java/demo/RetryPolicy.java"]


def test_the_context_stays_under_its_cap(ctx, wired):
    big = PAGE.replace("before the order is cancelled.", "before the order is cancelled. " + "Backoff grows. " * 2000)
    (wired.root / "docs" / "flows" / "payments.md").write_text(big, encoding="utf-8", newline="\n")
    out = ctx.build("change how payments retry with backoff when the charge fails")
    assert 0 < len(out["text"]) <= ctx.CAP


def test_building_is_deterministic_and_leaves_the_status_file_alone(ctx, wired):
    status = wired.root / "docs" / ".status.json"
    before = status.read_bytes() if status.exists() else None
    a = ctx.build("change how payments retry with backoff when the charge fails")
    b = ctx.build("change how payments retry with backoff when the charge fails")
    assert a == b
    assert (status.read_bytes() if status.exists() else None) == before
