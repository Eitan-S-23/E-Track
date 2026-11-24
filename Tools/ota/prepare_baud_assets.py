"""Finalize one diagnostic body and verify the bootstrap/shared FULL packages.

Host preparation only. No phone, debugger, firmware flash or device reset.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import time
import zlib


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


b = load("baud_assets_common", Path(__file__).with_name("baud_sweep.py"))
legacy = load("baud_assets_identity", b.P3 / "Tools/ota/p3-4-device/prepare_diagnostic.py")
FW = b.OUT / "fw"
OUT = b.OUT / "assets"
RAW = b.OUT / "build/app-gcc/X-Track-App-GCC.bin"
C3 = b.ROOT / ".cache/p34-cycles/c3-002/cells/reuse-without/mcu/result.json"
BASE_SHA = "16b4442d4d88aed0195513808862b64459159b4b40afdf5b94b2ecc30e2929fe"
BOOT_SHA = "e6618f50b6fce014beb2b8fe5cd4317b904d609d05c07a86e510a4bd772f2b7c"
HARNESS = b.P3 / "tests/ota/p3_4_full_image_host.c"
COMPILER = Path(r"D:\install\mingw64\bin\gcc.exe")
SOURCES = ("Libraries/OTA/ota_package.c", "Libraries/OTA/ota_keys.c", "boot/src/boot_crc32.c",
           "boot/src/boot_sha256.c", "boot/src/boot_fw_header.c",
           "bsdiff_lzma_AES128-main/bspatch/lzma/LzmaDec.c",
           "bsdiff_lzma_AES128-main/bspatch/AES128_CTR/aes_core.c")
INCLUDES = ("Libraries", "boot/include", "bsdiff_lzma_AES128-main/bspatch/lzma",
            "bsdiff_lzma_AES128-main/bspatch/AES128_CTR")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def output(name):
    return b.checked(OUT / name)


def write_bytes(name, data):
    path = output(name)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    return path


def python_tool(tool, args):
    path = FW / "Tools" / tool
    code = ("import sys,runpy;from pathlib import Path;"
            "sys.path.insert(0,str(Path(sys.base_prefix)/'Lib/site-packages'));"
            "sys.argv=" + repr([str(path), *map(str, args)]) + ";"
            "runpy.run_path(" + repr(str(path)) + ",run_name='__main__')")
    return [sys.executable, "-I", "-S", "-B", "-X", "utf8", "-c", code]


def run(tag, args, expected=0):
    paths = [output("logs/" + tag + suffix) for suffix in (".stdout", ".stderr", ".json")]
    b.require(not any(path.exists() for path in paths), "preserve existing command evidence")
    env = b.environment()
    env.update({key: str(output("tmp")) for key in ("TEMP", "TMP", "TMPDIR")})
    started = time.monotonic()
    result = subprocess.run(list(map(str, args)), cwd=FW, env=env, stdin=subprocess.DEVNULL,
                            capture_output=True, timeout=120, creationflags=subprocess.CREATE_NO_WINDOW)
    for path, data in zip(paths, (result.stdout, result.stderr)):
        with path.open("xb") as stream:
            stream.write(data)
    b.io.write_json(b.ROOT, paths[2], dict(args=list(map(str, args)), cwd=str(FW), exit=result.returncode,
        expected_exit=expected, seconds=time.monotonic() - started, stdout=b.record(paths[0]), stderr=b.record(paths[1])))
    print("ASSET_STEP", tag, "exit", result.returncode, flush=True)
    b.require(result.returncode == expected, "asset command failed: " + tag)
    return result.stdout


def package_info(data, current, target):
    b.require(64 < len(data) <= 0x180000 and data[:4] == b"ETU1", "ETU identity/length")
    b.require(struct.unpack_from("<HHII", data, 4) == (64, 0xB, 1, 1), "FULL algorithm/key/flags")
    length, crc, actual_target, base = struct.unpack_from("<IIII", data, 32)
    b.require(length + 64 == len(data) and zlib.crc32(data[64:]) & 0xFFFFFFFF == crc,
              "FULL payload length/CRC")
    b.require(zlib.crc32(data[:60]) & 0xFFFFFFFF == struct.unpack_from("<I", data, 60)[0], "ETU header CRC")
    b.require(actual_target == target and target > current and base == 0 and data[52:60] == bytes(8),
              "FULL version eligibility")
    b.require(data[48:52] == b"\x01\x00\x01\x01", "FULL platform eligibility")
    return dict(total_len=len(data), full_sha256=sha(data), current_vcode=current, target_vcode=target,
                payload_len=length, base_vcode=base, flags=0xB, reference_1mib=len(data) == 1048576)


def negatives(data, current):
    broken = bytearray(data)
    broken[81] ^= 1
    values = [("payload-crc", bytes(broken), "payload_crc"), ("truncated", data[:-1], "package_length")]
    for name, offset, form, value, error in (("same-version", 40, "<I", current, "version"),
                                            ("wrong-flags", 6, "<H", 7, "flags")):
        broken = bytearray(data)
        struct.pack_into(form, broken, offset, value)
        struct.pack_into("<I", broken, 60, zlib.crc32(broken[:60]) & 0xFFFFFFFF)
        values.append((name, bytes(broken), error))
    return values


def main():
    b.require(Path.cwd().resolve() == b.ROOT and sys.flags.isolated and sys.flags.no_site and
              sys.dont_write_bytecode, "isolated explicit project execution required")
    b.require(not os.environ.get("OTA_AES_KEY"), "external AES key rejected; public development fixture only")
    b.require(not OUT.exists(), "preserve existing assets, package nonce and verification evidence")
    images = {code: output("images/%s.bin" % name) for code, name in
              ((30207, "3.2.7-p34b"), (30208, "3.2.8-p34s"), (30209, "3.2.9-p34s"))}
    for name in ("images", "packages", "negative", "logs", "tmp", "bin", "result.json", "inputs.json",
                 "manifest.json", "images/whole-boot.bin", "bin/full_image_host.exe"):
        output(name)
    for tag in ("bootstrap", "screen"):
        for name in ("packages/%s.etu" % tag, "images/%s-recovered.bin" % tag):
            output(name)
        for name, _, _ in negatives(bytes(100), 30207):
            output("negative/%s-%s.etu" % (tag, name))
        for step in ("pack", "unpack", "decode", "payload-crc", "truncated", "same-version", "wrong-flags", "wrong-expected"):
            for suffix in (".stdout", ".stderr", ".json"):
                output("logs/%s-%s%s" % (tag, step, suffix))
    for tag in ("finalize-30208", "finalize-30209", "decoder-build"):
        for suffix in (".stdout", ".stderr", ".json"):
            output("logs/" + tag + suffix)
    build = b.read("firmware-build-001.json")
    b.require(build["passed"] and build["errors"] == 0 and
              b.record(RAW) in build["artifacts"], "diagnostic build binding failed")
    b.require(all(b.record(item["path"]) == item for item in build["modified_sources"]), "built source drift")
    previous = json.loads(C3.read_text(encoding="utf-8"))
    b.require(previous["result"] == "TARGET_VERIFIED_RETAINED" and previous["reader_closed"] and
              previous["final_identity"]["version_code"] == 30207, "last completed device identity missing")
    old, boot = Path(previous["final_image"]["path"]), Path(previous["final_boot"]["path"])
    for path, key, expected, length in ((old, "final_image", BASE_SHA, 603764),
                                      (boot, "final_boot", BOOT_SHA, 65536)):
        item = b.record(path)
        b.require(item["sha256"] == previous[key]["sha256"] == expected and
                  item["bytes"] == previous[key]["size"] == length, "original device readback drift")
    source_paths = {Path(__file__), Path(b.__file__), Path(legacy.__file__), Path(legacy.control.__file__),
                    HARNESS, COMPILER, RAW, C3, old, boot, b.OUT / "firmware-build-001.json",
                    FW / "Tools/etu_pack.py", FW / "Tools/etu_unpack.py", *[FW / name for name in SOURCES]}
    source_paths.update(Path(item["path"]) for item in build["modified_sources"])
    source_paths.update(Path(item["path"]) for item in build["artifacts"])
    for directory in ("Libraries/OTA", *INCLUDES[1:]):
        source_paths.update((FW / directory).glob("*.h"))
    inputs = [b.record(path) for path in sorted(source_paths)]
    for name in ("images", "packages", "negative", "logs", "tmp", "bin"):
        output(name).mkdir(parents=True, exist_ok=True)
    b.io.write_json(b.ROOT, output("inputs.json"), dict(time=b.now(), files=inputs,
        boot_version_assumption=1, hardware_contacted=False))
    checks = []
    try:
        write_bytes("images/3.2.7-p34b.bin", old.read_bytes())
        write_bytes("images/whole-boot.bin", boot.read_bytes())
        base_info = legacy.firmware(images[30207].read_bytes())
        raw = RAW.read_bytes()
        for code, name in ((30208, "3.2.8-p34s"), (30209, "3.2.9-p34s")):
            run("finalize-" + str(code), python_tool("etu_pack.py", ["finalize", "--app", RAW,
                "--out", images[code], "--ver-name", name, "--build-ts", str(base_info["build_timestamp"])]))
            target = images[code].read_bytes()
            identity = legacy.firmware(target)
            b.require(identity["version_code"] == code and identity["version_name"] == name and
                      len(target) == len(raw) and target[:0x400] == raw[:0x400] and target[0x460:] == raw[0x460:],
                      "finalization modified executable bytes or unexpected identity")
            checks.append("finalized-and-body-bound-" + str(code))
        first, second = images[30208].read_bytes(), images[30209].read_bytes()
        b.require(first[:0x400] == second[:0x400] and first[0x460:] == second[0x460:], "screening bodies differ")
        executable = output("bin/full_image_host.exe")
        run("decoder-build", [COMPILER, "-std=c99", "-Wall", "-Wextra", "-Werror", "-O2",
            *["-I" + str(FW / name) for name in INCLUDES], HARNESS, *[FW / name for name in SOURCES], "-o", executable])
        b.require(not output("logs/decoder-build.stderr").read_bytes(), "host compiler diagnostics present")
        groups = {}
        for tag, current, target in (("bootstrap", 30207, 30208), ("screen", 30208, 30209)):
            package, recovered = output("packages/" + tag + ".etu"), output("images/" + tag + "-recovered.bin")
            run(tag + "-pack", python_tool("etu_pack.py", ["pack-full", "--app", images[target],
                "--out", package, "--target-vcode", str(target)]))
            data = package.read_bytes()
            info = package_info(data, current, target)
            run(tag + "-unpack", python_tool("etu_unpack.py", [package, "--out", recovered, "--verify-fw-header"]))
            b.require(recovered.read_bytes() == images[target].read_bytes(), "Python unpack differs from target")
            decoded = json.loads(run(tag + "-decode", [executable, package, images[current], images[target], "ok"]))
            b.require(all(decoded[key] is True for key in ("passed", "byte_identical", "boot_ok", "guards_ok",
                                                          "workspace_lifecycle_ok")), "real decoder/Boot validation failed")
            checks.extend([tag + "-header", tag + "-python-byte-identical", tag + "-firmware-decoder-boot"])
            for name, mutation, expected in negatives(data, current):
                path = write_bytes("negative/%s-%s.etu" % (tag, name), mutation)
                value = json.loads(run(tag + "-" + name, [executable, path, images[current], images[target], expected]))
                b.require(value["passed"] and value["prepares"] == 0, "negative did not reject before preparation")
                checks.append(tag + "-reject-" + name)
            wrong = json.loads(run(tag + "-wrong-expected", [executable, package, images[current], images[current], "ok"], expected=1))
            b.require(wrong["result"] == "ok" and not wrong["passed"] and not wrong["byte_identical"],
                      "expected-image comparison lacks discrimination")
            checks.append(tag + "-wrong-expected-discrimination")
            groups[tag] = dict(package=b.record(package), header=info, baseline=b.record(images[current]),
                baseline_identity=legacy.firmware(images[current].read_bytes()), target=b.record(images[target]),
                target_identity=legacy.firmware(images[target].read_bytes()), decoder=decoded)
        b.require(all(b.record(item["path"]) == item for item in inputs), "immutable source drift")
        b.require(not list(output("tmp").iterdir()), "unexpected retained compiler temporary files")
        result = dict(result="HOST_READY", time=b.now(), groups=groups, checks=checks, checks_count=len(checks),
            rates=[115200, 460800, 921600], same_screening_package=True, whole_boot=b.record(output("images/whole-boot.bin")),
            diagnostic_build=b.record(b.OUT / "firmware-build-001.json"), firmware_warnings=build["warnings"],
            host_compiler_warnings=0, hardware="NOT_RUN", independent_acceptance="NOT_RUN",
            key_source="repository public development fixture", nonce_policy="generated once per package; reuse exact bytes",
            starting_device_identity_must_be_rechecked=True, recovery_route="NOT_YET_ADMITTED")
        b.io.write_json(b.ROOT, output("result.json"), result)
        b.io.write_json(b.ROOT, output("manifest.json"), dict(metadata=result,
            files=[b.record(path) for path in sorted(OUT.rglob("*")) if path.is_file()], inputs=inputs))
        print("BAUD_ASSETS_HOST_READY", json.dumps({key: value["header"] for key, value in groups.items()}), flush=True)
    except Exception as error:
        if not output("result.json").exists():
            b.io.write_json(b.ROOT, output("result.json"), dict(result="HOST_FAIL", checks=checks,
                error=type(error).__name__, reason=str(error), hardware="NOT_RUN"))
        raise


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print("ASSET_PREPARATION_FAILED", type(error).__name__, str(error), flush=True)
        raise SystemExit(1)
