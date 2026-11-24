// 只读探针：暴力匹配 cc-connect 会话分片文件名中的 8 位哈希对应的输入
// 用途：定位 sessions/<project>_<hash>.json 的 hash 是由什么字段计算的
const fs = require('fs');
const crypto = require('crypto');
const path = require('path');

const ROOT = 'C:\\Users\\SU\\.cc-connect';

const known = new Set(
  fs.readdirSync(path.join(ROOT, 'sessions'))
    .map(f => (f.match(/_([0-9a-f]{8})\.json$/) || [])[1])
    .filter(Boolean)
);

// 候选输入 1：工作目录（来自 dir_history.json，外加崩溃会话所在的 worktree）
const dh = JSON.parse(fs.readFileSync(path.join(ROOT, 'dir_history.json'), 'utf8'));
const candidates = new Set();
for (const k of Object.keys(dh)) for (const p of dh[k]) candidates.add(p);
candidates.add('D:\\github\\my\\E-Track-p2-5-20260801');
candidates.add('D:\\github\\my\\E-Track');

// 候选输入 2：chat id / user id / session key（从各分片的 user_meta 收集）
for (const f of fs.readdirSync(path.join(ROOT, 'sessions'))) {
  let j;
  try { j = JSON.parse(fs.readFileSync(path.join(ROOT, 'sessions', f), 'utf8')); } catch { continue; }
  for (const key of Object.keys(j.user_meta || {})) {
    candidates.add(key);
    const parts = key.split(':');
    for (const p of parts) candidates.add(p);
    if (parts.length >= 3) candidates.add(parts[1] + ':' + parts[2]);
  }
  for (const key of Object.keys(j.user_sessions || {})) candidates.add(key);
}

function variants(p) {
  const s = new Set([p, p.toLowerCase(), p.toUpperCase()]);
  for (const v of [...s]) {
    s.add(v.split('\\').join('/'));
    s.add(v.split('/').join('\\'));
  }
  for (const v of [...s]) { s.add(v + '\\'); s.add(v + '/'); }
  return [...s];
}

const algs = ['md5', 'sha1', 'sha256', 'sha512'];
const hits = new Set();
for (const c of candidates) {
  for (const v of variants(c)) {
    for (const a of algs) {
      const full = crypto.createHash(a).update(v).digest('hex');
      for (const slice of [full.slice(0, 8), full.slice(-8)]) {
        if (known.has(slice)) hits.add(`${slice}  ${a.padEnd(7)}  ${JSON.stringify(v)}`);
      }
    }
  }
}

console.log('known hashes  : ' + known.size);
console.log('candidates    : ' + candidates.size);
console.log('--- matches ---');
console.log(hits.size ? [...hits].sort().join('\n') : 'NO MATCH');
