"""Prepare one header-only30249-to30250 FULL candidate; never install firmware."""
import copy
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_radio_assets as original

OUT = ROOT / ".cache/p34-batch-fix/assets"
PRIOR = ROOT / ".cache/p34-radio-fix/recorder-fix/trials-v3/combined"
REPORT = PRIOR / "analysis/1790939796737635200/result.json"


def main():
    cli, host = original.cli, original.host
    s = cli.Store(ROOT)
    cli.require(not OUT.exists() and not os.environ.get("OTA_AES_KEY"), "preserve assets/no key override")
    s.checked(OUT)
    report = s.read(REPORT)
    group = s.read(original.OUT / "result.json")["groups"]["combined"]
    cli.require(report["result"] == "FULL_INSTALL_VERIFIED" and
                report["summary"]["input"]["targetVersionCode"] == 30249 and
                report["summary"]["input"]["targetImageSha256"] == group["target"]["sha256"], "wrong predecessor")
    inputs = [cli.record(REPORT), cli.record(original.OUT / "result.json"), report["after"]]
    closure = s.read(report["after"]["path"])
    cli.require(closure["retained_verified"] and closure["reader_closed"] and "cleanup_error" not in closure,
                "unresolved final readback")
    cli.require(closure["final_state"]["bcb_state"] == 4 and
                all(closure["final_state"][k] == 1 for k in ("confirm_done", "state_snapped", "sd_ready")),
                "normal confirmation required")
    for phase in ("initial_identity", "final_identity"):
        for name, expected in (("app", group["target"]), ("boot", group["target_bindings"]["whole_boot"])):
            item = closure[phase][name]
            cli.require((item["bytes"], item["sha256"]) == (expected["bytes"], expected["sha256"]), "identity differs")
            inputs.append(item)
    for name in ("coordinator", "network", "s04"):
        path = PRIOR / "runtime" / name / "closed.json"
        owner = s.read(path)
        cli.require(owner["worker_exit"] == 0 and not owner["forced_termination"], "old owner unresolved")
        inputs.append(cli.record(path))
    for item in inputs:
        cli.require(cli.record(s.checked(item["path"])) == item, "original evidence changed")
    env = host.environment(s, OUT)
    os.environ.update(env)
    sys.path.insert(0, str(Path(sys.base_prefix) / "Lib/site-packages"))
    previous = original.parent.parent.previous
    pack = cli.load_module("batch_pack", previous.erase.candidate.AREA / "f/Tools/etu_pack.py")
    unpack = cli.load_module("batch_unpack", previous.erase.candidate.AREA / "f/Tools/etu_unpack.py")
    package_tools = cli.load_module("batch_package_tools", ROOT / "Tools/ota/prepare_baud_assets.py")
    decoder = s.read(ROOT / ".cache/p34-next/n03/assets/result.json")["decoder"]
    previous.historical.resolve(decoder)
    receiver, bindings = group["target"], group["target_bindings"]
    cli.require(cli.record(receiver["path"]) == receiver, "receiver asset changed")
    before = Path(receiver["path"]).read_bytes()
    raw = bytearray(before)
    raw[0x400:0x460] = pack.build_fw_header(bytes(raw), "3.2.50-p34b", 1786320000)
    cli.require(before[:0x400] + before[0x460:] == raw[:0x400] + raw[0x460:], "executable changed")
    target = s.raw(OUT / "target.bin", bytes(raw))
    identity = previous.shared.identity(bytes(raw), unpack)
    cli.require(identity["version_code"] == 30250, "wrong target header")
    blob = previous.shared.wrap_payload(pack, pack.lzma_alone_encode(bytes(raw)), before, bytes(raw), kind="full")
    package = s.raw(OUT / "p34-batch-full.etu", blob)
    def native(label, item, expected):
        return json.loads(host.command(s, OUT, label,
            [decoder["path"], item["path"], receiver["path"], target["path"], expected], env, 180))
    decoded = native("positive", package, "ok")
    cli.require(all(decoded[k] for k in ("passed", "byte_identical", "boot_ok", "guards_ok", "workspace_lifecycle_ok")),
                "native positive failed")
    negatives = []
    for label, broken, expected in package_tools.negatives(blob, 30249):
        item = s.raw(OUT / (label + ".etu"), broken)
        result = native(label, item, expected)
        cli.require(result["passed"] and result["prepares"] == 0, "native negative failed")
        negatives.append(dict(name=label, package=item, native=result))
    target_bindings = copy.deepcopy(bindings)
    target_bindings["profile"].update(image=target, identity=identity, prefix=bytes(raw[:0x460]).hex())
    s.write(OUT / "result.json", dict(result="BATCH_ASSETS_VERIFIED", hardware=False,
        specification=dict(receiver=30249, target_version=30250, version_name="3.2.50-p34b",
            served_name="p34-batch-full.etu", release_key="p34-batch", kind="full",
            pauseScanDuringOta=True, androidHighPriority=True, dataBatchFrames=3),
        receiver=receiver, receiver_bindings=bindings, target=target, target_identity=identity,
        target_bindings=target_bindings, package=package, package_kind="full", decoded=decoded,
        negatives=negatives, inputs=inputs + [decoder, cli.record(__file__)],
        requires_actual_predecessor_verification=True))
    print(json.dumps(dict(result="BATCH_ASSETS_VERIFIED", package=package, target=target, hardware=False)))


if __name__ == "__main__":
    original.cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                         "explicit root and isolated Python required")
    main()
