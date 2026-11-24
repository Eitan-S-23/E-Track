"""Contained tests for new R2-B rendezvous; no device CLI."""
import argparse
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'Tools/ota'))
import p34_boot16_tests as ports
cli, host = ports.cli, ports.host


def sources():
    extra = ('Tools/ota/p34_boot16_entry_tests.py', 'Tools/ota/recovery_confirm/boot16_entry.py',
        'tests/boot/test_p34_boot16_entry.py', 'tests/boot/test_p34_rendezvous.py',
        'Tools/ota/recovery_confirm/r2_health.py', 'Tools/ota/recovery_confirm/r2_passive_state.py',
        'Tools/ota/recovery_confirm/r2_ui_binding.py', 'Tools/ota/recovery_confirm/r2_mapped_backup.py',
        'Tools/ota/recovery_confirm/r2_mapped_backup_byte.py', 'Tools/ota/recovery_entry/state_probe.py',
        'Tools/ota/recovery_entry/rendezvous.py', 'Tools/ota/recovery_entry/app_resume.py',
        'Tools/ota/recovery_entry/owner_probe.py', 'Tools/ota/recovery_entry/host_nor.py',
        'Tools/ota/p34_finalized_vtor_capture.py', 'Tools/ota/p34_r2_vtor_policy.py',
        '.cache/p34-recovery-sources1/r2-b.bin',
        '.cache/p34-early-usb-r2/on/b/app-gcc/X-Track-App-GCC.map',
        '.cache/p34-early-usb-r2/on/disassembly.log')
    snapshot = ('MDK-ARM_F435/Platform/Core/at32_sdio.c',
        'MDK-ARM_F435/Platform/middlewares/usb_drivers/inc/usb_std.h',
        'MDK-ARM_F435/Platform/middlewares/usb_drivers/inc/usbd_core.h',
        'Libraries/USB_MSC/msc_class/msc_bot_scsi.h', 'Libraries/USB_MSC/msc_class/msc_bot_scsi.c',
        'Libraries/USB_MSC/msc_class/msc_class.c', 'USER/HAL/HAL_USB.cpp', 'USER/main.cpp')
    return list(dict.fromkeys([*ports.sources(), *(ROOT / p for p in extra),
        *(ROOT / '.cache/p34-early-usb-r2/f' / p for p in snapshot)]))


def main():
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                'isolated explicit root required')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', required=True, type=Path)
    store = cli.Store(ROOT)
    out = store.checked(parser.parse_args().output_dir)
    cli.require(not out.exists(), 'preserve entry checks')
    paths = sources()
    for path in paths: store.checked(out / 'source' / path.relative_to(ROOT))
    for name in ('tests.log', 'tests.json', 'result.json'): store.checked(out / name)
    for key in ('HOME', 'USERPROFILE', 'APPDATA', 'LOCALAPPDATA', 'TEMP', 'TMP', 'TMPDIR',
                'XDG_CACHE_HOME', 'XDG_CONFIG_HOME', 'XDG_DATA_HOME', 'PYTHONUSERBASE',
                'PYTHONPYCACHEPREFIX', 'CCACHE_DIR', 'SCCACHE_DIR'):
        store.checked(out / 'host' / key.lower())
    records = [cli.record(path) for path in paths]
    env = host.environment(store, out)
    for path in paths: store.raw(out / 'source' / path.relative_to(ROOT), path.read_bytes())
    raw = host.command(store, out, 'tests', [sys.executable, '-I', '-S', '-B', '-X', 'utf8',
        ROOT / 'tests/boot/test_p34_boot16_entry.py', '-v'], env, 120)
    count = re.search(rb'Ran (\d+) tests? in .*\r?\n\r?\nOK\b', raw)
    cli.require(count and records == [cli.record(p) for p in paths], 'entry oracle/input drift')
    store.write(out / 'result.json', dict(result='BOOT16_ENTRY_HOST_PASS', tests=int(count[1]), inputs=records,
        device_operations=0, device_entry_implemented=False, independent_acceptance=False))
    print('BOOT16_ENTRY_HOST_PASS', int(count[1]), flush=True)


if __name__ == '__main__': main()
