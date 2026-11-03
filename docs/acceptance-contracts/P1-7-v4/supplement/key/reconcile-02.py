"""Read actual state after the pre-call GDB expression error; do not resume."""
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
AREA = Path(__file__).resolve().parent
assert Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode
sys.path.insert(0, str(ROOT / 'Tools/ota/p34-acceptance'))
import live_host as h
import live_mcu

out = h.checked(AREA / 'reconcile-02')
h.require(not out.exists(), 'preserve previous reconciliation')
for name in ('host', 'result.json', 'previous-owner.stdout', 'previous-owner.stderr',
             'previous-owner.started.json', 'previous-owner.closed.json', 'unresolved-owner.json'):
    h.checked(out / name)
h.fresh(out)
plan = h.read_json(AREA / 'key-plan-02.json')['retained']
original = h.command


def command(folder, label, argv, env, **kwargs):
    argv = list(map(str, argv))
    if label == 'commander':
        argv[argv.index('-Device') + 1] = 'CORTEX-M4'
        script = Path(argv[argv.index('-CommandFile') + 1]).read_text(encoding='ascii')
        assert all(line in set(live_mcu.START) | {'regs', 'qc'} or line.startswith('savebin "')
                   for line in script.splitlines())
    return original(folder, label, argv, env, **kwargs)


h.command = command
try:
    with h.device_owner(out, read_only=True):
        mcu = live_mcu.MCU(plan, out)
        fields = [('dhcsr', 0xe000edf0, 4), ('vtor', 0xe000ed08, 4), ('freeze', 0xe0042008, 4),
                  ('cfsr', 0xe000ed28, 4), ('hfsr', 0xe000ed2c, 4), ('gpio', 0x40020010, 4),
                  ('hold', 0x40020c14, 4), ('boot_code', 0x080019a0, 32), ('ticks', 0x20001030, 4)]
        data, console, folder = mcu.execute(['regs', *fields], {k:s for k,_,s in fields},
                                            'actual-state', seconds=30)
        pcs = re.findall(r'\bPC\s*=\s*([0-9a-fA-F]{8})', console)
        h.require(pcs, 'actual PC unavailable')
        values = {k:int.from_bytes(v,'little') for k,v in data.items() if k != 'boot_code'}
        pc = int(pcs[-1], 16)
        h.save(out / 'result.json', dict(outcome='ACTUAL_STATE_READ', pc=pc, values=values,
            resetCommands=0, resumeCommands=0, keyCalls=0, lockRetained=True))
        print('ACTUAL_STATE', hex(pc), values, flush=True)
finally:
    h.command = original
