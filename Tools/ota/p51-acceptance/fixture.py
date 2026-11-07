"""Hold the existing single-asset HTTPS fixture through APK build and P51 LONG."""
import argparse
import json
import os
from pathlib import Path
import signal
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
import benchmark as b
h = b.h


def serve(plan, out, seconds):
    h.require(type(seconds) is int and 18000 <= seconds <= 25200, 'finite fixture lifetime required')
    h.require(plan['schema'] == 'p51-benchmark-fixture-v1' and plan['kind'] == 'patch' and
        plan['benchmark']['purpose'] == 'fixed-load-benchmark' and plan['phone']['app']['id'] == b.APP_ID,
        'benchmark-only preparation scope required')
    b.package_binding(plan)
    selected = b.network_plan(plan)
    h.pinned(selected['tools']['cloudflared'])
    b.live_phone.reference_binding(selected)
    out = h.checked(out)
    for name in ('network', 'intent.json', 'result.json', 'failed.json', 'status.json', 'status.json.tmp', 'stop.json'):
        h.checked(out / name)
    h.fresh(out)
    started, stop = time.monotonic(), False
    source = h.record(Path(__file__))
    def cancel(signum, frame):
        nonlocal stop
        stop = True
    previous = {sig: signal.signal(sig, cancel) for sig in (signal.SIGINT, signal.SIGTERM)}
    h.save(out / 'intent.json', dict(pid=os.getpid(), source=source, seconds=seconds,
        package=plan['mcu']['package'], devices=0, normalChannelMutations=0))
    network = b.live_phone.Network(selected, out / 'network')
    outcome = 'FIXTURE_EXPIRED'
    try:
        origin = network.start(deadline=time.monotonic()+180)
        ready = h.record(network.out / 'ready.json')
        print('P51_BENCHMARK_HTTPS_READY ' + origin, flush=True)
        while not stop and time.monotonic() < started+seconds:
            h.require(network.tunnel.alive() and network.thread.is_alive(), 'owned HTTPS fixture stopped unexpectedly')
            request = out / 'stop.json'
            if request.exists():
                h.require(h.read_json(request) == dict(sourceSha256=source['sha256'], pid=os.getpid()),
                    'fixture stop request belongs to another owner')
                outcome = 'FIXTURE_STOPPED_BY_OWNER'
                break
            h.host.io.write_json(h.ROOT, out / 'status.json', dict(pid=os.getpid(), ready=ready,
                source=source, monotonicNs=time.monotonic_ns(),
                deadlineMonotonicNs=int((started+seconds)*1e9)), replace=True)
            time.sleep(1)
        if stop:
            outcome = 'FIXTURE_STOPPED_BY_SIGNAL'
    except BaseException as error:
        h.save(out / 'failed.json', dict(type=type(error).__name__, preserve=True, noAutomaticReplay=True))
        raise
    finally:
        try:
            network.close()
        finally:
            for sig, handler in previous.items():
                signal.signal(sig, handler)
    h.save(out / 'result.json', dict(outcome=outcome, source=source,
        networkClosure=h.record(network.out / 'closed.json'), devices=0, normalChannelMutations=0))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--seconds', type=int, default=25200)
    args = parser.parse_args()
    h.require(Path.cwd() == h.ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
        'explicit worktree and isolated Python required')
    serve(h.read_json(args.inputs), args.out, args.seconds)


if __name__ == '__main__':
    main()
