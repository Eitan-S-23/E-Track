"""Source-bound paired health self-tests only; no native DLL or device entry."""
import argparse
from pathlib import Path
import re
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'Tools/ota'))
import p34_r2_health_tests as old


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,required=True)
    args=parser.parse_args()
    host=old.host;cli=host.cli
    cli.require(Path.cwd()==ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,'isolated root required')
    store=cli.Store(ROOT);out=store.checked(args.output_dir)
    inputs=list(dict.fromkeys([*old.sources(store),Path(__file__),ROOT/'Tools/ota/p34_r2_health_tests.py',
        ROOT/'Tools/ota/recovery_confirm/r2_paired_health.py',ROOT/'tests/boot/test_p34_r2_paired_health.py',
        ROOT/'Tools/ota/p34_finalized_vtor_capture.py',ROOT/'Tools/ota/p34_finalized_vtor.py']))
    old.prior.preflight(store,out,inputs)
    records=[cli.record(p) for p in inputs]
    env=host.environment(store,out)
    for p in inputs:store.raw(out/'source'/p.relative_to(ROOT),p.read_bytes())
    log=host.command(store,out,'tests',[sys.executable,'-I','-S','-B','-X','utf8',
        ROOT/'tests/boot/test_p34_r2_paired_health.py','-v'],env,120)
    count=re.search(rb'Ran (\d+) tests? in .*\r?\n\r?\nOK\b',log)
    cli.require(count and records==[cli.record(p) for p in inputs],'paired tests/source drift')
    store.write(out/'result.json',dict(result='R2_PAIRED_HEALTH_HOST_PASS',tests=int(count[1]),
        inherited_case_invocations=10,inputs=records,hardware=False,checkpoint_entry_implemented=False))
    print('R2_PAIRED_HEALTH_HOST_PASS',int(count[1]))


if __name__=='__main__':main()
