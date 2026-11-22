import { env } from 'cloudflare:workers';
import { describe, expect, it } from 'vitest';
import { accountRoute, requireAccount } from '../src/accounts';
import { accountAdmin } from '../src/account_admin';
import { terminalInput } from '../src/account_terminals';
import { signedInRequest } from './account-fixture';

const owner = { email: 'owner@example.test', role: 'owner' as const };
const terminal = { installationId: 'a'.repeat(32), platform: 'android', versionName: '1.0.91', versionCode: 117,
  model: 'Test phone', osVersion: 'Android test' };
async function client() {
  const seed = await signedInRequest('https://example.test/api/public/latest');
  const account = await requireAccount(seed, env);
  seed.headers.set('Content-Type', 'application/json');
  const call = (path: string, body?: object) => accountRoute(new Request('https://example.test/api/account/' + path,
    { headers: seed.headers, method: body ? 'POST' : 'GET', body: body ? JSON.stringify(body) : undefined }), env);
  return { account, call, uid: seed.headers.get('X-Device-Uid')! };
}
const admin = (path: string, body?: object, actor = owner) => accountAdmin(new Request('https://admin.test/api/admin/accounts' + path,
  { method: body ? 'POST' : 'GET', headers: { 'Content-Type': 'application/json' }, body: body ? JSON.stringify(body) : undefined }), env, actor);

describe('account terminal relationships', () => {
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
