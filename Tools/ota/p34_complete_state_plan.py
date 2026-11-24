"""Contained HOST_ONLY R2-A geometry, preservation and original Boot branch tests."""
import argparse
from dataclasses import asdict
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'Tools/ota'))
import p34_install_cost as host
from recovery_confirm.flash_plan import geometry


def records_in(value):
    if isinstance(value, dict):
        if set(value) == {'path', 'bytes', 'sha256'}:
            yield value
        for item in value.values():
            yield from records_in(item)
    elif isinstance(value, list):
        for item in value:
            yield from records_in(item)


def main():
    cli = host.cli
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and
                sys.dont_write_bytecode, 'isolated explicit root required')
    store = cli.Store(ROOT)
    out = store.checked(args.output_dir)
    cli.require(not out.exists(), 'preserve earlier model evidence')
    boot = ROOT / '.cache/p34-bc-target/f'
    app = ROOT / '.cache/p34-early-usb-r2/f'
    component = ROOT / 'Tools/ota/recovery_confirm'
    flash_header = boot/'vendor/AT32F435_437_DFP/Peripherals/inc/at32f435_437_flash.h'
    flash_source = boot/'MDK-ARM_F435/RTE/Device/-AT32F435RGT7/at32f435_437_flash.c'
    compile_commands = boot.parent/'b1/compile_commands.json'
    flash_commands = [item for item in store.read(compile_commands)
                      if Path(item['file']).resolve() == flash_source.resolve()
                      and 'X_Track_Boot.dir' in item['command']]
    cli.require(len(flash_commands) == 1 and
                '-DAT32F435RGT7' in flash_commands[0]['command'].split(), 'RGT7 Boot compile definition missing')
    page_receipt = ROOT / '.cache/p34-confirm-page2/result.json'
    tested = store.read(page_receipt)
    cli.require(tested['result'] == 'HOST_ONLY_CONFIRM_PAGE_MODEL_PASS', 'page model prerequisite')
    for item in tested['inputs'] + [tested['dll'], tested['compiler']]:
        cli.require(cli.record(item['path']) == item, 'page source/artifact drift')
    cli.require((boot/'Libraries/EEPROM/eeprom_bcb.h').read_bytes().replace(b'\r\n', b'\n') ==
                (app/'Libraries/EEPROM/eeprom_bcb.h').read_bytes().replace(b'\r\n', b'\n'), 'BCB header mismatch')
    physical = ROOT / '.cache/p34-host-nor-rebuild1'
    read_cell = ROOT / '.cache/p34-finalized-reader-device1'
    images = [ROOT/'.cache/p34-native-acquire1/boot-readback.bin',
              ROOT/'.cache/p34-native-image1/app-readback.bin',
              ROOT/'.cache/p34-recovery-sources1/r2-a.bin', physical/'bcb-before.bin',
              physical/'after-candidate-backup.bin', physical/'after-recovery.bin',
              physical/'after-tail.bin', read_cell/'readback.bin']
    receipts = [physical/'worker.json', read_cell/'worker.json']
    recorded = tested['inputs'] + [r for p in receipts for r in records_in(store.read(p))]
    for p in images:
        cli.require(cli.record(p) in recorded, 'archive not bound by original receipt: '+str(p))
    sources = [ROOT/'tests/boot/p34_complete_state_boot_host.c', component/'confirm.c']
    sources += [boot/'boot/src'/n for n in
                ('boot_state_machine.c', 'boot_fw_header.c', 'boot_crc32.c', 'boot_sha256.c', 'boot_slot.c')]
    sources += [boot/'Libraries/EEPROM/eeprom_bcb.c']
    inputs = [Path(p) for p in dict.fromkeys([item['path'] for item in tested['inputs']] +
              list(map(str, sources+images+receipts+[page_receipt, Path(__file__), component/'flash_plan.py',
              ROOT/'tests/boot/test_p34_complete_state_plan.py', ROOT/'Tools/ota/p34_install_cost.py',
              ROOT/'Tools/ota/p34_session.py', ROOT/'.agents/skills/e-track-flutter-debug/scripts/host_io.py',
              boot/'boot/platform/at32/boot_platform_at32.c', flash_header, flash_source, compile_commands])))]
    for p in inputs:
        store.checked(out/'source'/p.relative_to(ROOT))
    for name in ('boot-model.exe', 'compile.log', 'compile.json', 'boot.log', 'boot.json',
                 'tests.log', 'tests.json', 'result.json'):
        store.checked(out/name)
    for key in ('HOME', 'USERPROFILE', 'APPDATA', 'LOCALAPPDATA', 'TEMP', 'TMP', 'TMPDIR',
                'XDG_CACHE_HOME', 'XDG_CONFIG_HOME', 'XDG_DATA_HOME', 'PYTHONUSERBASE',
                'PYTHONPYCACHEPREFIX', 'CCACHE_DIR', 'SCCACHE_DIR'):
        store.checked(out/'host'/key.lower())
    inputs_before = [cli.record(p) for p in inputs]
    env = host.environment(store, out)
    for p in inputs:
        store.raw(out/'source'/p.relative_to(ROOT), p.read_bytes())
    cc = Path(tested['compiler']['path'])
    compiler = cli.record(cc)
    compile_log = host.command(store, out, 'compile', [cc, '-std=c99', '-O2', '-Wall', '-Wextra', '-Werror',
        '-DRR_CONFIRM_HOST_ONLY', '-I'+str(component), '-I'+str(boot/'boot/include'),
        '-I'+str(app/'Libraries'), *sources, '-o', out/'boot-model.exe'], env, 90)
    test_log = host.command(store, out, 'tests', [sys.executable, '-I', '-S', '-B', '-X', 'utf8',
        ROOT/'tests/boot/test_p34_complete_state_plan.py', '-v'], env, 90)
    count = re.search(rb'Ran (\d+) tests? in .*\r?\n\r?\nOK\b', test_log)
    cli.require(count is not None, 'test count missing')
    boot_log = host.command(store, out, 'boot', [out/'boot-model.exe', *images], env, 180)
    cli.require(b'COMPLETE_STATE_BOOT_HOST_PASS hardware=0 reset_qualified=0' in boot_log, 'Boot model oracle missing')
    cli.require(inputs_before == [cli.record(p) for p in inputs] and compiler == cli.record(cc), 'model input drift')
    image = images[2].read_bytes()
    sectors = geometry(image).sectors
    store.write(out/'result.json', dict(result='HOST_ONLY_COMPLETE_STATE_PLAN_PASS', tests=int(count[1]),
        model_interruption_boundaries=606, isolated_sector_erase_cases=303,
        minimal_envelope=asdict(geometry(image)), existing_boot_4k_envelope=asdict(geometry(image, unit=4096)),
        bank1_sectors=sum(bank == 1 for _, bank in sectors), bank2_sectors=sum(bank == 2 for _, bank in sectors),
        physical_collateral_preimage='MISSING_964_BYTES', hardware=False, device_entry=False,
        reset_qualified=False, eeprom_write_authorized=False, internal_write_authorized=False,
        bank_definition=dict(header=cli.record(flash_header), compile_commands=cli.record(compile_commands),
                             chip_macro='AT32F435RGT7', target='X_Track_Boot'),
        boot_recovery_footprint=dict(erase_end=0x080A8000, program_end=0x080A8000,
                                    extra_beyond_direct=2048, direct_suffix_preservation_applies=False),
        model_suffix='synthetic non-FF; never a physical archive',
        inputs=inputs_before, compiler=compiler, executable=cli.record(out/'boot-model.exe'),
        warnings=len(re.findall(rb'\bwarning:', compile_log)), errors=len(re.findall(rb'\berror:', compile_log)),
        boot_model_lines=boot_log.decode('utf-8').splitlines()))
    print('HOST_ONLY_COMPLETE_STATE_PLAN_PASS tests='+str(int(count[1])))
    print(boot_log.decode('utf-8'))


if __name__ == '__main__':
    main()
