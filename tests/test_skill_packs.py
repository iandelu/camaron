"""Optional skill packs (pinned to a commit, vendored into the team's skills), and turning any skill off for the
project (workspace.yaml) or for this machine (Claude Code deny rules in settings.local.json)."""
import importlib
import json
import os
import subprocess
import sys

import pytest
import yaml

from conftest import KIT_DIR


def packs(kit):
    return importlib.import_module("lib.skills_packs")


def skills(kit):
    return importlib.import_module("lib.skills")


def git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


def source_repo(tmp_path, name="demo-pack"):
    """A local repo standing in for a pack's GitHub repo: two skills under skills/ and a licence at the root."""
    repo = tmp_path / name
    for skill in ("demo", "demo-help"):
        d = repo / "skills" / skill
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text(f"---\nname: {skill}\ndescription: The {skill} skill.\n---\n# {skill}\n",
                                    encoding="utf-8")
    (repo / "skills" / "demo" / "reference.md").write_text("more\n", encoding="utf-8")
    (repo / "LICENSE").write_text("MIT License\n", encoding="utf-8")
    git(repo, "init", "-q")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "pack")
    return repo, git(repo, "rev-parse", "HEAD")


def use_catalog(kit, monkeypatch, tmp_path, source, commit, **extra):
    data = {"icons": {"cam-task": "🧭"},
            "packs": {"demo-pack": {"title": "Demo", "icon": "🧪", "summary": {"en": "A demo", "es": "Una demo"},
                                    "source": str(source), "commit": commit, "path": "skills",
                                    "skills": ["demo", "demo-help"], "license": "MIT", "files": ["LICENSE"],
                                    "runs_code": False, **extra}}}
    f = tmp_path / "catalog.yaml"
    f.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    monkeypatch.setattr(packs(kit), "CATALOG", f)
    return f


def rendered(kit, name, host=".claude"):
    return (kit.root / host / "skills" / name / "SKILL.md").is_file()


# ---------- the kit's catalog ----------

def test_the_kits_catalog_pins_every_pack_and_names_known_skills(kit):
    cat = packs(kit).catalog()
    assert {"ponytail", "impeccable"} <= set(cat["packs"])
    for name, p in cat["packs"].items():
        assert len(p["commit"]) == 40 and p["source"].startswith("https://github.com/"), name
        assert p["skills"] and p["license"] and p["icon"] and p["summary"]["en"] and p["summary"]["es"], name
    assert set(cat["icons"]) <= set(skills(kit).kit_names()) | {"graphify", "openwiki"}
    assert packs(kit).icon("cam-task") == cat["icons"]["cam-task"]


def test_optional_means_nothing_renders_until_a_pack_is_added(wired):
    assert not rendered(wired, "ponytail") and not rendered(wired, "impeccable")
    assert packs(wired).load_lock() == {}


# ---------- adding and removing a pack ----------

def test_add_vendors_the_pack_at_its_commit_and_records_it(wired, monkeypatch, tmp_path):
    repo, sha = source_repo(tmp_path)
    use_catalog(wired, monkeypatch, tmp_path, repo, sha)
    git(repo, "commit", "-q", "--allow-empty", "-m", "newer")          # the pin wins over the repo's tip
    entry = packs(wired).add("demo-pack")
    team = wired.root / ".camarones" / "skills"
    assert (team / "demo" / "SKILL.md").is_file() and (team / "demo" / "reference.md").is_file()
    assert (team / "demo" / "LICENSE").read_text(encoding="utf-8") == "MIT License\n"
    assert (team / "demo-help" / "LICENSE").is_file()
    lock = packs(wired).load_lock()
    assert lock["demo-pack"]["commit"] == sha and lock["demo-pack"]["source"] == str(repo)
    assert set(lock["demo-pack"]["skills"]) == {"demo", "demo-help"} == set(entry["skills"])
    assert skills(wired).origin("demo") == "team-only"
    assert packs(wired).pack_of("demo") == "demo-pack" and packs(wired).icon("demo") == "🧪"


def test_add_refuses_without_writing_anything(wired, monkeypatch, tmp_path):
    repo, sha = source_repo(tmp_path)
    use_catalog(wired, monkeypatch, tmp_path, repo, sha)
    sp = packs(wired)
    with pytest.raises(ValueError, match="no optional skill pack"):
        sp.add("nope")
    use_catalog(wired, monkeypatch, tmp_path, repo, "0" * 40)
    with pytest.raises(ValueError, match="cannot fetch"):
        sp.add("demo-pack")
    use_catalog(wired, monkeypatch, tmp_path, repo, sha)
    clash = wired.root / ".camarones" / "skills" / "demo-help"
    clash.mkdir(parents=True)
    (clash / "SKILL.md").write_text("---\nname: demo-help\ndescription: Ours.\n---\n", encoding="utf-8")
    with pytest.raises(ValueError, match="demo-help"):
        sp.add("demo-pack")
    assert not (wired.root / ".camarones" / "skills" / "demo").exists() and sp.load_lock() == {}
    assert (clash / "SKILL.md").read_text(encoding="utf-8").endswith("Ours.\n---\n")


def test_remove_drops_unchanged_folders_and_keeps_an_edited_one(wired, monkeypatch, tmp_path):
    repo, sha = source_repo(tmp_path)
    use_catalog(wired, monkeypatch, tmp_path, repo, sha)
    sp = packs(wired)
    sp.add("demo-pack")
    edited = wired.root / ".camarones" / "skills" / "demo-help" / "SKILL.md"
    edited.write_text(edited.read_text(encoding="utf-8") + "our tweak\n", encoding="utf-8")
    out = sp.remove("demo-pack")
    assert out == {"removed": ["demo"], "kept": ["demo-help"]}
    assert not (wired.root / ".camarones" / "skills" / "demo").exists() and edited.is_file()
    assert sp.load_lock() == {}
    with pytest.raises(ValueError, match="not added"):
        sp.remove("demo-pack")


# ---------- on and off for the project ----------

def test_a_skill_off_for_the_project_is_not_rendered_until_enabled(wired):
    s = skills(wired)
    assert s.project_off() == set()                                   # no `skills:` key: everything on, as before
    ws = wired.services.workspace.workspace()
    ws["skills"] = {"off": ["cam-docs-diagrams"]}
    wired.services.workspace.save_workspace(ws)
    assert s.project_off() == {"cam-docs-diagrams"} and "cam-docs-diagrams" not in s.sources()
    wired.services.templates.write_kit_skills()
    assert not rendered(wired, "cam-docs-diagrams") and not rendered(wired, "cam-docs-diagrams", ".agents")
    assert rendered(wired, "cam-task")
    ws["skills"] = {"off": []}
    wired.services.workspace.save_workspace(ws)
    wired.services.templates.write_kit_skills()
    assert rendered(wired, "cam-docs-diagrams")


# ---------- on and off for this machine ----------

def local_settings(kit):
    return [p for p in {(kit.ws / ".claude" / "settings.local.json"), (kit.root / ".claude" / "settings.local.json")}
            if p.parent.is_dir()]


def test_off_for_this_machine_writes_only_the_kits_deny_rules(wired):
    sp = packs(wired)
    own = wired.ws / ".claude" / "settings.local.json"
    own.parent.mkdir(exist_ok=True)
    own.write_text(json.dumps({"permissions": {"deny": ["Bash(rm:*)"], "allow": ["Read"]}}), encoding="utf-8")
    trust = importlib.import_module("lib.trust")
    asked = lambda: sorted((it.id, it.digest) for it, _ in trust.pending())     # noqa: E731
    before = asked()
    sp.set_machine("cam-docs-diagrams", False)
    assert sp.machine_off() == {"cam-docs-diagrams"}
    for f in local_settings(wired):
        deny = json.loads(f.read_text(encoding="utf-8"))["permissions"]["deny"]
        assert "Skill(cam-docs-diagrams)" in deny
    data = json.loads(own.read_text(encoding="utf-8"))
    assert "Bash(rm:*)" in data["permissions"]["deny"] and data["permissions"]["allow"] == ["Read"]
    sp.apply_machine()                                                  # idempotent
    assert json.loads(own.read_text(encoding="utf-8"))["permissions"]["deny"].count("Skill(cam-docs-diagrams)") == 1
    assert rendered(wired, "cam-docs-diagrams")                         # the team's files stay: git shows no diff
    assert asked() == before                                            # deny rules widen nothing: no new approval
    sp.set_machine("cam-docs-diagrams", True)
    data = json.loads(own.read_text(encoding="utf-8"))
    assert data["permissions"]["deny"] == ["Bash(rm:*)"] and sp.machine_off() == set()


def test_a_deny_rule_the_person_wrote_is_never_removed(wired):
    sp = packs(wired)
    own = wired.ws / ".claude" / "settings.local.json"
    own.parent.mkdir(exist_ok=True)
    own.write_text(json.dumps({"permissions": {"deny": ["Skill(cam-retro)"]}}), encoding="utf-8")
    sp.set_machine("cam-retro", False)
    sp.set_machine("cam-retro", True)
    assert json.loads(own.read_text(encoding="utf-8"))["permissions"]["deny"] == ["Skill(cam-retro)"]


# ---------- the command line ----------

def cli(kit, *args):
    env = {**os.environ, "CAMARONES_ROOT": str(kit.root)}
    return subprocess.run([sys.executable, str(KIT_DIR / "camarones.py"), "skills", *args], env=env,
                          capture_output=True, text=True, encoding="utf-8")


def test_list_json_shows_icons_switches_and_the_packs_available(wired):
    r = cli(wired, "disable", "cam-docs-diagrams")
    assert r.returncode == 0, r.stderr
    assert "off for the project" in r.stdout
    r = cli(wired, "disable", "cam-retro", "--machine")
    assert r.returncode == 0 and "off on this machine" in r.stdout, r.stderr
    data = json.loads(cli(wired, "list", "--json").stdout)
    rows = {s["name"]: s for s in data["skills"]}
    assert rows["cam-task"]["icon"] and rows["cam-task"]["project"] == "on" and rows["cam-task"]["machine"] == "on"
    assert rows["cam-docs-diagrams"]["project"] == "off" and rows["cam-retro"]["machine"] == "off"
    assert {"ponytail", "impeccable"} <= {p["name"] for p in data["available"]}
    pony = next(p for p in data["available"] if p["name"] == "ponytail")
    assert pony["icon"] and pony["license"] == "MIT" and "ponytail-review" in pony["skills"]
    assert cli(wired, "enable", "cam-docs-diagrams").returncode == 0
    assert cli(wired, "enable", "cam-retro", "--machine").returncode == 0
    rows = {s["name"]: s for s in json.loads(cli(wired, "list", "--json").stdout)["skills"]}
    assert rows["cam-docs-diagrams"]["project"] == "on" and rows["cam-retro"]["machine"] == "on"


def test_bad_skill_switches_are_one_line_and_exit_2(wired):
    for args in (("disable", "nope"), ("enable",), ("add", "nope"), ("remove", "nope"),
                 ("list", "--machine"), ("fork", "cam-task", "--machine")):
        r = cli(wired, *args)
        assert r.returncode == 2 and r.stderr.startswith("✖") and len(r.stderr.strip().splitlines()) == 1, args


def test_trust_still_asks_for_permissions_that_widen_access(wired):
    trust = importlib.import_module("lib.trust")
    f = wired.root / ".claude" / "settings.local.json"
    f.write_text(json.dumps({"permissions": {"deny": ["Skill(x)"], "allow": ["Bash(curl:*)"]}}), encoding="utf-8")
    asked = [it for it, _ in trust.pending() if it.id == "claude permissions (local)"]
    assert asked and "allow" in asked[0].detail and "Skill(x)" not in asked[0].detail


def test_a_hand_written_off_list_counts_though_yaml_reads_off_as_false(wired):
    s = skills(wired)
    f = wired.root / ".camarones" / "workspace.yaml"
    f.write_text(f.read_text(encoding="utf-8") + "skills:\n  off: [cam-retro]\n", encoding="utf-8")
    assert s.project_off() == {"cam-retro"}


def test_turning_the_last_skill_back_on_leaves_no_empty_key(wired):
    assert cli(wired, "disable", "cam-retro").returncode == 0
    assert cli(wired, "enable", "cam-retro").returncode == 0
    assert "skills" not in wired.services.workspace.workspace()
