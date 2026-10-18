const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const { createHash } = require('node:crypto');
const { spawnSync } = require('node:child_process');

const root = path.resolve(__dirname, '../../../..');
const bundle = 'docs/acceptance-contracts/P4-3-v1';
const sha = bytes => createHash('sha256').update(bytes).digest('hex');
function run(command, args, options = {}) {
  const result = spawnSync(command, args, { cwd: root, windowsHide: true,
    maxBuffer: 128 * 1024 * 1024, timeout: 120000, ...options });
  if (result.status !== 0) throw new Error(`${command} failed (${result.status}): ${result.error?.message || result.stderr?.toString()}`);
  return result.stdout;
}
const git = args => run('git', ['--no-optional-locks', ...args]).toString('utf8');
function guard(file) {
  const full = path.resolve(root, file);
  const relative = path.relative(root, full);
  assert.ok(relative !== '..' && !relative.startsWith(`..${path.sep}`) && !path.isAbsolute(relative), 'Output outside worktree');
  let current = path.parse(full).root;
  for (const part of full.slice(current.length).split(path.sep).filter(Boolean)) {
    current = path.join(current, part);
    if (!fs.existsSync(current)) continue;
    assert.ok(!fs.lstatSync(current).isSymbolicLink(), 'Linked output path');
    if (process.platform === 'win32') {
      const result = spawnSync('fsutil.exe', ['reparsepoint', 'query', current], { cwd: root, windowsHide: true });
      const diagnostic = new TextDecoder('gbk').decode(Buffer.concat([result.stdout || Buffer.alloc(0), result.stderr || Buffer.alloc(0)]));
      assert.ok(result.status === 1 && /not a reparse point|\u4e0d\u662f\u4e00\u4e2a\u91cd\u5206\u6790\u70b9/.test(diagnostic), 'Unverified output parent');
    }
  }
  return full;
}
function writeJson(file, value, replace = false) {
  const full = guard(file);
  fs.mkdirSync(path.dirname(full), { recursive: true });
  guard(full);
  fs.writeFileSync(full, JSON.stringify(value, null, 2) + '\n', { flag: replace ? 'w' : 'wx' });
}
const readLocal = file => fs.readFileSync(path.resolve(root, file));
const jsonLocal = file => JSON.parse(readLocal(file));
function verify(bytes, entry) {
  assert.equal(bytes.length, entry.sizeBytes, `Original size mismatch: ${entry.path}`);
  assert.equal(sha(bytes), entry.sha256, `Original hash mismatch: ${entry.path}`);
  return bytes;
}
function archiveFile(bytes) {
  const file = guard(`.cache/p43-formal/archives/${sha(bytes)}.zip`);
  if (!fs.existsSync(file)) {
    fs.mkdirSync(path.dirname(file), { recursive: true });
    guard(file);
    fs.writeFileSync(file, bytes, { flag: 'wx' });
  }
  assert.equal(sha(fs.readFileSync(file)), sha(bytes), 'Changed nested archive cache');
  return file;
}
function store(kind) {
  assert.ok(['live', 'repair'].includes(kind));
  const inventory = jsonLocal(`${bundle}/inputs/${kind}.inventory.json`);
  const archivePath = `${bundle}/inputs/${kind}-originals.zip`;
  const archive = readLocal(archivePath);
  verify(archive, { ...inventory.archive, path: `${kind}-originals.zip` });
  const entries = new Map(inventory.entries.map(entry => [entry.path, entry]));
  assert.equal(entries.size, inventory.entries.length, 'Duplicate inventory entry');
  const list = run('tar', ['-tf', archivePath]).toString('utf8').trim().split(/\r?\n/);
  assert.equal(new Set(list).size, list.length, 'Duplicate archive entry');
  assert.deepEqual(list.sort(), [...entries.keys()].sort());
  const privateEntries = kind === 'live'
    ? new Map(jsonLocal(`${bundle}/inputs/private-originals.json`).entries.map(entry => [entry.path, entry])) : new Map();
  const cache = new Map();
  const privateRead = new Set();
  function read(file) {
    if (cache.has(file)) return cache.get(file);
    let bytes;
    if (entries.has(file)) {
      bytes = verify(run('tar', ['-xOf', archivePath, file]), entries.get(file));
    } else {
      assert.ok(file.startsWith('.cache/p43/private/') && privateEntries.has(file), `Unregistered external input: ${file}`);
      bytes = verify(readLocal(file), privateEntries.get(file));
      privateRead.add(file);
    }
    cache.set(file, bytes);
    return bytes;
  }
  return { read, json: file => JSON.parse(read(file)), text: file => read(file).toString('utf8'),
    exists: file => entries.has(file) || privateEntries.has(file),
    names: prefix => [...entries.keys()].filter(file => file.startsWith(prefix + '/') && !file.slice(prefix.length + 1).includes('/'))
      .map(file => file.slice(prefix.length + 1)),
    verifyAll: () => { for (const file of entries.keys()) read(file); return entries.size; },
    privateReadCount: () => privateRead.size, archiveSha256: sha(archive), inventory };
}
module.exports = { root, bundle, sha, run, git, guard, writeJson, readLocal, jsonLocal, verify, archiveFile, store };
