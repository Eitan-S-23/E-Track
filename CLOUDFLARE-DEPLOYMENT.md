# Cloudflare Deployment Memory

Read this file before deploying the E-Track backend or asking the owner for
Cloudflare credentials. It lives at the project root deliberately. Read the
primary checkout's copy, not only an old task worktree's copy.

## Current State: Account Backend Deployed 2026-11-22

After the owner's explicit backend-deployment request, Actions
[44972869444](https://github.com/Eitan-S-23/E-Track/actions/runs/44972869444)
successfully deploys the already-tested source
`8a6dd4a3f051ba137256795f8d889eef6ece3e2b` to all three existing components.
The unchanged `E_TRACK_CI` route is used; only pending `0018_accounts.sql` is
applied. No credential, Access, channel, delta or device changes are performed.

| Component | Verified live identity |
| --- | --- |
| Worker version | `4a6ece7d-d99d-4012-bf74-48aea9eaf5e4` |
| Admin deployment | `e314773a-497c-41d4-85b6-8d0e8a112d19` |
| Public deployment | `e87e25c6-e7ff-4503-828f-0bb964067802` |

Independent readback within this implementation session verifies the exact
three-component source, unchanged runtime settings/schedules and a real Admin
owner session. HTML plus ten JS/CSS files match committed bytes. Admin account
settings/list/statistics respond successfully; Public and Worker auth status
both expose separate automatic/manual limits of 5/5 and Asia/Shanghai days.
Anonymous cloud update requests return HTTP 401 / LOGIN_REQUIRED. Registration
and password registration are enabled; email verification/reset are unavailable
without owner-configured mail delivery. No synthetic account was registered.
Four channel pointers and all 59 existing delta IDs/attempts/input hashes match
the pre-deployment snapshot. This is live deployment verification, not independent
acceptance or proof of phone login/device binding/OTA.

The prior recommended firmware/App-first rollout was explained to the owner;
the later explicit instruction authorizes deploying now, but does not confirm
installation of App 1.0.90+116 or firmware 3.3.50. The pre-deployment Android
Stable channel still referenced 1.0.89. Older App cloud calls now require the
new login-capable App; local Bluetooth remains outside this cloud gate. Channel
publication and device/phone updates remain owner-controlled.

Existing dependency audit warnings remain: Worker reports 13 vulnerabilities
(3 moderate, 10 high); Admin and Public each report 4 high. Node/Actions
deprecation warnings are also retained, not treated as resolved by deployment.
Originals: `.cache/ota-followup-20261122/keyring-dispatch-93/`,
`keyring-cloud-live-94/97/`, `keyring-status-96/`, `keyring-logs-98/`.
See [the account deployment record](docs/ota-exec-notes/OTA-COMPANION-2026-11-20.md#owner-authorized-account-backend-deployment).

## Earlier Full Scroll Fix Verified 2026-11-20

Admin-only Actions [44615534351](https://github.com/Eitan-S-23/E-Track/actions/runs/44615534351)
deploys `2ad213fae81f395c0e70efed472d8386e1741564` as
`77ec808f-c927-4d17-af10-401f84c04990`. Exact-source backend `44613804222`
passes 291 browser tests, 501 Worker tests, 60 contracts and three typechecks.
The recorded existing fixture/Node/Actions warnings remain visible. No App or
firmware build, Worker/Public redeploy, schema or credential change occurred.
Production and preview runtime configuration are unchanged.

Real owner-session readback matches HTML and all nine JS/CSS assets. All 16
wheel/touch observations execute and pass at both edges of App/MCU delta bases,
announcements and firmware history. Modal background locks remain intact; no
page errors, unexpected writes or synthetic records occur, and channel/delta
identities are preserved. Long confirmation/error text also passes exact-source
browser regression without creating live errors. The earlier CSS-only desktop
failures below remain history and are superseded, not retroactively green.

Originals: `.cache/ota-companion-20261120/keyring-logs-03/04/` and
`keyring-cloud-live-06/result.json`. See [the completed delivery](docs/ota-exec-notes/OTA-COMPANION-2026-11-20.md#follow-up-delivery-completed).
MCU state reconciliation and pending real OTA are separate device work, not
prerequisites to serving this verified Admin change.

## Earlier Initial Scroll Fix Deployed 2026-11-20

Admin-only Actions [44602404051](https://github.com/Eitan-S-23/E-Track/actions/runs/44602404051)
deploys `9ed63498fd3ba83f2dd454c8c3ccf3ea0791805e` as
`25aa04d3-155d-4858-979b-28f6e23b2fb2`. Exact-source backend `44599364344`
passes 501 Worker/285 browser tests and contracts/typechecks. Existing runtime
configuration, Access/secrets, Worker/Public, schema and channel/delta identities
are preserved. Candidate `44599364349` skips App/MCU builds as intended.

Real owner touch checks for App/MCU delta bases, announcements and firmware
history pass at both boundaries, with all ten served assets matching the source
and zero business mutations. Desktop wheel checks reveal a remaining Chromium
latching case above a pre-scrolled page with sparse delta jobs. Initial failed
live probes are preserved; touch-only success is not full scroll qualification.
The targeted JS follow-up passes 18 local scroll regressions and typecheck but
still needs its own exact-source full CI, Admin-only deployment and live wheel/
touch readback. Do not repeat this CSS deployment or rebuild an App to finish it.
See [the follow-up record](docs/ota-exec-notes/OTA-COMPANION-2026-11-20.md#initial-admin-delivery-and-desktop-follow-up).

## Earlier Version Insights Deployed 2026-11-19

Actions [44531533628](https://github.com/Eitan-S-23/E-Track/actions/runs/44531533628)
deploys published source `7e088a0807c863f745043f2146d26b2459980851` using the
unchanged `E_TRACK_CI` Secret, with Worker and Public included. Only pending
`0017_inventory_details.sql` is applied; earlier migrations are not replayed.

| Component | Verified live identity |
| --- | --- |
| Worker version | `84b2bec5-8302-4994-97a7-e28f85795668` |
| Admin deployment | `289c9cce-6ea2-41a4-a396-3640389b526d` |
| Public deployment | `fbc0e58a-a1e9-4f9c-a86e-874433bba38f` |

Exact-source backend `44529237548` passes 501 Worker tests, 273 browser tests,
60 proxy/Access/deployment contracts and three typechecks. The deployment verifies
source identity and preserves the named Worker environment, runtime configuration,
schedules, production/preview Pages configuration, Access and signing/generator
references. No credential, binding, channel or delta-generator setting is changed.

Real owner-session checks match HTML and all nine JS/CSS assets to source. App
and MCU distribution details, complete scope validation, associated App navigation,
Back restoration and desktop/mobile layouts pass. Public inventory control returns
200. Legacy records have unknown phone/IP fields and no quality summaries; this
is honest missing coverage, not zero activity. No synthetic report is inserted.
Both read-only live probes preserve channel and existing delta identities.

The same source's original-signed App `1.0.85+111` and GCC MCU `3.3.36` candidates
are built and registered, but not published to Stable/Beta. No delta generation,
phone/MCU operation or measured reconnect improvement is implied by this deploy.
Candidate and device qualification remain separate from the live Admin checks.

Originals: `.cache/companion-insights-20261119/keyring-logs-04/06`,
`keyring-cloud-live-01/02`, `backend-verification.json`, and the
[inventory delivery record](docs/ota-exec-notes/APP-ADMIN-UX-01.md#delivered-source-and-live-readback).
This supersedes the older notification-only deployment state below; its successful
and failed original observations remain history, not instructions to redeploy.
Selected outputs are project-local, but concurrent external PowerShell/Cryptnet
cache modification times have no process attribution; see the
[continuation write audit](docs/ota-exec-notes/APP-COMPANION-01.md#continuation-write-audit).
No external cache was cleaned or declared unchanged.

<a id="current-state-mcu-notification-fix-deployed-2026-11-19"></a>
## Earlier MCU Notification Fix Deployed 2026-11-19

Admin-only Actions [44437264265](https://github.com/Eitan-S-23/E-Track/actions/runs/44437264265)
deployed `9e19f9d15e2f3bcc4a99d2203edd59eb592c6395` through the unchanged
`E_TRACK_CI` Secret. Canonical Admin deployment is
`9c636437-4327-4471-ae50-20aa6c36b61c`, with successful exact-source and unchanged
production/preview configuration readbacks. Worker, Public Pages, schema, Access,
signing/delta references and credentials were not changed or redeployed.

Exact-source backend CI `44436135581` passes 483 Worker tests, 267 browser tests,
60 proxy/Access/deployment contracts and the three typechecks. A real owner
session verifies the served HTML plus nine JS/CSS assets against committed bytes.
Opening existing firmware-candidate notification 55 in the live Admin reaches
its real firmware detail panel; all firmware requests have the exact scope and
there are no page errors. Only notification read acknowledgements are intercepted
in this read-only browser check, using their full response contract. Channel
pointers and existing delta IDs/attempts/input hashes match before and after.

The first live probe supplied an incomplete mocked read acknowledgement and
timed out behind the resulting UI error. Correcting that probe, not redeploying
or weakening production checks, produced the successful result. All originals
remain under `.cache/companion-fast-20261119/`: `ui-02/03`, `keyring-logs-01/03`,
and `keyring-cloud-live-01/02`. The earlier local UI dependency-resolution failure
is retained separately in `ui-01`; locked installation did not change the lockfile.

### Same-Day Stable Rollout

The owner's later completion authorization also finishes this batch's original
staging Stable rollout: Android `1.0.84+110` at channel revision 60 and MCU
`3.3.35` at revision 9. Only the selected `109 -> 110` and `3.3.34 -> 3.3.35`
deltas were generated and enabled; both Beta channels and 42 existing jobs are
preserved, with 44 total jobs. This is separate from the successful Admin deploy
above: no backend was redeployed and no credentials/configuration were changed.
Public patch selection/download and MCU full fallback are verified. The later
direct-route App full download also completes: all 48,718,441 public-response
bytes are saved and hash-matched to the original signed APK in 194.350 seconds.
Earlier timeout, bounded-probe and partial-transfer evidence remains recorded;
see the [complete APK readback](docs/ota-exec-notes/APP-COMPANION-01.md#complete-public-apk-readback-2026-11-19).
See [the rollout record](docs/ota-exec-notes/APP-COMPANION-01.md#stable-rollout-completed-2026-11-19)
for exact Actions, hashes, scope and retained failures. Device installation and
measured reconnection behavior are not claimed.

### Firmware Notification Scope Contract

`openCandidateDetails(kind, id)` must use
`GET /api/admin/firmware/releases?appId=trace&deviceModel=e-track-at32f435` for
`kind=firmware`; each required parameter occurs exactly once. The API's scope
validation remains strict. The same `FIRMWARE_SCOPE_QUERY` supplies initial
loads, refresh and history so the navigation entry cannot silently drift again.

The root cause was a copied App query and a permissive mock: the main firmware
list supplied the model, but candidate-notification navigation did not. Good
cases cover Android/Windows/firmware crossed with full-candidate/delta notices;
the actual package panel must open without other mutations. A removed/invisible
release remains an explicit error. Missing, duplicated or wrong firmware scope
must fail the test mock, just as it does the real API. Wrong: relax the server
validator or request a new token. Correct: preserve the scope at the shared UI
boundary and assert the real request. These assertions live in `admin-ux.spec.ts`.

## Earlier Feedback Backend Deployment 2026-11-18

Actions [44245893967](https://github.com/Eitan-S-23/E-Track/actions/runs/44245893967)
deployed source `344abd6d297c80b37b4a8c4ec0096c2932d6b88b` using the unchanged
`E_TRACK_CI` Secret. This supersedes the older codec/USB rollout wait below.
Only pending migration `0016_feedback.sql` was applied; 0015 was not replayed.

| Component | Current verified identity |
| --- | --- |
| Worker version | `eebb1354-2e8b-485a-b960-2fcd131b4f6a` |
| Admin deployment | `02848862-864d-4591-8aea-9a7dd354f027` |
| Public deployment | `7c8fc56c-15cb-496c-8396-73f20e758677` |

Exact-source App CI `44243311453` and backend CI `44243622777` pass. Backend
checks include 483 native Worker tests, 261 browser tests and all typechecks.
Real owner-session readback matches HTML and nine JS/CSS assets to committed
bytes. Feedback acceptance, idempotent replay, second-batch daily rejection,
Admin detail/processing and the audit event passed using one explicitly synthetic
record, now resolved. The shared 50-batch/IP boundary is covered by native tests,
not by exhausting a real network's quota. Four channel pointers and all 37 prior
delta jobs were unchanged by deployment and this feedback check.

The two Admin production App-generator reference slots were updated together,
using the same partial PATCH as pinned Wrangler's Pages secret-bulk operation,
to Trace `dev/admin/original-delta-codec-20261118` / `4745aeadf2b526c6ff640539b401ff3fc1623cdb`.
They remain `secret_text`; preview, original public key, Access, named Worker
environment, bindings, schedules and other settings are preserved. Actual use
is now verified by new delta run `44250220531`, bound to that exact workflow
commit and the unchanged E-Track generator `73e6022f`.

Original-signed `1.0.82+108`, candidate source
`a977c848e03a2798a7b5c46319cd126a292395b4`, passes E-Track `44245598054` and Trace
APK/Windows `44245743035`. Its App tree equals `344abd6d`; original package,
signer, signed capabilities, hashes and Android R2 candidate are verified.
The new 107-to-108 `bsdiff-lzma-v1` delta is 2,439,333 bytes versus 48,684,713
full bytes (94.99% smaller). The exact R2 bytes, Ed25519 per-base signature and
reconstruction proof pass; only this new delta was enabled (attempt 1, revision 4).
There are now 38 delta jobs: all 37 originals and four channels remain unchanged.

No Stable/Beta promotion or phone operation occurred. USB is not a delivery
prerequisite; actual phone upgrade/performance is still unmeasured. This record
accompanies the bounded 25-file product/main integration. Use the authoritative
main-board check for local/remote delivery, not the older pending statements.
Receipts: `.cache/app-codec-20261118/keyring-cloud-bind-01/`,
`keyring-cloud-live-01/02/03/04/`, `keyring-logs-17/18/19/20/21/22/`,
`candidate-verification-02.json` and
[the feedback/delta delivery](docs/ota-exec-notes/APP-ADMIN-UX-01.md#feedback-and-delta-delivered-2026-11-18).

## Earlier Actions Delivery: 28459a89

The existing `E_TRACK_CI` repository Secret is now used by the published workflow.
Actions run [44186088340](https://github.com/Eitan-S-23/E-Track/actions/runs/44186088340)
successfully deployed the original Worker, Admin and Public targets from
`28459a89fcd6792611052cb601b231bb947bcc6d`. This is an executed Actions deployment,
not just a credential probe or a local-source upload. No token was recreated,
rotated or exported from the provisioning input; legacy R2 consumers are unchanged.

| Component | Verified live identity |
| --- | --- |
| Worker version | `153bfa20-6c68-488a-93cc-1f027cc808d0` |
| Admin deployment | `a5afcc59-b12e-452b-a5a4-0ba0d2aa7def` |
| Public deployment | `ec8b50c6-b436-41ca-a7b6-0a309a7fef13` |
| D1 schema | `0015_delta_file_deletion.sql`, applied once; column and both retirement guards verified |

Native backend CI [44184804298](https://github.com/Eitan-S-23/E-Track/actions/runs/44184804298)
passes on that exact source: 463 native Worker tests, 255 browser tests and
60 deployment/Public/Access contracts, plus all three TypeScript checks.
Real owner-session readback verifies the served HTML and all eight JS/CSS files
against committed bytes. Admin releases, announcements and the 106 delta
candidate return 200; original App signing and dispatch are configured. Public
Android/Windows/iOS announcements return 200. Original Worker settings, schedules,
Pages runtime configuration, four channel pointers and 37 existing delta jobs
match the pre-deployment snapshot. Generated Pages config hashes are recorded
separately. No real deletion, cancellation, channel promotion or device operation
was performed.

App `1.0.80+106`, source `8011709906af2dd8a9178f458759d286b7f89f9f`, has successful
original-signed APK and Windows builds and is registered as an R2-backed candidate.
It is not automatically promoted to Stable/Beta. App codec remains VCDIFF; the
MCU-core size comparison did not implement client decoding or qualify a mobile rollout.

Receipts: `.cache/app-admin-ux-20261117/keyring-artifacts-02/`,
`keyring-logs-16/`, `cloud/keyring-cloud-delivery-03/04/` in the same parent,
and [the delivery closeout](docs/ota-exec-notes/APP-ADMIN-UX-01.md#follow-up-delivered-through-actions-2026-11-18).
Earlier LOCAL_PENDING and denied-route statements below are dated history,
superseded by this delivery rather than rewritten as successful earlier attempts.

### App Codec Source Ready; Rollout Still Pending

Historical checkpoint: the current feedback/delta delivery above supersedes this
rollout wait. Preserve its original observations; do not restore the old USB gate.

The later codec continuation has integrated product source
`73e6022fe66adb77855e22984309bfaece8cc9fc` into primary and remote `main`.
Full App CI `44198825893` and exact-source backend CI `44202412682` pass.
Original-signed `1.0.81+107`, packaging source
`11fbf0b899568977e312d5e1820d89d06a21f5a7`, passes E-Track `44202448846` and Trace
`44202598314`; its App tree equals the validated source. The original signer,
Ed25519 capability signature and R2-backed candidate are verified. This does
not deploy the new backend or qualify the decoder on a phone.

Prepared Trace branch `dev/admin/original-delta-codec-20261118`, commit
`4745aeadf2b526c6ff640539b401ff3fc1623cdb`, installs only the reviewed App delta
template pinned to generator `73e6022f`. Its public-key push run `44204047891`
succeeds; no Android delta job was generated. Existing production App workflow
ref/commit slots are `secret_text`: API values are redacted, not absent.
Their bindings have NOT been switched, and preview/public-key/credential slots
are unchanged. Wait for the prepared phone measurements before activation.

After phone qualification, change only Admin production's two App workflow
ref/commit bindings, then use the existing Actions workflow to deploy this
verified source with Worker and Public included. Keep `E_TRACK_CI`, named
`env.staging`, Access and every other binding. No new migration, App rebuild,
channel promotion or replay of a successful delta is needed. Cloud snapshots
`keyring-cloud-read-01/02` under `.cache/app-codec-20261118/` still verify live
source `28459a89`, four unchanged channel rows and 37 unchanged jobs.
See [candidate delivery and remaining work](docs/ota-exec-notes/APP-ADMIN-UX-01.md#codec-candidate-delivered-phone-qualification-pending).

### Preserve Named Worker Environments

The first run `44183120496` applied 0015 and uploaded the intended Worker code,
then correctly failed its runtime comparison: flattening `env.staging` removed
`cf:service=trace-update-service-dev` and `cf:environment=staging`. Variables,
secret slots, bindings, schedules and business rows were unchanged. This was a
deployment-adapter defect, not a token denial. Pages steps were skipped.

The fix retains the original named configuration and invokes Wrangler with
`--env staging`. Do not flatten it or ignore all tags to hide the mismatch.
Missing standard environment labels can be restored from the pinned original
service/environment; conflicting labels and every other runtime/custom-tag
change remain errors. The successful repair records `migrated=false`, an empty
pending-migration list, `environmentLabelsRestored=true` and `runtimePreserved=true`.
Its `configurationUnchanged=false` is relative to the intervening broken-label
snapshot; the final separate live readback matches the original pre-deployment
settings completely. No already-applied SQL or App build was repeated.

The earlier failure and both sanitized artifact sets remain preserved. Failure
diagnostics retain provider codes without exposing credentials. The regression
suite covers environment grouping, conflicting/missing labels, migration reuse,
partial failures and source/runtime verification. This is an operational lesson
and development regression, not independent product acceptance.

## Earlier Pages Delivery: 59131a3e

Updated 2026-11-17 after the owner's deployment request and retry. Both Pages
projects now serve source `59131a3ef0712d46e7b17694d585371b751ab7ba`:

| Component | Verified canonical deployment |
| --- | --- |
| Admin | `63cdf429-13dc-41b4-aa93-966755ee9d79` |
| Public | `3865fc8c-8c36-4247-afbf-408b1a8e35b1` |

Both exact project GETs report the expected full source SHA and successful deploy
stage. Production/preview runtime configuration, Access secret slots, bindings
and delta workflow references are unchanged. Only generated
`wrangler_config_hash` metadata changed; both original values are retained.
The real existing Admin session returns `owner`; served HTML plus all seven
JS/CSS files match source bytes. Public Android/Windows/iOS announcements return
HTTP 200, including the previously failing iOS route. Channels, all 29 delta jobs
and the original 1.0.79 candidate/R2 identities are unchanged.

Original receipts: `.cache/app-admin-ux-20261117/cloud/`, especially
`pages-deployment-readback-01.json`, `keyring-cloud-admin-02/`,
`keyring-cloud-public-02/`, `keyring-cloud-renew-03/` and
`keyring-cloud-live-06/result.json`. See the
[deployment closeout](docs/ota-exec-notes/APP-ADMIN-UX-01.md#pages-deployed-and-verified-2026-11-17).
This record is LOCAL_PENDING on primary main `1ff996b6`; deployment is complete,
but these documentation changes have not been committed or pushed.

### Preserved Earlier Failures

The following observations preceded the successful local deployment. They do not
describe the current Pages source or establish that the CI credentials recovered.

- E-Track Pages run [43978919787](https://github.com/Eitan-S-23/E-Track/actions/runs/43978919787)
  returned HTTP 403 / code 10000 at the exact Admin project GET.
- Original Trace Pages run [43996459438](https://github.com/Eitan-S-23/Trace/actions/runs/43996459438)
  independently used Trace's existing repository secrets and returned the same
  denial. Dependency installation and both deploy steps were skipped.
- The last successful local Pages deployment used Wrangler OAuth, not either
  repository's CI token. Access tokens from those retained configurations
  returned HTTP 401; their latest recorded **access-token** expiry was
  `2026-11-14T19:21:28.012Z`. This is not the refresh token's or overall grant's
  expiry. Prior normal refresh failures remain preserved; their exact cause is
  not established by the access-token timestamp.
- The owner's task authorization already existed. The fresh user-approved OAuth
  input below restored exact Admin/Public Pages reads and was subsequently used
  for the completed deployment. No APK rebuild or new API token was needed.

Full dated observations and original receipts:
[APP-ADMIN-UX-01](docs/ota-exec-notes/APP-ADMIN-UX-01.md#existing-local-and-github-routes-2026-11-17).

### Actions Credential History Check 2026-11-18

Read-only investigation, LOCAL_PENDING. The currently retained dedicated Pages
workflow history contains six Trace runs and one E-Track run, all failed. Five
Trace failures date to July 2-5, before this incident. There is no demonstrated
transition from successful Pages CI to a newly broken credential in this history.
The July logs now return HTTP 410, so their individual failure causes remain
unknown; the November runs explicitly fail the exact Admin GET with 403/10000.

The recent successful Trace run `43969069993`, Android job `133661964252`, used
`secrets.CLOUDFLARE_API_TOKEN` for R2 upload/readback, not Pages deployment.
Candidate registration separately used `TRACE_DEPLOY_TOKEN`. The older Pages
workflow's credential-check step only checked that variables were nonempty.
None of these results qualifies Pages permissions.

Repository Secret metadata shows no recent replacement: Trace's token was last
updated `2026-06-29T13:49:09Z`, E-Track's `2026-11-07T17:48:02Z`. Historical setup
documentation describes the CI input as an R2 token and separately warns about
Pages permissions versus browser OAuth. A longstanding Pages authorization or
account-scope gap is the leading explanation, not a confirmed policy diagnosis.
Metadata cannot establish unchanged Cloudflare policy or the encrypted values;
expiry, revocation and the precise missing permission remain unproved.

Evidence, limits and the bounded next check are recorded in
[the task note](docs/ota-exec-notes/APP-ADMIN-UX-01.md#actions-credential-history-check-2026-11-18).
No Secrets, token policies or remote resources were changed, and no workflow was
dispatched. Completed local Pages deployment remains separate from CI readiness.

### Historical Green Pages Run Was A Masked Failure

Further read-only history check, 2026-11-18, LOCAL_PENDING. The six-plus-one count
above covers the dedicated deployment workflow, not every historical job. An
older `deploy-admin` job briefly existed inside `cloudflare-update-service.yml`.
Trace run [28539578982](https://github.com/Eitan-S-23/Trace/actions/runs/28539578982),
job `84609678528`, reports success, but its retained warning says:
`Cloudflare API token could not deploy Pages.`

At source `7705b36e652e5566c8d11aaaa6443bab44d52805`, the workflow caught a failed
`npx wrangler pages deploy`, printed that warning, and executed `exit 0`. The
warning proves this failure branch executed: the green job was not a successful
Pages deployment. Its suggestion to add Pages Edit was generic workflow wording,
not a provider-issued token-policy diagnosis. The preceding run `28539132115`
failed normally; rollback `01ad9854` then removed this automatic deployment job.

No genuine successful Pages deployment via Actions has been established in the
checked records. Do not repeat the earlier proposal to redeploy merely to diagnose
the already denied CI route. Investigate the existing input's authorization;
the current exact Admin GET denial remains distinct from an unconfirmed policy.
See [the original annotation and source evidence](docs/ota-exec-notes/APP-ADMIN-UX-01.md#historical-green-pages-run-2026-11-18).

### Actions Repair In Progress 2026-11-18

The owner requested resolution, not another deployment probe. Fresh named local
token verification is active. Reading its user policy with the existing local
provisioning input returns 403/9109. The account-policy route also returns
403/9109 through that reader; the target token's account self-read returns
404/1003. These results do not establish the policy or encrypted GitHub Secret
values. Owner-side inspection of the existing token remains necessary; no token,
scope or Secret was changed. Receipts: `cloud/keyring-cloud-policy-01/02/` under
`.cache/app-admin-ux-20261117/`.

The existing Pages workflow now has a LOCAL, UNPUSHED fix to ignore only each
environment's generated `wrangler_config_hash` in readback comparison. Runtime
variables, secret slots and bindings remain strict. The existing checks workflow
runs the new regression test; 33 local tests pass. Secret names and one-click
entry are unchanged. This local fix is not CI recovery or a deployment claim.

### E-Track-CI Pages Reads Restored 2026-11-18

The owner explicitly identified `e-track-ci` as the token whose permissions were
updated. Fresh checks through its registered protected `p41-ci-token.txt` input
now pass for both exact Admin and Public Pages projects. No OAuth or alternate
API token was substituted. Original 403 results remain preserved; new receipts
are `.cache/app-admin-ux-20261117/cloud/keyring-cloud-pagesprobe-04/result.json`
(Admin) and `keyring-cloud-pagesprobe-05/result.json` (Public) in the same parent.

These are successful project reads, not an executed deployment or proof of all
write permissions. No GitHub Secret was replaced and no workflow was dispatched.
The repository-level `CLOUDFLARE_API_TOKEN` value cannot be read back; its local
source is distinct from `e-track-ci`. Binding the verified token to that existing
Secret still requires the owner's decision. The local workflow fix above remains
uncommitted/unpushed. This capability update is also LOCAL_PENDING.

### Named GitHub Secret Created 2026-11-18

The owner requested using the verified local `e-track-ci` and matching its name
in GitHub. GitHub Secret names allow underscores, not hyphens, and are stored in
uppercase, so the Actions name is `E_TRACK_CI`; the Cloudflare token remains
`e-track-ci`. At `2026-11-17T18:01:05Z`, the existing GitHub CLI successfully set
this repository Secret in `Eitan-S-23/E-Track` from the protected local input via
stdin. No plaintext token was written to logs or passed in command arguments.
Metadata readback confirms the new Secret; all other Secret metadata is unchanged.
Receipt: `.cache/app-admin-ux-20261117/cloud/keyring-cloud-githubsecret-01/result.json`.

The local Pages workflow now maps `secrets.E_TRACK_CI` to Wrangler's standard
`CLOUDFLARE_API_TOKEN` variable in preflight, both deploy steps and readback.
Combined workflow/Public/Access regressions pass 34 tests; six fixture-only
adapter checks cover the bounded secret update and failure handling.
The old repository `CLOUDFLARE_API_TOKEN` is preserved because App and MCU R2
release workflows still consume it. No Trace or rehearsal Secret was changed.

The workflow and records remain UNCOMMITTED/UNPUSHED. The remote Pages workflow
therefore still uses its old Secret reference; do not claim Actions cutover or
deployment success. Commit/push of the bounded workflow changes is the next
owner decision. No workflow dispatch, Cloudflare deployment or token rotation
occurred during this credential-name migration.

### OAuth Restored After Explicit Owner Request

Local observation, 2026-11-17 12:54..13:04 UTC; pending repository delivery.
The original grant observations below are historical. Later normal renewal was
verified, most recently by `keyring-cloud-renew-03/` at 15:02 UTC and an exact
Public Pages GET. This establishes working renewal, not a fixed overall lifetime.
The owner explicitly requested a fresh login in the already-open Edge, a longer
callback wait, the longest supported credential authorization and a real Feishu
mention when browser action was needed. Reused the Huawei bot-creation WMI route,
not the failed direct cross-session Edge launcher. The current Feishu session's
requesting user received a native text-message mention through cc-connect.

- New protected input:
  `.cache/app-admin-ux-20261117/cloud/private/xdg-current/.wrangler/config/default.toml`.
  Original global and historical source configurations were not overwritten.
- `/user` confirms `tangjichentudou@gmail.com`; exact existing Admin and Public
  project GETs in account `af6dd848e6a21f1cd26d44b1b656af7b` both return HTTP 200.
  Scopes are `account:read`, `user:read`, `pages:write` and `offline_access`.
  No GitHub secret replacement, new API token, scope expansion, deployment or
  business mutation was performed.
- The new access token expires at `2026-11-17T13:54:43.533Z`, which is 21:54:43
  Asia/Shanghai. Its refresh token is present. OAuth exposes no requested lifetime
  option here: access-token expiry is provider-controlled, while `offline_access`
  permits normal renewal. Refresh-grant lifetime and a successful future renewal
  are not established by the short access-token timestamp or token presence.
- Wrangler's internal callback deadline was 120 seconds, independently of the
  outer runner. A login-only preload extends that exact timer to 1800 seconds;
  outer CLI/adapter bounds are 1920/2040 seconds. No installed dependency or
  frozen source was edited. Timer and completed-grant regression checks pass.
- Wrangler logged success and wrote the grant, but its CLI did not exit. After
  the identity and both Pages GETs passed, only the two owned CLI processes were
  stopped. The raw exit-1 receipt is retained; it does not revoke or disprove the
  independently verified grant. Edge remained open. The local wrapper now records
  authorization completion separately and bounds this post-grant shutdown.

Receipts: `.cache/app-admin-ux-20261117/cloud/keyring-cloud-login-07/`, especially
`oauth-verification.json` and `cli-closeout.json`; browser/mention receipts are in
`.cache/app-admin-ux-20261117/edge-wmi-20261117/`. Earlier timeouts, failed native
launches and their external crash artifacts remain preserved, not cleaned.
Reuse this named project-private OAuth input for subsequent authorized Pages work.
Use its current token, not a token copied from an earlier receipt. Renew serially
in this canonical configuration when needed; do not reopen browser authorization
merely because an access token expires.

### Deployment Runner Observations

- On this host, the existing proxy intermittently timed out while direct API
  reads worked. The local wrapper supports `E_TRACK_CLOUD_DIRECT=1`; controllable
  caches, temporary files and private Wrangler logs remain project-local.
- Wrangler 4.105.0 `whoami` does not force renewal of a still-valid access token.
  An early renewal check blocked the first Admin attempt without uploading.
  Public's first attempt then encountered actual access-token expiry before
  upload. Normal renewal restored the same grant; no new login/token was created.
- Both successful upload CLIs logged `Deployment complete` but remained alive.
  Exact canonical deployment/source/configuration reads passed before only their
  owned process trees were stopped. Raw exit-1 receipts remain preserved and are
  reconciled by the independent remote and live readbacks, not rewritten as exit 0.
- Pages returns the Durable Object script name as `service`, not `script_name`.
  Match its namespace ID to the original Worker's binding as well as its class.
  Record generated `wrangler_config_hash` separately from runtime configuration;
  every other production/preview field must still match. Nine local wrapper
  regressions cover this narrow metadata allowance and bounded read-only retries.
- The unchanged Worker was not redeployed. A new Worker-site GET timed out;
  Pages-only closeout uses the actual Admin/Public origins rather than making an
  unrelated Worker-site connection a new deployment prerequisite.

## Exact Targets

Service directory, relative to the primary project root:
`app/bluetooth_flutter_Trace/cloudflare/update-service`.

| Component | Existing target |
| --- | --- |
| Cloudflare account | `af6dd848e6a21f1cd26d44b1b656af7b` |
| Worker | `trace-update-service-staging` |
| D1 | `trace-update-staging`, ID `0133ad9e-d4a2-4fef-a659-4f2bf3d3a645` |
| Admin Pages | `trace-update-admin-staging`, production branch `main` |
| Public Pages | `trace-update-public-staging`, production branch `main` |
| Admin URL | `https://trace-update-admin-staging.pages.dev` |
| Public URL | `https://trace-update-public-staging.pages.dev` |
| Worker URL | `https://trace-update-service-staging.tangjichentudou.workers.dev` |

The `staging` names are the existing App's configured targets. Do not create
replacement projects, change URLs or substitute production firmware resources.
App package delivery, Worker deployment, Pages deployment, channel publication
and device installation are separate operations.

## Existing Credentials First

The owner has already authorized any E-Track agent to reuse `e-track-ci`
(historical alias `e-track-p41-ci`) for authorized project work. Changing agents
does not require another token-use approval. Existence, operation-specific
capability and task authorization are separate facts.

| Protected input | Locator and use |
| --- | --- |
| E-Track CI token | `.cache/p41-dev-20261015/.cache/cf-auth-input/p41-ci-token.txt`; named `E_TRACK_CI` Actions route now verified for the original Worker/D1/Admin/Public operations above |
| Project management input | `app/bluetooth_flutter_Trace/cloudflare/update-service/.github-actions-secrets.staging.local.json`, field `secrets.CLOUDFLARE_API_TOKEN` |
| Original standalone Trace input | `D:/github/my/bluetooth_flutter_Trace/cloudflare/update-service/.github-actions-secrets.staging.local.json`; read-only, not `D:/github/my/Trace` |
| GitHub repository secrets | `CLOUDFLARE_ACCOUNT_ID` and `CLOUDFLARE_API_TOKEN` in `Eitan-S-23/E-Track` and `Eitan-S-23/Trace`; use inside the owning repository's Actions runner, never extract their values |
| Named backend Actions input | `E_TRACK_CI` in `Eitan-S-23/E-Track`, set from protected `e-track-ci` on 2026-11-18; workflow published and actual deployment `44186088340` verified. Old R2/rehearsal/Trace inputs remain unchanged. |
| Existing Wrangler user input | `C:/Users/SU/AppData/Roaming/xdg.config/.wrangler/config/default.toml`; read-only source, normal refresh only in a checked project-private copy |
| Last successful local Pages input | `.cache/p35-integration-20261028/source/.cache/admin-copy-version-20261115-01/ui-rollout/private/xdg-config/.wrangler/config/default.toml`; access token expired, refresh-token expiry not established |
| Fresh explicitly approved Pages OAuth | `.cache/app-admin-ux-20261117/cloud/private/xdg-current/.wrangler/config/default.toml`; owner identity and both exact Pages GETs verified 2026-11-17, `offline_access` present; normal renewal only within this protected project route |
| Documented one-month Access SSO | `.cache/p35-integration-20261028/source/.cache/p35-release-available/fw93/login-02/private/home/.cloudflared/sulovehuang.cloudflareaccess.com-org-token`; existing organization/site-login route, not a Pages management API token |

### One-Month Session Is Not Expired

Owner clarification, 2026-11-17: a previously supplied credential should last one
month. The one-month credential explicitly documented in the Admin README is the
organization Access SSO above. The existing live readback
`.cache/app-admin-ux-20261117/cloud/keyring-cloud-live-02/result.json` records its
expiry as `2026-11-28T02:43:53Z` (2026-11-28 10:43:53 Asia/Shanghai), and confirms
a real Admin owner session at 2026-11-16 23:29 UTC. It has not reached its recorded
expiry. This named match does not prove that it is the publishing credential the
owner means; do not silently substitute an SSO identity for an API/OAuth identity.

Wrangler 4.105.0 writes `expiration_time` from `oauth.token.expiry` and stores
`refresh_token` separately. A short access-token lifetime is not evidence that
the longer-lived refresh grant expired. HTTP 400 from the previous refresh is a
failed exchange, not a diagnosed refresh-token expiry. The project API token's
separate verification records `active` without an expiry field; do not invent one.
Preserve all these distinctions before requesting login or declaring the owner's
one-month credential invalid. Never send the Access SSO to the management API.

The provisioning `token.txt` beside `p41-ci-token.txt` is **not** the CI token.
Never export it to GitHub or use it as an interchangeable CI fallback. Do not
print keys, protected JSON/TOML, cookies or credential-bearing request bodies.
Do not scan arbitrary private caches, create empty replacement credential files,
or modify original credentials/ACLs to work around a different Windows identity.
On this host a SYSTEM process is not SU; use the existing exact-slot owner-read
route instead of treating SYSTEM's empty keyring/environment as user logout.

Wrangler prefers its legacy `~/.wrangler` directory when present, otherwise its
XDG configuration. Supported API-token/global-key environment inputs can override
OAuth. Inspect named source metadata and actual configuration resolution before
concluding that the user must log in again. Keep controllable config, logs,
caches and temporary files inside the active project; never refresh the original
user-profile file or a frozen task's file in place.

See [credential registry](docs/agent-collaboration/credential-registry.md) and
[credential rules](docs/agent-collaboration-contract.md#reuse-before-requesting-credentials)
for dated capability evidence and confidentiality/authorization boundaries.

## Normal Deployment

1. Run `python -B Tools/workflow/main_board.py --repo-root .` from the primary
   checkout. Pin the reviewed source commit and affected components. Reuse
   matching successful checks/packages; a Pages-only change needs no APK/EXE
   rebuild, new version, re-signing, candidate registration or delta generation.
2. Check the exact existing account and Pages projects with the selected
   credential. Preserve production/preview configuration privately before any
   deploy. Verify original D1/R2 bindings, variables, Access settings/roles and
   delta workflow references. A nonempty secret slot or `whoami` is insufficient.
3. Prefer the tracked manual workflow
   [.github/workflows/deploy-cloudflare-admin.yml](.github/workflows/deploy-cloudflare-admin.yml).
   It pins `source_sha`, checks existing targets, preserves Access secrets and
   optionally deploys Public Pages with `include_public=true`. When Worker or
   schema inputs changed, `include_worker=true` applies only pending committed
   migrations and deploys/verifies Worker before either Pages component.
4. If using a verified local Pages credential instead, run the tracked Node
   helper from the service directory with `--yes --skip-secrets --commit-hash`.
   Do not use the PowerShell wrapper on this host while its startup-cache writes
   are uncontained. Preflight all output/cache/temp paths before invoking tools.
5. Deploy Worker code or apply pending D1 migrations only when those inputs
   changed and the operation remains needed. An already-applied migration or
   source-matched successful Worker deployment must not be replayed for Pages.
6. Read back the deployed source and live behavior using the checks below.
   Update this file's dated result, the main board and shared index on `main`.
   Do not leave the only working procedure in a task cache or chat.

These command templates require a reviewed full SHA in `VERIFIED_SHA`, verified
credentials and contained output paths. **Do not repeat a rejected credential
unchanged.** A dispatch acknowledgement is not deployment success.

From the project root, with the existing `Eitan-S-23` GitHub identity:

```bat
gh workflow run deploy-cloudflare-admin.yml --repo Eitan-S-23/E-Track --ref main -f project_name=trace-update-admin-staging -f branch=main -f source_sha=%VERIFIED_SHA% -F include_public=true
```

For an authorized Worker/schema change as well, add `-F include_worker=true`.
The pinned-source native CI must pass first. Do not use this flag to replay an
unchanged successful Worker merely because a later Pages step needs recovery.

From the service directory, for an already verified local route:

```bat
node scripts/deploy-admin-staging.mjs --yes --skip-secrets --commit-hash %VERIFIED_SHA%
```

From the service's `public/` directory, when Public Functions changed:

```bat
node node_modules/wrangler/bin/wrangler.js pages deploy ./site --project-name trace-update-public-staging --branch main --commit-dirty=false --commit-hash %VERIFIED_SHA%
```

The Admin helper can create a missing project. The exact-project existence check
is therefore required before using it for a normal redeploy. Do not omit
`--skip-secrets`, recreate Access configuration, change billing or publish a
release channel as a deployment workaround.

## Success And Failure Checks

| Observation | Required action / conclusion |
| --- | --- |
| New canonical deployment ID, expected full source SHA and successful stage | Deployment identity verified; continue with live checks |
| Production/preview runtime configuration unchanged; generated hash metadata recorded separately | Existing bindings, roles, secrets and execution references preserved |
| Real Admin Access session succeeds and served HTML/JS match the intended bytes | New Admin page actually served; a generic HTTP 200 is not enough |
| Affected Public APIs pass, including iOS announcements for this batch | Public Functions update verified; a Worker-only HTTP 200 is not enough |
| Token-management GET returns 403/9109 | That management read is denied; do not infer that publishing credentials are absent |
| Exact Pages GET returns 401/403 | Stop that route; retain the result and reconcile the existing input/account/scope, without automatic login, token creation or permission expansion |
| OAuth copy expired or refresh fails | Check its provenance and other named existing routes; not proof of missing task authorization |
| Timeout, TLS failure or interrupted CLI after upload | Inspect actual remote deployment first; do not blindly redeploy or call it a credential failure |
| All checked routes rejected | State that deployment is incomplete and ask once for the existing Pages-capable input's name/location or restoration of its protected route; never request plaintext keys |

Wrong: "One 403 means the user must log in; rebuild the App and retry everything."
Correct: identify the exact operation and credential, preserve its denial, reuse
other named authorized inputs, and deploy only the component still missing.

The completed `1.0.79+105` package source is
`59131a3ef0712d46e7b17694d585371b751ab7ba`. Its original candidate/R2 artifacts,
migration `0014_admin_ux.sql`, Worker version
`54ad084f-1bc3-41a8-bcad-cdc28ff536d4`, and successful historical delta
`43932189981/1` must not be rebuilt, reapplied or replayed to unblock Pages.
Device/formal acceptance and Beta/Stable publication remain separate obligations.
