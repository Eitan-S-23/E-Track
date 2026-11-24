"""Test actual mixed erase planner, backup engine, driver and HAL wrapper bodies."""
import argparse
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_half_erase_candidate as build
import p34_erase_candidate as legacy

cli, host, AREA = build.cli, build.host, build.AREA


def test(s, attempt):
    out = s.checked(AREA / "tests" / attempt)
    cli.require(not out.exists(), "preserve test attempt")
    fw = AREA / "f"
    paths = ["intent.json", "result.json", "host", "plan.exe", "backup.exe"]
    for size in (32, 64): paths += [f"driver{size}.cpp", f"driver{size}.exe"]
    for tag in ("default", "b0h0", "b0h1", "b1h0", "b1h1"):
        paths += [tag + ".cpp", "hal-" + tag + ".exe"]
    for p in paths: s.checked(out / p)
    bound = build.sources(s)
    prior = s.read(ROOT / ".cache/p34-erase/tests/latest.json")["report"]
    cli.require(cli.record(prior["path"]) == prior, "prior test report changed")
    old = s.read(prior["path"])
    expected = [x for x in old["inputs"] if Path(x["path"]) == ROOT / "tests/ota/test_ota_backup.c"]
    cli.require(old["result"] == "ERASE_HOST_PASS" and expected ==
                [cli.record(ROOT / "tests/ota/test_ota_backup.c")], "verified backup tests changed")
    s.write(out / "intent.json", dict(sources=bound, hardware=False))
    env = host.environment(s, out)
    gcc = Path("D:/install/mingw64/bin/gcc.exe")
    gxx = gcc.with_name("g++.exe")
    results = {}
    try:
        for tag, names in (("plan", [ROOT / "tests/ota/test_p34_half_erase_plan.c"]),
                           ("backup", [ROOT / "tests/ota/test_p34_half_erase_backup.c",
                                       *[fw / p for p in legacy.BACKUP[1:]]])):
            exe = s.checked(out / (tag + ".exe"))
            host.command(s, out, tag + "-compile", [gcc, "-std=c99", "-O2", "-Wall", "-Wextra", "-Werror",
                "-DCONFIG_OTA_APP_CRC32_NIBBLE=1", "-I" + str(fw / "Libraries"), "-I" + str(fw / "boot/include"),
                *names, "-o", exe], env, 120)
            data = host.command(s, out, tag, [exe], env, 180)
            cli.require(b"HALF_ERASE_" in data and b"PASS" in data and b"failures=0" in data
                        if tag == "backup" else b"HALF_ERASE_PLAN_PASS" in data, "native tests failed")
            results[tag] = data.decode().strip()
        model = cli.load_module("half_erase_extract", ROOT / "tests/ota/test_qspi_install_restore.py")
        driver = (fw / "Libraries/W25Q128/qspi_cmd_en25qh128a.cpp").read_text(encoding="utf-8")
        header = (fw / "Libraries/W25Q128/qspi_cmd_en25qh128a.h").read_text(encoding="utf-8")
        enum = model.extract(header, r"^typedef enum\n\{.*?^\} qspi_status_t;")
        defines = "\n".join(re.findall(r"^#define QSPI_(?:FLASH_CAPACITY|SELFTEST_ADDR|SELFTEST_SIZE|BLOCK_ERASE_TIMEOUT_MS)\s+[^\n]+", header, re.M))
        for size in (32, 64):
            tag = "driver" + str(size)
            preamble, cases = legacy.DRIVER_HEAD, legacy.DRIVER_CASES
            if size == 32:
                preamble = preamble.replace("0xD8", "0x52")
                cases = cases.replace("qspi_erase_64k", "qspi_erase_32k")
                cases = cases.replace("{0, 65536, 0x100000, 0x7e0000}", "{0, 32768, 65536, 0x100000, 0x7e8000}")
                cases = cases.replace("0xffff0000", "0xffff8000")
            body = "\n".join((enum, defines, preamble, model.function(driver, "qspi_range_ok"),
                               model.function(driver, "qspi_erase_" + str(size) + "k"), cases))
            source = s.raw(out / (tag + ".cpp"), body.encode())
            exe = s.checked(out / (tag + ".exe"))
            host.command(s, out, tag + "-compile", [gxx, "-std=c++11", "-O2", "-Wall", "-Wextra", "-Werror",
                source["path"], "-o", exe], env, 120)
            results[tag] = host.command(s, out, tag, [exe], env, 60).decode().strip()
            cli.require("DRIVER_ERASE_PASS" in results[tag], "raw driver checks failed")
        hal = (fw / "USER/HAL/HAL_OTA_Package.cpp").read_text(encoding="utf-8")
        defaults = "\n".join(model.extract(hal, r"^#ifndef " + k + r"\n.*?^#endif")
            for k in ("CONFIG_OTA_INSTALL_BLOCK_ERASE", "CONFIG_OTA_INSTALL_HALF_ERASE"))
        functions = "\n".join(model.function(hal, k) for k in
            ("backup_slot_range_ok", "install_block_erase_enabled", "install_half_erase_enabled",
             "candidate_prepare", "backup_flash_erase_4k"))
        for size, flag in ((64, "BLOCK"), (32, "HALF")):
            functions += "\n#if CONFIG_OTA_INSTALL_" + flag + "_ERASE\n" + \
                         model.function(hal, "backup_flash_erase_" + str(size) + "k") + "\n#endif\n"
        functions += "\n" + model.function(hal, "HAL::OTA_BackupStage")
        template = (ROOT / "tests/ota/p34_half_erase_hal.cpp").read_text()
        body = defaults + "\n" + template.replace("/* EXTRACTED_HAL */", functions)
        for tag, block, half in (("default", None, None), ("b0h0", 0, 0), ("b0h1", 0, 1), ("b1h0", 1, 0), ("b1h1", 1, 1)):
            source = s.raw(out / (tag + ".cpp"), body.encode())
            exe = s.checked(out / ("hal-" + tag + ".exe"))
            args = [gxx, "-std=c++11", "-O2", "-Wall", "-Wextra", "-Werror",
                    "-I" + str(fw / "Libraries"), "-I" + str(fw / "boot/include"), source["path"], "-o", exe]
            if block is not None: args += ["-DCONFIG_OTA_INSTALL_BLOCK_ERASE=" + str(block), "-DCONFIG_OTA_INSTALL_HALF_ERASE=" + str(half)]
            host.command(s, out, tag + "-compile", args, env, 120)
            results[tag] = host.command(s, out, tag, [exe], env, 60).decode().strip()
            cli.require("HALF_ERASE_HAL_PASS" in results[tag], "HAL checks failed")
        cli.require(not any(re.search(rb"\bwarning:", p.read_bytes()) for p in out.glob("*-compile.log")), "native warning")
        cli.require(build.sources(s) == bound, "tested sources changed")
        s.write(out / "result.json", dict(result="HALF_ERASE_HOST_PASS", sources=bound, native=results,
            hardware=False, warnings=0, errors=0))
        s.write(AREA / "tests/latest.json", dict(report=cli.record(out / "result.json")),
                replace=(AREA / "tests/latest.json").exists())
        print("HALF_ERASE_HOST_PASS", results)
    except Exception as error:
        s.write(out / "result.json", dict(result="HALF_ERASE_HOST_FAIL", sources=bound, native=results,
            hardware=False, error=type(error).__name__, detail=str(error)))
        raise


if __name__ == "__main__":
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                "isolated explicit root required")
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--attempt", default="r1")
    a = p.parse_args()
    cli.require(re.fullmatch(r"r[1-9][0-9]*", a.attempt), "invalid attempt")
    test(cli.Store(ROOT), a.attempt)
