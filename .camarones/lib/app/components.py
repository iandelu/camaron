"""The project's chosen components: the kit tools and extras a project can switch on, and the profile that picks them."""
from __future__ import annotations

from lib.app import services
from lib.common import CACHE, load_json, save_json

KIT_TOOLS = {
    "graphify": "graphify — code knowledge graph (Claude/Codex query it instead of grepping)",
    "likec4": "LikeC4 — C4 architecture diagrams + interactive explorer",
    "openwiki": "OpenWiki — one wiki per repo with grounded claims",
    "quality": "Quality gate — mermaid-cli (diagram validation) + gitleaks (secret scan) for CLI check",
}
EXTRAS = {
    "agents": "Claude Code / Codex wiring in cam-docs (skills, MCP, rules), linked from the workspace root",
}
ALL_COMPONENTS = [*KIT_TOOLS, *EXTRAS]
MACHINE = "components.json"          # in the git-ignored cache: what this machine left out of the team's choice


def components() -> list[str]:
    """Components chosen in the wizard (stored in .camarones/workspace.yaml → project.components). Default: all."""
    chosen = services.current().workspace.workspace()["project"].get("components")
    return list(ALL_COMPONENTS) if chosen is None else [c for c in chosen if c in ALL_COMPONENTS]


def here() -> list[str]:
    """The team's components this machine runs: the team's choice minus what this machine left out (a join's tools
    step). No file, as in every project before 4.94: the team's choice."""
    skip = set((load_json(CACHE / MACHINE, {}) or {}).get("skip") or [])
    return [c for c in components() if c not in skip]


def set_machine(chosen: list[str]) -> None:
    """This machine's choice among the team's components; workspace.yaml (the team's decision) is never written."""
    save_json(CACHE / MACHINE, {"skip": [c for c in components() if c not in chosen]})


def set_profile(name: str) -> None:
    from lib.install import PROFILES
    if name not in PROFILES:
        raise ValueError(f'Unknown profile: {name}')
    ws = services.current().workspace.workspace()
    ws['project']['profile'] = name
    ws['project']['components'] = list(PROFILES[name])
    services.current().workspace.save_workspace(ws)


def set_components(chosen: list[str]) -> None:
    ws = services.current().workspace.workspace()
    ws["project"]["components"] = [c for c in ALL_COMPONENTS if c in chosen]
    services.current().workspace.save_workspace(ws)
