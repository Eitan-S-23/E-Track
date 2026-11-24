"""Resume the exact system-rejected APK update after the user's ready message."""
import json
from pathlib import Path
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'Tools/ota'))
import p34_probe_install as previous

cli, batch, AREA = previous.cli, previous.batch, previous.AREA
OUT = AREA / 'install-002'


def reconciled(s):
    before = s.read(previous.OUT / 'result.json')
    cli.require(before['result'] == 'BATCH_INSTALL_INCOMPLETE' and before['no_ota'] and
                before['no_uninstall'] and before['no_data_clear'], 'different prior installation outcome')
    owner = s.read(AREA / 'runtime/install-001/closed.json')
    usb = s.read(previous.OUT / 'usb/closed.json')
    cli.require(owner['worker_exit'] == 0 and not owner['forced_termination'] and usb['port_closed'] and
                usb['stop_exit'] == usb['server_exit'] == usb['launcher_exit'] == 0 and
                usb['key_before'] == usb['key_after'], 'prior resources unresolved')
    rows = [json.loads(x) for x in (previous.OUT / 'usb/commands.jsonl').read_text(encoding='utf-8').splitlines()]
    attempts = [x for x in rows if x['args'] and x['args'][0] == 'install']
    target = s.read(previous.OUT / 'install-intent.json')['apk']
    cli.require(len(attempts) == 1 and attempts[0]['args'] == ['install', '-r', '--no-streaming', target['path']] and
                attempts[0]['exit'] == 1 and 'Failure [INSTALL_FAILED_ABORTED: User rejected permissions]' in
                attempts[0]['stdout'] and 'Success' not in attempts[0]['stdout'], 'different or uncertain install failure')
    return target


def inputs(s):
    target = reconciled(s)
    report, completed = previous.inputs(s)
    cli.require(report['apk'] == target, 'do not replace rejected APK with another build')
    return report, completed


def apk(s):
    report, _ = inputs(s)
    result = s.read(OUT / 'result.json')
    owner = s.read(AREA / 'runtime/install-002/closed.json')
    cli.require(owner['worker_exit'] == 0 and not owner['forced_termination'] and
                result['result'] == 'FIXED_SIGNER_BATCH_UPDATE_VERIFIED' and result['usb_closed'] and
                result['installed']['sha256'] == report['apk']['sha256'] and result['snapshot_preserved'] and
                result['configuration_preserved'] and result['permissions_preserved'], 'resumed update unresolved')
    return report


if __name__ == '__main__':
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                'isolated explicit root required')
    cli.require(sys.argv[1:] in (['check'], ['launch'], ['worker']), 'exact mode required')
    s = cli.Store(ROOT)
    report, _ = inputs(s)
    if sys.argv[1] == 'check':
        print('REJECTED_INSTALL_RECONCILED', report['apk']['sha256'])
    else:
        owner = cli.load_module('probe_install_resume_owner', ROOT / '.cache/p3-4-screening-20260922/supervisor.py')
        if sys.argv[1] == 'launch':
            cli.require(not OUT.exists(), 'preserve resumed installation attempt')
            for name in ('intent.json', 'result.json', 'power.txt', 'stop-intent.json', 'install-intent.json',
                         'runtime-config.json', 'capture', 'host', 'usb'):
                s.checked(OUT / name)
            s.write(OUT / 'intent.json', dict(source=cli.record(__file__), prior=cli.record(previous.OUT / 'result.json'),
                implementation=cli.record(previous.original.__file__), no_ota=True, no_uninstall=True,
                reason='User confirmed phone ready after system rejected USB installation; verify old APK before mutation'))
            print(owner.owned.launch(s.checked(AREA / 'runtime/install-002'), Path(__file__), ['worker'], 600))
        else:
            cli.require(owner.owned.in_job(), 'finite install owner required')
            # The original worker verifies the current APK hash before any stop/install.
            # If the target is already present it fails closed, never reinstalling it.
            batch.clone(previous.original.worker, inputs=inputs, OUT=OUT,
                prior=SimpleNamespace(PKG=previous.PKG, OLD_SHA=previous.OLD_SHA))(s)
