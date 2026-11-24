"""Contained host tests for segmented C-derived confirmation; no device entry."""
import argparse
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'Tools/ota'))
import p34_mutation_audit_tests as prior
host = prior.host


def sources(store):
    return list(dict.fromkeys([*prior.sources(store),Path(__file__),
        ROOT/'Tools/ota/recovery_confirm/eeprom_sequence.py',ROOT/'tests/boot/test_p34_eeprom_sequence.py',
        ROOT/'Tools/ota/recovery_confirm/online_log.py',ROOT/'tests/boot/test_p34_online_log.py']))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,required=True)
    args = parser.parse_args()
    cli = host.cli
    cli.require(Path.cwd()==ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,'isolated root required')
    store = cli.Store(ROOT)
    out = store.checked(args.output_dir)
    inputs = sources(store)
    prior.preflight(store,out,inputs)
    records = [cli.record(p) for p in inputs]
    env = host.environment(store,out)
    env['P34_CONFIRM_DLL'] = store.read(ROOT/'.cache/p34-confirm-page2/result.json')['dll']['path']
    for path in inputs: store.raw(out/'source'/path.relative_to(ROOT),path.read_bytes())
    log = host.command(store,out,'tests',[sys.executable,'-I','-S','-B','-X','utf8',
        ROOT/'tests/boot/test_p34_eeprom_sequence.py','-v'],env,120)
    match = re.search(rb'Ran (\d+) tests? in .*\r?\n\r?\nOK\b',log)
    cli.require(match and records==[cli.record(p) for p in inputs],'EEPROM sequence test/source drift')
    store.write(out/'result.json',dict(result='EEPROM_SEQUENCE_HOST_PASS',tests=int(match[1]),inputs=records,
        hardware=False,full_install_qualified=False))
    print('EEPROM_SEQUENCE_HOST_PASS tests='+str(int(match[1])))


if __name__=='__main__': main()
