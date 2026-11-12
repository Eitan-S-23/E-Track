# Version Inventory And Operator Delta Jobs

## Scope And Trigger

Use the original unified Admin to inspect recent App/MCU version observations
and select old original packages when generating supplemental deltas. There is
no second management website, separate collector App, continuous phone polling,
or guarantee that the server can wake offline/backgrounded phones.

The existing Android App supports this from `1.0.75+101`. Older installed Apps
do not acquire reporting by a backend deployment. The profile settings provide
an opt-out. Reports contain a random installation identity and installation-salted
MCU observations, not raw Bluetooth addresses, location or ride data. Reinstalls
can be separate installations. One physical MCU used by two phones can be counted
twice; `uniqueDeviceCount` is always null.

## Signatures

| Entry | Purpose |
| --- | --- |
| `GET /api/public/version-inventory/control` | Low-frequency reporting control |
| `POST /api/public/version-inventory` | Installation report |
| `GET /api/admin/version-inventory` | Aggregated 7/30/90-day observations |
| `POST /api/admin/version-inventory/refresh` | Request fresh reports on future eligible foreground checks |
| `GET /api/admin/delta/candidates?kind=android\|firmware&targetId=...` | Original bases and retained jobs |
| `POST /api/admin/delta/jobs` | Select one to five bases |
| `POST /api/admin/delta/jobs/{id}/{enable\|disable\|retry\|reconcile}` | Explicit job/asset action |
| `/api/ci/delta/jobs/{id}/{spec\|base\|target\|claim\|asset\|complete\|fail}` | Bound Actions execution only |

The original Access facade owns administrator authentication, same-origin and
CSRF checks. Viewers can read; publishers can request reports and generate,
retry or reconcile jobs; only owners can enable/disable generated assets.

## Contracts

Installation reports use `Authorization: Bearer <64 lowercase hex characters>`.
The service stores its SHA-256 digest, not that raw bearer. Body example:

```json
{
  "appId": "trace",
  "platform": "android",
  "sequence": 1,
  "versionCode": 101,
  "versionName": "1.0.75",
  "imageSha256": "<64 lowercase hex APK SHA-256>",
  "devices": []
}
```

There are at most four device entries. Each has `deviceKey`,
`identityScope: "installation"`, `deviceModel: "e-track-at32f435"`,
`versionCode`, `imageSha256`, `hardwareRevision`, `layoutId`, a UUIDv4
`observationId` and bounded `ageSeconds`. Repeating a cached observation retains
its original server observation timestamp; an App refresh must not make an
unseen MCU appear active today.

Normal reports are daily; foreground control checks are at least four hours
apart. Changes are debounced and failures back off for one hour. Reporting does
not start BLE scans/connections and yields to active device OTA and App updates.
The initial server budget is 1000 accepted reports/day and at most eight per
installation/day. Retention is 90 days with bounded hourly cleanup. These are
application limits, not a promise about other usage in the shared free account.

A refresh body is `{ "requestId": "<UUIDv4>" }`. Same-key repeats are idempotent;
new requests are at least 15 minutes apart. It requests later reports, not
immediate push delivery or an exact census of every installation.

```json
{
  "kind": "firmware",
  "targetReleaseId": "<existing target release>",
  "baseReleaseIds": ["<existing older release>"],
  "reason": "Generate for selected supported installations"
}
```

Job actions require `expectedRevision` and a nonblank `reason`. At most 20 new
attempts/day, including explicit retries, are admitted transactionally. Existing
patches and immutable `(kind, target, base image hash)` jobs are reused.

Actions download the original files and verify their exact hashes. APK jobs
also require identical package/signing identities and source versionCode >= 41.
MCU jobs reuse the existing F435 ETU packer and require matching hardware/layout
1. They do not rebuild or finalize the original firmware again. Reconstruction
must equal the exact target bytes before completion. New assets start disabled.
Enabling requires an owner, a valid current target, the verified R2 object and a
patch smaller than the full package. Disabling retains the immutable job/output.
Original channel pointers and original sealed manifests are not rewritten.

| Binding | Consumer |
| --- | --- |
| `VERSION_INVENTORY_ENABLED` | Worker, Public Pages, Admin Pages |
| `DELTA_GITHUB_TOKEN` | Admin Pages secret; existing authorized GitHub credential with Actions dispatch/read access |
| `DELTA_WORKFLOW_REF`, `DELTA_WORKFLOW_COMMIT` | Admin; exact MCU execution ref and full commit in Eitan-S-23/E-Track |
| `DELTA_APP_WORKFLOW_REF`, `DELTA_APP_WORKFLOW_COMMIT` | Admin; exact App execution ref and full commit in Eitan-S-23/Trace |
| `DELTA_APP_PUBLIC_KEY_BASE64` | Admin admission and Worker completion verifier |
| `DELTA_ASSETS_ENABLED` | Worker, Public Pages, Admin Pages; false until qualified |

The dispatcher does not need repository administration or contents write. A
repository-limited credential is recommended, not a requirement to create a new
token when an existing credential is usable and authorized. On 2026-11-12 the
owner explicitly authorized reuse of the existing GitHub CLI OAuth credential
in the original Admin's production configuration; preview is unchanged and
that credential is not copied to Public Pages or the Worker. Its broader
account scopes are not a minimum permission requirement. App signing stays in the existing Actions secret;
firmware keys stay behind the existing `firmware-rehearsal` environment. The
retrieved client verification key is public. Ref registration and protected
environment branch eligibility must be verified without removing reviewer gates.

Original App deltas run in `Eitan-S-23/Trace`, where the original registration
bearer and payload-signing private key already live. E-Track's isolated test
secrets are not interchangeable with them. The tracked
`scripts/admin-app-delta-workflow.template.yml` is installed as the original
repository's `admin-delta-build.yml` with `__DELTA_SOURCE_COMMIT__` replaced by
one verified full E-Track source SHA. It checks out only that pinned generator;
it does not rebuild Apps, copy secrets between repositories, or publish channels.
Its push job exports only the existing public key. Verify that key against an
original published manifest before configuring either verifier.

New App attempts store `Eitan-S-23/Trace@<ref>` in the existing immutable-attempt
`workflow_ref` field. Unqualified historical refs retain their original E-Track
meaning. Dispatch, reconciliation and run links use the repository of that
specific attempt, not the current environment binding. Repository changes are
therefore possible only during an explicit retry of a known failed job; old
attempts and ready MCU artifacts are not rewritten. No schema migration is needed.
The spec returns `workflowRepository`; JSON callbacks and binary transfer headers
(`X-Delta-Repository`) must match it. Missing repository fields are accepted only
for legacy E-Track callbacks. The generator rejects another repository or a
firmware job outside E-Track. Original App key mismatch fails admission before
dispatch; early CI admission/claim failures retain a receipt without blind retry.

## Validation And Errors

| Case | Result |
| --- | --- |
| Missing reporting bearer | 401; no installation inserted |
| Reused sequence with changed state | 409; previous state preserved |
| Old sequence or identical early report | Idempotent/non-accepted response |
| Reporting or attempt budget exhausted | 429; no extra accepted attempt |
| Missing dispatcher/key configuration | Explicit unavailable response; no job falsely shown ready |
| Unauthorized role, origin or CSRF | Rejected before mutation |
| Stale job revision | CAS conflict; reread before another explicit action |
| Lost/5xx dispatch response | `dispatch_unknown`; never automatically redispatch |
| Wrong attempt, source commit or run identity | Reject callback |
| Upload size/hash, reconstruction or App signature mismatch | Reject completion |
| Verified but disabled generated delta | Original full fallback remains in effect |

Reconciliation reads GitHub and requires a unique run matching the job/attempt,
workflow commit and display title. A retry is a new explicitly authorized
attempt; GitHub's rerun button is not a substitute.

Both edge-side GitHub calls use `redirect: "manual"` and reject unexpected
statuses without forwarding credentials. Workers does not support the standard
Fetch `error` redirect mode: it rejects that option before making a network
request. Node-based mocks must not be treated as evidence of edge compatibility.
Regression tests construct the actual request, check the redirect policy, and
cover 302/307 dispatch responses and redirected reconciliation. Other transport
errors remain uncertain outcomes and must not automatically redispatch.

## Good, Base And Bad Cases

- Good: select a positively observed, eligible older version; build and verify
  its smaller delta; then explicitly enable that asset without changing channels.
- Base: an unreported version remains unknown. The operator can select it if
  eligible; automatic recommendations do not assume that unknown means zero.
- Bad: an older decoder, wrong original image, different APK certificate or
  mismatched MCU layout must not receive a generated patch.

## Tests And Activation

`worker/test/version-inventory.test.ts` covers sequence, nonces, aggregation,
limits and expiry. `worker/test/delta-jobs.test.ts` covers dispatch uncertainty,
binding, streaming, signed completion, CAS and original preservation.
`worker/test/firmware-admin.test.ts` tests the actual facade's role, origin,
CSRF, refresh and unavailable-dispatch paths.

`admin/test/version-operations.spec.ts` covers distribution controls, explicit
base selection, disabled states, pending jobs and fixed modal close controls.
`test/services/version_inventory_service_test.dart` covers App scheduling and
foreground/OTA guards. The full recording/parser integration test retains its
1 MiB input and invalid V1/window/batch cases with an explicit three-minute test
budget; production timing/recorder limits do not change.

Local and native-runtime tests do not prove a live GitHub/R2 delta round trip.
Before setting `DELTA_ASSETS_ENABLED=true`, configure the project credential and
bound workflow, execute a real disabled job for each format (APK and MCU), preserve
their originals/runs/receipts, and verify the resulting objects and registered read models. Do not publish a
channel, install an APK or perform an OTA just to check this server-side path.

The original-App workflow does not depend on GitHub artifact storage. Its public
verification key and a fixed list of bounded, non-secret JSON receipts are retained
in native run logs. The generator must still upload the exact delta to R2 and
complete the backend's hash, signature and immutable-input checks. The receipt
step verifies that the completed, disabled asset matches the local patch. It does
not print environment variables, original APKs or private keys, and does not
suppress a generation or receipt failure. Retrieve the raw logs and exact R2 object
for qualification; retain earlier artifact-quota failures rather than rerunning
an already-completed delta simply to produce another archive.

Current actual observations and source/run/deployment identities are in
`docs/ota-exec-notes/VERSION-INVENTORY-DELTA-2026-11-11.md` at the repository root.

## Wrong Versus Correct

Wrong: treat a successful dispatch as a ready patch, or an empty inventory as
proof that nobody uses a version. Correct: wait for verified completion and
label missing client observations as unknown. Generated assets are disabled
until an owner acts; generating a delta never silently publishes its target.
