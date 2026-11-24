"""Resume the unchanged App only after independently audited recovery provisioning."""
import argparse
import ctypes
import json
import os
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'Tools/ota'))
import p34_host_nor_mapped as prior
from recovery_entry import app_resume as ar, host_nor as hn
from recovery_entry.control_probe import Control
from recovery_entry.owner_probe import Reader

base, cli, host = prior.base, prior.cli, prior.host
SELF = Path(__file__).resolve()
SOURCES = list(dict.fromkeys([*prior.SOURCES, SELF, *(ROOT/n for n in (
    'Tools/ota/recovery_entry/app_resume.py', 'tests/boot/test_p34_app_resume.py',
    '.cache/p34-app-handoff/disassembly.log',
    '.cache/p34-sha-candidate/f/vendor/CMSIS/Include/core_cm4.h'))]))
FILES = prior.FILES
REBUILD = ROOT/'.cache/p34-host-nor-rebuild1'


def audit_bindings(store, audit, required):
    records = audit['traces'][-1].get('evidence', [])
    cli.require(set(map(str, required)).issubset({r['path'] for r in records}), 'audit lacks consumed input bindings')
    records = [*records, audit['script']]
    for record in records:
        cli.require(cli.record(store.checked(record['path'])) == record, 'post-audit input/script drift')
    return records


def recovery_inputs(store, audit_path):
    worker, parent = store.read(REBUILD/'worker.json'), store.read(REBUILD/'parent.json')
    cli.require(parent['exit'] == 0 and not parent['timeout'] and
                worker['result'] == 'RECOVERY_30276_VERIFIED_ORIGINAL_APP_HALTED' and worker['close_returned'] and
                worker['controller']['restored'] and worker['controller']['error'] is None and
                worker['controller']['mutations'] == 2576, 'fully verified closed recovery required')
    cli.require(worker['transaction']['native_result'] == 0 and worker['transaction']['callback_error'] is None,
                'recovery C core not verified')
    records = [cli.record(REBUILD/(name+'.json')) for name in ('worker', 'parent', 'plan', 'preimages', 'admission')]
    records += [worker['slot'], worker['boot_after'], worker['app_after'], worker['bcb_before']['raw'], worker['bcb_after']['raw']]
    for name in ('candidate-backup', 'tail', 'staging', 'recovery'):
        records.extend([worker['protected_before'][name], worker['protected_after'][name]])
        if name != 'recovery':
            cli.require(worker['protected_before'][name]['sha256'] == worker['protected_after'][name]['sha256'], 'protected NOR mismatch')
    cli.require(worker['bcb_before']['raw']['sha256'] == worker['bcb_after']['raw']['sha256'], 'BCB mismatch')
    for name, path in (('boot', '.cache/p34-native-acquire1/boot-readback.bin'),
                       ('app', '.cache/p34-native-image1/app-readback.bin')):
        cli.require(worker[name+'_after']['sha256'] == cli.record(ROOT/path)['sha256'], 'original internal image mismatch')
    admission = store.read(REBUILD/'admission.json')
    cli.require(admission['exit'] == 0 and cli.record(REBUILD/'admission.log') == admission['log'], 'Boot admission log drift')
    cli.require('RECOVERY_ADMISSION result=0' in (REBUILD/'admission.log').read_text() and
                'version=30276' in (REBUILD/'admission.log').read_text(), 'Boot admission missing')
    records.append(admission['log'])
    audit = store.read(audit_path)
    cli.require(audit['result'] == 'NOR_SDK_JOURNAL_AUDIT_PASS' and
                audit['traces'][-1]['area'] == 'p34-host-nor-rebuild1' and
                audit['traces'][-1]['trace']['mutation_commands'] == 2576 and
                audit['traces'][-1]['physical_files']['nor_archives'] == 8,
                'complete physical SDK/journal audit required')
    records += audit_bindings(store, audit, [REBUILD/'sdk.log', REBUILD/'events.jsonl', REBUILD/'worker.json',
        *(Path(r['path']) for r in [worker['boot_after'], worker['app_after'], worker['bcb_before']['raw'], worker['bcb_after']['raw'],
                                  *worker['protected_before'].values(), *worker['protected_after'].values()])])
    records.append(cli.record(audit_path))
    for item in records:
        cli.require(cli.record(store.checked(item['path'])) == item, 'recovery artifact drift')
    return records


def preflight(store, out):
    cli.require(not out.exists(), 'preserve resume evidence')
    for n in FILES: store.checked(out/n)
    for p in SOURCES: store.checked(out/'source'/p.relative_to(ROOT))


def snapshot(store, out):
    inputs = [cli.record(p) for p in SOURCES]; env = host.environment(store, out)
    for p in SOURCES: store.raw(out/'source'/p.relative_to(ROOT), p.read_bytes())
    return inputs, env


def worker(store, out):
    cli.require(base.in_job(), 'owned resume worker required')
    plan = store.read(out/'plan.json')
    cli.require(plan['inputs'] == [cli.record(p) for p in SOURCES] and plan['out'] == str(out), 'resume source drift')
    cli.require(plan['recovery'] == recovery_inputs(store, Path(plan['audit'])), 'recovery eligibility drift')
    cli.require(plan['native_history_approved'] == str(base.HISTORY), 'history scope mismatch')
    cli.require(cli.record(base.JLINK/'JLink_x64.dll')['sha256'] == base.DLL_SHA, 'SDK drift')
    return native_worker(store, out)


def native_worker(store, out):
    cli.require(base.in_job(), 'owned native resume worker required')
    for n in FILES: store.checked(out/n)
    result = dict(result='FAILED', reset_performed=False, close_returned=False, recovery_version=30276,
                  original_app_version=30275, sysTick_countflag_read_clear=True)
    control, dap, port = None, None, None
    with (out/'events.jsonl').open('x', encoding='utf-8') as events, (out/'callbacks.log').open('xb') as callbacks:
        def emit(event, **fields):
            events.write(json.dumps(dict(time=cli.now(), event=event, **fields))+'\n'); events.flush()
        try:
            presence = base.native_presence(); emit('presence', **presence)
            cli.require(not presence['debugger_processes'], 'another debugger present')
            with os.add_dll_directory(str(base.JLINK)):
                sdk = base.guarded(ctypes.CDLL, str(base.JLINK/'JLink_x64.dll'))
                dap = base.Dap(sdk, out/'sdk.log', out/'project.jlink', callbacks)
                observation = base.Observation(dap, emit, seconds=50)
                image = (ROOT/'.cache/p34-native-image1/app-readback.bin').read_bytes()
                control = Control(dap, observation, emit, image[0x400:0x460], retained=True)
                observation.connect()
                original = store.read(ROOT/'.cache/p34-entry-wfi1/worker.json')
                result['initial'] = control.initial()
                cli.require(result['initial']['dhcsr_control'] == 3 and result['initial']['comparators'] == [0]*6,
                            'unexpected halt controls/comparators')
                result['before'] = control.observe_retained(original)
                result['owners_before'] = prior.prior.prior.owners(control, dap, emit)
                for sample in result['before']['state_samples']:
                    raw = sample['raw']
                    cli.require((raw['wdt_div'], raw['wdt_rld'], raw['wdt_win'], raw['wdt_sts']) == (5, 3124, 4095, 0),
                                'watchdog tuple changed')
                qspi = Reader(dap, emit).qspi()
                qspi['qspi_xip3'] &= ~8
                cli.require(all(qspi[k] == v for k, v in hn.CONFIG.items()), 'restored QSPI configuration changed')
                vectors = dap.read_flash(0x08010000, 524)
                cli.require(vectors == image[:524], 'original vectors changed')
                cli.require(control.context() == original['context'], 'retained context/reset latch changed before resume')
                port = ar.Port(dap, emit, image[0x400:0x460])
                result['resume'] = ar.execute(port, vectors)
                observation._check()
                result['result'] = result['resume']['result']
        except BaseException as error:
            result['error'] = type(error).__name__+': '+str(error)
        finally:
            if port: result['last_state'] = dict(attempted=port.attempted, returned=port.returned,
                reset_seen=port.reset_seen, last_snapshot=port.last_snapshot)
            try:
                if control: control.close()
            except BaseException as error:
                result.update(result='FAILED', close_error=type(error).__name__+': '+str(error))
            result['close_returned'] = bool(dap and dap.close_returned)
            if dap: result['dap'] = dap.metadata
            store.write(out/'worker.json', result)
    print(json.dumps(result))
    return 0 if result['result'] in ('ORIGINAL_APP_RESUMED_STABLE', 'ORIGINAL_APP_RUNNING_AFTER_UNCERTAIN_RESUME') and result['close_returned'] else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('selftest', 'resume', 'worker'))
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--tests', type=Path)
    parser.add_argument('--audit', type=Path)
    parser.add_argument('--native-history-approved', type=Path)
    args = parser.parse_args()
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode, 'isolated root required')
    store = cli.Store(ROOT); out = store.checked(args.output_dir)
    if args.action == 'worker': return worker(store, out)
    preflight(store, out); inputs = [cli.record(p) for p in SOURCES]
    if args.action == 'selftest':
        inputs, env = snapshot(store, out); env['P34_TEST_OUT'] = str(out)
        log = host.command(store, out, 'tests', [sys.executable, '-I', '-S', '-B', '-X', 'utf8',
                           ROOT/'tests/boot/test_p34_app_resume.py', '-v'], env, 120)
        match = re.search(rb'Ran (\d+) tests? in .*\r?\n\r?\nOK\b', log)
        cli.require(match and inputs == [cli.record(p) for p in SOURCES], 'resume test/source drift')
        store.write(out/'result.json', dict(result='APP_RESUME_HOST_PASS', tests=int(match[1]), inputs=inputs, hardware=False))
        print('APP_RESUME_HOST_PASS', int(match[1])); return 0
    cli.require(args.native_history_approved == base.HISTORY, 'exact history scope required')
    tests = store.read(args.tests)
    cli.require(tests['result'] == 'APP_RESUME_HOST_PASS' and tests['inputs'] == inputs, 'bound resume tests required')
    recovery = recovery_inputs(store, args.audit)
    before = base.history(store); inputs, env = snapshot(store, out)
    store.write(out/'plan.json', dict(action='resume', out=str(out), inputs=inputs, recovery=recovery,
        audit=str(store.checked(args.audit)), tests=cli.record(args.tests), native_history_approved=str(base.HISTORY),
        before_history=before, worker_seconds=60, native_call_seconds=5, running_observation_seconds=20,
        scope='RESUME-22: one DHCSR A05F0001 only after closed verified recovery; no retry/reset/feed/PC/SP writes'))
    result = base.owned_run(store, out, [SELF, 'worker', '--output-dir', out], env, timeout=60)
    result['after_history'] = base.history(store); result['presence_after'] = base.native_presence()
    store.write(out/'parent.json', result); print(json.dumps(result))
    return 0 if result['exit'] == 0 and not result['timeout'] else 1


if __name__ == '__main__': raise SystemExit(main())
