"""Remaining prefer2m screen after reconciled observe OTA; never replay observe."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_phy_trial_resume as previous
import p34_phy_logfix_install as install

old = previous.original
cli, batch, ui = old.cli, old.batch, old.ui
backend = batch.radio.backend
AREA = install.AREA
OUT = AREA / "trials/prefer2m"
RECOVERY = AREA / "recovery-001"
HOST = AREA / "trial-tests-003"
TEST = ROOT / "tests/ota/test_p34_phy_logfix_trial.py"
ENVELOPE = AREA / "src/Tools/ota/p3-4-link-stats/observation_capture.py"
PROTECTED = "1791039287079074-d6f8dfe1a81f0a829517d60e"


def fixed_envelope():
    contract = cli.load_module("phy_logfix_contract", ENVELOPE)
    reader = batch.followup.fixed_envelope()
    cli.require(contract.PREFIXES == (*reader.PREFIXES, "OTA_PHY ", "OTA_PHY_CANCEL "),
                "unexpected PHY prefix contract")
    reader.PREFIXES = contract.PREFIXES
    return reader


def installed(s):
    report, proof = install.inputs(s)
    result = s.read(install.OUT / "result.json")
    closed = s.read(AREA / "runtime/install-001/closed.json")
    cli.require(result["result"] == "PHY_LOGFIX_SAME_SIGNER_INSTALLED" and result["usb_closed"] and
        result["original_invalid_capture_preserved"] and result["configuration_preserved"] and
        result["permissions_preserved"] and result["installed"]["sha256"] == report["apk"]["sha256"] and
        result["retained"] == proof["checkpoint"] and not result["app_launched"] and
        closed["worker_exit"] == 0 and not closed["forced_termination"], "repair installation unresolved")
    return report, proof


def recovery(s):
    report, proof = installed(s)
    value = s.read(RECOVERY / "result.json")
    closed = s.read(AREA / "runtime/recovery-001/closed.json")
    cli.require(value["result"] == "PHY_INVALID_CAPTURE_ARCHIVED" and value["usb_closed"] and
        value["app_stopped"] and value["no_delete"] and value["no_ota"] and
        value["raw_target"] == proof["checkpoint"] and closed["worker_exit"] == 0 and
        not closed["forced_termination"], "archive recovery unresolved")
    for item in [value["config"], value["protected"], *value["source_files"].values()]:
        cli.require(cli.record(s.checked(item["path"])) == item, "recovery bytes changed")
    return report, proof, value


def archive_worker(s):
    report, proof = installed(s)
    b, d, p, lock = install.runtime()
    protected = install.original.PRIOR / "cells/s04/finished/snapshot.jsonl"
    expected = protected.read_bytes()
    data = {p.name: p.read_bytes() for p in (install.OUT / "capture").iterdir()}
    cli.require(set(data) in ({"events.jsonl", "health.json"},
        {"events.jsonl", "health.json", "health.json.tmp"}), "unknown preserved failure files")
    install.validate_health(data["health.json"])
    config = (install.OUT / "runtime-config.json").read_bytes()
    destination = "files/p34-archived-observations/" + install.CAPTURE
    retired = "files/p34-retired-configs/" + hashlib.sha256(config).hexdigest() + ".json"
    def checked(path, new=False):
        return backend.checked_phone_path(install, p, path, new_leaf=new)
    def listing(path):
        return p.command(["exec-out", "run-as", install.PKG, "ls", "-1", path]).splitlines()
    def exists(path):
        return p.command(["exec-out", "run-as", install.PKG, "ls", "-d", path], check=False).strip() == path
    def read(path):
        return p.file_bytes(install.PKG, path, 16785408)
    value = dict(result="PHY_ARCHIVE_INCOMPLETE", no_delete=True, no_ota=True)
    try:
        with lock.device_lock(), d["usb"](b, p, RECOVERY):
            p.phone_identity()
            cli.require(d["installed"](b, p, report["apk"]["sha256"]) is not None, "repair APK differs")
            cli.require(not p.command(["shell", "pidof", install.PKG], check=False).strip(), "App must remain stopped")
            names = listing("files/p34-observations")
            cli.require(len(names) == len(set(names)) == 8 and all(backend.CAPTURE_NAME.fullmatch(n) for n in names)
                and sorted(names)[-1] == install.CAPTURE and PROTECTED in names, "capture inventory changed")
            protected_remote = "files/p34-observations/" + PROTECTED + "/snapshot-1.jsonl"
            cli.require(read(protected_remote) == expected and read("files/p34-experiment.json") == config and
                set(listing(install.REMOTE)) == set(data), "protected data or failure inventory changed")
            for name, raw in data.items():
                checked(install.REMOTE + "/" + name)
                cli.require(read(install.REMOTE + "/" + name) == raw, "failure bytes changed")
            for path in (install.REMOTE, "files/p34-experiment.json", "files/p34-archived-observations",
                         "files/p34-retired-configs"):
                checked(path)
            checked(destination, True)
            checked(retired, True)
            cli.require(not exists(destination) and not exists(retired), "archive exists; reconcile instead")
            sources = {name: s.raw(RECOVERY / "capture" / name, raw) for name, raw in data.items()}
            copied = s.raw(RECOVERY / "runtime-config.json", config)
            cli.require(all(cli.record(i["path"]) == i for i in [copied, *sources.values()]), "backup changed")
            s.write(RECOVERY / "move-intent.json", dict(source=checked(install.REMOTE),
                destination=checked(destination, True), config_source=checked("files/p34-experiment.json"),
                config_destination=checked(retired, True), source_files=sources, config=copied))
            p.command(["exec-out", "run-as", install.PKG, "mv", "-n", install.REMOTE, destination])
            cli.require(not exists(install.REMOTE) and set(listing(destination)) == set(data) and
                all(read(destination + "/" + n) == raw for n, raw in data.items()), "capture move unresolved")
            p.command(["exec-out", "run-as", install.PKG, "mv", "-n", "files/p34-experiment.json", retired])
            cli.require(not exists("files/p34-experiment.json") and read(retired) == config, "config move unresolved")
            remaining = listing("files/p34-observations")
            cli.require(set(remaining) == set(names) - {install.CAPTURE} and read(protected_remote) == expected and
                not p.command(["shell", "pidof", install.PKG], check=False).strip(), "protected state changed")
            value.update(result="PHY_INVALID_CAPTURE_ARCHIVED", source_files=sources, config=copied,
                raw_target=proof["checkpoint"], protected=cli.record(protected), protected_capture=PROTECTED,
                remaining=remaining, app_stopped=True, original_capture_invalid=True,
                destination=destination, retired_config=retired, performance="UNAVAILABLE")
        value["usb_closed"] = True
    except Exception as error:
        value.update(error=type(error).__name__, detail=str(error))
    s.write(RECOVERY / "result.json", dict(time=cli.now(), **value))
    print(json.dumps(value), flush=True)
    cli.require("error" not in value, "preserve archive outcome; no blind move retry")


class Trial(old.Trial):
    def __init__(self, s, arm="prefer2m", checking=False):
        cli.require(arm == "prefer2m", "observe already installed; no replay")
        self.probe_arm, self.ui_arm, self.arm = "reuse", "measure", "batch"
        self.preinstall, self.new_preinstall, self.new_arm, self.half_arm = True, True, "measure", "measure"
        # Historical archive/install receipts are not this successor's admission.
        self.phy_arm, self.phy_checking = arm, True
        self.assets = old.assets(s, arm)
        self.report, proof = install.inputs(s) if checking else installed(s)
        self.proof = dict(report=proof, plan=s.read(install.failed.TRIAL / "plan.json"),
            descriptor=dict(kind="RAW_CONFIRMED_CAPTURE_INVALID", report=cli.record(install.readback.OUT / "result.json"),
                run=str(install.failed.TRIAL), performance="UNAVAILABLE", no_replay=True),
            inputs=[cli.record(install.readback.OUT / "result.json"), proof["checkpoint"]])
        cli.require(self.assets["receiver"]["sha256"] == install.IMAGE, "candidate does not start at retained target")
        path = Path(self.proof["plan"]["profile"]["path"])
        backend.Backend.__init__(self, s, path, s.read(path), cli.RECONNECT_GROUP)
        spec = self.assets["specification"]
        self.receiver_version, self.target_version = spec["receiver"], spec["target_version"]
        self.served_name, self.checking = spec["served_name"], checking

    def context(self, out):
        c = super().context(out)
        c.envelope = fixed_envelope()
        c.envelope.ROOT, c.envelope.checked = ROOT, c.checked
        c.p.query.m = c.envelope
        before = c.sources
        extra = sources() + [cli.record(HOST / "result.json"), cli.record(AREA / "apk-g1/apk.json")]
        if not self.checking:
            extra += [cli.record(p) for p in (install.OUT / "result.json", RECOVERY / "result.json",
                AREA / "runtime/install-001/closed.json", AREA / "runtime/recovery-001/closed.json")]
        c.sources = lambda: sorted({i["path"]: i for i in [*before(), *extra]}.values(), key=lambda i: i["path"])
        return c

    def known_configs(self, c):
        return set()

    def retire_initial(self, c, p, phone, out):
        recovery(self.store)
        cli.require(not phone.exists(p, c.PKG, "files/p34-experiment.json") and
            not p.command(["shell", "pidof", c.PKG], check=False).strip(), "recovered App must remain stopped/unconfigured")

    def prepare(self, c, out, phone, tests):
        _, _, restored = recovery(self.store)
        cli.require(phone["result"] == "APP_INSPECTED" and phone["pid"] is None and phone["config"] is None and
            phone["usb_closed"] and phone["stable_completed"] and phone["health"]["captureId"] == PROTECTED and
            phone["capture_directories"] == len(restored["remaining"]) < 8 and
            phone["snapshot_records"]["snapshot-1.jsonl"]["sha256"] == restored["protected"]["sha256"],
            "protected prestart state differs after failed-capture archive")
        c.save(out / "root-before.json", c.root_state())
        c.save(out / "plan.json", dict(time=c.now(), root=str(ROOT), profile=cli.record(self.profile_path),
            sources=c.sources(), bindings=c.bindings, cells=cli.cells_for(self.group), native_authority=c.native_authority(),
            tests=tests, prestart=cli.record(out / "prestart-phone/result.json"), prefix_bytes=0, group=self.group,
            served=c.screen, served_name=self.served_name, receiver_version=self.receiver_version, target_version=self.target_version,
            no_end=False, no_mcu_reset=True, no_firmware_install=False, independent_acceptance=False,
            reconciled_terminal=None, predecessor=self.proof["descriptor"], target_bindings=self.installed_context(out).bindings,
            package_kind=c.package_kind, recorder_recovery=cli.record(RECOVERY / "result.json")))

    def observe_install(self, c, p, phone, out, pid, expected, **kwargs):
        try:
            return super().observe_install(c, p, phone, out, pid, expected, **kwargs)
        finally:
            c.raw(out / "logcat-observer.log", p.command(["logcat", "-d", "-v", "threadtime", "--pid=" + str(pid)],
                timeout=45, binary=True))


def sources():
    return [cli.record(p) for p in (Path(__file__), TEST, ENVELOPE, Path(install.__file__), Path(old.__file__),
        install.readback.OUT / "result.json", install.HOST / "result.json")]


def tests(s):
    old.tests(s)
    result = s.read(HOST / "result.json")
    cli.require(result["passed"] and result["sources"] == sources(), "current successor host tests required")
    return cli.record(HOST / "result.json")


if __name__ == "__main__":
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                "isolated explicit root required")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("archive", "archive-worker", "check", "launch", "coordinator", "network", "cell"))
    parser.add_argument("--arm", choices=("prefer2m",), default="prefer2m")
    args = parser.parse_args()
    s = cli.Store(ROOT)
    tests(s)
    owner = cli.load_module("phy_logfix_trial_owner", ROOT / ".cache/p3-4-screening-20260922/supervisor.py")
    if args.mode == "archive":
        installed(s)
        cli.require(not RECOVERY.exists(), "preserve original recovery")
        for name in ("intent.json", "result.json", "move-intent.json", "capture", "runtime-config.json", "host", "usb"):
            s.checked(RECOVERY / name)
        s.write(RECOVERY / "intent.json", dict(time=cli.now(), sources=sources(), no_delete=True, no_ota=True))
        print(owner.owned.launch(s.checked(AREA / "runtime/recovery-001"), Path(__file__), ["archive-worker"], 600))
    elif args.mode == "archive-worker":
        cli.require(owner.owned.in_job() and s.read(RECOVERY / "intent.json")["sources"] == sources(), "source-pinned archive owner required")
        archive_worker(s)
    else:
        if args.mode not in ("check", "launch"):
            cli.require(owner.owned.in_job(), "finite trial owner required")
        if args.mode == "launch":
            recovery(s)
            cli.require(not OUT.exists(), "preserve candidate trial")
        api = Trial(s, checking=args.mode == "check")
        c = api.context(OUT)
        api.preflight(c, OUT)
        if args.mode == "check":
            config = api.phone(c, "phy_logfix_offline").config(c, "s04", 921600, 28, "https://offline.trycloudflare.com")
            old.validate(config, api.assets)
            cli.require(api.installed_context(OUT).receiver_image_sha == api.assets["target"]["sha256"], "target binding differs")
            print("PHY_LOGFIX_OFFLINE_VERIFIED", len(c.sources()), flush=True)
        elif args.mode == "launch":
            s.write(OUT / "intent.json", dict(time=cli.now(), sources=c.sources(), tests=tests(s), arm=args.arm,
                scope="remaining prefer2m cell only; no observe replay/reset/Boot replacement", independent_acceptance=False))
            print(owner.owned.launch(s.checked(OUT / "runtime/coordinator"), Path(__file__), ["coordinator"], 6000))
        else:
            cli.require(c.sources() == s.read(OUT / "intent.json")["sources"], "running trial sources changed")
            os.environ.update(c.environment())
            if args.mode == "coordinator":
                batch.clone(ui.coordinate, __file__=__file__, tests=tests)(s, api, c, owner, OUT, args.arm)
            else:
                api.validate(c, OUT)
                code = api.network_worker(c, OUT) if args.mode == "network" else api.cell_worker(c, OUT, "s04")
                cli.require(code == 0, "trial incomplete; reconcile original outcome")
