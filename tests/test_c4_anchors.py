"""lib/domain/c4: the evidence anchors of a C4 element and the states they add up to. Values in, values out."""
from __future__ import annotations

import pytest

from lib.domain.c4 import anchors, verdict


def test_code_entries_name_their_repo_and_kind():
    got, bad = anchors.parse_code(["api:src/A.java", "api:src/A.java#L3-L9", "api:src/A.java#A.run",
                                   "api:src/web/", "api:src/*/*Route.java", "src/B.java", "api:../x"])
    assert [(a.repo, a.path, a.kind) for a in got] == [
        ("api", "src/A.java", "file"), ("api", "src/A.java", "lines"), ("api", "src/A.java", "symbol"),
        ("api", "src/web", "folder"), ("api", "src/*/*Route.java", "glob")]
    assert bad == ["src/B.java", "api:../x"]


def test_code_accepts_a_string_and_skips_blanks_and_unreadable_paths():
    got, bad = anchors.parse_code(" api:src/A.java ")
    assert [(a.repo, a.path) for a in got] == [("api", "src/A.java")] and bad == []
    got, bad = anchors.parse_code(["", "  ", "api:", "api:/etc/passwd"])
    assert got == [] and bad == ["api:", "api:/etc/passwd"]


def test_line_ranges_and_symbols():
    got, _ = anchors.parse_code(["a:f#L3", "a:f#L3-9", "a:f#L3-L9", "a:f#Cls.m"])
    assert [(x.kind, x.anchor) for x in got] == [("lines", "L3"), ("lines", "L3-9"), ("lines", "L3-L9"),
                                                 ("symbol", "Cls.m")]


def test_legacy_evidence_inherits_the_repo():
    got, _ = anchors.parse_legacy("gw:pom.xml#L322-L404, src/main/java/config/C.java", None)
    assert [(a.repo, a.path, a.legacy) for a in got] == [("gw", "pom.xml", True), ("gw", "src/main/java/config/C.java", True)]
    got, bad = anchors.parse_legacy("src/main/java/demo/Api.java", "api")
    assert got[0].repo == "api" and bad == []
    assert anchors.parse_legacy("src/X.java", None) == ([], ["src/X.java"])


def test_an_element_takes_its_container_repo():
    els = {"s.gw": {"metadata": {"repo": "gw"}}, "s.gw.api": {"metadata": {"evidence": "src/Api.java"}}}
    got, _ = anchors.of_element("s.gw.api", els)
    assert [(a.repo, a.path) for a in got] == [("gw", "src/Api.java")]
    assert [a.kind for a in anchors.of_element("s.gw", els)[0]] == ["repo"]
    assert anchors.container_repo("s.gw.api", els) == "gw"
    assert anchors.container_repo("s.other", els) is None


def test_an_element_reads_code_as_a_list():
    els = {"s.a": {"metadata": {"code": ["api:src/A.java", "api:src/web/"], "repo": "api"}}}
    got, bad = anchors.of_element("s.a", els)
    assert [a.kind for a in got] == ["file", "folder", "repo"] and bad == []


def test_cover_and_specificity():
    folder, = anchors.parse_code("api:src/web/")[0]
    glob, = anchors.parse_code("api:src/*/*Route.java")[0]
    assert anchors.covers(folder, "api", "src/web/x/Y.java") and not anchors.covers(folder, "web", "src/web/Y.java")
    assert anchors.covers(glob, "api", "src/geo/GeoRoute.java")
    assert anchors.specificity(folder) < anchors.specificity(anchors.parse_code("api:src/A.java")[0][0])


def test_cover_of_files_lines_and_repos():
    f, ln = anchors.parse_code(["api:src/A.java", "api:src/A.java#L1-L2"])[0]
    assert anchors.covers(f, "api", "src/A.java") and not anchors.covers(f, "api", "src/B.java")
    assert anchors.covers(ln, "api", "src/A.java")
    repo, = anchors.of_element("s", {"s": {"metadata": {"repo": "api"}}})[0]
    assert anchors.covers(repo, "api", "any/path.txt") and not anchors.covers(repo, "web", "any/path.txt")
    assert [anchors.specificity(x) for x in (repo, f, ln)] == [0, 2, 3]


@pytest.mark.parametrize("results, state", [([], "no-evidence"), (["fresh", "missing"], "broken"),
    (["fresh", "changed"], "suspect"), (["unchecked"], "unchecked"), (["fresh", "unchecked"], "fresh")])
def test_combine(results, state):
    assert verdict.combine(results) == state


def test_serve_follows_the_page_rule():
    assert verdict.serve("fresh", False) == (True, None)
    assert verdict.serve("suspect", False)[0] is True
    assert verdict.serve("broken", True)[0] is False
    assert verdict.serve("no-evidence", False)[0] is False and verdict.serve("no-evidence", True)[0] is True
    assert verdict.serve("unchecked", False)[0] is True
    assert verdict.serve("no-evidence", False, policy="warn")[0] is True
    assert verdict.serve("broken", False, policy="warn")[0] is True
    assert verdict.serve("broken", False)[1] and verdict.serve("fresh", True)[1] is None


@pytest.mark.parametrize("policy", ["Block", None, "off", "blokc"])
def test_an_unknown_policy_fails_closed(policy):
    assert verdict.serve("broken", False, policy=policy)[0] is False
    assert verdict.serve("no-evidence", False, policy=policy)[0] is False


def test_an_unknown_state_is_an_error():
    with pytest.raises(ValueError):
        verdict.serve("no_evidence", False)


@pytest.mark.parametrize("text", ["foo/bar:x, a.java", ":x, a.java"])
def test_a_bad_legacy_entry_does_not_poison_the_repo(text):
    got, bad = anchors.parse_legacy(text, "api")
    assert [(a.repo, a.path) for a in got] == [("api", "a.java")] and len(bad) == 1


def test_legacy_repo_switches_and_carries_on():
    got, _ = anchors.parse_legacy("a:x, y, b:z, w", None)
    assert [(a.repo, a.path) for a in got] == [("a", "x"), ("a", "y"), ("b", "z"), ("b", "w")]


def test_backslashes_and_spaces_around_the_hash_are_normalised():
    got, _ = anchors.parse_code(["api:src\\main\\A.java", "api:src/A.java #L3-L9"])
    assert [(a.path, a.kind) for a in got] == [("src/main/A.java", "file"), ("src/A.java", "lines")]


def test_a_code_value_that_is_not_text_is_unreadable():
    assert anchors.parse_code(5) == ([], ["5"])
