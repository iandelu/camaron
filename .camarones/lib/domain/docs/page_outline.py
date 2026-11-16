"""A page's outline: headings and their slugs (as the portal makes them), H2 sections as line ranges, the TL;DR and one
section's text. Pure: Markdown in, values out."""
from __future__ import annotations

import re

COMMENT_RE = re.compile(r"<!--.*?-->", re.S)
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
TLDR_RE = re.compile(r"^>\s*\*\*TL;DR:?\*\*", re.I)


def heading_text(md: str) -> str:
    """What a reader sees of a Markdown heading (the portal slugs its textContent)."""
    md = re.sub(r"<!--.*?-->", "", md)
    md = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", md)
    return re.sub(r"[`*]|(?<!\w)_|_(?!\w)", "", md).strip()


def slug(heading: str) -> str:
    """Mirror of the portal's slugify (portal/app/src/content/doc.js): lower case, letters/digits/space/_/- kept, spaces → -."""
    return re.sub(r"\s+", "-", re.sub(r"[^\w\s-]", "", heading_text(heading).lower().strip()))


def headings(body: str) -> list[dict]:
    """Every heading outside code: {level, title, slug, line}; a repeated slug gets -1, -2… like the portal."""
    out, seen, fence = [], {}, None
    for i, line in enumerate(body.splitlines()):
        if re.match(r"^\s*(```|~~~)", line):
            fence = None if fence else True
            continue
        m = None if fence else HEADING_RE.match(line)
        if not m:
            continue
        s = slug(m.group(2)) or "section"
        if s in seen:
            seen[s] += 1
            s = f"{s}-{seen[s]}"
        else:
            seen[s] = 0
        out.append({"level": len(m.group(1)), "title": heading_text(m.group(2)), "slug": s, "line": i})
    return out


def sections(body: str) -> list[dict]:
    """The page's H2 sections: {title, slug, start, end} as line ranges (a section runs to the next H1/H2)."""
    hs = headings(body)
    n = len(body.splitlines())
    h2 = [h for h in hs if h["level"] == 2]
    out = []
    for h in h2:
        end = next((x["line"] for x in hs if x["line"] > h["line"] and x["level"] <= 2), n)
        out.append({"title": h["title"], "slug": h["slug"], "start": h["line"], "end": end})
    return out


def section_of(body: str, line: int, secs: list[dict] | None = None) -> str | None:
    return next((s["slug"] for s in (secs if secs is not None else sections(body)) if s["start"] <= line < s["end"]), None)


def tldr(body: str) -> str:
    lines = body.splitlines()
    i = next((i for i, l in enumerate(lines) if TLDR_RE.match(l.strip())), None)
    if i is None:
        return ""
    out = []
    for l in lines[i:]:
        if not l.strip().startswith(">"):
            break
        out.append(l)
    return "\n".join(out)


def section_text(body: str, key: str) -> tuple[dict, str] | None:
    """The section whose slug or title is `key`, with its text (heading included)."""
    k = key.strip().lstrip("#").lower()
    s = next((s for s in sections(body) if s["slug"] == k or s["title"].lower() == k or s["slug"] == slug(key)), None)
    if not s:
        return None
    return s, "\n".join(body.splitlines()[s["start"]:s["end"]]).strip()
