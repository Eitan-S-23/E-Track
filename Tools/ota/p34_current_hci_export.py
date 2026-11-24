"""Reusable current-trial HCI export under the user's standing diagnostic scope."""
import argparse
import io
from pathlib import Path
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_link_hci as old

cli = old.cli
AUTHORITY = "LINK-NEXT-02: user authorized this and future equivalent diagnostic reports on 2026-10-04"


def sources():
    return old.sources() + [cli.record(__file__), cli.record(ROOT / "tests/ota/test_p34_current_hci_export.py")]


class Exporter:
    def __init__(self, store, trial, status, out, tests):
        self.store = store
        self.trial, self.status, self.out, self.tests_path = (
            store.checked(p) for p in (trial, status, out, tests))
        self.runtime = store.checked(self.out / "runtime")

    def inputs(self, store):
        pointer, apk = old.link.inputs(store, self.trial)
        status = store.read(self.status / "result.json")
        closed = store.read(self.status / "runtime/closed.json")
        cli.require(status["result"] == "HCI_STATUS_READ" and status["prior"] == pointer and
            status["usb_closed"] and status["properties"]["persist.sys.bluetooth.btsnooplogmode"] == "full" and
            closed["worker_exit"] == 0 and not closed["forced_termination"], "current status unresolved")
        return pointer, apk

    def worker(self):
        clone = old.link.previous.measure.batch.clone(old.previous.worker,
            OUT=self.out, TESTS=self.tests_path, sources=sources,
            status=SimpleNamespace(inputs=self.inputs))
        clone(self.store)

    def preflight(self):
        names = ["intent.json", "result.json", "preflight.json", "generation-intent.json",
            "generation.stdout", "generated.json", "archive.json", "usb/server.log",
            "usb/commands.jsonl", "usb/ready.json", "usb/closed.json", "usb/host/home/.android"]
        names += ["hci-%02d.btsnoop" % i for i in range(1, 9)]
        for prefix in ("", "runtime/"):
            names += [prefix + "host/" + leaf for leaf in ("home", "appdata", "localappdata", "tmp",
                "home/config", "home/cache", "gh", "python", "gitconfig", "hooks")]
        for name in names:
            self.store.checked(self.out / name)
        self.store.checked(ROOT / ".cache/p34-cycles/device.lock")

    def arguments(self):
        return ["worker", "--trial", str(self.trial), "--status", str(self.status),
                "--out", str(self.out), "--tests", str(self.tests_path)]


def test(store, output):
    import unittest
    output = store.checked(output)
    cli.require(not output.parent.exists(), "preserve previous test evidence")
    store.checked(output.parent / "tests.log")
    sys.path.insert(0, str(ROOT / "tests/ota"))
    suite = unittest.defaultTestLoader.loadTestsFromNames(["test_p34_hci_export", "test_p34_hci_current",
        "test_p34_link_status", "test_p34_link_hci", "test_p34_current_hci_export"])
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    store.raw(output.parent / "tests.log", stream.getvalue().encode())
    store.write(output, dict(passed=result.wasSuccessful(), count=result.testsRun,
        sources=sources(), device_operations=0))
    print(stream.getvalue())
    cli.require(result.wasSuccessful(), "host export tests failed")


if __name__ == "__main__":
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                "explicit isolated root required")
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("mode", choices=("test", "check", "launch", "worker"))
    p.add_argument("--tests", type=Path, required=True)
    for name in ("trial", "status", "out"):
        p.add_argument("--" + name, type=Path)
    args = p.parse_args()
    store = cli.Store(ROOT)
    if args.mode == "test":
        test(store, args.tests)
    else:
        cli.require(all(getattr(args, k) is not None for k in ("trial", "status", "out")),
                    "trial/status/out required")
        api = Exporter(store, args.trial, args.status, args.out, args.tests)
        api.preflight()
        tested = store.read(api.tests_path)
        cli.require(tested["passed"] and tested["sources"] == sources(), "current source-bound tests required")
        proof = cli.record(api.tests_path)
        pointer, apk = api.inputs(store)
        owner = cli.load_module("current_export_owner", ROOT / ".cache/p3-4-screening-20260922/supervisor.py")
        if args.mode == "worker":
            cli.require(owner.owned.in_job(), "finite owned worker required")
            intent = store.read(api.out / "intent.json")
            cli.require(intent["sources"] == sources() and intent["tests"] == proof and
                intent["prior"] == pointer and intent["apk"] == apk["apk"] and
                intent["status"] == cli.record(api.status / "result.json"), "running export inputs changed")
            api.worker()
        else:
            cli.require(not api.out.exists(), "preserve spent/uncertain export; reconcile instead of regenerating")
            owner.owned.validate_launch(api.runtime, Path(__file__), api.arguments(), 1800, ["status", "stop"])
            if args.mode == "check":
                print("CURRENT_HCI_EXPORT_READY", pointer["sha256"])
            else:
                store.write(api.out / "intent.json", dict(time=cli.now(), authority=AUTHORITY,
                    sources=sources(), tests=proof, prior=pointer, apk=apk["apk"],
                    status=cli.record(api.status / "result.json"), maximum_reports_this_operation=1,
                    phone_output=old.previous.export.REMOTE, host_output=str(api.out), seconds=1800,
                    no_ota=True, no_install=True, delete_existing=False, whole_report_saved_on_host=False, upload=False))
                print(owner.owned.launch(api.runtime, Path(__file__), api.arguments(), 1800))
