"""Offline cross-check of key originals and retained-state closure, no device IO."""
import ast
import csv
from datetime import datetime, timezone
import hashlib
import io
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
AREA = Path(__file__).resolve().parent
assert Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode
sys.path.insert(0, str(ROOT / 'Tools/ota/p34-acceptance'))
import live_host as h
import live_mcu


def key_gate(stdout, native):
    long = re.findall(r'P17_RESULT long result=(\d+) ticks=(\d+) gpio=([0-9a-f]+)', stdout)
    short = re.findall(r'P17_RESULT short result=(\d+) ticks=(\d+) gpio=([0-9a-f]+)', stdout)
    assert len(long) == len(short) == 1 and 'P17_ERROR' not in stdout
    assert long[0][0] == '1' and int(long[0][1]) >= 3000 and not int(long[0][2], 16) & 0x8000
    assert short[0][0] == '0' and 0 < int(short[0][1]) < 3000
    ticks = [int(v, 16) for v in re.findall(
        r'Read 4 bytes @ address 0x20001030 \(Data = 0x([0-9A-F]{8})\)', native)]
    assert len(ticks) == 4 and ticks[1]-ticks[0] == int(long[0][1]) and ticks[3]-ticks[2] == int(short[0][1])
    pcs = re.findall(r"Writing register 'pc' = 0x([0-9A-F]{8})", native)
    assert pcs == ['08001E6D', '080019AA', '08001E6D', '080019AA']
    assert 'Resetting target' not in native and 'Flash breakpoints disabled' in native
    calls = []
    pattern = r"^03-\d+-\d+-(\d+)-[0-9A-F]+: Writing register 'pc' = 0x(08001E6D|080019AA)"
    for match in re.finditer(pattern, native, re.M):
        calls.append(int(match[1]))
    assert len(calls) == 4 and calls[1]-calls[0] >= 3000
    return dict(longResult=True, longTicks=int(long[0][1]), shortResult=False,
                shortTicks=int(short[0][1]), nativeTicks=ticks,
                hostCallToContextRestoreMs=[calls[1]-calls[0], calls[3]-calls[2]],
                shortLimitation='Observed rejection after 10 ticks; not a measured one-second hold or debounced waveform.')


def main():
    out = h.checked(AREA / 'closeout-01')
    assert not out.exists()
    for name in ('host', 'result.json', 'files.json', 'processes.stdout', 'processes.stderr',
                 'processes.started.json', 'processes.closed.json'):
        h.checked(out / name)
    old = h.read_json(AREA / 'final-audit.json')['files']
    for pin in old:
        data = (ROOT / pin['path']).read_bytes()
        if pin['path'].endswith('P1-7-acceptance-preparation-2026-11-03.md'):
            data = data[:pin['bytes']]
        assert len(data) == pin['bytes'] and hashlib.sha256(data).hexdigest() == pin['sha256']
    run = AREA / 'gdb-key-03'
    plan = h.read_json(AREA / 'key-plan-03.json')
    for name in ('definitions', 'entry', 'gdb', 'server'):
        h.pinned(plan[name])
    stdout = (run / 'gdb.stdout').read_text(encoding='utf8')
    native = (run / 'server.log').read_text(encoding='utf8')
    observed = key_gate(stdout, native)
    negatives = [stdout.replace('long result=1', 'long result=0'),
                 stdout.replace('ticks=3000', 'ticks=2999'),
                 stdout.replace('short result=0', 'short result=1'),
                 stdout.replace('ticks=10 ', 'ticks=3000 ')]
    for changed in negatives:
        try:
            key_gate(changed, native)
        except AssertionError:
            pass
        else:
            raise AssertionError('negative oracle accepted')
    assert (run / 'stage-finished.log').read_text().strip() == 'P17_STAGE finished'
    notices = h.read_json(run / 'notifications.json')
    assert [x['stage'] for x in notices] == ['hold', 'release', 'short'] and all(x['delivered'] for x in notices)
    post = ROOT / '.cache/p17-key-post-20261104-01/inspect-01'
    raw = {p.stem:p.read_bytes() for p in (post / '0001-current-identity').glob('*.bin')}
    retained = plan['retained']
    assert raw['app'] == h.pinned(retained['images']['target']['image']).read_bytes()
    assert raw['boot'] == h.pinned(retained['boot']).read_bytes()
    health = live_mcu.health_gate(raw)
    assert health['registers']['freeze'] == 0
    stack = live_mcu.stack_observation(raw['guard'], raw['stack'])
    storage = live_mcu.storage_observation(raw, retained['package'])
    before = AREA / 'reconcile-01/0001-current-identity'
    for name in ('candidate_slot', 'backup_slot', 'recovery_slot', 'staging'):
        assert raw[name] == (before / (name + '.bin')).read_bytes()
    assert h.read_json(AREA / 'gdb-key-01/failed.json')['notifications'] == []
    failed = (AREA / 'gdb-key-02/gdb.stdout').read_text(encoding='utf8')
    assert 'Breakpoint 2, 0x080019aa' in failed and 'P17_RESULT' not in failed
    assert (AREA / 'gdb-key-02/server.stdout').read_text(encoding='utf8').count('Resetting target') == 1
    assert h.read_json(AREA / 'reconcile-02/result.json')['pc'] == 0x080019aa
    for root in (ROOT, Path('D:/github/my/E-Track')):
        for name in ('p34-live-device.lock', 'p35-reconcile-device.lock', 'p35-pipeline.lock'):
            assert not (root / '.cache' / name).exists()
    for folder in (AREA, post.parent):
        for p in folder.rglob('*.started.json'):
            if str(p.relative_to(ROOT)) in {x['path'] for x in old}:
                continue
            closed = h.read_json(p.with_name(p.name.replace('.started.json', '.closed.json')))
            assert closed['cleanup_complete']
            for stream in ('stdout', 'stderr'):
                h.pinned(closed[stream])
    for p in AREA.glob('*.py'):
        ast.parse(p.read_bytes())
    h.fresh(out)
    processes = h.command(out, 'processes', ['tasklist', '/FO', 'CSV', '/NH'], h.environment(out), seconds=15)
    names = {row[0].lower() for row in csv.reader(io.StringIO(processes.decode('utf8', 'replace'))) if row}
    assert not names & {'jlink.exe', 'jlinkgdbservercl.exe', 'jlinkgdbserver.exe', 'arm-none-eabi-gdb.exe', 'jlinkrttlogger.exe'}
    assert not any(h.listening(p) for p in plan['ports'])
    files = []
    old_names = {p['path'] for p in old}
    for folder in (AREA, post.parent):
        for p in sorted(folder.rglob('*')):
            h.checked(p)
            if p.is_file() and str(p.relative_to(ROOT)) not in old_names:
                files.append(h.record(p))
    h.save(out / 'files.json', files)
    result = dict(outcome='KEY_OBSERVATIONS_AND_RETAINED_STATE_VERIFIED', observed=observed,
        health=health, stack=stack, storage=storage, postRead=h.record(post/'result.json'),
        source=h.record(Path(__file__)), timeUtc=datetime.now(timezone.utc).isoformat(),
        negativeChecks=4, oldInputFilesVerified=len(old), newOutputFiles=len(files),
        resetCommands=1, keyCalls=2, firmwareProgramming=0, ota=0,
        deviceLockReleased=True, ownedProcessesClosed=True, debuggerPortsClosed=True,
        priorFailuresPreserved=True, sameCheckpointContinuation=True,
        noRepeatedSuccessfulKeyCall=True, controlledWritesWithinRoot=True,
        nativeException='C:/Users/SU/AppData/Roaming/SEGGER/', gitWrites=0,
        formalAcceptance='P1-7-v3 remains unchanged; supplemental formal adjudication not performed by this closeout.',
        scope='Isolated exact physical Boot predicate, not a forced end-to-end recovery receiver entry.')
    h.save(out / 'result.json', result)
    print(result['outcome'], observed, flush=True)


if __name__ == '__main__':
    main()
