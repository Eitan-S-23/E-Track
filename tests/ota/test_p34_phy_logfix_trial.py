"""Successor capture/PHY admission regressions; no phone or MCU operations."""
import io
import hashlib
import json
from contextlib import nullcontext
from pathlib import Path
import runpy
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_phy_logfix_trial as f


class Guards(unittest.TestCase):
    def archive_fixture(self, *, redirected=False, uncertain=False):
        saved = {p.name: p.read_bytes() for p in (f.install.failed.OUT / "capture").iterdir()}
        config = (f.install.failed.OUT / "runtime-config.json").read_bytes()
        expected = (f.install.original.PRIOR / "cells/s04/finished/snapshot.jsonl").read_bytes()
        names = json.loads((f.install.failed.AREA / "archive-observe/result.json").read_bytes())["remaining"]
        names = names + [f.install.CAPTURE]
        protected = "files/p34-observations/" + f.PROTECTED + "/snapshot-1.jsonl"
        archive = "files/p34-archived-observations/" + f.install.CAPTURE
        retired = "files/p34-retired-configs/" + hashlib.sha256(config).hexdigest() + ".json"
        remote = {f.install.REMOTE + "/" + n: raw for n, raw in saved.items()}
        remote.update({protected: expected, "files/p34-experiment.json": config})
        commands, writes = [], {}
        def command(args, **kwargs):
            commands.append(args)
            if args == ["shell", "pidof", f.install.PKG]: return ""
            self.assertEqual(args[:3], ["exec-out", "run-as", f.install.PKG])
            op, rest = args[3], args[4:]
            if op == "readlink":
                path = rest[1]
                return "/redirected" if redirected else "/data/user/0/" + f.install.PKG + ("/" + path if path != "." else "")
            if op == "ls":
                flag, path = rest
                if flag == "-d":
                    return path if path in remote or any(n.startswith(path + "/") for n in remote) else ""
                if path == "files/p34-observations": return "\n".join(names)
                return "\n".join(n[len(path) + 1:] for n in remote if n.startswith(path + "/"))
            if op == "mv":
                self.assertEqual(rest[0], "-n")
                source, target = rest[1:]
                if uncertain: raise RuntimeError("fixture move outcome unknown")
                if source == f.install.REMOTE:
                    self.assertEqual(target, archive)
                    names.remove(f.install.CAPTURE)
                    for name in saved: remote[target + "/" + name] = remote.pop(source + "/" + name)
                else:
                    self.assertEqual((source, target), ("files/p34-experiment.json", retired))
                    remote[target] = remote.pop(source)
                return ""
            self.fail("unplanned operation: " + str(args))
        p = SimpleNamespace(phone_identity=lambda: None, command=command,
            file_bytes=lambda pkg, path, limit: remote[path])
        def raw(path, data):
            writes[str(path)] = data
            return dict(path=str(path), bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
        original_record = f.cli.record
        def record(path):
            return raw(path, writes[str(path)]) if str(path) in writes else original_record(path)
        store = SimpleNamespace(raw=raw, write=lambda p, v: writes.update({str(p): v}))
        runtime = lambda: (None, dict(usb=lambda *a: nullcontext(), installed=lambda *a: {}),
                           p, SimpleNamespace(device_lock=nullcontext))
        error = None
        with patch.object(f, "installed", return_value=(dict(apk=dict(sha256="fixture")), dict(checkpoint={}))), \
             patch.object(f.install, "runtime", runtime), patch.object(f.install, "OUT", f.install.failed.OUT), \
             patch.object(f.cli, "record", record):
            try: f.archive_worker(store)
            except RuntimeError as caught: error = caught
        return commands, writes[str(f.RECOVERY / "result.json")], remote, error

    def test_archive_moves_only_exact_failure_and_config_without_deletion(self):
        commands, result, remote, error = self.archive_fixture()
        self.assertIsNone(error)
        self.assertEqual(result["result"], "PHY_INVALID_CAPTURE_ARCHIVED")
        self.assertEqual(sum("mv" in c for c in commands), 2)
        self.assertTrue(result["no_delete"] and result["usb_closed"] and result["original_capture_invalid"])
        self.assertEqual(len(result["remaining"]), 7)
        self.assertIn("files/p34-observations/" + f.PROTECTED + "/snapshot-1.jsonl", remote)

    def test_archive_redirect_and_uncertain_move_stop_without_replay(self):
        for args, moves in ((dict(redirected=True), 0), (dict(uncertain=True), 1)):
            commands, result, _, error = self.archive_fixture(**args)
            self.assertIsNotNone(error)
            self.assertEqual(result["result"], "PHY_ARCHIVE_INCOMPLETE")
            self.assertEqual(sum("mv" in c for c in commands), moves)

    def test_exact_successor_reader_keeps_runtime_helpers_and_strict_guards(self):
        fixture = runpy.run_path(str(f.AREA / "src/tests/ota/test_p3_4_observation_capture.py"))
        reader = f.fixed_envelope()
        self.assertTrue(callable(reader.same_device))
        self.assertTrue(callable(reader.experiment_record))
        items = fixture["rows"]()
        items[-1:-1] = [dict(kind="line", message="OTA_PHY {}"),
                        dict(kind="line", message="OTA_PHY_CANCEL nativeAcknowledged=false")]
        items = [dict(row, seq=i) for i, row in enumerate(items, 1)]
        verify = lambda data: reader.verify(data, sentinel=fixture["SENTINEL"], target=fixture["TARGET"])
        result, messages = verify(fixture["encoded"](items))
        self.assertFalse(result["eligibleForThreshold"])
        self.assertIn("OTA_PHY {}", messages)
        with self.assertRaises(reader.CaptureError): verify(fixture["encoded"](items, dict(lost=1)))
        items[-2]["message"] = "OTA_PHY_CANCEL token=fixture"
        with self.assertRaises(reader.CaptureError): verify(fixture["encoded"](items))

    def test_observe_cannot_be_replayed(self):
        with self.assertRaisesRegex(RuntimeError, "no replay"):
            f.Trial(f.cli.Store(ROOT), "observe", checking=True)

    def test_candidate_starts_at_actual_retained_image(self):
        group = f.old.assets(f.cli.Store(ROOT), "prefer2m")
        self.assertEqual(group["receiver"]["sha256"], f.install.IMAGE)
        self.assertEqual(group["specification"]["target_version"], 30268)
        self.assertEqual(group["specification"]["androidPhyPolicy"], "prefer2m")
        expected = dict(androidPhyPolicy="prefer2m", runId="fixture", target="AA:BB")
        value = dict(schema=1, status="observed", configSha256="a" * 64,
            requestId="fixture", remoteId="AA:BB", policy="prefer2m", connectionGeneration=1,
            elapsedMicros=10, beforeReadStatus=0, beforeTxPhy=1, beforeRxPhy=1,
            txPhy=2, rxPhy=2, readStatus=0, updateStatus=0)
        f.old.verify_phy("OTA_PHY " + json.dumps(value), expected, "a" * 64)
        for change in (dict(txPhy=1), dict(rxPhy=1), dict(updateStatus=1), dict(configSha256="b" * 64)):
            with self.assertRaises(RuntimeError):
                f.old.verify_phy("OTA_PHY " + json.dumps(dict(value, **change)), expected, "a" * 64)

    def test_prestart_rejects_active_or_unknown_state_before_saving_plan(self):
        api = f.Trial.__new__(f.Trial)
        api.store = object()
        restored = dict(remaining=["a"] * 7, protected=dict(sha256="expected"))
        phone = dict(result="APP_INSPECTED", pid=None, config=None, usb_closed=True,
            stable_completed=True, health=dict(captureId=f.PROTECTED), capture_directories=7,
            snapshot_records={"snapshot-1.jsonl": dict(sha256="expected")})
        c = SimpleNamespace(save=lambda *a: self.fail("invalid prestart must not save a plan"))
        with patch.object(f, "recovery", return_value=(None, None, restored)):
            for change in (dict(pid=123), dict(config={}), dict(usb_closed=False),
                           dict(capture_directories=8), dict(stable_completed=False),
                           dict(health=dict(captureId="wrong"))):
                with self.assertRaises(RuntimeError):
                    api.prepare(c, f.OUT, dict(phone, **change), {})


if __name__ == "__main__":
    f.cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                  "isolated explicit root required")
    s = f.cli.Store(ROOT)
    s.checked(f.HOST)
    f.cli.require(not f.HOST.exists(), "preserve test evidence")
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Guards))
    log = s.raw(f.HOST / "tests.log", stream.getvalue().encode())
    s.write(f.HOST / "result.json", dict(passed=result.wasSuccessful(), count=result.testsRun,
        sources=f.sources(), log=log, hardware=False))
    print(stream.getvalue())
    sys.exit(not result.wasSuccessful())
