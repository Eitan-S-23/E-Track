"""Resume an APK update that never started because the phone was asleep."""
import json
from pathlib import Path
import re
import runpy
import sys
import time
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_batch12_trial as trial

cli, AREA = trial.cli, trial.AREA
BEFORE, OUT = AREA / "install-001", AREA / "install-003"
TARGET_SHA = "a48549082f74a234d5acf0affdfa0d4120f2099fffefa8a40dc0302cac444387"
TEST = ROOT / "tests/ota/test_p34_batch12_install_resume.py"
HOST = AREA / "resume-tests-002"


def awake_power(command, waiting, *, seconds=180, clock=time.monotonic, sleep=time.sleep):
    """Read-only, pre-armed wake gate; leave time for install and USB closure."""
    cli.require(type(seconds) is int and 1 <= seconds <= 180, "bounded wake wait required")
    deadline, announced = clock() + seconds, False
    while clock() < deadline:
        value = command(["shell", "dumpsys", "power"], timeout=10)
        state = re.search(r"^\s*mWakefulness=(Awake|Asleep|Dozing|Dreaming)\s*$", value, re.M)
        cli.require(state is not None, "unknown phone power state")
        if state[1] == "Awake":
            return value
        if not announced:
            waiting()
            announced = True
        sleep(min(3, max(0, deadline - clock())))
    raise RuntimeError("phone wake window expired; no install attempted")


def verify_no_attempt(before, owner, usb, commands, *, install_intent, stop_intent):
    cli.require(before.get("result") == "NEEDS_PHONE_WAKE_NO_INSTALL_ATTEMPTED" and
                all(before.get(k) is True for k in ("no_ota", "no_uninstall", "no_data_clear", "usb_closed")),
                "different prior install outcome")
    cli.require(owner["worker_exit"] == 0 and owner["forced_termination"] is False and usb["port_closed"] and
                usb["stop_exit"] == usb["server_exit"] == usb["launcher_exit"] == 0 and
                usb["key_before"] == usb["key_after"], "prior resources unresolved")
    cli.require(not install_intent and not stop_intent and commands and
                not any(x["args"] and (x["args"][0] in ("install", "uninstall") or
                    x["args"][:3] == ["shell", "am", "force-stop"] or
                    x["args"][:3] == ["shell", "pm", "clear"]) for x in commands),
                "prior install or mutation may have started")


def reconciled(s):
    records = []
    for before in (BEFORE, AREA / "install-002"):
        paths = [before / "result.json", AREA / "runtime" / before.name / "closed.json",
                 before / "usb/closed.json", before / "usb/commands.jsonl"]
        rows = [json.loads(x) for x in paths[-1].read_text(encoding="utf-8").splitlines()]
        verify_no_attempt(*(s.read(p) for p in paths[:3]), rows,
                          install_intent=(before / "install-intent.json").exists(),
                          stop_intent=(before / "stop-intent.json").exists())
        records += [cli.record(p) for p in paths]
    return records


def inputs(s):
    reconciled(s)
    report, completed = trial.inputs(s)
    cli.require(report["apk"]["sha256"] == TARGET_SHA, "resume must use the already-verified APK")
    return report, completed


def apk(s):
    report, _ = inputs(s)
    result = s.read(OUT / "result.json")
    owner = s.read(AREA / "runtime" / OUT.name / "closed.json")
    cli.require(owner["worker_exit"] == 0 and not owner["forced_termination"] and
                result["result"] == "FIXED_SIGNER_BATCH_UPDATE_VERIFIED" and result["usb_closed"] and
                result["installed"]["sha256"] == TARGET_SHA and result["snapshot_preserved"] and
                result["configuration_preserved"] and result["permissions_preserved"], "resumed install unresolved")
    return report


def tests(s):
    value = s.read(HOST / "result.json")
    cli.require(value["result"] == "PASS" and value["source"] == cli.record(__file__) and
                value["test"] == cli.record(TEST), "resume tests stale")


if __name__ == "__main__":
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                "isolated explicit root required")
    cli.require(sys.argv[1:] in (["launch"], ["worker"]), "exact resume mode required")
    s = cli.Store(ROOT)
    inputs(s)
    tests(s)
    trial.tests(s)
    owner = cli.load_module("batch12_resume_owner", ROOT / ".cache/p3-4-screening-20260922/supervisor.py")
    if sys.argv[1] == "launch":
        cli.require(not OUT.exists(), "preserve resumed installation")
        for name in ("intent.json", "result.json", "power.txt", "stop-intent.json", "install-intent.json",
                     "runtime-config.json", "capture", "host", "usb", "ready-for-wake.json", "awake-confirmed.json"):
            s.checked(OUT / name)
        s.write(OUT / "intent.json", dict(source=cli.record(__file__), prior=reconciled(s),
            implementation=cli.record(trial.installer.__file__), no_ota=True, no_uninstall=True, no_data_clear=True,
            reason="User confirmed phone ready; verify actual old APK and awake state before any mutation"))
        print(owner.owned.launch(s.checked(AREA / "runtime" / OUT.name), Path(__file__), ["worker"], 600))
    else:
        cli.require(owner.owned.in_job(), "finite install owner required")
        def runtime():
            values = runpy.run_path(str(ROOT / "Tools/ota/p34_signing_migration.py"))["runtime"]()
            b, d, p, lock = values
            original = p.command
            def command(args, **kwargs):
                if args == ["shell", "dumpsys", "power"]:
                    def waiting():
                        s.write(OUT / "ready-for-wake.json", dict(time=cli.now(),
                            result="WAITING_FOR_PHONE_AWAKE", maximum_seconds=180, phone_read_only=True))
                        print("WAITING_FOR_PHONE_AWAKE", flush=True)
                    value = awake_power(original, waiting)
                    s.write(OUT / "awake-confirmed.json", dict(time=cli.now(), result="PHONE_AWAKE_OBSERVED"))
                    return value
                return original(args, **kwargs)
            p.command = command
            return b, d, p, lock
        def load(path):
            cli.require(Path(path) == ROOT / "Tools/ota/p34_signing_migration.py", "unexpected installer dependency")
            return dict(runtime=runtime)
        trial.batch.clone(trial.installer.worker, inputs=inputs, OUT=OUT,
            runpy=SimpleNamespace(run_path=load), prior=SimpleNamespace(PKG=trial.PKG, OLD_SHA=trial.OLD_SHA))(s)
