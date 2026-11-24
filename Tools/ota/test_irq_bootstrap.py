"""Offline admission and routing checks; no device or network workers."""
import copy
import io
from pathlib import Path
import runpy
import unittest

ROOT = Path(__file__).resolve().parents[2]
m = runpy.run_path(str(Path(__file__).with_name("irq_bootstrap.py")))


class Admission(unittest.TestCase):
    def setUp(self):
        self.prior = dict(result="ORIGINAL_FAILED_SNAPSHOT_VERIFIED", final_durable=24576,
                          nak_status_counts={"2": 4, "3": 31}, device_mutations=0)
        self.closed = dict(port_closed=True, stop_exit=0)
        self.owner = dict(forced_termination=False, worker_exit=1)
        self.group = dict(baseline_identity=dict(version_code=30208), target_identity=dict(version_code=30210),
            baseline=dict(sha256="b7f8542861591f22aa5ba65ff019b01f3fd23b66699db31e3b516855f1df48ed"),
            package=dict(bytes=1000), decoder=dict(passed=True))

    def test_original_failure_and_host_rejection_are_distinct(self):
        m["validate_prior"](self.prior, self.closed, self.owner)

    def test_unknown_outcome_rejected(self):
        self.prior["result"] = "PENDING_USB"
        with self.assertRaises(RuntimeError): m["validate_prior"](self.prior, self.closed, self.owner)

    def test_changed_durable_rejected(self):
        self.prior["final_durable"] = 4096
        with self.assertRaises(RuntimeError): m["validate_prior"](self.prior, self.closed, self.owner)

    def test_forced_close_rejected(self):
        self.owner["forced_termination"] = True
        with self.assertRaises(RuntimeError): m["validate_prior"](self.prior, self.closed, self.owner)

    def test_same_version_rejected(self):
        self.group["target_identity"]["version_code"] = 30208
        with self.assertRaises(RuntimeError): m["validate_group"](self.group)

    def test_wrong_baseline_rejected(self):
        self.group["baseline"]["sha256"] = "0" * 64
        with self.assertRaises(RuntimeError): m["validate_group"](self.group)

    def test_bad_decoder_rejected(self):
        self.group["decoder"]["passed"] = False
        with self.assertRaises(RuntimeError): m["validate_group"](self.group)

    def test_actual_runtime_rebinding(self):
        r = m["runtime"]()
        self.assertEqual(r.PKG, "com.wen.gaia.gaia.p34retry")
        self.assertEqual(r.b.OUT, ROOT / ".cache/p34q/irq")
        self.assertEqual(r.a.FW, ROOT / ".cache/p34q/irq/fw")
        self.assertEqual(r.PHONE, r.RUNTIME / "phone-r1")
        self.assertEqual(r.apk()["apk"]["sha256"], m["APK_SHA"])
        p = r.phone(m["RUN"])
        self.assertEqual(p.RUNTIME, r.PHONE)
        self.assertEqual(p.cell("runtime"), r.cell(m["RUN"]))
        assets = r.m.verified_assets()
        m["validate_group"](assets["groups"]["screen"])
        config = r.make_config(assets, "https://bounded.example", "a" * 64)
        self.assertTrue(all(x["asset"]["fileName"] == m["FILE_NAME"] for x in config["releases"].values()))
        self.assertEqual(set(r.m.load_bindings()["profiles"]), {"30208", "30210"})
        query = m["target_query"](r, assets["groups"]["screen"])
        self.assertEqual(query["currentVersionCode"], "30210")
        self.assertEqual(query["currentImageSha"], assets["groups"]["screen"]["target"]["sha256"])


if __name__ == "__main__":
    r = m["runtime"]()
    out = r.b.checked(m["AREA"] / "host-tests-v2")
    r.b.require(not out.exists(), "preserve original host tests")
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Admission))
    r.save(out / "result.json", dict(passed=result.wasSuccessful(), tests=result.testsRun,
        source=r.b.record(Path(__file__).with_name("irq_bootstrap.py")), test_source=r.b.record(Path(__file__)),
        output=stream.getvalue(), hardware=False, network=False))
    print(stream.getvalue(), flush=True)
    raise SystemExit(0 if result.wasSuccessful() else 1)
