import type { WorkerEnv } from "./types";

type StatusEnv = Pick<WorkerEnv, "DB" | "DELTA_GITHUB_TOKEN">;
export interface DeltaRunIdentity {
  id: string; attempt: number; workflowCommit: string; repository: string; ref: string; runId: string | null;
}
export interface DeltaRunStatus {
  phase: "awaiting_approval" | "ci_queued" | "ci_preparing" | "ci_waiting" | "ci_finished" | "ci_pending" | "ci_unavailable";
  checkedAt: number;
  runUrl: string | null;
  approvalEnvironments: string[];
  conclusion: string | null;
  errorCode: string | null;
}
interface CachedStatus {
  workflow_commit: string; checked_at: number; result_json: string | null;
}
const CACHE_SECONDS = 30;
const unavailable = (now: number, errorCode: string): DeltaRunStatus => ({
  phase: "ci_unavailable", checkedAt: now, runUrl: null, approvalEnvironments: [], conclusion: null, errorCode
});
const object = (value: unknown): value is Record<string, unknown> => !!value && typeof value === "object" && !Array.isArray(value);

// A shared D1 lease/cache bounds polling across tabs. Only provider observations
// are cached here; job status, revision, attempts and notifications are untouched.
export async function inspectDeltaRuns(env: StatusEnv, identities: DeltaRunIdentity[],
  fetcher = fetch, now = Math.floor(Date.now() / 1000)): Promise<Map<string, DeltaRunStatus>> {
  if (!env.DELTA_GITHUB_TOKEN) return new Map();
  const lists = new Map<string, Promise<Record<string, unknown>>>();
  async function get(path: string): Promise<Record<string, unknown> | unknown[]> {
    const response = await fetcher(`https://api.github.com/repos/${path}`, {
      headers: { Authorization: `Bearer ${env.DELTA_GITHUB_TOKEN}`, Accept: "application/vnd.github+json",
        "User-Agent": "E-Track-Admin-Delta-Status" },
      redirect: "manual", signal: AbortSignal.timeout(6000)
    });
    if (!response.ok) { await response.body?.cancel(); throw new Error(`GITHUB_HTTP_${response.status}`); }
    // pending_deployments is an array, unlike the object-only boundedJson contract.
    const reader = response.body?.getReader();
    if (!reader) throw new Error("CI_INVALID_RESPONSE");
    const chunks: Uint8Array[] = []; let length = 0;
    try {
      for (;;) {
        const chunk = await reader.read();
        if (chunk.done) break;
        length += chunk.value.byteLength;
        if (length > 2 * 1024 * 1024) { await reader.cancel(); throw new Error("CI_RESPONSE_TOO_LARGE"); }
        chunks.push(chunk.value);
      }
    } finally { reader.releaseLock(); }
    const bytes = new Uint8Array(length); let offset = 0;
    for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.byteLength; }
    const value: unknown = JSON.parse(new TextDecoder().decode(bytes));
    if (!object(value) && !Array.isArray(value)) throw new Error("CI_INVALID_RESPONSE");
    return value;
  }
  async function observe(identity: DeltaRunIdentity): Promise<DeltaRunStatus> {
    const { repository, ref } = identity;
    if (!["Eitan-S-23/E-Track", "Eitan-S-23/Trace"].includes(repository)
      || !/^(?:main|dev\/[a-zA-Z0-9/_.-]+)$/.test(ref)) throw new Error("CI_INVALID_BINDING");
    const path = `${repository}/actions/workflows/admin-delta-build.yml/runs?event=workflow_dispatch&branch=${encodeURIComponent(ref)}&per_page=100`;
    if (!lists.has(path)) lists.set(path, get(path).then(value => {
      if (!object(value) || !Array.isArray(value.workflow_runs)) throw new Error("CI_INVALID_RESPONSE");
      return value;
    }));
    const result = await lists.get(path)!;
    const matches = (result.workflow_runs as unknown[]).filter(object).filter(run =>
      run.event === "workflow_dispatch" && run.head_sha === identity.workflowCommit && run.head_branch === ref
      && run.display_title === `delta:${identity.id}:${identity.attempt}`
      && /^[1-9][0-9]{0,19}$/.test(String(run.id)) && (typeof run.id !== "number" || Number.isSafeInteger(run.id)));
    if (!matches.length) return { ...unavailable(now, "CI_RUN_NOT_FOUND"), phase: "ci_pending" };
    if (matches.length !== 1 || (identity.runId && identity.runId !== String(matches[0].id))) throw new Error("CI_RUN_AMBIGUOUS");
    const run = matches[0];
    const status: DeltaRunStatus = { phase: "ci_queued", checkedAt: now,
      runUrl: `https://github.com/${repository}/actions/runs/${run.id}`, approvalEnvironments: [],
      conclusion: typeof run.conclusion === "string" ? run.conclusion : null, errorCode: null };
    if (run.status === "completed") status.phase = "ci_finished";
    else if (run.status === "in_progress") status.phase = "ci_preparing";
    else if (run.status === "waiting") {
      const pending = await get(`${repository}/actions/runs/${run.id}/pending_deployments`);
      if (!Array.isArray(pending)) throw new Error("CI_INVALID_RESPONSE");
      status.approvalEnvironments = pending.filter(object).filter(entry => Array.isArray(entry.reviewers) && entry.reviewers.length)
        .map(entry => object(entry.environment) ? entry.environment.name : null)
        .filter((name): name is string => typeof name === "string" && name.length > 0 && name.length <= 128);
      status.phase = status.approvalEnvironments.length ? "awaiting_approval" : "ci_waiting";
    } else if (!["queued", "requested", "pending"].includes(String(run.status))) throw new Error("CI_INVALID_RESPONSE");
    return status;
  }
  const entries = await Promise.all(identities.slice(0, 5).map(async identity => {
    let status: DeltaRunStatus;
    try {
      const previous = await env.DB.prepare("SELECT workflow_commit,checked_at,result_json FROM admin_delta_run_status WHERE job_id=? AND attempt=?")
        .bind(identity.id, identity.attempt).first<CachedStatus>();
      if (previous && previous.workflow_commit !== identity.workflowCommit) throw new Error("CI_CACHE_BINDING_CHANGED");
      if (previous?.result_json && previous.checked_at > now - CACHE_SECONDS) {
        return [identity.id, JSON.parse(previous.result_json) as DeltaRunStatus] as const;
      }
      await env.DB.prepare("INSERT OR IGNORE INTO admin_delta_run_status(job_id,attempt,workflow_commit) VALUES (?,?,?)")
        .bind(identity.id, identity.attempt, identity.workflowCommit).run();
      const lease = crypto.randomUUID();
      const claimed = await env.DB.prepare(`UPDATE admin_delta_run_status SET lease_until=?,lease_token=?
        WHERE job_id=? AND attempt=? AND workflow_commit=? AND lease_until<=? AND checked_at<=?`)
        .bind(now + CACHE_SECONDS, lease, identity.id, identity.attempt, identity.workflowCommit, now, now - CACHE_SECONDS).run();
      if (!claimed.meta.changes) return [identity.id, unavailable(now, "CI_STATUS_REFRESHING")] as const;
      try { status = await observe(identity); }
      catch (error) {
        const message = error instanceof Error ? error.message : "";
        status = unavailable(now, /^(GITHUB_HTTP_\d{3}|CI_[A-Z_]+)$/.test(message) ? message : "CI_STATUS_UNAVAILABLE");
      }
      await env.DB.prepare(`UPDATE admin_delta_run_status SET result_json=?,checked_at=?,lease_until=0,lease_token=NULL
        WHERE job_id=? AND attempt=? AND workflow_commit=? AND lease_token=?`)
        .bind(JSON.stringify(status), now, identity.id, identity.attempt, identity.workflowCommit, lease).run();
    } catch { status = unavailable(now, "CI_STATUS_UNAVAILABLE"); }
    return [identity.id, status] as const;
  }));
  return new Map(entries);
}
