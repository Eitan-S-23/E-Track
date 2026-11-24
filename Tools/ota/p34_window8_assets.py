"""Write-once V successor for the U-receiver/window-8 cell; never regenerate U."""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import subprocess
import time

RECEIVER, VERSION, VERSION_NAME = 30217, 30218, "3.2.18-p34n"
SERVED_NAME, RELEASE_KEY = "prefix-n03w8-full.etu", "p34-n03-window8"
RELATIVE = ".cache/p34-session/n03-window8/assets/result.json"
U_RELATIVE = ".cache/p34-session/n03-full/assets/result.json"
RESULT = "N03_WINDOW8_ASSETS_HOST_VERIFIED"


def require(value, message):
    if not value:
        raise RuntimeError(message)


def receiver(c):
    require(c.receiver_version == RECEIVER and c.bindings == c.u_assets["target_bindings"] and
            c.bindings["profile"]["image"] == c.u_assets["target"], "window-8 assets require the exact U receiver")
    require(c.read(c.ROOT / U_RELATIVE) == c.u_assets, "U manifest changed")
    return c.bindings["profile"]["image"]


def same_executable(c, before, after):
    api = c.load("p34_window8_executable", c.ROOT / "Tools/ota/p34_full_assets.py")
    api.same_executable(before, after)


def load(c):
    source = receiver(c)
    value = c.read(c.checked(c.ROOT / RELATIVE))
    require(value["result"] == RESULT and value["hardware"] is False and
            value["independent_acceptance"] is False, "V is not a host-verified preparation")
    require(value["receiver_version"] == RECEIVER and value["receiver"] == source and
            value["receiver_bindings"] == c.bindings, "V receiver identity changed")
    for item in value["inputs"] + value["outputs"]:
        require(c.record(c.checked(item["path"])) == item, "V input/output changed: " + item["path"])
    target = Path(value["target"]["path"]).read_bytes()
    same_executable(c, Path(source["path"]).read_bytes(), target)
    require(value["target_identity"]["version_code"] == VERSION and
            value["target_identity"]["version_name"] == VERSION_NAME and
            value["target"]["sha256"] == value["target_identity"]["raw_image_sha256"] and
            value["target"]["bytes"] == value["target_identity"]["image_len"] and
            value["served_name"] == SERVED_NAME and value["release_key"] == RELEASE_KEY,
            "V version/image/naming changed")
    expected = copy.deepcopy(c.bindings)
    expected["profile"].update(image=value["target"], identity=value["target_identity"], prefix=target[:0x460].hex())
    require(value["target_bindings"] == expected, "V changed MAP/layout/Boot bindings")
    profile = expected["profile"]
    require(c.helper.bind_receiver(c.m, Path(profile["map"]["path"]).read_text(encoding="utf-8"), target, profile) ==
            profile["symbols"], "V MAP/image binding differs")
    api = c.load("p34_window8_checks", c.ROOT / "Tools/ota/prepare_baud_assets.py")
    api.package_info(Path(value["package"]["path"]).read_bytes(), RECEIVER, VERSION)
    require(all(value["decoded"][key] is True for key in
                ("passed", "byte_identical", "boot_ok", "guards_ok", "workspace_lifecycle_ok")) and
            value["decoded"]["image_bytes"] == len(target) and Path(value["decoded_image"]["path"]).read_bytes() == target,
            "V native/Python decode proof differs")
    require(len(value["negatives"]) == 4 and all(item["result"]["passed"] is True and item["result"]["prepares"] == 0
            for item in value["negatives"]), "V negative package gates missing")
    require(value["package"] not in (c.u_assets["package"], c.n03["groups"]["probe"]["package"],
            c.n03["groups"]["receiver"]["package"]), "R/T/U cannot be the V package")
    return value


def prepare(c):
    source = receiver(c)
    require(not os.environ.get("OTA_AES_KEY"), "external package-key override rejected")
    out = c.checked(c.ROOT / RELATIVE).parent
    if (out / "result.json").exists():
        load(c)
        return dict(result=RESULT, manifest=c.record(out / "result.json"), reused=True, device_operations=0)
    require(not out.exists(), "partial V preparation exists; preserve it instead of regenerating the nonce")
    api = c.load("p34_window8_tools", c.ROOT / "Tools/ota/prepare_baud_assets.py")
    api.FW = c.HERE / "n03/fw"
    raw, decoder = c.n03["receiver_raw"], c.n03["decoder"]
    inputs = [raw, decoder, source, c.bindings["profile"]["map"], c.bindings["profile"]["elf"], c.bindings["whole_boot"],
              c.record(c.ROOT / U_RELATIVE), c.record(c.HERE / "n03/assets/result.json"),
              c.record(c.HERE / "n03/mcu-bindings.json"), c.record(Path(__file__)),
              c.record(c.ROOT / "Tools/ota/p34_full_assets.py"), c.record(c.ROOT / "Tools/ota/prepare_baud_assets.py")]
    inputs += [c.record(path) for path in sorted((api.FW / "Tools").glob("*.py"))]
    for item in inputs:
        require(c.record(c.checked(item["path"])) == item, "V preparation input changed")
    same_executable(c, Path(source["path"]).read_bytes(), Path(raw["path"]).read_bytes())
    image, package, decoded = out / "images/30218-n03.bin", out / "packages/full.etu", out / "images/decoded.bin"
    steps = ("finalize", "pack", "unpack", "decode", "payload-crc", "truncated", "same-version", "wrong-flags")
    paths = [image, package, decoded, out / "inputs.json", out / "result.json", out / "failed.json"]
    paths += [out / "logs" / (step + suffix) for step in steps for suffix in (".stdout", ".stderr", ".json")]
    paths += [out / "negative" / (name + ".etu") for name in steps[4:]]
    for path in paths:
        c.checked(path)
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
        log = out / "logs" / (step + ".json")
        c.save(log, dict(args=list(map(str, args)), cwd=str(c.ROOT), exit=result.returncode,
                        seconds=time.monotonic() - begun, stdout=stdout, stderr=stderr))
        commands.append(c.record(log))
        require(result.returncode == 0, "V preparation step failed: " + step)
        return result.stdout

    try:
        run("finalize", api.python_tool("etu_pack.py", ["finalize", "--app", raw["path"], "--out", image,
            "--ver-name", VERSION_NAME, "--build-ts", "1786320000"]))
        target = image.read_bytes()
        same_executable(c, Path(source["path"]).read_bytes(), target)
        identity = api.legacy.firmware(target)
        require(identity["version_code"] == VERSION and identity["version_name"] == VERSION_NAME, "V finalizer version differs")
        run("pack", api.python_tool("etu_pack.py", ["pack-full", "--app", image, "--out", package, "--target-vcode", str(VERSION)]))
        data = package.read_bytes()
        header = api.package_info(data, RECEIVER, VERSION)
        run("unpack", api.python_tool("etu_unpack.py", [package, "--out", decoded, "--verify-fw-header"]))
        require(decoded.read_bytes() == target, "V Python decode differs")
        native = json.loads(run("decode", [decoder["path"], package, source["path"], image, "ok"]))
        require(all(native[key] is True for key in ("passed", "byte_identical", "boot_ok", "guards_ok", "workspace_lifecycle_ok")),
                "V native decode/Boot checks failed")
        negatives = []
        for name, mutation, expected in api.negatives(data, RECEIVER):
            path = out / "negative" / (name + ".etu")
            item = c.raw(path, mutation)
            value = json.loads(run(name, [decoder["path"], path, source["path"], image, expected]))
            require(value["passed"] is True and value["prepares"] == 0, "invalid V package reached preparation")
            negatives.append(dict(name=name, package=item, result=value))
        bindings = copy.deepcopy(c.bindings)
        bindings["profile"].update(image=c.record(image), identity=identity, prefix=target[:0x460].hex())
        outputs = [c.record(image), c.record(package), c.record(decoded), *commands, *(item["package"] for item in negatives)]
        for item in inputs:
            require(c.record(c.checked(item["path"])) == item, "V preparation modified an input")
        c.save(out / "result.json", dict(result=RESULT, receiver_version=RECEIVER, receiver=source, receiver_bindings=c.bindings,
            target=c.record(image), target_identity=identity, target_bindings=bindings, package=c.record(package), header=header,
            served_name=SERVED_NAME, release_key=RELEASE_KEY, decoded=native, decoded_image=c.record(decoded), negatives=negatives,
            inputs=inputs, outputs=outputs, hardware=False, independent_acceptance=False, executable_changes=False, no_build=True))
        load(c)
    except Exception as error:
        c.save(out / "failed.json", dict(error=type(error).__name__, detail=str(error), commands=commands,
            device_operations=0, preserve_partial_assets=True))
        raise
    return dict(result=RESULT, manifest=c.record(out / "result.json"), package=c.record(package), target=c.record(image),
                device_operations=0, reused=False)
