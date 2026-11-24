"""Recorder repair guards with simulated USB only; no installation or OTA."""
import copy
from contextlib import nullcontext
import io
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_phy_logfix_install as f


class Guards(unittest.TestCase):
    def test_retained_requires_full_app_boot_and_idle_confirmation(self):
        s = f.cli.Store(ROOT)
        proof = s.read(f.readback.OUT / "result.json")
        closure = s.read(proof["checkpoint"]["path"])
        f.validate_retained(proof, closure)
        for phase in ("initial_identity", "final_identity"):
            for image in ("app", "boot"):
                bad = copy.deepcopy(closure)
                bad[phase][image]["sha256"] = "0" * 64
                with self.assertRaises(RuntimeError): f.validate_retained(proof, bad)
        for key in ("confirm_done", "state_snapped", "sd_ready"):
            bad = copy.deepcopy(closure)
            bad["final_state"][key] = 0
            with self.assertRaises(RuntimeError): f.validate_retained(proof, bad)
        with self.assertRaises(RuntimeError):
            f.validate_retained(dict(proof, measurement_eligible=True), closure)

    def test_invalid_health_is_not_relabelled_healthy(self):
        h = json.loads((f.failed.OUT / "capture/health.json").read_bytes())
        f.validate_health(json.dumps(h))
        for update in (dict(healthy=True), dict(lost=0), dict(error=None),
                       dict(captureId="wrong"), dict(upgradeEnds=1)):
            with self.assertRaises(RuntimeError): f.validate_health(json.dumps(dict(h, **update)))

    def exercise(self, *, awake=True, old=True, reply="Success", corrupt=False):
        commands, writes = [], {}
        saved = {p.name: p.read_bytes() for p in (f.failed.OUT / "capture").iterdir()}
        config = (f.failed.OUT / "runtime-config.json").read_bytes()
        stopped = installed = False
        report = dict(apk=dict(path="fixture.apk", sha256="new"))
        def command(args, **kwargs):
            nonlocal stopped, installed
            commands.append(args)
            if args == ["shell", "dumpsys", "power"]:
                return "mWakefulness=" + ("Awake" if awake else "Asleep")
            if args == ["shell", "pidof", f.PKG]: return "" if stopped else str(f.failed.PID)
            if args == ["shell", "am", "force-stop", f.PKG]:
                stopped = True
                return ""
            if args == ["exec-out", "run-as", f.PKG, "ls", "-1", f.REMOTE]:
                return "\n".join(saved)
            if args == ["shell", "dumpsys", "package", f.PKG]: return "permissions"
            if args == ["install", "-r", "--no-streaming", "fixture.apk"]:
                installed = True
                return reply
            self.fail("unexpected phone operation: " + str(args))
        def read(pkg, path, limit):
            self.assertEqual(pkg, f.PKG)
            data = config if path == "files/p34-experiment.json" else saved[path.split("/")[-1]]
            return data + b"changed" if corrupt and installed and path.endswith("events.jsonl") else data
        phone = SimpleNamespace(phone_identity=lambda: None, command=command, file_bytes=read)
        route = lambda: (None, dict(usb=lambda *a: nullcontext(),
            installed=lambda *a: dict(sha256=a[-1]) if old else None,
            permission_state=lambda *a: {"bluetooth": True}), phone, SimpleNamespace(device_lock=nullcontext))
        store = SimpleNamespace(raw=lambda p, v: writes.update({str(p): v}),
                                write=lambda p, v: writes.update({str(p): v}))
        error = None
        try:
            f.worker(store, input_reader=lambda s: (report, dict(checkpoint={"fixture": True})), runtime_loader=route)
        except RuntimeError as caught:
            error = caught
        return commands, writes, writes[str(f.OUT / "result.json")], error

    def test_sleeping_or_wrong_apk_never_mutates(self):
        for args in (dict(awake=False), dict(old=False)):
            commands, writes, result, _ = self.exercise(**args)
            self.assertFalse(any(c[0] == "install" or "force-stop" in c for c in commands))
            self.assertFalse(any(p.endswith("intent.json") for p in writes))
            self.assertNotEqual(result["result"], "PHY_LOGFIX_SAME_SIGNER_INSTALLED")

    def test_same_signer_install_preserves_invalid_bytes_and_settings(self):
        commands, writes, result, error = self.exercise()
        self.assertIsNone(error)
        self.assertEqual(result["result"], "PHY_LOGFIX_SAME_SIGNER_INSTALLED")
        self.assertTrue(result["original_invalid_capture_preserved"] and result["permissions_preserved"])
        self.assertTrue(result["usb_closed"] and result["no_ota"] and not result["app_launched"])
        self.assertEqual(sum(c[0] == "install" for c in commands), 1)
        self.assertEqual(writes[str(f.OUT / "capture/events.jsonl")],
                         (f.failed.OUT / "capture/events.jsonl").read_bytes())

    def test_uncertain_install_and_changed_evidence_are_never_retried(self):
        for args in (dict(reply="Failure [fixture]"), dict(corrupt=True)):
            commands, _, result, error = self.exercise(**args)
            self.assertIsNotNone(error)
            self.assertEqual(sum(c[0] == "install" for c in commands), 1)
            self.assertEqual(result["result"], "PHY_LOGFIX_INSTALL_INCOMPLETE")
            self.assertNotIn("original_invalid_capture_preserved", result)


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
