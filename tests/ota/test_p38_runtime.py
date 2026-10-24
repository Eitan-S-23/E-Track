from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota/p38-acceptance"))
from runtime import baseline_config
from final_state import same_executable


class RuntimeTests(unittest.TestCase):
    def test_endpoint_override_retains_baseline(self):
        plan = dict(ble_address="AA:BB:CC:DD:EE:FF", package=dict(bytes=1048576, sha256="a" * 64),
                    images=dict(base=dict(image=dict(sha256="b" * 64)), target=dict(image=dict(sha256="c" * 64))))
        value = baseline_config(plan, "https://fixture.example", "p38-d1")
        self.assertEqual(value["schema"], 1)
        self.assertFalse(value["reuseGatt"] or value["withoutResponse"])
        self.assertEqual((value["currentVersionCode"], value["targetVersionCode"]), (30287, 30288))
        for origin in ("http://example.test", "https://example.test/path", "https://user@example.test", "https://example.test?token=1"):
            with self.subTest(origin=origin), self.assertRaises(RuntimeError):
                baseline_config(plan, origin, "p38-d1")

    def test_symbol_reuse_rejects_changed_executable(self):
        old = bytes(2048)
        header_only = bytearray(old)
        header_only[0x408] = 1
        same_executable(old, header_only)
        header_only[0x460] = 1
        with self.assertRaises(RuntimeError):
            same_executable(old, header_only)


if __name__ == "__main__":
    unittest.main()
