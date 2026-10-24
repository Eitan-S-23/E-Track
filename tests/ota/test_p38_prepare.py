"""Offline checks for the P3-8 admission-only parser boundary."""
import importlib.util
from pathlib import Path
import sys
import hashlib
import struct
import unittest
from unittest.mock import Mock, patch
import zlib

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("p38_prepare", ROOT / "Tools/ota/p38-acceptance/prepare.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
from live_phone import fixture_versions


class AdmissionTests(unittest.TestCase):
    def test_existing_fixture_defaults_unchanged(self):
        self.assertEqual(fixture_versions({}), dict(base=30286, target=30287, target_name="3.2.87"))

    def test_new_fixture_version_binding(self):
        versions = dict(base=30287, target=30288, target_name="3.2.88-p38")
        self.assertEqual(fixture_versions(dict(fixture_versions=versions)), versions)
        for bad in (dict(versions, base=30288), dict(versions, target=True),
                    dict(versions, target_name="3.2.89"), dict(versions, extra=0)):
            with self.subTest(bad=bad), self.assertRaises(RuntimeError):
                fixture_versions(dict(fixture_versions=bad))

    def test_runtime_observation_does_not_hide_absent_sd(self):
        data = {k: bytes(4) for k in ("vtor", "cfsr", "hfsr", "dhcsr", "sdio")}
        data.update(state=b"\4", confirmed=b"\1", snapped=b"\1", sd=b"\0", owner=b"\0", active=b"\0", isr=b"\0")
        data["vtor"] = struct.pack("<I", 0x08010800)
        data["health0"] = struct.pack("<9I", 30000, 30, 1000, 0, 100, 100, 0, 1, 1)
        data["health1"] = struct.pack("<9I", 30000, 30, 1000, 0, 200, 200, 0, 1, 1)
        result = m.runtime_observations(data)
        self.assertFalse(result["sd_ready"])
        self.assertTrue(result["confirmed"] and result["ota_idle"] and result["fault_free"] and result["same_boot_advancing"])
        data["active"] = b"\1"
        self.assertFalse(m.runtime_observations(data)["ota_idle"])
        data["hfsr"] = struct.pack("<I", 1)
        self.assertFalse(m.runtime_observations(data)["fault_free"])

    def test_phone_cleanup_still_runs_after_stop_error(self):
        phone = Mock()
        phone.server.alive.return_value = True
        phone.base = ["adb"]
        with patch.object(m.h, "listening", return_value=True), patch.object(m.h, "command", side_effect=RuntimeError("stop")):
            with self.assertRaisesRegex(RuntimeError, "stop"):
                m.close_phone(phone)
        phone.close.assert_called_once()

    def test_passive_runner_rejects_mutating_commands(self):
        for command in ("h", "r", "g", "w4 0x20000000, 1", 'loadbin "a.bin", 0x08010000'):
            device = object.__new__(m.PassiveMCU)
            device.logger, device.count = None, 0
            device.out = ROOT / ".cache/p38/virtual"
            with patch.object(m.h, "fresh", side_effect=lambda path: path), \
                    patch.object(device, "foreign_debuggers"), patch.object(m.h, "raw") as raw:
                with self.subTest(command=command), self.assertRaisesRegex(RuntimeError, "passive reads only"):
                    device.execute([command], {}, "test")
                raw.assert_not_called()

    def image(self):
        raw = bytearray(2048)
        raw[0x400:0x404] = b"ETFW"
        struct.pack_into("<II", raw, 0x404, 1, 30286)
        raw[0x40c:0x412] = b"3.2.86"
        struct.pack_into("<I", raw, 0x424, len(raw))
        raw[0x428:0x448] = hashlib.sha256(raw).digest()
        struct.pack_into("<I", raw, 0x45c, zlib.crc32(raw[0x400:0x45c]))
        return raw

    def test_valid_image_uses_raw_and_header_hash_separately(self):
        raw = self.image()
        result = m.firmware_identity(raw + bytes(2048))
        self.assertEqual(result["bytes"], 2048)
        self.assertEqual(result["version_code"], 30286)
        self.assertEqual(result["raw_sha256"], hashlib.sha256(raw).hexdigest())
        self.assertNotEqual(result["raw_sha256"], result["header_sha256"])

    def test_short_corrupt_and_out_of_bounds_image_rejected(self):
        for offset in (0, 0x400, 0x404, 0x424, 0x428, 0x45c, 0x700):
            raw = self.image()
            raw[offset] ^= 1
            with self.subTest(offset=offset), self.assertRaises(RuntimeError):
                m.firmware_identity(raw)
        with self.assertRaises(RuntimeError):
            m.firmware_identity(bytes(1024))

    def test_single_signer(self):
        self.assertEqual(m.signer("Verifies\nSigner #1 certificate SHA-256 digest: " + "a" * 64 + "\n"), "a" * 64)

    def test_missing_or_ambiguous_signer(self):
        for text in ("", "Signer #1 certificate SHA-256 digest: bad", "\n".join(
                "Signer #%d certificate SHA-256 digest: %s" % (n, "a" * 64) for n in (1, 2))):
            with self.subTest(text=text), self.assertRaises(RuntimeError):
                m.signer(text)

    def test_exact_installed_path(self):
        value = "package:/data/app/~~abcd==/com.wen.gaia.gaia-123==/base.apk"
        self.assertEqual(m.apk_path(value, "com.wen.gaia.gaia"), value[8:])

    def test_path_rejects_splits_foreign_and_shell(self):
        values = ("package:/data/app/com.other-123/base.apk", "package:/data/app/com.wen.gaia.gaia-x/split.apk",
                  "package:/data/app/com.wen.gaia.gaia-x/base.apk\npackage:/other.apk",
                  "package:/data/app/com.wen.gaia.gaia-x/base.apk;echo", "/data/app/com.wen.gaia.gaia-x/base.apk")
        for value in values:
            with self.subTest(value=value), self.assertRaises(RuntimeError):
                m.apk_path(value, "com.wen.gaia.gaia")


if __name__ == "__main__":
    assert Path.cwd() == ROOT and sys.flags.isolated and sys.dont_write_bytecode
    unittest.main()
