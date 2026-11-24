"""Contained host checks and App-only build for optional payload block erase."""
import argparse
from collections import Counter
import json
import os
from pathlib import Path
import re
import shutil
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_session as cli
import p34_install_cost as host

AREA = ROOT / ".cache/p34-erase"
OVERLAY = ("Libraries/OTA/ota_backup.c", "Libraries/OTA/ota_backup.h",
    "Libraries/OTA/ota_erase_plan.h", "Libraries/W25Q128/qspi_cmd_en25qh128a.cpp",
    "Libraries/W25Q128/qspi_cmd_en25qh128a.h", "USER/HAL/HAL_OTA_Package.cpp")
BACKUP = ("tests/ota/test_ota_backup.c", "Libraries/OTA/ota_backup.c",
    "Libraries/OTA/ota_slot_header.c", "Libraries/EEPROM/eeprom_bcb.c",
    "boot/src/boot_crc32.c", "boot/src/boot_sha256.c", "boot/src/boot_fw_header.c")

DRIVER_HEAD = r"""
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
static unsigned checks, calls, fail_at;
static uint32_t expected_address;
#define CHECK(x) do { ++checks; if (!(x)) { fprintf(stderr, "DRIVER_ERASE_FAIL %d\n", __LINE__); exit(7); } } while (0)
typedef struct { uint32_t instruction_code, address_code; } qspi_cmd_type;
static const qspi_cmd_type en25qh128a_erase_para = {0x20, 0};
static const qspi_cmd_type en25qh128a_rdsr_para = {0x05, 0};
static qspi_cmd_type en25qh128a_cmd_config;
static qspi_status_t status(void) { ++calls; return calls == fail_at ? QSPI_ERR_TIMEOUT : QSPI_OK; }
static qspi_status_t qspi_write_enable(void) { CHECK(calls == 0); return status(); }
static qspi_status_t qspi_cmd_send(qspi_cmd_type *cmd) {
    CHECK(calls == 1 && cmd->instruction_code == 0xD8 && cmd->address_code == expected_address);
    return status();
}
static qspi_status_t qspi_cmd_send_ex(qspi_cmd_type *cmd, uint32_t timeout) {
    CHECK(calls == 2 && cmd == &en25qh128a_rdsr_para);
    CHECK(timeout == 4000u);
    return status();
}
"""
DRIVER_CASES = r"""
int main(void) {
    const uint32_t good[] = {0, 65536, 0x100000, 0x7e0000};
    const uint32_t bad[] = {1, 4096, 0x7effff, 0x7f0000, 0x800000, 0xffff0000};
    for (unsigned i = 0; i < sizeof(good)/sizeof(good[0]); ++i) {
        for (fail_at = 0; fail_at <= 3; ++fail_at) {
            calls = 0; expected_address = good[i];
            qspi_status_t result = qspi_erase_64k(good[i]);
            CHECK(result == (fail_at ? QSPI_ERR_TIMEOUT : QSPI_OK));
            CHECK(calls == (fail_at ? fail_at : 3));
        }
    }
    for (unsigned i = 0; i < sizeof(bad)/sizeof(bad[0]); ++i) {
        calls = fail_at = 0;
        CHECK(qspi_erase_64k(bad[i]) != QSPI_OK && calls == 0);
    }
    printf("DRIVER_ERASE_PASS checks=%u\n", checks);
    return 0;
}
"""


def source_records():
    names = set(OVERLAY + BACKUP + ("tests/ota/test_ota_erase_plan.c",
        "tests/ota/test_qspi_install_restore.py", "Tools/ota/p34_erase_candidate.py",
        "Libraries/OTA/ota_layout.h", "Libraries/OTA/ota_slot_header.h",
        "Libraries/EEPROM/eeprom_bcb.h", "boot/include/boot_crypto.h", "boot/include/boot_fw_header.h"))
    return [cli.record(ROOT / p) for p in sorted(names)]


def warning_counts(data):
    messages = []
    for line in data.splitlines():
        if b"warning:" not in line:
            continue
        text = line.split(b"warning:", 1)[1].strip().decode("utf-8", "replace")
        for separator in ("/", "\\"):
            for name in ("p34-cost", "p34-erase"):
                text = text.replace(".cache" + separator + name + separator,
                                    ".cache" + separator + "<build>" + separator)
        messages.append(text)
    return Counter(messages)


def warning_checks():
    old = b"ld: warning: dir/.cache/p34-cost/f/a.o uses 2-byte wchar_t"
    new = old.replace(b"p34-cost", b"p34-erase")
    cli.require(warning_counts(old) == warning_counts(new), "path-only warning mismatch")
    cli.require(warning_counts(old) != warning_counts(new.replace(b"a.o", b"b.o")), "filename lost")
    cli.require(warning_counts(old) != warning_counts(new.replace(b"2-byte", b"4-byte")), "warning detail lost")
    cli.require(sum((warning_counts(new + b"\n" + new) - warning_counts(old)).values()) == 1, "multiplicity lost")
    cli.require(warning_counts(old) != warning_counts(new.replace(b"p34-erase", b"p34-other")), "unrelated path normalized")
    cli.require(not warning_counts(b"ordinary compiler output"), "invented warning")
    cli.require(warning_counts(old.replace(b"/", b"\\")) == warning_counts(new.replace(b"/", b"\\")), "Windows path mismatch")
    return 7


def test(s, attempt):
    out = s.checked(AREA / "tests" / attempt)
    cli.require(not out.exists(), "preserve test attempt")
    before = source_records()
    env = host.environment(s, out)
    s.write(out / "intent.json", dict(inputs=before, hardware=False))
    gcc = Path("D:/install/mingw64/bin/gcc.exe")
    gxx = gcc.with_name("g++.exe")
    results = {}
    try:
        results["warning_normalizer_checks"] = warning_checks()
        for tag, files in (("plan", ("tests/ota/test_ota_erase_plan.c",)), ("backup", BACKUP)):
            exe = s.checked(out / (tag + ".exe"))
            host.command(s, out, tag + "-compile", [gcc, "-std=c99", "-O2", "-Wall", "-Wextra", "-Werror",
                "-I" + str(ROOT / "Libraries"), "-I" + str(ROOT / "boot/include"),
                *[ROOT / f for f in files], "-o", exe], env, 90)
            data = host.command(s, out, tag, [exe], env, 120)
            cli.require(b"PASS" in data if tag == "plan" else b"failures=0" in data, "native PASS missing")
            results[tag] = data.decode().strip()
        model = cli.load_module("erase_restore_model", ROOT / "tests/ota/test_qspi_install_restore.py")
        driver = (ROOT / "Libraries/W25Q128/qspi_cmd_en25qh128a.cpp").read_text(encoding="utf-8")
        header = (ROOT / "Libraries/W25Q128/qspi_cmd_en25qh128a.h").read_text(encoding="utf-8")
        enum = model.extract(header, r"^typedef enum\n\{.*?^\} qspi_status_t;")
        defines = "\n".join(re.findall(r"^#define QSPI_(?:FLASH_CAPACITY|SELFTEST_ADDR|SELFTEST_SIZE|BLOCK_ERASE_TIMEOUT_MS)\s+[^\n]+", header, re.M))
        body = enum + "\n" + defines + "\n" + DRIVER_HEAD + model.function(driver, "qspi_range_ok") + "\n" + model.function(driver, "qspi_erase_64k") + DRIVER_CASES
        fixture = s.raw(out / "driver.cpp", body.encode("utf-8"))
        exe = s.checked(out / "driver.exe")
        host.command(s, out, "driver-compile", [gxx, "-std=c++11", "-O2", "-Wall", "-Wextra", "-Werror", fixture["path"], "-o", exe], env, 90)
        results["driver"] = host.command(s, out, "driver", [exe], env, 60).decode().strip()
        cli.require("DRIVER_ERASE_PASS" in results["driver"], "driver PASS missing")
        host.command(s, out, "hal", [sys.executable, "-I", "-S", "-B", "-X", "utf8",
            ROOT / "tests/ota/test_qspi_install_restore.py", "--root", ROOT, "--out", out / "hal"], env, 180)
        hal = s.read(out / "hal/result.json")
        cli.require(hal["result"] == "HOST_MODEL_PASS" and hal["tests"] == 16 and hal["inputs_unchanged"], "HAL checks failed")
        cli.require(not any(re.search(rb"\bwarning:", p.read_bytes()) for p in out.glob("*-compile.log")), "native compiler warning")
        cli.require(before == source_records(), "sources changed during tests")
        value = dict(result="ERASE_HOST_PASS", inputs=before, native=results,
            hal=cli.record(out / "hal/result.json"), hardware=False, warnings=0, errors=0)
        s.write(out / "result.json", value)
        s.write(AREA / "tests/latest.json", dict(report=cli.record(out / "result.json")), replace=(AREA / "tests/latest.json").exists())
        print("ERASE_HOST_PASS", results, "HAL16")
    except Exception as e:
        if not (out / "result.json").exists():
            s.write(out / "result.json", dict(result="ERASE_HOST_FAIL", error=type(e).__name__, detail=str(e), inputs=before, native=results, hardware=False))
        raise


def build(s):
    test_ref = s.read(AREA / "tests/latest.json")["report"]
    cli.require(cli.record(test_ref["path"]) == test_ref, "test report changed")
    checked = s.read(test_ref["path"])
    cli.require(checked["result"] == "ERASE_HOST_PASS" and checked["inputs"] == source_records(), "current source tests required")
    cli.require(cli.record(checked["hal"]["path"]) == checked["hal"], "HAL report changed")
    hal_inputs = s.read(checked["hal"]["path"])["inputs"]
    for item in hal_inputs:
        cli.require(cli.record(item["path"]) == item, "HAL test input changed")
    base = ROOT / ".cache/p34-cost"
    manifest = s.read(base / "build/source.json")
    fw, bld, logs = (s.checked(AREA / p) for p in ("f", "b", "build"))
    cli.require(not any(p.exists() for p in (fw, bld, logs)), "preserve build")
    copies = []
    for item in manifest["files"]:
        src = s.checked(item["path"])
        cli.require(cli.record(src) == item, "retained source changed")
        copies.append((src, s.checked(fw / src.relative_to(base / "f"))))
    for name in OVERLAY:
        s.checked(fw / name)
    for item in hal_inputs + checked["inputs"]:
        src = Path(item["path"])
        relative = src.relative_to(ROOT)
        prior = base / "f" / relative
        if relative.parts[0] in ("Libraries", "USER", "boot", "vendor") and relative.as_posix() not in OVERLAY:
            cli.require(prior.exists() and src.read_text(encoding="utf-8") == prior.read_text(encoding="utf-8"),
                        "host/base dependency differs: " + str(relative))
    env = host.environment(s, logs)
    for src, dst in copies:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
    for name in OVERLAY:
        shutil.copyfile(ROOT / name, fw / name)
    s.write(logs / "source.json", dict(base=cli.record(base / "build/source.json"), overlay=list(OVERLAY),
        files=[cli.record(p) for p in sorted(fw.rglob("*")) if p.is_file()]))
    args = [str(x).replace(str(base), str(AREA)) for x in s.read(base / "build/configure.json")["command"]]
    args = [x + " -DCONFIG_OTA_INSTALL_BLOCK_ERASE=1" if x.startswith("-DCMAKE_CXX_FLAGS:STRING=") else x for x in args]
    cli.require(any("CONFIG_OTA_INSTALL_BLOCK_ERASE=1" in x for x in args), "missing candidate flag")
    host.command(s, logs, "configure", args, env, 180)
    output = host.command(s, logs, "build", [args[0], "--build", bld, "--target", "X_Track_App_GCC", "--parallel", "6"], env, 600)
    artifacts = [cli.record(bld / "app-gcc" / ("X-Track-App-GCC" + ext)) for ext in (".bin", ".elf", ".map", ".hex")]
    warnings, errors = (len(re.findall(pattern, output)) for pattern in (rb"\bwarning:", rb"\berror:"))
    cli.require(errors == 0, "build errors")
    added = warning_counts(output) - warning_counts((base / "build/build.log").read_bytes())
    s.write(logs / "result.json", dict(result="ERASE_APP_BUILT", artifacts=artifacts, warnings=warnings, errors=errors,
        new_warnings=dict(added), boot_built=False, hardware=False, source=cli.record(logs / "source.json"), tests=test_ref))
    cli.require(not added, "new compiler warnings require review")
    print("ERASE_APP_BUILT", "warnings", warnings, "errors", errors, "Boot not built")


def review(s):
    out = s.checked(AREA / "build-review/result.json")
    cli.require(not out.exists(), "preserve build review")
    build_path = AREA / "build/result.json"
    built = s.read(build_path)
    test_ref = s.read(AREA / "tests/latest.json")["report"]
    cli.require(cli.record(test_ref["path"]) == test_ref, "test report changed")
    tests = s.read(test_ref["path"])
    cli.require(tests["result"] == "ERASE_HOST_PASS" and tests["inputs"] == source_records(), "current tests required")
    cli.require(built["result"] == "ERASE_APP_BUILT" and built["errors"] == 0 and not built["boot_built"], "build failed")
    for item in built["artifacts"] + [built["source"]]:
        cli.require(cli.record(item["path"]) == item, "built artifact changed")
    for item in s.read(built["source"]["path"])["files"]:
        cli.require(cli.record(item["path"]) == item, "built source changed")
    for name in OVERLAY:
        cli.require((ROOT / name).read_bytes() == (AREA / "f" / name).read_bytes(), "production overlay changed after build")
    logs = [ROOT / ".cache/p34-cost/build/build.log", AREA / "build/build.log"]
    old, new = [warning_counts(p.read_bytes()) for p in logs]
    cli.require(old == new and sum(new.values()) == built["warnings"], "real compiler warning difference")
    warning_checks()
    s.write(out, dict(result="ERASE_BUILD_REVIEW_PASS", build=cli.record(build_path), tests=test_ref,
        source=cli.record(__file__), logs=[cli.record(p) for p in logs], warnings=built["warnings"], new_warnings=0,
        errors=0, production_unchanged=True, firmware_rebuilt=False, normalizer_checks=7,
        reason="Original comparator retained embedded build paths in wchar_t warnings; normalize only the two known cache directory segments. Original report preserved."))
    print("ERASE_BUILD_REVIEW_PASS", "warnings", built["warnings"], "new0 errors0; no rebuild")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("test", "build", "review"))
    parser.add_argument("--attempt", default="r1")
    args = parser.parse_args()
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                "explicit root and isolated Python required")
    cli.require(re.fullmatch(r"r[1-9][0-9]*", args.attempt), "invalid test attempt")
    if args.command == "test":
        test(cli.Store(ROOT), args.attempt)
    elif args.command == "build":
        build(cli.Store(ROOT))
    else:
        review(cli.Store(ROOT))
