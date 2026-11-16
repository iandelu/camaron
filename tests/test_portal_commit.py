"""The portal's commit (`POST /api/commit`): a checkpoint of the docs as they stand, with the portal's message or its
default, the agents' index rebuilt first. A public route: any page on this machine may call it, so only the server's
gates stand in front of it (the X-Camarones header, the host, static mode)."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from fixtures.http_probe import arm, request, serving


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True,
                          encoding="utf-8").stdout.strip()


def project(kit) -> Path:
    """A set-up cam-docs (a git repo) with one page not checkpointed yet."""
    kit.services.templates.init_templates("demo", log=lambda _: None)
    note = kit.root / "docs" / "note.md"
    note.write_text("# Note\n", encoding="utf-8")
    return note


def test_commit_checkpoints_the_docs_with_the_portals_message(kit, monkeypatch):
    project(kit)
    arm(monkeypatch)
    with serving(kit.serve.Handler) as base:
        status, _, raw = request(base, "POST", "/api/commit", b'{"message": "note added"}')
        got = json.loads(raw)
        assert (status, got["committed"]) == (200, True)
        assert got["head"] == git(kit.root, "log", "-1", "--format=%h %s")
        assert got["head"].endswith(" docs(camarones): note added")
        assert git(kit.root, "status", "--porcelain", "--", "docs") == ""
        assert "note.md" in git(kit.root, "show", "HEAD:docs/llms.txt")         # the index was rebuilt, then committed

        (kit.root / "docs" / "other.md").write_text("# Other\n", encoding="utf-8")
        status, _, raw = request(base, "POST", "/api/commit", b"{}")            # no message: the portal's default
    assert (status, json.loads(raw)["head"].split(" ", 1)[1]) == (200, "docs(camarones): docs edited in the portal")
    assert git(kit.root, "status", "--porcelain", "--", "docs") == ""


def test_commit_answers_only_the_portal_on_this_machine(kit, monkeypatch):
    note = project(kit)
    pending = git(kit.root, "status", "--porcelain", "--", "docs/note.md")
    arm(monkeypatch)
    with serving(kit.serve.Handler) as base:
        status, _, raw = request(base, "POST", "/api/commit", b"{}", marked=False)   # a cross-site page cannot send it
        assert (status, json.loads(raw)) == (403, {"error": "forbidden"})
        status, _, raw = request(base, "POST", "/api/commit", b"{}", host="evil.test")
        assert (status, json.loads(raw)) == (403, {"error": "forbidden"})
    arm(monkeypatch, static=True)
    with serving(kit.serve.Handler) as base:
        status, _, raw = request(base, "POST", "/api/commit", b"{}")
    assert (status, json.loads(raw)) == (405, {"error": "read-only portal — run `camaron up` to edit"})
    assert pending.startswith("??") and note.is_file()
    assert git(kit.root, "status", "--porcelain", "--", "docs/note.md") == pending   # still not checkpointed
