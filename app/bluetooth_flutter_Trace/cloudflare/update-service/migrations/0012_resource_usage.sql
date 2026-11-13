-- A shared lease bounds provider queries across tabs and Pages isolates.
CREATE TABLE admin_resource_usage_cache (
  cache_key TEXT PRIMARY KEY,
  checked_at INTEGER NOT NULL DEFAULT 0,
  lease_until INTEGER NOT NULL DEFAULT 0,
  lease TEXT NOT NULL DEFAULT '',
  snapshot_json TEXT
);
