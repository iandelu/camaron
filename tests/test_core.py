"""lib/core: the leaf modules every layer builds on; the old paths keep handing out the very same objects."""
from __future__ import annotations

import importlib
import os
import re
import subprocess
import sys
import time

import pytest

from conftest import KIT_DIR, purge_kit_modules

COMMON_NAMES = [
    "IS_WIN", "IS_MAC", "HOME", "PREFS", "CTX", "ROOT", "CAM_LAYOUT", "WORKSPACE", "DOCS", "WORK", "WS_FILE", "CACHE",
    "GRAPHS", "KIT", "CAM_DIR", "Ctx", "docs_root", "find_project_marker", "find_root", "repo_dir", "ws_rel",
    "rel_file", "cli_cmd", "sdkman_dir", "extra_bin_dirs", "ensure_path", "which", "run", "out", "PARENT_SESSION",
    "leave_parent_session", "kill_tree", "uv", "retry_busy", "load_json", "save_json", "py", "rmtree", "VERSIONS",
]


def test_kit_is_still_the_kit_folder(kit):
    from lib.core import ctx
    assert ctx.KIT.resolve() == KIT_DIR.resolve()


def test_old_lock_paths_give_the_same_objects(kit):
    from lib.core import locks as new
    from lib.harness import locks as old
    assert (old.FileLock, old.LockBusy, old.pid_alive) == (new.FileLock, new.LockBusy, new.pid_alive)
    assert old.LockBusy is new.LockBusy


def test_old_ctx_path_gives_the_same_objects(kit):
    from lib.core import ctx as new
    from lib.harness import ctx as old
    for name in ("KIT", "CAM_DIR", "Ctx", "docs_root", "find_project_marker", "find_root"):
        assert getattr(old, name) is getattr(new, name)


def test_common_still_offers_the_file_helpers(kit):
    from lib.core import fsutil
    for name in ("retry_busy", "load_json", "save_json", "rmtree"):
        assert getattr(kit.common, name) is getattr(fsutil, name)


def test_common_re_exports_every_name_it_had(kit):
    from lib.core import paths, process
    assert [n for n in COMMON_NAMES if not hasattr(kit.common, n)] == []
    assert kit.common.run is process.run and kit.common.ROOT == paths.ROOT
    assert kit.common.__facade__ == "lib.core"


def test_the_kit_version_is_still_written_in_common_py(kit):
    from lib import upgrade
    text = (KIT_DIR / "lib" / "common.py").read_text(encoding="utf-8")
    assert upgrade._version_in(text) == kit.common.VERSIONS["kit"]
    assert re.search(r'"kit":\s*"([\d.]+)"', text).group(1) == kit.common.VERSIONS["kit"]


def test_importing_common_alone_extends_path(isolated_env, monkeypatch):
    extra = isolated_env / ".local" / "bin"
    extra.mkdir(parents=True)
    monkeypatch.delenv("CAMARONES_KEEP_PATH", raising=False)
    monkeypatch.setenv("PATH", "base")
    purge_kit_modules()
    try:
        importlib.import_module("lib.common")
        assert str(extra) in os.environ["PATH"].split(os.pathsep)
    finally:
        purge_kit_modules()


def test_now_is_utc_to_the_second():
    """now() moved from docs.py to core/clock.py (F5a): an ISO time in UTC without microseconds, as .state.json keeps it."""
    now = importlib.import_module("lib.core.clock").now()
    assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\+00:00", now)


SLEEPS = [sys.executable, "-c", "import time; time.sleep(30)"]


def test_a_command_past_its_timeout_is_killed_and_raises(kit):
    from lib.core import process
    calls = (lambda: process.out(SLEEPS, timeout=1),
             lambda: process.run(SLEEPS, timeout=1, check=False, capture=True))
    for call in calls:
        started = time.monotonic()
        with pytest.raises(subprocess.TimeoutExpired):
            call()
        assert time.monotonic() - started < 15                    # back long before the child would have ended


def test_a_command_inside_its_timeout_answers_as_before(kit):
    from lib.core import process
    assert process.out([sys.executable, "-c", "print('hi')"], timeout=30) == "hi"
    assert process.run([sys.executable, "-c", "pass"], timeout=30, check=False).returncode == 0


def test_no_timeout_leaves_subprocess_run_as_it_was(kit, monkeypatch):
    from lib.core import process
    monkeypatch.setattr(process, "IS_WIN", False)
    seen = []

    def fake(cmd, **kw):
        seen.append(kw)
        return subprocess.CompletedProcess(cmd, 0, "x\n", "")
    monkeypatch.setattr(process.subprocess, "run", fake)
    assert process.out(["tool"]) == "x"
    assert "timeout" not in seen[0]


def traps_term(marker, then="sys.exit(143)"):
    return [sys.executable, "-c", "import pathlib, signal, sys, time; signal.signal(signal.SIGTERM, lambda *a: "
            f"(pathlib.Path(sys.argv[1]).write_text('x'), {then})); time.sleep(30)", str(marker)]


@pytest.mark.skipif(sys.platform == "win32", reason="Windows has no SIGTERM to send a console program: its tree is killed")
def test_a_timed_out_command_is_asked_to_stop_before_it_is_killed(kit, tmp_path):
    from lib.core import process
    marker = tmp_path / "cleaned"                  # git drops its refs/*.lock on SIGTERM; SIGKILL leaves them behind
    with pytest.raises(subprocess.TimeoutExpired):
        process.run(traps_term(marker), timeout=2, check=False, capture=True)
    assert marker.exists()


@pytest.mark.skipif(sys.platform == "win32", reason="Windows has no SIGTERM to send a console program: its tree is killed")
def test_a_command_that_will_not_stop_is_killed_after_the_grace(kit, tmp_path, monkeypatch):
    from lib.core import process
    monkeypatch.setattr(process, "TERM_GRACE", 0.5)
    started = time.monotonic()
    with pytest.raises(subprocess.TimeoutExpired):
        process.run(traps_term(tmp_path / "m", then="None"), timeout=2, check=False, capture=True)
    assert time.monotonic() - started < 15


# Git for Windows' git.exe is a launcher that starts the real git, which holds the pipes: killing the launcher alone
# leaves subprocess waiting on them for as long as the real git runs. A timeout must not wait on such a child.
GRANDCHILD = [sys.executable, "-c", "import subprocess, sys, time; subprocess.Popen([sys.executable, '-c', "
              "'import time; time.sleep(30)'], stdout=sys.stdout, stderr=sys.stderr); time.sleep(30)"]


def test_a_timeout_does_not_wait_on_a_child_the_command_started(kit):
    from lib.core import process
    started = time.monotonic()
    with pytest.raises(subprocess.TimeoutExpired):
        process.run(GRANDCHILD, timeout=1, check=False, capture=True)
    assert time.monotonic() - started < 15


def test_on_windows_a_timeout_kills_the_command_and_what_it_started(kit, monkeypatch):
    from lib.core import process
    killed = []
    monkeypatch.setattr(process, "IS_WIN", True)
    monkeypatch.setattr(process, "kill_tree", lambda pid, sig=None: killed.append(pid) or True)
    with pytest.raises(subprocess.TimeoutExpired):
        process.run(SLEEPS, timeout=1, check=False, capture=True)
    assert len(killed) == 1
    assert process.out([sys.executable, "-c", "print('hi')"], timeout=30) == "hi"
    assert process.run([sys.executable, "-c", "import sys; sys.exit(3)"], timeout=30, check=False).returncode == 3
