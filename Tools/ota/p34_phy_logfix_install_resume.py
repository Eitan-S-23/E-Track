"""Resume the unspent recorder APK update after user readiness, without replay."""
import json
from pathlib import Path
import sys
from types import FunctionType

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_phy_logfix_install as original
import p34_batch12_install_resume as guards

cli, AREA = original.cli, original.AREA
OUT = AREA / "install-002"
HOST = AREA / "resume-tests-001"
TEST = ROOT / "tests/ota/test_p34_phy_logfix_resume.py"
TARGET_SHA = "aef3d433a54da801b594f5ddce64b5bdf80f0c0f1c2016a42f1188e04ae96934"


def __getattr__(name):
    return getattr(original, name)


def reconciled(s):
    paths = [original.OUT / "result.json", AREA / "runtime/install-001/closed.json",
             original.OUT / "usb/closed.json", original.OUT / "usb/commands.jsonl"]
    rows = [json.loads(line) for line in paths[-1].read_text(encoding="utf-8").splitlines()]
    guards.verify_no_attempt(*(s.read(p) for p in paths[:3]), rows,
        install_intent=(original.OUT / "install-intent.json").exists(),
        stop_intent=(original.OUT / "stop-intent.json").exists())
    return [cli.record(p) for p in paths]


def inputs(s):
    reconciled(s)
    report, proof = original.inputs(s)
    cli.require(report["apk"]["sha256"] == TARGET_SHA, "resume must use the verified repair APK")
    return report, proof


def sources():
    return original.sources() + [cli.record(p) for p in (Path(__file__), TEST, Path(guards.__file__))]


def tests(s):
    value = s.read(HOST / "result.json")
    cli.require(value["passed"] and value["sources"] == sources(), "current resume guard tests required")


def worker(s, *, input_reader=inputs, runtime_loader=None):
    def runtime():
        b, d, p, lock = original.runtime()
        before = p.command
        def command(args, **kwargs):
            if args == ["shell", "dumpsys", "power"]:
                def waiting():
                    s.write(OUT / "ready-for-wake.json", dict(time=cli.now(), seconds=180, phone_read_only=True))
                    print("WAITING_FOR_PHONE_AWAKE", flush=True)
                value = guards.awake_power(before, waiting)
                s.write(OUT / "awake-confirmed.json", dict(time=cli.now(), awake=True))
                return value
            return before(args, **kwargs)
        p.command = command
        return b, d, p, lock
    FunctionType(original.worker.__code__, dict(original.worker.__globals__, OUT=OUT), "worker")(
        s, input_reader=input_reader, runtime_loader=runtime_loader or runtime)


if __name__ == "__main__":
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                "isolated explicit root required")
    cli.require(sys.argv[1:] in (["launch"], ["worker"]), "exact mode required")
    s = cli.Store(ROOT)
    tests(s)
    report, proof = inputs(s)
    owner = cli.load_module("phy_logfix_resume_owner", ROOT / ".cache/p3-4-screening-20260922/supervisor.py")
    if sys.argv[1] == "launch":
        cli.require(not OUT.exists(), "preserve resumed install attempt")
        for name in ("intent.json", "result.json", "power.txt", "stop-intent.json", "install-intent.json",
                     "runtime-config.json", "capture", "host", "usb", "ready-for-wake.json", "awake-confirmed.json"):
            s.checked(OUT / name)
        s.write(OUT / "intent.json", dict(time=cli.now(), sources=sources(), prior=reconciled(s), apk=report["apk"],
            retained=proof["checkpoint"], no_ota=True, no_uninstall=True, no_data_clear=True,
            reason="User confirmed ready; verify actual awake state before replacement"))
        print(owner.owned.launch(s.checked(AREA / "runtime/install-002"), Path(__file__), ["worker"], 600))
    else:
        cli.require(owner.owned.in_job() and s.read(OUT / "intent.json")["sources"] == sources(), "finite source-pinned owner required")
        worker(s)
