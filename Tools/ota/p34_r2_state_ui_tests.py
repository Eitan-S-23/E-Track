"""Contained real passive/UI word-port integration tests; no native device load."""
import argparse
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'Tools/ota'))
import p34_r2_passive_state_tests as prior


def sources(store):
    paths = prior.sources(store)
    receipt = ROOT / '.cache/p34-r2-ui-binding-tests1/result.json'
    value = store.read(receipt)
    cli = prior.prior.prior.host.cli
    cli.require(value['result'] == 'R2_UI_BINDING_HOST_PASS', 'UI binding tests required')
    for item in value['inputs']:
        cli.require(cli.record(item['path']) == item, 'UI binding source drift')
        paths.append(Path(item['path']))
    return list(dict.fromkeys([*paths, Path(__file__).resolve(), receipt,
        ROOT / 'Tools/ota/recovery_confirm/r2_state_ui.py', ROOT / 'tests/boot/test_p34_r2_state_ui.py']))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    host = prior.prior.prior.host
    cli = host.cli
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                'isolated root required')
    store = cli.Store(ROOT)
    out = store.checked(args.output_dir)
    paths = sources(store)
    prior.prior.prior.prior.preflight(store, out, paths)
    if args.check_only:
        print('PASSIVE_UI_PREFLIGHT_PASS'); return
    records = [cli.record(p) for p in paths]
    env = host.environment(store, out)
    for path in paths: store.raw(out / 'source' / path.relative_to(ROOT), path.read_bytes())
    log = host.command(store, out, 'tests', [sys.executable, '-I', '-S', '-B', '-X', 'utf8',
        ROOT / 'tests/boot/test_p34_r2_state_ui.py', '-v'], env, 120)
    count = re.search(rb'Ran (\d+) tests? in .*\r?\n\r?\nOK\b', log)
    cli.require(count and records == [cli.record(p) for p in paths], 'passive/UI test/source drift')
    store.write(out / 'result.json', dict(result='R2_PASSIVE_UI_HOST_PASS', tests=int(count[1]),
        inputs=records, hardware=False, mapped_nor_read_implemented=False))
    print('R2_PASSIVE_UI_HOST_PASS', int(count[1]))


if __name__ == '__main__': main()
