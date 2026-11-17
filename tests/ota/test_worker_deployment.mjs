import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import path from 'node:path';
import test from 'node:test';
import { cliDiagnostics, deployWorker, pendingMigrations, runtimeSettings, stagingConfig, target }
  from '../../app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/deploy-worker-staging.mjs';

const sourceConfig = JSON.parse(await readFile(new URL(
  '../../app/bluetooth_flutter_Trace/cloudflare/update-service/worker/wrangler.jsonc', import.meta.url), 'utf8'));
const source = 'a'.repeat(40);
const committed = ['0014_admin_ux.sql', '0015_delta_file_deletion.sql'];
const deploymentConfig = stagingConfig(sourceConfig, path.resolve('worker-fixture'));
const config = { ...deploymentConfig, ...deploymentConfig.env.staging };

function fixture(options = {}) {
  const settings = {
    compatibility_date: config.compatibility_date, compatibility_flags: config.compatibility_flags,
    annotations: { 'workers/triggered_by': 'deployment', 'custom/audit': 'preserve' },
    tags: [`cf:service=${target.service}`, `cf:environment=${target.environment}`],
    observability: { enabled: true, logs: { enabled: true, invocation_logs: false } },
    bindings: [
      { name: 'DB', type: 'd1', database_id: target.database },
      { name: 'MANIFEST_CACHE', type: 'kv_namespace', namespace_id: target.cache },
      { name: 'RELEASES_BUCKET', type: 'r2_bucket', bucket_name: target.bucket },
      { name: 'RATE_LIMITER', type: 'durable_object_namespace', class_name: 'RateLimiter', namespace_id: 'original-do' },
      { name: 'ENVIRONMENT', type: 'plain_text', text: 'staging' },
      { name: 'APP_ID', type: 'plain_text', text: 'trace' },
      { name: 'CUSTOM_RUNTIME_VAR', type: 'plain_text', text: 'kept-live-value' },
      { name: 'DEPLOY_TOKEN_SHA256', type: 'secret_text' },
    ],
  };
  options.before?.(settings);
  let migrated = options.migrated ?? false;
  let deployed = options.deployed ?? false;
  let settingsReads = 0;
  const events = [], records = [];
  const cloud = async (route, body) => {
    events.push(['read', route]);
    if (options.deny?.(route)) throw new Error('Denied exact target read');
    if (route.endsWith('/settings')) {
      const value = structuredClone(settings);
      if (++settingsReads > 1) options.after?.(value);
      return value;
    }
    if (route.endsWith('/schedules')) return { schedules: config.triggers.crons.map(cron => ({ cron })) };
    if (route.endsWith('/deployments')) return { deployments: [{ id: deployed ? 'new-deploy' : 'old-deploy',
      created_on: '2026-11-18T00:00:00Z', versions: [{ version_id: deployed ? 'new-version' : 'old-version', percentage: 100 }] }] };
    if (route.includes('/versions/')) return { annotations: deployed
      ? { 'workers/tag': options.wrongSource ? 'b'.repeat(40) : source, 'workers/message': `source:${source}` } : {} };
    assert.ok(route.endsWith('/query'));
    assert.match(body.sql, /^SELECT /);
    assert.doesNotMatch(body.sql, /INSERT|UPDATE|DELETE|DROP|ALTER/);
    const names = migrated ? committed : committed.slice(0, 1);
    return [names.map(name => ({ name })), [{ id: 'app-stable', current_release_id: 'original-app', revision: 8 }],
      [{ id: 'firmware-stable', current_release_id: 'original-mcu', revision: 5, disable_downloads: 0 }],
      migrated ? [{ name: 'asset_state' }] : [],
      migrated ? [{ name: 'delta_file_no_restore' }, { name: 'app_delta_file_no_restore' }] : []]
      .map(results => ({ success: true, results }));
  };
  const wrangler = async (label, args) => {
    events.push([label, args]);
    if (label === options.fail) throw new Error(`Actual ${label} failure`);
    if (label === 'migrate') migrated = true;
    if (label === 'deploy') deployed = true;
  };
  const record = (name, value, privateValue) => records.push({ name, value: structuredClone(value), privateValue });
  return { run: () => deployWorker({ source, config, committed, cloud, wrangler, record }), events, records };
}

test('staging-only config preserves infrastructure but never writes live variables or secrets', () => {
  const before = structuredClone(sourceConfig);
  const value = stagingConfig(sourceConfig, path.resolve('worker-fixture'));
  assert.equal(value.name, sourceConfig.name);
  assert.equal(value.env.staging.name, target.worker);
  assert.equal(value.keep_vars, true);
  assert.deepEqual(value.vars, {});
  assert.deepEqual(value.env.staging.vars, {});
  assert.deepEqual(Object.keys(value.env), ['staging']);
  assert.ok(path.isAbsolute(value.main) && path.isAbsolute(value.d1_databases[0].migrations_dir));
  assert.ok(path.isAbsolute(value.env.staging.d1_databases[0].migrations_dir));
  assert.deepEqual(value.env.staging.triggers, sourceConfig.env.staging.triggers);
  assert.deepEqual(value.env.staging.observability, sourceConfig.env.staging.observability);
  assert.deepEqual(sourceConfig, before);
});

for (const [label, change] of [
  ['Worker', c => { c.env.staging.name = 'different'; }],
  ['service grouping', c => { c.name = 'different'; }],
  ['D1', c => { c.env.staging.d1_databases[0].database_id = 'different'; }],
  ['KV', c => { c.env.staging.kv_namespaces[0].id = 'different'; }],
  ['R2', c => { c.env.staging.r2_buckets[0].bucket_name = 'different'; }],
  ['DO', c => { c.env.staging.durable_objects.bindings[0].class_name = 'Different'; }],
]) test(`rejects changed ${label} source target before writes`, () => {
  const value = structuredClone(sourceConfig);
  change(value);
  assert.throws(() => stagingConfig(value, path.resolve('worker-fixture')));
});

test('migration planning preserves history, applies only missing suffix and rejects drift', () => {
  assert.deepEqual(pendingMigrations(committed, committed.slice(0, 1)), [committed[1]]);
  assert.deepEqual(pendingMigrations(committed, committed), []);
  assert.throws(() => pendingMigrations(committed, [committed[1]]));
  assert.throws(() => pendingMigrations(committed, [...committed, '0016_unknown.sql']));
  assert.throws(() => pendingMigrations(['../outside.sql'], []));
});

test('real orchestration reads targets, migrates, verifies schema, deploys and verifies source/runtime', async () => {
  const f = fixture();
  const result = await f.run();
  assert.equal(result.ok, true);
  assert.equal(result.schemaVerified, true);
  assert.equal(result.sourceVerified, true);
  assert.equal(result.configurationUnchanged, true);
  assert.equal(result.channelsUnchanged, true);
  const migrate = f.events.findIndex(e => e[0] === 'migrate'), deploy = f.events.findIndex(e => e[0] === 'deploy');
  assert.ok(migrate > 3 && deploy > migrate + 1);
  assert.deepEqual(f.events[migrate][1], ['d1', 'migrations', 'apply', target.databaseName, '--env', 'staging', '--remote']);
  assert.deepEqual(f.events[deploy][1], ['deploy', '--env', 'staging', '--keep-vars', '--tag', source, '--message', `source:${source}`]);
  assert.ok(f.records.find(r => r.name === 'before').privateValue);
  assert.ok(f.records.find(r => r.name === 'after').privateValue);
  const publicRecord = f.records.filter(r => !r.privateValue);
  assert.equal(publicRecord.length, 1);
  assert.doesNotMatch(JSON.stringify(publicRecord), /kept-live-value|DEPLOY_TOKEN_SHA256/);
});

test('already applied migration and matching version are not replayed', async () => {
  const f = fixture({ migrated: true, deployed: true });
  const result = await f.run();
  assert.equal(result.ok, true);
  assert.equal(result.updated, false);
  assert.equal(result.migrated, false);
  assert.ok(f.events.every(e => e[0] === 'read'));
});

test('restores only missing standard environment labels without repeating an applied migration', async () => {
  const f = fixture({ migrated: true, deployed: true,
    before: s => { s.tags = []; },
    after: s => { s.tags = [`cf:service=${target.service}`, `cf:environment=${target.environment}`]; } });
  const result = await f.run();
  assert.equal(result.ok, true);
  assert.equal(result.configurationUnchanged, false);
  assert.equal(result.runtimePreserved, true);
  assert.equal(result.environmentLabelsRestored, true);
  assert.equal(result.migrated, false);
  assert.deepEqual(f.events.filter(e => e[0] !== 'read').map(e => e[0]), ['deploy']);
});

test('conflicting service grouping fails before any remote write', async () => {
  const f = fixture({ before: s => { s.tags = ['cf:service=another-service']; } });
  await assert.rejects(f.run(), /Conflicting Worker environment labels/);
  assert.ok(f.events.every(e => e[0] === 'read'));
});

test('denied preflight does not turn into a deployment permission probe', async () => {
  const f = fixture({ deny: route => route.endsWith('/settings') });
  await assert.rejects(f.run(), /Denied/);
  assert.ok(f.events.every(e => e[0] === 'read'));
  assert.equal(f.records.at(-1).value.phase, 'preflight');
});

test('incorrect live target fails before migrations', async () => {
  const f = fixture({ before: s => { s.bindings.find(b => b.name === 'DB').database_id = 'another-database'; } });
  await assert.rejects(f.run(), /Live D1 differs/);
  assert.ok(f.events.every(e => e[0] === 'read'));
});

test('migration failure prevents deploy and retains a failure receipt', async () => {
  const f = fixture({ fail: 'migrate' });
  await assert.rejects(f.run(), /Actual migrate failure/);
  assert.equal(f.events.some(e => e[0] === 'deploy'), false);
  assert.equal(f.records.at(-1).value.phase, 'migrate');
  assert.equal(f.records.at(-1).value.ok, false);
});

test('deployment failure retains the completed migration instead of claiming success', async () => {
  const f = fixture({ fail: 'deploy' });
  await assert.rejects(f.run(), /Actual deploy failure/);
  assert.equal(f.records.at(-1).value.migrated, true);
  assert.equal(f.records.at(-1).value.ok, false);
  assert.equal(f.records.at(-1).value.error, 'Actual deploy failure');
});

test('failure diagnostics retain provider codes without credentials or ordinary config output', () => {
  const result = cliDiagnostics('CUSTOM_VAR="private-value"\n\u001b[31m[ERROR] Authentication failed [code: 10000]\u001b[0m\n'
    + 'HTTP 403 using fixture-token and ghp_fixture\n', ['fixture-token']);
  assert.match(result, /Authentication failed \[code: 10000\]/);
  assert.match(result, /HTTP 403/);
  assert.doesNotMatch(result, /fixture-token|ghp_fixture|private-value|\x1b/);
});

for (const [label, after] of [
  ['variable', s => { s.bindings.find(b => b.name === 'CUSTOM_RUNTIME_VAR').text = 'changed'; }],
  ['secret', s => { s.bindings = s.bindings.filter(b => b.type !== 'secret_text'); }],
  ['Durable Object', s => { s.bindings.find(b => b.name === 'RATE_LIMITER').namespace_id = 'changed'; }],
  ['observability', s => { s.observability.logs.invocation_logs = true; }],
  ['unknown annotation', s => { s.annotations['custom/audit'] = 'changed'; }],
  ['service labels', s => { s.tags = ['cf:service=different']; }],
]) test(`live ${label} drift keeps deployment red`, async () => {
  const f = fixture({ after });
  await assert.rejects(f.run(), /verification failed/);
  assert.equal(f.records.at(-1).value.ok, false);
  assert.equal(f.records.at(-1).value.configurationUnchanged, false);
});

test('wrong deployed source fails even after a successful CLI exit', async () => {
  const f = fixture({ wrongSource: true });
  await assert.rejects(f.run(), /verification failed/);
  assert.equal(f.records.at(-1).value.sourceVerified, false);
});

test('runtime comparison ignores only version bookkeeping and binding order', () => {
  const before = { bindings: [{ name: 'B' }, { name: 'A' }], annotations: { 'custom/audit': 'same' } };
  const after = { bindings: [{ name: 'A' }, { name: 'B' }],
    annotations: { 'custom/audit': 'same', 'workers/tag': source, 'workers/message': `source:${source}` } };
  assert.deepEqual(runtimeSettings(before), runtimeSettings(after));
  assert.equal(before.bindings[0].name, 'B');
});
