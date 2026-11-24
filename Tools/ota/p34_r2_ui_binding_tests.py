"""Offline linked-instruction UI binding and bounded pointer-model tests."""
import argparse
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'Tools/ota'))
import p34_install_cost as host
import p34_mutation_audit_tests as preflight
from recovery_confirm import r2_ui_binding as ui

cli = host.cli
BUILD = ROOT / '.cache/p34-early-usb-r2/on/b/app-gcc'
OBJDUMP = Path('D:/singlechip/gcc+gdb+openocd/tools/arm-gnu-toolchain-13.3.rel1-ming/bin/arm-none-eabi-objdump.exe')
SYMBOLS = dict(step='_ZN4Page14FirmwareUpdate11RunWorkStepEv',
    release='_ZN4Page14FirmwareUpdate9ReleaseUIEv', constructor='_ZN4Page14FirmwareUpdateC1Ev',
    register='_ZN11PageManager8RegisterEP8PageBasePKc', find='_ZN11PageManager14FindPageInPoolEPKc')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                'isolated root required')
    store = cli.Store(ROOT)
    out = store.checked(args.output_dir)
    manifest = ROOT / '.cache/p34-recovery-sources1/result.json'
    original = {r['path']: r for r in store.read(manifest)['inputs']}
    elf, map_path = (BUILD / ('X-Track-App-GCC' + suffix) for suffix in ('.elf', '.map'))
    cli.require(cli.record(elf) == original[str(elf)] and cli.record(map_path) == original[str(map_path)],
                'original R2 ELF/map required')
    paths = [Path(__file__).resolve(), Path(ui.__file__), Path(ui.capture.__file__),
        Path(ui.capture.policy.__file__), Path(ui.capture.policy.sources.__file__), Path(ui.r2_health.__file__),
        ROOT / 'tests/boot/test_p34_r2_ui_binding.py', ROOT / 'Tools/ota/p34_install_cost.py',
        ROOT / 'Tools/ota/p34_session.py', ROOT / 'Tools/ota/p34_mutation_audit_tests.py',
        ROOT / '.agents/skills/e-track-flutter-debug/scripts/host_io.py', manifest, elf, map_path,
        ROOT / '.cache/p34-recovery-sources1/r2-a.bin',
        *(ROOT / '.cache/p34-early-usb-r2/f' / n for n in ('USER/App/App.cpp',
            'USER/App/Pages/FirmwareUpdate/FirmwareUpdate.cpp', 'USER/App/Pages/FirmwareUpdate/FirmwareUpdate.h',
            'USER/App/Utils/PageManager/PM_Base.cpp', 'USER/App/Utils/PageManager/PageManager.h',
            'USER/App/Utils/PageManager/PageBase.h', 'USER/HAL/HAL_OTA_Package.cpp'))]
    preflight.preflight(store, out, paths)
    for tag in SYMBOLS:
        for suffix in ('.log', '.json'): store.checked(out / (tag + suffix))
    if args.check_only:
        print('UI_BINDING_PREFLIGHT_PASS'); return
    records = [cli.record(p) for p in paths]
    env = host.environment(store, out)
    for path in paths: store.raw(out / 'source' / path.relative_to(ROOT), path.read_bytes())
    log = host.command(store, out, 'tests', [sys.executable, '-I', '-S', '-B', '-X', 'utf8',
        ROOT / 'tests/boot/test_p34_r2_ui_binding.py', '-v'], env, 60)
    count = re.search(rb'Ran (\d+) tests? in .*\r?\n\r?\nOK\b', log)
    cli.require(count, 'UI binding tests failed')
    tool = cli.record(OBJDUMP)
    for tag, symbol in SYMBOLS.items():
        output = host.command(store, out, tag, [OBJDUMP, '-d', '--disassemble=' + symbol, elf], env, 30)
        cli.require(('<' + symbol + '>:').encode('ascii') in output, 'linked function disassembly missing')
    image = (ROOT / '.cache/p34-recovery-sources1/r2-a.bin').read_bytes()
    binding = ui.verify(image, map_path.read_bytes())
    cli.require(records == [cli.record(p) for p in paths] and tool == cli.record(OBJDUMP), 'UI binding source/tool changed')
    store.write(out / 'result.json', dict(result='R2_UI_BINDING_HOST_PASS', tests=int(count[1]),
        inputs=records, objdump=tool, binding=binding, anchors=ui.ANCHORS, hardware=False,
        firmware_rebuilt=False, nor_read_qualified=False))
    print('R2_UI_BINDING_HOST_PASS', int(count[1]))


if __name__ == '__main__': main()
