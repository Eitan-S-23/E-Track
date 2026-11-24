import ctypes
import io
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
sys.path.insert(0, str(ROOT / "tests/boot"))
import test_p34_native_probe as native_tests
import test_p34_rendezvous as policy_tests
from recovery_entry import rendezvous as rv
from recovery_entry.control_probe import Control, DHCSR, DCRSR, DCRDR, PAUSE, COMP
from recovery_entry.dap_probe import Dap
from recovery_entry.state_probe import REGISTERS


class SDK(native_tests.SDK):
    def __init__(self):
        super().__init__()
        self.dp = 0x40
        self.memory = {REGISTERS[n]: v for n, v in policy_tests.media()["raw"].items()}
        self.memory.update({DHCSR: 0x10001, 0xe000ed00: 0x410fc241, 0xe000ed08: 0x08010000,
                            0xe0002000: 0x261, PAUSE: 4, 0x40002c00: 0x7f,
                            rv.WFI: int.from_bytes(rv.WFI_BYTES, "little")})
        self.core = {15: rv.WFI, 16: 0x01000000, 17: 0x20060000, 20: 0x04000000}
        self.wrapped = set()
    def __getattr__(self, name):
        func = super().__getattr__(name)
        if name not in self.wrapped:
            old = func.callback
            def invoke(*args):
                if name == "JLINKARM_CORESIGHT_ReadAPDPReg" and args[:2] == (3, 1) and self.bank == 0:
                    ctypes.cast(args[2], ctypes.POINTER(ctypes.c_uint32))[0] = self.memory.get(self.tar, 0)
                    self.tar += 4
                    return 0
                if name == "JLINKARM_CORESIGHT_WriteAPDPReg" and args[:2] == (3, 1):
                    address, value = self.tar, args[2]
                    self.memory[address] = value
                    self.tar += 4
                    if address == COMP and value == rv.WFI_COMPARATOR:
                        self.memory[DHCSR] |= 0x20000
                    if address == DCRSR:
                        self.memory[DCRDR] = self.core[value]
                    return 0
                return old(*args)
            func.callback = invoke
            self.wrapped.add(name)
        return func


class Observer:
    def __init__(self, dap): self.dap = dap
    def _call(self, operation, *args):
        if operation != "read": raise AssertionError(operation)
        return self.dap.read(*args)
    def emit(self, *args, **kwargs): pass
    def close(self): self.dap.close()


class ControlTests(unittest.TestCase):
    def setUp(self):
        self.sdk = SDK()
        self.dap = Dap(self.sdk, ROOT/".cache/fake.log", ROOT/".cache/fake.jlink", io.BytesIO())
        self.dap.open(); self.dap.connect()
        self.events = []
        self.ctrl = Control(self.dap, Observer(self.dap),
                            lambda e, **kw: self.events.append((e, kw)), bytes(96))

    def test_real_adapter_mocked_complete_path_and_retained_close(self):
        result = rv.acquire(self.ctrl, lambda *a, **k: None)
        self.assertEqual(result["result"], "APP_WFI_HALTED_RETAINED_NOT_RESET", result)
        self.assertEqual(result["context"]["control"], 4)
        self.ctrl.close()
        self.assertEqual(self.sdk.memory[PAUSE], 0x1004)
        self.assertTrue(self.dap.metadata["dp_restore_deferred_for_halt"])
        self.assertTrue(self.dap.metadata["tar_restored"])
        self.assertTrue(self.dap.metadata["csw_restored"])
        self.assertTrue(self.dap.close_returned)
        self.assertEqual(self.sdk.dp, 0xf0000040)
        writes = [kw for e, kw in self.events if e == "debug-write-attempt"]
        self.assertTrue(all(w["address"] in (PAUSE, COMP, DCRSR) for w in writes))
        self.assertTrue(all(w["value"] in (15, 16, 17, 20) for w in writes if w["address"] == DCRSR))
        self.assertEqual([w["value"] for w in writes if w["address"] == COMP], [rv.WFI_COMPARATOR, 0])

    def test_unmutated_close_restores_requests(self):
        self.ctrl.initial(); self.ctrl.close()
        self.assertTrue(self.dap.metadata["dp_restored"])
        self.assertEqual(self.sdk.dp, 0x40)

    def test_disallowed_writes_and_reads(self):
        for operation, value in (("reset", 0), ("resume", 1), ("selector", 0x1000f),
                                 ("selector", 0), ("pause", 0x1000), ("arm", rv.WFI_COMPARATOR)):
            with self.assertRaises(ValueError): self.ctrl._write(operation, value)
        for address in (0x20060000, 0xe000ed0c, 0x40003000, DCRSR):
            with self.assertRaises(ValueError): self.ctrl._read32(address)
        self.assertFalse(self.ctrl.mutation_attempted)

    def test_selector_requires_halt_and_ready(self):
        with self.assertRaises(ValueError): self.ctrl._core(15)
        self.sdk.memory[DHCSR] = 0x20001
        with self.assertRaisesRegex(ValueError, "ready timeout"): self.ctrl._core(15)
        self.assertNotIn("control-word", [e for e, kw in self.events if kw.get("address") == DCRDR])

    def test_reset_sticky_is_accumulated_not_cleared_by_later_read(self):
        self.sdk.memory[DHCSR] |= 0x02000000
        self.assertTrue(self.ctrl.status()["reset_sticky"])
        self.sdk.memory[DHCSR] &= ~0x02000000
        self.assertTrue(self.ctrl.status()["reset_sticky"])

    def test_unknown_live_header_rejected_before_debug_mutation(self):
        self.sdk.memory[0x08010400] = 123
        result = rv.acquire(self.ctrl, lambda *a, **k: None)
        self.assertEqual(result["result"], "FAILED")
        self.assertFalse(self.ctrl.mutation_attempted)

    def test_failed_data_write_is_never_retried(self):
        self.ctrl.initial()
        old = self.sdk.JLINKARM_CORESIGHT_WriteAPDPReg.callback
        def fail(*args):
            if args[:2] == (3, 1): return -1
            return old(*args)
        self.sdk.JLINKARM_CORESIGHT_WriteAPDPReg.callback = fail
        with self.assertRaises(ValueError): self.ctrl.set_halt_pause(0x1004)
        with self.assertRaises(ValueError): self.ctrl.set_halt_pause(0x1004)
        self.assertEqual(sum(n == "JLINKARM_CORESIGHT_WriteAPDPReg" and a[:2] == (3, 1)
                             for n, a in self.sdk.calls), 1)

    def test_failed_retention_read_still_closes_without_dropping_requests(self):
        self.ctrl.initial(); self.ctrl.set_halt_pause(0x1004)
        def fail(): raise OSError("read failed")
        self.dap._power_ready = fail
        with self.assertRaises(OSError): self.ctrl.close()
        self.assertTrue(self.dap.close_returned)
        self.assertEqual(self.sdk.dp, 0xf0000040)

    def test_retained_observation_has_only_core_read_selectors(self):
        previous = rv.acquire(self.ctrl, lambda *a, **k: None)
        previous["close_returned"] = True
        observer = Control(self.dap, Observer(self.dap),
                           lambda e, **kw: self.events.append((e, kw)), bytes(96))
        self.events.clear()
        result = observer.observe_retained(previous)
        self.assertEqual(result["result"], "APP_WFI_RETAINED_AFTER_RECONNECT")
        self.assertTrue(all(kw["operation"] == "selector" for e, kw in self.events if e == "debug-write-attempt"))
        self.sdk.memory[DHCSR] &= ~0x20000
        with self.assertRaisesRegex(ValueError, "not retained"): observer.observe_retained(previous)

    def test_close_reopen_observe_close_including_early_mismatch(self):
        for mismatch in (False, True):
            self.setUp()
            previous = rv.acquire(self.ctrl, lambda *a, **k: None)
            self.ctrl.close()
            previous["close_returned"] = self.dap.close_returned
            # Also model a reconnect that must reacquire logical requests.
            self.sdk.dp = 0x40
            new_dap = Dap(self.sdk, ROOT/".cache/fake.log", ROOT/".cache/fake.jlink", io.BytesIO())
            observer = Control(new_dap, Observer(new_dap), lambda *a, **k: None, bytes(96), retained=True)
            new_dap.open(); new_dap.connect()
            if mismatch:
                self.sdk.memory[COMP] = 1
                with self.assertRaisesRegex(ValueError, "configuration changed"):
                    observer.observe_retained(previous)
                self.assertFalse(observer.mutation_attempted)
            else:
                self.assertEqual(observer.observe_retained(previous)["result"], "APP_WFI_RETAINED_AFTER_RECONNECT")
            observer.close()
            self.assertTrue(new_dap.close_returned)
            self.assertTrue(new_dap.metadata["dp_restore_deferred_for_halt"])
            self.assertEqual(self.sdk.dp, 0xf0000040)
            self.assertTrue(self.sdk.memory[DHCSR] & 0x20000)


def load_tests(loader, tests, pattern):
    tests.addTests(loader.loadTestsFromModule(policy_tests))
    return tests


if __name__ == "__main__":
    unittest.main()
