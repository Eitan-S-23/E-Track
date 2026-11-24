"""Prepare the identity-bound 30209 -> 30208 complete Boot rollback route.

This file's preparation entry does not connect a device. The recovery transaction
uses the existing inactive-BCB commit and verified complete backup, not an App-only
downgrade or a host-constructed EEPROM write.
"""
from __future__ import annotations

import argparse
import ctypes
import importlib.util
import json
from pathlib import Path
import re
import struct
import sys
import time
import zlib


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


m = load("baud_restore_mcu", Path(__file__).with_name("baud_mcu.py"))
b, a = m.b, m.a
OUT = b.OUT / "recovery"
OLD = b.ROOT / ".cache/p34-restore-20260922/helper"
COMMAND, MAGIC = 0x52333238, 0x38325352


def checked(name):
    return b.checked(OUT / name)


def save(name, value):
    return b.io.write_json(b.ROOT, checked(name), value)


def expectation():
    assets = m.verified_assets()
    group = assets["groups"]["screen"]
    data = Path(group["baseline"]["path"]).read_bytes()
    return dict(from_version=30209, to_version=30208, backup_length=len(data),
        backup_crc32=zlib.crc32(data) & 0xFFFFFFFF, backup_sha256=group["baseline"]["sha256"],
        boot_sha256=assets["whole_boot"]["sha256"], group=group)


def replace_once(text, before, after):
    b.require(text.count(before) == 1, "reviewed source transform drift: " + before)
    return text.replace(before, after, 1)


def command(tag, args, *, timeout=180):
    path = checked(tag + ".log")
    b.require(not path.exists(), "preserve recovery command evidence")
    result = b.command(list(map(str, args)), cwd=a.FW, timeout=timeout, check=False,
                       extra_env=dict(SOURCE_DATE_EPOCH="1786320000", CCACHE_DISABLE="1", SCCACHE_DISABLE="1"))
    with path.open("xb") as stream:
        stream.write(result.stdout + result.stderr)
    save(tag + ".json", dict(exit=result.returncode, log=b.record(path), args=list(map(str, args))))
    print("RECOVERY_PREPARATION", tag, "exit", result.returncode, flush=True)
    b.require(result.returncode == 0, "recovery preparation failed: " + tag)
    return result.stdout + result.stderr


def prepare():
    b.require(not OUT.exists(), "preserve previous recovery preparation")
    expected = expectation()
    source_names = ("restore_core.h", "restore_core.c", "restore_main.cpp", "test_restore.c")
    for name in (*["helper/" + name for name in source_names], "helper/inject.cmake", "build", "host-test.exe",
                 "helper-app.bin", "inputs.json", "manifest.json", "result.json"):
        checked(name)
    for tag in ("host-compile", "host-test", "configure", "build", "finalize"):
        checked(tag + ".log")
        checked(tag + ".json")
    checked("helper").mkdir(parents=True)
    inputs = [b.record(OLD / name) for name in source_names]
    transformed = {}
    for name in source_names:
        text = (OLD / name).read_text(encoding="ascii")
        text = text.replace("30207", "30209").replace("30206", "30208")
        text = text.replace("603764", str(expected["backup_length"]))
        text = text.replace("2464293393", str(expected["backup_crc32"]))
        if name == "restore_main.cpp":
            text = replace_once(text, "0x52333236u", "0x52333238u")
            text = replace_once(text, "0x36325352u", "0x38325352u")
            text = text.replace("RESTORE326:", "RESTORE328:")
            before = re.search(r"static const uint8_t wanted_backup\[32\] = \{.*?\};", text, re.S)
            b.require(before is not None, "backup digest declaration missing")
            digest = bytes.fromhex(expected["backup_sha256"])
            after = "static const uint8_t wanted_backup[32] = {\n    " + ",".join("0x%02x" % value for value in digest) + "\n};"
            text = replace_once(text, before.group(0), after)
        path = checked("helper/" + name)
        with path.open("x", encoding="ascii", newline="\n") as stream:
            stream.write(text)
        transformed[name] = b.record(path)
    injection = '''function(configure_restore_app)
    get_target_property(sources X_Track_App_GCC SOURCES)
    list(LENGTH sources before_count)
    list(FILTER sources EXCLUDE REGEX "/USER/main[.]cpp$")
    list(LENGTH sources after_count)
    math(EXPR difference "${before_count} - ${after_count}")
    if(NOT difference EQUAL 1)
        message(FATAL_ERROR "Exactly the production App main must be replaced")
    endif()
    set_property(TARGET X_Track_App_GCC PROPERTY SOURCES "${sources}")
    get_filename_component(fw "${CMAKE_SOURCE_DIR}/../.." ABSOLUTE)
    target_sources(X_Track_App_GCC PRIVATE
        "${CMAKE_CURRENT_FUNCTION_LIST_DIR}/restore_main.cpp"
        "${CMAKE_CURRENT_FUNCTION_LIST_DIR}/restore_core.c"
        "${fw}/boot/src/boot_slot.c")
    target_include_directories(X_Track_App_GCC PRIVATE "${CMAKE_CURRENT_FUNCTION_LIST_DIR}")
endfunction()
cmake_language(DEFER CALL configure_restore_app)
'''
    with checked("helper/inject.cmake").open("x", encoding="ascii", newline="\n") as stream:
        stream.write(injection)
    save("inputs.json", dict(time=b.now(), sources=inputs, transformed=transformed,
        expected=expected, generator=b.record(Path(__file__)), hardware=False))
    command("host-compile", [a.COMPILER, "-std=c99", "-O2", "-Wall", "-Wextra", "-Werror",
        "-I" + str(a.FW / "Libraries"), "-I" + str(checked("helper")),
        checked("helper/test_restore.c"), checked("helper/restore_core.c"),
        a.FW / "Libraries/EEPROM/eeprom_bcb.c", "-o", checked("host-test.exe")])
    test = command("host-test", [checked("host-test.exe")]).decode("utf-8")
    b.require("RESTORE_CORE_TESTS=18 PASS" in test, "real BCB rollback regression missing")
    cmake = Path(r"C:\Program Files\CMake\bin\cmake.exe")
    toolchain = Path(r"D:\singlechip\gcc+gdb+openocd\tools\arm-gnu-toolchain-13.3.rel1-ming")
    args = [cmake, "-S", a.FW / "MDK-ARM_F435/cmake-generated", "-B", checked("build"), "-G", "Ninja",
        "-DCMAKE_BUILD_TYPE=Release", "-DCMAKE_OBJECT_PATH_MAX=1024", "-DP3_4_LINK_PROFILE=OFF",
        "-DKEIL_GCC_COMPILER_CACHE:FILEPATH=", "-DARM_TOOLCHAIN_ROOT=" + str(toolchain),
        "-DCMAKE_PROJECT_INCLUDE=" + str(checked("helper/inject.cmake")),
        "-DCMAKE_MAKE_PROGRAM=D:/singlechip/gcc+gdb+openocd/tools/ninja-win/ninja.exe"]
    for language, compiler in (("C", "gcc"), ("CXX", "g++"), ("ASM", "gcc")):
        args.append("-DCMAKE_" + language + "_COMPILER=" + str(toolchain / "bin" / ("arm-none-eabi-" + compiler + ".exe")))
    command("configure", args)
    log = command("build", [cmake, "--build", checked("build"), "--target", "X_Track_App_GCC", "--parallel", "8"], timeout=1200)
    raw = checked("build/app-gcc/X-Track-App-GCC.bin")
    command("finalize", a.python_tool("etu_pack.py", ["finalize", "--app", raw, "--out", checked("helper-app.bin"),
        "--ver-name", "3.2.9-r328", "--build-ts", str(expected["group"]["baseline_identity"]["build_timestamp"])]))
    helper = checked("helper-app.bin").read_bytes()
    identity = a.legacy.firmware(helper)
    body = raw.read_bytes()
    b.require(helper[:0x400] == body[:0x400] and helper[0x460:] == body[0x460:] and
              identity["version_code"] == 30209, "helper finalization changed body or version")
    sp, reset = struct.unpack_from("<II", helper)
    b.require(0x20000000 < sp <= 0x20080000 and sp % 8 == 0 and reset & 1 and
              m.c.APP <= (reset & ~1) < m.c.APP + len(helper) <= 0x08100000, "helper App vector/range")
    map_path = checked("build/app-gcc/X-Track-App-GCC.map")
    address = m.map_symbol(map_path.read_text(encoding="utf-8"), "g_restore_control")
    b.require(0x20000000 <= address <= 0x20058000 - 640, "helper mailbox range")
    b.require(all(b.record(item["path"]) == item for item in inputs + list(transformed.values())), "source drift")
    value = dict(result="HOST_READY", helper=b.record(checked("helper-app.bin")), identity=identity,
        mailbox=address, mailbox_bytes=640, expected=expected, command=COMMAND, magic=MAGIC,
        map=b.record(map_path), host_tests=18, warnings=len(re.findall(rb"\bwarning:", log)),
        errors=len(re.findall(rb"\berror:", log)), boot_replacement=False, release=False, hardware="NOT_RUN",
        execution_requires="fresh known UART 115200; actual full target/whole Boot/backup bytes and settled BCB; one transaction")
    save("result.json", value)
    save("manifest.json", dict(metadata=value, files=[b.record(path) for path in
        [checked("helper-app.bin"), map_path, checked("host-test.exe"), checked("inputs.json"),
         checked("host-test.log"), checked("build.log"), checked("result.json"),
         *[checked("helper/" + name) for name in (*source_names, "inject.cmake")]]]))
    print("RECOVERY_HOST_READY", identity["raw_image_sha256"], "warnings", value["warnings"], flush=True)


def validate_slot(header, baseline, expected):
    b.require(len(header) == 32 and header[:8] == b"ETSL\x02\xff\xff\xff" and
              struct.unpack_from("<I", header, 28)[0] == 0x434F4D54, "backup slot is not committed")
    b.require(struct.unpack_from("<III", header, 8) == (expected["backup_length"], expected["backup_crc32"], 30208) and
              header[20:28] == baseline[0x428:0x430], "backup slot version/length/CRC/SHA8 mismatch")


def mailbox(data, expected):
    b.require(len(data) == 640, "full helper mailbox required")
    words = struct.unpack_from("<16I", data)
    b.require(words[:2] == (MAGIC, 1) and words[8:12] == (30209, 30208, expected["backup_length"], expected["backup_crc32"]),
              "helper mailbox identity mismatch")
    return words


def validate_ready(data, expected, arbitrate):
    words = mailbox(data, expected)
    b.require(words[2] == 1 and words[3] == 0 and words[5:7] == (0, 0) and words[12:16] == (0, 0, 0, 0),
              "helper not pristine READY")
    b.require(data[576:608].hex() == expected["boot_sha256"] and data[608:640].hex() == expected["backup_sha256"],
              "helper independently read different Boot/backup bytes")
    raw = data[64:320]
    active, record = arbitrate(raw)
    b.require(active == words[7] and raw[255] == 0x55 and record[5:8] == bytes((4, 0, 0)) and record[10:12] == bytes(2),
              "BCB not settled CONFIRMED")
    b.require(struct.unpack_from("<IIII", record, 28) == (30209, expected["backup_length"], expected["backup_crc32"], 30208),
              "BCB current and full-backup identity mismatch")
    return active, record


def validate_committed(ready, data, expected, arbitrate):
    active, record = validate_ready(ready, expected, arbitrate)
    words = mailbox(data, expected)
    b.require(words[2:4] == (3, 0) and words[5] == 0 and words[12:15] == (1, 0, 1), "rollback not committed")
    b.require(data[64:320] == ready[64:320] and data[576:] == ready[576:], "helper input evidence changed")
    updated = bytearray(record)
    updated[5:8] = bytes((5, 0, 2))
    struct.pack_into("<H", updated, 8, (struct.unpack_from("<H", record, 8)[0] + 1) & 0xFFFF)
    updated[10:12] = bytes(2)
    struct.pack_into("<I", updated, 60, zlib.crc32(updated[:60]) & 0xFFFFFFFF)
    wanted = bytearray(ready[64:320])
    offset = 64 if active == 1 else 0
    wanted[offset:offset + 64] = updated
    b.require(data[320:576] == wanted, "EEPROM changed beyond the inactive BCB transaction")
    after_active, after = arbitrate(data[320:576])
    b.require(after_active == 3 - active and after == updated, "post-commit BCB arbitration failed")
    return dict(before_active=active, after_active=after_active, settings_unchanged=True,
                before_seq=struct.unpack_from("<H", record, 8)[0], after_seq=struct.unpack_from("<H", after, 8)[0])


def execute(label, rate_receipt):
    b.require(re.fullmatch(r"[a-z0-9-]{1,48}", label), "recovery label")
    m.native_authority()
    manifest = json.loads(checked("manifest.json").read_text(encoding="utf-8"))
    b.require(all(b.record(item["path"]) == item for item in manifest["files"]), "recovery assets changed")
    value, expected = manifest["metadata"], expectation()
    b.require(value["result"] == "HOST_READY" and value["expected"] == expected, "recovery expectation changed")
    rate = json.loads(Path(rate_receipt).read_text(encoding="utf-8"))
    b.require(rate["result"] == "BAUD_COLD_START_VERIFIED" and rate["baud"] == 115200 and rate["version"] == 30209 and
              rate["reader_closed"] and rate["final_status"]["busy"] == 0, "return module and MCU to verified 115200 before maintenance")
    old = load("baud_restore_existing_primitives", b.ROOT / ".cache/p34-restore-20260922/restore_device.py")
    old.COMMAND, old.APP_RTT = COMMAND, m.load_bindings()["profiles"]["30208"]["symbols"]["rtt"]
    symbols = m.load_bindings()["profiles"]["30208"]["symbols"]
    old.APP_TICK, old.APP_CLOCK, old.APP_SD = symbols["tick"], symbols["core_clock"], symbols["sd_ready"]
    old.CONFIRMED = "OTA: BCB already CONFIRMED vcode=30208"
    directory = b.checked(OUT / ("execute-" + label))
    b.require(not directory.exists(), "recovery outcome already exists; never reissue a possible transaction")
    for phase in ("preflight", "helper", "final"):
        for name in ("backup.bin", "image.bin", "boot-region.bin", "backup-header.bin", "staging-journal.bin",
                     "sdk.log", "sdk-callbacks.log", "project.jlink", "up.raw", "ready.bin", "committed.bin",
                     "eeprom-before.bin", "eeprom-after.bin"):
            b.checked(directory / phase / name)
    for name in ("flash.log", "flash.json", "flash.jlink", "flash-settings.jlink", "flash-sdk.log", "result.json", "actions.jsonl"):
        b.checked(directory / name)
    journal = old.Journal(directory)
    old.b.OUT = directory
    baseline = Path(expected["group"]["baseline"]["path"]).read_bytes()
    target = Path(expected["group"]["target"]["path"]).read_bytes()
    helper = Path(value["helper"]["path"]).read_bytes()
    boot = Path(m.load_bindings()["whole_boot"]["path"]).read_bytes()
    result = dict(started=b.now(), result="NOT_RESTORED", from_version=30209, to_version=30208,
        rate_receipt=b.record(rate_receipt), source=b.record(Path(__file__)), helper=value["helper"],
        native_history_before=m.c.record(m.c.MRU), flash_started=False, command_started=False,
        rollback_reset_started=False, boot_replacement=False, release=False, independent_acceptance=False)
    link = channel = None

    def region(address, size):
        if (address, address + size) not in link.ram_reads:
            link.ram_reads.append((address, address + size))
        return old.read_all(link, address, size)

    try:
        evidence = old.Evidence(journal, "preflight")
        link = old.Link(evidence, writable=False)
        link.connect()
        result["before_app"] = link.image(target)
        result["before_boot"] = old.verify_boot(link, evidence, boot)
        b.require(m.u32(region(m.ERTC_DT20, 4)) == m.baud_word(115200), "retained baud changed after admission")
        header = region(0x90100000, 32)
        evidence.save("backup-header.bin", header)
        validate_slot(header, baseline, expected)
        backup = region(0x90101000, len(baseline))
        result["physical_backup"] = evidence.save("backup.bin", backup)
        b.require(backup == baseline and region(0x90100000, 32) == header, "complete physical backup differs")
        evidence.save("staging-journal.bin", region(0x90300000, 4096))
        link.close()
        link = None
        command_file = b.checked(directory / "flash.jlink")
        commands = ["exec DisableAutoUpdateFW", "h", 'loadbin "' + value["helper"]["path"] + '", 0x08010000',
                    'verifybin "' + value["helper"]["path"] + '", 0x08010000', "r", "g", "sleep 2500", "qc"]
        with command_file.open("x", encoding="ascii", newline="\n") as stream:
            stream.write("\n".join(commands) + "\n")
        m.c.host_presence()
        journal.emit("action", id="restore-helper-flash", status="started", command_file=b.record(command_file))
        result["flash_started"] = True
        old.b.command("flash", [str(m.c.JLINK / "JLink.exe"), "-Device", "AT32F435RGT7", "-If", "SWD", "-Speed", "1000",
            "-USB", "123456", "-AutoConnect", "1", "-ExitOnError", "1", "-NoGui", "1", "-SettingsFile",
            str(directory / "flash-settings.jlink"), "-Log", str(directory / "flash-sdk.log"), "-CommandFile", str(command_file)], timeout=180)
        b.require((directory / "flash.log").read_text(encoding="utf-8", errors="replace").count("Verify successful.") == 1,
                  "J-Link VerifyBin result missing")
        journal.emit("action", id="restore-helper-flash", status="completed")
        evidence = old.Evidence(journal, "helper")
        link = old.Link(evidence, writable=True)
        link.connect()
        result["helper_readback"] = link.image(helper)
        result["helper_boot"] = old.verify_boot(link, evidence, boot)
        address = value["mailbox"]
        deadline, ready = time.monotonic() + 30, b""
        while time.monotonic() < deadline:
            ready = region(address, 640)
            if m.u32(ready[:4]) == MAGIC and mailbox(ready, expected)[2] in (1, 3, 4, 5):
                break
            time.sleep(.1)
        evidence.save("ready.bin", ready)
        validate_ready(ready, expected, old.arbitrate)
        evidence.save("eeprom-before.bin", ready[64:320])
        link.ram_writes = [(address + 20, address + 28)]
        journal.emit("action", id="request-verified-rollback", status="started")
        result["command_started"] = True
        old.issue_once(link, address)
        deadline, committed = time.monotonic() + 30, b""
        while time.monotonic() < deadline:
            committed = region(address, 640)
            if mailbox(committed, expected)[2] in (3, 4, 5):
                break
            time.sleep(.1)
        evidence.save("committed.bin", committed)
        result["bcb_transaction"] = validate_committed(ready, committed, expected, old.arbitrate)
        evidence.save("eeprom-after.bin", committed[320:576])
        clean = region(0x90300000, 4096)
        evidence.save("staging-journal.bin", clean)
        b.require(clean == b"\xff" * 4096, "journal erase verification failed")
        journal.emit("action", id="request-verified-rollback", status="completed", **result["bcb_transaction"])
        final = old.Evidence(journal, "final")
        result["rollback_reset_started"] = True
        journal.emit("action", id="ordinary-boot-rollback", status="started")
        reset, go = link.sdk.JLINKARM_Reset, link.sdk.JLINKARM_Go
        reset.argtypes, reset.restype, go.argtypes, go.restype = [], None, [], None
        reset()
        go()
        link.ram_writes = []
        result["final_time"] = old.wait_original_app(link, baseline)
        channel = old.UpOnly(link, final)
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            channel.pump()
            if any(m.passive.confirmation(line, 30208) for line in channel.lines):
                break
            time.sleep(.05)
        b.require(any(m.passive.confirmation(line, 30208) for line in channel.lines), "fresh baseline BCB confirmation missing")
        result["final_bcb_confirmation"] = old.CONFIRMED
        data = region(m.c.APP, len(baseline))
        result["final_image"] = final.save("image.bin", data)
        b.require(data == baseline, "final raw image is not the exact diagnostic baseline")
        result["final_identity"] = m.c.image_identity(data)
        result["final_boot"] = old.verify_boot(link, final, boot)
        clean = region(0x90300000, 4096)
        result["final_journal"] = final.save("staging-journal.bin", clean)
        b.require(clean == b"\xff" * 4096 and region(0x90100000, 32) == header, "final journal/backup metadata changed")
        result["sd_ready"] = region(symbols["sd_ready"], 1)[0]
        b.require(result["sd_ready"] == 1, "baseline restored but SD requires physical recovery; do not repeat flash")
        link.running()
        journal.emit("action", id="ordinary-boot-rollback", status="completed", version=30208)
        result["result"] = "RESTORED_328_VERIFIED"
    except Exception as error:
        result["error"] = type(error).__name__ + ": " + str(error)
        journal.emit("error", error=result["error"])
    finally:
        if channel:
            channel.raw.close()
        if link:
            link.close()
        result.update(ended=b.now(), reader_closed=not link or not link.opened, native_history_after=m.c.record(m.c.MRU))
        b.io.write_json(b.ROOT, directory / "result.json", result)
        journal.stream.close()
    b.require(result["result"] == "RESTORED_328_VERIFIED", result.get("error", "restoration incomplete"))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("prepare",))
    parser.parse_args()
    b.require(Path.cwd().resolve() == b.ROOT and sys.flags.isolated and sys.flags.no_site and
              sys.dont_write_bytecode, "isolated explicit project execution required")
    prepare()
