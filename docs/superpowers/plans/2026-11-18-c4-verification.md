# C4 backed by the code — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every C4 element and relation names the code that backs it; the kit checks that evidence, reports drift
against the code graph, and hands agents only what the code backs, with the decisions about it.

**Architecture:** Anchors live in the `.c4` files (`metadata { code [...] }`, legacy `evidence` read too). Pure rules
(anchor parsing, states, drift) go in `lib/domain/c4/`; element states and stamps extend `harness/freshness.py`
(`fresh.json` key `c4`); the drift report and relation states are a use case (`lib/app/c4_verify.py`) reading graphify
through `services.code` and `quickarch.scan` through a new `services.arch_scan` port; agents read through
`lib/app/c4_lookup.py` (prompt hook, MCP tool `architecture`, pre-edit stop).

**Tech Stack:** Python 3.10+ (uv inline script), pytest (`-n auto`), LikeC4 1.59.4 DSL, graphify graph JSON.

**Spec:** `docs/superpowers/specs/2026-11-18-c4-verification-design.md` (read it with this plan; section numbers
below are the spec's).

## Global Constraints

- macOS, Windows and Linux: `pathlib` only, anchors and globs matched on repo-relative **posix** paths
  (`relative_to(...).as_posix()`), `encoding="utf-8"` on every read and write, LF (`newline="\n"`) on writes.
- TDD: the failing test first. Tests offline and deterministic (`kit`/`wired` fixtures, `make_workspace`); a test that
  needs LikeC4 uses `needs("likec4")`. Suite: `uv run pytest -n auto` from the repo root.
- No model call anywhere in this plan (AGENTS.md §1).
- Layers (`tests/test_architecture.py`): `lib/domain/c4/*` imports only `core` and `domain`; `lib/app/*` never imports
  an adapter (`quickarch`, `adapters.*`, `harness.symbols`): it goes through `services`. `allowlist.yaml` only shrinks;
  `largest_cycle` and `cycle_modules` must not grow.
- The kit never writes a `.c4` file on its own: only the C4 editor on a person's action and `arch-draft --save` (both
  exist today). `arch-verify` and `check` only read the model; states live in `docs/.work/fresh.json`.
- `fresh.json`: keep `{"v": 1, "pages": {...}}` as is; add the top-level key `c4`. Every write holds
  `freshness.LOCK`.
- Legacy `metadata { evidence '…' }` is read, never rewritten.
- Prompt hook: `prompt_context.CAP = 6000` characters, under ~1 s; the drift report is never computed per prompt.
- State names, exactly: `fresh`, `suspect`, `broken`, `no-evidence`, `unchecked`.
- `check`: C4 findings are warnings; `check --strict` makes them errors, except `unchecked`, which stays a warning.
- `VERSIONS["kit"]` in `.camarones/lib/common.py`: 4.88.0 → 4.89.0 (next minor if `main` moved), with the README
  badge, in the last task.
- User docs move with the code (AGENTS.md §5.1): README in Spanish; guides in `en` and `es`; tutorial regenerated.
- Conventional commits, no `Co-Authored-By: Claude` and no "Generated with" line; stage only your own hunks.

## Review Focus

1. **Windows paths.** A folder or glob anchor must match a file found through `pathlib` on Windows the same as on
   POSIX → test in Task 3 (`test_folder_and_glob_anchors_match_posix_paths`).
2. **A model that does not parse.** A `.c4` that `c4edit.index()` cannot read must not crash the prompt hook, the
   MCP or `check`; states come back empty with an error and `check` warns once → test in Task 3
   (`test_a_model_that_does_not_parse_leaves_no_states_and_one_error`).
3. **A renamed element.** Its old stamp is dropped and the new FQN is stamped fresh; pages citing the old FQN go stale
   as today → test in Task 3 (`test_a_renamed_element_is_stamped_again`).
4. **Two identical relations.** Same `from`, `to` and label in two files must not share one stamp → test in Task 3
   (`test_duplicate_relations_get_their_own_keys`).
5. **Graph nodes with no file.** Imports of external modules (nodes without `source_file`) and edges to them are
   skipped, never mapped to an element → test in Task 6 (`test_external_nodes_never_become_relations`).

---

### Task 1: The C4 editor reads and keeps list metadata and relation metadata

**Files:**
- Modify: `.camarones/lib/c4edit.py` (`META_PAIR`, `_details`, `_set_meta`, `quote`, `_parse_file`)
- Test: `tests/test_c4_edit.py`

**Interfaces:**
- Produces: `index()["elements"][fqn]["metadata"]` values are `str | list[str]`; each `index()["relations"][i]`
  gains `"metadata": dict[str, str | list[str]]` and `"tags": list[str]`, read from the relation's own block.

- [ ] **Step 1: Write the failing tests**

```python
LISTED = MODEL.replace("      metadata { repo 'orders' }",
                       "      metadata {\n        repo 'orders'\n        code ['orders:src/A.java', 'orders:src/b/']\n      }")

def test_list_metadata_is_read_and_kept_on_confirm(arch):
    from lib import c4edit
    (arch / "model.c4").write_text(LISTED, encoding="utf-8", newline="\n")
    assert c4edit.index()["elements"]["shop.orders"]["metadata"]["code"] == ["orders:src/A.java", "orders:src/b/"]
    c4edit.confirm(["shop.orders"], by="ana", today="2026-11-18")
    meta = c4edit.index()["elements"]["shop.orders"]["metadata"]
    assert meta["code"] == ["orders:src/A.java", "orders:src/b/"] and meta["confirmed-by"] == "ana"

def test_relation_metadata_and_tags_are_read(arch):
    from lib import c4edit
    text = MODEL.replace("      -> billing 'charges'\n",
                         "      -> billing 'charges' {\n        #confirmed\n        metadata { code 'orders:src/Pay.java#L3' }\n      }\n")
    (arch / "model.c4").write_text(text, encoding="utf-8", newline="\n")
    rel = next(r for r in c4edit.index()["relations"] if r["to"] == "shop.billing")
    assert rel["metadata"] == {"code": "orders:src/Pay.java#L3"} and rel["tags"] == ["confirmed"]
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/test_c4_edit.py -k "list_metadata or relation_metadata" -v`
Expected: FAIL (`KeyError: 'code'`; relations have no `metadata`).

- [ ] **Step 3: Implement**

`META_PAIR` also matches `NAME '[' STR (',' STR)* ']'` (a list value; a trailing comma allowed); `_details` keeps the
list as `list[str]`. `_set_meta` writes a list as `key ['a', 'b']` (each item through `quote`), on one line. In
`_parse_file`, when a relation line opens a block, read the tags and the `metadata { … }` pairs between its `start`
and `end` with the same helpers. No other behaviour changes.

- [ ] **Step 4: Run the file and the LikeC4 check**

Run: `uv run pytest tests/test_c4_edit.py -v` → all PASS (the LikeC4 round-trip test runs where `likec4` is
installed: `CAMARONES_TEST_HOST_TOOLS=1 uv run pytest tests/test_c4_edit.py -k valid_for_likec4`).

- [ ] **Step 5: Commit** — `fix(c4edit): keep list metadata and read relation metadata` (body: no user-visible change
  besides confirm no longer dropping a list value).

---

### Task 2: Anchors and states as pure rules

**Files:**
- Create: `.camarones/lib/domain/c4/__init__.py` (empty docstring module)
- Create: `.camarones/lib/domain/c4/anchors.py`
- Create: `.camarones/lib/domain/c4/verdict.py`
- Test: `tests/test_c4_anchors.py`

**Interfaces:**
- Produces (`anchors.py`):
  - `@dataclass(frozen=True) class Anchor: repo: str; path: str; anchor: str; kind: str; legacy: bool; raw: str` —
    `kind` ∈ `"repo" | "file" | "folder" | "glob" | "lines" | "symbol"`; `path` posix, no leading `/`; `anchor` is
    the text after `#` (`L3-L9`, `Class.method`) or `""`.
  - `parse_code(value: str | list[str]) -> tuple[list[Anchor], list[str]]` — anchors, and the raw entries that
    cannot be read (no `repo:`, empty path, absolute path, `..`).
  - `parse_legacy(text: str, default_repo: str | None) -> tuple[list[Anchor], list[str]]` — comma-separated; an
    entry without `repo:` takes the previous entry's repo, the first takes `default_repo`.
  - `container_repo(fqn: str, elements: dict) -> str | None` — the `metadata.repo` of the nearest ancestor (or the
    element itself) that has one.
  - `of_element(fqn: str, elements: dict) -> tuple[list[Anchor], list[str]]` — `code` + legacy `evidence` + the
    element's own `metadata.repo` as a `kind="repo"` anchor.
  - `covers(a: Anchor, repo: str, path: str) -> bool`; `specificity(a: Anchor) -> int` (lines/symbol 3, file 2,
    folder/glob 1, repo 0).
- Produces (`verdict.py`):
  - `STATES = ("fresh", "suspect", "broken", "no-evidence", "unchecked")`
  - `combine(results: list[str]) -> str` — `results` are per-anchor `"fresh" | "changed" | "missing" | "unchecked"`;
    empty → `no-evidence`; any `missing` → `broken`; any `changed` → `suspect`; all `unchecked` → `unchecked`;
    otherwise `fresh`.
  - `serve(state: str, confirmed: bool, policy: str = "block") -> tuple[bool, str | None]` — the table of spec §5.2;
    `policy == "warn"` serves `broken` and `no-evidence` too, with the notice (as `freshness.gate` does for pages).

- [ ] **Step 1: Write the failing tests**

```python
from lib.domain.c4 import anchors, verdict

def test_code_entries_name_their_repo_and_kind():
    got, bad = anchors.parse_code(["api:src/A.java", "api:src/A.java#L3-L9", "api:src/A.java#A.run",
                                   "api:src/web/", "api:src/*/*Route.java", "src/B.java", "api:../x"])
    assert [(a.repo, a.path, a.kind) for a in got] == [
        ("api", "src/A.java", "file"), ("api", "src/A.java", "lines"), ("api", "src/A.java", "symbol"),
        ("api", "src/web", "folder"), ("api", "src/*/*Route.java", "glob")]
    assert bad == ["src/B.java", "api:../x"]

def test_legacy_evidence_inherits_the_repo():
    got, bad = anchors.parse_legacy("gw:pom.xml#L322-L404, src/main/java/config/C.java", None)
    assert [(a.repo, a.path, a.legacy) for a in got] == [("gw", "pom.xml", True), ("gw", "src/main/java/config/C.java", True)]
    got, bad = anchors.parse_legacy("src/main/java/demo/Api.java", "api")
    assert got[0].repo == "api" and bad == []
    assert anchors.parse_legacy("src/X.java", None) == ([], ["src/X.java"])

def test_an_element_takes_its_container_repo():
    els = {"s.gw": {"metadata": {"repo": "gw"}}, "s.gw.api": {"metadata": {"evidence": "src/Api.java"}}}
    got, _ = anchors.of_element("s.gw.api", els)
    assert [(a.repo, a.path) for a in got] == [("gw", "src/Api.java")]
    assert [a.kind for a in anchors.of_element("s.gw", els)[0]] == ["repo"]

def test_cover_and_specificity():
    folder, = anchors.parse_code("api:src/web/")[0]
    glob, = anchors.parse_code("api:src/*/*Route.java")[0]
    assert anchors.covers(folder, "api", "src/web/x/Y.java") and not anchors.covers(folder, "web", "src/web/Y.java")
    assert anchors.covers(glob, "api", "src/geo/GeoRoute.java")
    assert anchors.specificity(folder) < anchors.specificity(anchors.parse_code("api:src/A.java")[0][0])

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
```

- [ ] **Step 2: Run to verify they fail** — `uv run pytest tests/test_c4_anchors.py -v` → FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Implement both modules** with `PurePosixPath` and `fnmatch.fnmatchcase` on posix paths; a path with
  `*`, `?` or `[` is a glob, one ending in `/` a folder, `#L…` lines, any other `#…` a symbol.

- [ ] **Step 4: Run** — `uv run pytest tests/test_c4_anchors.py tests/test_architecture.py -v` → PASS (the new
  package is under `domain.*`).

- [ ] **Step 5: Commit** — `feat(c4): anchors and evidence states as pure rules`

---

### Task 3: Element and relation evidence in freshness

**Files:**
- Modify: `.camarones/lib/harness/freshness.py`
- Test: `tests/test_c4_evidence.py` (new); update `tests/test_freshness_layers.py` (`C4` constant)

**Interfaces:**
- Consumes: `c4edit.index()` (Task 1), `domain.c4.anchors`, `domain.c4.verdict` (Task 2).
- Produces:
  - `c4_states() -> dict` → `{"elements": {fqn: {"state", "confirmed": bool, "anchors": [{"raw", "kind",
    "legacy", "result"}], "unreadable": [str], "legacy_only": bool, "file": str, "line": int}}, "relations":
    {key: {"from", "to", "label", "anchors": [...], "own": state-or-None, "confirmed": bool, "file", "line"}},
    "error": str | None}`. `own` is `combine()` of the relation's own anchors, `None` when it has none.
  - `relation_key(rel: dict, seen: collections.Counter) -> str` → `"from -> to 'label'"`, then `" [2]"`, `" [3]"`
    for repeats in index order.
  - `c4_stamp_all() -> int`; `c4_ack(fqns: list[str], by: str) -> list[str]`.
  - `fresh.json["c4"] = {"elements": {fqn: {"sha", "at", "by"?, "anchors": {raw: stamp}}}, "relations": {key: …}}`.
  - Element text fingerprint v2: `{"h", "n", "k": "c4", "v": 2}` over the element's `c4edit.index()` line range
    without tag lines and `metadata { … }` blocks (its own and its children's).

- [ ] **Step 1: Write the failing tests** (in `tests/test_c4_evidence.py`). Fixture `c4(kit)`: writes `MODEL` as
  `model.c4` and `FRAGMENT` as `repos/api.c4` into `kit.services.diagrams.arch_dir()` and returns
  `importlib.import_module("lib.harness.freshness")`. Helpers: `page(kit, rel, sources)` as in
  `test_freshness_layers.py`; `edit(kit, repo, rel, old, new)` replaces text in a repo file. `Api.java` in
  `make_workspace` is `package demo; / public class Api { / // calls worker over HTTP / }`; comment-only lines are not
  fingerprinted, so a change must touch code.

```python
MODEL = """model {
  shop = system 'Shop' {
    api = service 'Api' {
      metadata { repo 'api' }
    }
    db = database 'Orders DB'
    ghost = service 'Ghost' { #confirmed }
  }
}
"""
FRAGMENT = """model {
  extend shop.api {
    orders = component 'Orders' {
      metadata { code ['api:src/main/java/demo/Api.java', 'api:src/main/java/demo/Api.java#Api'] }
    }
    legacy = component 'Legacy' {
      metadata { evidence 'src/main/java/demo/Api.java, src/gone/' }
    }
    orders -> legacy 'reads'
    orders -> legacy 'reads'
  }
}
"""

def test_each_element_gets_its_state(c4):
    st = c4.c4_states()["elements"]
    assert st["shop.api"]["state"] == "fresh"                       # its repo
    assert st["shop.api.orders"]["state"] == "fresh"
    assert st["shop.api.legacy"]["state"] == "broken"               # src/gone/ matches nothing
    assert st["shop.db"]["state"] == "no-evidence"
    assert st["shop.ghost"]["state"] == "no-evidence" and st["shop.ghost"]["confirmed"] is True
    assert st["shop.api.legacy"]["legacy_only"] is True

def test_a_symbol_anchor_goes_suspect_a_file_anchor_does_not(c4, kit):
    c4.c4_stamp_all()
    edit(kit, "api", "src/main/java/demo/Api.java", "    // calls worker over HTTP", "    void call() { }")
    assert c4.c4_states()["elements"]["shop.api.orders"]["state"] == "suspect"
    c4.c4_ack(["shop.api.orders"], by="ana")
    assert c4.c4_states()["elements"]["shop.api.orders"]["state"] == "fresh"

def test_confirming_in_the_editor_stamps_again(c4, kit):
    c4.c4_stamp_all()
    edit(kit, "api", "src/main/java/demo/Api.java", "    // calls worker over HTTP", "    void call() { }")
    importlib.import_module("lib.c4edit").confirm(["shop.api.orders"], by="ana", today="2026-11-18")
    assert c4.c4_states()["elements"]["shop.api.orders"]["state"] == "fresh"   # its block changed: stamped again

def test_a_repo_not_cloned_here_is_unchecked(c4, kit):
    shutil.rmtree(kit.ws / "api")
    assert c4.c4_states()["elements"]["shop.api.orders"]["state"] == "unchecked"

def test_a_repo_not_in_the_workspace_is_broken(c4, kit): ...   # anchor `nope:src/A.java` → "broken"

def test_duplicate_relations_get_their_own_keys(c4):
    keys = sorted(c4.c4_states()["relations"])
    assert keys == ["shop.api.orders -> shop.api.legacy 'reads'", "shop.api.orders -> shop.api.legacy 'reads' [2]"]

def test_a_renamed_element_is_stamped_again(c4, kit): ...      # rename orders → checkout: old key gone, new "fresh"
def test_folder_and_glob_anchors_match_posix_paths(c4, kit): ...  # `api:src/main/` and `api:src/*/java/demo/*.java` → "fresh"
def test_a_model_that_does_not_parse_leaves_no_states_and_one_error(c4, monkeypatch):
    monkeypatch.setattr(importlib.import_module("lib.c4edit"), "index", lambda *a, **k: 1 / 0)
    st = c4.c4_states()
    assert st["elements"] == {} and st["relations"] == {} and st["error"]

def test_pages_follow_their_element(c4, kit):                   # spec §5.4
    page(kit, "flows/a.md", ["c4:shop.db"])                     # no evidence, not confirmed → suspect
    page(kit, "flows/b.md", ["c4:shop.ghost"])                  # vouched for by a person → fresh
    page(kit, "flows/c.md", ["c4:shop.api.orders"])
    c4.stamp_all()
    assert [c4.status(p)["state"] for p in ("flows/a.md", "flows/b.md", "flows/c.md")] == ["suspect", "fresh", "fresh"]

def test_adding_anchors_or_confirming_leaves_citing_pages_fresh(c4, kit): ...  # add `code` + `#confirmed` → "fresh"
def test_decisions_check_elements_for_existence_only(c4, kit): ...  # `type: decision` citing c4:shop.db → "fresh"

def test_stamps_from_the_current_kit_migrate(c4, kit):
    """A fresh.json written before v2 (no "v" in a c4 stamp): unchanged elements are re-stamped silently, once."""
    ...  # build the v1 stamp with the old `_c4_lines` hash, run states() twice → "fresh", stamp now has "v": 2
```

  In `tests/test_freshness_layers.py`, give the `C4` constant's `orders` element evidence
  (`metadata { code 'api:src/main/java/demo/OrderService.java' }`) so its page stays fresh under the new L3 rule.

- [ ] **Step 2: Run to verify they fail** — `uv run pytest tests/test_c4_evidence.py -v` → FAIL (`AttributeError:
  c4_states`).

- [ ] **Step 3: Implement in `freshness.py`**
  - Per anchor result: `repo` not in `workspace.yaml` → `missing`; repo listed but its folder absent → `unchecked`;
    file / folder (has a file) / glob (first match, then stop) exist → `fresh`, else `missing`; lines and symbol →
    the existing `check_source(ref, stamp)` (`changed` → suspect).
  - An element or relation whose full block sha changed since its stamp is stamped again (as `stamp_all` does for a
    page whose body changed); a stamp whose FQN or key is gone is dropped.
  - `kind(ref) == "c4"` fingerprints with v2; `stamp_all` first migrates c4 stamps without `"v"`: re-stamp when the
    v1 hash (today's `_c4_lines`) still matches, keep it otherwise. Idempotent.
  - `states()`: for a page that `adr_doc.is_decision(logical, fm.get("type"))`, a `c4:` source is `fresh` if
    `c4_exists` else `missing`; for other pages, a `c4:` source is also `changed` when the element is `broken`, or
    `no-evidence` and not confirmed.
  - `c4_exists` reads `c4edit.index()` (fragments and `extend` included).
  - Keep `freshness.py` under 600 lines; if it goes over, move the C4 part to `harness/c4_fresh.py` (layer `app` in
    `tests/architecture/layers.yaml`) and leave nothing behind but the calls.

- [ ] **Step 4: Run the suite** — `uv run pytest -n auto`. Fixtures of other tests that cite an element with no
  evidence (`test_source_links.py`, `test_check_sources.py`, `test_adr_candidates.py`) get evidence on that element;
  never weaken the rule to make a test pass. Expected: all PASS.

- [ ] **Step 5: Commit** — `feat(freshness): C4 elements and relations checked against their code`

---

### Task 4: `camaron arch-verify` and `check` findings

**Files:**
- Create: `.camarones/lib/app/c4_verify.py`
- Modify: `.camarones/lib/interfaces/cli/commands/check.py` (new `ArchVerify` beside `ArchValidate`),
  `.camarones/lib/interfaces/cli/registry.py` (`ORDER`: `"arch-verify"` right after `"arch-validate"`),
  `.camarones/lib/interfaces/cli/help_text.py`, `.camarones/lib/app/doc_status.py` (`check`),
  `tests/snapshots/cli.json` (regenerated)
- Docs: `.camarones/lib/tutorial.py` + `.camarones/TUTORIAL.md`, `.camarones/templates/docs/guides/tutorial.md` and
  `templates/docs/i18n/es/guides/tutorial.md` (command list and the `check` table: "C4 evidence — warning, ERROR with
  `--strict`")
- Test: `tests/test_c4_verify.py`

**Interfaces:**
- Consumes: `freshness.c4_states()`, `c4_ack()` (Task 3); `verdict.serve` (Task 2).
- Produces: `c4_verify.report() -> dict` → `{"elements": …as c4_states, "relations": {key: {"state", "backing":
  [str]}}, "repos": {}, "containers": {}, "error"}` (Task 6 fills `repos`, `containers` and relation backing; here a
  relation's state is its `own` state, or `no-evidence` when it has no anchor);
  `c4_verify.findings(strict: bool) -> tuple[list[str], list[str]]` (errors, warnings), one line per item:
  `"<file>:<line>: C4 <fqn or key>: <state> — <what is missing or changed>"`, plus one line per unreadable legacy
  entry, one summary line for `unchecked` items (always a warning) and, when `report()["error"]` is set, one warning
  `"C4 model could not be read: <error>"` (never an error: `arch-validate` owns syntax).
- CLI: `camaron arch-verify [--json] [--ack FQN …] [--by NAME]`; `@command("arch-verify", "app", "check",
  es="Comprobar el C4 contra el código", en="Check the C4 against the code")`; `--ack` needs `--by`; exit 0 (it
  reports, `check` gates).

- [ ] **Step 1: Write the failing tests**

```python
def test_check_warns_and_strict_fails(verify_world):
    kit, _ = verify_world                                 # the Task 3 model: shop.db has no evidence
    errors, warns = kit.services.doc_status.check()
    assert any("C4 shop.db: no-evidence" in w for w in warns) and not any("C4 " in e for e in errors)
    errors, _ = kit.services.doc_status.check(strict=True)
    assert any("C4 shop.db: no-evidence" in e for e in errors)

def test_unchecked_never_fails(verify_world): ...          # api removed → summary warning, no error under strict
def test_a_confirmed_element_without_evidence_is_not_a_finding(verify_world): ...  # shop.ghost absent from both lists
def test_arch_verify_json_and_ack(verify_world):
    r = cli(kit, "arch-verify", "--json"); data = json.loads(r.stdout)
    assert r.returncode == 0 and data["elements"]["shop.db"]["state"] == "no-evidence"
    assert cli(kit, "arch-verify", "--ack", "shop.api.orders", "--by", "ana").returncode == 0
def test_no_model_no_findings(kit): ...                    # no architecture folder → ([], [])
def test_a_model_that_does_not_parse_warns_once(verify_world, monkeypatch): ...  # c4edit.index raises → one "C4 model could not be read" warning, no error
```

- [ ] **Step 2: Run to verify they fail** — `uv run pytest tests/test_c4_verify.py -v` → FAIL.
- [ ] **Step 3: Implement** `c4_verify.report`, `findings`, the command (text: one block per state, worst first,
  then the legacy-only elements with "turn into `code`"), the `check` hook (`doc_status.check` adds
  `c4_verify.findings(strict)`), the help line `arch-verify [--json] [--ack FQN.. --by NAME]   check the C4 against
  the code: evidence, drift, coverage`, and the docs listed above.
- [ ] **Step 4: Regenerate and run** — `CAMARONES_UPDATE_SNAPSHOTS=1 uv run pytest tests/test_cli_snapshot.py`
  (review the diff: only `arch-verify` added), regenerate `TUTORIAL.md` (AGENTS.md §5.1 command), then
  `uv run pytest -n auto` → PASS (`test_catalog.py`, `test_guide.py`, `test_wizard.py` included).
- [ ] **Step 5: Commit** — `feat(c4): arch-verify and C4 evidence in check`

---

### Task 5: `arch-draft` writes evidence

**Files:**
- Modify: `.camarones/lib/quickarch.py` (`scan`, `render_c4`)
- Create: `.camarones/lib/ports/arch_scanner.py`
- Modify: `.camarones/lib/app/services.py` (field `arch_scan: ArchScanner`), `.camarones/lib/bootstrap.py`
  (`"arch_scan": _arch_scan` → `quickarch`)
- Test: `tests/test_archscan.py` (extend), `tests/test_env_split.py` (if it lists ports or fields)

**Interfaces:**
- Produces: `scan()` keeps its keys and adds `"evidence": {node: [ "repo:path#Ln", … ]}` (node = a db key, a broker
  or identity-provider label) and `"edge_evidence": {(from, to, label): "repo:path#Ln"}` — the line of the match
  (`blob.count("\n", header, at)` from the `### <path>` header). `render_c4` writes `metadata { code [...] }` (up to 3,
  sorted) on every element it has evidence for and a `{ metadata { code '…' } }` block on every relation it has an
  edge source for. `ArchScanner(Protocol): def scan(self) -> dict: ...`.

- [ ] **Step 1: Failing test** — on `make_workspace` (`Api.java` says "calls worker over HTTP"):
  `files = quickarch.render_c4(quickarch.scan(), "demo")` → the relation `api -> worker` carries
  `code 'api:src/main/java/demo/Api.java#L4'`; with LikeC4 installed the saved draft is `✓ Valid`.
- [ ] **Step 2: Run** — `uv run pytest tests/test_archscan.py -v` → FAIL.
- [ ] **Step 3: Implement** the scan additions, `render_c4`, the port, the field and the provider.
- [ ] **Step 4: Run** — `uv run pytest tests/test_archscan.py tests/test_env_split.py tests/test_architecture.py -v`
  → PASS; a draft saved with `arch-draft --save` and checked with `arch-verify` shows no `no-evidence` on the repos
  and datastores it found.
- [ ] **Step 5: Commit** — `feat(arch-draft): the first-look C4 carries its evidence` (body: projects get it on their
  next `arch-draft --save`; existing models are not rewritten).

---

### Task 6: Drift report and relation backing

**Files:**
- Create: `.camarones/lib/domain/c4/drift.py`
- Modify: `.camarones/lib/app/c4_verify.py` (`report` fills `repos`, `containers`, relation backing)
- Docs: `templates/docs/guides/using.md` + `templates/docs/i18n/es/guides/using.md` (what `arch-verify` reports)
- Test: `tests/test_c4_drift.py` (pure), `tests/test_c4_verify.py` (extend)

**Interfaces:**
- Consumes: `anchors.covers`, `anchors.specificity` (Task 2); `services.code.repo_graph(name)`;
  `services.arch_scan.scan()` (Task 5); `freshness.c4_states()` (Task 3).
- Produces (`drift.py`, pure):
  - `STRUCTURAL = ("imports", "imports_from", "calls", "references", "extends", "inherits", "dynamic_import")`
  - `map_files(files: list[str], anchors_by_fqn: dict[str, list[Anchor]], repo: str) -> tuple[dict[str, str],
    list[dict]]` — file → most specific covering element; overlaps `{"file", "elements"}` for ties between siblings.
  - `derive(graph: dict, file_of: dict[str, str]) -> dict[tuple[str, str], dict]` — `(A, B)` → `{"count", "example":
    "path:Lnn", "relations": [str]}`, from `graph["links"]` whose `relation` is in `STRUCTURAL` and whose two nodes'
    `source_file` map to different elements.
  - `covered_by(pair: tuple[str, str], drawn: set[tuple[str, str]]) -> bool` — a drawn relation between the pair or
    their ancestors (FQN prefixes) covers it.
  - `coverage(files: list[str], file_of: dict[str, str]) -> list[dict]` — `{"folder", "files": int}` groups of
    uncovered files, folder = parent directory, largest first.
- `report()["repos"][repo] = {"graph": "ok" | "missing" | "stale", "in_code_not_model": [{"from", "to", "count",
  "example"}], "overlaps": [...], "coverage": [...]}` — only for repos with a components file (elements nested under a
  container whose `metadata.repo` is that repo). `report()["containers"] = {"in_code_not_model": [...],
  "not_compared": [...]}`. Relation state: own anchors when present (`own`); else `fresh` when a derived edge, a
  `quickarch` edge or (for components of two repos) a container edge backs it; `unchecked` when the repo's graph is
  missing; else `no-evidence`. Code files: graph nodes with `file_type == "code"`, filtered with `NOT_SOURCE` and
  `TEST_FILE`, which move from `prompt_context.py` into `domain/c4/drift.py` (`prompt_context` imports them from
  there under the same names): `c4_verify` importing `prompt_context` would close the cycle `prompt_context →
  c4_lookup → c4_verify → prompt_context` once Task 7 lands.
- `findings()` adds one warning per `in_code_not_model` item and per relation `no-evidence` or `broken` (errors under
  `--strict`), and one warning per repo whose graph is missing or stale (never an error).

- [ ] **Step 1: Failing tests** (pure, in `tests/test_c4_drift.py`):

```python
def test_imports_between_components_become_relations():
    file_of = {"src/geo/GeoRoute.java": "gw.geo", "src/err/ExceptionRoute.java": "gw.err"}
    graph = {"nodes": [{"id": "a", "source_file": "src/geo/GeoRoute.java"}, {"id": "b", "source_file": "src/err/ExceptionRoute.java"}],
             "links": [{"source": "a", "target": "b", "relation": "extends", "source_location": "L5"}]}
    got = drift.derive(graph, file_of)
    assert got[("gw.geo", "gw.err")]["count"] == 1 and got[("gw.geo", "gw.err")]["example"] == "src/geo/GeoRoute.java:L5"

def test_external_nodes_never_become_relations():
    graph = {"nodes": [{"id": "a", "source_file": "src/geo/GeoRoute.java"}, {"id": "x", "label": "java.util"}],
             "links": [{"source": "a", "target": "x", "relation": "imports"}]}
    assert drift.derive(graph, {"src/geo/GeoRoute.java": "gw.geo"}) == {}

def test_a_relation_drawn_between_parents_covers_the_children():
    assert drift.covered_by(("s.gw.geo", "s.cs.client"), {("s.gw", "s.cs")})

def test_the_most_specific_anchor_wins_and_ties_are_overlaps(): ...
def test_uncovered_files_group_by_folder(): ...
```

  And in `tests/test_c4_verify.py`: with a written graph for `api`, an undrawn import is in
  `report()["repos"]["api"]["in_code_not_model"]`; a drawn relation without anchor or derived edge is `no-evidence`;
  with the graph file removed it is `unchecked` and `findings(strict=True)` has no error for it; a relation anchored
  to a line (`code 'api:src/main/java/demo/Api.java#L4'`) is backed with no graph at all.
- [ ] **Step 2: Run** — `uv run pytest tests/test_c4_drift.py tests/test_c4_verify.py -v` → FAIL.
- [ ] **Step 3: Implement** `drift.py` and the `report` additions; `arch-verify` text prints the drift sections and
  the coverage groups as "candidate components".
- [ ] **Step 4: Run** — `uv run pytest -n auto` → PASS.
- [ ] **Step 5: Commit** — `feat(c4): drift report against the code graph and the arch-draft scan`

---

### Task 7: Agents get the C4 with its evidence

**Files:**
- Create: `.camarones/lib/app/c4_lookup.py`
- Modify: `.camarones/lib/app/prompt_context.py` (`_c4`, `_render`, `build`), `.camarones/lib/mcp.py` (`TOOLS`,
  `HANDLERS`, new `architecture`), `.camarones/lib/app/retrieval_hooks.py` (`pre_edit` message)
- Docs: `templates/docs/guides/internals.md` + es twin (MCP tool list), `templates/AGENTS.md` (the `architecture`
  tool; evidence and states live there, not in the `likec4` MCP)
- Test: `tests/test_c4_lookup.py` (new); update `tests/test_prompt_context.py` (`MODEL`: `evidence
  'api:src/main/java/demo/Api.java'`)

**Interfaces:**
- Consumes: `c4_verify.report()` (Tasks 4, 6), `verdict.serve`, `anchors.covers`, `freshness.policy()`.
- Produces:
  - `c4_lookup.covering(repo: str, rel: str) -> list[str]` — FQNs whose anchors cover the file, most specific first.
  - `c4_lookup.decisions_about(fqn: str, limit: int = 2) -> list[dict]` — `{"path", "title", "status"}` for decision
    pages (`adr_doc.is_decision`) citing `c4:<fqn>` or an ancestor, then those whose code sources fall under the
    element's anchors; accepted first.
  - `c4_lookup.lookup(target: str) -> dict` — `target` is a FQN or `repo:path`; `{"target", "elements": [{"fqn",
    "title", "kind", "description", "state", "served", "notice", "anchors", "relations_in", "relations_out",
    "decisions", "pages"}], "error"}`; a withheld element keeps only `fqn`, `state`, `served`, `notice`.
  - `c4_lookup.render(found: dict) -> str` — the MCP text.
  - MCP tool `{"name": "architecture", "description": "The C4 element behind an element id or a repo:path file: its
    evidence in the code and its state, its relations and the decisions about it. Elements the code does not back
    are withheld.", "inputSchema": {"type": "object", "properties": {"target": {"type": "string"}}, "required":
    ["target"]}}`; handler `architecture(target: str) -> str` records `usage.record("mcp:architecture")`.

- [ ] **Step 1: Failing tests.** Fixture `ctx_world`: the `ctx` fixture of `test_prompt_context.py` plus
  `write_model(wired)` and a decision page `docs/decisions/0001-retries.md` (`type: decision`, `x-sources:
  [c4:shop.payments]`, `## Status` `Accepted (2026-11-18)`). `covering` reads anchors with `anchors.of_element` over
  `c4edit.index()["elements"]`; `decisions_about` imports nothing from `adr` or `adr_pack` (they import `c4_lookup`
  in Task 8).

```python
def test_a_file_named_in_the_prompt_brings_its_element_state_and_decision(ctx_world):
    out = ctx.build("why does Api.java retry payments with backoff")
    assert "shop.payments" in out["c4"] and "fresh" in out["text"] and "decisions/0001-retries.md" in out["text"]

def test_an_element_with_no_evidence_is_withheld_with_a_notice(ctx_world):
    out = ctx.build("change how billing sends invoices")           # shop.billing has no evidence
    assert "shop.billing" not in out["c4"] and "withheld: shop.billing" in out["text"]

def test_the_mcp_tool_answers_for_an_element_and_a_file(ctx_world):
    import lib.mcp as mcp
    assert "evidence" in mcp.architecture("shop.payments")
    assert "shop.payments" in mcp.architecture("api:src/main/java/demo/Api.java")
    assert "withheld" in mcp.architecture("shop.billing")

def test_the_pre_edit_stop_names_the_element(ctx_world): ...   # message holds `architecture("api:src/…/Api.java")` and shop.payments
def test_the_context_stays_under_its_cap_with_decisions(ctx_world): ...  # len(out["text"]) <= prompt_context.CAP
```

- [ ] **Step 2: Run** — `uv run pytest tests/test_c4_lookup.py tests/test_prompt_context.py -v` → FAIL.
- [ ] **Step 3: Implement** `c4_lookup`, then `prompt_context._c4` (match by name as today **and** by files named in
  the prompt through `covering`; serve by `verdict.serve`; one `withheld: <fqn> — <why>` line per held element;
  up to 2 decisions per served element), the MCP tool, the pre-edit lines, and the docs. The hook reads element
  states from `freshness.c4_states()` only (no drift per prompt).
- [ ] **Step 4: Run** — `uv run pytest -n auto` → PASS; time the hook on the `wired` project:
  `uv run python -c` calling `prompt_context.build(...)` 10× stays under 1 s per call.
- [ ] **Step 5: Commit** — `feat(agents): the C4 with its evidence and decisions in the prompt hook and the MCP`

---

### Task 8: Decisions cite the elements they are about

**Files:**
- Modify: `.camarones/lib/adr_doc.py` (`render_new`: `fields["elements"]` → `c4:<fqn>` in `x-sources`),
  `.camarones/lib/adr.py` (where `render_new` is called: `elements` = `c4_lookup.covering` of each touch, unique),
  `.camarones/lib/adr_pack.py` (`_c4`: elements whose anchors cover a touched file, most specific first, instead of
  every element of the repo), `.camarones/templates/skeletons/decision.md` (`x-sources` example with
  `- c4:<element>`), `.camarones/CONVENTIONS.md` (ADR section: cite the elements a decision is about)
- Test: `tests/test_adr_doc.py`, `tests/test_adr_pack.py`, `tests/test_adr.py`

**Interfaces:**
- Consumes: `c4_lookup.covering` (Task 7).
- Produces: `render_new(fields, number)` accepts `fields["elements"]: list[str]`; the ADR's `x-sources` are the
  touches' sources followed by `c4:<fqn>` per element, in order, unique.

- [ ] **Step 1: Failing tests** — `render_new({"title": "T", "touches": ["api:src/A.java"], "elements":
  ["shop.api"]}, "0002")` has `x-sources: [api:src/A.java, c4:shop.api]`; `adr_pack.build({"touches": [ORDER]})["c4"]`
  lists `shop.orders` (covers via `metadata { repo 'api' }`) and not `shop.cart`; an ADR written through `adr.py` for
  a touch under `shop.orders` cites `c4:shop.orders`.
- [ ] **Step 2: Run** — `uv run pytest tests/test_adr_doc.py tests/test_adr_pack.py tests/test_adr.py -v` → FAIL.
- [ ] **Step 3: Implement** the three changes and the two text changes.
- [ ] **Step 4: Run** — `uv run pytest -n auto` → PASS.
- [ ] **Step 5: Commit** — `feat(adr): decisions cite the C4 elements they are about` (body: the skeleton reaches
  existing projects only on a templates refresh; their ADRs are not rewritten).

---

### Task 9: The rules shipped to projects ask for evidence

**Files:**
- Modify: `.camarones/CONVENTIONS.md` §4 (every element and relation an agent writes carries `code`; the anchor
  syntax; legacy `evidence` still read; relations graphify cannot see are anchored to the line of the call; what the
  code cannot show is left for a person to confirm), `.camarones/PLAYBOOK.md` (`repo-brief` step 2 and
  `arch-system`: write `code` anchors; done when `CLI arch-verify` shows no `no-evidence` item the unit wrote; list
  the elements a person must vouch for in the handoff)
- Test: `tests/test_agent_guidance.py` (extend: CONVENTIONS and PLAYBOOK mention `metadata { code` and `arch-verify`)

- [ ] **Step 1: Failing test** — asserts the two texts hold `metadata { code [` and `arch-verify`.
- [ ] **Step 2: Run** — `uv run pytest tests/test_agent_guidance.py -v` → FAIL.
- [ ] **Step 3: Edit** both files (English, the style of the surrounding rules).
- [ ] **Step 4: Run** — `uv run pytest -n auto` → PASS.
- [ ] **Step 5: Commit** — `docs(conventions): agents write code evidence on every C4 element and relation`

---

### Task 10: README core section, guides, version, end-to-end check

**Files:**
- Modify: `README.md` (new section "El C4 respaldado por el código" right after "La IA propone. Tú confirmas.":
  the two principles, an anchor example, the states table and what agents get, `arch-verify`, `check --strict` and how
  CI fails, ADRs citing elements; one line in "Qué es Camarón" point 3; `arch-verify` in "Mapa de comandos"; badge
  `4.89.0`), `.camarones/lib/common.py` (`VERSIONS["kit"] = "4.89.0"`),
  `templates/docs/guides/using.md` + es twin (the day-to-day flow mentions `arch-verify`)
- Test: the existing doc tests

- [ ] **Step 1: Write the README section and the guide lines; bump the version and the badge.**
- [ ] **Step 2: Run** — `uv run pytest -n auto` → PASS (`test_guide.py`, `test_wizard.py`, `test_bump.py`).
- [ ] **Step 3: Sandbox** — `uv run scripts/sandbox.py reset`, then `uv run scripts/sandbox.py cli arch-draft --save`,
  `… cli arch-verify`, `… cli check`, `… cli check --strict`. Expected: the draft's repos and datastores have
  evidence; `check` exits 0 with C4 warnings for what has none; `--strict` exits 1 naming them. Say so with the
  output, or say what failed.
- [ ] **Step 4: Commit** — `docs(readme): the C4 backed by the code is core; kit 4.89.0`
