"""Contained host-only tests for first16KiB ports; never load a device DLL."""
import argparse
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'Tools/ota'))
import p34_install_cost as host
cli = host.cli


def sources():
    names = ('Tools/ota/recovery_confirm/boot16.py', 'Tools/ota/recovery_confirm/flash_port.py',
        'Tools/ota/recovery_confirm/flash_remainder.py', 'Tools/ota/recovery_confirm/flash_plan.py',
        'Tools/ota/recovery_confirm/native_io.py', 'Tools/ota/recovery_confirm/mutation_audit.py',
        'Tools/ota/recovery_confirm/ap_journal.py', 'Tools/ota/p34_nor_audit.py',
        'Tools/ota/recovery_entry/native_probe.py', 'Tools/ota/recovery_entry/probe.py',
        'Tools/ota/recovery_entry/load_contract.py',
        'Tools/ota/p34_boot16_tests.py', 'Tools/ota/p34_install_cost.py', 'Tools/ota/p34_session.py',
        '.agents/skills/e-track-flutter-debug/scripts/host_io.py', 'tests/boot/test_p34_boot16.py',
        'tests/boot/test_p34_recovery_ports.py', 'tests/boot/p34_eeprom_wire_model.py',
        'Tools/ota/p34_confirm_page.py', 'Tools/ota/recovery_confirm/eeprom_page.py',
        'Tools/ota/recovery_confirm/page_port.py', 'Tools/ota/recovery_confirm/gpio_page.py',
        'Tools/ota/recovery_confirm/boot_exit.py', 'Tools/ota/recovery_confirm/confirm_io.py',
        '.cache/p34-host-nor-rebuild1/bcb-before.bin', '.cache/p34-native-acquire1/boot-readback.bin',
        '.cache/p34-recovery-sources1/r2-a.bin', '.cache/p34-bc-target/b16/boot/X-Track-Boot.bin')
    return [ROOT / name for name in names]


def main():
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                'isolated explicit root required')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', required=True, type=Path)
    out = parser.parse_args().output_dir
    store = cli.Store(ROOT)
    out = store.checked(out)
    cli.require(not out.exists(), 'preserve host checks')
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
        ROOT / 'tests/boot/test_p34_boot16.py', '-v'], env, 120)
    count = re.search(rb'Ran (\d+) tests? in .*\r?\n\r?\nOK\b', raw)
    cli.require(count and records == [cli.record(p) for p in paths], 'host oracle/input drift')
    store.write(out / 'result.json', dict(result='BOOT16_PORT_HOST_PASS', tests=int(count[1]), inputs=records,
        device_operations=0, device_entry_implemented=False, independent_acceptance=False))
    print('BOOT16_PORT_HOST_PASS', int(count[1]), flush=True)


if __name__ == '__main__':
    main()
