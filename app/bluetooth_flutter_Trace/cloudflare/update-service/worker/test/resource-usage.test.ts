import { env } from "cloudflare:workers";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { resourceUsage } from "../src/resource_usage";

const now = Date.parse("2026-11-14T12:00:00Z")/1000;
const config={accountId:"a".repeat(32),workerScript:"test-worker",pagesScript:"pages-worker--123-production",publicPagesScript:"pages-worker--456-production",
  databaseId:"a".repeat(8)+"-"+"a".repeat(4)+"-"+"a".repeat(4)+"-"+"a".repeat(4)+"-"+"a".repeat(12),namespaceId:"b".repeat(32),bucketName:"test-bucket"};
const enabled={...env,RESOURCE_USAGE_CONFIG_JSON:JSON.stringify(config),RESOURCE_USAGE_API_TOKEN:"private-analytics-token"};
type Body={metrics:Array<{key:string;used:number|null;allowance:null;remaining:null;state:string;reason:string;periodStart:number;lastSuccessAt:number|null}>;
  account:{quotas:Array<{key:string;used:number|null;allowance:number|null;remaining:number|null;state:string;periodStart:number;lastSuccessAt:number|null}>};plan:{name:string|null};refreshing:boolean};
const read=async(response:Response)=>response.json<Body>();
const sample=()=>({data:{viewer:{accounts:[{metrics:[{sum:{requests:12,cpuTimeUs:2000,rowsRead:45,rowsWritten:8,duration:.125},
  quantiles:{cpuTimeP50:400,cpuTimeP99:1200},max:{databaseSizeBytes:2048,storedBytes:4096,payloadSize:8192},
  dimensions:{datetime:new Date((now-900)*1000).toISOString()}}]}]}},errors:null});
function successful(url: RequestInfo | URL, init?: RequestInit, project = sample()) {
  if (String(url).endsWith("/subscriptions")) return Response.json({success:true,result:[{state:"Paid",frequency:"monthly",
    current_period_start:"2026-10-28T00:00:00Z",current_period_end:"2026-11-28T00:00:00Z",rate_plan:{id:"r2_paid",public_name:"R2 Paid",is_contract:false}}]});
  if (String(url).includes("/d1/database?")) return Response.json({success:true,result:[{uuid:config.databaseId,file_size:2048}],result_info:{page:1,total_count:1}});
  if (!init?.body) return Response.json({success:true,result:{type:"standard"}});
  const query = JSON.parse(String(init.body)).query as string;
  if (query.includes("metrics:")) return Response.json(project);
  if (query.includes("workers:")) return Response.json({data:{viewer:{accounts:[{workers:[{sum:{requests:12}}],pages:[{sum:{requests:12}}]}]}}});
  if (query.includes("r2StorageAdaptiveGroups")) return Response.json({data:{viewer:{accounts:[{usage:Array.from({length:18},(_,index)=>({
    dimensions:{date:new Date(Date.parse("2026-10-28T00:00:00Z")+index*86400000).toISOString().slice(0,10),bucketName:"other-project"},max:{payloadSize:8192}}))}]}}});
  return Response.json({data:{viewer:{accounts:[{usage:[sample().data.viewer.accounts[0].metrics[0]]}]}}});
}
beforeEach(async()=>{await env.DB.prepare("DELETE FROM admin_resource_usage_cache").run();});
describe("honest, bounded provider usage",()=>{
  it("uses fixed scoped queries, real units and a shared 15-minute cache without exposing credentials",async()=>{
    const fetcher=vi.fn<typeof fetch>(async(_url,init)=>{
      expect(init?.redirect).toBe("manual");
      if (init?.body) {
        expect(_url).toBe("https://api.cloudflare.com/client/v4/graphql");
        const query=JSON.parse(String(init.body)).query;
        expect(query).toContain('accountTag:"'+config.accountId+'"');
        if (query.includes("metrics:")) expect(query).toContain("limit:1");
      }
      return successful(_url,init);
    });
    const response=await resourceUsage(enabled,now,fetcher),raw=await response.text(),body=JSON.parse(raw) as Body;
    expect(fetcher).toHaveBeenCalledTimes(22);expect(raw).not.toContain(enabled.RESOURCE_USAGE_API_TOKEN);
    expect(body.metrics.find(m=>m.key==="workerCpu")?.used).toBe(2);
    expect(body.metrics.find(m=>m.key==="pagesCpuP50")?.used).toBe(.4);
    expect(body.metrics.find(m=>m.key==="doDuration")?.used).toBe(.125);
    expect(body.metrics.every(m=>m.allowance===null&&m.remaining===null)).toBe(true);expect(body.plan.name).toBe("Workers Free");
    expect(body.account.quotas.find(m=>m.key==="accountRequests")).toMatchObject({used:24,allowance:100000,remaining:99976});
    await resourceUsage(enabled,now+10,fetcher);expect(fetcher).toHaveBeenCalledTimes(22);
  });
  it("does not convert unconfigured, denied or empty data to zero",async()=>{
    const denied=vi.fn<typeof fetch>(async()=>new Response("token must not appear",{status:403}));
    expect((await read(await resourceUsage(env,now,denied))).metrics.every(m=>m.used===null&&m.state==="not_configured")).toBe(true);
    expect(denied).not.toHaveBeenCalled();
    expect((await read(await resourceUsage(enabled,now,denied))).metrics.every(m=>m.used===null&&m.state==="permission_denied")).toBe(true);
    const empty=async()=>Response.json({data:{viewer:{accounts:[{metrics:[]}]}}});
    expect((await read(await resourceUsage(enabled,now+901,empty))).metrics.every(m=>m.used===null&&m.state==="no_samples")).toBe(true);
  });
  it("preserves the actual old measurement window on failure across a UTC reset",async()=>{
    const first=await read(await resourceUsage(enabled,now,async(url,init)=>successful(url,init)));
    const second=await read(await resourceUsage(enabled,now+86401,async()=>new Response(null,{status:503})));
    expect(second.metrics.every(m=>m.state==="stale"&&m.reason==="unavailable"&&m.lastSuccessAt===now)).toBe(true);
    expect(second.metrics[0].periodStart).toBe(first.metrics[0].periodStart);
    expect(second.account.quotas.find(m=>m.key==="accountRequests")).toMatchObject({state:"stale",used:24,remaining:99976,lastSuccessAt:now});
    expect(second.account.quotas.find(m=>m.key==="accountRequests")?.periodStart).toBe(first.account.quotas.find(m=>m.key==="accountRequests")?.periodStart);
  });
  it("does not reuse cached values across resource scope changes",async()=>{
    await resourceUsage(enabled,now,async(url,init)=>successful(url,init));
    const changed={...enabled,RESOURCE_USAGE_CONFIG_JSON:JSON.stringify({...config,workerScript:"other-worker"})};
    expect((await read(await resourceUsage(changed,now,async()=>new Response(null,{status:403})))).metrics.every(m=>m.used===null)).toBe(true);
  });
  it("replaces a corrupt expanded cache even when its timestamp is still fresh",async()=>{
    const fetcher=vi.fn<typeof fetch>(async(url,init)=>successful(url,init));
    await resourceUsage(enabled,now,fetcher);
    await env.DB.prepare("UPDATE admin_resource_usage_cache SET snapshot_json=?").bind("{}").run();
    const result=await read(await resourceUsage(enabled,now+10,fetcher));
    expect(fetcher).toHaveBeenCalledTimes(44);
    expect(result.account.quotas.find(row=>row.key === "accountRequests")).toMatchObject({used:24,remaining:99976,state:"ok"});
  });
  it("allows only one bounded provider refresh across concurrent readers",async()=>{
    let release!:()=>void;const gate=new Promise<void>(resolve=>{release=resolve;});
    const fetcher=vi.fn<typeof fetch>(async(url,init)=>{await gate;return successful(url,init);});
    const pending=resourceUsage(enabled,now,fetcher);
    await vi.waitFor(()=>expect(fetcher).toHaveBeenCalledTimes(3));
    const next=await read(await resourceUsage(enabled,now,fetcher));expect(next.refreshing).toBe(true);
    release();await pending;expect(fetcher).toHaveBeenCalledTimes(22);
  });
  it("rejects oversized provider bodies, malformed scopes and missing numeric fields",async()=>{
    const body=await read(await resourceUsage(enabled,now,async()=>new Response("x".repeat(262145))));
    expect(body.metrics.every(m=>m.used===null&&m.state==="unavailable")).toBe(true);
    const malicious={...enabled,RESOURCE_USAGE_CONFIG_JSON:JSON.stringify({...config,workerScript:'evil"){'})};
    const fetcher=vi.fn<typeof fetch>();await resourceUsage(malicious,now,fetcher);expect(fetcher).not.toHaveBeenCalled();
    const missing=sample();missing.data.viewer.accounts[0].metrics[0].sum.cpuTimeUs=Number.NaN;
    const result=await read(await resourceUsage(enabled,now+901,async(url,init)=>successful(url,init,missing)));
    expect(result.metrics.find(m=>m.key==="workerCpu")?.used).toBeNull();
  });
  it("keeps a provider-reported zero distinct from no samples",async()=>{
    const value=sample();value.data.viewer.accounts[0].metrics[0].sum.requests=0;
    const result=await read(await resourceUsage(enabled,now,async(url,init)=>successful(url,init,value)));
    expect(result.metrics.find(m=>m.key==="workerRequests")).toMatchObject({used:0,state:"ok"});
  });
  it("uses the Workers-supported redirect mode and never follows a provider redirect with credentials",async()=>{
    const fetcher=vi.fn<typeof fetch>(async(_url,init)=>{
      if(init?.redirect === "error") throw new TypeError("Workers does not implement redirect:error");
      expect(init?.redirect).toBe("manual");
      return new Response(null,{status:302,headers:{Location:"https://untrusted.example.test/"}});
    });
    const result=await read(await resourceUsage(enabled,now,fetcher));
    expect(fetcher).toHaveBeenCalledTimes(15);
    expect(fetcher.mock.calls.every(([url])=>String(url).startsWith("https://api.cloudflare.com/client/v4/"))).toBe(true);
    expect(result.metrics.every(metric=>metric.used===null&&metric.state==="unavailable")).toBe(true);
  });
});
