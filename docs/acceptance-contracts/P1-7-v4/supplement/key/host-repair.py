"""Check corrected source syntax offline; reconcile the pre-GDB host failure."""
import importlib.util
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
AREA = Path(__file__).resolve().parent
assert Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode
sys.path.insert(0, str(ROOT / 'Tools/ota/p34-acceptance'))
import live_host as h
import live_mcu


def main():
    mode = sys.argv[1]
    h.require(mode in ('check', 'reconcile'), 'explicit mode required')
    plan = h.read_json(AREA / 'key-plan-final.json')
    out = h.checked(AREA / ('host-repair-01' if mode == 'check' else 'reconcile-01'))
    h.require(not out.exists(), 'preserve old output')
    for name in ('host', 'result.json', 'intent.json', 'lock-reconciliation.json'):
        h.checked(out / name)
    h.checked(AREA / 'key-plan-02.json')
    h.fresh(out)
    env = h.environment(out)
    if mode == 'check':
        definitions = AREA / 'gdb-definitions-04.gdb'
        entry = AREA / 'gdb-key-04.gdb'
        lines = entry.read_text(encoding='ascii').splitlines()
        h.require(lines == ['source ' + definitions.as_posix(), 'p17-key-test', 'quit'], 'entry changed scope')
        raw = h.command(out, 'gdb', [h.pinned(plan['gdb']), '-nx', '-nh', '--batch',
            '-ex', lines[0], '-ex', 'help p17-key-test'], env, seconds=20)
        h.require(b'User command' in raw, 'source did not load definitions')
        plan.update(definitions=h.record(definitions), entry=h.record(entry),
                    out=str(AREA / 'gdb-key-02'), status='PREPARED_NOT_RUN',
                    preparationHistory='gdb-key-01 source filename quoted: GDB never attached; original retained')
        h.save(AREA / 'key-plan-02.json', plan)
        h.save(out / 'result.json', dict(outcome='SOURCE_ENTRY_LOADED', deviceOperations=0,
            definitions=h.record(definitions), entry=h.record(entry)))
        print('SOURCE_ENTRY_LOADED', flush=True)
        return
    old = AREA / 'gdb-key-01'
    h.require(not h.read_json(old / 'notifications.json'), 'a human action was requested')
    for name in ('server', 'gdb'):
        h.require(h.read_json(old / (name + '.closed.json'))['cleanup_complete'], 'owned process unclosed')
    native = (old / 'server.log').read_bytes()
    h.require(b'Connected to target' in (old / 'server.stdout').read_bytes() and
              b'GDB connected' not in native and b'Received monitor command' not in native,
              'unexpected GDB activity requires a different reconciliation')
    lock = h.checked(ROOT / '.cache/p34-live-device.lock')
    previous = h.read_json(lock)
    h.require(Path(previous['out']) == old, 'foreign owner')
    adapter = ROOT / '.cache/p17-generic-readiness-20261104-01/inspect.py'
    spec = importlib.util.spec_from_file_location('p17_generic_adapter', adapter)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    original = h.command
    h.command = module.command
    try:
        with h.device_owner(out, read_only=True):
            mcu = live_mcu.MCU(plan['retained'], out)
            observed = mcu.inspect('target', 'current-identity')
            h.require(observed['registers']['freeze'] == 0, 'debug freeze not restored')
            h.save(out / 'result.json', dict(outcome='CURRENT_30313_READINESS_CONFIRMED',
                observed=observed, resetCommands=0, keyCalls=0, firmwareProgramming=0))
    finally:
        h.command = original
    h.require(h.read_json(lock) == previous, 'lock changed during reconciliation')
    h.save(out / 'lock-reconciliation.json', dict(previous=previous,
        outcome='DEAD_OWNED_LOCK_RELEASED_AFTER_FULL_READINESS', oldEvidencePreserved=True))
    lock.unlink()
    print('CURRENT_30313_READINESS_CONFIRMED; DEAD_OWNED_LOCK_RELEASED', flush=True)


if __name__ == '__main__':
    main()
