"""Docs model: workspace, repo sync, incremental state, trust (draft/confirmed), translations, llms.txt, search."""
from __future__ import annotations

import math, os, re
from collections import Counter
from pathlib import Path

from .app import services
from .core.clock import now
from .domain.docs import directives, frontmatter, logical_paths, page_outline, synonyms, trust_levels
from .core.paths import cli_cmd
from .common import KIT, ROOT, DOCS, CAM_DIR, repo_dir, rel_file, save_json


# ---------- workspace ----------


# ---------- incremental state ----------


# ---------- docs model ----------


SECTIONS = ["index.md", "overview", "architecture", "domain", "flows", "data", "deployment", "decisions", "quality",
            "guides", "repos"]


def confirm(files: list[str], by: str) -> list[str]:
    done = []
    for p in files:
        f = services.current().docs.resolve(p)
        fm, body = frontmatter.split_fm(f.read_text(encoding="utf-8"))
        if not fm:
            raise RuntimeError(f"{p}: no frontmatter, refusing to confirm")
        fm["x-confirmed"] = {"by": by, "at": now(), "body_sha": frontmatter.body_sha(body)}
        f.write_text(frontmatter.join_fm(fm, body), encoding="utf-8", newline="\n")
        done.append(p)
        logical = next((lp for lp, df in services.current().docs.iter_docs() if df.resolve() == f.resolve()), None)
        if logical:
            from .harness import drafts, freshness
            try:
                drafts.record_confirmation(logical, body, by)
            except Exception:  # noqa: BLE001 — a measurement must never fail a confirmation
                pass
            freshness.ack([logical], by)          # a person checked it against today's code
    return done


def translated(files: list[str]) -> list[str]:
    canon = dict(services.current().docs.iter_docs())
    done = []
    for p in files:
        f = services.current().docs.resolve(p)
        rel = f.relative_to(DOCS / "i18n")
        lang, logical = rel.parts[0], Path(*rel.parts[1:]).as_posix()
        if logical not in canon and (alias := logical_paths.old_wiki_path(logical)) in canon \
                and services.current().docs.translation_file(alias, lang).resolve() == f.resolve():
            logical = alias                       # a wiki page's translation kept at its pre-4.81 path
        if logical not in canon:
            raise RuntimeError(f"{p}: no canonical doc at {logical}")
        _, cbody = frontmatter.split_fm(canon[logical].read_text(encoding="utf-8"))
        fm, body = frontmatter.split_fm(f.read_text(encoding="utf-8"))
        fm["x-translation-of"] = {"path": logical, "lang": lang, "body_sha": frontmatter.body_sha(cbody)}
        f.write_text(frontmatter.join_fm(fm, body), encoding="utf-8", newline="\n")
        done.append(f"{p} <- {logical}")
    return done


def readable() -> list[dict]:
    """Rows an agent may read today (the freshness gate), in llms.txt order; interviews last."""
    from .harness import freshness
    rows = services.current().doc_status.collect()
    block = freshness.policy() == "block"
    ok = [r for r in rows if not block or freshness.gate(r["path"], r["trust"], r.get("freshness"))[0]]
    return sorted(ok, key=_llms_key)


def _llms_key(r: dict) -> tuple:
    head = r["path"].split("/")[0]
    return (r["type"] == "interview" or head == "interview",
            SECTIONS.index(head) if head in SECTIONS else len(SECTIONS), r["path"])


def llms() -> int:
    """docs/llms.txt (index, llmstxt.org) and docs/llms-full.txt (every page agents may read, one file)."""
    from .harness import freshness
    ws, rows = services.current().workspace.workspace(), services.current().doc_status.collect()
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


# ---------- search (portal + MCP): BM25 over body tokens, prefix-matched (pedido → pedidos) ----------


KIT_WORDS = {"camaron", "camarón", "camarones", "kit", "wizard", "tutorial"}


def kit_guides() -> set[str]:
    """Logical paths of the guides the kit copies into every project: about Camarón, not about the project."""
    return {f"guides/{f.name}" for f in (KIT / "templates" / "docs" / "guides").glob("*.md")}


def search(query: str, limit: int = 20) -> list[dict]:
    weights = synonyms.expand(query)
    terms = list(weights)
    if not terms:
        return []
    pages = []
    for logical, f in services.current().docs.iter_docs():
        fm, body = frontmatter.split_fm(f.read_text(encoding="utf-8", errors="replace"))
        trust = trust_levels.trust_of(fm, frontmatter.body_sha(body))
        body = page_outline.COMMENT_RE.sub(lambda m: "\n" * m.group().count("\n"), body)     # markers are not content
        toks = Counter(re.findall(r"\w+", body.lower()))
        tf = {t: sum(c for w, c in toks.items() if w.startswith(t)) for t in terms}
        title = fm.get("title") or frontmatter.first_heading(body) or f.stem
        meta = " ".join([str(title), str(fm.get("description") or ""), *map(str, fm.get("x-answers") or [])]).lower()
        pages.append((logical, trust, body, sum(toks.values()), tf, str(title), meta))
    if not pages:
        return []
    n, avg = len(pages), max(1.0, sum(p[3] for p in pages) / len(pages))
    idf = {t: math.log(1 + (n - (df := sum(1 for p in pages if p[4][t])) + 0.5) / (df + 0.5)) for t in terms}
    k1, b, hits = 1.2, 0.75, []
    for logical, trust, body, length, tf, title, meta in pages:
        score = sum(weights[t] * idf[t] * tf[t] * (k1 + 1) / (tf[t] + k1 * (1 - b + b * length / avg)) for t in terms)
        score += sum(2 * weights[t] * idf[t] for t in terms if t in meta or t in logical.lower())
        if score:
            lines = body.splitlines()
            at = [i for i, l in enumerate(lines) if any(t in l.lower() for t in terms)]
            secs = page_outline.sections(body)
            per = Counter(s for i in at if (s := page_outline.section_of(body, i, secs)))
            hits.append({"path": logical, "title": title, "trust": trust, "score": round(score, 2),
                         "section": per.most_common(1)[0][0] if per else None,
                         "lines": [lines[i].strip()[:240] for i in at[:3]]})
    guides = set() if KIT_WORDS & set(re.findall(r"\w+", query.lower())) else kit_guides()
    hits.sort(key=lambda h: (h["path"] in guides, -h["score"]))
    return hits[:limit]


# ---------- human review ----------
REVIEW_ORDER = ["domain", "glossary", "business-flow", "architecture", "data-model", "deployment", "decision", "quality",
                "overview", "guide"]


def review_queue() -> list[dict]:
    """Pages waiting for a human: re-confirmations first, then by how much the doc type matters to agents."""
    rows = [r for r in services.current().doc_status.collect() if r["trust"] != "confirmed" and r["type"] != "interview" and r["owner"] != "human"
            and r["has_frontmatter"] and r["path"] != "status.md"]
    waiting = {m.group(1) for l in services.current().docs.pending_feedback() if (m := re.match(r"- \[ \] `([^`]+)`", l))}
    rows = [r for r in rows if r["file"] not in waiting]      # changes requested: back in the queue once the AI fixed them
    def key(r):
        t = r["type"] if r["type"] in REVIEW_ORDER else "zzz"
        return (0 if r["trust"] == "needs-reconfirm" else 1, REVIEW_ORDER.index(t) if t in REVIEW_ORDER else 99, r["path"])
    return sorted(rows, key=key)


