"""Original review oracles adapted to hash-bound archive reads; no physical actions."""
import copy
from collections import Counter
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import traceback
import zipfile

ROOT = Path(__file__).resolve().parents[3]
STORE = None
assert Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode
sys.path.insert(0, str(ROOT / '.agents/skills/e-track-flutter-debug/scripts'))
import host_io
sys.path.insert(0, str(ROOT / 'Tools/ota/p35-automation'))
import runner as r
import scenarios
r.load_host()
import live_mcu

TEN = ROOT / '.cache/p35-30309-20261102'
SUP = ROOT / '.cache/p35-supplement-20261102'
FIX = ROOT / '.cache/p35-r03-remediation-20261102'
inputs = {}
checks = []
details = {}


def path(p):
    return host_io.checked_output(ROOT, p)


def raw(p):
    key = STORE.key(p)
    b = STORE.read(key)
    inputs[key] = dict(bytes=len(b), sha256=hashlib.sha256(b).hexdigest())
    return b


def js(p):
    return json.loads(raw(p))


def pin(p):
    b = raw(p['path'])
    assert len(b) == p['bytes'] and hashlib.sha256(b).hexdigest() == p['sha256'], p['path']
    return b


def check(name, fn):
    try:
        value = fn()
        checks.append(dict(id=name, result='PASS', detail=value))
        print(name, 'PASS', flush=True)
    except Exception as e:
        checks.append(dict(id=name, result='FAIL', errorType=type(e).__name__,
                           detail=str(e), traceback=traceback.format_exc()))
        print(name, 'FAIL', type(e).__name__, str(e)[:300], flush=True)


def git(*args):
    p = subprocess.run(['git', '--no-optional-locks', *args], cwd=ROOT,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30, check=True)
    return p.stdout


def manifest(p):
    records = js(p)
    for record in records:
        pin(record)
    return dict(files=len(records), bytes=sum(p['bytes'] for p in records))


def capture(folder, sealed=True):
    b = raw(folder / ('app-capture.jsonl' if sealed else 'process-death-original.jsonl'))
    assert b == raw(folder / 'live-stream.stdout')
    decoder = r.Decoder()
    states = decoder.feed(b)
    assert not decoder.pending and states[0]['seq'] == 1
    if sealed:
        audit = r.audit_capture(b, decoder.opened['captureId'])
        assert decoder.closed and audit['records'] == len(states)
    else:
        assert decoder.opened and decoder.closed is None
        audit = dict(records=len(states), sealed=False, sha256=hashlib.sha256(b).hexdigest())
    return states, audit


def journal(folder):
    return [js(p) for p in STORE.glob(folder / 'journal', '*.json')]


def commands(folder):
    result = []
    for p in STORE.glob(folder / 'usb', 'adb-*.started.json'):
        a = js(p)
        closed = p.with_name(p.name.replace('.started.', '.closed.'))
        if not STORE.exists(closed):
            continue
        c = js(closed)
        b = pin(c['stdout'])
        pin(c['stderr'])
        assert c['argv'] == a['argv'] and c['cleanup_complete']
        result.append(dict(start=a['monotonic_ns'], end=c['ended_monotonic_ns'],
                           cmd=' '.join(a['argv'][9:]), allcmd=' '.join(a['argv']),
                           argv=a['argv'], data=b, code=c['exit_code'], file=str(p.relative_to(ROOT))))
    return sorted(result, key=lambda c: c['start'])


def source_identity():
    contract = js('docs/acceptance-contracts/P3-5-v3.contract.json')
    assert git('rev-parse', contract['freeze_commit']).decode().strip() == contract['freeze_commit']
    assert git('rev-parse', contract['freeze_commit'] + '^{tree}').decode().strip() == contract['freeze_tree']
    assert git('rev-parse', contract['freeze_commit'] + ':Tools/provenance/manifest_profiles.json').decode().strip() == contract['profile_config_blob']
    product = ['app/bluetooth_flutter_Trace/lib', 'app/bluetooth_flutter_Trace/test']
    assert not git('diff', 'd717e6a0', '--', *product)
    for p in (TEN / 'frozen-bindings.json', TEN / 'pipeline-01/source-pins.json',
              SUP / 'background-lock/bindings.json', SUP / 'process-death/bindings.json',
              SUP / 'process-continuation/supervisor-01/launch.json'):
        value = js(p)
        for record in value if isinstance(value, list) else value['pins']:
            pin(record)
    for entry in contract['external_inputs']:
        assert hashlib.sha256(raw(TEN / entry['evidence_path'])).hexdigest() == entry['evidence_sha256']
    return dict(head=contract['freeze_commit'], tree=contract['freeze_tree'], product='d717e6a0', pins='unchanged')


def ci():
    result = []
    close = js(FIX / 'remediation-closeout.json')
    for row in close['ci']:
        host_results = []
        for host in row['hosts']:
            report = json.loads(pin(host['report']))
            assert report['source_before']['head'] == row['commit'] and report['scope'] == 'all'
            base = ROOT / host['report']['path']
            cmd = next(c for c in report['commands'] if c['name'] == 'tests')
            log = raw(base.parent / cmd['log']).decode('utf-8')
            terminal = re.findall(r'\d+:\d+\s+\+(\d+)(?:\s+~(\d+))?(?:\s+-(\d+))?: (All tests passed!|Some tests failed\.)', log)
            assert terminal
            passed, skipped, failed, message = terminal[-1]
            counts = dict(passed=int(passed), skipped=int(skipped or 0), failed=int(failed or 0))
            assert counts == cmd['diagnostics']['test_counts']
            analyze = next(c for c in report['commands'] if c['name'] == 'analyze')
            assert analyze['exit_code'] == 0 and 'No issues found!' in raw(base.parent / analyze['log']).decode()
            if row['runId'] == 41399653523:
                assert counts['failed'] == 8 and 'cmd=0x80' in log and 'P35-R03' in log
            if row['runId'] == 41403989651:
                assert counts['failed'] == 0 and report['development_result'] == 'PASS'
                assert all(c['status'] == 'PASS' and c['exit_code'] == 0 for c in report['commands'])
                names = set(re.findall(r'(P35-R03[^\r\n]*)', log))
                # Expanded parallel reporter need not print every short test title.
                # Bind full-suite counts and every changed retirement/probe title.
                for version in (1, 2):
                    for exit_kind in ('disconnect', 'notification-error', 'cancel', 'dispose'):
                        assert any(('v%d %s after completed DATA write' % (version, exit_kind)) in n for n in names)
                    for failure in ('write', 'identity'):
                        assert any(('v%d failed cancellation %s probe' % (version, failure)) in n for n in names)
            host_results.append(dict(host=report['host'], counts=counts, terminal=message))
        result.append(dict(run=row['runId'], source=row['commit'], hosts=host_results))
    return result


def release_assets():
    base = FIX / 'release-artifacts'
    v = js(base / 'assets-resumed-01/verification.json')
    meta = js(base / 'metadata-01/run.stdout')
    assert meta['head_sha'] == v['source'] and meta['conclusion'] == 'success' and meta['id'] == v['run']
    jobs = js(base / 'metadata-01/jobs.stdout')['jobs']
    assert all(j['conclusion'] in ('success', 'skipped') for j in jobs)
    inventory = js(base / 'metadata-01/artifacts.stdout')['artifacts']
    assets = [pin(p) for p in v['assets']]
    for platform, artifact_id in [('android', v['assets'][0]['artifactId']), ('windows', v['assets'][1]['artifactId'])]:
        archive = raw(base / ('assets-resumed-01/' + platform + '-artifact.zip'))
        remote = next(x for x in inventory if x['id'] == artifact_id)
        assert remote['digest'] == 'sha256:' + hashlib.sha256(archive).hexdigest()
        with zipfile.ZipFile(io.BytesIO(archive)) as z:
            assert z.testzip() is None
            for p in v['assets']:
                if p['artifactId'] == artifact_id:
                    name, = [n for n in z.namelist() if n.endswith(Path(p['path']).name)]
                    assert z.read(name) == pin(p)
    with zipfile.ZipFile(io.BytesIO(assets[2])) as z:
        name, = [n for n in z.namelist() if n == 'ble_monitor.exe']
        assert z.read(name) == assets[1]
    assert v['assets'][0]['sha256'] == js(TEN / 'pipeline-01/plan.json')['app']['sha256']
    assert 'versionCode=\'97\'' in raw(base / 'assets-resumed-01/badging.stdout').decode()
    return dict(run=v['run'], source=v['source'], apk=v['assets'][0], exe=v['assets'][1], jobs=[(j['name'], j['conclusion']) for j in jobs])


def ten_recoveries():
    folder = TEN / 'pipeline-01/device'
    plan = js(TEN / 'pipeline-01/plan.json')
    pin(plan['firmware']['package'])
    states, audit = capture(folder)
    by = {s['seq']: s for s in states}
    j = journal(folder)
    result = js(folder / 'result.json')
    initial, = [x['state'] for x in j if x['event'] == 'observed' and x.get('stage') == 'initial-BEGIN']
    assert initial == by[initial['seq']] and initial['durable'] == 0
    for event in ('radio-intent', 'radio-state-observed'):
        assert [x['enabled'] for x in j if x['event'] == event] == [False, True] * 10
    n = plan['firmware']['package']['bytes']
    starts = [(n * i // 10 // 4096) * 4096 for i in range(10)]
    cases = []
    for i, (case, window) in enumerate(zip(result['cases'], plan['cases'], strict=True)):
        assert window['durable_min'] == starts[i] and window['durable_max'] == (starts[i+1] - 1 if i < 9 else n-1)
        before, cut, resume, first = [case[k] for k in ('before', 'disconnected', 'resume', 'firstData')]
        for s in (before, cut, resume, first):
            assert s == by[s['seq']]
            r.bound(s, plan, package=True)
        assert before['seq'] < cut['seq'] < resume['seq'] < first['seq']
        assert r.case_matches(before, window) and r.case_matches(cut, window) and not cut['linkConnected']
        assert resume['event'] == 'beginAck' and resume['linkConnected'] and resume['freshConnection']
        assert cut['durable'] <= resume['durable'] <= window['durable_max']
        assert first['event'] == 'data' and first['sendOffset'] == r.resume_offset(resume) and first['session'] == resume['session']
        progress, = [x['state'] for x in j if x['event'] == 'observed' and x.get('stage') == case['id'] + '-durable-progress']
        assert progress == by[progress['seq']] and progress['durable'] > resume['durable']
        cases.append(dict(id=case['id'], intentDurable=before['durable'], cutDurable=cut['durable'],
                          resumeDurable=resume['durable'], firstData=first['sendOffset'], sequences=[s['seq'] for s in (before,cut,resume,first)]))
    assert len(cases) == 10 and sum(s['event'] == 'beginAck' for s in states) == 11
    final = result['final']
    assert final == by[final['seq']] and final['freshConnection'] and final['phase'] == 'completed'
    r.bound(final, plan, package=True, final=True)
    assert final['durable'] == n
    no_update = by[result['noUpdate']['seq']]
    assert no_update['seq'] > final['seq'] and no_update['phase'] == 'idle' and no_update['targetVersionCode'] == 0
    assert no_update['currentVersionCode'] == final['currentVersionCode']
    cmd = commands(folder)
    radio = [c for c in cmd if 'cmd bluetooth_manager disable' in c['allcmd'] or 'cmd bluetooth_manager enable' in c['allcmd']]
    assert len(radio) == 20 and all(c['code'] == 0 for c in radio)
    assert [('disable' in c['allcmd']) for c in radio] == [True, False] * 10
    details['ten'] = dict(audit=audit, cases=cases, zeroOrigin=True,
        preFirstDurableCutObserved=any(x['cutDurable'] == 0 for x in cases), final=final, noUpdate=no_update)
    return details['ten']


def supplements():
    pre = SUP / 'process-death/pipeline-01/device/before-death'
    folder = SUP / 'process-continuation/device'
    plan = js(SUP / 'process-death/pipeline-01/plan.json')
    prefix, pa = capture(pre, sealed=False)
    killed = js(pre / 'kill-observed.json')
    assert pa['sha256'] == killed['rawSha256'] and max(s['durable'] for s in prefix) == killed['durableFloor']
    states, audit = capture(folder)
    by = {s['seq']: s for s in states}
    j = journal(folder)
    res = js(SUP / 'process-continuation/device-summary.json')
    assert len(set(res['processIds'])) == 2 and res['processIds'][0] == killed['pid']
    observed, = [x for x in j if x['event'] == 'process-resume-observed']
    a,b = observed['begin'], observed['firstData']
    assert a == by[a['seq']] and b == by[b['seq']]
    assert a['durable'] >= killed['durableFloor'] > 0 and b['sendOffset'] == a['durable'] and a['seq'] < b['seq']
    r.bound(a, plan, package=True)
    assert a['freshConnection'] and a['linkConnected']
    cover = res['scenarioCoverage']
    for stage in ('home', 'locked'):
        a,b = cover[stage]['start'],cover[stage]['end']
        assert a == by[a['seq']] and b == by[b['seq']] and b['durable'] > a['durable']
        for s in states[a['seq']-1:b['seq']]:
            runtime=s['runtime']
            assert runtime['backgrounded'] and runtime['active'] and runtime['acquired'] and not runtime['paused']
            assert runtime['task'] == a['runtime']['task'] and s['session'] == a['session']
    final = res['final']
    assert final == by[final['seq']] and final['freshConnection'] and final['durable'] == plan['firmware']['package']['bytes']
    r.bound(final, plan, package=True, final=True)
    assert sum(s['event'] == 'beginAck' for s in states) == 1
    cmd = commands(folder)
    samples = [x for x in j if x['event'] == 'locked-window-sample']
    assert len(samples) == 47
    for sample in samples:
        assert sample['state'] == by[sample['state']['seq']]
        preceding = [c for c in cmd if c['end'] <= sample['hostMonoNs']]
        power = [c for c in preceding if c['allcmd'].endswith('dumpsys power')][-1]
        policy = [c for c in preceding if c['allcmd'].endswith('dumpsys window policy')][-1]
        screen = scenarios.display(power['data'],policy['data'])
        assert screen == sample['screen'] and not screen['awake'] and not screen['interactive'] and screen['showing']
        pid = [c for c in preceding if c['allcmd'].endswith('pidof ' + plan['app']['id'])][-1]
        assert pid['data'].decode().strip() == res['processIds'][1]
        assert sample['hostMonoNs'] - min(power['start'],policy['start'],pid['start']) < 5_000_000_000
        if sample.get('terminalServiceAbsent'):
            svc=[c for c in preceding if c['allcmd'].endswith('dumpsys activity services ' + plan['app']['id'])][-1]
            assert b'DeviceOtaService' not in svc['data'] and svc['code'] == 0
    locked, = [x for x in j if x['event'] == 'screen-locked']
    complete, = [x for x in j if x['event'] == 'locked-window-completed']
    wake, = [x for x in j if x['event'] == 'screen-wake-intent']
    assert (complete['hostMonoNs'] - locked['hostMonoNs'])/1e9 >= 600 and wake['hostMonoNs'] > complete['hostMonoNs']
    returned, = [x for x in j if x['event'] == 'display-restored']
    assert returned['samePid'] == res['processIds'][1] and not returned['lifecycle']['runtime']['backgrounded']
    assert by[res['noUpdate']['seq']]['targetVersionCode'] == 0 and audit['final']['phase'] == 'idle'
    assert not audit['final']['runtime']['active'] and not audit['final']['runtime']['acquired']
    before_cmd=commands(pre)
    kills=[c for c in before_cmd if 'am force-stop ' + plan['app']['id'] in c['allcmd']]
    assert len(kills) == 1 and kills[0]['code'] == 0
    details['supplement'] = dict(prefix=pa, audit=audit, pidPair=res['processIds'], resumedDurable=observed['begin']['durable'],
        firstData=observed['firstData']['sendOffset'], lockedSeconds=complete['seconds'], lockSamples=len(samples),
        resumeBeginToFinalSeconds=(final['monoUs']-observed['begin']['monoUs'])/1e6,
        continuousTenMinuteTransfer=False, multiCycleEndurance=False)
    return details['supplement']


def mcu():
    result=[]
    baseline=git('show','edfce184ebe9926d0fb777478b5b9a03fc09f48d:docs/acceptance-contracts/P3-8-v5/inputs/mcu/boot.bin')
    for folder, target in ((TEN / 'final-mcu-01',30309), (SUP / 'background-lock/final-mcu-01',30310),
                            (SUP / 'process-death/final-mcu-01',30311)):
        plan=js(folder / 'plan.json')
        reads,=[p for p in STORE.children(folder) if re.match(r'\d{4}-',p.name)]
        samples={p.stem:raw(p) for p in STORE.glob(reads, '*.bin')}
        assert samples['boot'] == baseline
        assert samples['app'] == pin(plan['images']['target']['image'])
        assert samples['header_after'] == samples['app'][0x400:0x460]
        health=live_mcu.health_gate(samples)
        storage=live_mcu.storage_observation(samples,plan['package'])
        assert storage['journal']['committed_target'] == target
        assert storage['journal']['durable'] == plan['package']['bytes']
        lines=raw(reads / 'commands.jlink').decode().splitlines()
        assert lines[:len(live_mcu.START)] == live_mcu.START
        assert all(s in ('qc','sleep 1000') or s.startswith('savebin ') for s in lines[len(live_mcu.START):])
        closed=js(reads / 'commander.closed.json')
        assert closed['exit_code'] == 0 and closed['cleanup_complete']
        pin(closed['stdout'])
        result.append(dict(version=target, appSha256=hashlib.sha256(samples['app']).hexdigest(),
                           bootSha256=hashlib.sha256(baseline).hexdigest(), health=health, journal=storage['journal']))
    return result


def cleanup_and_failures():
    results=[]
    for folder in (TEN / 'pipeline-01', SUP / 'background-lock/pipeline-01',
                   SUP / 'process-death/pipeline-01', SUP / 'process-continuation'):
        old,new=js(folder / 'channels-before.json'),js(folder / 'channels-restored.json')
        assert old['beta']==new['beta'] and new['stable']['revision']==old['stable']['revision']+2
        assert {k:v for k,v in old['stable'].items() if k!='revision'}=={k:v for k,v in new['stable'].items() if k!='revision'}
        results.append(dict(folder=str(folder.relative_to(ROOT)),revision=[old['stable']['revision'],new['stable']['revision']]))
    bg=js(SUP / 'background-lock/pipeline-01/device/result.json')
    assert bg['outcome']=='EVIDENCE_GAP' and bg['detail']=='locked observation window interrupted'
    states,audit=capture(SUP / 'background-lock/pipeline-01/device')
    screen=scenarios.display(raw(SUP / 'background-lock/pipeline-01/device/usb/adb-00143.stdout'),
                             raw(SUP / 'background-lock/pipeline-01/device/usb/adb-00144.stdout'))
    assert screen['awake'] and not screen['showing']
    assert hashlib.sha256(raw('.cache/p35-clean-30308-20261102/pipeline-01/device/app-capture.jsonl')).hexdigest() == '6c7ef2f091e0053d89505ee93ffc5e325ee321dc7cc2bbe3454d31954b5a8e90'
    for folder in (TEN / 'pipeline-01/device',SUP / 'process-continuation/device'):
        v=js(folder / 'result.json')
        assert v['cleanup']['complete'] and v['cleanup']['ownedAppClosed'] and not v['lockRetained']
        d=js(folder / 'logcat-diagnostic-integrity.json')
        assert d['usedForInjection'] is False and d['nativeMirror']['status']=='FAILED_DISABLED'
    return dict(restorations=results, earlyUnlock='preserved failure', auxiliaryLogcat='incomplete, not primary',
                backgroundFailedCaptureRecords=audit['records'])


def negative_controls():
    folder=TEN / 'pipeline-01/device'
    b=raw(folder / 'app-capture.jsonl')
    decoder=r.Decoder();states=decoder.feed(b)
    variants=[b.rsplit(b'OTA_P35_CAPTURE ',1)[0],b.replace(b'"seq":2,',b'"seq":3,',1),b.replace(b'"lost":0',b'"lost":1',1)]
    assert all(v!=b for v in variants)
    for variant in variants:
        try:r.audit_capture(variant,states[0]['captureId'])
        except r.Stop:pass
        else:raise AssertionError('corrupted capture accepted')
    plan=js(TEN / 'pipeline-01/plan.json')
    candidate=copy.deepcopy(next(s for s in states if s['event']=='beginAck'))
    candidate['packageSha256']='0'*64
    try:r.bound(candidate,plan,package=True)
    except r.Stop:pass
    else:raise AssertionError('wrong package accepted')
    return dict(missingFooter='rejected',replayedSequence='rejected',loss='rejected',wrongPackage='rejected')


def build_originals():
    import pipeline_build
    import pipeline
    values=[]
    pairs=[(TEN / 'pipeline-01',TEN / 'inputs/configuration.json'),
           (SUP / 'background-lock/pipeline-01',SUP / 'background-lock/configuration.json'),
           (SUP / 'process-death/pipeline-01',SUP / 'process-death/configuration.json')]
    for folder,config_path in pairs:
        configuration=js(config_path)
        config=dict(configuration['build'],version_code=pipeline.validate(configuration))
        build=folder / 'build'
        bound=js(build/'run-bound.json')
        completed=js(build/'run-completed.json')
        assert completed['id']==bound['id'] and completed['head_sha']==bound['sha']==config['sha']
        assert completed['status']=='completed' and completed['conclusion']=='success'
        receipts=[]
        for p in STORE.glob(build, 'gh-*.started.json'):
            start=js(p);close=js(p.with_name(p.name.replace('started','closed')))
            assert start['argv']==close['argv'] and close['cleanup_complete']
            receipts.append(dict(start=start,close=close,data=pin(close['stdout'])))
        download,=[x for x in receipts if any(re.search(r'/actions/artifacts/\d+/zip$',a) for a in x['start']['argv'])]
        artifact=js(build/'artifact.json')
        assert artifact['digest']=='sha256:'+hashlib.sha256(download['data']).hexdigest()
        with zipfile.ZipFile(io.BytesIO(download['data'])) as z:
            assert z.testzip() is None
            files={i.filename:z.read(i) for i in z.infolist() if not i.is_dir()}
        for name,data in files.items():
            assert raw(build/'originals'/name)==data
        marker=js(build/'dispatch-intent.json')['marker']
        verified=pipeline_build.verify_release(files,config,bound['id'],marker)
        target=js(folder/'target.json')
        for k,v in verified.items():assert target[k]==v,k
        previous=js(build/'variables-before.json')
        for name,value in previous.items():
            reads=[x for x in receipts if any(a.endswith('/variables/'+name) for a in x['start']['argv'])
                   and x['start']['argv'][-1]=='GET']
            assert reads and json.loads(reads[-1]['data'])['value']==value
            assert reads[-1]['close']['exit_code']==0
        values.append(dict(run=bound['id'],version=target['versionCode'],warnings=verified['warnings'],
                           errors=verified['errors'],artifactSha256=artifact['digest'],variablesRestored=True))
    return values


def supplemental_failure_lineage():
    failed=js(SUP/'process-death/pipeline-01/device/after-restart/result.json')
    assert failed['cleanup']['armAttempts']==0 and not failed['cleanup']['ownedAppLaunchConfirmed']
    assert failed['outcome']=='UNRESOLVED_STATE' and failed['lockRetained']
    state=js(SUP/'process-recovery-01/state.json')
    assert state['appAbsent'] and state['serviceAbsent'] and state['archiveUnchanged']
    assert not state['newOta'] and not state['newKill']
    complete=js(SUP/'process-continuation/device-summary.json')
    assert complete['cleanup']['complete'] and not complete['lockRetained']
    v=js(TEN/'pipeline-01/result.json')
    assert v['continuedInterruptedInvocation'] and not STORE.exists(TEN/'operations/execute/pipeline.closed.json')
    for folder in (TEN/'supervisor-resume-01',SUP/'background-lock/supervisor-01',
                   SUP/'process-death/supervisor-01',SUP/'process-continuation/supervisor-01'):
        result=js(folder/'result.json')
        assert result['outcome']=='COMMAND_COMPLETED'
    assert all(not STORE.exists(ROOT/'.cache'/n) for n in ('p34-live-device.lock','p35-reconcile-device.lock','p35-pipeline.lock'))
    contract=js('docs/acceptance-contracts/P3-5-v3.contract.json')
    missing=[{'id':a['id'],'path':a['path']} for a in contract['artifacts'] if not STORE.exists(TEN/a['path'])]
    return dict(usbFailurePreserved=True,unstartedRecoveryOnly=True,tenInterruptedReceipt='still missing, not invented',
                currentLocalLocksAbsent=True,formalMatrix=js(TEN/'execution-matrix.json')['overall_result'],
                formalArtifactPathsNotMaterialized=missing)
