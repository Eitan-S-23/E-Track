from pathlib import Path
import struct
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
from recovery_entry.probe import BEFORE_CONNECT, BEFORE_OPEN, Observation, read_allowed, scan_sdk_writes


class Backend:
    def __init__(self):
        self.calls = []
        self.fail = None
        self.error = ""
        self.auto = self.did_connect = False
        self.cache = 1
        self.restart, self.inhibit = 1, 0
        self.read_result = None

    def call(self, name, *args):
        self.calls.append((name, *args))
        if self.fail == name:
            raise OSError(name)

    def command(self, text):
        self.call("command", text)
        if self.fail == text:
            return -1, self.error
        if text == "SetEnableMemCache = 0":
            previous, self.cache = self.cache, 0
            return previous, self.error
        if text == "SetRestartOnClose = 0":
            previous, self.restart = self.restart, 0
            return previous, self.error
        if text == "InhibitConnectRetries = 1":
            previous, self.inhibit = self.inhibit, 1
            return previous, self.error
        return 0, self.error

    def select(self, serial): self.call("select", serial); return 0
    def open(self): self.call("open"); return None
    def connected(self): self.call("connected"); return int(self.auto or self.did_connect)
    def interface(self, value): self.call("interface", value); return 0
    def speed(self, value): self.call("speed", value)
    def connect(self): self.call("connect"); self.did_connect = True; return 0
    def close(self): self.call("close")

    def read(self, address, size):
        self.call("read", address, size)
        return self.read_result if self.read_result is not None else bytes(size)


class Probe(unittest.TestCase):
    def setUp(self):
        self.backend, self.events = Backend(), []
        self.probe = Observation(self.backend, lambda event, **data: self.events.append((event, data)))

    def test_order_and_no_power_commands(self):
        self.probe.connect()
        calls = self.backend.calls
        opened, connected = calls.index(("open",)), calls.index(("connect",))
        self.assertTrue(all(calls.index(("command", c)) < opened for c in BEFORE_OPEN))
        self.assertTrue(all(("command", c) in calls[opened:connected] for c in BEFORE_CONNECT))
        self.assertEqual([c for c in calls if c[0] == "speed"], [("speed", 1000)])
        self.assertFalse(any("power" in str(c).lower() for c in calls))
        self.assertFalse(hasattr(self.probe, "write"))
        self.probe.close()
        self.probe.close()
        self.assertEqual(calls.count(("close",)), 1)
        with self.assertRaisesRegex(ValueError, "consumed"): self.probe.connect()

    def test_every_configuration_failure_stops_before_connect(self):
        for command in (*BEFORE_OPEN, *BEFORE_CONNECT, "SetEnableMemCache = 0", "InvalidateCache"):
            with self.subTest(command=command):
                self.setUp()
                self.backend.fail = command
                with self.assertRaises(ValueError): self.probe.connect()
                self.assertNotIn(("connect",), self.backend.calls)
                self.assertEqual(self.backend.calls.count(("close",)), int(self.probe.open_attempted))
                with self.assertRaisesRegex(ValueError, "consumed"): self.probe.connect()

    def test_error_message_with_zero_result_rejected(self):
        self.backend.error = "unsupported"
        with self.assertRaisesRegex(ValueError, "setting rejected"): self.probe.connect()
        self.assertNotIn(("open",), self.backend.calls)

    def test_partial_open_closed_without_resume(self):
        self.backend.fail = "open"
        with self.assertRaises(OSError): self.probe.connect()
        self.assertEqual(self.backend.calls[-1], ("close",))
        self.assertNotIn(("connect",), self.backend.calls)

    def test_unexpected_autoconnect(self):
        self.backend.auto = True
        with self.assertRaisesRegex(ValueError, "auto-connect"): self.probe.connect()
        self.assertEqual(self.backend.calls[-1], ("close",))
        self.assertNotIn(("connect",), self.backend.calls)

    def test_connection_failure_no_retry(self):
        self.backend.fail = "connect"
        with self.assertRaises(OSError): self.probe.connect()
        self.assertEqual(self.backend.calls.count(("connect",)), 1)
        self.assertEqual(self.backend.calls.count(("close",)), 1)

    def test_cache_previous_value_not_generic_success(self):
        self.backend.cache = 2
        with self.assertRaisesRegex(ValueError, "setting rejected"): self.probe.connect()
        self.assertNotIn(("connect",), self.backend.calls)

    def test_read_scope(self):
        for args in [(0x08000000, 4096), (0x0800fffc, 4), (0xE0001000, 8)]:
            self.assertTrue(read_allowed(*args))
        for args in [(True, 4), (0x08000000, True), (0x08000000, 0),
                     (0x08000000, 4097), (0x0800fffc, 8), (0x08000001, 4),
                     (0xE0001000, 4), (0xE0001004, 4), (0x20060000, 4),
                     (0x40020410, 4), (-1, 4), (0xffffffff, 4)]:
            self.assertFalse(read_allowed(*args))
        self.probe.connect()
        with self.assertRaisesRegex(ValueError, "allowlist"): self.probe.read(0x20060000, 4)
        self.assertFalse(any(c[0] == "read" for c in self.backend.calls))
        self.probe.close()

    def test_dhcsr_reset_sticky_is_retained_not_discarded(self):
        self.probe.connect()
        original = self.backend.read
        self.backend.read = lambda a, n: struct.pack("<I", (1 << 25) | (1 << 17)) if a == 0xE000EDF0 else original(a, n)
        sample = self.probe.sample()
        self.assertTrue(sample["reset_sticky_observed"])
        self.assertTrue(sample["halted"])
        self.assertFalse(sample["pre_attach_values_known"])
        self.assertFalse(sample["device_execute_ready"])
        self.assertIn(("read", 0xE0001000, 8), self.backend.calls)
        self.probe.close()

    def test_read_failure_closes_once(self):
        for fail, value in [("read", None), (None, b"short")]:
            self.setUp()
            self.probe.connect()
            self.backend.fail, self.backend.read_result = fail, value
            with self.assertRaises((ValueError, OSError)): self.probe.read(0x08000000, 16)
            self.probe.close()
            self.assertEqual(self.backend.calls.count(("close",)), 1)

    def test_deadline_before_and_after_call(self):
        for delta in [-1, 30]:
            self.setUp()
            now = [0]
            self.probe.clock = lambda: now[0]
            self.probe.connect()
            now[0] = delta
            with self.assertRaisesRegex(ValueError, "deadline"): self.probe.read(0x08000000, 16)
            self.assertFalse(any(c[0] == "read" for c in self.backend.calls))
            self.assertEqual(self.backend.calls.count(("close",)), 1)
        self.setUp()
        now = [0]
        self.probe.clock = lambda: now[0]
        self.probe.connect()
        def late(address, size): now[0] = 31; return bytes(size)
        self.backend.read = late
        with self.assertRaisesRegex(ValueError, "deadline"): self.probe.read(0x08000000, 16)
        self.assertTrue(self.probe.closed)

    def test_close_failure_does_not_retry(self):
        self.probe.connect()
        self.backend.fail = "close"
        with self.assertRaises(OSError): self.probe.close()
        self.probe.close()
        self.assertEqual(self.backend.calls.count(("close",)), 1)
        with self.assertRaises(ValueError): self.probe.read(0x08000000, 4)

    def test_failed_evidence_sink_still_closes(self):
        self.probe.connect()
        def broken(*args, **kwargs): raise OSError("evidence sink")
        self.probe.emit = broken
        with self.assertRaises(OSError): self.probe.read(0x08000000, 4)
        self.assertEqual(self.backend.calls.count(("close",)), 1)
        self.probe.close()
        self.assertEqual(self.backend.calls.count(("close",)), 1)

    def test_invalid_native_statuses(self):
        for name in ["select", "connected", "interface", "connect"]:
            for value in [True, None, -1, 2]:
                with self.subTest(name=name, value=value):
                    self.setUp()
                    setattr(self.backend, name, lambda *args, value=value: value)
                    with self.assertRaises(ValueError): self.probe.connect()
                    self.assertFalse(self.probe.connected)
                    self.assertEqual(self.backend.calls.count(("close",)), int(self.probe.open_attempted))

    def test_invalid_deadlines(self):
        for value in [True, 0, -1, 601, float("nan"), float("inf")]:
            with self.assertRaises(ValueError): Observation(self.backend, lambda *a: None, seconds=value)

    def test_historical_writes_never_become_proof(self):
        paths = sorted((ROOT / ".cache/p34-early-identity1").glob("*/sdk.log"))
        self.assertEqual(len(paths), 5)
        count = 0
        for path in paths:
            result = scan_sdk_writes(path.read_text(errors="strict"))
            count += len(result["writes"])
            self.assertFalse(result["sdk_write_audit_passed"])
            self.assertFalse(result["transient_debug_state_proven_unchanged"])
            self.assertTrue(all(not w["values_known"] for w in result["writes"]))
        self.assertEqual(count, 23)

    def test_unknown_or_empty_log_not_green(self):
        for value in ["", "CPU_WriteMem(4 bytes @ 0xE0001000)\nDATA = 00000001",
                      "CPU_WriteMem(broken)", "JLINKARM_WriteMem(0x20000000, 4)",
                      "CPU_WriteMem(4 bytes @ 0xFFFFFFFFFFFFFFFF)"]:
            result = scan_sdk_writes(value)
            self.assertFalse(result["sdk_write_audit_passed"])
            self.assertFalse(result["device_execute_ready"])
        self.assertTrue(scan_sdk_writes("CPU_WriteMem(broken)")["unknown_write_lines"])


if __name__ == "__main__":
    unittest.main()
