"""The evidence state of a C4 element or relation, and whether agents are served it (spec §5.2). Pure."""
from __future__ import annotations

STATES = ("fresh", "suspect", "broken", "no-evidence", "unchecked")
FIX = {"broken": "is broken: fix its `code`",
       "no-evidence": "has no evidence: add `code` to it or have a person confirm it"}


def combine(results: list[str]) -> str:
    """One state from the per-anchor results (`fresh`, `changed`, `missing`, `unchecked`)."""
    if not results:
        return "no-evidence"
    if "missing" in results:
        return "broken"
    if "changed" in results:
        return "suspect"
    if all(r == "unchecked" for r in results):
        return "unchecked"
    return "fresh"


def serve(state: str, confirmed: bool, policy: str = "block") -> tuple[bool, str | None]:
    """Whether an agent may read it, and the notice to show with it (or instead of it). `warn` serves everything."""
    if state not in STATES:
        raise ValueError(f"unknown state {state!r}")
    blocking = policy != "warn"
    if state == "broken":
        return (not blocking), ("withheld: some of its evidence is gone. Read the code instead." if blocking
                                else "may be out of date: some of its evidence is gone.")
    if state == "no-evidence":
        if confirmed:
            return True, "vouched for by a person; nothing in the code backs it."
        return (not blocking), ("withheld: nothing in the code backs it and no person confirmed it." if blocking
                                else "unreviewed: nothing in the code backs it.")
    if state == "suspect":
        return True, "its code changed: verify."
    if state == "unchecked":
        return True, "not checked here."
    return True, None


def advice(held: dict) -> str:
    """What settles a page suspect through its C4 elements ({`c4:` source: state}): their evidence, never
    `fresh --ack`."""
    parts = []
    for state, fix in FIX.items():
        if names := ", ".join(s.strip()[3:].strip() for s, got in held.items() if got == state):
            parts.append(f"its C4 element {names} {fix}")
    return "; ".join(parts) + " (`camaron arch-verify`)"
