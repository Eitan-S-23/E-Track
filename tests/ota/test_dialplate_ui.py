"""Source-bound LVGL rendering and DMA protocol self-tests, not device evidence."""

import hashlib
import json
import math
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
ORIGINAL_LOCATOR_PNG = ROOT / "UI" / "\u4eea\u8868\u76d8.png"
ORIGINAL_LOCATOR_PNG_SHA256 = "aa8b11e3ce3799a1e08ceb5e63356c1c3dd276d2d364e1d1ace61645f6b0e750"
LOCATOR_CX, LOCATOR_CY, LOCATOR_RADIUS = 119, 232, 28
SKIN_OUTSIDE_LOCATOR_SHA256 = "d50f729a1a3ccbb96391d36c978f083ec713fa82741df69f3ece76cf23ad58ec"
SKIN_ORIGINAL_LOCATOR_SHA256 = "1890a0bac2e0c6c42c8ad9fdba8277975583c256ad27ed6110b99dd943fb8d94"
TIMER_FRAME_CASES = ("timer_frames", "statusbar_frames", "transparent_top_frames")
CASES = ("layout", "long_values", "populated", "arrow", "controls", "spectrum", "spectrum_frames",
         *TIMER_FRAME_CASES, "popup_occlusion", "lifecycle", "dma")
VARIANTS = ("desktop", "hardware")
UI_METHODS = ("void SetAdaptiveMetricLabel", "void SetSpeedLabel", "void SetCalorieLabel",
              "void SetMaxSpeedLabel", "void SetNavDistanceLabel")
REFERENCE_RENDER_CASES = ("layout", "long_values", "populated", "arrow", "controls", "spectrum",
                          "spectrum_frames", *TIMER_FRAME_CASES)
REFERENCE_UI_HASHES = {
    "view": "6a12d37b9fd0c81881fca9a14ca9be8341d134b3bee8a73dbb67ff853d4f7398",
    "header": "17728fe5c4ae7ea0844757d034b787a1200f780787df4e24e5a50456afacb86b",
    "void SetAdaptiveMetricLabel": "0f0c0c891e55cf3729953c352ab6ec2067e51e22a116fa19d9ec827abf88c750",
    "void SetSpeedLabel": "371170125168a27abcd006a5f54c9f52c1c0970e9e543a0ba6dce58960ab4ae8",
    "void SetCalorieLabel": "3890825b2412d14c11c368c8942138321233f75b075c9791ecd4088f53672531",
    "void SetMaxSpeedLabel": "25760f09ffea625f15cbb52f36ab5950d033e98f8aaabbabd6bb896a09532fa2",
    "void SetNavDistanceLabel": "f728c8bc5dc9ca2379e02806321cd7c1e45054db6f52ec08c70784737a2e9ecc",
    "void Dialplate::Update": "a75bce331c91d046932295a3e9ddc3002dc734c5723ec64a8c91461fa0ee006e",
}
ORIGINAL_ARROW_LAYER = """    const void* arrowSrc = IMG("gps_arrow_light");
    if(arrowSrc != nullptr)
    {
        lv_obj_t* arrow = lv_img_create(root);
        if(arrow != nullptr)
        {
            lv_img_set_src(arrow, arrowSrc);
            lv_obj_set_pos(arrow, ARROW_CENTER_X - ARROW_PIVOT_X,
                           ARROW_CENTER_Y - ARROW_PIVOT_Y);
            lv_img_set_pivot(arrow, ARROW_PIVOT_X, ARROW_PIVOT_Y);
            lv_img_set_angle(arrow, 0);
            lv_obj_clear_flag(arrow, LV_OBJ_FLAG_CLICKABLE);
            lv_obj_clear_flag(arrow, LV_OBJ_FLAG_SCROLLABLE);
            ui.arrow.img = arrow;
            ui.arrow.angle = 0;
        }
    }

"""
SPECTRUM_OCCLUSION_HELPER = """static bool DialplatePopup_CoversSpectrum()
{
    /* A popup owns these pixels even though the HUD effects bypass LVGL. */
    const lv_area_t spectrumArea =
    {
        SPECTRUM_X,
        SPECTRUM_Y,
        SPECTRUM_X + SPECTRUM_W - 1,
        SPECTRUM_Y + SPECTRUM_H - 1
    };
    lv_obj_t* topLayer = lv_layer_top();
    for(uint32_t i = 0; i < lv_obj_get_child_cnt(topLayer); i++)
    {
        lv_obj_t* overlay = lv_obj_get_child(topLayer, i);
        if(lv_obj_get_style_opa(overlay, 0) == LV_OPA_TRANSP ||
           lv_obj_get_style_bg_opa(overlay, 0) == LV_OPA_TRANSP)
        {
            continue;
        }
        lv_area_t visibleArea = spectrumArea;
        if(lv_obj_area_is_visible(overlay, &visibleArea))
        {
            return true;
        }
    }
    return false;
}
"""
SPECTRUM_OCCLUSION_CONDITIONS = (
    "frame == nullptr",
    "ui.skin == nullptr",
    "instance == nullptr || area == nullptr || color_p == nullptr",
)


def checked(path):
    path = path.absolute()
    path.relative_to(ROOT)
    for parent in (path, *path.parents):
        if parent.exists() and (parent.is_symlink() or
                getattr(parent.lstat(), "st_file_attributes", 0) & 0x400):
            raise RuntimeError("Redirected Dialplate test output: " + str(parent))
    path.resolve(strict=False).relative_to(ROOT.resolve(strict=True))
    return path


def source_digest(text):
    canonical = re.sub(r"[ \t]+$", "", text, flags=re.M).strip() + "\n"
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def locator_pixels(data, channels, outside=False):
    chunks = []
    for y in range(320):
        start, end = y * 240 * channels, (y + 1) * 240 * channels
        distance = abs(y - LOCATOR_CY)
        if distance > LOCATOR_RADIUS:
            if outside:
                chunks.append(data[start:end])
            continue
        half_width = math.isqrt(LOCATOR_RADIUS ** 2 - distance ** 2)
        left = start + (LOCATOR_CX - half_width) * channels
        right = start + (LOCATOR_CX + half_width + 1) * channels
        chunks.extend((data[start:left], data[right:end]) if outside else (data[left:right],))
    return b"".join(chunks)


def skin_rgb565(source_root=ROOT):
    text = (source_root / "USER/App/Resource/Image/img_src_dialplate_skin.c").read_text(encoding="utf-8")
    match = re.search(r"#if LV_COLOR_DEPTH == 16 && LV_COLOR_16_SWAP != 0\n(.*?)\n#else\n(.*?)\n#endif", text, re.S)
    if match is None:
        raise AssertionError("Missing the two original skin byte orders")
    swapped, little = [bytes(int(value, 16) for value in re.findall(r"0x([0-9a-fA-F]{2})", block))
                       for block in match.groups()]
    if len(little) != 240 * 320 * 2 or swapped[::2] != little[1::2] or swapped[1::2] != little[::2]:
        raise AssertionError("Inconsistent skin RGB565 byte orders")
    return little


def write_ui_helpers(source_root, directory):
    presenter = (source_root / "USER/App/Pages/Dialplate/Dialplate.cpp").read_text(encoding="utf-8")
    maximum = re.search(r"^#define MAX_SPEED_TEXT_W[^\n]+", presenter, re.M)[0]
    checked(directory / "dialplate_presenter_ui.inc").write_text(
        maximum + "\n\n" + "\n\n".join(method(presenter, name) for name in UI_METHODS),
        encoding="utf-8")
    statusbar = (source_root / "USER/App/Pages/StatusBar/StatusBar.cpp").read_text(encoding="utf-8")
    checked(directory / "statusbar_ui.inc").write_text(
        "\n\n".join(method(statusbar, name) for name in
                     ("static void StatusBar_StyleInit", "static void StatusBar_Appear")),
        encoding="utf-8")
    firmware = (ROOT / "USER/App/Pages/FirmwareUpdate/FirmwareUpdate.cpp").read_text(encoding="utf-8")
    popup = method(firmware[firmware.index("\nvoid CompanionOpen(void*)\n{"):], "void CompanionOpen")
    checked(directory / "companion_popup_ui.inc").write_text(
        popup[popup.index("    companionModal = lv_obj_create(lv_layer_top());"):
              popup.index("    companionEmblem = lv_obj_create(panel);")], encoding="utf-8")


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
        checked(cls.directory / "reference_page_dependencies.h").write_text(
            '#define __PAGE_H\n#include "lvgl/lvgl.h"\n'
            '#include "Resource/ResourcePool.h"\n', encoding="utf-8")
        cmake = (ROOT / "MDK-ARM_F435/cmake-generated/CMakeLists.txt").read_text(encoding="utf-8")
        cls.lvgl_pool = int(re.search(r"P34_OTA_FIXED_CONFIG=1.*?LV_MEM_SIZE=(\d+)U", cmake, re.S)[1])
        hal_path = ROOT / "MDK-ARM_F435/Platform/HAL/HAL_Display.cpp"
        source = hal_path.read_text(encoding="utf-8")
        signatures = ("void DMA1_Channel3_IRQHandler", "void HAL::Display_SendPixels",
                      "void HAL::Display_WaitForSendFinish", "void HAL::Display_SendPixelsBlocking",
                      "void HAL::Display_SetSendFinishCallback")
        checked(cls.directory / "hal_display_methods.inc").write_text(
            "\n\n".join(method(source, signature) for signature in signatures), encoding="utf-8")
        write_ui_helpers(ROOT, cls.directory)
        inputs = (
            "UI/\u4eea\u8868\u76d8.png",
            "USER/App/Pages/Dialplate/DialplateView.cpp",
            "USER/App/Pages/Dialplate/DialplateView.h",
            "USER/App/Pages/Dialplate/Dialplate.cpp",
            "USER/App/Pages/Dialplate/DialplateGlowData.inc",
            "USER/App/Resource/Image/img_src_dialplate_skin.c",
            "USER/lv_port/lv_port.h", "USER/App/Common/HAL/HAL.h",
            "MDK-ARM_F435/Platform/HAL/HAL_Display.cpp",
            "MDK-ARM_F435/Platform/lv_port/lv_port_disp.cpp",
            "MDK-ARM_F435/cmake-generated/CMakeLists.txt",
            "tests/ota/lvgl_companion/lv_conf.h", "USER/App/Pages/StatusBar/StatusBar.cpp",
            "USER/App/Pages/FirmwareUpdate/FirmwareUpdate.cpp",
            "tests/ota/dialplate_ui_harness.cpp", "tests/ota/test_dialplate_ui.py",
            "tests/ota/lvgl_companion/CMakeLists.txt")
        hashes = {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in inputs}
        checked(cls.directory / "source-sha256.json").write_text(
            json.dumps(hashes, indent=2) + "\n", encoding="utf-8")
        commands = [
            ["cmake", "-S", str(ROOT / "tests/ota/lvgl_companion"), "-B", str(cls.build),
             "-G", "Ninja", "-DCMAKE_BUILD_TYPE=Debug", "-DDIALPLATE_ONLY=ON",
             "-DCMAKE_C_COMPILER=" + shutil.which("gcc"),
             "-DCMAKE_CXX_COMPILER=" + shutil.which("g++"), "-DHARNESS_DIR=" + str(cls.directory),
             "-DDIALPLATE_UI_ROOT=" + str(ROOT), "-DDIALPLATE_VARIANTS=" + ";".join(VARIANTS),
             "-DDIALPLATE_LV_MEM_SIZE=" + str(cls.lvgl_pool)],
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

        cls.reference_build = None
        reference = os.environ.get("E_TRACK_UI_REFERENCE_ROOT")
        if reference:
            reference_root = Path(reference).resolve(strict=True)
            cls.reference_directory = checked(cls.directory / "reference")
            cls.reference_directory.mkdir()
            cls.reference_build = checked(cache / "build-reference")
            reference_stub = checked(cls.reference_directory / "HAL")
            reference_stub.mkdir()
            checked(reference_stub / "HAL.h").write_text(HAL_STUB, encoding="utf-8")
            # The View needs LVGL/resources, not the unrelated legacy PageFactory.
            checked(cls.reference_directory / "reference_page_dependencies.h").write_text(
                '#define __PAGE_H\n#include "lvgl/lvgl.h"\n'
                '#include "Resource/ResourcePool.h"\n', encoding="utf-8")
            checked(cls.reference_directory / "hal_display_methods.inc").write_text(
                "\n\n".join(method(source, signature) for signature in signatures), encoding="utf-8")
            write_ui_helpers(reference_root, cls.reference_directory)
            reference_files = list((reference_root / "USER/App/Pages/Dialplate").glob("*"))
            reference_files += list((reference_root / "USER/App/Resource").rglob("*"))
            checked(cls.reference_directory / "source-sha256.json").write_text(json.dumps({
                path.relative_to(reference_root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
                for path in reference_files if path.is_file()}, indent=2) + "\n", encoding="utf-8")
            reference_commands = [
                ["cmake", "-S", str(ROOT / "tests/ota/lvgl_companion"), "-B", str(cls.reference_build),
                 "-G", "Ninja", "-DCMAKE_BUILD_TYPE=Debug", "-DDIALPLATE_ONLY=ON",
                 "-DCMAKE_C_COMPILER=" + shutil.which("gcc"),
                 "-DCMAKE_CXX_COMPILER=" + shutil.which("g++"),
                 "-DHARNESS_DIR=" + str(cls.reference_directory),
                 "-DDIALPLATE_UI_ROOT=" + str(reference_root), "-DDIALPLATE_VARIANTS=desktop;hardware",
                 "-DDIALPLATE_LV_MEM_SIZE=" + str(cls.lvgl_pool)],
                ["cmake", "--build", str(cls.reference_build), "--target",
                 "dialplate_desktop", "dialplate_hardware", "--parallel", "8"]]
            for index, command in enumerate(reference_commands):
                result = subprocess.run(command, cwd=ROOT, env=cls.env, capture_output=True,
                                        text=True, timeout=300)
                checked(cls.reference_directory / ("build-%d.log" % index)).write_text(
                    result.stdout + result.stderr, encoding="utf-8")
                if result.returncode:
                    raise RuntimeError(result.stdout[-12000:] + result.stderr[-3000:])

    def run_case(self, variant, case, build=None, directory=None):
        build = self.build if build is None else build
        directory = self.directory if directory is None else directory
        extension = ".exe" if os.name == "nt" else ""
        command = [str(build / ("dialplate_" + variant + extension)), case, str(directory)]
        if build == self.reference_build:
            command.append("--without-arrow")
        result = subprocess.run(command, cwd=ROOT, env=self.env,
                                capture_output=True, text=True, timeout=30)
        checked(directory / (variant + "-" + case + ".log")).write_text(
            result.stdout + result.stderr, encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        names = [variant + "-" + case]
        if case == "spectrum_frames":
            names += [variant + "-spectrum_frames-" + str(frame) for frame in range(16)]
        if case in TIMER_FRAME_CASES:
            names += [variant + "-" + case + "-" + str(frame) for frame in range(32)]
        if case == "popup_occlusion":
            names += [variant + "-popup_occlusion-shown", variant + "-popup_occlusion-closed"]
        for name in names:
            image_path = checked(directory / (name + ".ppm"))
            data = image_path.read_bytes()
            header = b"P6\n240 320\n255\n"
            self.assertTrue(data.startswith(header))
            self.assertEqual(len(data), len(header) + 240 * 320 * 3)
            if Image is not None:
                with Image.open(image_path) as image:
                    image.save(checked(directory / (name + ".png")))
        print(result.stdout.strip())
        # Bind the named snapshot, not the last separately captured animation frame.
        return (directory / (names[0] + ".ppm")).read_bytes()

    def test_original_ui_source_is_preserved(self):
        view = (ROOT / "USER/App/Pages/Dialplate/DialplateView.cpp").read_text(encoding="utf-8")
        header = (ROOT / "USER/App/Pages/Dialplate/DialplateView.h").read_text(encoding="utf-8")
        presenter = (ROOT / "USER/App/Pages/Dialplate/Dialplate.cpp").read_text(encoding="utf-8")
        self.assertNotIn('IMG("gps_arrow_light")', view)
        anchor = "    ui.skin = skin;\n\n"
        self.assertEqual(view.count(anchor), 1)
        # Only the authorized arrow omission and popup guard differ from the reference.
        self.assertEqual(view.count(SPECTRUM_OCCLUSION_HELPER), 1)
        restored = view.replace(anchor, anchor + ORIGINAL_ARROW_LAYER, 1)
        restored = restored.replace("\n" + SPECTRUM_OCCLUSION_HELPER, "", 1)
        for original in SPECTRUM_OCCLUSION_CONDITIONS:
            guarded = "if(" + original + " || DialplatePopup_CoversSpectrum())"
            self.assertEqual(restored.count(guarded), 1)
            restored = restored.replace(guarded, "if(" + original + ")", 1)
        self.assertEqual(source_digest(restored), REFERENCE_UI_HASHES["view"])
        self.assertEqual(source_digest(header), REFERENCE_UI_HASHES["header"])
        for name in (*UI_METHODS, "void Dialplate::Update"):
            self.assertEqual(source_digest(method(presenter, name)), REFERENCE_UI_HASHES[name], name)

    def test_candidate_memory_preserves_the_system_heap_gate(self):
        self.assertEqual(self.lvgl_pool, 120 * 1024)
        cmake = (ROOT / "MDK-ARM_F435/cmake-generated/CMakeLists.txt").read_text(encoding="utf-8")
        self.assertIn('"-Wl,--defsym=__p34_heap_min=4096"', cmake)

    def test_skin_restores_the_original_png_locator_only(self):
        data = skin_rgb565()
        self.assertEqual(hashlib.sha256(ORIGINAL_LOCATOR_PNG.read_bytes()).hexdigest(),
                         ORIGINAL_LOCATOR_PNG_SHA256, "The owner's original PNG changed")
        self.assertEqual(hashlib.sha256(locator_pixels(data, 2, outside=True)).hexdigest(),
                         SKIN_OUTSIDE_LOCATOR_SHA256, "Skin pixels outside the owner-requested repair changed")
        self.assertEqual(hashlib.sha256(locator_pixels(data, 2)).hexdigest(), SKIN_ORIGINAL_LOCATOR_SHA256,
                         "The locator differs from the original PNG's RGB565 pixels")
        if Image is not None:
            with Image.open(ORIGINAL_LOCATOR_PNG) as image:
                self.assertEqual(image.size, (240, 320))
                original = bytearray()
                for r, g, b in image.convert("RGB").getdata():
                    value = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
                    original.extend((value & 0xFF, value >> 8))
            self.assertEqual(locator_pixels(data, 2), locator_pixels(original, 2),
                             "Original PNG pixels were repainted, resized or copied from another location")

    def assert_reference_pixels(self, actual, original, name):
        header = b"P6\n240 320\n255\n"
        self.assertEqual(actual[:len(header)], original[:len(header)])
        actual_pixels, original_pixels = actual[len(header):], original[len(header):]
        self.assertEqual(locator_pixels(actual_pixels, 3, outside=True),
                         locator_pixels(original_pixels, 3, outside=True),
                         "UI pixels outside the authorized background repair differ: " + name)
        repaired, previous = locator_pixels(actual_pixels, 3), locator_pixels(original_pixels, 3)
        return sum(repaired[index:index + 3] != previous[index:index + 3]
                   for index in range(0, len(repaired), 3))

    def test_reference_render_equivalence(self):
        if self.reference_build is None:
            self.skipTest("Set E_TRACK_UI_REFERENCE_ROOT for read-only reference rendering")
        hashes = {}
        for variant in ("desktop", "hardware"):
            for case in REFERENCE_RENDER_CASES:
                with self.subTest(variant=variant, case=case):
                    actual = self.run_case(variant, case)
                    original = self.run_case(variant, case, self.reference_build, self.reference_directory)
                    self.assertEqual(actual, (self.directory / (variant + "-" + case + ".ppm")).read_bytes())
                    self.assertEqual(original, (self.reference_directory / (variant + "-" + case + ".ppm")).read_bytes())
                    different = self.assert_reference_pixels(actual, original, variant + "-" + case)
                    hashes[variant + "-" + case] = {
                        "targetSha256": hashlib.sha256(actual).hexdigest(),
                        "referenceSha256": hashlib.sha256(original).hexdigest(),
                        "differentPixels": different,
                        "outsideLocatorDifferentPixels": 0}
                    if case == "spectrum_frames" or case in TIMER_FRAME_CASES:
                        frame_count = 16 if case == "spectrum_frames" else 32
                        for frame in range(frame_count):
                            name = variant + "-" + case + "-" + str(frame)
                            actual_frame = (self.directory / (name + ".ppm")).read_bytes()
                            original_frame = (self.reference_directory / (name + ".ppm")).read_bytes()
                            different = self.assert_reference_pixels(actual_frame, original_frame, name)
                            hashes[name] = {
                                "targetSha256": hashlib.sha256(actual_frame).hexdigest(),
                                "referenceSha256": hashlib.sha256(original_frame).hexdigest(),
                                "differentPixels": different,
                                "outsideLocatorDifferentPixels": 0}
        checked(self.directory / "reference-comparison.json").write_text(
            json.dumps(hashes, indent=2) + "\n", encoding="utf-8")
        if Image is not None:
            with Image.open(self.reference_directory / "desktop-populated.ppm") as left, \
                    Image.open(self.directory / "desktop-populated.ppm") as right:
                comparison = Image.new("RGB", (480, 320))
                comparison.paste(left, (0, 0))
                comparison.paste(right, (240, 0))
                comparison.save(checked(self.directory / "reference-left-target-right.png"))

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
        self.assertNotIn("View.SetMetricText(", presenter)
        self.assertIn("SetAdaptiveMetricLabel(", presenter)
        self.assertIn("SetCalorieLabel(View.ui.metrics.item[3].labelValue", presenter)

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
