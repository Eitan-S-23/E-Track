"""Source-bound modal lifecycle regressions against the actual bundled LVGL."""

import ast
import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

from test_main_menu_encoder import method

ROOT = Path(__file__).resolve().parents[2]
UI = "USER/App/Pages/FirmwareUpdate/FirmwareUpdate.cpp"
BASELINE = "816b1888be2dfaa632e4e802e6b680ec85ed5aec"
CASES = ("ownership", "repeat", "snapshots", "offer_replacement", "deleted_focus", "escape", "async_open",
         "transfer_progress", "apply_progress", "progress_close")


def checked(path):
    path = path.absolute()
    path.relative_to(ROOT)
    for candidate in (path, *path.parents):
        if candidate.exists() and (candidate.is_symlink() or
                getattr(candidate.lstat(), "st_file_attributes", 0) & 0x400):
            raise RuntimeError("Redirected modal test output")
    return path


class CompanionModalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        for tool in ("cmake", "ninja", "gcc", "g++"):
            if shutil.which(tool) is None:
                raise RuntimeError("Required host tool: " + tool)
        cache = checked(ROOT / ".cache/companion-modal-tests")
        cache.mkdir(parents=True, exist_ok=True)
        cls.directory = checked(Path(tempfile.mkdtemp(prefix="run-", dir=cache)))
        cls.build = checked(cache / "build")
        cls.env = dict(os.environ, TEMP=str(cls.directory), TMP=str(cls.directory), TMPDIR=str(cls.directory),
                       PYTHONDONTWRITEBYTECODE="1")
        source = (ROOT / UI).read_text(encoding="utf-8")
        original = subprocess.run(["git", "-c", "safe.directory=" + ROOT.as_posix(),
            "--no-optional-locks", "show", BASELINE + ":" + UI], cwd=ROOT, env=cls.env,
            capture_output=True, check=True, timeout=30).stdout.decode("utf-8")
        template = (ROOT / "tests/ota/companion_modal_harness.cpp.in").read_text(encoding="utf-8")
        for name, text in (("original", original), ("candidate", source)):
            block = text[text.index("namespace\n{\n    PageManager* companionManager"):]
            if name == "candidate":
                block = "#define COMPANION_PROGRESS_TEST 1\n" + method(text, "void CreateUpdateProgress") + "\n" + block
            # Init belongs to Page even when the original fixture has no UI header.
            generated = template.replace("// INSERT_PRODUCTION_MODAL", block).replace(
                "namespace Page { void FirmwareCompanion_Show(); }",
                "namespace Page { void FirmwareCompanion_Show(); void FirmwareCompanion_Init(PageManager*); }")
            checked(cls.directory / (name + ".cpp")).write_text(generated, encoding="utf-8")
        commands = [
            ["cmake", "-S", str(ROOT / "tests/ota/lvgl_companion"), "-B", str(cls.build),
             "-G", "Ninja", "-DCMAKE_BUILD_TYPE=Debug", "-DCMAKE_C_COMPILER=" + shutil.which("gcc"),
             "-DCMAKE_CXX_COMPILER=" + shutil.which("g++"), "-DHARNESS_DIR=" + str(cls.directory)],
            ["cmake", "--build", str(cls.build), "--target", "original", "candidate", "--parallel", "8"],
        ]
        for index, command in enumerate(commands):
            result = subprocess.run(command, cwd=ROOT, env=cls.env, capture_output=True, text=True, timeout=240)
            checked(cls.directory / ("build-%d.log" % index)).write_text(result.stdout + result.stderr, encoding="utf-8")
            if result.returncode:
                raise RuntimeError(result.stdout[-9000:] + result.stderr[-3000:])
        print("Real-LVGL originals: " + str(cls.directory))
        print("Modal SHA-256: " + hashlib.sha256(source.encode()).hexdigest())

    def run_case(self, variant, case):
        extension = ".exe" if os.name == "nt" else ""
        result = subprocess.run([str(self.build / (variant + extension)), case, str(self.directory)],
            cwd=ROOT, env=self.env, capture_output=True, text=True, timeout=30)
        checked(self.directory / (variant + "-" + case + ".log")).write_text(
            result.stdout + result.stderr, encoding="utf-8")
        return result

    def test_original_reproduces_cross_group_membership(self):
        result = self.run_case("original", "ownership")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("page group owns modal buttons", result.stderr)

    def test_menu_entry_and_font_coverage(self):
        menu = (ROOT / "USER/App/Pages/Menu/MainMenu.cpp").read_text(encoding="utf-8")
        source = (ROOT / UI).read_text(encoding="utf-8")
        self.assertNotIn('"@companion"', source)
        self.assertIn("MENU_ACTION_UPDATE", menu)
        self.assertIn("FirmwareCompanion_Show();", menu)
        glyphs = {int(value, 16) for value in re.findall(r"U\+([0-9A-Fa-f]+)",
            (ROOT / "USER/App/Resource/Font/font_cn_16.c").read_text(encoding="utf-8"))}
        for text in (menu, source[source.index("    const char* CompanionStatusText"):]):
            for literal in re.findall(r'"(?:[^"\\\n]|\\.)*"', text):
                decoded = ast.literal_eval("b" + literal).decode("utf-8")
                for char in decoded:
                    if ord(char) >= 0x80 and not 0xE000 <= ord(char) <= 0xF8FF:
                        self.assertIn(ord(char), glyphs, "Missing glyph: " + char)
        for char in "\u68c0\u67e5\u66f4\u65b0":
            self.assertIn(ord(char), glyphs)


def test_case(name):
    def run(self):
        result = self.run_case("candidate", name)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        print(result.stdout.strip())
    return run


for case in CASES:
    setattr(CompanionModalTests, "test_" + case, test_case(case))

if __name__ == "__main__":
    unittest.main(verbosity=2)
