"""Offline capacity budgets and confirmation coverage, never a hardware PASS."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import re
import sys


def require(value, message):
    if not value:
        raise ValueError(message)


def record(path):
    data = path.read_bytes()
    return dict(path=str(path), bytes=len(data), sha256=hashlib.sha256(data).hexdigest())


def budgets(total, transfer_seconds, erase_seconds, program_seconds, *, baud=921600):
    for value in (total, transfer_seconds, erase_seconds, program_seconds, baud):
        require(type(value) in (int, float) and math.isfinite(value) and value > 0, "positive finite budget inputs required")
    require(type(total) is int and total % 4096 == 0, "whole 4 KiB workload required")
    block_uart = 32 * 142 * 10 / baud
    block_flash = (erase_seconds + program_seconds) / (total / 4096)
    return dict(
        scope="conditional model, not measured link ceiling; erase/program must remain serial for the serial bound",
        measured_payload_Bps=total / transfer_seconds,
        uart_payload_ceiling_Bps=baud / 10 * 128 / 142,
        uart_wire_seconds_per_block=block_uart,
        measured_erase_program_seconds_per_block=block_flash,
        serial_model_payload_ceiling_Bps=4096 / (block_uart + block_flash),
        targets=[dict(payload_Bps=rate, transfer_seconds=total / rate,
                      speedup_required=rate * transfer_seconds / total,
                      block_budget_seconds=4096 / rate,
                      serial_model_exceeds_budget=block_uart + block_flash > 4096 / rate)
                 for rate in (50000, 51200)])


def confirmation_coverage(samples, receiver, target, window_ms):
    require(type(window_ms) is int and window_ms > 0, "positive confirmation window required")
    require(samples and receiver != target, "distinct receiver/target and original samples required")
    last = -1
    for item in samples:
        require(type(item.get("start_ns")) is int and type(item.get("end_ns")) is int and
                last <= item["start_ns"] <= item["end_ns"], "invalid monotonic sample brackets")
        last = item["end_ns"]
    initialized = [x for x in samples if x.get("phase") == "app" and x.get("final_phase") == "app" and
                   x.get("version") == target and x.get("initialized") is True]
    require(initialized, "no initialized target samples")
    require(all(type(x.get("tick")) is int and 0 <= x["tick"] <= 0xffffffff for x in initialized),
            "missing target tick")
    require(all(b["tick"] >= a["tick"] for a, b in zip(initialized, initialized[1:])),
            "target ticks reset/wrapped; cannot infer one startup")
    confirmed = [x for x in initialized if x.get("confirmed") is True]
    last_tick = initialized[-1]["tick"]
    return dict(result="CONFIRMATION_OBSERVED" if confirmed else "EVIDENCE_GAP",
                confirmation_window_ticks_ms=window_ms,
                last_initialized_target_tick_ms=last_tick,
                ended_before_window_from_zero=not confirmed and last_tick < window_ms,
                observed_initialized_target_span_seconds=(initialized[-1]["end_ns"] - initialized[0]["start_ns"]) / 1e9,
                confirmed_bracket_ns=([confirmed[0]["start_ns"], confirmed[0]["end_ns"]] if confirmed else None),
                detail="tick coverage is not wall-time calibration; final readback does not repair a missing trace sample")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--report-sha256", required=True)
    parser.add_argument("--health-header", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    require(args.root.is_absolute() and Path.cwd() == args.root and sys.flags.isolated and
            sys.flags.no_site and sys.dont_write_bytecode, "explicit root and Python -I -S -B required")
    spec = importlib.util.spec_from_file_location("capacity_io", args.root / ".agents/skills/e-track-flutter-debug/scripts/host_io.py")
    io = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(io)
    checked = lambda path: io.checked_output(args.root, path)
    out = checked(args.out)
    require(not out.exists(), "output exists; preserve original analysis")
    report_path = checked(args.report)
    require(record(report_path)["sha256"] == args.report_sha256, "original report hash changed")
    report = json.loads(report_path.read_bytes())
    require(report["result"] == "FULL_INSTALL_VERIFIED", "completed original required")

    def original(item):
        path = checked(item["path"])
        require(record(path) == item, "original evidence changed: " + str(path))
        return path.read_bytes()

    plan = json.loads(original(report["inputs"]["plan"]))
    original(report["inputs"]["snapshot"])
    native = json.loads(original(report["native_trace"]["original"]))
    require(native["result"] == "TRACE_CLOSED" and native["reader_closed"] is True, "native owner not closed")
    samples = [json.loads(line) for line in original(native["samples"]).splitlines()]
    header = checked(args.health_header)
    window = re.findall(r"^#define OTA_CONFIRM_HEALTH_WINDOW_MS (\d+)u$", header.read_text(), re.M)
    require(len(window) == 1, "ambiguous health window header")
    metrics, profile = report["full_metrics"], report["native_trace"]["profile"]
    require(profile["clean_counters"] and profile["clock_ok"] == 1 and
            profile["total_len"] == report["experiment"]["packageBytes"], "invalid native cost sample")
    result = dict(result="OFFLINE_BOUND_ANALYSIS", source=record(Path(__file__)), original_report=record(report_path),
                  health_header=record(header), health_header_scope="provided source input; installed-source binding checked separately",
                  device_operations=0, measured_speedup=False,
                  budgets=budgets(profile["total_len"], metrics["transfer_seconds"],
                                  profile["phases"]["payload_erase"]["seconds"],
                                  profile["phases"]["payload_program"]["seconds"], baud=profile["retained_baud"]),
                  original_installation_reconnect_seconds=metrics["installation_reconnect_seconds"],
                  original_boot_residency=report["native_trace"]["boot_residency"],
                  internal_boot_subphases="NOT_MEASURED",
                  layouts_equal=plan["bindings"]["layout"] == plan["target_bindings"]["layout"],
                  confirmation_coverage=confirmation_coverage(samples, native["receiver"], native["target"], int(window[0])))
    io.write_json(args.root, out, result)
    print(json.dumps(result, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
