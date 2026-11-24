"""Remaining radio arms from raw-confirmed30247, preserving the invalid scan verdict."""
import json
from pathlib import Path
import runpy
import sys
import types

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_radio_trial as radio
import p34_radio_recorder_recovery as recovery
import p34_radio_recorder_artifacts as artifacts
import p34_capture_capacity as capacity

cli = radio.cli
AREA = recovery.AREA
TRIALS = AREA / "trials-v3"
VERIFIED_PRIORITY = AREA / "trials-v2"
HOST_TESTS = AREA / "host-tests-003"
CAPACITY_RECOVERY = ROOT / ".cache/p34-runtime-doctor/combined-recovery-001/result.json"
TEST = ROOT / "tests/ota/test_p34_radio_followup.py"
ENVELOPE = radio.AREA / "src/Tools/ota/p3-4-link-stats/observation_capture.py"


def fixed_envelope():
    contract = cli.load_module("recorder_prefix_contract", ENVELOPE)
    reader = cli.load_module("recorder_fixed_envelope", ROOT / "Tools/ota/p34_observation.py")
    cli.require(contract.PREFIXES == (*reader.PREFIXES, "OTA_RADIO "), "unexpected parser contract change")
    # Keep the runtime reader's identity/query helpers; extend only the tested prefix contract.
    reader.PREFIXES = contract.PREFIXES
    return reader


def recovered(s):
    path = recovery.OUT / "result.json"
    value = s.read(path)
    cli.require(value["result"] == "INVALID_CAPTURE_ARCHIVED_TARGET_RETAINED" and value["no_delete"] and
                value["original_capture_invalid"] and value["performance"] == "UNAVAILABLE" and
                value["usb_closed"] and value["app_stopped"], "invalid capture recovery unresolved")
    for item in [*value["source_files"].values(), value["config"], value["raw_target"]]:
        cli.require(cli.record(s.checked(item["path"])) == item, "recovery evidence changed")
    owner = s.read(radio.AREA / "runtime/recorder-recovery-001/closed.json")
    cli.require(owner["worker_exit"] == 0 and not owner["forced_termination"], "recovery owner unresolved")
    return value


def startup_recovered(s):
    recovered(s)
    path = AREA / "startup-recovery-002/result.json"
    value = s.read(path)
    cli.require(value["result"] == "PRESTART_QUERY_ARCHIVED_NO_TRANSFER" and value["zero_upgrade_starts"] and
                value["app_stopped"] and value["usb_closed"] and value["no_delete"], "startup failure not reconciled")
    for item in [*value["files"].values(), value["config"], value["original_failure"]]:
        cli.require(cli.record(s.checked(item["path"])) == item, "startup evidence changed")
    owner = s.read(radio.AREA / "runtime/startup-recovery-002/closed.json")
    cli.require(owner["worker_exit"] == 0 and not owner["forced_termination"], "startup recovery owner unresolved")
    return value


def capacity_recovered(s):
    startup_recovered(s)
    value = s.read(CAPACITY_RECOVERY)
    cli.require(value["result"] == "PRESTART_CAPACITY_RECOVERED" and value["usb_closed"] and
                value["app_stopped"] and value["no_ota"] and value["no_delete"], "capacity recovery unresolved")
    for item in (value["capacity"], value["config"], value["diagnosis"]):
        cli.require(cli.record(s.checked(item["path"])) == item, "capacity evidence changed")
    owner = s.read(CAPACITY_RECOVERY.parent / "runtime/closed.json")
    cli.require(owner["worker_exit"] == 0 and not owner["forced_termination"], "capacity recovery owner unresolved")
    return s.read(value["capacity"]["path"])


def apk(s):
    report = s.read(AREA / "apk-g1/apk.json")
    signing = runpy.run_path(str(ROOT / "Tools/ota/p34_signing_artifacts.py"))
    cli.require(report["sha"] == artifacts.SHA and report["certificate_sha256"] == signing["CERT"] and
                report["metadata"]["application_id"] == recovery.install.previous.PKG and
                cli.record(report["apk"]["path"]) == report["apk"] and
                signing["apk_certificate"](Path(report["apk"]["path"]).read_bytes()) == signing["CERT"], "APK drift")
    hosts = set()
    for record in report["host_reports"]:
        cli.require(cli.record(record["path"]) == record, "CI evidence changed")
        host = s.read(record["path"])
        cli.require(host["development_result"] == "PASS" and host["scope"] == "all" and
                    host["source_before"]["head"] == artifacts.SHA and host["source_before"]["clean"], "both-host exact CI required")
        hosts.add(json.dumps(host["host"], sort_keys=True))
    cli.require(len(hosts) == len(report["host_reports"]) == 2, "distinct CI hosts required")
    installed = s.read(recovery.install.OUT / "result.json")
    cli.require(installed["result"] == "FIXED_SIGNER_RECORDER_UPDATE_VERIFIED" and installed["usb_closed"] and
                installed["installed"]["sha256"] == report["apk"]["sha256"] and
                installed["original_invalid_capture_preserved"] and installed["configuration_preserved"], "installed repair differs")
    return report


def predecessor(s, arm, group):
    if arm == "combined":
        fn = radio.confirmed_predecessor
        return types.FunctionType(fn.__code__, dict(fn.__globals__, TRIALS=VERIFIED_PRIORITY), fn.__name__)(s, arm, group)
    cli.require(arm == "priority", "only the two remaining radio arms are admitted")
    archive = recovered(s)
    path = radio.AREA / "readback-scan-001/result.json"
    proof = s.read(path)
    cli.require(proof["result"] == "TARGET_30247_RAW_CONFIRMED_CAPTURE_INVALID" and
                proof["checkpoint"] == archive["raw_target"] and proof["performance"] == "UNAVAILABLE",
                "raw confirmation cannot be relabelled as a measured scan success")
    closure = s.read(proof["checkpoint"]["path"])
    cli.require(closure["reader_closed"] and closure["retained_verified"] and "cleanup_error" not in closure and
                all(closure[k] for k in ("no_reset", "no_halt", "no_flash", "no_nvic_write")), "native closure unresolved")
    records = [cli.record(path), proof["checkpoint"], cli.record(recovery.OUT / "result.json"), archive["config"],
               *archive["source_files"].values()]
    for phase in ("initial_identity", "final_identity"):
        for key, expected in (("app", group["receiver"]), ("boot", group["receiver_bindings"]["whole_boot"])):
            actual = closure[phase][key]
            cli.require((actual["bytes"], actual["sha256"]) == (expected["bytes"], expected["sha256"]), "raw predecessor differs")
            records.append(actual)
    state = closure["final_state"]
    cli.require(state["bcb_state"] == 4 and all(state[k] == 1 for k in ("confirm_done", "state_snapped", "sd_ready")),
                "ordinary confirmation missing")
    old = radio.TRIALS / "scan"
    for name in ("s04", "coordinator", "network"):
        owner = s.read(old / "runtime" / name / "closed.json")
        cli.require(not owner["forced_termination"], "scan owner unresolved")
        records.append(cli.record(old / "runtime" / name / "closed.json"))
    failed = s.read(old / "cells/s04/result.json")
    cli.require(failed["result"] == "FULL_INSTALL_INCOMPLETE" and
                failed["error"] == "RuntimeError: installation capture is unhealthy or replayed", "different failed scan")
    records += [cli.record(old / "cells/s04/result.json"), cli.record(old / "plan.json")]
    for item in records:
        cli.require(cli.record(s.checked(item["path"])) == item, "original evidence drift")
    return dict(report=proof, plan=s.read(old / "plan.json"), inputs=records,
        descriptor=dict(kind="RAW_CONFIRMED_CAPTURE_INVALID", report=cli.record(path), run=str(old),
                        performance="UNAVAILABLE", no_replay=True))


class Followup(radio.Radio):
    def __init__(self, s, arm):
        cli.require(arm in ("priority", "combined"), "do not replay baseline or scan")
        self.arm, self.assets = arm, radio.assets(s, arm)
        self.proof = predecessor(s, arm, self.assets)
        self.report = apk(s)
        path = Path(self.proof["plan"]["profile"]["path"])
        radio.backend.Backend.__init__(self, s, path, s.read(path), cli.RECONNECT_GROUP)
        spec = self.assets["specification"]
        self.receiver_version, self.target_version = spec["receiver"], spec["target_version"]
        self.served_name = spec["served_name"]

    def context(self, out):
        c = super().context(out)
        c.envelope = fixed_envelope()
        cli.require("OTA_RADIO " in c.envelope.PREFIXES, "new producer prefix not supported")
        original = c.sources
        records = [cli.record(p) for p in (__file__, TEST, ENVELOPE, recovery.__file__, artifacts.__file__,
            recovery.OUT / "result.json", recovery.install.OUT / "result.json", AREA / "apk-g1/apk.json",
            AREA / "startup-recovery-002/result.json", ROOT / "Tools/ota/p34_radio_startup_recovery.py",
            CAPACITY_RECOVERY, capacity.__file__, ROOT / "Tools/ota/p34_runtime_doctor.py")]
        c.sources = lambda: sorted({x["path"]:x for x in [*original(), *records]}.values(), key=lambda x:x["path"])
        return c

    def known_configs(self, c):
        return set() if self.arm == "priority" else super().known_configs(c)

    def phone(self, c, name, *, producer=False):
        phone = super().phone(c, name, producer=producer)
        original = phone.provision
        def guarded(c, p, out, value):
            capacity.ensure_capacity(self.store, p, out / "capacity", package=c.PKG,
                sentinel=c.apk["metadata"]["device_observation"]["sentinel"], target=c.TARGET,
                known_configs=self.known_configs(c))
            return original(c, p, out, value)
        phone.provision = guarded
        return phone

    def retire_initial(self, c, p, phone, out):
        if self.arm == "combined" and not phone.exists(p, c.PKG, "files/p34-experiment.json"):
            capacity_recovered(self.store)
            cli.require(not p.command(["shell", "pidof", c.PKG], check=False).strip(), "recovered App unexpectedly running")
            return
        if self.arm != "priority":
            return super().retire_initial(c, p, phone, out)
        recovered(self.store)
        cli.require(not phone.exists(p, c.PKG, "files/p34-experiment.json") and
                    not p.command(["shell", "pidof", c.PKG], check=False).strip(), "recovered App must remain stopped/unconfigured")

    def prepare(self, c, out, phone, tests):
        recovered_combined = self.arm == "combined" and phone.get("config") is None
        if self.arm != "priority" and not recovered_combined:
            return super().prepare(c, out, phone, tests)
        archive = capacity_recovered(self.store) if recovered_combined else recovered(self.store)
        expected_count = archive["count"] if recovered_combined else len(archive["remaining"])
        expected_capture = self.proof["report"]["summary"]["captureId"] if recovered_combined else recovery.PROTECTED
        expected_sha = self.proof["report"]["summary"]["rawSha256"] if recovered_combined else "b36de84896286524ca671707662676ef46a10aab979228f6746d37234260b5a1"
        cli.require(phone["result"] == "APP_INSPECTED" and phone["pid"] is None and phone["config"] is None and
                    phone["usb_closed"] and phone["capture_directories"] == expected_count < 8 and
                    phone["health"]["captureId"] == expected_capture and phone["stable_completed"],
                    "unexpected phone state after exact invalid-capture archival")
        snapshot = phone["snapshot_records"]["snapshot-1.jsonl"]
        cli.require(snapshot["sha256"] == expected_sha,
                    "protected baseline snapshot changed")
        c.save(out / "root-before.json", c.root_state())
        c.save(out / "plan.json", dict(time=c.now(), root=str(self.root), profile=cli.record(self.profile_path),
            sources=c.sources(), bindings=c.bindings, cells=cli.cells_for(self.group), native_authority=c.native_authority(),
            tests=tests, prestart=cli.record(out / "prestart-phone/result.json"), prefix_bytes=0, group=self.group,
            served=c.screen, served_name=self.served_name, receiver_version=self.receiver_version, target_version=self.target_version,
            no_end=False, no_mcu_reset=True, no_firmware_install=False, independent_acceptance=False,
            reconciled_terminal=None, predecessor=self.proof["descriptor"], target_bindings=self.installed_context(out).bindings,
            package_kind=c.package_kind, recorder_recovery=cli.record(recovery.OUT / "result.json")))

    def observe_install(self, c, p, phone, out, pid, expected, **kwargs):
        try:
            return super().observe_install(c, p, phone, out, pid, expected, **kwargs)
        finally:
            # Retain the Android ring even if the health guard aborts observation.
            c.raw(out / "logcat-observer.log", p.command(["logcat", "-d", "-v", "threadtime", "--pid=" + str(pid)],
                                                        timeout=45, binary=True))


def tests(s):
    path = HOST_TESTS / "result.json"
    value = s.read(path)
    cli.require(value["result"] == "PASS" and value["source"] == cli.record(__file__) and
                value["test"] == cli.record(TEST) and value["envelope"] == cli.record(ENVELOPE), "source-bound followup tests required")
    return cli.record(path)


if __name__ == "__main__":
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                "explicit root and isolated Python required")
    entry = radio.main
    types.FunctionType(entry.__code__, dict(entry.__globals__, __file__=__file__, Radio=Followup,
        TRIALS=TRIALS, ORDER=("combined",), tests=tests, verify_pre_cell_failure=capacity_recovered), entry.__name__)()
