from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota/p38-acceptance"))
import offline as m


class OriginalTests(unittest.TestCase):
    def test_actual_test_counts_include_skips(self):
        self.assertEqual(m.test_counts("00:34 +753 ~16: All tests passed!\n"),
                         dict(passed=753, skipped=16, failed=0))
        for value in ("All tests passed!", "+753 ~16 -1: All tests passed!", "+1: All tests passed!\n+1: All tests passed!"):
            with self.subTest(value=value), self.assertRaises(RuntimeError):
                m.test_counts(value)

    def test_native_counts_do_not_hide_case_failure(self):
        cases = ''.join('<testcase name="case%d" />' % n for n in range(18))
        xml = '<testsuite name="com.wen.gaia.gaia.DeviceOtaServiceTest" tests="18" failures="0" errors="0" skipped="0">' + cases + '</testsuite>'
        self.assertEqual(len(m.native_cases(xml)), 18)
        with self.assertRaises(RuntimeError):
            m.native_cases(xml.replace('<testcase name="case0" />', '<testcase name="case0"><failure /></testcase>'))


if __name__ == "__main__":
    unittest.main()
