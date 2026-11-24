"""Preserve the failed App verdict and reconcile target firmware without OTA."""
import argparse
import json
import os
from pathlib import Path
import runpy
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_session as cli

RUN = "20261001T191549-84800"
AREA = ROOT / ".cache/p34-reconnect/timeout-30243"
CAPTURE = "1790882915541398-f0e7c878e47e73001842b7e8"
PKG = "com.wen.gaia.gaia.p34probe"


def originals(store):
    out = store.run(RUN)
    for name in ("s04", "network"):
        cli.require(cli.owner_state(store, out / "runtime" / name)["state"] == "CLOSED",
                    "old observers must be closed")
    plan = store.read(out / "plan.json")
    cli.require(plan["group"] == cli.RECONNECT_GROUP and plan["receiver_version"] == 30242 and
                plan["target_version"] == 30243 and cli.record(plan["profile"]["path"]) == plan["profile"],
                "exact reconnect plan required")
    capture = cli.load_module("timeout_original_capture", ROOT / "Tools/ota/p34_observation.py")
    raw = (out / "cells/s04/finished/snapshot.jsonl").read_bytes()
    summary, messages = capture.verify(raw, sentinel="OTAOBS96bb2c74d5ad6ccecaf30e40", target="02:00:00:00:00:01")
    cli.require(summary["captureId"] == CAPTURE and summary["pid"] == 17127 and
                summary["outcome"] == "not-completed" and summary["input"]["targetVersionCode"] == 30243 and
                summary["input"]["packageSha256"] == plan["served"]["sha256"], "wrong failed invocation")
    return out, plan, summary, messages


def analyze(store):
    out, plan, summary, messages = originals(store)
    rows = [json.loads(line[len("OTA_LINK_STATS "):]) for line in messages.splitlines()
            if line.startswith("OTA_LINK_STATS ")]
    upgrades = [x for x in rows if x["label"] == "upgrade"]
    probes = [x for x in rows if x["label"] == "probe" and x["attempt"] is not None]
    rounds = [x for x in rows if x["label"] == "probe" and x["attempt"] is None]
    cli.require(len(upgrades) == len(rounds) == 1 and probes, "ambiguous transfer/reconnect observations")
    transfer = upgrades[0]["transfer"]
    cli.require(transfer["outcome"] == "ok" and transfer["elapsedUs"] > 0 and
                transfer["durable"]["finalOff"] == plan["served"]["bytes"], "transfer was not durable END OK")
    seconds = transfer["elapsedUs"] / 1000000
    native = store.read(out / "cells/s04/native-trace/result.json")
    cli.require(native["result"] == "TRACE_CLOSED" and native["reader_closed"], "native trace unresolved")
    value = dict(result="TRANSFER_COMPLETE_APP_RECONNECT_FAILED", original_summary=summary,
        snapshot=cli.record(out / "cells/s04/finished/snapshot.jsonl"), plan=cli.record(out / "plan.json"),
        native_trace=cli.record(out / "cells/s04/native-trace/result.json"), source=cli.record(__file__),
        transfer_seconds=seconds, throughput_kib_s=plan["served"]["bytes"] / 1024 / seconds,
        transfer=transfer, probe_attempts=len(probes),
        attempts_with_bind=sum("bind" in x["phases"] for x in probes),
        info_calls=sum(x["getInfo"]["calls"] for x in probes),
        reconnect_seconds=(rounds[0]["phases"]["reconnect"][1] - rounds[0]["phases"]["reconnect"][0]) / 1000000,
        no_ota_replayed=True, full_raw_readback_pending=True, formal_acceptance=False)
    store.write(AREA / "analysis.json", value)
    print(json.dumps({k:v for k,v in value.items() if k not in ("transfer", "original_summary")}), flush=True)


def phone(store):
    original, _, _, _ = originals(store)
    out = store.checked(AREA / "phone-001")
    cli.require(not out.exists(), "preserve phone collection; no blind retry")
    for name in ("intent.json", "result.json", "health.json", "snapshot.jsonl", "logcat.log", "usb", "host"):
        store.checked(out / name)
    module = runpy.run_path(str(ROOT / "Tools/ota/p34_signing_migration.py"))
    b, d, p, lock = module["runtime"]()
    store.write(out / "intent.json", dict(time=cli.now(), source=cli.record(__file__), no_app_mutation=True, no_mcu=True))
    value = dict(result="PHONE_COLLECTION_INCOMPLETE")
    try:
        with lock.device_lock(), d["usb"](b, p, out):
            p.phone_identity()
            value["installed"] = d["installed"](b, p, module["NEW_SHA"])
            remote = "files/p34-observations/" + CAPTURE
            log = p.command(["logcat", "-d", "-v", "threadtime", "-t", "16000", "--pid=17127"],
                            timeout=45, binary=True)
            value["logcat"] = store.raw(out / "logcat.log", log)
            value["health"] = store.raw(out / "health.json", p.file_bytes(PKG, remote + "/health.json", 8192))
            raw = p.file_bytes(PKG, remote + "/snapshot-1.jsonl", 16 * 1024 * 1024)
            value["snapshot"] = store.raw(out / "snapshot.jsonl", raw)
            cli.require(raw == (original / "cells/s04/finished/snapshot.jsonl").read_bytes(),
                        "original immutable snapshot differs")
            value["pid"] = p.command(["shell", "pidof", PKG], check=False).strip()
        value.update(result="ORIGINAL_TIMEOUT_LOGS_RETRIEVED", usb_closed=True)
    except Exception as error:
        value.update(error=type(error).__name__, detail=str(error))
    store.write(out / "result.json", dict(time=cli.now(), **value))
    print(json.dumps(value), flush=True)
    cli.require("error" not in value, "phone collection needs reconciliation")


def readback(store):
    _, plan, _, _ = originals(store)
    out = store.checked(AREA / "readback-001")
    cli.require(not out.exists(), "preserve original readback; reconcile before another")
    for name in ("intent.json", "result.json", "installed-mcu", "host"):
        store.checked(out / name)
    store.write(out / "intent.json", dict(time=cli.now(), source=cli.record(__file__), no_ota=True,
        no_reset=True, no_halt=True, no_flash=True, target_version=30243, profile=plan["profile"]))
    value = dict(result="TARGET_READBACK_INCOMPLETE", app_verdict="not-completed")
    try:
        api = cli.backend(store, Path(plan["profile"]["path"]), cli.RECONNECT_GROUP)
        c = api.installed_context(out)
        api.preflight(c, out)
        c.native_authority()
        os.environ.update(c.environment())
        lock = c.load("timeout_readback_lock", ROOT / "Tools/ota/repeat_cycle.py")
        with lock.device_lock():
            checkpoint = api.install_checkpoint(c, out)
            api.verify_install_checkpoint(c, checkpoint["path"])
        value.update(result="TARGET_30243_RAW_CONFIRMED_APP_RECONNECT_FAILED", checkpoint=checkpoint,
            no_ota=True, no_reset=True, no_halt=True, no_flash=True, original_failure_preserved=True)
    except Exception as error:
        value.update(error=type(error).__name__, detail=str(error))
    store.write(out / "result.json", dict(time=cli.now(), **value))
    print(json.dumps(value), flush=True)
    cli.require("error" not in value, "target readback needs reconciliation")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("analyze", "phone", "readback"))
    args = parser.parse_args()
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                "isolated explicit root required")
    {"analyze": analyze, "phone": phone, "readback": readback}[args.mode](cli.Store(ROOT))
