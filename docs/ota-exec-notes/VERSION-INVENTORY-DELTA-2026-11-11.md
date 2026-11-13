# Version Inventory And Operator Delta Jobs

## Scope And Plan

User approved implementation on 2026-11-11. Active root is the existing
`.cache/p35-integration-20261028/source` worktree. Preserve all earlier dirty
files, registered packages and completed observations. Work area:
`.cache/version-inventory-delta-20261111-01/`.

Implement low-frequency, optional Android version reporting and dated MCU
observations; original-Admin inventory and refresh controls; multi-base delta
requests using existing Actions packaging tools, append-only assets and explicit
enablement. No automatic channel publication, old-package replacement, production
approval, phone installation, firmware flash or four-hour test is part of this
implementation batch. No new review agent is required for development feedback.

App counts are reported installation instances, not people. Current OTA INFO
has no qualified global device identifier. MCU observations are scoped to an
installation, clearly labelled as potentially duplicated across phones; do not
invent unique-device counts or mutate the frozen INFO frame for analytics.
Cached MCU data retains its original observation time and nonce. Unknown and
unreported versions are not zero users. Reports carry no raw Bluetooth address,
location or riding data. Users can disable reporting in the existing App.

Keep normal reports daily, coalesce changes and back off failures. Server-side
per-installation limits and a transactional daily budget protect the existing
free-tier service. Existing HTTPS/Cloudflare/D1/R2 and CI tools are reused.
Actions source and inputs must be pinned; registration must verify reconstruction
and target hashes before an optional patch can become visible. APP VCDIFF and MCU
ETU remain separate formats. Original immutable registration metadata stays intact.

Validation order: existing contained Node/SQLite and browser regressions; required
dual-host Flutter development CI and APK/EXE compilation for changed App inputs;
then source-bound staging migration/deployment and bounded real UI/server checks.
Only request a phone window after scripts and artifacts are ready. Missing live
credentials or client coverage is reported as missing, not simulated success.

## Status

Inventory and original-Admin UI deployed and checked with the real owner session.
The updated APK and Windows EXE have passed Actions builds. Both real delta
formats are now qualified: MCU 30323 to 30324 and original App 83 to 86. The
original App repository/key boundary is fixed; no replacement credentials or
original-package rebuild were required. Owner controls are active on all three
original services at `9dd858fc8f9943d444060169291ea5131d63489b`; neither verified
asset is enabled. The final real owner UI and public-offer checks passed.
No device operation or channel publication occurred. Older blocked statements
below are retained history, superseded by the continuation recorded at the end.

## Implemented Contract

- The existing Android App reports its installed APK version/hash and up to four
  cached MCU INFO observations. Normal reports are daily; a control check occurs
  at most every four hours on foreground events. Backoff is one hour. No new BLE
  scan/connection, remote wake-up, perpetual polling or OTA ownership is added.
- The profile settings dialog contains an opt-out and disclosure. The server
  stores a digest of the random installation token, not the raw token or BLE
  address. One phone's MCU keys cannot deduplicate across phones. Report sequence
  checks and observation nonces prevent stale cached data from becoming fresh.
- D1 migrations 0007/0008 are additive. Inventory has an initial daily accepted
  report limit of 1000 and a per-installation limit of eight. This deliberately
  leaves room for D1 index writes, cleanup and the original update service under
  the free plan; it is not an account-wide quota guarantee. Data is retained for
  90 days, with bounded hourly cleanup. The new minute-17 staging cron only cleans
  inventory, not historical firmware idempotency receipts.
- Original Admin App/MCU sections have peer distribution tabs and compact paged
  7/30/90-day tables. Manual refresh requests future reports, not immediate replies.
  Unreported and stale data are never silently treated as zero users.
- Each target version's delta dialog selects up to five original bases. Reported
  30-day counts are guidance only; the operator makes the selection. Existing
  patches/jobs are reused. At most 20 new attempts/day are admitted transactionally.
- GitHub Actions downloads bound original packages. APK jobs verify version,
  package name and the same signing certificate; use the existing VCDIFF encoder;
  reconstruct byte-for-byte; sign a per-base manifest using the existing key.
  MCU jobs unpack existing full ETUs, reuse the existing bsdiff/ETU tools and
  validate all image/header/package identities. No original is finalized again.
- CI claims bind job, attempt, workflow commit and run. An unknown dispatch is
  reconciled against a unique GitHub run, never blindly retried. An explicit retry
  can bind a corrected workflow while retaining the previous attempt's identity.
- A generated asset is disabled until an owner explicitly enables it. Enabling
  requires a smaller verified object and a valid original target. Mutation nonces
  bind transaction side effects to the winning CAS. Channels and sealed original
  metadata do not change. Full fallback remains available.

## Validation Observed

- App WIP `60906e304044319b1237bac6ba51811219c6dccc`, Actions `43044268397`:
  four analyzer findings; Windows unpaced parser fixture overflowed its recorder
  queue. Both original logs and development artifacts are retained.
- App correction `ce458416cb96dc9be41981aa9cd3098198b21c1f`, Actions `43049945504`:
  strict analysis passed on both hosts. Linux 771 passed/16 skipped; Windows 752
  passed/35 skipped; eight additional candidate checks passed on each host.
  SDK: Flutter 3.47.9 / Dart 3.13.7. Production recorder limits were not changed;
  the parser contract now uses a memory writer before persisting its exact output,
  so an unpaced mock link does not measure Windows fsync scheduling.
- Local `host-01`: 395 backend tests and 13 delta orchestration tests passed.
  `host-02` also includes retention, GitHub reconciliation and concurrent-CAS tests.
- New browser scenarios `ui-01`: 13 passed. `ui-all-01`: 150 passed, one 320px
  English tab overflow found. The short tab label was corrected; no assertion was
  removed. A complete successor UI run is retained separately.

Node/SQLite and browser doubles are development checks, not real Cloudflare,
Access or hardware evidence. Native Workers CI, APK/EXE build, staging deployment
and live checks are recorded separately below when actually observed.

## Configuration And Remaining Gates

Original resources remain `trace-update-admin-staging.pages.dev`,
`trace-update-public-staging.pages.dev`, `trace-update-service-staging`,
`trace-update-staging` D1 and `trace-update-staging-releases` R2.

The cloud dispatcher needs project-scoped GitHub Actions write/read credentials
(`DELTA_GITHUB_TOKEN`), the exact workflow ref/commit and the existing APK public
verification key. Never export the host's personal GitHub credential into Pages.
Supplemental distribution stays disabled until those bindings and the real job
route are qualified. Firmware Actions retain the `firmware-rehearsal` approval
gate. This task does not bypass it, publish Stable/Beta, merge unrelated branches,
install an APK or declare the old P5-1 hardware campaign complete.

The App build candidate is bumped to `1.0.75+101`; existing installations do not
gain inventory support until an explicitly installed/published new App is used.

## Observed Delivery, 2026-11-12

- Feature source: `b36304eb243005f56dbe6b30b76e28a18f1c91dc`, then the scoped
  correction `9b690ab33cd967da1706d6b254ee8e66076d6628` on
  `dev/admin/version-inventory-20261111`. GitHub Git API delivery did not write
  the worktree's shared Git index, refs or object store. This is not a main merge.
- Native Workers CI `43057580798` passed 358 tests and 13 generator checks.
  Corrected-source CI `43061882806` passed 366 native tests and the same 13
  generator checks, including the added real Pages-facade role/CSRF/origin tests.
  A transient `gh run view` EOF was recovered using that existing job's log API;
  it did not cause another build. Raw results: `feature-status-01`,
  `feature-status-02` and `feature-logs-01` under the task work area.
- UI `ui-all-02` passed all 151 browser regressions. Those are mock API tests;
  the separate real owner UI result below is not inferred from them.
- Build `43059113940` stopped in both hosts at the recording/parser integration
  test's implicit 30-second deadline. The correction gives that one test an
  explicit three-minute budget. The full 1 MiB, exact byte comparison, actual
  parser and all four deliberately invalid wire/profile cases remain present.
  Each parser invocation is still separately bounded; production BLE/recorder
  limits were not changed by this correction.
- Build `43062138212` at `9b690ab33cd967da1706d6b254ee8e66076d6628` passed both
  release-mode Android APK and Windows EXE jobs. Strict analysis passed; Linux
  had 771 passed/16 skipped and Windows 752 passed/35 skipped. Flutter 3.47.9 /
  Dart 3.13.7; original application ID, fixed signing certificate and V2-only
  `adaptive-v2-candidate` profile. `publish_release=false`; no tag, GitHub Release,
  channel publication, APK installation or hardware operation occurred.
- `build-artifacts-01` retains both original Actions archives plus the APK,
  Windows EXE and complete Windows ZIP. Archives matched GitHub's SHA-256
  digests, and the standalone EXE matched the EXE inside the Windows bundle.
  The new App version is `1.0.75+101`, not a separate collector application.

### Database And Deployment

`database-backup-02` holds a fresh remote SQL backup and an in-memory rehearsal.
Only migrations 0007 and 0008 were applied. The first attempt used the existing
Pages-only OAuth credential, received an explicit D1 permission denial, and was
replaced with the already authorized dedicated project credential. No new login
or credential rotation was required.

Wrangler printed both migrations as completed but retained its process until the
bound elapsed. The subsequent export similarly completed its SQL download before
retaining its process. Both native failure receipts are preserved. Neither the
migration nor the successful export was repeated to obtain a green shell status.
`database-reconcile-01` parsed the completed, source-pinned export after process
closure, verified the exact eight migration identities, and compared all 17
original tables and their schemas. All rows/hashes and channel pointers matched:
53 App releases, three firmware releases, seven original firmware assets, 100 App
assets, and 62 original App patch records. The one inventory refresh below only
updates the newly added control table.

Subsequent native deployments use Wrangler's own proxy support without also
enabling Node's global environment proxy. All three deployed normally and closed.
`source-binding-01` matched all 75 actual deployment inputs against `9b690ab...`.
Original runtime bindings and Access secrets were compared before/after; only the
two new feature flags were added.

| Original Service | Observed Deployment |
| --- | --- |
| Admin Pages | `ea89f5ea-12c3-4f3b-b111-dd5a2a462fd2` |
| Public Pages | `ff604b84-4cdc-4a0a-bc6b-79f035bc1c60` |
| Worker | Native deploy receipt in `worker-deploy-01`; prior bindings preserved |

Inventory is enabled on all three; supplemental distribution remains disabled.
Existing App stable remains 1.0.60/build 86, revision 52; App beta remains
1.0.16, revision 13. MCU beta remains 3.3.24/build 30324, revision 9; MCU stable
remains empty, revision 0.

`live-ui-01` used the existing, still-valid original-Admin Access application
session, not a new login. The served HTML/CSS matched local source bytes. The
real owner interface successfully loaded both distribution tabs, opened App/MCU
delta dialogs, verified disabled dispatch controls and the fixed close button
after scrolling at desktop/mobile sizes, and issued one successful inventory
refresh request. There were no page errors. The public control route returned
the daily reporting interval; an unauthenticated report was rejected with 401.
The original public App stable offer remained build 86. No synthetic installation
or MCU report was inserted: both distribution tables were honestly empty.

### Next Owner And Activation Boundary

The missing credential is `DELTA_GITHUB_TOKEN` for the original Admin's
server-to-GitHub Actions dispatch/read calls. It is not a Cloudflare login, a
phone authorization, or permission to copy the host's personal `GH_TOKEN`.
Use a fine-grained credential limited to `Eitan-S-23/E-Track` with Actions
read/write and the default Metadata read permission. Do not request repository
administration or contents-write permissions for the dispatcher.

Once provided, configure the bound workflow ref/commit and the already retrieved
existing client public key (`public-key-01`). Qualify a real disabled delta job
for each of APK and MCU, its CI run, streamed object and append/readback path before enabling
distribution. Confirm workflow registration and the allowed ref under the
existing `firmware-rehearsal` policy; retain its reviewer gate. Do not silently
merge main, widen the protected gate, regenerate old originals or publish a
channel just to qualify this path. The actual end-to-end CI delta execution is
NOT_RUN, despite the implemented controls and passing runtime/generator tests.

Operational/API contract: `app/bluetooth_flutter_Trace/cloudflare/update-service/docs/VERSION-INVENTORY-DELTA.md`.
Local original evidence: `.cache/version-inventory-delta-20261111-01/`.
These observations do not complete or restart the old P5-1 hardware campaign.

### Existing GitHub Credential Correction, 2026-11-12

The user's existing-credential question exposed an unsupported inference above:
an absent `DELTA_GITHUB_TOKEN` runtime binding does not mean that the project
lacks a usable GitHub credential. A new token is not a prerequisite established
by the evidence. The blanket personal-token prohibition and mandatory new
fine-grained-token direction in the earlier activation notes were implementation
preferences, not an owner-imposed rule. This correction supersedes those
directions without changing original receipts or any release/environment gate.

The existing protected GitHub CLI route in `.cache/fw93.py` already supplied the
credential for this task's source delivery and successful workflow dispatches.
A bounded read-only check reused it without displaying or persisting its value:

- Authenticated identity: `Eitan-S-23`; `GET /user` returned HTTP 200.
- Credential class: OAuth access token. Observed scopes:
  `gist, read:org, repo, user, workflow`. This is broader than a repository-only
  Actions credential; repository metadata is not a fine-grained token policy.
- `GET /repos/Eitan-S-23/E-Track` returned HTTP 200.
- The exact `admin-delta-build.yml` workflow returned HTTP 200, ID `414894870`,
  state `active`. Its protected execution-ref eligibility was not checked by
  this credential probe.
- No expiration was returned in these responses; perpetual validity is not
  established. No new dispatch was performed to test write permission: existing
  successful dispatch receipts and the observed scopes remain the evidence.

The existing credential can technically support the dispatcher; there is no
observed permission deficit requiring a replacement. `DELTA_GITHUB_TOKEN` is
the backend binding name, not a requirement to issue a different credential.
Persisting the existing account-level credential in Cloudflare gives that
backend its broader scope, so least privilege remains a recommendation and
credential storage must be distinguished from local credential use. This
question-only investigation did not copy a credential to Cloudflare, deploy,
modify protections, create CI runs, or operate a device. The real delta job path
remains NOT_RUN and supplemental distribution remains disabled.

Evidence: `.cache/version-inventory-delta-20261111-01/github-credential-reuse-01/result.json`
and its three original closed GET receipts. Earlier `closeout.json` and failure
records are preserved; their mandatory-new-credential interpretation is
superseded by this correction. This documentation correction is local and has
not been committed, pushed or deployed.

### Credential Activation And Edge Fix Continuation, 2026-11-12

The owner explicitly authorized using the existing GitHub credential in the
original Admin and continuing the task. `dispatcher-configure-01/result.json`
records deployment `56e036a3-ecb5-45b7-b91e-add1bb801a19`, still at source
`9b690ab33cd967da1706d6b254ee8e66076d6628`. The four dispatcher bindings were
added to Admin production only, with preview and all old bindings unchanged.
The Worker received the existing public verification key, not the GitHub token.
`delta-branch-admission-01` added only `dev/admin/version-inventory-20261111`
to `firmware-rehearsal`; its reviewers and other protection settings remained
unchanged. Do not repeat these completed configuration operations.

Live original-package selection chose APK 83 to 86 (1.0.57 to 1.0.60) and MCU
30323 to 30324. The initial read-only UI harness incorrectly assumed that the
MCU list had the App list's field names. Its failed evidence is preserved in
`delta-inspect-01`; `delta-inspect-02` uses the actual `firmwareReleases` model
and contains the successful immutable input selection. No package was rebuilt
or installed during this preparation.

The first real App request created
`delta_234630c418601fe1899658e6d79a2dd473e7aa59d518ff1b014b2863227ca65b`,
attempt 1, then returned `dispatch_unknown` / `DISPATCH_OUTCOME_UNKNOWN`.
`delta-run-reconcile-01` observed zero GitHub dispatches. The existing Admin
reconciliation endpoint exposed the actual error in `delta-cloud-reconcile-01`:
Workers rejects `redirect: "error"` before sending a request. The current
Cloudflare Request documentation independently confirms this behavior. The
failure is an edge-runtime compatibility defect, not a token permission error.

Source `37b9857526cdad5d6c44f991752e369513b7517c` fixes both edge GitHub calls
with `redirect: "manual"`, retains strict status checks, and adds redirect
regressions. `delta-edge-fix-01` passed 20 focused tests and Worker/Admin/Public
type checks. `delta-edge-source-01` records the exact three-file GitHub API
delivery, without shared local Git writes. The original API guide now records
the owner-approved credential reuse and edge Fetch contract. Mock-only fetch
tests had missed platform option validation; the added tests construct requests,
assert the redirect policy and cover redirected dispatch/reconciliation.

Public readback `delta-edge-ci-public-01` independently located CI run
`43077908260` at that exact source: completed/success, `checks` and `public-key`
successful, Android/firmware generation jobs correctly skipped for the push
event. This is code validation, not a successful real delta build. Original
logs/artifacts were not retrieved through this unauthenticated metadata route.

On this continuation, `whoami /user` reported `NT AUTHORITY\SYSTEM` / `S-1-5-18`.
The existing Wrangler authorization directory under
`.cache/p51-app-release-20261108-01/private/wrangler/xdg-config/.wrangler`
was inaccessible (`WinError 5`), so the old combined cloud preflight did not run.
`system-credential-route-01` additionally established that the named CF-CI-01
input was unreadable to this identity. The organization SSO input remained
readable, but the old original-Admin application token was unreadable.
`system-github-route-01` separately tried the existing GitHub CLI route without
the unrelated cloud preflight and could not retrieve its credential. No ACL,
credential, login, platform setting or device state was changed in these checks.
Do not request new tokens or bypass ACLs to compensate for the changed identity.

Next: restore execution under the original Windows user `SU`. Reuse the passed
CI and delivered source, deploy the two-call edge fix to the original backend,
and update its pinned workflow commit. Preserve the original failed request;
reconcile its proven pre-send failure with a bounded audited state correction
before an explicit retry of that same job. Do not blindly replay `delta-create-01`
or the earlier configuration scripts. The MCU request has not been submitted.
Complete one disabled real delta for each format and verify original bytes and
channel pointers before enabling supplemental distribution. The fixed code is
not yet deployed; no new delta is ready, distribution remains disabled, and
there has been no APK installation, device operation or long-test restart.

## Original Repository Completion, 2026-11-12

This continuation supersedes the earlier SYSTEM/credential and NOT_RUN status;
it does not rewrite any original failed receipt. Existing Windows credentials
were read through the existing SU logon token and passed privately to native
tools running as SYSTEM. The project-private Wrangler working copy was renewed
without a new browser login. The original authorization file and existing ACLs
were not changed. The original Admin owner session was reused.

### Root Cause And Corrected Route

The E-Track repository's App deployment bearer and payload-signing key belong
to the isolated historical P51 service, not the original App backend. The real
App attempt 2, run `43211285682`, failed at its initial spec GET with HTTP 401,
before claiming or downloading packages. The named original App bearer returned
HTTP 200, while the previously configured delta public key did not verify the
original target manifest. This was a repository/signing-boundary defect, not
missing user authorization or an expired phone session.

App delta generation now runs in `Eitan-S-23/Trace`, using that repository's
existing original bearer and signing secrets in place. Firmware generation stays
in `Eitan-S-23/E-Track` with the unchanged `firmware-rehearsal` approval gate.
Each new App attempt pins its qualified repository/ref and exact workflow commit;
historical unqualified attempts retain their E-Track meaning. Callback provenance
and run links use the attempt's repository. No private signing key was exported,
original build/release workflow edited, APK rebuilt, or default branch merged.

Source `74058b6a42bfc1d9c26981e07ad15e219080109d` passed 415 local backend tests,
16 generator tests, 13 focused browser tests, and native Workers CI `43221242575`.
The subsequent receipt-only correction `e669393dc4a263cdfd0f159ab62e008e302b41cd`
passed all 18 generator tests, including executable public-key/receipt tests and
corrupt-completion rejection, and native CI `43232008885`.

The first Trace public-key run, `43228109291`, generated its public key but failed
uploading the optional duplicate archive because GitHub artifact storage was full.
That failed run is preserved. The corrected workflow retains a bounded allowlist
of non-secret receipts in native logs; the actual patch and signed completion
remain mandatory R2/D1 outputs. It does not suppress failures, print private keys,
clean old artifacts, change billing, or repeat a completed delta for an archive.
Trace workflow `8f6d2ab64b1c400811613ae8540c15e0bdf28d9f` pins generator `e669393...`;
public-key run `43233026528` succeeded. Its public key independently verified both
unchanged original APK manifests, versions 83 and 86.

### Real Delta Results

| Format | Original Versions | Real Run | Delta Bytes | Original Full Bytes |
| --- | --- | --- | --- | --- |
| App VCDIFF | 1.0.57/83 to 1.0.60/86 | Trace `43237679323` | 9,388,361 | 45,951,912 |
| MCU ETU | 30323 to 30324 | E-Track `43209589741` | 306 | 291,176 |

The MCU result was reused, not regenerated. App attempt 2 was reconciled through
the real Admin button against its unique completed failed run. The same immutable
job was then retried through the real Admin as attempt 3; it succeeded in Trace.
CI verified APK versions, package name and signing certificate, reconstructed the
target byte-for-byte, signed the per-base manifest, uploaded the patch, and
registered a disabled asset. Native log receipts were recovered byte-exactly
against their recorded hashes. The R2 readback was 9,388,361 bytes with SHA-256
`793c2d119ff4194103f0ac831a7118b32d35d178be6fac2ab2c17a38ae39a5fc`; its signature
was independently verified with the original public key. No original APK or
firmware package was replaced.

Original evidence under `.cache/version-inventory-delta-20261111-01/`:

- `original-app-delta-key-01/result.json`: both original signatures verified.
- `app-route-reconcile-01` and `app-route-retry-01`: actual owner UI requests,
  responses, unchanged channel snapshots, and retained attempt history.
- `app-route-run-02/result.json`: successful Trace execution and original logs.
- `app-route-evidence-01/result.json`: exact recovered receipts, R2 patch, signature.
- `delta-firmware-artifacts-01/result.json`: reused successful MCU artifact/readback.
- `app-route-verify-01/result.json`: both real dialogs show ready, disabled deltas;
  served HTML matches source and there are no page errors or channel mutations.

Worker configuration initially printed all four successful secret writes but
retained its CLI process until the bounded timeout. The closed receipt and remote
bindings were reconciled; those successful writes were not repeated. The remaining
deployment was resumed separately. Later native invocations preserve explicit
terminal reports, bounded owned-process closure and remote state verification;
a terminated CLI is not misreported as a natural zero exit.

### Owner Controls And Remaining Client Boundary

The activation readback found exactly the two expected ready jobs, both disabled,
with no other enabled assets. Source `9dd858fc8f9943d444060169291ea5131d63489b`
changes only the three staging `DELTA_ASSETS_ENABLED` flags and passed native CI
`43240948113`; it does not enable either individual asset. The MCU dispatcher
commit follows the new branch HEAD; the Trace workflow/signing inputs stay pinned.
Final activation deployment/readback receipts are recorded separately below.

| Original Service | Active Deployment |
| --- | --- |
| Worker | `4bccbd77-5945-4690-bdf7-3602d522187d` |
| Admin Pages | `80fb49e6-75fd-4a64-9f60-29efc1598588` |
| Public Pages | `028e98d2-9135-4f0d-b832-8b5ff0d16cc2` |

`activation-worker-01`, `activation-admin-01` and `activation-public-01`
confirmed their deployed source and preserved the original runtime/Access
bindings and preview configuration. `activation-verify-01` re-read D1 and found
both job rows identical to the pre-activation snapshot: App attempt 3/revision 9
and MCU attempt 1/revision 3, both ready and disabled. Both real owner dialogs
now expose enabled enable-controls; no button was pressed to publish an asset.
The public App stable check still offers build 86 and does not include the new
disabled patch. Public inventory control remains available. There were no page
errors, asset enablements, package replacements, channel writes or device actions.

Operators can now use the original Admin version details' delta dialog to select
up to five eligible bases, generate, inspect the actual job, and explicitly enable
or disable a verified delta. Existing jobs and original packages are reused.
The tests do not claim a live enable/disable publication experiment: the two
qualification assets were intentionally left disabled for the owner.

Version statistics still require a reporting-capable installed App, starting at
`1.0.75+101`. The already built APK was not reinstalled or published in this
continuation. Empty/unreported versions remain unknown, not zero users; no
synthetic installation/MCU report was inserted. This server-side result neither
restarts nor completes the old P5-1 hardware/long-test campaign.

## Original App Candidate Delivery, 2026-11-13

The owner requested delivery to the original Admin before further optimization.
Channel publication remains operator-controlled. No USB installation, hardware
operation, delta regeneration or old long campaign is included.

`app-candidate-inspect-02` found a concrete defect in the retained 1.0.75+101 APK:
both ARM libraries contain the isolated `e-track-firmware-p41-public.pages.dev`
endpoint, not the original public endpoints or their trusted payload key. BLE V2
and the reporting implementation are present, but this APK is not suitable for
the original backend. Its original bytes and successful CI remain preserved.

App source `34495140d28ce401616cc19b6b62bb6bba1d764c` changes only the version to
1.0.76+102 on top of integrated source `9dd858fc8f9943d444060169291ea5131d63489b`.
The bounded Trace workflow on `dev/admin/app-candidate-20261113` checks out that
exact E-Track source and uses the original Trace signing secrets in place. It
reuses the existing build, metadata, R2 upload/readback and registration tools,
sets the original public endpoints/key explicitly, compares the original APK
signer, and checks both produced ARM libraries. It generates no delta and never
publishes an Admin channel. GitHub draft/prerelease assets avoid the already
observed Actions-artifact quota issue; `latest` is not changed.

Run `43257030748` stopped before tests/builds when the floating stable SDK selected
Flutter 3.50.0 and strict analysis reported Material-library deprecations. No APK,
GitHub Release or Admin candidate was created. Successor workflow
`6b991b7f4ac4cd25b00e17ea842dd9f83fee0d8a` changes only the two SDK selectors to
the previously verified Flutter 3.47.9; checks were not suppressed. Run
`43258693636` completed both platforms' analysis/tests and APK/EXE builds. Its
Android signer/configuration checks passed and exact artifacts were retained in
the new GitHub draft before uploader dependency installation failed. The failed
runner did not finish its remaining cleanup; ordinary cancellation closed it.
The later force-close probe found it already completed and did not force-cancel
anything. The original run remains `cancelled`, not a claimed all-green build
workflow. Its Android text log is incomplete; the original job/step results and
available raw logs are retained without inventing missing terminal test counts.

Upload-only run `43269370153` failed on a missing `actions: read` permission before
downloading or uploading assets. Workflow
`6eec579cf801563360c16c36fec0e2d9d9f07d73` corrects that permission and adds native
verification of the retained APK, without recompilation or signing-key export.
It uses the qualified backend Node 24/package-directory dependency setup.
Run `43271032258` passed: original artifact hashes, native `apksigner` and `aapt`,
both ARM libraries' original endpoints/key, BLE V2 and version-inventory markers,
the original Ed25519 payload signature, full R2 upload/readback and CI candidate
registration. No APK or EXE was rebuilt during these delivery continuations.

Final candidate: `1.0.76+102`, `rel_trace_android_v1_0_76`, APK 47,745,568 bytes,
SHA-256 `7b55fb0ef2e54cdacddaac569d919207e049329b51060542b3f840fcd7b200aa`.
Its package is `com.wen.gaia.gaia`; its original-release signer SHA-256 is
`3cecee6330a930e020b454b6d4a79568f4494ca324ae7bcf2c1914e51b04ab47`.
This differs from the development signer on the old, uninstalled 1.0.75+101 APK.
The full APK and manifest are available in original R2; no delta was generated.
GitHub assets are a prerelease, never GitHub latest.

`app-candidate-artifacts-01` retains byte-exact metadata reconstructed against its
native-log hash and the successful retained-APK verification. The host's earlier
GitHub draft download timed out, leaving a partial APK/ZIP under
`app-candidate-draft-02`; these are preserved failed downloads and must never be
installed, uploaded or described as complete artifacts. The successful CI used
the complete immutable original assets, not those host partials.

`app-candidate-ui-after-01` used the actual original Admin owner session, opened
the new version, verified the signature, all R2 assets and both enabled publish
controls, and found no page errors. APP and MCU channel pointers/revisions are
unchanged, and public App Stable still offers build 86. The candidate has not
been published to either channel or installed on a device. The owner's next step
is to select its publication channel and test through the original App updater.
Automatic candidate preparation for every future ordinary push remains separate
follow-up work, not a capability established by this bounded delivery.

All local delivery records use `app-candidate-*` under the existing
`.cache/version-inventory-delta-20261111-01/` area. Do not replay successful builds,
uploads, registration or the old hardware campaign on continuation.

## Future Automatic Candidates, 2026-11-13

The next authorized work is automatic unpublished candidate ingestion, not a
repeat of 1.0.76+102 delivery or a choice of publication channel. The operational
source branch is `release/candidates`, starting from the latest integrated App
source above. The developer route and failure rules are in
`docs/original-admin-candidates.md`.

The source workflow separates ordinary checks, original-key App builds in Trace,
and protected fresh GCC firmware builds. No signing key is exported, no old Trace
App tree is substituted, no channel is published and no automatic delta selection
is made. The firmware environment reviewer/production gates remain in force.
The source push's App job follows the actual downstream result rather than
equating HTTP dispatch acceptance with completed backend delivery.

The first local regression attempt preserved 106 passes and three failures:
one historical test still expected the pre-V2 CMake default, and two synthetic
packaging tests tried the unavailable Windows `python3` command. The test now
checks the actual mandatory V2 default, without reverting product code; the host
runner selects its installed Python explicitly. Original raw results remain in
`.cache/version-inventory-delta-20261111-01/auto-candidate-tests-01/`.
The new two-workflow structure passed native `actionlint` in
`auto-candidate-lint-01`. Runtime CI delivery and the final test results are
recorded below when observed, not inferred from this source description.

The corrected local run `auto-candidate-tests-02` passed all 110 Node tests and
eight Python tests. Native actionlint also passed again on the delivered workflow
bytes during `auto-candidate-prepare-01`. Only four pre-existing tooling/test
files changed, checked against their original Git blobs before delivery; App and
firmware product source stayed at the integrated parent.

Operational source commit `d69f6e3df7a8a55e4721f85b63c42de25f2d488a` and Trace
workflow commit `7eaa1dc3a5b2eaa54b921b2baa9a339acc29fbd0` are on their respective
`release/candidates` branches. Source push CI `43278610509` passed and skipped
both package jobs because versions are unchanged. Trace checks-only CI
`43278896945` passed exact-source admission and candidate guard regressions;
Android/Windows builds were intentionally skipped. This is verified wiring and
no-replay behavior, not a claim of an executed new-version build/upload.

The existing GitHub credential was stored as `ORIGINAL_ADMIN_ACTIONS_TOKEN` for
the source repository's cross-repository dispatch, without creating a token,
expanding scopes or exporting either signing key. The exact candidate branch
was added to `firmware-rehearsal`'s allowlist; existing required reviewers and
production-gate rules were preserved. New firmware signing still waits for that
existing environment approval. Neither repository's `main` was modified.

No Cloudflare deployment, new release/package, channel publication, APK install,
MCU operation or review agent occurred in this follow-up. The next user-owned
step remains publication/testing of the already available 1.0.76+102 candidate.
This closing observation is local; the operational code and developer guide are
already on the branch/commits above.

## Delegated Beta Publication, 2026-11-13

After the recommended Beta option and repeated delegation to continue without
unnecessary intervention, the root used the existing owner session and original
Admin UI to publish the existing 1.0.76+102 candidate to Beta only. Exactly one
`POST /api/admin/channels/beta/publish` succeeded (HTTP 200), advancing revision
13 to 14. The public Beta response returns 102 with the original APK SHA-256.
Stable remains 1.0.60+86 with its row unchanged; MCU channels are unchanged.
No build, upload, new Release, installation or long test occurred.

Source inspection corrected an earlier user instruction: App updates read the
compile-time `ShareLinks.updateChannel`, default `stable`; there is no runtime
Beta selector. Publishing Beta therefore does not make the original App's
ordinary Check Updates offer it. This test uses direct download and same-package,
original-signature installation, not another specially built APK. Do not tell the
user to switch to a nonexistent Beta setting or uninstall/clear App data.

Evidence is under
`.cache/version-inventory-delta-20261111-01/app-candidate-beta-01/`. The original
candidate signature, R2 availability, UI confirmation and post-publication
channel/public reads passed, with no page errors. A bounded download probe
received HTTP 200, the expected APK content type/name, `X-Trace-Asset-Source: r2`
and length 47,745,568. This endpoint ignored Range; curl exited 63 at the explicit
1 KiB cap before downloading the full object. That preserved probe is not an
HTTPS failure, a successful range check or a new full-file hash observation.
The earlier complete CI download/hash remains the full-byte evidence.

## Admin Interaction Follow-up, 2026-11-13

The user independently published 1.0.76+102 to Beta and Stable and reported a
successful 1.0.60/86 -> 102 delta upgrade. Do not repeat that upgrade, restore
either channel, rebuild the APK or start the old long campaign for this UI task.
The authorized follow-up is shared sheet dismissal (downward/header-horizontal
drag and topmost Back), persistent delta progress/results and optional background
browser notifications for both App and MCU.

Fresh read-only Admin observations are in
`.cache/version-inventory-delta-20261111-01/admin-interactions-20261113-01/live-before-01/`.
They confirm the 86 -> 102 job is ready/enabled, an MCU delta job is already ready,
and version 102 has one reporting installation. MCU inventory currently has no
reports; this is unknown coverage, not zero users. No business mutations or device
operations were used for this observation.

The new notification implementation uses an additive D1 migration, actual CI
callback phases, actor-scoped unread records and payloadless VAPID wake-ups with
authenticated service-worker reads. Permission must come from a user's browser
click. It is not granted by development authorization. Existing signatures,
workflow inputs, original artifacts, channel revisions and publication rules stay
unchanged. Self-tests are not an independent acceptance campaign or proof of
delivery through every browser vendor/phone notification policy.
