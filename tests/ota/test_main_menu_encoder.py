"""Compile the real menu methods against a small LVGL unit-test boundary.

This is not a simulator rendering or physical encoder observation.
"""

import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
MENU = "USER/App/Pages/Menu/MainMenu.cpp"
METHODS = ("bool MainMenu::IsFocusItem", "void MainMenu::RefreshEncoderGroup",
           "void MainMenu::ClearEncoderGroup", "void MainMenu::onEvent")


def method(source, signature):
    start = source.index(signature + "(")
    brace = source.index("{", start)
    depth = 0
    for position in range(brace, len(source)):
        depth += (source[position] == "{") - (source[position] == "}")
        if depth == 0:
            return source[start:position + 1]
    raise ValueError("Unterminated production method")


class MainMenuEncoderTests(unittest.TestCase):
    def test_real_methods_and_original_regression(self):
        compiler = shutil.which("g++")
        if compiler is None:
            self.fail("A host g++ is required for the menu behavioral self-test")
        cache = ROOT / ".cache/main-menu-tests"
        for candidate in (cache, *cache.parents):
            if candidate.exists() and (candidate.is_symlink() or
                    getattr(candidate.lstat(), "st_file_attributes", 0) & 0x400):
                self.fail("Redirected test output")
        cache.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=cache) as directory:
            work = Path(directory)
            env = dict(os.environ, TEMP=directory, TMP=directory, TMPDIR=directory)
            original = subprocess.run(["git", "-c", "safe.directory=" + ROOT.as_posix(),
                "--no-optional-locks", "show", "bd146e6b7dc6d1c2616c823f1e3668b671c8076d:" + MENU],
                cwd=ROOT, env=env, check=True, capture_output=True, timeout=30).stdout.decode("utf-8")
            candidate = (ROOT / MENU).read_text(encoding="utf-8")
            template = (ROOT / "tests/ota/main_menu_encoder_harness.cpp.in").read_text(encoding="utf-8")
            for label, source, expected in (("original", original, 1), ("candidate", candidate, 0)):
                generated = template.replace("// INSERT_PRODUCTION_METHODS",
                    "\n\n".join(method(source, name) for name in METHODS))
                cpp, executable = work / (label + ".cpp"), work / (label + ".exe")
                cpp.write_text(generated, encoding="utf-8")
                build = subprocess.run([compiler, "-std=c++11", "-Wall", "-Wextra", "-Werror",
                    "-static-libgcc", "-static-libstdc++", str(cpp), "-o", str(executable)],
                    cwd=ROOT, env=env, capture_output=True, text=True, timeout=60)
                self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
                run = subprocess.run([str(executable)], cwd=ROOT, env=env,
                    capture_output=True, text=True, timeout=10)
                print(label + ": " + (run.stdout + run.stderr).strip())
                self.assertEqual(run.returncode, expected)
            print("candidate SHA-256: " + hashlib.sha256((ROOT / MENU).read_bytes()).hexdigest())


if __name__ == "__main__":
    unittest.main()
