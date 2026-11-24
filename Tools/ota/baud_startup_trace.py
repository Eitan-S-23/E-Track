"""Bounded, non-halting startup diagnosis for the preserved failed bootstrap."""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import struct
import sys
import time

SELF = Path(__file__).resolve()
RUN = "bootstrap-trace"
APP = 0x08010000
PCSR, ICSR, CFSR = 0xE000101C, 0xE000ED04, 0xE000ED28


def require(value, message):
    if not value:
        raise RuntimeError(message)


class StartupProbe:
    """Read-only samples are diagnostics, never a substitute for health gates."""

    def __init__(self, link, profiles):
        self.link, self.profiles = link, profiles
        self.previous = None
        self.epoch, self.count, self.stagnant = 0, 0, 0
        self.stack_epochs = set()

    def read(self, address, size):
        if (address, address + size) not in self.link.ram_reads:
            self.link.ram_reads.append((address, address + size))
        return self.link.read(address, size)

    def word(self, address):
        return struct.unpack("<I", self.read(address, 4))[0]

    def sample(self, include_baseline=False):
        if self.count >= 240:
            return None
        self.link.running()
        prefix = self.link.read(APP, 0x460)
        found = [p for p in self.profiles if p["prefix"] == prefix]
        if len(found) != 1 or (found[0]["version"] == 30207 and not include_baseline):
            return None
        p = found[0]
        tick = self.word(p["tick"])
        health = struct.unpack("<9I", self.read(p["health"], 36))
        previous = self.previous
        if previous and (previous["version"] != p["version"] or tick < previous["tick"]):
            self.epoch += 1
            self.stagnant = 0
        elif previous and previous["loops"] == health[4]:
            self.stagnant += 1
        else:
            self.stagnant = 0
        faults = struct.unpack("<5I", self.read(CFSR, 20))
        sample = dict(index=self.count, epoch=self.epoch, version=p["version"], tick=tick,
                      pcsr=self.word(PCSR), icsr=self.word(ICSR),
                      faults=dict(zip(("cfsr", "hfsr", "dfsr", "mmfar", "bfar"), faults)),
                      health=list(health), state=self.read(p["state"], 3).hex(),
                      sd_ready=self.read(p["sd_ready"], 1)[0])
        stalled = (tick >= 1500 and health[4] == 0) or self.stagnant >= 4
        if self.epoch not in self.stack_epochs and (faults[0] or faults[1] or stalled):
            sample["stack_top_4k"] = self.read(0x20057000, 4096).hex()
            sample["stack_base"] = 0x20057000
            address = p["rtt"]
            if self.read(address, 16).startswith(b"SEGGER RTT"):
                descriptor = self.read(address + 24, 24)
                _, buffer, size, wr, rd, _ = struct.unpack("<6I", descriptor)
                if 16 <= size <= 8192 and 0x20000000 <= buffer and buffer + size <= 0x20058000 and wr < size and rd < size:
                    sample["rtt_ring_snapshot"] = dict(address=buffer, size=size, wr=wr, rd=rd,
                                                       bytes=self.read(buffer, size).hex(), consuming=False)
            self.stack_epochs.add(self.epoch)
        self.link.running()
        require(self.link.read(APP, 0x460) == prefix, "image changed inside startup sample")
        self.previous = dict(version=p["version"], tick=tick, loops=health[4])
        self.count += 1
        return sample


def load_runtime():
    spec = importlib.util.spec_from_file_location("startup_runtime", SELF.with_name("baud_runtime.py"))
    runtime = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runtime)
    return runtime


def profiles(runtime):
    result = []
    for code, p in runtime.m.load_bindings()["profiles"].items():
        text = Path(p["map"]["path"]).read_text(encoding="utf-8")
        result.append(dict(version=int(code), prefix=bytes.fromhex(p["prefix"]), **p["symbols"],
                           health=runtime.m.map_bss(text, "_ZL12g_ota_health", 36),
                           state=runtime.m.map_bss(text, "_ZL20g_ota_state_snapshot", 1)))
    return result


def validation_root(runtime):
    return runtime.cell("bootstrap") / "failure/probe-validation"


def bind_trace(runtime):
    original = runtime.m.ImageReader
    bound = profiles(runtime)
    streams = []
    runtime.m.Evidence.NAMES = (*runtime.m.Evidence.NAMES, "startup-probe.jsonl")

    class TracedReader(original):
        def __init__(self, link, *args, **kwargs):
            super().__init__(link, *args, **kwargs)
            self.probe, self.next_sample = StartupProbe(link, bound), 0
            path = runtime.b.checked(link.e.out / "startup-probe.jsonl")
            self.trace = path.open("x", encoding="utf-8", newline="\n")
            streams.append(self.trace)

        def poll(self):
            if time.monotonic() >= self.next_sample:
                self.next_sample = time.monotonic() + .5
                try:
                    sample = self.probe.sample()
                    if sample:
                        self.trace.write(json.dumps(dict(time=runtime.b.now(), **sample)) + "\n")
                        self.trace.flush()
                except runtime.m.passive.Transition:
                    pass
            return super().poll()

    runtime.m.ImageReader = TracedReader
    return streams


def validate_probe(runtime):
    b, m, c = runtime.b, runtime.m, runtime.m.c
    require(runtime.supervisor.owned.in_job(), "owned bounded worker required")
    m.native_authority()
    out = b.checked(validation_root(runtime))

    class Evidence(c.Evidence):
        NAMES = (*c.Evidence.NAMES, "startup-probe.jsonl")

    for name in Evidence.NAMES:
        b.checked(out / name)
    os.environ.update(runtime.supervisor.owned.environment(out.parent / "probe-host"))
    e = Evidence(out)
    link = m.BoundLink(e, writable=False)
    probe = StartupProbe(link, profiles(runtime))
    result = dict(started=b.now(), result="PROBE_NOT_VALIDATED", source=b.record(SELF),
                  flash=0, reset=0, target_writes=0, native_history_before=c.record(c.MRU))
    samples = []
    try:
        link.connect()
        with b.checked(out / "startup-probe.jsonl").open("x", encoding="utf-8", newline="\n") as stream:
            for _ in range(16):
                sample = probe.sample(include_baseline=True)
                require(sample and sample["version"] == 30207 and sample["state"] == "040101", "baseline changed")
                samples.append(sample)
                stream.write(json.dumps(dict(time=b.now(), **sample)) + "\n")
                stream.flush()
                time.sleep(.5)
        require(samples[-1]["health"][4] > samples[0]["health"][4] and
                samples[-1]["health"][5] > samples[0]["health"][5] and
                all(x["faults"]["cfsr"] == 0 and x["faults"]["hfsr"] == 0 for x in samples), "probe disturbed baseline")
        result.update(result="PASSIVE_PROBE_VALIDATED", samples=len(samples),
                      pcsr_values=sorted({hex(x["pcsr"]) for x in samples}),
                      pc_sampling_available=any(x["pcsr"] for x in samples))
    except Exception as error:
        result["error"] = type(error).__name__ + ": " + str(error)
    finally:
        link.close()
        result.update(ended=b.now(), reader_closed=not link.opened, native_history_after=c.record(c.MRU))
        e.save("result.json", result)
        e.events.close()
        e.ledger.close()
    print(json.dumps(result), flush=True)
    return 0 if result["result"] == "PASSIVE_PROBE_VALIDATED" else 1


def configure_workers(runtime):
    runtime.PHONE = runtime.RUNTIME / "phone-r2"

    def launch(name, mode, seconds, run=None):
        args = [mode] + (["--run", run] if run else [])
        return runtime.supervisor.owned.launch(runtime.RUNTIME / name, SELF, args, seconds)

    runtime.launch_worker = launch


def prepare_run(runtime):
    b = runtime.b
    check = runtime.read(validation_root(runtime) / "result.json")
    require(check["result"] == "PASSIVE_PROBE_VALIDATED" and check["reader_closed"] and
            check["source"] == b.record(SELF), "validate current probe before starting a new diagnostic")
    require(not runtime.cell(RUN).exists(), "diagnostic run already prepared; inspect it instead")
    prior = runtime.read(runtime.cell("bootstrap") / "failure/readback/result.json")
    require(prior["result"] == "BASELINE_RETAINED_BOOT_AND_SLOTS_VERIFIED" and prior["reader_closed"], "failure not reconciled")
    p = runtime.phone("bootstrap")
    require(p.installed("runtime") is not None, "exact installed App required")
    pkg, pid, remote = p.location("runtime")
    health = json.loads(p.file_bytes(pkg, remote + "/health.json", 8192))
    require(health["healthy"] and health["upgradeStarts"] == health["upgradeEnds"] == 1 and
            health["outcome"] == "not-completed", "App changed since failure")
    snapshot = p.file_bytes(pkg, remote + "/snapshot-1.jsonl", p.envelope.MAX_BYTES + 8192)
    require(snapshot == (runtime.cell("bootstrap") / "finished/snapshot.jsonl").read_bytes(), "original failure snapshot changed")
    runtime.save(runtime.cell("bootstrap") / "failure/app-release.json", dict(time=b.now(), pid=pid, health=health,
                 snapshot=b.record(runtime.cell("bootstrap") / "finished/snapshot.jsonl"), source=b.record(SELF)))
    runtime.event("release-reconciled-bootstrap-app", "started", pid=pid)
    require(p.command(["shell", "pidof", pkg]).strip() == str(pid), "App process identity changed")
    p.command(["shell", "am", "force-stop", pkg])
    require(not p.command(["shell", "pidof", pkg], check=False).strip(), "debug App did not stop")
    runtime.event("release-reconciled-bootstrap-app", "completed", data_preserved=True)
    runtime.save(runtime.PHONE / "stop.json", dict(time=b.now(), reason="renew owned USB window for startup diagnosis"))
    old = runtime.wait_file(runtime.PHONE / "closed.json", 45)
    old_sup = runtime.wait_file(runtime.RUNTIME / "phone-worker/closed.json", 20)
    require(old["port_closed"] and old["stop_exit"] == 0 and not old.get("forced_cleanup") and
            not old_sup["forced_termination"] and old_sup["worker_exit"] == 0 and not p.alive(), "old USB route is not closed")
    configure_workers(runtime)
    runtime.launch_worker("phone-startup-trace", "phone-worker", 5430)
    runtime.wait_file(runtime.PHONE / "ready.json", 60)
    runtime.start(RUN, 115200, "bootstrap")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("launch-probe", "probe-worker", "prepare-run", "phone-worker", "capture-worker", "coordinate"))
    parser.add_argument("--run", default=RUN)
    args = parser.parse_args()
    runtime = load_runtime()
    require(Path.cwd().resolve() == runtime.b.ROOT and sys.flags.isolated and sys.flags.no_site and
            sys.dont_write_bytecode and args.run == RUN, "isolated bounded startup task required")
    runtime.authority()
    if args.mode == "launch-probe":
        print(runtime.supervisor.owned.launch(runtime.RUNTIME / "probe-validation", SELF, ["probe-worker"], 90), flush=True)
    elif args.mode == "probe-worker":
        cycle = runtime.load("startup_lock", SELF.with_name("repeat_cycle.py"))
        with cycle.device_lock():
            raise SystemExit(validate_probe(runtime))
    elif args.mode == "prepare-run":
        prepare_run(runtime)
    else:
        configure_workers(runtime)
        os.environ.update(runtime.environment())
        if args.mode == "phone-worker":
            runtime.phone().server()
        elif args.mode == "capture-worker":
            streams = bind_trace(runtime)
            cycle = runtime.load("startup_lock", SELF.with_name("repeat_cycle.py"))
            try:
                with cycle.device_lock():
                    rc = runtime.m.capture(args.run)
            finally:
                for stream in streams:
                    stream.close()
            raise SystemExit(rc)
        else:
            runtime.coordinate(args.run)
            result = runtime.read(runtime.cell(args.run) / "coordinator-result.json")
            if result.get("app_health", {}).get("outcome") == "not-completed":
                runtime.save(runtime.cell(args.run) / "stop.json", dict(time=runtime.b.now(), reason="preserve failed startup diagnostic"))


if __name__ == "__main__":
    main()
