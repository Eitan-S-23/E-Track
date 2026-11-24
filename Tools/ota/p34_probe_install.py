"""Reuse verified in-place installation; preserve the completed30254 snapshot."""
import json
from pathlib import Path
import runpy
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'Tools/ota'))
import p34_probe_artifacts as artifact
import p34_probe_profile as profile
import p34_batch_install as original

cli, batch = profile.cli, profile.batch
AREA = profile.assets_api.AREA
OUT = AREA / 'install-001'
PKG = 'com.wen.gaia.gaia.p34probe'
OLD_SHA = '97cacd39f163357e6844098d1840adefde4c1aee24cf52edd8e6fd003fb8320a'


def inputs(s):
    report = s.read(AREA / 'apk-g1/apk.json')
    signer = runpy.run_path(str(ROOT / 'Tools/ota/p34_signing_artifacts.py'))
    cli.require(report['sha'] == artifact.SHA and report['metadata']['application_id'] == PKG and
                report['certificate_sha256'] == signer['CERT'] and cli.record(report['apk']['path']) == report['apk'] and
                signer['apk_certificate'](Path(report['apk']['path']).read_bytes()) == signer['CERT'], 'APK identity differs')
    hosts = set()
    for item in report['host_reports']:
        cli.require(cli.record(item['path']) == item, 'CI report changed')
        value = s.read(item['path'])
        cli.require(value['development_result'] == 'PASS' and value['scope'] == 'all' and
                    value['source_before']['head'] == artifact.SHA and value['source_before']['clean'], 'exact green CI required')
        hosts.add(json.dumps(value['host'], sort_keys=True))
    cli.require(len(hosts) == len(report['host_reports']) == 2, 'two CI hosts required')
    completed = profile.assets_api.archive.proof(s, profile.assets_api.PRIOR)
    cli.require(completed['summary']['input']['targetVersionCode'] == 30254, 'wrong retained target')
    profile.assets(s, 'control')
    tests = s.read(AREA / 'profile-tests-001/result.json')
    cli.require(tests['result'] == 'PASS' and tests['source'] == cli.record(profile.__file__), 'host profile not tested')
    return report, completed


def apk(s):
    report, _ = inputs(s)
    value = s.read(OUT / 'result.json')
    cli.require(value['result'] == 'FIXED_SIGNER_BATCH_UPDATE_VERIFIED' and value['usb_closed'] and
                value['installed']['sha256'] == report['apk']['sha256'] and value['snapshot_preserved'] and
                value['configuration_preserved'] and value['permissions_preserved'], 'in-place update unresolved')
    owner = s.read(AREA / 'runtime/install-001/closed.json')
    cli.require(owner['worker_exit'] == 0 and not owner['forced_termination'], 'install owner unresolved')
    return report


if __name__ == '__main__':
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                'isolated explicit root required')
    cli.require(sys.argv[1:] in (['check'], ['launch'], ['worker']), 'exact mode required')
    s = cli.Store(ROOT)
    report, _ = inputs(s)
    if sys.argv[1] == 'check':
        print('PROBE_INSTALL_INPUTS_VERIFIED', report['apk']['sha256'])
    else:
        owner = cli.load_module('probe_install_owner', ROOT / '.cache/p3-4-screening-20260922/supervisor.py')
        if sys.argv[1] == 'launch':
            cli.require(not OUT.exists(), 'preserve installation attempt')
            for name in ('intent.json', 'result.json', 'power.txt', 'stop-intent.json', 'install-intent.json',
                         'runtime-config.json', 'capture', 'host', 'usb'):
                s.checked(OUT / name)
            s.write(OUT / 'intent.json', dict(source=cli.record(__file__), implementation=cli.record(original.__file__),
                no_ota=True, no_uninstall=True, no_data_clear=True, purpose='same-link INFO candidate, not collector recovery'))
            print(owner.owned.launch(s.checked(AREA / 'runtime/install-001'), Path(__file__), ['worker'], 600))
        else:
            cli.require(owner.owned.in_job(), 'finite install owner required')
            batch.clone(original.worker, inputs=inputs, OUT=OUT,
                prior=SimpleNamespace(PKG=PKG, OLD_SHA=OLD_SHA))(s)
