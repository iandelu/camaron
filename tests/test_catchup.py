import json, threading
from test_team_repo import bare, git, publish
from test_share_pull import mate_commits

def fake_c4(kit, monkeypatch, state):
    # the kit's modules are imported afresh for each test: patch the ones this test's services carry
    built = []
    monkeypatch.setattr(kit.services.viewers, "viewers", lambda: {"c4": state, "graphs": {}, "graphify": False, "likec4": True})
    monkeypatch.setattr(kit.services.viewers, "build_c4", lambda dest=None, log=print: built.append(1) or True)
    monkeypatch.setattr(kit.services.catchup, "which", lambda name: "/bin/" + name)
    return built

def test_a_teammates_c4_edit_rebuilds_the_explorer(kit, tmp_path, monkeypatch):
    remote = bare(tmp_path); publish(kit, remote)
    mate_commits(kit, remote, tmp_path, "docs/architecture/model.c4", "model {\n}\n")
    built = fake_c4(kit, monkeypatch, {"exists": True, "stale": True, "model": True})
    r = kit.services.catchup.run(log=lambda _: None)
    assert r["status"] == "done" and r["pull"]["status"] == "pulled" and r["views"]["c4"] == "built" and built

def test_a_fresh_explorer_is_left_alone(kit, tmp_path, monkeypatch):
    publish(kit, bare(tmp_path))
    built = fake_c4(kit, monkeypatch, {"exists": True, "stale": False, "model": True})
    assert kit.services.catchup.run(log=lambda _: None)["views"]["c4"] == "fresh" and not built

def test_it_never_writes_team_decisions_and_never_pushes(kit, tmp_path, monkeypatch):
    remote = bare(tmp_path); publish(kit, remote); mate_commits(kit, remote, tmp_path)
    fake_c4(kit, monkeypatch, {"exists": False, "stale": False, "model": False})
    (kit.root / "docs" / "mine.md").write_text("# Mine\n", encoding="utf-8"); kit.services.share.checkpoint_commit("mine")
    watched = [kit.root / ".camarones" / "workspace.yaml", kit.plan.PLAN]
    before = [p.read_bytes() if p.exists() else None for p in watched]
    head_remote = git(remote, "rev-parse", "main")
    kit.services.catchup.run(log=lambda _: None)
    assert [p.read_bytes() if p.exists() else None for p in watched] == before
    assert git(remote, "rev-parse", "main") == head_remote

def test_a_run_in_progress_skips_the_pull_not_the_views(kit, tmp_path, monkeypatch):
    publish(kit, bare(tmp_path))
    import lib.harness.scheduler as sch
    monkeypatch.setattr(sch, "busy", lambda: {"what": "autopilot"})
    fake_c4(kit, monkeypatch, {"exists": True, "stale": True, "model": True})
    r = kit.services.catchup.run(log=lambda _: None)
    assert (r["pull"]["status"], r["pull"]["detail"]) == ("busy", "run") and r["views"]["c4"] == "built"

def test_offline_ends_with_a_reason_and_raises_nothing(kit, tmp_path, monkeypatch):
    kit.services.templates.init_templates("demo", log=lambda _: None)
    kit.services.share.set_remote(str(tmp_path / "gone.git")); kit.services.share.checkpoint_commit("first")
    fake_c4(kit, monkeypatch, {"exists": False, "stale": False, "model": False})
    r = kit.services.catchup.run(log=lambda _: None)
    assert r["status"] == "done" and r["pull"]["status"] == "error" and r["pull"]["reason"] == "not-found"

def test_a_second_catch_up_does_not_wait(kit, tmp_path):
    publish(kit, bare(tmp_path))
    from lib.core.locks import FileLock
    held, done = threading.Event(), threading.Event()
    def hold():                                   # FileLock is re-entrant per thread: hold it from another one
        with FileLock(kit.services.catchup.LOCK, wait=0):
            held.set(); done.wait(30)
    t = threading.Thread(target=hold); t.start(); held.wait(30)
    try:
        assert kit.services.catchup.run(log=lambda _: None)["status"] == "busy"
    finally:
        done.set(); t.join()

def test_the_last_result_is_kept(kit, tmp_path, monkeypatch):
    publish(kit, bare(tmp_path)); fake_c4(kit, monkeypatch, {"exists": False, "stale": False, "model": False})
    kit.services.catchup.run(log=lambda _: None)
    assert kit.services.catchup.last()["pull"]["status"] == "up-to-date"
    assert json.loads(kit.services.catchup.LAST.read_text(encoding="utf-8"))["at"]

def test_only_stale_graphs_are_listed_and_only_with_graphify(kit, monkeypatch):
    graphs = {"api": {"at": 1, "stale": True}, "web": {"at": 2, "stale": False}, "all": {"at": 1, "stale": False}}
    for chosen in (True, False):
        monkeypatch.setattr(kit.services.viewers, "viewers",
                            lambda chosen=chosen: {"c4": {}, "graphs": graphs, "graphify": chosen, "likec4": True})
        assert kit.services.catchup.stale_graphs() == (["api"] if chosen else [])

def test_the_explorer_is_skipped_without_likec4_chosen(kit, monkeypatch):
    built = fake_c4(kit, monkeypatch, {"exists": True, "stale": True, "model": True})
    monkeypatch.setattr(kit.services.components, "components", lambda: ["graphify"])
    assert kit.services.catchup.rebuild_c4(log=lambda _: None) == "skipped" and not built

def test_stale_graphs_are_reported_for_the_caller_not_rebuilt(kit, tmp_path, monkeypatch):
    publish(kit, bare(tmp_path))
    monkeypatch.setattr(kit.services.viewers, "viewers", lambda: {
        "c4": {"exists": False, "stale": False, "model": False}, "graphs": {"api": {"at": 1, "stale": True}},
        "graphify": True, "likec4": True})
    called = []
    monkeypatch.setattr(kit.services.code, "graph_repo", lambda name: called.append(name) or True, raising=False)
    r = kit.services.catchup.run(log=lambda _: None)
    assert r["views"]["graphs"] == ["api"] and not called

def test_a_failing_c4_build_does_not_break_the_catch_up(kit, tmp_path, monkeypatch):
    publish(kit, bare(tmp_path))
    fake_c4(kit, monkeypatch, {"exists": True, "stale": True, "model": True})
    def boom(dest=None, log=print):
        raise RuntimeError("likec4 crashed")
    monkeypatch.setattr(kit.services.viewers, "build_c4", boom)
    r = kit.services.catchup.run(log=lambda _: None)
    assert r["status"] == "done" and r["views"]["c4"] == "failed"
    assert kit.services.catchup.last() == r

def test_the_catch_up_bounds_its_fetch(kit, monkeypatch):
    seen = {}
    def pull(log=print, timeout=None):
        seen["timeout"] = timeout
        return {"status": "up-to-date", "commits": 0, "files": [], "regenerated": [], "detail": ""}
    monkeypatch.setattr(kit.services.share, "pull", pull)
    fake_c4(kit, monkeypatch, {"exists": False, "stale": False, "model": False})
    assert kit.services.catchup.run(log=lambda _: None)["pull"]["status"] == "up-to-date" and seen["timeout"] == 30
