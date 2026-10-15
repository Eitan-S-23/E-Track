import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { firmwareGitHub } from '../app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/firmware-github-release.mjs';
import { canonicalJson } from '../app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/firmware-schema.mjs';
import { digest } from '../app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/prepare-firmware-release.mjs';
import { outputPath } from '../app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/firmware-cli.mjs';

const root = fs.realpathSync.native(path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..'));
assert.equal(fs.realpathSync.native(process.cwd()), root);
const commit = 'c860b3be7a0b1a3ca1b3a53cf79cc9ef21cc9124';
const tree = 'e823a55cfb45549dc355e58e56ed0e2aceabc769';
const repository = 'Eitan-S-23/E-Track';
const archivePath = 'docs/ota-exec-notes/P4-1-bootstrap-baseline-2026-10-15';
const origin = `https://api.github.com/repos/${repository}`;
const out = outputPath(root, path.join(root, '.cache/p41-bootstrap-readonly'));
const routes = new Map([
  ['https://api.github.com/user', 'identity.json'],
  [`${origin}/releases?per_page=100&page=1`, 'releases.json'],
  [`${origin}/git/ref/tags/mcu-e-track-at32f435-v3.2.8`, 'target-tag.json'],
  [`${origin}/git/commits/${commit}`, 'archive-commit.json'],
  [`${origin}/git/trees/${tree}?recursive=1`, 'archive-tree.json'],
  [`${origin}/contents/${archivePath}/provenance.json?ref=${commit}`, 'provenance-contents.json'],
  [`${origin}/contents/${archivePath}/app-final.bin?ref=${commit}`, 'app-contents.json'],
]);
const names = [...routes.values(), 'descriptor-development-only.json', 'app-final.bin', 'qualification.json'];
for (const name of names) assert(!fs.existsSync(outputPath(root, path.join(out, name))));
assert(!fs.existsSync(out));
const head = spawnSync('git', ['--no-optional-locks', 'rev-parse', 'HEAD'], { cwd: root, encoding: 'utf8', windowsHide: true });
assert.equal(head.status, 0);
assert.equal(head.stdout.trim(), commit);
const clean = spawnSync('git', ['--no-optional-locks', '-c', 'core.fsmonitor=false', 'diff', '--exit-code', 'HEAD', '--',
  'app/bluetooth_flutter_Trace/cloudflare/update-service/scripts'], { cwd: root, windowsHide: true });
assert.equal(clean.status, 0);
fs.mkdirSync(out);
const write = (name, data) => fs.writeFileSync(outputPath(root, path.join(out, name)), data, { flag: 'wx' });
const json = (name, value) => write(name, JSON.stringify(value, null, 2) + '\n');
const signal = AbortSignal.timeout(120000);
const requests = [];
const receipt = { startedAt: new Date().toISOString(), testedCommit: commit, pid: process.pid,
  helperSha256: digest(fs.readFileSync(fileURLToPath(import.meta.url))),
  scope: 'Development-only authenticated bootstrap download through the existing client',
  approvalOrigin: 'LOCAL_TEST_EXPECTATION_NOT_PROTECTED_APPROVAL',
  protectedConfigurationChanged: false, targetFirmwareBuilt: false,
  rehearsal: 'NOT_RUN', production: 'NOT_RUN', remoteWrites: 0, requests, ok: false };
try {
  const credential = spawnSync('C:/Program Files/GitHub CLI/gh.exe',
    ['auth', 'token', '--hostname', 'github.com', '--user', 'Eitan-S-23'],
    { cwd: root, encoding: 'utf8', windowsHide: true, timeout: 15000,
      env: { ...process.env, GH_NO_UPDATE_NOTIFIER: '1', GH_PROMPT_DISABLED: '1' } });
  assert.equal(credential.status, 0);
  const token = credential.stdout.trim();
  assert(token);
  async function fetcher(input, options = {}) {
    const url = String(input), name = routes.get(url);
    assert(name, 'Request outside the seven exact read-only endpoints');
    assert.equal(options.method ?? 'GET', 'GET');
    assert.equal(options.redirect, 'error');
    assert(!requests.some(row => row.file === name), 'Repeated request is not admitted');
    const response = await fetch(url, { ...options, signal: options.signal ?? signal });
    const bytes = Buffer.from(await response.arrayBuffer());
    assert(bytes.length <= 16 * 1024 * 1024, 'Oversized GitHub response');
    if (name === 'identity.json') {
      const identity = JSON.parse(bytes);
      assert.equal(response.status, 200);
      assert.equal(identity.login, 'Eitan-S-23');
      json(name, { login: identity.login, id: identity.id, status: response.status,
        scope: 'Sanitized credential identity, not a retained private user profile' });
    } else write(name, bytes);
    requests.push({ method: 'GET', url, file: name, status: response.status,
      sizeBytes: bytes.length, sha256: digest(bytes), identitySanitized: name === 'identity.json' });
    return new Response(bytes, { status: response.status, headers: { 'Content-Type': 'application/json' } });
  }
  await fetcher('https://api.github.com/user', { redirect: 'error', signal,
    headers: { Authorization: `Bearer ${token}`, Accept: 'application/vnd.github+json', 'X-GitHub-Api-Version': '2022-11-28' } });
  const source = JSON.parse(fs.readFileSync(path.join(root, archivePath, 'provenance.json')));
  const descriptor = { provenanceKind: 'inaugural-bootstrap-v1', isFormalRelease: false, kind: 'app',
    versionName: '3.2.7', versionCode: 30207, commitSha: source.run.head_sha, buildTimestamp: 1792014177,
    imageSha256: source.verification.finalImage.sha256, sourceSha256: source.verification.finalImage.sha256,
    sourceSizeBytes: 605072, archiveCommit: commit, archivePath,
    sourceRunId: String(source.run.id), sourceRunAttempt: String(source.run.run_attempt),
    sourceArtifactId: String(source.artifact.id), sourceArtifactSha256: source.artifact.digest.slice(7),
    provenanceSha256: digest(fs.readFileSync(path.join(root, archivePath, 'provenance.json'))),
    targetVersionName: '3.2.8', targetCommitSha: commit,
    sourceUrl: `https://raw.githubusercontent.com/${repository}/${commit}/${archivePath}/app-final.bin` };
  json('descriptor-development-only.json', descriptor);
  const target = { versionName: '3.2.8', commitSha: commit };
  const client = firmwareGitHub({ repository, token, fetcher, signal });
  const before = requests.length;
  await assert.rejects(client.releaseBase(descriptor, target, undefined, 'rehearsal'), /independently approved/);
  assert.equal(requests.length, before);
  receipt.missingApprovalRejectedBeforeNetwork = true;
  // This injected digest exercises the reader, not protected environment approval.
  const sourceResult = await client.releaseBase(descriptor, target, digest(Buffer.from(canonicalJson(descriptor))), 'rehearsal');
  assert.equal(sourceResult.bytes.compare(fs.readFileSync(path.join(root, archivePath, 'app-final.bin'))), 0);
  write('app-final.bin', sourceResult.bytes);
  assert.equal(requests.length, 7);
  receipt.sourceEvidence = sourceResult.evidence;
  receipt.remoteDownload = 'PASS';
  receipt.ok = true;
} catch (error) {
  receipt.failureClass = error?.name ?? 'Error';
  receipt.remoteDownload = 'NOT_VERIFIED';
  process.exitCode = 1;
} finally {
  receipt.endedAt = new Date().toISOString();
  receipt.closed = true;
  json('qualification.json', receipt);
  console.log(JSON.stringify({ ok: receipt.ok, remoteDownload: receipt.remoteDownload,
    requests: requests.length, receipt: path.join(out, 'qualification.json'), failureClass: receipt.failureClass }));
}
