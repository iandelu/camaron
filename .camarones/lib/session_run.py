"""Runs an interactive agent session inside the terminal window the kit opened, and keeps its record current
(lib/sessions.py): this process's pid while the agent runs, then when it ended and how. A closed window kills this
process too, so a record with a dead pid is a session nobody has open any more.

Executed as a script by that terminal (`python session_run.py <record> -- <agent argv>`), so stdlib only, but for the
kit's file lock (stdlib too): each write holds the record's lock, the one lib/sessions.py takes. A `-` record is none
(the docs update): the agent just runs, with Ctrl+C its own."""
from __future__ import annotations

import json
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path


def _write(path: Path, rec: dict) -> None:
    tmp = path.with_name(path.name + f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps(rec), encoding="utf-8")
    for _ in range(50):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:                 # Windows: the server is reading it right now
            time.sleep(0.05)
    tmp.unlink(missing_ok=True)


def _read(path: Path) -> dict:
    try:
        rec = json.loads(path.read_text(encoding="utf-8"))
        return rec if isinstance(rec, dict) else {}
    except (OSError, ValueError):
        return {}


def _lock(path: Path):
    if __package__:
        from .harness.locks import FileLock
    else:
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        from lib.harness.locks import FileLock
    return FileLock(path.with_name(path.name + ".lock"), wait=10)


_ANY = object()


def _update(path: Path, launched=_ANY, **fields) -> dict:
    """The record with `fields`, under its lock, and what it now holds. One that cannot be had in time, or loaded, does
    not stop the write. With `launched`, only while the record is still that session's: a newer one (sessions.start
    after a takeover, or the unit reopened) has its own, and it is left alone."""
    try:
        lock = _lock(path)
        lock.acquire()
    except Exception:
        lock = None
    try:
        rec = _read(path)
        if launched is not _ANY and rec.get("launched") != launched:
            return rec
        rec = {**rec, **fields}
        _write(path, rec)
        return rec
    finally:
        if lock:
            lock.release()


def main(argv: list[str]) -> int:
    if len(argv) < 3 or argv[1] != "--":
        print("usage: session_run.py <record | -> -- <command…>", file=sys.stderr)
        return 2
    path, cmd = None if argv[0] == "-" else Path(argv[0]), argv[2:]
    env = dict(os.environ)                      # the agent's, as the terminal gave it: loading the lock adds the kit's
    mine = None                                 # the session this wrapper runs: its record's `launched`
    if path:
        mine = _update(path, pid=os.getpid(), host=socket.gethostname(), ts=time.time()).get("launched")
    # Ctrl+C belongs to the agent; a handler, not SIG_IGN, so it resets. Put back once the record has its end, for a
    # caller in this process
    old = signal.signal(signal.SIGINT, lambda *_: None)
    try:
        try:
            code = subprocess.call(cmd, env=env)
        except OSError as e:
            print(e, file=sys.stderr)
            code = 127
        if path:                                # the agent can end before this process when its terminal closes
            _update(path, mine, ended=time.time(), code=code)
    finally:
        signal.signal(signal.SIGINT, old)
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
