"""What a git remote points at, whatever its spelling: the team's repos are matched by it (lib/app/repos_here.py,
lib/projects.py), never by a folder's name."""
from __future__ import annotations

import os, re, urllib.parse
from pathlib import Path


def remote_key(url: str) -> str:
    """What a git remote points at, so the scp, https, ssh:// and token-in-URL spellings of one repo compare equal."""
    u = url.strip()
    m = re.match(r"^[\w.+-]+@([^:/]+):(?!//)(.+)$", u)                  # git@host:group/repo.git
    if m:
        host, path = m.groups()
    else:
        p = urllib.parse.urlparse(u)
        if not p.hostname:                                             # local path or file:// (tests, shared drives)
            from urllib.request import url2pathname                    # lazy: it loads http.client on every start
            local = url2pathname(p.path) if p.scheme == "file" else u
            return os.path.normcase(str(Path(local).resolve()))
        host, path = p.hostname, p.path
    return f"{host.lower()}/{path.strip('/').removesuffix('.git').strip('/').lower()}"
