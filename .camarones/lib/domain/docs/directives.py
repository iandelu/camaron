"""`:::` blocks of a page (the portal's directives): the `:::rule` blocks as data, and every known block flattened to plain
Markdown for agents and exports. Pure: Markdown in, values out."""
from __future__ import annotations

import re

DIRECTIVES = ("tabs", "cards", "steps", "details", "tech", "business", "rule")
RULE_META = re.compile(r"^(enforced|test):\s*(.+)$")


def _rule(arg: str, body: list[str]) -> dict:
    rid, _, title = arg.partition(" ")
    meta, text = {"enforced": [], "test": []}, []
    for line in body:
        m = RULE_META.match(line.strip())
        if m:
            meta[m.group(1)] += [r.strip() for r in m.group(2).split(",") if r.strip()]
        else:
            text.append(line)
    return {"id": rid, "title": title.strip(), "text": "\n".join(text).strip(), **meta}


def rules(md: str) -> list[dict]:
    """The `:::rule ID [title]` blocks of a page (X8): `enforced:` / `test:` lines hold `repo:path#Symbol` anchors."""
    out, fence, lines = [], None, md.split("\n")
    for i, line in enumerate(lines):
        f = re.match(r"^\s*(```|~~~)", line)
        if f:
            fence = None if fence and line.strip().startswith(fence) else (fence or f.group(1))
        m = None if fence else re.match(r"^:::\s*rule\s+(.+)$", line, re.I)
        end = next((j for j in range(i + 1, len(lines)) if re.match(r"^:::\s*$", lines[j])), None) if m else None
        if m and end is not None:
            out.append(_rule(m.group(1).strip(), lines[i + 1:end]))
    return out


def flatten_directives(md: str) -> str:
    """`:::` blocks (portal/app/src/content/directives.js) as plain Markdown for agents and exports: a tab or details
    summary becomes a bold line, the rest keeps its content. Code fences and unknown kinds are left alone."""
    lines, out, i, fence = md.split("\n"), [], 0, None
    while i < len(lines):
        line = lines[i]
        f = re.match(r"^\s*(```|~~~)", line)
        if f:
            fence = None if fence and line.strip().startswith(fence) else (fence or f.group(1))
        m = None if fence else re.match(r"^:::\s*(\w+)\s*(.*)$", line)
        end = next((j for j in range(i + 1, len(lines)) if re.match(r"^:::\s*$", lines[j])), None) if m else None
        if m and m.group(1).lower() in DIRECTIVES and end is not None:
            kind, arg, body = m.group(1).lower(), m.group(2).strip(), lines[i + 1:end]
            if kind == "tabs":
                for b in body:
                    t = re.match(r"^::tab\s+(.+)$", b)
                    out += ["", f"**{t.group(1).strip()}**", ""] if t else [b]
            elif kind == "details":
                out += [f"**{arg or 'Details'}**", "", *body]
            elif kind == "rule":
                r = _rule(arg, body)
                out += [f"**Rule {r['id']}" + (f" — {r['title']}" if r["title"] else "") + "**", "", r["text"]]
                out += [f"{label}: " + ", ".join(f"`{x}`" for x in r[key])
                        for key, label in (("enforced", "Enforced by"), ("test", "Tested by")) if r[key]]
            else:
                out += body
            i = end + 1
            continue
        out.append(line)
        i += 1
    text = re.sub(r"\n{3,}", "\n\n", "\n".join(out))
    return text.lstrip("\n") if not md.startswith("\n") else text
