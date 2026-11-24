"""One authorized current-trial system report; reuse bounded HCI-only extraction."""
import argparse
import io
from pathlib import Path
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_hci_current as previous
import p34_link_status as link

cli = link.cli
AREA = ROOT / ".cache/p34-half-erase"
TRIAL = AREA / "trials/measure"
STATUS = AREA / "link-status/status-003"
OUT = AREA / "hci-export-001"
RUNTIME = AREA / "runtime/hci-export-001"
TESTS = AREA / "hci-export-tests-001/result.json"


def sources():
    paths = [Path(__file__), Path(previous.__file__), Path(previous.export.__file__), Path(link.__file__),
        ROOT / "tests/ota/test_p34_link_hci.py", ROOT / "tests/ota/test_p34_hci_current.py",
        ROOT / "tests/ota/test_p34_hci_export.py", ROOT / "tests/ota/test_p34_link_status.py",
        ROOT / ".cache/p34-next/device.py", ROOT / ".cache/p3-4-screening-20260922/phone.py",
        ROOT / "Tools/ota/p34_signing_migration.py"]
    return [cli.record(p) for p in paths]


def inputs(s):
    pointer, apk = link.inputs(s, TRIAL)
    report = s.read(pointer["path"])
    cli.require(report["summary"]["input"]["targetVersionCode"] == 30266, "wrong current trial")
    status = s.read(STATUS / "result.json")
    closed = s.read(STATUS / "runtime/closed.json")
    cli.require(status["result"] == "HCI_STATUS_READ" and status["prior"] == pointer and
                status["usb_closed"] and status["properties"]["persist.sys.bluetooth.btsnooplogmode"] == "full" and
                closed["worker_exit"] == 0 and not closed["forced_termination"], "current status unresolved")
    return pointer, apk


def worker(s):
    clone = link.previous.measure.batch.clone(previous.worker, OUT=OUT, TESTS=TESTS,
        sources=sources, status=SimpleNamespace(inputs=inputs))
    clone(s)


def tests(s):
    value = s.read(TESTS)
    cli.require(value["passed"] and value["sources"] == sources(), "current exporter tests required")
    return cli.record(TESTS)


if __name__ == "__main__":
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                "explicit isolated root required")
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("mode", choices=("test", "check", "launch", "worker"))
    a = p.parse_args()
    s = cli.Store(ROOT)
    if a.mode == "test":
        import unittest
        cli.require(not TESTS.parent.exists(), "preserve host tests")
        for name in ("result.json", "tests.log"): s.checked(TESTS.parent / name)
        sys.path.insert(0, str(ROOT / "tests/ota"))
        suite = unittest.defaultTestLoader.loadTestsFromNames(
            ["test_p34_hci_export", "test_p34_hci_current", "test_p34_link_status", "test_p34_link_hci"])
        stream = io.StringIO()
        result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
        s.raw(TESTS.parent / "tests.log", stream.getvalue().encode())
        s.write(TESTS, dict(passed=result.wasSuccessful(), count=result.testsRun, sources=sources(), device_operations=0))
        print(stream.getvalue())
        cli.require(result.wasSuccessful(), "host tests failed")
    else:
        proof = tests(s)
        pointer, apk = inputs(s)
        for name in ("intent.json", "result.json", "preflight.json", "generation-intent.json",
                     "generation.stdout", "generated.json", "archive.json", "usb", "host"):
            s.checked(OUT / name)
        for i in range(1, 9): s.checked(OUT / ("hci-%02d.btsnoop" % i))
        owner = cli.load_module("link_hci_owner", ROOT / ".cache/p3-4-screening-20260922/supervisor.py")
        if a.mode == "worker":
            cli.require(owner.owned.in_job(), "finite worker required")
            intent = s.read(OUT / "intent.json")
            cli.require(intent["sources"] == sources() and intent["tests"] == proof and
                        intent["prior"] == pointer and intent["apk"] == apk["apk"], "running exporter inputs changed")
            worker(s)
        else:
            owner.owned.validate_launch(RUNTIME, Path(__file__), ["worker"], 1800, ["status", "stop"])
            cli.require(not OUT.exists(), "report scope already reserved; reconcile only")
            if a.mode == "check":
                print("CURRENT_HCI_EXPORT_READY", pointer["sha256"], "one report; no writes")
            else:
                s.write(OUT / "intent.json", dict(time=cli.now(), sources=sources(), tests=proof,
                    prior=pointer, apk=apk["apk"], status=cli.record(STATUS / "result.json"), maximum_reports=1,
                    authority="User approved LINK-NEXT-01 new report and sidecars in this thread",
                    phone_output=previous.export.REMOTE, host_output=str(OUT), seconds=1800,
                    no_ota=True, no_install=True, delete_existing=False, whole_report_saved_on_host=False, upload=False))
                print(owner.owned.launch(RUNTIME, Path(__file__), ["worker"], 1800))
