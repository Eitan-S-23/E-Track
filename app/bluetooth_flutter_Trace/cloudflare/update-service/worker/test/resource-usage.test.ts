import { env } from "cloudflare:workers";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { resourceUsage } from "../src/resource_usage";

const now = Date.parse("2026-11-14T12:00:00Z")/1000;
const config={accountId:"a".repeat(32),workerScript:"test-worker",pagesScript:"pages-worker--123-production",publicPagesScript:"pages-worker--456-production",
  databaseId:"a".repeat(8)+"-"+"a".repeat(4)+"-"+"a".repeat(4)+"-"+"a".repeat(4)+"-"+"a".repeat(12),namespaceId:"b".repeat(32),bucketName:"test-bucket"};
const enabled={...env,RESOURCE_USAGE_CONFIG_JSON:JSON.stringify(config),RESOURCE_USAGE_API_TOKEN:"private-analytics-token"};
type Body={metrics:Array<{key:string;used:number|null;allowance:null;remaining:null;state:string;reason:string;periodStart:number;lastSuccessAt:number|null}>;plan:{name:null};refreshing:boolean};
const read=async(response:Response)=>response.json<Body>();
const sample=()=>({data:{viewer:{accounts:[{metrics:[{sum:{requests:12,cpuTimeUs:2000,rowsRead:45,rowsWritten:8,duration:.125},
  quantiles:{cpuTimeP50:400,cpuTimeP99:1200},max:{databaseSizeBytes:2048,storedBytes:4096,payloadSize:8192},
  dimensions:{datetime:new Date((now-900)*1000).toISOString()}}]}]}},errors:null});
beforeEach(async()=>{await env.DB.prepare("DELETE FROM admin_resource_usage_cache").run();});
describe("honest, bounded provider usage",()=>{
  it("uses fixed scoped queries, real units and a shared 15-minute cache without exposing credentials",async()=>{
    const fetcher=vi.fn<typeof fetch>(async(_url,init)=>{
      expect(_url).toBe("https://api.cloudflare.com/client/v4/graphql");expect(init?.redirect).toBe("manual");
      const query=JSON.parse(String(init?.body)).query;
      expect(query).toContain('accountTag:"'+config.accountId+'"');expect(query).toContain("limit:1");
      return Response.json(sample());
    });
    const response=await resourceUsage(enabled,now,fetcher),raw=await response.text(),body=JSON.parse(raw) as Body;
    expect(fetcher).toHaveBeenCalledTimes(12);expect(raw).not.toContain(enabled.RESOURCE_USAGE_API_TOKEN);
    expect(body.metrics.find(m=>m.key==="workerCpu")?.used).toBe(2);
    expect(body.metrics.find(m=>m.key==="pagesCpuP50")?.used).toBe(.4);
    expect(body.metrics.find(m=>m.key==="doDuration")?.used).toBe(.125);
    expect(body.metrics.every(m=>m.allowance===null&&m.remaining===null)).toBe(true);expect(body.plan.name).toBeNull();
    await resourceUsage(enabled,now+10,fetcher);expect(fetcher).toHaveBeenCalledTimes(12);
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
    const first=await read(await resourceUsage(enabled,now,async()=>Response.json(sample())));
    const second=await read(await resourceUsage(enabled,now+86401,async()=>new Response(null,{status:503})));
    expect(second.metrics.every(m=>m.state==="stale"&&m.reason==="unavailable"&&m.lastSuccessAt===now)).toBe(true);
    expect(second.metrics[0].periodStart).toBe(first.metrics[0].periodStart);
  });
  it("does not reuse cached values across resource scope changes",async()=>{
    await resourceUsage(enabled,now,async()=>Response.json(sample()));
    const changed={...enabled,RESOURCE_USAGE_CONFIG_JSON:JSON.stringify({...config,workerScript:"other-worker"})};
    expect((await read(await resourceUsage(changed,now,async()=>new Response(null,{status:403})))).metrics.every(m=>m.used===null)).toBe(true);
  });
  it("allows only one bounded provider refresh across concurrent readers",async()=>{
    let release!:()=>void;const gate=new Promise<void>(resolve=>{release=resolve;});
    const fetcher=vi.fn<typeof fetch>(async()=>{await gate;return Response.json(sample());});
    const pending=resourceUsage(enabled,now,fetcher);
    await vi.waitFor(()=>expect(fetcher).toHaveBeenCalledTimes(3));
    const next=await read(await resourceUsage(enabled,now,fetcher));expect(next.refreshing).toBe(true);
    release();await pending;expect(fetcher).toHaveBeenCalledTimes(12);
  });
  it("rejects oversized provider bodies, malformed scopes and missing numeric fields",async()=>{
    const body=await read(await resourceUsage(enabled,now,async()=>new Response("x".repeat(262145))));
    expect(body.metrics.every(m=>m.used===null&&m.state==="unavailable")).toBe(true);
    const malicious={...enabled,RESOURCE_USAGE_CONFIG_JSON:JSON.stringify({...config,workerScript:'evil"){'})};
    const fetcher=vi.fn<typeof fetch>();await resourceUsage(malicious,now,fetcher);expect(fetcher).not.toHaveBeenCalled();
    const missing=sample();missing.data.viewer.accounts[0].metrics[0].sum.cpuTimeUs=Number.NaN;
    const result=await read(await resourceUsage(enabled,now+901,async()=>Response.json(missing)));
    expect(result.metrics.find(m=>m.key==="workerCpu")?.used).toBeNull();
  });
  it("keeps a provider-reported zero distinct from no samples",async()=>{
    const value=sample();value.data.viewer.accounts[0].metrics[0].sum.requests=0;
    const result=await read(await resourceUsage(enabled,now,async()=>Response.json(value)));
    expect(result.metrics.find(m=>m.key==="workerRequests")).toMatchObject({used:0,state:"ok"});
  });
  it("uses the Workers-supported redirect mode and never follows a provider redirect with credentials",async()=>{
    const fetcher=vi.fn<typeof fetch>(async(_url,init)=>{
      if(init?.redirect === "error") throw new TypeError("Workers does not implement redirect:error");
      expect(init?.redirect).toBe("manual");
      return new Response(null,{status:302,headers:{Location:"https://untrusted.example.test/"}});
    });
    const result=await read(await resourceUsage(enabled,now,fetcher));
    expect(fetcher).toHaveBeenCalledTimes(12);
    expect(fetcher.mock.calls.every(([url])=>url==="https://api.cloudflare.com/client/v4/graphql")).toBe(true);
    expect(result.metrics.every(metric=>metric.used===null&&metric.state==="unavailable")).toBe(true);
  });
});
