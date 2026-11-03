"""Reproduce the retained group16 Boot and prepare bounded P1-6 test fixtures."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shutil
import sys
import sysconfig

ROOT = Path(__file__).resolve().parents[2]
ORIGINAL = Path('D:/github/my/E-Track/.cache/p34-bc-target')
sys.path.insert(0, str(ROOT / 'Tools/ota/p34-acceptance'))
import live_host as h


def original_inputs():
    snapshot = json.loads((ORIGINAL / 'snapshot.json').read_bytes())
    for item in snapshot['files']:
        path = Path(item['path'])
        h.require(path.stat().st_size == item['bytes'] and
                  hashlib.sha256(path.read_bytes()).hexdigest() == item['sha256'], 'original source changed: ' + str(path))
    binary = ORIGINAL / 'b16/boot/X-Track-Boot.bin'
    h.require(hashlib.sha256(binary.read_bytes()).hexdigest() ==
        '2f84014278421de7a84a0f621a494a9974fbf51c56b768974b0c5e647105ec80', 'retained Boot source artifact changed')
    return snapshot


def build(out, instrumented):
    bound = original_inputs()
    for name in ('b', 'install', 'result.json', 'source-inputs.json'):
        h.checked(out / name)
    h.fresh(out)
    env = h.environment(out)
    h.save(out / 'source-inputs.json', bound)
    toolchain = Path('D:/singlechip/gcc+gdb+openocd/tools/arm-gnu-toolchain-13.3.rel1-ming')
    cmake, ninja = shutil.which('cmake'), shutil.which('ninja')
    h.require(cmake and ninja, 'installed CMake/Ninja required')
    command = [cmake, '-S', ORIGINAL / 'f/MDK-ARM_F435/cmake-generated', '-B', out / 'b', '-G', 'Ninja',
               '-DCMAKE_BUILD_TYPE=Release', '-DCMAKE_OBJECT_PATH_MAX=220', '-DKEIL_GCC_COMPILER_CACHE:FILEPATH=',
               '-DARM_TOOLCHAIN_ROOT=' + str(toolchain), '-DCMAKE_MAKE_PROGRAM=' + ninja,
               '-DCMAKE_INSTALL_PREFIX=' + str(out / 'install'), '-DP34_BOOT_SKIP_IDENTICAL_BLOCKS=ON',
               '-DP34_BOOT_APPLY_CHECKPOINT_BLOCKS=16', '-DP1_6_TEST_ENABLE=' + ('ON' if instrumented else 'OFF')]
    for language, compiler in (('C', 'gcc'), ('CXX', 'g++'), ('ASM', 'gcc')):
        command.append('-DCMAKE_' + language + '_COMPILER=' + str(toolchain / 'bin' / ('arm-none-eabi-' + compiler + '.exe')))
    h.command(out, 'configure', command, env, seconds=180)
    raw = h.command(out, 'build', [cmake, '--build', out / 'b', '--target', 'X_Track_Boot', '--parallel', '4'], env, seconds=600)
    raw += (out / 'build.stderr').read_bytes()
    binary = out / 'b/boot/X-Track-Boot.bin'
    if not instrumented:
        h.require(binary.read_bytes() == (ORIGINAL / 'b16/boot/X-Track-Boot.bin').read_bytes(), 'baseline does not reproduce retained Boot')
    h.require(original_inputs() == bound, 'external source changed during build')
    value = dict(instrumented=instrumented, retainedReproduced=not instrumented, group=16, skipIdentical=True,
                 warnings=len(re.findall(rb'\bwarning:', raw)), errors=len(re.findall(rb'\berror:', raw)),
                 configureWarnings=len(re.findall(rb'(?im)^CMake Warning', (out / 'configure.stderr').read_bytes())),
                 artifacts=[h.record(out / ('b/boot/X-Track-Boot.' + ext)) for ext in ('bin', 'elf', 'map', 'hex')],
                 source=h.record(out / 'source-inputs.json'), deviceOperations=0)
    h.save(out / 'result.json', value)
    print(json.dumps(value), flush=True)


def fixtures(out, app_build, boot_build):
    sys.path.insert(0, sysconfig.get_path('purelib'))
    sys.path.insert(0, str(ROOT / 'Tools'))
    import etu_pack
    spec = importlib.util.spec_from_file_location('p16_matrix', ROOT / 'Tools/jlink/p1_6_matrix.py')
    matrix = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(matrix)
    check = matrix.validator()
    binary = app_build / 'app-gcc/X-Track-App-GCC.bin'
    original = binary.read_bytes()
    k = ((len(original) + 65535) // 65536) * 16
    blocks = k + 35
    length = (blocks - 1) * 4096 + 137
    h.require(length <= check.APP_LENGTH, 'safe test suffix exceeds App partition')
    copies = [(boot_build / ('boot/X-Track-Boot.' + ext), 'build/boot/X-Track-Boot.' + ext)
              for ext in ('bin', 'elf', 'map', 'hex')]
    copies += [(app_build / ('app-gcc/X-Track-App-GCC.' + ext), 'build/app-gcc/X-Track-App-GCC.' + ext)
               for ext in ('bin', 'elf', 'map', 'hex')]
    for name in ('V0-final.bin', 'V1-final.bin', 'assets.json', 'fixture.json', *[v[1] for v in copies]):
        h.checked(out / name)
    h.fresh(out)
    manifest = {}
    for name, version, fill in (('V0-final.bin', '3.3.14', 0xA5), ('V1-final.bin', '3.3.15', 0x5A)):
        data = bytearray(original + b'\xff' * (length - len(original)))
        data[k * 4096:] = bytes([fill]) * (length - k * 4096)
        data[0x400:0x460] = etu_pack.build_fw_header(bytes(data), version, 1786320000)
        fields = check.validate_app(bytes(data))
        h.require(data[:0x400] == original[:0x400] and data[0x460:len(original)] == original[0x460:],
                  'test fixture changed executable bytes')
        h.raw(out / name, bytes(data))
        manifest[name] = dict(length=len(data), version_code=fields['version_code'],
            raw_sha256=hashlib.sha256(data).hexdigest(), double_zero_sha256=data[0x428:0x448].hex(),
            header_crc32='%08x' % check.u32(data, 0x45c))
    for source, relative in copies:
        h.raw(out / relative, source.read_bytes())
    manifest['policy'] = dict(applyGroup=16, rollbackGroup=1, changedBlock=k,
                              applyResume=k + 16, rollbackResume=k + 1, blocks=blocks,
                              payloadSource=h.record(binary), appendedOnlyAfter=len(original),
                              bootBuild=str(boot_build), appBuild=str(app_build),
                              bootSha256=hashlib.sha256((boot_build / 'boot/X-Track-Boot.bin').read_bytes()).hexdigest(),
                              nonProductionFixture=True)
    h.save(out / 'assets.json', manifest)
    h.save(out / 'fixture.json', dict(policy=manifest['policy'], executableBytesPreserved=True,
        fullLength=length, suffixIsNotExecutable=True, noDeviceOperation=True))
    print(json.dumps(manifest['policy']), flush=True)


def recovery_inputs(out, backup, assets):
    import struct
    import zlib
    spec = importlib.util.spec_from_file_location('p16_matrix', ROOT / 'Tools/jlink/p1_6_matrix.py')
    matrix = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(matrix)
    binding = matrix.assets(assets, assets / 'build')
    saved = h.read_json(backup / 'result.json')
    h.require(saved['outcome'] == 'READ_ONLY_RECOVERY_INPUTS_CAPTURED', 'unqualified backup capture')
    raw = h.pinned(saved['internal']).read_bytes()
    retained = h.read_json(ROOT / '.cache/p17-key-method-20261104-01/key-plan-03.json')['retained']
    boot = h.pinned(retained['boot']).read_bytes()
    app = h.pinned(retained['images']['target']['image']).read_bytes()
    h.require(len(raw) == 0x100000 and raw[:0x10000] == boot and raw[0x10000:0x10000 + len(app)] == app,
              'recovery internal image binding')
    boot_length = ((assets / 'build/boot/X-Track-Boot.bin').stat().st_size + 4095) // 4096 * 4096
    app_length = binding['blocks'] * 4096
    h.require(boot_length == 0x5000 and app_length <= 0xf0000, 'unexpected restore bounds')
    files = {'original-boot.bin': raw[:boot_length], 'original-app.bin': raw[0x10000:0x10000 + app_length]}
    for name, item in saved['slots'].items():
        slot = h.pinned(item['raw']).read_bytes()
        payload = slot[4096:4096 + item['payloadBytes']]
        fields = matrix.validator().validate_app(payload)
        h.require(hashlib.sha256(payload).hexdigest() == item['imageSha256'] and
                  fields['version_code'] == item['header']['version'] and
                  zlib.crc32(payload) == struct.unpack_from('<I', slot, 12)[0], 'restore slot binding')
        files[name + '.bin'] = payload
    for name in (*files, 'plan.json'):
        h.checked(out / name)
    h.fresh(out)
    for name, data in files.items():
        h.raw(out / name, data)
    symbols = h.read_json(backup / 'symbols-target/result.json')['symbols']
    plan = dict(schema='p16-group16-recovery-v1', probeSerial=123456, vtor=binding['vtor'],
        safeHalt=symbols['_ZN3HAL10HAL_UpdateEv'][0], testSafeHalt=binding['safeHalt'],
        bootAffectedBytes=boot_length, appAffectedBytes=app_length,
        originalBoot=h.record(out / 'original-boot.bin'), originalApp=h.record(out / 'original-app.bin'),
        testBoot=h.record(assets / 'build/boot/X-Track-Boot.bin'),
        v0=h.record(assets / 'V0-final.bin'), v1=h.record(assets / 'V1-final.bin'),
        slots={name:h.record(out / (name + '.bin')) for name in saved['slots']},
        backups=saved, retained=retained, assets=str(assets.relative_to(ROOT)),
        restoration=dict(internal='byte-exact full 1 MiB compared with original',
            slots='original header and complete declared payload; unused tails are not claimed identical',
            bcb='known CONFIRMED 30313 with no pending apply/rollback; raw A/B and sequence may differ',
            unrelated='staging header/journal unchanged; no writes outside three test slots and BCB A/B'))
    h.save(out / 'plan.json', plan)
    print(json.dumps(dict(outcome='RECOVERY_INPUTS_BOUND', plan=h.record(out / 'plan.json'),
                         deviceOperations=0, restorationPhysicallyQualified=False)), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('baseline', 'instrumented', 'fixtures', 'recovery-inputs'))
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--app-build', type=Path)
    parser.add_argument('--boot-build', type=Path)
    parser.add_argument('--backup', type=Path)
    parser.add_argument('--assets', type=Path)
    args = parser.parse_args()
    h.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
              'explicit isolated worktree execution required')
    out = h.checked(args.out)
    if args.mode == 'recovery-inputs':
        h.require(args.backup is not None and args.assets is not None, 'backup and fixture inputs required')
        recovery_inputs(out, args.backup.resolve(), args.assets.resolve())
    elif args.mode == 'fixtures':
        h.require(args.app_build is not None and args.boot_build is not None, 'two bound builds required')
        fixtures(out, args.app_build.resolve(), args.boot_build.resolve())
    else:
        build(out, args.mode == 'instrumented')


if __name__ == '__main__':
    main()
