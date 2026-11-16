"""A page's trust (draft, confirmed, needs-reconfirm) from its front matter and body hash, and the counts the status
shows."""
from __future__ import annotations


def trust_of(fm: dict, sha: str) -> str:
    conf = fm.get("x-confirmed") or {}
    return "confirmed" if conf.get("body_sha") == sha else ("needs-reconfirm" if conf else "draft")


def summary(rows: list[dict]) -> dict:
    c = {k: sum(1 for r in rows if r["trust"] == k) for k in ("confirmed", "needs-reconfirm", "draft")}
    c["total"] = len(rows)
    c["orphans"] = sum(1 for r in rows if r["orphan_sources"])
    c["untranslated"] = sum(1 for r in rows if any(v != "current" for v in r["i18n"].values()))
    return c
