"""Finish the already-executed cold start and preserve canonical reset types."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import runpy
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
SELF = Path(__file__).resolve()
PARENT = SELF.with_name("baud_uncached.py")


def runtime():
    r = runpy.run_path(str(PARENT), run_name="canonical_clock_parent")["runtime"]()
    previous = r.load

    def load(name, path):
        module = previous(name, path)
        if Path(path).name == "baud_tune.py":
            # Rebinding module.m alone leaves this copied class method pointing
            # at a separately imported Transition class, which poll cannot catch.
            module.ControlLink.running = r.m.BoundLink.running
        return module

    r.load = load
    r.launch_worker = lambda name, mode, seconds, run=None: r.supervisor.owned.launch(
        r.RUNTIME / name, SELF, [mode] + (["--run", run] if run else []), seconds)
    return r


def finish_prior_reset(r, run):
    b, m = r.b, r.m
    tune = r.load("canonical_postreset_tune", SELF.with_name("baud_tune.py"))
    prior_path = b.OUT / "rates/baud-115200-r5.json"
    prior = r.read(prior_path)
    b.require(prior["reader_closed"] and prior["mcu_reset"] == 1 and prior["flash"] == prior["ota"] == 0 and
              prior["commands"][-1]["terminal"].startswith("BXPB: done baud=115200 comm=1 idx=5 "),
              "the prior 115200 probe/reset is not reconciled")
    out, receipt = b.checked(b.OUT / "rates" / run), b.checked(b.OUT / "rates" / (run + ".json"))
    b.require(not out.exists() and not receipt.exists(), "preserve post-reset attempt")
    profile = m.load_bindings()["profiles"]["30208"]
    e, reader = m.Evidence(out), None
    link = tune.ControlLink(e, writable=True)
    result = dict(run=run, baud=115200, version=30208, result="NOT_ADMITTED", source=b.record(SELF),
                  prior_reset=b.record(prior_path), mcu_reset=0, flash=0, ota=0, rate_set=0, commands=[],
                  native_history_before=m.c.record(m.c.MRU))
    try:
        link.connect()
        b.require(m.base.read_image(link, profile["image"]["bytes"]) == Path(profile["image"]["path"]).read_bytes(),
                  "fixed App changed after the prior reset")
        boot = m.read_region(link, 0x08000000, 65536)
        b.require(m.a.sha(boot) == m.load_bindings()["whole_boot"]["sha256"], "Boot changed")
        reader = m.ImageReader(link, {"30208": profile}, channel_factory=tune.ControlChannel)
        lines, deadline = [], time.monotonic() + 60
        while time.monotonic() < deadline:
            observed = reader.poll()
            if observed:
                lines.extend(observed["lines"])
                if any(m.passive.confirmation(line, 30208) for line in lines):
                    break
            time.sleep(.1)
        b.require(any(m.passive.confirmation(line, 30208) for line in lines), "current boot confirmation not observed")
        symbols = profile["symbols"]
        result["boot_fields"] = {name: reader.read32(symbols[name])
                                 for name in ("boot_baud", "retained_word", "retention_error")}
        b.require(result["boot_fields"] == dict(boot_baud=115200, retained_word=m.baud_word(115200), retention_error=0) and
                  reader.read32(m.ERTC_DT20) == m.baud_word(115200), "prior selected baud did not survive reset")
        result["dwt_after_restart"] = reader.check_dwt()
        channel = reader.channel
        before = channel.status()
        command = tune.command_for("probe", 115200, before)
        e.emit("post-reset-probe-reserved", command=command, previous_reset=b.record(prior_path))
        first = channel.send(command)
        terminal = channel.wait(first, lambda line: tune.c.probe_terminal(line, 115200), 10)
        after = channel.status()
        b.require(terminal.startswith("BXPB: done baud=115200 comm=1 idx=5 ") and tune.known(after, 115200) and
                  after["epoch"] == before["epoch"] and after["drop"] == before["drop"] and
                  after["logdrop"] == before["logdrop"], "post-reset UART probe failed or lost evidence")
        result["commands"].append(dict(command=command, before=before, terminal=terminal, after=after))
        result.update(result="BAUD_COLD_START_VERIFIED", post_restart_status=after, identity=profile["identity"],
                      completion="remaining post-reset checks only; no repeated reset or rate setter")
    except Exception as error:
        result["error"] = type(error).__name__ + ": " + str(error)
        e.emit("error", error=result["error"])
    finally:
        if reader:
            reader.close()
        link.close()
        result.update(reader_closed=not link.opened, native_history_after=m.c.record(m.c.MRU), ended=b.now())
        e.save("result.json", result)
        e.events.close()
        e.ledger.close()
        r.save(receipt, result)
    b.require(result["result"] == "BAUD_COLD_START_VERIFIED", result.get("error", "post-reset verification failed"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("launch", "prepare-worker", "capture-worker", "coordinate", "advance", "advance-worker"))
    parser.add_argument("--run", default="baud-115200-r6")
    args = parser.parse_args()
    r = runtime()
    r.b.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                "isolated explicit root required")
    os.environ.update(r.environment())
    r.authority()
    tests_path = r.b.OUT / "host-tests-clock-resume-001/result.json"
    tests = r.read(tests_path)
    r.b.require(tests["passed"] and tests["source"] == r.b.record(SELF) and tests["parent"] == r.b.record(PARENT) and
                tests["test_source"] == r.b.record(SELF.with_name("test_baud_resume_clock.py")) and
                tests["runtime_sources"] == r.sources(), "source-bound canonical reset tests required")
    supplement = r.b.OUT / "clock-resume.json"
    if args.mode == "launch":
        r.b.require(args.run == "baud-115200-r6", "bounded first continuation")
        closed = r.read(r.RUNTIME / "prepare-baud-115200-r5/closed.json")
        r.b.require(closed["worker_exit"] == 1 and not closed["forced_termination"], "prior reader closure unresolved")
        r.save(supplement, dict(source=r.b.record(SELF), parent=r.b.record(PARENT), tests=r.b.record(tests_path),
            plan=r.b.record(r.b.OUT / "plan.json"), prior=r.b.record(r.b.OUT / "rates/baud-115200-r5.json"),
            purpose="canonical reset exception and completion of already-executed cold start"))
        print(r.launch_worker("prepare-" + args.run, "prepare-worker", 900, args.run), flush=True)
        return
    value = r.read(supplement)
    r.b.require(value["source"] == r.b.record(SELF) and value["parent"] == r.b.record(PARENT) and
                value["plan"] == r.b.record(r.b.OUT / "plan.json"), "continuation inputs changed")
    if args.mode == "advance":
        print(r.launch_worker("advance-" + args.run + "-canonical", "advance-worker", 1800, args.run), flush=True)
        return
    r.b.require(r.supervisor.owned.in_job(), "bounded owned worker required")
    if args.mode == "prepare-worker":
        cycle = r.load("canonical_postreset_lock", SELF.with_name("repeat_cycle.py"))
        with cycle.device_lock():
            finish_prior_reset(r, args.run)
        r.start(args.run, 115200, "screen")
    elif args.mode == "capture-worker":
        cycle = r.load("canonical_capture_lock", SELF.with_name("repeat_cycle.py"))
        with cycle.device_lock():
            raise SystemExit(r.m.capture(args.run))
    elif args.mode == "coordinate":
        r.coordinate(args.run)
    else:
        r.advance(args.run)


if __name__ == "__main__":
    main()
