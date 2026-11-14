CREATE TABLE admin_delta_run_status (
  job_id TEXT NOT NULL REFERENCES delta_jobs(id) ON DELETE CASCADE,
  attempt INTEGER NOT NULL,
  workflow_commit TEXT NOT NULL,
  checked_at INTEGER NOT NULL DEFAULT 0,
  lease_until INTEGER NOT NULL DEFAULT 0,
  lease_token TEXT,
  result_json TEXT,
  PRIMARY KEY (job_id, attempt)
);
