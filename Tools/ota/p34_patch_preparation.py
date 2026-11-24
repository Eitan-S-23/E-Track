"""Offline-only preparation of the P34-INSTALL-03 receiver and matching assets.

No device, service, publication, or Git mutation entry point is provided.
Existing source/build/package evidence is write-once and never regenerated.
"""
from __future__ import annotations

import argparse
import ast
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import struct
import sys
import types
import p34_historical_inputs as historical

ROOT = Path(__file__).resolve().parents[2]
AREA = ROOT / ".cache/p34-patch-next"
FW = ROOT / ".cache/p34pc/f"
BUILD = ROOT / ".cache/p34pc/b"
BASE = ROOT / ".cache/p34-session/n04/fw"
N04 = ROOT / ".cache/p34-session/n04/firmware"
Y_ASSETS = ROOT / ".cache/p34-session/n04/assets/y/result.json"
Y_RESULT = ROOT / ".cache/p34-session/runs/20260927T162548-11400/analysis/1790527302778574900/result.json"
HOST_TESTS = ROOT / ".cache/p34-session/patch-coalesce/r1/result.json"
ARM_TESTS = ROOT / ".cache/p34-session/patch-coalesce/arm-r1/result.json"
OVERLAY = ("Libraries/OTA/ota_patch.c", "Libraries/OTA/ota_patch.h")
AA, AB = 30223, 30224
AA_NAME, AB_NAME = "3.2.23-p34c", "3.2.24-p34c"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


common = load("p34_patch_build_common", ROOT / "Tools/ota/p34_install_candidate.py")
common.AREA, common.FW, common.BUILD = AREA / "firmware", FW, BUILD
require, checked, record, read, save = common.require, common.checked, common.record, common.read, common.save


def verify_records(items):
    for item in items:
        historical.resolve(item)


def raw(path, data):
    path = checked(path)
    checked(path.parent).mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    return record(path)


def producer_snapshot(label):
    return raw(common.AREA / "sources" / (label + ".py"), Path(__file__).read_bytes())


def input_evidence():
    tests, arm = read(HOST_TESTS), read(ARM_TESTS)
    require(tests["result"] == "HOST_PASS" and tests["failures"] == tests["errors"] == tests["skipped"] == 0
            and tests["inputs_unchanged"] and tests["hardware"] is False, "E95 decoder validation required")
    require(arm["result"] == "ARM_OBJECT_PASS" and arm["inputs_unchanged"] and arm["hardware"] is False,
            "E96 object validation required")
    verify_records(tests["inputs"] + tests["binaries"])
    y, result, build = read(Y_ASSETS), read(Y_RESULT), read(N04 / "build.json")
    require(y["target_identity"]["version_code"] == 30221 and result["result"] == "FULL_INSTALL_VERIFIED",
            "original completed Y required")
    closure_records = [value for value in result.values() if isinstance(value, dict) and
                       str(value.get("path", "")).replace("\\", "/").endswith("/installed-mcu/closure.json")]
    require(len(closure_records) == 1, "Y lacks its original MCU closure")
    verify_records(closure_records)
    closure = read(closure_records[0]["path"])
    require(closure["retained_verified"] and closure["reader_closed"] and
            closure["final_state"]["bcb_state"] == 4 and closure["final_state"]["confirm_done"] == 1,
            "Y closure was not confirmed")
    verify_records(list(closure["final_identity"].values()) + [y["target"], y["target_bindings"]["whole_boot"]])
    require(closure["final_identity"]["app"]["sha256"] == y["target"]["sha256"] and
            closure["final_identity"]["boot"]["sha256"] == y["target_bindings"]["whole_boot"]["sha256"],
            "retained device and source-lineage identities disagree")
    require(build["result"] == "N04_APP_BUILD_PASS" and build["errors"] == 0 and build["n04_enabled"]
            and not build["boot_built"], "verified N04 App build required")
    verify_records([build["source_manifest"], *build["artifacts"]])
    manifest = read(build["source_manifest"]["path"])
    require(Path(manifest["fw"]) == BASE, "wrong N04 source lineage")
    verify_records(manifest["candidate_files"])
    n04_binary = next(item for item in build["artifacts"] if Path(item["path"]).suffix == ".bin")
    equivalent = load("p34_patch_executable", ROOT / "Tools/ota/p34_full_assets.py").same_executable
    equivalent(Path(n04_binary["path"]).read_bytes(), Path(y["target"]["path"]).read_bytes())
    return manifest, [record(path) for path in (HOST_TESTS, ARM_TESTS, Y_ASSETS, Y_RESULT,
        N04 / "build.json", Path(build["source_manifest"]["path"]),
        ROOT / "Tools/ota/p34_install_candidate.py", ROOT / "Tools/ota/p34_full_assets.py",
        ROOT / ".agents/skills/e-track-flutter-debug/scripts/host_io.py")] + closure_records


def verify_source():
    value = read(common.AREA / "source.json")
    require(value["result"] == "PATCH_SOURCE_READY" and value["overlay"] == list(OVERLAY) and
            value["base"] == str(BASE) and value["fw"] == str(FW) and value["build"] == str(BUILD),
            "source preparation scope changed")
    verify_records(value["inputs"] + value["originals"] + value["files"])
    actual = {path.relative_to(FW).as_posix() for path in FW.rglob("*") if path.is_file()}
    require(actual == {Path(item["path"]).relative_to(FW).as_posix() for item in value["files"]},
            "candidate source file set changed")
    return value


def prepare_source():
    if (common.AREA / "source.json").exists():
        return dict(result=verify_source()["result"], reused=True)
    for path in (common.AREA, FW, BUILD):
        checked(path)
        require(not path.exists(), "preserve partial source/build outputs: " + str(path))
    manifest, inputs = input_evidence()
    originals = manifest["candidate_files"]
    require({Path(item["path"]).relative_to(BASE).as_posix() for item in originals} ==
            {path.relative_to(BASE).as_posix() for path in BASE.rglob("*") if path.is_file()},
            "N04 source tree differs from its frozen manifest")
    for item in originals:
        checked(FW / Path(item["path"]).relative_to(BASE))
    for name in ("source.json", "intent.json", "failed-source.json", "sources/prepare.py"):
        checked(common.AREA / name)
    inputs += [record(ROOT / name) for name in OVERLAY]
    environment, paths = common.environment()
    inputs.append(producer_snapshot("prepare"))
    save(common.AREA / "intent.json", dict(inputs=inputs, environment=paths, base=str(BASE),
        fw=str(FW), build=str(BUILD), overlay=OVERLAY, hardware=False))
    try:
        for item in originals:
            relative = Path(item["path"]).relative_to(BASE)
            target = checked(FW / relative)
            checked(target.parent).mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / relative if relative.as_posix() in OVERLAY else item["path"], target)
        files = [record(FW / Path(item["path"]).relative_to(BASE)) for item in originals]
        changed = [Path(before["path"]).relative_to(BASE).as_posix()
                   for before, after in zip(originals, files) if before["sha256"] != after["sha256"]]
        require(set(changed) == set(OVERLAY), "unexpected inherited source delta")
        verify_records(inputs + originals)
        save(common.AREA / "source.json", dict(result="PATCH_SOURCE_READY", base=str(BASE), fw=str(FW),
            build=str(BUILD), overlay=list(OVERLAY), inputs=inputs, originals=originals, files=files,
            historical_device="Y 30221; no fresh admission", hardware=False))
        return dict(result="PATCH_SOURCE_READY", files=len(files), overlay=changed, reused=False)
    except Exception as error:
        save(common.AREA / "failed-source.json", dict(error=str(error), preserve_partial_outputs=True))
        raise


def build_command(original):
    args = list(original)
    require(args.count("-S") == args.count("-B") == 1, "ambiguous original CMake command")
    args[args.index("-S") + 1] = str(FW / "MDK-ARM_F435/cmake-generated")
    args[args.index("-B") + 1] = str(BUILD)
    require(not any(arg.startswith("-DCMAKE_C_FLAGS") for arg in args), "unexpected inherited C flags")
    cxx = [index for index, arg in enumerate(args) if arg.startswith("-DCMAKE_CXX_FLAGS:STRING=")]
    install = [index for index, arg in enumerate(args) if arg.startswith("-DCMAKE_INSTALL_PREFIX=")]
    require(len(cxx) == len(install) == 1 and "-DCONFIG_OTA_INSTALL_QE_REUSE=1" in args[cxx[0]] and
            "-DCONFIG_OTA_INSTALL_PROFILE=1" in args[cxx[0]], "inherited N04 flags missing")
    args[cxx[0]] += " -DOTA_PATCH_COALESCE_WRITES=1"
    args[install[0]] = "-DCMAKE_INSTALL_PREFIX=" + str(common.AREA / "install")
    args.append("-DCMAKE_C_FLAGS:STRING=-DOTA_PATCH_COALESCE_WRITES=1")
    return args


def sections_from_objdump(text):
    result = {}
    for line in text.splitlines():
        match = re.match(r"^\s*\d+\s+(\S+)\s+([0-9a-fA-F]+)\s+([0-9a-fA-F]+)\s+([0-9a-fA-F]+)\s+", line)
        if match:
            name, size, address, load_address = match.groups()
            require(name not in result, "duplicate ELF section")
            result[name] = dict(bytes=int(size, 16), address=int(address, 16), load_address=int(load_address, 16))
    return result


def layout_constants(fw=FW):
    header = (fw / "Libraries/OTA/ota_layout.h").read_text(encoding="utf-8")
    names = ("OTA_APP_ORIGIN", "OTA_APP_LENGTH", "OTA_FW_HEADER_OFFSET", "OTA_FW_HEADER_SIZE",
             "OTA_RAM_ORIGIN", "OTA_RAM_LENGTH", "OTA_OVERLAY_ORIGIN", "OTA_OVERLAY_LENGTH",
             "OTA_OVERLAY_WORKSPACE_LENGTH", "OTA_VECTOR_MAX")
    result = {}
    for name in names:
        values = re.findall(r"^#define\s+" + name + r"\s+(0x[0-9a-fA-F]+|\d+)\s*$", header, re.M)
        require(len(values) == 1, "ambiguous frozen layout constant: " + name)
        result[name] = int(values[0], 0)
    linker = (fw / "cmake/linker/x-track-app-gcc.ld.S").read_text(encoding="utf-8")
    for name in ("OTA_STACK_RESERVE", "OTA_STACK_GUARD_SIZE"):
        values = re.findall(r"^" + name + r"\s*=\s*(0x[0-9a-fA-F]+|\d+);\s*$", linker, re.M)
        require(len(values) == 1, "ambiguous frozen linker constant: " + name)
        result[name] = int(values[0], 0)
    return result


def memory_checks(sections, constants=None):
    constants = layout_constants() if constants is None else constants
    required = (".isr_vector", ".fw_header", ".ota_overlay", ".ota_stack", ".ota_stack_guard", "._user_heap_stack")
    require(all(name in sections for name in required), "required final linker sections absent")
    require(sections[".isr_vector"]["address"] == constants["OTA_APP_ORIGIN"] and
            sections[".isr_vector"]["bytes"] <= constants["OTA_VECTOR_MAX"] and
            sections[".fw_header"]["address"] == constants["OTA_APP_ORIGIN"] + constants["OTA_FW_HEADER_OFFSET"] and
            sections[".fw_header"]["bytes"] == constants["OTA_FW_HEADER_SIZE"],
            "App/header flash placement changed")
    overlay, stack, guard = (sections[name] for name in (".ota_overlay", ".ota_stack", ".ota_stack_guard"))
    require(overlay["address"] == constants["OTA_OVERLAY_ORIGIN"] and
            overlay["bytes"] == constants["OTA_OVERLAY_WORKSPACE_LENGTH"],
            "40 KiB OTA overlay changed")
    require(stack["bytes"] == constants["OTA_STACK_RESERVE"] and
            guard["bytes"] == constants["OTA_STACK_GUARD_SIZE"] and
            stack["address"] + stack["bytes"] == constants["OTA_RAM_ORIGIN"] + constants["OTA_RAM_LENGTH"] and
            guard["address"] + guard["bytes"] == stack["address"], "stack/guard layout changed")
    heap = sections["._user_heap_stack"]
    require(heap["address"] + heap["bytes"] <= guard["address"], "heap crosses stack guard")
    return dict(overlay=overlay, stack=stack, guard=guard, heap=heap, constants=constants,
                heap_to_guard_bytes=guard["address"] - heap["address"],
                heap_after_link_reserve_bytes=guard["address"] - heap["address"] - heap["bytes"],
                runtime_stack_high_water=False)


def original_command(name):
    value = read(common.AREA / "logs" / (name + ".json"))
    require(value["exit"] == 0 and value["timeout"] is False, "original command failed: " + name)
    verify_records([value["stdout"], value["stderr"]])
    return b"".join(Path(value[key]["path"]).read_bytes() for key in ("stdout", "stderr"))


def capture_limits(text):
    limits = {}
    for field in ("defaultMaxBytes", "defaultMaxPendingBytes", "defaultMaxStoreBytes", "maxLineBytes", "_batchBytes"):
        matches = re.findall(r"static const " + field + r" = (\d+(?:\s*\*\s*\d+)*);", text)
        require(len(matches) == 1, "capture limit missing/ambiguous: " + field)
        value = 1
        for factor in matches[0].split("*"):
            value *= int(factor)
        require(value > 0, "invalid capture limit")
        limits[field] = value
    slots = re.findall(r"directories >= (\d+)", text)
    require(len(slots) == 1 and int(slots[0]) > 0, "capture slot limit missing/ambiguous")
    limits["directories"] = int(slots[0])
    return limits


def capture_projection(snapshot_bytes, records, segments, package_bytes, limits):
    require(all(type(value) is int and value > 0 for value in (snapshot_bytes, records, segments, package_bytes)),
            "positive original capture counts required")
    target_segments = (package_bytes + 127) // 128
    estimate = (snapshot_bytes * target_segments + segments - 1) // segments
    return dict(package_bytes=package_bytes, data_segments=target_segments,
        durable_blocks=(package_bytes + 4095) // 4096,
        estimated_snapshot_bytes=estimate, estimated_records=(records * target_segments + segments - 1) // segments,
        estimated_two_copy_bytes=2 * (estimate + 8192),
        capture_limit_bytes=limits["defaultMaxBytes"], pending_limit_bytes=limits["defaultMaxPendingBytes"],
        reservation_bytes=limits["defaultMaxBytes"] + 8192,
        estimated_below_capture_limit=estimate < limits["defaultMaxBytes"],
        estimate_only=True, proves_pending_queue_capacity=False, proves_free_phone_storage=False)


def warning_lines(text, source):
    return sorted(line.replace("\\", "/").replace(source.as_posix(), "<FW>")
                  .replace(source.as_posix().replace(":", "_"), "<FW>")
                  for line in text.splitlines() if re.search(r"\bwarning:", line))


def verified_git_blob(data, expected):
    require(re.fullmatch(r"[0-9a-f]{40}", expected) is not None, "invalid Git blob identity")
    for candidate in (data, data.replace(b"\r\n", b"\n")):
        actual = hashlib.sha1(b"blob " + str(len(candidate)).encode("ascii") + b"\0" + candidate).hexdigest()
        if actual == expected:
            return candidate
    raise RuntimeError("APK file does not match its committed Git blob")


def observation_plan(*, reconcile=False):
    """Freeze source-verified capacity estimates and the existing finite bounds."""
    original = AREA / "observation"
    if reconcile:
        require(read(original / "failed.json")["error"] == "host command failed: source-ota_firmware_latest.dart",
                "observation reconciliation is limited to the preserved missing blob")
    out = checked(AREA / ("observation-r2" if reconcile else "observation"))
    require(not out.exists(), "preserve completed/partial observation preparation")
    for name in ("result.json", "failed.json", "sources/producer.py", "apk-source", "logs"):
        checked(out / name)
    before = common.AREA
    try:
        common.AREA = out
        env, paths = common.environment()
        inputs = [raw(out / "sources/producer.py", Path(__file__).read_bytes())]
        if reconcile:
            inputs.append(record(original / "failed.json"))
        apk_path = ROOT / ".cache/p34-next/validation/apk.json"
        apk = read(apk_path)
        verify_records([apk["apk"], *apk["host_reports"]])
        require(apk["sha"] == apk["metadata"]["commit"] == "aea62c6490a529a47f74dde86669dc3e3c7605ff" and
                apk["apk"]["sha256"] == "ac42662d5efb8aebc6eccc56d10a0a82a85e4c5506bdbcded709965e241b3408",
                "prepared observation does not use the verified APK")
        inputs += [record(apk_path), apk["apk"], *apk["host_reports"]]
        source_root = ROOT / ".cache/p34-next/validation/src"
        apk_sources = {}
        source_bindings = {}
        for name in ("ota_observation_log.dart", "ota_experiment_config.dart", "ota_firmware_latest.dart"):
            relative = "app/bluetooth_flutter_Trace/lib/ota/" + name
            local = source_root / relative
            if reconcile:
                command_path = original / "logs" / ("source-" + name + ".json")
                command = read(command_path)
                receipts = [record(command_path), command["stdout"], command["stderr"]]
                verify_records(receipts)
                inputs += receipts
                require(command["args"][-1] == apk["sha"] + ":" + relative and not command["timeout"],
                        "original APK source query is not bound to this commit/path")
                if command["exit"] == 0:
                    require(command["stderr"]["bytes"] == 0, "original Git source query has stderr")
                    data = Path(command["stdout"]["path"]).read_bytes()
                    source_bindings[name] = "REUSED original git show"
                else:
                    require(name == "ota_firmware_latest.dart" and command["exit"] == 128 and
                            "fatal: bad object " in Path(command["stderr"]["path"]).read_text(encoding="utf-8"),
                            "unclassified Git failure cannot use blob reconciliation")
                    blob = common.run("tree-" + name, ["git", "--no-optional-locks", "-c", "core.fsmonitor=false",
                        "-C", source_root, "ls-tree", "--format=%(objectname)", apk["sha"], "--", relative], ROOT, env, 20).decode().strip()
                    data = verified_git_blob(local.read_bytes(), blob)
                    source_bindings[name] = dict(method="commit tree plus exact blob hash", blob=blob)
            else:
                data = common.run("source-" + name, ["git", "--no-optional-locks", "-c", "core.fsmonitor=false",
                    "-C", source_root, "show", apk["sha"] + ":" + relative], ROOT, env, 20)
                source_bindings[name] = "original git show"
            require(data.replace(b"\r\n", b"\n") == local.read_bytes().replace(b"\r\n", b"\n"),
                    "APK source checkout differs from its actual build commit")
            inputs.append(record(local))
            apk_sources[name] = raw(out / "apk-source" / name, data)
        limits = capture_limits(Path(apk_sources["ota_observation_log.dart"]["path"]).read_text(encoding="utf-8"))
        source = read(Y_RESULT)
        inputs += [record(Y_RESULT), source["inputs"]["snapshot"], source["inputs"]["health_before"],
                   source["inputs"]["health_after"]]
        verify_records(inputs)
        require(source["summary"]["outcome"] == "completed" and source["summary"]["rawSha256"] ==
                source["inputs"]["snapshot"]["sha256"], "capacity basis is not the original completed Y snapshot")
        projections = {str(size): capture_projection(source["inputs"]["snapshot"]["bytes"],
            source["summary"]["records"], source["full_metrics"]["transfer"]["segmentsUnique"], size, limits)
            for size in (1048576,)}
        warnings = []
        for area, fw in ((N04, BASE), (AREA / "firmware", FW)):
            text = ""
            for name in ("configure", "build"):
                command = read(area / "logs" / (name + ".json"))
                require(command["exit"] == 0 and command["timeout"] is False, "original build command incomplete")
                receipts = [record(area / "logs" / (name + ".json")), command["stdout"], command["stderr"]]
                verify_records(receipts)
                inputs += receipts
                text += "".join(Path(command[key]["path"]).read_text(encoding="utf-8") for key in ("stdout", "stderr"))
            warnings.append(warning_lines(text, fw))
        build = read(AREA / "firmware/build.json")
        require(len(warnings[0]) == read(N04 / "build.json")["warnings"] and len(warnings[1]) == build["warnings"],
                "warning count does not match original receipts")
        value = dict(result="PATCH_OBSERVATION_PREPARED", inputs=inputs, apk_sources=apk_sources,
            source_bindings=source_bindings, original_failure=record(original / "failed.json") if reconcile else None,
            environment=paths, limits=limits, projections=projections,
            warning_comparison=dict(original=len(warnings[0]), candidate=len(warnings[1]),
                same_normalized_diagnostics=warnings[0] == warnings[1],
                normalization="source root and path separator only; multiplicity retained"),
            physical_order=["P34-WAIT-01 original history or fixed-window diagnosis", "fresh Y/device/store admission",
                "Y-to-AA FULL bootstrap and actual raw/Boot confirmation", "ONE selected AA-to-AB PATCH alternative"],
            required_phases=["download", "BEGIN-to-END-ACK", "PATCH/FULL and backup restore cycles",
                "Boot residency", "reconnect and full raw identity"],
            no_replay_on_collector_failure=True, hardware=False, independent_acceptance=False,
            pressure_runtime_cost="UNKNOWN; two decode passes and base reads remain; host counts are not seconds",
            observation_bounds="Reuse the existing 900 s active, 2700 s native and 3900 s cell bounds; no silent extension",
            existing_apk_reused=True, current_device="Last verified Y; AA/AB not installed")
        save(out / "result.json", value)
        return {key: value[key] for key in ("result", "projections", "warning_comparison", "hardware")}
    except Exception as error:
        save(out / "failed.json", dict(error=str(error), preserve_partial_outputs=True, hardware=False))
        raise
    finally:
        common.AREA = before


def build_app(*, reconcile=False):
    source = verify_source()
    require(not (common.AREA / "build.json").exists(), "preserve completed build")
    if reconcile:
        require(BUILD.is_dir() and read(common.AREA / "failed-build.json")["error"] == "40 KiB OTA overlay changed",
                "reconciliation is limited to the recorded layout-address error")
    else:
        require(not BUILD.exists(), "preserve attempted build")
    failure = common.AREA / ("failed-reconcile.json" if reconcile else "failed-build.json")
    for path in (BUILD, common.AREA / "build.json", failure, common.AREA / "install"):
        checked(path)
    env, paths = common.environment()
    verifier = producer_snapshot("reconcile" if reconcile else "build")
    producer = record(common.AREA / "sources/build.py")
    original = read(N04 / "logs/configure.json")
    require(original["exit"] == 0 and not original["timeout"], "original configure did not complete")
    args = build_command(original["args"])
    try:
        if reconcile:
            log = original_command("configure") + original_command("build")
            size, symbols, sections_text = (original_command(name) for name in ("size", "symbols", "sections"))
            symbols = symbols.decode("utf-8")
        else:
            log = common.run("configure", args, FW, env, 300)
            log += common.run("build", [common.CMAKE, "--build", BUILD, "--target", "X_Track_App_GCC", "--parallel", "8"],
                              FW, env, 1800)
            elf = BUILD / "app-gcc/X-Track-App-GCC.elf"
            size = common.run("size", [common.ARM / "bin/arm-none-eabi-size.exe", "--format=berkeley", elf], FW, env, 30)
            symbols = common.run("symbols", [common.ARM / "bin/arm-none-eabi-nm.exe", "-S", elf], FW, env, 30).decode("utf-8")
            sections_text = common.run("sections", [common.ARM / "bin/arm-none-eabi-objdump.exe", "-h", elf], FW, env, 30)
        sections = sections_from_objdump(sections_text.decode("utf-8"))
        layout = memory_checks(sections)
        selected = common.selected_symbols(symbols)
        require(selected.get("g_p34_ble_profile", {}).get("bytes") == 336 and
                "qspi_xip_restore_checked" in selected and "_SEGGER_RTT" in selected,
                "N03/N04 instrumentation was lost")
        require(re.search(r"\b[tT] append_candidate_chunk\r?$", symbols, re.M) is not None,
                "coalescer did not reach the final ELF")
        commands = read(BUILD / "compile_commands.json")
        patch_commands = [item for item in commands if Path(item["file"]) == FW / OVERLAY[0] and
                          "X_Track_App_GCC.dir" in item["command"]]
        require(len(patch_commands) == 1 and "-DOTA_PATCH_COALESCE_WRITES=1" in patch_commands[0]["command"],
                "actual App compile did not enable coalescing")
        stack_files = [path for path in BUILD.rglob("*.su") if path.name == "ota_patch.c.su"]
        require(len(stack_files) == 1, "ambiguous patch compiler stack report")
        stack_text = stack_files[0].read_text(encoding="utf-8")
        frames = re.findall(r":ota_patch_apply\t(\d+)\tstatic\r?$", stack_text, re.M)
        require(len(frames) == 1, "patch own-frame report missing")
        raw_image = (BUILD / "app-gcc/X-Track-App-GCC.bin").read_bytes()
        require(0 < len(raw_image) <= 0xf0000 and b"P34INSTALL:" in raw_image, "invalid App size/diagnostics")
        require(not (BUILD / "boot/X-Track-Boot.bin").exists(), "unexpected Boot artifact")
        verify_source()
        artifacts = [dict(record(path), mtime_ns=path.stat().st_mtime_ns)
                     for path in sorted((BUILD / "app-gcc").glob("X-Track-App-GCC.*"))]
        save(common.AREA / "build.json", dict(result="PATCH_APP_BUILD_PASS", source=record(common.AREA / "source.json"),
            producer=producer, verifier=verifier, reused_original_build=reconcile,
            original_failure=record(common.AREA / "failed-build.json") if reconcile else None,
            original_configure=record(N04 / "logs/configure.json"), environment=paths,
            artifacts=artifacts, symbols=selected, sections=sections, layout=layout,
            patch_frame_bytes=int(frames[0]), patch_stack_report=record(stack_files[0]),
            warnings=len(re.findall(rb"\bwarning:", log)), errors=len(re.findall(rb"\berror:", log)),
            app_bytes=len(raw_image), size_output=size.decode("utf-8"), coalesce=True,
            boot_built=False, hardware=False, finalized=False, independent_acceptance=False,
            commands=[record(common.AREA / "logs" / (name + ".json")) for name in
                      ("configure", "build", "size", "symbols", "sections")]))
        return {key: read(common.AREA / "build.json")[key] for key in
                ("result", "warnings", "errors", "app_bytes", "patch_frame_bytes", "layout")}
    except Exception as error:
        save(failure, dict(error=str(error), preserve_partial_outputs=True,
                                                      do_not_rebuild_to_repair_analysis=True))
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("source", "build", "reconcile", "verify-source", "assets", "verify-assets", "observation", "observation-reconcile"))
    parser.add_argument("--root", required=True)
    args = parser.parse_args()
    require(Path(args.root) == ROOT and Path.cwd() == ROOT and sys.flags.isolated and
            sys.flags.no_site and sys.dont_write_bytecode, "isolated explicit project root required")
    if args.action in ("assets", "verify-assets"):
        sys.modules["p34_patch_preparation"] = sys.modules[__name__]
        assets = load("p34_patch_assets", ROOT / "Tools/ota/p34_patch_assets.py")
        value = assets.prepare() if args.action == "assets" else dict(result=assets.load()["result"], verified=True)
        print(json.dumps(value), flush=True)
        return
    action = {"source": prepare_source, "build": build_app, "reconcile": lambda: build_app(reconcile=True), "observation": observation_plan,
              "observation-reconcile": lambda: observation_plan(reconcile=True),
              "verify-source": verify_source}[args.action]
    value = action()
    print(json.dumps(value if args.action != "verify-source" else dict(result=value["result"], verified=True)), flush=True)


if __name__ == "__main__":
    main()
