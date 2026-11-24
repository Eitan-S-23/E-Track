"""Contained CRC equivalence and existing backup regression; no firmware/device build."""
from pathlib import Path
import json
import runpy
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'Tools/ota'))
import p34_install_cost as host


def main():
    s = host.cli.Store(ROOT)
    out = s.checked(ROOT / '.cache/p34-crc-screen/host-001')
    host.cli.require(not out.exists(), 'preserve host test evidence')
    env = host.environment(s, out)
    cc = 'D:/install/mingw64/bin/gcc.exe'
    flags = [cc, '-std=c99', '-O2', '-Wall', '-Wextra', '-Werror',
             '-I'+str(ROOT/'boot/include'), '-I'+str(ROOT/'Libraries')]
    source = ROOT / 'boot/src/boot_crc32.c'
    reference, candidate, exe = [s.checked(out/n) for n in ('reference.o','candidate.o','crc.exe')]
    renames = ['-Dboot_crc32_init=reference_init', '-Dboot_crc32_update=reference_update',
               '-Dboot_crc32_final=reference_final','-Dboot_crc32=reference_crc']
    host.command(s,out,'compile-reference',flags+renames+['-c',source,'-o',reference],env,60)
    host.command(s,out,'compile-candidate',flags+['-DCONFIG_OTA_APP_CRC32_NIBBLE=1','-c',source,'-o',candidate],env,60)
    host.command(s,out,'compile-test',flags+[ROOT/'tests/ota/test_p34_crc.c',reference,candidate,'-o',exe],env,60)
    result = host.command(s,out,'equivalence',[exe],env,60).decode()
    host.cli.require('CRC_EQUIVALENCE_PASS' in result, 'missing CRC result')
    backup = runpy.run_path(str(ROOT/'tests/ota/test_ota_backup.py'))
    for enabled in (0,1):
        binary = s.checked(out/f'backup-{enabled}.exe')
        host.command(s,out,f'compile-backup-{enabled}',flags+[
            f'-DCONFIG_OTA_APP_CRC32_NIBBLE={enabled}',*backup['BACKUP_SOURCES'],'-o',binary],env,60)
        host.command(s,out,f'backup-{enabled}',[binary],env,120)
    inputs = [source, Path(__file__), ROOT/'tests/ota/test_p34_crc.c',*backup['BACKUP_SOURCES']]
    s.write(out/'result.json',dict(result='CRC_HOST_SCREEN_PASS',equivalence=result,
        sources=[host.cli.record(p) for p in sorted(set(inputs))],boot_built=False,device_operations=0,
        scope='host equivalence/performance only; default path unchanged; no measured MCU gain'))
    print(result, 'BACKUP_DEFAULT_AND_CANDIDATE_PASS', flush=True)


if __name__ == '__main__':
    host.cli.require(Path.cwd()==ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                     'explicit root and isolated Python required')
    main()
