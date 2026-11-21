CREATE TABLE account_settings (
  app_id TEXT PRIMARY KEY,
  registration_enabled INTEGER NOT NULL DEFAULT 1 CHECK(registration_enabled IN (0,1)),
  password_registration_enabled INTEGER NOT NULL DEFAULT 1 CHECK(password_registration_enabled IN (0,1)),
  email_verification_enabled INTEGER NOT NULL DEFAULT 0 CHECK(email_verification_enabled IN (0,1)),
  automatic_daily_limit INTEGER NOT NULL DEFAULT 5 CHECK(automatic_daily_limit BETWEEN 0 AND 1000),
  manual_daily_limit INTEGER NOT NULL DEFAULT 5 CHECK(manual_daily_limit BETWEEN 0 AND 1000),
  revision INTEGER NOT NULL DEFAULT 0
);
INSERT INTO account_settings(app_id) VALUES('trace');

CREATE TABLE accounts (
  id TEXT PRIMARY KEY,
  app_id TEXT NOT NULL,
  username TEXT NOT NULL COLLATE NOCASE,
  display_name TEXT NOT NULL,
  email TEXT COLLATE NOCASE,
  email_verified INTEGER NOT NULL DEFAULT 0,
  password_hash TEXT NOT NULL,
  state TEXT NOT NULL DEFAULT 'active' CHECK(state IN ('active','disabled','deleted')),
  created_at INTEGER NOT NULL,
  last_login_at INTEGER,
  UNIQUE(app_id,username),
  UNIQUE(app_id,email)
);
CREATE TABLE account_sessions (
  token_hash TEXT PRIMARY KEY,
  account_id TEXT NOT NULL REFERENCES accounts(id),
  created_at INTEGER NOT NULL,
  expires_at INTEGER NOT NULL,
  revoked_at INTEGER
);
CREATE INDEX account_sessions_account ON account_sessions(account_id,expires_at);
CREATE TABLE account_login_events (
  id TEXT PRIMARY KEY,
  account_id TEXT NOT NULL REFERENCES accounts(id),
  occurred_at INTEGER NOT NULL,
  app_version TEXT NOT NULL DEFAULT ''
);
CREATE INDEX account_logins_date ON account_login_events(occurred_at,account_id);
CREATE TABLE account_email_codes (
  id TEXT PRIMARY KEY,
  app_id TEXT NOT NULL,
  email TEXT NOT NULL COLLATE NOCASE,
  purpose TEXT NOT NULL CHECK(purpose IN ('register','reset')),
  code_hash TEXT NOT NULL,
  created_at INTEGER NOT NULL,
  expires_at INTEGER NOT NULL,
  used_at INTEGER
);
CREATE INDEX account_email_expiry ON account_email_codes(expires_at);

CREATE TABLE account_devices (
  app_id TEXT NOT NULL,
  uid TEXT NOT NULL,
  account_id TEXT NOT NULL REFERENCES accounts(id),
  name TEXT NOT NULL,
  model TEXT NOT NULL,
  hardware_revision INTEGER NOT NULL,
  firmware_version INTEGER NOT NULL,
  image_sha256 TEXT NOT NULL,
  bound_at INTEGER NOT NULL,
  last_seen_at INTEGER NOT NULL,
  PRIMARY KEY(app_id,uid)
);
CREATE INDEX account_devices_owner ON account_devices(account_id,bound_at);

CREATE TABLE account_update_checks (
  account_id TEXT NOT NULL REFERENCES accounts(id),
  check_id TEXT NOT NULL,
  day TEXT NOT NULL,
  kind TEXT NOT NULL CHECK(kind IN ('automatic','manual')),
  request_hash TEXT NOT NULL,
  state TEXT NOT NULL CHECK(state IN ('pending','complete','failed')),
  created_at INTEGER NOT NULL,
  lease_until INTEGER NOT NULL,
  lease_token TEXT NOT NULL,
  response_status INTEGER,
  response_json TEXT,
  PRIMARY KEY(account_id,check_id)
);
CREATE INDEX account_checks_budget ON account_update_checks(account_id,day,kind,state,lease_until);
CREATE INDEX account_checks_spacing ON account_update_checks(account_id,kind,created_at);
CREATE TABLE account_audit (
  id TEXT PRIMARY KEY,
  actor TEXT NOT NULL,
  action TEXT NOT NULL,
  account_id TEXT,
  device_uid TEXT,
  occurred_at INTEGER NOT NULL
);
