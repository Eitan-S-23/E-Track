(async()=>{const fs=require("node:fs"),path=require("node:path"),crypto=require("node:crypto"),assert=require("node:assert/strict");const {execFileSync}=require("node:child_process");const root="D:/github/my/E-Track/.cache/p4-4-integration-20261018",sha="546d8b39a5697ba1b018720b120608de52a511d2";
  const evidenceRel = "docs/ota-exec-notes/P4-4-s3-interface-2026-10-19";
  const evidenceRoot = path.join(root, evidenceRel);
  const inventory = JSON.parse(fs.readFileSync(path.join(evidenceRoot, "raw-output-inventory.json"), "utf8"));
  let total = 0;
  for (const e of inventory.entries) {
    const p = path.resolve(e.destination);
    const relative = path.relative(evidenceRoot, p);
    assert(!relative.startsWith("..") && !path.isAbsolute(relative));
    const raw = fs.readFileSync(p);
    assert.equal(raw.length, e.bytes);
    assert.equal(crypto.createHash("sha256").update(raw).digest("hex"), e.sha256);
    const committed = execFileSync("git", ["show", sha + ":" + evidenceRel + "/" + relative.replaceAll("\\", "/")],
      { cwd: root, maxBuffer: 16 * 1024 * 1024 });
    assert.deepEqual(raw, committed);
    total += raw.length;
  }
  const provenance = execFileSync("git", ["diff", "--exit-code",
    "de362151bda72c0dd1c19ab1293e99838fb8976e", sha, "--", ".github", "app",
    "tests/ota/firmware-pipeline.host.test.ts", "tests/ota/test_firmware_s3.mjs", "tests/ota/test_firmware_workflow.mjs"],
    { cwd: root, maxBuffer: 8 * 1024 * 1024 });
  assert.equal(provenance.length, 0);
process.stdout.write(JSON.stringify({nature:"Independent read-only original-evidence verification",delivery:sha,files:inventory.entries.length,bytes:total,hashesMatch:true,gitBlobsMatch:true,developmentSourceUnchanged:true},null,2)+"\n");})().catch(e=>{process.stderr.write(e.stack+"\n");process.exitCode=1;});
