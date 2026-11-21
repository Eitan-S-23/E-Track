import { env } from 'cloudflare:workers';
import { SELF as platformSelf } from 'cloudflare:test';
import { sha256Hex } from '../src/crypto';

// Existing release tests exercise their original handlers behind real admission.
// Account limits and anonymous denials have separate tests; no production bypass.
export async function signedInRequest(input: RequestInfo | URL, init?: RequestInit): Promise<Request> {
  const request = new Request(input, init);
  if (!new URL(request.url).pathname.startsWith('/api/public/')) return request;
  const id = crypto.randomUUID(), token = 'acct_' + crypto.randomUUID().replaceAll('-', '') + crypto.randomUUID().replaceAll('-', '');
  const uid = crypto.randomUUID().replaceAll('-', '').slice(0, 24), now = Date.now();
  await env.DB.batch([
    env.DB.prepare('INSERT INTO accounts(id,app_id,username,display_name,password_hash,created_at) VALUES(?,?,?,?,?,?)')
      .bind(id, env.APP_ID, id, id, '', now),
    env.DB.prepare('INSERT INTO account_sessions(token_hash,account_id,created_at,expires_at) VALUES(?,?,?,?)')
      .bind(await sha256Hex(token), id, now, now + 86400000),
    env.DB.prepare(`INSERT INTO account_devices(app_id,uid,account_id,name,model,hardware_revision,firmware_version,image_sha256,bound_at,last_seen_at)
      VALUES(?,?,?,?,?,?,?,?,?,?)`).bind(env.APP_ID, uid, id, 'Test device', 'e-track-at32f435', 1, 30348, 'a'.repeat(64), now, now)
  ]);
  const headers = new Headers(request.headers);
  const installation = headers.get('Authorization')?.match(/^Bearer ([0-9a-f]{64})$/)?.[1];
  if (installation) headers.set('X-Install-Token', installation);
  headers.set('Authorization', 'Bearer ' + token);
  headers.set('X-Device-Uid', uid);
  headers.set('X-Update-Check-Id', crypto.randomUUID());
  headers.set('X-Update-Check-Kind', 'manual');
  return new Request(request, { headers });
}
export const SELF = { async fetch(input: RequestInfo | URL, init?: RequestInit) {
  return platformSelf.fetch(await signedInRequest(input, init));
} };
