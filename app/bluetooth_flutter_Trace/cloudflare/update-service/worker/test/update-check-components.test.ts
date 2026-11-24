import { env } from 'cloudflare:workers';
import { applyD1Migrations } from 'cloudflare:test';
import { describe, expect, it, vi } from 'vitest';
import { accountBudget, accountCheck, accountDay, automaticSpacingMs } from '../src/account_quota';
import { accountCloudAccess, accountRoute, accountSettings, requireAccount } from '../src/accounts';
import { accountAdmin } from '../src/account_admin';
import { sha256Hex } from '../src/crypto';
import { signedInRequest } from './account-fixture';
import worker from '../src/index';
import { onRequest as publicRequest } from '../../public/functions/[[path]]';

type Component = 'app' | 'firmware';
const components: Component[] = ['app', 'firmware'];
const limits = { automatic_daily_limit: 5, manual_daily_limit: 5,
  firmware_automatic_daily_limit: 5, firmware_manual_daily_limit: 5 };
const urls = {
  app: 'https://example.com/api/public/latest?appId=trace&platform=android&channel=stable&versionCode=120&schemaVersion=2&capabilities=full',
  firmware: 'https://example.com/api/public/firmware/latest?versionCode=30348',
};
const noUpdate = () => Promise.resolve(Response.json({ updateAvailable: false, errorCode: 'NO_UPDATE' }));
function check(component: Component, kind = 'automatic', id: string = crypto.randomUUID()) {
  return new Request(urls[component], { headers: { 'X-Update-Check-Id': id, 'X-Update-Check-Kind': kind } });
}
async function customer() {
  const request = await signedInRequest(check('app', 'manual'));
  return { id: (await requireAccount(request, env)).id, request };
}
function authenticated(from: Request, component: Component, kind = 'automatic') {
  const headers = new Headers(from.headers);
  headers.set('X-Update-Check-Id', crypto.randomUUID());
  headers.set('X-Update-Check-Kind', kind);
  if (component === 'app') headers.delete('X-Device-Uid');
  return new Request(urls[component], { headers });
}

describe('independent update check components', () => {
  it.each(components)('automatic intervals remain independent when %s checks first', async first => {
    const other = first === 'app' ? 'firmware' : 'app';
    const { id } = await customer(), now = Date.now();
    expect((await accountCheck(check(first), env.DB, id, limits, noUpdate, now)).status).toBe(200);
    await expect(accountCheck(check(other), env.DB, id, limits, noUpdate, now + 10))
      .resolves.toMatchObject({ status: 200 });
    await expect(accountCheck(check(first), env.DB, id, limits, noUpdate, now + 20))
      .rejects.toMatchObject({ code: 'CHECK_TOO_SOON' });
    await expect(accountCheck(check(other), env.DB, id, limits, noUpdate, now + 20))
      .rejects.toMatchObject({ code: 'CHECK_TOO_SOON' });
  });

  it.each(components)('exhausting %s leaves the other component and both kinds independent', async first => {
    const other = first === 'app' ? 'firmware' : 'app';
    const { id } = await customer(), base = Date.parse('2026-11-25T00:00:00Z');
    for (let index = 0; index < 5; index++) {
      const now = base + index * automaticSpacingMs;
      await accountCheck(check(first), env.DB, id, limits, noUpdate, now);
      await accountCheck(check(first, 'manual'), env.DB, id, limits, noUpdate, now);
    }
    const now = base + 5 * automaticSpacingMs;
    for (const kind of ['automatic', 'manual']) {
      await expect(accountCheck(check(first, kind), env.DB, id, limits, noUpdate, now))
        .rejects.toMatchObject({ code: 'CHECK_QUOTA_EXCEEDED' });
      await expect(accountCheck(check(other, kind), env.DB, id, limits, noUpdate, now))
        .resolves.toMatchObject({ status: 200 });
    }
    expect(await accountBudget(env.DB, id, limits, now)).toMatchObject({ components: {
      [first]: { automatic: { used: 5, remaining: 0 }, manual: { used: 5, remaining: 0 } },
      [other]: { automatic: { used: 1, remaining: 4 }, manual: { used: 1, remaining: 4 } },
    } });
  });

  it.each(components)('a pending %s lease does not reserve the other automatic budget', async first => {
    const other = first === 'app' ? 'firmware' : 'app';
    const { id } = await customer(), now = Date.now();
    let enter!: () => void, release!: () => void;
    const entered = new Promise<void>(resolve => { enter = resolve; });
    const released = new Promise<void>(resolve => { release = resolve; });
    const waiting = accountCheck(check(first), env.DB, id, limits, async () => {
      enter(); await released; return noUpdate();
    }, now);
    await entered;
    try {
      await expect(accountCheck(check(other), env.DB, id, limits, noUpdate, now + 10))
        .resolves.toMatchObject({ status: 200 });
      await expect(accountCheck(check(first), env.DB, id, limits, noUpdate, now + 10))
        .rejects.toMatchObject({ code: 'CHECK_TOO_SOON' });
    } finally { release(); await waiting; }
  });

  it.each(components)('the %s burst limiter cannot block the other component', async first => {
    const other = first === 'app' ? 'firmware' : 'app';
    const { request } = await customer();
    expect((await accountCloudAccess(authenticated(request, first), env, noUpdate)).status).toBe(200);
    for (let index = 1; index < 12; index++) {
      await expect(accountCloudAccess(authenticated(request, first), env, noUpdate))
        .rejects.toMatchObject({ code: 'CHECK_TOO_SOON' });
    }
    await expect(accountCloudAccess(authenticated(request, first), env, noUpdate))
      .rejects.toMatchObject({ code: 'RATE_LIMITED' });
    await expect(accountCloudAccess(authenticated(request, other), env, noUpdate))
      .resolves.toMatchObject({ status: 200 });
  });

  it.each(components)('the trusted %s route determines its budget without a new client header', async component => {
    const { id } = await customer();
    const request = check(component, 'manual');
    const headers = new Headers(request.headers);
    headers.set('X-Update-Check-Component', component === 'app' ? 'firmware' : 'app');
    const response = await accountCheck(new Request(request, { headers }), env.DB, id, limits, noUpdate);
    expect(response.headers.get('X-Update-Check-Component')).toBe(component);
    expect(await accountBudget(env.DB, id, limits)).toMatchObject({ components: {
      [component]: { manual: { used: 1, remaining: 4 } },
      [component === 'app' ? 'firmware' : 'app']: { manual: { used: 0, remaining: 5 } },
    } });
  });

  it('supports independently configured APP and firmware automatic/manual limits', async () => {
    const { id } = await customer(), base = Date.parse('2026-11-25T00:00:00Z');
    const separate = { automatic_daily_limit: 1, manual_daily_limit: 2,
      firmware_automatic_daily_limit: 2, firmware_manual_daily_limit: 3 };
    await accountCheck(check('app'), env.DB, id, separate, noUpdate, base);
    for (let index = 0; index < 2; index++) {
      await accountCheck(check('firmware'), env.DB, id, separate, noUpdate, base + index * automaticSpacingMs);
      await accountCheck(check('app', 'manual'), env.DB, id, separate, noUpdate, base);
    }
    for (let index = 0; index < 3; index++) {
      await accountCheck(check('firmware', 'manual'), env.DB, id, separate, noUpdate, base);
    }
    expect(await accountBudget(env.DB, id, separate, base + 2 * automaticSpacingMs)).toMatchObject({ components: {
      app: { automatic: { limit: 1, used: 1 }, manual: { limit: 2, used: 2 } },
      firmware: { automatic: { limit: 2, used: 2 }, manual: { limit: 3, used: 3 } },
    } });
    for (const component of components) for (const kind of ['automatic', 'manual']) {
      await expect(accountCheck(check(component, kind), env.DB, id, separate, noUpdate, base + 2 * automaticSpacingMs))
        .rejects.toMatchObject({ code: 'CHECK_QUOTA_EXCEEDED' });
    }
  });

  it('disabling firmware checks does not disable APP checks', async () => {
    const { id } = await customer();
    const separate = { ...limits, firmware_automatic_daily_limit: 0, firmware_manual_daily_limit: 0 };
    await expect(accountCheck(check('firmware'), env.DB, id, separate, noUpdate))
      .rejects.toMatchObject({ code: 'CHECK_QUOTA_EXCEEDED' });
    await expect(accountCheck(check('app'), env.DB, id, separate, noUpdate))
      .resolves.toMatchObject({ status: 200 });
  });

  it('concurrent manual reservations independently cap both components at five', async () => {
    const { id } = await customer();
    const results = await Promise.all(components.map(component => Promise.allSettled(
      Array.from({ length: 12 }, () => accountCheck(check(component, 'manual'), env.DB, id, limits, noUpdate)))));
    for (const result of results) expect(result.filter(value => value.status === 'fulfilled')).toHaveLength(5);
    expect(await accountBudget(env.DB, id, limits)).toMatchObject({ components: {
      app: { manual: { used: 5, remaining: 0 }, automatic: { used: 0 } },
      firmware: { manual: { used: 5, remaining: 0 }, automatic: { used: 0 } },
    } });
  });

  it('keeps the installed APP account fields as APP aliases, not combined totals', async () => {
    const { id, request } = await customer();
    await accountCheck(check('firmware', 'manual'), env.DB, id, limits, noUpdate);
    const response = await accountRoute(new Request('https://example.com/api/account/me', { headers: request.headers }), env);
    expect(await response.json()).toMatchObject({ quota: {
      component: 'app', manual: { used: 0, remaining: 5 },
      components: { app: { manual: { used: 0 } }, firmware: { manual: { used: 1, remaining: 4 } } },
    } });
  });

  it.each(['Worker', 'Public Pages'])('old APP requests work through %s after a firmware automatic check', async runtime => {
    const { request } = await customer();
    await accountCloudAccess(authenticated(request, 'firmware'), env, noUpdate);
    const appRequest = authenticated(request, 'app');
    expect(appRequest.headers.has('X-Update-Check-Component')).toBe(false);
    const response = runtime === 'Worker' ? await worker.fetch(appRequest, env)
      : await publicRequest({ request: appRequest, env: { ...env, ASSETS: { fetch: async () => new Response('asset') } },
        params: {}, data: {}, functionPath: '/', waitUntil() {}, passThroughOnException() {},
        next: async () => new Response('asset') } as Parameters<typeof publicRequest>[0]);
    expect(response.status).toBe(200);
    expect(await response.json()).toMatchObject({ updateAvailable: false, errorCode: 'NO_UPDATE' });
    expect(response.headers.get('X-Update-Check-Component')).toBe('app');
  });
});

describe('component rollout preservation', () => {
  it('preserves old records and copies configured limits without inventing their component', async () => {
    const at = env.TEST_MIGRATIONS.findIndex(migration => migration.name.startsWith('0020_update_check_components'));
    expect(at).toBeGreaterThan(0);
    const db = env.PREFLIGHT_LEGACY_DB;
    await applyD1Migrations(db, env.TEST_MIGRATIONS.slice(0, at));
    const id = crypto.randomUUID(), now = Date.now();
    await db.prepare('UPDATE account_settings SET automatic_daily_limit=3,manual_daily_limit=7 WHERE app_id=?')
      .bind(env.APP_ID).run();
    await db.prepare('INSERT INTO accounts(id,app_id,username,display_name,password_hash,created_at) VALUES(?,?,?,?,?,?)')
      .bind(id, env.APP_ID, id, id, '', now).run();
    await db.prepare(`INSERT INTO account_update_checks(account_id,check_id,day,kind,request_hash,state,created_at,
      lease_until,lease_token,response_status,response_json) VALUES(?,?,?,?,?,?,?,?,?,?,?)`)
      .bind(id, crypto.randomUUID(), accountDay(now).day, 'automatic', 'preserved-request-hash', 'complete', now,
        now + 120000, 'preserved-lease', 200, '{"updateAvailable":false,"errorCode":"NO_UPDATE"}').run();
    const before = await db.prepare('SELECT * FROM account_update_checks WHERE account_id=?').bind(id).first();
    await applyD1Migrations(db, env.TEST_MIGRATIONS.slice(at));
    const after = await db.prepare('SELECT * FROM account_update_checks WHERE account_id=?').bind(id).first();
    expect(after).toEqual({ ...before, component: 'legacy' });
    expect(await db.prepare('SELECT * FROM account_settings WHERE app_id=?').bind(env.APP_ID).first())
      .toMatchObject({ automatic_daily_limit: 3, manual_daily_limit: 7,
        firmware_automatic_daily_limit: 3, firmware_manual_daily_limit: 7 });
    expect(await accountBudget(db, id, limits, now)).toMatchObject({
      components: { app: { automatic: { used: 0 } }, firmware: { automatic: { used: 0 } } },
      unclassifiedLegacyChecks: { automatic: 1, manual: 0 },
    });
  });

  it('identifies a legacy row only when its original request is replayed exactly', async () => {
    const { id } = await customer(), request = check('app', 'manual'), now = Date.now();
    const url = new URL(request.url); url.searchParams.sort();
    const hash = await sha256Hex(url.pathname + url.search + '|');
    await env.DB.prepare(`INSERT INTO account_update_checks(account_id,check_id,day,kind,request_hash,state,
      created_at,lease_until,lease_token,response_status,response_json) VALUES(?,?,?,?,?,?,?,?,?,?,?)`)
      .bind(id, request.headers.get('X-Update-Check-Id'), accountDay(now).day, 'manual', hash, 'complete', now,
        now + 120000, 'legacy-lease', 200, '{"updateAvailable":false,"errorCode":"NO_UPDATE"}').run();
    const next = vi.fn(noUpdate);
    const response = await accountCheck(request, env.DB, id, limits, next, now);
    expect(next).not.toHaveBeenCalled();
    expect(response.headers.get('X-Update-Check-Component')).toBe('app');
    expect(await env.DB.prepare('SELECT component FROM account_update_checks WHERE account_id=? AND check_id=?')
      .bind(id, request.headers.get('X-Update-Check-Id')).first()).toEqual({ component: 'app' });
  });

  it('rejects a different route reusing a legacy request ID without relabelling it', async () => {
    const { id } = await customer(), original = check('firmware', 'manual'), now = Date.now();
    const url = new URL(original.url); url.searchParams.sort();
    const hash = await sha256Hex(url.pathname + url.search + '|');
    await env.DB.prepare(`INSERT INTO account_update_checks(account_id,check_id,day,kind,request_hash,state,
      created_at,lease_until,lease_token,response_status,response_json) VALUES(?,?,?,?,?,?,?,?,?,?,?)`)
      .bind(id, original.headers.get('X-Update-Check-Id'), accountDay(now).day, 'manual', hash, 'complete', now,
        now + 120000, 'legacy-lease', 200, '{"updateAvailable":false,"errorCode":"NO_UPDATE"}').run();
    await expect(accountCheck(check('app', 'manual', original.headers.get('X-Update-Check-Id')!), env.DB, id, limits, noUpdate, now))
      .rejects.toMatchObject({ code: 'IDEMPOTENCY_CONFLICT' });
    expect(await env.DB.prepare('SELECT component FROM account_update_checks WHERE account_id=? AND check_id=?')
      .bind(id, original.headers.get('X-Update-Check-Id')).first()).toEqual({ component: 'legacy' });
  });

  it('preserves firmware settings when an older Admin saves APP-only limits', async () => {
    const before = await accountSettings(env);
    const post = (body: object) => new Request('https://admin.example.com/api/admin/accounts/settings', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
    });
    try {
      const result = await accountAdmin(post({ ...before, automatic_daily_limit: 2, manual_daily_limit: 3,
        firmware_automatic_daily_limit: 7, firmware_manual_daily_limit: 8 }), env,
      { email: 'owner@example.test', role: 'owner' });
      expect(await result.json()).toMatchObject({ settings: { automatic_daily_limit: 2, manual_daily_limit: 3,
        firmware_automatic_daily_limit: 7, firmware_manual_daily_limit: 8 } });
      const current = await accountSettings(env);
      const old = { registration_enabled: current.registration_enabled,
        password_registration_enabled: current.password_registration_enabled,
        email_verification_enabled: current.email_verification_enabled, revision: current.revision,
        automatic_daily_limit: 4, manual_daily_limit: 6 };
      expect(await (await accountAdmin(post(old), env, { email: 'owner@example.test', role: 'owner' })).json())
        .toMatchObject({ settings: { automatic_daily_limit: 4, manual_daily_limit: 6,
          firmware_automatic_daily_limit: 7, firmware_manual_daily_limit: 8 } });
    } finally {
      await env.DB.prepare(`UPDATE account_settings SET automatic_daily_limit=?,manual_daily_limit=?,
        firmware_automatic_daily_limit=?,firmware_manual_daily_limit=?,revision=? WHERE app_id=?`)
        .bind(before.automatic_daily_limit, before.manual_daily_limit,
          before.firmware_automatic_daily_limit ?? before.automatic_daily_limit,
          before.firmware_manual_daily_limit ?? before.manual_daily_limit, before.revision, env.APP_ID).run();
    }
  });

  it.each([-1, 1001, 1.5, '5', null])('rejects invalid firmware limits %s before mutating settings', async invalid => {
    const before = await accountSettings(env);
    const request = new Request('https://admin.example.com/api/admin/accounts/settings', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...before, firmware_automatic_daily_limit: invalid }),
    });
    await expect(accountAdmin(request, env, { email: 'owner@example.test', role: 'owner' }))
      .rejects.toMatchObject({ code: 'INVALID_PARAMETER' });
    expect(await accountSettings(env)).toEqual(before);
  });

  it('keeps the independent firmware controls owner-only', async () => {
    const before = await accountSettings(env);
    const request = new Request('https://admin.example.com/api/admin/accounts/settings', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...before, firmware_automatic_daily_limit: 1 }),
    });
    await expect(accountAdmin(request, env, { email: 'viewer@example.test', role: 'viewer' }))
      .rejects.toMatchObject({ code: 'ACCOUNT_DISABLED', status: 403 });
    expect(await accountSettings(env)).toEqual(before);
  });
});
