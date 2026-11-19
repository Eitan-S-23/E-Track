-- Nullable metadata keeps existing clients and observations valid.
ALTER TABLE version_inventory_installations ADD COLUMN phone_brand TEXT
  CHECK(phone_brand IS NULL OR length(phone_brand) BETWEEN 1 AND 80);
ALTER TABLE version_inventory_installations ADD COLUMN phone_model TEXT
  CHECK(phone_model IS NULL OR length(phone_model) BETWEEN 1 AND 80);
ALTER TABLE version_inventory_installations ADD COLUMN os_version TEXT
  CHECK(os_version IS NULL OR length(os_version) BETWEEN 1 AND 64);
ALTER TABLE version_inventory_installations ADD COLUMN report_ip TEXT
  CHECK(report_ip IS NULL OR length(report_ip) BETWEEN 2 AND 45);
ALTER TABLE version_inventory_installations ADD COLUMN quality_json TEXT
  CHECK(quality_json IS NULL OR (length(quality_json) <= 1024 AND json_valid(quality_json)));
CREATE INDEX version_inventory_app_details ON version_inventory_installations
  (platform, version_code, version_name, image_sha256, last_seen, install_key);
CREATE INDEX version_inventory_firmware_details ON version_inventory_devices
  (device_model, version_code, image_sha256, hardware_revision, layout_id, observed_at, install_key, device_key);
