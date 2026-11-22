import { invalidParameter } from './errors';

export interface Terminal {
  installationId: string; platform: string; versionName: string; versionCode: number;
  model: string; osVersion: string;
}

export function terminalInput(value: unknown): Terminal | null {
  if (value === undefined) return null; // Older clients never reported an installation identity.
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw invalidParameter('Invalid terminal');
  const v = value as Record<string, unknown>;
  const clean = (key: string, max: number) => {
    if (typeof v[key] !== 'string' || v[key].length > max || /[\x00-\x1f\x7f]/.test(v[key])) {
      throw invalidParameter('Invalid terminal ' + key);
    }
    return v[key] as string;
  };
  const installationId = clean('installationId', 32), platform = clean('platform', 16);
  if (!/^[0-9a-f]{32}$/.test(installationId) || !['android', 'windows', 'ios', 'macos', 'linux', 'unknown'].includes(platform)
      || !Number.isSafeInteger(v.versionCode) || Number(v.versionCode) < 0 || Number(v.versionCode) > 2100000000) {
    throw invalidParameter('Invalid terminal identity');
  }
  return { installationId, platform, versionName: clean('versionName', 64), versionCode: Number(v.versionCode),
    model: clean('model', 80), osVersion: clean('osVersion', 80) };
}

export function saveTerminal(db: D1Database, accountId: string, value: Terminal, now: number) {
  return db.prepare(`INSERT INTO account_terminals
    (account_id,installation_id,platform,version_name,version_code,model,os_version,first_seen_at,last_seen_at)
    VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(account_id,installation_id) DO UPDATE SET
    platform=excluded.platform,version_name=excluded.version_name,version_code=excluded.version_code,
    model=excluded.model,os_version=excluded.os_version,last_seen_at=excluded.last_seen_at`)
    .bind(accountId, value.installationId, value.platform, value.versionName, value.versionCode, value.model, value.osVersion, now, now);
}

export async function sessionList(db: D1Database, accountId: string, tokenHash?: string) {
  const now = Date.now();
  return (await db.prepare(`SELECT s.session_id AS id,s.installation_id AS installationId,
    s.created_at AS createdAt,s.last_seen_at AS lastSeenAt,s.expires_at AS expiresAt,
    CASE WHEN s.revoked_at IS NOT NULL THEN 'revoked' WHEN s.expires_at<=? THEN 'expired' ELSE 'valid' END AS state,
    s.token_hash=? AS current,t.platform,t.version_name AS versionName,t.version_code AS versionCode,t.model,t.os_version AS osVersion
    FROM account_sessions s LEFT JOIN account_terminals t ON t.account_id=s.account_id AND t.installation_id=s.installation_id
    WHERE s.account_id=? ORDER BY s.created_at DESC,s.session_id DESC LIMIT 100`)
    .bind(now, tokenHash ?? '', accountId).all()).results;
}

export async function accountConnections(db: D1Database, accountId: string, tokenHash?: string) {
  // Aggregate all retained sessions, not the truncated history display page.
  const terminals = (await db.prepare(`WITH retained_sessions AS (
    SELECT installation_id,MAX(created_at) AS last_login_at,COUNT(*) AS session_count,
      SUM(CASE WHEN revoked_at IS NULL AND expires_at>? THEN 1 ELSE 0 END) AS active_count,
      SUM(CASE WHEN revoked_at IS NULL THEN 1 ELSE 0 END) AS unrevoked_count,
      MAX(CASE WHEN token_hash=? THEN 1 ELSE 0 END) AS current
    FROM account_sessions WHERE account_id=? AND installation_id IS NOT NULL GROUP BY installation_id
    ) SELECT t.installation_id AS installationId,t.platform,t.version_name AS versionName,
    t.version_code AS versionCode,t.model,t.os_version AS osVersion,t.first_seen_at AS firstSeenAt,t.last_seen_at AS lastSeenAt,
    s.last_login_at AS lastLoginAt,COALESCE(s.session_count,0) AS sessionCount,
    COALESCE(s.active_count,0) AS activeSessionCount,COALESCE(s.current,0) AS current,
    CASE WHEN s.active_count>0 THEN 'valid' WHEN s.unrevoked_count>0 THEN 'expired'
      WHEN s.session_count>0 THEN 'revoked' ELSE 'unknown' END AS state
    FROM account_terminals t LEFT JOIN retained_sessions s ON s.installation_id=t.installation_id
    WHERE t.account_id=? ORDER BY t.last_seen_at DESC,t.installation_id LIMIT 100`)
    .bind(Date.now(), tokenHash ?? '', accountId, accountId).all()).results;
  const observations = (await db.prepare(`SELECT o.installation_id AS installationId,o.uid,o.firmware_version AS firmwareVersion,
    o.observed_at AS observedAt FROM account_device_observations o JOIN account_devices d ON d.account_id=o.account_id AND d.uid=o.uid
    WHERE o.account_id=? ORDER BY o.observed_at DESC,o.uid,o.installation_id LIMIT 100`).bind(accountId).all()).results;
  return { terminals, observations, coverage: 'reported-clients-only', onlineState: 'unknown', limit: 100 };
}
