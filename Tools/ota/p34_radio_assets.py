"""Host-only four-arm header-successor preparation from confirmed30245."""
import copy
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_session as cli
import p34_discovery_trial as parent
import p34_install_cost as host

OUT = ROOT / ".cache/p34-radio-fix/assets"
MATRIX = (("baseline", False, False), ("scan", True, False),
          ("priority", False, True), ("combined", True, True))


def main():
    s = cli.Store(ROOT)
    cli.require(not OUT.exists() and not os.environ.get("OTA_AES_KEY"), "preserve existing assets/no key override")
    s.checked(OUT)
    group = parent.load_assets(s)
    pointer = s.read(parent.TRIAL / "analysis/latest.json")
    cli.require(cli.record(pointer["report"]["path"]) == pointer["report"], "original report changed")
    report = s.read(pointer["report"]["path"])
    cli.require(report["result"] == "FULL_INSTALL_VERIFIED" and report["summary"]["outcome"] == "completed" and
                report["summary"]["input"]["targetVersionCode"] == 30245 and
                report["summary"]["input"]["targetImageSha256"] == group["target"]["sha256"], "confirmed30245 required")
    closure = s.read(report["after"]["path"])
    cli.require(closure["retained_verified"] and closure["reader_closed"] and "cleanup_error" not in closure and
                all(closure[k] is True for k in ("no_reset", "no_halt", "no_flash", "no_nvic_write")),
                "unresolved MCU closure")
    state = closure["final_state"]
    cli.require(state["bcb_state"] == 4 and all(state[k] == 1 for k in ("confirm_done", "state_snapped", "sd_ready")),
                "ordinary confirmation missing")
    inputs = [pointer["report"], *report["inputs"].values(), report["after"], cli.record(parent.ASSETS)]
    for phase in ("initial_identity", "final_identity"):
        for name, expected in (("app", group["target"]), ("boot", group["target_bindings"]["whole_boot"])):
            item = closure[phase][name]
            cli.require((item["bytes"], item["sha256"]) == (expected["bytes"], expected["sha256"]), "raw identity differs")
            inputs.append(item)
    inputs += [parent.parent.closed(s, parent.TRIAL / "runtime" / n) for n in ("coordinator", "network", "s04")]
    for item in inputs:
        cli.require(cli.record(s.checked(item["path"])) == item, "original input changed")
    env = host.environment(s, OUT)
    os.environ.update(env)
    sys.path.insert(0, str(Path(sys.base_prefix) / "Lib/site-packages"))
    previous = parent.parent.previous
    pack = cli.load_module("radio_pack", previous.erase.candidate.AREA / "f/Tools/etu_pack.py")
    unpack = cli.load_module("radio_unpack", previous.erase.candidate.AREA / "f/Tools/etu_unpack.py")
    package_tools = cli.load_module("radio_package_tools", ROOT / "Tools/ota/prepare_baud_assets.py")
    decoder = s.read(ROOT / ".cache/p34-next/n03/assets/result.json")["decoder"]
    previous.historical.resolve(decoder)
    inputs += [decoder, cli.record(__file__), *[cli.record(m.__file__) for m in (pack, unpack, package_tools, previous.shared)]]
    receiver, bindings = group["target"], group["target_bindings"]
    groups, outputs = {}, []
    for index, (name, pause, high) in enumerate(MATRIX):
        current, target_version = 30245 + index, 30246 + index
        where = s.checked(OUT / name)
        before = Path(receiver["path"]).read_bytes()
        raw = bytearray(before)
        version_name = "3.2.%d-p34r" % (46 + index)
        raw[0x400:0x460] = pack.build_fw_header(bytes(raw), version_name, 1786320000)
        cli.require(before[:0x400] + before[0x460:] == raw[:0x400] + raw[0x460:], "executable changed")
        target = s.raw(where / "target.bin", bytes(raw))
        identity = previous.shared.identity(bytes(raw), unpack)
        cli.require(identity["version_code"] == target_version, "target identity differs")
        blob = previous.shared.wrap_payload(pack, pack.lzma_alone_encode(bytes(raw)), before, bytes(raw), kind="full")
        package = s.raw(where / "target.etu", blob)
        def native(label, item, expected):
            return json.loads(host.command(s, where, label,
                [decoder["path"], item["path"], receiver["path"], target["path"], expected], env, 180))
        positive = native("positive", package, "ok")
        cli.require(all(positive[k] for k in ("passed", "byte_identical", "boot_ok", "guards_ok", "workspace_lifecycle_ok")),
                    "positive native decode failed")
        negatives = []
        outputs += [target, package]
        for label, broken, expected in package_tools.negatives(blob, current):
            item = s.raw(where / (label + ".etu"), broken)
            result = native(label, item, expected)
            cli.require(result["passed"] and result["prepares"] == 0, "negative native decode failed")
            negatives.append(dict(name=label, native=result, package=item))
            outputs.append(item)
        target_bindings = copy.deepcopy(bindings)
        target_bindings["profile"].update(image=target, identity=identity, prefix=bytes(raw[:0x460]).hex())
        groups[name] = dict(specification=dict(receiver=current, target_version=target_version,
            version_name=version_name, served_name="p34-radio-" + name + ".etu", release_key="p34-radio-" + name,
            kind="full", pauseScanDuringOta=pause, androidHighPriority=high),
            receiver=receiver, receiver_bindings=bindings, target=target, target_identity=identity,
            target_bindings=target_bindings, package=package, package_kind="full", decoded=positive,
            negatives=negatives, header=package_tools.package_info(blob, current, target_version),
            requires_actual_predecessor_verification=True)
        outputs += [cli.record(p) for p in where.glob("*.log")]
        receiver, bindings = target, target_bindings
    s.write(OUT / "result.json", dict(result="RADIO_MATRIX_ASSETS_VERIFIED", hardware=False,
        confirmed_start=30245, order=[x[0] for x in MATRIX], groups=groups, inputs=inputs, outputs=outputs,
        prepared_lineage_is_not_installed_identity=True))
    print(json.dumps(dict(result="RADIO_MATRIX_ASSETS_VERIFIED", packages={k:v["package"] for k,v in groups.items()})), flush=True)


if __name__ == "__main__":
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                "explicit root and isolated Python required")
    main()
