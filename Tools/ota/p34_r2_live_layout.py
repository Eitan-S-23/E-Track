"""Derive R2 session ABI with its exact original C flags; no firmware rebuild."""
import argparse
from pathlib import Path
import re
import shlex
import struct
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'Tools/ota'))
import p34_install_cost as host
from recovery_confirm import r2_health

cli = host.cli
BUILD = ROOT / '.cache/p34-early-usb-r2/on/b'
PROBE = ROOT / 'Tools/ota/baud_session_layout.c'


def plan(store, out):
    ninja = BUILD / 'build.ninja'
    rules = BUILD / 'CMakeFiles/rules.ninja'
    text = ninja.read_text(encoding='utf-8')
    matches = re.findall(r'^build [^\n]*?/ota_ble_session\.c\.obj: C_COMPILER__X_Track_App_GCC_unscanned_Release[^\n]*\n((?:  [^\n]*\n)+)', text, re.M)
    cli.require(len(matches) == 1, 'exact R2 session C compile entry required')
    fields = dict(re.findall(r'^  ([A-Z_]+) = (.*)$', matches[0], re.M))
    command = re.findall(r'^rule C_COMPILER__X_Track_App_GCC_unscanned_Release\n(?:(?:  .*\n)*?)  command = (.*)$', rules.read_text(encoding='utf-8'), re.M)
    cli.require(len(command) == 1, 'exact original C compiler rule required')
    compiler = command[0].split('@$RSP_FILE', 1)[0].replace('${LAUNCHER}${CODE_CHECK}', '').strip()
    gcc = Path(compiler)
    cli.require(gcc.is_file() and gcc.name == 'arm-none-eabi-gcc.exe', 'original cross compiler missing')
    flags = shlex.split(' '.join(fields[k] for k in ('DEFINES', 'INCLUDES', 'FLAGS')), posix=False)
    cli.require('-fstack-usage' in flags and '-std=c99' in flags and '-fshort-enums' in flags,
                'R2 original compile options changed')
    cli.require(not any(x.startswith(('-o', '-M', '--output', '-save-temps', '-fprofile')) for x in flags),
                'unqualified compiler output option')
    objcopy = gcc.with_name('arm-none-eabi-objcopy.exe')
    cli.require(objcopy.is_file(), 'matching objcopy missing')
    inputs = [Path(__file__).resolve(), PROBE, ninja, rules, BUILD / 'app-gcc/X-Track-App-GCC.map',
              ROOT / 'Tools/ota/p34_install_cost.py', ROOT / 'Tools/ota/p34_session.py', gcc, objcopy]
    r2_health.verify_map(inputs[4].read_bytes())
    cli.require(not out.exists(), 'preserve live ABI derivation')
    for name in ('compile.log', 'compile.json', 'extract.log', 'extract.json', 'layout.o',
                 'layout.su', 'layout.o.su', 'layout.d', 'layout.bin', 'result.json'):
        store.checked(out / name)
    for key in ('HOME', 'USERPROFILE', 'APPDATA', 'LOCALAPPDATA', 'TEMP', 'TMP', 'TMPDIR',
                'XDG_CACHE_HOME', 'XDG_CONFIG_HOME', 'XDG_DATA_HOME', 'PYTHONUSERBASE',
                'PYTHONPYCACHEPREFIX', 'CCACHE_DIR', 'SCCACHE_DIR'):
        store.checked(out / 'host' / key.lower())
    return inputs, [gcc, *flags, '-MD', '-MT', 'layout.o', '-MF', out / 'layout.d',
                    '-o', out / 'layout.o', '-c', PROBE], objcopy


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                'isolated explicit project root required')
    store = cli.Store(ROOT)
    out = store.checked(args.output_dir)
    inputs, command, objcopy = plan(store, out)
    if args.check_only:
        print('R2_ABI_PREFLIGHT_PASS'); return
    before = [cli.record(p) for p in inputs]
    env = host.environment(store, out)
    output = host.command(store, out, 'compile', command, env, 60)
    cli.require(not re.search(rb'\b(?:warning|error):', output), 'ABI compiler warning/error')
    host.command(store, out, 'extract', [objcopy, '-O', 'binary', '-j', '.rodata.p34_session_layout',
                                       out / 'layout.o', out / 'layout.bin'], env, 30)
    raw = (out / 'layout.bin').read_bytes()
    names = re.findall(r'\bFIELD\(([^)]+)\)', PROBE.read_text(encoding='utf-8'))[1:]
    cli.require(len(raw) == 180 and len(names) == 21, 'ABI output extent differs')
    words = struct.unpack('<45I', raw)
    cli.require(words[:3] == (0x50334c59, 576, 21), 'R2 session ABI identity differs')
    members = {name: dict(offset=words[3 + 2 * i], bytes=words[4 + 2 * i]) for i, name in enumerate(names)}
    map_text = (BUILD / 'app-gcc/X-Track-App-GCC.map').read_text(encoding='utf-8')
    symbols = {}
    for symbol, size in (('_ZL13s_ble_session', 576), ('s_ble_epoch', 4), ('g_p34_retained_word', 4),
                         ('g_p34_boot_baud', 4), ('g_p34_retention_error', 4)):
        name = '_ZL11s_ble_epoch' if symbol == 's_ble_epoch' else symbol
        found = re.findall(r'^ \.bss\.' + re.escape(name) + r'\s+(0x[0-9a-f]+)\s+(0x[0-9a-f]+)\s', map_text, re.M)
        cli.require(len(found) == 1 and int(found[0][1], 16) == size, 'R2 live symbol differs: ' + symbol)
        symbols[symbol] = int(found[0][0], 16)
    deps = (out / 'layout.d').read_text(encoding='utf-8').replace('\\\n', '').split(': ', 1)[1].split()
    dependencies = [Path(p).resolve() for p in deps]
    # Every transitive header is a read-only input; none is rebuilt or rewritten.
    cli.require(before == [cli.record(p) for p in inputs], 'ABI derivation inputs changed')
    store.write(out / 'result.json', dict(result='R2_SESSION_ABI_DERIVED', inputs=before,
        dependencies=[cli.record(p) for p in dependencies], members=members, size=words[1], symbols=symbols,
        outputs=[cli.record(out / n) for n in ('layout.o', 'layout.bin', 'layout.d')],
        compiler_warnings=0, compiler_errors=0, hardware=False, firmware_rebuilt=False,
        live_read_qualified=False, qspi_mapping_qualified=False))
    print('R2_SESSION_ABI_DERIVED', members['state'], members['isr_active'], symbols)


if __name__ == '__main__':
    main()
