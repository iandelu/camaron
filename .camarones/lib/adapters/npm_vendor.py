"""The graph viewers' CDN libraries served from the portal itself: each file fetched once with `npm pack` into the cache
(works with an internal npm mirror), and a site's pages rewritten to load them from /vendor/. Behind
lib/ports/vendor.py."""
from __future__ import annotations

import re, shutil, tarfile, tempfile
from pathlib import Path

from lib.common import CACHE, run

CDN_RE = re.compile(r"https://(?:cdn\.jsdelivr\.net/npm|unpkg\.com)/((?:@[\w.-]+/)?[\w.-]+)@([\w.+-]+)/([\w./+-]+)")


def vendor(site: Path) -> tuple[int, list[str]]:
    """Graph viewers load libraries from CDNs: fetch them through npm (works with an internal npm mirror) and
    serve them from /vendor/ so the portal works on-prem without internet."""
    targets = [f for d in ("code-graph", "wiki-graph") if (site / d).exists()
               for f in (site / d).rglob("*") if f.suffix in (".html", ".js")]
    done, failed = set(), set()
    for f in targets:
        text = f.read_text(encoding="utf-8", errors="ignore")
        def sub(m):
            pkg, ver, path = m.groups()
            key = f"{pkg}@{ver}"
            src = None if key in failed else vendor_file(pkg, ver, path)
            if not src:
                failed.add(key)
                return m.group(0)
            done.add(key)
            dst = site / "vendor" / key / path
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dst)
            return f"/vendor/{key}/{path}"
        new = CDN_RE.sub(sub, text)
        if new != text:
            f.write_text(new, encoding="utf-8")
    return len(done), sorted(failed)


def vendor_file(pkg: str, ver: str, path: str) -> Path | None:
    """One file of an npm package, fetched once with `npm pack` into the cache."""
    cache = CACHE / "vendor-cache"
    pkg_dir = cache / f"{pkg}@{ver}".replace("/", "__")
    if not pkg_dir.exists():
        cache.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory() as tmp:
            r = run(["npm", "pack", f"{pkg}@{ver}", "--silent", "--pack-destination", tmp], check=False, capture=True)
            tgz = next(Path(tmp).glob("*.tgz"), None)
            if r.returncode != 0 or not tgz:
                return None
            with tarfile.open(tgz) as t:
                try:
                    t.extractall(pkg_dir, filter="data")
                except TypeError:
                    t.extractall(pkg_dir)
    f = (pkg_dir / "package" / path).resolve()
    return f if f.is_file() and pkg_dir.resolve() in f.parents else None
