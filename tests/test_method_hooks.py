"""R36 / X2: hooks that hold the method even when an agent skims the playbook — opt-in per project (`camaron hooks
on`), written by the kit into cam-docs/.claude/settings.json and recognised by trust as the kit's own. SessionStart
brings the plan state in, PostToolUse checks the page just edited, Stop reminds once to update the docs."""
from __future__ import annotations

import json, os, subprocess, sys

import pytest


def settings(kit):
    return json.loads((kit.root / ".claude" / "settings.json").read_text(encoding="utf-8"))


def kit_hooks(kit):
    return {e: [h["command"] for g in groups for h in g.get("hooks", []) if " hook " in h.get("command", "")]
            for e, groups in (settings(kit).get("hooks") or {}).items()}


@pytest.fixture
def hooks(wired):
    import importlib
    wired.trust = importlib.import_module("lib.trust")
    return importlib.import_module("lib.hooks")


def test_off_by_default(wired, hooks):
    assert not any(kit_hooks(wired).values())


def test_on_writes_five_hooks_the_kit_owns(wired, hooks):
    hooks.set_enabled(True)
    found = kit_hooks(wired)
    assert {k for k, v in found.items() if v} == {"SessionStart", "UserPromptSubmit", "PreToolUse", "PostToolUse",
                                                  "Stop"}
    assert wired.trust.pending() == []
    hooks.set_enabled(False)
    assert not any(kit_hooks(wired).values())


def test_the_teams_own_hooks_are_kept(wired, hooks):
    st = settings(wired)
    st.setdefault("hooks", {})["PreToolUse"] = [{"matcher": "Bash", "hooks": [{"type": "command", "command": "echo x"}]}]
    (wired.root / ".claude" / "settings.json").write_text(json.dumps(st), encoding="utf-8")
    hooks.set_enabled(True)
    hooks.set_enabled(False)
    assert settings(wired)["hooks"]["PreToolUse"][0]["hooks"][0]["command"] == "echo x"


def test_session_start_brings_the_plan_in(wired, hooks):
    wired.plan.sync()
    text = hooks.session_start()
    assert "plan" in text.lower() and "setup" in text and len(text) <= hooks.CAP


def run_hook(kit, name, payload):
    env = {**os.environ, "CAMARONES_ROOT": str(kit.root)}
    return subprocess.run([sys.executable, str(kit.kit_dir / "camarones.py"), "hook", name], env=env,
                          input=json.dumps(payload), capture_output=True, text=True, encoding="utf-8")


def test_post_edit_feeds_a_pages_problems_back(wired, hooks):
    page = wired.root / "docs" / "flows" / "x.md"
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text("---\ntitle: X\ntype: business-flow\n---\n# X\n\nNo summary here, see above.\n", encoding="utf-8")
    r = run_hook(wired, "post-edit", {"tool_name": "Write", "tool_input": {"file_path": str(page)}})
    assert r.returncode == 2 and "TL;DR" in r.stderr and "flows/x.md" in r.stderr
    other = run_hook(wired, "post-edit", {"tool_name": "Write", "tool_input": {"file_path": str(wired.ws / "api" / "x.java")}})
    assert other.returncode == 0 and not other.stderr


def test_stop_reminds_once_per_session(wired, hooks):
    payload = {"session_id": "s-1", "stop_hook_active": False}
    first = run_hook(wired, "stop", payload)
    assert first.returncode == 0 and json.loads(first.stdout)["decision"] == "block"
    assert "never-documented" in first.stdout or "changed" in first.stdout
    assert run_hook(wired, "stop", payload).stdout.strip() == ""
    assert run_hook(wired, "stop", {"session_id": "s-2", "stop_hook_active": True}).stdout.strip() == ""


def test_the_hooks_command(wired, hooks):
    env = {**os.environ, "CAMARONES_ROOT": str(wired.root)}
    out = subprocess.run([sys.executable, str(wired.kit_dir / "camarones.py"), "hooks", "on"], env=env,
                         capture_output=True, text=True, encoding="utf-8")
    assert out.returncode == 0 and wired.services.workspace.workspace()["hooks"]["method"] is True
    assert kit_hooks(wired)["Stop"]



# ---------- P1: retrieval by default (turning-point spec) ----------
PROMPT = "change how payments retry with backoff when the charge fails"


@pytest.fixture
def documented(wired, hooks):
    from test_prompt_context import PAGE
    page = wired.root / "docs" / "flows" / "payments.md"
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text(PAGE, encoding="utf-8", newline="\n")
    return wired


@pytest.fixture
def rh(documented):
    import importlib
    return importlib.import_module("lib.app.retrieval_hooks")


def edit(kit, session, path=None, transcript=None):
    target = path or kit.ws / "api" / "src" / "main" / "java" / "demo" / "Api.java"
    return {"session_id": session, "tool_name": "Edit", "tool_input": {"file_path": str(target)},
            "transcript_path": str(transcript or kit.ws / "no-transcript.jsonl")}


def test_the_prompt_hook_prints_the_docs_for_the_prompt(documented):
    r = run_hook(documented, "prompt", {"session_id": "s-1", "prompt": PROMPT})
    assert r.returncode == 0 and "flows/payments.md" in r.stdout and "exponential backoff" in r.stdout
    assert run_hook(documented, "prompt", {"session_id": "s-1", "prompt": "ok"}).stdout.strip() == ""


def test_an_edit_with_no_docs_consulted_is_stopped_once(documented, rh):
    code, text = rh.pre_edit(edit(documented, "s-2"))
    assert code == 2 and "flows/payments.md" in text and "api/src/main/java/demo/Api.java" in text
    assert rh.pre_edit(edit(documented, "s-2")) == (0, "")
    rep = rh.report()
    assert rep["edit_sessions"] == 1 and rep["consulted_first"] == 0 and rep["stops"] == 1


def test_an_injected_prompt_counts_as_consulted(documented, rh):
    assert rh.prompt({"session_id": "s-3", "prompt": PROMPT})
    assert rh.pre_edit(edit(documented, "s-3")) == (0, "")
    rep = rh.report()
    assert rep["prompts"] == 1 and rep["prompts_with_docs"] == 1
    assert rep["edit_sessions"] == 1 and rep["consulted_first"] == 1 and rep["stops"] == 0


def test_a_docs_tool_in_the_transcript_counts_as_consulted(documented, rh, tmp_path):
    t = tmp_path / "s-4.jsonl"
    use = {"type": "tool_use", "id": "t1", "name": "mcp__camarones__read_doc", "input": {"path": "flows/payments.md"}}
    t.write_text(json.dumps({"type": "user", "message": {"content": "hi"}}) + "\n"
                 + json.dumps({"type": "assistant", "message": {"content": [use]}}) + "\n", encoding="utf-8")
    assert rh.pre_edit(edit(documented, "s-4", transcript=t)) == (0, "")


def test_reading_a_docs_page_counts_as_consulted(documented, rh, tmp_path):
    t = tmp_path / "s-5.jsonl"
    page = str(documented.root / "docs" / "flows" / "payments.md")
    use = {"type": "tool_use", "id": "t1", "name": "Read", "input": {"file_path": page}}
    t.write_text(json.dumps({"type": "assistant", "message": {"content": [use]}}) + "\n", encoding="utf-8")
    assert rh.pre_edit(edit(documented, "s-5", transcript=t)) == (0, "")


def test_files_outside_the_service_repos_are_never_stopped(documented, rh):
    assert rh.pre_edit(edit(documented, "s-6", path=documented.root / "docs" / "flows" / "x.md")) == (0, "")
    assert rh.report()["edit_sessions"] == 0


def test_gate_off_keeps_the_prompt_hook_and_drops_the_stop(documented, rh):
    ws = documented.services.workspace.workspace()
    ws["hooks"] = {**(ws.get("hooks") or {}), "gate": False}
    documented.services.workspace.save_workspace(ws)
    assert rh.pre_edit(edit(documented, "s-7")) == (0, "")
    assert rh.prompt({"session_id": "s-7", "prompt": PROMPT})


def test_a_broken_payload_never_blocks(documented):
    env = {**os.environ, "CAMARONES_ROOT": str(documented.root)}
    r = subprocess.run([sys.executable, str(documented.kit_dir / "camarones.py"), "hook", "pre-edit"], env=env,
                       input="{not json", capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0
    assert run_hook(documented, "pre-edit", {"tool_input": {"file_path": 42}}).returncode == 0


# ---------- X7: compliance of what a unit writes ----------
GOOD = """---
type: business-flow
title: Checkout
description: How an order goes from the cart to a paid invoice, and what happens when the payment fails.
x-sources:
  - api:README.md
---
# Checkout

> **TL;DR:** The cart calls the payments service.

## Summary
S.

## Sequence
```mermaid
sequenceDiagram
  A->>B: pay
```

## Steps
1. Pay.

## Failure handling
Retry.

## Data touched
Orders.
"""


def test_compliance_score_is_deterministic(wired):
    from lib.harness import comply
    good = wired.root / "docs" / "flows" / "good.md"
    bad = wired.root / "docs" / "flows" / "bad.md"
    good.parent.mkdir(parents=True, exist_ok=True)
    good.write_text(GOOD, encoding="utf-8")
    bad.write_text("---\ntitle: Bad\nx-sources:\n  - api:nope.java\n---\nno heading\n", encoding="utf-8")
    s = comply.score(["flows/good.md", "flows/bad.md"])
    assert s["pages"] == 2 and s["compliant"] == 1 and s["score"] == 0.5
    assert s["by_page"]["flows/bad.md"]["orphan_sources"] == ["api:nope.java"]
    assert s["by_page"]["flows/good.md"]["issues"] == []


def test_comply_runs_one_unit_and_scores_what_it_wrote(wired, tmp_path, monkeypatch):
    import sys as _sys
    from test_scheduler import FAKE
    script = tmp_path / "fake.py"
    script.write_text(FAKE, encoding="utf-8")
    monkeypatch.setenv("FAKE_LOG", str(tmp_path / "fake.log"))
    monkeypatch.setenv("KIT_DIR", str(wired.kit_dir))
    monkeypatch.setenv("FAKE_SLEEP", "0.1")
    from lib.common import PREFS, save_json
    save_json(PREFS, {"runners": {"fake": {"argv": [_sys.executable, str(script), "ok"]}},
                      "routing": {"agentic-heavy": ["fake"]}})
    wired.plan.sync()
    wired.plan.set_status("setup", "done")
    from lib.harness import comply
    r = comply.run("discovery:api", echo=lambda _: None)
    assert r["status"] == "done" and r["written"] == ["notes/discovery-api.md"]
    assert r["pages"] == 1 and r["score"] == 0.0                      # the fake writes a page without TL;DR or type
    assert list((wired.root / "docs" / ".work" / "evals" / "comply").glob("*.json"))


def test_comply_refuses_a_unit_that_is_not_ready(wired):
    """Found on the sandbox: comply on repo-brief (waiting for discovery) printed '0 pages' and exit 0."""
    import pytest
    wired.plan.sync()
    from lib.harness import comply
    with pytest.raises(ValueError, match="discovery-cross"):
        comply.run("repo-brief:api", echo=lambda _: None)
    assert not list((wired.root / "docs" / ".work" / "evals" / "comply").glob("*.json"))


def test_comply_follows_links_to_pages_it_did_not_write(wired):
    """Found on the sandbox: the score checked links against the written pages only, so a brief linking its
    reference.md (written earlier) counted as broken while `check` was clean."""
    docs_dir = wired.root / "docs" / "flows"
    docs_dir.mkdir(parents=True, exist_ok=True)
    (docs_dir / "other.md").write_text("---\ntitle: Other\n---\n# Other\n", encoding="utf-8")
    (docs_dir / "good.md").write_text(GOOD.rstrip() + "\n\nSee [the other flow](other.md).\n", encoding="utf-8")
    from lib.harness import comply
    s = comply.score(["flows/good.md"])
    assert s["by_page"]["flows/good.md"]["issues"] == [], s
