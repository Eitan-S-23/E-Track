// Development host adapter: real commands, file stdio instead of denied pipes.
const fs = require('node:fs'), path = require('node:path'), cp = require('node:child_process');
const assert = require('node:assert/strict');
const root = path.resolve(__dirname, '../../..');
const host = path.join(__dirname, 'host');
const native = cp.spawnSync;
let calls = 0;
cp.spawnSync = function(command, args, options = {}) {
  if (options.stdio) return native(command, args, options);
  assert(['fsutil.exe', 'git'].includes(command), 'HOST_STDIO_COMMAND');
  assert.equal(path.resolve(options.cwd || root), root);
  if (command === 'fsutil.exe') assert.deepEqual(args.slice(0, 2), ['reparsepoint', 'query']);
  else assert(args.includes('--no-optional-locks'), 'HOST_GIT_READ_ONLY');
  const files = ['stdout.tmp', 'stderr.tmp'].map(name => path.join(host, name));
  for (const file of files) {
    for (let current = file; current !== path.dirname(current); current = path.dirname(current)) {
      if (fs.existsSync(current)) assert(!fs.lstatSync(current).isSymbolicLink(), 'HOST_REPARSE');
    }
    assert.equal(fs.realpathSync(path.dirname(file)), fs.realpathSync(host));
  }
  const fds = files.map(file => fs.openSync(file, 'w'));
  let result;
  try { result = native(command, args, { ...options, timeout: options.timeout || 30000, stdio: ['ignore', ...fds] }); }
  finally { for (const fd of fds) fs.closeSync(fd); }
  const raw = files.map(file => fs.readFileSync(file));
  const decoded = options.encoding && options.encoding !== 'buffer' ? raw.map(value => value.toString(options.encoding)) : raw;
  calls++;
  return { ...result, stdout: decoded[0], stderr: decoded[1], output: [null, ...decoded] };
};
process.on('exit', () => console.log(JSON.stringify({ host_stdio_actual_commands: calls, cached_answers: 0 })));
