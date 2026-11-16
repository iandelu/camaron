"""A change's pure rules (WI-21): the phases a coding change goes through and their order, the fixed rules by which the
kit moves the change's board card, its id, slug and branch name, and which change a command means. Values in, values
out: the record is a dict (lib/app/change.py reads and writes it), no git, no files."""
from __future__ import annotations

import re
import string
import unicodedata
from typing import Sequence

PHASES = ("docs", "assess", "plan", "code", "docs-update", "verify", "ship", "retro")
RULES = {"start": "In Progress", "pr": "In Review", "merged": "Done", "abandon": "Ready"}
# where a card already is when a rule has nothing to do: never back out of a later column by a rule
_LEAVE = {"start": ("In Progress", "In Review"), "pr": ("In Review", "Done"), "merged": ("Done",),
          "abandon": ("Backlog", "Ready", "Done")}
BRANCH = "cam/{id}-{slug}"                # `change.branch` in workspace.yaml replaces it
STATES = ("open", "in-review", "closed")  # `prepared` (pushed, no PR opened) is WI-24's
OPEN = ("open", "in-review")


def advance(current: str, new: str) -> bool:
    """True when `new` is a later phase, False when it is the current one. ValueError for an unknown phase or one
    before the current: a phase only moves forward (it may skip ahead)."""
    if new not in PHASES:
        raise ValueError(f"unknown phase {new} (one of: {', '.join(PHASES)})")
    if current in PHASES and PHASES.index(new) < PHASES.index(current):
        raise ValueError(f"a phase never goes back: the change is in {current}, {new} comes before it")
    return new != current


def board_target(rule: str, status: str) -> str | None:
    """The column `rule` moves a card in `status` to, or None when it leaves the card where it is."""
    return None if status in _LEAVE[rule] else RULES[rule]


def slugify(title: str, words: int = 4, limit: int = 30) -> str:
    """The title's first words, ASCII, lower case, dash-separated, at most `limit` characters."""
    plain = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode("ascii").lower()
    parts = re.findall(r"[a-z0-9]+", plain)[:words]
    return "-".join(parts)[:limit].strip("-") or "change"


def change_id(item: str | None, slug: str, rand_hex: str) -> str:
    return item.strip().lower() if item else f"{slug}-{rand_hex}"


def branch_name(template: str, id_: str, slug: str) -> str:
    """The branch `template` names for the change. Without an item the id already carries the slug, so the caller
    passes `slug=""` and the separators it leaves are dropped."""
    fields = {f for _, f, _, _ in string.Formatter().parse(template) if f is not None}
    if fields - {"id", "slug"}:
        raise ValueError(f"change.branch: only {{id}} and {{slug}} can be used (got {template!r})")
    if "id" not in fields:
        raise ValueError(f"change.branch must contain {{id}} (got {template!r})")
    name = re.sub(r"[^A-Za-z0-9._/-]+", "-", template.format(id=id_, slug=slug))
    name = re.sub(r"-{2,}", "-", name)
    name = re.sub(r"-+(?=/)|(?<=/)-+", "", name)
    return name.strip("-/.")


def pick(records: Sequence[dict], wanted: str | None, branches: Sequence[str]) -> dict:
    """The change a command means among the open `records`: the one named, else the one whose branch is checked out
    in the current folder (`branches`), else the only one. LookupError says why none fits."""
    ids = ", ".join(r["id"] for r in records)
    if wanted:
        found = [r for r in records if r["id"] == wanted.strip().lower()]
        if not found:
            raise LookupError(f"no open change {wanted.strip().lower()}" + (f" (open: {ids})" if ids else ""))
        return found[0]
    if not records:
        raise LookupError("no open change (start one: camaron change start \"<title>\" --item WI-n)")
    mine = [r for r in records if _branches(r) & set(branches)]
    if len(mine) == 1:
        return mine[0]
    if len(records) == 1:
        return records[0]
    raise LookupError(f"several changes are open ({ids}): name one")


def _branches(r: dict) -> set[str]:
    return {v.get("branch") for v in (r.get("repos") or {}).values()} | {(r.get("docs") or {}).get("branch")}


_NEXT = {
    "docs": "read the docs it lists and cite them, then: camaron change phase {id} assess",
    "assess": "score the difficulty (skill cam-difficulty), then: camaron change phase {id} plan",
    "plan": "plan as the level says (medium and high: the person approves it), then: camaron change phase {id} code",
    "code": "implement test-first and commit, then: camaron change phase {id} docs-update",
    "docs-update": "update and commit the docs in the worktree, then: camaron change phase {id} verify",
    "verify": "run the verification (skill cam-verify), then: camaron change phase {id} ship",
    "ship": "guardrails, impact, one question, the PRs; then for each PR: camaron change link {id} <url>",
}


def next_step(rec: dict) -> str:
    """One line: what the change needs next. Empty once it is closed."""
    if rec.get("state") not in OPEN:
        return ""
    phase, id_ = rec.get("phase"), rec["id"]
    if phase == "ship" and rec.get("prs"):
        return f"camaron change phase {id_} retro"
    if phase == "retro":
        if rec.get("prs"):
            return f"once the PRs are merged: camaron change close {id_}"
        return f"link the PRs: camaron change link {id_} <url> (or give up: camaron change close {id_} --abandon)"
    return _NEXT.get(phase, "").format(id=id_)
