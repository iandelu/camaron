"""The retrieval hooks (turning-point spec, P1), run by `camaron hook prompt|pre-edit`. UserPromptSubmit prints the
docs, C4 elements and code-graph nodes that match the prompt (prompt_context, no model call). PreToolUse stops, once per
session, the first edit of a service-repo file when the session consulted no docs: an injected prompt, a camarones or
likec4 MCP tool, or a file tool pointed inside cam-docs, read from the session's transcript. `hooks: {gate: false}` in
workspace.yaml drops the stop and keeps the prompt hook. Both log what happened (counts, never the prompt) to
.cache/hooks/events.jsonl, which `camaron hooks report` adds up."""
from __future__ import annotations

import json, sys
from collections import Counter
from datetime import datetime
from pathlib import Path

from lib.app import prompt_context, services
from lib.common import CACHE, ROOT, repo_dir
from lib.domain.docs import frontmatter
from lib.harness import freshness

LOG = CACHE / "hooks" / "events.jsonl"
DOCS_TOOLS = ("mcp__camarones__", "mcp__likec4__")   # tool-name prefixes that consult the docs
READERS = ("Read", "Grep", "Glob")                     # …and file tools, when they look inside cam-docs


def gate_enabled() -> bool:
    return (services.current().workspace.workspace().get("hooks") or {}).get("gate", True) is not False


def _log(entry: dict) -> None:
    """One line per prompt or edit decision; a log that cannot be written never blocks the agent."""
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with LOG.open("a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps({"at": datetime.now().isoformat(timespec="seconds"), **entry}) + "\n")
    except OSError:
        pass


def _events() -> list[dict]:
    if not LOG.is_file():
        return []
    rows = []
    for line in LOG.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def prompt(payload: dict) -> str:
    """The docs for this prompt, or nothing; the log keeps only whether something was injected."""
    ctx = prompt_context.build(str(payload.get("prompt") or ""))
    _log({"session": str(payload.get("session_id") or ""), "event": "prompt", "injected": bool(ctx["text"]),
          "served": sum(1 for p in ctx["pages"] if p["served"]), "held": sum(1 for p in ctx["pages"] if not p["served"]),
          "c4": len(ctx["c4"]), "nodes": len(ctx["nodes"])})
    return ctx["text"]


def _in_repo(path: Path) -> tuple[str, str] | None:
    """(repo, repo-relative path) when `path` lies in one of the workspace's service repos."""
    for repo in services.current().workspace.workspace().get("repos") or []:
        name = repo.get("name") if isinstance(repo, dict) else None
        if not name:
            continue
        try:
            return name, path.relative_to(repo_dir(name).resolve()).as_posix()
        except ValueError:
            continue
    return None


def _inside_docs(value) -> bool:
    try:
        return Path(str(value)).resolve().is_relative_to(ROOT.resolve())
    except (OSError, ValueError):
        return False


def _transcript_consulted(transcript: str) -> bool:
    """Whether the session's transcript shows a docs tool, or a file tool pointed inside cam-docs."""
    f = Path(transcript) if transcript else None
    if not f or not f.is_file():
        return False
    for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
        if '"tool_use"' not in line:
            continue
        try:
            content = (json.loads(line).get("message") or {}).get("content") or []
        except (ValueError, AttributeError):
            continue
        for use in content if isinstance(content, list) else []:
            if not isinstance(use, dict) or use.get("type") != "tool_use":
                continue
            name, args = str(use.get("name") or ""), use.get("input") or {}
            if name.startswith(DOCS_TOOLS):
                return True
            if name in READERS and isinstance(args, dict) and any(
                    _inside_docs(args[k]) for k in ("file_path", "path") if args.get(k)):
                return True
    return False


def _pages_citing(repo: str, rel: str) -> list[str]:
    """The pages whose x-sources cite this file."""
    found = []
    for logical, f in services.current().docs.iter_docs():
        fm, _ = frontmatter.split_fm(f.read_text(encoding="utf-8", errors="replace"))
        for src in fm.get("x-sources") or []:
            r, path, _span = freshness.parse(str(src))
            if r == repo and path.split("#", 1)[0] == rel:
                found.append(logical)
                break
    return found


def pre_edit(payload: dict) -> tuple[int, str]:
    """(exit code, message): 2 stops the edit once per session when no docs were consulted; 0 lets it through."""
    if not gate_enabled():
        return 0, ""
    raw = (payload.get("tool_input") or {}).get("file_path")
    if not isinstance(raw, str) or not raw:
        return 0, ""
    where = _in_repo(Path(raw).resolve())
    if not where:
        return 0, ""
    sid = str(payload.get("session_id") or "")
    mine = [e for e in _events() if e.get("session") == sid]
    if any(e.get("event") == "edit" for e in mine):
        return 0, ""
    consulted = (any(e.get("event") == "prompt" and e.get("injected") for e in mine)
                 or _transcript_consulted(str(payload.get("transcript_path") or "")))
    repo, rel = where
    if not consulted and not any(e.get("event") == "stop" for e in mine):
        _log({"session": sid, "event": "stop", "repo": repo})
        pages = _pages_citing(repo, rel)
        read = ("\n".join(f"- read_doc(\"{p}\")" for p in pages[:5]) if pages else
                f"- no page cites this file: search_docs(\"{Path(rel).stem}\") or ask(\"<what you are changing>\")")
        return 2, (f"Camarón: before you edit {repo}/{rel}, read what the docs say — this session consulted none.\n"
                   f"{read}\nIf the docs do not cover it, say so and edit again (this stop happens once per session).")
    _log({"session": sid, "event": "edit", "repo": repo, "consulted": consulted})
    return 0, ""


def report() -> dict:
    """What the prompt and edit hooks saw: the share of code-editing sessions that consulted docs before their first
    edit is the number turning-point P1 is judged by."""
    rows = _events()
    count = Counter(e.get("event") for e in rows)
    firsts: dict[str, bool] = {}
    for e in rows:
        if e.get("event") == "edit":
            firsts.setdefault(str(e.get("session")), bool(e.get("consulted")))
    sessions = len(firsts)
    consulted = sum(firsts.values())
    return {"prompts": count["prompt"], "prompts_with_docs": sum(1 for e in rows if e.get("event") == "prompt"
                                                                 and e.get("injected")),
            "edit_sessions": sessions, "consulted_first": consulted, "stops": count["stop"],
            "share": round(consulted / sessions, 2) if sessions else None}


def run(name: str) -> int:
    """`camaron hook prompt|pre-edit`: Claude Code passes the event as JSON on stdin. A hook never breaks the session."""
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except ValueError:
        payload = {}
    try:
        if name == "prompt":
            text = prompt(payload)
            if text:
                print(text)
        elif name == "pre-edit":
            code, text = pre_edit(payload)
            if code:
                print(text, file=sys.stderr)
            return code
    except Exception:  # noqa: BLE001 — never block the agent on a kit error
        return 0
    return 0
