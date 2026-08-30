#!/usr/bin/env python3
"""Offline regression checks for the persistent P2-6 RTT OTA driver."""

from __future__ import annotations

import importlib.util
import io
from pathlib import Path
import re
import shutil
import socket
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
            "rtt_payload_ready": True,
            "rtt_drain_success": True,
            "rtt_drain_complete": True,
            "rtt_drain_deadline_expired": False,
            "rtt_payload_complete": True,
            "rtt_record_count": 1,
            "rtt_matching_record_count": 1,
        }
        self.assertEqual(DRIVER.classify_transport_session(outcome), "PASS")
        self.assertFalse(outcome.get("rtt_channel_binding_verified", False))

    def _run_fake_session(
        self,
        payload: bytes = b"",
        *,
        measurement_policy: bool,
        expected_kind: str = "PATCH",
        gdb_exit_code: int = 0,
        capture_error: str | None = None,
        socket_eof: bool = False,
        socket_error: bool = False,
        delayed: bool = False,
    ) -> tuple[dict[str, object], float]:
        class FakeServer:
            pid = 501

            def __init__(self) -> None:
                self.exited = False

            def poll(self) -> int | None:
                return 0 if self.exited else None

            def wait(self, timeout: float | None = None) -> int:
                self.exited = True
                return 0

            def terminate(self) -> None:
                raise AssertionError("unexpected terminate")

            def kill(self) -> None:
                raise AssertionError("unexpected kill")

        class FakeCapture:
            def __init__(
                capture_self,
                host: str,
                port: int,
                output: Path,
                stop: threading.Event,
                measurement_policy: bool = False,
                expected_kind: str | None = None,
            ) -> None:
                capture_self.output = output
                capture_self.measurement_policy = measurement_policy
                capture_self.expected_kind = expected_kind
                capture_self.connected = threading.Event()
                capture_self.socket_connected = False
                capture_self.socket_eof = socket_eof
                capture_self.socket_error = socket_error
                capture_self.payload_ready = False
                capture_self.drain_started = False
                capture_self.drain_success = False
                capture_self.drain_complete = False
                capture_self.drain_deadline_expired = False
                capture_self.payload_timeout = False
                capture_self.error = capture_error
                capture_self.ident = None

            def start(capture_self) -> None:
                capture_self.ident = 1
                capture_self.socket_connected = capture_error is None
                if capture_self.socket_connected:
                    capture_self.connected.set()
                if not delayed:
                    capture_self.output.write_bytes(payload)

            def wait_for_bounded_drain(
                capture_self, timeout: float, quiet_timeout: float = 0.1
            ) -> None:
                capture_self.drain_started = True
                if delayed:
                    time.sleep(0.03)
                    capture_self.output.write_bytes(payload)
                capture_self.payload_ready = bool(payload.endswith(b"\n") and b"P2_6 kind=" in payload)
                capture_self.drain_success = capture_self.payload_ready
                capture_self.drain_deadline_expired = False
                capture_self.payload_timeout = not capture_self.drain_success
                capture_self.drain_complete = capture_self.drain_success

            def join(capture_self, timeout: float | None = None) -> None:
                return None

            def is_alive(capture_self) -> bool:
                return False

        with tempfile.TemporaryDirectory(dir=DRIVER.DEFAULT_TMP_DIR) as temp:
            temp_dir = Path(temp)
            with (
                mock.patch.object(DRIVER, "start_server", return_value=(FakeServer(), io.StringIO())),
                mock.patch.object(DRIVER, "wait_for_server_ready"),
                mock.patch.object(DRIVER, "RttCapture", FakeCapture),
                mock.patch.object(DRIVER, "port_is_listening", return_value=False),
                mock.patch.object(DRIVER, "wait_for_ports_closed", return_value=True),
                mock.patch.object(
                    DRIVER.subprocess,
                    "run",
                    return_value=SimpleNamespace(returncode=gdb_exit_code),
                ),
            ):
                started = time.monotonic()
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
                    measurement_policy=measurement_policy,
                    expected_kind=expected_kind,
                    drain_timeout=0.05,
                    quiet_timeout=0.02,
                )
                elapsed = time.monotonic() - started
        return outcome, elapsed

    def test_default_shared_policy_does_not_require_measurement(self) -> None:
        outcome, _ = self._run_fake_session(measurement_policy=False)
        self.assertEqual(outcome["transport_classification"], "PASS")
        self.assertFalse(outcome["rtt_measurement_required"])
        self.assertEqual(outcome["rtt_record_count"], 0)

    def test_ota_policy_rejects_banner_only_and_missing_payload(self) -> None:
        for payload in (b"", b"SEGGER RTT\r\n"):
            with self.subTest(payload=payload):
                outcome, _ = self._run_fake_session(payload, measurement_policy=True)
                self.assertEqual(outcome["transport_classification"], "RTT_PAYLOAD_FAIL")
                self.assertFalse(outcome["rtt_payload_ready"])

    def test_ota_policy_waits_for_delayed_payload(self) -> None:
        outcome, elapsed = self._run_fake_session(
            b"SEGGER RTT\r\nnoise\n" + self._measurement("patch"),
            measurement_policy=True,
            delayed=True,
        )
        self.assertGreaterEqual(elapsed, 0.025)
        self.assertEqual(outcome["transport_classification"], "PASS")
        self.assertTrue(outcome["rtt_payload_ready"])
        self.assertTrue(outcome["rtt_drain_complete"])
        self.assertTrue(outcome["rtt_payload_complete"])
        self.assertEqual(outcome["rtt_record_count"], 1)
        self.assertFalse(outcome["rtt_channel_binding_verified"])

    def test_ota_policy_rejects_duplicate_and_wrong_kind(self) -> None:
        duplicate, _ = self._run_fake_session(
            self._measurement("PATCH") * 2,
            measurement_policy=True,
        )
        wrong_kind, _ = self._run_fake_session(
            self._measurement("FULL"),
            measurement_policy=True,
            expected_kind="PATCH",
        )
        self.assertEqual(duplicate["rtt_record_count"], 2)
        self.assertEqual(duplicate["transport_classification"], "RTT_PAYLOAD_FAIL")
        self.assertEqual(wrong_kind["rtt_matching_record_count"], 0)
        self.assertEqual(wrong_kind["transport_classification"], "RTT_PAYLOAD_FAIL")

    def test_ota_policy_rejects_eof_error_and_truncated_payload(self) -> None:
        eof, _ = self._run_fake_session(
            b"SEGGER RTT\r\n", measurement_policy=True, socket_eof=True
        )
        error, _ = self._run_fake_session(
            self._measurement("PATCH"),
            measurement_policy=True,
            capture_error="socket failed",
            socket_error=True,
        )
        truncated, _ = self._run_fake_session(
            self._measurement("PATCH").rstrip(b"\r\n"),
            measurement_policy=True,
        )
        self.assertEqual(eof["transport_classification"], "RTT_PAYLOAD_FAIL")
        self.assertEqual(error["transport_classification"], "RTT_NOT_READY")
        self.assertEqual(truncated["transport_classification"], "RTT_PAYLOAD_FAIL")

    def test_ota_policy_rejects_complete_payload_after_eof_or_drain_timeout(self) -> None:
        eof, _ = self._run_fake_session(
            self._measurement("PATCH"),
            measurement_policy=True,
            socket_eof=True,
        )
        socket_error, _ = self._run_fake_session(
            self._measurement("PATCH"),
            measurement_policy=True,
            socket_error=True,
        )
        self.assertEqual(eof["rtt_record_count"], 1)
        self.assertTrue(eof["rtt_socket_eof"])
        self.assertEqual(eof["transport_classification"], "RTT_PAYLOAD_FAIL")
        self.assertEqual(socket_error["rtt_record_count"], 1)
        self.assertTrue(socket_error["rtt_socket_error"])
        self.assertEqual(
            socket_error["transport_classification"], "RTT_PAYLOAD_FAIL"
        )

    def test_real_rtt_capture_payload_then_timeout_fails_closed(self) -> None:
        payload = self._measurement("PATCH")

        class TimeoutSocket:
            def __init__(self) -> None:
                self.first = True

            def settimeout(self, timeout: float) -> None:
                return None

            def recv(self, size: int) -> bytes:
                if self.first:
                    self.first = False
                    return payload
                raise socket.timeout()

            def close(self) -> None:
                return None

        with tempfile.TemporaryDirectory(dir=DRIVER.DEFAULT_TMP_DIR) as temp:
            output = Path(temp) / "timeout-capture.log"
            stop = threading.Event()
            capture = DRIVER.RttCapture(
                "127.0.0.1",
                DRIVER.RTT_PORT,
                output,
                stop,
                connect_timeout=1.0,
                measurement_policy=True,
                expected_kind="PATCH",
            )
            with mock.patch.object(
                DRIVER.socket, "create_connection", return_value=TimeoutSocket()
            ):
                capture.start()
                self.assertTrue(capture.connected.wait(1.0))
                deadline = time.monotonic() + 1.0
                while not capture.payload_ready and time.monotonic() < deadline:
                    time.sleep(0.005)
                capture.wait_for_bounded_drain(0.05)
                stop.set()
                capture.join(1.0)
            records = DRIVER.parse_measurements(output.read_bytes())

        self.assertTrue(capture.payload_ready)
        self.assertEqual(len(records), 1)
        self.assertTrue(capture.drain_started)
        self.assertFalse(capture.drain_success)
        self.assertFalse(capture.drain_complete)
        self.assertTrue(capture.drain_deadline_expired)
        self.assertTrue(capture.payload_timeout)
        self.assertEqual(
            DRIVER.classify_transport_session(
                {
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
                    "rtt_payload_ready": True,
                    "rtt_drain_success": False,
                    "rtt_drain_complete": False,
                    "rtt_drain_deadline_expired": True,
                    "rtt_payload_complete": False,
                    "rtt_payload_timeout": True,
                    "rtt_socket_eof": False,
                    "rtt_socket_error": False,
                    "rtt_record_count": 1,
                    "rtt_matching_record_count": 1,
                }
            ),
            "RTT_PAYLOAD_FAIL",
        )

    def _run_real_capture_sequence(
        self,
        responses: list[bytes | BaseException | object],
        *,
        drain: float = 0.1,
        quiet: float = 0.02,
        wait_payload_before_drain: bool = False,
    ) -> tuple[DRIVER.RttCapture, bytes]:
        class SequenceSocket:
            def __init__(self, values: list[bytes | BaseException]) -> None:
                self.values = iter(values)

            def settimeout(self, timeout: float) -> None:
                return None

            def recv(self, size: int) -> bytes:
                try:
                    value = next(self.values)
                except StopIteration:
                    raise socket.timeout()
                if callable(value):
                    value = value()
                if isinstance(value, BaseException):
                    raise value
                return value

            def close(self) -> None:
                return None

        with tempfile.TemporaryDirectory(dir=DRIVER.DEFAULT_TMP_DIR) as temp:
            output = Path(temp) / "sequence-capture.log"
            stop = threading.Event()
            capture = DRIVER.RttCapture(
                "127.0.0.1",
                DRIVER.RTT_PORT,
                output,
                stop,
                connect_timeout=1.0,
                measurement_policy=True,
                expected_kind="PATCH",
            )
            with mock.patch.object(
                DRIVER.socket,
                "create_connection",
                return_value=SequenceSocket(responses),
            ):
                capture.start()
                self.assertTrue(capture.connected.wait(1.0))
                if wait_payload_before_drain:
                    deadline = time.monotonic() + 1.0
                    while not capture.payload_ready and time.monotonic() < deadline:
                        time.sleep(0.002)
                    self.assertTrue(capture.payload_ready)
                capture.wait_for_bounded_drain(drain, quiet)
                stop.set()
                capture.join(1.0)
            data = output.read_bytes()
        return capture, data

    def test_pre_drain_payload_enters_quiet_window_and_passes(self) -> None:
        capture, data = self._run_real_capture_sequence(
            [self._measurement("PATCH")],
            wait_payload_before_drain=True,
        )
        self.assertEqual(len(DRIVER.parse_measurements(data)), 1)
        self.assertTrue(capture.payload_ready)
        self.assertTrue(capture.drain_success)
        self.assertTrue(capture.drain_complete)
        self.assertFalse(capture.drain_deadline_expired)

    def test_delayed_payload_arrives_within_outer_and_quiet_windows(self) -> None:
        capture, data = self._run_real_capture_sequence(
            [lambda: (time.sleep(0.01), self._measurement("patch"))[1]]
        )
        self.assertEqual(len(DRIVER.parse_measurements(data)), 1)
        self.assertTrue(capture.payload_ready)
        self.assertTrue(capture.drain_success)
        self.assertTrue(capture.drain_complete)

    def test_second_record_during_quiet_window_fails_closed(self) -> None:
        capture, data = self._run_real_capture_sequence(
            [
                self._measurement("PATCH"),
                lambda: (time.sleep(0.01), self._measurement("PATCH"))[1],
            ],
            drain=0.06,
            quiet=0.02,
            wait_payload_before_drain=True,
        )
        self.assertEqual(len(DRIVER.parse_measurements(data)), 2)
        self.assertFalse(capture.drain_success)
        self.assertFalse(capture.drain_complete)
        self.assertTrue(capture.drain_deadline_expired)
        self.assertTrue(capture.payload_timeout)

    def test_complete_payload_then_eof_or_socket_error_fails_closed(self) -> None:
        eof, _ = self._run_real_capture_sequence(
            [self._measurement("PATCH"), b""]
        )
        error, _ = self._run_real_capture_sequence(
            [self._measurement("PATCH"), OSError("socket failed")]
        )
        self.assertTrue(eof.socket_eof)
        self.assertFalse(eof.drain_success)
        self.assertFalse(eof.drain_complete)
        self.assertTrue(error.socket_error)
        self.assertFalse(error.drain_success)
        self.assertFalse(error.drain_complete)

    def test_payload_arriving_too_late_for_quiet_window_times_out(self) -> None:
        capture, data = self._run_real_capture_sequence(
            [lambda: (time.sleep(0.015), self._measurement("PATCH"))[1]],
            drain=0.02,
            quiet=0.05,
        )
        self.assertEqual(len(DRIVER.parse_measurements(data)), 1)
        self.assertTrue(capture.payload_ready)
        self.assertFalse(capture.drain_success)
        self.assertFalse(capture.drain_complete)
        self.assertTrue(capture.drain_deadline_expired)
        self.assertTrue(capture.payload_timeout)

    def test_shared_policy_ignores_invalid_measurement_content(self) -> None:
        payloads = (
            self._measurement("PATCH").rstrip(b"\r\n"),
            self._measurement("OTHER"),
        )
        for payload in payloads:
            with self.subTest(payload=payload[-32:]):
                outcome, _ = self._run_fake_session(
                    payload,
                    measurement_policy=False,
                )
                self.assertEqual(outcome["transport_classification"], "PASS")
                self.assertIsNone(outcome["session_error"])
                self.assertIsNone(outcome["rtt_payload_parse_error"])
                self.assertEqual(outcome["rtt_record_count"], 0)

    def test_gdb_nonzero_fails_even_with_valid_payload(self) -> None:
        outcome, _ = self._run_fake_session(
            self._measurement("PATCH"),
            measurement_policy=True,
            gdb_exit_code=7,
        )
        self.assertEqual(outcome["rtt_record_count"], 1)
        self.assertEqual(outcome["transport_classification"], "GDB_FAIL")

    def test_rtt_capture_eof_and_socket_error_do_not_fake_payload_ready(self) -> None:
        class FakeSocket:
            def __init__(self, responses: list[bytes | Exception]) -> None:
                self.responses = iter(responses)

            def settimeout(self, timeout: float) -> None:
                return None

            def recv(self, size: int) -> bytes:
                response = next(self.responses)
                if isinstance(response, Exception):
                    raise response
                return response

            def close(self) -> None:
                return None

        cases = (
            (FakeSocket([b"SEGGER RTT\r\n", b""]), True, False),
            (FakeSocket([OSError("recv failed")]), False, True),
        )
        for fake_socket, expect_eof, expect_error in cases:
            with self.subTest(eof=expect_eof, error=expect_error):
                with tempfile.TemporaryDirectory(dir=DRIVER.DEFAULT_TMP_DIR) as temp:
                    output = Path(temp) / "capture.log"
                    capture = DRIVER.RttCapture(
                        "127.0.0.1", DRIVER.RTT_PORT, output, threading.Event()
                    )
                    with mock.patch.object(
                        DRIVER.socket, "create_connection", return_value=fake_socket
                    ):
                        capture.run()
                self.assertTrue(capture.socket_connected)
                self.assertEqual(capture.socket_eof, expect_eof)
                self.assertEqual(capture.socket_error, expect_error)
                self.assertFalse(capture.payload_ready)
                self.assertFalse(capture.connected.is_set() and capture.error is not None and not capture.socket_connected)

    def test_shared_rtt_capture_does_not_run_strict_parser(self) -> None:
        class FakeSocket:
            def __init__(self) -> None:
                self.responses = iter([b"P2_6 kind=OTHER\r\n", b""])

            def settimeout(self, timeout: float) -> None:
                return None

            def recv(self, size: int) -> bytes:
                return next(self.responses)

            def close(self) -> None:
                return None

        with tempfile.TemporaryDirectory(dir=DRIVER.DEFAULT_TMP_DIR) as temp:
            output = Path(temp) / "shared-capture.log"
            capture = DRIVER.RttCapture(
                "127.0.0.1",
                DRIVER.RTT_PORT,
                output,
                threading.Event(),
                measurement_policy=False,
            )
            with mock.patch.object(
                DRIVER.socket, "create_connection", return_value=FakeSocket()
            ):
                capture.run()
            captured = output.read_bytes()
        self.assertTrue(capture.socket_connected)
        self.assertTrue(capture.socket_eof)
        self.assertIsNone(capture.error)
        self.assertFalse(capture.payload_ready)
        self.assertEqual(captured, b"P2_6 kind=OTHER\r\n")

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
            DRIVER.gdb_command_file(
                output,
                DRIVER.ROOT / "firmware.elf",
                selected_symbols(),
                bytes(range(96)),
                layout_values(),
                "/P2-6-RUN-20260820-01/P2-6A-PATCH-SD-R2.etu",
                "PATCH",
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

        class FakeCapture:
            def __init__(self, *args: object, **kwargs: object) -> None:
                self.connected = threading.Event()
                self.socket_connected = False
                self.error = None
                self.ident = None

            def start(self) -> None:
                events.append("rtt_start")
                self.ident = 1
                self.socket_connected = True
                self.connected.set()

            def join(self, timeout: float | None = None) -> None:
                events.append("rtt_join")

            def is_alive(self) -> bool:
                return False

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
                mock.patch.object(DRIVER, "RttCapture", FakeCapture),
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
        self.assertEqual(
            events,
            ["start_server", "ready", "rtt_start", "gdb", "rtt_join", "server_wait"],
        )
        self.assertTrue(outcome["server_ready"])
        self.assertTrue(outcome["server_natural_exit"])
        self.assertFalse(outcome["server_terminate_sent"])
        self.assertEqual(outcome["transport_classification"], "PASS")

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

        class ForbiddenCapture:
            def __init__(self, *args: object, **kwargs: object) -> None:
                self.connected = threading.Event()
                self.socket_connected = False
                self.error = None
                self.ident = None

            def start(self) -> None:
                raise AssertionError("RTT capture started before readiness")

            def join(self, timeout: float | None = None) -> None:
                raise AssertionError("RTT capture joined despite never starting")

            def is_alive(self) -> bool:
                return False

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
                mock.patch.object(DRIVER, "RttCapture", ForbiddenCapture),
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

        class FakeCapture:
            def __init__(self, *args: object, **kwargs: object) -> None:
                self.connected = threading.Event()
                self.socket_connected = False
                self.error = None
                self.ident = None

            def start(self) -> None:
                self.ident = 1
                self.socket_connected = True
                self.connected.set()

            def join(self, timeout: float | None = None) -> None:
                return None

            def is_alive(self) -> bool:
                return False

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
                mock.patch.object(DRIVER, "RttCapture", FakeCapture),
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


if __name__ == "__main__":
    unittest.main(verbosity=2)
