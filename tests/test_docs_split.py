"""The split of lib/docs.py (hexagonal refactor F5a): every name it defines has one home, a moved name lives in its home,
domain modules stay pure, and kit code reaches a moved store or use case through services (lib/app/services.py), or
directly where its layer may import it (an adapter importing a store)."""
from __future__ import annotations

import ast
import importlib
import re

from conftest import KIT_DIR, REPO
from fixtures import archscan

# The names docs.py defined before the split (top-level def, class and assignment targets), generated once with ast.
DOCS_NAMES = frozenset({
    "CDN_RE", "COMMENT_RE", "DIRECTIVES", "FEEDBACK", "FM_RE", "GI_END", "GI_START", "HEADING_RE", "IMPLIED",
    "INTERVIEW_MODES", "KIT_WORDS", "LOOSE_VALUE_RE", "Log", "REVIEW_ORDER", "RULE_META", "SECTIONS", "STATE_FILE",
    "STATUS_FILE", "STOPWORDS", "TERMS_FILE", "TLDR_RE", "_llms_key", "_rule", "add_feedback", "body_sha",
    "changes", "check", "collect", "confirm", "detect_repos", "doc_status", "expand", "find_page", "first_heading",
    "flatten_directives", "git", "guess_kind", "heading_text", "headings", "interview_mode",
    "interview_mode_chosen", "iter_docs", "join_fm", "kit_guides", "link_target", "llms", "mark_documented", "now",
    "old_wiki_path", "parse_fm", "pending_feedback", "readable", "repo_file_exists", "repo_names", "resolve",
    "review_queue", "rules", "save_workspace", "search", "search_terms", "section_of", "section_text", "sections",
    "set_interview_mode", "set_wiki_repos", "slug", "space_of", "split_fm", "summary", "sync_repos", "tldr",
    "translated", "translation_file", "trust_of", "vendor", "vendor_file", "wiki_dir", "wiki_path", "wiki_repos",
    "workspace", "write_gitignore", "ws_file",
})

# The plan's Name map (cam-docs docs/.work/plans/2026-11-14-hexagonal-f5-domain.md): each home, a dotted module under
# lib, and the names it receives from docs.py.
_MAP: dict[str, tuple[str, ...]] = {
    "core.clock": ("now",),
    "ports": ("Log",),
    "domain.docs.frontmatter": ("FM_RE", "LOOSE_VALUE_RE", "parse_fm", "split_fm", "join_fm", "body_sha",
                                "first_heading"),
    "domain.docs.trust_levels": ("trust_of", "summary"),
    "domain.docs.logical_paths": ("wiki_path", "old_wiki_path", "link_target"),
    "domain.docs.page_outline": ("COMMENT_RE", "HEADING_RE", "TLDR_RE", "heading_text", "slug", "headings",
                                 "sections", "section_of", "tldr", "section_text"),
    "domain.docs.directives": ("DIRECTIVES", "RULE_META", "_rule", "rules", "flatten_directives"),
    "domain.docs.synonyms": ("STOPWORDS", "TERMS_FILE", "IMPLIED", "search_terms", "expand"),
    "adapters.stores.workspace": ("ws_file", "workspace", "save_workspace", "repo_names", "wiki_repos",
                                  "INTERVIEW_MODES", "interview_mode", "interview_mode_chosen", "set_interview_mode",
                                  "set_wiki_repos", "GI_START", "GI_END", "write_gitignore"),
    "adapters.git.repos": ("git", "detect_repos", "guess_kind", "sync_repos"),
    "adapters.stores.doc_state": ("STATE_FILE", "STATUS_FILE", "changes", "mark_documented"),
    "adapters.stores.doc_store": ("iter_docs", "find_page", "translation_file", "wiki_dir", "resolve", "FEEDBACK",
                                  "add_feedback", "pending_feedback"),
    "adapters.npm_vendor": ("CDN_RE", "vendor", "vendor_file"),
    "app.doc_status": ("repo_file_exists", "space_of", "doc_status", "collect", "check"),
    "app.llms": ("SECTIONS", "readable", "_llms_key", "llms"),
    "app.doc_review": ("REVIEW_ORDER", "confirm", "review_queue"),
    "app.translations": ("translated",),
    "app.search": ("KIT_WORDS", "kit_guides", "search"),
}
HOME: dict[str, str] = {name: home for home, names in _MAP.items() for name in names}
# Names that join a store from another module (plan Q5), not docs names: the facade does not re-export them.
FROM_ONBOARD = {"WS_HEADER": "adapters.stores.workspace", "write_workspace": "adapters.stores.workspace"}
# MOVED: the homes whose names have moved; each task adds its own
MOVED: set[str] = {"core.clock", "ports", "domain.docs.frontmatter", "domain.docs.trust_levels", "domain.docs.page_outline",
                   "domain.docs.logical_paths", "domain.docs.directives", "domain.docs.synonyms",
                   "adapters.stores.workspace", "adapters.git.repos"}
NEW: set[str] = {home for home in _MAP if home.startswith(("domain.", "adapters.", "app."))}

# `services.docs` is the DocStore field (plan Q7), not lib.docs: the patterns skip it
# any chain before docs (kit.docs.X, pg.kit.docs.X, a bare docs.X), except the services field
TEST_READS = (re.compile(r"(?<![\w./@:#-])(?:\w+\.)*(?<!services\.)docs\.([A-Za-z_]\w*)"),   # not a URL's docs.git
              re.compile(r"lib\.docs\.([A-Za-z_]\w*)"),
              re.compile(r"setattr\(\s*(?:(?!services\b)\w+\.)*docs\s*,\s*[\"']([A-Za-z_]\w*)[\"']"))
CODE_STRING_READ = re.compile(r"(?<![\w.])docs\.([A-Za-z_]\w*)")


def _layer(name: str) -> str | None:
    return archscan.layer_of(name, archscan.load_layers())


def _is_facade(path) -> bool:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return any(isinstance(t, ast.Name) and t.id == "__facade__"
               for n in tree.body if isinstance(n, ast.Assign) for t in n.targets)


def test_every_docs_name_has_one_home():
    listed = [name for names in _MAP.values() for name in names]
    assert sorted({n for n in listed if listed.count(n) > 1}) == []
    assert set(HOME) == DOCS_NAMES
    assert not set(FROM_ONBOARD) & DOCS_NAMES


def test_moved_names_live_in_their_home(kit):
    docs = importlib.import_module("lib.docs")
    wrong = []
    for name, home in sorted({**HOME, **FROM_ONBOARD}.items()):
        if home not in MOVED:
            continue
        mod = importlib.import_module(f"lib.{home}")
        if not hasattr(mod, name):
            wrong.append(f"lib.{home} has no {name}")
        elif name in DOCS_NAMES and name in vars(docs) and getattr(docs, name) is not getattr(mod, name):
            wrong.append(f"lib.docs.{name} is not lib.{home}.{name}")   # docs may import it back, as that very object
        elif home.startswith(("adapters.", "app.")) and name in vars(docs) and not _is_facade(KIT_DIR / "lib/docs.py"):
            wrong.append(f"lib.docs still has {name} (moved to lib.{home})")
    assert wrong == []


def test_domain_imports_only_core_and_domain():
    mods = archscan.modules(KIT_DIR)
    bad = sorted(f"{a} -> {b}" for a, b in archscan.edges(mods)
                 if a.startswith("domain.") and not b.startswith(("core", "domain")))
    assert bad == [], "domain is data in, data out: it imports only lib.core and lib.domain\n" + "\n".join(bad)


def test_moved_code_is_reached_through_services():
    """A new store or use case is imported only by the new modules, bootstrap, the docs facade, or a module whose layer
    may import it (plan Q2: an adapter imports a store directly). Everything else goes through services."""
    mods = archscan.modules(KIT_DIR)
    facade = _is_facade(mods["docs"])
    targets = {h for h in NEW & MOVED if h.startswith(("adapters.", "app."))}
    bad = sorted(f"{a} -> {b}" for a, b in archscan.edges(mods)
                 if b in targets and not (a in NEW or a == "bootstrap" or (a == "docs" and facade)
                                          or _layer(b) in archscan.ALLOWED.get(_layer(a) or "", ())))
    assert bad == [], ("kit code reaches a moved store or use case through services (cli.services, req.services or "
                       "services.current()), never by importing its module:\n" + "\n".join(bad))


def _docs_aliases(name: str, path, tree) -> set[str]:
    """Local names bound to the module lib.docs in one kit module, however it imported it."""
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and (node.level or archscan._is_kit(node.module)):
            target = archscan._from_target(name, path.name == "__init__.py", node)
            out |= {a.asname or a.name for a in node.names if (f"{target}.{a.name}" if target else a.name) == "docs"}
        elif isinstance(node, ast.Import):
            out |= {a.asname for a in node.names if a.name == "lib.docs" and a.asname}
    return out


def test_no_kit_code_reaches_a_moved_name_through_docs():
    """Every read, executed or not: attribute reads on an alias of lib.docs, `from lib.docs import X`, and `docs.X` in
    a string constant (lib/harness/integrate.py runs kit code from strings in a unit's tree)."""
    found = []
    mods = archscan.modules(KIT_DIR)
    if _is_facade(mods["docs"]):
        return
    for name, path in sorted(mods.items()):
        if name == "docs":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        aliases = _docs_aliases(name, path, tree)
        for node in ast.walk(tree):
            hits: set[str] = set()
            if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id in aliases:
                hits.add(node.attr)
            elif isinstance(node, ast.ImportFrom) and (node.level or archscan._is_kit(node.module)) \
                    and archscan._from_target(name, path.name == "__init__.py", node) == "docs":
                hits |= {a.name for a in node.names}
            elif isinstance(node, ast.Constant) and isinstance(node.value, str) and "docs." in node.value:
                hits |= {m.group(1) for m in CODE_STRING_READ.finditer(node.value)}
            found += [f"{name}:{node.lineno}: docs.{n} (now lib.{HOME[n]})" for n in sorted(hits)
                      if HOME.get(n) in MOVED]
    assert found == []


def test_no_test_reaches_a_moved_name_through_docs():
    found = []
    for f in sorted((REPO / "tests").rglob("*.py")):
        if f.name == "test_docs_split.py":
            continue
        for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            names = {m.group(1) for pattern in TEST_READS for m in pattern.finditer(line)}
            found += [f"{f.relative_to(REPO).as_posix()}:{i}: {n} (read or patch lib.{HOME[n]})"
                      for n in sorted(names) if HOME.get(n) in MOVED]
    assert found == []


def test_the_guard_sees_the_setattr_and_code_string_forms():
    seen = {m.group(1) for line in ('monkeypatch.setattr(kit.docs, "zz", f)', "monkeypatch.setattr(wired.docs, 'x', f)")
            for m in TEST_READS[2].finditer(line)}
    assert seen == {"zz", "x"}
    assert TEST_READS[2].search('monkeypatch.setattr(kit.services.docs, "zz", f)') is None
    assert TEST_READS[0].search("kit.services.docs.iter_docs()") is None
    assert TEST_READS[0].search('"https://gitlab.example.com/g/docs.git", "team-docs.git", "git@h:a/docs.git"') is None
    assert {m.group(1) for m in TEST_READS[0].finditer("kit.docs.workspace(), docs.split_fm(t), pg.kit.docs.check()")} \
        == {"workspace", "split_fm", "check"}
    assert {m.group(1) for m in CODE_STRING_READ.finditer("from lib import docs\ndocs.collect()\ndocs.llms()")} \
        == {"collect", "llms"}
    assert CODE_STRING_READ.search("services.current().docs.iter_docs()") is None
