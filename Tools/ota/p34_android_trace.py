"""Bounded exact-PID FBP observation; native callbacks are not durable ACKs."""
from __future__ import annotations

import re
import subprocess
import threading
import time
from pathlib import Path

MAX_BYTES = 16 * 1024 * 1024
MAX_SECONDS = 2600
TAG = "[FBP-Android]"
LINE = re.compile(r"\s*(\d+)\.(\d{3,6})\s+(\d+)\s+(\d+)\s+([VDIWEF])\s+\[FBP-Android\]\s*:\s*\[FBP\] (.*)")


def require(value, message):
    if not value:
        raise RuntimeError(message)


def command(p, pid):
    require(type(pid) is int and pid > 0, "one exact positive Android PID required")
    return [str(p.ADB), "-H", "127.0.0.1", "-P", str(p.PORT), "-s", p.SERIAL,
            "logcat", "-b", "main", "-v", "epoch", "-v", "usec", "-T", "1",
            "--pid=" + str(pid), TAG + ":V", "*:S"]


def markers(raw, pid, *, complete=False):
    """Keep native durations in their own clock; reject ambiguous serial writes."""
    require(type(pid) is int and pid > 0 and len(raw) <= MAX_BYTES, "native trace identity/size")
    text = raw.decode("utf-8", errors="strict")
    if not text.endswith("\n"):
        require(not complete or not text, "truncated native trace")
        text = text.rsplit("\n", 1)[0] + "\n" if "\n" in text else ""
    writes, notifications, pending, callbacks = [], [], None, {}
    previous, lines = None, 0
    for line in text.splitlines():
        if not line or line.startswith("--------- beginning of "):
            continue
        match = LINE.fullmatch(line)
        require(match is not None, "unexpected native log line/format")
        seconds, fraction, actual_pid, tid, level, body = match.groups()
        require(int(actual_pid) == pid, "native log PID changed")
        require(level not in "EF", "native error marker")
        us = int(seconds) * 1000000 + int(fraction.ljust(6, "0"))
        require(previous is None or us >= previous, "native clock/order moved backwards")
        previous, lines = us, lines + 1
        if body == "onMethodCall: writeCharacteristic":
            require(pending is None, "overlapping native writes")
            pending = us
        elif body in ("onCharacteristicWrite:", "onCharacteristicChanged:"):
            require(tid not in callbacks, "incomplete native callback")
            callbacks[tid] = dict(kind="write" if "Write" in body else "notify", us=us)
        elif tid in callbacks and body.strip().startswith("chr:"):
            cb = callbacks[tid]
            cb["chr"] = body.strip()[4:].strip().lower()
            if cb["kind"] == "notify":
                require(cb["chr"] == "fff1", "unexpected notification characteristic")
                notifications.append(cb["us"])
                del callbacks[tid]
        elif tid in callbacks and body.strip().startswith("status:"):
            cb = callbacks.pop(tid)
            require(cb["kind"] == "write" and cb.get("chr") == "fff2" and
                    body.strip() == "status: GATT_SUCCESS (0)", "invalid native write callback")
            require(pending is not None and cb["us"] >= pending, "unmatched native write callback")
            writes.append(dict(start_us=pending, callback_us=cb["us"], elapsed_us=cb["us"] - pending))
            pending = None
    if complete:
        require(pending is None and not callbacks, "incomplete native write/callback tail")
    return dict(pid=pid, lines=lines, writes=writes, notifications_us=notifications,
                pending_write=pending is not None, partial_callbacks=len(callbacks),
                clock="Android logcat epoch; not synchronized to App stopwatch",
                callback_semantics="local Android buffer availability, not durable ACK")


def query_gate(raw, pid):
    value = markers(raw, pid)
    require(value["writes"] and value["notifications_us"] and not value["pending_write"] and
            value["partial_callbacks"] == 0, "query-time native write/notify markers missing")
    return dict(result="NATIVE_QUERY_MARKERS_OBSERVED", **value,
                attribution="capability only; packet pairing and trace completeness not yet proved")


class Trace:
    """One read-only logcat client, bounded bytes/deadline and joined on exit."""

    def __init__(self, c, p, out, pid):
        self.c, self.p, self.out, self.pid = c, p, c.checked(out), pid
        self.process = self.thread = self.timer = None
        self.lock, self.stopping = threading.Lock(), threading.Event()
        self.error, self.count = None, 0
        self.raw_path = c.checked(self.out / "logcat.txt")
        for leaf in ("start.json", "result.json", "query-logcat.txt", "query.json"):
            c.checked(self.out / leaf)
        self.args = command(p, pid)

    def start(self):
        require(self.process is None and self.p.alive(), "native collector already used or USB not owned")
        require(self.p.command(["shell", "pidof", self.c.PKG]).strip() == str(self.pid), "native collector PID not live")
        self.c.checked(self.out).mkdir(parents=True, exist_ok=False)
        env = self.p.environment()
        self.c.save(self.out / "start.json", dict(time=self.c.now(), pid=self.pid, command=self.args,
            apk=self.c.apk["apk"], source=self.c.record(Path(__file__)),
            maximum_bytes=MAX_BYTES, maximum_seconds=MAX_SECONDS, phone_log_clear=False))
        self.process = subprocess.Popen(self.args, cwd=self.c.ROOT, env=env,
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        self.thread = threading.Thread(target=self._read, name="p34-android-log", daemon=True)
        self.timer = threading.Timer(MAX_SECONDS, self._expire)
        self.timer.daemon = True
        self.thread.start()
        self.timer.start()
        self.require_ready()

    def _expire(self):
        self.error = "native collector deadline exceeded"
        if self.process.poll() is None:
            self.process.terminate()

    def _read(self):
        try:
            with self.raw_path.open("xb") as stream:
                while True:
                    data = self.process.stdout.read1(4096)
                    if not data:
                        break
                    with self.lock:
                        require(self.count + len(data) <= MAX_BYTES, "native collector byte limit")
                        stream.write(data)
                        stream.flush()
                        self.count += len(data)
            require(self.stopping.is_set(), "native logcat exited before collector stop")
        except Exception as error:
            self.error = str(error)
            if self.process.poll() is None:
                self.process.terminate()

    def require_ready(self):
        require(self.error is None and self.process is not None and self.process.poll() is None and
                self.thread.is_alive(), "native collector unavailable: " + str(self.error))

    def admit_queries(self):
        self.require_ready()
        with self.lock:
            raw = self.raw_path.read_bytes() if self.raw_path.exists() else b""
        value = query_gate(raw, self.pid)
        value["input"] = self.c.raw(self.out / "query-logcat.txt", raw)
        self.c.save(self.out / "query.json", value)
        return self.c.record(self.out / "query.json")

    def stop(self):
        require(self.process is not None, "native collector was not started")
        self.stopping.set()
        if self.timer:
            self.timer.cancel()
            self.timer.join(2)
        requested = self.process.poll() is None
        if requested:
            self.process.terminate()
        forced = False
        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            forced = True
            self.process.kill()
            self.process.wait(timeout=5)
        if self.thread:
            self.thread.join(5)
        require(self.thread is None or not self.thread.is_alive(), "native log reader closure uncertain")
        self.process.stdout.close()
        value = dict(result="NATIVE_LOG_COLLECTED" if not self.error and not forced else "NATIVE_LOG_FAILED",
            time=self.c.now(), pid=self.pid, error=self.error, bytes=self.count,
            client_exit=self.process.returncode, host_client_stop_requested=requested,
            forced_kill=forced, thread_closed=True, log=self.c.record(self.raw_path),
            start=self.c.record(self.out / "start.json"), remote_logcat_closure="owned USB close required",
            speed_attribution="NOT_ANALYZED", phone_mutations=0)
        self.c.save(self.out / "result.json", value)
        return self.c.record(self.out / "result.json")
