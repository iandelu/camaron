"""Where a project's C4 model lives. By default in cam-docs (`docs/architecture`); a project whose service repo keeps
its own LikeC4 model points at it in workspace.yaml (`project.architecture: <repo>:<path>`), so there is one model and
the kit lists, builds, edits and checks that one. Pure: the value and the workspace's repos come in as data."""
from __future__ import annotations

import re
from pathlib import PurePosixPath

KEY = "architecture"                    # under `project:` in workspace.yaml
DRIVE = re.compile(r"^[A-Za-z]:[\\/]")  # a Windows path written where `<repo>:<path>` goes


def parse(value: object, repos: list[str]) -> tuple[str, str] | None:
    """(repo, path) for `<repo>:<path>`, the path relative to that repo's folder in posix form; None when the key is
    unset (the model is in cam-docs). ValueError says why a value cannot be used: not text, no `<repo>:`, a repo
    workspace.yaml does not list, an empty or absolute path, or one that leaves the repo."""
    if value is None or isinstance(value, str) and not value.strip():
        return None
    how = "write it as <repo>:<path>, e.g. api:docs/architecture"
    if not isinstance(value, str) or ":" not in value or DRIVE.match(value.strip()):
        raise ValueError(f"project.architecture: {how} (got {value!r})")
    repo, _, path = value.partition(":")
    repo, path = repo.strip(), path.strip().replace("\\", "/")
    if repo not in repos:
        raise ValueError(f"project.architecture: {repo!r} is not a repo in workspace.yaml ({how})")
    p = PurePosixPath(path)
    if not path or p.is_absolute() or ".." in p.parts:
        raise ValueError(f"project.architecture: {path!r} must be a folder inside {repo} ({how})")
    return repo, p.as_posix()
