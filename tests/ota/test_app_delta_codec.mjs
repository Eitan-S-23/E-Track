import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {readFileSync} from 'node:fs';
import test from 'node:test';
import {appPatchFormat, canonical, validateJob} from '../../app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/generate-delta-job.mjs';

const format = 'bsdiff-lzma-v1';
function fixture(version=107, capabilities=[format]) {
  const part = (versionCode, hash) => ({releaseId:'rel_'+versionCode,versionCode,versionName:'1.0.81',imageSha256:hash,
    file:{sha256:hash,bytes:1000}, securityPayload:{apkSha256:hash,versionCode,capabilities}});
  const input = {schema:'operator-delta-v1',kind:'android',patchFormat:format,
    base:part(version,'a'.repeat(64)),target:part(108,'b'.repeat(64))};
  const job = {ok:true,jobId:'delta_'+'c'.repeat(64),attempt:1,workflowCommit:'d'.repeat(40),workflowRepository:'Eitan-S-23/Trace',
    input,inputSha256:createHash('sha256').update(canonical(input)).digest('hex')};
  const env = {INPUT_JOB_ID:job.jobId,INPUT_ATTEMPT:'1',INPUT_KIND:'android',GITHUB_SHA:job.workflowCommit,
    GITHUB_REPOSITORY:'Eitan-S-23/Trace',GITHUB_RUN_ATTEMPT:'1',GITHUB_RUN_ID:'123'};
  return {job, env};
}
test('new generator uses explicit immutable format and installed decoder capability', () => {
  const {job, env} = fixture();
  assert.equal(validateJob(job,env).patchFormat,format);
  for (const args of [[106,[format]],[107,[]]]) {
    const invalid = fixture(...args);
    assert.throws(()=>validateJob(invalid.job,invalid.env), /decoder/);
  }
  assert.equal(appPatchFormat({base:{versionCode:106}}),'vcdiff');
  assert.throws(()=>appPatchFormat({patchFormat:'other',base:{versionCode:107}}),/Unsupported/);
});
test('new App format remains separate from encrypted firmware and original manifests', () => {
  const source=readFileSync(new URL('../../.github/scripts/create_bsdiff_lzma_patch.py',import.meta.url),'utf8');
  assert.match(source, /"-aes", "0", "-eos", "1"/);
  assert.doesNotMatch(source, /etu_pack|OTA_AES_KEY/);
  const template=readFileSync(new URL('../../app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/admin-app-delta-workflow.template.yml',import.meta.url),'utf8');
  assert.match(template,/cmake -S \.github\/scripts\/bsdiff/);
  assert.match(template,/__DELTA_SOURCE_COMMIT__/);
  assert.doesNotMatch(template,/flutter build|gradle build|publish-staging/);
});
