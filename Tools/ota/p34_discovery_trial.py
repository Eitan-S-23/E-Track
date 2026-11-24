"""One legal30244-to30245 discovery-deadline screen; never replay its predecessor."""
import argparse
import copy
import json
import os
from pathlib import Path
import runpy
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_session as cli
import p34_session_backend as backend
import p34_reconnect_followup as parent
import p34_discovery_assets as assets_api
import p34_discovery_query as query_api
import p34_install_cost as host

AREA = ROOT / ".cache/p34-discovery-fix"
ASSETS = AREA / "assets/result.json"
APK_REPORT = AREA / "apk-g1/apk.json"
TRIAL = AREA / "trial-001"
TEST = ROOT / "tests/ota/test_p34_discovery_trial.py"
SPEC = assets_api.SPEC
COMMIT = query_api.COMMIT
RAW_SHA = query_api.RAW_SHA
BOOT_SHA = parent.BOOT_SHA


def load_assets(s):
    value = s.read(ASSETS)
    cli.require(value["result"] == "DISCOVERY_SUCCESSOR_ASSETS_VERIFIED" and value["hardware"] is False and
                value["admission_negative_checks"] == 3, "verified successor assets required")
    for item in value["inputs"] + value["outputs"]:
        cli.require(cli.record(s.checked(item["path"])) == item, "successor evidence changed")
    group = value["group"]
    cli.require(group["specification"] == SPEC and group["receiver"]["sha256"] == RAW_SHA and
                group["target_identity"]["version_code"] == 30245 and group["package_kind"] == "full",
                "successor identity mismatch")
    before, after = (Path(group[k]["path"]).read_bytes() for k in ("receiver", "target"))
    cli.require(len(before) == len(after) and before[:0x400] + before[0x460:] == after[:0x400] + after[0x460:],
                "executable bytes changed")
    expected = copy.deepcopy(group["receiver_bindings"])
    expected["profile"].update(image=group["target"], identity=group["target_identity"], prefix=after[:0x460].hex())
    cli.require(expected == group["target_bindings"] and expected["whole_boot"]["sha256"] == BOOT_SHA,
                "target runtime/Boot binding mismatch")
    cli.require(all(group["decoded"][k] for k in ("passed", "byte_identical", "boot_ok", "guards_ok", "workspace_lifecycle_ok")) and
                len(group["negatives"]) == 4 and all(n["native"]["passed"] and n["native"]["prepares"] == 0
                for n in group["negatives"]), "native package guards failed")
    return group


def apk(s):
    value = s.read(APK_REPORT)
    cert = runpy.run_path(str(ROOT / "Tools/ota/p34_signing_artifacts.py"))
    cli.require(value["sha"] == COMMIT and value["run"] == 36935410469 and
                cli.record(value["apk"]["path"]) == value["apk"] and value["certificate_sha256"] == cert["CERT"] and
                cert["apk_certificate"](Path(value["apk"]["path"]).read_bytes()) == cert["CERT"] and
                value["metadata"]["application_id"] == query_api.PKG and not value["independent_acceptance"],
                "exact fixed-signer APK provenance required")
    hosts = set()
    for item in value["host_reports"]:
        cli.require(cli.record(item["path"]) == item, "host report changed")
        report = s.read(item["path"])
        cli.require(report["development_result"] == "PASS" and report["scope"] == "all" and
                    report["source_before"]["head"] == COMMIT and report["source_before"]["clean"],
                    "both exact host passes required")
        hosts.add(json.dumps(report["host"], sort_keys=True))
    cli.require(len(hosts) == len(value["host_reports"]) == 2, "two distinct host reports required")
    return value


def predecessor(s, group):
    pointer = s.read(parent.TRIAL / "analysis/latest.json")
    cli.require(cli.record(pointer["report"]["path"]) == pointer["report"], "predecessor report changed")
    report = s.read(pointer["report"]["path"])
    old = parent.load_assets(s)
    cli.require(group["receiver"] == old["target"] and group["receiver_bindings"] == old["target_bindings"],
                "successor does not continue the confirmed receiver")
    closure = s.read(report["after"]["path"])
    assets_api.validate_parent(report, old, closure)
    records = [pointer["report"], *report["inputs"].values(), report["after"]]
    for phase in ("initial_identity", "final_identity"):
        records += [closure[phase][k] for k in ("app", "boot")]
    for item in records:
        cli.require(cli.record(s.checked(item["path"])) == item, "original completed evidence changed")
    records += [parent.closed(s, parent.TRIAL / "runtime" / name) for name in ("coordinator", "network", "s04")]
    return dict(plan=s.read(report["inputs"]["plan"]["path"]), inputs=records,
                descriptor=dict(kind="FULL_INSTALL_VERIFIED", report=pointer["report"], version=30244))


def installed_query(s, report):
    installed = s.read(AREA / "install-001/result.json")
    cli.require(installed["result"] == "FIXED_SIGNER_DISCOVERY_UPDATE_VERIFIED" and installed["usb_closed"] and
                installed["installed"]["sha256"] == report["apk"]["sha256"] and
                installed["original_snapshot_preserved"] and installed["configuration_preserved"],
                "verified in-place discovery installation missing")
    query = s.read(query_api.OUT / "result.json")
    cli.require(query["result"] == "DISCOVERY_APK_QUERY_SUCCEEDED" and query["usb_closed"] and query["no_ota"] and
                query["query"]["successfulQueries"] > 0 and query["query"]["pid"] == query["pid"] and
                not query["post_ota_cold_reconnect_acceptance"], "new APK query incomplete")
    files = [AREA / "install-001/result.json", AREA / "install-001/runtime-config.json", query_api.OUT / "result.json"]
    files += [query_api.OUT / n for n in ("events.jsonl", "health-before.json", "health-after.json", "logcat.log")]
    cli.require(cli.record(query["logcat"]["path"]) == query["logcat"], "query log changed")
    return [cli.record(p) for p in files] + [parent.closed(s, AREA / "runtime" / n) for n in ("install", "query")]


def validate_config(value, group):
    fixed = dict(schema=3, runId="s04", requestedBaud=921600, senderWindowSegments=28,
        reuseGatt=True, withoutResponse=True, transferMode="full", prefixBytes=0,
        rebootInfoTimeoutMs=2000, rebootProbeIntervalMs=500, currentVersionCode=30244,
        targetVersionCode=30245, currentImageSha256=RAW_SHA, targetImageSha256=group["target"]["sha256"],
        packageBytes=group["package"]["bytes"], packageSha256=group["package"]["sha256"])
    cli.require(all(type(value.get(k)) is type(v) and value[k] == v for k, v in fixed.items()),
                "discovery screen fixed axis or full identity changed")


class Discovery(parent.Followup):
    def __init__(self, s):
        self.assets = load_assets(s)
        self.proof = predecessor(s, self.assets)
        self.report = apk(s)
        self.query_inputs = installed_query(s, self.report)
        path = Path(self.proof["plan"]["profile"]["path"])
        backend.Backend.__init__(self, s, path, s.read(path), cli.RECONNECT_GROUP)
        self.receiver_version, self.target_version = 30244, 30245
        self.served_name = SPEC["served_name"]

    def context(self, out):
        c = backend.Backend.context(self, out)
        c.n04_prior_assets += [c.full_assets, parent.load_assets(self.store)]
        c.previous_assets = c.n04_prior_assets[-1]
        c.full_assets, c.bindings = self.assets, self.assets["receiver_bindings"]
        c.spec = dict(c.spec, **SPEC)
        c.receiver_version, c.target_version = 30244, 30245
        c.served_name, c.release_key = SPEC["served_name"], SPEC["release_key"]
        c.served = c.screen = self.assets["package"]
        c.screen_bytes = Path(c.screen["path"]).read_bytes()
        c.target, c.target_identity = self.assets["target"], self.assets["target_identity"]
        c.apk, c.APK_SHA, c.BOOT_SHA = self.report, self.report["apk"]["sha256"], BOOT_SHA
        saved_query = self.store.read(query_api.OUT / "result.json")
        query, _, _ = c.p.query.validate((query_api.OUT / "events.jsonl").read_bytes(),
            (query_api.OUT / "health-before.json").read_bytes(), (query_api.OUT / "health-after.json").read_bytes(),
            pid=saved_query["pid"], sentinel=self.report["metadata"]["device_observation"]["sentinel"], target=c.TARGET)
        cli.require(query == saved_query["query"], "new query differs from original App bytes")
        identity = ("addr=02:00:00:00:00:01 result=ok wire=E-Track model=e-track-at32f435 "
                    "vcode=30244 hw=1 layout=1 boot=1 proto=1 window=32 sha=" + RAW_SHA)
        log = (query_api.OUT / "logcat.log").read_text(encoding="utf-8")
        cli.require(any(line.split("OTA_OBS identity ", 1)[1] == identity for line in log.splitlines()
                        if "OTA_OBS identity " in line), "full30244 App query identity missing")
        c.flash_addresses = backend.bind_flash_gate(c.bindings["profile"],
            self.legacy["named"]["restored"]["clock"]["gate"]["symbol"])
        original = c.sources
        extra = [cli.record(p) for p in (__file__, TEST, ASSETS, APK_REPORT, parent.__file__, assets_api.__file__, query_api.__file__)]
        c.sources = lambda: sorted({r["path"]: r for r in [*original(), *extra, *self.proof["inputs"],
            *self.query_inputs, self.report["apk"], *self.report["host_reports"]]}.values(), key=lambda r: r["path"])
        return c

    def predecessor(self, c):
        cli.require(c.bindings == self.assets["receiver_bindings"], "wrong confirmed30244 receiver")
        return self.proof

    def known_configs(self, c):
        return {cli.record(AREA / "install-001/runtime-config.json")["sha256"]}

    def phone(self, c, name, *, producer=False):
        phone = backend.Backend.phone(self, c, name, producer=producer)
        raw = self.legacy["named"]["raw_load"](name + "_raw", c.HERE / "prefix_phone.py")
        def config(c, cell, baud, window, origin):
            value = dict(raw.config(c, cell, baud, window, origin), schema=3, transferMode="full", prefixBytes=0,
                         rebootInfoTimeoutMs=2000, rebootProbeIntervalMs=500)
            validate_config(value, self.assets)
            return value
        phone.config = config
        provision = phone.provision
        def checked_provision(c, p, out, value):
            backend.checked_phone_path(c, p, "files/p34-experiment.json", new_leaf=True)
            return provision(c, p, out, value)
        phone.provision = checked_provision
        return phone


def test_receipt(s):
    path = AREA / "tests/result.json"
    value = s.read(path)
    cli.require(value["result"] == "PASS" and value["source"] == cli.record(__file__) and
                value["test"] == cli.record(TEST), "current discovery adapter tests required")
    return cli.record(path)


def owner(s, mode):
    supervisor = cli.load_module("discovery_trial_owner", ROOT / ".cache/p3-4-screening-20260922/supervisor.py")
    if mode == "launch":
        test_receipt(s)
        cli.require(not TRIAL.exists(), "trial already reserved; reconcile its original outcome")
        api = Discovery(s)
        c = api.context(TRIAL)
        api.preflight(c, TRIAL)
        s.write(TRIAL / "intent.json", dict(time=cli.now(), sources=c.sources(), tests=test_receipt(s),
            scope="one30244-to30245 discovery screen; no automatic UI/OTA/replay", retained_boot=BOOT_SHA,
            independent_acceptance=False))
        print(supervisor.owned.launch(TRIAL / "runtime/coordinator", Path(__file__), ["coordinator"], 6000), flush=True)
        return
    cli.require(supervisor.owned.in_job(), "finite detached owner required")
    api = Discovery(s)
    c = api.context(TRIAL)
    api.preflight(c, TRIAL)
    cli.require(c.sources() == s.read(TRIAL / "intent.json")["sources"], "running sources changed")
    os.environ.update(c.environment())
    if mode == "coordinator":
        result, network_started = dict(result="DISCOVERY_SCREEN_INCOMPLETE"), False
        try:
            observed = api.inspect(c, TRIAL / "prestart-phone")
            api.prepare(c, TRIAL, observed, test_receipt(s))
            supervisor.owned.launch(TRIAL / "runtime/network", Path(__file__), ["network"], cli.NETWORK_SUPERVISOR_SECONDS)
            network_started = True
            def ready():
                cli.require(cli.owner_state(s, TRIAL / "runtime/network")["state"] != "CLOSED", "network closed before ready")
                return (TRIAL / "live-network.json").exists()
            cli.wait_until(ready, seconds=cli.NETWORK_READY_WAIT_SECONDS)
            api.network_ready(c, TRIAL)
            supervisor.owned.launch(TRIAL / "runtime/s04", Path(__file__), ["cell"], cli.CELL_SECONDS)
            s.write(TRIAL / "coordinator-ready.json", dict(time=cli.now(), cell="s04"))
            cli.wait_until(lambda: (TRIAL / "runtime/s04/closed.json").exists(), seconds=cli.CELL_SECONDS + 30)
            result.update(cell=s.read(TRIAL / "cells/s04/result.json"), owner=s.read(TRIAL / "runtime/s04/closed.json"))
            result["result"] = result["cell"]["result"]
        except Exception as error:
            result.update(error=type(error).__name__, detail=str(error))
        finally:
            if network_started:
                s.write(TRIAL / "network-stop.json", dict(time=cli.now(), reason="coordinator-closure"))
                cli.wait_until(lambda: (TRIAL / "runtime/network/closed.json").exists(), seconds=90)
                result["network_owner"] = s.read(TRIAL / "runtime/network/closed.json")
            s.write(TRIAL / "coordinator-result.json", dict(time=cli.now(), **result))
        cli.require("error" not in result, "discovery screen requires reconciliation")
    else:
        api.validate(c, TRIAL)
        code = api.network_worker(c, TRIAL) if mode == "network" else api.cell_worker(c, TRIAL, "s04")
        cli.require(code == 0, "owned discovery worker failed; preserve evidence")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("check", "launch", "coordinator", "network", "cell"))
    args = parser.parse_args()
    s = cli.Store(ROOT)
    if args.mode == "check":
        api = Discovery(s)
        c = api.context(TRIAL)
        config = api.phone(c, "discovery_offline").config(c, "s04", 921600, 28, "https://offline.trycloudflare.com")
        validate_config(config, api.assets)
        cli.require(api.installed_context(TRIAL).receiver_image_sha == api.assets["target"]["sha256"], "target context mismatch")
        print(json.dumps(dict(result="OFFLINE_DISCOVERY_BINDINGS_VERIFIED", config=config,
            sources=len(c.sources()), predecessor=api.predecessor(c)["descriptor"])), flush=True)
    else:
        owner(s, args.mode)


if __name__ == "__main__":
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                "explicit root and isolated Python required")
    main()
