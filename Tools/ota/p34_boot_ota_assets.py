"""Explicit Boot identity transition and a best-case header-only FULL screen."""
import copy
import hashlib
import json
import os
from pathlib import Path
import runpy
import secrets
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_session as cli
import p34_boot_device as device

RELATIVE = ".cache/p34-boot/ota-assets/validated.json"
BUILD_REPORT = ".cache/p34-boot/preparation/result.json"
GROUP = cli.BOOT_COPY_GROUP
BOOT_SHA = "a63346db0dc673dc42adf6064892c466af5c4571df53cb55fe5b6ea154c1fdf4"
ACT = ROOT / ".cache/p34-boot/activation"


def transition():
    report = json.loads((ACT / "result.json").read_bytes())
    cli.require(report["result"] == "CANDIDATE_BOOT_ACTIVE_30235_CONFIRMED" and
                report["flash_verified"] and report["no_ota"], "Boot activation not verified")
    value = device.bindings()
    for side, expected in (("before", device.BOOT_SHA), ("after", BOOT_SHA)):
        raw = {k: (ACT / side / (k + ".bin")).read_bytes() for k in device.read_regions(value)}
        device.validate_snapshot(raw, value, boot_sha=expected)
        receipt = json.loads((ACT / side / "command-result.json").read_bytes())
        cli.require(receipt["exit"] == 0, "Boot activation reader did not exit normally")
    cli.require(json.loads((ACT / "flash/command-result.json").read_bytes())["exit"] == 0 and
                (ACT / "flash/console.log").read_bytes().count(b"Verify successful.") == 2,
                "Boot/App verification not recorded")
    current = copy.deepcopy(value)
    current["whole_boot"] = cli.record(ACT / "after/boot.bin")
    current["boot_map"] = cli.record(ROOT / ".cache/p34-boot/preparation/candidate/boot/X-Track-Boot.map")
    return value, current


def verify_transition(previous, current):
    old, new = transition()
    cli.require(previous == old and current == new, "only the verified Boot-only transition is allowed")


def diagnostic_package():
    result = json.loads((ROOT / ".cache/p34-rolling28/session-w28/result.json").read_bytes())
    cli.require(result["result"] == "CAPACITY_SCREEN_VERIFIED" and result["no_install"], "prior screen unresolved")
    asset = json.loads((ROOT / ".cache/p34ab/screen/assets/result.json").read_bytes())["package"]
    cli.require(cli.record(asset["path"]) == asset, "prior diagnostic package changed")
    return asset


def load():
    value = json.loads((ROOT / RELATIVE).read_bytes())
    cli.require(value["result"] == "BOOT_COPY_ASSETS_VERIFIED" and value["hardware"] is False,
                "Boot-copy assets not verified")
    for item in value["inputs"] + value["outputs"]:
        cli.require(cli.record(item["path"]) == item, "Boot-copy source/asset changed")
    verify_transition(value["historical_receiver_bindings"], value["receiver_bindings"])
    target = Path(value["target"]["path"]).read_bytes()
    source = Path(value["receiver"]["path"]).read_bytes()
    cli.require(len(source) == len(target) and source[:0x400] == target[:0x400] and
                source[0x460:] == target[0x460:], "header-only target executable changed")
    cli.require(value["target_identity"]["version_code"] == 30238 and
                value["target_identity"]["version_name"] == "3.2.38-p34b" and
                value["target_identity"]["raw_image_sha256"] == value["target"]["sha256"], "target identity changed")
    expected = copy.deepcopy(value["receiver_bindings"])
    expected["profile"].update(image=value["target"], identity=value["target_identity"], prefix=target[:0x460].hex())
    cli.require(value["target_bindings"] == expected, "target layout/Boot changed")
    cli.require(all(value["decoded"][k] is True for k in
        ("passed", "byte_identical", "boot_ok", "guards_ok", "workspace_lifecycle_ok")), "native decoder failure")
    cli.require(len(value["negatives"]) == 4 and all(x["native"]["passed"] and x["native"]["prepares"] == 0
                for x in value["negatives"]), "package rejection proofs missing")
    return value


def load_for_context(c, specification):
    cli.require(specification == cli.ALL_PATCH_GROUPS[GROUP], "unknown Boot-copy specification")
    value = load()
    cli.require(c.receiver_version == 30235 and c.bindings == value["historical_receiver_bindings"] and
                c.previous_assets["target"] == value["receiver"], "wrong pre-transition receiver")
    c.bindings = copy.deepcopy(value["receiver_bindings"])
    return dict(result=value["result"], specification=specification, receiver=value["receiver"],
        receiver_bindings=c.bindings, target=value["target"], target_identity=value["target_identity"],
        target_bindings=value["target_bindings"], package=value["package"], package_kind="full",
        header=value["header"], decoded=value["decoded"], decoded_image=value["target"],
        negatives=value["negatives"], manifest=cli.record(ROOT / RELATIVE))


def prepare(reuse=False):
    out = ROOT / Path(RELATIVE).parent
    io = runpy.run_path(str(ROOT / ".agents/skills/e-track-flutter-debug/scripts/host_io.py"))
    check = lambda p: io["checked_output"](ROOT, p)
    cli.require((not check(out).exists() or reuse and (out / "full.etu").is_file() and
                 (out / "result.json").is_file() and not (out / "validated.json").exists()) and
                not os.environ.get("OTA_AES_KEY"), "preserve assets/no key override")
    old, current = transition()
    g = runpy.run_path(str(ROOT / ".cache/project-governance-20260922/run.py"))
    g["environment"].__globals__["OUT"] = out
    env = g["environment"]()
    os.environ.update(env)
    sys.path.insert(0, str(Path(sys.base_prefix) / "Lib/site-packages"))
    pack_path = ROOT / ".cache/p34sr/f/Tools/etu_pack.py"
    unpack_path = ROOT / ".cache/p34sr/f/Tools/etu_unpack.py"
    pack, unpack = runpy.run_path(str(pack_path)), runpy.run_path(str(unpack_path))
    source = Path(current["profile"]["image"]["path"])
    target = bytearray(source.read_bytes())
    target[0x400:0x460] = pack["build_fw_header"](bytes(target), "3.2.38-p34b", 1786320000)
    unpack["verify_fw_header"](bytes(target), "Boot-copy target")
    if reuse:
        cli.require((out / "target.bin").read_bytes() == bytes(target), "preserved target differs")
        blob = (out / "full.etu").read_bytes()
    else:
        nonce = secrets.token_bytes(16)
        payload = pack["aes_ctr_xcrypt"](bytes.fromhex(pack["DEFAULT_KEY_HEX"]), nonce,
            pack["lzma_alone_encode"](bytes(target)), True)
        blob = pack["build_etu_header"](11, nonce, payload, 30238, 0, bytes(8)) + payload
    outputs = []
    def write(name, data):
        path = check(out / name)
        path.parent.mkdir(parents=True, exist_ok=True)
        if reuse and path.exists():
            cli.require(path.read_bytes() == bytes(data), "preserved asset differs: " + name)
        else:
            with path.open("xb") as stream:
                stream.write(data)
        item = cli.record(path)
        outputs.append(item)
        return item
    target_record, package = write("target.bin", target), write("full.etu", blob)
    tools = cli.load_module("boot_copy_pack_tools", ROOT / "Tools/ota/prepare_baud_assets.py")
    identity = tools.legacy.firmware(bytes(target))
    decoder = json.loads((ROOT / ".cache/p34-next/n03/assets/result.json").read_bytes())["decoder"]
    cli.require(cli.record(decoder["path"]) == decoder, "native decoder changed")
    def decode(name, item, expected):
        p = subprocess.run([decoder["path"], item["path"], str(source), target_record["path"], expected],
            cwd=ROOT, env=env, capture_output=True, timeout=180,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        write(name + ("-r2.log" if reuse else ".log"), p.stdout + p.stderr)
        cli.require(p.returncode == 0, "native decode/rejection failed: " + name)
        return json.loads(p.stdout)
    decoded = decode("positive", package, "ok")
    negatives = []
    for name, data, expected in tools.negatives(blob, 30235):
        item = write(name + ".etu", data)
        negatives.append(dict(name=name, package=item, native=decode(name, item, expected)))
    expected = copy.deepcopy(current)
    expected["profile"].update(image=target_record, identity=identity, prefix=bytes(target[:0x460]).hex())
    inputs = [cli.record(p) for p in (Path(__file__), Path(device.__file__), pack_path, unpack_path,
        ACT / "result.json", ACT / "plan.json", ACT / "after/result.json")]
    inputs += [decoder, current["profile"]["image"], current["profile"]["map"], current["whole_boot"], current["boot_map"]]
    if reuse:
        inputs.append(cli.record(out / "result.json"))
    io["write_json"](ROOT, ROOT / RELATIVE, dict(result="BOOT_COPY_ASSETS_VERIFIED", hardware=False,
        historical_receiver_bindings=old, receiver_bindings=current, receiver=current["profile"]["image"],
        target=target_record, target_identity=identity, target_bindings=expected, package=package,
        header=tools.package_info(blob, 30235, 30238), decoded=decoded, negatives=negatives, inputs=inputs, outputs=outputs))
    load()
    print("BOOT_COPY_ASSETS_VERIFIED", package["bytes"], package["sha256"])


if __name__ == "__main__":
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                "isolated explicit root required")
    cli.require(sys.argv[1:] in ([], ["finish"]), "unknown preparation mode")
    prepare(reuse=sys.argv[1:] == ["finish"])
