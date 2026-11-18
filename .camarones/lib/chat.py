"""The Docs chat's picker: every runner installed on this machine with the models it can be asked for, and the choice
the panel opens with. It installs and configures nothing (H21): it only lists what the machine already has. An empty
model id means no `--model`: the CLI or its own config decides."""
from __future__ import annotations

import re

from . import agents, answers
from .app import services
from .core import process
from .core.fsutil import load_json, save_json
from .core.paths import PREFS
from .harness import routing

CLAUDE_MODELS = ("haiku", "sonnet", "opus")      # no unset entry: Claude's own default can cost far more than haiku
MODEL_SHAPE = re.compile(r"^[A-Za-z0-9_][\w.:/@-]*$")      # an argv element, never a shell word; match with fullmatch
DEFAULT = "default"
OLLAMA_TIMEOUT = 5                               # seconds `ollama list` may take: an unreachable OLLAMA_HOST hangs it


def ai_enabled() -> bool:
    return (services.current().workspace.workspace().get("ask") or {}).get("ai") is not False


def _model(id: str, label: str, local: bool = False) -> dict:
    return {"id": id, "label": label, "local": local}


def _ollama_tags() -> list[str]:
    """The tags `ollama list` reports, only when OpenCode can reach them. A binary that fails, outlasts OLLAMA_TIMEOUT
    (it is killed) or prints another shape leaves none."""
    if not (process.which("ollama") and process.which("opencode")):
        return []
    try:
        lines = process.out(["ollama", "list"], timeout=OLLAMA_TIMEOUT).splitlines()
    except Exception:                       # a blocked, slow or broken binary must not take the whole picker with it
        return []
    if not lines or lines[0].split()[:1] != ["NAME"]:
        return []
    tags = (line.split()[0] for line in lines[1:] if line.strip())
    return [t for t in tags if MODEL_SHAPE.fullmatch(f"ollama/{t}")]


def _models_of(runner: str, prefs: dict) -> list[dict]:
    if runner == "claude":
        return [_model(m, m) for m in CLAUDE_MODELS]
    if runner == "opencode":
        tags = _ollama_tags()
        return [_model(f"ollama/{t}", t, True) for t in tags] if tags else [_model("", DEFAULT)]
    configured = str(agents.model_for(runner, prefs) or "")        # hand-edited: one the turn refuses is not offered
    return [_model(configured if MODEL_SHAPE.fullmatch(configured) else "", DEFAULT)]


def models() -> list[dict]:
    """[{runner, label, models: [{id, label, local}]}] for every installed runner, routed for bounded work or not."""
    prefs = load_json(PREFS, {})
    return [{"runner": r["id"], "label": r["label"], "models": _models_of(r["id"], prefs)} for r in agents.installed()]


def _only_default(entries: list[dict]) -> bool:
    return len(entries) == 1 and entries[0]["label"] == DEFAULT and not entries[0]["local"]


def remembered(offered: list[dict] | None = None) -> dict | None:
    """The last pick, kept in `~/.camarones.json` under `chat`, while its runner and model are still offered. A runner
    whose only entry is a configured default (Codex's) stays valid and answers with that entry's current id: the
    configured model may have changed since. An unset default (the CLI decides) matches only an unset pick, so a
    local pick whose tags are all gone does not fall to whatever the CLI would run."""
    saved = load_json(PREFS, {}).get("chat")
    if not isinstance(saved, dict) or not all(isinstance(saved.get(k), str) for k in ("runner", "model")):
        return None
    offered = models() if offered is None else offered
    entries = next((r["models"] for r in offered if r["runner"] == saved["runner"]), None)
    if not entries:
        return None
    if _only_default(entries) and (entries[0]["id"] or not saved["model"]):
        return {"runner": saved["runner"], "model": entries[0]["id"]}
    if saved["model"] not in {m["id"] for m in entries}:
        return None
    return {"runner": saved["runner"], "model": saved["model"]}


def remember(runner: str, model: str | None) -> None:
    save_json(PREFS, {**load_json(PREFS, {}), "chat": {"runner": runner, "model": model or ""}})


def _cheapest(entry: dict) -> dict:
    wanted, ids = answers.CHEAP.get(entry["runner"]), [m["id"] for m in entry["models"]]
    return {"runner": entry["runner"], "model": wanted if wanted in ids else ids[0]}


def _asks(offered: list[dict]) -> dict | None:
    """What Ask would use today, so a first chat costs what Ask costs: its routed runner for bounded work and its
    model (`ask.model`, the route's own, or the runner's cheap one). A model the picker does not offer (Ask leaves
    Codex's to its CLI) becomes that runner's cheapest entry: the panel never opens on a model it cannot show."""
    try:
        target = answers.runner()
    except ValueError:                      # a routing tier the config misspells: the picker still opens
        return None
    if not target:
        return None
    route = routing.parse(target)
    entry = next((r for r in offered if r["runner"] == route.runner), None)
    if not entry:
        return None
    offered_ids = {m["id"] for m in entry["models"]}
    wanted = answers.model(target) or route.model or ""
    return {"runner": route.runner, "model": wanted if wanted in offered_ids else _cheapest(entry)["model"]}


def default_choice(offered: list[dict] | None = None) -> dict | None:
    """{runner, model} the panel opens with: the remembered pick, else Ask's, else the first runner's cheap entry. None
    when nothing is installed."""
    offered = models() if offered is None else offered
    if not offered:
        return None
    return remembered(offered) or _asks(offered) or _cheapest(offered[0])
