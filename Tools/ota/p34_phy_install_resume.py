"""Resume the verified, unspent PHY APK replacement without replaying old records."""
import json
from pathlib import Path
import runpy
import sys
from types import SimpleNamespace, FunctionType

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_phy_install as original
import p34_batch12_install_resume as guards

cli, AREA = original.cli, original.AREA
OUT = AREA / "install-002"
TEST = ROOT / "tests/ota/test_p34_phy_install_resume.py"
HOST = AREA / "resume-tests-001"
TARGET_SHA = "7cafe0c20956cd6791f9c9a495feeac19843cd390d09b0fdcdee4ecb4edc748a"


def reconciled(s):
    before = original.OUT
    paths = [before / "result.json", AREA / "runtime/install-001/closed.json",
             before / "usb/closed.json", before / "usb/commands.jsonl"]
    rows = [json.loads(line) for line in paths[-1].read_text().splitlines()]
    guards.verify_no_attempt(*(s.read(p) for p in paths[:3]), rows,
        install_intent=(before / "install-intent.json").exists(), stop_intent=(before / "stop-intent.json").exists())
    return [cli.record(p) for p in paths]


def inputs(s):
    reconciled(s)
    value = original.inputs(s)
    cli.require(value[0]["apk"]["sha256"] == TARGET_SHA, "already-verified APK required")
    return value


def apk(s, checking=False):
    report = inputs(s)[0]
    if checking: return report
    result = s.read(OUT / "result.json")
    owner = s.read(AREA / "runtime/install-002/closed.json")
    cli.require(result["result"] == "FIXED_SIGNER_BATCH_UPDATE_VERIFIED" and result["usb_closed"] and
        result["installed"]["sha256"] == TARGET_SHA and result["snapshot_preserved"] and
        result["configuration_preserved"] and result["permissions_preserved"] and
        owner["worker_exit"] == 0 and not owner["forced_termination"], "resumed installation unresolved")
    return report


def sources():
    return original.sources() + [cli.record(p) for p in (Path(__file__), TEST, Path(guards.__file__))]


def tests(s):
    result = s.read(HOST / "result.json")
    cli.require(result["result"] == "PASS" and result["sources"] == sources(), "current resume self-tests required")


def worker(s):
    def runtime():
        values = runpy.run_path(str(ROOT / "Tools/ota/p34_signing_migration.py"))["runtime"]()
        b, d, p, lock = values
        before = p.command
        def command(args, **kwargs):
            if args == ["shell", "dumpsys", "power"]:
                def waiting():
                    s.write(OUT / "ready-for-wake.json", dict(time=cli.now(), phone_read_only=True, seconds=180))
                    print("WAITING_FOR_PHONE_AWAKE", flush=True)
                value = guards.awake_power(before, waiting)
                s.write(OUT / "awake-confirmed.json", dict(time=cli.now(), awake=True))
                return value
            return before(args, **kwargs)
        p.command = command
        return b, d, p, lock
    def load(path):
        cli.require(Path(path) == ROOT / "Tools/ota/p34_signing_migration.py", "unexpected runtime dependency")
        return dict(runtime=runtime)
    FunctionType(original.worker.__code__, dict(original.worker.__globals__, OUT=OUT), "worker")(
        s, input_reader=inputs, runtime_loader=SimpleNamespace(run_path=load))


if __name__ == "__main__":
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                "explicit isolated root required")
    cli.require(sys.argv[1:] in (["launch"], ["worker"]), "exact resume mode required")
    s = cli.Store(ROOT)
    tests(s)
    report, completed = inputs(s)
    owner = cli.load_module("phy_resume_owner", ROOT / ".cache/p3-4-screening-20260922/supervisor.py")
    if sys.argv[1] == "launch":
        cli.require(not OUT.exists(), "preserve resume attempt")
        for name in ("intent.json", "result.json", "power.txt", "stop-intent.json", "install-intent.json",
                     "runtime-config.json", "capture", "host", "usb", "ready-for-wake.json", "awake-confirmed.json"):
            s.checked(OUT / name)
        s.write(OUT / "intent.json", dict(time=cli.now(), sources=sources(), prior=reconciled(s),
            apk=report["apk"], no_ota=True, no_uninstall=True, no_data_clear=True,
            reason="User confirmed ready; read actual awake state before any replacement"))
        print(owner.owned.launch(s.checked(AREA / "runtime/install-002"), Path(__file__), ["worker"], 600))
    else:
        cli.require(owner.owned.in_job() and s.read(OUT / "intent.json")["sources"] == sources(), "source-pinned owner required")
        worker(s)
