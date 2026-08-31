#!/usr/bin/env python3
"""Run the one-shot P2-6 SD-R2 hardware preflight without SD file calls."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys


THIS_DIR = Path(__file__).resolve().parent
if str(THIS_DIR) not in sys.path:
    sys.path.insert(0, str(THIS_DIR))

import p2_6_rtt_ota_driver as driver


class PreflightError(driver.DriverError):
    pass


def preflight_gdb_command_file(
    path: Path,
    elf: Path,
    symbols: dict[str, int],
    expected_header: bytes,
    layout: dict[str, int],
) -> None:
    update_entry = symbols[driver.HAL_UPDATE_SYMBOL]
    lines = [
        *driver.gdb_prologue_lines(elf),
        *driver.deterministic_stop_lines(
            update_entry, "preflight_hal_update", 0x50326201, 70, attach=True
        ),
        *driver.runtime_state_lines(
            symbols,
            expected_header,
            layout,
            "preflight",
            driver.BCB_STATE_CONFIRMED,
            71,
        ),
        'printf "P2_6_SD_PREFLIGHT PASS write_calls=0 flash_calls=0\\n"',
        "detach",
        "quit",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="ascii")


def run_preflight(args: argparse.Namespace) -> int:
    build = driver.require_inside_root(Path(args.build), "build directory")
    log_dir = driver.require_inside_root(Path(args.log_dir), "log directory")
    tmp_dir = driver.require_inside_root(Path(args.tmp_dir), "temporary directory")
    device_image = driver.require_inside_root(Path(args.device_image), "device image")
    prefix = args.output_prefix
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", prefix):
        raise PreflightError(f"invalid output prefix: {prefix!r}")
    log_dir.mkdir(parents=True, exist_ok=True)
    tmp_dir.mkdir(parents=True, exist_ok=True)

    elf, map_path = driver.require_frozen_build(build)
    expected_header, layout = driver.load_frozen_device_header(device_image)
    gdb = Path(args.gdb or shutil.which("arm-none-eabi-gdb") or "")
    nm = Path(args.nm or shutil.which("arm-none-eabi-nm") or "")
    if not gdb.is_file() or not nm.is_file():
        raise PreflightError("arm-none-eabi-gdb/nm is unavailable")
    symbols = driver.read_symbol_table(nm, elf)
    required = [
        driver.GET_BCB_SYMBOL,
        driver.HAL_UPDATE_SYMBOL,
        driver.SD_READY_SYMBOL,
        driver.RTT_SYMBOL,
        driver.OVERLAY_OWNER_SYMBOL,
        driver.OVERLAY_WORKSPACE_SYMBOL,
    ]
    selected = driver.require_symbols(symbols, required)
    if selected[driver.OVERLAY_WORKSPACE_SYMBOL] != layout["OTA_OVERLAY_ORIGIN"]:
        raise PreflightError(
            f"unexpected overlay address: 0x{selected[driver.OVERLAY_WORKSPACE_SYMBOL]:08X}"
        )

    gdb_script = tmp_dir / f"{prefix}.gdb"
    rtt_log = log_dir / f"{prefix}-rtt.raw.log"
    gdb_log = log_dir / f"{prefix}-gdb.log"
    server_log = log_dir / f"{prefix}-jlink-server.log"
    result_path = log_dir / f"{prefix}-result.json"
    for output in (gdb_script, rtt_log, gdb_log, server_log, result_path):
        driver.require_inside_root(output, "output")
        if output.exists():
            raise PreflightError(f"refusing to overwrite existing output: {output}")

    preflight_gdb_command_file(
        gdb_script, elf, selected, expected_header, layout
    )
    script_text = gdb_script.read_text(encoding="ascii")
    forbidden = (
        "lv_fs_open",
        "lv_fs_write",
        "lv_fs_close",
        "restore ",
        "continue &",
        "App_Init()::manager",
        "PageCurrent",
        "Dialplate",
    )
    hits = [token for token in forbidden if token in script_text]
    if hits:
        raise PreflightError("preflight script contains forbidden operations: " + ", ".join(hits))

    base_result: dict[str, object] = {
        "schema": "p2-6-rtt-sd-preflight-v1",
        "prepare_only": bool(args.prepare_only),
        "hardware_started": False,
        "build": str(build),
        "elf": str(elf),
        "elf_sha256": driver.sha256_file(elf),
        "map": str(map_path),
        "map_sha256": driver.sha256_file(map_path),
        "device_image": str(device_image),
        "device_image_sha256": driver.sha256_file(device_image),
        "device_header_sha256": hashlib.sha256(expected_header).hexdigest().upper(),
        "symbols": {name: f"0x{value:08X}" for name, value in selected.items()},
        "write_calls": 0,
        "flash_calls": 0,
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
    gdb_text = gdb_log.read_text(encoding="utf-8", errors="replace") if gdb_log.exists() else ""
    pass_count = gdb_text.count("P2_6_SD_PREFLIGHT PASS")
    state_pass_count = gdb_text.count("P2_6_STATE PASS label=preflight")
    result = {
        **base_result,
        "hardware_started": bool(session["server_started"]),
        "session": session,
        "preflight_pass_markers": pass_count,
        "state_pass_markers": state_pass_count,
    }
    result["outside_repo_writes"] = (
        [driver.AUTHORIZED_SEGGER_WRITE] if session["server_started"] else []
    )
    result["sha256"] = {
        "rtt": driver.sha256_file(rtt_log) if rtt_log.exists() else None,
        "gdb": driver.sha256_file(gdb_log) if gdb_log.exists() else None,
        "server": driver.sha256_file(server_log) if server_log.exists() else None,
        "gdb_script": driver.sha256_file(gdb_script),
    }
    result_path.write_text(
        json.dumps(result, indent=2, ensure_ascii=True) + "\n", encoding="ascii"
    )

    if session["session_error"]:
        raise PreflightError(f"GDB/RTT session failed: {session['session_error']}")
    if session["gdb_exit_code"] != 0:
        raise PreflightError(
            f"GDB preflight failed with exit code {session['gdb_exit_code']}; see {gdb_log}"
        )
    if pass_count != 1 or state_pass_count != 1:
        raise PreflightError(
            f"preflight markers are incomplete: pass={pass_count} state={state_pass_count}"
        )
    print(json.dumps(result, indent=2, ensure_ascii=True))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--output-prefix", required=True)
    parser.add_argument("--build", default=str(driver.DEFAULT_BUILD))
    parser.add_argument("--device-image", default=str(driver.DEFAULT_DEVICE_IMAGE))
    parser.add_argument("--log-dir", default=str(driver.DEFAULT_LOG_DIR))
    parser.add_argument("--tmp-dir", default=str(driver.DEFAULT_TMP_DIR))
    parser.add_argument("--jlink-dir", default=str(driver.DEFAULT_JLINK_DIR))
    parser.add_argument("--gdb")
    parser.add_argument("--nm")
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--server-ready-timeout", type=float, default=45.0)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        return run_preflight(args)
    except PreflightError as exc:
        print(f"P2_6_RTT_SD_PREFLIGHT=FAIL {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
