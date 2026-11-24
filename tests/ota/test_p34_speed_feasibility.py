"""Budget and image-difference guards do not invent missing observations."""
import io
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_speed_feasibility as f


class Tests(unittest.TestCase):
    def test_unknown_padding_is_not_identical(self):
        value = f.block_workload(b"abcde", b"abcde", 4)
        self.assertEqual(value["counts"], dict(different=0, identical=1, unknown=1))

    def test_known_mismatch_proves_difference_even_on_partial_block(self):
        value = f.block_workload(b"abcde", b"abcdx", 4)
        self.assertEqual(value["counts"], dict(different=1, identical=1, unknown=0))

    def test_growth_unknown_and_shrink_padding(self):
        self.assertEqual(f.block_workload(b"abcd", b"abcdefgh", 4)["counts"]["unknown"], 1)
        self.assertEqual(f.block_workload(b"abcdef", b"abcde", 4)["counts"]["different"], 1)

    def test_commit_counts(self):
        value = f.block_workload(b"x"*617588, b"x"*617588)
        self.assertEqual(value["per_block_copy_commits"], 151)
        self.assertEqual(value["hypothetical_group16_copy_commits"], 10)

    def test_budget_fixed_cost_counterfactual(self):
        value = f.budget(dict(data_gatt_us=10000000, last_chunk_to_durable_us=5000000,
                              other=1000000), 300000)
        self.assertEqual(value["target_budget_us"], 6000000)
        self.assertEqual(value["cases"]["half_gatt_zero_tail_other_costs_fixed"]["decimal_kb_s"], 50)
        self.assertGreater(value["cases"]["zero_tail_other_costs_fixed"]["seconds"], 6)

    def test_invalid_inputs(self):
        for total in (0, -1, True):
            with self.assertRaises(RuntimeError): f.budget(dict(data_gatt_us=1,last_chunk_to_durable_us=1),total)
        with self.assertRaises(RuntimeError): f.block_workload(b"", b"")
        with self.assertRaises(RuntimeError): f.budget(dict(data_gatt_us=-1,last_chunk_to_durable_us=1),1)


if __name__ == "__main__":
    f.cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and
                  sys.dont_write_bytecode, "explicit isolated root required")
    s=f.cli.Store(ROOT); out=s.checked(Path(sys.argv[1]))
    f.cli.require(not out.exists(), "preserve test evidence")
    for name in ("tests.log", "result.json"): s.checked(out/name)
    stream=io.StringIO()
    result=unittest.TextTestRunner(stream=stream,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    s.raw(out/"tests.log",stream.getvalue().encode())
    s.write(out/"result.json",dict(passed=result.wasSuccessful(),count=result.testsRun,
        source=f.cli.record(f.__file__),test=f.cli.record(__file__),device_operations=0))
    print(stream.getvalue());sys.exit(not result.wasSuccessful())
