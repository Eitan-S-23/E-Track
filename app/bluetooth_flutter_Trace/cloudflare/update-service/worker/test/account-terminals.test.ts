import { env } from 'cloudflare:workers';
import { describe, expect, it } from 'vitest';
import { accountAuthRoute, accountRoute, requireAccount } from '../src/accounts';
import { accountAdmin } from '../src/account_admin';
import { saveTerminal, terminalInput } from '../src/account_terminals';
import { sha256Hex } from '../src/crypto';
import { signedInRequest } from './account-fixture';

const owner = { email: 'owner@example.test', role: 'owner' as const };
const terminal = { installationId: 'a'.repeat(32), platform: 'android', versionName: '1.0.91', versionCode: 117,
  model: 'Test phone', osVersion: 'Android test' };
let addressSequence = 0;
const address = () => '192.0.2.' + ++addressSequence;
const sessionAddresses = new Map<string, string>();
async function client() {
  const seed = await signedInRequest('https://example.test/api/public/latest', { headers: { 'CF-Connecting-IP': address() } });
  const account = await requireAccount(seed, env);
  seed.headers.set('Content-Type', 'application/json');
  const call = (path: string, body?: object) => accountRoute(new Request('https://example.test/api/account/' + path,
    { headers: seed.headers, method: body ? 'POST' : 'GET', body: body ? JSON.stringify(body) : undefined }), env);
  return { account, call, uid: seed.headers.get('X-Device-Uid')! };
}
const admin = (path: string, body?: object, actor = owner) => accountAdmin(new Request('https://admin.test/api/admin/accounts' + path,
  { method: body ? 'POST' : 'GET', headers: { 'Content-Type': 'application/json' }, body: body ? JSON.stringify(body) : undefined }), env, actor);

const accountCall = (token: string, path: string, body?: object) => {
  if (!sessionAddresses.has(token)) sessionAddresses.set(token, address());
  return accountRoute(new Request('https://example.test/api/account/' + path,
    { headers: { Authorization: 'Bearer ' + token, 'Content-Type': 'application/json', 'CF-Connecting-IP': sessionAddresses.get(token)! },
      method: body ? 'POST' : 'GET', body: body ? JSON.stringify(body) : undefined }), env);
};
async function extraSession(accountId: string, installationId: string, options: { expiresAt?: number; revokedAt?: number; createdAt?: number } = {}) {
  const token = 'acct_' + crypto.randomUUID().replaceAll('-', '') + crypto.randomUUID().replaceAll('-', '');
  const id = crypto.randomUUID().replaceAll('-', ''), now = Date.now();
  await env.DB.prepare(`INSERT INTO account_sessions(token_hash,account_id,session_id,installation_id,created_at,expires_at,revoked_at)
    VALUES(?,?,?,?,?,?,?)`).bind(await sha256Hex(token), accountId, id, installationId,
    options.createdAt ?? now, options.expiresAt ?? now + 86400000, options.revokedAt ?? null).run();
  return { id, call: (path: string, body?: object) => accountCall(token, path, body) };
}
type Connections = { terminals: Array<{ installationId: string; model: string; state: string; current: number;
  activeSessionCount: number; sessionCount: number; lastLoginAt: number | null }>;
  sessions: Array<{ current: number; installationId: string | null }>; onlineState: string };

describe('account terminal relationships', () => {
  it('logout and real relogin retain one installation and separate login history', async () => {
    const username = 'rider_' + crypto.randomUUID().replaceAll('-', '').slice(0, 16), password = 'test-password';
    const ip = address();
    const auth = (path: string, body: object) => accountAuthRoute(new Request('https://example.test/api/auth/' + path,
      { method: 'POST', headers: { 'Content-Type': 'application/json', 'CF-Connecting-IP': ip }, body: JSON.stringify(body) }), env);
    await auth('register', { username, password });
    const first = await (await auth('login', { username, password, terminal })).json() as { token: string };
    await accountCall(first.token, 'logout', {});
    const second = await (await auth('login', { username, password, terminal })).json() as { token: string; account: { id: string } };
    const result = await (await accountCall(second.token, 'sessions')).json() as Connections;
    expect(result.terminals).toHaveLength(1); expect(result.sessions).toHaveLength(2);
    expect(result.terminals[0]).toMatchObject({ installationId: terminal.installationId, state: 'valid', current: 1,
      activeSessionCount: 1, sessionCount: 2 });
    const events = await env.DB.prepare('SELECT COUNT(*) AS count FROM account_login_events WHERE account_id=?')
      .bind(second.account.id).first<{ count: number }>();
    expect(events?.count).toBe(2); expect(result.onlineState).toBe('unknown');
  });
  it('keeps identical phone models on separate installations as separate terminals', async () => {
    const a = await client(); await a.call('terminal', { terminal });
    const other = { ...terminal, installationId: 'b'.repeat(32) };
    await saveTerminal(env.DB, a.account.id, other, Date.now()).run();
    await extraSession(a.account.id, other.installationId);
    const result = await (await a.call('sessions')).json() as Connections;
    expect(result.terminals).toHaveLength(2);
    expect(new Set(result.terminals.map(row => row.installationId))).toEqual(new Set([terminal.installationId, other.installationId]));
    expect(result.terminals.map(row => row.model)).toEqual(['Test phone', 'Test phone']);
    expect(result.terminals.filter(row => row.current === 1)).toHaveLength(1);
  });
  it('terminal status and current marker aggregate beyond the 100-session history page', async () => {
    const a = await client(); await a.call('terminal', { terminal });
    const now = Date.now(), prefix = crypto.randomUUID().replaceAll('-', '');
    await env.DB.prepare('UPDATE account_sessions SET created_at=? WHERE account_id=?').bind(now - 300000, a.account.id).run();
    await env.DB.prepare(`WITH RECURSIVE n(i) AS (SELECT 1 UNION ALL SELECT i+1 FROM n WHERE i<101)
      INSERT INTO account_sessions(token_hash,account_id,session_id,installation_id,created_at,expires_at)
      SELECT ?||printf('%032x',i),?,?||printf('%016x',i),?,?+i,? FROM n`)
      .bind(prefix, a.account.id, prefix.slice(0, 16), terminal.installationId, now - 100000, now - 1000).run();
    const result = await (await a.call('sessions')).json() as Connections;
    expect(result.sessions).toHaveLength(100); expect(result.sessions.every(row => row.current === 0)).toBe(true);
    expect(result.terminals[0]).toMatchObject({ state: 'valid', current: 1, activeSessionCount: 1, sessionCount: 102,
      lastLoginAt: now - 100000 + 101 });
  });
  it('terminal revocation affects all its active sessions but no other installation or account', async () => {
    const a = await client(), b = await client();
    await a.call('terminal', { terminal }); await b.call('terminal', { terminal });
    const second = await extraSession(a.account.id, terminal.installationId);
    const other = { ...terminal, installationId: 'b'.repeat(32) };
    await saveTerminal(env.DB, a.account.id, other, Date.now()).run();
    const otherLogin = await extraSession(a.account.id, other.installationId);
    const expired = await extraSession(a.account.id, terminal.installationId, { expiresAt: Date.now() - 1000 });
    const revokedAt = Date.now() - 2000;
    const revoked = await extraSession(a.account.id, terminal.installationId, { revokedAt });
    const response = await (await a.call('sessions/revoke', { installationId: terminal.installationId })).json();
    expect(response).toEqual({ ok: true, currentRevoked: true });
    await expect(a.call('me')).rejects.toMatchObject({ code: 'LOGIN_REQUIRED' });
    await expect(second.call('me')).rejects.toMatchObject({ code: 'LOGIN_REQUIRED' });
    expect((await otherLogin.call('me')).status).toBe(200); expect((await b.call('me')).status).toBe(200);
    const history = (await env.DB.prepare('SELECT session_id,revoked_at FROM account_sessions WHERE account_id=?').bind(a.account.id).all()).results;
    expect(history).toHaveLength(5);
    expect(history.find(row => row.session_id === expired.id)?.revoked_at).toBeNull();
    expect(history.find(row => row.session_id === revoked.id)?.revoked_at).toBe(revokedAt);
    const result = await (await otherLogin.call('sessions')).json() as Connections;
    expect(result.terminals.find(row => row.installationId === terminal.installationId)).toMatchObject({ activeSessionCount: 0, state: 'expired' });
  });
  it('revoking another installation reports that the current login remains usable', async () => {
    const a = await client(); await a.call('terminal', { terminal });
    const other = await extraSession(a.account.id, 'b'.repeat(32));
    expect(await (await a.call('sessions/revoke', { installationId: 'b'.repeat(32) })).json()).toEqual({ ok: true, currentRevoked: false });
    expect((await a.call('me')).status).toBe(200);
    await expect(other.call('me')).rejects.toMatchObject({ code: 'LOGIN_REQUIRED' });
  });
  it('rejects missing, conflicting or malformed revocation selectors without mutation', async () => {
    const a = await client(); await a.call('terminal', { terminal });
    for (const body of [{}, { installationId: null }, { installationId: 'phone' },
      { installationId: terminal.installationId, sessionId: '1'.repeat(32) }]) {
      await expect(a.call('sessions/revoke', body)).rejects.toMatchObject({ code: 'INVALID_PARAMETER' });
    }
    expect((await a.call('me')).status).toBe(200);
  });
  it('an installation without retained sessions is unknown rather than online or expired', async () => {
    const a = await client();
    await saveTerminal(env.DB, a.account.id, terminal, Date.now()).run();
    const result = await (await a.call('sessions')).json() as Connections;
    expect(result.terminals[0]).toMatchObject({ state: 'unknown', current: 0, activeSessionCount: 0, sessionCount: 0, lastLoginAt: null });
    expect(result.sessions[0].installationId).toBeNull(); expect(result.onlineState).toBe('unknown');
  });
  it('keeps legacy sessions unknown instead of fabricating installation records', async () => {
    const c = await client();
    const result = await (await c.call('sessions')).json() as any;
    expect(result.terminals).toEqual([]);
    expect(result.sessions[0].installationId).toBeNull();
    expect(result.sessions[0].state).toBe('valid');
    expect(result.onlineState).toBe('unknown');
    expect(JSON.stringify(result)).not.toContain('token_hash');
  });
  it('updates one terminal per account without merging two users on one phone', async () => {
    const a = await client(), b = await client();
    await a.call('terminal', { terminal });
    await b.call('terminal', { terminal: { ...terminal, model: 'Other account phone' } });
    await a.call('terminal', { terminal: { ...terminal, versionName: '1.0.92', versionCode: 118 } });
    const detail = await (await admin('/' + a.account.id)).json() as any;
    expect(detail.terminals).toHaveLength(1);
    expect(detail.terminals[0]).toMatchObject({ versionCode: 118, model: 'Test phone' });
    expect(detail.sessions[0]).toMatchObject({ versionCode: 118, current: 0 });
    const other = await (await b.call('sessions')).json() as any;
    expect(other.terminals[0].model).toBe('Other account phone');
    await expect(a.call('terminal', { terminal: { ...terminal, installationId: 'b'.repeat(32) } }))
      .rejects.toMatchObject({ code: 'INVALID_PARAMETER' });
  });
  it('records only bound UID observations and does not consume check allowances', async () => {
    const a = await client(); await a.call('terminal', { terminal });
    await a.call('devices/observe', { firmwareVersion: 30350, imageSha256: 'b'.repeat(64) });
    const detail = await (await admin('/' + a.account.id)).json() as any;
    expect(detail.observations).toHaveLength(1);
    expect(detail.observations[0]).toMatchObject({ uid: a.uid, firmwareVersion: 30350, installationId: terminal.installationId });
    expect(detail.devices[0]).toMatchObject({ firmware_version: 30350, image_sha256: 'b'.repeat(64) });
    expect(detail.quota.manual.remaining).toBe(5);
    expect(detail.quota.automatic.remaining).toBe(5);
    await admin('/' + a.account.id + '/unbind', { uid: a.uid });
    await expect(a.call('devices/observe', { firmwareVersion: 30351, imageSha256: 'c'.repeat(64) }))
      .rejects.toMatchObject({ code: 'DEVICE_NOT_BOUND' });
    const after = await (await admin('/' + a.account.id)).json() as any;
    expect(after.devices).toEqual([]); expect(after.observations).toEqual([]);
  });
  it('supports account-scoped single-session revocation without exposing tokens', async () => {
    const a = await client(), b = await client();
    await env.DB.prepare('UPDATE account_sessions SET session_id=? WHERE account_id=?').bind('1'.repeat(32), a.account.id).run();
    await env.DB.prepare('UPDATE account_sessions SET session_id=? WHERE account_id=?').bind('2'.repeat(32), b.account.id).run();
    await a.call('sessions/revoke', { sessionId: '2'.repeat(32) });
    expect((await b.call('me')).status).toBe(200);
    await expect(admin('/' + a.account.id + '/revoke-session', { sessionId: '1'.repeat(32) },
      { email: owner.email, role: 'viewer' as any })).rejects.toMatchObject({ status: 403 });
    await admin('/' + a.account.id + '/revoke-session', { sessionId: '1'.repeat(32) });
    await expect(a.call('me')).rejects.toMatchObject({ code: 'LOGIN_REQUIRED' });
    expect((await b.call('me')).status).toBe(200);
  });
  it('offers bounded global account/terminal/device lookup and accurate version filtering', async () => {
    const a = await client(); await a.call('terminal', { terminal });
    const result = await (await admin('/terminals?q=' + a.account.username)).json() as any;
    expect(result.rows).toHaveLength(1); expect(result.rows[0].accountId).toBe(a.account.id);
    const devices = await (await admin('/devices?q=' + a.uid)).json() as any;
    expect(devices.rows).toHaveLength(1); expect(devices.rows[0].uid).toBe(a.uid);
    expect(devices.onlineState).toBe('unknown');
    await expect(admin('/terminals?page=0')).rejects.toMatchObject({ code: 'INVALID_PARAMETER' });
    await expect(admin('/devices?q=' + 'a'.repeat(65))).rejects.toMatchObject({ code: 'INVALID_PARAMETER' });
  });
  it('validates bounded metadata and leaves absent metadata absent', () => {
    expect(terminalInput(undefined)).toBeNull();
    for (const value of [null, [], { ...terminal, model: 'a'.repeat(81) }, { ...terminal, osVersion: '\n' },
      { ...terminal, versionCode: -1 }, { ...terminal, installationId: 'not-an-id' }]) {
      expect(() => terminalInput(value)).toThrow();
    }
  });
});
