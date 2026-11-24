"""Read the restarted repaired App before any stop/archive; no device mutation."""
from pathlib import Path
import runpy
import sys
from types import FunctionType, SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_phy_logfix_trial_resume as trial

cli, AREA = trial.cli, trial.AREA
OUT = AREA / "startup-inspect-001"
ORIGINAL = ROOT / "Tools/ota/p34_radio_startup_inspect.py"


def inputs(s):
    trial.installed(s)
    value = s.read(trial.RECOVERY / "result.json")
    closed = s.read(AREA / "runtime/recovery-001/closed.json")
    cli.require(value["result"] == "PHY_ARCHIVE_INCOMPLETE" and value["detail"] == "App must remain stopped" and
        closed["worker_exit"] == 1 and not closed["forced_termination"] and
        not (trial.RECOVERY / "move-intent.json").exists(), "different/uncertain archive outcome")
    return [cli.record(p) for p in (Path(__file__), ORIGINAL, trial.RECOVERY / "result.json",
        AREA / "runtime/recovery-001/closed.json")]


if __name__ == "__main__":
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                "isolated explicit root required")
    cli.require(sys.argv[1:] in (["launch"], ["worker"]), "exact mode required")
    s = cli.Store(ROOT)
    sources = inputs(s)
    owner = cli.load_module("phy_restarted_app_owner", ROOT / ".cache/p3-4-screening-20260922/supervisor.py")
    if sys.argv[1] == "launch":
        cli.require(not OUT.exists(), "preserve original inspection")
        for name in ("intent.json", "result.json", "logcat.log", "runtime-config.json", "usb", "host"):
            s.checked(OUT / name)
        s.write(OUT / "intent.json", dict(time=cli.now(), sources=sources, no_phone_mutation=True))
        print(owner.owned.launch(s.checked(AREA / "runtime/startup-inspect-001"), Path(__file__), ["worker"], 600))
    else:
        cli.require(owner.owned.in_job() and s.read(OUT / "intent.json")["sources"] == sources, "source-pinned read-only owner required")
        worker = runpy.run_path(str(ORIGINAL))["worker"]
        facade = SimpleNamespace(AREA=AREA, radio=SimpleNamespace(backend=trial.original.backend),
            recovery=SimpleNamespace(install=SimpleNamespace(previous=SimpleNamespace(PKG=trial.install.PKG))))
        FunctionType(worker.__code__, dict(worker.__globals__, OUT=OUT, f=facade), "worker")(s)
