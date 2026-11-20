"""Where the C4 model lives: `cam-docs/docs/architecture` by default, or a folder of a service repo when workspace.yaml
says so (`project.architecture: <repo>:<path>`), as a project whose repo keeps its own LikeC4 model does. Then that is
the one model: the kit lists its views, builds the explorer from it, edits it from the portal, checks `c4:` sources
against it, counts it in the KPIs and points the likec4 MCP server at it; arch-draft writes no second model."""
from __future__ import annotations

import argparse, json

import pytest

from fixtures.host_tools import needs

REF = "api:docs/04-architecture"
SPEC_LINE = "specification {\n  element system\n  element service\n}\n"
EXTERNAL_MODEL = """model {
  api = system 'API' {
    orders = service 'Orders' {
      technology 'Kotlin'
    }
  }
}
"""
EXTERNAL_VIEWS = """views {
  view index {
    title 'System context'
    include *
  }
  view modules of api {
    title 'API modules'
    include *
  }
}
"""


def point_at(kit, value=REF):
    ws = kit.services.workspace.workspace()
    ws["project"]["architecture"] = value
    kit.services.workspace.save_workspace(ws)


def external_model(kit, *, config=True):
    d = kit.ws / "api" / "docs" / "04-architecture"
    d.mkdir(parents=True, exist_ok=True)
    files = {"spec.c4": SPEC_LINE, "model.c4": EXTERNAL_MODEL, "views.c4": EXTERNAL_VIEWS}
    if config:
        files["likec4.config.json"] = '{ "name": "api" }'
    for name, text in files.items():
        (d / name).write_text(text, encoding="utf-8", newline="\n")
    return d


# ---------- the rule (pure) ----------
def test_parse_reads_repo_and_path():
    from lib.domain import architecture as a
    repos = ["api", "web"]
    assert a.parse(None, repos) is None
    assert a.parse("", repos) is None
    assert a.parse("  ", repos) is None
    assert a.parse("api:docs/04-architecture", repos) == ("api", "docs/04-architecture")
    assert a.parse(" api : docs/arch/ ", repos) == ("api", "docs/arch")
    assert a.parse("api:docs\\arch", repos) == ("api", "docs/arch")       # a Windows hand keeps working
    assert a.parse("web:.", repos) == ("web", ".")


@pytest.mark.parametrize("value", ["docs/architecture", "shop:docs/c4", "api:", "api:../web/c4", "api:/abs/c4",
                                   "api:docs/../../c4", "C:/models/c4", 42, ["api"]])
def test_parse_refuses_what_cannot_be_used(value):
    from lib.domain import architecture as a
    with pytest.raises(ValueError, match="project.architecture"):
        a.parse(value, ["api", "web"])


# ---------- where the model is ----------
def test_without_the_key_the_model_stays_in_cam_docs(kit):
    """A 3.x / 4.x project has no `architecture` key: nothing changes for it."""
    assert "architecture" not in kit.services.workspace.workspace()["project"]
    assert kit.services.diagrams.arch_dir() == kit.root / "docs" / "architecture"
    assert kit.services.diagrams.arch_source() is None


def test_the_key_points_at_the_repo_folder(kit):
    point_at(kit)
    assert kit.services.diagrams.arch_dir() == kit.ws / "api" / "docs" / "04-architecture"
    assert kit.services.diagrams.arch_source() == REF


def test_a_repo_not_cloned_yet_does_not_fall_back_to_cam_docs(kit):
    """Falling back would let arch-draft write the second model the key is there to avoid."""
    from lib.common import rmtree
    rmtree(kit.ws / "api")
    point_at(kit)
    assert kit.services.diagrams.arch_dir() == kit.ws / "api" / "docs" / "04-architecture"


def test_an_unusable_key_keeps_cam_docs_and_check_says_why(kit):
    point_at(kit, "shop:docs/c4")
    assert kit.services.diagrams.arch_dir() == kit.root / "docs" / "architecture"
    assert kit.services.diagrams.arch_source() is None
    _, warns = kit.services.doc_status.check()
    assert any("project.architecture" in w and "shop" in w for w in warns)


def test_check_says_when_the_folder_is_missing(kit):
    point_at(kit)
    _, warns = kit.services.doc_status.check()
    assert any("project.architecture" in w and "api/docs/04-architecture" in w for w in warns)
    external_model(kit)
    _, warns = kit.services.doc_status.check()
    assert not any("project.architecture" in w for w in warns)


# ---------- everything follows it ----------
def test_views_come_from_the_repo_model(kit):
    external_model(kit)
    (kit.root / "docs" / "architecture").mkdir(parents=True, exist_ok=True)
    (kit.root / "docs" / "architecture" / "views.c4").write_text("views {\n  view stale {\n  }\n}\n", encoding="utf-8")
    point_at(kit)
    views = {v["id"]: v for v in kit.services.diagrams.c4_views()}
    assert set(views) == {"index", "modules"}
    assert views["modules"]["file"] == "views.c4"


def test_the_portal_tree_says_where_the_model_is(kit):
    from lib.app import portal_views
    assert portal_views.tree()["c4Source"] is None
    external_model(kit)
    point_at(kit)
    t = portal_views.tree()
    assert t["c4Source"] == REF and {v["id"] for v in t["views"]} == {"index", "modules"}


def test_the_editor_reads_and_writes_the_repo_model(kit, monkeypatch):
    d = external_model(kit)
    point_at(kit)
    from lib import c4edit
    monkeypatch.setattr(c4edit, "validate", lambda: (True, ""))
    idx = c4edit.index()
    assert idx["elements"]["api.orders"]["file"] == "model.c4"
    c4edit.edit("api.orders", technology="Kotlin · Spring Boot")
    assert "technology 'Kotlin · Spring Boot'" in (d / "model.c4").read_text(encoding="utf-8")
    assert not (kit.root / "docs" / "architecture" / "model.c4").exists()


def test_c4_sources_resolve_against_the_repo_model(kit):
    external_model(kit)
    point_at(kit)
    from lib.harness import freshness
    assert freshness.c4_exists("api.orders")
    assert not freshness.c4_exists("api.billing")


def test_the_kpis_count_the_repo_model(kit):
    external_model(kit)
    point_at(kit)
    from lib.harness import kpis
    assert kpis.coverage(run_check=False)["c4_files"] == 3


def test_the_likec4_mcp_server_reads_the_repo_model(kit):
    args = kit.services.agent_config.likec4_mcp()["args"]
    assert args[-1] == "cam-docs/docs/architecture"
    point_at(kit)
    assert kit.services.agent_config.likec4_mcp()["args"][-1] == "api/docs/04-architecture"


def test_the_viewer_state_sees_the_repo_model(kit):
    point_at(kit)
    assert kit.services.viewers.viewers()["c4"]["model"] is False
    external_model(kit)
    assert kit.services.viewers.viewers()["c4"]["model"] is True


def test_a_build_without_config_names_the_real_folder(kit):
    external_model(kit, config=False)
    point_at(kit)
    said = []
    assert kit.services.viewers.build_c4(log=said.append) is False
    assert any(REF in s for s in said)
    ok, msg = kit.services.diagrams.arch_validate()
    assert not ok and REF in msg


def fake_likec4(kit, monkeypatch, ok):
    """likec4 build as a stand-in: on success it writes the explorer where `-o` says; a broken model writes nothing."""
    import subprocess
    from lib.app import viewers
    kit.services.diagrams.arch_dir().mkdir(parents=True, exist_ok=True)
    (kit.services.diagrams.arch_dir() / "likec4.config.json").write_text("{}\n", encoding="utf-8")

    def run(cmd, **kw):
        out = viewers.Path(cmd[cmd.index("-o") + 1])
        if ok:
            out.mkdir(parents=True, exist_ok=True)
            (out / "index.html").write_text("new", encoding="utf-8")
        return subprocess.CompletedProcess(cmd, 0 if ok else 1, "", "")
    monkeypatch.setattr(viewers, "run", run)
    dest = viewers.VIEWERS / "architecture"
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "index.html").write_text("old", encoding="utf-8")
    (dest / "gone.js").write_text("old", encoding="utf-8")
    return dest


def test_a_broken_model_leaves_the_working_explorer_alone(kit, monkeypatch):
    dest = fake_likec4(kit, monkeypatch, ok=False)
    assert kit.services.viewers.build_c4(log=lambda _: None) is False
    assert (dest / "index.html").read_text(encoding="utf-8") == "old"
    assert sorted(p.name for p in dest.parent.iterdir()) == ["architecture"]       # no build folder left behind


def test_a_good_build_replaces_the_explorer_whole(kit, monkeypatch):
    dest = fake_likec4(kit, monkeypatch, ok=True)
    assert kit.services.viewers.build_c4(log=lambda _: None) is True
    assert (dest / "index.html").read_text(encoding="utf-8") == "new" and not (dest / "gone.js").exists()
    assert sorted(p.name for p in dest.parent.iterdir()) == ["architecture"]


@needs("likec4")
def test_likec4_validates_and_builds_the_repo_model(kit):
    external_model(kit)
    point_at(kit)
    ok, msg = kit.services.diagrams.arch_validate()
    assert ok, msg
    assert kit.services.viewers.build_c4(log=lambda _: None)
    assert (kit.services.viewers.VIEWERS / "architecture" / "index.html").is_file()


def test_setup_counts_the_repo_model(kit):
    from lib.app import setup
    before = setup.setup_steps(["likec4"])
    external_model(kit)
    point_at(kit)
    assert setup.setup_steps(["likec4"]) == before + 1


# ---------- no second model ----------
def test_arch_draft_writes_nothing_when_the_model_lives_in_a_repo(kit, tmp_path):
    from lib import quickarch
    draft = tmp_path / "draft"
    draft.mkdir()
    for name in ("likec4.config.json", "spec.c4", "model.c4", "views.c4"):
        (draft / name).write_text("// draft\n", encoding="utf-8")
    point_at(kit)
    assert quickarch.save({"dir": draft}, overwrite=True) == []
    assert not (kit.root / "docs" / "architecture" / "model.c4").exists()


def test_the_app_save_says_the_model_is_elsewhere(kit, monkeypatch):
    from lib import onboard
    monkeypatch.setattr(onboard, "last_draft", lambda: {"dir": kit.root})
    external_model(kit)
    point_at(kit)
    assert onboard.arch_save() == {"exists": True, "external": REF}
    assert onboard.arch_save(overwrite=True) == {"exists": True, "external": REF}


def test_the_refine_prompt_names_the_repo_folder(kit):
    from lib import onboard
    point_at(kit)
    p = onboard.arch_prompt("en")
    assert "`api/docs/04-architecture/model.c4`" in p
    assert "cam-docs/docs/architecture/model.c4" not in p


def test_the_cli_arch_draft_says_where_the_model_is(kit, monkeypatch, capsys):
    from lib import quickarch
    from lib.interfaces.cli import registry
    from lib.interfaces.cli.commands import analyze
    draft = kit.root / ".draft"
    draft.mkdir()
    (draft / "model.c4").write_text("// draft\n", encoding="utf-8")
    monkeypatch.setattr(quickarch, "draft", lambda **_: {"dir": draft, "valid": True})
    point_at(kit)
    args = argparse.Namespace(save=True, overwrite=False)
    assert analyze.ArchDraft().run(args, registry.CliContext(argparse.ArgumentParser(), kit.services)) == 0
    out = capsys.readouterr().out
    assert REF in out
    assert not (kit.root / "docs" / "architecture" / "model.c4").exists()


def test_tree_json_keeps_its_shape_without_the_key(kit):
    from lib.app import portal_views
    t = portal_views.tree()
    json.dumps(t)
    assert "c4Source" in t
