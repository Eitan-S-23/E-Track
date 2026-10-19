const io = require('./io.cjs');
const { spawnSync } = require('node:child_process');
function createHttp(label) {
  io.assert.match(label, /^[a-z0-9-]+$/);
  const slots = Array.from({ length: 24 }, (_, i) => ({
    body: io.reserve(label + '/' + String(i + 1).padStart(2, '0') + '.body'),
    headers: io.reserve(label + '/' + String(i + 1).padStart(2, '0') + '.headers'),
  }));
  const env = io.environment(); env.CURL_HOME = env.HOME;
  let sequence = 0;
  return async function http(url, options, receipts) {
    const parsed = new URL(url);
    io.assert.ok(['https://api.cloudflare.com', 'https://api.github.com'].includes(parsed.origin));
    io.assert.ok(!parsed.username && !parsed.password);
    const files = slots[sequence++]; io.assert.ok(files, 'HTTP request budget exhausted');
    for (const file of Object.values(files)) { io.guard(file); io.fs.mkdirSync(io.path.dirname(file), { recursive: true }); io.guard(file); }
    const method = options.method || 'GET';
    const lines = ['url = ' + JSON.stringify(url)];
    for (const [key, value] of Object.entries(options.headers || {})) lines.push('header = ' + JSON.stringify(key + ': ' + value));
    if (options.body !== undefined) lines.push('data = ' + JSON.stringify(options.body));
    const receipt = { method, origin: parsed.origin, path: parsed.pathname, transport: 'curl-verified-TLS-config-stdin',
      startedAt: new Date().toISOString(), bodyPath: files.body, headersPath: files.headers };
    receipts.push(receipt);
    const result = spawnSync('curl.exe', ['--disable', '--config', '-', '--silent', '--show-error', '--proto', '=https',
      '--request', method, '--connect-timeout', '15', '--max-time', '60', '--max-filesize', '4194304',
      '--output', files.body, '--dump-header', files.headers, '--write-out', '%{http_code}'],
    { cwd: io.base, env, input: lines.join('\n') + '\n', encoding: 'utf8', windowsHide: true, timeout: 70000, maxBuffer: 1024 * 1024 });
    const bytes = io.fs.existsSync(files.body) ? io.fs.readFileSync(files.body) : Buffer.alloc(0);
    const rawHeaders = io.fs.existsSync(files.headers) ? io.fs.readFileSync(files.headers, 'utf8') : '';
    Object.assign(receipt, { endedAt: new Date().toISOString(), exitCode: result.status, signal: result.signal,
      status: Number(result.stdout?.trim()), bytes: bytes.length, sha256: io.sha256(bytes), stderr: io.redact(result.stderr || '') });
    io.assert.ok(!result.error && result.status === 0, 'Curl transport failed; retain output and reconcile without write retry');
    const finalHeaders = rawHeaders.trim().split(/\r?\n\r?\n/).at(-1).split(/\r?\n/).slice(1);
    const headers = Object.fromEntries(finalHeaders.map(line => { const colon = line.indexOf(':'); return [line.slice(0, colon).toLowerCase(), line.slice(colon + 1).trim()]; }));
    receipt.requestId = headers['x-github-request-id'] || headers['cf-ray'];
    let json; try { json = JSON.parse(bytes); } catch { /* Worker module bodies are binary multipart. */ }
    return { status: receipt.status, bytes, headers, json };
  };
}
module.exports = { createHttp };
