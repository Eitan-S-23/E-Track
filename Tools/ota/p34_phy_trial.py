"""Source-bound schema8 PHY cells, reusing the closed-trial OTA collectors."""
import argparse
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_phy_assets as asset_api
import p34_phy_install as install

previous = asset_api.previous
cli, batch, ui = previous.cli, previous.batch, previous.ui
AREA, PRIOR, ORDER = asset_api.AREA, asset_api.PRIOR, asset_api.ORDER
TRIALS = AREA / "trials"
TEST = ROOT / "tests/ota/test_p34_phy_trial.py"
HOST = AREA / "trial-tests-001"


def assets(s, arm):
    cli.require(arm in ORDER, "unlisted PHY arm")
    value = s.read(asset_api.OUT / "result.json")
    cli.require(value["result"] == "PHY_ASSETS_VERIFIED" and not value["hardware"] and
                value["no_build"] and not value["executable_changed"], "verified header-only assets required")
    group = value["groups"][arm]
    for item in [*value["inputs"], group["receiver"], group["target"], group["package"],
                 *[x["package"] for x in group["negatives"]]]:
        cli.require(cli.record(s.checked(item["path"])) == item, "PHY asset changed")
    spec = group["specification"]
    version = 30267 + ORDER.index(arm)
    cli.require(spec["receiver"] == version - 1 and spec["target_version"] == version and
        spec["androidPhyPolicy"] == arm and spec["dataBatchFrames"] == 12 and
        group["receiver_bindings"]["whole_boot"] == group["target_bindings"]["whole_boot"] and
        all(group["decoded"][k] for k in ("passed", "byte_identical", "boot_ok", "guards_ok", "workspace_lifecycle_ok")),
        "wrong PHY asset policy")
    return group


def validate(value, group):
    previous.old.validate({**{k: v for k, v in value.items() if k != "androidPhyPolicy"}, "schema": 7}, group)
    cli.require(type(value.get("schema")) is int and value["schema"] == 8 and
        value.get("androidPhyPolicy") == group["specification"]["androidPhyPolicy"] and
        value["androidPhyPolicy"] in ORDER, "wrong schema8 PHY policy")


def verify(capture, messages, expected, sha):
    cli.require(type(expected.get("schema")) is int and expected["schema"] == 8 and
                expected.get("androidPhyPolicy") in ORDER, "schema8 expected")
    value = batch.radio.original_verify(capture, messages, expected, sha)
    fields = set(expected) - {"target", "firmwareLatestUrl"} | {"deviceAddress", "endpointHost", "configSha256"}
    cli.require(set(value) == fields and all(type(value[k]) is type(expected[k]) and value[k] == expected[k]
        for k in set(expected) - {"target", "firmwareLatestUrl"}), "PHY experiment record differs")
    return value


batch.radio.backend.verify_experiment = verify


def verify_phy(messages, expected, sha):
    values = [json.loads(line[len("OTA_PHY "):]) for line in messages.splitlines() if line.startswith("OTA_PHY ")]
    cli.require(len(values) == 1, "one original actual-PHY observation required")
    value = values[0]
    cli.require(type(value.get("schema")) is int and value["schema"] == 1 and value.get("status") == "observed" and
        value.get("configSha256") == sha and value.get("requestId") == expected["runId"] and
        value.get("remoteId") == expected["target"] and value.get("policy") == expected["androidPhyPolicy"] and
        type(value.get("connectionGeneration")) is int and value["connectionGeneration"] > 0 and
        type(value.get("elapsedMicros")) is int and 0 <= value["elapsedMicros"] < 4000000 and
        type(value.get("beforeReadStatus")) is int and value["beforeReadStatus"] == 0 and all(type(value.get(k)) is int and 1 <= value[k] <= 3
        for k in ("beforeTxPhy", "beforeRxPhy", "txPhy", "rxPhy")), "invalid or stale PHY readback")
    if value["policy"] == "prefer2m":
        cli.require(all(type(value.get(k)) is int and value[k] == 0 for k in ("readStatus", "updateStatus")) and
                    value["txPhy"] == value["rxPhy"] == 2, "2M preference lacks actual bidirectional 2M")
    return value


def apk(s, checking=False):
    report = install.inputs(s)[0]
    if not checking:
        result = s.read(install.OUT / "result.json")
        closed = s.read(AREA / "runtime/install-001/closed.json")
        cli.require(result["result"] == "FIXED_SIGNER_BATCH_UPDATE_VERIFIED" and result["usb_closed"] and
            result["installed"]["sha256"] == report["apk"]["sha256"] and result["snapshot_preserved"] and
            result["configuration_preserved"] and result["permissions_preserved"] and
            closed["worker_exit"] == 0 and not closed["forced_termination"], "PHY installation unresolved")
    return report


class Trial(previous.Trial):
    def __init__(self, s, arm, checking=False):
        self.probe_arm, self.ui_arm, self.arm = "reuse", "measure", "batch"
        self.preinstall, self.new_preinstall, self.new_arm, self.half_arm = True, True, "measure", "measure"
        self.phy_arm, self.phy_checking = arm, checking
        self.assets = assets(s, arm)
        root = PRIOR if arm == "observe" else TRIALS / "observe"
        self.proof = batch.clone(batch.radio.confirmed_predecessor,
            ORDER=(root.name, "next"), TRIALS=root.parent)(s, "next", self.assets)
        self.report = apk(s, checking)
        path = Path(self.proof["plan"]["profile"]["path"])
        batch.radio.backend.Backend.__init__(self, s, path, s.read(path), cli.RECONNECT_GROUP)
        spec = self.assets["specification"]
        self.receiver_version, self.target_version = spec["receiver"], spec["target_version"]
        self.served_name = spec["served_name"]

    def context(self, out):
        c = super().context(out)
        c.n04_prior_assets.append(previous.assets(self.store, "measure"))
        if self.phy_arm == "prefer2m": c.n04_prior_assets.append(assets(self.store, "observe"))
        c.previous_assets = c.n04_prior_assets[-1]
        before = c.sources
        paths = [Path(__file__), TEST, Path(asset_api.__file__), Path(install.__file__),
            HOST / "result.json", asset_api.OUT / "result.json", AREA / "apk-g1/apk.json"]
        if not self.phy_checking: paths += [install.OUT / "result.json", AREA / ("archive-" + self.phy_arm) / "result.json"]
        extra = [cli.record(p) for p in paths]
        c.sources = lambda: sorted({x["path"]: x for x in [*before(), *extra]}.values(), key=lambda x: x["path"])
        return c

    def phone(self, c, name, *, producer=False):
        phone = super().phone(c, name, producer=producer)
        before = phone.config
        def config(*args):
            value = dict(before(*args), schema=8, androidPhyPolicy=self.phy_arm)
            validate(value, self.assets)
            return value
        phone.config = config
        return phone

    def finish_install_snapshot(self, c, p, phone, out, pid, remote, expected):
        result = super().finish_install_snapshot(c, p, phone, out, pid, remote, expected)
        _, messages = c.envelope.verify((out / "finished/snapshot.jsonl").read_bytes(),
            sentinel=c.apk["metadata"]["device_observation"]["sentinel"], target=c.TARGET)
        value = verify_phy(messages, expected, cli.record(out / "runtime-config.json")["sha256"])
        c.save(out / "phy-observation.json", dict(result="PRE_BEGIN_PHY_OBSERVED", observation=value,
            continuous_data_phy=False, snapshot=cli.record(out / "finished/snapshot.jsonl")))
        return result


def tests(s):
    value = s.read(HOST / "result.json")
    cli.require(value["result"] == "PASS" and value["source"] == cli.record(__file__) and
        value["test"] == cli.record(TEST), "current PHY host regressions required")
    return cli.record(HOST / "result.json")


def archive(s, owner, arm, worker):
    current = PRIOR if arm == "observe" else TRIALS / "observe"
    prior = previous.TRIALS / "bootstrap" if arm == "observe" else PRIOR
    ui.archival.proof(s, current)
    ui.archival.proof(s, prior)
    out = s.checked(AREA / ("archive-" + arm))
    if worker:
        radio = SimpleNamespace(ORDER=(current.name,), TRIALS=current.parent, old=SimpleNamespace(TRIAL=prior),
            APK=AREA / "apk-g1/apk.json", backend=batch.radio.backend)
        batch.clone(ui.archival.worker, radio=radio)(s, current.name, out)
    else:
        apk(s)
        cli.require(not out.exists(), "preserve archive")
        for name in ("intent.json", "result.json", "capture", "host", "usb", "stop-intent.json", "mkdir-intent.json", "move-intent.json"):
            s.checked(out / name)
        s.write(out / "intent.json", dict(source=cli.record(__file__), protected=str(current), selected=str(prior), no_delete=True, no_ota=True))
        print(owner.owned.launch(s.checked(AREA / "runtime" / ("archive-" + arm)), Path(__file__), ["archive-worker", "--arm", arm], 600))


if __name__ == "__main__":
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                "isolated explicit root required")
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("mode", choices=("check", "archive", "archive-worker", "launch", "coordinator", "network", "cell"))
    p.add_argument("--arm", choices=ORDER, default="observe")
    a = p.parse_args()
    s, out = cli.Store(ROOT), TRIALS / a.arm
    owner = cli.load_module("phy_trial_owner", ROOT / ".cache/p3-4-screening-20260922/supervisor.py")
    tests(s)
    if a.mode not in ("check", "archive", "launch"): cli.require(owner.owned.in_job(), "finite owner required")
    if a.mode.startswith("archive"):
        archive(s, owner, a.arm, a.mode == "archive-worker")
    else:
        if a.mode == "launch":
            cli.require(not out.exists(), "preserve PHY trial")
            batch.clone(previous.old.archive_ready, AREA=AREA)(s, a.arm)
        api = Trial(s, a.arm, checking=a.mode == "check")
        c = api.context(out)
        api.preflight(c, out)
        if a.mode == "check":
            value = api.phone(c, "phy_offline").config(c, "s04", 921600, 28, "https://offline.trycloudflare.com")
            validate(value, api.assets)
            cli.require(api.installed_context(out).receiver_image_sha == api.assets["target"]["sha256"], "target binding differs")
            print("PHY_OFFLINE_VERIFIED", a.arm, len(c.sources()))
        elif a.mode == "launch":
            s.write(out / "intent.json", dict(time=cli.now(), sources=c.sources(), tests=tests(s), arm=a.arm,
                scope="declared PHY cell; user Start; no replay/reset/Boot replacement", independent_acceptance=False))
            print(owner.owned.launch(s.checked(out / "runtime/coordinator"), Path(__file__), ["coordinator", "--arm", a.arm], 6000))
        else:
            cli.require(c.sources() == s.read(out / "intent.json")["sources"], "running PHY inputs changed")
            os.environ.update(c.environment())
            if a.mode == "coordinator":
                batch.clone(ui.coordinate, __file__=__file__, tests=tests)(s, api, c, owner, out, a.arm)
            else:
                api.validate(c, out)
                code = api.network_worker(c, out) if a.mode == "network" else api.cell_worker(c, out, "s04")
                cli.require(code == 0, "PHY trial incomplete; reconcile originals")
