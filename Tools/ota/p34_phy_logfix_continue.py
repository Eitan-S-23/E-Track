"""Reconcile an auto-started, recorder-blocked App and run the unspent PHY cell."""
import argparse
import json
import os
from pathlib import Path
import sys
from types import FunctionType

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_phy_logfix_trial_resume as trial
import p34_phy_logfix_inspect as inspect

cli, AREA, OUT = trial.cli, trial.AREA, trial.OUT
RECOVERY = AREA / "recovery-002"
HOST = AREA / "continue-tests-001"
TEST = ROOT / "tests/ota/test_p34_phy_logfix_continue.py"
base = trial.original


def blocked_inventory(names, config, expected_config, headers, pid):
    cli.require(len(names) == len(set(names)) == 8 and all(base.backend.CAPTURE_NAME.fullmatch(n) for n in names) and
        sorted(names)[-1] == trial.install.CAPTURE and base.PROTECTED in names and config == expected_config and
        headers and all(h["kind"] == "open" and str(h["pid"]) != pid for h in headers),
        "new recording/config may exist; no stop is permitted")


def recover(s):
    trial.installed(s)
    inspected = s.read(inspect.OUT / "result.json")
    cli.require(inspected["result"] == "CURRENT_APP_INSPECTED_NO_MUTATION" and inspected["usb_closed"], "inspection unresolved")
    for name in ("startup-inspect-001", "runtime-state-001"):
        closed = s.read(AREA / "runtime" / name / "closed.json")
        cli.require(not closed["forced_termination"] and closed["worker_exit"] in (0, 1), "prior owner unresolved")
    pid = inspected["pid"]
    before = cli.load_module("phy_prestop_readback", ROOT / "Tools/ota/p34_phy_readback.py")
    board_out = RECOVERY / "prestop-mcu"
    FunctionType(before.worker.__code__, dict(before.worker.__globals__, OUT=board_out), "worker")(s)
    board = s.read(board_out / "result.json")
    trial.install.validate_retained(board, s.read(board["checkpoint"]["path"]))
    b, d, p, lock = trial.install.runtime()
    stop_out = RECOVERY / "stop"
    with lock.device_lock(), d["usb"](b, p, stop_out):
        p.phone_identity()
        cli.require(d["installed"](b, p, trial.install.TARGET_SHA) is not None, "installed repair differs")
        cli.require(p.command(["shell", "pidof", trial.install.PKG], check=False).strip() == pid, "new App process; inspect it first")
        names = p.command(["exec-out", "run-as", trial.install.PKG, "ls", "-1", "files/p34-observations"]).splitlines()
        config = p.file_bytes(trial.install.PKG, "files/p34-experiment.json", 8192)
        expected = (inspect.OUT / "runtime-config.json").read_bytes()
        headers = []
        for name in names:
            cli.require(base.backend.CAPTURE_NAME.fullmatch(name), "unknown capture name")
            raw = p.command(["exec-out", "run-as", trial.install.PKG, "head", "-n", "1",
                "files/p34-observations/" + name + "/events.jsonl"], timeout=15, binary=True)
            cli.require(len(raw) <= 8192, "header too large")
            headers.append(json.loads(raw))
        blocked_inventory(names, config, expected, headers, pid)
        cli.require(names == inspected["names"], "capture inventory changed")
        s.raw(stop_out / "runtime-config.json", config)
        s.write(stop_out / "stop-intent.json", dict(time=cli.now(), pid=pid, board=board["checkpoint"], headers=headers,
            reason="fresh raw-confirmed idle MCU; eight prior captures block recorder initialization and BEGIN; no current-PID capture"))
        p.command(["shell", "am", "force-stop", trial.install.PKG])
        cli.require(not p.command(["shell", "pidof", trial.install.PKG], check=False).strip(), "App did not stop")
        cli.require(p.command(["exec-out", "run-as", trial.install.PKG, "ls", "-1", "files/p34-observations"]).splitlines() == names,
                    "capture appeared during stop; reconcile")
    s.write(stop_out / "result.json", dict(time=cli.now(), result="RECORDER_BLOCKED_APP_STOPPED", pid=pid,
        usb_closed=True, no_ota=True, no_install=True, board=board["checkpoint"]))
    FunctionType(base.archive_worker.__code__, dict(base.archive_worker.__globals__, RECOVERY=RECOVERY), "archive_worker")(s)


def recovered(s):
    report, proof = trial.installed(s)
    value = s.read(RECOVERY / "result.json")
    closed = s.read(AREA / "runtime/recovery-002/closed.json")
    stopped = s.read(RECOVERY / "stop/result.json")
    cli.require(value["result"] == "PHY_INVALID_CAPTURE_ARCHIVED" and value["usb_closed"] and
        value["app_stopped"] and value["no_delete"] and value["no_ota"] and value["raw_target"] == proof["checkpoint"] and
        closed["worker_exit"] == 0 and not closed["forced_termination"] and
        stopped["result"] == "RECORDER_BLOCKED_APP_STOPPED" and stopped["usb_closed"], "reconciled archive incomplete")
    board = s.read(stopped["board"]["path"])
    trial.install.validate_retained(s.read(RECOVERY / "prestop-mcu/result.json"), board)
    for item in [value["config"], value["protected"], stopped["board"], *value["source_files"].values()]:
        cli.require(cli.record(s.checked(item["path"])) == item, "recovery bytes changed")
    return report, proof, value


def sources():
    return trial.sources() + [cli.record(p) for p in (Path(__file__), TEST, Path(inspect.__file__),
        inspect.OUT / "result.json", ROOT / "Tools/ota/p34_phy_readback.py")]


def tests(s):
    trial.tests(s)
    result = s.read(HOST / "result.json")
    cli.require(result["passed"] and result["sources"] == sources(), "current continuation tests required")
    return cli.record(HOST / "result.json")


class Trial(trial.Trial):
    def context(self, out):
        c = super().context(out)
        previous = c.sources
        extra = sources() + [cli.record(HOST / "result.json")]
        if not self.checking:
            extra += [cli.record(p) for p in (RECOVERY / "result.json", RECOVERY / "stop/result.json",
                RECOVERY / "prestop-mcu/result.json", AREA / "runtime/recovery-002/closed.json")]
        c.sources = lambda: sorted({i["path"]: i for i in [*previous(), *extra]}.values(), key=lambda i: i["path"])
        return c


if __name__ == "__main__":
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                "isolated explicit root required")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("recover", "recover-worker", "launch", "coordinator", "network", "cell"))
    parser.add_argument("--arm", choices=("prefer2m",), default="prefer2m")
    args = parser.parse_args()
    s = cli.Store(ROOT)
    tests(s)
    owner = cli.load_module("phy_continue_owner", ROOT / ".cache/p3-4-screening-20260922/supervisor.py")
    if args.mode == "recover":
        cli.require(not RECOVERY.exists(), "preserve recovery operation")
        for name in ("intent.json", "result.json", "failure.json", "prestop-mcu", "stop", "capture", "runtime-config.json", "move-intent.json", "usb", "host"):
            s.checked(RECOVERY / name)
        s.write(RECOVERY / "intent.json", dict(time=cli.now(), sources=sources(), no_ota=True, no_install=True, no_delete=True))
        print(owner.owned.launch(s.checked(AREA / "runtime/recovery-002"), Path(__file__), ["recover-worker"], 900))
    elif args.mode == "recover-worker":
        cli.require(owner.owned.in_job() and s.read(RECOVERY / "intent.json")["sources"] == sources(), "source-pinned recovery required")
        try:
            recover(s)
        except Exception as error:
            s.write(RECOVERY / "failure.json", dict(time=cli.now(), error=type(error).__name__, detail=str(error)))
            raise
    else:
        if args.mode != "launch": cli.require(owner.owned.in_job(), "finite trial owner required")
        recovered(s)
        base.RECOVERY, base.recovery = RECOVERY, recovered
        if args.mode == "launch": cli.require(not OUT.exists(), "preserve original PHY candidate")
        api = Trial(s)
        c = api.context(OUT)
        api.preflight(c, OUT)
        if args.mode == "launch":
            config = api.phone(c, "phy_continue_check").config(c, "s04", 921600, 28, "https://offline.trycloudflare.com")
            base.old.validate(config, api.assets)
            cli.require(api.installed_context(OUT).receiver_image_sha == api.assets["target"]["sha256"], "target binding differs")
            s.write(OUT / "intent.json", dict(time=cli.now(), sources=c.sources(), tests=tests(s), arm=args.arm,
                scope="remaining prefer2m with repaired capture; no observe replay/reset/Boot replacement", independent_acceptance=False))
            print(owner.owned.launch(s.checked(OUT / "runtime/coordinator"), Path(__file__), ["coordinator"], 6000))
        else:
            cli.require(c.sources() == s.read(OUT / "intent.json")["sources"], "running trial sources changed")
            os.environ.update(c.environment())
            if args.mode == "coordinator":
                base.batch.clone(base.ui.coordinate, __file__=__file__, tests=tests)(s, api, c, owner, OUT, args.arm)
            else:
                api.validate(c, OUT)
                code = api.network_worker(c, OUT) if args.mode == "network" else api.cell_worker(c, OUT, "s04")
                cli.require(code == 0, "trial incomplete; reconcile original outcome")
