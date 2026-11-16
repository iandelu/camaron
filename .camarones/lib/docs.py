"""docs' code moved to lib/domain/docs, lib/adapters and lib/app; tests/test_docs_split.py HOME names each home; this path stays for old imports."""
from __future__ import annotations

from .adapters.git.repos import detect_repos, git, guess_kind, sync_repos
from .adapters.npm_vendor import CDN_RE, vendor, vendor_file
from .adapters.stores.doc_state import STATE_FILE, STATUS_FILE, changes, mark_documented
from .adapters.stores.doc_store import (
    FEEDBACK, add_feedback, find_page, iter_docs, pending_feedback, resolve, translation_file, wiki_dir,
)
from .adapters.stores.workspace import (
    GI_END, GI_START, INTERVIEW_MODES, interview_mode, interview_mode_chosen, repo_names, save_workspace,
    set_interview_mode, set_wiki_repos, wiki_repos, workspace, write_gitignore, ws_file,
)
from .app.doc_review import REVIEW_ORDER, confirm, review_queue
from .app.doc_status import check, collect, doc_status, repo_file_exists, space_of
from .app.llms import SECTIONS, _llms_key, llms, readable
from .app.search import KIT_WORDS, kit_guides, search
from .app.translations import translated
from .core.clock import now
from .domain.docs.directives import DIRECTIVES, RULE_META, _rule, flatten_directives, rules
from .domain.docs.frontmatter import FM_RE, LOOSE_VALUE_RE, body_sha, first_heading, join_fm, parse_fm, split_fm
from .domain.docs.logical_paths import link_target, old_wiki_path, wiki_path
from .domain.docs.page_outline import (
    COMMENT_RE, HEADING_RE, TLDR_RE, heading_text, headings, section_of, section_text, sections, slug, tldr,
)
from .domain.docs.synonyms import IMPLIED, STOPWORDS, TERMS_FILE, expand, search_terms
from .domain.docs.trust_levels import summary, trust_of
from .ports import Log

__facade__ = "lib.domain.docs, lib.adapters and lib.app"
__all__ = [
    "CDN_RE", "COMMENT_RE", "DIRECTIVES", "FEEDBACK", "FM_RE", "GI_END", "GI_START", "HEADING_RE", "IMPLIED",
    "INTERVIEW_MODES", "KIT_WORDS", "LOOSE_VALUE_RE", "Log", "REVIEW_ORDER", "RULE_META", "SECTIONS", "STATE_FILE",
    "STATUS_FILE", "STOPWORDS", "TERMS_FILE", "TLDR_RE", "_llms_key", "_rule", "add_feedback", "body_sha", "changes",
    "check", "collect", "confirm", "detect_repos", "doc_status", "expand", "find_page", "first_heading",
    "flatten_directives", "git", "guess_kind", "heading_text", "headings", "interview_mode", "interview_mode_chosen",
    "iter_docs", "join_fm", "kit_guides", "link_target", "llms", "mark_documented", "now", "old_wiki_path", "parse_fm",
    "pending_feedback", "readable", "repo_file_exists", "repo_names", "resolve", "review_queue", "rules",
    "save_workspace", "search", "search_terms", "section_of", "section_text", "sections", "set_interview_mode",
    "set_wiki_repos", "slug", "space_of", "split_fm", "summary", "sync_repos", "tldr", "translated", "translation_file",
    "trust_of", "vendor", "vendor_file", "wiki_dir", "wiki_path", "wiki_repos", "workspace", "write_gitignore",
    "ws_file",
]
