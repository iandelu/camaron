"""`camaron skills`: the agents' skills from the command line. One positional `action` plus positionals (no nested
subparsers, so `catalog.args_of` reads it). Each action calls `lib/skills.py`; nothing here knows how a skill is
rendered or a note is written. Errors are one plain line on stderr and exit 2, with no joke; --json prints data and no
prose."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from lib.interfaces.cli.registry import CliContext, Command, command

ACTIONS = ("list", "fork", "diff", "reset", "note", "notes", "enable", "disable", "add", "remove")
_USAGE = {"list": "list", "fork": "fork NAME", "diff": "diff NAME [--kit]", "reset": "reset NAME",
          "note": "note SKILL TEXT --source retro|review|board [--step S] [--change ID] [--ref URL]",
          "notes": "notes [SKILL]", "enable": "enable NAME [--machine]", "disable": "disable NAME [--machine]",
          "add": "add PACK", "remove": "remove PACK"}
# flags that only mean something for some actions: anywhere else they are an error, not silently ignored
_ONLY = (("kit", "--kit", "diff"), ("source", "--source", "note"), ("step", "--step", "note"),
         ("change", "--change", "note"), ("ref", "--ref", "note"), ("machine", "--machine", ("enable", "disable")))


def add_parser(sp) -> None:
    Skills().configure(sp.add_parser("skills"))


@command("skills", "app", "team", es="Skills de los agentes: iconos, activar o desactivar y packs opcionales",
         en="The agents' skills: icons, turn them on or off, optional packs")
class Skills(Command):
    def run(self, args: argparse.Namespace, cli: CliContext) -> int:
        return run(args)

    def configure(self, b: argparse.ArgumentParser) -> None:
        b.add_argument("action", choices=ACTIONS)
        b.add_argument("args", nargs="*")
        b.add_argument("--kit", action="store_true")
        b.add_argument("--source")
        b.add_argument("--step")
        b.add_argument("--change")
        b.add_argument("--ref")
        b.add_argument("--machine", action="store_true")
        b.add_argument("--json", action="store_true")


def _misplaced(a) -> str | None:
    for dest, flag, action in _ONLY:
        allowed = (action,) if isinstance(action, str) else action
        if getattr(a, dest, None) not in (None, False) and a.action not in allowed:
            return f"✖ {flag} only goes with: {', '.join(allowed)}"
    return None


def _wrong_usage(a) -> str | None:
    n = len(a.args)
    if a.action == "list":
        ok = n == 0
    elif a.action == "notes":
        ok = n <= 1
    elif a.action == "note":
        ok = n >= 2 and a.source is not None
    else:
        ok = n == 1
    return None if ok else f"✖ usage: camaron skills {_USAGE[a.action]}"


def _who() -> str:
    from lib.app import portal_views
    return portal_views.reviewer()


def _rel(path: Path) -> str:
    from lib.core.paths import ROOT
    try:
        return path.resolve().relative_to(Path(ROOT).resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _rerender() -> None:
    from lib.app import services
    services.current().setup.refresh_agent_config()


def _done(a, data: dict, line: str) -> int:
    print(json.dumps(data, ensure_ascii=False, indent=2) if a.json else line)
    return 0


def _rows() -> dict:
    """Every skill the project knows (on or off), with its icon, pack and both switches, and the packs not added."""
    from lib import skills, skills_packs, trust
    outdated, off, mine = set(skills.outdated()), skills.project_off(), skills_packs.machine_off()
    waiting = {it.group.split("/")[2] for it, _ in trust.pending() if it.kind == "skill" and it.group.count("/") == 2}
    names = sorted(set(skills.kit_names()) | set(skills.team_names()))
    rows = [{"name": n, "origin": skills.origin(n), "outdated": n in outdated, "description": skills.description(n),
             "icon": skills_packs.icon(n), "pack": skills_packs.pack_of(n) if skills.origin(n) == "team-only" else None,
             "project": "off" if n in off else "on", "machine": "off" if n in mine else "on",
             "needs_trust": n in waiting}
            for n in names]
    return {"skills": rows, "ignored": skills.ignored(), "available": skills_packs.available()}


def _list(a) -> int:
    data = _rows()
    if a.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0
    for r in data["skills"]:
        flags = [f for f, on in (("off for the project", r["project"] == "off"),
                                 ("off on this machine", r["machine"] == "off"),
                                 ("waits for `trust`", r["needs_trust"]),
                                 ("kit changed since your copy", r["outdated"])) if on]
        print(f"{r['icon'] or '·'} {r['name']}  {r['origin']}" + (f"  ({'; '.join(flags)})" if flags else ""))
    for p in data["available"]:
        print(f"+ {p['icon'] or '·'} {p['name']}  optional pack, {p['license']}: {', '.join(p['skills'])}"
              f" — `skills add {p['name']}`")
    for s in data["ignored"]:
        print(f"· skipped .camarones/skills/{s['name']}: {s['why']}", file=sys.stderr)
    return 0


def _known(name: str) -> None:
    from lib import skills
    if name not in set(skills.kit_names()) | set(skills.team_names()):
        raise ValueError(f"unknown skill: {name}")


def _switch(a, on: bool) -> int:
    name = a.args[0]
    _known(name)
    if a.machine:
        from lib import skills_packs
        skills_packs.set_machine(name, on)
        where = "on this machine (Claude Code)"
    else:
        from lib.app import services
        ws = services.current().workspace.workspace()
        from lib import skills
        cfg = ws.get("skills") if isinstance(ws.get("skills"), dict) else {}
        off = skills.off_list(cfg) - {name} if on else skills.off_list(cfg) | {name}
        rest = {k: v for k, v in cfg.items() if k not in ("off", False)}
        cfg = {**rest, "off": sorted(off)} if off else rest
        if cfg:
            ws["skills"] = cfg
        else:
            ws.pop("skills", None)                     # back to what a workspace without the key always meant
        services.current().workspace.save_workspace(ws)
        _rerender()
        where = "for the project"
    state = "on" if on else "off"
    return _done(a, {"name": name, "state": state, "scope": "machine" if a.machine else "project"},
                 f"✔ {name} {state} {where}")


def _enable(a) -> int:
    return _switch(a, True)


def _disable(a) -> int:
    return _switch(a, False)


def _add(a) -> int:
    from lib import skills_packs
    entry = skills_packs.add(a.args[0])
    _rerender()
    names = sorted(entry["skills"])
    return _done(a, {"pack": a.args[0], "commit": entry["commit"], "skills": names},
                 f"✔ {a.args[0]} added at {entry['commit'][:7]}: {', '.join(names)} — approve them with "
                 f"`{_cli()} trust`, then commit .camarones/skills in a docs PR")


def _remove(a) -> int:
    from lib import skills_packs
    out = skills_packs.remove(a.args[0])
    _rerender()
    line = f"✔ {a.args[0]} removed: {', '.join(out['removed']) or 'nothing left to remove'}"
    if out["kept"]:
        line += f" (kept, edited here: {', '.join(out['kept'])})"
    return _done(a, {"pack": a.args[0], **out}, line)


def _cli() -> str:
    from lib.common import cli_cmd
    return cli_cmd()


def _fork(a) -> int:
    from lib import skills
    path = skills.fork(a.args[0])
    _rerender()
    return _done(a, {"name": a.args[0], "path": _rel(path)},
                 f"✔ team copy of {a.args[0]}: {_rel(path)} — edit it and commit it in a docs PR")


def _diff(a) -> int:
    from lib import skills
    text = skills.diff(a.args[0], against_fork=a.kit)
    if a.json:
        print(json.dumps({"name": a.args[0], "diff": text}, ensure_ascii=False, indent=2))
    else:
        print(text.rstrip("\n") if text else f"{a.args[0]}: same as the kit")
    return 0


def _reset(a) -> int:
    from lib import skills
    path = skills.reset(a.args[0])
    _rerender()
    return _done(a, {"name": a.args[0], "path": _rel(path)},
                 f"✔ {a.args[0]} follows the kit again (your copy: {_rel(path)})")


def _note(a) -> int:
    from lib import skills
    path = skills.add_note(a.args[0], " ".join(a.args[1:]), a.source, _who(), step=a.step or "",
                           change=a.change or "", ref=a.ref or "")
    return _done(a, {"skill": a.args[0], "path": _rel(path)}, f"✔ note added to {_rel(path)}")


def _notes(a) -> int:
    from lib import skills
    rows = skills.notes(a.args[0] if a.args else None)
    if a.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return 0
    if not rows:
        print("No skill notes yet.", file=sys.stderr)
        return 0
    tree: dict[str, dict[str, list[dict]]] = {}
    for n in rows:
        tree.setdefault(n["skill"], {}).setdefault(n["step"] or "-", []).append(n)
    for skill, steps in tree.items():
        print(f"{skill} ({sum(len(v) for v in steps.values())})")
        for step, items in steps.items():
            print(f"  {step} ({len(items)})")
            for n in items:
                print(f"    {n['date']} {n['source']} {n['change'] or '-'} {n['by']} — {n['text']}")
    return 0


_RUN = {"list": _list, "fork": _fork, "diff": _diff, "reset": _reset, "note": _note, "notes": _notes,
        "enable": _enable, "disable": _disable, "add": _add, "remove": _remove}


def run(a) -> int:
    wrong = _misplaced(a) or _wrong_usage(a)
    if wrong:
        print(wrong, file=sys.stderr)
        return 2
    try:
        return _RUN[a.action](a)
    except (ValueError, OSError) as e:
        print(f"✖ {e}", file=sys.stderr)
    return 2
