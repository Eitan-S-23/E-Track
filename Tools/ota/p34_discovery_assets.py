"""Prepare a header-only30244-to30245 successor from the verified real trial."""
import copy
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_session as cli
import p34_reconnect_followup as parent
import p34_install_cost as host

OUT = ROOT / ".cache/p34-discovery-fix/assets"
SPEC = dict(receiver=30244, target_version=30245, version_name="3.2.45-p34r",
    served_name="p34-discovery-full.etu", release_key="p34-discovery", kind="full")


def validate_parent(report, group, closure):
    cli.require(report["result"] == "FULL_INSTALL_VERIFIED" and
                report["summary"]["outcome"] == "completed" and
                report["summary"]["input"]["targetVersionCode"] == 30244 and
                report["summary"]["input"]["targetImageSha256"] == group["target"]["sha256"],
                "completed30244 App verdict required")
    cli.require(closure["retained_verified"] is True and closure["reader_closed"] is True and
                "cleanup_error" not in closure and all(closure[k] is True for k in
                    ("no_reset", "no_halt", "no_flash", "no_nvic_write")), "native closure unresolved")
    for phase in ("initial_identity", "final_identity"):
        for key, expected in (("app", group["target"]), ("boot", group["target_bindings"]["whole_boot"])):
            item = closure[phase][key]
            cli.require(item["bytes"] == expected["bytes"] and item["sha256"] == expected["sha256"],
                        "complete retained raw identity mismatch")
    state = closure["final_state"]
    cli.require(state["bcb_state"] == 4 and all(state[k] == 1 for k in
                ("confirm_done", "state_snapped", "sd_ready")), "normal confirmation required")


def main():
    s = cli.Store(ROOT)
    cli.require(not OUT.exists() and not os.environ.get("OTA_AES_KEY"), "preserve assets/no key override")
    s.checked(OUT)
    group = parent.load_assets(s)
    pointer = s.read(parent.TRIAL / "analysis/latest.json")
    cli.require(cli.record(pointer["report"]["path"]) == pointer["report"], "original report changed")
    report = s.read(pointer["report"]["path"])
    inputs = [pointer["report"], *report["inputs"].values(), report["after"], cli.record(parent.ASSETS)]
    for item in inputs:
        cli.require(cli.record(s.checked(item["path"])) == item, "original evidence changed")
    closure = s.read(report["after"]["path"])
    validate_parent(report, group, closure)
    # Exercise the admission gate on copies, never on frozen evidence files.
    cases = 0
    for key, value in (("bcb_state", 3), ("confirm_done", 0), ("sd_ready", 0)):
        broken = copy.deepcopy(closure)
        broken["final_state"][key] = value
        try:
            validate_parent(report, group, broken)
        except RuntimeError:
            cases += 1
        else:
            raise RuntimeError("unsafe predecessor admitted")
    for phase in ("initial_identity", "final_identity"):
        for key in ("app", "boot"):
            item = closure[phase][key]
            cli.require(cli.record(s.checked(item["path"])) == item, "raw checkpoint bytes changed")
            inputs.append(item)
    plan = s.read(report["inputs"]["plan"]["path"])
    cli.require(plan["target_bindings"] == group["target_bindings"] and plan["target_version"] == 30244,
                "predecessor runtime binding changed")
    for name in ("coordinator", "s04", "network"):
        inputs.append(parent.closed(s, parent.TRIAL / "runtime" / name))
    env = host.environment(s, OUT)
    os.environ.update(env)
    sys.path.insert(0, str(Path(sys.base_prefix) / "Lib/site-packages"))
    previous = parent.previous
    pack = cli.load_module("discovery_pack", previous.erase.candidate.AREA / "f/Tools/etu_pack.py")
    unpack = cli.load_module("discovery_unpack", previous.erase.candidate.AREA / "f/Tools/etu_unpack.py")
    package_tools = cli.load_module("discovery_package_tools", ROOT / "Tools/ota/prepare_baud_assets.py")
    decoder = s.read(ROOT / ".cache/p34-next/n03/assets/result.json")["decoder"]
    previous.historical.resolve(decoder)
    receiver = group["target"]
    raw = bytearray(Path(receiver["path"]).read_bytes())
    raw[0x400:0x460] = pack.build_fw_header(bytes(raw), SPEC["version_name"], 1786320000)
    target = s.raw(OUT / "target.bin", bytes(raw))
    identity = previous.shared.identity(bytes(raw), unpack)
    cli.require(identity["version_code"] == 30245, "wrong target header")
    before = Path(receiver["path"]).read_bytes()
    cli.require(before[:0x400] + before[0x460:] == raw[:0x400] + raw[0x460:], "executable changed")
    blob = previous.shared.wrap_payload(pack, pack.lzma_alone_encode(bytes(raw)), before, bytes(raw), kind="full")
    package = s.raw(OUT / "target.etu", blob)
    def native(label, item, expected):
        return json.loads(host.command(s, OUT, label,
            [decoder["path"], item["path"], receiver["path"], target["path"], expected], env, 180))
    positive = native("positive", package, "ok")
    cli.require(all(positive[k] for k in ("passed", "byte_identical", "boot_ok", "guards_ok", "workspace_lifecycle_ok")),
                "native package proof failed")
    negatives, outputs = [], [target, package]
    for label, broken, expected in package_tools.negatives(blob, 30244):
        item = s.raw(OUT / (label + ".etu"), broken)
        result = native(label, item, expected)
        cli.require(result["passed"] and result["prepares"] == 0, "negative decoder guard failed")
        negatives.append(dict(name=label, native=result, package=item))
        outputs.append(item)
    bindings = copy.deepcopy(group["target_bindings"])
    bindings["profile"].update(image=target, identity=identity, prefix=bytes(raw[:0x460]).hex())
    inputs += [decoder, cli.record(__file__), *[cli.record(m.__file__) for m in (pack, unpack, package_tools, previous.shared)]]
    outputs += [cli.record(p) for p in OUT.glob("*.log")]
    s.write(OUT / "result.json", dict(result="DISCOVERY_SUCCESSOR_ASSETS_VERIFIED", hardware=False,
        admission_negative_checks=cases, inputs=inputs, outputs=outputs,
        group=dict(specification=SPEC, receiver=receiver, receiver_bindings=group["target_bindings"],
            target=target, target_identity=identity, target_bindings=bindings, package=package,
            package_kind="full", decoded=positive, negatives=negatives,
            header=package_tools.package_info(blob, 30244, 30245))))
    print(json.dumps(dict(result="DISCOVERY_SUCCESSOR_ASSETS_VERIFIED", package=package, identity=identity)), flush=True)


if __name__ == "__main__":
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                "explicit root and isolated Python required")
    main()
