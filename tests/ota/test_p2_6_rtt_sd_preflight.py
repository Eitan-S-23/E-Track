#!/usr/bin/env python3
"""Offline checks for the no-media-write P2-6 SD-R2 preflight."""

from __future__ import annotations

import ast
import importlib.util
from pathlib import Path
import tempfile
import unittest


MODULE_PATH = Path(__file__).with_name("p2_6_rtt_sd_preflight.py")
SPEC = importlib.util.spec_from_file_location("p2_6_rtt_sd_preflight", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
PREFLIGHT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PREFLIGHT)


def selected_symbols() -> dict[str, int]:
    driver = PREFLIGHT.driver
    return {
        driver.GET_BCB_SYMBOL: 0x08040CCC,
        driver.HAL_UPDATE_SYMBOL: 0x08040884,
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


class P26RttSdPreflightTest(unittest.TestCase):
    def test_generated_preflight_is_read_only_and_page_independent(self) -> None:
        PREFLIGHT.driver.DEFAULT_TMP_DIR.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=PREFLIGHT.driver.DEFAULT_TMP_DIR) as temp:
            script = Path(temp) / "preflight.gdb"
            PREFLIGHT.preflight_gdb_command_file(
                script,
                PREFLIGHT.driver.ROOT / "firmware.elf",
                selected_symbols(),
                bytes(range(96)),
                layout_values(),
            )
            text = script.read_text(encoding="ascii")
        self.assertIn("monitor halt", text)
        self.assertIn("stop_verified label=preflight_hal_update", text)
        self.assertIn("P2_6_IDENTITY PASS label=preflight_fw", text)
        self.assertIn("P2_6_STATE PASS label=preflight", text)
        self.assertIn("P2_6_SD_PREFLIGHT PASS write_calls=0 flash_calls=0", text)
        self.assertIn("0xe000ed08", text)
        self.assertIn("0xe000ed28", text)
        for forbidden in (
            "lv_fs_open",
            "lv_fs_write",
            "lv_fs_close",
            "restore ",
            "dump binary memory",
            "continue &",
            "interrupt",
            "App_Init()::manager",
            "_PageCurrent",
            "Dialplate",
            "loadfile",
        ):
            self.assertNotIn(forbidden, text)

    def test_preflight_required_symbols_are_unique_in_frozen_elf(self) -> None:
        driver = PREFLIGHT.driver
        nm = Path(driver.shutil.which("arm-none-eabi-nm") or "")
        self.assertTrue(nm.is_file())
        elf, _ = driver.require_frozen_build(driver.DEFAULT_BUILD)
        table = driver.read_symbol_table(nm, elf)
        required = list(selected_symbols())
        selected = driver.require_symbols(table, required)
        self.assertEqual(set(selected), set(required))
        self.assertEqual(selected[driver.HAL_UPDATE_SYMBOL], 0x08040884)
        self.assertEqual(selected[driver.OVERLAY_WORKSPACE_SYMBOL], 0x20058000)

    def test_preflight_source_has_no_file_api_or_page_gate(self) -> None:
        text = MODULE_PATH.read_text(encoding="utf-8")
        tree = ast.parse(text)
        names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
        driver_attributes = {
            node.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id == "driver"
        }
        for forbidden_name in (
            "LV_FS_OPEN_SYMBOL",
            "LV_FS_WRITE_SYMBOL",
            "LV_FS_CLOSE_SYMBOL",
        ):
            self.assertNotIn(forbidden_name, names)
        for forbidden_attribute in (
            "MANAGER_SYMBOL",
            "PAGE_VTABLE_SYMBOL",
            "PUSH_SYMBOL",
        ):
            self.assertNotIn(forbidden_attribute, driver_attributes)


if __name__ == "__main__":
    unittest.main(verbosity=2)
