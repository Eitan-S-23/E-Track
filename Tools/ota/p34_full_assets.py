"""Host-only, write-once successor of the measured N03 receiver, not probe T."""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import time

VERSION, VERSION_NAME = 30217, "3.2.17-p34n"
SERVED_NAME = "prefix-n03full-full.etu"
RELEASE_KEY = "p34-n03-full"
RELATIVE = ".cache/p34-session/n03-full/assets/result.json"
RESULT = "N03_FULL_ASSETS_HOST_VERIFIED"


def require(value, message):
    if not value:
        raise RuntimeError(message)


def same_executable(receiver, target):
    require(len(receiver) == len(target) and len(receiver) > 0x460 and
            receiver[:0x400] == target[:0x400] and receiver[0x460:] == target[0x460:],
            "successor must retain every executable byte of N03")


def load(c):
    """Recheck immutable files and executable equivalence without regenerating them."""
    path = c.checked(c.ROOT / RELATIVE)
    value = c.read(path)
    require(value["result"] == RESULT and value["hardware"] is False and
            value["independent_acceptance"] is False, "full assets are not host-verified")
    for item in value["inputs"] + value["outputs"]:
        require(c.record(c.checked(item["path"])) == item, "full asset input/output changed: " + item["path"])
    require(value["receiver_bindings"] == c.bindings and c.receiver_version == 30215 and
            value["receiver"] == c.bindings["profile"]["image"], "full assets belong to a different receiver")
    require(value["target_identity"]["version_code"] == VERSION and
            value["target_identity"]["version_name"] == VERSION_NAME and
            value["served_name"] == SERVED_NAME and value["release_key"] == RELEASE_KEY,
            "full successor version/naming changed")
    source = Path(value["receiver"]["path"]).read_bytes()
    target = Path(value["target"]["path"]).read_bytes()
    same_executable(source, target)
    require(value["target"]["sha256"] == value["target_identity"]["raw_image_sha256"] and
            value["target"]["bytes"] == value["target_identity"]["image_len"], "full target raw identity differs")
    expected = copy.deepcopy(c.bindings)
    expected["profile"].update(image=value["target"], identity=value["target_identity"], prefix=target[:0x460].hex())
    require(value["target_bindings"] == expected, "header-only successor changed layout/MAP/Boot bindings")
    profile = expected["profile"]
    text = Path(profile["map"]["path"]).read_text(encoding="utf-8")
    require(c.helper.bind_receiver(c.m, text, target, profile) == profile["symbols"], "successor MAP/image mismatch")
    api = c.load("p34_full_asset_checks", c.ROOT / "Tools/ota/prepare_baud_assets.py")
    api.package_info(Path(value["package"]["path"]).read_bytes(), 30215, VERSION)
    require(all(value["decoded"][key] is True for key in
                ("passed", "byte_identical", "boot_ok", "guards_ok", "workspace_lifecycle_ok")) and
            value["decoded"]["image_bytes"] == len(target), "native full decode proof failed")
    require(len(value["negatives"]) == 4 and all(item["result"]["passed"] is True and
            item["result"]["prepares"] == 0 for item in value["negatives"]), "negative package gates missing")
    require(Path(value["decoded_image"]["path"]).read_bytes() == target, "Python decoded image differs")
    require(value["package"] != c.n03["groups"]["probe"]["package"] and
            value["package"] != c.n03["groups"]["receiver"]["package"], "R/T cannot be served as the successor")
    return value


def prepare(c):
    """Use the existing production packer and native decoder; never rebuild R/T."""
    require(c.receiver_version == 30215 and c.group == "n03-b", "prepare from the exact measured N03 receiver")
    require(not os.environ.get("OTA_AES_KEY"), "external package-key override rejected")
    out = c.checked(c.ROOT / RELATIVE).parent
    if (out / "result.json").exists():
        load(c)
        return dict(result=RESULT, manifest=c.record(out / "result.json"), reused=True, device_operations=0)
    require(not out.exists(), "partial full-asset preparation exists; preserve it instead of changing the nonce")
    api = c.load("p34_full_asset_tools", c.ROOT / "Tools/ota/prepare_baud_assets.py")
    api.FW = c.HERE / "n03/fw"
    raw, decoder = c.n03["receiver_raw"], c.n03["decoder"]
    inputs = [raw, decoder, c.bindings["profile"]["image"], c.bindings["profile"]["map"],
              c.bindings["profile"]["elf"], c.bindings["whole_boot"],
              c.record(c.HERE / "n03/assets/result.json"), c.record(c.HERE / "n03/mcu-bindings.json"),
              c.record(Path(__file__)), c.record(c.ROOT / "Tools/ota/prepare_baud_assets.py")]
    inputs += [c.record(path) for path in sorted((api.FW / "Tools").glob("*.py"))]
    for item in inputs:
        require(c.record(c.checked(item["path"])) == item, "asset preparation input changed")
    require(raw == c.n03["receiver_raw"] and raw["bytes"] == c.bindings["profile"]["image"]["bytes"],
            "N03 raw build is not bound")
    source = Path(c.bindings["profile"]["image"]["path"]).read_bytes()
    same_executable(source, Path(raw["path"]).read_bytes())
    steps = ("finalize", "pack", "unpack", "decode", "payload-crc", "truncated", "same-version", "wrong-flags")
    paths = [out / name for name in ("images/30217-n03.bin", "images/decoded.bin", "packages/full.etu",
                                    "inputs.json", "result.json", "failed.json")]
    paths += [out / "logs" / (step + suffix) for step in steps for suffix in (".stdout", ".stderr", ".json")]
    paths += [out / "negative" / (name + ".etu") for name in steps[4:]]
    for path in paths:
        c.checked(path)
    # The reused host environment directs every controllable home/cache/temp into OUT.
    c.OUT = c.host.OUT = out
    env = c.environment()
    for path in paths:
        c.checked(path.parent).mkdir(parents=True, exist_ok=True)
    c.save(out / "inputs.json", dict(inputs=inputs, environment={key: env.get(key) for key in
        ("TEMP", "TMP", "TMPDIR", "HOME", "USERPROFILE", "APPDATA", "LOCALAPPDATA")}))
    commands = []

    def run(step, args):
        begun = time.monotonic()
        result = subprocess.run(list(map(str, args)), cwd=c.ROOT, env=env, stdin=subprocess.DEVNULL,
            capture_output=True, timeout=180, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        stdout = c.raw(out / "logs" / (step + ".stdout"), result.stdout)
        stderr = c.raw(out / "logs" / (step + ".stderr"), result.stderr)
        path = out / "logs" / (step + ".json")
        c.save(path, dict(args=list(map(str, args)), cwd=str(c.ROOT), exit=result.returncode,
                         seconds=time.monotonic() - begun, stdout=stdout, stderr=stderr))
        commands.append(c.record(path))
        require(result.returncode == 0, "full asset step failed: " + step)
        return result.stdout

    image, package, decoded = out / "images/30217-n03.bin", out / "packages/full.etu", out / "images/decoded.bin"
    try:
        run("finalize", api.python_tool("etu_pack.py", ["finalize", "--app", raw["path"], "--out", image,
            "--ver-name", VERSION_NAME, "--build-ts", "1786320000"]))
        target = image.read_bytes()
        same_executable(source, target)
        identity = api.legacy.firmware(target)
        require(identity["version_code"] == VERSION and identity["version_name"] == VERSION_NAME,
                "finalized successor version differs")
        run("pack", api.python_tool("etu_pack.py", ["pack-full", "--app", image, "--out", package,
            "--target-vcode", str(VERSION)]))
        data = package.read_bytes()
        header = api.package_info(data, 30215, VERSION)
        run("unpack", api.python_tool("etu_unpack.py", [package, "--out", decoded, "--verify-fw-header"]))
        require(decoded.read_bytes() == target, "full Python decoder changed target bytes")
        native = json.loads(run("decode", [decoder["path"], package, c.bindings["profile"]["image"]["path"], image, "ok"]))
        require(all(native[key] is True for key in ("passed", "byte_identical", "boot_ok", "guards_ok",
                    "workspace_lifecycle_ok")), "native full decode/Boot check failed")
        negatives = []
        for name, mutation, expected in api.negatives(data, 30215):
            path = out / "negative" / (name + ".etu")
            item = c.raw(path, mutation)
            value = json.loads(run(name, [decoder["path"], path, c.bindings["profile"]["image"]["path"], image, expected]))
            require(value["passed"] is True and value["prepares"] == 0, "invalid package reached preparation: " + name)
            negatives.append(dict(name=name, package=item, result=value))
        target_bindings = copy.deepcopy(c.bindings)
        target_bindings["profile"].update(image=c.record(image), identity=identity, prefix=target[:0x460].hex())
        outputs = [c.record(image), c.record(package), c.record(decoded), *commands,
                   *(item["package"] for item in negatives)]
        for item in inputs:
            require(c.record(c.checked(item["path"])) == item, "asset preparation modified an input")
        c.save(out / "result.json", dict(result=RESULT, receiver=c.bindings["profile"]["image"],
            receiver_bindings=c.bindings, target=c.record(image), target_identity=identity,
            target_bindings=target_bindings, package=c.record(package), header=header,
            served_name=SERVED_NAME, release_key=RELEASE_KEY, decoded=native, decoded_image=c.record(decoded),
            negatives=negatives, inputs=inputs, outputs=outputs, hardware=False, independent_acceptance=False,
            executable_changes=False, no_build=True, commands=commands))
        load(c)
    except Exception as error:
        c.save(out / "failed.json", dict(error=type(error).__name__, detail=str(error), commands=commands,
            device_operations=0, preserve_partial_assets=True))
        raise
    return dict(result=RESULT, manifest=c.record(out / "result.json"), package=c.record(package),
                target=c.record(image), device_operations=0, reused=False)
