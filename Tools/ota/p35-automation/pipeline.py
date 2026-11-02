"""One test-only CI -> channel -> real P3-5 runner -> restoration entry."""
import argparse
import copy
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import re
import sys

import runner as r
from pipeline_build import Build, VARIABLES
from pipeline_cloud import Cloud, PUBLIC

ROOT = r.ROOT
LOCK = ROOT / '.cache/p35-pipeline.lock'


def validate(c):
    required = {'schema', 'run_id', 'build', 'cloud', 'plan', 'authority'}
    r.require(isinstance(c, dict) and required <= set(c) <= required | {'test_profile'},
              'pipeline configuration fields')
    r.require('test_profile' not in c or c['test_profile'] in {'single-upgrade', 'resume-once', 'background-lock'},
              'unknown pipeline test profile')
    r.require(type(c['schema']) is int and c['schema'] == 1 and
              re.fullmatch(r'p35-[a-z0-9-]{1,40}', c['run_id']), 'pipeline schema/run_id')
    b = c['build']
    r.require(isinstance(b, dict) and set(b) == {'ref', 'sha', 'workflow_blob', 'version', 'seconds', 'variables'}, 'build fields')
    r.require(isinstance(b['ref'], str) and re.fullmatch(r'dev/firmware/[A-Za-z0-9_-]+', b['ref']),
              'explicit development firmware branch required')
    for field in ('sha', 'workflow_blob'):
        r.require(isinstance(b[field], str) and re.fullmatch('[0-9a-f]{40}', b[field]) and b[field] != '0' * 40,
                  'pinned source/workflow required')
    r.require(isinstance(b['version'], str) and re.fullmatch(r'(0|[1-9][0-9]*)\.(0|[1-9][0-9]?)\.(0|[1-9][0-9]?)', b['version']),
              'canonical major.minor.patch required (minor/patch < 100)')
    major, minor, patch = map(int, b['version'].split('.'))
    version = major * 10000 + minor * 100 + patch
    r.require(0 < version <= 0xffffffff, 'firmware version overflow')
    r.require(type(b['seconds']) is int and 60 <= b['seconds'] <= 10800, 'bounded build deadline')
    r.require(isinstance(b['variables'], dict) and set(b['variables']) <= VARIABLES, 'test variable allowlist')
    for change in b['variables'].values():
        r.require(isinstance(change, dict) and set(change) == {'before', 'during'} and
                  all(isinstance(x, str) and 0 < len(x) < 32768 for x in change.values()), 'exact reviewed variable values')
    r.require(isinstance(c['cloud'], dict) and set(c['cloud']) == {'actor_sha256', 'query'} and
              r.digest(c['cloud']['actor_sha256']), 'cloud fields')
    query = c['cloud']['query']
    r.require(isinstance(query, dict) and query.get('appId') == 'trace' and
              query.get('deviceModel') == 'e-track-at32f435' and query.get('channel') == 'stable', 'test latest query')
    allowed = {'appId', 'deviceModel', 'channel', 'currentVersionCode', 'currentImageSha', 'appVersionCode',
               'hardwareRevision', 'layoutId', 'bootVersion', 'protocolVersion'}
    r.require(set(query) == allowed and all(type(x) in (str, int) for x in query.values()), 'complete latest query, no custom fields')
    for name, maximum in [('currentVersionCode', 0xffffffff), ('appVersionCode', 0x7fffffff),
                          ('hardwareRevision', 65535), ('layoutId', 255), ('bootVersion', 255), ('protocolVersion', 255)]:
        r.require(r.uint(query[name], maximum), 'invalid query field: ' + name)
    r.require(query['protocolVersion'] == 1 and r.digest(query['currentImageSha']),
              'public firmware API compatibility version is 1; wire v2 is a separate field')
    pin = c['plan']
    r.require(isinstance(pin, dict) and set(pin) == {'path', 'bytes', 'sha256'} and
              isinstance(pin['path'], str) and type(pin['bytes']) is int and 0 < pin['bytes'] <= 1048576 and
              r.digest(pin['sha256']), 'pinned existing runner plan/template required')
    authority = c['authority']
    r.require(isinstance(authority, dict) and set(authority) == {
        'test_ci', 'test_channel', 'device_campaign', 'exclusive_rehearsal_environment', 'reference'}, 'authority fields')
    r.require(all(type(authority[k]) is bool for k in authority if k != 'reference') and
              isinstance(authority['reference'], str) and 0 < len(authority['reference']) <= 500, 'authority declaration')
    return version


def windows(size):
    r.require(40960 <= size <= 0x180000, 'package too small for ten block-aligned windows')
    starts = [(size * i // 10) // 4096 * 4096 for i in range(10)]
    return [dict(id='R%02d' % (i + 1), durable_min=start,
                 durable_max=(starts[i + 1] if i < 9 else size) - 1, bitmap='any') for i, start in enumerate(starts)]


def make_plan(template, c, target):
    p = copy.deepcopy(template)
    p['run_id'] = c['run_id']
    r.require(p['firmware']['protocol'] == 2, 'automatic windows currently support only the reviewed v2 profile')
    p['firmware'].update(target=dict(version=target['versionCode'], sha256=target['targetImageSha256']),
                         package=target['package'], release_id=target['releaseId'],
                         latest_url=PUBLIC + '/api/public/firmware/latest')
    single = c.get('test_profile') == 'single-upgrade'
    scenario = c.get('test_profile') in {'resume-once', 'background-lock'}
    r.require(p.get('test_profile') == c.get('test_profile'), 'pipeline/runner profile mismatch')
    p['cases'] = [] if single or c.get('test_profile') == 'background-lock' else windows(target['package']['bytes'])
    if c.get('test_profile') == 'resume-once':
        p['cases'] = [dict(id='R01', durable_min=4096, durable_max=target['package']['bytes']//2-1, bitmap='any')]
    return r.validate_plan(p, single=single, scenarios=scenario)


def inputs(c, h):
    version = validate(c)
    single = c.get('test_profile') == 'single-upgrade'
    scenario = c.get('test_profile') in {'resume-once', 'background-lock'}
    template = r.validate_plan(r.strict_json(h.pinned(c['plan']).read_bytes()), single=single, scenarios=scenario)
    r.require(template.get('test_profile') == c.get('test_profile'), 'pipeline/runner profile mismatch')
    r.require(template['firmware']['protocol'] == 2 and version > template['firmware']['current']['version'],
              'new forward v2 firmware required')
    r.require(not template['cases'] or template.get('allow_bluetooth_toggle') is True, 'runner plan must explicitly allow fault injection')
    query = c['cloud']['query']
    for k, value in {'currentVersionCode': template['firmware']['current']['version'],
                     'currentImageSha': template['firmware']['current']['sha256'],
                     'appVersionCode': template['app']['version_code']}.items():
        r.require(query.get(k) == value, 'public query/phone plan mismatch: ' + k)
    for pin in (template['phone']['adb'], template['phone']['adb_key']):
        h.pinned(pin)
    return template, dict(c['build'], version_code=version)


def environment(h, out):
    env = h.environment(out)
    for name in ('GH_DEBUG', 'GH_HOST', 'GH_ENTERPRISE_TOKEN', 'GITHUB_TOKEN', 'GITHUB_ENTERPRISE_TOKEN',
                 'NODE_OPTIONS', 'NODE_EXTRA_CA_CERTS', 'SSLKEYLOGFILE', 'P35_ACCESS_TOKEN',
                 'HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY'):
        env.pop(name, None)
    env.update(GH_CONFIG_DIR=str(h.checked(out / 'host/gh')), GH_PROMPT_DISABLED='1',
               GH_NO_UPDATE_NOTIFIER='1', GH_NO_EXTENSION_UPDATE_NOTIFIER='1')
    return env


def device_run(plan, out, h, env):
    device_env = {k: v for k, v in env.items() if k not in ('GH_TOKEN', 'P35_ACCESS_TOKEN')}
    run_out = out / 'device'
    r.load_smoke().preflight_outputs(h, run_out)
    h.command(out, 'campaign', [sys.executable, '-I', '-S', '-B', '-X', 'utf8',
        'Tools/ota/p35-automation/runner.py', 'run', '--plan', str(out / 'plan.json'),
        '--out', str(run_out), '--execute'] + (['--single-upgrade'] if plan.get('test_profile') == 'single-upgrade' else
        ['--scenario-coverage'] if plan.get('test_profile') in {'resume-once', 'background-lock'} else []), device_env,
        seconds=min(18000, plan['limits']['total_seconds'] + 300), success_codes=(0, 2))
    result = h.read_json(run_out / 'result.json')
    receipt = h.read_json(out / 'campaign.closed.json')
    r.require(receipt['cleanup_complete'], 'runner process cleanup incomplete')
    r.require(receipt['exit_code'] == 0 or result['outcome'] != 'AUTOMATION_COMPLETED', 'runner exit/result contradiction')
    return result


def execute(c, template, build_config, out, h, build_factory=Build, cloud_factory=Cloud, run=device_run):
    r.require(not h.checked(LOCK).exists(), 'existing pipeline; reconcile before a new build')
    for name in ('p34-live-device.lock', 'p35-reconcile-device.lock'):
        r.require(not h.checked(ROOT / '.cache' / name).exists(), 'unresolved device state; no new build')
    for folder in (out, out / 'build', out / 'cloud', out / 'host', out / 'device'):
        h.checked(folder)
    h.fresh(out)
    h.save(out / 'configuration.json', c)
    sources = [h.record(Path(__file__).parent / name) for name in
               ('pipeline.py', 'pipeline_build.py', 'pipeline_cloud.py', 'runner.py', 'smoke.py', 'live_stream.py', 'scenarios.py', 'logcat_binary.py')]
    h.save(out / 'source-pins.json', sources)
    owner = dict(pid=os.getpid(), out=str(out), configurationSha256=hashlib.sha256(
        (out / 'configuration.json').read_bytes()).hexdigest())
    h.save(out / 'owner.json', owner)
    h.save(LOCK, owner)
    result = dict(outcome='NOT_RUN', device='NOT_RUN', cloudRestored=True, buildRestored=False,
                  formalAcceptance='NOT_ADJUDICATED')
    build, cloud, original, target, activation_attempted = None, None, None, None, False
    build_restore_attempted = False
    try:
        env = environment(h, out)
        build = build_factory(build_config, h.fresh(out / 'build'), h, env, 'P35 pipeline ' + c['run_id'])
        cloud = cloud_factory(c['cloud'], h.fresh(out / 'cloud'), h)
        build.preflight()
        original = cloud.preflight(build_config['version_code'])
        h.save(out / 'channels-before.json', original)
        target = build.start()
        h.save(out / 'target.json', target)
        plan = make_plan(template, c, target)
        h.save(out / 'plan.json', plan)
        # CI is terminal now. Restore its temporary configuration before opening the device window.
        build_restore_attempted = True
        build.restore()
        result['buildRestored'] = True
        h.save(out / 'activation-intent.json', dict(releaseId=target['releaseId'],
            target=h.record(out / 'target.json'), original=h.record(out / 'channels-before.json')))
        activation_attempted = True
        result['cloudRestored'] = False
        cloud.activate(original, target, c['cloud']['query'])
        for source in sources:
            h.pinned(source)
        actual = run(plan, out, h, env)
        result['device'] = actual['outcome']
        result['outcome'] = 'PASS' if actual['outcome'] == 'AUTOMATION_COMPLETED' else 'FAIL'
    except BaseException as error:
        result.update(outcome='FAIL', errorType=type(error).__name__,
                      detail=str(error) if isinstance(error, r.Stop) else 'inspect preserved step receipts')
    finally:
        if activation_attempted:
            try:
                restored = cloud.restore(original, target)
                h.save(out / 'channels-restored.json', restored)
                result['cloudRestored'] = True
            except BaseException as error:
                result.update(restoreError=type(error).__name__, cloudRestored=False)
        if build is not None and not build_restore_attempted:
            try:
                build.restore()
                result['buildRestored'] = True
            except BaseException as error:
                result['buildRestoreError'] = type(error).__name__
        complete = result['cloudRestored'] and result['buildRestored']
        if not complete:
            result['outcome'] = 'UNRESOLVED_STATE'
        result['deviceLockRetained'] = (ROOT / '.cache/p34-live-device.lock').exists()
        if result['deviceLockRetained']:
            result['outcome'] = 'UNRESOLVED_STATE'
        h.save(out / 'result.json', result)
        if complete:
            r.require(h.read_json(LOCK) == owner, 'pipeline ownership changed')
            h.checked(LOCK).unlink()
    return result


def recover(prior, out, h):
    """Explicit remote cleanup only. Never dispatch CI or launch the phone again."""
    prior = h.checked(prior)
    owner = h.read_json(prior / 'owner.json')
    r.require(h.read_json(h.checked(LOCK)) == owner and owner['out'] == str(prior), 'recovery owner mismatch')
    raw = (prior / 'configuration.json').read_bytes()
    r.require(hashlib.sha256(raw).hexdigest() == owner['configurationSha256'], 'recovery configuration changed')
    c = r.strict_json(raw)
    version = validate(c)
    h.fresh(out)
    env = environment(h, out)
    tasks = h.command(out, 'owner-check', ['tasklist', '/FO', 'CSV', '/NH', '/FI', 'PID eq ' + str(owner['pid'])], env, seconds=15)
    rows = csv.reader(io.StringIO(tasks.decode('utf-8', 'replace')))
    r.require(not any(len(x) > 1 and x[1] == str(owner['pid']) for x in rows), 'original pipeline owner still alive')
    build = Build(dict(c['build'], version_code=version), h.fresh(out / 'build'), h, env, 'P35 pipeline ' + c['run_id'])
    old = prior / 'build'
    build.changed = [name for name in c['build']['variables'] if (old / ('variable-' + name + '-intent.json')).exists()]
    build.dispatch_attempted = (old / 'dispatch-intent.json').exists()
    if build.dispatch_attempted:
        r.require((old / 'run-bound.json').exists(), 'dispatch unbound; inspect GitHub before cleanup; never redispatch')
        build.run_id = h.read_json(old / 'run-bound.json')['id']
        run = build.api('/actions/runs/' + str(build.run_id))
        r.require(run['head_sha'] == c['build']['sha'] and run['status'] == 'completed' and run['run_attempt'] == 1,
                  'CI still active or changed; preserve temporary variables')
        build.terminal = True
    if not (old / 'variables-restored.json').exists():
        build.restore()
    if (prior / 'activation-intent.json').exists():
        intent = h.read_json(prior / 'activation-intent.json')
        h.pinned(intent['target'])
        h.pinned(intent['original'])
        cloud = Cloud(c['cloud'], h.fresh(out / 'cloud'), h)
        restored = cloud.restore(h.read_json(prior / 'channels-before.json'), h.read_json(prior / 'target.json'))
        h.save(out / 'channels-restored.json', restored)
    h.save(out / 'result.json', dict(outcome='REMOTE_STATE_RESTORED', device='NOT_RUN', original=str(prior)))
    r.require(h.read_json(LOCK) == owner, 'pipeline ownership changed during recovery')
    h.checked(LOCK).unlink()
    return dict(outcome='REMOTE_STATE_RESTORED', device='NOT_RUN')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('pipeline', 'pipeline-check', 'pipeline-recover'))
    parser.add_argument('--config', type=Path)
    parser.add_argument('--prior', type=Path)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args(argv)
    r.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
              'run from the worktree with Python -I -S -B')
    h = r.load_host()
    if args.mode == 'pipeline-recover':
        r.require(args.execute and args.prior is not None and args.out is not None and args.config is None,
                  'recovery requires --prior, fresh --out and --execute, no config override')
        result = recover(args.prior, h.checked(args.out), h)
    else:
        r.require(args.config is not None and args.prior is None, '--config required')
        r.require(args.config.stat().st_size <= 1048576, 'oversized configuration')
        c = r.strict_json(args.config.read_bytes())
        template, build = inputs(c, h)
        if args.mode == 'pipeline-check':
            r.require(not args.execute and args.out is None, 'check is offline and has no outputs')
            result = dict(outcome='CONFIGURATION_VALID', network='NOT_RUN', device='NOT_RUN')
        else:
            r.require(args.execute and args.out is not None, '--execute and fresh --out required')
            r.require(all(c['authority'][k] is True for k in c['authority'] if k != 'reference'),
                      'explicit task CI/test-cloud/device/exclusive-environment authority required')
            result = execute(c, template, build, h.checked(args.out), h)
    print(json.dumps(result))
    return 0 if result['outcome'] in ('PASS', 'CONFIGURATION_VALID', 'REMOTE_STATE_RESTORED') else 2
