import { json } from "./http";
import { sha256Text } from "./version_inventory";

export interface ResourceUsageEnv {
  DB: D1Database;
  RESOURCE_USAGE_API_TOKEN?: string;
  RESOURCE_USAGE_CONFIG_JSON?: string;
}
interface Configuration {
  accountId: string;
  workerScript: string;
  pagesScript: string;
  publicPagesScript: string;
  databaseId: string;
  namespaceId: string;
  bucketName: string;
}
type State = "ok" | "stale" | "not_configured" | "permission_denied" | "unavailable" | "no_samples" | "refreshing";
interface Metric {
  key: string;
  group: string;
  unit: string;
  used: number | null;
  allowance: null;
  remaining: null;
  state: State;
  reason: State | null;
  scope: string;
  periodStart: number;
  periodEnd: number;
  periodRolloverAt: number | null;
  quotaResetAt: null;
  sampledAt: number | null;
  lastSuccessAt: number | null;
}
interface Snapshot { metrics: Metric[]; checkedAt: number }
interface CacheRow { checked_at: number; lease_until: number; snapshot_json: string | null }
interface Query {
  dataset: string;
  filter: Record<string, string | string[]>;
  fields: string;
  metrics: Array<{ key: string; group: string; unit: string; field: string; scale?: number }>;
  scope: string;
  monthly?: boolean;
  sample?: boolean;
}
const REFRESH_SECONDS = 900;
const MAX_RESPONSE_BYTES = 256 * 1024;
const CLASS_A = ["ListBuckets", "PutBucket", "ListObjects", "PutObject", "CopyObject", "CompleteMultipartUpload",
  "CreateMultipartUpload", "LifecycleStorageTierTransition", "ListMultipartUploads", "UploadPart", "UploadPartCopy",
  "ListParts", "PutBucketEncryption", "PutBucketCors", "PutBucketLifecycleConfiguration"];
const CLASS_B = ["HeadBucket", "HeadObject", "GetObject", "UsageSummary", "GetBucketEncryption", "GetBucketLocation",
  "GetBucketCors", "GetBucketLifecycleConfiguration"];

function configuration(env: ResourceUsageEnv): Configuration | null {
  if (!env.RESOURCE_USAGE_CONFIG_JSON || env.RESOURCE_USAGE_CONFIG_JSON.length > 4096) return null;
  try {
    const value: unknown = JSON.parse(env.RESOURCE_USAGE_CONFIG_JSON);
    if (!value || typeof value !== "object" || Array.isArray(value)) return null;
    const row = value as Record<string, unknown>;
    for (const key of ["accountId", "namespaceId"]) if (typeof row[key] !== "string" || !/^[a-f0-9]{32}$/.test(row[key])) return null;
    if (typeof row.databaseId !== "string" || !/^[a-f0-9-]{36}$/.test(row.databaseId)) return null;
    for (const key of ["workerScript", "pagesScript", "publicPagesScript", "bucketName"]) {
      if (typeof row[key] !== "string" || !/^[a-zA-Z0-9_-]{1,100}$/.test(row[key])) return null;
    }
    return { accountId: String(row.accountId), workerScript: String(row.workerScript), pagesScript: String(row.pagesScript),
      publicPagesScript: String(row.publicPagesScript), databaseId: String(row.databaseId), namespaceId: String(row.namespaceId), bucketName: String(row.bucketName) };
  } catch { return null; }
}
function queries(config: Configuration | null): Query[] {
  const metric = (key: string, group: string, unit: string, field: string, scale = 1) => ({key,group,unit,field,scale});
  return [
    { dataset:"workersInvocationsAdaptive", filter:{scriptName:config?.workerScript ?? ""}, fields:"sum { requests cpuTimeUs }",
      metrics:[metric("workerRequests","workers","requests","sum.requests"),metric("workerCpu","workers","ms","sum.cpuTimeUs",.001)], scope:config?.workerScript ?? "Workers" },
    ...[{script:config?.pagesScript,prefix:"pages"},{script:config?.publicPagesScript,prefix:"publicPages"}].map(({script,prefix})=>({
      dataset:"pagesFunctionsInvocationsAdaptiveGroups", filter:{scriptName:script ?? ""}, fields:"sum { requests } quantiles { cpuTimeP50 cpuTimeP99 }",
      metrics:[metric(prefix+"Requests","pages","requests","sum.requests"),metric(prefix+"CpuP50","pages","ms/request","quantiles.cpuTimeP50",.001),
        metric(prefix+"CpuP99","pages","ms/request","quantiles.cpuTimeP99",.001)], scope:script ?? "Pages Functions" })),
    { dataset:"d1AnalyticsAdaptiveGroups", filter:{databaseId:config?.databaseId ?? ""}, fields:"sum { rowsRead rowsWritten }",
      metrics:[metric("d1Read","d1","rows","sum.rowsRead"),metric("d1Write","d1","rows","sum.rowsWritten")], scope:config?.databaseId ?? "D1" },
    { dataset:"d1StorageAdaptiveGroups", filter:{databaseId:config?.databaseId ?? ""}, fields:"dimensions { datetime } max { databaseSizeBytes }", sample:true,
      metrics:[metric("d1Storage","d1","bytes","max.databaseSizeBytes")], scope:config?.databaseId ?? "D1" },
    { dataset:"durableObjectsInvocationsAdaptiveGroups", filter:{namespaceId:config?.namespaceId ?? ""}, fields:"sum { requests }",
      metrics:[metric("doRequests","durableObjects","requests","sum.requests")], scope:config?.namespaceId ?? "Durable Objects" },
    { dataset:"durableObjectsPeriodicGroups", filter:{namespaceId:config?.namespaceId ?? ""}, fields:"sum { duration rowsRead rowsWritten }",
      metrics:[metric("doDuration","durableObjects","GB-s","sum.duration"),metric("doRead","durableObjects","rows","sum.rowsRead"),
        metric("doWrite","durableObjects","rows","sum.rowsWritten")], scope:config?.namespaceId ?? "Durable Objects" },
    { dataset:"durableObjectsSqlStorageGroups", filter:{namespaceId:config?.namespaceId ?? ""}, fields:"dimensions { datetime } max { storedBytes }", sample:true,
      metrics:[metric("doStorage","durableObjects","bytes","max.storedBytes")], scope:config?.namespaceId ?? "Durable Objects" },
    { dataset:"r2OperationsAdaptiveGroups", filter:{bucketName:config?.bucketName ?? "",actionType_in:CLASS_A}, fields:"sum { requests }", monthly:true,
      metrics:[metric("r2ClassA","r2","operations","sum.requests")], scope:config?.bucketName ?? "R2" },
    { dataset:"r2OperationsAdaptiveGroups", filter:{bucketName:config?.bucketName ?? "",actionType_in:CLASS_B}, fields:"sum { requests }", monthly:true,
      metrics:[metric("r2ClassB","r2","operations","sum.requests")], scope:config?.bucketName ?? "R2" },
    ...["Standard","InfrequentAccess"].map(storageClass=>({ dataset:"r2StorageAdaptiveGroups", filter:{bucketName:config?.bucketName ?? "",storageClass},
      fields:"dimensions { datetime } max { payloadSize }", sample:true,
      metrics:[metric(storageClass === "Standard" ? "r2Storage" : "r2IaStorage","r2","bytes","max.payloadSize")],
      scope:`${config?.bucketName ?? "R2"} / ${storageClass}` }))
  ];
}
function windowFor(query: Query, now: number) {
  const date = new Date(now * 1000), day = Math.floor(now / 86400) * 86400;
  const start = query.monthly ? Date.UTC(date.getUTCFullYear(),date.getUTCMonth(),1) / 1000 : query.sample ? now - 86400 : day;
  return { start, end: Math.max(start,now - 300), rollover: query.sample ? null : query.monthly
    ? Date.UTC(date.getUTCFullYear(),date.getUTCMonth()+1,1) / 1000 : day + 86400 };
}
function blank(query: Query, now: number, state: State): Metric[] {
  const window = windowFor(query,now);
  return query.metrics.map(metric=>({key:metric.key,group:metric.group,unit:metric.unit,used:null,allowance:null,remaining:null,
    state,reason:state === "ok" ? null : state,scope:query.scope,periodStart:window.start,periodEnd:window.end,
    periodRolloverAt:window.rollover,quotaResetAt:null,sampledAt:null,lastSuccessAt:null}));
}
class ProviderError extends Error {
  constructor(readonly state: State) { super(state); }
}
async function readResponse(response: Response): Promise<Record<string, unknown>> {
  if (!response.ok) {
    await response.body?.cancel();
    throw new ProviderError([401,403].includes(response.status) ? "permission_denied" : "unavailable");
  }
  const reader = response.body?.getReader();
  if (!reader) throw new ProviderError("unavailable");
  let size = 0, value = "";
  const decoder = new TextDecoder();
  try {
    for (;;) {
      const chunk = await reader.read();
      if (chunk.done) break;
      size += chunk.value.byteLength;
      if (size > MAX_RESPONSE_BYTES) throw new ProviderError("unavailable");
      value += decoder.decode(chunk.value,{stream:true});
    }
    value += decoder.decode();
    return JSON.parse(value) as Record<string, unknown>;
  } finally { await reader.cancel().catch(()=>{}); reader.releaseLock(); }
}
export async function collectResourceUsage(config: Configuration, token: string, now: number, fetcher = fetch): Promise<Metric[]> {
  const specs = queries(config), result: Metric[] = [];
  const queryOne = async (spec: Query): Promise<Metric[]> => {
    const initial = blank(spec,now,"unavailable"), window = windowFor(spec,now);
    if (window.start === window.end) return blank(spec,now,"no_samples");
    const filter = { ...spec.filter, datetime_geq:new Date(window.start*1000).toISOString(), datetime_leq:new Date(window.end*1000).toISOString() };
    const fields = Object.entries(filter).map(([key,value])=>`${key}:${JSON.stringify(value)}`).join(",");
    const query = `{viewer{accounts(filter:{accountTag:${JSON.stringify(config.accountId)}}){metrics:${spec.dataset}(limit:1,filter:{${fields}}${spec.sample ? ",orderBy:[datetime_DESC]" : ""}){${spec.fields}}}}}`;
    try {
      // Workers supports manual/follow only; reject 3xx below without forwarding credentials.
      const response = await fetcher("https://api.cloudflare.com/client/v4/graphql",{method:"POST",redirect:"manual",
        headers:{Authorization:`Bearer ${token}`,"Content-Type":"application/json"},body:JSON.stringify({query}),signal:AbortSignal.timeout(7000)});
      const body = await readResponse(response);
      if (Array.isArray(body.errors) && body.errors.length) {
        const denied = body.errors.some(error=>/auth|permission|not allowed|not entitled/i.test(String(error?.message)));
        throw new ProviderError(denied ? "permission_denied" : "unavailable");
      }
      const data = body.data as {viewer?:{accounts?:Array<{metrics?:Array<Record<string,Record<string,unknown>>>}>}} | null;
      const accounts = data?.viewer?.accounts;
      if (!Array.isArray(accounts) || accounts.length !== 1 || !Array.isArray(accounts[0].metrics)) throw new ProviderError("unavailable");
      const rows = accounts[0].metrics;
      if (!rows.length) return blank(spec,now,"no_samples");
      if (rows.length !== 1) throw new ProviderError("unavailable");
      const row = rows[0];
      const sampledAt = spec.sample && typeof row.dimensions?.datetime === "string" ? Date.parse(row.dimensions.datetime)/1000 : null;
      if (spec.sample && (sampledAt === null || !Number.isFinite(sampledAt) || sampledAt < window.start || sampledAt > window.end)) throw new ProviderError("unavailable");
      return initial.map((metric,index)=>{
        const definition = spec.metrics[index], [aggregate,field] = definition.field.split(".");
        const value = row[aggregate]?.[field];
        if (typeof value !== "number" || !Number.isFinite(value) || value < 0) return metric;
        return {...metric,used:value*(definition.scale ?? 1),state:"ok",reason:null,lastSuccessAt:now,sampledAt};
      });
    } catch (error) { return blank(spec,now,error instanceof ProviderError ? error.state : "unavailable"); }
  };
  // Twelve fixed scoped queries at most, with only three provider requests in flight.
  for (let index=0;index<specs.length;index+=3) result.push(...(await Promise.all(specs.slice(index,index+3).map(queryOne))).flat());
  return result;
}
export async function resourceUsage(env: ResourceUsageEnv, now = Math.floor(Date.now()/1000), fetcher = fetch): Promise<Response> {
  const config = configuration(env);
  const empty = (state: State): Snapshot => ({metrics:queries(config).flatMap(query=>blank(query,now,state)),checkedAt:now});
  const respond = (snapshot: Snapshot, refreshing = false) => json({ok:true,...snapshot,generatedAt:now,refreshing,
    nextRefreshAt:snapshot.checkedAt+REFRESH_SECONDS,source:"Cloudflare GraphQL Analytics",scope:"configured-project-resources",
    plan:{name:null,state:"unavailable",reason:"Analytics access does not establish billing plan or account allowances"},
    githubActions:{state:"not_connected",used:null,allowance:null,remaining:null},
    safeguards:{clientReportsPerUtcDay:8,backendReportsPerUtcDay:1000,providerQuota:false},
    caveats:["Provider analytics can be delayed or sampled; a five-minute lag is excluded.",
      "R2 operations are calendar-month API counts, not an authoritative bill; storage is the latest sample, not GB-month.",
      "Pages CPU is per-invocation P50/P99, not total CPU. Project usage cannot establish account-wide remaining allowance."]});
  if (!config || !env.RESOURCE_USAGE_API_TOKEN) return respond(empty("not_configured"));
  const cacheKey = await sha256Text("resource-usage-v1:" + JSON.stringify(config));
  const previous = await env.DB.prepare("SELECT checked_at,lease_until,snapshot_json FROM admin_resource_usage_cache WHERE cache_key=?")
    .bind(cacheKey).first<CacheRow>();
  let snapshot: Snapshot = empty("refreshing");
  if (previous?.snapshot_json) {
    try { snapshot = JSON.parse(previous.snapshot_json) as Snapshot; } catch { /* Replace a corrupt cache rather than exposing it. */ }
    if (previous.checked_at > now-REFRESH_SECONDS) return respond(snapshot);
  }
  const lease = crypto.randomUUID();
  const claimed = await env.DB.prepare(`INSERT INTO admin_resource_usage_cache(cache_key,lease_until,lease) VALUES (?,?,?)
    ON CONFLICT(cache_key) DO UPDATE SET lease_until=excluded.lease_until,lease=excluded.lease WHERE lease_until<=?`)
    .bind(cacheKey,now+90,lease,now).run();
  if (!claimed.meta.changes) return respond({...snapshot,metrics:snapshot.metrics.map(metric=>metric.used === null ? metric : {...metric,state:"stale",reason:"refreshing"})},true);
  const metrics = await collectResourceUsage(config,env.RESOURCE_USAGE_API_TOKEN,now,fetcher);
  snapshot = {checkedAt:now,metrics:metrics.map(metric=>{
    const last = snapshot.metrics.find(row=>row.key === metric.key && row.used !== null && row.lastSuccessAt !== null);
    // Retain the old window as well as the value. Yesterday's count is not today's.
    return metric.state !== "ok" && last ? {...last,state:"stale",reason:metric.state} : metric;
  })};
  await env.DB.prepare("UPDATE admin_resource_usage_cache SET checked_at=?,lease_until=0,snapshot_json=? WHERE cache_key=? AND lease=?")
    .bind(now,JSON.stringify(snapshot),cacheKey,lease).run();
  return respond(snapshot);
}
