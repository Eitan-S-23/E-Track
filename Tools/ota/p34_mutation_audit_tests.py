"""Contained host validation of online segment audit; never a device runner."""
import argparse
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'Tools/ota'))
import p34_install_cost as host


def sources(store):
    paths = [Path(__file__), ROOT/'Tools/ota/recovery_confirm/mutation_audit.py',
             ROOT/'tests/boot/test_p34_mutation_audit.py', ROOT/'.cache/p34-recovery-ports3/result.json',
             ROOT/'.cache/p34-recovery-preflight1/envelope.bin',
             ROOT/'Tools/ota/recovery_confirm/ap_journal.py', ROOT/'Tools/ota/p34_nor_audit.py']
    ports = store.read(ROOT/'.cache/p34-recovery-ports3/result.json')
    host.cli.require(ports['result'] == 'RECOVERY_PORTS_HOST_PASS', 'original port model required')
    for record in ports['inputs']:
        host.cli.require(host.cli.record(record['path']) == record, 'port model dependency drift')
        paths.append(Path(record['path']))
    return list(dict.fromkeys(paths))


def preflight(store, out, inputs):
    host.cli.require(not out.exists(), 'preserve mutation-audit evidence')
    for path in inputs: store.checked(out/'source'/path.relative_to(ROOT))
    for name in ('tests.json', 'tests.log', 'result.json'): store.checked(out/name)
    for key in ('HOME', 'USERPROFILE', 'APPDATA', 'LOCALAPPDATA', 'TEMP', 'TMP', 'TMPDIR',
                'XDG_CACHE_HOME', 'XDG_CONFIG_HOME', 'XDG_DATA_HOME', 'PYTHONUSERBASE',
                'PYTHONPYCACHEPREFIX', 'CCACHE_DIR', 'SCCACHE_DIR'):
        store.checked(out/'host'/key.lower())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    cli = host.cli
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                'isolated root required')
    store = cli.Store(ROOT)
    out = store.checked(args.output_dir)
    inputs = sources(store)
    preflight(store, out, inputs)
    records = [cli.record(p) for p in inputs]
    env = host.environment(store, out)
    for path in inputs: store.raw(out/'source'/path.relative_to(ROOT), path.read_bytes())
    log = host.command(store, out, 'tests', [sys.executable, '-I', '-S', '-B', '-X', 'utf8',
                       ROOT/'tests/boot/test_p34_mutation_audit.py', '-v'], env, 180)
    match = re.search(rb'Ran (\d+) tests? in .*\r?\n\r?\nOK\b', log)
    cli.require(match and records == [cli.record(p) for p in inputs], 'test/source drift')
    store.write(out/'result.json', dict(result='MUTATION_AUDIT_HOST_PASS', tests=int(match[1]),
                                      inputs=records, hardware=False, mutation_admitted=False))
    print('MUTATION_AUDIT_HOST_PASS tests='+str(int(match[1])))


if __name__ == '__main__': main()
