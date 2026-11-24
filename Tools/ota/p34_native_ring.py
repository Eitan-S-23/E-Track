"""Read one completed trial's existing native Android log ring; never replay OTA."""
import argparse
import json
from pathlib import Path
import runpy
import sys

ROOT = Path(__file__).resolve().parents[2]
PKG = "com.wen.gaia.gaia.p34probe"
MAX_BYTES = 16 * 1024 * 1024


def ring_command(pid):
    if type(pid) is not int or pid <= 0:
        raise ValueError("exact positive original PID required")
    return ["logcat", "-d", "-b", "main", "-v", "epoch", "-v", "usec",
            "-t", "30000", "--pid=" + str(pid), "[FBP-Android]:V", "*:S"]


def capture(p, pid):
    command = ring_command(pid)
    if p.command(["shell", "pidof", PKG]).strip() != str(pid):
        raise ValueError("original App PID is no longer live; no restart")
    raw = p.command(command, timeout=45, binary=True)
    if type(raw) is not bytes or len(raw) > MAX_BYTES:
        raise ValueError("native ring exceeds capture bound")
    return raw


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trial", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if not (Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode):
        raise RuntimeError("explicit isolated project root required")
    sys.path.insert(0, str(ROOT / "Tools/ota"))
    import p34_batch_review as review
    cli = review.cli
    s = cli.Store(ROOT)
    out = s.checked(args.out)
    cli.require(not out.exists(), "preserve original collection")
    for name in ("intent.json", "result.json", "native.log", "host", "usb"):
        s.checked(out / name)
    pointer, report = review.load_report(s, s.checked(args.trial))
    launch = s.read(report["inputs"]["launch"]["path"])
    pid = report["summary"]["pid"]
    cli.require(pid == launch["pid"], "original PID binding differs")
    ring_command(pid)
    b, d, p, lock = runpy.run_path(str(ROOT / "Tools/ota/p34_signing_migration.py"))["runtime"]()
    s.write(out / "intent.json", dict(time=cli.now(), report=pointer, source=cli.record(__file__),
        pid=pid, command=ring_command(pid), no_phone_mutation=True, no_ota=True, no_system_report=True))
    value = dict(result="NATIVE_RING_INCOMPLETE", report=pointer, pid=pid,
                 no_phone_mutation=True, no_ota=True, no_system_report=True)
    try:
        with lock.device_lock(), d["usb"](b, p, out):
            p.phone_identity()
            cli.require(d["installed"](b, p, launch["apk"]["sha256"]) is not None, "installed APK changed")
            config = p.file_bytes(PKG, "files/p34-experiment.json", 8192)
            cli.require(config == Path(report["inputs"]["config"]["path"]).read_bytes(), "runtime config changed")
            raw = capture(p, pid)
            s.raw(out / "native.log", raw)
            value.update(result="NATIVE_RING_COLLECTED", log=cli.record(out / "native.log"),
                         capture_completeness="NOT_YET_CORRELATED", timing_attribution="NOT_ANALYZED")
        value["usb_closed"] = True
    except Exception as error:
        value.update(error=type(error).__name__, detail=str(error))
    s.write(out / "result.json", dict(time=cli.now(), **value))
    print(json.dumps(value), flush=True)
    cli.require("error" not in value and value.get("usb_closed"), "collection incomplete; no OTA replay")


if __name__ == "__main__":
    main()
