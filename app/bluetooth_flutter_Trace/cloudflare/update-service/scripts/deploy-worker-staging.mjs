import assert from 'node:assert/strict';
import { execFileSync, spawnSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { isDeepStrictEqual } from 'node:util';

export const target = Object.freeze({
  account: 'af6dd848e6a21f1cd26d44b1b656af7b',
  worker: 'trace-update-service-staging',
  service: 'trace-update-service-dev',
  environment: 'staging',
  database: '0133ad9e-d4a2-4fef-a659-4f2bf3d3a645',
  databaseName: 'trace-update-staging',
  cache: 'fe3b08f2e0774072a44bdf140c44174a',
  bucket: 'trace-update-staging-releases',
});
const workerRoute = `/workers/scripts/${target.worker}`;
const schemaSql = 'SELECT name FROM d1_migrations ORDER BY id;'
  + 'SELECT id,current_release_id,revision FROM channels ORDER BY id;'
  + 'SELECT id,current_release_id,revision,disable_downloads FROM firmware_channels ORDER BY id;'
  + 'PRAGMA table_info(delta_jobs);'
  + "SELECT name FROM sqlite_master WHERE type='trigger' AND name IN ('delta_file_no_restore','app_delta_file_no_restore') ORDER BY name;";

export function stagingConfig(config, workerDir) {
  const value = structuredClone({ ...config, ...config.env?.staging });
  assert.equal(config.name, target.service, 'Unexpected original service grouping');
  assert.equal(value.name, target.worker, 'Unexpected Worker target');
  assert.deepEqual(value.d1_databases?.map(b => [b.binding, b.database_name, b.database_id]),
    [['DB', target.databaseName, target.database]], 'Unexpected D1 binding');
  assert.deepEqual(value.kv_namespaces, [{ binding: 'MANIFEST_CACHE', id: target.cache }]);
  assert.deepEqual(value.r2_buckets, [{ binding: 'RELEASES_BUCKET', bucket_name: target.bucket }]);
  assert.deepEqual(value.durable_objects, { bindings: [{ name: 'RATE_LIMITER', class_name: 'RateLimiter' }] });
  assert.equal(value.vars?.ENVIRONMENT, 'staging');
  assert.equal(value.vars?.APP_ID, 'trace');
  assert.equal(value.main, 'src/index.ts');
  // Keep the named environment: Wrangler derives the existing cf:service and
  // cf:environment labels from it, even with legacy per-environment Workers.
  const output = structuredClone(config);
  delete output.$schema;
  output.env = { staging: output.env.staging };
  output.main = path.resolve(workerDir, value.main);
  for (const area of [output, output.env.staging]) {
    area.vars = {};
    for (const db of area.d1_databases ?? []) db.migrations_dir = path.resolve(workerDir, '../migrations');
  }
  output.keep_vars = true;
  return output;
}

export function runtimeSettings(settings) {
  const value = structuredClone(settings);
  assert.ok(Array.isArray(value.bindings), 'Worker settings lack bindings');
  value.bindings.sort((a, b) => a.name.localeCompare(b.name));
  if (Array.isArray(value.tags)) value.tags.sort();
  value.annotations ??= {};
  for (const key of ['workers/tag', 'workers/message', 'workers/triggered_by']) delete value.annotations[key];
  return value;
}

function expectedRuntime(settings) {
  const value = runtimeSettings(settings);
  const tags = value.tags ?? [];
  const required = [`cf:service=${target.service}`, `cf:environment=${target.environment}`];
  assert.ok(tags.every(tag => !/^cf:(service|environment)=/.test(tag) || required.includes(tag)),
    'Conflicting Worker environment labels');
  // A previous flattened-config upload removed these two labels. Restore only
  // missing standard labels; every other setting and custom tag stays strict.
  value.tags = [...new Set([...tags, ...required])].sort();
  return value;
}

export function pendingMigrations(committed, applied) {
  assert.ok(committed.length > 0 && committed.every(n => /^\d{4}_[a-z0-9_]+\.sql$/.test(n)));
  assert.equal(new Set(committed).size, committed.length);
  assert.deepEqual(applied, committed.slice(0, applied.length), 'Live migration history is not a committed prefix');
  return committed.slice(applied.length);
}

export function cliDiagnostics(output, secrets) {
  let text = output.replace(/\x1b\[[0-9;]*m/g, '');
  for (const secret of secrets.filter(Boolean)) text = text.replaceAll(secret, '[REDACTED]');
  text = text.replace(/(?:gh[opusr]_|github_pat_)[A-Za-z0-9_]+/g, '[REDACTED]');
  return text.split(/\r?\n/).filter(line => /\bERROR\b|\bfailed\b|\[code:\s*\d+\]|\bHTTP\s+[45]\d\d/i.test(line))
    .slice(-12).map(line => line.trim().slice(0,600)).join(' | ');
}

function currentDeployment(response) {
  const latest = [...(response.deployments ?? [])].sort((a, b) => b.created_on.localeCompare(a.created_on))[0];
  assert.ok(latest?.id && latest.versions?.length === 1 && latest.versions[0].percentage === 100,
    'Expected one fully deployed Worker version');
  return { id: latest.id, version: latest.versions[0].version_id };
}

function assertLiveBindings(settings, config) {
  const binding = name => settings.bindings?.find(b => b.name === name);
  const db = binding('DB');
  assert.ok(db?.type === 'd1' && (db.database_id ?? db.id) === target.database, 'Live D1 differs');
  assert.ok(binding('MANIFEST_CACHE')?.type === 'kv_namespace'
    && binding('MANIFEST_CACHE').namespace_id === target.cache, 'Live KV differs');
  assert.ok(binding('RELEASES_BUCKET')?.type === 'r2_bucket'
    && binding('RELEASES_BUCKET').bucket_name === target.bucket, 'Live R2 differs');
  assert.ok(binding('RATE_LIMITER')?.type === 'durable_object_namespace'
    && binding('RATE_LIMITER').class_name === 'RateLimiter' && binding('RATE_LIMITER').namespace_id,
  'Live Durable Object differs');
  assert.equal(binding('ENVIRONMENT')?.text, 'staging');
  assert.equal(binding('APP_ID')?.text, 'trace');
  assert.equal(settings.compatibility_date, config.compatibility_date);
  assert.deepEqual(settings.compatibility_flags, config.compatibility_flags);
}

// Only Cloudflare/CLI boundaries are injected; tests exercise the real ordering and gates.
export async function deployWorker({ source, config, committed, cloud, wrangler, record }) {
  assert.match(source, /^[0-9a-f]{40}$/);
  const result = { source, worker: target.worker, phase: 'preflight', ok: false, migrated: false, updated: false };
  const query = () => cloud(`/d1/database/${target.database}/query`, { sql: schemaSql });
  const readSchema = value => {
    assert.equal(value.length, 5, 'Incomplete database readback');
    assert.ok(value.every(r => r.success === true && Array.isArray(r.results)), 'Database query failed');
    return value.map(r => r.results);
  };
  const crons = response => response.schedules.map(s => s.cron).sort();
  try {
    const before = await cloud(`${workerRoute}/settings`);
    assertLiveBindings(before, config);
    const expectedSettings = expectedRuntime(before);
    const restoreLabels = !isDeepStrictEqual(runtimeSettings(before), expectedSettings);
    const schedules = await cloud(`${workerRoute}/schedules`);
    assert.deepEqual(crons(schedules), [...config.triggers.crons].sort(), 'Live schedules differ');
    const deployment = currentDeployment(await cloud(`${workerRoute}/deployments`));
    const version = await cloud(`${workerRoute}/versions/${deployment.version}`);
    const schema = readSchema(await query());
    result.pendingMigrations = pendingMigrations(committed, schema[0].map(r => r.name));
    result.previousVersion = deployment.version;
    record('before', { settings: before, schedules, deployment, schema }, true);
    if (result.pendingMigrations.length) {
      result.phase = 'migrate';
      await wrangler('migrate', ['d1', 'migrations', 'apply', target.databaseName, '--env', 'staging', '--remote']);
      result.migrated = true;
    }
    const afterSchema = readSchema(await query());
    assert.deepEqual(pendingMigrations(committed, afterSchema[0].map(r => r.name)), []);
    assert.ok(afterSchema[3].some(c => c.name === 'asset_state'), 'Missing delta file state');
    assert.equal(afterSchema[4].length, 2, 'Missing file retirement guards');
    result.schemaVerified = true;
    result.channelsUnchanged = isDeepStrictEqual(schema.slice(1, 3), afterSchema.slice(1, 3));
    assert.ok(result.channelsUnchanged, 'Channel state changed; reconcile before deploying');
    result.phase = 'deploy';
    if (version.annotations?.['workers/tag'] !== source || restoreLabels) {
      await wrangler('deploy', ['deploy', '--env', 'staging', '--keep-vars', '--tag', source, '--message', `source:${source}`]);
      result.updated = true;
    }
    result.phase = 'readback';
    const after = await cloud(`${workerRoute}/settings`);
    const live = currentDeployment(await cloud(`${workerRoute}/deployments`));
    const liveVersion = await cloud(`${workerRoute}/versions/${live.version}`);
    const liveSchedules = await cloud(`${workerRoute}/schedules`);
    const liveSchema = readSchema(await query());
    record('after', { settings: after, deployment: live, schema: liveSchema, schedules: liveSchedules }, true);
    result.version = live.version;
    result.deployment = live.id;
    result.sourceVerified = liveVersion.annotations?.['workers/tag'] === source
      && liveVersion.annotations?.['workers/message'] === `source:${source}`;
    result.configurationUnchanged = isDeepStrictEqual(runtimeSettings(before), runtimeSettings(after));
    result.runtimePreserved = isDeepStrictEqual(expectedSettings, runtimeSettings(after));
    result.environmentLabelsRestored = restoreLabels && result.runtimePreserved;
    result.schedulesUnchanged = isDeepStrictEqual(crons(schedules), crons(liveSchedules));
    result.channelsUnchanged = isDeepStrictEqual(schema.slice(1, 3), liveSchema.slice(1, 3));
    assert.ok(result.sourceVerified && result.runtimePreserved && result.schedulesUnchanged
      && result.channelsUnchanged, 'Worker source/runtime verification failed');
    result.ok = true;
    result.phase = 'complete';
    return result;
  } catch (error) {
    result.error = error.message;
    throw error;
  } finally {
    record('result', result, false);
  }
}

async function main() {
  const env = process.env;
  const service = fileURLToPath(new URL('../', import.meta.url));
  const root = path.resolve(service, '../../../..');
  const workerDir = path.join(service, 'worker');
  const out = path.join(root, '.cache/pages-deploy/worker');
  assert.ok(env.GITHUB_ACTIONS === 'true' && env.GITHUB_REPOSITORY === 'Eitan-S-23/E-Track', 'Actions only');
  assert.equal(path.resolve(process.cwd()), root);
  assert.equal(path.resolve(env.GITHUB_WORKSPACE ?? ''), root);
  assert.equal(env.CLOUDFLARE_ACCOUNT_ID, target.account);
  assert.ok(env.CLOUDFLARE_API_TOKEN, 'Missing E_TRACK_CI binding');
  const checked = value => {
    const absolute = path.resolve(value), relative = path.relative(root, absolute);
    assert.ok(!path.isAbsolute(relative) && relative.split(path.sep)[0] !== '..', 'Output outside checkout');
    for (let item = absolute; ; item = path.dirname(item)) {
      if (fs.existsSync(item)) assert.ok(!fs.lstatSync(item).isSymbolicLink()
        && fs.realpathSync.native(item) === item, 'Redirected output');
      if (item === path.dirname(item)) break;
    }
    return absolute;
  };
  for (const directory of [out, workerDir, env.TMPDIR, env.XDG_CONFIG_HOME,
    env.XDG_CACHE_HOME, env.WRANGLER_LOG_PATH, env.npm_config_cache]) checked(directory);
  const git = args => execFileSync('git', args, { cwd: root, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] }).trim();
  assert.match(env.SOURCE_SHA ?? '', /^[0-9a-f]{40}$/);
  assert.equal(git(['rev-parse', 'HEAD']), env.SOURCE_SHA);
  git(['diff', '--exit-code', 'HEAD', '--', path.relative(root, service)]);
  const committed = git(['ls-files', '--', `${path.relative(root, service).split(path.sep).join('/')}/migrations/*.sql`])
    .split('\n').map(name => path.basename(name)).sort();
  const config = stagingConfig(JSON.parse(fs.readFileSync(path.join(workerDir, 'wrangler.jsonc'), 'utf8')), workerDir);
  fs.mkdirSync(checked(path.join(out, 'private')), { recursive: true, mode: 0o700 });
  const record = (name, value, privateValue) => fs.writeFileSync(
    checked(path.join(out, privateValue ? 'private' : '', `${name}.json`)),
    JSON.stringify(value, null, 2) + '\n', { flag: 'wx', mode: 0o600 });
  record('worker-config', config, true);
  const configFile = path.join(out, 'private/worker-config.json');
  const cloud = async (route, data) => {
    const response = await fetch(`https://api.cloudflare.com/client/v4/accounts/${target.account}${route}`, {
      method: data ? 'POST' : 'GET', redirect: 'error', signal: AbortSignal.timeout(30000),
      headers: { Authorization: `Bearer ${env.CLOUDFLARE_API_TOKEN}`, 'Content-Type': 'application/json' },
      body: data ? JSON.stringify(data) : undefined,
    });
    const body = await response.json();
    if (!response.ok || body.success !== true) throw new Error(`Cloudflare ${route}: HTTP ${response.status}`);
    return body.result;
  };
  const wrangler = async (label, args) => {
    const extra = label === 'deploy' ? ['--tsconfig', path.join(workerDir, 'tsconfig.json'),
      '--outdir', checked(path.join(out, 'bundle'))] : [];
    const logFile = checked(path.join(out, 'private', `${label}.log`));
    const log = fs.openSync(logFile, 'wx', 0o600);
    console.log(`${label}: using the existing staging target`);
    try {
      const run = spawnSync(process.execPath, [path.join(workerDir, 'node_modules/wrangler/bin/wrangler.js'),
        ...args, '--config', configFile, ...extra], {
        cwd: workerDir, env: { ...env, CI: 'true', WRANGLER_LOG: 'info' }, stdio: ['ignore', log, log], timeout: 600000,
      });
      if (run.status !== 0) {
        const diagnostic = cliDiagnostics(fs.readFileSync(logFile, 'utf8'),
          [env.CLOUDFLARE_API_TOKEN, env.GH_TOKEN, env.GITHUB_TOKEN]);
        throw new Error(`${label} failed (${run.status ?? run.error?.code}): ${diagnostic || 'No structured CLI error was emitted'}`);
      }
    } finally { fs.closeSync(log); }
  };
  const effective = { ...config, ...config.env.staging };
  console.log(JSON.stringify(await deployWorker({ source: env.SOURCE_SHA, config: effective, committed, cloud, wrangler, record })));
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main().catch(error => { console.error(error.message); process.exitCode = 1; });
}
