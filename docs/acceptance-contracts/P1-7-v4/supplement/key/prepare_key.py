"""Bind final key-window scripts without executing them or changing prior inputs."""
import hashlib
import importlib.util
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
AREA = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('key_method_definition', AREA / 'gdb_method.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
h = m.h


def main():
    binding = h.read_json(AREA / 'binding.json')
    old = h.pinned(binding['definitions']).read_text(encoding='ascii')
    h.require(h.read_json(AREA / 'gdb-qualify-01/result.json')['outcome'] ==
              'GDB_GENERIC_CONNECTION_QUALIFIED', 'standard transport not qualified')
    post = h.read_json(ROOT / '.cache/p17-gdb-post-20261104-01/inspect-01/result.json')
    h.require(post['outcome'] == 'CURRENT_30313_READINESS_CONFIRMED', 'post-GDB health not confirmed')
    code = old
    registers = ('msp', 'psp', 'primask', 'basepri', 'faultmask', 'control')
    gates = m.check('$primask == 0 && $basepri == 0 && $faultmask == 0 && $control == 0', 'interrupt_context')
    gates += m.check('($xpsr & 0x1ff) == 0 && ($xpsr & 0x01000000) != 0', 'thread_thumb_context')
    gates += m.check(f'({m.word(0xE000E010)} & 7) == 7', 'systick_enabled')
    gates += m.check(f'({m.word(0x40020000)} >> 30) == 0 && ({m.word(0x4002000C)} >> 30) == 1', 'key_gpio_input_pullup')
    gates += m.check(f'{m.word(0x0800003C)} == 0x08001e45', 'bound_systick_vector')
    gates += [f'set $p17_saved_{name} = ${name}' for name in registers]
    marker = 'set $p17_saved_r0 = $r0\n'
    h.require(code.count(marker) == 1, 'unexpected context-save structure')
    code = code.replace(marker, '\n'.join(gates) + '\n' + marker)
    for branch in ('long', 'short'):
        marker = f'if !($p17_result_{branch} == '
        index = code.index(marker)
        checks = []
        for name in registers:
            checks += m.check(f'${name} == $p17_saved_{name}', 'call_special_' + name)
        code = code[:index] + '\n'.join(checks) + '\n' + code[index:]
    h.require(code.count('monitor reset\n') == 1 and code.count(f'0x{m.PREDICATE:08x})()') == 2,
              'unexpected reset/call count')
    h.require('monitor flash breakpoints = 0' in code and 'loadbin' not in code and 'loadfile' not in code,
              'Flash operation in key definition')
    definitions = AREA / 'gdb-definitions-02.gdb'
    entry = AREA / 'gdb-key-02.gdb'
    h.raw(definitions, code.encode('ascii'))
    h.raw(entry, (f'source {m.quote(definitions)}\np17-key-test\nquit\n').encode('ascii'))
    pin = lambda path: dict(path=str(path), bytes=path.stat().st_size,
                            sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    h.save(AREA / 'key-plan.json', dict(status='PREPARED_NOT_RUN', scope='isolated physical predicate observation',
        gdb=binding['gdb'], server=binding['server'], definitions=pin(definitions), entry=pin(entry),
        retained=binding['mcu'], postRead=h.record(ROOT / '.cache/p17-gdb-post-20261104-01/inspect-01/result.json'),
        out=str(AREA / 'gdb-key-01'), ports=m.PORTS, overallSeconds=240, perUserWaitSeconds=60,
        userActions=['Hold power key after the App is stopped and the hold signal is sent.',
                     'Release on the release signal after the long predicate returns.',
                     'On the short signal, press for about one second and release.'],
        operations=dict(reset=1, predicateCalls=2, firmwareProgramming=0, persistentStateEdits=0),
        recovery='On any unexpected stop/timeout, close owned processes, retain the lock and reconcile the actual PC/state before resuming. Do not assume disconnect alone leaves the MCU halted.',
        success='Both predicate results, tick durations and complete CPU context checks pass; restore scratch/debug freeze, resume normal Boot, then independently verify App/Boot and health.',
        limitations='The controlled calls themselves are not yet physically qualified or formal acceptance. Native GDB attachment does briefly halt the MCU.'))
    print('PREPARED_NOT_RUN: bound long/short key calls, interrupt/context guards, restoration and user stages', flush=True)


if __name__ == '__main__':
    main()
