#!/usr/bin/env python3
"""Drive the P2-6 SD OTA hardware flow through J-Link RTT/GDB.

The target control path is test-build only. It drives the existing
FirmwareUpdate page, while transport state, firmware identity, runtime state,
and output boundaries are checked fail-closed before product calls run.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import socket
import struct
import subprocess
import sys
import threading
import time


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BUILD = ROOT / ".cache" / "p2-6a-cmake-test-stack"
DEFAULT_LOG_DIR = ROOT / ".cache" / "p2-6-sd-r2" / "logs"
DEFAULT_TMP_DIR = ROOT / ".cache" / "p2-6-sd-r2" / "tmp"
DEFAULT_DEVICE_IMAGE = (
    ROOT
    / ".cache"
    / "p2-6-sd-ota"
    / "assets"
    / "X-Track-App-GCC-p2-6a-test-v2.8.0.finalized.bin"
)
DEFAULT_ELF_REL = Path("app-gcc") / "X-Track-App-GCC.elf"
DEFAULT_MAP_REL = Path("app-gcc") / "X-Track-App-GCC.map"
DEFAULT_JLINK_DIR = Path(r"C:\Users\SU\SEGGER\JLink_V818")
LAYOUT_HEADER = ROOT / "Libraries" / "OTA" / "ota_layout.h"

FROZEN_TEST_ELF_SHA256 = (
    "35BB2AB75C683FA9061C2A75F20F32DB20F4D9E731E1C4A90E8D7AD95076D019"
)
FROZEN_TEST_MAP_SHA256 = (
    "2446B401E1C7812BA9792FAA4D24D8875BC2529A2C9255854999942DA45D0C13"
)
FROZEN_V280_IMAGE_SHA256 = (
    "AB38A4E75D905D306AFC97EB476554AF6DE2144A8D4FCBFA9A80040AE569A5E5"
)
AUTHORIZED_SEGGER_WRITE = r"C:\Users\SU\AppData\Roaming\SEGGER\JLinkDLL.ini"

DEVICE = "AT32F435RGT7"
INTERFACE = "SWD"
SPEED_KHZ = 1000
GDB_PORT = 24361
SWO_PORT = 24362
RTT_PORT = 24363
MONITOR_PORT = 24364
SERVER_READY_MARKER = "Waiting for GDB connection..."

# The GDB server's RTT telnet channel was proven banner-only on this
# J-Link/board combination (R19 probe F1, 2026-08-29: zero payload bytes over
# the telnet port whether the core was halted or running), so measurement
# payloads are captured with the project's canonical reader JLinkRTTLogger in
# its own probe connection, two-phase: the first GDB session snapshots the RTT
# control block and the Up0 ring while halted, the host derives the pending
# inventory, the logger reads exactly that inventory and advances RdOff, and a
# short second GDB session verifies only the four-byte RdOff word changed.
RTT_LOGGER = Path(r"C:\Users\SU\SEGGER\JLink_V818\JLinkRTTLogger.exe")
RTT_CB_SIZE = 0xA8
RTT_CB_MAX_UP_OFFSET = 0x10
RTT_CB_MAX_DOWN_OFFSET = 0x14
RTT_CB_UP0_PBUFFER_OFFSET = 0x1C
RTT_CB_UP0_SIZE_OFFSET = 0x20
RTT_CB_UP0_WROFF_OFFSET = 0x24
RTT_CB_UP0_RDOFF_OFFSET = 0x28
RTT_CB_UP0_FLAGS_OFFSET = 0x2C
RTT_EXPECTED_MAX_UP_BUFFERS = 3
RTT_EXPECTED_MAX_DOWN_BUFFERS = 3
RTT_EXPECTED_UP0_SIZE = 1024
RTT_EXPECTED_UP0_FLAGS = 1
RTT_SIGNATURE = b"SEGGER RTT"

# Watchdog pause for halted GDB sessions (R18 root cause: the independent
# watchdog keeps counting while the core is halted and resets the chip after
# 10 s). Space-separated form only: the comma form is rejected by the server
# (R19 probe, 2026-08-29). Debug-domain register, not flash, lost on power
# cycle, does not change the image bytes or its SHA-256.
WDT_PAUSE_COMMAND = "monitor WriteU32 0xE0042008 0x00001000"

LOGGER_PAYLOAD_TIMEOUT = 10.0
LOGGER_SETTLE_SECONDS = 1.0
LOGGER_STOP_WAIT_SECONDS = 15.0
SERVER_NATURAL_EXIT_TIMEOUT = 10.0
SERVER_TERMINATE_TIMEOUT = 5.0
SERVER_KILL_TIMEOUT = 5.0

MANAGER_SYMBOL = "App_Init()::manager"
PAGE_VTABLE_SYMBOL = "vtable for Page::FirmwareUpdate"
PUSH_SYMBOL = "PageManager::Push(char const*, PageBase::Stash_t const*)"
ENTER_PATH_SYMBOL = "Page::FirmwareUpdate::EnterPath(char const*)"
SELECT_ROW_SYMBOL = "Page::FirmwareUpdate::SelectRow(unsigned char)"
START_IMPORT_SYMBOL = "Page::FirmwareUpdate::StartImport()"
FINISH_IMPORT_SYMBOL = "Page::FirmwareUpdate::FinishImport(bool)"
GET_BCB_SYMBOL = "HAL::OTA_GetBcbState()"
HAL_UPDATE_SYMBOL = "HAL::HAL_Update()"
STRCMP_SYMBOL = "strcmp"
SD_READY_SYMBOL = "SD_IsReady"
RTT_SYMBOL = "_SEGGER_RTT"
OVERLAY_OWNER_SYMBOL = "g_ota_overlay_owner"
OVERLAY_WORKSPACE_SYMBOL = "g_ota_overlay_workspace"

# Verified against the frozen test ELF disassembly and PageBase layout.
PAGE_CURRENT_OFFSET = 60
PAGE_STATE_OFFSET = 36
PAGE_STATE_DID_APPEAR = 3
PAGE_STATE_ACTIVITY = 4
FIRMWARE_UPDATE_ROWS_OFFSET = 0x146C
FIRMWARE_UPDATE_ROW_STRIDE = 312
FIRMWARE_UPDATE_ROW_PATH_OFFSET = 4
FIRMWARE_UPDATE_MODE_OFFSET = 0x34E4
MODE_BROWSER = 0
MODE_CONFIRM = 1
MODE_WORKING = 2
MODE_RESULT = 3
BCB_STATE_STAGED = 1
BCB_STATE_CONFIRMED = 4
OTA_OVERLAY_FREE = 0
SCB_VTOR_ADDRESS = 0xE000ED08
SCB_CFSR_ADDRESS = 0xE000ED28
EXPECTED_VTOR = 0x08010000

MEASUREMENT_RE = re.compile(
    r"^P2_6 kind=(?P<kind>FULL|PATCH|full|patch) result=(?P<result>-?\d+) "
    r"workspace_peak=(?P<workspace_peak>\d+) "
    r"arena_peak_observed=(?P<arena_peak_observed>\d+) "
    r"failed_request_size=(?P<failed_request_size>\d+) "
    r"stack_entry=(?P<stack_entry>\d+) stack_peak=(?P<stack_peak>\d+) "
    r"stack_total=(?P<stack_total>\d+) guard_entry=(?P<guard_entry>\d+) "
    r"guard_exit=(?P<guard_exit>\d+) sbrk_delta=(?P<sbrk_delta>\d+) "
    r"sbrk_peak=(?P<sbrk_peak>\d+) "
    r"tlsf_malloc_delta=(?P<tlsf_malloc_delta>\d+) "
    r"tlsf_realloc_delta=(?P<tlsf_realloc_delta>\d+) "
    r"tlsf_free_delta=(?P<tlsf_free_delta>\d+) "
    r"lv_free_entry=(?P<lv_free_entry>\d+) lv_free_exit=(?P<lv_free_exit>\d+) "
    r"lv_big_entry=(?P<lv_big_entry>\d+) lv_big_exit=(?P<lv_big_exit>\d+) "
    r"lv_frag_entry=(?P<lv_frag_entry>\d+) lv_frag_exit=(?P<lv_frag_exit>\d+) "
    r"lv_max_entry=(?P<lv_max_entry>\d+) lv_max_exit=(?P<lv_max_exit>\d+) "
    r"seq=(?P<seq>\d+) last_size=(?P<last_size>\d+) "
    r"last_ret=0x(?P<last_ret>[0-9A-Fa-f]+)$"
)


class DriverError(RuntimeError):
    pass


def inside_root(path: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(ROOT.resolve())
        return True
    except ValueError:
        return False


def require_inside_root(path: Path, label: str) -> Path:
    resolved = path.resolve(strict=False)
    if not inside_root(resolved):
        raise DriverError(f"{label} is outside the repository: {resolved}")
    return resolved


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def parse_layout_values() -> dict[str, int]:
    required = (
        "OTA_APP_ORIGIN",
        "OTA_FW_HEADER_OFFSET",
        "OTA_FW_HEADER_SIZE",
        "OTA_OVERLAY_ORIGIN",
        "OTA_OVERLAY_WORKSPACE_LENGTH",
    )
    text = LAYOUT_HEADER.read_text(encoding="ascii")
    values: dict[str, int] = {}
    for name in required:
        match = re.search(
            rf"^\s*#define\s+{re.escape(name)}\s+(0x[0-9A-Fa-f]+|\d+)\s*$",
            text,
            flags=re.MULTILINE,
        )
        if not match:
            raise DriverError(f"layout macro missing or non-literal: {name}")
        values[name] = int(match.group(1), 0)
    return values


def require_frozen_build(build: Path) -> tuple[Path, Path]:
    elf = build / DEFAULT_ELF_REL
    map_path = build / DEFAULT_MAP_REL
    if not elf.is_file() or not map_path.is_file():
        raise DriverError(f"missing frozen ELF/map under {build}")
    elf_hash = sha256_file(elf)
    map_hash = sha256_file(map_path)
    if elf_hash != FROZEN_TEST_ELF_SHA256:
        raise DriverError(
            f"frozen test ELF hash mismatch: {elf_hash} != {FROZEN_TEST_ELF_SHA256}"
        )
    if map_hash != FROZEN_TEST_MAP_SHA256:
        raise DriverError(
            f"frozen test map hash mismatch: {map_hash} != {FROZEN_TEST_MAP_SHA256}"
        )
    if not map_has_test_instrumentation(map_path):
        raise DriverError("selected map is not the P2_6_TEST_ENABLE build")
    return elf, map_path


def load_frozen_device_header(image: Path) -> tuple[bytes, dict[str, int]]:
    if not image.is_file():
        raise DriverError(f"missing frozen device image: {image}")
    image_hash = sha256_file(image)
    if image_hash != FROZEN_V280_IMAGE_SHA256:
        raise DriverError(
            f"frozen v2.8.0 image hash mismatch: {image_hash} != {FROZEN_V280_IMAGE_SHA256}"
        )
    layout = parse_layout_values()
    data = image.read_bytes()
    offset = layout["OTA_FW_HEADER_OFFSET"]
    size = layout["OTA_FW_HEADER_SIZE"]
    if len(data) < offset + size:
        raise DriverError("frozen device image does not contain the complete fw_header")
    return data[offset:offset + size], layout


def read_symbol_table(nm: Path, elf: Path) -> dict[str, list[int]]:
    result = subprocess.run(
        [str(nm), "-n", "-C", str(elf)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise DriverError(f"nm failed ({result.returncode}): {result.stderr.strip()}")
    symbols: dict[str, list[int]] = {}
    for raw in result.stdout.splitlines():
        parts = raw.split(maxsplit=2)
        if len(parts) != 3 or not re.fullmatch(r"[0-9A-Fa-f]+", parts[0]):
            continue
        symbols.setdefault(parts[2], []).append(int(parts[0], 16))
    return symbols


def require_symbols(
    symbols: dict[str, list[int]], names: list[str]
) -> dict[str, int]:
    missing = [name for name in names if not symbols.get(name)]
    if missing:
        raise DriverError("ELF lacks required symbols: " + ", ".join(missing))
    ambiguous = {
        name: symbols[name]
        for name in names
        if len(symbols[name]) != 1
    }
    if ambiguous:
        details = "; ".join(
            f"{name}=[{', '.join(f'0x{value:08X}' for value in values)}]"
            for name, values in ambiguous.items()
        )
        raise DriverError("ELF required symbols are not unique: " + details)
    return {name: symbols[name][0] for name in names}


def map_has_test_instrumentation(map_path: Path) -> bool:
    text = map_path.read_text(encoding="utf-8", errors="replace")
    required = (
        "P2_6_StartupStackScanProbe",
        "__wrap_lv_tlsf_malloc",
        "__wrap_lv_tlsf_realloc",
        "P2_6_sbrk_call_count",
    )
    return all(item in text for item in required)


def parse_measurements(raw: bytes) -> list[dict[str, int | str]]:
    text = raw.decode("utf-8", errors="replace")
    records: list[dict[str, int | str]] = []
    frames = text.split("\n")
    complete_frames = frames if text.endswith("\n") else frames[:-1]
    for frame in complete_frames:
        line = frame[:-1] if frame.endswith("\r") else frame
        stripped = line.strip()
        if not stripped:
            continue
        if not stripped.startswith("P2_6 kind="):
            continue
        match = MEASUREMENT_RE.fullmatch(stripped)
        if not match:
            raise DriverError(f"invalid or unknown complete P2_6 measurement: {stripped}")
        record: dict[str, int | str] = {"raw": line.strip()}
        for key, value in match.groupdict().items():
            record[key] = (
                value.upper() if key == "kind" else int(value, 16 if key == "last_ret" else 10)
            )
        records.append(record)
    if not text.endswith("\n"):
        tail = frames[-1].strip()
        if tail.startswith("P2_6 kind="):
            raise DriverError(f"truncated P2_6 measurement: {tail}")
    return records


def classify_measurement(record: dict[str, int | str]) -> dict[str, object]:
    return {
        "kind": record["kind"],
        "result_ok": record["result"] == 0,
        "workspace_ok": int(record["workspace_peak"]) <= 40960,
        "stack_ok": int(record["stack_peak"]) <= 8192,
        "guard_ok": record["guard_entry"] == 1 and record["guard_exit"] == 1,
        "sbrk_ok": record["sbrk_delta"] == 0,
        "tlsf_required_ok": (
            record["tlsf_malloc_delta"] == 0
            and record["tlsf_realloc_delta"] == 0
        ),
        "tlsf_free_zero": record["tlsf_free_delta"] == 0,
        "lv_pool_net_unchanged": (
            record["lv_free_entry"] == record["lv_free_exit"]
            and record["lv_big_entry"] == record["lv_big_exit"]
            and record["lv_frag_entry"] == record["lv_frag_exit"]
            and record["lv_max_entry"] == record["lv_max_exit"]
        ),
    }


def gdb_path(path: Path) -> str:
    return str(path).replace("\\", "/").replace('"', '\\"')


def gdb_prologue_lines(elf: Path) -> list[str]:
    return [
        "set pagination off",
        "set confirm off",
        "set print elements 0",
        f'file "{gdb_path(elf)}"',
    ]


def _gdb_label(label: str) -> str:
    if not re.fullmatch(r"[a-z][a-z0-9_]*", label):
        raise DriverError(f"invalid GDB audit label: {label!r}")
    return label


def deterministic_stop_lines(
    address: int,
    label: str,
    magic: int,
    quit_code: int,
    attach: bool = False,
) -> list[str]:
    label = _gdb_label(label)
    lines: list[str] = []
    if attach:
        lines.extend(
            [
                f"target remote 127.0.0.1:{GDB_PORT}",
                "monitor halt",
                WDT_PAUSE_COMMAND,
                "set $p2_6_attach_pc = (unsigned int)$pc",
                'printf "P2_6_TRANSPORT attached_stopped pc=0x%08x\\n", $p2_6_attach_pc',
            ]
        )
    lines.extend(
        [
            "set $p2_6_stop_magic = 0",
            f"thbreak *0x{address:08x}",
            "commands",
            "  silent",
            f"  set $p2_6_stop_magic = 0x{magic:08x}",
            f'  printf "P2_6_TRANSPORT breakpoint label={label} pc=0x%08x\\n", (unsigned int)$pc',
            "end",
            "continue",
            f"if $p2_6_stop_magic != 0x{magic:08x}",
            f'  printf "P2_6_TRANSPORT ERROR unexpected_stop label={label} magic=0x%08x pc=0x%08x\\n", $p2_6_stop_magic, (unsigned int)$pc',
            f"  quit {quit_code}",
            "end",
            f"if (unsigned int)$pc != 0x{address:08x}",
            f'  printf "P2_6_TRANSPORT ERROR wrong_pc label={label} pc=0x%08x expected=0x{address:08x}\\n", (unsigned int)$pc',
            f"  quit {quit_code}",
            "end",
            "delete breakpoints",
            f'printf "P2_6_TRANSPORT stop_verified label={label} pc=0x%08x\\n", (unsigned int)$pc',
        ]
    )
    return lines


def assert_stopped_at_lines(address: int, label: str, quit_code: int) -> list[str]:
    label = _gdb_label(label)
    return [
        "set $p2_6_checked_pc = (unsigned int)$pc",
        f"if $p2_6_checked_pc != 0x{address:08x}",
        f'  printf "P2_6_TRANSPORT ERROR context_lost label={label} pc=0x%08x expected=0x{address:08x}\\n", $p2_6_checked_pc',
        f"  quit {quit_code}",
        "end",
        f'printf "P2_6_TRANSPORT context_verified label={label} pc=0x%08x\\n", $p2_6_checked_pc',
    ]


def firmware_header_check_lines(
    header_address: int,
    expected_header: bytes,
    label: str,
    quit_code: int,
) -> list[str]:
    label = _gdb_label(label)
    if not expected_header or len(expected_header) % 4 != 0:
        raise DriverError("fw_header comparison requires non-empty 32-bit words")
    lines: list[str] = []
    for offset in range(0, len(expected_header), 4):
        expected = struct.unpack_from("<I", expected_header, offset)[0]
        address = header_address + offset
        lines.extend(
            [
                f"if *(unsigned int*)0x{address:08x} != 0x{expected:08x}",
                f'  printf "P2_6_IDENTITY ERROR label={label} offset={offset} actual=0x%08x expected=0x{expected:08x}\\n", *(unsigned int*)0x{address:08x}',
                f"  quit {quit_code}",
                "end",
            ]
        )
    lines.append(
        f'printf "P2_6_IDENTITY PASS label={label} header_bytes={len(expected_header)}\\n"'
    )
    return lines


def runtime_state_lines(
    symbols: dict[str, int],
    expected_header: bytes,
    layout: dict[str, int],
    label: str,
    expected_bcb: int,
    quit_code: int,
) -> list[str]:
    label = _gdb_label(label)
    update_entry = symbols[HAL_UPDATE_SYMBOL]
    header_address = layout["OTA_APP_ORIGIN"] + layout["OTA_FW_HEADER_OFFSET"]
    owner = symbols[OVERLAY_OWNER_SYMBOL]
    lines = firmware_header_check_lines(
        header_address, expected_header, f"{label}_fw", quit_code
    )
    lines.extend(
        [
            f"set $rtt_{label} = (unsigned char*)0x{symbols[RTT_SYMBOL]:08x}",
            f"if $rtt_{label}[0] != 0x53 || $rtt_{label}[1] != 0x45 || $rtt_{label}[2] != 0x47 || $rtt_{label}[3] != 0x47 || $rtt_{label}[4] != 0x45 || $rtt_{label}[5] != 0x52 || $rtt_{label}[6] != 0x20 || $rtt_{label}[7] != 0x52 || $rtt_{label}[8] != 0x54 || $rtt_{label}[9] != 0x54",
            f'  printf "P2_6_STATE ERROR label={label} rtt_signature\\n"',
            f"  quit {quit_code}",
            "end",
            f"set $sd_{label} = *(unsigned char*)0x{symbols[SD_READY_SYMBOL]:08x}",
            f"set $vtor_{label} = *(unsigned int*)0x{SCB_VTOR_ADDRESS:08x}",
            f"set $cfsr_{label} = *(unsigned int*)0x{SCB_CFSR_ADDRESS:08x}",
            f"set $owner_{label} = *(unsigned char*)0x{owner:08x}",
            f"if $sd_{label} != 1 || $vtor_{label} != 0x{EXPECTED_VTOR:08x} || $cfsr_{label} != 0 || $owner_{label} != {OTA_OVERLAY_FREE}",
            f'  printf "P2_6_STATE ERROR label={label} sd=%u vtor=0x%08x cfsr=0x%08x owner=%u\\n", $sd_{label}, $vtor_{label}, $cfsr_{label}, $owner_{label}',
            f"  quit {quit_code}",
            "end",
            f"set $bcb_{label} = ((unsigned char (*)(void))0x{symbols[GET_BCB_SYMBOL] | 1:08x})()",
            *assert_stopped_at_lines(update_entry, f"{label}_bcb_call", quit_code),
            f"if $bcb_{label} != {expected_bcb}",
            f'  printf "P2_6_STATE ERROR label={label} bcb=%u expected={expected_bcb}\\n", $bcb_{label}',
            f"  quit {quit_code}",
            "end",
            f'printf "P2_6_STATE PASS label={label} sd=%u vtor=0x%08x cfsr=0x%08x bcb=%u owner=%u\\n", $sd_{label}, $vtor_{label}, $cfsr_{label}, $bcb_{label}, $owner_{label}',
        ]
    )
    return lines


def probe_rtt_telnet(
    host: str,
    port: int,
    output: Path,
    connect_timeout: float = 60.0,
    banner_timeout: float = 1.5,
) -> tuple[bool, bytes, str | None]:
    """Connect once to the GDB server RTT telnet port and record the banner.

    The telnet channel is banner-only on this J-Link/board combination (R19
    probe F1), so it is used purely as a transport reachability probe: the
    first received chunk (the SEGGER banner) is stored in the RTT log for
    continuity with earlier rounds, and the measurement payload itself is
    captured by the two-phase JLinkRTTLogger flow. A successful TCP connect
    never means payload-ready.
    """
    deadline = time.monotonic() + connect_timeout
    last_error: str | None = None
    while time.monotonic() < deadline:
        sock: socket.socket | None = None
        try:
            sock = socket.create_connection((host, port), timeout=1.0)
            sock.settimeout(banner_timeout)
            banner = bytearray()
            try:
                while len(banner) < 4096:
                    chunk = sock.recv(4096)
                    if not chunk:
                        break
                    banner.extend(chunk)
            except OSError:
                pass
            output.write_bytes(bytes(banner))
            return True, bytes(banner), None
        except OSError as exc:
            last_error = str(exc)
            time.sleep(0.2)
        finally:
            if sock is not None:
                sock.close()
    return False, b"", last_error


def server_command(jlink_dir: Path) -> list[str]:
    server = jlink_dir / "JLinkGDBServerCL.exe"
    if not server.is_file():
        raise DriverError(f"missing J-Link GDB server: {server}")
    ports = (GDB_PORT, SWO_PORT, RTT_PORT, MONITOR_PORT)
    if len(set(ports)) != len(ports):
        raise DriverError(f"J-Link server ports are not unique: {ports}")
    return [
        str(server),
        "-select", "USB",
        "-device", DEVICE,
        "-if", INTERFACE,
        "-speed", str(SPEED_KHZ),
        "-port", str(GDB_PORT),
        "-swoport", str(SWO_PORT),
        "-telnetport", str(MONITOR_PORT),
        "-rtttelnetport", str(RTT_PORT),
        "-nogui",
        "-singlerun",
    ]


def start_server(
    jlink_dir: Path,
    server_log: Path,
    env: dict[str, str] | None = None,
) -> tuple[subprocess.Popen[bytes], object]:
    stream = server_log.open("wb")
    process = subprocess.Popen(
        server_command(jlink_dir),
        cwd=ROOT,
        stdout=stream,
        stderr=subprocess.STDOUT,
        env=env,
    )
    return process, stream


def wait_for_server_ready(
    process: subprocess.Popen[bytes], server_log: Path, timeout: float
) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise DriverError(f"J-Link GDB server exited early: {process.returncode}")
        if server_log.exists():
            text = server_log.read_text(encoding="utf-8", errors="replace")
            if SERVER_READY_MARKER in text:
                return
        time.sleep(0.1)
    raise DriverError(f"J-Link GDB server readiness timeout after {timeout:.1f}s")


def finish_server_process(
    process: subprocess.Popen[bytes],
    natural_exit_timeout: float = SERVER_NATURAL_EXIT_TIMEOUT,
    terminate_timeout: float = SERVER_TERMINATE_TIMEOUT,
    kill_timeout: float = SERVER_KILL_TIMEOUT,
) -> dict[str, object]:
    """Let a -singlerun server release J-Link before forcing cleanup."""
    started = time.monotonic()
    result: dict[str, object] = {
        "process_exited": False,
        "natural_exit": False,
        "terminate_sent": False,
        "kill_sent": False,
        "exit_code": None,
        "exit_wait_seconds": None,
        "cleanup_action": None,
        "cleanup_error": None,
    }
    try:
        if process.poll() is not None:
            result["natural_exit"] = True
            result["cleanup_action"] = "already_exited"
        else:
            try:
                process.wait(timeout=natural_exit_timeout)
                result["natural_exit"] = True
                result["cleanup_action"] = "natural_exit"
            except subprocess.TimeoutExpired:
                result["terminate_sent"] = True
                result["cleanup_action"] = "terminate"
                process.terminate()
                try:
                    process.wait(timeout=terminate_timeout)
                except subprocess.TimeoutExpired:
                    result["kill_sent"] = True
                    result["cleanup_action"] = "kill"
                    process.kill()
                    process.wait(timeout=kill_timeout)
    except Exception as exc:  # pragma: no cover - defensive hardware cleanup
        result["cleanup_error"] = f"{type(exc).__name__}: {exc}"
    result["exit_code"] = process.poll()
    result["process_exited"] = process.poll() is not None
    result["exit_wait_seconds"] = round(time.monotonic() - started, 3)
    if not result["process_exited"] and result["cleanup_error"] is None:
        result["cleanup_error"] = "J-Link GDB server process remains alive"
    return result


def port_is_listening(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.15):
            return True
    except OSError:
        return False


def wait_for_ports_closed(ports: tuple[int, ...], timeout: float = 5.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not any(port_is_listening(port) for port in ports):
            return True
        time.sleep(0.1)
    return not any(port_is_listening(port) for port in ports)


def classify_transport_session(outcome: dict[str, object]) -> str:
    if not outcome["server_started"]:
        return "HARNESS_PRECONDITION_FAIL"
    if not outcome["server_ready"]:
        return "TRANSPORT_NOT_READY"
    if not outcome["rtt_connected"]:
        return "RTT_NOT_READY"
    if not outcome["gdb_started"]:
        return "GDB_NOT_STARTED"
    if outcome["gdb_exit_code"] != 0:
        return "GDB_FAIL"
    if (
        not outcome["server_process_exited"]
        or not outcome["server_natural_exit"]
        or outcome["server_terminate_sent"]
        or outcome["server_kill_sent"]
        or not outcome["capture_stopped"]
        or not outcome["ports_closed"]
    ):
        return "CLEANUP_FAIL"
    if outcome.get("rtt_measurement_required"):
        if (
            not outcome.get("rtt_pending_derived")
            or not outcome["rtt_payload_ready"]
            or not outcome.get("rtt_drain_success")
            or not outcome["rtt_drain_complete"]
            or outcome.get("rtt_drain_deadline_expired")
            or outcome.get("rtt_socket_eof")
            or outcome.get("rtt_socket_error")
            or outcome.get("rtt_payload_timeout")
            or outcome.get("capture_error")
            or outcome["rtt_record_count"] != 1
            or outcome.get("rtt_matching_record_count") != 1
        ):
            return "RTT_PAYLOAD_FAIL"
        if not outcome.get("rtt_postcheck_passed"):
            return "RTT_POSTCHECK_FAIL"
    if outcome["session_error"]:
        return "HARNESS_FAIL"
    return "PASS"


def run_gdb_session(
    *,
    jlink_dir: Path,
    gdb: Path,
    gdb_script: Path,
    gdb_log: Path,
    server_log: Path,
    rtt_log: Path,
    tmp_dir: Path,
    timeout: int,
    server_ready_timeout: float,
    server_exit_timeout: float = SERVER_NATURAL_EXIT_TIMEOUT,
    measurement_policy: bool = False,
    expected_kind: str | None = None,
) -> dict[str, object]:
    """Run one GDB server session end to end.

    The RTT telnet port is only probed for reachability (the SEGGER banner is
    recorded in the RTT log); it is banner-only on this J-Link, so measurement
    payloads are captured by the two-phase JLinkRTTLogger flow in
    run_two_phase_ota_session, which fills in the rtt_* payload fields and the
    final transport classification afterwards. With measurement_policy set,
    transport_classification stays None here on purpose: the outcome is
    incomplete until the second phase closes.
    """
    ports = (GDB_PORT, SWO_PORT, RTT_PORT, MONITOR_PORT)
    outcome: dict[str, object] = {
        "server_started": False,
        "server_pid": None,
        "server_ready": False,
        "server_ready_seconds": None,
        "server_exit_code": None,
        "server_process_exited": False,
        "server_natural_exit": False,
        "server_terminate_sent": False,
        "server_kill_sent": False,
        "server_exit_wait_seconds": None,
        "server_cleanup_action": None,
        "server_cleanup_error": None,
        "gdb_started": False,
        "gdb_exit_code": None,
        "capture_error": None,
        "rtt_connected": False,
        "rtt_socket_connected": False,
        "rtt_socket_eof": False,
        "rtt_socket_error": False,
        "rtt_banner_bytes": None,
        "rtt_capture_mode": "two_phase_logger",
        "rtt_measurement_required": bool(measurement_policy),
        "rtt_expected_kind": expected_kind.upper() if expected_kind else None,
        "rtt_pending_derived": False,
        "rtt_payload_ready": False,
        "rtt_drain_started": False,
        "rtt_drain_success": False,
        "rtt_drain_complete": False,
        "rtt_drain_deadline_expired": False,
        "rtt_payload_complete": False,
        "rtt_payload_timeout": False,
        "rtt_payload_parse_error": None,
        "rtt_record_count": 0,
        "rtt_matching_record_count": None,
        "rtt_postcheck_passed": False,
        "rtt_channel_binding_verified": False,
        "capture_stopped": True,
        "ports_closed": False,
        "session_error": None,
        "transport_classification": None,
    }
    server: subprocess.Popen[bytes] | None = None
    server_stream: object | None = None
    child_env = os.environ.copy()
    child_env["TEMP"] = str(tmp_dir)
    child_env["TMP"] = str(tmp_dir)
    child_env["TMPDIR"] = str(tmp_dir)
    child_env["PYTHONPYCACHEPREFIX"] = str(tmp_dir / "pycache")
    try:
        busy = [port for port in ports if port_is_listening(port)]
        if busy:
            raise DriverError(f"J-Link ports already in use: {busy}")
        server, server_stream = start_server(jlink_dir, server_log, child_env)
        outcome["server_started"] = True
        outcome["server_pid"] = server.pid
        ready_started = time.monotonic()
        wait_for_server_ready(server, server_log, server_ready_timeout)
        outcome["server_ready"] = True
        outcome["server_ready_seconds"] = round(
            time.monotonic() - ready_started, 3
        )
        connected, banner, probe_error = probe_rtt_telnet(
            "127.0.0.1", RTT_PORT, rtt_log, connect_timeout=5.0
        )
        if not connected:
            raise DriverError(
                f"RTT Telnet connection was not established: {probe_error}"
            )
        outcome["rtt_connected"] = True
        outcome["rtt_socket_connected"] = True
        outcome["rtt_banner_bytes"] = len(banner)
        if not banner.startswith(b"SEGGER"):
            outcome["rtt_socket_error"] = True
            raise DriverError(
                f"RTT Telnet banner is not a SEGGER banner: {banner[:32]!r}"
            )
        outcome["gdb_started"] = True
        gdb_env = child_env.copy()
        gdb_env["HOME"] = str(tmp_dir)
        gdb_env["USERPROFILE"] = str(tmp_dir)
        with gdb_log.open("wb") as stream:
            result = subprocess.run(
                [str(gdb), "-nx", "-q", "-batch", "-x", str(gdb_script)],
                cwd=ROOT,
                stdout=stream,
                stderr=subprocess.STDOUT,
                check=False,
                timeout=timeout,
                env=gdb_env,
            )
        outcome["gdb_exit_code"] = result.returncode
    except Exception as exc:  # pragma: no cover - exercised on hardware
        outcome["session_error"] = f"{type(exc).__name__}: {exc}"
    finally:
        if server is not None:
            cleanup = finish_server_process(server, server_exit_timeout)
            outcome["server_exit_code"] = cleanup["exit_code"]
            outcome["server_process_exited"] = cleanup["process_exited"]
            outcome["server_natural_exit"] = cleanup["natural_exit"]
            outcome["server_terminate_sent"] = cleanup["terminate_sent"]
            outcome["server_kill_sent"] = cleanup["kill_sent"]
            outcome["server_exit_wait_seconds"] = cleanup["exit_wait_seconds"]
            outcome["server_cleanup_action"] = cleanup["cleanup_action"]
            outcome["server_cleanup_error"] = cleanup["cleanup_error"]
        if server_stream is not None:
            server_stream.close()
        outcome["ports_closed"] = wait_for_ports_closed(ports)
    cleanup_errors: list[str] = []
    if not outcome["ports_closed"]:
        cleanup_errors.append("J-Link listener ports remain open")
    if outcome["server_cleanup_error"]:
        cleanup_errors.append(
            f"J-Link server cleanup error: {outcome['server_cleanup_error']}"
        )
    if outcome["server_terminate_sent"] or outcome["server_kill_sent"]:
        cleanup_errors.append("J-Link -singlerun server required forced termination")
    if cleanup_errors:
        suffix = "; ".join(cleanup_errors)
        prior = outcome["session_error"]
        outcome["session_error"] = f"{prior}; {suffix}" if prior else suffix
    if not measurement_policy:
        outcome["transport_classification"] = classify_transport_session(outcome)
    return outcome


def rtt_descriptor(control_block: bytes) -> dict[str, int]:
    """Parse the Up0 descriptor fields out of a 0xA8-byte RTT control block."""
    if len(control_block) < RTT_CB_SIZE:
        raise DriverError("RTT control block snapshot is truncated")
    if control_block[:10] != RTT_SIGNATURE:
        raise DriverError("RTT control block signature mismatch")
    return {
        "max_up_buffers": struct.unpack_from("<i", control_block, RTT_CB_MAX_UP_OFFSET)[0],
        "max_down_buffers": struct.unpack_from("<i", control_block, RTT_CB_MAX_DOWN_OFFSET)[0],
        "pBuffer": struct.unpack_from("<I", control_block, RTT_CB_UP0_PBUFFER_OFFSET)[0],
        "SizeOfBuffer": struct.unpack_from("<I", control_block, RTT_CB_UP0_SIZE_OFFSET)[0],
        "WrOff": struct.unpack_from("<I", control_block, RTT_CB_UP0_WROFF_OFFSET)[0],
        "RdOff": struct.unpack_from("<I", control_block, RTT_CB_UP0_RDOFF_OFFSET)[0],
        "Flags": struct.unpack_from("<I", control_block, RTT_CB_UP0_FLAGS_OFFSET)[0],
    }


def ring_slice(ring: bytes, rd: int, count: int) -> bytes:
    if count and not 0 <= rd < len(ring):
        raise DriverError(f"RdOff is out of range: {rd}")
    if not 0 <= count <= len(ring) - 1:
        raise DriverError(f"pending byte count is out of range: {count}")
    first = min(count, len(ring) - rd)
    return ring[rd:rd + first] + ring[:count - first]


def derive_rtt_pending(
    control_block_path: Path,
    ring_path: Path,
    expected_kind: str,
    pending_path: Path,
) -> dict[str, object]:
    """Derive the pending Up0 inventory from the session-1 halted snapshot.

    Fails closed on any structural inconsistency before a single byte is sent
    to the logger: the descriptor must describe the frozen firmware RTT
    configuration and the pending bytes must parse as exactly one record of
    the expected kind.
    """
    result: dict[str, object] = {"status": "FAIL"}
    try:
        control_block = control_block_path.read_bytes()
        ring = ring_path.read_bytes()
        desc = rtt_descriptor(control_block)
        if desc["max_up_buffers"] != RTT_EXPECTED_MAX_UP_BUFFERS or desc["max_down_buffers"] != RTT_EXPECTED_MAX_DOWN_BUFFERS:
            raise DriverError(
                f"RTT buffer counts mismatch: up={desc['max_up_buffers']} down={desc['max_down_buffers']}"
            )
        if not 0x20000000 <= desc["pBuffer"] < 0x20080000:
            raise DriverError(f"Up0 pBuffer is outside SRAM: 0x{desc['pBuffer']:08X}")
        if desc["SizeOfBuffer"] != RTT_EXPECTED_UP0_SIZE:
            raise DriverError(f"Up0 size mismatch: {desc['SizeOfBuffer']}")
        if len(ring) != RTT_EXPECTED_UP0_SIZE:
            raise DriverError(f"Up0 ring snapshot size mismatch: {len(ring)}")
        if desc["Flags"] != RTT_EXPECTED_UP0_FLAGS:
            raise DriverError(f"Up0 flags mismatch: {desc['Flags']}")
        if not 0 <= desc["WrOff"] < RTT_EXPECTED_UP0_SIZE or not 0 <= desc["RdOff"] < RTT_EXPECTED_UP0_SIZE:
            raise DriverError("Up0 offsets are out of range")
        pending_count = (desc["WrOff"] - desc["RdOff"]) % RTT_EXPECTED_UP0_SIZE
        pending = ring_slice(ring, desc["RdOff"], pending_count)
        records = parse_measurements(pending)
        normalized = expected_kind.upper()
        matching = [record for record in records if record["kind"] == normalized]
        if pending_count == 0:
            result.update(
                {
                    "status": "EMPTY",
                    "descriptor": desc,
                    "pending_count": 0,
                    "reason": "UP0_INVENTORY_EMPTY",
                }
            )
            return result
        if len(records) != 1 or len(matching) != 1:
            result.update(
                {"record_count": len(records), "matching_record_count": len(matching)}
            )
            raise DriverError(
                f"expected exactly one {normalized} record in pending inventory, "
                f"records={len(records)} matching={len(matching)}"
            )
        pending_path.write_bytes(pending)
        result.update(
            {
                "status": "ELIGIBLE",
                "descriptor": desc,
                "pending_count": pending_count,
                "pending_sha256": hashlib.sha256(pending).hexdigest().upper(),
                "pending_path": str(pending_path),
                "record_count": len(records),
                "matching_record_count": len(matching),
            }
        )
        return result
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
        return result


def run_rtt_logger_capture(
    pending_path: Path,
    raw_log: Path,
    console_log: Path,
    rtt_address: int,
    tmp_dir: Path,
    payload_timeout: float = LOGGER_PAYLOAD_TIMEOUT,
    settle_seconds: float = LOGGER_SETTLE_SECONDS,
) -> dict[str, object]:
    """Between-sessions RTT payload capture via JLinkRTTLogger.

    The logger is the project's canonical RTT reader in its own probe
    connection: it reads the Up0 inventory [RdOff, WrOff) that must be
    byte-identical to the session-1 GDB-snapshotted pending inventory and
    advances RdOff. The logger has no natural exit; it is stopped with the
    AGENTS.md residual-logger cleanup pattern and the stop is disclosed in
    the capture result.
    """
    result: dict[str, object] = {
        "phase": "capture",
        "status": "FAIL",
        "reader": "JLinkRTTLogger",
        "payload_ready": False,
        "payload_complete": False,
        "payload_timeout": False,
        "logger_stopped_by": (
            "AGENTS.md residual-logger cleanup pattern (Stop-Process); "
            "the logger has no natural exit"
        ),
    }
    if not RTT_LOGGER.is_file():
        result["error"] = f"missing JLinkRTTLogger: {RTT_LOGGER}"
        return result
    pending = pending_path.read_bytes()
    if raw_log.exists():
        raw_log.unlink()
    logger: subprocess.Popen[bytes] | None = None
    logger_env = os.environ.copy()
    logger_env["TEMP"] = str(tmp_dir)
    logger_env["TMP"] = str(tmp_dir)
    logger_env["TMPDIR"] = str(tmp_dir)
    try:
        command = [
            str(RTT_LOGGER),
            "-Device", "CORTEX-M4",
            "-If", "SWD",
            "-Speed", "1000",
            "-RTTAddress", f"0x{rtt_address:08X}",
            "-RTTChannel", "0",
            str(raw_log),
        ]
        started = time.monotonic()
        with console_log.open("wb") as console:
            logger = subprocess.Popen(
                command,
                cwd=ROOT,
                stdin=subprocess.DEVNULL,
                stdout=console,
                stderr=subprocess.STDOUT,
                env=logger_env,
            )
        result["logger_pid"] = logger.pid
        result["logger_command"] = command
        deadline = started + payload_timeout
        delivered = 0
        while time.monotonic() < deadline:
            if logger.poll() is not None:
                raise DriverError(f"RTT logger exited early: rc={logger.returncode}")
            delivered = raw_log.stat().st_size if raw_log.exists() else 0
            if delivered >= len(pending):
                break
            time.sleep(0.1)
        else:
            raise DriverError(
                f"RTT payload timeout: logger delivered {delivered} of {len(pending)} bytes"
            )
        result["payload_ready"] = True
        # Quiet settle: once the inventory size is reached no further byte may
        # arrive; extra bytes mean the firmware produced output the session-1
        # snapshot never saw, which would break the byte-binding proof.
        settle_deadline = time.monotonic() + settle_seconds
        while time.monotonic() < settle_deadline:
            if raw_log.exists() and raw_log.stat().st_size > len(pending):
                raise DriverError("RTT payload contains extra bytes")
            time.sleep(0.1)
        payload = raw_log.read_bytes()
        if len(payload) > len(pending):
            raise DriverError("RTT payload contains extra bytes")
        if payload != pending:
            raise DriverError("RTT payload differs from pre-read Up0 inventory")
        result.update(
            {
                "status": "PASS",
                "payload_complete": True,
                "payload_bytes": len(payload),
                "payload_sha256": hashlib.sha256(payload).hexdigest().upper(),
                "expected_pending_bytes": len(pending),
                "logger_wait_seconds": round(time.monotonic() - started, 3),
            }
        )
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
        result["payload_timeout"] = "timeout" in str(exc).lower()
        result["raw_bytes"] = raw_log.stat().st_size if raw_log.exists() else 0
    # Stop the logger before sealing the capture result so the recorded
    # lifecycle is part of the evidence itself.
    if logger is not None and logger.poll() is None:
        subprocess.run(
            [
                "powershell.exe", "-NoProfile", "-Command",
                "Stop-Process -Name JLinkRTTLogger -Force -ErrorAction SilentlyContinue",
            ],
            capture_output=True,
            check=False,
        )
        for _ in range(int(LOGGER_STOP_WAIT_SECONDS / 0.25)):
            if logger.poll() is not None:
                break
            time.sleep(0.25)
    result["logger_stopped"] = logger is None or logger.poll() is not None
    check = subprocess.run(
        ["tasklist", "/FO", "CSV", "/NH"], capture_output=True, text=True, check=False
    )
    result["residual_rtt_logger_processes"] = sum(
        1 for line in check.stdout.splitlines() if "JLinkRTTLogger" in line
    )
    if result.get("residual_rtt_logger_processes"):
        result["status"] = "FAIL"
        result["error"] = "residual JLinkRTTLogger processes remain"
    return result


def verify_rtt_postcheck(
    pre_control_block_path: Path,
    post_control_block_path: Path,
    pending_count: int,
) -> dict[str, object]:
    """Verify the logger's only legal side effect on the RTT control block.

    WrOff must be unchanged, RdOff must have advanced exactly over the
    consumed inventory, and every control-block byte outside the four-byte
    Up0 RdOff word must be identical between the two snapshots.
    """
    result: dict[str, object] = {"phase": "postcheck", "status": "FAIL"}
    try:
        pre_cb = pre_control_block_path.read_bytes()
        post_cb = post_control_block_path.read_bytes()
        d0 = rtt_descriptor(pre_cb)
        d1 = rtt_descriptor(post_cb)
        if (
            d1["pBuffer"] != d0["pBuffer"]
            or d1["SizeOfBuffer"] != d0["SizeOfBuffer"]
            or d1["Flags"] != d0["Flags"]
        ):
            raise DriverError("post-read Up0 descriptor identity mismatch")
        if d1["WrOff"] != d0["WrOff"]:
            raise DriverError(
                f"WrOff changed during host consumption: {d0['WrOff']} -> {d1['WrOff']}"
            )
        if d1["RdOff"] != d0["WrOff"]:
            raise DriverError(
                f"RdOff did not consume inventory: before={d0['RdOff']} "
                f"after={d1['RdOff']} wr={d0['WrOff']}"
            )
        consumed = (d1["RdOff"] - d0["RdOff"]) % d0["SizeOfBuffer"]
        if consumed != pending_count:
            raise DriverError(f"RdOff delta {consumed} != pending count {pending_count}")
        rd_off_word = RTT_CB_UP0_RDOFF_OFFSET
        outside_rd_off = [
            {"offset": offset, "before": pre_cb[offset], "after": post_cb[offset]}
            for offset in range(len(pre_cb))
            if pre_cb[offset] != post_cb[offset]
            and not (rd_off_word <= offset < rd_off_word + 4)
        ]
        if outside_rd_off:
            raise DriverError(
                "RTT control block changed outside the four-byte Up0 RdOff word: "
                f"{outside_rd_off[:8]}"
            )
        result.update(
            {
                "status": "PASS",
                "descriptor_before": d0,
                "descriptor_after": d1,
                "pending_count": pending_count,
                "consumed_count": consumed,
                "control_block_outside_rd_off_changes": 0,
            }
        )
        return result
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
        return result


def gdb_command_file(
    path: Path,
    elf: Path,
    symbols: dict[str, int],
    expected_header: bytes,
    layout: dict[str, int],
    package_path: str,
    expected_kind: str,
    rtt_cb_snapshot: Path,
    rtt_ring_snapshot: Path,
) -> None:
    escaped_path = package_path.replace("\\", "\\\\").replace('"', '\\"')
    parent_path = package_path.rsplit("/", 1)[0] or "/"
    escaped_parent = parent_path.replace("\\", "\\\\").replace('"', '\\"')
    manager = symbols[MANAGER_SYMBOL]
    page_current = manager + PAGE_CURRENT_OFFSET
    update_entry = symbols[HAL_UPDATE_SYMBOL]

    def thumb(name: str) -> int:
        return symbols[name] | 1

    lines = [
        *gdb_prologue_lines(elf),
        *deterministic_stop_lines(
            update_entry, "initial_hal_update", 0x50326001, 20, attach=True
        ),
        *runtime_state_lines(
            symbols,
            expected_header,
            layout,
            "before_ota",
            BCB_STATE_CONFIRMED,
            21,
        ),
        f"set $initial_page = *(void**)0x{page_current:08x}",
        "if $initial_page == 0",
        '  printf "P2_6_RTT_DRIVER ERROR no_initial_page context_harness_fail\\n"',
        "  quit 22",
        "end",
        f'set $push_ok = ((unsigned char (*)(void*, const char*, void*))0x{thumb(PUSH_SYMBOL):08x})((void*)0x{manager:08x}, "Pages/FirmwareUpdate", 0)',
        *assert_stopped_at_lines(update_entry, "push_return", 23),
        'printf "P2_6_RTT_DRIVER push_ok=%u\\n", $push_ok',
        "if $push_ok == 0",
        '  printf "P2_6_RTT_DRIVER ERROR push_failed context_harness_fail\\n"',
        "  quit 24",
        "end",
        f"set $page = *(void**)0x{page_current:08x}",
        'printf "P2_6_RTT_DRIVER page=0x%08x\\n", $page',
        "if $page == 0",
        '  printf "P2_6_RTT_DRIVER ERROR no_current_page context_harness_fail\\n"',
        "  quit 25",
        "end",
        f"set $expected_vptr = 0x{symbols[PAGE_VTABLE_SYMBOL] + 8:08x}",
        "if *(unsigned int*)$page != $expected_vptr",
        '  printf "P2_6_RTT_DRIVER ERROR wrong_page vptr=0x%08x expected=0x%08x\\n", *(unsigned int*)$page, $expected_vptr',
        "  quit 26",
        "end",
        f"set $page_state = *(unsigned char*)((char*)$page + {PAGE_STATE_OFFSET})",
        f"if $page_state != {PAGE_STATE_DID_APPEAR} && $page_state != {PAGE_STATE_ACTIVITY}",
        '  printf "P2_6_RTT_DRIVER ERROR wrong_page_state state=%u expected=3_or_4\\n", $page_state',
        "  quit 27",
        "end",
        'printf "P2_6_RTT_DRIVER page_ready state=%u\\n", $page_state',
        f'call ((void (*)(void*, const char*))0x{thumb(ENTER_PATH_SYMBOL):08x})($page, "{escaped_parent}")',
        *assert_stopped_at_lines(update_entry, "enter_path_return", 28),
        "set $row_index = -1",
        "set $i = 0",
        "while $i < 24",
        f"  set $row_path = (char*)$page + 0x{FIRMWARE_UPDATE_ROWS_OFFSET:x} + $i * {FIRMWARE_UPDATE_ROW_STRIDE} + {FIRMWARE_UPDATE_ROW_PATH_OFFSET}",
        f'  set $cmp = ((int (*)(const char*, const char*))0x{thumb(STRCMP_SYMBOL):08x})($row_path, "{escaped_path}")',
        "  if $cmp == 0",
        "    set $row_index = $i",
        "    loop_break",
        "  end",
        "  set $i = $i + 1",
        "end",
        *assert_stopped_at_lines(update_entry, "row_scan_return", 29),
        'printf "P2_6_RTT_DRIVER row_index=%d\\n", $row_index',
        "if $row_index < 0",
        '  printf "P2_6_RTT_DRIVER ERROR package_row_not_found\\n"',
        "  quit 30",
        "end",
        f"call ((void (*)(void*, unsigned char))0x{thumb(SELECT_ROW_SYMBOL):08x})($page, $row_index)",
        *assert_stopped_at_lines(update_entry, "select_row_return", 31),
        f"set $mode = *(unsigned char*)((char*)$page + 0x{FIRMWARE_UPDATE_MODE_OFFSET:x})",
        f'printf "P2_6_RTT_DRIVER confirm mode=%u kind={expected_kind}\\n", $mode',
        f"if $mode != {MODE_CONFIRM}",
        '  printf "P2_6_RTT_DRIVER ERROR confirm_not_reached\\n"',
        "  quit 32",
        "end",
        f"call ((void (*)(void*))0x{thumb(START_IMPORT_SYMBOL):08x})($page)",
        *assert_stopped_at_lines(update_entry, "start_import_return", 33),
        f"set $mode = *(unsigned char*)((char*)$page + 0x{FIRMWARE_UPDATE_MODE_OFFSET:x})",
        'printf "P2_6_RTT_DRIVER import_started mode=%u\\n", $mode',
        f"if $mode != {MODE_WORKING}",
        '  printf "P2_6_RTT_DRIVER ERROR import_not_started\\n"',
        "  quit 34",
        "end",
        *deterministic_stop_lines(
            symbols[FINISH_IMPORT_SYMBOL],
            "finish_import_entry",
            0x50326002,
            35,
        ),
        *deterministic_stop_lines(
            update_entry,
            "result_hal_update",
            0x50326003,
            36,
        ),
        f"set $mode = *(unsigned char*)((char*)$page + 0x{FIRMWARE_UPDATE_MODE_OFFSET:x})",
        *runtime_state_lines(
            symbols,
            expected_header,
            layout,
            "after_ota",
            BCB_STATE_STAGED,
            37,
        ),
        'printf "P2_6_RTT_DRIVER result mode=%u\\n", $mode',
        f"if $mode != {MODE_RESULT}",
        '  printf "P2_6_RTT_DRIVER ERROR result_mode_not_reached\\n"',
        "  quit 38",
        "end",
        f'printf "P2_6_RTT_DRIVER PASS kind={expected_kind} page_state=%u mode=%u\\n", $page_state, $mode',
        "",
        "# Two-phase RTT capture, phase 1: snapshot the Up0 inventory while halted.",
        f"set $rtt_cb = (unsigned char*)0x{symbols[RTT_SYMBOL]:08x}",
        f"if $rtt_cb[0] != 0x53 || $rtt_cb[1] != 0x45 || $rtt_cb[2] != 0x47 || $rtt_cb[3] != 0x47 || $rtt_cb[4] != 0x45 || $rtt_cb[5] != 0x52 || $rtt_cb[6] != 0x20 || $rtt_cb[7] != 0x52 || $rtt_cb[8] != 0x54 || $rtt_cb[9] != 0x54",
        '  printf "P2_6_RTT_DRIVER ERROR rtt_signature_at_snapshot\\n"',
        "  quit 39",
        "end",
        "set $up0_pbuf = *(unsigned int*)($rtt_cb + 0x1C)",
        "set $up0_size = *(unsigned int*)($rtt_cb + 0x20)",
        "set $up0_wroff = *(unsigned int*)($rtt_cb + 0x24)",
        "set $up0_rdoff = *(unsigned int*)($rtt_cb + 0x28)",
        'printf "P2_6_RTT_CB pBuffer=0x%08x size=%u wroff=%u rdoff=%u\\n", $up0_pbuf, $up0_size, $up0_wroff, $up0_rdoff',
        "if $up0_size != 1024",
        '  printf "P2_6_RTT_DRIVER ERROR up0_size=%u\\n", $up0_size',
        "  quit 40",
        "end",
        f"dump binary memory {gdb_path(rtt_cb_snapshot)} $rtt_cb ($rtt_cb + 0xA8)",
        f"dump binary memory {gdb_path(rtt_ring_snapshot)} $up0_pbuf ($up0_pbuf + $up0_size)",
        'printf "P2_6_RTT_DRIVER SNAPSHOT_WRITTEN cb_bytes=168 ring_bytes=%u\\n", $up0_size',
        "detach",
        "quit",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="ascii")


def post_snapshot_command_file(
    path: Path,
    elf: Path,
    rtt_address: int,
    control_block_path: Path,
) -> None:
    """Phase-3 GDB script: halt, pause the watchdog, dump the post-read RTT
    control block, detach. Nothing else may run in this session."""
    lines = [
        *gdb_prologue_lines(elf),
        f"target remote 127.0.0.1:{GDB_PORT}",
        "monitor halt",
        WDT_PAUSE_COMMAND,
        f"set $rtt_cb = (unsigned char*)0x{rtt_address:08x}",
        f"if $rtt_cb[0] != 0x53 || $rtt_cb[1] != 0x45 || $rtt_cb[2] != 0x47 || $rtt_cb[3] != 0x47 || $rtt_cb[4] != 0x45 || $rtt_cb[5] != 0x52 || $rtt_cb[6] != 0x20 || $rtt_cb[7] != 0x52 || $rtt_cb[8] != 0x54 || $rtt_cb[9] != 0x54",
        '  printf "P2_6_RTT_POST ERROR rtt_signature\\n"',
        "  quit 41",
        "end",
        'printf "P2_6_RTT_POST attached_stopped pc=0x%08x\\n", (unsigned int)$pc',
        f"dump binary memory {gdb_path(control_block_path)} $rtt_cb ($rtt_cb + 0xA8)",
        'printf "P2_6_RTT_POST SNAPSHOT_WRITTEN cb_bytes=168\\n"',
        "detach",
        "quit",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="ascii")


def _append_session_error(outcome: dict[str, object], message: str) -> None:
    prior = outcome["session_error"]
    outcome["session_error"] = f"{prior}; {message}" if prior else message


def run_two_phase_ota_session(
    *,
    jlink_dir: Path,
    gdb: Path,
    gdb_script: Path,
    gdb_log: Path,
    server_log: Path,
    rtt_log: Path,
    tmp_dir: Path,
    timeout: int,
    server_ready_timeout: float,
    expected_kind: str,
    rtt_address: int,
    cb_snapshot: Path,
    ring_snapshot: Path,
    pending_path: Path,
    raw_log: Path,
    console_log: Path,
    post_gdb_script: Path,
    post_gdb_log: Path,
    post_server_log: Path,
    post_rtt_log: Path,
    post_cb_snapshot: Path,
    server_exit_timeout: float = SERVER_NATURAL_EXIT_TIMEOUT,
    logger_payload_timeout: float = LOGGER_PAYLOAD_TIMEOUT,
    logger_settle_seconds: float = LOGGER_SETTLE_SECONDS,
) -> dict[str, object]:
    """Two-phase OTA measurement session (R19-proven capture structure).

    Phase 1 runs the OTA driver GDB script, which snapshots the RTT control
    block and the Up0 ring while the core is halted. Phase 2 captures the
    pending inventory with JLinkRTTLogger in its own probe connection and
    requires byte identity with the snapshot. Phase 3 is a short second GDB
    session proving the logger's only side effect on the control block is the
    four-byte Up0 RdOff word. The returned outcome keeps the
    run_gdb_session field layout; the rtt_* payload fields are filled here.
    """
    session = run_gdb_session(
        jlink_dir=jlink_dir,
        gdb=gdb,
        gdb_script=gdb_script,
        gdb_log=gdb_log,
        server_log=server_log,
        rtt_log=rtt_log,
        tmp_dir=tmp_dir,
        timeout=timeout,
        server_ready_timeout=server_ready_timeout,
        server_exit_timeout=server_exit_timeout,
        measurement_policy=True,
        expected_kind=expected_kind,
    )
    phases: dict[str, object] = {}
    transport_ok = (
        session["session_error"] is None and session["gdb_exit_code"] == 0
    )
    derived: dict[str, object] = {"status": "NOT_RUN"}
    capture: dict[str, object] = {"status": "NOT_RUN", "payload_timeout": False}
    postcheck: dict[str, object] = {"status": "NOT_RUN"}
    if transport_ok:
        derived = derive_rtt_pending(
            cb_snapshot, ring_snapshot, expected_kind, pending_path
        )
        phases["derive"] = derived
        if derived.get("status") == "ELIGIBLE":
            capture = run_rtt_logger_capture(
                pending_path,
                raw_log,
                console_log,
                rtt_address,
                tmp_dir,
                payload_timeout=logger_payload_timeout,
                settle_seconds=logger_settle_seconds,
            )
            phases["capture"] = capture
            if capture.get("status") == "PASS":
                post_session = run_gdb_session(
                    jlink_dir=jlink_dir,
                    gdb=gdb,
                    gdb_script=post_gdb_script,
                    gdb_log=post_gdb_log,
                    server_log=post_server_log,
                    rtt_log=post_rtt_log,
                    tmp_dir=tmp_dir,
                    timeout=timeout,
                    server_ready_timeout=server_ready_timeout,
                    server_exit_timeout=server_exit_timeout,
                    measurement_policy=False,
                )
                phases["post_session"] = post_session
                if (
                    post_session["session_error"] is None
                    and post_session["gdb_exit_code"] == 0
                ):
                    postcheck = verify_rtt_postcheck(
                        cb_snapshot, post_cb_snapshot, int(derived["pending_count"])
                    )
                    phases["postcheck"] = postcheck
                    if postcheck.get("status") != "PASS":
                        _append_session_error(
                            session,
                            f"RTT postcheck failed: {postcheck.get('error')}",
                        )
                else:
                    _append_session_error(
                        session,
                        "post snapshot session failed: "
                        f"{post_session['session_error']}; gdb={post_session['gdb_exit_code']}",
                    )
            else:
                _append_session_error(
                    session, f"RTT logger capture failed: {capture.get('error')}"
                )
        elif derived.get("status") == "EMPTY":
            _append_session_error(session, "RTT pending inventory is empty")
        else:
            _append_session_error(
                session, f"RTT pending derivation failed: {derived.get('error')}"
            )
    session["rtt_two_phase"] = phases
    session["rtt_pending_derived"] = derived.get("status") == "ELIGIBLE"
    session["rtt_drain_started"] = capture.get("status") not in ("NOT_RUN",)
    session["rtt_drain_success"] = capture.get("status") == "PASS"
    session["rtt_drain_complete"] = capture.get("status") == "PASS"
    session["rtt_drain_deadline_expired"] = bool(capture.get("payload_timeout"))
    session["rtt_payload_timeout"] = bool(capture.get("payload_timeout"))
    session["rtt_postcheck_passed"] = postcheck.get("status") == "PASS"
    session["rtt_record_count"] = int(derived.get("record_count", 0) or 0)
    session["rtt_matching_record_count"] = int(
        derived.get("matching_record_count", 0) or 0
    )
    session["rtt_payload_ready"] = bool(
        session["rtt_pending_derived"] and session["rtt_drain_success"]
    )
    session["rtt_payload_complete"] = bool(
        session["rtt_pending_derived"]
        and session["rtt_drain_success"]
        and session["rtt_drain_complete"]
        and session["rtt_postcheck_passed"]
        and session["rtt_record_count"] == 1
        and session["rtt_matching_record_count"] == 1
        and not session["rtt_payload_timeout"]
        and session["session_error"] is None
    )
    session["rtt_channel_binding_verified"] = bool(session["rtt_payload_complete"])
    session["transport_classification"] = classify_transport_session(session)
    return session


def hardware_run(args: argparse.Namespace) -> int:
    build = require_inside_root(Path(args.build), "build directory")
    log_dir = require_inside_root(Path(args.log_dir), "log directory")
    tmp_dir = require_inside_root(Path(args.tmp_dir), "temporary directory")
    device_image = require_inside_root(Path(args.device_image), "device image")
    log_dir.mkdir(parents=True, exist_ok=True)
    tmp_dir.mkdir(parents=True, exist_ok=True)
    elf, map_path = require_frozen_build(build)
    expected_header, layout = load_frozen_device_header(device_image)

    gdb = Path(args.gdb or shutil.which("arm-none-eabi-gdb") or "")
    nm = Path(args.nm or shutil.which("arm-none-eabi-nm") or "")
    if not gdb.is_file() or not nm.is_file():
        raise DriverError("arm-none-eabi-gdb/nm is unavailable")
    symbols = read_symbol_table(nm, elf)
    required_names = [
        MANAGER_SYMBOL,
        PAGE_VTABLE_SYMBOL,
        PUSH_SYMBOL,
        ENTER_PATH_SYMBOL,
        SELECT_ROW_SYMBOL,
        START_IMPORT_SYMBOL,
        FINISH_IMPORT_SYMBOL,
        GET_BCB_SYMBOL,
        HAL_UPDATE_SYMBOL,
        STRCMP_SYMBOL,
        SD_READY_SYMBOL,
        RTT_SYMBOL,
        OVERLAY_OWNER_SYMBOL,
        OVERLAY_WORKSPACE_SYMBOL,
    ]
    selected_symbols = require_symbols(symbols, required_names)
    if selected_symbols[OVERLAY_WORKSPACE_SYMBOL] != layout["OTA_OVERLAY_ORIGIN"]:
        raise DriverError(
            "overlay symbol does not match ota_layout.h: "
            f"0x{selected_symbols[OVERLAY_WORKSPACE_SYMBOL]:08X} != "
            f"0x{layout['OTA_OVERLAY_ORIGIN']:08X}"
        )

    prefix = args.output_prefix
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", prefix):
        raise DriverError(f"invalid output prefix: {prefix!r}")
    if not args.package_path.startswith("/") or '"' in args.package_path:
        raise DriverError("package path must be an absolute MCU LVGL path without quotes")
    rtt_log = log_dir / f"{prefix}-rtt.raw.log"
    gdb_log = log_dir / f"{prefix}-gdb.log"
    server_log = log_dir / f"{prefix}-jlink-server.log"
    json_path = log_dir / f"{prefix}-result.json"
    rtt_payload_log = log_dir / f"{prefix}-rtt-payload.raw.log"
    rtt_logger_console_log = log_dir / f"{prefix}-rtt-logger-console.log"
    post_gdb_log = log_dir / f"{prefix}-post-gdb.log"
    post_server_log = log_dir / f"{prefix}-post-jlink-server.log"
    post_rtt_log = log_dir / f"{prefix}-post-rtt.raw.log"
    rtt_cb_snapshot = log_dir / f"{prefix}-rtt-cb-pre.bin"
    rtt_ring_snapshot = log_dir / f"{prefix}-rtt-up0-pre.bin"
    post_cb_snapshot = log_dir / f"{prefix}-rtt-cb-post.bin"
    rtt_pending_path = log_dir / f"{prefix}-rtt-pending.bin"
    gdb_script = tmp_dir / f"{prefix}.gdb"
    post_gdb_script = tmp_dir / f"{prefix}-post.gdb"
    outputs = (
        rtt_log,
        gdb_log,
        server_log,
        json_path,
        rtt_payload_log,
        rtt_logger_console_log,
        post_gdb_log,
        post_server_log,
        post_rtt_log,
        rtt_cb_snapshot,
        rtt_ring_snapshot,
        post_cb_snapshot,
        rtt_pending_path,
        gdb_script,
        post_gdb_script,
    )
    for output in outputs:
        require_inside_root(output, "output")
        if output.exists():
            raise DriverError(f"refusing to overwrite existing output: {output}")

    args.kind = args.kind.upper()
    gdb_command_file(
        gdb_script,
        elf,
        selected_symbols,
        expected_header,
        layout,
        args.package_path,
        args.kind,
        rtt_cb_snapshot,
        rtt_ring_snapshot,
    )
    post_snapshot_command_file(
        post_gdb_script, elf, selected_symbols[RTT_SYMBOL], post_cb_snapshot
    )

    base_result: dict[str, object] = {
        "schema": "p2-6-rtt-ota-driver-v2",
        "kind": args.kind,
        "package_path": args.package_path,
        "prepare_only": bool(args.prepare_only),
        "hardware_started": False,
        "build": str(build),
        "elf": str(elf),
        "elf_sha256": sha256_file(elf),
        "map": str(map_path),
        "map_sha256": sha256_file(map_path),
        "device_image": str(device_image),
        "device_image_sha256": sha256_file(device_image),
        "device_header_sha256": hashlib.sha256(expected_header).hexdigest().upper(),
        "page_layout": {
            "page_current_offset": PAGE_CURRENT_OFFSET,
            "page_state_offset": PAGE_STATE_OFFSET,
            "allowed_states": [PAGE_STATE_DID_APPEAR, PAGE_STATE_ACTIVITY],
        },
        "symbols": {
            key: f"0x{value:08X}" for key, value in selected_symbols.items()
        },
        "logs": {
            "rtt": str(rtt_log),
            "gdb": str(gdb_log),
            "server": str(server_log),
            "gdb_script": str(gdb_script),
            "rtt_payload": str(rtt_payload_log),
            "rtt_logger_console": str(rtt_logger_console_log),
            "rtt_cb_pre": str(rtt_cb_snapshot),
            "rtt_up0_pre": str(rtt_ring_snapshot),
            "rtt_cb_post": str(post_cb_snapshot),
            "rtt_pending": str(rtt_pending_path),
            "post_gdb": str(post_gdb_log),
            "post_server": str(post_server_log),
            "post_rtt": str(post_rtt_log),
            "post_gdb_script": str(post_gdb_script),
        },
        "sha256": {"gdb_script": sha256_file(gdb_script), "post_gdb_script": sha256_file(post_gdb_script)},
        "outside_repo_writes": [],
    }
    if args.prepare_only:
        json_path.write_text(
            json.dumps(base_result, indent=2, ensure_ascii=True) + "\n",
            encoding="ascii",
        )
        print(json.dumps(base_result, indent=2, ensure_ascii=True))
        return 0

    session = run_two_phase_ota_session(
        jlink_dir=Path(args.jlink_dir),
        gdb=gdb,
        gdb_script=gdb_script,
        gdb_log=gdb_log,
        server_log=server_log,
        rtt_log=rtt_log,
        tmp_dir=tmp_dir,
        timeout=args.timeout + 90,
        server_ready_timeout=args.server_ready_timeout,
        expected_kind=args.kind,
        rtt_address=selected_symbols[RTT_SYMBOL],
        cb_snapshot=rtt_cb_snapshot,
        ring_snapshot=rtt_ring_snapshot,
        pending_path=rtt_pending_path,
        raw_log=rtt_payload_log,
        console_log=rtt_logger_console_log,
        post_gdb_script=post_gdb_script,
        post_gdb_log=post_gdb_log,
        post_server_log=post_server_log,
        post_rtt_log=post_rtt_log,
        post_cb_snapshot=post_cb_snapshot,
    )
    raw = rtt_payload_log.read_bytes() if rtt_payload_log.exists() else b""
    try:
        measurements = parse_measurements(raw)
    except DriverError:
        measurements = []
    matching = [record for record in measurements if record["kind"] == args.kind]
    classifications = [classify_measurement(record) for record in matching]
    result = {
        **base_result,
        "hardware_started": bool(session["server_started"]),
        "session": session,
        "measurements": matching,
        "classifications": classifications,
    }
    result["outside_repo_writes"] = (
        [AUTHORIZED_SEGGER_WRITE] if session["server_started"] else []
    )
    result["sha256"] = {
        "rtt": sha256_file(rtt_log) if rtt_log.exists() else None,
        "gdb": sha256_file(gdb_log) if gdb_log.exists() else None,
        "server": sha256_file(server_log) if server_log.exists() else None,
        "gdb_script": sha256_file(gdb_script),
        "post_gdb_script": sha256_file(post_gdb_script),
        "rtt_payload": sha256_file(rtt_payload_log) if rtt_payload_log.exists() else None,
        "rtt_logger_console": (
            sha256_file(rtt_logger_console_log)
            if rtt_logger_console_log.exists()
            else None
        ),
        "rtt_cb_pre": sha256_file(rtt_cb_snapshot) if rtt_cb_snapshot.exists() else None,
        "rtt_up0_pre": sha256_file(rtt_ring_snapshot) if rtt_ring_snapshot.exists() else None,
        "rtt_cb_post": sha256_file(post_cb_snapshot) if post_cb_snapshot.exists() else None,
        "rtt_pending": sha256_file(rtt_pending_path) if rtt_pending_path.exists() else None,
        "post_gdb": sha256_file(post_gdb_log) if post_gdb_log.exists() else None,
        "post_server": sha256_file(post_server_log) if post_server_log.exists() else None,
        "post_rtt": sha256_file(post_rtt_log) if post_rtt_log.exists() else None,
    }
    json_path.write_text(
        json.dumps(result, indent=2, ensure_ascii=True) + "\n", encoding="ascii"
    )

    if session["session_error"]:
        raise DriverError(f"GDB/RTT session failed: {session['session_error']}")
    if session["gdb_exit_code"] != 0:
        raise DriverError(
            f"GDB driver failed with exit code {session['gdb_exit_code']}; see {gdb_log}"
        )
    if len(measurements) != 1 or len(matching) != 1:
        raise DriverError(
            f"expected exactly one {args.kind} P2_6 record, "
            f"found total={len(measurements)} matching={len(matching)}; see {rtt_payload_log}"
        )
    if (
        not session["rtt_payload_complete"]
        or not session["rtt_channel_binding_verified"]
    ):
        raise DriverError(
            "RTT measurement payload was not completely captured and bound "
            "(pending derive + logger byte identity + postcheck); "
            f"ready={session['rtt_payload_ready']} "
            f"drain={session['rtt_drain_complete']} "
            f"postcheck={session['rtt_postcheck_passed']}"
        )
    checks = classifications[0]
    required = (
        "result_ok",
        "workspace_ok",
        "stack_ok",
        "guard_ok",
        "sbrk_ok",
        "tlsf_required_ok",
    )
    if not all(checks[key] for key in required):
        raise DriverError(f"P2-6 product gate failed: {checks}")
    print(json.dumps(result, indent=2, ensure_ascii=True))
    return 0


def parser_selftest() -> int:
    sample = (
        b"noise\r\n"
        b"P2_6 kind=FULL result=0 workspace_peak=35492 "
        b"arena_peak_observed=35492 failed_request_size=0 "
        b"stack_entry=512 stack_peak=1296 stack_total=8192 "
        b"guard_entry=1 guard_exit=1 sbrk_delta=0 sbrk_peak=536891392 "
        b"tlsf_malloc_delta=0 tlsf_realloc_delta=0 tlsf_free_delta=0 "
        b"lv_free_entry=90000 lv_free_exit=90000 "
        b"lv_big_entry=80000 lv_big_exit=80000 "
        b"lv_frag_entry=2 lv_frag_exit=2 lv_max_entry=131072 lv_max_exit=131072 "
        b"seq=0 last_size=0 last_ret=0x0\r\n"
    )
    records = parse_measurements(sample)
    if len(records) != 1 or records[0]["workspace_peak"] != 35492:
        raise DriverError("measurement parser self-test failed")
    checks = classify_measurement(records[0])
    if not all(
        checks[key]
        for key in (
            "result_ok",
            "workspace_ok",
            "stack_ok",
            "guard_ok",
            "sbrk_ok",
            "tlsf_required_ok",
            "tlsf_free_zero",
            "lv_pool_net_unchanged",
        )
    ):
        raise DriverError("measurement classifier self-test failed")
    print("P2_6_RTT_OTA_DRIVER_SELFTEST=PASS checks=9")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--kind", type=str.upper, choices=("FULL", "PATCH"))
    parser.add_argument("--package-path")
    parser.add_argument("--output-prefix", default="p2-6-rtt-ota")
    parser.add_argument("--build", default=str(DEFAULT_BUILD))
    parser.add_argument("--device-image", default=str(DEFAULT_DEVICE_IMAGE))
    parser.add_argument("--log-dir", default=str(DEFAULT_LOG_DIR))
    parser.add_argument("--tmp-dir", default=str(DEFAULT_TMP_DIR))
    parser.add_argument("--jlink-dir", default=str(DEFAULT_JLINK_DIR))
    parser.add_argument("--gdb")
    parser.add_argument("--nm")
    parser.add_argument("--timeout", type=int, default=240)
    parser.add_argument("--server-ready-timeout", type=float, default=45.0)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.self_test:
        return parser_selftest()
    if not args.kind or not args.package_path:
        parser.error("--kind and --package-path are required")
    try:
        return hardware_run(args)
    except DriverError as exc:
        print(f"P2_6_RTT_OTA_DRIVER=FAIL {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
