import ctypes
import io
import json
import struct
import zlib
import os
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
sys.path.insert(0, str(ROOT / "tests/boot"))
from test_p34_entry_probe import Probe
from recovery_entry.native_probe import Native
from recovery_entry.dap_probe import Dap, WORDS
from recovery_entry.probe import Observation
import p34_probe_acquire as acquire


class Function:
    def __init__(self, name, calls, callback):
        self.name, self.calls, self.callback = name, calls, callback
    def __call__(self, *args):
        self.calls.append((self.name, args))
        return self.callback(*args)


class SDK:
    def __init__(self):
        self.calls, self.bound = [], {}
        self.short = False
        self.serial = 123456
        self.bank, self.tar, self.csw, self.dp = 0, 0x12345678, 0x23000052, 0xf0000000
    def __getattr__(self, name):
        def invoke(*args):
            if name == "JLINKARM_CORESIGHT_WriteAPDPReg":
                index, ap, value = args
                if (ap, index) == (0, 2): self.bank = value
                elif (ap, index) == (1, 1): self.tar = value
                elif (ap, index) == (1, 0): self.csw = value
                elif (ap, index) == (0, 1):
                    self.dp = value | ((value & 0x50000000) << 1)
                else: raise AssertionError("unexpected DAP write")
                return 0
            if name == "JLINKARM_CORESIGHT_ReadAPDPReg":
                index, ap, pointer = args
                if (ap, index) == (0, 0): value = 0x2ba01477
                elif (ap, index) == (0, 1): value = self.dp
                elif (ap, index) == (1, 0): value = self.csw
                elif (ap, index) == (1, 1): value = self.tar
                elif (ap, index) == (1, 3) and self.bank == 0xf0: value = 0x24770011
                elif (ap, index) == (1, 3): value = self.tar; self.tar += 4
                else: raise AssertionError("unexpected DAP read")
                ctypes.cast(pointer, ctypes.POINTER(ctypes.c_uint32))[0] = value
                return 0
            if name == "JLINKARM_ReadMemEx":
                ctypes.memmove(args[2], b"x" * args[1], args[1])
                return args[1] - int(self.short)
            if name == "JLINKARM_EMU_GetList":
                args[1][0].SerialNumber, args[1][0].Connection = self.serial, 1
                return 1
            if name == "JLINKARM_OpenEx": return None
            if name == "JLINKARM_GetSN": return self.serial
            return 0
        if name not in self.bound: self.bound[name] = Function(name, self.calls, invoke)
        return self.bound[name]


class NativeTests(unittest.TestCase):
    def setUp(self):
        self.sdk = SDK()
        self.backend = Native(self.sdk, ROOT / ".cache/fake.log", ROOT / ".cache/fake.jlink", io.BytesIO())

    def test_no_mutator_binding(self):
        self.assertFalse(any(part in name for name in self.sdk.bound
            for part in ("Write", "Reset", "Halt", "Go", "Power", "Download")))
        self.assertEqual(self.sdk.bound["JLINKARM_ReadMemEx"].restype, ctypes.c_int)
        for command in ("DisablePowerSupplyOnClose", "Device = AT32F435RGT7", "SetRestartOnClose = 1"):
            with self.assertRaises(ValueError): self.backend.command(command)

    def test_version_bound_setting_responses(self):
        from recovery_entry.probe import PREVIOUS_VALUE_COMMANDS
        data = json.loads((ROOT / ".cache/p34-native-settings2/worker.json").read_text())
        plan = json.loads((ROOT / ".cache/p34-native-settings2/plan.json").read_text())
        self.assertEqual(plan["dll"]["sha256"], acquire.DLL_SHA)
        self.assertFalse(data["probe_open_attempted"])
        responses = {}
        for item in data["responses"]:
            self.assertEqual(item["message"], "")
            responses.setdefault(item["command"], []).append(item["result"])
        for command, desired in PREVIOUS_VALUE_COMMANDS.items():
            self.assertEqual(responses[command], [1-desired, desired])

    def test_exact_usb_binding(self):
        self.assertEqual(self.backend.select(123456), 0)
        self.sdk.serial = 654321
        with self.assertRaises(ValueError): self.backend.select(123456)
        with self.assertRaises(ValueError): self.backend.select(654321)

    def test_read_and_short_read(self):
        self.assertEqual(self.backend.read(0x08000000, 16), b"x" * 16)
        self.sdk.short = True
        with self.assertRaises(ValueError): self.backend.read(0x08000000, 16)
        with self.assertRaises(ValueError): self.backend.read(0x20060000, 16)

    def test_close_receipt_survives_callback_failure(self):
        self.backend.open()
        self.backend.callback_error = OSError("log failure")
        with self.assertRaises(ValueError): self.backend.read(0x08000000, 16)
        self.backend.close()
        self.assertTrue(self.backend.close_returned)
        self.backend.close()
        self.assertEqual(sum(name == "JLINKARM_Close" for name, _ in self.sdk.calls), 1)

    def test_failed_close_stays_uncertain(self):
        self.backend.open()
        def fail(): raise OSError("close failure")
        self.sdk.JLINKARM_Close.callback = fail
        with self.assertRaises(OSError): self.backend.close()
        self.backend.close()
        self.assertFalse(self.backend.close_returned)

    def test_owned_workers_and_native_timeout(self):
        store = acquire.cli.Store(ROOT)
        base = store.checked(Path(os.environ["P34_TEST_OUT"]))
        for mode, expected in [("ok", 0), ("hang", 124)]:
            out = store.checked(base / ("case-" + mode))
            out.mkdir()
            env = acquire.host.environment(store, out)
            result = acquire.owned_run(store, out, [acquire.SELF, "fixture-" + mode, "--output-dir", out], env, timeout=5)
            store.write(out / "result.json", result)
            self.assertEqual(result["exit"], expected)
            self.assertFalse(result["timeout"])
            self.assertTrue(result["worker_released"])
            text = (out / "worker.log").read_text()
            self.assertIn("OWNED_FIXTURE_PASS" if mode == "ok" else "NATIVE_CALL_TIMEOUT", text)


class DapTests(unittest.TestCase):
    def setUp(self):
        self.sdk = SDK()
        self.backend = Dap(self.sdk, ROOT / ".cache/fake.log", ROOT / ".cache/fake.jlink", io.BytesIO())
        self.backend.open()

    def test_only_select_tar_writes_and_restore(self):
        original = self.sdk.tar
        self.backend.connect()
        self.assertEqual(self.backend.read(0x08000000, 16), b"".join(a.to_bytes(4, "little") for a in range(0x08000000, 0x08000010, 4)))
        self.backend.close()
        self.assertTrue(self.backend.close_returned)
        self.assertTrue(self.backend.metadata["tar_restored"])
        self.assertEqual(self.sdk.tar, original)
        for name, args in self.sdk.calls:
            self.assertNotIn(name, ("JLINKARM_Connect", "JLINKARM_ReadMemEx", "JLINKARM_WriteMem"))
            if name == "JLINKARM_CORESIGHT_WriteAPDPReg":
                self.assertTrue(args[:2] in [(2, 0), (0, 1)] or (args[:2] == (1, 1) and args[2] in WORDS | {original}))

    def test_reject_memory_writes_and_extra_reads(self):
        self.backend.connect()
        for args in [(3, 1, 0), (0, 1, 2), (1, 0, 0x54000000), (1, 1, 0x20060000)]:
            with self.assertRaises(ValueError): self.backend._write_reg(*args)
        for args in [(0x20060000, 4), (0x08000000, 20), (0x08000001, 4)]:
            with self.assertRaises(ValueError): self.backend.read(*args)
        self.backend.close()

    def test_no_sticky_error_reset_or_active_transfer_repair(self):
        for name, value in [("dp", 0x04000040), ("dp", 0xf0000020), ("csw", 0x230000d2)]:
            self.setUp()
            setattr(self.sdk, name, value)
            with self.assertRaises(ValueError): self.backend.connect()
            self.backend.close()
            self.assertFalse(any(n == "JLINKARM_CORESIGHT_WriteAPDPReg" and a[:2] not in [(2, 0)]
                                 for n, a in self.sdk.calls))

    def test_scoped_debug_power_request_and_restore(self):
        self.sdk.dp, self.sdk.csw = 0x40, 0x23000040
        self.backend.connect()
        self.backend.read(0x08000000, 4)
        self.backend.close()
        self.assertEqual(self.sdk.dp, 0x40)
        self.assertEqual(self.sdk.csw, 0x23000040)
        self.assertTrue(self.backend.metadata["dp_restored"])
        self.assertTrue(self.backend.metadata["csw_restored"])
        writes = [a[2] for n, a in self.sdk.calls if n == "JLINKARM_CORESIGHT_WriteAPDPReg" and a[:2] == (1, 0)]
        self.assertEqual(writes, [0x50000040, 0x10000040, 0x40])

    def test_power_handshake_is_bounded(self):
        self.sdk.dp = 0x40
        original = self.sdk.JLINKARM_CORESIGHT_WriteAPDPReg.callback
        def no_ack(*args):
            value = original(*args)
            self.sdk.dp &= ~0xa0000000
            return value
        self.sdk.JLINKARM_CORESIGHT_WriteAPDPReg.callback = no_ack
        with self.assertRaisesRegex(ValueError, "handshake exhausted"): self.backend.connect()
        with self.assertRaisesRegex(ValueError, "handshake exhausted"): self.backend.close()
        self.assertTrue(self.backend.close_returned)

    def test_bounded_incrementing_app_chunks(self):
        self.backend.connect()
        self.assertEqual(self.backend.read_flash(0x08010000, 16), b"".join(a.to_bytes(4, "little") for a in range(0x08010000, 0x08010010, 4)))
        for args in [(0x08000000, 4), (0x080103fc, 8), (0x20060000, 4), (0x08010000, 1028), (0x08010000, 3)]:
            with self.assertRaises(ValueError): self.backend.read_flash(*args)
        self.backend.close()

    def test_restore_failure_still_closes(self):
        self.backend.connect()
        def fail(*args): raise OSError("DAP unavailable")
        self.sdk.JLINKARM_CORESIGHT_WriteAPDPReg.callback = fail
        with self.assertRaises(OSError): self.backend.close()
        self.assertTrue(self.backend.close_returned)
        self.assertFalse(self.backend.metadata["tar_restored"])


class StateTests(unittest.TestCase):
    def test_exact_running_image_session_accessors(self):
        image = (ROOT / ".cache/p34-native-image1/app-readback.bin").read_bytes()
        self.assertEqual(image[0x3cb3c:0x3cb40], bytes.fromhex("90f8cc00"))
        self.assertEqual(image[0x3cb4a:0x3cb4e], bytes.fromhex("90f8ac01"))
        self.assertEqual(image[0x35a78:0x35a7c], bytes.fromhex("30bfa9e7"))
        from recovery_entry.state_probe import REGISTERS
        self.assertEqual(REGISTERS["ble_state_word"], 0x20052988 + 0xcc)
        self.assertEqual(REGISTERS["ble_isr_word"], 0x20052988 + 0x1ac)

    def test_watchdog_option_consistency_not_running_state(self):
        from recovery_entry.state_probe import REGISTERS, decode
        values = dict.fromkeys(REGISTERS, 0)
        values.update(usd_fap_ssb=0x00ff5aa5, flash_usd=4)
        result = decode(values, bytes(96))
        self.assertTrue(result["wdt_software_start_option"])
        self.assertFalse(result["wdt_running_proven"])
        self.assertFalse(result["media_safe_reset_proven"])
        values["flash_usd"] = 0
        self.assertIsNone(decode(values, bytes(96))["wdt_software_start_option"])
        values["usd_fap_ssb"] = 0x01fe5aa5
        self.assertFalse(decode(values, bytes(96))["wdt_software_start_option"])
        values.update(usd_fap_ssb=0xffff5aa5, flash_usd=0x03fffffc)
        self.assertTrue(decode(values, bytes(96))["wdt_software_start_option"])
        values["flash_usd"] |= 1
        self.assertIsNone(decode(values, bytes(96))["wdt_software_start_option"])

    def test_actual_sdio2_mapping_not_unused_sdio1(self):
        from recovery_entry.state_probe import REGISTERS
        source = (ROOT / ".cache/p34-sha-candidate/f/MDK-ARM_F435/Platform/Core/at32_sdio.h").read_text()
        self.assertRegex(source, r"#define\s+SDIOx\s+SDIO2")
        self.assertEqual(REGISTERS["sdio2_dtctrl"], 0x5006102c)
        self.assertEqual(REGISTERS["sdio2_sts"], 0x50061034)

    def test_no_consuming_fifo_or_command_address(self):
        from recovery_entry.state_probe import STATE_WORDS
        for address in (0x40003000, 0xa0001100, 0xa000100c, 0x4002c480, 0x4002c438, 0x40020418):
            self.assertNotIn(address, STATE_WORDS)

    def test_exact_recorder_and_cache_mapping(self):
        from recovery_entry.state_probe import REGISTERS
        image = (ROOT / ".cache/p34-native-image1/app-readback.bin").read_bytes()
        self.assertEqual(image[0x6080:0x6084], struct.pack("<I", 0x200041fc))
        for offset, code in ((0x2768, "2430"), (0x2770, "04f50c70"),
                             (0x37b6, "0378da07"), (0x3ab4, "8062"), (0x3abc, "c0f83402")):
            expected = bytes.fromhex(code)
            self.assertEqual(image[offset:offset+len(expected)], expected)
        mapping = (ROOT / ".cache/p34-sha-candidate/b/app-gcc/X-Track-App-GCC.map").read_text()
        self.assertRegex(mapping, r"\.bss\._ZZ17_DP_Recorder_InitP7AccountE8recorder\s+0x20051c14\s+0x78\b")
        self.assertEqual(REGISTERS["recorder_file"], 0x20051c14 + 0x64)
        self.assertEqual(REGISTERS["recorder_active_word"], 0x20051c14 + 0x70)
        self.assertEqual(REGISTERS["sd_data_cache_status"], 0x20052de0 + 0x24)
        self.assertEqual(REGISTERS["sd_fat_cache_status"], 0x20052de0 + 0x230)

    def test_cache_clean_and_recorder_paused_do_not_prove_safe_reset(self):
        from recovery_entry.state_probe import REGISTERS, decode
        values = dict.fromkeys(REGISTERS, 0)
        values.update(sd_data_cache_owner=0x20052de0, sd_fat_cache_owner=0x20052de0)
        for key in ("recorder_file", "recorder_driver", "recorder_cache"):
            values[key] = 0x20001000
            self.assertTrue(decode(values, bytes(96))["recorder_file_handle_present"])
            values[key] = 0
        for key, flag in (("sd_data_cache_status", "sd_data_cache_dirty"),
                          ("sd_fat_cache_status", "sd_fat_cache_dirty")):
            values[key] = 3
            self.assertTrue(decode(values, bytes(96))[flag])
            values[key] = 2
            self.assertFalse(decode(values, bytes(96))[flag])
        values["sd_error_word"] = 0x01020703
        result = decode(values, bytes(96))
        self.assertEqual([result[n] for n in ("sd_last_error", "sd_transfer_end", "sd_transfer_error", "sd_stop_flag")], [3, 7, 2, 1])
        self.assertTrue(result["sd_cache_owners_match"])
        for name in ("sd_card_ready_proven", "sd_filesystem_flushed_proven", "media_safe_reset_proven", "device_execute_ready"):
            self.assertFalse(result[name])

    def test_decode_does_not_qualify_ownership(self):
        from recovery_entry.state_probe import REGISTERS, decode
        values = dict.fromkeys(REGISTERS, 0)
        values.update(crm_ahben1=2, gpiob_mode=0x5000, gpiob_type=0xc0,
            gpiob_pull=0x5000, gpiob_drive=0xa000, gpiob_input=0xc0, gpiob_output=0xc0,
            dma1_1=1, debug_apb1_frz=0x1000)
        header = bytearray(96)
        header[:4] = b"ETFW"
        struct.pack_into("<II", header, 4, 1, 30275)
        struct.pack_into("<I", header, 92, zlib.crc32(header[:92]))
        result = decode(values, bytes(header))
        self.assertEqual(result["header_version_code"], 30275)
        self.assertEqual(result["dma_enabled"], ["dma1_1"])
        self.assertTrue(result["eeprom_config_matches"])
        self.assertTrue(result["wdt_pause_on_halt"])
        for name in ("full_app_verified", "wdt_running_proven", "dma_quiescence_proven", "eeprom_ownership_proven", "device_execute_ready"):
            self.assertFalse(result[name])
        header[30] ^= 1
        self.assertIsNone(decode(values, bytes(header))["header_version_code"])


if __name__ == "__main__":
    unittest.main()
