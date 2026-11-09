"""Frozen P5 native state cells, verified restoration and bounded BLE blocks."""
import argparse
import copy
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import shlex
import struct
import sys
import time
import threading

sys.path.insert(0, str(Path(__file__).resolve().parent))
import state_chain as sc
import observation as obs
import functional_sample
import benchmark
import v2
from observation import r
h, m = sc.h, sc.m

RUNNERS = [
    'Tools/ota/p51-acceptance/run.py', 'Tools/ota/p51-acceptance/state_chain.py',
    'Tools/ota/p51-acceptance/benchmark.py',
    'Tools/ota/p51-acceptance/v2.py',
    'Tools/ota/p51-acceptance/fixture.py',
    'Tools/ota/p51-benchmark-inputs.py', 'Tools/ota/p51-benchmark-inputs.json',
    'Tools/ota/p51-normal-staging-inputs.py', 'Tools/ota/p51-normal-staging-inputs.json',
    'Tools/ota/p51-normal-inputs.py', 'Tools/ota/p51-normal-inputs.json',
    'Tools/ota/p51-package.py', 'Tools/ota/p51-candidate-inputs.json',
    'Tools/ota/p51-start-state-inputs.json', 'Tools/ota/p34-acceptance/encoding.py', 'Tools/etu_pack.py',
    'Tools/ota/p51-acceptance/functional_sample.py', '.github/scripts/firmware-byte-check.py',
    'Tools/etu_unpack.py', 'Tools/jlink/prepare-bootstrap-app.py',
    'Tools/ota/p51-acceptance/observation.py', 'Tools/ota/p34-acceptance/live_host.py',
    'Tools/ota/p34-acceptance/live_mcu.py', 'Tools/ota/p34-acceptance/live_phone.py',
    'Tools/ota/p34-acceptance/build.py', 'Tools/flutter/dev_checks.py',
    '.agents/skills/e-track-flutter-debug/scripts/host_io.py',
    'Tools/ota/p35-automation/runner.py', 'Tools/ota/p35-automation/smoke.py',
    'Tools/ota/p35-automation/live_stream.py', 'Tools/ota/p35-automation/logcat_binary.py',
    'Tools/ota/p35-automation/pipeline_cloud.py',
    'Tools/ota/p3-4-link-stats/acceptance_stats.py', 'Tools/ota/p3-4-link-stats/observation_capture.py',
    'Tools/ota/p3-4-link-stats/batch_timing.py', 'Tools/ota/p3-3-service/service.py',
    'Tools/ota/p34-acceptance/live.py', 'Tools/ota/p34-acceptance/metrics.py',
    'Tools/provenance/manifest_profiles.json', 'Tools/acceptance/validate_bundle.py']


def validate(plan, *, require_fixture=True):
    h.require(plan['schema'] == 1 and plan['task'] == 'P5-1', 'not a P5 execution input')
    mcu, phone = plan['mcu'], plan['phone']
    is_benchmark = 'benchmark' in plan
    h.require(mcu['probe_serial'] == 123456 and phone['phone']['serial'] == '10ADA4197U001CK' and
              phone['phone']['model'] == 'V2312A' and phone['phone']['adb_port'] == 5093 and
              phone['app']['release'] is True and
              phone['device']['address'] == 'e3:49:e1:14:d6:cb', 'device scope changed')
    if not is_benchmark:
        h.require(phone['app']['id'] == 'com.wen.gaia.gaia.p35acceptance' and phone['app']['version_code'] == 98,
                  'functional APK98 scope changed')
    h.require(mcu['boot']['bytes'] == 65536 and mcu['boot']['sha256'] ==
              '01e4b9e162bfaaf9fda070aa13c0cec3f377b8d696db01f731e0ab3d1464e527', 'group16 Boot mismatch')
    for pin in (mcu['boot'], mcu['package'], phone['phone']['adb'], phone['phone']['adb_key'],
                plan['apk'], plan['notify_cli'], *mcu['tools'].values(), *plan['tool_dependencies']):
        h.pinned(pin)
    if not is_benchmark:
        h.require(plan['apk']['sha256'] == phone['app']['sha256'] ==
                  'b0a5cd5cbb45ba7e75ad492b65d4843ef70c33fbda365abaea495c48b3ebbcf1', 'APK98 identity changed')
    for role in ('base', 'target', 'restore'):
        for pin in mcu['images'][role].values():
            h.pinned(pin)
    for role, field in (('base', 'current'), ('target', 'target')):
        raw = h.pinned(mcu['images'][role]['image']).read_bytes()
        h.require(plan['firmware'][field] == dict(version=struct.unpack_from('<I', raw, 0x408)[0],
            sha256=hashlib.sha256(raw).hexdigest()), 'image/header input mismatch')
    h.require(plan['firmware']['package'] == mcu['package'] and
              plan['firmware']['target']['version'] > plan['firmware']['current']['version'], 'package/direction mismatch')
    h.require(3000 <= phone['limits']['total_seconds'] <= 5400 and phone['limits']['cleanup_seconds'] == 180,
              'phone observation/cleanup budget changed')
    if is_benchmark:
        benchmark.validate(plan, require_fixture=require_fixture)
    return plan


def validate_live(plan):
    v2.live_plan(plan)
    return validate(plan)


def validate_functional_patch(plan):
    functional_sample.validate(plan, h)


def invocation(command, argv):
    parts = shlex.split(command)
    h.require(parts[1:7] == ['-I', '-S', '-B', '-X', 'utf8', 'Tools/ota/p51-acceptance/run.py'],
              'frozen isolated entry required')
    def normal(args):
        args = list(args)
        for i, value in enumerate(args[:-1]):
            if value in ('--inputs', '--out', '--contract', '--matrix', '--previous', '--observe-root'):
                args[i+1] = os.path.normcase(str((h.ROOT / args[i+1]).resolve()))
        return args
    h.require(normal(parts[7:]) == normal(argv), 'actual invocation differs from frozen command')


def gate(args, out):
    h.require(args.contract and args.matrix and args.command_id, 'formal contract/matrix/command ID required')
    contract = h.read_json(args.contract)
    h.require(contract['task_id'] == 'P5-1' and contract['status'] == 'FROZEN' and
              contract['approved_by'] and contract['approved_at'], 'P5 contract not frozen')
    commands = [row for row in contract['commands'] if row['id'] == args.command_id]
    h.require(len(commands) == 1 and set(RUNNERS) <= set(commands[0]['runner_paths']), 'incomplete runner closure')
    invocation(commands[0]['command'], sys.argv[1:])
    digest = hashlib.sha256(args.inputs.read_bytes()).hexdigest()
    h.require(any(row['fingerprint'] == 'sha256:' + digest for row in contract['external_inputs']),
              'execution input is not frozen')
    h.command(out, 'contract-precheck', [sys.executable, '-I', '-S', '-B', '-X', 'utf8',
        h.ROOT / 'Tools/acceptance/validate_bundle.py', '--contract', args.contract,
        '--matrix', args.matrix, '--repo-root', h.ROOT, *predecessor_arguments(contract)], h.environment(out), seconds=120)


def predecessor_arguments(contract):
    if contract['version'] == 1:
        return []
    prior = contract.get('predecessor_bundle')
    h.require(isinstance(prior, dict) and set(prior) == {'contract', 'matrix'}, 'successor must bind its actual predecessor')
    arguments = ['--previous-contract', h.pinned(prior['contract']), '--previous-matrix', h.pinned(prior['matrix'])]
    sources = contract.get('reuse_sources', [])
    h.require(isinstance(sources, list), 'reuse sources must be pinned contract/matrix pairs')
    for source in sources:
        h.require(isinstance(source, dict) and set(source) == {'contract', 'matrix'}, 'unbound reuse source')
        arguments += ['--reuse-source', h.pinned(source['contract']), h.pinned(source['matrix'])]
    return arguments


@contextmanager
def channel(plan, out, enabled):
    if not enabled:
        yield
        return
    if 'benchmark' in plan:
        benchmark.check_fixture(plan, out / 'fixture-check')
        yield
        return
    import pipeline_cloud as c
    client = c.Cloud(plan['cloud']['config'], out / 'cloud', h)
    client.login()
    original = client.channels()
    target = plan['cloud']['target']
    h.require(next(row for row in client.releases() if row['releaseId'] == target['releaseId']) == target,
              'registered candidate changed')
    h.require(original['stable']['currentReleaseId'] != target['releaseId'], 'candidate already active; reconcile ownership')
    h.save(out / 'channels-before.json', original)
    try:
        h.save(out / 'channel-publish-intent.json', dict(target=target['releaseId'], before=original))
        client.mutate(original, target['releaseId'], 'publish')
        yield
    finally:
        restored = client.restore(original, target)
        h.save(out / 'channels-restored.json', restored)
        client.auth.clear()


def invite(phone, plan, channel, before, armed):
    phone.phase('upgrade-ready', 120)
    phone.pump_stream()
    if channel == 'ble':
        r.bound(phone.live[-1], dict(firmware=plan['firmware']), package=True)
        text = '\u73b0\u5728\u8bf7\u53ea\u70b9\u4e00\u6b21\u201c\u5f00\u59cb\u5347\u7ea7\u201d\u3002\u4fdd\u6301 App \u524d\u53f0\u548c\u8fde\u63a5\uff0c\u4e0d\u53d6\u6d88\u3001\u4e0d\u91cd\u8bd5\u3001\u4e0d\u56de\u804a\u5929\u3002'
    else:
        text = ('\u677f\u7aef\u91c7\u96c6\u5df2\u5c31\u7eea\u3002\u8bf7\u5728\u677f\u5b50\u7684\u56fa\u4ef6\u5bfc\u5165\u9875\u9009\u62e9 ' + plan['sd_path'] +
            '\uff0c\u6838\u5bf9\u76ee\u6807\u7248\u672c\u540e\u53ea\u70b9\u4e00\u6b21\u201c\u5f00\u59cb\u5bfc\u5165\u201d\u3002\u6210\u529f\u540e\u4e0d\u8981\u624b\u52a8\u5173\u673a\u6216\u590d\u4f4d\uff0c\u6211\u4f1a\u5728\u6838\u5bf9 STAGED \u548c SD \u7a7a\u95f2\u540e\u6267\u884c\u6b63\u5e38\u590d\u4f4d\u3002\u4fdd\u6301\u624b\u673a App \u524d\u53f0\u8bb0\u5f55\uff0c\u65e0\u9700\u56de\u590d\u3002')
    h.save(armed / 'start-ready.json', dict(package=plan['mcu']['package'], before=before,
        captureId=phone.capture_id, pid=phone.pid, hostMonoNs=time.monotonic_ns()))
    phone.ask('start-' + channel, text)


def final_storage(final, firmware):
    journal = final['storage']['journal']
    h.require(journal.get('matches_reference') is True and
              journal['durable'] == firmware['package']['bytes'] and
              journal['committed_target'] == firmware['target']['version'],
              'actual staged package is not the selected complete package')


def cell(plan, out, channel_name):
    mcu = m.MCU(plan['mcu'], out / 'mcu')
    points = sc.bind(mcu)
    phone = obs.Observer(plan['phone'], out / 'phone', plan['notify_cli'])
    try:
        phone.start_recording()
        initial = phone.fresh_identity(plan['firmware']['current'], request=True)
        if channel_name == 'ble':
            phone.ready_package(plan['firmware'])
        collector = sc.Collector(mcu, points, time.monotonic()+2100)
        result = collector.run(channel_name, lambda before, armed: invite(phone, plan, channel_name, before, armed))
        final_storage(result['final'], plan['firmware'])
        phone.pump_stream()
        target = plan['firmware']['target']
        already = obs.identity(phone.live, target['version'], target['sha256'], plan['phone']['device']['address'], initial['seq'])
        final = phone.fresh_identity(target, initial['seq'], request=already is None)
        observation = phone.finish(diagnostics=False)
        h.save(out / 'result.json', dict(outcome='CELL_OBSERVED', channel=channel_name, kind=plan['kind'],
            initialInfo=initial, finalInfo=final, native=h.record(mcu.out / 'state-chain.json'),
            phone=h.record(phone.out / 'app-capture.jsonl'), package=plan['mcu']['package'],
            inputs=plan['firmware'], stateChain=result['stateChain'], timingCredit=False,
            phoneRecords=(observation.get('archive') or observation)['records']))
    finally:
        try:
            phone.preserve_failure()
        finally:
            phone.close()
        h.require(phone.capture_id is None or phone.capture_resolved, 'recording unresolved; retrieve it, never replay OTA')


def restore(plan, out, previous):
    h.require(previous and (previous / 'result.json').is_file(), 'preceding upgrade result required')
    result = h.read_json(previous / 'result.json')
    h.require(result['outcome'] == 'CELL_OBSERVED' and result['inputs'] == plan['firmware'] and
              result['finalInfo']['currentImageSha256'] == plan['firmware']['target']['sha256'],
              'restoration not bound to the preceding successful cell')
    for key in ('native', 'phone'):
        h.pinned(result[key])
    mcu = m.MCU(plan['mcu'], out / 'mcu')
    mcu.restore()
    h.save(out / 'result.json', dict(outcome='RESTORED_BASE', preceding=h.record(previous / 'result.json'),
        restoration=h.record(mcu.out / 'restore-result.json'), base=plan['firmware']['current']))


def ble_block(plan, out, max_cells, *, known_captures=None):
    is_benchmark = 'benchmark' in plan
    cap = benchmark.BUDGET['maxCells'] if is_benchmark else 8
    h.require(plan['kind'] == 'patch' and plan['mcu']['package']['bytes'] == 1048576 and 1 <= max_cells <= cap,
              'bound reference group/recording capacity required')
    phone = benchmark.Observer(plan, out / 'phone', known_captures) if is_benchmark else \
        obs.Observer(plan['phone'], out / 'phone', plan['notify_cli'])
    completed = []
    try:
        phone.start_recording()
        previous_seq = 0
        for index in range(max_cells):
            reserve_ok = phone.next_transfer() if is_benchmark else time.monotonic()+1800 < phone.recording_deadline
            if not reserve_ok:
                h.require(completed, 'recording budget exhausted before first transfer')
                break
            folder = h.fresh(out / ('cell-%02d' % (index+1)))
            mcu = benchmark.MCU(plan['mcu'], folder / 'mcu', deadline=min(phone.recording_deadline,
                plan.get('_campaign_deadline', phone.recording_deadline))-180) if is_benchmark else \
                m.MCU(plan['mcu'], folder / 'mcu')
            initial = phone.fresh_identity(plan['firmware']['current'], previous_seq, request=True)
            before = mcu.inspect('base', 'pre-transfer')
            h.require(before['storage']['journal']['expected_begin_durable'] == 0, 'nonzero reference start')
            ready = phone.ready_package(plan['firmware'])
            if is_benchmark:
                h.require(phone.next_transfer(), 'recording reserve consumed during package preparation; no BEGIN')
            h.save(folder / 'intent.json', dict(index=index+1, initial=initial, ready=ready,
                package=plan['mcu']['package'], hostMonoNs=time.monotonic_ns()))
            invite(phone, plan, 'ble', before, folder)
            phone.phase('transfer-and-reconnect', 600)
            boundaries = {}
            def terminal():
                phone.pump_stream()
                rows = [row for row in phone.live if row['seq'] > ready['seq']]
                v2.states(rows)
                if 'beginObservedMonoNs' not in boundaries and any(row['event'] == 'beginAck' for row in rows):
                    boundaries['beginObservedMonoNs'] = time.monotonic_ns()
                    h.save(folder / 'begin-observed.json', boundaries)
                h.require(not any(row['phase'] in ('failed', 'cancelled') for row in rows), 'actual BLE attempt failed')
                return next((row for row in reversed(rows) if row['phase'] == 'completed'), None)
            finished = phone.wait(terminal)
            h.require(boundaries, 'no observed BEGIN ACK boundary')
            r.bound(finished, dict(firmware=plan['firmware']), package=True, final=True)
            h.require(finished['freshConnection'] and finished['linkConnected'], 'no fresh completed identity')
            mcu.wait_boot('target')
            final = mcu.inspect('target', 'final-full-readback')
            final_storage(final, plan['firmware'])
            item = dict(index=index+1, firstSeq=ready['seq'], lastSeq=finished['seq'],
                initial=initial, finalInfo=finished, native=final, package=plan['mcu']['package'],
                hostFinishedMonoNs=time.monotonic_ns(), debuggerHaltsDuringTransfer=0, **boundaries)
            h.save(folder / 'result.json', item)
            completed.append(item)
            if is_benchmark:
                phone.clear_at_target(finished)
            phone.phase('verified-base-restoration', 600)
            mcu.restore()
            previous_seq = finished['seq']
            if is_benchmark:
                restored = phone.fresh_identity(plan['firmware']['current'], previous_seq, request=True)
                benchmark.idle_base(restored, plan['firmware'])
                phone.idle_services()
                h.save(folder / 'restored-idle.json', dict(state=restored,
                    restoration=h.record(mcu.out / 'restore-result.json')))
                previous_seq = restored['seq']
        report = phone.finish(diagnostics=True)
        upgrades = [group for group in report['groups'] if group['label'] == 'upgrade']
        v2.diagnostics(report['groups'], expected=plan['benchmark']['link'] if is_benchmark else None)
        h.require(len(upgrades) == len(completed), 'missing/extra upgrade diagnostic groups')
        result = dict(outcome='BLE_BLOCK_OBSERVED', cells=completed,
            original=h.record(phone.out / 'app-capture.jsonl'), diagnostics=h.record(phone.out / 'observation.json'),
            inputs=plan['firmware'], retained='base', formalVerdict='NOT_ADJUDICATED', allAttemptsPreserved=True)
        if is_benchmark:
            result.update(captureId=phone.capture_id, existingCaptures=len(phone.previous_captures),
                canonicalCaptures=dict(phone.known_captures))
        h.save(out / 'result.json', result)
        return result
    finally:
        try:
            phone.preserve_failure()
        finally:
            phone.close()
        h.require(phone.capture_id is None or phone.capture_resolved, 'block original unresolved; no replay')


def long_campaign(plan, out):
    from live import soak_clock
    clock_out = h.fresh(out / 'clock')
    stop, clock_errors = threading.Event(), []
    def observe():
        try:
            soak_clock(clock_out, out, 18000, stop_event=stop)
        except BaseException as error:
            clock_errors.append(error)
    thread = threading.Thread(target=observe, name='p5-soak-clock')
    thread.start()
    end = time.monotonic()+18000
    blocks, count, first_begin, span = [], 0, None, 0
    is_benchmark = 'benchmark' in plan
    block_limit, cells_per_block = (benchmark.BUDGET['maxRecordings'], benchmark.BUDGET['maxCells']) \
        if is_benchmark else (16, 8)
    known_captures = {}
    try:
        h.wait_for(lambda: (clock_out / 'monotonic.jsonl').is_file(), 5)
        for index in range(1, block_limit+1):
            if index > block_limit:
                break
            h.require(not clock_errors and time.monotonic()+3000 < end, 'insufficient complete next-block/cleanup budget')
            current = copy.deepcopy(plan)
            if is_benchmark:
                current['_long_execution'] = True
                current['_campaign_deadline'] = end
            current['phone']['limits']['total_seconds'] = min(5400, int(end-time.monotonic()-180))
            folder = h.fresh(out / ('block-%02d' % index))
            h.save(folder / 'intent.json', dict(index=index, hostMonoNs=time.monotonic_ns(),
                package=plan['mcu']['package'], maxCells=cells_per_block))
            result = ble_block(current, folder, cells_per_block, known_captures=known_captures) if is_benchmark else \
                ble_block(current, folder, cells_per_block)
            if is_benchmark:
                if index == 1:
                    block_limit = benchmark.recording_slots(result['existingCaptures'])
                h.require(result['captureId'] not in known_captures, 'recording reused within campaign')
                canonical = result['canonicalCaptures']
                h.require(all(canonical.get(cid) == pin for cid, pin in known_captures.items()) and
                    canonical.get(result['captureId']) == result['original'] and
                    len(canonical) == result['existingCaptures']+1, 'canonical archive lineage changed')
                for pin in canonical.values():
                    h.pinned(pin)
                known_captures = dict(canonical)
            blocks.append(h.record(folder / 'result.json'))
            count += len(result['cells'])
            first_begin = first_begin or result['cells'][0]['beginObservedMonoNs']
            last = folder / ('cell-%02d' % len(result['cells'])) / 'intent.json'
            span = (h.read_json(last)['hostMonoNs']-first_begin)/1e9
            h.save(out / ('progress-%02d.json' % index), dict(completed=count, conservativeSpanSeconds=span,
                blocks=blocks, first30='the first 30 declared attempts, never selected afterward'))
            if count >= 30 and span >= 14400:
                break
        h.require(count >= 30 and span >= 14400, 'finite campaign ended without all required observations')
    finally:
        stop.set()
        thread.join(timeout=10)
        h.require(not thread.is_alive() and not clock_errors, 'soak observer closure failed')
    h.save(out / 'result.json', dict(outcome='LONG_CAMPAIGN_OBSERVED', blocks=blocks, attempts=count,
        conservativeSpanSeconds=span, clock=h.record(clock_out / 'clock-result.json'),
        retained='base', formalVerdict='NOT_ADJUDICATED'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('cell', 'restore', 'ble-block', 'long', 'clock'))
    parser.add_argument('--inputs', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--channel', choices=('sd', 'ble'), default='sd')
    parser.add_argument('--max-cells', type=int, default=8)
    parser.add_argument('--previous', type=Path)
    parser.add_argument('--observe-root', type=Path)
    parser.add_argument('--seconds', type=int, default=18000)
    parser.add_argument('--contract', type=Path, required=True)
    parser.add_argument('--matrix', type=Path, required=True)
    parser.add_argument('--command-id', required=True)
    args = parser.parse_args()
    h.require(Path.cwd() == h.ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
              'explicit worktree and isolated Python required')
    args.inputs = (h.ROOT / args.inputs).resolve()
    if args.previous is not None:
        args.previous = (h.ROOT / args.previous).resolve()
    validator = validate if args.action == 'clock' else validate_live
    plan = validator(h.read_json(args.inputs))
    for name in ('host', 'phone', 'mcu', 'cloud', 'result.json', 'failed.json'):
        h.checked(args.out / name)
    out = h.fresh(args.out)
    h.save(out / 'intent.json', dict(argv=sys.argv, inputs=h.record(args.inputs), hostMonoNs=time.monotonic_ns()))
    try:
        gate(args, out)
        if args.action == 'cell':
            validate_functional_patch(plan)
        if args.action == 'clock':
            from live import soak_clock
            h.require(args.observe_root is not None and 14400 <= args.seconds <= 18000, 'bounded real soak clock required')
            soak_clock(out, h.checked(args.observe_root), args.seconds)
            return
        with h.device_owner(out):
            with channel(plan, out, args.action in ('ble-block', 'long') or args.action == 'cell' and args.channel == 'ble'):
                if args.action == 'cell':
                    cell(plan, out, args.channel)
                elif args.action == 'restore':
                    restore(plan, out, args.previous)
                elif args.action == 'ble-block':
                    ble_block(plan, out, args.max_cells)
                else:
                    long_campaign(plan, out)
        print(h.read_json(out / 'result.json')['outcome'], flush=True)
    except BaseException as error:
        h.save(out / 'failed.json', dict(type=type(error).__name__, message=str(error),
            noAutomaticReplay=True, preserveOriginals=True, hostMonoNs=time.monotonic_ns()))
        raise


if __name__ == '__main__':
    main()
