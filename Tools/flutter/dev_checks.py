#!/usr/bin/env python3
"""Bounded Flutter CI self-tests. This is not an acceptance-bundle runner."""

import argparse
import ctypes
from ctypes import wintypes
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import signal
import stat
import subprocess
import sys
import time
import uuid


sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
APP = Path("app/bluetooth_flutter_Trace")
SCOPES = {"all": "test", "ota": "test/ota"}
SDK_URL = "https://github.com/flutter/flutter.git"
WINDOWS_LAUNCHER = (
    "import json,subprocess,sys; "
    "command=json.loads(sys.stdin.readline()); "
    "sys.exit(subprocess.call(command,stdin=subprocess.DEVNULL))"
)


class WindowsJob:
    """Own one command tree without process enumeration or taskkill permissions."""

    def __init__(self):
        class BasicLimits(ctypes.Structure):
            _fields_ = [
                ("process_time", ctypes.c_int64), ("job_time", ctypes.c_int64),
                ("flags", wintypes.DWORD), ("min_working_set", ctypes.c_size_t),
                ("max_working_set", ctypes.c_size_t), ("process_limit", wintypes.DWORD),
                ("affinity", ctypes.c_size_t), ("priority", wintypes.DWORD),
                ("scheduling", wintypes.DWORD),
            ]

        class ExtendedLimits(ctypes.Structure):
            _fields_ = [
                ("basic", BasicLimits), ("io_counters", ctypes.c_uint64 * 6),
                ("process_memory", ctypes.c_size_t), ("job_memory", ctypes.c_size_t),
                ("peak_process_memory", ctypes.c_size_t), ("peak_job_memory", ctypes.c_size_t),
            ]

        class Accounting(ctypes.Structure):
            _fields_ = [
                ("times", ctypes.c_int64 * 4), ("page_faults", wintypes.DWORD),
                ("total_processes", wintypes.DWORD), ("active_processes", wintypes.DWORD),
                ("terminated_processes", wintypes.DWORD),
            ]

        self.accounting_type = Accounting
        self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        signatures = {
            "CreateJobObjectW": ([ctypes.c_void_p, wintypes.LPCWSTR], wintypes.HANDLE),
            "SetInformationJobObject": (
                [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD], wintypes.BOOL
            ),
            "AssignProcessToJobObject": ([wintypes.HANDLE, wintypes.HANDLE], wintypes.BOOL),
            "TerminateJobObject": ([wintypes.HANDLE, wintypes.UINT], wintypes.BOOL),
            "QueryInformationJobObject": (
                [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD,
                 ctypes.c_void_p], wintypes.BOOL
            ),
            "CloseHandle": ([wintypes.HANDLE], wintypes.BOOL),
        }
        for name, (arguments, result) in signatures.items():
            function = getattr(self.kernel, name)
            function.argtypes = arguments
            function.restype = result
        self.handle = self.kernel.CreateJobObjectW(None, None)
        if not self.handle:
            raise ctypes.WinError(ctypes.get_last_error())
        limits = ExtendedLimits()
        limits.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not self.kernel.SetInformationJobObject(
            self.handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)
        ):
            error = ctypes.WinError(ctypes.get_last_error())
            self.close()
            raise error

    def assign(self, process):
        # Popen retains the owned process handle on Windows. The launcher cannot
        # create a child until we send its command after this assignment.
        if not self.kernel.AssignProcessToJobObject(self.handle, int(process._handle)):
            raise ctypes.WinError(ctypes.get_last_error())

    def terminate(self):
        if not self.kernel.TerminateJobObject(self.handle, 1):
            raise ctypes.WinError(ctypes.get_last_error())
        deadline = time.monotonic() + 10
        while True:
            accounting = self.accounting_type()
            if not self.kernel.QueryInformationJobObject(
                self.handle, 1, ctypes.byref(accounting), ctypes.sizeof(accounting), None
            ):
                raise ctypes.WinError(ctypes.get_last_error())
            if accounting.active_processes == 0:
                return
            if time.monotonic() >= deadline:
                raise OSError("Owned Windows job still has active processes")
            time.sleep(0.025)

    def close(self):
        if self.handle:
            self.kernel.CloseHandle(self.handle)
            self.handle = None


def checked_path(root, path):
    """Reject escapes and existing link/reparse ancestors before any write."""
    root = Path(os.path.abspath(root))
    path = Path(os.path.abspath(root / path))
    if not path.is_relative_to(root):
        raise ValueError(f"Output is outside the project root: {path}")
    for parent in reversed((path, *path.parents)):
        try:
            info = parent.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or (
            getattr(info, "st_file_attributes", 0)
            & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
        ):
            raise ValueError(f"Link/reparse path is not an allowed output: {parent}")
        # NTFS mounts are covered by the reparse attribute above.
        if os.name != "nt" and parent != Path(parent.anchor) and os.path.ismount(parent):
            raise ValueError(f"Mounted output path requires separate review: {parent}")
        if stat.S_ISREG(info.st_mode) and info.st_nlink > 1:
            raise ValueError(f"Hard-linked output requires separate review: {parent}")
    if not root.is_dir():
        raise ValueError(f"Project root is not an existing directory: {root}")
    return path


def make_directory(root, path, *, exclusive=False):
    path = checked_path(root, path)
    path.mkdir(parents=True, exist_ok=not exclusive)
    return checked_path(root, path)


def contained_environment(root, run_dir):
    env = os.environ.copy()
    directories = {
        "HOME": run_dir / "home",
        "USERPROFILE": run_dir / "home",
        "APPDATA": run_dir / "home/AppData/Roaming",
        "LOCALAPPDATA": run_dir / "home/AppData/Local",
        "XDG_CONFIG_HOME": run_dir / "home/.config",
        "XDG_CACHE_HOME": run_dir / "cache",
        "PUB_CACHE": run_dir / "pub-cache",
        "GRADLE_USER_HOME": run_dir / "gradle",
        "TEMP": run_dir / "tmp",
        "TMP": run_dir / "tmp",
        "TMPDIR": run_dir / "tmp",
    }
    for name, path in directories.items():
        env[name] = str(make_directory(root, path))
    env.update({
        "CI": "true",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONUTF8": "1",
        "FLUTTER_SUPPRESS_ANALYTICS": "true",
        "DART_SUPPRESS_ANALYTICS": "true",
        "PUB_ENVIRONMENT": "github_actions",
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_CONFIG_GLOBAL": str(checked_path(root, run_dir / "home/.gitconfig")),
    })
    return env


def platform_command(argv):
    if os.name != "nt" or Path(argv[0]).suffix.lower() not in (".bat", ".cmd"):
        return argv
    # cmd.exe does not implement the C argv quoting rules used by Popen lists.
    # Only fixed Flutter options and a checked path reach this batch boundary.
    if any(any(char in arg for char in '%!"\r\n&|<>^') for arg in argv):
        raise ValueError("Unsafe character in Windows batch command")
    comspec = str(Path(os.environ["SystemRoot"]) / "System32/cmd.exe")
    quoted = " ".join(f'"{arg}"' for arg in argv)
    return f'"{comspec}" /d /s /c "{quoted}"'


def stop_process_tree(process, job=None):
    error = None
    try:
        if os.name == "nt":
            if job is None:
                raise OSError("Missing Windows command job")
            job.terminate()
        else:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        process.wait(timeout=10)
    except (OSError, subprocess.TimeoutExpired) as exc:
        error = f"Process-tree cleanup failed: {exc}"
        try:
            process.kill()
            process.wait(timeout=5)
        except (OSError, subprocess.TimeoutExpired):
            pass
    return error


def run_command(root, argv, cwd, env, log_path, timeout):
    log_path = checked_path(root, log_path)
    started = time.monotonic()
    result = {"status": "ERROR", "exit_code": None, "timed_out": False}
    with log_path.open("xb") as log:
        process = None
        job = None
        assigned = False
        try:
            launch = platform_command(argv)
            result["launch"] = launch
            if os.name == "nt":
                if shutil.which(argv[0], path=env.get("PATH")) is None:
                    raise FileNotFoundError(f"Executable not found: {argv[0]}")
                job = WindowsJob()
                process = subprocess.Popen(
                    [sys.executable, "-B", "-c", WINDOWS_LAUNCHER],
                    cwd=cwd, env=env, stdin=subprocess.PIPE,
                    stdout=log, stderr=subprocess.STDOUT,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
                job.assign(process)
                assigned = True
                process.stdin.write((json.dumps(launch) + "\n").encode("ascii"))
                process.stdin.close()
            else:
                process = subprocess.Popen(
                    launch, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                    stdout=log, stderr=subprocess.STDOUT, start_new_session=True,
                )
            result["pid"] = process.pid
            try:
                process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                result["timed_out"] = True
                result["cleanup_error"] = stop_process_tree(process, job)
            result["exit_code"] = process.returncode
            result["status"] = (
                "TIMEOUT" if result["timed_out"] else
                "PASS" if process.returncode == 0 else "FAIL"
            )
            if job is not None and not result["timed_out"]:
                job.terminate()
        except (OSError, ValueError) as exc:
            result["status"] = "ERROR"
            result["error"] = str(exc)
            log.write((str(exc) + "\n").encode("utf-8"))
            if process is not None:
                if job is not None and not assigned:
                    # The launcher is still waiting for stdin and has no child.
                    process.kill()
                    process.wait(timeout=5)
                else:
                    result["cleanup_error"] = stop_process_tree(process, job)
                result["exit_code"] = process.returncode
        finally:
            try:
                if process is not None and process.stdin is not None and not process.stdin.closed:
                    process.stdin.close()
            finally:
                if job is not None:
                    job.close()
    result["elapsed_seconds"] = round(time.monotonic() - started, 3)
    return result


def checkout_identity(root):
    def git(*args):
        return subprocess.run(
            ["git", "--no-optional-locks", "-C", str(root), *args],
            cwd=root, capture_output=True, text=True, encoding="utf-8",
            errors="replace", check=True, timeout=15,
        ).stdout.strip()

    toplevel = Path(os.path.abspath(git("rev-parse", "--show-toplevel")))
    if toplevel != root:
        raise ValueError(f"Expected Git root {root}, got {toplevel}")
    status = git("status", "--porcelain=v1", "--untracked-files=normal")
    return {"head": git("rev-parse", "HEAD"), "clean": not status, "status": status}


def command_plan(root, run_dir, scope, *, build_apk=False, env=None):
    if scope not in SCOPES:
        raise ValueError(f"Unknown test scope: {scope}")
    sdk = checked_path(root, run_dir / "sdk")
    flutter = str(sdk / ("bin/flutter.bat" if os.name == "nt" else "bin/flutter"))
    app = checked_path(root, root / APP)
    commands = [
        ("sdk_checkout", ["git", "clone", "--config", "core.longpaths=true",
                          "--depth", "1", "--branch", "stable",
                          SDK_URL, str(sdk)], root, 180),
        ("sdk_version", [flutter, "--version", "--machine"], app, 300),
        ("dependencies", [flutter, "pub", "get", "--enforce-lockfile"], app, 300),
        ("analyze", [flutter, "analyze", "--no-pub"], app, 300),
        ("tests", [flutter, "test", "--no-pub", "--reporter", "expanded",
                   "--timeout", "2m", SCOPES[scope]], app, 600),
    ]
    if build_apk:
        if scope != "all" or sys.platform != "linux":
            raise ValueError("APK mode requires Linux and the full all test scope")
        from Tools.flutter import dev_apk
        commands.extend(dev_apk.plan(root, run_dir, env or {}))
    return commands


def file_hash(path):
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except FileNotFoundError:
        return None


def save_report(root, path, report):
    with checked_path(root, path).open("w", encoding="utf-8", newline="\n") as output:
        output.write(json.dumps(report, indent=2, ensure_ascii=True) + "\n")


def run_checks(root, scope, *, build_apk=False, execute=run_command, identify=checkout_identity):
    root = checked_path(root, Path("."))
    if scope not in SCOPES:
        raise ValueError(f"Unknown test scope: {scope}")
    if build_apk and (scope != "all" or sys.platform != "linux"):
        raise ValueError("APK mode requires Linux and the full all test scope")
    app = checked_path(root, root / APP)
    if not (app / "pubspec.yaml").is_file() or not (app / SCOPES[scope]).is_dir():
        raise ValueError("Flutter package or selected test directory is missing")
    lockfile = checked_path(root, app / "pubspec.lock")
    lock_before = file_hash(lockfile)
    if lock_before is None:
        raise ValueError("A committed pubspec.lock is required; do not resolve a new lock")
    source = identify(root)
    for relative in (".dart_tool", "build", ".flutter-plugins",
                     ".flutter-plugins-dependencies", "windows/flutter/ephemeral",
                     "linux/flutter/ephemeral", "macos/Flutter/ephemeral"):
        checked_path(root, app / relative)
    run_dir = make_directory(
        root, Path(".cache/flutter-dev-checks/runs") / ("run-" + uuid.uuid4().hex),
        exclusive=True,
    )
    logs = make_directory(root, run_dir / "logs")
    env = contained_environment(root, run_dir)
    apk_env = env
    if build_apk:
        from Tools.flutter import dev_apk
        apk_env = dev_apk.environment(root, run_dir, env)
    report_path = run_dir / "result.json"
    report = {
        "schema": "etrack-flutter-dev-checks-v1",
        "evidence_kind": "development-self-test",
        "formal_acceptance": "NOT_RUN",
        "development_result": "NOT_RUN",
        "scope": scope,
        "apk_requested": build_apk,
        "apk_result": "NOT_RUN" if build_apk else "NOT_REQUESTED",
        "source_before": source,
        "host": platform.platform(),
        "python": sys.version,
        "sdk_channel": "stable",
        "github_run_url": (
            f"{os.environ.get('GITHUB_SERVER_URL', 'https://github.com')}/"
            f"{os.environ.get('GITHUB_REPOSITORY', '')}/actions/runs/"
            f"{os.environ.get('GITHUB_RUN_ID', '')}"
        ),
        "github_run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
        "lock_sha256_before": lock_before,
        "commands": [
            {"name": name, "argv": argv, "cwd": str(cwd),
             "timeout_seconds": timeout, "status": "NOT_RUN", "exit_code": None,
             "log": str(Path("logs") / (name + ".log"))}
            for name, argv, cwd, timeout in command_plan(
                root, run_dir, scope, build_apk=build_apk, env=apk_env
            )
        ],
    }
    save_report(root, report_path, report)
    blocked = None
    for command in report["commands"]:
        name = command["name"]
        if name == "apk_prepare" and not blocked:
            if any(item["status"] != "PASS" for item in report["commands"][:5]):
                blocked = "APK generation requires both analysis and full tests to pass"
            elif not source["clean"] or identify(root) != source:
                blocked = "APK generation requires the unchanged, committed checkout tested above"
            elif source["head"] != os.environ.get("GITHUB_SHA"):
                blocked = "APK generation requires the tested commit to match GITHUB_SHA"
        if blocked:
            command["reason"] = blocked
        else:
            print(f"Running {name}; log: {logs / (name + '.log')}", flush=True)
            command.update(execute(
                root, command["argv"], Path(command["cwd"]),
                apk_env if name.startswith("apk_") else env,
                logs / (name + ".log"), command["timeout_seconds"],
            ))
            if name == "dependencies" and file_hash(lockfile) != lock_before:
                command["status"] = "FAIL"
                command["error"] = "Dependency resolution changed the lockfile"
            if command.get("cleanup_error"):
                blocked = command["cleanup_error"]
            elif command["status"] != "PASS" and name != "analyze":
                blocked = f"Prerequisite {name} did not pass"
        save_report(root, report_path, report)
    report["lock_sha256_after"] = file_hash(lockfile)
    report["lockfile_unchanged"] = report["lock_sha256_after"] == lock_before
    report["source_after"] = identify(root)
    report["source_unchanged"] = report["source_after"] == source
    passed = report["lockfile_unchanged"] and all(
        command["status"] == "PASS" for command in report["commands"]
    )
    if build_apk and not report["source_unchanged"]:
        passed = False
        report["error"] = "Source checkout changed during APK generation"
    report["development_result"] = "PASS" if passed else "FAIL"
    if build_apk:
        apk_commands = [item for item in report["commands"] if item["name"].startswith("apk_")]
        report["apk_result"] = (
            "PASS" if all(item["status"] == "PASS" for item in apk_commands) else
            "NOT_RUN" if all(item["status"] == "NOT_RUN" for item in apk_commands) else "FAIL"
        )
        if report["apk_result"] == "PASS":
            report["apk_metadata"] = "artifacts/trace-dev-debug.json"
    save_report(root, report_path, report)
    for command in report["commands"]:
        print(f"{command['name']}: {command['status']} (exit={command['exit_code']})")
    print(f"Development report: {report_path}")
    return (0 if passed else 1), report_path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--scope", choices=SCOPES,
                        default=os.environ.get("FLUTTER_DEV_TEST_SCOPE", "all"))
    parser.add_argument("--build-apk", action="store_true",
                        default=os.environ.get("FLUTTER_DEV_BUILD_APK", "false") == "true")
    args = parser.parse_args(argv)
    # SDK initialization can write and spawn platform tools. Only the explicitly
    # authorized remote workflow uses this entry; host regressions import it.
    if os.environ.get("GITHUB_ACTIONS") != "true":
        parser.error("CI-only entry; use the authorized Flutter Development Checks workflow")
    root = Path(os.path.abspath(args.repo_root))
    workspace = os.environ.get("GITHUB_WORKSPACE")
    if not workspace or Path(os.path.abspath(workspace)) != root:
        parser.error("--repo-root must equal the checked-out GITHUB_WORKSPACE")
    if not os.environ.get("GITHUB_REF", "").startswith("refs/heads/dev/flutter/"):
        parser.error("Development checks are restricted to dev/flutter/** branches")
    if os.environ.get("FLUTTER_DEV_BUILD_APK", "false") not in ("true", "false"):
        parser.error("FLUTTER_DEV_BUILD_APK must be true or false")
    try:
        return run_checks(root, args.scope, build_apk=args.build_apk)[0]
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print(f"Development checks could not complete: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
