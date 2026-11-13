import { readFileSync, readdirSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { SqliteD1 } from "./host/sqlite-d1";

describe("candidate notification migration",()=>{
  it("preserves legacy IDs, per-item reads, cursors, subscriptions and delivery leases without backfilling releases",()=>{
    const db=new SqliteD1(),dir=new URL("../../migrations/",import.meta.url);
    for (const name of readdirSync(dir).filter(name=>name.endsWith(".sql")&&name<"0011").sort()) db.migrate(readFileSync(new URL(name,dir),"utf8"));
    db.sqlite.exec(`INSERT INTO delta_jobs(id,kind,target_release_id,base_release_id,target_sha256,base_sha256,base_version_code,target_version_code,
      status,input_json,input_sha256,workflow_commit,workflow_ref,actor,reason,created_at,updated_at)
      VALUES('old-job','android','target','base','${"a".repeat(64)}','${"b".repeat(64)}',1,2,'running','{}','${"a".repeat(64)}','${"b".repeat(40)}','main','owner','test',1,1);
      INSERT INTO admin_push_subscriptions VALUES('browser','owner','https://fcm.googleapis.com/fcm/send/test',1,9999999999);
      UPDATE delta_jobs SET status='failed',updated_at=10 WHERE id='old-job';
      UPDATE delta_notifications SET read_at=11;
      INSERT INTO admin_notification_reads VALUES('owner',1);
      UPDATE admin_push_deliveries SET attempts=2,lease='inflight',next_at=300;
      UPDATE sqlite_sequence SET seq=50 WHERE name='delta_notifications';`);
    db.migrate(readFileSync(new URL("0011_candidate_notifications.sql",dir),"utf8"));
    expect(db.sqlite.prepare("SELECT id,read_at FROM admin_notifications").all()).toEqual([{id:1,read_at:11}]);
    expect(db.sqlite.prepare("SELECT attempts,lease,next_at FROM admin_notification_deliveries").all()).toEqual([{attempts:2,lease:"inflight",next_at:300}]);
    expect(db.sqlite.prepare("SELECT through_id FROM admin_notification_reads").get()).toEqual({through_id:1});
    expect(db.sqlite.prepare("SELECT * FROM admin_candidate_events").all()).toEqual([]);
    db.sqlite.exec("UPDATE delta_jobs SET status='dispatching',attempt=2 WHERE id='old-job';UPDATE delta_jobs SET status='ready',updated_at=20 WHERE id='old-job';");
    expect(db.sqlite.prepare("SELECT MAX(id) AS id FROM admin_notifications").get()).toEqual({id:51});
    expect(db.sqlite.prepare("SELECT COUNT(*) AS n FROM delta_notifications").get()).toEqual({n:1});
    expect(db.sqlite.prepare("PRAGMA foreign_key_check").all()).toEqual([]);
    db.sqlite.close();
  });
});
