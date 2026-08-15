#!/usr/bin/env python3
import ast
import hashlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
GUARD = ROOT / "Tools" / "provenance" / "worktree_guard.ps1"
MANIFEST = ROOT / "Tools" / "provenance" / "source_manifest.ps1"
PROFILE_CONFIG = ROOT / "Tools" / "provenance" / "manifest_profiles.json"
VALIDATOR_PATH = ROOT / "Tools" / "acceptance" / "validate_bundle.py"
REPRO = ROOT / "cmake" / "reproducible_build.cmake"
FIRMWARE_WORKFLOW = ROOT / ".github" / "workflows" / "firmware-build.yml"
ACCEPTANCE_WORKFLOW = ROOT / ".github" / "workflows" / "acceptance-governance.yml"
GCC_REPRO_TEST = ROOT / "tests" / "ota" / "test_ota_gcc_reproducibility.py"
POWERSHELL = shutil.which("powershell.exe") or shutil.which("pwsh")
VALIDATOR_SPEC = importlib.util.spec_from_file_location("provenance_validator", VALIDATOR_PATH)
VALIDATOR = importlib.util.module_from_spec(VALIDATOR_SPEC)
VALIDATOR_SPEC.loader.exec_module(VALIDATOR)


def repo_local_temp_env(directory):
    env = os.environ.copy()
    for name in ("TEMP", "TMP", "TMPDIR"):
        env[name] = str(directory)
    return env


def load_gcc_repro_module():
    spec = importlib.util.spec_from_file_location("gcc_reproducibility_test", GCC_REPRO_TEST)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load GCC reproducibility test: {GCC_REPRO_TEST}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class P25BuildProvenanceTests(unittest.TestCase):
    def test_release_requires_source_date_epoch(self):
        text = REPRO.read_text(encoding="ascii")
        self.assertIn('CMAKE_BUILD_TYPE STREQUAL "Release"', text)
        self.assertIn("Release firmware builds require SOURCE_DATE_EPOCH", text)
        self.assertIn('MATCHES "^[0-9]+$"', text)
        workflow = FIRMWARE_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("python3 tests/ota/test_ota_gcc_reproducibility.py", workflow)
        governance = ACCEPTANCE_WORKFLOW.read_text(encoding="utf-8")
        self.assertEqual(
            2,
            governance.count('"tests/ota/test_ota_gcc_reproducibility.py"'),
        )

    def test_gcc_reproducibility_forbids_skip_apis(self):
        source = GCC_REPRO_TEST.read_text(encoding="ascii")
        tree = ast.parse(source, filename=str(GCC_REPRO_TEST))
        forbidden = {
            "SkipTest",
            "expectedFailure",
            "skip",
            "skipIf",
            "skipTest",
            "skipUnless",
        }
        violations = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and node.id in forbidden:
                violations.append((node.lineno, node.id))
            elif isinstance(node, ast.Attribute) and node.attr in forbidden:
                violations.append((node.lineno, node.attr))
        self.assertEqual([], violations)

    def test_gcc_reproducibility_missing_compiler_is_failure(self):
        module = load_gcc_repro_module()
        with mock.patch.object(module, "find_arm_gcc", return_value=None):
            result = unittest.TestResult()
            module.load_suite().run(result)

        self.assertEqual(1, result.testsRun)
        self.assertEqual([], result.skipped)
        self.assertEqual([], result.errors)
        self.assertEqual(1, len(result.failures))
        self.assertIn("GNU Arm compiler is required", result.failures[0][1])

    def test_gcc_reproducibility_runner_rejects_nonexecuted_results(self):
        module = load_gcc_repro_module()

        class SkippedFixture(unittest.TestCase):
            def runTest(self):
                self.skipTest("fixture skip")

        class ExpectedFailureFixture(unittest.TestCase):
            @unittest.expectedFailure
            def runTest(self):
                self.fail("fixture expected failure")

        suites = {
            "empty": unittest.TestSuite(),
            "skipped": unittest.TestSuite([SkippedFixture()]),
            "expected-failure": unittest.TestSuite([ExpectedFailureFixture()]),
        }
        for name, suite in suites.items():
            with self.subTest(name=name):
                stream = io.StringIO()
                self.assertEqual(1, module.run_suite(suite=suite, stream=stream))
                self.assertIn("FAIL-CLOSED:", stream.getvalue())

    def test_manifest_protocol_is_explicit(self):
        text = MANIFEST.read_text(encoding="ascii")
        self.assertIn("[System.StringComparer]::Ordinal", text)
        self.assertIn("Join-Path (Join-Path (Join-Path $PSHOME 'Modules')", text)
        self.assertIn("Import-Module $utilityModule", text)
        self.assertIn("UTF-8 without BOM, CRLF, one trailing newline", text)
        self.assertIn("manifest_profiles.json", text)
        self.assertIn("etrack-manifest-profiles-v1", text)
        self.assertIn("Assert-WorktreeFileOutput", text)
        self.assertIn("'ls-files', '-co', '--exclude-standard', '-z'", text)
        self.assertIn("[Text.UTF8Encoding]::new($false, $true)", text)

    def test_manifest_profiles_separate_product_and_validation_inputs(self):
        text = MANIFEST.read_text(encoding="ascii")
        self.assertIn("ValidateSet('Legacy', 'Production', 'Validation', 'Governance')", text)
        self.assertIn("'etrack-input-manifest-v2'", text)
        config = json.loads(PROFILE_CONFIG.read_text(encoding="ascii"))
        self.assertEqual("etrack-manifest-profiles-v1", config["schema"])
        production = config["profiles"]["Production"]
        validation = config["profiles"]["Validation"]
        governance = config["profiles"]["Governance"]
        self.assertIn(".github/workflows/firmware-build.yml", production["top_files"])
        self.assertIn("Tools/etu_pack.py", production["top_files"])
        self.assertIn("MDK-ARM_F435/cmake-generated/CMakeLists.txt", production["top_files"])
        self.assertIn(
            "MDK-ARM_F435/RTE/Device/-AT32F435RGT7/",
            production["root_patterns"],
        )
        self.assertIn("MDK-ARM_F435/RTE/_X-Track/", production["root_patterns"])
        self.assertNotIn("MDK-ARM_F435/RTE/_X-Track-App-AC5/", production["root_patterns"])
        cmake = (ROOT / "MDK-ARM_F435" / "cmake-generated" / "CMakeLists.txt").read_text(
            encoding="utf-8"
        )
        self.assertIn("../RTE/Device/-AT32F435RGT7", cmake)
        self.assertIn("../RTE/_X-Track", cmake)
        self.assertNotIn("Tools/", production["root_patterns"])
        self.assertNotIn("tests/", production["root_patterns"])
        self.assertIn("Tools/", validation["root_patterns"])
        self.assertIn("tests/", validation["root_patterns"])
        self.assertIn(".github/workflows/acceptance-governance.yml", validation["top_files"])
        self.assertIn(
            "docs/acceptance-contracts/template.contract.json",
            validation["top_files"],
        )
        self.assertIn(
            "docs/acceptance-contracts/template.evidence-matrix.json",
            validation["top_files"],
        )
        self.assertIn("Tools/provenance/manifest_profiles.json", validation["required_paths"])
        self.assertIn(
            "docs/acceptance-contracts/template.contract.json",
            validation["required_paths"],
        )
        self.assertIn(
            "docs/acceptance-contracts/template.evidence-matrix.json",
            validation["required_paths"],
        )
        self.assertIn("PLAN-OTA-EXEC.md", governance["top_files"])
        self.assertNotIn("docs/acceptance-contracts/", governance["root_patterns"])

    def test_worktree_guard_rejects_sibling_output(self):
        if POWERSHELL is None:
            self.skipTest("PowerShell is unavailable")
        with tempfile.TemporaryDirectory(dir=ROOT, prefix=".manifest-test-") as temp_dir:
            sibling = ROOT.parent / (ROOT.name + "-outside-test-" + Path(temp_dir).name)
            command = (
                f". '{GUARD}'; "
                f"Assert-WorktreeOutput -RepoRoot '{ROOT}' -OutputPath '{sibling}'"
            )
            result = subprocess.run(
                [
                    POWERSHELL,
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-Command",
                    command,
                ],
                cwd=ROOT,
                env=repo_local_temp_env(temp_dir),
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(sibling.exists())

    def test_worktree_guard_accepts_platform_native_child_path(self):
        if POWERSHELL is None:
            self.skipTest("PowerShell is unavailable")
        with tempfile.TemporaryDirectory(dir=ROOT, prefix=".manifest-test-") as temp_dir:
            child = Path(temp_dir) / "nested" / "evidence.txt"
            command = (
                f". '{GUARD}'; "
                f"Assert-WorktreeFileOutput -RepoRoot '{ROOT}' -FilePath '{child}'"
            )
            result = subprocess.run(
                [
                    POWERSHELL,
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-Command",
                    command,
                ],
                cwd=ROOT,
                env=repo_local_temp_env(temp_dir),
                capture_output=True,
                text=True,
            )
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertTrue(child.parent.is_dir())

    def test_worktree_guard_rejects_existing_output_symlink(self):
        if POWERSHELL is None:
            self.skipTest("PowerShell is unavailable")
        with tempfile.TemporaryDirectory(dir=ROOT, prefix=".manifest-test-") as temp_dir:
            temp = Path(temp_dir)
            target = temp / "real-evidence.txt"
            target.write_text("unchanged\n", encoding="ascii", newline="\n")
            link = temp / "evidence.txt"
            try:
                link.symlink_to(target)
            except OSError as exc:
                self.skipTest(f"symlink creation is unavailable: {exc}")
            command = (
                f". '{GUARD}'; "
                f"Assert-WorktreeFileOutput -RepoRoot '{ROOT}' -FilePath '{link}'"
            )
            result = subprocess.run(
                [
                    POWERSHELL,
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-Command",
                    command,
                ],
                cwd=ROOT,
                env=repo_local_temp_env(temp_dir),
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(0, result.returncode)
            self.assertEqual("unchanged\n", target.read_text(encoding="ascii"))

    def test_manifest_profiles_execute_and_report_their_category(self):
        if POWERSHELL is None:
            self.skipTest("PowerShell is unavailable")
        with tempfile.TemporaryDirectory(dir=ROOT, prefix=".manifest-test-") as temp_dir:
            for profile in ("Production", "Validation", "Governance"):
                output = Path(temp_dir) / profile.lower()
                result = subprocess.run(
                    [
                        POWERSHELL,
                        "-NoProfile",
                        "-ExecutionPolicy",
                        "Bypass",
                        "-File",
                        str(MANIFEST),
                        "-RepoRoot",
                        str(ROOT),
                        "-OutputDirectory",
                        str(output),
                        "-Profile",
                        profile,
                    ],
                    cwd=ROOT,
                    env=repo_local_temp_env(temp_dir),
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(0, result.returncode, result.stderr)
                manifest = json.loads((output / "source-manifest.json").read_text(encoding="utf-8-sig"))
                summary = json.loads((output / "summary.json").read_text(encoding="utf-8-sig"))
                self.assertEqual("etrack-input-manifest-v2", manifest["Schema"])
                self.assertEqual(profile, manifest["Profile"])
                self.assertNotIn("RepoRoot", manifest)
                self.assertNotIn("Head", manifest)
                self.assertEqual(str(ROOT.resolve()), str(Path(summary["RepoRoot"]).resolve()))
                self.assertRegex(summary["Head"], r"^[0-9a-fA-F]{40,64}$")
                manifest_bytes = (output / "source-manifest.json").read_bytes()
                self.assertEqual(
                    hashlib.sha256(manifest_bytes).hexdigest().upper(),
                    summary["ManifestJsonSHA256"],
                )
                paths = {entry["Path"] for entry in manifest["Files"]}
                if profile == "Production":
                    self.assertIn(".github/workflows/firmware-build.yml", paths)
                    self.assertIn("Tools/etu_pack.py", paths)
                    self.assertIn("MDK-ARM_F435/cmake-generated/CMakeLists.txt", paths)
                    self.assertTrue(
                        any(path.startswith("MDK-ARM_F435/RTE/") for path in paths)
                    )
                    self.assertIn("MDK-ARM_F435/RTE/_X-Track/RTE_Components.h", paths)
                    self.assertFalse(
                        any(
                            path.startswith("MDK-ARM_F435/RTE/_X-Track-App-AC5/")
                            for path in paths
                        )
                    )
                    self.assertFalse(
                        any(
                            path.startswith("MDK-ARM_F435/RTE/Device/-AT32F435CGU7/")
                            for path in paths
                        )
                    )
                    self.assertNotIn("tests/ota/test_ota_patch.py", paths)
                elif profile == "Validation":
                    self.assertIn("tests/ota/test_ota_patch.py", paths)
                    self.assertIn("Tools/provenance/source_manifest.ps1", paths)
                    self.assertIn("Tools/provenance/manifest_profiles.json", paths)
                    self.assertIn("Tools/\u56fe\u6807/README.md", paths)
                    self.assertIn(".github/workflows/acceptance-governance.yml", paths)
                    self.assertIn("docs/acceptance-contracts/template.contract.json", paths)
                    self.assertIn(
                        "docs/acceptance-contracts/template.evidence-matrix.json",
                        paths,
                    )
                    self.assertNotIn("USER/main.cpp", paths)
                    self.assertEqual(
                        VALIDATOR._collect_profile_records(ROOT, profile),
                        manifest["Files"],
                    )
                else:
                    self.assertIn("PLAN-OTA-EXEC.md", paths)
                    self.assertNotIn("docs/acceptance-contracts/template.contract.json", paths)

    def test_manifest_identity_ignores_root_head_and_mtime(self):
        if POWERSHELL is None:
            self.skipTest("PowerShell is unavailable")
        with tempfile.TemporaryDirectory(dir=ROOT, prefix=".manifest-stability-test-") as temp_dir:
            base = Path(temp_dir)
            outputs = []
            summaries = []
            mtimes = []
            for index in (1, 2):
                repo = base / f"repo-{index}"
                process_temp = repo / ".tmp"
                process_temp.mkdir(parents=True)
                process_env = repo_local_temp_env(process_temp)
                files = {
                    ".github/workflows/firmware-build.yml": "name: fixture\n",
                    "CMakeLists.txt": "cmake_minimum_required(VERSION 3.20)\n",
                    "build_f435_and_simulator.bat": "@echo off\n",
                    "MDK-ARM_F435/build_f435.ps1": "Write-Output fixture\n",
                    "MDK-ARM_F435/cmake-generated/CMakeLists.txt": "project(fixture C)\n",
                    "MDK-ARM_F435/proj.uvprojx": "<Project />\n",
                    "MDK-ARM_F435/RTE/Device/-AT32F435RGT7/gpio.c": "void gpio(void) {}\n",
                    "Tools/etu_pack.py": "print('fixture')\n",
                    "USER/sample.c": "int sample(void) { return 1; }\n",
                }
                for relative, content in files.items():
                    path = repo / relative
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(content, encoding="ascii", newline="\n")
                subprocess.run(
                    ["git", "init", "-q", str(repo)],
                    check=True,
                    cwd=ROOT,
                    env=process_env,
                )
                subprocess.run(
                    ["git", "-C", str(repo), "config", "user.name", "fixture"],
                    check=True,
                    env=process_env,
                )
                subprocess.run(
                    ["git", "-C", str(repo), "config", "user.email", "fixture@example.invalid"],
                    check=True,
                    env=process_env,
                )
                subprocess.run(
                    ["git", "-C", str(repo), "config", "core.autocrlf", "false"],
                    check=True,
                    env=process_env,
                )
                hooks = repo / ".no-hooks"
                hooks.mkdir()
                subprocess.run(
                    ["git", "-C", str(repo), "config", "core.hooksPath", str(hooks)],
                    check=True,
                    env=process_env,
                )
                subprocess.run(
                    ["git", "-C", str(repo), "add", "."],
                    check=True,
                    env=process_env,
                )
                subprocess.run(
                    ["git", "-C", str(repo), "commit", "-q", "-m", "fixture"],
                    check=True,
                    env=process_env,
                )
                if index == 2:
                    note = repo / "unrelated-governance-note.txt"
                    note.write_text("unrelated\n", encoding="ascii", newline="\n")
                    subprocess.run(
                        ["git", "-C", str(repo), "add", note.name],
                        check=True,
                        env=process_env,
                    )
                    subprocess.run(
                        ["git", "-C", str(repo), "commit", "-q", "-m", "unrelated"],
                        check=True,
                        env=process_env,
                    )
                sample = repo / "USER" / "sample.c"
                stat = sample.stat()
                os.utime(sample, (stat.st_atime, stat.st_mtime + (index * 60)))
                mtimes.append(sample.stat().st_mtime_ns)
                output = repo / "manifest-output"
                result = subprocess.run(
                    [
                        POWERSHELL,
                        "-NoProfile",
                        "-ExecutionPolicy",
                        "Bypass",
                        "-File",
                        str(MANIFEST),
                        "-RepoRoot",
                        str(repo),
                        "-OutputDirectory",
                        str(output),
                        "-Profile",
                        "Production",
                    ],
                    cwd=repo,
                    env=process_env,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(0, result.returncode, result.stderr)
                outputs.append(
                    (
                        (output / "source-manifest.txt").read_bytes(),
                        (output / "source-manifest.json").read_bytes(),
                    )
                )
                summaries.append(json.loads((output / "summary.json").read_text(encoding="utf-8")))

            self.assertEqual(outputs[0], outputs[1])
            self.assertNotEqual(mtimes[0], mtimes[1])
            self.assertNotEqual(summaries[0]["RepoRoot"], summaries[1]["RepoRoot"])
            self.assertNotEqual(summaries[0]["Head"], summaries[1]["Head"])
            self.assertEqual(summaries[0]["ManifestSHA256"], summaries[1]["ManifestSHA256"])

if __name__ == "__main__":
    unittest.main()
