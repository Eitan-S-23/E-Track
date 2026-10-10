"""P3-4 private ADB, controlled HTTPS fixture and immutable App snapshot route."""
import hashlib
import json
import logging
import re
import secrets
import shlex
import sys
import threading
import time
from urllib.parse import urlencode, urlsplit
from urllib.request import build_opener, ProxyHandler

import live_host as h

sys.path.insert(0, str(h.ROOT / "Tools/ota/p3-4-link-stats"))
import acceptance_stats
import observation_capture

service = h.host.load("p34_live_service", h.ROOT / "Tools/ota/p3-3-service/service.py")


def config(plan, run_id, origin, baud, timeout):
    h.require(re.fullmatch(r"[a-z][a-z0-9-]{0,47}", run_id), "runtime run ID")
    h.require(baud in (115200, 230400, 460800, 921600) and 500 <= timeout <= 2000, "calibrated parameter range")
    parsed = urlsplit(origin)
    h.require(parsed.scheme == "https" and parsed.hostname and parsed.port in (None, 443) and
              not (parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path), "actual HTTPS origin required")
    base, target = plan["images"]["base"]["image"], plan["images"]["target"]["image"]
    return dict(schema=10, runId=run_id, target=plan["ble_address"], requestedBaud=baud,
        reuseGatt=True, withoutResponse=True, firmwareLatestUrl=origin + service.LATEST_PATH,
        packageBytes=plan["package"]["bytes"], packageSha256=plan["package"]["sha256"],
        currentVersionCode=30286, currentImageSha256=base["sha256"],
        targetVersionCode=30287, targetImageSha256=target["sha256"],
        senderWindowSegments=24, transferMode="full", prefixBytes=0,
        rebootInfoTimeoutMs=2000, rebootProbeIntervalMs=1500, pauseScanDuringOta=False,
        androidHighPriority=False, dataBatchFrames=12, reuseRebootInfoLink=True,
        androidPhyPolicy="off", rebootInfoMaxAttempts=3, ackTimeoutMs=timeout)


def service_config(plan, origin):
    asset = plan["package"]
    return dict(publicBaseUrl=origin, token=dict(keyVersion=1, keyHex=secrets.token_hex(32), ttlSeconds=300),
        channels=dict(stable="reference"), releases=dict(reference=dict(releaseId="p34-reference",
            versionName="3.2.87", versionCode=30287, releaseTag="mcu-e-track-at32f435-v3.2.87",
            releaseNotes="P3-4 controlled reference", targetImageSha256=plan["images"]["target"]["image"]["sha256"],
            targetHardware="e-track-at32f435", minAppVersionCode=0, hardwareRevision=1, layoutId=1,
            minBootVersion=1, minProtocolVersion=1, asset=dict(assetId="p34-reference-patch", kind="patch",
                fileName="e-track-at32f435-v3.2.86-to-v3.2.87-patch.etu", path=str(h.pinned(asset)),
                sizeBytes=asset["bytes"], sha256=asset["sha256"], baseVersionCode=30286,
                baseImageSha256=plan["images"]["base"]["image"]["sha256"]))))


class Network:
    def __init__(self, plan, out):
        self.plan, self.out = plan, h.fresh(out)
        self.env = h.environment(out)
        self.server = self.thread = self.tunnel = self.log_handler = None

    def start(self):
        cfg = service_config(self.plan, "https://runtime-required.invalid")
        state = service.V2ServiceState(cfg, str(h.ROOT))
        logger = logging.getLogger("p34-live-" + str(self.out))
        logger.setLevel(logging.INFO)
        logger.propagate = False
        self.log_handler = logging.FileHandler(h.checked(self.out / "http.log"), mode="x", encoding="utf-8")
        logger.addHandler(self.log_handler)
        handler = type("BoundReferenceHandler", (service.P33RequestHandler,), dict(state=state, log=logger))
        self.server = service.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.server.daemon_threads = True
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.tunnel = h.Process(self.out, "https-tunnel", [h.pinned(self.plan["tools"]["cloudflared"]),
            "tunnel", "--no-autoupdate", "--protocol", "quic", "--edge-ip-version", "4",
            "--metrics", "127.0.0.1:0", "--url", "http://127.0.0.1:%d" % self.server.server_address[1]], self.env)
        def ready():
            h.require(self.tunnel.alive(), "HTTPS tunnel stopped before readiness")
            text = self.tunnel.paths["stderr"].read_text(encoding="utf-8", errors="replace")
            urls = set(re.findall(r"https://[a-z0-9-]+\.trycloudflare\.com", text))
            h.require(len(urls) <= 1, "ambiguous HTTPS endpoint")
            return next(iter(urls)) if urls else None
        origin = h.wait_for(ready, 90)
        cfg["publicBaseUrl"] = state.public_base_url = origin
        h.save(self.out / "service-config.json", cfg)
        query = dict(appId="trace", deviceModel="e-track-at32f435", channel="stable", currentVersionCode=30286,
            currentImageSha=self.plan["images"]["base"]["image"]["sha256"], hardwareRevision=1,
            layoutId=1, bootVersion=1, protocolVersion=1, appVersionCode=86)
        opener = build_opener(ProxyHandler({}))
        with opener.open(origin + service.LATEST_PATH + "?" + urlencode(query), timeout=20) as response:
            body = json.load(response)
        asset = body.get("asset", {})
        h.require(body.get("updateAvailable") is True and asset.get("kind") == "patch" and
            asset.get("baseImageSha256") == query["currentImageSha"] and
            asset.get("sha256") == self.plan["package"]["sha256"] and
            asset.get("sizeBytes") == self.plan["package"]["bytes"] and
            urlsplit(asset.get("downloadUrl", "")).hostname == urlsplit(origin).hostname, "HTTPS metadata identity")
        with opener.open(asset["downloadUrl"], timeout=30) as response:
            downloaded = response.read(self.plan["package"]["bytes"] + 1)
        h.require(downloaded == h.pinned(self.plan["package"]).read_bytes(), "HTTPS download original bytes mismatch")
        h.raw(self.out / "https-package.etu", downloaded)
        h.save(self.out / "ready.json", dict(origin=origin, package=h.record(self.out / "https-package.etu"),
            service_config=h.record(self.out / "service-config.json"), local_port=self.server.server_address[1]))
        return origin

    def close(self):
        if self.tunnel:
            self.tunnel.close("planned_service_close")
        if self.server:
            self.server.shutdown()
            self.server.server_close()
        if self.thread:
            self.thread.join(timeout=5)
            h.require(not self.thread.is_alive(), "HTTP thread still live")
        if self.log_handler:
            self.log_handler.close()
        h.save(self.out / "closed.json", dict(thread_closed=not self.thread or not self.thread.is_alive(),
            tunnel_closed=not self.tunnel or not self.tunnel.alive()))


class Phone:
    def __init__(self, plan, out, seconds):
        self.plan, self.out = plan, h.fresh(out)
        self.env = h.environment(out, plan["adb_key"])
        self.port, self.serial, self.pkg = plan["adb_port"], plan["phone_serial"], plan["app_id"]
        self.base = [str(h.pinned(plan["tools"]["adb"])), "-H", "127.0.0.1", "-P", str(self.port), "-s", self.serial]
        self.deadline, self.count, self.server = time.monotonic() + seconds, 0, None
        self.capture = self.pid = None

    def start(self, *, verify_apk=True):
        h.require(not h.listening(self.port), "ADB port already owned; no global server fallback")
        self.server = h.Process(self.out, "adb-server", [self.base[0], "-P", str(self.port), "nodaemon", "server"], self.env)
        h.wait_for(lambda: self.server.alive() and h.listening(self.port), 10)
        h.require(self.cmd(["get-serialno"]).strip().decode() == self.serial and
            self.cmd(["shell", "getprop", "ro.product.model"]).strip().decode() == self.plan["phone_model"], "wrong phone")
        if verify_apk:
            self.installed()

    def cmd(self, args, *, stdin=None, seconds=30, success_codes=(0,)):
        h.require(self.server and self.server.alive() and h.listening(self.port), "private ADB owner not live")
        h.require(time.monotonic() + seconds + 5 < self.deadline, "insufficient private ADB lifetime")
        self.count += 1
        # adb joins shell/exec arguments; explicitly quote the remote shell layer.
        if args[0] in ("shell", "exec-out", "exec-in"):
            args = [args[0], " ".join(shlex.quote(str(part)) for part in args[1:])]
        result = h.command(self.out, "adb-%05d" % self.count, self.base + list(map(str, args)), self.env,
                           seconds=seconds, stdin=stdin, success_codes=success_codes)
        h.require(self.server.alive() and h.listening(self.port), "private ADB owner changed during command; reconcile")
        return result

    def installed(self):
        packages = self.cmd(["shell", "pm", "list", "packages", self.pkg]).decode().strip()
        h.require(packages == "package:" + self.pkg, "required diagnostic APK missing; use the explicit installation action")
        text = self.cmd(["shell", "pm", "path", self.pkg]).decode().strip()
        h.require(re.fullmatch(r"package:/data/app/[A-Za-z0-9/_.=+~-]+/base\.apk", text), "ambiguous APK path")
        digest = self.cmd(["shell", "sha256sum", text[8:]]).decode().split()[0]
        h.require(digest == self.plan["apk"]["sha256"], "installed APK differs; do not overwrite blindly")

    def install(self):
        self.start(verify_apk=False)
        packages = self.cmd(["shell", "pm", "list", "packages", self.pkg]).decode().strip()
        if packages:
            h.require(packages == "package:" + self.pkg, "ambiguous APK identity")
            text = self.cmd(["shell", "pm", "path", self.pkg]).decode().strip()
            h.require(re.fullmatch(r"package:/data/app/[A-Za-z0-9/_.=+~-]+/base\.apk", text), "APK path")
            digest = self.cmd(["shell", "sha256sum", text[8:]]).decode().split()[0]
            if digest == self.plan["apk"]["sha256"]:
                return self.installed()
            h.require(digest in self.plan["replace_apk_sha256"], "foreign APK; no replacement")
            for capture in self.captures():
                health = self.health(capture)
                h.require(health.get("upgradeStarts") == health.get("upgradeEnds"), "active/unknown old upgrade")
        result = self.cmd(["install", "-r", "--no-streaming", h.pinned(self.plan["apk"])], seconds=180)
        h.require(result.strip().splitlines()[-1:] == [b"Success"], "APK installation result unknown")
        self.installed()

    def safe_remote(self, remote):
        h.require(re.fullmatch(r"(?:files|app_flutter)(?:/[A-Za-z0-9_.-]+)*", remote) and
                  not {".", ".."} & set(remote.split("/")), "unsafe App path")
        root = self.cmd(["exec-out", "run-as", self.pkg, "readlink", "-f", "."]).decode().strip()
        h.require(root in ("/data/user/0/" + self.pkg, "/data/data/" + self.pkg), "foreign App root")
        checks = []
        for n in range(1, len(remote.split("/")) + 1):
            part = "/".join(remote.split("/")[:n])
            checks.append("test ! -L %s || exit 41; if test -e %s; then test \"$(readlink -f %s)\" = %s || exit 42; fi" %
                          (part, part, part, root + "/" + part))
        self.cmd(["exec-out", "run-as", self.pkg, "sh", "-c", "; ".join(checks)])

    def exists(self, remote):
        self.safe_remote(remote)
        raw = self.cmd(["exec-out", "run-as", self.pkg, "sh", "-c",
            "if test -e " + remote + "; then printf yes; else printf no; fi"])
        h.require(raw in (b"yes", b"no"), "ambiguous App existence result")
        return raw == b"yes"

    def file(self, remote, limit=64 * 1024 * 1024 + 8192, *, allow_empty=False, prefix=False):
        self.safe_remote(remote)
        size = self.cmd(["exec-out", "run-as", self.pkg, "stat", "-c", "%s", remote]).strip()
        h.require(size.isdigit() and (0 if allow_empty else 1) <= int(size) <= limit, "App file size/missing original")
        read = ["head", "-c", str(int(size)), remote] if prefix else ["cat", remote]
        data = self.cmd(["exec-out", "run-as", self.pkg, *read], seconds=60)
        h.require(len(data) == int(size), "App file changed during read")
        return data

    def file_stamp(self, remote):
        self.safe_remote(remote)
        stamp = self.cmd(["exec-out", "run-as", self.pkg, "stat", "-c", "%d:%i:%s:%Y:%Z", remote]).strip().decode()
        h.require(re.fullmatch(r"\d+:\d+:\d+:\d+:\d+", stamp), "invalid file identity stamp")
        return stamp

    def downloaded(self, remote, previous_stamp):
        h.require(self.health(self.capture).get("upgradeStarts") == 0, "transfer started before qualification")
        if not self.exists(remote) or self.file_stamp(remote) == previous_stamp:
            return False
        prefix = self.file("files/p34-observations/" + self.capture + "/events.jsonl", prefix=True)
        lines = prefix.splitlines() if prefix.endswith(b"\n") else prefix.splitlines()[:-1]
        rows = [json.loads(line) for line in lines]
        h.require(rows and rows[0].get("pid") == self.pid and rows[0].get("captureId") == self.capture,
                  "query belongs to another App process/capture")
        if not any(re.fullmatch(r"OTA_LINK_SAMPLE label=query kind=get_info us=\d+ ok=1", row.get("message", "")) for row in rows):
            return False
        data = self.file(remote, self.plan["package"]["bytes"] + 1)
        h.require(data == h.pinned(self.plan["package"]).read_bytes(), "phone downloaded different bytes")
        h.raw(self.out / "downloaded.etu", data)
        h.raw(self.out / "query-events.jsonl", prefix)
        h.save(self.out / "downloaded.json", dict(previous_stamp=previous_stamp,
            current_stamp=self.file_stamp(remote), fresh_query=True,
            package=h.record(self.out / "downloaded.etu"), query_prefix=h.record(self.out / "query-events.jsonl")))
        return True

    def captures(self):
        remote = "files/p34-observations"
        if not self.exists(remote):
            return set()
        names = self.cmd(["exec-out", "run-as", self.pkg, "ls", "-1", remote]).decode().splitlines()
        h.require(len(names) <= 8 and all(re.fullmatch(r"\d{13,20}-[0-9a-f]{24}", n) for n in names), "unknown capture directory")
        return set(names)

    def provision(self, cfg, previous_cell=None):
        previous = self.captures()
        runtime = "files/p34-experiment.json"
        if self.exists(runtime):
            raw = self.file(runtime, 8192)
            owned = set(self.plan["owned_configs"])
            if previous_cell is not None:
                previous_cell = h.checked(previous_cell)
                closed = h.read_json(previous_cell / "result.json")
                h.require(closed.get("action") == "phone" and closed.get("tool_operations_completed") is True and
                    not (previous_cell / "failed.json").exists(), "previous cell not fully closed")
                receipt = h.read_json(h.pinned(closed["phone_capture"]))
                h.require(receipt.get("remote_pruned") is True and receipt.get("apk_sha256") == self.plan["apk"]["sha256"],
                          "previous capture ownership/closure mismatch")
                for item in receipt["originals"]:
                    h.pinned(item)
                owned.add(h.record(h.pinned(receipt["runtime"]))["sha256"])
            h.require(hashlib.sha256(raw).hexdigest() in owned, "unknown runtime config; collect/reconcile first")
            h.raw(self.out / "previous-runtime.json", raw)
        for name in previous:
            health = json.loads(self.file("files/p34-observations/" + name + "/health.json", 8192))
            h.require(health.get("upgradeStarts", 0) == health.get("upgradeEnds", 0), "active/unknown App transfer; no stop/restart")
        h.require(len(previous) < 8, "App capture store full; archive verified owned captures first")
        self.cmd(["shell", "am", "force-stop", self.pkg])
        h.require(not self.cmd(["shell", "pidof", self.pkg], success_codes=(0, 1)).strip(), "App stop outcome unknown")
        encoded = (json.dumps(cfg, sort_keys=True, separators=(",", ":")) + "\n").encode()
        h.raw(self.out / "runtime.json", encoded)
        self.safe_remote("files")
        self.cmd(["exec-out", "run-as", self.pkg, "mkdir", "-p", "files"])
        self.safe_remote(runtime)
        self.cmd(["exec-in", "run-as", self.pkg, "sh", "-c", "cat > " + runtime], stdin=encoded)
        h.require(self.file(runtime, 8192) == encoded, "runtime write/readback mismatch")
        component = self.cmd(["shell", "cmd", "package", "resolve-activity", "--brief", self.pkg]).decode().strip().splitlines()[-1]
        h.require(component.startswith(self.pkg + "/") and re.fullmatch(r"[A-Za-z0-9_./]+", component), "App launch component")
        self.cmd(["shell", "am", "start", "-W", "-n", component], seconds=45)
        pid = self.cmd(["shell", "pidof", self.pkg]).strip()
        h.require(pid.isdigit(), "one new App process required")
        def new_capture():
            names = self.captures() - previous
            h.require(len(names) <= 1, "ambiguous new App capture")
            return next(iter(names)) if names else None
        capture = h.wait_for(new_capture, 20)
        self.pid, self.capture = int(pid), capture
        h.save(self.out / "launched.json", dict(pid=int(pid), capture=capture, config=h.record(self.out / "runtime.json"), apk=self.plan["apk"]))
        return int(pid), capture

    def health(self, capture):
        return json.loads(self.file("files/p34-observations/" + capture + "/health.json", 8192))

    def finished(self, pid, capture, cfg):
        remote = "files/p34-observations/" + capture
        health = self.health(capture)
        h.require(health.get("upgradeStarts") == health.get("upgradeEnds") == 1, "not one sealed upgrade")
        names = self.cmd(["exec-out", "run-as", self.pkg, "ls", "-1", remote]).decode().splitlines()
        snapshots = sorted(n for n in names if re.fullmatch(r"snapshot-[1-4]\.jsonl", n))
        h.require(snapshots, "finished snapshot missing; never replay a successful OTA")
        raw = self.file(remote + "/" + snapshots[-1])
        path = self.out / "snapshot.jsonl"
        h.raw(path, raw)
        value = acceptance_stats.inspect(raw, self.plan["sentinel"], self.plan["ble_address"])
        rows = [json.loads(line) for line in raw.splitlines()]
        h.require(rows[0].get("pid") == pid and rows[0].get("captureId") == capture, "snapshot process/capture identity")
        stamps = [json.loads(row["message"][len("OTA_EXPERIMENT "):]) for row in rows
                  if isinstance(row.get("message"), str) and row["message"].startswith("OTA_EXPERIMENT ")]
        wanted = hashlib.sha256((self.out / "runtime.json").read_bytes()).hexdigest()
        h.require(stamps and all(s.get("configSha256") == wanted and s.get("runId") == cfg["runId"] for s in stamps),
                  "snapshot does not consume this runtime config")
        h.require(value["parameters"]["input"]["packageSha256"] == self.plan["package"]["sha256"], "wrong observed package")
        h.save(self.out / "statistics.json", value)
        return value

    def archive_capture(self):
        """Only this new, finished capture; preserve all bytes before exact unlink."""
        h.require(self.capture is not None and (self.out / "statistics.json").is_file(), "unverified capture cannot be pruned")
        health = self.health(self.capture)
        h.require(health.get("upgradeStarts") == health.get("upgradeEnds") == 1, "capture still active")
        h.require(self.cmd(["shell", "pidof", self.pkg]).strip() == str(self.pid).encode(), "App process changed")
        self.cmd(["shell", "am", "force-stop", self.pkg])
        h.require(not self.cmd(["shell", "pidof", self.pkg], success_codes=(0, 1)).strip(), "App stop unconfirmed")
        remote = "files/p34-observations/" + self.capture
        self.safe_remote(remote)
        names = sorted(self.cmd(["exec-out", "run-as", self.pkg, "ls", "-1", remote]).decode().splitlines())
        h.require({"events.jsonl", "health.json"} <= set(names) and len(names) <= 7 and
            all(re.fullmatch(r"events\.jsonl|health\.json(?:\.tmp)?|snapshot-[1-4]\.jsonl", name) for name in names),
            "unknown capture contents; do not prune")
        originals = []
        for name in names:
            data = self.file(remote + "/" + name, allow_empty=True)
            item = h.raw(self.out / "archive" / name, data)
            digest = self.cmd(["exec-out", "run-as", self.pkg, "sha256sum", remote + "/" + name]).decode().split()[0]
            h.require(digest == item["sha256"], "remote archive readback mismatch")
            originals.append(item)
        h.save(self.out / "archived.json", dict(capture=self.capture, originals=originals))
        for name, item in zip(names, originals):
            self.safe_remote(remote + "/" + name)
            digest = self.cmd(["exec-out", "run-as", self.pkg, "sha256sum", remote + "/" + name]).decode().split()[0]
            h.require(digest == item["sha256"], "capture changed before bounded prune")
            h.pinned(item)
            self.cmd(["exec-out", "run-as", self.pkg, "rm", remote + "/" + name])
        self.cmd(["exec-out", "run-as", self.pkg, "rmdir", remote])
        h.require(not self.exists(remote), "prune result unknown")
        h.save(self.out / "closed-capture.json", dict(capture=self.capture, pid=self.pid,
            originals=originals, runtime=h.record(self.out / "runtime.json"), remote_pruned=True,
            apk_sha256=self.plan["apk"]["sha256"]))

    def salvage(self):
        """Read existing originals after failure, without restarting or repeating OTA."""
        if self.capture is None or self.server is None or not self.server.alive():
            return
        remote = "files/p34-observations/" + self.capture
        collected, errors = [], []
        for name in ("health.json", "events.jsonl", *("snapshot-%d.jsonl" % n for n in range(1, 5))):
            try:
                if self.exists(remote + "/" + name):
                    collected.append(h.raw(self.out / "salvage" / name, self.file(remote + "/" + name, allow_empty=True)))
            except Exception as error:
                errors.append(dict(file=name, error=str(error)))
        h.save(self.out / "salvage.json", dict(originals=collected, errors=errors, no_restart_or_ota=True))

    def close(self):
        if self.server:
            try:
                if self.server.alive() and h.listening(self.port):
                    h.command(self.out, "adb-stop", [self.base[0], "-H", "127.0.0.1", "-P", str(self.port), "kill-server"], self.env, seconds=10)
            finally:
                self.server.close("planned_private_adb_close")
            h.require(not h.listening(self.port), "ADB port still live; do not claim closure")
        h.save(self.out / "closed.json", dict(private_port=self.port, listening=h.listening(self.port),
            server_closed=not self.server or not self.server.alive()))
