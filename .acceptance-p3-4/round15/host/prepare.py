"""Prepare the direct native-path successor with the standard lineage checks."""
import copy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shlex
import sys

R = Path('D:/github/my/E-Track/.cache/p34-final')
E = R / '.cache/p34-local-closeout-20261014'
F = E / 'successor15'
OLD = R / '.acceptance-p3-4/round14'
B = R / '.acceptance-p3-4/round15'
PC = R / 'docs/acceptance-contracts/P3-4-v14.contract.json'
C = R / 'docs/acceptance-contracts/P3-4-v15.contract.json'
assert Path.cwd() == R and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode
sys.path.insert(0, str(R / 'Tools/ota/p34-acceptance'))
import live_host as h

v = h.host.load('p34_native_path_validator', R / 'Tools/acceptance/validate_bundle.py')
sealed = h.read_json(E / 'v14-evidence-gap-sealed.json')
assert sealed['result'] == 'EVIDENCE_GAP'
old = h.read_json(h.pinned(sealed['contract']))
previous = h.read_json(h.pinned(sealed['matrix']))
assert h.read_json(h.pinned(sealed['final_validation']))['exit_code'] == 0
assert not C.exists() and not B.exists()
assert not v.validate_evidence_files(previous, OLD)
assert not v.validate_artifact_files(previous, OLD)
for path in (B, C, F / 'host', F / 'prepared.json'):
    h.checked(path)
h.fresh(B)
reference = next(x for x in previous['criteria'] if x['id'] == 'P34-CANDIDATE-REFERENCE')
assert reference['result'] == 'PASS' and reference['execution'] == 'EXECUTED'
ref_ids = {'CMD-REFERENCE-V10', 'CMD-REFERENCE-V11', 'CMD-REFERENCE-MCU'}
copied = []
for name in sorted(previous['evidence_hashes']):
    target = name
    if name.startswith('commands/') and not any(name.startswith('commands/' + cid + '.') for cid in ref_ids):
        target = 'origins/v14/' + name
    elif name.startswith('host/') or name == 'adjudications/partial-execution.json':
        target = 'origins/v14/' + name
    elif name in ('P3-4-v14.contract.json', 'rerun-plan.json'):
        target = 'origins/v14/' + name
    data = (OLD / name).read_bytes()
    assert hashlib.sha256(data).hexdigest().upper() == previous['evidence_hashes'][name]
    h.raw(B / target, data)
    copied.append(dict(original=h.record(OLD / name), copy=h.record(B / target)))
h.raw(B / 'origins/v14/evidence-matrix.json', (OLD / 'evidence-matrix.json').read_bytes())
h.raw(B / 'origins/v14/contract.json', PC.read_bytes())
h.raw(B / 'origins/v14/sealed.json', (E / 'v14-evidence-gap-sealed.json').read_bytes())

c = copy.deepcopy(old)
c.update(contract_id='P3-4-v15', version=15, parent_contract_sha256=h.record(PC)['sha256'].upper(),
    approved_at=datetime.now(timezone.utc).isoformat(),
    approved_by='Current user approved the metadata correction and subsequent necessary local closeout authorizations on 2026-10-14; same reviewer continues without repeated approval, devices and publication excluded.')
changed = []
for command in c['commands']:
    argv = shlex.split(command['command'])
    if Path(argv[0]).name.lower() != 'fc.exe':
        continue
    assert argv[1] == '/B' and len(argv) == 4
    native = [str(h.checked(R / arg)) for arg in argv[2:]]
    assert all(Path(arg).is_file() and '/' not in arg for arg in native)
    changed.append(dict(id=command['id'], before=command['command'],
        inputs=[h.record(Path(arg)) for arg in native]))
    command['command'] = shlex.join(argv[:2] + native)
    changed[-1]['after'] = command['command']
assert len(changed) == 7
c['stage']['id'] = 'candidate-stage-native-path-closeout'
c['stage']['resume'].update(previous_round_id=previous['round_id'], previous_result='EVIDENCE_GAP',
    previous_matrix_sha256=h.record(OLD / 'evidence-matrix.json')['sha256'].upper(),
    first_active_command='CMD-Q-TRANSFER',
    scope_reason='Correct seven FC input filename spellings only. Reuse the complete v14 reference PASS; remaining standard-plan commands evaluate the same preserved originals offline.',
    failure_preserved='v14 partial offline evidence gap and native-path error; v11 HARNESS_FAIL, v12 EVIDENCE_GAP and v13 scoped PASS all remain unchanged.')
c['operating_rules']['matrix_lifecycle'] = 'Only round15 is writable; all predecessors and their original outcomes remain unchanged.'
argv = shlex.split(old['operating_rules']['lineage_preflight_command'])
for flag, value in (('--contract', C), ('--matrix', B / 'evidence-matrix.json'),
                    ('--previous-contract', PC), ('--previous-matrix', OLD / 'evidence-matrix.json')):
    argv[argv.index(flag) + 1] = str(value)
argv += ['--reuse-source', str(R / 'docs/acceptance-contracts/P3-4-v13.contract.json'),
         str(R / '.acceptance-p3-4/round13/evidence-matrix.json')]
c['operating_rules']['lineage_preflight_command'] = shlex.join(argv)
c['operating_rules']['plan_generation_command'] = shlex.join(argv + ['--write-rerun-plan', 'rerun-plan.json'])
h.save(B / 'inputs/native-fc-successor.json', dict(scope='Only native absolute filename spelling for the seven existing FC comparisons.',
    authority=h.record(E / 'metadata-correction-authorization.json'), changes=changed,
    parent_contract=h.record(PC), parent_matrix=h.record(OLD / 'evidence-matrix.json'),
    source_or_gate_changed=False, physical_operations=0, qualification_total=3,
    copied_originals=copied, no_old_file_rewritten=True))
errors = (v.validate_contract(c) + v.validate_freeze_objects(c, R) +
          v.validate_execution_worktree(c, R) + v.validate_external_inputs(c, B))
assert not errors, errors
cbytes = (json.dumps(c, indent=2, allow_nan=False) + '\n').encode('utf-8')
csha = hashlib.sha256(cbytes).hexdigest().upper()
round_id = 'P3-4-20261014-candidate-native-path-closeout'
plan = v.compute_rerun_plan(c, old, previous, current_contract_sha256=csha,
    previous_contract_sha256=h.record(PC)['sha256'].upper(),
    previous_matrix_sha256=h.record(OLD / 'evidence-matrix.json')['sha256'].upper(),
    current_round_id=round_id, repo_root=R)
assert plan['changed_input_groups'] == []
assert plan['reusable_criteria'] == ['P34-CANDIDATE-REFERENCE']
assert len(plan['required_commands']) == 16
pbytes = (json.dumps(plan, indent=2, allow_nan=False) + '\n').encode('utf-8')
reused = copy.deepcopy(reference)
reused.update(execution='REUSED', reused_from_round=previous['round_id'],
    origin_contract_sha256=h.record(PC)['sha256'].upper(),
    origin_matrix_sha256=h.record(OLD / 'evidence-matrix.json')['sha256'].upper())
m = dict(schema=previous['schema'], contract_id=c['contract_id'], contract_sha256=csha,
    round_id=round_id, overall_result='NOT_RUN',
    previous_matrix_sha256=h.record(OLD / 'evidence-matrix.json')['sha256'].upper(),
    rerun_plan_path='rerun-plan.json', rerun_plan_sha256=hashlib.sha256(pbytes).hexdigest().upper(),
    criteria=[reused if x['id'] == reused['id'] else dict(id=x['id'], result='NOT_OBSERVED',
        failure_owner=None, execution='EXECUTED', reused_from_round=None,
        origin_contract_sha256=None, origin_matrix_sha256=None, observed=None, evidence=[],
        notes='Await the required offline commands; no new physical execution.') for x in c['criteria']],
    commands=[copy.deepcopy(x) for x in previous['commands'] if x['id'] in ref_ids],
    artifacts=[copy.deepcopy(x) for x in previous['artifacts'] if x['id'].removeprefix('ART-') in ref_ids],
    evidence_hashes={name: previous['evidence_hashes'][name] for name in reference['evidence']})
assert not v.validate_matrix(m, c, csha)
assert not v.validate_evidence_files(m, B)
assert not v.validate_artifact_files(m, B)
h.raw(B / 'rerun-plan.json', pbytes)
assert not v.validate_rerun_plan_file(m, B, plan, m['previous_matrix_sha256'])
h.raw(C, cbytes)
h.raw(B / 'P3-4-v15.contract.json', cbytes)
h.save(B / 'evidence-matrix.json', m)
out = h.fresh(F / 'host')
env = h.environment(out)
git = h.pinned(h.read_json(B / 'origins/v13/inputs/live-inputs.json')['tools']['git'])
env['PATH'] = str(git.parent) + os.pathsep + env.get('PATH', '')
h.command(out, 'preflight', argv, env, seconds=300)
h.save(F / 'prepared.json', dict(contract=h.record(C), matrix=h.record(B / 'evidence-matrix.json'),
    plan=h.record(B / 'rerun-plan.json'), preflight=h.record(out / 'preflight.closed.json'),
    required_commands=plan['required_commands'], reused_criteria=plan['reusable_criteria'],
    changed_commands=changed, physical_operations=0, prior_failure_preserved=True))
print('V15_PREFLIGHT_PASS; reference reused from actual v14 PASS; required offline commands=16; device actions=0', flush=True)
