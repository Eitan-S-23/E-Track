"""Finite R2-A read-only checkpoint from the actual closed recovery, never OTA."""
import argparse
import ctypes
import json
import os
from pathlib import Path
import re
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'Tools/ota'))
import p34_r2_checkpoint_device as owner
import p34_install_offline_audit as evidence

cli, host, base = owner.cli, owner.host, owner.base
SELF = Path(__file__).resolve()
RECOVERY = ROOT / '.cache/p34-recovery-continue1'
AUDIT = ROOT / '.cache/p34-recovery-continue-audit1/result.json'
REVIEW = ROOT / '.cache/p34-recovery-continue1-independent-review1/result.json'
OWNER_TESTS = ROOT / '.cache/p34-r2-checkpoint-owner-tests2/result.json'
ASSETS = dict(image=ROOT / '.cache/p34-recovery-sources1/r2-a.bin',
    boot=ROOT / '.cache/p34-native-acquire1/boot-readback.bin',
    map_bytes=ROOT / '.cache/p34-early-usb-r2/on/b/app-gcc/X-Track-App-GCC.map')
SCOPE = 'R2-A30276 full image/original Boot/health; no halt/reset/EEPROM/NOR/phone/target payload stores'
WORKER_SECONDS, PARENT_SECONDS = 900, 1020


def validate_predecessor(review, audit, worker, parent, plan):
    cli.require(review['schema'] == 'p34-independent-closed-continuation-review/v1' and
        review['result'] == 'CLOSED_CONTINUATION_AND_R2A_HEALTH_INDEPENDENT_REVIEW_PASS' and
        review['independent_full_transport_replay'] is True and
        review['runtime_health_independently_reconciled'] is True and
        review['runtime_health']['original_sdk_bound'] is True, 'independent closed recovery health required')
    cli.require(audit['result'] == 'INSTALL_TRANSPORT_ARCHIVES_AUDIT_PASS' and
        audit['terminal_idle_checked'] is True and audit['programmed_sectors'] == 300 and
        worker['result'] == 'R2_INSTALLED_ORIGINAL_BOOT_CLOSED' and worker['close_returned'] is True and
        worker['sources_unchanged_after_close'] is True and worker['final_trace']['native_close_completed'] == 1,
        'actual closed complete recovery required')
    cli.require(parent['exit'] == 0 and parent['timeout'] is False and
        not parent['presence_after']['debugger_processes'] and parent['after_history'] == plan['before_history'] and
        review['original_hardware_run'] == parent, 'recovery owner/history unresolved')
    cli.require(review['reviewed_source_inputs'] == audit['strict_inputs'] == plan['inputs'] and
        review['original_inputs'] == audit['inputs'][:4] and
        review['original_logs'] == worker['logs'] == audit['logs'] and len(worker['logs']) == 721 and
        review['original_archives'] == worker['archives'] == audit['archives'] and len(worker['archives']) == 29,
        'independent recovery bindings disagree')
    for key in ('native_calls', 'target_reads', 'target_writes'):
        cli.require(review[key] == audit[key], 'recovery native accounting differs')
    expected_sha = '7445ef63d5f4cbef95761f27075333d7d09c9d43585a28b84e6575ccfb274fcf'
    cli.require(review['continuation']['image_version'] == 30276 and
        review['continuation']['image_sha256'] == expected_sha and
        review['reset_release']['native_close_completed'] is True and
        review['reset_release']['tar_csw_dp_restored'] is True and
        all(worker['dap'][k] is True for k in ('tar_restored', 'csw_restored', 'dp_restored')) and
        review['historical_sdk_audit_passed'] is False and
        review['recovery_establishes_r2_backup'] is False, 'R2 predecessor identity/scope differs')


def predecessor(store):
    review, audit = store.read(REVIEW), store.read(AUDIT)
    worker, parent, plan = (store.read(RECOVERY / (n + '.json')) for n in ('worker', 'parent', 'plan'))
    validate_predecessor(review, audit, worker, parent, plan)
    cli.require(review['root_receipt_crosscheck'] == cli.record(AUDIT), 'reviewed root audit changed')
    items = [*audit['inputs'], *audit['logs'], *audit['archives'].values(),
             review['audit_execution']['source'], review['audit_execution']['terminal_output'],
             review['publication_script']]
    records = list({r['path']: r for r in items}.values())
    for item in records:
        cli.require(evidence.record(store.checked(item['path'])) == item, 'original recovery evidence changed')
    return dict(kind='CLOSED_RECOVERY_R2A', review=cli.record(REVIEW), audit=cli.record(AUDIT),
        worker=cli.record(RECOVERY / 'worker.json'), parent=cli.record(RECOVERY / 'parent.json'),
        version=30276, image_sha256=review['continuation']['image_sha256'],
        historical_ota_predecessor=False, evidence_records=records)


def validate_worker_plan(store, plan, out, current):
    cli.require(plan['out'] == str(out) and plan['scope'] == SCOPE and plan['inputs'] == current,
                'source-bound recovery checkpoint plan changed')
    test_record = plan['tests']
    test_path = store.checked(test_record['path'])
    cli.require(cli.record(test_path) == test_record, 'capture selftest receipt changed')
    tested = store.read(test_path)
    cli.require(tested['result'] == 'R2_CHECKPOINT_CAPTURE_HOST_PASS' and tested['hardware'] is False and
                tested['inputs'] == current, 'current capture selftests required in worker')
    proof = plan['predecessor']
    review, audit = store.read(REVIEW), store.read(AUDIT)
    worker, parent, original_plan = (store.read(RECOVERY / (n + '.json')) for n in ('worker', 'parent', 'plan'))
    validate_predecessor(review, audit, worker, parent, original_plan)
    cli.require(proof['kind'] == 'CLOSED_RECOVERY_R2A' and proof['version'] == 30276 and
        proof['image_sha256'] == review['continuation']['image_sha256'] and
        proof['historical_ota_predecessor'] is False and proof['review'] == cli.record(REVIEW) and
        proof['audit'] == cli.record(AUDIT) == review['root_receipt_crosscheck'] and
        proof['worker'] == cli.record(RECOVERY / 'worker.json') and
        proof['parent'] == cli.record(RECOVERY / 'parent.json'), 'compact recovery predecessor differs')
    cli.require(plan['worker_seconds'] == WORKER_SECONDS and plan['parent_seconds'] == PARENT_SECONDS and
        plan['connection_generation'] == 'r2-checkpoint-' + out.name and
        plan['before_history'] == base.history(store), 'checkpoint lifetime/generation/history differs')


def sources(store):
    tested = store.read(OWNER_TESTS)
    paths = owner.sources(store)
    cli.require(tested['result'] == 'R2_CHECKPOINT_OWNER_HOST_PASS' and
                tested['inputs'] == [cli.record(p) for p in paths], 'current checkpoint owner tests required')
    return list(dict.fromkeys([*paths, SELF, OWNER_TESTS,
        ROOT / 'Tools/ota/p34_install_offline_audit.py', ROOT / 'tests/boot/test_p34_r2_checkpoint_capture.py',
        REVIEW, AUDIT, *(RECOVERY / (n + '.json') for n in ('plan', 'worker', 'parent')),
        *ASSETS.values()]))


def worker(store, out):
    cli.require(base.in_job(), 'owned read-only checkpoint worker required')
    plan = store.read(out / 'plan.json')
    validate_worker_plan(store, plan, out, [cli.record(p) for p in sources(store)])
    cli.require(plan['native_history_approved'] == str(base.HISTORY) and
        cli.record(base.JLINK / 'JLink_x64.dll')['sha256'] == base.DLL_SHA, 'native scope/DLL changed')
    for name in (*owner.LOGS, 'events.jsonl', 'callbacks.log', 'project.jlink', 'app.bin', 'boot.bin', 'worker.json'):
        cli.require(not store.checked(out / name).exists(), 'preserve checkpoint; worker cannot replay')
    assets = {k: p.read_bytes() for k, p in ASSETS.items()}
    deadline = time.monotonic() + WORKER_SECONDS
    dap = observation = None
    result = dict(result='FAILED', close_returned=False)
    archives = {}
    with (out / 'events.jsonl').open('x', encoding='utf-8') as stream, (out / 'callbacks.log').open('xb') as callbacks:
        initial = []
        def persist(event, **fields):
            stream.write(json.dumps(dict(time=cli.now(), event=event, **fields)) + '\n')
            stream.flush()
            if event == 'online-log-sealed':
                os.fsync(stream.fileno())
                print('SEALED', fields['index'], flush=True)
        def collect(event, **fields):
            persist(event, **fields)
            initial.append(dict(event=event, **fields))
        def archive(name, raw):
            cli.require(name in ('app', 'boot') and name not in archives, 'fixed one-pass checkpoint archives required')
            expected = assets['image' if name == 'app' else 'boot']
            cli.require(raw == expected, 'checkpoint archive identity differs')
            item = store.raw(out / (name + '.bin'), raw)
            cli.require(cli.record(item['path']) == item, 'durable checkpoint archive changed')
            archives[name] = item
        try:
            cli.require(not base.native_presence()['debugger_processes'], 'competing debugger present')
            with os.add_dll_directory(str(base.JLINK)):
                sdk = base.guarded(ctypes.CDLL, str(base.JLINK / 'JLink_x64.dll'))
                dap = base.Dap(sdk, out / owner.LOGS[0], out / 'project.jlink', callbacks)
                dap.sdk = owner.JournalSDK(sdk, collect)
                observation = base.Observation(dap, collect, seconds=600)
                result = owner.execute(dap, observation, persist, initial,
                    [out / n for n in owner.LOGS], cli.record, lambda: deadline-time.monotonic(),
                    archive, **assets, connection_generation=plan['connection_generation'])
        except BaseException as error:
            result['result'] = 'FAILED'
            result['outer_error'] = type(error).__name__ + ': ' + str(error)
            try:
                if observation is not None: observation.close()
                elif dap is not None and dap._opened: dap.close()
            except BaseException as close: result['outer_close_error'] = str(close)
        result['archives'] = archives
        try:
            result['sources_unchanged_after_close'] = plan['inputs'] == [cli.record(p) for p in sources(store)]
        except BaseException as error:
            result.update(sources_unchanged_after_close=False, source_check_error=str(error))
        if not result['sources_unchanged_after_close']: result['result'] = 'FAILED'
        store.write(out / 'worker.json', result)
    print(result['result'], flush=True)
    return 0 if result['result'] == 'R2_CHECKPOINT_NATIVE_CLOSED' else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('selftest', 'capture', 'worker'))
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--tests', type=Path)
    parser.add_argument('--native-history-approved', type=Path)
    args = parser.parse_args()
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                'isolated explicit root required')
    store = cli.Store(ROOT)
    out = store.checked(args.output_dir)
    if args.action == 'worker': return worker(store, out)
    inputs = sources(store)
    owner.preflight(store, out, inputs)
    records = [cli.record(p) for p in inputs]
    if args.action == 'capture':
        cli.require(args.native_history_approved == base.HISTORY, 'exact native history permission required')
        tests = store.read(args.tests)
        cli.require(tests['result'] == 'R2_CHECKPOINT_CAPTURE_HOST_PASS' and tests['inputs'] == records,
                    'current capture host tests required')
        proof = predecessor(store)
        before = base.history(store)
        cli.require(not base.native_presence()['debugger_processes'], 'competing debugger present')
    env = host.environment(store, out)
    for source in inputs: store.raw(out / 'source' / source.relative_to(ROOT), source.read_bytes())
    if args.action == 'selftest':
        log = host.command(store, out, 'tests', [sys.executable, '-I', '-S', '-B', '-X', 'utf8',
            ROOT / 'tests/boot/test_p34_r2_checkpoint_capture.py', '-v'], env, 120)
        count = re.search(rb'Ran (\d+) tests? in .*\r?\n\r?\nOK\b', log)
        cli.require(count and records == [cli.record(p) for p in inputs], 'capture test/source drift')
        store.write(out / 'result.json', dict(result='R2_CHECKPOINT_CAPTURE_HOST_PASS', tests=int(count[1]),
                                            inputs=records, hardware=False))
        print('R2_CHECKPOINT_CAPTURE_HOST_PASS', int(count[1])); return 0
    store.write(out / 'plan.json', dict(out=str(out), inputs=records, tests=cli.record(args.tests),
        scope=SCOPE, predecessor=proof, native_history_approved=str(base.HISTORY), before_history=before,
        worker_seconds=WORKER_SECONDS, parent_seconds=PARENT_SECONDS,
        connection_generation='r2-checkpoint-' + out.name))
    result = base.owned_run(store, out, [SELF, 'worker', '--output-dir', out], env, timeout=PARENT_SECONDS)
    result.update(after_history=base.history(store), presence_after=base.native_presence())
    store.write(out / 'parent.json', result)
    print(json.dumps(result))
    return 0 if result['exit'] == 0 and not result['timeout'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
