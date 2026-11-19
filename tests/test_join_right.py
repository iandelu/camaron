"""Joining a team's cam-docs (spec 2026-11-18 §6.2, §6.5): a join never changes a team decision. The components in
workspace.yaml stay the team's; what this machine installs or leaves out is kept in the git-ignored cache."""
from __future__ import annotations

from conftest import load_kit, wire_project
from test_team_repo import bare, git, publish

QUIET = lambda _: None  # noqa: E731


def joined(kit, tmp_path):
    """The team publishes its cam-docs; a teammate joins it into another folder and becomes the loaded kit."""
    remote = bare(tmp_path)
    publish(kit, remote)
    root, ok = kit.projects.join(str(remote), tmp_path / "mate")
    assert ok
    return load_kit(root, kit.home, root.parent)


PREREQS = {"git": {"ok": True, "need": True, "hint": "git"}, "claude": {"ok": True, "need": False, "hint": "Claude Code"},
           "codex": {"ok": False, "need": False, "hint": "Codex"}}


def offline(mate, monkeypatch) -> None:
    """A machine with nothing installed and nothing to install: setup's repos and wiring run for real."""
    monkeypatch.setattr(mate.services.setup, "prerequisites", lambda: PREREQS)
    monkeypatch.setattr(mate.services.toolchain, "tool_ok", lambda k: False)


def set_components(kit, comps) -> None:
    ws = kit.services.workspace.workspace()
    ws["project"]["components"] = comps
    kit.services.workspace.save_workspace(ws)


# ---------- team decisions vs this machine's tools ----------
def test_without_a_machine_file_here_is_the_teams_choice(kit):
    """Every project made before 4.94 has no per-machine file: it runs the team's choice, as before."""
    c = kit.services.components
    assert c.here() == c.components() == c.ALL_COMPONENTS
    set_components(kit, ["likec4", "agents"])
    assert c.here() == ["likec4", "agents"]
    yaml_before = (kit.root / ".camarones" / "workspace.yaml").read_bytes()
    c.set_machine(["agents"])
    assert c.here() == ["agents"] and c.components() == ["likec4", "agents"]
    assert (kit.root / ".camarones" / "workspace.yaml").read_bytes() == yaml_before


def test_a_join_leaves_cam_docs_clean(kit, tmp_path, monkeypatch):
    team = kit.services.workspace.workspace()["project"].get("components")
    mate = joined(kit, tmp_path)
    offline(mate, monkeypatch)
    mate.onboard.save_position(mate.root, "tools", "join")
    mate.onboard.install_tools([], [], QUIET)                       # every kit tool left out on this machine
    assert mate.onboard.run_setup(QUIET)
    mate.onboard.done()
    assert git(mate.root, "status", "--porcelain") == ""
    assert mate.services.workspace.workspace()["project"].get("components") == team


def test_unticking_openwiki_on_a_join_leaves_the_plan_and_the_teams_choice(kit, tmp_path, monkeypatch):
    wire_project(kit)                                               # the team's own setup wrote its agent config
    mate = joined(kit, tmp_path)
    offline(mate, monkeypatch)
    monkeypatch.setattr(mate.services.setup, "install_tools", lambda log=print, comps=None: None)
    plan, yaml_file = mate.plan.PLAN.read_bytes(), mate.root / ".camarones" / "workspace.yaml"
    yaml_before = yaml_file.read_bytes()
    mate.onboard.save_position(mate.root, "tools", "join")
    mate.onboard.install_tools([], ["agents"], QUIET)                 # OpenWiki (and the rest) not on this machine
    assert mate.onboard.run_setup(QUIET)
    mate.onboard.done()
    assert mate.plan.PLAN.read_bytes() == plan and yaml_file.read_bytes() == yaml_before
    assert git(mate.root, "status", "--porcelain") == ""
    assert mate.services.components.here() == ["agents"]
    assert "openwiki" in mate.services.components.components()


def test_a_join_tools_step_lists_the_teams_components(kit, tmp_path, monkeypatch):
    set_components(kit, ["likec4", "agents"])
    mate = joined(kit, tmp_path)
    offline(mate, monkeypatch)
    mate.onboard.save_position(mate.root, "tools", "join")
    assert [r["id"] for r in mate.onboard.tool_rows() if not r["sys"]] == ["likec4", "agents"]


def test_a_new_project_tools_step_still_saves_the_teams_choice(kit, monkeypatch):
    offline(kit, monkeypatch)
    kit.onboard.save_position(kit.root, "tools", "new")
    kit.onboard.install_tools([], ["likec4"], QUIET)
    assert kit.services.workspace.workspace()["project"]["components"] == ["likec4"]


# ---------- the join's first run in the CLI wizard ----------
def test_the_wizard_join_repos_step_shows_the_rows_and_writes_no_team_file(kit, fake_wizard, tmp_path, capsys):
    from test_repos_here import team_repos
    team_repos(kit, tmp_path)
    (kit.ws / "api").rename(kit.ws / "api-svc")
    yaml_before = (kit.root / ".camarones" / "workspace.yaml").read_bytes()
    w = fake_wizard(["go"])
    assert w.fr_join_repos(kit.services.workspace.workspace()) is None
    out = capsys.readouterr().out
    assert w.t("jr_linked", path="./api-svc") in out and w.t("jr_here") in out
    assert (kit.root / ".camarones" / "workspace.yaml").read_bytes() == yaml_before


def test_the_wizard_join_repos_step_searches_another_folder(kit, fake_wizard, tmp_path):
    from test_repos_here import team_repos
    team_repos(kit, tmp_path)
    elsewhere = tmp_path / "IdeaProjects"
    elsewhere.mkdir()
    (kit.ws / "web").rename(elsewhere / "frontend")
    fake_wizard(["search", str(elsewhere), "go"]).fr_join_repos(kit.services.workspace.workspace())
    assert kit.services.links._is_link(kit.ws / "web")
