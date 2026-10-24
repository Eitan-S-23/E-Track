"""Prepare the existing schema-1 endpoint override, retaining baseline BLE policy."""
import argparse
from pathlib import Path
import re
import sys
import time
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent))
from prepare import ROOT, Phone, close_phone, h


def baseline_config(plan, origin, run_id):
    uri = urlsplit(origin)
    h.require(uri.scheme == "https" and uri.hostname and uri.port in (None, 443) and
              not any((uri.username, uri.password, uri.query, uri.fragment, uri.path)), "HTTPS origin required")
    h.require(re.fullmatch(r"[a-z][a-z0-9-]{0,47}", run_id), "run ID")
    return dict(schema=1, runId=run_id, target=plan["ble_address"], requestedBaud=921600,
                reuseGatt=False, withoutResponse=False,
                firmwareLatestUrl=origin + "/api/public/firmware/latest",
                packageBytes=plan["package"]["bytes"], packageSha256=plan["package"]["sha256"],
                currentVersionCode=30287, currentImageSha256=plan["images"]["base"]["image"]["sha256"],
                targetVersionCode=30288, targetImageSha256=plan["images"]["target"]["image"]["sha256"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phone", type=Path, required=True)
    parser.add_argument("--network", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--previous-config", type=Path)
    args = parser.parse_args()
    h.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
              "explicit root and isolated Python required")
    out = h.checked(args.out)
    for name in ("host", "usb", "config.json", "result.json"):
        h.checked(out / name)
    plan = h.read_json(args.phone)
    h.require(plan["app_id"] == "com.wen.gaia.gaia.p38acceptance", "wrong preparation package")
    ready = h.read_json(args.network / "ready.json")
    h.require(not (args.network / "result.json").exists() and
              ready["deadline_monotonic"] - time.monotonic() > 1800, "insufficient fixture lifetime")
    network_plan = h.read_json(h.pinned(ready["plan"]))
    cfg = baseline_config(network_plan, ready["origin"], args.run_id)
    if args.previous_config:
        import hashlib
        plan["owned_configs"] = [hashlib.sha256(args.previous_config.read_bytes()).hexdigest()]
    h.fresh(out)
    h.save(out / "config.json", cfg)
    phone = Phone(plan, out / "usb", 360)
    try:
        phone.start()
        for capture in phone.captures():
            health = phone.health(capture)
            h.require(health["upgradeStarts"] == health["upgradeEnds"], "unfinished capture; preserve before restart")
            raw = phone.live_file("files/p34-observations/" + capture + "/events.jsonl")
            h.raw(out / "previous" / (capture + ".jsonl"), raw)
        pid, capture = phone.provision(cfg)
        h.save(out / "result.json", dict(result="RUNTIME_WRITTEN_PROCESS_LAUNCHED_NO_OTA", pid=pid,
            capture=capture, runtime=h.record(phone.out / "runtime.json"), config=h.record(out / "config.json"),
            origin=ready["origin"], no_ota_start=True, no_at_or_mcu_write=True))
    finally:
        close_phone(phone)


if __name__ == "__main__":
    main()
