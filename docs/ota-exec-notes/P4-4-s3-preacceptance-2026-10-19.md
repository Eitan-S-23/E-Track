# P4-4 S3 Pre-Acceptance Review (2026-10-19)

Current disposition: P44-REVIEW-01 and P44-REVIEW-02 are RESOLVED on b56534d;
independent successor review is 10/10 and both source-bound development CIs pass.
Both target Workers now contain the verified new module. P44-CREDENTIAL-01's
missing-pair/configuration blocker is RESOLVED by the later agent handoff and
root's independent 15-GET / 28-assertion readback. The successful provisioning
source differs from the previously denied local token; it is not evidence that
the old token's 403 became 200. Formal P4-4 acceptance remains NOT_RUN, not PASS.
Historical failures remain below; see Independent Credential Handoff below for
the current source, protection, lifecycle and evidence limits.

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
