"""Source-bound schema4 radio matrix; each arm requires its real confirmed predecessor."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import runpy
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_session as cli
import p34_discovery_trial as old
import p34_radio_assets as assets_api

AREA = ROOT / ".cache/p34-radio-fix"
ASSETS = AREA / "assets/result.json"
APK = AREA / "apk-g1/apk.json"
INSTALL = AREA / "install-002"
HOST_TESTS = AREA / "host-tests-003"
TRIALS = AREA / "trials-v2"
TEST = ROOT / "tests/ota/test_p34_radio_trial.py"
COMMIT = "254e78507d27aedc636cca3614272003e67bd369"
ORDER = tuple(x[0] for x in assets_api.MATRIX)
backend = cli.load_module("radio_private_backend", ROOT / "Tools/ota/p34_session_backend.py")
original_verify = backend.verify_experiment
EXTRA = dict(rebootInfoTimeoutMs=2000, rebootProbeIntervalMs=500)


def verify_radio(capture, messages, expected, sha):
    cli.require(type(expected.get("schema")) is int and expected["schema"] == 4 and
                expected.get("transferMode") == "full" and type(expected.get("prefixBytes")) is int and
                expected["prefixBytes"] == 0, "radio requires schema4 FULL")
    for key, value in EXTRA.items():
        cli.require(type(expected.get(key)) is int and expected[key] == value, "radio cadence changed")
    for key in ("pauseScanDuringOta", "androidHighPriority"):
        cli.require(type(expected.get(key)) is bool, "radio flag must be boolean")
    item = original_verify(capture, messages, expected, sha)
    for key in (*EXTRA, "pauseScanDuringOta", "androidHighPriority"):
        cli.require(type(item.get(key)) is type(expected[key]) and item[key] == expected[key], "radio observation axis mismatch")
    fields = set(expected) - {"target", "firmwareLatestUrl"} | {"deviceAddress", "endpointHost", "configSha256"}
    cli.require(set(item) == fields, "unknown or missing radio observation field")
    return item


backend.verify_experiment = verify_radio


def assets(s, arm):
    value = s.read(ASSETS)
    cli.require(value["result"] == "RADIO_MATRIX_ASSETS_VERIFIED" and value["hardware"] is False and
                value["order"] == list(ORDER) and value["confirmed_start"] == 30245, "matrix identity differs")
    for item in value["inputs"] + value["outputs"]:
        cli.require(cli.record(s.checked(item["path"])) == item, "matrix bytes changed")
    group = value["groups"][arm]
    original_name = "p34-radio-" + arm + ".etu"
    cli.require(group["specification"]["served_name"] == original_name, "unexpected original filename")
    # Correct only the served metadata; preserve the verified package and manifest.
    return dict(group, specification=dict(group["specification"],
        served_name="p34-radio-" + arm + "-full.etu"))


def apk(s):
    value = s.read(APK)
    signing = runpy.run_path(str(ROOT / "Tools/ota/p34_signing_artifacts.py"))
    cli.require(value["sha"] == COMMIT and value["certificate_sha256"] == signing["CERT"] and
                value["metadata"]["application_id"] == "com.wen.gaia.gaia.p34probe" and
                cli.record(value["apk"]["path"]) == value["apk"] and
                signing["apk_certificate"](Path(value["apk"]["path"]).read_bytes()) == signing["CERT"],
                "exact fixed-signer radio APK required")
    hosts = set()
    for record in value["host_reports"]:
        cli.require(cli.record(record["path"]) == record, "CI report changed")
        report = s.read(record["path"])
        cli.require(report["development_result"] == "PASS" and report["scope"] == "all" and
                    report["source_before"]["head"] == COMMIT and report["source_before"]["clean"], "both hosts must pass")
        hosts.add(json.dumps(report["host"], sort_keys=True))
    cli.require(len(hosts) == len(value["host_reports"]) == 2, "distinct both-host reports required")
    installed = s.read(INSTALL / "result.json")
    cli.require(installed["result"] == "FIXED_SIGNER_RADIO_UPDATE_VERIFIED" and installed["usb_closed"] and
                installed["installed"]["sha256"] == value["apk"]["sha256"] and
                installed["original_snapshot_preserved"] and installed["configuration_preserved"], "radio installation unresolved")
    return value


def confirmed_predecessor(s, arm, group):
    index = ORDER.index(arm)
    root = old.TRIAL if index == 0 else TRIALS / ORDER[index - 1]
    pointer = s.read(root / "analysis/latest.json")
    cli.require(cli.record(pointer["report"]["path"]) == pointer["report"], "predecessor report changed")
    report = s.read(pointer["report"]["path"])
    cli.require(report["result"] == "FULL_INSTALL_VERIFIED" and report["summary"]["outcome"] == "completed" and
                report["summary"]["input"]["targetVersionCode"] == group["specification"]["receiver"] and
                report["summary"]["input"]["targetImageSha256"] == group["receiver"]["sha256"],
                "actual confirmed predecessor required; prepared lineage is not identity")
    closure = s.read(report["after"]["path"])
    cli.require(closure["retained_verified"] and closure["reader_closed"] and "cleanup_error" not in closure and
                all(closure[k] is True for k in ("no_reset", "no_halt", "no_flash", "no_nvic_write")), "unresolved native closure")
    records = [pointer["report"], *report["inputs"].values(), report["after"]]
    for phase in ("initial_identity", "final_identity"):
        for key, expected in (("app", group["receiver"]), ("boot", group["receiver_bindings"]["whole_boot"])):
            item = closure[phase][key]
            cli.require((item["bytes"], item["sha256"]) == (expected["bytes"], expected["sha256"]), "full raw predecessor differs")
            records.append(item)
    state = closure["final_state"]
    cli.require(state["bcb_state"] == 4 and all(state[k] == 1 for k in ("confirm_done", "state_snapped", "sd_ready")),
                "ordinary healthy-App confirmation missing")
    for item in records:
        cli.require(cli.record(s.checked(item["path"])) == item, "original predecessor bytes changed")
    records += [old.parent.closed(s, root / "runtime" / n) for n in ("coordinator", "network", "s04")]
    return dict(report=report, plan=s.read(report["inputs"]["plan"]["path"]), inputs=records,
        descriptor=dict(kind="FULL_INSTALL_VERIFIED", report=pointer["report"], run=str(root)))


def validate_config(value, group):
    spec = group["specification"]
    fixed = dict(schema=4, runId="s04", requestedBaud=921600, senderWindowSegments=28,
        reuseGatt=True, withoutResponse=True, transferMode="full", prefixBytes=0, **EXTRA,
        pauseScanDuringOta=spec["pauseScanDuringOta"], androidHighPriority=spec["androidHighPriority"],
        currentVersionCode=spec["receiver"], targetVersionCode=spec["target_version"],
        currentImageSha256=group["receiver"]["sha256"], targetImageSha256=group["target"]["sha256"],
        packageBytes=group["package"]["bytes"], packageSha256=group["package"]["sha256"])
    cli.require(all(type(value.get(k)) is type(v) and value[k] == v for k,v in fixed.items()), "radio input axis changed")


class Radio(backend.Backend):
    def __init__(self, s, arm):
        self.arm, self.assets = arm, assets(s, arm)
        self.proof = confirmed_predecessor(s, arm, self.assets)
        self.report = apk(s)
        path = Path(self.proof["plan"]["profile"]["path"])
        super().__init__(s, path, s.read(path), cli.RECONNECT_GROUP)
        spec = self.assets["specification"]
        self.receiver_version, self.target_version = spec["receiver"], spec["target_version"]
        self.served_name = spec["served_name"]

    def context(self, out):
        c = super().context(out)
        c.n04_prior_assets += [c.full_assets, old.parent.load_assets(self.store), old.load_assets(self.store)]
        value = self.store.read(ASSETS)
        c.n04_prior_assets += [value["groups"][name] for name in ORDER[:ORDER.index(self.arm)]]
        c.previous_assets = c.n04_prior_assets[-1]
        c.full_assets, c.bindings = self.assets, self.assets["receiver_bindings"]
        spec = self.assets["specification"]
        c.spec = dict(c.spec, **spec)
        c.receiver_version, c.target_version = spec["receiver"], spec["target_version"]
        c.served_name, c.release_key = spec["served_name"], spec["release_key"]
        c.served = c.screen = self.assets["package"]
        c.screen_bytes = Path(c.screen["path"]).read_bytes()
        c.target, c.target_identity = self.assets["target"], self.assets["target_identity"]
        c.apk, c.APK_SHA = self.report, self.report["apk"]["sha256"]
        c.BOOT_SHA = self.assets["receiver_bindings"]["whole_boot"]["sha256"]
        c.flash_addresses = backend.bind_flash_gate(c.bindings["profile"], self.legacy["named"]["restored"]["clock"]["gate"]["symbol"])
        original = c.sources
        extra = [cli.record(p) for p in (__file__, TEST, ASSETS, APK, assets_api.__file__, old.__file__,
            INSTALL / "result.json", INSTALL / "runtime-config.json")]
        c.sources = lambda: sorted({x["path"]:x for x in [*original(), *extra, *self.proof["inputs"],
            self.report["apk"], *self.report["host_reports"]]}.values(), key=lambda x:x["path"])
        return c

    def predecessor(self, c):
        cli.require(c.bindings == self.assets["receiver_bindings"], "wrong radio predecessor binding")
        return self.proof

    def known_configs(self, c):
        return {self.proof["report"]["inputs"]["config"]["sha256"]}

    def phone(self, c, name, *, producer=False):
        phone = super().phone(c, name, producer=producer)
        raw = self.legacy["named"]["raw_load"](name + "_radio_raw", c.HERE / "prefix_phone.py")
        spec = self.assets["specification"]
        def config(c, cell, baud, window, origin):
            value = dict(raw.config(c, cell, baud, window, origin), schema=4, transferMode="full", prefixBytes=0,
                **EXTRA, pauseScanDuringOta=spec["pauseScanDuringOta"], androidHighPriority=spec["androidHighPriority"])
            validate_config(value, self.assets)
            return value
        phone.config = config
        provision = phone.provision
        def checked_provision(c, p, out, value):
            backend.checked_phone_path(c, p, "files/p34-experiment.json", new_leaf=True)
            return provision(c, p, out, value)
        phone.provision = checked_provision
        return phone

    def retire_initial(self, c, p, phone, out):
        config = p.file_bytes(c.PKG, "files/p34-experiment.json", 8192)
        backend.require_owned_config(config, self.known_configs(c))
        backend.checked_phone_path(c, p, "files/p34-experiment.json")
        directory = "files/p34-retired-configs"
        backend.checked_phone_path(c, p, directory, new_leaf=not phone.exists(p, c.PKG, directory))
        archive = directory + "/" + hashlib.sha256(config).hexdigest() + ".json"
        cli.require(not phone.exists(p, c.PKG, archive), "old configuration already archived; do not replay")
        return super().retire_initial(c, p, phone, out)

    def finish_install_snapshot(self, c, p, phone, out, pid, remote, expected):
        try:
            result = super().finish_install_snapshot(c, p, phone, out, pid, remote, expected)
            _, messages = c.envelope.verify((out / "finished/snapshot.jsonl").read_bytes(),
                sentinel=c.apk["metadata"]["device_observation"]["sentinel"], target=c.TARGET)
            validate_radio_markers(messages, expected)
            c.save(out / "radio-policy.json", dict(result="RADIO_POLICY_OBSERVED", config=cli.record(out / "runtime-config.json"),
                pauseScanDuringOta=expected["pauseScanDuringOta"], androidHighPriority=expected["androidHighPriority"],
                negotiated_interval="UNKNOWN", no_cleanup_error=True))
            return result
        finally:
            c.raw(out / "logcat-full.log", p.command(["logcat", "-d", "-v", "threadtime", "--pid=" + str(pid)], timeout=45, binary=True))


def validate_radio_markers(messages, expected):
    lines = messages.splitlines()
    for key, marker in (("pauseScanDuringOta", "OTA_RADIO scan=paused"),
                        ("androidHighPriority", "OTA_RADIO priority=request-accepted negotiated=unknown")):
        cli.require(lines.count(marker) == int(expected[key]), "requested radio policy lacks unique original acknowledgement")
    cli.require(not any(x.startswith("OTA_RADIO cleanup=unresolved") for x in lines), "radio cleanup unresolved")


def tests(s):
    path = HOST_TESTS / "result.json"
    value = s.read(path)
    cli.require(value["result"] == "PASS" and value["source"] == cli.record(__file__) and value["test"] == cli.record(TEST),
                "current source-bound radio host tests required")
    return cli.record(path)


def verify_pre_cell_failure(s):
    failed = AREA / "trials/baseline"
    result = s.read(failed / "network-result.json")
    cli.require(result["result"] == "NETWORK_INCOMPLETE" and result["device_operations"] == 0 and
                result["detail"] == "full asset filename does not match the App contract/download path",
                "only the diagnosed pre-cell filename failure may resume")
    cli.require(not (failed / "cells").exists() and not (failed / "live-network.json").exists() and
                not (failed / "runtime/s04").exists(), "device cell may have started; reconcile first")
    for name in ("network", "coordinator"):
        closed = s.read(failed / "runtime" / name / "closed.json")
        cli.require(closed["worker_exit"] == 1 and not closed["forced_termination"], "failed owner unresolved")
    network = s.read(failed / "network-owner/network/closed.json")
    cli.require(network["listener_closed"] and network["worker_stopped"], "failed service still active")
    phone = s.read(failed / "prestart-phone/result.json")
    usb = s.read(failed / "prestart-phone/usb/closed.json")
    cli.require(phone["stable_completed"] and phone["pid"] is None and phone["usb_closed"] and
                usb["port_closed"] and usb["stop_exit"] == usb["server_exit"] == usb["launcher_exit"] == 0 and
                usb["key_before"] == usb["key_after"], "preflight phone unresolved")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("check", "launch", "coordinator", "network", "cell"))
    parser.add_argument("--arm", choices=ORDER, default="baseline")
    args = parser.parse_args()
    s = cli.Store(ROOT)
    out = TRIALS / args.arm
    supervisor = cli.load_module("radio_trial_owner", ROOT / ".cache/p3-4-screening-20260922/supervisor.py")
    if args.mode not in ("check", "launch"):
        cli.require(supervisor.owned.in_job(), "finite detached owner required")
    if args.mode == "launch":
        cli.require(not out.exists(), "radio arm already reserved; reconcile original outcome")
        tests(s)
        verify_pre_cell_failure(s)
    api = Radio(s, args.arm)
    c = api.context(out)
    api.preflight(c, out)
    if args.mode == "check":
        config = api.phone(c, "radio_check").config(c, "s04", 921600, 28, "https://offline.trycloudflare.com")
        validate_config(config, api.assets)
        cli.require(api.installed_context(out).receiver_image_sha == api.assets["target"]["sha256"], "wrong target context")
        print(json.dumps(dict(result="RADIO_OFFLINE_BINDINGS_VERIFIED", arm=args.arm, config=config, sources=len(c.sources()))), flush=True)
        return
    if args.mode == "launch":
        s.write(out / "intent.json", dict(time=cli.now(), sources=c.sources(), tests=tests(s), arm=args.arm,
            scope="one legal FULL radio arm; user Start; no replay/reset/flash", independent_acceptance=False))
        print(supervisor.owned.launch(out / "runtime/coordinator", Path(__file__), ["coordinator", "--arm", args.arm], 6000), flush=True)
        return
    cli.require(c.sources() == s.read(out / "intent.json")["sources"], "running sources changed")
    os.environ.update(c.environment())
    if args.mode != "coordinator":
        api.validate(c, out)
        code = api.network_worker(c, out) if args.mode == "network" else api.cell_worker(c, out, "s04")
        cli.require(code == 0, "radio worker failed; preserve evidence")
        return
    result, network_started = dict(result="RADIO_ARM_INCOMPLETE"), False
    try:
        observed = api.inspect(c, out / "prestart-phone")
        api.prepare(c, out, observed, tests(s))
        supervisor.owned.launch(out / "runtime/network", Path(__file__), ["network", "--arm", args.arm], cli.NETWORK_SUPERVISOR_SECONDS)
        network_started = True
        def ready():
            cli.require(cli.owner_state(s, out / "runtime/network")["state"] != "CLOSED", "network closed before ready")
            return (out / "live-network.json").exists()
        cli.wait_until(ready, seconds=cli.NETWORK_READY_WAIT_SECONDS)
        api.network_ready(c, out)
        supervisor.owned.launch(out / "runtime/s04", Path(__file__), ["cell", "--arm", args.arm], cli.CELL_SECONDS)
        s.write(out / "coordinator-ready.json", dict(time=cli.now(), cell="s04", arm=args.arm))
        cli.wait_until(lambda: (out / "runtime/s04/closed.json").exists(), seconds=cli.CELL_SECONDS + 30)
        result.update(cell=s.read(out / "cells/s04/result.json"), owner=s.read(out / "runtime/s04/closed.json"))
        result["result"] = result["cell"]["result"]
    except Exception as error:
        result.update(error=type(error).__name__, detail=str(error))
    finally:
        if network_started:
            s.write(out / "network-stop.json", dict(time=cli.now(), reason="coordinator-closure"))
            cli.wait_until(lambda: (out / "runtime/network/closed.json").exists(), seconds=90)
            result["network_owner"] = s.read(out / "runtime/network/closed.json")
        s.write(out / "coordinator-result.json", dict(time=cli.now(), **result))
    cli.require("error" not in result, "radio arm needs reconciliation")


if __name__ == "__main__":
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                "explicit root and isolated Python required")
    main()
