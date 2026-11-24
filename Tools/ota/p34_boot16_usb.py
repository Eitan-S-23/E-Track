"""USB104 successor, same bounded no-payload-write R2 entry qualification."""
import argparse
import json
from pathlib import Path
import re
import sys
from types import FunctionType

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'Tools/ota'))
import p34_boot16_display as previous
from recovery_confirm.boot16_usb_entry import Control

core = previous.prior
cli, host, base = core.cli, core.host, core.base
SELF = Path(__file__).resolve()
FAILED = ROOT / '.cache/p34-boot16-entry-probe2'


def execute(*args, **kwargs):
    if 'control_type' in kwargs: raise ValueError('USB successor control type is fixed')
    return core.execute(*args, **kwargs, control_type=Control)


def sources(store):
    for path, sha in ((ROOT / 'Tools/ota/p34_boot16_display.py',
                      'c3388afb566f35ede0bc42031b1222807ae94ca798cadc3859bf92fdaff2f9c8'),
                     (ROOT / 'Tools/ota/recovery_confirm/boot16_display_entry.py',
                      '0f558cf18c4dfebf27f753ab58c87308b46c07650d1716e807569970123978b6')):
        cli.require(cli.record(path)['sha256'] == sha, 'frozen display predecessor changed')
    result = store.read(FAILED / 'worker.json')
    cli.require(result['result'] == 'FAILED' and result['mutation_attempted'] is False and result['close_returned'],
                'closed zero-mutation USB predecessor required')
    snapshot = ROOT / '.cache/p34-early-usb-r2/f/MDK-ARM_F435/Platform/middlewares/usb_drivers/src'
    config = ROOT / '.cache/p34-early-usb-r2/f/Libraries/USB_MSC'
    return sorted(set([*previous.sources(store), SELF, ROOT / 'Tools/ota/recovery_confirm/boot16_usb_entry.py',
        ROOT / 'tests/boot/test_p34_boot16_usb.py', *(snapshot / name for name in ('usbd_int.c', 'usbd_sdr.c', 'usbd_core.c')),
        *(config / name for name in ('usb_conf.h', 'UsbMsc.h', 'UsbMsc.cpp')),
        *sorted((snapshot.parent / 'inc').glob('*.h')),
        *(FAILED / name for name in ('worker.json', 'parent.json', 'plan.json', 'sdk-000.log', 'sdk-001.log', 'events.jsonl')),
        ROOT / '.cache/p34-boot16-entry-probe2-analysis1/result.json']))


worker = FunctionType(core.worker.__code__, dict(core.worker.__globals__, sources=sources, execute=execute),
                      'worker', core.worker.__defaults__, core.worker.__closure__)


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
    core.preflight(store, out, inputs)
    records = [cli.record(p) for p in inputs]
    if args.action == 'capture':
        tested = store.read(args.tests)
        cli.require(tested['result'] == 'BOOT16_USB_HOST_PASS' and tested['inputs'] == records, 'USB successor tests required')
        cli.require(args.native_history_approved == base.HISTORY, 'exact native history approval required')
        before = base.history(store)
    env = host.environment(store, out)
    for path in inputs: store.raw(out / 'source' / path.relative_to(ROOT), path.read_bytes())
    if args.action == 'selftest':
        raw = host.command(store, out, 'tests', [sys.executable, '-I', '-S', '-B', '-X', 'utf8',
            ROOT / 'tests/boot/test_p34_boot16_usb.py', '-v'], env, 120)
        count = re.search(rb'Ran (\d+) tests? in .*\r?\n\r?\nOK\b', raw)
        cli.require(count and records == [cli.record(p) for p in inputs], 'USB successor test/source drift')
        store.write(out / 'result.json', dict(result='BOOT16_USB_HOST_PASS', tests=int(count[1]),
            inputs=records, hardware=False, independent_acceptance=False))
        print('BOOT16_USB_HOST_PASS', int(count[1]), flush=True)
        return 0
    store.write(out / 'plan.json', dict(out=str(out), inputs=records, tests=cli.record(args.tests),
        native_history_approved=str(base.HISTORY), before_history=before, worker_seconds=core.WORKER_SECONDS,
        parent_seconds=core.PARENT_SECONDS, predecessor=cli.record(FAILED / 'worker.json'),
        boot_writes=0, eeprom_writes=0, nor_writes=0, reset_commands=0,
        scope='exact USB suspended-default104/MSC0 exception; existing display/R2 same-context qualification; no Boot write'))
    value = base.owned_run(store, out, [SELF, 'worker', '--output-dir', out], env, timeout=core.PARENT_SECONDS)
    value.update(after_history=base.history(store), presence_after=base.native_presence())
    store.write(out / 'parent.json', value)
    print(json.dumps(value), flush=True)
    return 0 if value['exit'] == 0 and not value['timeout'] else 1


if __name__ == '__main__': raise SystemExit(main())
