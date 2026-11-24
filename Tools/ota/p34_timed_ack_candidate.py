"""Contained ACK hold candidate: test, clone verified source, and build App only."""
import argparse
import json
from pathlib import Path
import re
import shutil
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_half_erase_candidate as base
import p34_batch_review as review

cli, host = base.cli, base.host
BASE, AREA = base.AREA, ROOT / ".cache/p34-timed-ack"
HEADER = ROOT / "Tools/ota/p34_timed_ack_batch.h"
TEST = ROOT / "tests/ota/test_p34_timed_ack_batch.cpp"
HAL = "USER/HAL/HAL_Bluetooth.cpp"
COPIED_HEADER = "USER/HAL/p34_timed_ack_batch.h"
PRIOR = ROOT / ".cache/p34-info-retry/trials/extended"


def prepare(s):
    fw = s.checked(AREA / "f")
    cli.require(not fw.exists(), "preserve candidate source")
    proof, report = review.load_report(s, PRIOR)
    cli.require(report["summary"]["input"]["targetVersionCode"] == 30271, "confirmed30271 required")
    manifest = s.read(BASE / "build/source.json")
    copies = []
    for item in manifest["files"]:
        src = s.checked(item["path"])
        cli.require(cli.record(src) == item, "built baseline source changed")
        copies.append((src, s.checked(fw / src.relative_to(BASE / "f"))))
    target = s.checked(fw / COPIED_HEADER)
    s.checked(AREA / "prepared.json")
    for src, dst in copies:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
    shutil.copyfile(HEADER, target)
    s.write(AREA / "prepared.json", dict(base=cli.record(BASE / "build/source.json"),
        predecessor=proof, header=cli.record(HEADER), copied_header=cli.record(target), hardware=False))
    print("TIMED_ACK_SOURCE_PREPARED", len(copies))


def expected_hal():
    value = (BASE / "f" / HAL).read_text(encoding="utf-8")
    pairs = (
        ('#include "p34_ack_batch.h"', '#include "p34_timed_ack_batch.h"'),
        ('static P34AckBatch s_p34_ack_batch;', 'static P34TimedAckBatch s_p34_ack_batch;'),
        ('data_ok && durable == s_p34_ack_durable, ble_uart_send);',
         'data_ok && durable == s_p34_ack_durable, millis(), ble_uart_send);'),
        ('    HAL::OTA_OverlayReleaseBle();',
         '    (void)s_p34_ack_batch.drain(ble_uart_send);\n    HAL::OTA_OverlayReleaseBle();'),
        ('(void)s_p34_ack_batch.begin();', '(void)s_p34_ack_batch.begin(s_ble_epoch);'),
        ('        s_ble_epoch++;\n#if CONFIG_OTA_BLE_PROFILE',
         '        s_ble_epoch++;\n        (void)s_p34_ack_batch.rebind(s_ble_epoch);\n#if CONFIG_OTA_BLE_PROFILE'),
        ('(void)s_p34_ack_batch.end(ble_uart_send);',
         '(void)s_p34_ack_batch.end(millis(), ota_ble_session_active(&s_ble_session) != 0, ble_uart_send);'),
    )
    for old, new in pairs:
        cli.require(value.count(old) == 1, "ambiguous HAL integration anchor")
        value = value.replace(old, new)
    return value


def sources(s):
    prepared = s.read(AREA / "prepared.json")
    cli.require(prepared["base"] == cli.record(BASE / "build/source.json") and
        (AREA / "f" / COPIED_HEADER).read_bytes() == HEADER.read_bytes(), "prepared source changed")
    for item in s.read(BASE / "build/source.json")["files"]:
        src = Path(item["path"])
        relative = src.relative_to(BASE / "f")
        cli.require(cli.record(src) == item, "base source changed")
        if relative.as_posix() != HAL:
            cli.require((AREA / "f" / relative).read_bytes() == src.read_bytes(), "unrelated candidate change")
    cli.require((AREA / "f" / HAL).read_text(encoding="utf-8") == expected_hal(), "HAL wiring differs")
    return [cli.record(p) for p in (Path(__file__), HEADER, TEST, AREA / "f" / HAL,
                                    AREA / "f" / COPIED_HEADER)]


def test(s, attempt):
    out = s.checked(AREA / "tests" / attempt)
    cli.require(not out.exists(), "preserve native tests")
    bound = sources(s)
    for name in ("batch.exe", "compile.log", "compile.json", "native.log", "native.json", "result.json"):
        s.checked(out / name)
    s.checked(AREA / "tests/latest.json")
    s.checked(AREA / "tests/latest.json.tmp")
    env = host.environment(s, out)
    exe = out / "batch.exe"
    args = ["D:/install/mingw64/bin/g++.exe", "-std=c++11", "-O2", "-Wall", "-Wextra", "-Werror",
            TEST, "-o", exe]
    compiled = host.command(s, out, "compile", args, env, 120)
    cli.require(not re.search(rb"\bwarning:", compiled), "native compile warning")
    output = host.command(s, out, "native", [exe], env, 120)
    cli.require(b"TIMED_ACK_BATCH_PASS" in output and sources(s) == bound, "native oracle or source changed")
    s.write(out / "result.json", dict(result="TIMED_ACK_HOST_PASS", sources=bound,
        hardware=False, warnings=0, errors=0))
    s.write(AREA / "tests/latest.json", dict(report=cli.record(out / "result.json")),
            replace=(AREA / "tests/latest.json").exists())
    print("TIMED_ACK_HOST_PASS")


def build(s):
    ref = s.read(AREA / "tests/latest.json")["report"]
    cli.require(cli.record(ref["path"]) == ref, "test evidence changed")
    proof = s.read(ref["path"])
    cli.require(proof["result"] == "TIMED_ACK_HOST_PASS" and proof["sources"] == sources(s), "current tests required")
    fw, bld, out = (s.checked(AREA / x) for x in ("f", "b", "build"))
    cli.require(not bld.exists() and not out.exists(), "preserve build")
    s.checked(AREA / "install")
    args = [str(x).replace(str(BASE), str(AREA)) for x in s.read(BASE / "build/configure.json")["command"]]
    for name in ("source.json", "configure.json", "configure.log", "build.json", "build.log", "result.json"):
        s.checked(out / name)
    s.write(out / "source.json", dict(base=cli.record(BASE / "build/source.json"), overlays=[HAL, COPIED_HEADER],
        files=[cli.record(p) for p in sorted(fw.rglob("*")) if p.is_file()]))
    env = host.environment(s, out)
    host.command(s, out, "configure", args, env, 180)
    raw = host.command(s, out, "build", [args[0], "--build", bld, "--target", "X_Track_App_GCC", "--parallel", "6"], env, 900)
    def warnings(data):
        return base.previous.previous.review.warnings(data.replace(b"p34-timed-ack", b"p34-half-erase"))
    old, new = warnings((BASE / "build/build.log").read_bytes()), warnings(raw)
    value = dict(result="TIMED_ACK_APP_BUILT", artifacts=[cli.record(bld / "app-gcc" / ("X-Track-App-GCC" + ext))
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
    elif a.mode == "test": test(s, a.attempt)
    else:
        owner = cli.load_module("timed_ack_build_owner", ROOT / ".cache/p3-4-screening-20260922/supervisor.py")
        if a.mode == "launch":
            print(owner.owned.launch(s.checked(AREA / "runtime/build-001"), Path(__file__), ["worker"], 1500))
        else:
            cli.require(owner.owned.in_job(), "finite build owner required")
            build(s)
