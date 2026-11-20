"""What a fingerprint hashes: a source's lines without whitespace runs, blank lines or comment-only lines. Pure."""
from __future__ import annotations

import hashlib
import re

COMMENT = re.compile(r"^(//|#|/\*|\*|<!--|-->|--\s|;)")


def norm(lines: list[str]) -> list[str]:
    out = []
    for line in lines:
        s = re.sub(r"\s+", " ", line.strip())
        if s and not COMMENT.match(s):
            out.append(s)
    return out


def digest(lines: list[str]) -> str:
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()[:16]
