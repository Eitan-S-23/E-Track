#!/usr/bin/env python3
"""Run one bounded, read-only P2-6 RTT/GDB transport qualification."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys
import time


THIS_DIR = Path(__file__).resolve().parent
if str(THIS_DIR) not in sys.path:
    sys.path.insert(0, str(THIS_DIR))

import p2_6_rtt_ota_driver as driver


QUALIFICATION_ID = "P2-6-TR-R1"
SESSION_COUNT = 2
DEFAULT_LOG_DIR = driver.ROOT / ".cache" / "p2-6-transport-r1" / "logs"
DEFAULT_TMP_DIR = driver.ROOT / ".cache" / "p2-6-transport-r1" / "tmp"
SCB_VTOR_ADDRESS = driver.SCB_VTOR_ADDRESS
SCB_CFSR_ADDRESS = driver.SCB_CFSR_ADDRESS
EXPECTED_VTOR = driver.EXPECTED_VTOR


class QualificationError(driver.DriverError):
    pass


def required_symbols(
    nm: Path, elf: Path, layout: dict[str, int]
) -> dict[str, int]:
    table = driver.read_symbol_table(nm, elf)
    names = [
        driver.SD_READY_SYMBOL,
        driver.RTT_SYMBOL,
        driver.OVERLAY_OWNER_SYMBOL,
        driver.OVERLAY_WORKSPACE_SYMBOL,
    ]
    selected = driver.require_symbols(table, names)
    if selected[driver.OVERLAY_WORKSPACE_SYMBOL] != layout["OTA_OVERLAY_ORIGIN"]:
        raise QualificationError(
            "overlay symbol does not match the frozen transport layout: "
            f"0x{selected[driver.OVERLAY_WORKSPACE_SYMBOL]:08X}"
        )
    return selected


def transport_gdb_command_file(
    path: Path,
    elf: Path,
    symbols: dict[str, int],
    expected_header: bytes,
    layout: dict[str, int],
    session_number: int,
) -> None:
    if session_number < 1 or session_number > SESSION_COUNT:
        raise QualificationError(f"invalid transport session number: {session_number}")
    label = f"tr_session_{session_number}"
    header_address = layout["OTA_APP_ORIGIN"] + layout["OTA_FW_HEADER_OFFSET"]
    rtt = symbols[driver.RTT_SYMBOL]
    sd_ready = symbols[driver.SD_READY_SYMBOL]
    owner = symbols[driver.OVERLAY_OWNER_SYMBOL]
    lines = [
        *driver.gdb_prologue_lines(elf),
        f"target remote 127.0.0.1:{driver.GDB_PORT}",
        "monitor halt",
        "set $p2_6_transport_pc = (unsigned int)$pc",
        f'printf "P2_6_TR attached_stopped session={session_number} pc=0x%08x\\n", $p2_6_transport_pc',
        *driver.firmware_header_check_lines(
            header_address, expected_header, f"{label}_fw", 10
        ),
        f"set $rtt_{label} = (unsigned char*)0x{rtt:08x}",
        f"if $rtt_{label}[0] != 0x53 || $rtt_{label}[1] != 0x45 || $rtt_{label}[2] != 0x47 || $rtt_{label}[3] != 0x47 || $rtt_{label}[4] != 0x45 || $rtt_{label}[5] != 0x52 || $rtt_{label}[6] != 0x20 || $rtt_{label}[7] != 0x52 || $rtt_{label}[8] != 0x54 || $rtt_{label}[9] != 0x54",
        f'  printf "P2_6_TR ERROR session={session_number} rtt_signature\\n"',
        "  quit 11",
        "end",
        f"set $sd_{label} = *(unsigned char*)0x{sd_ready:08x}",
        f"set $vtor_{label} = *(unsigned int*)0x{SCB_VTOR_ADDRESS:08x}",
        f"set $cfsr_{label} = *(unsigned int*)0x{SCB_CFSR_ADDRESS:08x}",
        f"set $owner_{label} = *(unsigned char*)0x{owner:08x}",
        f"if $sd_{label} != 1 || $vtor_{label} != 0x{EXPECTED_VTOR:08x} || $cfsr_{label} != 0 || $owner_{label} != 0",
        f'  printf "P2_6_TR ERROR session={session_number} sd=%u vtor=0x%08x cfsr=0x%08x owner=%u\\n", $sd_{label}, $vtor_{label}, $cfsr_{label}, $owner_{label}',
        "  quit 12",
        "end",
        f'printf "P2_6_TR STATE_PASS session={session_number} sd=%u vtor=0x%08x cfsr=0x%08x owner=%u\\n", $sd_{label}, $vtor_{label}, $cfsr_{label}, $owner_{label}',
        f'printf "P2_6_TR PASS session={session_number}\\n"',
        "detach",
        "quit",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="ascii")


def audit_read_only_script(path: Path) -> None:
    text = path.read_text(encoding="ascii")
    lowered = text.lower()
    forbidden = (
        "lv_fs_open",
        "lv_fs_write",
        "lv_fs_close",
        "loadfile",
        "loadbin",
        "verifybin",
        "restore ",
        "dump binary memory",
        "monitor reset",
        "monitor go",
        "flash",
        "continue",
        "call ",
    )
    hits = [token for token in forbidden if token in lowered]
    if hits:
        raise QualificationError(
            f"read-only transport script contains forbidden operations: {', '.join(hits)}"
        )
    if re.search(r"(?im)^\s*set\s+\*", text):
        raise QualificationError("read-only transport script contains a target memory write")
    if re.search(r"(?im)^\s*monitor\s+(reset|go|load)", text):
        raise QualificationError("read-only transport script contains a target control write")


def marker_counts(text: str, session_number: int) -> dict[str, int]:
    return {
        "attached": text.count(f"P2_6_TR attached_stopped session={session_number}"),
        "identity": text.count(
            f"P2_6_IDENTITY PASS label=tr_session_{session_number}_fw"
        ),
        "state": text.count(f"P2_6_TR STATE_PASS session={session_number}"),
        "pass": text.count(f"P2_6_TR PASS session={session_number}"),
    }


def session_pass(
    session: dict[str, object],
    gdb_text: str,
    server_text: str,
    session_number: int,
) -> bool:
    markers = marker_counts(gdb_text, session_number)
    return (
        session["transport_classification"] == "PASS"
        and session["server_ready"] is True
        and session["rtt_connected"] is True
        and session["gdb_started"] is True
        and session["gdb_exit_code"] == 0
        and session["server_process_exited"] is True
        and session["server_natural_exit"] is True
        and session["server_terminate_sent"] is False
        and session["server_kill_sent"] is False
        and session["capture_stopped"] is True
        and session["ports_closed"] is True
        and session["session_error"] is None
        and driver.SERVER_READY_MARKER in server_text
        and markers == {"attached": 1, "identity": 1, "state": 1, "pass": 1}
    )


def file_hash_or_none(path: Path) -> str | None:
    return driver.sha256_file(path) if path.exists() else None


def run_qualification(args: argparse.Namespace) -> int:
    build = driver.require_inside_root(Path(args.build), "build directory")
    log_dir = driver.require_inside_root(Path(args.log_dir), "log directory")
    tmp_dir = driver.require_inside_root(Path(args.tmp_dir), "temporary directory")
    device_image = driver.require_inside_root(Path(args.device_image), "device image")
    prefix = args.output_prefix
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", prefix):
        raise QualificationError(f"invalid output prefix: {prefix!r}")
    if args.inter_session_delay < 0:
        raise QualificationError("inter-session delay must be non-negative")
    log_dir.mkdir(parents=True, exist_ok=True)
    tmp_dir.mkdir(parents=True, exist_ok=True)

    elf, map_path = driver.require_frozen_build(build)
    expected_header, layout = driver.load_frozen_device_header(device_image)
    gdb = Path(args.gdb or shutil.which("arm-none-eabi-gdb") or "")
    nm = Path(args.nm or shutil.which("arm-none-eabi-nm") or "")
    if not gdb.is_file() or not nm.is_file():
        raise QualificationError("arm-none-eabi-gdb/nm is unavailable")
    selected = required_symbols(nm, elf, layout)

    scripts = [tmp_dir / f"{prefix}-session-{i}.gdb" for i in range(1, SESSION_COUNT + 1)]
    for script in scripts:
        driver.require_inside_root(script, "GDB script")
        if script.exists():
            raise QualificationError(f"refusing to overwrite existing output: {script}")
    result_path = log_dir / f"{prefix}-result.json"
    driver.require_inside_root(result_path, "qualification result")
    if result_path.exists():
        raise QualificationError(f"refusing to overwrite existing output: {result_path}")

    for index, script in enumerate(scripts, 1):
        transport_gdb_command_file(
            script, elf, selected, expected_header, layout, index
        )
        audit_read_only_script(script)

    base_result: dict[str, object] = {
        "schema": "p2-6-rtt-transport-qualification-v1",
        "qualification_id": QUALIFICATION_ID,
        "execution": 1,
        "session_limit": SESSION_COUNT,
        "hardware_started": False,
        "build": str(build),
        "elf": str(elf),
        "elf_sha256": driver.sha256_file(elf),
        "map": str(map_path),
        "map_sha256": driver.sha256_file(map_path),
        "device_image": str(device_image),
        "device_image_sha256": driver.sha256_file(device_image),
        "device_header_sha256": hashlib.sha256(expected_header).hexdigest().upper(),
        "scripts": [str(script) for script in scripts],
        "script_sha256": {str(i): driver.sha256_file(script) for i, script in enumerate(scripts, 1)},
        "sessions": [],
        "sessions_attempted": 0,
        "qualification_pass": False,
        "outside_repo_writes": [],
    }

    def write_result(value: dict[str, object]) -> None:
        result_path.write_text(
            json.dumps(value, indent=2, ensure_ascii=True) + "\n", encoding="ascii"
        )

    write_result(base_result)
    sessions: list[dict[str, object]] = []
    for index in range(1, SESSION_COUNT + 1):
        session_prefix = f"{prefix}-session-{index}"
        rtt_log = log_dir / f"{session_prefix}-rtt.raw.log"
        gdb_log = log_dir / f"{session_prefix}-gdb.log"
        server_log = log_dir / f"{session_prefix}-jlink-server.log"
        for output in (rtt_log, gdb_log, server_log):
            driver.require_inside_root(output, "qualification log")
            if output.exists():
                raise QualificationError(f"refusing to overwrite existing output: {output}")
        session = driver.run_gdb_session(
            jlink_dir=Path(args.jlink_dir),
            gdb=gdb,
            gdb_script=scripts[index - 1],
            gdb_log=gdb_log,
            server_log=server_log,
            rtt_log=rtt_log,
            tmp_dir=tmp_dir,
            timeout=args.timeout,
            server_ready_timeout=args.server_ready_timeout,
            server_exit_timeout=args.server_exit_timeout,
        )
        gdb_text = gdb_log.read_text(encoding="utf-8", errors="replace") if gdb_log.exists() else ""
        server_text = server_log.read_text(encoding="utf-8", errors="replace") if server_log.exists() else ""
        markers = marker_counts(gdb_text, index)
        record = {
            "session_number": index,
            "session": session,
            "markers": markers,
            "session_pass": session_pass(session, gdb_text, server_text, index),
            "logs": {
                "rtt": str(rtt_log),
                "gdb": str(gdb_log),
                "server": str(server_log),
            },
            "sha256": {
                "rtt": file_hash_or_none(rtt_log),
                "gdb": file_hash_or_none(gdb_log),
                "server": file_hash_or_none(server_log),
            },
        }
        sessions.append(record)
        base_result["hardware_started"] = bool(
            base_result["hardware_started"] or session["server_started"]
        )
        base_result["sessions"] = sessions
        base_result["sessions_attempted"] = len(sessions)
        base_result["outside_repo_writes"] = (
            [driver.AUTHORIZED_SEGGER_WRITE]
            if base_result["hardware_started"]
            else []
        )
        base_result["qualification_pass"] = all(
            item["session_pass"] for item in sessions
        ) and len(sessions) == SESSION_COUNT
        write_result(base_result)
        if not record["session_pass"]:
            break
        if index < SESSION_COUNT:
            time.sleep(args.inter_session_delay)

    if not base_result["qualification_pass"]:
        raise QualificationError(
            f"{QUALIFICATION_ID} qualification failed after "
            f"{base_result['sessions_attempted']}/{SESSION_COUNT} session(s); see {result_path}"
        )
    print(json.dumps(base_result, indent=2, ensure_ascii=True))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-prefix", default="p2-6-tr-r1-hw-1")
    parser.add_argument("--build", default=str(driver.DEFAULT_BUILD))
    parser.add_argument("--device-image", default=str(driver.DEFAULT_DEVICE_IMAGE))
    parser.add_argument("--log-dir", default=str(DEFAULT_LOG_DIR))
    parser.add_argument("--tmp-dir", default=str(DEFAULT_TMP_DIR))
    parser.add_argument("--jlink-dir", default=str(driver.DEFAULT_JLINK_DIR))
    parser.add_argument("--gdb")
    parser.add_argument("--nm")
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--server-ready-timeout", type=float, default=45.0)
    parser.add_argument(
        "--server-exit-timeout",
        type=float,
        default=driver.SERVER_NATURAL_EXIT_TIMEOUT,
    )
    parser.add_argument("--inter-session-delay", type=float, default=5.0)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        return run_qualification(args)
    except driver.DriverError as exc:
        print(f"P2_6_RTT_TRANSPORT_QUALIFIER=FAIL {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
