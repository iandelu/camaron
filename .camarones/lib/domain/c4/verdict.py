"""The evidence state of a C4 element or relation, and whether agents are served it (spec §5.2). Pure."""
from __future__ import annotations

STATES = ("fresh", "suspect", "broken", "no-evidence", "unchecked")


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
