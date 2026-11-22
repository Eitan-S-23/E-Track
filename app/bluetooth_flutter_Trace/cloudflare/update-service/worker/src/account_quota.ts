import { sha256Hex } from './crypto';
import { ApiError, invalidParameter } from './errors';
import { json } from './http';

export type CheckKind = 'automatic' | 'manual';
export interface AccountLimits { automatic_daily_limit: number; manual_daily_limit: number }
export const automaticSpacingMs = 60 * 60 * 1000;
interface CheckRow {
  request_hash: string; kind: CheckKind; day: string; state: string; created_at: number;
  lease_until: number; response_status: number | null; response_json: string | null;
}

export function accountDay(now: number): { day: string; resetsAt: number } {
  const offset = 8 * 3600000;
  const date = new Date(now + offset);
  return { day: date.toISOString().slice(0, 10),
    resetsAt: Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), date.getUTCDate() + 1) - offset };
}

export async function accountBudget(db: D1Database, account: string, limits: AccountLimits, now = Date.now()) {
  const { day, resetsAt } = accountDay(now);
  const rows = (await db.prepare(`SELECT kind,COUNT(*) AS used FROM account_update_checks
    WHERE account_id=? AND day=? AND (state='complete' OR (state='pending' AND lease_until>?)) GROUP BY kind`)
    .bind(account, day, now).all<{ kind: CheckKind; used: number }>()).results;
  const used = (kind: CheckKind) => rows.find(r => r.kind === kind)?.used ?? 0;
  return { day, resetsAt, automatic: { limit: limits.automatic_daily_limit, used: used('automatic'),
    remaining: Math.max(0, limits.automatic_daily_limit - used('automatic')) },
    manual: { limit: limits.manual_daily_limit, used: used('manual'),
      remaining: Math.max(0, limits.manual_daily_limit - used('manual')) } };
}

function identity(value: Record<string, unknown>): string {
  // Download refresh may renew URLs, never silently select a different update.
  const asset = value.asset as Record<string, unknown> | undefined;
  return JSON.stringify([value.versionCode, value.releaseId, value.releaseTag,
    value.targetImageSha256, value.apkSha256, value.apkSize, value.payloadSignature,
    value.assets, asset?.assetId, asset?.kind, asset?.sha256, asset?.sizeBytes,
    asset?.baseImageSha256, value.legacyMigration]);
}

export async function accountCheck(request: Request, db: D1Database, account: string,
  limits: AccountLimits, next: () => Promise<Response>, now = Date.now()): Promise<Response> {
  const started = performance.now();
  const checkId = request.headers.get('X-Update-Check-Id') ?? '';
  const kind = request.headers.get('X-Update-Check-Kind');
  if (!/^[a-zA-Z0-9_-]{16,80}$/.test(checkId) || (kind !== 'automatic' && kind !== 'manual')) {
    throw invalidParameter('A check ID and automatic/manual kind are required');
  }
  const url = new URL(request.url);
  url.searchParams.sort();
  const requestHash = await sha256Hex(url.pathname + url.search + '|' + (request.headers.get('X-Device-Uid') ?? ''));
  const { day, resetsAt } = accountDay(now);
  const find = () => db.prepare('SELECT * FROM account_update_checks WHERE account_id=? AND check_id=?')
    .bind(account, checkId).first<CheckRow>();
  let row = await find();
  if (row && (row.request_hash !== requestHash || row.kind !== kind)) {
    throw new ApiError('IDEMPOTENCY_CONFLICT', 'Check ID belongs to a different request', 409);
  }
  const refresh = request.headers.get('X-Update-Refresh') === '1';
  if (refresh) {
    if (!row || row.state !== 'complete' || !row.response_json || now - row.created_at > 24 * 3600000) {
      throw new ApiError('IDEMPOTENCY_RESULT_EXPIRED', 'Update preparation expired; check again', 409);
    }
    const previous = JSON.parse(row.response_json) as Record<string, unknown>;
    if (previous.updateAvailable !== true) throw invalidParameter('No prepared update to refresh');
    const response = await next();
    if (!response.ok) return response;
    const current = await response.clone().json() as Record<string, unknown>;
    if (current.updateAvailable !== true || identity(previous) !== identity(current)) {
      throw new ApiError('IDEMPOTENCY_CONFLICT', 'Prepared update changed; a new check is required', 409);
    }
    return withBudget(response, db, account, limits, now);
  }
  if (row?.state === 'complete') {
    if (now - row.created_at > 60000 || !row.response_json || row.response_status === null) {
      throw new ApiError('IDEMPOTENCY_RESULT_EXPIRED', 'Check replay expired', 409);
    }
    return withBudget(json(JSON.parse(row.response_json), row.response_status), db, account, limits, now);
  }
  if (row?.state === 'pending' && row.lease_until > now) {
    throw new ApiError('CHECK_IN_PROGRESS', 'The same check is in progress', 409);
  }
  const limit = kind === 'automatic' ? limits.automatic_daily_limit : limits.manual_daily_limit;
  const leaseToken = crypto.randomUUID();
  // A single conditional SQL write serializes reservations across all phones.
  const reserved = await db.prepare(`INSERT INTO account_update_checks
    (account_id,check_id,day,kind,request_hash,state,created_at,lease_until,lease_token)
    SELECT ?,?,?,?,?,'pending',?,?,? WHERE
      (SELECT COUNT(*) FROM account_update_checks WHERE account_id=? AND day=? AND kind=?
        AND (state='complete' OR (state='pending' AND lease_until>?))) < ?
      AND (?='manual' OR NOT EXISTS(SELECT 1 FROM account_update_checks
        WHERE account_id=? AND kind='automatic' AND created_at>?
        AND (state='complete' OR (state='pending' AND lease_until>?))))
    ON CONFLICT(account_id,check_id) DO UPDATE SET state='pending',day=excluded.day,
      created_at=excluded.created_at,lease_until=excluded.lease_until,lease_token=excluded.lease_token
      WHERE account_update_checks.request_hash=excluded.request_hash AND account_update_checks.kind=excluded.kind
        AND (account_update_checks.state='failed' OR
          (account_update_checks.state='pending' AND account_update_checks.lease_until<=?))
    RETURNING check_id`).bind(account, checkId, day, kind, requestHash, now, now + 120000, leaseToken,
      account, day, kind, now, limit, kind, account, now - automaticSpacingMs, now, now).all();
  if (!reserved.results.length) {
    row = await find();
    if (row && (row.request_hash !== requestHash || row.kind !== kind)) {
      throw new ApiError('IDEMPOTENCY_CONFLICT', 'Check ID belongs to a different request', 409);
    }
    if (row?.state === 'complete') return accountCheck(request, db, account, limits, next, now);
    if (row?.state === 'pending' && row.lease_until > now) throw new ApiError('CHECK_IN_PROGRESS', 'Check in progress', 409);
    const budget = await accountBudget(db, account, limits, now);
    if (kind === 'automatic' && budget.automatic.remaining > 0) {
      const previous = await db.prepare(`SELECT MAX(created_at) AS last FROM account_update_checks
        WHERE account_id=? AND kind='automatic' AND (state='complete' OR (state='pending' AND lease_until>?))`)
        .bind(account, now).first<{ last: number | null }>();
      if (previous?.last !== null && previous?.last !== undefined && previous.last + automaticSpacingMs > now) {
        throw new ApiError('CHECK_TOO_SOON', 'Automatic check interval has not elapsed', 429,
          { nextCheckAt: previous.last + automaticSpacingMs });
      }
    }
    throw new ApiError('CHECK_QUOTA_EXCEEDED', 'Account daily check allowance exhausted', 429,
      { kind, limit, remaining: 0, resetsAt });
  }
  try {
    const response = await next();
    const body = response.ok ? await response.clone().text() : null;
    const parsed = body ? JSON.parse(body) as Record<string, unknown> : null;
    const counted = response.ok && parsed !== null &&
      ((parsed.updateAvailable === true && !parsed.errorCode) ||
        (parsed.updateAvailable === false && parsed.errorCode === 'NO_UPDATE'));
    const completedAt = now + Math.max(0, performance.now() - started);
    const completed = await db.prepare(`UPDATE account_update_checks SET state=?,response_status=?,response_json=?
      WHERE account_id=? AND check_id=? AND state='pending' AND lease_token=? AND lease_until>?
      RETURNING check_id`)
      .bind(counted ? 'complete' : 'failed', counted ? response.status : null, counted ? body : null,
        account, checkId, leaseToken, completedAt).all();
    if (!completed.results.length) throw new ApiError('CHECK_IN_PROGRESS', 'Check lease was replaced; retry the same check ID', 409);
    return withBudget(response, db, account, limits, completedAt);
  } catch (error) {
    await db.prepare(`UPDATE account_update_checks SET state='failed' WHERE account_id=? AND check_id=?
      AND state='pending' AND lease_token=?`).bind(account, checkId, leaseToken).run();
    throw error;
  }
}

async function withBudget(response: Response, db: D1Database, account: string, limits: AccountLimits, now: number) {
  const budget = await accountBudget(db, account, limits, now);
  const headers = new Headers(response.headers);
  headers.set('X-Update-Automatic-Remaining', String(budget.automatic.remaining));
  headers.set('X-Update-Manual-Remaining', String(budget.manual.remaining));
  headers.set('X-Update-Quota-Reset', String(budget.resetsAt));
  headers.set('Cache-Control', 'no-store');
  return new Response(response.body, { status: response.status, headers });
}
