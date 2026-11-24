// 从会话 transcript 提取本批 lib 文件 Edit 的 old/new 摘要（仅用于 §6.11 记录重建）。
const fs = require('fs');
const path = require('path');
const tdir = 'C:/Users/SU/.claude/projects/D--github-my-E-Track';
const tfile = path.join(tdir, '499df32d-653e-4229-ac5f-2fdc104c5c68.jsonl');
const lines = fs.readFileSync(tfile, 'utf8').split('\n').filter(Boolean);
const targets = [
  'ota_ble_transport.dart',
  'ota_service.dart',
  'ota_upgrade_page.dart',
  'bluetooth_service.dart',
  'ota_download.dart',
];
const which = process.argv[2] || 'lib';
for (const line of lines) {
  let obj;
  try { obj = JSON.parse(line); } catch { continue; }
  const msg = obj.type === 'assistant' ? obj.message : null;
  if (!msg || !Array.isArray(msg.content)) continue;
  for (const b of msg.content) {
    if (b.type !== 'tool_use' || b.name !== 'Edit') continue;
    const fp = (b.input && b.input.file_path) || '';
    const hit = targets.some((t) => fp.replace(/\\/g, '/').includes(t));
    if (which === 'lib' ? !hit : hit) continue;
    const short = fp.replace(/\\/g, '/').split('E-Track/')[1] || fp;
    const oldS = (b.input.old_string || '').replace(/\s+/g, ' ').slice(0, 100);
    const newS = (b.input.new_string || '').replace(/\s+/g, ' ').slice(0, 170);
    console.log('== ' + short);
    console.log('  OLD: ' + oldS);
    console.log('  NEW: ' + newS);
  }
}
