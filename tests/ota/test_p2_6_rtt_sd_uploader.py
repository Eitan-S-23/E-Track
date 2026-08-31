#!/usr/bin/env python3
"""Offline checks for the persistent P2-6 RTT/GDB SD uploader."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import re
import tempfile
import unittest


MODULE_PATH = Path(__file__).with_name("p2_6_rtt_sd_uploader.py")
SPEC = importlib.util.spec_from_file_location("p2_6_rtt_sd_uploader", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
UPLOADER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(UPLOADER)


def layout_values() -> dict[str, int]:
    return {
        "OTA_APP_ORIGIN": 0x08010000,
        "OTA_FW_HEADER_OFFSET": 0x400,
        "OTA_FW_HEADER_SIZE": 96,
        "OTA_OVERLAY_ORIGIN": 0x20058000,
        "OTA_OVERLAY_WORKSPACE_LENGTH": 0xA000,
    }


def selected_symbols() -> dict[str, int]:
    return {
        UPLOADER.driver.GET_BCB_SYMBOL: 0x08040CCC,
        UPLOADER.driver.HAL_UPDATE_SYMBOL: 0x08040884,
        UPLOADER.driver.SD_READY_SYMBOL: 0x20053214,
        UPLOADER.driver.RTT_SYMBOL: 0x20053E1C,
        UPLOADER.driver.OVERLAY_OWNER_SYMBOL: 0x20053FA0,
        UPLOADER.driver.OVERLAY_WORKSPACE_SYMBOL: 0x20058000,
        UPLOADER.LV_FS_OPEN_SYMBOL: 0x0802B040,
        UPLOADER.LV_FS_CLOSE_SYMBOL: 0x0802AD10,
        UPLOADER.LV_FS_READ_SYMBOL: 0x0802AD4E,
        UPLOADER.LV_FS_WRITE_SYMBOL: 0x0802AEC4,
        UPLOADER.LV_FS_SEEK_SYMBOL: 0x0802AEFA,
        UPLOADER.LV_FS_TELL_SYMBOL: 0x0802AF80,
    }


def make_mi_log(
    chunk_sizes: list[int],
    *,
    order: list[int] | None = None,
    omit_event: tuple[int, str] | None = None,
    wrong_size_at: int | None = None,
) -> tuple[bytes, bytes]:
    specs = UPLOADER.expected_mi_read_blocks(0x20058000, chunk_sizes)
    indexes = order if order is not None else list(range(len(specs)))
    lines: list[str] = []
    expected_parts: list[bytes] = []
    for emitted_index in indexes:
        spec = specs[emitted_index]
        data = bytes([(spec["chunk"] * 17 + spec["block"]) & 0xFF]) * spec["size"]
        expected_parts.append(data)
        if omit_event != (emitted_index, "begin"):
            lines.append(
                "P2_6_MI_READ_BEGIN "
                f"chunk={spec['chunk']} block={spec['block']} "
                f"address=0x{spec['address']:08x} size={spec['size']}"
            )
        response_data = data[:-1] if wrong_size_at == emitted_index else data
        if omit_event != (emitted_index, "response"):
            lines.append(
                '^done,memory=[{begin="0x%08x",offset="0x0",end="0x%08x",contents="%s"}]'
                % (
                    spec["address"],
                    spec["address"] + spec["size"],
                    response_data.hex(),
                )
            )
        if omit_event != (emitted_index, "end"):
            lines.append(
                f"P2_6_MI_READ_END chunk={spec['chunk']} block={spec['block']}"
            )
    return ("\n".join(lines) + "\n").encode("ascii"), b"".join(expected_parts)


class P26RttSdUploaderTest(unittest.TestCase):
    def test_validate_mcu_path(self) -> None:
        self.assertEqual(
            UPLOADER.validate_mcu_path("/P2-6-RUN/P2-6A-FULL.etu"),
            b"/P2-6-RUN/P2-6A-FULL.etu\0",
        )
        with self.assertRaises(UPLOADER.UploadError):
            UPLOADER.validate_mcu_path("relative.etu")
        with self.assertRaises(UPLOADER.UploadError):
            UPLOADER.validate_mcu_path('/bad"name.etu')

    def test_split_chunks_preserves_bytes(self) -> None:
        UPLOADER.driver.DEFAULT_TMP_DIR.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=UPLOADER.driver.DEFAULT_TMP_DIR) as temp:
            base = Path(temp)
            source = base / "input.bin"
            data = bytes(range(256)) * 300
            source.write_bytes(data)
            chunks = UPLOADER.split_chunks(source, base / "chunks")
            self.assertEqual(b"".join(path.read_bytes() for path in chunks), data)
            self.assertGreater(len(chunks), 1)
            self.assertTrue(
                all(path.stat().st_size <= UPLOADER.UPLOAD_CHUNK_SIZE for path in chunks)
            )

    def test_mi_chunked_write_and_multiblock_readback(self) -> None:
        data = bytes(range(256)) * 9
        write_lines = UPLOADER.mi_write_memory_lines(0x20058000, data)
        self.assertGreater(len(write_lines), 1)
        self.assertTrue(all("-data-write-memory-bytes" in line for line in write_lines))
        read_lines = UPLOADER.mi_read_memory_lines(0x20058000, len(data), 0)
        self.assertGreater(len(read_lines), 3)
        self.assertTrue(any("P2_6_MI_READ_BEGIN" in line for line in read_lines))
        raw, expected = make_mi_log([1300, 7])
        parsed, blocks = UPLOADER.parse_mi_readback(raw, [1300, 7], 0x20058000)
        self.assertEqual(parsed, expected)
        self.assertEqual(len(blocks), 3)
        self.assertEqual([item["chunk"] for item in blocks], [0, 0, 1])

    def test_mi_readback_rejects_missing_duplicate_and_out_of_order_blocks(self) -> None:
        raw, _ = make_mi_log([1300], omit_event=(1, "end"))
        with self.assertRaisesRegex(UPLOADER.UploadError, "event count mismatch"):
            UPLOADER.parse_mi_readback(raw, [1300], 0x20058000)

        complete, _ = make_mi_log([5])
        with self.assertRaisesRegex(UPLOADER.UploadError, "event count mismatch"):
            UPLOADER.parse_mi_readback(complete + complete, [5], 0x20058000)

        out_of_order, _ = make_mi_log([1300], order=[1, 0])
        with self.assertRaisesRegex(UPLOADER.UploadError, "begin mismatch"):
            UPLOADER.parse_mi_readback(out_of_order, [1300], 0x20058000)

    def test_mi_readback_rejects_error_and_wrong_length(self) -> None:
        raw, _ = make_mi_log([5])
        with self.assertRaisesRegex(UPLOADER.UploadError, "MI command error"):
            UPLOADER.parse_mi_readback(
                b'^error,msg="target running"\n' + raw, [5], 0x20058000
            )
        wrong, _ = make_mi_log([5], wrong_size_at=0)
        with self.assertRaisesRegex(UPLOADER.UploadError, "range mismatch"):
            UPLOADER.parse_mi_readback(wrong, [5], 0x20058000)

    def test_gdb_script_has_no_restore_or_page_dependency(self) -> None:
        UPLOADER.driver.DEFAULT_TMP_DIR.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=UPLOADER.driver.DEFAULT_TMP_DIR) as temp:
            base = Path(temp)
            chunk = base / "source-000.bin"
            path_blob = base / "mcu-path.bin"
            script = base / "upload.gdb"
            chunk.write_bytes(b"test-data")
            path_blob.write_bytes(b"/P2-6-RUN/test.etu\0")
            UPLOADER.upload_gdb_command_file(
                script,
                UPLOADER.driver.ROOT / "firmware.elf",
                selected_symbols(),
                bytes(range(96)),
                layout_values(),
                [chunk],
                path_blob,
                chunk.stat().st_size,
            )
            text = script.read_text(encoding="ascii")
        source_text = MODULE_PATH.read_text(encoding="utf-8")
        self.assertIn("target_exists", text)
        self.assertIn("P2_6_STATE PASS label=before_upload", text)
        self.assertIn("P2_6_STATE PASS label=after_upload", text)
        self.assertIn("-data-write-memory-bytes", text)
        self.assertIn("-data-read-memory-bytes", text)
        self.assertIn("P2_6_MI_READ_BEGIN", text)
        self.assertIn("P2_6_SD_UPLOAD PASS", text)
        for forbidden in (
            "continue &",
            "interrupt",
            "restore ",
            "dump binary memory",
            "App_Init()::manager",
            "_PageCurrent",
            "Dialplate",
            "no_current_page",
        ):
            self.assertNotIn(forbidden, text)
            self.assertNotIn(forbidden, source_text)

    def test_uploader_required_symbols_exclude_page_objects(self) -> None:
        names = set(selected_symbols())
        self.assertNotIn("App_Init()::manager", names)
        self.assertNotIn("vtable for Page::Dialplate", names)
        self.assertNotIn("vtable for Page::FirmwareUpdate", names)
        self.assertIn(UPLOADER.driver.OVERLAY_OWNER_SYMBOL, names)
        self.assertIn(UPLOADER.LV_FS_WRITE_SYMBOL, names)

    def test_bcb_precondition_allows_staged_confirmed_idle(self) -> None:
        """钉死 R6 裁定 §3（P2-6-BR-20260830-SD-R6-01）：不得把 STAGED 判为失败。

        R5 FULL 上传 1/1 的 HARNESS_FAIL 根因是 uploader 把 BCB == CONFIRMED
        当作上传硬前置；PATCH OTA 之后板卡按契约处于 STAGED。本负例断言：
        IDLE/STAGED/CONFIRMED 均不触发 quit，而 APPLYING/TEST_BOOT/ROLLBACK
        仍按原 quit_code fail-closed。
        """
        header = bytes(range(96))
        symbols = selected_symbols()
        layout = layout_values()
        allowed = (
            UPLOADER.UPLOAD_BCB_STATE_IDLE,
            UPLOADER.driver.BCB_STATE_STAGED,
            UPLOADER.driver.BCB_STATE_CONFIRMED,
        )
        # 2=APPLYING 3=TEST_BOOT 5=ROLLBACK（Libraries/EEPROM/eeprom_bcb.h）
        forbidden = (2, 3, 5)
        for label, quit_code in (("before_upload", 41), ("after_upload", 63)):
            lines = UPLOADER.upload_runtime_state_lines(
                symbols, header, layout, label, quit_code
            )
            text = "\n".join(lines)
            conditions = [
                line for line in lines if line.startswith(f"if $bcb_{label} != ")
            ]
            self.assertEqual(
                len(conditions), 1, f"expected one BCB condition for {label}"
            )
            condition = conditions[0]
            for state in allowed:
                self.assertFalse(
                    self._condition_triggers_quit(condition, label, state),
                    f"BCB state {state} must not fail {label}",
                )
            for state in forbidden:
                self.assertTrue(
                    self._condition_triggers_quit(condition, label, state),
                    f"BCB state {state} must stay fail-closed at {label}",
                )
            self.assertIn(f"quit {quit_code}", text)
            allowed_text = ",".join(
                str(state) for state in UPLOADER.UPLOAD_ALLOWED_BCB_STATES
            )
            self.assertIn(
                f'printf "P2_6_STATE ERROR label={label} bcb=%u '
                f'allowed={allowed_text}',
                text,
            )

    @staticmethod
    def _condition_triggers_quit(condition: str, label: str, state: int) -> bool:
        expression = (
            condition[len("if "):]
            .replace(f"$bcb_{label}", str(state))
            .replace("&&", "and")
        )
        return bool(eval(expression, {"__builtins__": {}}, {}))

    def test_upload_allowed_bcb_states_match_eeprom_bcb_header(self) -> None:
        """上传前置允许集合必须与生产 BCB 状态枚举逐一对账，防止魔数漂移。"""
        header_path = (
            UPLOADER.driver.ROOT / "Libraries" / "EEPROM" / "eeprom_bcb.h"
        )
        text = header_path.read_text(encoding="utf-8", errors="replace")
        values = {
            name: int(value)
            for name, value in re.findall(
                r"(BCB_STATE_[A-Z_]+)\s*=\s*(\d+)", text
            )
        }
        self.assertEqual(
            values["BCB_STATE_IDLE"], UPLOADER.UPLOAD_BCB_STATE_IDLE
        )
        self.assertEqual(
            values["BCB_STATE_STAGED"], UPLOADER.driver.BCB_STATE_STAGED
        )
        self.assertEqual(
            values["BCB_STATE_CONFIRMED"], UPLOADER.driver.BCB_STATE_CONFIRMED
        )
        self.assertEqual(
            set(UPLOADER.UPLOAD_ALLOWED_BCB_STATES), {0, 1, 4}
        )

    def test_gdb_script_uses_bcb_state_set_not_single_value(self) -> None:
        """生成的 GDB 脚本两处 BCB 检查都必须是集合判定，不得回退为单值比较。"""
        UPLOADER.driver.DEFAULT_TMP_DIR.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=UPLOADER.driver.DEFAULT_TMP_DIR) as temp:
            base = Path(temp)
            chunk = base / "source-000.bin"
            path_blob = base / "mcu-path.bin"
            script = base / "upload.gdb"
            chunk.write_bytes(b"test-data")
            path_blob.write_bytes(b"/P2-6-RUN/test.etu\0")
            UPLOADER.upload_gdb_command_file(
                script,
                UPLOADER.driver.ROOT / "firmware.elf",
                selected_symbols(),
                bytes(range(96)),
                layout_values(),
                [chunk],
                path_blob,
                chunk.stat().st_size,
            )
            text = script.read_text(encoding="ascii")
        lines = text.splitlines()
        for label in ("before_upload", "after_upload"):
            conditions = [
                line for line in lines if line.startswith(f"if $bcb_{label} != ")
            ]
            self.assertEqual(len(conditions), 1, f"label={label}")
            for state in UPLOADER.UPLOAD_ALLOWED_BCB_STATES:
                self.assertIn(
                    f"$bcb_{label} != {state}", conditions[0], f"label={label}"
                )
            for line in lines:
                self.assertNotRegex(
                    line, rf"^if \$bcb_{label} != \d+$", f"label={label}"
                )
        self.assertIn("quit 41", text)
        self.assertIn("quit 63", text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
