import copy
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
from recovery_entry import rendezvous as rv
from recovery_entry.state_probe import REGISTERS, decode


def media():
    raw = dict.fromkeys(REGISTERS, 0)
    raw.update(sd_data_cache_owner=0x20052de0, sd_fat_cache_owner=0x20052de0,
               sd_ready_mirror=1, gpioc_input=1, sdio2_cmd=0x44d,
               sdio2_rspcmd=13, sdio2_rsp1=0x900, gpiob_input=0xc0, gpiob_output=0xc0)
    return decode(raw, bytes(96))


class Transport:
    def __init__(self):
        self.calls = []
        self.before = dict(wfi_bytes=rv.WFI_BYTES.hex(), vtor=0x08010000, halted=False,
                           lockup=False, reset_sticky=False, fp_ctrl=0x261,
                           comparators=[0]*6, dhcsr_control=1, wwdt_ctrl=0x7f, debug_apb1_frz=4)
        self.ctx = dict(halted=True, pc=rv.WFI, xpsr=0x01000000, control=0,
                        vtor=0x08010000, lockup=False, reset_sticky=False)
        self.pause, self.comp = 4, 0
        self.state = media()
        self.fail = None
        self.tick = 0
    def call(self, name):
        self.calls.append(name)
        if name == self.fail: raise OSError("injected " + name)
    def initial(self): self.call("initial"); return copy.deepcopy(self.before)
    def set_halt_pause(self, value): self.call("set_halt_pause"); self.pause = value
    def read_halt_pause(self): self.call("read_halt_pause"); return self.pause
    def arm_wfi(self): self.call("arm_wfi"); self.comp = rv.WFI_COMPARATOR
    def read_comparator(self): self.call("read_comparator"); return self.comp
    def disarm_wfi(self): self.call("disarm_wfi"); self.comp = 0
    def status(self): self.call("status"); return dict(halted=True, lockup=False, reset_sticky=False)
    def context(self): self.call("context"); return dict(self.ctx)
    def media(self): self.call("media"); return copy.deepcopy(self.state)
    def clock(self): self.tick += .001; return self.tick


class RendezvousTests(unittest.TestCase):
    def run_case(self, t):
        self.events = []
        return rv.acquire(t, lambda e, **kw: self.events.append((e, kw)), clock=t.clock, sleep=lambda _: None)

    def test_success_pauses_before_breakpoint_and_never_resumes(self):
        t = Transport()
        result = self.run_case(t)
        self.assertEqual(result["result"], "APP_WFI_HALTED_RETAINED_NOT_RESET")
        self.assertLess(t.calls.index("read_halt_pause"), t.calls.index("arm_wfi"))
        self.assertEqual((t.pause, t.comp), (0x1004, 0))
        self.assertFalse(result["media"]["media_safe_reset_proven"])
        self.assertFalse(result["device_execute_ready"])

    def test_initial_rejections_have_no_mutations(self):
        for name, value in (("wfi_bytes", "00000000"), ("vtor", 0x08000000),
                            ("halted", True), ("lockup", True), ("reset_sticky", True),
                            ("fp_ctrl", 0x260), ("comparators", [1]*6),
                            ("dhcsr_control", 3), ("wwdt_ctrl", 0xff)):
            with self.subTest(name=name):
                t = Transport(); t.before[name] = value
                result = self.run_case(t)
                self.assertEqual(result["result"], "FAILED")
                self.assertFalse(result["mutation_attempted"])
                self.assertEqual(t.calls, ["initial"])

    def test_failed_pause_never_arms_breakpoint(self):
        for point in ("set_halt_pause", "read_halt_pause"):
            t = Transport(); t.fail = point
            result = self.run_case(t)
            self.assertNotIn("arm_wfi", t.calls)
            self.assertFalse(result["pause_verified"])

    def test_wrong_pause_readback_never_arms(self):
        t = Transport(); t.read_halt_pause = lambda: 0
        self.assertEqual(self.run_case(t)["result"], "FAILED")
        self.assertNotIn("arm_wfi", t.calls)

    def test_all_post_arm_failures_retain_without_cleanup(self):
        for point in ("arm_wfi", "read_comparator", "status", "context", "disarm_wfi", "media"):
            t = Transport(); t.fail = point
            result = self.run_case(t)
            self.assertEqual(result["result"], "FAILED")
            self.assertTrue(result["breakpoint_attempted"])
            self.assertEqual(t.pause, 0x1004)
            self.assertFalse(result["automatic_resume"])
            self.assertFalse(result["reset_performed"])

    def test_wrong_pc_exception_or_unprivileged_context_retained(self):
        for key, value in (("pc", rv.WFI+2), ("xpsr", 0x0100000f),
                           ("xpsr", 0), ("control", 1), ("lockup", True), ("reset_sticky", True)):
            t = Transport(); t.ctx[key] = value
            self.assertEqual(self.run_case(t)["result"], "FAILED")
            self.assertNotIn("disarm_wfi", t.calls)
            self.assertEqual(t.pause, 0x1004)

    def test_timeout_no_reset_or_resume(self):
        t = Transport()
        t.status = lambda: dict(halted=False, lockup=False, reset_sticky=False)
        result = rv.acquire(t, lambda *a, **k: None, seconds=.02, clock=t.clock, sleep=lambda _: None)
        self.assertEqual(result["result"], "FAILED")
        self.assertIn("deadline", result["error"])
        self.assertTrue(result["pause_verified"])

    def test_first_halted_sample_reset_is_not_lost_in_context(self):
        for fault in ("reset_sticky", "lockup"):
            t = Transport()
            status = dict(halted=True, reset_sticky=False, lockup=False)
            status[fault] = True
            t.status = lambda: status
            result = self.run_case(t)
            self.assertEqual(result["result"], "FAILED")
            self.assertNotIn("context", t.calls)
            self.assertFalse(result["automatic_resume"])

    def test_late_media_or_final_context_cannot_report_success(self):
        for operation, late_call in (("media", 2), ("context", 2)):
            t = Transport()
            original = getattr(t, operation)
            calls = [0]
            def delayed():
                calls[0] += 1
                value = original()
                if calls[0] == late_call:
                    t.tick += 20
                return value
            setattr(t, operation, delayed)
            result = self.run_case(t)
            self.assertEqual(result["result"], "FAILED")
            self.assertIn("deadline", result["error"])
            self.assertFalse(any(e == "halt-retained" for e, fields in self.events))

    def test_cache_flags_are_fail_closed_and_mirror_not_dirty(self):
        for value, expected in ((0, []), (2, []), (1, ["dirty_cache"]),
                                (4, ["unknown_cache_status"])):
            t = Transport(); t.state["raw"]["sd_fat_cache_status"] = value
            result = self.run_case(t)
            self.assertEqual(result["media"]["observed_blockers"], expected)
            self.assertFalse(result["media"]["media_safe_reset_proven"])

    def test_other_media_blockers_not_hidden_by_successful_halt(self):
        for name, value, blocker in (("recorder_file_handle_present", True, "recorder_active_or_open"),
                                     ("sd_transfer_error", 1, "sd_error_or_stop"),
                                     ("sd_data0_sampled_high", False, "sd_not_ready"),
                                     ("ble_state", 1, "ota_owner")):
            t = Transport(); t.state[name] = value
            result = self.run_case(t)
            self.assertIn(blocker, result["media"]["observed_blockers"])
            self.assertEqual(result["result"], "APP_WFI_HALTED_RETAINED_NOT_RESET")

    def test_cmd13_r1_error_bits_rejected(self):
        t = Transport(); t.state["raw"]["sdio2_rsp1"] = 0x80000900
        self.assertIn("sd_command_or_transfer", self.run_case(t)["media"]["observed_blockers"])


if __name__ == "__main__":
    unittest.main()
