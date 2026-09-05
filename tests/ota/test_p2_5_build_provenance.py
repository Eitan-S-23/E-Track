#!/usr/bin/env python3
import ast
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
BOARD = "PLAN-OTA-EXEC.md"
FREEZE_INDEX = "docs/acceptance-contracts/FREEZE-INDEX.md"
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


def git_fixture(repo_root, *arguments):
    """只读 git 调用：统一关掉引号转义，保证非 ASCII 路径不被转义。"""
    result = subprocess.run(
        ["git", "-C", str(repo_root), "-c", "core.quotepath=false", *arguments],
        check=True,
        cwd=ROOT,
        capture_output=True,
    )
    return result.stdout.decode("utf-8").strip()


def init_fixture_repo(repo_root):
    subprocess.run(["git", "init", "-q", str(repo_root)], check=True, cwd=ROOT)
    hooks = repo_root / ".no-hooks"
    hooks.mkdir()
    git_fixture(repo_root, "config", "core.autocrlf", "false")
    git_fixture(repo_root, "config", "core.hooksPath", str(hooks))
    git_fixture(repo_root, "config", "user.name", "fixture")
    git_fixture(repo_root, "config", "user.email", "fixture@example.invalid")


def commit_fixture_repo(repo_root, message):
    git_fixture(repo_root, "add", "-A", ".")
    git_fixture(repo_root, "commit", "-q", "-m", message)


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

    def test_profile_enumeration_protocol_is_explicit(self):
        """v3 起输入组的唯一来源是 git 对象，校验器的调用口径必须显式可查。"""
        text = VALIDATOR_PATH.read_text(encoding="utf-8")
        # 仓库含非 ASCII 路径（Tools/图标/**）：关引号转义 + NUL 分隔缺一不可。
        self.assertIn('"-c", "core.quotepath=false"', text)
        self.assertIn('["ls-tree", "-r", "-z", "--name-only", tree,', text)
        self.assertIn('"diff-tree",', text)
        self.assertIn('"--no-renames",', text)
        self.assertIn('"--no-commit-id",', text)
        # 工作树枚举只保留给治理测试做对照，不参与失效判定。
        self.assertIn('["ls-files", "-co", "--exclude-standard", "-z", "--",', text)
        # 路径集按 UTF-8 字节排序，避免不同 locale 下顺序漂移。
        self.assertIn('sorted(selected, key=lambda path: path.encode("utf-8"))', text)
        self.assertIn("etrack-manifest-profiles-v1", text)
        self.assertIn("manifest_profiles.json", text)
        self.assertIn("profile_config_blob", text)
        self.assertIn("validate_execution_worktree", text)
        self.assertIn('"merge-base", "--is-ancestor"', text)
        # 自研 manifest 生成器已删除，校验器不得再引用它。
        self.assertNotIn("source_manifest.ps1", text)

    def test_manifest_profiles_separate_product_and_validation_inputs(self):
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
        # 看板是每轮收口都要回写的文件，留在 Governance 会让任何一行日志改动
        # 打红全部治理判据，因此必须在 profile 之外。
        self.assertNotIn(BOARD, governance["top_files"])
        self.assertNotIn(BOARD, governance["required_paths"])
        self.assertNotIn(FREEZE_INDEX, governance["top_files"])
        self.assertNotIn(FREEZE_INDEX, governance["required_paths"])
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

    def test_profile_enumeration_separates_product_validation_and_governance(self):
        head_tree = git_fixture(ROOT, "rev-parse", "--verify", "HEAD^{tree}")
        enumerated = {}
        for profile in ("Production", "Validation", "Governance"):
            tree_paths = VALIDATOR._profile_tree_paths(ROOT, head_tree, profile)
            self.assertTrue(tree_paths, profile)
            # 这里只断言 git tree 枚举，不比工作树：工作树枚举会看见未跟踪文件，
            # 属于环境状态。tree 与干净工作树逐路径一致由
            # tests/ota/test_acceptance_bundle.py 的 fixture 仓库用例保证。
            self.assertTrue(
                VALIDATOR.PROFILE_REQUIRED_PATHS[profile].issubset(set(tree_paths)), profile
            )
            enumerated[profile] = set(tree_paths)

        production = enumerated["Production"]
        self.assertIn(".github/workflows/firmware-build.yml", production)
        self.assertIn("Tools/etu_pack.py", production)
        self.assertIn("MDK-ARM_F435/cmake-generated/CMakeLists.txt", production)
        self.assertIn("MDK-ARM_F435/RTE/_X-Track/RTE_Components.h", production)
        self.assertTrue(any(path.startswith("MDK-ARM_F435/RTE/") for path in production))
        # AC5 专用 RTE 与旧 CGU7 目录不是 GCC 输入，混入会让 AC5 改动打红 GCC 判据。
        self.assertFalse(
            any(path.startswith("MDK-ARM_F435/RTE/_X-Track-App-AC5/") for path in production)
        )
        self.assertFalse(
            any(
                path.startswith("MDK-ARM_F435/RTE/Device/-AT32F435CGU7/")
                for path in production
            )
        )
        self.assertNotIn("tests/ota/test_ota_patch.py", production)

        validation = enumerated["Validation"]
        self.assertIn("tests/ota/test_ota_patch.py", validation)
        self.assertIn("Tools/provenance/worktree_guard.ps1", validation)
        self.assertIn("Tools/provenance/manifest_profiles.json", validation)
        # 非 ASCII 路径必须完整出现，证明 core.quotepath=false 与 -z 生效。
        self.assertIn("Tools/\u56fe\u6807/README.md", validation)
        self.assertIn(".github/workflows/acceptance-governance.yml", validation)
        self.assertIn("docs/acceptance-contracts/template.contract.json", validation)
        self.assertIn("docs/acceptance-contracts/template.evidence-matrix.json", validation)
        self.assertNotIn("USER/main.cpp", validation)

        governance = enumerated["Governance"]
        self.assertIn("AGENTS.md", governance)
        self.assertIn("docs/acceptance-execution-contract.md", governance)
        # 看板与冻结点索引都必须留在 profile 之外：它们每轮收口都会被回写。
        self.assertNotIn(BOARD, governance)
        self.assertNotIn(FREEZE_INDEX, governance)
        self.assertNotIn("docs/acceptance-contracts/template.contract.json", governance)

        # Tools/etu_pack.py 是唯一被两个 profile 共享的路径：它既是 OTA 打包器
        # （Production top_files），又落在 Validation 的 Tools/ 根模式下。除它以外
        # 生产源与验收工具必须完全分开，否则改测试会打红产品判据、反之亦然。
        self.assertEqual({"Tools/etu_pack.py"}, production & validation)
        self.assertEqual(set(), production & governance)
        self.assertEqual(set(), validation & governance)

    def test_profile_enumeration_ignores_root_head_and_mtime(self):
        """两个内容相同、根路径/HEAD/mtime 都不同的仓库必须枚举出相同的 Production 路径集。

        这是 v3 失效判定的地基：判据只能被 profile 路径集的 git 内容变化打红，
        绝对路径、提交 id、文件时间戳都不得参与。
        """
        with tempfile.TemporaryDirectory(dir=ROOT, prefix=".manifest-stability-test-") as temp_dir:
            base = Path(temp_dir)
            enumerated = []
            trees = []
            heads = []
            mtimes = []
            for index in (1, 2):
                repo = base / f"repo-{index}"
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
                init_fixture_repo(repo)
                commit_fixture_repo(repo, "fixture")
                if index == 2:
                    # 完全无关的新文件：改变 HEAD 与整棵 tree，但不在任何 profile 里。
                    (repo / "unrelated-governance-note.txt").write_text(
                        "unrelated\n", encoding="ascii", newline="\n"
                    )
                    commit_fixture_repo(repo, "unrelated")
                sample = repo / "USER" / "sample.c"
                stat = sample.stat()
                os.utime(sample, (stat.st_atime, stat.st_mtime + (index * 60)))
                mtimes.append(sample.stat().st_mtime_ns)
                heads.append(git_fixture(repo, "rev-parse", "--verify", "HEAD^{commit}"))
                trees.append(git_fixture(repo, "rev-parse", "--verify", "HEAD^{tree}"))
                enumerated.append(
                    VALIDATOR._profile_tree_paths(repo, trees[-1], "Production")
                )

            self.assertEqual(enumerated[0], enumerated[1])
            self.assertIn("USER/sample.c", enumerated[0])
            self.assertNotIn("unrelated-governance-note.txt", enumerated[1])
            self.assertNotEqual(mtimes[0], mtimes[1])
            self.assertNotEqual(heads[0], heads[1])
            self.assertNotEqual(trees[0], trees[1])

            repo = base / "repo-2"
            first_tree = git_fixture(repo, "rev-parse", "--verify", "HEAD~1^{tree}")
            # 负例的另一半:profile 之外的提交不得让 Production 失效。
            self.assertEqual(
                [],
                VALIDATOR._profile_tree_changes(repo, first_tree, trees[1], "Production"),
            )
            # 正例:真实 Production 输入改一个字节就必须失效。
            (repo / "USER" / "sample.c").write_text(
                "int sample(void) { return 2; }\n", encoding="ascii", newline="\n"
            )
            commit_fixture_repo(repo, "touch a production input")
            changed_tree = git_fixture(repo, "rev-parse", "--verify", "HEAD^{tree}")
            self.assertEqual(
                ["USER/sample.c"],
                VALIDATOR._profile_tree_changes(repo, trees[1], changed_tree, "Production"),
            )

if __name__ == "__main__":
    unittest.main()
