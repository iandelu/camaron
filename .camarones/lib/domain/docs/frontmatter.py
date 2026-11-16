"""A page's front matter: read it (forgiving unquoted `key: a: b` values), split it from the body, write it back, and the
body hash that trust and freshness compare. Pure: text in, values out."""
from __future__ import annotations

import hashlib, json, re

import yaml

from lib.core import yamlio

FM_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?", re.S)

# agents often write `description: Foo: bar` unquoted; quote such top-level scalars instead of failing
LOOSE_VALUE_RE = re.compile(r"^([\w-]+):[ \t]+(?![\"'\[{|>&*!%@`])(.*?:\s.*?)[ \t]*$", re.M)


def parse_fm(text: str) -> tuple[dict, str, bool]:
    """(frontmatter, body, valid). Unreadable frontmatter yields {} but is still kept out of the body."""
    m = FM_RE.match(text)
    if not m:
        return {}, text, True
    raw, body = m.group(1), text[m.end():]
    for candidate in (raw, LOOSE_VALUE_RE.sub(lambda v: f"{v[1]}: {json.dumps(v[2], ensure_ascii=False)}", raw)):
        try:
            fm = yamlio.safe_load(candidate) or {}
        except yaml.YAMLError:
            continue
        if isinstance(fm, dict):
            return fm, body, True
    return {}, body, False


def split_fm(text: str) -> tuple[dict, str]:
    fm, body, _ = parse_fm(text)
    return fm, body


def join_fm(fm: dict, body: str) -> str:
    return "---\n" + yaml.safe_dump(fm, sort_keys=False, allow_unicode=True, width=120) + "---\n" + body


def body_sha(body: str) -> str:
    norm = "\n".join(line.rstrip() for line in body.strip().splitlines())
    return hashlib.sha256(norm.encode()).hexdigest()[:16]


def first_heading(body: str) -> str | None:
    m = re.search(r"^#\s+(.+)$", body, re.M)
    return m.group(1).strip() if m else None
