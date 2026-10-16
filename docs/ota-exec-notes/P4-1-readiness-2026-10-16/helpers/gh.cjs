const fs = require('node:fs');
const path = require('node:path');
const cp = require('node:child_process');
const root = fs.realpathSync.native(path.resolve(__dirname, '..'));
const gh = 'C:/Program Files/GitHub CLI/gh.exe';
const [label, operation, ...args] = process.argv.slice(2);
if (!/^[a-z0-9-]+$/.test(label || '')) throw Error('Invalid label');
const branch = 'dev/p4-1/unattended-20261015';
function check(value) {
  const target = path.resolve(root, value);
  let a = target;
  while (!fs.existsSync(a)) a = path.dirname(a);
  const real = path.resolve(fs.realpathSync.native(a), path.relative(a, target));
  const r = path.relative(root, real);
  if (r === '..' || r.startsWith('..' + path.sep) || path.isAbsolute(r)) throw Error('outside worktree');
  for (let p = a; p !== path.dirname(p); p = path.dirname(p)) if (fs.lstatSync(p).isSymbolicLink()) throw Error('reparse');
  return target;
}
async function main() {
  const tokenRead = cp.spawnSync(gh, ['auth', 'token', '--hostname', 'github.com', '--user', 'Eitan-S-23'],
    { cwd: root, encoding: 'utf8', windowsHide: true });
  if (tokenRead.status !== 0 || !tokenRead.stdout.trim()) throw Error('Expected GitHub credential unavailable');
  const token = tokenRead.stdout.trim();
  if (operation === 'artifact') {
    if (!/^repos\/Eitan-S-23\/E-Track\/actions\/artifacts\/[1-9][0-9]*\/zip$/.test(args[0] || '')) throw Error('Unauthorized artifact');
    const output = check(`.cache/github/${label}.zip`);
    if (fs.existsSync(output)) throw Error('Output exists');
    const env = { ...process.env, GH_TOKEN: token, GH_HOST: 'github.com',
      GH_PROMPT_DISABLED: '1', GH_NO_UPDATE_NOTIFIER: '1' };
    for (const [key, value] of Object.entries({ TEMP: 'tmp', TMP: 'tmp', TMPDIR: 'tmp', HOME: 'home',
      USERPROFILE: 'home', APPDATA: 'appdata', LOCALAPPDATA: 'localappdata', GH_CONFIG_DIR: 'config/gh' })) {
      env[key] = check('.cache/runtime/' + value);
      fs.mkdirSync(env[key], { recursive: true });
    }
    const identity = await fetch('https://api.github.com/user', {
      headers: { Authorization: `Bearer ${token}`, Accept: 'application/vnd.github+json' },
      signal: AbortSignal.timeout(30000) });
    if (!identity.ok || (await identity.json()).login !== 'Eitan-S-23') throw Error('Artifact identity check failed');
    const redirect = await fetch('https://api.github.com/' + args[0], {
      headers: { Authorization: `Bearer ${token}`, Accept: 'application/vnd.github+json' },
      redirect: 'manual', signal: AbortSignal.timeout(30000) });
    if (redirect.status !== 302) throw Error('Artifact redirect unavailable: ' + redirect.status);
    const location = new URL(redirect.headers.get('location'));
    if (location.protocol !== 'https:' || !location.hostname.endsWith('.blob.core.windows.net')) throw Error('Unexpected artifact host');
    const curlEnv = { ...env };
    for (const name of Object.keys(curlEnv)) if (/^(CLOUDFLARE_|CF_|TRACE_|GH_|GITHUB_TOKEN|OTA_)/.test(name)) delete curlEnv[name];
    const result = cp.spawnSync('curl.exe', ['--config', '-', '--silent', '--show-error', '--fail',
      '--proto', '=https', '--noproxy', '*', '--connect-timeout', '30', '--max-time', '300', '--max-filesize', '16777216'],
      { cwd: root, env: curlEnv, input: `url = "${location.href}"\n`, windowsHide: true,
        timeout: 310000, maxBuffer: 16 * 1024 * 1024 });
    if (result.error || result.status !== 0) {
      process.stderr.write(JSON.stringify({ operation, exitCode: result.status, causeCode: result.error?.code,
        error: result.stderr?.toString().replace(/https?:\/\/\S+/g, '[REDACTED_DOWNLOAD_URL]') }) + '\n');
      process.exitCode = 1;
      return;
    }
    fs.mkdirSync(check('.cache/github'), { recursive: true });
    fs.writeFileSync(output, result.stdout, { flag: 'wx' });
    process.stdout.write(JSON.stringify({ identity: 'Eitan-S-23', transport: 'curl-artifact-direct-https', output, bytes: result.stdout.length }) + '\n');
    return;
  }
  const headers = { Authorization: `Bearer ${token}`, Accept: 'application/vnd.github+json',
    'X-GitHub-Api-Version': '2022-11-28' };
  const identity = await fetch('https://api.github.com/user', { headers, signal: AbortSignal.timeout(30000) });
  if (!identity.ok || (await identity.json()).login !== 'Eitan-S-23') throw Error('Wrong GitHub identity');
  const dir = check('.cache/github');
  const output = check(`.cache/github/${label}.${operation === 'logs' || operation === 'artifact' ? 'zip' : 'json'}`);
  if (fs.existsSync(output)) throw Error('Output exists');
  fs.mkdirSync(dir, { recursive: true });
  if (operation === 'draft-pr') {
    const body = check(args[0]);
    if (!fs.statSync(body).isFile()) throw Error('PR body file missing');
    const env = { ...process.env, GH_TOKEN: token, GH_HOST: 'github.com',
      GH_PROMPT_DISABLED: '1', GH_NO_UPDATE_NOTIFIER: '1', GIT_TERMINAL_PROMPT: '0',
      GIT_OPTIONAL_LOCKS: '0' };
    for (const [key, value] of Object.entries({ TEMP: 'tmp', TMP: 'tmp', TMPDIR: 'tmp', HOME: 'home',
      USERPROFILE: 'home', APPDATA: 'appdata', LOCALAPPDATA: 'localappdata', GH_CONFIG_DIR: 'config/gh' })) {
      env[key] = check('.cache/runtime/' + value);
      fs.mkdirSync(env[key], { recursive: true });
    }
    const result = cp.spawnSync(gh, ['pr', 'create', '--repo', 'Eitan-S-23/E-Track',
      '--draft', '--no-maintainer-edit', '--base', 'main', '--head', branch,
      '--title', 'P4-1: verified release-chain development candidate', '--body-file', body],
      { cwd: root, env, encoding: 'utf8', windowsHide: true, timeout: 120000 });
    const data = { identity: 'Eitan-S-23', branch, operation: 'draft-pr', exitCode: result.status,
      stdout: result.stdout, stderr: result.stderr };
    fs.writeFileSync(output, JSON.stringify(data, null, 2) + '\n', { flag: 'wx' });
    process.stdout.write(JSON.stringify(data) + '\n');
    process.exitCode = result.status ?? 1;
    return;
  }
  if (operation === 'push') {
    const env = { ...process.env, GIT_TERMINAL_PROMPT: '0', GIT_CONFIG_COUNT: '1',
      GIT_CONFIG_KEY_0: 'http.https://github.com/.extraheader',
      GIT_CONFIG_VALUE_0: 'AUTHORIZATION: basic ' + Buffer.from(`x-access-token:${token}`).toString('base64') };
    for (const key of ['TEMP', 'TMP', 'TMPDIR']) env[key] = check('.cache/runtime/tmp');
    const result = cp.spawnSync('git', ['-c', 'core.hooksPath=NUL', '-c', 'credential.helper=', '-c', 'gc.auto=0',
      'push', 'https://github.com/Eitan-S-23/E-Track.git', `HEAD:refs/heads/${branch}`],
      { cwd: root, env, encoding: 'utf8', windowsHide: true, timeout: 120000 });
    const data = { identity: 'Eitan-S-23', branch, exitCode: result.status, stdout: result.stdout, stderr: result.stderr };
    fs.writeFileSync(output, JSON.stringify(data, null, 2) + '\n', { flag: 'wx' });
    process.stdout.write(JSON.stringify(data) + '\n');
    process.exitCode = result.status ?? 1;
    return;
  }
  let endpoint = args[0];
  let init = { headers, signal: AbortSignal.timeout(operation === 'artifact' ? 300000 : 120000) };
  if (operation === 'dispatch') {
    if (!['firmware-build.yml', 'cloudflare-update-service.yml'].includes(endpoint)) throw Error('workflow not authorized');
    init = { ...init, method: 'POST', body: JSON.stringify({ ref: branch,
      inputs: endpoint === 'firmware-build.yml' ? { publish: 'false', rehearsal: 'false', version_name: '3.2.7' } : {} }) };
    endpoint = `repos/Eitan-S-23/E-Track/actions/workflows/${endpoint}/dispatches`;
  } else {
    const currentRepository = endpoint === 'repos/Eitan-S-23/E-Track' || endpoint.startsWith('repos/Eitan-S-23/E-Track/');
    const relatedSourceRead = operation === 'get' && [
      'repos/Eitan-S-23/Trace', 'repos/Eitan-S-23/Trace/releases?per_page=100',
      'repos/Eitan-S-23/Trace/tags?per_page=100',
      'repos/Eitan-S-23/Trace/git/matching-refs/tags/mcu-e-track-at32f435-v'
    ].includes(endpoint);
    if (!['get', 'logs', 'artifact'].includes(operation) || (!currentRepository && !relatedSourceRead)) throw Error('Unauthorized operation');
  }
  const response = await fetch(`https://api.github.com/${endpoint}`, init);
  const bytes = Buffer.from(await response.arrayBuffer());
  fs.writeFileSync(output, bytes.length ? bytes : JSON.stringify({ status: response.status, branch }), { flag: 'wx' });
  process.stdout.write(JSON.stringify({ identity: 'Eitan-S-23', status: response.status, output, bytes: bytes.length }) + '\n');
  if (!response.ok) { process.stderr.write(bytes + '\n'); process.exitCode = 1; }
}
main().catch(error => { process.stderr.write(JSON.stringify({ error: error.message, causeCode: error.cause?.code }) + '\n'); process.exitCode = 1; });
