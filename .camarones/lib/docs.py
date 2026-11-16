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


