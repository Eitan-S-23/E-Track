"""Run the single declared batch12 interaction cell using existing bounded owners."""
import argparse
import os
from pathlib import Path
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_pump_batch_assets as asset_api

previous = asset_api.previous
old, cli, batch, ui = previous.old, previous.cli, previous.batch, previous.ui
AREA, PRIOR, ORDER = asset_api.AREA, asset_api.PRIOR, asset_api.ORDER
TRIALS = AREA / "trials"
TEST = ROOT / "tests/ota/test_p34_pump_batch_trial.py"
HOST = AREA / "trial-tests-001"


def assets(s, arm):
    cli.require(arm in ORDER, "unlisted pump batch arm")
    value = s.read(asset_api.OUT / "result.json")
    cli.require(value["result"] == "PUMP_BATCH_ASSETS_VERIFIED" and value["hardware"] is False
                and value["no_build"] is True, "verified successor assets required")
    group = value["groups"][arm]
    for item in [*value["inputs"], group["receiver"], group["target"], group["package"],
                 *[x["package"] for x in group["negatives"]]]:
        cli.require(cli.record(s.checked(item["path"])) == item, "pump batch asset changed")
    spec = group["specification"]
    cli.require(spec["receiver"] == 30263 and spec["target_version"] == 30264 and spec["dataBatchFrames"] == 12
                and spec["rebootProbeIntervalMs"] == 500 and spec["reuseRebootInfoLink"] is True
                and group["package_kind"] == "full" and group["receiver_bindings"]["whole_boot"] ==
                group["target_bindings"]["whole_boot"] and all(group["decoded"][k] for k in
                ("passed", "byte_identical", "boot_ok", "guards_ok", "workspace_lifecycle_ok")), "wrong successor policy")
    return group


def predecessor(s, arm, group):
    cli.require(arm in ORDER, "unlisted predecessor")
    return batch.clone(batch.radio.confirmed_predecessor, ORDER=(PRIOR.name, "next"), TRIALS=PRIOR.parent)(s, "next", group)


class Trial(previous.Trial):
    def __init__(self, s, arm, checking=False):
        self.probe_arm, self.ui_arm, self.arm = "reuse", "measure", "batch"
        self.preinstall, self.new_preinstall, self.new_arm = True, checking, arm
        self.assets = assets(s, arm)
        self.proof = predecessor(s, arm, self.assets)
        self.report = old.apk(s)
        path = Path(self.proof["plan"]["profile"]["path"])
        batch.radio.backend.Backend.__init__(self, s, path, s.read(path), cli.RECONNECT_GROUP)
        self.receiver_version, self.target_version = 30263, 30264
        self.served_name = self.assets["specification"]["served_name"]

    def context(self, out):
        c = super().context(out)
        c.n04_prior_assets.append(previous.assets(self.store, "measure"))
        c.previous_assets = c.n04_prior_assets[-1]
        before = c.sources
        paths = [Path(__file__), TEST, Path(asset_api.__file__), HOST / "result.json",
                 asset_api.OUT / "result.json", previous.AREA / "review-001/result.json"]
        if not self.new_preinstall: paths.append(AREA / "archive-measure/result.json")
        extra = [cli.record(p) for p in paths]
        c.sources = lambda: sorted({x["path"]: x for x in [*before(), *extra]}.values(), key=lambda x: x["path"])
        return c


def tests(s):
    previous.tests(s)
    value = s.read(HOST / "result.json")
    cli.require(value["result"] == "PASS" and value["source"] == cli.record(__file__)
                and value["test"] == cli.record(TEST) and value["assets_source"] == cli.record(asset_api.__file__),
                "current interaction tests required")
    return cli.record(HOST / "result.json")


def archive(s, owner, worker):
    prior = previous.TRIALS / "bootstrap"
    ui.archival.proof(s, PRIOR)
    ui.archival.proof(s, prior)
    out = s.checked(AREA / "archive-measure")
    if worker:
        radio = SimpleNamespace(ORDER=(PRIOR.name,), TRIALS=PRIOR.parent, old=SimpleNamespace(TRIAL=prior),
            APK=old.AREA / "apk-g1/apk.json", backend=batch.radio.backend)
        batch.clone(ui.archival.worker, radio=radio)(s, PRIOR.name, out)
    else:
        old.apk(s)
        tests(s)
        cli.require(not out.exists(), "preserve archive attempt")
        for name in ("intent.json", "result.json", "capture", "host", "usb", "stop-intent.json", "mkdir-intent.json", "move-intent.json"):
            s.checked(out / name)
        s.write(out / "intent.json", dict(source=cli.record(__file__), protected=str(PRIOR),
                                         selected=str(prior), no_delete=True, no_ota=True))
        print(owner.owned.launch(s.checked(AREA / "runtime/archive-measure"), Path(__file__), ["archive-worker"], 600))


if __name__ == "__main__":
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                "isolated explicit root required")
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("mode", choices=("check", "archive", "archive-worker", "launch", "coordinator", "network", "cell"))
    p.add_argument("--arm", choices=ORDER, default="measure")
    a = p.parse_args()
    s, out = cli.Store(ROOT), TRIALS / a.arm
    owner = cli.load_module("pump_batch_owner", ROOT / ".cache/p3-4-screening-20260922/supervisor.py")
    tests(s)
    if a.mode not in ("check", "archive", "launch"): cli.require(owner.owned.in_job(), "finite owner required")
    if a.mode.startswith("archive"):
        archive(s, owner, a.mode == "archive-worker")
    else:
        if a.mode == "launch":
            cli.require(not out.exists(), "preserve interaction trial")
            batch.clone(old.archive_ready, AREA=AREA)(s, a.arm)
        api = Trial(s, a.arm, checking=a.mode == "check")
        c = api.context(out)
        api.preflight(c, out)
        if a.mode == "check":
            value = api.phone(c, "interaction_offline").config(c, "s04", 921600, 28, "https://offline.trycloudflare.com")
            old.validate(value, api.assets)
            cli.require(api.installed_context(out).receiver_image_sha == api.assets["target"]["sha256"], "target binding differs")
            print("PUMP_BATCH_OFFLINE_VERIFIED", a.arm, len(c.sources()))
        elif a.mode == "launch":
            s.write(out / "intent.json", dict(time=cli.now(), sources=c.sources(), tests=tests(s), arm=a.arm,
                scope="one batch12 interaction on active pump; same APK; no replay/reset/Boot replacement", independent_acceptance=False))
            print(owner.owned.launch(s.checked(out / "runtime/coordinator"), Path(__file__), ["coordinator"], 6000))
        else:
            cli.require(c.sources() == s.read(out / "intent.json")["sources"], "running interaction inputs changed")
            os.environ.update(c.environment())
            if a.mode == "coordinator":
                batch.clone(ui.coordinate, __file__=__file__, tests=tests)(s, api, c, owner, out, a.arm)
            else:
                api.validate(c, out)
                code = api.network_worker(c, out) if a.mode == "network" else api.cell_worker(c, out, "s04")
                cli.require(code == 0, "interaction incomplete; reconcile originals")
