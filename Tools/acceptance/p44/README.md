# P4-4 Offline Evidence Evaluator

`inspect.py` is an offline adapter, not a platform controller or release runner. It
does not authenticate, dispatch, approve/reject, upload, deploy or operate a
device. Root captures the original platform responses using an independently
reviewed route. Passing this tool is not by itself P4-4 acceptance or permission
to unlock the production gate.

The existing `docs/acceptance-contracts/P4-1-v2/tools/inspect.py` rehearsal byte
evaluator remains unchanged and is called with absolute artifact/target paths.
Only its `rehearsal` function is reused. Its historical campaign, state collector
and proxy-approval paths are not imported or executed. Additional checks bind
the new protocol and original GitHub run, review and snapshot objects.

## Invocation And Boundaries

Run from the exact task worktree root. The interpreter must not use `-O`.

```text
python -I -S -B Tools/acceptance/p44/inspect.py rehearsal --repo-root ABSOLUTE_ROOT --input PATH/manifest.json --output PATH/rehearsal-result.json
python -I -S -B Tools/acceptance/p44/inspect.py approvals --repo-root ABSOLUTE_ROOT --input PATH/manifest.json --output PATH/approvals-result.json
python -I -S -B Tools/acceptance/p44/inspect.py states --repo-root ABSOLUTE_ROOT --input PATH/manifest.json --output PATH/states-result.json
```

CLI paths can be absolute or relative to `--repo-root`; file references inside
JSON are absolute or relative to the manifest's directory. All resolved inputs
and outputs must be inside that worktree. Every existing parent, including the
worktree's ancestors, is checked for symlinks, junctions and other reparse
points. Outputs are exclusive-created, never overwritten. On a validation
failure the output contains a fixed error code, never an upstream body,
comment, request or exception text. A filesystem/preflight failure creates no
output. No dependency installation, default system temporary directory, or
ignored-cache helper is used by the evaluator.

## Common Shapes

`File` is a reference to original bytes, not a hand-written PASS summary:

```json
{"path":"run-a/final-run.json","size_bytes":12345,"sha256":"64 lowercase hex digits"}
```

`HTTP` contains capture metadata plus a `File` reference to the byte-exact
response. Header names are case-insensitive; values are original strings. Save
all received response headers, particularly `Link`. Do not save authorization
headers, cookies, signed download URLs or credential-bearing request bodies.

```json
{
  "method":"GET",
  "path":"/repos/Eitan-S-23/E-Track/actions/runs/123/attempts/1",
  "status":200,
  "started":"2026-10-19T09:00:00.000Z",
  "ended":"2026-10-19T09:00:01.000Z",
  "response_headers":{"content-type":"application/json"},
  "body":{"path":"run-a/final-run.json","size_bytes":12345,"sha256":"..."}
}
```

POST captures additionally require `request: File` binding the original JSON
request body. Dispatch response bodies are normally zero bytes and still need
their `File` identity. All other accepted HTTP responses are HTTP 200. A
definitive or ambiguous failed operation must remain in the root evidence;
this evaluator neither retries it nor rewrites it as successful.
New captures mark transport completion with the boolean `completed`. A
`completed: false` envelope is rejected even if HTTP status is 200 and the
retained partial body already parses as valid JSON. Its `error_code`, partial
body and headers remain original failure evidence. An omitted completion field
is accepted for compatibility with previously captured complete originals;
when present it must be exactly `true`, not a truthy string or number.

The top-level manifest has `schema: "p44-observations-v1"` and `target: File`.
The target is the existing P4-1 target shape: `repository`, `branch`,
`commitSha`, `versionName`, `descriptor`, `descriptorSha256`, `keySha256`,
`minAppVersionCode`, `minProtocolVersion`. Repository is Eitan-S-23/E-Track;
branch is an explicitly reviewed `dev/p4-4/` branch. Descriptor hash uses
canonical sorted JSON without a trailing LF, matching the product contract.
It must bind this exact target commit and version. The tool does not select
or invent a candidate version. Root must freeze this target and all runner
paths before external execution.

## Rehearsal And Approval Inputs

Both modes consume the following manifest fields; `rehearsal` uses run B,
artifact and artifact listing, while `approvals` uses both runs and attestation.

```text
run_a / run_b:
  run_id: positive integer
  dispatch: HTTP POST /repos/Eitan-S-23/E-Track/actions/workflows/firmware-build.yml/dispatches (204)
  waiting_run: HTTP GET /repos/Eitan-S-23/E-Track/actions/runs/ID
  pending_deployments: HTTP GET /repos/Eitan-S-23/E-Track/actions/runs/ID/pending_deployments
  final_run: HTTP GET /repos/Eitan-S-23/E-Track/actions/runs/ID/attempts/1
  reviews: HTTP GET /repos/Eitan-S-23/E-Track/actions/runs/ID/approvals
  jobs_pages: HTTP[] GET /repos/Eitan-S-23/E-Track/actions/runs/ID/attempts/1/jobs?per_page=100&page=N
artifact: File (the successful run-B p41-rehearsal-ID-1 ZIP)
artifact_listing: HTTP[] GET /repos/Eitan-S-23/E-Track/actions/runs/ID/artifacts?per_page=100&page=N
reviewer_attestation: File
```

Run captures keep the complete original GitHub object, not a selected-step
projection. The run ID, attempt, head SHA, branch, event, workflow path,
repository, timestamps and final conclusion are independently compared.
Jobs must be complete according to `total_count` and the original `Link`
chain, and each job must belong to that same run/attempt/source. The artifact
listing binds its name, digest, size and workflow-run identity to run B.
The original run creation must be within the dispatch interval, allowing two
seconds for timestamp rounding/clock skew and up to 120 seconds after its
receipt. The terminal artifact listing must be captured after run completion.

Both dispatch request bodies must be identical and explicit:

```json
{
  "ref":"dev/p4-4/config-integration-20261018",
  "inputs":{
    "publish":"false",
    "rehearsal":"true",
    "check_bindings":"false",
    "approved_rehearsal_run_id":"",
    "version_name":"REVIEWED_VERSION",
    "release_notes":"REVIEWED_NOTES"
  }
}
```

JSON booleans are accepted for the three boolean inputs, but the two requests
must still be identical including types. No extra dispatch inputs are accepted.
Run A must wait for the configured reviewer, then record a real `rejected`
event and complete with `failure`, without any rehearsal/production step
running. Cancellation is not rejection. Run B must be a distinct new run at
attempt 1, created after A's terminal update, with a real `approved` event,
the full successful workflow, and the required release/cleanup/archive steps.
The reviewer is the existing User `Eitan-S-23` (ID 204050265), on the same
pending environment ID/name. Opposite or extra review events are rejected.

The additional attestation is a separate original root/owner record:

```json
{
  "schema":"p44-reviewer-attestation-v1",
  "reviewer":"Eitan-S-23",
  "reviewer_id":204050265,
  "actions":[
    {"run_id":123,"run_attempt":1,"state":"rejected","basis":"owner_response","evidence":{"path":"owner-reject-receipt.txt","size_bytes":100,"sha256":"..."}},
    {"run_id":124,"run_attempt":1,"state":"approved","basis":"root_witness","evidence":{"path":"root-approve-observation.txt","size_bytes":100,"sha256":"..."}}
  ]
}
```

Its evidence must be nonempty and hash-bound. Root, not this parser, judges
the truth of an owner response or actual witnessed dashboard action. GitHub's
account identity alone cannot distinguish a human click from a caller using
the same account. No comment string can substitute for an actual API review
event; historical P4-1 delegated approval does not satisfy this obligation.

Rehearsal additionally requires `s3-worker-preflight-v1`, staging preflight
schema/request identity and metadata digest, exact preflight/upload/register/
replay event order, canonical ready metadata, three asset identities, one
non-idempotent ready registration and its same-release idempotent replay.
The reused byte evaluator verifies the full/patch/recovery and keyed-GCC bytes.

## State Snapshot Inputs

`states` consumes run B, artifact/listing, `snapshots: {before, after}` and
`readbacks`. Each snapshot is:

```text
databases:
  production / protected / staging:
    schema: HTTP POST /accounts/[ACCOUNT]/d1/database/EXACT_ID/query
    tables:
      TABLE_NAME:
        count: HTTP POST (same database route)
        pages: HTTP[] POST (same database route)
buckets:
  production / protected / staging: HTTP[] GET /EXACT_BUCKET/?list-type=2&max-keys=1000[&continuation-token=...]
github:
  releases: HTTP[] GET /repos/Eitan-S-23/E-Track/releases?per_page=100&page=N
  assets:
    RELEASE_ID: HTTP[] GET /repos/Eitan-S-23/E-Track/releases/RELEASE_ID/assets?per_page=100&page=N
readbacks (top-level):
  EXACT_R2_KEY: HTTP GET /e-track-firmware-p41-test-releases/ENCODED_R2_KEY
```

`[ACCOUNT]` is the literal redaction marker in the captured D1 route. The
precise resource mapping is fixed, not caller-selectable:

| Role | Database ID | R2 bucket |
| --- | --- | --- |
| production | 1cd5db26-6bbd-4595-abef-72ff51ecdaf3 | e-track-firmware-production-releases |
| protected | 0133ad9e-d4a2-4fef-a659-4f2bf3d3a645 | trace-update-staging-releases |
| staging | 2617e1e1-956f-42ce-a465-da56d84abf06 | e-track-firmware-p41-test-releases |

D1 request JSON must contain only `sql`, using these exact SELECT shapes:

```text
SELECT name,type,sql FROM sqlite_master ORDER BY type,name
SELECT COUNT(*) AS count FROM "TABLE_NAME"
SELECT * FROM "TABLE_NAME" ORDER BY rowid LIMIT 500 OFFSET N
```

Schema table names (excluding SQLite and `_cf_` internals) determine the exact
table set. Counts must be integers from 0 to 20000, and full 500-row pages
must cover the observed count. Zero-row tables have no row pages. Every raw
D1 result must report success, zero rows written and `changed_db: false`.
Counts, contents, schema and channel rows are compared, not summary hashes
selected by a collector. These multi-request snapshots are not a transaction
or a claim of continuous observation between captures.

R2 pagination validates bucket name, empty prefix/no delimiter, key count,
continuation request/response linkage, unique keys and an explicit terminal
`IsTruncated=false`; a bare `complete: true` is never accepted. GitHub lists
similarly follow the original Link chain and reject missing or repeated pages.
Each release requires a separate complete asset listing, including empty ones.

Production and protected D1/R2 and all GitHub Release/asset objects must be
unchanged. Staging may add only this candidate's ready release, its three
asset rows, one registration audit row and three R2 keys. Existing rows,
schema and all channel rows must remain unchanged. Three independently
captured complete R2 GET bodies must match the candidate bytes/digests.
Every before-snapshot capture must finish before run B is created; every
after-snapshot capture and independent asset GET must begin after run B's
terminal update. Copies of pre-run snapshots cannot stand in for after-state.

## Frozen Runner Paths

The root acceptance contract must declare the actual transitive paths:

```text
Tools/acceptance/p44/inspect.py
docs/acceptance-contracts/P4-1-v2/tools/inspect.py
Tools/jlink/prepare-bootstrap-app.py
```

The rehearsal byte evaluator also consumes the original bootstrap directory
and `Libraries/OTA/ota_keys.c` from the bound target commit. Root must retain
the corresponding source/input dependencies and original bootstrap evidence;
this adapter does not waive them. `README.md` is a schema guide, not a new
acceptance criterion. Offline tests are development checks only:

```text
python -I -S -B tests/ota/test_p44_acceptance_tools.py --output-dir ABSOLUTE_ROOT/.cache/p44-runner-tests-20261019/UNUSED_LABEL
```

## Root Capture And Sealing

`capture.cjs` is the separate root-owned thin adapter for the fixed plan. It
uses installed Undici/OpenSSL and standard AWS SigV4, never a custom signing
algorithm. `run.cjs` contains controllable outputs and captures original stdout.
Commit these tools before `bundle.py prepare`, target binding, the exact
rehearsal branch/descriptor configuration, freeze and NOT_RUN precheck. The
`P44Capture` profile isolates raw collection from offline parser dependencies.

The first before snapshot requires the known 3.2.8 registration, no unresolved
legacy channel and no version collision with reviewed 3.2.9. Two new same-input
attempt-1 runs are planned: real reviewer rejection A, then real approval B.
Neither API identity nor a frozen contract is evidence of a human action.
All three gates stay false; production firmware publication and devices are
outside this plan. No unchanged Worker is deployed again.

Only uncertain or missing collection has a read-only recovery route. Preserve
the original intent and failed response; `recover-a/b LABEL` reconciles the
existing run, never dispatches another one. `finish-a/b-recovery LABEL` is only
for an absent final capture. If final data already exists, collect only missing
logs with `logs-a/b LABEL` or missing B artifact with `collect-b LABEL`.
Already-completed final/log/artifact captures are rejected before a new GET.
No recovery command grants another business operation or rewrites a success.

`bundle.py` prepares and freezes the v3 contract and assesses completed evidence.
Its initial matrix stays NOT_RUN; its final matrix is a different file.
Run `assess` and the final physical validator with logs outside the bundle's
`evidence/` directory, not through formal `run.cjs`, so an active log cannot
invalidate its own just-recorded digest. Run the final validator against
`final-evidence-matrix.json`. Preserve all original failures and use the project
rerun rules if any frozen input or formal command fails.
