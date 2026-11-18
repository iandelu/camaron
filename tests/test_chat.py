"""The Docs chat's picker (lib/chat.py): every runner installed on this machine with the models it can be asked for,
and the choice the panel opens with. Nothing here touches the machine's own tools: `which` and `ollama list` are
faked, and the one command runner is a script of the test's own."""
from __future__ import annotations

import importlib
import subprocess
import sys
from types import SimpleNamespace

import pytest

from test_app_api import TOKEN, app_server, call  # noqa: F401 — the app token server fixture

OLLAMA_LIST = (
    "NAME                ID              SIZE      MODIFIED\n"
    "llama3.2:latest     a80c4f17acd5    2.0 GB    2 weeks ago\n"
    "qwen2.5-coder:7b    dae161e27b0e    4.7 GB    3 days ago\n"
)
HAIKU, SONNET, OPUS = "haiku", "sonnet", "opus"
FAKE_RUNNER = {"argv": [sys.executable, "-c", "pass", "{prompt}"]}


@pytest.fixture
def machine(kit, monkeypatch):
    """What this machine has: `installed` names the commands `which` finds, `ollama` is what `ollama list` prints (or
    the exception it raises), `calls` the commands run through `out`."""
    from lib.common import PREFS, save_json
    state = SimpleNamespace(installed=set(), ollama="", calls=[], timeouts=[], kit=kit)

    def which(name):
        return f"/fake/{name}" if name in state.installed else None

    def out(cmd, cwd=None, timeout=None):
        state.calls.append(list(cmd))
        state.timeouts.append(timeout)
        if isinstance(state.ollama, BaseException):
            raise state.ollama
        return state.ollama

    for target in ("lib.agents.which", "lib.plan.which", "lib.core.process.which"):
        monkeypatch.setattr(target, which)
    monkeypatch.setattr("lib.core.process.out", out)

    def install(*names, fake=False):
        state.installed |= set(names)
        if fake:
            state.installed.add(sys.executable)
            prefs(runners={"fake": FAKE_RUNNER})

    def prefs(**keys):
        from lib.core.fsutil import load_json
        save_json(PREFS, {**load_json(PREFS, {}), **keys})

    def workspace(**keys):
        ws = kit.services.workspace.workspace()
        ws.update(keys)
        kit.services.workspace.save_workspace(ws)

    state.install, state.prefs, state.workspace, state.PREFS = install, prefs, workspace, PREFS
    return state


@pytest.fixture
def chat(machine):
    return importlib.import_module("lib.chat")


def by_runner(listing):
    return {r["runner"]: r for r in listing}


def ids(entry):
    return [m["id"] for m in entry["models"]]


def test_claude_offers_its_three_models_and_no_unset_one(machine, chat):
    machine.install("claude")
    listing = chat.models()
    assert [r["runner"] for r in listing] == ["claude"] and listing[0]["label"] == "Claude Code"
    assert listing[0]["models"] == [{"id": m, "label": m, "local": False} for m in (HAIKU, SONNET, OPUS)]
    assert "" not in ids(listing[0])


def test_a_command_runner_has_one_default_entry(machine, chat):
    machine.install(fake=True)
    only = by_runner(chat.models())["fake"]
    assert only["models"] == [{"id": "", "label": "default", "local": False}]
    machine.prefs(fake_model="fast-1")
    assert ids(by_runner(chat.models())["fake"]) == ["fast-1"]


def test_codex_has_its_configured_model_as_its_default_entry(machine, chat):
    machine.install("codex")
    from lib import agents
    assert by_runner(chat.models())["codex"]["models"] == [
        {"id": agents.CODEX_MODEL_DEFAULT, "label": "default", "local": False}]
    machine.prefs(codex_model="gpt-x")
    assert by_runner(chat.models())["codex"]["models"] == [{"id": "gpt-x", "label": "default", "local": False}]


def test_every_installed_runner_is_listed_even_when_routing_ignores_it(machine, chat):
    machine.install("claude", "codex", fake=True)
    machine.prefs(routing={"bounded": ["claude"]})
    assert [r["runner"] for r in chat.models()] == ["claude", "codex", "fake"]


def test_opencode_lists_the_ollama_tags_as_local_models(machine, chat):
    machine.install("opencode", "ollama")
    machine.ollama = OLLAMA_LIST
    entry = by_runner(chat.models())["opencode"]
    assert entry["models"] == [
        {"id": "ollama/llama3.2:latest", "label": "llama3.2:latest", "local": True},
        {"id": "ollama/qwen2.5-coder:7b", "label": "qwen2.5-coder:7b", "local": True}]
    assert machine.calls == [["ollama", "list"]]


def test_opencode_without_ollama_has_the_single_default(machine, chat):
    machine.install("opencode")
    machine.ollama = OLLAMA_LIST
    assert by_runner(chat.models())["opencode"]["models"] == [{"id": "", "label": "default", "local": False}]
    assert machine.calls == []


def test_ollama_without_opencode_adds_nothing(machine, chat):
    machine.install("claude", "ollama")
    machine.ollama = OLLAMA_LIST
    assert [r["runner"] for r in chat.models()] == ["claude"] and machine.calls == []


@pytest.mark.parametrize("printed", [
    "",
    "NAME  ID  SIZE  MODIFIED\n",
    "Error: could not connect to ollama app, is it running?\n",
    '{"models": [{"name": "llama3.2:latest"}]}\n',
    "llama3.2:latest   a80c4f17acd5   2.0 GB   2 weeks ago\n",
    OSError("ollama is blocked here"),
    subprocess.TimeoutExpired(["ollama", "list"], 5),
    RuntimeError("command failed"),
], ids=["empty", "header-only", "error-text", "json", "no-header", "oserror", "timeout", "runtimeerror"])
def test_an_ollama_list_that_fails_or_is_odd_leaves_the_single_default(machine, chat, printed):
    machine.install("opencode", "ollama")
    machine.ollama = printed
    assert by_runner(chat.models())["opencode"]["models"] == [{"id": "", "label": "default", "local": False}]


def test_ollama_list_is_run_with_a_short_bound(machine, chat):
    machine.install("opencode", "ollama")
    machine.ollama = OLLAMA_LIST
    chat.models()
    assert machine.timeouts == [5]                                   # a hung `ollama list` must not hold the picker


def test_every_offered_id_is_one_the_turn_will_accept(machine, chat):
    machine.install("claude", "codex", "opencode", "ollama", fake=True)
    machine.ollama = OLLAMA_LIST
    offered = [i for r in chat.models() for i in ids(r)]
    assert offered and all(i == "" or chat.MODEL_SHAPE.fullmatch(i) for i in offered)
    assert chat.MODEL_SHAPE.fullmatch("ollama/llama3.2:latest") and chat.MODEL_SHAPE.fullmatch("gpt-5.6")
    assert not any(chat.MODEL_SHAPE.fullmatch(bad) for bad in ("", "-rf", "a b", "a;b", "a\nb", "a\n", "$(x)", "a`b`"))
    machine.prefs(codex_model="-rf", fake_model="a b")                  # a hand-edited model the turn would refuse
    offered = {r["runner"]: ids(r) for r in chat.models()}
    assert (offered["codex"], offered["fake"]) == ([""], [""])
    assert all(i == "" or chat.MODEL_SHAPE.fullmatch(i) for i in [i for r in chat.models() for i in ids(r)])


def test_nothing_installed_offers_nothing(machine, chat):
    assert chat.models() == []
    machine.prefs(chat={"runner": "claude", "model": OPUS})
    assert chat.remembered() is None and chat.default_choice() is None
    assert machine.calls == []


def test_remember_keeps_every_other_key(machine, chat):
    machine.prefs(lang="en", model="opus", runners={"fake": FAKE_RUNNER}, routing={"bounded": ["fake"]})
    chat.remember("claude", SONNET)
    from lib.core.fsutil import load_json
    saved = load_json(machine.PREFS, {})
    assert saved["chat"] == {"runner": "claude", "model": SONNET}
    assert (saved["lang"], saved["model"], saved["routing"]) == ("en", "opus", {"bounded": ["fake"]})
    assert saved["runners"] == {"fake": FAKE_RUNNER}


def test_an_unset_model_is_stored_as_an_empty_one(machine, chat):
    chat.remember("fake", None)
    from lib.core.fsutil import load_json
    assert load_json(machine.PREFS, {})["chat"] == {"runner": "fake", "model": ""}
    machine.install(fake=True)
    assert chat.remembered() == {"runner": "fake", "model": ""}


def test_remembered_is_what_was_picked_while_it_is_still_offered(machine, chat):
    machine.install("claude", "opencode", "ollama")
    machine.ollama = OLLAMA_LIST
    chat.remember("opencode", "ollama/qwen2.5-coder:7b")
    assert chat.remembered() == {"runner": "opencode", "model": "ollama/qwen2.5-coder:7b"}


def test_remembered_is_dropped_when_its_runner_is_gone(machine, chat):
    machine.install("claude")
    chat.remember("codex", "gpt-x")
    assert chat.remembered() is None
    chat.remember("claude", OPUS)
    machine.installed.clear()
    assert chat.remembered() is None


def test_remembered_is_dropped_when_its_model_vanished(machine, chat):
    machine.install("claude", "opencode", "ollama")
    machine.ollama = OLLAMA_LIST
    chat.remember("opencode", "ollama/qwen2.5-coder:7b")
    machine.ollama = "NAME  ID  SIZE  MODIFIED\nllama3.2:latest   a80c4f17acd5   2.0 GB   2 weeks ago\n"
    assert chat.remembered() is None
    chat.remember("claude", "opus-9")
    assert chat.remembered() is None


def test_a_runner_with_one_default_keeps_its_remembered_pick(machine, chat):
    machine.install("codex", fake=True)
    chat.remember("fake", "")
    assert chat.remembered() == {"runner": "fake", "model": ""}
    machine.prefs(codex_model="gpt-new")
    chat.remember("codex", "gpt-old")                                  # the machine's configured model changed since
    assert chat.remembered() == {"runner": "codex", "model": "gpt-new"}


def test_a_remembered_local_pick_does_not_fall_to_the_clis_own_default(machine, chat):
    machine.install("claude", "opencode", "ollama")
    machine.ollama = OLLAMA_LIST
    chat.remember("opencode", "ollama/qwen2.5-coder:7b")
    machine.ollama = ""                                                # Ollama quit: every tag is gone at once
    assert by_runner(chat.models())["opencode"]["models"] == [{"id": "", "label": "default", "local": False}]
    assert chat.remembered() is None
    chat.remember("opencode", None)                                    # an unset pick still matches an unset default
    assert chat.remembered() == {"runner": "opencode", "model": ""}


def test_an_ollama_tag_named_default_is_not_taken_for_a_default_entry(machine, chat):
    machine.install("opencode", "ollama")
    machine.ollama = "NAME  ID  SIZE  MODIFIED\ndefault   a80c4f17acd5   2.0 GB   now\n"
    chat.remember("opencode", "ollama/gone")
    assert chat.remembered() is None


@pytest.mark.parametrize("saved", ["claude", ["claude", OPUS], {"runner": "claude"}, {"runner": 1, "model": OPUS},
                                   {"runner": "claude", "model": 7}, {"model": OPUS}, None])
def test_a_hand_edited_choice_is_ignored(machine, chat, saved):
    machine.install("claude")
    machine.prefs(chat=saved)
    assert chat.remembered() is None


def test_the_first_choice_is_the_first_runners_cheap_entry(machine, chat):
    machine.install("claude", "codex")
    assert chat.default_choice() == {"runner": "claude", "model": HAIKU}
    machine.installed.discard("claude")
    from lib import agents
    assert chat.default_choice() == {"runner": "codex", "model": agents.CODEX_MODEL_DEFAULT}


def test_the_first_choice_of_a_lone_command_runner_or_local_runner_is_its_first_entry(machine, chat):
    machine.install(fake=True)
    assert chat.default_choice() == {"runner": "fake", "model": ""}
    machine.installed.clear()
    machine.install("opencode", "ollama")
    machine.ollama = OLLAMA_LIST
    assert chat.default_choice() == {"runner": "opencode", "model": "ollama/llama3.2:latest"}


def test_a_bad_routing_tier_does_not_take_the_picker_down(machine, chat):
    machine.install("claude", "codex")
    machine.prefs(routing={"nonsense": ["codex"]})                     # routing.table refuses a tier it does not know
    from lib import answers
    with pytest.raises(ValueError):
        answers.runner()
    assert chat.default_choice() == {"runner": "claude", "model": HAIKU}


def test_ask_comes_before_the_first_cheap_entry(machine, chat):
    machine.install("claude", fake=True)
    machine.prefs(routing={"bounded": ["fake"]})
    assert chat.default_choice() == {"runner": "fake", "model": ""}


def test_ask_brings_its_model_and_its_own_route_model(machine, chat):
    machine.install("claude")
    assert chat.default_choice() == {"runner": "claude", "model": HAIKU}               # Ask's cheap model for Claude
    machine.workspace(ask={"model": SONNET})
    assert chat.default_choice() == {"runner": "claude", "model": SONNET}              # ask.model applies here too
    machine.workspace(ask={})
    machine.prefs(routing={"bounded": ["claude:opus"]})
    assert chat.default_choice() == {"runner": "claude", "model": OPUS}                # the route names its own


def test_the_panel_never_opens_on_a_model_it_does_not_offer(machine, chat):
    machine.install("claude", "codex", fake=True)
    machine.prefs(routing={"bounded": ["claude"]})
    machine.workspace(ask={"model": "claude-9-future"})                                 # outside Claude's three
    assert chat.default_choice() == {"runner": "claude", "model": HAIKU}
    machine.prefs(routing={"bounded": ["codex"]})                                       # Ask leaves Codex's to the CLI
    from lib import agents
    assert chat.default_choice() == {"runner": "codex", "model": agents.CODEX_MODEL_DEFAULT}
    machine.workspace(ask={"model": SONNET})
    machine.prefs(routing={"bounded": ["fake"]})                                        # a command runner: its own only
    assert chat.default_choice() == {"runner": "fake", "model": ""}


def test_remembered_comes_before_ask(machine, chat):
    machine.install("claude", fake=True)
    machine.prefs(routing={"bounded": ["fake"]})
    chat.remember("claude", OPUS)
    assert chat.default_choice() == {"runner": "claude", "model": OPUS}
    machine.prefs(chat={"runner": "claude", "model": "gone"})                          # a remembered pick that vanished
    assert chat.default_choice() == {"runner": "fake", "model": ""}


def test_ask_turned_off_falls_to_the_first_cheap_entry(machine, chat):
    machine.install("claude", fake=True)
    machine.prefs(routing={"bounded": ["fake"]})
    machine.workspace(ask={"ai": False})
    assert chat.default_choice() == {"runner": "claude", "model": HAIKU}


def test_an_ask_runner_that_is_not_offered_is_skipped(machine, chat, monkeypatch):
    machine.install("claude")
    from lib import answers
    monkeypatch.setattr(answers, "runner", lambda: "ghost:big")
    assert chat.default_choice() == {"runner": "claude", "model": HAIKU}


def test_the_route_needs_the_app_token_and_answers_with_the_picker(machine, app_server):  # noqa: F811
    machine.install("claude", "opencode", "ollama")
    machine.ollama = OLLAMA_LIST
    url = app_server + "/api/app/chat/models"
    code, body = call(url)
    assert (code, body.get("app")) == (403, True)
    code, body = call(url, token=TOKEN)
    assert code == 200 and set(body) == {"runners", "choice", "ai"}
    assert [r["runner"] for r in body["runners"]] == ["claude", "opencode"]
    assert ids(by_runner(body["runners"])["opencode"]) == ["ollama/llama3.2:latest", "ollama/qwen2.5-coder:7b"]
    assert body["choice"] == {"runner": "claude", "model": HAIKU} and body["ai"] is True
    assert machine.calls == [["ollama", "list"]]                          # one listing serves the models and the choice


def test_the_route_says_when_ask_ai_is_off(machine, app_server):  # noqa: F811
    machine.install("claude")
    url = app_server + "/api/app/chat/models"
    machine.workspace(ask={"ai": False})
    assert call(url, token=TOKEN)[1]["ai"] is False
    machine.workspace(ask={"ai": True})
    assert call(url, token=TOKEN)[1]["ai"] is True
    machine.workspace(ask=None)
    assert call(url, token=TOKEN)[1]["ai"] is True


def test_the_route_survives_a_bad_routing_tier(machine, app_server):  # noqa: F811
    machine.install("claude", "codex")
    machine.prefs(routing={"nonsense": ["codex"]})
    code, body = call(app_server + "/api/app/chat/models", token=TOKEN)
    assert code == 200 and body["choice"] == {"runner": "claude", "model": HAIKU}
    assert [r["runner"] for r in body["runners"]] == ["claude", "codex"]


def test_the_route_with_nothing_installed_is_empty_not_an_error(machine, app_server):  # noqa: F811
    code, body = call(app_server + "/api/app/chat/models", token=TOKEN)
    assert code == 200 and body == {"runners": [], "choice": None, "ai": True}
