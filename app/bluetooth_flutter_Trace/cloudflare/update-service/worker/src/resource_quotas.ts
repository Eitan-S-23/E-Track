import { analyticsAccount, nonnegative, ProviderError, providerFailure, providerRead, UsageState } from "./resource_provider";

interface BillingWindow { start: number; end: number }
export interface ResourcePlan {
  product: "workers" | "r2";
  name: string | null;
  state: UsageState;
  reason: string | null;
  basis: "subscription" | "default_free" | "unknown";
  periodStart: number | null;
  periodEnd: number | null;
  lastSuccessAt: number | null;
}
export interface AccountQuota {
  key: string;
  group: string;
  unit: string;
  used: number | null;
  allowance: number | null;
  remaining: number | null;
  overage: number | null;
  limitKind: "hard" | "included" | "per_invocation" | "unknown";
  state: UsageState;
  reason: string | null;
  scope: "cloudflare-account" | "cloudflare-account/Standard";
  planName: string | null;
  periodStart: number | null;
  periodEnd: number | null;
  quotaResetAt: number | null;
  sampledAt: number | null;
  lastSuccessAt: number | null;
  estimation: "analytics" | "daily_peaks_30_days" | "inventory" | null;
  coverage: { expectedDays: number; observedDays: number; bucketDays: number; complete: boolean; normalizationDays: number } | null;
  pricingUrl: string;
}
export interface AccountQuotaSnapshot { plans: ResourcePlan[]; quotas: AccountQuota[]; checkedAt: number }
interface Read<T> { value: T | null; state: UsageState; reason: string | null }
interface Subscription { state: string; id: string; name: string; contract: boolean; period: BillingWindow | null; end: number | null }

const API = "https://api.cloudflare.com/client/v4";
export const R2_STORAGE_ROW_LIMIT = 1000;
const PRICING = {
  workers:"https://developers.cloudflare.com/workers/platform/pricing/",
  d1:"https://developers.cloudflare.com/d1/platform/pricing/",
  durableObjects:"https://developers.cloudflare.com/durable-objects/platform/pricing/",
  r2:"https://developers.cloudflare.com/r2/pricing/"
};
export const R2_CLASS_A = ["ListBuckets", "PutBucket", "ListObjects", "PutObject", "CopyObject", "CompleteMultipartUpload",
  "CreateMultipartUpload", "LifecycleStorageTierTransition", "ListMultipartUploads", "UploadPart", "UploadPartCopy",
  "ListParts", "PutBucketEncryption", "PutBucketCors", "PutBucketLifecycleConfiguration"];
export const R2_CLASS_B = ["HeadBucket", "HeadObject", "GetObject", "UsageSummary", "GetBucketEncryption", "GetBucketLocation",
  "GetBucketCors", "GetBucketLifecycleConfiguration"];

function object(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new ProviderError("unavailable");
  return value as Record<string, unknown>;
}
async function attempt<T>(read: () => Promise<T>): Promise<Read<T>> {
  try { return {value:await read(),state:"ok",reason:null}; }
  catch (error) { return {value:null,...providerFailure(error)}; }
}
function timestamp(value: unknown): number | null {
  if (typeof value !== "string" || value.length > 40) return null;
  const parsed = Date.parse(value)/1000;
  return Number.isSafeInteger(parsed) && parsed > 0 ? parsed : null;
}
function billingWindow(row: Record<string, unknown>, now: number): BillingWindow | null {
  const start = timestamp(row.current_period_start), end = timestamp(row.current_period_end);
  if (row.frequency !== "monthly" || start === null || end === null || start > now || end <= now ||
      end-start < 27*86400 || end-start > 32*86400) return null;
  return {start,end};
}
function unknownPlan(product: ResourcePlan["product"], state: UsageState, reason: string = state): ResourcePlan {
  return {product,name:null,state,reason,basis:"unknown",periodStart:null,periodEnd:null,lastSuccessAt:null};
}
function knownPlan(product: ResourcePlan["product"], name: string, basis: ResourcePlan["basis"], now: number, period: BillingWindow | null): ResourcePlan {
  return {product,name,state:"ok",reason:null,basis,periodStart:period?.start ?? null,periodEnd:period?.end ?? null,lastSuccessAt:now};
}
async function readPlans(accountId: string, token: string, now: number, fetcher: typeof fetch): Promise<ResourcePlan[]> {
  const prefix = `${API}/accounts/${accountId}`;
  const [subscriptions, account] = await Promise.all([
    attempt(async()=>{
      const body = await providerRead(prefix+"/subscriptions",token,fetcher);
      if (body.success !== true || !Array.isArray(body.result) || body.result.length > 100) throw new ProviderError("unavailable");
      if (body.result_info && object(body.result_info).total_count !== undefined &&
          object(body.result_info).total_count !== body.result.length) throw new ProviderError("unavailable","incomplete_coverage");
      // This endpoint is SinglePage, not the paginated D1 inventory. Never expose raw billing records.
      return body.result.map(value=>{
        const row = object(value), rate = object(row.rate_plan);
        if (typeof rate.id !== "string" || !/^[a-zA-Z0-9_-]{1,100}$/.test(rate.id) || typeof row.state !== "string") {
          throw new ProviderError("unavailable","unknown_plan");
        }
        return {id:rate.id.toLowerCase(),name:typeof rate.public_name === "string" ? rate.public_name.slice(0,120) : rate.id,
          state:row.state.toLowerCase(),contract:rate.is_contract === true,period:billingWindow(row,now),end:timestamp(row.current_period_end)} as Subscription;
      });
    }),
    attempt(async()=>{
      const body = await providerRead(prefix,token,fetcher);
      if (body.success !== true) throw new ProviderError("unavailable");
      return object(body.result).type;
    })
  ]);
  if (!subscriptions.value) return ["workers","r2"].map(product=>unknownPlan(product as ResourcePlan["product"],subscriptions.state,subscriptions.reason ?? subscriptions.state));
  const current = subscriptions.value.filter(row=>!["expired","cancelled","canceled","failed"].includes(row.state) || row.end === null || row.end > now);
  const workers = current.filter(row=>/worker|durable|d1|enterprise/i.test(row.id+" "+row.name));
  let workerPlan: ResourcePlan;
  if (workers.length === 1 && !workers[0].contract && ["paid","provisioned","trial"].includes(workers[0].state) &&
      ["workers_paid","workers_standard","worker_standard"].includes(workers[0].id)) {
    workerPlan = knownPlan("workers","Workers Paid / Standard","subscription",now,workers[0].period);
  } else if (!workers.length && account.value === "standard" && !current.some(row=>row.contract)) {
    // Cloudflare documents Free as the default. R2/Teams subscriptions do not upgrade Workers.
    workerPlan = knownPlan("workers","Workers Free","default_free",now,null);
  } else workerPlan = unknownPlan("workers",account.state !== "ok" ? account.state : "unavailable",account.state !== "ok" ? account.reason ?? account.state : "unknown_plan");
  const r2 = current.filter(row=>/\br2\b/i.test(row.name) || row.id.startsWith("r2_"));
  const r2Plan = r2.length === 1 && r2[0].id === "r2_paid" && !r2[0].contract && ["paid","provisioned","trial"].includes(r2[0].state)
    ? knownPlan("r2","R2 Paid / Standard free tier","subscription",now,r2[0].period)
    : unknownPlan("r2","unavailable","unknown_plan");
  return [workerPlan,r2Plan];
}

async function databaseStorage(accountId: string, token: string, fetcher: typeof fetch): Promise<number> {
  let total = 0, count = 0;
  const seen = new Set<string>();
  for (let page=1;page<=3;page++) {
    const body = await providerRead(`${API}/accounts/${accountId}/d1/database?per_page=100&page=${page}`,token,fetcher);
    if (body.success !== true || !Array.isArray(body.result) || body.result.length > 100) throw new ProviderError("unavailable");
    for (const value of body.result) {
      const row = object(value), size = nonnegative(row.file_size);
      if (typeof row.uuid !== "string" || !row.uuid.length || row.uuid.length > 100 || seen.has(row.uuid) || size === null || !Number.isSafeInteger(size)) {
        throw new ProviderError("unavailable","incomplete_coverage");
      }
      seen.add(row.uuid); total += size; count++;
      if (!Number.isSafeInteger(total)) throw new ProviderError("unavailable","invalid_usage");
    }
    const info = body.result_info === undefined ? null : object(body.result_info);
    const expected = info?.total_count === undefined ? null : nonnegative(info.total_count);
    const pages = info?.total_pages === undefined ? null : nonnegative(info.total_pages);
    if (info && (info.page !== undefined && info.page !== page || info.total_count !== undefined && expected === null ||
        expected !== null && (!Number.isSafeInteger(expected) || expected < count) ||
        info.count !== undefined && info.count !== body.result.length || info.total_pages !== undefined && (pages === null || !Number.isSafeInteger(pages)))) {
      throw new ProviderError("unavailable","incomplete_coverage");
    }
    if (expected === count && pages !== null && pages > page || pages !== null && pages <= page && expected !== null && expected !== count ||
        !body.result.length && (expected !== null && expected !== count || pages !== null && pages > page)) {
      throw new ProviderError("unavailable","incomplete_coverage");
    }
    const more = expected !== null ? expected > count : pages !== null ? pages > page : body.result.length === 100;
    if (!more) {
      if (expected !== null && expected !== count) throw new ProviderError("unavailable","incomplete_coverage");
      return total / 1e9;
    }
  }
  throw new ProviderError("unavailable","incomplete_coverage");
}

function layout(plans: ResourcePlan[], now: number, state: UsageState = "unavailable"): AccountQuota[] {
  const worker = plans[0], r2 = plans[1], free = worker.name === "Workers Free", paid = worker.name === "Workers Paid / Standard";
  const day = Math.floor(now/86400)*86400;
  const start = free ? day : paid ? worker.periodStart : day;
  const reset = free ? day+86400 : paid ? worker.periodEnd : null;
  const kind = free ? "hard" : paid ? "included" : "unknown";
  const definitions: Array<[string,keyof typeof PRICING,string,number|null,AccountQuota["limitKind"]]> = [
    ["accountRequests","workers","requests",free ? 100000 : paid ? 10000000 : null,kind],
    ["accountCpuLimit","workers","ms/invocation",free ? 10 : null,"per_invocation"],
    ["accountD1Read","d1","rows",free ? 5000000 : paid ? 25000000000 : null,kind],
    ["accountD1Write","d1","rows",free ? 100000 : paid ? 50000000 : null,kind],
    ["accountD1Storage","d1",paid ? "GB-month" : "GB",free || paid ? 5 : null,kind],
    ["accountDoRequests","durableObjects","requests",free ? 100000 : paid ? 1000000 : null,kind],
    ["accountDoDuration","durableObjects","GB-s",free ? 13000 : paid ? 400000 : null,kind],
    ["accountDoRead","durableObjects","rows",free ? 5000000 : paid ? 25000000000 : null,kind],
    ["accountDoWrite","durableObjects","rows",free ? 100000 : paid ? 50000000 : null,kind],
    ["accountDoStorage","durableObjects",paid ? "GB-month" : "GB",free || paid ? 5 : null,kind],
    ["accountR2ClassA","r2","operations",r2.name ? 1000000 : null,"included"],
    ["accountR2ClassB","r2","operations",r2.name ? 10000000 : null,"included"],
    ["accountR2Storage","r2","GB-month",r2.name ? 10 : null,"included"]
  ];
  return definitions.map(([key,group,unit,allowance,limitKind])=>{
    const plan = group === "r2" ? r2 : worker;
    const capacity = key === "accountD1Storage" || key === "accountDoStorage" || key === "accountCpuLimit";
    const periodStart = group === "r2" ? r2.periodStart : capacity ? (free ? now : null) : start;
    const end = group === "r2" ? r2.periodEnd : reset;
    return {key,group,unit,used:null,allowance,remaining:null,overage:null,limitKind:allowance === null && limitKind !== "per_invocation" ? "unknown" : limitKind,
      state,reason:plan.state !== "ok" ? plan.reason : state,scope:group === "r2" ? "cloudflare-account/Standard" : "cloudflare-account",
      planName:plan.name,periodStart,periodEnd:capacity ? (free ? now : null) : periodStart === null || end === null ? null : Math.max(periodStart,Math.min(end,now-300)),
      quotaResetAt:capacity ? null : end,sampledAt:null,lastSuccessAt:null,estimation:null,coverage:null,pricingUrl:PRICING[group]} as AccountQuota;
  });
}
export function emptyAccountQuotas(now: number, state: UsageState): AccountQuotaSnapshot {
  const plans = [unknownPlan("workers",state),unknownPlan("r2",state)];
  return {plans,quotas:layout(plans,now,state),checkedAt:now};
}
function measured(quota: AccountQuota, value: number, now: number, estimation: AccountQuota["estimation"] = "analytics"): AccountQuota {
  if (nonnegative(value) === null) throw new ProviderError("unavailable","invalid_usage");
  return {...quota,used:value,remaining:quota.allowance === null ? null : Math.max(0,quota.allowance-value),
    overage:quota.allowance === null ? null : Math.max(0,value-quota.allowance),state:"ok",reason:quota.allowance === null ? "unknown_plan" : null,
    lastSuccessAt:now,estimation};
}
function fail(quota: AccountQuota, error: unknown): AccountQuota { return {...quota,...providerFailure(error)}; }
function filterFor(quota: AccountQuota) {
  if (quota.periodStart === null || quota.periodEnd === null) throw new ProviderError("unavailable","unknown_billing_period");
  if (quota.periodStart === quota.periodEnd) throw new ProviderError("no_samples");
  return `datetime_geq:${JSON.stringify(new Date(quota.periodStart*1000).toISOString())},datetime_leq:${JSON.stringify(new Date(quota.periodEnd*1000).toISOString())}`;
}
function sumField(account: Record<string, unknown>, alias: string, field: string): number {
  const rows = account[alias];
  if (!Array.isArray(rows)) throw new ProviderError("unavailable");
  if (!rows.length) throw new ProviderError("no_samples");
  if (rows.length !== 1) throw new ProviderError("unavailable");
  const value = nonnegative(object(object(rows[0]).sum)[field]);
  if (value === null || field !== "duration" && !Number.isSafeInteger(value)) throw new ProviderError("unavailable","invalid_usage");
  return value;
}
async function accountQuery(accountId: string, token: string, fields: string, fetcher: typeof fetch) {
  const query = `{viewer{accounts(filter:{accountTag:${JSON.stringify(accountId)}}){${fields}}}}`;
  return analyticsAccount(await providerRead(API+"/graphql",token,fetcher,query));
}

export function storageGbMonth(rows: unknown[], quota: AccountQuota): { used: number; coverage: NonNullable<AccountQuota["coverage"]> } {
  if (quota.periodStart === null || quota.periodEnd === null || quota.periodStart%86400 !== 0 || rows.length >= R2_STORAGE_ROW_LIMIT) {
    throw new ProviderError("unavailable","incomplete_coverage");
  }
  if (!rows.length) throw new ProviderError("no_samples");
  const first = quota.periodStart/86400, last = Math.floor(quota.periodEnd/86400), seen = new Set<string>(), days = new Set<number>();
  let sum = 0;
  for (const value of rows) {
    const row = object(value), dims = object(row.dimensions);
    if (typeof dims.date !== "string" || !/^\d{4}-\d{2}-\d{2}$/.test(dims.date) || typeof dims.bucketName !== "string") {
      throw new ProviderError("unavailable","incomplete_coverage");
    }
    const day = Date.parse(dims.date+"T00:00:00Z")/86400000, bytes = nonnegative(object(row.max).payloadSize), key = `${day}:${dims.bucketName}`;
    if (!Number.isSafeInteger(day) || new Date(day*86400000).toISOString().slice(0,10) !== dims.date || day < first || day > last ||
        bytes === null || !Number.isSafeInteger(bytes) || seen.has(key)) {
      throw new ProviderError("unavailable","incomplete_coverage");
    }
    seen.add(key); days.add(day); sum += bytes;
    if (!Number.isSafeInteger(sum)) throw new ProviderError("unavailable","invalid_usage");
  }
  const expectedDays = last-first+1;
  if (days.size !== expectedDays) throw new ProviderError("unavailable","incomplete_coverage");
  // Official R2 GB-month examples use 30 daily peaks. The current day and billing estimate are provisional.
  return {used:sum/1e9/30,coverage:{expectedDays,observedDays:days.size,bucketDays:rows.length,complete:true,normalizationDays:30}};
}

export async function collectAccountQuotas(accountId: string, token: string, now: number, fetcher = fetch): Promise<AccountQuotaSnapshot> {
  if (!/^[a-f0-9]{32}$/.test(accountId) || !token) return emptyAccountQuotas(now,"not_configured");
  const [plans, inventory] = await Promise.all([readPlans(accountId,token,now,fetcher),attempt(()=>databaseStorage(accountId,token,fetcher))]);
  let quotas = layout(plans,now);
  const find = (key: string) => quotas.find(quota=>quota.key === key)!;
  const jobs: Array<() => Promise<AccountQuota[]>> = [];
  const count = (keys: string[], fields: (filter: string)=>string, values: (account: Record<string, unknown>)=>number[]) => {
    jobs.push(async()=>{
      const selected = keys.map(find);
      try {
        const account = await accountQuery(accountId,token,fields(filterFor(selected[0])),fetcher);
        return values(account).map((value,index)=>measured(selected[index],value,now));
      } catch (error) { return selected.map(quota=>fail(quota,error)); }
    });
  };
  count(["accountRequests"],filter=>`workers:workersInvocationsAdaptive(limit:1,filter:{${filter}}){sum{requests}} pages:pagesFunctionsInvocationsAdaptiveGroups(limit:1,filter:{${filter}}){sum{requests}}`,
    account=>[sumField(account,"workers","requests")+sumField(account,"pages","requests")]);
  count(["accountD1Read","accountD1Write"],filter=>`usage:d1AnalyticsAdaptiveGroups(limit:1,filter:{${filter}}){sum{rowsRead rowsWritten}}`,
    account=>[sumField(account,"usage","rowsRead"),sumField(account,"usage","rowsWritten")]);
  count(["accountDoRequests"],filter=>`usage:durableObjectsInvocationsAdaptiveGroups(limit:1,filter:{${filter}}){sum{requests}}`,
    account=>[sumField(account,"usage","requests")]);
  count(["accountDoDuration","accountDoRead","accountDoWrite"],filter=>`usage:durableObjectsPeriodicGroups(limit:1,filter:{${filter}}){sum{duration rowsRead rowsWritten}}`,
    account=>[sumField(account,"usage","duration"),sumField(account,"usage","rowsRead"),sumField(account,"usage","rowsWritten")]);
  for (const [key,actions] of [["accountR2ClassA",R2_CLASS_A],["accountR2ClassB",R2_CLASS_B]] as const) {
    count([key],filter=>`usage:r2OperationsAdaptiveGroups(limit:1,filter:{${filter},storageClass:"Standard",actionType_in:${JSON.stringify(actions)}}){sum{requests}}`,
      account=>[sumField(account,"usage","requests")]);
  }
  jobs.push(async()=>{
    const quota = find("accountR2Storage");
    try {
      const account = await accountQuery(accountId,token,`usage:r2StorageAdaptiveGroups(limit:${R2_STORAGE_ROW_LIMIT},filter:{${filterFor(quota)},storageClass:"Standard"}){dimensions{date bucketName}max{payloadSize}}`,fetcher);
      if (!Array.isArray(account.usage)) throw new ProviderError("unavailable");
      const result = storageGbMonth(account.usage,quota);
      return [{...measured(quota,result.used,now,"daily_peaks_30_days"),coverage:result.coverage}];
    } catch (error) { return [fail(quota,error)]; }
  });
  const cpu = find("accountCpuLimit"), storage = find("accountD1Storage"), doStorage = find("accountDoStorage");
  const fixed: AccountQuota[] = [
    {...cpu,state:cpu.allowance === null ? "unavailable" : "ok",reason:"per_invocation",lastSuccessAt:plans[0].lastSuccessAt},
    {...doStorage,reason:"unsupported_meter",lastSuccessAt:plans[0].lastSuccessAt},
    storage.unit === "GB-month" ? {...storage,reason:"unsupported_meter",lastSuccessAt:plans[0].lastSuccessAt}
      : inventory.value === null ? {...storage,state:inventory.state,reason:inventory.reason}
      : {...measured(storage,inventory.value,now,"inventory"),sampledAt:now}
  ];
  const measuredQuotas: AccountQuota[] = [];
  // Initial subscriptions/account/inventory reads and subsequent batches never exceed three in flight.
  for (let index=0;index<jobs.length;index+=3) measuredQuotas.push(...(await Promise.all(jobs.slice(index,index+3).map(job=>job()))).flat());
  quotas = quotas.map(quota=>[...fixed,...measuredQuotas].find(row=>row.key === quota.key) ?? quota);
  return {plans,quotas,checkedAt:now};
}

export function retainAccountQuotas(current: AccountQuotaSnapshot, previous: AccountQuotaSnapshot): AccountQuotaSnapshot {
  return {...current,plans:current.plans.map(plan=>{
    const last = previous.plans.find(row=>row.product === plan.product && row.lastSuccessAt !== null && row.name !== null);
    return plan.state !== "ok" && last ? {...last,state:"stale",reason:plan.reason} : plan;
  }),quotas:current.quotas.map(quota=>{
    const last = previous.quotas.find(row=>row.key === quota.key && (row.used !== null || row.allowance !== null) && row.lastSuccessAt !== null);
    return quota.used === null && quota.state !== "ok" && last && (last.used !== null || quota.lastSuccessAt === null)
      ? {...last,state:"stale",reason:quota.reason} : quota;
  })};
}
