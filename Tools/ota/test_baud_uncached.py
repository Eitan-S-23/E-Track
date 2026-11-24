"""Exercise the real clock guard with a cached and uncached fake SDK link."""
import io
import os
from pathlib import Path
import runpy
import struct
import sys
import types
import unittest

ROOT = Path(__file__).resolve().parents[2]
helper = runpy.run_path(str(Path(__file__).with_name("baud_uncached.py")), run_name="tested_uncached")
r = helper["runtime"]()
OUT = r.b.checked(r.b.OUT / "host-tests-uncached-004")


class FakeLink:
    def __init__(self):
        self.calls, self.ram_reads = [], []
        self.e = types.SimpleNamespace(emit=lambda kind, **kwargs: self.calls.append("evidence")
                                      if kind == "host-memory-cache-disabled" else None)
        self.cached, self.frozen = True, False
        self.demcr, self.ctrl, self.count = 1 << 24, 1, 100
        self.reject = None
        self.sdk = types.SimpleNamespace(JLINKARM_ExecCommand=self.exec_cache)
        self.forced_result = None
        self.raw_reads = []

    def exec_cache(self, encoded, error, length):
        command = encoded.decode("ascii")
        self.calls.append(command)
        if command == self.reject:
            error.value = b"unsupported command"
            return -1
        if self.forced_result is not None:
            return self.forced_result
        previous = int(self.cached)
        self.cached = False
        return previous

    def connect(self):
        self.calls.append("connect")

    def command(self, command):
        self.calls.append(command)
        if command == self.reject:
            raise RuntimeError("unsupported cache command")

    def running(self):
        return None

    def read(self, address, size):
        self.raw_reads.append((address, size))
        if address == r.m.DWT_CTRL and size == 8:
            if not self.frozen:
                self.count += 1000
            return struct.pack("<II", self.ctrl, self.count)
        if address == r.m.DEMCR:
            value = self.demcr
        elif address == r.m.DWT_CTRL:
            value = self.ctrl
        elif address == r.m.DWT_COUNT:
            value = self.count
        else:
            raise AssertionError("unexpected read")
        return struct.pack("<I", value)


def reader(link):
    value = r.m.ImageReader(link, {})
    value.profile = dict(symbols=dict(profile=0x20000000))
    value.gate = types.SimpleNamespace(ready=True, epoch=1)
    return value


class CacheTests(unittest.TestCase):
    def linked(self):
        link = helper["uncached_link"](FakeLink, lambda: dict(fixture=True))()
        link.connect()
        return link

    def test_original_cached_counter_reproduces_false_freeze(self):
        link = FakeLink()
        link.connect()
        with self.assertRaisesRegex(RuntimeError, "DWT disabled/frozen"):
            reader(link).check_dwt()

    def test_uncached_counter_passes_unchanged_real_guard(self):
        link = self.linked()
        value = reader(link).check_dwt()
        self.assertGreater(value["after"][2], value["before"][2])
        self.assertEqual([size for address, size in link.raw_reads if address == r.m.DWT_CTRL], [8, 8, 8, 8])
        self.assertEqual(link.calls, ["connect", "SetEnableMemCache = 0", "SetEnableMemCache = 0",
                                     "InvalidateCache", "evidence"])

    def test_real_frozen_counter_still_fails(self):
        link = self.linked()
        link.frozen = True
        with self.assertRaisesRegex(RuntimeError, "DWT disabled/frozen"):
            reader(link).check_dwt()

    def test_disabled_clock_bits_still_fail(self):
        for name in ("demcr", "ctrl"):
            link = self.linked()
            setattr(link, name, 0)
            with self.subTest(name=name), self.assertRaisesRegex(RuntimeError, "DWT disabled/frozen"):
                reader(link).check_dwt()

    def test_cache_command_failure_propagates(self):
        for command in ("SetEnableMemCache = 0", "InvalidateCache"):
            link = helper["uncached_link"](FakeLink, lambda: {})()
            link.reject = command
            with self.subTest(command=command), self.assertRaises(RuntimeError):
                link.connect()
            self.assertNotIn("evidence", link.calls)

    def test_capture_and_tuning_classes_both_use_adapter(self):
        tune = r.load("uncached_class_test", ROOT / "Tools/ota/baud_tune.py")
        for cls in (r.m.BoundLink, tune.ControlLink):
            self.assertEqual(cls.__name__, "UncachedLink")
            self.assertIn("disable_cache", cls.connect.__code__.co_names)

    def test_non_boolean_return_is_not_accepted(self):
        for code in (-1, 2):
            link = helper["uncached_link"](FakeLink, lambda: {})()
            link.forced_result = code
            with self.subTest(code=code), self.assertRaises(RuntimeError):
                link.connect()
            self.assertNotIn("evidence", link.calls)

    def test_unchanged_enabled_state_is_not_accepted(self):
        link = helper["uncached_link"](FakeLink, lambda: {})()
        link.forced_result = 1
        with self.assertRaises(RuntimeError):
            link.connect()
        self.assertNotIn("evidence", link.calls)

    def test_scalar_cache_survives_memory_cache_setting(self):
        link = FakeLink()
        helper["disable_cache"](link)
        self.assertFalse(link.cached)
        with self.assertRaisesRegex(RuntimeError, "DWT disabled/frozen"):
            reader(link).check_dwt()

    def test_block_adapter_cannot_expand_an_unadmitted_request(self):
        link = self.linked()
        with self.assertRaisesRegex(RuntimeError, "admitted read scope"):
            link.read(r.m.DWT_COUNT, 4)


class PresenceTests(unittest.TestCase):
    def test_exact_usb_and_non_debugger_processes(self):
        usb = ["USB\\VID_1366&PID_0101\\000000123456"]
        value = helper["validate_presence"](usb, [("python.exe", "1"), ("adb.exe", "2")])
        self.assertEqual(value["debugger_processes"], [])
        for bad in ([], usb + usb, ["USB\\VID_1366&PID_0101\\other"]):
            with self.subTest(usb=bad), self.assertRaises(RuntimeError):
                helper["validate_presence"](bad, [])

    def test_all_original_debugger_filters_remain_blocking(self):
        usb = ["USB\\VID_1366&PID_0101\\000000123456"]
        for name in ("JLinkRTTViewer.exe", "openocd.exe", "UV4.exe", "arm-none-eabi-gdb.exe"):
            with self.subTest(name=name), self.assertRaises(RuntimeError):
                helper["validate_presence"](usb, [(name, "123")])

    def test_actual_native_inventory_finds_this_process(self):
        processes = helper["process_inventory"]()
        self.assertTrue(any(pid == str(os.getpid()) for _, pid in processes))


if __name__ == "__main__":
    r.b.require(Path.cwd().resolve() == ROOT and sys.flags.isolated and sys.flags.no_site and
                sys.dont_write_bytecode, "isolated explicit root required")
    r.b.require(not OUT.exists(), "preserve previous test receipt")
    r.b.checked(OUT / "result.json")
    output = io.StringIO()
    result = unittest.TextTestRunner(stream=output, verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__]))
    r.save(OUT / "result.json", dict(passed=result.wasSuccessful(), tests=result.testsRun,
        failures=len(result.failures), errors=len(result.errors), output=output.getvalue(), hardware=False,
        source=r.b.record(Path(__file__).with_name("baud_uncached.py")), test_source=r.b.record(Path(__file__)),
        runtime_sources=r.sources()))
    print(output.getvalue(), flush=True)
    raise SystemExit(0 if result.wasSuccessful() else 1)
