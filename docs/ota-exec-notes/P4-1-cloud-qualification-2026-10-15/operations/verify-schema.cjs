const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const { DatabaseSync } = require('node:sqlite');
const root = path.resolve(__dirname, '../../..');
assert.equal(fs.realpathSync.native(root).toLowerCase(), root.toLowerCase());
assert.equal(fs.realpathSync.native(__dirname).toLowerCase(), __dirname.toLowerCase());
for (let parent = __dirname; parent !== path.dirname(parent); parent = path.dirname(parent)) {
  assert.equal(fs.lstatSync(parent).isSymbolicLink(), false);
}
const output = path.join(__dirname, 'schema-comparison.json');
assert.equal(fs.existsSync(output), false);
const bytes = fs.readFileSync(path.join(__dirname, 'inspect-after.json'));
const receipt = JSON.parse(bytes);
const remote = JSON.parse(receipt.stdout);
assert.equal(receipt.exitCode, 0);
assert.equal(remote.length, 3);
assert.ok(remote.every(x => x.success && x.meta.rows_written === 0 && !x.meta.changed_db));
assert.deepEqual(remote[1].results.map(x => x.name), ['0001_init.sql', '0002_patch_formats.sql',
  '0003_firmware_releases.sql', '0004_announcements.sql', '0005_firmware_multi_asset.sql']);
assert.deepEqual(remote[2].results, []);
const db = new DatabaseSync(':memory:');
try {
  db.exec(remote[0].results.find(x => x.name === 'd1_migrations').sql);
  db.exec(fs.readFileSync(path.join(__dirname, 'accepted-migrations.sql'), 'utf8'));
  const normalize = rows => rows.filter(x => x.name !== '_cf_KV').map(x => ({
    type: x.type, name: x.name, tbl_name: x.tbl_name, sql: x.sql?.replace(/\r\n/g, '\n') ?? null
  }));
  const local = normalize(db.prepare('SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name').all());
  const actual = normalize(remote[0].results);
  assert.deepEqual(actual, local);
  const counts = Object.fromEntries(['table', 'index', 'trigger'].map(type =>
    [type, actual.filter(x => x.type === type).length]));
  const result = { ok: true, checkedAt: new Date().toISOString(), comparison: 'All sqlite_master SQL after CRLF normalization only',
    migrations: remote[1].results, counts, foreignKeyViolations: 0,
    remoteReceiptSha256: crypto.createHash('sha256').update(bytes).digest('hex') };
  fs.writeFileSync(output, JSON.stringify(result, null, 2) + '\n', { flag: 'wx' });
  console.log(JSON.stringify(result, null, 2));
} finally {
  db.close();
}
