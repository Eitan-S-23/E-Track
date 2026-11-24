"""Source-bound HOST_ONLY tests for separately scoped native recovery adapters."""
import argparse
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'Tools/ota'))
import p34_install_cost as host


def main():
    cli = host.cli
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                'isolated root required')
    store = cli.Store(ROOT)
    out = store.checked(args.output_dir)
    cli.require(not out.exists(), 'preserve prior port evidence')
    page = ROOT/'.cache/p34-confirm-page2/result.json'
    reused = store.read(page)
    for item in reused['inputs']+[reused['dll'],reused['compiler']]:
        cli.require(cli.record(item['path']) == item, 'confirmation model source/artifact drift')
    inputs = [Path(__file__), page, Path(reused['dll']['path'])]
    inputs += [ROOT/name for name in (
        'Tools/ota/recovery_confirm/native_io.py', 'Tools/ota/recovery_confirm/gpio_page.py',
        'Tools/ota/recovery_confirm/eeprom_page.py', 'tests/boot/test_p34_recovery_ports.py',
        'Tools/ota/recovery_confirm/flash_port.py', 'Tools/ota/recovery_confirm/flash_plan.py',
        'Tools/ota/recovery_confirm/boot_exit.py', 'Tools/ota/recovery_confirm/confirm_io.py',
        '.cache/p34-finalized-reader-device1/readback.bin',
        '.cache/p34-bc-target/f/vendor/AT32F435_437_DFP/Peripherals/inc/at32f435_437_flash.h',
        '.cache/p34-bc-target/f/MDK-ARM_F435/RTE/Device/-AT32F435RGT7/at32f435_437_flash.c',
        '.cache/p34-bc-target/b1/compile_commands.json',
        'tests/boot/p34_eeprom_wire_model.py', 'Tools/ota/p34_install_cost.py', 'Tools/ota/p34_session.py',
        '.agents/skills/e-track-flutter-debug/scripts/host_io.py',
        'Tools/ota/recovery_entry/native_probe.py', 'Tools/ota/recovery_entry/probe.py')]
    inputs += [Path(item['path']) for item in reused['inputs']]
    inputs = list(dict.fromkeys(inputs))
    for p in inputs: store.checked(out/'source'/p.relative_to(ROOT))
    for name in ('tests.log','tests.json','result.json'): store.checked(out/name)
    for key in ('HOME','USERPROFILE','APPDATA','LOCALAPPDATA','TEMP','TMP','TMPDIR','XDG_CACHE_HOME',
                'XDG_CONFIG_HOME','XDG_DATA_HOME','PYTHONUSERBASE','PYTHONPYCACHEPREFIX','CCACHE_DIR','SCCACHE_DIR'):
        store.checked(out/'host'/key.lower())
    records = [cli.record(p) for p in inputs]
    env = host.environment(store, out)
    env['P34_CONFIRM_DLL'] = reused['dll']['path']
    for p in inputs: store.raw(out/'source'/p.relative_to(ROOT), p.read_bytes())
    log = host.command(store,out,'tests',[sys.executable,'-I','-S','-B','-X','utf8',
        ROOT/'tests/boot/test_p34_recovery_ports.py','-v'],env,180)
    count = re.search(rb'Ran (\d+) tests? in .*\r?\n\r?\nOK\b',log)
    cli.require(count and records == [cli.record(p) for p in inputs], 'test/source binding')
    store.write(out/'result.json',dict(result='RECOVERY_PORTS_HOST_PASS',tests=int(count[1]),inputs=records,
        hardware=False,device_entry=False,confirmation_dll_reused=reused['dll'],
        scope='EEPROM protocol/native AP/GPIO and two-bank Flash via injected SDK/storage only'))
    print('RECOVERY_PORTS_HOST_PASS tests='+str(int(count[1])))


if __name__ == '__main__': main()
