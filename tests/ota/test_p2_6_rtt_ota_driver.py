#!/usr/bin/env python3
"""Offline regression checks for the persistent P2-6 RTT OTA driver."""

from __future__ import annotations

import importlib.util
import io
from pathlib import Path
import re
import shutil
import socket
import struct
import subprocess
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest import mock


MODULE_PATH = Path(__file__).with_name("p2_6_rtt_ota_driver.py")
SPEC = importlib.util.spec_from_file_location("p2_6_rtt_ota_driver", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
DRIVER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(DRIVER)


def selected_symbols() -> dict[str, int]:
    return {
        DRIVER.MANAGER_SYMBOL: 0x200504F8,
        DRIVER.PAGE_VTABLE_SYMBOL: 0x0809CB3C,
        DRIVER.PUSH_SYMBOL: 0x0803DB94,
        DRIVER.ENTER_PATH_SYMBOL: 0x08045618,
        DRIVER.SELECT_ROW_SYMBOL: 0x08045710,
        DRIVER.START_IMPORT_SYMBOL: 0x080457A8,
        DRIVER.FINISH_IMPORT_SYMBOL: 0x08045074,
        DRIVER.GET_BCB_SYMBOL: 0x08040CCC,
        DRIVER.HAL_UPDATE_SYMBOL: 0x08040884,
        DRIVER.STRCMP_SYMBOL: 0x08052DB6,
        DRIVER.SD_READY_SYMBOL: 0x20053214,
        DRIVER.RTT_SYMBOL: 0x20053E1C,
        DRIVER.OVERLAY_OWNER_SYMBOL: 0x20053FA0,
        DRIVER.OVERLAY_WORKSPACE_SYMBOL: 0x20058000,
    }


def layout_values() -> dict[str, int]:
    return {
        "OTA_APP_ORIGIN": 0x08010000,
        "OTA_FW_HEADER_OFFSET": 0x400,
        "OTA_FW_HEADER_SIZE": 96,
        "OTA_OVERLAY_ORIGIN": 0x20058000,
        "OTA_OVERLAY_WORKSPACE_LENGTH": 0xA000,
    }


class P26RttOtaDriverTest(unittest.TestCase):
    def _measurement(self, kind: str = "PATCH") -> bytes:
        return (
            f"P2_6 kind={kind} result=0 workspace_peak=21832 "
            "arena_peak_observed=21832 failed_request_size=0 "
            "stack_entry=640 stack_peak=1536 stack_total=8192 "
            "guard_entry=1 guard_exit=1 sbrk_delta=0 sbrk_peak=536891392 "
            "tlsf_malloc_delta=0 tlsf_realloc_delta=0 tlsf_free_delta=0 "
            "lv_free_entry=90000 lv_free_exit=90000 "
            "lv_big_entry=80000 lv_big_exit=80000 "
            "lv_frag_entry=2 lv_frag_exit=2 lv_max_entry=131072 lv_max_exit=131072 "
            "seq=0 last_size=0 last_ret=0x0\r\n"
        ).encode()

    def test_parse_normalizes_lowercase_kinds(self) -> None:
        self.assertEqual(DRIVER.parse_measurements(self._measurement("patch"))[0]["kind"], "PATCH")
        self.assertEqual(DRIVER.parse_measurements(self._measurement("full"))[0]["kind"], "FULL")

    def test_parser_requires_complete_frames_and_rejects_unknown_kind(self) -> None:
        with self.assertRaises(DRIVER.DriverError):
            DRIVER.parse_measurements(self._measurement("PATCH")[:-2])
        with self.assertRaises(DRIVER.DriverError):
            DRIVER.parse_measurements(self._measurement("OTHER"))
        with self.assertRaises(DRIVER.DriverError):
            DRIVER.parse_measurements(self._measurement("PATCH") + self._measurement("PATCH" )[:-2])

    def test_parser_ignores_banner_noise_but_not_invalid_measurement(self) -> None:
        raw = b"SEGGER RTT\r\nnoise\r\n" + self._measurement("patch")
        self.assertEqual(len(DRIVER.parse_measurements(raw)), 1)

    def test_parser_rejects_unterminated_record(self) -> None:
        with self.assertRaises(DRIVER.DriverError):
            DRIVER.parse_measurements(self._measurement("PATCH").rstrip(b"\r\n"))

    def test_channel_binding_stays_unverified(self) -> None:
        outcome = {
            "server_started": True,
            "server_ready": True,
            "rtt_connected": True,
            "gdb_started": True,
            "gdb_exit_code": 0,
            "server_process_exited": True,
            "server_natural_exit": True,
            "server_terminate_sent": False,
            "server_kill_sent": False,
            "capture_stopped": True,
            "ports_closed": True,
            "session_error": None,
            "rtt_measurement_required": True,
            "rtt_pending_derived": True,
            "rtt_payload_ready": True,
            "rtt_drain_success": True,
            "rtt_drain_complete": True,
            "rtt_drain_deadline_expired": False,
            "rtt_payload_complete": True,
            "rtt_record_count": 1,
            "rtt_matching_record_count": 1,
            "rtt_postcheck_passed": True,
        }
        self.assertEqual(DRIVER.classify_transport_session(outcome), "PASS")
        self.assertFalse(outcome.get("rtt_channel_binding_verified", False))

    def _fake_transport_outcome(self, *, measurement_policy: bool, gdb_exit_code: int = 0) -> dict[str, object]:
        return {
            "server_started": True,
            "server_pid": 501,
            "server_ready": True,
            "server_ready_seconds": 0.1,
            "server_exit_code": 0,
            "server_process_exited": True,
            "server_natural_exit": True,
            "server_terminate_sent": False,
            "server_kill_sent": False,
            "server_exit_wait_seconds": 0.1,
            "server_cleanup_action": "natural_exit",
            "server_cleanup_error": None,
            "gdb_started": gdb_exit_code == 0,
            "gdb_exit_code": gdb_exit_code,
            "capture_error": None,
            "rtt_connected": True,
            "rtt_socket_connected": True,
            "rtt_socket_eof": False,
            "rtt_socket_error": False,
            "rtt_banner_bytes": 107,
            "rtt_capture_mode": "two_phase_logger",
            "rtt_measurement_required": bool(measurement_policy),
            "rtt_expected_kind": "PATCH" if measurement_policy else None,
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
            "ports_closed": True,
            "session_error": None,
            "transport_classification": None,
        }

    def _make_control_block(
        self,
        *,
        wr_off: int,
        rd_off: int,
        signature: bytes = DRIVER.RTT_SIGNATURE,
        up_size: int = 1024,
        p_buffer: int = 0x20053A1C,
        flags: int = 1,
        max_up: int = 3,
        max_down: int = 3,
    ) -> bytes:
        cb = bytearray(DRIVER.RTT_CB_SIZE)
        cb[0:len(signature)] = signature
        struct.pack_into("<i", cb, DRIVER.RTT_CB_MAX_UP_OFFSET, max_up)
        struct.pack_into("<i", cb, DRIVER.RTT_CB_MAX_DOWN_OFFSET, max_down)
        struct.pack_into("<I", cb, DRIVER.RTT_CB_UP0_PBUFFER_OFFSET, p_buffer)
        struct.pack_into("<I", cb, DRIVER.RTT_CB_UP0_SIZE_OFFSET, up_size)
        struct.pack_into("<I", cb, DRIVER.RTT_CB_UP0_WROFF_OFFSET, wr_off)
        struct.pack_into("<I", cb, DRIVER.RTT_CB_UP0_RDOFF_OFFSET, rd_off)
        struct.pack_into("<I", cb, DRIVER.RTT_CB_UP0_FLAGS_OFFSET, flags)
        return bytes(cb)

    def _make_ring(self, pending: bytes) -> bytes:
        ring = bytearray(b"\xEE" * 1024)
        ring[0:len(pending)] = pending
        return bytes(ring)

    def _run_fake_two_phase(
        self,
        pending: bytes = b"",
        *,
        expected_kind: str = "PATCH",
        gdb_exit_code: int = 0,
        capture_status: str = "PASS",
        capture_error: str | None = None,
        capture_payload: bytes | None = None,
        capture_timeout: bool = False,
        post_wr_off: int | None = None,
        post_rd_off: int | None = None,
        post_extra_byte: bool = False,
        post_session_fail: bool = False,
    ) -> dict[str, object]:
        """Drive run_two_phase_ota_session with the process/socket layer mocked.

        The phase-1 snapshots, the pending derivation, and the postcheck all
        run for real on constructed control-block/ring bytes; only the GDB
        sessions, the logger process, and the port checks are faked.
        """
        wr_off = len(pending)
        pre_cb = self._make_control_block(wr_off=wr_off, rd_off=0)
        post_cb = bytearray(
            self._make_control_block(
                wr_off=wr_off if post_wr_off is None else post_wr_off,
                rd_off=wr_off if post_rd_off is None else post_rd_off,
            )
        )
        if post_extra_byte:
            post_cb[0x30] = (post_cb[0x30] + 1) & 0xFF
        post_cb = bytes(post_cb)

        with tempfile.TemporaryDirectory(dir=DRIVER.DEFAULT_TMP_DIR) as temp:
            temp_dir = Path(temp)
            cb_pre = temp_dir / "cb-pre.bin"
            ring_pre = temp_dir / "ring-pre.bin"
            cb_post = temp_dir / "cb-post.bin"
            pending_path = temp_dir / "pending.bin"
            raw_log = temp_dir / "payload.raw.log"
            console_log = temp_dir / "console.log"
            post_rtt_log = temp_dir / "post-rtt.log"
            cb_pre.write_bytes(pre_cb)
            ring_pre.write_bytes(self._make_ring(pending))

            def fake_gdb_session(**kwargs: object) -> dict[str, object]:
                measurement = bool(kwargs.get("measurement_policy"))
                outcome = self._fake_transport_outcome(
                    measurement_policy=measurement,
                    gdb_exit_code=gdb_exit_code if measurement else 0,
                )
                # GDB did start in every fake case; a nonzero exit code is a
                # GDB_FAIL, not a GDB_NOT_STARTED.
                outcome["gdb_started"] = True
                if not measurement:
                    cb_post.write_bytes(post_cb)
                    if post_session_fail:
                        outcome["session_error"] = "post session failed"
                        outcome["gdb_exit_code"] = 3
                return outcome

            def fake_capture(*args: object, **kwargs: object) -> dict[str, object]:
                result: dict[str, object] = {
                    "phase": "capture",
                    "status": capture_status,
                    "reader": "JLinkRTTLogger",
                    "payload_ready": capture_status == "PASS",
                    "payload_complete": capture_status == "PASS",
                    "payload_timeout": capture_timeout,
                    "logger_stopped": True,
                    "residual_rtt_logger_processes": 0,
                    "logger_stopped_by": "test",
                }
                if capture_status == "PASS":
                    payload = pending if capture_payload is None else capture_payload
                    raw_log.write_bytes(payload)
                    result["payload_bytes"] = len(payload)
                else:
                    result["error"] = capture_error or "capture failed"
                return result

            with (
                mock.patch.object(
                    DRIVER, "run_gdb_session", side_effect=fake_gdb_session
                ),
                mock.patch.object(
                    DRIVER, "run_rtt_logger_capture", side_effect=fake_capture
                ),
            ):
                outcome = DRIVER.run_two_phase_ota_session(
                    jlink_dir=Path("C:/JLink"),
                    gdb=Path("C:/gdb.exe"),
                    gdb_script=temp_dir / "session.gdb",
                    gdb_log=temp_dir / "session-gdb.log",
                    server_log=temp_dir / "session-server.log",
                    rtt_log=temp_dir / "session-rtt.log",
                    tmp_dir=temp_dir,
                    timeout=1,
                    server_ready_timeout=0.01,
                    expected_kind=expected_kind,
                    rtt_address=0x20053E1C,
                    cb_snapshot=cb_pre,
                    ring_snapshot=ring_pre,
                    pending_path=pending_path,
                    raw_log=raw_log,
                    console_log=console_log,
                    post_gdb_script=temp_dir / "post.gdb",
                    post_gdb_log=temp_dir / "post-gdb.log",
                    post_server_log=temp_dir / "post-server.log",
                    post_rtt_log=post_rtt_log,
                    post_cb_snapshot=cb_post,
                )
        return outcome

    def test_two_phase_full_chain_passes_and_verifies_binding(self) -> None:
        outcome = self._run_fake_two_phase(self._measurement("PATCH") + b"\r\n")
        self.assertEqual(outcome["transport_classification"], "PASS")
        self.assertTrue(outcome["rtt_pending_derived"])
        self.assertTrue(outcome["rtt_payload_ready"])
        self.assertTrue(outcome["rtt_drain_complete"])
        self.assertTrue(outcome["rtt_payload_complete"])
        self.assertTrue(outcome["rtt_postcheck_passed"])
        self.assertTrue(outcome["rtt_channel_binding_verified"])
        self.assertEqual(outcome["rtt_record_count"], 1)
        self.assertEqual(outcome["rtt_matching_record_count"], 1)
        phases = outcome["rtt_two_phase"]
        self.assertEqual(phases["derive"]["status"], "ELIGIBLE")
        self.assertEqual(phases["capture"]["status"], "PASS")
        self.assertEqual(phases["postcheck"]["status"], "PASS")

    def test_two_phase_rejects_empty_and_banner_only_inventory(self) -> None:
        # A banner-only telnet file carries no records; the equivalent empty
        # Up0 inventory must fail closed at the derive stage.
        outcome = self._run_fake_two_phase(b"")
        self.assertFalse(outcome["rtt_pending_derived"])
        self.assertEqual(outcome["transport_classification"], "RTT_PAYLOAD_FAIL")
        self.assertIn("empty", str(outcome["session_error"]).lower())

    def test_two_phase_rejects_duplicate_and_wrong_kind(self) -> None:
        duplicate = self._run_fake_two_phase(
            self._measurement("PATCH") + b"\r\n" + self._measurement("PATCH") + b"\r\n"
        )
        wrong_kind = self._run_fake_two_phase(
            self._measurement("FULL") + b"\r\n", expected_kind="PATCH"
        )
        self.assertEqual(duplicate["transport_classification"], "RTT_PAYLOAD_FAIL")
        self.assertEqual(wrong_kind["transport_classification"], "RTT_PAYLOAD_FAIL")
        self.assertEqual(duplicate["rtt_record_count"], 2)
        self.assertEqual(wrong_kind["rtt_matching_record_count"], 0)

    def test_two_phase_rejects_truncated_record(self) -> None:
        truncated = self._run_fake_two_phase(
            self._measurement("PATCH").rstrip(b"\r\n")
        )
        self.assertFalse(truncated["rtt_pending_derived"])
        self.assertEqual(truncated["transport_classification"], "RTT_PAYLOAD_FAIL")

    def test_two_phase_rejects_capture_timeout_extra_bytes_and_mismatch(self) -> None:
        payload = self._measurement("PATCH") + b"\r\n"
        timeout_case = self._run_fake_two_phase(
            payload,
            capture_status="FAIL",
            capture_error="RTT payload timeout: logger delivered 0 of 60 bytes",
            capture_timeout=True,
        )
        self.assertEqual(
            timeout_case["transport_classification"], "RTT_PAYLOAD_FAIL"
        )
        self.assertTrue(timeout_case["rtt_payload_timeout"])
        extra_case = self._run_fake_two_phase(
            payload,
            capture_status="FAIL",
            capture_error="RTT payload contains extra bytes",
        )
        self.assertEqual(extra_case["transport_classification"], "RTT_PAYLOAD_FAIL")
        mismatch_case = self._run_fake_two_phase(
            payload,
            capture_status="FAIL",
            capture_error="RTT payload differs from pre-read Up0 inventory",
        )
        self.assertEqual(
            mismatch_case["transport_classification"], "RTT_PAYLOAD_FAIL"
        )

    def test_two_phase_rejects_wroff_change_rdoff_stall_and_extra_cb_bytes(self) -> None:
        payload = self._measurement("PATCH") + b"\r\n"
        wr_off_case = self._run_fake_two_phase(payload, post_wr_off=len(payload) + 1)
        self.assertEqual(wr_off_case["transport_classification"], "RTT_POSTCHECK_FAIL")
        stall_case = self._run_fake_two_phase(payload, post_rd_off=0)
        self.assertEqual(
            stall_case["transport_classification"], "RTT_POSTCHECK_FAIL"
        )
        extra_byte_case = self._run_fake_two_phase(payload, post_extra_byte=True)
        self.assertEqual(
            extra_byte_case["transport_classification"], "RTT_POSTCHECK_FAIL"
        )
        for case in (wr_off_case, stall_case, extra_byte_case):
            self.assertFalse(case["rtt_channel_binding_verified"])
            self.assertTrue(case["rtt_pending_derived"])

    def test_two_phase_post_session_failure_fails_closed(self) -> None:
        payload = self._measurement("PATCH") + b"\r\n"
        outcome = self._run_fake_two_phase(payload, post_session_fail=True)
        self.assertEqual(outcome["transport_classification"], "RTT_POSTCHECK_FAIL")
        self.assertFalse(outcome["rtt_postcheck_passed"])
        self.assertFalse(outcome["rtt_channel_binding_verified"])

    def test_gdb_nonzero_fails_even_with_valid_payload(self) -> None:
        outcome = self._run_fake_two_phase(
            self._measurement("PATCH") + b"\r\n",
            gdb_exit_code=7,
        )
        self.assertEqual(outcome["gdb_exit_code"], 7)
        self.assertFalse(outcome["rtt_pending_derived"])
        self.assertEqual(outcome["transport_classification"], "GDB_FAIL")

    def test_two_phase_never_reports_binding_without_full_chain(self) -> None:
        # Any single broken stage must keep rtt_channel_binding_verified false.
        cases = (
            self._run_fake_two_phase(b""),
            self._run_fake_two_phase(self._measurement("PATCH") + b"\r\n", capture_status="FAIL"),
            self._run_fake_two_phase(self._measurement("PATCH") + b"\r\n", post_rd_off=0),
        )
        for outcome in cases:
            self.assertFalse(outcome["rtt_channel_binding_verified"])
            self.assertNotEqual(outcome["transport_classification"], "PASS")

    def test_classify_rejects_drain_timeout_with_valid_record_count(self) -> None:
        # A complete record count alone must not pass when the capture timed
        # out: the payload was never fully delivered to the host.
        outcome = {
            "server_started": True,
            "server_ready": True,
            "rtt_connected": True,
            "gdb_started": True,
            "gdb_exit_code": 0,
            "server_process_exited": True,
            "server_natural_exit": True,
            "server_terminate_sent": False,
            "server_kill_sent": False,
            "capture_stopped": True,
            "ports_closed": True,
            "session_error": None,
            "capture_error": None,
            "rtt_measurement_required": True,
            "rtt_pending_derived": True,
            "rtt_payload_ready": True,
            "rtt_drain_success": False,
            "rtt_drain_complete": False,
            "rtt_drain_deadline_expired": True,
            "rtt_payload_complete": False,
            "rtt_payload_timeout": True,
            "rtt_record_count": 1,
            "rtt_matching_record_count": 1,
            "rtt_postcheck_passed": False,
        }
        self.assertEqual(
            DRIVER.classify_transport_session(outcome), "RTT_PAYLOAD_FAIL"
        )

    def test_non_measurement_session_never_parses_payload(self) -> None:
        # Shared (preflight/uploader/qualifier) sessions must not require or
        # parse any measurement payload; their classification is transport-only.
        outcome = self._fake_transport_outcome(measurement_policy=False)
        outcome["transport_classification"] = DRIVER.classify_transport_session(outcome)
        self.assertEqual(outcome["transport_classification"], "PASS")
        self.assertFalse(outcome["rtt_measurement_required"])
        self.assertEqual(outcome["rtt_record_count"], 0)
        self.assertFalse(outcome["rtt_channel_binding_verified"])

    def test_parse_and_classify_clean_record(self) -> None:
        raw = (
            b"P2_6 kind=PATCH result=0 workspace_peak=21832 "
            b"arena_peak_observed=21832 failed_request_size=0 "
            b"stack_entry=640 stack_peak=1536 stack_total=8192 "
            b"guard_entry=1 guard_exit=1 sbrk_delta=0 sbrk_peak=536891392 "
            b"tlsf_malloc_delta=0 tlsf_realloc_delta=0 tlsf_free_delta=0 "
            b"lv_free_entry=90000 lv_free_exit=90000 "
            b"lv_big_entry=80000 lv_big_exit=80000 "
            b"lv_frag_entry=2 lv_frag_exit=2 lv_max_entry=131072 lv_max_exit=131072 "
            b"seq=0 last_size=0 last_ret=0x0\r\n"
        )
        records = DRIVER.parse_measurements(raw)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["kind"], "PATCH")
        self.assertEqual(records[0]["workspace_peak"], 21832)
        checks = DRIVER.classify_measurement(records[0])
        for key in (
            "result_ok",
            "workspace_ok",
            "stack_ok",
            "guard_ok",
            "sbrk_ok",
            "tlsf_required_ok",
        ):
            self.assertTrue(checks[key], key)

    def test_classify_rejects_required_gate_failures(self) -> None:
        record = {
            "kind": "FULL",
            "result": -1,
            "workspace_peak": 40961,
            "stack_peak": 8193,
            "guard_entry": 1,
            "guard_exit": 0,
            "sbrk_delta": 1,
            "tlsf_malloc_delta": 1,
            "tlsf_realloc_delta": 1,
            "tlsf_free_delta": 0,
            "lv_free_entry": 1,
            "lv_free_exit": 2,
            "lv_big_entry": 1,
            "lv_big_exit": 2,
            "lv_frag_entry": 1,
            "lv_frag_exit": 2,
            "lv_max_entry": 1,
            "lv_max_exit": 2,
        }
        checks = DRIVER.classify_measurement(record)
        for key in (
            "result_ok",
            "workspace_ok",
            "stack_ok",
            "guard_ok",
            "sbrk_ok",
            "tlsf_required_ok",
            "lv_pool_net_unchanged",
        ):
            self.assertFalse(checks[key], key)

    def test_output_boundary_rejects_project_external_path(self) -> None:
        with self.assertRaises(DRIVER.DriverError):
            DRIVER.require_inside_root(Path(r"C:\Temp\p2-6.log"), "test")

    def test_required_symbols_fail_closed_on_missing_or_ambiguous(self) -> None:
        with self.assertRaisesRegex(DRIVER.DriverError, "lacks required"):
            DRIVER.require_symbols({}, [DRIVER.HAL_UPDATE_SYMBOL])
        with self.assertRaisesRegex(DRIVER.DriverError, "not unique"):
            DRIVER.require_symbols(
                {DRIVER.HAL_UPDATE_SYMBOL: [0x08040884, 0x08040888]},
                [DRIVER.HAL_UPDATE_SYMBOL],
            )
        self.assertEqual(
            DRIVER.require_symbols(
                {DRIVER.HAL_UPDATE_SYMBOL: [0x08040884]},
                [DRIVER.HAL_UPDATE_SYMBOL],
            ),
            {DRIVER.HAL_UPDATE_SYMBOL: 0x08040884},
        )

    def test_generated_script_is_synchronous_and_checks_real_page_layout(self) -> None:
        DRIVER.DEFAULT_TMP_DIR.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=DRIVER.DEFAULT_TMP_DIR) as temp:
            output = Path(temp) / "driver.gdb"
            cb_snapshot = Path(temp) / "cb-pre.bin"
            ring_snapshot = Path(temp) / "up0-pre.bin"
            DRIVER.gdb_command_file(
                output,
                DRIVER.ROOT / "firmware.elf",
                selected_symbols(),
                bytes(range(96)),
                layout_values(),
                "/P2-6-RUN-20260820-01/P2-6A-PATCH-SD-R2.etu",
                "PATCH",
                cb_snapshot,
                ring_snapshot,
            )
            text = output.read_text(encoding="ascii")
        self.assertIn("Pages/FirmwareUpdate", text)
        self.assertIn("P2_6_TRANSPORT stop_verified label=initial_hal_update", text)
        self.assertIn("P2_6_TRANSPORT context_verified label=push_return", text)
        self.assertIn("set $page = *(void**)0x20050534", text)
        self.assertIn("(char*)$page + 36", text)
        self.assertIn("wrong_page_state", text)
        self.assertIn("expected=3_or_4", text)
        self.assertNotIn("continue &", text)
        self.assertNotIn("interrupt", text)
        self.assertNotIn("restore ", text)
        self.assertNotIn("Dialplate", text)
        self.assertNotIn("sleep", text.lower())
        self.assertLess(text.index("monitor halt"), text.index("continue\n"))
        self.assertLess(
            text.index("stop_verified label=initial_hal_update"),
            text.index("set $sd_before_ota"),
        )

    def test_generated_script_snapshots_rtt_while_halted_with_wdt_pause(self) -> None:
        DRIVER.DEFAULT_TMP_DIR.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=DRIVER.DEFAULT_TMP_DIR) as temp:
            output = Path(temp) / "driver.gdb"
            cb_snapshot = Path(temp) / "cb-pre.bin"
            ring_snapshot = Path(temp) / "up0-pre.bin"
            DRIVER.gdb_command_file(
                output,
                DRIVER.ROOT / "firmware.elf",
                selected_symbols(),
                bytes(range(96)),
                layout_values(),
                "/P2-6-RUN-20260820-01/P2-6A-PATCH-SD-R2.etu",
                "PATCH",
                cb_snapshot,
                ring_snapshot,
            )
            text = output.read_text(encoding="ascii")
        # Exactly one watchdog-pause line, immediately after monitor halt.
        self.assertEqual(text.count(DRIVER.WDT_PAUSE_COMMAND), 1)
        self.assertLess(text.index("monitor halt"), text.index(DRIVER.WDT_PAUSE_COMMAND))
        # Snapshot dump lines run while halted, before detach, at the frozen
        # RTT control-block address.
        rtt_addr = selected_symbols()[DRIVER.RTT_SYMBOL]
        self.assertIn(f"set $rtt_cb = (unsigned char*)0x{rtt_addr:08x}", text)
        self.assertIn(
            f"dump binary memory {cb_snapshot.as_posix()} $rtt_cb ($rtt_cb + 0xA8)",
            text,
        )
        self.assertIn(
            f"dump binary memory {ring_snapshot.as_posix()} $up0_pbuf ($up0_pbuf + $up0_size)",
            text,
        )
        self.assertIn("SNAPSHOT_WRITTEN", text)
        self.assertLess(text.index("SNAPSHOT_WRITTEN"), text.index("detach"))
        self.assertLess(text.index("P2_6_RTT_DRIVER PASS"), text.index("SNAPSHOT_WRITTEN"))

    def test_post_snapshot_script_is_halt_wdt_dump_only(self) -> None:
        DRIVER.DEFAULT_TMP_DIR.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=DRIVER.DEFAULT_TMP_DIR) as temp:
            output = Path(temp) / "post.gdb"
            cb_snapshot = Path(temp) / "cb-post.bin"
            rtt_addr = selected_symbols()[DRIVER.RTT_SYMBOL]
            DRIVER.post_snapshot_command_file(
                output, DRIVER.ROOT / "firmware.elf", rtt_addr, cb_snapshot
            )
            text = output.read_text(encoding="ascii")
        self.assertEqual(text.count("monitor halt"), 1)
        self.assertEqual(text.count(DRIVER.WDT_PAUSE_COMMAND), 1)
        self.assertLess(text.index("monitor halt"), text.index(DRIVER.WDT_PAUSE_COMMAND))
        self.assertIn(
            f"dump binary memory {cb_snapshot.as_posix()} $rtt_cb ($rtt_cb + 0xA8)",
            text,
        )
        # Read-only session: no continue, no calls, no reset/go, no flash.
        self.assertNotIn("continue", text)
        self.assertNotIn("call ", text)
        self.assertNotIn("reset", text)
        self.assertNotIn("loadbin", text)
        self.assertNotIn("loadfile", text)
        self.assertIn("detach", text)

    def test_page_offsets_match_frozen_elf_disassembly(self) -> None:
        objdump = shutil.which("arm-none-eabi-objdump")
        nm = shutil.which("arm-none-eabi-nm")
        self.assertIsNotNone(objdump)
        self.assertIsNotNone(nm)
        elf = DRIVER.DEFAULT_BUILD / DRIVER.DEFAULT_ELF_REL
        symbols = DRIVER.read_symbol_table(Path(nm), elf)
        switch_name = "PageManager::SwitchTo(PageBase*, bool, PageBase::Stash_t const*)"
        switch = DRIVER.require_symbols(symbols, [switch_name])[switch_name]
        result = subprocess.run(
            [
                str(objdump),
                "-d",
                "-C",
                f"--start-address=0x{switch:08x}",
                f"--stop-address=0x{switch + 0xB0:08x}",
                str(elf),
            ],
            cwd=DRIVER.ROOT,
            text=True,
            capture_output=True,
            check=True,
        )
        self.assertRegex(result.stdout, r"str\s+r4, \[r5, #60\]")
        self.assertRegex(result.stdout, r"ldr\s+r6, \[r5, #56\]")
        self.assertRegex(result.stdout, r"strb\.w\s+r3, \[r4, #36\]")
        self.assertEqual(DRIVER.PAGE_CURRENT_OFFSET, 60)
        self.assertEqual(DRIVER.PAGE_STATE_OFFSET, 36)

    def test_layout_and_frozen_hashes_are_exact(self) -> None:
        elf, map_path = DRIVER.require_frozen_build(DRIVER.DEFAULT_BUILD)
        header, layout = DRIVER.load_frozen_device_header(DRIVER.DEFAULT_DEVICE_IMAGE)
        self.assertEqual(DRIVER.sha256_file(elf), DRIVER.FROZEN_TEST_ELF_SHA256)
        self.assertEqual(DRIVER.sha256_file(map_path), DRIVER.FROZEN_TEST_MAP_SHA256)
        self.assertEqual(len(header), 96)
        self.assertEqual(layout["OTA_FW_HEADER_SIZE"], 96)
        self.assertEqual(layout["OTA_OVERLAY_ORIGIN"], 0x20058000)

    def test_jlink_server_ports_are_unique(self) -> None:
        command = DRIVER.server_command(DRIVER.DEFAULT_JLINK_DIR)
        values = {}
        for option in ("-port", "-swoport", "-rtttelnetport", "-telnetport"):
            values[option] = int(command[command.index(option) + 1])
        self.assertEqual(values["-port"], DRIVER.GDB_PORT)
        self.assertEqual(values["-swoport"], DRIVER.SWO_PORT)
        self.assertEqual(values["-rtttelnetport"], DRIVER.RTT_PORT)
        self.assertEqual(values["-telnetport"], DRIVER.MONITOR_PORT)
        self.assertEqual(len(set(values.values())), len(values))

    def test_server_cleanup_prefers_natural_singlerun_exit(self) -> None:
        events: list[str] = []

        class NaturalServer:
            pid = 401

            def __init__(self) -> None:
                self.exited = False

            def poll(self) -> int | None:
                return 1 if self.exited else None

            def wait(self, timeout: float | None = None) -> int:
                events.append("wait")
                self.exited = True
                return 1

            def terminate(self) -> None:
                events.append("terminate")

            def kill(self) -> None:
                events.append("kill")

        result = DRIVER.finish_server_process(
            NaturalServer(), natural_exit_timeout=0.01
        )
        self.assertTrue(result["natural_exit"])
        self.assertFalse(result["terminate_sent"])
        self.assertFalse(result["kill_sent"])
        self.assertTrue(result["process_exited"])
        self.assertEqual(events, ["wait"])

    def test_server_cleanup_forces_only_after_grace_timeout(self) -> None:
        events: list[str] = []

        class StalledServer:
            pid = 402

            def __init__(self) -> None:
                self.exited = False
                self.wait_count = 0

            def poll(self) -> int | None:
                return 0 if self.exited else None

            def wait(self, timeout: float | None = None) -> int:
                self.wait_count += 1
                events.append(f"wait{self.wait_count}")
                if self.wait_count == 1:
                    raise subprocess.TimeoutExpired("JLinkGDBServerCL", timeout)
                self.exited = True
                return 0

            def terminate(self) -> None:
                events.append("terminate")

            def kill(self) -> None:
                events.append("kill")

        result = DRIVER.finish_server_process(
            StalledServer(), natural_exit_timeout=0.01, terminate_timeout=0.01
        )
        self.assertFalse(result["natural_exit"])
        self.assertTrue(result["terminate_sent"])
        self.assertFalse(result["kill_sent"])
        self.assertEqual(result["cleanup_action"], "terminate")
        self.assertEqual(events, ["wait1", "terminate", "wait2"])

    def test_session_waits_for_ready_before_rtt_or_gdb_and_closes_naturally(self) -> None:
        events: list[str] = []

        class FakeServer:
            pid = 403

            def __init__(self) -> None:
                self.exited = False

            def poll(self) -> int | None:
                return 0 if self.exited else None

            def wait(self, timeout: float | None = None) -> int:
                events.append("server_wait")
                self.exited = True
                return 0

            def terminate(self) -> None:
                events.append("terminate")

            def kill(self) -> None:
                events.append("kill")

        class FakeBannerSocket:
            def settimeout(self, timeout: float) -> None:
                return None

            def recv(self, size: int) -> bytes:
                return b"SEGGER J-Link V8.18 - Real time terminal output\r\n"

            def close(self) -> None:
                return None

        with tempfile.TemporaryDirectory(dir=DRIVER.DEFAULT_TMP_DIR) as temp:
            temp_dir = Path(temp)
            with (
                mock.patch.object(
                    DRIVER,
                    "start_server",
                    side_effect=lambda *args, **kwargs: (
                        events.append("start_server") or FakeServer(),
                        io.StringIO(),
                    ),
                ),
                mock.patch.object(
                    DRIVER,
                    "wait_for_server_ready",
                    side_effect=lambda *args, **kwargs: events.append("ready"),
                ),
                mock.patch.object(
                    DRIVER.socket,
                    "create_connection",
                    side_effect=lambda *args, **kwargs: (
                        events.append("rtt_probe") or FakeBannerSocket()
                    ),
                ),
                mock.patch.object(DRIVER, "port_is_listening", return_value=False),
                mock.patch.object(DRIVER, "wait_for_ports_closed", return_value=True),
                mock.patch.object(
                    DRIVER.subprocess,
                    "run",
                    side_effect=lambda *args, **kwargs: (
                        events.append("gdb") or SimpleNamespace(returncode=0)
                    ),
                ),
            ):
                outcome = DRIVER.run_gdb_session(
                    jlink_dir=Path("C:/JLink"),
                    gdb=Path("C:/gdb.exe"),
                    gdb_script=temp_dir / "session.gdb",
                    gdb_log=temp_dir / "session-gdb.log",
                    server_log=temp_dir / "session-server.log",
                    rtt_log=temp_dir / "session-rtt.log",
                    tmp_dir=temp_dir,
                    timeout=1,
                    server_ready_timeout=0.01,
                    server_exit_timeout=0.01,
                )
        self.assertEqual(events, ["start_server", "ready", "rtt_probe", "gdb", "server_wait"])
        self.assertTrue(outcome["server_ready"])
        self.assertTrue(outcome["server_natural_exit"])
        self.assertFalse(outcome["server_terminate_sent"])
        self.assertTrue(outcome["rtt_connected"])
        self.assertTrue(outcome["rtt_banner_bytes"] > 0)
        self.assertEqual(outcome["transport_classification"], "PASS")

    def test_session_rejects_non_segger_banner(self) -> None:
        class JunkSocket:
            def settimeout(self, timeout: float) -> None:
                return None

            def recv(self, size: int) -> bytes:
                return b"garbage"

            def close(self) -> None:
                return None

        with tempfile.TemporaryDirectory(dir=DRIVER.DEFAULT_TMP_DIR) as temp:
            temp_dir = Path(temp)
            with (
                mock.patch.object(
                    DRIVER,
                    "start_server",
                    return_value=(SimpleNamespace(pid=407, poll=lambda: None, wait=lambda t=None: 0), io.StringIO()),
                ),
                mock.patch.object(DRIVER, "wait_for_server_ready"),
                mock.patch.object(
                    DRIVER.socket, "create_connection", return_value=JunkSocket()
                ),
                mock.patch.object(DRIVER, "port_is_listening", return_value=False),
                mock.patch.object(DRIVER, "wait_for_ports_closed", return_value=True),
                mock.patch.object(DRIVER.subprocess, "run") as gdb_run,
            ):
                outcome = DRIVER.run_gdb_session(
                    jlink_dir=Path("C:/JLink"),
                    gdb=Path("C:/gdb.exe"),
                    gdb_script=temp_dir / "session.gdb",
                    gdb_log=temp_dir / "session-gdb.log",
                    server_log=temp_dir / "session-server.log",
                    rtt_log=temp_dir / "session-rtt.log",
                    tmp_dir=temp_dir,
                    timeout=1,
                    server_ready_timeout=0.01,
                    server_exit_timeout=0.01,
                )
        gdb_run.assert_not_called()
        self.assertFalse(outcome["gdb_started"])
        self.assertTrue(outcome["rtt_socket_error"])
        self.assertIsNotNone(outcome["session_error"])
        # The probe failure happened before the GDB launch, so the session
        # fails closed with GDB never started.
        self.assertEqual(outcome["transport_classification"], "GDB_NOT_STARTED")

    def test_readiness_failure_never_starts_rtt_or_gdb(self) -> None:
        events: list[str] = []

        class FakeServer:
            pid = 404

            def __init__(self) -> None:
                self.exited = False

            def poll(self) -> int | None:
                return 0 if self.exited else None

            def wait(self, timeout: float | None = None) -> int:
                self.exited = True
                return 1

            def terminate(self) -> None:
                events.append("terminate")

            def kill(self) -> None:
                events.append("kill")

        with tempfile.TemporaryDirectory(dir=DRIVER.DEFAULT_TMP_DIR) as temp:
            temp_dir = Path(temp)
            with (
                mock.patch.object(
                    DRIVER,
                    "start_server",
                    return_value=(FakeServer(), io.StringIO()),
                ),
                mock.patch.object(
                    DRIVER,
                    "wait_for_server_ready",
                    side_effect=DRIVER.DriverError("readiness timeout"),
                ),
                mock.patch.object(DRIVER.socket, "create_connection") as connect,
                mock.patch.object(DRIVER, "port_is_listening", return_value=False),
                mock.patch.object(DRIVER, "wait_for_ports_closed", return_value=True),
                mock.patch.object(DRIVER.subprocess, "run") as gdb_run,
            ):
                outcome = DRIVER.run_gdb_session(
                    jlink_dir=Path("C:/JLink"),
                    gdb=Path("C:/gdb.exe"),
                    gdb_script=temp_dir / "session.gdb",
                    gdb_log=temp_dir / "session-gdb.log",
                    server_log=temp_dir / "session-server.log",
                    rtt_log=temp_dir / "session-rtt.log",
                    tmp_dir=temp_dir,
                    timeout=1,
                    server_ready_timeout=0.01,
                    server_exit_timeout=0.01,
                )
        gdb_run.assert_not_called()
        connect.assert_not_called()
        self.assertFalse(outcome["server_ready"])
        self.assertFalse(outcome["gdb_started"])
        self.assertFalse(outcome["rtt_connected"])
        self.assertEqual(outcome["transport_classification"], "TRANSPORT_NOT_READY")

    def test_two_consecutive_sessions_use_independent_server_processes(self) -> None:
        pids = iter((405, 406))

        class FakeServer:
            def __init__(self, pid: int) -> None:
                self.pid = pid
                self.exited = False

            def poll(self) -> int | None:
                return 0 if self.exited else None

            def wait(self, timeout: float | None = None) -> int:
                self.exited = True
                return 0

            def terminate(self) -> None:
                raise AssertionError("forced termination used")

            def kill(self) -> None:
                raise AssertionError("kill used")

        class FakeBannerSocket:
            def settimeout(self, timeout: float) -> None:
                return None

            def recv(self, size: int) -> bytes:
                return b"SEGGER J-Link V8.18 - Real time terminal output\r\n"

            def close(self) -> None:
                return None

        with tempfile.TemporaryDirectory(dir=DRIVER.DEFAULT_TMP_DIR) as temp:
            temp_dir = Path(temp)
            with (
                mock.patch.object(
                    DRIVER,
                    "start_server",
                    side_effect=lambda *args, **kwargs: (
                        FakeServer(next(pids)), io.StringIO()
                    ),
                ),
                mock.patch.object(DRIVER, "wait_for_server_ready"),
                mock.patch.object(
                    DRIVER.socket, "create_connection", return_value=FakeBannerSocket()
                ),
                mock.patch.object(DRIVER, "port_is_listening", return_value=False),
                mock.patch.object(DRIVER, "wait_for_ports_closed", return_value=True),
                mock.patch.object(
                    DRIVER.subprocess,
                    "run",
                    return_value=SimpleNamespace(returncode=0),
                ),
            ):
                outcomes = []
                for index in (1, 2):
                    outcomes.append(
                        DRIVER.run_gdb_session(
                            jlink_dir=Path("C:/JLink"),
                            gdb=Path("C:/gdb.exe"),
                            gdb_script=temp_dir / f"session-{index}.gdb",
                            gdb_log=temp_dir / f"session-{index}-gdb.log",
                            server_log=temp_dir / f"session-{index}-server.log",
                            rtt_log=temp_dir / f"session-{index}-rtt.log",
                            tmp_dir=temp_dir,
                            timeout=1,
                            server_ready_timeout=0.01,
                            server_exit_timeout=0.01,
                        )
                    )
        self.assertEqual([item["server_pid"] for item in outcomes], [405, 406])
        self.assertTrue(all(item["server_natural_exit"] for item in outcomes))
        self.assertTrue(all(item["transport_classification"] == "PASS" for item in outcomes))

    def _write_snapshot_pair(
        self, temp: Path, pre_cb: bytes, ring: bytes
    ) -> tuple[Path, Path]:
        cb_path = temp / "derive-cb.bin"
        ring_path = temp / "derive-ring.bin"
        cb_path.write_bytes(pre_cb)
        ring_path.write_bytes(ring)
        return cb_path, ring_path

    def test_derive_rtt_pending_structural_failures(self) -> None:
        payload = self._measurement("PATCH") + b"\r\n"
        cases: list[tuple[str, bytes, bytes]] = [
            (
                "bad_signature",
                self._make_control_block(wr_off=len(payload), rd_off=0, signature=b"XEGGER RTT"),
                self._make_ring(payload),
            ),
            (
                "bad_up_size",
                self._make_control_block(wr_off=len(payload), rd_off=0, up_size=512),
                self._make_ring(payload),
            ),
            (
                "bad_pbuffer",
                self._make_control_block(wr_off=len(payload), rd_off=0, p_buffer=0x08010000),
                self._make_ring(payload),
            ),
            (
                "bad_flags",
                self._make_control_block(wr_off=len(payload), rd_off=0, flags=0),
                self._make_ring(payload),
            ),
            (
                "bad_buffer_counts",
                self._make_control_block(wr_off=len(payload), rd_off=0, max_up=1),
                self._make_ring(payload),
            ),
            (
                "bad_ring_size",
                self._make_control_block(wr_off=len(payload), rd_off=0),
                b"\xEE" * 512,
            ),
            (
                "wroff_out_of_range",
                self._make_control_block(wr_off=2000, rd_off=0),
                self._make_ring(payload),
            ),
            (
                "rdoff_out_of_range",
                self._make_control_block(wr_off=len(payload), rd_off=2000),
                self._make_ring(payload),
            ),
        ]
        for name, cb, ring in cases:
            with self.subTest(case=name):
                with tempfile.TemporaryDirectory(dir=DRIVER.DEFAULT_TMP_DIR) as temp:
                    cb_path, ring_path = self._write_snapshot_pair(Path(temp), cb, ring)
                    result = DRIVER.derive_rtt_pending(
                        cb_path, ring_path, "PATCH", Path(temp) / "pending.bin"
                    )
                self.assertEqual(result["status"], "FAIL")
                self.assertIn("error", result)

    def test_derive_rtt_pending_wraparound_inventory(self) -> None:
        payload = self._measurement("PATCH") + b"\r\n"
        ring = bytearray(b"\xEE" * 1024)
        # Inventory wrapped across the ring end: bytes 1000..1023 plus 0..9.
        tail = payload[:24]
        head = payload[24:]
        ring[1000:1024] = tail
        ring[0:len(head)] = head
        cb = self._make_control_block(wr_off=len(head), rd_off=1000)
        with tempfile.TemporaryDirectory(dir=DRIVER.DEFAULT_TMP_DIR) as temp:
            cb_path, ring_path = self._write_snapshot_pair(Path(temp), cb, bytes(ring))
            pending_path = Path(temp) / "pending.bin"
            result = DRIVER.derive_rtt_pending(cb_path, ring_path, "PATCH", pending_path)
            written = pending_path.read_bytes() if pending_path.exists() else None
        self.assertEqual(result["status"], "ELIGIBLE")
        self.assertEqual(result["pending_count"], len(payload))
        self.assertEqual(written, payload)

    def test_verify_rtt_postcheck_pass_and_failures(self) -> None:
        payload = self._measurement("PATCH") + b"\r\n"
        wr = len(payload)
        pre = self._make_control_block(wr_off=wr, rd_off=0)
        good_post = self._make_control_block(wr_off=wr, rd_off=wr)
        with tempfile.TemporaryDirectory(dir=DRIVER.DEFAULT_TMP_DIR) as temp:
            temp_dir = Path(temp)
            pre_path = temp_dir / "pre.bin"
            post_path = temp_dir / "post.bin"
            pre_path.write_bytes(pre)
            post_path.write_bytes(good_post)
            passed = DRIVER.verify_rtt_postcheck(pre_path, post_path, wr)
            self.assertEqual(passed["status"], "PASS")
            self.assertEqual(passed["consumed_count"], wr)
            self.assertEqual(passed["control_block_outside_rd_off_changes"], 0)

            # WrOff changed during host consumption.
            post_path.write_bytes(self._make_control_block(wr_off=wr + 1, rd_off=wr))
            wr_case = DRIVER.verify_rtt_postcheck(pre_path, post_path, wr)
            self.assertEqual(wr_case["status"], "FAIL")
            self.assertIn("WrOff changed", wr_case["error"])

            # RdOff stalled (did not consume the inventory).
            post_path.write_bytes(self._make_control_block(wr_off=wr, rd_off=0))
            stall = DRIVER.verify_rtt_postcheck(pre_path, post_path, wr)
            self.assertEqual(stall["status"], "FAIL")
            self.assertIn("RdOff did not consume", stall["error"])

            # RdOff consumed a different amount than the pending inventory.
            post_path.write_bytes(self._make_control_block(wr_off=wr, rd_off=wr - 1))
            short = DRIVER.verify_rtt_postcheck(pre_path, post_path, wr)
            self.assertEqual(short["status"], "FAIL")

            # A byte outside the four-byte RdOff word changed.
            mutated = bytearray(self._make_control_block(wr_off=wr, rd_off=wr))
            mutated[0x30] = (mutated[0x30] + 1) & 0xFF
            post_path.write_bytes(bytes(mutated))
            extra = DRIVER.verify_rtt_postcheck(pre_path, post_path, wr)
            self.assertEqual(extra["status"], "FAIL")
            self.assertIn("outside the four-byte", extra["error"])

            # RdOff within the word may change freely (that is the logger's
            # only legal write).
            mutated = bytearray(self._make_control_block(wr_off=wr, rd_off=wr))
            struct.pack_into("<I", mutated, DRIVER.RTT_CB_UP0_RDOFF_OFFSET, wr)
            post_path.write_bytes(bytes(mutated))
            again = DRIVER.verify_rtt_postcheck(pre_path, post_path, wr)
            self.assertEqual(again["status"], "PASS")

    def _run_fake_logger(
        self,
        pending: bytes,
        *,
        delivered: bytes | None,
        exit_early: bool = False,
        residual_lines: int = 0,
    ) -> dict[str, object]:
        loggers: list[object] = []

        class FakeLogger:
            pid = 901

            def __init__(self) -> None:
                # None means still running; the Stop-Process mock below makes
                # every logger exit once the cleanup command is issued.
                self.returncode = 5 if exit_early else None
                loggers.append(self)

            def poll(self) -> int | None:
                return self.returncode

        class FakeTasklist:
            stdout = "\r\n".join(
                ['"JLinkRTTLogger.exe","1234"' for _ in range(residual_lines)]
            )

        with tempfile.TemporaryDirectory(dir=DRIVER.DEFAULT_TMP_DIR) as temp:
            temp_dir = Path(temp)
            pending_path = temp_dir / "pending.bin"
            pending_path.write_bytes(pending)
            raw_log = temp_dir / "raw.log"
            console_log = temp_dir / "console.log"

            def fake_popen(*args: object, **kwargs: object) -> FakeLogger:
                # The real logger writes its output file after launch; write
                # the scripted bytes here so the pre-existing-file cleanup in
                # run_rtt_logger_capture does not delete them first.
                if delivered is not None:
                    raw_log.write_bytes(delivered)
                return FakeLogger()

            def fake_run(*args: object, **kwargs: object) -> FakeTasklist:
                # The Stop-Process cleanup makes the running loggers exit.
                for logger in loggers:
                    if logger.returncode is None:
                        logger.returncode = 0
                return FakeTasklist()

            with (
                mock.patch.object(DRIVER.subprocess, "Popen", side_effect=fake_popen),
                mock.patch.object(DRIVER.subprocess, "run", side_effect=fake_run),
            ):
                return DRIVER.run_rtt_logger_capture(
                    pending_path,
                    raw_log,
                    console_log,
                    0x20053E1C,
                    temp_dir,
                    payload_timeout=0.4,
                    settle_seconds=0.05,
                )

    def test_logger_capture_passes_on_byte_identical_payload(self) -> None:
        payload = self._measurement("PATCH") + b"\r\n"
        result = self._run_fake_logger(payload, delivered=payload)
        self.assertEqual(result["status"], "PASS")
        self.assertTrue(result["payload_complete"])
        self.assertEqual(result["payload_bytes"], len(payload))
        self.assertEqual(result["residual_rtt_logger_processes"], 0)
        self.assertTrue(result["logger_stopped"])

    def test_logger_capture_fails_closed_on_timeout_and_extra_bytes(self) -> None:
        payload = self._measurement("PATCH") + b"\r\n"
        timeout_case = self._run_fake_logger(payload, delivered=b"")
        self.assertEqual(timeout_case["status"], "FAIL")
        self.assertTrue(timeout_case["payload_timeout"])
        extra_case = self._run_fake_logger(
            payload, delivered=payload + b"extra\r\n"
        )
        self.assertEqual(extra_case["status"], "FAIL")
        self.assertIn("extra bytes", str(extra_case["error"]))
        mismatch_case = self._run_fake_logger(
            payload, delivered=b"X" * len(payload)
        )
        self.assertEqual(mismatch_case["status"], "FAIL")
        self.assertIn("differs", str(mismatch_case["error"]))

    def test_logger_capture_fails_closed_on_early_exit_and_residuals(self) -> None:
        payload = self._measurement("PATCH") + b"\r\n"
        early = self._run_fake_logger(payload, delivered=payload, exit_early=True)
        self.assertEqual(early["status"], "FAIL")
        self.assertIn("exited early", str(early["error"]))
        residual = self._run_fake_logger(
            payload, delivered=payload, residual_lines=1
        )
        self.assertEqual(residual["status"], "FAIL")
        self.assertIn("residual", str(residual["error"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
