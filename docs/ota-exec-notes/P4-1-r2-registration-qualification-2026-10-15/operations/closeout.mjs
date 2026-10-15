import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { spawnSync } from 'node:child_process';
import { fileURLToPath, pathToFileURL } from 'node:url';

const directory = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(directory, '../..');
const { outputPath } = await import(pathToFileURL(path.join(root,
  'app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/firmware-cli.mjs')));
const guard = value => outputPath(root, value);
const encode = value => JSON.stringify(value, null, 2) + '\n';
const sha = bytes => createHash('sha256').update(bytes).digest('hex');
const read = value => JSON.parse(fs.readFileSync(guard(path.resolve(root, value)), 'utf8'));
assert.equal(fs.realpathSync.native(process.cwd()), fs.realpathSync.native(root));
const action = process.argv[2];
assert.ok(['protected', 'audit'].includes(action));
const resultPath = guard(path.join(directory, action === 'protected' ? 'protected-after.json' : 'closeout-audit.json'));
assert.equal(fs.existsSync(resultPath), false);
const credentialDirectory = guard(path.join(root, '.cache/cf-auth-input'));
const token = fs.readFileSync(path.join(credentialDirectory, 'token.txt'), 'utf8').trim();
const secrets = read('.cache/cf-auth-input/firmware-test-secrets.json');
const expiredPath = guard(path.join(credentialDirectory, 'r2-qualification/readonly-credentials.json'));
const expired = read(expiredPath);
const sensitive = [token, ...Object.values(secrets), ...Object.values(expired)].filter(value => typeof value === 'string' && value.length > 10);
const redact = value => sensitive.reduce((text, secret) => text.split(secret).join('[REDACTED]'), String(value));
const result = { started: new Date().toISOString(), action, root, ok: false };
try {
  if (action === 'protected') {
    const original = read('.cache/cf-readonly-20261015-r1/d1-inventory.json');
    assert.equal(original.route, 'accounts/af6dd848e6a21f1cd26d44b1b656af7b/d1/database/0133ad9e-d4a2-4fef-a659-4f2bf3d3a645/query');
    const response = await fetch('https://api.cloudflare.com/client/v4/' + original.route, {
      method: 'POST', redirect: 'error', headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      body: JSON.stringify({ sql: original.sql }), signal: AbortSignal.timeout(30000) });
    const body = await response.json();
    result.protectedD1 = { sql: original.sql, status: response.status, cfRay: response.headers.get('cf-ray'), body };
    assert.equal(response.status, 200); assert.equal(body.success, true);
    assert.ok(body.result.every(value => value.success && value.meta.rows_written === 0 && !value.meta.changed_db));
    assert.deepEqual(body.result.map(value => value.results), original.body.result.map(value => value.results));
    const old = read('.cache/cf-readonly-20261015-r1/bindings.json')[0];
    assert.equal(old.route, 'accounts/af6dd848e6a21f1cd26d44b1b656af7b/workers/scripts/trace-update-service-staging/settings');
    const settingsResponse = await fetch('https://api.cloudflare.com/client/v4/' + old.route, {
      redirect: 'error', headers: { Authorization: `Bearer ${token}` }, signal: AbortSignal.timeout(30000) });
    const settings = await settingsResponse.json();
    assert.equal(settingsResponse.status, 200); assert.equal(settings.success, true);
    assert.equal(settings.result.compatibility_date, old.result.compatibility_date);
    assert.deepEqual(settings.result.compatibility_flags, old.result.compatibility_flags);
    assert.equal(settings.result.bindings.length, old.result.bindings.length);
    const bindings = old.result.bindings.map(previous => {
      const current = settings.result.bindings.find(value => value.name === previous.name);
      assert.ok(current);
      const observed = Object.fromEntries(Object.keys(previous).map(key => [key, current[key]]));
      assert.deepEqual(observed, previous);
      return observed;
    });
    result.protectedWorker = { status: settingsResponse.status, cfRay: settingsResponse.headers.get('cf-ray'), bindings };
    const main = read('.cache/github/p41-s3-main-before-record.json');
    assert.equal(main.object.sha, 'b42d3e25db85d6aba397cb4d0fb34bb5b653904f');
    assert.deepEqual(read('.cache/github/p41-s3-releases-after.json'), []);
    assert.equal(read('.cache/github/p41-s3-environments-after.json').total_count, 0);
    result.github = { mainSha: main.object.sha, releaseCount: 0, environmentCount: 0 };
    result.limitations = 'Protected old D1 count/observable binding comparison and repository Release inventory only; not complete production R2/channel-identity/Release zero-effect acceptance.';
  } else {
    const records = ['first-upload', 'first-upload-r2', 'assets-register'].map(name => read(path.join(directory, name + '.json')));
    assert.deepEqual(records.map(value => value.ok), [false, true, true]);
    const commands = ['p41-s3-first-upload', 'p41-s3-first-upload-r2', 'p41-s3-assets-register'].map(label => read('.cache/logs/' + label + '.json'));
    assert.deepEqual(commands.map(value => value.exitCode), [1, 0, 0]);
    assert.ok(commands.every(value => value.closed));
    const processes = [...commands.map(value => ({ pid: value.pid, name: 'node.exe' })),
      ...records.flatMap(value => value.observations.filter(entry => entry.pid).map(entry => ({ pid: entry.pid, name: 'curl.exe' })))];
    const query = spawnSync('wmic', ['process', 'get', 'Name,ProcessId', '/format:csv'], {
      cwd: root, encoding: 'utf8', windowsHide: true, timeout: 20000 });
    assert.equal(query.status, 0);
    const current = query.stdout.split(/\r?\n/).map(line => line.trim().split(','));
    const liveOwned = current.filter(parts => processes.some(value => Number(parts.at(-1)) === value.pid && parts.at(-2) === value.name));
    assert.deepEqual(liveOwned, []);
    const sharedIndexSha256 = sha(fs.readFileSync('D:/github/my/E-Track/.git/index'));
    assert.equal(sharedIndexSha256, '2907ee569cb8415877c8c688b3e09b5948a789d6430796eab99ae3ad43f3a3dd');
    const scanned = [];
    function walk(dir) {
      for (const entry of fs.readdirSync(guard(dir), { withFileTypes: true })) {
        const file = guard(path.join(dir, entry.name));
        assert.equal(entry.isSymbolicLink(), false);
        if (entry.isDirectory()) walk(file);
        else {
          const bytes = fs.readFileSync(file);
          for (const value of sensitive) assert.equal(bytes.includes(Buffer.from(value)), false, 'Private value leaked: ' + file);
          scanned.push(file);
        }
      }
    }
    walk(directory);
    for (const command of commands) for (const target of Object.values(command.outputs)) guard(target);
    const acl = spawnSync('icacls', [credentialDirectory], { cwd: root, encoding: 'utf8', windowsHide: true });
    assert.equal(acl.status, 0);
    const probe = read(path.join(directory, 'readonly-probe.json'));
    assert.ok(Date.now() > Date.parse(probe.finished) + probe.ttlSeconds * 1000);
    const expiredBytes = fs.statSync(expiredPath).size;
    fs.unlinkSync(guard(expiredPath));
    assert.equal(fs.existsSync(expiredPath), false);
    result.sharedIndexSha256 = sharedIndexSha256;
    result.closedOwnedProcesses = processes;
    result.workerdProcessCount = current.filter(parts => parts.at(-2) === 'workerd.exe').length;
    result.credentialScan = { files: scanned.length, suppliedTokenTestSecretsAndExpiredReadonlyValueMatches: 0,
      shortLivedReadWriteCredentials: 'Minted only in process memory; passed by stdin; never written or exported to CI.' };
    result.removedExpiredCredential = { path: expiredPath, bytes: expiredBytes, reason: 'Read-only 900-second credential expired; completed probe retained without the secret.' };
    result.retainedPrivateInputs = { directory: credentialDirectory, names: ['token.txt', 'firmware-test-secrets.json'],
      reason: 'Authorized isolated environment remains open for subsequent configuration qualification; do not force another token paste.', acl: acl.stdout.trim() };
    result.outputs = [directory, path.join(root, '.cache/logs'), path.join(root, '.cache/github'),
      path.join(root, 'docs/ota-exec-notes/P4-1-r2-registration-qualification-2026-10-15'),
      path.join(root, 'docs/ota-exec-notes/P4-1-implementation-2026-10-15.md')];
    result.externalWriteAssessment = 'All selected outputs and controllable child homes/temp/cache paths are project-contained; no PowerShell, workerd, build, deployment or system installation was invoked. Prior P41-AUDIT-01 is unchanged.';
    assert.equal(process.env.NODE_COMPILE_CACHE, undefined);
  }
  result.ok = true;
} catch (error) {
  result.error = { name: error.name, message: redact(error.message) };
  process.exitCode = 1;
} finally {
  result.finished = new Date().toISOString();
  fs.writeFileSync(resultPath, redact(encode(result)), { flag: 'wx' });
  console.log(JSON.stringify({ action, ok: result.ok, error: result.error, resultPath }));
}
