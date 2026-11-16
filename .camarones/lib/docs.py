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


