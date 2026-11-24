"""Bounded localhost/USB diagnostic, separate from the Flutter OTA recorder."""
from __future__ import annotations

import argparse
import hashlib
from http.server import BaseHTTPRequestHandler, HTTPServer
import importlib.util
import json
import os
from pathlib import Path
import secrets
import struct
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
AREA = ROOT / ".cache/p34-target50"
RUN = "20260929T135725-69500"
REPORT = ROOT / ".cache/p34-session/runs" / RUN / "analysis/1790691391248239700/result.json"
REPORT_SHA = "bfef15ff7b36d08206b5737d5fbee8f4c17978b0bfe630c81ebd6eb9d22d8349"
PORT = 8874
SESSION = "session"
WINDOW = 31
TARGET_VERSION = 30231
TARGET_LABEL = "3.2.31-p34r"


def require(value, message):
    if not value:
        raise RuntimeError(message)


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def record(path):
    data = path.read_bytes()
    return dict(path=str(path), bytes=len(data), sha256=hashlib.sha256(data).hexdigest())


def context(out):
    cli = load("p34_session", ROOT / "Tools/ota/p34_session.py")
    store = cli.Store(ROOT)
    store.checked(out)
    require(record(REPORT)["sha256"] == REPORT_SHA, "completed30230 report changed")
    report = json.loads(REPORT.read_bytes())
    plan = store.read(report["inputs"]["plan"]["path"])
    require(record(Path(report["inputs"]["plan"]["path"])) == report["inputs"]["plan"], "plan changed")
    state = cli.status(store, RUN, "s04")
    require(state["result"] == "FULL_INSTALL_VERIFIED" and state["worker"]["state"] ==
            state["network"]["state"] == "CLOSED", "prior owners/outcome unresolved")
    impl = cli.backend(store, Path(plan["profile"]["path"]), "receive-pressure")
    c = impl.context(out)
    c.bindings = plan["target_bindings"]
    c.receiver_version = 30230
    require(c.bindings["profile"]["identity"]["version_code"] == 30230, "wrong retained receiver")
    for item in (c.bindings["profile"]["image"], c.bindings["whole_boot"]):
        require(record(Path(item["path"])) == item, "retained input changed")
    impl.preflight(c, out)
    return cli, store, impl, c


def prepare():
    cli, store, impl, c = context(AREA / "assets")
    require(TARGET_VERSION > c.receiver_version, "diagnostic successor must be newer")
    out = c.OUT
    require(not out.exists() and not os.environ.get("OTA_AES_KEY"), "preserve assets/no key override")
    names = ("target.bin", "full.etu", "decoded.bin", "decode.log", "result.json", "input.json")
    for name in names:
        c.checked(out / name)
    env = c.environment()
    os.environ.update(env)
    sys.path.insert(0, str(Path(sys.base_prefix) / "Lib/site-packages"))
    pack_path = ROOT / ".cache/p34sr/f/Tools/etu_pack.py"
    unpack_path = ROOT / ".cache/p34sr/f/Tools/etu_unpack.py"
    pack = load("capacity_pack", pack_path)
    unpack = load("capacity_unpack", unpack_path)
    base = Path(c.bindings["profile"]["image"]["path"])
    target = bytearray(base.read_bytes())
    target[0x400:0x460] = pack.build_fw_header(bytes(target), TARGET_LABEL, 1786320000)
    unpack.verify_fw_header(bytes(target), "capacity successor")
    require(target[:0x400] + target[0x460:] == base.read_bytes()[:0x400] + base.read_bytes()[0x460:],
            "header-only successor changed executable")
    nonce = secrets.token_bytes(16)
    plain = pack.lzma_alone_encode(bytes(target))
    payload = pack.aes_ctr_xcrypt(bytes.fromhex(pack.DEFAULT_KEY_HEX), nonce, plain, True)
    blob = pack.build_etu_header(11, nonce, payload, TARGET_VERSION, 0, bytes(8)) + payload
    outer = unpack.parse_etu_header(blob)
    require(outer["target_vcode"] == TARGET_VERSION and len(blob) > 4096, "invalid diagnostic package")
    image, package = c.raw(out / "target.bin", bytes(target)), c.raw(out / "full.etu", blob)
    n03 = c.read(ROOT / ".cache/p34-next/n03/assets/result.json")
    decoder = n03["decoder"]
    require(record(Path(decoder["path"])) == decoder, "native full decoder changed")
    command = [decoder["path"], package["path"], str(base), image["path"], "ok"]
    run = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, timeout=180,
                         creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    c.raw(out / "decode.log", run.stdout + run.stderr)
    require(run.returncode == 0, "native package decoding failed")
    decoded = json.loads(run.stdout)
    require(all(decoded[k] is True for k in ("passed", "byte_identical", "boot_ok", "guards_ok", "workspace_lifecycle_ok")),
            "native full/Boot/guard validation failed")
    value = dict(result="CAPACITY_ASSETS_PREPARED", no_install=True, package=package, target=image,
                 retained=c.bindings["profile"]["image"], boot=c.bindings["whole_boot"],
                 decoder=decoder, decoded=decoded, command=command,
                 sources=[record(pack_path), record(unpack_path), record(Path(__file__))],
                 input=dict(packageBytes=len(blob), packageSha256=package["sha256"], prefixHex=blob[:3968].hex()),
                 expected=dict(version=c.receiver_version, imageSha256=c.receiver_image_sha))
    c.save(out / "result.json", value)
    print(json.dumps(dict(result=value["result"], package=package, target=image, no_install=True)))


def identity_matches(actual, expected):
    require(isinstance(actual, dict) and actual.get("version") == expected["version"] and
            actual.get("imageSha256") == expected["imageSha256"] and actual.get("modelHex") == "452d547261636b00" and
            actual.get("hardware") == actual.get("layout") == actual.get("protocol") == 1 and
            actual.get("maxWindow", 0) >= 31, "diagnostic INFO differs")


def result_matches(value, chunk, window=31):
    require(value.get("kind") == "repeated-payload-link-capacity" and value.get("durableThroughput") is False and
            value.get("chunkBytes") == chunk and value.get("window") == window and value.get("endSent") is False,
            "unbound diagnostic result")
    require(value.get("result") == "ACKED_LINK_SAMPLE" and value.get("abortConfirmed") is True and
            value.get("writeUncertain") is False, "incomplete diagnostic; preserve/reconcile, never replay")
    frames, duration = value.get("sentFrames"), value.get("elapsedMs")
    require(type(frames) is int and 31 < frames <= 16000 and type(duration) in (int, float) and
            10000 <= duration <= 20000 and value.get("repeatedPayloadBytes") == frames * 128 and
            value.get("uniquePayloadBytes") == 128, "invalid sustained byte/time counters")
    require(abs(value.get("linkPayloadKiBps", -1) - frames * 128 / 1024 / (duration / 1000)) < 1e-9,
            "diagnostic numerator/time mismatch")


def noncommitted_terminal(state, frames):
    session = state["session"]
    require(session["state"] == 0 and session["isr_active"] == 0 and session["durable_off"] == 0 and
            session["segment_bitmap"] == 1 and session["last_ack_cmd"] == 0x84 and
            session["last_ack_seq"] == frames + 2, "noncommitted ABORT state differs")
    require(state["bcb_state"] == 4 and state["confirm_done"] == state["sd_ready"] == 1,
            "retained state is not confirmed/ready")


def browser_resources(sender="fixed"):
    require(sender in ("fixed", "rolling-credit-v1"), "unplanned sender")
    script = (ROOT / "Tools/ota/p34_link_capacity.js").read_bytes()
    if sender == "rolling-credit-v1":
        script += b"\n" + (ROOT / "Tools/ota/p34_rolling_capacity.js").read_bytes()
    return {"/": ((ROOT / "Tools/ota/p34_capacity_control.html").read_bytes(), "text/html; charset=utf-8"),
            "/wire.js": ((ROOT / "Tools/ota/uart_probe.js").read_bytes(), "text/javascript"),
            "/capacity.js": (script, "text/javascript")}


def worker(*, baud=921600, chunks=(142, 244), sender="fixed"):
    require(type(baud) is int and baud in (460800, 921600), "unplanned capacity baud")
    require(chunks in ((142,), (142, 244)), "unplanned capacity chunks")
    cli, store, impl, c = context(AREA / SESSION)
    require(c.supervisor.owned.in_job(), "owned finite worker required")
    out = c.OUT
    admission = c.read(out / "admission.json")
    require(record(AREA / "assets/result.json") == admission["assets"] and
            all(record(Path(item["path"])) == item for item in admission["sources"]),
            "admitted worker inputs changed")
    require(sender == admission.get("sender", "fixed"), "sender differs from admission")
    if sender == "rolling-credit-v1":
        require(record(ROOT / "Tools/ota/p34_rolling_capacity.js") in admission["sources"],
                "rolling source not admitted")
    for name in ("status.json", "status.json.tmp", "result.json", "browser-bound.json", "browser-failed.json",
                 "reverse.json", "trial-142.json", "trial-244.json", "page-ready.json", "mcu", "phone"):
        c.checked(out / name)
    assets = c.read(AREA / "assets/result.json")
    for item in (assets["package"], assets["retained"], assets["boot"]):
        require(record(Path(item["path"])) == item, "capacity asset changed")
    c.screen, c.screen_bytes = assets["package"], Path(assets["package"]["path"]).read_bytes()
    c.target_version = TARGET_VERSION
    require(c.target_version > c.receiver_version, "diagnostic successor must be newer")
    os.environ.update(c.environment())
    require(not (out / "result.json").exists(), "spent diagnostic worker")
    phone = impl.phone(c, "capacity_phone")
    lock = c.load("capacity_lock", ROOT / "Tools/ota/repeat_cycle.py")
    mcu = c.helper.Mcu(c, out / "mcu")
    server = None
    value = dict(result="CAPACITY_INCOMPLETE", trials=[], no_end=True, no_install=True, no_reset=True)
    value.update(selected_baud=baud, required_retained_baud=921600,
                 reset_scope="no MCU reset; confirmed deferred baud setters may reboot the BLE module")
    shared = dict(bound=False, armed=None, done=False, failed=False, index=0)
    token = secrets.token_hex(16)
    resources = browser_resources(sender)

    def status(state):
        c.save(out / "status.json", dict(result=state, time=c.now(), trials=value["trials"]), replace=True)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def send(self, data, content_type="application/json"):
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if self.path in resources:
                self.send(*resources[self.path])
            elif self.path == "/config":
                self.send(json.dumps(dict(expected=assets["expected"], input=assets["input"], token=token, window=WINDOW, chunks=chunks)).encode())
            else:
                self.send_error(404)

        def do_POST(self):
            try:
                self.connection.settimeout(10)
                require(self.headers.get("X-Capacity-Token") == token and
                        self.headers.get("Origin") == f"http://127.0.0.1:{PORT}", "unbound browser origin/token")
                size = int(self.headers.get("Content-Length", "0"))
                require(0 < size <= 16 * 1024 * 1024, "bounded result body required")
                raw = self.rfile.read(size)
                require(len(raw) == size, "truncated browser result")
                body = json.loads(raw)
                if self.path == "/page-ready":
                    require(body.get("secureContext") is True and body.get("webBluetooth") is True,
                            "localhost browser lacks secure Web Bluetooth")
                    c.raw(out / "page-ready.json", raw)
                    status("READY_FOR_USER_BLUETOOTH_CHOOSER")
                elif self.path == "/bound":
                    require(not shared["bound"], "duplicate bind")
                    identity_matches(body["identity"], assets["expected"])
                    c.raw(out / "browser-bound.json", raw)
                    shared["bound"] = True
                    status("READY_FOR_LINK_SCREEN")
                elif self.path == "/arm":
                    require(shared["bound"] and not shared["failed"] and shared["armed"] is None and shared["index"] < len(chunks),
                            "diagnostic trial already spent or unresolved")
                    chunk = chunks[shared["index"]]
                    require(body.get("chunkBytes") == chunk, "trial order differs")
                    identity_matches(body["identity"], assets["expected"])
                    sample = mcu.sample("arm-" + str(chunk))
                    c.helper.idle(sample)
                    shared["armed"] = dict(chunk=chunk, run=sample["profile"]["run"] + 1,
                                           payload=mcu.read(0x90301000, 4096))
                    status("LINK_SCREEN_ACTIVE")
                elif self.path == "/result":
                    require(shared["armed"] is not None, "result without armed trial")
                    armed = shared["armed"]
                    c.raw(out / ("trial-%d.json" % armed["chunk"]), raw)
                    result_matches(body, armed["chunk"], WINDOW)
                    if sender == "rolling-credit-v1":
                        require(body.get("sender") == sender and
                                type(body.get("peakOutstanding")) is int and
                                1 <= body["peakOutstanding"] <= WINDOW and
                                body.get("acknowledgedFrames") == body["sentFrames"],
                                "rolling credit/final ACK accounting differs")
                    identity_matches(body["identity"], assets["expected"])
                    sample = mcu.sample("after-%d" % armed["chunk"])
                    noncommitted_terminal(sample, body["sentFrames"])
                    journal = mcu.read(0x90300000, 4096)
                    c.raw(out / ("journal-%d.bin" % armed["chunk"]), journal)
                    parsed = c.decode_journal(journal, c.screen["sha256"], c.screen["bytes"])
                    require(parsed["durable_off"] == 0 and mcu.read(0x90300000, 4096) == journal,
                            "persistent zero journal differs")
                    profile = Path(sample["profile_raw"]["path"]).read_bytes()
                    decoded = c.helper.decode_terminal(c.m, profile, run=armed["run"], baud=baud,
                        total=c.screen["bytes"], layout=mcu.instrumentation, terminal=1)
                    require(decoded["clean_counters"] and decoded["rx_session_bytes"] == body["sentFrames"] * 142 + 10 and
                            decoded["phases"]["payload_program"]["calls"] == decoded["phases"]["payload_erase"]["calls"] == 0 and
                            mcu.read(0x90301000, 4096) == armed["payload"],
                            "native errors or payload changed")
                    value["trials"].append(dict(chunk_bytes=armed["chunk"], repeated_payload_kib_s=body["linkPayloadKiBps"],
                        frames=body["sentFrames"], milliseconds=body["elapsedMs"], window=WINDOW, native=decoded,
                        original=record(out / ("trial-%d.json" % armed["chunk"]))))
                    shared["armed"] = None
                    shared["index"] += 1
                    status("TRIAL_VERIFIED")
                elif self.path == "/done":
                    require(shared["index"] == len(chunks) and shared["armed"] is None, "screen incomplete")
                    shared["done"] = True
                elif self.path == "/failed":
                    c.raw(out / "browser-failed.json", raw)
                    shared["failed"] = True
                else:
                    raise RuntimeError("unsupported diagnostic operation")
                self.send(b'{"ok":true}')
            except Exception as error:
                value["error"] = type(error).__name__ + ": " + str(error)
                shared["failed"] = True
                self.send_error(409, "preserve result; do not repeat")

    try:
        with lock.device_lock(), phone.usb(c, out / "phone") as p:
            require(not p.command(["shell", "pidof", c.PKG], check=False).strip(), "quiesce completed Flutter App first")
            mcu.open()
            require(mcu.original_baud == 921600, "retain selected baud; no automatic tuning")
            if baud != mcu.original_baud:
                mcu.tune_rate(baud, "selected-capacity-baud")
            server = HTTPServer(("127.0.0.1", PORT), Handler)
            server.timeout = .1
            forwards = p.command(["reverse", "--list"])
            require(f"tcp:{PORT}" not in forwards, "reverse port already owned")
            p.command(["reverse", f"tcp:{PORT}", f"tcp:{PORT}"])
            c.save(out / "reverse.json", dict(port=PORT, purpose="localhost capacity only"))
            try:
                url = f"http://127.0.0.1:{PORT}/"
                require("com.android.chrome" in p.command(["shell", "pm", "list", "packages", "com.android.chrome"]),
                        "Chrome unavailable; no install fallback")
                p.command(["shell", "am", "start", "-a", "android.intent.action.VIEW", "-d", url, "com.android.chrome"])
                status("WAITING_FOR_BROWSER_CAPABILITY_CHECK")
                deadline = time.monotonic() + 600
                while not shared["done"] and not shared["failed"] and time.monotonic() < deadline:
                    server.handle_request()
                    mcu.reader.poll()
                require(shared["done"] and not shared["failed"], "screen incomplete or user window expired")
                value["result"] = "CAPACITY_SCREEN_VERIFIED"
            finally:
                p.command(["reverse", "--remove", f"tcp:{PORT}"])
                require(f"tcp:{PORT}" not in p.command(["reverse", "--list"]), "reverse route not closed")
                if server:
                    server.server_close()
                # Failed partial frames may need the normal session timeout, never a reset.
                until = time.monotonic() + 45
                while time.monotonic() < until:
                    state = mcu.sample("closing-wait-" + str(time.monotonic_ns()))
                    if state["session"]["state"] == 0:
                        break
                    time.sleep(1)
                mcu.close(restore=baud != 921600)
            value["usb_closed"] = True
    except Exception as error:
        value.setdefault("error", type(error).__name__ + ": " + str(error))
        value["result"] = "CAPACITY_INCOMPLETE"
    finally:
        if server:
            server.server_close()
        if mcu.link and mcu.link.opened:
            try:
                mcu.close(restore=baud != 921600)
            except Exception as error:
                value["closure_error"] = str(error)
        c.save(out / "result.json", value)
        status(value["result"])
    return 0 if value["result"] == "CAPACITY_SCREEN_VERIFIED" else 1


def main():
    global SESSION, WINDOW
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "start", "worker", "status"))
    parser.add_argument("--session", choices=("session", "session-w4"), default="session")
    args = parser.parse_args()
    SESSION = args.session
    WINDOW = 4 if SESSION == "session-w4" else 31
    require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
            "explicit root and isolated no-bytecode Python required")
    if args.command == "prepare":
        prepare()
    elif args.command == "status":
        path = AREA / SESSION / "status.json"
        print(path.read_text() if path.exists() else '{"result":"NOT_STARTED"}')
    elif args.command == "worker":
        return worker()
    else:
        _, _, _, c = context(AREA / SESSION)
        require(not c.OUT.exists(), "preserve spent session; no implicit replay")
        test_path = AREA / ("tests-r4/result.json" if SESSION == "session-w4" else "tests-r3/result.json")
        tests = c.read(test_path)
        require(tests["passed"] and all(record(Path(item["path"])) == item for item in tests["sources"]),
                "current source-bound capacity host tests required")
        os.environ.update(c.environment())
        c.save(c.OUT / "admission.json", dict(tests=record(test_path),
            assets=record(AREA / "assets/result.json"), sources=tests["sources"]))
        print(json.dumps(c.supervisor.owned.launch(c.OUT / "owner", Path(__file__), ["worker", "--session", SESSION], 900)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
