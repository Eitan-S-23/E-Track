"""Run production modal, receiver admission and recorder methods on host stubs.

This is an implementation self-test, not a physical rotary/OTA observation.
"""

import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from test_main_menu_encoder import method

ROOT = Path(__file__).resolve().parents[2]
BASELINE = "7fa86c2cffc3fc7bd611887c0a7c399830445c28"
UI = "USER/App/Pages/FirmwareUpdate/FirmwareUpdate.cpp"
HAL = "USER/HAL/HAL_Bluetooth.cpp"
RECORDER = "USER/App/Common/DataProc/DP_Recorder.cpp"
METHODS = (
    (RECORDER, "bool DataProc::Recorder_IsOpen"),
    (HAL, "static bool companion_install_safe"),
    (HAL, "static int ble_env_overlay_acquire"),
    (HAL, "static void companion_update_phase"),
    (HAL, "static int ble_env_activate_staged"),
    (HAL, "void HAL::BT_CompanionGetInfo"),
    (HAL, "void HAL::BT_CompanionSetProgressRefresh"),
    (HAL, "bool HAL::BT_CompanionCheck"),
    (HAL, "bool HAL::BT_CompanionCanInstall"),
    (HAL, "bool HAL::BT_CompanionInstallPending"),
    (HAL, "static bool companion_display_matches"),
    (HAL, "bool HAL::BT_CompanionChoose"),
    (HAL, "void HAL::BT_CompanionPresented"),
    (UI, "bool CompanionCanInstall"),
    (UI, "const char* CompanionStatusText"),
    (UI, "void CompanionRequestClose"),
    (UI, "void CompanionButtonEvent"),
    (UI, "void CompanionRefresh"),
    (RECORDER, "static int onNotify"),
    (RECORDER, "static int onEvent"),
    ("USER/App/Pages/Dialplate/DialplateModel.cpp", "bool DialplateModel::RecorderCommand"),
    ("USER/App/Pages/Dialplate/Dialplate.cpp", "void Dialplate::onRecord"),
)
CASES = ("replacement_refresh", "replacement_before_refresh", "same_offer_retransmission",
         "offer_expires_held", "checking_during_press", "offer_reappears_held", "lost_or_disabled_press",
         "later_binding", "later_once", "unsafe_after_choice", "motion_after_choice", "motion_before_choice",
         "battery_after_choice", "paused_recording", "safe_receiver_admission",
         "recording_reservation", "recording_binary_owner", "recording_ui_conflict",
         "durable_progress", "invalid_progress", "phase_progress", "fresh_transfer_progress",
         "apply_phase_notifications")


def extract(source, signature):
    return method(source[source.rindex(signature + "("):], signature)


class CompanionSafetyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cache = ROOT / ".cache/companion-safety-tests"
        for entry in (cache, *cache.parents):
            if entry.exists() and (entry.is_symlink() or getattr(entry.lstat(), "st_file_attributes", 0) & 0x400):
                raise RuntimeError("Redirected test output")
        compiler = shutil.which("g++")
        if compiler is None:
            raise RuntimeError("Host g++ required")
        cache.mkdir(parents=True, exist_ok=True)
        directory = Path(tempfile.mkdtemp(prefix="run-", dir=cache))
        cls.env = dict(os.environ, TEMP=str(directory), TMP=str(directory), TMPDIR=str(directory))
        paths = {path for path, _ in METHODS} | {"Libraries/Bluetooth/CompanionControl.h",
            "USER/App/Common/HAL/CompanionUpdate.h", "tests/ota/companion_control_test.cpp",
            "tests/ota/companion_safety_harness.cpp.in"}
        source = {path: (ROOT / path).read_text(encoding="utf-8") for path in paths}
        fixture = source["tests/ota/companion_control_test.cpp"].split("static void Test(", 1)[0]
        template = source["tests/ota/companion_safety_harness.cpp.in"].replace("// INSERT_CONTROL_FIXTURE", fixture)
        originals = {}
        for path in (UI, HAL):
            originals[path] = subprocess.run(["git", "-c", "safe.directory=" + ROOT.as_posix(),
                "--no-optional-locks", "show", BASELINE + ":" + path],
                cwd=ROOT, env=cls.env, capture_output=True, check=True, timeout=30).stdout.decode("utf-8")
        cls.executables = {}
        for label in ("candidate", "original-boundaries"):
            methods = []
            for path, signature in METHODS:
                original = label == "original-boundaries" and signature in (
                    "void CompanionButtonEvent", "void CompanionRefresh", "static int ble_env_overlay_acquire")
                methods.append(extract(originals[path] if original else source[path], signature))
            cpp = directory / (label + ".cpp")
            cpp.write_text(template.replace("// INSERT_PRODUCTION_METHODS", "\n\n".join(methods)), encoding="utf-8")
            exe = directory / (label + ".exe")
            build = subprocess.run([compiler, "-std=c++11", "-Wall", "-Wextra", "-Werror",
                "-static-libgcc", "-static-libstdc++", "-I", str(ROOT / "Libraries"),
                "-I", str(ROOT / "USER/App"), str(cpp), "-o", str(exe)],
                cwd=ROOT, env=cls.env, capture_output=True, text=True, timeout=60)
            if build.returncode:
                raise RuntimeError(build.stdout + build.stderr)
            cls.executables[label] = exe
        for path in sorted(paths):
            print(path + " SHA-256: " + hashlib.sha256((ROOT / path).read_bytes()).hexdigest())
        print("Retained fixtures: " + str(directory))

    def test_original_boundaries_fail_both_review_oracles(self):
        for case in ("replacement_refresh", "unsafe_after_choice"):
            result = subprocess.run([str(self.executables["original-boundaries"]), case],
                cwd=ROOT, env=self.env, capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            expected = "held press confirmed replacement" if case == "replacement_refresh" else "unsafe receiver acquired overlay"
            self.assertIn(expected, result.stderr)
            print("original boundary " + case + ": expected failure: " + result.stderr.strip())

    def test_phase_refresh_is_outside_blocking_storage_and_before_reset(self):
        source = (ROOT / HAL).read_text(encoding="utf-8")
        apply = extract(source, "static int ble_apply_staged")
        self.assertLess(apply.index("companion_update_phase(HAL::COMPANION_UPDATE_BACKING_UP)"),
                        apply.index("HAL::OTA_BackupStage"))
        reset = extract(source, "static void ble_env_system_reset")
        self.assertLess(reset.index("companion_update_phase(HAL::COMPANION_UPDATE_REBOOTING)"),
                        reset.index("NVIC_SystemReset"))
        wait_rx = extract(source, 'extern "C" void HAL_OTA_QspiWaitRx')
        self.assertNotIn("companion_update_phase", wait_rx)


def test_case(name):
    def run(self):
        result = subprocess.run([str(self.executables["candidate"]), name], cwd=ROOT, env=self.env,
            capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        print(result.stdout.strip())
    return run


for case in CASES:
    setattr(CompanionSafetyTests, "test_" + case, test_case(case))

if __name__ == "__main__":
    unittest.main(verbosity=2)
