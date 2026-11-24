"""Source-bound Boot16 coordinator host checks; no device CLI."""
import argparse
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'Tools/ota'))
import p34_boot16_usb as prior
cli, host = prior.cli, prior.host


def sources(store):
    test = ROOT / 'tests/boot/test_p34_boot16_program.py'
    cli.load_module('boot16_program_model', test)
    cli.load_module('boot16_program_entry', ROOT / 'Tools/ota/p34_boot16_program.py')
    return sorted(set([*prior.sources(store), Path(__file__).resolve(), test,
        ROOT / 'Tools/ota/recovery_confirm/boot16_archive.py',
        ROOT / 'Tools/ota/recovery_confirm/boot16_owner.py',
        ROOT / 'Tools/ota/recovery_confirm/boot16_program.py',
        ROOT / 'Tools/ota/recovery_confirm/boot16_settle.py',
        ROOT / 'tests/boot/test_p34_boot16_settle.py',
        ROOT / 'tests/boot/test_p34_boot16_archive.py',
        ROOT / 'Tools/ota/p34_boot16_program.py',
        ROOT / '.cache/p34-boot16-entry-probe3/worker.json',
        ROOT / '.cache/p34-bc-target/b16/boot/X-Track-Boot.bin']))


def main():
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                'isolated explicit root required')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', required=True, type=Path)
    store = cli.Store(ROOT)
    out = store.checked(parser.parse_args().output_dir)
    cli.require(not out.exists(), 'preserve Boot16 coordinator tests')
    inputs = sources(store)
    for path in inputs: store.checked(out / 'source' / path.relative_to(ROOT))
    for name in ('tests.log', 'tests.json', 'result.json'): store.checked(out / name)
    store.checked(out / 'archive-tests')
    for key in ('HOME', 'USERPROFILE', 'APPDATA', 'LOCALAPPDATA', 'TEMP', 'TMP', 'TMPDIR',
                'XDG_CACHE_HOME', 'XDG_CONFIG_HOME', 'XDG_DATA_HOME', 'PYTHONUSERBASE',
                'PYTHONPYCACHEPREFIX', 'CCACHE_DIR', 'SCCACHE_DIR'):
        store.checked(out / 'host' / key.lower())
    records = [cli.record(p) for p in inputs]
    env = host.environment(store, out)
    env['P34_BOOT16_TEST_OUT'] = str(out / 'archive-tests')
    for path in inputs: store.raw(out / 'source' / path.relative_to(ROOT), path.read_bytes())
    raw = host.command(store, out, 'tests', [sys.executable, '-I', '-S', '-B', '-X', 'utf8',
        ROOT / 'tests/boot/test_p34_boot16_program.py', '-v'], env, 360)
    count = re.search(rb'Ran (\d+) tests? in .*\r?\n\r?\nOK\b', raw)
    cli.require(count and records == [cli.record(p) for p in inputs], 'coordinator test/source drift')
    store.write(out / 'result.json', dict(result='BOOT16_PROGRAM_HOST_PASS', tests=int(count[1]),
        inputs=records, hardware=False, device_entry=False, independent_acceptance=False))
    print('BOOT16_PROGRAM_HOST_PASS', int(count[1]), flush=True)


if __name__ == '__main__': main()
