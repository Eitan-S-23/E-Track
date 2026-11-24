"""One source-bound Boot-only activation, with retained original recovery bytes."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import runpy
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_boot_device as d

OUT = ROOT / ".cache/p34-boot/activation"
PREP = ROOT / ".cache/p34-boot/preparation/result.json"
ORIGINAL = ROOT / ".cache/p34-boot/preparation/original-whole-boot.bin"
CANDIDATE = OUT / "candidate-whole-boot.bin"
APP = ROOT / ".cache/p34-boot/device-r2/app.bin"


def env(out):
    g = runpy.run_path(str(ROOT / ".cache/project-governance-20260922/run.py"))
    g["environment"].__globals__["OUT"] = out
    return g["environment"]()


def raw(path, data):
    path = d.checked(path)
    d.checked(path.parent).mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    return d.record(path)


def flash_commands(image):
    image = d.checked(image)
    d.require(image in (CANDIDATE, ORIGINAL) and image.stat().st_size == 65536,
              "only an exact whole Boot image can be programmed")
    d.require(d.record(APP)["sha256"] == d.APP_SHA, "retained App input changed")
    return ["exec DisableAutoUpdateFW", "h", "loadbin " + d.quote(image) + ", 0x08000000",
            "verifybin " + d.quote(image) + ", 0x08000000",
            "verifybin " + d.quote(APP) + ", 0x08010000", "r", "g", "qc"]


def source_records():
    old = json.loads((ROOT / ".cache/p34q/irqscreen/triage/boot-fix/run-002/result.json").read_bytes())
    paths = {Path(x["path"]) for x in old["sources"]}
    paths.update((Path(__file__), Path(d.__file__), ROOT / "tests/boot/test_boot_state_machine.c",
                  ROOT / "Tools/ota/p34_boot_candidate.py", ROOT / "Tools/ota/baud_uncached.py"))
    return [d.record(p) for p in sorted(paths)]


def prepare():
    d.require(not OUT.exists(), "preserve prior activation")
    build = json.loads(PREP.read_bytes())
    d.require(build["passed"] and build["default_byte_identical"] and
              all(x["warnings"] == x["errors"] == x["exit"] == 0 for x in build["actions"]),
              "clean verified build required")
    for item in build["sources"] + build["default"] + build["candidate"] + [build["backup"]]:
        d.require(d.record(item["path"]) == item, "build input/artifact drift")
    old = ORIGINAL.read_bytes()
    binary = Path(build["candidate"][0]["path"]).read_bytes()
    d.require(len(old) == 65536 and hashlib.sha256(old).hexdigest() == d.BOOT_SHA and
              0x400 < len(binary) < 65536, "Boot image bounds")
    raw(CANDIDATE, binary + old[len(binary):])
    checks = 0
    for image in (CANDIDATE, ORIGINAL):
        commands = flash_commands(image)
        d.require(len(commands) == 8 and commands[2].endswith(", 0x08000000") and
                  sum(x.startswith("loadbin ") for x in commands) == 1 and
                  commands[-3:] == ["r", "g", "qc"], "flash scope differs")
        raw(OUT / ("apply.jlink" if image == CANDIDATE else "restore.jlink"),
            ("\n".join(commands) + "\n").encode("ascii"))
        checks += 1
    try:
        flash_commands(APP)
    except RuntimeError:
        checks += 1
    else:
        raise RuntimeError("App programming was accepted")
    tests = json.loads((d.AREA / "device-tests-r3/result.json").read_bytes())
    d.require(tests["passed"] and tests["source"] == d.record(Path(d.__file__)), "snapshot tests stale")
    d.save(OUT / "plan.json", dict(source=d.record(Path(__file__)), sources=source_records(), build=d.record(PREP),
        candidate=d.record(CANDIDATE), original=d.record(ORIGINAL), app=d.record(APP), checks=checks,
        apply=d.record(OUT / "apply.jlink"), restore=d.record(OUT / "restore.jlink"),
        authority="Current user explicitly authorized this F435 Boot optimization and flash after recovery preflight",
        operations="fresh uncached read; one whole-Boot load/verify and unchanged-App verify; reset; fresh full read",
        recovery="exact original whole Boot available; no App downgrade or arbitrary BCB write",
        no_ota=True, independent_acceptance=False))
    print("BOOT_ACTIVATION_PREPARED", d.record(CANDIDATE)["sha256"], flush=True)


def commander(out, commands):
    environment = env(out)
    for name in ("command.jlink", "settings.jlink", "sdk.log", "console.log"):
        d.checked(out / name)
    script = out / "command.jlink"
    raw(script, ("\n".join(commands) + "\n").encode("ascii"))
    presence = runpy.run_path(str(ROOT / "Tools/ota/baud_uncached.py"))["native_presence"]()
    args = [str(d.JLINK), "-Device", "AT32F435RGT7", "-If", "SWD", "-Speed", "1000", "-USB", "123456",
        "-AutoConnect", "1", "-ExitOnError", "1", "-NoGui", "1", "-SettingsFile", str(out / "settings.jlink"),
        "-Log", str(out / "sdk.log"), "-CommandFile", str(script)]
    p = subprocess.run(args, cwd=ROOT, env=environment, capture_output=True, timeout=180,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    data = p.stdout + p.stderr
    raw(out / "console.log", data)
    d.save(out / "command-result.json", dict(exit=p.returncode, command=args, presence=presence))
    d.require(p.returncode == 0 and b"Not all bytes" not in data, "Commander failure; inspect original result")
    return data


def snapshot(out, value, boot_sha):
    commander(out, d.commands(out, value))
    data = {k: (out / (k + ".bin")).read_bytes() for k in d.read_regions(value)}
    d.validate_snapshot(data, value, boot_sha=boot_sha)
    result = dict(result="FULL_BOOT_APP_HEALTH_VERIFIED", files=[d.record(out / (k + ".bin")) for k in data])
    d.save(out / "result.json", result)
    return result


def apply():
    plan = json.loads((OUT / "plan.json").read_bytes())
    d.require(not (OUT / "started.json").exists(), "activation already attempted; reconcile, never replay")
    for item in plan["sources"] + [plan[k] for k in ("build", "candidate", "original", "app", "apply", "restore")]:
        d.require(d.record(item["path"]) == item, "activation input drift")
    value = d.bindings()
    before = snapshot(OUT / "before", value, d.BOOT_SHA)
    d.save(OUT / "started.json", dict(time=time.time(), plan=d.record(OUT / "plan.json"),
        before=before, native_before=d.record(d.MRU), scope="0x08000000..0x0800ffff only"))
    result = dict(result="BOOT_ACTIVATION_UNRECONCILED", flash_started=False, no_ota=True)
    try:
        result["flash_started"] = True
        text = commander(OUT / "flash", flash_commands(CANDIDATE))
        d.require(text.count(b"Verify successful.") == 2, "whole Boot/App verification uncertain")
        result["flash_verified"] = True
        time.sleep(10)
        result["after"] = snapshot(OUT / "after", value, plan["candidate"]["sha256"])
        result["result"] = "CANDIDATE_BOOT_ACTIVE_30235_CONFIRMED"
    except Exception as error:
        result["error"] = type(error).__name__ + ": " + str(error)
    result["native_after"] = d.record(d.MRU)
    d.save(OUT / "result.json", result)
    print(json.dumps(result))
    return 0 if result["result"] == "CANDIDATE_BOOT_ACTIVE_30235_CONFIRMED" else 1


if __name__ == "__main__":
    d.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
              "isolated explicit root required")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("prepare", "apply"))
    args = parser.parse_args()
    raise SystemExit(prepare() if args.mode == "prepare" else apply())
