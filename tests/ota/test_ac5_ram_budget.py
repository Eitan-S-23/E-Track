#!/usr/bin/env python3
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
LV_CONF = ROOT / "Simulator" / "LVGL.Simulator" / "lv_conf.h"
DECODER = ROOT / "Simulator" / "LVGL.Simulator" / "lvgl" / "src" / "draw" / "lv_img_decoder.c"
LIVE_MAP = ROOT / "USER" / "App" / "Pages" / "LiveMap" / "LiveMap.cpp"


class Ac5RamBudgetTests(unittest.TestCase):
    def test_embedded_lvgl_pool_remains_128_kib(self):
        text = LV_CONF.read_text(encoding="utf-8")
        self.assertRegex(text, r"#define\s+LV_MEM_SIZE\s+\(128U\s*\*\s*1024U\)")

    def test_only_ac5_moves_line_cache_to_lvgl_pool(self):
        text = DECODER.read_text(encoding="utf-8")
        self.assertIn("#if defined(__CC_ARM)", text)
        self.assertIn("#define XTRACK_IMG_LINE_CACHE_DYNAMIC 1", text)
        self.assertIn("#define XTRACK_IMG_LINE_CACHE_DYNAMIC 0", text)
        self.assertIn("static xtrack_img_line_cache_entry_t * xtrack_img_line_cache;", text)
        self.assertRegex(
            text,
            re.compile(
                r"static\s+xtrack_img_line_cache_entry_t\s+"
                r"xtrack_img_line_cache\s*\[XTRACK_IMG_LINE_CACHE_CNT\]"
            ),
        )
        self.assertIn("xtrack_img_line_cache = lv_mem_alloc(cache_size);", text)
        self.assertIn("if(xtrack_img_line_cache_alloc_warned != 0)", text)
        self.assertIn("#if XTRACK_IMG_LINE_CACHE_DYNAMIC", text)

    def test_live_map_releases_dynamic_line_cache_only_for_ac5(self):
        text = LIVE_MAP.read_text(encoding="utf-8")
        self.assertRegex(
            text,
            re.compile(
                r"#if defined\(__CC_ARM\)\s+"
                r'extern "C" void xtrack_img_line_cache_release\(void\);\s+'
                r"#endif"
            ),
        )
        self.assertRegex(
            text,
            re.compile(
                r"#if defined\(__CC_ARM\)\s+"
                r"xtrack_img_line_cache_release\(\);\s+"
                r"#endif"
            ),
        )


if __name__ == "__main__":
    unittest.main()
