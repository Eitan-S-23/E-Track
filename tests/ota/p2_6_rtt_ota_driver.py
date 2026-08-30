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


class RttCapture(threading.Thread):
    def __init__(
        self,
        host: str,
        port: int,
        output: Path,
        stop: threading.Event,
        connect_timeout: float = 60.0,
        measurement_policy: bool = False,
        expected_kind: str | None = None,
    ):
        super().__init__(daemon=True)
        self.host = host
        self.port = port
        self.output = output
        self.stop_event = stop
        self.connect_timeout = connect_timeout
        self.measurement_policy = measurement_policy
        self.expected_kind = expected_kind.upper() if expected_kind else None
        self.error: str | None = None
        self.connected = threading.Event()
        self.socket_connected = False
        self.socket_eof = False
        self.socket_error = False
        self.payload_ready = False
        self.drain_started = False
        self.drain_success = False
        self.drain_complete = False
        self.drain_deadline_expired = False
        self.payload_timeout = False
        self._buffer = bytearray()
        self._state = threading.Condition()
        self._byte_generation = 0

    def wait_for_bounded_drain(self, timeout: float, quiet_timeout: float = 0.1) -> None:
        outer_deadline = time.monotonic() + timeout
        with self._state:
            self.drain_started = True
            self.drain_success = False
            self.drain_complete = False
            self.drain_deadline_expired = False
            self.payload_timeout = False
            quiet_deadline: float | None = None
            quiet_generation = self._byte_generation
            while True:
                if self.socket_eof or self.socket_error or self.error:
                    self.drain_complete = False
                    return
                now = time.monotonic()
                if now >= outer_deadline:
                    self.drain_deadline_expired = True
                    self.payload_timeout = True
                    self.drain_complete = False
                    return
                if self.payload_ready:
                    if quiet_deadline is None or quiet_generation != self._byte_generation:
                        quiet_generation = self._byte_generation
                        quiet_deadline = now + quiet_timeout
                    elif now >= quiet_deadline:
                        self.drain_success = True
                        self.drain_complete = True
                        return
                else:
                    quiet_deadline = None
                wait_until = outer_deadline
                if quiet_deadline is not None:
                    wait_until = min(wait_until, quiet_deadline)
                self._state.wait(timeout=max(0.0, wait_until - now))

    def run(self) -> None:
        deadline = time.monotonic() + self.connect_timeout
        sock: socket.socket | None = None
        try:
            while time.monotonic() < deadline and not self.stop_event.is_set():
                try:
                    sock = socket.create_connection((self.host, self.port), timeout=1.0)
                    self.socket_connected = True
                    self.connected.set()
                    break
                except OSError:
                    time.sleep(0.2)
            if sock is None:
                raise DriverError(f"RTT Telnet did not open on {self.host}:{self.port}")
            sock.settimeout(0.5)
            with self.output.open("wb") as stream:
                while not self.stop_event.is_set():
                    try:
                        chunk = sock.recv(4096)
                    except socket.timeout:
                        continue
                    except OSError:
                        if self.stop_event.is_set():
                            break
                        with self._state:
                            self.socket_error = True
                            self._state.notify_all()
                        raise
                    if not chunk:
                        with self._state:
                            self.socket_eof = True
                            self._state.notify_all()
                        break
                    with self._state:
                        self._buffer.extend(chunk)
                        self._byte_generation += 1
                        if self.measurement_policy:
                            try:
                                last_newline = self._buffer.rfind(b"\n")
                                if last_newline >= 0:
                                    complete = bytes(self._buffer[:last_newline + 1])
                                    records = parse_measurements(complete)
                                    matching = [
                                        record
                                        for record in records
                                        if record["kind"] == self.expected_kind
                                    ]
                                    self.payload_ready = (
                                        len(records) == 1 and len(matching) == 1
                                    )
                                    self._state.notify_all()
                            except DriverError as exc:
                                self.error = str(exc)
                                self._state.notify_all()
                                break
                    stream.write(chunk)
                    stream.flush()
        except Exception as exc:  # pragma: no cover - exercised on hardware
            if not self.stop_event.is_set():
                if self.error is None:
                    self.error = str(exc)
                self.socket_error = True
        finally:
            with self._state:
                self._state.notify_all()
            if sock is not None:
                sock.close()


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
    if outcome.get("rtt_measurement_required") and (
        not outcome["rtt_payload_ready"]
        or not outcome.get("rtt_drain_success")
        or not outcome["rtt_drain_complete"]
        or outcome.get("rtt_drain_deadline_expired")
        or not outcome["rtt_payload_complete"]
        or outcome.get("rtt_socket_eof")
        or outcome.get("rtt_socket_error")
        or outcome.get("rtt_payload_timeout")
        or outcome.get("capture_error")
        or outcome["rtt_record_count"] != 1
        or outcome.get("rtt_matching_record_count") != 1
    ):
        return "RTT_PAYLOAD_FAIL"
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
    drain_timeout: float = 2.0,
    quiet_timeout: float = 0.1,
) -> dict[str, object]:
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
        "rtt_payload_ready": False,
        "rtt_drain_started": False,
        "rtt_drain_success": False,
        "rtt_drain_complete": False,
        "rtt_drain_deadline_expired": False,
        "rtt_payload_complete": False,
        "rtt_payload_timeout": False,
        "rtt_record_count": 0,
        "rtt_channel_binding_verified": False,
        "rtt_measurement_required": bool(measurement_policy),
        "capture_stopped": True,
        "ports_closed": False,
        "session_error": None,
        "transport_classification": None,
    }
    stop = threading.Event()
    capture = RttCapture(
        "127.0.0.1",
        RTT_PORT,
        rtt_log,
        stop,
        measurement_policy=measurement_policy,
        expected_kind=expected_kind,
    )
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
        capture.start()
        if not capture.connected.wait(timeout=5.0) or not capture.socket_connected:
            raise DriverError("RTT Telnet connection was not established")
        outcome["rtt_connected"] = True
        outcome["rtt_socket_connected"] = bool(capture.socket_connected)
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
        if measurement_policy and capture.ident is not None and not capture.drain_complete:
            capture.wait_for_bounded_drain(drain_timeout, quiet_timeout)
        stop.set()
        if capture.ident is not None:
            capture.join(timeout=5.0)
            outcome["capture_stopped"] = not capture.is_alive()
        outcome["capture_error"] = capture.error
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
    raw = rtt_log.read_bytes() if rtt_log.exists() else b""
    if measurement_policy:
        try:
            parsed_records = parse_measurements(raw)
            parse_error = None
        except DriverError as exc:
            parsed_records = []
            parse_error = str(exc)
    else:
        parsed_records = []
        parse_error = None
    outcome["rtt_socket_connected"] = bool(
        outcome["rtt_socket_connected"] or getattr(capture, "socket_connected", False)
    )
    normalized_expected_kind = expected_kind.upper() if expected_kind else None
    matching = (
        [record for record in parsed_records if record["kind"] == normalized_expected_kind]
        if measurement_policy and normalized_expected_kind
        else []
    )
    outcome["rtt_payload_ready"] = bool(
        measurement_policy
        and getattr(capture, "payload_ready", False)
        and len(parsed_records) == 1
        and len(matching) == 1
        and not parse_error
        and not outcome["capture_error"]
        and not getattr(capture, "socket_error", False)
    )
    outcome["rtt_socket_eof"] = bool(getattr(capture, "socket_eof", False))
    outcome["rtt_socket_error"] = bool(getattr(capture, "socket_error", False))
    outcome["rtt_payload_timeout"] = bool(getattr(capture, "payload_timeout", False))
    outcome["rtt_drain_started"] = bool(getattr(capture, "drain_started", False))
    outcome["rtt_drain_success"] = bool(getattr(capture, "drain_success", False))
    outcome["rtt_drain_complete"] = bool(
        measurement_policy and getattr(capture, "drain_complete", False)
    )
    outcome["rtt_drain_deadline_expired"] = bool(
        getattr(capture, "drain_deadline_expired", False)
    )
    outcome["rtt_record_count"] = len(parsed_records)
    outcome["rtt_payload_complete"] = bool(
        len(parsed_records) == 1
        and len(matching) == 1
        and parse_error is None
        and outcome["rtt_drain_complete"]
        and outcome["rtt_drain_success"]
        and not outcome["rtt_drain_deadline_expired"]
        and not outcome["capture_error"]
        and not outcome["rtt_socket_error"]
        and not outcome["rtt_socket_eof"]
        and not outcome["rtt_payload_timeout"]
    )
    outcome["rtt_channel_binding_verified"] = False
    if measurement_policy and parse_error:
        prior = outcome["session_error"]
        outcome["session_error"] = (
            f"{prior}; RTT payload parse failed: {parse_error}"
            if prior
            else f"RTT payload parse failed: {parse_error}"
        )
    outcome["rtt_payload_parse_error"] = parse_error
    if measurement_policy and normalized_expected_kind:
        outcome["rtt_expected_kind"] = normalized_expected_kind
        outcome["rtt_matching_record_count"] = len(matching)
    cleanup_errors: list[str] = []
    if not outcome["capture_stopped"]:
        cleanup_errors.append("RTT capture thread did not stop")
    if not outcome["ports_closed"]:
        cleanup_errors.append("J-Link listener ports remain open")
    if outcome["capture_error"]:
        cleanup_errors.append(f"RTT capture error: {outcome['capture_error']}")
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
    outcome["transport_classification"] = classify_transport_session(outcome)
    return outcome


def gdb_command_file(
    path: Path,
    elf: Path,
    symbols: dict[str, int],
    expected_header: bytes,
    layout: dict[str, int],
    package_path: str,
    expected_kind: str,
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
        "detach",
        "quit",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="ascii")


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
    gdb_script = tmp_dir / f"{prefix}.gdb"
    for output in (rtt_log, gdb_log, server_log, json_path, gdb_script):
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
        },
        "sha256": {"gdb_script": sha256_file(gdb_script)},
        "outside_repo_writes": [],
    }
    if args.prepare_only:
        json_path.write_text(
            json.dumps(base_result, indent=2, ensure_ascii=True) + "\n",
            encoding="ascii",
        )
        print(json.dumps(base_result, indent=2, ensure_ascii=True))
        return 0

    session = run_gdb_session(
        jlink_dir=Path(args.jlink_dir),
        gdb=gdb,
        gdb_script=gdb_script,
        gdb_log=gdb_log,
        server_log=server_log,
        rtt_log=rtt_log,
        tmp_dir=tmp_dir,
        timeout=args.timeout + 90,
        server_ready_timeout=args.server_ready_timeout,
        measurement_policy=True,
        expected_kind=args.kind,
    )
    raw = rtt_log.read_bytes() if rtt_log.exists() else b""
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
            f"found total={len(measurements)} matching={len(matching)}; see {rtt_log}"
        )
    if not session["rtt_payload_complete"] or not session["rtt_drain_complete"]:
        raise DriverError(
            "RTT measurement payload was not complete after bounded drain; "
            f"ready={session['rtt_payload_ready']} drain={session['rtt_drain_complete']}"
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
