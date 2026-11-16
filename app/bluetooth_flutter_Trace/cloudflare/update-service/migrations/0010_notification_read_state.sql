-- Preserve existing read cursors; individual views do not consume unseen results.
ALTER TABLE delta_notifications ADD COLUMN read_at INTEGER
  CHECK(read_at IS NULL OR read_at > 0);
