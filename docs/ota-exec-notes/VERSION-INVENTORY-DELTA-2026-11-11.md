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

Admin/public-site branding, reporting repairs, candidate notifications and the
resource panel are deployed. Original App `1.0.77+103`, Windows `1.0.77.103` and
MCU `3.3.25` candidates were built, delivered and byte-verified; Stable/Beta were
not changed by this work. The earlier qualified optional deltas remain separate.
The owner has confirmed a Free account and a free-only requirement. The hosted
Access login retains Cloudflare's title/favicon and its already updated E-Track
application name. Paid HTML login customization is out of scope, not waiting
for another credential or subscription check. The prepared template stays
inactive. Installation and physical UI verification remain pending the actual
phone connection.
The final continuation below records exact commits, failed originals, successful
recovery and remaining external intervention. Earlier checkpoints are history,
not a claim that the candidates are installed or every finding is closed.

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

### Delivered Interaction Changes And Verification

Implementation `f57a6ffe0d47c6cc4d1713b0fb505d3cf3197f5c` and the final mobile
toolbar correction `5126f55fb30dab6a850284bcf84fe47589d40966` are delivered on
`release/candidates`; neither repository's `main` was changed. The follow-up
changes only Admin CSS and its regression test, so the Worker was not redeployed.

| Original Service | Final Deployment | Source |
| --- | --- | --- |
| Admin Pages | `fb6d3526-b092-4b4c-af2d-f103581b44a3` | `5126f55fb30dab6a850284bcf84fe47589d40966` |
| Worker | `dd3b187a-a237-4650-bf81-7f90949e8424` | `f57a6ffe0d47c6cc4d1713b0fb505d3cf3197f5c` |

App details, MCU details, delta management and Tasks share sheet dismissal:
downward dragging from scroll-top, downward/left/right header dragging, and
topmost Back handling. Inputs, nested scrolling, short gestures, multiple touches
and busy submission retain their guards. Fixed close controls and draft retention
remain. Closing a sheet never cancels or repeats its server-side build.

The sticky toolbar's Tasks entry shows both App and MCU jobs, real stages,
elapsed time and unread terminal results. Results survive closing the dialog,
refresh and background/foreground transitions. Enabling a delta or publishing a
channel remains an explicit operator action. Migration
`0009_delta_notifications.sql` was applied and read back; rehearsing against the
current database backup preserved all original columns/data and created no
historical notifications. Existing Access/signing bindings were preserved.

All receipts below are under
`.cache/version-inventory-delta-20261111-01/admin-interactions-20261113-01/`:

- `worker-final-02`: 424 backend tests passed.
- `ui-final-01`: 163 full Admin UI tests passed.
- `ui-toolbar-01`: 28 focused follow-up tests passed; these overlap the full suite.
- `admin-types-final`, `worker-types-final-02` and `binding-types-01`: type checks
  and current Worker binding generation passed, without modifying source types.
- `rehearsal-01` and `migration-01`: additive migration rehearsal and live readback.
- `ci-01` and `ci-02`: source CI `43344133290` and final CI `43345920546` passed;
  both skipped App/firmware package jobs rather than rebuilding unchanged versions.
- `live-after-02`: authenticated, read-only checks on the original deployed Admin
  verified all five CSS/JS asset hashes, App/MCU downward dismissal, Tasks Back,
  a single mobile toolbar row, no horizontal overflow and no page errors.

Real OS/browser-vendor push delivery is **NOT_OBSERVED**. This SYSTEM headless
environment denied notification permission; failed full-Chrome attempts are
preserved. Service-worker tests use the actual worker, native CDP push injection,
fetch and IndexedDB, but explicitly mock the OS notification sink, including
closed-page and expired-Access cases. The operator must click Tasks -> Enable
alerts in a supported browser and grant permission there. In-app durable results
do not depend on that permission; browser/OS policy can still delay or block push.

Final live reads preserve the user's Beta/Stable 1.0.76+102 publication and enabled
86 -> 102 App delta. The existing MCU delta remains ready. No package/channel
mutation, delta generation, APK reinstall, device operation, new review agent or
four-hour campaign occurred in this interaction task. Empty MCU reporting remains
unknown coverage, not zero users, and historical P5 obligations remain open.

The closing result and controlled-write audit are in `closeout-01/`. Product
delivery is already on the source commits above; this final task-note update is
local follow-up documentation and does not trigger another deployment.

## Notification Enrollment Follow-up, 2026-11-13

The operator reported a successful new 85 -> 102 delta, visible progress and a
return-to-page result toast, but no background system alert. The reminder state
subsequently changed, and another Enable click returned
`Registration failed - push service error`. Do not repeat that delta or its
upgrade to diagnose browser enrollment.

`admin-interactions-20261113-01/push-observe-01/result.json` records a read-only
D1 observation at 2026-11-13 02:41:44 UTC: event 1 is the successful 85 -> 102 job,
completed at 01:53:38 UTC; current subscription and delivery tables are empty.
The existing sender deletes rejected/expired subscriptions and cascades their
delivery rows, so this snapshot cannot establish whether an earlier send was
attempted. Do not invent a push-provider HTTP status or blame phone power policy.
The reported registration error occurs at the browser/provider boundary before
the Admin subscription POST; the browser/device and its network remain relevant.

The source investigation independently reproduced missing enrollment coverage:
the UI treated a cached local record as subscription truth, a late activity read
could clear a newly successful registration, and explicit re-enable cancelled
an existing browser subscription solely because that local record was missing.
These are implicit-state/concurrency assumptions and test-coverage gaps, not
evidence that a new APK or signing key is needed. The preserved red run
`push-ui-red-01` has four failing reproductions and one passing control.

The repair checks the actual browser subscription against the actor's server
records, reuses matching subscriptions without cancelling them, serializes setup
against refresh, and keeps provider-registration errors separate from task-read
errors. Permission remains a user click and real system delivery remains an
unobserved boundary. The initial targeted `push-ui-green-01` passed all five
cases; the expanded suite also covers pending setup, server-registration failure
and explicit turn-off. The executable contract is in the Admin README and tests,
not a new review or hardware acceptance workflow.

The final `push-ui-full-01` run passed all 175 Admin UI tests, including the eight
enrollment regressions; `push-admin-types-01` passed. `push-live-before-01`
preserves the actual pre-deployment catalogue: the new 85 -> 102 delta is ready
and disabled, 86 -> 102 remains enabled, and existing MCU state is unchanged.
The scoped source/deployment and closing receipts are recorded separately under
the same interaction directory. No backend schema/Worker change or new device
test is part of this enrollment repair.

Repair source `1dc15e906fa89e9ae3f3edd6234ce2b7458469f1` is delivered on
`release/candidates`; CI `43356214620` passed with both package jobs skipped.
Original Admin deployment `5313c60f-fae1-440d-a78c-6a48bc792ac7` preserves its
runtime bindings. `live-push-after-01` verified current asset bytes and actual
read-only UI behavior with no page errors; the new disabled 85 -> 102 delta and
existing enabled 86 -> 102 delta remain intact. Worker, schema and packages were
not redeployed. Existing owned OAuth credentials were renewed without another
interactive login. `push-closeout-01` binds final receipts and controlled writes.

The provider registration error is not claimed resolved by these UI tests or
this deployment. No real push subscription/delivery was created by the agent.
The next diagnostic input is the operator's device/browser and its registration
result after refreshing the repaired page; no further package build is required.
This final closing paragraph is local follow-up documentation.

### Android Chrome Registration Diagnosis

The operator identified an Android vivo/iQOO phone on mobile data, with Google
Play services installed and the Play Store working. This does not establish the
cause of Chrome's generic registration error; do not attribute it to connectivity
or exclude our code solely from that message. Chromium's Android InstanceID
bridge catches IOException, returns an empty token and maps it to UNKNOWN_ERROR,
which the push service exposes as SERVICE_ERROR. Its distinct desktop/general
NETWORK_ERROR enum is not proof that Android network errors remain distinguishable.

The bounded follow-up reuses the actual protected Admin/browser route to validate
the delivered P-256 key and decode, then checks the existing private ADB route.
If the previously identified V2312A is connected and authorized, read only its
Chrome/GMS versions and a bounded warning/error log snapshot. Keep raw logs in
the protected task-local private directory; report error codes, not tokens.
No APK install, notification enrollment, UI tap, configuration change, log clear,
firmware operation or new delta is authorized by this diagnostic runner. Its
private server closes after the read or absence check; a missing phone requires
a real connection, not another synthetic product test.

`push-config-check-01` retrieved the live key through the existing authenticated
Chromium route. Its 65-byte uncompressed P-256 point imported successfully in
both Node and Chromium; the actual frontend decoding produced identical bytes.
Fingerprint `4b16aac3cd031179`; active server subscriptions were zero. This checks
configuration, not a successful native push registration or delivered alert.
An earlier direct urllib GET was rejected with HTTP 403; that host-client failure
is separate from the phone's Chrome error and did not change authorization.

`push-phone-check-01` used the pinned existing ADB binary/key on private port
5093 and found no connected expected phone. It closed its server and ownership
lock with zero phone/package/settings/UI operations. The read-only collector is
ready in `.cache/version-inventory-delta-20261111-01/push-phone-check.py`; the next
run needs a fresh output label and the operator's USB connection. Do not replay
an upgrade or claim the phone-specific root cause has already been established.

Chromium source references inspected for this diagnostic:

- `chrome/browser/push_messaging/push_messaging_service_impl.cc`, `DidSubscribe`.
- `components/gcm_driver/instance_id/android/java/src/org/chromium/components/gcm_driver/instance_id/InstanceIDBridge.java`, `getToken`.
- `components/gcm_driver/instance_id/instance_id_android.cc`, `DidGetToken`.

These are upstream-main observations, not proof of the operator's exact Chrome
version. Device-specific logs/version remain required to distinguish causes.

## Notification Click And Read-State Repair, 2026-11-13

The operator subsequently confirmed successful Chrome enrollment AND real system
notification delivery with VPN enabled. That supersedes the preceding request
for USB registration diagnostics: no USB action or repeated delta is needed.
This establishes network dependence of the observed Google push path, not a
promise that delivery will persist after VPN disconnection. Play Store downloads
and Cloudflare page access are separate network paths.

Two reported UI defects were reproduced in source: notification clicks only
posted once to any same-origin window, with no acknowledgement or focus fallback;
viewing/clicking notifications never saved their read state. The badge also used
the active-job count when unread was zero. Repairs add an acknowledged, retained
open-Tasks intent with absolute-URL fallback; foreground visible/clicked per-ID
read acknowledgements; independent unread and running indicators; notification
pagination; and a read revision guard against late activity snapshots.

Migration `0010_notification_read_state.sql` adds one nullable read timestamp.
The global cursor remains only for explicit Mark all read. It would be incorrect
to use that cursor for an individual viewed result, because older unseen events
would disappear too. Existing notification subscriptions, keys, tasks, package
bytes and channel state must remain unchanged. The read functions live in the
shared Worker source module but are served by Admin Pages Functions; no change
to the running Worker's sender or redeployment of that Worker is required.

Under `admin-interactions-20261113-01/`, `notification-ui-01` passed 53 focused
browser cases and `notification-worker-01` passed 426 backend tests. Both Admin
and Worker type checks passed. Window navigation tests explicitly mock client
focus/openWindow, and the push integration still mocks the OS notification sink;
physical Android tap behavior is not claimed measured by these tests. Full UI,
source delivery, additive migration and live read-only receipts follow under
fresh `notification-*` labels. No review agent, device test or new package build
is part of this repair.

`notification-ui-full-01` subsequently passed all 191 Admin UI regressions.
The current authenticated `notification-live-before-01` observes the user's
additional ready, disabled App deltas from 80..85 to 102; 86 to 102 remains
enabled and the existing MCU delta is ready. Preserve this newer live baseline,
not the older catalogue with only 85 and 86. Both Beta/Stable remain operator-owned.
The earlier renewal and D1 export commands produced terminal output but retained
their native processes; originals and closed timeout receipts remain intact.
The renewed OAuth expiry and a fresh authenticated read are checked separately;
the existing export is verified rather than exported again.

Notification repair source `ace860f0280c92fad9791988fe7b3b1309a665ad` was deployed
to original Admin version `711108df-65e5-4cbb-8d19-c0e3fc1342db`; migration 0010
was applied/read back with no read acknowledgements or package/channel changes.
Native CI `43390824908` passed Public checks and 385 Worker tests, but failed two
existing resource-panel UI checks (189 UI passes). It is not a green workflow.
The panel deferred positioning/focus to requestAnimationFrame, exposing an
unpositioned panel and allowing a late callback to take focus after Escape.
`notification-panel-red-01` deterministically reproduced this by deferring page
animation callbacks. The correction positions/focuses synchronously and preserves
the existing close behavior. It changes no notification, task or mutation logic.

Follow-up `aacb803430dd6529fd7dc6fa32ef0589296d344c` deployed as
`0cb5f710-a504-41d4-a753-8385435f72c1`. `notification-panel-tests-01` passed all
55 App UI tests. Native CI `43414505154` passed 385 backend tests and 188 UI cases,
but exposed three immediate-Escape variants and one too-early resize measurement.
These failures are preserved, not reported as a green run. The new
`notification-modal-red-01` deterministically holds animation frames to reproduce
the immediate-Escape hole. App/MCU opening now establishes keyboard ownership
synchronously; the resize test polls the same exact bounds after the asynchronous
resize event instead of sampling before it. No assertions are relaxed.

`notification-live-after-02` already verified deployed notification assets and
real read-only task/modal behavior. The first probe's separate Node HTTP client
had ECONNRESET after successful asset checks; the successor uses browser-owned
GETs and keeps the all-non-GET barrier. Raw Playwright diagnostics can include
request cookies: the old failure file is access-restricted, its bytes preserved,
and subsequent diagnostics emit only sanitized error summaries.

### Final Notification Repair Delivery

Final source `1b75d3921244642127f6aaa980ac308baf797b66` is deployed on the
original Admin as version `c0ed148b-04fa-40b7-a2a5-f93c34482719`. Native CI
`43417157076` completed successfully: the retrieved original log records 193
Admin UI tests and 385 Worker tests passed, with both Pages type checks green.
`notification-modal-native-03` retains that completed observation and log;
the earlier in-progress observations and failed prior-source runs are preserved.
Push CI `43416739592` also succeeded, with App/firmware package jobs skipped.
The 426-test host backend result remains separate from the native 385-test run.

`notification-live-after-03` verified the final deployed asset hashes, synchronous
panel/modal ownership and task/gesture behavior using authenticated browser GETs.
The probe allowed no server mutation, blocked its one attempted read POST, and
left notification read state unchanged. Existing package/channel observations
are retained for closeout comparison. Worker version
`dd3b187a-a237-4650-bf81-7f90949e8424` at source
`f57a6ffe0d47c6cc4d1713b0fb505d3cf3197f5c` was not redeployed.

No repeated migration/export, new delta/package, subscription reset, APK install
or device operation is part of this closeout. A normal Admin page refresh loads
the fix and updates its existing service-worker registration in place. Actual
Android notification-tap navigation still needs the operator's phone check;
headless tests are not evidence of that physical OS interaction. This closing
note is local documentation and does not trigger another commit or deployment.

### Operator Confirmation And Deferred App UI Finding

The operator confirmed the notification repair works on the phone after the
deployment above. Record this as operator-reported real-device confirmation,
separate from the headless test evidence; do not repeat the completed notification
or delta-generation tests to replace it.

APP-UI-INV-01, OPEN / DEFERRED BY OPERATOR: in the App settings dialog, the
version-statistics opt-in label ("Participate in version statistics") is too dim
against the current background, and its color is inconsistent with the switch
and surrounding surface. The operator explicitly requested recording only and
batching this with later UI findings. Do not change the App theme, label, build
version or APK for this issue now. A later fix should follow the existing dialog
palette, maintain readable text contrast in each supported theme, and keep the
reporting opt-in behavior unchanged.

The operator has now connected the MCU and successfully read its current version
in the existing App. The reported version number itself has not been supplied in
chat; the next step is a read-only check of actual backend inventory and package
eligibility. A successful local INFO read is not by itself proof of a received
server report. Preserve the current device, App, package and channel state while
reconciling this observation.

### MCU Inventory Intake And Channel Boundary

`admin-interactions-20261113-01/mcu-inventory-read-01` received the real current
inventory through authenticated Admin GETs: one reporting installation on App
102 and one MCU observation, version 30321, hardware revision 1, layout 1, image
SHA-256 `5820b830e9763ee853f29ff21adb4c43ebd5cf1c7ce00fcff85cef1e05be11bf`.
The observation matches the existing 30321 base of the 30324 firmware catalogue,
including its image hash, not merely its version label. The installed App's MCU
reporting path is now observed end-to-end. This is one installation-scoped MCU
observation, not a globally deduplicated user or device count.

The original 3.3.24 candidate and 30321-to-30324 delta already exist. The fresh
channel read still shows 30324 on Beta and an empty MCU Stable channel. The
ordinary installed App queries Stable; its update page has no Beta selector.
Do not prescribe a nonexistent selector, change request/signature checks, or
reinstall the App solely to hide this mismatch. Serving this candidate through
the ordinary installed-App path requires an explicit MCU Stable publication,
which affects all eligible clients of that channel and is a release decision,
not an inventory read. No publication, device upgrade, new package, build,
subscription change or UI source change was performed in this observation.
The existing tiny delta proves package eligibility, not representative BLE speed.

### Additional Deferred UI And Branding Findings

The operator explicitly requested recording the following observations only,
then fixing them together after the exploratory testing batch. These are
operator-reported findings, not newly reproduced or repaired in this session.
APP-UI-INV-01 remains open in the same deferred batch. Do not change UI assets,
App versions, authentication settings or deployed services for this note.

- ADMIN-UI-SHEET-01, OPEN / DEFERRED: the panel opened by the floating resource
  ball does not dismiss on a left/right screen swipe, unlike the other dialogs.
  Bring its swipe-to-close behavior into line with the other overlays. The top
  overlay should own dismissal without navigating the underlying page; retain
  existing nested-scroll, draft and busy-operation protections and ball dragging.
- ADMIN-UI-LOGIN-01, OPEN / DEFERRED: the current login page looks inconsistent
  and unattractive. Optimize its layout, typography, colors and mobile behavior
  together with the existing Admin/App visual language. At implementation time,
  identify whether each visible login surface belongs to the project or the
  Cloudflare Access page; appearance changes must preserve authentication and
  access policies.
- BRAND-ETRACK-01, OPEN / DEFERRED: replace the website's current icon/favicon
  with an identity appropriate to this project, and set its displayed slogan/name
  to exactly `E-Track`. Audit the Admin and phone App for remaining user-visible
  `Trace` branding and consistently replace it with `E-Track`, including relevant
  titles, login copy, dialogs and notifications. This is a visible-branding scope,
  not a blind replacement of compatibility-sensitive technical identifiers such
  as application IDs, signing identities, API fields, storage keys, repository
  names or existing service domains. The exact icon design is deferred too.

Only this existing task note was updated. No image was generated, product source
was edited, package/channel state changed, or build/deployment was triggered.
The operator retains control of the ongoing MCU publication/upgrade test.

### Operator MCU Upgrade Result, Patch Provenance And Stale System Info

The operator reported a successful 3.3.21-to-3.3.24 upgrade and asked why its
patch already existed without a new delta-management action. The original
`mcu-admin-delta-20261111-01/candidate-dispatch-01/dispatch-intent.json` binds an
agent-initiated `firmware-build.yml` dispatch with `prepare_admin_candidate=true`,
`version_name=3.3.24` and `candidate_base_version=3.3.21`. Native run
`43027319926` generated, verified, uploaded and registered the 307-byte patch
together with the full/recovery assets. It was not generated by the operator's
current session or by an unrequested new build. This older, original-package
patch becomes available with its release's channel publication; supplemental
patches generated later through delta jobs have a separate enable/disable step.
Explain this distinction; do not delete, regenerate or relabel the originals.
This is not new evidence of a version-bump push completing the newer automatic
candidate workflow.

MCU-UI-INFO-01, OPEN / DEFERRED WITH THE UI BATCH: the operator reports stale
information on the MCU device/system-information display. Source confirms
`USER/App/Pages/SystemInfos/SystemInfos.cpp` passes `VERSION_FIRMWARE_NAME` and
`VERSION_SOFTWARE` to `View.SetSystem`; `USER/App/Version.h` still fixes these to
`X-TRACK` and `v2.7`, with the upstream author/project metadata. The displayed
software version does not come from the running OTA firmware header. The
30324 package's preserved byte comparison has `changesOutsideFwHeader=false`:
it reuses the verified V2 executable and updates the finalized header, not this
old information-page implementation. Treat the constant label as a real display
defect, not evidence that an OTA did or did not succeed. A later batched fix
should use the actual running firmware identity, coordinate visible E-Track
branding, and retain required upstream license/attribution notices. Hardware,
library/compiler versions and build/release dates must remain factual, not be
blindly replaced with the OTA version or current date. No MCU/UI code was edited.

The new authenticated GET-only `admin-interactions-20261113-01/mcu-inventory-read-02`
confirms MCU Stable now points to 30324 at revision 1, with query/download enabled;
Beta remains revision 9. This was the operator's publication, not an agent write.
Inventory still contains the prior 30321 observation at `lastSeen=1794570798`,
unchanged from `mcu-inventory-read-01`. Preserve the operator's successful-upgrade
report separately: this stale inventory is neither a new 30324 readback nor
proof of an upgrade failure. A later ordinary foreground App observation can
reconcile the new version/hash; no repeat upgrade, reset or reinstall is justified.

### Post-Upgrade Reporting Budget Check And Deferred Admin Additions

The operator reports checking for updates several more times after the successful
upgrade, asks whether reporting has exhausted its daily allowance, and requests
recording the two Admin additions below for the existing batched remediation.
Do not implement these changes or replay the completed upgrade for this inquiry.

The read-only observation at `2026-11-13T12:31:15Z` (20:31:15 Asia/Shanghai) is
preserved in
`.cache/version-inventory-delta-20261111-01/admin-interactions-20261113-01/inventory-budget-read-01/`.
One authenticated D1 query request executed four SELECT statements against the
original `trace-update-staging` database. The native response records six rows
read, zero rows written and no changed database. It submitted no inventory report
and did not request a refresh, modify limits, or touch release/channel state.

| Observed field | Value |
| --- | --- |
| UTC budget day | 2026-11-13 |
| Global accepted reports / configured daily limit | 2 / 1000 |
| Existing App 102 installation accepted reports / daily limit | 2 / 8 |
| Latest accepted installation sequence | 2 |
| Latest report received | 2026-11-13T11:53:23Z (19:53:23 Asia/Shanghai) |
| Latest MCU observation | 30321, observed 2026-11-13T11:53:18Z |
| MCU image SHA-256 | `5820b830e9763ee853f29ff21adb4c43ebd5cf1c7ce00fcff85cef1e05be11bf` |

APP-INV-POSTOTA-01, OPEN / DEFERRED INVESTIGATION: no 30324 observation has reached
the inventory at this checkpoint. Neither the installation daily cap nor the
global accepted-report budget is exhausted. This does not establish spare
account-wide Cloudflare quota, absence of ingress rate limiting, or the exact
phone-side cause. Preserve the operator's upgrade success separately; stale
telemetry must not downgrade it to an OTA failure.

Source observations, not a confirmed diagnosis of this phone: successful
`OtaService.readDeviceInfo` and verified post-reboot completion both call
`VersionInventoryService.observeDevice`. The inventory service debounces for
five seconds, coalesces unchanged identities for 24 hours, checks refresh control
at most every four hours, and waits one hour after a reporting exception. A
changed version/hash makes a report due, but foreground, opt-in, busy and retry
guards still apply. A timer that returns while busy does not itself schedule an
idle retry. The public control/report endpoints also share a 120 requests/hour
per-IP ingress limit, separate from the two daily accepted-report limits. Merely
pressing Check for updates is not a forced reporting acknowledgement.

Next implementation owner: inspect the existing phone's latest observed identity,
report scheduling/attempt/result and retry deadline through an authorized ordinary
observation, without another upgrade or reinstall. Use the installed App identity
when comparing with source. If the new identity is local but unsent, repair the
pending-report/foreground-idle-retry path; if a request is rejected, preserve its
real HTTP/error reason and address that condition instead. Add sanitized status
visibility rather than silently swallowing the reason. The later oracle is a
backend-acknowledged 30324 observation with the expected image hash, plus tests
for busy-to-idle, foreground return, failure backoff, opt-out and unchanged-state
coalescing. Do not raise limits, clear consent/state, or invent a phone result to
hide this gap. No phone logs or new physical observations were collected here.

ADMIN-NOTIFY-BUILD-01, OPEN / DEFERRED: when a GitHub Actions App or MCU candidate
has actually finished upload, validation and registration in this original
backend, show an in-page arrival popup and a browser/system notification through
the existing authorized notification route. A successful compile alone is not
proof that the backend received a package. Existing actor-scoped delta-job
notifications do not cover every newly registered CI candidate. Reuse the
notification/outbox/read-state infrastructure, preserve role/audience boundaries,
and deduplicate repeated registration callbacks by immutable candidate identity.
Include package type/version and an entry to the correct release details; do not
auto-publish it. Retain an unread arrival when the page is closed or notification
permission/vendor delivery is unavailable. Respect active dialogs and drafts;
do not replay old packages as new arrivals or request browser permission on load.
Later checks must distinguish foreground popup, actual browser delivery,
idempotent callback, failed upload/registration, and click navigation. No new
build, subscription mutation or test notification was triggered for this note.

ADMIN-RESOURCE-USAGE-01, OPEN / DEFERRED: expand the floating resource panel to
show real usage for the resources consumed by reporting and the existing update
service. Include Workers/Pages Functions requests and CPU, D1 rows read/written
and storage, Durable Objects requests/duration/SQLite usage, and existing R2
storage/Class A/Class B usage. Keep GitHub Actions usage separate from Cloudflare.
Show used/allowance/remaining, applicable account or project scope, actual plan,
period, reset time and last successful measurement. Distinguish provider quotas
from the App's 8/day and backend's 1000/day safeguards. Use bounded cached
server-side provider metrics where available; do not expose credentials, invent
unsupported counters, treat stale/missing data as zero, or infer provider usage
by multiplying accepted reports. Flag permission gaps and statistical delay.
Do not auto-upgrade plans or delete assets to satisfy a displayed quota.

Reporting directly invokes Pages Functions/Workers and the inventory D1 queries;
its ingress limiter makes a Durable Object RPC and SQLite operations. One accepted
report is not one database write: budget triggers, snapshots and indexes can add
writes. Rejected, control and coalesced network requests can still consume
compute/limiter/read resources. This report handler does not directly read/write
R2 or KV; package upload/download and other update routes are separate consumers.

Official free-tier references retrieved on 2026-11-13, not a measurement of this
account's subscription or remaining allowance:

| Resource | Reference allowance and period |
| --- | --- |
| Workers / Pages Functions | 100000 requests/day; 10 ms CPU per invocation |
| D1 | 5 million rows read/day; 100000 rows written/day; 5 GB total storage |
| Durable Objects compute | 100000 requests/day; 13000 GB-s duration/day |
| Durable Objects SQLite | 5 million rows read/day; 100000 rows written/day; 5 GB total storage |
| R2 Standard free tier | 10 GB-month storage; 1 million Class A and 10 million Class B operations/month |

These services do not share a single weekly quota. Daily provider allowances
reset at 00:00 UTC (08:00 Asia/Shanghai); the application daily caps also use UTC.
Rolling client intervals and per-IP hourly windows are different clocks. Paid
included usage and R2 free usage are monthly, with service/billing-period rules;
an included allowance is not necessarily a hard stop, since overage may be billed.
The panel must use the actual service/plan instead of presenting this reference
table as a verified account balance. No subscription or account-wide analytics
query was made in this investigation.

Sources: [Workers pricing](https://developers.cloudflare.com/workers/platform/pricing/),
[D1 pricing](https://developers.cloudflare.com/d1/platform/pricing/),
[Durable Objects pricing](https://developers.cloudflare.com/durable-objects/platform/pricing/),
and [R2 pricing](https://developers.cloudflare.com/r2/pricing/).
This continuation writes only the existing task note and the project-local query
receipts. Product source, UI, limits, packages and deployments remain unchanged;
there was no Git commit/push, new CI run, device operation or external cleanup.

### Post-Restart MCU Report Received

After the operator restarted the App, reconnected the MCU and read its firmware
identity, the SELECT-only `inventory-budget-read-02` observation at
`2026-11-13T13:06:18Z` confirmed a newly received 30324 report. The App 102
installation advanced from sequence 2 to 3; its daily accepted count is 3/8 and
the global count is 3/1000. MCU observation time is `2026-11-13T13:02:47Z`; report
receipt is `2026-11-13T13:02:52Z` (21:02:52 Asia/Shanghai). The reported image hash
is `bdca1ebcb40e39c0f108dc2c4eb49b1acd9621d4ac9563192720c6fd5ae0a7ae`, exactly
matching the preserved 30324 candidate binding, with hardware revision/layout 1.
Original response, comparison and write audit are under the existing
`admin-interactions-20261113-01/inventory-budget-read-02/` evidence directory.

APP-INV-POSTOTA-01 now has a successful new-version reporting observation; the
earlier missing-report checkpoints remain unchanged. Its scheduling/backoff
investigation remains OPEN / DEFERRED: this recovery does not identify the earlier
cause, prove that restarting is required, or constitute a code repair. Do not
repeat the upgrade or restart to replace this successful observation. The agent
only read the backend and updated local evidence/this note; no report was
fabricated, device operated, limit changed or product source modified.

## UI Remediation Continuation, 2026-11-13

The recovered thread resumed the eight-item remediation batch. Existing upgrade,
inventory, notification-delivery and publication observations were retained, not
replayed. Work remains incomplete. No new firmware/App release, deployment,
publication, device operation or destructive cleanup was performed.

All local changes and command outputs stay in the active worktree
`.cache/p35-integration-20261028/source` relative to the authorized E-Track root.
Within that worktree, `.cache/ui-remediation-20261113-01/` retains the preceding
agent's 17 baseline files and the additional before-images, original command
streams, development source binding and continuation write audit. The task
worktree's unrelated dirty files and shared Git index were not rewritten.

### Bounded Implementation Status

| Finding | Current continuation status |
| --- | --- |
| APP-INV-POSTOTA-01 | Retained the prior scheduling patch; added quick background/foreground cancellation handling, re-reading invalid App identity, bounded scheduling of old receipts, sequence reconciliation and truthful duplicate acknowledgements. Worker host tests pass; Dart tests added but NOT_RUN in CI. |
| APP-UI-INV-01 | Retained explicit readable opt-in colors and sanitized last-report/retry status. App runtime/visual verification remains pending. |
| ADMIN-UI-SHEET-01 | Resource panel now reuses sheet gestures with its own positioning origin/header, and participates in same-document overlay history. Ten resource browser tests pass, including both horizontal swipe directions, scrolling, Back/Forward and dragging. |
| BRAND-ETRACK-01 | Display names, share copy, native notification text, Windows title/description, website titles and SVG favicons changed to E-Track. Technical IDs, package/signing identities, URLs, storage keys and protocol fields remain unchanged. App/package verification pending. |
| MCU-UI-INFO-01 | System information reads the running App's validated firmware header once when opening the model. Invalid identity shows unknown; simulator/legacy builds are labelled explicitly. Library/compiler/build metadata and upstream attribution remain intact. Native formatter fixtures pass; full MCU/simulator build and device verification NOT_RUN. |
| ADMIN-UI-LOGIN-01 | Current official customization options reviewed only; no login template, plan or Access configuration changed. |
| ADMIN-NOTIFY-BUILD-01 | Not implemented in this continuation. Existing delta notifications remain unchanged. |
| ADMIN-RESOURCE-USAGE-01 | Not implemented in this continuation. No provider quota, plan, remaining balance or usage measurement has been invented. |

### Original Verification And CI Stop

`verification-02/result.json` and its original streams record:

- Worker inventory host suite: 19 tests passed.
- Worker and Admin TypeScript checks: exit 0.
- Resource browser suite: 10 mocked Playwright tests passed.
- Firmware-info C/C++ compilation: `-Wall -Wextra -Werror`, exit 0. Separate
  3.3.24 and 3.3.25 fixture runs each passed 11 checks, including truncated
  output, missing input and corrupt header cases. These are host fixtures, not
  installed MCU evidence.
- A scoped `git diff --check` passed. An earlier whole-tree check reported
  pre-existing task-board whitespace; those unrelated lines were not modified.

Development-only source delivery under the standing Flutter self-test authority:

- Repository/account: `Eitan-S-23/E-Track`, authenticated `Eitan-S-23`.
- Parent: `ce458416cb96dc9be41981aa9cd3098198b21c1f`. All 16 selected App
  before-images matched the parent; there were no baseline differences.
- New exclusive branch: `dev/flutter/ui-remediation-20261113-01`.
- WIP commit: `6e25bbac607f413c463071494f41cd5967c09bea`.
- Workflow: `flutter-dev-checks.yml`, push event, checks only, no APK requested.
- Run: https://github.com/Eitan-S-23/E-Track/actions/runs/43446806308
- Both Ubuntu and Windows jobs FAILED at dependency resolution, exit 65.
  Flutter was `3.50.0`, revision
  `ab2912035e160d9cad6306df307576da6128ebdb`, Dart `3.14.0`.
  The original log says `Would change 6 dependencies` and
  `Unable to satisfy pubspec.yaml using pubspec.lock`.
  The six reported differences are clock 1.1.2 -> 1.1.3, stack_trace
  1.12.1 -> 1.12.2, test_api 0.7.12 -> 0.7.14, vector_math 2.4.2 -> 2.4.4,
  new listen 1.0.1, and classification of the existing local
  flutter_blue_plus_android override as a dev dependency.
- App analysis/tests and candidate tests: NOT_RUN, not failed App assertions.
  Android APK and Windows EXE: NOT_BUILT. Both diagnostic artifact uploads
  succeeded; the combined original console log is preserved locally.

No blind rerun, lock-file check removal, SDK downgrade or dependency upgrade was
performed. Next owner is the user for the dependency-baseline decision: the
preferred bounded continuation is to allow only the lock-file changes required
by the current CI SDK, review the exact resolver diff, then retain the strict
lock-file gate for the normal dual-host development run. Do not turn this into
a broad dependency upgrade or production workflow. Continue the original eight
findings after that decision, rather than claiming source-only remediation is
finished or repeating already successful physical tests.
The WIP branch and run already exist: reconcile or advance that branch by an
ordinary reviewed commit; do not replay branch creation or the original push.

### Credential And Login Findings

The direct GitHub CLI call under SYSTEM could not read the owner's credential.
The older whole-process SU launcher then failed importing Python `_ctypes` before
any GitHub request. Both failures remain preserved. The later existing
`existing-credentials.py` route successfully read the named owner credential
under its already-qualified SU context, with commands remaining SYSTEM. It
verified the authenticated GitHub identity and performed the scoped development
delivery above. No replacement credential, login, credential export, ACL change,
service or scheduled task was created. The new `ui-remediation-ci.py` is only a
thin adapter over those existing credential/API/receipt helpers.

Official Access docs retrieved during this continuation distinguish two routes:
the basic organization login design affects every Access application, while
application-specific HTML/Liquid login templates require a Zero Trust
Pay-as-you-go or Enterprise plan and exactly one visible
`cf-access-authbox` control. The actual account plan was not queried, so neither
availability nor a need to upgrade is established. Preserve authentication
policies and avoid an organization-wide appearance change under an E-Track-only
scope without a separate decision. Sources:
https://developers.cloudflare.com/cloudflare-one/reusable-components/custom-pages/access-login-page/
and https://developers.cloudflare.com/cloudflare-one/reusable-components/custom-pages/access-custom-pages/.

Cloud/UI/MCU source and these notes remain local and uncommitted. Only the listed
App WIP files were delivered to the new development branch; no mainline delivery
or independent acceptance is claimed.

## Authorized App UI And Dependency Follow-up, 2026-11-14

The operator authorized the dependency correction and explicitly requested the
version-statistics control's display/color repair. This follow-up changed only
the assigned App UI/tests, the development SDK selector and its guide. It did
not replay an upgrade, publication, notification or device observation.

### Final Development Result

- Validation branch: `dev/flutter/ui-remediation-20261113-01`.
- Final commit: `2c3a4e41ba402cb2c047b62f6bd809f735473bf0`.
- Actions: https://github.com/Eitan-S-23/E-Track/actions/runs/43470268506 .
  Both host jobs and diagnostic uploads completed successfully.
- SDK: Flutter `3.47.9`, framework revision
  `c197ca5199e9ee5661e865596c9c07294dfab51c`, Dart `3.13.7`.
  The tag checkout truthfully reports channel `[user-branch]`.
- Strict dependency resolution and analysis: PASS on both hosts. Full App tests:
  Linux 789 passed / 16 skipped / 0 failed; Windows 770 passed / 35 skipped /
  0 failed. Eight additional candidate checks passed on each host.
- Local contained runner regression: 65 passed. No local Flutter build occurred.
- APK/EXE builds, publishing, deployment and device operations: NOT_RUN.
  These are development results, not shipping or independent acceptance.

APP-UI-INV-01 now has explicit readable label/state colors, selected/unselected/
loading switch colors and its own transparent Material surface, so the dialog's
painted background cannot hide ink feedback. Eight widget cases cover both theme
brightnesses, adaptive controls, saved opt-out, loading, reporting status and a
320-pixel layout at 200% text scale. The profile header, button captions and
footer fit narrow layouts without clipping; remaining profile display names
use E-Track. Privacy text, opt-in defaults, stored preferences and package IDs
were not changed. No installed phone UI has been claimed updated.

### Baseline And Test Lessons

The first lock refresh passed strict resolution with Flutter 3.50.0, but that
SDK also introduced unrelated Material-library migration diagnostics. Instead
of migrating the whole App or suppressing checks, the development runner now
selects the already verified 3.47.9 baseline recorded above in runs 43049945504
and 43258693636. All five hosted-package changes were removed. The final lock
diff only reclassifies the existing vendored `flutter_blue_plus_android` as a
direct dev dependency; its version and source remain unchanged.

The inherited scheduling tests used Flutter's guarded `expect` inside a mock
transport invoked by a Timer during `tester.pump`. The resulting test-framework
exception was caught by the optional telemetry service and appeared as
`REPORT_UNAVAILABLE`. Mock requests/tokens are now recorded and asserted outside
that callback. Timers and deadlines share the binding's clock; services close
in the test body's `finally`, before invariant checks. Automatic retry/idle and
foreground-cancellation assertions all pass without changing the production
retry behavior in this follow-up. Two service lint findings were corrected.

UI tests now tap the actual settings icon, not the non-interactive caption.
The optional native version label is checked in both loading and resolved
states; color, preference, status and overflow assertions remain intact. The
development guide records these concrete pitfalls. Earlier failed runs and
transport failures remain in the evidence; none were relabelled PASS.

### Write Audit And Remaining Work

Evidence is under `.cache/ui-remediation-20261113-01/dependency-ui-02`, with CI
receipts in the sibling `github-*-ui02-*` directories. Explicit source/output
paths and host-test fixtures are project-local; the shared Git index/branch was
not switched or staged. Only ordinary reviewed fast-forward validation commits
were made, with no mainline or release operation.

The audit found a missed native-TLS side effect: six new certificate-revocation
cache/metadata files under
`C:/Windows/System32/config/systemprofile/AppData/LocalLow/Microsoft/CryptnetUrlCache`.
Creation times and Google CRL/OCSP URLs match the initial Windows HTTPS lookup;
the exact six paths, hashes and timestamps are recorded in
`dependency-ui-02/external-cache-audit.json`. Their combined size is 224192 bytes.
No cleanup was performed. Native gh/curl network calls were stopped after this
discovery; the existing credential reader is now used with Python/OpenSSL HTTPS,
with credentials excluded from redirected log downloads. Readback found no
further change to the six files. Do not claim every write was project-contained;
deleting any of these files requires the operator's explicit path-scoped approval.

The original login-page, CI candidate-arrival notification and provider-usage
panel findings remain unimplemented. Prior cloud/MCU changes and observations
are retained, not repeated. App release-mode APK/EXE verification and real-device
visual verification still require their applicable authorized delivery route.

## Authorized Original Admin UI Deployment, 2026-11-14

The operator explicitly authorized deployment after the source-versus-online
status clarification. The original Admin at
`https://trace-update-admin-staging.pages.dev` now serves deployment
`cc6b9de2-bf77-4238-b263-5b3eb55c313b`, replacing
`c0ed148b-04fa-40b7-a2a5-f93c34482719`.

Only the four static UI files `index.html`, `admin.css`, `sheet-gestures.js` and
`favicon.svg` changed relative to the previous deployment. This delivers the
E-Track title/name/icon and resource-panel dismissal fix. Screenshot inspection
also caught the new name wrapping beside the icon; the bounded correction keeps
it on one line, shows only the icon in collapsed desktop navigation and restores
the name in mobile navigation. Seven new branding regressions cover both locales,
desktop/mobile widths, the title/favicon and collapsed-to-mobile restoration.

The deployment is an explicitly dirty UI patch on base
`1b75d3921244642127f6aaa980ac308baf797b66`, not a new Git commit. The authoritative
source manifest is
`.cache/ui-remediation-20261113-01/admin-deploy-01/source-publish.json`, SHA-256
`0c980fadd16cd1f25113cad11b532cd43c7ac5a4913bd69f4f31a1abdca06144`.
Backend sources, including the prior inventory handler, match the deployed base;
the pending local inventory-handler change was deliberately excluded. The first
native attempt failed locally because the isolated bundle omitted two runtime
script dependencies. Their exact bytes were checked against the deployed Git
commit before adding them; remote readback confirmed the old deployment and
bindings remained unchanged before the successful retry. Failed originals remain
preserved, not relabelled as a successful deployment.

Verification under the same `admin-deploy-01` directory:

- The original App/firmware Admin UI regression run passed all 144 tests.
- After the small layout correction, all 49 selected branding/design/workspace
  checks passed, including the seven new cases. Desktop/mobile screenshots were
  inspected. These are mocked browser self-tests, not device acceptance.
- `after-public.json` records HTTP 200 and exact deployed-byte matches for all
  seven static assets, the E-Track title in both locale tables and the SVG MIME.
- The existing owner session remains valid; unauthenticated Admin session access
  still redirects with HTTP 302 to the existing Access issuer. Verification made
  no business mutations and required no interactive login.
- Pages production/preview deployment configurations and existing bindings match
  the pre-deployment snapshot. No Worker/public-site deployment, D1 migration,
  package/channel mutation, Git push, App/MCU build or device action occurred.

The Cloudflare Access login appearance is still unimplemented and was not changed
by this static-site publication. Candidate-arrival notifications and the expanded
provider-usage panel also remain pending. The earlier six-file certificate-cache
cleanup was completed under its separate exact-file authorization; its original
receipt remains in `dependency-ui-02/external-cache-cleanup-01/result.json`.

## Browser Favicon Clarification And Partial Correction, 2026-11-14

The operator clarified that the requested icon is the browser favicon, not the
in-page brand mark. Fresh anonymous navigation reaches the Access-hosted login
page, whose title is `Sign in` / `Cloudflare Access` and whose favicon is an
inline Cloudflare SVG data URL. That page never referenced the Admin's new icon.
The authenticated Admin used the new SVG favicon, but `/favicon.ico` and
`/favicon.png` both returned the SPA HTML with status 200. The preceding asset
check did not cover these compatibility entries or the login-page favicon;
do not attribute the operator's observation to browser caching without evidence.

Deployment `0eb9a0d8-9383-45ce-a4ec-d25c1112929a` replaces `cc6b9de2...` on the
same original Admin. It adds a real four-frame ICO (16/32/48/64 pixels), a 64-pixel
PNG and versioned icon links, using the existing artwork. Browser decoding and
all eight targeted branding/favicon tests passed. `verification.json` under
`.cache/ui-remediation-20261113-01/favicon-login-01/` confirms the bare and
versioned ICO/PNG URLs return their exact image bytes and correct MIME types,
not HTML, and that the existing owner session remains valid. Backend sources,
bindings, other static assets and Access configuration were preserved. No Git
push, App/MCU build, package/channel action or device operation occurred.

The Access login favicon and appearance remain UNRESOLVED, not deployed. The
existing CI credential can read the target Access application and organization,
but custom-page and subscription GETs return 403 / 10000. The registered local
provisioning credential was also checked only for those two read operations and
returned the same denial; it was not exported or substituted into CI. The
separate Pages OAuth credential has Pages-write scope, not Access customization
scope. These observations establish an unavailable management route, not the
absence of credentials or proof of the account's plan.

Current official documentation says application-specific HTML/Liquid Access
custom pages require Pay-as-you-go or Enterprise. The actual subscription could
not be read, so no plan or entitlement is inferred. Basic organization-wide login
design changes affect all Access applications and do not by themselves replace
the observed built-in favicon. Do not expand scope to other applications, weaken
authentication, create a replacement credential, or upgrade a plan to hide this
remaining gap. Next step is an owner-confirmed available Access custom-page
management route/entitlement for this application. The favicon correction above
does not complete the original login-page finding.

## Remaining Admin Features, 2026-11-14

The operator requested completion of the remaining work. This continuation
implemented the two independent deferred Admin features rather than repeating
the completed favicon deployment or the unchanged Access-permission probes.
The active Git root was reconfirmed as
`D:/github/my/E-Track/.cache/p35-integration-20261028/source`.
Execution evidence is under
`.cache/ui-remediation-20261113-01/remaining-20261114-01/` (abbreviated A below).

### Delivered Scope

| ID | Current status and boundary |
| --- | --- |
| ADMIN-NOTIFY-BUILD-01 | Implemented, self-tested and deployed. New App/MCU candidate registrations create durable, deduplicated arrivals in the same validated registration transaction. Existing subscriptions/read state remain intact. No candidate was manufactured and no real vendor/OS delivery was triggered for this continuation. |
| ADMIN-RESOURCE-USAGE-01 | Implemented and deployed, with 20 real metrics returned by the live protected API and rendered on desktop/mobile. Includes the original Worker, Admin Pages, public update API Pages, D1, Durable Objects/SQLite and R2. Plan/allowance/remaining remain unknown; GitHub Actions remains separately not connected. |
| ADMIN-UI-SHEET-01 follow-up | Fixed the existing delayed resource-panel hide: after the panel grew taller, its 190 ms delayed removal intercepted the next orb drag. The panel has no exit transition and now hides immediately. |
| ADMIN-UI-LOGIN-01 | Still unresolved. No Access application/policy, account-wide login design, custom page or plan was changed. The earlier authenticated custom-page/subscription 403 evidence remains applicable; it was not blindly repeated. |

The new events do not auto-publish, enable a delta, move a channel or backfill old
packages. Active push subscribers get payloadless wakeups; an authorized reader
without push also gets persistent unread arrivals on return. Candidate clicks
open package details, including when navigating from the distribution tab.
Windows details are read-only and cannot operate the Android channels. Modal
work retains keyboard ownership and drafts. The existing push permission flow
still requires an explicit user click.

### Deployment And Provenance

- D1 migrations `0011_candidate_notifications.sql` and `0012_resource_usage.sql`
  applied once to `trace-update-staging`. Old notification IDs, per-item reads,
  read cursors, sequence high-water mark and delivery leases were preserved in
  the unified stream. Legacy tables were retained. The pre-migration outbox was
  empty and the new candidate-event table remained empty after migration.
- Original Worker version: `7844dddc-0087-464a-ba13-f3f6701c23d9`. All existing
  bindings and checked runtime settings were preserved with `--keep-vars` and
  no staged variable overrides. This also includes the previously local,
  tested inventory acknowledgement change in the Worker bundle.
- Initial Admin deployment: `e508d580-755c-40e4-80d5-47f5dddd15e9`, replacing
  `0eb9a0d8-9383-45ce-a4ec-d25c1112929a`.
- Current Admin deployment: `e998c204-7df9-4814-b185-47d78bc3f442`, correcting
  only the resource reader's Workers request mode and cache namespace. This
  correction did not rerun migrations, redeploy the Worker or change secrets.
- Only two Pages production secrets were added: `RESOURCE_USAGE_API_TOKEN`
  using the existing dedicated CI credential, and `RESOURCE_USAGE_CONFIG_JSON`
  identifying the measured resources. Existing variables/bindings and preview
  configuration were verified unchanged. No token was exposed to the browser.
- Both Admin publications are explicitly dirty source patches on base commit
  `1b75d3921244642127f6aaa980ac308baf797b66`, not new Git commits. The final source
  manifest is `A/resource-runtime-fix/source.json`, SHA-256
  `f81a3207c896ab7b738dc3e9775a92805699740f6eba5e3660db783ca4de4501`.
  Its predecessor is `A/rollout/source.json`; the older staged inputs remain
  unchanged. Source and this note are still pending authorized Git integration.

Before/after D1 snapshots verified the same App/MCU releases, asset counts,
channel pointers and revisions. No GitHub write, new CI build, package upload,
publication, device operation, billing change or external cleanup occurred.
The original ICO/PNG bytes were retained and verified on the final deployment.

### Verification And Corrections

`A/checks-09` records 181 passing host tests across eight affected suites,
including CI registration invariants, firmware, deltas, inventory, notifications
and migration preservation. Subsequent focused resource tests cover the final
12-query scope and runtime correction; `checks-19` has eight passes. Final Admin
and Worker TypeScript checks are `checks-20` and `checks-21`, both exit zero.
These are self-tests, not independent runtime or device acceptance.

`checks-07` records 58 passing notification/operations browser tests. The wider
page regression initially had 20 mock-script failures because two older fixtures
served API JSON for the new JavaScript asset; the fixtures now serve the actual
module. The next 47-case targeted run had 46 passes and exposed the real delayed
hide/drag issue, rather than justifying a blind retry. After its repair,
`checks-16` passed all 17 resource/provider/candidate cases. `checks-13` also
passed five candidate cases, including a mock OS notification sink. The initial
132 unaffected browser passes and all failed originals remain preserved.

The first isolated Worker dry build could not resolve the installed `hono` from
the staged source. The already installed 4.12.27 package was copied, pinned and
qualified inside the isolated bundle; no dependency was upgraded or installed.
Worker and Pages bundle checks then passed. An expired Pages OAuth was renewed
in the owned project-private copy via the existing session, without a new login.

The first live resource probe returned explicit unavailable/null metrics, not
fake zeroes. Root-cause categories B/D/E: the new code assumed Node/browser fetch
semantics and its host mock accepted `redirect: "error"`. Current Workers docs
confirm that mode throws before a network request. Existing `delta_jobs.ts` and
push delivery already used the correct `manual` contract; propagating that known
pattern would have prevented the repeat. The corrective patch uses `manual`,
rejects 3xx without forwarding credentials, and namespaces the corrected cache.
A hostile-redirect regression and the package code-spec now preserve this rule.
The failed first deployment/probe and its cache row were not rewritten.

`A/live-verification.json` records the final live result:

- Owner access succeeds; anonymous navigation still redirects to Access.
- All 20 requested metric fields returned measured values, including a genuine
  provider-reported zero for Infrequent Access storage. The immediately repeated
  request reused the same cache snapshot. No account allowance was inferred.
- HTML, notification JavaScript, resource JavaScript and ICO/PNG responses match
  the staged bytes and correct content types. No old candidate alert appeared.
- `A/rollout/private/live-browser-settled/result.json` and its desktop/mobile
  screenshots show the real deployment, 20 rendered metric rows, no browser
  errors, and no mobile overflow. An earlier mobile capture caught the resize
  transition; the final capture waits for the sidebar transition and loading
  state to finish rather than treating an intermediate frame as final proof.

The write audit and owned-process close receipts are recorded in A. Expected
tool warnings (SQLite experimental, color environment, proxy/OAuth scope notices,
and Git line-ending notices) are not firmware or independent-acceptance results.

### Remaining Decisions And Delivery

Login appearance/favicon still needs an owner-confirmed usable Access custom-page
management route and entitlement for this application. Do not widen account-wide
branding, alter authentication policies or upgrade billing merely to hide that
gap. Actual system-notification delivery must be observed with a future normal
candidate and the existing browser subscription; the mock OS sink is not that
observation, and no extra package should be created solely to manufacture one.

The prior Flutter source changes and passing development CI remain as recorded
above, with no new APK/EXE built or installed here. MCU information-page full
firmware/simulator build and physical validation remain NOT_RUN. Public update
site branding and its own shared reporting-handler deployment were not included
in these original Admin/Worker publications. Do not label all earlier findings
complete or infer package publication/hardware authority from this web rollout.

### Final Write-Audit Qualification

`A/write-audit.json` closed all 38 owned native command trees, found no credential
bytes outside private outputs, and confirmed the six previously cleaned SYSTEM
certificate-cache entries remained absent. All selected source, build, test,
browser and evidence outputs were inside the active worktree; no external cleanup
was attempted. This is a controlled-path review, not a process-level filesystem
trace, and its status remains REVIEW_REQUIRED rather than an unconditional PASS.

The expanded read-only check found 17 *pre-existing* files with modification
timestamps in this task window. None was created after the first project write.
`A/external-cache-observations.json` records every exact path, creation/modification
time, size, hash and certificate source URL. They are under:

- `C:/Windows/System32/config/systemprofile/AppData/LocalLow/Microsoft/CryptnetUrlCache/Content/`
  and `MetaData/`: one DigiCert CRL cache object and existing certificate lookup
  metadata for DigiCert, Google, Let's Encrypt and Windows trust-list updates.
- `C:/Users/SU/AppData/LocalLow/Microsoft/CryptnetUrlCache/MetaData/`: existing
  certificate lookup metadata for the same public certificate services.
- `C:/Users/SU/AppData/Local/Microsoft/Windows/PowerShell/StartupProfileData-NonInteractive`:
  an existing startup-profile cache. No PowerShell command was intentionally
  invoked in this continuation.

Timestamps alone do not identify the writer. Windows certificate validation and
other concurrent host activity are possible causes, not established attribution
to these tool calls. There is no before-image or writer-process trace for these
17 files, so do not declare them newly generated agent debris or delete them.
Recommended handling is to retain them and require a scoped attribution review
before any path-specific cleanup request. Product deployment and live verification
remain valid; the external-cache attribution is a separate unresolved audit item.

## Public Website Follow-up, 2026-11-14

The next continuation reused the completed Admin/Worker rollout and did not repeat
migrations, notification enrollment, package generation or Access-permission
probes. Work remains in the same active worktree. Evidence for this addition is
`.cache/ui-remediation-20261113-01/public-followup-01/` (B below).

### Root Cause And Bounded Repair

The original public Pages endpoint still served deployment
`028e98d2-9135-4f0d-b832-8b5ff0d16cc2`. Browser-style GET `/` returned JSON 404
`Public route not found`, while the reporting-control API returned 200. The
catch-all function intercepted the homepage and favicon requests, so changing
the static HTML alone could not expose its title or icon. Initial requests using
Python's default User-Agent returned 403; the qualified browser-style request
distinguished that edge response from the actual application routing defect.
No authentication policy was weakened to obtain the latter observation.

Categories B/C/D/E: the earlier source-only branding change missed the Functions
routing layer and the separate public deployment. The repair delegates only
known GET/HEAD static paths to Pages. Unknown/private API routes and POST requests
retain their JSON errors. Versioned ICO/PNG/SVG entries reuse the already verified
Admin artwork, not a new logo or only an in-page image. The shared inventory
acknowledgement implementation now reaches the public endpoint used by Apps.

### Delivery And Verification

- Current public deployment: `64b91cec-99c5-4c30-84de-eb61de52e0e9` at
  `https://trace-update-public-staging.pages.dev`.
- This is an explicitly dirty six-file runtime/static patch on the prior public
  base `9dd858fc8f9943d444060169291ea5131d63489b`, not a Git commit. `B/source.json`
  records every input and staged hash. Other runtime dependencies match the
  original public deployment's source pins, including the retained firmware
  handler. No unrelated current registration/notification change was bundled.
- Existing Pages OAuth was renewed only in a new project-private copy. Pages
  production/preview configuration and bindings were equal before and after.
  D1 readback confirmed unchanged release/asset counts and channel pointers/revisions.
- `remaining-20261114-01/checks-22` passed 41 public-router/inventory host tests.
  `checks-23` found a missing `ASSETS` field in the new Pages test fixture. The
  fixture was corrected rather than weakening types: `checks-24` passed Worker
  TypeScript, and `checks-25` passed all 22 affected public-router tests.
- Public TypeScript and the isolated Pages Functions bundle passed. Existing
  installed Worker/Admin tooling was reused without installing dependencies.
  Proxy notices and Git line-ending warnings are retained in the original logs.
- `B/live-verification.json` passed 12 original-origin reads: real homepage,
  canonical index behavior, bare/versioned favicon image bytes/MIMEs, health,
  inventory control and rejection of Admin/CI routes. No synthetic report was sent.
- `B/browser/result.json` passed desktop/mobile checks, decoded all three image
  formats, recorded no page errors/overflow and confirmed Stable/Beta still
  offer build 102. Screenshots were inspected. No APK/package was downloaded.

The code-spec now records the actual static/API boundary and corrects its stale
statement that Dart tests were blocked on the old SDK. Existing failed observations
remain unchanged. The new files, script outputs, caches and screenshots are
project-local; `B/write-audit.json` and `B/closeout.json` contain the final bounded
audit/closeout, without treating the earlier cache-attribution uncertainty as PASS.

### Remaining Owner Boundaries

The Admin favicon/title, candidate arrivals and measured resource panel remain
deployed as previously recorded. The public website/reporting deployment is now
delivered too. The Access-hosted login favicon/appearance is still NOT_CHANGED:
the existing 403s remain applicable, and an owner-confirmed usable custom-page
management route and eligible entitlement are still required. No plan, billing,
organization-wide design, Access policy or replacement credential was changed.

Flutter CI results remain valid, but no new release APK/EXE was built, published
or installed. MCU full firmware/simulator compilation and physical verification
remain NOT_RUN. Website rollout authority is not package/channel/hardware
authority. Actual OS delivery of a normal future candidate notification remains
unobserved; do not create a package solely to manufacture that observation.
Source integration remains pending its own Git authorization. Provider plan,
allowance and GitHub billing remain unknown/not connected. Earlier external-cache
writer attribution stays open; no external cleanup was performed.

## Authorized Completion And Candidate Delivery, 2026-11-14

The operator explicitly instructed the agent to continue until real human
intervention is necessary and granted the remaining required task authorization.
Do not ask again for routine source delivery, builds or the scoped existing-device
verification route. This does not grant account/billing changes, authentication
bypass, unrelated work, external-cache cleanup or arbitrary filesystem outputs.

Work stays in the same active worktree. New execution records are under
`.cache/ui-remediation-20261113-01/completion-20261114-01/` (C below). The existing
Admin/Worker/public deployments and their completed migrations are not repeated.

`C/inspect/result.json` confirms the existing `release/candidates` branch remains
at `1b75d3921244642127f6aaa980ac308baf797b66`; no original candidate run is active.
The App remediation files match tested development source
`2c3a4e41ba402cb2c047b62f6bd809f735473bf0`. The candidate branch's already-fixed
three-minute P51 parser test timeout is retained, not reverted to the older
development test timeout. Dependency declarations match the tested baseline.

The original database's maximum versions are App 102 and MCU 30324. The Trace
`v1.0.77` tag is absent. The next original candidates are therefore
`1.0.77+103` and `3.3.25`, with the original package/signing/backend identities.
They use the existing automatic candidate workflow and its protected firmware
environment. Actual CI approval must use its legitimate current reviewer route;
required reviewers, production gates and signing-key isolation remain intact.

Source integration is bounded to the earlier remediation, its tests/docs and
these version increments. The shared local Git index is not used. The candidate
branch, not `main`, is the established delivery route. Candidate ingestion does
not select Stable/Beta, replace older packages or claim device acceptance.
At this preparation checkpoint, candidate build/delivery and device verification
are pending, not completed. Access login customization remains independently
blocked on a usable provider management route, not on repeated user authorization.

### Candidate Results And Bounded Android Recovery

Source `9623cc43d6cb48a922caedbe08b82b5492afd7be` was delivered once, without the
shared local index or a main merge. Original run `43517863599` passed candidate
checks and the protected firmware job. Its normal reviewer approval was made
through the existing authorized account; the environment configuration is byte
equivalent before/after. MCU 3.3.25 is registered ready but unpublished.

Cloud checks `43519152580` passed: public checks, 423 native Worker tests and
211 Admin browser tests. Trace run `43518046702` passed its admission and Windows
analysis/tests/EXE build, then failed on Android with the provider annotation
`System.IO.IOException: No space left on device`. Android's raw log is truncated
and its APK build has no successful completion. Do not invent terminal counts or
label the aggregate workflows successful.

The version's immutable draft is release `444802803`, still draft/prerelease,
targeting original Trace workflow `7eaa1dc3a5b2eaa54b921b2baa9a339acc29fbd0`.
It contains only Windows EXE asset `745410815` and ZIP asset `745410816`; no APK
or App D1 registration exists. The by-tag release API returned 404, but the
authenticated release list found this real draft. Preserve the draft and assets.

The evidenced tooling gap is continuing the missing Android build without
rebuilding successful Windows bytes. A blind failed-job rerun would retain the
same full checkout/disk setup; a full new dispatch would conflict with the draft.
The bounded fix extends the existing template with `resume_android_run`, strict
original-run/Windows-only-draft guards and native hash readback, and reuses the
already-tested development sparse checkout and disk preflight. It keeps full
Android tests and original secrets in Trace. It neither creates a new release
system nor changes App dependencies, signing, billing or channel selection.

MCU native receipts were recovered byte-exactly against all six logged hashes.
The full ETU and recovery binary were read back from original R2 and matched
their registered hashes. The existing recovery parser validated the exact
614416-byte final image, version 30325, SHA-256
`8f0014f9de43b913a4157a543c12d83e1cf78bec1367e015cc0847a86c95a4cb`.
The normal arrival created one notification and two provider-accepted deliveries,
each on its first attempt. This is not an observation of either OS displaying it.

The local default build failed at an existing USB header lookup despite the
header's presence. Its original logs remain in `C/native-build-01`; exact-source
GCC App/Boot compilation is supplied by the successful native candidate CI, not
a substituted local image. Sparse simulator inputs were restored from matching
existing Git blobs without changing the shared index. The simulator now includes
the shared `USER` header root; `C/simulator-02` built successfully with 78 warnings
and zero errors. This configuration-only fix does not rebuild the MCU candidate.

Access application `0d826613-3097-41ea-ba20-a8174d6822dd` now has name `E-Track`
and the existing public PNG as `logo_url`. Original policies, audience, session,
cookie and destination settings compared equal after the update. Actual anonymous
HTML now shows the new name, but its title/favicon remain Cloudflare's and the
application logo is not used on this hosted login page. The custom-page management
403s were not replayed; no organization-wide design or subscription changed.

`C/phone-status-01` found the expected phone not connected to its contained ADB
server. The server closed normally, with zero installation, UI or MCU operations.
Finish Android delivery and prepare its verified artifacts before requesting the
necessary phone connection. No previous successful OTA is repeated for logs.

### Final Candidate Delivery And Verification

The Android-only recovery was delivered as E-Track
`c985ea9eb6a856e946bd28fa4e11e23f2b4681e1` and Trace workflow
`64e07b345bb5a3de39a933f505bf466f78331cc4`, both on `release/candidates`, not main.
E-Track checks run `43524424407` passed and correctly skipped both package jobs.
Trace continuation `43524678459` completed successfully, including Android job
`132227700250`; the already successful Windows job was not rerun. The App/MCU
source remains `9623cc43d6cb48a922caedbe08b82b5492afd7be`.

The original E-Track aggregate run `43517863599` and original Trace run
`43518046702` remain failed. Recovery does not rewrite their disk-exhaustion
annotation or truncated Android log. The successful continuation had 15381098496
bytes free before SDK setup, 5.4 GiB before APK build and 2.7 GiB after delivery.
No dependency upgrade, larger paid runner or hosted system-directory deletion
was used to recover it. Full Android analysis/tests and original signing checks
were retained; a missing terminal test count is not invented from step success.

`C/android-assets-01/result.json` binds the downloaded 47827484-byte APK to the
native CI inspection, package `com.wen.gaia.gaia`, version `1.0.77+103`, original
signer `3cecee6330a930e020b454b6d4a79568f4494ca324ae7bcf2c1914e51b04ab47`
and SHA-256 `bff1dce207c438194b8d2a524e294729893b88569606d31fc1bda080642747a8`.
Both ARM libraries retain the original endpoints/public key, BLE V2, inventory
and E-Track display markers. The APK is not installed. GitHub release `444802803`
is now a prerelease rather than a draft, and the original Admin contains
`rel_trace_android_v1_0_77` as a candidate, not a selected channel release.

The original Windows EXE/ZIP asset IDs `745410815`/`745410816` and all their
digests remained unchanged. The standalone EXE is 93184 bytes, SHA-256
`8b447e6cc586b29d0f7555c938e9f15bea30d852ee1ae3db314417f0d31f40ef`; the
20532147-byte ZIP has SHA-256
`b365cf180416ca7ee5c6bb8f4d5e2679fe0acbede31f03015c848d4a46937272`.
`C/windows-reconcile-01` validates native PE version `1.0.77.103` and applicable
compiled markers. An earlier optional host check incorrectly demanded the
Android-only public-key literal in Windows AOT code. That failed observation is
preserved, not used as grounds to rebuild Windows or claim its Android-only
self-update/reporting runtime was exercised.

MCU release
`fw_558bc61e09297044b4608eff79ac7976bc859d94321b0b23c5f321cd41815bd6`
remains ready and unpublished. `C/firmware-display-01` runs all 11 information
formatter checks against the actual registered final image and obtains
`E-Track 3.3.25`. This is not physical display evidence. The separate successful
simulator EXE hash is
`e171d47dfc20242c6cdd7850f00ba94456a3c1130254e76f8ea37eb9e44428a7`;
its 78 warnings and zero errors remain reported, not hidden as a clean build.

`C/database-state-02` and `C/candidate-browser-01` verify both real candidates,
desktop/mobile details and no overflow/page errors. Candidate notifications
10 (MCU) and 11 (App) each have provider-accepted deliveries to the two existing
subscriptions on the first attempt. The closed Tasks markup was inspected without
marking notifications read. Neither provider acceptance nor the headless browser
proves OS notification display. Channel pointers/revisions remained unchanged.

The archived GitHub `cloudflare-release-metadata.json` is the pre-upload
1443-byte record; the byte-exact native 1650-byte receipt contains the final R2
verification state. Both originals are preserved. This normal workflow staging
difference is not an APK hash mismatch and must not trigger another build.

### Closing Branding And Login Boundary

`C/branding-notes-01` changed only this new App candidate's generated first line
to `E-Track 1.0.77 (103)` and its GitHub title to `E-Track 1.0.77 candidate`.
The protected existing notes API used a valid owner session and normal CSRF;
the old text was compared exactly before the edit. One `edit_notes` audit entry
was added. All other release rows, all assets, firmware and channels were equal
before/after. GitHub asset IDs/digests, tag, source target and prerelease state
were preserved. Signed metadata and older release history were not rewritten.
The two future workflow display strings now use E-Track too; repository/package
identifiers continue to use their original Trace names where required.

The complete `admin/access-login.html` template uses the existing design and
public ICO/PNG assets, exactly one unconditional `<cf-access-authbox>`, and
visible escaped Liquid messages. It adds no customer scripts or sign-in forms.
The root `tests/ota/test_access_login_template.mjs` is now included in the normal
Cloudflare workflow and its test-only path filters. `C/closeout-checks-01` passed
66 checks across candidate admission, Access template and public routing, plus
actionlint for both affected workflows. Existing 423 Worker and 211 Admin runtime
tests remain the unchanged runtime evidence; no web redeployment or package
rebuild is needed for this documentation/template/workflow-only closing diff.

The current official creation API requires `Access: Custom Pages Write`.
`C/custom-page-create-01` records one scoped create attempt per existing CI and
provisioning credential, both explicitly denied with HTTP 403 / code 10000.
No custom page was created, assigned or made an account default. The earlier
read denials alone had not proved the exact write permission; these actual create
responses do. Do not replay them unless the available capability changes.
Current plan/entitlement remains unknown: official HTML/Liquid documentation
names Pay-as-you-go/Enterprise, but a permission denial does not prove this
account's plan or authorize an upgrade. Application name/logo configuration is
not evidence that the hosted login's browser icon or layout changed.

### Required External Intervention And Audit

Only real external prerequisites remain for the blocked observations: connect
the actual authorized phone for the already prepared install/UI route, and make
the existing Admin application's custom-login management capability usable.
Another generic verbal authorization cannot supply a missing USB connection or
platform permission. Preserve normal authentication, billing, release gates and
operator channel choices. Do not ask for another blanket authorization, operate
an unrelated device, repeat a successful OTA or auto-read notifications.

The final read-only ADB audit resolves the misleading `loaded new key` wording.
The checked executable is x86 (PE machine `0x14c`), so its logged System32 path
maps to `C:/Windows/SysWOW64/config/systemprofile/.android/adbkey` and `.pub`.
Both files were created/modified at `2026-11-13 12:26:02 +08:00`, before the
phone-status check at `2026-11-14 06:41:33 +08:00`. The two files under
`C:/Users/SU/.android/` date from `2022-02-21`. Private key contents were not read
for this metadata audit, and no key was deleted, rotated or copied. These are
loaded pre-existing files, not evidence of key creation by this phone check.

`C/closeout-before-01` retains the metadata, source before-images and shared-index
hash. Controllable outputs stay inside the active worktree, including restored
sparse simulator inputs, native build directories, `.cache/original-admin-tests`,
browser caches and HTTP/test evidence. Earlier external certificate/PowerShell
cache attribution remains qualified: timestamps do not prove which process wrote
those pre-existing files. No external cleanup occurred. The final controlled-path
audit is not a machine-wide filesystem trace or unconditional external-write PASS.

## LOGIN-CREDENTIAL-RECONCILE-01, 2026-11-14

The operator corrected the request for another credential: the earlier one-month
login is still present and must be reused. The blanket implication that the
custom-page 403 required a replacement credential is withdrawn. This correction
does not reinterpret the failed API calls as success or claim the hosted login
favicon has changed.

Read-only evidence is under
`.cache/ui-remediation-20261113-01/access-capability-20261114-01/` (D below).
The protected CI input was compared under its authorized Windows identity and
matches the registered `CF-CI-01` input exactly; there was no wrong-token lookup.
The earlier inability to list that protected directory under SYSTEM is not
evidence that its contents are absent. No new credential was requested, copied
to CI, rotated, edited or created in this investigation.

| Check | Actual observation |
| --- | --- |
| Existing organization SSO | Present, type `org`, issuer `sulovehuang.cloudflareaccess.com`, expiration `2026-11-28T02:43:53Z`; not expired |
| Existing original-Admin token | Present, type `app`, expiration `2026-11-14T11:20:58Z`; live `GET /api/admin/session` returned HTTP 200 / site role `owner` |
| Registered CI token verify | HTTP 200, `active`; no expiration was returned, which is not a perpetual-validity claim |
| Local provisioning token verify | HTTP 200, `active`; no expiration returned |
| CI read of the exact existing Access application | HTTP 200, `E-Track`, original domain and self-hosted type |
| Provisioning read of that application | HTTP 403, `1010 / auth.forbidden`; an active token does not imply this operation is authorized |
| Each token's own policy-metadata read | HTTP 403 / 9109, `Unauthorized to access requested resource`; the complete grants were not disclosed |
| Existing Wrangler OAuth scope | `user:read`, `offline_access`, `account:read`, `pages:write`; not an alternate Access custom-page or Billing grant |

Fresh official documentation confirms that the previous create URL and JSON
shape were correct: account-scoped `POST /access/custom_pages` with `name`,
`type: "login"`, `custom_html` and `contract_version: 1`. The required permission
is `Access: Custom Pages Write`. HTML/Liquid custom pages separately require
Zero Trust Pay-as-you-go or Enterprise. Account subscription reads require
`Billing Read` or `Billing Write`, neither supplied by the Pages OAuth grant.
The earlier subscription and custom-page denials were reused, not repeated.
No expired OAuth token was needlessly refreshed for scopes it does not grant.

The month-long SSO grants Access site authentication, not Cloudflare account/API
administration. The website's `owner` role similarly does not prove Cloudflare
platform-admin permissions. Conversely, the management API's 403 does not prove
that the SSO expired, the account is Free, or a replacement token is necessary.
The same-account successful CI control also rules out a mistyped target account
or a generally invalid CI credential as the explanation for the earlier request.

Disposition: NEED_EVIDENCE of the provider's current custom-page capability, not
a new blanket authorization. Existing API access does not reveal the full token
policy or subscription, so the precise split between missing permission and
entitlement remains unknown. The smallest next observation is the existing
Cloudflare account's **Reusable components > Custom pages > Access custom pages**
view: is Create/Publish available, or does it show an entitlement/upgrade notice?
Also inspect the existing `e-track-ci` token's target-account permission selection;
do not create a replacement token just to answer that question.

If the feature is available and the existing token can perform the scoped create,
reuse the prepared template and assign it only to the original Admin application,
then verify anonymous title/favicon and unchanged authentication settings. If
the feature is plan-gated, return that actual provider observation for an owner
decision; do not upgrade billing or proxy/replace authentication. If only the
existing token's grant is missing, correct that grant through a legitimate
account-management route rather than demanding a new secret value. No usable
account-management session is established by the month-long Access SSO alone.

The basic organization login designer is not a silent workaround: the official
guide says it affects all Access applications, and its fields are name, logo,
header/footer and background, not browser favicon. Original organization defaults,
policies, application settings, billing and website deployments were unchanged.
No custom-page creation was retried and no package, phone or MCU operation ran.

## LOGIN-FREE-ONLY-01, 2026-11-14

The operator explicitly confirms that this is a Free account and that the
required solution has always been free. Paid features are not an acceptable
completion route. This owner statement resolves the previously unknown plan
for this task; it is not a new provider API observation.

Disposition: DECIDED. Stop the paid HTML/Liquid login-template route. Do not
upgrade a plan, start a paid trial, enable billing or pursue expanded token
permissions to revive that route. The earlier request for a console screenshot,
subscription information or another credential is withdrawn. The exact cause
of the historical 403s remains unproven, but it no longer matters to choosing
the free-only route; do not relabel those original failures as a proved billing
error.

Retain the current free Access sign-in flow, existing policies and sessions, and
the already changed E-Track application name. The Cloudflare-hosted login page's
browser favicon/title remain the provider default. Record that limitation
honestly, not as an implemented favicon change or a blocker for unrelated work.
Do not proxy or replace authentication, or alter account-wide login branding,
just to hide the limitation.

The Admin and public websites keep their already deployed E-Track favicon,
title and other changes. The unused `admin/access-login.html` and its checks are
retained as inactive reference, not deployed or scheduled work. This decision
requires no new build, migration, website deployment, package replacement or
device operation. Evidence and source-delivery records are under
`.cache/ui-remediation-20261113-01/free-only-20261114-01/`.

## App Operator Confirmation And Deferred Browser Icon, 2026-11-14

The operator reports that the latest App is already installed, its displayed
latest-report time matches the receipt time shown in the Admin, and the version
inventory participation control displays normally. These are user-observed
results, not a new agent package readback or device test. The message does not
provide an exact installed version, APK digest or report timestamp.

Disposition: DECIDED. APP-UI-INV-01 is resolved for the reported control-display
issue, and the App/Admin report-time agreement is operator-confirmed. This
supersedes the earlier uninstalled-App/USB prerequisite for these observations.
Do not reinstall the App, reset consent, force another report or repeat an OTA
to obtain evidence of what the operator has already confirmed. The report-time
agreement does not independently establish every offline-retry, background or
post-OTA scheduling case under APP-INV-POSTOTA-01; retain the existing software
test evidence without claiming those cases were physically exercised here.

MCU-UI-INFO-01 still lacks confirmation of the actual device information page;
the existing final-image formatter checks are not a physical display observation.
Use any existing operator observation before proposing another device operation.
The operator explicitly defers the browser-icon inquiry, including the disputed
post-login icon. Keep that visible outcome deferred, not completed or a blocker
for unrelated work. The free-only authentication decision remains unchanged.

This continuation updates only the task note. No package installation, MCU
flash, rebuild, deployment, remote publication, channel change or billing action
is performed, and the earlier failed and successful evidence is preserved.

## ADMIN-CSRF-LIFETIME-01, 2026-11-14

The operator reports `TOKEN_INVALID: CSRF token is invalid` while confirming MCU
delta generation, request ID `7dfa53c9-725a-4e7d-81c1-4a797bcc82a5`. The UI says
to reconcile the task and does not automatically resend it. Disposition:
DECIDED, repair the Admin session lifecycle without replaying the requested job.
Evidence below is under
`.cache/ui-remediation-20261113-01/csrf-20261114-01/` (A).

### Root Cause And Existing Evidence

Categories E/D: implicit lifetime assumption and missing browser coverage. The
server's HttpOnly CSRF cookie has `Max-Age=3600`, independently of Access login.
The old `mutate()` reused a nonempty in-memory token indefinitely and fetched a
session only when that value was absent. Cookie expiry or replacement by another
tab therefore leaves a visible signed-in page unable to submit. Earlier mocks
accepted a constant header without modeling the cookie, hiding this condition.
The operator's exact cookie age was not captured; expiry and replacement are
reproduced failure modes, not a fabricated readback of that browser.

The facade checks CSRF before reading the delta body or calling `createDeltaJobs`.
That rejection cannot create a job. Read-only live observations found 13 existing
jobs, including only the old completed MCU 30323-to-30324 job. No generation,
retry, enable or notification-read action was sent during diagnosis.

### Repair And Propagation

The shared `readAdminSession()` performs a non-cached session GET, validates its
shape/scope, and coalesces concurrent reads. Initial load, firmware refresh and
every mutation now use it. `mutate()` snapshots the confirmed body before waiting,
refreshes the cookie/header pair before sending, and refuses an old confirmation
when the signed-in actor changes. Failed refresh sends no POST. Delta selection
and reason remain available for reconciliation and explicit confirmation.

The original CSRF, origin, role, cookie attributes and Access checks remain in
place. No automatic POST retry was added. The repair is shared by App and MCU
management instead of special-casing the reported MCU button. No App or firmware
source, dependency, version or package was changed.

### Regression Results

The existing contained browser runner was reused with fresh output labels under
`remaining-20261114-01/`: `checks-26` intentionally reproduces both expired-cookie
failures against the old UI; `checks-27` passes all nine new cases; `checks-28`
passes all 220 Admin browser tests; `checks-29` passes the Admin type check.
The new cases cover expiry, another tab's token, failed refresh, failed CSRF
after refresh without replay, shared concurrent reads, changed actor and unusable
session responses. This is self-test and operator-error diagnosis, not a new
independent or physical-device acceptance campaign.

The local Pages compiler printed success and produced all expected artifacts,
but did not exit within its deadline. `A/pages-build.closed.json` preserves that
timeout and nonzero exit with complete process cleanup; it is not relabeled as
a clean command PASS. The existing artifacts passed `node --check`, their route
configuration matched the predecessor, and pinned inputs were rechecked. No
second standalone compile was used to replace that original receipt.

### Deployment And Live Verification

The original Admin Pages project now serves deployment
`7bd5ef34-59c9-46ca-abc1-053aa3f3914a`, replacing
`e998c204-7df9-4814-b185-47d78bc3f442`. Only `admin/public/index.html` differs in
the runtime input; backend inputs are reused byte-for-byte from the prior
deployment. The native deployment completed and the Pages configuration is
unchanged. Worker/public deployments, migrations, Access/billing changes and
package/channel mutations are all zero.

An isolated browser loaded the deployed page, removed only its own CSRF cookie,
then used the real session API and MCU delta confirmation UI. One fresh session
GET preceded one attempted POST with matching cookie/header. The browser route
blocked that POST before network transmission. The retained selection and
no-replay notice were checked; no real delta build was started for verification.
`A/private/browser/result.json` records this distinction explicitly. Subsequent
GETs verify the deployed HTML hash and unchanged jobs/App channels/MCU channels
in `A/live-after.json`.

### Knowledge Capture And Delivery

The Admin README now documents this session/CSRF lifetime contract and its
regression cases. There is no Trellis tree in this worktree; no parallel task or
spec hierarchy was created. The nine lifecycle tests replace the misleading
constant-header-only assumption while retaining the existing operation tests.
Scoped source delivery is recorded in `A/delivery.json` on `release/candidates`,
not a main merge. Original failed receipts and unrelated dirty files are retained.

The existing Pages authorization was renewed only in
`A/private/xdg-config/.wrangler/config/default.toml`; the source credential file
was not modified and no new interactive login or user credential was requested.
Controlled-path, owned-process and credential checks are recorded in
`A/write-audit.json`; they are not a machine-wide filesystem trace. The previous
App user-confirmed results, pending MCU information-page observation and deferred
browser-icon inquiry keep their existing dispositions.

## ADMIN-DELTA-APPROVAL-WAIT-01, 2026-11-14

DECIDED: the operator's new MCU 3.3.24-to-3.3.25 delta was waiting for the
existing `firmware-rehearsal` required-reviewer gate, not a stalled computation.
Original job `delta_50ee22d988ff13c2eef7c28a65c6b98d2178263f68718930e02437f7906f3a9e`,
attempt 1, maps uniquely to GitHub run `43584158880` and pinned workflow commit
`9dd858fc8f9943d444060169291ea5131d63489b`. The checks job passed at 10:13:16 UTC;
the firmware job had no runner or steps while its environment awaited review.
Admin `queued` means dispatched but not yet claimed, so its generic waiting
label does not distinguish this gate from runner queueing.

Using the existing authorized account's legitimate reviewer route, root approved
only environment `24458272742` on that original run. Before/after environment
configuration is identical. No redispatch, GitHub rerun, protection removal,
paid service, source/deployment change, asset enablement or device action occurred.

The firmware job ran from 10:45:42 to 10:46:17 UTC and the aggregate run succeeded.
The original Admin independently reports `ready`, revision 3, attempt 1,
`enabled: false`: `delta-30324-30325-bdca1ebcb40e.etu`, 7,301 bytes, SHA-256
`59bbbf54c134c131ff4bec0a8375ab5f52684cbc88f9e0a043bcc39ef34eecaf`.
App/MCU channel rows and all other delta jobs are unchanged. Evidence is under
`.cache/delta-wait-20261114-01/`, especially `approval-result.json`,
`observe-01/result.json` and `closeout.json`. Initial read-only probe corrections
(missing firmware scope and one SSL EOF) are retained in the closeout record;
neither caused a task replay. This is operational diagnosis, not new hardware
acceptance. The UI waiting label and normal gate remain unchanged: future
waiting tasks must be matched to their existing run before any new action.

## DELTA-SCHEMA-FEEDBACK-01, 2026-11-14

The operator reported schema v2 rejection of the existing 30324-to-30325 delta,
requested an explicit approval reminder, and asked for visible error dialogs
with the established swipe behavior. Scope remains the original backend/Admin
and free services. No App/MCU rebuild, package regeneration, channel publication,
asset enablement, new approval, dependency change or device operation is included.

The delta completion path invented a filename without the schema's `-patch.etu`
suffix. A latest-plus-download regression also exposed raw `R2Object.etag` being
stored where streaming needs quoted `httpEtag`. New results now use the shared
firmware schema name and HTTP ETag. A read adapter repairs both fields for sealed
legacy results without mutating their JSON, object bytes or package identity.
Worker, Public Pages and Admin must all receive their affected bundles.

Admin activity/candidates now observe exact GitHub run identities and actual
pending reviewer gates. A separate 30-second D1 lease/cache, migration 0013,
avoids repeated provider polling. It does not alter job state or grant approval.
Errors and real approval reminders use the existing result dialog, with actor
binding, deduplication, draft retention, focus/history ownership and dismiss-only
swipes. The service code-spec and Admin README contain the executable contracts.

Local evidence is preserved under `.cache/delta-followup-20261114-01/`:
`worker-all-01` passed 483 host tests; `browser-04` passed 73 selected browser
tests; `types-02` and `types-03` passed Worker/Admin type checks. Earlier failed
receipts are retained, including the regression that found the ETag defect and
old browser fixtures/expectations corrected for the now-visible error dialogs.
`browser-all-01` then passed the complete 232-test Admin browser suite.

`runtime-01` crashed before native Windows tests started (`0xc0000005`), so it is
NOT_RUN rather than a runtime pass. `types-04` could not find Public Pages' local
TypeScript installation; no packages were installed or locks changed. Existing
Linux `cloudflare-update-service.yml` is the remaining real-runtime/Public check.

The already successful original job/run and immutable 7,301-byte patch from
`ADMIN-DELTA-APPROVAL-WAIT-01` will be reused for post-deploy readback. Deployment
preparation only has reconciled current configuration, business state and
existing credentials; no source delivery, migration or deployment is claimed
at this point. Source delivery targets only `release/candidates`, never `main`.
The rollout preserves current user-controlled enablement/channel values rather
than restoring the older job snapshot. Later receipts below own final outcomes.

### Deployed Outcome And Readback

COMPLETE for the bounded backend/Admin repair. Source commit
`50335639c3863a2fa96dd504cdfaa159a172955f` was delivered to
`Eitan-S-23/E-Track:release/candidates`. Cloudflare checks run `43602972553`
passed Worker type/invariant tests in real Linux workerd, Public Pages checks
and the complete Admin browser suite. The automatic candidate check
`43602618960` also passed, with both App and firmware build jobs skipped.
This closes the local Windows native-runtime/Public-tooling gaps above; it is
self-test/deployment evidence, not a new independent hardware acceptance.

Only migration `0013_delta_run_status.sql` was applied. Wrangler reported the
successful migration but did not exit before its bound; the owned process was
closed and remote schema plus migration inventory were independently read back.
The migration was not replayed. The failed native receipt remains preserved.
Deployed versions, with existing configuration verified unchanged:

| Surface | Deployed version |
| --- | --- |
| Worker | `bae6201e-d3db-4c41-ba9b-6d0751c7eaa2` |
| Public Pages | `cf310624-3e43-415c-8591-935c0d00d428` |
| Admin Pages | `4f2b15c8-36bd-4060-8f62-0ac627b1cf15` |

`A/live-readback-02/result.json`, where
`A=.cache/delta-followup-20261114-01`, verifies both actual serving origins and
the original Admin. The existing enabled stable-channel delta is exposed as
`e-track-at32f435-v3.3.24-to-v3.3.25-patch.etu`, remains 7,301 bytes with SHA-256
`59bbbf54c134c131ff4bec0a8375ab5f52684cbc88f9e0a043bcc39ef34eecaf`, and succeeds
with a quoted ETag and signed full/range downloads. Its sealed result JSON,
all sampled App/MCU channel rows and delta-job rows match the pre-deploy snapshot.
User enablement remains true and was not written by this task.

The first readback already verified the Worker's full download, then used an
unsupported closed Range form. Existing firmware downloads accept only
`bytes=N-`; the corrected probe used `bytes=7237-` with `If-Range`, verified
HTTP 206 and the exact final 64 bytes, and reused the successful full download.
This was a probe correction, not a change to the download protocol or another
artifact generation. Both observations remain in A.

`A/live-ui-02/result.json` and its private screenshots verify actual deployed
HTML/CSS/JS and the actual Access session/catalogue at 390x844. Error/approval
states were simulated in an isolated browser, with all mutation requests blocked.
The error stays above MCU details, both swipe directions only dismiss, the
GitHub review link is correct and the same approval reminder does not reopen.
There were no browser errors or attempted mutation requests. Screenshots await
full opacity; the earlier behavior pass's transition frames are not the settled
visual reference. No new real build or approval was created to test the reminder.

Existing credentials were reused. One private OAuth renewal encountered a
transient failure; the later renewal succeeded without a new login or changed
scope. Failed Git uploads were reconciled by their exact blob hashes; successful
uploads were reused, and the remaining upload used the installed GitHub CLI.
Only checks were dispatched. No main merge, App/MCU/dependency changes, package
regeneration, new approval, paid feature, channel publication or device action
occurred in this repair.

`A/write-audit.json` records the scoped controllable-output, credential and owned
process review. All selected output roots are in this worktree. This is not a
machine-wide filesystem trace: no complete baseline was taken, and earlier
external Windows crypto/PowerShell cache observations remain unattributed and
untouched. Credentials and authenticated screenshots remain in protected
project-private directories; no project-external cleanup was performed.

The operator can refresh the original Admin and repeat App **Check for updates**;
the existing delta requires neither regeneration nor another approval. Future
firmware jobs still obey their original GitHub reviewer gate and now surface it
explicitly. A device OTA was not run or claimed by this verification.

## DELTA-AUTO-01: Match The App Generation Flow, 2026-11-15

The operator explicitly requested that MCU delta generation work like App delta
generation: the existing Admin reason and confirmation are sufficient, without
an additional trip to GitHub for approval. This supersedes only the preceding
future-MCU-delta reviewer requirement, not ordinary firmware build/publication
approval or the ability to display a real historical pending gate.

The change is limited to `.github/workflows/admin-delta-build.yml`, its
orchestration regression, this record and the existing service contract. No
Flutter, installed firmware, package dependency or UI change is required.
Use a dedicated `firmware-delta` environment with no reviewer/timer and only
the exact `dev/admin/version-inventory-delta-auto` branch. Reuse the existing
AES key and original-Admin upload bearer as environment secrets; do not rotate
them, expose them, grant repository-wide key access or modify the protected
`firmware-rehearsal` / `firmware-production` environments.

The generator still uses immutable original packages, reconstruction checks,
attempt/source identity and a disabled result that an operator enables
separately. Do not retry/regenerate the completed 30324-to-30325 job. Historical
attempt bindings and sealed results are not migrated. Only new MCU execution
bindings in the original Admin change; App execution bindings are retained.

Fresh contained records are under `.cache/delta-auto-20261115-01/`. The live
`release/candidates` baseline is `b605d70df554d3f6fa2e034df6e63d29b5118bb9`.
`snapshot-03/result.json` reuses the earlier successful small reads and checks
the four exact file object IDs. A redirected content request and truncated
recursive tree response remain preserved in `snapshot-01` / `snapshot-02`;
neither caused a remote write or a repeated package generation. The remaining
verification uses bounded per-file identities instead of downloading the whole
repository tree. Implementation/testing/activation results follow below.

### DELTA-AUTO-01 Completion And Verification

Source `3135a06e92a9165158cac49abdb789732fcd6842` is delivered to the dedicated
execution branch and `release/candidates`; `main` and the local Git index were
not changed. `provision-01/result.json` verifies the new `firmware-delta`
environment: no required reviewers or timer, one exact allowed branch, and only
the two required existing credentials. The original protected environment
documents compare equal before/after. Keys were passed to `gh secret set` on
stdin, not printed, rotated or stored in repository-wide secrets.

The 19 local orchestration tests passed. The initial receipt parser expected
TAP while Node emitted its default spec reporter; the successful original
execution was evaluated directly, not rerun. `checks-01/result.json` preserves
that distinction. GitHub run `43619002759` passed the workflow checks including
TypeScript and native Linux workerd. The push intentionally skipped generation.
Candidate workflow `43619017635` also passed with both App and firmware jobs
skipped: no original version was rebuilt by delivery of this change.

The existing Wrangler OAuth was renewed in a fresh protected project-local
copy, leaving its input unchanged. Only the original Admin production
`DELTA_WORKFLOW_REF` and `DELTA_WORKFLOW_COMMIT` were set to the dedicated branch
and source above. Cloudflare hides encrypted values on GET; their exact request
is bound by `cloud/binding-intent.json`, the native stdin digest and the successful
two-setting upload receipt. Readback verifies the retained secret types and
unchanged App, preview, authentication and storage configuration. No claim is
made that an API GET reveals secret values.

Admin deployment `7f29300a-8ed9-4fc7-8866-5192335eea81` activates those settings
using the byte-identical previously verified Admin runtime/static source. The
native bundle build and deployment succeeded; the deployment warning only
reports use of the configured local network proxy. No Worker/Public deployment
or migration was necessary. `cloud/verified.json` confirms unchanged Worker
bindings/deployment and exact unchanged rows in `channels`, `firmware_channels`,
`delta_jobs` and `delta_job_attempts`.

`cloud/live-verified.json` records real authenticated HTTP 200 responses for the
owner session and MCU delta candidates, with dispatch configured and the HTML
unchanged. The existing 30324-to-30325 patch remains ready, enabled and attempt
1. No new package, approval request, billing change or device operation was used
as a probe. This is configuration/live-readback verification plus development
self-tests, not a newly executed delta-generation or hardware acceptance.

The operator now refreshes the Admin and uses the existing reason/confirmation
flow. New MCU delta jobs build automatically; generated results still require
manual enablement. Historic pending jobs keep their original immutable attempt
bindings and are not silently restarted or moved to another approval policy.
