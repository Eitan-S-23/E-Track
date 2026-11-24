"""Reconcile the observed PHY trial without OTA, reset, halt or flash."""
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_phy_trial_resume as trial
import p34_phy_failure as failure

cli, AREA = trial.cli, trial.AREA
OUT = AREA / "readback-001"


def inputs(s):
    failure.inputs(s)
    closed = s.read(AREA / "runtime/reconcile-001/closed.json")
    recovered = s.read(failure.OUT / "result.json")
    cli.require(closed["worker_exit"] == 0 and not closed["forced_termination"] and
                recovered["usb_closed"] and recovered["result"] == "PHY_ORIGINAL_BYTES_COLLECTED",
                "original USB owner must be closed")
    trial.tests(s)
    return [cli.record(p) for p in (Path(__file__), Path(trial.__file__),
        failure.OUT / "result.json", AREA / "runtime/reconcile-001/closed.json")]


def worker(s):
    value = dict(result="PHY_TARGET_READBACK_INCOMPLETE", no_ota=True, no_reset=True,
                 no_halt=True, no_flash=True, measurement_eligible=False)
    try:
        api = trial.Trial(s, "observe")
        c = api.installed_context(OUT)
        api.preflight(c, OUT)
        cli.require(c.receiver_image_sha == api.assets["target"]["sha256"], "wrong target context")
        c.native_authority()
        os.environ.update(c.environment())
        lock = c.load("phy_readback_lock", ROOT / "Tools/ota/repeat_cycle.py")
        with lock.device_lock():
            checkpoint = api.install_checkpoint(c, OUT)
            api.verify_install_checkpoint(c, checkpoint["path"])
        value.update(result="PHY_TARGET_30267_RAW_AND_BOOT_CONFIRMED", checkpoint=checkpoint,
                     retained_version=30267, target=api.assets["target"],
                     original_capture_failure_preserved=True)
    except Exception as error:
        value.update(error=type(error).__name__, detail=str(error))
    s.write(OUT / "result.json", dict(time=cli.now(), **value))
    print(json.dumps(value), flush=True)
    cli.require("error" not in value, "preserve readback; reconcile actual device state")


if __name__ == "__main__":
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                "isolated explicit root required")
    cli.require(sys.argv[1:] in (["launch"], ["worker"]), "exact mode required")
    s = cli.Store(ROOT)
    sources = inputs(s)
    owner = cli.load_module("phy_readback_owner", ROOT / ".cache/p3-4-screening-20260922/supervisor.py")
    if sys.argv[1] == "launch":
        cli.require(not OUT.exists(), "preserve original readback")
        for name in ("intent.json", "result.json", "installed-mcu", "host"):
            s.checked(OUT / name)
        s.write(OUT / "intent.json", dict(time=cli.now(), sources=sources,
            no_ota=True, no_reset=True, no_halt=True, no_flash=True))
        print(owner.owned.launch(s.checked(AREA / "runtime/readback-001"), Path(__file__), ["worker"], 900))
    else:
        cli.require(owner.owned.in_job() and s.read(OUT / "intent.json")["sources"] == sources,
                    "finite source-pinned owner required")
        worker(s)
