-- Keep the legacy tables as rollback evidence. Preserve notification IDs,
-- read cursors and delivery leases when moving to the shared event stream.
CREATE TABLE admin_candidate_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  app_id TEXT NOT NULL,
  kind TEXT NOT NULL CHECK(kind IN ('android','windows','firmware')),
  release_id TEXT NOT NULL,
  version_name TEXT NOT NULL,
  version_code INTEGER NOT NULL,
  device_model TEXT,
  commit_sha TEXT NOT NULL,
  run_id TEXT NOT NULL,
  created_at INTEGER NOT NULL,
  UNIQUE(kind,release_id)
);
CREATE INDEX admin_candidate_app ON admin_candidate_events(app_id,id);

CREATE TABLE admin_notifications (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  job_id TEXT REFERENCES delta_jobs(id) ON DELETE CASCADE,
  candidate_id INTEGER REFERENCES admin_candidate_events(id),
  actor TEXT NOT NULL,
  attempt INTEGER,
  status TEXT NOT NULL CHECK(status IN ('ready','failed')),
  error_code TEXT,
  created_at INTEGER NOT NULL,
  read_at INTEGER CHECK(read_at IS NULL OR read_at > 0),
  CHECK((job_id IS NOT NULL AND candidate_id IS NULL) OR
        (job_id IS NULL AND candidate_id IS NOT NULL AND status='ready')),
  UNIQUE(job_id,attempt,status),
  UNIQUE(actor,candidate_id)
);
CREATE INDEX admin_notifications_actor ON admin_notifications(actor,id);
INSERT INTO admin_notifications(id,job_id,actor,attempt,status,error_code,created_at,read_at)
  SELECT id,job_id,actor,attempt,status,error_code,created_at,read_at FROM delta_notifications;
-- Deleted notifications may still be remembered by browser receipt cursors.
INSERT INTO sqlite_sequence(name,seq)
  SELECT 'admin_notifications',0 WHERE NOT EXISTS(SELECT 1 FROM sqlite_sequence WHERE name='admin_notifications');
UPDATE sqlite_sequence SET seq=MAX(seq,COALESCE((SELECT seq FROM sqlite_sequence WHERE name='delta_notifications'),0))
  WHERE name='admin_notifications';

CREATE TABLE admin_notification_deliveries (
  event_id INTEGER NOT NULL REFERENCES admin_notifications(id) ON DELETE CASCADE,
  subscription_id TEXT NOT NULL REFERENCES admin_push_subscriptions(id) ON DELETE CASCADE,
  attempts INTEGER NOT NULL DEFAULT 0,
  next_at INTEGER NOT NULL,
  lease TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','sent','failed')),
  PRIMARY KEY(event_id,subscription_id)
);
CREATE INDEX admin_notification_due ON admin_notification_deliveries(status,next_at);
INSERT INTO admin_notification_deliveries SELECT * FROM admin_push_deliveries;

DROP TRIGGER delta_terminal_notification;
DROP TRIGGER delta_notification_delivery;
CREATE TRIGGER delta_terminal_notification AFTER UPDATE OF status ON delta_jobs
WHEN NEW.status IN ('ready','failed') AND NEW.status<>OLD.status
BEGIN
  INSERT OR IGNORE INTO admin_notifications(job_id,actor,attempt,status,error_code,created_at)
    VALUES(NEW.id,NEW.actor,NEW.attempt,NEW.status,NEW.error_code,NEW.updated_at);
END;
CREATE TRIGGER admin_notification_delivery AFTER INSERT ON admin_notifications
BEGIN
  INSERT OR IGNORE INTO admin_notification_deliveries(event_id,subscription_id,next_at)
    SELECT NEW.id,id,NEW.created_at FROM admin_push_subscriptions
    WHERE actor=NEW.actor AND created_at<=NEW.created_at AND expires_at>NEW.created_at;
END;
CREATE TRIGGER admin_candidate_notification AFTER INSERT ON admin_candidate_events
BEGIN
  INSERT OR IGNORE INTO admin_notifications(candidate_id,actor,status,created_at)
    SELECT NEW.id,actor,'ready',NEW.created_at FROM admin_push_subscriptions
    WHERE created_at<=NEW.created_at AND expires_at>NEW.created_at GROUP BY actor;
END;
-- No release backfill: only future, successfully registered candidates alert.
