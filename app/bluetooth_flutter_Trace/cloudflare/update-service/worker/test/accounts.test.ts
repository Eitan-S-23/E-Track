import { env } from 'cloudflare:workers';
import { describe, expect, it } from 'vitest';
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
    expect((await accountBudget(env.DB, a, limits, time)).manual.used).toBe(5);
    expect((await accountBudget(env.DB, a, limits, time)).automatic.used).toBe(5);
    for (const kind of ['manual', 'automatic']) {
      await expect(accountCheck(request(kind), env.DB, a, limits, noUpdate, time)).rejects.toMatchObject({ code: 'CHECK_QUOTA_EXCEEDED' });
    }
    await accountCheck(request(), env.DB, a, limits, noUpdate, base + 86400000);
  });
  it('enforces the automatic minimum interval account-wide, but not on manual checks', async () => {
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
    expect((await accountBudget(env.DB, a, limits)).manual.used).toBe(5);
  });
  it('does not charge failed requests, and can retry the same ID', async () => {
    const a = await seed(), req = request();
    await accountCheck(req, env.DB, a, limits, async () => Response.json({ errorCode: 'CHANNEL_STOPPED' }));
    expect((await accountBudget(env.DB, a, limits)).manual.used).toBe(0);
    await expect(accountCheck(req, env.DB, a, limits, async () => { throw new Error('offline'); })).rejects.toThrow('offline');
    await accountCheck(req, env.DB, a, limits, noUpdate);
    expect((await accountBudget(env.DB, a, limits)).manual.used).toBe(1);
  });
  it('replays without charging, but rejects a changed kind/request', async () => {
    const a = await seed(), id = crypto.randomUUID();
    await accountCheck(request('manual', id), env.DB, a, limits, noUpdate);
    await accountCheck(request('manual', id), env.DB, a, limits, async () => { throw new Error('must not execute'); });
    await expect(accountCheck(request('automatic', id), env.DB, a, limits, noUpdate)).rejects.toMatchObject({ code: 'IDEMPOTENCY_CONFLICT' });
    expect((await accountBudget(env.DB, a, limits)).manual.used).toBe(1);
  });
  it('renews prepared download URLs without charging or changing the payload', async () => {
    const a = await seed(), id = crypto.randomUUID();
    await accountCheck(request('manual', id), env.DB, a, limits, latest());
    const refresh = request('manual', id, { 'X-Update-Refresh': '1' });
    await accountCheck(refresh, env.DB, a, limits, latest('a'.repeat(64), 'renewed'));
    await expect(accountCheck(refresh, env.DB, a, limits, latest('c'.repeat(64)))).rejects.toMatchObject({ code: 'IDEMPOTENCY_CONFLICT' });
    expect((await accountBudget(env.DB, a, limits)).manual.used).toBe(1);
  });
  it('does not share quota between accounts', async () => {
    const a = await seed(), b = await seed();
    for (let i = 0; i < 5; i++) await accountCheck(request(), env.DB, a, limits, noUpdate);
    await accountCheck(request(), env.DB, b, limits, noUpdate);
    expect((await accountBudget(env.DB, b, limits)).manual.remaining).toBe(4);
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
    expect((await accountBudget(env.DB, other.id, limits)).manual.used).toBe(0);
    headers.set('Authorization', ownerRequest.headers.get('Authorization')!);
    expect((await accountCloudAccess(new Request(otherRequest, { headers }), env, next)).status).toBe(200);
    expect(calls).toBe(1);
    const owner = await requireAccount(ownerRequest, env);
    expect((await accountBudget(env.DB, owner.id, limits)).manual.used).toBe(1);
  });
});
