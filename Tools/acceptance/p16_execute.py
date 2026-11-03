"""Bounded caller of the existing P1-6 matrix and native restoration primitives."""
import argparse
import hashlib
from pathlib import Path
import struct
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'Tools/ota/p34-acceptance'))
import live_host as h
import live_mcu as m
sys.path.insert(0, str(ROOT / 'Tools/acceptance'))
import p16_backup

ROWS = ('01', '02', '04', '06', '08', '09', '10', '11', '12', '13', '14', '18', '19', '20')


def admitted_plan(contract, plan_path):
    h.require(contract.get('task_id') == 'P1-6' and contract.get('status') == 'FROZEN', 'wrong/unfrozen task')
    bindings = [item for item in contract['external_inputs'] if item['id'] == 'recovery-plan']
    h.require(len(bindings) == 1 and hashlib.sha256(plan_path.read_bytes()).hexdigest().upper() ==
              bindings[0]['evidence_sha256'].upper(), 'recovery plan differs from frozen external input')
    return h.read_json(plan_path)


def passive_read(mcu, label, expected, *, restored=False):
    commands = [('internal', 0x08000000, 0x100000), ('candidate', 0x90000000, 0x100000),
                ('backup', 0x90100000, 0x100000), ('recovery', 0x90200000, 0x100000),
                ('fpb', 0xe0002000, 40)]
    raw, _, folder = mcu.execute(commands, {name:size for name,_,size in commands}, label, seconds=300)
    h.require(raw['internal'] == h.pinned(expected['internal']).read_bytes(), 'full internal Flash differs')
    h.require(all(not v & 1 for v in struct.unpack('<10I', raw['fpb'])[2:8]), 'active hardware comparator')
    slots = {}
    for name, item in expected['slots'].items():
        original = h.pinned(item['raw']).read_bytes()
        if restored:
            h.require(raw[name][:32] == original[:32] and
                      raw[name][4096:4096 + item['payloadBytes']] == original[4096:4096 + item['payloadBytes']],
                      'restored slot header/payload differs: ' + name)
        else:
            h.require(raw[name] == original, 'slot changed since backup: ' + name)
        slots[name] = dict(raw=h.record(folder / (name + '.bin')), originalPayloadRestored=True,
                           fullSlotIdentical=raw[name] == original)
    return dict(internal=h.record(folder / 'internal.bin'), slots=slots, fpb=h.record(folder / 'fpb.bin'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--contract', type=Path, required=True)
    parser.add_argument('--matrix', type=Path, required=True)
    args = parser.parse_args()
    h.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
              'explicit isolated worktree execution required')
    plan = admitted_plan(h.read_json(args.contract), args.plan)
    h.require(plan['schema'] == 'p16-group16-recovery-v1' and plan['probeSerial'] == 123456 and
              plan['bootAffectedBytes'] == 0x5000 and plan['appAffectedBytes'] == 0xc3000, 'unexpected recovery scope')
    for name in ('originalBoot', 'originalApp', 'testBoot', 'v0', 'v1'):
        h.pinned(plan[name])
    for item in plan['slots'].values():
        h.pinned(item)
    for root in (ROOT, Path('D:/github/my/E-Track')):
        for name in ('p34-live-device.lock', 'p35-pipeline.lock', 'p35-reconcile-device.lock'):
            h.require(not (root / '.cache' / name).exists(), 'outstanding device owner')
    out = h.checked(args.out)
    for name in ('precheck', 'seed', 'matrix', 'restore', 'before', 'after', 'actions.json', 'failure.json', 'result.json'):
        h.checked(out / name)
    h.fresh(out)
    env = h.environment(out)
    h.command(out, 'precheck', [sys.executable, '-I', '-S', '-B', '-X', 'utf8',
        'Tools/acceptance/validate_bundle.py', '--contract', args.contract, '--matrix', args.matrix,
        '--repo-root', ROOT], env, seconds=300)
    actions = []

    def action(name, operation):
        item = dict(name=name, status='started', monotonicNs=time.monotonic_ns())
        actions.append(item)
        # New immutable receipt per transition, not an overwritten prior result.
        h.save(out / (name + '-started.json'), item)
        print('P16_ACTION_START=' + name, flush=True)
        value = operation()
        item = dict(name=name, status='completed', monotonicNs=time.monotonic_ns())
        h.save(out / (name + '-completed.json'), item)
        print('P16_ACTION_COMPLETE=' + name, flush=True)
        return value

    def setup(mode):
        return h.command(out, mode.lower(), ['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass',
            '-File', 'Tools/jlink/p1-6-setup.ps1', '-Action', mode, '-Plan', args.plan.resolve(),
            '-RunDirectory', out / mode.lower()], env, seconds=2400)

    old = h.command
    try:
        with h.device_owner(out):
            h.command = p16_backup.passive
            mcu = m.MCU(plan['retained'], h.fresh(out / 'before'))
            before = action('current-identity', lambda: mcu.inspect('target', 'admission'))
            h.require(before['registers']['freeze'] == 0 and before['storage'] == plan['backups']['after']['storage'],
                      'retained state changed since backup')
            action('current-backup-equality', lambda: passive_read(mcu, 'full-state', plan['backups']))
            h.command = old
            action('seed', lambda: setup('Seed'))
            stage = h.read_json(out / 'seed/staged.json')
            h.require((stage['state'], stage['boot_try'], stage['cur_vcode'], stage['cand_vcode'],
                       stage['backup_vcode'], stage['app_vcode'], stage['resume_block']) ==
                      (1, 3, 30314, 30315, 30314, 30314, 0), 'seed did not establish S0')
            assets = ROOT / plan['assets']
            action('matrix', lambda: h.command(out, 'matrix', ['powershell.exe', '-NoProfile',
                '-ExecutionPolicy', 'Bypass', '-File', 'Tools/jlink/test-p1-6-matrix.ps1',
                '-BuildDirectory', assets / 'build', '-AssetDirectory', assets,
                '-RunDirectory', out / 'matrix', '-ProbeSerial', str(plan['probeSerial']),
                '-ExecuteBoard', '-AssumeS0'], env, seconds=24000))
            action('restore', lambda: setup('Restore'))
            h.command = p16_backup.passive
            final = m.MCU(plan['retained'], h.fresh(out / 'after'))
            after = action('restored-identity', lambda: final.inspect('target', 'retained'))
            h.require(after['registers']['freeze'] == 0 and before['storage'] == after['storage'],
                      'restoration storage/freeze mismatch')
            readback = action('restored-full-readback', lambda: passive_read(final, 'full-state', plan['backups'], restored=True))
            summaries = [h.read_json(out / 'matrix' / ('row-' + row) / 'row-summary.json') for row in ROWS]
            h.require(all(value['row'] == row and value['terminal'] == ('PHYSICAL_RECOVERY' if row == '20' else 'BOOTABLE')
                          for row, value in zip(ROWS, summaries)), 'missing row terminal')
            h.save(out / 'result.json', dict(outcome='AUTO_MATRIX_EXECUTED_RESTORED', auto=list(ROWS),
                physicalNotRun=['03','05','07','15','16','17'], before=before, after=after, readback=readback,
                acceptance='PENDING_INDEPENDENT_ORIGINAL_EVALUATION', restorePolicy=plan['restoration']))
            print('P16_AUTO_EXECUTED=14 RETAINED=30313 PHYSICAL_NOT_RUN=6', flush=True)
    except BaseException as error:
        h.save(out / 'failure.json', dict(error=str(error), actions=actions,
            disposition='STOP_AND_RECONCILE_CURRENT_STATE_NO_BLIND_RETRY',
            lockRetained=(ROOT / '.cache/p34-live-device.lock').exists()))
        raise
    finally:
        h.command = old


if __name__ == '__main__':
    main()
