"""Offline batch12 asset, schema, original-log and route admission checks."""
import io
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_batch12_trial as f


class Guards(unittest.TestCase):
    def setUp(self):
        self.s = f.cli.Store(ROOT)

    def config(self, group):
        g, spec = group, group["specification"]
        return dict(schema=7, runId="s04", target="02:00:00:00:00:01", requestedBaud=921600,
            reuseGatt=True, withoutResponse=True, senderWindowSegments=28, transferMode="full", prefixBytes=0,
            rebootInfoTimeoutMs=2000, rebootProbeIntervalMs=500, pauseScanDuringOta=True, androidHighPriority=True,
            dataBatchFrames=spec["dataBatchFrames"], reuseRebootInfoLink=True,
            currentVersionCode=spec["receiver"], targetVersionCode=spec["target_version"],
            currentImageSha256=g["receiver"]["sha256"], targetImageSha256=g["target"]["sha256"],
            packageBytes=g["package"]["bytes"], packageSha256=g["package"]["sha256"],
            firmwareLatestUrl="https://offline.trycloudflare.com/api/public/firmware/latest")

    def test_assets_have_same_executable_and_boot(self):
        for arm in f.ORDER:
            g = f.assets(self.s, arm)
            a, b = [Path(g[k]["path"]).read_bytes() for k in ("receiver", "target")]
            self.assertEqual(a[:0x400] + a[0x460:], b[:0x400] + b[0x460:])
            self.assertEqual(g["receiver_bindings"]["whole_boot"], g["target_bindings"]["whole_boot"])
            self.assertEqual(len(g["negatives"]), 4)
            self.assertTrue(all(x["native"]["passed"] and x["native"]["prepares"] == 0 for x in g["negatives"]))

    def test_lineage_is_sequential_not_a_baseline_downgrade(self):
        first, second = [f.assets(self.s, arm) for arm in f.ORDER]
        self.assertEqual(first["target"], second["receiver"])
        self.assertEqual(first["target_identity"]["version_code"], 30258)
        self.assertEqual(second["target_identity"]["version_code"], 30259)
        proof = f.predecessor(self.s, "control", first)
        self.assertEqual(proof["report"]["summary"]["input"]["targetVersionCode"], 30257)

    def test_exact_profile_and_original_observation(self):
        capture = f.cli.load_module("batch12_capture", ROOT / "Tools/ota/p34_observation.py")
        for arm in f.ORDER:
            g = f.assets(self.s, arm)
            config = self.config(g)
            f.validate(config, g)
            item = {k: v for k, v in config.items() if k not in ("target", "firmwareLatestUrl")}
            item.update(deviceAddress=config["target"], endpointHost="offline.trycloudflare.com", configSha256="a" * 64)
            self.assertEqual(f.verify(capture, "OTA_EXPERIMENT " + json.dumps(item), config, "a" * 64), item)
            item["dataBatchFrames"] = 12 if arm == "control" else 3
            with self.assertRaises(RuntimeError):
                f.verify(capture, "OTA_EXPERIMENT " + json.dumps(item), config, "a" * 64)

    def test_only_declared_axes_and_exact_types(self):
        for arm in f.ORDER:
            group = f.assets(self.s, arm)
            config = self.config(group)
            for key, value in config.items():
                if key == "firmwareLatestUrl":
                    continue
                changed = not value if type(value) is bool else value + 1 if type(value) is int else value + "x"
                with self.subTest(arm=arm, key=key), self.assertRaises(RuntimeError):
                    f.validate(dict(config, **{key: changed}), group)
            for value in (True, 12.0, "12", 0, 4, 8, 13):
                with self.subTest(value=value), self.assertRaises(RuntimeError):
                    f.validate(dict(config, dataBatchFrames=value), group)

    def test_no_extra_or_missing_fields(self):
        group = f.assets(self.s, "batch12")
        config = self.config(group)
        with self.assertRaises(RuntimeError):
            f.validate(dict(config, unknown=True), group)
        for key in config:
            bad = dict(config)
            del bad[key]
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                f.validate(bad, group)

    def test_phone_wrapper_preserves_parent_config(self):
        for arm in f.ORDER:
            api = object.__new__(f.Trial)
            api.assets = f.assets(self.s, arm)
            expected = self.config(api.assets)
            old = dict(expected, schema=6, rebootProbeIntervalMs=100, dataBatchFrames=3)
            with mock.patch.object(f.prior.Cadence, "phone", return_value=SimpleNamespace(config=lambda *a: old)):
                self.assertEqual(api.phone(None, "fixture").config(), expected)
            self.assertEqual(old["schema"], 6)
            self.assertEqual(old["rebootProbeIntervalMs"], 100)

    def test_original_timing_remains_original_and_mixed_batch_rejected(self):
        p = f.PRIOR / "cells/s04/finished/snapshot.jsonl"
        rows = [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines()]
        messages = "\n".join(x["message"] for x in rows if x.get("kind") == "line")
        value = f.full_metrics(messages, 293194, "02:00:00:00:00:01")
        self.assertEqual(value["transfer_seconds"], 21.179229)
        stamp = next(x for x in messages.splitlines() if x.startswith("OTA_EXPERIMENT "))
        changed = json.loads(stamp.removeprefix("OTA_EXPERIMENT "))
        changed["dataBatchFrames"] = 12
        with self.assertRaises(RuntimeError):
            f.full_metrics(messages.replace(stamp, "OTA_EXPERIMENT " + json.dumps(changed)), 293194, "02:00:00:00:00:01")

    def test_unlisted_arm_rejected(self):
        with self.assertRaises(RuntimeError):
            f.assets(self.s, "repeat")


if __name__ == "__main__":
    f.cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                  "isolated explicit root required")
    s = f.cli.Store(ROOT)
    s.checked(f.HOST)
    f.cli.require(not f.HOST.exists(), "preserve tests")
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Guards))
    log = s.raw(f.HOST / "tests.log", stream.getvalue().encode())
    s.write(f.HOST / "result.json", dict(result="PASS" if result.wasSuccessful() else "FAIL", tests=result.testsRun,
        source=f.cli.record(f.__file__), test=f.cli.record(__file__), log=log, hardware=False))
    print(stream.getvalue())
    sys.exit(not result.wasSuccessful())
