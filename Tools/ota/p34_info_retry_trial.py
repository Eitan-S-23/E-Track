"""Bounded schema9 INFO retry cells; preserve all original OTA safety checks."""
import argparse
import io
import os
from pathlib import Path
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_info_timeout as old
import p34_verified_install as installer

cli, batch, ui = old.cli, old.batch, old.ui
AREA = ROOT / ".cache/p34-info-retry"
TRIALS, HOST = AREA / "trials", AREA / "trial-tests-002"
APK, INSTALL = AREA / "apk-g1/apk.json", AREA / "install-004"
COMMIT = "b6e6e32df1fdf5418aa94ba6ac858256e8ef9066"
ORDER = ("control", "extended")
TEST = ROOT / "tests/ota/test_p34_info_retry_trial.py"


def assets(s, arm):
    cli.require(arm in ORDER, "unlisted retry arm")
    value = s.read(AREA / "assets/result.json")
    cli.require(value["result"] == "INFO_RETRY_ASSETS_VERIFIED" and value["no_build"] and
                not value["executable_changed"] and not value["hardware"], "header-only assets required")
    group = value["groups"][arm]
    for item in [*value["inputs"], group["receiver"], group["target"], group["package"],
                 *[n["package"] for n in group["negatives"]]]:
        cli.require(cli.record(s.checked(item["path"])) == item, "asset bytes changed")
    spec = group["specification"]
    version, attempts = (30270, 3) if arm == "control" else (30271, 12)
    cli.require(spec["receiver"] == version - 1 and spec["target_version"] == version and
        spec["rebootInfoMaxAttempts"] == attempts and spec["rebootInfoTimeoutMs"] == 1000 and
        group["receiver_bindings"]["whole_boot"] == group["target_bindings"]["whole_boot"] and
        all(group["decoded"][k] for k in ("passed", "byte_identical", "boot_ok", "guards_ok", "workspace_lifecycle_ok")) and
        len(group["negatives"]) == 4 and all(n["native"]["passed"] and n["native"]["prepares"] == 0
        for n in group["negatives"]), "wrong retry asset policy")
    return dict(group, specification=dict(spec, served_name="p34-info-retry-" + arm + "-full.etu"))


def installed(s):
    api = installer.Installer(s, old.OUT, APK, COMMIT, INSTALL)
    report, _, _ = api.inputs(s)
    result, closed = s.read(INSTALL / "result.json"), s.read(INSTALL / "runtime/closed.json")
    cli.require(result["result"] == "FIXED_SIGNER_BATCH_UPDATE_VERIFIED" and result["usb_closed"] and
        result["installed"]["sha256"] == report["apk"]["sha256"] and
        all(result[k] for k in ("snapshot_preserved", "configuration_preserved", "permissions_preserved")) and
        closed["worker_exit"] == 0 and not closed["forced_termination"], "retry APK installation unresolved")
    return report


def validate(value, group):
    cli.require(type(value.get("schema")) is int and value["schema"] == 9 and
        type(value.get("rebootInfoMaxAttempts")) is int and
        value["rebootInfoMaxAttempts"] == group["specification"]["rebootInfoMaxAttempts"] and
        value.get("reuseRebootInfoLink") is True, "wrong schema9 retry policy")
    normalized = {k: v for k, v in value.items() if k != "rebootInfoMaxAttempts"}
    old.validate(dict(normalized, schema=8), group)


def verify(capture, messages, expected, sha):
    cli.require(type(expected.get("schema")) is int and expected["schema"] == 9 and
        type(expected.get("rebootInfoMaxAttempts")) is int and expected["rebootInfoMaxAttempts"] in (3, 12) and
        expected.get("reuseRebootInfoLink") is True, "schema9 retry observation required")
    value = batch.radio.original_verify(capture, messages, expected, sha)
    fields = set(expected) - {"target", "firmwareLatestUrl"} | {"deviceAddress", "endpointHost", "configSha256"}
    cli.require(set(value) == fields and all(type(value[k]) is type(expected[k]) and value[k] == expected[k]
        for k in set(expected) - {"target", "firmwareLatestUrl"}), "retry observation differs")
    return value


batch.radio.backend.verify_experiment = verify


def predecessor(arm):
    return old.OUT if arm == "control" else TRIALS / "control"


class Trial(old.Trial):
    def __init__(self, s, arm):
        self.retry_arm = arm
        self.probe_arm, self.ui_arm, self.arm = "reuse", "measure", "batch"
        self.preinstall, self.new_preinstall, self.new_arm, self.half_arm = True, True, "measure", "measure"
        self.phy_arm, self.phy_checking = "prefer2m", True
        self.assets, self.report = assets(s, arm), installed(s)
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
        c.n04_prior_assets.append(old.assets(self.store))
        if self.retry_arm == "extended": c.n04_prior_assets.append(assets(self.store, "control"))
        c.previous_assets = c.n04_prior_assets[-1]
        before = c.sources
        extra = sources() + [cli.record(p) for p in (APK, AREA / "assets/result.json", HOST / "result.json",
                                                     INSTALL / "result.json", INSTALL / "runtime/closed.json")]
        c.sources = lambda: sorted({x["path"]: x for x in [*before(), *extra]}.values(), key=lambda x: x["path"])
        return c

    def phone(self, c, name, *, producer=False):
        phone = super().phone(c, name, producer=producer)
        before = phone.config
        def config(*args):
            value = dict(before(*args), schema=9,
                rebootInfoMaxAttempts=self.assets["specification"]["rebootInfoMaxAttempts"])
            validate(value, self.assets)
            return value
        phone.config = config
        return phone


def sources():
    return [cli.record(p) for p in (Path(__file__), TEST, Path(old.__file__),
        Path(installer.__file__), Path(ui.archival.__file__), ROOT / "Tools/ota/p34_info_retry_assets.py")]


def tests(s):
    value = s.read(HOST / "result.json")
    cli.require(value["passed"] and value["sources"] == sources(), "current retry trial tests required")
    return cli.record(HOST / "result.json")


def archive(s, owner, arm, worker):
    current = predecessor(arm)
    selected = old.PRIOR if arm == "control" else old.OUT
    ui.archival.proof(s, current)
    ui.archival.proof(s, selected)
    installed(s)
    out = AREA / ("archive-" + arm)
    api = installer.Installer(s, old.OUT, APK, COMMIT, out)
    api.preflight()
    for name in ("mkdir-intent.json", "move-intent.json"): s.checked(out / name)
    if worker:
        cli.require(s.read(out / "intent.json")["sources"] == sources(), "archive source changed")
        radio = SimpleNamespace(ORDER=(current.name,), TRIALS=current.parent,
            old=SimpleNamespace(TRIAL=selected), APK=APK, backend=batch.radio.backend)
        batch.clone(ui.archival.worker, radio=radio)(s, current.name, out)
    else:
        cli.require(not out.exists(), "preserve archival receipt")
        s.write(out / "intent.json", dict(time=cli.now(), sources=sources(), tests=tests(s),
            protected=str(current), selected=str(selected), no_delete=True, no_ota=True))
        print(owner.owned.launch(s.checked(out / "runtime"), Path(__file__), ["archive-worker", "--arm", arm], 600))


def archive_ready(s, arm):
    out = AREA / ("archive-" + arm)
    result, closed = s.read(out / "result.json"), s.read(out / "runtime/closed.json")
    cli.require(result["result"] == "INACTIVE_CAPTURE_ARCHIVED_VERIFIED" and result["usb_closed"] and
        result["protected_snapshot_unchanged"] and result["configuration_unchanged"] and result["app_stopped"] and
        len(result["remaining"]) == 7 and closed["worker_exit"] == 0 and not closed["forced_termination"],
        "archive unresolved")


if __name__ == "__main__":
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                "isolated explicit root required")
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("mode", choices=("test", "check", "archive", "archive-worker", "launch", "coordinator", "network", "cell"))
    p.add_argument("--arm", choices=ORDER, default="control")
    a = p.parse_args()
    s, out = cli.Store(ROOT), TRIALS / a.arm
    owner = cli.load_module("info_retry_owner", ROOT / ".cache/p3-4-screening-20260922/supervisor.py")
    if a.mode == "test":
        import unittest
        cli.require(not HOST.exists(), "preserve trial tests")
        for name in ("tests.log", "result.json"): s.checked(HOST / name)
        sys.path.insert(0, str(ROOT / "tests/ota"))
        stream = io.StringIO()
        result = unittest.TextTestRunner(stream=stream, verbosity=2).run(
            unittest.defaultTestLoader.loadTestsFromName("test_p34_info_retry_trial"))
        s.raw(HOST / "tests.log", stream.getvalue().encode())
        s.write(HOST / "result.json", dict(passed=result.wasSuccessful(), count=result.testsRun, sources=sources(), device_operations=0))
        print(stream.getvalue())
        cli.require(result.wasSuccessful(), "retry trial tests failed")
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
                value = api.phone(c, "retry_offline").config(c, "s04", 921600, 28, "https://offline.trycloudflare.com")
                validate(value, api.assets)
                cli.require(api.installed_context(out).receiver_image_sha == api.assets["target"]["sha256"], "wrong target")
                print("INFO_RETRY_OFFLINE_VERIFIED", a.arm, len(c.sources()))
            elif a.mode == "launch":
                archive_ready(s, a.arm)
                cli.require(not out.exists(), "preserve retry cell")
                s.write(out / "intent.json", dict(time=cli.now(), sources=c.sources(), tests=tests(s), arm=a.arm,
                    scope="header-only retry cell; same APK/Boot/radio; user Start; no reset or replay", independent_acceptance=False))
                print(owner.owned.launch(s.checked(out / "runtime/coordinator"), Path(__file__), ["coordinator", "--arm", a.arm], 6000))
            else:
                cli.require(c.sources() == s.read(out / "intent.json")["sources"], "running retry inputs changed")
                os.environ.update(c.environment())
                if a.mode == "coordinator":
                    batch.clone(ui.coordinate, __file__=__file__, tests=tests)(s, api, c, owner, out, a.arm)
                else:
                    api.validate(c, out)
                    code = api.network_worker(c, out) if a.mode == "network" else api.cell_worker(c, out, "s04")
                    cli.require(code == 0, "retry cell incomplete; reconcile original outcome")
