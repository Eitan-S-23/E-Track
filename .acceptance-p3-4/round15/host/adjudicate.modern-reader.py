"""Evaluate original candidate evidence using committed readers and pure MCU gates."""
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import struct
import sys
import zipfile
import zlib

S = Path('D:/github/my/E-Track')
R = S / '.cache/p34-final'
F = R / '.cache/p34-local-closeout-20261014/successor15'
B = R / '.acceptance-p3-4/round15'
O = B / 'origins/v13'
C = R / 'docs/acceptance-contracts/P3-4-v15.contract.json'
assert Path.cwd() == R and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode
sys.path.insert(0, str(R / 'Tools/ota/p34-acceptance'))
import live_host as h
from live_mcu import health_gate, restore_gate, stack_observation, storage_observation
sys.path.insert(0, str(R / 'Tools/ota/p3-4-link-stats'))
import acceptance_stats
import observation_capture

assert h.read_json(F / 'evaluated.json')['required_count'] == 16
prepared = h.read_json(F / 'prepared.json')
c = h.read_json(h.pinned(prepared['contract']))
m = h.read_json(h.pinned(prepared['matrix']))
assert m['overall_result'] == 'NOT_RUN'
plan = h.read_json(O / 'inputs/live-inputs.json')
registry = h.read_json(B / 'inputs/adopted-originals.json')['provenance_paths']
copies = []


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def pin(item, root=R):
    path = Path(item['path'])
    path = path if path.is_absolute() else root / path
    path = B / registry[str(path)] if str(path) in registry else path
    assert path.is_file() and path.stat().st_size == item['bytes'] and digest(path) == item['sha256'].lower()
    return path


def retain(path, name):
    path, target = Path(path), h.checked(B / name)
    data = path.read_bytes()
    if target.exists():
        assert target.read_bytes() == data
    else:
        h.raw(target, data)
    copies.append(dict(original_path=str(path), bytes=len(data), sha256=digest(path), copy=h.record(target)))
    return target


def samples(folder):
    return {p.stem: p.read_bytes() for p in folder.glob('*.bin')}


required = set(h.read_json(h.pinned(prepared['plan']))['required_commands'])
for definition in c['commands']:
    if definition['id'] not in required:
        continue
    receipt = h.read_json(B / 'commands' / (definition['id'] + '.closed.json'))
    assert receipt['argv'] == shlex.split(definition['command']) and receipt['exit_code'] == 0
    assert receipt['cleanup_complete'] and not receipt['stopped_while_running']

base = (O / 'inputs/expected-base.bin').read_bytes()
target = (O / 'inputs/expected-target.bin').read_bytes()
boot = (O / 'inputs/expected-boot.bin').read_bytes()
assert hashlib.sha256(base).hexdigest() == plan['images']['base']['image']['sha256']
assert hashlib.sha256(target).hexdigest() == plan['images']['target']['image']['sha256']
assert hashlib.sha256(boot).hexdigest() == plan['boot']['sha256']
package = (B / 'inputs/metrics/reference-1MiB.etu').read_bytes()
assert len(package) == 1048576 and hashlib.sha256(package).hexdigest() == plan['package']['sha256']

prep = O / 'ops/cmd-q-prep-restore/mcu'
mailboxes = sorted(prep.glob('*-restore-mailbox-*'))
assert len(mailboxes) == 6
phases = []
ticks = []
for folder, expected in zip(mailboxes, [1, 1, 1, 1, 3, 3]):
    result = restore_gate((folder / 'value.bin').read_bytes(), base, plan['boot']['sha256'], expected)
    phases.append(result['phase'])
    ticks.append(result['tick'])
    assert h.read_json(folder / 'commander.closed.json')['exit_code'] == 0
assert all(ticks[i + 1] > ticks[i] for i in (0, 2, 4))
restored = samples(prep / '0016-rollback-full-readback')
assert restored['app'] == base and restored['boot'] == boot
prep_health = health_gate(restored)
prep_stack = stack_observation(restored['guard'], restored['stack'])
prep_storage = storage_observation(restored, plan['package'])
assert prep_health['confirmed_state'] == 4
assert (prep / '0017-rollback-staging-zero/value.bin').read_bytes() == b'\xff' * 4096
restore_result = h.read_json(prep / 'restore-result.json')
assert restore_result['ordinary_boot'] and restore_result['journal_erased'] and not restore_result['boot_programmed']
old12 = R / '.acceptance-p3-4/round12'
old12_matrix = h.read_json(old12 / 'evidence-matrix.json')
anchor = next(x for x in old12_matrix['criteria'] if x['id'] == 'Q-PREP-RESTORE')
assert anchor['execution'] == 'EXECUTED' and anchor['result'] == 'PASS'
assert h.read_json(old12 / 'commands/CMD-Q-PREP-RESTORE.closed.json')['exit_code'] == 0
retain(old12 / 'evidence-matrix.json', 'inputs/original-v12.matrix.json')
retain(R / 'docs/acceptance-contracts/P3-4-v12.contract.json', 'inputs/original-v12.contract.json')
preparation = dict(result='PASS', interpretation='New offline evaluation of the single original v12 restoration, not another restoration.',
    mailbox_phases=phases, configuration_preserved=True, full_base_and_original_boot_equal=True,
    health=prep_health, stack=prep_stack, storage=prep_storage, journal_erased=True,
    original_executed_pass_preserved=True, new_physical_restorations=0)

troot = O / 'ops/cmd-q-transfer'
diag = O / 'diagnostics/post-interruption'
stats = h.read_json(B / 'commands/CMD-Q-TRANSFER.stdout')
rtt = h.read_json(B / 'commands/CMD-Q-TRANSFER-MCU.stdout')['metrics']
ram = h.read_json(B / 'commands/CMD-Q-TRANSFER-RAM.stdout')['metrics']
reference_stats = [h.read_json(B / ('commands/CMD-REFERENCE-' + name + '.stdout')) for name in ('V10', 'V11')]
assert stats['success'] and stats['fullZeroStart'] and stats['reference'] and stats['ackEligible']
assert stats['initialDurable'] == 0 and stats['finalDurable'] == 1048576
assert stats['parameters'] == reference_stats[1]['parameters']
assert all(stats['parameters'][key] == expected for key, expected in {
    'protocol': 2, 'requestedBaud': 921600, 'ackTimeoutMs': 2000, 'maxRetries': 5,
    'senderWindowSegments': 24, 'dataBatchFrames': 12, 'mtuChunkBytes': 244,
}.items())
snapshot = (troot / 'phone/snapshot.jsonl').read_bytes()
rows = [json.loads(line) for line in snapshot.splitlines()]
launched = h.read_json(troot / 'phone/launched.json')
assert rows[0]['pid'] == launched['pid'] and rows[0]['captureId'] == launched['capture']
runtime = (troot / 'phone/runtime.json').read_bytes()
configuration = json.loads(runtime)
stamps = [json.loads(x['message'][len('OTA_EXPERIMENT '):]) for x in rows
    if isinstance(x.get('message'), str) and x['message'].startswith('OTA_EXPERIMENT ')]
assert stamps and all(x.get('configSha256') == hashlib.sha256(runtime).hexdigest() and
    x.get('runId') == configuration['runId'] for x in stamps)
assert (troot / 'phone/downloaded.etu').read_bytes() == package
assert h.read_json(troot / 'phone/downloaded.json')['fresh_query']
_, messages = observation_capture.verify(snapshot, sentinel=plan['sentinel'], target=plan['ble_address'])
begin = next(x for x in messages.splitlines() if ' kind=begin_ack ' in x)
epoch = int(re.search(r'\bepoch=(\d+)', begin)[1])
assert rtt == ram and rtt['epoch'] == epoch and rtt['clean'] and rtt['terminal'] == 0
assert rtt['initial_durable'] == 0 and rtt['final_durable'] == 1048576
assert rtt['package_sha256'] == plan['package']['sha256'] and rtt['package_crc32'] == zlib.crc32(package)
folders = list((troot / 'mcu').glob('*-terminal-before-reboot'))
assert len(folders) == 1
terminal = folders[0]
raw = samples(terminal)
assert int.from_bytes(raw['vtor'], 'little') == 0x08010800 and int.from_bytes(raw['published'], 'little') == 853
assert raw['header_before'] == raw['header_after'] == base[0x400:0x460]
assert int.from_bytes(raw['clock'], 'little') == 288000000
ctrl, reload, current = struct.unpack('<3I', raw['systick'])
assert ctrl & 7 == 7 and reload == 287999 and current <= reload
tick0, tick1 = [int.from_bytes(raw[key], 'little') for key in ('tick0', 'tick1')]
assert tick1 > tick0
transfer_stack = stack_observation(raw['guard'], raw['stack'])
assert struct.unpack('<2I', raw['wdt']) == (5, 3124)
terminal_closed = h.read_json(terminal / 'commander.closed.json')
assert terminal_closed['exit_code'] == 0 and not terminal_closed['stopped_while_running']
assert terminal_closed['ended_monotonic_ns'] / 1e9 < h.read_json(troot / 'phase-terminal.json')['deadline_monotonic']
assert h.read_json(troot / 'start-observed.json')['within_start_window']
post = next(iter((diag / 'mcu').glob('*-current-target-after-interruption')))
post_raw = samples(post)
assert post_raw['app'] == target and post_raw['boot'] == boot
post_health = health_gate(post_raw)
stack_observation(post_raw['guard'], post_raw['stack'])
storage_observation(post_raw, plan['package'])
closed = h.read_json(diag / 'result.json')
assert closed['extra_ota'] == 0 and closed['v11_original_unchanged']
assert closed['new_capture_archived_and_pruned'] and closed['private_adb_closed']
for item in h.read_json(diag / 'phone/closed-capture.json')['originals']:
    original = pin(item)
    assert digest(O / original.relative_to(old12)) == item['sha256']
assert not (old12 / 'commands/CMD-Q-TRANSFER.closed.json').exists()
assert not (old12 / 'ops/cmd-q-transfer/result.json').exists()
assert old12_matrix['overall_result'] == 'EVIDENCE_GAP'
all_reference = acceptance_stats.aggregate([dict(id='original-v' + str(i + 10), role='clean', observation=value)
    for i, value in enumerate(reference_stats + [stats])], expected_count=3)
assert len(all_reference['groups']) == 1 and all_reference['groups'][0]['recommendedAckTimeoutMs'] == 2000
assert not all_reference['groups'][0]['stability30MeetsObservedGates']
transfer = dict(result='PASS', interpretation='Offline evaluation of original v12 product observations, not old command completion or another OTA.',
    transfer_us=stats['transferUs'], throughput_kib_s=stats['throughputKiBs'], retransmit_rate=stats['retransmitRate'],
    ack_samples=len(stats['ackSamplesUs']), app_rtt_ram_integrity=True, one_timely_old_app_sample=True,
    stack=transfer_stack, clock_hz=288000000, tick_delta=tick1-tick0, watchdog_registers=[5, 3124],
    health=post_health, full_target_and_unchanged_boot=True, final_archive_and_owned_tool_closure=True,
    original_v12_exit=None, original_v12_result='EVIDENCE_GAP', original_interruption_cause='UNESTABLISHED',
    sample_limit='Observed stack paint, clock and WDT configuration only; not whole-program worst case or electrical fault testing.',
    same_group_candidate_statistics=all_reference, new_physical_operations=0)

provenance = h.read_json(B / 'inputs/provenance-review.json')
source = h.read_json(pin(plan['source_lock']))
assert source['artifact_source_commit'] == provenance['artifact_source_commit']
assert source['ci_final']['commit'] == provenance['ci_commit']
identity = h.read_json(pin(source['runtime_build_input_identity'], S))
assert identity['standard_api_errors'] == []
ci_runs = []
for entry in source['ci_final']['runs']:
    meta = h.read_json(pin(entry['metadata'], S))
    archive_path = pin(entry['original_archive'], S)
    pin(entry['archive_receipt'], S)
    run = meta['run']
    assert run['id'] == entry['id'] and run['head_sha'] == source['ci_final']['commit']
    assert run['conclusion'] == entry['conclusion'] == 'success' and run['run_attempt'] == entry['attempt']
    assert all(x['conclusion'] in ('success', 'skipped') for x in meta['jobs']['jobs'])
    with zipfile.ZipFile(archive_path) as archive:
        members = len(archive.infolist())
    ci_runs.append(dict(name=entry['name'], commit=run['head_sha'], conclusion=run['conclusion'], archive_members=members,
        crc_check='Actual frozen archive command exited zero; not rerun during adjudication.'))
hosts = []
for entry in source['ci_final']['hosts']:
    report = h.read_json(pin(entry['report'], S))
    log = pin(entry['tests_log'], S).read_text(encoding='utf-8')
    test = next(x for x in report['commands'] if x['name'] == 'tests')
    assert report['development_result'] == 'PASS' and test['exit_code'] == 0 and not test['timed_out']
    assert all(test['diagnostics']['test_counts'][key] == entry['counts'][key] for key in ('passed', 'skipped', 'failed'))
    assert entry['counts']['failed'] == 0
    assert entry['final_line'] in log
    hosts.append(dict(host=entry['host'], counts=entry['counts']))
asset_registration = h.read_json(pin(source['artifact_source_registration'], S))
registered = {str((S / x['path']).resolve()): x for x in asset_registration['development_evidence']}
firmware = h.read_json(pin(registered[str(R / '.cache/p34-offline2/firmware/result.json')], S))
assert firmware['passed'] and len(firmware['tests']) == 7
firmware_suites = []
for item in firmware['tests']:
    log_path = pin(item['log'])
    assert digest(log_path) == registered[str(R / item['log']['path'])]['sha256']
    assert item['exit'] == 0 and not item['timed_out']
    summaries = re.findall(r'^([A-Z][A-Z0-9_]*=PASS[^\r\n]*)', log_path.read_text(encoding='utf-8'), re.MULTILINE)
    assert summaries
    firmware_suites.append(dict(test=item['test'], summaries=summaries))
assert provenance['firmware_test_source_changes'] == []
elf_origin = Path(plan['images']['base']['elf']['path'])
elf_origin = elf_origin if elf_origin.is_absolute() else R / elf_origin
ninja = elf_origin.parent.parent / 'build.ninja'
assert digest(ninja) == provenance['candidate_build']['ninja_sha256']
retain(ninja, 'inputs/candidate-build.ninja')
definitions = [line for line in ninja.read_text(encoding='utf-8').splitlines()
    if line.lstrip().startswith('DEFINES =') and 'CONFIG_OTA_LINK_METRICS' in line]
assert len(definitions) == provenance['candidate_build']['definition_rows']
for line in definitions:
    flags = dict(re.findall(r'-D([A-Z_]+)=([^ ]+)', line))
    assert all(flags.get(k) == value for k, value in provenance['candidate_build']['expected_defines'].items())
assert b'BXST:' not in base and b'RTTCMD:' not in base

model = h.read_json(B / 'inputs/receiver-model/result.json')
assert model['checks'] == 327 and model['cases'] == 10 and model['source_mutation_detected']
assert not model['hardware'] and not model['trial5_root_cause_proved']
for item in model['sources']:
    pin(item)
for item in model['commands']:
    log = B / 'inputs/receiver-model' / Path(item['log']['path']).name
    assert digest(log) == item['log']['sha256'] and not item['timed_out']
assert [x['exit'] for x in model['commands']] == [0, 0, 0, 1]
assert 'RECEIVER_FAILURE checks=327 failures=0 cases=10 mutation=0' in (B / 'inputs/receiver-model/run.log').read_text()
assert 'RECEIVER_FAILURE checks=29 failures=2 cases=1 mutation=1' in (B / 'inputs/receiver-model/mutant.log').read_text()
assert digest(Path(model['commands'][2]['command'][1])) == model['package_sha256']
host_review = h.read_json(B / 'inputs/host-close/independent/adjudication.json')
assert host_review['disposition'] == 'DECIDED_CLOSED' and host_review['result'] == 'PASS'
assert host_review['accepted_primitive_and_18_tests_unchanged'] and not host_review['new_findings']
for item in host_review['sources']:
    pin(item)
for folder, count, log_name in [('focused-2', 17, 'focused-2/tests.log'), ('live-command', 134, 'live-suite/test_p34_live_route.py.log')]:
    summary = h.read_json(B / 'inputs/host-close/implementation' / folder / 'summary.json')
    assert summary['exit'] == 0 and not summary['timed_out'] and summary['actual_test_count'] == count
    log_path = B / 'inputs/host-close/implementation' / log_name
    assert digest(log_path) == summary['log']['sha256']
    assert re.search(r'Ran ' + str(count) + r' tests in [^\r\n]+[\r\n]+\s*OK\b', log_path.read_text(encoding='utf-8'))
    for item in summary['sources']:
        pin(item)
independent = h.read_json(B / 'inputs/host-close/independent/result.json')
assert independent['methods'] == 20 and independent['exit_code'] == 0 and not independent['timed_out']
independent_log = B / 'inputs/host-close/independent/suite/tests.log'
assert digest(independent_log) == independent['log']['sha256']
assert re.search(r'Ran 20 tests in [^\r\n]+[\r\n]+\s*OK\b', independent_log.read_text(encoding='utf-8'))
source_commit = h.read_json(B / 'inputs/host-source-commit.json')
assert source_commit['commit'] == c['freeze_commit']
for item in source_commit['files']:
    pin(item)

screening_path = S / '.cache/p34-cycle-checkpoints/screening-summary.json'
screening = h.read_json(screening_path)
comparison = h.read_json(B / 'inputs/comparison-applicability.json')
assert screening['baud'] == 115200 and screening['package_bytes'] == 284643
assert len(screening['rows']) == len(comparison['rows']) == 4
retain(screening_path, 'inputs/historical-comparison/screening-summary.json')
history = []
for row, declared in zip(screening['rows'], comparison['rows']):
    assert row['candidate'] == declared['candidate']
    prefix = 'inputs/historical-comparison/' + row['candidate'] + '/'
    values = {}
    for key in ('measurement', 'binding', 'board'):
        original = pin(row[key], S)
        values[key] = h.read_json(retain(original, prefix + key + '.json'))
    measurement, binding, board = (values[key] for key in ('measurement', 'binding', 'board'))
    snapshot_path = Path(row['measurement']['path']).parent / measurement['raw_finished_snapshot']
    assert digest(snapshot_path) == measurement['raw_finished_sha256'] == binding['summary']['rawSha256']
    raw_snapshot = retain(snapshot_path, prefix + 'snapshot.jsonl').read_bytes()
    observed = acceptance_stats.inspect(raw_snapshot, binding['summary']['sentinel'], binding['summary']['target'], historical=True)
    assert observed['success'] and observed['historical'] and not observed['reference'] and not observed['ackEligible']
    assert observed['transferUs'] == round(row['transfer_seconds'] * 1000000)
    assert observed['parameters']['input']['packageSha256'] == screening['package_sha256']
    assert observed['parameters']['writeMode'] == row['write_mode'] == declared['actual_write_mode']
    assert measurement['discovers']['calls'] == declared['actual_discoveries'] == row['discoveries']
    assert observed['retransmitFrames'] == measurement['data_retransmit_frames'] == 0
    metadata_path = pin(declared['metadata'], S)
    metadata = h.read_json(retain(metadata_path, prefix + 'apk-metadata.json'))
    assert metadata['commit'] == declared['commit'] == measurement['source_commit']
    assert metadata['sha256'] == declared['apk_sha256'] == measurement['apk_sha256']
    assert metadata.get('requested_ota_link_candidate') == declared['requested']
    pin(binding['apk'], S)
    for key in ('baseline_image', 'baseline_boot', 'final_image', 'final_boot'):
        original = pin(board[key], S)
        retain(original, prefix + key + '.bin')
    assert board['final_image']['sha256'] == measurement['final_image_sha256']
    assert board['baseline_boot']['sha256'] == board['final_boot']['sha256'] == measurement['whole_boot_sha256']
    history.append(dict(candidate=row['candidate'], seconds=row['transfer_seconds'], protocol=observed['parameters']['protocol'],
        declared_source=metadata['commit'], apk_sha256=metadata['sha256'], write_mode=row['write_mode'],
        discoveries=row['discoveries'], missing_ack_samples=observed['missingAckSamples'],
        early_ack_samples=observed['earlyAckSamples'], threshold_eligible=False,
        scope='Historical declared factorial observation, not current-v2 causal speedup or final reference statistics.'))

closeout = dict(result='PASS', scope='P3-4 candidate stage only under the existing Spec and OTA-DEC-016.',
    source_commit=c['freeze_commit'], artifact_source_commit=provenance['artifact_source_commit'],
    actual_original_ci_commit=provenance['ci_commit'], ci_runs=ci_runs, flutter_hosts=hosts,
    firmware_host_suites=firmware_suites, candidate_build_definition_rows=len(definitions),
    disabled_test_commands_absent=True, receiver_model_checks=327, receiver_model_cases=10,
    receiver_mutant_rejected=True, receiver_model_is_not_hardware=True,
    caller_independent_checks=20, caller_implementation_checks=[17, 134], host_repairs='A/B and P34-HOST-CLOSE-01 CLOSED',
    historical_comparison=history, historical_source_object_not_available=True,
    candidate=dict(protocol=2, baud=921600, timeout_ms=2000, max_retries=5, window=24, batch=12, write_payload=244),
    reference_times_us=[x['transferUs'] for x in reference_stats + [stats]],
    timeout_basis='Same-group original ACK samples and the unchanged shared-contract clamp; reference and supplemental three-observation groups kept explicit.',
    timing_limits='BLE BEGIN-to-END ACK is not installation or reconnect time. Discovery is nested in GATT; ACK samples overlap work. No cross-clock subtraction or summed exclusive cost claim.',
    rates=dict(baud115200='Historical comparison reconciled', baud230400='Unreconciled, not unsupported', baud460800='Old failure/resume evidence is not a clean current-v2 comparator', baud921600='Supported candidate, not final highest stable production choice'),
    trial5='Deferred by the existing user direction; unresolved, not repaired or waived.',
    deferred=dict(P3_5='Real-backend 10/10 recovery', P5_1='Final selected-group 30/30 and real four-hour campaign', P5_2='Fault/applicability coverage'),
    final_release_allowed=False, new_physical_observations_required_for_this_candidate_scope=[],
    no_new_build_ci_test_or_device_execution=True, qualification_total=3)
review_path = B / 'adjudications/candidate-original-review.json'
h.save(review_path, dict(preparation=preparation, transfer=transfer, closeout=closeout,
    retained_originals=copies, old_v11='HARNESS_FAIL', old_v12='EVIDENCE_GAP', old_v13='PASS for its original-evidence scope',
    old_v14='EVIDENCE_GAP with native FC failure preserved', new_physical_operations=0))
host = B / 'host'
for suffix in ('started.json', 'stdout', 'stderr', 'closed.json'):
    retain(F / 'host' / ('preflight.' + suffix), 'host/preflight.' + suffix)
for name in ('prepare.py', 'run.py', 'adjudicate.py', 'prepared.json', 'evaluated.json'):
    retain(F / name, 'host/' + name)
for definition in c['commands']:
    if definition['id'] not in required:
        continue
    path = B / 'commands' / (definition['id'] + '.closed.json')
    item = h.record(path)
    m['commands'].append(dict(id=definition['id'], command=definition['command'], exit_code=0,
        output_evidence='commands/' + definition['id'] + '.stdout'))
    m['artifacts'].append(dict(id='ART-' + definition['id'], path=path.relative_to(B).as_posix(),
        size=item['bytes'], sha256=item['sha256'].upper()))
evidence = {p.relative_to(B).as_posix() for p in B.rglob('*') if p.is_file() and p != B / 'evidence-matrix.json'}
for row in m['criteria']:
    if row['execution'] == 'REUSED':
        continue
    prefix = 'origins/v13/ops/cmd-q-prep-restore/' if row['id'] == 'Q-PREP-RESTORE' else 'origins/v13/ops/cmd-q-transfer/'
    selected = {name for name in evidence if name.startswith(prefix) or name.startswith('commands/') or name.startswith('inputs/')}
    if row['id'] in ('Q-TRANSFER', 'P34-CANDIDATE-CLOSEOUT'):
        selected.update(name for name in evidence if name.startswith('origins/v13/diagnostics/') or name.startswith('host/'))
    selected.add('adjudications/candidate-original-review.json')
    row.update(result='PASS', observed=True, failure_owner=None, evidence=sorted(selected),
        notes='Actual offline original-data evaluation passed. This is not another restoration/OTA, a repaired old failed record, final campaign completion, or production release.')
m['evidence_hashes'] = {name: digest(B / name).upper() for name in sorted(evidence)}
m['overall_result'] = 'PASS'
m['stage_scope'] = 'P3-4 candidate stage PASS: reference REUSED from the original v14 EXECUTED PASS; three criteria newly evaluated offline. Old failures, trial5 deferral and 3/3 preserved. P3-5/P5 and production release remain outside this result.'
v = h.host.load('p34_candidate_final_validator', R / 'Tools/acceptance/validate_bundle.py')
errors = v.validate_matrix(m, c, m['contract_sha256']) + v.validate_evidence_files(m, B) + v.validate_artifact_files(m, B)
assert not errors, errors
h.raw(F / 'preseal-matrix.original.json', (B / 'evidence-matrix.json').read_bytes())
h.host.io.write_json(R, B / 'evidence-matrix.json', m, replace=True)
h.save(F / 'adjudicated.json', dict(result='PASS', contract=h.record(C), matrix=h.record(B / 'evidence-matrix.json'),
    review=h.record(review_path), physical_operations=0, candidate_only=True))
out = h.fresh(F / 'final-host')
env = h.environment(out)
env['PATH'] = str(pin(plan['tools']['git']).parent) + os.pathsep + env.get('PATH', '')
h.command(out, 'final-validation', shlex.split(c['operating_rules']['lineage_preflight_command']), env, seconds=300)
h.save(F / 'sealed.json', dict(result='PASS', scope='P3-4 candidate stage only',
    contract=h.record(C), matrix=h.record(B / 'evidence-matrix.json'), review=h.record(review_path),
    final_validation=h.record(out / 'final-validation.closed.json'),
    reused_criteria=['P34-CANDIDATE-REFERENCE'], newly_evaluated_criteria=['Q-PREP-RESTORE', 'Q-TRANSFER', 'P34-CANDIDATE-CLOSEOUT'],
    old_results_preserved=True, trial5_deferred_not_waived=True, production_release_allowed=False,
    physical_operations=0, qualification_total=3))
print('P34_CANDIDATE_STAGE_PASS; one original PASS reused, three offline criteria executed; final release NOT_GRANTED; device actions=0', flush=True)
