"""Reusable same-signer APK update after a closed verified OTA; no OTA replay."""
import argparse
import io
from pathlib import Path
import runpy
import sys
from types import FunctionType, SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_phy_install as old

cli = old.cli
TEST = ROOT / "tests/ota/test_p34_verified_install.py"


def sources():
    return old.sources() + [cli.record(__file__), cli.record(TEST)]


class Installer:
    def __init__(self, store, trial, apk, commit, out):
        self.store = store
        self.trial, self.apk, self.out = (store.checked(p) for p in (trial, apk, out))
        cli.require(len(commit) == 40 and all(c in "0123456789abcdef" for c in commit), "exact source commit required")
        self.commit = commit

    def inputs(self, s):
        self.previous_report, completed = old.review.load_report(s, self.trial)
        report = s.read(self.apk)
        for item in [report["apk"], *report["host_reports"], *report["native_reports"]]:
            cli.require(cli.record(s.checked(item["path"])) == item, "APK or original CI bytes changed")
        validate = FunctionType(old.validate_apk.__code__, dict(old.validate_apk.__globals__, SHA=self.commit))
        validate(report, [s.read(v["path"]) for v in report["host_reports"]],
                 [s.read(v["path"]) for v in report["native_reports"]])
        signer = runpy.run_path(str(ROOT / "Tools/ota/p34_signing_artifacts.py"))["apk_certificate"]
        cli.require(signer(Path(report["apk"]["path"]).read_bytes()) == old.CERT, "actual APK signer differs")
        prior = s.read(completed["inputs"]["launch"]["path"])["apk"]
        cli.require(cli.record(s.checked(prior["path"])) == prior and prior["sha256"] != report["apk"]["sha256"],
                    "prior APK changed or replacement is unnecessary")
        return report, completed, prior

    def preflight(self):
        names = ["intent.json", "result.json", "power.txt", "stop-intent.json", "install-intent.json",
                 "runtime-config.json", "capture/events.jsonl", "capture/health.json", "capture/health.json.tmp",
                 "capture/snapshot-1.jsonl"]
        for prefix in ("usb/", "runtime/"):
            names += [prefix + n for n in ("config.json", "ready.json", "closed.json", "state.json",
                "state.json.tmp", "worker.log", "server.log", "commands.jsonl", "host/home/.android")]
        for prefix in ("", "runtime/", "usb/"):
            names += [prefix + "host/" + leaf for leaf in ("home", "appdata", "localappdata", "tmp",
                "home/config", "home/cache", "gh", "python", "gitconfig", "hooks")]
        for name in names: self.store.checked(self.out / name)
        self.store.checked(ROOT / ".cache/p34-cycles/device.lock")

    def arguments(self, tests):
        return ["worker", "--trial", str(self.trial), "--apk", str(self.apk), "--commit", self.commit,
                "--out", str(self.out), "--tests", str(tests)]

    def worker(self, *, input_reader=None, runtime_loader=runpy):
        report, completed, prior = (input_reader or self.inputs)(self.store)
        operation = FunctionType(old.original.worker.__code__, dict(old.original.worker.__globals__,
            inputs=lambda s: (report, completed), OUT=self.out,
            prior=SimpleNamespace(PKG=old.PKG, OLD_SHA=prior["sha256"]), runpy=runtime_loader))
        operation(self.store)
        result = self.store.read(self.out / "result.json")
        cli.require("error" not in result and result.get("usb_closed") is True,
                    "preserve uncertain installation; reconcile before another attempt")


def tests(store, out):
    import unittest
    cli.require(not out.parent.exists(), "preserve earlier tests")
    store.checked(out.parent / "tests.log")
    sys.path.insert(0, str(ROOT / "tests/ota"))
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromName("test_p34_verified_install"))
    store.raw(out.parent / "tests.log", stream.getvalue().encode())
    store.write(out, dict(passed=result.wasSuccessful(), count=result.testsRun, sources=sources(), device_operations=0))
    print(stream.getvalue())
    cli.require(result.wasSuccessful(), "installer guard tests failed")


if __name__ == "__main__":
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                "explicit isolated project root required")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("test", "check", "launch", "worker"))
    parser.add_argument("--tests", type=Path, required=True)
    for name in ("trial", "apk", "out"): parser.add_argument("--" + name, type=Path)
    parser.add_argument("--commit")
    a = parser.parse_args()
    s = cli.Store(ROOT)
    tested = s.checked(a.tests)
    if a.mode == "test":
        tests(s, tested)
    else:
        cli.require(all(getattr(a, n) is not None for n in ("trial", "apk", "out", "commit")), "all bindings required")
        api = Installer(s, a.trial, a.apk, a.commit, a.out)
        api.preflight()
        proof = s.read(tested)
        cli.require(proof["passed"] and proof["sources"] == sources(), "current installer tests required")
        report, completed, prior = api.inputs(s)
        owner = cli.load_module("verified_install_owner", ROOT / ".cache/p3-4-screening-20260922/supervisor.py")
        if a.mode == "worker":
            intent = s.read(api.out / "intent.json")
            cli.require(owner.owned.in_job() and intent["sources"] == sources() and
                intent["tests"] == cli.record(tested) and intent["apk"] == report["apk"] and
                intent["prior_apk"] == prior and intent["report"] == cli.record(api.apk) and
                intent["prior_report"] == api.previous_report, "owned source-pinned installer required")
            api.worker()
        else:
            cli.require(not api.out.exists(), "preserve prior/uncertain installation; reconcile first")
            owner.owned.validate_launch(api.out / "runtime", Path(__file__), api.arguments(tested), 600, ["status", "stop"])
            if a.mode == "check":
                print("VERIFIED_INSTALL_INPUTS_READY", report["apk"]["sha256"])
            else:
                s.write(api.out / "intent.json", dict(time=cli.now(), sources=sources(), tests=cli.record(tested),
                    apk=report["apk"], prior_apk=prior, report=cli.record(api.apk), prior_report=api.previous_report,
                    retained=completed["summary"]["input"], no_ota=True, no_uninstall=True, no_data_clear=True,
                    purpose="same-signer development update; retain config, permissions and original completed snapshot"))
                print(owner.owned.launch(api.out / "runtime", Path(__file__), api.arguments(tested), 600))
