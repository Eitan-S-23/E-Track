"""Source-bound LVGL rendering and DMA protocol self-tests, not device evidence."""

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

try:
    from PIL import Image
except ImportError:
    Image = None

from test_main_menu_encoder import method

ROOT = Path(__file__).resolve().parents[2]
CASES = ("layout", "long_values", "arrow", "controls", "spectrum",
         "foreground", "transitions", "lifecycle", "dma")
VARIANTS = ("desktop", "hardware", "fallback")


def checked(path):
    path = path.absolute()
    path.relative_to(ROOT)
    for parent in (path, *path.parents):
        if parent.exists() and (parent.is_symlink() or
                getattr(parent.lstat(), "st_file_attributes", 0) & 0x400):
            raise RuntimeError("Redirected Dialplate test output: " + str(parent))
    path.resolve(strict=False).relative_to(ROOT.resolve(strict=True))
    return path


HAL_STUB = """#ifndef DIALPLATE_TEST_HAL_H
#define DIALPLATE_TEST_HAL_H
#include "lvgl/lvgl.h"
#include <stdint.h>
#define CONFIG_SCREEN_HOR_RES 240
#define CONFIG_SCREEN_VER_RES 320
#define CONFIG_SCREEN_CS_PIN 1
#define CONFIG_SCREEN_DC_PIN 2
#define DMA1_FDT3_FLAG 1
#define RESET 0
void mock_wait_for_interrupt();
#define __wfi() mock_wait_for_interrupt()
namespace HAL {
typedef void (*Display_CallbackFunc_t)();
void Display_SetAddrWindow(int16_t, int16_t, int16_t, int16_t);
void Display_SendPixels(const uint16_t*, uint32_t);
void Display_WaitForSendFinish();
void Display_SendPixelsBlocking(const uint16_t*, uint32_t);
void Display_SetSendFinishCallback(Display_CallbackFunc_t);
}
#endif
"""


class DialplateUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        for tool in ("cmake", "ninja", "gcc", "g++"):
            if shutil.which(tool) is None:
                raise RuntimeError("Required host tool: " + tool)
        cache = checked(ROOT / ".cache/dialplate-ui-tests")
        cache.mkdir(parents=True, exist_ok=True)
        cls.directory = checked(Path(tempfile.mkdtemp(prefix="run-", dir=cache)))
        cls.build = checked(cache / "build")
        cls.env = dict(os.environ, TEMP=str(cls.directory), TMP=str(cls.directory),
                       TMPDIR=str(cls.directory), PYTHONDONTWRITEBYTECODE="1")
        stub = checked(cls.directory / "HAL")
        stub.mkdir()
        checked(stub / "HAL.h").write_text(HAL_STUB, encoding="utf-8")
        hal_path = ROOT / "MDK-ARM_F435/Platform/HAL/HAL_Display.cpp"
        source = hal_path.read_text(encoding="utf-8")
        signatures = ("void DMA1_Channel3_IRQHandler", "void HAL::Display_SendPixels",
                      "void HAL::Display_WaitForSendFinish", "void HAL::Display_SendPixelsBlocking",
                      "void HAL::Display_SetSendFinishCallback")
        checked(cls.directory / "hal_display_methods.inc").write_text(
            "\n\n".join(method(source, signature) for signature in signatures), encoding="utf-8")
        inputs = (
            "USER/App/Pages/Dialplate/DialplateView.cpp",
            "USER/App/Pages/Dialplate/DialplateView.h",
            "USER/App/Pages/Dialplate/DialplateGlowData.inc",
            "USER/App/Resource/Image/img_src_dialplate_skin.c",
            "USER/lv_port/lv_port.h", "USER/App/Common/HAL/HAL.h",
            "MDK-ARM_F435/Platform/HAL/HAL_Display.cpp",
            "MDK-ARM_F435/Platform/lv_port/lv_port_disp.cpp",
            "tests/ota/dialplate_ui_harness.cpp", "tests/ota/lvgl_companion/CMakeLists.txt")
        hashes = {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in inputs}
        checked(cls.directory / "source-sha256.json").write_text(
            json.dumps(hashes, indent=2) + "\n", encoding="utf-8")
        commands = [
            ["cmake", "-S", str(ROOT / "tests/ota/lvgl_companion"), "-B", str(cls.build),
             "-G", "Ninja", "-DCMAKE_BUILD_TYPE=Debug", "-DDIALPLATE_ONLY=ON",
             "-DCMAKE_C_COMPILER=" + shutil.which("gcc"),
             "-DCMAKE_CXX_COMPILER=" + shutil.which("g++"), "-DHARNESS_DIR=" + str(cls.directory)],
            ["cmake", "--build", str(cls.build), "--target",
             *("dialplate_" + name for name in VARIANTS), "--parallel", "8"]]
        for index, command in enumerate(commands):
            result = subprocess.run(command, cwd=ROOT, env=cls.env, capture_output=True,
                                    text=True, timeout=300)
            checked(cls.directory / ("build-%d.log" % index)).write_text(
                result.stdout + result.stderr, encoding="utf-8")
            if result.returncode:
                raise RuntimeError(result.stdout[-12000:] + result.stderr[-3000:])
        print("Retained real-LVGL renders and source bindings: " + str(cls.directory))

    def run_case(self, variant, case):
        extension = ".exe" if os.name == "nt" else ""
        result = subprocess.run([str(self.build / ("dialplate_" + variant + extension)),
                                 case, str(self.directory)], cwd=ROOT, env=self.env,
                                capture_output=True, text=True, timeout=30)
        checked(self.directory / (variant + "-" + case + ".log")).write_text(
            result.stdout + result.stderr, encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        names = [variant + "-" + case]
        if case == "foreground":
            names.append(variant + "-foreground-modal")
        for name in names:
            image_path = checked(self.directory / (name + ".ppm"))
            data = image_path.read_bytes()
            header = b"P6\n240 320\n255\n"
            self.assertTrue(data.startswith(header))
            self.assertEqual(len(data), len(header) + 240 * 320 * 3)
            if Image is not None:
                with Image.open(image_path) as image:
                    image.save(checked(self.directory / (name + ".png")))
        print(result.stdout.strip())

    def test_preserves_current_ota_and_recording_contracts(self):
        menu = (ROOT / "USER/App/Pages/Menu/MainMenu.cpp").read_text(encoding="utf-8")
        model = (ROOT / "USER/App/Pages/Dialplate/DialplateModel.cpp").read_text(encoding="utf-8")
        presenter = (ROOT / "USER/App/Pages/Dialplate/Dialplate.cpp").read_text(encoding="utf-8")
        self.assertIn("MENU_ACTION_UPDATE", menu)
        self.assertIn("FirmwareCompanion_Show();", menu)
        self.assertIn('_Manager->Push("Pages/FirmwareUpdate")', menu)
        self.assertIn("bool DialplateModel::RecorderCommand", model)
        recording = method(presenter, "void Dialplate::onRecord")
        self.assertIn("if (!Model.RecorderCommand(Model.REC_START))", recording)
        self.assertIn("if (!Model.RecorderCommand(Model.REC_CONTINUE))", recording)
        for index in range(4):
            self.assertIn("View.SetMetricText(%d," % index, presenter)

    def test_snapshot_width_matches_its_actual_descriptor(self):
        model = (ROOT / "USER/App/Pages/LiveMap/LiveMap.cpp").read_text(encoding="utf-8")
        view = (ROOT / "USER/App/Pages/LiveMap/LiveMapView.cpp").read_text(encoding="utf-8")
        width = int(re.search(r"#define SNAPSHOT_W (\d+)", model)[1])
        self.assertIn("snapshotDsc.header.w = SNAPSHOT_W;", model)
        self.assertIn("lv_obj_set_size(imgSnap, %d," % width, view)

    def test_sparse_glow_data_is_bounded(self):
        text = (ROOT / "USER/App/Pages/Dialplate/DialplateGlowData.inc").read_text(encoding="utf-8")
        count = int(re.search(r"#define DIALPLATE_GLOW_FRAME_COUNT (\d+)", text)[1])
        maximum = int(re.search(r"#define DIALPLATE_GLOW_BLIT_MAX_PIXELS (\d+)", text)[1])
        pixels = re.findall(r"kDialplateGlowPixels(\d+)\[\] = \{(.*?)\};", text, re.S)
        segments = re.findall(r"kDialplateGlowSegments(\d+)\[\] = \{(.*?)\};", text, re.S)
        self.assertEqual(len(pixels), count)
        self.assertEqual(len(segments), count)
        for _, block in pixels:
            for index, r, g, b in re.findall(r"\{\s*(\d+),\s*(\d+),\s*(\d+),\s*(\d+)\s*\}", block):
                self.assertLess(int(index), 240 * 320)
                for channel in (r, g, b):
                    self.assertLessEqual(int(channel), 255)
        for _, block in segments:
            areas = re.findall(r"\{\s*\{\s*(-?\d+),\s*(-?\d+),\s*(-?\d+),\s*(-?\d+)\s*\}\s*\}", block)
            self.assertTrue(areas)
            for area in areas:
                x1, y1, x2, y2 = map(int, area)
                self.assertTrue(0 <= x1 <= x2 < 240 and 0 <= y1 <= y2 < 320)
                self.assertLessEqual((x2 - x1 + 1) * (y2 - y1 + 1), maximum)


def case_test(variant, case):
    def run(self):
        if case == "dma" and variant != "hardware":
            self.skipTest("DMA implementation is F435-only; fallback has no direct transfers")
        self.run_case(variant, case)
    return run


for variant in VARIANTS:
    for case in CASES:
        setattr(DialplateUiTests, "test_%s_%s" % (variant, case), case_test(variant, case))

if __name__ == "__main__":
    unittest.main(verbosity=2)
