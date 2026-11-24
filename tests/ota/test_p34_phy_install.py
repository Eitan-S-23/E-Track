"""PHY install adapter guards, with no phone commands or APK installation."""
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
import p34_phy_install as f


class Guards(unittest.TestCase):
    def test_actual_retained_identity(self):
        _, value = f.review.load_report(f.cli.Store(ROOT), f.PRIOR)
        f.validate_retained(value)
        for key, wrong in [("targetVersionCode", 30265), ("targetImageSha256", "0" * 64)]:
            bad = copy.deepcopy(value)
            bad["summary"]["input"][key] = wrong
            with self.assertRaises(RuntimeError): f.validate_retained(bad)

    def test_apk_and_hosts_must_match(self):
        apk = dict(sha=f.SHA, certificate_sha256=f.CERT,
            metadata=dict(application_id=f.PKG, release_signing=False))
        hosts = [dict(host=name, development_result="PASS", scope="all",
            source_before=dict(head=f.SHA, clean=True)) for name in ("Linux", "Windows")]
        native = [dict(passed=True), dict(passed=True)]
        f.validate_apk(apk, hosts, native)
        for key in ("sha", "certificate_sha256"):
            with self.assertRaises(RuntimeError): f.validate_apk(dict(apk, **{key: "wrong"}), hosts, native)
        for wrong in ([hosts[0]], [hosts[0], hosts[0]], [dict(hosts[0], scope="ota"), hosts[1]]):
            with self.assertRaises(RuntimeError): f.validate_apk(apk, wrong, native)
        with self.assertRaises(RuntimeError): f.validate_apk(apk, hosts, [dict(passed=False), native[1]])

    def test_sleeping_phone_never_stops_or_installs(self):
        commands, values = [], {}
        def command(args, **kwargs):
            commands.append(args)
            self.assertEqual(args, ["shell", "dumpsys", "power"])
            return "mWakefulness=Asleep\n"
        phone = SimpleNamespace(phone_identity=lambda: None, command=command)
        runtime = lambda: (None, dict(usb=lambda *args: nullcontext(),
            installed=lambda *args: dict(sha256=f.OLD_SHA)), phone,
            SimpleNamespace(device_lock=nullcontext))
        loader = SimpleNamespace(run_path=lambda path: dict(runtime=runtime))
        store = SimpleNamespace(raw=lambda path, data: values.update({str(path): data}),
            write=lambda path, data: values.update({str(path): data}))
        f.worker(store, input_reader=lambda s: ({}, dict(summary=dict(captureId="retained"))), runtime_loader=loader)
        result = values[str(f.OUT / "result.json")]
        self.assertEqual(result["result"], "NEEDS_PHONE_WAKE_NO_INSTALL_ATTEMPTED")
        self.assertTrue(result["usb_closed"] and result["no_uninstall"] and result["no_ota"])
        self.assertEqual(len(commands), 1)
        self.assertFalse(any("intent.json" in key for key in values))

    def test_missing_old_apk_never_mutates_phone(self):
        values = {}
        phone = SimpleNamespace(phone_identity=lambda: None,
            command=lambda *args, **kwargs: self.fail("must stop before phone mutation"))
        runtime = lambda: (None, dict(usb=lambda *args: nullcontext(), installed=lambda *args: None),
            phone, SimpleNamespace(device_lock=nullcontext))
        store = SimpleNamespace(write=lambda path, data: values.update({str(path): data}))
        f.worker(store, input_reader=lambda s: ({}, dict(summary=dict(captureId="retained"))),
            runtime_loader=SimpleNamespace(run_path=lambda path: dict(runtime=runtime)))
        self.assertEqual(values[str(f.OUT / "result.json")]["result"], "BATCH_INSTALL_INCOMPLETE")
        self.assertEqual(values[str(f.OUT / "result.json")]["error"], "RuntimeError")


if __name__ == "__main__":
    f.cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                  "explicit isolated root required")
    s = f.cli.Store(ROOT)
    s.checked(f.HOST)
    f.cli.require(not f.HOST.exists(), "preserve test evidence")
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Guards))
    log = s.raw(f.HOST / "tests.log", stream.getvalue().encode())
    s.write(f.HOST / "result.json", dict(result="PASS" if result.wasSuccessful() else "FAIL",
        sources=f.sources(), tests=result.testsRun, log=log, hardware=False))
    print(stream.getvalue())
    sys.exit(not result.wasSuccessful())
