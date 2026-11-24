"""Same-APK bootstrap/measurement for optional 32KiB installation erases."""
import argparse
import os
from pathlib import Path
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_half_erase_assets as asset_api

previous = asset_api.previous
old, cli, batch, ui = previous.old, previous.cli, previous.batch, previous.ui
AREA, PRIOR, ORDER = asset_api.AREA, asset_api.PRIOR, asset_api.ORDER
TRIALS = AREA / "trials"
TEST = ROOT / "tests/ota/test_p34_half_erase_trial.py"
HOST = AREA / "trial-tests-001"


def assets(s, arm):
    cli.require(arm in ORDER, "unlisted half erase arm")
    value = s.read(asset_api.OUT / "result.json")
    cli.require(value["result"] == "HALF_ERASE_ASSETS_VERIFIED" and value["hardware"] is False, "verified assets required")
    group = value["groups"][arm]
    for item in [*value["inputs"], group["receiver"], group["target"], group["package"],
                 *[x["package"] for x in group["negatives"]]]:
        cli.require(cli.record(s.checked(item["path"])) == item, "half erase asset changed")
    spec = group["specification"]
    version = 30265 + ORDER.index(arm)
    cli.require(spec["receiver"] == version-1 and spec["target_version"] == version and spec["dataBatchFrames"] == 12
                and spec["rebootProbeIntervalMs"] == 500 and spec["reuseRebootInfoLink"] is True
                and group["package_kind"] == "full" and group["receiver_bindings"]["whole_boot"] ==
                group["target_bindings"]["whole_boot"] and all(group["decoded"][k] for k in
                ("passed", "byte_identical", "boot_ok", "guards_ok", "workspace_lifecycle_ok")), "wrong half erase policy")
    return group


def predecessor(s, arm, group):
    cli.require(arm in ORDER, "unlisted predecessor")
    root = PRIOR if arm == "bootstrap" else TRIALS / "bootstrap"
    return batch.clone(batch.radio.confirmed_predecessor, ORDER=(root.name, "next"), TRIALS=root.parent)(s, "next", group)


class Trial(previous.Trial):
    def __init__(self, s, arm, checking=False):
        self.probe_arm, self.ui_arm, self.arm = "reuse", "measure", "batch"
        # Ancestor 'measure' selects the completed pump/sender history, not this arm.
        self.preinstall, self.new_preinstall, self.new_arm = True, checking, "measure"
        self.half_arm = arm
        self.assets = assets(s, arm)
        self.proof = predecessor(s, arm, self.assets)
        self.report = old.apk(s)
        path = Path(self.proof["plan"]["profile"]["path"])
        batch.radio.backend.Backend.__init__(self, s, path, s.read(path), cli.RECONNECT_GROUP)
        spec = self.assets["specification"]
        self.receiver_version, self.target_version = spec["receiver"], spec["target_version"]
        self.served_name = spec["served_name"]

    def context(self, out):
        c = super().context(out)
        c.n04_prior_assets.append(previous.assets(self.store, "measure"))
        if self.half_arm == "measure": c.n04_prior_assets.append(assets(self.store, "bootstrap"))
        c.previous_assets = c.n04_prior_assets[-1]
        before = c.sources
        paths = [Path(__file__), TEST, Path(asset_api.__file__), Path(asset_api.build.__file__), HOST / "result.json",
                 asset_api.OUT / "result.json", AREA / "build/result.json", AREA / "build/source.json",
                 AREA / "tests/r4/result.json", ROOT / "Tools/ota/p34_half_erase.patch"]
        if not self.new_preinstall: paths.append(AREA / ("archive-" + self.half_arm) / "result.json")
        extra = [cli.record(p) for p in paths]
        c.sources = lambda: sorted({x["path"]: x for x in [*before(), *extra]}.values(), key=lambda x: x["path"])
        return c


def tests(s):
    previous.tests(s)
    value = s.read(HOST / "result.json")
    cli.require(value["result"] == "PASS" and value["source"] == cli.record(__file__)
                and value["test"] == cli.record(TEST) and value["assets_source"] == cli.record(asset_api.__file__),
                "current half erase trial tests required")
    return cli.record(HOST / "result.json")


def archive(s, owner, arm, worker):
    cli.require(arm in ORDER, "unlisted archive")
    current = PRIOR if arm == "bootstrap" else TRIALS / "bootstrap"
    prior = previous.previous.TRIALS / "measure" if arm == "bootstrap" else PRIOR
    ui.archival.proof(s, current)
    ui.archival.proof(s, prior)
    out = s.checked(AREA / ("archive-" + arm))
    if worker:
        radio = SimpleNamespace(ORDER=(current.name,), TRIALS=current.parent, old=SimpleNamespace(TRIAL=prior),
            APK=old.AREA / "apk-g1/apk.json", backend=batch.radio.backend)
        batch.clone(ui.archival.worker, radio=radio)(s, current.name, out)
    else:
        old.apk(s)
        tests(s)
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
    p.add_argument("--arm", choices=ORDER, default="bootstrap")
    a = p.parse_args()
    s, out = cli.Store(ROOT), TRIALS / a.arm
    owner = cli.load_module("half_erase_trial_owner", ROOT / ".cache/p3-4-screening-20260922/supervisor.py")
    tests(s)
    if a.mode not in ("check", "archive", "launch"): cli.require(owner.owned.in_job(), "finite owner required")
    if a.mode.startswith("archive"):
        archive(s, owner, a.arm, a.mode == "archive-worker")
    else:
        if a.mode == "launch":
            cli.require(not out.exists(), "preserve half erase trial")
            batch.clone(old.archive_ready, AREA=AREA)(s, a.arm)
        api = Trial(s, a.arm, checking=a.mode == "check")
        c = api.context(out)
        api.preflight(c, out)
        if a.mode == "check":
            value = api.phone(c, "half_erase_offline").config(c, "s04", 921600, 28, "https://offline.trycloudflare.com")
            old.validate(value, api.assets)
            cli.require(api.installed_context(out).receiver_image_sha == api.assets["target"]["sha256"], "target binding differs")
            print("HALF_ERASE_OFFLINE_VERIFIED", a.arm, len(c.sources()))
        elif a.mode == "launch":
            s.write(out / "intent.json", dict(time=cli.now(), sources=c.sources(), tests=tests(s), arm=a.arm,
                scope="one declared half erase cell; same APK/batch12; no replay/reset/Boot replacement", independent_acceptance=False))
            print(owner.owned.launch(s.checked(out / "runtime/coordinator"), Path(__file__), ["coordinator", "--arm", a.arm], 6000))
        else:
            cli.require(c.sources() == s.read(out / "intent.json")["sources"], "running half erase inputs changed")
            os.environ.update(c.environment())
            if a.mode == "coordinator":
                batch.clone(ui.coordinate, __file__=__file__, tests=tests)(s, api, c, owner, out, a.arm)
            else:
                api.validate(c, out)
                code = api.network_worker(c, out) if a.mode == "network" else api.cell_worker(c, out, "s04")
                cli.require(code == 0, "half erase trial incomplete; reconcile originals")
