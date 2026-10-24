"""Bounded local single-fixture service using the existing HTTPS/ownership route."""
import argparse
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "Tools/ota/p34-acceptance"))
import live_host as h
from live_phone import Network


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--prior-inputs", type=Path, required=True)
    parser.add_argument("--seconds", type=int, default=7200)
    args = parser.parse_args()
    h.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
              "explicit root and isolated Python required")
    h.require(60 <= args.seconds <= 7200, "bounded fixture service required")
    out = h.fresh(args.out)
    for name in ("owner.json", "plan.json", "ready.json", "result.json", "stop.json", "service"):
        h.checked(out / name)
    reference = h.read_json(ROOT / ".cache/p38/reference-001/result.json")
    current = h.read_json(ROOT / ".cache/p38/native-preflight-002/result.json")
    h.require(reference["result"] == "LEGAL_1MIB_REFERENCE_READY" and
              reference["base"]["sha256"] == current["firmware"]["raw_sha256"], "fixture baseline differs from read device")
    prior = h.read_json(args.prior_inputs)
    plan = dict(images=dict(base=dict(image=reference["base"]), target=dict(image=reference["target"])),
                package=reference["package"], tools=dict(cloudflared=prior["tools"]["cloudflared"]),
                ble_address=prior["ble_address"], fixture_versions=dict(base=30287, target=30288, target_name="3.2.88-p38"))
    for item in (plan["package"], plan["images"]["base"]["image"], plan["images"]["target"]["image"]):
        h.pinned(item)
    deadline = time.monotonic() + args.seconds
    h.save(out / "plan.json", plan)
    h.save(out / "owner.json", dict(pid=os.getpid(), deadline_monotonic=deadline, seconds=args.seconds,
                                   no_device_operations=True, no_cloud_deployment=True))
    network = Network(plan, out / "service")
    value = dict(result="NETWORK_INCOMPLETE", no_device_operations=True)
    try:
        origin = network.start(deadline=min(deadline, time.monotonic() + 180))
        h.save(out / "ready.json", dict(origin=origin, plan=h.record(out / "plan.json"),
                                       deadline_monotonic=deadline))
        print("P38_FIXTURE_READY " + origin, flush=True)
        while time.monotonic() < deadline and not (out / "stop.json").exists():
            h.require(network.tunnel.alive(), "owned HTTPS tunnel exited")
            time.sleep(.5)
        value["result"] = "NETWORK_CLOSED"
    except BaseException as error:
        value.update(result="NETWORK_FAILED", error=type(error).__name__ + ": " + str(error))
        raise
    finally:
        try:
            network.close()
        finally:
            h.save(out / "result.json", value)


if __name__ == "__main__":
    main()
