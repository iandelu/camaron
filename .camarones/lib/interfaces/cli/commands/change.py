"""`camaron change`: a coding change from the command line (WI-21, lib/app/change.py). One positional `action` plus
positionals (no nested subparsers, so `catalog.args_of` reads it), as `board` does. Exit 0 done, 1 blocked (one plain
line on stderr says why and what to do), 2 a usage error; --json output carries no prose."""
from __future__ import annotations

import argparse
import json
import sys

from lib.interfaces.cli.registry import CliContext, Command, command

ACTIONS = ("start", "phase", "status", "link", "close")
_ARGS = {"start": (1, 99), "phase": (1, 2), "status": (0, 1), "link": (1, 2), "close": (1, 1)}
_USAGE = {"start": 'start "TITLE" [--item WI-n] [--repo R]… [--files REPO:PATH,…] [--base REF] [--force]',
          "phase": "phase [ID] PHASE", "status": "status [ID]", "link": "link [ID] URL [--repo NAME|docs]",
          "close": "close ID [--abandon]"}
# flags that only mean something for some actions: anywhere else they are an error, not silently ignored
_ONLY = (("item", "--item", ("start",)), ("files", "--files", ("start",)), ("base", "--base", ("start",)),
         ("force", "--force", ("start",)), ("repo", "--repo", ("start", "link")), ("abandon", "--abandon", ("close",)))

_T = {
    "en": {"started": "🦐 {id} started: branches cut, docs worktree open", "again": "{id} was already open",
           "read": "Docs to read before coding:", "none_read": "No page matched: say so when you cite the docs",
           "next": "Next", "worktree": "docs worktree", "pr": "PR", "no_open":
           'No open change (start one: camaron change start "<title>" --item WI-n)', "card": "card"},
    "es": {"started": "🦐 {id} en marcha: ramas creadas, worktree de docs abierto", "again": "{id} ya estaba abierto",
           "read": "Docs que leer antes de programar:", "none_read": "Ninguna página coincide: dilo al citar los docs",
           "next": "Siguiente", "worktree": "worktree de docs", "pr": "PR", "no_open":
           'Ningún cambio abierto (empieza uno: camaron change start "<título>" --item WI-n)', "card": "tarjeta"},
}


@command("change", "cli")
class Change(Command):
    def run(self, args: argparse.Namespace, cli: CliContext) -> int:
        return run(args)

    def configure(self, p: argparse.ArgumentParser) -> None:
        p.add_argument("action", choices=ACTIONS)
        p.add_argument("args", nargs="*")
        p.add_argument("--item")
        p.add_argument("--repo", action="append")
        p.add_argument("--files", action="append")
        p.add_argument("--base")
        p.add_argument("--force", action="store_true")
        p.add_argument("--abandon", action="store_true")
        p.add_argument("--json", action="store_true")


def _lang() -> str:
    try:
        from lib.kanban import ops
        return "es" if ops.docs_lang() == "es" else "en"
    except Exception:                                        # noqa: BLE001 — a label must never break the command
        return "en"


def _fail(msg: str, code: int) -> int:
    print(f"✖ {msg}", file=sys.stderr)
    return code


def _usage(a) -> str | None:
    """The error line for a call that cannot mean anything, or None."""
    for dest, flag, actions in _ONLY:
        if getattr(a, dest, None) not in (None, False, []) and a.action not in actions:
            return f"{flag} only goes with: {', '.join(actions)}"
    lo, hi = _ARGS[a.action]
    if not lo <= len(a.args) <= hi:
        return f"usage: camaron change {_USAGE[a.action]}"
    if a.action == "link" and len(a.repo or ()) > 1:
        return "link takes one --repo"
    if a.action == "phase":
        from lib.domain import change as rules
        if a.args[-1] not in rules.PHASES:
            return f"unknown phase {a.args[-1]} (one of: {', '.join(rules.PHASES)})"
    return None


def run(a) -> int:
    wrong = _usage(a)
    if wrong:
        return _fail(wrong, 2)
    from lib.app import change
    from lib.core.locks import LockBusy
    try:
        return _run(a, change)
    except LookupError as e:                                 # which change, or which repo: the caller must say
        if isinstance(e, (KeyError, IndexError)):            # a bug, not a usage error
            raise
        return _fail(str(e), 2)
    except (change.ChangeError, LockBusy, OSError) as e:
        return _fail(str(e), 1)


def _dump(data) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2, default=str))


def _show(row: dict, t: dict) -> None:
    item = f"  {row['item']}" if row.get("item") else ""
    print(f"{row['id']}  {row['phase']}  {row['state']}{item}  {row.get('title') or ''}".rstrip())
    bases = row.get("bases") or {}
    for name, branch in row["repos"].items():
        print(f"  {name}: {branch} (from {bases.get(name)})")
    if row.get("worktree") and row["state"] != "closed":
        print(f"  {t['worktree']}: {row['worktree']} ({row.get('docs_branch')}, from {bases.get('docs')})")
    for name, url in row["prs"].items():
        print(f"  {t['pr']} {name}: {url}")
    if row.get("next"):
        print(f"  {t['next']}: {row['next']}")


def _start(a, change, t: dict) -> int:
    res = change.start(" ".join(a.args), item=a.item, repos=a.repo or (), files=a.files or (), base=a.base,
                       force=a.force)
    if a.json:
        _dump(res)
        return 0
    rec = res["change"]
    print((t["again"] if res["again"] else t["started"]).format(id=rec["id"]))
    for name, r in rec["repos"].items():
        print(f"  {name}: {r['branch']} (from {r['base_ref']})")
    docs = rec["docs"]
    print(f"  {t['worktree']}: {docs['worktree']} ({docs['branch']}, from {docs['base_ref']})")
    moved = [b for b in rec.get("board") or [] if b.get("to")]
    if moved and not res["again"]:
        print(f"  {t['card']} {rec['item']}: {moved[-1]['to']}")
    print(t["read"] if res["to_read"] else t["none_read"])
    for d in res["to_read"]:
        where = f"{d['path']}#{d['section']}" if d.get("section") else d["path"]
        print(f"  [{d['trust']}] {where}  ({d['why']})")
    print(f"{t['next']}: {res['next']}")
    return 0


def _run(a, change) -> int:
    t = _T[_lang()]
    x, args = a.action, a.args
    if x == "start":
        return _start(a, change, t)
    if x == "status":
        rows = change.status(args[0] if args else None)
        if a.json:
            _dump({"changes": rows})
        elif not rows:
            print(t["no_open"])
        for r in [] if a.json else rows:
            _show(r, t)
        return 0
    if x == "phase":
        rec = change.phase(args[0] if len(args) == 2 else None, args[-1])
    elif x == "link":
        rec = change.link(args[0] if len(args) == 2 else None, args[-1], repo=(a.repo or [None])[0])
    else:
        rec = change.close(args[0], abandon=a.abandon)
    row = change.row(rec)
    if a.json:
        _dump(row)
    else:
        _show(row, t)
    return 0
