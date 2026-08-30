#!/usr/bin/env python3
"""Offline checks for the persistent P2-6 RTT/GDB SD uploader."""

from __future__ import annotations

import importlib.util
from pathlib import Path
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


if __name__ == "__main__":
    unittest.main(verbosity=2)
