"""Schema8 host bindings and actual-PHY evidence guards; no hardware or CI."""
import io
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_phy_trial as f


def config(group):
    spec = group["specification"]
    return dict(schema=8, runId="s04", requestedBaud=921600, target="02:00:00:00:00:01",
        reuseGatt=True, withoutResponse=True, senderWindowSegments=28, transferMode="full", prefixBytes=0,
        rebootInfoTimeoutMs=2000, rebootProbeIntervalMs=500, pauseScanDuringOta=True, androidHighPriority=True,
        dataBatchFrames=12, reuseRebootInfoLink=True, androidPhyPolicy=spec["androidPhyPolicy"],
        firmwareLatestUrl="https://offline.trycloudflare.com/api/public/firmware/latest",
        currentVersionCode=spec["receiver"], targetVersionCode=spec["target_version"],
        currentImageSha256=group["receiver"]["sha256"], targetImageSha256=group["target"]["sha256"],
        packageBytes=group["package"]["bytes"], packageSha256=group["package"]["sha256"])


class Guards(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.groups = {name: f.assets(f.cli.Store(ROOT), name) for name in f.ORDER}

    def test_real_assets_and_configs(self):
        for group in self.groups.values():
            f.validate(config(group), group)
            before, after = [Path(group[key]["path"]).read_bytes() for key in ("receiver", "target")]
            self.assertNotEqual(before, after)
            self.assertEqual(before[:0x400] + before[0x460:], after[:0x400] + after[0x460:])

    def test_wrong_or_extra_policy_rejected(self):
        group = self.groups["observe"]
        good = config(group)
        for changes in ({"schema": 7}, {"schema": 8.0}, {"androidPhyPolicy": "off"},
                        {"androidPhyPolicy": "prefer2m"}, {"dataBatchFrames": 3}, {"extra": 1}):
            with self.assertRaises(RuntimeError): f.validate(dict(good, **changes), group)
        with self.assertRaises(RuntimeError): f.validate({k: v for k, v in good.items() if k != "androidPhyPolicy"}, group)

    def test_preference_is_not_actual_phy(self):
        expected = config(self.groups["prefer2m"])
        good = dict(schema=1, status="observed", configSha256="a" * 64, requestId="s04",
            remoteId=expected["target"], policy="prefer2m", connectionGeneration=4, elapsedMicros=3000,
            beforeReadStatus=0, beforeTxPhy=1, beforeRxPhy=1, txPhy=2, rxPhy=2, readStatus=0, updateStatus=0)
        def verify(value): return f.verify_phy("OTA_PHY " + json.dumps(value), expected, "a" * 64)
        self.assertEqual(verify(good), good)
        for changes in ({"txPhy": 1}, {"rxPhy": 1}, {"status": "requested"}, {"status": "timeout"},
                        {"configSha256": "b" * 64}, {"requestId": "old"}, {"readStatus": None},
                        {"elapsedMicros": 4000000}, {"schema": True}, {"beforeReadStatus": False},
                        {"connectionGeneration": True}, {"updateStatus": False}):
            with self.assertRaises(RuntimeError): verify(dict(good, **changes))
        with self.assertRaises(RuntimeError): f.verify_phy("", expected, "a" * 64)
        with self.assertRaises(RuntimeError): f.verify_phy(("OTA_PHY " + json.dumps(good) + "\n") * 2, expected, "a" * 64)


if __name__ == "__main__":
    f.cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                  "explicit isolated root required")
    s = f.cli.Store(ROOT)
    s.checked(f.HOST)
    f.cli.require(not f.HOST.exists(), "preserve original test output")
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Guards))
    log = s.raw(f.HOST / "tests.log", stream.getvalue().encode())
    s.write(f.HOST / "result.json", dict(result="PASS" if result.wasSuccessful() else "FAIL",
        source=f.cli.record(f.__file__), test=f.cli.record(__file__), tests=result.testsRun, log=log, hardware=False))
    print(stream.getvalue())
    sys.exit(not result.wasSuccessful())
