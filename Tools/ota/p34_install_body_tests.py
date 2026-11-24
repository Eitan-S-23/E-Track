"""Contained body orchestration tests, not physical installation admission."""
import argparse
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'Tools/ota'))
import p34_r2_health_tests as health
import p34_nor_capture_tests as nor
import p34_eeprom_sequence_tests as eeprom
import p34_flash_sequence_tests as flash
import p34_held_window_tests as window
import p34_read_pair_tests as pair
import p34_gpio_read_device as entry
import p34_failed_install_audit as failed_entry
host = health.host


def sources(store):
    inputs = [path for module in (health,nor,eeprom,flash,window,pair,entry) for path in module.sources(store)]
    inputs += [Path(__file__),ROOT/'tests/boot/test_p34_install_body.py',ROOT/'Tools/ota/recovery_confirm/install.py',
               *(ROOT/'.cache/p34-host-nor-rebuild1'/('after-'+name+'.bin') for name in ('candidate-backup','tail','staging')),
               ROOT/'Tools/ota/recovery_entry/control_probe.py',ROOT/'Tools/ota/recovery_entry/rendezvous.py',
               ROOT/'Tools/ota/recovery_entry/owner_probe.py',ROOT/'Tools/ota/recovery_entry/state_probe.py',
               ROOT/'tests/boot/test_p34_install_bridges.py',ROOT/'Tools/ota/p34_install_recovery.py',
               ROOT/'Tools/ota/recovery_confirm/install_entry.py',ROOT/'Tools/ota/p34_failed_install_audit.py',
               ROOT/'tests/boot/test_p34_install_entry.py']
    return list(dict.fromkeys([*inputs,*failed_entry.INPUTS,failed_entry.RECEIPT]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,required=True)
    args = parser.parse_args()
    cli = host.cli
    cli.require(Path.cwd()==ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,'isolated root required')
    store = cli.Store(ROOT)
    out = store.checked(args.output_dir)
    inputs = sources(store)
    health.prior.preflight(store,out,inputs)
    store.checked(out/'model-only.jlink')
    records = [cli.record(p) for p in inputs]
    env = host.environment(store,out)
    env['P34_CONFIRM_DLL'] = store.read(ROOT/'.cache/p34-confirm-page2/result.json')['dll']['path']
    env['P34_TEST_OUT'] = str(out)
    for path in inputs: store.raw(out/'source'/path.relative_to(ROOT),path.read_bytes())
    log = host.command(store,out,'tests',[sys.executable,'-I','-S','-B','-X','utf8',
        ROOT/'tests/boot/test_p34_install_body.py','-v'],env,180)
    match = re.search(rb'Ran (\d+) tests? in .*\r?\n\r?\nOK\b',log)
    cli.require(match and records==[cli.record(p) for p in inputs],'body test/source drift')
    store.write(out/'result.json',dict(result='INSTALL_BODY_HOST_PASS',tests=int(match[1]),inputs=records,
        hardware=False,full_install_qualified=False))
    print('INSTALL_BODY_HOST_PASS tests='+str(int(match[1])))


if __name__=='__main__': main()
