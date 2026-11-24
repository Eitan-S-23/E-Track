"""Fixed-APK batch3/12 cells reusing original ownership, archive and collectors."""
import argparse
import json
import os
from pathlib import Path
import runpy
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_batch12_assets as asset_api
import p34_batch12_artifacts as artifact
import p34_batch_install as installer
import p34_dns_readiness as dns

prior = asset_api.prior
cli, batch, ui = prior.cli, prior.batch, prior.ui
AREA, PRIOR = asset_api.AREA, asset_api.PRIOR
TRIALS = AREA / "trials"
INSTALL = AREA / "install-003"
ORDER = ("control", "batch12")
TEST = ROOT / "tests/ota/test_p34_batch12_trial.py"
HOST = AREA / "trial-tests-003"
READER = AREA / "src/Tools/ota/p3-4-link-stats/batch_timing.py"
PKG = "com.wen.gaia.gaia.p34probe"
OLD_SHA = "2b501a94bdf83d3c9568cb5e2cc2e61d83d71ba9db138e13e638589be228a099"


def assets(s, arm):
    cli.require(arm in ORDER, "unlisted batch12 arm")
    value = s.read(asset_api.OUT / "result.json")
    cli.require(value["result"] == "BATCH12_ASSETS_VERIFIED" and value["hardware"] is False, "verified assets required")
    group = value["groups"][arm]
    for item in [*value["inputs"], group["receiver"], group["target"], group["package"],
                 *[x["package"] for x in group["negatives"]]]:
        cli.require(cli.record(s.checked(item["path"])) == item, "asset changed")
    spec = group["specification"]
    _, version, frames = asset_api.MATRIX[ORDER.index(arm)]
    cli.require(spec["receiver"] == version - 1 and spec["target_version"] == version and
                spec["dataBatchFrames"] == frames and spec["reuseRebootInfoLink"] is True and
                spec["rebootProbeIntervalMs"] == 500 and
                group["receiver_bindings"]["whole_boot"] == group["target_bindings"]["whole_boot"] and
                all(group["decoded"][k] for k in ("passed", "byte_identical", "boot_ok", "guards_ok", "workspace_lifecycle_ok")),
                "wrong batch12 assets")
    return group


def validate(value, group):
    cli.require(type(value.get("schema")) is int and value["schema"] == 7 and
                type(value.get("dataBatchFrames")) is int and
                value["dataBatchFrames"] == group["specification"]["dataBatchFrames"] and
                value["dataBatchFrames"] in (3, 12) and value.get("reuseRebootInfoLink") is True and
                value.get("target") == "02:00:00:00:00:01",
                "wrong batch12 policy")
    batch.radio.validate_config(dict(value, schema=4), group)
    keys = {"schema", "runId", "target", "requestedBaud", "reuseGatt", "withoutResponse", "firmwareLatestUrl",
        "packageBytes", "packageSha256", "currentVersionCode", "currentImageSha256", "targetVersionCode",
        "targetImageSha256", "senderWindowSegments", "transferMode", "prefixBytes", *batch.radio.EXTRA,
        *prior.previous.profile.FLAGS}
    cli.require(set(value) == keys, "unknown or missing batch12 field")


def verify(capture, messages, expected, sha):
    cli.require(type(expected.get("schema")) is int and expected["schema"] == 7 and
                type(expected.get("dataBatchFrames")) is int and expected["dataBatchFrames"] in (3, 12) and
                expected.get("reuseRebootInfoLink") is True and expected.get("transferMode") == "full" and
                expected.get("prefixBytes") == 0, "schema7 full batch required")
    value = batch.radio.original_verify(capture, messages, expected, sha)
    keys = set(expected) - {"target", "firmwareLatestUrl"} | {"deviceAddress", "endpointHost", "configSha256"}
    cli.require(set(value) == keys and all(type(value.get(k)) is type(expected[k]) and value[k] == expected[k]
                for k in (*batch.radio.EXTRA, *prior.previous.profile.FLAGS)), "batch12 observation differs")
    return value


batch.radio.backend.verify_experiment = verify


def full_metrics(messages, total, device):
    value = batch.clone(batch.full_metrics, READER=READER)(messages, total, device)
    stamp = cli.load_module(
        "batch12_observation", ROOT / "Tools/ota/p34_observation.py").experiment_record(messages.splitlines())
    cli.require(value["transfer"]["dataBatch"]["maxFrames"] == stamp["dataBatchFrames"], "summary/config batch differs")
    return value


def inputs(s):
    report = s.read(AREA / "apk-g1/apk.json")
    signer = runpy.run_path(str(ROOT / "Tools/ota/p34_signing_artifacts.py"))
    cli.require(report["sha"] == artifact.SHA and report["metadata"]["application_id"] == PKG and
                report["certificate_sha256"] == signer["CERT"] and cli.record(report["apk"]["path"]) == report["apk"] and
                signer["apk_certificate"](Path(report["apk"]["path"]).read_bytes()) == signer["CERT"], "APK identity differs")
    hosts = set()
    for item in report["host_reports"]:
        cli.require(cli.record(item["path"]) == item, "CI report changed")
        value = s.read(item["path"])
        cli.require(value["development_result"] == "PASS" and value["scope"] == "all" and
                    value["source_before"]["head"] == artifact.SHA and value["source_before"]["clean"], "exact green CI required")
        hosts.add(json.dumps(value["host"], sort_keys=True))
    cli.require(len(hosts) == len(report["host_reports"]) == 2, "both CI hosts required")
    completed = ui.archival.proof(s, PRIOR)
    cli.require(completed["summary"]["input"]["targetVersionCode"] == 30257, "wrong retained predecessor")
    assets(s, "control")
    return report, completed


def apk(s):
    import p34_batch12_install_resume as resume
    return resume.apk(s)


def predecessor(s, arm, group):
    root = PRIOR if arm == "control" else TRIALS / "control"
    return batch.clone(batch.radio.confirmed_predecessor, ORDER=(root.name, "next"), TRIALS=root.parent)(s, "next", group)


class Trial(prior.Cadence):
    def __init__(self, s, arm, preinstall=False):
        self.probe_arm, self.ui_arm, self.arm = "reuse", "measure", "batch"
        self.preinstall, self.new_preinstall, self.new_arm = True, preinstall, arm
        self.assets = assets(s, arm)
        self.proof = predecessor(s, arm, self.assets)
        self.report = inputs(s)[0] if preinstall else apk(s)
        path = Path(self.proof["plan"]["profile"]["path"])
        batch.radio.backend.Backend.__init__(self, s, path, s.read(path), cli.RECONNECT_GROUP)
        spec = self.assets["specification"]
        self.receiver_version, self.target_version = spec["receiver"], spec["target_version"]
        self.served_name = spec["served_name"]

    def context(self, out):
        c = super().context(out)
        c.n04_prior_assets.append(prior.assets(self.store))
        if self.new_arm == "batch12":
            c.n04_prior_assets.append(assets(self.store, "control"))
        c.previous_assets = c.n04_prior_assets[-1]
        before, load = c.sources, c.load
        def current_load(name, path):
            module = load(name, path)
            if Path(path) == ROOT / "Tools/ota/p34_full_trace.py":
                module.full_metrics = full_metrics
            return module
        c.load = current_load
        import p34_batch12_install_resume as resume
        paths = [Path(__file__), TEST, Path(asset_api.__file__), Path(artifact.__file__), Path(dns.__file__),
                 Path(resume.__file__), resume.TEST, resume.HOST / "result.json",
                 asset_api.OUT / "result.json", AREA / "apk-g1/apk.json", READER, HOST / "result.json"]
        if not self.new_preinstall:
            paths += [INSTALL / "result.json", AREA / ("archive-" + self.new_arm) / "result.json"]
        extra = [cli.record(p) for p in paths] + resume.reconciled(self.store)
        c.sources = lambda: sorted({x["path"]: x for x in [*before(), *extra]}.values(), key=lambda x: x["path"])
        return c

    def phone(self, c, name, *, producer=False):
        phone = super().phone(c, name, producer=producer)
        before = phone.config
        def config(*args):
            value = dict(before(*args), schema=7, rebootProbeIntervalMs=500,
                         dataBatchFrames=self.assets["specification"]["dataBatchFrames"])
            validate(value, self.assets)
            return value
        phone.config = config
        return phone

    def verify_served(self, c, origin, *, proxy=False):
        return dns.verify(self, c, origin)


def tests(s):
    value = s.read(HOST / "result.json")
    cli.require(value["result"] == "PASS" and value["source"] == cli.record(__file__) and
                value["test"] == cli.record(TEST), "current host tests required")
    return cli.record(HOST / "result.json")


def archive(s, owner, arm, worker):
    current = PRIOR if arm == "control" else TRIALS / "control"
    previous = prior.PRIOR if arm == "control" else PRIOR
    ui.archival.proof(s, current)
    ui.archival.proof(s, previous)
    out = s.checked(AREA / ("archive-" + arm))
    if worker:
        radio = SimpleNamespace(ORDER=(current.name,), TRIALS=current.parent,
            old=SimpleNamespace(TRIAL=previous), APK=AREA / "apk-g1/apk.json", backend=batch.radio.backend)
        batch.clone(ui.archival.worker, radio=radio)(s, current.name, out)
    else:
        apk(s)
        tests(s)
        cli.require(not out.exists(), "preserve archive")
        for name in ("intent.json", "result.json", "capture", "host", "usb", "stop-intent.json", "mkdir-intent.json", "move-intent.json"):
            s.checked(out / name)
        s.write(out / "intent.json", dict(source=cli.record(__file__), protected=str(current), selected=str(previous), no_delete=True, no_ota=True))
        print(owner.owned.launch(s.checked(AREA / "runtime" / ("archive-" + arm)), Path(__file__), ["archive-worker", "--arm", arm], 600))


def archive_ready(s, arm):
    value = s.read(AREA / ("archive-" + arm) / "result.json")
    owner = s.read(AREA / "runtime" / ("archive-" + arm) / "closed.json")
    cli.require(value["result"] == "INACTIVE_CAPTURE_ARCHIVED_VERIFIED" and value["usb_closed"] and
                value["protected_snapshot_unchanged"] and value["configuration_unchanged"] and
                value["app_stopped"] and len(value["remaining"]) == 7 and
                owner["worker_exit"] == 0 and not owner["forced_termination"], "archive unresolved")


if __name__ == "__main__":
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                "isolated explicit root required")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("check", "archive", "archive-worker",
                                        "launch", "coordinator", "network", "cell"))
    parser.add_argument("--arm", choices=ORDER, default="control")
    a = parser.parse_args()
    s, out = cli.Store(ROOT), TRIALS / a.arm
    owner = cli.load_module("batch12_trial_owner", ROOT / ".cache/p3-4-screening-20260922/supervisor.py")
    tests(s)
    if a.mode not in ("check", "archive", "launch"):
        cli.require(owner.owned.in_job(), "finite owner required")
    if a.mode.startswith("archive"):
        archive(s, owner, a.arm, a.mode == "archive-worker")
    else:
        if a.mode == "launch":
            cli.require(not out.exists(), "preserve trial")
            archive_ready(s, a.arm)
        api = Trial(s, a.arm, preinstall=a.mode == "check")
        c = api.context(out)
        api.preflight(c, out)
        if a.mode == "check":
            value = api.phone(c, "batch12_offline").config(c, "s04", 921600, 28, "https://offline.trycloudflare.com")
            validate(value, api.assets)
            cli.require(api.installed_context(out).receiver_image_sha == api.assets["target"]["sha256"], "wrong target binding")
            print("BATCH12_OFFLINE_VERIFIED_NOT_INSTALLATION", a.arm, len(c.sources()))
        elif a.mode == "launch":
            s.write(out / "intent.json", dict(time=cli.now(), sources=c.sources(), tests=tests(s), arm=a.arm,
                scope="one declared batch3/12 FULL cell; same APK; no replay/reset/Boot replacement", independent_acceptance=False))
            print(owner.owned.launch(s.checked(out / "runtime/coordinator"), Path(__file__), ["coordinator", "--arm", a.arm], 6000))
        else:
            cli.require(c.sources() == s.read(out / "intent.json")["sources"], "running inputs changed")
            os.environ.update(c.environment())
            if a.mode == "coordinator":
                batch.clone(ui.coordinate, __file__=__file__, tests=tests)(s, api, c, owner, out, a.arm)
            else:
                api.validate(c, out)
                code = api.network_worker(c, out) if a.mode == "network" else api.cell_worker(c, out, "s04")
                cli.require(code == 0, "trial incomplete; reconcile originals")
