"""Independent offline review of P35-IR-01; never invokes device controllers."""
import copy
from datetime import datetime, timezone
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
PRIOR = ROOT / '.cache/p35-independent-review-20261102-01'
AREA = ROOT / '.cache/p35-pre-durable-20261102'
OLD = AREA / 'target-30312'
NEW = AREA / 'target-30313'
RUN = NEW / 'suffix-01'
assert Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode
import original as v
import pipeline
import pipeline_build

raw, js, pin, r = v.raw, v.js, v.pin, v.r


def position_gate(states, plan, intent, cut, resume, first):
    """Position evidence, not a replacement for radio/integrity/final gates."""
    by_seq = {s['seq']: s for s in states}
    for state in (intent, cut, resume, first):
        r.validate_state(state)
        r.bound(state, plan, package=True)
        r.require(state == by_seq.get(state['seq']), 'position anchor absent from original')
        r.require(state['captureId'] == intent['captureId'], 'different capture anchor')
    r.require(intent['seq'] < cut['seq'] < resume['seq'] < first['seq'], 'position order')
    begins = [s for s in states if s['event'] == 'beginAck' and s['seq'] <= intent['seq']]
    r.require(len(begins) == 1 and begins[0]['durable'] == 0, 'missing initial zero BEGIN')
    before = [s for s in states if s['seq'] < cut['seq']][-1]
    r.require(before['linkConnected'] and not cut['linkConnected'], 'not an actual disconnect edge')
    r.require(intent['durable'] == cut['durable'] == 0,
              'zero intent does not prove an actual pre-durable disconnect')
    interval = [s for s in states if begins[0]['seq'] <= s['seq'] <= cut['seq']]
    r.require(all(s['durable'] == 0 for s in interval), 'positive persistence before disconnect')
    connected = [s for s in states if cut['seq'] < s['seq'] < resume['seq'] and
                 s['linkConnected'] and s['freshConnection']]
    r.require(connected, 'missing fresh reconnection')
    r.bound(connected[0], plan, package=True)
    r.require(resume['event'] == 'beginAck' and resume['durable'] == 0 and
              resume['bitmap'] in (None, 0), 'MCU persisted before recovery; position not proved')
    data = [s for s in states if resume['seq'] < s['seq'] and s['event'] == 'data']
    r.require(data and data[0] == first and first['session'] == resume['session'] and
              first['sendOffset'] == r.resume_offset(resume) == 0, 'not the first resumed DATA at zero')
    r.require(any(s['seq'] > first['seq'] and s['durable'] > 0 for s in states),
              'no durable progress after recovery')
    return 'PRE_DURABLE_POSITION_PROVED'


def prior_review():
    decision = js(PRIOR / 'decision.json')
    latest, unchanged, histories = {}, {}, []
    for index, item in enumerate(decision['results'], 1):
        b = raw(PRIOR / item['path'])
        assert hashlib.sha256(b).hexdigest() == item['sha256']
        result = json.loads(b)
        latest.update({c['id']: c for c in result['checks']})
        histories.append(dict(path=item['path'], passed=result['passed'], failed=result['failed']))
        for rel, expected in js(PRIOR / ('inputs-%02d.json' % index)).items():
            if rel == (PRIOR / 'review.py').relative_to(ROOT).as_posix():
                rel = (PRIOR / ('review-%02d.py' % index if index < 4 else 'review.py')).relative_to(ROOT).as_posix()
            assert rel not in unchanged or unchanged[rel] == expected, rel
            unchanged[rel] = expected
    for rel, expected in unchanged.items():
        pin(dict(path=rel, **expected))
    assert len(latest) == 14
    assert [k for k, c in latest.items() if c['result'] != 'PASS'] == ['required-positions']
    return dict(unchangedInputs=len(unchanged), previousPassedChecks=13,
                unresolvedPriorCheck='required-positions', histories=histories,
                method='Rehashed unchanged original inputs; did not replay prior physical tests.')


def source_binding():
    identity = v.source_identity()
    for target in (OLD, NEW):
        for record in js(target / 'bindings.json')['pins']:
            pin(record)
        cfg = js(target / 'configuration.json')
        assert cfg['build']['sha'] == '18f6b3d3af0c24b1ce81573700cd61005b7c530e'
    for folder in (OLD/'supervisor-01', OLD/'continuation-01/supervisor-01', NEW/'supervisor-01', RUN/'supervisor-01'):
        for record in js(folder/'launch.json')['pins']:
            pin(record)
    assert not v.git('diff', '--name-only', '--', 'app/bluetooth_flutter_Trace', 'Tools/ota/p35-automation')
    before = js(v.TEN/'pipeline-01/plan.json')
    after = js(RUN/'plan.json')
    assert before['app'] == after['app']
    assert before['phone'] == after['phone']
    return dict(**identity, firmwareSource='18f6b3d3', apkSha256=after['app']['sha256'],
                triggerChange='Earlier fault injection only; no product or link-parameter edit.')


def position():
    folder = RUN/'device'
    plan = js(RUN/'plan.json')
    pin(plan['firmware']['package'])
    states, integrity = v.capture(folder)
    assert integrity['records'] == 5306
    assert hashlib.sha256(raw(folder/'app-capture.jsonl')).hexdigest() == '058a5e5b09dd27b3334d3e64c92e22c375fd2bb571f4592770f4a13e66613cc8'
    result = js(folder/'device-summary.json')
    p = result['preDurable']
    trigger, initial, cut, resume, first = [p[k] for k in ('trigger','initialBeginAck','disconnected','resume','firstData')]
    position_gate(states, plan, initial, cut, resume, first)
    by = {s['seq']: s for s in states}
    for s in (trigger, initial, cut, resume, first):
        assert s == by[s['seq']]
        r.bound(s, plan, package=True)
    assert [s['seq'] for s in (trigger, initial, cut, resume, first)] == [289, 291, 318, 376, 379]
    assert trigger['phase'] == 'transferring' and trigger['event'] == 'identity'
    assert all(s['durable'] == 0 for s in states if s['seq'] <= cut['seq'])
    assert by[cut['seq']-1]['linkConnected'] and not cut['linkConnected']
    assert initial['session'] != resume['session'] == first['session']
    assert resume['freshConnection'] and resume['linkConnected']
    assert len([s for s in states if s['event'] == 'beginAck']) == 2
    final = result['final']
    assert final == by[final['seq']] and final['event'] == 'identity'
    r.bound(final, plan, package=True, final=True)
    assert final['freshConnection'] and final['linkConnected'] and final['phase'] == 'completed'
    assert final['durable'] == plan['firmware']['package']['bytes']
    no_update = by[result['noUpdate']['seq']]
    assert result['noUpdate']['outcome'] == 'NO_UPDATE' and no_update['seq'] > final['seq']
    assert no_update['targetVersionCode'] == 0 and no_update['phase'] == 'idle'
    assert no_update['currentVersionCode'] == 30313 and no_update['currentImageSha256'] == final['currentImageSha256']
    last = states[-1]
    assert last['phase'] == 'idle' and not last['runtime']['active'] and not last['runtime']['acquired']
    j = v.journal(folder)
    radio = [x for x in j if x['event'] == 'radio-state-observed']
    assert [x['enabled'] for x in radio] == [False, True]
    warm = js(folder/'warm/result.json')
    assert warm['sendCount'] == 1 and warm['outcome'] == 'FIRED' and warm['cleanupComplete']
    assert warm['signal']['state'] == trigger
    commands = v.commands(folder)
    enables = [c for c in commands if 'cmd bluetooth_manager enable' in c['allcmd']]
    assert len(enables) == 1 and enables[0]['code'] == 0
    assert not any('am start' in c['allcmd'] and c['start'] > radio[0]['hostMonoNs'] for c in commands)
    assert result['cleanup']['complete'] and result['cleanup']['ownedAppClosed'] and not result['lockRetained']
    negative = []
    for name, seq, key, value in [('positive_cut',318,'durable',4096), ('buffered_resume',376,'durable',8192),
                                  ('wrong_first_offset',379,'sendOffset',2048), ('wrong_first_session',379,'session',1)]:
        changed = copy.deepcopy(states)
        changed[seq-1][key] = value
        try:
            position_gate(changed,plan,*[changed[i-1] for i in (291,318,376,379)])
        except r.Stop:
            negative.append(name)
        else:
            raise AssertionError('Invalid position accepted: '+name)
    old_states, _ = v.capture(v.TEN/'pipeline-01/device')
    old_case = js(v.TEN/'pipeline-01/device/result.json')['cases'][0]
    try:
        position_gate(old_states,js(v.TEN/'pipeline-01/plan.json'),
                            *[old_case[k] for k in ('before','disconnected','resume','firstData')])
    except r.Stop:
        negative.append('original_R01_zero_intent_positive_cut')
    else:
        raise AssertionError('Original missing position relabeled PASS')
    return dict(records=len(states), capture=integrity, sequences=[289,291,318,376,379],
                initialDurable=0, actualCutDurable=0, resumeDurable=0, firstData=0,
                beginToCutSeconds=(cut['monoUs']-initial['monoUs'])/1e6,
                finalVersion=30313, noUpdateSeq=no_update['seq'], negativeControls=negative,
                observedRadioPairs=1, oldTenGroupUnchanged=True)


def builds():
    outputs = []
    for target, completed_run in ((OLD,41457337813), (NEW,41463640594)):
        build = target/'pipeline-01/build'
        cfg = js(target/'configuration.json')
        config = dict(cfg['build'], version_code=pipeline.validate(cfg))
        bound, completed = js(build/'run-bound.json'), js(build/'run-completed.json')
        assert bound['id'] == completed['id'] == completed_run
        assert completed['head_sha'] == config['sha'] and completed['conclusion'] == 'success'
        receipts = []
        for p in v.STORE.glob(build, 'gh-*.started.json'):
            start = js(p)
            end = js(p.with_name(p.name.replace('started','closed')))
            assert start['argv'] == end['argv'] and end['cleanup_complete']
            receipts.append((start,end,pin(end['stdout'])))
            pin(end['stderr'])
        if target == OLD:
            meta = js(build/'artifact.json')
            archive, = [data for start,end,data in receipts if any(a.endswith('/zip') for a in start['argv'])]
            originals = build/'originals'
        else:
            recovered = target/'download-recovery-01'
            meta = js(recovered/'artifact.json')
            archive = raw(recovered/'artifact.zip')
            prefix = pin(js(build/'gh-0051.closed.json')['stdout'])
            suffix = pin(js(recovered/'artifact-range.closed.json')['stdout'])
            assert archive == prefix + suffix
            assert js(build/'gh-0051.closed.json')['reason'] == 'timeout_outcome_unknown'
            original_meta = js(build/'gh-0050.stdout')['artifacts']
            assert meta in original_meta
            assert js(target/'pipeline-01/result.json')['device'] == 'NOT_RUN'
            originals = recovered/'originals'
        assert len(archive) == meta['size_in_bytes']
        assert 'sha256:'+hashlib.sha256(archive).hexdigest() == meta['digest']
        with zipfile.ZipFile(io.BytesIO(archive)) as z:
            assert z.testzip() is None
            files = {i.filename:z.read(i) for i in z.infolist() if not i.is_dir()}
        for name, data in files.items():
            assert data == raw(originals/name)
        verified = pipeline_build.verify_release(files, config, completed_run, js(build/'dispatch-intent.json')['marker'])
        for name, value in js(build/'variables-before.json').items():
            reads = [(end,data) for start,end,data in receipts if start['argv'][-1] == 'GET' and
                     any(a.endswith('/variables/'+name) for a in start['argv'])]
            assert reads and reads[-1][0]['exit_code'] == 0 and json.loads(reads[-1][1])['value'] == value
        assert verified['errors'] == 0 and verified['warnings'] == 641
        outputs.append(dict(run=completed_run,version=verified['versionCode'],warnings=verified['warnings'],
                            errors=verified['errors'],artifactSha256=meta['digest'],variablesReadback=True))
    return outputs


def mcu():
    baseline = v.git('show','edfce184ebe9926d0fb777478b5b9a03fc09f48d:docs/acceptance-contracts/P3-8-v5/inputs/mcu/boot.bin')
    values = []
    for target, version in ((OLD,30312),(NEW,30313)):
        folder = target/'final-mcu-01'
        plan = js(folder/'plan.json')
        reads, = [p for p in v.STORE.children(folder) if p.name[:4].isdigit()]
        samples = {p.stem:raw(p) for p in v.STORE.glob(reads, '*.bin')}
        assert samples['boot'] == baseline and samples['app'] == pin(plan['images']['target']['image'])
        assert samples['header_after'] == samples['app'][0x400:0x460]
        health = v.live_mcu.health_gate(samples)
        storage = v.live_mcu.storage_observation(samples,plan['package'])
        assert storage['journal']['committed_target'] == version
        assert storage['journal']['durable'] == plan['package']['bytes']
        command = raw(reads/'commands.jlink').decode().splitlines()
        assert command[:len(v.live_mcu.START)] == v.live_mcu.START
        assert all(s in ('qc','sleep 1000') or s.startswith('savebin ') for s in command[len(v.live_mcu.START):])
        closed = js(reads/'commander.closed.json')
        assert closed['exit_code'] == 0 and closed['cleanup_complete']
        pin(closed['stdout'])
        values.append(dict(version=version,imageSha256=hashlib.sha256(samples['app']).hexdigest(),
                           bootSha256=hashlib.sha256(baseline).hexdigest(),health=health,storage=storage))
    return values


def lineage():
    failed_states, _ = v.capture(OLD/'pipeline-01/device')
    resumed_states, _ = v.capture(OLD/'continuation-01/device')
    failed = js(OLD/'continuation-01/device-summary.json')
    assert failed['outcome'] == 'EVIDENCE_GAP'
    assert failed['resume'] in resumed_states and failed['firstData'] in resumed_states
    assert failed['resume']['durable'] == failed['firstData']['sendOffset'] == 8192
    assert failed_states[0]['captureId'] != resumed_states[0]['captureId']
    assert js(OLD/'pipeline-01/device/result.json')['outcome'] == 'UNRESOLVED_STATE'
    assert js(OLD/'recovery-02/result.json')['processClosed']
    assert js(NEW/'pipeline-01/result.json')['device'] == 'NOT_RUN'
    assert not v.STORE.exists(NEW/'pipeline-01/device')
    restorations = []
    for folder in (OLD/'pipeline-01',OLD/'continuation-01',RUN):
        before, after = js(folder/'channels-before.json'), js(folder/'channels-restored.json')
        assert before['beta'] == after['beta']
        assert after['stable']['revision'] == before['stable']['revision']+2
        assert {k:x for k,x in before['stable'].items() if k!='revision'} == {k:x for k,x in after['stable'].items() if k!='revision'}
        restorations.append([before['stable']['revision'],after['stable']['revision']])
    assert restorations == [[64,66],[66,68],[68,70]]
    for folder in (OLD/'supervisor-01',OLD/'continuation-01/supervisor-01',NEW/'supervisor-01',RUN/'supervisor-01'):
        js(folder/'result.json')
    for p in v.STORE.glob(AREA, '*.started.json', recursive=True):
        end = js(p.with_name(p.name.replace('started','closed')))
        assert end['cleanup_complete'], str(p)
    assert all(not v.STORE.exists(ROOT/'.cache'/name) for name in ('p34-live-device.lock','p35-reconcile-device.lock','p35-pipeline.lock'))
    mirror = js(RUN/'device/logcat-diagnostic-integrity.json')
    assert mirror['usedForInjection'] is False and mirror['nativeMirror']['status'] == 'FAILED_DISABLED'
    return dict(failed30312Preserved=True, separateCaptures=True, downloadFailurePreserved=True,
                channelRestorations=restorations, currentLocalLocksAbsent=True,
                auxiliaryLogcat='Incomplete; not the primary observation source')
