"""The time as the kit writes it: UTC, to the second."""
from __future__ import annotations

import datetime as dt


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
