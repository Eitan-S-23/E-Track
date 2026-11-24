"""One legal successor after reconciled App timeout; never relabel the failed run."""
import argparse
import copy
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_session as cli
import p34_session_backend as backend
import p34_reconnect_assets as previous
import p34_reconnect_timeout as timeout
import p34_install_cost as host

AREA = ROOT / ".cache/p34-connect-fix/followup"
ASSETS = AREA / "assets/result.json"
TRIAL = AREA / "trial-001"
APK_REPORT = ROOT / ".cache/p34-connect-fix/apk-g1/apk.json"
APK_SHA = "5fd96270b90f64c706ce8eaeba4b88a3c3df1b1ea90763369e118adb9f23a366"
COMMIT = "e29c1392db7a1e0570b588f4d2f2c8d0d9c9c3ad"
CERT = "9e9b89c5e7fdc802b1fe71806a988a866db49cd988a739caeee56cb69f3df579"
RAW_SHA = "fef244ea0eb85a85b89c6bbcdc8955673c2cf26ad2dc979deec63a4a11bc45ed"
BOOT_SHA = "a63346db0dc673dc42adf6064892c466af5c4571df53cb55fe5b6ea154c1fdf4"
SNAPSHOT_SHA = "64484a292a810cd27db24e4709c0157a0bdf4d356f155e572e3f739de90a666d"
READBACK = timeout.AREA / "readback-recovery/readback-001/result.json"
SPEC = dict(receiver=30243, target_version=30244, version_name="3.2.44-p34r",
    served_name="p34-reconnect-fixed-full.etu", release_key="p34-reconnect-fixed", kind="full")
TEST = ROOT / "tests/ota/test_p34_reconnect_followup.py"


def closed(s, path):
    value = s.read(path / "closed.json")
    cli.require(value.get("worker_exit") == 0 and value.get("forced_termination") is False,
                "owned worker did not close normally: " + str(path))
    return cli.record(path / "closed.json")


def validate_reconciliation(summary, transfer, closure, query, identities):
    cli.require(summary["outcome"] == "not-completed" and
                summary["input"]["currentVersionCode"] == 30242 and
                summary["input"]["targetVersionCode"] == 30243 and
                summary["input"]["targetImageSha256"] == RAW_SHA,
                "original failed App outcome/target changed")
    cli.require(transfer["outcome"] == "ok" and transfer["elapsedUs"] > 0 and
                transfer["durable"]["finalOff"] == summary["input"]["packageBytes"],
                "durable END success required")
    cli.require(all(closure.get(k) is True for k in
                ("retained_verified", "reader_closed", "no_reset", "no_halt", "no_flash", "no_nvic_write")) and
                "cleanup_error" not in closure, "raw checkpoint unresolved")
    for phase in ("initial_identity", "final_identity"):
        for key, sha, size in (("app", RAW_SHA, 616540), ("boot", BOOT_SHA, 65536)):
            item = closure[phase][key]
            cli.require(item["sha256"] == sha and item["bytes"] == size, "raw App/Boot identity mismatch")
    state = closure["final_state"]
    cli.require(state["bcb_state"] == 4 and state["confirm_done"] == 1 and
                state["state_snapped"] == 1 and state["sd_ready"] == 1, "normal confirmation required")
    cli.require(query["successfulQueries"] >= 1 and query["pid"] == 17018 and
                query["captureId"] == "1790886478814858-966a83c7a649c78702af5243",
                "exact new-APK query evidence required")
    expected = ("addr=02:00:00:00:00:01 result=ok wire=E-Track model=e-track-at32f435 "
        "vcode=30243 hw=1 layout=1 boot=1 proto=1 window=32 sha=" + RAW_SHA)
    cli.require(expected in identities, "App-origin full receiver identity missing")


def apk(s):
    value = s.read(APK_REPORT)
    cli.require(value["sha"] == COMMIT and value["run"] == 36918990724 and
                value["apk"]["sha256"] == APK_SHA and cli.record(value["apk"]["path"]) == value["apk"] and
                value["certificate_sha256"] == CERT and not value["independent_acceptance"] and
                value["metadata"]["application_id"] == timeout.PKG, "fixed APK provenance changed")
    hosts = set()
    for item in value["host_reports"]:
        cli.require(cli.record(item["path"]) == item, "original CI evidence changed")
        report = s.read(item["path"])
        cli.require(report["development_result"] == "PASS" and report["scope"] == "all" and
                    report["source_before"]["head"] == COMMIT and report["source_before"]["clean"],
                    "both exact host checks required")
        hosts.add(json.dumps(report["host"], sort_keys=True))
    cli.require(len(value["host_reports"]) == len(hosts) == 2, "two distinct host checks required")
    return value


def reconciled(s):
    out, plan, summary, messages = timeout.originals(s)
    snapshot = cli.record(out / "cells/s04/finished/snapshot.jsonl")
    cli.require(snapshot["sha256"] == SNAPSHOT_SHA and
                s.read(out / "cells/s04/result.json")["result"] == "FULL_INSTALL_INCOMPLETE",
                "do not relabel the original failed run")
    rows = [json.loads(line.removeprefix("OTA_LINK_STATS ")) for line in messages.splitlines()
            if line.startswith("OTA_LINK_STATS ")]
    upgrades = [row for row in rows if row["label"] == "upgrade"]
    cli.require(len(upgrades) == 1, "one original transfer required")
    result = s.read(READBACK)
    cli.require(result["result"] == "TARGET_30243_RAW_CONFIRMED_APP_RECONNECT_FAILED" and
                result["original_failure_preserved"] and cli.record(result["checkpoint"]["path"]) == result["checkpoint"],
                "confirmed target reconciliation missing")
    closure = s.read(result["checkpoint"]["path"])
    old_api = cli.backend(s, Path(plan["profile"]["path"]), cli.RECONNECT_GROUP)
    old_api.verify_install_checkpoint(old_api.installed_context(AREA), Path(result["checkpoint"]["path"]))
    qdir = ROOT / ".cache/p34-connect-fix/query-001"
    installed = s.read(ROOT / ".cache/p34-connect-fix/install-002/result.json")
    cli.require(installed["result"] == "FIXED_SIGNER_IN_PLACE_UPDATE_VERIFIED" and
                installed["installed"]["sha256"] == APK_SHA and installed["usb_closed"] and
                installed["original_snapshot_preserved"] and installed["configuration_preserved"],
                "verified in-place installation missing")
    qresult = s.read(qdir / "result.json")
    cli.require(qresult["result"] == "NEW_APK_QUERY_SUCCEEDED" and qresult["usb_closed"] and
                qresult["post_ota_cold_reconnect_acceptance"] is False and
                cli.record(qresult["logcat"]["path"]) == qresult["logcat"], "query retrieval unresolved")
    report = apk(s)
    query_module = old_api.installed_context(AREA).p.query
    query_module.m = cli.load_module("followup_query_envelope", ROOT / "Tools/ota/p34_observation.py")
    query, _, _ = query_module.validate((qdir / "events.jsonl").read_bytes(),
        (qdir / "health-before.json").read_bytes(), (qdir / "health-after.json").read_bytes(),
        pid=17018, sentinel=report["metadata"]["device_observation"]["sentinel"], target="02:00:00:00:00:01")
    cli.require(query == qresult["query"], "query result differs from original App bytes")
    identities = [line.split("OTA_OBS identity ", 1)[1] for line in
                  Path(qresult["logcat"]["path"]).read_text(encoding="utf-8").splitlines()
                  if "OTA_OBS identity " in line and "result=ok" in line]
    validate_reconciliation(summary, upgrades[0]["transfer"], closure, query, identities)
    files = [out / "plan.json", out / "cells/s04/result.json", Path(snapshot["path"]), READBACK,
             Path(result["checkpoint"]["path"]), APK_REPORT, qdir / "result.json", qdir / "events.jsonl",
             qdir / "health-before.json", qdir / "health-after.json", Path(qresult["logcat"]["path"]),
             ROOT / ".cache/p34-connect-fix/install-002/result.json"]
    owners = [closed(s, ROOT / ".cache/p34-connect-fix/runtime" / name)
              for name in ("query-001", "install-retry-001")]
    return dict(result="FAILED_APP_TARGET_RECONCILED_FOR_SUCCESSOR", original_app_outcome="not-completed",
        post_ota_reconnect_verified=False, current_version=30243, current_image_sha256=RAW_SHA,
        plan=plan, inputs=[cli.record(p) for p in files] + owners)


def prepare_assets(s):
    cli.require(not ASSETS.parent.exists() and not os.environ.get("OTA_AES_KEY"), "preserve assets/no key override")
    proof = reconciled(s)
    old = previous.load()["groups"]["measure"]
    receiver, bindings = old["target"], old["target_bindings"]
    cli.require(bindings == proof["plan"]["target_bindings"] and receiver["sha256"] == RAW_SHA,
                "actual receiver differs from prepared lineage")
    env = host.environment(s, ASSETS.parent)
    os.environ.update(env)
    sys.path.insert(0, str(Path(sys.base_prefix) / "Lib/site-packages"))
    pack = cli.load_module("followup_pack", previous.erase.candidate.AREA / "f/Tools/etu_pack.py")
    unpack = cli.load_module("followup_unpack", previous.erase.candidate.AREA / "f/Tools/etu_unpack.py")
    package_tools = cli.load_module("followup_package_tools", ROOT / "Tools/ota/prepare_baud_assets.py")
    decoder = s.read(ROOT / ".cache/p34-next/n03/assets/result.json")["decoder"]
    previous.historical.resolve(decoder)
    raw = bytearray(Path(receiver["path"]).read_bytes())
    raw[0x400:0x460] = pack.build_fw_header(bytes(raw), SPEC["version_name"], 1786320000)
    target = s.raw(ASSETS.parent / "target.bin", bytes(raw))
    identity = previous.shared.identity(bytes(raw), unpack)
    blob = previous.shared.wrap_payload(pack, pack.lzma_alone_encode(bytes(raw)),
        Path(receiver["path"]).read_bytes(), bytes(raw), kind="full")
    package = s.raw(ASSETS.parent / "target.etu", blob)
    def native(label, item, expected):
        return json.loads(host.command(s, ASSETS.parent, label,
            [decoder["path"], item["path"], receiver["path"], target["path"], expected], env, 180))
    positive = native("positive", package, "ok")
    negatives, outputs = [], [target, package]
    for label, broken, expected in package_tools.negatives(blob, SPEC["receiver"]):
        item = s.raw(ASSETS.parent / (label + ".etu"), broken)
        negatives.append(dict(name=label, native=native(label, item, expected), package=item))
        outputs.append(item)
    target_bindings = copy.deepcopy(bindings)
    target_bindings["profile"].update(image=target, identity=identity, prefix=bytes(raw[:0x460]).hex())
    group = dict(specification=SPEC, receiver=receiver, receiver_bindings=bindings, target=target,
        target_identity=identity, target_bindings=target_bindings, package=package, package_kind="full",
        decoded=positive, negatives=negatives, header=package_tools.package_info(blob, 30243, 30244))
    outputs += [cli.record(p) for p in ASSETS.parent.glob("*.log")]
    s.write(ASSETS, dict(result="FIXED_RECONNECT_SUCCESSOR_ASSETS_VERIFIED", hardware=False,
        group=group, reconciliation={k:v for k,v in proof.items() if k != "plan"},
        inputs=proof["inputs"] + [decoder, cli.record(ROOT / previous.RELATIVE),
            *[cli.record(m.__file__) for m in (pack, unpack, package_tools, previous.shared)]], outputs=outputs))
    load_assets(s)
    print(json.dumps(dict(result="ASSETS_VERIFIED", package=package, identity=identity)), flush=True)


def validate_group(g):
    cli.require(g["specification"] == SPEC and g["receiver"]["sha256"] == RAW_SHA and
                g["target_identity"]["version_code"] == 30244 and g["package_kind"] == "full",
                "successor specification drift")
    x, y = (Path(g[key]["path"]).read_bytes() for key in ("receiver", "target"))
    cli.require(len(x) == len(y) and x[:0x400] + x[0x460:] == y[:0x400] + y[0x460:],
                "successor changed executable bytes")
    expected = copy.deepcopy(g["receiver_bindings"])
    expected["profile"].update(image=g["target"], identity=g["target_identity"], prefix=y[:0x460].hex())
    cli.require(g["target_bindings"] == expected and expected["whole_boot"]["sha256"] == BOOT_SHA,
                "runtime/Boot binding drift")
    cli.require(all(g["decoded"][k] for k in
        ("passed", "byte_identical", "boot_ok", "guards_ok", "workspace_lifecycle_ok")) and
        len(g["negatives"]) == 4 and all(n["native"]["passed"] and n["native"]["prepares"] == 0
        for n in g["negatives"]), "decoder proofs missing")


def load_assets(s):
    value = s.read(ASSETS)
    cli.require(value["result"] == "FIXED_RECONNECT_SUCCESSOR_ASSETS_VERIFIED" and value["hardware"] is False,
                "successor assets not verified")
    for item in value["inputs"] + value["outputs"]:
        previous.historical.resolve(item)
    validate_group(value["group"])
    return value["group"]


class Followup(backend.Backend):
    def __init__(self, s):
        proof = reconciled(s)
        path = Path(proof["plan"]["profile"]["path"])
        super().__init__(s, path, s.read(path), cli.RECONNECT_GROUP)
        self.proof, self.assets = proof, load_assets(s)
        self.receiver_version, self.target_version = 30243, 30244
        self.served_name = SPEC["served_name"]

    def context(self, out):
        c = super().context(out)
        c.previous_assets = c.full_assets
        c.n04_prior_assets.append(c.previous_assets)
        c.full_assets = self.assets
        c.spec = dict(c.spec, **SPEC)
        c.bindings = self.assets["receiver_bindings"]
        c.receiver_version, c.target_version = 30243, 30244
        c.served_name, c.release_key = SPEC["served_name"], SPEC["release_key"]
        c.served = c.screen = self.assets["package"]
        c.screen_bytes = Path(c.screen["path"]).read_bytes()
        c.target, c.target_identity = self.assets["target"], self.assets["target_identity"]
        c.apk = apk(self.store)
        c.APK_SHA = APK_SHA
        c.BOOT_SHA = BOOT_SHA
        c.flash_addresses = backend.bind_flash_gate(c.bindings["profile"],
            self.legacy["named"]["restored"]["clock"]["gate"]["symbol"])
        original = c.sources
        c.sources = lambda: sorted({r["path"]:r for r in [*original(), cli.record(__file__), cli.record(TEST),
            cli.record(ASSETS), cli.record(APK_REPORT), *self.proof["inputs"],
            c.apk["apk"], *c.apk["host_reports"]]}.values(), key=lambda r:r["path"])
        return c

    def predecessor(self, c):
        cli.require(c.bindings == self.assets["receiver_bindings"], "wrong reconciled receiver")
        return dict(descriptor=dict(kind="RAW_CONFIRMED_AFTER_APP_TIMEOUT",
            run=timeout.RUN, original_app_outcome="not-completed", assets=cli.record(ASSETS),
            inputs=self.proof["inputs"]), plan=self.proof["plan"])

    def completed_capture(self, c, observed, previous=None):
        # This entry permits only the subsequent query-only process, never an
        # invented successful verdict for the failed predecessor snapshot.
        cli.require(observed.get("safe_idle") is True, "followup requires idle query-only App")
        return None

    def known_configs(self, c):
        return {cli.record(ROOT / ".cache/p34-connect-fix/install-002/runtime-config.json")["sha256"]}

    def phone(self, c, name, *, producer=False):
        phone = super().phone(c, name, producer=producer)
        raw_phone = self.legacy["named"]["raw_load"](name + "_raw", c.HERE / "prefix_phone.py")
        def config(c, cell, baud, window, origin):
            value = dict(raw_phone.config(c, cell, baud, window, origin), schema=3,
                transferMode="full", prefixBytes=0, rebootInfoTimeoutMs=2000, rebootProbeIntervalMs=500)
            validate_config(value, self.assets)
            return value
        phone.config = config
        original_provision = phone.provision
        def provision(c, p, out, value):
            backend.checked_phone_path(c, p, "files/p34-experiment.json", new_leaf=True)
            return original_provision(c, p, out, value)
        phone.provision = provision
        return phone

    def retire_initial(self, c, p, phone, out):
        # Validate real destinations before the inherited archival operation.
        import hashlib
        config = p.file_bytes(c.PKG, "files/p34-experiment.json", 8192)
        backend.require_owned_config(config, self.known_configs(c))
        backend.checked_phone_path(c, p, "files/p34-experiment.json")
        archive_dir = "files/p34-retired-configs"
        if phone.exists(p, c.PKG, archive_dir):
            backend.checked_phone_path(c, p, archive_dir)
        else:
            backend.checked_phone_path(c, p, archive_dir, new_leaf=True)
        archive = archive_dir + "/" + hashlib.sha256(config).hexdigest() + ".json"
        if phone.exists(p, c.PKG, archive):
            raise RuntimeError("prior archive exists; do not replay retirement")
        return super().retire_initial(c, p, phone, out)

    def finish_install_snapshot(self, c, p, phone, out, pid, remote, expected):
        # Retrieve the full original Android ring even when the App verdict fails.
        try:
            return super().finish_install_snapshot(c, p, phone, out, pid, remote, expected)
        finally:
            c.raw(out / "logcat-full.log", p.command(
                ["logcat", "-d", "-v", "threadtime", "--pid=" + str(pid)], timeout=45, binary=True))


def validate_config(value, assets):
    fixed = dict(schema=3, runId="s04", requestedBaud=921600, senderWindowSegments=28,
        reuseGatt=True, withoutResponse=True, transferMode="full", prefixBytes=0,
        rebootInfoTimeoutMs=2000, rebootProbeIntervalMs=500, currentVersionCode=30243,
        targetVersionCode=30244, currentImageSha256=RAW_SHA, targetImageSha256=assets["target"]["sha256"],
        packageBytes=assets["package"]["bytes"], packageSha256=assets["package"]["sha256"])
    cli.require(all(type(value.get(k)) is type(v) and value[k] == v for k,v in fixed.items()),
                "followup changed a fixed axis or image/package identity")


def test_receipt(s):
    value = s.read(AREA / "tests/result.json")
    cli.require(value["result"] == "PASS" and value["source"] == cli.record(__file__) and
                value["test"] == cli.record(TEST), "current adapter self-tests required")
    return cli.record(AREA / "tests/result.json")


def owner(s, mode):
    supervisor = cli.load_module("followup_owner", ROOT / ".cache/p3-4-screening-20260922/supervisor.py")
    if mode == "launch":
        test_receipt(s)
        cli.require(not TRIAL.exists(), "trial already reserved; inspect original outcome")
        api = Followup(s)
        c = api.context(TRIAL)
        api.preflight(c, TRIAL)
        s.write(TRIAL / "intent.json", dict(time=cli.now(), sources=c.sources(), tests=test_receipt(s),
            scope="one30243-to30244 reconnect-fix screen; no automatic UI/OTA/replay",
            retained_boot=BOOT_SHA, independent_acceptance=False))
        print(supervisor.owned.launch(TRIAL / "runtime/coordinator", Path(__file__), ["coordinator"], 6000), flush=True)
        return
    cli.require(supervisor.owned.in_job(), "finite detached owner required")
    api = Followup(s)
    c = api.context(TRIAL)
    api.preflight(c, TRIAL)
    cli.require(c.sources() == s.read(TRIAL / "intent.json")["sources"], "running sources changed")
    os.environ.update(c.environment())
    if mode == "coordinator":
        result = dict(result="FOLLOWUP_INCOMPLETE")
        network_started = False
        try:
            phone = api.inspect(c, TRIAL / "prestart-phone")
            api.prepare(c, TRIAL, phone, test_receipt(s))
            supervisor.owned.launch(TRIAL / "runtime/network", Path(__file__), ["network"], cli.NETWORK_SUPERVISOR_SECONDS)
            network_started = True
            def ready():
                state = cli.owner_state(s, TRIAL / "runtime/network")
                cli.require(state["state"] != "CLOSED", "network closed before ready")
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
        cli.require("error" not in result, "followup requires reconciliation")
    else:
        api.validate(c, TRIAL)
        code = api.network_worker(c, TRIAL) if mode == "network" else api.cell_worker(c, TRIAL, "s04")
        cli.require(code == 0, "owned " + mode + " failed; inspect preserved evidence")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("mode", choices=("assets", "check", "launch", "coordinator", "network", "cell"))
    args = p.parse_args()
    s = cli.Store(ROOT)
    if args.mode == "assets":
        prepare_assets(s)
    elif args.mode == "check":
        api = Followup(s)
        c = api.context(TRIAL)
        phone = api.phone(c, "followup_offline")
        config = phone.config(c, "s04", 921600, 28, "https://offline.trycloudflare.com")
        validate_config(config, api.assets)
        cli.require(api.installed_context(TRIAL).receiver_image_sha == api.assets["target"]["sha256"],
                    "target context differs")
        print(json.dumps(dict(result="OFFLINE_BINDINGS_VERIFIED", config=config,
            sources=len(c.sources()), predecessor=api.predecessor(c)["descriptor"]["kind"])), flush=True)
    else:
        owner(s, args.mode)


if __name__ == "__main__":
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                "explicit root and isolated Python required")
    main()
