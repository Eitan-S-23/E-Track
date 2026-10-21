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
SELECT * FROM "TABLE_NAME" ORDER BY rowid LIMIT 8 OFFSET N
SELECT * FROM "TABLE_NAME" ORDER BY rowid LIMIT 500 OFFSET N
```

Schema table names (excluding SQLite and `_cf_` internals) determine the exact
table set. Counts must be integers from 0 to 20000. Each raw page must have
LIMIT 8 or 500, OFFSET equal to the preceding accumulated row count, and exactly
min(LIMIT, remaining count) rows. Mixed widths preserve original row order;
the final accumulated count must match. Zero-row tables have no row pages. Every raw
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

## V2 Before-Snapshot Recovery

This section describes the sealed V2 attempt. The current runner uses the V4
successor below; it does not rewrite V1/V2 sources, matrices or originals.

V1 retained a 60-second truncated response to a LIMIT 500 query: 65
channel_history rows would have been 9631314 bytes. V2 does not repeat that
large request or extend the 60-second/16-MiB transport bounds. All new row
queries, including every after-snapshot page, use LIMIT 8 and distinct
`ROLE-TABLE-rows8-OFFSET` labels.

The one explicit recovery entry is:

```text
node Tools/acceptance/p44/capture.cjs before inputs/predecessor-before.json
```

The frozen P4-4-v2 contract must hash-bind external input `predecessor-before`.
The manifest schema is `p44-predecessor-before-v1`; `source_evidence_root` is
`inputs/predecessor-before`. `source_commit` and `source_bundle_commit` pin
the original C1/B1 objects. `predecessor_contract_id` and
`predecessor_contract_sha256` bind the original frozen contract;
`predecessor_contract` and `predecessor_final_matrix` are File references
relative to that root. `files` contains the unchanged original before captures,
formal-before receipts/log, and failure-report references, using original v1
evidence-relative paths. The original matrix's EVIDENCE_GAP/NOT_OBSERVED is not
rewritten as a FAIL or a successful REUSED criterion.

Only exact same-label D1 SELECT and R2 listing records with completed=true,
expected status, hash-verified reservation/request/body and identical request
bytes may be consumed without network access. Original response bytes and
timestamps stay intact; returned File paths are relocated beneath the fixture
root with explicit predecessor provenance. A completed=false response remains
failed even if its partial body parses. Binding mismatches fail closed rather
than becoming cache misses. Configuration/GitHub reads and the protected-pair
identity check remain fresh. This recovery state exists only during `before`;
it cannot restore a dispatch, configuration mutation, registration or approval.

For each table, the collector first checks the old `ROLE-TABLE-OFFSET` LIMIT
500 record. A valid complete page advances by its actual row count. A failed
or absent old page instead results in one new LIMIT 8 query under its distinct
rows8 label; it never sends a new LIMIT 500 request. Subsequent offsets follow
the actual cumulative rows. Old failures are preserved, new failures are not
automatically retried, and after-state is entirely new observation.

V2 configuration accepts only the complete hash-bound approved C1
descriptor/hash pair or the complete new C2 pair. A C2 pair is a zero-PATCH
no-op; mixed C1/C2 values or the old P4-1 pair fail before any PATCH. The
existing P4-4 branch rule is required; configuration only updates the
descriptor/hash variables and never recreates that branch rule. Historical
contract/matrix digests are validated as 64 hexadecimal characters before
case-insensitive comparison; their original uppercase bytes remain unchanged.

## V3 Strict Gzip And Two-Round Recovery

The following V3 behavior and failure history remain preserved. V4 retains
strict gzip handling and adds only the bounded request-boundary policy below.

V2 retained four complete eight-row channel-history pages and an incomplete
HTTP 200 at offset 32. That page declared 4746278 wire bytes; its retained
1441765-byte prefix did not even contain one complete row. LIMIT 1 is therefore
not a justified remedy. V3 keeps LIMIT 8 and the same 60-second deadline and
separate 16-MiB wire/decoded bounds. No new SQL, retry controller or wider
permission is introduced.

Only fixed D1 POST reads send `Accept-Encoding: gzip`. Installed Undici
`request` retains the original encoded body. Standard Node `pipeline` and
`createGunzip` use the same absolute AbortSignal as the HTTP request, with
default strict trailer/CRC validation. Unsupported or compound content codings,
truncation, CRC/size errors, wire-length mismatches and either size overflow
fail closed. An identity response remains subject to the existing bounds; it
does not trigger a retry. S3 object readbacks are never HTTP-decoded by this
adapter, including objects carrying Content-Encoding metadata.

Successful gzip D1 records use these two distinct File references:

```text
body: LABEL.body                 original HTTP content-coded wire bytes
decoded_body: LABEL.decoded.body derived decoded representation
response_headers:               original wire headers, including Content-Length
request_headers:                {"accept-encoding":"gzip"}
```

Each representation has its own length and SHA-256. Content-Length describes
the wire body, never the decoded sidecar. Both the wire and decoded bytes are
checked for known sensitive values before either public file is written.
The capture-side staging admission rereads both references, strictly decodes
the wire and compares the sidecar; it does not parse `body` as plain JSON.
The offline `decode_d1_wire(wire, headers)` oracle uses a standard in-memory
GzipFile bounded read, not unbounded `gzip.decompress` or a `flush(length)`
allocation assumption. `Context.response` recomputes and compares gzip D1
sidecars before any D1/state interpretation. Non-D1 responses keep their raw
semantics and cannot substitute a decoded sidecar.

An encoded failure is never written as a public partial body, even when its
decoded prefix happens to be valid JSON. Its original wire prefix is retained
exclusively beneath the already-approved, user-only-ACL directory:

```text
.cache/p44/private/capture-failures/P4-4-v3/LABEL.wire.body
```

The public incomplete envelope contains only safe headers, fixed error code,
hash/length and `private_wire` location metadata. That location is relative to
the worktree, not a public bundle File input. It is not read or exported by
offline acceptance. Private destinations are checked before the request and
exclusive-created after the failure; tests inject an in-memory sink so they
never populate formal private capture names.

V3's predecessor manifest still uses `p44-predecessor-before-v1` and
`source_evidence_root: inputs/predecessor-before`. Its direct source is
C2 `70193ce7fb7cc4e426029d07cf7b50c1fcbfef1c`, bundle
B2 `84268ac2ad34727b76250ff944211b7efba1cfb3`, and the actual P4-4-v2 final
matrix. Its required `inherited_predecessor` File points to
`inputs/predecessor-before.json` relative to that source root: the unchanged
V2-era manifest of C1/B1 originals. The associated `inputs/predecessor-before/`
subtree is copied byte-for-byte. The loader admits exactly these two pinned
generations, verifies both frozen external anchors and all File references,
and preserves both failed responses. It cannot skip V2, recurse further or
turn a failed newer observation into an older successful one.

The before collector consumes 35 complete originals: V1's 31 and V2's four
new pages. It resumes the first missing logical page at offset 32 using the
changed gzip transport; no successful page, upload or rehearsal is replayed.
After-state remains new observation under its existing plan. The real B2
`bundle.predecessor_plan()` integration test checks 35 complete plus two
incomplete observations, original hashes/timestamps and zero network requests.

Configuration now accepts only the intact approved C2 descriptor/hash pair
or the intact C3 target pair. C2-to-C3 changes only those two variables; C3 is
a zero-PATCH no-op. Mixed pairs, superseded C1/P4-1 pairs and missing existing
branch rules fail before mutations. Gates, reviewer identity, business routes
and production/device restrictions remain unchanged.

## V4 One Pre-Response Retry

Round `P44-20261020-04` uses the actual V3 parent. Its source is C3
`ba952497948a03c40cbd8baebbfc9228621fb44b`, with bundle B3
`20febda2ac2e05e5f4b761a9f365091b177516b6`. The old 2026-10-19 filenames,
dates, contracts, matrices, 47 complete observations and three failures are
not renamed or rewritten. Reviewer runs A/B remain unspent, not reset.

V3 completed another 12 gzip D1 reads, then its patches read failed with
ECONNRESET in 7.087 seconds before a final HTTP response. Installed Undici
RetryAgent was evaluated but not adopted: its default retry count, status
policy and partial Range continuation would require unnecessary interception.
The existing `request` Promise already provides the smaller boundary. Once
final headers have fulfilled that Promise, later errors belong to its body
Readable rather than rejecting the original request.

V4 therefore uses two explicit request call sites, not a loop/controller.
Only an already-allowlisted capture GET without a request body, or a fixed D1
POST whose sole own body field is an approved SELECT `sql`, may make one extra
attempt after ECONNRESET. The same immutable request identity is used. Native
`onInfo` records informational responses; any 1xx prevents that extra attempt.
PATCH, dispatch, other business POSTs, other error codes, HTTP 401/403/5xx,
and the direct private verification route remain one-attempt operations.

One AbortSignal covers both requests, the cancellable 500ms backoff and the
existing strict body pipeline. The original 60 seconds and separate 16-MiB
wire/decoded bounds do not increase. A single monotonic absolute deadline is
also checked after synchronous audit I/O and immediately before the second
request, so a pending timeout callback cannot permit a late retry. Body,
decompression, CRC, size and interrupted-stream failures are outside the
request retry catch and never enter this policy.

The existing reservation still precedes the logical capture. The additional
exclusive-created audit originals are:

```text
LABEL-request-failure-1.json
LABEL-retry-2-reservation.json
LABEL-request-failure-2.json   only if the second request call actually fails
```

Failure records bind method, redacted path, original request File reference,
attempt number, start/end, fixed error code, informational-response facts and
the absence of a final response/body. Only the first informational status/time
and a count are retained, never response/authentication headers or exception
text. The first failure must be stored before the backoff/retry. The second
reservation binds that first failure and precedes the actual second call.
Audit failure, cancellation or deadline exhaustion prevents further calls.
An unspent reservation is not proof that a second call happened.

The final successful or failed envelope adds `request_attempts`,
`request_failures: File[]` and, when created, `retry_reservation: File`.
Success does not turn its preceding failure record into PASS. Existing file
reservations reject another invocation of the same label, rather than granting
another retry allowance. This policy grants no additional business action,
does not erase previous consumption, and adds no formal command IDs.

The V4 predecessor entry stays `inputs/predecessor-before.json`, but only its
new `source_evidence_root` is shortened to `p`. The three fixed roots are
`p`, `inputs/predecessor-before`, `inputs/predecessor-before`, with identities
C3/B3, C2/B2 and C1/B1 respectively. Both inherited manifests retain their
original bytes and paths. The three-layer maximum path is 239 characters in
this worktree instead of 263 with another long outer prefix; no external
short directory, alias or generic path migration is needed.

All 47 complete records are reused without requests, including C3's 12 gzip
records. Every inherited wire, request and decoded File reference is verified
and relocated under its actual layer. The existing strict `d1Document` oracle
recomputes gzip and compares its sidecar before returning decoded bytes/JSON;
an inherited sidecar is not independently trusted. The three failed originals
stay failed. Only missing observations, beginning with the patches page, are
new reads. A/B approval and production/device restrictions are unchanged.

V4 configuration accepts only the intact approved C3 pair or intact C4 pair;
older/mixed pairs fail before mutation. The encoded-failure private namespace
is `.cache/p44/private/capture-failures/P4-4-v4/`, subject to root's formal
preflight. Development tests use an in-memory private sink and do not create it.

The affected host batch uses the real installed Undici MockAgent with network
connections disabled, request/body/error boundary cases, audit/deadline
negatives, and actual B3-plan-to-loader checks (47 complete, three incomplete,
12 gzip, zero requests). The Windows path test calls the real Node guard and
Python File-reference reader on an existing, explicitly supplied 239-character
fixture. It can otherwise create one bounded equivalent beneath
`.cache/p44/v4-paths/`. It never creates a formal evidence/private fixture.

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
python -I -S -B tests/ota/test_p44_acceptance_tools.py --output-dir ABSOLUTE_ROOT/.cache/p44-runner-tests-20261020/UNUSED_LABEL --windows-fixture-file EXISTING_PROJECT_LOCAL_LONGEST_FIXTURE
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

`bundle.py` prepares and freezes the P4-4-v4 contract (execution schema v3) and assesses completed evidence.
Its initial matrix stays NOT_RUN; its final matrix is a different file.
Run `assess` and the final physical validator with logs outside the bundle's
`evidence/` directory, not through formal `run.cjs`, so an active log cannot
invalidate its own just-recorded digest. Run the final validator against
`final-evidence-matrix.json`. Preserve all original failures and use the project
rerun rules if any frozen input or formal command fails.
