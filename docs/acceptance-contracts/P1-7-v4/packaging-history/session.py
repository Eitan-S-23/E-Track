"""Bounded local successor packaging, using existing Git/validator primitives."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
AREA = Path(__file__).resolve().parent
assert Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode
sys.path.insert(0, str(ROOT/'.cache/p17-acceptance-20261103-01'))
import control as c
h = c.h
PACKAGE = ROOT/'docs/acceptance-contracts/P1-7-v4'
CONTRACT = ROOT/'docs/acceptance-contracts/P1-7-v4.contract.json'
PREVIOUS = ROOT/'docs/acceptance-contracts/P1-7-v3'
PREVIOUS_CONTRACT = ROOT/'docs/acceptance-contracts/P1-7-v3.contract.json'
SOURCE = ['Tools/acceptance/p17_supplement.py', 'tests/ota/test_p17_supplement.py']
NOTE = 'docs/ota-exec-notes/P1-7-acceptance-preparation-2026-11-03.md'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def validate(out, env, label, matrix, write_plan=False):
    argv = [sys.executable, '-I', '-S', '-B', '-X', 'utf8', ROOT/'Tools/acceptance/validate_bundle.py',
        '--contract', CONTRACT, '--matrix', PACKAGE/matrix, '--repo-root', ROOT,
        '--previous-contract', PACKAGE/'predecessor/contract.json',
        '--previous-matrix', PACKAGE/'predecessor/final-matrix.json']
    if write_plan:
        argv += ['--write-rerun-plan', PACKAGE/'rerun-plan.json']
    return h.command(out, label, argv, env, seconds=180)


def run(mode):
    out = h.fresh(AREA/mode)
    env = c.env_for(out)
    git = lambda label, *args: c.git(out, env, label, *args)
    if mode == 'baseline':
        h.save(out/'shared.json', dict(main=git('main', 'rev-parse', 'refs/heads/main').decode().strip(),
            mainIndex=sha(c.COMMON/'index'), head=git('head', 'rev-parse', 'HEAD').decode().strip()))
        assert not git('staged', 'diff', '--cached', '--name-only', '-z')
        assert git('branch', 'symbolic-ref', '--short', 'HEAD').decode().strip() == c.BRANCH
        for name, rel in (('board', 'PLAN-OTA-EXEC.md'), ('note', NOTE),
                          ('index', 'docs/acceptance-contracts/FREEZE-INDEX.md')):
            h.raw(out/(name+'.original'), (ROOT/rel).read_bytes())
        old = [h.record(PREVIOUS_CONTRACT)] + [h.record(p) for p in PREVIOUS.rglob('*') if p.is_file()]
        h.save(out/'originals.json', old)
        unrelated = [p for p in git('dirty', 'diff', '--name-only', '-z').decode().strip('\0').split('\0')
                     if p and p not in ('PLAN-OTA-EXEC.md', NOTE)]
        h.save(out/'unrelated.json', [h.record(ROOT/p) for p in unrelated])
    elif mode == 'prepare':
        assert not PACKAGE.exists() and not CONTRACT.exists()
        h.fresh(PACKAGE)
        for p in PREVIOUS.rglob('*'):
            if p.is_file():
                h.raw(PACKAGE/'predecessor'/p.relative_to(PREVIOUS), p.read_bytes())
        h.raw(PACKAGE/'predecessor/contract.json', PREVIOUS_CONTRACT.read_bytes())
        h.raw(PACKAGE/'.gitattributes', b'predecessor/** -text -diff\nsupplement/** -text -diff\nevaluation/*.stdout -text -diff\nevaluation/*.stderr -text -diff\n')
        files = {}
        for prefix, folder in (('key', ROOT/'.cache/p17-key-method-20261104-01'),
                               ('post', ROOT/'.cache/p17-key-post-20261104-01')):
            for p in folder.rglob('*'):
                if not p.is_file() or 'host' in p.relative_to(folder).parts:
                    continue
                name = prefix+'/'+p.relative_to(folder).as_posix()
                data = p.read_bytes()
                h.raw(PACKAGE/'supplement'/name, data)
                files[name] = dict(bytes=len(data), sha256=hashlib.sha256(data).hexdigest(),
                                   original=p.relative_to(ROOT).as_posix())
        report = dict(quote='\u6d4b\u8bd5\u4e86\uff0c\u4e00\u5207\u90fd\u6b63\u5e38',
            source='current-conversation-user', reportedDate='2026-11-03', instrumented=False,
            procedure=dict(usbDisconnected=True, jlinkDisconnected=True, batteryOnly=True,
                           powerButtonStartup=True, enteredApp=True),
            meaning='Firsthand user response to the preceding battery-only startup procedure; '
                    'not agent telemetry or a repeated experiment.',
            context='Existing P17-BATTERY-01 task-board annotation and original conversation retained.')
        h.save(PACKAGE/'supplement/battery.json', report)
        h.raw(PACKAGE/'supplement/battery-context.md', (AREA/'baseline/board.original').read_bytes())
        for name in ('battery.json', 'battery-context.md'):
            p = PACKAGE/'supplement'/name
            files[name] = dict(bytes=p.stat().st_size, sha256=sha(p).lower(), original='user-report/context')
        h.save(PACKAGE/'supplement/index.json', dict(schema='p17-supplement-originals-v1', files=files,
            operationDate='2026-11-04 Asia/Shanghai', formalDeviceReplay=False))
        h.save(out/'result.json', dict(files=len(files), outcome='ORIGINALS_COPIED_WITHOUT_REPLAY'))
    elif mode.startswith('regression'):
        h.command(out, 'tests', [sys.executable, '-I', '-S', '-B', '-X', 'utf8', AREA/'tests.py'],
                  env, seconds=1200)
        h.save(out/'sources.json', [h.record(ROOT/p) for p in SOURCE])
    elif mode.startswith('preview'):
        h.command(out, 'review', [sys.executable, '-I', '-S', '-B', '-X', 'utf8',
            ROOT/SOURCE[0], '--bundle', PACKAGE, '--out', out/'result.json'], env, seconds=180)
    elif mode == 'freeze':
        source = h.read_json(AREA/'commit-source/result.json')['commit']
        assert git('head', 'rev-parse', 'HEAD').decode().strip() == source
        value = h.read_json(PREVIOUS_CONTRACT)
        value.update(contract_id='P1-7-v4', version=4, parent_contract_sha256=sha(PREVIOUS_CONTRACT),
            freeze_commit=source, freeze_tree=git('tree', 'rev-parse', 'HEAD^{tree}').decode().strip(),
            profile_config_blob=git('profile', 'rev-parse', 'HEAD:Tools/provenance/manifest_profiles.json').decode().strip(),
            approved_at=datetime.now(timezone.utc).isoformat(),
            approved_by='Original independent acceptance reviewer under existing user P1-7/local Git authority; no new device execution')
        value['external_inputs'] = [dict(id='original-'+str(i), category='fixture',
            description='Exact historical input: '+p.relative_to(PACKAGE).as_posix(),
            fingerprint='sha256:'+sha(p), evidence_path=p.relative_to(PACKAGE).as_posix(), evidence_sha256=sha(p))
            for i, p in enumerate(sorted(PACKAGE.rglob('*'))) if p.is_file() and p.name != '.gitattributes']
        command = value['commands'][0]
        command.update(description='Offline original evidence evaluation: preserved startup/tick evidence, '
            'actual isolated Boot key calls and firsthand battery-only startup report. No device operation.',
            command='python -I -S -B -X utf8 Tools/acceptance/p17_supplement.py --bundle docs/acceptance-contracts/P1-7-v4 --out docs/acceptance-contracts/P1-7-v4/evaluation/result.json')
        command['runner_paths'].append(SOURCE[0])
        for item in value['criteria']:
            item['external_inputs'] = [x['id'] for x in value['external_inputs']]
        for item in value['artifacts']:
            if item['id'] != 'ART-OBSERVATION':
                item['path'] = 'predecessor/'+item['path']
        value['scope'] = dict(authority='Existing bounded local P1-7 source/bundle/index commits; no remote writes.',
            offlineOriginalEvaluation=True, deviceOperations=0, physicalKeyCalls=2, physicalKeyResets=1,
            previousOutcome='EVIDENCE_GAP', batteryEvidence='Firsthand user report, no instrumented duration.',
            shortSample='10 ticks rejected; not a measured one-second stable press.',
            keyScope='Exact unchanged predicate, not forced end-to-end recovery receiver.',
            oldEvidenceUnchanged=True, noP16PowerCuts=True)
        h.save(CONTRACT, value)
        matrix = h.read_json(PREVIOUS/'initial-matrix.json')
        matrix.update(contract_id=value['contract_id'], contract_sha256=sha(CONTRACT),
                      round_id='p17-supplement-20261104-04')
        h.save(PACKAGE/'initial-matrix.json', matrix)
        validate(out, env, 'rerun-plan', 'initial-matrix.json', True)
        validate(out, env, 'precheck', 'initial-matrix.json')
        h.save(out/'result.json', dict(outcome='FROZEN_NOT_RUN_PRECHECK_PASS'))
    elif mode == 'evaluate':
        validate(out, env, 'precheck', 'initial-matrix.json')
        h.command(PACKAGE/'evaluation', 'review', [sys.executable, '-I', '-S', '-B', '-X', 'utf8',
            ROOT/SOURCE[0], '--bundle', PACKAGE, '--out', PACKAGE/'evaluation/result.json'], env, seconds=180)
        result = h.read_json(PACKAGE/'evaluation/result.json')
        assert result['overallResult'] == 'PASS'
        matrix = h.read_json(PACKAGE/'initial-matrix.json')
        matrix.update(overall_result='PASS', previous_matrix_sha256=sha(PACKAGE/'predecessor/final-matrix.json'),
                      rerun_plan_path='rerun-plan.json', rerun_plan_sha256=sha(PACKAGE/'rerun-plan.json'))
        for item in matrix['criteria']:
            assert result['criteria'][item['id'].replace('-', '_')] == 'PASS'
            item.update(result='PASS', observed=dict(value=result['originalStartup']['observed']['startup']['upper_ms'], unit='ms')
                        if item['id'] == 'C-STARTUP' else True,
                        evidence=['evaluation/result.json', 'evaluation/review.stdout'],
                        notes='Executed independent offline evaluation of bound originals; no repeated hardware. '
                              'Preserve original sampling bounds, 10-tick short rejection and user-reported battery origin.')
        value = h.read_json(CONTRACT)
        matrix['commands'] = [dict(id='CMD-REVIEW', command=value['commands'][0]['command'], exit_code=0,
                                   output_evidence='evaluation/review.stdout')]
        matrix['artifacts'] = [dict(id=x['id'], path=x['path'], size=(PACKAGE/x['path']).stat().st_size,
                                    sha256=sha(PACKAGE/x['path'])) for x in value['artifacts']]
        matrix['evidence_hashes'] = {p.relative_to(PACKAGE).as_posix():sha(p) for p in PACKAGE.rglob('*') if p.is_file()}
        h.save(PACKAGE/'final-matrix.json', matrix)
        validate(out, env, 'final', 'final-matrix.json')
        h.save(out/'result.json', dict(outcome='FINAL_VALIDATION_PASS', criteria=5, deviceOperations=0))
    elif mode.startswith('commit-'):
        for rel in ('objects', 'refs/heads/'+c.BRANCH, 'logs/refs/heads/'+c.BRANCH, 'worktrees/source1'):
            h.host.io.checked_output(c.COMMON, c.COMMON/rel)
        assert git('branch', 'symbolic-ref', '--short', 'HEAD').decode().strip() == c.BRANCH
        assert not git('staged-before', 'diff', '--cached', '--name-only', '-z')
        before = git('head-before', 'rev-parse', 'HEAD').decode().strip()
        if mode == 'commit-source':
            names, message = SOURCE, 'test(p17): evaluate physical key and battery originals offline'
        elif mode == 'commit-bundle':
            validate(out, env, 'final-before-commit', 'final-matrix.json')
            names = [CONTRACT.relative_to(ROOT).as_posix()] + [p.relative_to(ROOT).as_posix() for p in PACKAGE.rglob('*') if p.is_file()]
            message = 'test(p17): accept supplemental originals in frozen v4 bundle'
        elif mode == 'commit-record':
            names = ['docs/acceptance-contracts/FREEZE-INDEX.md', NOTE]
            message = 'docs(p17): register accepted bundle and close local task'
        else:
            raise ValueError(mode)
        for name in names:
            h.checked(ROOT/name)
        h.save(out/'scope.json', dict(paths=names, parent=before, gitRoot=str(c.COMMON), remoteWrites=0))
        h.raw(out/'files.nul', b'\0'.join(n.encode() for n in names)+b'\0')
        git('add', 'add', '--pathspec-from-file='+str(out/'files.nul'), '--pathspec-file-nul')
        if mode == 'commit-record':
            # Stage only the P1 table row/P1-7 card, retaining unrelated dirty board content.
            base = git('board-head', 'show', 'HEAD:PLAN-OTA-EXEC.md').decode('utf8')
            working = (ROOT/'PLAN-OTA-EXEC.md').read_text(encoding='utf8')
            start, end = '#### P1-7 ', '## 5. P2 '
            staged = base[:base.index(start)] + working[working.index(start):working.index(end)] + base[base.index(end):]
            oldrow = next(s for s in staged.splitlines() if s.startswith('| P1 |'))
            newrow = next(s for s in working.splitlines() if s.startswith('| P1 |'))
            staged = staged.replace(oldrow, newrow)
            blob = h.command(out, 'board-blob', ['git', *c.OPTIONS, 'hash-object', '-w', '--stdin'], env,
                             stdin=staged.encode('utf8'), seconds=30).decode().strip()
            git('board-stage', 'update-index', '--cacheinfo', '100644,'+blob+',PLAN-OTA-EXEC.md')
            names += ['PLAN-OTA-EXEC.md']
        assert set(git('staged', 'diff', '--cached', '--name-only', '-z').decode().strip('\0').split('\0')) == set(names)
        git('whitespace', 'diff', '--cached', '--check')
        git('commit', 'commit', '-m', message)
        oid = git('head-after', 'rev-parse', 'HEAD').decode().strip()
        assert git('parent', 'rev-parse', 'HEAD^').decode().strip() == before
        baseline = h.read_json(AREA/'baseline/shared.json')
        assert git('main', 'rev-parse', 'refs/heads/main').decode().strip() == baseline['main']
        assert sha(c.COMMON/'index') == baseline['mainIndex']
        h.save(out/'result.json', dict(commit=oid, parent=before, paths=names, mainUnchanged=True))
    elif mode == 'audit':
        validate(out, env, 'final', 'final-matrix.json')
        for pin in h.read_json(AREA/'baseline/originals.json') + h.read_json(AREA/'baseline/unrelated.json'):
            h.pinned(pin)
        baseline = h.read_json(AREA/'baseline/shared.json')
        assert git('main', 'rev-parse', 'refs/heads/main').decode().strip() == baseline['main']
        assert sha(c.COMMON/'index') == baseline['mainIndex']
        assert not git('staged', 'diff', '--cached', '--name-only', '-z')
        entries = git('bundle-blobs', 'ls-tree', '-r', '-z', 'HEAD', '--', PACKAGE.relative_to(ROOT).as_posix(), CONTRACT.relative_to(ROOT).as_posix())
        count = 0
        for entry in entries.rstrip(b'\0').split(b'\0'):
            meta, name = entry.split(b'\t', 1)
            mode, kind, oid = meta.split()
            data = (ROOT/name.decode()).read_bytes()
            assert mode == b'100644' and kind == b'blob'
            assert hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest().encode() == oid
            count += 1
        files = []
        for folder in (AREA, PACKAGE):
            for p in folder.rglob('*'):
                h.checked(p)
                if p.is_file():
                    files.append(h.record(p))
                    if folder == AREA and p.name.endswith('.started.json'):
                        assert h.read_json(p.with_name(p.name.replace('.started.json', '.closed.json')))['cleanup_complete']
        h.save(out/'files.json', files)
        h.save(out/'result.json', dict(outcome='LOCAL_P17_ACCEPTANCE_AND_WRITE_AUDIT_PASS', exactBundleBlobs=count,
            originalBundlesUnchanged=True, sharedMainAndIndexUnchanged=True, unrelatedChangesPreserved=True,
            deviceOperations=0, remoteWrites=0, productEdits=0,
            externalWrites='Only authorized task objects/ref/reflog and worktrees/source1 metadata'))
    else:
        raise ValueError(mode)
    print(mode+' COMPLETE', flush=True)


if __name__ == '__main__':
    run(sys.argv[1])
