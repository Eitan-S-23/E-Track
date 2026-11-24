"""Single-App, bounded network/USB/MCU orchestration for P3-4 screening."""
from __future__ import annotations

import argparse
import base64
import datetime as dt
import hashlib
import importlib.util
import json
import logging
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request
import zipfile


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


m = load("baud_runtime_mcu", Path(__file__).with_name("baud_mcu.py"))
b, a = m.b, m.a
HERE = b.ROOT / ".cache/p3-4-screening-20260922"
supervisor = load("baud_runtime_supervisor", HERE / "supervisor.py")
original_phone = load("baud_runtime_phone", HERE / "phone.py")
service = m.base.assets_api.service
runner = original_phone.b.runner
SELF = Path(__file__).resolve()
RUNTIME = b.OUT / "runtime"
PHONE = RUNTIME / "phone-r1"
NETWORK = RUNTIME / "network-r1"
PKG, TARGET = "com.wen.gaia.gaia.p34baud", "02:00:00:00:00:01"
TUNNEL = b.P3 / ".cache/p3-4-single-ota-20260921/bin/cloudflared.exe"
TUNNEL_SHA = "2837888cc0f5d58f15b6dc478376de90b4d3ba5241c7947455d1e0a0df429712"


def save(path, value, replace=False):
    return b.io.write_json(b.ROOT, b.checked(path), value, replace=replace)


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def raw(path, data):
    path = b.checked(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    return b.record(path)


def event(action, status, **values):
    path = b.checked(RUNTIME / "actions.jsonl")
    path.parent.mkdir(parents=True, exist_ok=True)
    item = dict(time=b.now(), action=action, status=status, **values)
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(item) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    print("BAUD_ACTION", json.dumps(item), flush=True)


def environment():
    value = b.environment()
    for key in list(value):
        if key.startswith(("TUNNEL_", "CLOUDFLARE_", "CF_API_")):
            value.pop(key, None)
    return value


def sources():
    paths = {SELF, Path(m.__file__), Path(a.__file__), Path(b.__file__), Path(service.__file__),
        Path(original_phone.__file__), Path(original_phone.query.__file__),
        Path(supervisor.__file__), Path(supervisor.owned.__file__), supervisor.owned.SPAWNER,
        Path(runner.__file__), Path(b.io.__file__), Path(m.c.__file__), Path(m.passive.__file__),
        Path(m.epoch.__file__), Path(m.base.__file__),
        b.SRC / "Tools/ota/p3-4-link-stats/observation_capture.py",
        b.P3 / "Tools/ota/p3-4-link-stats/link_stats.py", Path(__file__).with_name("baud_restore.py"),
        Path(__file__).with_name("baud_tune.py"), b.ROOT / "Tools/ota/repeat_cycle.py",
        *[b.ROOT / ".cache/p34-restore-20260922" / (name + ".py") for name in ("restore_device", "build_helper", "inspect_device")]}
    return [b.record(path) for path in sorted(paths)]


def authority():
    value = b.read("plan.json")
    b.require(value["root"] == str(b.ROOT) and value["sources"] == sources() and
              value["rates"] == [115200, 460800, 921600] and value["package"] == PKG, "prepared task source/scope changed")
    return value


def apk():
    value = b.read("apk.json")
    b.require(value["metadata"]["application_id"] == PKG and b.record(value["apk"]["path"]) == value["apk"], "APK drift")
    return value


def cell(run):
    b.require(isinstance(run, str) and re.fullmatch(r"[a-z0-9-]{1,48}", run), "run label")
    return b.checked(b.OUT / "runs" / run)


def phone(run=None):
    p = original_phone
    p.RUNTIME = PHONE
    p.b.authority = authority
    p.b.environment = environment
    p.b.event = event
    p.apk = lambda _: apk()
    p.package = lambda _: PKG
    p.cell = lambda _: cell(run)
    envelope = load("baud_runtime_envelope", b.SRC / "Tools/ota/p3-4-link-stats/observation_capture.py")
    envelope.ROOT, envelope.checked = b.ROOT, b.checked
    p.envelope, p.query.m = envelope, envelope
    return p


def make_config(assets, origin, token_key):
    releases = {}
    for tag, group in assets["groups"].items():
        key = "p34-baud-" + tag
        releases[key] = dict(releaseId=key, versionName=group["target_identity"]["version_name"],
            versionCode=group["target_identity"]["version_code"], releaseTag=key,
            releaseNotes="Development baud screening; not release or 1 MiB acceptance.",
            targetImageSha256=group["target"]["sha256"], targetHardware=service.DEVICE_MODEL,
            minAppVersionCode=0, hardwareRevision=1, layoutId=1, minBootVersion=1, minProtocolVersion=1,
            asset=dict(assetId=key + "-full", kind="full", fileName=tag + "-full.etu",
                sha256=group["package"]["sha256"], sizeBytes=group["package"]["bytes"],
                path=group["package"]["path"], baseVersionCode=0, baseImageSha256=None))
    return dict(publicBaseUrl=origin, token=dict(keyVersion=1, keyHex=token_key, ttlSeconds=300),
                channels=dict(stable="p34-baud-screen", beta=None), releases=releases)


class RoutingState:
    def __init__(self, assets, origin):
        config = make_config(assets, origin, secrets.token_hex(32))
        self.states = {tag: service.V2ServiceState(config, str(b.ROOT), active_release="p34-baud-" + tag)
                       for tag in ("bootstrap", "screen")}

    def handle_latest(self, pairs, request_id=None):
        tag = "bootstrap" if ("currentVersionCode", "30207") in pairs else "screen"
        return self.states[tag].handle_latest(pairs, request_id=request_id)

    def handle_download(self, pairs, *args, **kwargs):
        tag = "bootstrap" if ("releaseId", "p34-baud-bootstrap") in pairs else "screen"
        return self.states[tag].handle_download(pairs, *args, **kwargs)


def query_for(group):
    return dict(appId="trace", deviceModel=service.DEVICE_MODEL, channel="stable",
        currentVersionCode=str(group["baseline_identity"]["version_code"]), currentImageSha=group["baseline"]["sha256"],
        hardwareRevision="1", layoutId="1", bootVersion="1", protocolVersion="1", appVersionCode="0")


def verify_latest(body, group):
    b.require(body.get("schemaVersion") == 2 and body.get("updateAvailable") is True and
              body.get("versionCode") == group["target_identity"]["version_code"] and
              body.get("targetImageSha256") == group["target"]["sha256"] and
              body["asset"]["kind"] == "full" and body["asset"]["sha256"] == group["package"]["sha256"] and
              body["asset"]["sizeBytes"] == group["package"]["bytes"], "latest group/asset identity mismatch")


def hostcheck():
    out = b.checked(b.OUT / "runtime-hostcheck-003")
    b.require(not out.exists(), "preserve previous host HTTP check")
    for name in ("result.json", "service.log"):
        b.checked(out / name)
    out.mkdir(parents=True)
    assets = m.verified_assets()
    log = logging.getLogger("baud-http-selftest")
    log.setLevel(logging.INFO)
    log.propagate = False
    sink = logging.FileHandler(out / "service.log", mode="x", encoding="utf-8")
    log.addHandler(sink)
    handler = type("BaudHostCheck", (service.P33RequestHandler,), dict(log=log, timeout=5))
    server = service.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    origin = "http://127.0.0.1:%d" % server.server_port
    handler.state = RoutingState(assets, origin)
    worker = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": .1}, daemon=True)
    checks = []
    worker.start()
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        for tag, group in assets["groups"].items():
            url = origin + service.LATEST_PATH + "?" + urllib.parse.urlencode(query_for(group))
            with opener.open(url, timeout=5) as response:
                body = json.loads(response.read(16384))
            verify_latest(body, group)
            download = body["asset"]["downloadUrl"]
            with opener.open(download, timeout=5) as response:
                data = response.read(group["package"]["bytes"] + 1)
            b.require(data == Path(group["package"]["path"]).read_bytes(), "HTTP bytes differ from admitted package")
            checks.extend([tag + "-latest", tag + "-exact-full-download"])
            request = urllib.request.Request(download, headers={"Range": "bytes=16-"})
            with opener.open(request, timeout=5) as response:
                b.require(response.status == 206 and response.read() == data[16:], "HTTP range mismatch")
            checks.append(tag + "-range")
        changed = query_for(assets["groups"]["screen"])
        changed["currentVersionCode"] = "30209"
        changed["currentImageSha"] = assets["groups"]["screen"]["target"]["sha256"]
        with opener.open(origin + service.LATEST_PATH + "?" + urllib.parse.urlencode(changed), timeout=5) as response:
            b.require(json.loads(response.read())["updateAvailable"] is False, "final target must not loop into another upgrade")
        checks.append("target-no-update")
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=5)
        log.removeHandler(sink)
        sink.close()
    b.require(not worker.is_alive() and server.socket.fileno() == -1, "host HTTP test worker did not close")
    save(out / "result.json", dict(passed=True, checks=checks, sources=sources(), hardware=False, listener_closed=True))
    print("RUNTIME_HTTP_HOST_READY", len(checks), flush=True)


def prepare():
    b.require(not (b.OUT / "plan.json").exists(), "preserve prepared plan")
    assets, metadata = m.verified_assets(), apk()
    m.load_bindings()
    host = read(b.OUT / "runtime-hostcheck-003/result.json")
    test = read(b.OUT / "host-tests-mcu-002/result.json")
    runtime_test = read(b.OUT / "host-tests-runtime-002/result.json")
    recovery = read(b.OUT / "recovery/result.json")
    b.require(host["passed"] and host["sources"] == sources() and test["passed"] and
              test["tested_source"] == b.record(Path(m.__file__)) and recovery["result"] == "HOST_READY" and
              runtime_test["passed"] and runtime_test["sources"] == sources(),
              "source-bound host checks and recovery assets required")
    b.require(b.record(TUNNEL)["sha256"] == TUNNEL_SHA, "tunnel executable changed")
    ci = []
    for item in metadata["host_reports"]:
        b.require(b.record(item["path"]) == item, "original CI report changed")
        report = read(item["path"])
        commands = {item["name"]: item for item in report["commands"]}
        b.require(report["development_result"] == "PASS" and report["scope"] == "all" and
                  report["lockfile_unchanged"] and report["diagnostics_complete"] and
                  all(item["status"] == "PASS" and item["exit_code"] == 0 for item in commands.values()),
                  "original CI command outcome failed")
        ci.append(dict(host=report["host"], report=item, sdk=commands["sdk_version"]["diagnostics"]["sdk_identity"],
                       tests=commands["tests"]["diagnostics"]["test_counts"]))
    with zipfile.ZipFile(metadata["apk"]["path"]) as archive:
        data = archive.read("assets/flutter_assets/kernel_blob.bin")
        obs = metadata["metadata"]["device_observation"]
        b.require(all(obs[key].encode() in data for key in ("target", "sentinel", "firmware_latest_url")), "APK observation constants missing")
    value = dict(time=b.now(), root=str(b.ROOT), package=PKG, phone=original_phone.SERIAL, target=TARGET,
        rates=[115200, 460800, 921600], cells=["bootstrap", "baud-115200", "baud-460800", "baud-921600"],
        group_assets=assets, apk=metadata["apk"], ci=ci, sources=sources(), native_history=m.native_authority(),
        authority="Current user-authorized P3-4 continuation and device-experiment-policy; stop for actual human intervention",
        sender=dict(reuseGatt=True, withoutResponse=True, unchanged_data_bytes=128, unchanged_window=True),
        recovery=b.record(b.OUT / "recovery/manifest.json"), cold_start_per_cell=True,
        initial_state="same 30208 body and zero durable offset; unmatched prior journal and erased journal both take the same rebuild_session path",
        runtime=dict(phone_seconds=5400, capture_seconds=4100, transfer_reserve=1280, network_seconds=10800),
        human_actions="phone permission dialogs; connection/download/start; physical action only if required",
        prohibitions=["no automatic UI taps", "no App-data clearing", "no Boot replacement", "no release/deploy",
                      "no replay of successful OTA to repair host evidence", "no App-only downgrade across BCB"],
        screening_only=True, independent_acceptance=False)
    b.save("plan.json", value)
    event("prepare-three-rate-plan", "completed", rates=value["rates"], ci=ci)


def network_worker():
    authority()
    b.require(not NETWORK.exists(), "network runtime exists")
    for name in ("service.log", "tunnel.log", "ready.json", "closed.json", "stop.json"):
        b.checked(NETWORK / name)
    NETWORK.mkdir(parents=True)
    assets = m.verified_assets()
    log = logging.getLogger("p34-baud-service")
    log.setLevel(logging.INFO)
    log.propagate = False
    sink = logging.FileHandler(NETWORK / "service.log", mode="x", encoding="utf-8")
    log.addHandler(sink)
    server = worker = job = process = output = None
    started, opened = time.monotonic(), dt.datetime.now(dt.timezone.utc)
    result = dict(started=opened.isoformat(), result="NETWORK_FAILURE")
    try:
        handler = type("BaudHandler", (service.P33RequestHandler,), dict(log=log, timeout=5))
        server = service.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        local = "http://127.0.0.1:%d" % server.server_port
        handler.state = RoutingState(assets, local)
        worker = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": .1}, daemon=True)
        worker.start()
        output = b.checked(NETWORK / "tunnel.log").open("xb")
        job = runner.WindowsJob()
        process = subprocess.Popen([sys.executable, "-I", "-S", "-B", "-X", "utf8", "-c", runner.WINDOWS_LAUNCHER],
            cwd=b.ROOT, env=environment(), stdin=subprocess.PIPE, stdout=output, stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW)
        job.assign(process)
        args = [str(TUNNEL), "tunnel", "--no-autoupdate", "--protocol", "http2", "--edge-ip-version", "4",
                "--metrics", "127.0.0.1:0", "--url", local]
        process.stdin.write((json.dumps(args) + "\n").encode())
        process.stdin.close()
        origin = None
        while time.monotonic() - started < 90:
            b.require(process.poll() is None, "tunnel exited")
            text = (NETWORK / "tunnel.log").read_text(encoding="utf-8", errors="replace")
            matches = re.findall(r"https://[a-z0-9-]+\.trycloudflare\.com", text)
            if matches and "Registered tunnel connection" in text:
                origin = matches[0]
                break
            time.sleep(.5)
        b.require(origin is not None, "tunnel registration deadline")
        handler.state = RoutingState(assets, origin)
        save(NETWORK / "ready.json", dict(origin=origin, listen="127.0.0.1:%d" % server.server_port,
            expires_at=(opened + dt.timedelta(seconds=10800)).isoformat(), source=b.record(SELF), pid=os.getpid()))
        event("temporary-network", "ready", origin=origin)
        while time.monotonic() - started < 10800 and not (NETWORK / "stop.json").exists():
            b.require(process.poll() is None, "tunnel unexpectedly exited")
            time.sleep(.5)
        result["result"] = "STOPPED_BY_OPERATOR" if (NETWORK / "stop.json").exists() else "STOPPED_AT_DEADLINE"
    except Exception as error:
        result["error"] = type(error).__name__ + (": " + str(error) if isinstance(error, RuntimeError) else "")
    finally:
        if job:
            job.terminate()
            job.close()
        if process:
            result["launcher_exit"] = process.wait(timeout=10)
        if server:
            if worker and worker.is_alive():
                server.shutdown()
            server.server_close()
            result["listener_closed"] = server.socket.fileno() == -1
        if worker:
            worker.join(timeout=5)
            result["worker_stopped"] = not worker.is_alive()
        if output:
            output.close()
        log.removeHandler(sink)
        sink.close()
        result.update(ended=b.now(), seconds=time.monotonic() - started)
        save(NETWORK / "closed.json", result)
    b.require(result["result"] != "NETWORK_FAILURE", "network failed; original outcome retained")


def wait_file(path, seconds=90):
    deadline = time.monotonic() + seconds
    while not Path(path).exists():
        b.require(time.monotonic() < deadline, "readiness deadline: " + str(path))
        time.sleep(.25)
    return read(path)


def launch_worker(name, mode, seconds, run=None):
    args = [mode] + (["--run", run] if run else [])
    out = b.checked(RUNTIME / name)
    value = supervisor.owned.launch(out, SELF, args, seconds)
    b.require(value["detached_from_job"], "worker lifetime is still tied to agent tool")
    return value


def live_network():
    value = read(NETWORK / "ready.json")
    b.require(not (NETWORK / "closed.json").exists() and value["source"] == b.record(SELF) and
              dt.datetime.fromisoformat(value["expires_at"]).timestamp() - time.time() > 1800,
              "network closed/expired or lacks device reserve")
    return value


def https_check():
    origin = live_network()["origin"]
    results = []
    for tag, group in m.verified_assets()["groups"].items():
        url = origin + service.LATEST_PATH + "?" + urllib.parse.urlencode(query_for(group))
        with urllib.request.urlopen(url, timeout=30) as response:
            body = json.loads(response.read(16384))
        verify_latest(body, group)
        parsed = urllib.parse.urlsplit(body["asset"]["downloadUrl"])
        b.require(parsed.scheme + "://" + parsed.netloc == origin, "unexpected download origin")
        with urllib.request.urlopen(body["asset"]["downloadUrl"], timeout=30) as response:
            data = response.read(group["package"]["bytes"] + 1)
        b.require(data == Path(group["package"]["path"]).read_bytes(), "HTTPS package bytes changed")
        results.append(dict(group=tag, bytes=len(data), sha256=hashlib.sha256(data).hexdigest()))
    save(NETWORK / "verified.json", dict(time=b.now(), origin=origin, results=results))
    print("HTTPS_GROUPS_VERIFIED", json.dumps(results), flush=True)


def open_runtime():
    authority()
    if not (RUNTIME / "network-worker/ready.json").exists():
        launch_worker("network-worker", "network-worker", 10830)
    wait_file(NETWORK / "ready.json")
    if not (NETWORK / "verified.json").exists():
        https_check()
    p = phone()
    if not (RUNTIME / "phone-worker/ready.json").exists():
        prior = read(b.ROOT / ".cache/p34-cycles/c3-002/phone-recovery-r1/closed.json")
        supervisor_closed = read(b.ROOT / ".cache/p34-cycles/c3-002/adb-recovery-r1/closed.json")
        b.require(prior["port_closed"] and prior["stop_exit"] == 0 and not prior.get("forced_cleanup") and
                  supervisor_closed["worker_exit"] == 0 and not supervisor_closed["forced_termination"] and not p.alive(),
                  "prior private ADB ownership/closure unresolved")
        launch_worker("phone-worker", "phone-worker", 5430)
    wait_file(PHONE / "ready.json", 30)
    p.phone_identity()
    value, installed = apk(), p.installed("runtime")
    if installed is None:
        b.require(not (RUNTIME / "install-started.json").exists(), "installation outcome unresolved; inspect, do not repeat")
        save(RUNTIME / "install-started.json", dict(time=b.now(), apk=value["apk"], package=PKG))
        event("single-apk-install", "started")
        output = p.command(["install", "--no-streaming", value["apk"]["path"]], timeout=180)
        b.require(output.strip().splitlines()[-1:] == ["Success"], "installation outcome uncertain")
        installed = p.installed("runtime")
        b.require(installed is not None, "installed package missing")
    if not (RUNTIME / "installed.json").exists():
        save(RUNTIME / "installed.json", dict(time=b.now(), **installed))
    event("single-apk-install", "completed", **installed)


def release_previous():
    p = phone()
    previous = "com.wen.gaia.gaia.p34c3"
    pid = p.command(["shell", "pidof", previous], check=False).strip()
    if not pid:
        return
    binding = read(b.ROOT / ".cache/p34-cycles/c3-002/cells/reuse-without/finished/binding.json")
    board = read(b.ROOT / ".cache/p34-cycles/c3-002/cells/reuse-without/mcu/result.json")
    b.require(binding["summary"]["outcome"] == "completed" and board["result"] == "TARGET_VERIFIED_RETAINED",
              "previous debug run is not reconciled")
    path = p.command(["shell", "pm", "path", previous]).strip()
    b.require(path.startswith("package:/data/app/") and "\n" not in path, "previous package path")
    digest = p.command(["shell", "sha256sum", path[8:]]).split()[0]
    b.require(digest == binding["apk"]["sha256"], "do not stop an unrelated installed App")
    event("release-previous-completed-debug-app", "started", package=previous)
    p.command(["shell", "am", "force-stop", previous])
    b.require(not p.command(["shell", "pidof", previous], check=False).strip(), "previous App still running")
    event("release-previous-completed-debug-app", "completed", data_preserved=True)


def experiment_config(run, group, baud, origin):
    b.require(baud in (115200, 460800, 921600) and
              re.fullmatch(r"https://[a-z0-9-]+\.trycloudflare\.com", origin), "runtime endpoint/baud")
    return dict(schema=1, runId=run, target=TARGET, requestedBaud=baud, reuseGatt=True, withoutResponse=True,
        firmwareLatestUrl=origin + service.LATEST_PATH, packageBytes=group["package"]["bytes"],
        packageSha256=group["package"]["sha256"], currentVersionCode=group["baseline_identity"]["version_code"],
        currentImageSha256=group["baseline"]["sha256"], targetVersionCode=group["target_identity"]["version_code"],
        targetImageSha256=group["target"]["sha256"])


def start(run, baud, group_name):
    authority()
    b.require(group_name == "bootstrap" and baud == 115200 or group_name == "screen" and baud in (115200, 460800, 921600), "run matrix")
    out = cell(run)
    b.require(not out.exists(), "run already exists; status/resume must not repeat preparation")
    group = m.verified_assets()["groups"][group_name]
    p = phone(run)
    p.phone_identity()
    b.require(p.installed("runtime") is not None, "verified APK not installed")
    b.require(not p.command(["shell", "pidof", PKG], check=False).strip(), "stop only a reconciled completed debug run before reprovisioning")
    if group_name == "bootstrap":
        release_previous()
    if group_name == "screen":
        rate_path = b.OUT / "rates" / (run + ".json")
        rate = read(rate_path)
        b.require(rate["result"] == "BAUD_COLD_START_VERIFIED" and rate["baud"] == baud,
                  "actual module/MCU baud and matched startup not admitted")
    origin = live_network()["origin"]
    data = (json.dumps(experiment_config(run, group, baud, origin), ensure_ascii=True, separators=(",", ":")) + "\n").encode()
    record = raw(out / "p34-experiment.json", data)
    config = dict(id=run, group=group_name, baud=baud, assets=group, apk=apk()["apk"], runtime_config=record,
                  capture_seconds=4100, sources=sources(), plan=b.record(b.OUT / "plan.json"))
    save(out / "config.json", config)
    encoded = base64.b64encode(data).decode("ascii")
    script = "'printf %s " + encoded + " | base64 -d > files/p34-experiment.json'"
    event("provision-" + run, "started", runtime_config=record)
    p.command(["shell", "run-as", PKG, "mkdir", "-p", "files"])
    p.command(["shell", "run-as", PKG, "sh", "-c", script])
    p.command(["shell", "run-as", PKG, "chmod", "600", "files/p34-experiment.json"])
    actual = p.file_bytes(PKG, "files/p34-experiment.json", 8192)
    b.require(actual == data, "provisioned immutable App config differs")
    save(out / "provisioned.json", dict(time=b.now(), file=record, private_path="files/p34-experiment.json", process_stopped=True))
    launch_worker("capture-" + run, "capture-worker", 4130, run)
    preflight = wait_file(out / "mcu/preflight.json", 150)
    b.require(preflight["preflight_ready"] and not (out / "mcu/result.json").exists(), "MCU observer not ready")
    component = p.command(["shell", "cmd", "package", "resolve-activity", "--brief", PKG]).strip().splitlines()[-1]
    b.require(component.startswith(PKG + "/") and re.fullmatch(r"[A-Za-z0-9_./]+", component), "launch component")
    save(out / "launch-started.json", dict(time=b.now(), component=component))
    response = p.command(["shell", "am", "start", "-W", "-n", component], timeout=45)
    pid = p.command(["shell", "pidof", PKG]).strip()
    b.require(pid.isdigit(), "one running debug App required")
    save(out / "launched.json", dict(time=b.now(), pid=int(pid), output=response, apk=apk()["apk"]))
    launch_worker("coordinate-" + run, "coordinate", 5030, run)
    event("run-" + run, "waiting-for-phone-connect-and-download", pid=int(pid))


def experiment_line(messages, config):
    values = [json.loads(line[len("OTA_EXPERIMENT "):]) for line in messages.splitlines() if line.startswith("OTA_EXPERIMENT ")]
    b.require(values, "original App runtime-configuration line missing")
    expected = read(config["runtime_config"]["path"])
    for value in values:
        b.require(value["configSha256"] == config["runtime_config"]["sha256"] and
                  value["runId"] == config["id"] and value["requestedBaud"] == config["baud"] and
                  value["schema"] == 1 and value["deviceAddress"] == TARGET and
                  value["endpointHost"] == urllib.parse.urlsplit(expected["firmwareLatestUrl"]).hostname and
                  all(value[key] == expected[key] for key in ("reuseGatt", "withoutResponse", "packageBytes", "packageSha256",
                      "currentVersionCode", "currentImageSha256", "targetVersionCode", "targetImageSha256")),
                  "App used a different immutable experiment config")
    return values[-1]


def inspect_start(run):
    out, p = cell(run), phone(run)
    config = read(out / "config.json")
    pkg, pid, remote = p.location("runtime")
    before = p.file_bytes(pkg, remote + "/health.json", 8192)
    events = p.file_bytes(pkg, remote + "/events.jsonl", p.envelope.MAX_BYTES)
    after = p.file_bytes(pkg, remote + "/health.json", 8192)
    b.require(p.command(["shell", "pidof", pkg]).strip() == str(pid), "App process changed while reading checkpoint")
    obs = apk()["metadata"]["device_observation"]
    result, prefix, lines = p.query.validate(events, before, after, pid=pid, sentinel=obs["sentinel"], target=TARGET)
    result["experiment"] = experiment_line(lines, config)
    location = b.checked(out / "queries" / str(time.time_ns()))
    for name, data in (("health-before.json", before), ("health-after.json", after), ("events.jsonl", events),
                       ("checkpoint.jsonl", prefix), ("observations.log", lines.encode("utf-8"))):
        raw(location / name, data)
    save(location / "result.json", result)
    if not result["successfulQueries"]:
        return None
    remote_package = "app_flutter/firmware/" + config["group"] + "-full.etu"
    exists = p.command(["exec-out", "run-as", pkg, "ls", remote_package], check=False).strip()
    if exists != remote_package:
        return None
    data = p.file_bytes(pkg, remote_package, config["assets"]["package"]["bytes"] + 1)
    b.require(hashlib.sha256(data).hexdigest() == config["assets"]["package"]["sha256"] and
              len(data) == config["assets"]["package"]["bytes"], "downloaded package differs from group")
    if not (out / "downloaded-full.etu").exists():
        raw(out / "downloaded-full.etu", data)
    value = dict(time=b.now(), query=b.record(location / "result.json"), package=b.record(out / "downloaded-full.etu"),
                 apk=apk()["apk"], pid=pid, experiment=result["experiment"], result="PHONE_QUERY_AND_PACKAGE_VERIFIED")
    save(location / "start-inputs.json", value)
    return b.record(location / "start-inputs.json")


def finished(run):
    out, p = cell(run), phone(run)
    config = read(out / "config.json")
    dest = b.checked(out / "finished")
    if (dest / "binding.json").exists():
        return read(dest / "binding.json")
    b.require(not dest.exists(), "partial extraction must be reconciled without another OTA")
    pkg, pid, remote = p.location("runtime")
    names = p.command(["exec-out", "run-as", pkg, "ls", "-1", remote]).splitlines()
    snapshots = sorted(name for name in names if re.fullmatch(r"snapshot-[1-4]\.jsonl", name))
    if not snapshots:
        return None
    before = p.file_bytes(pkg, remote + "/health.json", 8192)
    data = p.file_bytes(pkg, remote + "/" + snapshots[-1], p.envelope.MAX_BYTES + 8192)
    after = p.file_bytes(pkg, remote + "/health.json", 8192)
    b.require(p.command(["shell", "pidof", pkg]).strip() == str(pid), "App process changed while retrieving snapshot")
    for name, value in (("health-before.json", before), ("snapshot.jsonl", data), ("health-after.json", after)):
        raw(dest / name, value)
    obs = apk()["metadata"]["device_observation"]
    summary = p.envelope.extract(dest / "snapshot.jsonl", dest / "parsed", obs["sentinel"], TARGET)
    expected = read(config["runtime_config"]["path"])
    b.require(summary["pid"] == pid and summary["outcome"] == "completed" and
              all(summary["input"][key] == expected[key] for key in ("packageSha256", "packageBytes", "currentVersionCode",
                  "targetVersionCode", "currentImageSha256", "targetImageSha256")), "finished snapshot input/outcome mismatch")
    experiment_line((dest / "parsed/observations.log").read_text(encoding="utf-8"), config)
    script = b.P3 / "Tools/ota/p3-4-link-stats/link_stats.py"
    rc, output, error = p.execute([sys.executable, "-I", "-S", "-B", "-X", "utf8", str(script), "--log",
        str(dest / "parsed/observations.log"), "--device-capture", "--json"], timeout=60, env=environment())
    raw(dest / "statistics.json", output)
    raw(dest / "statistics.stderr.log", error)
    value = dict(time=b.now(), summary=summary, pid=pid, remote=remote, apk=apk()["apk"], parser=b.record(script),
                 parser_exit=rc, snapshot=b.record(dest / "snapshot.jsonl"), independent_acceptance=False)
    save(dest / "binding.json", value)
    b.require(rc == 0, "strict statistics parser rejected original snapshot")
    return value


def coordinate(run):
    authority()
    out = cell(run)
    started = time.monotonic()
    result = dict(run=run, result="WAITING_FOR_PHONE_QUERY_AND_DOWNLOAD")
    try:
        while time.monotonic() - started < 4930:
            if not (out / "arm.json").exists():
                board = read(out / "mcu/state.json")
                b.require(not (out / "mcu/result.json").exists(), "MCU observer closed before start")
                if board["remaining_seconds"] < m.RESERVE_SECONDS:
                    result["result"] = "START_WINDOW_EXPIRED_NO_REPLAY"
                    break
                p = phone(run)
                names = p.command(["exec-out", "run-as", PKG, "ls", "-1", "files/p34-observations"], check=False).splitlines()
                if not any(re.fullmatch(r"\d{13,20}-[0-9a-f]{24}", name) for name in names):
                    save(out / "status.json", dict(time=b.now(), result="WAITING_FOR_APP_OBSERVATION_OR_PHONE_PERMISSION"), replace=True)
                    time.sleep(3)
                    continue
                item = inspect_start(run)
                if item:
                    b.require(board["state"]["ready_to_begin"], "MCU not ready for this baseline")
                    save(out / "arm.json", dict(time=b.now(), config=b.record(out / "config.json"), start_inputs=item))
                    wait_file(out / "mcu/ota-reserved.json", 15)
                    result["result"] = "READY_FOR_USER_START"
                    event("run-" + run, "ready-for-user-start")
            else:
                result["result"] = "WAITING_FOR_USER_OR_ORDINARY_OTA"
                p = phone(run)
                pkg, _, remote = p.location("runtime")
                health = json.loads(p.file_bytes(pkg, remote + "/health.json", 8192))
                result["app_health"] = health
                if health.get("upgradeEnds", 0) > 0:
                    bound = finished(run)
                    if bound:
                        board = wait_file(out / "mcu/result.json", 380)
                        b.require(board["result"] == "TARGET_VERIFIED_RETAINED" and board["reader_closed"] and
                                  board["final_image"]["sha256"] == read(out / "config.json")["assets"]["target"]["sha256"],
                                  "full MCU target confirmation missing; never replay successful transfer")
                        result.update(result="COMPLETED_RETAINED", app=b.record(out / "finished/binding.json"),
                                      mcu=b.record(out / "mcu/result.json"))
                        save(out / "completed.json", result)
                        break
            save(out / "status.json", dict(time=b.now(), **result), replace=True)
            time.sleep(3)
    except Exception as error:
        result.update(result="HOST_OR_DEVICE_STATE_REQUIRES_RECONCILIATION", error=type(error).__name__ + ": " + str(error))
    finally:
        save(out / "coordinator-result.json", dict(time=b.now(), **result))
    print("COORDINATOR_RESULT", json.dumps(result), flush=True)


def advance(previous):
    authority()
    old = cell(previous)
    completed = read(old / "completed.json")
    b.require(completed["result"] == "COMPLETED_RETAINED", "previous OTA outcome not reconciled")
    config = read(old / "config.json")
    if config["group"] == "bootstrap":
        baud = 115200
    else:
        candidates = [115200, 460800, 921600]
        position = candidates.index(config["baud"])
        b.require(position < 2, "three screening rates are already complete; do not start extra cells")
        baud = candidates[position + 1]
    run = "baud-" + str(baud)
    b.require(not cell(run).exists(), "next cell exists; reconcile instead of advancing twice")
    p = phone(previous)
    b.require(p.installed("runtime") is not None, "only the exact debug App may be stopped")
    if p.command(["shell", "pidof", PKG], check=False).strip():
        event("release-" + previous, "started")
        p.command(["shell", "am", "force-stop", PKG])
        b.require(not p.command(["shell", "pidof", PKG], check=False).strip(), "previous debug process did not stop")
        event("release-" + previous, "completed", data_preserved=True)
    tune = load("baud_runtime_tune", SELF.with_name("baud_tune.py"))
    cycle = load("baud_runtime_advance_lock", SELF.with_name("repeat_cycle.py"))
    with cycle.device_lock():
        if config["group"] == "screen":
            label = "restore-for-" + run
            tune.tune(label, 115200, 30209)
            restore = load("baud_runtime_restore", SELF.with_name("baud_restore.py"))
            restore.execute(label, b.OUT / "rates" / (label + ".json"))
        tune.tune(run, baud, 30208)
    start(run, baud, "screen")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("hostcheck", "prepare", "open", "network-worker", "phone-worker", "start",
        "capture-worker", "coordinate", "inspect", "finished", "status", "advance", "advance-worker", "close"))
    parser.add_argument("--run", default="bootstrap")
    parser.add_argument("--baud", type=int, choices=(115200, 460800, 921600), default=115200)
    parser.add_argument("--group", choices=("bootstrap", "screen"), default="bootstrap")
    args = parser.parse_args()
    b.require(Path.cwd().resolve() == b.ROOT and sys.flags.isolated and sys.flags.no_site and
              sys.dont_write_bytecode, "isolated explicit project execution required")
    if args.mode == "hostcheck":
        hostcheck()
        return
    if args.mode == "prepare":
        prepare()
        return
    authority()
    os.environ.update(environment())
    if args.mode == "open":
        open_runtime()
    elif args.mode == "network-worker":
        network_worker()
    elif args.mode == "phone-worker":
        phone().server()
    elif args.mode == "start":
        start(args.run, args.baud, args.group)
    elif args.mode == "capture-worker":
        cycle = load("baud_runtime_device_lock", SELF.with_name("repeat_cycle.py"))
        with cycle.device_lock():
            raise SystemExit(m.capture(args.run))
    elif args.mode == "coordinate":
        coordinate(args.run)
    elif args.mode == "inspect":
        print(json.dumps(inspect_start(args.run)), flush=True)
    elif args.mode == "finished":
        print(json.dumps(finished(args.run)), flush=True)
    elif args.mode == "status":
        for path in (cell(args.run) / "status.json", cell(args.run) / "coordinator-result.json", cell(args.run) / "mcu/state.json"):
            if path.exists():
                print(path.name, json.dumps(read(path)), flush=True)
    elif args.mode == "advance":
        launch_worker("advance-" + args.run, "advance-worker", 1800, args.run)
    elif args.mode == "advance-worker":
        advance(args.run)
    elif args.mode == "close":
        for directory in (PHONE, NETWORK):
            if directory.exists() and not (directory / "closed.json").exists() and not (directory / "stop.json").exists():
                save(directory / "stop.json", dict(time=b.now(), reason="close owned task runtime"))


if __name__ == "__main__":
    main()
