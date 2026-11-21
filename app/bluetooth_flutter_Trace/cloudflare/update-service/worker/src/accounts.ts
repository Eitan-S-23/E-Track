import { sha256Hex, timingSafeEqual } from './crypto';
import { ApiError, invalidParameter } from './errors';
import { clientIpFrom, json } from './http';
import { boundedJson } from './version_inventory';
import { accountBudget, accountCheck, type AccountLimits } from './account_quota';
import type { WorkerEnv } from './types';
import { scryptSync } from 'node:crypto';

type Env = Pick<WorkerEnv, 'DB' | 'APP_ID' | 'ACCOUNT_MAIL_API_KEY' | 'ACCOUNT_MAIL_FROM'>;
export interface AccountSettings extends AccountLimits {
  registration_enabled: number; password_registration_enabled: number;
  email_verification_enabled: number; revision: number;
}
export interface Account {
  id: string; app_id: string; username: string; display_name: string; email: string | null;
  email_verified: number; password_hash: string; state: string; created_at: number; last_login_at: number | null;
}
const encoder = new TextEncoder();
const randomHex = (bytes = 32) => Array.from(crypto.getRandomValues(new Uint8Array(bytes)), b => b.toString(16).padStart(2, '0')).join('');
const milliseconds = () => Date.now();

export async function accountSettings(env: Env): Promise<AccountSettings> {
  const settings = await env.DB.prepare('SELECT * FROM account_settings WHERE app_id=?').bind(env.APP_ID).first<AccountSettings>();
  if (!settings) throw new ApiError('BACKEND_UNAVAILABLE', 'Account migration is not installed', 503);
  return settings;
}

export function accountPublic(a: Account) {
  return { id: a.id, username: a.username, displayName: a.display_name, email: a.email,
    emailVerified: a.email_verified === 1, state: a.state, createdAt: a.created_at, lastLoginAt: a.last_login_at };
}

export function accountPassword(input: unknown): string {
  if (typeof input !== 'string' || input.length < 8 || input.length > 128 || encoder.encode(input).length > 512) {
    throw invalidParameter('Password must contain 8 to 128 characters');
  }
  return input;
}

export async function hashAccountPassword(password: string, salt = randomHex(16)): Promise<string> {
  // OWASP's 16 MiB scrypt profile avoids Workers' PBKDF2 iteration cap.
  const value = scryptSync(password, salt, 32, { N: 16384, r: 8, p: 5, maxmem: 32 * 1024 * 1024 });
  return 'scrypt$16384$8$5$' + salt + '$' + value.toString('hex');
}

async function passwordMatches(password: string, saved: string): Promise<boolean> {
  const match = /^scrypt\$16384\$8\$5\$([0-9a-f]{32})\$[0-9a-f]{64}$/.exec(saved);
  return match !== null && timingSafeEqual(await hashAccountPassword(password, match[1]), saved);
}

export async function requireAccount(request: Request, env: Env): Promise<Account> {
  const match = /^Bearer (acct_[0-9a-f]{64})$/.exec(request.headers.get('Authorization') ?? '');
  if (!match) throw new ApiError('LOGIN_REQUIRED', 'Please sign in to use cloud features', 401);
  const account = await env.DB.prepare(`SELECT a.* FROM account_sessions s JOIN accounts a ON a.id=s.account_id
    WHERE s.token_hash=? AND s.expires_at>? AND s.revoked_at IS NULL AND a.app_id=?`)
    .bind(await sha256Hex(match[1]), milliseconds(), env.APP_ID).first<Account>();
  if (!account) throw new ApiError('LOGIN_REQUIRED', 'Your session has expired; sign in again', 401);
  if (account.state !== 'active') throw new ApiError('ACCOUNT_DISABLED', 'Account is not enabled', 403);
  return account;
}

function field(body: Record<string, unknown>, key: string, pattern: RegExp): string {
  const value = body[key];
  if (typeof value !== 'string' || !pattern.test(value)) throw invalidParameter('Invalid ' + key);
  return value;
}
const emailOf = (body: Record<string, unknown>) => field(body, 'email', /^[^\s@]{1,64}@[^\s@]{1,190}\.[^\s@]{2,30}$/).toLowerCase();

async function authRate(request: Request, env: WorkerEnv, identifier = '') {
  const ip = await sha256Hex(clientIpFrom(request));
  const keys = ['ip:' + ip, ...(identifier ? ['identity:' + await sha256Hex(identifier.toLowerCase())] : [])];
  for (const key of keys) {
    const rate = await env.RATE_LIMITER.getByName('account:' + key).check('auth', 10, 60);
    if (!rate.allowed) throw new ApiError('RATE_LIMITED', 'Please wait before trying again', 429, { retryAfter: rate.retryAfter });
  }
}

async function session(env: Env, a: Account, appVersion: string): Promise<Response> {
  const token = 'acct_' + randomHex();
  const now = milliseconds(), expiresAt = now + 30 * 86400000;
  await env.DB.batch([
    env.DB.prepare('INSERT INTO account_sessions(token_hash,account_id,created_at,expires_at) VALUES(?,?,?,?)')
      .bind(await sha256Hex(token), a.id, now, expiresAt),
    env.DB.prepare('UPDATE accounts SET last_login_at=? WHERE id=?').bind(now, a.id),
    env.DB.prepare('INSERT INTO account_login_events(id,account_id,occurred_at,app_version) VALUES(?,?,?,?)')
      .bind(crypto.randomUUID(), a.id, now, appVersion.slice(0, 64))
  ]);
  return json({ ok: true, account: accountPublic({ ...a, last_login_at: now }), token, expiresAt,
    quota: await accountBudget(env.DB, a.id, await accountSettings(env)) });
}

async function consumeCode(env: Env, body: Record<string, unknown>, purpose: 'register' | 'reset') {
  const email = emailOf(body);
  const code = field(body, 'code', /^[0-9]{6}$/);
  const id = field(body, 'verificationId', /^[a-zA-Z0-9-]{36}$/);
  const hash = await sha256Hex(id + ':' + code);
  const found = await env.DB.prepare(`UPDATE account_email_codes SET used_at=? WHERE id=? AND app_id=?
    AND email=? AND purpose=? AND code_hash=? AND used_at IS NULL AND expires_at>? RETURNING id`)
    .bind(milliseconds(), id, env.APP_ID, email, purpose, hash, milliseconds()).all();
  if (!found.results.length) throw new ApiError('EMAIL_VERIFICATION_REQUIRED', 'Verification code is invalid or expired', 400);
}

async function sendCode(request: Request, env: WorkerEnv, body: Record<string, unknown>): Promise<Response> {
  const email = emailOf(body);
  const purpose = field(body, 'purpose', /^(register|reset)$/) as 'register' | 'reset';
  const settings = await accountSettings(env);
  if (purpose === 'register' && (!settings.registration_enabled || !settings.password_registration_enabled)) {
    throw new ApiError('REGISTRATION_DISABLED', 'Registration has been closed by the administrator', 403);
  }
  await authRate(request, env, email);
  if (!env.ACCOUNT_MAIL_API_KEY || !env.ACCOUNT_MAIL_FROM) throw new ApiError('BACKEND_UNAVAILABLE', 'Email delivery is not configured', 503);
  const id = crypto.randomUUID(), now = milliseconds();
  const random = crypto.getRandomValues(new Uint32Array(1))[0];
  const code = String(random % 1000000).padStart(6, '0');
  const existing = await env.DB.prepare(`SELECT id FROM accounts WHERE app_id=? AND email=? AND state='active'`)
    .bind(env.APP_ID, email).first();
  // Password reset deliberately returns the same response for unknown accounts.
  if (purpose === 'reset' && !existing) return json({ ok: true, verificationId: id, expiresIn: 600 });
  await env.DB.prepare(`INSERT INTO account_email_codes(id,app_id,email,purpose,code_hash,created_at,expires_at)
    VALUES(?,?,?,?,?,?,?)`).bind(id, env.APP_ID, email, purpose, await sha256Hex(id + ':' + code), now, now + 600000).run();
  const response = await fetch('https://api.resend.com/emails', { method: 'POST',
    headers: { Authorization: 'Bearer ' + env.ACCOUNT_MAIL_API_KEY, 'Content-Type': 'application/json', 'Idempotency-Key': id },
    body: JSON.stringify({ from: env.ACCOUNT_MAIL_FROM, to: [email], subject: 'E-Track verification code',
      text: 'Your E-Track verification code is ' + code + '. It expires in 10 minutes. Do not share it.' }),
    signal: AbortSignal.timeout(15000) });
  if (!response.ok) {
    await env.DB.prepare('DELETE FROM account_email_codes WHERE id=?').bind(id).run();
    throw new ApiError('BACKEND_UNAVAILABLE', 'Unable to send verification email', 503);
  }
  await response.body?.cancel();
  return json({ ok: true, verificationId: id, expiresIn: 600 });
}

export async function accountAuthRoute(request: Request, env: WorkerEnv): Promise<Response> {
  const path = new URL(request.url).pathname;
  if (request.method === 'GET' && path === '/api/auth/status') {
    const s = await accountSettings(env);
    return json({ registrationEnabled: !!s.registration_enabled,
      passwordRegistrationEnabled: !!s.password_registration_enabled,
      emailVerificationEnabled: !!s.email_verification_enabled,
      passwordResetAvailable: !!env.ACCOUNT_MAIL_API_KEY && !!env.ACCOUNT_MAIL_FROM,
      automaticDailyLimit: s.automatic_daily_limit, manualDailyLimit: s.manual_daily_limit, timezone: 'Asia/Shanghai' });
  }
  if (request.method !== 'POST') throw invalidParameter('Unsupported account operation');
  const body = await boundedJson(request, 8192);
  if (path === '/api/auth/email-code') return sendCode(request, env, body);
  const login = typeof body.username === 'string' ? body.username.trim().toLowerCase() : '';
  await authRate(request, env, login || (typeof body.email === 'string' ? body.email : ''));
  if (path === '/api/auth/register') {
    const settings = await accountSettings(env);
    if (!settings.registration_enabled || !settings.password_registration_enabled) {
      throw new ApiError('REGISTRATION_DISABLED', 'Registration has been closed by the administrator', 403);
    }
    const username = field(body, 'username', /^[A-Za-z0-9_]{3,32}$/).toLowerCase();
    const password = accountPassword(body.password);
    const email = body.email ? emailOf(body) : null;
    if (settings.email_verification_enabled) await consumeCode(env, body, 'register');
    const now = milliseconds(), id = crypto.randomUUID();
    const hash = await hashAccountPassword(password);
    const result = await env.DB.prepare(`INSERT INTO accounts
      (id,app_id,username,display_name,email,email_verified,password_hash,created_at)
      SELECT ?,?,?,?,?,?,?,? WHERE EXISTS(SELECT 1 FROM account_settings
        WHERE app_id=? AND registration_enabled=1 AND password_registration_enabled=1
        AND email_verification_enabled=?) ON CONFLICT DO NOTHING RETURNING id`)
      .bind(id, env.APP_ID, username, username, email, email && settings.email_verification_enabled ? 1 : 0,
        hash, now, env.APP_ID, settings.email_verification_enabled).all();
    if (!result.results.length) throw new ApiError('CAS_CONFLICT', 'Registration unavailable or account already exists', 409);
    const a = await env.DB.prepare('SELECT * FROM accounts WHERE id=?').bind(id).first<Account>();
    return json({ ok: true, account: accountPublic(a!) }, 201);
  }
  if (path === '/api/auth/login') {
    const password = accountPassword(body.password);
    const account = await env.DB.prepare(`SELECT * FROM accounts WHERE app_id=? AND (username=? OR email=?)`)
      .bind(env.APP_ID, login, login).first<Account>();
    const dummy = 'scrypt$16384$8$5$00000000000000000000000000000000$' + '0'.repeat(64);
    const matched = await passwordMatches(password, account?.password_hash ?? dummy);
    if (!account || !matched || account.state === 'deleted') throw new ApiError('INVALID_CREDENTIALS', 'Username or password is incorrect', 401);
    if (account.state !== 'active') throw new ApiError('ACCOUNT_DISABLED', 'Account has been disabled', 403);
    return session(env, account, typeof body.appVersion === 'string' ? body.appVersion : '');
  }
  if (path === '/api/auth/reset-password') {
    const password = accountPassword(body.password), email = emailOf(body);
    await consumeCode(env, body, 'reset');
    const account = await env.DB.prepare(`SELECT id FROM accounts WHERE app_id=? AND email=? AND state='active'`)
      .bind(env.APP_ID, email).first<{ id: string }>();
    if (!account) throw new ApiError('INVALID_CREDENTIALS', 'Reset unavailable', 400);
    await env.DB.batch([
      env.DB.prepare('UPDATE accounts SET password_hash=?,email_verified=1 WHERE id=?').bind(await hashAccountPassword(password), account.id),
      env.DB.prepare('UPDATE account_sessions SET revoked_at=? WHERE account_id=?').bind(milliseconds(), account.id)
    ]);
    return json({ ok: true });
  }
  throw invalidParameter('Unknown authentication operation');
}

export async function accountRoute(request: Request, env: WorkerEnv): Promise<Response> {
  const account = await requireAccount(request, env);
  const url = new URL(request.url), path = url.pathname;
  if (request.method === 'GET' && path === '/api/account/me') {
    return json({ account: accountPublic(account), quota: await accountBudget(env.DB, account.id, await accountSettings(env)) });
  }
  if (request.method === 'GET' && path === '/api/account/devices') {
    return json({ devices: (await env.DB.prepare(`SELECT uid,name,model,hardware_revision,firmware_version,image_sha256,
      bound_at,last_seen_at FROM account_devices WHERE account_id=? AND app_id=? ORDER BY bound_at DESC LIMIT 100`)
      .bind(account.id, env.APP_ID).all()).results });
  }
  if (request.method !== 'POST') throw invalidParameter('Unsupported account operation');
  await authRate(request, env, account.id);
  const body = await boundedJson(request, 8192), now = milliseconds();
  if (path === '/api/account/logout') {
    const token = request.headers.get('Authorization')!.slice(7);
    await env.DB.prepare('UPDATE account_sessions SET revoked_at=? WHERE token_hash=?').bind(now, await sha256Hex(token)).run();
    return json({ ok: true });
  }
  if (path === '/api/account/delete') {
    if (!await passwordMatches(accountPassword(body.password), account.password_hash)) throw new ApiError('INVALID_CREDENTIALS', 'Password is incorrect', 401);
    await env.DB.batch([
      env.DB.prepare(`UPDATE accounts SET state='deleted',email=NULL,display_name='',password_hash='' WHERE id=?`).bind(account.id),
      env.DB.prepare('DELETE FROM account_sessions WHERE account_id=?').bind(account.id),
      env.DB.prepare('DELETE FROM account_devices WHERE account_id=?').bind(account.id),
      env.DB.prepare('DELETE FROM account_email_codes WHERE app_id=? AND email=?').bind(env.APP_ID, account.email ?? '')
    ]);
    return json({ ok: true });
  }
  if (path === '/api/account/devices/bind') {
    const uid = field(body, 'uid', /^[0-9a-f]{24}$/);
    if (/^(0{24}|f{24})$/.test(uid)) throw invalidParameter('Invalid hardware UID');
    const model = field(body, 'model', /^e-track-at32f435$/);
    const name = field(body, 'name', /^[^\x00-\x1f]{1,64}$/);
    const image = field(body, 'imageSha256', /^[0-9a-f]{64}$/);
    const hardware = body.hardwareRevision, version = body.firmwareVersion;
    if (!Number.isInteger(hardware) || Number(hardware) < 1 || Number(hardware) > 65535 ||
        !Number.isInteger(version) || Number(version) < 1 || Number(version) > 0xffffffff || body.confirmed !== true) {
      throw invalidParameter('A confirmed connected-device identity is required');
    }
    const old = await env.DB.prepare('SELECT account_id FROM account_devices WHERE app_id=? AND uid=?')
      .bind(env.APP_ID, uid).first<{ account_id: string }>();
    if (old && old.account_id !== account.id) throw new ApiError('DEVICE_ALREADY_BOUND', 'Device belongs to another account', 409);
    const bound = await env.DB.prepare(`INSERT INTO account_devices
      (app_id,uid,account_id,name,model,hardware_revision,firmware_version,image_sha256,bound_at,last_seen_at)
      SELECT ?,?,?,?,?,?,?,?,?,? WHERE
        EXISTS(SELECT 1 FROM account_devices WHERE app_id=? AND uid=? AND account_id=?) OR
        (SELECT COUNT(*) FROM account_devices WHERE account_id=?) < 100
      ON CONFLICT(app_id,uid) DO UPDATE SET name=excluded.name,
      hardware_revision=excluded.hardware_revision,firmware_version=excluded.firmware_version,
      image_sha256=excluded.image_sha256,last_seen_at=excluded.last_seen_at
      WHERE account_devices.account_id=excluded.account_id RETURNING uid`)
      .bind(env.APP_ID, uid, account.id, name, model, hardware, version, image, now, now,
        env.APP_ID, uid, account.id, account.id).all();
    if (!bound.results.length) throw new ApiError('DEVICE_ALREADY_BOUND', 'Device binding changed', 409);
    await env.DB.prepare('INSERT INTO account_audit(id,actor,action,account_id,device_uid,occurred_at) VALUES(?,?,?,?,?,?)')
      .bind(crypto.randomUUID(), account.id, old ? 'device_refresh' : 'device_bind', account.id, uid, now).run();
    return json({ ok: true });
  }
  if (path === '/api/account/devices/unbind') {
    const uid = field(body, 'uid', /^[0-9a-f]{24}$/);
    if (!await passwordMatches(accountPassword(body.password), account.password_hash)) throw new ApiError('INVALID_CREDENTIALS', 'Password is incorrect', 401);
    await env.DB.batch([
      env.DB.prepare('DELETE FROM account_devices WHERE app_id=? AND uid=? AND account_id=?').bind(env.APP_ID, uid, account.id),
      env.DB.prepare('INSERT INTO account_audit(id,actor,action,account_id,device_uid,occurred_at) VALUES(?,?,?,?,?,?)')
        .bind(crypto.randomUUID(), account.id, 'device_unbind', account.id, uid, now)
    ]);
    return json({ ok: true });
  }
  if (path === '/api/account/ota/authorize') {
    await requireBoundDevice(request, env, account);
    return json({ ok: true, accountId: account.id, authorizedAt: now });
  }
  throw invalidParameter('Unknown account operation');
}

export async function requireBoundDevice(request: Request, env: Env, account: Account) {
  const uid = request.headers.get('X-Device-Uid') ?? '';
  if (!/^[0-9a-f]{24}$/.test(uid)) throw new ApiError('DEVICE_NOT_BOUND', 'Connect and bind this device before OTA', 403);
  const device = await env.DB.prepare('SELECT * FROM account_devices WHERE app_id=? AND uid=? AND account_id=?')
    .bind(env.APP_ID, uid, account.id).first();
  if (!device) throw new ApiError('DEVICE_NOT_BOUND', 'Device is not bound to this account', 403);
  return device;
}

export async function accountCloudAccess(request: Request, env: WorkerEnv, next: () => Promise<Response>): Promise<Response> {
  const account = await requireAccount(request, env);
  const path = new URL(request.url).pathname;
  if (path.startsWith('/api/public/firmware/')) await requireBoundDevice(request, env, account);
  if (path === '/api/public/latest' || path === '/api/public/firmware/latest') {
    const rate = await env.RATE_LIMITER.getByName('account-check:' + account.id).check('check', 12, 60);
    if (!rate.allowed) throw new ApiError('RATE_LIMITED', 'Too many check attempts', 429, { retryAfter: rate.retryAfter });
    return accountCheck(request, env.DB, account.id, await accountSettings(env), next);
  }
  return next();
}

export async function cleanupAccounts(env: Env) {
  const now = milliseconds();
  await env.DB.batch([
    env.DB.prepare('DELETE FROM account_sessions WHERE expires_at<? OR revoked_at<?').bind(now - 86400000, now - 86400000),
    env.DB.prepare('DELETE FROM account_email_codes WHERE expires_at<?').bind(now - 86400000),
    env.DB.prepare('DELETE FROM account_update_checks WHERE created_at<?').bind(now - 8 * 86400000),
    env.DB.prepare('DELETE FROM account_login_events WHERE occurred_at<?').bind(now - 90 * 86400000)
  ]);
}
