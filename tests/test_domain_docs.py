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


# ---------- page_outline ----------
PAGE = """# Title

> **TL;DR:** short.
> more.

## Data flow
text
```
## not a heading
```
## Data flow
### Detail [link](x.md)
## `Last` *one*
end
"""


def test_heading_text_is_what_a_reader_sees():
    o = mod("page_outline")
    assert o.heading_text("The [API](a.md) `v2` *now* <!-- x -->") == "The API v2 now"
    assert o.slug("Qué es `esto`? (v2)") == "qué-es-esto-v2"


def test_headings_skip_code_and_number_repeated_slugs():
    hs = mod("page_outline").headings(PAGE)
    assert [(h["level"], h["slug"]) for h in hs] == [(1, "title"), (2, "data-flow"), (2, "data-flow-1"),
                                                      (3, "detail-link"), (2, "last-one")]


def test_sections_run_to_the_next_h2_and_name_a_line():
    o = mod("page_outline")
    secs = o.sections(PAGE)
    assert [(s["slug"], s["start"], s["end"]) for s in secs] == [("data-flow", 5, 10), ("data-flow-1", 10, 12),
                                                                 ("last-one", 12, 14)]
    assert o.section_of(PAGE, 11) == "data-flow-1" and o.section_of(PAGE, 0) is None


def test_tldr_and_section_text():
    o = mod("page_outline")
    assert o.tldr(PAGE) == "> **TL;DR:** short.\n> more."
    sec, text = o.section_text(PAGE, "last one")
    assert sec["slug"] == "last-one" and text == "## `Last` *one*\nend"
    assert o.section_text(PAGE, "#data-flow-1")[1].startswith("## Data flow\n### Detail")
    assert o.section_text(PAGE, "missing") is None


def test_comment_re_spans_lines():
    assert mod("page_outline").COMMENT_RE.sub("", "a<!-- one\ntwo -->b") == "ab"


# ---------- directives ----------
RULED = """intro
:::rule R1 Totals add up
The sum is the total.
enforced: api:Order.java#total, web:cart.ts
test: api:OrderTest.java#sums
:::
```
:::rule R2 inside code
:::
```
"""


def test_rules_read_rule_blocks_outside_code():
    assert mod("directives").rules(RULED) == [{"id": "R1", "title": "Totals add up", "text": "The sum is the total.",
                                               "enforced": ["api:Order.java#total", "web:cart.ts"],
                                               "test": ["api:OrderTest.java#sums"]}]


def test_flatten_directives_turns_blocks_into_plain_markdown():
    d = mod("directives")
    md = ":::tabs\n::tab Java\njava code\n::tab Go\ngo code\n:::\n:::details Why\nbecause\n:::\n:::unknown x\nkept\n:::"
    assert d.flatten_directives(md) == ("**Java**\n\njava code\n\n**Go**\n\ngo code\n**Why**\n\nbecause\n"
                                        ":::unknown x\nkept\n:::")
    flat = d.flatten_directives(RULED)
    assert "**Rule R1 — Totals add up**" in flat and "Enforced by: `api:Order.java#total`, `web:cart.ts`" in flat
    assert ":::rule R2 inside code" in flat                  # a fence keeps its content as written


# ---------- synonyms ----------
def test_search_terms_file_is_the_shipped_one():
    """The data file stays in lib/ (spec §2): the moved constant must still name it (plan Q4)."""
    kit = importlib.import_module("lib.core.ctx").KIT
    terms = mod("synonyms").TERMS_FILE
    assert terms == kit / "lib" / "search_terms.yaml" and terms.is_file()


def test_expand_weighs_said_words_over_implied_ones():
    w = mod("synonyms").expand("Where is the cache configured?")
    assert w["cache"] == 1.0 and w["configured"] == 1.0 and "where" not in w and "the" not in w
    assert w["redis"] == mod("synonyms").IMPLIED


def test_a_phrase_key_stands_for_its_words_and_is_followed_once():
    w = mod("synonyms").expand("base de datos")
    assert "base" not in w and "datos" not in w
    assert w["database"] == w["postgresql"] == 0.6


def test_only_stopwords_keep_their_words():
    assert mod("synonyms").expand("the of") == {"the": 1.0, "of": 1.0}
