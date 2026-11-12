import assert from "node:assert/strict";
import { createHash, generateKeyPairSync, verify } from "node:crypto";
import { mkdir, mkdtemp, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";
import { apkIdentity, canonical, generatePatch, runDeltaJob, validateJob } from "../../app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/generate-delta-job.mjs";
import { outputPath } from "../../app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/firmware-cli.mjs";

const root=fileURLToPath(new URL("../../",import.meta.url));
const sha=bytes=>createHash("sha256").update(bytes).digest("hex");
const keys=generateKeyPairSync("ed25519");
async function fixture() {
  const parent=outputPath(root,path.join(root,".cache/firmware-release-tests"));
  await mkdir(parent,{recursive:true});
  const out=await mkdtemp(path.join(parent,"admin-delta-"));
  const base=Buffer.alloc(1000,1),target=Buffer.alloc(1100,2),patch=Buffer.from("delta-fixture");
  const input={schema:"operator-delta-v1",kind:"android",base:{releaseId:"base",versionCode:99,versionName:"1.0.73",imageSha256:sha(base),
    file:{id:"base",key:"original/base",fileName:"base.apk",sha256:sha(base),bytes:base.length}},
  target:{releaseId:"target",versionCode:100,versionName:"1.0.74",imageSha256:sha(target),
    file:{id:"target",key:"original/target",fileName:"app.apk",sha256:sha(target),bytes:target.length},
    securityPayload:{appId:"trace",platform:"android",versionName:"1.0.74",versionCode:100,releaseTag:"v1.0.74",apkAssetName:"app.apk",
      apkSha256:sha(target),apkSize:target.length,patches:[],assetHashes:[{assetType:"apk",fileName:"app.apk",sha256:sha(target),size:target.length}],
      minClientVersionCode:41,capabilities:["full","patch","payloadSignature","vcdiff"]}}};
  const job={ok:true,jobId:`delta_${"a".repeat(64)}`,attempt:1,workflowCommit:"c".repeat(40),workflowRepository:"Eitan-S-23/Trace",status:"queued",input,inputSha256:sha(canonical(input))};
  const env={INPUT_JOB_ID:job.jobId,INPUT_ATTEMPT:"1",INPUT_KIND:"android",GITHUB_SHA:job.workflowCommit,
    GITHUB_RUN_ID:"123456",GITHUB_RUN_ATTEMPT:"1",GITHUB_REPOSITORY:"Eitan-S-23/Trace",PYTHON:"fake-python",
    DELTA_AAPT:"fake-aapt",DELTA_APKSIGNER:"fake-signer",XDELTA3:"fake-xdelta",TRACE_UPDATE_SERVICE_URL:"https://worker.test/",TRACE_DEPLOY_TOKEN:"test-ci-only",
    TRACE_UPDATE_PAYLOAD_ED25519_PRIVATE_KEY_BASE64:keys.privateKey.export({format:"der",type:"pkcs8"}).toString("base64")};
  for(const part of ["base","target"]) await writeFile(outputPath(root,path.join(out,part)),part==="base"?base:target,{flag:"wx"});
  const calls=[];
  let corrupt=false,certificate="b".repeat(64);
  const execute=async(program,argv,options)=>{
    assert.equal(options.cwd,out); assert.equal(options.windowsHide,true); assert.equal(options.env.TEMP,path.join(out,"tmp"));
    calls.push([program,...argv]);
    let stdout="";
    if(program==="fake-aapt") {
      const part=argv.at(-1).endsWith("base")?input.base:input.target;
      stdout=`package: name='com.trace.app' versionCode='${part.versionCode}' versionName='${part.versionName}'\n`;
    } else if(program==="fake-signer") stdout=`Number of signers: 1\nSigner #1 certificate SHA-256 digest: ${certificate}\n`;
    else if(program==="fake-python") {
      assert.match(argv[1],/create_vcdiff_patch\.py$/);
      assert.equal(argv.includes("finalize"),false);
      await writeFile(outputPath(root,argv[4]),patch,{flag:"wx"});
      await writeFile(outputPath(root,argv.at(-1)),JSON.stringify({algorithm:"vcdiff",sha256:sha(patch),size:patch.length,oldSha256:sha(base),newSha256:sha(target)}),{flag:"wx"});
    } else if(program==="fake-xdelta") await writeFile(outputPath(root,argv.at(-1)),corrupt?base:target,{flag:"wx"});
    else assert.fail(`Unexpected program ${program}`);
    return {status:0,stdout,stderr:""};
  };
  return {out,root,job,env,execute,calls,base,target,patch,corrupt:()=>{corrupt=true;},signer:value=>{certificate=value;}};
}
test("uses the existing VCDIFF generator, reconstructs exact originals and signs the per-base manifest",async()=>{
  const f=await fixture();const result=await generatePatch(f);
  assert.equal(result.proof.byteEqual,true);
  assert.equal(result.proof.baseImageSha256,sha(f.base));assert.equal(result.proof.targetImageSha256,sha(f.target));
  assert.equal(verify(null,Buffer.from(canonical(result.proof.securityPayload)),keys.publicKey,Buffer.from(result.proof.payloadSignature.signature,"base64")),true);
  assert.equal(Object.hasOwn(result.proof.securityPayload.patches[0],"algorithm"),false);
  assert.deepEqual(result.proof.securityPayload.assetHashes.at(-1),{fileName:result.proof.securityPayload.patches[0].assetName,assetType:"patch",sha256:sha(f.patch),size:f.patch.length});
  assert.deepEqual(await readFile(path.join(f.out,"base")),f.base);assert.deepEqual(await readFile(path.join(f.out,"target")),f.target);
  await assert.rejects(()=>generatePatch(f),/Prior output exists/);
});
test("rejects a reconstruction that does not equal the target",async()=>{
  const f=await fixture();f.corrupt();await assert.rejects(()=>generatePatch(f),/reconstruction/);
});
test("rejects original file drift before any packaging tool runs",async()=>{
  const f=await fixture();await writeFile(outputPath(root,path.join(f.out,"base")),f.target);
  await assert.rejects(()=>generatePatch(f),/Downloaded original bytes differ/);assert.equal(f.calls.length,0);
});
for(const [field,value] of [["GITHUB_SHA","d".repeat(40)],["INPUT_ATTEMPT","2"],["INPUT_KIND","firmware"],["GITHUB_RUN_ATTEMPT","2"],["GITHUB_REPOSITORY","someone/else"]]) {
  test(`rejects changed ${field} before claiming/building`,async()=>{const f=await fixture();assert.throws(()=>validateJob(f.job,{...f.env,[field]:value}));});
}
test("rejects a forged input hash and pre-41 source clients",async()=>{
  const f=await fixture();f.job.input.base.versionCode=40;assert.throws(()=>validateJob(f.job,f.env),/input hash mismatch/);
  f.job.inputSha256=sha(canonical(f.job.input));assert.throws(()=>validateJob(f.job,f.env),/VCDIFF/);
});
test("APK identity requires a matching version and exactly one verified signer",()=>{
  const expected={versionCode:99,versionName:"1.0.73"};
  const good="package: name='com.trace.app' versionCode='99' versionName='1.0.73'\n";
  const cert=`Number of signers: 1\nV2 Signer: certificate SHA-256 digest: ${"a".repeat(64)}\n`;
  assert.equal(apkIdentity(good,cert,expected).packageName,"com.trace.app");
  assert.throws(()=>apkIdentity(good.replace("'99'","'98'"),cert,expected),/version/);
  assert.throws(()=>apkIdentity(good,cert.replace("signers: 1","signers: 2"),expected),/single/);
});
test("network driver claims once, verifies streamed input bytes, and never publishes a channel",async()=>{
  const f=await fixture();const out=outputPath(root,path.join(f.out,"network"));
  const execute=async(program,argv,options)=>f.execute(program,argv,{...options,cwd:f.out,env:{...options.env,TEMP:path.join(f.out,"tmp")}});
  const requests=[];
  const fetcher=async(url,init={})=>{
    assert.equal(url.origin,"https://worker.test");assert.equal(init.redirect,"error");
    assert.equal(init.headers.Authorization,"Bearer test-ci-only");
    const action=url.pathname.split("/").at(-1);requests.push(action);
    if(action==="spec") return Response.json(f.job);
    if(action==="base"||action==="target") return new Response(f[action]);
    if(action==="asset") {const bytes=[];for await(const chunk of init.body) bytes.push(chunk);assert.equal(sha(Buffer.concat(bytes)),sha(f.patch));return Response.json({ok:true,sha256:sha(f.patch),sizeBytes:f.patch.length});}
    return Response.json(action==="complete"?{ok:true,channelPublished:false}:{ok:true});
  };
  await runDeltaJob({...f,out,execute,fetcher});
  assert.deepEqual(requests,["spec","claim","base","target","asset","complete"]);
});
test("a corrupt download reports failure without generating, uploading or replaying",async()=>{
  const f=await fixture(),requests=[];
  const fetcher=async(url)=>{const action=url.pathname.split("/").at(-1);requests.push(action);
    return action==="spec"?Response.json(f.job):action==="base"?new Response("corrupt"):Response.json({ok:true});};
  await assert.rejects(()=>runDeltaJob({...f,out:path.join(f.out,"network"),fetcher}),/download hash mismatch/);
  assert.deepEqual(requests,["spec","claim","base","fail"]);assert.equal(f.calls.length,0);
});
test("workflow keeps the original MCU approval gate and does not build or publish originals",async()=>{
  const workflow=await readFile(path.join(root,".github/workflows/admin-delta-build.yml"),"utf8");
  assert.match(workflow,/environment: firmware-rehearsal/);assert.match(workflow,/ORIGINAL_ADMIN_FIRMWARE_DEPLOY_TOKEN/);
  assert.doesNotMatch(workflow,/TRACE_UPDATE_PAYLOAD_ED25519_PRIVATE_KEY_BASE64/);assert.match(workflow,/cancel-in-progress: false/);
  assert.doesNotMatch(workflow,/flutter build|pack-full|finalize|firmware-release\.mjs execute|contents: write/);
});
test("original APK workflow retains its repository secrets and pins only generator code",async()=>{
  const workflow=await readFile(path.join(root,"app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/admin-app-delta-workflow.template.yml"),"utf8");
  assert.match(workflow,/github.repository == 'Eitan-S-23\/Trace'/);
  assert.match(workflow,/ref: __DELTA_SOURCE_COMMIT__/);
  assert.match(workflow,/secrets\.TRACE_DEPLOY_TOKEN/);
  assert.match(workflow,/secrets\.TRACE_UPDATE_PAYLOAD_ED25519_PRIVATE_KEY_BASE64/);
  assert.doesNotMatch(workflow,/flutter build|contents: write|gh secret|privateKeyBase64/);
});
test("preserves a pre-claim authentication failure without replay or a false failed-claim report",async()=>{
  const f=await fixture(),out=path.join(f.out,"admission-failure"),requests=[];
  await assert.rejects(()=>runDeltaJob({...f,out,fetcher:async url=>{
    requests.push(url.pathname.split('/').at(-1));return Response.json({ok:false},{status:401});
  }}),/HTTP 401/);
  assert.deepEqual(requests,["spec"]);
  const failure=JSON.parse(await readFile(path.join(out,"failure.json"),"utf8"));
  assert.equal(failure.stage,"admission");assert.equal(failure.claimOutcome,"not_sent");assert.equal(failure.automaticReplay,false);
});
test("a lost claim response remains unknown, not falsely recorded as unclaimed",async()=>{
  const f=await fixture(),out=path.join(f.out,"claim-failure");
  await assert.rejects(()=>runDeltaJob({...f,out,fetcher:async url=>{
    if(url.pathname.endsWith('/spec'))return Response.json(f.job);throw new Error('lost claim reply');
  }}),/lost claim reply/);
  const failure=JSON.parse(await readFile(path.join(out,"failure.json"),"utf8"));
  assert.equal(failure.stage,"claim");assert.equal(failure.claimOutcome,"unknown");
});
