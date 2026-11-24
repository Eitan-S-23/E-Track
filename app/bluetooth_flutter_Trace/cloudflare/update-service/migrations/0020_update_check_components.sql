ALTER TABLE account_settings ADD COLUMN firmware_automatic_daily_limit INTEGER NOT NULL DEFAULT 5
  CHECK(firmware_automatic_daily_limit BETWEEN 0 AND 1000);
ALTER TABLE account_settings ADD COLUMN firmware_manual_daily_limit INTEGER NOT NULL DEFAULT 5
  CHECK(firmware_manual_daily_limit BETWEEN 0 AND 1000);
UPDATE account_settings SET firmware_automatic_daily_limit=automatic_daily_limit,
  firmware_manual_daily_limit=manual_daily_limit;

-- Old request hashes cannot identify NO_UPDATE origins. Keep those records unclassified.
ALTER TABLE account_update_checks ADD COLUMN component TEXT NOT NULL DEFAULT 'legacy'
  CHECK(component IN ('app','firmware','legacy'));
CREATE INDEX account_checks_component_budget
  ON account_update_checks(account_id,component,day,kind,state,lease_until);
CREATE INDEX account_checks_component_spacing
  ON account_update_checks(account_id,component,kind,created_at);
