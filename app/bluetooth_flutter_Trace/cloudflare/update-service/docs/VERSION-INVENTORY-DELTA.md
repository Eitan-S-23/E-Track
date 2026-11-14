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

## Task Progress And Notifications

Migration `0009_delta_notifications.sql` adds progress phases and an actor-scoped
notification/outbox model. It does not alter release files, channels, workflow
bindings, signatures or existing job identities. Old terminal jobs remain visible
in task history but are not backfilled as new alerts.

The existing CI callbacks report actual stages: claim means building and local
reconstruction checks; an accepted asset upload enters uploading; stored bytes
await verification/registration; only successful completion becomes ready. No
estimated percentage is returned. Dispatch uncertainty remains uncertainty and
requires reconciliation. A read, reload, gesture or notification never dispatches
another build, retries a failed job, enables an asset or changes a channel.

The Access-protected facade adds these same-origin, actor-bound routes:

- `GET /api/admin/delta/activity`: up to 100 own jobs (active first), the latest
  30 own terminal notifications, total unread count, public push key and active
  subscription IDs/expiry. It never exposes push endpoints or private keys.
- `POST /api/admin/delta/notifications/read`: `{ids:[1,2]}` for individually viewed
  results, or `{throughId}` for explicit Mark all read. The latter is monotonic
  and clamped to existing notifications for this actor, never future results.
- `POST /api/admin/delta/notifications/subscribe`: `{endpoint,applicationServerKey}`;
  explicit browser consent, supported HTTPS vendor endpoints, at most five active
  subscriptions per actor, 30-day expiry, no reassignment across accounts.
- `POST /api/admin/delta/notifications/unsubscribe`: `{id}`; actor-scoped removal.

All POST routes retain the existing Access/role, same-origin JSON and CSRF guards.
Job completion/failure and its notification/outbox insert are atomic SQLite
trigger operations. Completion sends a bounded background delivery; the distinct
five-minute Worker schedule retries only notifications, never firmware cleanup
or builds. Deliveries use a lease, at most five tries, no redirect following and
remove expired vendor subscriptions on 404/410. A push failure cannot turn a
successful delta into a failed delta or remove its unread result.

`ADMIN_PUSH_PUBLIC_KEY` is shared by the Admin and Worker. Only the Worker receives
the `ADMIN_PUSH_PRIVATE_JWK` secret; `ADMIN_PUSH_SUBJECT` is a contact HTTPS URL.
VAPID is ES256/P-256 (RFC 8292). The RFC 8030 push is payloadless: it wakes the
service worker, which reads protected task details with the browser Access session.
Expired sessions receive a generic alert with no version detail. No authenticated
page/API cache is installed. The worker uses a notification tag and durable local
receipts to suppress duplicate completion alerts; clicking opens Tasks, not an API
mutation. Browser/platform suspension and denied permission can prevent or delay
OS delivery. Durable in-app results and foreground reconnection are the fallback.

The toolbar task list does not depend on an open delta dialog. It polls while the
page is alive, refreshes on online/foreground return and preserves stale results
with an explicit error if reads fail. The server owns task state; page timers are
not the background-notification guarantee. Notification consent is requested only
from the Enable alerts button, never on load or as a prerequisite for generation.

### Read State And Click Navigation

Migration `0010_notification_read_state.sql` adds nullable `read_at` to each
actor-owned notification. A notification is unread only when above the existing
actor cursor AND `read_at IS NULL`. Old cursors and timestamps are preserved.
Per-result reads accept 1..30 distinct positive safe-integer IDs, reject mixed
`ids`/`throughId` or invalid input, update only matching actor-owned rows, and
return `{ok:true,readIds:[...]}`. Unknown/foreign IDs are not acknowledged and
cannot change another account. Repeating a read preserves its original timestamp.
Cursor responses return `{ok:true,throughId:<actual stored cursor>}`.

The UI sends only actually visible or clicked IDs. An old successful activity
response is discarded and reread if an intervening read acknowledgement changed
the local revision. Read failures never silently zero the badge. The badge is
unread count, not `unread || activeJobs`; running jobs keep a distinct icon state.

| Case | Expected behavior |
| --- | --- |
| Foreground visible result / explicit result click | Save that ID; acknowledge before clearing unread |
| Hidden page, inert/closed sheet, another notification page | No automatic read mutation |
| Network/server read failure | Retain unread/error; explicit refresh may recover |
| Late pre-ack activity response | Discard notification snapshot and reread |
| Explicit Mark all read followed by a new result | Newer result remains unread |
| Notification click while loading or confirming | Acknowledge queued intent; open when safe |
| Closed, unresponsive or non-Admin window | Open absolute original-origin `/?tasks=1` |

Regression oracles are in `admin/test/version-operations.spec.ts`,
`admin/test/delta-activity.spec.ts`, and `worker/test/admin-notifications.test.ts`.
Good: read one result, retain older unseen and future results. Base: explicit
Mark all read consumes the currently observed boundary. Bad: using the global
cursor on a single clicked result would silently mark unseen results read.

Android Chrome system push uses Google's push transport independently of the
Cloudflare webpage. Working Play Store downloads do not establish that transport's
connectivity. The operator reported registration AND delivery succeeding with VPN
on 2026-11-13; this is real user-reported evidence, not a local headless test.
Turning VPN off can affect later delivery too. The webpage cannot replace Chrome's
push provider or guarantee its reachability; in-page durable results still work.

## Reporting Receipt And Scheduler Update

Receipt support must reach both the Worker and the separately bundled public
Pages endpoint before a new client relies on duplicate confirmation. Both server
bundles were deployed on 2026-11-14; the client change has passed development CI
but has not been shipped in a new APK/EXE. The existing accepted-report response
remains compatible. Server deployment does not update an installed client.

### Signatures And Invariants

`reportInventory` adds `acknowledged: boolean`, `reportedAt: number | null`
(server Unix seconds), and `sequence: number` to its response. `accepted` keeps
its original meaning: a new snapshot was written. A matching duplicate can be
acknowledged without being accepted, but retains the stored receipt time and
stored refresh identity. A different stale snapshot cannot be acknowledged.
If a concurrent sequence wins the guarded transaction, reread the stored
installation before returning its receipt. No reporting limit, device identity,
retention policy or channel state changes.

`VersionInventoryService` consumes runtime activity streams and exposes
`status`, `lastReportedAt`, `nextAttemptAt` and a sanitized `failureCode`. These
do not expose tokens or raw BLE addresses. Idle/foreground events resume the
pending snapshot; an endpoint failure retains one-hour backoff. The service
owns and cancels all retry/control timers and activity subscriptions. An old
server receipt cannot cause a zero-delay polling loop if the phone clock is
ahead. Unchanged observations remain coalesced instead of raising report limits.

### Validation Matrix

| Case | Expected behavior |
| --- | --- |
| Upgrade busy, then idle | No hashing/reporting while busy; retry the pending identity after idle |
| Background cancellation, including a quick foreground return | Ignore the cancelled request outcome; no invented one-hour network penalty |
| Endpoint error | Preserve last successful receipt, show sanitized reason, schedule bounded retry |
| Explicit opt-out or service close | Cancel timers, request and listeners; no further report |
| Matching server duplicate | Keep original server receipt time; do not manufacture new freshness |
| Stale different sequence | Reconcile server sequence but retain failure, not a successful local report |
| Temporarily unavailable APK identity | Do not cache the invalid identity forever; reread after backoff |
| Fresh read of unchanged MCU | Retain daily coalescing and installation-scoped identity |

Good: a post-upgrade identity waits for idle, then becomes reported only after
the backend acknowledges its snapshot. Base: an unchanged daily snapshot sends
no extra report. Bad: treating every HTTP 200 as acceptance, or resetting the
retry clock on every UI event, hides stale state and can starve or flood reporting.

Tests live in `worker/test/version-inventory.test.ts` and
`test/services/version_inventory_service_test.dart` relative to the update-service
and Flutter package respectively. The Worker host suite and the dual-host Dart
development checks have passed. The earlier SDK/lock failure was resolved using
the documented supported SDK baseline; no APK/EXE or device result follows from
those checks. `worker/test/public-pages.test.ts` also tests duplicate receipts
through the public Pages router. See the continuation in
`docs/ota-exec-notes/VERSION-INVENTORY-DELTA-2026-11-11.md` at the repository root
for the exact source/run and remaining gate. Neither a host fixture nor a stale
previous device observation proves this new client scheduling fix on a phone.

## Registered Candidate Arrivals

### Scope And Signatures

`ADMIN-NOTIFY-BUILD-01` covers newly registered App/MCU candidates, not successful
compiles. `candidateArrival(env, input): D1PreparedStatement` is appended to the
existing App or firmware registration batch after object validation. The input
binds `appId`, `kind`, `releaseId`, `versionName`, `versionCode`, `commitSha`,
`runId`, and optional `deviceModel`. Only the configured `APP_ID` emits events.
No channel, publication or asset-enabling operation is added.

Migration `0011_candidate_notifications.sql` creates `admin_candidate_events`,
`admin_notifications` and `admin_notification_deliveries`. It copies existing
notification IDs, read timestamps and delivery leases, preserves read cursors
and the old sequence high-water mark, and moves the terminal-job trigger to the
shared stream. The legacy tables remain as evidence, but are no longer live.
Do not blindly roll back to a legacy consumer after new events have arrived.
Reconcile pending deliveries before the coordinated Worker/Pages rollout.

### Response And Audience Contract

`GET /api/admin/delta/activity` keeps its existing own-job and actor checks.
Notifications now include `type: "delta" | "candidate"`; candidate entries have
`kind`, `targetReleaseId`, `versionName`, `targetVersionCode`, `deviceModel`,
`createdAt`, and the existing actor-specific `id`/`unread` fields. Candidate
identity is unique by kind/release; actor delivery is unique by actor/event.
Registration replay and R2 backfill never produce another arrival.

Existing, unexpired subscriptions receive payloadless outbox wakeups. An
Access-authorized reader without push also materializes up to 100 unseen event
records per poll, with independent read state. The event log starts empty: old
releases are not backfilled. Subscriptions created after an event are not sent
retrospective pushes. Browser permission is still requested only by a click.

In-page alerts wait until the page is visible and busy/modal work has finished.
They do not replace drafts or auto-open a release. A selected candidate opens its
registered App/MCU details, not a delta-build form. Windows details are read-only
and do not operate the Android channels. Missing/removed targets show an error.
System notifications use the same protected activity fetch and existing task
navigation route; no package or account data is sent to the push vendor.

### Validation, Cases And Tests

| Input/outcome | Required result |
| --- | --- |
| Compiled but upload/validation fails | No event, no push, no publication |
| Registration batch rolls back | Event and outbox roll back together |
| Successful new registration | One arrival with exact package identity |
| Repeated callback or old registered tag | No duplicate or historical arrival |
| Push unavailable, denied or page closed | Durable unread record remains |
| Different authorized readers | Independent read cursors and notification IDs |
| Modal, draft or in-flight write | No focus theft or automatic navigation |

Tests: `worker/test/candidate-notifications.test.ts`,
`worker/test/candidate-migration.host.test.ts`, the existing notification suite,
and candidate cases in `admin/test/version-operations.spec.ts` and
`admin/test/delta-activity.spec.ts`. Assert both positive and negative database
effects, package-detail navigation, and exact label/version rendering. Browser
OS sinks and host R2/SQLite doubles are not real vendor-delivery evidence.

Wrong: notify from a GitHub build-success callback. Correct:
`statements.push(candidateArrival(env, { ...input, kind: input.platform, releaseId }))`
inside the validated registration transaction, followed by a best-effort wakeup
after commit. The scheduled outbox retry remains the recovery route.

## Provider Resource Usage

### Scope And Signatures

`ADMIN-RESOURCE-USAGE-01` adds Access/role-protected `GET /api/admin/resource-usage`.
`resourceUsage(env, now?, fetcher?): Promise<Response>` uses D1 only for its shared
cache and lease. Provider queries are fixed, scoped Cloudflare GraphQL requests;
request parameters cannot choose an account, URL, script or SQL query.

The Pages-only secret `RESOURCE_USAGE_API_TOKEN` must have the applicable analytics
read access. `RESOURCE_USAGE_CONFIG_JSON` identifies `accountId`, `workerScript`,
`pagesScript` (Admin), `publicPagesScript` (public update API), `databaseId`,
`namespaceId`, and `bucketName`. IDs and names are validated and serialized, not
interpolated as raw GraphQL. Never expose either credential to the browser.

Migration `0012_resource_usage.sql` creates `admin_resource_usage_cache`. A shared
90-second lease allows one refresh across isolates/tabs. A refresh makes at most
12 provider requests, at most three concurrently, with seven-second timeouts and
256 KiB response limits. Results, including failures, cache for 15 minutes.

### Measurement And Error Contract

Metrics report `key`, `group`, `unit`, `used`, `state`, `reason`, `scope`,
`periodStart`, `periodEnd`, `periodRolloverAt`, `sampledAt`, and `lastSuccessAt`.
Unknown `allowance`, `remaining`, `quotaResetAt` and plan stay null. Scope is the
configured project resources, not all account consumption. A project measurement
does not establish a remaining account allowance.

Workers expose requests and CPU sum (microseconds converted to milliseconds).
Admin and public Pages expose requests and per-invocation CPU P50/P99, never an
invented total. D1 exposes rows read/written and latest storage samples. Durable
Objects expose requests, GB-s duration, SQLite reads/writes and storage. R2
exposes calendar-month Class A/B operation counts and separate latest Standard
and Infrequent Access storage samples. Never take a maximum across storage classes
and call it total storage. These samples/counts are not an authoritative bill.

Daily windows roll over at 00:00 UTC; R2 operation windows at the calendar month.
These are measurement windows, not verified billing/reset periods. Queries exclude
the most recent five minutes and disclose provider delay/sampling. On failure,
retain the last measurement *and its original period*, marked stale. No samples,
missing numeric fields, configuration gaps and permission failures are not zero.
GitHub Actions remains separately labelled not connected. App 8/UTC-day and backend
1000/UTC-day reporting safeguards are shown separately and are not provider quotas.

| Case | Expected response |
| --- | --- |
| Missing/invalid config or credential | `not_configured`, null used; no provider request |
| Provider 401/403 or authorization error | `permission_denied`; never a zero balance |
| Empty dataset | `no_samples`, null used |
| Explicit provider zero | `ok`, used zero |
| Timeout, malformed or oversized response | `unavailable`; preserve older successful data as stale |
| Simultaneous readers | One leased refresh, no unbounded provider fanout |
| Resource scope changes | Separate cache identity, no old-scope values |
| Failure after UTC rollover | Old window retained, never labelled as today's count |

### Examples And Verification

Good: show a measured D1 read count with its scope, window and unknown allowance.
Base: reuse a fresh cached response when another tab opens the panel.
Bad: multiply report counts to estimate D1 usage, infer a Free plan, or divide
bucket bytes by a reference 10 GB allowance and present it as account utilization.
The old reference-quota water level was replaced with decoration, not a meter.

`worker/test/resource-usage.test.ts` covers scope/units, credentials, cache/lease,
bounded bodies, null versus zero and stale-window preservation. Browser cases
verify lazy loading, mobile layout and visible unavailable/stale states. Test
fixtures must serve `resource-usage.js` as JavaScript. The resource panel now hides
synchronously on close: an obsolete 190 ms delay intercepted the next drag when
the taller panel overlapped its orb. Keep the immediate-close/drag regression.

GraphQL dataset fields/units were introspected from the provider during the
2026-11-14 continuation, in addition to the current Workers, D1, Durable Objects
analytics and R2 pricing documentation. Live account plan/custom-login access
remains unavailable; do not turn that capability gap into a billing assumption.

Runtime correction: Cloudflare Workers does not implement `redirect: "error"`;
it throws during Request construction, unlike Node/browser fetch. Provider calls
must use `manual`, reject 3xx and never forward the credential. A host mock that
accepts `error` is not a Workers compatibility check. The initial live probe
caught this before metrics were claimed successful; the regression explicitly
checks the supported mode and a hostile redirect. Browser service-worker fetch
is a different runtime and retains its existing `error` policy. The corrected
reader uses the `resource-usage-v1` cache namespace, preserving the failed snapshot
without serving that incompatible cached failure after the correction.

## Public Website And Favicon Boundary

### Scope And Signatures

`public/functions/[[path]].ts` is a catch-all Pages function, not just an API
handler. `onRequest(context)` must pass GET/HEAD requests for `/`, `/index.html`,
`/favicon.ico`, `/favicon.png` and `/favicon.svg` to `context.next()` so that Pages
can serve `public/site`. Query strings such as `?v=20261114` do not change that
pathname decision. Other routes retain the explicit public API routing table.

### Contracts And Validation

No credentials, bindings, release state or API permissions change. The static
response retains its body, status and asset headers; the existing request-ID
wrapper remains. The ICO, PNG and SVG share the Admin's existing artwork.

| Input | Expected result |
| --- | --- |
| GET `/` | Actual E-Track HTML, not API error JSON |
| GET a bare/versioned favicon URL | Exact image bytes with the matching image MIME type |
| HEAD a listed static URL | Pages metadata with an empty body |
| `/index.html` canonical redirect | May redirect to this origin's `/`; no cross-origin redirect required |
| POST a listed static URL | Existing JSON 404, no static fallback |
| Unknown route, `/api/admin/*` or `/api/ci/*` | Existing JSON 404, no static fallback |
| Known public API | Existing handler, rate limits, validation and error contract |

### Cases And Required Tests

Good: validate original-domain HTML, versioned and bare ICO/PNG/SVG responses,
image decoding and desktop/mobile rendering. Base: an existing client continues
using the unchanged public update and reporting APIs. Bad: modify only static
files while the catch-all still returns JSON, or route every unknown API to HTML.

`worker/test/public-pages.test.ts` checks GET/HEAD delegation, exact bytes and
headers, POST/unknown/private-route rejection, health/control routing and the
shared duplicate receipt. The fixture must include the Pages `env.ASSETS` binding,
not hide its absence behind an `unknown` cast. Type checks and a Pages bundle
build complement host tests; live asset readback is still required after deployment.

Wrong: treat an Admin favicon deployment as an Access login-page change, or
assume a Worker deployment refreshes the separately compiled public Pages handler.
Correct: verify each delivered origin/bundle independently. Cloudflare's hosted
Access login remains a separate management/entitlement boundary; do not change
organization-wide branding, authentication policy or billing to bypass it.

## Delta Schema And Visible Feedback

### Scope And Signatures

`DELTA-SCHEMA-FEEDBACK-01` repairs supplemental firmware metadata and Admin
feedback without regenerating artifacts, publishing channels, approving builds
or changing the installed App. `deltaFileName(job): string` delegates firmware
names to the existing schema's `assetFileName("patch", versionNameFor(target),
base)`. Android VCDIFF names remain unchanged.

`deltaJobViews(env, jobs, fetcher?)` enriches Admin activity/candidate results.
`inspectDeltaRuns(env, identities, fetcher?, now?)` reads GitHub and caches only
observations in `admin_delta_run_status`, created by migration
`0013_delta_run_status.sql`. These are not additional job states or mutations.

### Contracts

New firmware results use names such as
`e-track-at32f435-v3.3.24-to-v3.3.25-patch.etu` and quoted HTTP ETags from
`R2Object.httpEtag`. The read model adapts already sealed results with legacy
names/raw ETags without updating their JSON, object bytes, hashes, IDs or
enablement. Both the Worker and independently bundled Public Pages must deploy
the adapter; changing only the Admin label cannot fix an App's latest/download.

The optional `ci` result contains `phase`, `checkedAt`, `runUrl`,
`approvalEnvironments`, `conclusion` and `errorCode`. It never includes a token,
reviewer identity or service-token `current_user_can_approve`. The phase is one
of `awaiting_approval`, `ci_queued`, `ci_preparing`, `ci_waiting`, `ci_finished`,
`ci_pending` or `ci_unavailable`; canonical `status`, attempt and revision stay
unchanged. Matching requires the exact repository/ref, workflow commit,
`delta:<job ID>:<attempt>` run title and any stored run ID. Ambiguous matches
fail closed instead of linking an arbitrary build.

Only the existing Admin `DELTA_GITHUB_TOKEN` performs read-only observation.
A 30-second D1 lease/cache bounds repeated tabs; at most five pre-claim jobs are
inspected per request, sharing run listings by repository/ref. GitHub requests
use six-second timeouts, 2 MiB body limits and manual redirects without forwarding
credentials. Running and terminal jobs need no provider lookup. No new token or
permission scope is required when the configured credential already supports reads.

`showErrorDialog(error, {scope?})` queues a visible `role="alertdialog"` in the
existing confirmation/result component. `queueFeedback` defers behind active
confirmations, mutations and hidden documents, and binds notices to the actor.
Scoped background failures are deduplicated until recovery/explicit refresh.
`observeDeltaJobs` queues approval reminders with validated GitHub links; stale
queued reminders are dropped. Result dialogs preserve drafts and the underlying
sheet's focus/history ownership. The shared gesture handler's `verticalCentered`
option preserves centered-dialog geometry. Swipes only dismiss.

### Validation And Error Matrix

| Input or observation | Required result |
| --- | --- |
| New firmware delta | Schema v2 `-patch.etu` name and quoted download ETag |
| Existing sealed legacy result | Adapt latest/download view, leave stored bytes/JSON unchanged |
| Matching run with pending reviewers | `awaiting_approval`, environment names, one visible reminder |
| Runner queue or environment timer without reviewers | Separate waiting label, no invented approval |
| Wrong commit/title/ref, duplicate match or wrong stored run ID | No unsafe run link or approval claim |
| Provider 3xx/403/429/error | Explicit unavailable observation, not a failed/restarted job |
| Fresh operation error beneath a sheet | Visible top-layer error, retained draft and request detail |
| Same passive error after dismissal | No periodic popup loop; recover/reset the relevant error scope |
| Approval state advances before a queued reminder opens | Drop the stale reminder |
| Left/right/downward header swipe or Back | Dismiss only; no business request |

### Cases And Required Tests

Good: an existing 30324-to-30325 delta passes latest selection and signed download
without a rebuild, and a different queued run shows its real reviewer gate.
Base: terminal/disabled jobs keep their original controls and ordinary labels.
Bad: rename only a UI field, expose raw R2 ETags to `If-Match`, or infer approval
from elapsed time. Correct: use the shared schema and public read adapter, and
query the exact run's `pending_deployments` before claiming reviewer action.

`worker/test/delta-jobs.test.ts` asserts legacy latest/download bytes, filename,
ETag and unchanged sealed storage. `worker/test/delta-run-status.test.ts` covers
identity, provider failures, gate versus timer, cache expiry, concurrency and the
five-job bound. Admin feedback regressions in `version-operations.spec.ts` cover
visible errors, approval deduplication/staleness, actor changes, retained drafts,
long mobile messages and dismissal gestures with zero mutation. Existing App/MCU
tests must explicitly dismiss expected errors before operating the underlying
sheet, not weaken modal behavior to preserve an obsolete test assumption.

Host SQLite/R2 doubles and browser mocks are self-tests, not deployed runtime or
device acceptance. Use the existing Linux Cloudflare checks for real workerd
when native Windows workerd cannot start; do not change system tooling or App
dependencies as a workaround. Verify the deployed latest and bounded download
on both serving origins without starting OTA or generating another delta.
