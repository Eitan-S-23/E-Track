"""Contained checkpoint component tests, without a device entry or native load."""
import argparse
from pathlib import Path
import re
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'Tools/ota'))
import p34_r2_health_tests as prior


def sources(store):
    return list(dict.fromkeys([*prior.sources(store),Path(__file__),*(ROOT/n for n in (
        'Tools/ota/recovery_confirm/r2_checkpoint.py','Tools/ota/recovery_confirm/r2_paired_health.py',
        'Tools/ota/recovery_entry/finalized_reader.py','Tools/ota/p34_finalized_vtor_capture.py',
        'Tools/ota/p34_finalized_vtor.py','Tools/ota/recovery_confirm/boot_exit.py',
        'tests/boot/test_p34_r2_checkpoint.py','tests/boot/test_p34_install_bridges.py',
        'tests/boot/test_p34_recovery_ports.py','.cache/p34-r2-paired-health-tests2/result.json'))]))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,required=True)
    args=parser.parse_args()
    host=prior.host;cli=host.cli
    cli.require(Path.cwd()==ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,'isolated root required')
    store=cli.Store(ROOT);out=store.checked(args.output_dir);inputs=sources(store)
    prior.prior.preflight(store,out,inputs)
    records=[cli.record(p) for p in inputs]
    env=host.environment(store,out)
    for path in inputs:store.raw(out/'source'/path.relative_to(ROOT),path.read_bytes())
    log=host.command(store,out,'tests',[sys.executable,'-I','-S','-B','-X','utf8',
        ROOT/'tests/boot/test_p34_r2_checkpoint.py','-v'],env,180)
    count=re.search(rb'Ran (\d+) tests? in .*\r?\n\r?\nOK\b',log)
    cli.require(count and records==[cli.record(p) for p in inputs],'checkpoint test/source drift')
    store.write(out/'result.json',dict(result='R2_CHECKPOINT_COMPONENT_HOST_PASS',tests=int(count[1]),
        inputs=records,hardware=False,device_entry_implemented=False))
    print('R2_CHECKPOINT_COMPONENT_HOST_PASS',int(count[1]))


if __name__=='__main__':main()
