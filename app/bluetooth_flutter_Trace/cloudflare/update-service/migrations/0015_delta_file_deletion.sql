-- File retirement never rewrites a successful build or its reconstruction proof.
ALTER TABLE delta_jobs ADD COLUMN asset_state TEXT NOT NULL DEFAULT 'retained'
  CHECK(asset_state IN ('retained','deleting','deleted'))
  CHECK(asset_state='retained' OR (status='ready' AND enabled=0));

CREATE TRIGGER delta_file_no_restore BEFORE UPDATE OF asset_state ON delta_jobs
WHEN (OLD.asset_state='deleted' AND NEW.asset_state<>'deleted')
  OR (OLD.asset_state='deleting' AND NEW.asset_state='retained')
BEGIN SELECT RAISE(ABORT,'deleted delta file cannot be restored'); END;

CREATE TRIGGER app_delta_file_no_restore BEFORE UPDATE OF disabled,r2_state ON release_assets
WHEN (NEW.disabled<>1 OR NEW.r2_state='available') AND EXISTS(
  SELECT 1 FROM delta_jobs WHERE kind='android' AND 'asset_'||id=NEW.id AND asset_state<>'retained')
BEGIN SELECT RAISE(ABORT,'deleted delta asset cannot be restored'); END;
