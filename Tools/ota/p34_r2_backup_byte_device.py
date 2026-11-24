"""Continue only the failed pre-NOR qualification with byte-wide display DMA."""
import argparse
import ctypes
import os
from pathlib import Path
import re
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'Tools/ota'))
import p34_r2_backup_device as prior
from recovery_confirm import r2_mapped_backup_byte as byte

cli, host, base = prior.cli, prior.host, prior.base
owner, component = prior.owner, prior.component
mapped = SimpleNamespace(**dict(vars(prior.mapped), Capture=byte.Capture))
execute = byte.bind(prior.execute, mapped=mapped)
audit_trace = prior.audit_trace
LOGS, SCOPE, WORKER_SECONDS, PARENT_SECONDS = prior.LOGS, prior.SCOPE, prior.WORKER_SECONDS, prior.PARENT_SECONDS
SELF = Path(__file__).resolve()
TEST = ROOT/'tests/boot/test_p34_r2_backup_byte_device.py'
PRIOR_TESTS = ROOT/'.cache/p34-r2-backup-device-tests2/result.json'
FAILED = ROOT/'.cache/p34-r2-backup1'
REVIEW = ROOT/'.cache/p34-r2-backup1-independent-review1/result.json'
REVIEW_SHA = '86ac6ec2f69d0d1d47e443c105fae827c1e2140118a03070015f53625c365e53'


def predecessor(store):
    proof = prior.predecessor(store)
    cli.require(cli.record(REVIEW)['sha256'] == REVIEW_SHA, 'fixed failed-prefix review required')
    reviewed = store.read(REVIEW)
    for item in (*reviewed['original_inputs'], *reviewed['source_inputs'], reviewed['script']):
        cli.require(cli.record(store.checked(item['path'])) == item, 'failed-prefix evidence changed')
    parent, worker = (store.read(FAILED/(n+'.json')) for n in ('parent', 'worker'))
    cli.require(parent['exit'] == 1 and parent['timeout'] is False and not parent['presence_after']['debugger_processes'] and
        worker['result'] == 'FAILED' and worker['close_returned'] is True and worker['archives'] == {} and
        worker['sources_unchanged_after_close'] is True and
        worker['error'] == 'ValueError: active DMA may access non-SRAM/non-display/SD endpoint' and
        all(worker['dap'][k] for k in ('tar_restored', 'csw_restored', 'dp_restored')),
        'only the diagnosed closed pre-NOR failure may continue')
    return dict(original=proof, failed_prefix_review=cli.record(REVIEW),
                failed_worker=cli.record(FAILED/'worker.json'), failed_parent=cli.record(FAILED/'parent.json'),
                reason='source-known byte-wide display DMA accepts odd in-SRAM continuation',
                repeat_successful_nor_capture=False)


def sources(store):
    paths = prior.sources(store)
    tested = store.read(PRIOR_TESTS)
    cli.require(tested['result'] == 'R2_BACKUP_DEVICE_HOST_PASS' and
                tested['inputs'] == [cli.record(p) for p in paths], 'current original owner tests required')
    return list(dict.fromkeys([*paths, SELF, TEST, Path(byte.__file__), PRIOR_TESTS, REVIEW,
                              *(FAILED/(n+'.json') for n in ('plan', 'worker', 'parent'))]))


def validate_worker_plan(*args):
    return byte.bind(prior.validate_worker_plan, predecessor=predecessor)(*args)


def worker(*args):
    return byte.bind(prior.worker, execute=execute, sources=sources, mapped=mapped,
                     validate_worker_plan=validate_worker_plan)(*args)


def capture_main():
    return byte.bind(prior.main, SELF=SELF, sources=sources, predecessor=predecessor, worker=worker)()


def main():
    if len(sys.argv) < 2 or sys.argv[1] != 'selftest': return capture_main()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('selftest',))
    parser.add_argument('--output-dir', type=Path, required=True)
    a = parser.parse_args()
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                'isolated explicit root required')
    store = cli.Store(ROOT)
    out = store.checked(a.output_dir)
    paths = sources(store)
    prior.preflight(store, out, paths)
    records = [cli.record(p) for p in paths]
    env = host.environment(store, out)
    for path in paths: store.raw(out/'source'/path.relative_to(ROOT), path.read_bytes())
    log = host.command(store, out, 'tests', [sys.executable, '-I', '-S', '-B', '-X', 'utf8', TEST, '-v'], env, 180)
    count = re.search(rb'Ran (\d+) tests? in .*\r?\n\r?\nOK\b', log)
    cli.require(count and records == [cli.record(p) for p in paths], 'byte-display test/source drift')
    store.write(out/'result.json', dict(result='R2_BACKUP_DEVICE_HOST_PASS', tests=int(count[1]), inputs=records,
        hardware=False, byte_display_successor=True, failed_prefix_review=cli.record(REVIEW)))
    print('R2_BACKUP_DEVICE_HOST_PASS byte-display', int(count[1]))
    return 0


if __name__ == '__main__': raise SystemExit(main())
