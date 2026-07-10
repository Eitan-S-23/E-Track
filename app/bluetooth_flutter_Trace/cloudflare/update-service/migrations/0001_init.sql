PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS apps (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS app_config (
  app_id TEXT PRIMARY KEY,
  default_channel TEXT NOT NULL DEFAULT 'stable' CHECK (default_channel IN ('stable', 'beta')),
  min_supported_client_version_code INTEGER NOT NULL DEFAULT 0 CHECK (min_supported_client_version_code >= 0),
  emergency_manifest_url TEXT,
  disable_all_latest INTEGER NOT NULL DEFAULT 0 CHECK (disable_all_latest IN (0, 1)),
  disable_all_downloads INTEGER NOT NULL DEFAULT 0 CHECK (disable_all_downloads IN (0, 1)),
  maintenance_message TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (app_id) REFERENCES apps(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS releases (
  id TEXT PRIMARY KEY,
  app_id TEXT NOT NULL,
  platform TEXT NOT NULL CHECK (platform IN ('android', 'windows')),
  version_name TEXT NOT NULL,
  version_code INTEGER NOT NULL CHECK (version_code >= 0),
  release_tag TEXT NOT NULL,
  commit_sha TEXT NOT NULL,
  run_id TEXT NOT NULL,
  state TEXT NOT NULL DEFAULT 'candidate' CHECK (state IN ('candidate', 'disabled')),
  payload_signature_json TEXT,
  security_payload_json TEXT NOT NULL,
  release_notes TEXT NOT NULL DEFAULT '',
  min_client_version_code INTEGER NOT NULL DEFAULT 0 CHECK (min_client_version_code >= 0),
  capabilities_json TEXT NOT NULL DEFAULT '[]',
  archived INTEGER NOT NULL DEFAULT 0 CHECK (archived IN (0, 1)),
  fallback_only INTEGER NOT NULL DEFAULT 0 CHECK (fallback_only IN (0, 1)),
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (app_id) REFERENCES apps(id) ON DELETE CASCADE,
  UNIQUE (app_id, platform, release_tag),
  UNIQUE (app_id, platform, run_id),
  UNIQUE (app_id, platform, version_code)
);

CREATE TABLE IF NOT EXISTS release_assets (
  id TEXT PRIMARY KEY,
  release_id TEXT NOT NULL,
  app_id TEXT NOT NULL,
  platform TEXT NOT NULL CHECK (platform IN ('android', 'windows')),
  asset_type TEXT NOT NULL CHECK (asset_type IN ('apk', 'windows_zip', 'windows_exe', 'manifest', 'patch')),
  file_name TEXT NOT NULL,
  sha256 TEXT NOT NULL CHECK (length(sha256) = 64),
  size_bytes INTEGER NOT NULL CHECK (size_bytes > 0),
  r2_key TEXT,
  r2_state TEXT NOT NULL DEFAULT 'not_uploaded' CHECK (r2_state IN ('not_uploaded', 'available', 'r2_deleted', 'archived')),
  github_url TEXT NOT NULL CHECK (instr(github_url, '/latest/download/') = 0),
  disabled INTEGER NOT NULL DEFAULT 0 CHECK (disabled IN (0, 1)),
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (release_id) REFERENCES releases(id) ON DELETE CASCADE,
  FOREIGN KEY (app_id) REFERENCES apps(id) ON DELETE CASCADE,
  UNIQUE (release_id, platform, asset_type, file_name),
  UNIQUE (app_id, platform, github_url)
);

CREATE TABLE IF NOT EXISTS patches (
  id TEXT PRIMARY KEY,
  app_id TEXT NOT NULL,
  platform TEXT NOT NULL CHECK (platform IN ('android', 'windows')),
  to_release_id TEXT NOT NULL,
  asset_id TEXT NOT NULL,
  from_version_code INTEGER NOT NULL CHECK (from_version_code >= 0),
  old_sha256 TEXT NOT NULL CHECK (length(old_sha256) = 64),
  patch_format TEXT NOT NULL DEFAULT 'tracepatch' CHECK (patch_format IN ('tracepatch', 'vcdiff')),
  patch_sha256 TEXT NOT NULL CHECK (length(patch_sha256) = 64),
  patch_size_bytes INTEGER NOT NULL CHECK (patch_size_bytes > 0),
  output_sha256 TEXT NOT NULL CHECK (length(output_sha256) = 64),
  output_size_bytes INTEGER NOT NULL CHECK (output_size_bytes > 0),
  disabled INTEGER NOT NULL DEFAULT 0 CHECK (disabled IN (0, 1)),
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (app_id) REFERENCES apps(id) ON DELETE CASCADE,
  FOREIGN KEY (to_release_id) REFERENCES releases(id) ON DELETE CASCADE,
  FOREIGN KEY (asset_id) REFERENCES release_assets(id) ON DELETE CASCADE,
  UNIQUE (app_id, platform, to_release_id, from_version_code, old_sha256, patch_format)
);

CREATE TABLE IF NOT EXISTS channels (
  id TEXT PRIMARY KEY,
  app_id TEXT NOT NULL,
  platform TEXT NOT NULL CHECK (platform IN ('android', 'windows')),
  name TEXT NOT NULL CHECK (name IN ('stable', 'beta')),
  current_release_id TEXT,
  revision INTEGER NOT NULL DEFAULT 0 CHECK (revision >= 0),
  disable_latest INTEGER NOT NULL DEFAULT 0 CHECK (disable_latest IN (0, 1)),
  disable_downloads INTEGER NOT NULL DEFAULT 0 CHECK (disable_downloads IN (0, 1)),
  maintenance_admin_only INTEGER NOT NULL DEFAULT 0 CHECK (maintenance_admin_only IN (0, 1)),
  maintenance_message TEXT,
  last_action TEXT NOT NULL DEFAULT 'init' CHECK (
    last_action IN (
      'init',
      'publish',
      'rollback',
      'stop_latest',
      'resume_latest',
      'stop_downloads',
      'resume_downloads',
      'edit_notes'
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
  FOREIGN KEY (current_release_id) REFERENCES releases(id) ON DELETE SET NULL,
  UNIQUE (app_id, platform, name)
);

CREATE TABLE IF NOT EXISTS channel_history (
  id TEXT PRIMARY KEY,
  channel_id TEXT NOT NULL,
  release_id TEXT,
  revision INTEGER NOT NULL CHECK (revision >= 0),
  action TEXT NOT NULL CHECK (
    action IN (
      'publish',
      'rollback',
      'stop_latest',
      'resume_latest',
      'stop_downloads',
      'resume_downloads',
      'edit_notes'
    )
  ),
  actor TEXT NOT NULL,
  actor_type TEXT NOT NULL CHECK (actor_type IN ('ci', 'access', 'system', 'test')),
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  request_id TEXT NOT NULL,
  before_json TEXT NOT NULL,
  after_json TEXT NOT NULL,
  FOREIGN KEY (channel_id) REFERENCES channels(id) ON DELETE CASCADE,
  FOREIGN KEY (release_id) REFERENCES releases(id) ON DELETE SET NULL,
  UNIQUE (channel_id, revision)
);

CREATE TABLE IF NOT EXISTS audit_logs (
  id TEXT PRIMARY KEY,
  app_id TEXT,
  actor TEXT NOT NULL,
  actor_type TEXT NOT NULL CHECK (actor_type IN ('ci', 'access', 'system', 'test')),
  action TEXT NOT NULL,
  target_type TEXT NOT NULL,
  target_id TEXT,
  request_id TEXT NOT NULL,
  ip TEXT,
  user_agent TEXT,
  before_json TEXT,
  after_json TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (app_id) REFERENCES apps(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_releases_app_platform_state ON releases(app_id, platform, state);
CREATE INDEX IF NOT EXISTS idx_release_assets_release_platform_type ON release_assets(release_id, platform, asset_type);
CREATE INDEX IF NOT EXISTS idx_release_assets_app_platform_type ON release_assets(app_id, platform, asset_type);
CREATE INDEX IF NOT EXISTS idx_patches_lookup ON patches(app_id, platform, to_release_id, from_version_code, old_sha256);
CREATE INDEX IF NOT EXISTS idx_channels_lookup ON channels(app_id, platform, name);
CREATE INDEX IF NOT EXISTS idx_channel_history_channel_revision ON channel_history(channel_id, revision);
CREATE INDEX IF NOT EXISTS idx_channel_history_release_created ON channel_history(release_id, created_at);
CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at ON audit_logs(created_at);
CREATE INDEX IF NOT EXISTS idx_audit_logs_actor_created_at ON audit_logs(actor, created_at);

CREATE TRIGGER IF NOT EXISTS channels_reject_disabled_release_insert
BEFORE INSERT ON channels
WHEN NEW.current_release_id IS NOT NULL
  AND EXISTS (SELECT 1 FROM releases WHERE id = NEW.current_release_id AND state = 'disabled')
BEGIN
  SELECT RAISE(ABORT, 'channel cannot point at disabled release');
END;

CREATE TRIGGER IF NOT EXISTS channels_reject_disabled_release_update
BEFORE UPDATE OF current_release_id ON channels
WHEN NEW.current_release_id IS NOT NULL
  AND EXISTS (SELECT 1 FROM releases WHERE id = NEW.current_release_id AND state = 'disabled')
BEGIN
  SELECT RAISE(ABORT, 'channel cannot point at disabled release');
END;

CREATE TRIGGER IF NOT EXISTS releases_reject_disable_when_published
BEFORE UPDATE OF state ON releases
WHEN NEW.state = 'disabled'
  AND EXISTS (SELECT 1 FROM channels WHERE current_release_id = NEW.id)
BEGIN
  SELECT RAISE(ABORT, 'published release cannot be disabled');
END;

CREATE TRIGGER IF NOT EXISTS channels_append_history
AFTER UPDATE OF current_release_id, revision, disable_latest, disable_downloads, maintenance_admin_only, maintenance_message ON channels
WHEN NEW.revision > OLD.revision AND NEW.last_action <> 'init'
BEGIN
  INSERT INTO channel_history (
    id,
    channel_id,
    release_id,
    revision,
    action,
    actor,
    actor_type,
    request_id,
    before_json,
    after_json
  )
  VALUES (
    'hist_' || lower(hex(randomblob(16))),
    NEW.id,
    NEW.current_release_id,
    NEW.revision,
    NEW.last_action,
    COALESCE(NEW.last_actor, 'system'),
    COALESCE(NEW.last_actor_type, 'system'),
    COALESCE(NEW.last_request_id, 'unknown'),
    COALESCE(NEW.last_before_json, '{}'),
    COALESCE(NEW.last_after_json, '{}')
  );

  INSERT INTO audit_logs (
    id,
    app_id,
    actor,
    actor_type,
    action,
    target_type,
    target_id,
    request_id,
    before_json,
    after_json
  )
  VALUES (
    'audit_' || lower(hex(randomblob(16))),
    NEW.app_id,
    COALESCE(NEW.last_actor, 'system'),
    COALESCE(NEW.last_actor_type, 'system'),
    NEW.last_action,
    'channel',
    NEW.id,
    COALESCE(NEW.last_request_id, 'unknown'),
    COALESCE(NEW.last_before_json, '{}'),
    COALESCE(NEW.last_after_json, '{}')
  );
END;

CREATE TRIGGER IF NOT EXISTS channel_history_no_update
BEFORE UPDATE ON channel_history
BEGIN
  SELECT RAISE(ABORT, 'channel_history is append-only');
END;

CREATE TRIGGER IF NOT EXISTS channel_history_no_delete
BEFORE DELETE ON channel_history
BEGIN
  SELECT RAISE(ABORT, 'channel_history is append-only');
END;

CREATE TRIGGER IF NOT EXISTS audit_logs_no_update
BEFORE UPDATE ON audit_logs
BEGIN
  SELECT RAISE(ABORT, 'audit_logs are append-only');
END;

CREATE TRIGGER IF NOT EXISTS audit_logs_no_delete
BEFORE DELETE ON audit_logs
BEGIN
  SELECT RAISE(ABORT, 'audit_logs are append-only');
END;
