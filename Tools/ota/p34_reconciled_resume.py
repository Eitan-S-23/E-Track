"""One explicitly reconciled resume; the original complete-SDK gate stays strict."""
import argparse
import datetime as dt
import json
from pathlib import Path
import re
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'Tools/ota'))
import p34_app_resume as prior
import p34_nor_reconcile as reconciliation
import p34_nor_audit as audit

cli, base, host = prior.cli, prior.base, prior.host
SELF = Path(__file__).resolve()
RECONCILIATION = ROOT/'.cache/p34-nor-reconcile1/result.json'
STATUS = ROOT/'.cache/p34-host-nor-status2'
STATUS_AUDIT = ROOT/'.cache/p34-current-status-audit3/result.json'
SOURCES = list(dict.fromkeys([*prior.SOURCES, *reconciliation.SOURCES, SELF,
                             ROOT/'tests/boot/test_p34_reconciled_resume.py']))


def verify_records(store, records):
    dll = base.JLINK/'JLink_x64.dll'
    for record in records:
        path = Path(record['path'])
        if path == dll: cli.require(record['sha256'] == base.DLL_SHA, 'unbound external DLL')
        else: path = store.checked(path)
        cli.require(cli.record(path) == record, 'reconciled evidence/source drift')


def reconciliation_gate(store):
    value = store.read(RECONCILIATION)
    cli.require(value['result'] == 'JOURNAL_ARCHIVES_RECONCILED_SDK_INCOMPLETE' and
                value['historical_sdk_audit_passed'] is False and value['resume_authorized'] is False and
                value['hardware_operations'] == 0, 'explicit historical SDK gap required')
    j = value['journal']
    cli.require(j['mutation_commands'] == j['settled_mutations'] == 2576 and j['tx_payload_bytes'] == 619612 and
                j['target_writes'] == 249220 and j['nor_commands'] == 15529 and j['attempt_return_pairs'] == 127596,
                'incomplete reconciled sequence')
    cli.require(value['archives']['nor_archives'] == 8 and value['archives']['internal_images'] == 2 and
                len(value['archives']['bcb_traces']) == 2, 'incomplete archive/BCB reconstruction')
    records = [*value['evidence'], *value['sources'], cli.record(RECONCILIATION)]
    expected = {str(reconciliation.AREA/n) for n in ('sdk.log', 'events.jsonl', 'worker.json', 'parent.json', 'plan.json')}
    cli.require(expected.issubset({r['path'] for r in records}), 'original execution bindings missing')
    verify_records(store, records)
    return records


def status_gate(store):
    worker, parent, plan = (store.read(STATUS/(n+'.json')) for n in ('worker', 'parent', 'plan'))
    cli.require(plan['out'] == str(STATUS) and worker['result'] == 'HOST_NOR_STATUS_RESTORED_RETAINED' and
                worker['close_returned'] and worker['controller']['restored'] and worker['controller']['error'] is None and
                worker['nor_payload_bytes_written'] == 0 and worker['nor_write_admitted'] is False and
                worker['automatic_resume'] is False and worker['reset_performed'] is False and
                parent['exit'] == 0 and not parent['timeout'] and parent['after_history'] == plan['before_history'],
                'closed restored status-only cell required')
    rebuild = store.read(reconciliation.AREA/'parent.json')
    cli.require(dt.datetime.fromisoformat(parent['started']) > dt.datetime.fromisoformat(rebuild['ended']),
                'fresh post-rebuild status required')
    original = store.read(ROOT/'.cache/p34-entry-wfi1/worker.json')
    cli.require(worker['before']['context'] == original['context'], 'status context drift')
    cli.require(worker['status']['samples'] == [dict(sr1=0, sr2=2, jedec='ef4018')]*2,
                'exact current NOR identity/status changed')
    evidence = [cli.record(STATUS/n) for n in ('sdk.log', 'events.jsonl', 'worker.json', 'parent.json', 'plan.json')]
    for rec in plan['inputs']:
        path = store.checked(rec['path']); snap = cli.record(store.checked(STATUS/'source'/path.relative_to(ROOT)))
        cli.require((snap['bytes'], snap['sha256']) == (rec['bytes'], rec['sha256']), 'status snapshot drift')
        evidence.extend((rec, snap))
    verify_records(store, evidence)
    return worker, evidence


def audit_status(store):
    reconciled = reconciliation_gate(store)
    worker, evidence = status_gate(store)
    trace = audit.trace(STATUS, worker)
    cli.require(trace['target_writes'] == 46 and trace['mutation_commands'] == 0 and trace['nor_commands'] == 6,
                'unexpected current-status native sequence')
    evidence.extend((cli.record(SELF), cli.record(Path(audit.__file__)), *reconciled))
    verify_records(store, evidence)
    return dict(result='CURRENT_RETAINED_STATUS_SDK_AUDIT_PASS', trace=trace, evidence=evidence,
                historical_sdk_audit_passed=False, resume_authorized=False, hardware_operations=0)


def eligibility(store):
    records = reconciliation_gate(store)
    _, status_records = status_gate(store)
    current = store.read(STATUS_AUDIT)
    cli.require(current['result'] == 'CURRENT_RETAINED_STATUS_SDK_AUDIT_PASS' and
                current['historical_sdk_audit_passed'] is False and current['trace']['mutation_commands'] == 0,
                'complete fresh SDK status audit required; historical gap cannot be erased')
    required = {str(STATUS/n) for n in ('sdk.log', 'events.jsonl', 'worker.json', 'parent.json', 'plan.json')}
    required.update((str(SELF), str(Path(audit.__file__))))
    cli.require(required.issubset({r['path'] for r in current['evidence']}), 'fresh SDK input bindings missing')
    records.extend((*status_records, *current['evidence'], cli.record(STATUS_AUDIT)))
    # Duplicate records must also agree; never replace an older digest by a newer one.
    verify_records(store, records)
    return list({(r['path'], r['sha256'], r['bytes']): r for r in records}.values())


def preflight(store, out):
    cli.require(not out.exists(), 'preserve successor evidence')
    for name in (*prior.FILES, 'result.json', 'original-tests.json', 'original-tests.log',
                 'successor-tests.json', 'successor-tests.log'): store.checked(out/name)
    for path in SOURCES: store.checked(out/'source'/path.relative_to(ROOT))


def snapshot(store, out):
    inputs = [cli.record(p) for p in SOURCES]
    env = host.environment(store, out)
    for path in SOURCES: store.raw(out/'source'/path.relative_to(ROOT), path.read_bytes())
    return inputs, env


def worker(store, out):
    cli.require(base.in_job(), 'owned reconciled resume worker required')
    started = time.monotonic()
    plan = store.read(out/'plan.json')
    cli.require(plan['inputs'] == [cli.record(p) for p in SOURCES] and plan['out'] == str(out) and
                plan['route'] == 'RESUME-23-RECONCILED' and plan['historical_sdk_audit_passed'] is False,
                'reconciled worker/source scope changed')
    cli.require(plan['evidence'] == eligibility(store), 'reconciled eligibility drift')
    cli.require(time.monotonic()-started < 45, 'insufficient native observation/close headroom')
    cli.require(plan['native_history_approved'] == str(base.HISTORY), 'native history scope mismatch')
    cli.require(cli.record(base.JLINK/'JLink_x64.dll')['sha256'] == base.DLL_SHA, 'native DLL drift')
    return prior.native_worker(store, out)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('selftest', 'audit-status', 'resume', 'worker'))
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--tests', type=Path)
    parser.add_argument('--native-history-approved', type=Path)
    args = parser.parse_args()
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                'isolated root required')
    store = cli.Store(ROOT); out = store.checked(args.output_dir)
    if args.action == 'worker': return worker(store, out)
    preflight(store, out)
    inputs = [cli.record(p) for p in SOURCES]
    if args.action == 'selftest':
        inputs, env = snapshot(store, out); env['P34_TEST_OUT'] = str(out)
        counts = {}
        for tag, test in (('original-tests', 'test_p34_app_resume.py'), ('successor-tests', 'test_p34_reconciled_resume.py')):
            log = host.command(store, out, tag, [sys.executable, '-I', '-S', '-B', '-X', 'utf8', ROOT/'tests/boot'/test, '-v'], env, 180)
            match = re.search(rb'Ran (\d+) tests? in .*\r?\n\r?\nOK\b', log)
            cli.require(match is not None, 'test count missing'); counts[tag] = int(match[1])
        cli.require(inputs == [cli.record(p) for p in SOURCES], 'source drift')
        store.write(out/'result.json', dict(result='RECONCILED_RESUME_HOST_PASS', tests=counts, inputs=inputs, hardware=False))
        print('RECONCILED_RESUME_HOST_PASS', json.dumps(counts)); return 0
    if args.action == 'audit-status':
        result = audit_status(store)
        cli.require(inputs == [cli.record(p) for p in SOURCES], 'audit source changed')
        store.write(out/'result.json', result)
        print(result['result'], json.dumps(result['trace'])); return 0
    cli.require(args.native_history_approved == base.HISTORY, 'exact native history scope required')
    tests = store.read(args.tests)
    cli.require(tests['result'] == 'RECONCILED_RESUME_HOST_PASS' and tests['inputs'] == inputs, 'current tested sources required')
    started = time.monotonic(); evidence = eligibility(store); hashing_seconds = time.monotonic()-started
    cli.require(hashing_seconds < 45, 'insufficient 120s worker headroom')
    before = base.history(store); inputs, env = snapshot(store, out)
    store.write(out/'plan.json', dict(route='RESUME-23-RECONCILED', action='resume', out=str(out), inputs=inputs,
        evidence=evidence, tests=cli.record(args.tests), native_history_approved=str(base.HISTORY), before_history=before,
        historical_sdk_audit_passed=False, worker_seconds=120, native_call_seconds=5, running_observation_seconds=20,
        eligibility_hash_seconds=hashing_seconds,
        scope='Exact closed host reconciliation plus complete fresh native status audit; one no-reset original-App resume.'))
    result = base.owned_run(store, out, [SELF, 'worker', '--output-dir', out], env, timeout=120)
    result['after_history'] = base.history(store); result['presence_after'] = base.native_presence()
    result['route'] = 'RESUME-23-RECONCILED'; result['historical_sdk_audit_passed'] = False
    store.write(out/'parent.json', result); print(json.dumps(result))
    return 0 if result['exit'] == 0 and not result['timeout'] else 1


if __name__ == '__main__': raise SystemExit(main())
