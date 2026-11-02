"""P3-5 v5: independent offline original evaluation, never another campaign."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import original as v
import supplement as s
import store

ROOT = v.ROOT
BUNDLE = ROOT / 'docs/acceptance-contracts/P3-5-v5'


def predecessor_plan(contract, matrix, digest, previous):
    sys.path.insert(0, str(ROOT))
    from Tools.acceptance import validate_bundle as validator
    pc, pm, ph, mh = validator._load_bundle(previous / 'contract.json', previous / 'matrix.json')
    assert not validator.validate_contract_lineage(contract, pc, digest, ph)
    return validator.compute_rerun_plan(contract, pc, pm, digest, ph, mh, matrix['round_id'], ROOT)


def precheck(source, target, contract_path, matrix_path):
    sys.path.insert(0, str(ROOT))
    from Tools.acceptance import validate_bundle as validator
    contract, matrix, digest, _ = validator._load_bundle(contract_path, matrix_path)
    assert contract['status'] == 'FROZEN' and matrix['overall_result'] == 'NOT_RUN'
    errors = validator.validate_contract(contract)
    errors += validator.validate_matrix(matrix, contract, digest)
    errors += validator.validate_freeze_objects(contract, ROOT)
    errors += validator.validate_execution_worktree(contract, ROOT)
    errors += validator.validate_external_inputs(contract, BUNDLE)
    assert not errors, errors
    actual = 'python -I -S -B -X utf8 ' + ' '.join(sys.argv).replace('\\', '/')
    command, = contract['commands']
    assert command['command'] == actual
    assert any(x['evidence_path'] == source.relative_to(BUNDLE).as_posix()
               and x['evidence_sha256'] == store.sha(source.read_bytes()) for x in contract['external_inputs'])
    assert any(x['path'] == target.relative_to(BUNDLE).as_posix() for x in contract['artifacts'])
    plan = predecessor_plan(contract, matrix, digest, BUNDLE / 'history/v4')
    assert plan == json.loads((BUNDLE / 'rerun-plan.json').read_bytes())
    assert plan['required_commands'] == [command['id']]
    return dict(contract_sha256=digest, freeze_commit=contract['freeze_commit'], result='PASS')


def mobile_chain():
    plan = v.js(v.TEN / 'pipeline-01/plan.json')
    states, integrity = v.capture(v.TEN / 'pipeline-01/device')
    required = ('checkingUpdate', 'downloading', 'readyToInstall', 'transferring', 'completed')
    sequence = []
    for phase in required:
        matches = [x for x in states if x['phase'] == phase and (not sequence or x['seq'] > sequence[-1])]
        assert matches, phase
        sequence.append(matches[0]['seq'])
    ready = next(x for x in states if x['seq'] == sequence[2])
    v.r.bound(ready, plan, package=True)
    assert ready['packageVerified'] and ready['freshConnection']
    target = v.js(v.TEN / 'pipeline-01/target.json')
    cloud = v.TEN / 'pipeline-01/cloud'
    responses = [v.js(p) for p in v.STORE.glob(cloud, '*-response.json')]
    releases = [r for response in responses for r in response['data'].get('firmwareReleases', [])
                if r['releaseId'] == target['releaseId']]
    assert releases and all(r['state'] == 'ready' and not r['archived'] for r in releases)
    for asset in target['assets']:
        assert any(all(a[k] == asset[k] for k in ('kind','sha256','sizeBytes','fileName')) and a['r2State']=='available'
                   for r in releases for a in r['assets'])
    latest = [r['data'] for r in responses if r['data'].get('updateAvailable') is True]
    assert any(all(x[k] == target[k] for k in ('releaseId','versionCode','targetImageSha256')) for x in latest)
    return dict(phaseSequences=sequence, package=ready['packageSha256'], release=target['releaseId'], records=integrity['records'])


def admission():
    cfg = v.js(v.TEN / 'inputs/configuration.json')
    import pipeline
    assert pipeline.validate(cfg) == 30309
    pre = v.js(v.TEN / 'preflight/result.json')
    assert pre['outcome'] == 'APPROVED_PREFLIGHT_PASS' and pre['privatePortsClosed']
    # Check the campaign's fresh identity, not just the earlier admission label.
    prior = v.js(v.TEN / 'inputs/device-admission.json')
    assert prior['outcome'] == 'FRESH_CURRENT_IDENTITY_VERIFIED'
    states, _ = v.capture(v.TEN / 'pipeline-01/device')
    plan = v.js(v.TEN / 'pipeline-01/plan.json')
    initial = next(x for x in states if x['phase']=='idle' and x['freshConnection'] and x['linkConnected'])
    v.r.bound(initial, plan)
    assert initial['currentVersionCode'] == prior['current']['currentVersionCode']
    assert initial['currentImageSha256'] == prior['current']['currentImageSha256']
    return dict(historicalAdmissionVersion=prior['current']['currentVersionCode'], campaignInitialVersion=initial['currentVersionCode'],
                newPhysicalAdmission=False, originalSource=v.js('docs/acceptance-contracts/P3-5-v3.contract.json')['freeze_commit'])


def evaluate(originals):
    v.STORE = originals
    v.checks.clear()
    v.inputs.clear()
    v.details.clear()
    checks = [
        ('packet-integrity', originals.verify), ('source-identity', v.source_identity),
        ('ten-original-manifest', lambda:v.manifest(v.TEN/'closeout-01/outputs.json')),
        ('supplement-original-manifest', lambda:v.manifest(v.SUP/'closeout-04/outputs.json')),
        ('ci-red-green',v.ci), ('release-assets',v.release_assets), ('ten-recoveries',v.ten_recoveries),
        ('supplements',v.supplements), ('mcu-readbacks',v.mcu), ('cleanup-and-failures',v.cleanup_and_failures),
        ('negative-controls',v.negative_controls), ('build-originals',v.build_originals),
        ('supplemental-failure-lineage',v.supplemental_failure_lineage),
        ('prior-review-integrity',s.prior_review), ('supplement-source',s.source_binding),
        ('remediation-inventory',lambda:v.manifest(s.NEW/'closeout-01/outputs.json')),
        ('zero-position-and-negative-controls',s.position), ('firmware-ci-originals',s.builds),
        ('mcu-originals',s.mcu), ('failure-and-restoration-lineage',s.lineage),
        ('mobile-chain',mobile_chain), ('admission',admission)]
    for name, fn in checks:
        v.check(name,fn)
    by = {x['id']:x for x in v.checks}
    common = ['packet-integrity','source-identity','supplement-source','prior-review-integrity']
    mapping = {
        'C-ADMISSION':['admission'], 'C-MOBILE-CHAIN':['mobile-chain','release-assets','ci-red-green','ten-recoveries'],
        'C-FINAL-IDENTITY':['ten-recoveries','mcu-readbacks','mcu-originals'],
        'C-NO-UPDATE':['ten-recoveries','zero-position-and-negative-controls'],
        'C-INTEGRITY':['ten-original-manifest','supplement-original-manifest','remediation-inventory','negative-controls'],
        'C-CLEANUP':['cleanup-and-failures','supplemental-failure-lineage','failure-and-restoration-lineage','build-originals','firmware-ci-originals'],
        'C-COVERAGE':['ten-recoveries','supplements','zero-position-and-negative-controls'],
        'C-PUBLICATION':['build-originals','firmware-ci-originals','mobile-chain']}
    mapping.update({'R%02d'%i:['ten-recoveries'] for i in range(1,11)})
    criteria = {}
    for name, dependencies in mapping.items():
        dependencies = common + dependencies
        passed = all(by[n]['result']=='PASS' for n in dependencies)
        criteria[name] = dict(result='PASS' if passed else 'NOT_OBSERVED', observed=True if passed else None,
                              checks=dependencies)
    return dict(result='PASS' if all(x['result']=='PASS' for x in criteria.values()) else 'EVIDENCE_GAP',
                criteria=criteria, checks=v.checks, originalReads=len(originals.reads),
                operation='independent offline evaluation of dated originals', newDeviceOperations=0,
                coverage='Original 30309 R01-R10 plus separate 30313 pre-durable supplement; not a replacement R01',
                limits=['Auxiliary Logcat incomplete','No continuous ten-minute transfer or endurance claim'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--contract',type=Path)
    parser.add_argument('--matrix',type=Path)
    args=parser.parse_args()
    assert Path.cwd()==ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode and not sys.flags.optimize
    target=v.path(args.out)
    assert not target.exists()
    source=v.path(args.inputs)
    formal=target.is_relative_to(BUNDLE)
    if formal:
        gate=precheck(source,target,args.contract,args.matrix)
    else:
        assert target.is_relative_to(ROOT/'.cache/p35-formal-closeout-20261102') and args.contract is None and args.matrix is None
        gate=None
    result=evaluate(store.load(source,ROOT,v.host_io.checked_output))
    result['formalPrecheck']=gate
    v.host_io.write_json(ROOT,target,result)
    print(json.dumps(dict(result=result['result'],criteria=result['criteria'])),flush=True)
    return 0 if result['result']=='PASS' else 1


if __name__=='__main__':
    raise SystemExit(main())
