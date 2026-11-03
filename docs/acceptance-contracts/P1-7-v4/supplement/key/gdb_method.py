"""Prepare a bounded standard-GDB predicate observation; no replacement transport."""
from pathlib import Path
import csv
import hashlib
import io
import json
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
AREA = Path(__file__).resolve().parent
assert Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode
sys.path.insert(0, str(ROOT / 'Tools/ota/p34-acceptance'))
import live_host as h

PORTS = (25341, 25342, 25343, 25344)
CHECKPOINT = 0x080019AA
PREDICATE = 0x08001E6D
GPIO = 0x40020010
TICK = 0x20001030
FREEZE = 0xE0042008


def quote(path):
    return '"' + Path(path).as_posix() + '"'


def check(expression, label):
    return [f'if !({expression})', f'  echo P17_ERROR {label}\\n',
            '  monitor halt', '  disconnect', '  quit 3', 'end']


def word(address):
    return f'*(volatile unsigned int*)0x{address:08x}'


def stage(out, name):
    return [f'set logging file {quote(out / ("stage-" + name + ".log"))}',
            'set logging overwrite on', 'set logging redirect on', 'set logging enabled on',
            f'echo P17_STAGE {name}\\n', 'set logging enabled off', 'set logging redirect off']


def wait_key(pressed):
    condition = f'({word(GPIO)} & 0x8000) ' + ('== 0' if pressed else '!= 0')
    return ['set $p17_wait = 0', f'while !({condition}) && $p17_wait < 1200',
            '  monitor sleep 50', '  set $p17_wait = $p17_wait + 1', 'end',
            *check(condition, 'key_wait_timeout')]


def prepare():
    base = ROOT / '.cache/p17-generic-readiness-20261104-01/inspect-01'
    plan = h.read_json(base / 'plan.json')
    observed = h.read_json(base / 'result.json')
    h.require(observed['outcome'] == 'CURRENT_30313_READINESS_CONFIRMED', 'readiness missing')
    boot = ROOT / '.cache/p17-acceptance-20261103-01/prepare-01'
    expected = {'boot.bin': '2f84014278421de7a84a0f621a494a9974fbf51c56b768974b0c5e647105ec80',
                'boot.elf': 'f0917cd4332444ae41afb2da49dc17b82b4536a62417b69300c2e41d6c82e036'}
    for name, digest in expected.items():
        h.require(hashlib.sha256((boot / name).read_bytes()).hexdigest() == digest, 'Boot changed')
    table = h.read_json(base / 'symbols-target/result.json')['symbols']
    idle = table['_ZN3HAL10HAL_UpdateEv'][0]
    header = h.pinned(plan['images']['target']['image']).read_bytes()[0x400:0x460]
    gdb = Path(plan['tools']['nm']['path']).with_name('arm-none-eabi-gdb.exe')
    server = Path(plan['tools']['commander']['path']).with_name('JLinkGDBServerCL.exe')
    for tool in (gdb, server):
        h.require(tool.is_file(), 'missing installed debugger')
    out = AREA / 'gdb-key-01'
    registers = [f'r{i}' for i in range(13)] + ['sp', 'lr', 'pc', 'xpsr']
    code = ['define p17-key-test', f'target remote 127.0.0.1:{PORTS[0]}',
            'monitor exec DisableAutoUpdateFW', 'monitor exec SetRestartOnClose = 0',
            'monitor flash breakpoints = 0', f'set $p17_freeze = {word(FREEZE)}',
            f'set {word(FREEZE)} = $p17_freeze | 0x1000', 'monitor halt',
            f'hbreak *0x{idle:08x}', 'continue', *check(f'$pc == 0x{idle:08x}', 'not_idle'),
            'delete breakpoints']
    for offset in range(0, len(header), 4):
        value = int.from_bytes(header[offset:offset + 4], 'little')
        code += check(f'{word(0x08010400 + offset)} == 0x{value:08x}', 'header_changed')
    for name, value in (('_ZL10SD_IsReady', 1), ('_ZL19g_ota_overlay_owner', 0),
                        ('_ZL18g_ota_confirm_done', 1), ('_ZL20g_ota_state_snapshot', 4)):
        code += check(f'*(unsigned char*)0x{table[name][0]:08x} == {value}', 'app_state')
    code += check(f'({word(0x4002C434)} & 0x3800) == 0', 'sdio_active')
    code += stage(out, 'hold') + wait_key(True)
    code += ['monitor reset', f'set {word(FREEZE)} = $p17_freeze | 0x1000',
             f'hbreak *0x{CHECKPOINT:08x}', 'continue',
             *check(f'$pc == 0x{CHECKPOINT:08x} && $r0 == 0', 'boot_checkpoint'),
             'delete breakpoints', *check(f'{word(0xE000ED08)} == 0x08000000', 'boot_vectors'),
             *check(f'{word(0x20000000)} == 288000000 && {word(0xE000E014)} == 287999', 'boot_clock'),
             *check(f'({word(0x40020C14)} & 4) != 0', 'power_hold'),
             *check('$sp > 0x20057000 && $sp <= 0x20058000 && ($sp & 7) == 0', 'boot_stack')]
    for register in registers:
        code.append(f'set $p17_saved_{register} = ${register}')
    code += ['set $p17_scratch = $sp - 512',
             f'dump binary memory {quote(out / "stack-before.bin")} $p17_scratch $sp']
    for name in ('long', 'short'):
        if name == 'short':
            code += stage(out, 'release') + wait_key(False) + stage(out, 'short') + wait_key(True)
        code += check(f'({word(GPIO)} & 0x8000) == 0', 'key_not_pressed')
        code += [f'set $p17_start_{name} = {word(TICK)}',
                 f'set $p17_result_{name} = ((int (*)(void))0x{PREDICATE:08x})()',
                 f'set $p17_ticks_{name} = (unsigned int)({word(TICK)} - $p17_start_{name})',
                 f'printf "P17_RESULT {name} result=%d ticks=%u gpio=%08x\\n", $p17_result_{name}, $p17_ticks_{name}, {word(GPIO)}']
        for register in registers:
            code += check(f'${register} == $p17_saved_{register}', 'call_context_' + register)
        condition = f'$p17_result_{name} == ' + ('1 && $p17_ticks_long >= 3000' if name == 'long'
                    else '0 && $p17_ticks_short > 0 && $p17_ticks_short < 3000')
        code += check(condition, name + '_predicate')
    code += [f'dump binary memory {quote(out / "stack-after.bin")} $p17_scratch $sp',
             f'restore {quote(out / "stack-before.bin")} binary $p17_scratch',
             *check(f'$pc == 0x{CHECKPOINT:08x}', 'resume_checkpoint'),
             f'set {word(FREEZE)} = $p17_freeze', 'detach', *stage(out, 'finished'), 'end']
    prologue = ['set pagination off', 'set confirm off', 'set auto-load off',
                'set debuginfod enabled off', 'set trust-readonly-sections off',
                'set mem inaccessible-by-default off', 'set breakpoint auto-hw on',
                'set remote hardware-breakpoint-limit 6', 'set remotetimeout 5',
                f'file {quote(boot / "boot.elf")}', 'mem 0x08000000 0x08100000 ro']
    definitions = '\n'.join(prologue + code) + '\n'
    h.raw(AREA / 'gdb-definitions.gdb', definitions.encode('ascii'))
    h.raw(AREA / 'gdb-key.gdb', (f'source {quote(AREA / "gdb-definitions.gdb")}\np17-key-test\nquit\n').encode('ascii'))
    qualification = prologue + [f'target remote 127.0.0.1:{PORTS[0]}',
                     'monitor exec DisableAutoUpdateFW', 'monitor exec SetRestartOnClose = 0',
                     'monitor flash breakpoints = 0',
                     f'printf "P17_GDB_CPUID %08x\\n", {word(0xE000ED00)}', 'detach', 'quit']
    h.raw(AREA / 'gdb-qualify.gdb', ('\n'.join(qualification) + '\n').encode('ascii'))
    pin = lambda p: dict(path=str(p), bytes=p.stat().st_size, sha256=hashlib.sha256(p.read_bytes()).hexdigest())
    h.save(AREA / 'binding.json', dict(mcu=plan, gdb=pin(gdb), server=pin(server),
        definitions=pin(AREA / 'gdb-definitions.gdb'), checkpoint=CHECKPOINT, predicate=PREDICATE,
        physical='NOT_RUN', nativePipe='REJECTED_PROMPT_BUFFERING', caller=h.record(Path(__file__))))
    print('PREPARED: standard GDB commands; physical key test NOT_RUN', flush=True)


def run(mode):
    h.require(mode in ('check', 'qualify'), 'key execution is not exposed before qualification')
    binding = h.read_json(AREA / 'binding.json')
    h.pinned(binding['definitions'])
    out = h.fresh(AREA / ('gdb-' + mode + '-01'))
    env = h.environment(out)
    argv = [h.pinned(binding['gdb']), '-nx', '-nh', '--batch', '-x',
            AREA / ('gdb-definitions.gdb' if mode == 'check' else 'gdb-qualify.gdb')]
    if mode == 'check':
        argv += ['-ex', 'help p17-key-test', '-ex', 'show breakpoint auto-hw']
        result = h.command(out, 'gdb', argv, env, seconds=20)
        h.require(b'Undefined command' not in result, 'unsupported GDB definition')
        h.save(out / 'result.json', dict(outcome='GDB_DEFINITIONS_LOADED', deviceOperations=0))
        print('GDB_DEFINITIONS_LOADED', flush=True)
        return
    for root in (ROOT, Path('D:/github/my/E-Track')):
        for name in ('p34-live-device.lock', 'p35-reconcile-device.lock', 'p35-pipeline.lock'):
            h.require(not (root / '.cache' / name).exists(), 'existing owner')
    h.require(not any(h.listening(port) for port in PORTS), 'debugger port occupied')
    with h.device_owner(out):
        processes = h.command(out, 'processes', ['tasklist', '/FO', 'CSV', '/NH'], env, seconds=15)
        names = {row[0].lower() for row in csv.reader(io.StringIO(processes.decode('utf8', 'replace'))) if row}
        h.require(not names & {'uv4.exe', 'jlink.exe', 'jlinkrttlogger.exe', 'jlinkrttviewer.exe',
            'jlinkgdbserver.exe', 'jlinkgdbservercl.exe', 'jflash.exe', 'jlinkguiserver.exe'},
            'another debugger exists')
        server = h.Process(out, 'server', [h.pinned(binding['server']), '-select',
            'USB=' + str(binding['mcu']['probe_serial']), '-device', 'CORTEX-M4', '-if', 'SWD',
            '-speed', '1000', '-port', str(PORTS[0]), '-swoport', str(PORTS[1]),
            '-telnetport', str(PORTS[2]), '-rtttelnetport', str(PORTS[3]), '-localhostonly',
            '-noir', '-nohalt', '-noreset', '-nogui', '-singlerun',
            '-SettingsFile', out / 'settings.jlink', '-log', out / 'server.log'], env)
        try:
            def ready():
                h.require(server.alive(), 'GDB server exited before readiness')
                return b'Waiting for GDB connection' in (out / 'server.stdout').read_bytes()
            h.wait_for(ready, 15)
            raw = h.command(out, 'gdb', argv, env, seconds=20)
            h.require(b'p17_gdb_cpuid 410fc241' in raw.lower(),
                      'GDB CPUID not verified')
            server.wait(10)
            h.save(out / 'result.json', dict(outcome='GDB_GENERIC_CONNECTION_QUALIFIED', keyCalls=0,
                    resetCommands=0, flashCommands=0, portsClosed=not any(h.listening(port) for port in PORTS)))
            print('GDB_GENERIC_CONNECTION_QUALIFIED', flush=True)
        finally:
            server.close()


if __name__ == '__main__':
    h.require(len(sys.argv) == 2, 'one explicit mode required')
    prepare() if sys.argv[1] == 'prepare' else run(sys.argv[1])
