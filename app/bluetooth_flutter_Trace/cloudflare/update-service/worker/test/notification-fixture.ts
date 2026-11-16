import { env } from "cloudflare:workers";

// These tests exercise history/status only, but job references must still exist.
export async function retainInputs(kind: string, target: string, base = "base") {
  await env.DB.prepare("INSERT OR IGNORE INTO apps(id,name) VALUES ('trace','trace')").run();
  for (const id of [base,target]) {
    if (kind === "android") {
      await env.DB.prepare(`INSERT OR IGNORE INTO releases(id,app_id,platform,version_name,version_code,release_tag,commit_sha,run_id,security_payload_json)
        SELECT ?,'trace','android',?,COALESCE(MAX(version_code),0)+1,?,'fixture',?,'{}' FROM releases`)
        .bind(id,id,id,id).run();
    } else {
      await env.DB.prepare(`INSERT OR IGNORE INTO firmware_releases(id,app_id,device_model,version_name,version_code,release_tag,
        commit_sha,run_id,target_image_sha256,hardware_rev,layout_id,min_boot_version,min_protocol_version,target_hardware)
        SELECT ?,'trace','e-track-at32f435',?,COALESCE(MAX(version_code),0)+1,?,?,?,?,1,1,1,1,'fixture' FROM firmware_releases`)
        .bind(id,id,id,"b".repeat(40),id,"a".repeat(64)).run();
    }
  }
}
