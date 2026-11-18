"""`camaron arch-verify` and the C4 findings of `check` (spec §5.2, §5.5)."""
from __future__ import annotations

import argparse
import importlib
import json
import os
import subprocess
import sys

import pytest
from test_c4_evidence import API, CODE, COMMENT, FRAGMENT, GHOST, MODEL, edit, element, model


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
    assert cli(kit, "arch-verify", "--ack", "shop.api.orders").returncode != 0


def test_ack_re_stamps_the_element(verify_world):
    kit, _ = verify_world
    fresh = importlib.import_module("lib.harness.freshness")
    fresh.c4_stamp_all()
    edit(kit, "api", API, COMMENT, CODE)
    assert fresh.c4_states()["elements"]["shop.api.orders"]["state"] == "suspect"
    r = cli(kit, "arch-verify", "--ack", "shop.api.orders", "--by", "ana")
    assert r.returncode == 0 and "shop.api.orders" in r.stdout
    assert fresh.c4_states()["elements"]["shop.api.orders"]["state"] == "fresh"


def test_ack_of_an_unknown_name_exits_1(verify_world):
    kit, _ = verify_world
    r = cli(kit, "arch-verify", "--ack", "shop.api.orders", "shop.nope", "--by", "ana")
    assert r.returncode == 1 and "shop.nope" in r.stderr


def test_an_ack_that_cannot_save_exits_1(verify_world, monkeypatch, capsys):
    kit, _ = verify_world
    fresh = importlib.import_module("lib.harness.freshness")
    monkeypatch.setattr(fresh, "c4_ack", lambda *a, **k: (_ for _ in ()).throw(OSError("disk full")))
    registry = importlib.import_module("lib.interfaces.cli.registry")
    cmd = importlib.import_module("lib.interfaces.cli.commands.check").ArchVerify()
    args = argparse.Namespace(json=False, ack=["shop.api.orders"], by="ana")
    assert cmd.run(args, registry.CliContext(argparse.ArgumentParser(), kit.services)) == 1
    assert "disk full" in capsys.readouterr().err


def test_suspect_is_only_ever_a_warning(verify_world):
    kit, v = verify_world
    fresh = importlib.import_module("lib.harness.freshness")
    fresh.c4_stamp_all()
    edit(kit, "api", API, COMMENT, CODE)
    errors, warns = v.findings(True)
    assert any("C4 shop.api.orders: suspect" in w for w in warns)
    assert not any("C4 shop.api.orders:" in e for e in errors)


def test_unreadable_entries_follow_strict(verify_world):
    kit, v = verify_world
    model(kit, MODEL.replace(GHOST, GHOST + element("loose", "src/A.java")))
    errors, warns = v.findings(True)
    assert any("shop.loose: unreadable evidence entry 'src/A.java'" in e for e in errors)
    errors, warns = v.findings(False)
    assert not errors and any("shop.loose: unreadable evidence entry" in w for w in warns)


def test_an_unreadable_line_without_a_file_has_no_prefix(verify_world):
    _, v = verify_world
    assert v._where({}) == ""


def test_arch_verify_text_lists_worst_first(verify_world):
    kit, _ = verify_world
    out = cli(kit, "arch-verify").stdout
    assert out.index("broken (") < out.index("no-evidence (")
    legacy = out[out.index("turn into `code`"):]
    assert "shop.api.legacy" in legacy and "shop.db" not in legacy


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
