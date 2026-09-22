"""Project-contained output guards and bounded Windows atomic replacement."""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import stat
import time


class OutputBoundaryError(ValueError):
    pass


def _ordinary_path(value):
    text = os.fspath(value)
    if os.name == "nt":
        if text.startswith("\\\\?\\UNC\\"):
            text = "\\\\" + text[8:]
        elif re.match(r"^\\\\\?\\[A-Za-z]:\\", text):
            text = text[4:]
        elif text.startswith(("\\\\?\\", "\\\\.\\")):
            raise OutputBoundaryError("unsupported Windows device namespace")
    return Path(text)


def _no_reparse_points(path):
    for item in (path, *path.parents):
        try:
            info = item.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise OutputBoundaryError("output reparse point: " + str(item))


def checked_output(root, value):
    """Return the path to use, resolving a stable parent rather than a racy leaf.

    The caller supplies the already-authorized absolute project root. This is a
    preflight guard, not protection against adversarial concurrent path changes.
    """
    root = _ordinary_path(root)
    if not root.is_absolute() or not root.is_dir():
        raise OutputBoundaryError("existing absolute authorized project root required")
    root = Path(os.path.abspath(root))
    _no_reparse_points(root)
    canonical_root = _ordinary_path(root.resolve(strict=True))
    path = _ordinary_path(value)
    if path.drive and not path.is_absolute():
        raise OutputBoundaryError("drive-relative output is ambiguous")
    path = Path(os.path.abspath(path if path.is_absolute() else root / path))
    _no_reparse_points(path)
    parent, missing = path.parent, []
    while True:
        try:
            info = parent.lstat()
            if not stat.S_ISDIR(info.st_mode):
                raise OutputBoundaryError("output parent is not a directory")
            resolved = _ordinary_path(parent.resolve(strict=True))
            break
        except FileNotFoundError:
            if parent == parent.parent:
                raise OutputBoundaryError("no stable existing output parent") from None
            missing.append(parent.name)
            parent = parent.parent
    candidate = resolved.joinpath(*reversed(missing), path.name)
    try:
        candidate.relative_to(canonical_root)
    except ValueError:
        raise OutputBoundaryError("output is outside the authorized project root") from None
    _no_reparse_points(candidate)
    return candidate


def replace_file(root, source, target, *, seconds=2.0, clock=time.monotonic,
                 sleep=time.sleep, replace=os.replace):
    source, target = checked_output(root, source), checked_output(root, target)
    if type(seconds) not in (int, float) or not 0 < seconds <= 2:
        raise ValueError("replace retry must be bounded to at most two seconds")
    started, attempts = clock(), 0
    while True:
        attempts += 1
        try:
            replace(source, target)
            return attempts
        except OSError as error:
            elapsed = clock() - started
            if getattr(error, "winerror", None) not in (5, 32, 33) or not 0 <= elapsed < seconds:
                raise
            sleep(min(.025, seconds-elapsed))


def write_json(root, path, value, *, replace=False):
    """Write-once by default; replace=True is for an owned mutable status file."""
    path = checked_output(root, path)
    pending = checked_output(root, path.with_suffix(path.suffix + ".tmp")) if replace else path
    checked_output(root, path.parent).mkdir(parents=True, exist_ok=True)
    path, pending = checked_output(root, path), checked_output(root, pending)
    with pending.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    if replace:
        replace_file(root, pending, path)
    return path
