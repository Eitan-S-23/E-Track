"""Bounded R2 152-block host extension; no target build or device entry."""
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'Tools/ota'))
import p34_boot_checkpoint_model as model

cli, host = model.cli, model.host
TARGET = ROOT / '.cache/p34-bc-target'
EXTENSION = ROOT / 'tests/boot/p34_checkpoint_r2_tail.c'
IMAGES = {
    'r2-a': ('.cache/p34-recovery-sources1/r2-a.bin',
             '7445ef63d5f4cbef95761f27075333d7d09c9d43585a28b84e6575ccfb274fcf'),
    'r2-b': ('.cache/p34-recovery-sources1/r2-b.bin',
             'e4737cfcbbb884c4a7fa407ea733486425674c7ed2723d0f8cf3263beb4e8802'),
}


def inputs(store):
    model.validate(store)
    paths = [Path(__file__), EXTENSION, ROOT / 'Tools/ota/p34_install_cost.py',
             ROOT / 'Tools/ota/p34_session.py',
             ROOT / '.agents/skills/e-track-flutter-debug/scripts/host_io.py']
    for name in ('r3/result.json', 'extension1/result.json', 'review-tests1/result.json'):
        path = model.AREA / name
        prior = store.read(path)
        paths.append(path)
        for record in prior['sources']:
            cli.require(cli.record(record['path']) == record, 'prior model binding changed')
            paths.append(Path(record['path']))
    # Reuse build/stack evidence, never rebuild their frozen inputs.
    for name in ('result.json', 'analysis.json', 'stack-analysis.json', 'snapshot.json'):
        path = TARGET / name
        prior = store.read(path)
        paths.append(path)
        for record in prior.get('inputs', []) if isinstance(prior.get('inputs'), list) else []:
            cli.require(cli.record(record['path']) == record, 'target analysis input changed')
            paths.append(Path(record['path']))
        for record in prior.get('files', []):
            cli.require(cli.record(record['path']) == record, 'target snapshot changed')
            paths.append(Path(record['path']))
    result = store.read(TARGET / 'result.json')
    for group in ('1', '16'):
        variant = result['variants'][group]
        cli.require(variant['warnings'] == 1 and variant['errors'] == 0, 'build diagnostics changed')
        for key in ('artifacts', 'stack_files', 'configuration'):
            for record in variant[key]:
                cli.require(cli.record(record['path']) == record, 'target artifact changed')
                paths.append(Path(record['path']))
    original = ROOT / '.cache/p34-native-acquire1/boot-readback.bin'
    control = TARGET / 'b1/boot/X-Track-Boot.bin'
    candidate = TARGET / 'b16/boot/X-Track-Boot.bin'
    checks = ((original, 65536, 'a63346db0dc673dc42adf6064892c466af5c4571df53cb55fe5b6ea154c1fdf4'),
              (control, 14780, 'f0ed3994f7f7a7d39dac92a09b0fedf2f2b7b05ee038ac400eba2c569c586954'),
              (candidate, 14800, '2f84014278421de7a84a0f621a494a9974fbf51c56b768974b0c5e647105ec80'))
    for path, size, digest in checks:
        rec = cli.record(path)
        cli.require(rec['bytes'] == size and rec['sha256'] == digest, 'Boot identity changed')
        paths.append(path)
    boot = original.read_bytes()
    cli.require(boot[:14780] == control.read_bytes() and boot[14780:16384] == b'\xff' * 1604
                and boot[16384:] != b'\xff' * 49152, 'Boot write/preservation boundary changed')
    for name, (relative, digest) in IMAGES.items():
        path = ROOT / relative
        rec = cli.record(path)
        cli.require(rec['bytes'] == 619580 and rec['sha256'] == digest, name + ' changed')
        paths.append(path)
    cli.require((TARGET / 'f/boot/src/boot_state_machine.c').read_text(encoding='utf-8') ==
                (model.AREA / 'boot_state_machine.c').read_text(encoding='utf-8'), 'target/model source differs')
    return sorted(set(paths))


def test(out):
    store = cli.Store(ROOT)
    out = store.checked(out)
    cli.require(not out.exists(), 'preserve extension output')
    paths = inputs(store)
    bound = [cli.record(p) for p in paths]
    for name in ('fixture.c', 'tail.c', 'result.json'):
        store.checked(out / name)
    for group in (1, 16):
        store.checked(out / ('g%d.exe' % group))
        for tag in ('compile', 'run'):
            for ext in ('.json', '.log'):
                store.checked(out / ('g%d-%s%s' % (group, tag, ext)))
    for key in ('HOME', 'USERPROFILE', 'APPDATA', 'LOCALAPPDATA', 'TEMP', 'TMP', 'TMPDIR',
                'XDG_CACHE_HOME', 'XDG_CONFIG_HOME', 'XDG_DATA_HOME', 'PYTHONUSERBASE',
                'PYTHONPYCACHEPREFIX', 'CCACHE_DIR', 'SCCACHE_DIR'):
        store.checked(out / 'host' / key.lower())
    env = host.environment(store, out)
    fixture = (model.AREA / 'fixture.c').read_text(encoding='utf-8')
    for old, new in (('TEST_IMAGE_LEN = 617588', 'TEST_IMAGE_LEN = 619580'),
                     ('TEST_BLOCK_COUNT = 151', 'TEST_BLOCK_COUNT = 152')):
        cli.require(fixture.count(old) == 1, 'unique fixture shape anchor required')
        fixture = fixture.replace(old, new)
    source = model.HARNESS.read_text(encoding='utf-8')
    cli.require(source.count('int main(void)') == 1, 'unique harness entry required')
    source = source.replace('int main(void)', 'int original_campaign_main(void)')
    store.raw(out / 'fixture.c', fixture.encode('utf-8'))
    store.raw(out / 'tail.c', (source + '\n' + EXTENSION.read_text(encoding='utf-8')).encode('utf-8'))
    common = [ROOT / p for p in ('boot/src/boot_fw_header.c', 'boot/src/boot_slot.c',
              'boot/src/boot_crc32.c', 'boot/src/boot_sha256.c', 'Libraries/EEPROM/eeprom_bcb.c')]
    results = {}
    for group in (1, 16):
        exe = out / ('g%d.exe' % group)
        command = ['D:/install/mingw64/bin/gcc.exe', '-std=c99', '-O2', '-Wall', '-Wextra', '-Werror',
                   '-DP34_BOOT_SKIP_IDENTICAL_BLOCKS=1', '-DP34_BOOT_APPLY_CHECKPOINT_BLOCKS=%d' % group,
                   '-include', model.HOOK]
        command += ['-I' + str(ROOT / p) for p in ('boot/include', 'Libraries', 'Tools/ota')]
        command += ['-I' + str(out), out / 'tail.c', model.AREA / 'boot_state_machine.c', *common, '-o', exe]
        compiled = host.command(store, out, 'g%d-compile' % group, command, env, 120)
        cli.require(not compiled.strip(), 'unexpected compiler diagnostics')
        raw = host.command(store, out, 'g%d-run' % group, [exe], env, 300)
        cli.require(b'R2_CHECKPOINT_TAIL_PASS' in raw, 'tail oracle absent')
        results[str(group)] = raw.decode().splitlines()
        print(raw.decode(), end='', flush=True)
    cli.require(bound == [cli.record(p) for p in paths], 'input changed during checks')
    store.write(out / 'result.json', dict(result='R2_CHECKPOINT_TAIL_HOST_PASS', inputs=bound,
        generated=[cli.record(out / p) for p in ('fixture.c', 'tail.c')], variants=results,
        image_bytes=619580, blocks=152, final_block_bytes=1084, tail_blocks=8,
        model_images='synthetic header-only and dense changes with exact R2 length; not R2 payload replay',
        compile_warnings=0, compile_errors=0, reused_target_warnings_per_variant=1,
        device_operations=0, measured_speedup=False, independent_acceptance=False))


if __name__ == '__main__':
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                'isolated explicit root required')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    test(parser.parse_args().output_dir)
