"""Source-bound successor of the pre-halt display rejection; no Boot writer."""
import argparse
import json
from pathlib import Path
import re
import sys
from types import FunctionType

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'Tools/ota'))
import p34_boot16_probe as prior
from recovery_confirm.boot16_display_entry import Control

cli, host, base = prior.cli, prior.host, prior.base
SELF = Path(__file__).resolve()
FAILED = ROOT / '.cache/p34-boot16-entry-probe1'


def execute(*args, **kwargs):
    if 'control_type' in kwargs: raise ValueError('successor control type is fixed')
    return prior.execute(*args, **kwargs, control_type=Control)


def sources(store):
    hashes = {
        ROOT / 'Tools/ota/p34_boot16_probe.py': 'f582e01fd49196e6d7fe3c1cdea9008cae63e3f6d6847d810c2535b456e03df6',
        ROOT / 'Tools/ota/recovery_confirm/boot16_entry.py': '6f163337976b2bc95d3d89cbbdca8c9cfd2accd801594f2929529dc99bdf8162',
        FAILED / 'worker.json': 'c0a7d324463af632da8dfe4556e5f8dd741fef2135b01ecb4b47501475b7dd78',
    }
    for path, digest in hashes.items(): cli.require(cli.record(path)['sha256'] == digest, 'frozen predecessor changed')
    result = store.read(FAILED / 'worker.json')
    cli.require(result['result'] == 'FAILED' and result['mutation_attempted'] is False and result['close_returned'],
                'reconciled zero-mutation predecessor required')
    return sorted(set([*prior.sources(store), SELF, ROOT / 'Tools/ota/recovery_confirm/boot16_display_entry.py',
        ROOT / 'tests/boot/test_p34_boot16_display.py',
        ROOT / '.cache/p34-early-usb-r2/f/MDK-ARM_F435/Platform/HAL/HAL_Display.cpp',
        *(FAILED / name for name in ('worker.json', 'parent.json', 'plan.json', 'sdk-000.log', 'sdk-001.log', 'events.jsonl')),
        ROOT / '.cache/p34-boot16-entry-probe1-analysis1/result.json']))


# Same owned worker/connect/close implementation; only its declared sources and
# injected control differ. Do not mutate the executed predecessor's globals.
worker = FunctionType(prior.worker.__code__, dict(prior.worker.__globals__, sources=sources, execute=execute),
                      'worker', prior.worker.__defaults__, prior.worker.__closure__)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('selftest', 'capture', 'worker'))
    parser.add_argument('--output-dir', required=True, type=Path)
    parser.add_argument('--tests', type=Path)
    parser.add_argument('--native-history-approved', type=Path)
    args = parser.parse_args()
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                'isolated explicit root required')
    store = cli.Store(ROOT)
    out = store.checked(args.output_dir)
    if args.action == 'worker': return worker(store, out)
    inputs = sources(store)
    prior.preflight(store, out, inputs)
    records = [cli.record(p) for p in inputs]
    if args.action == 'capture':
        tested = store.read(args.tests)
        cli.require(tested['result'] == 'BOOT16_DISPLAY_HOST_PASS' and tested['inputs'] == records,
                    'source-bound successor tests required')
        cli.require(args.native_history_approved == base.HISTORY, 'exact native history approval required')
        before = base.history(store)
    env = host.environment(store, out)
    for path in inputs: store.raw(out / 'source' / path.relative_to(ROOT), path.read_bytes())
    if args.action == 'selftest':
        raw = host.command(store, out, 'tests', [sys.executable, '-I', '-S', '-B', '-X', 'utf8',
            ROOT / 'tests/boot/test_p34_boot16_display.py', '-v'], env, 120)
        count = re.search(rb'Ran (\d+) tests? in .*\r?\n\r?\nOK\b', raw)
        cli.require(count and records == [cli.record(p) for p in inputs], 'successor test/source drift')
        store.write(out / 'result.json', dict(result='BOOT16_DISPLAY_HOST_PASS', tests=int(count[1]),
            inputs=records, hardware=False, independent_acceptance=False))
        print('BOOT16_DISPLAY_HOST_PASS', int(count[1]), flush=True)
        return 0
    store.write(out / 'plan.json', dict(out=str(out), inputs=records, tests=cli.record(args.tests),
        native_history_approved=str(base.HISTORY), before_history=before, worker_seconds=prior.WORKER_SECONDS,
        parent_seconds=prior.PARENT_SECONDS, predecessor=cli.record(FAILED / 'worker.json'),
        boot_writes=0, eeprom_writes=0, nor_writes=0, reset_commands=0,
        scope='new running-display admission and one-second held completion; original same-context release; no Boot write'))
    value = base.owned_run(store, out, [SELF, 'worker', '--output-dir', out], env, timeout=prior.PARENT_SECONDS)
    value.update(after_history=base.history(store), presence_after=base.native_presence())
    store.write(out / 'parent.json', value)
    print(json.dumps(value), flush=True)
    return 0 if value['exit'] == 0 and not value['timeout'] else 1


if __name__ == '__main__': raise SystemExit(main())
