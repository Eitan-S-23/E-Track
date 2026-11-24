"""Bounded SHA compiler screen using the installed APK and original collectors."""
import argparse
import io
import os
from pathlib import Path
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_sha_assets as asset_api
import p34_timed_ack_trial as prior

old, cli, batch, ui = prior.old, prior.cli, prior.batch, prior.ui
AREA, PRIOR, ORDER = asset_api.AREA, asset_api.PRIOR, asset_api.ORDER
TRIALS, HOST = AREA / "trials", AREA / "trial-tests-001"
TEST = ROOT / "tests/ota/test_p34_sha_trial.py"


def assets(s, arm):
    cli.require(arm in ORDER, "unlisted SHA arm")
    value = s.read(AREA / "assets/result.json")
    cli.require(value["result"] == "SHA_ASSETS_VERIFIED" and not value["hardware"], "verified SHA assets required")
    group = value["groups"][arm]
    for item in [*value["inputs"], group["receiver"], group["target"], group["package"],
                 *[n["package"] for n in group["negatives"]]]:
        cli.require(cli.record(s.checked(item["path"])) == item, "SHA asset changed")
    spec, version = group["specification"], 30274 + ORDER.index(arm)
    cli.require(spec["receiver"] == version - 1 and spec["target_version"] == version and
        spec["rebootInfoMaxAttempts"] == 12 and spec["rebootInfoTimeoutMs"] == 1000 and
        spec["dataBatchFrames"] == 12 and spec["androidPhyPolicy"] == "prefer2m" and
        group["receiver_bindings"]["whole_boot"] == group["target_bindings"]["whole_boot"] and
        all(group["decoded"][k] for k in ("passed", "byte_identical", "boot_ok", "guards_ok", "workspace_lifecycle_ok")) and
        len(group["negatives"]) == 4 and all(n["native"]["passed"] and n["native"]["prepares"] == 0
        for n in group["negatives"]), "SHA input policy changed")
    return group


def predecessor(arm):
    return PRIOR if arm == "bootstrap" else TRIALS / "bootstrap"


class Trial(prior.Trial):
    def __init__(self, s, arm):
        self.timed_arm, self.retry_arm = arm, "extended"
        self.probe_arm, self.ui_arm, self.arm = "reuse", "measure", "batch"
        self.preinstall, self.new_preinstall, self.new_arm, self.half_arm = True, True, "measure", "measure"
        self.phy_arm, self.phy_checking = "prefer2m", True
        self.assets, self.report = assets(s, arm), old.installed(s)
        root = predecessor(arm)
        self.proof = batch.clone(batch.radio.confirmed_predecessor, ORDER=(root.name, "next"),
                                TRIALS=root.parent)(s, "next", self.assets)
        path = Path(self.proof["plan"]["profile"]["path"])
        batch.radio.backend.Backend.__init__(self, s, path, s.read(path), cli.RECONNECT_GROUP)
        spec = self.assets["specification"]
        self.receiver_version, self.target_version = spec["receiver"], spec["target_version"]
        self.served_name = spec["served_name"]

    def context(self, out):
        c = super().context(out)
        known = {group["target"]["sha256"] for group in c.n04_prior_assets}
        for arm in prior.ORDER:
            group = prior.assets(self.store, arm)
            if group["target"]["sha256"] not in known:
                c.n04_prior_assets.append(group)
                known.add(group["target"]["sha256"])
        if self.timed_arm == "measure": c.n04_prior_assets.append(assets(self.store, "bootstrap"))
        c.previous_assets = c.n04_prior_assets[-1]
        before = c.sources
        extra = sources() + [cli.record(p) for p in (HOST / "result.json", AREA / "assets/result.json",
            AREA / "build/result.json", AREA / "build/source.json",
            ROOT / ".cache/p34-sha-screen/r1/result.json", ROOT / ".cache/p34-sha-screen/parser-tests-001/result.json")]
        c.sources = lambda: sorted({x["path"]: x for x in [*before(), *extra]}.values(), key=lambda x: x["path"])
        return c


def sources():
    return [cli.record(p) for p in (Path(__file__), TEST, Path(asset_api.__file__),
        Path(asset_api.build.__file__), Path(asset_api.build.screen.__file__),
        asset_api.build.screen.TEST, AREA / "f" / asset_api.build.CMAKE)]


def tests(s):
    value = s.read(HOST / "result.json")
    cli.require(value["passed"] and value["sources"] == sources(), "current SHA trial tests required")
    return cli.record(HOST / "result.json")


def archive(s, owner, arm, worker):
    current = predecessor(arm)
    selected = prior.TRIALS / "bootstrap" if arm == "bootstrap" else PRIOR
    ui.archival.proof(s, current)
    ui.archival.proof(s, selected)
    old.installed(s)
    out = AREA / ("archive-" + arm)
    api = old.installer.Installer(s, old.old.OUT, old.APK, old.COMMIT, out)
    api.preflight()
    for name in ("mkdir-intent.json", "move-intent.json"): s.checked(out / name)
    if worker:
        cli.require(s.read(out / "intent.json")["sources"] == sources(), "archive source changed")
        radio = SimpleNamespace(ORDER=(current.name,), TRIALS=current.parent,
            old=SimpleNamespace(TRIAL=selected), APK=old.APK, backend=batch.radio.backend)
        batch.clone(ui.archival.worker, radio=radio)(s, current.name, out)
    else:
        cli.require(not out.exists(), "preserve archival receipt")
        s.write(out / "intent.json", dict(time=cli.now(), sources=sources(), tests=tests(s),
            protected=str(current), selected=str(selected), no_delete=True, no_ota=True))
        print(owner.owned.launch(s.checked(out / "runtime"), Path(__file__), ["archive-worker", "--arm", arm], 600))


if __name__ == "__main__":
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                "isolated explicit root required")
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("mode", choices=("test", "check", "archive", "archive-worker", "launch", "coordinator", "network", "cell"))
    p.add_argument("--arm", choices=ORDER, default="bootstrap")
    a = p.parse_args()
    s, out = cli.Store(ROOT), TRIALS / a.arm
    owner = cli.load_module("sha_trial_owner", ROOT / ".cache/p3-4-screening-20260922/supervisor.py")
    if a.mode == "test":
        import unittest
        cli.require(not HOST.exists(), "preserve trial tests")
        for name in ("tests.log", "result.json"): s.checked(HOST / name)
        sys.path.insert(0, str(ROOT / "tests/ota"))
        stream = io.StringIO()
        result = unittest.TextTestRunner(stream=stream, verbosity=2).run(
            unittest.defaultTestLoader.loadTestsFromName("test_p34_sha_trial"))
        s.raw(HOST / "tests.log", stream.getvalue().encode())
        s.write(HOST / "result.json", dict(passed=result.wasSuccessful(), count=result.testsRun, sources=sources(), device_operations=0))
        print(stream.getvalue())
        cli.require(result.wasSuccessful(), "SHA trial tests failed")
    else:
        tests(s)
        if a.mode not in ("check", "archive", "launch"): cli.require(owner.owned.in_job(), "finite worker required")
        if a.mode.startswith("archive"):
            archive(s, owner, a.arm, a.mode == "archive-worker")
        else:
            api = Trial(s, a.arm)
            c = api.context(out)
            api.preflight(c, out)
            if a.mode == "check":
                value = api.phone(c, "sha_offline").config(c, "s04", 921600, 28, "https://offline.trycloudflare.com")
                old.validate(value, api.assets)
                cli.require(api.installed_context(out).receiver_image_sha == api.assets["target"]["sha256"], "wrong target")
                cli.require(c.previous_assets["target"] == api.assets["receiver"], "wrong immediate predecessor")
                print("SHA_OFFLINE_VERIFIED", a.arm, len(c.sources()))
            elif a.mode == "launch":
                batch.clone(old.archive_ready, AREA=AREA)(s, a.arm)
                cli.require(not out.exists(), "preserve SHA cell")
                s.write(out / "intent.json", dict(time=cli.now(), sources=c.sources(), tests=tests(s), arm=a.arm,
                    scope="App SHA compiler screen; same APK/Boot/radio; user Start; no reset/replay", independent_acceptance=False))
                print(owner.owned.launch(s.checked(out / "runtime/coordinator"), Path(__file__), ["coordinator", "--arm", a.arm], 6000))
            else:
                cli.require(c.sources() == s.read(out / "intent.json")["sources"], "running SHA inputs changed")
                os.environ.update(c.environment())
                if a.mode == "coordinator":
                    batch.clone(ui.coordinate, __file__=__file__, tests=tests)(s, api, c, owner, out, a.arm)
                else:
                    api.validate(c, out)
                    code = api.network_worker(c, out) if a.mode == "network" else api.cell_worker(c, out, "s04")
                    cli.require(code == 0, "SHA cell incomplete; reconcile original outcome")
