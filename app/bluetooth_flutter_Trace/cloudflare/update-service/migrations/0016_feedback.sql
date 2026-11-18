CREATE TABLE feedback_settings (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  ip_salt TEXT NOT NULL CHECK (length(ip_salt) = 64)
);
INSERT INTO feedback_settings(id, ip_salt) VALUES (1, lower(hex(randomblob(32))));

CREATE TABLE feedback_batches (
  id TEXT PRIMARY KEY,
  install_key TEXT NOT NULL,
  payload_hash TEXT NOT NULL,
  report_day INTEGER NOT NULL,
  ip_key TEXT NOT NULL,
  received_at INTEGER NOT NULL,
  UNIQUE(install_key, report_day)
);
CREATE INDEX feedback_ip_day ON feedback_batches(ip_key, report_day);

-- Count only committed batches. The trigger and all messages share one transaction.
CREATE TRIGGER feedback_ip_budget BEFORE INSERT ON feedback_batches
WHEN (SELECT COUNT(*) FROM feedback_batches
      WHERE ip_key = NEW.ip_key AND report_day = NEW.report_day) >= 50
BEGIN
  SELECT RAISE(ABORT, 'feedback IP daily budget');
END;

CREATE TABLE feedback_messages (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  client_id TEXT NOT NULL,
  install_key TEXT NOT NULL,
  batch_id TEXT NOT NULL REFERENCES feedback_batches(id),
  body TEXT NOT NULL CHECK (length(body) BETWEEN 1 AND 2000),
  client_created_at INTEGER NOT NULL,
  received_at INTEGER NOT NULL,
  platform TEXT NOT NULL CHECK (platform IN ('android', 'windows', 'ios')),
  version_name TEXT NOT NULL,
  version_code INTEGER NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'resolved', 'declined')),
  note TEXT NOT NULL DEFAULT '' CHECK (length(note) <= 2000),
  revision INTEGER NOT NULL DEFAULT 1 CHECK (revision > 0),
  updated_at INTEGER NOT NULL,
  updated_by TEXT NOT NULL DEFAULT 'app',
  UNIQUE(install_key, client_id)
);
CREATE INDEX feedback_status_id ON feedback_messages(status, id DESC);
CREATE INDEX feedback_received ON feedback_messages(received_at);

CREATE TABLE feedback_events (
  feedback_id INTEGER NOT NULL REFERENCES feedback_messages(id) ON DELETE CASCADE,
  revision INTEGER NOT NULL,
  status TEXT NOT NULL,
  note TEXT NOT NULL,
  actor TEXT NOT NULL,
  created_at INTEGER NOT NULL,
  PRIMARY KEY(feedback_id, revision)
);
CREATE TRIGGER feedback_update_audit AFTER UPDATE OF status, note ON feedback_messages
BEGIN
  INSERT INTO feedback_events(feedback_id, revision, status, note, actor, created_at)
  VALUES (NEW.id, NEW.revision, NEW.status, NEW.note, NEW.updated_by, NEW.updated_at);
END;
