-- Seal disabled releases before an owner can remove their immutable R2 files.
-- The release, asset identities and audit history remain in D1.
CREATE TRIGGER firmware_disabled_assets_sealed BEFORE INSERT ON firmware_release_assets
WHEN EXISTS (SELECT 1 FROM firmware_releases WHERE id=NEW.release_id
  AND (state='disabled' OR archived=1))
BEGIN SELECT RAISE(ABORT,'disabled firmware asset set is sealed'); END;

CREATE TRIGGER firmware_archive_no_reopen BEFORE UPDATE OF archived ON firmware_releases
WHEN OLD.archived=1 AND NEW.archived<>1
BEGIN SELECT RAISE(ABORT,'firmware archive is permanent'); END;

CREATE TRIGGER firmware_deleted_asset_no_restore BEFORE UPDATE OF r2_state ON firmware_release_assets
WHEN (OLD.r2_state='r2_deleted' AND NEW.r2_state<>'r2_deleted')
  OR (NEW.r2_state IN ('available','not_uploaded') AND EXISTS
    (SELECT 1 FROM firmware_releases WHERE id=NEW.release_id AND archived=1))
BEGIN SELECT RAISE(ABORT,'deleted firmware files cannot be restored'); END;
