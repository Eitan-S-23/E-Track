"""Read newline-terminated host receipts without racing their first publication."""
from __future__ import annotations

import json
import math
from pathlib import Path
import runpy
import time

ROOT = Path(__file__).resolve().parents[2]
IO = runpy.run_path(str(ROOT / ".agents/skills/e-track-flutter-debug/scripts/host_io.py"))
MAX_BYTES = 4 * 1024 * 1024


def wait_json(root, path, seconds=90, *, clock=time.monotonic, sleep=time.sleep):
    """Wait for one receipt, never repeat the operation that produces it.

    host_io.write_json appends a newline after the complete JSON object. Its
    write-once path is visible before that write finishes; file existence alone
    is not publication. Persistent malformed data still fails after two seconds.
    """
    if type(seconds) not in (int, float) or not math.isfinite(seconds) or not 0 < seconds <= 600:
        raise ValueError("receipt wait must be between zero and 600 seconds")
    path = IO["checked_output"](root, path)
    started = clock()
    deadline = started + seconds
    partial_since = None
    while True:
        now = clock()
        if now < started or now >= deadline:
            raise TimeoutError("receipt publication deadline: " + str(path))
        try:
            with path.open("rb") as stream:
                raw = stream.read(MAX_BYTES + 1)
        except FileNotFoundError:
            raw = None
        if raw is not None:
            if len(raw) > MAX_BYTES:
                raise ValueError("receipt exceeds its byte limit: " + str(path))
            try:
                value = json.loads(raw) if raw.endswith(b"\n") else None
            except (json.JSONDecodeError, UnicodeDecodeError):
                value = None
            else:
                if raw.endswith(b"\n"):
                    if not isinstance(value, dict):
                        raise ValueError("receipt must contain one JSON object: " + str(path))
                    return value
            if partial_since is None:
                partial_since = now
        if partial_since is not None and now - partial_since >= 2:
            raise ValueError("receipt stayed incomplete or malformed: " + str(path))
        remaining = deadline - now
        if partial_since is not None:
            remaining = min(remaining, partial_since + 2 - now)
        sleep(min(.025, remaining))
