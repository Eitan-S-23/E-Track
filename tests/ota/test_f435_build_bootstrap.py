#!/usr/bin/env python3
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BUILD_SCRIPT = ROOT / "MDK-ARM_F435" / "build_f435.ps1"
ONE_CLICK = ROOT / "build_f435_and_simulator.bat"
PROJECT = ROOT / "MDK-ARM_F435" / "proj.uvprojx"
CMAKE_PROJECT = ROOT / "MDK-ARM_F435" / "cmake-generated" / "CMakeLists.txt"
AGENT_GUIDE = ROOT / "AGENTS.md"
GOVERNANCE_WORKFLOW = ROOT / ".github" / "workflows" / "acceptance-governance.yml"
FIRMWARE_WORKFLOW = ROOT / ".github" / "workflows" / "firmware-build.yml"


class F435BuildBootstrapTests(unittest.TestCase):
    def test_one_click_defaults_to_ci_aligned_gcc_targets(self):
        text = ONE_CLICK.read_text(encoding="ascii")
        self.assertIn('set "BUILD_AC5=0"', text)
        self.assertIn('set "AC5_ONLY=0"', text)
        self.assertIn('set "SOURCE_DATE_EPOCH=1786320000"', text)
        self.assertIn(
            'cmake.exe -S "%CMAKE_SOURCE%" -B "%GCC_BUILD%" -G Ninja '
            '-DCMAKE_BUILD_TYPE=Release -DCMAKE_OBJECT_PATH_MAX=1024',
            text,
        )
        self.assertIn(
            'cmake.exe --build "%GCC_BUILD%" --target '
            'X_Track_App_GCC X_Track_Boot --parallel',
            text,
        )
        self.assertLess(text.index("call :build_gcc"), text.index("call :build_simulator"))

    def test_ac5_builds_are_explicit_and_bootstrap_capable(self):
        text = ONE_CLICK.read_text(encoding="ascii")
        self.assertIn('if /I "%~1"=="--with-ac5"', text)
        self.assertIn('if /I "%~1"=="--ac5-only"', text)
        self.assertIn('set "AC5_TARGET=X-Track-App-AC5"', text)
        self.assertIn('-Target "%AC5_TARGET%"', text)
        self.assertIn("-BootstrapIfNeeded -AutoStale -AutoFonts", text)
        self.assertIn('if /I "%~1"=="--legacy"', text)
        self.assertIn("--legacy requires --with-ac5 or --ac5-only", text)

    def test_build_temporary_outputs_are_project_local(self):
        text = ONE_CLICK.read_text(encoding="ascii")
        self.assertIn('set "TEMP=%ROOT%.cache\\build-temp"', text)
        self.assertIn('set "SCCACHE_DIR=%ROOT%.cache\\sccache"', text)
        self.assertIn('set "CCACHE_DIR=%ROOT%.cache\\ccache"', text)
        self.assertIn(
            'set "GCC_BUILD=%CMAKE_SOURCE%\\build-gcc-release"', text
        )

    def test_cmake_respects_explicit_object_path_limit(self):
        text = CMAKE_PROJECT.read_text(encoding="utf-8")
        self.assertIn("if(NOT DEFINED CMAKE_OBJECT_PATH_MAX)", text)
        self.assertIn("set(CMAKE_OBJECT_PATH_MAX 140)", text)
        self.assertNotIn("set(CMAKE_OBJECT_PATH_MAX 140)\nif(NOT CMAKE_BUILD_TYPE)", text)

    def test_bootstrap_is_explicit_and_incremental_by_default(self):
        text = BUILD_SCRIPT.read_text(encoding="ascii")
        self.assertIn("[string]   $Target = 'X-Track-App-AC5'", text)
        self.assertIn("[switch]   $BootstrapIfNeeded", text)
        self.assertIn("if (-not $BootstrapIfNeeded)", text)
        self.assertIn("Rerun with -BootstrapIfNeeded", text)

    def test_bootstrap_detects_missing_empty_and_stale_metadata(self):
        text = BUILD_SCRIPT.read_text(encoding="ascii")
        self.assertIn('"missing: {0}"', text)
        self.assertIn('"empty: {0}"', text)
        self.assertIn('"older than proj.uvprojx: {0}"', text)
        self.assertIn("LastWriteTimeUtc -lt $projectTime", text)

    def test_bootstrap_hash_stamp_avoids_timestamp_only_refreshes(self):
        text = BUILD_SCRIPT.read_text(encoding="ascii")
        self.assertIn('("proj_{0}.uvprojx.sha256" -f $Target)', text)
        self.assertIn("[Security.Cryptography.SHA256]::Create()", text)
        self.assertIn('.Replace("`r`n", "`n").Replace("`r", "`n")', text)
        self.assertIn("$sha256.ComputeHash($bytes)", text)
        self.assertIn("proj.uvprojx content hash changed", text)
        self.assertIn("Get-KeilMetadataProblems -IgnoreProjectHash", text)
        self.assertIn("Update-KeilMetadataProjectHash", text)
        self.assertIn("Normalize-UVisionGeneratedWhitespace", text)
        self.assertIn("[Text.RegularExpressions.RegexOptions]::Multiline", text)

    def test_running_uvision_fails_fast(self):
        text = BUILD_SCRIPT.read_text(encoding="ascii")
        self.assertIn("Get-Process -Name $uv4ProcessName", text)
        self.assertIn("Close uVision and rerun", text)
        self.assertNotIn("while ($running", text)

    def test_bootstrap_requires_zero_error_log_and_fresh_metadata(self):
        text = BUILD_SCRIPT.read_text(encoding="ascii")
        self.assertIn("UV4 bootstrap log has no build summary", text)
        self.assertIn("if ($errorCount -ne 0)", text)
        self.assertIn("Get-KeilMetadataProblems", text)
        self.assertIn("UV4 bootstrap left invalid metadata", text)

    def test_bootstrap_waits_for_detached_uvision_with_timeout(self):
        text = BUILD_SCRIPT.read_text(encoding="ascii")
        self.assertIn("$BootstrapTimeoutSeconds = 900", text)
        self.assertIn("Start-Process -FilePath $uv4", text)
        self.assertIn("$process.WaitForExit($timeoutMs)", text)
        self.assertIn("taskkill.exe", text)
        self.assertNotIn("[checked]", text)

    def test_ota_app_target_declares_ota_inputs_and_cpp11_group(self):
        root = ET.parse(PROJECT).getroot()
        target = next(
            item for item in root.findall("./Targets/Target")
            if item.findtext("TargetName") == "X-Track-App-AC5"
        )
        include_path = target.findtext(
            "./TargetOption/TargetArmAds/Cads/VariousControls/IncludePath"
        )
        self.assertIn(r"..\boot\include", include_path.split(";"))
        self.assertIn(
            r"..\bsdiff_lzma_AES128-main\bspatch\AES128_CTR",
            include_path.split(";"),
        )
        groups = {
            group.findtext("GroupName"): group
            for group in target.findall("./Groups/Group")
        }
        ota_paths = {
            file.findtext("FilePath")
            for file in groups["OTA"].findall("./Files/File")
        }
        self.assertIn(r"..\Libraries\OTA\ota_package.c", ota_paths)
        self.assertIn(r"..\boot\src\boot_crc32.c", ota_paths)
        firmware_group = groups["Pages/FirmwareUpdate"]
        self.assertEqual(
            "--cpp11",
            firmware_group.findtext(
                "./GroupOption/GroupArmAds/Cads/VariousControls/MiscControls"
            ),
        )
        firmware_paths = {
            file.findtext("FilePath")
            for file in firmware_group.findall("./Files/File")
        }
        self.assertIn(
            r"..\USER\App\Pages\FirmwareUpdate\FirmwareUpdate.cpp",
            firmware_paths,
        )
        self.assertIn(r"..\USER\App\Utils\OtaUpdate\OtaUpdate.cpp", firmware_paths)

    def test_agent_guide_uses_matching_ac5_target_and_map(self):
        text = AGENT_GUIDE.read_text(encoding="utf-8")
        self.assertIn("build_f435.ps1 -Target X-Track-App-AC5 -AutoStale", text)
        self.assertIn(
            r"MDK-ARM_F435\Listings-App-AC5\X-Track-App-AC5.map",
            text,
        )
        self.assertNotIn(r"MDK-ARM_F435\Listings\X-Track.map", text)

    def test_governance_tests_are_wired_into_ci(self):
        governance = GOVERNANCE_WORKFLOW.read_text(encoding="utf-8")
        for path in (
            "Tools/acceptance/**",
            "Tools/provenance/**",
            "docs/acceptance-contracts/**",
            "docs/acceptance-execution-contract.md",
            "build_f435_and_simulator.bat",
        ):
            self.assertIn(path, governance)
        for test in (
            "tests/ota/test_acceptance_bundle.py",
            "tests/ota/test_ac5_ram_budget.py",
            "tests/ota/test_f435_build_bootstrap.py",
            "tests/ota/test_p2_5_build_provenance.py",
        ):
            self.assertIn(test, governance)

    def test_firmware_ci_excludes_governance_only_tests(self):
        firmware = FIRMWARE_WORKFLOW.read_text(encoding="utf-8")
        self.assertNotIn('      - "tests/ota/**"', firmware)
        self.assertIn('      - "tests/ota/test_ota_*.py"', firmware)
        self.assertIn('      - "tests/ota/test_ota_*.c"', firmware)
        for test in (
            "test_acceptance_bundle.py",
            "test_ac5_ram_budget.py",
            "test_f435_build_bootstrap.py",
            "test_p2_5_build_provenance.py",
        ):
            self.assertNotIn(test, firmware)


if __name__ == "__main__":
    unittest.main()
