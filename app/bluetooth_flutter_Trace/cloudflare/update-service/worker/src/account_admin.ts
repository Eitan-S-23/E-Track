import { accountBudget, accountDay } from './account_quota';
import { accountPublic, accountSettings, type Account } from './accounts';
import { ApiError, invalidParameter } from './errors';
import { json } from './http';
import { boundedJson } from './version_inventory';

interface Env { DB: D1Database; APP_ID: string; ACCOUNT_MAIL_API_KEY?: string; ACCOUNT_MAIL_FROM?: string }
interface Actor { email: string; role: 'viewer' | 'publisher' | 'owner' }

// Caller owns Access authentication, same-origin validation and CSRF enforcement.
export async function accountAdmin(request: Request, env: Env, actor: Actor): Promise<Response> {
  const url = new URL(request.url), method = request.method;
  const suffix = url.pathname.slice('/api/admin/accounts'.length);
  if (method === 'GET' && suffix === '/settings') return json(await accountSettings(env));
  if (method === 'GET' && suffix === '') {
    const page = Number(url.searchParams.get('page') ?? 1);
    if (!Number.isSafeInteger(page) || page < 1 || page > 100000) throw invalidParameter('Invalid page');
    const search = (url.searchParams.get('q') ?? '').trim();
    if (search.length > 64) throw invalidParameter('Search is too long');
    const state = url.searchParams.get('state') ?? '';
    if (!['', 'active', 'disabled', 'deleted'].includes(state)) throw invalidParameter('Invalid state');
    const where = `a.app_id=? AND (?='' OR a.state=?) AND (?='' OR instr(a.username,?)>0 OR instr(coalesce(a.email,''),?)>0
      OR EXISTS(SELECT 1 FROM account_devices d WHERE d.account_id=a.id AND instr(d.uid,?)>0))`;
    const args = [env.APP_ID, state, state, search, search.toLowerCase(), search.toLowerCase(), search.toLowerCase()];
    const users = (await env.DB.prepare(`SELECT a.*,(SELECT COUNT(*) FROM account_devices d WHERE d.account_id=a.id) AS device_count
      FROM accounts a WHERE ${where} ORDER BY a.created_at DESC,a.id DESC LIMIT 30 OFFSET ?`)
      .bind(...args, (page - 1) * 30).all<Account & { device_count: number }>()).results;
    const total = await env.DB.prepare(`SELECT COUNT(*) AS n FROM accounts a WHERE ${where}`).bind(...args).first<{ n: number }>();
    const dayStart = accountDay(Date.now()).resetsAt - 86400000;
    const stats = await env.DB.prepare(`SELECT COUNT(*) AS logins,COUNT(DISTINCT e.account_id) AS users FROM account_login_events e
      JOIN accounts a ON a.id=e.account_id WHERE a.app_id=? AND e.occurred_at>=?`)
      .bind(env.APP_ID, dayStart).first();
    const registered = await env.DB.prepare(`SELECT COUNT(*) AS total,SUM(state='active') AS active,
      SUM(created_at>=?) AS today FROM accounts WHERE app_id=? AND state!='deleted'`).bind(dayStart, env.APP_ID).first();
    return json({ users: users.map(a => ({ ...accountPublic(a), deviceCount: a.device_count })),
      total: total?.n ?? 0, page, pageSize: 30, stats: { today: stats, registered, timezone: 'Asia/Shanghai' } });
  }
  const match = /^\/([a-zA-Z0-9-]{36})(?:\/(state|revoke-sessions|unbind))?$/.exec(suffix);
  if (method === 'GET' && match && !match[2]) {
    const a = await env.DB.prepare('SELECT * FROM accounts WHERE app_id=? AND id=?').bind(env.APP_ID, match[1]).first<Account>();
    if (!a) throw invalidParameter('Account not found');
    const devices = (await env.DB.prepare(`SELECT uid,name,model,hardware_revision,firmware_version,image_sha256,bound_at,last_seen_at
      FROM account_devices WHERE account_id=? AND app_id=? ORDER BY bound_at DESC`).bind(a.id, env.APP_ID).all()).results;
    const logins = (await env.DB.prepare(`SELECT occurred_at,app_version FROM account_login_events WHERE account_id=?
      ORDER BY occurred_at DESC,id DESC LIMIT 50`).bind(a.id).all()).results;
    return json({ account: accountPublic(a), devices, logins,
      quota: await accountBudget(env.DB, a.id, await accountSettings(env)) });
  }
  if (method !== 'POST') throw invalidParameter('Unsupported account administration operation');
  if (actor.role !== 'owner') throw new ApiError('ACCOUNT_DISABLED', 'Owner role required', 403);
  const body = await boundedJson(request, 8192), now = Date.now();
  if (suffix === '/settings') {
    const settings = await accountSettings(env);
    if (!Number.isSafeInteger(body.revision) || body.revision !== settings.revision) {
      throw new ApiError('CAS_CONFLICT', 'Settings changed; reload before saving', 409);
    }
    const flags = ['registration_enabled', 'password_registration_enabled', 'email_verification_enabled'] as const;
    const counts = ['automatic_daily_limit', 'manual_daily_limit'] as const;
    for (const key of flags) if (body[key] !== 0 && body[key] !== 1) throw invalidParameter('Invalid ' + key);
    for (const key of counts) if (!Number.isInteger(body[key]) || Number(body[key]) < 0 || Number(body[key]) > 1000) throw invalidParameter('Invalid ' + key);
    if (body.email_verification_enabled === 1 && (!env.ACCOUNT_MAIL_API_KEY || !env.ACCOUNT_MAIL_FROM)) {
      throw invalidParameter('Email delivery must be configured before enabling verification');
    }
    const results = await env.DB.batch([
      env.DB.prepare(`UPDATE account_settings SET registration_enabled=?,password_registration_enabled=?,email_verification_enabled=?,
        automatic_daily_limit=?,manual_daily_limit=?,revision=revision+1 WHERE app_id=? AND revision=? RETURNING revision`)
        .bind(...flags.map(k => body[k]), ...counts.map(k => body[k]), env.APP_ID, body.revision),
      env.DB.prepare(`INSERT INTO account_audit(id,actor,action,occurred_at)
        SELECT ?,?,'settings_update',? WHERE changes()=1`).bind(crypto.randomUUID(), actor.email, now)
    ]);
    if (!results[0].results.length) throw new ApiError('CAS_CONFLICT', 'Settings changed; reload before saving', 409);
    return json({ ok: true, settings: await accountSettings(env) });
  }
  if (!match?.[2]) throw invalidParameter('Unsupported account operation');
  const a = await env.DB.prepare('SELECT id,state FROM accounts WHERE app_id=? AND id=?').bind(env.APP_ID, match[1]).first<{ id: string; state: string }>();
  if (!a || a.state === 'deleted') throw invalidParameter('Account is absent or deleted');
  const statements: D1PreparedStatement[] = [];
  if (match[2] === 'state') {
    if (body.state !== 'active' && body.state !== 'disabled') throw invalidParameter('Invalid state');
    statements.push(env.DB.prepare('UPDATE accounts SET state=? WHERE id=? AND state!=?').bind(body.state, a.id, 'deleted'));
  }
  let uid: string | null = null;
  if (match[2] === 'unbind') {
    if (typeof body.uid !== 'string' || !/^[0-9a-f]{24}$/.test(body.uid)) throw invalidParameter('Invalid UID');
    uid = body.uid;
    statements.push(env.DB.prepare('DELETE FROM account_devices WHERE account_id=? AND app_id=? AND uid=?').bind(a.id, env.APP_ID, uid));
  } else {
    statements.push(env.DB.prepare('UPDATE account_sessions SET revoked_at=? WHERE account_id=?').bind(now, a.id));
  }
  statements.push(env.DB.prepare('INSERT INTO account_audit(id,actor,action,account_id,device_uid,occurred_at) VALUES(?,?,?,?,?,?)')
    .bind(crypto.randomUUID(), actor.email, match[2] === 'state' ? 'state_' + String(body.state) : match[2], a.id, uid, now));
  await env.DB.batch(statements);
  return json({ ok: true });
}
