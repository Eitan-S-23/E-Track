"""Contained old-backup mapped comparison tests, no native load or capture CLI."""
import argparse
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'Tools/ota'))
import p34_r2_state_device as prior
from recovery_confirm.r2_mapped_backup import expected

ARCHIVE = ROOT/'.cache/p34-recovery-continue1/after-candidate-backup.bin'
FROZEN = ROOT/'.cache/p34-early-usb-r2/f'


def sources(store):
    paths = prior.sources(store)
    receipt = ROOT/'.cache/p34-r2-state-device-tests1/result.json'
    tested = store.read(receipt)
    prior.cli.require(tested['result'] == 'R2_STATE_DEVICE_HOST_PASS' and
                      tested['inputs'] == [prior.cli.record(p) for p in paths], 'current state-owner tests required')
    expected(ARCHIVE.read_bytes())
    return list(dict.fromkeys([*paths, receipt, ARCHIVE, Path(__file__).resolve(),
        ROOT/'Tools/ota/recovery_confirm/r2_mapped_backup.py', ROOT/'tests/boot/test_p34_r2_mapped_backup.py',
        *(FROZEN/n for n in ('Libraries/W25Q128/qspi_cmd_en25qh128a.cpp',
            'Libraries/W25Q128/qspi_cmd_en25qh128a.h', 'USER/HAL/HAL_W25Q128.cpp',
            'MDK-ARM_F435/Platform/HAL/HAL_Display.cpp', 'MDK-ARM_F435/Platform/Core/at32_sdio.c',
            'MDK-ARM_F435/Platform/Core/adc.c', 'Libraries/USB_MSC/msc_diskio.h',
            'USER/App/Pages/FirmwareUpdate/FirmwareUpdate.cpp', 'USER/HAL/HAL_OTA_Package.cpp'))]))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output-dir', type=Path, required=True)
    p.add_argument('--check-only', action='store_true')
    a = p.parse_args()
    cli, host = prior.cli, prior.host
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                'isolated root required')
    s = cli.Store(ROOT)
    out = s.checked(a.output_dir)
    paths = sources(s)
    prior.preflight(s, out, paths)
    if a.check_only:
        print('MAPPED_BACKUP_TEST_PREFLIGHT_PASS', len(paths)); return
    records = [cli.record(p) for p in paths]
    env = host.environment(s, out)
    for path in paths: s.raw(out/'source'/path.relative_to(ROOT), path.read_bytes())
    log = host.command(s, out, 'tests', [sys.executable, '-I', '-S', '-B', '-X', 'utf8',
        ROOT/'tests/boot/test_p34_r2_mapped_backup.py', '-v'], env, 180)
    count = re.search(rb'Ran (\d+) tests? in .*\r?\n\r?\nOK\b', log)
    cli.require(count and records == [cli.record(p) for p in paths], 'mapped test/source drift')
    s.write(out/'result.json', dict(result='R2_MAPPED_BACKUP_COMPONENT_HOST_PASS', tests=int(count[1]),
        inputs=records, hardware=False, native_capture_entry=False, physical_uncached_claim=False))
    print('R2_MAPPED_BACKUP_COMPONENT_HOST_PASS', int(count[1]))


if __name__ == '__main__': main()
