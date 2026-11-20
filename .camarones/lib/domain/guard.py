"""The guardrails' pure rules (P3): what counts as an AI credit in a commit, which paths never belong in a change,
Claude Code's attribution setting turned off, and when the gate's checks are green. No git, no network, no project paths.

`AI_CREDIT` is the pattern of lib/githooks/kit/commit-msg and pre-push, in Python's syntax; tests/test_guard_hooks.py
keeps the three in step."""
from __future__ import annotations

import re
from pathlib import PurePosixPath

AI_CREDIT = re.compile(r"^[ \t]*co-authored-by:([ \t]*claude([^a-z]|$)|.*@anthropic\.com)|^[^a-z0-9\n]*generated with \[?claude code",
                       re.I | re.M)
FORBIDDEN_NAMES = (".env", ".env.*", "*.pem", "*.key", "id_rsa*")
FORBIDDEN_DIRS = ("secrets",)
ENV_EXAMPLES = (".env.example", ".env.sample", ".env.template")   # placeholders a team commits on purpose
STATUSES = ("pass", "fail", "not-run", "n/a")


def has_ai_credit(message: str) -> bool:
    return bool(AI_CREDIT.search(message))


def forbidden(path: str) -> bool:
    """A file a change must not carry: environment files, private keys, anything under a `secrets/` folder."""
    p = PurePosixPath(path.replace("\\", "/"))
    if p.name in ENV_EXAMPLES:
        return False
    return any(p.match(pattern) for pattern in FORBIDDEN_NAMES) or any(d in p.parts[:-1] for d in FORBIDDEN_DIRS)


def attribution_is_off(settings: dict) -> bool:
    a = settings.get("attribution")
    return a is False or (isinstance(a, dict) and a.get("commit") == "" and a.get("pr") == "" and a.get("sessionUrl") is False)


def attribution_off(settings: dict) -> dict:
    """`settings` with Claude Code's commit and PR attribution empty (`attribution`, which replaced the deprecated
    `includeCoAuthoredBy` in Claude Code 2.0.62), and no claude.ai session link either (`sessionUrl`, for web and Remote
    Control sessions); the rest of the file stays."""
    a = settings.get("attribution")
    return {**settings, "attribution": {**(a if isinstance(a, dict) else {}), "commit": "", "pr": "", "sessionUrl": False}}


def overall(checks: list[dict]) -> str:
    """`fail` beats `not-run`; only `pass` and `n/a` checks make `pass`: a check that could not run is never green."""
    statuses = {c["status"] for c in checks}
    return "fail" if "fail" in statuses else "not-run" if "not-run" in statuses else "pass"


def exit_code(checks: list[dict]) -> int:
    return {"pass": 0, "fail": 1, "not-run": 3}[overall(checks)]


def _major(version: str) -> int | None:
    m = re.match(r"[^\d]*(\d+)", version or "")
    return int(m.group(1)) if m else None


def majors_behind(current: str, latest: str) -> int:
    """How many major versions `current` (a declared range such as `^4.1` counts by its first number) trails `latest`."""
    a, b = _major(current), _major(latest)
    return max(0, b - a) if a is not None and b is not None else 0


# the files OSV-Scanner reads packages from: a change that touches none of them has nothing for the vulnerability check
LOCK_FILES = ("pom.xml", "package-lock.json", "npm-shrinkwrap.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock", "uv.lock",
              "Pipfile.lock", "requirements*.txt", "go.mod", "go.sum", "Cargo.lock", "composer.lock", "Gemfile.lock",
              "gradle.lockfile", "packages.lock.json", "pubspec.lock", "mix.lock")


def is_lockfile(path: str) -> bool:
    return any(PurePosixPath(path.replace("\\", "/")).match(pattern) for pattern in LOCK_FILES)
