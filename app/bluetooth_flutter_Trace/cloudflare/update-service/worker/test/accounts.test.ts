import { env } from 'cloudflare:workers';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { accountBudget, accountCheck, accountDay, automaticSpacingMs } from '../src/account_quota';
import { accountAuthRoute, accountRoute, accountCloudAccess, requireAccount, hashAccountPassword } from '../src/accounts';
import { accountAdmin } from '../src/account_admin';
import { signedInRequest } from './account-fixture';
import worker from '../src/index';
import { onRequest as publicRequest } from '../../public/functions/[[path]]';

const limits = { automatic_daily_limit: 5, manual_daily_limit: 5 };
async function seed() {
  const id = crypto.randomUUID();
  await env.DB.prepare('INSERT INTO accounts(id,app_id,username,display_name,password_hash,created_at) VALUES(?,?,?,?,?,?)')
    .bind(id, env.APP_ID, id, id, '', Date.now()).run();
  return id;
}
function request(kind = 'manual', id = crypto.randomUUID(), headers: Record<string, string> = {}) {
  return new Request('https://example.com/api/public/firmware/latest?versionCode=30348', {
    headers: { 'X-Update-Check-Id': id, 'X-Update-Check-Kind': kind, ...headers }
  });
}
const noUpdate = () => Promise.resolve(Response.json({ updateAvailable: false, errorCode: 'NO_UPDATE' }));
const latest = (sha = 'a'.repeat(64), token = 'first') => async () => Response.json({
  updateAvailable: true, versionCode: 30349, releaseId: 'release1', targetImageSha256: 'b'.repeat(64),
  asset: { assetId: 'asset1', kind: 'full', sha256: sha, sizeBytes: 500, downloadUrl: 'https://example.com/' + token }
});

describe('account check allowance', () => {
  it('uses the server Shanghai day across midnight', () => {
    expect(accountDay(Date.parse('2026-11-22T15:59:59Z')).day).toBe('2026-11-22');
    expect(accountDay(Date.parse('2026-11-22T16:00:00Z')).day).toBe('2026-11-23');
    expect(accountDay(Date.parse('2026-11-22T12:00:00Z')).resetsAt).toBe(Date.parse('2026-11-22T16:00:00Z'));
  });
  it('allows five manual and five separately-spaced automatic checks, not six', async () => {
    const a = await seed(), base = Date.parse('2026-11-22T00:00:00Z');
    for (let i = 0; i < 5; i++) {
      await accountCheck(request(), env.DB, a, limits, noUpdate, base + i * automaticSpacingMs);
      await accountCheck(request('automatic'), env.DB, a, limits, noUpdate, base + i * automaticSpacingMs);
    }
    const time = base + 5 * automaticSpacingMs;
    expect((await accountBudget(env.DB, a, limits, time)).components.firmware.manual.used).toBe(5);
    expect((await accountBudget(env.DB, a, limits, time)).components.firmware.automatic.used).toBe(5);
    for (const kind of ['manual', 'automatic']) {
      await expect(accountCheck(request(kind), env.DB, a, limits, noUpdate, time)).rejects.toMatchObject({ code: 'CHECK_QUOTA_EXCEEDED' });
    }
    await accountCheck(request(), env.DB, a, limits, noUpdate, base + 86400000);
  });
  it('enforces the automatic minimum interval account-wide within a component, but not on manual checks', async () => {
    const a = await seed(), now = Date.now();
    await accountCheck(request('automatic'), env.DB, a, limits, noUpdate, now);
    await expect(accountCheck(request('automatic'), env.DB, a, limits, noUpdate, now + 10)).rejects.toMatchObject({ code: 'CHECK_TOO_SOON' });
    await accountCheck(request(), env.DB, a, limits, noUpdate, now + 10);
    await accountCheck(request('automatic'), env.DB, a, limits, noUpdate, now + automaticSpacingMs);
  });
  it('atomically caps simultaneous requests from multiple phones at five', async () => {
    const a = await seed();
    const results = await Promise.allSettled(Array.from({ length: 12 }, () => accountCheck(request(), env.DB, a, limits, noUpdate)));
    expect(results.filter(r => r.status === 'fulfilled')).toHaveLength(5);
    expect((await accountBudget(env.DB, a, limits)).components.firmware.manual.used).toBe(5);
  });
  it('does not charge failed requests, and can retry the same ID', async () => {
    const a = await seed(), req = request();
    await accountCheck(req, env.DB, a, limits, async () => Response.json({ errorCode: 'CHANNEL_STOPPED' }));
    expect((await accountBudget(env.DB, a, limits)).components.firmware.manual.used).toBe(0);
    await expect(accountCheck(req, env.DB, a, limits, async () => { throw new Error('offline'); })).rejects.toThrow('offline');
    await accountCheck(req, env.DB, a, limits, noUpdate);
    expect((await accountBudget(env.DB, a, limits)).components.firmware.manual.used).toBe(1);
  });
  it('replays without charging, but rejects a changed kind/request', async () => {
    const a = await seed(), id = crypto.randomUUID();
    await accountCheck(request('manual', id), env.DB, a, limits, noUpdate);
    await accountCheck(request('manual', id), env.DB, a, limits, async () => { throw new Error('must not execute'); });
    await expect(accountCheck(request('automatic', id), env.DB, a, limits, noUpdate)).rejects.toMatchObject({ code: 'IDEMPOTENCY_CONFLICT' });
    expect((await accountBudget(env.DB, a, limits)).components.firmware.manual.used).toBe(1);
  });
  it('renews prepared download URLs without charging or changing the payload', async () => {
    const a = await seed(), id = crypto.randomUUID();
    await accountCheck(request('manual', id), env.DB, a, limits, latest());
    const refresh = request('manual', id, { 'X-Update-Refresh': '1' });
    await accountCheck(refresh, env.DB, a, limits, latest('a'.repeat(64), 'renewed'));
    await expect(accountCheck(refresh, env.DB, a, limits, latest('c'.repeat(64)))).rejects.toMatchObject({ code: 'IDEMPOTENCY_CONFLICT' });
    expect((await accountBudget(env.DB, a, limits)).components.firmware.manual.used).toBe(1);
  });
  it('does not share quota between accounts', async () => {
    const a = await seed(), b = await seed();
    for (let i = 0; i < 5; i++) await accountCheck(request(), env.DB, a, limits, noUpdate);
    await accountCheck(request(), env.DB, b, limits, noUpdate);
    expect((await accountBudget(env.DB, b, limits)).components.firmware.manual.remaining).toBe(4);
  });
});

describe('account admission', () => {
  it('denies anonymous cloud access at both Worker and public Pages, before query or download', async () => {
    for (const path of ['latest', 'firmware/latest', 'firmware/download', 'download', 'github-fallback', 'announcements', 'version-inventory/control', 'feedback']) {
      const req = new Request('https://example.com/api/public/' + path);
      expect((await worker.fetch(req, env)).status).toBe(401);
      expect((await publicRequest({ request: req, env: { ...env, ASSETS: { fetch: async () => new Response('asset') } },
        params: {}, data: {}, functionPath: '/', waitUntil() {}, passThroughOnException() {},
        next: async () => new Response('asset') } as Parameters<typeof publicRequest>[0])).status).toBe(401);
    }
  });
  it('hashes passwords with independent salts through the production password routine', async () => {
    const a = await hashAccountPassword('test-password-123');
    const b = await hashAccountPassword('test-password-123');
    expect(a).toMatch(/^scrypt\$16384\$8\$5\$/);
    expect(a).not.toBe(b);
    expect(a).not.toContain('test-password');
  });
  it('registers, logs in, stores only a token hash, and revokes disabled-account sessions', async () => {
    const username = 'u' + crypto.randomUUID().replaceAll('-', '').slice(0, 20);
    const post = (path: string, body: object) => new Request('https://example.com/api/auth/' + path,
      { method: 'POST', headers: { 'Content-Type': 'application/json', 'CF-Connecting-IP': '192.0.2.' + Math.floor(Math.random() * 200) }, body: JSON.stringify(body) });
    expect((await accountAuthRoute(post('register', { username, password: 'test-password-123' }), env)).status).toBe(201);
    const response = await accountAuthRoute(post('login', { username, password: 'test-password-123' }), env);
    const value = await response.json() as { token: string; account: { id: string } };
    const req = new Request('https://example.com/api/account/me', { headers: { Authorization: 'Bearer ' + value.token } });
    expect((await requireAccount(req, env)).id).toBe(value.account.id);
    const session = await env.DB.prepare('SELECT token_hash FROM account_sessions WHERE account_id=?').bind(value.account.id).first<{ token_hash: string }>();
    expect(session?.token_hash).not.toBe(value.token);
    const state = new Request('https://admin.example.com/api/admin/accounts/' + value.account.id + '/state', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ state: 'disabled' }) });
    await accountAdmin(state, env, { email: 'owner@example.com', role: 'owner' });
    await expect(requireAccount(req, env)).rejects.toMatchObject({ code: 'LOGIN_REQUIRED' });
  });
  it('enforces disabled registration on the server', async () => {
    await env.DB.prepare('UPDATE account_settings SET registration_enabled=0 WHERE app_id=?').bind(env.APP_ID).run();
    try {
      await expect(accountAuthRoute(new Request('https://example.com/api/auth/register', {
        method: 'POST', headers: { 'Content-Type': 'application/json', 'CF-Connecting-IP': '192.0.2.251' },
        body: JSON.stringify({ username: 'closed', password: 'test-password-123' }) }), env)).rejects.toMatchObject({ code: 'REGISTRATION_DISABLED' });
    } finally { await env.DB.prepare('UPDATE account_settings SET registration_enabled=1 WHERE app_id=?').bind(env.APP_ID).run(); }
  });
  it('binds a UID once and blocks other accounts before cloud checks or OTA authorization', async () => {
    const ownerRequest = await signedInRequest(request());
    const otherRequest = await signedInRequest(request());
    const uid = crypto.randomUUID().replaceAll('-', '').slice(0, 24);
    const device = { uid, confirmed: true, name: 'Rider device', model: 'e-track-at32f435',
      hardwareRevision: 1, firmwareVersion: 30349, imageSha256: 'b'.repeat(64) };
    const operation = (from: Request, path: string, body: object) => new Request('https://example.com/api/account/' + path, {
      method: 'POST', headers: { Authorization: from.headers.get('Authorization')!,
        'Content-Type': 'application/json', 'X-Device-Uid': uid }, body: JSON.stringify(body),
    });
    expect((await accountRoute(operation(ownerRequest, 'devices/bind', device), env)).status).toBe(200);
    await expect(accountRoute(operation(otherRequest, 'devices/bind', device), env))
      .rejects.toMatchObject({ code: 'DEVICE_ALREADY_BOUND' });
    expect((await accountRoute(operation(ownerRequest, 'ota/authorize', {}), env)).status).toBe(200);
    await expect(accountRoute(operation(otherRequest, 'ota/authorize', {}), env))
      .rejects.toMatchObject({ code: 'DEVICE_NOT_BOUND' });
    let calls = 0;
    const next = () => { calls++; return noUpdate(); };
    const headers = new Headers(otherRequest.headers);
    headers.set('X-Device-Uid', uid);
    await expect(accountCloudAccess(new Request(otherRequest, { headers }), env, next))
      .rejects.toMatchObject({ code: 'DEVICE_NOT_BOUND' });
    expect(calls).toBe(0);
    const other = await requireAccount(otherRequest, env);
    expect((await accountBudget(env.DB, other.id, limits)).components.firmware.manual.used).toBe(0);
    headers.set('Authorization', ownerRequest.headers.get('Authorization')!);
    expect((await accountCloudAccess(new Request(otherRequest, { headers }), env, next)).status).toBe(200);
    expect(calls).toBe(1);
    const owner = await requireAccount(ownerRequest, env);
    expect((await accountBudget(env.DB, owner.id, limits)).components.firmware.manual.used).toBe(1);
    expect((await accountBudget(env.DB, owner.id, limits)).manual.used).toBe(0);
  });
});

describe('account verification email', () => {
  const mailEnv = () => ({ ...env, ACCOUNT_MAIL_API_KEY: 'fixture-mail-key', ACCOUNT_MAIL_FROM: 'E-Track <mail@example.test>' });
  const address = () => crypto.randomUUID() + '@example.test';
  const post = (path: string, body: object) => new Request('https://example.com/api/auth/' + path, {
    method: 'POST', headers: { 'Content-Type': 'application/json', 'CF-Connecting-IP': crypto.randomUUID() },
    body: JSON.stringify(body),
  });
  afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); });
  function mailbox() {
    const messages: Array<{ text: string; html: string; subject: string; to: string[]; from: string }> = [];
    const transport = vi.fn(async (_url: unknown, options: RequestInit) => {
      expect(String(_url)).toBe('https://api.resend.com/emails');
      expect(options.redirect).toBe('error');
      expect(new Headers(options.headers).get('Idempotency-Key')).toMatch(/^[a-z0-9-]{36}$/);
      messages.push(JSON.parse(String(options.body)));
      return Response.json({ id: crypto.randomUUID() });
    });
    vi.stubGlobal('fetch', transport);
    return { messages, transport, code: () => /code is (\d{6})/.exec(messages.at(-1)!.text)![1] };
  }
  it('reports configuration without exposing secrets, and refuses sends when unconfigured', async () => {
    const box = mailbox();
    const status = await accountAuthRoute(new Request('https://example.com/api/auth/status'), env);
    expect(await status.json()).toMatchObject({ emailDeliveryAvailable: false, passwordResetAvailable: false });
    await expect(accountAuthRoute(post('email-code', { email: address(), purpose: 'register' }), env))
      .rejects.toMatchObject({ code: 'EMAIL_DELIVERY_UNAVAILABLE', status: 503 });
    const configured = mailEnv();
    const settings = await accountAdmin(new Request('https://example.com/api/admin/accounts/settings'), configured, { email: 'owner@example.test', role: 'owner' });
    const text = await settings.text();
    expect(JSON.parse(text).emailDeliveryAvailable).toBe(true);
    expect(text).not.toContain(configured.ACCOUNT_MAIL_API_KEY);
    expect(text).not.toContain(configured.ACCOUNT_MAIL_FROM);
    expect(box.transport).not.toHaveBeenCalled();
  });
  it('sends a one-use registration code with text/HTML and stores only its hash', async () => {
    const box = mailbox(), email = address(), configured = mailEnv();
    const response = await accountAuthRoute(post('email-code', { email, purpose: 'register' }), configured);
    const sent = await response.json() as { verificationId: string; expiresIn: number };
    const code = box.code();
    expect(sent.expiresIn).toBe(600); expect(JSON.stringify(sent)).not.toContain(code);
    expect(box.messages[0]).toMatchObject({ to: [email], from: configured.ACCOUNT_MAIL_FROM });
    expect(box.messages[0].html).toContain(code); expect(box.messages[0].subject).toContain('registration');
    const stored = await env.DB.prepare('SELECT code_hash,expires_at,created_at FROM account_email_codes WHERE id=?')
      .bind(sent.verificationId).first<{ code_hash: string; expires_at: number; created_at: number }>();
    expect(stored!.code_hash).toMatch(/^[a-f0-9]{64}$/); expect(stored!.code_hash).not.toBe(code);
    expect(stored!.expires_at - stored!.created_at).toBe(600000);
    await env.DB.prepare('UPDATE account_settings SET email_verification_enabled=1 WHERE app_id=?').bind(env.APP_ID).run();
    const body = { username: 'u' + crypto.randomUUID().replaceAll('-', '').slice(0,20), email,
      verificationId: sent.verificationId, code, password: 'test-password-123' };
    try {
      expect((await accountAuthRoute(post('register', body), configured)).status).toBe(201);
      await expect(accountAuthRoute(post('register', body), configured)).rejects.toMatchObject({ code: 'EMAIL_VERIFICATION_REQUIRED' });
    } finally { await env.DB.prepare('UPDATE account_settings SET email_verification_enabled=0 WHERE app_id=?').bind(env.APP_ID).run(); }
  });
  it.each(['rejected', 'network', 'timeout'])('invalidates orphan codes on %s send failure without leaking provider data', async kind => {
    const email = address();
    vi.stubGlobal('fetch', vi.fn(async () => {
      if (kind === 'rejected') return new Response('private provider diagnostic', { status: 403 });
      throw new Error(kind + ': fixture-mail-key');
    }));
    await expect(accountAuthRoute(post('email-code', { email, purpose: 'register' }), mailEnv()))
      .rejects.toMatchObject({ code: 'EMAIL_DELIVERY_FAILED', status: 502,
        message: 'Verification email was not confirmed; request a new code later' });
    expect((await env.DB.prepare('SELECT COUNT(*) AS n FROM account_email_codes WHERE email=?').bind(email).first<{ n: number }>())!.n).toBe(0);
  });
  it('limits resends per mailbox across purposes without sending a duplicate', async () => {
    const box = mailbox(), email = address(), configured = mailEnv();
    await accountAuthRoute(post('email-code', { email, purpose: 'register' }), configured);
    await expect(accountAuthRoute(post('email-code', { email, purpose: 'reset' }), configured))
      .rejects.toMatchObject({ code: 'EMAIL_SEND_COOLDOWN', status: 429 });
    expect(box.transport).toHaveBeenCalledTimes(1);
  });
  it('does not send to or identify an unknown reset account', async () => {
    const box = mailbox();
    const response = await accountAuthRoute(post('email-code', { email: address(), purpose: 'reset' }), mailEnv());
    expect(await response.json()).toMatchObject({ ok: true, expiresIn: 600 });
    expect(box.transport).not.toHaveBeenCalled();
  });
  it('resets a real account only for its code and revokes existing sessions', async () => {
    const box = mailbox(), email = address(), configured = mailEnv();
    const username = 'u' + crypto.randomUUID().replaceAll('-', '').slice(0,20);
    await accountAuthRoute(post('register', { username, email, password: 'test-password-123' }), configured);
    const login = await accountAuthRoute(post('login', { username, password: 'test-password-123' }), configured);
    const old = await login.json() as { token: string };
    const sent = await (await accountAuthRoute(post('email-code', { email, purpose: 'reset' }), configured)).json() as { verificationId: string };
    const body = { email, verificationId: sent.verificationId, code: box.code(), password: 'new-password-456' };
    await expect(accountAuthRoute(post('reset-password', { ...body, email: address() }), configured))
      .rejects.toMatchObject({ code: 'EMAIL_VERIFICATION_REQUIRED' });
    expect((await accountAuthRoute(post('reset-password', body), configured)).status).toBe(200);
    await expect(requireAccount(new Request('https://example.com/api/account/me', { headers: { Authorization: 'Bearer ' + old.token } }), configured))
      .rejects.toMatchObject({ code: 'LOGIN_REQUIRED' });
    await expect(accountAuthRoute(post('login', { username, password: 'test-password-123' }), configured))
      .rejects.toMatchObject({ code: 'INVALID_CREDENTIALS' });
    expect((await accountAuthRoute(post('login', { username, password: body.password }), configured)).status).toBe(200);
  });
});
