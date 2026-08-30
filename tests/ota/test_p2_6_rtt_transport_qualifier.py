#!/usr/bin/env python3
"""Offline regression checks for the P2-6 transport qualifier."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock


MODULE_PATH = Path(__file__).with_name("p2_6_rtt_transport_qualifier.py")
SPEC = importlib.util.spec_from_file_location("p2_6_rtt_transport_qualifier", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
QUALIFIER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(QUALIFIER)


def selected_symbols() -> dict[str, int]:
    driver = QUALIFIER.driver
    return {
        driver.SD_READY_SYMBOL: 0x20053214,
        driver.RTT_SYMBOL: 0x20053E1C,
        driver.OVERLAY_OWNER_SYMBOL: 0x20053FA0,
        driver.OVERLAY_WORKSPACE_SYMBOL: 0x20058000,
    }


def layout_values() -> dict[str, int]:
    return {
        "OTA_APP_ORIGIN": 0x08010000,
        "OTA_FW_HEADER_OFFSET": 0x400,
        "OTA_FW_HEADER_SIZE": 96,
        "OTA_OVERLAY_ORIGIN": 0x20058000,
        "OTA_OVERLAY_WORKSPACE_LENGTH": 0xA000,
    }


class P26TransportQualifierTest(unittest.TestCase):
    def test_generated_scripts_are_read_only_and_session_bounded(self) -> None:
        driver = QUALIFIER.driver
        with tempfile.TemporaryDirectory(dir=driver.ROOT / ".cache") as temp:
            temp_dir = Path(temp)
            scripts = []
            for session in (1, 2):
                script = temp_dir / f"session-{session}.gdb"
                QUALIFIER.transport_gdb_command_file(
                    script,
                    driver.ROOT / "firmware.elf",
                    selected_symbols(),
                    bytes(range(96)),
                    layout_values(),
                    session,
                )
                QUALIFIER.audit_read_only_script(script)
                text = script.read_text(encoding="ascii")
                scripts.append(text)
                self.assertIn("target remote 127.0.0.1:24361", text)
                self.assertIn("monitor halt", text)
                self.assertIn(f"P2_6_TR PASS session={session}", text)
                self.assertIn("detach", text)
                self.assertNotIn("continue", text.lower())
                self.assertNotIn("lv_fs_", text)
                self.assertNotIn("loadfile", text.lower())
                self.assertNotIn("restore ", text.lower())
                self.assertNotIn("set *", text.lower())
            self.assertNotEqual(scripts[0], scripts[1])

    def test_marker_counts_and_session_pass_require_natural_cleanup(self) -> None:
        session = {
            "transport_classification": "PASS",
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
        }
        gdb_text = "\n".join(
            (
                "P2_6_TR attached_stopped session=1 pc=0x08040000",
                "P2_6_IDENTITY PASS label=tr_session_1_fw header_bytes=96",
                "P2_6_TR STATE_PASS session=1 sd=1 vtor=0x08010000 cfsr=0 owner=0",
                "P2_6_TR PASS session=1",
            )
        )
        server_text = QUALIFIER.driver.SERVER_READY_MARKER
        self.assertEqual(
            QUALIFIER.marker_counts(gdb_text, 1),
            {"attached": 1, "identity": 1, "state": 1, "pass": 1},
        )
        self.assertTrue(QUALIFIER.session_pass(session, gdb_text, server_text, 1))
        session["server_natural_exit"] = False
        self.assertFalse(QUALIFIER.session_pass(session, gdb_text, server_text, 1))

    def test_qualification_runs_exactly_two_sessions_and_never_retries(self) -> None:
        driver = QUALIFIER.driver
        symbols = selected_symbols()
        with tempfile.TemporaryDirectory(dir=driver.ROOT / ".cache") as temp:
            temp_dir = Path(temp)
            build = temp_dir / "build"
            build.mkdir()
            elf = build / "firmware.elf"
            map_path = build / "firmware.map"
            elf.write_bytes(b"elf")
            map_path.write_bytes(b"map")
            image = temp_dir / "image.bin"
            image.write_bytes(b"image")
            args = SimpleNamespace(
                build=str(build),
                log_dir=str(temp_dir / "logs"),
                tmp_dir=str(temp_dir / "tmp"),
                device_image=str(image),
                output_prefix="qualification-test",
                gdb=str(Path(__file__)),
                nm=str(Path(__file__)),
                jlink_dir="C:/JLink",
                timeout=1,
                server_ready_timeout=0.01,
                server_exit_timeout=0.01,
                inter_session_delay=0,
            )

            def fake_session(**kwargs: object) -> dict[str, object]:
                index = len(fake_session.calls) + 1
                fake_session.calls.append(index)
                gdb_log = Path(str(kwargs["gdb_log"]))
                server_log = Path(str(kwargs["server_log"]))
                rtt_log = Path(str(kwargs["rtt_log"]))
                gdb_log.write_text(
                    "\n".join(
                        (
                            f"P2_6_TR attached_stopped session={index} pc=0x08040000",
                            f"P2_6_IDENTITY PASS label=tr_session_{index}_fw header_bytes=96",
                            f"P2_6_TR STATE_PASS session={index} sd=1 vtor=0x08010000 cfsr=0 owner=0",
                            f"P2_6_TR PASS session={index}",
                        )
                    ),
                    encoding="ascii",
                )
                server_log.write_text(driver.SERVER_READY_MARKER, encoding="ascii")
                rtt_log.write_bytes(b"")
                return {
                    "server_started": True,
                    "server_pid": 500 + index,
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
                    "transport_classification": "PASS",
                }

            fake_session.calls = []
            with (
                mock.patch.object(
                    driver,
                    "require_frozen_build",
                    return_value=(elf, map_path),
                ),
                mock.patch.object(
                    driver,
                    "load_frozen_device_header",
                    return_value=(bytes(range(96)), layout_values()),
                ),
                mock.patch.object(
                    driver,
                    "read_symbol_table",
                    return_value={name: [value] for name, value in symbols.items()},
                ),
                mock.patch.object(driver, "run_gdb_session", side_effect=fake_session),
                mock.patch.object(QUALIFIER.time, "sleep") as sleep,
                mock.patch("builtins.print"),
            ):
                result = QUALIFIER.run_qualification(args)
            self.assertEqual(result, 0)
            self.assertEqual(fake_session.calls, [1, 2])
            self.assertEqual(sleep.call_count, 1)
            result_path = temp_dir / "logs" / "qualification-test-result.json"
            self.assertTrue(result_path.is_file())

    def test_qualification_stops_after_first_failed_session(self) -> None:
        driver = QUALIFIER.driver
        with tempfile.TemporaryDirectory(dir=driver.ROOT / ".cache") as temp:
            temp_dir = Path(temp)
            build = temp_dir / "build"
            build.mkdir()
            elf = build / "firmware.elf"
            map_path = build / "firmware.map"
            elf.write_bytes(b"elf")
            map_path.write_bytes(b"map")
            image = temp_dir / "image.bin"
            image.write_bytes(b"image")
            args = SimpleNamespace(
                build=str(build), log_dir=str(temp_dir / "logs"), tmp_dir=str(temp_dir / "tmp"),
                device_image=str(image), output_prefix="stop-test", gdb=str(Path(__file__)),
                nm=str(Path(__file__)), jlink_dir="C:/JLink", timeout=1,
                server_ready_timeout=0.01, server_exit_timeout=0.01, inter_session_delay=0,
            )
            calls: list[int] = []

            def failed_session(**kwargs: object) -> dict[str, object]:
                calls.append(1)
                Path(str(kwargs["gdb_log"])).write_text("", encoding="ascii")
                Path(str(kwargs["server_log"])).write_text("", encoding="ascii")
                return {
                    "server_started": True,
                    "server_pid": 601,
                    "server_ready": False,
                    "rtt_connected": False,
                    "gdb_started": False,
                    "gdb_exit_code": None,
                    "server_process_exited": True,
                    "server_natural_exit": True,
                    "server_terminate_sent": False,
                    "server_kill_sent": False,
                    "capture_stopped": True,
                    "ports_closed": True,
                    "session_error": "readiness timeout",
                    "transport_classification": "TRANSPORT_NOT_READY",
                }

            with (
                mock.patch.object(driver, "require_frozen_build", return_value=(elf, map_path)),
                mock.patch.object(driver, "load_frozen_device_header", return_value=(bytes(range(96)), layout_values())),
                mock.patch.object(driver, "read_symbol_table", return_value={name: [value] for name, value in selected_symbols().items()}),
                mock.patch.object(driver, "run_gdb_session", side_effect=failed_session),
            ):
                with self.assertRaises(QUALIFIER.QualificationError):
                    QUALIFIER.run_qualification(args)
            self.assertEqual(calls, [1])


if __name__ == "__main__":
    unittest.main(verbosity=2)
