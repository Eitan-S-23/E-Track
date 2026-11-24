"""Recover a completed bugreport from its original receipt; never generate one."""
import argparse
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import runpy
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_current_hci_export as current

cli = current.cli
legacy = current.old.previous
export = legacy.export
TEST = ROOT / "tests/ota/test_p34_hci_retrieve_existing.py"


def completed_generation(raw, receipt, before):
    cli.require(receipt["args"] == ["shell", "bugreportz", "-p"] and receipt["exit"] == 0 and
        receipt["stdout_bytes"] == len(raw) and receipt["stdout_sha256"] == hashlib.sha256(raw).hexdigest(),
        "original successful generation receipt required")
    remote = export.completed_report(raw)
    cli.require(PurePosixPath(remote).name not in before, "report was already present before generation")
    return remote


def inventory(raw):
    result = {}
    for line in raw.splitlines():
        parts = line.split()
        if not parts or not parts[-1].endswith(".zip"):
            continue
        cli.require(len(parts) == 8 and parts[0].startswith("-") and parts[4].isdigit(), "invalid ZIP inventory")
        name = PurePosixPath(export.report_path(export.REMOTE + "/" + parts[-1])).name
        cli.require(name not in result, "duplicate ZIP inventory")
        result[name] = int(parts[4])
    return result


def sources():
    return current.sources() + [cli.record(__file__), cli.record(TEST)]


class Retrieval:
    def __init__(self, s, trial, failed, out, tests):
        self.s = s
        self.trial, self.failed, self.out, self.tests = (s.checked(p) for p in (trial, failed, out, tests))

    def inputs(self):
        s, old = self.s, self.failed
        pointer, apk = current.old.link.inputs(s, self.trial)
        result, closed, usb = (s.read(old / p) for p in ("result.json", "runtime/closed.json", "usb/closed.json"))
        cli.require(result["result"] == "HCI_EXPORT_INCOMPLETE" and result["prior"] == pointer and
            result.get("detail") == "report did not complete; do not repeat" and
            closed["worker_exit"] == 1 and not closed["forced_termination"] and usb["port_closed"] and
            usb["stop_exit"] == usb["server_exit"] == usb["launcher_exit"] == 0 and
            usb["key_before"] == usb["key_after"], "reconcile original failure and owner closure first")
        raw = (old / "generation.stdout").read_bytes()
        commands = [json.loads(line) for line in (old / "usb/commands.jsonl").read_text().splitlines()]
        matches = [v for v in commands if v["args"] == ["shell", "bugreportz", "-p"]]
        cli.require(len(matches) == 1, "one original generation command required")
        remote = completed_generation(raw, matches[0], s.read(old / "preflight.json")["before"])
        intent = s.read(old / "intent.json")
        status = s.read(intent["status"]["path"])
        cli.require(cli.record(intent["status"]["path"]) == intent["status"] and intent["apk"] == apk["apk"],
                    "original APK/status bytes changed")
        return dict(prior=pointer, apk=apk["apk"], remote=remote, before=inventory(status["existing_reports"]),
            evidence=[cli.record(old / p) for p in ("generation.stdout", "usb/commands.jsonl", "preflight.json",
                "intent.json", "result.json", "runtime/closed.json", "usb/closed.json")])

    def preflight(self):
        current.Exporter(self.s, self.trial, self.failed, self.out, self.tests).preflight()
        for name in ("inventory-before.json", "inventory-after.json"):
            self.s.checked(self.out / name)

    def arguments(self):
        return ["worker", "--trial", str(self.trial), "--failed", str(self.failed),
                "--out", str(self.out), "--tests", str(self.tests)]

    def worker(self, admitted):
        b, d, p, lock = runpy.run_path(str(ROOT / "Tools/ota/p34_signing_migration.py"))["runtime"]()
        c = legacy.Evidence(self.s)
        result = dict(result="EXISTING_HCI_RETRIEVAL_INCOMPLETE", generated=False, no_ota=True, no_install=True)
        try:
            with lock.device_lock(), d["usb"](legacy.Backend(b, self.out), p, self.out):
                p.phone_identity()
                cli.require(d["installed"](b, p, admitted["apk"]["sha256"]) is not None, "installed APK changed")
                names = export.remote_preflight(c, p, self.out)
                name = PurePosixPath(admitted["remote"]).name
                cli.require(name in names, "completed report missing; do not regenerate")
                before = inventory(p.command(["shell", "ls", "-l", export.REMOTE]))
                cli.require(set(before) == set(admitted["before"]) | {name} and
                    all(before[k] == v for k, v in admitted["before"].items()), "existing reports changed")
                self.s.write(self.out / "inventory-before.json", before)
                result.update(legacy.retrieve(c, p, self.out, admitted["remote"]))
                after = inventory(p.command(["shell", "ls", "-l", export.REMOTE]))
                self.s.write(self.out / "inventory-after.json", after)
                cli.require(before == after, "report inventory changed during retrieval")
                result.update(existing_reports_preserved=True, remote=admitted["remote"], prior=admitted["prior"])
            result["usb_closed"] = True
        except Exception as error:
            result.update(error=type(error).__name__, detail=str(error))
        self.s.write(self.out / "result.json", result)
        print(json.dumps(result))
        cli.require("error" not in result, "preserve retrieval failure; never regenerate")


if __name__ == "__main__":
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                "explicit isolated root required")
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("mode", choices=("test", "check", "launch", "worker"))
    p.add_argument("--tests", type=Path, required=True)
    for name in ("trial", "failed", "out"): p.add_argument("--" + name, type=Path)
    a = p.parse_args()
    s = cli.Store(ROOT)
    tested = s.checked(a.tests)
    if a.mode == "test":
        import unittest
        cli.require(not tested.parent.exists(), "preserve test evidence")
        s.checked(tested.parent / "tests.log")
        sys.path.insert(0, str(ROOT / "tests/ota"))
        stream = io.StringIO()
        result = unittest.TextTestRunner(stream=stream, verbosity=2).run(
            unittest.defaultTestLoader.loadTestsFromNames(["test_p34_hci_export", "test_p34_hci_current",
                "test_p34_link_status", "test_p34_link_hci", "test_p34_current_hci_export", "test_p34_hci_retrieve_existing"]))
        s.raw(tested.parent / "tests.log", stream.getvalue().encode())
        s.write(tested, dict(passed=result.wasSuccessful(), count=result.testsRun, sources=sources(), device_operations=0))
        print(stream.getvalue())
        cli.require(result.wasSuccessful(), "retrieval tests failed")
    else:
        cli.require(all(getattr(a, n) is not None for n in ("trial", "failed", "out")), "all input bindings required")
        api = Retrieval(s, a.trial, a.failed, a.out, tested)
        api.preflight()
        test = s.read(tested)
        cli.require(test["passed"] and test["sources"] == sources(), "current retrieval tests required")
        admitted = api.inputs()
        owner = cli.load_module("hci_retrieval_owner", ROOT / ".cache/p3-4-screening-20260922/supervisor.py")
        if a.mode == "worker":
            intent = s.read(api.out / "intent.json")
            cli.require(owner.owned.in_job() and intent["sources"] == sources() and
                intent["inputs"] == admitted and intent["tests"] == cli.record(tested), "owned immutable retrieval required")
            api.worker(admitted)
        else:
            cli.require(not api.out.exists(), "preserve earlier retrieval")
            owner.owned.validate_launch(api.out / "runtime", Path(__file__), api.arguments(), 1800, ["status", "stop"])
            if a.mode == "check": print("EXISTING_REPORT_READY", admitted["remote"])
            else:
                s.write(api.out / "intent.json", dict(sources=sources(), inputs=admitted, tests=cli.record(tested),
                    no_generation=True, no_ota=True, no_install=True, no_delete=True, no_upload=True))
                print(owner.owned.launch(api.out / "runtime", Path(__file__), api.arguments(), 1800))
