"""Resume the unstarted batch12 matrix after the phone USB cable was restored."""
import argparse
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_batch12_trial as old

cli, AREA = old.cli, old.AREA
FAILED = old.TRIALS / "control"
TRIALS = AREA / "resumed-trials"
TEST = ROOT / "tests/ota/test_p34_batch12_recovery.py"
HOST = AREA / "recovery-tests-001"
MISSING = "exact phone did not become online in the bounded USB window"


def verify_unstarted(result, owner, usb, commands, started):
    cli.require(not started and result.get("result") == "UI_TRIAL_INCOMPLETE" and
                result.get("error") == "RuntimeError" and result.get("detail") == MISSING,
                "different failure or device work may have started")
    cli.require(owner.get("result") == "WORKER_ERROR" and owner.get("worker_exit") == 1 and
                owner.get("forced_termination") is False and usb.get("port_closed") is True and
                usb.get("port") == 5062 and all(usb.get(k) == 0 for k in
                    ("stop_exit", "server_exit", "launcher_exit")) and
                usb.get("key_before") and usb.get("key_before") == usb.get("key_after"),
                "prior owner or USB closure unresolved")
    cli.require(commands and all(x.get("args") == ["get-state"] and x.get("exit") == 1 and
                x.get("stdout") == "" and x.get("stdout_bytes") == 0 and
                x.get("stderr", "").strip() == "error: device '10ADA4197U001CK' not found"
                for x in commands), "previous commands are not only missing-device checks")


def reconciled(s):
    paths = [FAILED / "coordinator-result.json", FAILED / "runtime/coordinator/closed.json",
             FAILED / "capacity-preflight/usb/closed.json", FAILED / "capacity-preflight/usb/commands.jsonl",
             FAILED / "intent.json"]
    commands = [json.loads(x) for x in paths[3].read_text(encoding="utf-8").splitlines()]
    started = any((FAILED / name).exists() for name in
                  ("cells", "prestart-phone", "plan.json", "runtime/network", "runtime/s04", "live-network.json"))
    verify_unstarted(*(s.read(p) for p in paths[:3]), commands, started)
    for item in s.read(paths[4])["sources"]:
        cli.require(cli.record(item["path"]) == item, "original trial input changed")
    old.archive_ready(s, "control")
    return [cli.record(p) for p in paths]


def predecessor(s, arm, group):
    cli.require(arm in old.ORDER, "unlisted recovery arm")
    root = old.PRIOR if arm == "control" else TRIALS / "control"
    return old.batch.clone(old.batch.radio.confirmed_predecessor,
        ORDER=(root.name, "next"), TRIALS=root.parent)(s, "next", group)


class Trial(old.Trial):
    def __init__(self, s, arm):
        reconciled(s)
        old.batch.clone(old.Trial.__init__, predecessor=predecessor)(self, s, arm)

    def context(self, out):
        c = super().context(out)
        before = c.sources
        extra = [cli.record(p) for p in (Path(__file__), TEST, HOST / "result.json")]
        extra += reconciled(self.store)
        c.sources = lambda: sorted({x["path"]: x for x in [*before(), *extra]}.values(), key=lambda x: x["path"])
        return c


def tests(s):
    old.tests(s)
    value = s.read(HOST / "result.json")
    cli.require(value.get("result") == "PASS" and value["source"] == cli.record(__file__) and
                value["test"] == cli.record(TEST), "current recovery tests required")
    return cli.record(HOST / "result.json")


def archive(s, owner, arm, worker):
    cli.require(arm == "batch12", "control archive already completed; do not repeat")
    reconciled(s)
    old.batch.clone(old.archive, TRIALS=TRIALS, __file__=__file__)(s, owner, arm, worker)


def main():
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                "isolated explicit root required")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("launch", "coordinator", "network", "cell", "archive", "archive-worker"))
    parser.add_argument("--arm", choices=old.ORDER, default="control")
    a = parser.parse_args()
    s = cli.Store(ROOT)
    owner = cli.load_module("batch12_recovery_owner", ROOT / ".cache/p3-4-screening-20260922/supervisor.py")
    tests(s)
    if a.mode not in ("launch", "archive"):
        cli.require(owner.owned.in_job(), "finite recovery owner required")
    if a.mode.startswith("archive"):
        archive(s, owner, a.arm, a.mode == "archive-worker")
        return
    out = s.checked(TRIALS / a.arm)
    if a.mode == "launch":
        cli.require(not out.exists(), "preserve resumed trial; reconcile instead of replay")
        old.archive_ready(s, a.arm)
    api = Trial(s, a.arm)
    c = api.context(out)
    api.preflight(c, out)
    if a.mode == "launch":
        s.write(out / "intent.json", dict(time=cli.now(), sources=c.sources(), tests=tests(s), arm=a.arm,
            recovery=reconciled(s), scope="resume declared batch3/12 matrix; same APK/assets/archive; no replay",
            independent_acceptance=False))
        print(owner.owned.launch(s.checked(out / "runtime/coordinator"), Path(__file__),
                                ["coordinator", "--arm", a.arm], 6000))
    else:
        cli.require(c.sources() == s.read(out / "intent.json")["sources"], "running recovery inputs changed")
        os.environ.update(c.environment())
        if a.mode == "coordinator":
            old.batch.clone(old.ui.coordinate, __file__=__file__, tests=tests)(s, api, c, owner, out, a.arm)
        else:
            api.validate(c, out)
            code = api.network_worker(c, out) if a.mode == "network" else api.cell_worker(c, out, "s04")
            cli.require(code == 0, "recovery incomplete; preserve original device outcome")


if __name__ == "__main__":
    main()
