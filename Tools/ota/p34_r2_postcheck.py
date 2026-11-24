"""Post-OTA exact R2-B identity and R2-A mapped backup, in two read-only owners."""
import argparse
from pathlib import Path
import re
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'Tools/ota'))
import p34_r2_checkpoint_capture as checkpoint
import p34_r2_backup_byte_device as baseline
import p34_r2_trial_assets as asset_api
from recovery_confirm import r2_new_backup as backup

cli, host, base, bind = baseline.cli, baseline.host, baseline.base, baseline.byte.bind
SELF = Path(__file__).resolve()
TEST = ROOT/'tests/boot/test_p34_r2_postcheck.py'
ASSET_RECEIPT = ROOT/'.cache/p34-r2-trial-assets2/result.json'
IMAGE_A = ROOT/'.cache/p34-recovery-sources1/r2-a.bin'
IMAGE_B = ROOT/'.cache/p34-recovery-sources1/r2-b.bin'
ASSETS = dict(checkpoint.ASSETS, image=IMAGE_B)
SCOPE = 'Completed R2-A to R2-B snapshot then read-only B identity/original Boot or mapped A backup; no reset/write'
SUCCESS = dict(identity='R2_CHECKPOINT_NATIVE_CLOSED', backup='R2_BACKUP_MAPPED_NATIVE_CLOSED')
WORKER_SECONDS, PARENT_SECONDS = 900, 1020
mapped = SimpleNamespace(**dict(vars(baseline.mapped), Capture=backup.Capture, expected=backup.expected,
    READS=backup.READS, PAYLOAD_BYTES=backup.PAYLOAD_BYTES, PAYLOAD_SHA=backup.PAYLOAD_SHA))
mapped_owner = SimpleNamespace(**dict(vars(baseline.owner), ASSETS={k: ASSETS[k] for k in ('image', 'map_bytes')}))
mapped_component = SimpleNamespace(**dict(vars(baseline.component), ARCHIVE=IMAGE_A))
execute_backup = bind(baseline.prior.execute, mapped=mapped, owner=mapped_owner)
QUERY = ROOT/'.cache/worktrees/p3-4-link-stats/.cache/p3-4-log-device-20260921/usb_capture.py'
repaired = asset_api.policy.old.repaired


def observation_reader(store):
    reader = repaired.fixed_envelope()
    reader.ROOT, reader.checked = ROOT, store.checked
    return reader


def query_reader(store, reader):
    query = cli.load_module('r2_original_query_reader', store.checked(QUERY))
    query.m = reader
    return query


def reader_sources(store):
    query = query_reader(store, observation_reader(store))
    return [Path(repaired.__file__), Path(repaired.batch.followup.__file__),
        repaired.ENVELOPE, repaired.batch.followup.ENVELOPE,
        ROOT/'Tools/ota/p34_observation.py', QUERY, Path(query.u.__file__), Path(query.s.__file__)]


def verify_trigger(store, path):
    path = store.checked(path)
    cli.require(path.name == 'snapshot.jsonl' and path.parent.name == 'finished', 'original finished snapshot path required')
    cell = path.parent.parent
    config = store.read(cell/'runtime-config.json')
    launch = store.read(cell/'launch.json')
    query = store.read(cell/'queries/result.json')
    assets = store.read(ASSET_RECEIPT)['groups']['transition']
    asset_api.policy.validate(config, assets)
    original = store.read(ROOT/'.cache/p34-sha-candidate/trials/measure/cells/s04/runtime-config.json')
    cli.require(config['target'] == original['target'], 'different physical BLE target')
    apk = asset_api.policy.installed(store)
    cli.require(launch['apk'] == apk['apk'], 'actual launch APK differs')
    envelope = observation_reader(store)
    summary, _, _ = asset_api.policy.batch.radio.backend.verify_full_snapshot(envelope, path.read_bytes(), config,
        cli.record(cell/'runtime-config.json')['sha256'], launch['pid'], apk['metadata']['device_observation']['sentinel'])
    cli.require(query['start_inputs_verified_before'] is True and query['pid'] == launch['pid'] and
        query['config'] == cli.record(cell/'runtime-config.json') and
        (cell/'queries/package.etu').read_bytes() == Path(assets['package']['path']).read_bytes(),
        'original downloaded-byte admission missing')
    q = cell/'queries'
    originals = [q/name for name in ('events.jsonl', 'health-before.json', 'health-after.json', 'health-ready.json')]
    for original_path in originals: store.checked(original_path)
    verified, _, messages = query_reader(store, envelope).validate(
        originals[0].read_bytes(), originals[1].read_bytes(), originals[2].read_bytes(),
        pid=launch['pid'], sentinel=apk['metadata']['device_observation']['sentinel'], target=config['target'])
    ready = store.read(originals[3])
    cli.require(verified['successfulQueries'] > 0 and
        verified['captureId'] == ready['captureId'] == summary['captureId'] and
        ready['healthy'] is True and ready['lost'] == 0 and ready['error'] is None and
        ready['upgradeStarts'] == ready['upgradeEnds'] == 0 and ready['outcome'] is None,
        'original prestart capture/admission differs')
    asset_api.policy.verify(envelope, messages, config, cli.record(cell/'runtime-config.json')['sha256'])
    for leaf in ('health-before.json', 'health-after.json'):
        health = store.read(path.parent/leaf)
        cli.require(health['healthy'] is True and health['lost'] == 0 and health['error'] is None and
            health['upgradeStarts'] == health['upgradeEnds'] == 1 and health['outcome'] == 'completed' and
            health['captureId'] == summary['captureId'], 'original completed health differs')
    paths = [path, cell/'runtime-config.json', cell/'launch.json', cell/'queries/result.json', cell/'queries/package.etu',
             path.parent/'health-before.json', path.parent/'health-after.json', *originals]
    return dict(kind='ORIGINAL_R2_OTA_SNAPSHOT_NOT_FINAL_DEVICE_VERIFICATION', snapshot=cli.record(path),
                inputs=[cli.record(store.checked(p)) for p in paths], summary=summary, final_device_verified=False)


def sources(store):
    tested_assets = store.read(ASSET_RECEIPT)
    cli.require(tested_assets['result'] == 'R2_TRIAL_ASSETS_HOST_VERIFIED' and
        tested_assets['inputs'] == [cli.record(p) for p in asset_api.sources(store)] and
        tested_assets['groups']['transition'] == asset_api.derive(store), 'fixed R2 sender assets changed')
    paths = [*baseline.sources(store), *checkpoint.sources(store), *asset_api.sources(store),
        SELF, TEST, Path(backup.__file__), Path(checkpoint.__file__), *reader_sources(store),
        ROOT/'Tools/ota/p34_session_backend.py', ASSET_RECEIPT, IMAGE_A, IMAGE_B,
        asset_api.policy.APK, ROOT/'.cache/p34-r2-backup-byte-tests2/result.json',
        *(Path(r['path']) for r in asset_api.policy.installer.sources()),
        ROOT/'Tools/ota/p34_signing_artifacts.py']
    return list(dict.fromkeys(paths))


def validate_plan(store, plan, out, current):
    cli.require(plan['out'] == str(out) and plan['scope'] == SCOPE and plan['inputs'] == current and
                plan['kind'] in SUCCESS, 'post-OTA source/scope/kind differs')
    test = store.checked(plan['tests']['path'])
    cli.require(cli.record(test) == plan['tests'], 'post-OTA tests changed')
    tested = store.read(test)
    cli.require(tested['result'] == 'R2_POST_OTA_HOST_PASS' and tested['hardware'] is False and
                tested['inputs'] == current, 'current post-OTA tests required')
    cli.require(plan['trigger'] == verify_trigger(store, plan['trigger']['snapshot']['path']), 'post-OTA trigger changed')
    cli.require(plan['worker_seconds'] == WORKER_SECONDS and plan['parent_seconds'] == PARENT_SECONDS and
        plan['connection_generation'] == 'r2-post-'+plan['kind']+'-'+out.name and
        plan['before_history'] == base.history(store) and plan['native_history_approved'] == str(base.HISTORY),
        'post-OTA lifetime/generation/history differs')


def worker(store, out, kind):
    cli.require(base.in_job(), 'owned post-OTA worker required')
    cli.require(store.read(out/'plan.json')['kind'] == kind, 'worker kind differs')
    if kind == 'identity':
        call = bind(checkpoint.worker, sources=sources, validate_worker_plan=validate_plan, ASSETS=ASSETS)
    else:
        call = bind(baseline.prior.worker, sources=sources, validate_worker_plan=validate_plan,
                    mapped=mapped, owner=mapped_owner, component=mapped_component, execute=execute_backup)
    return call(store, out)


def audit_trace(kind, *args):
    if kind == 'identity': return checkpoint.owner.audit_trace(*args)
    cli.require(kind == 'backup', 'post-OTA audit kind differs')
    return bind(baseline.prior.audit_trace, mapped=mapped)(*args)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=('selftest', 'check', 'capture', 'worker'))
    p.add_argument('--output-dir', type=Path, required=True)
    p.add_argument('--kind', choices=tuple(SUCCESS), default='identity')
    p.add_argument('--tests', type=Path)
    p.add_argument('--snapshot', type=Path)
    p.add_argument('--native-history-approved', type=Path)
    a = p.parse_args()
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                'isolated explicit root required')
    store = cli.Store(ROOT)
    out = store.checked(a.output_dir)
    if a.action == 'worker': return worker(store, out, a.kind)
    paths = sources(store)
    checkpoint.owner.preflight(store, out, paths)
    for name in ('backup-header.bin', 'backup-payload.bin'): store.checked(out/name)
    records = [cli.record(p) for p in paths]
    if a.action == 'check':
        print('POST_OTA_PREFLIGHT_PASS', len(paths)); return 0
    if a.action == 'capture':
        cli.require(a.native_history_approved == base.HISTORY, 'exact native history permission required')
        test = store.checked(a.tests)
        tested = store.read(test)
        cli.require(tested['result'] == 'R2_POST_OTA_HOST_PASS' and tested['inputs'] == records, 'current post tests required')
        trigger, before = verify_trigger(store, a.snapshot), base.history(store)
        cli.require(not base.native_presence()['debugger_processes'], 'competing debugger present')
    env = host.environment(store, out)
    for path in paths: store.raw(out/'source'/path.relative_to(ROOT), path.read_bytes())
    if a.action == 'selftest':
        log = host.command(store, out, 'tests', [sys.executable, '-I', '-S', '-B', '-X', 'utf8', TEST, '-v'], env, 240)
        count = re.search(rb'Ran (\d+) tests? in .*\r?\n\r?\nOK\b', log)
        cli.require(count and records == [cli.record(p) for p in paths], 'post test/source drift')
        store.write(out/'result.json', dict(result='R2_POST_OTA_HOST_PASS', tests=int(count[1]), inputs=records, hardware=False))
        print('R2_POST_OTA_HOST_PASS', int(count[1])); return 0
    store.write(out/'plan.json', dict(out=str(out), scope=SCOPE, kind=a.kind, inputs=records, tests=cli.record(test),
        trigger=trigger, before_history=before, native_history_approved=str(base.HISTORY),
        worker_seconds=WORKER_SECONDS, parent_seconds=PARENT_SECONDS,
        connection_generation='r2-post-'+a.kind+'-'+out.name))
    result = base.owned_run(store, out, [SELF, 'worker', '--kind', a.kind, '--output-dir', out], env, timeout=PARENT_SECONDS)
    result.update(after_history=base.history(store), presence_after=base.native_presence())
    store.write(out/'parent.json', result)
    print(result)
    return 0 if result['exit'] == 0 and not result['timeout'] else 1


if __name__ == '__main__': raise SystemExit(main())
