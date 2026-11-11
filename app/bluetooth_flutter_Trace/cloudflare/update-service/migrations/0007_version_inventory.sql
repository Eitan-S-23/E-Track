-- Optional installation telemetry; no changes to immutable release records.
CREATE TABLE version_inventory_control (
  id INTEGER PRIMARY KEY CHECK(id = 1),
  refresh_id TEXT NOT NULL,
  requested_at INTEGER NOT NULL,
  requested_by TEXT NOT NULL,
  daily_limit INTEGER NOT NULL CHECK(daily_limit BETWEEN 1 AND 5000)
);
-- Leave shared D1 write headroom for downloads, indexes, cleanup and releases.
INSERT INTO version_inventory_control VALUES (1, 'initial', 0, 'system', 1000);

CREATE TABLE version_inventory_budget (
  day TEXT PRIMARY KEY,
  accepted INTEGER NOT NULL CHECK(accepted >= 0)
);

CREATE TABLE version_inventory_installations (
  install_key TEXT PRIMARY KEY CHECK(length(install_key) = 64),
  platform TEXT NOT NULL CHECK(platform = 'android'),
  version_code INTEGER NOT NULL CHECK(version_code BETWEEN 0 AND 2100000000),
  version_name TEXT NOT NULL CHECK(length(version_name) BETWEEN 1 AND 64),
  image_sha256 TEXT NOT NULL CHECK(length(image_sha256) = 64),
  sequence INTEGER NOT NULL CHECK(sequence > 0),
  state_hash TEXT NOT NULL CHECK(length(state_hash) = 64),
  first_seen INTEGER NOT NULL,
  last_seen INTEGER NOT NULL,
  refresh_id TEXT NOT NULL,
  report_day TEXT NOT NULL,
  day_count INTEGER NOT NULL CHECK(day_count BETWEEN 1 AND 8)
);
CREATE INDEX version_inventory_installations_seen ON version_inventory_installations(last_seen);

CREATE TABLE version_inventory_devices (
  install_key TEXT NOT NULL REFERENCES version_inventory_installations(install_key) ON DELETE CASCADE,
  device_key TEXT NOT NULL CHECK(length(device_key) = 64),
  identity_scope TEXT NOT NULL CHECK(identity_scope = 'installation'),
  device_model TEXT NOT NULL CHECK(device_model = 'e-track-at32f435'),
  version_code INTEGER NOT NULL CHECK(version_code BETWEEN 0 AND 4294967295),
  image_sha256 TEXT NOT NULL CHECK(length(image_sha256) = 64),
  hardware_revision INTEGER NOT NULL,
  layout_id INTEGER NOT NULL,
  observation_id TEXT NOT NULL,
  observed_at INTEGER NOT NULL,
  PRIMARY KEY(install_key, device_key)
);
CREATE INDEX version_inventory_devices_seen ON version_inventory_devices(observed_at);

CREATE TRIGGER version_inventory_budget_insert BEFORE INSERT ON version_inventory_installations
WHEN NOT EXISTS (SELECT 1 FROM version_inventory_installations WHERE install_key = NEW.install_key)
BEGIN
  SELECT CASE WHEN COALESCE((SELECT accepted FROM version_inventory_budget WHERE day = NEW.report_day), 0)
    >= (SELECT daily_limit FROM version_inventory_control WHERE id = 1)
    THEN RAISE(ABORT, 'inventory daily budget exhausted') END;
  INSERT INTO version_inventory_budget(day, accepted) VALUES (NEW.report_day, 1)
    ON CONFLICT(day) DO UPDATE SET accepted = accepted + 1;
END;

CREATE TRIGGER version_inventory_budget_update BEFORE UPDATE ON version_inventory_installations
BEGIN
  SELECT CASE WHEN NEW.sequence <= OLD.sequence THEN RAISE(ABORT, 'inventory stale sequence') END;
  SELECT CASE WHEN COALESCE((SELECT accepted FROM version_inventory_budget WHERE day = NEW.report_day), 0)
    >= (SELECT daily_limit FROM version_inventory_control WHERE id = 1)
    THEN RAISE(ABORT, 'inventory daily budget exhausted') END;
  INSERT INTO version_inventory_budget(day, accepted) VALUES (NEW.report_day, 1)
    ON CONFLICT(day) DO UPDATE SET accepted = accepted + 1;
END;
