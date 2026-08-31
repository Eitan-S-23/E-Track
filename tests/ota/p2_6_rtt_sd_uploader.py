#!/usr/bin/env python3
"""Upload one frozen P2-6 OTA asset to SD through stopped-target GDB calls.

The uploader has no PageManager dependency. It binds readiness to the exact
test ELF/map and device image, RTT, SD, VTOR/CFSR, BCB, overlay ownership,
file API results, byte counts, and a strict MI readback SHA-256 comparison.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys


THIS_DIR = Path(__file__).resolve().parent
if str(THIS_DIR) not in sys.path:
    sys.path.insert(0, str(THIS_DIR))

import p2_6_rtt_ota_driver as driver


LV_FS_OPEN_SYMBOL = "lv_fs_open"
LV_FS_CLOSE_SYMBOL = "lv_fs_close"
LV_FS_READ_SYMBOL = "lv_fs_read"
LV_FS_WRITE_SYMBOL = "lv_fs_write"
LV_FS_SEEK_SYMBOL = "lv_fs_seek"
LV_FS_TELL_SYMBOL = "lv_fs_tell"

LV_FS_RES_OK = 0
LV_FS_RES_UNKNOWN = 12
LV_FS_MODE_WR_RD = 3
LV_FS_MODE_RD = 2
LV_FS_SEEK_SET = 0
LV_FS_SEEK_END = 2
UPLOAD_CHUNK_SIZE = 0x8000
PATH_OFFSET = 0x9E00
FILE_OFFSET = 0x9F20
COUNT_OFFSET = 0x9F40
LV_FS_FILE_SIZE = 12
MAX_MCU_PATH_BYTES = 255
GDB_MEMORY_BLOCK_SIZE = 1024

FROZEN_PATCH_SHA256 = (
    "2B0ACCAEABD88572F1DAE98A7AB66DF511F48D099530537281FDA36AF37C9D2B"
)
FROZEN_FULL_SHA256 = (
    "84D3F38420A9521FEEC1251CCE13A76F83F862935C2846A30D09DE1EC96DD2E7"
)
FROZEN_ASSETS = {
    FROZEN_PATCH_SHA256: "PATCH",
    FROZEN_FULL_SHA256: "FULL",
}

MI_BEGIN_RE = re.compile(
    r"^P2_6_MI_READ_BEGIN chunk=(?P<chunk>\d+) block=(?P<block>\d+) "
    r"address=0x(?P<address>[0-9A-Fa-f]+) size=(?P<size>\d+)$"
)
MI_END_RE = re.compile(
    r"^P2_6_MI_READ_END chunk=(?P<chunk>\d+) block=(?P<block>\d+)$"
)
MI_RESPONSE_RE = re.compile(
    r'^\^done,memory=\[\{begin="(?P<begin>0x[0-9A-Fa-f]+)",'
    r'offset="(?P<offset>0x[0-9A-Fa-f]+)",'
    r'end="(?P<end>0x[0-9A-Fa-f]+)",'
    r'contents="(?P<contents>[0-9A-Fa-f]*)"\}\]$'
)


class UploadError(driver.DriverError):
    pass


def split_chunks(source: Path, output_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=False)
    chunks: list[Path] = []
    with source.open("rb") as stream:
        index = 0
        while True:
            data = stream.read(UPLOAD_CHUNK_SIZE)
            if not data:
                break
            chunk = output_dir / f"source-{index:03d}.bin"
            chunk.write_bytes(data)
            chunks.append(chunk)
            index += 1
    if not chunks:
        raise UploadError("input file is empty")
    return chunks


def validate_mcu_path(path: str) -> bytes:
    if not path.startswith("/") or '"' in path or "\n" in path or "\r" in path:
        raise UploadError("MCU path must be absolute and contain no quotes/newlines")
    encoded = path.encode("ascii", errors="strict")
    if len(encoded) > MAX_MCU_PATH_BYTES:
        raise UploadError(f"MCU path exceeds {MAX_MCU_PATH_BYTES} ASCII bytes")
    return encoded + b"\0"


def validate_frozen_asset(source: Path) -> tuple[str, str]:
    digest = driver.sha256_file(source)
    kind = FROZEN_ASSETS.get(digest)
    if kind is None:
        raise UploadError(f"input is not a frozen P2-6 FULL/PATCH asset: {digest}")
    return kind, digest


def mi_write_memory_lines(address: int, data: bytes) -> list[str]:
    lines: list[str] = []
    for offset in range(0, len(data), GDB_MEMORY_BLOCK_SIZE):
        block = data[offset:offset + GDB_MEMORY_BLOCK_SIZE]
        lines.append(
            'interpreter-exec mi "-data-write-memory-bytes '
            f'0x{address + offset:08x} {block.hex()}"'
        )
    return lines


def expected_mi_read_blocks(
    address: int, chunk_sizes: list[int]
) -> list[dict[str, int]]:
    blocks: list[dict[str, int]] = []
    for chunk_index, chunk_size in enumerate(chunk_sizes):
        if chunk_size <= 0:
            raise UploadError(f"invalid readback chunk size at {chunk_index}: {chunk_size}")
        block_index = 0
        for offset in range(0, chunk_size, GDB_MEMORY_BLOCK_SIZE):
            size = min(GDB_MEMORY_BLOCK_SIZE, chunk_size - offset)
            blocks.append(
                {
                    "chunk": chunk_index,
                    "block": block_index,
                    "address": address + offset,
                    "size": size,
                }
            )
            block_index += 1
    return blocks


def mi_read_memory_lines(address: int, size: int, chunk_index: int) -> list[str]:
    lines: list[str] = []
    block_index = 0
    for offset in range(0, size, GDB_MEMORY_BLOCK_SIZE):
        block_size = min(GDB_MEMORY_BLOCK_SIZE, size - offset)
        block_address = address + offset
        lines.extend(
            [
                f'printf "P2_6_MI_READ_BEGIN chunk={chunk_index} block={block_index} address=0x{block_address:08x} size={block_size}\\n"',
                'interpreter-exec mi "-data-read-memory-bytes '
                f'0x{block_address:08x} {block_size}"',
                f'printf "P2_6_MI_READ_END chunk={chunk_index} block={block_index}\\n"',
            ]
        )
        block_index += 1
    return lines


def parse_mi_readback(
    raw: bytes, chunk_sizes: list[int], address: int
) -> tuple[bytes, list[dict[str, object]]]:
    text = raw.decode("utf-8", errors="replace").replace("\r", "")
    events: list[tuple[str, object]] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line.startswith("^error"):
            raise UploadError(f"MI command error in GDB log: {line}")
        begin = MI_BEGIN_RE.fullmatch(line)
        if begin:
            events.append(
                (
                    "begin",
                    {
                        "chunk": int(begin.group("chunk")),
                        "block": int(begin.group("block")),
                        "address": int(begin.group("address"), 16),
                        "size": int(begin.group("size")),
                    },
                )
            )
            continue
        response = MI_RESPONSE_RE.fullmatch(line)
        if response:
            events.append(("response", response.groupdict()))
            continue
        if line.startswith("^done,memory="):
            raise UploadError(f"malformed MI memory response: {line}")
        end = MI_END_RE.fullmatch(line)
        if end:
            events.append(
                (
                    "end",
                    {"chunk": int(end.group("chunk")), "block": int(end.group("block"))},
                )
            )

    expected = expected_mi_read_blocks(address, chunk_sizes)
    if len(events) != len(expected) * 3:
        raise UploadError(
            f"MI readback event count mismatch: {len(events)} != {len(expected) * 3}"
        )

    data_parts: list[bytes] = []
    adopted: list[dict[str, object]] = []
    for index, spec in enumerate(expected):
        begin_type, begin_value = events[index * 3]
        response_type, response_value = events[index * 3 + 1]
        end_type, end_value = events[index * 3 + 2]
        if begin_type != "begin" or response_type != "response" or end_type != "end":
            raise UploadError(
                f"MI readback block ordering error at chunk={spec['chunk']} block={spec['block']}"
            )
        if begin_value != spec:
            raise UploadError(
                f"MI readback begin mismatch: observed={begin_value} expected={spec}"
            )
        expected_end = {"chunk": spec["chunk"], "block": spec["block"]}
        if end_value != expected_end:
            raise UploadError(
                f"MI readback end mismatch: observed={end_value} expected={expected_end}"
            )
        assert isinstance(response_value, dict)
        begin_address = int(str(response_value["begin"]), 16)
        offset = int(str(response_value["offset"]), 16)
        end_address = int(str(response_value["end"]), 16)
        contents = str(response_value["contents"])
        if len(contents) % 2 != 0:
            raise UploadError(
                f"MI readback has odd hex length at chunk={spec['chunk']} block={spec['block']}"
            )
        block_data = bytes.fromhex(contents)
        if (
            begin_address != spec["address"]
            or offset != 0
            or end_address != spec["address"] + spec["size"]
            or len(block_data) != spec["size"]
        ):
            raise UploadError(
                "MI readback range mismatch: "
                f"chunk={spec['chunk']} block={spec['block']} "
                f"begin=0x{begin_address:08X} offset={offset} "
                f"end=0x{end_address:08X} bytes={len(block_data)} expected={spec}"
            )
        data_parts.append(block_data)
        adopted.append(
            {
                **spec,
                "begin": f"0x{begin_address:08X}",
                "end": f"0x{end_address:08X}",
                "sha256": hashlib.sha256(block_data).hexdigest().upper(),
            }
        )
    return b"".join(data_parts), adopted


def upload_gdb_command_file(
    path: Path,
    elf: Path,
    symbols: dict[str, int],
    expected_header: bytes,
    layout: dict[str, int],
    chunks: list[Path],
    path_blob: Path,
    total_size: int,
) -> None:
    overlay = symbols[driver.OVERLAY_WORKSPACE_SYMBOL]
    buffer_addr = overlay
    path_addr = overlay + PATH_OFFSET
    file_addr = overlay + FILE_OFFSET
    count_addr = overlay + COUNT_OFFSET
    overlay_size = layout["OTA_OVERLAY_WORKSPACE_LENGTH"]
    if total_size <= 0:
        raise UploadError("invalid upload chunk plan")
    if COUNT_OFFSET + 4 > overlay_size:
        raise UploadError("upload control layout exceeds OTA overlay workspace")
    if UPLOAD_CHUNK_SIZE > PATH_OFFSET:
        raise UploadError("upload data buffer overlaps control layout")

    def thumb(name: str) -> int:
        return symbols[name] | 1

    def clear_file() -> list[str]:
        return [
            f"set {{unsigned int}}0x{file_addr:08x} = 0",
            f"set {{unsigned int}}0x{file_addr + 4:08x} = 0",
            f"set {{unsigned int}}0x{file_addr + 8:08x} = 0",
        ]

    update_entry = symbols[driver.HAL_UPDATE_SYMBOL]
    lines = [
        *driver.gdb_prologue_lines(elf),
        *driver.deterministic_stop_lines(
            update_entry, "upload_hal_update", 0x50326101, 40, attach=True
        ),
        *driver.runtime_state_lines(
            symbols,
            expected_header,
            layout,
            "before_upload",
            driver.BCB_STATE_CONFIRMED,
            41,
        ),
        *mi_write_memory_lines(path_addr, path_blob.read_bytes()),
        *clear_file(),
        f"set $probe = ((unsigned char (*)(void*, const char*, unsigned char))0x{thumb(LV_FS_OPEN_SYMBOL):08x})((void*)0x{file_addr:08x}, (const char*)0x{path_addr:08x}, {LV_FS_MODE_RD})",
        *driver.assert_stopped_at_lines(update_entry, "probe_open_return", 42),
        f"if $probe == {LV_FS_RES_OK}",
        f"  set $close_probe = ((unsigned char (*)(void*))0x{thumb(LV_FS_CLOSE_SYMBOL):08x})((void*)0x{file_addr:08x})",
        '  printf "P2_6_SD_UPLOAD ERROR target_exists close=%u\\n", $close_probe',
        "  quit 43",
        "end",
        f"if $probe != {LV_FS_RES_UNKNOWN}",
        f'  printf "P2_6_SD_UPLOAD ERROR target_probe_unexpected res=%u expected_unknown={LV_FS_RES_UNKNOWN}\\n", $probe',
        "  quit 44",
        "end",
        'printf "P2_6_SD_UPLOAD target_absent probe_res=%u\\n", $probe',
        *clear_file(),
        f"set $open = ((unsigned char (*)(void*, const char*, unsigned char))0x{thumb(LV_FS_OPEN_SYMBOL):08x})((void*)0x{file_addr:08x}, (const char*)0x{path_addr:08x}, {LV_FS_MODE_WR_RD})",
        *driver.assert_stopped_at_lines(update_entry, "create_open_return", 45),
        f"if $open != {LV_FS_RES_OK}",
        '  printf "P2_6_SD_UPLOAD ERROR create_failed res=%u\\n", $open',
        "  quit 46",
        "end",
    ]

    for index, chunk in enumerate(chunks):
        data = chunk.read_bytes()
        size = len(data)
        lines.extend(
            [
                *mi_write_memory_lines(buffer_addr, data),
                f"set {{unsigned int}}0x{count_addr:08x} = 0",
                f"set $wr = ((unsigned char (*)(void*, const void*, unsigned int, unsigned int*))0x{thumb(LV_FS_WRITE_SYMBOL):08x})((void*)0x{file_addr:08x}, (const void*)0x{buffer_addr:08x}, {size}, (unsigned int*)0x{count_addr:08x})",
                *driver.assert_stopped_at_lines(
                    update_entry, f"write_chunk_{index}_return", 46
                ),
                f"set $written = *(unsigned int*)0x{count_addr:08x}",
                f'printf "P2_6_SD_UPLOAD write chunk={index} res=%u bytes=%u\\n", $wr, $written',
                f"if $wr != {LV_FS_RES_OK} || $written != {size}",
                f"  set $close_write_error = ((unsigned char (*)(void*))0x{thumb(LV_FS_CLOSE_SYMBOL):08x})((void*)0x{file_addr:08x})",
                '  printf "P2_6_SD_UPLOAD ERROR write_failed close=%u\\n", $close_write_error',
                "  quit 47",
                "end",
            ]
        )

    lines.extend(
        [
            f"set {{unsigned int}}0x{count_addr:08x} = 0",
            f"set $tell_write = ((unsigned char (*)(void*, unsigned int*))0x{thumb(LV_FS_TELL_SYMBOL):08x})((void*)0x{file_addr:08x}, (unsigned int*)0x{count_addr:08x})",
            *driver.assert_stopped_at_lines(update_entry, "tell_write_return", 48),
            f"set $write_size = *(unsigned int*)0x{count_addr:08x}",
            f"if $tell_write != {LV_FS_RES_OK} || $write_size != {total_size}",
            f"  set $close_size = ((unsigned char (*)(void*))0x{thumb(LV_FS_CLOSE_SYMBOL):08x})((void*)0x{file_addr:08x})",
            '  printf "P2_6_SD_UPLOAD ERROR write_size res=%u size=%u close=%u\\n", $tell_write, $write_size, $close_size',
            "  quit 49",
            "end",
            f"set $close_write = ((unsigned char (*)(void*))0x{thumb(LV_FS_CLOSE_SYMBOL):08x})((void*)0x{file_addr:08x})",
            *driver.assert_stopped_at_lines(update_entry, "close_write_return", 50),
            f"if $close_write != {LV_FS_RES_OK}",
            '  printf "P2_6_SD_UPLOAD ERROR close_write res=%u\\n", $close_write',
            "  quit 51",
            "end",
            *clear_file(),
            f"set $reopen = ((unsigned char (*)(void*, const char*, unsigned char))0x{thumb(LV_FS_OPEN_SYMBOL):08x})((void*)0x{file_addr:08x}, (const char*)0x{path_addr:08x}, {LV_FS_MODE_RD})",
            *driver.assert_stopped_at_lines(update_entry, "reopen_return", 52),
            f"if $reopen != {LV_FS_RES_OK}",
            '  printf "P2_6_SD_UPLOAD ERROR reopen_failed res=%u\\n", $reopen',
            "  quit 53",
            "end",
            f"set $seek_end = ((unsigned char (*)(void*, unsigned int, unsigned char))0x{thumb(LV_FS_SEEK_SYMBOL):08x})((void*)0x{file_addr:08x}, 0, {LV_FS_SEEK_END})",
            *driver.assert_stopped_at_lines(update_entry, "seek_end_return", 54),
            f"set {{unsigned int}}0x{count_addr:08x} = 0",
            f"set $tell_read = ((unsigned char (*)(void*, unsigned int*))0x{thumb(LV_FS_TELL_SYMBOL):08x})((void*)0x{file_addr:08x}, (unsigned int*)0x{count_addr:08x})",
            *driver.assert_stopped_at_lines(update_entry, "tell_read_return", 55),
            f"set $read_size = *(unsigned int*)0x{count_addr:08x}",
            f"if $seek_end != {LV_FS_RES_OK} || $tell_read != {LV_FS_RES_OK} || $read_size != {total_size}",
            f"  set $close_reopen = ((unsigned char (*)(void*))0x{thumb(LV_FS_CLOSE_SYMBOL):08x})((void*)0x{file_addr:08x})",
            '  printf "P2_6_SD_UPLOAD ERROR read_size seek=%u tell=%u size=%u close=%u\\n", $seek_end, $tell_read, $read_size, $close_reopen',
            "  quit 56",
            "end",
            f"set $seek_start = ((unsigned char (*)(void*, unsigned int, unsigned char))0x{thumb(LV_FS_SEEK_SYMBOL):08x})((void*)0x{file_addr:08x}, 0, {LV_FS_SEEK_SET})",
            *driver.assert_stopped_at_lines(update_entry, "seek_start_return", 57),
            f"if $seek_start != {LV_FS_RES_OK}",
            f"  set $close_seek = ((unsigned char (*)(void*))0x{thumb(LV_FS_CLOSE_SYMBOL):08x})((void*)0x{file_addr:08x})",
            '  printf "P2_6_SD_UPLOAD ERROR seek_start res=%u close=%u\\n", $seek_start, $close_seek',
            "  quit 58",
            "end",
        ]
    )

    for index, chunk in enumerate(chunks):
        size = chunk.stat().st_size
        lines.extend(
            [
                f"set {{unsigned int}}0x{count_addr:08x} = 0",
                f"set $rd = ((unsigned char (*)(void*, void*, unsigned int, unsigned int*))0x{thumb(LV_FS_READ_SYMBOL):08x})((void*)0x{file_addr:08x}, (void*)0x{buffer_addr:08x}, {size}, (unsigned int*)0x{count_addr:08x})",
                *driver.assert_stopped_at_lines(
                    update_entry, f"read_chunk_{index}_return", 59
                ),
                f"set $read = *(unsigned int*)0x{count_addr:08x}",
                f'printf "P2_6_SD_UPLOAD read chunk={index} res=%u bytes=%u\\n", $rd, $read',
                f"if $rd != {LV_FS_RES_OK} || $read != {size}",
                f"  set $close_read_error = ((unsigned char (*)(void*))0x{thumb(LV_FS_CLOSE_SYMBOL):08x})((void*)0x{file_addr:08x})",
                '  printf "P2_6_SD_UPLOAD ERROR read_failed close=%u\\n", $close_read_error',
                "  quit 60",
                "end",
                *mi_read_memory_lines(buffer_addr, size, index),
            ]
        )

    lines.extend(
        [
            f"set $close_read = ((unsigned char (*)(void*))0x{thumb(LV_FS_CLOSE_SYMBOL):08x})((void*)0x{file_addr:08x})",
            *driver.assert_stopped_at_lines(update_entry, "close_read_return", 61),
            f"if $close_read != {LV_FS_RES_OK}",
            '  printf "P2_6_SD_UPLOAD ERROR close_read res=%u\\n", $close_read',
            "  quit 62",
            "end",
            *driver.runtime_state_lines(
                symbols,
                expected_header,
                layout,
                "after_upload",
                driver.BCB_STATE_CONFIRMED,
                63,
            ),
            f'printf "P2_6_SD_UPLOAD PASS bytes={total_size} chunks={len(chunks)}\\n"',
            "detach",
            "quit",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="ascii")


def upload(args: argparse.Namespace) -> int:
    source = driver.require_inside_root(Path(args.input), "input")
    build = driver.require_inside_root(Path(args.build), "build directory")
    log_dir = driver.require_inside_root(Path(args.log_dir), "log directory")
    tmp_dir = driver.require_inside_root(Path(args.tmp_dir), "temporary directory")
    device_image = driver.require_inside_root(Path(args.device_image), "device image")
    if not source.is_file():
        raise UploadError(f"input does not exist: {source}")
    asset_kind, source_hash = validate_frozen_asset(source)
    path_bytes = validate_mcu_path(args.mcu_path)
    prefix = args.output_prefix
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", prefix):
        raise UploadError(f"invalid output prefix: {prefix!r}")

    elf, map_path = driver.require_frozen_build(build)
    expected_header, layout = driver.load_frozen_device_header(device_image)
    gdb = Path(args.gdb or shutil.which("arm-none-eabi-gdb") or "")
    nm = Path(args.nm or shutil.which("arm-none-eabi-nm") or "")
    if not gdb.is_file() or not nm.is_file():
        raise UploadError("arm-none-eabi-gdb/nm is unavailable")
    symbols = driver.read_symbol_table(nm, elf)
    required = [
        driver.GET_BCB_SYMBOL,
        driver.HAL_UPDATE_SYMBOL,
        driver.SD_READY_SYMBOL,
        driver.RTT_SYMBOL,
        driver.OVERLAY_OWNER_SYMBOL,
        driver.OVERLAY_WORKSPACE_SYMBOL,
        LV_FS_OPEN_SYMBOL,
        LV_FS_CLOSE_SYMBOL,
        LV_FS_READ_SYMBOL,
        LV_FS_WRITE_SYMBOL,
        LV_FS_SEEK_SYMBOL,
        LV_FS_TELL_SYMBOL,
    ]
    selected = driver.require_symbols(symbols, required)
    if selected[driver.OVERLAY_WORKSPACE_SYMBOL] != layout["OTA_OVERLAY_ORIGIN"]:
        raise UploadError(
            f"unexpected overlay address: 0x{selected[driver.OVERLAY_WORKSPACE_SYMBOL]:08X}"
        )

    log_dir.mkdir(parents=True, exist_ok=True)
    tmp_dir.mkdir(parents=True, exist_ok=True)
    run_dir = tmp_dir / prefix
    gdb_script = run_dir / "upload.gdb"
    path_blob = run_dir / "mcu-path.bin"
    readback = run_dir / "readback.bin"
    rtt_log = log_dir / f"{prefix}-rtt.raw.log"
    gdb_log = log_dir / f"{prefix}-gdb.log"
    server_log = log_dir / f"{prefix}-jlink-server.log"
    result_path = log_dir / f"{prefix}-result.json"
    for output in (
        run_dir,
        readback,
        rtt_log,
        gdb_log,
        server_log,
        result_path,
    ):
        driver.require_inside_root(output, "output")
        if output.exists():
            raise UploadError(f"refusing to overwrite existing output: {output}")

    chunks = split_chunks(source, run_dir)
    path_blob.write_bytes(path_bytes)
    upload_gdb_command_file(
        gdb_script,
        elf,
        selected,
        expected_header,
        layout,
        chunks,
        path_blob,
        source.stat().st_size,
    )
    chunk_sizes = [chunk.stat().st_size for chunk in chunks]
    base_result: dict[str, object] = {
        "schema": "p2-6-rtt-sd-uploader-v2",
        "prepare_only": bool(args.prepare_only),
        "hardware_started": False,
        "input": str(source),
        "asset_kind": asset_kind,
        "input_bytes": source.stat().st_size,
        "input_sha256": source_hash,
        "mcu_path": args.mcu_path,
        "build": str(build),
        "elf": str(elf),
        "elf_sha256": driver.sha256_file(elf),
        "map": str(map_path),
        "map_sha256": driver.sha256_file(map_path),
        "device_image": str(device_image),
        "device_image_sha256": driver.sha256_file(device_image),
        "device_header_sha256": hashlib.sha256(expected_header).hexdigest().upper(),
        "chunk_count": len(chunks),
        "chunk_sizes": chunk_sizes,
        "symbols": {name: f"0x{value:08X}" for name, value in selected.items()},
        "logs": {
            "rtt": str(rtt_log),
            "gdb": str(gdb_log),
            "server": str(server_log),
            "gdb_script": str(gdb_script),
        },
        "sha256": {"gdb_script": driver.sha256_file(gdb_script)},
        "outside_repo_writes": [],
    }
    if args.prepare_only:
        result_path.write_text(
            json.dumps(base_result, indent=2, ensure_ascii=True) + "\n",
            encoding="ascii",
        )
        print(json.dumps(base_result, indent=2, ensure_ascii=True))
        return 0

    session = driver.run_gdb_session(
        jlink_dir=Path(args.jlink_dir),
        gdb=gdb,
        gdb_script=gdb_script,
        gdb_log=gdb_log,
        server_log=server_log,
        rtt_log=rtt_log,
        tmp_dir=tmp_dir,
        timeout=args.timeout,
        server_ready_timeout=args.server_ready_timeout,
    )
    readback_data: bytes | None = None
    readback_blocks: list[dict[str, object]] = []
    readback_parse_error: str | None = None
    if gdb_log.exists():
        try:
            readback_data, readback_blocks = parse_mi_readback(
                gdb_log.read_bytes(), chunk_sizes, selected[driver.OVERLAY_WORKSPACE_SYMBOL]
            )
        except UploadError as exc:
            readback_parse_error = str(exc)
    else:
        readback_parse_error = "GDB log was not created"
    if readback_data is not None:
        readback.write_bytes(readback_data)
    readback_hash = driver.sha256_file(readback) if readback.is_file() else None
    result = {
        **base_result,
        "hardware_started": bool(session["server_started"]),
        "session": session,
        "readback": str(readback) if readback.is_file() else None,
        "readback_bytes": readback.stat().st_size if readback.is_file() else None,
        "readback_sha256": readback_hash,
        "readback_matches": readback_hash == source_hash,
        "readback_parse_error": readback_parse_error,
        "readback_blocks": readback_blocks,
    }
    result["outside_repo_writes"] = (
        [driver.AUTHORIZED_SEGGER_WRITE] if session["server_started"] else []
    )
    result["sha256"] = {
        "rtt": driver.sha256_file(rtt_log) if rtt_log.exists() else None,
        "gdb": driver.sha256_file(gdb_log) if gdb_log.exists() else None,
        "server": driver.sha256_file(server_log) if server_log.exists() else None,
        "gdb_script": driver.sha256_file(gdb_script),
        "readback": readback_hash,
    }
    result_path.write_text(
        json.dumps(result, indent=2, ensure_ascii=True) + "\n", encoding="ascii"
    )

    if session["session_error"]:
        raise UploadError(f"GDB/RTT session failed: {session['session_error']}")
    if session["gdb_exit_code"] != 0:
        raise UploadError(
            f"GDB upload failed with exit code {session['gdb_exit_code']}; see {gdb_log}"
        )
    if readback_parse_error:
        raise UploadError(f"SD readback parse failed: {readback_parse_error}")
    if readback_data is None or len(readback_data) != source.stat().st_size:
        raise UploadError("SD readback byte count does not match input")
    if not result["readback_matches"]:
        raise UploadError("SD readback SHA-256 does not match input")
    if gdb_log.read_text(encoding="utf-8", errors="replace").count(
        "P2_6_SD_UPLOAD PASS"
    ) != 1:
        raise UploadError("GDB log does not contain exactly one upload PASS marker")
    print(json.dumps(result, indent=2, ensure_ascii=True))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--input", required=True)
    parser.add_argument("--mcu-path", required=True)
    parser.add_argument("--output-prefix", required=True)
    parser.add_argument("--build", default=str(driver.DEFAULT_BUILD))
    parser.add_argument("--device-image", default=str(driver.DEFAULT_DEVICE_IMAGE))
    parser.add_argument("--log-dir", default=str(driver.DEFAULT_LOG_DIR))
    parser.add_argument("--tmp-dir", default=str(driver.DEFAULT_TMP_DIR))
    parser.add_argument("--jlink-dir", default=str(driver.DEFAULT_JLINK_DIR))
    parser.add_argument("--gdb")
    parser.add_argument("--nm")
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--server-ready-timeout", type=float, default=45.0)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        return upload(args)
    except (UploadError, UnicodeEncodeError) as exc:
        print(f"P2_6_RTT_SD_UPLOAD=FAIL {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
