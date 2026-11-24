// 只读推演：计算 worktree 目录对应的分片哈希，并校验恢复前提
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

const ROOT = 'C:\\Users\\SU\\.cc-connect';
const WT = 'D:\\github\\my\\E-Track-p2-5-20260801';
const SID = 'c50d9c49-cc65-45c1-9495-8d3701ed955e';

const h = crypto.createHash('sha256').update(WT).digest('hex').slice(0, 8);
console.log('worktree      : ' + WT);
console.log('分片哈希      : ' + h);
console.log('目标分片文件  : sessions/agent-claude_' + h + '.json');

const target = path.join(ROOT, 'sessions', 'agent-claude_' + h + '.json');
console.log('该文件已存在? : ' + fs.existsSync(target) + '   <- false 表示新建，不会覆盖任何东西');

// 是否与现有任何分片撞名
const all = fs.readdirSync(path.join(ROOT, 'sessions'));
console.log('同哈希其它项目: ' + (all.filter(f => f.includes(h)).join(', ') || '(无)'));

// 转录是否存在（resume 的硬前提）
const enc = WT.split(':').join('-').split('\\').join('-');
const tdir = path.join('C:\\Users\\SU\\.claude\\projects', enc);
const tfile = path.join(tdir, SID + '.jsonl');
console.log('\n转录目录      : ' + tdir);
console.log('目录存在?     : ' + fs.existsSync(tdir));
console.log('转录文件存在? : ' + fs.existsSync(tfile));
if (fs.existsSync(tfile)) {
  const st = fs.statSync(tfile);
  console.log('转录大小/时间 : ' + st.size + ' B  ' + st.mtime.toISOString());
}

// worktree 目录本身是否还在
console.log('\nworktree 存在? : ' + fs.existsSync(WT));

// 源数据 s4
const src = JSON.parse(fs.readFileSync(path.join(ROOT, 'sessions', 'agent-claude_aed1f9ff.json'), 'utf8'));
const s4 = src.sessions.s4;
console.log('\ns4.agent_session_id : ' + s4.agent_session_id);
console.log('s4 与转录 ID 一致?  : ' + (s4.agent_session_id === SID));
console.log('s4 历史消息条数     : ' + (s4.history ? s4.history.length : 0));
