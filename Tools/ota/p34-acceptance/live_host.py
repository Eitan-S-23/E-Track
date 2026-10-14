"""P3-4 standard-tool ownership and receipts, never a Flash/ADB implementation."""
import base64
import csv
from contextlib import contextmanager
import hashlib
import json
import math
import os
import io
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time

import build as host

ROOT = host.ROOT
checked = host.checked
record = host.record
def require(value, message):
    if not value:
        raise RuntimeError(message)


def read_json(path):
    path = Path(path)
    require(path.is_file() and path.stat().st_size <= 8 * 1024 * 1024, "missing/oversized JSON input")
    return json.loads(path.read_text(encoding="utf-8"))


def pinned(item):
    require(isinstance(item, dict) and {"path", "bytes", "sha256"} <= item.keys(), "unbound file")
    path = Path(item["path"])
    path = path if path.is_absolute() else ROOT / path
    require(path.is_file() and path.stat().st_size == item["bytes"] and
            hashlib.sha256(path.read_bytes()).hexdigest() == item["sha256"], "input identity mismatch: " + str(path))
    return path.resolve(strict=True)


def raw(path, data):
    path = checked(path)
    checked(path.parent).mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    return record(path)


def save(path, value):
    return host.io.write_json(ROOT, path, value)


def fresh(path):
    path = checked(path)
    require(not path.exists(), "prior/uncertain action exists; reconcile, do not replay")
    path.mkdir(parents=True)
    return path


def environment(out, vendor_key=None):
    env = host.environment(out)
    for name in ("CC_LOG_FILE", "ADB_TRACE", "ADB_SERVER_SOCKET", "ANDROID_SERIAL", "ANDROID_LOG_TAGS"):
        env.pop(name, None)
    android = checked(out / "host/android")
    android.mkdir(parents=True, exist_ok=True)
    env.update(ANDROID_USER_HOME=str(android), ANDROID_SDK_HOME=str(android.parent))
    if vendor_key:
        env["ADB_VENDOR_KEYS"] = str(pinned(vendor_key))
    else:
        env.pop("ADB_VENDOR_KEYS", None)
    return env


@contextmanager
def device_owner(out, *, read_only=False):
    """One fixed worktree device lock; an uncertain exit keeps its evidence."""
    lock = checked(ROOT / ".cache/p34-live-device.lock")
    value = dict(pid=os.getpid(), out=str(out), monotonic_ns=time.monotonic_ns())
    if lock.exists() and read_only:
        previous = read_json(lock)
        require(type(previous.get("pid")) is int and previous["pid"] > 0, "invalid outstanding owner")
        data = command(out, "previous-owner", ["tasklist", "/FO", "CSV", "/NH", "/FI",
            "PID eq " + str(previous["pid"])], environment(out), seconds=15)
        rows = list(csv.reader(io.StringIO(data.decode("utf-8", "replace"))))
        require(not any(len(row) > 1 and row[1] == str(previous["pid"]) for row in rows),
                "outstanding owner is still running")
        save(out / "unresolved-owner.json", previous)
        yield
        return  # Read-only reconciliation never clears an uncertain mutation.
    save(lock, value)
    try:
        yield
    except BaseException:
        raise
    else:
        require(read_json(lock) == value, "device ownership changed")
        lock.unlink()


LAUNCHER = """import base64,json,subprocess,sys
x=json.loads(sys.stdin.buffer.readline())
data=base64.b64decode(x['stdin']) if x['stdin'] is not None else None
options={'input':data} if data is not None else {'stdin':subprocess.DEVNULL}
p=subprocess.run(x['argv'],**options)
raise SystemExit(p.returncode)
"""


class ObservationReady(RuntimeError):
    """An expendable read yielded to the existing terminal MCU observation."""


class Process:
    """Reuse the existing Windows Job class; preserve split binary stdout/stderr."""
    def __init__(self, out, label, argv, env, *, stdin=None):
        require(label.replace("-", "").replace("_", "").isalnum(), "unsafe command label")
        self.out, self.label = checked(out), label
        self.argv, self.started = list(map(str, argv)), time.monotonic_ns()
        self.paths = {name: checked(self.out / (label + "." + name))
                      for name in ("stdout", "stderr", "started.json", "closed.json")}
        for path in self.paths.values():
            require(not path.exists(), "duplicate command/unknown prior outcome")
        self.out.mkdir(parents=True, exist_ok=True)
        save(self.paths["started.json"], dict(argv=self.argv, cwd=str(ROOT),
            monotonic_ns=self.started, stdin_sha256=hashlib.sha256(stdin).hexdigest() if stdin is not None else None))
        self.streams = []
        self.process, self.job, self.closed = None, None, False
        self.close_attempted, self.close_error = False, None
        try:
            for name in ("stdout", "stderr"):
                self.streams.append(self.paths[name].open("xb"))
            self.job = host.owned.WindowsJob() if os.name == "nt" else None
            options = dict(cwd=ROOT, env=env, stdin=subprocess.PIPE, stdout=self.streams[0], stderr=self.streams[1])
            if os.name == "nt":
                options["creationflags"] = subprocess.CREATE_NO_WINDOW
            else:
                options["start_new_session"] = True
            self.process = subprocess.Popen([sys.executable, "-I", "-S", "-B", "-X", "utf8", "-c", LAUNCHER], **options)
            if self.job:
                self.job.assign(self.process)
            packet = dict(argv=self.argv, stdin=base64.b64encode(stdin).decode("ascii") if stdin is not None else None)
            self.process.stdin.write((json.dumps(packet, ensure_ascii=True) + "\n").encode("ascii"))
            self.process.stdin.close()
        except BaseException as error:
            self._close_after_error("launch_failed", error)
            raise

    def alive(self):
        return self.process is not None and self.process.poll() is None

    def close(self, reason="completed"):
        if self.closed:
            return
        if getattr(self, "close_attempted", False):
            raise self.close_error
        self.close_error = RuntimeError("process close interrupted; outcome unknown, do not retry")
        self.close_attempted = True
        errors = []

        def attempt(step, operation):
            # One bounded pass: a failed owned step cannot skip later cleanup or evidence IO.
            try:
                return True, operation()
            except BaseException as error:
                errors.append((step, error))
                return False, None

        def signal_group(sig):
            try:
                os.killpg(self.process.pid, sig)
            except ProcessLookupError:
                pass

        _, running = attempt("poll_before_close", self.alive)
        job_terminated = job_handle_closed = None
        if self.job:
            job_terminated, _ = attempt("job_terminate", self.job.terminate)
            job_handle_closed, _ = attempt("job_close", self.job.close)
        elif self.process:
            if os.name == "nt":
                attempt("process_kill", self.process.kill)
            else:
                for name, sig in (("sigterm", signal.SIGTERM), ("sigkill", signal.SIGKILL)):
                    attempt("process_group_" + name, lambda: signal_group(sig))
        if self.process:
            if self.process.stdin is not None:
                attempt("stdin_close", self.process.stdin.close)
            try:
                self.process.wait(timeout=5)
            except BaseException as error:
                if not isinstance(error, subprocess.TimeoutExpired):
                    errors.append(("process_wait", error))
                attempt("process_kill", self.process.kill if os.name == "nt"
                        else lambda: signal_group(signal.SIGKILL))
                attempt("process_wait_after_kill", lambda: self.process.wait(timeout=5))
        code = self.process.returncode if self.process else None
        if self.process and code is None and not errors:
            errors.append(("process_exit", RuntimeError("owned process exit remains unknown after bounded cleanup")))
        for name, stream in zip(("stdout", "stderr"), self.streams):
            attempt(name + "_close", stream.close)
        _, stdout = attempt("stdout_record", lambda: record(self.paths["stdout"]))
        _, stderr = attempt("stderr_record", lambda: record(self.paths["stderr"]))
        value = dict(argv=self.argv, reason=reason, stopped_while_running=running,
            exit_code=code, exit_status="not_started" if self.process is None else "unknown" if code is None else "exited",
            started_monotonic_ns=self.started, ended_monotonic_ns=time.monotonic_ns(), stdout=stdout, stderr=stderr,
            job_terminated=job_terminated, job_handle_closed=job_handle_closed, cleanup_complete=not errors,
            cleanup_errors=[dict(step=step, type=type(error).__name__, message=str(error)) for step, error in errors])
        attempt("close_receipt", lambda: save(self.paths["closed.json"], value))
        if errors:
            self.close_error = errors[0][1]
            for step, error in errors:
                self.close_error.add_note("Process cleanup %s: %s: %s" % (step, type(error).__name__, error))
            raise self.close_error
        self.close_error, self.closed = None, True

    def _close_after_error(self, reason, error):
        try:
            self.close(reason)
        except BaseException as cleanup:
            if cleanup is not error and getattr(error, "process_cleanup_error", None) is not cleanup:
                error.process_cleanup_error = cleanup
                error.add_note("Secondary process cleanup failure (%s): %s" % (type(cleanup).__name__, cleanup))
                for note in getattr(cleanup, "__notes__", ()):
                    error.add_note(note)

    def wait(self, seconds, success_codes=(0,), *, read_ready=None, deadline=None):
        require(0 < seconds <= 18000, "finite command timeout required")
        if deadline is not None:
            require(type(deadline) in (int, float) and math.isfinite(deadline), "finite absolute command deadline required")
        deadline = min(time.monotonic() + seconds, deadline) if deadline is not None else time.monotonic() + seconds
        try:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise subprocess.TimeoutExpired(self.argv, seconds)
            if read_ready is None:
                code = self.process.wait(timeout=remaining)
            else:
                while True:
                    code = self.process.poll()
                    if code is not None:
                        break
                    if read_ready():
                        self.close("readonly_query_yielded_to_terminal")
                        raise ObservationReady("read-only query yielded to terminal MCU observation")
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise subprocess.TimeoutExpired(self.argv, seconds)
                    try:
                        code = self.process.wait(timeout=min(.1, remaining))
                        break
                    except subprocess.TimeoutExpired:
                        pass
        except subprocess.TimeoutExpired:
            error = RuntimeError("tool timeout; reconcile device, no next action")
            self._close_after_error("timeout_outcome_unknown", error)
            raise error from None
        try:
            require(code in success_codes, "standard tool failed; inspect original command streams")
        except BaseException as error:
            self._close_after_error("completed", error)
            raise
        self.close()
        if read_ready is not None and read_ready():
            raise ObservationReady("completed read yielded to terminal MCU observation")
        return self.paths["stdout"].read_bytes()


def command(out, label, argv, env, *, seconds=180, stdin=None, success_codes=(0,), read_ready=None, deadline=None):
    if deadline is not None:
        require(type(deadline) in (int, float) and math.isfinite(deadline) and time.monotonic() < deadline,
                "command deadline reached before launch")
    process = Process(out, label, argv, env, stdin=stdin)
    try:
        result = process.wait(seconds, success_codes, read_ready=read_ready, deadline=deadline)
    except BaseException as error:
        process._close_after_error("caller_failed", error)
        raise
    process.close("caller_failed")
    return result


def listening(port):
    with socket.socket() as sock:
        sock.settimeout(.2)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def wait_for(check, seconds, *, interval=.2):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        value = check()
        if value:
            return value
        time.sleep(min(interval, max(0, deadline - time.monotonic())))
    raise RuntimeError("observation deadline; preserve partial evidence, no replay")
