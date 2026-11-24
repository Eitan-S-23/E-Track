"""Prepare and verify byte-preserving ACK-batch FULL assets, never install."""
import argparse
import json
import os
from pathlib import Path
import struct
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import p34_session as cli
import p34_patch_assets as shared

ROOT = Path(__file__).resolve().parents[2]
AREA = ROOT / ".cache/p34ab"
RELATIVE = ".cache/p34ab/assets/session-assets.json"
BUILD_REPORT = ".cache/p34ab/build.json"
GROUP = "ack-batch-bootstrap"


def diagnostic_package():
    store = cli.Store(ROOT)
    area = ROOT / ".cache/p34ag/screen"
    assets = store.read(area / "assets/result.json")
    result = store.read(area / "session-w31/result.json")
    closure = store.read(area / "session-w31/mcu/closure.json")
    owner = store.read(area / "session-w31/owner/closed.json")
    package = assets["package"]
    cli.require(cli.record(store.checked(package["path"])) == package and
                result["result"] == "CAPACITY_SCREEN_VERIFIED" and len(result["trials"]) == 2 and
                closure["retained_verified"] is True and closure["reader_closed"] is True and
                owner["worker_exit"] == 0 and owner["forced_termination"] is False,
                "burst diagnostic outcome unresolved")
    cli.require(closure["final_state"]["session"]["durable_off"] == 0 and
                closure["final_state"]["session"]["package_sha256"] == package["sha256"],
                "burst diagnostic journal differs")
    return package


def validate(value):
    cli.require(value["result"] == "ACK_BATCH_ASSETS_VERIFIED" and value["hardware"] is False and
                value["build_review"]["passed"] is True and value["build_review"]["errors"] == 0 and
                value["build_review"]["boot_built"] is False, "batch build not verified")
    cli.require(value["source_delta"] == ["USER/HAL/HAL_Bluetooth.cpp", "USER/HAL/p34_ack_batch.h"],
                "unexpected candidate source delta")
    image, group = value["images"]["aa"], value["groups"]["bootstrap"]
    cli.require(image["identity"]["version_code"] == 30235 and image["identity"]["version_name"] == "3.2.35-p34b" and
                group["target"] == image["image"] and group["package"] == value["package"], "batch target mismatch")
    cli.require(all(group["native"][k] is True for k in
                    ("passed", "byte_identical", "boot_ok", "guards_ok", "workspace_lifecycle_ok")), "native proof missing")
    cli.require({n["name"] for n in group["negatives"]} == {"payload-crc", "truncated", "same-version"} and
                all(n["native"]["passed"] is True and n["native"]["prepares"] == 0 for n in group["negatives"]),
                "negative decode proof missing")


def load():
    store = cli.Store(ROOT)
    value = store.read(ROOT / RELATIVE)
    validate(value)
    for item in value["inputs"] + store.read(value["source"]["path"])["files"]:
        cli.require(cli.record(store.checked(item["path"])) == item, "batch input changed: " + item["path"])
    image = value["images"]["aa"]
    actual = shared.bindings(dict(target_bindings=value["historical_receiver_bindings"]),
                             image["image"], image["identity"], value["artifacts"], value["constants"])
    cli.require(actual == image["bindings"], "batch MAP/ELF bindings differ")
    return value


def load_for_context(c, specification):
    cli.require(specification == cli.ACK_GAP_GROUPS[GROUP], "undeclared batch cell")
    value = load()
    cli.require(c.receiver_version == 30232 and c.bindings == value["historical_receiver_bindings"] and
                c.previous_assets["target"] == value["historical_receiver"], "batch requires gap receiver")
    image, group = value["images"]["aa"], value["groups"]["bootstrap"]
    return dict(result=value["result"], specification=specification,
        receiver=value["historical_receiver"], receiver_bindings=c.bindings,
        target=image["image"], target_identity=image["identity"], target_bindings=image["bindings"],
        package=group["package"], package_kind="full", header=group["header"], decoded=group["native"],
        decoded_image=image["image"], negatives=group["negatives"], manifest=cli.record(ROOT / RELATIVE))


def prepare():
    store = cli.Store(ROOT)
    out = store.checked(AREA / "assets")
    cli.require(not out.exists() and not os.environ.get("OTA_AES_KEY"), "preserve assets; no key override")
    old_path = ROOT / ".cache/p34ag/assets/session-assets.json"
    old = store.read(old_path)
    build = store.read(AREA / "build.json")
    cli.require(build["passed"] and build["errors"] == 0 and build["boot_built"] is False, "App-only build required")
    previous_source = store.read(old["source"]["path"])
    source = store.read(AREA / "source.json")
    before = {str(Path(i["path"]).relative_to(ROOT / ".cache/p34ag/f")).replace("\\", "/"): i for i in previous_source["files"]}
    after = {str(Path(i["path"]).relative_to(AREA / "f")).replace("\\", "/"): i for i in source["files"]}
    delta = sorted(n for n in before.keys() | after.keys() if before.get(n, {}).get("sha256") != after.get(n, {}).get("sha256"))
    cli.require(delta == ["USER/HAL/HAL_Bluetooth.cpp", "USER/HAL/p34_ack_batch.h"], "source delta differs")
    inputs = [cli.record(old_path), cli.record(AREA / "build.json"), cli.record(AREA / "source.json"),
              cli.record(AREA / "tests/result.json"), cli.record(Path(__file__))]
    receiver = old["images"]["aa"]["image"]
    receiver_bindings = old["images"]["aa"]["bindings"]
    decoder = next(i for i in store.read(ROOT / ".cache/p34ag/assets/result.json")["inputs"]
                   if Path(i["path"]).name == "full_image_host.exe")
    inputs += [receiver, decoder, cli.record(ROOT / "Tools/ota/p34_ack_batch.h"),
               cli.record(ROOT / "tests/ota/test_p34_ack_batch.cpp")]
    for item in inputs + source["files"]:
        cli.require(cli.record(store.checked(item["path"])) == item, "immutable input changed")
    artifacts = {Path(i["path"]).suffix: i for i in build["artifacts"] if Path(i["path"]).suffix in (".elf", ".map", ".bin", ".hex")}
    inputs += list(artifacts.values())
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONUTF8="1")
    for key in ("HOME", "USERPROFILE", "APPDATA", "LOCALAPPDATA", "TEMP", "TMP", "TMPDIR"):
        p = store.checked(out / "host" / key.lower())
        p.mkdir(parents=True, exist_ok=True)
        env[key] = str(p)
    os.environ.update(env)
    sys.path.insert(0, str(Path(sys.base_prefix) / "Lib/site-packages"))
    pack = cli.load_module("batch_pack", AREA / "f/Tools/etu_pack.py")
    unpack = cli.load_module("batch_unpack", AREA / "f/Tools/etu_unpack.py")

    def native(name, package, target, expected):
        command = [decoder["path"], package["path"], receiver["path"], target["path"], expected]
        log = store.checked(out / (name + ".log"))
        run = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, timeout=180,
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        store.raw(log, run.stdout + run.stderr)
        cli.require(run.returncode == 0, "native decode command failed")
        value = json.loads(run.stdout)
        cli.require(value["passed"] is True and value["result"] == expected, "native decode oracle failed")
        return value

    def image_package(name, raw, version):
        image = bytearray(raw)
        image[0x400:0x460] = pack.build_fw_header(bytes(image), version, 1786320000)
        data = bytes(image)
        ident = shared.identity(data, unpack)
        blob = shared.wrap_payload(pack, pack.lzma_alone_encode(data), Path(receiver["path"]).read_bytes(), data, kind="full")
        shared.decode_python(blob, Path(receiver["path"]).read_bytes(), data, "full", unpack)
        target, package = store.raw(out / (name + ".bin"), data), store.raw(out / (name + ".etu"), blob)
        proof = native(name, package, target, "ok")
        cli.require(all(proof[k] is True for k in ("byte_identical", "boot_ok", "guards_ok", "workspace_lifecycle_ok")), "native integrity failed")
        inputs.extend((target, package))
        return dict(image=target, package=package, identity=ident, native=proof), blob

    candidate, blob = image_package("batch", Path(artifacts[".bin"]["path"]).read_bytes(), "3.2.35-p34b")
    restore, _ = image_package("restore", Path(receiver["path"]).read_bytes(), "3.2.36-p34b")
    damaged = bytearray(blob); damaged[-1] ^= 1
    cases = (("payload-crc", bytes(damaged), "payload_crc"), ("truncated", blob[:-1], "package_length"),
             ("same-version", shared.header_mutation(blob, 40, struct.pack("<I", 30232)), "version"))
    negatives = []
    for name, data, expected in cases:
        package = store.raw(out / (name + ".etu"), data)
        proof = native(name, package, candidate["image"], expected)
        cli.require(proof["prepares"] == 0, "negative case reached prepare")
        negatives.append(dict(name=name, package=package, native=proof)); inputs.append(package)
    constants = old["constants"]
    binding = shared.bindings(dict(target_bindings=receiver_bindings), candidate["image"], candidate["identity"], artifacts, constants)
    value = dict(result="ACK_BATCH_ASSETS_VERIFIED", hardware=False, source=cli.record(AREA / "source.json"),
        inputs=inputs, build_review={k: build[k] for k in ("passed", "errors", "warnings", "boot_built")},
        source_delta=delta, historical_receiver=receiver, historical_receiver_bindings=receiver_bindings,
        constants=constants, artifacts=artifacts, package=candidate["package"], restore=restore,
        images=dict(aa=dict(image=candidate["image"], identity=candidate["identity"], bindings=binding)),
        groups=dict(bootstrap=dict(package=candidate["package"], target=candidate["image"], native=candidate["native"],
            negatives=negatives, header=shared.package_header(blob, "full", 30232, 30235, receiver["sha256"], unpack))))
    validate(value)
    store.write(ROOT / RELATIVE, value)
    print(json.dumps(dict(result=value["result"], candidate=candidate["package"], restore=restore["package"], hardware=False)))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare",))
    parser.parse_args()
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                "explicit root and isolated Python required")
    prepare()
