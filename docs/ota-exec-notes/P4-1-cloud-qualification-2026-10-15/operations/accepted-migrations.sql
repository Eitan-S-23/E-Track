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

INSERT INTO "d1_migrations" (name) VALUES ('0001_init.sql');
PRAGMA foreign_keys = OFF;

DROP INDEX IF EXISTS idx_patches_lookup;

CREATE TABLE IF NOT EXISTS patches_new (
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

INSERT OR IGNORE INTO patches_new (
  id,
  app_id,
  platform,
  to_release_id,
  asset_id,
  from_version_code,
  old_sha256,
  patch_format,
  patch_sha256,
  patch_size_bytes,
  output_sha256,
  output_size_bytes,
  disabled,
  created_at,
  updated_at
)
SELECT
  id,
  app_id,
  platform,
  to_release_id,
  asset_id,
  from_version_code,
  old_sha256,
  'tracepatch',
  patch_sha256,
  patch_size_bytes,
  output_sha256,
  output_size_bytes,
  disabled,
  created_at,
  updated_at
FROM patches;

DROP TABLE patches;
ALTER TABLE patches_new RENAME TO patches;

CREATE INDEX IF NOT EXISTS idx_patches_lookup
  ON patches(app_id, platform, to_release_id, from_version_code, old_sha256);

PRAGMA foreign_keys = ON;

INSERT INTO "d1_migrations" (name) VALUES ('0002_patch_formats.sql');
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

INSERT INTO "d1_migrations" (name) VALUES ('0003_firmware_releases.sql');
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS announcements (
  id TEXT PRIMARY KEY,
  app_id TEXT NOT NULL,
  title TEXT NOT NULL CHECK (length(title) BETWEEN 1 AND 120),
  body TEXT NOT NULL CHECK (length(body) BETWEEN 1 AND 8000),
  pinned INTEGER NOT NULL DEFAULT 0 CHECK (pinned IN (0, 1)),
  published INTEGER NOT NULL DEFAULT 1 CHECK (published IN (0, 1)),
  published_at TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (app_id) REFERENCES apps(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_announcements_public
ON announcements(app_id, published, pinned, published_at, updated_at);

INSERT INTO "d1_migrations" (name) VALUES ('0004_announcements.sql');
-- Run as one D1 migration transaction. Keep every legacy byte until an approved
-- manifest and artifact readback authorize backfill; never invent image identity.
DROP TRIGGER firmware_channels_reject_disabled_release_insert;
DROP TRIGGER firmware_channels_reject_disabled_release_update;
DROP TRIGGER firmware_releases_reject_disable_when_published;
ALTER TABLE firmware_channels RENAME TO firmware_channels_legacy;
ALTER TABLE firmware_releases RENAME TO firmware_releases_legacy;

CREATE TABLE firmware_releases (
  id TEXT NOT NULL PRIMARY KEY CHECK (length(trim(id)) > 0),
  app_id TEXT NOT NULL REFERENCES apps(id) ON DELETE CASCADE,
  device_model TEXT NOT NULL CHECK (length(trim(device_model)) > 0),
  version_name TEXT NOT NULL CHECK (length(trim(version_name)) > 0),
  version_code INTEGER NOT NULL CHECK (typeof(version_code) = 'integer' AND version_code BETWEEN 0 AND 4294967295),
  release_tag TEXT NOT NULL CHECK (length(trim(release_tag)) > 0),
  commit_sha TEXT NOT NULL CHECK (length(commit_sha) = 40 AND commit_sha NOT GLOB '*[^0-9a-f]*'),
  run_id TEXT NOT NULL CHECK (length(trim(run_id)) > 0),
  state TEXT NOT NULL DEFAULT 'draft' CHECK (state IN ('draft','ready','disabled')),
  release_notes TEXT NOT NULL DEFAULT '',
  target_image_sha256 TEXT NOT NULL CHECK (length(target_image_sha256) = 64 AND target_image_sha256 NOT GLOB '*[^0-9a-f]*'),
  hardware_rev INTEGER NOT NULL CHECK (typeof(hardware_rev) = 'integer' AND hardware_rev BETWEEN 0 AND 65535),
  layout_id INTEGER NOT NULL CHECK (typeof(layout_id) = 'integer' AND layout_id BETWEEN 0 AND 255),
  min_boot_version INTEGER NOT NULL CHECK (typeof(min_boot_version) = 'integer' AND min_boot_version BETWEEN 0 AND 255),
  min_protocol_version INTEGER NOT NULL CHECK (typeof(min_protocol_version) = 'integer' AND min_protocol_version BETWEEN 0 AND 255),
  target_hardware TEXT NOT NULL CHECK (length(trim(target_hardware)) > 0),
  transport TEXT NOT NULL DEFAULT 'ble' CHECK (transport = 'ble'),
  min_app_version_code INTEGER NOT NULL DEFAULT 0 CHECK (typeof(min_app_version_code) = 'integer' AND min_app_version_code BETWEEN 0 AND 2100000000),
  archived INTEGER NOT NULL DEFAULT 0 CHECK (archived IN (0,1)),
  registration_json TEXT CHECK (registration_json IS NULL OR (json_valid(registration_json) AND json_type(registration_json) = 'object')),
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now')),
  UNIQUE (app_id,device_model,release_tag),
  UNIQUE (app_id,device_model,version_code),
  UNIQUE (app_id,device_model,run_id)
);

CREATE TABLE firmware_release_assets (
  id TEXT NOT NULL PRIMARY KEY CHECK (length(trim(id)) > 0),
  release_id TEXT NOT NULL REFERENCES firmware_releases(id) ON DELETE CASCADE,
  kind TEXT NOT NULL CHECK (kind IN ('full','patch','recovery')),
  file_name TEXT NOT NULL CHECK (
    length(file_name) BETWEEN 1 AND 128 AND length(trim(file_name)) > 0 AND file_name NOT IN ('.','..')
    AND file_name NOT GLOB '*[^ -~]*' AND instr(file_name,'/') = 0
    AND instr(file_name,char(92)) = 0 AND instr(file_name,char(0)) = 0
  ),
  sha256 TEXT NOT NULL CHECK (length(sha256) = 64 AND sha256 NOT GLOB '*[^0-9a-f]*'),
  size_bytes INTEGER NOT NULL CHECK (typeof(size_bytes) = 'integer' AND size_bytes > 0),
  r2_key TEXT,
  r2_etag TEXT,
  r2_state TEXT NOT NULL DEFAULT 'not_uploaded' CHECK (r2_state IN ('not_uploaded','available','archived','r2_deleted')),
  github_url TEXT NOT NULL CHECK (length(trim(github_url)) > 0 AND instr(github_url,'/latest/download/') = 0),
  base_image_sha256 TEXT NOT NULL DEFAULT '',
  base_vcode INTEGER NOT NULL DEFAULT 0 CHECK (typeof(base_vcode) = 'integer'),
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now')),
  CHECK ((kind = 'patch' AND length(base_image_sha256) = 64
          AND base_image_sha256 NOT GLOB '*[^0-9a-f]*' AND base_vcode > 0)
      OR (kind IN ('full','recovery') AND base_image_sha256 = '' AND base_vcode = 0)),
  CHECK (r2_state <> 'available' OR (r2_key IS NOT NULL AND length(trim(r2_key)) > 0
    AND r2_etag IS NOT NULL AND length(trim(r2_etag)) > 0)),
  UNIQUE (release_id,kind,base_image_sha256),
  UNIQUE (release_id,file_name),
  UNIQUE (r2_key)
);
CREATE INDEX idx_firmware_v2_assets_release ON firmware_release_assets(release_id);
CREATE INDEX idx_firmware_v2_patch_base ON firmware_release_assets(base_image_sha256,kind,r2_state);

CREATE TABLE firmware_channels (
  id TEXT NOT NULL PRIMARY KEY,
  app_id TEXT NOT NULL REFERENCES apps(id) ON DELETE CASCADE,
  device_model TEXT NOT NULL CHECK (length(trim(device_model)) > 0),
  name TEXT NOT NULL CHECK (name IN ('stable','beta')),
  current_release_id TEXT REFERENCES firmware_releases(id) ON DELETE SET NULL,
  -- This is an unresolved migration marker, never a second distribution source.
  legacy_current_release_id TEXT REFERENCES firmware_releases_legacy(id),
  revision INTEGER NOT NULL DEFAULT 0 CHECK (typeof(revision) = 'integer' AND revision >= 0),
  disable_latest INTEGER NOT NULL DEFAULT 0 CHECK (disable_latest IN (0,1)),
  disable_downloads INTEGER NOT NULL DEFAULT 0 CHECK (disable_downloads IN (0,1)),
  maintenance_message TEXT,
  last_action TEXT NOT NULL DEFAULT 'init' CHECK (last_action IN ('init','publish','retract','stop_latest','resume_latest','stop_downloads','resume_downloads')),
  last_actor TEXT,
  last_actor_type TEXT CHECK (last_actor_type IS NULL OR last_actor_type IN ('ci','access','system','test')),
  last_request_id TEXT,
  last_reason TEXT,
  last_before_json TEXT,
  last_after_json TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now')),
  CHECK (current_release_id IS NULL OR legacy_current_release_id IS NULL),
  UNIQUE (app_id,device_model,name)
);
INSERT INTO firmware_channels (
  id,app_id,device_model,name,legacy_current_release_id,revision,
  disable_latest,disable_downloads,maintenance_message,last_action,last_actor,
  last_actor_type,last_request_id,last_before_json,last_after_json,created_at,updated_at
)
SELECT id,app_id,device_model,name,current_release_id,revision,
  disable_latest,disable_downloads,maintenance_message,
  CASE last_action WHEN 'rollback' THEN 'retract' ELSE last_action END,last_actor,
  last_actor_type,last_request_id,last_before_json,last_after_json,created_at,updated_at
FROM firmware_channels_legacy;

CREATE TABLE firmware_backfill_manifests (
  release_id TEXT NOT NULL PRIMARY KEY REFERENCES firmware_releases(id),
  manifest_sha256 TEXT NOT NULL CHECK (length(manifest_sha256) = 64 AND manifest_sha256 NOT GLOB '*[^0-9a-f]*'),
  manifest_json TEXT NOT NULL CHECK (json_valid(manifest_json) AND json_type(manifest_json) = 'object'),
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

ALTER TABLE audit_logs ADD COLUMN reason TEXT;
CREATE TRIGGER firmware_audit_reason BEFORE INSERT ON audit_logs
WHEN NEW.target_type IN ('firmware_release','firmware_asset','firmware_channel')
  AND NEW.actor_type = 'access' AND (NEW.reason IS NULL OR length(trim(NEW.reason,char(9)||char(10)||char(11)||char(12)||char(13)||' ')) = 0)
BEGIN SELECT RAISE(ABORT,'firmware admin reason required'); END;
CREATE TRIGGER firmware_audit_values BEFORE INSERT ON audit_logs
WHEN NEW.target_type IN ('firmware_release','firmware_asset','firmware_channel') AND (
  NEW.id IS NULL OR length(trim(NEW.id)) = 0 OR length(trim(NEW.actor)) = 0
  OR length(trim(NEW.request_id)) = 0 OR NEW.after_json IS NULL
  OR NOT json_valid(NEW.after_json) OR json_type(NEW.after_json) <> 'object'
  OR (NEW.before_json IS NOT NULL AND (NOT json_valid(NEW.before_json) OR json_type(NEW.before_json) <> 'object')))
BEGIN SELECT RAISE(ABORT,'firmware audit identity and object snapshots required'); END;

CREATE TRIGGER firmware_asset_base_insert BEFORE INSERT ON firmware_release_assets
WHEN NEW.kind = 'patch' AND NOT EXISTS (
  SELECT 1 FROM firmware_releases WHERE id = NEW.release_id AND version_code > NEW.base_vcode)
BEGIN SELECT RAISE(ABORT,'firmware patch base version must precede target'); END;
CREATE TRIGGER firmware_ready_assets_sealed BEFORE INSERT ON firmware_release_assets
WHEN EXISTS (SELECT 1 FROM firmware_releases WHERE id=NEW.release_id AND state='ready')
BEGIN SELECT RAISE(ABORT,'ready firmware asset set is sealed'); END;

CREATE TRIGGER firmware_ready_insert BEFORE INSERT ON firmware_releases
WHEN NEW.state = 'ready'
BEGIN SELECT RAISE(ABORT,'firmware ready requires draft assets'); END;
CREATE TRIGGER firmware_ready_update BEFORE UPDATE OF state ON firmware_releases
WHEN NEW.state = 'ready' AND (
  (SELECT count(*) FROM firmware_release_assets WHERE release_id = NEW.id AND kind = 'full') <> 1
  OR EXISTS (SELECT 1 FROM firmware_release_assets WHERE release_id = NEW.id
    AND (r2_state <> 'available' OR r2_key IS NULL OR length(trim(r2_key)) = 0)))
BEGIN SELECT RAISE(ABORT,'firmware ready requires exactly one full and verified assets'); END;
CREATE TRIGGER firmware_state_transition BEFORE UPDATE OF state ON firmware_releases
WHEN (OLD.state = 'disabled' AND NEW.state <> 'disabled')
  OR (OLD.state = 'ready' AND NEW.state = 'draft')
BEGIN SELECT RAISE(ABORT,'firmware release state transition forbidden'); END;
CREATE TRIGGER firmware_release_referenced BEFORE UPDATE OF state,archived ON firmware_releases
WHEN (NEW.state <> 'ready' OR NEW.archived = 1)
  AND EXISTS (SELECT 1 FROM firmware_channels WHERE current_release_id = NEW.id)
BEGIN SELECT RAISE(ABORT,'firmware release is in use'); END;

CREATE TRIGGER firmware_pointer_insert BEFORE INSERT ON firmware_channels
WHEN NEW.current_release_id IS NOT NULL AND NOT EXISTS (
  SELECT 1 FROM firmware_releases r WHERE r.id = NEW.current_release_id
    AND r.app_id = NEW.app_id AND r.device_model = NEW.device_model AND r.state = 'ready' AND r.archived = 0)
BEGIN SELECT RAISE(ABORT,'firmware channel requires same-scope ready release'); END;
CREATE TRIGGER firmware_pointer_update BEFORE UPDATE OF current_release_id,app_id,device_model ON firmware_channels
WHEN NEW.current_release_id IS NOT NULL AND NOT EXISTS (
  SELECT 1 FROM firmware_releases r WHERE r.id = NEW.current_release_id
    AND r.app_id = NEW.app_id AND r.device_model = NEW.device_model AND r.state = 'ready' AND r.archived = 0)
BEGIN SELECT RAISE(ABORT,'firmware channel requires same-scope ready release'); END;
CREATE TRIGGER firmware_publish_regression BEFORE UPDATE OF current_release_id,revision ON firmware_channels
WHEN NEW.revision <> OLD.revision AND NEW.last_action = 'publish'
  AND (SELECT version_code FROM firmware_releases WHERE id = NEW.current_release_id)
    <= COALESCE((SELECT version_code FROM firmware_releases WHERE id = OLD.current_release_id),
      (SELECT version_code FROM firmware_releases_legacy WHERE id = OLD.legacy_current_release_id))
BEGIN SELECT RAISE(ABORT,'firmware version regression'); END;
CREATE TRIGGER firmware_channel_identity BEFORE UPDATE OF id,app_id,device_model,name,created_at ON firmware_channels
BEGIN SELECT RAISE(ABORT,'firmware channel identity is immutable'); END;
CREATE TRIGGER firmware_channel_no_new_legacy BEFORE INSERT ON firmware_channels
WHEN NEW.legacy_current_release_id IS NOT NULL
BEGIN SELECT RAISE(ABORT,'new legacy channel reference forbidden'); END;
CREATE TRIGGER firmware_channel_no_legacy_retarget BEFORE UPDATE OF legacy_current_release_id ON firmware_channels
WHEN NEW.legacy_current_release_id IS NOT NULL AND NEW.legacy_current_release_id IS NOT OLD.legacy_current_release_id
BEGIN SELECT RAISE(ABORT,'legacy channel retarget forbidden'); END;
CREATE TRIGGER firmware_channel_mutation_guard BEFORE UPDATE ON firmware_channels
WHEN (NEW.current_release_id IS NOT OLD.current_release_id OR NEW.legacy_current_release_id IS NOT OLD.legacy_current_release_id
  OR NEW.disable_latest <> OLD.disable_latest OR NEW.disable_downloads <> OLD.disable_downloads
  OR NEW.maintenance_message IS NOT OLD.maintenance_message)
  AND NEW.revision <> OLD.revision + 1
  AND NOT (OLD.legacy_current_release_id IS NOT NULL AND NEW.current_release_id = OLD.legacy_current_release_id
    AND NEW.legacy_current_release_id IS NULL AND NEW.revision = OLD.revision
    AND NEW.disable_latest = OLD.disable_latest AND NEW.disable_downloads = OLD.disable_downloads
    AND NEW.maintenance_message IS OLD.maintenance_message
    AND EXISTS (SELECT 1 FROM firmware_backfill_manifests WHERE release_id=NEW.current_release_id))
BEGIN SELECT RAISE(ABORT,'firmware channel mutation requires CAS revision'); END;
CREATE TRIGGER firmware_channel_revision BEFORE UPDATE OF revision ON firmware_channels
WHEN NEW.revision <> OLD.revision AND (NEW.revision <> OLD.revision + 1
  OR NEW.last_actor IS NULL OR length(trim(NEW.last_actor)) = 0
  OR NEW.last_actor_type IS NULL OR NEW.last_request_id IS NULL
  OR NEW.last_reason IS NULL OR length(trim(NEW.last_reason)) = 0
  OR NEW.last_before_json IS NULL OR NOT json_valid(NEW.last_before_json)
  OR NEW.last_after_json IS NULL OR NOT json_valid(NEW.last_after_json))
BEGIN SELECT RAISE(ABORT,'firmware mutation requires revision and audit context'); END;
CREATE TRIGGER firmware_channel_audit AFTER UPDATE ON firmware_channels
WHEN NEW.revision <> OLD.revision
BEGIN
  INSERT INTO audit_logs(id,app_id,actor,actor_type,action,target_type,target_id,
    request_id,reason,before_json,after_json)
  VALUES ('audit_' || lower(hex(randomblob(16))),NEW.app_id,NEW.last_actor,
    NEW.last_actor_type,NEW.last_action,'firmware_channel',NEW.id,
    NEW.last_request_id,NEW.last_reason,NEW.last_before_json,NEW.last_after_json);
END;

CREATE TRIGGER firmware_release_identity BEFORE UPDATE OF
  id,app_id,device_model,version_name,version_code,release_tag,commit_sha,run_id,
  target_image_sha256,hardware_rev,layout_id,min_boot_version,min_protocol_version,
  target_hardware,transport,min_app_version_code,registration_json,created_at ON firmware_releases
BEGIN SELECT RAISE(ABORT,'firmware release identity is immutable'); END;
CREATE TRIGGER firmware_asset_identity BEFORE UPDATE OF
  id,release_id,kind,file_name,sha256,size_bytes,github_url,base_image_sha256,base_vcode,created_at ON firmware_release_assets
BEGIN SELECT RAISE(ABORT,'firmware asset identity is immutable'); END;
CREATE TRIGGER firmware_r2_identity BEFORE UPDATE OF r2_key,r2_etag ON firmware_release_assets
WHEN (OLD.r2_key IS NOT NULL AND NEW.r2_key IS NOT OLD.r2_key)
  OR (OLD.r2_etag IS NOT NULL AND NEW.r2_etag IS NOT OLD.r2_etag)
BEGIN SELECT RAISE(ABORT,'verified firmware R2 identity is immutable'); END;
CREATE TRIGGER firmware_release_no_delete BEFORE DELETE ON firmware_releases
BEGIN SELECT RAISE(ABORT,'firmware release history is retained'); END;
CREATE TRIGGER firmware_asset_no_delete BEFORE DELETE ON firmware_release_assets
BEGIN SELECT RAISE(ABORT,'firmware asset history is retained'); END;
CREATE TRIGGER firmware_manifest_no_update BEFORE UPDATE ON firmware_backfill_manifests
BEGIN SELECT RAISE(ABORT,'firmware manifest is immutable'); END;
CREATE TRIGGER firmware_manifest_no_delete BEFORE DELETE ON firmware_backfill_manifests
BEGIN SELECT RAISE(ABORT,'firmware manifest is retained'); END;
CREATE TRIGGER firmware_legacy_release_no_insert BEFORE INSERT ON firmware_releases_legacy
BEGIN SELECT RAISE(ABORT,'legacy firmware is read only'); END;
CREATE TRIGGER firmware_legacy_release_no_update BEFORE UPDATE ON firmware_releases_legacy
BEGIN SELECT RAISE(ABORT,'legacy firmware is read only'); END;
CREATE TRIGGER firmware_legacy_release_no_delete BEFORE DELETE ON firmware_releases_legacy
BEGIN SELECT RAISE(ABORT,'legacy firmware is retained'); END;
CREATE TRIGGER firmware_legacy_channel_no_insert BEFORE INSERT ON firmware_channels_legacy
BEGIN SELECT RAISE(ABORT,'legacy channel is read only'); END;
CREATE TRIGGER firmware_legacy_channel_no_update BEFORE UPDATE ON firmware_channels_legacy
BEGIN SELECT RAISE(ABORT,'legacy channel is read only'); END;
CREATE TRIGGER firmware_legacy_channel_no_delete BEFORE DELETE ON firmware_channels_legacy
BEGIN SELECT RAISE(ABORT,'legacy channel is retained'); END;

CREATE TABLE firmware_admin_idempotency (
  actor_canonical TEXT NOT NULL CHECK (length(trim(actor_canonical)) > 0 AND actor_canonical = lower(trim(actor_canonical))),
  idempotency_key TEXT NOT NULL CHECK (length(idempotency_key) = 36
    AND substr(idempotency_key,9,1) = '-' AND substr(idempotency_key,14,1) = '-'
    AND substr(idempotency_key,19,1) = '-' AND substr(idempotency_key,24,1) = '-'
    AND substr(idempotency_key,15,1) = '4' AND substr(idempotency_key,20,1) IN ('8','9','a','b')
    AND length(replace(idempotency_key,'-','')) = 32 AND replace(idempotency_key,'-','') NOT GLOB '*[^0-9a-f]*'),
  fingerprint TEXT NOT NULL CHECK (length(fingerprint) = 64 AND fingerprint NOT GLOB '*[^0-9a-f]*'),
  method TEXT NOT NULL CHECK (method = 'POST'),
  canonical_path TEXT NOT NULL,
  action TEXT NOT NULL CHECK (action IN ('disable','recovery-download')),
  release_id TEXT NOT NULL REFERENCES firmware_releases(id),
  state TEXT NOT NULL CHECK (state IN ('pending','completed')),
  status_code INTEGER,
  response_body_json TEXT,
  request_id TEXT,
  created_epoch_seconds INTEGER NOT NULL CHECK (typeof(created_epoch_seconds) = 'integer' AND created_epoch_seconds >= 0),
  retained_until INTEGER NOT NULL CHECK (retained_until = created_epoch_seconds + 86400),
  original_expires_at INTEGER,
  -- Deferred self-reference permits pending only inside the atomic batch.
  completed_state TEXT NOT NULL DEFAULT 'completed' CHECK (completed_state = 'completed'),
  PRIMARY KEY (actor_canonical,idempotency_key),
  UNIQUE (actor_canonical,idempotency_key,completed_state),
  FOREIGN KEY (actor_canonical,idempotency_key,state)
    REFERENCES firmware_admin_idempotency(actor_canonical,idempotency_key,completed_state)
    DEFERRABLE INITIALLY DEFERRED,
  CHECK (canonical_path = '/api/admin/firmware/releases/' || release_id || '/' || action),
  CHECK (state <> 'completed' OR (status_code IS NOT NULL AND status_code = 200
    AND response_body_json IS NOT NULL AND json_valid(response_body_json)
    AND json_type(response_body_json) = 'object' AND request_id IS NOT NULL AND length(request_id) > 0
    AND COALESCE(json_type(response_body_json,'$.requestId'),'missing') = 'text'
    AND json_extract(response_body_json,'$.requestId') = request_id)),
  CHECK ((action = 'disable' AND original_expires_at IS NULL)
    OR (action = 'recovery-download' AND (state = 'pending'
      OR (original_expires_at IS NOT NULL AND original_expires_at = created_epoch_seconds + 300))))
);
CREATE INDEX idx_firmware_idempotency_retained ON firmware_admin_idempotency(retained_until);
CREATE TRIGGER firmware_idempotency_starts_pending BEFORE INSERT ON firmware_admin_idempotency
WHEN NEW.state <> 'pending'
BEGIN SELECT RAISE(ABORT,'firmware idempotency must reserve pending before completion'); END;

CREATE TABLE firmware_admin_idempotency_tombstones (
  actor_canonical TEXT NOT NULL CHECK (length(trim(actor_canonical)) > 0 AND actor_canonical = lower(trim(actor_canonical))),
  idempotency_key TEXT NOT NULL CHECK (length(idempotency_key) = 36
    AND substr(idempotency_key,9,1) = '-' AND substr(idempotency_key,14,1) = '-'
    AND substr(idempotency_key,19,1) = '-' AND substr(idempotency_key,24,1) = '-'
    AND substr(idempotency_key,15,1) = '4' AND substr(idempotency_key,20,1) IN ('8','9','a','b')
    AND length(replace(idempotency_key,'-','')) = 32 AND replace(idempotency_key,'-','') NOT GLOB '*[^0-9a-f]*'),
  fingerprint TEXT NOT NULL CHECK (length(fingerprint) = 64 AND fingerprint NOT GLOB '*[^0-9a-f]*'),
  action TEXT NOT NULL CHECK (action IN ('disable','recovery-download')),
  release_id TEXT NOT NULL REFERENCES firmware_releases(id),
  expired_at INTEGER NOT NULL CHECK (typeof(expired_at) = 'integer' AND expired_at >= 86400),
  tombstoned_at INTEGER NOT NULL CHECK (typeof(tombstoned_at) = 'integer' AND tombstoned_at >= expired_at),
  PRIMARY KEY (actor_canonical,idempotency_key)
);
CREATE INDEX idx_firmware_tombstone_expired ON firmware_admin_idempotency_tombstones(expired_at);
CREATE TRIGGER firmware_tombstone_consistent BEFORE INSERT ON firmware_admin_idempotency_tombstones
WHEN EXISTS (SELECT 1 FROM firmware_admin_idempotency_tombstones t
  WHERE t.actor_canonical = NEW.actor_canonical AND t.idempotency_key = NEW.idempotency_key
    AND (t.fingerprint <> NEW.fingerprint OR t.action <> NEW.action
      OR t.release_id <> NEW.release_id OR t.expired_at <> NEW.expired_at))
  OR EXISTS (SELECT 1 FROM firmware_admin_idempotency i
  WHERE i.actor_canonical = NEW.actor_canonical AND i.idempotency_key = NEW.idempotency_key
    AND (i.state <> 'completed' OR i.fingerprint <> NEW.fingerprint OR i.action <> NEW.action
      OR i.release_id <> NEW.release_id OR i.retained_until <> NEW.expired_at))
BEGIN SELECT RAISE(ABORT,'firmware tombstone integrity mismatch'); END;
CREATE TRIGGER firmware_tombstone_no_update BEFORE UPDATE ON firmware_admin_idempotency_tombstones
BEGIN SELECT RAISE(ABORT,'firmware tombstone is immutable'); END;
CREATE TRIGGER firmware_tombstone_no_delete BEFORE DELETE ON firmware_admin_idempotency_tombstones
BEGIN SELECT RAISE(ABORT,'firmware tombstone is permanent'); END;
CREATE TRIGGER firmware_idempotency_no_reuse BEFORE INSERT ON firmware_admin_idempotency
WHEN EXISTS (SELECT 1 FROM firmware_admin_idempotency_tombstones
  WHERE actor_canonical = NEW.actor_canonical AND idempotency_key = NEW.idempotency_key)
BEGIN SELECT RAISE(ABORT,'firmware idempotency key is tombstoned'); END;
CREATE TRIGGER firmware_idempotency_immutable BEFORE UPDATE ON firmware_admin_idempotency
WHEN OLD.state = 'completed' OR NEW.state <> 'completed'
  OR NEW.actor_canonical <> OLD.actor_canonical OR NEW.idempotency_key <> OLD.idempotency_key
  OR NEW.fingerprint <> OLD.fingerprint OR NEW.method <> OLD.method OR NEW.canonical_path <> OLD.canonical_path
  OR NEW.action <> OLD.action OR NEW.release_id <> OLD.release_id
  OR NEW.created_epoch_seconds <> OLD.created_epoch_seconds OR NEW.retained_until <> OLD.retained_until
BEGIN SELECT RAISE(ABORT,'firmware idempotency result is immutable'); END;
CREATE TRIGGER firmware_idempotency_delete_guard BEFORE DELETE ON firmware_admin_idempotency
WHEN NOT EXISTS (SELECT 1 FROM firmware_admin_idempotency_tombstones t
  WHERE t.actor_canonical = OLD.actor_canonical AND t.idempotency_key = OLD.idempotency_key
    AND t.fingerprint = OLD.fingerprint AND t.action = OLD.action
    AND t.release_id = OLD.release_id AND t.expired_at = OLD.retained_until)
BEGIN SELECT RAISE(ABORT,'firmware result cleanup requires matching tombstone first'); END;

INSERT INTO "d1_migrations" (name) VALUES ('0005_firmware_multi_asset.sql');
