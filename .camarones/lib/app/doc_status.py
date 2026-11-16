"""The docs' status: one row per page (trust, orphan sources, translations, space), the rows with their freshness written
to docs/.status.json, and `camaron check`'s errors and warnings over them."""
from __future__ import annotations

from pathlib import Path

from lib.app import services
from lib.common import CAM_DIR, DOCS, ROOT, rel_file, repo_dir, save_json
from lib.core.clock import now
from lib.core.paths import cli_cmd
from lib.domain.docs import frontmatter, trust_levels


def repo_file_exists(ref: str) -> bool:
    if ref.strip().startswith("c4:"):                   # `c4:<element>`: an element of docs/architecture/*.c4
        from lib.harness import freshness
        return freshness.c4_exists(ref.strip()[3:])
    ref = ref.split("#", 1)[0]
    if ref.startswith("repo://"):
        ref = ref[len("repo://"):].replace("/", ":", 1)
    if ":" not in ref:
        return True
    repo, path = ref.split(":", 1)
    base = ROOT if repo in ("umbrella", ".", CAM_DIR) else repo_dir(repo)
    return (base / path).exists()


def space_of(logical: str, f: Path, fm: dict) -> str:
    """docs = the documentation; notes = working notes (discovery, interviews); wiki = a repo's OpenWiki page."""
    if not f.is_relative_to(DOCS):
        return "wiki"
    return "notes" if fm.get("type") == "interview" or logical.startswith("interview/") else "docs"


def doc_status(logical: str, f: Path, langs: list[str]) -> dict:
    fm, body, fm_valid = frontmatter.parse_fm(f.read_text(encoding="utf-8"))
    sha = frontmatter.body_sha(body)
    trust = trust_levels.trust_of(fm, sha)
    missing = [s for s in (fm.get("x-sources") or []) if not repo_file_exists(str(s))]
    i18n, i18n_titles = {}, {}                  # i18n_titles: what the portal names the page in each language
    for lang in ([] if fm.get("type") == "interview" else langs):   # working notes are not translated
        tf = services.current().docs.translation_file(logical, lang)
        if not tf.exists():
            i18n[lang] = "missing"
        else:
            tfm, tbody = frontmatter.split_fm(tf.read_text(encoding="utf-8"))
            of = tfm.get("x-translation-of")                      # a hand-written one may be just the page's path
            i18n[lang] = "current" if isinstance(of, dict) and of.get("body_sha") == sha else "outdated"
            if title := tfm.get("title") or frontmatter.first_heading(tbody):
                i18n_titles[lang] = title
    return {"path": logical, "file": rel_file(f),
            "title": fm.get("title") or frontmatter.first_heading(body) or f.stem, "description": fm.get("description", ""),
            "type": fm.get("type", ""), "trust": trust, "owner": fm.get("x-owner", "ai"), "orphan_sources": missing,
            "space": space_of(logical, f, fm), "i18n": i18n, "i18n_titles": i18n_titles, "body_sha": sha,
            "has_frontmatter": bool(fm) or not fm_valid, "frontmatter_valid": fm_valid}


def collect() -> list[dict]:
    langs = services.current().workspace.workspace()["project"].get("translations", [])
    rows = [doc_status(l, f, langs) for l, f in services.current().docs.iter_docs()]
    try:
        from lib.harness import freshness
        states = freshness.states()
    except Exception:  # noqa: BLE001 — a repo that cannot be read must not hide the docs
        states = {}
    for r in rows:
        st = states.get(r["path"], {"state": "unverified", "changed": [], "missing": []})
        r["fresh"], r["freshness"] = st["state"], st
    save_json(services.current().doc_state.STATUS_FILE, {"generated_at": now(), "docs": rows})
    return rows


def check(strict: bool = False, secrets_only: bool = False) -> tuple[list[str], list[str]]:
    from lib import quality
    if secrets_only:
        return quality.check_secrets()
    errors, warns = [], []
    rows = collect()
    for r in rows:
        if not r.get("frontmatter_valid", True):
            errors.append(f"{r['file']}: invalid frontmatter (YAML does not parse) — quote values that contain ': '")
        elif not r["has_frontmatter"]:
            errors.append(f"{r['file']}: missing frontmatter")
        if r["orphan_sources"]:
            errors.append(f"{r['file']}: sources no longer exist: {r['orphan_sources']}")
        if r["trust"] == "needs-reconfirm":
            (errors if strict else warns).append(f"{r['file']}: changed after human confirmation")
        for lang, st in r["i18n"].items():
            if st != "current":
                warns.append(f"{r['file']}: translation {lang} {st}")
    for fn in quality.CHECKS:
        e, w = fn(rows, strict)
        errors += e
        warns += w
    for n in services.current().wiki.old_wikis():
        warns.append(f"wikis/{n}: written with an older, narrower scope — regenerate it for a complete wiki: "
                     f"{cli_cmd()} wiki {n}")
    return errors, warns + architecture_warnings()


def architecture_warnings() -> list[str]:
    """workspace.yaml `project.architecture` (where the C4 model lives): a value the kit cannot use, so the model stays
    in docs/architecture, or a repo folder that is not there yet."""
    from lib.domain import architecture
    ws = services.current().workspace
    try:
        ref = architecture.parse(ws.workspace()["project"].get(architecture.KEY), ws.repo_names())
    except ValueError as e:
        return [f"{e}; the C4 model stays in docs/architecture"]
    if ref and not services.current().diagrams.arch_dir().is_dir():
        return [f"project.architecture: {ref[0]}/{ref[1]} does not exist yet — clone {ref[0]} ({cli_cmd()} sync) "
                f"or fix the path in workspace.yaml"]
    return []
