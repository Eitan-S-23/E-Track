"""Build and test host recovery writer callbacks; this entry has no device access."""
import argparse
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'Tools/ota'))
import p34_install_cost as host

cli = host.cli
CC = Path('D:/install/mingw64/bin/gcc.exe')
CORE = ROOT/'Tools/ota/ram_recovery'
SNAP = ROOT/'.cache/p34-bc-target/f'
SOURCES = [Path(__file__).resolve(), ROOT/'Tools/ota/recovery_entry/host_writer.py',
           ROOT/'Tools/ota/recovery_entry/probe.py', ROOT/'tests/boot/test_p34_host_writer.py',
           CORE/'host_writer.c', CORE/'writer.c', CORE/'writer.h',
           ROOT/'.cache/p34-recovery-sources1/r2-a.bin',
           ROOT/'.cache/p34-ram-writer-cross1/result.json',
           ROOT/'.cache/p34-ram-writer-cross1/a.bin',
           ROOT/'.cache/p34-recovery-admission2/validator.exe',
           ROOT/'Tools/ota/p34_session.py', ROOT/'Tools/ota/p34_install_cost.py',
           ROOT/'.agents/skills/e-track-flutter-debug/scripts/host_io.py',
           SNAP/'Libraries/OTA/ota_layout.h']
SOURCES += [SNAP/'boot/src'/n for n in ('boot_fw_header.c', 'boot_crc32.c', 'boot_sha256.c')]
SOURCES += sorted((SNAP/'boot/include').glob('*.h'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                'isolated explicit root required')
    store = cli.Store(ROOT); out = store.checked(args.output_dir)
    cli.require(not out.exists(), 'preserve writer evidence')
    for name in ('writer.dll', 'compile.log', 'compile.json', 'tests.log', 'tests.json', 'result.json',
                 'physical-model.bin', 'admission.log', 'admission.json'):
        store.checked(out/name)
    for p in SOURCES: store.checked(out/'source'/p.relative_to(ROOT))
    inputs = [cli.record(p) for p in SOURCES]
    env = host.environment(store, out)
    for p in SOURCES: store.raw(out/'source'/p.relative_to(ROOT), p.read_bytes())
    dll = store.checked(out/'writer.dll')
    log = host.command(store, out, 'compile', [CC, '-std=c99', '-O2', '-Wall', '-Wextra', '-Werror',
        '-shared', '-static-libgcc', '-I'+str(CORE), '-I'+str(SNAP/'boot/include'), '-I'+str(SNAP/'Libraries'),
        CORE/'host_writer.c', CORE/'writer.c', *(SNAP/'boot/src'/n for n in
        ('boot_fw_header.c', 'boot_crc32.c', 'boot_sha256.c')), '-o', dll], env, 90)
    env['P34_WRITER_DLL'] = str(dll); env['P34_TEST_OUT'] = str(out)
    data = host.command(store, out, 'tests', [sys.executable, '-I', '-S', '-B', '-X', 'utf8',
        ROOT/'tests/boot/test_p34_host_writer.py', '-v'], env, 120)
    match = re.search(rb'Ran (\d+) tests? in .*\r?\n\r?\nOK\b', data)
    cli.require(match and inputs == [cli.record(p) for p in SOURCES], 'writer tests/source drift')
    store.write(out/'result.json', dict(result='HOST_WRITER_DLL_TESTS_PASS', tests=int(match[1]),
        inputs=inputs, writer_dll=cli.record(dll), compiler=cli.record(CC), hardware=False,
        warnings=len(re.findall(rb'\bwarning:', log)), errors=len(re.findall(rb'\berror:', log))))
    print('HOST_WRITER_DLL_TESTS_PASS', int(match[1]))


if __name__ == '__main__': main()
