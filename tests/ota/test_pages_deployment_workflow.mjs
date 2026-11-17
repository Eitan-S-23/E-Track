import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import { isDeepStrictEqual } from 'node:util';
import vm from 'node:vm';

const workflow = (await readFile(new URL('../../.github/workflows/deploy-cloudflare-admin.yml', import.meta.url), 'utf8')).replace(/\r\n/g, '\n');
const helper = workflow.match(/^          const samePagesRuntime = \(before, after\) => \{[\s\S]*?^          \};/m);
assert.ok(helper, 'Readback must expose its actual runtime comparison for regression checks');
const samePagesRuntime = vm.runInNewContext(`${helper[0]}\nsamePagesRuntime`, { structuredClone, isDeepStrictEqual });

function fixture() {
  const environment = {
    wrangler_config_hash: 'generated-before',
    env_vars: {
      APP_ID: { type: 'plain_text', value: 'trace' },
      ACCESS_AUD: { type: 'secret_text' },
    },
    d1_databases: { DB: { id: 'database-fixture' } },
    r2_buckets: { RELEASES_BUCKET: { name: 'bucket-fixture' } },
    kv_namespaces: { MANIFEST_CACHE: { namespace_id: 'cache-fixture' } },
    durable_object_namespaces: { RATE_LIMITER: { namespace_id: 'limiter-fixture' } },
  };
  return { production: structuredClone(environment), preview: structuredClone(environment) };
}

test('the actual workflow uses the comparator and preserves its failure gates', () => {
  assert.match(workflow, /configurationUnchanged: samePagesRuntime\(entry\.deploymentConfigs, project\.deployment_configs\)/);
  assert.match(workflow, /!p\.configurationUnchanged \|\| !p\.updated \|\| p\.source !== before\.source \|\| p\.status !== 'success'/);
  assert.match(workflow, /CLOUDFLARE_API_TOKEN: \$\{\{ secrets\.E_TRACK_CI \}\}/);
  assert.doesNotMatch(workflow, /continue-on-error|exit 0/);
});

test('all Pages credential consumers use the named e-track-ci secret', () => {
  const bindings = [...workflow.matchAll(/^\s+CLOUDFLARE_API_TOKEN: \$\{\{ secrets\.([A-Z_]+) \}\}$/gm)];
  assert.equal(bindings.length, 5, 'Preflight, Worker, Admin, Public and readback must all bind the token');
  assert.deepEqual(bindings.map(binding => binding[1]), Array(5).fill('E_TRACK_CI'));
  assert.doesNotMatch(workflow, /secrets\.CLOUDFLARE_API_TOKEN/);
});

test('optional Worker/schema deployment precedes both Pages deployments', () => {
  const worker = workflow.indexOf('run: node app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/deploy-worker-staging.mjs');
  assert.ok(worker > 0 && worker < workflow.indexOf('run: node scripts/deploy-admin-staging.mjs'));
  assert.ok(worker < workflow.indexOf('run: node node_modules/wrangler/bin/wrangler.js pages deploy'));
  assert.match(workflow, /include_worker:\n\s+description: [^\n]+\n\s+default: false\n\s+type: boolean/);
  assert.match(workflow, /name: Apply pending schema[^\n]+\n\s+if: inputs.include_worker/);
  assert.match(workflow, /path: \.cache\/pages-deploy\/worker\/result\.json/);
  assert.doesNotMatch(workflow, /path: \.cache\/pages-deploy\/(?:\*|worker\/$|worker\/private)/m);
});

test('accepts unchanged runtime and generated hash changes in both environments', () => {
  const before = fixture();
  const after = structuredClone(before);
  assert.equal(samePagesRuntime(before, after), true);
  after.production.wrangler_config_hash = 'generated-after';
  delete after.preview.wrangler_config_hash;
  assert.equal(samePagesRuntime(before, after), true);
});

for (const [name, change] of [
  ['production variable', value => { value.production.env_vars.APP_ID.value = 'different'; }],
  ['Access secret slot', value => { delete value.production.env_vars.ACCESS_AUD; }],
  ['D1 binding', value => { value.production.d1_databases.DB.id = 'different'; }],
  ['R2 binding', value => { value.production.r2_buckets.RELEASES_BUCKET.name = 'different'; }],
  ['KV binding', value => { value.production.kv_namespaces.MANIFEST_CACHE.namespace_id = 'different'; }],
  ['Durable Object binding', value => { value.production.durable_object_namespaces.RATE_LIMITER.namespace_id = 'different'; }],
  ['preview runtime', value => { value.preview.env_vars.APP_ID.value = 'different'; }],
  ['missing environment', value => { delete value.preview; }],
  ['additional runtime field', value => { value.production.compatibility_date = '2026-01-01'; }],
]) {
  test(`rejects changed ${name}`, () => {
    const before = fixture();
    const after = structuredClone(before);
    after.production.wrangler_config_hash = 'generated-after';
    change(after);
    assert.equal(samePagesRuntime(before, after), false);
  });
}

test('does not ignore a runtime variable that happens to share the metadata name', () => {
  const before = fixture();
  const after = structuredClone(before);
  after.production.env_vars.wrangler_config_hash = { type: 'plain_text', value: 'runtime' };
  assert.equal(samePagesRuntime(before, after), false);
});

test('preserves original provider snapshots', () => {
  const before = fixture();
  const after = fixture();
  after.production.wrangler_config_hash = 'generated-after';
  const originals = structuredClone({ before, after });
  samePagesRuntime(before, after);
  assert.deepEqual({ before, after }, originals);
});
