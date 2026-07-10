PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS firmware_releases (
  id TEXT PRIMARY KEY,
  app_id TEXT NOT NULL,
  device_model TEXT NOT NULL,
  version_name TEXT NOT NULL,
  version_code INTEGER NOT NULL CHECK (version_code >= 0),
  release_tag TEXT NOT NULL,
  commit_sha TEXT NOT NULL,
  run_id TEXT NOT NULL,
  state TEXT NOT NULL DEFAULT 'candidate' CHECK (state IN ('candidate', 'disabled')),
  release_notes TEXT NOT NULL DEFAULT '',
  file_name TEXT NOT NULL,
  sha256 TEXT NOT NULL CHECK (length(sha256) = 64),
  size_bytes INTEGER NOT NULL CHECK (size_bytes > 0),
  r2_key TEXT,
  r2_state TEXT NOT NULL DEFAULT 'not_uploaded' CHECK (r2_state IN ('not_uploaded', 'available', 'r2_deleted', 'archived')),
  github_url TEXT NOT NULL CHECK (instr(github_url, '/latest/download/') = 0),
  target_hardware TEXT,
  transport TEXT NOT NULL DEFAULT 'ble',
  min_app_version_code INTEGER NOT NULL DEFAULT 0 CHECK (min_app_version_code >= 0),
  archived INTEGER NOT NULL DEFAULT 0 CHECK (archived IN (0, 1)),
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (app_id) REFERENCES apps(id) ON DELETE CASCADE,
  UNIQUE (app_id, device_model, release_tag),
  UNIQUE (app_id, device_model, run_id),
  UNIQUE (app_id, device_model, version_code)
);

CREATE TABLE IF NOT EXISTS firmware_channels (
  id TEXT PRIMARY KEY,
  app_id TEXT NOT NULL,
  device_model TEXT NOT NULL,
  name TEXT NOT NULL CHECK (name IN ('stable', 'beta')),
  current_release_id TEXT,
  revision INTEGER NOT NULL DEFAULT 0 CHECK (revision >= 0),
  disable_latest INTEGER NOT NULL DEFAULT 0 CHECK (disable_latest IN (0, 1)),
  disable_downloads INTEGER NOT NULL DEFAULT 0 CHECK (disable_downloads IN (0, 1)),
  maintenance_message TEXT,
  last_action TEXT NOT NULL DEFAULT 'init' CHECK (
    last_action IN (
      'init',
      'publish',
      'rollback',
      'stop_latest',
      'resume_latest',
      'stop_downloads',
      'resume_downloads'
    )
  ),
  last_actor TEXT,
  last_actor_type TEXT CHECK (last_actor_type IS NULL OR last_actor_type IN ('ci', 'access', 'system', 'test')),
  last_request_id TEXT,
  last_before_json TEXT,
  last_after_json TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (app_id) REFERENCES apps(id) ON DELETE CASCADE,
  FOREIGN KEY (current_release_id) REFERENCES firmware_releases(id) ON DELETE SET NULL,
  UNIQUE (app_id, device_model, name)
);

CREATE INDEX IF NOT EXISTS idx_firmware_releases_app_model_state
  ON firmware_releases(app_id, device_model, state);
CREATE INDEX IF NOT EXISTS idx_firmware_releases_r2
  ON firmware_releases(app_id, device_model, r2_state, archived);
CREATE INDEX IF NOT EXISTS idx_firmware_channels_lookup
  ON firmware_channels(app_id, device_model, name);

CREATE TRIGGER IF NOT EXISTS firmware_channels_reject_disabled_release_insert
BEFORE INSERT ON firmware_channels
WHEN NEW.current_release_id IS NOT NULL
  AND EXISTS (SELECT 1 FROM firmware_releases WHERE id = NEW.current_release_id AND state = 'disabled')
BEGIN
  SELECT RAISE(ABORT, 'firmware channel cannot point at disabled release');
END;

CREATE TRIGGER IF NOT EXISTS firmware_channels_reject_disabled_release_update
BEFORE UPDATE OF current_release_id ON firmware_channels
WHEN NEW.current_release_id IS NOT NULL
  AND EXISTS (SELECT 1 FROM firmware_releases WHERE id = NEW.current_release_id AND state = 'disabled')
BEGIN
  SELECT RAISE(ABORT, 'firmware channel cannot point at disabled release');
END;

CREATE TRIGGER IF NOT EXISTS firmware_releases_reject_disable_when_published
BEFORE UPDATE OF state ON firmware_releases
WHEN NEW.state = 'disabled'
  AND EXISTS (SELECT 1 FROM firmware_channels WHERE current_release_id = NEW.id)
BEGIN
  SELECT RAISE(ABORT, 'published firmware release cannot be disabled');
END;
