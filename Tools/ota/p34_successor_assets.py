"""Write-once header-only N03 successors for explicitly declared follow-up cells."""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import re
import subprocess
import time

RESULT = "N03_SUCCESSOR_ASSETS_HOST_VERIFIED"


def require(value, message):
    if not value:
        raise RuntimeError(message)


def receiver(c, spec):
    require(set(spec) == {"receiver", "target_version", "version_name", "served_name", "release_key", "assets", "parent_assets"},
            "invalid declared successor specification")
    require(type(spec["receiver"]) is int and type(spec["target_version"]) is int and
            30215 <= spec["receiver"] < spec["target_version"] < 40000 and
            re.fullmatch(r"3\.2\.\d+-p34n", spec["version_name"]) and
            re.fullmatch(r"prefix-[a-z0-9-]+-full\.etu", spec["served_name"]), "invalid N03 successor identity")
    parent = c.previous_assets
    require(c.receiver_version == spec["receiver"] and c.bindings == parent["target_bindings"] and
            c.bindings["profile"]["image"] == parent["target"] and
            parent["target_identity"]["version_code"] == spec["receiver"], "successor requires the bound completed receiver")
    require(c.read(c.checked(c.ROOT / spec["parent_assets"])) == parent, "parent asset manifest changed")
    return parent["target"]


def same_executable(c, before, after):
    c.load("p34_successor_executable", c.ROOT / "Tools/ota/p34_full_assets.py").same_executable(before, after)


def load(c, spec):
    source = receiver(c, spec)
    path = c.checked(c.ROOT / spec["assets"])
    value = c.read(path)
    require(value["result"] == RESULT and value["specification"] == spec and
            value["hardware"] is False and value["independent_acceptance"] is False, "successor preparation/specification differs")
    require(value["receiver"] == source and value["receiver_bindings"] == c.bindings, "successor receiver changed")
    for item in value["inputs"] + value["outputs"]:
        require(c.record(c.checked(item["path"])) == item, "successor input/output changed: " + item["path"])
    frozen = value["generator_snapshot"]
    require(Path(frozen["path"]) == path.parent / "sources/p34_successor_assets.py" and
            frozen in value["inputs"] and c.record(c.checked(frozen["path"])) == frozen and
            (frozen["bytes"], frozen["sha256"]) == tuple(value["generator"][key] for key in ("bytes", "sha256")),
            "successor generator provenance differs")
    target = Path(value["target"]["path"]).read_bytes()
    same_executable(c, Path(source["path"]).read_bytes(), target)
    require(value["target_identity"]["version_code"] == spec["target_version"] and
            value["target_identity"]["version_name"] == spec["version_name"] and
            value["target"]["sha256"] == value["target_identity"]["raw_image_sha256"] and
            value["target"]["bytes"] == value["target_identity"]["image_len"], "successor target identity differs")
    expected = copy.deepcopy(c.bindings)
    expected["profile"].update(image=value["target"], identity=value["target_identity"], prefix=target[:0x460].hex())
    require(value["target_bindings"] == expected, "successor changed MAP/layout/Boot")
    profile = expected["profile"]
    require(c.helper.bind_receiver(c.m, Path(profile["map"]["path"]).read_text(encoding="utf-8"), target, profile) ==
            profile["symbols"], "successor MAP/image binding differs")
    api = c.load("p34_successor_checks", c.ROOT / "Tools/ota/prepare_baud_assets.py")
    api.package_info(Path(value["package"]["path"]).read_bytes(), spec["receiver"], spec["target_version"])
    require(all(value["decoded"][key] is True for key in
                ("passed", "byte_identical", "boot_ok", "guards_ok", "workspace_lifecycle_ok")) and
            value["decoded"]["image_bytes"] == len(target) and Path(value["decoded_image"]["path"]).read_bytes() == target,
            "successor native/Python decode proof differs")
    require(len(value["negatives"]) == 4 and all(item["result"]["passed"] is True and item["result"]["prepares"] == 0
            for item in value["negatives"]), "successor negative package gates missing")
    require(value["package"] != c.previous_assets["package"], "successor cannot replay its parent package")
    return value


def prepare(c, spec):
    source = receiver(c, spec)
    require(not os.environ.get("OTA_AES_KEY"), "external package-key override rejected")
    out = c.checked(c.ROOT / spec["assets"]).parent
    if (out / "result.json").exists():
        load(c, spec)
        return dict(result=RESULT, manifest=c.record(out / "result.json"), reused=True, device_operations=0)
    require(not out.exists(), "partial successor preparation exists; preserve it instead of regenerating the nonce")
    api = c.load("p34_successor_tools", c.ROOT / "Tools/ota/prepare_baud_assets.py")
    api.FW = c.HERE / "n03/fw"
    raw, decoder = c.n03["receiver_raw"], c.n03["decoder"]
    generator = c.record(Path(__file__))
    inputs = [raw, decoder, source, c.bindings["profile"]["map"], c.bindings["profile"]["elf"], c.bindings["whole_boot"],
              c.record(c.ROOT / spec["parent_assets"]), c.record(c.HERE / "n03/assets/result.json"),
              c.record(c.HERE / "n03/mcu-bindings.json"), c.record(c.ROOT / "Tools/ota/p34_full_assets.py"),
              c.record(c.ROOT / "Tools/ota/prepare_baud_assets.py")]
    inputs += [c.record(path) for path in sorted((api.FW / "Tools").glob("*.py"))]
    for item in inputs:
        require(c.record(c.checked(item["path"])) == item, "successor preparation input changed")
    same_executable(c, Path(source["path"]).read_bytes(), Path(raw["path"]).read_bytes())
    image = out / ("images/%d-n03.bin" % spec["target_version"])
    package, decoded = out / "packages/full.etu", out / "images/decoded.bin"
    steps = ("finalize", "pack", "unpack", "decode", "payload-crc", "truncated", "same-version", "wrong-flags")
    paths = [image, package, decoded, out / "inputs.json", out / "result.json", out / "failed.json",
             out / "sources/p34_successor_assets.py"]
    paths += [out / "logs" / (step + suffix) for step in steps for suffix in (".stdout", ".stderr", ".json")]
    paths += [out / "negative" / (name + ".etu") for name in steps[4:]]
    for path in paths:
        c.checked(path)
    c.OUT = c.host.OUT = out
    env = c.environment()
    for path in paths:
        c.checked(path.parent).mkdir(parents=True, exist_ok=True)
    # Pin executed generator bytes, not a mutable source path that would invalidate an old nonce.
    frozen = c.raw(out / "sources/p34_successor_assets.py", Path(__file__).read_bytes())
    require((frozen["bytes"], frozen["sha256"]) == (generator["bytes"], generator["sha256"]), "generator changed during preparation")
    inputs.append(frozen)
    c.save(out / "inputs.json", dict(inputs=inputs, generator=generator, specification=spec,
        environment={key: env.get(key) for key in ("TEMP", "TMP", "TMPDIR", "HOME", "USERPROFILE", "APPDATA", "LOCALAPPDATA")}))
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
        require(result.returncode == 0, "successor preparation step failed: " + step)
        return result.stdout

    try:
        run("finalize", api.python_tool("etu_pack.py", ["finalize", "--app", raw["path"], "--out", image,
            "--ver-name", spec["version_name"], "--build-ts", "1786320000"]))
        target = image.read_bytes()
        same_executable(c, Path(source["path"]).read_bytes(), target)
        identity = api.legacy.firmware(target)
        require(identity["version_code"] == spec["target_version"] and identity["version_name"] == spec["version_name"],
                "successor finalizer version differs")
        run("pack", api.python_tool("etu_pack.py", ["pack-full", "--app", image, "--out", package,
            "--target-vcode", str(spec["target_version"])]))
        data = package.read_bytes()
        header = api.package_info(data, spec["receiver"], spec["target_version"])
        run("unpack", api.python_tool("etu_unpack.py", [package, "--out", decoded, "--verify-fw-header"]))
        require(decoded.read_bytes() == target, "successor Python decode differs")
        native = json.loads(run("decode", [decoder["path"], package, source["path"], image, "ok"]))
        require(all(native[key] is True for key in ("passed", "byte_identical", "boot_ok", "guards_ok", "workspace_lifecycle_ok")),
                "successor native decode/Boot checks failed")
        negatives = []
        for name, mutation, expected in api.negatives(data, spec["receiver"]):
            path = out / "negative" / (name + ".etu")
            item = c.raw(path, mutation)
            value = json.loads(run(name, [decoder["path"], path, source["path"], image, expected]))
            require(value["passed"] is True and value["prepares"] == 0, "invalid successor reached preparation")
            negatives.append(dict(name=name, package=item, result=value))
        bindings = copy.deepcopy(c.bindings)
        bindings["profile"].update(image=c.record(image), identity=identity, prefix=target[:0x460].hex())
        outputs = [c.record(image), c.record(package), c.record(decoded), *commands, *(item["package"] for item in negatives)]
        for item in inputs:
            require(c.record(c.checked(item["path"])) == item, "successor preparation modified an input")
        c.save(out / "result.json", dict(result=RESULT, specification=spec, receiver=source, receiver_bindings=c.bindings,
            target=c.record(image), target_identity=identity, target_bindings=bindings, package=c.record(package), header=header,
            decoded=native, decoded_image=c.record(decoded), negatives=negatives, generator=generator, generator_snapshot=frozen,
            inputs=inputs, outputs=outputs, hardware=False, independent_acceptance=False, executable_changes=False, no_build=True))
        load(c, spec)
    except Exception as error:
        c.save(out / "failed.json", dict(error=type(error).__name__, detail=str(error), commands=commands,
            device_operations=0, preserve_partial_assets=True))
        raise
    return dict(result=RESULT, manifest=c.record(out / "result.json"), package=c.record(package), target=c.record(image),
                device_operations=0, reused=False)
