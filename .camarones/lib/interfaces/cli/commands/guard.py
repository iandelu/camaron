"""`camaron guard`: the guardrails (P3). `install` and `status` for the git hooks (no AI co-author, no staged secret,
the docs check on a cam-docs push, the repo's own hooks chained after) and Claude Code's attribution; `gate` runs the
checks a change must pass; `uninstall` gives the repos their own hooks back. One positional `action`, as `change` and
`board` do. Exit 0 done or green, 1 a check failed, 2 a usage error, 3 nothing failed but a check could not run (never
green); --json output carries no prose."""
from __future__ import annotations

import argparse
import json
import sys

from lib.interfaces.cli.registry import CliContext, Command, command

ACTIONS = ("install", "status", "gate", "uninstall")
_ONLY = (("base", "--base", ("gate",)), ("latest", "--latest", ("gate",)))      # flags that mean something for one action
_MARK = {"pass": "✔", "fail": "✖", "not-run": "?", "n/a": "·"}
_T = {
    "en": {"off": "guardrails are off for this project (guard: {install: false} in workspace.yaml)",
           "done": "✔ guardrails installed: git hooks and Claude Code attribution", "same": "✔ guardrails already in place",
           "none": "no repo to guard", "hooks": "git hooks", "attr": "Claude Code attribution", "on": "on", "offs": "off",
           "gone": "git hooks and Claude Code attribution removed from: {names}", "nothing": "nothing of the kit's to remove",
           "again": "setup and repair put them back; to keep them off set guard: {install: false} in workspace.yaml",
           "pass": "✔ the gate is green", "fail": "✖ the gate is red: fix what failed", "not-run":
           "? nothing failed, but a check did not run: the gate is not green", "state": {
               "pass": "pass", "fail": "FAIL", "not-run": "NOT RUN", "n/a": "n/a"}},
    "es": {"off": "las protecciones están apagadas en este proyecto (guard: {install: false} en workspace.yaml)",
           "done": "✔ protecciones instaladas: git hooks y atribución de Claude Code", "same": "✔ protecciones ya instaladas",
           "none": "no hay ningún repo que proteger", "hooks": "git hooks", "attr": "atribución de Claude Code", "on": "activa",
           "offs": "apagada", "gone": "git hooks y atribución de Claude Code quitados de: {names}",
           "nothing": "no hay nada del kit que quitar",
           "again": "setup y repair los vuelven a poner; para dejarlos apagados pon guard: {install: false} en workspace.yaml",
           "pass": "✔ la puerta está en verde", "fail": "✖ la puerta está en rojo: arregla lo que falló", "not-run":
           "? nada falló, pero una comprobación no se ejecutó: la puerta no está en verde", "state": {
               "pass": "bien", "fail": "FALLA", "not-run": "NO SE EJECUTÓ", "n/a": "no aplica"}},
}


@command("guard", "cli")
class Guard(Command):
    def configure(self, p: argparse.ArgumentParser) -> None:
        p.add_argument("action", choices=ACTIONS)
        p.add_argument("--repo", action="append")
        p.add_argument("--base")
        p.add_argument("--latest", action="store_true")
        p.add_argument("--json", action="store_true")

    def run(self, args: argparse.Namespace, cli: CliContext) -> int:
        for dest, flag, actions in _ONLY:
            if getattr(args, dest) and args.action not in actions:
                print(f"✖ {flag} only goes with {' or '.join(actions)}", file=sys.stderr)
                return 2
        from lib.app import guard
        t = _T[_lang()]
        names = args.repo or None
        if names and (unknown := sorted(set(names) - {x["name"] for x in guard.targets()})):
            print(f"✖ not a repo of this project: {', '.join(unknown)}", file=sys.stderr)
            return 2
        return {"install": _install, "status": _status, "gate": _gate, "uninstall": _uninstall}[args.action](args, guard, t, names)


def _lang() -> str:
    try:
        from lib.kanban import ops
        return "es" if ops.docs_lang() == "es" else "en"
    except Exception:                                        # noqa: BLE001 — a label must never break the command
        return "en"


def _install(args, guard, t, names) -> int:
    if not guard.enabled():
        print(t["off"])
        return 0
    changed = guard.install(log=(lambda _: None) if args.json else print, only=names)
    if args.json:
        print(json.dumps({"changed": changed}))
    else:
        print(t["done"] if changed else t["same"] if guard.targets(names) else t["none"])
    return 0


def _status(args, guard, t, names) -> int:
    rows = [r for r in guard.status() if names is None or r["name"] in names]
    if args.json:
        print(json.dumps({"enabled": guard.enabled(), "repos": rows}, ensure_ascii=False))
        return 0
    if not guard.enabled():
        print(t["off"])
    for r in rows:
        hooks = f"{t['hooks']}: {t['on']}" if not r["hooks"] else f"{t['hooks']}: {t['offs']} ({r['hooks']})"
        attr = f"{t['attr']}: {t['offs'] if r['attribution'] else t['on']}"          # attribution *off* is the guardrail
        print(f"  {'✔' if not r['hooks'] and r['attribution'] else '✖'} {r['name']:<14} {hooks} · {attr}")
    return 0


def _gate(args, guard, t, names) -> int:
    reports = guard.gate(names, base=args.base, latest=args.latest, log=(lambda _: None) if args.json else print)
    if args.json:
        print(json.dumps({"verdict": _verdict(reports), "repos": reports}, ensure_ascii=False))
    else:
        for rep in reports:
            print(f"{rep['repo']}  ({rep['base']}..{rep['head']})")
            for c in rep["checks"]:
                print(f"  {_MARK[c['status']]} {c['id']:<9} {t['state'][c['status']]}")
                for line in c["detail"][:12]:
                    print(f"      {line}")
        print(t[_verdict(reports)])
    return {"pass": 0, "fail": 1, "not-run": 3}[_verdict(reports)]


def _verdict(reports: list[dict]) -> str:
    from lib.domain import guard as rules
    return rules.overall([c for rep in reports for c in rep["checks"]])


def _uninstall(args, guard, t, names) -> int:
    gone = guard.uninstall(only=names)
    if args.json:
        print(json.dumps({"removed": gone}))
    elif gone:
        print(t["gone"].format(names=", ".join(gone)))
        print(t["again"])
    else:
        print(t["nothing"])
    return 0
