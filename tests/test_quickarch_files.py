"""quickarch.files(): the files of a repo the static scan reads, and the folders it never walks into."""
from __future__ import annotations

import os
from pathlib import Path


def _tree(root: Path, spec: dict[str, str]) -> Path:
    for rel, text in spec.items():
        f = root / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8")
    return root


def _rel(repo: Path, found) -> list[str]:
    return sorted(p.relative_to(repo).as_posix() for p in found)


def test_it_never_walks_into_a_skipped_folder(kit, tmp_path, monkeypatch):
    """`node_modules` held ~195k entries in this very repo: listing them to throw them away cost 3 s per scan, and a
    quality check scans seven times."""
    from lib import quickarch
    repo = _tree(tmp_path / "repo", {"src/App.java": "x", "node_modules/pkg/deep/index.js": "x",
                                     "web/node_modules/pkg/index.js": "x", "build/out/Gen.java": "x"})
    listed: list[str] = []
    real = os.scandir

    def spy(path="."):
        listed.append(str(path))
        return real(path)
    monkeypatch.setattr(os, "scandir", spy)
    assert _rel(repo, quickarch.files(repo)) == ["src/App.java"]
    inside = [Path(p).relative_to(repo) for p in listed if p.startswith(str(repo))]
    assert inside and not [d for d in inside if set(d.parts) & quickarch.SKIP_DIRS]


def test_it_yields_the_source_files_it_always_did(kit, tmp_path):
    from lib import quickarch
    repo = _tree(tmp_path / "repo", {
        "pom.xml": "x", "Dockerfile": "x", "pubspec.yaml": "x", ".env.local": "x", "README.md": "x", "notes.txt": "x",
        "src/main/App.java": "x", "src/main/application.yml": "x", "web/app.ts": "x",
        "web/dist/app.js": "x", ".git/config.json": "x", "vendor/lib.go": "x", ".claude/x.json": "x"})
    (repo / "big.json").write_text("x" * (quickarch.MAX_BYTES + 1), encoding="utf-8")
    assert _rel(repo, quickarch.files(repo)) == [".env.local", "Dockerfile", "pom.xml", "pubspec.yaml",
                                                 "src/main/App.java", "src/main/application.yml", "web/app.ts"]


def test_the_order_does_not_depend_on_the_filesystem(kit, tmp_path, monkeypatch):
    """The first file that matches a pattern is the evidence a C4 element cites: it must not change with the order a
    filesystem lists a folder in (NTFS sorts, ext4 and APFS do not)."""
    from lib import quickarch
    repo = _tree(tmp_path / "repo", {"b.py": "x", "a.py": "x", "z/y.py": "x", "m/n.py": "x"})
    real = os.scandir

    class Backwards:
        def __init__(self, path):
            self._it = iter(sorted(real(path), key=lambda e: e.name, reverse=True))

        def __iter__(self): return self
        def __next__(self): return next(self._it)
        def __enter__(self): return self
        def __exit__(self, *exc): return False
        def close(self): pass
    monkeypatch.setattr(os, "scandir", Backwards)
    assert [p.relative_to(repo).as_posix() for p in quickarch.files(repo)] == ["a.py", "b.py", "m/n.py", "z/y.py"]


def test_it_stops_at_the_file_cap(kit, tmp_path, monkeypatch):
    from lib import quickarch
    repo = _tree(tmp_path / "repo", {f"a/{i}.py": "x" for i in range(5)} | {f"b/{i}.py": "x" for i in range(5)})
    monkeypatch.setattr(quickarch, "MAX_FILES", 3)
    assert len(list(quickarch.files(repo))) == 3
