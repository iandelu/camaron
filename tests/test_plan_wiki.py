"""Work plan units and the OpenWiki run lifecycle (choice of repos, brief requirement, open/close, one run at a time)."""
from __future__ import annotations

import importlib, json, os

import pytest


def unit(data, uid):
    return next(u for u in data["units"] if u["id"] == uid)


# ---------- plan ----------
def test_wiki_units_only_for_the_chosen_repos(kit):
    plan, store = kit.plan, kit.services.workspace
    data = plan.sync()
    assert unit(data, "repo-wiki:api")["status"] == "dropped"
    assert unit(data, "repo-wiki:api")["notes"] == plan.NO_WIKI
    store.set_wiki_repos(["api"])
    data = plan.sync()
    assert unit(data, "repo-wiki:api")["status"] == "todo" and unit(data, "repo-wiki:api")["notes"] == ""
    assert unit(data, "repo-wiki:web")["status"] == "dropped"


def test_no_wiki_units_without_the_openwiki_component(kit):
    kit.services.workspace.set_wiki_repos(["api"])
    kit.services.components.set_components(["likec4", "agents"])
    assert unit(kit.plan.sync(), "repo-wiki:api")["notes"] == "OpenWiki not selected"


@pytest.mark.parametrize("note", ["OpenWiki not selected", "No wiki for this repo (wizard → Wikis → choose repos)",
                                  "dropped by hand"])
def test_picking_openwiki_again_brings_back_its_units(kit, note):
    """C3 (spec 2026-11-18 §6.5): a machine's choice that an older join shared is not repaired by itself; the team
    picks the component again and every unit dropped for it comes back, whatever its note."""
    plan, comps = kit.plan, kit.services.components
    kit.services.workspace.set_wiki_repos(["api"])
    comps.set_components(["likec4", "agents"])
    data = plan.sync()
    u = unit(data, "repo-wiki:api")
    u["status"], u["notes"] = "dropped", note
    plan.save(data)
    comps.set_components(comps.ALL_COMPONENTS)
    u = unit(plan.sync(), "repo-wiki:api")
    assert u["status"] == "todo"
    assert u["notes"] == ("" if note in (plan.NO_WIKI, plan.NO_OPENWIKI) else note)


def test_sync_keeps_progress_and_drops_removed_repos(kit):
    plan, store = kit.plan, kit.services.workspace
    plan.sync()
    plan.set_status("discovery:web", "done")
    ws = store.workspace()
    ws["repos"] = [r for r in ws["repos"] if r["name"] != "worker"]
    store.save_workspace(ws)
    data = plan.sync()
    assert unit(data, "discovery:web")["status"] == "done"
    assert unit(data, "discovery:worker")["status"] == "dropped"


def test_restoring_a_failed_run_is_not_a_transition(kit):
    plan = kit.plan
    plan.sync()
    stamp = plan.set_status("setup", "doing")["updated"]
    plan.set_status("setup", "todo", record=False)
    u = unit(plan.load(), "setup")
    assert u["status"] == "todo" and u["updated"] == stamp
    assert not plan.LOG.exists()
    plan.set_status("setup", "done")
    assert "**setup** → done" in plan.LOG.read_text(encoding="utf-8")


def test_available_follows_dependencies(kit):
    plan = kit.plan
    plan.sync()
    assert [u["id"] for u in plan.available()] == ["setup"]
    plan.set_status("setup", "done")
    ids = [u["id"] for u in plan.available()]
    assert {"discovery:api", "discovery:web", "discovery:worker"} <= set(ids)
    assert "discovery-cross" not in ids


# ---------- OpenWiki ----------
def test_close_without_open_is_a_no_op(wired):
    agents = wired.ws / "api" / "AGENTS.md"
    agents.write_text("the repo's own", encoding="utf-8")
    assert wired.services.wiki_engine.wiki_close("api", log=lambda _: None) is False
    assert agents.read_text(encoding="utf-8") == "the repo's own"


def test_open_close_round_trip_restores_the_repo(wired):
    wiki, links, repo = wired.services.wiki_engine, wired.services.links, wired.ws / "api"
    claude_before = (repo / "CLAUDE.md").read_text(encoding="utf-8")
    wiki.wiki_open("api", log=lambda _: None)
    ow = repo / "openwiki"
    assert ow.is_dir() and not links._is_link(ow)
    (ow / "index.md").write_text("# api wiki\n", encoding="utf-8")        # what OpenWiki writes during the run
    (repo / "AGENTS.md").write_text("openwiki snippet", encoding="utf-8")
    (repo / "CLAUDE.md").write_text("openwiki snippet", encoding="utf-8")
    (repo / ".github" / "workflows").mkdir(parents=True)
    (repo / ".github" / "workflows" / "openwiki-update.yml").write_text("on: push", encoding="utf-8")
    assert wiki.wiki_close("api", log=lambda _: None) is True
    assert (wired.root / "wikis" / "api" / "index.md").is_file()
    assert links._is_link(ow)
    assert not (repo / "AGENTS.md").exists() and not (repo / ".github").exists()
    assert (repo / "CLAUDE.md").read_text(encoding="utf-8") == claude_before
    assert wiki.wiki_close("api", log=lambda _: None) is False               # a second close changes nothing


@pytest.mark.parametrize("ending", [b"\n", b"\r\n"])
def test_close_restores_the_repos_files_byte_for_byte(wired, ending):
    """A close used to write the saved text back with the platform's line endings: on Windows an LF AGENTS.md came
    back CRLF (same content, every line changed), and a CRLF one came back LF everywhere."""
    ow, repo = wired.services.wiki_engine, wired.ws / "api"
    own = ending.join([b"# api", b"", b"Rules for agents \xe2\x80\x94 ours.", b""])
    (repo / "AGENTS.md").write_bytes(own)
    (repo / "CLAUDE.md").write_bytes(own)
    ow.wiki_open("api", log=lambda _: None)
    (repo / "AGENTS.md").write_text("openwiki snippet\n", encoding="utf-8")   # OpenWiki rewrites one, leaves the other
    assert ow.wiki_close("api", log=lambda _: None) is True
    assert (repo / "AGENTS.md").read_bytes() == own
    assert (repo / "CLAUDE.md").read_bytes() == own


def test_close_reads_a_state_saved_by_an_older_kit(wired):
    """Kits up to 4.80.1 saved the files as universal-newline text: a close still restores them, with LF."""
    ow, repo = wired.services.wiki_engine, wired.ws / "api"
    state = wired.root / ".camarones" / ".cache" / "wiki-open" / "api.json"
    ow.wiki_open("api", log=lambda _: None)
    state.write_text(json.dumps({"AGENTS.md": "# api\nold kit\n", "CLAUDE.md": None,
                                 ".github/workflows/openwiki-update.yml": None}), encoding="utf-8")
    (repo / "AGENTS.md").write_text("openwiki snippet\n", encoding="utf-8")
    assert ow.wiki_close("api", log=lambda _: None) is True
    assert (repo / "AGENTS.md").read_bytes() == b"# api\nold kit\n"


def test_brief_is_not_a_page(wired):
    wiki = wired.root / "wikis" / "web"
    (wiki / "INSTRUCTIONS.md").write_text("brief", encoding="utf-8")
    assert wired.services.wiki.wiki_pages("web") == [] and wired.services.wiki.wiki_brief_ready("web")
    (wiki / "overview.md").write_text("# overview", encoding="utf-8")
    assert [p.name for p in wired.services.wiki.wiki_pages("web")] == ["overview.md"]
    assert "repos/web/INSTRUCTIONS.md" not in [l for l, _ in wired.services.docs.iter_docs()]


def test_one_wiki_run_at_a_time(wired, monkeypatch):
    paths, ow = importlib.import_module("lib.core.paths"), wired.services.wiki_engine
    paths.WIKI_LOCK.parent.mkdir(parents=True, exist_ok=True)
    paths.WIKI_LOCK.write_text('{"pid": 999999, "repo": "web"}', encoding="utf-8")
    from lib.core import locks                                            # liveness moved there with the shared FileLock
    monkeypatch.setattr(locks, "pid_alive", lambda pid: True)
    with pytest.raises(RuntimeError, match="another OpenWiki run"):
        with ow.wiki_lock("api"):
            pass
    monkeypatch.setattr(locks, "pid_alive", lambda pid: False)            # a dead holder does not block
    with ow.wiki_lock("api"):
        assert f'"pid": {os.getpid()}' in paths.WIKI_LOCK.read_text(encoding="utf-8")
    assert not paths.WIKI_LOCK.exists()


@pytest.fixture
def engine(wired, monkeypatch):
    """A fake headless engine: `rc` is its exit code; with rc 0 it writes one page into the real openwiki/ folder."""
    wk, box = wired.services.wiki, {"rc": 0, "calls": 0}

    def stream(cmd, cwd, log, env_=None):
        box["calls"] += 1
        if box["rc"] == 0:
            (wired.ws / "api" / "openwiki" / "index.md").write_text("# api\n", encoding="utf-8")
        log("session limit reached" if box["rc"] else "ok")
        return box["rc"]
    monkeypatch.setattr(wk, "wiki_engines", lambda: ["claude"])
    mcp = wired.root / ".mcp.json"                                       # setup connected OpenWiki to the agents
    cfg = json.loads(mcp.read_text(encoding="utf-8"))
    cfg["mcpServers"]["openwiki"] = {"command": "openwiki", "args": ["mcp", "--host", "claude"]}
    mcp.write_text(json.dumps(cfg), encoding="utf-8")
    monkeypatch.setattr(wk, "stream", stream)
    monkeypatch.setattr(wk, "wiki_graph", lambda *a, **kw: True)
    monkeypatch.setattr(wired.services.share, "checkpoint_commit", lambda *a, **kw: True)
    wired.services.workspace.set_wiki_repos(["api"])
    wired.plan.sync()
    return box


def test_first_wiki_needs_the_brief(wired, engine):
    with pytest.raises(RuntimeError, match="INSTRUCTIONS.md"):
        wired.services.wiki.openwiki_generate("api", log=lambda _: None)
    assert engine["calls"] == 0
    assert wired.services.wiki.openwiki_generate("api", log=lambda _: None, force=True) is True
    assert unit(wired.plan.load(), "repo-wiki:api")["status"] == "done"
    assert wired.services.links._is_link(wired.ws / "api" / "openwiki")


def test_engine_down_aborts_and_restores_the_unit(wired, engine):
    engine["rc"] = 1
    (wired.root / "wikis" / "api" / "INSTRUCTIONS.md").write_text("brief", encoding="utf-8")
    with pytest.raises(wired.services.wiki.WikiAbort):
        wired.services.wiki.openwiki_generate("api", log=lambda _: None)
    u = unit(wired.plan.load(), "repo-wiki:api")
    assert u["status"] == "todo"
    assert "repo-wiki:api" not in (wired.plan.LOG.read_text(encoding="utf-8") if wired.plan.LOG.exists() else "")
    assert not importlib.import_module("lib.core.paths").WIKI_LOCK.exists()
    assert wired.services.links._is_link(wired.ws / "api" / "openwiki")             # the repo is put back even on failure


@pytest.fixture
def engine_down(kit, monkeypatch):
    """An engine that cannot run at all (quota, login): `openwiki_generate` raises WikiAbort; returns the repos asked."""
    wk, asked = kit.services.wiki, []

    def generate(repo, mode="", log=print, engine="", force=False):
        asked.append(repo)
        raise wk.WikiAbort("claude cannot run right now — session limit reached")
    monkeypatch.setattr(wk, "openwiki_generate", generate)        # where the CLI and the wizard look it up
    return asked


def test_cli_wiki_stops_the_batch_when_the_engine_is_down(kit, engine_down, capsys):
    from lib.interfaces.cli import main
    assert main.main(["wiki", "api", "web", "worker"]) == 1
    assert engine_down == ["api"]                                    # the rest would fail the same way: not started
    assert capsys.readouterr().err == ("✖ claude cannot run right now — session limit reached\n"
                                       "  not started: web, worker\n")
    assert main.main(["wiki", "web"]) == 1                           # the last repo: nothing left to name
    assert capsys.readouterr().err == "✖ claude cannot run right now — session limit reached\n"


def test_wizard_wikis_stop_the_batch_when_the_engine_is_down(kit, engine_down, fake_wizard, monkeypatch, capsys):
    kit.services.workspace.set_wiki_repos(["api", "web"])
    for r in ("api", "web"):                                         # each has its brief: both can be picked
        brief = kit.services.docs.wiki_dir(r) / "INSTRUCTIONS.md"
        brief.parent.mkdir(parents=True, exist_ok=True)
        brief.write_text("brief", encoding="utf-8")
    monkeypatch.setattr(kit.services.wiki, "wiki_engines", lambda: ["claude"])
    w = fake_wizard(["gen", ["api", "web"], None])                   # generate both, then leave the menu
    w.do_wikis()
    assert engine_down == ["api"]
    out = capsys.readouterr().out
    assert "claude cannot run right now — session limit reached" in out and w.t("w_skipped", repos="web") in out
    assert w.t("w_fail", repo="api") not in out                      # an engine that is down is not this repo failing


# ---------- wiki scope: complete wikis, and a warning for the ones written under the old, narrow scope ----------
def test_the_wiki_prompt_asks_for_a_complete_wiki(wired):
    p = wired.services.wiki.wiki_prompt("api", "init")
    assert "Coverage" in p and "do not restate" not in p
    assert "docs/" in p                                           # still points at the cross-repo docs, to link not copy


def test_a_generated_wiki_is_stamped_with_the_current_scope(wired, engine):
    wk = wired.services.wiki
    assert wk.openwiki_generate("api", log=lambda _: None, force=True) is True
    assert wk.wiki_scope("api") == wk.WIKI_SCOPE
    assert not {w["repo"]: w for w in wk.wikis()}["api"]["old"]


def test_an_unstamped_wiki_is_old_warned_and_expanded_on_update(wired, engine, monkeypatch):
    wk, wiki = wired.services.wiki, wired.root / "wikis" / "api"
    (wiki / "INSTRUCTIONS.md").write_text("brief", encoding="utf-8")
    (wiki / "index.md").write_text("# api\n", encoding="utf-8")          # written by a kit before scope stamps
    assert wk.wiki_scope("api") == 1
    assert {w["repo"]: w for w in wk.wikis()}["api"]["old"]
    assert any("wikis/api" in w and "older" in w for w in wired.services.doc_status.check()[1])
    assert "Expand" in wk.wiki_prompt("api", "update")
    prompts = []
    real = wk.stream
    monkeypatch.setattr(wk, "stream", lambda cmd, cwd, log, env_=None: prompts.append(cmd[2]) or real(cmd, cwd, log))
    assert wk.openwiki_generate("api", log=lambda _: None) is True
    assert "Expand" in prompts[0]
    assert not {w["repo"]: w for w in wk.wikis()}["api"]["old"]
    assert not any("wikis/api" in w and "older" in w for w in wired.services.doc_status.check()[1])


def test_openwiki_own_engine_counts_as_complete_only_with_a_coverage_brief(wired, engine, monkeypatch):
    wk, brief = wired.services.wiki, wired.root / "wikis" / "api" / "INSTRUCTIONS.md"
    monkeypatch.setattr(wk, "wiki_engines", lambda: ["openwiki"])      # OpenWiki's agent reads the brief, not our prompt
    brief.write_text("# brief\n", encoding="utf-8")
    assert wk.openwiki_generate("api", log=lambda _: None) is True
    assert wk.wiki_old("api")
    brief.write_text("# brief\n\n## Coverage\n- one page per endpoint group\n", encoding="utf-8")
    assert wk.openwiki_generate("api", log=lambda _: None) is True
    assert not wk.wiki_old("api")


# ---------- a wiki written by an agent is a run of its own, with its tokens and cost ----------
@pytest.fixture
def engine_streaming(wired, engine, monkeypatch):
    """The fake engine, now speaking Claude Code's stream-json: one tool call, then the result with its usage."""
    wk = wired.services.wiki
    lines = [{"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Write",
                                                            "input": {"file_path": "openwiki/index.md"}}]}},
             {"type": "result", "result": "done", "total_cost_usd": 0.42,
              "usage": {"input_tokens": 100, "output_tokens": 20, "cache_read_input_tokens": 5}}]

    def stream(cmd, cwd, log, env_=None):
        (wired.ws / "api" / "openwiki" / "index.md").write_text("# api\n", encoding="utf-8")
        for line in lines:
            log(json.dumps(line))
        return 0
    monkeypatch.setattr(wk, "stream", stream)
    return engine


def test_a_wiki_by_an_agent_is_a_run_with_its_cost(wired, engine_streaming):
    shown = []
    assert wired.services.wiki.openwiki_generate("api", log=shown.append, force=True) is True
    from lib.harness import runs
    rid = runs.ids()[0]
    assert rid.endswith("-wiki-api") and runs.ids(wiki=False) == []
    s = runs.summary(rid)
    assert (s["cost_usd"], s["tokens_in"], s["done"], s["finished"]) == (0.42, 100, 1, True)
    u = runs.detail(rid)["units"][0]
    assert (u["unit"], u["runner"], u["outcome"]) == ("repo-wiki:api", "claude", "ok")
    assert not any(l.startswith("{") for l in shown)                     # progress, not raw JSON
    assert any("Write" in l for l in shown)


def test_openwikis_own_engine_writes_no_run(wired, engine, monkeypatch):
    monkeypatch.setattr(wired.services.wiki, "wiki_engines", lambda: ["openwiki"])
    (wired.root / "wikis" / "api" / "INSTRUCTIONS.md").write_text("# brief\n", encoding="utf-8")
    assert wired.services.wiki.openwiki_generate("api", log=lambda _: None) is True
    from lib.harness import runs
    assert runs.ids() == []


def test_a_run_log_that_cannot_be_written_never_breaks_the_wiki(wired, engine_streaming, monkeypatch):
    from lib.harness.events import EventLog

    def full(self, *a, **kw):
        raise OSError("no space left on device")
    monkeypatch.setattr(EventLog, "emit", full)
    assert wired.services.wiki.openwiki_generate("api", log=lambda _: None, force=True) is True
    assert unit(wired.plan.load(), "repo-wiki:api")["status"] == "done"


def test_a_wiki_that_crashes_still_closes_its_run(wired, engine_streaming, monkeypatch):
    def boom(cmd, cwd, log, env_=None):
        raise RuntimeError("engine crashed")
    monkeypatch.setattr(wired.services.wiki, "stream", boom)
    with pytest.raises(RuntimeError):
        wired.services.wiki.openwiki_generate("api", log=lambda _: None, force=True)
    from lib.harness import runs
    s = runs.summary(runs.ids()[0])
    assert s["finished"] is True and s["failed"] == 1
