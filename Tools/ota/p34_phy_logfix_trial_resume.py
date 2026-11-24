"""Bind the prepared remaining PHY cell to the successful resumed APK install."""
import argparse
import os
from pathlib import Path
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_phy_logfix_trial as original
import p34_phy_logfix_install_resume as install

cli, AREA, OUT, RECOVERY = original.cli, original.AREA, original.OUT, original.RECOVERY
HOST = AREA / "trial-resume-tests-001"
TEST = ROOT / "tests/ota/test_p34_phy_logfix_trial_resume.py"


def validate_installed(report, proof, result, closed):
    cli.require(result["result"] == "PHY_LOGFIX_SAME_SIGNER_INSTALLED" and result["usb_closed"] and
        result["original_invalid_capture_preserved"] and result["configuration_preserved"] and
        result["permissions_preserved"] and result["installed"]["sha256"] == report["apk"]["sha256"] == install.TARGET_SHA and
        result["retained"] == proof["checkpoint"] and not result["app_launched"] and
        closed["worker_exit"] == 0 and not closed["forced_termination"], "resumed installation unresolved")


def installed(s):
    install.tests(s)
    report, proof = install.inputs(s)
    validate_installed(report, proof, s.read(install.OUT / "result.json"), s.read(AREA / "runtime/install-002/closed.json"))
    return report, proof


# Preserve the original helper/provenance fields; only rebind the new operation.
original.install = SimpleNamespace(**dict(vars(original.install), OUT=install.OUT, inputs=install.inputs))
original.installed = installed


def sources():
    return original.sources() + install.sources() + [cli.record(p) for p in
        (Path(__file__), TEST, install.HOST / "result.json")]


def tests(s):
    original.tests(s)
    install.tests(s)
    value = s.read(HOST / "result.json")
    cli.require(value["passed"] and value["sources"] == sources(), "current resumed-trial tests required")
    return cli.record(HOST / "result.json")


class Trial(original.Trial):
    def context(self, out):
        c = super().context(out)
        before = c.sources
        extra = sources() + [cli.record(HOST / "result.json")]
        if not self.checking:
            extra += [cli.record(AREA / "runtime/install-002/closed.json")]
        c.sources = lambda: sorted({i["path"]: i for i in [*before(), *extra]}.values(), key=lambda i: i["path"])
        return c


if __name__ == "__main__":
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                "isolated explicit root required")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("archive", "archive-worker", "check", "launch", "coordinator", "network", "cell"))
    parser.add_argument("--arm", choices=("prefer2m",), default="prefer2m")
    args = parser.parse_args()
    s = cli.Store(ROOT)
    tests(s)
    owner = cli.load_module("phy_logfix_resumed_trial_owner", ROOT / ".cache/p3-4-screening-20260922/supervisor.py")
    if args.mode == "archive":
        installed(s)
        cli.require(not RECOVERY.exists(), "preserve original recovery")
        for name in ("intent.json", "result.json", "move-intent.json", "capture", "runtime-config.json", "host", "usb"):
            s.checked(RECOVERY / name)
        s.write(RECOVERY / "intent.json", dict(time=cli.now(), sources=sources(), no_delete=True, no_ota=True))
        print(owner.owned.launch(s.checked(AREA / "runtime/recovery-001"), Path(__file__), ["archive-worker"], 600))
    elif args.mode == "archive-worker":
        cli.require(owner.owned.in_job() and s.read(RECOVERY / "intent.json")["sources"] == sources(), "source-pinned archive owner required")
        original.archive_worker(s)
    else:
        if args.mode not in ("check", "launch"):
            cli.require(owner.owned.in_job(), "finite trial owner required")
        if args.mode == "launch":
            original.recovery(s)
            cli.require(not OUT.exists(), "preserve candidate trial")
        api = Trial(s, checking=args.mode == "check")
        c = api.context(OUT)
        api.preflight(c, OUT)
        if args.mode == "check":
            config = api.phone(c, "phy_logfix_resumed_offline").config(c, "s04", 921600, 28, "https://offline.trycloudflare.com")
            original.old.validate(config, api.assets)
            cli.require(api.installed_context(OUT).receiver_image_sha == api.assets["target"]["sha256"], "target binding differs")
            print("PHY_LOGFIX_RESUMED_OFFLINE_VERIFIED", len(c.sources()), flush=True)
        elif args.mode == "launch":
            s.write(OUT / "intent.json", dict(time=cli.now(), sources=c.sources(), tests=tests(s), arm=args.arm,
                scope="remaining prefer2m after verified resumed installation; no observe replay/reset/Boot replacement",
                independent_acceptance=False))
            print(owner.owned.launch(s.checked(OUT / "runtime/coordinator"), Path(__file__), ["coordinator"], 6000))
        else:
            cli.require(c.sources() == s.read(OUT / "intent.json")["sources"], "running trial sources changed")
            os.environ.update(c.environment())
            if args.mode == "coordinator":
                original.batch.clone(original.ui.coordinate, __file__=__file__, tests=tests)(s, api, c, owner, OUT, args.arm)
            else:
                api.validate(c, OUT)
                code = api.network_worker(c, OUT) if args.mode == "network" else api.cell_worker(c, OUT, "s04")
                cli.require(code == 0, "trial incomplete; reconcile original outcome")
