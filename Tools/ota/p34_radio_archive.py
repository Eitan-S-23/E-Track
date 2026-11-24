"""Preserve one verified inactive capture on host and move its phone directory."""
import argparse
import hashlib
import json
from pathlib import Path
import runpy
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_radio_trial as radio
import p34_radio_install as install

cli = radio.cli
AREA = radio.AREA
TEST = ROOT / "tests/ota/test_p34_radio_archive.py"
ARCHIVE = "files/p34-archived-observations"


def proof(s, root):
    pointer = s.read(root / "analysis/latest.json")
    cli.require(cli.record(pointer["report"]["path"]) == pointer["report"], "analysis changed")
    report = s.read(pointer["report"]["path"])
    cli.require(report["result"] == "FULL_INSTALL_VERIFIED" and report["summary"]["outcome"] == "completed",
                "verified completed capture required")
    for item in [*report["inputs"].values(), report["after"]]:
        cli.require(cli.record(s.checked(item["path"])) == item, "original evidence changed")
    closure = s.read(report["after"]["path"])
    cli.require(closure["reader_closed"] and closure["retained_verified"] and "cleanup_error" not in closure,
                "native reader unresolved")
    for name in ("coordinator", "network", "s04"):
        closed = s.read(root / "runtime" / name / "closed.json")
        cli.require(closed["worker_exit"] == 0 and not closed["forced_termination"], "trial owner not closed")
    return report


def names_valid(names, selected, protected):
    cli.require(2 <= len(names) <= 8 and len(set(names)) == len(names) and
                all(radio.backend.CAPTURE_NAME.fullmatch(n) for n in names), "invalid capture inventory")
    cli.require(selected != protected and selected in names and protected == sorted(names)[-1],
                "selected capture is current, absent or ambiguous")


def healthy(raw, capture):
    value = json.loads(raw)
    cli.require(value["captureId"] == capture and value["healthy"] is True and value["lost"] == 0 and
                value["error"] is None and value["upgradeStarts"] == value["upgradeEnds"] == 1 and
                value["outcome"] == "completed", "capture not healthy and completed")


def files_valid(names):
    cli.require(len(set(names)) == len(names) and set(names) in (
        {"events.jsonl", "health.json", "snapshot-1.jsonl"},
        {"events.jsonl", "health.json", "snapshot-1.jsonl", "health.json.tmp"}),
        "unknown capture files; do not move")


def equal_snapshot(raw, report):
    record = report["inputs"]["snapshot"]
    cli.require(len(raw) == record["bytes"] and hashlib.sha256(raw).hexdigest() ==
                record["sha256"] == report["summary"]["rawSha256"], "snapshot differs from verified original")


def worker(s, after, out):
    index = radio.ORDER.index(after)
    current = proof(s, radio.TRIALS / after)
    previous = proof(s, radio.old.TRIAL if index == 0 else radio.TRIALS / radio.ORDER[index - 1])
    selected, protected = previous["summary"]["captureId"], current["summary"]["captureId"]
    source, active = ("files/p34-observations/" + x for x in (selected, protected))
    target = ARCHIVE + "/" + selected
    b, d, p, lock = runpy.run_path(str(ROOT / "Tools/ota/p34_signing_migration.py"))["runtime"]()
    checked = lambda path, new=False: radio.backend.checked_phone_path(install, p, path, new_leaf=new)
    def exists(path):
        return p.command(["exec-out", "run-as", install.PKG, "ls", "-d", path], check=False).strip() == path
    def listing(path):
        return p.command(["exec-out", "run-as", install.PKG, "ls", "-1", path]).splitlines()
    def read(path):
        data = p.command(["exec-out", "run-as", install.PKG, "head", "-c", "16777217", path],
                         timeout=30, binary=True)
        cli.require(len(data) <= 16777216, "capture file exceeds archive bound")
        return data
    value = dict(result="CAPTURE_ARCHIVE_INCOMPLETE", no_delete=True, no_ota=True,
                 selected=selected, protected=protected, destination=target)
    try:
        with lock.device_lock(), d["usb"](b, p, out):
            p.phone_identity()
            d["installed"](b, p, s.read(radio.APK)["apk"]["sha256"])
            before = listing("files/p34-observations")
            names_valid(before, selected, protected)
            checked(active)
            healthy(read(active + "/health.json"), protected)
            protected_raw = read(active + "/snapshot-1.jsonl")
            equal_snapshot(protected_raw, current)
            config = read("files/p34-experiment.json")
            cli.require(hashlib.sha256(config).hexdigest() == current["inputs"]["config"]["sha256"],
                        "active runtime configuration changed")
            pid = p.command(["shell", "pidof", install.PKG], check=False).strip()
            cli.require(pid in ("", str(current["summary"]["pid"])), "different App invocation")
            s.write(out / "stop-intent.json", dict(pid=pid, completed_capture=protected))
            p.command(["shell", "am", "force-stop", install.PKG])
            cli.require(not p.command(["shell", "pidof", install.PKG], check=False).strip(), "App not stopped")
            checked(source)
            files = listing(source)
            files_valid(files)
            saved = {}
            for name in files:
                checked(source + "/" + name)
                saved[name] = read(source + "/" + name)
            healthy(saved["health.json"], selected)
            equal_snapshot(saved["snapshot-1.jsonl"], previous)
            host = {name:s.raw(out / "capture" / name, data) for name, data in saved.items()}
            cli.require(all(cli.record(item["path"]) == item for item in host.values()), "host archive readback failed")
            cli.require(listing(source) == files and all(read(source + "/" + name) == data for name,data in saved.items()),
                        "source changed during archival")
            parent_exists = exists(ARCHIVE)
            checked(ARCHIVE, not parent_exists)
            if not parent_exists:
                s.write(out / "mkdir-intent.json", dict(path=ARCHIVE))
                p.command(["exec-out", "run-as", install.PKG, "mkdir", ARCHIVE])
            checked(ARCHIVE)
            checked(target, True)
            cli.require(not exists(target), "archive destination exists; reconcile, never overwrite")
            cli.require(not p.command(["shell", "pidof", install.PKG], check=False).strip(), "App restarted")
            s.write(out / "move-intent.json", dict(source=checked(source), destination=checked(target, True),
                before=before, host=host, selected=selected, protected=protected))
            p.command(["exec-out", "run-as", install.PKG, "mv", "-n", source, target])
            checked(target)
            cli.require(not exists(source) and listing(target) == files and
                        all(read(target + "/" + name) == data for name,data in saved.items()), "archive move unresolved")
            remaining = listing("files/p34-observations")
            cli.require(set(remaining) == set(before) - {selected} and
                        read(active + "/snapshot-1.jsonl") == protected_raw and
                        read("files/p34-experiment.json") == config, "protected App state changed")
            value.update(result="INACTIVE_CAPTURE_ARCHIVED_VERIFIED", host=host, remaining=remaining,
                         app_stopped=True, protected_snapshot_unchanged=True, configuration_unchanged=True)
        value["usb_closed"] = True
    except Exception as error:
        value.update(error=type(error).__name__, detail=str(error))
    s.write(out / "result.json", dict(time=cli.now(), **value))
    print(json.dumps(value), flush=True)
    cli.require("error" not in value, "archive outcome requires reconciliation; do not repeat")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("launch", "worker"))
    parser.add_argument("--after", choices=radio.ORDER[:-1], required=True)
    args = parser.parse_args()
    s = cli.Store(ROOT)
    out = s.checked(AREA / "archive" / args.after)
    tests = s.read(AREA / "archive-tests/result.json")
    cli.require(tests["result"] == "PASS" and tests["source"] == cli.record(__file__) and
                tests["test"] == cli.record(TEST), "source-bound archive tests required")
    supervisor = cli.load_module("radio_archive_owner", ROOT / ".cache/p3-4-screening-20260922/supervisor.py")
    if args.mode == "launch":
        cli.require(not out.exists(), "archive attempt already exists")
        for name in ("intent.json", "result.json", "stop-intent.json", "mkdir-intent.json", "move-intent.json",
                     "capture", "usb", "host"):
            s.checked(out / name)
        s.write(out / "intent.json", dict(source=cli.record(__file__), tests=tests, after=args.after,
            scope="one inactive verified capture; host copy plus App-internal move; no deletion or OTA"))
        print(supervisor.owned.launch(AREA / "runtime" / ("archive-" + args.after), Path(__file__),
            ["worker", "--after", args.after], 600), flush=True)
    else:
        cli.require(supervisor.owned.in_job(), "finite archive owner required")
        worker(s, args.after, out)


if __name__ == "__main__":
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                "explicit root and isolated Python required")
    main()
