"""`camaron arch-verify` and the C4 findings of `check` (spec §5.2, §5.5)."""
from __future__ import annotations

import importlib
import json
import os
import subprocess
import sys

import pytest
from test_c4_evidence import FRAGMENT, MODEL, model


def cli(kit, *args):
    e = {**os.environ, "CAMARONES_ROOT": str(kit.root)}
    return subprocess.run([sys.executable, str(kit.kit_dir / "camarones.py"), *args], env=e, capture_output=True,
                          text=True, encoding="utf-8")


@pytest.fixture
def verify_world(kit):
    model(kit, MODEL)
    model(kit, FRAGMENT, "repos/api.c4")
    return kit, importlib.import_module("lib.app.c4_verify")


def test_check_warns_and_strict_fails(verify_world):
    kit, _ = verify_world
    errors, warns = kit.services.doc_status.check()
    assert any("C4 shop.db: no-evidence" in w for w in warns) and not any("C4 " in e for e in errors)
    errors, _ = kit.services.doc_status.check(strict=True)
    assert any("C4 shop.db: no-evidence" in e for e in errors)


def test_findings_name_file_line_and_what_is_wrong(verify_world):
    _, v = verify_world
    _, warns = v.findings(False)
    assert any(w.startswith("repos/api.c4:") and "C4 shop.api.legacy: broken" in w and "src/gone/" in w for w in warns)


def test_unchecked_never_fails(verify_world):
    kit, v = verify_world
    kit.common.rmtree(kit.ws / "api")
    errors, warns = v.findings(True)
    assert not any("unchecked" in e for e in errors)
    assert sum("unchecked" in w for w in warns) == 1


def test_a_confirmed_element_without_evidence_is_not_a_finding(verify_world):
    _, v = verify_world
    errors, warns = v.findings(True)
    assert not any("shop.ghost" in x for x in errors + warns)


def test_a_relation_without_anchor_is_no_evidence(verify_world):
    _, v = verify_world
    rel = v.report()["relations"]
    assert rel and all(r["state"] == "no-evidence" and r["backing"] == [] for r in rel.values())


def test_arch_verify_json_and_ack(verify_world):
    kit, _ = verify_world
    r = cli(kit, "arch-verify", "--json")
    data = json.loads(r.stdout)
    assert r.returncode == 0 and data["elements"]["shop.db"]["state"] == "no-evidence"
    assert data["repos"] == {} and data["containers"] == {}
    assert cli(kit, "arch-verify", "--ack", "shop.api.orders", "--by", "ana").returncode == 0
    assert cli(kit, "arch-verify", "--ack", "shop.api.orders").returncode != 0


def test_arch_verify_text_lists_worst_first(verify_world):
    kit, _ = verify_world
    out = cli(kit, "arch-verify").stdout
    assert out.index("broken") < out.index("no-evidence")
    assert "turn into `code`" in out


def test_no_model_no_findings(kit):
    v = importlib.import_module("lib.app.c4_verify")
    assert v.findings(False) == ([], []) and v.findings(True) == ([], [])


def test_a_model_that_does_not_parse_warns_once(verify_world, monkeypatch):
    kit, v = verify_world
    c4edit = importlib.import_module("lib.c4edit")
    monkeypatch.setattr(c4edit, "index", lambda *a, **k: (_ for _ in ()).throw(ValueError("boom")))
    importlib.import_module("lib.harness.freshness")._parsed.cache_clear()
    errors, warns = v.findings(True)
    assert not errors and sum("C4 model could not be read" in w for w in warns) == 1
