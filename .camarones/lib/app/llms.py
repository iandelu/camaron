"""docs/llms.txt (the index, llmstxt.org) and docs/llms-full.txt (every page agents may read, in one file), in the order
agents read them; the freshness gate decides which pages they may read today."""
from __future__ import annotations

import os, re

from lib.app import doc_status, services
from lib.common import DOCS, ROOT
from lib.domain.docs import directives, frontmatter

SECTIONS = ["index.md", "overview", "architecture", "domain", "flows", "data", "deployment", "decisions", "quality",
            "guides", "repos"]


def readable() -> list[dict]:
    """Rows an agent may read today (the freshness gate), in llms.txt order; interviews last."""
    from lib.harness import freshness
    rows = doc_status.collect()
    block = freshness.policy() == "block"
    ok = [r for r in rows if not block or freshness.gate(r["path"], r["trust"], r.get("freshness"))[0]]
    return sorted(ok, key=_llms_key)


def _llms_key(r: dict) -> tuple:
    head = r["path"].split("/")[0]
    return (r["type"] == "interview" or head == "interview",
            SECTIONS.index(head) if head in SECTIONS else len(SECTIONS), r["path"])


def llms() -> int:
    """docs/llms.txt (index, llmstxt.org) and docs/llms-full.txt (every page agents may read, one file)."""
    from lib.harness import freshness
    ws, rows = services.current().workspace.workspace(), doc_status.collect()
    home = next((r for r in rows if r["path"] == "index.md"), None)
    intro = (home or {}).get("description") or f"Living documentation of {ws['project']['name']}."
    lines = [f"# {ws['project']['name']}", "",
             f"> {intro} Trust: `confirmed` = verified by a human (source of truth); `draft` = AI-generated, verify "
             "against code; `needs-reconfirm` = confirmed, then changed.", "",
             "Every page below in one file: [llms-full.txt](llms-full.txt).", ""]
    ok = readable()
    served = {r["path"] for r in ok}
    section = None
    for r in ok:
        notes = r["type"] == "interview" or r["path"].startswith("interview/")
        top = r["path"].split("/")
        head = "Optional" if notes else ("/".join(top[:2]) if top[0] in ("repos", "wikis") and len(top) > 2
                                         else (top[0] if len(top) > 1 else "root"))
        if head != section:
            lines += ["", f"## {head}"]
            section = head
        link = os.path.relpath(ROOT / r["file"], DOCS).replace("\\", "/")
        desc = f": {r['description']}" if r["description"] else ""
        size = (len(frontmatter.split_fm((ROOT / r["file"]).read_text(encoding="utf-8"))[1]) + 3) // 4
        lines.append(f"- [{r['title']}]({link}) [{r['trust']}] (~{size} tokens){desc}")
    held = sorted((r for r in rows if r["path"] not in served), key=_llms_key)
    if section == "Optional":                        # llmstxt.org: Optional comes last
        tail = lines[lines.index("## Optional") - 1:]
        lines = lines[:lines.index("## Optional") - 1]
    else:
        tail = []
    old = [r for r in held if r["fresh"] in freshness.OUT_OF_DATE]
    if old:
        lines += ["", "## Out of date (read the code instead)", ""]
        lines += [f"- {r['path']}: {', '.join(freshness.code_paths(r['freshness']['missing'] + r['freshness']['changed']))}"
                  for r in old]
    waiting = [r for r in held if r["fresh"] not in freshness.OUT_OF_DATE]
    if waiting:
        lines += ["", "## Awaiting review (no sources to check them against)", ""]
        lines += [f"- {r['path']}" for r in waiting]
    lines += tail
    DOCS.mkdir(exist_ok=True)
    (DOCS / "llms.txt").write_text(re.sub(r"\n{3,}", "\n\n", "\n".join(lines)) + "\n", encoding="utf-8")
    full = [f"# {ws['project']['name']} — full documentation", "", f"> {intro}", ""]
    for r in ok:
        if r["type"] == "interview" or r["path"].startswith("interview/"):
            continue
        body = directives.flatten_directives(frontmatter.split_fm((ROOT / r["file"]).read_text(encoding="utf-8", errors="replace"))[1]).strip()
        desc = f" · {r['description']}" if r["description"] else ""
        full += [f"<!-- {r['path']} · {r['trust']}{desc} -->", "", body, ""]
    (DOCS / "llms-full.txt").write_text("\n".join(full).rstrip() + "\n", encoding="utf-8", newline="\n")
    return len(rows)
