ALTER TABLE account_sessions ADD COLUMN session_id TEXT;
ALTER TABLE account_sessions ADD COLUMN installation_id TEXT;
ALTER TABLE account_sessions ADD COLUMN last_seen_at INTEGER;
UPDATE account_sessions SET session_id=lower(hex(randomblob(16)));
CREATE UNIQUE INDEX account_session_identity ON account_sessions(session_id);

CREATE TABLE account_terminals (
  account_id TEXT NOT NULL REFERENCES accounts(id),
  installation_id TEXT NOT NULL,
  platform TEXT NOT NULL,
  version_name TEXT NOT NULL,
  version_code INTEGER NOT NULL,
  model TEXT NOT NULL,
  os_version TEXT NOT NULL,
  first_seen_at INTEGER NOT NULL,
  last_seen_at INTEGER NOT NULL,
  PRIMARY KEY(account_id,installation_id)
);
CREATE TABLE account_device_observations (
  account_id TEXT NOT NULL REFERENCES accounts(id),
  installation_id TEXT NOT NULL,
  uid TEXT NOT NULL,
  firmware_version INTEGER NOT NULL,
  image_sha256 TEXT NOT NULL,
  observed_at INTEGER NOT NULL,
  PRIMARY KEY(account_id,installation_id,uid)
);
CREATE INDEX account_observations_uid ON account_device_observations(account_id,uid,observed_at);
