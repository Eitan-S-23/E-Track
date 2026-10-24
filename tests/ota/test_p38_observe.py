import importlib.util
import json
from pathlib import Path
import sys
import subprocess
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota/p38-acceptance"))
spec = importlib.util.spec_from_file_location("p38_observe", ROOT / "Tools/ota/p38-acceptance/observe.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class CollectorTests(unittest.TestCase):
    def test_changed_process_stops_before_later_samples(self):
        phone = Mock(pkg="com.wen.gaia.gaia.p38acceptance")
        phone.cmd.return_value = b"13\n"
        with patch.object(m.h, "fresh", side_effect=lambda path: path), patch.object(m.h, "raw"), \
                self.assertRaisesRegex(RuntimeError, "process changed"):
            m.sample(phone, ROOT / ".cache/p38/unused", 1, {}, 12, "capture")
        self.assertEqual(phone.cmd.call_count, 1)
        phone.health.assert_not_called()

    def test_record_requires_real_frozen_contract(self):
        args = Mock(contract=None, matrix=None, command_id=None)
        with self.assertRaisesRegex(RuntimeError, "requires frozen"):
            m.gate(args, ROOT / ".cache/p38/unused")

    def test_real_isolated_cli_imports(self):
        result = subprocess.run([sys.executable, "-I", "-S", "-B", "-W", "error", "-X", "utf8",
                                 str(ROOT / "Tools/ota/p38-acceptance/observe.py"), "--help"],
                                cwd=ROOT, capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr.decode())

    def test_exact_capture_identity(self):
        plan = dict(sentinel="OTAOBS" + "a" * 24, ble_address="AA:BB:CC:DD:EE:FF")
        header = dict(kind="open", pid=12, captureId="capture", sentinel=plan["sentinel"], target=plan["ble_address"])
        self.assertEqual(m.capture_header(json.dumps(header).encode(), plan, 12, "capture"), header)
        for key, value in (("kind", "line"), ("pid", 13), ("captureId", "other"),
                           ("sentinel", "other"), ("target", "00:00:00:00:00:00"), ("target", None)):
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                m.capture_header(json.dumps(dict(header, **{key: value})).encode(), plan, 12, "capture")

    def test_notification_selection_cannot_inject_shell(self):
        for package in ("x;id", "a.b'", "a.b c", "a.b\nreboot"):
            with self.subTest(package=package), self.assertRaises(RuntimeError):
                m.notification_filter(package)
        command = m.notification_filter("com.wen.gaia.gaia.p38acceptance")
        self.assertIn("pkg=com.wen.gaia.gaia.p38acceptance ", command)
        self.assertIn("keep=0", command)


if __name__ == "__main__":
    unittest.main()
