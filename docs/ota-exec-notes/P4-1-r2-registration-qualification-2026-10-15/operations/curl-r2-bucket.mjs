import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { spawnSync } from 'node:child_process';
import { Readable } from 'node:stream';

// Test transport only. The unchanged production uploader owns validation and replay.
export function qualificationBucket({ root, guard, directory, accountId, bucketName,
  objects, credentials, observations, redact }) {
  assert.equal(accountId, 'af6dd848e6a21f1cd26d44b1b656af7b');
  assert.equal(bucketName, 'e-track-firmware-p41-test-releases');
  assert.equal(objects.length, 3);
  for (const key of ['accessKeyId', 'secretAccessKey', 'sessionToken']) {
    assert.match(credentials[key], /^[A-Za-z0-9._~+/=-]+$/);
  }
  const env = { ...process.env };
  for (const key of Object.keys(env)) {
    if (/^(CF_|CLOUDFLARE_|GH_|GITHUB_TOKEN|TRACE_|OTA_AES_KEY|NODE_OPTIONS|NODE_COMPILE_CACHE|GIT_CONFIG|GIT_INDEX_FILE)/i.test(key)) delete env[key];
  }
  for (const [key, name] of Object.entries({ TEMP: 'tmp', TMP: 'tmp', TMPDIR: 'tmp',
    HOME: 'home', USERPROFILE: 'home', APPDATA: 'appdata', LOCALAPPDATA: 'localappdata',
    XDG_CACHE_HOME: 'cache', XDG_CONFIG_HOME: 'config', CURL_HOME: 'home' })) {
    env[key] = guard(path.join(directory, 'runtime', name));
    fs.mkdirSync(env[key], { recursive: true });
  }
  const config = ['aws-sigv4 = "aws:amz:auto:s3"',
    'user = ' + JSON.stringify(credentials.accessKeyId + ':' + credentials.secretAccessKey),
    'header = ' + JSON.stringify('X-Amz-Security-Token: ' + credentials.sessionToken)].join('\n') + '\n';
  let sequence = 0;
  const hash = bytes => createHash('sha256').update(bytes).digest('hex');
  function requestOnce(method, key, headers = {}, bytes) {
    assert.ok(objects.includes(key), 'Request outside the three authorized keys');
    assert.ok(['HEAD', 'GET', 'PUT'].includes(method));
    assert.ok(++sequence <= 60, 'Bounded qualification request limit');
    const prefix = String(sequence).padStart(3, '0') + '-' + method.toLowerCase();
    const headerPath = guard(path.join(directory, prefix + '.headers'));
    const bodyPath = guard(path.join(directory, prefix + '.body'));
    for (const output of [headerPath, bodyPath]) assert.equal(fs.existsSync(output), false);
    const args = ['--disable', '--config', '-', '--silent', '--show-error', '--proto', '=https',
      '--connect-timeout', '15', '--max-time', '45', '--max-filesize', '1048576',
      '--dump-header', headerPath, '--output', bodyPath, '--write-out', '%{http_code}'];
    if (method === 'HEAD') args.push('--head');
    else args.push('--request', method);
    if (bytes !== undefined) {
      const payload = guard(path.join(directory, prefix + '.upload'));
      assert.equal(fs.existsSync(payload), false);
      fs.writeFileSync(payload, bytes, { flag: 'wx' });
      args.push('--data-binary', '@' + payload);
    }
    for (const [name, value] of Object.entries(headers)) args.push('--header', name + ': ' + value);
    args.push(`https://${accountId}.r2.cloudflarestorage.com/${bucketName}/${key.split('/').map(encodeURIComponent).join('/')}`);
    const result = spawnSync('curl', args, { cwd: root, env, input: config, encoding: 'utf8',
      windowsHide: true, timeout: 50000, maxBuffer: 1024 * 1024 });
    const rawHeaders = fs.existsSync(headerPath) ? fs.readFileSync(headerPath, 'utf8') : '';
    const body = fs.existsSync(bodyPath) ? fs.readFileSync(bodyPath) : Buffer.alloc(0);
    const status = Number(result.stdout?.trim());
    const entry = { sequence, method, key, requestHeaders: headers, status,
      curlExitCode: result.status, pid: result.pid, processClosed: true,
      stderr: redact(result.stderr), responseHeaders: redact(rawHeaders),
      responseBodyLength: body.length, responseBodySha256: hash(body), headerPath, bodyPath };
    observations.push(entry);
    if (status === 0 && !result.error && [5, 6, 7, 28, 35, 52, 55, 56].includes(result.status)) {
      entry.networkFailureWithoutHttpResponse = true;
      return { retryable: true };
    }
    assert.equal(result.error, undefined, 'curl failed to execute');
    assert.equal(result.status, 0, 'curl transport failed; inspect the preserved receipt');
    const block = rawHeaders.trim().split(/\r?\n\r?\n/).findLast(value => /^HTTP\//.test(value));
    assert.ok(block, 'HTTP response headers missing');
    const [line, ...lines] = block.split(/\r?\n/);
    assert.equal(Number(line.split(' ')[1]), status);
    const parsed = new Headers();
    for (const line of lines) {
      const split = line.indexOf(':');
      assert.ok(split > 0);
      parsed.append(line.slice(0, split), line.slice(split + 1).trim());
    }
    return { status, headers: parsed, body, bodyPath };
  }
  function request(...args) {
    for (let attempt = 0; attempt < 3; attempt++) {
      const result = requestOnce(...args);
      if (!result.retryable) return result;
      if (attempt < 2) Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, 1000 * (attempt + 1));
    }
    throw new Error('R2 transport failed after three bounded attempts; no verified success');
  }
  function objectInfo(response) {
    const quoted = response.headers.get('etag');
    assert.match(quoted, /^"[0-9a-f]+"$/);
    const customMetadata = {};
    for (const [name, value] of response.headers) {
      if (name.startsWith('x-amz-meta-')) customMetadata[name.slice(11)] = value;
    }
    const size = Number(response.headers.get('content-length'));
    assert.ok(Number.isSafeInteger(size) && size >= 0);
    return { size, etag: quoted.slice(1, -1), httpEtag: quoted, customMetadata,
      lastModified: response.headers.get('last-modified'), httpMetadata: {
        contentType: response.headers.get('content-type'),
        contentDisposition: response.headers.get('content-disposition'),
        cacheControl: response.headers.get('cache-control') } };
  }
  return {
    async head(key) {
      const response = request('HEAD', key);
      if (response.status === 404) return null;
      assert.equal(response.status, 200, 'R2 HEAD rejected');
      return objectInfo(response);
    },
    async put(key, bytes, options) {
      assert.deepEqual(options.onlyIf, { etagDoesNotMatch: '*' });
      assert.equal(hash(bytes), options.sha256);
      const headers = Object.fromEntries(options.httpMetadata);
      assert.equal(headers['content-length'], String(bytes.byteLength));
      headers['If-None-Match'] = '*';
      headers['X-Amz-Content-Sha256'] = options.sha256;
      headers['Content-MD5'] = createHash('md5').update(bytes).digest('base64');
      for (const [name, value] of Object.entries(options.customMetadata)) headers['x-amz-meta-' + name] = value;
      const response = request('PUT', key, headers, bytes);
      if (response.status === 412) return null;
      assert.equal(response.status, 200, 'R2 conditional PUT rejected');
      return { etag: response.headers.get('etag') };
    },
    async get(key, options) {
      assert.match(options.onlyIf.etagMatches, /^[0-9a-f]+$/);
      const response = request('GET', key, { 'If-Match': '"' + options.onlyIf.etagMatches + '"' });
      if (response.status === 404) return null;
      if (response.status === 412) return {};
      assert.equal(response.status, 200, 'R2 conditional GET rejected');
      return { ...objectInfo(response), body: Readable.toWeb(fs.createReadStream(response.bodyPath)) };
    }
  };
}
