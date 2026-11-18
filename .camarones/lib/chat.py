"""The Docs chat: every runner installed on this machine with the models it can be asked for, the choice the panel
opens with, and one turn — a question with the recent history, answered from the docs by Ask's core
(answers.ask_docs) on the runner and model the person picked. It installs and configures nothing (H21): it only lists
what the machine already has. An empty model id means no `--model`: the CLI or its own config decides."""
from __future__ import annotations

import re

from . import agents, answers, usage
from .app import services
from .core import process
from .core.fsutil import load_json, save_json
from .core.paths import PREFS
from .harness import routing

CLAUDE_MODELS = ("haiku", "sonnet", "opus")      # no unset entry: Claude's own default can cost far more than haiku
MODEL_SHAPE = re.compile(r"^[A-Za-z0-9_][\w.:/@-]*$")      # an argv element, never a shell word; match with fullmatch
DEFAULT = "default"
OLLAMA_TIMEOUT = 5                               # seconds `ollama list` may take: an unreachable OLLAMA_HOST hangs it
HISTORY_TURNS, HISTORY_CHARS = 6, 4000           # context re-sent each turn: a bounded model's room beside the excerpts
ROLES = ("user", "assistant")


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
    except (ValueError, TypeError, AttributeError):     # a hand-edited routing, misspelt or misshapen: the picker opens
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


def clean_history(history) -> list[dict]:
    """The last HISTORY_TURNS non-empty turns as {role, text}, the oldest dropped until they fit in HISTORY_CHARS; a
    single turn longer than that is cut to fit."""
    if not isinstance(history, list):
        raise ValueError("history: a list of {role, text}")
    for h in history:
        if not isinstance(h, dict) or h.get("role") not in ROLES or not isinstance(h.get("text"), str):
            raise ValueError("history: each turn is {role: user|assistant, text}")
    kept = [{"role": h["role"], "text": h["text"]} for h in history if h["text"].strip()][-HISTORY_TURNS:]
    while len(kept) > 1 and sum(len(h["text"]) for h in kept) > HISTORY_CHARS:
        kept.pop(0)
    if kept:
        kept[0]["text"] = kept[0]["text"][:HISTORY_CHARS]
    return kept


def check(body: dict) -> tuple[str, str | None, str, list[dict]]:
    """(runner, model or None, question, history) from a turn's body, before any job starts. ValueError: a body the
    app would never send; RuntimeError: no AI answer on this machine (the app words it from its prefix)."""
    if not isinstance(body, dict):
        raise ValueError("the request body must be a JSON object")
    if not ai_enabled():
        raise RuntimeError("no AI answer here: ask.ai is false in workspace.yaml")
    offered = models()
    if not offered:
        raise RuntimeError("no AI answer here: no runner is installed on this machine")
    q, runner, model = body.get("q"), body.get("runner"), body.get("model")
    if not isinstance(q, str) or not q.strip():
        raise ValueError("q: the question is empty")
    if runner not in [r["runner"] for r in offered]:
        raise ValueError(f"runner: {runner!r} is not installed on this machine")
    if model is None:
        model = ""
    if not isinstance(model, str) or (model and not MODEL_SHAPE.fullmatch(model)):
        raise ValueError(f"model: {model!r} is not a model name")
    return runner, model or None, q.strip(), clean_history(body.get("history", []))


def turn(runner: str, model: str | None, q: str, history: list[dict], log) -> dict:
    """One answer, as a job: the log gets the answer's text (never the JSON the prompt asks for), the job's result
    everything else. Nothing found is an answer of None, not a failure; a timeout raises Ask's error, and a runner that
    was asked and gave nothing usable (not signed in, a model it lacks: its stderr is not kept) fails the turn, so the
    person sees why and the pick is not remembered."""
    got = answers.ask_docs(q, runner, model, tuple(history))
    if got["answer"] is None and "seconds" in got:
        who = f"{runner}:{model}" if model else runner
        raise RuntimeError(f"{who} gave no answer: is it signed in, and does it have that model?")
    for line in (got["answer"] or "").splitlines():
        log(line)
    try:
        remember(runner, model)
    except OSError:                         # the pick is a convenience: an unwritable home must not lose the answer
        pass
    usage.record("app:chat", channel="human", hit=bool(got["answer"]))
    return {"rc": 0, "result": got}
