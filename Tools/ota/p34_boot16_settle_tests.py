"""Host-only controller settlement tests for a future Boot restoration entry."""
import argparse
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'Tools/ota'))
import p34_boot16_tests as prior
cli, host = prior.cli, prior.host


def main():
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                'isolated explicit root required')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', required=True, type=Path)
    store = cli.Store(ROOT)
    out = store.checked(parser.parse_args().output_dir)
    cli.require(not out.exists(), 'preserve settlement tests')
    sources = [*prior.sources(), Path(__file__), ROOT / 'Tools/ota/recovery_confirm/boot16_settle.py',
               ROOT / 'tests/boot/test_p34_boot16_settle.py']
    for path in sources: store.checked(out / 'source' / path.relative_to(ROOT))
    for name in ('tests.log', 'tests.json', 'result.json'): store.checked(out / name)
    for key in ('HOME', 'USERPROFILE', 'APPDATA', 'LOCALAPPDATA', 'TEMP', 'TMP', 'TMPDIR',
                'XDG_CACHE_HOME', 'XDG_CONFIG_HOME', 'XDG_DATA_HOME', 'PYTHONUSERBASE',
                'PYTHONPYCACHEPREFIX', 'CCACHE_DIR', 'SCCACHE_DIR'):
        store.checked(out / 'host' / key.lower())
    records = [cli.record(p) for p in sources]
    env = host.environment(store, out)
    for path in sources: store.raw(out / 'source' / path.relative_to(ROOT), path.read_bytes())
    raw = host.command(store, out, 'tests', [sys.executable, '-I', '-S', '-B', '-X', 'utf8',
        ROOT / 'tests/boot/test_p34_boot16_settle.py', '-v'], env, 60)
    count = re.search(rb'Ran (\d+) tests? in .*\r?\n\r?\nOK\b', raw)
    cli.require(count and records == [cli.record(p) for p in sources], 'settlement test/source drift')
    store.write(out / 'result.json', dict(result='BOOT16_SETTLEMENT_HOST_PASS', tests=int(count[1]),
        inputs=records, device_operations=0, hardware=False, device_entry=False))
    print('BOOT16_SETTLEMENT_HOST_PASS', int(count[1]), flush=True)


if __name__ == '__main__': main()
