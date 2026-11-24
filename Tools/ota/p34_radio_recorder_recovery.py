"""Archive the invalid scan capture/config; retain its failure and confirmed target."""
import argparse
import hashlib
import json
from pathlib import Path
import runpy
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_radio_trial as radio
import p34_radio_recorder_install as install

cli = radio.cli
AREA = radio.AREA / "recorder-fix"
OUT = AREA / "recovery-001"
CAPTURE = install.REMOTE.split("/")[-1]
PROTECTED = "1790922902993068-85c604a42872fe472af630d8"


def invalid_health(raw):
    h = json.loads(raw)
    cli.require(h["captureId"] == CAPTURE and h["healthy"] is False and h["error"] == "invalid-record" and
                h["upgradeStarts"] == 1 and h["upgradeEnds"] == 0 and h["outcome"] is None and
                type(h["lost"]) is int and h["lost"] > 0, "not the original failed scan recording")


def worker(s):
    installed = s.read(install.OUT / "result.json")
    cli.require(installed["result"] == "FIXED_SIGNER_RECORDER_UPDATE_VERIFIED" and installed["usb_closed"] and
                installed["original_invalid_capture_preserved"] and not installed["app_launched"], "repair install unresolved")
    owner = s.read(radio.AREA / "runtime/recorder-install-001/closed.json")
    cli.require(owner["worker_exit"] == 0 and not owner["forced_termination"], "installation owner unresolved")
    raw_proof = s.read(radio.AREA / "readback-scan-001/result.json")
    cli.require(raw_proof["result"] == "TARGET_30247_RAW_CONFIRMED_CAPTURE_INVALID" and
                cli.record(raw_proof["checkpoint"]["path"]) == raw_proof["checkpoint"], "raw target proof changed")
    backup = install.OUT / "capture"
    data = {p.name:p.read_bytes() for p in backup.iterdir()}
    cli.require(set(data) in ({"events.jsonl", "health.json"}, {"events.jsonl", "health.json", "health.json.tmp"}),
                "unknown backup files")
    invalid_health(data["health.json"])
    config = (install.OUT / "runtime-config.json").read_bytes()
    config_sha = hashlib.sha256(config).hexdigest()
    protected = radio.TRIALS / "baseline/cells/s04/finished/snapshot.jsonl"
    expected_protected = protected.read_bytes()
    cli.require(cli.record(protected)["sha256"] == "b36de84896286524ca671707662676ef46a10aab979228f6746d37234260b5a1",
                "protected baseline changed")
    b, d, p, lock = runpy.run_path(str(ROOT / "Tools/ota/p34_signing_migration.py"))["runtime"]()
    checked = lambda path, new=False: radio.backend.checked_phone_path(install.previous, p, path, new_leaf=new)
    def exists(path):
        return p.command(["exec-out", "run-as", install.previous.PKG, "ls", "-d", path], check=False).strip() == path
    def listing(path):
        return p.command(["exec-out", "run-as", install.previous.PKG, "ls", "-1", path]).splitlines()
    def read(path):
        result = p.command(["exec-out", "run-as", install.previous.PKG, "head", "-c", "16777217", path], timeout=30, binary=True)
        cli.require(len(result) <= 16777216, "file too large")
        return result
    value = dict(result="RECOVERY_INCOMPLETE", no_delete=True, no_ota=True, original_capture_invalid=True)
    destination = "files/p34-archived-observations/" + CAPTURE
    retired = "files/p34-retired-configs/" + config_sha + ".json"
    try:
        with lock.device_lock(), d["usb"](b, p, OUT):
            p.phone_identity()
            cli.require(d["installed"](b, p, installed["installed"]["sha256"]) is not None, "new APK changed")
            cli.require(not p.command(["shell", "pidof", install.previous.PKG], check=False).strip(), "App must stay stopped")
            names = listing("files/p34-observations")
            cli.require(len(names) == 8 and len(set(names)) == 8 and all(radio.backend.CAPTURE_NAME.fullmatch(n) for n in names) and
                        CAPTURE == sorted(names)[-1] and PROTECTED in names, "unexpected capture inventory")
            checked(install.REMOTE)
            cli.require(set(listing(install.REMOTE)) == set(data), "capture files changed")
            for name, raw in data.items():
                checked(install.REMOTE + "/" + name)
                cli.require(read(install.REMOTE + "/" + name) == raw, "capture changed after installation")
            cli.require(read("files/p34-experiment.json") == config and
                        read("files/p34-observations/" + PROTECTED + "/snapshot-1.jsonl") == expected_protected,
                        "protected data changed")
            for path in ("files/p34-archived-observations", "files/p34-retired-configs"):
                checked(path)
            checked(destination, True)
            checked(retired, True)
            cli.require(not exists(destination) and not exists(retired), "archive exists; reconcile instead of overwrite")
            sources = {name:s.raw(OUT / "capture" / name, raw) for name, raw in data.items()}
            config_copy = s.raw(OUT / "runtime-config.json", config)
            cli.require(all(cli.record(item["path"]) == item for item in [*sources.values(), config_copy]), "host backup differs")
            s.write(OUT / "move-intent.json", dict(capture_source=checked(install.REMOTE), capture_target=checked(destination, True),
                config_source=checked("files/p34-experiment.json"), config_target=checked(retired, True), sources=sources,
                config=config_copy, protected=PROTECTED, raw_target=raw_proof["checkpoint"]))
            p.command(["exec-out", "run-as", install.previous.PKG, "mv", "-n", install.REMOTE, destination])
            cli.require(not exists(install.REMOTE) and set(listing(destination)) == set(data) and
                        all(read(destination + "/" + name) == raw for name,raw in data.items()), "capture move unresolved")
            p.command(["exec-out", "run-as", install.previous.PKG, "mv", "-n", "files/p34-experiment.json", retired])
            cli.require(not exists("files/p34-experiment.json") and read(retired) == config, "config move unresolved")
            remaining = listing("files/p34-observations")
            cli.require(set(remaining) == set(names) - {CAPTURE} and
                        read("files/p34-observations/" + PROTECTED + "/snapshot-1.jsonl") == expected_protected and
                        not p.command(["shell", "pidof", install.previous.PKG], check=False).strip(), "protected state changed")
            value.update(result="INVALID_CAPTURE_ARCHIVED_TARGET_RETAINED", capture=CAPTURE, capture_archive=destination,
                retired_config=retired, remaining=remaining, source_files=sources, config=config_copy,
                raw_target=raw_proof["checkpoint"], performance="UNAVAILABLE", app_stopped=True)
        value["usb_closed"] = True
    except Exception as error:
        value.update(error=type(error).__name__, detail=str(error))
    s.write(OUT / "result.json", dict(time=cli.now(), **value))
    print(json.dumps(value), flush=True)
    cli.require("error" not in value, "recovery uncertain; preserve state and do not repeat")


if __name__ == "__main__":
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                "explicit root and isolated Python required")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("launch", "worker"))
    args = parser.parse_args()
    s = cli.Store(ROOT)
    supervisor = cli.load_module("recorder_recovery_owner", ROOT / ".cache/p3-4-screening-20260922/supervisor.py")
    if args.mode == "launch":
        cli.require(not OUT.exists(), "preserve recovery attempt")
        for name in ("intent.json", "result.json", "move-intent.json", "capture", "runtime-config.json", "usb", "host"):
            s.checked(OUT / name)
        invalid_health((install.OUT / "capture/health.json").read_bytes())
        s.write(OUT / "intent.json", dict(source=cli.record(__file__), no_delete=True, no_ota=True,
            scope="archive exact invalid capture/config; retain raw-confirmed30247 and all original failure evidence"))
        print(supervisor.owned.launch(radio.AREA / "runtime/recorder-recovery-001", Path(__file__), ["worker"], 600), flush=True)
    else:
        cli.require(supervisor.owned.in_job(), "finite recovery owner required")
        worker(s)
