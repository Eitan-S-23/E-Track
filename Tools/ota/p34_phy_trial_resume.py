"""Use the verified resumed installation with the unchanged PHY trial machinery."""
import argparse
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_phy_trial as original
import p34_phy_install_resume as install

cli, AREA, TRIALS = original.cli, original.AREA, original.TRIALS
TEST = ROOT / "tests/ota/test_p34_phy_trial_resume.py"
HOST = AREA / "trial-resume-tests-001"
original.install, original.apk = install, install.apk


def bindings():
    return [cli.record(p) for p in (Path(__file__), TEST, Path(install.__file__),
        install.HOST / "result.json", install.OUT / "result.json", AREA / "runtime/install-002/closed.json")]


class Trial(original.Trial):
    def context(self, out):
        c = super().context(out)
        before, extra = c.sources, bindings() + [cli.record(HOST / "result.json")]
        c.sources = lambda: sorted({x["path"]: x for x in [*before(), *extra]}.values(), key=lambda x: x["path"])
        return c


def tests(s):
    original.tests(s)
    install.tests(s)
    value = s.read(HOST / "result.json")
    cli.require(value["result"] == "PASS" and value["bindings"] == bindings(), "current resumed-trial tests required")
    return cli.record(HOST / "result.json")


def main():
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                "isolated explicit root required")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("check", "archive", "archive-worker", "launch", "coordinator", "network", "cell"))
    parser.add_argument("--arm", choices=original.ORDER, default="observe")
    args = parser.parse_args()
    s, out = cli.Store(ROOT), TRIALS / args.arm
    owner = cli.load_module("phy_resumed_trial_owner", ROOT / ".cache/p3-4-screening-20260922/supervisor.py")
    tests(s)
    if args.mode not in ("check", "archive", "launch"):
        cli.require(owner.owned.in_job(), "finite owned worker required")
    if args.mode.startswith("archive"):
        original.batch.clone(original.archive, __file__=__file__)(s, owner, args.arm, args.mode == "archive-worker")
        return
    if args.mode == "launch":
        cli.require(not out.exists(), "preserve trial")
        original.batch.clone(original.previous.old.archive_ready, AREA=AREA)(s, args.arm)
    print("PHY_CONTEXT_BINDING", args.mode, args.arm, flush=True)
    api = Trial(s, args.arm, checking=args.mode == "check")
    c = api.context(out)
    api.preflight(c, out)
    print("PHY_CONTEXT_BOUND", args.mode, args.arm, flush=True)
    if args.mode == "check":
        config = api.phone(c, "phy_resume_check").config(c, "s04", 921600, 28, "https://offline.trycloudflare.com")
        original.validate(config, api.assets)
        cli.require(api.installed_context(out).receiver_image_sha == api.assets["target"]["sha256"], "target context differs")
        print("PHY_RESUMED_OFFLINE_VERIFIED", len(c.sources()), flush=True)
    elif args.mode == "launch":
        s.write(out / "intent.json", dict(time=cli.now(), sources=c.sources(), tests=tests(s), arm=args.arm,
            scope="declared PHY cell after verified same-signer update; user Start; no replay/reset/Boot replacement"))
        print(owner.owned.launch(s.checked(out / "runtime/coordinator"), Path(__file__),
            ["coordinator", "--arm", args.arm], 6000), flush=True)
    else:
        cli.require(c.sources() == s.read(out / "intent.json")["sources"], "source-pinned PHY inputs changed")
        os.environ.update(c.environment())
        if args.mode == "coordinator":
            original.batch.clone(original.ui.coordinate, __file__=__file__, tests=tests)(s, api, c, owner, out, args.arm)
        else:
            api.validate(c, out)
            code = api.network_worker(c, out) if args.mode == "network" else api.cell_worker(c, out, "s04")
            cli.require(code == 0, "PHY trial incomplete; reconcile original result")


if __name__ == "__main__":
    main()
