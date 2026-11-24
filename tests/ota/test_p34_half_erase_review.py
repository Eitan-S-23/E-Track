"""Keep bootstrap, installation gains and complete-package transfer rates separate."""
import io
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_half_erase_review as f


def fixture():
    rows = {}
    for index, name in enumerate(f.TRIALS):
        first = 30263 + index
        rows[name] = dict(policy=dict(f.POLICY),
            binding=dict(writeMode="without", mtuChunkBytes=244, mtuSource="negotiated"),
            header_only=index != 1, apk_sha256="same-apk", boot_sha256="same-boot",
            transfer_seconds=17 if index == 0 else 16,
            installation_reconnect_seconds=(22, 38, 20)[index],
            input=dict(currentVersionCode=first, targetVersionCode=first + 1,
                currentImageSha256=format(first, "064x"), targetImageSha256=format(first + 1, "064x"),
                packageSha256=format(first + 100, "064x"), packageBytes=300000 + index * 100,
                deviceAddress="AA:BB", appLifecycle="resumed"))
    return rows


class Tests(unittest.TestCase):
    def cost_text(self, phase):
        return f"P34COST: phase={phase} rc=0 clock=millis total=10 rest=3 valid=1\n" + "\n".join(
            f"P34COST_IO: phase={phase} kind={i} calls=1 fail=0 bytes=0:256 ticks=0:1" for i in range(7))

    def test_original_cost_blocks(self):
        values = f.parse_costs([self.cost_text("full"), self.cost_text("backup")])
        self.assertEqual(set(values), {"full", "backup"})
        self.assertEqual(values["full"]["ports"]["erase"]["ticks_ms"], 1)
        self.assertEqual(values["backup"]["total_ticks_ms"], 10)

    def test_costs_reject_missing_failed_duplicate_or_truncated(self):
        full, backup = self.cost_text("full"), self.cost_text("backup")
        for texts in ([full], [full, backup, backup], [full, backup.replace("rc=0", "rc=-1")],
                      [full, backup.rsplit("\n", 1)[0]], [full.replace("rest=3", "rest=4"), backup],
                      [full, backup.replace("phase=backup", "phase=patch")],
                      [full, backup + "\nP34COST_IO: orphan"],
                      [full, "\n".join(backup.splitlines()[1:])]):
            with self.assertRaises(RuntimeError): f.parse_costs(texts)

    def reject(self, role, path, value):
        rows = fixture()
        target = rows[role]
        for key in path[:-1]: target = target[key]
        target[path[-1]] = value
        with self.assertRaises(RuntimeError): f.compare(rows)

    def test_rates_and_disjoint_total(self):
        result = f.compare(fixture())
        self.assertAlmostEqual(result["measure_kb_s"], 300200 / 16000)
        self.assertEqual(result["transfer_seconds_saved"], 1)
        self.assertEqual(result["installation_reconnect_seconds_saved"], 2)
        self.assertEqual(result["transfer_plus_install_seconds_saved"], 3)
        self.assertFalse(result["strict_same_package_ab"])
        self.assertFalse(result["independent_acceptance"])

    def test_bootstrap_and_native_times_cannot_be_savings(self):
        rows = fixture(); expected = f.compare(rows)
        rows["bootstrap"].update(transfer_seconds=999, installation_reconnect_seconds=999)
        rows["measure"]["pump"] = dict(work_seconds=999, gap_seconds=999)
        rows["measure"]["payload_erase_seconds"] = 999
        self.assertEqual(f.compare(rows), expected)

    def test_partial_install_gain_is_not_whole_upgrade_gain(self):
        rows = fixture(); rows["measure"]["transfer_seconds"] = 30
        result = f.compare(rows)
        self.assertTrue(result["useful_installation_screening_gain"])
        self.assertFalse(result["whole_upgrade_screening_gain"])
        rows["measure"]["installation_reconnect_seconds"] = 23
        self.assertFalse(f.compare(rows)["useful_installation_screening_gain"])

    def test_normalized_smaller_package(self):
        rows = fixture(); rows["measure"]["input"]["packageBytes"] = 100000
        self.assertLess(f.compare(rows)["throughput_gain_percent"], 0)

    def test_policy_and_workload_for_every_role(self):
        for role in f.TRIALS:
            self.reject(role, ("policy", "dataBatchFrames"), 3)
            self.reject(role, ("policy", "rebootProbeIntervalMs"), 100)
            self.reject(role, ("binding", "mtuChunkBytes"), 20)
            self.reject(role, ("header_only",), role == "bootstrap")
            self.reject(role, ("input", "appLifecycle"), "paused")

    def test_identity_roles_and_no_replay(self):
        for role in f.TRIALS:
            self.reject(role, ("apk_sha256",), "different")
            self.reject(role, ("boot_sha256",), "different")
            self.reject(role, ("input", "deviceAddress"), "CC:DD")
            self.reject(role, ("input", "targetVersionCode"), True)
            self.reject(role, ("input", "packageSha256"), "invalid")
        self.reject("bootstrap", ("input", "currentImageSha256"), "f" * 64)
        self.reject("measure", ("input", "currentImageSha256"), "f" * 64)
        self.reject("measure", ("input", "packageSha256"), fixture()["control"]["input"]["packageSha256"])
        rows = fixture(); del rows["bootstrap"]
        with self.assertRaises(RuntimeError): f.compare(rows)

    def test_invalid_sizes_and_clocks(self):
        for role in f.TRIALS:
            for value in (True, 0, -1, 1.5, 1048577):
                self.reject(role, ("input", "packageBytes"), value)
            for key in ("transfer_seconds", "installation_reconnect_seconds"):
                for value in (True, 0, -1, float("nan"), float("inf")):
                    self.reject(role, (key,), value)

    def test_targets_are_separate(self):
        rows = fixture(); rows["measure"]["transfer_seconds"] = 6.004
        self.assertTrue(f.compare(rows)["transfer_target_met"])
        rows["measure"]["installation_reconnect_seconds"] = 20.001
        self.assertFalse(f.compare(rows)["installation_target_met"])
        rows["measure"]["installation_reconnect_seconds"] = 20
        self.assertTrue(f.compare(rows)["installation_target_met"])


if __name__ == "__main__":
    f.cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                  "explicit isolated root required")
    s = f.cli.Store(ROOT)
    out = s.checked(Path(sys.argv[1]))
    f.cli.require(not out.exists(), "preserve tests")
    for name in ("tests.log", "result.json"): s.checked(out / name)
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    s.raw(out / "tests.log", stream.getvalue().encode())
    s.write(out / "result.json", dict(result="PASS" if result.wasSuccessful() else "FAIL", tests=result.testsRun,
        source=f.cli.record(f.__file__), test=f.cli.record(__file__), hardware=False))
    print(stream.getvalue())
    sys.exit(not result.wasSuccessful())
