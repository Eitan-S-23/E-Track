"""Rolling screen keeps the old resources/default and pins its predecessor."""
import importlib.util
from pathlib import Path
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("rolling_screen", ROOT / "Tools/ota/p34_rolling_screen.py")
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


class Tests(unittest.TestCase):
    def test_fixed_resource_unchanged(self):
        resources = M.capacity.browser_resources()
        self.assertEqual(resources["/capacity.js"][0], (ROOT / "Tools/ota/p34_link_capacity.js").read_bytes())

    def test_rolling_loads_after_fixed_base(self):
        resources = M.capacity.browser_resources("rolling-credit-v1")
        self.assertEqual(resources["/capacity.js"][0],
            (ROOT / "Tools/ota/p34_link_capacity.js").read_bytes() + b"\n" +
            (ROOT / "Tools/ota/p34_rolling_capacity.js").read_bytes())
        with self.assertRaises(RuntimeError):
            M.capacity.browser_resources("unknown")

    def test_source_bindings_include_sender_and_controller(self):
        paths = {Path(v["path"]).name for v in M.sources()}
        self.assertTrue({"p34_rolling_capacity.js", "p34_rolling_screen.py",
                         "p34_capacity_session.py", "uart_probe.js"} <= paths)

    def test_predecessor_drift_rejected(self):
        with mock.patch.object(M.capacity, "record", return_value={"sha256": "00" * 32}):
            with self.assertRaises(RuntimeError):
                M.verify_previous()

    def test_configuration_uses_same_package_version(self):
        M.configure()
        self.assertEqual((M.capacity.TARGET_VERSION, M.capacity.WINDOW), (30237, 28))
        self.assertEqual(M.capacity.AREA, ROOT / ".cache/p34-rolling28")
        self.assertLessEqual(M.capacity.WINDOW * 142, 4095)


if __name__ == "__main__":
    unittest.main(verbosity=2)
