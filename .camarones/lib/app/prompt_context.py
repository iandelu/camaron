"""What an agent should know before it acts on a prompt, with no model call (turning-point spec, P1): the best doc
sections through the same freshness gate as the MCP, the C4 elements behind them and the code-graph nodes the prompt
names, under CAP characters. The prompt hook (`hooks.prompt`) prints it into the session's context; a prompt that
matches nothing adds nothing."""
from __future__ import annotations

import json, re

from lib import c4edit
from lib.app import c4_lookup, services
from lib.common import out, repo_dir
from lib.domain.c4 import anchors, verdict
from lib.domain.c4.drift import NOT_SOURCE, TEST_FILE
from lib.domain.docs import directives, frontmatter, page_outline, synonyms
from lib.harness import freshness

CAP = 6000                 # characters added to the agent's context (~1,500 tokens)
MIN_WORDS = 3              # "ok", "go on", "yes please" are not questions about the system
SCORE_MIN = 1.0            # a page's BM25 score below this is noise, whatever the best page scored
REL = 0.35                 # …and so is one far below the best page
PAGES = 4
SECTION_CHARS = 1400
C4_TOP = 3
DECISIONS_TOP = 2
DESC_CHARS = 300
C4_MARK = "\x00"          # tags the C4 part, which is cut at line boundaries
NODES_TOP = 6
UNVERIFIED = {"state": "unverified", "changed": [], "missing": []}
# words that say what to do, not where: left out of name matching (C4, graph), kept for the docs search
REQUEST_WORDS = set("change changes add fix make update remove delete create new want need please why not does doesn "
                    "don also just like still into about".split()) | set(
    "cambiar cambia cambio añadir añade arreglar arregla quitar quita borrar crear crea nuevo nueva quiero hacer haz "
    "porque cuando también solo".split())
HEADER = ("Camarón — docs for this prompt, from cam-docs (no model call). `confirmed` is the source of truth; `draft` "
          "must be checked against the code; withheld pages are out of date or unreviewed. More: read_doc(path, "
          "section), ask, repo_graph.")


def _empty() -> dict:
    return {"text": "", "pages": [], "c4": [], "nodes": []}


def _terms(prompt: str) -> list[str]:
    """The prompt's own words (stopwords and request verbs out), lower case, in order: what to look for in names."""
    return [t for t, w in synonyms.expand(prompt).items() if w == 1.0 and t not in REQUEST_WORDS]


def _words(text: str) -> list[str]:
    """Words of an identifier or a sentence: RetryPolicy → retry, policy; retry_policy → retry, policy."""
    spaced = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", str(text))
    return [w.lower() for w in re.findall(r"[A-Za-z0-9]+", spaced)]


def _matches(term: str, words: list[str]) -> bool:
    """The word itself or a plural-like form of it (page → pages, camaron → camarones), not a longer word (check →
    checkpoint)."""
    return any(w == term or (len(term) >= 4 and w.startswith(term) and len(w) - len(term) <= 2) for w in words)


def _code_path(ref) -> str:
    """A source or evidence entry as a repo-relative path: `api:src/A.java#run` → `src/A.java`."""
    ref = str(ref).strip()
    if ref.startswith("c4:"):
        return ""
    return freshness.parse(ref)[1].split("#", 1)[0].strip()


def _pages(prompt: str) -> list[dict]:
    hits = services.current().search.search(prompt, 20)
    if not hits:
        return []
    floor = max(SCORE_MIN, REL * hits[0]["score"])
    hits = [h for h in hits if h["score"] >= floor][:PAGES]
    states = freshness.states()
    pages = []
    for h in hits:
        st = states.get(freshness.docs_alias(h["path"], states), UNVERIFIED)
        ok, notice = freshness.gate(h["path"], h["trust"], st)
        page = {"path": h["path"], "section": h.get("section"), "trust": h["trust"], "fresh": st["state"],
                "served": ok, "notice": notice, "text": "", "sources": [], "cited": []}
        f = services.current().docs.find_page(h["path"]) if ok else None
        if f:
            fm, body = frontmatter.split_fm(f.read_text(encoding="utf-8", errors="replace"))
            body = directives.flatten_directives(body)
            found = page_outline.section_text(body, h["section"]) if h.get("section") else None
            tl = page_outline.tldr(body)
            text = found[1].strip() if found else (tl or body.strip())
            if len(text) > SECTION_CHARS:
                text = text[:SECTION_CHARS].rsplit(" ", 1)[0] + " …"
            page["text"] = (tl + "\n\n" if tl and found else "") + text
            page["section"] = h["section"] if found else None
            sources = [str(x) for x in fm.get("x-sources") or []]
            page["sources"] = [p for p in map(_code_path, sources) if p]
            page["cited"] = [(r, path.split("#", 1)[0]) for r, path, _ in
                             map(freshness.parse, [x for x in sources if not x.startswith("c4:")]) if r and path]
        pages.append(page)
    return pages


def _named_paths(prompt: str, nodes: list[dict], elements: dict) -> set[tuple[str, str]]:
    """The (repo, path) of the files the prompt names: by file name (graph nodes, file anchors), as `repo:path`, or as
    a repo-relative path that exists in a repo."""
    names = {f.lower() for f in re.findall(r"[\w.-]+\.[A-Za-z]\w*", prompt)}
    found = {(n["repo"], n["file"]) for n in nodes if n["file"].rsplit("/", 1)[-1].lower() in names}
    found |= {(a.repo, a.path) for fqn in elements for a in anchors.of_element(fqn, elements)[0]
              if a.kind in ("file", "lines", "symbol") and a.path.rsplit("/", 1)[-1].lower() in names}
    repos = services.current().workspace.repo_names()
    for token in re.findall(r"[\w.-]+(?::|/)[\w./-]*[\w-]", prompt):
        repo, colon, rest = token.partition(":")
        if colon and repo in repos:
            found.add((repo, c4_lookup.normal(rest)))
        elif "/" in token and "." in token.rsplit("/", 1)[-1]:
            rel = c4_lookup.normal(token)
            found |= {(r, rel) for r in repos if repo_dir(r).joinpath(rel).is_file()}
    return found


def _c4_line(e: dict) -> str:
    head = (f"- {e['fqn']} — {e['title']} ({e['kind']}{', repo ' + e['repo'] if e['repo'] else ''}) · {e['state']}"
            + (f" · {e['notice']}" if e["notice"] else ""))
    desc = e["description"] if len(e["description"]) <= DESC_CHARS else e["description"][:DESC_CHARS].rsplit(" ", 1)[0] + " …"
    return "\n".join([head + (f": {desc}" if desc else "")]
                     + ([f"  evidence: {', '.join(e['evidence'][:3])}"] if e["evidence"] else [])
                     + [f"  decision: {d['path']} — {d['title']} ({d['status']})" for d in e["decisions"]])


def _c4(prompt: str, terms: list[str], files: set[tuple[str, str]], nodes: list[dict]
        ) -> tuple[list[dict], list[str]]:
    """(served elements, a `withheld:` line per element the evidence does not allow). Only the candidates are
    evaluated, and decision pages are read only when an element is served."""
    try:
        elements = c4edit.index()["elements"]
    except Exception:  # noqa: BLE001 — a model that does not parse must not hide the docs
        return [], []
    try:
        named = _named_paths(prompt, nodes, elements)
    except Exception:  # noqa: BLE001 — a path the system refuses to look up must not hide the rest
        named = set()
    covered = {}
    for repo, path in files | named:
        for fqn in c4_lookup.covering(repo, path, elements)[:1]:
            covered[fqn] = covered.get(fqn, 0) + 1
    scored = []
    for fqn, el in elements.items():
        name = _words(fqn) + _words(el.get("title", ""))
        desc = _words(el.get("description", ""))
        score = sum(2 for t in terms if _matches(t, name)) + sum(1 for t in terms if _matches(t, desc))
        score += 2 * covered.get(fqn, 0)
        if score >= 2:
            scored.append((-score, fqn, el))
    if not scored:
        return [], []
    scored.sort(key=lambda s: (s[0], s[1]))
    try:
        states = freshness.element_states(f for _, f, _ in scored)
    except Exception:  # noqa: BLE001
        return [], []
    policy, pages = freshness.policy(), None
    served, held = [], []
    for _, fqn, el in scored:
        if len(served) >= C4_TOP:
            break
        st = states.get(fqn) or {"state": "no-evidence", "confirmed": False, "anchors": []}
        ok, notice = verdict.serve(st["state"], bool(st["confirmed"]), policy)
        if not ok:
            if len(held) < C4_TOP:
                held.append(c4_lookup.withheld(fqn, notice, st["anchors"]))
            continue
        pages = c4_lookup.decision_pages() if pages is None else pages
        served.append({"fqn": fqn, "title": el.get("title", ""), "kind": el.get("kind", ""),
                       "repo": (el.get("metadata") or {}).get("repo", ""), "description": el.get("description", ""),
                       "state": st["state"], "notice": notice,
                       "evidence": [a["raw"] for a in c4_lookup.shown(st["anchors"])],
                       "decisions": c4_lookup.decisions_about(fqn, DECISIONS_TOP, elements, pages)})
    return served, held


def _graph_nodes(prompt: str, terms: list[str], paths: set[str]) -> tuple[list[dict], list[str]]:
    files = {f.lower() for f in re.findall(r"[\w.-]+\.[A-Za-z]\w*", prompt)}
    scored, stale = [], []
    about_tests = any(t.startswith("test") or t.startswith("prueba") for t in terms)
    for repo in services.current().workspace.workspace().get("repos") or []:
        name = repo.get("name") if isinstance(repo, dict) else None
        g = services.current().code.repo_graph(name) if name else None
        if not g or not g.is_file():
            continue
        try:
            data = json.loads(g.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        hits = []
        for n in data.get("nodes") or []:
            if n.get("file_type", "code") != "code":
                continue
            label, src = str(n.get("label") or ""), str(n.get("source_file") or "")
            if not src or src.endswith("/") or NOT_SOURCE.search(src) or "{" in label or "," in label:
                continue                                   # import entries, build output, vendored code
            if not about_tests and TEST_FILE.search(src):
                continue
            by_file = src.rsplit("/", 1)[-1].lower() in files
            named = (len(_words(label)) >= 2                                  # the prompt says RetryPolicy, not
                     and re.sub(r"[^a-z0-9]", "", label.lower()) in terms)     # just "charge"
            matched = [t for t in terms if len(t) >= 4 and _matches(t, _words(label))]
            cited = src in paths
            score = 3 * by_file + 3 * named + 2 * len(matched) + cited
            if by_file or named or len(matched) >= 2 or (matched and cited):
                hits.append((-score, -len(matched), src, label, n))
        if hits:
            scored += [(s, m, src, label, name, n) for s, m, src, label, n in hits]
            built = str(data.get("built_at_commit") or "")
            head = out(["git", "-C", str(repo_dir(name)), "rev-parse", "HEAD"])
            if built and head and not head.startswith(built) and not built.startswith(head):
                stale.append(f"graph of {name} built at {built[:7]}, the repo is at {head[:7]}: rebuild with "
                             "`camaron graph`")
    scored.sort(key=lambda s: s[:4])
    best = scored[0][0] if scored else 0
    seen, nodes = set(), []
    for score, _, src, label, repo, n in scored:
        if score > best + 2 or (repo, src, label) in seen:   # far below the best match: a common word, not a name
            continue
        seen.add((repo, src, label))
        nodes.append({"label": label, "repo": repo, "file": src, "line": str(n.get("source_location") or "")})
        if len(nodes) >= NODES_TOP:
            break
    return nodes, stale


def _render(pages: list[dict], c4: list[dict], held: list[str], nodes: list[dict], stale: list[str]) -> str:
    parts = [HEADER]
    for p in pages:
        if p["served"]:
            cite = p["path"] + (f"#{p['section']}" if p["section"] else "")
            parts.append(f"[{cite}] ({p['trust']} · {p['fresh']})\n{p['text']}")
    held_pages = [p for p in pages if not p["served"]]
    if held_pages:
        parts.append("\n".join(f"- {p['notice']}" for p in held_pages))
    if c4 or held:
        parts.append(C4_MARK + "C4 elements:\n" + "\n".join([*map(_c4_line, c4), *(f"- {h}" for h in held)]))
    if nodes:
        parts.append("Code graph:\n" + "\n".join(
            f"- {n['label']} — {n['repo']}/{n['file']}" + (f":{n['line']}" if n["line"] else "") for n in nodes)
            + "".join(f"\n({s})" for s in stale))
    text = ""
    for part in parts:
        room = CAP - len(text) - 2
        if room <= 0:
            break
        by_line = part.startswith(C4_MARK)
        part = part.removeprefix(C4_MARK)
        if len(part) > room:
            cut = part[:max(0, room - 2)]
            if by_line and "\n" in cut:                    # a head line keeps its state and notice or goes whole
                cut = cut[:cut.rindex("\n")]
            part = cut + " …"
        text += ("\n\n" if text else "") + part
    return text[:CAP]


def build(prompt: str) -> dict:
    """{text, pages, c4, nodes}: `text` is what the hook prints, empty when the prompt matches nothing."""
    prompt = str(prompt or "")
    if len(re.findall(r"\w+", prompt)) < MIN_WORDS:
        return _empty()
    terms = _terms(prompt)
    pages = _pages(prompt)
    paths = {s for p in pages for s in p["sources"]}
    files = {(r, f) for p in pages for r, f in p["cited"]}
    nodes, stale = _graph_nodes(prompt, terms, paths)
    c4, held = _c4(prompt, terms, files, nodes)
    if not (pages or c4 or held or nodes):
        return _empty()
    return {"text": _render(pages, c4, held, nodes, stale), "pages": [{k: p[k] for k in ("path", "section", "trust", "fresh",
            "served")} for p in pages], "c4": [e["fqn"] for e in c4], "nodes": nodes}
