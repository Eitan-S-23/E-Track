"""Group-aware prefix backend: reuse proved primitives without replaying old controllers.

The receiver/target pair and served package come from the selected comparison group
(`screen` for the retained 30214 lineage, `n03-a`/`n03-b` for the paired 32 KiB probe),
so one backend drives both N03 arms without inlining a group literal."""
from __future__ import annotations

from contextlib import contextmanager
import copy
import datetime as dt
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import runpy
import struct
import time
import types
import urllib.error
import urllib.parse
import urllib.request
import zlib

import p34_session as cli

# The served package name, receiver version and target version all come from the
# selected comparison group; nothing in this backend may inline a group literal.
AUTHORIZATION = "native-authorization.json"


def idle_capture(value):
    health = value.get("health")
    return bool(health and health.get("healthy") is True and health.get("lost") == 0 and
                health.get("error") is None and health.get("upgradeStarts") == health.get("upgradeEnds") == 0 and
                health.get("outcome") is None and not value.get("snapshots"))


def require_owned_config(config, known):
    cli.require(config is None or hashlib.sha256(config).hexdigest() in known,
                "existing App configuration is not owned by this profile/session; collect before changing it")


# The App writes one capture directory per start, refuses to open a new one once this many
# exist, and has no delete path or UI of its own. Freeing room is therefore a host-side,
# explicitly named operation that must never remove evidence the host has not preserved.
STORE_LIMIT = 8
CAPTURE_NAME = re.compile(r"\d{13,20}-[0-9a-f]{24}")
SNAPSHOT_NAME = re.compile(r"snapshot-[1-4]\.jsonl")
APP_EVIDENCE_LEAVES = ("app", "previous-app", "queries")


# Same bounded offsets as the frozen readiness window. A quick tunnel answers 530 while an
# edge connection re-registers (20260926T123854-90800/s01), which is service-side transience
# like 502-504; strict metadata or package-byte mismatches still fail on the first attempt.
READY_OFFSETS = (0, 15, 45, 90)
TUNNEL_TRANSIENT_STATUS = frozenset({530})


def wait_ready(check, record, transient, *, clock=time.monotonic, sleep=time.sleep):
    started = clock()
    for attempt, offset in enumerate(READY_OFFSETS, 1):
        sleep(max(0, started + offset - clock()))
        try:
            value = check()
        except Exception as error:
            status = error.code if isinstance(error, urllib.error.HTTPError) else None
            record(dict(attempt=attempt, elapsed=clock() - started, result="FAILED",
                        error=type(error).__name__, http_status=status))
            if attempt == len(READY_OFFSETS) or not (isinstance(error, TimeoutError) or
                    status in TUNNEL_TRANSIENT_STATUS or transient(error)):
                raise
        else:
            record(dict(attempt=attempt, elapsed=clock() - started, result="VERIFIED"))
            return value


def terminal_capture(health):
    """A capture whose transfer ended without completing and lost nothing."""
    return (health.get("healthy") is True and health.get("lost") == 0 and health.get("error") is None and
            health.get("upgradeStarts") == health.get("upgradeEnds") == 1 and
            health.get("outcome") == "not-completed")


def capture_state(health):
    if terminal_capture(health):
        return "terminal-not-completed"
    return "idle" if idle_capture(dict(health=health)) else "active-or-unknown"


def verify_experiment(capture, messages, expected, sha):
    item = capture.experiment_record(messages.splitlines())
    keys = ("schema", "runId", "requestedBaud", "reuseGatt", "withoutResponse", "packageBytes",
            "packageSha256", "currentVersionCode", "currentImageSha256", "targetVersionCode",
            "targetImageSha256", "senderWindowSegments", "transferMode", "prefixBytes")
    if expected.get("schema") == 3:
        reconnect = cli.load_module("p34_reconnect_observation", Path(__file__).with_name("p34_reconnect_profile.py"))
        reconnect.validate_cadence(expected)
        keys += tuple(reconnect.CADENCE)
    cli.require(item.get("configSha256") == sha and
                capture.same_device(item.get("deviceAddress"), expected["target"]) and
                item.get("endpointHost") == urllib.parse.urlsplit(expected["firmwareLatestUrl"]).hostname and
                all(type(item.get(key)) is type(expected[key]) and item[key] == expected[key] for key in keys),
                "App runtime config differs from this cell")
    return item


def verify_full_snapshot(capture, raw, expected, config_sha, pid, sentinel):
    summary, messages = capture.verify(raw, sentinel=sentinel, target=expected["target"])
    cli.require(expected["transferMode"] == "full" and expected["prefixBytes"] == 0 and
                summary["outcome"] == "completed" and summary["pid"] == pid and
                capture.same_device(summary["input"]["deviceAddress"], expected["target"]) and
                all(summary["input"][key] == expected[key] for key in
                    ("packageSha256", "packageBytes", "currentVersionCode", "targetVersionCode",
                     "currentImageSha256", "targetImageSha256")), "full installation snapshot/input mismatch")
    experiment = verify_experiment(capture, messages, expected, config_sha)
    cli.require(not any(line.startswith("OTA_PREFIX_PROBE ") for line in messages.splitlines()),
                "a prefix verdict is not an installation")
    return summary, messages, experiment


def bind_flash_gate(profile, symbol):
    item = profile["map"]
    cli.require(cli.record(item["path"]) == item, "receiver MAP bytes changed")
    text = Path(item["path"]).read_text(encoding="utf-8")
    return dict(disabled=symbol(text, "data", "_ZL19g_qspi_ota_disabled", 1, "HAL_W25Q128.cpp"),
                jedec=symbol(text, "bss", "_ZL15g_qspi_jedec_id", 4, "HAL_W25Q128.cpp"),
                boot_clock_ok=symbol(text, "bss", "_ZL14s_p34_clock_ok", 4, "HAL_Bluetooth.cpp"))


def same_terminal(live, previous, *, idle_abort_sequence=False):
    keys = ("state", "session_id", "next_session_id", "expected_seq", "total_len", "package_sha256",
            "target_vcode", "pkg_kind", "durable_off", "segment_bitmap", "resumed", "complete",
            "last_ack_cmd", "last_ack_seq", "receiver", "isr_active", "parser_bad_frames")
    if idle_abort_sequence:
        # An idle ABORT echoes the caller's seq without starting a receive/profile
        # generation. This exception is only for the no-BEGIN prestart recovery.
        cli.require(all(state["session"]["state"] == state["session"]["session_id"] == 0 and
                        state["session"]["last_ack_cmd"] == 0x84 and state["profile"]["schema"] == 2 and
                        state["profile"]["ready"] == 1 and state["profile"]["active"] == 0 and
                        state["profile"]["terminal"] == 1 for state in (live, previous)),
                    "prestart comparison requires an unchanged idle ABORT generation")
        keys = tuple(key for key in keys if key != "last_ack_seq")
    cli.require(all(live["session"][key] == previous["session"][key] for key in keys) and
                live["profile_raw"]["sha256"] == previous["profile_raw"]["sha256"] and
                0 < ((live["tick"] - previous["tick"]) & 0xFFFFFFFF) < 0x80000000,
                "MCU generation/terminal changed; preserve the sample, do not replay the transfer")


def pending_health_bytes(p, package, remote):
    """Allow an empty interrupted health write without weakening normal log reads."""
    parts = remote.split("/")
    cli.require(len(parts) == 4 and parts[:2] == ["files", "p34-observations"] and
                CAPTURE_NAME.fullmatch(parts[2]) and parts[3] == "health.json.tmp", "unexpected pending health path")
    size = p.command(["exec-out", "run-as", package, "stat", "-c", "%s", remote]).strip()
    cli.require(size.isdigit() and 0 <= int(size) <= 8192, "pending health file exceeds its bound")
    raw = p.command(["exec-out", "run-as", package, "head", "-c", "8193", remote], timeout=30, binary=True)
    cli.require(len(raw) == int(size) and len(raw) <= 8192, "pending health size changed during read")
    return raw


def checked_phone_path(c, p, relative, *, new_leaf=False):
    """Reject redirected App paths before a named deletion or configuration move."""
    path = PurePosixPath(relative)
    cli.require(not path.is_absolute() and path.parts[0] == "files" and ".." not in path.parts,
                "invalid App-relative mutation path")
    root = p.command(["exec-out", "run-as", c.PKG, "readlink", "-f", "."]).strip()
    cli.require(root in ("/data/user/0/" + c.PKG, "/data/data/" + c.PKG), "unexpected App data root")
    checked = path.parent if new_leaf else path
    actual = p.command(["exec-out", "run-as", c.PKG, "readlink", "-f", str(checked)]).strip()
    cli.require(actual == root + "/" + str(checked), "App mutation path is redirected or unresolved")
    return root + "/" + str(path)


def distinct_journal(data, target, known_packages):
    """Identify old metadata, not a zero or reusable target staging state."""
    cli.require(len(data) == 4096, "old staging journal length")
    etrj = data[0x40:0x6c]
    total = struct.unpack_from("<I", etrj, 36)[0]
    sha = etrj[4:36].hex()
    cli.require(etrj[:4] == b"ETRJ" and 0 < total <= 2093056 and
                struct.unpack_from("<I", etrj, 40)[0] == zlib.crc32(etrj[:40]) & 0xffffffff,
                "old staging ETRJ identity/CRC invalid; reconcile before BEGIN")
    cli.require(sha != target["sha256"], "same package may resume; no browser fallback or replay")
    cli.require(any(item["sha256"] == sha and item["bytes"] == total for item in known_packages),
                "old staging package is unknown; reconcile before BEGIN")
    return dict(sha256=sha, bytes=total)


def zero_before_data(messages, label="prefix-probe", total=None):
    """Require original zero progress; full mode also proves every DATA segment."""
    cli.require(label in ("prefix-probe", "upgrade"), "unbound transfer label")
    lines = messages.splitlines()
    durable = [(n, int(match[1])) for n, line in enumerate(lines)
               if (match := re.fullmatch(r"OTA_LINK_SAMPLE label=" + label + r" kind=durable us=\d+ off=(\d+)", line))]
    data = [n for n, line in enumerate(lines) if re.fullmatch(
        r"OTA_LINK_SAMPLE label=" + label + r" kind=segment_first_send us=\d+ off=\d+ len=128", line)]
    cli.require(durable and data and durable[0][1] == 0 and durable[0][0] < data[0] and
                sum(offset == 0 for _, offset in durable) == 1,
                "original zero durable must precede DATA; not a fresh-start prefix")
    if label == "upgrade":
        cli.require(type(total) is int and total > 0, "full DATA coverage needs its bound total")
        sent = [(int(match[1]), int(match[2])) for line in lines if (match := re.fullmatch(
            r"OTA_LINK_SAMPLE label=upgrade kind=segment_first_send us=\d+ off=(\d+) len=(\d+)", line))]
        cli.require(sent == [(offset, min(128, total - offset)) for offset in range(0, total, 128)],
                    "full DATA coverage is not one zero-start complete package")
    return dict(source=("ORIGINAL_ZERO_DURABLE_AND_COMPLETE_DATA_COVERAGE" if label == "upgrade" else
                       "PINNED_APP_BEGIN_ACK_GUARD_AND_ORIGINAL_ZERO_DURABLE"), native_zero_sample=False)


def patch_service(c):
    """Isolated fixed-PATCH adapter; never mutate the frozen FULL service module."""
    service = c.service
    receiver, base_sha = c.receiver_version, c.receiver_image_sha
    target_version, target_sha = c.target_version, c.target["sha256"]
    key = c.release_key
    expected = dict(assetId=key + "-patch", kind="patch", fileName=c.served_name,
        sha256=c.screen["sha256"], sizeBytes=c.screen["bytes"], path=c.screen["path"],
        baseVersionCode=receiver, baseImageSha256=base_sha)

    class BoundPatchState(service.V2ServiceState):
        def __init__(self, config, config_dir, active_release=None, now_fn=time.time):
            cli.require(c.package_kind == "patch" and set(config["releases"]) == {key} and
                        active_release in (None, key), "PATCH service release scope changed")
            release = config["releases"][key]
            cli.require(release["asset"] == expected and release["versionCode"] == target_version and
                        release["targetImageSha256"] == target_sha and
                        release["versionName"] == c.target_identity["version_name"], "PATCH service asset/base/target changed")
            # Reuse the legacy service's common metadata and byte-hash validation
            # on a private copy, then expose only the actual manifest-bound kind.
            compatible = copy.deepcopy(config)
            compatible["releases"][key]["asset"].update(kind="full", baseVersionCode=0, baseImageSha256=None)
            super().__init__(compatible, config_dir, active_release=active_release, now_fn=now_fn)
            asset = self.releases[key].asset
            asset.kind, asset.base_version_code, asset.base_image_sha256 = "patch", receiver, base_sha

        def _parse_latest_params(self, query_pairs, request_id):
            pairs = list(query_pairs)
            params = super()._parse_latest_params(pairs, request_id)
            # The legacy FULL parser validates SHA syntax but omits it from the
            # result. Its duplicate/required checks have already validated pairs.
            if params["currentVersionCode"] != receiver or dict(pairs)["currentImageSha"] != base_sha:
                raise service.ServiceError(400, "INVALID_PARAMETER",
                    "fixed diagnostic PATCH requires the bound receiver image", request_id=request_id)
            return params

    return types.SimpleNamespace(**dict(vars(service), V2ServiceState=BoundPatchState))


def tunnel_protocol_adapter(phone, root, protocol):
    """Adapt only this private module's launcher input; frozen helpers stay intact."""
    cli.require(protocol == "quic", "only the diagnosed QUIC alternative is supported")
    tunnel = str(root / ".cache/worktrees/p3-4-link-stats/.cache/p3-4-single-ota-20260921/bin/cloudflared.exe")
    original = phone.subprocess

    class Input:
        def __init__(self, stream):
            self.stream = stream

        def __getattr__(self, key):
            return getattr(self.stream, key)

        def write(self, data):
            args = json.loads(data)
            if isinstance(args, list) and args and args[0] == tunnel:
                cli.require(len(args) == 11 and args[1:10] == ["tunnel", "--no-autoupdate", "--protocol", "http2",
                    "--edge-ip-version", "4", "--metrics", "127.0.0.1:0", "--url"] and
                    re.fullmatch(r"http://127\.0\.0\.1:[0-9]{1,5}", args[10]), "unexpected frozen tunnel launch shape")
                args[4] = protocol
                data = (json.dumps(args) + "\n").encode()
            return self.stream.write(data)

    def popen(*args, **kwargs):
        process = original.Popen(*args, **kwargs)
        if process.stdin is not None:
            process.stdin = Input(process.stdin)
        return process

    phone.subprocess = types.SimpleNamespace(**dict(vars(original), Popen=popen))


class Backend:
    def __init__(self, store, profile_path, profile, group="screen"):
        self.store, self.root = store, store.root
        self.profile_path, self.profile = profile_path, profile
        self.legacy = runpy.run_path(str(store.checked(store.root / profile["bootstrap"]["path"])))
        cli.require(self.legacy["ROOT"] == self.root, "retained artifact profile belongs to a different project root")
        core, groups = self.legacy["core"], self.legacy["core"]["GROUPS"]
        legacy_group = "n03-b" if group in cli.MEASURED_FULL_GROUPS else group
        cli.require(legacy_group in groups, "unknown comparison group; pick a declared receiver pairing")
        core["select_group"](legacy_group)
        self.group, self.spec = group, groups[legacy_group]
        if group == cli.NATIVE_DIAGNOSTIC_GROUP:
            cli.require(profile.get("native_diagnostic") is True, "native diagnostic profile flag missing")
            cli.require(profile.get("tunnel_protocol", "http2") in ("http2", "quic"), "undeclared tunnel protocol")
        if group == cli.SPEED16_GROUP:
            cli.require(profile.get("speed_window16") is True and profile.get("native_diagnostic") is False and
                        profile.get("tunnel_protocol") == "quic", "speed screening profile flags differ")
        if group == cli.SPEED32_GROUP:
            cli.require(profile.get("speed_window32") is True and profile.get("native_diagnostic") is False and
                        profile.get("tunnel_protocol") == "quic", "window-32 screening profile flags differ")
        if group in cli.PATCH32_GROUPS:
            cli.require(profile.get("patch32") is True and profile.get("native_diagnostic") is False and
                        profile.get("tunnel_protocol") == "quic", "PATCH32 profile flags differ")
        if group in cli.RECEIVE_GROUPS:
            cli.require(profile.get("receive_restore") is True and profile.get("native_diagnostic") is False and
                        profile.get("tunnel_protocol") == "quic", "receive-restore profile flags differ")
        if group in cli.ACK_GAP_GROUPS:
            cli.require(profile.get("ack_gap") is True and profile.get("native_diagnostic") is False and
                        profile.get("tunnel_protocol") == "quic", "ACK-gap diagnostic profile flag missing")
        if group == "ack-batch-bootstrap":
            cli.require(profile.get("ack_batch") is True, "ACK-batch diagnostic profile flag missing")
        if group in cli.NEW_BOOT_GROUPS:
            cli.require(profile.get("ack_batch") is True and profile.get("boot_copy") is True,
                        "explicit verified Boot-copy profile required")
        if group in (*cli.COST_GROUPS, *cli.ERASE_GROUPS):
            cli.require(profile.get("install_cost") is True, "explicit install-cost profile required")
        if group in cli.ERASE_GROUPS:
            cli.require(profile.get("block_erase") is True, "explicit block-erase profile required")
        if group == cli.RECONNECT_GROUP:
            cli.require(all(profile.get(k) is True for k in ("install_cost", "block_erase", "reconnect_probe")),
                        "explicit reconnect profile required")
        if group in cli.MEASURED_FULL_GROUPS:
            self.full_api = cli.load_module("p34_full_assets", self.root / "Tools/ota/p34_full_assets.py")
            self.spec = dict(self.spec, target_version=self.full_api.VERSION, served="full",
                served_name=self.full_api.SERVED_NAME, release_key=self.full_api.RELEASE_KEY,
                assets=self.root / self.full_api.RELATIVE)
            if group in cli.FULL_SUCCESSOR_GROUPS:
                self.window_api = cli.load_module("p34_window8_assets", self.root / "Tools/ota/p34_window8_assets.py")
                self.spec.update(receiver=self.window_api.RECEIVER, target_version=self.window_api.VERSION,
                    served_name=self.window_api.SERVED_NAME, release_key=self.window_api.RELEASE_KEY,
                    assets=self.root / self.window_api.RELATIVE)
                if group in cli.SUCCESSORS:
                    self.successor_api = cli.load_module("p34_successor_assets", self.root / "Tools/ota/p34_successor_assets.py")
                    self.spec.update(cli.SUCCESSORS[group])
                    self.spec["assets"] = self.root / self.spec["assets"]
                if group in cli.N04_LINEAGE_GROUPS:
                    self.successor_api = cli.load_module("p34_successor_assets", self.root / "Tools/ota/p34_successor_assets.py")
                    self.install_api = cli.load_module("p34_install_assets", self.root / "Tools/ota/p34_install_assets.py")
                    self.spec.update(({**cli.N04_GROUPS, **cli.ALL_PATCH_GROUPS})[group])
                    self.spec["assets"] = self.root / self.spec["assets"]
                    if group in cli.ALL_PATCH_GROUPS:
                        cli.require(profile.get("patch_group") == group, "PATCH profile belongs to another alternative")
                        self.patch_api = cli.patch_assets_api(store, group)
        self.served_name = self.spec["served_name"]
        self.receiver_version, self.target_version = self.spec["receiver"], self.spec["target_version"]
        self.authorization = store.checked(store.base / AUTHORIZATION)

    def context(self, out):
        api, base = self, self.legacy["core"]["Context"]
        class Context(base):
            def __init__(self):
                super().__init__()
                if api.group in cli.MEASURED_FULL_GROUPS:
                    expected = api.profile.get("receiver_assets" if api.group in cli.FULL_SUCCESSOR_GROUPS else "full_assets")
                    cli.require(cli.record(api.root / api.full_api.RELATIVE) == expected, "full asset manifest changed")
                    self.full_assets = api.full_api.load(self)
                    if api.group in cli.FULL_SUCCESSOR_GROUPS:
                        self.u_assets = self.full_assets
                        self.bindings = self.u_assets["target_bindings"]
                        self.receiver_version = api.window_api.RECEIVER
                        cli.require(cli.record(api.root / api.window_api.RELATIVE) == api.profile.get("window_assets"), "V asset manifest changed")
                        self.full_assets = api.window_api.load(self)
                        if api.group in (*cli.SUCCESSORS, *cli.N04_LINEAGE_GROUPS):
                            successor = cli.SUCCESSORS["n03-window8-repeat" if api.group in cli.N04_LINEAGE_GROUPS else api.group]
                            self.v_assets = self.previous_assets = self.full_assets
                            self.bindings = self.v_assets["target_bindings"]
                            self.receiver_version = successor["receiver"]
                            cli.require(cli.record(api.root / successor["assets"]) == api.profile.get("successor_assets"), "successor asset manifest changed")
                            self.full_assets = api.successor_api.load(self, successor)
                        if api.group in cli.N04_LINEAGE_GROUPS:
                            self.w_assets = self.full_assets
                            for name in cli.n04_asset_groups(api.group):
                                spec = cli.N04_GROUPS[name]
                                cli.require(cli.record(api.root / spec["assets"]) == api.profile.get("n04_assets", {}).get(name),
                                            "N04 asset manifest changed")
                            self.n04_prior_assets = []
                            for name in cli.n04_asset_groups(api.group):
                                if name != "n04-bootstrap":
                                    self.n04_prior_assets.append(self.full_assets)
                                self.previous_assets = self.full_assets
                                self.bindings = self.previous_assets["target_bindings"]
                                self.receiver_version = cli.N04_GROUPS[name]["receiver"]
                                self.full_assets = api.install_api.load(self, cli.N04_GROUPS[name])
                                if name == api.group:
                                    break
                            self.install_restore_expected = api.group != "n04-bootstrap"
                            if api.group in cli.ALL_PATCH_GROUPS:
                                cli.require(cli.record(api.root / api.patch_api.RELATIVE) == api.profile.get("patch_assets"),
                                            "prepared PATCH asset manifest changed")
                                for name in cli.patch_asset_groups(api.group):
                                    self.n04_prior_assets.append(self.full_assets)
                                    self.previous_assets = self.full_assets
                                    self.bindings = self.previous_assets["target_bindings"]
                                    self.receiver_version = cli.ALL_PATCH_GROUPS[name]["receiver"]
                                    loader = api.patch_api
                                    if (api.group in cli.RECEIVE_GROUPS and name in cli.PATCH32_GROUPS) or (
                                            api.group in cli.ACK_GAP_GROUPS and name != api.group):
                                        loader = cli.patch_assets_api(api.store, name)
                                        cli.require(cli.record(api.root / loader.RELATIVE) ==
                                                    api.profile.get("patch_prior_assets", {}).get(loader.RELATIVE),
                                                    "prior PATCH asset manifest changed")
                                    self.full_assets = loader.load_for_context(self, cli.ALL_PATCH_GROUPS[name])
                    self.group, self.spec = api.group, api.spec
                    self.receiver_version, self.target_version = api.receiver_version, api.target_version
                    self.served_name, self.release_key = api.served_name, api.spec["release_key"]
                    self.served = self.screen = self.full_assets["package"]
                    self.target, self.target_identity = self.full_assets["target"], self.full_assets["target_identity"]
                    self.screen_bytes = Path(self.screen["path"]).read_bytes()
                    self.package_kind = self.full_assets.get("package_kind", "full")
                    if self.package_kind == "patch":
                        self.service = patch_service(self)
                if api.group in cli.NEW_BOOT_GROUPS:
                    self.BOOT_SHA = self.bindings["whole_boot"]["sha256"]
                if api.group == cli.RECONNECT_GROUP:
                    reconnect = cli.load_module("p34_reconnect_context", api.root / "Tools/ota/p34_reconnect_profile.py")
                    cli.require(cli.record(api.root / reconnect.APK_REPORT) == api.profile.get("reconnect_apk"),
                                "reconnect APK manifest changed")
                    self.apk = reconnect.apk()
                    self.APK_SHA = self.apk["apk"]["sha256"]
                self.CELLS = cli.cells_for(api.group)
                self.OUT, self.host.OUT = out, out
                # The run directory holds the evidence; the operator's authorization
                # of this window is recorded once, outside the run, and only read.
                self.authorization = api.authorization
                self.envelope = cli.load_module("p34_observation", api.root / "Tools/ota/p34_observation.py")
                self.envelope.ROOT, self.envelope.checked = api.root, self.checked
                self.p.query.m = self.envelope
                gate = api.legacy["named"]["restored"]["clock"]["gate"]
                self.flash_addresses = bind_flash_gate(self.bindings["profile"], gate["symbol"])
            def sources(self):
                items = super().sources() + [cli.record(api.root / name) for name in (
                    "Tools/ota/p34_session.py", "Tools/ota/p34_session_backend.py",
                    "Tools/ota/p34_observation.py", "tests/ota/test_p34_session.py", "tests/ota/test_p34_observation.py")]
                if api.group in cli.MEASURED_FULL_GROUPS:
                    items += [cli.record(api.root / name) for name in ("Tools/ota/p34_full_assets.py",
                        "Tools/ota/p34_full_trace.py", "tests/ota/test_p34_full.py", api.full_api.RELATIVE)]
                    if api.group in cli.FULL_SUCCESSOR_GROUPS:
                        items += [cli.record(api.root / name) for name in ("Tools/ota/p34_window8_assets.py",
                            "tests/ota/test_p34_window8.py", api.window_api.RELATIVE)]
                    if api.group in (*cli.SUCCESSORS, *cli.N04_LINEAGE_GROUPS):
                        successor = cli.SUCCESSORS["n03-window8-repeat" if api.group in cli.N04_LINEAGE_GROUPS else api.group]
                        items += [cli.record(api.root / name) for name in ("Tools/ota/p34_successor_assets.py",
                            "tests/ota/test_p34_repeat.py", successor["assets"])]
                    if api.group in cli.N04_LINEAGE_GROUPS:
                        items += [cli.record(api.root / name) for name in ("Tools/ota/p34_install_assets.py",
                            "tests/ota/test_p34_install.py", api.install_api.BUILD)]
                        items += [cli.record(api.root / cli.N04_GROUPS[name]["assets"]) for name in cli.n04_asset_groups(api.group)]
                    if api.group in cli.ALL_PATCH_GROUPS:
                        items += [cli.record(api.root / name) for name in ("Tools/ota/p34_patch_assets.py",
                            "Tools/ota/p34_patch_preparation.py", "tests/ota/test_p34_patch_session.py",
                            api.patch_api.RELATIVE,
                            (".cache/p34-erase/build/result.json" if api.group == cli.RECONNECT_GROUP else api.patch_api.BUILD_REPORT))]
                    if api.group in cli.PATCH32_GROUPS:
                        items += [cli.record(api.root / name) for name in
                                  ("Tools/ota/p34_patch32_assets.py", "Tools/ota/p34_patch32_recovery.py",
                                   "tests/ota/test_p34_patch32.py")]
                    if api.group in cli.RECEIVE_GROUPS:
                        items += [cli.record(api.root / name) for name in
                                   ("Tools/ota/p34_receive_assets.py", "tests/ota/test_p34_receive.py",
                                    "Tools/ota/p34_cached_resume.py", "tests/ota/test_p34_cached_resume.py",
                                   "Tools/ota/p34_patch32_assets.py", ".cache/p34-patch32/assets/result.json")]
                    if api.group in cli.ACK_GAP_GROUPS:
                        items += [cli.record(api.root / name) for name in
                                  ("Tools/ota/p34_ack_gap_assets.py", "tests/ota/test_p34_ack_gap_assets.py",
                                   "Tools/ota/p34_ack_gap.h", "tests/ota/test_p34_ack_gap.cpp",
                                   "Tools/ota/p34_receive_assets.py", "tests/ota/test_p34_receive.py",
                                   "Tools/ota/p34_patch32_assets.py", ".cache/p34-patch32/assets/result.json",
                                   ".cache/p34-receive-screen/assets/result.json",
                                   ".cache/p34-target50/assets/result.json",
                                   ".cache/p34-target50/session-serial-w1/result.json",
                                   ".cache/p34-target50/session-serial-w1/mcu/closure.json",
                                   ".cache/p34-target50/session-serial-w1/owner/closed.json")]
                    if api.group in ("ack-batch-bootstrap", *cli.NEW_BOOT_GROUPS):
                        items += [cli.record(api.root / name) for name in (
                            "Tools/ota/p34_ack_batch_assets.py", "tests/ota/test_p34_ack_batch_assets.py",
                            "Tools/ota/p34_ack_batch.h", "tests/ota/test_p34_ack_batch.cpp",
                            ".cache/p34ag/assets/session-assets.json", ".cache/p34ab/tests/result.json",
                            ".cache/p34ag/screen/assets/result.json", ".cache/p34ag/screen/session-w31/result.json",
                            ".cache/p34ag/screen/session-w31/mcu/closure.json",
                            ".cache/p34ag/screen/session-w31/owner/closed.json")]
                    if api.group in cli.NEW_BOOT_GROUPS:
                        items += [cli.record(api.root / name) for name in (
                            "Tools/ota/p34_boot_ota_assets.py", "tests/ota/test_p34_boot_ota.py",
                            ".cache/p34-boot/activation/result.json", ".cache/p34-boot/activation/plan.json",
                            ".cache/p34-boot/activation/after/result.json",
                            ".cache/p34-boot/preparation/candidate/boot/X-Track-Boot.map")]
                    if api.group in (*cli.COST_GROUPS, *cli.ERASE_GROUPS):
                        items += [cli.record(api.root / name) for name in (
                            "Tools/ota/p34_cost_assets.py", "Tools/ota/p34_install_cost.py",
                            "tests/ota/test_p34_cost_assets.py", ".cache/p34-cost/assets/result.json",
                            ".cache/p34-cost/build/result.json", ".cache/p34-cost/tests/result.json")]
                    if api.group in cli.ERASE_GROUPS:
                        items += [cli.record(api.root / name) for name in (
                            "Tools/ota/p34_erase_assets.py", "Tools/ota/p34_erase_candidate.py",
                            "tests/ota/test_p34_erase_assets.py", ".cache/p34-erase/assets/result.json",
                            ".cache/p34-erase/build/result.json", ".cache/p34-erase/build/source.json",
                            ".cache/p34-erase/build-review/result.json", ".cache/p34-erase/tests/r2/result.json")]
                if api.group == cli.NATIVE_DIAGNOSTIC_GROUP:
                    items += [cli.record(api.root / name) for name in
                              ("Tools/ota/p34_android_trace.py", "tests/ota/test_p34_android_trace.py")]
                if api.group == cli.SPEED16_GROUP:
                    items.append(cli.record(api.root / "tests/ota/test_p34_speed16.py"))
                if api.group == cli.SPEED32_GROUP:
                    items.append(cli.record(api.root / "tests/ota/test_p34_speed32.py"))
                    items.append(cli.record(api.root / "Tools/ota/p34_retirement_recovery.py"))
                if api.group in cli.ALL_PATCH_GROUPS:
                    items += [cli.record(api.root / name) for name in (
                        "Tools/ota/p34_historical_inputs.py", "tests/ota/test_p34_historical_inputs.py",
                        "Tools/ota/p34_patch_preparation.py", "Tools/ota/p34_patch_assets.py")]
                    historical = cli.load_module("p34_historical_source_pins", api.root / "Tools/ota/p34_historical_inputs.py")
                    items += [cli.record(api.root / pair[0]) for pair in historical.ARCHIVES.values()]
                if api.group == cli.RECONNECT_GROUP:
                    items += [cli.record(api.root / name) for name in (
                        "Tools/ota/p34_reconnect_profile.py", "Tools/ota/p34_reconnect_assets.py",
                        "tests/ota/test_p34_reconnect.py", ".cache/p34-reconnect/apk.json",
                        "Tools/ota/p34_erase_assets.py", ".cache/p34-erase/assets/result.json")]
                    items += [self.apk["apk"], *self.apk["host_reports"]]
                return sorted({item["path"]: item for item in items}.values(), key=lambda item: item["path"])
            def action(self, label, state, **values):
                with self.checked(getattr(self, "action_out", self.OUT) / "actions.jsonl").open("a", encoding="utf-8", newline="\n") as stream:
                    stream.write(json.dumps(dict(time=self.now(), cell=self.cell, id=label, state=state, **values)) + "\n")
                    stream.flush()
                    os.fsync(stream.fileno())
            def load(self, name, path):
                if Path(path) == self.HERE / "prefix_phone.py":
                    return api.phone(self, name)
                module = base.load(name, path)
                if Path(path) == self.HERE / "prefix_mcu.py":
                    parent = module.Mcu
                    class BoundMcu(parent):
                        def open(self):
                            value = super().open()
                            self.c.save(self.out / "receiver-admission.json", dict(result="BOUND_RECEIVER_ADMITTED",
                                receiver_version=self.c.receiver_version, image_sha256=self.c.receiver_image_sha,
                                map=self.c.bindings["profile"]["map"], addresses=self.c.flash_addresses,
                                flash_gate=self.c.record(self.out / "flash-admission.json")))
                            return value
                    module.Mcu = BoundMcu
                return module
        return Context()

    def preflight(self, c, out):
        for name in ("plan.json", "root-before.json", "actions.jsonl", "live-network.json", "network-result.json",
                     "network-stop.json", "network-owner", "runtime", "prestart-phone", "collections"):
            c.checked(out / name)
        for leaf in ("home", "appdata", "localappdata", "tmp", "home/config", "home/cache", "gh", "python", "gitconfig", "hooks"):
            c.checked(out / "host" / leaf)
        for cell in cli.CELLS:
            for name in ("intent.json", "status.json", "health-live.json", "result.json", "stop.json", "usb", "mcu", "control", "fresh-begin.json",
                         "queries", "finished", "previous-app", "runtime-config.json", "launch.json", "provision.json", "screen.png",
                         "installed-mcu", "native-trace", "android-trace"):
                c.checked(out / "cells" / cell / name)
            c.checked(out / "runtime" / cell)

    def observation_names(self, c, p):
        """Validated App capture directory names, oldest first."""
        names = p.command(["exec-out", "run-as", c.PKG, "ls", "-1", "files/p34-observations"]).splitlines()
        cli.require(names and len(names) <= 64 and all(CAPTURE_NAME.fullmatch(name) for name in names),
                    "ambiguous App capture directories")
        return sorted(names)

    def capture(self, c, p, phone, out):
        pid_text = p.command(["shell", "pidof", c.PKG], check=False).strip()
        cli.require(not pid_text or pid_text.isdigit(), "ambiguous App process")
        value = dict(pid=int(pid_text) if pid_text else None, snapshots=[], config=None, result="APP_INSPECTED",
                     capture_directories=0)
        if phone.exists(p, c.PKG, "files/p34-experiment.json"):
            data = p.file_bytes(c.PKG, "files/p34-experiment.json", 8192)
            value["config"] = c.raw(out / "runtime-config.json", data)
        if not phone.exists(p, c.PKG, "files/p34-observations"):
            cli.require(not pid_text, "running App has no observation yet; wait and collect")
            value["safe_idle"] = value["config"] is None
            c.save(out / "result.json", value)
            return value
        names = self.observation_names(c, p)
        # The App refuses to record once its own store is full and the exact limit lives in the
        # App build, not here: report the read-only count so `p34 doctor` can show whether a
        # window has room before any transfer is invoked.
        value["capture_directories"] = len(names)
        remote = "files/p34-observations/" + names[-1]
        before = p.file_bytes(c.PKG, remote + "/health.json", 8192)
        events = p.file_bytes(c.PKG, remote + "/events.jsonl", c.envelope.MAX_BYTES)
        after = p.file_bytes(c.PKG, remote + "/health.json", 8192)
        for name, data in (("health-before.json", before), ("events.jsonl", events), ("health-after.json", after)):
            c.raw(out / name, data)
        files = p.command(["exec-out", "run-as", c.PKG, "ls", "-1", remote]).splitlines()
        value.update(remote=remote, health=json.loads(after), snapshots=sorted(
            name for name in files if re.fullmatch(r"snapshot-[1-4]\.jsonl", name)))
        value["snapshot_records"] = {}
        for name in value["snapshots"]:
            value["snapshot_records"][name] = c.raw(out / name, p.file_bytes(c.PKG, remote + "/" + name, c.envelope.MAX_BYTES + 8192))
        cli.require(p.command(["shell", "pidof", c.PKG], check=False).strip() == pid_text, "App changed during capture")
        value["pid_checked_before_after"] = True
        if pid_text and idle_capture(value):
            query, checkpoint, messages = p.query.validate(events, before, after, pid=int(pid_text),
                sentinel=c.apk["metadata"]["device_observation"]["sentinel"], target=c.TARGET)
            c.raw(out / "checkpoint.jsonl", checkpoint)
            c.raw(out / "observations.log", messages.encode())
            value["successful_queries"] = query["successfulQueries"]
        value["safe_idle"] = idle_capture(value) and idle_capture(dict(value, health=json.loads(before)))
        value["stable_terminal"] = all(health.get("healthy") is True and health.get("lost") == 0 and
            health.get("error") is None and health.get("upgradeStarts") == health.get("upgradeEnds") == 1 and
            health.get("outcome") == "not-completed" and health.get("captureId") == value["health"]["captureId"]
            for health in (json.loads(before), value["health"]))
        value["stable_completed"] = all(health.get("healthy") is True and health.get("lost") == 0 and
            health.get("error") is None and health.get("upgradeStarts") == health.get("upgradeEnds") == 1 and
            health.get("outcome") == "completed" and health.get("captureId") == value["health"]["captureId"]
            for health in (json.loads(before), value["health"]))
        c.save(out / "result.json", dict(time=c.now(), **value))
        return value

    def inspect(self, c, out):
        self.preflight(c, out)
        phone = self.phone(c, "p34_inspection")
        lock = c.load("p34_inspection_lock", self.root / "Tools/ota/repeat_cycle.py")
        try:
            with lock.device_lock(), phone.usb(c, out) as p:
                value = self.capture(c, p, phone, out / "app")
            value["usb_closed"] = True
        except Exception as error:
            value = dict(result="PHONE_NOT_READY", error=type(error).__name__, detail=str(error))
        c.save(out / "result.json", dict(time=c.now(), **value))
        return value

    def preserved_payloads(self, c):
        """Host copies of App payloads by content hash; only real App evidence dirs count."""
        result = {}
        for path in (self.store.base / "runs").glob("**/*"):
            if path.is_file() and path.parent.name in APP_EVIDENCE_LEAVES and (
                    path.name in ("events.jsonl", "snapshot.jsonl") or SNAPSHOT_NAME.fullmatch(path.name)):
                result.setdefault(hashlib.sha256(path.read_bytes()).hexdigest(), self.store.checked(path))
        return result

    def store_report(self, c, p, out):
        """Read-only App observation inventory: capacity, per-directory state, deletion eligibility.

        The report is re-derived on every invocation and is not itself an authorization: an
        apply step rebuilds it and refuses any named directory it does not mark eligible."""
        names = self.observation_names(c, p)
        preserved = self.preserved_payloads(c)
        value = dict(result="STORE_INSPECTED", capture_directories=len(names), store_limit=STORE_LIMIT,
                     preserved_payloads=len(preserved), directories=[])
        for name in names:
            remote = "files/p34-observations/" + name
            files = p.command(["exec-out", "run-as", c.PKG, "ls", "-1", remote]).splitlines()
            item, reasons = dict(name=name, payloads={}), []
            if "health.json" in files:
                health = json.loads(p.file_bytes(c.PKG, remote + "/health.json", 8192))
                item.update(state=capture_state(health), health=health)
                if item["state"] != "terminal-not-completed":
                    reasons.append("capture is not a terminal not-completed transfer")
            else:
                item["state"] = "unreadable"
                reasons.append("health.json is missing on the device")
            labels = [label for label in ("events.jsonl",) if label in files]
            labels += [label for label in sorted(files) if SNAPSHOT_NAME.fullmatch(label)]
            for label in labels:
                data = p.file_bytes(c.PKG, remote + "/" + label, c.envelope.MAX_BYTES + 8192)
                digest = hashlib.sha256(data).hexdigest()
                item["payloads"][label] = dict(bytes=len(data), sha256=digest,
                                               host_copy=str(preserved.get(digest, "")))
                if digest not in preserved:
                    reasons.append("no host copy of " + label)
            item["eligible"], item["reasons"] = not reasons, reasons
            value["directories"].append(item)
        c.save(out / "store-report.json", value)
        return value

    def prune(self, c, out, names):
        """Inventory the App capture store and, when names are given, delete exactly those.

        The App store limit and this window's manual install both forbid guessing: the caller
        names exact directories, this re-derives the read-only report and refuses anything it does
        not mark eligible, never empties the store and never deletes while the App is up. No names
        means inventory only, which is the review copy an apply is authorized against."""
        cli.verify_tests(self.store)
        cli.require(all(CAPTURE_NAME.fullmatch(name) for name in names), "invalid capture directory name")
        phone = self.phone(c, "p34_prune")
        lock = c.load("p34_prune_lock", self.root / "Tools/ota/repeat_cycle.py")
        value = dict(result="PRUNE_FAILED", device_operations=0, requested=sorted(names))
        with lock.device_lock(), phone.usb(c, out / "usb") as p:
            if names:
                cli.require(not p.command(["shell", "pidof", c.PKG], check=False).strip(),
                            "stop the App before freeing observation directories")
            report = self.store_report(c, p, out)
            before = [item["name"] for item in report["directories"]]
            eligible = sorted(item["name"] for item in report["directories"] if item["eligible"])
            value.update(result="STORE_REPORTED", before=before, eligible=eligible,
                         report=cli.record(out / "store-report.json"))
            if names:
                cli.require(len(set(names)) == len(names) and set(names) <= set(eligible),
                            "requested directories are not all terminal captures preserved host-side")
                cli.require(len(before) - len(names) >= 1, "the App store needs at least one capture directory")
                resolved = {name: checked_phone_path(c, p, "files/p34-observations/" + name) for name in names}
                cli.require(not p.command(["shell", "pidof", c.PKG], check=False).strip(),
                            "App started during capture inventory; do not delete")
                c.save(out / "prune-intent.json", dict(time=c.now(), requested=sorted(names), eligible=eligible,
                    before=before, resolved_paths=resolved, report=cli.record(out / "store-report.json")))
                for name in names:
                    p.command(["shell", "run-as", c.PKG, "rm", "-rf", "files/p34-observations/" + name])
                remaining = self.observation_names(c, p)
                cli.require(set(remaining) == set(before) - set(names),
                            "deletion did not match the requested directories")
                value.update(result="PRUNED", device_operations=len(names), removed=sorted(names))
            else:
                remaining = before
            newest = json.loads(p.file_bytes(c.PKG, "files/p34-observations/" + remaining[-1] + "/health.json", 8192))
            value.update(remaining=remaining, remaining_state=capture_state(newest))
        c.save(out / "result.json", dict(time=c.now(), **value))
        return value

    def prune_completed(self, c, out, selection, *, apply=False, tests=None):
        """Archive/preview one verified U capture; apply deletes only that phone copy."""
        for name in ("intent.json", "result.json", "app", "usb"):
            c.checked(out / name)
        chosen, protected = selection["selected"], selection["protected"]
        report = chosen["report"]
        remote, capture = selection["remote"], selection["capture"]
        cli.require(CAPTURE_NAME.fullmatch(capture) and remote == "files/p34-observations/" + capture and
                    capture != protected["report"]["summary"]["captureId"], "invalid/current completed recording target")
        phone = self.phone(c, "p34_completed_prune")
        lock = c.load("p34_completed_prune_lock", self.root / "Tools/ota/repeat_cycle.py")
        result = dict(result="COMPLETED_CAPTURE_PRUNE_FAILED", apply=apply, selected=chosen["descriptor"],
            protected=protected["descriptor"], remote=remote, capture=capture, no_transfer=True, phone_mutations=0)
        try:
            with lock.device_lock(), phone.usb(c, out) as p:
                if apply:
                    cli.require(not p.command(["shell", "pidof", c.PKG], check=False).strip(),
                                "stop the verified idle App before completed cleanup")
                before = self.observation_names(c, p)
                cli.require(capture in before and len(before) > 1 and
                            protected["report"]["summary"]["captureId"] in before, "selected/protected recording missing")
                names = p.command(["exec-out", "run-as", c.PKG, "ls", "-1", remote]).splitlines()
                snapshots = [name for name in names if SNAPSHOT_NAME.fullmatch(name)]
                cli.require(len(snapshots) == 1 and
                            set(names) - {"health.json.tmp"} == {"events.jsonl", "health.json", snapshots[0]},
                            "completed recording has unknown files or multiple snapshots")
                # Preserve interrupted atomic-health writes as opaque evidence, never as a verdict.
                pending = pending_health_bytes(p, c.PKG, remote + "/health.json.tmp") if "health.json.tmp" in names else None
                health_before = p.file_bytes(c.PKG, remote + "/health.json", 8192)
                events = p.file_bytes(c.PKG, remote + "/events.jsonl", c.envelope.MAX_BYTES)
                raw = p.file_bytes(c.PKG, remote + "/" + snapshots[0], c.envelope.MAX_BYTES + 8192)
                health_after = p.file_bytes(c.PKG, remote + "/health.json", 8192)
                if pending is not None:
                    cli.require(pending_health_bytes(p, c.PKG, remote + "/health.json.tmp") == pending,
                                "pending health file changed during archival")
                health = json.loads(health_after)
                cli.require(health_before == health_after and health["captureId"] == capture and
                            health["healthy"] is True and health["lost"] == 0 and health["error"] is None and
                            health["upgradeStarts"] == health["upgradeEnds"] == 1 and health["outcome"] == "completed",
                            "completed recording is unhealthy or changed during archival")
                config = report["inputs"]["config"]
                cli.require(cli.record(c.checked(config["path"])) == config, "original recording configuration changed")
                summary, _, _ = verify_full_snapshot(c.envelope, raw, c.read(config["path"]), config["sha256"],
                    report["summary"]["pid"], c.apk["metadata"]["device_observation"]["sentinel"])
                cli.require(summary["rawSha256"] == report["summary"]["rawSha256"] == report["inputs"]["snapshot"]["sha256"] and
                            len(raw) == report["inputs"]["snapshot"]["bytes"], "phone snapshot differs from original U")
                archived = {name: c.raw(out / "app" / name, data) for name, data in
                    (("health-before.json", health_before), ("events.jsonl", events), (snapshots[0], raw), ("health-after.json", health_after))}
                if pending is not None:
                    archived["health.json.tmp"] = c.raw(out / "app/health.json.tmp", pending)
                cli.require(all(cli.record(c.checked(item["path"])) == item for item in archived.values()), "archived bytes differ")
                result.update(result="COMPLETED_CAPTURE_ARCHIVED", before=before, archived=archived, tests=tests,
                    original_snapshot=report["inputs"]["snapshot"], full_snapshot_verified=True)
                if apply:
                    resolved = checked_phone_path(c, p, remote)
                    cli.require(not p.command(["shell", "pidof", c.PKG], check=False).strip(),
                                "App started during archival; do not delete")
                    c.save(out / "intent.json", dict(time=c.now(), apply=True, selected=chosen["descriptor"],
                        protected=protected["descriptor"], remote=remote, resolved=resolved, archived=archived, tests=tests))
                    p.command(["shell", "run-as", c.PKG, "rm", "-rf", remote])
                    remaining = self.observation_names(c, p)
                    cli.require(set(remaining) == set(before) - {capture}, "completed cleanup changed other recordings")
                    result.update(result="COMPLETED_CAPTURE_PRUNED", remaining=remaining, removed=[capture], phone_mutations=1)
            result["usb_closed"] = True
        except Exception as error:
            result.update(result="COMPLETED_CAPTURE_PRUNE_FAILED", error=type(error).__name__, detail=str(error))
        c.save(out / "result.json", dict(time=c.now(), **result))
        return result

    def known_configs(self, c):
        result = set()
        installed = self.installation(c)
        if installed:
            result.add(installed["report"]["inputs"]["config"]["sha256"])
        for item in self.profile.get("owned_configs", []):
            path = self.store.checked(self.root / item["path"])
            cli.require(cli.record(path)["sha256"] == item["sha256"], "original owned configuration changed")
            result.add(item["sha256"])
        for path in (c.OUT / "cells").glob("*/runtime-config.json"):
            result.add(cli.record(path)["sha256"])
        for plan_path in (self.store.base / "runs").glob("*/plan.json"):
            plan = self.store.read(plan_path)
            if (plan.get("root") != str(self.root) or plan.get("profile") != cli.record(self.profile_path) or
                    plan.get("bindings") != c.bindings):
                continue
            for path in plan_path.parent.glob("cells/*/runtime-config.json"):
                provision = path.parent / "provision.json"
                if not provision.exists():
                    continue
                actual = cli.record(self.store.checked(path))
                cli.require(self.store.read(provision)["config"] == actual, "prior configuration/provision receipt changed")
                result.add(actual["sha256"])
        return result

    def predecessor(self, c):
        group = getattr(self, "group", "screen")
        if group in cli.FULL_SUCCESSOR_GROUPS:
            value = cli.completed_full_predecessor(self.store, self.profile.get("predecessor"),
                group=cli.PREDECESSOR_GROUPS[group])
            if group == cli.BOOT_COPY_GROUP:
                self.patch_api.verify_transition(value["plan"]["target_bindings"], c.bindings)
            else:
                cli.require(value["plan"]["target_bindings"] == c.bindings, "window-8 receiver differs from verified predecessor")
            return value
        if group == "n03-full":
            value = cli.full_predecessor(self.store, self.profile.get("predecessor"))
            cli.require(value["plan"]["bindings"] == c.bindings, "full receiver differs from completed B")
            return value
        if group not in ("n03-b", "n03-install"):
            return None
        value = cli.paired_predecessor(self.store, self.profile.get("predecessor"))
        probe = c.screen if group == "n03-b" else c.n03["groups"]["probe"]["package"]
        versions = (30215, 30216) if group == "n03-b" else (30214, 30215)
        cli.require(value["plan"]["served"] == probe and
                    (c.receiver_version, c.target_version) == versions and value["plan"]["target_version"] == 30216,
                    "paired receiver transition must retain the identical T package")
        return value

    def installation(self, c):
        if getattr(self, "group", "screen") != "n03-b" or not self.profile.get("installation"):
            return None
        value = cli.installed_predecessor(self.store, self.profile["installation"], self.predecessor(c))
        cli.require(value["plan"]["served"] == c.n03["groups"]["receiver"]["package"] and
                    value["plan"]["target_bindings"] == c.bindings, "installation is not the bound N03 receiver")
        return value

    def completed_capture(self, c, observed, previous=None):
        if not (observed.get("stable_terminal") or observed.get("stable_completed")) or \
                len(observed.get("snapshots", [])) != 1 or not observed.get("config"):
            return None
        snapshot = observed.get("snapshot_records", {}).get(observed["snapshots"][0])
        if not snapshot:
            return None
        previous = previous or self.installation(c) or self.predecessor(c)
        if previous:
            report = previous["report"]
            if (report["inputs"]["config"]["sha256"] == observed["config"]["sha256"] and
                    report["summary"]["rawSha256"] == snapshot["sha256"] and
                    (report["summary"]["pid"] == observed["pid"] or
                     observed["pid"] is None and observed.get("pid_checked_before_after") is True) and
                    report["summary"]["captureId"] == observed["health"]["captureId"]):
                return previous["descriptor"]["report"]
        if observed.get("stable_completed"):
            return None  # Only the explicitly verified normal-OTA bridge may be retired.
        matches = []
        for path in (self.store.base / "runs").glob("*/analysis/latest.json"):
            value = self.store.read(path)
            if value.get("result") != "PREFIX_RECONCILED":
                continue
            parent = path.parent.parent
            plan = self.store.read(parent / "plan.json")
            if plan.get("profile") != cli.record(self.profile_path) or plan.get("bindings") != c.bindings:
                continue
            cli.require(cli.record(self.store.checked(value["report"]["path"])) == value["report"] and
                        cli.record(self.store.checked(value["readback"]["path"])) == value["readback"],
                        "reconciled evidence changed")
            report, readback = self.store.read(value["report"]["path"]), self.store.read(value["readback"]["path"])
            if (report["inputs"]["config"]["sha256"] == observed["config"]["sha256"] and
                    report["summary"]["rawSha256"] == snapshot["sha256"] and
                    (report["summary"]["pid"] == observed["pid"] or
                     observed["pid"] is None and observed.get("pid_checked_before_after") is True) and
                    report["summary"]["captureId"] == observed["health"]["captureId"]):
                cli.require(readback["result"] == "PREFIX_READBACK_VERIFIED" and readback["closure"]["retained_verified"] is True and
                            cli.owner_state(self.store, parent / "runtime" / value["cell"])["state"] == "CLOSED",
                            "prior transfer/closure not reconciled")
                matches.append(cli.record(path))
        cli.require(len(matches) <= 1, "ambiguous reconciled App ownership")
        return matches[0] if matches else None

    def retire_initial(self, c, p, phone, out):
        config_path = "files/p34-experiment.json"
        if not phone.exists(p, c.PKG, config_path):
            return
        config = p.file_bytes(c.PKG, config_path, 8192)
        own = [path for path in (c.OUT / "cells").glob("*/runtime-config.json") if path.parent != out and path.read_bytes() == config]
        if own:
            return  # The original strict completed-cell guard owns this case.
        require_owned_config(config, self.known_configs(c))
        observed = self.capture(c, p, phone, out / "previous-app")
        terminal = self.completed_capture(c, observed)
        cli.require((observed["safe_idle"] or terminal) and observed["config"]["sha256"] == hashlib.sha256(config).hexdigest(),
                    "App has active/completed/uncertain work; collect it instead of restarting")
        archive = "files/p34-retired-configs/" + hashlib.sha256(config).hexdigest() + ".json"
        cli.require(not phone.exists(p, c.PKG, archive), "configuration archive already exists; reconcile original retirement")
        cli.require(p.command(["shell", "pidof", c.PKG], check=False).strip() == (str(observed["pid"]) if observed["pid"] else ""),
                    "App changed before retirement")
        c.save(out / "previous-app/retire-intent.json", dict(time=c.now(), archive=archive, observation=observed, reconciled_terminal=terminal))
        if observed["pid"]:
            p.command(["shell", "am", "force-stop", c.PKG])
        cli.require(not p.command(["shell", "pidof", c.PKG], check=False).strip(), "App did not stop")
        cli.require(p.file_bytes(c.PKG, config_path, 8192) == config, "configuration changed before archival")
        p.command(["shell", "run-as", c.PKG, "mkdir", "-p", "files/p34-retired-configs"])
        p.command(["shell", "run-as", c.PKG, "mv", config_path, archive])
        cli.require(not phone.exists(p, c.PKG, config_path) and p.file_bytes(c.PKG, archive, 8192) == config,
                    "configuration archive/readback unresolved")
        c.save(out / "previous-app/retired.json", dict(time=c.now(), archive=archive, data_cleared=False, reinstalled=False))

    def quiesce(self, c, out, previous):
        """Stop only the verified completed App; keep its configuration for archival."""
        for name in ("intent.json", "result.json", "app", "usb"):
            c.checked(out / name)
        phone = self.phone(c, "p34_quiesce")
        lock = c.load("p34_quiesce_lock", self.root / "Tools/ota/repeat_cycle.py")
        value = dict(result="APP_QUIESCE_FAILED", predecessor=previous["descriptor"], no_transfer=True, data_cleared=False)
        try:
            with lock.device_lock(), phone.usb(c, out) as p:
                observed = self.capture(c, p, phone, out / "app")
                cli.require(observed.get("stable_completed") is True and
                            self.completed_capture(c, observed, previous) == previous["descriptor"]["report"],
                            "quiesce requires the exact completed capture/config/PID")
                config = Path(observed["config"]["path"]).read_bytes()
                expected_pid = str(observed["pid"]) if observed["pid"] else ""
                cli.require(p.command(["shell", "pidof", c.PKG], check=False).strip() == expected_pid and
                            p.file_bytes(c.PKG, "files/p34-experiment.json", 8192) == config,
                            "completed App changed before quiesce")
                c.save(out / "intent.json", dict(time=c.now(), pid=observed["pid"], config=observed["config"],
                    predecessor=previous["descriptor"], archive_config=False, delete_captures=False))
                if observed["pid"]:
                    p.command(["shell", "am", "force-stop", c.PKG])
                cli.require(not p.command(["shell", "pidof", c.PKG], check=False).strip() and
                            p.file_bytes(c.PKG, "files/p34-experiment.json", 8192) == config and
                            not p.command(["shell", "pidof", c.PKG], check=False).strip(),
                            "quiesce process absence/configuration preservation unresolved")
                value.update(pid=observed["pid"], config=observed["config"], configuration_preserved=True,
                             process_absent=True, result="APP_QUIESCED")
            value["usb_closed"] = True
        except Exception as error:
            value.update(result="APP_QUIESCE_FAILED", error=type(error).__name__, detail=str(error))
        c.save(out / "result.json", dict(time=c.now(), **value))
        return value

    def recovery_phone(self, c, observed, failure, *, retired=False):
        previous = failure["previous"]["report"]
        names = observed.get("snapshots", [])
        snapshot = observed.get("snapshot_records", {}).get(names[0]) if len(names) == 1 else None
        expected = previous["inputs"]["snapshot"]
        cli.require(observed.get("result") == "APP_INSPECTED" and observed.get("stable_terminal") is True and
                    observed.get("pid_checked_before_after") is True and
                    observed.get("remote") == "files/p34-observations/" + previous["summary"]["captureId"] and
                    snapshot is not None and (snapshot["bytes"], snapshot["sha256"]) == (expected["bytes"], expected["sha256"]),
                    "recovery phone capture differs from preserved B")
        cli.require(observed.get("pid") is None if retired else observed.get("pid") in (None, failure["pid"]),
                    "recovery refuses a different App process")
        config = observed.get("config")
        cli.require(config is None if retired else config is not None and
                    (config["bytes"], config["sha256"]) == tuple(failure["inputs"]["config"][key] for key in ("bytes", "sha256")),
                    "recovery refuses a different App configuration")
        if not retired:
            cli.require(observed.get("capture_directories") == STORE_LIMIT, "unrecorded full-store state changed")
        cli.require(cli.record(c.checked(snapshot["path"])) == snapshot, "recovery phone snapshot changed")
        return previous["inputs"]["snapshot"]

    def recovery_native(self, c, failure, checkpoint):
        self.verify_install_checkpoint(c, failure["inputs"]["before"]["path"])
        self.verify_install_checkpoint(c, checkpoint)
        closure = c.read(checkpoint)
        for previous in (failure["before"]["final_state"], failure["previous"]["readback"]["closure"]["final_state"]):
            same_terminal(closure["final_state"], previous, idle_abort_sequence=True)
        return cli.record(checkpoint)

    def recover_prestart(self, c, out, failure):
        """Retire one proven unrecorded launch. No service, launch, transfer or deletion."""
        c.cell = cli.INSTALL_CELL
        os.environ.update(c.environment())
        phone = self.phone(c, "p34_prestart_recovery")
        lock = c.load("p34_prestart_recovery_lock", self.root / "Tools/ota/repeat_cycle.py")
        helper = c.load("p34_prestart_recovery_mcu", c.HERE / "prefix_mcu.py")
        value = dict(result="PRESTART_RECOVERY_FAILED", failed_inputs=failure["inputs"], no_transfer=True,
                     usb_closed=False, evidence=str(out))
        try:
            cli.require(c.read(failure["inputs"]["launch"]["path"])["apk"]["sha256"] == c.apk["apk"]["sha256"],
                        "failed launch was not the pinned diagnostic APK")
            with lock.device_lock():
                mcu = helper.Mcu(c, out / "mcu")
                try:
                    mcu.open()
                    same_terminal(mcu.sample("recovery-before"), failure["before"]["final_state"], idle_abort_sequence=True)
                    with phone.usb(c, out / "phone") as p:
                        observed = self.capture(c, p, phone, out / "phone/app")
                        self.recovery_phone(c, observed, failure)
                        config_path = "files/p34-experiment.json"
                        config = Path(failure["inputs"]["config"]["path"]).read_bytes()
                        archive_dir = "files/p34-retired-configs"
                        archive = archive_dir + "/" + failure["inputs"]["config"]["sha256"] + ".json"
                        cli.require(not phone.exists(p, c.PKG, archive), "failed configuration already archived; reconcile retirement")
                        resolved = {config_path: checked_phone_path(c, p, config_path),
                                    archive_dir: checked_phone_path(c, p, archive_dir, new_leaf=not phone.exists(p, c.PKG, archive_dir))}
                        same_terminal(mcu.sample("recovery-pre-retire"), failure["before"]["final_state"], idle_abort_sequence=True)
                        expected_pid = str(observed["pid"]) if observed["pid"] else ""
                        cli.require(p.command(["shell", "pidof", c.PKG], check=False).strip() == expected_pid and
                                    p.file_bytes(c.PKG, config_path, 8192) == config, "App changed before prestart retirement")
                        c.save(out / "retire-intent.json", dict(time=c.now(), pid=observed["pid"], config=failure["inputs"]["config"],
                            archive=archive, resolved_paths=resolved, observation=cli.record(out / "phone/app/result.json")))
                        if observed["pid"]:
                            p.command(["shell", "am", "force-stop", c.PKG])
                        cli.require(not p.command(["shell", "pidof", c.PKG], check=False).strip(), "owned App did not stop")
                        cli.require(p.file_bytes(c.PKG, config_path, 8192) == config, "configuration changed after App stop")
                        cli.require(not p.command(["shell", "pidof", c.PKG], check=False).strip(), "App restarted before archival")
                        p.command(["shell", "run-as", c.PKG, "mkdir", "-p", archive_dir])
                        checked_phone_path(c, p, archive, new_leaf=True)
                        p.command(["shell", "run-as", c.PKG, "mv", config_path, archive])
                        cli.require(not phone.exists(p, c.PKG, config_path) and p.file_bytes(c.PKG, archive, 8192) == config and
                                    not p.command(["shell", "pidof", c.PKG], check=False).strip(), "prestart archival unresolved")
                        c.save(out / "retired.json", dict(time=c.now(), pid=observed["pid"], config=failure["inputs"]["config"],
                            archive=archive, process_absent=True, configuration_absent=True, data_cleared=False, reinstalled=False))
                    value["usb_closed"] = True
                    same_terminal(mcu.sample("recovery-after"), failure["before"]["final_state"], idle_abort_sequence=True)
                finally:
                    closure = mcu.close(restore=False)
                    c.save(out / "checkpoint.json", closure)
            value["checkpoint"] = self.recovery_native(c, failure, out / "checkpoint.json")
            value["retired"] = cli.record(out / "retired.json")
            value["result"] = "PRESTART_RECOVERED"
        except Exception as error:
            value.update(error=type(error).__name__, detail=str(error))
        c.save(out / "result.json", dict(time=c.now(), **value))
        return value

    def validate_served(self, c, value, origin):
        """App-contract checks for the served release metadata, bound to the selected group.

        The chain's ``prefix_named.validate_latest`` is frozen with the retained group's
        target version and served file name, so a paired N03 arm can never satisfy it with
        its own declared metadata.  Every predicate below is one of that validator's checks
        with the bound group's values substituted; none is dropped or weakened, so the
        retained group keeps exactly the frozen set."""
        require = cli.require
        require(value["schemaVersion"] == 2 and value["updateAvailable"] is True and
                value.get("errorCode") is None and value["appId"] == "trace" and
                value["deviceModel"] == c.service.DEVICE_MODEL and value["channel"] == "stable" and
                value["transport"] == "ble" and value["versionCode"] == c.target_version and
                value["targetImageSha256"] == c.target["sha256"], "HTTP release metadata drift")
        for key in ("requestId", "releaseId", "releaseTag", "versionName", "targetHardware"):
            require(isinstance(value[key], str) and value[key], "missing release string: " + key)
        require(type(value["minAppVersionCode"]) is int and value["minAppVersionCode"] == 0, "App version gate drift")
        asset = value["asset"]
        name = asset["fileName"]
        kind = getattr(c, "package_kind", "full")
        require(kind in ("full", "patch"), "unsupported bound package kind")
        require(asset["kind"] == kind and isinstance(name, str) and 0 < len(name) <= 128 and
                re.fullmatch(r"[A-Za-z0-9._-]+", name) and name.endswith("-" + kind + ".etu") and name == self.served_name,
                kind + " asset filename does not match the App contract/download path")
        base_version = c.receiver_version if kind == "patch" else 0
        base_sha = c.receiver_image_sha if kind == "patch" else None
        require(isinstance(asset["assetId"], str) and asset["assetId"] and
                asset["sha256"] == c.screen["sha256"] and type(asset["sizeBytes"]) is int and
                asset["sizeBytes"] == len(c.screen_bytes) and type(asset["baseVersionCode"]) is int and
                asset["baseVersionCode"] == base_version and "baseImageSha256" in asset and asset["baseImageSha256"] == base_sha and
                type(asset["expiresAt"]) is int and asset["expiresAt"] > 0, kind + " asset metadata drift")
        uri = urllib.parse.urlsplit(asset["downloadUrl"])
        require(uri.scheme == "https" and uri.scheme + "://" + uri.netloc == origin and not uri.username,
                "download origin/security differs")

    def verify_served(self, c, origin, *, proxy=False):
        """Frozen DNS-readiness window, then the group-bound metadata and package checks.

        The DNS half stays the frozen one (its bounded attempts and its own action record);
        only the strict half is re-bound, because that half is frozen to the retained group."""
        cli.require(re.fullmatch(r"https://[a-z0-9-]+\.trycloudflare\.com", origin), "unbound HTTPS origin")
        host = urllib.parse.urlsplit(origin).hostname
        self.legacy["wait_dns"](lambda: self.legacy["resolve"](c, host),
            lambda value: c.action("dns-readiness", value["result"].lower(), host=host, **value))
        opener = urllib.request.build_opener() if proxy else urllib.request.build_opener(urllib.request.ProxyHandler({}))
        query = self.legacy["named"]["raw_load"]("p34_served_query", c.HERE / "prefix_phone.py").latest_query(c)
        with opener.open(origin + c.service.LATEST_PATH + "?" + urllib.parse.urlencode(query), timeout=30) as response:
            value = json.loads(response.read(16384))
        self.validate_served(c, value, origin)
        with opener.open(value["asset"]["downloadUrl"], timeout=30) as response:
            data = response.read(len(c.screen_bytes) + 1)
        cli.require(data == c.screen_bytes, "HTTPS package bytes differ")
        return dict(origin=origin, bytes=len(data), sha256=hashlib.sha256(data).hexdigest(),
                    file_name=self.served_name, kind=getattr(c, "package_kind", "full"), filename_contract_verified=True)

    def known_staging_packages(self, c):
        values = [c.assets["groups"][name]["package"] for name in ("screen", "reset-control")]
        if self.group in ("n03-a", "n03-b", *cli.INSTALL_GROUPS):
            values.append(c.n03["groups"]["receiver"]["package"])
        if self.group in cli.INSTALL_GROUPS:
            values.append(c.n03["groups"]["probe"]["package"])
        if self.group in cli.FULL_SUCCESSOR_GROUPS:
            values.append(c.u_assets["package"])
        if self.group in (*cli.SUCCESSORS, *cli.N04_LINEAGE_GROUPS):
            values.append(c.v_assets["package"])
        if self.group in cli.N04_LINEAGE_GROUPS:
            values.append(c.w_assets["package"])
            values.extend(item["package"] for item in c.n04_prior_assets)
        if self.group in cli.ACK_GAP_GROUPS:
            values.append(self.patch_api.diagnostic_package())
        return values

    def fresh_begin(self, c, mcu, out):
        cli.require(self.group in ("n03-a", "n03-b", *cli.INSTALL_GROUPS), "fresh BEGIN is only for the declared N03 sequence")
        helper = c.load("p34_fresh_begin_mcu", c.HERE / "prefix_mcu.py")
        for path in (out / "fresh-begin.json", out / "mcu/fresh-before-journal.bin"):
            self.store.checked(path)
        before = mcu.sample("fresh-begin-before")
        helper.idle(before)
        raw = mcu.read(0x90300000, 4096)
        journal = c.raw(out / "mcu/fresh-before-journal.bin", raw)
        prior = distinct_journal(raw, c.screen, self.known_staging_packages(c))
        cli.require(mcu.read(0x90300000, 4096) == raw, "old staging journal changed during admission")
        current = mcu.sample("fresh-begin-after")
        helper.idle(current)
        same_terminal(current, before)
        c.save(out / "fresh-begin.json", dict(result="DIFFERENT_PACKAGE_BEGIN_REQUIRED", group=self.group,
            package=c.screen, prior_package=prior, journal=journal, before=before, current=current,
            native_zero_sample=False, new_begin=False, new_abort=False))
        return self.initial_sample(c, out)

    def initial_sample(self, c, out):
        fresh = out / "fresh-begin.json"
        if not fresh.exists():
            reused = out / "control-reused.json"
            return c.read(reused)["current"] if reused.exists() else c.read(out / "control/result.json")["after"]
        proof = c.read(fresh)
        cli.require(self.group in ("n03-a", "n03-b", *cli.INSTALL_GROUPS) and proof["group"] == self.group and
                    proof["result"] == "DIFFERENT_PACKAGE_BEGIN_REQUIRED" and proof["package"] == c.screen and
                    all(proof[key] is False for key in ("native_zero_sample", "new_begin", "new_abort")),
                    "fresh-BEGIN proof belongs to different inputs or invents a zero control")
        helper = c.load("p34_initial_sample_mcu", c.HERE / "prefix_mcu.py")
        journal = proof["journal"]
        path = self.store.checked(journal["path"])
        cli.require(cli.record(path) == journal and distinct_journal(path.read_bytes(), c.screen,
                    self.known_staging_packages(c)) == proof["prior_package"], "old journal proof changed")
        for state in (proof["before"], proof["current"]):
            helper.idle(state)
            for key in ("profile_raw", "session_raw"):
                item = state[key]
                cli.require(cli.record(self.store.checked(item["path"])) == item, "fresh-BEGIN sample bytes changed")
            raw = Path(state["profile_raw"]["path"]).read_bytes()
            cli.require(len(raw) == c.instrumentation["size"] and
                        dict(zip(c.m.HEADERS, struct.unpack_from("<%dI" % len(c.m.HEADERS), raw))) == state["profile"] and
                        c.decode_session(Path(state["session_raw"]["path"]).read_bytes(),
                                         c.bindings["layout"]["members"]) == state["session"],
                        "fresh-BEGIN decoded sample differs from its original bytes")
        same_terminal(proof["current"], proof["before"])
        return proof["current"]

    def phone(self, c, name, *, producer=False):
        phone = self.legacy["named"]["raw_load"](name, c.HERE / "prefix_phone.py")
        if self.group in (cli.NATIVE_DIAGNOSTIC_GROUP, cli.SPEED16_GROUP, cli.SPEED32_GROUP, *cli.PATCH32_GROUPS, *cli.RECEIVE_GROUPS, *cli.ACK_GAP_GROUPS) and self.profile.get("tunnel_protocol") == "quic":
            tunnel_protocol_adapter(phone, self.root, "quic")
        phone.FILENAME = self.served_name
        phone.experiment = lambda messages, expected, sha: verify_experiment(c.envelope, messages, expected, sha)
        def verify(c, origin, *, proxy=False):
            """Readiness record plus the group-bound strict checks of this arm's package."""
            return wait_ready(lambda: self.verify_served(c, origin, proxy=proxy),
                lambda value: c.action("https-readiness", value["result"].lower(), **value),
                self.legacy["entry"]["live"]["retry"]["transient"])
        phone.verify_http = verify
        if self.group in cli.INSTALL_GROUPS:
            original_config, original_service = phone.config, phone.service_config
            def full_config(c, cell, baud, window, origin):
                cli.require(cell == cli.INSTALL_CELL and (baud, window) == cli.cells_for(self.group)[cell], "unplanned installation axes")
                value = dict(original_config(c, cell, baud, window, origin), transferMode="full", prefixBytes=0)
                if self.group == cli.RECONNECT_GROUP:
                    reconnect = cli.load_module("p34_reconnect_config", self.root / "Tools/ota/p34_reconnect_profile.py")
                    value = reconnect.config(value)
                return value
            def full_service(c, origin):
                value = original_service(c, origin)
                value["releases"][c.release_key]["releaseNotes"] = ("Full OTA received by N03; retain the N03 executable."
                    if self.group in cli.MEASURED_FULL_GROUPS else "Install the N03 receiver R by normal full BLE OTA.")
                if self.group in cli.N04_GROUPS:
                    value["releases"][c.release_key]["releaseNotes"] = (
                        "Install N04 App X by normal OTA; W still performs this installation, not an N04 speed result."
                        if self.group == "n04-bootstrap" else
                        "Measure N04 installation on X, retaining the same executable in Y and the unchanged Boot.")
                    if self.group == "n04-window16":
                        value["releases"][c.release_key]["releaseNotes"] = (
                            "Screen window 16 on Y; retain the same N04 executable in Z and unchanged Boot. "
                            "One full transfer, not a 1 MiB or stability acceptance run.")
                    if self.group == cli.NATIVE_DIAGNOSTIC_GROUP:
                        value["releases"][c.release_key]["releaseNotes"] = (
                            "Fixed Y/window 8 native diagnostic; retain Z and unchanged Boot. "
                            "Wait for query-time native admission before Start.")
                    if self.group == cli.SPEED16_GROUP:
                        value["releases"][c.release_key]["releaseNotes"] = (
                            "Window-16 speed screen on retained Z; same N04 executable and Boot. "
                            "Sequential full transfer, not strict same-package A/B or 1 MiB acceptance.")
                    if self.group == cli.SPEED32_GROUP:
                        value["releases"][c.release_key]["releaseNotes"] = (
                            "Window-32 speed screen on retained 30225; same N04 executable and Boot. "
                            "One legal successor, not a replay, strict same-package A/B or 1 MiB acceptance.")
                if self.group in cli.ALL_PATCH_GROUPS:
                    release = value["releases"][c.release_key]
                    kind = c.package_kind
                    release["asset"].update(assetId=c.release_key + "-" + kind, kind=kind,
                        baseVersionCode=c.receiver_version if kind == "patch" else 0,
                        baseImageSha256=c.receiver_image_sha if kind == "patch" else None)
                    release["releaseNotes"] = (
                        "Install the coalescing receiver through FULL OTA; the predecessor performs installation, not the new receiver."
                        if cli.ALL_PATCH_GROUPS[self.group]["asset_group"] == "bootstrap" else
                        "One complete AA-to-AB PATCH, not two sequential alternatives or a formal benchmark. "
                        "Measure receive/install separately and retain the verified target and original Boot.")
                    if self.group in cli.RECEIVE_GROUPS:
                        release["releaseNotes"] = (
                            "Install the checked receive-restore candidate; this transfer still measures the old receiver."
                            if self.group == "receive-bootstrap" else
                            "Measure checked receive restoration with a legal1MiB PATCH; retain the target and original Boot.")
                    if self.group == "ack-gap-bootstrap":
                        release["releaseNotes"] = "Install the diagnostic 1ms ACK-gap candidate; original Boot retained. This is not a throughput acceptance run."
                    if self.group == "ack-batch-bootstrap":
                        release["releaseNotes"] = "Install byte-preserving ACK batching; original Boot retained. Bootstrap measures the old receiver, not batching throughput."
                    if self.group == cli.BOOT_COPY_GROUP:
                        release["releaseNotes"] = "Verified replacement Boot; header-only full successor, window28. Best-case identical-block copy screen, not general OTA throughput acceptance."
                    if self.group in cli.COST_GROUPS:
                        release["releaseNotes"] = ("Install diagnostic port-cost firmware; this bootstrap measures the old receiver."
                            if self.group == "cost-bootstrap" else
                            "Measure diagnostic port costs with a header-only successor; millis ticks are not calibrated wall time.")
                    if self.group in cli.ERASE_GROUPS:
                        release["releaseNotes"] = ("Install diagnostic block-erase candidate; bootstrap measures the old receiver."
                            if self.group == "erase-bootstrap" else
                            "Measure diagnostic block erase with a header-only successor; retain all verification and confirmation guards.")
                    if self.group == cli.RECONNECT_GROUP:
                        release["releaseNotes"] = "Measure diagnostic reconnect cadence on a header-only successor; retained Boot, executable and full confirmation guards."
                return value
            phone.config, phone.service_config = full_config, full_service
        if producer:
            return phone
        @contextmanager
        def borrow(c, out):
            live = self.network_ready(c, c.OUT)
            verified = phone.verify_http(c, live["origin"])
            c.save(out / "network-borrowed.json", dict(time=c.now(), verified=verified, owner=str(c.OUT / "runtime/network")))
            yield live["origin"]
        original_release = phone.release_old
        def release(c, p, out):
            self.retire_initial(c, p, phone, out)
            return original_release(c, p, out)
        original_control = phone.browser_control
        def control(c, p, mcu, out, cell):
            if self.group in ("n03-a", "n03-b"):
                return self.fresh_begin(c, mcu, out)
            previous = self.profile.get("zero_control")
            if cell == "s01" and previous:
                old = c.read(self.store.checked(self.root / previous["path"]))
                cli.require(cli.record(self.root / previous["path"])["sha256"] == previous["sha256"], "zero-control evidence changed")
                state = mcu.sample("zero-reuse-check")
                try:
                    self.legacy["named"]["valid_reused_zero"](c, state, old, previous["last_tick"])
                except RuntimeError:
                    c.action("zero-control", "fresh-control-required", reason="current idle generation differs from retained control")
                else:
                    state = mcu.journal("reused-control", c.control, 0)
                    c.save(out / "control-reused.json", dict(time=c.now(), result="EXISTING_ZERO_REVERIFIED", original=previous,
                        current=state, new_begin=False, new_abort=False))
                    return state
            return original_control(c, p, mcu, out, cell)
        original_observe = phone.observe_app
        def observe(c, p, mcu, out, pid, expected, initial):
            value = original_observe(c, p, mcu, out, pid, expected, initial)
            if (out / "fresh-begin.json").exists() and value["result"] == "PREFIX_OBSERVED":
                self.initial_sample(c, out)
                messages = (out / "finished/parsed/observations.log").read_text(encoding="utf-8")
                value["initial_state_evidence"] = zero_before_data(messages)
                probe = value["app"]["prefix"]
                cli.require(probe["sentTotalBytes"] == probe["prefixBytes"] and value["profile"]["clean_counters"],
                            "paired prefix has retransmissions or MCU errors; preserve it, do not repeat")
            return value
        phone.network, phone.release_old, phone.browser_control, phone.observe_app = borrow, release, control, observe
        return phone

    def prepare(self, c, out, phone, tests):
        count = phone.get("capture_directories")
        cli.require(type(count) is int and 0 <= count < STORE_LIMIT,
                    "App observation store has no verified free slot; review preserved captures before cleanup")
        previous = self.predecessor(c)
        terminal = self.completed_capture(c, phone)
        recovery = getattr(self, "recovery", None)
        retirement = getattr(self, "retirement_recovery", None)
        if retirement:
            cli.require(c.sources() == retirement["value"]["sources"], "retirement recovery source binding changed")
            cli.retirement_api(self.store).verify_phone(self.store, phone, retirement["failure"])
            terminal = retirement["report"]
        if recovery:
            cli.require(c.sources() == c.read(Path(recovery["report"]["path"]).parent / "intent.json")["sources"],
                        "prestart recovery source binding changed")
            self.recovery_native(c, recovery["failure"], recovery["value"]["checkpoint"]["path"])
            self.recovery_phone(c, phone, recovery["failure"], retired=True)
            terminal = recovery["report"]
        cli.require(phone.get("safe_idle") or terminal, "App has unresolved transfer history; p34 collect before starting")
        known = self.known_configs(c)
        require_owned_config(Path(phone["config"]["path"]).read_bytes() if phone.get("config") else None, known)
        c.save(out / "root-before.json", c.root_state())
        installing = self.group in cli.INSTALL_GROUPS
        extra = dict(predecessor=previous["descriptor"], target_bindings=self.installed_context(out).bindings) if installing else {}
        if self.group in cli.ALL_PATCH_GROUPS:
            extra["package_kind"] = c.package_kind
        if recovery:
            extra["prestart_recovery"] = recovery["pointer"]
        if retirement:
            extra["retirement_recovery"] = retirement["report"]
        c.save(out / "plan.json", dict(time=c.now(), root=str(self.root), profile=cli.record(self.profile_path),
            sources=c.sources(), bindings=c.bindings, cells=cli.cells_for(self.group), native_authority=c.native_authority(), tests=tests,
            prestart=cli.record(out / "prestart-phone/result.json"), prefix_bytes=0 if installing else 32768,
            group=self.group, served=c.screen, served_name=self.served_name, receiver_version=self.receiver_version,
            target_version=self.target_version,
            no_end=not installing, no_mcu_reset=True, no_firmware_install=not installing,
            independent_acceptance=False, reconciled_terminal=terminal, **extra))

    def validate(self, c, out):
        self.preflight(c, out)
        plan = c.read(out / "plan.json")
        cli.require(plan["root"] == str(self.root) and plan["profile"] == cli.record(self.profile_path) and
                    plan["sources"] == c.sources() and plan["bindings"] == c.bindings and
                    plan["cells"] == {key:list(value) for key,value in cli.cells_for(self.group).items()} and
                    plan["native_authority"] == c.native_authority(), "session source/input/permission binding changed")
        cli.require(plan.get("group", "screen") == self.group == c.group and
                    plan.get("served") == c.screen and plan.get("served_name") == self.served_name and
                    plan.get("receiver_version") == c.receiver_version and
                    plan.get("target_version") == c.target_version,
                    "session comparison group or served package changed")
        if self.group in cli.INSTALL_GROUPS:
            cli.require(plan["prefix_bytes"] == 0 and plan["no_end"] is False and plan["no_firmware_install"] is False and
                        plan["target_bindings"] == self.installed_context(out).bindings and
                        plan["predecessor"] == self.predecessor(c)["descriptor"], "installation plan/bindings changed")
        if self.group in cli.ALL_PATCH_GROUPS:
            cli.require(plan.get("package_kind") == c.package_kind, "PATCH plan package kind changed")
        if plan.get("prestart_recovery"):
            item = plan["prestart_recovery"]
            cli.require(cli.record(c.checked(item["path"])) == item, "prestart recovery pointer changed")
            recovered = cli.prestart_recovery(self.store, Path(item["path"]), self.profile_path)
            self.recovery_native(c, recovered["failure"], recovered["value"]["checkpoint"]["path"])
        if plan.get("retirement_recovery"):
            item = plan["retirement_recovery"]
            cli.require(cli.record(c.checked(item["path"])) == item, "retirement recovery report changed")
            cli.retirement_api(self.store).load_recovery(self.store, Path(item["path"]), self.profile_path)

    def network_ready(self, c, out):
        owner = cli.owner_state(self.store, out / "runtime/network")
        cli.require(owner["state"] == "LIVE" and not (out / "network-stop.json").exists(), "service owner is not live")
        live = c.read(out / "live-network.json")
        cli.require(dt.datetime.fromisoformat(live["expires"]).timestamp() - time.time() > 3500 and
                    live["package"] == c.screen and live["file_name"] == self.served_name,
                    "service expired or insufficient observation reserve")
        return live

    def network_worker(self, c, out):
        c.cell = "network-only"
        phone = self.phone(c, "p34_asset_producer", producer=True)
        result = dict(result="NETWORK_INCOMPLETE", device_operations=0)
        try:
            with phone.network(c, out / "network-owner") as origin:
                started = dt.datetime.fromisoformat(c.read(out / "runtime/network/ready.json")["started"])
                expires = started + dt.timedelta(seconds=cli.NETWORK_SECONDS)
                cli.require(expires.timestamp() - time.time() > 3500, "service preparation consumed the device reserve")
                c.save(out / "live-network.json", dict(time=c.now(), origin=origin, expires=expires.isoformat(),
                    package=c.screen, file_name=self.served_name, source=cli.record(self.root / "Tools/ota/p34_session.py")))
                print("P34_VERIFIED_SERVICE_READY", origin, flush=True)
                while time.time() < expires.timestamp() and not (out / "network-stop.json").exists():
                    time.sleep(.5)
                result["result"] = "NETWORK_CLOSED"
        except Exception as error:
            result.update(error=type(error).__name__, detail=str(error)[:240])
        c.save(out / "network-result.json", dict(time=c.now(), **result))
        return int("error" in result)

    def cell_worker(self, c, out, cell):
        self.network_ready(c, out)
        c.cell = cell
        original = c.p.file_bytes
        def file_bytes(pkg, path, limit):
            data = original(pkg, path, limit)
            if path.endswith("/health.json") and (out / "cells" / cell / "launch.json").exists():
                c.save(out / "cells" / cell / "health-live.json", dict(observed=c.now(), health=json.loads(data)), replace=True)
            return data
        c.p.file_bytes = file_bytes
        if self.group in cli.INSTALL_GROUPS:
            return self.install_worker(c, out, cell)
        return self.phone(c, "p34_prefix_cell").run(c, cell)

    def installed_context(self, out):
        if self.group in cli.MEASURED_FULL_GROUPS:
            c = self.context(out)
            c.bindings = c.full_assets["target_bindings"]
            c.receiver_version = self.target_version
            gate = self.legacy["named"]["restored"]["clock"]["gate"]
            c.flash_addresses = bind_flash_gate(c.bindings["profile"], gate["symbol"])
            return c
        return Backend(self.store, self.profile_path, self.profile, "n03-b").context(out)

    def install_checkpoint(self, c, out, *, before=False):
        helper = c.load("p34_install_mcu", c.HERE / "prefix_mcu.py")
        path = out / ("mcu" if before else "installed-mcu")
        c.checked(path)
        mcu = helper.Mcu(c, path)
        try:
            mcu.open()
            cli.require(mcu.original_baud == 921600, "installation requires retained 921600; no implicit tuning")
            if before:
                self.fresh_begin(c, mcu, out)
        finally:
            mcu.close(restore=False)
        return cli.record(path / "closure.json")

    def verify_install_checkpoint(self, c, path):
        closure = c.read(path)
        cli.require(closure.get("retained_verified") is True and closure.get("reader_closed") is True and
                    "cleanup_error" not in closure and all(closure.get(key) is True for key in
                    ("no_reset", "no_halt", "no_flash", "no_nvic_write")), "installation native closure unresolved")
        for phase in ("initial_identity", "final_identity"):
            for image, expected in (("app", c.receiver_image_sha), ("boot", c.BOOT_SHA)):
                item = closure[phase][image]
                cli.require(cli.record(c.checked(item["path"])) == item and item["sha256"] == expected,
                            "installation complete raw App/Boot mismatch")
        state = closure["final_state"]
        helper = c.load("p34_install_idle", c.HERE / "prefix_mcu.py")
        helper.idle(state)
        for key in ("session_raw", "profile_raw"):
            cli.require(cli.record(c.checked(state[key]["path"])) == state[key], "installation terminal bytes changed")
        cli.require(c.decode_session(Path(state["session_raw"]["path"]).read_bytes(), c.bindings["layout"]["members"]) == state["session"] and
                    state["profile_raw"]["bytes"] == c.instrumentation["size"] and
                    state["retained_word"] == c.m.baud_word(921600), "installation terminal layout/rate differs")
        return cli.record(path)

    def verify_receiver_admission(self, c, directory):
        path = directory / "receiver-admission.json"
        if not path.exists():
            return None
        value = c.read(path)
        cli.require(value["result"] == "BOUND_RECEIVER_ADMITTED" and value["receiver_version"] == c.receiver_version and
                    value["image_sha256"] == c.receiver_image_sha and value["map"] == c.bindings["profile"]["map"] and
                    value["addresses"] == c.flash_addresses, "receiver admission used different image/MAP addresses")
        gate = value["flash_gate"]
        cli.require(cli.record(c.checked(gate["path"])) == gate and Path(gate["path"]) == directory / "flash-admission.json",
                    "receiver Flash gate proof changed")
        observed = c.read(gate["path"])
        cli.require(observed["disabled"] == 0 and observed["jedec"] == 0xEF4018,
                    "receiver Flash gate did not pass")
        return cli.record(path)

    def finish_install_snapshot(self, c, p, phone, out, pid, remote, expected):
        def ready():
            names = p.command(["exec-out", "run-as", c.PKG, "ls", "-1", remote]).splitlines()
            snapshots = [name for name in names if SNAPSHOT_NAME.fullmatch(name)]
            cli.require(len(snapshots) <= 1, "multiple installation snapshots; preserve and reconcile")
            return snapshots[0] if snapshots else None
        name = cli.wait_until(ready, seconds=30)
        before = p.file_bytes(c.PKG, remote + "/health.json", 8192)
        raw = p.file_bytes(c.PKG, remote + "/" + name, c.envelope.MAX_BYTES + 8192)
        after = p.file_bytes(c.PKG, remote + "/health.json", 8192)
        for leaf, data in (("health-before.json", before), ("snapshot.jsonl", raw), ("health-after.json", after)):
            c.raw(out / "finished" / leaf, data)
        cli.require(p.command(["shell", "pidof", c.PKG]).strip() == str(pid), "installation App PID changed during retrieval")
        summary, _, _ = verify_full_snapshot(c.envelope, raw, expected, cli.record(out / "runtime-config.json")["sha256"],
            pid, c.apk["metadata"]["device_observation"]["sentinel"])
        return summary

    def launched_capture(self, c, p, phone, out, pid, expected):
        """A new PID plus the newest *old* directory is not a new observation."""
        actual, remote = phone.location(c, p, c.PKG)
        cli.require(actual == pid, "installation App restarted; retrieve original capture")
        if not phone.exists(p, c.PKG, remote + "/events.jsonl"):
            return None
        text = p.command(["exec-out", "run-as", c.PKG, "head", "-n", "2", remote + "/events.jsonl"])
        cli.require(len(text.encode()) <= 32768, "oversized capture header")
        rows = text.splitlines()
        if len(rows) < 2:
            return None
        try:
            header, stamp = (json.loads(row) for row in rows)
        except json.JSONDecodeError:
            return None  # Startup may have appended only part of its first two records.
        cli.require(header.get("kind") == "open" and header.get("schema") == 1 and header.get("seq") == 1,
                    "not an original App capture header")
        if header.get("pid") != pid:
            return None
        cli.require(header["captureId"] == remote.rsplit("/", 1)[-1] and
                    header["sentinel"] == c.apk["metadata"]["device_observation"]["sentinel"] and
                    c.envelope.same_device(header["target"], c.TARGET) and
                    stamp.get("kind") == "line" and stamp.get("seq") == 2,
                    "launched capture identity differs")
        verify_experiment(c.envelope, stamp["message"], expected, cli.record(out / "runtime-config.json")["sha256"])
        return remote

    def downloaded_package(self, c, p):
        # An existing filename may still hold a previous cell's completed download.
        path = "app_flutter/firmware/" + self.served_name
        size = p.command(["exec-out", "run-as", c.PKG, "stat", "-c", "%s", path]).strip()
        cli.require(re.fullmatch(r"0|[1-9][0-9]{0,19}", size), "invalid download cache size")
        if int(size) != len(c.screen_bytes):
            return None
        data = p.file_bytes(c.PKG, path, len(c.screen_bytes) + 1)
        return data if data == c.screen_bytes else None

    def observe_install(self, c, p, phone, out, pid, expected, observer=None, android=None):
        cli.require(self.group != cli.NATIVE_DIAGNOSTIC_GROUP or android is not None,
                    "native diagnostic requires its Android collector")
        started, active, admitted = time.monotonic(), None, False
        c.save(out / "status.json", dict(time=c.now(), result="APP_LAUNCHED_CONNECT_AND_DOWNLOAD", cell=c.cell), replace=True)
        while active is not None or time.monotonic() - started < cli.APP_START_SECONDS:
            cli.require(not (out / "stop.json").exists(), "installation observer stopped; reconcile before another action")
            if android is not None:
                android.require_ready()
            if not phone.exists(p, c.PKG, "files/p34-observations"):
                time.sleep(1)
                continue
            remote = self.launched_capture(c, p, phone, out, pid, expected)
            if remote is None:
                if observer is not None:
                    observer.require_ready()
                time.sleep(1)
                continue
            before = p.file_bytes(c.PKG, remote + "/health.json", 8192)
            health = json.loads(before)
            cli.require(health["healthy"] and health["lost"] == 0 and health["error"] is None and
                        0 <= health["upgradeEnds"] <= health["upgradeStarts"] <= 1, "installation capture is unhealthy or replayed")
            if health["upgradeStarts"]:
                active = active or time.monotonic()
                cli.require(time.monotonic() - active < cli.INSTALL_ACTIVE_SECONDS, "full installation observation deadline")
            if health["upgradeEnds"]:
                result = self.finish_install_snapshot(c, p, phone, out, pid, remote, expected)
                cli.require(admitted, "installation started before downloaded-input admission; preserve original result")
                return result
            if observer is not None and not health["upgradeStarts"]:
                observer.require_ready()
            if not admitted and not health["upgradeStarts"]:
                events = p.file_bytes(c.PKG, remote + "/events.jsonl", c.envelope.MAX_BYTES)
                after = p.file_bytes(c.PKG, remote + "/health.json", 8192)
                if json.loads(after)["upgradeStarts"]:
                    active = time.monotonic()
                    continue
                query, checkpoint, messages = p.query.validate(events, before, after, pid=pid,
                    sentinel=c.apk["metadata"]["device_observation"]["sentinel"], target=c.TARGET)
                download = "app_flutter/firmware/" + self.served_name
                if query["successfulQueries"] and phone.exists(p, c.PKG, download):
                    verify_experiment(c.envelope, messages, expected, cli.record(out / "runtime-config.json")["sha256"])
                    data = self.downloaded_package(c, p)
                    if data is None:
                        time.sleep(3)
                        continue
                    # Check again after the package read: admission must precede any BEGIN.
                    last = p.file_bytes(c.PKG, remote + "/health.json", 8192)
                    if json.loads(last)["upgradeStarts"]:
                        active = time.monotonic()
                        continue
                    native_query = android.admit_queries() if android is not None else None
                    for leaf, raw in (("health-before.json", before), ("health-after.json", after),
                                      ("health-ready.json", last), ("events.jsonl", events),
                                      ("checkpoint.jsonl", checkpoint), ("package.etu", data)):
                        c.raw(out / "queries" / leaf, raw)
                    c.save(out / "queries/result.json", dict(time=c.now(), query=query, pid=pid, remote=remote,
                        config=cli.record(out / "runtime-config.json"), start_inputs_verified_before=True,
                        **({"android_native": native_query} if native_query else {})))
                    admitted = True
                    c.save(out / "status.json", dict(time=c.now(), result="READY_FOR_FULL_INSTALL_START", cell=c.cell,
                        pid=pid, baud=921600, window=cli.cells_for(self.group)[cli.INSTALL_CELL][1],
                        package_bytes=len(data), target_version=c.target_version), replace=True)
            time.sleep(3)
        raise RuntimeError("App start window ended; no automatic installation retry")

    def install_worker(self, c, out, cell):
        cli.require(cell == cli.INSTALL_CELL, "unplanned installation cell")
        cell_out = out / "cells" / cell
        phone = self.phone(c, "p34_full_install")
        lock = c.load("p34_install_lock", self.root / "Tools/ota/repeat_cycle.py")
        result = dict(result="FULL_INSTALL_INCOMPLETE", cell=cell, n03_receive_measurement=False,
                      internal_installation_timing="NOT_OBSERVED")
        trace = android = None
        try:
            with lock.device_lock(), phone.usb(c, cell_out) as p, phone.network(c, cell_out) as origin:
                phone.release_old(c, p, cell_out)
                result["before"] = self.install_checkpoint(c, cell_out, before=True)
                self.verify_install_checkpoint(c, result["before"]["path"])
                try:
                    if self.group in cli.MEASURED_FULL_GROUPS:
                        module = c.load("p34_full_trace", self.root / "Tools/ota/p34_full_trace.py")
                        generation = (self.initial_sample(c, cell_out)["profile"]["run"] + 1) & 0xffffffff
                        trace = module.Trace(c, cell_out / "native-trace", generation)
                        trace.start()
                    expected = phone.config(c, cell, *cli.cells_for(self.group)[cell], origin)
                    pid = phone.provision(c, p, cell_out, expected)
                    if self.group == cli.NATIVE_DIAGNOSTIC_GROUP:
                        module = c.load("p34_android_trace", self.root / "Tools/ota/p34_android_trace.py")
                        android = module.Trace(c, p, cell_out / "android-trace", pid)
                        android.start()
                    kwargs = {"android": android} if android is not None else {}
                    result["summary"] = self.observe_install(c, p, phone, cell_out, pid, expected, observer=trace, **kwargs)
                    result["n03_receive_measurement"] = self.group in cli.MEASURED_FULL_GROUPS
                finally:
                    try:
                        if android is not None and android.process is not None:
                            result["android_trace"] = android.stop()
                    finally:
                        if trace:
                            result["native_trace"] = trace.stop()
                # The transition-aware reader must close before a fresh U identity owner.
                result["after"] = self.install_checkpoint(self.installed_context(out), cell_out)
                result["result"] = "FULL_INSTALL_OBSERVED"
            result["analysis"] = self.analyze_install(c, out, cell)
            result["result"] = result["analysis"]["result"]
            c.action("install-receiver", "completed", result=result["result"])
        except Exception as error:
            result["error"] = type(error).__name__ + ": " + str(error)
            c.action("install-receiver", "unknown", error=result["error"])
        c.save(cell_out / "result.json", dict(time=c.now(), **result))
        c.save(cell_out / "status.json", dict(time=c.now(), result=result["result"], error=result.get("error"), closed=True), replace=True)
        print(json.dumps(result), flush=True)
        return int("error" in result)

    def analyze_install(self, c, out, cell):
        """Reconcile original App/native evidence; never contact a device here."""
        cli.require(self.group in cli.INSTALL_GROUPS and cell == cli.INSTALL_CELL, "not an installation cell")
        destination = c.checked(out / "analysis" / str(time.time_ns()))
        cell_out = out / "cells" / cell
        plan = c.read(out / "plan.json")
        cli.require(plan["profile"] == cli.record(self.profile_path) and plan["bindings"] == c.bindings and
                    plan["target_bindings"] == self.installed_context(out).bindings, "installation archive binding changed")
        if self.group in cli.ALL_PATCH_GROUPS:
            cli.require(plan.get("package_kind") == c.package_kind, "PATCH archive package kind changed")
        expected = c.read(cell_out / "runtime-config.json")
        config = cli.record(cell_out / "runtime-config.json")
        launch = c.read(cell_out / "launch.json")
        origin_record = out / ("origin-record.json" if plan.get("cached_resume") else "live-network.json")
        cli.require(c.read(cell_out / "provision.json")["config"] == config and launch["apk"] == c.apk["apk"] and
                    expected == self.phone(c, "p34_install_archive").config(c, cell, *cli.cells_for(self.group)[cell],
                        c.read(origin_record)["origin"]), "installation configuration/launch changed")
        result = dict(result="INSTALL_ANALYSIS_REJECTED", cell=cell, no_transfer_replayed=True, analysis_sources=c.sources(),
                      n03_receive_measurement=False, internal_installation_timing="NOT_OBSERVED")
        try:
            candidates = [cell_out / "finished/snapshot.jsonl", *sorted((out / "collections").glob("**/snapshot-*.jsonl"))]
            matches, rejected = {}, []
            for path in candidates:
                if not path.exists():
                    continue
                try:
                    summary, messages, experiment = verify_full_snapshot(c.envelope, path.read_bytes(), expected,
                        config["sha256"], launch["pid"], c.apk["metadata"]["device_observation"]["sentinel"])
                    for leaf in ("health-before.json", "health-after.json"):
                        health = c.read(path.parent / leaf)
                        cli.require(health["healthy"] and health["lost"] == 0 and health["error"] is None and
                                    health["captureId"] == summary["captureId"] and health["outcome"] == "completed" and
                                    health["upgradeStarts"] == health["upgradeEnds"] == 1, "installation terminal health differs")
                    matches.setdefault(summary["rawSha256"], (path, summary, messages, experiment))
                except Exception as error:
                    rejected.append(dict(path=str(path), error=str(error)))
            cli.require(len(matches) == 1, "one original completed installation snapshot required: " + str(rejected))
            path, summary, messages, experiment = next(iter(matches.values()))
            query = c.read(cell_out / "queries/result.json")
            cli.require(query["start_inputs_verified_before"] is True and query["pid"] == launch["pid"] and
                        query["config"] == config and Path(cell_out / "queries/package.etu").read_bytes() == c.screen_bytes,
                        "installation downloaded-input proof changed")
            q = cell_out / "queries"
            verified, _, query_messages = c.p.query.validate((q / "events.jsonl").read_bytes(),
                (q / "health-before.json").read_bytes(), (q / "health-after.json").read_bytes(), pid=launch["pid"],
                sentinel=c.apk["metadata"]["device_observation"]["sentinel"], target=c.TARGET)
            health_ready = c.read(q / "health-ready.json")
            cli.require(verified["successfulQueries"] > 0 and health_ready["captureId"] == summary["captureId"] and
                        health_ready["healthy"] and health_ready["lost"] == 0 and health_ready["error"] is None and
                        health_ready["upgradeStarts"] == health_ready["upgradeEnds"] == 0, "installation started before admission")
            verify_experiment(c.envelope, query_messages, expected, config["sha256"])
            before = self.verify_install_checkpoint(c, cell_out / "mcu/closure.json")
            self.initial_sample(c, cell_out)
            inputs = dict(plan=cli.record(out / "plan.json"), config=config, snapshot=cli.record(path),
                launch=cli.record(cell_out / "launch.json"), query=cli.record(q / "result.json"),
                download=cli.record(q / "package.etu"), health_before=cli.record(path.parent / "health-before.json"),
                health_after=cli.record(path.parent / "health-after.json"))
            result.update(result="APP_FULL_INSTALL_VERIFIED", inputs=inputs, summary=summary, experiment=experiment,
                          before=before, start_inputs_verified_before=True)
            if self.group in cli.MEASURED_FULL_GROUPS:
                result["initial_state_evidence"] = zero_before_data(messages, "upgrade", c.screen["bytes"])
                module = c.load("p34_full_trace_analysis", self.root / "Tools/ota/p34_full_trace.py")
                result["full_metrics"] = module.full_metrics(messages, c.screen["bytes"], c.TARGET)
                result["n03_receive_measurement"] = True
                try:
                    result["native_trace"] = module.analyze(c, cell_out)
                    result["internal_installation_timing"] = "COARSE_ORIGINAL_PHASE_OBSERVATION"
                except (RuntimeError, OSError, KeyError, ValueError) as error:
                    result["native_trace"] = dict(result="EVIDENCE_GAP", detail=str(error))
                    result["internal_installation_timing"] = "EVIDENCE_GAP_NO_REPLAY"
                if self.group in cli.N04_LINEAGE_GROUPS:
                    restored = result["native_trace"].get("install_restore", {})
                    result["n04_install_measurement"] = self.group != "n04-bootstrap" and \
                        restored.get("result") == "INSTALL_RESTORE_PROFILE_VERIFIED"
                    result["n04_scope"] = ("new receiver installation path; sequential legal package" if self.group != "n04-bootstrap"
                                           else "bootstrap received/applied by W; not N04 installation benefit")
                    if self.group in cli.ALL_PATCH_GROUPS:
                        result.update(package_kind=c.package_kind,
                            patch_install_measurement=c.package_kind == "patch" and result["n04_install_measurement"],
                            coalescer_bootstrap=cli.ALL_PATCH_GROUPS[self.group]["asset_group"] == "bootstrap",
                            formal_reference_admitted=False)
            target = self.installed_context(out)
            native = [cell_out / "installed-mcu/closure.json", *sorted((out / "analysis").glob("*/installed-mcu/closure.json"))]
            existing = [item for item in native if item.exists()]
            if existing:
                result["after"] = self.verify_install_checkpoint(target, existing[-1])
                result["flash_admission"] = self.verify_receiver_admission(target, existing[-1].parent)
                if result["flash_admission"]:
                    result["result"] = "FULL_INSTALL_VERIFIED"
            c.raw(destination / "observations.log", messages.encode())
        except Exception as error:
            result.update(result="INSTALL_ANALYSIS_REJECTED", error=type(error).__name__, detail=str(error))
        result.update(time=c.now(), evidence=str(destination))
        c.save(destination / "result.json", result)
        c.save(out / "analysis/latest.json", dict(time=c.now(), cell=cell, result=result["result"],
            report=cli.record(destination / "result.json")), replace=True)
        cli.require(result["result"] != "INSTALL_ANALYSIS_REJECTED", "installation analysis rejected; see " + str(destination))
        return result

    def verify_install_readback(self, c, out, cell):
        for path in (out / "runtime").iterdir():
            cli.require(cli.owner_state(self.store, path)["state"] in ("CLOSED", "NOT_STARTED") or path.name == "network",
                        "close existing observers before installation readback")
        result = self.analyze_install(c, out, cell)
        if result["result"] == "FULL_INSTALL_VERIFIED":
            return result
        tests = cli.verify_tests(self.store)
        destination = Path(result["evidence"])
        c.save(destination / "readback-plan.json", dict(sources=c.sources(), tests=tests,
            analysis=cli.record(destination / "result.json"), target_bindings=self.installed_context(out).bindings))
        runtime = out / "runtime" / ("install-readback-" + destination.name)
        c.checked(runtime)
        c.supervisor.owned.launch(runtime, self.root / "Tools/ota/p34_session.py",
            ["--root", str(self.root), "--run", out.name, "--cell", cell, "--analysis", destination.name, "_install_readback"], 180)
        cli.wait_until(lambda: (runtime / "closed.json").exists(), seconds=195)
        closed = c.read(runtime / "closed.json")
        cli.require(closed["worker_exit"] == 0 and closed["forced_termination"] is False, "installation readback failed; no replay")
        return self.analyze_install(c, out, cell)

    def install_readback_worker(self, c, out, cell, name):
        cli.require(self.group in cli.INSTALL_GROUPS and cell == cli.INSTALL_CELL and name and name.isdecimal() and len(name) <= 24,
                    "invalid installation readback")
        destination = c.checked(out / "analysis" / name)
        plan = c.read(destination / "readback-plan.json")
        target = self.installed_context(out)
        cli.require(plan["sources"] == c.sources() and plan["analysis"] == cli.record(destination / "result.json") and
                    plan["target_bindings"] == target.bindings, "installation readback inputs changed")
        os.environ.update(c.environment())
        lock = c.load("p34_install_readback_lock", self.root / "Tools/ota/repeat_cycle.py")
        with lock.device_lock():
            self.install_checkpoint(target, destination)
        return 0

    def collect_install_capture(self, c, p, out, destination, cell):
        """Read the planned capture even if a newer App process/capture now exists."""
        query = c.read(out / "cells" / cell / "queries/result.json")
        remote = query["remote"]
        cli.require(remote.startswith("files/p34-observations/") and CAPTURE_NAME.fullmatch(remote.rsplit("/", 1)[-1]) and
                    remote == "files/p34-observations/" + remote.rsplit("/", 1)[-1], "invalid planned App capture path")
        names = p.command(["exec-out", "run-as", c.PKG, "ls", "-1", remote]).splitlines()
        snapshots = [name for name in names if SNAPSHOT_NAME.fullmatch(name)]
        payloads = {}
        for leaf, source, limit in (("health-before.json", "health.json", 8192),
                                   ("events.jsonl", "events.jsonl", c.envelope.MAX_BYTES),
                                   *[(name, name, c.envelope.MAX_BYTES + 8192) for name in snapshots],
                                   ("health-after.json", "health.json", 8192)):
            payloads[leaf] = c.raw(destination / "app" / leaf, p.file_bytes(c.PKG, remote + "/" + source, limit))
        value = dict(result="ORIGINAL_INSTALL_CAPTURE_COLLECTED", remote=remote, payloads=payloads,
                     no_transfer_replayed=True, no_app_restart=True)
        c.save(destination / "result.json", value)
        return value

    def analyze(self, c, out, cell):
        """Derive a new result from original bytes, never replace a failed receipt."""
        self.preflight(c, out)
        plan = c.read(out / "plan.json")
        cli.require(plan["profile"] == cli.record(self.profile_path) and plan["bindings"] == c.bindings,
                    "archived session belongs to different inputs/profile")
        cell_out = out / "cells" / cell
        destination = self.store.checked(out / "analysis" / str(time.time_ns()))
        snapshot = self.store.checked(cell_out / "finished/snapshot.jsonl")
        cli.require(snapshot.exists(), "original finished snapshot missing; collect from the App before analysis")
        config_path = cell_out / "runtime-config.json"
        expected = c.read(config_path)
        config = cli.record(config_path)
        launch = c.read(cell_out / "launch.json")
        cli.require(c.read(cell_out / "provision.json")["config"] == config and launch["apk"] == c.apk["apk"] and
                    expected["runId"] == cell and expected["packageSha256"] == c.screen["sha256"] and
                    expected["packageBytes"] == c.screen["bytes"] and
                    [expected["requestedBaud"], expected["senderWindowSegments"]] == plan["cells"][cell],
                    "original configuration/launch/plan binding changed")
        sources = c.sources()
        inputs = dict(plan=cli.record(out / "plan.json"), config=config, snapshot=cli.record(snapshot),
                      launch=cli.record(cell_out / "launch.json"))
        c.save(destination / "intent.json", dict(time=c.now(), sources=sources, inputs=inputs, no_device_operations=True))
        result = dict(result="ANALYSIS_REJECTED", cell=cell, inputs=inputs, sources=sources,
                      no_transfer_replayed=True, independent_acceptance=False)
        try:
            summary = c.envelope.extract(snapshot, destination / "parsed",
                c.apk["metadata"]["device_observation"]["sentinel"], c.TARGET, require_prefix_probe=True)
            messages = (destination / "parsed/observations.log").read_text(encoding="utf-8")
            experiment = verify_experiment(c.envelope, messages, expected, config["sha256"])
            cli.require(summary["pid"] == launch["pid"], "finished App PID differs from the launched process")
            for name in ("health-before.json", "health-after.json"):
                health = c.read(cell_out / "finished" / name)
                cli.require(health["captureId"] == summary["captureId"] and health["healthy"] is True and
                            health["lost"] == 0 and health["error"] is None and
                            health["upgradeStarts"] == health["upgradeEnds"] == 1 and
                            health["outcome"] == summary["outcome"], "terminal health/capture binding changed")
            probe = summary["prefixProbe"]
            result.update(result="APP_PREFIX_VERIFIED", summary=summary, experiment=experiment,
                prefix=probe, diagnostic_kib_s=probe["prefixBytes"] / 1024 / (probe["elapsedUs"] / 1000000),
                experiment_records=sum(line.startswith("OTA_EXPERIMENT ") for line in messages.splitlines()),
                mcu_staging_readback="NOT_CAPTURED")
            closure_path = cell_out / "mcu/closure.json"
            if closure_path.exists():
                closure = c.read(closure_path)
                cli.require(closure["retained_verified"] is True and "cleanup_error" not in closure,
                            "original MCU closure was not verified")
                for identities in (closure["initial_identity"], closure["final_identity"]):
                    for key, sha in (("app", c.receiver_image_sha), ("boot", c.BOOT_SHA)):
                        item = identities[key]
                        cli.require(cli.record(self.store.checked(item["path"])) == item and item["sha256"] == sha,
                                    "archived full MCU identity changed")
                final = closure["final_state"]
                zero = self.initial_sample(c, cell_out)
                for item in (final["profile_raw"], final["session_raw"], zero["profile_raw"]):
                    cli.require(cli.record(self.store.checked(item["path"])) == item, "archived terminal/control bytes changed")
                helper = c.load("p34_archive_mcu", c.HERE / "prefix_mcu.py")
                helper.idle(final)
                # Receiver-relative: the archived profile is sliced with the layout the
                # bound receiver declares (288/8 retained, 336/10 candidate).
                profile = helper.decode_terminal(c.m, Path(final["profile_raw"]["path"]).read_bytes(),
                    run=zero["profile"]["run"] + 1, baud=expected["requestedBaud"], total=c.screen["bytes"],
                    layout=c.instrumentation)
                if (cell_out / "fresh-begin.json").exists():
                    result["initial_state_evidence"] = zero_before_data(messages)
                    cli.require(probe["sentTotalBytes"] == probe["prefixBytes"] and profile["clean_counters"],
                                "paired prefix has retransmissions or MCU errors; not a clean comparison")
                session = final["session"]
                cli.require(session["package_sha256"] == c.screen["sha256"] and
                            session["durable_off"] == probe["prefixBytes"] and session["segment_bitmap"] == 0 and
                            session["last_ack_cmd"] == 0x84 and session["last_ack_seq"] == probe["abortSeq"],
                            "original MCU terminal differs from the App prefix")
                result.update(mcu_closure=cli.record(closure_path), profile=profile, retained_verified=True)
                journal, prefix = cell_out / "mcu/measured-journal.bin", cell_out / "mcu/measured-prefix.bin"
                if journal.exists() and prefix.exists():
                    decoded = c.decode_journal(journal.read_bytes(), c.screen["sha256"], c.screen["bytes"])
                    cli.require(decoded["durable_off"] == probe["prefixBytes"] and
                                prefix.read_bytes() == c.screen_bytes[:probe["prefixBytes"]], "original staging readback changed")
                    result.update(mcu_staging_readback="VERIFIED", journal=cli.record(journal), staging_prefix=cli.record(prefix))
        except Exception as error:
            result.update(result="ANALYSIS_REJECTED", error=type(error).__name__, detail=str(error))
        latest = out / "analysis/latest.json"
        if result["result"] == "APP_PREFIX_VERIFIED" and latest.exists():
            previous = c.read(latest)
            if previous.get("cell") == cell and previous.get("result") == "PREFIX_RECONCILED":
                cli.require(cli.record(self.store.checked(previous["report"]["path"])) == previous["report"] and
                            cli.record(self.store.checked(previous["readback"]["path"])) == previous["readback"],
                            "previous reconciliation evidence changed")
                old = c.read(previous["report"]["path"])
                if old["inputs"] == inputs and old.get("mcu_closure") == result.get("mcu_closure"):
                    result.update(readback=previous["readback"], mcu_staging_readback="VERIFIED")
        result.update(time=c.now(), evidence=str(destination))
        c.save(destination / "result.json", result)
        pointer = dict(time=c.now(), cell=cell, result=result["result"], report=cli.record(destination / "result.json"))
        if result.get("readback"):
            pointer.update(result="PREFIX_RECONCILED", readback=result["readback"])
        c.save(latest, pointer, replace=True)
        cli.require(result["result"] != "ANALYSIS_REJECTED", "offline analysis failed; see " + str(destination / "result.json"))
        return result

    def verify_readback(self, c, out, cell):
        for name in cli.CELLS:
            cli.require(cli.owner_state(self.store, out / "runtime" / name)["state"] in ("NOT_STARTED", "CLOSED"),
                        "close the existing MCU observer before a readback")
        tests = cli.verify_tests(self.store)
        analysis = self.analyze(c, out, cell)
        cli.require(analysis.get("retained_verified") is True, "no verified original MCU closure for reconciliation")
        destination = Path(analysis["evidence"])
        if analysis.get("readback"):
            return dict(result="PREFIX_RECONCILED", cell=cell, evidence=str(destination),
                diagnostic_kib_s=analysis["diagnostic_kib_s"], prefix=analysis["prefix"], retained_verified=True,
                no_transfer_replayed=True, mcu_staging_readback="VERIFIED", reused_readback=analysis["readback"])
        if analysis["mcu_staging_readback"] == "VERIFIED":
            proof = destination / "readback-result.json"
            c.save(proof, dict(time=c.now(), result="PREFIX_READBACK_VERIFIED", evidence_source="ORIGINAL_MEASUREMENT",
                closure=c.read(analysis["mcu_closure"]["path"]), journal=analysis["journal"], prefix=analysis["staging_prefix"],
                no_transfer_replayed=True, no_device_operations=True))
            c.save(out / "analysis/latest.json", dict(time=c.now(), cell=cell, result="PREFIX_RECONCILED",
                report=cli.record(destination / "result.json"), readback=cli.record(proof)), replace=True)
            return dict(result="PREFIX_RECONCILED", cell=cell, evidence=str(destination),
                diagnostic_kib_s=analysis["diagnostic_kib_s"], prefix=analysis["prefix"], retained_verified=True,
                no_transfer_replayed=True, mcu_staging_readback="VERIFIED", reused_original_readback=True)
        runtime = self.store.checked(out / "runtime" / ("readback-" + destination.name))
        for path in (runtime, destination / "readback", destination / "readback-result.json",
                     destination / "readback-plan.json", destination / "host", destination / "actions.jsonl"):
            self.store.checked(path)
        c.save(destination / "readback-plan.json", dict(time=c.now(), sources=c.sources(), bindings=c.bindings,
            analysis=cli.record(destination / "result.json"), tests=tests, no_transfer=True, no_reset=True,
            no_tuning=True, no_firmware_install=True, seconds=180))
        c.supervisor.owned.launch(runtime, self.root / "Tools/ota/p34_session.py",
            ["--root", str(self.root), "--run", out.name, "--cell", cell, "--analysis", destination.name, "_readback"], 180)
        cli.wait_until(lambda: (runtime / "closed.json").exists(), seconds=195)
        closed = c.read(runtime / "closed.json")
        result = c.read(destination / "readback-result.json")
        cli.require(closed.get("worker_exit") == 0 and closed.get("forced_termination") is False and
                    result["result"] == "PREFIX_READBACK_VERIFIED", "readback failed; preserve its original result")
        c.save(out / "analysis/latest.json", dict(time=c.now(), cell=cell, result="PREFIX_RECONCILED",
            report=cli.record(destination / "result.json"), readback=cli.record(destination / "readback-result.json")), replace=True)
        return dict(result="PREFIX_RECONCILED", cell=cell, evidence=str(destination),
            diagnostic_kib_s=analysis["diagnostic_kib_s"], prefix=analysis["prefix"],
            retained_verified=True, no_transfer_replayed=True, mcu_staging_readback="VERIFIED")

    def readback_worker(self, c, out, cell, name):
        cli.require(name and name.isdecimal() and len(name) <= 24, "invalid analysis identifier")
        destination = self.store.checked(out / "analysis" / name)
        plan = c.read(destination / "readback-plan.json")
        cli.require(plan["sources"] == c.sources() and plan["bindings"] == c.bindings and
                    plan["analysis"] == cli.record(destination / "result.json"), "readback source/input binding changed")
        analysis = c.read(destination / "result.json")
        closure_path = out / "cells" / cell / "mcu/closure.json"
        cli.require(analysis["cell"] == cell and analysis["mcu_closure"] == cli.record(closure_path),
                    "original MCU closure binding changed")
        previous = c.read(closure_path)["final_state"]
        c.cell, c.action_out, c.host.OUT = cell, destination, destination
        os.environ.update(c.environment())
        lock = c.load("p34_readback_lock", self.root / "Tools/ota/repeat_cycle.py")
        helper = c.load("p34_readback_mcu", c.HERE / "prefix_mcu.py")
        result, mcu = dict(result="READBACK_FAILED", plan=cli.record(destination / "readback-plan.json")), None
        try:
            with lock.device_lock():
                mcu = helper.Mcu(c, destination / "readback")
                try:
                    mcu.open()
                    live = mcu.sample("reconcile-live")
                    same_terminal(live, previous)
                    verified = mcu.journal("reconciled", c.screen, analysis["prefix"]["prefixBytes"])
                    same_terminal(verified, previous)
                    result.update(result="PREFIX_READBACK_VERIFIED", sample=verified,
                        journal=cli.record(destination / "readback/reconciled-journal.bin"),
                        prefix=cli.record(destination / "readback/reconciled-prefix.bin"), no_transfer_replayed=True)
                finally:
                    result["closure"] = mcu.close(restore=False)
        except Exception as error:
            result.update(result="READBACK_FAILED", error=type(error).__name__, detail=str(error))
        c.save(destination / "readback-result.json", dict(time=c.now(), **result))
        return int(result["result"] != "PREFIX_READBACK_VERIFIED")

    def collect(self, c, out, cell, *, offline=False, verify_mcu=False):
        if self.group in cli.INSTALL_GROUPS:
            if verify_mcu:
                return self.verify_install_readback(c, out, cell)
            if offline:
                return self.analyze_install(c, out, cell)
        if verify_mcu:
            return self.verify_readback(c, out, cell)
        if offline:
            return self.analyze(c, out, cell)
        destination = out / "collections" / str(time.time_ns())
        cell_out = out / "cells" / cell
        owner = cli.owner_state(self.store, out / "runtime" / cell)
        planned_install = self.group in cli.INSTALL_GROUPS and (cell_out / "queries/result.json").exists()
        if owner["state"] == "LIVE" and (cell_out / "usb/ready.json").exists() and not (cell_out / "usb/closed.json").exists():
            c.p.RUNTIME = cell_out / "usb"
            if planned_install:
                value = self.collect_install_capture(c, c.p, out, destination, cell)
            else:
                value = self.capture(c, c.p, self.phone(c, "p34_live_collection"), destination / "app")
                if value.get("health"):
                    c.save(cell_out / "health-live.json", dict(observed=c.now(), health=value["health"]), replace=True)
                c.save(destination / "result.json", dict(time=c.now(), **value, borrowed_usb=True))
        else:
            cli.require(owner["state"] in ("CLOSED", "NOT_STARTED"), "USB owner uncertain; no competing collector")
            if planned_install:
                phone = self.phone(c, "p34_install_retrieval")
                lock = c.load("p34_install_retrieval_lock", self.root / "Tools/ota/repeat_cycle.py")
                with lock.device_lock(), phone.usb(c, destination) as p:
                    value = self.collect_install_capture(c, p, out, destination, cell)
            else:
                value = self.inspect(c, destination)
        value["evidence"] = str(destination)
        value["no_transfer_replayed"] = True
        return value
