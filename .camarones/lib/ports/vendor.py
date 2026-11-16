"""Vendor: what the app asks of npm to serve the graph viewers' CDN libraries from the portal itself: one file of a
package, fetched once with `npm pack` into the cache (an internal npm mirror works), and a site rewritten to use them."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Protocol


class Vendor(Protocol):
    CDN_RE: re.Pattern[str]

    def vendor(self, site: Path) -> tuple[int, list[str]]: ...

    def vendor_file(self, pkg: str, ver: str, path: str) -> Path | None: ...
