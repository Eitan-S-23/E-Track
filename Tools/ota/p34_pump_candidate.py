"""Isolated active-pump cadence candidate; reuse the proven build/test primitives."""
import argparse
import json
from pathlib import Path
import re
import shutil
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_staging_erase_candidate as previous
import p34_batch_review as review

cli, host = previous.cli, previous.host
BASE, AREA = previous.AREA, ROOT / ".cache/p34-pump-cadence"
HEADER = ROOT / "Tools/ota/p34_pump_cadence.h"
TEST = ROOT / "tests/ota/test_p34_pump_cadence.cpp"
HAL, COPIED_HEADER = "USER/HAL/HAL.cpp", "USER/HAL/ota_pump_cadence.h"


def prepare(s):
    fw = s.checked(AREA / "f")
    cli.require(not fw.exists(), "preserve candidate source")
    proof, report = review.load_report(s, BASE / "trials/measure")
    cli.require(report["summary"]["input"]["targetVersionCode"] == 30261, "confirmed30261 required")
    manifest = s.read(BASE / "build/source.json")
    copies = []
    for item in manifest["files"]:
        src = s.checked(item["path"])
        cli.require(cli.record(src) == item, "built base source changed")
        copies.append((src, s.checked(fw / src.relative_to(BASE / "f"))))
    target = s.checked(fw / COPIED_HEADER)
    for src, dst in copies:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
    shutil.copyfile(HEADER, target)
    s.write(AREA / "prepared.json", dict(base=cli.record(BASE / "build/source.json"), predecessor=proof,
        header=cli.record(HEADER), copied_header=cli.record(target), hardware=False))
    print("PUMP_SOURCE_PREPARED", len(copies))


def sources(s):
    prepared = s.read(AREA / "prepared.json")
    cli.require(prepared["base"] == cli.record(BASE / "build/source.json") and
                prepared["header"] == cli.record(HEADER) and
                (AREA / "f" / COPIED_HEADER).read_bytes() == HEADER.read_bytes(), "prepared input changed")
    for item in s.read(BASE / "build/source.json")["files"]:
        src = Path(item["path"])
        relative = src.relative_to(BASE / "f")
        cli.require(cli.record(src) == item, "base source changed")
        if relative.as_posix() != HAL:
            cli.require((AREA / "f" / relative).read_bytes() == src.read_bytes(), "unrelated candidate change")
    before = (BASE / "f" / HAL).read_text(encoding="utf-8")
    expected = before.replace('#include "MillisTaskManager/MillisTaskManager.h"',
        '#include "MillisTaskManager/MillisTaskManager.h"\n#include "HAL/ota_pump_cadence.h"', 1)
    expected = expected.replace('    taskManager.Running(millis());',
        '#if CONFIG_OTA_ACTIVE_PUMP\n'
        '    taskManager.SetIntervalTime(BT_OtaPump,\n'
        '        ota_pump_period(OTA_OverlayIsBleOwned(), CONFIG_OTA_BLE_PUMP_PERIOD_MS));\n'
        '#endif\n    taskManager.Running(millis());', 1)
    cli.require((AREA / "f" / HAL).read_text(encoding="utf-8") == expected, "unexpected scheduler wiring")
    paths = [Path(__file__), HEADER, TEST, AREA / "f" / HAL, AREA / "f" / COPIED_HEADER]
    paths += [AREA / "f/Libraries/MillisTaskManager" / ("MillisTaskManager." + x) for x in ("h", "cpp")]
    return [cli.record(p) for p in paths]


def tests(s, attempt):
    out = s.checked(AREA / "tests" / attempt)
    cli.require(not out.exists(), "preserve host tests")
    bound = sources(s)
    env = host.environment(s, out)
    variants = {}
    for enabled in (0, 1):
        name = "active" + str(enabled)
        exe = s.checked(out / (name + ".exe"))
        args = ["D:/install/mingw64/bin/g++.exe", "-std=c++11", "-O2", "-Wall", "-Wextra", "-Werror",
            "-DCONFIG_OTA_ACTIVE_PUMP=" + str(enabled), "-I" + str(AREA / "f/USER"),
            "-I" + str(AREA / "f/Libraries/MillisTaskManager"), TEST,
            AREA / "f/Libraries/MillisTaskManager/MillisTaskManager.cpp", "-o", exe]
        compiled = host.command(s, out, name + "-compile", args, env, 120)
        cli.require(not re.search(rb"\bwarning:", compiled), "native compiler warning")
        data = host.command(s, out, name, [exe], env, 120)
        cli.require(b"PUMP_CADENCE=PASS" in data, "scheduler test failed")
        variants[name] = data.decode().strip()
    cli.require(sources(s) == bound, "tested sources changed")
    s.write(out / "result.json", dict(result="PUMP_HOST_PASS", sources=bound, variants=variants,
        hardware=False, warnings=0, errors=0))
    s.write(AREA / "tests/latest.json", dict(report=cli.record(out / "result.json")),
            replace=(AREA / "tests/latest.json").exists())
    print("PUMP_HOST_PASS", variants)


def build(s):
    ref = s.read(AREA / "tests/latest.json")["report"]
    cli.require(cli.record(ref["path"]) == ref, "tests changed")
    tested = s.read(ref["path"])
    cli.require(tested["result"] == "PUMP_HOST_PASS" and tested["sources"] == sources(s), "current tests required")
    fw, bld, out = (s.checked(AREA / x) for x in ("f", "b", "build"))
    cli.require(not bld.exists() and not out.exists(), "preserve build")
    s.checked(AREA / "install")
    args = [str(x).replace(str(BASE), str(AREA)) for x in s.read(BASE / "build/configure.json")["command"]]
    args = [x + " -DCONFIG_OTA_ACTIVE_PUMP=1" if x.startswith("-DCMAKE_CXX_FLAGS:STRING=") else x for x in args]
    cli.require(sum("CONFIG_OTA_ACTIVE_PUMP=1" in x for x in args) == 1, "candidate flag missing")
    s.write(out / "source.json", dict(base=cli.record(BASE / "build/source.json"), overlays=[HAL, COPIED_HEADER],
        files=[cli.record(p) for p in sorted(fw.rglob("*")) if p.is_file()]))
    env = host.environment(s, out)
    host.command(s, out, "configure", args, env, 180)
    raw = host.command(s, out, "build", [args[0], "--build", bld, "--target", "X_Track_App_GCC", "--parallel", "6"], env, 900)
    def normalized(data):
        return previous.review.warnings(data.replace(b"p34-pump-cadence", b"p34-staging-erase"))
    old, new = normalized((BASE / "build/build.log").read_bytes()), normalized(raw)
    value = dict(result="PUMP_APP_BUILT", artifacts=[cli.record(bld / "app-gcc" / ("X-Track-App-GCC" + ext))
        for ext in (".bin", ".elf", ".map", ".hex")], warnings=sum(new.values()), new_warnings=dict(new-old),
        errors=raw.count(b"error:"), boot_built=False, hardware=False,
        source=cli.record(out / "source.json"), tests=ref)
    s.write(out / "result.json", value)
    cli.require(not value["new_warnings"] and not value["errors"], "new build diagnostics need review")
    print(json.dumps(value))


if __name__ == "__main__":
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                "isolated explicit root required")
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("mode", choices=("prepare", "test", "launch", "worker"))
    p.add_argument("--attempt", default="r1")
    a = p.parse_args()
    cli.require(re.fullmatch(r"r[1-9][0-9]*", a.attempt), "invalid output label")
    s = cli.Store(ROOT)
    if a.mode == "prepare": prepare(s)
    elif a.mode == "test": tests(s, a.attempt)
    else:
        owner = cli.load_module("pump_build_owner", ROOT / ".cache/p3-4-screening-20260922/supervisor.py")
        if a.mode == "launch":
            print(owner.owned.launch(s.checked(AREA / "runtime/build-001"), Path(__file__), ["worker"], 1500))
        else:
            cli.require(owner.owned.in_job(), "finite build owner required")
            build(s)
