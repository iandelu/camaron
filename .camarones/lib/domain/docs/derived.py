"""The files the kit writes on its own. `REBUILT` comes back from the pages (doc status, llms.txt): a clash in one takes
the other side and rewrites it. `kit_written` adds the state the kit keeps beside the pages (freshness fingerprints,
each person's usage counters): never a person's unsaved work, though it cannot be rebuilt."""
from __future__ import annotations

REBUILT: tuple[str, ...] = ("docs/.status.json", "docs/llms.txt", "docs/llms-full.txt")
KEPT: tuple[str, ...] = ("docs/.work/fresh.json",)
KEPT_DIRS: tuple[str, ...] = ("docs/.work/usage/",)


def kit_written(path: str) -> bool:
    return path in REBUILT or path in KEPT or path.startswith(KEPT_DIRS)
