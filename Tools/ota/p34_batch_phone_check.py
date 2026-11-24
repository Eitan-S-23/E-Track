"""Bounded read-only phone readiness; no App launch, install, stop or OTA."""
import json
from pathlib import Path
import runpy
import sys

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / '.cache/p34-batch-fix/preinstall-001'
PRIOR = ROOT / '.cache/p34-radio-fix/recorder-fix/trials-v3/combined'
PKG = 'com.wen.gaia.gaia.p34probe'
OLD_SHA = 'd1bc81c8b8151ef34d095df87bfbe7afcc40444b6f391446a9e0239f592c4991'


def main():
    sys.path.insert(0, str(ROOT / 'Tools/ota'))
    import p34_session as cli
    s = cli.Store(ROOT)
    cli.require(not OUT.exists(), 'preserve original readiness check')
    for name in ('result.json', 'power.txt', 'health.json', 'runtime-config.json', 'snapshot.jsonl', 'usb', 'host'):
        s.checked(OUT / name)
    for name in ('coordinator', 'network', 's04'):
        owner = s.read(PRIOR / 'runtime' / name / 'closed.json')
        cli.require(owner['worker_exit'] == 0 and not owner['forced_termination'], 'prior owner unresolved')
    report = s.read(PRIOR / 'analysis/1790939796737635200/result.json')
    cli.require(report['result'] == 'FULL_INSTALL_VERIFIED', 'prior upgrade unresolved')
    capture = report['summary']['captureId']
    remote = 'files/p34-observations/' + capture
    b, d, p, lock = runpy.run_path(str(ROOT / 'Tools/ota/p34_signing_migration.py'))['runtime']()
    result = dict(result='PHONE_CHECK_INCOMPLETE', no_phone_mutation=True, no_ota=True)
    try:
        with lock.device_lock(), d['usb'](b, p, OUT):
            p.phone_identity()
            result['installed'] = d['installed'](b, p, OLD_SHA)
            cli.require(result['installed'] is not None, 'installed APK changed')
            power = p.command(['shell', 'dumpsys', 'power'], timeout=30)
            s.raw(OUT / 'power.txt', power.encode())
            result['awake'] = 'mWakefulness=Awake' in power
            result['pid'] = p.command(['shell', 'pidof', PKG], check=False).strip()
            result['expected_pid'] = report['summary']['pid']
            config = p.file_bytes(PKG, 'files/p34-experiment.json', 8192)
            cli.require(config == Path(report['inputs']['config']['path']).read_bytes(), 'configuration changed')
            s.raw(OUT / 'runtime-config.json', config)
            raw = p.file_bytes(PKG, remote + '/health.json', 8192)
            health = json.loads(raw)
            cli.require(health['captureId'] == capture and health['healthy'] is True and health['lost'] == 0 and
                        health['error'] is None and health['upgradeStarts'] == health['upgradeEnds'] == 1 and
                        health['outcome'] == 'completed', 'prior recorder changed')
            s.raw(OUT / 'health.json', raw)
            snapshot = p.file_bytes(PKG, remote + '/snapshot-1.jsonl', 16785408)
            cli.require(snapshot == Path(report['inputs']['snapshot']['path']).read_bytes(), 'original snapshot changed')
            s.raw(OUT / 'snapshot.jsonl', snapshot)
            result['snapshot_preserved'] = True
            result['result'] = ('NEEDS_PHONE_WAKE' if not result['awake'] else
                'PHONE_READY' if result['pid'] in ('', str(result['expected_pid'])) else 'APP_INVOCATION_CHANGED')
        result['usb_closed'] = True
    except Exception as error:
        result.update(error=type(error).__name__, detail=str(error))
    s.write(OUT / 'result.json', dict(time=cli.now(), **result))
    print(json.dumps(result))


if __name__ == '__main__':
    if not (Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode):
        raise RuntimeError('explicit root and isolated Python required')
    main()
