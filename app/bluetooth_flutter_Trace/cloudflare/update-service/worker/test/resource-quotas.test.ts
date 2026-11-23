import { describe, expect, it, vi } from "vitest";
import { collectAccountQuotas, emptyAccountQuotas, retainAccountQuotas, R2_STORAGE_ROW_LIMIT, storageGbMonth } from "../src/resource_quotas";

const accountId = "a".repeat(32), token = "fixture-private-token";
const now = Date.parse("2026-11-23T12:00:00Z")/1000;
const start = "2026-10-28T00:00:00Z", end = "2026-11-28T00:00:00Z";
const subscription = (id = "r2_paid", publicName = "R2 Paid") => ({state:"Paid",frequency:"monthly",
  current_period_start:start,current_period_end:end,rate_plan:{id,public_name:publicName,is_contract:false},
  component_values:[{name:"r2_storage",value:1}],client_secrets:{fixture:"must-not-be-returned"}});
function storageRows(bytes = 1e9) {
  return Array.from({length:27},(_,index)=>({dimensions:{date:new Date(Date.parse(start)+index*86400000).toISOString().slice(0,10),bucketName:"other-project"},
    max:{payloadSize:bytes}}));
}
const accountBody = (value: object) => ({data:{viewer:{accounts:[value]}},errors:null});
type Options = { subscriptions?: object[]; accountType?: string; inventory?: object[];
  override?: (url: string, query: string)=>Response | undefined };
function provider(options: Options = {}) {
  return vi.fn<typeof fetch>(async(url,init)=>{
    const route = String(url), query = init?.body ? JSON.parse(String(init.body)).query as string : "";
    expect(init?.redirect).toBe("manual");
    expect(init?.headers).toMatchObject({Authorization:`Bearer ${token}`});
    const override = options.override?.(route,query);
    if (override) return override;
    if (route.endsWith("/subscriptions")) return Response.json({success:true,result:options.subscriptions ?? [subscription(),subscription("teams_free","Teams Free Base")]});
    if (route.includes("/d1/database?")) {
      const rows = options.inventory ?? [{uuid:"database-1",file_size:1e6},{uuid:"database-2",file_size:2e6}];
      return Response.json({success:true,result:rows,result_info:{page:1,total_count:rows.length}});
    }
    if (!query) return Response.json({success:true,result:{type:options.accountType ?? "standard"}});
    expect(route).toBe("https://api.cloudflare.com/client/v4/graphql");
    expect(query).toContain(`accountTag:"${accountId}"`);
    expect(query).not.toMatch(/scriptName:|databaseId:|namespaceId:|bucketName:/);
    if (query.includes("workers:")) return Response.json(accountBody({workers:[{sum:{requests:5}}],pages:[{sum:{requests:7}}]}));
    if (query.includes("r2StorageAdaptiveGroups")) return Response.json(accountBody({usage:storageRows()}));
    return Response.json(accountBody({usage:[{sum:{requests:9,rowsRead:100,rowsWritten:20,duration:.25}}]}));
  });
}
const get = (value: Awaited<ReturnType<typeof collectAccountQuotas>>, key: string) => value.quotas.find(row=>row.key === key)!;

describe("account allowances, distinct from project analytics and invoices",()=>{
  it("establishes documented default Free only with complete subscriptions/account metadata, not from R2 Paid",async()=>{
    const fetcher = provider(), value = await collectAccountQuotas(accountId,token,now,fetcher);
    expect(value.plans[0]).toMatchObject({name:"Workers Free",basis:"default_free",state:"ok"});
    expect(value.plans[1]).toMatchObject({name:"R2 Paid / Standard free tier",basis:"subscription"});
    expect(get(value,"accountRequests")).toMatchObject({used:12,allowance:100000,remaining:99988,limitKind:"hard",scope:"cloudflare-account"});
    expect(get(value,"accountD1Read")).toMatchObject({allowance:5000000,remaining:4999900});
    expect(get(value,"accountDoDuration")).toMatchObject({used:.25,allowance:13000,remaining:12999.75,unit:"GB-s"});
    expect(get(value,"accountD1Storage")).toMatchObject({used:.003,allowance:5,remaining:4.997,unit:"GB",estimation:"inventory"});
    expect(get(value,"accountCpuLimit")).toMatchObject({used:null,allowance:10,remaining:null,limitKind:"per_invocation"});
    expect(fetcher).toHaveBeenCalledTimes(10);
    expect(JSON.stringify(value)).not.toMatch(/fixture-private-token|client_secrets|must-not-be-returned|component_values/);
  });
  it("uses the actual renewal window, Standard-only operations and accrued daily peaks rather than current bytes",async()=>{
    const fetcher = provider(), value = await collectAccountQuotas(accountId,token,now,fetcher);
    expect(get(value,"accountR2ClassA")).toMatchObject({used:9,allowance:1000000,remaining:999991,limitKind:"included",periodStart:Date.parse(start)/1000,quotaResetAt:Date.parse(end)/1000});
    expect(get(value,"accountR2ClassB").allowance).toBe(10000000);
    const r2 = fetcher.mock.calls.filter(([,init])=>String(init?.body).includes("r2"));
    expect(r2).toHaveLength(3);
    for (const [,init] of r2) {
      const query = JSON.parse(String(init?.body)).query;
      expect(query).toContain('storageClass:"Standard"');expect(query).toContain(`datetime_geq:${JSON.stringify(new Date(start).toISOString())}`);
      expect(query).not.toContain("InfrequentAccess");expect(query).not.toContain('datetime_geq:"2026-11-01');
    }
    expect(get(value,"accountR2Storage")).toMatchObject({used:.9,allowance:10,remaining:9.1,unit:"GB-month",estimation:"daily_peaks_30_days",
      coverage:{expectedDays:27,observedDays:27,bucketDays:27,complete:true,normalizationDays:30}});
    expect(get(value,"accountDoStorage")).toMatchObject({allowance:5,used:null,remaining:null,reason:"unsupported_meter"});
  });
  it.each([
    {accountType:"enterprise"},
    {subscriptions:[subscription(),subscription("workers_legacy","Workers Unbound")]},
    {subscriptions:[subscription(),{...subscription("workers_paid","Workers Paid"),state:"Cancelled"}]},
    {subscriptions:[subscription(),{...subscription("enterprise_custom","Enterprise"),rate_plan:{id:"enterprise_custom",public_name:"Contract",is_contract:true}}]}
  ])("does not invent default limits for an unknown, contracted, enterprise or not-yet-ended canceled plan: %j",async options=>{
    const value = await collectAccountQuotas(accountId,token,now,provider(options));
    expect(value.plans[0]).toMatchObject({name:null,state:"unavailable",reason:"unknown_plan"});
    expect(value.quotas.filter(row=>row.group !== "r2").every(row=>row.allowance === null && row.remaining === null)).toBe(true);
  });
  it("uses monthly included usage rather than daily hard limits for a recognized Paid/Standard plan",async()=>{
    const value = await collectAccountQuotas(accountId,token,now,provider({subscriptions:[subscription(),subscription("workers_paid","Workers Paid")],
      override:(_url,query)=>query.includes("workers:") ? Response.json(accountBody({workers:[{sum:{requests:11000000}}],pages:[{sum:{requests:2000000}}]})) : undefined}));
    expect(get(value,"accountRequests")).toMatchObject({used:13000000,allowance:10000000,remaining:0,overage:3000000,limitKind:"included",periodStart:Date.parse(start)/1000});
    expect(get(value,"accountD1Read").allowance).toBe(25000000000);
    expect(get(value,"accountD1Storage")).toMatchObject({used:null,allowance:5,remaining:null,unit:"GB-month",reason:"unsupported_meter"});
    expect(get(value,"accountDoDuration").allowance).toBe(400000);
  });
  it("keeps real zero distinct from absent analytics and unsupported storage",async()=>{
    const value = await collectAccountQuotas(accountId,token,now,provider({inventory:[],override:(_url,query)=>{
      if (query.includes("workers:")) return Response.json(accountBody({workers:[{sum:{requests:0}}],pages:[{sum:{requests:0}}]}));
      if (query.includes("r2Storage")) return Response.json(accountBody({usage:storageRows(0)}));
      if (query.includes("durableObjectsInvocations")) return Response.json(accountBody({usage:[]}));
      return undefined;
    }}));
    expect(get(value,"accountRequests")).toMatchObject({used:0,remaining:100000,state:"ok"});
    expect(get(value,"accountD1Storage")).toMatchObject({used:0,remaining:5,state:"ok"});
    expect(get(value,"accountR2Storage")).toMatchObject({used:0,remaining:10,state:"ok"});
    expect(get(value,"accountDoRequests")).toMatchObject({used:null,remaining:null,state:"no_samples"});
  });
  it("requires both Workers and Pages request datasets, never treating the missing half as zero",async()=>{
    const value = await collectAccountQuotas(accountId,token,now,provider({override:(_url,query)=>query.includes("workers:")
      ? Response.json(accountBody({workers:[{sum:{requests:5}}],pages:[]})) : undefined}));
    expect(get(value,"accountRequests")).toMatchObject({used:null,allowance:100000,remaining:null,state:"no_samples"});
  });
  it.each([{}, {current_period_start:"2026-11-24T00:00:00Z"}, {current_period_end:"2026-11-01T00:00:00Z"}, {frequency:"yearly"}])(
    "does not substitute calendar-month R2 balances when billing period is missing or invalid: %j",async fields=>{
      const row = Object.keys(fields).length ? {...subscription(),...fields} : {...subscription(),current_period_start:undefined};
      const fetcher = provider({subscriptions:[row]}), value = await collectAccountQuotas(accountId,token,now,fetcher);
      expect(get(value,"accountR2ClassA")).toMatchObject({used:null,remaining:null,reason:"unknown_billing_period",quotaResetAt:null});
      expect(fetcher.mock.calls.some(([,init])=>String(init?.body).includes("r2Operations"))).toBe(false);
    });
  it.each(["missing", "duplicate", "cap", "overflow"])("rejects incomplete or invalid storage coverage: %s",async mode=>{
    const rows = storageRows();
    if (mode === "missing") rows.pop();
    if (mode === "duplicate") rows.push(rows[0]);
    if (mode === "cap") rows.push(...Array.from({length:R2_STORAGE_ROW_LIMIT-rows.length},()=>rows[0]));
    if (mode === "overflow") rows[0].max.payloadSize = Number.MAX_SAFE_INTEGER+1;
    const value = await collectAccountQuotas(accountId,token,now,provider({override:(_url,query)=>query.includes("r2Storage") ? Response.json(accountBody({usage:rows})) : undefined}));
    expect(get(value,"accountR2Storage")).toMatchObject({used:null,allowance:10,remaining:null,state:"unavailable"});
    expect(get(value,"accountR2ClassA").state).toBe("ok");
  });
  it("adds every bucket-day, not just the largest bucket or latest sample",()=>{
    const quota = {...emptyAccountQuotas(now,"unavailable").quotas.find(row=>row.key === "accountR2Storage")!,periodStart:Date.parse(start)/1000,periodEnd:now-300};
    const rows = [...storageRows(),...storageRows(2e9).map(row=>({...row,dimensions:{...row.dimensions,bucketName:"second-project"}}))];
    expect(storageGbMonth(rows,quota).used).toBe(2.7);
    expect(storageGbMonth(rows,quota).coverage.bucketDays).toBe(54);
  });
  it("reads a second inventory page, validates total coverage and rejects a duplicated/truncated inventory",async()=>{
    for (const mode of ["complete","duplicate","truncated"]) {
      const fetcher = provider({override:(url)=>{
        if (!url.includes("/d1/database?")) return undefined;
        const page = Number(new URL(url).searchParams.get("page"));
        const rows = page === 1 ? Array.from({length:100},(_,index)=>({uuid:`db-${index}`,file_size:1e6}))
          : mode === "truncated" ? [] : [{uuid:mode === "duplicate" ? "db-0" : "db-100",file_size:1e6}];
        return Response.json({success:true,result:rows,result_info:{page,total_count:101}});
      }});
      const value = await collectAccountQuotas(accountId,token,now,fetcher);
      if (mode === "complete") expect(get(value,"accountD1Storage")).toMatchObject({used:.101,remaining:4.899,state:"ok"});
      else expect(get(value,"accountD1Storage")).toMatchObject({used:null,remaining:null,reason:"incomplete_coverage"});
    }
  });
  it("caps inventory requests and does not report an unenumerated account as empty",async()=>{
    const fetcher = provider({override:url=>{
      if (!url.includes("/d1/database?")) return undefined;
      const page = Number(new URL(url).searchParams.get("page"));
      return Response.json({success:true,result:Array.from({length:100},(_,index)=>({uuid:`db-${page}-${index}`,file_size:0})),result_info:{page,total_count:301}});
    }});
    const value = await collectAccountQuotas(accountId,token,now,fetcher);
    expect(fetcher.mock.calls.filter(([url])=>String(url).includes("/d1/database?")).length).toBe(3);
    expect(get(value,"accountD1Storage")).toMatchObject({used:null,remaining:null,state:"unavailable",reason:"incomplete_coverage"});
  });
  it("honors page-count-only inventories and rejects inconsistent count metadata",async()=>{
    const value = await collectAccountQuotas(accountId,token,now,provider({override:url=>{
      if (!url.includes("/d1/database?")) return undefined;
      const page = Number(new URL(url).searchParams.get("page"));
      return Response.json({success:true,result:[{uuid:`db-${page}`,file_size:1e6}],result_info:{page,count:1,total_pages:2}});
    }}));
    expect(get(value,"accountD1Storage")).toMatchObject({used:.002,remaining:4.998});
    const inconsistent = await collectAccountQuotas(accountId,token,now,provider({override:url=>url.includes("/d1/database?")
      ? Response.json({success:true,result:[{uuid:"db",file_size:0}],result_info:{page:1,count:2,total_count:1}}) : undefined}));
    expect(get(inconsistent,"accountD1Storage")).toMatchObject({used:null,remaining:null,reason:"incomplete_coverage"});
  });
  it.each([403,503,302])("preserves old values, plan and actual billing/reset windows on failed rollover without forwarding redirects: HTTP %s",async status=>{
    const previous = await collectAccountQuotas(accountId,token,now,provider());
    const fetcher = vi.fn<typeof fetch>(async(_url,init)=>{
      expect(init?.redirect).toBe("manual");return new Response(null,{status,headers:{Location:"https://other.example.test/"}});
    });
    const current = await collectAccountQuotas(accountId,token,now+10*86400,fetcher);
    const retained = retainAccountQuotas(current,previous), r2 = get(retained,"accountR2ClassA");
    expect(r2).toMatchObject({state:"stale",used:9,remaining:999991,periodStart:Date.parse(start)/1000,quotaResetAt:Date.parse(end)/1000,lastSuccessAt:now});
    expect(retained.plans[0]).toMatchObject({name:"Workers Free",state:"stale",lastSuccessAt:now});
    expect(get(retained,"accountRequests").periodStart).toBe(get(previous,"accountRequests").periodStart);
    expect(get(retained,"accountCpuLimit")).toMatchObject({allowance:10,state:"stale"});
    expect(fetcher.mock.calls.every(([url])=>String(url).startsWith("https://api.cloudflare.com/client/v4/"))).toBe(true);
  });
  it("does not obtain Free allowances from denied/incomplete subscriptions or account reads",async()=>{
    for (const failure of ["denied","truncated","account"]) {
      const value = await collectAccountQuotas(accountId,token,now,provider({override:(url)=>{
        if (failure === "denied" && url.endsWith("/subscriptions") || failure === "account" && url.endsWith(accountId)) return new Response(null,{status:403});
        if (failure === "truncated" && url.endsWith("/subscriptions")) return Response.json({success:true,result:[subscription()],result_info:{total_count:2}});
        return undefined;
      }}));
      expect(get(value,"accountRequests").allowance).toBeNull();expect(get(value,"accountRequests").remaining).toBeNull();
    }
  });
  it("rejects invalid counts, oversized responses and GraphQL permission failures without fabricating zero",async()=>{
    for (const invalid of ["count","size","denied"]) {
      const value = await collectAccountQuotas(accountId,token,now,provider({override:(_url,query)=>{
        if (!query.includes("workers:")) return undefined;
        if (invalid === "size") return new Response("x".repeat(262145));
        if (invalid === "denied") return Response.json({data:null,errors:[{message:"not entitled"}]});
        return Response.json(accountBody({workers:[{sum:{requests:Number.MAX_SAFE_INTEGER+1}}],pages:[{sum:{requests:0}}]}));
      }}));
      expect(get(value,"accountRequests").used).toBeNull();expect(get(value,"accountRequests").remaining).toBeNull();
      expect(get(value,"accountRequests").state).toBe(invalid === "denied" ? "permission_denied" : "unavailable");
    }
  });
  it("bounds concurrent provider reads to three and rejects malformed direct account scope",async()=>{
    const mock = provider();let active=0,maximum=0;
    const fetcher: typeof fetch = async(url,init)=>{
      active++;maximum=Math.max(maximum,active);await new Promise(resolve=>setTimeout(resolve,2));
      try { return await mock(url,init); } finally { active--; }
    };
    await collectAccountQuotas(accountId,token,now,fetcher);expect(maximum).toBeLessThanOrEqual(3);
    const unused = vi.fn<typeof fetch>();
    const value = await collectAccountQuotas('evil/"account',token,now,unused);
    expect(value.quotas.every(row=>row.used === null && row.allowance === null)).toBe(true);expect(unused).not.toHaveBeenCalled();
  });
});
