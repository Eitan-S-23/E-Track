-- Supplemental assets do not unseal or rewrite the original release manifest.
CREATE TABLE delta_jobs (
  id TEXT PRIMARY KEY,
  kind TEXT NOT NULL CHECK(kind IN ('android','firmware')),
  target_release_id TEXT NOT NULL,
  base_release_id TEXT NOT NULL,
  target_sha256 TEXT NOT NULL CHECK(length(target_sha256)=64),
  base_sha256 TEXT NOT NULL CHECK(length(base_sha256)=64),
  base_version_code INTEGER NOT NULL,
  target_version_code INTEGER NOT NULL CHECK(target_version_code>base_version_code),
  status TEXT NOT NULL CHECK(status IN ('dispatching','queued','dispatch_unknown','running','ready','failed')),
  enabled INTEGER NOT NULL DEFAULT 0 CHECK(enabled IN (0,1)),
  attempt INTEGER NOT NULL DEFAULT 1 CHECK(attempt>0),
  revision INTEGER NOT NULL DEFAULT 0,
  input_json TEXT NOT NULL CHECK(json_valid(input_json)),
  input_sha256 TEXT NOT NULL CHECK(length(input_sha256)=64),
  workflow_commit TEXT NOT NULL CHECK(length(workflow_commit)=40),
  workflow_ref TEXT NOT NULL,
  mutation_id TEXT NOT NULL DEFAULT '',
  run_id TEXT,
  result_json TEXT CHECK(result_json IS NULL OR json_valid(result_json)),
  error_code TEXT,
  actor TEXT NOT NULL,
  reason TEXT NOT NULL CHECK(length(trim(reason))>0),
  created_at INTEGER NOT NULL,
  updated_at INTEGER NOT NULL,
  UNIQUE(kind,target_release_id,base_sha256),
  CHECK(enabled=0 OR status='ready')
);
CREATE INDEX delta_jobs_target ON delta_jobs(kind,target_release_id,enabled,status,base_version_code);
CREATE INDEX delta_jobs_created ON delta_jobs(created_at);
CREATE TRIGGER delta_job_daily_budget BEFORE INSERT ON delta_jobs
WHEN (SELECT COUNT(*) FROM delta_jobs WHERE created_at>=NEW.created_at-(NEW.created_at%86400))>=20
BEGIN SELECT RAISE(ABORT,'delta job daily budget exhausted'); END;
CREATE TRIGGER delta_job_inputs_immutable BEFORE UPDATE OF
  id,kind,target_release_id,base_release_id,target_sha256,base_sha256,base_version_code,target_version_code,
  input_json,input_sha256,actor,reason,created_at ON delta_jobs
BEGIN SELECT RAISE(ABORT,'delta job inputs are immutable'); END;
CREATE TRIGGER delta_job_ready_immutable BEFORE UPDATE OF status,attempt,run_id,result_json ON delta_jobs
WHEN OLD.status='ready'
BEGIN SELECT RAISE(ABORT,'ready delta artifact is immutable'); END;
CREATE TRIGGER delta_job_attempt_binding BEFORE UPDATE OF workflow_commit,workflow_ref,attempt ON delta_jobs
WHEN NOT (OLD.status='failed' AND NEW.status='dispatching' AND NEW.attempt=OLD.attempt+1)
BEGIN SELECT RAISE(ABORT,'delta workflow binding changes only on explicit retry'); END;

CREATE TABLE delta_job_attempts (
  job_id TEXT NOT NULL REFERENCES delta_jobs(id),
  attempt INTEGER NOT NULL,
  workflow_commit TEXT NOT NULL,
  workflow_ref TEXT NOT NULL,
  run_id TEXT,
  status TEXT NOT NULL,
  error_code TEXT,
  created_at INTEGER NOT NULL,
  updated_at INTEGER NOT NULL,
  PRIMARY KEY(job_id,attempt)
);
CREATE INDEX delta_attempts_created ON delta_job_attempts(created_at);
CREATE TRIGGER delta_attempt_budget BEFORE INSERT ON delta_job_attempts
WHEN NOT EXISTS(SELECT 1 FROM delta_job_attempts WHERE job_id=NEW.job_id AND attempt=NEW.attempt)
  AND (SELECT COUNT(*) FROM delta_job_attempts WHERE created_at>=NEW.created_at-(NEW.created_at%86400))>=20
BEGIN SELECT RAISE(ABORT,'delta attempt daily budget exhausted'); END;
CREATE TRIGGER delta_attempt_insert AFTER INSERT ON delta_jobs
BEGIN INSERT INTO delta_job_attempts VALUES
  (NEW.id,NEW.attempt,NEW.workflow_commit,NEW.workflow_ref,NEW.run_id,NEW.status,NEW.error_code,NEW.created_at,NEW.updated_at); END;
CREATE TRIGGER delta_attempt_update AFTER UPDATE OF status,attempt,run_id ON delta_jobs
BEGIN
  INSERT INTO delta_job_attempts VALUES
    (NEW.id,NEW.attempt,NEW.workflow_commit,NEW.workflow_ref,NEW.run_id,NEW.status,NEW.error_code,NEW.updated_at,NEW.updated_at)
  ON CONFLICT(job_id,attempt) DO UPDATE SET run_id=excluded.run_id,status=excluded.status,
    error_code=excluded.error_code,updated_at=excluded.updated_at;
END;

CREATE TABLE delta_job_events (
  id TEXT PRIMARY KEY,
  job_id TEXT NOT NULL REFERENCES delta_jobs(id),
  action TEXT NOT NULL,
  actor TEXT NOT NULL,
  reason TEXT NOT NULL,
  revision INTEGER NOT NULL,
  created_at INTEGER NOT NULL
);
