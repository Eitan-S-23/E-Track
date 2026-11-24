"""Contained exact-R2 passive monitor tests; never release a device."""
import argparse
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'Tools/ota'))
import p34_mutation_audit_tests as prior
host = prior.host


def sources(store):
    receipt = ROOT/'.cache/p34-recovery-sources1/result.json'
    bound = store.read(receipt)
    for item in bound['inputs']+bound['outputs']:
        host.cli.require(host.cli.record(item['path'])==item,'finalized R2 asset/source drift')
    return list(dict.fromkeys([*prior.sources(store),Path(__file__),receipt,
        *(Path(item['path']) for item in bound['inputs']+bound['outputs']),
        *(ROOT/name for name in ('Tools/ota/recovery_confirm/r2_health.py',
        'Tools/ota/recovery_confirm/online_log.py','tests/boot/test_p34_online_log.py','tests/boot/test_p34_r2_health.py',
        '.cache/p34-early-usb-r2/f/USER/main.cpp','.cache/p34-early-usb-r2/f/Libraries/OTA/ota_confirm_health.h',
        '.cache/p34-early-usb-r2/f/Libraries/OTA/ota_confirm_health.c',
        '.cache/p34-early-usb-r2/f/MDK-ARM_F435/Platform/Core/delay.c'))]))


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
    for path in inputs: store.raw(out/'source'/path.relative_to(ROOT),path.read_bytes())
    log = host.command(store,out,'tests',[sys.executable,'-I','-S','-B','-X','utf8',
        ROOT/'tests/boot/test_p34_r2_health.py','-v'],env,120)
    match = re.search(rb'Ran (\d+) tests? in .*\r?\n\r?\nOK\b',log)
    cli.require(match and records==[cli.record(p) for p in inputs],'R2 monitor test/source drift')
    store.write(out/'result.json',dict(result='R2_HEALTH_HOST_PASS',tests=int(match[1]),inputs=records,
        hardware=False,full_install_qualified=False))
    print('R2_HEALTH_HOST_PASS tests='+str(int(match[1])))


if __name__=='__main__': main()
