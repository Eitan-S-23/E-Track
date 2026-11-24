"""Recover only the exact closed pre-cell filename failure; no device I/O."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_session as cli
import p34_cost_assets as assets

FAILED = "20260930T155736-6400"
PREVIOUS = "20260930T133457-87100"


def recover():
    s = cli.Store(ROOT)
    receipt = s.checked(ROOT / ".cache/p34-cost/network-fix/recovery.json")
    profile_path = s.checked(s.base / "profile-cost-bootstrap-v2.json")
    with s.command_lock():
        cli.require(s.current() == FAILED and not receipt.exists() and not profile_path.exists(), "recovery already used or wrong owner")
        tests = cli.verify_tests(s)
        out = s.run(FAILED)
        plan = s.read(out / "plan.json")
        failure = s.read(out / "network-result.json")
        cli.require(failure["result"] == "NETWORK_INCOMPLETE" and failure["device_operations"] == 0 and
                    failure["error"] == "RuntimeError" and
                    failure["detail"] == "full asset filename does not match the App contract/download path", "different failure")
        cli.require(plan["group"] == "cost-bootstrap" and (plan["receiver_version"], plan["target_version"]) == (30238, 30239), "different cell")
        cli.require(not (out / "cells").exists() and not (out / "live-network.json").exists(), "device/service admitted")
        for cell in cli.CELLS:
            cli.require(not (out / "runtime" / cell).exists(), "cell attempted")
        owner = cli.owner_state(s, out / "runtime/network")
        cli.require(owner["state"] == "CLOSED" and owner["receipt"]["worker_exit"] == 1 and
                    not owner["receipt"]["forced_termination"], "network closure unresolved")
        phone = s.read(out / "prestart-phone/result.json")
        usb = s.read(out / "prestart-phone/usb/closed.json")
        cli.require(phone["stable_completed"] and phone["usb_closed"] and phone["pid"] is None and
                    phone["health"]["outcome"] == "completed" and phone["health"]["healthy"] and
                    phone["health"]["upgradeStarts"] == phone["health"]["upgradeEnds"] == 1 and
                    phone["capture_directories"] == 7 and usb["port_closed"] and
                    usb["stop_exit"] == usb["server_exit"] == usb["launcher_exit"] == 0 and
                    usb["key_before"] == usb["key_after"], "phone preflight not completed/closed")
        descriptor = plan["predecessor"]
        cli.require(descriptor["run"] == PREVIOUS and descriptor["cell"] == "s04", "wrong predecessor")
        previous = cli.completed_full_predecessor(s, descriptor, group=cli.BOOT_COPY_GROUP)
        cli.require(previous["plan"]["target_bindings"] == plan["bindings"], "receiver changed")
        for item in [plan["profile"], phone["config"], *phone["snapshot_records"].values()]:
            cli.require(cli.record(item["path"]) == item, "original preflight changed")
        profile = s.read(plan["profile"]["path"])
        cli.require(profile["predecessor"] == descriptor and cli.record(profile["patch_assets"]["path"]) == profile["patch_assets"], "profile changed")
        old = s.read(profile["patch_assets"]["path"])
        revised = assets.load()
        for name in ("bootstrap", "measure"):
            a, b = old["groups"][name], revised["groups"][name]
            cli.require({k:v for k,v in a.items() if k != "specification"} ==
                        {k:v for k,v in b.items() if k != "specification"}, "package/bindings changed")
        new_profile = dict(profile, name=profile["name"] + "-filename-v2", patch_assets=cli.record(ROOT / assets.RELATIVE))
        s.write(profile_path, new_profile)
        s.write(receipt, dict(result="PRE_CELL_NETWORK_FAILURE_RECOVERED", time=cli.now(), device_operations=0,
            failed_run=FAILED, predecessor=descriptor, tests=tests, source=cli.record(__file__),
            original_current=s.read(s.base / "current.json"), new_profile=cli.record(profile_path),
            preserved=[cli.record(out / p) for p in ("plan.json", "network-result.json", "runtime/network/closed.json",
                       "prestart-phone/result.json", "prestart-phone/usb/closed.json", "actions.jsonl")],
            packages_unchanged=True, no_cell_attempted=True, no_config_retirement=True))
        s.write(s.base / "current.json", dict(run=PREVIOUS, created=cli.now(), recovery=cli.record(receipt)), replace=True)
        print("PRE_CELL_NETWORK_FAILURE_RECOVERED", str(profile_path))


if __name__ == "__main__":
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                "explicit root and isolated Python required")
    recover()
