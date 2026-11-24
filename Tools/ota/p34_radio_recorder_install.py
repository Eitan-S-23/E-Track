"""Same-signer recorder repair; retain the invalid capture and confirmed30247."""
import argparse
import json
from pathlib import Path
import runpy
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_radio_install as previous
import p34_radio_recorder_artifacts as artifact

cli = previous.cli
AREA = previous.AREA
OUT = AREA / "recorder-fix/install-001"
REMOTE = "files/p34-observations/1790925192124168-1a3c191610d5b0cc5010d74d"
OLD_SHA = "20ae2d51c9623c8abfc264afadf5ad397edea46c1fa15c3199475b06c5f7f80e"


def worker(s):
    report = s.read(AREA / "recorder-fix/apk-g1/apk.json")
    signing = runpy.run_path(str(ROOT / "Tools/ota/p34_signing_artifacts.py"))
    cli.require(report["sha"] == artifact.SHA and report["metadata"]["application_id"] == previous.PKG and
                report["certificate_sha256"] == signing["CERT"] and cli.record(report["apk"]["path"]) == report["apk"] and
                signing["apk_certificate"](Path(report["apk"]["path"]).read_bytes()) == signing["CERT"],
                "APK provenance/signature mismatch")
    hosts = set()
    for record in report["host_reports"]:
        cli.require(cli.record(record["path"]) == record, "CI evidence changed")
        host = s.read(record["path"])
        cli.require(host["development_result"] == "PASS" and host["scope"] == "all" and
                    host["source_before"]["head"] == artifact.SHA and host["source_before"]["clean"], "exact CI pass required")
        hosts.add(json.dumps(host["host"], sort_keys=True))
    cli.require(len(hosts) == len(report["host_reports"]) == 2, "both hosts required")
    proof = s.read(AREA / "readback-scan-001/result.json")
    cli.require(proof["result"] == "TARGET_30247_RAW_CONFIRMED_CAPTURE_INVALID" and
                cli.record(proof["checkpoint"]["path"]) == proof["checkpoint"], "confirmed target required")
    for name in ("readback-scan-001", "retrieve-scan-001"):
        owner = s.read(AREA / "runtime" / name / "closed.json")
        cli.require(owner["worker_exit"] == 0 and not owner["forced_termination"], "prior owner unresolved")
    closure = s.read(proof["checkpoint"]["path"])
    cli.require(closure["reader_closed"] and closure["retained_verified"] and
                closure["final_state"]["bcb_state"] == 4 and closure["final_state"]["confirm_done"] == 1,
                "Boot confirmation unresolved")
    for phase in ("initial_identity", "final_identity"):
        for record in closure[phase].values():
            cli.require(cli.record(record["path"]) == record, "full readback bytes changed")
    b, d, p, lock = runpy.run_path(str(ROOT / "Tools/ota/p34_signing_migration.py"))["runtime"]()
    value = dict(result="RECORDER_INSTALL_INCOMPLETE", no_ota=True, no_uninstall=True, no_data_clear=True)
    try:
        with lock.device_lock(), d["usb"](b, p, OUT):
            p.phone_identity()
            cli.require(d["installed"](b, p, OLD_SHA) is not None, "unexpected installed App")
            power = p.command(["shell", "dumpsys", "power"], timeout=30)
            s.raw(OUT / "power.txt", power.encode())
            if "mWakefulness=Awake" not in power:
                value["result"] = "NEEDS_PHONE_WAKE_NO_INSTALL_ATTEMPTED"
            else:
                pid = p.command(["shell", "pidof", previous.PKG], check=False).strip()
                cli.require(pid in ("", "2078"), "different App invocation; reconcile before stopping")
                raw = p.file_bytes(previous.PKG, REMOTE + "/health.json", 8192)
                health = json.loads(raw)
                cli.require(health["captureId"] == REMOTE.split("/")[-1] and health["error"] == "invalid-record" and
                            health["healthy"] is False and health["upgradeStarts"] == 1 and health["upgradeEnds"] == 0,
                            "recording outcome changed")
                config = p.file_bytes(previous.PKG, "files/p34-experiment.json", 8192)
                cli.require(config == (AREA / "retrieve-scan-001/runtime-config.json").read_bytes(), "configuration changed")
                s.write(OUT / "stop-intent.json", dict(time=cli.now(), pid=pid, confirmed_target=proof["checkpoint"],
                    reason="user reported completed; full raw target confirmed; unhealthy recorder forbids a new invocation"))
                p.command(["shell", "am", "force-stop", previous.PKG])
                cli.require(not p.command(["shell", "pidof", previous.PKG], check=False).strip(), "App did not stop")
                names = p.command(["exec-out", "run-as", previous.PKG, "ls", "-1", REMOTE]).splitlines()
                cli.require(set(names) in ({"health.json", "events.jsonl"}, {"health.json", "events.jsonl", "health.json.tmp"}),
                            "unknown capture files; do not install")
                saved = {}
                for name in names:
                    raw = p.command(["exec-out", "run-as", previous.PKG, "head", "-c", "16777217", REMOTE + "/" + name],
                                    timeout=30, binary=True)
                    cli.require(len(raw) <= 16777216, "capture bound exceeded")
                    saved[name] = raw
                    s.raw(OUT / "capture" / name, raw)
                cli.require(saved["events.jsonl"] == (AREA / "retrieve-scan-001/events.jsonl").read_bytes(),
                            "original incomplete events changed")
                s.raw(OUT / "runtime-config.json", config)
                permissions = d["permission_state"](p.command(["shell", "dumpsys", "package", previous.PKG]), 0)
                s.write(OUT / "install-intent.json", dict(time=cli.now(), apk=report["apk"], replace=True))
                reply = p.command(["install", "-r", "--no-streaming", report["apk"]["path"]], timeout=180)
                cli.require(reply.strip().splitlines()[-1:] == ["Success"], "installation uncertain; reconcile first")
                value["installed"] = d["installed"](b, p, report["apk"]["sha256"])
                cli.require(value["installed"] is not None, "new APK missing")
                for name, raw in saved.items():
                    after = p.command(["exec-out", "run-as", previous.PKG, "head", "-c", "16777217", REMOTE + "/" + name],
                                      timeout=30, binary=True)
                    cli.require(after == raw, "original capture changed during installation")
                cli.require(p.file_bytes(previous.PKG, "files/p34-experiment.json", 8192) == config and
                            d["permission_state"](p.command(["shell", "dumpsys", "package", previous.PKG]), 0) == permissions,
                            "configuration or permissions changed")
                value.update(result="FIXED_SIGNER_RECORDER_UPDATE_VERIFIED", original_invalid_capture_preserved=True,
                             configuration_preserved=True, permissions=permissions, app_launched=False)
        value["usb_closed"] = True
    except Exception as error:
        value.update(error=type(error).__name__, detail=str(error))
    s.write(OUT / "result.json", dict(time=cli.now(), **value))
    print(json.dumps(value), flush=True)
    cli.require("error" not in value, "preserve outcome; no blind installation retry")


if __name__ == "__main__":
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                "explicit root and isolated Python required")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("launch", "worker"))
    args = parser.parse_args()
    s = cli.Store(ROOT)
    supervisor = cli.load_module("recorder_install_owner", ROOT / ".cache/p3-4-screening-20260922/supervisor.py")
    if args.mode == "launch":
        cli.require(not OUT.exists(), "preserve installation attempt")
        for name in ("intent.json", "result.json", "power.txt", "stop-intent.json", "install-intent.json",
                     "capture", "runtime-config.json", "usb", "host"):
            s.checked(OUT / name)
        s.write(OUT / "intent.json", dict(source=cli.record(__file__), no_uninstall=True, no_data_clear=True, no_ota=True))
        print(supervisor.owned.launch(AREA / "runtime/recorder-install-001", Path(__file__), ["worker"], 600), flush=True)
    else:
        cli.require(supervisor.owned.in_job(), "finite installation owner required")
        worker(s)
