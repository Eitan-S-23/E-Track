const io = require('./io.cjs');
const { spawnSync } = require('node:child_process');
const destination = io.reserve('credential-protection-01.json');
const directory = io.project + '/.cache/p44-cred-20261019/private';
const expected = [
  'p44-s3-credentials-20261019.json', 'production_access_key_id.txt',
  'production_secret_access_key.txt', 'rehearsal_access_key_id.txt', 'rehearsal_secret_access_key.txt',
].sort();
const source = io.project + '/app/bluetooth_flutter_Trace/cloudflare/update-service/.github-actions-secrets.staging.local.json';
io.guard(directory);
io.assert.deepEqual(io.fs.readdirSync(directory).sort(), expected, 'Unexpected private child: inspect before changing ACLs');
const targets = [directory, ...expected.map(name => directory + '/' + name), source].map(io.guard);
for (const target of targets) io.assert.ok(!io.fs.lstatSync(target).isSymbolicLink());
const env = io.environment();
const report = { startedAt: new Date().toISOString(), action: 'Current-user-only ACL repair for handed-off credential inputs',
  targets: [], contentChanged: false, tokenRotation: false, platformMutations: false, formalAcceptance: 'NOT_RUN' };
function run(command, args) {
  const result = spawnSync(command, args, { cwd: io.project, env, encoding: 'utf8', windowsHide: true, timeout: 30000 });
  io.assert.equal(result.status, 0, 'Native ACL operation failed: ' + command);
  return result.stdout.trim();
}
try {
  const owner = run('whoami.exe', []).toLowerCase();
  const identity = run('whoami.exe', ['/user', '/fo', 'csv', '/nh']);
  const ids = identity.match(/S-1-5-(?:[0-9]+-)*[0-9]+/g);
  io.assert.equal(ids?.length, 1, 'Ambiguous current SID');
  report.currentUserSid = ids[0];
  for (const target of targets) {
    const isDirectory = io.fs.statSync(target).isDirectory();
    const beforeHash = isDirectory ? null : io.sha256(io.fs.readFileSync(target));
    const entry = { path: target, isDirectory, beforeAcl: run('icacls.exe', [target]) };
    report.targets.push(entry);
    io.guard(target);
    entry.operationOutput = run('icacls.exe', [target, '/inheritance:r', '/grant:r',
      '*' + ids[0] + (isDirectory ? ':(OI)(CI)F' : ':F')]);
    entry.afterAcl = run('icacls.exe', [target]);
    const grants = entry.afterAcl.split(/\r?\n/).filter(line => /:\(/.test(line));
    io.assert.equal(grants.length, 1, 'Unexpected explicit principal remains; stop without deleting content');
    io.assert.ok(grants[0].toLowerCase().includes(owner + ':'), 'ACL owner mismatch');
    io.assert.ok(!grants[0].includes('(I)'), 'Unexpected inherited grant');
    if (!isDirectory) io.assert.equal(io.sha256(io.fs.readFileSync(target)), beforeHash, 'Credential bytes changed');
    entry.currentUserOnly = true;
    entry.contentUnchanged = true;
  }
  report.complete = true;
} catch (error) {
  report.error = error.message;
  process.exitCode = 1;
} finally {
  report.endedAt = new Date().toISOString();
  io.writeJson(destination, report);
  process.stdout.write(JSON.stringify({ output: destination, complete: report.complete || false,
    protectedTargets: report.targets.filter(x => x.currentUserOnly).length, error: report.error,
    credentialBytesChanged: false, platformMutations: false }) + '\n');
}
