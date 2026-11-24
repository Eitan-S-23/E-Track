"""Same-APK header successor: screen 1s reboot INFO timeout, retain 500ms cadence."""
import argparse
import copy
import io
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_phy_logfix_trial as repaired
import p34_batch_review as review

phy = repaired.old
cli, batch, ui = phy.cli, phy.batch, phy.ui
AREA = ROOT / ".cache/p34-info-timeout"
ASSETS, OUT, HOST = AREA / "assets", AREA / "trial", AREA / "tests-001"
PRIOR = ROOT / ".cache/p34-phy-logfix/trials/prefer2m"
APK = ROOT / ".cache/p34-phy-logfix/apk-g1/apk.json"
TEST = ROOT / "tests/ota/test_p34_info_timeout.py"


def asset_preflight(s):
    names = ["target.bin", "p34-info-timeout-full.etu", "result.json", "host"]
    for label in ("positive", "payload-crc", "truncated", "same-version", "wrong-flags"):
        names += [label + suffix for suffix in (".etu", ".log", ".json")]
    for name in names: s.checked(ASSETS / name)
    for key in ("home", "userprofile", "appdata", "localappdata", "temp", "tmp", "tmpdir",
                "xdg_cache_home", "xdg_config_home", "xdg_data_home", "pythonuserbase",
                "pythonpycacheprefix", "ccache_dir", "sccache_dir"):
        s.checked(ASSETS / "host" / key)


def make_assets(s):
    cli.require(not ASSETS.exists() and not os.environ.get("OTA_AES_KEY"), "preserve assets/no key override")
    asset_preflight(s)
    pointer, report = review.load_report(s, PRIOR)
    old = phy.assets(s, "prefer2m")
    cli.require(report["summary"]["input"]["targetVersionCode"] == 30268 and
        report["summary"]["input"]["targetImageSha256"] == old["target"]["sha256"], "wrong retained receiver")
    host, shared = phy.previous.asset_api.host, phy.previous.asset_api.shared
    pack_path = phy.previous.AREA / "f/Tools/etu_pack.py"
    unpack_path = phy.previous.AREA / "f/Tools/etu_unpack.py"
    decoder = s.read(ROOT / ".cache/p34-next/n03/assets/result.json")["decoder"]
    inputs = [pointer, report["after"], cli.record(phy.asset_api.OUT / "result.json"),
        decoder, cli.record(pack_path), cli.record(unpack_path), old["target"], old["target_bindings"]["whole_boot"]]
    for item in inputs: cli.require(cli.record(s.checked(item["path"])) == item, "asset input changed")
    env = host.environment(s, ASSETS)
    os.environ.update(env)
    sys.path.insert(0, str(Path(sys.base_prefix) / "Lib/site-packages"))
    pack = cli.load_module("info_timeout_pack", pack_path)
    unpack = cli.load_module("info_timeout_unpack", unpack_path)
    tools = cli.load_module("info_timeout_negatives", ROOT / "Tools/ota/prepare_baud_assets.py")
    before = Path(old["target"]["path"]).read_bytes()
    raw = bytearray(before)
    raw[0x400:0x460] = pack.build_fw_header(bytes(raw), "3.2.69-p34p", 1786320000)
    cli.require(before != raw and before[:0x400] + before[0x460:] == raw[:0x400] + raw[0x460:], "executable changed")
    target = s.raw(ASSETS / "target.bin", bytes(raw))
    identity = shared.identity(bytes(raw), unpack)
    cli.require(identity["version_code"] == 30269, "wrong successor")
    blob = shared.wrap_payload(pack, pack.lzma_alone_encode(bytes(raw)), before, bytes(raw), kind="full")
    package = s.raw(ASSETS / "p34-info-timeout-full.etu", blob)
    def native(label, item, expected):
        return json.loads(host.command(s, ASSETS, label,
            [decoder["path"], item["path"], old["target"]["path"], target["path"], expected], env, 180))
    decoded = native("positive", package, "ok")
    cli.require(all(decoded[k] for k in ("passed", "byte_identical", "boot_ok", "guards_ok", "workspace_lifecycle_ok")),
                "positive native decode failed")
    negatives = []
    for label, broken, expected in tools.negatives(blob, 30268):
        item = s.raw(ASSETS / (label + ".etu"), broken)
        result = native(label, item, expected)
        cli.require(result["passed"] and result["prepares"] == 0, "negative reached preparation")
        negatives.append(dict(name=label, package=item, native=result))
    bindings = copy.deepcopy(old["target_bindings"])
    bindings["profile"].update(image=target, identity=identity, prefix=bytes(raw[:0x460]).hex())
    group = dict(specification=dict(old["specification"], receiver=30268, target_version=30269,
        version_name="3.2.69-p34p", served_name="p34-info-timeout-full.etu", release_key="p34-info-timeout",
        rebootInfoTimeoutMs=1000), receiver=old["target"], receiver_bindings=old["target_bindings"],
        target=target, target_identity=identity, target_bindings=bindings, package=package,
        package_kind="full", decoded=decoded, negatives=negatives)
    s.write(ASSETS / "result.json", dict(result="INFO_TIMEOUT_ASSETS_VERIFIED", group=group,
        inputs=inputs, source=cli.record(__file__), no_build=True, executable_changed=False, hardware=False))
    print("INFO_TIMEOUT_ASSETS_VERIFIED", package["bytes"], package["sha256"], flush=True)


def assets(s):
    value = s.read(ASSETS / "result.json")
    cli.require(value["result"] == "INFO_TIMEOUT_ASSETS_VERIFIED" and value["no_build"] and
                not value["executable_changed"] and not value["hardware"], "verified header successor required")
    group = value["group"]
    for item in [*value["inputs"], group["receiver"], group["target"], group["package"],
                 *[n["package"] for n in group["negatives"]]]:
        cli.require(cli.record(s.checked(item["path"])) == item, "asset bytes changed")
    cli.require(group["specification"]["receiver"] == 30268 and group["specification"]["target_version"] == 30269 and
        group["receiver_bindings"]["whole_boot"] == group["target_bindings"]["whole_boot"], "wrong successor/Boot")
    return group


def validate(value, group):
    cli.require(type(value.get("rebootInfoTimeoutMs")) is int and value["rebootInfoTimeoutMs"] == 1000,
                "only 1s INFO timeout admitted")
    phy.validate(dict(value, rebootInfoTimeoutMs=2000), group)


class Trial(phy.Trial):
    def __init__(self, s):
        self.probe_arm, self.ui_arm, self.arm = "reuse", "measure", "batch"
        self.preinstall, self.new_preinstall, self.new_arm, self.half_arm = True, True, "measure", "measure"
        self.phy_arm, self.phy_checking = "prefer2m", True
        self.assets = assets(s)
        self.proof = batch.clone(batch.radio.confirmed_predecessor, ORDER=(PRIOR.name, "timeout"),
                                TRIALS=PRIOR.parent)(s, "timeout", self.assets)
        self.report = s.read(APK)
        current = s.read(self.proof["report"]["inputs"]["launch"]["path"])
        cli.require(self.report["apk"] == current["apk"] and cli.record(s.checked(current["apk"]["path"])) == current["apk"],
                    "reuse the exact installed APK")
        path = Path(self.proof["plan"]["profile"]["path"])
        batch.radio.backend.Backend.__init__(self, s, path, s.read(path), cli.RECONNECT_GROUP)
        self.receiver_version, self.target_version = 30268, 30269
        self.served_name = self.assets["specification"]["served_name"]

    def context(self, out):
        c = super().context(out)
        c.n04_prior_assets.append(phy.assets(self.store, "prefer2m"))
        c.previous_assets = c.n04_prior_assets[-1]
        c.envelope = repaired.fixed_envelope()
        c.envelope.ROOT, c.envelope.checked = ROOT, c.checked
        c.p.query.m = c.envelope
        previous = c.sources
        extra = sources() + [cli.record(ASSETS / "result.json"), cli.record(HOST / "result.json"), cli.record(APK)]
        c.sources = lambda: sorted({i["path"]: i for i in [*previous(), *extra]}.values(), key=lambda i: i["path"])
        return c

    def phone(self, c, name, *, producer=False):
        phone = super().phone(c, name, producer=producer)
        original = phone.config
        def config(*args):
            value = dict(original(*args), rebootInfoTimeoutMs=1000)
            validate(value, self.assets)
            return value
        phone.config = config
        return phone


def sources():
    return [cli.record(p) for p in (Path(__file__), TEST, Path(phy.__file__), Path(repaired.__file__),
        repaired.ENVELOPE, ROOT / ".cache/p34-phy-logfix/hci-correlation-001/result.json",
        ROOT / ".cache/p34-phy-logfix/review-001/result.json")]


def tests(s):
    value = s.read(HOST / "result.json")
    cli.require(value["passed"] and value["sources"] == sources(), "current timeout adapter tests required")
    return cli.record(HOST / "result.json")


def archival(s, owner, worker):
    out = AREA / "archive"
    selected = phy.previous.TRIALS / "measure"
    ui.archival.proof(s, PRIOR)
    ui.archival.proof(s, selected)
    for n in ("intent.json", "result.json", "capture", "host", "usb", "stop-intent.json", "mkdir-intent.json", "move-intent.json"):
        s.checked(out / n)
    if worker:
        radio = SimpleNamespace(ORDER=(PRIOR.name,), TRIALS=PRIOR.parent,
            old=SimpleNamespace(TRIAL=selected), APK=APK, backend=batch.radio.backend)
        batch.clone(ui.archival.worker, radio=radio)(s, PRIOR.name, out)
    else:
        cli.require(not out.exists(), "preserve archival")
        s.write(out / "intent.json", dict(time=cli.now(), source=cli.record(__file__), protected=str(PRIOR),
            selected=str(selected), no_delete=True, no_ota=True))
        print(owner.owned.launch(s.checked(AREA / "runtime/archive-001"), Path(__file__), ["archive-worker"], 600))


if __name__ == "__main__":
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                "explicit isolated root required")
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("mode", choices=("assets-launch", "assets-worker", "test", "check", "archive", "archive-worker",
                                    "launch", "coordinator", "network", "cell"))
    p.add_argument("--arm", choices=("timeout",), default="timeout")
    a = p.parse_args()
    s = cli.Store(ROOT)
    owner = cli.load_module("info_timeout_owner", ROOT / ".cache/p3-4-screening-20260922/supervisor.py")
    if a.mode not in ("assets-launch", "test", "check", "archive", "launch"):
        cli.require(owner.owned.in_job(), "finite worker required")
    if a.mode == "assets-launch":
        asset_preflight(s)
        print(owner.owned.launch(s.checked(AREA / "runtime/assets-001"), Path(__file__), ["assets-worker"], 900))
    elif a.mode == "assets-worker":
        make_assets(s)
    elif a.mode == "test":
        import unittest
        cli.require(not HOST.exists(), "preserve tests")
        for name in ("tests.log", "result.json"): s.checked(HOST / name)
        sys.path.insert(0, str(ROOT / "tests/ota"))
        stream = io.StringIO()
        result = unittest.TextTestRunner(stream=stream, verbosity=2).run(
            unittest.defaultTestLoader.loadTestsFromName("test_p34_info_timeout"))
        s.raw(HOST / "tests.log", stream.getvalue().encode())
        s.write(HOST / "result.json", dict(passed=result.wasSuccessful(), count=result.testsRun, sources=sources(), device_operations=0))
        print(stream.getvalue())
        cli.require(result.wasSuccessful(), "timeout tests failed")
    elif a.mode.startswith("archive"):
        tests(s)
        archival(s, owner, a.mode == "archive-worker")
    else:
        tests(s)
        api = Trial(s)
        c = api.context(OUT)
        api.preflight(c, OUT)
        if a.mode == "check":
            value = api.phone(c, "timeout_offline").config(c, "s04", 921600, 28, "https://offline.trycloudflare.com")
            validate(value, api.assets)
            cli.require(api.installed_context(OUT).receiver_image_sha == api.assets["target"]["sha256"], "target binding differs")
            print("INFO_TIMEOUT_OFFLINE_VERIFIED", len(c.sources()), flush=True)
        elif a.mode == "launch":
            result = s.read(AREA / "archive/result.json")
            closed = s.read(AREA / "runtime/archive-001/closed.json")
            cli.require(result["result"] == "INACTIVE_CAPTURE_ARCHIVED_VERIFIED" and result["usb_closed"] and
                result["protected_snapshot_unchanged"] and result["configuration_unchanged"] and len(result["remaining"]) == 7 and
                closed["worker_exit"] == 0 and not closed["forced_termination"], "archive unresolved")
            cli.require(not OUT.exists(), "preserve original timeout cell")
            s.write(OUT / "intent.json", dict(time=cli.now(), sources=c.sources(), tests=tests(s), arm="timeout",
                scope="one header-only30268-to30269 full; only INFO1s instead of2s; same APK/Boot/PHY/cadence", independent_acceptance=False))
            print(owner.owned.launch(s.checked(OUT / "runtime/coordinator"), Path(__file__), ["coordinator"], 6000))
        else:
            cli.require(c.sources() == s.read(OUT / "intent.json")["sources"], "running trial inputs changed")
            os.environ.update(c.environment())
            if a.mode == "coordinator":
                batch.clone(ui.coordinate, __file__=__file__, tests=tests)(s, api, c, owner, OUT, "timeout")
            else:
                api.validate(c, OUT)
                result = api.network_worker(c, OUT) if a.mode == "network" else api.cell_worker(c, OUT, "s04")
                cli.require(result == 0, "timeout cell requires reconciliation")
