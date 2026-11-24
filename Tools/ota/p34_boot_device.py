"""Read-only Boot replacement preflight, using a bounded uncached Commander."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import runpy
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
AREA = ROOT / ".cache/p34-boot"
IO = runpy.run_path(str(ROOT / ".agents/skills/e-track-flutter-debug/scripts/host_io.py"))
JLINK = Path(r"C:\Users\SU\SEGGER\JLink_V818\JLink.exe")
MRU = Path(r"C:\Users\SU\AppData\Roaming\SEGGER\JLinkDLL.ini")
APP_SHA = "20712c2f50a85177a1de80b29c9080753bb3b0545778bf389e258c50074608b1"
BOOT_SHA = "55200bb8b9399b5b2fa3e9b9d02d0504bec066f7624d0f293d82cb4244505f62"


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def checked(path):
    return IO["checked_output"](ROOT, path)


def record(path):
    data = Path(path).read_bytes()
    return dict(path=str(path), bytes=len(data), sha256=hashlib.sha256(data).hexdigest())


def save(path, value):
    return IO["write_json"](ROOT, path, value)


def bindings():
    manifest = ROOT / ".cache/p34ab/assets/session-assets.json"
    require(record(manifest)["sha256"] == "aba6bef3505ac1dad257c2eea0c11a3e9f1ec0d739cbcd497f84cd49381f497c",
            "installed App manifest changed")
    value = json.loads(manifest.read_bytes())["images"]["aa"]["bindings"]
    for item in (value["profile"]["image"], value["profile"]["map"], value["whole_boot"]):
        require(record(item["path"]) == item, "bound image/map/Boot changed")
    require(value["profile"]["image"]["sha256"] == APP_SHA and value["whole_boot"]["sha256"] == BOOT_SHA,
            "unexpected baseline")
    return value


def quote(path):
    path = checked(path)
    require(not any(c in str(path) for c in '\r\n\"\0,'), "unsafe Commander path")
    return '"' + str(path) + '"'


def read_regions(value):
    s, layout = value["profile"]["symbols"], value["layout"]
    return dict(boot=(0x08000000, 65536), app=(0x08010000, value["profile"]["image"]["bytes"]),
        tick_before=(s["tick"], 4), tick_after=(s["tick"], 4), vtor=(0xE000ED08, 4),
        core=(s["core_clock"], 4), session=(layout["session"], 576),
        bcb=(layout["bcb_state"], 1), confirm=(layout["confirm_done"], 1),
        snapped=(layout["state_snapped"], 1), sd=(s["sd_ready"], 1),
        retained=(0x4000289c, 4), dhcsr=(0xE000EDF0, 4))


def commands(out, value):
    regions = read_regions(value)
    order = ["tick_before", "boot", "app", "vtor", "core", "session", "bcb", "confirm", "snapped", "sd", "retained", "dhcsr", "tick_after"]
    result = ["exec DisableAutoUpdateFW", "exec SetEnableMemCache = 0", "exec InvalidateCache",
              "exec ExcludeFlashCacheRange 0x08000000-0x080FFFFF"]
    for name in order:
        address, length = regions[name]
        require(0 < length <= 655360, "unbounded read")
        result.append("savebin " + quote(out / (name + ".bin")) + ", 0x%08X, 0x%X" % (address, length))
    result.append("qc")
    require(not any(x.startswith(("h", "r", "g", "load", "w")) for x in result), "probe must not mutate target")
    return result


def validate_snapshot(raw, value, *, boot_sha=BOOT_SHA):
    regions = read_regions(value)
    require(set(raw) == set(regions) and all(len(raw[k]) == regions[k][1] for k in regions), "short snapshot")
    require(hashlib.sha256(raw["app"]).hexdigest() == APP_SHA and
            hashlib.sha256(raw["boot"]).hexdigest() == boot_sha, "live full image mismatch")
    word = lambda k: struct.unpack("<I", raw[k])[0]
    require(word("vtor") == 0x08010000 and word("core") == 288000000 and
            not word("dhcsr") & (1 << 17), "App is not running at the bound clock")
    require(0 < (word("tick_after") - word("tick_before")) & 0xffffffff < 120000,
            "App clock did not advance")
    require(raw["bcb"] == b"\x04" and raw["confirm"] == raw["snapped"] == raw["sd"] == b"\x01" and
            word("retained") == 0x5034f708, "unconfirmed/not-ready baseline")
    fields = value["layout"]["members"]["members"]
    for name in ("state", "session_id", "receiver", "isr_active"):
        field = fields[name]
        require(int.from_bytes(raw["session"][field["offset"]:field["offset"] + field["size"]], "little") == 0,
                "active or unreconciled OTA session")


def test():
    value = bindings()
    names = commands(AREA / "device", value)
    require(len(names) == 18 and names[-1] == "qc", "unexpected read command count")
    parsed = {Path(line.split('"')[1]).stem: int(line.rsplit(",", 1)[1].strip(), 16)
              for line in names if line.startswith("savebin ")}
    require(parsed == {k: v[1] for k, v in read_regions(value).items()}, "Commander hexadecimal length mismatch")
    for suffix in ('bad".bin', 'bad,.bin', 'bad\n.bin'):
        try:
            quote(AREA / suffix)
        except (RuntimeError, ValueError, OSError):
            pass
        else:
            raise RuntimeError("unsafe path accepted")
    regions = read_regions(value)
    raw = {k: bytes(length) for k, (_, length) in regions.items()}
    raw.update(app=Path(value["profile"]["image"]["path"]).read_bytes(),
        boot=Path(value["whole_boot"]["path"]).read_bytes(),
        vtor=struct.pack("<I", 0x08010000), core=struct.pack("<I", 288000000),
        tick_after=struct.pack("<I", 1000), bcb=b"\x04", confirm=b"\x01", snapped=b"\x01",
        sd=b"\x01", retained=struct.pack("<I", 0x5034f708))
    validate_snapshot(raw, value)
    for field in ("app", "boot", "bcb", "confirm", "sd", "vtor", "core", "retained", "tick_after"):
        bad = dict(raw)
        bad[field] = bytes(len(raw[field]))
        try:
            validate_snapshot(bad, value)
        except RuntimeError:
            pass
        else:
            raise RuntimeError("invalid snapshot accepted: " + field)
    save(AREA / "device-tests-r3/result.json", dict(passed=True, checks=15, source=record(Path(__file__)), hardware=False))
    print("BOOT_DEVICE_HOST_CHECKS=PASS")


def probe():
    out = checked(AREA / "device-r2")
    require(not out.exists(), "preserve prior probe")
    tests = json.loads((AREA / "device-tests-r3/result.json").read_bytes())
    require(tests["passed"] and tests["source"] == record(Path(__file__)), "current host checks required")
    value = bindings()
    build = json.loads((AREA / "preparation/result.json").read_bytes())
    require(build["passed"] and build["default_byte_identical"], "candidate build not verified")
    for item in build["sources"] + build["default"] + build["candidate"] + [build["backup"]]:
        require(record(item["path"]) == item, "build/source drift")
    for area in (".cache/p34-rolling/session-w31", ".cache/p34-rolling28/session-w28"):
        closed = json.loads((ROOT / area / "owner/closed.json").read_bytes())
        require(not closed["forced_termination"] and closed["worker_exit"] in (0, 1), "prior owner unresolved")
    g = runpy.run_path(str(ROOT / ".cache/project-governance-20260922/run.py"))
    g["environment"].__globals__["OUT"] = out
    env = g["environment"]()
    for name in ("probe.jlink", "settings.jlink", "sdk.log", "console.log", "result.json"):
        checked(out / name)
    lines = commands(out, value)
    command = checked(out / "probe.jlink")
    with command.open("x", encoding="ascii") as stream:
        stream.write("\n".join(lines) + "\n")
    native = runpy.run_path(str(ROOT / "Tools/ota/baud_uncached.py"))
    result = dict(result="PREFLIGHT_FAILED", flash=0, reset=0, halt=0, native_before=record(MRU))
    try:
        result["presence"] = native["native_presence"]()
        args = [str(JLINK), "-Device", "AT32F435RGT7", "-If", "SWD", "-Speed", "1000",
            "-USB", "123456", "-AutoConnect", "1", "-ExitOnError", "1", "-NoGui", "1",
            "-SettingsFile", str(out / "settings.jlink"), "-Log", str(out / "sdk.log"), "-CommandFile", str(command)]
        p = subprocess.run(args, cwd=ROOT, env=env, capture_output=True, timeout=180,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        with (out / "console.log").open("xb") as stream:
            stream.write(p.stdout + p.stderr)
        result["exit"] = p.returncode
        require(p.returncode == 0, "Commander failed; preserve outcome")
        require(b"Not all bytes" not in p.stdout + p.stderr, "Commander returned a partial read")
        raw = {k: (out / (k + ".bin")).read_bytes() for k in read_regions(value)}
        validate_snapshot(raw, value)
        result.update(result="BOOT_REPLACEMENT_PREFLIGHT_VERIFIED",
                      files=[record(out / (k + ".bin")) for k in raw])
    except Exception as error:
        result["error"] = type(error).__name__ + ": " + str(error)
    result["native_after"] = record(MRU)
    save(out / "result.json", result)
    print(json.dumps(result))
    return 0 if result["result"] == "BOOT_REPLACEMENT_PREFLIGHT_VERIFIED" else 1


if __name__ == "__main__":
    require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
            "isolated explicit root required")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("test", "probe"))
    args = parser.parse_args()
    raise SystemExit(test() if args.mode == "test" else probe())
