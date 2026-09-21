"""Local-only skill regression tests; all fixtures stay in the explicit root."""
import argparse
import ctypes
from ctypes import wintypes
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import sys
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

spec = importlib.util.spec_from_file_location("flutter_debug_host_io", Path(__file__).with_name("host_io.py"))
io = importlib.util.module_from_spec(spec)
spec.loader.exec_module(io)
ROOT = OUT = None


def windows_error(code):
    error = PermissionError("sharing-test")
    error.winerror = code
    return error


class HostTests(unittest.TestCase):
    def setUp(self):
        self.out = io.checked_output(ROOT, OUT / self.id().rsplit(".", 1)[-1])
        self.out.mkdir()

    def test_missing_nested_output_is_contained(self):
        path = self.out / "a/b/state.json"
        self.assertEqual(io.checked_output(ROOT, path), path)
        self.assertFalse(path.parent.exists())

    def test_parent_traversal_and_sibling_prefix_are_rejected(self):
        for path in (ROOT.parent / (ROOT.name + "-other/file"), ROOT / "../outside/file"):
            with self.assertRaises(io.OutputBoundaryError):
                io.checked_output(ROOT, path)

    def test_relative_root_is_rejected(self):
        with self.assertRaises(io.OutputBoundaryError):
            io.checked_output(Path("."), self.out / "file")

    def test_volatile_leaf_is_never_resolved(self):
        path = self.out / "state.json.tmp"
        original = Path.resolve
        def resolve(value, *args, **kwargs):
            self.assertNotEqual(value, path)
            return original(value, *args, **kwargs)
        with patch.object(Path, "resolve", resolve):
            self.assertEqual(io.checked_output(ROOT, path), path)

    def test_disappearing_leaf_is_treated_as_a_new_output(self):
        path = io.write_json(ROOT, self.out / "state.json.tmp", {"seq":1})
        original = Path.lstat
        removed = False
        def lstat(value, *args, **kwargs):
            nonlocal removed
            if value == path and not removed:
                removed = True
                os.unlink(path)
                raise FileNotFoundError(str(path))
            return original(value, *args, **kwargs)
        with patch.object(Path, "lstat", lstat):
            self.assertEqual(io.checked_output(ROOT, path), path)
        self.assertTrue(removed)

    def test_reparse_attribute_is_rejected(self):
        parent = self.out / "junction"
        original = Path.lstat
        def lstat(path, *args, **kwargs):
            return (SimpleNamespace(st_mode=stat.S_IFDIR, st_file_attributes=0x400)
                    if path == parent else original(path, *args, **kwargs))
        with patch.object(Path, "lstat", lstat), self.assertRaises(io.OutputBoundaryError):
            io.checked_output(ROOT, parent / "file")

    def test_real_internal_symlink_is_rejected(self):
        target = io.checked_output(ROOT, self.out / "target")
        target.mkdir()
        link = io.checked_output(ROOT, self.out / "link")
        try:
            link.symlink_to(target, target_is_directory=True)
        except OSError as error:
            if os.name == "nt" and getattr(error, "winerror", None) == 1314:
                self.skipTest("Windows symlink privilege unavailable; attribute rejection tested separately")
            raise
        with self.assertRaises(io.OutputBoundaryError):
            io.checked_output(ROOT, link / "file")

    @unittest.skipUnless(os.name == "nt", "Windows path syntax")
    def test_extended_path_spelling_is_normalized(self):
        path = self.out / "pending.json.tmp"
        self.assertEqual(io.checked_output(ROOT, "\\\\?\\" + str(path)), path)

    @unittest.skipUnless(os.name == "nt", "Windows path syntax")
    def test_device_namespace_and_drive_relative_are_rejected(self):
        for value in ("\\\\.\\NUL", "\\\\?\\GLOBALROOT\\Device\\file", "D:ambiguous"):
            with self.assertRaises(io.OutputBoundaryError):
                io.checked_output(ROOT, value)

    def test_write_once_does_not_overwrite_receipt(self):
        path = io.write_json(ROOT, self.out / "receipt.json", {"reserved":1})
        with self.assertRaises(FileExistsError):
            io.write_json(ROOT, path, {"reserved":2})
        self.assertEqual(json.loads(path.read_text()), {"reserved":1})

    def test_atomic_status_has_no_pending_file_after_success(self):
        path = io.write_json(ROOT, self.out / "status.json", {"seq":1})
        io.write_json(ROOT, path, {"seq":2}, replace=True)
        self.assertEqual(json.loads(path.read_text()), {"seq":2})
        self.assertFalse(path.with_suffix(".json.tmp").exists())

    def test_existing_pending_evidence_is_not_deleted(self):
        path = io.write_json(ROOT, self.out / "status.json", {"seq":1})
        pending = io.write_json(ROOT, path.with_suffix(".json.tmp"), {"uncertain":True})
        with self.assertRaises(FileExistsError):
            io.write_json(ROOT, path, {"seq":2}, replace=True)
        self.assertEqual(json.loads(pending.read_text()), {"uncertain":True})
        self.assertEqual(json.loads(path.read_text()), {"seq":1})

    def test_retry_only_repeats_the_same_rename(self):
        for code in (5, 32, 33):
            operation = Mock(side_effect=[windows_error(code), None])
            count = io.replace_file(ROOT, self.out / "source", self.out / "target",
                                    replace=operation, clock=lambda:0, sleep=Mock())
            self.assertEqual(count, 2)
            self.assertEqual(operation.call_args_list[0], operation.call_args_list[1])

    def test_persistent_and_unrelated_errors_fail(self):
        clock = iter([0, .5, 2])
        operation = Mock(side_effect=windows_error(5))
        with self.assertRaises(PermissionError):
            io.replace_file(ROOT, self.out / "a", self.out / "b", replace=operation,
                            clock=lambda:next(clock), sleep=Mock())
        self.assertEqual(operation.call_count, 2)
        operation = Mock(side_effect=OSError("disk"))
        with self.assertRaises(OSError):
            io.replace_file(ROOT, self.out / "a", self.out / "b", replace=operation)
        operation.assert_called_once()

    def test_invalid_retry_budget_and_clock_fail(self):
        for seconds in (True, 0, -1, 3, float("nan"), float("inf")):
            with self.assertRaises(ValueError):
                io.replace_file(ROOT, self.out / "a", self.out / "b", seconds=seconds)
        clock = iter([2, 1])
        with self.assertRaises(PermissionError):
            io.replace_file(ROOT, self.out / "a", self.out / "b", replace=Mock(side_effect=windows_error(5)),
                            clock=lambda:next(clock), sleep=Mock())

    @unittest.skipUnless(os.name == "nt", "actual Windows file sharing")
    def test_real_windows_reader_lock_is_tolerated(self):
        path = io.write_json(ROOT, self.out / "state.json", {"seq":1})
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                      wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
        kernel.CreateFileW.restype = wintypes.HANDLE
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel.CloseHandle.restype = wintypes.BOOL
        handle = kernel.CreateFileW(str(path), 0x80000000, 3, None, 3, 0x80, None)
        self.assertNotEqual(handle, ctypes.c_void_p(-1).value)
        def release():
            time.sleep(.20)
            kernel.CloseHandle(handle)
        thread = threading.Thread(target=release)
        thread.start()
        started = time.monotonic()
        try:
            io.write_json(ROOT, path, {"seq":2}, replace=True)
        finally:
            thread.join(timeout=3)
        self.assertFalse(thread.is_alive())
        self.assertGreaterEqual(time.monotonic()-started, .15)
        self.assertEqual(json.loads(path.read_text()), {"seq":2})

    def test_skill_references_resolve_to_real_project_files(self):
        skill = Path(__file__).resolve().parents[1]
        for source in (skill / "SKILL.md", skill / "references/device-session.md",
                       ROOT / "docs/agent-collaboration-contract.md"):
            for target in re.findall(r"\]\(([^)]+)\)", source.read_text(encoding="utf-8")):
                self.assertNotIn("://", target)
                target = target.split("#", 1)[0]
                self.assertTrue(io.checked_output(ROOT, source.parent / target).is_file(), target)


def main():
    global ROOT, OUT
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    ROOT = args.root
    if not ROOT.is_absolute() or Path.cwd().resolve() != ROOT.resolve():
        raise ValueError("run with explicit cwd at the authorized absolute project root")
    OUT = io.checked_output(ROOT, args.out)
    io.checked_output(ROOT, OUT / "result.json")
    if OUT.exists():
        raise ValueError("fresh output directory required; preserve previous test evidence")
    OUT.mkdir(parents=True)
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(HostTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    io.write_json(ROOT, OUT / "result.json", dict(tests=result.testsRun,
                  failures=len(result.failures), errors=len(result.errors),
                  skipped=len(result.skipped), passed=result.wasSuccessful(),
                  platform=os.name, output_root=str(OUT), device_operations=0))
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
