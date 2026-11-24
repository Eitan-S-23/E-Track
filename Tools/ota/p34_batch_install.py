"""Verified same-signer batch APK replacement, preserving completed OTA records."""
import argparse
import json
from pathlib import Path
import runpy
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'Tools/ota'))
import p34_session as cli
import p34_batch_phone_check as prior
import p34_batch_artifacts as artifact

AREA = ROOT / '.cache/p34-batch-fix'
OUT = AREA / 'install-001'


def inputs(s):
    report = s.read(AREA / 'apk-g1/apk.json')
    signer = runpy.run_path(str(ROOT / 'Tools/ota/p34_signing_artifacts.py'))
    cli.require(report['sha'] == artifact.SHA and report['metadata']['application_id'] == prior.PKG and
                report['certificate_sha256'] == signer['CERT'] and
                cli.record(report['apk']['path']) == report['apk'] and
                signer['apk_certificate'](Path(report['apk']['path']).read_bytes()) == signer['CERT'],
                'APK provenance/signature differs')
    hosts = set()
    for item in report['host_reports']:
        cli.require(cli.record(item['path']) == item, 'CI evidence changed')
        host = s.read(item['path'])
        cli.require(host['development_result'] == 'PASS' and host['scope'] == 'all' and
                    host['source_before']['head'] == artifact.SHA and host['source_before']['clean'], 'exact CI required')
        hosts.add(json.dumps(host['host'], sort_keys=True))
    cli.require(len(hosts) == len(report['host_reports']) == 2, 'both CI hosts required')
    completed = s.read(prior.PRIOR / 'analysis/1790939796737635200/result.json')
    cli.require(completed['result'] == 'FULL_INSTALL_VERIFIED' and
                completed['summary']['input']['targetVersionCode'] == 30249, 'prior OTA unresolved')
    for item in (completed['inputs']['snapshot'], completed['inputs']['config'], completed['after']):
        cli.require(cli.record(item['path']) == item, 'prior evidence changed')
    for name in ('coordinator', 'network', 's04'):
        owner = s.read(prior.PRIOR / 'runtime' / name / 'closed.json')
        cli.require(owner['worker_exit'] == 0 and not owner['forced_termination'], 'prior owner unresolved')
    return report, completed


def worker(s):
    apk, completed = inputs(s)
    remote = 'files/p34-observations/' + completed['summary']['captureId']
    b, d, p, lock = runpy.run_path(str(ROOT / 'Tools/ota/p34_signing_migration.py'))['runtime']()
    value = dict(result='BATCH_INSTALL_INCOMPLETE', no_ota=True, no_uninstall=True, no_data_clear=True)
    try:
        with lock.device_lock(), d['usb'](b, p, OUT):
            p.phone_identity()
            cli.require(d['installed'](b, p, prior.OLD_SHA) is not None, 'installed APK differs; do not reinstall blindly')
            power = p.command(['shell', 'dumpsys', 'power'], timeout=30)
            s.raw(OUT / 'power.txt', power.encode())
            if 'mWakefulness=Awake' not in power:
                value['result'] = 'NEEDS_PHONE_WAKE_NO_INSTALL_ATTEMPTED'
            else:
                pid = p.command(['shell', 'pidof', prior.PKG], check=False).strip()
                cli.require(pid in ('', str(completed['summary']['pid'])), 'App invocation changed; inspect before stopping')
                config = p.file_bytes(prior.PKG, 'files/p34-experiment.json', 8192)
                cli.require(config == Path(completed['inputs']['config']['path']).read_bytes(), 'config changed')
                health = json.loads(p.file_bytes(prior.PKG, remote + '/health.json', 8192))
                cli.require(health['healthy'] and health['lost'] == 0 and health['error'] is None and
                            health['upgradeStarts'] == health['upgradeEnds'] == 1 and health['outcome'] == 'completed',
                            'capture no longer completed')
                s.write(OUT / 'stop-intent.json', dict(pid=pid, reason='verified completed App, same-signer batch update'))
                p.command(['shell', 'am', 'force-stop', prior.PKG])
                cli.require(not p.command(['shell', 'pidof', prior.PKG], check=False).strip(), 'App did not stop')
                names = p.command(['exec-out', 'run-as', prior.PKG, 'ls', '-1', remote]).splitlines()
                cli.require(set(names) in ({'events.jsonl', 'health.json', 'snapshot-1.jsonl'},
                            {'events.jsonl', 'health.json', 'health.json.tmp', 'snapshot-1.jsonl'}), 'unknown capture files')
                saved = {name: p.file_bytes(prior.PKG, remote + '/' + name, 16785408) for name in names}
                cli.require(saved['snapshot-1.jsonl'] == Path(completed['inputs']['snapshot']['path']).read_bytes(),
                            'original snapshot changed')
                for name, data in saved.items():
                    s.raw(OUT / 'capture' / name, data)
                s.raw(OUT / 'runtime-config.json', config)
                permissions = d['permission_state'](p.command(['shell', 'dumpsys', 'package', prior.PKG]), 0)
                s.write(OUT / 'install-intent.json', dict(time=cli.now(), apk=apk['apk'], replace=True))
                reply = p.command(['install', '-r', '--no-streaming', apk['apk']['path']], timeout=180)
                cli.require(reply.strip().splitlines()[-1:] == ['Success'], 'install uncertain; inspect before another attempt')
                value['installed'] = d['installed'](b, p, apk['apk']['sha256'])
                cli.require(value['installed'] is not None, 'installed package hash differs')
                cli.require(all(p.file_bytes(prior.PKG, remote + '/' + name, len(data) + 1) == data
                                for name, data in saved.items()), 'prior capture changed during install')
                cli.require(p.file_bytes(prior.PKG, 'files/p34-experiment.json', 8192) == config and
                            d['permission_state'](p.command(['shell', 'dumpsys', 'package', prior.PKG]), 0) == permissions,
                            'config or permissions changed')
                value.update(result='FIXED_SIGNER_BATCH_UPDATE_VERIFIED', snapshot_preserved=True,
                             configuration_preserved=True, permissions_preserved=True, app_launched=False)
        value['usb_closed'] = True
    except Exception as error:
        value.update(error=type(error).__name__, detail=str(error))
    s.write(OUT / 'result.json', dict(time=cli.now(), **value))
    print(json.dumps(value))


if __name__ == '__main__':
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                'isolated explicit root required')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('check', 'launch', 'worker'))
    args = parser.parse_args()
    s = cli.Store(ROOT)
    if args.mode == 'check':
        report, _ = inputs(s)
        print('INSTALL_INPUTS_VERIFIED', report['apk']['sha256'])
    else:
        owner = cli.load_module('batch_install_owner', ROOT / '.cache/p3-4-screening-20260922/supervisor.py')
        if args.mode == 'launch':
            cli.require(not OUT.exists(), 'preserve installation attempt')
            for name in ('intent.json', 'result.json', 'power.txt', 'stop-intent.json', 'install-intent.json',
                         'runtime-config.json', 'capture', 'host', 'usb'):
                s.checked(OUT / name)
            inputs(s)
            s.write(OUT / 'intent.json', dict(source=cli.record(__file__), no_ota=True, no_uninstall=True))
            print(owner.owned.launch(AREA / 'runtime/install-001', Path(__file__), ['worker'], 600))
        else:
            cli.require(owner.owned.in_job(), 'finite detached owner required')
            worker(s)
