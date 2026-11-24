"""Contained install-cost model tests, strict log parsing and App-only build."""
import argparse
import copy
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_session as cli

AREA = ROOT / ".cache/p34-cost"
KINDS = ("package_read", "base_read", "candidate_read", "slot_read", "erase", "program", "restore")


def parse_one(text):
    lines = [line for line in text.splitlines() if line.startswith("P34COST")]
    cli.require(len(lines) == 8, "one header and seven cost rows required")
    h = re.fullmatch(r"P34COST: phase=(full|patch|backup) rc=(-?\d+) clock=millis total=(\d+) rest=(\d+) valid=1", lines[0])
    cli.require(h is not None, "invalid cost header/clock")
    phase, rc, total, rest = h[1], int(h[2]), int(h[3]), int(h[4])
    cli.require(-(1 << 31) <= rc < (1 << 31) and 0 <= rest <= total <= 0xffffffff, "cost header range")
    rows = {}
    for line in lines[1:]:
        m = re.fullmatch(r"P34COST_IO: phase=(full|patch|backup) kind=(\d+) calls=(\d+) fail=(\d+) bytes=(\d+):(\d+) ticks=(\d+):(\d+)", line)
        cli.require(m is not None and m[1] == phase, "invalid/mixed cost row")
        kind, calls, failed, bh, bl, th, tl = map(int, m.groups()[1:])
        cli.require(kind < len(KINDS) and kind not in rows and all(0 <= v <= 0xffffffff for v in
                    (calls, failed, bh, bl, th, tl)) and failed <= calls, "cost row range/count")
        byte_count, ticks = (bh << 32) | bl, (th << 32) | tl
        cli.require(calls or byte_count == ticks == 0, "uncalled port has costs")
        cli.require(rc != 0 or failed == 0, "failed port hidden by successful phase")
        rows[kind] = dict(calls=calls, failures=failed, bytes=byte_count, ticks_ms=ticks)
    cli.require(sum(v["ticks_ms"] for v in rows.values()) + rest == total, "cost partition does not close")
    return dict(phase=phase, result_code=rc, success=rc == 0, total_ticks_ms=total,
        residual_ticks_ms=rest, ports={KINDS[k]: rows[k] for k in range(7)},
        clock="MCU millis; not calibrated wall time", residual_is_decode_only=False)


def environment(store, out):
    env = dict(os.environ)
    for key in ("HOME", "USERPROFILE", "APPDATA", "LOCALAPPDATA", "TEMP", "TMP", "TMPDIR",
                "XDG_CACHE_HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "PYTHONUSERBASE",
                "PYTHONPYCACHEPREFIX", "CCACHE_DIR", "SCCACHE_DIR"):
        path = store.checked(out / "host" / key.lower())
        path.mkdir(parents=True, exist_ok=True)
        env[key] = str(path)
    env.update(PYTHONDONTWRITEBYTECODE="1", SOURCE_DATE_EPOCH="1786320000", CCACHE_DISABLE="1",
               SCCACHE_DISABLE="1", GIT_OPTIONAL_LOCKS="0")
    return env


def command(store, out, tag, args, env, timeout):
    log = store.checked(out / (tag + ".log"))
    receipt = store.checked(out / (tag + ".json"))
    cli.require(not log.exists() and not receipt.exists(), "preserve command evidence")
    try:
        p = subprocess.run(list(map(str, args)), cwd=ROOT, env=env, capture_output=True,
                           timeout=timeout, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        data, code = p.stdout + p.stderr, p.returncode
    except subprocess.TimeoutExpired as e:
        data, code = (e.stdout or b"") + (e.stderr or b""), None
    record = store.raw(log, data)
    store.write(receipt, dict(command=list(map(str, args)), cwd=str(ROOT), exit=code, log=record))
    cli.require(code == 0, "host command failed: " + tag)
    return data


def test(store):
    out = store.checked(AREA / "tests")
    cli.require(not out.exists(), "preserve tests")
    env = environment(store, out)
    exe = store.checked(out / "cost.exe")
    args = ["D:/install/mingw64/bin/g++.exe", "-std=c++11", "-O2", "-Wall", "-Wextra", "-Werror",
            "-I" + str(ROOT / "USER"), ROOT / "tests/ota/test_ota_install_cost.cpp", "-o", exe]
    command(store, out, "compile", args, env, 60)
    output = command(store, out, "native", [exe], env, 60)
    cli.require(b"INSTALL_COST_PASS checks=14" in output, "native cost checks missing")
    good = "P34COST: phase=full rc=0 clock=millis total=10 rest=3 valid=1\n" + "\n".join(
        f"P34COST_IO: phase=full kind={i} calls=1 fail=0 bytes=0:256 ticks=0:1" for i in range(7))
    cli.require(parse_one(good)["residual_ticks_ms"] == 3, "parser positive failed")
    cases = [good.replace("valid=1", "valid=0"), good.replace("rest=3", "rest=4"),
        good.replace("kind=6", "kind=0"), good.replace("kind=6", "kind=7"),
        good.replace("calls=1", "calls=0", 1), good.replace("fail=0", "fail=2", 1),
        good.replace("P34COST_IO: phase=full", "P34COST_IO: phase=backup", 1),
        good.replace("bytes=0:256", "bytes=0:4294967296", 1),
        good.rsplit("\n", 1)[0], good + "\nP34COST: broken"]
    for data in cases:
        try:
            parse_one(data)
        except RuntimeError:
            continue
        raise RuntimeError("invalid cost log accepted")
    cli.require(parse_one(good.replace("rc=0", "rc=-1").replace("fail=0", "fail=1", 1))["success"] is False,
                "failed phase became success")
    paths = [Path(__file__), ROOT / "USER/HAL/HAL_OTA_Package.cpp", ROOT / "USER/HAL/ota_install_cost.h",
             ROOT / "tests/ota/test_ota_install_cost.cpp", ROOT / "tests/ota/test_qspi_install_restore.py"]
    hal = store.read(AREA / "hal-tests/result.json")
    cli.require(hal["result"] == "HOST_MODEL_PASS" and hal["tests"] == 12 and hal["inputs_unchanged"], "HAL checks missing")
    for item in hal["inputs"]:
        cli.require(cli.record(item["path"]) == item, "HAL test source changed")
    store.write(out / "result.json", dict(result="COST_HOST_PASS", native_checks=14, parser_checks=12,
        hal_tests=12, inputs=[cli.record(p) for p in paths], hal=cli.record(AREA / "hal-tests/result.json"), hardware=False))
    print("COST_HOST_PASS native14 parser12 HAL12")


def build(store):
    result = store.read(AREA / "tests/result.json")
    cli.require(result["result"] == "COST_HOST_PASS", "host tests required")
    for item in result["inputs"]:
        cli.require(cli.record(item["path"]) == item, "tested source changed")
    baseline = ROOT / ".cache/p34ab"
    source = store.read(baseline / "source.json")
    old = store.read(baseline / "build.json")
    fw, bld, logs = (store.checked(AREA / n) for n in ("f", "b", "build"))
    cli.require(not any(p.exists() for p in (fw, bld, logs)), "preserve existing build")
    overlay = ("USER/HAL/HAL_OTA_Package.cpp", "USER/HAL/ota_install_cost.h")
    copies = []
    for item in source["files"]:
        original = store.checked(item["path"])
        cli.require(cli.record(original) == item, "baseline source changed")
        relative = original.relative_to(baseline / "f")
        copies.append((original, store.checked(fw / relative)))
    for name in overlay:
        store.checked(fw / name)
    env = environment(store, logs)
    for src, dst in copies:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
    for name in overlay:
        shutil.copyfile(ROOT / name, fw / name)
    store.write(logs / "source.json", dict(base=cli.record(baseline / "source.json"), overlay=list(overlay),
        files=[cli.record(p) for p in sorted(fw.rglob("*")) if p.is_file()]))
    args = [str(x).replace(str(baseline), str(AREA)) for x in old["commands"][0]["command"]]
    args = [x + " -DCONFIG_OTA_INSTALL_COST=1" if x.startswith("-DCMAKE_CXX_FLAGS:STRING=") else x for x in args]
    command(store, logs, "configure", args, env, 180)
    output = command(store, logs, "build", [args[0], "--build", bld, "--target", "X_Track_App_GCC", "--parallel", "6"], env, 600)
    artifacts = [cli.record(store.checked(bld / "app-gcc" / ("X-Track-App-GCC" + suffix)))
                 for suffix in (".bin", ".elf", ".map", ".hex")]
    warnings = len(re.findall(rb"\bwarning:", output))
    errors = len(re.findall(rb"\berror:", output))
    cli.require(errors == 0, "build contains errors")
    store.write(logs / "result.json", dict(result="COST_APP_BUILT", artifacts=artifacts,
        warnings=warnings, errors=errors, boot_built=False, hardware=False,
        source=cli.record(logs / "source.json"), tests=cli.record(AREA / "tests/result.json")))
    print("COST_APP_BUILT warnings", warnings, "errors", errors, "Boot not built")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("test", "build"))
    args = parser.parse_args()
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                "explicit root and isolated Python required")
    {"test": test, "build": build}[args.command](cli.Store(ROOT))
