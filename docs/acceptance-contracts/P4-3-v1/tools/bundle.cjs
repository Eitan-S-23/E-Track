const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const { root, bundle, sha, run, git, guard, writeJson, readLocal, jsonLocal } = require('./io.cjs');

const source = '0067b6c3caa9ee263c53ae372fdc63cc7f74250f';
const contractPath = 'docs/acceptance-contracts/P4-3-v1.contract.json';
const matrixPath = `${bundle}/evidence-matrix.json`;
const mode = process.argv[2];
const describe = file => { const bytes = readLocal(file); return { path: file, sizeBytes: bytes.length, sha256: sha(bytes) }; };
if (mode === 'prepare') {
  const original = 'docs/ota-exec-notes/P4-3-dev-2026-10-17/';
  const copies = [
    ['live-preparation-04.zip', 'live-originals.zip'],
    ['live-preparation-04.inventory.json', 'live.inventory.json'],
    ['accept02-01.zip', 'repair-originals.zip'],
    ['accept02-01.inventory.json', 'repair.inventory.json']
  ].map(([from, to]) => [original + from, `${bundle}/inputs/${to}`]);
  for (const [, to] of copies) { guard(to); assert.ok(!fs.existsSync(path.join(root, to)), 'Original input already exists'); }
  guard(`${bundle}/inputs/private-originals.json`); guard(`${bundle}/inputs/host.json`);
  for (const [from, to] of copies) {
    fs.mkdirSync(path.dirname(guard(to)), { recursive: true });
    fs.copyFileSync(path.join(root, from), guard(to), fs.constants.COPYFILE_EXCL);
    assert.equal(describe(from).sha256, describe(to).sha256);
  }
  const files = [];
  const privateBase = '.cache/p43/private/live-drill/';
  for (const batch of ['probe-01', 'probe-02', 'probe-03', 'drill-01', 'drill-02', 'drill-03', 'drill-04', 'drill-05', 'drill-06']) {
    for (const name of fs.readdirSync(path.join(root, privateBase, batch))) {
      if (/-(?:d1-original\.json|response-original\.json|request\.json|body\.bin)$/.test(name)) files.push(privateBase + batch + '/' + name);
    }
  }
  files.push(privateBase + 'drill-06/session-original.json', privateBase + 'drill-06/served-index.html',
    '.cache/p43/private/pages/pages-csrf-02-readback.json',
    '.cache/p43/private/pages/pages-csrf-01-project-before-deploy.json',
    '.cache/p43/private/pages/pages-csrf-01-project-after-deploy.json');
  assert.equal(new Set(files).size, files.length);
  writeJson(`${bundle}/inputs/private-originals.json`, { schema: 'p43-private-originals-v1',
    purpose: 'Immutable private retrieval registry, not published credentials; each read also matches the original public receipt and projection.',
    originalOperator: 'P4-3 implementation agent', originalSources: ['933b790e69e04ee551ad255398e08f12a1b2a107', '972e74c43cd36b7a308e457296aaf7bb06120e78'],
    captured: '2026-10-17/2026-10-18; exact timestamps remain in each source receipt',
    retrieval: 'Same authorized task worktree only; do not recreate an absent original by rerunning cloud mutations.',
    entries: files.sort().map(describe) });
  const tar = run('where.exe', ['tar']).toString('utf8').trim().split(/\r?\n/)[0];
  writeJson(`${bundle}/inputs/host.json`, { node: { version: process.version, executable: process.execPath, sha256: sha(fs.readFileSync(process.execPath)) },
    tar: { executable: tar, version: run(tar, ['--version']).toString('utf8').trim(), sha256: sha(fs.readFileSync(tar)) },
    python: run('python', ['--version']).toString('utf8').trim(), platform: process.platform, arch: process.arch,
    root, temporaryOutputs: '.cache/p43-formal', newCloudBusinessRequests: 0 });
  process.stdout.write(JSON.stringify({ copiedOriginals: copies.map(([, to]) => describe(to)), privateOriginals: files.length, prepared: true }, null, 2) + '\n');
} else if (mode === 'freeze') {
  assert.ok(!fs.existsSync(path.join(root, contractPath)), 'Never rewrite a frozen contract');
  const head = git(['rev-parse', 'HEAD']).trim();
  git(['diff', '--exit-code', source, head, '--', 'app/bluetooth_flutter_Trace/cloudflare/update-service',
    '.github/workflows/cloudflare-update-service.yml', '.github/workflows/deploy-cloudflare-admin.yml']);
  const groups = [['production', 'Production', 'production_source'], ['validation', 'Validation', 'validation_inputs'],
    ['governance', 'Governance', 'governance_inputs'], ['cloudflare', 'Cloudflare', 'production_source'],
    ['evaluation', 'P43Evaluation', 'validation_inputs'], ['evidence', 'Evidence', 'validation_inputs']]
    .map(([id, profile, category]) => ({ id, profile, category }));
  const inputs = [
    ['live-archive', 'live-originals.zip'], ['live-index', 'live.inventory.json'],
    ['repair-archive', 'repair-originals.zip'], ['repair-index', 'repair.inventory.json'],
    ['private-originals', 'private-originals.json'], ['host', 'host.json'],
    ['governance-run', 'governance.json'], ['governance-jobs', 'governance-jobs.json'], ['governance-logs', 'governance-logs.zip']
  ].map(([id, file]) => { const bytes = readLocal(`${bundle}/inputs/${file}`); return { id,
    category: id === 'host' ? 'environment' : 'fixture', description: id === 'private-originals'
      ? 'Exact local sensitive original registry; bytes remain private, independently checked against archived public receipts/projections. Missing or changed originals fail closed.'
      : `Hash-bound original ${id}; source/date/operator remain in original metadata. Offline assessment, not a repeated operation.`,
    fingerprint: `sha256:${sha(bytes)}`, evidence_path: `inputs/${file}`, evidence_sha256: sha(bytes) }; });
  const specifications = [
    ['formal-ci', 'inspect-ci.cjs', '', ['cloudflare', 'evaluation']],
    ['formal-live', 'inspect-live.cjs', '', ['cloudflare', 'evaluation']],
    ['formal-ui', 'ui-reconcile-probe.cjs', '', ['cloudflare', 'evaluation']],
    ['formal-governance', 'inspect-ci.cjs', ' governance', ['governance', 'evidence', 'evaluation']]
  ];
  const commands = specifications.map(([id, entry, extra, dependencies]) => ({ id,
    description: 'evidence: after frozen-input precheck, independently evaluate retained originals/current source with no cloud or device action; one execution, 15-minute timeout. Preserve failures; source/harness changes require a successor contract and minimal rerun plan.',
    command: `node ${bundle}/tools/run.cjs ${id} node ${bundle}/tools/${entry}${extra}`,
    input_groups: dependencies, runner_paths: [`${bundle}/tools/run.cjs`, `${bundle}/tools/io.cjs`, `${bundle}/tools/${entry}`],
    expected_exit_codes: [0, 1, 2], success_exit_code: 0, output_required: true }));
  const artifacts = commands.map(command => ({ id: command.id + '-result', description: 'Original stdout/stderr from the independently executed evaluator.', path: `evidence/${command.id}.log` }));
  const definitions = [
    ['P43-API', 'Fixed endpoints/envelopes, reason, role/Access/origin/CSRF errors, ready gates, version rules, CAS and atomic audit; source-bound native 270/270 and compiled router 3/3.', ['formal-ci']],
    ['P43-CHANNEL', 'Original stable/beta publish/retract/stop/resume and repaired stale-tab CAS: continuous revision/audit chains, one winner, no loser mutation and unchanged cancellation state.', ['formal-ci', 'formal-live']],
    ['P43-PUBLIC', 'Retracted low release is offered only to older clients; upgraded clients receive NO_UPDATE. Independent latest/download switches govern the exact original signed URL and verified binary bytes.', ['formal-ci', 'formal-live']],
    ['P43-RELEASE', 'Ready/owner/reason/reference protection, conditional disable and recovery capability; same-key replay, conflict/tombstone boundaries, real expiry and one-effect audit; no new recovery issuance.', ['formal-ci', 'formal-live', 'formal-ui']],
    ['P43-UI', 'Bilingual retract boundary and fresh confirmation/cancel/conflict UI, 36 source-bound browser cases, original screenshots and unchanged-source six-case interrupted-reconciliation probe.', ['formal-ci', 'formal-live', 'formal-ui']],
    ['P43-RETENTION', 'Retract/stop never changes release identity or deletes assets. Original six asset rows and high release stay unchanged; low disable is preceded by the original dependency/reference check.', ['formal-ci', 'formal-live']],
    ['P43-GOVERNANCE', 'Actual source-bound governance CI, original failures preserved, profile and runner registration and contract validation route; no hardware/production readiness or real publisher/viewer coverage is implied.', ['formal-governance']]
  ];
  const criteria = definitions.map(([id, description, ids]) => ({ id, description, required: true,
    kind: id === 'P43-GOVERNANCE' ? 'process' : 'functional', evidence_types: ['raw_log'],
    input_groups: [...new Set(ids.flatMap(commandId => commands.find(command => command.id === commandId).input_groups))],
    dependency_rationale: id === 'P43-GOVERNANCE'
      ? 'Governance supplies task/authority rules; Evidence supplies actual validator/profile/workflow inputs; P43Evaluation supplies original CI interpretation and contained command capture.'
      : 'Cloudflare supplies the unchanged server and repaired UI/config inputs; P43Evaluation supplies Worker tests and frozen source/original-data evaluators with their contained command capture. Historical collector source is bound inside external original archives, not executed again.',
    external_inputs: id === 'P43-GOVERNANCE' ? ['governance-run', 'governance-jobs', 'governance-logs', 'host']
      : ['live-archive', 'live-index', 'repair-archive', 'repair-index', 'host', ...(ids.includes('formal-live') ? ['private-originals'] : [])],
    command_ids: ids, artifact_ids: ids.map(value => value + '-result'),
    gate: { type: 'boolean', basis: 'frozen_requirement', expected: true } }));
  const contract = { schema: 'etrack-acceptance-contract-v3', contract_id: 'P4-3-v1', version: 1, task_id: 'P4-3',
    parent_contract_sha256: null, status: 'FROZEN', approved_by: 'Codex independent root acceptance; explicit user delegation P43-AUTH-20261018',
    approved_at: new Date().toISOString(), implementation_ref: source, freeze_commit: head, freeze_tree: git(['rev-parse', 'HEAD:']).trim(),
    profile_config_blob: git(['rev-parse', 'HEAD:Tools/provenance/manifest_profiles.json']).trim(),
    result_taxonomy: ['PASS', 'PRODUCT_FAIL', 'HARNESS_FAIL', 'EVIDENCE_GAP', 'ENV_BLOCKED'],
    invalidation_policy: 'docs/acceptance-execution-contract.md', input_groups: groups, external_inputs: inputs,
    commands, artifacts, criteria, performance_gates: [] };
  writeJson(contractPath, contract);
  writeJson(`${bundle}/contract.json`, contract);
  writeJson(matrixPath, { schema: 'etrack-evidence-matrix-v2', contract_id: contract.contract_id, contract_sha256: sha(readLocal(contractPath)),
    round_id: 'P43-20261018-01', overall_result: 'NOT_RUN', previous_matrix_sha256: null, rerun_plan_path: null, rerun_plan_sha256: null,
    criteria: criteria.map(item => ({ id: item.id, result: 'NOT_OBSERVED', failure_owner: null, execution: 'EXECUTED', reused_from_round: null,
      origin_contract_sha256: null, origin_matrix_sha256: null, observed: null, evidence: [], notes: 'First formal round; prior pre-reviews and implementation runs are not formal REUSED origins.' })),
    evidence_hashes: {}, commands: [], artifacts: [] });
  process.stdout.write(JSON.stringify({ freezeCommit: head, freezeTree: contract.freeze_tree, contractSha256: sha(readLocal(contractPath)), criteria: criteria.length, status: 'NOT_RUN' }, null, 2) + '\n');
} else if (mode === 'finalize') {
  const contract = jsonLocal(contractPath);
  const matrix = jsonLocal(matrixPath);
  assert.equal(matrix.overall_result, 'NOT_RUN');
  assert.equal(matrix.contract_sha256, sha(readLocal(contractPath)));
  const results = Object.fromEntries(contract.commands.map(command => [command.id, jsonLocal(`${bundle}/evidence/${command.id}.log`)]));
  assert.equal(results['formal-ci'].productVerdict, true);
  assert.deepEqual(results['formal-ci'].archiveEntries, { live: 585, repair: 158 });
  assert.equal(results['formal-live'].identityAndBindingsVerified, true);
  assert.equal(results['formal-live'].semanticTamperControlsRejected, 2);
  assert.deepEqual(results['formal-live'].effectsCorrelated, { channel: 24, recovery: 3, disable: 1 });
  assert.equal(results['formal-ui'].passed, 6); assert.equal(results['formal-ui'].failed, 0);
  assert.equal(results['formal-governance'].verified, true);
  const evidence = new Set(contract.external_inputs.map(item => item.evidence_path));
  matrix.commands = contract.commands.map(command => {
    const receipt = jsonLocal(`${bundle}/evidence/${command.id}.json`);
    assert.equal(receipt.exitCode, 0); assert.equal(receipt.signal, null); assert.equal(receipt.error, null);
    assert.equal(receipt.label, command.id); assert.equal(receipt.command, 'node');
    const actual = `node ${bundle}/tools/run.cjs ${receipt.label} ${receipt.command} ${receipt.args.join(' ')}`;
    assert.equal(actual, command.command);
    evidence.add(`evidence/${command.id}.log`); evidence.add(`evidence/${command.id}.json`);
    return { id: command.id, command: command.command, exit_code: receipt.exitCode, output_evidence: `evidence/${command.id}.log`,
      started_at: receipt.started, ended_at: receipt.ended };
  });
  matrix.artifacts = contract.artifacts.map(item => { const bytes = readLocal(`${bundle}/${item.path}`); return { id: item.id, path: item.path, size: bytes.length, sha256: sha(bytes) }; });
  matrix.criteria = contract.criteria.map(item => ({ id: item.id, result: 'PASS', failure_owner: null, execution: 'EXECUTED',
    reused_from_round: null, origin_contract_sha256: null, origin_matrix_sha256: null, observed: true,
    evidence: item.command_ids.map(id => `evidence/${id}.log`),
    notes: 'The frozen offline evaluator ran in this round. Historical CI/cloud originals are external inputs, not new CI/cloud executions. Role/deployment/dependency/private retrieval limitations remain in the acceptance report.' }));
  matrix.evidence_hashes = Object.fromEntries([...evidence].sort().map(file => [file, sha(readLocal(`${bundle}/${file}`))]));
  matrix.overall_result = 'PASS';
  writeJson(matrixPath, matrix, true);
  process.stdout.write(JSON.stringify({ overallResult: matrix.overall_result, requiredCriteria: matrix.criteria.length, independentlyExecutedCommands: matrix.commands.length,
    newCloudBusinessRequests: 0, reusedFormalCriteria: 0 }, null, 2) + '\n');
} else {
  throw new Error('Expected prepare, freeze or finalize');
}
