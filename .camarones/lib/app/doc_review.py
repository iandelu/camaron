"""A person's review of the docs: confirm pages (their body hash recorded, their freshness acknowledged) and the queue of
pages still waiting for a person, re-confirmations first."""
from __future__ import annotations

import re

from lib.app import doc_status, services
from lib.core.clock import now
from lib.core.paths import rel_file
from lib.domain.docs import frontmatter
from lib.domain.docs.page_versions import PageConflict


def confirm(files: list[str], by: str, body_sha: str | None = None) -> list[str]:
    """Each page is read, checked and written holding its lock. `body_sha` is the body the person read (the portal's
    one page): what a confirmation vouches for, so a page whose body changed since is a PageConflict and is not
    confirmed."""
    done = []
    for p in files:
        f = services.current().docs.resolve(p)
        with services.current().docs.page_lock(f):
            fm, body = frontmatter.split_fm(f.read_text(encoding="utf-8"))
            if not fm:
                raise RuntimeError(f"{p}: no frontmatter, refusing to confirm")
            sha = frontmatter.body_sha(body)
            if body_sha is not None and sha != body_sha:
                raise PageConflict(rel_file(f), "body_sha", sha)
            fm["x-confirmed"] = {"by": by, "at": now(), "body_sha": sha}
            f.write_text(frontmatter.join_fm(fm, body), encoding="utf-8", newline="\n")
        done.append(p)
        logical = next((lp for lp, df in services.current().docs.iter_docs() if df.resolve() == f.resolve()), None)
        if logical:
            from lib.harness import drafts, freshness
            try:
                drafts.record_confirmation(logical, body, by)
            except Exception:  # noqa: BLE001 — a measurement must never fail a confirmation
                pass
            freshness.ack([logical], by)          # a person checked it against today's code
    return done


REVIEW_ORDER = ["domain", "glossary", "business-flow", "architecture", "data-model", "deployment", "decision", "quality",
                "overview", "guide"]


def review_queue() -> list[dict]:
    """Pages waiting for a human: re-confirmations first, then by how much the doc type matters to agents."""
    rows = [r for r in doc_status.collect() if r["trust"] != "confirmed" and r["type"] != "interview" and r["owner"] != "human"
            and r["has_frontmatter"] and r["path"] != "status.md"]
    waiting = {m.group(1) for l in services.current().docs.pending_feedback() if (m := re.match(r"- \[ \] `([^`]+)`", l))}
    rows = [r for r in rows if r["file"] not in waiting]      # changes requested: back in the queue once the AI fixed them
    def key(r):
        t = r["type"] if r["type"] in REVIEW_ORDER else "zzz"
        return (0 if r["trust"] == "needs-reconfirm" else 1, REVIEW_ORDER.index(t) if t in REVIEW_ORDER else 99, r["path"])
    return sorted(rows, key=key)
