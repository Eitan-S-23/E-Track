"""P1-6 asset binding and owned native-tool adapter; no Flash implementation."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'Tools/ota/p34-acceptance'))
import live_host as host


def validator():
    spec = importlib.util.spec_from_file_location('p16_app_validator', ROOT / 'Tools/jlink/prepare-bootstrap-app.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def section(text, name):
    matches = re.findall(r'^\.' + re.escape(name) + r'\s+(0x[0-9a-fA-F]+)\s+(0x[0-9a-fA-F]+)\b', text, re.M)
    host.require(len(matches) == 1, 'missing/ambiguous linked section: ' + name)
    return tuple(int(v, 16) for v in matches[0])


def idle_symbol(text):
    matches = re.findall(r'^ \.text\._ZN3HAL10HAL_UpdateEv[ \t]*\n\s*(0x[0-9a-fA-F]+)\s+0x[0-9a-fA-F]+\b', text, re.M)
    host.require(len(matches) == 1, 'missing/ambiguous linked HAL_Update')
    address = int(matches[0], 16)
    host.require(0x08010000 <= address < 0x08100000 and address % 2 == 0, 'invalid HAL_Update address')
    return address


def assets(directory, build):
    check = validator()
    manifest = json.loads((directory / 'assets.json').read_bytes())
    images = []
    payloads = []
    for name in ('V0-final.bin', 'V1-final.bin'):
        data = (directory / name).read_bytes()
        value = check.validate_app(data)
        expected = manifest[name]
        actual = dict(length=len(data), version_code=value['version_code'],
                      raw_sha256=hashlib.sha256(data).hexdigest(),
                      double_zero_sha256=data[check.FW_HEADER_OFFSET + 40:check.FW_HEADER_OFFSET + 72].hex(),
                      header_crc32='%08x' % check.u32(data, check.FW_HEADER_OFFSET + 92))
        host.require(all(expected.get(k) == v for k, v in actual.items()), 'asset manifest mismatch: ' + name)
        images.append(actual)
        payloads.append(data)
    host.require(images[1]['version_code'] > images[0]['version_code'], 'V1 must advance V0')
    size = images[0]['length']
    policy = manifest.get('policy')
    host.require(isinstance(policy, dict) and policy.get('applyGroup') == 16 and policy.get('rollbackGroup') == 1,
                 'group16 fixture policy required')
    k = policy.get('changedBlock')
    host.require(type(k) is int and k > 0 and k % 16 == 0, 'changed block must start a durable group')
    blocks = (size + 4095) // 4096
    host.require(size == images[1]['length'] and blocks > k + 16 and size % 4096 != 0 and blocks % 16 != 0,
                 'equal images with changed groups and partial tail required')
    host.require(policy.get('applyResume') == k + 16 and policy.get('rollbackResume') == k + 1 and
                 policy.get('blocks') == blocks, 'group checkpoint mismatch')
    source = host.pinned(policy['payloadSource']).read_bytes()
    host.require(len(source) == policy.get('appendedOnlyAfter') and len(source) <= k * 4096,
                 'changed suffix overlaps linked App')
    for data in payloads:
        host.require(data[:0x400] == source[:0x400] and data[0x460:len(source)] == source[0x460:],
                     'fixture changed executable bytes')
    for block in (k, k + 1, k + 16):
        start = block * 4096
        host.require(payloads[0][start:start + 4096] != payloads[1][start:start + 4096],
                     'checkpoint block would be skipped as identical')
    host.require(hashlib.sha256((build / 'boot/X-Track-Boot.bin').read_bytes()).hexdigest() == policy.get('bootSha256'),
                 'test Boot artifact mismatch')
    control = check.parse_layout_macro('OTA_RAM_ORIGIN') + check.parse_layout_macro('OTA_RAM_LENGTH') - 512
    maps = [build / 'boot/X-Track-Boot.map', build / 'app-gcc/X-Track-App-GCC.map']
    for path in maps:
        host.require(section(path.read_text(encoding='utf8'), 'p1_6_control') == (control, 512), 'linked control mismatch')
    app_map = maps[1].read_text(encoding='utf8')
    vtor, vector_size = section(app_map, 'p34_runtime_vectors' if re.search(r'^\.p34_runtime_vectors\s', app_map, re.M) else 'isr_vector')
    host.require(vtor % 1024 == 0 and check.APP_ORIGIN <= vtor < check.APP_ORIGIN + size and vector_size > 0,
                 'invalid runtime vector section')
    return dict(v0=images[0]['version_code'], v1=images[1]['version_code'],
                bytes=size, blocks=blocks, control=control, vtor=vtor, safeHalt=idle_symbol(app_map),
                changedBlock=k, applyResume=k + 16, rollbackResume=k + 1, applyGroup=16,
                images=images, maps=[host.record(p) for p in maps])


def native(args):
    log = host.checked(args.log)
    out = host.checked(log.with_suffix('.native'))
    host.require(not log.exists() and not out.exists(), 'native output already exists')
    host.require(0 < args.timeout <= 600 and args.serial > 0, 'native bounds')
    commands = host.checked(args.commands)
    for line in commands.read_text(encoding='ascii').splitlines():
        if line.lower().startswith('savebin '):
            match = re.fullmatch(r'savebin "([^"]+)",\s*0x[0-9a-fA-F]+,\s*0x[0-9a-fA-F]+', line, re.I)
            host.require(match is not None, 'unbound native readback path')
            target = host.checked(Path(match[1]))
            host.require(not target.exists(), 'readback would overwrite prior evidence')
    host.fresh(out)
    env = host.environment(out)
    argv = [args.tool, '-USB', str(args.serial), '-Device', 'AT32F435RGT7', '-If', 'SWD', '-Speed', '1000',
            '-AutoConnect', '0', '-ExitOnError', '1', '-NoGui', '1', '-Log', out / 'segger.log',
            '-SettingsFile', out / 'settings.jlink',
            '-CommandFile', commands]
    try:
        host.command(out, 'commander', argv, env, seconds=args.timeout)
    finally:
        streams = [out / ('commander.' + kind) for kind in ('stdout', 'stderr')]
        if all(p.is_file() for p in streams):
            host.raw(log, b''.join(p.read_bytes() for p in streams))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_subparsers(dest='mode', required=True)
    bound = modes.add_parser('assets')
    bound.add_argument('--assets', type=Path, required=True)
    bound.add_argument('--build', type=Path, required=True)
    run = modes.add_parser('native')
    for name in ('tool', 'commands', 'log'):
        run.add_argument('--' + name, type=Path, required=True)
    run.add_argument('--serial', type=int, required=True)
    run.add_argument('--timeout', type=int, required=True)
    args = parser.parse_args()
    host.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                 'explicit isolated worktree execution required')
    if args.mode == 'assets':
        print(json.dumps(assets(args.assets, args.build)))
    else:
        native(args)


if __name__ == '__main__':
    main()
