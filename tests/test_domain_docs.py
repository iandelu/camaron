"""lib/domain/docs (hexagonal refactor F5a): the docs model's pure rules. Strings and dicts in, values out: no `kit`
fixture, no workspace, no files."""
from __future__ import annotations

import importlib


def mod(name: str):
    return importlib.import_module(f"lib.domain.docs.{name}")


# ---------- frontmatter ----------
def test_parse_fm_reads_front_matter_and_body():
    fm, body, valid = mod("frontmatter").parse_fm("---\ntitle: A\nx-owner: ai\n---\n# A\n")
    assert (fm, body, valid) == ({"title": "A", "x-owner": "ai"}, "# A\n", True)


def test_parse_fm_quotes_an_unquoted_value_with_a_colon():
    fm, _, valid = mod("frontmatter").parse_fm("---\ndescription: Foo: bar\n---\nbody")
    assert valid and fm == {"description": "Foo: bar"}


def test_parse_fm_keeps_unreadable_front_matter_out_of_the_body():
    assert mod("frontmatter").parse_fm("---\n: [\n---\nbody") == ({}, "body", False)


def test_parse_fm_without_front_matter_is_all_body():
    assert mod("frontmatter").parse_fm("# Just a page\n") == ({}, "# Just a page\n", True)


def test_split_and_join_round_trip():
    f = mod("frontmatter")
    text = f.join_fm({"title": "Ünïcode", "x-sources": ["api:pom.xml"]}, "# T\n\nbody\n")
    assert text.startswith("---\ntitle: Ünïcode\n")
    assert f.split_fm(text) == ({"title": "Ünïcode", "x-sources": ["api:pom.xml"]}, "# T\n\nbody\n")


def test_body_sha_ignores_trailing_spaces_and_outer_blank_lines():
    f = mod("frontmatter")
    assert f.body_sha("\n# T  \nline\n\n") == f.body_sha("# T\nline")
    assert f.body_sha("# T\nline") != f.body_sha("# T\nother")
    assert len(f.body_sha("x")) == 16


def test_first_heading_is_the_first_h1():
    f = mod("frontmatter")
    assert f.first_heading("intro\n## Two\n# One \n# Later") == "One"
    assert f.first_heading("no heading") is None


# ---------- trust_levels ----------
def test_trust_follows_the_confirmed_body_hash():
    t = mod("trust_levels")
    assert t.trust_of({}, "abc") == "draft"
    assert t.trust_of({"x-confirmed": {"body_sha": "abc"}}, "abc") == "confirmed"
    assert t.trust_of({"x-confirmed": {"body_sha": "old"}}, "abc") == "needs-reconfirm"


def test_summary_counts_trust_orphans_and_translations():
    rows = [{"trust": "confirmed", "orphan_sources": [], "i18n": {"es": "current"}},
            {"trust": "draft", "orphan_sources": ["api:gone.py"], "i18n": {"es": "missing"}},
            {"trust": "needs-reconfirm", "orphan_sources": [], "i18n": {}}]
    assert mod("trust_levels").summary(rows) == {"confirmed": 1, "needs-reconfirm": 1, "draft": 1, "total": 3,
                                                 "orphans": 1, "untranslated": 1}


# ---------- logical_paths ----------
def test_a_wiki_page_sits_under_wikis():
    assert mod("logical_paths").wiki_path("api", "index.md") == "wikis/api/index.md"


def test_an_old_wiki_path_names_its_wikis_page():
    p = mod("logical_paths")
    assert p.old_wiki_path("repos/api/flows/x.md") == "wikis/api/flows/x.md"
    assert p.old_wiki_path("repos/api") is None
    assert p.old_wiki_path("domain/glossary.md") is None


def test_link_target_prefers_a_known_page():
    p = mod("logical_paths")
    known = {"repos/api/index.md", "wikis/api/index.md", "wikis/api/setup.md", "domain/glossary.md"}
    assert p.link_target("repos/api/index.md", known) == "repos/api/index.md"     # the docs page wins
    assert p.link_target("docs/domain/glossary.md", known) == "domain/glossary.md"
    assert p.link_target("repos/api/setup.md", known) == "wikis/api/setup.md"     # a pre-4.81 wiki path
    assert p.link_target("nowhere.md", known) == "nowhere.md"
