"""The DiagramEngine port (lib/ports/diagram_engine.py) on LikeC4: the model under docs/architecture, or in a service
repo's folder when workspace.yaml says so (lib/domain/architecture.py), checked with `likec4 validate`, edited live
with `likec4 start`, and its views read with a regex so the portal needs no LikeC4."""
from __future__ import annotations

import re
from pathlib import Path, PurePosixPath

from lib.adapters.stores import workspace
from lib.common import DOCS, repo_dir, run
from lib.domain import architecture


def _ref() -> tuple[str, str] | None:
    """(repo, path) of a model kept in a service repo; None for cam-docs, and for a value `check` reports as unusable."""
    try:
        return architecture.parse(workspace.workspace()["project"].get(architecture.KEY), workspace.repo_names())
    except ValueError:
        return None


def arch_source() -> str | None:
    """`<repo>:<path>` when the model lives in a service repo (workspace.yaml `project.architecture`), else None."""
    ref = _ref()
    return f"{ref[0]}:{ref[1]}" if ref else None


def arch_where() -> str:
    """The model's folder as a person reads it in a message: `docs/architecture` or `<repo>:<path>`."""
    return arch_source() or "docs/architecture"


def arch_dir() -> Path:
    """The model's folder. A configured repo that is not cloned yet still answers its folder: falling back to cam-docs
    would let arch-draft write the second model the key is there to avoid."""
    ref = _ref()
    return repo_dir(ref[0]).joinpath(*PurePosixPath(ref[1]).parts) if ref else DOCS / "architecture"


def arch_validate() -> tuple[bool, str]:
    if not (arch_dir() / "likec4.config.json").exists():
        return False, f"no {arch_where()}/likec4.config.json yet"
    r = run(["likec4", "validate", "."], cwd=arch_dir(), check=False, capture=True)
    text = re.sub(r"\x1b\[[0-9;]*m", "", (r.stdout or "") + (r.stderr or ""))
    keep = [l for l in text.splitlines() if re.search(r"ERROR|Line \d+|Invalid|Valid|WARN .*layout", l)]
    return r.returncode == 0, "\n".join(keep[-40:])


def arch_start() -> None:
    run(["likec4", "start", "."], cwd=arch_dir(), check=False)


C4_VIEW_RE = re.compile(r"^\s*(dynamic\s+|deployment\s+)?view\s+([A-Za-z_][\w-]*)\b", re.M)
C4_TITLE_RE = re.compile(r"""^\s*title\s+(['"])(.*?)\1""", re.M)


def c4_views() -> list[dict]:
    """Views declared in the model, read with a regex so the portal can list and embed them without LikeC4."""
    arch = arch_dir()
    found = []
    for f in sorted(arch.rglob("*.c4"), key=lambda p: (p.parent != arch, p.as_posix())) if arch.is_dir() else []:
        text = f.read_text(encoding="utf-8", errors="replace")
        decls = list(C4_VIEW_RE.finditer(text))
        for i, m in enumerate(decls):
            block = text[m.end(): decls[i + 1].start() if i + 1 < len(decls) else len(text)]
            title = C4_TITLE_RE.search(block)
            kind = (m.group(1) or "element").strip()
            found.append({"id": m.group(2), "title": title.group(2) if title else m.group(2), "kind": kind,
                          "file": f.relative_to(arch).as_posix()})
    return found
