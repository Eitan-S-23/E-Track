ALTER TABLE delta_jobs ADD COLUMN progress_phase TEXT NOT NULL DEFAULT 'building'
  CHECK(progress_phase IN ('building','uploading','verifying'));

CREATE TABLE admin_push_subscriptions (
  id TEXT PRIMARY KEY,
  actor TEXT NOT NULL,
  endpoint TEXT NOT NULL,
  created_at INTEGER NOT NULL,
  expires_at INTEGER NOT NULL
);
CREATE INDEX admin_push_actor ON admin_push_subscriptions(actor,expires_at);
CREATE TRIGGER admin_push_budget BEFORE INSERT ON admin_push_subscriptions
WHEN NOT EXISTS(SELECT 1 FROM admin_push_subscriptions WHERE id=NEW.id)
  AND (SELECT COUNT(*) FROM admin_push_subscriptions WHERE actor=NEW.actor AND expires_at>NEW.created_at)>=5
BEGIN SELECT RAISE(ABORT,'push subscription limit'); END;

CREATE TABLE delta_notifications (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  job_id TEXT NOT NULL REFERENCES delta_jobs(id) ON DELETE CASCADE,
  actor TEXT NOT NULL,
  attempt INTEGER NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('ready','failed')),
  error_code TEXT,
  created_at INTEGER NOT NULL,
  UNIQUE(job_id,attempt,status)
);
CREATE INDEX delta_notifications_actor ON delta_notifications(actor,id);
CREATE TABLE admin_notification_reads (actor TEXT PRIMARY KEY, through_id INTEGER NOT NULL DEFAULT 0);
CREATE TABLE admin_push_deliveries (
  event_id INTEGER NOT NULL REFERENCES delta_notifications(id) ON DELETE CASCADE,
  subscription_id TEXT NOT NULL REFERENCES admin_push_subscriptions(id) ON DELETE CASCADE,
  attempts INTEGER NOT NULL DEFAULT 0,
  next_at INTEGER NOT NULL,
  lease TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','sent','failed')),
  PRIMARY KEY(event_id,subscription_id)
);
CREATE INDEX admin_push_due ON admin_push_deliveries(status,next_at);

-- Completion and notification creation share the actual job transaction.
-- Existing completed jobs are deliberately not backfilled into new alerts.
CREATE TRIGGER delta_terminal_notification AFTER UPDATE OF status ON delta_jobs
WHEN NEW.status IN ('ready','failed') AND NEW.status<>OLD.status
BEGIN
  INSERT OR IGNORE INTO delta_notifications(job_id,actor,attempt,status,error_code,created_at)
    VALUES(NEW.id,NEW.actor,NEW.attempt,NEW.status,NEW.error_code,NEW.updated_at);
END;
CREATE TRIGGER delta_notification_delivery AFTER INSERT ON delta_notifications
BEGIN
  INSERT OR IGNORE INTO admin_push_deliveries(event_id,subscription_id,next_at)
    SELECT NEW.id,id,NEW.created_at FROM admin_push_subscriptions
    WHERE actor=NEW.actor AND expires_at>NEW.created_at;
END;
