#!/usr/bin/env python3
"""Host regression for the Flutter development entry; never runs Flutter."""

import ctypes
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import signal
import stat
import subprocess
import sys
import time
from types import SimpleNamespace
import unittest
from unittest import mock
import uuid


sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "flutter_dev_checks", ROOT / "Tools/flutter/dev_checks.py"
)
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)


def process_running(pid):
    if os.name == "nt":
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
        kernel.OpenProcess.restype = ctypes.c_void_p
        kernel.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        kernel.WaitForSingleObject.restype = ctypes.c_uint32
        kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        handle = kernel.OpenProcess(0x100000, False, pid)
        if not handle:
            if ctypes.get_last_error() == 87:
                return False
            raise OSError(ctypes.get_last_error(), "Cannot inspect owned child process")
        try:
            state = kernel.WaitForSingleObject(handle, 0)
            if state not in (0, 258):
                raise OSError(f"Unexpected process wait result: {state}")
            return state == 258
        finally:
            kernel.CloseHandle(handle)
    try:
        os.kill(pid, 0)
        proc_stat = Path(f"/proc/{pid}/stat")
        if proc_stat.exists() and proc_stat.read_text().rsplit(")", 1)[1].split()[0] == "Z":
            return False
        return True
    except ProcessLookupError:
        return False


class FlutterDevelopmentChecksTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.output = RUNNER.make_directory(
            ROOT, Path(".cache/flutter-dev-checks-tests") / ("run-" + uuid.uuid4().hex),
            exclusive=True,
        )
        print(f"Host fixtures: {cls.output}", flush=True)

    def setUp(self):
        self.project = RUNNER.make_directory(ROOT, self.output / self._testMethodName)
        self.write(RUNNER.APP / "pubspec.yaml", "name: runner_fixture\n")
        self.write(RUNNER.APP / "pubspec.lock", "fixture-lock\n")
        RUNNER.make_directory(self.project, RUNNER.APP / "test/ota")

    def write(self, relative, content):
        path = RUNNER.checked_path(self.project, relative)
        RUNNER.make_directory(self.project, path.parent)
        with path.open("w", encoding="utf-8", newline="\n") as output:
            output.write(content)
        return path

    def fixture_run(self, outcomes=None, after=None, scope="all", build_apk=False):
        calls = []

        def execute(root, argv, cwd, env, log, timeout):
            name = log.stem
            calls.append(name)
            RUNNER.checked_path(root, log).write_text(
                f"fixture output for {name}\n", encoding="ascii"
            )
            result = {"status": "PASS", "exit_code": 0, "timed_out": False}
            result.update((outcomes or {}).get(name, {}))
            if after:
                after(name)
            return result

        with mock.patch("sys.stdout", new_callable=io.StringIO), \
                mock.patch.dict(os.environ, {"GITHUB_SHA": "1" * 40}):
            code, path = RUNNER.run_checks(
                self.project, scope, build_apk=build_apk, execute=execute,
                identify=lambda root: {
                    "head": "1" * 40, "clean": True, "status": "",
                    "dirty_semantic": [], "dirty_eol_only": [], "fixture": True,
                },
            )
        return code, json.loads(path.read_text(encoding="utf-8")), calls, path

    def command(self, argv, timeout=10, log_name="command.log"):
        work = RUNNER.make_directory(self.project, Path("process"))
        env = RUNNER.contained_environment(self.project, work)
        log = work / log_name
        result = RUNNER.run_command(self.project, argv, self.project, env, log, timeout)
        return result, log

    def test_command_scopes_are_bounded_and_lock_enforced(self):
        for scope, directory in (("all", "test"), ("ota", "test/ota")):
            plan = RUNNER.command_plan(self.project, self.project / "run", scope)
            self.assertEqual(
                ["sdk_checkout", "sdk_version", "dependencies", "analyze", "tests"],
                [item[0] for item in plan],
            )
            self.assertEqual(["pub", "get", "--enforce-lockfile"], plan[2][1][1:])
            self.assertEqual(["analyze", "--no-pub"], plan[3][1][1:])
            self.assertEqual(directory, plan[4][1][-1])
            self.assertIn("--no-pub", plan[4][1])
            self.assertTrue(all(0 < item[3] <= 600 for item in plan))
            for _, argv, _, _ in plan:
                self.assertFalse({"build", "publish", "deploy", "push"}.intersection(argv))

    def test_success_is_development_only_with_all_raw_logs(self):
        code, report, calls, path = self.fixture_run(scope="ota")
        self.assertEqual(0, code)
        self.assertEqual("PASS", report["development_result"])
        self.assertEqual("development-self-test", report["evidence_kind"])
        self.assertEqual("NOT_RUN", report["formal_acceptance"])
        self.assertEqual("ota", report["scope"])
        self.assertEqual(5, len(calls))
        self.assertTrue(report["lockfile_unchanged"])
        for item in report["commands"]:
            self.assertEqual(0, item["exit_code"])
            self.assertTrue((path.parent / item["log"]).is_file())
            self.assertTrue(item["argv"])
            self.assertTrue(Path(item["cwd"]).is_relative_to(self.project))

    def test_analyze_failure_still_collects_tests_and_fails_overall(self):
        code, report, calls, _ = self.fixture_run({
            "analyze": {"status": "FAIL", "exit_code": 23}
        })
        self.assertEqual(1, code)
        self.assertEqual("FAIL", report["development_result"])
        self.assertEqual("tests", calls[-1])
        self.assertEqual(23, report["commands"][3]["exit_code"])
        self.assertEqual("PASS", report["commands"][4]["status"])

    def test_test_failure_is_not_masked(self):
        code, report, _, _ = self.fixture_run({
            "tests": {"status": "FAIL", "exit_code": 7}
        })
        self.assertEqual(1, code)
        self.assertEqual("PASS", report["commands"][3]["status"])
        self.assertEqual(7, report["commands"][4]["exit_code"])

    def test_dependency_failure_leaves_analysis_and_tests_not_run(self):
        code, report, calls, path = self.fixture_run({
            "dependencies": {"status": "FAIL", "exit_code": 65}
        })
        self.assertEqual(1, code)
        self.assertEqual(["sdk_checkout", "sdk_version", "dependencies"], calls)
        for item in report["commands"][3:]:
            self.assertEqual("NOT_RUN", item["status"])
            self.assertIsNone(item["exit_code"])
            self.assertFalse((path.parent / item["log"]).exists())

    def test_sdk_setup_failure_does_not_pretend_checks_executed(self):
        code, report, calls, _ = self.fixture_run({
            "sdk_checkout": {"status": "ERROR", "exit_code": None}
        })
        self.assertEqual(1, code)
        self.assertEqual(["sdk_checkout"], calls)
        self.assertEqual(["NOT_RUN"] * 4, [c["status"] for c in report["commands"][1:]])

    def test_analysis_timeout_is_red_but_cleaned_up_tests_can_run(self):
        code, report, calls, _ = self.fixture_run({
            "analyze": {"status": "TIMEOUT", "timed_out": True, "exit_code": -9,
                        "cleanup_error": None}
        })
        self.assertEqual(1, code)
        self.assertEqual("tests", calls[-1])
        self.assertTrue(report["commands"][3]["timed_out"])

    def test_unproven_process_cleanup_stops_downstream_work(self):
        code, report, calls, _ = self.fixture_run({
            "analyze": {"status": "TIMEOUT", "timed_out": True, "exit_code": -9,
                        "cleanup_error": "child cleanup unproven"}
        })
        self.assertEqual(1, code)
        self.assertNotIn("tests", calls)
        self.assertEqual("NOT_RUN", report["commands"][4]["status"])

    def test_lockfile_drift_fails_before_analysis(self):
        def alter_lock(name):
            if name == "dependencies":
                self.write(RUNNER.APP / "pubspec.lock", "changed-fixture-lock\n")

        code, report, calls, _ = self.fixture_run(after=alter_lock)
        self.assertEqual(1, code)
        self.assertFalse(report["lockfile_unchanged"])
        self.assertEqual("FAIL", report["commands"][2]["status"])
        self.assertNotIn("analyze", calls)

    def test_new_run_preserves_previous_report_and_logs(self):
        _, first_report, _, first = self.fixture_run()
        original = first.read_bytes()
        _, _, _, second = self.fixture_run()
        self.assertNotEqual(first.parent, second.parent)
        self.assertEqual(original, first.read_bytes())
        for item in first_report["commands"]:
            self.assertTrue((first.parent / item["log"]).is_file())

    def test_invalid_scope_fails_before_any_run_output(self):
        with self.assertRaisesRegex(ValueError, "Unknown test scope"):
            RUNNER.run_checks(self.project, "../../escape")
        self.assertFalse((self.project / ".cache").exists())

    def test_missing_lock_does_not_silently_resolve_dependencies(self):
        lock = RUNNER.checked_path(self.project, RUNNER.APP / "pubspec.lock")
        lock.unlink()
        with self.assertRaisesRegex(ValueError, "pubspec.lock"):
            RUNNER.run_checks(self.project, "all")
        self.assertFalse((self.project / ".cache").exists())

    def test_cli_refuses_local_sdk_initialization(self):
        with mock.patch.dict(os.environ, {"GITHUB_ACTIONS": "false"}), \
                mock.patch.object(RUNNER, "run_checks") as run, \
                mock.patch("sys.stderr", new_callable=io.StringIO), \
                self.assertRaises(SystemExit) as stopped:
            RUNNER.main(["--repo-root", str(self.project)])
        self.assertEqual(2, stopped.exception.code)
        run.assert_not_called()
        self.assertFalse((self.project / ".cache").exists())

    def test_cli_rejects_mismatched_workspace(self):
        with mock.patch.dict(os.environ, {
            "GITHUB_ACTIONS": "true", "GITHUB_WORKSPACE": str(ROOT)
        }), mock.patch("sys.stderr", new_callable=io.StringIO), \
                self.assertRaises(SystemExit):
            RUNNER.main(["--repo-root", str(self.project)])
        self.assertFalse((self.project / ".cache").exists())

    def test_invalid_scope_from_environment_is_not_a_shell_argument(self):
        with mock.patch.dict(os.environ, {
            "GITHUB_ACTIONS": "true", "GITHUB_WORKSPACE": str(self.project),
            "GITHUB_REF": "refs/heads/dev/flutter/test-fixture",
            "FLUTTER_DEV_TEST_SCOPE": "all & unexpected-command"
        }), mock.patch("sys.stderr", new_callable=io.StringIO):
            self.assertEqual(1, RUNNER.main(["--repo-root", str(self.project)]))
        self.assertFalse((self.project / ".cache").exists())

    def test_boundary_rejects_parent_escape_and_sibling_prefix(self):
        for candidate in (Path("../escape"), Path(str(self.project) + "-sibling/log")):
            with self.subTest(candidate=candidate), self.assertRaisesRegex(
                ValueError, "outside the project root"
            ):
                RUNNER.make_directory(self.project, candidate)
            self.assertFalse(Path(os.path.abspath(self.project / candidate)).exists())

    def test_boundary_checks_nonexistent_leaf_and_all_existing_parents(self):
        marked = RUNNER.make_directory(self.project, Path("marked"))
        real_lstat = Path.lstat

        def lstat(path, *args, **kwargs):
            if path == marked:
                return SimpleNamespace(st_mode=stat.S_IFDIR, st_nlink=1,
                                       st_file_attributes=0x400)
            return real_lstat(path, *args, **kwargs)

        with mock.patch.object(Path, "lstat", lstat), \
                self.assertRaisesRegex(ValueError, "Link/reparse"):
            RUNNER.make_directory(self.project, marked / "missing/logs")
        self.assertFalse((marked / "missing").exists())

    def test_real_link_or_junction_is_rejected_as_leaf_ancestor_and_root(self):
        target = RUNNER.make_directory(self.project, Path("target"))
        original = self.write(Path("target/original.txt"), "preserved\n")
        link = RUNNER.checked_path(self.project, Path("link"))
        if os.name == "nt":
            subprocess.run(
                [str(Path(os.environ["SystemRoot"]) / "System32/cmd.exe"),
                 "/d", "/c", "mklink", "/J", str(link), str(target)],
                cwd=ROOT, check=True, capture_output=True,
                creationflags=subprocess.CREATE_NO_WINDOW, timeout=10,
            )
        else:
            link.symlink_to(target, target_is_directory=True)
        try:
            for root, candidate in ((self.project, link),
                                    (self.project, link / "nested/new.txt"),
                                    (link, Path("new.txt"))):
                with self.subTest(candidate=candidate), self.assertRaisesRegex(
                    ValueError, "Link/reparse"
                ):
                    RUNNER.checked_path(root, candidate)
            self.assertFalse((target / "nested").exists())
            self.assertEqual("preserved\n", original.read_text())
        finally:
            # Remove only this test-owned link, never recurse into its target.
            self.assertEqual(target.resolve(), link.resolve())
            self.assertTrue(target.resolve().is_relative_to(ROOT))
            if os.name == "nt":
                os.rmdir(link)
            else:
                link.unlink()

    def test_environment_contains_standard_sdk_cache_home_and_temp_outputs(self):
        original = dict(os.environ)
        run = RUNNER.make_directory(self.project, Path("env"))
        env = RUNNER.contained_environment(self.project, run)
        for name in ("HOME", "USERPROFILE", "APPDATA", "LOCALAPPDATA", "PUB_CACHE",
                     "XDG_CONFIG_HOME", "XDG_CACHE_HOME", "GRADLE_USER_HOME",
                     "TEMP", "TMP", "TMPDIR", "GIT_CONFIG_GLOBAL"):
            self.assertTrue(Path(env[name]).is_relative_to(run), name)
        self.assertEqual(original, dict(os.environ))
        self.assertEqual("0", env["GIT_TERMINAL_PROMPT"])

    def test_real_process_preserves_stdout_stderr_and_exit_code(self):
        result, log = self.command([
            sys.executable, "-B", "-c",
            "import sys; print('stdout-marker'); "
            "print('stderr-marker', file=sys.stderr); sys.exit(7)",
        ])
        self.assertEqual("FAIL", result["status"])
        self.assertEqual(7, result["exit_code"])
        self.assertFalse(result["timed_out"])
        output = log.read_text(encoding="utf-8")
        self.assertIn("stdout-marker", output)
        self.assertIn("stderr-marker", output)

    def test_missing_executable_is_error_not_pass(self):
        result, log = self.command([str(self.project / "no-such-executable")])
        self.assertEqual("ERROR", result["status"])
        self.assertIsNone(result["exit_code"])
        self.assertTrue(log.read_bytes())

    def test_existing_log_cannot_be_overwritten(self):
        log = self.write(Path("process/command.log"), "original\n")
        with self.assertRaises(FileExistsError):
            self.command([sys.executable, "-B", "-c", "raise RuntimeError()"])
        self.assertEqual("original\n", log.read_text())

    def test_real_timeout_terminates_parent_and_child_without_hanging(self):
        result, log = self.command([
            sys.executable, "-B", "-c",
            "import subprocess,sys,time; "
            "child=subprocess.Popen([sys.executable,'-B','-c',"
            "'import time; time.sleep(60)']); "
            "print('CHILD='+str(child.pid),flush=True); time.sleep(60)",
        ], timeout=3)
        # taskkill appends native-codepage bytes; the raw log must stay untouched.
        match = re.search(rb"^CHILD=(\d+)\r?$", log.read_bytes(), re.MULTILINE)
        self.assertIsNotNone(match, "The timeout fixture never reached child creation")
        child_pid = int(match.group(1))
        try:
            self.assertEqual("TIMEOUT", result["status"])
            self.assertTrue(result["timed_out"])
            self.assertIsNotNone(result["exit_code"])
            self.assertIsNone(result.get("cleanup_error"))
            deadline = time.monotonic() + 2
            while process_running(child_pid) and time.monotonic() < deadline:
                time.sleep(0.05)
            self.assertFalse(process_running(child_pid), "Timed-out child survived")
        finally:
            if process_running(child_pid):
                if os.name == "nt":
                    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
                    kernel.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
                    kernel.OpenProcess.restype = ctypes.c_void_p
                    kernel.TerminateProcess.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
                    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
                    handle = kernel.OpenProcess(1, False, child_pid)
                    if not handle:
                        raise ctypes.WinError(ctypes.get_last_error())
                    try:
                        if not kernel.TerminateProcess(handle, 1):
                            raise ctypes.WinError(ctypes.get_last_error())
                    finally:
                        kernel.CloseHandle(handle)
                else:
                    os.kill(child_pid, signal.SIGKILL)

    def test_windows_batch_quoting_and_exit_propagation(self):
        if os.name != "nt":
            argv = ["/sdk/bin/flutter", "test", "test/ota"]
            self.assertEqual(argv, RUNNER.platform_command(argv))
            return
        batch = self.write(Path("space dir/probe.bat"),
                           "@echo off\necho %~1\nexit /b 23\n")
        result, log = self.command([str(batch), "argument with spaces"])
        self.assertEqual(23, result["exit_code"])
        self.assertEqual("FAIL", result["status"])
        self.assertIn("argument with spaces", log.read_text())
        with self.assertRaisesRegex(ValueError, "Unsafe character"):
            RUNNER.platform_command([str(batch), "all & injected"])

    def test_windows_job_assignment_failure_never_starts_the_command(self):
        if os.name != "nt":
            self.assertEqual("posix", os.name)
            return
        marker = RUNNER.checked_path(self.project, Path("must-not-exist.txt"))
        with mock.patch.object(RUNNER.WindowsJob, "assign", side_effect=OSError("denied")):
            result, _ = self.command([
                sys.executable, "-B", "-c",
                f"from pathlib import Path; Path({str(marker)!r}).write_text('unsafe')",
            ])
        self.assertEqual("ERROR", result["status"])
        self.assertFalse(marker.exists())

    def test_workflow_is_development_only_and_covers_both_hosts(self):
        # workflow 含中文注释，必须显式 UTF-8 读取（Windows 默认 GBK 解码失败）。
        text = (ROOT / ".github/workflows/flutter-dev-checks.yml").read_text(
            encoding="utf-8")
        self.assertIn('branches:\n      - "dev/flutter/**"\n', text)
        self.assertNotIn("\n    paths:", text)
        self.assertIn("permissions:\n  contents: read\n", text)
        self.assertIn("persist-credentials: false", text)
        self.assertIn("fail-fast: false", text)
        self.assertIn("os: ubuntu-latest\n            shell: bash", text)
        self.assertIn("os: windows-2022\n            shell: cmd", text)
        # steps.shell 不接受任何 context（GitHub 解析器拒绝 matrix）；
        # matrix shell 必须经 job 级 defaults.run.shell 注入。
        self.assertIn("defaults:\n      run:\n        shell: ${{ matrix.shell }}", text)
        self.assertNotIn("steps:", text[:text.index("defaults:")])
        self.assertIn("timeout-minutes: 90", text)
        self.assertIn("options:\n          - all\n          - ota", text)
        self.assertIn("python -B Tools/flutter/dev_checks.py --repo-root .", text)
        self.assertIn("python -B tests/ota/test_flutter_dev_checks.py", text)
        self.assertIn("python -B tests/ota/test_flutter_dev_apk.py", text)
        self.assertIn("build_apk:", text)
        self.assertIn("refs/heads/dev/flutter/apk/", text)
        self.assertIn("trace-dev-debug.apk", text)
        self.assertIn("if: always()", text)
        self.assertIn("include-hidden-files: true", text)
        self.assertIn("if-no-files-found: error", text)
        for forbidden in ("secrets.", "contents: write", "pages: write", "id-token:",
                          "continue-on-error", "flutter build", "wrangler", "pwsh",
                          "pull_request_target:", "publish_release", "git push"):
            self.assertNotIn(forbidden, text)

    def test_runner_workflow_and_docs_have_profile_and_ci_ownership(self):
        profiles = json.loads((ROOT / "Tools/provenance/manifest_profiles.json").read_text())[
            "profiles"
        ]
        validation = profiles["Validation"]
        self.assertIn("Tools/", validation["root_patterns"])
        self.assertIn("tests/", validation["root_patterns"])
        self.assertIn(".github/workflows/flutter-dev-checks.yml", validation["top_files"])
        self.assertIn("docs/flutter-development-validation.md",
                      profiles["Governance"]["top_files"])
        workflow = (ROOT / ".github/workflows/acceptance-governance.yml").read_text(
            encoding="utf-8"
        )
        for path in ("Tools/flutter/**", "tests/ota/test_flutter_dev_checks.py",
                     "docs/flutter-development-validation.md",
                     ".github/workflows/flutter-dev-checks.yml", ".github/workflows/build.yml"):
            self.assertEqual(2, workflow.count(f'      - "{path}"'), path)
        self.assertIn("python3 -B tests/ota/test_flutter_dev_checks.py", workflow)

    def test_release_build_does_not_mask_analysis_failures(self):
        workflow = (ROOT / ".github/workflows/build.yml").read_text(encoding="utf-8")
        steps = re.findall(
            r"^      - name: Analyze project\n(.*?)(?=^      - name:|\Z)",
            workflow, re.MULTILINE | re.DOTALL,
        )
        self.assertEqual(2, len(steps))
        for step in steps:
            self.assertIn("run: flutter analyze", step)
            self.assertNotIn("continue-on-error", step)
            self.assertNotIn("--no-fatal", step)

    def test_cli_rejects_non_validation_branches(self):
        for ref in ("refs/heads/main", "refs/heads/master", "refs/tags/v1.0.0", "refs/heads/feature/demo"):
            with self.subTest(ref=ref), mock.patch.dict(os.environ, {
                "GITHUB_ACTIONS": "true", "GITHUB_WORKSPACE": str(self.project), "GITHUB_REF": ref
            }), mock.patch.object(RUNNER, "run_checks") as run, \
                    mock.patch("sys.stderr", new_callable=io.StringIO), self.assertRaises(SystemExit):
                RUNNER.main(["--repo-root", str(self.project)])
            run.assert_not_called()

    def apk_inputs(self):
        self.write(RUNNER.APP / "android/app/build.gradle.kts", "compileSdk = 35\n")
        self.write(RUNNER.APP / "android/gradle/wrapper/gradle-wrapper.properties",
                   "distributionUrl=https\\://services.gradle.org/distributions/gradle-8.12-all.zip\n")

    def test_apk_requires_full_scope_and_linux(self):
        self.apk_inputs()
        with mock.patch.object(sys, "platform", "linux"), self.assertRaisesRegex(ValueError, "full all"):
            RUNNER.run_checks(self.project, "ota", build_apk=True)
        with mock.patch.object(sys, "platform", "win32"), self.assertRaisesRegex(ValueError, "Linux"):
            RUNNER.run_checks(self.project, "all", build_apk=True)
        self.assertFalse((self.project / ".cache").exists())

    def test_analysis_failure_collects_tests_but_never_builds_apk(self):
        self.apk_inputs()
        with mock.patch.object(sys, "platform", "linux"):
            code, report, calls, _ = self.fixture_run({
                "analyze": {"status": "FAIL", "exit_code": 1}
            }, build_apk=True)
        self.assertEqual(1, code)
        self.assertIn("tests", calls)
        self.assertFalse(any(name.startswith("apk_") for name in calls))
        self.assertEqual("NOT_RUN", report["apk_result"])

    def test_test_failure_prevents_apk_and_success_preserves_phase_order(self):
        self.apk_inputs()
        with mock.patch.object(sys, "platform", "linux"):
            code, report, calls, _ = self.fixture_run({
                "tests": {"status": "FAIL", "exit_code": 1}
            }, build_apk=True)
            self.assertEqual(1, code)
            self.assertNotIn("apk_prepare", calls)
            self.assertEqual("NOT_RUN", report["apk_result"])
            code, report, calls, _ = self.fixture_run(build_apk=True)
        self.assertEqual(0, code)
        self.assertEqual("PASS", report["apk_result"])
        self.assertLess(calls.index("tests"), calls.index("apk_prepare"))
        self.assertLess(calls.index("apk_build"), calls.index("apk_verify"))
        self.assertLess(calls.index("apk_verify"), calls.index("apk_collect"))

    def test_apk_failure_propagates_and_does_not_collect_an_artifact(self):
        self.apk_inputs()
        with mock.patch.object(sys, "platform", "linux"):
            code, report, calls, _ = self.fixture_run({
                "apk_build": {"status": "FAIL", "exit_code": 1}
            }, build_apk=True)
        self.assertEqual(1, code)
        self.assertEqual("FAIL", report["apk_result"])
        self.assertNotIn("apk_verify", calls)
        self.assertNotIn("apk_collect", calls)

    def test_standing_authorization_is_not_a_mainline_or_release_grant(self):
        guide = (ROOT / "docs/flutter-development-validation.md").read_text(encoding="utf-8")
        app_rules = (ROOT / "app/bluetooth_flutter_Trace/AGENTS.md").read_text(encoding="utf-8")
        contract = (ROOT / "docs/acceptance-execution-contract.md").read_text(encoding="utf-8")
        board = (ROOT / "PLAN-OTA-EXEC.md").read_text(encoding="utf-8")
        self.assertIn("### Standing Authorization", guide)
        self.assertIn("No repeated", guide)
        self.assertIn("No force-push", guide)
        self.assertIn("exclusively owned", app_rules)
        self.assertNotIn("Only the root session may commit/push", app_rules)
        self.assertIn("7.3.2", contract)
        self.assertIn("\u65e0\u9700\u9010\u6279\u91cd\u590d\u7533\u8bf7", board.split("## 1.", 1)[0])


if __name__ == "__main__":
    unittest.main(verbosity=2)
