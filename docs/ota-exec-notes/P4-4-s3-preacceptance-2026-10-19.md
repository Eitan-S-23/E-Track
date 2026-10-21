# P4-4 S3 Pre-Acceptance Review (2026-10-19)

Current disposition: P44-REVIEW-01 and P44-REVIEW-02 are RESOLVED on b56534d;
independent successor review is 10/10 and both source-bound development CIs pass.
Both target Workers now contain the verified new module. P44-CREDENTIAL-01's
missing-pair/configuration blocker is RESOLVED by the later agent handoff and
root's independent 15-GET / 28-assertion readback. The successful provisioning
source differs from the previously denied local token; it is not evidence that
the old token's 403 became 200. Formal P4-4 remains IN_PROGRESS, not PASS:
V1 through V5 are closed EVIDENCE_GAP rounds. In V4 the owner personally rejected
A and approved B; B's new-chain rehearsal, independent bytes/readbacks and
production read-only preflight passed. The after-state collector retained 31
complete responses before a connection timeout. C5 stopped at an auxiliary token
verification connection reset before any new business read; its HTTP receive
phase is unknown. A matching original token ID is now available offline, without
new credentials or permissions. Only missing after evidence and offline aggregate
decisions remain, with C4/3.2.9 preserved as the product target.
Historical failures remain below;
see Independent Credential Handoff for the source, protection and lifecycle
limits, and the final continuation sections for current execution state.

## Historical Initial Review: Source And Scope

- Reviewer: main/root agent, not the implementation author.
- Delivery: 546d8b39a5697ba1b018720b120608de52a511d2 on
  dev/p4-4/config-integration-20261018.
- Product/workflow development CI source:
  de362151bda72c0dd1c19ab1293e99838fb8976e.
- Current governance correction:
  53f336d2f6dfc6067b33b3cf6975d52c5ffad9e2.
- Reviewed the S3 port, uploader, fixed preflight handler/client, shared monotonic
  checks, release/promotion/qualification callers, workflow credential mappings,
  relevant tests and current contract changes.
- Applicable rules: acceptance-execution-contract sections 0 and 7.3, the
  collaboration response contract, and OTA-XC-R2-UPLOAD / OTA-XC-SECRETS /
  OTA-XC-RELEASE-GATE at the delivery source.

No implementation worktree, product source, platform configuration, existing
evidence or task ownership was changed by this review. No CI, Worker deployment,
credential creation, staging rehearsal, reviewer action or device operation ran.

## Findings

### P44-REVIEW-01: Historical storage fixture cannot be a release candidate

Disposition: DECIDED, required fix, P1. Affected entry:
.github/scripts/firmware-bindings-check.mjs, checkFirmwareBindings.

The fixed existing-object input is
docs/ota-exec-notes/P4-1-r2-registration-qualification-2026-10-15/operations/verified-metadata.json.
It is the synthetic 2.8.1 / 20801 storage qualification sample. The new caller
passes this same metadata into preflightFirmware before opening the S3 port.

The accepted P4-1-v4 target is 3.2.8 / 30208. Its original target.json,
states-formal.json and the P4-1 implementation record retain the successful
registration. This review did not query current Cloudflare state; it tested the
valid retained-history state explicitly rather than assuming a fresh database.

Independent reproduction exercises the actual checkFirmwareBindings,
preflightFirmware and verifyMonotonic code with injected read-only DB/storage
ports. Empty DB control succeeds (two preflights, three object reads). With
current version 30208, the fixed sample returns HTTP 409 / RELEASE_CONFLICT
before S3 connection or any object read. The existing host qualification test
uses the actual handler, but seeds the storage objects without the newer
registered-release history, so it does not cover this case.

Preferred minimal direction:

- Separate the existing-object readback input from the independently bound
  preflight metadata. The latter must be an actually reviewed candidate or the
  exact canonical identity of the current registered release, not a fabricated
  higher version used merely to pass qualification.
- Bind the preflight input and its SHA/source in the existing qualification
  contract/caller. Keep the three old objects as read-only storage fixtures.
  A new general SQL or management endpoint is not needed.
- Seed the accepted newer-release history in a real handler/SQLite regression.
  Verify the supported qualification route reads all three old objects without
  PUT/register, while an actually stale or same-version conflicting publication
  candidate still fails before GitHub/R2 side effects.

Do not clear/downgrade staging D1, replace the frozen 2.8.1 fixture, skip the
monotonic predicate, change a version in memory just to get green, or repeat the
old successful rehearsal as a workaround.

Owner: implementation agent repairs the caller/input contract and related test
coverage as one batch. Root checks the revised input binding and the history
regression before scheduling live qualification.

### P44-REVIEW-02: Stream failure is falsely reported as an object conflict

Disposition: DECIDED, required error-contract fix, P2. Affected entry:
app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/upload-firmware-r2-asset.mjs,
readback's catch around reader.read.

The added blanket catch throws mismatch() for every stream exception. For an
already-present object, mismatch() means R2_OBJECT_CONFLICT and the message says
the existing object has different byte identity. A transport interruption does
not establish any such difference.

Independent reproduction provides correct HEAD identity and a read stream that
errors. verifyStoredFirmwareAsset reports R2_OBJECT_CONFLICT. A genuinely
different-byte stream reports the same code; a valid stream succeeds. These are
injected stream cases, not a claim of an actual Cloudflare network fault.

Preferred minimal direction:

- Preserve deliberate identity/length/digest mismatch errors.
- Project unknown stream/read/abort failures to a sanitized R2_VERIFY_FAILED
  (or the documented transport code where applicable), not a proved conflict.
- Add interrupted existing-object replay coverage, including failure after some
  bytes, plus controls for genuine digest mismatch and exact successful replay.
  No raw upstream message, URL, credential or signature may enter diagnostics.

Changing classification does not authorize automatic retry, unconditional PUT,
deletion/replacement of an existing object, or relabelling any old failure.

Owner: implementation agent fixes the catch and its SDK/uploader regressions;
root verifies the three distinct outcomes on the successor source.

## Historical Initial Review: Checks Actually Performed

Review-only scripts and outputs live under the active root at:
.cache/p44-root-review-546d8b3-20261019/

- cases.cjs / cases-result.json: five bounded offline scenarios using the actual
  product caller/shared predicate/uploader with explicit DB/stream ports.
  Both reported defects reproduce; empty-state and correct-byte controls pass.
  This is not a new real Worker, S3 or permission observation.
- originals.cjs / originals-result.json: all 48 delivered raw files, 3139235
  bytes, match their inventory SHA-256/length and committed Git blobs.
- Product/workflow/affected release-test sources are unchanged between the
  successful de36215 development CI and the delivery commit.
- Reviewed the original 283 native / 131 pipeline / 98 SDK-workflow CI summaries
  and their source identities. They remain implementation CI results, not newly
  executed independent test campaigns or formal PASS.
- Checked the pinned HTTP handler cancellation wiring. No additional
  cancellation finding is asserted from an untested hypothesis.

Commands, run from D:/github/my/E-Track:

    node .cache/p44-root-review-546d8b3-20261019/cases.cjs > .cache/p44-root-review-546d8b3-20261019/cases-result.json
    node .cache/p44-root-review-546d8b3-20261019/originals.cjs > .cache/p44-root-review-546d8b3-20261019/originals-result.json

The first combined inline probe exceeded cmd.exe's command-length limit before
executing. Split bounded probes succeeded; file-based copies avoid that limit.
The initial output preflight expected a numeric fsutil error in its text and
rejected the localized diagnostic before any write. It was corrected to decode
and require the actual "not a reparse point" result. These preparation failures
are not product-test failures and are not counted as passing checks.

## Historical Initial Review: Disposition And Next Action

The S3/target-Worker route remains approved. Do not return to account-wide
Workers permissions or request the obsolete CLOUDFLARE_API_TOKEN.

Consolidate the two findings in the existing P4-4 record. Repair and self-test
the affected batch; the real new-chain staging campaign is not a development
prerequisite to obtain an independent PASS. Root resumes the affected review
on the successor source and then prepares the admitted live plan.

The live plan still needs distinct bucket-scoped S3 pairs, exact Worker source
and binding readbacks, reviewed candidate/descriptor identity, and the actual
reviewer rejection route. New-chain rehearsal evidence is required where the
changed dependencies invalidate old observations; unchanged valid originals
remain inputs for independent evaluation, not direct cross-task REUSED entries.

The 11 dependency advisories, compiler/deprecation warning occurrences, real
role-session/admin-bypass limits and historical external-cache attribution remain
disclosed. They are not silently resolved, nor is unrelated full remediation
invented as a consequence of these two findings.

OTA_BOOT_CHAIN_READY remains false. No production release or device operation
is authorized by this review. Report and review-only outputs are local and
uncommitted; no main integration or implementation-branch mutation occurred.

## Resumed Owner Delegation And Preparation

The owner explicitly authorized implementation sub-agents and autonomous
progress through P4-4 closeout on 2026-10-19, stopping only for genuinely
necessary owner actions. Root assigned P44-REVIEW-01 and P44-REVIEW-02 as one
implementation batch on the existing exclusive branch; root does not author
the product repairs. The child inherits the parent model configuration. The
available collaboration receipt does not establish an exact runtime model ID.

Two bounded read-only reviews cover dependency advisories and the exact R2
credential policy/API, alongside root's platform and formal-plan preparation.
No new mandatory pre-acceptance reviewer or per-fix approval cycle is introduced.

Preparation outputs are under .cache/p44-root-acceptance-20261019/ in the active
root. The existing P4-4 path guard and existing Undici HTTP component are reused;
there is no new platform protocol or replacement uploader. Node/cmd execution,
selected cache/temp locations and all evidence outputs are preflighted inside
D:/github/my/E-Track. Root does not mutate the child's worktree concurrently.

platform-preparation-01.json retains an initial connection timeout before any
successful API request. The proxy was confirmed listening and a separate curl
HEAD reached Cloudflare; the failed read was then repeated once. The successor
platform-preparation-02.json completed 20 bounded read-only requests:

- Both previously supplied credentials verify active. Both user and account
  permission catalogs return 403/code 9109. This is not token absence, a failed
  creation attempt or permission to expand scopes. No POST token creation has
  yet occurred.
- Both production and staging retain their recorded Worker/D1/R2 targets and
  old Worker deployments. The new preflight Worker remains NOT_DEPLOYED.
- Production retains its four existing secrets and no S3 pair. Staging retains
  its existing five secrets and no S3 pair. Old control-plane secrets are not
  wired into the new workflow.
- Repository and both environment gates are exactly false. Production retains
  reviewer Eitan-S-23, prevent_self_review=true and main-only branch policy.
  Staging retains that reviewer, prevent_self_review=false and the one old
  exact P4-1 branch. Admin-bypass capability remains true and was not used.
- Remote main is still 0779f677507fa2c8a88c1799c8d2909bbae5a0a0.

Planned affected formal coverage, to freeze only after batch review and available
environment prechecks: current configuration/type/scope readbacks; source-bound
negative/redaction checks; exact bucket credentials and target Worker auth;
actual reviewer waiting/rejection plus an approved new-chain staging run;
three immutable asset readbacks and ready/idempotency; unchanged production
D1/R2/channel/GitHub Release snapshots; owner/rotation/revocation handoff.
Existing applicable raw inputs will be independently evaluated, not relabelled
as same-task REUSED or repeated as a new physical campaign.

Root will bind any new branch, candidate version/commit and bootstrap descriptor
explicitly. Historical 3.2.8/b9d7d18 approval cannot silently authorize the new
chain. The existing reviewer must perform actual P4-4 reviewer actions; the
historical P4-1 proxy-approval exception is not reused. Production approval and
release remain after P5. These are preparation records, not a frozen contract,
formal start, platform mutation or P4-4 PASS.

### P44-DEPS-01: Advisory Assessment

Disposition: DECIDED, disclosed non-blocking dependency debt for the current
call paths, not a claim of no vulnerabilities. A read-only independent child
reviewed the lock, installed dependency source, the official npm advisory feed
and 32 unique GitHub advisories. Root independently checked the original CI log
and lock hashes and the Worker/raw-request and uploader entry points.

The historical log SHA-256 is
2feadac23e5c659bcb748c61d7caf621ab1181f57e32738eba49e96536c46588;
the committed worker/package-lock.json SHA-256 is
5c52e25476276ec2827d703a0145fc6672060bf88cc29856ff2bdc50dddeaa61.
The old log records only 11 affected package nodes, 3 moderate and 8 high, not
11 unique advisories. Its historical complete audit JSON was never retained.

| Package node | Version | Severity | Current reachability assessment |
| --- | --- | --- | --- |
| hono | 4.12.27 | moderate | Runtime core router; affected CORS/JSX/proxy/language/SSG/parseBody/query helpers are not used. Handlers receive c.req.raw. |
| vitest | 4.1.9 | moderate | Non-public run-mode development tests; no exposed standalone mocker/interceptor plugin. |
| @vitest/mocker | 4.1.9 | moderate | Same advisory and development boundary as Vitest, not another unique defect. |
| nanoid | 3.3.15 | high | PostCSS calls a fixed positive size, not attacker-selected zero/negative size. |
| postcss | 8.5.15 | high | No untrusted CSS/sourceMappingURL processing in the release path. |
| source-map-js | 1.2.1 | high | No untrusted indexed source-map processing in the release path. |
| sharp | 0.34.5 | high | Miniflare Images path; no Images binding or untrusted image input is configured. |
| undici | 7.28.0 | high | No affected retry/cache/decompress/dump interceptor, BalancedPool, cookie helper or hostile WebSocket path in this scope. Not the AWS SDK Node HTTP transport. |
| miniflare | 4.20260625.0 | high | Exact-pin transitive advisory node; local/native development runtime, not deployed Worker dependencies. |
| wrangler | 4.105.0 | high | Exact-pin Miniflare dependency; build/deploy tooling, not deployed Worker runtime. |
| @cloudflare/vitest-pool-workers | 0.16.20 | high | Exact-pin development dependency node. |

All 11 versions are unchanged from the pre-S3 53ad5d0 input. The current public
query returned 8 directly affected packages and 33 package-advisory records
(32 unique GHSA IDs); a current reconstruction matches the old 11-node count
but does not recreate the missing historical raw audit.

The implementer subsequently ran one contained npm audit --json at the current
date, retaining its complete output and real exit 1 in
.cache/p44/logs/remediation-npm-audit-01.{log,json}. Root parsed this original:
11 nodes, 3 moderate, 8 high, 0 critical. This is a new advisory snapshot, not
a failed product test, a historical replacement or an audit-fix operation.
Release jobs still install development dependencies; "not exercised here"
does not mean "not installed". No exploit test or dynamic coverage claim is made.

Future use of the affected APIs must reopen the corresponding dependency
assessment. Published fix floors reviewed by the child are Hono 4.13.7,
Vitest/mocker 4.1.11, nanoid 3.3.18, PostCSS 8.5.23, source-map-js 1.2.2,
sharp 0.35.5 and Undici 7.29.1. Upgrade the compatible toolchain as a tested
batch; do not use unverified overrides or npm audit fix --force. No unrelated
full firmware/physical campaign is required by this non-blocking disposition.

### P44-CREDENTIAL-01: Actual Creation Authority Check

The R2 policy review confirmed the documented single-bucket resource syntax,
explicit allow/implicit deny behavior and ID-required permission-group shape.
Two public Cloudflare-provider issues corroborated Bucket Item Write ID
2efd5506f9c8494dacb1fa10a3e7d5b6; this is not a live catalog receipt. The
creation request omitted the cosmetic group name so any returned name would
have to be resolved by the service, not echoed from the request. Consumption
was conditioned on exact service-returned one-policy/one-bucket/one-group scope.

Root reserved the intended production credential operation, established a
current-user-only ACL on the project-local private destination, and attempted
the actual strict request through the documented account-token endpoint.
Only after a definite 403 with success=false and no returned token did it try
the documented user-token endpoint with the same local provisioning credential.
Both returned 403/code 9109. The closed record is
.cache/p44-root-acceptance-20261019/create-s3-production-01.json,
ended 2026-10-18T22:59:40.924Z; the pre-POST reservation is retained alongside it.

No token or key file was created; no secret was configured, no scope was
expanded and no failed/ambiguous write was retried. These are actual rejected
creation attempts, unlike the earlier catalog GET denials. No staging creation
was attempted with the same unavailable management authority. Existing
e-track-ci remains present and is not substituted into production CI.

Required owner action after safe autonomous preparation is exhausted: create
or supply two distinct R2 Object Read and Write pairs, each limited to its
exact existing production/staging bucket, and put them directly in the matching
GitHub environment secrets or a protected project-local input. Do not send
plaintext in chat. This is now a real platform-rights blocker, not another
request for a route choice or general delegation.

Object Read and Write includes deletion capability at Cloudflare's permission
granularity. The application never issues DELETE, but this is not hard put-only
IAM. Official short-lived action-scoped credentials need a session-token path
not implemented by the current pair-only S3 client; they are not silently
substituted as a different release interface.

### Interim Review Progress Before Source-Bound CI

The implementation child completed the local affected checks: SDK 23/23,
pipeline 147/147, workflow 89/89 and typecheck exit 0. Root reviewed the actual
product/caller/test diff without adding a third required product finding.
Source-bound successor review and non-publishing CI remain to be closed.
The initial implementation turn hit a provider token-rate limit; its explicit
provider receipt identified gpt-6-astra. The same child resumed its existing
changes with the same model rather than restarting tests or changing models.

The fixed preparation D1 reads independently confirm production has no current
firmware release and staging still has versionCode 30208; all six SELECT
responses report zero rows written. Canonical 3.2.8 identity remains intact.
Formal P4-4 rounds remain zero and gate remains false.

## Stable Remediation And Source-Bound Review

Product: b56534d7b6c993c0795010d0404fb8a81f7eeb9d.
Implementation evidence: 15be25e593405396d8db8fb0011fc62e42d6d27d.
Branch: dev/p4-4/config-integration-20261018.

Root's verify-remediation-01.json contains ten independently executed offline
cases using the actual caller, client and monotonic predicate with a separate
in-memory SQLite harness. Empty and actual 30208-history cases each perform two
preflights, six SELECTs and three old-object reads with no PUT. Stale and
same-version conflicts fail before S3; a raw-SHA mismatch makes no request.
Empty/partial/abort read failures yield R2_VERIFY_FAILED, exact bytes succeed,
and actual differing bytes still yield R2_OBJECT_CONFLICT. Both original repair
oracles are satisfied. The Node experimental SQLite warning is retained; this
is not a native Worker/S3 or formal acceptance claim.

Firmware CI 39175549010 and governance CI 39175558187 both passed at b56534d.
The three cloud/publication jobs in the former were skipped. Root independently
verified all 38 successor originals, 2990737 bytes, against both inventory and
committed Git blobs; all match. Product, relevant tests and current contracts
are unchanged by 15be25e. delivery-review.json retains this evaluation.

Actual CI groups: native 283, pipeline 147, SDK/workflow 112 (23 plus 89, not an
extra disjoint 112), script/migration 41 and byte preparation 22. Worker/GCC
builds and types passed. Governance's eight primary suites total 331. Current
CI has 1309 warning-containing lines, including two GCC passes of 640 each and
six bsdiff warnings. These are occurrences, not unique defects. The first
failed TLS log retrieval and the new npm audit exit 1 remain originals.

## Worker Configuration Preparation

The downloaded CI artifact is 12154675551,
p41-worker-bundle-b56534d7b6c993c0795010d0404fb8a81f7eeb9d,
102228 bytes, archive SHA-256
7bee78195841780046c3333d4dc6c0b3ec9d442f8a99399051d204844a7e2f6f.
All 16 non-dependency source-map inputs match their committed Git bytes. The
single runtime module is 149013 bytes, SHA-256
1ad919d795a2354cd4c7d9617f3e3c9805f831967d1a2cdd5930ba61e4c3303f.

worker-input-01.json preserves an evaluator mistake: it expected a separate
firmware-preflight.ts file, but the actual handler is in firmware.ts. The old
helper is preserved. worker-input-02.json re-evaluated the same retained ZIP
offline; no new download, build or CI was run to repair that check.

### P44-DEPLOY-01: Non-Versioned Observability Override

Disposition: DECIDED, deployment-adapter issue found by a real readback, repaired
without modifying product code or repeating a firmware rehearsal.

The staging CLI invocation deployed the new source, but its subsequent
non-versioned settings PATCH disabled query redaction despite the explicit true
in unsafe upload metadata. Initial false was observed at 23:34:12 UTC. Root
stopped production deployment and attempted only restoration of the existing
staging observability settings. The first restoration PATCH lost its connection;
its outcome was treated as unknown, not blindly repeated. A separate curl GET
still showed false before the single subsequent PATCH. True was read back at
23:41:17 UTC. No Worker business request was made by root during this interval;
the absence of unrelated third-party requests or exposure is not asserted.

The independent read-only investigation traced pinned Wrangler 4.105.0:
cli.js:150062 obtains worker.observability from the top-level parsed config;
:150186 sends that object in the later PATCH. unsafe.metadata only replaces
upload metadata. The ordinary JSON configuration path retains unknown fields
while emitting warnings (inheritable :29727, validation :39583/:42198,
readConfig :171590). The separate experimental-new-config path was not used.

The corrected adapter writes the complete observed observability object to
both top-level config and unsafe upload metadata. It preserves TLS checks,
uses the standard CLI and does not upgrade dependencies. An unknown-field
warning is retained, not used as proof of behavior. Production's final readback
actually confirms true and exact observability equality; it did not use the
staging stop-and-repair sequence as its normal deployment procedure.

Two production preparation reads failed at the connection layer before any
configuration was written. The first actual production CLI attempt stopped at
its sole initial read-only services GET, before uploading. Root reviewed that
original log, successfully read current service/old version with curl and then
continued the unperformed update. It did not reissue an ambiguous upload.

### Current Deployed Identity

| Target | Version | Source / actual readback |
| --- | --- | --- |
| e-track-firmware-p41-test | bb3d44fd-4a84-489e-9e04-6adfc54a458e | b56534d module; redaction-recovery-02.json verifies raw downloaded bytes, unchanged DB/R2/KV/DO bindings, secret names, compatibility settings, full observability and cron. |
| e-track-firmware-production | e1653d60-03cb-4397-b154-78efd681ebbc | b56534d module; deploy-04.json verifies raw downloaded bytes, unchanged DB/R2 bindings, secret names, compatibility settings, full observability and cron. Deployment b76395f1-f2bf-4adb-b936-0a291edf6e45. |

Both module readbacks equal the CI runtime SHA above. No migrations, R2 object
writes, firmware registrations, channel changes, GitHub Releases or device
operations were requested. These are authorized Worker configuration updates,
not production firmware publication or the new-chain staging rehearsal.
All three gates were read as false immediately before the production update.
Native runtime authorization/upload/idempotency observations still belong to
the pending frozen formal plan; deployment identity alone does not satisfy them.

## Closing Disposition And Owner Input

No remaining known product repair is assigned to implementation. Root completed
all presently independent safe review/configuration work. The required external
credential dependency is still missing: the current local provisioning source
cannot create either account-owned or user-owned tokens (actual 403/code 9109).
General delegation cannot change that Cloudflare permission. P4-4 cannot start
its complete formal campaign or be closed as PASS on this evidence.

Owner must create or select two independent R2 Object Read and Write pairs,
each limited to its exact bucket, retaining redacted policy/source/lifetime
information. Do not send values in chat, reuse the old broad CI/provisioning
token, add account-wide permissions or place values in ordinary variables.

| GitHub environment | Exact bucket | Required secret names |
| --- | --- | --- |
| firmware-production | e-track-firmware-production-releases | TRACE_R2_ACCESS_KEY_ID; TRACE_R2_SECRET_ACCESS_KEY |
| firmware-rehearsal | e-track-firmware-p41-test-releases | FIRMWARE_REHEARSAL_TRACE_R2_ACCESS_KEY_ID; FIRMWARE_REHEARSAL_TRACE_R2_SECRET_ACCESS_KEY |

The owner may configure these directly, or provide the pair values through the
already current-user-only project directory
.cache/p44-root-acceptance-20261019/private/. No new general authorization or
plaintext chat reply is requested. Root will verify scope/presence/capability,
bind the exact candidate and descriptor, commit/freeze the runner and perform
the NOT_RUN precheck before formal observations. Version 3.2.9 is the proposed
next real candidate after observed 3.2.8; its exact commit/descriptor is not yet
approved and will not be fabricated merely to pass a qualification check.

Existing reviewer Eitan-S-23 must perform the real rejection and later approval
on the exact staging run(s) root prepares after admission. Historical P4-1
delegated approval is not reused. Root preserves waiting, actor/receipt and
same-run unexecuted release steps, then evaluates the one required new-chain
staging observation and production before/after evidence. No production
firmware release, gate unlock or P5/device work is included.

The branch remains pending main integration. Formal rounds are zero; no frozen
P4-4 bundle or FREEZE-INDEX entry is invented for this preparation. Old failures
and frozen P4-1/P4-3 evidence are unchanged. Generic token-governance changes
already on the task branch remain pending main delivery as previously recorded.

### Final Read-Only Admission Refresh

At 2026-10-19T00:58:42.120Z, refresh-admission-02.json completed ten GitHub GETs.
Both production S3 secret names and both prefixed rehearsal names remain absent.
All three OTA_BOOT_CHAIN_READY variables are false. Environment reviewer,
prevent-self-review and exact branch restrictions remain as previously recorded;
remote main is still 0779f677507fa2c8a88c1799c8d2909bbae5a0a0. Secret metadata
does not prove value correctness or operation-specific capability.

refresh-admission-01.json retains the earlier connection timeout on the second
GET, not a permission or product failure. A separate verified-TLS reachability
check completed before the successful read-only refresh. No token-creation or
configuration mutation was repeated. The required external input remains real;
the task can be recorded as blocked under board section 0.6 without inventing
an ENV_BLOCKED formal round or changing the readiness derivation.

The published review entry is docs/ota-exec-notes/P4-4-root-review-2026-10-19/.
Its inventory distinguishes byte-exact originals from explicitly sanitized
public projections and retains original hashes/locators. This is preparation
delivery on the existing task branch, not whole-card closure or main delivery.
The selected publication contains 149 evidence files, 1172491 bytes: 117
byte-exact originals and 32 declared public projections. Both raw deployed
module responses and the CI ZIP remain byte-exact; private configuration and
credentials are excluded. Known protected values and credential-shaped strings
were scanned, including uncompressed CI ZIP members, before publication.

### Record Checks And Write Audit

The independent read-only record review checked the complete current report,
configuration matrix and P4-4 board update together. It caught a dropped existing
credential-discovery sentence before execution; the sentence was restored without
weakening a test. Three selected PostP26SpecGovernanceTests then passed in 0.047s:
readiness derivation/exact dispatch set, P4-4 interface reconciliation, and the
scoped S3/preflight contract. root-record-check-01.{log,json} retain the actual
Python 3.13 command and exit 0. The record diff check also returned 0; Git's
LF-to-CRLF warning is retained. No full product/GCC/native campaign was rerun.

write-audit-01.json at 2026-10-19T01:23:29.615Z checked 168 files, 38 directories
and 2603182 bytes across the selected root preparation, review and task-record
outputs. All selected output paths are within D:/github/my/E-Track; root's shared
index was only fingerprinted for later comparison, not staged. The delegated
implementation output audit and original hashes were separately reconciled.
The audit is not a machine-wide filesystem trace or evidence of zero external
writes. A final read-only audit also checks the newly published copies and the
unchanged root shared index after scoped Git delivery.

Known external metadata observations remain attribution-unresolved:

| Read-only observed path | Size | Latest observed UTC mtime |
| --- | --- | --- |
| C:/Users/SU/AppData/Local/Microsoft/Windows/PowerShell/StartupProfileData-NonInteractive | 1004 | 2026-10-19T01:10:43.603Z |
| C:/Users/SU/AppData/LocalLow/Microsoft/CryptnetUrlCache/Content/B6E4D06BF128A1673A8DAFB4E25B990D | 309 | 2026-10-19T01:20:01.013Z |
| C:/Users/SU/AppData/LocalLow/Microsoft/CryptnetUrlCache/MetaData/B6E4D06BF128A1673A8DAFB4E25B990D | 192 | 2026-10-19T01:20:01.013Z |

These updates were not intentionally requested, and no PowerShell command was
invoked by root or the review children. The timestamps alone do not identify
the writer or establish contents. No cleanup, move or overwrite was performed.
Any future cleanup requires path-specific owner permission; preserve the files
and correlate host/process tracing rather than asserting an unproved cause.

### Git Delivery Reconciliation

The first index check rejected an incomplete stage: .gitignore:13 excludes
*.log, so ordinary git add skipped twelve selected evidence logs. Only those
twelve already scanned public copies were force-added; no ignore rule, source
or evidence byte was changed. That initial failure is in the truncated tool
transcript, not a complete saved console log. The later contained
.cache/p44/logs/root-index-verify-02.{log,json} records the successful check of
155 staged files and all 149 original/public evidence pairs against Git blobs.
Known protected-value scanning passed; there were no conflict-marker or secret
pattern hits. This is packaging verification, not a formal acceptance round.

The global pre-commit debug-statement rule also matches four byte-exact archived
Worker-module responses. Those are original evidence, not added application
debugging code. Only GIT_NO_DEBUG_CHECK is scoped to the evidence commit after
the explicit byte/secret checks; conflict and secret hooks stay active. Explicit
commit-message input avoids the global AI-message hook, and the contained
runner disables webhook notifications. No global hook/configuration is edited.

## Owner Permission Update: Fresh Verification

P44-CREDENTIAL-01 remains an external credential blocker, not a new product
finding or a request to choose the interface again. The owner reported that
permissions had been updated. Root therefore tested the current protected
local provisioning input instead of reusing the historical rejection as proof
of the new state. The new entry is P4-4-credential-resume-2026-10-19/; its inventory
binds originals and explicit public projections. Existing archives are unchanged.

- verify-permissions-02.json and -03.json confirm the local token is active.
  User/account permission catalogs and self-metadata GETs return 403/9109.
  These reads do not prove creation failure or reveal the current policy/name.
- The existing CI account permission catalog also returns 403/9109. There is no
  evidence that the added management permission reached e-track-ci, but this
  single denied endpoint is not a complete audit of its grants.
- refresh-admission-04.json preserves nine successful GitHub reads: the four
  S3 names remain absent, all three gates are false, reviewer/branch settings
  are unchanged. Its tenth main-ref GET failed at TLS; this is a partial refresh,
  not ten successful reads, not a main change and not an authorization denial.
- After a pre-POST reservation and a verified current-user-only private output
  ACL, root made one new production account-token POST. The policy requested
  exactly e-track-firmware-production-releases and the documented Object Read
  and Write group, with 90-day expiry. It returned a definite 403/9109, no token
  ID or value, at 2026-10-19T04:41:00.445Z (request a4cd1b9f4ac38685-NRT).
  The 124-byte denial is retained byte-exact as account-create-denial.json.
- No pair was created or written to GitHub. No staging create, user-token
  fallback, scope expansion or retry of the denied POST followed. The first
  local permission probe and the later transport interruption are retained,
  not converted to successful permission checks.

The next owner input is the name and redacted Permissions / Account Resources
view of the token actually edited. Root cannot infer whether the cause is the
selected token, account scope, underlying membership/grants, or a newly issued
value that has not replaced the existing protected input. Do not ask the owner
to send the token value in chat. If the owner created/rolled a replacement, its
value must reach the already protected local input before another permitted
state-change check. The source currently consumed is project-relative
.cache/p41-dev-20261015/.cache/cf-auth-input/token.txt, never the CI token file.

### Consolidated Remaining Formal Plan

The read-only p44_acceptance_plan child reviewed the complete remaining scope
on 231932f. It found no new evidenced product repair. Root retains the following
single plan rather than discovering these preparation gaps one at a time:

1. Obtain and verify both bucket pairs; complete scope/lifetime/name/type and
   false-gate/reviewer/branch readbacks without a production object write.
2. Independently review the actual new staging candidate and bootstrap target,
   then commit the bounded runner and freeze P4-4-v1 with a NOT_RUN precheck.
   3.2.9 remains a proposal, not an approved candidate or an artificial version
   used only to satisfy qualification. Cached helpers are not formal runners.
3. Plan two new workflow dispatches on the same reviewed inputs: run A waits
   for Eitan-S-23 to actually Reject; after A terminates, new run B starts at
   attempt=1 and that reviewer actually Approves the sole new-chain staging
   observation. Do not rerun A: attempt>1 requires an artifact absent after
   rejection. The old campaign's P4-1 proxy-approval code must not be reused.
4. Do not add a third check_bindings run by default. Its two metadata variables
   are explicitly not ordinary rehearsal/production prerequisites. If an actual
   safety need justifies that extra run, bind canonical 3.2.8 raw JSON separately
   from the historical 2.8.1 storage fixture and count its run/reviewer action.
5. Reuse the original offline byte evaluator with absolute artifact/target paths;
   add only new-protocol/preflight, real-reviewer and current-production snapshot
   checks. Before/after snapshots include production D1/schema/channel, complete
   R2 listings, GitHub Releases/assets, and the protected old Trace resources.
   The pipeline's existing register/replay is one shared observation, not a
   reason to repeat a successful workflow.
6. Evaluate existing CI/remediation/deployment originals without rerunning them;
   finish the matrix, terminal validator, immutable bundle and later freeze-index
   entry only after all required observations. Preserve dependency debt, warning
   occurrences, P44-DEPLOY-01 and external-cache attribution limits. Production
   promotion bindings must use exact successful artifact hashes, never a summary.

No candidate/branch variable, formal runner, frozen contract, approval, business request,
release or device operation was executed by this plan review. Formal rounds stay
zero and gate remains false. Actual reviewer clicks still require the existing
reviewer; the owner need not grant generic delegation again.

### Continuation Checks And Write Audit

The three affected record/readiness/S3 contract regressions passed (3 tests,
0.068 seconds); original output and exit 0 are in
.cache/p44/logs/root-permission-record-check-01.{log,json}. git diff --check also
passed, retaining the existing LF-to-CRLF warnings. No full product suite or CI
was repeated. The read-only child independently reconciled this record batch
and all 36 original/published file hashes: 32 byte-exact, four declared
projections, 83894 bytes; no additional fact correction was required.

.cache/p44-root-acceptance-20261019/permission-write-audit-01.json (project-root
relative) inspected 100 selected paths, verified all 36 archive/source pairs,
confirmed the unchanged root shared index and unchanged product/frozen inputs.
Only the three task records, new task-local evidence and contained preparation
outputs were selected for writing. This continuation has no commit/push or main
integration; its records/evidence are local modifications on the existing task
branch, whose published baseline remains 231932f. The present audit note was
appended afterward on its separately rechecked existing task-record path.

The audit is not a machine-wide trace. These external files had timestamps
inside this continuation's selected-write window; their contents were not read
and the timestamp alone does not establish the writer or whether a file is new:

| Exact external path | Bytes | Observed UTC mtime |
| --- | --- | --- |
| C:/Users/SU/AppData/Local/Microsoft/Windows/PowerShell/StartupProfileData-NonInteractive | 1004 | 2026-10-19T04:40:22.379Z |
| C:/Users/SU/AppData/LocalLow/Microsoft/CryptnetUrlCache/Content/5F1978C76A118CE692CF538FB0B323EA | 310 | 2026-10-19T04:41:18.925Z |
| C:/Users/SU/AppData/LocalLow/Microsoft/CryptnetUrlCache/MetaData/1B1495DD322A24490E2BF2FAABAE1C61 | 192 | 2026-10-19T04:37:50.022Z |
| C:/Users/SU/AppData/LocalLow/Microsoft/CryptnetUrlCache/MetaData/22D536C4B4AD2CEF7AC6B7789FD235E3 | 192 | 2026-10-19T04:37:47.334Z |
| C:/Users/SU/AppData/LocalLow/Microsoft/CryptnetUrlCache/MetaData/5F1978C76A118CE692CF538FB0B323EA | 192 | 2026-10-19T04:41:18.926Z |
| C:/Users/SU/AppData/LocalLow/Microsoft/CryptnetUrlCache/MetaData/77EC63BDA74BD0D0E0426DC8F8008506 | 330 | 2026-10-19T04:37:50.791Z |

No PowerShell command or deliberate external-cache write was invoked by root
or the child. The existing curl adapter uses Schannel, which is relevant to
investigation, but no causal attribution is proved for these observations.
Do not claim zero external writes. Preserve these files; do not move, overwrite
or clean them without path-specific permission. Before further use of any
route capable of such writes, establish containment or the applicable exact
authorization; correlate host/process records before asserting a root cause.

## Independent Credential Handoff

Root and a read-only independent child reconciled the owner's later agent
handoff rather than repeating its successful creates or S3 lists. The archive
P4-4-credential-handoff-2026-10-19-v2/inventory.json binds eight supplied/readback
files (four byte-exact, four declared sanitized projections; 268533 bytes).
The original agent note came from the root worktree; this task-worktree note
remains the canonical current record. Earlier histories were not overwritten.

P44-CREDENTIAL-01 is DECIDED, configuration blocker resolved:

- The actual provisioning source was the protected project input
  app/bluetooth_flutter_Trace/cloudflare/update-service/.github-actions-secrets.staging.local.json,
  not token.txt or p41-ci-token.txt. In-memory comparisons and current verify
  metadata establish different values and a different management ID from the
  previously denied local token, on the same approved account. Its management
  ID SHA-256 is ec3e3b40801a2af2676d699686429cc49d1fea95afb328d8efb9ac519b31d666.
  Later removal of temporary management authority must address this source,
  not the old local token or e-track-ci. No management token was exported to CI.
- The current account directory contains exactly the original Track and the
  two new active tokens. Each new token has exactly one allow policy, one
  account_default_bucket resource with value "*", exactly Bucket Item Read
  and Bucket Item Write, and no conditions or Worker/D1/management grants.
  Production and rehearsal keys differ; each matches its four protected
  input files and its own approved bucket. Cloudflare's Item Write includes
  delete capability; the application does not issue DELETE.
- Both S3 names are present in firmware-production and both prefixed names in
  firmware-rehearsal. Secret metadata proves presence, not the stored values;
  the new-chain workflow must still prove actual consumption. Existing
  reviewer settings and all three false gates are unchanged. Remote main was
  0779f677507fa2c8a88c1799c8d2909bbae5a0a0 at the independent readback.
- The claimed private ACL was initially inherited too broadly. Root removed
  inheritance and retained only the current user's explicit access on the
  private directory, its five files and the newly consumed source input.
  credential-protection-01.json records all seven repairs and unchanged bytes.
  This establishes an exposure window, not proof of another reader or a claim
  of never being exposed. No automatic recreation/rotation was performed.
- The supplied machine result records two creation HTTP 200 and two actual
  SigV4 ListObjectsV2 HTTP 200. It lacks raw response bodies and historical gh
  set/list receipts; no raw receipt for the reported initial 400 was supplied.
  The earlier final-create-probe-01 403 is not that 400. Current readback closes
  current scope/presence questions, not these historical capture gaps.
- create_s3_02.py is retained as an executed, non-reentrant historical input.
  Its incomplete scope assertion and deferred private save are disclosed; do
  not rerun it. Root's fail-closed current checks determine the actual policy.
  An initial offline archive attempt rejected an empty redaction sentinel
  before writing; excluding empty sentinels fixed that archive-only failure.
- Independent preparation review then found the original Track token ID was
  still visible in the first projection and had entered a child's tool output.
  No token value or S3 secret was printed. The v2 projection additionally masks
  all token directory IDs, without masking permission-group IDs. The complete
  first candidate projection (ten files including inventory/attributes) was
  moved byte-exact to .cache/p44/credential-handoff-projection-01/ inside this
  worktree, not committed or deleted. Original provisioning/readback inputs
  remain unchanged; identifier redaction is not a reason to rotate credentials.

### Lifecycle Decision Under Existing Owner Delegation

Both provider metadata records have expires_on=null and not_before=null. The
older proposed 90-day provider expiry was NOT applied. Root accepts these
exact already-created pairs for the bounded configuration/rehearsal stage,
not an indefinite unattended production grant. O1 / Eitan-S-23 retains secret
ownership, with operator-enforced rotation/review no later than
2027-01-17T07:40:38Z (production) and 2027-01-17T07:40:50Z (rehearsal).
This is a recorded operating deadline, not a configured Cloudflare TTL or an
automatic scheduled job. Before P5 production promotion, recheck active scope,
age and ownership. No extra owner choice is needed for this bounded decision.

Rotate one environment at a time: create a replacement with the same exact
bucket/two-group policy, install both fields through the protected environment
secret route, verify new scope and an authorized new run, then revoke the old
token by its verified management identity. A changed pair invalidates affected
runtime evidence; old success does not validate its replacement. Emergency
revocation disables the identified token and leaves gate=false; preserve
evidence and firmware objects. Do not use asset deletion, wider scope or old
P4-1 proxy approval as recovery. Existing AES and deploy/HMAC lifecycle rules
in the configuration matrix remain unchanged.

### Minimal Formal Preparation

No new formal observation has occurred. The independent evaluator and thin
capture adapter are preparation work, using the existing byte evaluator,
standard AWS SigV4 implementation and bounded HTTP transport. The old campaign
has fixed P4-1 branch/version/history and a proxy-approval path; the old cloud
collector omits production and uses Schannel with unresolved external-cache
attribution. Therefore a small data-capture adapter is necessary, not a new
release protocol. It must have no approval/rejection API or business-write
interface, except the two explicitly planned shared-workflow dispatches.
Offline mocks qualify the adapter before its source/profile commit and freeze.

Root continues with the existing consolidated formal plan. Actual reviewer
actions, new-chain upload/register/readback and unchanged-resource snapshots
remain to be observed. Production publication, devices and gate unlocking are
out of scope; P4-4 is IN_PROGRESS, not PASS.

### Concentrated Formal Tooling Review

This is one preparation/remediation batch, not another product review round or
an independent P4-4 PASS. Root authored the thin capture/sealing adapter; the
two bounded children authored the offline evaluators, and the credential
reviewer independently checked deployment coverage and bundle dependencies.
No P4-1/P4-2 product implementation changed in this batch.

| ID | Finding and bounded disposition | Verification / owner |
| --- | --- | --- |
| P44-RUNNER-01 | Completed transport is mandatory even if an HTTP 200 partial body already parses; absent markers retain old-original compatibility, non-boolean markers fail. Fixed. | Offline evaluator 85/85; original stdout/result in selftest-03. |
| P44-CAPTURE-01 | Separate mutation intent and HTTP reservation; persist partial response identity, redact known values in bodies/headers/requests, require actual pending state and real owner action before B. Fixed. | Capture mocks use installed standard SigV4; no cloud operation or filesystem fixture output. |
| P44-CAPTURE-02 | Bind the exact staging registration and monotonic candidate, resolve an existing bare/annotated target tag, consume observed.metadata, capture full Actions logs, and reject already-complete recovery before GET. Fixed. | Capture 115 assertions; existing 3.2.8 JSON fixture plus baseline/legacy negatives and zero-request recovery guards. |
| P44-BUNDLE-01 | Known-value scans alone miss a new Actions installation token. Added ghs_/other GitHub token shapes without claiming arbitrary-secret detection. | Five positive/negative privacy checks, including ghs_ fixture. |
| P44-BUNDLE-02 | State interpretation consumes release identities; parser-fed readbacks must declare Evidence. Fixed minimal dependencies; raw A/B remains in exact P44Capture profile. | Schema/dependency negative passes; parser edits do not grant new dispatches. |
| P44-BUNDLE-03 | Assess must not hash a still-growing log in its own evidence tree. Keep initial NOT_RUN and final matrices separate. | Execution constraint: assess/final-validator logs use the existing contained cache wrapper outside DATA. |
| P44-BUNDLE-04 | Frozen timeout text must describe actual limits, not a shorter unimplemented bound. Fixed. | Undici 60 seconds, standard gh archive 180 seconds, wrapper 60 minutes. |
| P44-BUNDLE-05 | Credential/CI evidence alone omitted the independently deployed module/version/binding originals. Fixed in this same batch. | Original evaluator 90/90, including 21 deployment cases; root-review inventory plus 16 selected originals retain failure history without repeated deployment. |
| P44-BUNDLE-06 | Generated offline commands used relative --repo-root although originals CLI requires an absolute task root. Fixed before freeze. | All five generated offline commands bind the exact absolute ROOT; schema selftest passes. |
| P44-TOOLS-INTERFACE-01 | The deployment inventory uses entries, unlike the two existing files inventories. Fixed the shared selection helper before any prepare copy. | Positive checks for both schemas and rejection of a missing selected original; preserve the inventory bytes. |

The raw deployment subset preserves public and original digests separately:
email/cookie projections must not be presented as byte-exact responses. The
selected CI ZIP and both original multipart bodies, not reported module hashes
alone, bind the accepted source. Historical configuration observations do not
claim continuous state monitoring; formal before/after isolation is still due.

The plan has 17 formal commands and nine criteria. Source and all new runners
must be committed first. Preparation then binds reviewed 3.2.9 to that exact C,
retaining the already-verified 3.2.7 bootstrap bytes; it does not substitute the
current staging 3.2.8 registration as bootstrap. Only the exact rehearsal branch
policy and descriptor/hash may change. All three gates, existing reviewers,
production main-only policy and production prevent_self_review remain intact.

Remote pre-delivery readback still reports task HEAD
231932fdd554af1504c1465117d1470cf4a0dc22 and main
0779f677507fa2c8a88c1799c8d2909bbae5a0a0. The task branch must not advance between
the two same-input runs. A must reach waiting and be personally rejected by
Eitan-S-23; only then may B be dispatched and personally approved. Root records
the actual owner response or genuinely witnessed action, not just the API login.
No extra check_bindings run, old proxy approval, production firmware publish,
channel mutation, R2 object write outside rehearsal, or device action is granted.

Development stdout/results and source hashes are sealed separately under
P4-4-acceptance-preparation-2026-10-19/. Earlier successful checks and failures
remain visible; only changed tools are retested. The original-evaluator's early
BOM/multiline parsing failures exist in tool receipts 02e541 and 172087 and were
not repaired by repeating the original CI. Existing compiler warnings and 11
dependency advisories remain disclosed.

Final development results are evaluator 85/85, original/deployment evaluator
90/90, capture 115 assertions, three targeted board/profile/S3-contract checks,
and the bundle schema/dependency/privacy/absolute-root/inventory checks (17
commands, nine criteria). The final original-evaluator stdout is
.cache/p44-original-tests-20261019/bundle05-originals-tests-02.log, SHA-256
3fa15ce240a1ca282a2adf6ff57d722d15157a4ecbe5c05691819654ec2877ff.
These are development observations, not the pending formal P4-4 results.

Git delivery uses this exclusive task index only. The reviewed CLI console
output needs the scoped GIT_NO_DEBUG_CHECK=1 hook exception; the secret check
stays enabled, an explicit commit message avoids AI hook generation, and the
contained environment disables webhook notifications. The shared root index
SHA-256 before delivery is
2907ee569cb8415877c8c688b3e09b5948a789d6430796eab99ae3ad43f3a3dd;
it is not part of staging. Private inputs, the first identifier-leaking archive,
and generated fixture trees remain untracked/ignored. No external cache cleanup
is authorized; earlier PowerShell/Cryptnet attribution remains unresolved.

P44-DELIVERY-01: the first staged-byte audit failed because Git had normalized
CRLF in twelve credential-resume HTTP header files before that directory gained
its byte-preserving attributes. The worktree originals were unchanged. Root
added a directory-local `* -text` rule and reapplied the reviewed worktree bytes
to this task's index with scoped `git add --renormalize`; no original was edited.
The failed receipt remains `.cache/p44/logs/p44-index-bytes-01.json` and its log.
Unscoped diff whitespace checking also flags original CRLF, empty HTTP header
values and terminating blank lines in the archives. These bytes are retained,
not reformatted; manual source/record whitespace checks are scoped separately.

## First Formal Admission

The scoped preparation commit was pushed as
08afb97ddae316b3b305354f1582afdb836d7633. The secret hook remained enabled and
passed; final staged privacy checked 64 files and 31 archive members. All 51
staged evidence files matched the original worktree bytes, and manual
source/record whitespace checks passed. Main remains outside this delivery.

The original plan is frozen as P4-4-v1 / P44-20261019-01, with 17 commands and
nine criteria. The unchanged contract's raw SHA-256 is
5EDFE3AA67DB573730F0D095A72E8EAD3F9E49E5D2457B2982480F8FC068BDB9.
Preparation copied 67 original files and bound version 3.2.9 to that exact C;
descriptor SHA-256 is
98e6a3d23d019b77732d2855366592008e25fd1441284473d1e8302e321be71d.
The exact rehearsal branch rule was added (HTTP 200), and the descriptor/hash
variables updated (two HTTP 204 responses), with original before/after reads.
The old rehearsal rule remains; production remains main-only, reviewers and
prevent_self_review are unchanged, and all three gates remain false. No secrets
were recreated/rewritten and neither Worker was redeployed.

P44-PREFLIGHT-01 is a retained HARNESS_FAIL at admission, not a product failure
or an extra formal round. The first NOT_RUN precheck rejected a lowercase
contract_sha256 because the stock validator loads the same digest in uppercase
and compares that field case-sensitively. Other evidence digest comparisons
normalize case. The digest value and frozen contract bytes were never different.
The independent reviewer approved the minimal metadata repair: retain the first
matrix and failed log/receipt byte-exact in
P4-4-v1/evidence/precheck-failures/hash-case-01/ with transfer.json, then change
only that field's hexadecimal case. No source/profile/criterion/contract was
changed and freeze/configure were not repeated.

The separately identified formal-precheck-02 passed the unchanged contract and
NOT_RUN matrix. The frozen capture adapter expects a fixed admission receipt
path, so commands/formal-precheck.json is a byte-exact compatibility copy of
the actual precheck-02 receipt: its internal label and log reference still name
formal-precheck-02. It is not a rewritten successful first attempt. resolution.json
binds this copy, the actual passed receipt and the metadata-only repair.
The validator's case inconsistency is recorded, not patched during this freeze.

The first two formal offline commands completed successfully: formal-history
independently evaluated the original implementation/CI evidence against C;
formal-configuration evaluated the credential originals plus actual deployed
modules/versions/bindings. Their result SHA-256 values are respectively
b6e5f0f6bf73628c438fc0dab930796652e888facd01d62e21e980c820dbb914
and 0a31bc61cd9baab434cf49fc3614bfe3569c0a87f1c489fbaa0593376aabdef0.
This does not make the remaining criteria or P4-4 PASS. Snapshot capture and
the planned real reviewer observations follow; source C must remain fixed.

### P44-SNAPSHOT-01: Bounded Large-Page Failure

The first formal-before ended with exit 1 before any dispatch. Its protected
Trace channel_history page received HTTP 200 but did not complete within the
60-second transport budget: content-length 9631314, received 4214365 bytes,
65 rows from the prior count, elapsed 63453 ms, error_code 23. The retained
partial body is not valid complete JSON. It remains completed=false and is
not admissible merely because the HTTP status is 200. Thirty-one preceding
complete HTTP responses remain intact; they are not discarded or automatically
retried. The actual failing request and complete original command receipt are
under P4-4-v1/evidence/snapshots/before/ and evidence/commands/formal-before.*.

This is an environment-stage response-stream failure, not evidence of a token
permission problem or a product publication failure. The fixed 500-row SELECT
page was too large for the observed transport/time budget. Root retains that
failed page and the 60-second limit; the successor collector will fetch new row
pages of eight rows, with distinct labels, rather than retrying the same 9.6 MB
body or silently accepting a truncated response.

V1-MATRIX-STATUS: RAW-STATE also requires negatives and after, neither of which
was executed. The stock validator requires all commands of a PASS/FAIL
criterion, so the honest aggregate disposition is NOT_OBSERVED with the actual
formal-before exit 1 and environmental failure retained in notes/evidence;
overall is EVIDENCE_GAP, not a fabricated set of failed or executed downstream
commands. This is still the actual first attempted formal round. The next
contract must cite it and its final matrix, not restart the history at v2.

Before changing profile sources, root is sealing v1 with its real completed
history/configuration results and a bounded final privacy scan. Only after that
bundle and its separate index commit may v2 source edits begin. V2 will import
the hash-bound old collector/source/failed-round provenance, independently
consume complete matching readonly originals, and fetch only failed or missing
data using fixed LIMIT 8. Existing successful LIMIT 500 pages remain original;
the evaluator must verify each page's actual limit, contiguous offset and exact
row count. After-state is entirely fresh. No incomplete page can become a reused
success, and no mutation uses the readonly reuse mechanism.

There have still been zero A/B dispatches, firmware publications, registrations,
R2 object writes or device operations in this formal attempt. The same legitimate
3.2.9 version remains selected; it is not raised to bypass a conflict. A successor
source/descriptor binding will be explicit. The two planned reviewer-controlled
runs remain unspent; gate=false and all existing approvals are preserved.

V1 is now closed as EVIDENCE_GAP. HISTORY, CONFIGURATION and HYGIENE have actual
EXECUTED PASS results; six aggregate criteria remain NOT_OBSERVED. The four
recorded command exits are history=0, configuration=0, before=1, privacy=0.
Privacy scanned 291 files and five ZIP members with 34 known-sensitive forms,
zero matches and the recorded lifecycle decision. No downstream observation
was invented to satisfy a grouped criterion.

The final matrix binds 295 evidence files and has SHA-256
021346d79cf0e01848c09acc33a7d5854400b2ddb82ba10e1addf0df049dca0e.
The stock physical validator completed successfully with overall=EVIDENCE_GAP,
not overall=PASS; original output is .cache/p44/logs/p44-v1-final-check-01.log
(SHA-256 8eff8e922cf9cb95f7d6da908a11fcdc52149836ede3f1ee898e9dbcf6c17b61).
The failure-report.json, initial NOT_RUN matrix, failed precheck and incomplete
HTTP body remain unchanged. Root will deliver this failed bundle and a separate
index commit before releasing the bounded v2 source changes.

### V1 Delivery And Bounded V2 Continuation

The failed V1 bundle was committed as
e5994fb28466e46c99a1f247494473e6cba9cc03 (B1), then indexed by the separate
9ca520de2c2e3ec9f915feac0ab389db4e86dd21 (I1). Both are pushed only to
dev/p4-4/config-integration-20261018. The staged-byte audit checked 299 files,
including all 295 matrix-bound evidence files, with no profile input staged.
The two commits change no Tools/tests/product/workflow source. The shared root
index remains SHA-256
2907ee569cb8415877c8c688b3e09b5948a789d6430796eab99ae3ad43f3a3dd.
The stock freeze-index reachability and readiness/board checks passed (2 tests;
.cache/p44/logs/p44-v1-index-check-01.log). This verifies bundle delivery,
not the unobserved P4-4 criteria.

Only after B1/I1 delivery did root release the bounded V2 source batch. Its
predecessor provenance must name B1 as source_bundle_commit, not the later
index commit. It retains the same 17 command IDs and nine criterion IDs,
the real V1 contract/final matrix, and a computed rerun plan. Complete exact
readonly responses may be imported with original timestamps; failed/partial
responses remain failures. New D1 row requests use LIMIT 8 with actual consumed
row offsets, never a replay of the failed LIMIT 500 page. Current GitHub
configuration and protected credential verification stay fresh, and all after
snapshots are fresh. No mutation participates in this reuse path.

The next source commit will precede the new target/descriptor binding and V2
freeze. Only the two approved descriptor/hash variables need a scoped update;
the already-added branch policy is checked, not created again. The source
branch must then remain unchanged between the actual rejected run A and the
separate approved run B. Both require personal actions by Eitan-S-23 with an
owner response or genuine root witness; no agent API action substitutes for
that provenance. The two observations remain unspent, and all three gates
remain false. No Worker redeployment, credential recreation, production
publication, Release mutation or device action is added by this continuation.

P44-V2-BIND-01 was found during the concentrated V2 review, before any V2
platform observation. The predecessor generator and actual V1 matrix carry
uppercase contract digests, while the first loader compared them to lowercase
hash output. The final loader validates the 64-hex shape before comparing
normalized values; the archived V1 bytes are not changed. The same batch
restricts configure to an intact approved C1 descriptor/hash pair, or the
complete C2 pair with zero PATCH. Old P4-1 values and mixed pairs fail before
any mutation; the existing branch rule is required and never recreated.

Final development results are 156 capture assertions and 93 offline evaluator
tests with zero failures/errors/skips. The latter ran in 25.902 seconds. Its
test_capture_consumes_real_bundle_predecessor_plan case calls the actual
bundle.predecessor_plan, then loads the real B1 contract, final matrix and 32
HTTP originals through the Node loader: 31 complete responses are retained,
one incomplete response is not reused, original times stay intact, and wrong
or malformed digests remain rejected with zero network requests. The earlier
148-assertion synthetic run is retained and is not presented as proving this
real-input integration. The separate bundle selftest validates the stock
matrix interface, actual V1 originals and a 9-criterion/17-command plan preview;
that preview is not C2 formal admission.

The source hashes of all five capture/evaluator/test/README files match the
author's stable handoff (.cache/p44/logs/p44-v2-source-check-01.log). The final
capture stdout is p44-v2-capture-02.log, and evaluator originals are under
.cache/p44-runner-tests-20261019/selftest-v2-01/. Development originals are
appended under P4-4-acceptance-preparation-2026-10-19/v2/, leaving the first
archive unchanged. Whitespace checks passed; LF-to-CRLF notices are preserved.
The parser validates row offsets/counts but does not implement a second
predecessor provenance controller: the frozen collector's fixed entry points,
hash-bound predecessor manifest and real-input regression enforce old-only
LIMIT 500 reuse and fresh LIMIT 8 collection. No product, workflow, validator,
credential or frozen V1 file changed in this batch.

The independent originals reviewer inspected the stable diff and existing
selftest originals without rerunning them, and reported no unresolved blocker.
The appended development ZIP contains 20 byte-verified entries (20428 bytes).
The pre-delivery scan checked all 10 changed delivery files and 20 ZIP members
against known credentials/encodings and token shapes with zero matches. These
are preparation results, not a P4-4 PASS or proof of live LIMIT 8 collection.

### V2 Frozen Admission

C2 is 70193ce7fb7cc4e426029d07cf7b50c1fcbfef1c, pushed to the existing task
branch only. Its frozen tree is e97e9b44d4e06efc9133add82502a55241c9af55 and
profile configuration blob is 5ef97ae98674373c3cf641676c16ff7baf1b617f.
P4-4-v2.contract.json has SHA-256
cfff5e841b6fbe6f251a8a931c450907b477b678e890dcd6b00c2081e07d719a
and retains the actual V1 parent. The reviewed target remains 3.2.9; its C2
descriptor SHA-256 is
d2cf8f96c7551b9bd3e646f2bb8bd1eb6bb82fc8969023afaf32362a0fe7f893.

Preparation copied 67 original inputs plus 132 predecessor files. The only
platform writes were the two approved descriptor/hash variable PATCHes, both
completed HTTP 204. Readback confirms all three gates false; no branch rule
was created, secret replaced or Worker redeployed. Receipts are retained under
the V2 evidence configure-before/configure-after paths and the two top-level
configure-*.http.json files; helper stdout is in .cache/p44/logs/p44-v2-*.log.

The actual formal-precheck returned VALIDATION=PASS, overall=NOT_RUN for round
P44-20261019-02. Both it and the real rerun-plan command supplied the V1 contract
and final matrix. The generated plan names nine affected criteria and the
existing 17 command IDs, with zero reusable criteria. The before collector's
old-response adoption is independent original-evidence evaluation, not reuse
of the failed V1 RAW-STATE criterion. Plan generation reports
FINAL_VALIDATION=NOT_RUN and is not final acceptance.

The admitted history and configuration commands independently passed against
the retained originals, without rerunning CI or deployment. Their output
hashes are a5883f8cd2cb01b3cca0a31b20829f01bea23de4b5e9b6c0bf523314ec63b6da
and 192e193e8e7a42150d43ea6dcbd35cec1291e9f7e4a827938e5b48c3b33380a0.
Root then started the single planned before snapshot with the frozen
predecessor fixture. A/B remain undispatched pending its actual completion and
the required negative probes. P4-4 remains IN_PROGRESS, not PASS.

### P44-SNAPSHOT-01: V2 Byte-Size Correction

V2 before stopped with a closed exit 1 at channel_history rows8 OFFSET 32.
Its HTTP 200 response declared 4746278 bytes; only 1441765 bytes arrived in
64684 ms. The original is completed=false with error_code=23, not a permission
denial or complete JSON. The preceding four new pages (offsets 0/8/16/24)
completed with 19398/91934/7016/1264686 bytes. They and the 31 complete V1
responses remain valid originals; neither partial response is a successful page.

The earlier row-count repair did not bound response bytes. Independent offline
inspection found no complete row in the V2 partial: it stops within row 32's
before_json. The retained V1 partial already contains that field's closed
1740978-byte serialized string and an incomplete after_json of at least
1091442 bytes; the row's serialized lower bound is 2832753 bytes. Therefore
LIMIT 1 is not an evidenced size guarantee. This is a collection/data-size
issue, not proof of a product publication failure or a need for new credentials.

Standard in-memory gzip of the four complete pages produced
1775/3250/1058/26973 bytes. The V2 partial compresses to 29319 bytes and the V1
partial to 87797 bytes; these are partial-only diagnostics, not complete result
sizes. A separate single unauthenticated GET of the public Cloudflare /ips API
with Accept-Encoding: gzip returned HTTP 200/gzip, 277 wire bytes and 505 decoded
bytes. Its originals are .cache/p44/diagnostics/gzip-public-api-01.{body,json};
this proves that API host can negotiate gzip, not that the D1 capture passed.

Root's bounded successor direction retains Undici request/ProxyAgent, TLS,
LIMIT 8 and the same 60-second deadline. Only D1 SELECT requests negotiate
gzip; standard strict zlib decoding and separate 16 MiB wire/decoded limits
must preserve original headers/wire bytes and a hash-bound decoded derivative.
The offline evaluator must strictly recompute decoding. Truncation, CRC faults,
unsupported encoding and size overflow fail; decoded bytes must be included in
the sensitive-value scan. Unsafe-to-decode failed wire is privately retained,
not blindly published. The existing .cache/p44/private ACL was read back as
current-user-only (inheritable full control), without changing it. No generic
SQL fragmentation controller, permissive fetch decompression, larger timeout,
credential change or repeat of a complete page is authorized by this decision.

V2 is closed as EVIDENCE_GAP: HISTORY/CONFIGURATION/HYGIENE PASS, six other
criteria NOT_OBSERVED; actual command exits are 0/0/1/0. Privacy checked 307
files, five ZIP members and 34 known-sensitive forms with zero matches. The
final matrix binds 312 evidence files and has SHA-256
c335006f0b166535ce957c345adf579440e087b6b980239baca96500f019a46c.
Standard final validation included the actual V1 predecessor and returned
VALIDATION=PASS, overall=EVIDENCE_GAP; log
.cache/p44/logs/p44-v2-final-check-01.log has SHA-256
efbad04c92c567e104a055ac5218242db8f03dde0a480041fbc60922ac6240a3.
The rerun plan remains
8587c8b637c5d0acc725eb2bb118e6ed1080f6528d9cfc4dd36d578e6cc2b67f.

Source edits remain held until root commits the V2 failure bundle and its
separate index. V3 must directly bind V2/C2/B2, then the retained V2 manifest's
V1/C1/B1 ancestry. It must consume the 35 complete observations without network
replay and retain both failed originals. The planned rejection/approval runs
remain unspent; no production publication, registration, R2 write or device
operation occurred. P4-4 is not PASS and all gates remain false.

V2 was then delivered as bundle B2
84268ac2ad34727b76250ff944211b7efba1cfb3 and the separate index commit I2
5b6b5a02ebe56dfa9981e49697c3055d69670967, both on the task branch only. The
staged-byte audit verified 316 staged files and all 312 bound evidence files,
with no profile source staged. Freeze-index reachability and board/readiness
checks passed again for this new index row (2 tests, 19.046 seconds). Only after
those commits were delivered did root release the bounded V3 source changes;
source_bundle_commit refers to B2, not I2. Existing product, credentials,
Workers, reviewer authority and the unspent A/B observations are unchanged.

### Concentrated V3 Collector Review

P44-SNAPSHOT-01 is DECIDED as a bounded collector repair, not a product or
credential change. The stable batch uses standard strict gzip only for the
fixed D1 SELECT POSTs, retaining the same 60-second request/pipeline signal,
LIMIT 8 and independent 16-MiB wire/decoded limits. Original wire and headers
remain distinct from the verified decoded derivative. The actual staging
admission caller now consumes that verified representation; S3 object bytes
and the release/authentication paths retain their previous semantics.

Root and the independent originals reviewer completed one consolidated review
of capture, parsing, privacy, predecessor provenance, configuration and their
actual callers. No unresolved blocking finding remains in this source batch.
The private failure destination was rechecked before delivery: all existing
parents passed the reparse guard and .cache/p44/private has only the current
user's inheritable full-control ACL. The formal V3 failure namespace does not
yet exist. Tests use an in-memory private sink; they did not write a formal
private capture or invoke Cloudflare.

The final development results are 199 Node capture assertions and 105 Python
tests, with zero failures/errors/skips. The Python suite took 29.202 seconds.
Its actual bundle.predecessor_plan -> Node loader case consumed the real B2
inputs: 37 HTTP originals, 35 complete and two incomplete, with zero network
requests. Wrong/malformed digests remain rejected. The same batch exercises
CRC/EOF/encoding/length/size failures, the real staging caller and a correctly
hashed but substituted decoded sidecar. The bundle selftest checks the actual
V2 physical evidence, five compressed-privacy cases and the 17-command /
nine-criterion preview; none of these is a live D1 observation or formal PASS.

The Node test used exclusive command redirection rather than formal run.cjs.
Its receipt explicitly transcribes the actual tool completion (exit 0,
6.519 seconds, no remaining session), binds the original log and leaves the
uncollected wall-clock start/end null. It was not rerun to manufacture a
different receipt. The independent reviewer and root each recomputed the five
author-owned source hashes. Root's original review is retained as
.cache/p44/logs/p44-v3-root-review-01.{log,json}; V1/V2 bundles, the stock
validator, profile configuration, workflow/product paths and shared root index
were unchanged.

The existing preparation archive now has a separate v3/development.zip and
inventory under P4-4-acceptance-preparation-2026-10-19/. Its 25 entries (29542
ZIP bytes) were individually compared with their originals. It includes both
bundle selftests, the final capture receipt/log, source audit, Python output
and result, the three actual B2 integration originals, the independent root
review and the earlier public gzip probe. Generated fixture trees remain in
ignored cache; no historical archive or failure was rewritten. Current source
hashes are declared without retroactively rebinding earlier tests.

Next, root delivers C3 before preparing a target or freezing V3. The real V2
contract/final matrix remain mandatory for the NOT_RUN precheck, rerun plan
and final physical validation. Thirty-five complete observations must not be
replayed; only missing before-state reads resume with the changed transport.
Only the existing rehearsal descriptor/hash pair may be updated for C3. Both
planned runs remain unspent and require personal reviewer actions in order:
Reject A, then Approve a distinct B on identical source and inputs. Production
publication, gate unlock, device work and main integration remain outside this
execution plan. Earlier external-cache attribution remains unresolved.

### V3 Admission And Original Results

C3 is ba952497948a03c40cbd8baebbfc9228621fb44b, pushed only to the task branch.
All ten staged blobs matched their reviewed bytes; the 25 archive members and
all staged files passed the known-value/token-shape privacy scan. The frozen
tree is 5427f4728cfc0e6a3b4760548fb6e03385922c6b and the contract SHA-256 is
4fc05662f1bb9ca829bb8e769754229f6bebc41cbb99a3ed38099db1e5d7e2cd.
Target 3.2.9 has descriptor SHA-256
81904c875eb58cd241dde54d11f7e48e0722d11491a3cdd3f0208a55b432423b.

Preparation copied 67 original inputs and 158 predecessor files. Configuration
returned 22 complete responses, including exactly two descriptor/hash PATCHes
with HTTP 204. All three gates remained false. The actual formal-precheck
passed with overall=NOT_RUN; the separate plan used the actual V2 contract and
final matrix and reported nine criteria, 17 commands and zero REUSED criteria.
History/configuration independently passed on original bytes, not new CI or
Worker deployments.

P44-SNAPSHOT-01's gzip remedy now has real D1 evidence. The formerly failing
channel_history OFFSET 32 page completed at 90146 wire / 4746278 decoded bytes;
OFFSET 40 completed at 64997 / 3488749 bytes. All five remaining channel-history
pages and seven following SELECT responses completed with strictly verified
wire/decoded pairs and zero reported database writes. Those 12 new responses,
the 35 earlier complete responses and their original timestamps remain intact.

### P44-SNAPSHOT-02: Pre-Response Connection Reset

The same formal-before then stopped at protected-patches-rows8-0. Its original
reservation/request/envelope records 2026-10-19T15:27:27.071Z through
15:27:34.158Z, ECONNRESET and completed=false, with no observed HTTP status,
headers or body. Elapsed envelope time was 7087 ms, not a 60-second truncation.
The command closed with exit 1 at 15:27:35.620Z. This is a separate transport
failure, not evidence of bad credentials, gzip corruption or a product release
failure. No second attempt or A/B dispatch was made.

V3 is closed honestly as EVIDENCE_GAP. HISTORY/CONFIGURATION/HYGIENE passed;
six aggregate criteria remain NOT_OBSERVED. Actual command exits are
history=0, configuration=0, before=1 and privacy=0. The formal privacy scan
covered 377 then-present files, five ZIP members and all 12 decoded D1 bodies.
Later generated sealing metadata and final matrices are also checked by the
scoped staged-byte privacy audit; the completed formal scan is not replayed.
The frozen sources, initial matrix and all previous originals were preserved.

The final matrix SHA-256 is
41c328859fe3289567ffff409375766148d826d76f79918cf34ed14740413895 and it binds
384 evidence files. Actual standard validation, with the V2 predecessor
arguments, returned VALIDATION=PASS, overall=EVIDENCE_GAP in
.cache/p44/logs/p44-v3-final-check-01.log. This validates the failed bundle,
not P4-4. The one-off sealer source and precise failure report are retained
inside the bundle; no product observation was repeated for packaging.

Root is reviewing the installed Undici retry/observer APIs before extending
the thin adapter. The proposed scope is one additional pre-header ECONNRESET
attempt for explicitly allowed read-only captures, within the same 60-second
signal and size limits. It must retain every failure, never retry a mutation,
completed/header-bearing response or permission denial, and preserve all 47
complete observations and all three failures. Gzip predecessor sidecars and
actual Windows path handling are part of the same review. Sources remain held
until V3 bundle/index delivery; no retry policy has yet been executed or frozen.
Gate=false, reviewer ownership and the unspent A/B plan remain unchanged.

### V3 Delivery And V4 Source Release (2026-10-20)

V3 bundle B3 is 20febda2ac2e05e5f4b761a9f365091b177516b6. The separate index
commit I3 is 738b2badb861ae3d3902bffa5bec2fe830707beb. Both are pushed only to
the task branch. The final staged audit verified all 389 blobs byte-exact,
all 384 bound evidence files and five ZIP members, with no known credential
match. This includes the sealing metadata generated after formal privacy.
The root index still has its recorded unchanged SHA-256. Index reachability
and board/readiness checks passed (two tests, 18.465 seconds).

Only after this delivery did root release the next bounded source batch.
The source_bundle_commit input must name B3, not I3. The successor preserves
the actual V3 parent, 47 complete observations, three failures and the same
17 command/nine criterion identities. Its local-date round is planned as
P44-20261020-04; that date does not restart lineage or action accounting.

The installed Undici API was inspected before choosing the repair. RetryAgent
defaults to five retries and supports post-header Range recovery; matching the
required scope would need additional observers and policy overrides. The
smaller selected route retains request() and adds a single conditional retry
only around its pre-response rejection. After final headers, the native API
resolves the request and sends later errors to the body stream; responseBytes
therefore stays outside this retry boundary. Native onInfo marks informational
responses, which also prevent retry. No new controller, package or deprecated
observer dependency is needed.

Only already-admitted capture GETs and fixed D1 SELECT POSTs may receive one
additional pre-response ECONNRESET attempt. Both requests, the abortable
500-ms delay and decoding share the original 60-second signal. The first
failure must be exclusive-written and hash-bound before any second attempt;
failure to retain it or cancellation prevents retry. Mutations, other POSTs,
private verification, other error codes and every received HTTP response or
body failure remain single-attempt. All previous unsuccessful attempts remain
failures even if the new bounded read eventually succeeds.

The same batch includes gzip predecessor body/request/decoded references and
strict byte comparison, plus privacy Context selection for each bound source
root. Only the new fixture root changes to p: existing manifest bytes and
relative paths remain unchanged. This lowers the longest planned inherited
path from 263 to 239 characters. The existing 237-character path was checked
read-only; a real contained Windows fixture must still validate the new path
shape before admission. These are development obligations, not newly observed
product results. No new formal command, platform configuration or approval
action is authorized until the stable batch is reviewed and frozen.

### Concentrated V4 Collector Review

The bounded P44-SNAPSHOT-02 development batch is now stable. The final Node
run passed 246 assertions; the Python run passed 106 tests with zero failures,
errors or skips, from 2026-10-19T18:33:19.065131Z through
2026-10-19T18:33:53.238280Z. Both actual processes closed with exit 0. The
real B3-plan-to-Node-loader integration consumed 47 complete observations,
retained all three failures and checked 12 inherited gzip representations,
with zero network requests. Hash, matrix, sidecar and malformed-input negatives
remain strict. The actual 239-character Windows file was read through both
Python File references and the Node guard, with identical bytes and SHA-256;
the existing fixture was not copied again.

The first two Node attempts and the diagnostic attempt remain failed originals.
They exposed test-only Undici adapter mismatches: MockAgent closes through
close(), while the real ProxyAgent implements destroy(); a string body matcher
also cannot equal the actual Buffer request. The final test uses a public
Dispatcher delegating to disabled-network MockAgent dispatch/close and an exact
byte predicate. Production cleanup, Buffer request identity, permissions and
the bounded retry policy were not weakened to make these tests pass. Their
post-execution receipts identify the actual tool completion; uncollected process
times remain null. No successful test was repeated just to obtain a receipt.

Root independently recomputed all six source hashes and ten author-artifact
hashes, checked the actual successful receipts, and verified the unchanged root
index. The original result is .cache/p44/logs/p44-v4-root-review-01.{log,json}.
The separate successful bundle selftest retains its own earlier source/time;
it was not rerun. Existing product CI, deployments, credentials and the three
previous frozen bundles remain unchanged. LF-to-CRLF Git notices are retained,
not hidden as zero warnings.

The v4 development archive contains 31 byte-verified original members in 37173
ZIP bytes, including all failed/final Node outputs, Python caller/path results,
source/receipt audits, the root review and the actual V3 final-validator and
index-check outputs. Its inventory is under
P4-4-acceptance-preparation-2026-10-19/v4/. Generated fixtures remain in ignored
cache. These development results do not constitute live read recovery or P4-4
PASS. The next source commit precedes target preparation, the two rehearsal
descriptor/hash changes, freeze and real V3-bound precheck/rerun-plan execution.
Runs A/B remain unspent; gates stay false, and the earlier external-cache
attribution remains unresolved.

Independent p44_originals_evaluator then adjudicated this exact six-file batch
REVIEW PASS with no unresolved required finding. It independently recomputed
the stable source hashes and reviewed the actual Node/Python completion receipts,
retry exclusions/audit ordering, all three predecessor generations, privacy
boundaries and real Windows File-reference result. That review was read-only:
no test replay, network request or platform action. Root's pre-delivery privacy
scan checked the nine changed/new files and all 31 archive members with no
known-value or token-shape match. This closes source review only; the real
NOT_RUN precheck, V3-bound rerun plan and missing runtime observations remain
required after C4 is committed.

### V4 Admission And Runtime Observation

C4 is 2756ca95e26ec636216313271708b3304d61a5cc, pushed to the task branch only.
All nine staged files matched their reviewed bytes and passed the staged privacy
scan. Its tree is 77549b4b756f1e88de8b854b4673857021a65783, with unchanged
profile blob 5ef97ae98674373c3cf641676c16ff7baf1b617f. V4 contract SHA-256 is
86764fa47b8c52d748bf93b83c5735352ceab69519d8ffcc4c6bfc706f8939b5.

Preparation copied 67 original inputs and 227 predecessor files. Target 3.2.9
is bound to C4 and descriptor SHA-256
d08b8b36f2b0dab9066491ccbd4e2c98109c5b15cbd0e7b839922d5254fd373b.
Configuration retained 22 complete responses and exactly two single-attempt
descriptor/hash PATCHes returning 204. Production/rehearsal/repository gates
were all read back as false; reviewer, secrets and Worker deployment were not
changed. The private parent ACL still grants only the current user inheritable
full control, and the controlled output paths passed the reparse guard.

The actual NOT_RUN precheck passed. The separately executed rerun-plan command
uses the real V3 contract/final matrix and admits the same 17 commands and nine
criteria, with zero REUSED criteria. Its plan-only result is not final validation.
Formal history and configuration independently passed on the retained originals,
without repeating CI or deployment. The one admitted formal-before invocation
then completed with exit 0: all three D1/R2 roles, an empty GitHub Release list,
47 unchanged complete predecessor observations and all three historical failures
were retained. It added 64 complete before responses, with no new incomplete
response. The previously interrupted patches page returned 200 on its first
attempt; this does not retroactively establish the source of V3's connection
reset or imply that a retry was needed for that page.

Formal negatives also completed with exit 0. Three missing/cross-Worker
authentication probes returned 401/TOKEN_INVALID, and both cross-bucket S3
listings returned 403/AccessDenied. All five were complete single-attempt
responses; none was a registration, upload or production mutation. Only after
these results did root start the admitted A dispatch command, including its
fresh environment/branch/gate checks. B remains unspent; A must reach an
observed waiting state before requesting the real reviewer's Reject action.

### A Waiting: Required Human Rejection

The one A dispatch is now run 39313672925, attempt 1, on C4
2756ca95e26ec636216313271708b3304d61a5cc:
https://github.com/Eitan-S-23/E-Track/actions/runs/39313672925

Original run/pending-deployment responses in run-a/waiting.json show status
waiting and exactly firmware-rehearsal, environment ID 24458272742. The waiting
run response ended at 2026-10-19T19:47:34.537Z. The capture process closed with
exit 0; root independently checked the original run ID, attempt, source,
environment and closed receipt without another request. Its result is
.cache/p44/logs/p44-v4-waiting-review-01.{log,json}. The root index remains
unchanged. A is consumed once; B has not been dispatched.

Next owner is the existing human reviewer Eitan-S-23: personally select Review
deployments, firmware-rehearsal, then Reject and confirm that human action in
the main conversation. Cancel, Rerun, Approve and an agent acting through the
same account are not substitutes. No rejection or owner attestation is claimed
yet. After the actual rejection is captured, root may continue with distinct B
under the unchanged source/inputs; B requires its own personal Approve action.
No branch advancement, extra check_bindings run, production firmware release,
device action or gate unlock is authorized. P4-4 remains not PASS.

Selected writes in this resumed batch are the reviewed task-worktree sources,
task note, development archive, guarded local cache and V4 evidence, plus the
already-authorized task-branch Git metadata. No deletion or selected external
output was performed. This is not a machine-wide zero-write claim: the earlier
PowerShell/Cryptnet cache attribution remains unresolved and those paths were
not cleaned or modified by this batch.

On the next owner request to continue unfinished P4-4, root used the existing
read-only recover-a route with label resume-20261020-01. The preserved response
and run-a/recover-resume-20261020-01-result.json still report run 39313672925 as
waiting; the command closed with exit 0 and zero platform mutations. No run
was redispatched, no successful observation was repeated and B remains unspent.
The pending human Reject requirement is unchanged. This continuation request
is not an attestation that the reviewer personally performed that action.
Selected writes were limited to guarded task-local recovery evidence, cache
receipts and this note; prior outputs and frozen sources were not rewritten.

### A Rejection Observed; B Admission Started

The owner subsequently confirmed personally rejecting A in the root conversation.
The exact message is preserved as ASCII-escaped JSON in
evidence/owner-reject-a-response.json, explicitly labeled a root transcription
with no invented message timestamp. Its 982 bytes have SHA-256
16973493cb831c772ad6fc095be5600e515ae8914d6b20016f3532a655deabec.
reviewer-action-a.json binds that response to A, attempt 1 and the existing
reviewer; it does not substitute the response for a platform review event.

Formal finish-a completed with exit 0. The original GitHub run is completed /
failure, terminal update 2026-10-20T00:46:00Z, with exactly one rejected event
from Eitan-S-23 (204050265) for firmware-rehearsal (24458272742). Both nongated
development/build jobs succeeded. The rejected rehearsal has no executed steps,
and production/binding-qualification jobs were skipped. This failure conclusion
is the planned rejection result, not a failed release execution.

The original A log archive is run-a/logs.zip, 173214 bytes, SHA-256
fd4523eac301fb277809faebb8bddf74b599ee7103fc375b4d4fa80b6a90f7bf.
Root ran the existing rejectedAdmission oracle against these hash-bound originals
and the owner-response witness; it passed without a new platform request.
Its receipt is .cache/p44/logs/p44-v4-rejection-review-01.{log,json}.

Only then did root start formal-dispatch-b under unchanged C4 and identical
dispatch inputs. No A rerun, source advancement, gate change, production
publication or device operation occurred. The owner's question about repository
review permissions is answered by the existing Spec, line 61: repository code
review authority does not replace the required personal environment-reviewer
observation. The frozen B approval must still be performed by that reviewer;
all other currently authorized follow-up capture/evaluation remains root-owned.

### B Waiting: Required Human Approval

B is run 39351100037, attempt 1, on unchanged C4:
https://github.com/Eitan-S-23/E-Track/actions/runs/39351100037

The run and pending-deployment originals show waiting on firmware-rehearsal
(24458272742); the waiting run response ended at
2026-10-20T01:03:35.317Z. Formal-dispatch-b closed with exit 0. B was created
after A's terminal update, and their dispatch request bytes are identical,
SHA-256 b636165e193b6e9d9c7322138b55e2e3a68c2657fc901573b0b0d4ca0a57040b.
Root also verified A's actual ZIP bytes and the unchanged root index in
.cache/p44/logs/p44-v4-b-waiting-review-01.{log,json}. A and B have each been
dispatched once; neither may be rerun to substitute another observation.

The next necessary action is Eitan-S-23 personally selecting Review deployments,
firmware-rehearsal and Approve for B, then confirming that action in the root
conversation. No B approval, upload, registration or successful rehearsal is
claimed yet. After the actual approval, root continues terminal/log/artifact
capture, byte/readback/preflight checks, fresh after-state, independent
approval/isolation/privacy evaluation and final physical validation. Gate=false,
production/device restrictions and the pending main-integration boundary remain.

This turn's selected writes are only guarded task-local A/B evidence, two owner
witness files, cache receipts and this note. There was no source commit/push,
external selected output or deletion; earlier cache-attribution limits remain
unchanged. No owned capture process remains running at this handoff.

### B Success And V4 After-State Evidence Gap

The owner personally approved B and confirmed that action in this root
conversation. This supersedes the preceding waiting state, not its original
record. B 39351100037/1 completed successfully at 2026-10-20T01:13:20Z on
unchanged C4. The platform review original records approved by Eitan-S-23
(204050265), firmware-rehearsal (24458272742). A remains the distinct rejected
run 39313672925/1, terminal failure at 2026-10-20T00:46:00Z, with no executed
rehearsal steps. Both production jobs were skipped. Their dispatch bytes are
identical; neither workflow was rerun, and no approval was performed by an agent.

The independent byte evaluation of B passed, including protected-key GCC input,
full/patch/recovery bytes, the new S3/preflight chain, three immutable uploads,
full readbacks, ready registration and the required single idempotent replay.
Root's three additional independent S3 GET bodies matched the expected hashes
and sizes: 285646, 380 and 605080 bytes. Production's authenticated fixed
SELECT-only preflight also passed; this was not production workflow execution
or firmware publication. The actual B logs ZIP is 463831 bytes, SHA-256
5ee501c3b4bbdaed420ba9ecc53bfac8a991e06f4543569172b3aa34266d38ca.
The rehearsal ZIP is 4154078 bytes, SHA-256
5233b85d80d36e4e42249768f64f2abf25ee7dc7cebefa5a7997ec632a98f098,
artifact 12233374226. Independent review checked archive CRC/hashes, raw run
identities, reviewer events/owner provenance, chronology and skipped production.
The two root-transcribed owner responses remain labelled as transcriptions with
unknown original message timestamps; they are not platform exports.

Formal-after then retained 31 complete original responses before the protected
audit_logs page at LIMIT 8 OFFSET 16 failed with UND_ERR_CONNECT_TIMEOUT. Its
single request ran 2026-10-20T01:38:31.684Z..01:38:42.184Z (10500 ms); the
envelope ran 01:38:30.236Z..01:38:44.107Z (13871 ms). No informational/final
HTTP headers or body were received, no retry was made, and the command closed
at 01:38:45.696Z with exit 1. The failed envelope SHA-256 is
d3e047b1375d4399b505ec4c9adcfc559d8e845b3642364562223af8470452c5.
This is not a credential denial, proven D1 error or gzip failure. All 31 complete
after observations follow B's terminal success; they do not establish the
missing remainder or continuous monitoring. snapshots/after.json, manifest.json,
approvals-result.json and states-result.json were not produced.

One already-authorized unauthenticated GET of Cloudflare /client/v4/ips later
returned 200/505 bytes in 4082 ms on its first attempt, at
2026-10-20T01:53:26.962Z..01:53:31.044Z. Its original receipt is
.cache/p44/logs/p44-v4-connectivity-probe-01.json. This establishes recovered
connectivity at that time, not a retrospective root cause or successful D1
after-state capture. It was not repeated. Separately, B waiting poll 2 used only
C4's admitted single pre-response ECONNRESET retry; its first failure and retry
reservation remain original evidence, not an unreported extra business run.

The V4 gap sealer source is archived in evidence/sealing/p44-v4-gap-close.py,
SHA-256 94860e763859fe1f53fabe37e45b032d35cc082b720d50e5d03d95a6b6c91c4e.
The actual formal privacy command then passed over 1149 files, 132 ZIP members
and 102 decoded D1 representations. No DATA files were added after the formal
privacy command closed; its log, receipt and result were the three excluded
self-outputs and were covered by the subsequent staged-byte audit.
The final matrix SHA-256 is
25d71ccb7707c83a62ace11e6662b2bdeab5e85df45faa557326010219f038d7.
It records 14 actual command receipts, only formal-after exiting 1. HISTORY,
CONFIGURATION, RAW-RUNS, REHEARSAL, RAW-READBACK and HYGIENE are PASS; RAW-STATE,
APPROVALS and ISOLATION are NOT_OBSERVED. The human review facts are real, but
the aggregate approval assembly/evaluation was not executed and is not invented.
The stock final validator, with the actual V3 contract/final matrix, passed with
overall=EVIDENCE_GAP; the result is not P4-4 PASS.

Root and the separate read-only scope reviewer retain the following minimal
recovery direction. Deliver the immutable V4 gap bundle and its later index
first. Then freeze a successor for missing after observations only: preserve C4
3.2.9 as the product target, all A/B/byte/readback/preflight/before evidence,
all 31 complete after responses and every failed original. Prefer one isolated
Tools/ota entry using the existing capture/evaluation primitives, with explicit
tooling-freeze versus product-target identity. Do not change the C4 capture,
run, inspect, bundle or profile inputs merely to move the evidence namespace.
The installed Undici 7.28.0 passes proxyTls and requestTls into its native
connectors; their default timeout is 10 seconds. A reviewed 30000-ms setting on
both, retaining the 60-second total deadline and original strict body/gzip
bounds, is the proposed repair, not yet an observed successful recovery.
UND_ERR_CONNECT_TIMEOUT is not silently added to C4's ECONNRESET retry rule.
No further owner action, token creation, descriptor/secret change, Worker
deployment, workflow dispatch, upload or registration is required or authorized
by this evidence recovery. Gates remain false; main and devices remain untouched.

Retained build output has 640 GCC warnings and zero errors: 246 -W warnings,
385 wchar_t-size notices, eight newlib unimplemented notices and one RWX notice.
npm reported 11 vulnerabilities (three moderate and eight high), not 33 by
adding duplicate run summaries. Structured advisory IDs were not independently
deduplicated; this work neither fixed nor established exploitability. The original build
stdout hash is 77da8a0494274a9dca1326a67b79583e5d42db51d20a78bc0e8a7dd9621cd272.
All selected new writes are in this guarded task worktree or the previously
authorized shared Git metadata. One disclosed accidental task-root empty file
from cmd redirection was verified as a regular zero-byte file and removed only
by apply_patch. Earlier PowerShell/Cryptnet cache attribution remains unresolved;
no external cleanup or machine-wide zero-write claim is made.

The staged-byte audit passed for all 1158 files, 1154 bound evidence files and
132 ZIP members, with the shared-root index unchanged. A separate targeted
board regression then exposed two previously omitted credential-boundary
sentences. Only the operational board restores those existing meanings and
labels the earlier no-rehearsal statement as its historical preparation stage;
no frozen evidence or criterion changes. The failed original is retained at
.cache/p44/logs/p44-v4-board-check-01.json. This document-only correction receives
a targeted regression and incremental staged review, not another live campaign.

V4 evidence was committed separately as B4
da37711799a21c4eb2c5d082dab1a7b81d028511 on the task branch; its frozen source
remains C4, not the bundle commit. The subsequent index records that exact
freeze-to-bundle ancestry. The corrected P4-4 card and readiness tests passed
2/2; the incremental staged review verified both document bytes, unchanged
final matrix and shared-root index. The secret pre-commit hook stayed enabled.
Source changes for after-only recovery start only after B4/index delivery.

### V4 Delivery And After-Only Development

I4 is 7168568489ab0eb67a9e7a05106f245e7243421e. The first push returned HTTP 408
and exit 1; its message "Everything up-to-date" was not accepted as delivery.
One subsequent native Git ls-remote confirmed the task ref still at C4. The
same authorized push then used standard HTTP/1.1 and a 512-MiB in-memory
postBuffer, without changing Git configuration on disk, and completed with
exit 0 at I4. The original failure, outcome check and successful push are in
.cache/p44/logs/p44-v4-delivery-push-01.json,
p44-v4-push-outcome-01.json and p44-v4-delivery-push-buffered-01.json.
No force push, amended commit, main merge or platform configuration change
occurred. B4 and I4 were independently reviewed as truthful EVIDENCE_GAP records.

The Node recovery and Python packaging owners are now implementing only two
Tools/ota leaves and their two targeted tests. The separate reviewer checks the
same stable batch, including source identity, path/secret boundaries, inherited
originals, eight required command IDs and four expected direct C4 reuses.
The entire Tools/acceptance tree and profile configuration stay unchanged.
The above expected reuse is not a formal plan until the actual new tooling
commit is frozen and the stock planner runs against the real C4 final matrix.

This operational note also corrects the earlier advisory-count wording and
privacy self-output explanation following independent feedback. Frozen B4
DATA, matrix and index bytes remain unchanged. The correction does not reopen
successful A/B or require another whole-bundle scan.

### Concentrated C5 Development Review

The independent reviewer has closed P44-C5-REVIEW-01 through 06 on the stable
four-file batch. Network admission consumes the exact C5 contract/initial
matrix/real predecessor plan and original-file inventory; the Node caller
checks the Python admission identity. All three complete schemas are checked
before network activity. Old after data is never presented as a fresh response,
and the first missing D1 page remains protected audit_logs OFFSET 16. After
configuration checks compare secret names and created_at/updated_at, variables,
review policies and the still-C4 descriptor; only the tooling branch ref may
advance to C5. New capture/assembly results bind exact file references and
C4/B4/C5 identities. Four reusable criterion/command/artifact/external signatures
remain unchanged; only the five affected criteria and their eight command IDs
are adapted.

Review of actual originals found one pre-existing interpretation defect before
formal C5 execution: the old inspector rejects Cloudflare's internal _cf_KV
WITHOUT ROWID table before excluding internal tables from business pagination.
The new Python leaf adapts only that database-snapshot interpretation. Original
schema bytes and the complete schema remain in the final delta comparison;
only enumerated business tables receive the rowid-pagination restriction.
Business WITHOUT ROWID, changed internal schema, malformed pages and incorrect
identities still fail. The original inspector is unchanged on disk, and the
local function substitution is restored in finally. No D1 observation was
repeated to repair this parser issue.

Node's final self-test passed 69 assertion groups from
2026-10-20T04:12:25.781Z to 04:12:44.599Z, with a closed exit-0 receipt. It binds
source 719a49f9f05f908dd984ba399e8f22568335f5dee8a78e8f6797df420a5ddd28
and test 93f7197da54243e85b549d5611798a62a2699ff2a240c352142442fd8e6f6cfc.
Python's final self-test passed 34 tests, its wrapper closed at
2026-10-20T04:13:15.068Z with exit 0. It binds source
ed786eede5cdd2d4afa029351db822a9a28cde51d134e522db92837ea3588d1c and test
8c251a65428154a000d4133a78eee9009039e2a54d2d0a9881942ccf4e93f758.
The first Python batch remains failed (13 passed, seven errors: six prospective
Git-fixture errors and the real internal-table issue); the subsequent 29-test
success and Node's earlier 49-group success retain their own inputs and dates.
They are not overwritten or relabelled as final-source results.

The stable tests also cover single-attempt CONNECT_TIMEOUT, native double
30000-ms connector settings with the original 60000-ms total signal, strict
interpreter arguments, duplicate rows, source/receipt drift, the actual protected
S3 derived key and base64 scan, and preserving an already-present formal
contract during later test execution. Actual before/negative originals were
evaluated without cloud operations. The original approval leaf additionally
passed one read-only independent check of 18 files; human-action provenance
still relies on root's actual saved owner confirmations. That preparation is
not a C4 or C5 formal aggregate PASS and is not repeated for a new receipt.

Root separately matched all four source hashes, actual final test logs/receipts
and the unchanged shared-root index. The development archive uses the retained
standard-tar route and includes original failed/successful tests, V4 delivery
failure/outcome/success, final-validator outputs and byte-exact member checks.
Current private-parent ACL readback still shows only the current user's
inheritable full control; no ACL mutation or claim of never-exposure follows.
All new outputs remain task-local. Entire Tools/acceptance, profile definitions
and V1-V4 frozen evidence are unchanged. Source review is complete; actual C5
freeze, precheck, planner and missing after observations are the next steps,
not results inferred from these development tests.

### V5 Admission And Honest Gap Closure

C5 is 9bfc48573a5eed190583411ac465bd847424a286, tree
bd28d777ee526166d9c1050c23e487dddf8eac0a, already pushed to the task branch.
The unchanged profile blob is 5ef97ae98674373c3cf641676c16ff7baf1b617f.
Contract P4-4-v5 SHA-256 is
ac95899a5dfdc8010dfc26ff350a2ffd94a72328412dd7a56705f72a99d83687,
round P44-20261020-05. Actual precheck and planning both closed successfully
against the actual C4 predecessor. The initial NOT_RUN matrix SHA-256 is
b24fe963392fd35c35bfaa8df73c014bdb3f5c9f6a5615897e9f076c7d6e66fa;
the actual rerun plan is
d81c8af9a8f6d10d63bb2db1fcda8c5045d640f7f91688642d28ede4e78c842c.
Only validation inputs changed. CONFIGURATION, RAW-RUNS, REHEARSAL and
RAW-READBACK directly reuse C4 EXECUTED PASS; no successful business operation
was repeated. The required history, before and negatives commands then passed
as actual offline evaluations of retained original bytes.

Formal-after closed with exit 1 at 2026-10-20T04:54:41.802Z after 172832 ms.
Its auxiliary GET /user/tokens/verify records ECONNRESET, attempts=1, during
04:54:35.600Z..04:54:40.458Z (4858 ms). The original failure records no status,
informational/final headers or body-receive state. This is UNKNOWN, not proved
pre-response failure, credential denial or D1 failure. The original SHA-256 is
7ebfa717f21722bf19fd65a5441c10ccae58f16adf3796b0221063cea147326e;
the closed command receipt is
cdfe411bbc4e33b067746a2ba1a9f494663bd80c1824080fc88fdb337f5f4e94.
Frozen call ordering and absent downstream outputs establish zero new D1/S3
business reads. All 31 completed C4 after responses and the earlier failures
remain unchanged. No after aggregate, complete manifest, approvals or states
result was generated, and no downstream command exit is invented.

The independently reviewed C5 gap sealer was archived before privacy at
evidence/recovery/sealing/p44-v5-gap-close.py, SHA-256
3d9eeb7399feb5b7f42ddabaa7fd3c7cf9874991f9b06feaf80244e0e5bd8047.
Its separate recovery/failure-report.json has SHA-256
18f74b72deb5664137a8e21783a072f96dca6e7543d13d24f1492174fc2c644d;
the C4 failure-report.json was not overwritten. Actual formal-privacy then
passed over 1182 files, 132 ZIP members and 102 decoded D1 representations,
including lifecycle checks. No DATA file was added after that command closed;
the privacy log, receipt and result are its three excluded self-outputs and
receive the separate staged-byte scan. Final sealing and validation logs stay
outside DATA in .cache/p44/logs/.

Final matrix SHA-256 is
0c79b01bbb97d276aa2fce322c0ab7f4aa5be65bc183a1457c75ca69f4c1f5dc
(182214 bytes). It retains nine original command records and five real C5
records: history/before/negatives/privacy exit 0, after exit 1. Four criteria
are REUSED PASS, HISTORY/HYGIENE are new EXECUTED PASS, and RAW-STATE/APPROVALS/
ISOLATION remain NOT_OBSERVED. The stock final validator with the actual C4
contract/final matrix closed exit 0, VALIDATION=PASS, overall=EVIDENCE_GAP.
This validates the honest failed-round bundle; it does not declare P4-4 PASS.

### P44-C5-AUTH: Offline Identity For Minimal Continuation

After the failure, root reconciled already-authorized historical credential
metadata without a network request. The original at
D:/github/my/E-Track/.cache/p41-dev-20261015/.cache/cf-readonly-20261015-r1/token-status.json
is 483 bytes, SHA-256
693ac971c7473e03f2fe526d117efe8b295cd403d24f8f66961ecb31ca563afa.
Its /body/result/id is a complete ID matching fingerprint
0c22488a9bee1355603d8d61faca06fcacbdafccfed8a4ba7dc490af7cacdedc.
The other historical token-policy diagnostic independently matched the same ID.
Only fingerprints and source metadata were reported; neither source was changed
or copied, and the ID/value remains private. Earlier searches that did not find
the ID do not negate this later discovery. The historical active status is not
a fresh status check or proof of current capability.

DECIDED: deliver B5 and its later freeze-index commit before editing the frozen
source. Then adapt only the existing two Tools/ota recovery leaves and their
tests. Read this fixed metadata file offline with exact byte/hash/ID checks,
derive the S3 secret in memory from the same existing protected local token,
and remove auxiliary verification entirely, with no network fallback. Put the
actual ID, derived key and base64 forms in both privacy and staged-scan needles.
The planned missing D1/S3 reads, not another token-status request, will establish
their actual operation-specific authentication. Do not create or rotate tokens,
change secrets, redeploy Workers, change descriptors or widen permissions.

C6 must use C5 as the actual predecessor and C4 as the explicit original reuse
source. Preserve all prior files and failure semantics; use new input/result/
command namespaces rather than overwriting C5. Legacy p/ decoding still uses
the preserved C4 contract. Product C4/3.2.9, A/B, the 31 completed after responses,
successful uploads/registration/readbacks and production read-only preflight
are not replayed. The entire Tools/acceptance tree and profile stay unchanged.
Source self-tests, independent batch review, real freeze/precheck/plan and only
the admitted missing observations are required before final adjudication.

No additional owner action is currently necessary. Gates remain false; no
production release, main merge or device action occurred. New outputs are in
the guarded task worktree or previously authorized shared Git metadata; the
shared-root index remains unchanged. Earlier PowerShell/Cryptnet attribution
remains unresolved, with no external cleanup or machine-wide zero-write claim.

### V5 Bundle Delivery

B5 is 21fa17f7da91a0d336ae1f1a7f1a93910beb2ab7. Independent review checked
all 1185 DATA files, 16 artifacts, 14 command records and their actual results;
the four original reuse anchors and unknown HTTP phase remain intact. The
separate staged scan passed for 1191 files, all 1187 bound evidence references
and 132 archive members, with exact staged/worktree bytes and the unchanged
shared-root index. Readiness and the P4-4 card checks separately passed 1/1 each.
The first commit attempt failed only the global debug-statement heuristic on
console examples in retained deployment HTTP originals. Its closed failure is
preserved in .cache/p44/logs/p44-v5-bundle-commit-01.json. The second attempt
disabled only that debug heuristic for this command; the secret hook remained
enabled and passed. No evidence bytes were edited to make the hook pass.

Full-evidence git diff --check also reported preserved CRLF/trailing whitespace;
the scoped check of manually changed documents, contract/matrices/plan and the
archived sealer passed. Raw logs and original provider output stay byte-exact.
This later index commit records B5 separately from its C5 input freeze. The
task-branch push must finish before C6 source edits; this is still a gap closure,
not whole-card PASS, production authority or main integration.

### V5 Delivered And C6 Development Batch

I5 is 7ae9112dcb8a910a541005df3421ed75fe8be3cb. The task-branch push closed
exit 0, moving its remote ref from C5 to I5 without changing main. Its original
is .cache/p44/logs/p44-v5-delivery-push-01.json. The later optional GitHub run-list
lookup failed with a TLS handshake timeout; p44-v5-ci-status-01.json/log preserve
that failure. It was not retried, is not a credential denial or a workflow
failure, and supplies no new CI-status conclusion.

Only the existing Node/Python recovery leaves and their two tests changed for
C6. The entire Tools/acceptance tree, profile and C1-C5 frozen bundles remain
unchanged. The implementation now reads the fixed historical identity offline,
without verify or fallback, separates C4 product/origin from the C5 predecessor,
preserves all 1185 C5 DATA files and uses independent v6 namespaces. Copy targets
are deduplicated before writes; existing recovery/c4.* is not copied twice.
Actual planner/reuse calls and all validator command strings carry C5 previous
arguments plus explicit C4 reuse-source. Precheck/plan receipts must reference
their own exact recovery-commands-v6 log, not another valid output.

The same batch fixes a discovered privacy error path: hashing a file containing
only the local token yields the derived S3 secret. A failed scan must not emit
that value through file_hashes. The scanner now omits sensitive failed digests
while retaining independent scan counts and failed paths; successful complete
hash mapping is unchanged. Synthetic raw-ID, derived-key, base64 and token-only
cases cover the serialized report. This is a demonstrated error-path risk, not
evidence that an actual token was exposed. The separate v6 staged scanner adds
the same fixed raw-ID sentinel and uses boolean digest comparisons so a failed
assertion does not print actual data digests. Old executed scanners are unchanged.

Node's actual self-test passed 121 assertion groups, closed exit 0, from
2026-10-20T07:35:16.604Z to 07:37:32.238Z. Source SHA-256 is
373d15c32507b10b05247bcae4c078bc1766b579ab88ea691a75e6addf1bf6f9;
test SHA-256 is
577f49e11734e36cfc5b4970c500cb04cf306628851645bf2486f325b53a9df0.
Originals are .cache/p44-v6-development/node-01.json/log and
selftest-01/result.json. Its actual mock after()/assemble() output is labelled
OFFLINE_CROSS_LANGUAGE_SYNTHETIC, not a cloud observation. The interop receipt
f9a08abda69e75a9c06f6b02db48264916869b2f50ffa6221084f9b8bf820e1c
binds 39 files, which the Python positive and mismatch cases consume unchanged.

Python's early core run passed 8/8 under its recorded earlier source. The first
full run passed 54/55: the missing-file fixture raised a bare uppercase string
that matched the safe error-code grammar instead of a real OSError shape. Only
that fixture was corrected to include errno and a path, retaining checks for
redaction, fixed-file access and zero fallback. The original failed log is
.cache/p44/logs/p44-v6-python-tests-01.log, SHA-256
cbc9284639a0848cad3b18d0c9439c6a36599aa34aa9c19a7a31a92824bb291e.
The final full run passed 55/55 in 149.403 seconds and closed exit 0 at
2026-10-20T08:03:49.745Z. Its log SHA-256 is
f4dda15a878b0154182e5ec132d007b55a2454fdff51a5b69125e2579de61f93,
receipt SHA-256
4b99622976b7824483a680cdbe0e300f5b489de88bb59bb0a3b29cffdb00c736.
Final Python source is
31230e4afc350f684ecf7b7501cd765a901ed8fb8df3f9577544c3665d205c97;
test is bd50db4394d09022e4ed4cffcdbd83b4f2597ff53fa5d137e569ff0573bd771f.
No earlier pass is relabelled as a final-source result, and Node was not rerun
to supply the Python interop cases.

Root independently matched all four current source hashes and read the closed
test receipts. Manual-file diff checks pass with four LF/CRLF notices; those
notices are not new GCC warnings. The Node owner's 46 outputs and Python owner's
90 fixture paths are task-local, and no formal C6 package was created by them.
Independent batch review, compact development archival, source delivery and
the actual C6 freeze/precheck/plan still precede any missing after observation.
Expected four C4 reuses and eight required command IDs are not promoted to an
executed formal plan from unit tests. No new workflow, upload, registration,
production preflight, gate unlock, main merge or device action occurred.

### C6 Successor Independent Review And Execution

On 2026-10-20 the owner transferred execution to the successor Codex root and
expressly authorized delivery of the eight already-staged files, C6 freezing,
missing-after observation and final evidence/index delivery on the existing
task branch. New tool remediation still requires owner agreement. The active
output boundary is this task worktree; shared Git metadata under
`D:/github/my/E-Track/.git` is authorized only for this scoped delivery.

The successor reviewer did not implement or change either recovery tool. It
reviewed the four source/test diffs, matched all four working and staged hashes
to the completed Node 121-group and Python 55-test originals, verified all 81
development archive inputs and the archive hash, and checked all 39 Node/Python
interop files against their producer receipt. Existing self-tests were not
rerun or promoted to newly executed tests. No required source remediation was
identified in this bounded review.

C6 is `6fffaa25442bdcd863f3a3f4e93e20ebe180a2c1`, successfully pushed only to
`dev/p4-4/config-integration-20261018`. Source commit/push receipts are
`.cache/p44/logs/p44-v6-root-source-commit-01.json` and
`.cache/p44/logs/p44-v6-root-source-push-01.json`. The secret hook remained
enabled; only the debug-statement check was excluded for normal tool output.

Preparation preserved 1187 predecessor files and generated the new descriptor,
SHA-256 `673b18612e00f77a850f1b3be8f3ee48e3330d8394163c92239819e0f00b79ff`.
The actual frozen contract SHA-256 is
`dbb6bf4bf986b320dfe91a7a3b6817cd4031a156be310b9f87bbad51e65120a9`.
The closed formal precheck passed with overall NOT_RUN. The actual formal plan
retains C5 as predecessor and C4 as the original EXECUTED PASS source for
CONFIGURATION, RAW-RUNS, REHEARSAL and RAW-READBACK. Its eight required command
IDs are history, before, negatives, after, assemble-complete, approvals, states
and privacy, each with the existing `formal-` prefix.

History, complete before and five original authentication negatives passed
their new offline evaluations with actual exit 0. The after command started at
2026-10-20T11:39:28.585Z. Offline identity evaluation reports zero verify requests
and does not claim a new active-token observation. The former missing
`protected-audit_logs-rows8-16` response completed HTTP 200 at
2026-10-20T11:43:42.672Z. This is execution progress, not a final isolation or
whole-card PASS. The 31 complete C4 after responses retain their original times
and bytes; no successful A/B, upload, registration or readback is repeated.

#### P44-C6-TRANSPORT-01: Incomplete After Tail

The actual after process closed exit 1 at 2026-10-20T11:55:31.813Z, after
preserving 39 new complete HTTP 200 responses. Together with the unchanged C4
prefix, 70 complete after responses are available; they are not a complete
snapshot. The failing SELECT is `protected-patches-rows8-16`, with original
`evidence/snapshots/after-tail-v6/protected-patches-rows8-16.http.json` and its
`-request-failure-1.json` record. The latter explicitly records one attempt,
`UND_ERR_SOCKET`, no final response, zero body bytes and no informational
response. This establishes the receive phase, not the network fault's cause or
a product defect. The closed `formal-after.json` receipt binds the failure log
SHA-256 `3905175dfdac979c90a7e5387e8f7fca9605626c29a6c709f6ddb245b1cc957e`.

The unchanged frozen transport permits retry only for pre-response ECONNRESET;
it correctly did not retry this different error. The current after adapter is
fixed to the 31-response C4 prefix and rejects an existing after reservation.
There is no admitted CLI route to resume these 39 new responses. Do not delete
the reservation, relabel the socket error, replay successful pages, or change
the frozen source to force continuation.

The independent `formal-privacy` command subsequently closed exit 0: 1411 files,
141 decoded D1 responses and 132 ZIP members checked; lifecycle checks passed.
No after aggregate, complete manifest, approvals/states result or final matrix
was produced. C6 remains an incomplete evidence collection, not PASS. The
current C6 originals and this note remain local pending disposition; only the
C6 source/development commit has been pushed.

Owner decision is required before new collector remediation, as explicitly
requested in this successor session. The preferred direction is bounded
continuation of existing verified pages with truthful per-attempt failures,
not another product run or a new general-purpose controller. Any change to
retry conditions, frozen inputs or evidence lineage must first be reviewed
against its actual dependencies. Successor root retains independent acceptance
ownership; the existing gates, historical failures and original card owner
remain unchanged.

### Collector Remediation Takeover (2026-10-21)

The owner requested that the reviewing root take over implementation. This
session is now the implementation owner, not the independent acceptor of these
changes. The only writable root remains `.cache/p4-4-integration-20261018`.
No commit, push, freeze, platform observation or frozen-evidence change is
authorized by this takeover. A different reviewer must accept the repaired tools.

The bounded repair retains the existing collector and HTTP leaf. C6 provides
39 successful originals plus its failed request; C4 provides 31 successes and
its failure. Resuming verified prefixes is needed because the old collector
cannot consume the C6 tail. No new transport, retry policy or controller is needed.

| ID | Required repair | Development oracle |
| --- | --- | --- |
| R1 | Build failed attempt summaries from persisted HTTP originals | Persisted socket failure reloads unchanged; next invocation starts at its missing label |
| R2 | Correct identity initialization, Map frontier and attempt summaries | Complete capture reloads and assembles; two interrupted attempts resume without source edits |
| R3 | Align Node/Python per-invocation recovery semantics and order | Both complete and multi-attempt Node outputs pass the actual Python verifier with explicit synthetic Git identity |
| R4 | Remove cached write-path trust | Recheck ancestors before writes; replaced/reparse paths are rejected |
| R5 | Restore executable regression feedback | Targeted tests first, then both existing suites and negative cases; no formal PASS from self-tests |

Development output stays under `.cache/p44-v6-development`. Tests reuse real
C4/C6 bytes in memory and simulate missing responses only. Cross-language
fixtures are explicitly synthetic; tool identity is resolved by a test-only
Git mock with real producer bytes, never by weakening production hash checks.
The exit condition is runnable complete/reload/interrupted-resume/interop tests
plus both affected suites, not another network attempt or a new frozen bundle.

#### Recovery Adapter Contract And Regression Notes

Scope: the development `Tools/ota/p44-after-*` adapters only. No historical
contract, original, profile or acceptance runner is reinterpreted or rewritten.
The existing C6 formal CLI admission is not authority to use dirty tooling or
restart its failed command. The successor contract, C6 gap matrix and additional
observation allowance remain independent-acceptance responsibilities.

Signatures and ordering:

- `await validatePrefix(ctx)` is asynchronous. A complete-prefix check also
  validates the recorded tool ref, so the CLI must call `admit(...)` to establish
  `ctx.toolCommit` before prefix validation. Unit fixtures set that identity
  explicitly; this does not grant real admission.
- `attemptResult(ctx, ok, error)` rescans persisted HTTP records before closing
  the attempt. The HTTP leaf writes the failure original and then throws; the
  caller must not use only records returned by successful awaits.
- `verify_after_recovery(contract, descriptor, ctx)` verifies Node's actual
  snapshot, attempt records, reservations and final result. `_plan_records`
  derives traversal from raw schema/release responses and binds each label to
  its exact snapshot record, rather than trusting dictionary/file enumeration.

Field contracts:

- An attempt result's `new_reads` includes its complete and failed HTTP record
  references. `complete_labels` and `failure_labels` are sorted; `failures`
  retains every request-failure reference, including both failures when the
  original permitted retry also fails. Original error codes are not relabeled.
- Final `recovery.reused_complete`, `reused_records` and `reused_failures`
  describe all observations present before the final invocation, not always
  C4+C6 alone. `recovery.new_reads` describes only that invocation's complete
  records, in traversal order, with exact `label/kind/role/record` fields.
- `recovery.first_missing` is the final invocation's starting frontier;
  `after-result.first_missing` is null only after completing the plan.
  `first_new` is the first newly captured label. These are not the C4 frontier.
- Attempt end times include terminal failures. A retry reservation's start is
  at or after its first failure's end and no later than the enclosing HTTP
  record's end; it is not equal to the initial request's start.
- An attempt summary is derived exactly once. `Map.size`, not
  `Object.keys(map).length`, determines complete-prefix coverage.
- Every physical write reuses the existing uncached `s.guard` before creation
  and again before opening the destination. Positive path checks are not
  persistent authorization if an ancestor changes.

| Case | Required behavior / assertion |
| --- | --- |
| Base C4+C6 prefix | Reuse 31+39 complete records; retain both failures; collect 72 missing records in the fixture |
| Two further disconnects | Preserve one then two new successes and both failures; final invocation reuses 73 and collects 69; four attempts remain visible |
| Full prefix reloaded | No network replay; identity/frontier validation and `assemble` succeed |
| Failed request persisted before throw | Final failure code and references match disk; next missing label is data-derived |
| Reordered snapshot dictionaries | Raw schema/release traversal, not object insertion order, defines labels |
| Changed body, SQL, resource, duplicate rows or washed failure | Reject before new collection; no output from prefix validation |
| Wrong tool bytes or changed failure/frontier summary | Python rejects; synthetic Git resolution does not bypass hashing |
| Pre-response ECONNRESET then success / socket failure | Native Undici MockAgent produces both traces; both parsers preserve the 500ms retry reservation and original codes |
| Previously checked ancestor becomes a link | Next write fails `REPARSE_PATH`; no destination is created |

Wrong: extending collectors until the happy-path probe finishes, then testing
the consumer later. Correct: first run persisted-disconnect and full-reload
regressions, then consume producer output with the actual Python verifier.
The prior failures combined asynchronous API propagation, inconsistent
cross-language field definitions and an untested assumption that an awaited
HTTP call returns its failure evidence. The regression boundary is the durable
record and its consumer, not only the in-memory successful call count.

The existing test files remain the only test entry points. Node accepts
`--output-dir <fresh project-local directory> [resume|all]`; `all` is the
default. Python accepts `--node-fixture <that Node output directory>` before
normal unittest selectors. Cross-language packets bind producer source hashes
and every exported byte. Python materializes them only in its guarded
development batch directory, and mocks only the synthetic Git object lookup.
Real source-identity failures still reject. No uncommitted production tool is
passed off as a real Git object or formal observation.

The first targeted run (`remediation-red01.log`) failed R1 and R2 as intended.
After the Node fixes, `remediation-python-red01.log` reproduced the actual
`AFTER_ATTEMPT_PREVIOUS` mismatch in both single and repeated-resume fixtures.
`remediation-python02.log` then passed all five targeted producer/consumer and
negative tests. These are development red/green results, not formal rounds.

#### Final Development Verification

All R1-R5 development oracles passed. The final consistency check also binds
configuration values/rules/secret metadata to the original paginated responses
and before snapshot, checks environment/page/tag routes, and binds final tool
identity to the contract and final attempt. Neither hash validation nor any
formal criterion was relaxed. Git source/fixture hashes below describe these
uncommitted working bytes, not a new frozen tool commit.

Commands ran from this worktree using `cmd.exe`, with controllable host/cache/
temporary locations set by `containedEnvironment` under
`.cache/p44-v6-development/remediation-host`. Python was isolated with `-I -S -B`.

    node tests/ota/test_p44_after_recovery.cjs --output-dir .cache/p44-v6-development/remediation-node04
    python -I -S -B tests/ota/test_p44_after_bundle.py --node-fixture .cache/p44-v6-development/remediation-node04

The Node command closed exit 0 with 145 assertion groups, including native
Undici retry traces and the physical contained command-wrapper check. Its result
binds the current Node source/test hashes. The final Python command closed exit
0 with 61 tests in 311.738 seconds, including the actual complete and four-attempt
Node outputs. Both suites verified unchanged formal evidence; Node also checked
all 1185 original C5 evidence files. These are implementation self-tests only.
Both Node syntax checks, Python AST checks and `git diff --check` passed; Git
reported normal LF-to-CRLF checkout advisories, not hidden test failures.

| Current file | SHA-256 |
| --- | --- |
| `Tools/ota/p44-after-recovery.cjs` | `26c6cd93c2a048bf3137f13af8c3ec5815bc83ac6dd942ac38e6ac0b0816f578` |
| `Tools/ota/p44-after-bundle.py` | `4c4a2f7175538eea903c2b74ea5d67209718e85cfda338c106c624b18213c9b3` |
| `tests/ota/test_p44_after_recovery.cjs` | `11faced2b35376e63f33b5b1e953317108aa47e76256dda68dddeb66cdae1e19` |
| `tests/ota/test_p44_after_bundle.py` | `93547b772e9723a3940d583268d50e0a199d5c61f95f326f1a9d482bde04ffa2` |

Final originals under `.cache/p44-v6-development/`:

| Evidence | SHA-256 |
| --- | --- |
| `remediation-node04.log` | `4d01949e8ceb9e751a70c74ba08994ff88ff541e2a996ec9ec616c5d8ce84315` |
| `remediation-node04/result.json` | `3988d27f592b0c238aadb792134d440b43aaf1ae887c7fbe42d09f10fe9dc63c` |
| `remediation-python05.log` | `2217db6a42878b03e8154caa6c6a6b40487e32c8ffe0899ee4100b21407efb70` |

Final interchange packets remain in `remediation-node04/`; their evaluated
copies are in `python/batch-8/`. All red/green logs and Node result records are
retained. Only this session's duplicate intermediate interchange packets in
`remediation-node02/` and `remediation-node03/`, and its materialized
`python/batch-4` through `python/batch-7`, were removed after checking exact
resolved targets and descendants. No older agent cache or formal original was
cleaned. All actively selected writes/deletions are within this worktree;
no external output, commit, push, network business request or new freeze occurred.

The developer batch is ready for another independent review, not formal P4-4
acceptance or immediate execution of the old C6 command. The next owner must
retain C6's actual failed round and C4's original PASS sources, arrange any
authorized source delivery, and provide the approved successor admission and
remaining observation allowance. Do not rewrite C6, treat synthetic Git IDs as
real commits, grant retry authority from these tests, or replay successful pages.

### P44-C6-TRANSPORT-02: Post-Response Body Failure (2026-10-21)

Independent review rejected the preceding developer batch: the failure parsers
assumed every failed capture was a failed `request()` call. The HTTP leaf already
preserves a response-body failure with `status`, partial hash/size and zero (or
one prior retry) request-failure documents. Calling the complete-body decoder on
these bytes, demanding one more request-failure document, and enumerating
`.body` instead of `.partial.body` prevented attempt closeout and reload.

Required repair stays in the two adapters and their tests. Distinguish
pre-response failure from post-response failure using the retained response
status and partial evidence; validate the correct request-failure count and
terminal record. Preserve public partial bytes, private encoded originals and
intentional privacy-only hash projections without promoting any to a complete
page. No body retry, deadline extension, invented request-failure file, new
network operation or edit to `Tools/acceptance` is permitted.

The regression uses the real HTTP leaf and body pipeline, with only the HTTP
request/body source and private filesystem replaced in memory. Cases cover
plain, gzip/private, empty, a prior ECONNRESET retry followed by body failure,
and sensitive plaintext projection. Each must write a failed attempt result,
reload to the same gap, retain all originals, and allow only a separately
invoked synthetic continuation. Node output is consumed by the real Python
verification path, with explicit synthetic Git and private-byte resolution.
The reviewer retains independence and owns disposition of this finding.

#### TRANSPORT-02 Implementation And Verification

Implemented; independent closure remains pending. The preceding 145/61 test
results remain historical development results and did not cover this phase.
The new red run failed `POST_RESPONSE_ATTEMPT_RESULT_MISSING` against those
exact Node bytes before the repair. No independent finding is self-closed here.

The two parsers now use these matching contracts:

| Retained capture | Request-failure count | Storage / result behavior |
| --- | --- | --- |
| Failed before a response (`status` absent) | `request_attempts` | Last request-failure code must match; partial fields/body are forbidden |
| Failed after a response (`status` present) | `request_attempts - 1` | Valid HTTP status and partial hash/size required; the terminal HTTP record is also in attempt `failures` |
| Public unencoded partial body | As above | Exact `<label>.partial.body`; verify its actual hash/length, not advertised full Content-Length |
| Encoded D1 partial body | As above | Exact project-local private wire path, required original bytes/hash/length, no public or decoded body |
| Sensitive plaintext projection | As above | Preserve the original hash/size and exact privacy projection; missing plaintext is intentional, not a complete observation |
| Complete response | `request_attempts - 1` | Partial/private markers are rejected; existing complete-body decoding and semantic checks remain required |

Private paths are constrained to the existing capture namespace plus the exact
attempt/label stem before reading. Missing, altered or redirected private
originals fail closed. Both implementations reject a public gzip D1 partial,
injected decoded sidecar, incorrect partial path/hash/size, negative received
length, response-status removal and a changed completion flag. Private partial
bytes are not decompressed. The original HTTP leaf, retries and deadlines are
unchanged; each body failure uses one request, except the case with the already
permitted pre-response ECONNRESET retry, which uses exactly two.

The fixture retains C4+C6's 70 complete responses through five new failed
invocations. Each reload reaches the same gap without promoting partial bytes;
one explicitly invoked mock continuation adds the 72 missing complete responses.
Python verifies all seven attempts and 142 complete records. `private_files` in
the development interchange packet contains only synthetic wire bytes from the
mock pipeline; tests resolve those in memory and still execute real hash checks.
It is not a public export of any real private capture.

Commands (same contained host environment as the preceding batch):

    node tests/ota/test_p44_after_recovery.cjs --output-dir .cache/p44-v6-development/transport02-red01 body
    node tests/ota/test_p44_after_recovery.cjs --output-dir .cache/p44-v6-development/transport02-node03
    python -I -S -B tests/ota/test_p44_after_bundle.py --node-fixture .cache/p44-v6-development/transport02-node03

Red exit 1 was expected and retained. Final Node exit 0: 175 assertion groups.
Final Python exit 0: 65 tests, 333.954 seconds. The four targeted Python tests
also passed beforehand (`transport02-python01.log`). Final fixture directory:
`.cache/p44-v6-development/transport02-node03`; Python materialization:
`.cache/p44-v6-development/python/batch-5`. Both suites retained their formal
evidence immutability checks. No C6 original, transport leaf, product source,
release workflow, gate, profile or frozen contract was changed.

| Current source | SHA-256 |
| --- | --- |
| `Tools/ota/p44-after-recovery.cjs` | `7a8a31d4c49356b57991480cb055e84df23af5821630ccb61001f318a60f6b06` |
| `Tools/ota/p44-after-bundle.py` | `5671d16d66a8c37e3f60eaf6d645d31c88bc6f45b06d7e22d5177cf482aae157` |
| `tests/ota/test_p44_after_recovery.cjs` | `caa7f8a8b1b082ddd28a793fe31758b178ee228f0f1b5596a2f0518700b8f950` |
| `tests/ota/test_p44_after_bundle.py` | `c004d02ea81d8df3adc4077a41195f17796f5f56921b742a3b22b305aa0201ff` |

| Log / result under `.cache/p44-v6-development/` | SHA-256 |
| --- | --- |
| `transport02-red01.log` | `912d47775906fa82837b7fb6f865d1874e8c6a478e373cf064f0267f131d368b` |
| `transport02-node03.log` | `029a364e963ea71bbb6e5e331d2c0061c4ea14b6333b8699e428b59fd9baa604` |
| `transport02-node03/result.json` | `3c3f6062a056966565e606be21599700797dd677a02257815417954cb110871e` |
| `transport02-python02.log` | `4ee550e44d10c3e9a539fced62c05080bf286b27fed3df10550fdd7a5bdb162f` |

All outputs remain in the authorized worktree; this follow-up deletes no older
artifact. No real HTTP request, commit, push, PR, freeze or index registration
was performed. The next owner is the existing independent reviewer for
P44-C6-TRANSPORT-02, not a new formal collection or automatic retry.

#### TRANSPORT-02 Independent Closure (2026-10-21)

Disposition: CLOSED for the bounded tool finding. The independent reviewer did
not author or modify either adapter or test. The four current source hashes
and four red/green evidence hashes match the preceding implementation tables.
The original Node 175-group and Python 65-test results were reviewed, not rerun
or relabeled as new independent test-suite executions.

The reviewer independently exercised the actual HTTP capture/body pipeline
with synthetic HTTP responses and memory-only output storage. Plain body
disconnect and gzip/private disconnect each used one request; a pre-response
ECONNRESET followed by body disconnect used exactly two. Every case retained
UND_ERR_SOCKET, wrote an unsuccessful attempt result, kept the partial response
incomplete, and reloaded 70 complete originals at the unchanged
protected-patches-rows8-16 frontier. No body retry occurred. An initial gzip
probe referenced an unexported constant in the reviewer fixture; correcting
that memory-only private-path fixture made the gzip and retry probes pass,
without any adapter change or filesystem output.

The Python partial-storage/count branches and terminal-failure references were
checked against these capture shapes and the source-bound interoperability and
tampering-test originals. No remaining required fix was found in TRANSPORT-02.
All 1411 C6 files bound by its privacy inventory still match; its contract hash
remains dbb6bf4bf986b320dfe91a7a3b6817cd4031a156be310b9f87bbad51e65120a9.
The HTTP leaf, profile, product source and workflow remain unchanged.

This closes only the repair finding, not P4-4. Source delivery, C6 failure
disposition, successor admission and the remaining real observations still
belong to the main acceptor. Do not rerun the old C6 command with dirty tools,
rewrite its originals, replay A/B or open a production gate. This review only
appends this closure record; it performs no commit, push, freeze or cloud read.

#### C6 Gap Seal And Successor Boundary (2026-10-21)

The independent root sealed the actual C6 result as EVIDENCE_GAP, not P4-4
PASS. C6 completed 39 new HTTP 200 responses in 40 single-attempt read-only
requests. The last request, protected-patches-rows8-16, failed with
UND_ERR_SOCKET before any informational/final response or body byte. Its
formal-after command exited 1 and closed. All 31 complete C4 after responses,
the 39 complete C6 responses, both historical after failures and the C5 private
verification failure remain intact. No business operation was replayed.

The matrix contains 14 command records: nine original C4 records supporting
four direct REUSED PASS criteria and five actual C6 executions. HISTORY and
HYGIENE are EXECUTED PASS; RAW-STATE, APPROVALS and ISOLATION remain
NOT_OBSERVED. Complete after/manifest/approval/isolation outputs do not exist
and were not fabricated. All 1411 files in the closed C6 privacy inventory
still match; its 141 decoded D1 responses and 132 ZIP members remain bound.
New closeout metadata lives outside evidence/ and is covered separately by
the staged delivery privacy audit, rather than changing the closed scan.

| Item | SHA-256 |
| --- | --- |
| P4-4-v6.contract.json, unchanged | dbb6bf4bf986b320dfe91a7a3b6817cd4031a156be310b9f87bbad51e65120a9 |
| P4-4-v6/final-evidence-matrix.json, 215879 bytes | 7dfa85be4a70858a38468839f4a888b12c7cf4109f2afcb107e8997b6e5bb414 |
| P4-4-v6/closeout/failure-report.json | 97390331b9953354f908e05eb820e7ce03d8626e1e38ceb6a8deceb1dc5ed724 |
| .cache/p44/logs/c6-final-validation02.log | 2ba3a518f022686d1aab73594c12bd6ebfa26d1e6aa3beaac63fcb2bd120f94d |
| .cache/p44/logs/c6-final-validation02.json | 6604b066e67f7b7831fd36bc0059f4f096dbe82a52fc2e644bde728bff2b4a97 |

The stock final CLI returned exit 0 and
`VALIDATION=PASS contract=P4-4-v6 round=P44-20261020-06 overall=EVIDENCE_GAP`.
It ran from a native detached C6 worktree under
.cache/p44-c6-verification with byte-exact C6 package copies, the actual C5
previous pair and the original C4 reuse pair. Only the needed paths were
checked out. No current dirty tool was reverted or used to certify C6.
An initial copy-only verification attempt could not find the unchecked-out
validator; its exit-2 Python output remains in c6-final-validation01.log.
Initializing that new worktree's sparse checkout fixed the setup without
editing any evidence or source. This was a local verification setup issue,
not a new product observation or a hidden successful test.

The authorized successor implementation is delegated to gpt-6-astra because
the preferred gpt-6.1-sol invocation failed at encrypted-context hydration.
Root remains the non-implementing reviewer/acceptor. P44-SUCCESSOR-01 uses a
pinned project-local package specification and the actual C6 B/I lineage;
it retains original criterion/command IDs and C4 PASS origins. At most two
after invocation slots are admitted, with no automatic continuation. A
second slot requires root adjudication, a closed previous failure, unchanged
source/frontier and concrete repair or external-state-change evidence. Every
failed receipt stays bound; command text and observation budgets cannot be
reset. Shared capture transport/retry policy, profiles and product stay
unchanged. Stable source delivery, successor freeze, actual precheck/rerun
plan and only the missing SELECT/list observations still precede final P4-4
adjudication. No production release, main merge, gate unlock or device work
is authorized by this closeout.

#### P44-SUCCESSOR-04 修复记录（2026-10-21）

原始失败保留：v7 `source_plan()` 预检退出 1，报
`AssertionError: PREDECESSOR_REUSE_HISTORY`（`source_identity()` 第 177 行）。
根因是 C6 矩阵的四项 `REUSED` 判据把 `previous_matrix_sha256` 指向 C5，而
`reuse_sources()` 只返回了 C4，未提供标准校验器要求的中间谱系。该失败日志
`.cache/p44/logs/v7-source-plan-preflight01.log` 未被改写；本修复未重做 A/B
演练、上传、注册或成功 readback，也未改动既有 70 份完整 after 响应。

仅修改以下四个文件：

- `Tools/ota/p44-after-bundle.py`：`reuse_sources()` 改为从真实前驱矩阵出发，
  按 `previous_matrix_sha256` 回溯；中间来源按矩阵 SHA-256 唯一定位，逐级核验
  合同/矩阵哈希、包名与 `contract_id` 身份、`task_id`、版本递增、
  `parent_contract_sha256`、矩阵前驱与轮次关系，并在前驱 bundle 中复核 Git
  blob 字节。遗漏中间来源、哈希不符、身份漂移、谱系错误或循环均失败。来源集合
  由目标版本推导（v6 为 C4；v7 为 C4+C5；v8 为 C4+C5+C6），不新增每轮常量。
  `validation_commands()` 按同一版本推导追加全部 `--reuse-source` 对。
- `Tools/ota/p44-after-recovery.cjs`：`validatorArgs()` 使用相同的版本推导，
  在 `--matrix` 前依次追加 C4、C5（后续轮次自动扩展）。
- `tests/ota/test_p44_after_bundle.py` 与
  `tests/ota/test_p44_after_recovery.cjs`：增加真实 C6/C5/C4 正向谱系、缺失
  中间来源、哈希篡改、身份/谱系错误、循环以及 Python/Node 参数一致性的定向用例；
  新增 `validator` 定向套件，避免为验证默认 v6 参数而运行历史操作。

未改动：`Tools/acceptance/`、任何 profile、产品源码、workflow、传输/重试策略、
原判据与命令 ID、两个有界 after 调用槽、失败回执及既有时间检查；C4/C5/C6
字节与 v7 package spec 身份绑定保持不变。

验证结果（全部离线，工作树外无主动写入）：

| 检查 | 命令/证据 | 结果 |
| --- | --- | --- |
| 真实 v7 `source_plan()`（不注入、不 monkeypatch） | `.cache/p44/logs/v7-source-plan-fixed02.log` | 退出 0；1416 个来源、1414 个 descriptor 文件、1417 个目标检查；复用版本 `[4,5]`；cloud/evidence 写入均为 0 |
| 标准 `_validate_reuse_history()` | 真实 C6 前驱 + 真实 C4/C5 来源 | 完整链返回 `[]`；删除 C5 后仅返回 `reuse history P44-20261020-06: missing previous round ...` |
| Python 定向测试（4 项） | `.cache/p44/logs/p44-successor-04-python-targeted02.log` | 退出 0，`Ran 4 tests ... OK`，81.583 s |
| Node 定向测试（默认 v6 参数 + v7 参数） | `.cache/p44/logs/p44-successor-04-node-targeted02.log` | 退出 0，89 组断言，`cloud_operations=0` |
| Node successor 定向套件 | `.cache/p44/logs/p44-successor-04-node-successor03.log` | 退出 0，23 组断言，`cloud_operations=0` |

真实身份：C6 仍是 `--previous-contract`/`--previous-matrix`
（`P4-4-v6.contract.json`、`P4-4-v6/final-evidence-matrix.json`）；C4 仍是四项
原始 `EXECUTED PASS` 的直接来源；C5 作为唯一中间来源出现一次。Python
`validation_commands()` 的 precheck 参数向量与 Node `validatorArgs('formal-precheck')`
在定向测试中逐项相等。

| 当前文件 | SHA-256 |
| --- | --- |
| `Tools/ota/p44-after-bundle.py` | `e61af5c4d1c91cea25c47c311c2303fc4251cb4f8ae6766d2d69cefccc02013c` |
| `Tools/ota/p44-after-recovery.cjs` | `037c66a8388156382847702e72c21c1d3b01f96f5ca4976579a772c43bb3c8d2` |
| `tests/ota/test_p44_after_bundle.py` | `12903d318f199147c67658d0046bc5745af9ffe6507cd3dc8c2589ac76723902` |
| `tests/ota/test_p44_after_recovery.cjs` | `01b9ac71196a27f5cfdd22e8e72aa372d27ded28937b4b85812c5501f782c755` |

| 证据文件（工作树内） | SHA-256 |
| --- | --- |
| `.cache/p44/logs/p44-successor-04-python-targeted02.log` | `29debccc8eb78f632cd3107945f86390c1a69781557efb010b70f382024f404c` |
| `.cache/p44/logs/p44-successor-04-node-targeted02.log` | `4ff8d599c6ddc0c8524008aa6d08e6445f7b07d7277e6e4c082fda77361b09f8` |
| `.cache/p44/logs/p44-successor-04-node-successor03.log` | `83d133bfdf40f608533d54ecfb47e54235f34afce23b5ecc7ff88c7589cb72e1` |
| `.cache/p44/logs/v7-source-plan-fixed02.log` | `97f280c56053b8e8e7fe63d20c490ad89c82d48ba7ef1efdb8c04fb04374b263` |

边界与残留：本节只证明“实现及离线自测完成”，不构成 P4-4 正式验收通过，也不
证明 C6 的 `EVIDENCE_GAP` 已转为 PASS。未冻结 v7 合同，因此未运行标准 CLI 的
正式 precheck/rerun plan/final；该步骤仍由原 root 在稳定源码交付后执行。Python
全量历史套件与 Node 历史操作未作为本修复的验收证据重跑；一次 Node 定向套件
门控失误曾离线执行既有操作（退出 0、157 组断言、0 云操作），其结果仅保留在
`.cache/p44-v7-development/validator-targeted-01/`，未计入修复证据，随后已修正
门控并以 89 组断言的定向运行替代。所有主动输出均位于
`D:\github\my\E-Track\.cache\p4-4-integration-20261018` 内；后台命令的宿主任务
临时输出文件由运行框架管理，不是本任务选择的证据路径。未提交、推送、冻结、
触网、操作设备或修改平台配置。下一责任人为原 root，独立复核后决定 successor
freeze 与正式 precheck/final。

#### P44-SUCCESSOR-04 Independent Closure (2026-10-21)

Disposition: CLOSED for this bounded implementation finding. The independent
root authored no adapter or test changes and used no sub-agent for this review.
The four source/test hashes and four implementation-log hashes match the
preceding tables. The targeted self-test originals were reviewed rather than
repeated or counted as independent suite executions.

The root independently imported the delivered Python module, selected the
unchanged real v7 package specification and ran source_plan() against the
committed C6/C5/C4 files and Git objects. There was no injected source map,
monkeypatch, mock Git or network request. The plan contains 1416 copy inputs,
1414 descriptor files and 1417 guarded output targets. The unchanged standard
history validator accepted the complete chain and returned exactly one
missing-previous-round error when C5 was removed. Node and Python precheck and
plan argument vectors match exactly; all three Python validation commands
include C4 and C5 once, with C6 remaining the actual previous pair.

For clarity, C6's matrix-level previous_matrix_sha256 identifies C5, while
the four reused criteria still point directly to C4's original EXECUTED PASS.
The repair preserves both identities. No new blocking finding was found in
the bounded implementation review. The earlier transport and continuation-time
closures remain valid; no product or successful observation was replayed.

Independent receipt: .cache/p44/logs/p44-successor04-root-review01.json
(SHA-256 703de5bf4ce9355891025156470515ebe01f6e85369bf0d2465e04c4bc355903).
Independent output: .cache/p44/logs/p44-successor04-root-review01.log
(SHA-256 54ef7663401e211e299fe3750cceedabf89414547d679223b1633bfe98f755b0).
The command closed with exit 0; implementation and original evidence bytes
were not modified. This closes SUCCESSOR-04, not P4-4 formal acceptance.

C6 delivery is complete on the authorized task branch: B6 is
90c5924f74e3c1fe3ca88576a16a9ba18b39856d and I6 is
08e3929f19b4d3ca7fa722a3b7414c36e8285b34, both pushed. The v7 package spec
pins those identities. Stable successor source delivery, freeze, real precheck
and rerun plan, missing observations and final validation remain root-owned.

Delivery-only preparation: the existing v6 staged audit needed approximately
19 minutes for 1422 files. The already-drafted v7 adapter reuses the existing
native Python path guard, credential sentinels and Git blob identities instead
of repeated fsutil ancestor probes and per-file Git processes. Root reviewed
and self-tested its stdout-only invocation; six negative predicates passed,
with no credential read or Git/network action during self-test. Its optional
--output interface is not used or qualified. The script is not a formal
criterion or a replacement for the frozen privacy command. Its original hash
is 0b9074a305cf87e77a2334c6a26d11ca4a77ab97d583d007243673b26b5732d4;
self-test output is .cache/p44/logs/v7-delivery-auditor-selftest01.log,
SHA-256 0250f0c1fe97c5c2395c55ef966b85b1d67355b2b8bf27b801de56e23b030668.

#### P44-SUCCESSOR-05 Independent Finding And C7 Closeout (2026-10-21)

Disposition: DECIDED, required harness repair, not an observed product failure.
SUCCESSOR-04 remains independently closed. Root did not change the collector or
its tests and did not delegate remediation to a sub-agent. The next implementation
owner is the external agent selected by the user; root retains independent review.

The stable source was delivered as C7
371baeeb8519a0340a79c96b6a7cd6406b2e0346, tree
085b095982054ecf45c1a23ff21031760376cb2b, on the authorized task branch.
The frozen v7 contract is SHA-256
587258cde323692569733470045a2e174ec1bef32c67088ba0cc3e76e1223314,
round P44-20261021-07. Actual precheck and rerun-plan commands passed, retaining
four direct C4 origins and requiring five criteria/eight commands. The actual
plan SHA-256 is 7918ebdf96495b00ccbf16a73d2535b6ce803a1e1976e0d6315e652a738178fc.

The first formal-after invocation ran from 2026-10-21T04:52:14.277Z to
2026-10-21T05:04:43.440Z and closed with exit 1, signal null and no spawn failure.
Its original output is {"ok":false,"error_code":"ERR_ASSERTION"}. The receipt
is P4-4-v7/evidence/recovery-commands-v7/formal-after-invocation-1.json,
SHA-256 a7cc8d60e49c57f75405e6335789cc0f2381fc02e0034b3ab715bc476917cdf9;
the adjacent log SHA-256 is
8dfea9fb1567bb31c6951ffc12fd511211be83d683545d2ae8803163891835b4.
No attempt-2 directory, new HTTP record or after snapshot was created. There
were zero new cloud requests; the 31 C4 plus 39 C6 complete responses and all
historical failures remain unchanged. Invocation slot 1 was consumed; slot 2
was not used or admitted. There is no failed attempt-result for continuation.

Root independently reproduced the first-missing path with real makeIO and
makeEnsure.d1 while explicitly blocking writes and network calls. The stack is
makeEnsure.d1 -> prepare -> startAttempt -> makeIO.exists -> destination ->
relative. At Tools/ota/p44-after-recovery.cjs:893, startAttempt passes
attemptDir(2), which ends in '/', to exists. The strict relative() at line 56
rejects that empty final component with RECOVERY_PATH. The in-memory fixture
accepted this argument and therefore missed the production-IO mismatch.
The probe recorded zero attempted writes and zero attempted requests. Its exact
output and invocation are archived in P4-4-v7/closeout/independent-probe.log and
independent-probe-receipt.json; their SHA-256 values are respectively
90ce4a1fc40cba118ae45a41f7a9916af83a830e24335af38eca30665612d75e and
bcd03c0894c831799f9cedf1d00a40874b1ea46381924e3e25ce35c39bb7ab8f.

Preferred minimal repair: normalize the directory argument at the startAttempt
existence-check call site. Do not weaken relative() globally or remove the
trailing separator from attemptDir(), whose other callers concatenate filenames.
The bounded static sweep found no other bare-directory exists call; list()
already normalizes its directory argument. Verify with actual production makeIO
and project-local filesystem fixtures: first missing-request registration,
subsequent attempt numbering/reload, existing-directory refusal and unchanged
traversal/reparse/no-overwrite guards. Network responses may be simulated, but
the tested exists/destination/relative chain must not be mocked or replaced.
Keep transport/retry policy, original IDs, invocation limits, time checks,
source binding and all old evidence unchanged. Do not retry frozen v7; the
reviewed repair requires a subsequent source freeze and actual predecessor.

Independent safe work completed: formal-history, formal-before,
formal-negatives and formal-privacy exited 0. The privacy result scanned 1439
files, 141 decoded D1 bodies and 132 archive members; lifecycle checks passed.
The closed privacy inventory is unchanged. Dependent assemble, approvals and
states were not run because their required after artifact does not exist.

The unchanged standard validator accepted the final matrix with the actual C6
previous pair and both C4/C5 reuse-source pairs:
VALIDATION=PASS contract=P4-4-v7 round=P44-20261021-07 overall=EVIDENCE_GAP.
This is validation of the honest incomplete bundle, not P4-4 PASS. Four criteria
are REUSED PASS, HISTORY/HYGIENE are EXECUTED PASS, and RAW-STATE/APPROVALS/
ISOLATION are NOT_OBSERVED. EVIDENCE_GAP is used because there is no actual
after artifact for a failed-criterion HARNESS_FAIL; none was fabricated.

Final matrix: P4-4-v7/final-evidence-matrix.json, 220199 bytes, SHA-256
1c4bdd4002748aea77ab6839344b6d9d02e4f377ec6fc35a2050e089ccbaee62.
Failure report: P4-4-v7/closeout/failure-report.json, SHA-256
7f0aa55068dc74a21bfe536c72ae49145b449935e5f6248d6eb3d4dff15963e6.
Final-validator original: .cache/p44/logs/v7-final-validator01.log, SHA-256
ba5501e81cc3fd3b5768fc582f9525cd3017083313005fcaf8578f7f4e486f4a;
its receipt SHA-256 is 24aabad92f3ab23704b07dc889104a231b1c2596267b87549abb8eeef07635e1.
The thin seal.py only binds existing originals and records missing observations.
It does not collect, retry, fabricate after evidence or change the frozen tool.

P4-4 stays IN_PROGRESS; product stays C4/3.2.9 and gate stays false. No A/B,
upload, registration, successful readback, production release, main integration,
device operation or platform-configuration change was repeated. Closeout writes
are confined to the task worktree and authorized shared Git metadata.

#### P44-SUCCESSOR-05 Bounded Implementation (2026-10-21)

Entry: clean task worktree, HEAD I7 ca352d8b0410d2040ced7be8a94290ef86a2b406,
C7 371baeeb8519a0340a79c96b6a7cd6406b2e0346 and B7
98c1d053227d437e9ec71c3ee622926b8ad4f116 are present. No prior uncommitted
SUCCESSOR-05 changes were found. SUCCESSOR-04 remains independently closed.
The sole writable root is D:/github/my/E-Track/.cache/p4-4-integration-20261018.
The canonical governance is consumed read-only; no Trellis tree is installed.

DECIDED: normalize only startAttempt's exists directory argument. Keep
attemptDir's concatenation convention and strict relative/destination checks.
The bounded sweep of exists/list callers found list already strips trailing
separators; file references retain strict validation. Extend the existing Node
and Python test entries with real filesystem fixtures, a failed partial body,
reload/continuation and actual assembly/consumer checks. No new formal bundle,
formal command, cloud request, product change or slot admission is involved.

Host preparation found Node 24.13.0 (also installed Node 20.19.5) cannot create
spawnSync capture pipes in this sandbox: actual fsutil and git calls return
EPERM, status null, pid 0. Direct cmd/Python and Node inherited stdio execute
fsutil successfully. A development-only stdio adapter will capture the actual
fsutil/read-only Git subprocess output using project-local file descriptors;
it will not cache answers, replace guard/IO/registration functions, change exit
codes, or weaken reparse checks. All child commands keep explicit cwd/deadlines.
This is a host execution limitation, not another production collector finding.
Preflight used the existing Python native reparse guard for every controlled
output tree and the five allowed source/note paths before writing. Logs,
scratch, contained environment and fixtures stay below
.cache/p44-v7-development/; no external cleanup is authorized or performed.

Preparation adjustment: the first controlled invocation was cancelled during
fixture seeding because it was doing three complete Node guard walks per copied
input. No test case completed and no attempt-2 was created in that fixture.
Its raw .cache/p44-v7-development/successor05-01/node.log is retained unchanged,
SHA-256 5759057086399793519295eb2e6de9b4fa49629cc74ed6e9c05b9eb4006f7529.
The command session closed with exit 1; elapsed time was not recorded by the
interrupted launcher and is not invented. psutil subsequently found no Node
process executing test_p44_after_recovery.cjs. No unchanged failed test was
repeated: the second invocation changes only fixture preparation to call the
existing Python bundle.guard/write implementation with a bounded, hash-checked
input packet. Registration, response writes, scanning and reload continue to
use actual makeIO and the unchanged Windows fsutil guard, without cached answers.

The second run uses .cache/p44-v7-development/successor05-02/ and the thin
launcher/preloader in successor05-01/. Its controlled stdio scratch files remain
successor05-01/host/stdout.tmp and stderr.tmp; contained TEMP/HOME/APPDATA/cache
paths are successor05-02/host/*. Initial retained inventory covers 6460 paths
from v1 through v7. The shared worktree index mtime was checked read-only as
2026-10-21T05:52:59.289Z, before this implementation session.

Observed intermediate checkpoints (not a completed self-test verdict): actual
loadRecovery/validatePrefix restored 70 complete responses and frontier
protected-patches-rows8-16. Real makeEnsure.d1/startAttempt created the attempt-2
directory and resume reservation before the simulated API callback. The callback
checked schema, attempt, source/product/tool identity, current HEAD/tool bytes,
prior record count, history and absent response file. The actual HTTP leaf then
persisted one complete page and one truncated HTTP-200 body, closed its agent,
and actual attemptResult recorded complete_labels=[protected-patches-rows8-16],
failure_labels=[protected-patches-rows8-24], ok=false, UND_ERR_SOCKET, with two
new_reads and one failure reference. The partial body was not counted complete
and no retry reservation was created. Reload, continuation, assembly and Python
consumer results are recorded below only after they finish.

##### Completed offline batch and handoff

SUCCESSOR-05 root cause: attemptDir(2) is a filename-concatenation prefix ending
in '/', while production makeIO.exists accepts a strict relative path without
empty components. The previous memory fixture normalized that argument and hid
the mismatch. The production diff is one line at startAttempt's exists call:
strip its final slash there. relative(), attemptDir(), transport, retry,
source/time checks, no-overwrite and invocation admission remain unchanged.
The same-chain exists/list sweep found no additional production defect.

The existing Node entry adds a bounded real-io suite. Fixture inputs are a
hash-checked 754-file subset prepared with existing Python bundle.guard/write;
the tested IO is actual makeIO, including exists/destination/relative/write,
makeEnsure.d1 -> prepare -> startAttempt, registerFresh, attemptResult/scanSource,
loadRecovery/validatePrefix, after/walkAll and assemble. The production HTTP
capture.d1/body pipeline handles a simulated truncated response. The test does
not replace filesystem, registration, scanning, assembly or hash validators.
The Python test entry adds a direct-directory fixture consumer and two bounded
cases; it does not rehydrate/copied-replace the tested Node outputs. Production
p44-after-bundle.py is byte-identical to C7 and needed no repair.

External inputs simulated: network/API responses, credential-pair inputs and
the new uncommitted candidate's Git identity. Node reads actual HEAD and tool
bytes; candidate tool_commit is deliberately 'a' repeated 40 times. The existing
synthetic_git helper supplies that development Git object's current producer
bytes and ancestor answers to Python. Actual digest/lineage/source checks stay
live, and the wrong-tool-bytes negative is rejected as AFTER_ATTEMPT_TOOL.
No actual credential is read or exported. This synthetic identity is not a
commit, frozen input, admission or formal source observation.

| Development chain | Actual result |
| --- | --- |
| Prefix and first missing registration | 31 C4 + 39 C6 complete responses restored from disk; first missing rows8-16; actual attempt-2 directory/reservation written before simulated request; identity/format/path checked |
| Partial failure | One additional complete rows8-16 page, then one truncated HTTP-200 rows8-24 body; actual HTTP/partial body/attempt-result persisted; ok=false, UND_ERR_SOCKET; one body transport call, one destroy, no retry |
| Reload and explicit development continuation | Actual loadRecovery/validatePrefix restored 71 complete responses and failed rows8-24; next attempt=3; only 71 missing responses requested; prior success and failure hashes unchanged |
| Success and assembly | Actual attemptResult rescanned persisted new files; a fresh loadRecovery context fed actual assemble; 142 complete responses (70 originals + 72 newly simulated completes over the two development attempts), three attempts including legacy attempt-1; manifest/result written, duplicate assembly refused |
| Python consumption | Actual capture_results -> verify_after_recovery -> _after_source/INSPECT.Context and snapshot/configuration checks consumed the same 1098 disk files; 31 C4, 39 C6, 142 total, three attempts, 71 final new_reads; partial success count=0; no consumer writes |
| Negative guards | Existing attempt directory rejected before request/reservation; original marker unchanged; overwrite rejected; seven illegal/traversal/absolute path cases and sibling boundary rejected; actual Windows junction rejected for exists/write, no escaped file created, junction unlinked |

There were 73 simulated request outcomes across the two development attempts:
72 complete and one truncated body. Actual cloud/network requests were zero.
The development fixture uses the existing default v6 input interface and the
same production tail/attempt functions used by the v7 collector. It does not
run a v7 command or authorize its second invocation slot.

All commands used cmd.exe and explicit cwd
D:/github/my/E-Track/.cache/p4-4-integration-20261018. The two actual suite
invocations are below; the launcher captures binary stdout/stderr without
rewriting output and retains command vectors, PIDs, deadlines and closure.

    python -I -S -B .cache\p44-v7-development\successor05-01\run.py node
    node --require .cache\p44-v7-development\successor05-01\stdio.cjs tests/ota/test_p44_after_recovery.cjs --output-dir .cache/p44-v7-development/successor05-02/node real-io

    python -I -S -B .cache\p44-v7-development\successor05-01\run.py python
    python -I -S -B tests/ota/test_p44_after_bundle.py --node-fixture .cache/p44-v7-development/successor05-02/node AfterBundleTests.test_real_io_failure_reload_assembly_is_consumed_without_copying AfterBundleTests.test_real_io_consumer_rejects_wrong_tool_bytes

| Scope | Deadline / exit / count / elapsed | Raw output / receipt |
| --- | --- | --- |
| Node real-io | 5400 s / 0 / 19 check groups / 4076.323545 s launcher elapsed; 06:53:19.003Z through 08:01:03.347Z inner self-test | successor05-02/node.log and node-receipt.json |
| Python direct consumer + wrong source negative | 300 s / 0 / Ran 2 tests in 111.381 s, OK / 112.092277 s launcher elapsed | successor05-02/python.log and python-receipt.json |

The Node host adapter executed 78372 actual fsutil/read-only Git subprocesses
with zero cached answers; no path guard was weakened for speed. Both receipts
record process_closed=true. A final psutil check found Node PID 24220 and Python
PID 1660 absent. Native synchronous children had already returned; the mock HTTP
agent's destruction was asserted. The cancelled preparation has no valid suite
result and is not counted above. No old log is counted as newly executed.

Node/Python syntax checks completed without errors. Final git diff --check
returned 0; Git emitted four normal LF-to-CRLF checkout notices, not test or
compiler diagnostics. No firmware build, complete historical failure matrix,
formal precheck/final, formal after/assemble, live cloud request, A/B, upload,
registration, readback, CI, device operation, commit, push or freeze was run.
Existing valid SUCCESSOR-04/other failure-type evidence is retained and reused
by review, not relabelled as this batch's executions. The real pipe-host issue
required the disclosed development file-stdio adapter; an unadapted Node
capture-pipe invocation remains environment-blocked in this sandbox.

Paths below are relative to .cache/p44-v7-development/ unless fully spelled.

| Original output | SHA-256 |
| --- | --- |
| successor05-02/node.log | d86746934cff1ca49a518e02808a7483c111ee98bf7d82b9df9516928ddc15ef |
| successor05-02/node-receipt.json | 8c673b41c7b143ef35ddbfe6ae854457d69f1e1e929a01d308ce46bbebb8505a |
| successor05-02/python.log | 76150f5db1d6a9ea64aa2e8a5462c03527f454bbead99913573ace0fd679ad10 |
| successor05-02/python-receipt.json | 444bada93c9b46fa0587ee19f7bd5d0c1a80bdaa13dbe70bfc049bc771d6c15b |
| successor05-02/originals.json | aed630a757d060d1261eeda3523ff6d33becf98faa4d7af778ea42ba0d44490b |
| successor05-02/node/real-io.json | f452159316eaaf686163d96156e282dd775afec0f1885bea2f4a093043a35f52 |

| Delivered source/test | Final SHA-256 |
| --- | --- |
| Tools/ota/p44-after-recovery.cjs | 4b5081954a47c36bfc71e11f5eb07bdc2c94db6a615a7a42ab85ec78fcd9a21c |
| tests/ota/test_p44_after_recovery.cjs | d4678e22bc71a848064860290d546085d58c15f0c9dd2fc981d07d9047d48055 |
| tests/ota/test_p44_after_bundle.py | 5aaaa75f73aad688c7c927637f939621d604f033638026d0b874d8891e8a1b0c |
| Tools/ota/p44-after-bundle.py, unchanged | e61af5c4d1c91cea25c47c311c2303fc4251cb4f8ae6766d2d69cefccc02013c |

The final note hash (including this section) and all five source/note hashes
are stored without self-reference in successor05-02/audit.json, generated by:

    python -I -S -B .cache\p44-v7-development\successor05-01\run.py audit

Output audit: controlled writes are exclusively the three modified source/test
files and this note; successor05-01/ (cancelled fixture, local launcher and
stdio scratch), successor05-02/ (logs, raw fixtures, results, receipts, host
environment and audit), and .cache/p44-v7-development/python/batch-5/ (empty
existing test-entry batch directory). The audit rechecks every existing output
path with the native reparse guard and compares the retained 6460 formal paths.
No junction remains, no path escaped the active root, no system temporary/cache
path was selected, and no main-worktree or shared Git index write occurred.
The shared index mtime was again 2026-10-21T05:52:59.289Z after both suites.
The formal v7 contract/matrix retain their stated hashes, all 70 complete
after responses and historical failures remain original, and slot 2 remains
unused/unadmitted. Only the four listed tracked files are dirty; no user or
other agent changes were reset or reverted. Development artifacts are retained.

Disposition: implementation self-test only, pending the original root's
independent review. No claim excludes all future defects. Product stays
C4/3.2.9, gate=false, P4-4 not formally passed and v7 EVIDENCE_GAP unchanged.
The original root owns any formal successor/source delivery, freeze, missing
read-only collection and final adjudication.

实现及离线闭环自测完成，待原 root 独立复核。

##### SUCCESSOR-05 Independent Closure And V8 Preparation

Disposition: CLOSED for the bounded directory-argument defect. The independent
root changed no collector or test implementation and used no sub-agent. The
production delta is exactly the one-line exists-argument normalization; the
strict path validator and filename-prefix convention remain unchanged. No new
blocking finding was found in the affected batch and call-chain review.

Root verified the implementation source/support/log hashes and closed receipts,
then compared all 6460 historical entries with the supplied retained inventory
and all 6213 historical files with actual HEAD Git blob identities. All match;
the shared main index retains SHA-256
2907ee569cb8415877c8c688b3e09b5948a789d6430796eab99ae3ad43f3a3dd.
The 19-group, 4076-second Node run was reviewed, not repeated. Its file-stdio
adapter executes real commands and preserves status/output without cached
answers; it was not needed on the root host, whose native pipes were checked.

Root independently reran the two direct Python consumer/source-negative tests:
exit 0, 2 tests in 101.056 seconds, consuming the same 1098 files without copying
or changing them. The disclosed synthetic development Git identity remains a
fixture limitation, not a formal provenance assertion. A separate native Node
probe used actual makeIO, actual Git and the version-selected v7 call path,
without the development stdio adapter: reservation preceded the simulated
callback, the existing attempt directory was rejected without another callback,
and seven invalid paths were rejected. It made no network request. Its minimal
development reservation is outside every formal package.

The new v8 package descriptor retains v7 as the actual predecessor and all
earlier failures. Its SHA-256 is
d487dbdd0a36f9d49a8f7308acd0bb02978cdd56c829ba3bf83b0cb54f8ca0b4.
An unmodified source_plan() against real Git/files verified 1444 copy inputs,
1442 descriptor files and 1445 absent guarded targets. Reuse sources are C4,
C5 and C6; removing C6 yields exactly one missing-previous-round error. Node
and Python precheck/plan vectors match, and every validation command includes
all three reuse-source pairs. This was a read-only preparation probe, not a
formal precheck, freeze or new observation.

Nineteen original outputs/receipts, support sources and the implementation note
snapshot are archived under P4-4-acceptance-preparation-2026-10-19/v8/. The
inventory SHA-256 is 2bcc2740e436a9eb5f682bd43188b94b3dbdfd9cdc612891056d5c85192e86a5.
It binds successor05-root-record-review01, successor05-root-consumer01,
successor05-root-entry01 and v8-source-plan-review01, including exact invocations.
The cancelled preparation remains failed history, not a passing test.

For delivery hygiene, root reuses the already-qualified v7 auditor's unchanged
functions and native guards with only the exact v8 package/spec/preparation path
constants substituted. Its source SHA-256 remains
0b9074a305cf87e77a2334c6a26d11ca4a77ab97d583d007243673b26b5732d4;
stdout-only operation and the existing credential/byte checks remain intact.
This operational path binding is not a new formal validator or product gate.

The stable repaired source may now proceed to source delivery and ordinary
successor admission. V7 is still EVIDENCE_GAP; its second slot was not used.
P4-4 remains IN_PROGRESS, product C4/3.2.9 and gate=false. No successful A/B,
upload, registration or readback was replayed; no cloud/device action occurred
during this review. Only the missing approved observations remain eligible
after the actual frozen rerun plan and execution-worktree checks.

##### P4-4 V8 Independent Acceptance PASS (2026-10-21)

The unchanged stock final validator returned exit 0:
VALIDATION=PASS contract=P4-4-v8 round=P44-20261021-08 overall=PASS.
All nine required criteria pass: CONFIGURATION, RAW-RUNS, REHEARSAL and
RAW-READBACK directly reuse C4's original EXECUTED PASS; HISTORY, RAW-STATE,
APPROVALS, ISOLATION and HYGIENE were evaluated in this round. Eight required
commands actually executed, with nine original command records reused. The
actual previous pair is v7; C4/C5/C6 were supplied as the complete reuse chain.
This is formal P4-4 stage acceptance, not merely a valid EVIDENCE_GAP bundle.

| Bound identity | Value |
| --- | --- |
| C8 source commit, already pushed | 640cb359db7672cdab1e40bc5853a9ab311e35fa |
| C8 freeze tree | a343caba4c7d2a5976ebf7674017e7352b938626 |
| v8 contract SHA-256 | 4c414c3632a7b4f74ffcee80c9ae9e629370ac14bf097d9a7fb1b755300d80d4 |
| v8 final matrix SHA-256, 281881 bytes | e0236015d4d0f88bdd16f542d1c67bedd5725932111971378af4032981603bc6 |
| Actual rerun plan SHA-256 | 0397507cd401b9f8ad5f21527321d9bc1b25f84faa9441a9071e2d9dbaa1d707 |
| Complete manifest SHA-256 | 270e6e9376ed467f98c451cbbc90e3fcf77c46b1c7baadd3fccb32ce8c467e33 |
| Complete after snapshot SHA-256 | ed8e8cb6e59d2fef03520bd4b12e1654edd564566191fcd22e006d3ea33edf2f |

The formal after invocation ran from 2026-10-21T09:23:06.271Z to
2026-10-21T10:13:40.380Z and closed with exit 0, signal null and no spawn
failure. It retained 70 complete C4/C6 responses and obtained 73 additional
complete responses, giving 143 in total. Only invocation slot 1 was used;
there was no second invocation or continuation approval.

The precise request ledger is 74 new request attempts for 73 complete responses,
not zero failed attempts. config-production-secrets-1 encountered one
pre-response ECONNRESET with no final response and zero received body bytes.
The existing frozen GET retry policy reserved attempt 2 after its 500 ms delay;
the final response was complete HTTP 200. The first failure and retry reservation
remain in snapshots/after-tail-v6/attempt-2/. No retry policy was added or
changed. Earlier progress counters counted incomplete HTTP envelopes only;
the final ledger includes this failed request attempt explicitly.

Actual offline assembly, approvals and state/isolation evaluation all passed.
The privacy command passed with 1824 scanned files, 200 decoded D1 bodies,
132 ZIP members and lifecycle checks. Its closed DATA inventory was not
modified after scanning. The final matrix binds 1829 evidence/plan/initial-matrix
hashes and 17 command records. No failing history was removed or relabelled.

The original assessment and final-validator outputs/receipts are archived in
P4-4-v8/closeout/, outside the closed evidence directory. The final-validation.log
has SHA-256 db6840d81cc0face329cef92d94f1104635c4351018100dd103ab3f98d60781d;
its receipt has SHA-256 b9ec231f3b5e483c9e96b2ff2e0197711d4105b67af79ba94da991ba48b4deb4.
The standard validator checked actual v7 history, all reuse-source pairs,
frozen objects, the execution worktree and the final evidence, not just plan
generation or the matrix's handwritten result field.

SUCCESSOR-05 is closed and no further remediation was identified in this
accepted scope. The P4-4 card may be marked complete for its specified P5-before
configuration/staging prerequisite, retaining the original implementation owner.
Source and evidence delivery use only dev/p4-4/config-integration-20261018;
main integration is not performed. Product stays C4/3.2.9, gate=false, and P5,
owner/environment approval and production rebuild/publication gates remain.
No successful A/B, upload, registration or readback was replayed; no device or
production-release action was performed. Historical v1-v7 bundles are unchanged.

Delivery-only correction: the first v8 bundle hygiene invocation stopped at
FINAL_MATRIX_SCOPE because root had rebound the v7 auditor's path constants but
missed its one literal expected matrix ID. Its original output/receipt are kept
as closeout/delivery-scope-failure.log and delivery-scope-failure-receipt.json.
The corrected invocation verifies the unchanged base-auditor hash, substitutes
exactly that expected-ID literal with P4-4-v8, and binds only the exact v8 paths.
All existing byte, boundary and credential predicates remain active; the six
negative self-test predicates are retained. This does not modify the stock
formal validator, frozen input, contract, matrix or closed evidence. No formal
command, cloud read or successful observation is repeated for this delivery check.

##### P4-4 Main Delivery Closeout (2026-10-21)

The user's follow-up requested complete P4-4 closeout before the P3-5 handoff.
PR #30 merged the unchanged v8 delivery tree into main as
6469233b282bdaf188e764d68128133f553f0247 after all four PR workflows passed.
C8, B8 and I8 remain reachable, with all v1-v8 frozen bytes unchanged.

Main Governance, GCC and App path checks passed. The Admin mock UI job exposed
P44-DELIVERY-CI-01: the test helper typed before the dialog's scheduled initial
focus, placing the reason into the confirmation field; the product correctly
kept confirmation disabled. The failed run 39599518618 and both bilingual
failure screenshots are preserved, not reclassified or discarded.

Root changed only the shared UI test helper, not product code, P4-4 tools or
frozen criteria. Commit 3ecc6722b9eb847f6b6aae196aad6aa6a23a232e waits for the
existing animation-frame marker and verifies exact field values. PR #31 passed
and merged as 75d3ad24424989f5a5f38fe237d24deef9decd4f. Main Cloudflare run
39602375609 passes all jobs, including 36/36 UI cases with zero retries.

P4-4 formal acceptance and main delivery are complete. This is not a new formal
acceptance or production qualification. Product C4/3.2.9 and gate=false remain;
no successful business observation or device action was repeated. The original
main worktree and its dirty files/index are preserved. Full delivery identities,
CI receipts, warnings, failure evidence and output audit are recorded in
P4-4-main-closeout-2026-10-21.md and its adjacent inventory. Next task is P3-5
integration admission and execution, not another P4-4 remediation campaign.
