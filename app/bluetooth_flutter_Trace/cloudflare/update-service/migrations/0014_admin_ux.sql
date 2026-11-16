-- Dismissal preserves the identity used by candidate backfill and audit history.
ALTER TABLE admin_notifications ADD COLUMN dismissed_at INTEGER;
CREATE INDEX admin_notifications_visible ON admin_notifications(actor,dismissed_at,id);
CREATE TABLE admin_hidden_delta_jobs (
  actor TEXT NOT NULL,
  job_id TEXT NOT NULL REFERENCES delta_jobs(id),
  attempt INTEGER NOT NULL,
  hidden_at INTEGER NOT NULL,
  PRIMARY KEY(actor,job_id,attempt)
);

-- Cancellation is an intent until the exact provider run confirms termination.
ALTER TABLE delta_jobs ADD COLUMN cancel_requested_at INTEGER;
ALTER TABLE delta_jobs ADD COLUMN cancel_restart INTEGER NOT NULL DEFAULT 0 CHECK(cancel_restart IN (0,1));
ALTER TABLE delta_jobs ADD COLUMN cancel_actor TEXT;
ALTER TABLE delta_jobs ADD COLUMN cancel_reason TEXT;
ALTER TABLE delta_jobs ADD COLUMN cancel_error TEXT;
CREATE INDEX delta_jobs_cancel_pending ON delta_jobs(cancel_requested_at);

CREATE TRIGGER app_delta_archive_guard BEFORE UPDATE OF archived ON releases
WHEN NEW.archived=1 AND EXISTS(SELECT 1 FROM delta_jobs WHERE kind='android'
  AND (target_release_id=NEW.id OR base_release_id=NEW.id))
BEGIN SELECT RAISE(ABORT,'release retained by delta job'); END;
CREATE TRIGGER firmware_delta_archive_guard BEFORE UPDATE OF archived ON firmware_releases
WHEN NEW.archived=1 AND EXISTS(SELECT 1 FROM delta_jobs WHERE kind='firmware'
  AND (target_release_id=NEW.id OR base_release_id=NEW.id))
BEGIN SELECT RAISE(ABORT,'release retained by delta job'); END;
CREATE TRIGGER delta_input_archive_guard BEFORE INSERT ON delta_jobs
WHEN (NEW.kind='android' AND (SELECT COUNT(*) FROM releases WHERE id IN (NEW.target_release_id,NEW.base_release_id) AND archived=0)<>2)
  OR (NEW.kind='firmware' AND (SELECT COUNT(*) FROM firmware_releases WHERE id IN (NEW.target_release_id,NEW.base_release_id) AND archived=0)<>2)
BEGIN SELECT RAISE(ABORT,'delta inputs are not available'); END;
