"""Immutable N04 bootstrap/measurement assets, using the existing packer/decoder."""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import subprocess
import time

RESULT = "N04_INSTALL_ASSETS_HOST_VERIFIED"
BUILD = ".cache/p34-session/n04/firmware/build.json"
FW = ".cache/p34-session/n04/fw"
BINDING_HELPER = ".cache/p34-next/n03_bindings.py"


def require(value, message):
    if not value:
        raise RuntimeError(message)


def executable(c, before, after):
    c.load("p34_n04_executable", c.ROOT / "Tools/ota/p34_full_assets.py").same_executable(before, after)


def build_inputs(c):
    report = c.read(c.ROOT / BUILD)
    require(report["result"] == "N04_APP_BUILD_PASS" and report["errors"] == 0 and report["n04_enabled"] is True and
            report["n03_profile_bytes"] == 336 and report["boot_built"] is False and report["finalized"] is False,
            "verified App-only N04 build required")
    require(c.record(c.checked(report["source_manifest"]["path"])) == report["source_manifest"],
            "N04 source provenance changed")
    by_suffix = {}
    for item in report["artifacts"]:
        path = c.checked(item["path"])
        simple = {key: item[key] for key in ("path", "bytes", "sha256")}
        require(c.record(path) == simple, "N04 build artifact changed")
        by_suffix[path.suffix] = simple
    require({".bin", ".elf", ".map"} <= set(by_suffix), "N04 build artifact set incomplete")
    require(b"P34INSTALL:" in Path(by_suffix[".bin"]["path"]).read_bytes(), "N04 diagnostic marker absent")
    return report, by_suffix


def receiver(c, spec):
    require(set(spec) == {"receiver", "target_version", "version_name", "served_name", "release_key", "assets",
                         "parent_assets", "predecessor_group"}, "invalid N04 specification")
    parent = c.previous_assets
    require(c.receiver_version == spec["receiver"] and parent["target_identity"]["version_code"] == spec["receiver"] and
            c.bindings == parent["target_bindings"] and c.bindings["profile"]["image"] == parent["target"] and
            c.read(c.ROOT / spec["parent_assets"]) == parent, "N04 receiver/predecessor asset binding differs")
    reserved_skip = spec["predecessor_group"] == "n04-diagnostic8" and (spec["receiver"], spec["target_version"]) == (30222, 30225)
    require(spec["target_version"] == spec["receiver"] + 1 or reserved_skip,
            "N04 only admits the declared next version or reserved 30222-to-30225 speed screen")
    return parent["target"]


def target_bindings(c, image, identity, artifacts):
    result = copy.deepcopy(c.bindings)
    helper = c.load("p34_n04_binding_derivation", c.ROOT / BINDING_HELPER)
    symbols = helper.derive(c.m, artifacts[".map"]["path"], image["path"], 336)
    profile = result["profile"]
    require(profile["profile_size"] == 336 and len(profile["phases"]) == 10, "N03 ABI must be preserved")
    raw = Path(image["path"]).read_bytes()
    profile.update(image=image, identity=identity, map=artifacts[".map"], elf=artifacts[".elf"],
                   prefix=raw[:0x460].hex(), symbols=symbols)
    text = Path(artifacts[".map"]["path"]).read_text(encoding="utf-8")
    layout = result["layout"]
    layout["session"] = c.m.map_bss(text, "_ZL13s_ble_session", layout["members"]["size"])
    for name, symbol in (("bcb_state", "_ZL20g_ota_state_snapshot"), ("confirm_done", "_ZL18g_ota_confirm_done"),
                         ("state_snapped", "_ZL19g_ota_state_snapped")):
        layout[name] = c.m.map_bss(text, symbol, 1)
    require(c.helper.bind_receiver(c.m, text, raw, profile) == symbols, "new receiver MAP/image/layout disagree")
    require(result["whole_boot"] == c.bindings["whole_boot"] and result["original_binding"] == c.bindings["original_binding"],
            "N04 must not change Boot")
    return result


def load(c, spec):
    source = receiver(c, spec)
    path = c.checked(c.ROOT / spec["assets"])
    value = c.read(path)
    require(value["result"] == RESULT and value["specification"] == spec and value["hardware"] is False and
            value["independent_acceptance"] is False and value["receiver"] == source and
            value["receiver_bindings"] == c.bindings, "N04 preparation identity/scope differs")
    for item in value["inputs"] + value["outputs"]:
        require(c.record(c.checked(item["path"])) == item, "N04 asset input/output changed: " + item["path"])
    frozen = value["generator_snapshot"]
    require(Path(frozen["path"]) == path.parent / "sources/p34_install_assets.py" and frozen in value["inputs"] and
            (frozen["bytes"], frozen["sha256"]) == tuple(value["generator"][key] for key in ("bytes", "sha256")),
            "N04 executed generator snapshot differs")
    _, artifacts = build_inputs(c)
    target = Path(value["target"]["path"]).read_bytes()
    executable(c, Path(artifacts[".bin"]["path"]).read_bytes(), target)
    identity = value["target_identity"]
    require(identity["version_code"] == spec["target_version"] and identity["version_name"] == spec["version_name"] and
            identity["raw_image_sha256"] == value["target"]["sha256"] and identity["image_len"] == len(target),
            "N04 target header differs")
    require(value["target_bindings"] == target_bindings(c, value["target"], identity, artifacts),
            "N04 target binding derivation changed")
    api = c.load("p34_n04_package_checks", c.ROOT / "Tools/ota/prepare_baud_assets.py")
    api.package_info(Path(value["package"]["path"]).read_bytes(), spec["receiver"], spec["target_version"])
    require(all(value["decoded"][key] is True for key in
        ("passed", "byte_identical", "boot_ok", "guards_ok", "workspace_lifecycle_ok")) and
        value["decoded"]["image_bytes"] == len(target) and Path(value["decoded_image"]["path"]).read_bytes() == target,
        "N04 native/Python decode proof differs")
    require(len(value["negatives"]) == 4 and all(item["result"]["passed"] is True and item["result"]["prepares"] == 0
            for item in value["negatives"]), "N04 invalid package gates missing")
    require(value["package"] != c.previous_assets["package"], "N04 cannot replay its predecessor")
    if spec["predecessor_group"] in ("n04-bootstrap", "n04-measure", "n04-diagnostic8", "speed-window16"):
        executable(c, Path(source["path"]).read_bytes(), target)
        require(c.bindings["profile"]["map"] == artifacts[".map"], "measurement receiver is not the N04 App")
    else:
        require(c.bindings["profile"]["map"] != artifacts[".map"], "bootstrap must originate on measured W")
    return value


def prepare(c, spec):
    source = receiver(c, spec)
    require(not os.environ.get("OTA_AES_KEY"), "external package-key override rejected")
    out = c.checked(c.ROOT / spec["assets"]).parent
    if (out / "result.json").exists():
        load(c, spec)
        return dict(result=RESULT, manifest=c.record(out / "result.json"), reused=True, device_operations=0)
    require(not out.exists(), "partial N04 assets exist; preserve their nonce and failed evidence")
    report, artifacts = build_inputs(c)
    api = c.load("p34_n04_pack_tools", c.ROOT / "Tools/ota/prepare_baud_assets.py")
    api.FW = c.ROOT / FW
    decoder = c.n03["decoder"]
    inputs = [source, decoder, *artifacts.values(), c.bindings["profile"]["map"], c.bindings["profile"]["elf"],
              c.bindings["whole_boot"], report["source_manifest"], c.record(c.ROOT / BUILD),
              c.record(c.ROOT / spec["parent_assets"]), c.record(c.ROOT / BINDING_HELPER),
              c.record(c.ROOT / "Tools/ota/prepare_baud_assets.py"), c.record(c.ROOT / "Tools/ota/p34_full_assets.py")]
    inputs += [c.record(path) for path in sorted((api.FW / "Tools").glob("*.py"))]
    for item in inputs:
        require(c.record(c.checked(item["path"])) == item, "N04 input changed")
    image = out / ("images/%d-n04.bin" % spec["target_version"])
    package, decoded = out / "packages/full.etu", out / "images/decoded.bin"
    steps = ("finalize", "pack", "unpack", "decode", "payload-crc", "truncated", "same-version", "wrong-flags")
    paths = [image, package, decoded, out / "inputs.json", out / "result.json", out / "failed.json",
             out / "sources/p34_install_assets.py"]
    paths += [out / "logs" / (step + suffix) for step in steps for suffix in (".stdout", ".stderr", ".json")]
    paths += [out / "negative" / (name + ".etu") for name in steps[4:]]
    for path in paths:
        c.checked(path)
    c.OUT = c.host.OUT = out
    env = c.environment()
    for path in paths:
        c.checked(path.parent).mkdir(parents=True, exist_ok=True)
    generator = c.record(Path(__file__))
    frozen = c.raw(out / "sources/p34_install_assets.py", Path(__file__).read_bytes())
    require((frozen["bytes"], frozen["sha256"]) == (generator["bytes"], generator["sha256"]), "N04 generator changed")
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
        print("N04_ASSET_STEP", spec["target_version"], step, "exit", result.returncode, flush=True)
        require(result.returncode == 0, "N04 package step failed: " + step)
        return result.stdout

    try:
        run("finalize", api.python_tool("etu_pack.py", ["finalize", "--app", artifacts[".bin"]["path"], "--out", image,
            "--ver-name", spec["version_name"], "--build-ts", "1786320000"]))
        target = image.read_bytes()
        executable(c, Path(artifacts[".bin"]["path"]).read_bytes(), target)
        identity = api.legacy.firmware(target)
        require(identity["version_code"] == spec["target_version"] and identity["version_name"] == spec["version_name"],
                "N04 finalized version differs")
        run("pack", api.python_tool("etu_pack.py", ["pack-full", "--app", image, "--out", package,
            "--target-vcode", str(spec["target_version"])]))
        data = package.read_bytes()
        header = api.package_info(data, spec["receiver"], spec["target_version"])
        run("unpack", api.python_tool("etu_unpack.py", [package, "--out", decoded, "--verify-fw-header"]))
        require(decoded.read_bytes() == target, "N04 Python decode differs")
        native = json.loads(run("decode", [decoder["path"], package, source["path"], image, "ok"]))
        require(all(native[key] is True for key in
            ("passed", "byte_identical", "boot_ok", "guards_ok", "workspace_lifecycle_ok")), "N04 native decode failed")
        negatives = []
        for name, mutation, expected in api.negatives(data, spec["receiver"]):
            item = c.raw(out / "negative" / (name + ".etu"), mutation)
            value = json.loads(run(name, [decoder["path"], item["path"], source["path"], image, expected]))
            require(value["passed"] is True and value["prepares"] == 0, "invalid N04 package reached preparation")
            negatives.append(dict(name=name, package=item, result=value))
        bindings = target_bindings(c, c.record(image), identity, artifacts)
        outputs = [c.record(image), c.record(package), c.record(decoded), *commands, *(item["package"] for item in negatives)]
        for item in inputs:
            require(c.record(c.checked(item["path"])) == item, "N04 preparation modified an input")
        c.save(out / "result.json", dict(result=RESULT, specification=spec, receiver=source, receiver_bindings=c.bindings,
            target=c.record(image), target_identity=identity, target_bindings=bindings, package=c.record(package), header=header,
            decoded=native, decoded_image=c.record(decoded), negatives=negatives, generator=generator, generator_snapshot=frozen,
            inputs=inputs, outputs=outputs, hardware=False, independent_acceptance=False,
            bootstrap=spec["predecessor_group"] not in ("n04-bootstrap", "n04-measure", "speed-window16"), no_boot_change=True))
        load(c, spec)
    except Exception as error:
        c.save(out / "failed.json", dict(error=type(error).__name__, detail=str(error), commands=commands,
            device_operations=0, preserve_partial_assets=True))
        raise
    return dict(result=RESULT, manifest=c.record(out / "result.json"), package=c.record(package),
                target=c.record(image), device_operations=0, reused=False)
