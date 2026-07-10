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
