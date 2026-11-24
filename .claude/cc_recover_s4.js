// s4 会话恢复脚本
// 目标：让 D:\github\my\E-Track（当前工作目录）下能 /list 到并续聊原 s4 会话
//
// 动作（全部先备份、原子写、不覆盖已存在文件）：
//   1. 备份 aed1f9ff（原始证据）与 b54d0747（目标分片）到项目内 .claude/cc-recover-backup/
//   2. 复制 s4 转录 jsonl 到 D--github-my-E-Track 转录目录，使 resume 能在当前目录命中
//   3. 把 s4 作为新会话写入 b54d0747（当前目录分片）——用户目标路径
//   4. 另建 8253d923（worktree 目录分片）作为保底，防止步骤 3 被 cc-connect 内存覆盖
const fs = require('fs');
const path = require('path');

const CC = 'C:\\Users\\SU\\.cc-connect';
const SESS = path.join(CC, 'sessions');
const PROJ = 'C:\\Users\\SU\\.claude\\projects';
const BK = 'D:\\github\\my\\E-Track\\.claude\\cc-recover-backup';

const SID = 'c50d9c49-cc65-45c1-9495-8d3701ed955e';
const SRC = 'agent-claude_aed1f9ff.json';      // s4 所在（cc-connect 目录分片）
const DST = 'agent-claude_b54d0747.json';      // E-Track 目录分片（用户目标）
const FALLBACK = 'agent-claude_8253d923.json'; // worktree 目录分片（保底）
const UKEY = 'feishu:oc_23045f1c11957bfd57a7bef1b0d520ff:ou_69e906c4a18a121d8dff16571d9e8de1';
const NAME = 'P2-5验收(恢复)';

const rd = f => JSON.parse(fs.readFileSync(f, 'utf8'));
// 原子写：临时文件 + rename，避免断电产生截断 JSON（正是本次 bug 的次要缺陷）
function atomicWrite(f, obj) {
  const tmp = f + '.recover-tmp';
  fs.writeFileSync(tmp, JSON.stringify(obj, null, 2), 'utf8');
  fs.renameSync(tmp, f);
}

fs.mkdirSync(BK, { recursive: true });
const log = [];

// ---- 1. 备份 ----
for (const f of [SRC, DST]) {
  const p = path.join(SESS, f);
  if (fs.existsSync(p)) {
    fs.copyFileSync(p, path.join(BK, f + '.bak'));
    log.push(`备份  ${f} -> .claude/cc-recover-backup/${f}.bak`);
  }
}

// ---- 取出 s4 ----
const s4 = rd(path.join(SESS, SRC)).sessions.s4;
if (s4.agent_session_id !== SID) throw new Error('s4 的 agent_session_id 与预期不符，中止');
log.push(`读取  s4  history=${s4.history.length} 条  sid=${SID}`);

// ---- 2. 复制转录，使当前目录可 resume ----
const dstDir = path.join(PROJ, 'D--github-my-E-Track');
const dstJsonl = path.join(dstDir, SID + '.jsonl');
const srcJsonl = path.join(PROJ, 'D--github-my-E-Track-p2-5-20260801', SID + '.jsonl');
if (fs.existsSync(dstJsonl)) {
  log.push('跳过  转录已存在，未覆盖');
} else {
  fs.copyFileSync(srcJsonl, dstJsonl);
  log.push(`复制  转录 -> D--github-my-E-Track/${SID}.jsonl (${fs.statSync(dstJsonl).size} B)`);
}

// ---- 写入辅助：把 s4 插入某个分片 ----
function inject(file, createIfMissing) {
  const p = path.join(SESS, file);
  let store;
  if (fs.existsSync(p)) {
    store = rd(p);
  } else if (createIfMissing) {
    store = { sessions: {}, active_session: {}, user_sessions: {}, counter: 0,
              user_meta: {}, past_id_tracking: true, version: 1 };
  } else {
    log.push(`跳过  ${file} 不存在`); return null;
  }
  store.sessions = store.sessions || {};
  store.user_sessions = store.user_sessions || {};
  store.active_session = store.active_session || {};
  store.user_meta = store.user_meta || {};

  // 幂等：已存在同 agent_session_id 则不重复插入
  const dup = Object.keys(store.sessions).find(k => store.sessions[k].agent_session_id === SID);
  if (dup) { log.push(`跳过  ${file} 已含该会话 (${dup})`); return dup; }

  const id = 's' + ((store.counter || 0) + 1);
  store.sessions[id] = { ...s4, id, name: NAME };
  store.counter = (store.counter || 0) + 1;
  store.user_sessions[UKEY] = [...(store.user_sessions[UKEY] || []), id];
  if (!store.user_meta[UKEY]) {
    store.user_meta[UKEY] = { user_name: UKEY.split(':')[2], chat_name: UKEY.split(':')[1] };
  }
  atomicWrite(p, store);
  log.push(`写入  ${file}  新会话 ${id}  counter=${store.counter}`);
  return id;
}

// ---- 3. 目标分片（当前目录）----
const idMain = inject(DST, false);
// ---- 4. 保底分片（worktree 目录）----
const idFb = inject(FALLBACK, true);

console.log(log.join('\n'));
console.log('\n=== 结果 ===');
console.log('当前目录分片 b54d0747 会话号 : ' + idMain);
console.log('保底分片   8253d923 会话号 : ' + idFb);
