"""P3-4 standard-tool ownership and receipts, never a Flash/ADB implementation."""
import base64
import csv
from contextlib import contextmanager
import hashlib
import json
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
        self.streams = [self.paths[k].open("xb") for k in ("stdout", "stderr")]
        self.job = host.owned.WindowsJob() if os.name == "nt" else None
        self.process, self.closed = None, False
        try:
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
        except BaseException:
            if self.alive():
                self.process.kill()
            self.close("launch_failed")
            raise

    def alive(self):
        return self.process is not None and self.process.poll() is None

    def close(self, reason="completed"):
        if self.closed:
            return
        running = self.alive()
        try:
            if self.job:
                self.job.terminate()
                self.job.close()
            elif self.process:
                for sig in (signal.SIGTERM, signal.SIGKILL):
                    try:
                        os.killpg(self.process.pid, sig)
                    except ProcessLookupError:
                        pass
            if self.process:
                try:
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    if os.name == "nt":
                        self.process.kill()
                    else:
                        os.killpg(self.process.pid, signal.SIGKILL)
                    self.process.wait(timeout=5)
        finally:
            for stream in self.streams:
                stream.close()
            self.closed = True
        save(self.paths["closed.json"], dict(argv=self.argv, reason=reason, stopped_while_running=running,
            exit_code=self.process.returncode if self.process else None, started_monotonic_ns=self.started,
            ended_monotonic_ns=time.monotonic_ns(), stdout=record(self.paths["stdout"]),
            stderr=record(self.paths["stderr"])))

    def wait(self, seconds, success_codes=(0,)):
        require(0 < seconds <= 18000, "finite command timeout required")
        try:
            code = self.process.wait(timeout=seconds)
        except subprocess.TimeoutExpired:
            self.close("timeout_outcome_unknown")
            raise RuntimeError("tool timeout; reconcile device, no next action") from None
        self.close()
        require(code in success_codes, "standard tool failed; inspect original command streams")
        return self.paths["stdout"].read_bytes()


def command(out, label, argv, env, *, seconds=180, stdin=None, success_codes=(0,)):
    process = Process(out, label, argv, env, stdin=stdin)
    try:
        return process.wait(seconds, success_codes)
    finally:
        process.close("caller_failed")


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
        time.sleep(interval)
    raise RuntimeError("observation deadline; preserve partial evidence, no replay")
