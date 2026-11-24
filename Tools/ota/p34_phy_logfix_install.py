"""Same-signer recorder repair after raw-confirmed OTA; preserve unhealthy bytes."""
import json
from pathlib import Path
import runpy
import sys
from types import FunctionType

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_phy_install as original
import p34_phy_failure as failed
import p34_phy_readback as readback

cli = original.cli
AREA = ROOT / ".cache/p34-phy-logfix"
OUT, HOST = AREA / "install-001", AREA / "install-tests-001"
TEST = ROOT / "tests/ota/test_p34_phy_logfix_install.py"
SHA = "b85f50aae66f51895aa4f9bbb9a82732138bae3b"
OLD_SHA = "7cafe0c20956cd6791f9c9a495feeac19843cd390d09b0fdcdee4ecb4edc748a"
PKG, CAPTURE = original.PKG, failed.CAPTURE
REMOTE = "files/p34-observations/" + CAPTURE
IMAGE = "b6452ac18c37dd7ce5cc8c27cfeab336583ed8446847a4379f7d83d11ae55e66"
BOOT = "a63346db0dc673dc42adf6064892c466af5c4571df53cb55fe5b6ea154c1fdf4"


def validate_health(raw):
    h = json.loads(raw)
    cli.require(h["captureId"] == CAPTURE and h["healthy"] is False and
        h["error"] == "invalid-record" and type(h["lost"]) is int and h["lost"] > 0 and
        h["upgradeStarts"] == 1 and h["upgradeEnds"] == 0 and h["outcome"] is None,
        "original invalid recording changed")


def validate_retained(proof, closure):
    cli.require(proof["result"] == "PHY_TARGET_30267_RAW_AND_BOOT_CONFIRMED" and
        proof["retained_version"] == 30267 and not proof["measurement_eligible"], "wrong retained proof")
    cli.require(closure["reader_closed"] and closure["retained_verified"] and
        "cleanup_error" not in closure and all(closure[k] for k in
        ("no_reset", "no_halt", "no_flash", "no_nvic_write")), "native closure unresolved")
    for phase in ("initial_identity", "final_identity"):
        for key, sha, size in (("app", IMAGE, 617324), ("boot", BOOT, 65536)):
            item = closure[phase][key]
            cli.require(item["sha256"] == sha and item["bytes"] == size, "actual full image differs")
    state = closure["final_state"]
    cli.require(state["bcb_state"] == 4 and all(state[k] == 1 for k in
        ("confirm_done", "state_snapped", "sd_ready")) and all(state["session"][k] == 0 for k in
        ("state", "session_id", "isr_active", "receiver", "complete")), "MCU not confirmed idle")


def inputs(s):
    failed.inputs(s)
    for name in ("readback-001", "reconcile-001"):
        owner = s.read(failed.AREA / "runtime" / name / "closed.json")
        cli.require(owner["worker_exit"] == 0 and not owner["forced_termination"], "prior owner unresolved")
    proof = s.read(readback.OUT / "result.json")
    closure = s.read(proof["checkpoint"]["path"])
    validate_retained(proof, closure)
    for item in [proof["checkpoint"], *[v for phase in ("initial_identity", "final_identity")
                    for v in closure[phase].values()]]:
        cli.require(cli.record(s.checked(item["path"])) == item, "retained raw proof changed")
    report = s.read(AREA / "apk-g1/apk.json")
    for item in [report["apk"], *report["host_reports"], *report["native_reports"]]:
        cli.require(cli.record(s.checked(item["path"])) == item, "candidate or CI bytes changed")
    check = FunctionType(original.validate_apk.__code__, dict(original.validate_apk.__globals__, SHA=SHA))
    check(report, [s.read(i["path"]) for i in report["host_reports"]],
          [s.read(i["path"]) for i in report["native_reports"]])
    signer = runpy.run_path(str(ROOT / "Tools/ota/p34_signing_artifacts.py"))["apk_certificate"]
    cli.require(signer(Path(report["apk"]["path"]).read_bytes()) == original.CERT, "actual signer differs")
    recovered = s.read(failed.OUT / "result.json")
    for item in recovered["files"]:
        cli.require(cli.record(s.checked(item["path"])) == item, "original failure bytes changed")
    return report, proof


def runtime():
    return runpy.run_path(str(ROOT / "Tools/ota/p34_signing_migration.py"))["runtime"]()


def worker(s, *, input_reader=inputs, runtime_loader=runtime):
    report, proof = input_reader(s)
    b, d, p, lock = runtime_loader()
    value = dict(result="PHY_LOGFIX_INSTALL_INCOMPLETE", no_ota=True, no_uninstall=True,
                 no_data_clear=True, original_capture_invalid=True, app_launched=False)
    try:
        with lock.device_lock(), d["usb"](b, p, OUT):
            p.phone_identity()
            cli.require(d["installed"](b, p, OLD_SHA) is not None, "installed APK differs; no blind reinstall")
            power = p.command(["shell", "dumpsys", "power"], timeout=30)
            s.raw(OUT / "power.txt", power.encode())
            if "mWakefulness=Awake" not in power:
                value["result"] = "NEEDS_PHONE_WAKE_NO_INSTALL_ATTEMPTED"
            else:
                pid = p.command(["shell", "pidof", PKG], check=False).strip()
                cli.require(pid in ("", str(failed.PID)), "App invocation changed; reconcile before stopping")
                validate_health(p.file_bytes(PKG, REMOTE + "/health.json", 8192))
                config = p.file_bytes(PKG, "files/p34-experiment.json", 8192)
                cli.require(config == (failed.OUT / "runtime-config.json").read_bytes(), "configuration changed")
                s.write(OUT / "stop-intent.json", dict(time=cli.now(), pid=pid,
                    retained=proof["checkpoint"], reason="confirmed idle target; required recorder repair"))
                p.command(["shell", "am", "force-stop", PKG])
                cli.require(not p.command(["shell", "pidof", PKG], check=False).strip(), "App did not stop")
                names = p.command(["exec-out", "run-as", PKG, "ls", "-1", REMOTE]).splitlines()
                cli.require(set(names) in ({"events.jsonl", "health.json"},
                    {"events.jsonl", "health.json", "health.json.tmp"}), "unknown capture files")
                saved = {n: p.file_bytes(PKG, REMOTE + "/" + n, 16785408) for n in names}
                cli.require(saved["events.jsonl"] == (failed.OUT / "capture/events.jsonl").read_bytes(),
                            "original events changed")
                validate_health(saved["health.json"])
                for name, raw in saved.items():
                    s.raw(OUT / "capture" / name, raw)
                s.raw(OUT / "runtime-config.json", config)
                permissions = d["permission_state"](p.command(["shell", "dumpsys", "package", PKG]), 0)
                s.write(OUT / "install-intent.json", dict(time=cli.now(), apk=report["apk"], replace=True))
                reply = p.command(["install", "-r", "--no-streaming", report["apk"]["path"]], timeout=180)
                cli.require(reply.strip().splitlines()[-1:] == ["Success"], "installation uncertain; reconcile first")
                value["installed"] = d["installed"](b, p, report["apk"]["sha256"])
                cli.require(value["installed"] is not None, "installed package hash differs")
                cli.require(all(p.file_bytes(PKG, REMOTE + "/" + n, len(raw) + 1) == raw for n, raw in saved.items()),
                            "original failure changed during installation")
                cli.require(p.file_bytes(PKG, "files/p34-experiment.json", 8192) == config and
                    d["permission_state"](p.command(["shell", "dumpsys", "package", PKG]), 0) == permissions,
                    "configuration or permissions changed")
                value.update(result="PHY_LOGFIX_SAME_SIGNER_INSTALLED", original_invalid_capture_preserved=True,
                    configuration_preserved=True, permissions_preserved=True, retained=proof["checkpoint"])
        value["usb_closed"] = True
    except Exception as error:
        value.update(error=type(error).__name__, detail=str(error))
    s.write(OUT / "result.json", dict(time=cli.now(), **value))
    print(json.dumps(value), flush=True)
    cli.require("error" not in value, "preserve installation outcome; do not retry blindly")


def sources():
    return [cli.record(p) for p in (Path(__file__), TEST, Path(original.__file__),
        Path(failed.__file__), Path(readback.__file__), ROOT / "Tools/ota/p34_signing_migration.py")]


if __name__ == "__main__":
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                "isolated explicit root required")
    cli.require(sys.argv[1:] in (["launch"], ["worker"]), "exact mode required")
    s = cli.Store(ROOT)
    tests = s.read(HOST / "result.json")
    cli.require(tests["passed"] and tests["sources"] == sources(), "current installation guard tests required")
    report, proof = inputs(s)
    owner = cli.load_module("phy_logfix_install_owner", ROOT / ".cache/p3-4-screening-20260922/supervisor.py")
    if sys.argv[1] == "launch":
        cli.require(not OUT.exists(), "preserve install attempt")
        for name in ("intent.json", "result.json", "power.txt", "stop-intent.json", "install-intent.json",
                     "runtime-config.json", "capture", "host", "usb"):
            s.checked(OUT / name)
        s.write(OUT / "intent.json", dict(time=cli.now(), sources=sources(), apk=report["apk"],
            retained=proof["checkpoint"], no_ota=True, no_uninstall=True, no_data_clear=True))
        print(owner.owned.launch(s.checked(AREA / "runtime/install-001"), Path(__file__), ["worker"], 600))
    else:
        cli.require(owner.owned.in_job() and s.read(OUT / "intent.json")["sources"] == sources(), "finite source-pinned owner required")
        worker(s)
