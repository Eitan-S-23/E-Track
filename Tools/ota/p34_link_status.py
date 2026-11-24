"""Reuse the read-only HCI status check with any verified, closed current trial."""
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_hci_status as previous

cli = previous.cli


def inputs(store, trial):
    pointer, report = previous.review.load_report(store, trial)
    launch = store.read(report["inputs"]["launch"]["path"])
    apk = launch["apk"]
    cli.require(cli.record(store.checked(apk["path"])) == apk, "installed APK input changed")
    return pointer, dict(apk=apk)


def worker(store, trial, out):
    # Clone the function's globals, never mutate the original source or live module.
    clone = previous.measure.batch.clone(previous.worker, OUT=out,
        inputs=lambda s: inputs(s, trial))
    clone(store)


if __name__ == "__main__":
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                "explicit isolated root required")
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("mode", choices=("check", "launch", "worker"))
    p.add_argument("--trial", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    s = cli.Store(ROOT)
    trial, out = s.checked(a.trial), s.checked(a.out)
    # The existing reader includes the safe report inventory only for this leaf.
    cli.require(out.name == "status-003", "use a fresh parent with the inventory-enabled status-003 leaf")
    pointer, apk = inputs(s, trial)
    source = [cli.record(__file__), cli.record(previous.__file__),
              cli.record(ROOT / "tests/ota/test_p34_link_status.py")]
    for name in ("intent.json", "result.json", "host", "usb", "runtime"): s.checked(out / name)
    if a.mode == "check":
        cli.require(not out.exists(), "preserve earlier status")
        print("LINK_STATUS_INPUTS_VERIFIED", pointer["sha256"], apk["apk"]["sha256"])
    elif a.mode == "launch":
        cli.require(not out.exists(), "preserve earlier status")
        s.write(out / "intent.json", dict(sources=source, report=pointer, apk=apk["apk"],
            phone_read_only=True, no_ota=True, no_install=True, no_system_report=True))
        owner = cli.load_module("closed_trial_status_owner", ROOT / ".cache/p3-4-screening-20260922/supervisor.py")
        print(owner.owned.launch(out / "runtime", Path(__file__),
            ["worker", "--trial", str(trial), "--out", str(out)], 600))
    else:
        owner = cli.load_module("closed_trial_status_owner", ROOT / ".cache/p3-4-screening-20260922/supervisor.py")
        cli.require(owner.owned.in_job(), "finite worker required")
        intent = s.read(out / "intent.json")
        cli.require(intent["sources"] == source and intent["report"] == pointer and intent["apk"] == apk["apk"],
                    "running status inputs changed")
        worker(s, trial, out)
