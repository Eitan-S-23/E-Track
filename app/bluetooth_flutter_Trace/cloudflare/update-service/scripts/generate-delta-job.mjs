#!/usr/bin/env node
import { createHash, createPrivateKey, sign } from "node:crypto";
import { createReadStream, createWriteStream, existsSync, readdirSync } from "node:fs";
import { mkdir, readFile, stat, writeFile } from "node:fs/promises";
import { spawnSync } from "node:child_process";
import { Readable, Transform } from "node:stream";
import { pipeline } from "node:stream/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { args, CliError, failure, outputPath, projectRoot } from "./firmware-cli.mjs";

const LIMIT = 256 * 1024 * 1024;
const HEX = /^[0-9a-f]{64}$/;
export function canonical(value) {
  if (Array.isArray(value)) return `[${value.map(canonical).join(",")}]`;
  if (value && typeof value === "object") return `{${Object.entries(value).sort(([a],[b])=>a.localeCompare(b))
    .map(([k,v])=>`${JSON.stringify(k)}:${canonical(v)}`).join(",")}}`;
  return JSON.stringify(value);
}
const digest = value => createHash("sha256").update(value).digest("hex");
const requireValue = (ok, message) => { if (!ok) throw new CliError(message); };
export async function identity(file) {
  const info=await stat(file);
  requireValue(info.isFile() && info.size>0 && info.size<=LIMIT,"Missing or oversized input/patch");
  const hash=createHash("sha256");
  for await(const chunk of createReadStream(file)) hash.update(chunk);
  return {sha256:hash.digest("hex"),bytes:info.size};
}

export function validateJob(job, env) {
  requireValue(job?.ok===true && /^delta_[0-9a-f]{64}$/.test(job.jobId),"Invalid delta job identity");
  requireValue(job.jobId===env.INPUT_JOB_ID && Number(env.INPUT_ATTEMPT)===job.attempt && Number.isSafeInteger(job.attempt) && job.attempt>0,"Stale delta attempt");
  requireValue(job.workflowCommit===env.GITHUB_SHA && /^[0-9a-f]{40}$/.test(env.GITHUB_SHA ?? ""),"Workflow source differs from the pinned job");
  requireValue(env.GITHUB_REPOSITORY==="Eitan-S-23/E-Track" && env.GITHUB_RUN_ATTEMPT==="1"
    && /^[1-9][0-9]{0,19}$/.test(env.GITHUB_RUN_ID ?? ""),"Use a new Admin attempt, not GitHub rerun");
  const input=job.input;
  requireValue(input?.schema==="operator-delta-v1" && ["android","firmware"].includes(input.kind) && input.kind===env.INPUT_KIND,"Invalid delta scope");
  requireValue(job.inputSha256===digest(canonical(input)),"Delta input hash mismatch");
  for(const part of [input.base,input.target]) {
    requireValue(part && typeof part.releaseId==="string" && /^[A-Za-z0-9_-]{1,160}$/.test(part.releaseId)
      && Number.isSafeInteger(part.versionCode) && part.versionCode>=0 && typeof part.versionName==="string"
      && /^[\w.+-]{1,64}$/.test(part.versionName) && HEX.test(part.imageSha256),"Invalid delta version binding");
    requireValue(part.file && HEX.test(part.file.sha256) && Number.isSafeInteger(part.file.bytes)
      && part.file.bytes>0 && part.file.bytes<=LIMIT,"Invalid original file binding");
  }
  requireValue(input.base.versionCode<input.target.versionCode,"Delta base must precede target");
  if(input.kind==="android") {
    requireValue(input.base.versionCode>=41,"Source APK predates supported VCDIFF decoding");
    requireValue(input.target.securityPayload?.apkSha256===input.target.imageSha256
      && input.target.securityPayload?.versionCode===input.target.versionCode,"Invalid target APK manifest");
  } else {
    requireValue(input.base.hardwareRevision===1 && input.target.hardwareRevision===1
      && input.base.layoutId===1 && input.target.layoutId===1,"Existing F435 packer supports hardware/layout 1 only");
    requireValue(/^[0-9a-fA-F]{32}$/.test(env.OTA_AES_KEY ?? ""),"Protected firmware packaging key is missing");
  }
  return input;
}

function androidTools(env) {
  if (env.DELTA_AAPT && env.DELTA_APKSIGNER) return {aapt:env.DELTA_AAPT,apksigner:env.DELTA_APKSIGNER};
  const base=path.join(env.ANDROID_SDK_ROOT ?? env.ANDROID_HOME ?? "", "build-tools");
  requireValue(existsSync(base),"Android SDK build-tools are required for original APK verification");
  const versions=readdirSync(base).filter(v=>/^\d+\.\d+\.\d+$/.test(v)).sort((a,b)=>a.localeCompare(b,undefined,{numeric:true}));
  requireValue(versions.length>0,"No Android build-tools version is available");
  return {aapt:path.join(base,versions.at(-1),"aapt"),apksigner:path.join(base,versions.at(-1),"apksigner")};
}
export function apkIdentity(badging, signature, expected) {
  const match=badging.match(/^package: name='([^']+)' versionCode='(\d+)' versionName='([^']+)'/m);
  const certs=[...signature.matchAll(/certificate SHA-256 digest: ([0-9a-f]{64})/ig)].map(m=>m[1].toLowerCase());
  requireValue(match && Number(match[2])===expected.versionCode && match[3]===expected.versionName,"APK package version differs from the registered original");
  requireValue(/Number of signers: 1(?:\r?\n|$)/.test(signature) && new Set(certs).size===1,"A single verified APK signer is required");
  return {packageName:match[1],certificateSha256:certs[0]};
}

export async function generatePatch({root,out,job,env=process.env,execute=spawnSync}) {
  const input=validateJob(job,env);
  out=outputPath(root,path.resolve(out));
  const files=Object.fromEntries(["base","target","base.bin","target.bin","reconstructed","patch","patch-metadata.json","proof.json","steps.json"]
    .map(name=>[name,outputPath(root,path.join(out,name))]));
  const labels=input.kind==="firmware"?["base-unpack","base-verify","target-unpack","target-verify","pack","apply","patch-verify"]
    :["base-package","base-signer","target-package","target-signer","pack","apply"];
  for(const label of labels) for(const ext of ["stdout","stderr"]) outputPath(root,path.join(out,`${label}.${ext}`));
  const temp=outputPath(root,path.join(out,"tmp"));
  await mkdir(temp,{recursive:true});
  for(const part of ["base","target"]) {
    const got=await identity(files[part]);
    requireValue(got.sha256===input[part].file.sha256 && got.bytes===input[part].file.bytes,"Downloaded original bytes differ from the job");
  }
  requireValue(!existsSync(files.patch) && !existsSync(files["proof.json"]),"Prior output exists; do not rebuild/overwrite an attempt");
  const childEnv={...env,TEMP:temp,TMP:temp,TMPDIR:temp,PYTHONDONTWRITEBYTECODE:"1",PYTHONUTF8:"1"};
  const steps=[];
  async function run(label,program,argv) {
    const result=await execute(program,argv,{cwd:out,env:childEnv,encoding:"utf8",windowsHide:true,timeout:360000,maxBuffer:2*1024*1024});
    for(const ext of ["stdout","stderr"]) await writeFile(outputPath(root,path.join(out,`${label}.${ext}`)),result[ext]??"",{flag:"wx"});
    steps.push({label,program,argv,exitCode:result.status});
    await writeFile(files["steps.json"],JSON.stringify(steps,null,2));
    requireValue(!result.error && result.status===0,`${label} failed; see retained step diagnostics`);
    return result.stdout??"";
  }
  const python=env.PYTHON ?? "python3";
  const py=(label,script,argv)=>run(label,python,["-B",path.join(root,script),...argv]);
  let base=files.base,target=files.target;
  let packages;
  if(input.kind==="firmware") {
    for(const part of ["base","target"]) {
      const image=files[`${part}.bin`];
      await py(`${part}-unpack`,"Tools/etu_unpack.py",[files[part],"--out",image,"--verify-fw-header"]);
      const check=JSON.parse(await py(`${part}-verify`,".github/scripts/firmware-byte-check.py",[
        "--input",image,"--kind","app","--version",input[part].versionName,"--sha256",input[part].imageSha256,"--package",files[part]]));
      requireValue(check.ok===true && check.version_code===input[part].versionCode,"Firmware original header mismatch");
    }
    base=files["base.bin"];target=files["target.bin"];
    requireValue(env.BSDIFF_EXE && existsSync(env.BSDIFF_EXE),"Existing bsdiff tool is required");
    await py("pack","Tools/etu_pack.py",["pack-patch","--old",base,"--new",target,"--out",files.patch,
      "--ver-name",input.target.versionName,"--base-ver-name",input.base.versionName,"--bsdiff-exe",env.BSDIFF_EXE]);
    await py("apply","Tools/etu_unpack.py",[files.patch,"--old",base,"--out",files.reconstructed,"--verify-fw-header"]);
    const checked=JSON.parse(await py("patch-verify",".github/scripts/firmware-byte-check.py",[
      "--input",files.reconstructed,"--kind","app","--version",input.target.versionName,"--sha256",input.target.imageSha256,
      "--package",files.patch,"--base-image",base]));
    requireValue(checked.ok===true && checked.version_code===input.target.versionCode,"Patch outer/header verification failed");
  } else {
    const tools=androidTools(env);packages={};
    for(const part of ["base","target"]) packages[part]=apkIdentity(
      await run(`${part}-package`,tools.aapt,["dump","badging",files[part]]),
      await run(`${part}-signer`,tools.apksigner,["verify","--verbose","--print-certs",files[part]]),input[part]);
    requireValue(canonical(packages.base)===canonical(packages.target),"APK package name or signing certificate changed");
    await py("pack",".github/scripts/create_vcdiff_patch.py",[base,target,files.patch,
      "--from-version-code",String(input.base.versionCode),"--to-version-code",String(input.target.versionCode),
      "--metadata-output",files["patch-metadata.json"]]);
    await run("apply",env.XDELTA3 ?? "xdelta3",["-d","-s",base,files.patch,files.reconstructed]);
  }
  const targetIdentity=await identity(target), reconstructed=await identity(files.reconstructed), baseIdentity=await identity(base);
  requireValue(targetIdentity.sha256===input.target.imageSha256 && baseIdentity.sha256===input.base.imageSha256
    && reconstructed.sha256===targetIdentity.sha256 && reconstructed.bytes===targetIdentity.bytes,"Patch reconstruction SHA/length mismatch");
  requireValue((await readFile(files.reconstructed)).equals(await readFile(target)),"Patch reconstruction differs byte-for-byte");
  for(const part of ["base","target"]) {
    const got=await identity(files[part]);
    requireValue(got.sha256===input[part].file.sha256 && got.bytes===input[part].file.bytes,"A packaging tool modified original input bytes");
  }
  const patch=await identity(files.patch);
  const proof={attempt:job.attempt,runId:env.GITHUB_RUN_ID,workflowCommit:env.GITHUB_SHA,inputSha256:job.inputSha256,
    baseImageSha256:input.base.imageSha256,targetImageSha256:input.target.imageSha256,reconstructedSha256:reconstructed.sha256,
    byteEqual:true,sha256:patch.sha256,sizeBytes:patch.bytes};
  if(input.kind==="android") {
    const metadata=JSON.parse(await readFile(files["patch-metadata.json"],"utf8"));
    requireValue(metadata.algorithm==="vcdiff" && metadata.sha256===patch.sha256 && metadata.size===patch.bytes
      && metadata.oldSha256===input.base.imageSha256 && metadata.newSha256===input.target.imageSha256,"VCDIFF metadata drift");
    requireValue(env.TRACE_UPDATE_PAYLOAD_ED25519_PRIVATE_KEY_BASE64,"APK manifest signing key is required");
    const fileName=`delta-${input.base.versionCode}-${input.target.versionCode}-${input.base.imageSha256.slice(0,12)}.vcdiff`;
    const original=input.target.securityPayload;
    proof.securityPayload={...original,patches:[{fromVersionCode:input.base.versionCode,toVersionCode:input.target.versionCode,
      assetName:fileName,sha256:patch.sha256,size:patch.bytes,oldSha256:input.base.imageSha256,newSha256:input.target.imageSha256}],
      assetHashes:[...original.assetHashes.filter(a=>a.assetType!=="patch"),{fileName,assetType:"patch",sha256:patch.sha256,size:patch.bytes}]};
    const key=createPrivateKey({key:Buffer.from(env.TRACE_UPDATE_PAYLOAD_ED25519_PRIVATE_KEY_BASE64,"base64"),format:"der",type:"pkcs8"});
    proof.payloadSignature={algorithm:"ed25519",keyVersion:env.TRACE_UPDATE_PAYLOAD_KEY_VERSION??"staging",
      signature:sign(null,Buffer.from(canonical(proof.securityPayload)),key).toString("base64")};
  }
  await writeFile(files["proof.json"],JSON.stringify(proof,null,2)+"\n",{flag:"wx"});
  if(patch.bytes>=input.target.file.bytes) throw new CliError("Delta is not smaller; full fallback remains unchanged","DELTA_NOT_SMALLER");
  return {proof,patchPath:files.patch};
}

async function responseJson(response) {
  const reader=response.body?.getReader();requireValue(reader,"Empty API response");
  const chunks=[];let size=0;
  try {while(true) {const r=await reader.read();if(r.done)break;size+=r.value.length;
    if(size>65536){await reader.cancel();throw new CliError("Oversized API response");} chunks.push(Buffer.from(r.value));}}
  finally {reader.releaseLock();}
  const value=JSON.parse(Buffer.concat(chunks).toString("utf8"));
  requireValue(response.ok && value.ok===true,`Delta API failed (HTTP ${response.status})`);
  return value;
}

export async function runDeltaJob({root,out,env=process.env,fetcher=fetch,execute=spawnSync}) {
  const service=new URL(env.TRACE_UPDATE_SERVICE_URL??"");
  requireValue(service.protocol==="https:" && !service.username && !service.password && service.pathname==="/"
    && !service.search && !service.hash,"A fixed HTTPS Worker origin is required");
  requireValue(/^delta_[0-9a-f]{64}$/.test(env.INPUT_JOB_ID??"") && env.TRACE_DEPLOY_TOKEN,"Job and scoped CI credential required");
  out=outputPath(root,path.resolve(out));
  requireValue(!existsSync(out),"Prior delta attempt directory exists; do not replay");
  for(const name of ["job.json","claim.json","base","target","upload.json","complete.json","failure.json"]) outputPath(root,path.join(out,name));
  await mkdir(out,{recursive:true});
  const route=new URL(`/api/ci/delta/jobs/${env.INPUT_JOB_ID}/`,service);
  const headers={Authorization:`Bearer ${env.TRACE_DEPLOY_TOKEN}`,Accept:"application/json"};
  const request=(action,body)=>fetcher(new URL(action,route),{method:body?"POST":"GET",headers:{...headers,"Content-Type":"application/json"},
    body:body?JSON.stringify(body):undefined,redirect:"error",signal:AbortSignal.timeout(60000)}).then(responseJson);
  const save=(name,value)=>writeFile(outputPath(root,path.join(out,name)),JSON.stringify(value,null,2)+"\n",{flag:"wx"});
  const job=await request("spec");
  validateJob(job,env);await save("job.json",job);
  const binding={attempt:job.attempt,runId:env.GITHUB_RUN_ID,workflowCommit:env.GITHUB_SHA};
  await save("claim.json",await request("claim",binding));
  let completionStarted=false;
  try {
    const assetHeaders={...headers,"X-Delta-Attempt":String(job.attempt),"X-Delta-Run":env.GITHUB_RUN_ID,"X-Delta-Commit":env.GITHUB_SHA};
    for(const part of ["base","target"]) {
      const response=await fetcher(new URL(part,route),{headers:assetHeaders,redirect:"error",signal:AbortSignal.timeout(240000)});
      requireValue(response.ok && response.body && !response.headers.has("Content-Encoding"),"Original download failed");
      const expected=job.input[part].file;let bytes=0;const hash=createHash("sha256");
      const guard=new Transform({transform(chunk,encoding,done){bytes+=chunk.length;
        if(bytes>expected.bytes)return done(new Error("Original size exceeded"));hash.update(chunk);done(null,chunk);}});
      await pipeline(Readable.fromWeb(response.body),guard,createWriteStream(outputPath(root,path.join(out,part)),{flags:"wx"}));
      requireValue(bytes===expected.bytes && hash.digest("hex")===expected.sha256,"Original download hash mismatch");
    }
    const result=await generatePatch({root,out,job,env,execute});
    const uploaded=await fetcher(new URL("asset",route),{method:"POST",headers:{...assetHeaders,"Content-Type":"application/octet-stream",
      "Content-Length":String(result.proof.sizeBytes),"X-Delta-Sha256":result.proof.sha256},body:createReadStream(result.patchPath),
      duplex:"half",redirect:"error",signal:AbortSignal.timeout(240000)}).then(responseJson);
    requireValue(uploaded.sha256===result.proof.sha256 && uploaded.sizeBytes===result.proof.sizeBytes,"Uploaded delta identity mismatch");
    await save("upload.json",uploaded);
    completionStarted=true;
    const complete=await request("complete",result.proof);await save("complete.json",complete);
    requireValue(complete.channelPublished===false || complete.idempotent===true,"Unexpected channel mutation receipt");
    return complete;
  } catch(error) {
    // A lost completion reply must be reconciled, not converted into a new build.
    const details={errorCode:error?.code==="DELTA_NOT_SMALLER"?"DELTA_NOT_SMALLER":"CI_BUILD_FAILED",completionUncertain:completionStarted};
    if(!completionStarted) {
      try {details.reported=await request("fail",{...binding,errorCode:details.errorCode});}
      catch {details.failureReportUncertain=true;}
    }
    await save("failure.json",details);throw error;
  }
}

if(process.argv[1] && path.resolve(process.argv[1])===fileURLToPath(import.meta.url)) {
  const options=args(process.argv.slice(2),["out"]);
  runDeltaJob({root:projectRoot(),out:options.out??".cache/admin-delta/run"})
    .then(()=>process.stdout.write("Verified supplemental delta ready; channels unchanged.\n")).catch(failure);
}
