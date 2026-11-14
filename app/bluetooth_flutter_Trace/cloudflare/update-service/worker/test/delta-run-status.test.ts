import { env } from "cloudflare:workers";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { inspectDeltaRuns, type DeltaRunIdentity } from "../src/delta_run_status";
import { deltaJobViews, type DeltaJob } from "../src/delta_jobs";

const config = { ...env, DELTA_GITHUB_TOKEN: "status-read-test" };
const now = 1794652000;
let count = 0;
beforeEach(async () => {
  count = 0;
  await env.DB.batch(["admin_notification_deliveries", "admin_notifications", "admin_push_deliveries", "delta_notifications",
    "delta_job_events", "delta_job_attempts", "delta_jobs"].map(table => env.DB.prepare(`DELETE FROM ${table}`)));
});
async function identity(): Promise<DeltaRunIdentity> {
  const number = ++count, id = "delta_" + String(number).padStart(64, "0"), sha = "a".repeat(64);
  await env.DB.prepare(`INSERT INTO delta_jobs(id,kind,target_release_id,base_release_id,target_sha256,base_sha256,
    base_version_code,target_version_code,status,input_json,input_sha256,workflow_commit,workflow_ref,actor,reason,created_at,updated_at)
    VALUES (?,'firmware',?,'base',?,?,30324,30325,'queued','{}',?,?,'dev/admin/status-test','owner','test',?,?)`)
    .bind(id, `target-${number}`, sha, sha, sha, "b".repeat(40), now, now).run();
  return { id, attempt: 1, workflowCommit: "b".repeat(40), repository: "Eitan-S-23/E-Track", ref: "dev/admin/status-test", runId: null };
}
const run = (job: DeltaRunIdentity, status = "waiting", extra: Record<string, unknown> = {}) => ({
  id: 12345, event: "workflow_dispatch", head_sha: job.workflowCommit, head_branch: job.ref,
  display_title: `delta:${job.id}:${job.attempt}`, status, conclusion: null, ...extra
});
function provider(runs: unknown[], pending: unknown = [{ environment: { name: "firmware-rehearsal" },
  reviewers: [{ type: "User", reviewer: { login: "do-not-expose" } }], current_user_can_approve: true }]) {
  return vi.fn<typeof fetch>(async (input, init) => {
    const request = new Request(input, init);
    expect(request.method).toBe("GET"); expect(request.redirect).toBe("manual");
    return Response.json(String(input).endsWith("/pending_deployments") ? pending : { workflow_runs: runs });
  });
}
describe("observed GitHub delta approval state", () => {
  it("requires an actual matching reviewer gate, caches it, and never mutates the job or approves", async () => {
    const job = await identity(), fetcher = provider([run(job)]);
    const before = await env.DB.prepare("SELECT * FROM delta_jobs WHERE id=?").bind(job.id).first();
    const result = (await inspectDeltaRuns(config, [job], fetcher, now)).get(job.id)!;
    expect(result).toMatchObject({ phase: "awaiting_approval", approvalEnvironments: ["firmware-rehearsal"],
      runUrl: "https://github.com/Eitan-S-23/E-Track/actions/runs/12345" });
    expect(JSON.stringify(result)).not.toContain("do-not-expose");
    expect(JSON.stringify(result)).not.toContain("current_user_can_approve");
    expect((await inspectDeltaRuns(config, [job], fetcher, now + 10)).get(job.id)).toEqual(result);
    expect(fetcher).toHaveBeenCalledTimes(2);
    expect(await env.DB.prepare("SELECT * FROM delta_jobs WHERE id=?").bind(job.id).first()).toEqual(before);
    expect((await env.DB.prepare("SELECT * FROM delta_job_events").all()).results).toHaveLength(0);
  });
  it.each([["queued", "ci_queued"], ["in_progress", "ci_preparing"], ["completed", "ci_finished"]])(
    "distinguishes %s without inventing approval", async (status, phase) => {
      const job = await identity(), fetcher = provider([run(job, status)]);
      expect((await inspectDeltaRuns(config, [job], fetcher, now)).get(job.id)).toMatchObject({ phase, approvalEnvironments: [] });
      expect(fetcher).toHaveBeenCalledTimes(1);
    });
  it("does not turn an environment wait timer into manual approval", async () => {
    const job = await identity(), fetcher = provider([run(job)], [{ environment: { name: "timer" }, reviewers: [], wait_timer: 5 }]);
    expect((await inspectDeltaRuns(config, [job], fetcher, now)).get(job.id)?.phase).toBe("ci_waiting");
  });
  it("refreshes expired status when the same run moves on", async () => {
    const job = await identity(); await inspectDeltaRuns(config, [job], provider([run(job)]), now);
    const next = provider([run(job, "in_progress")]);
    expect((await inspectDeltaRuns(config, [job], next, now + 31)).get(job.id)?.phase).toBe("ci_preparing");
    expect(next).toHaveBeenCalledTimes(1);
  });
  it.each([{ head_sha: "c".repeat(40) }, { display_title: "another attempt" }, { head_branch: "main" }])(
    "does not link a mismatched run: %j", async extra => {
      const job = await identity(), fetcher = provider([run(job, "waiting", extra)]);
      expect((await inspectDeltaRuns(config, [job], fetcher, now)).get(job.id)).toMatchObject({ phase: "ci_pending", runUrl: null });
      expect(fetcher).toHaveBeenCalledTimes(1);
    });
  it("rejects duplicate matching runs rather than choosing one to approve", async () => {
    const job = await identity(), fetcher = provider([run(job), run(job, "waiting", { id: 67890 })]);
    expect((await inspectDeltaRuns(config, [job], fetcher, now)).get(job.id)).toMatchObject({ phase: "ci_unavailable", errorCode: "CI_RUN_AMBIGUOUS", runUrl: null });
  });
  it.each([302, 403, 429, 503])("keeps a provider HTTP %i failure separate from job failure", async status => {
    const job = await identity(), fetcher = vi.fn<typeof fetch>(async (input, init) => {
      expect(new Request(input, init).redirect).toBe("manual");
      return new Response(null, { status, headers: { Location: "https://untrusted.example/" } });
    });
    expect((await inspectDeltaRuns(config, [job], fetcher, now)).get(job.id)).toMatchObject({ phase: "ci_unavailable", errorCode: `GITHUB_HTTP_${status}` });
    expect(fetcher).toHaveBeenCalledTimes(1);
    expect((await env.DB.prepare("SELECT status,attempt FROM delta_jobs WHERE id=?").bind(job.id).first())).toEqual({ status: "queued", attempt: 1 });
  });
  it("bounds the batch and reuses one repository/ref listing", async () => {
    const jobs = []; for (let i = 0; i < 7; i++) jobs.push(await identity());
    const fetcher = provider(jobs.map((job, i) => run(job, "queued", { id: 12345 + i })));
    expect((await inspectDeltaRuns(config, jobs, fetcher, now)).size).toBe(5);
    expect(fetcher).toHaveBeenCalledTimes(1);
  });
  it("leases a pending observation across concurrent requests", async () => {
    const job = await identity(); let release!: () => void;
    const gate = new Promise<void>(resolve => { release = resolve; });
    const fetcher = vi.fn<typeof fetch>(async () => { await gate; return Response.json({ workflow_runs: [run(job, "queued")] }); });
    const first = inspectDeltaRuns(config, [job], fetcher, now);
    await vi.waitFor(() => expect(fetcher).toHaveBeenCalledTimes(1));
    const second = await inspectDeltaRuns(config, [job], fetcher, now);
    expect(second.get(job.id)?.errorCode).toBe("CI_STATUS_REFRESHING");
    release(); await first;
    expect(fetcher).toHaveBeenCalledTimes(1);
  });
  it("does not read GitHub for a terminal job or without configured credentials", async () => {
    const identityRow = await identity(), fetcher = provider([]);
    expect((await inspectDeltaRuns({ DB: env.DB }, [identityRow], fetcher, now)).size).toBe(0);
    const job = (await env.DB.prepare("SELECT * FROM delta_jobs WHERE id=?").bind(identityRow.id).first<DeltaJob>())!;
    const views = await deltaJobViews(config, [{ ...job, status: "failed", error_code: "CI_BUILD_FAILED" }], fetcher);
    expect(views[0]).toMatchObject({ status: "failed", phase: "failed", errorCode: "CI_BUILD_FAILED" });
    expect(fetcher).not.toHaveBeenCalled();
  });
});
