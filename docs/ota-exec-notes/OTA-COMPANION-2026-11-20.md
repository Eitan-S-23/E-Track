# OTA Companion And Admin Scroll Investigation

## Independent Update Check Rollout, 2026-11-25

Status: MAIN_DELIVERED / CI_CHECKS_PASSED / CLOUD_DEPLOYED / LIVE_VERIFIED.
Owner: Codex root. The owner's explicit follow-up authorizes the pending D1
migration and code rollout, not channel/delta, credential/configuration work or
phone/device operations. This supersedes the earlier deployment-pending record.

Reviewed source 703fea1f8df8621870d802610a9c99d4357ab147 is already on main.
Exact-source checks 45468883658 pass; successful deployment Actions 45476279470
uses the existing named credential/workflow with Worker and Public included.
Only migration 0020_update_check_components.sql is pending and applied first.
Worker version is 028f2f6b-cfae-4290-bc0d-913c34fe1856, deployment
947048df-7878-4239-b859-f5afa6e4f555. Admin/Public deployments are
3464a3cc-48c5-44e9-bd23-4af1dd1f245d / f2d3e9aa-e532-4113-9a1d-947da37bf8bd.
All three report the exact reviewed source and successful deployment.

Read-only original-owner verification matches HTML/ten JS/CSS files to source.
The existing account's detail API returns components.app/components.firmware,
each with automatic/manual limits 5 and separately counted usage; old flat
fields equal the APP budget. Both public origins expose all four limits and
preserve mail readiness and anonymous HTTP 401 / LOGIN_REQUIRED. Registration
flags, settings revision 6, Worker runtime/schedules and Pages production/preview
configuration are unchanged. Four channel pointers and all 69 delta identities,
attempts and input hashes match the pre-deploy snapshot. Historical rows remain
classified as legacy until an exact original request identifies its component;
no history or client reminder state is cleared.

No additional APP/MCU version, package build, installation, OTA, manual check,
quota reset, channel publication, delta generation or credential change occurs.
Bluetooth recovery cooldown, firmware cache/dedup and the early APP daily-marker
write remain unchanged. This does not retroactively prove an older missing-popup
incident or claim a new real-phone/independent acceptance result.

Original evidence: .cache/update-check-isolation-20261125/rollout-01/.
dispatch-01/observe-01 bind the one deployment; receipt-01 preserves sanitized
Worker/Pages receipts and original Actions logs; keyring-cloud-live-601/603 are
the before/after readbacks. Prepare-01's TLS failure and live-602's wrong
list-versus-detail expectation are retained; only the harness/read-only route is
corrected, with no deployment replay. Worker 13 dependency advisories and
Admin/Public four high each, install-script, DEP0040/DEP0169 and Actions warnings
remain. Older pending document text/bytes are preserved and excluded from the
scoped main record delivery. All controlled outputs stay in the project.

## Bluetooth-On Background Recovery, 2026-11-24

Status at owner-authorized delivery, 2026-11-25:
MAIN_DELIVERED / CANDIDATE_DELIVERED / PHONE_VERIFICATION_NOT_RUN.
Owner: Codex root. This new report does not reverse or repeat the owner's
previous 23:00 successful checks. Bluetooth was ON in the original unattended
failure; OFF in later USB captures was deliberate testing. Cache remediation
is explicitly deferred.

The original archive records four connection timeouts, deliberate service stop
at 03:05:20, subsequent LOW_MEMORY exit and no retained recovery until owner
opening. Recovery jobs were registered but had pending-without-active periods.
The exact historical OEM/system scheduling delay remains unknown.

Old source returned START_NOT_STICKY and stopped the service during backoff.
Tested development source 283c65d756e3db434f16c72370e8c222e888fc0b retains its
foreground service without a wake lock while waiting, schedules local recovery,
requests guarded sticky recreation and preserves cold-restart cooldown. The
existing four-attempt/60-second windows and 2-to-60-minute capped cooldown stay.
Real connection success resets failure state; permission/association/disable/
terminal/OTA ownership gates remain. Late callbacks cannot stack failures,
extend backoff or claim readiness. Sticky recreation is an Android request,
not an OEM guarantee, exact sleep alarm or force-stop bypass.

Development CI 45421424363 / 45421702392 passes on both hosts. Original native
XML has 149 passed with zero failures/errors/skips, including 16 added service
tests. Linux Flutter full suite 1059 passed/16 skipped; Windows 1007/68, plus
eight candidate tests each. Debug APK passes; Flutter 3.47.9 / Dart 3.13.7.
Development APK/native commands retain 12/17 warning lines and zero error lines.

Owner explicitly authorizes main merge and the existing automatic candidate
route. Version checks cover 133 Trace Releases/tags, including drafts, before
1.0.94+120 -> 1.0.95+121. Main merge source is
629155427508e67be843a8f84d3296b03907e13a, preserving exact tested code blobs and
the previous main parent f8c1f4b43d6fd16468d60ac76dd6deab640a3f93. Formal parent
CI 45433637395 / original-signer Trace 45434018855 both complete successfully.
Original-signed APK/Windows EXE and automatic candidate registration pass;
registration returns ok=true, releaseId=rel_trace_android_v1_0_95, with no
Stable/Beta publication. APK and manifest assets are R2-verified. APK SHA256
487b04f58ac8df6a4802b3e72abbb81838141c7252dd255a6633e15cf937dfe6,
49636885 bytes. Package com.wen.gaia.gaia, original signer, both ARM libraries,
original backend, BLE V2 and inventory admission all pass. Android build has
10 warning lines/zero errors, Windows zero/zero; other whole-job diagnostics
remain in complete original logs. Firmware skips.
Phone App last verified as 1.0.94+120 does not contain this repair.

The first 20-minute local observation expires while CI is running; a second
observer completes against the same source/run, without another push/version/
build. The interrupted record reconciliation catches concurrent main advancement
before staging. Separate MCU/UI main commits 258c7051 and 916b9022 are retained;
the entire App tree is identical to the 62915542 formal source. Reconciliation
verifies the original pending bytes plus other-task additive board records.
Only this task's new three record blocks enter the following documentation
commit; earlier pending contents and the MCU/UI work are neither overwritten
nor included as new work by this root task.

Implementation/self-tests, main integration, formal candidate ingestion,
operator publication, phone installation and real-device behavior remain
separate. Owner controls Stable/Beta publication and phone update. No App UI
launch, force-stop, permission/data/dedup change, OTA, J-Link, MCU/cache/cloud
configuration change or new independent acceptance occurred. Original pending
documents and unrelated Dialplate/test edits are preserved.

The supported version-only entry rejects a dirty main and cannot integrate
the tested three-file repair. A narrow adapter reuses its contained Host,
version/draft checks and original candidate observer; an isolated index
produces only the tested repair plus the version line. No replacement build,
credential reader or backend publisher was introduced. Existing exact-slot
owner reader, scoped-record staging and original CI artifacts are reused.
Evidence: .cache/companion-wake-20261124/implementation.md,
.cache/companion-wake-20261124/delivery/observe-02/result.json, and
complete source-bound signer logs/metadata under delivery/records/inspect-06.
Actual phone verification is NOT_RUN;
future observation must be ready before owner testing, without opening the
App or triggering a firmware check from the collector. No repeated 1.5-hour
wait or successful OTA is requested merely to refresh logs.

## Owner-Confirmed Functional Closeout And 3.3.52 Delivery, 2026-11-23

Status: OWNER_VERIFIED_PASS / CANDIDATE_DELIVERED.
Owner: Codex root, record reconciliation only. Entry primary/remote main both
match ba3d5cc44344bfa0c8a2747949789d0380390be8.

The owner reports normal Bluetooth operation in the 23:00 Shanghai test and
explicitly confirms that both follow-up checklists have already passed:
- Automatic discovery, cross-page update prompts, Later not starting an upgrade,
  and the upgrade history/log results.
- Phone account-name display, logout/relogin terminal deduplication and the
  previously listed phone-side checks.

These are OWNER_VERIFIED_PASS outcomes from the owner's messages in this thread,
not new agent-executed tests. No exact installed version, per-case timestamp,
new raw capture or 3.3.52 installation is inferred from that confirmation.
The prior request to repeat or further clarify these checks is withdrawn.
There is no remaining owner test request or Bluetooth remediation in this
closeout. Earlier connection failures and cooldown observations remain valid
historical evidence, not current unresolved defects after the owner's report.
The one-hour automatic-check policy is unchanged; no policy change is requested.

MCU_TEST_3352 is delivered, not still building. The original one-click receipt
.cache/candidate-release/20261123T132806Z-d8ae7394/result.json reports DELIVERED:
- MCU 3.3.52 / 30352, source ba3d5cc44344bfa0c8a2747949789d0380390be8.
- Formal CI [45184334373](https://github.com/Eitan-S-23/E-Track/actions/runs/45184334373).
- Two R2-verified full/recovery assets registered, state ready; 641 warning
  lines and zero errors. Registration request e628d0ac-fb3c-48c5-b029-7f81ffbf6776.
- Target raw SHA-256:
  1837d78dfa903086c3ebd701b5e69c7976052ed0a2750d392a691ca669fe58b9.
The owner also confirms that Cloudflare received the package. The receipt's
channelPublished=false is the registration-time state, not a new live channel
query. Later publication, delta state and the installed target are not inferred.
No candidate rebuild, download, publication or OTA is needed to close this record.

The user-facing batch is closed on the owner's verification. Formal whole-card
independent acceptance is not performed or promoted to PASS by this record;
existing obligations remain separate, with no new device run or reviewer
spawned. Earlier pending labels for the confirmed checks and 3.3.52 build are
superseded by this section, not instructions to repeat successful work.
Older failures, pending edits and original evidence remain preserved.

The owner authorizes a scoped documentation commit and push to main. Only the
new closeout blocks in this note, the shared index and the main board/session
log are selected; older pending edits remain untouched. The exact commit,
push/readback and preservation checks are recorded in
.cache/owner-closeout-20261123/delivery/result.json, not inferred from this text.
Product code, App 1.0.94+120, MCU inputs, credentials, channels, deltas and device
state are unchanged. Board/receipt, link, whitespace and byte-preservation checks
cover this documentation closeout; automatic checks may run on the push, but no
App/MCU rebuild, device test or backend deployment is requested.

## Owner-Requested MCU Test Candidate, 2026-11-23

Status: CANDIDATE_DELIVERED / OWNER_PUBLICATION_AND_OTA_PENDING, Codex root.
The owner reports that the
3.3.48 -> 3.3.50 compatibility upgrade and device binding have succeeded and
explicitly cancels further compatibility-delta remediation. That report
supersedes the pending policy-choice/upgrade/binding statements below; it is
OWNER_REPORTED, not a new hardware readback or independent acceptance. The
original full-only diagnosis and its evidence remain unchanged.

The owner requests one new MCU-only test package through the existing one-click
entry. Current primary/remote main is bd599c2a; MCU is 3.3.50 and App is
1.0.94+120. The supported release_candidate.bat / Tools/ota/release_candidate.py
route owns version selection, Release/draft/tag checks, version-only commit,
main push and exact-source formal GCC candidate observation. It does not publish
Stable/Beta, generate/enable deltas, check the App or operate a device.

The entry requires clean tracked files, but six existing pending documents must
be retained. A task-local thin Host adapter ignores only their exact frozen
hashes in unstaged-document checks; it rejects staged/other/concurrent changes
and keeps the original single-version-file commit and first-push guards.
The default whole-worktree whitespace check flags pre-existing CRLF lines;
only the selected version file is checked for this delivery. The original
release/credential-reader files stay unchanged. Evidence and original document
bytes are under .cache/mcu-test-20261123; formal receipts remain under
.cache/candidate-release. No App bump, backend deployment, credential change,
new agent, package download or repeated successful upgrade is requested.

UID provenance: USER/HAL/HAL_Bluetooth.cpp:55 reads the three factory 32-bit
UID words at 0x1FFFF7E8, 0x1FFFF7EC and 0x1FFFF7F0 and formats them in that
order as 24 lowercase hexadecimal characters. CompanionControl.h:187 sends
that value in the session-bound UID reply; OtaService validates and uses it for
device binding. It is silicon identity, not BLE address, an App-generated UUID
or account ID. Ordinary firmware/data/account changes do not generate a new
chip UID; replacing the MCU changes the hardware identity. No actual UID is
read or exported in this task.

Delivered MCU 3.3.51 / 30351, source
ddc0a638ecbe34cb874e15dca51f33ed98360182. Formal first-push Actions
[45176505831](https://github.com/Eitan-S-23/E-Track/actions/runs/45176505831)
passes checks and firmware; App is skipped. The source differs from formal
3.3.50 only in the MCU version/notes across the firmware inputs. The original
entry's 24 offline tests and the bounded document adapter's seven tests pass.
Firmware logs retain 641 warning lines and zero errors, not warning-free.

Automatic registration is ready/unpublished, two R2-verified full/recovery
assets, productionApproved=false and channelPublished=false. Release ID:
fw_052e1b611aa08496839b970aca157038afafa70cb35fb23cf976198892202b4f.
Target raw image SHA-256:
7d2af1699caaa5887ed6e07cc9a4ca96e079153e7bea602f9f3362ecba18f89a.
Full envelope: 304677 bytes, SHA-256
6ff5bf3d7fee0a9f001f607af12a634fa7b0739367116d00c0dba13b18f9451d.
Recovery: 635868 bytes, SHA-256
daf8ed858ec4e88a812753e5a88492c4e60b08f4f17c5dcdd97e5a7907a90cec.

The first script invocation created the correct single-file commit but its
push received a connection-reset error. Fresh remote readback proved the push
absent. One reconciled push of that same SHA through the existing Git proxy
succeeded; the supported --resume then observed the original first-attempt CI.
No repeated bump/build/dispatch. Failed original receipt and command-038.log:
.cache/candidate-release/20261123T122841Z-fbec46ab. Push reconciliation:
.cache/mcu-test-20261123/push-reconcile-01. Delivered source-bound receipt:
.cache/candidate-release/20261123T124217Z-28d10bbe/result.json; it retains the
inherited original error as historical context while phase/registration are
DELIVERED. The dry-run receipt is 20261123T122639Z-a740cb76.

Next owner: publish existing 3.3.51 to the desired channel; for a delta test,
generate and enable exactly 3.3.50 -> 3.3.51 before checking from the bound
device. For a full test, leave that matching delta disabled. No agent channel,
delta, check, OTA or device action occurred. The owner's previous successful
upgrade/binding is retained without replay; this candidate is not installed
and does not prove physical or independent OTA acceptance. Only this new
section/board/index/log record is selected for main; six older pending document
blocks and their raw snapshots remain preserved.

## Cloudflare Account Quota Display, 2026-11-23

RESOURCE-QUOTA-DISPLAY: CODE_ON_MAIN / ADMIN_LIVE_VERIFIED, Codex root. Product
source is c503165fe236ebdcf29fa8cd6f7aeb5e55f64515; fresh primary and remote main
match it at deployment. This task started from 504a2eaa. The owner requests quota display and
deployment/testing of the existing Admin. This admits bounded source delivery
and Admin Pages deployment, not credential/configuration changes, channel/delta
actions, App/MCU rebuilds or device operations. No additional agent is started.
The six pre-existing dirty document blocks are preserved; pre-edit bytes/hashes
are in .cache/quota-display-20261123/entry-01/before.json.

Reuse the successful corrected-personal-token billing and account analytics
probes. The missing R2 storage schema is qualified once in research-04: dimensions
are date/bucketName, and 81 Standard rows cover 27 billing days. The failed earlier
query and unavailable workers/limits route remain evidence, not retried routes.
Subscriptions are a single-page endpoint in the installed Cloudflare SDK. Default
Workers Free can be classified only from a complete valid subscription list,
standard account metadata and absence of any unknown Workers/contract plan;
R2 Paid does not imply Workers Paid. Never use component_values as free quotas.

Implement account-scoped Workers plus Pages requests, D1 rows/storage inventory,
DO requests/duration/SQLite rows, and billing-period Standard R2 operations and
daily storage peaks. Only documented limits of an established plan apply. R2
GB-month is a labelled 30-day daily-peak estimate with coverage, not current bytes
or an invoice; IA is excluded. Unsupported meters, missing periods, empty samples,
denials and truncated inventories stay unknown. Failed refreshes retain the old
values AND their original plan/window/reset time as stale.

Reuse the D1 15-minute cache/90-second refresh lease and response/timeout bounds.
Extend the existing resource panel without redesign, keep controls reachable and
exercise narrow/short/enlarged-text, actor/refresh races and failure states. After
contained self-tests and exact-source backend CI, deploy only Admin with pinned
source_sha, include_worker=false and include_public=false. Verify source, assets,
real owner Access, populated quota API/UI and unchanged runtime/channel identities.
These are implementation self-tests/live checks, not independent acceptance.

### Implementation And Self-Tests

The account/provider collector, v2 cache, separate account/project display and
published API contract are implemented. Quotas never use subscription component
values. R2 uses Standard-only actions, actual renewal boundaries and explicitly
labelled daily peaks / 30 estimates; unsupported storage meters remain unknown.
The panel preserves its design and now keeps Close reachable while scrolling.

Complete local host run host-full-02 passes 645/645 in 22 files; ui-full-01 passes
314/314, including narrow/short and 200% text, zero/unknown/overage, failed and
malformed refresh, actor races, scrolling and close/focus behavior. Worker/Admin/
Public typechecks and 60 proxy/deployment contracts pass. The missing local Admin
Node types/Public compiler are reused from project-installed exact locked
versions; no SDK/package installation or credential/configuration change.

Original host-targeted-01 (33/34, ISO spelling oracle), ui-targeted-01 (5/6,
test assumed an error dialog left the resource popover open), local missing-type
commands, and host-full-01 (621 passes plus a SYSTEM/SU Git ownership blocked
suite) are retained. Corrected lifecycle assertions keep the real shared error
dialog behavior; a project-only ephemeral safe.directory resolves ownership.
No global Git config, old evidence or product criterion is altered. Final tested
product remains unchanged after the complete passes.

One installed-bundler product probe in live-collect-01 uses the registered token
without raw billing/secret output and returns 11/11 supported balances. Requests
254/100000, D1 read 27922/5000000, write 101/100000 and storage 0.014147584/5 GB;
DO request/duration/rows are measured. R2 A 446/1000000, B 2842/10000000; Standard
storage estimate 1.2709962915/10 GB-month, remaining 8.7290037085, across all 27
elapsed billing days. These are timestamped account statistics/estimates, not a
bill or a deployed UI claim. No cloud mutation occurs in this product probe.

Warnings: local Node experimental SQLite, Playwright NO_COLOR/FORCE_COLOR and a
slow test-file advisory. A whole-worktree diff-check also detects existing mixed
CRLF/trailing whitespace in older pending board lines; they are not bulk cleaned.
Scoped product checks pass, and only this task's selected LF record blobs enter
the delivery commit; older pending content is not staged wholesale.

### Source And Live Deployment

Product delivery c503165f is confirmed by deliver-01, without an App/MCU version
change or build. Exact-source backend CI
[45157043450](https://github.com/Eitan-S-23/E-Track/actions/runs/45157043450)
passes 603 Worker tests in 19 files, 314 browser tests and all three typechecks.
The broader local 645-test host scope is recorded separately above. Original
candidate and ordinary build jobs skip App/MCU packages as intended.

The first verifier attempt exits before cloud execution because its composed
source redeclares service. compose-check-01 retains that SyntaxError; the minimal
adapter fix passes compose-check-02 without credentials/cloud execution. The
successful read-only keyring-cloud-live-501 snapshot writes zero database rows.
No completed operation or failed receipt is replayed or overwritten.

One Admin-only dispatch of deploy-cloudflare-admin.yml, pinned to c503165f with
include_worker=false/include_public=false, completes in
[45160962404](https://github.com/Eitan-S-23/E-Track/actions/runs/45160962404).
Canonical Admin deployment is b6eed4f0-7e4f-4937-b73b-0c7674e2a5c8. Dispatch
acceptance, successful CI and actual live verification are separate receipts.
Worker/Public retain cc8039e4 and their exact prior deployment identities,
runtime hashes and schedules. Settings and all 19 migrations are unchanged;
four channel pointers and all 63 delta identities/attempts/input hashes match
the fresh pre-deploy snapshot, not the older 62-delta historical checkpoint.

keyring-cloud-live-502 verifies the real owner Access session and served HTML
plus ten JS/CSS files against Git blobs. The deployed API returns 11/11 supported
balances. At 2026-11-23 11:02:17 UTC / 19:02:17 Shanghai: requests 320/100000,
D1 reads 40653/5000000, writes 124/100000, storage 0.014155776/5 GB; R2 A
448/1000000 and B 2847/10000000. Standard storage estimate remains 1.2709962915
of 10 GB-month, leaving 8.7290037085, across 27 complete sampled days in the
actual 2026-10-28 to 2026-11-28 UTC billing period. Values remain timestamped
analytics/estimates, not invoice balances. CPU shows its per-invocation limit;
unsupported complete DO storage remains unknown rather than becoming zero.

Populated native quota UI passes 1440x1000 desktop, 360x520 mobile and 320x400
with 200% text, with no horizontal overflow/page errors and a reachable working
Close. Screenshots are cropped to the resource panel under the new private
evidence directory. Real notification acknowledgements are intercepted and
other business writes blocked; only the resource GET's own cache refresh is
permitted. No synthetic accounts, mail, quota reset, token/configuration change,
channel/delta action, device operation or extra agent occurs.

CI retains Worker 13 dependency advisories (3 moderate/10 high), Admin/Public
four high each, and workerd fixture reset/disconnection diagnostics; all tests
pass, not a claim that raw error logs are empty. CI and deployment artifact
uploads retain DEP0040/DEP0169. No unrelated dependency upgrade is mixed in.
Originals are ci-status-02/ci-logs-01, deploy-01/deploy-status-01/deploy-logs-01
and keyring-cloud-live-501/502 under .cache/quota-display-20261123. The scoped
record closeout and selected-output audit are separate closeout-03/final-audit-01
receipts. closeout-01 retains an EOF on the read-only GitHub /user request before
any index/commit/push operation; closeout-02 similarly fails on the remote-main
metadata GET. direct-read-01 qualifies the same target/credential via direct
GitHub transport. Only this task's process-level NO_PROXY for GitHub is adjusted;
no global proxy, credential or cloud configuration changes. Only metadata/record
delivery is retried, not deployment. Older pending documents/failures remain preserved; no system-wide
zero-I/O or independent acceptance claim follows from these checks.

## Account Backend Rollout Completed, 2026-11-23

Status: CODE_ON_MAIN / APP_CANDIDATE_DELIVERED / BACKEND_LIVE_VERIFIED /
OWNER_PHONE_AND_DEVICE_VALIDATION_PENDING, Codex root. Product source remains
`cc8039e41c13e0300db6d656103b7cefb3579880`; primary/remote main at entry match
`f2bb573c853f1c97de7cd28c580913606ad8281e`. Existing task worktree is clean;
no active J-Link/RTT/BLE collector is found. No extra agent, repair, product change,
rebuild or hardware replay. The owner's explicit backend-deployment request plus
continued-work authorization narrowly supersedes the earlier deployment-pending
checkpoint. Channels/deltas, credentials/configuration and phone/device actions
remain outside this rollout; the earlier candidate adapter guard stays unchanged.

One dispatch of the existing deploy-cloudflare-admin.yml, pinned to tested
cc8039e4 with Worker/Public included, completes in
[45076742719](https://github.com/Eitan-S-23/E-Track/actions/runs/45076742719).
Accepted dispatch, completed CI and actual live verification are now separately
confirmed. Exact-source checks 45071318738/45069818091 are reused, not rerun.
Worker version/deployment are 788ecbc4-2191-4508-b996-5dc9aac54db8 /
9a33119c-0ffe-4aa7-aad3-e0f16179a36e; Admin/Public are
3831978c-6859-44a2-9068-029c52a29d5f / 6049bb98-146a-475e-87b8-9dad1b8e9191.
All three sources match cc8039e4. No migration is pending/replayed; 0019 is last.
Runtime/schedules/production/preview, email-on revision 2 and 5/5 are unchanged.
Four channel pointers and all 62 delta identities/attempts/input hashes match
fresh before/after snapshots. No channel/delta/credential/device mutation.

Live readback at 2026-11-22 22:18 UTC / 2026-11-23 06:18 Shanghai passes existing
owner access, HTML/ten JS-CSS assets, account/detail/terminal/device APIs and both
Public/Worker auth routes. There is one real account and terminal, zero bound
devices. Guest cloud calls remain 401/LOGIN_REQUIRED; no synthetic account,
revocation, mail resend or quota reset. Existing warnings remain Worker 13
(3 moderate/10 high), Admin/Public four high each and two upload DEP0169 warnings.
This is live deployment verification, not independent or physical acceptance.

Final owner window, deferred until the owner is available:

1. Publish the existing App 1.0.94+120 candidate and update the phone without
   clearing data or substituting debug. Android Stable currently remains 1.0.93;
   no agent publication or actual phone installation is claimed.
2. Check logged-in username/email, logout/relogin returning one terminal, detail
   dialogs, both scroll edges, whole-row selection and visible logout. Phone
   interactions remain pending rather than inferred from CI.
3. Report actual MCU version and validate its real UID/account binding. Only a
   still-3.3.48 device needs the existing explicit logged-in formal 3.3.50 full
   compatibility path. An already-upgraded device must not repeat that OTA or
   J-Link installation; existing 3.3.50 is not rebuilt.
4. Agree actual identities/channel/target before one bounded remaining background/
   global-offer/Later/OTA window. Note start/end times and return App complete
   export, not only the newest page. Correlate control-ready, check/skip reasons,
   received versus shown offers, durable progress, reboot identity and history.

Use a fresh project-local evidence directory at the window's preflight. No agent
check/OTA clicks, quota/reminder reset, data clearing or successful-OTA replay to
repair collection gaps. USB is optional only for a named missing native/system
observation, after retrieval/deadline/single-owner/closure preparation. Missing
close time stays unknown; a reused connection is not a reconnect. Notification
disappearance alone does not prove process kill. Historical failures and confirmed
mail/registration/reset/candidate outcomes remain unchanged.

Originals, pre-edit pending document bytes and scoped closeout:
`.cache/account-identity-20261123/rollout-*` and `keyring-cloud-live-401/402`.
Only this new rollout block and board lines are staged; older pending content is
preserved, not cleaned or staged wholesale. Final audit covers selected outputs,
environment defaults and inspected subprocess routes, not system-wide I/O claims.

## Account Identity And Terminal Follow-Up, 2026-11-23

Status: APP_CANDIDATE_DELIVERED / OWNER_VALIDATION_DEFERRED, Codex root. Owner approves implementation;
phone/MCU assistance is deferred until the end. Current primary and remote main
match `fa3e9ac740ddcd21316bca9a9971018fbbab171a`; the existing clean
`dev/flutter/ota-ui-20261121` worktree is fast-forwarded to that revision.
The earlier read-only remote freshness failure has recovered, not been hidden.
Five pre-existing pending documents and all historical evidence remain intact.

Confirmed defects: Profile avatar text is hard-coded, and AccountPage renders
per-login sessions instead of the endpoint's installation-keyed terminals.
The installation ID is already secure-store persistent across logout; server
terminal upsert already keys by account/installation. Do not regenerate identity,
merge phones by model or delete session history to hide duplicate display rows.

Implement reactive username/email display, separate terminal and session data,
real retained-session summaries and account-scoped terminal-wide revocation.
Keep existing bounded lists, detail/confirmation/result dialogs, edge-scroll
handoff, visible logout, Bluetooth guest access and unchanged account 5/5 quotas.
Add regression tests for logout/relogin, restoration, account changes, separate
installations, preserved history and narrow/enlarged-text layouts.

Reuse the prior contained host/CI helpers through fresh thin adapters under
`.cache/account-identity-20261123/`. Full development checks precede a new,
draft/tag-checked original-signed App candidate. Existing 3.3.50 is unchanged;
no device action, mail resend or successful-build replay. Resource queries stay
read-only with actual usage/unknown limits distinguished. Backend deployment,
Stable/Beta, deltas, phone actions and real OTA stay owner-operated. Prepare the
exact-source deployment and final observation/log-retrieval handoff, not a live
device window while the owner is unavailable. Self-tests are not acceptance.

### Identity Implementation And Development Checkpoint

Status: CODE_ON_MAIN / FORMAL_APP_PENDING / OWNER_VALIDATION_DEFERRED. Product
source `cc8039e41c13e0300db6d656103b7cefb3579880` is integrated and pushed to main.
The existing task worktree is clean. Integration verifies unchanged hashes for
all five already-pending primary files and the same 1,150 untracked entries.
Only 11 scoped product/rule/test files entered the product commit; no mail,
historical helper, credential, firmware or unrelated file was staged.

Both Profile and AccountPage now subscribe to the same username/email identity.
Login, late restoration, account switching and logout update it without reopening
the page. The Profile label retains normal dimensions and expands only within
118..180 pixels for enlarged text; long identities have deliberate ellipsis and
full accessibility text. Terminal rows now use the existing installation-keyed
response, not per-login history. Same-model phones stay distinct. Shared dialogs,
full-row selection, bounded windows, two-edge drag handoff and visible logout
remain in use. Late account responses cannot restore cleared relation views.

| Development check | Actual result | Original evidence |
| --- | --- | --- |
| Flutter all, Ubuntu | 1,059 passed / 16 platform skips / 0 failed; analyze clean | `45069815624/1`, `app-logs-01/`, `full-linux-01/` |
| Flutter all, Windows | 1,007 passed / 68 platform skips / 0 failed; analyze clean | Same run, `full-windows-01/` |
| Candidate-profile tests | 8 passed on each host | Same full original artifacts |
| Worker invariants | 575 passed | `45069818091/1`, `backend-logs-01/` |
| Admin browser regressions | 308 passed | Same backend run |
| Worker/Admin/Public typechecks | All passed | Same backend run |
| Local terminal regression / Worker typecheck | 13 passed / passed | `host-terminals-02/`, `node-typecheck-01/` |
| Main backend checks | Success, no deployment | `45071318738/1` |

Flutter is 3.47.9 / framework c197ca5199e9ee5661e865596c9c07294dfab51c /
Dart 3.13.7. Two complete artifact archives, IDs 14773002143 and 14772926372,
match GitHub digests; all 12 full command logs match report lengths and actual
test footers through the existing full-log parser. Toolchain regeneration and
Windows header EOL-only restoration are bound rather than called source drift.
See `log-audit-01/result.json`; console truncation does not mean lost originals.
No new debug APK, local Flutter/Gradle build, SDK install or physical acceptance.

The first local terminal run has 7 passes / 6 failures: shared fixture IPs exhaust
the real auth limiter across test cases. Distinct fixture clients fix isolation;
production rate limits and assertions are unchanged. Original failure/closure is
`host-terminals-01/`. Artifact-list EOF is retained in `app-artifacts-list-01/`;
the next read succeeds without rerunning tests or packages. Worker dependencies
retain 13 advisories (3 moderate, 10 high), Admin/Public four high each, and the
existing SQLite/Node/Actions warnings. Do not report zero overall warnings.

App `1.0.94+120` is checked against all 132 releases/drafts and tag refs, then
rechecked before integration. Automatic formal parent `45071318837/1` selects
only App; firmware and duplicate ordinary APK/EXE builds skip. Its first ten-minute
observer expires while CI is still building; `formal-candidate-02/` continues
that same source/run without another dispatch, version bump or build. Final
candidate receipt is still pending at this checkpoint. Firmware 3.3.50 is unchanged.

### Identity And Terminal Implementation Contract

#### Scope And Signatures

This follow-up fixes active identity presentation and terminal/session confusion,
not login-token reuse, cloud quotas, online detection or device identity bypasses.
Normative interface requirements live in `docs/ui-design-contract.md` on main.

- App: `AccountService.identityLabel`, `terminals`, `sessions`, `refresh()` and `revokeTerminal(terminal)`.
- Existing read: `GET /api/account/sessions` returns independent `sessions` and `terminals` arrays.
- Terminal summaries: `installationId`, metadata, `state`, `current`, `lastLoginAt`, `sessionCount`, `activeSessionCount`.
- Existing mutation: `POST /api/account/sessions/revoke` accepts exactly one of `installationId` or legacy `sessionId`, both lower-case 32-hex.
- Confirmed response: `{ok:true,currentRevoked:boolean}`. App clears the current login only from the server receipt; missing receipts remain unconfirmed, never automatically retried.
- Database: existing `account_terminals(account_id,installation_id)` key; aggregate `account_sessions` by account/installation. No new schema or environment setting.

#### Contracts

Terminal summaries aggregate all retained sessions, not the 100-row display page.
Any unrevoked/unexpired session gives valid state; only expired unrevoked sessions
give expired; only revoked history gives revoked; no retained sessions give unknown.
Current is derived from the authenticated token hash, which is never returned.
The secure installation ID survives logout; each login still creates its own
session and login event. Legacy null IDs stay null and cannot be invented from a
phone model/address. Terminal revocation is account-scoped and touches only its
unrevoked/unexpired sessions; other accounts/installations and historical rows
remain. Existing scheduled retention remains, not a new lifetime-history promise.
Local view clearing changes neither reminders nor server-owned daily 5/5 quotas.

#### Validation And Error Matrix

| Case | Required result |
| --- | --- |
| Signed-out / restored login / logout / actor change | Correct live identity; no stale relation rows |
| Repeated real-handler login on one installation | One terminal, separate retained login history |
| Same model on two installations / same installation on two accounts | Separate correctly scoped rows |
| More than 100 history rows | Accurate active state, current flag and retained counts |
| Unknown legacy installation | Unknown, not fabricated/online/expired |
| Terminal-wide logout | All active matching sessions revoked; other scopes usable; history preserved |
| Missing/both/malformed selectors | INVALID_PARAMETER; no revocation |
| Missing receipt / failed follow-up refresh | Unconfirmed or REFRESH_FAILED dialog; no mutation retry |
| 320px and 200% text / row whitespace / both scroll edges | No layout exception; shared details/actions reachable; correct scroll handoff |

#### Good, Base And Bad Cases

Good: two logins yield one stable terminal and two retained sessions. Base: an
old null installation remains a historical unknown. Bad: merging same-model
phones or deleting login history to make the terminal list look deduplicated.

#### Tests Required

`account_service_test.dart` covers identity/restoration/actor changes, separate
arrays, confirmed revocation, receipt/refresh failures and late-response discard.
`account_page_test.dart` covers terminal rows, detail/confirmation/error dialogs,
whole-row taps, bounded lists and two-edge parent handoff. Profile settings tests
cover live identity and long names at 320px/200% text. Worker terminal tests cover
real auth-handler relogin, cross-account/install isolation, history limits,
unknown states and all revocation invariants. Green self-tests are not live UI,
background BLE reliability or independent system acceptance.

#### Wrong Versus Correct

Wrong: interpret per-login sessions as unique phones, merge by appearance, infer
online state from a valid token, or retry an uncertain logout. Correct: use the
existing stable terminal key, retain history, aggregate the full retained scope,
use the real server receipt and surface unknown/error states in shared dialogs.

### Resource Read And Deferred Owner Route

Read-only provider snapshot at 2026-11-22 21:10 UTC (Shanghai 2026-11-23 05:10)
uses CF-CI-01 and the existing `collectResourceUsage`, not the cache-writing Admin
route. All 12 GraphQL requests/20 metrics succeed. UTC-day project counts through
21:05 are Worker 1,859, Admin Functions 352, Public Functions 292, D1 rows read
127,406 / written 604. D1 storage is 12,791,808 bytes; the latest Standard R2
sample is 2,215,433,313 bytes, Infrequent Access zero. Monthly R2 Class A/B counts
are 343/1,716. See `resource-01/result.json` for actual scopes/windows/samples.

Subscription GET returns HTTP 403. Workers default usage model is standard, not
proof of a billing plan. Account allowance/remaining stay unknown; delayed/sampled
project analytics cannot be subtracted from an assumed account-wide free limit.
No new credential, login, permission, billing or cloud configuration change.
Live Admin/Public remain on source 95470e8e at this snapshot; latest product
backend changes have not been deployed. Mail activation/user-confirmed account
flows remain done, not repeated.

After the owner is available, use the existing `deploy-cloudflare-admin.yml`
with `source_sha=cc8039e41c13e0300db6d656103b7cefb3579880`,
`project_name=trace-update-admin-staging`, `branch=main`, `include_worker=true`,
`include_public=true`. This includes the previous still-undeployed Admin/Public
and legacy-route fixes plus the current terminal aggregation/revocation. There
is no new migration; preserve applied 0019, mail/verification revision 2, 5/5,
bindings, credentials, channels and deltas. Verify actual three-component sources
afterward; dispatch acceptance alone is not a live deployment.

Then publish/install App 1.0.94+120 without clearing data. Confirm live username/
email, one terminal after logout/relogin, distinct installations, detail dialogs,
scroll edges and visible logout. Report the actual MCU version before any OTA.
Only a still-3.3.48 device needs the existing formal 3.3.50 full compatibility
transition, followed by fresh real UID binding; no replacement firmware build,
J-Link installation or repeated successful OTA is needed for this follow-up.

Physical observation remains closed until the owner is available. Start with
App complete export (not just the newest local page), exact App/MCU/account/device
and target-package identities plus start/end times. Save originals under a fresh
bounded owner window and correlate reconnect/control-ready, check decisions,
offer/popup/Later, durable progress, reboot identity and persisted history. Never
reset quotas/reminder dedup or click checks/OTA for the owner. USB is optional,
only if a specific missing native/system observation requires a prepared bounded
collector. Do not repeat successful transfers to repair missing host evidence.

Backend rollout, phone layouts/terminal actions, actual UID/binding and remaining
background/global-notification/history correlation stay owner-pending, not passed
by this development batch. No extra agent, PowerShell, device action or channel/
delta operation. Historical failures and helper-loss incident remain unchanged.

### Identity Formal Candidate Delivered

App `1.0.94+120`, exact product source
`cc8039e41c13e0300db6d656103b7cefb3579880`, completes automatic parent
`45071318837/1` and original signer `45071476388/1`. Both Windows and Android jobs
pass. Signer workflow commit is still 12ff41fc, not product source. Native inspection
checks original package `com.wen.gaia.gaia`, original certificate 3cecee6330a930e0,
both ARM ABIs, original backend, BLE V2 and inventory. Existing CI fully uploads
and read-back verifies APK/manifest, then registers `rel_trace_android_v1_0_94`
with `ok=true,idempotent=false`. GitHub tag `v1.0.94` is a prerelease/not latest;
Stable/Beta, deltas and backend deployment remain untouched.

| Immutable asset | Bytes | SHA-256 |
| --- | --- | --- |
| `ble-monitor-android.apk` | 49,636,885 | `4b0729c5736e66e47eb1713982e8b5d1d351e3918b5f98ba91ae8d4e48f23a54` |
| `ble-monitor-windows.exe` | 161,792 | `2088fb4c5fbbaf7e3bd43f79a72ea4d2f9018b1391a2ee77cc360a9eb885ae7e` |
| `ble-monitor-windows.zip` | 20,886,370 | `af8fc50c7eca1292f999e4726fb054d63e1a79fa58f7a5d9cdfdc81d05c94e89` |

Android has ten build warning lines / zero error lines; Windows zero / zero.
Existing Gradle/AGP/Kotlin and SDK-36 plugin warnings plus earlier dependency/
Actions warnings are not hidden or fixed by this batch. Full original/native/R2/
registration checks are bound in `formal-audit-01/result.json`, with raw signer
logs in `signer-logs-01/`. Hosted metadata digest differs from post-R2 metadata
because the uploader adds verified R2 fields; immutable assets were not replaced.
The APK was not downloaded again or rebuilt to improve evidence.

The first candidate observer times out, the second ends on a GitHub metadata EOF,
and the third observes the same completed run. Those original failures remain in
`formal-candidate-01/02/`; no version bump, dispatch or package replay. A metadata
read mistakenly used the backend release ID as a GitHub tag and got 404; corrected
`v1.0.94` read succeeds. This was not proof of an unoccupied version, and no asset
was overwritten. The small offline presenter initially matched an echoed script
instead of its JSON log line; exact-line parsing then verified the originals.

Owner assistance remains last. When available: deploy the pinned three-component
backend using the parameters above, then publish/install App 1.0.94+120 and run
the prepared account/terminal and actual device observation route. No immediate
phone/MCU/USB action is requested. Firmware 3.3.50 remains the existing candidate;
only actual still-3.3.48 legacy migration needs that already-built full target.
Code/self-tests/formal candidate are delivered; live rollout, remaining system
verification and independent acceptance are not being marked complete.

Closeout selects only this follow-up's three record blocks against main, retaining
all older pending SMTP/registration records, deployment/mail documentation and
historical/untracked tools. Selected/controlled output paths are the authorized
primary/task worktree, Git metadata and `.cache/account-identity-20261123/`.
The final audit checks real paths, inspected child defaults and owned closures;
it does not attribute unrelated Windows/kernel activity. No PowerShell, extra
agent, device, backend mutation, channel/delta action or external cleanup.

## Account UI And Legacy Migration Follow-Up, 2026-11-23

Status: IN_PROGRESS / LOCAL_PENDING, owner-approved consolidated implementation.
Primary main and remote main match 6073f443. Existing task worktree
`.worktrees/ota-ui-20261121` / `dev/flutter/ota-ui-20261121` was clean and is
fast-forwarded to that main source; no setup/repair, new worktree or device access.
The five pending primary document changes were reviewed and preserved in place.
No extra agent, PowerShell or product-external output is used.

Owner reports registration/login succeeded after reopening the account page and
forgot-password succeeded. This supersedes prior pending/no-account observations
at their earlier timestamps, not proof of the original uncaptured request or
independent acceptance. Required email verification was observed enabled at
revision 2; retain it. Mailbox configuration and actual received email stay done.

Confirmed current defects: Admin relation views overwrite the account data shape;
`run()` renders before its protected try/finally, so switching back can throw and
leave controls busy. Details expand inline; account settings repeat in relation
views; Accounts is nested under APP. App logout follows all outer-scroll content,
device picker buttons only fit their labels, redundant explanations remain, and
registration requirements load only on page entry. Fix these as one bounded batch.

Shared normative rules belong in `docs/ui-design-contract.md`, referenced from
root AGENTS, not just this task log. Upstream newAPI sources inspected on
2026-11-23: `web/src/features/users/index.tsx`, `components/users-table.tsx`, and
`web/src/features/system-settings/auth/basic-auth-section.tsx`; current web subtree
0f6c90cc7e0a06fe383001bab4ea71951f5da0e7. Reference its separate paginated/filterable
user table and grouped authentication settings. Do not claim a complete upstream
visual review or copy its drawer styling over E-Track's established modal design.

Firmware 3.3.48 source 5d81e6b9 lacks IDENTIFY/UID; App's cloud/binding gates need
that real UID. Existing formal 3.3.50 source 91916e11 / CI 44970721130 supports it.
Implement an explicit, logged-in, package/device-bound legacy full-OTA migration,
not a fake UID or global gate bypass. Preserve current account 5/5 quotas, package
validation, user consent, Boot/data, true reboot identity verification and normal
binding. No J-Link write, channel publication, delta generation or phone action is
part of implementation. Owner will publish/install and exercise the prepared route.

Validation must cover populated repeated transitions, failures, modal/focus/scroll
boundaries, short/enlarged-text App layouts, row-whitespace taps, stale registration
requirements and the restricted migration allow/deny/verification paths. Full
Flutter development CI and scoped backend checks precede original-signed App
delivery and affected backend deployment. New runs are NOT_RUN at this entry.
Resource-usage checks follow actual provider APIs and existing credential authority;
unavailable limits/usage stay unknown. Do not alter credentials or billing.

New controlled evidence belongs in `.cache/account-ux-20261123/`, not the four
overwritten historical helpers. Their loss remains open; no guessed restoration
or cleanup occurs. Existing primary local edits and all failed receipts remain.

### Implementation And Development Checkpoint

The tested product source is `dbcf94cf6424eec00e5fb0d8fae7140e82928ba2`, now
fast-forwarded and pushed to primary/remote main. The task branch remains clean.
All five pre-existing pending document byte hashes and the 1,150-entry untracked
inventory were unchanged by integration. Only this batch's 28 product/rule/test
files entered main; historical mail/support-tool changes were not staged.

Admin now owns separate paginated account/terminal/device lists, modal details,
focus restoration and independent settings. Loading/rendering failures restore
controls. The last failed browser case exposed a real lost query while a list
was busy: retain the latest search intent and execute it after the current
request, resetting it on actor changes. Its deterministic gated-response test
and all 16 local account browser cases pass; the original 307-case failed run
and earlier development failures remain preserved, not rewritten or rerun.
App logout stays outside growing lists, connected-device rows accept whitespace
taps, registration refreshes requirements before submission, and account errors
retain validated field/request correlation without recording submitted values.

| Check | Actual result | Original evidence |
| --- | --- | --- |
| Flutter all, Ubuntu | 1,045 passed, 16 platform skips, zero failures; analyze clean | `45055320407/1`, `resume-app-logs-01/` |
| Flutter all, Windows | 993 passed, 68 platform skips, zero failures; analyze clean | Same run and console archive |
| Candidate-profile tests | 8 passed on each host | Same run |
| Worker invariants | 568 passed, 18 files | `45055321435/1`, `resume-backend-logs-01/` |
| Admin browsers | 308 passed | Same backend run |
| Worker/Admin/Public typechecks | All passed | Same backend run |
| Targeted account browser regression | 16 passed | Existing `ui-query-01/`, reused without another execution |

Flutter is 3.47.9, framework `c197ca5199e9ee5661e865596c9c07294dfab51c`,
Dart 3.13.7. Console detailed-test output is explicitly truncated by its budget;
both full log artifacts are retrieved and verified in `resume-full-linux-01/`
and `resume-full-windows-01/`, without rerunning either successful self-test.
Artifact IDs are 14767670670 and 14767466548. All 12 complete command-log byte
counts/SHA-256 values and the actual test footers match the source-bound reports;
details are in `resume-records-01/log-evidence.json`. The first offline checker
mistakenly required literal post-test cleanliness. Windows retains only EOL drift
in `generated_plugin_registrant.h`, no semantic/untracked drift; the existing
runner's semantic/source-regeneration contract was applied without changing CI,
the source or any original log. Both controlled toolchain regeneration records
and the unchanged lockfile are retained.
SDK/runner/native inputs unchanged by this batch are not retested on a device.
These are development self-tests, not independent acceptance or actual OTA.

Version/draft/tag preflight checks all 131 Trace releases, including drafts:
`1.0.93+119` was unoccupied. Integration receipt is `resume-integration-01/`.
Automatic formal parent `45057066631` selects only App; firmware and duplicate
ordinary APK/EXE builds skip. The final completed delivery is recorded below;
the earlier bounded observation timeout is not a failed CI or another build.
Firmware 3.3.50 remains unchanged.
Worker dependencies report 13 advisories (3 moderate, 10 high); Admin/Public
each report 4 high advisories. Existing install-script and Node/Actions warnings
remain visible. No dependency upgrade, backend deployment, credential change,
mail resend, phone action, J-Link write, channel publication or delta operation.

### Legacy Migration Implementation Contract

#### Scope And Trigger

Only an explicitly selected, logged-in, current 3.3.48/protocol-1 device without
UID may prepare this full-OTA transition to the existing formal 3.3.50. It is not
an automatic-check, binding or recovery bypass. Ordinary UID-bound routes remain
unchanged; this description grants no additional deployment or device authority.

#### Signatures

- App: `AccountCheck.forLegacy(check)` and `checkFirmwareUpdate(legacyMigration: true)`.
- Latest: `GET /api/public/firmware/latest`, manual check ID/kind, `X-Legacy-Migration: uid-v1`, exact source image/version and hardware/layout/Boot/protocol query fields.
- Download: existing signed `GET /api/public/firmware/download` plus `X-Legacy-Migration-Check-Id`, authenticated to the same account.
- BEGIN authorization: `POST /api/account/ota/authorize`, `legacyCheckId` and the grant's exact source/target/hardware/asset fields.
- Storage: completed/manual `account_update_checks.response_json`; authorization writes the existing `account_audit` action `legacy_ota_authorize`, not a new schema or fake binding.

#### Contracts

The server-owned grant binds account/check ID, source version/raw SHA, hardware
revision, layout, Boot/protocol, target version/raw SHA/release, asset ID/SHA and
expiry. It expires 24 hours after the original check; refresh does not extend it.
Source must match a registered formal 3.3.48. Target is only 3.3.50 source
`91916e11469fce94282a9e1a0254048f4e4a9d7f`, raw image SHA-256
`6e763fb66958d4a4db3b9cbf7b02351184c189165d5499faf26986421273762a`.
Both Worker and Public forward full-only selection through the common handler.
Existing quotas, signed download purpose, package verification, consent, power/
recording/storage gates and reboot version/raw-image verification remain intact.
No synthetic UID or automatic binding is written. After a real successful OTA,
read the target's real factory UID and bind normally; the fake-BLE success test
intentionally leaves UID null and is not a live identity/binding observation.

#### Validation And Error Matrix

| Input/state | Required result |
| --- | --- |
| Exact registered source, published exact full target, logged-in manual check | One account-scoped grant; same check ID follows download and authorization |
| Ordinary/automatic check, wrong current device, missing login | No legacy bypass or BEGIN |
| Wrong account/check/source field, duplicate query, expired grant | `LEGACY_MIGRATION_INVALID`; no transfer |
| Missing/wrong formal source or target, or non-full target asset | `LEGACY_MIGRATION_UNAVAILABLE`; no transfer |
| Explicitly stopped channel | Existing `CHANNEL_STOPPED` no-update response, no grant or transfer |
| Invalid existing signed download token | Existing signature verification rejects it |
| Account/device changes after preparation or authorization rejects | BEGIN remains zero; preparation cannot redirect devices |
| Reboot identity does not match target version and full raw SHA | Not upgrade success; existing failure/waiting-verification history semantics remain |

#### Good, Base And Bad Cases

Good: the same explicit account/check/device uses the exact signed full package,
then verifies the target after reboot. Base: ordinary cloud checks still require
the real UID binding. Bad: pretending a Bluetooth address is UID, accepting an
arbitrary latest version, or counting END ACK as installation success.

#### Tests Required

`worker/test/account-legacy.test.ts`, `test/ota/ota_legacy_migration_test.dart`
and the real `OtaService` integration cases cover full-only selection, quota/check
reuse, signed-download binding, allow/deny/expiry, account/device substitution,
authorization-before-BEGIN and reboot verification. Account widget/service and
Admin browser cases cover refresh/errors, full-row taps, short/200%-text layout,
scroll/focus/modal boundaries, repeated populated views and busy-search coalescing.
Actual legacy OTA, factory UID/binding and phone layouts remain owner validation.

#### Wrong Versus Correct

Wrong: disable global UID admission, silently use a different package, or drop
search input while the list is busy. Correct: restrict the persisted grant to
this one formal transition, retain final identity checks and execute the latest
queued search once after the protected request ends.

### Formal App Delivered, Backend And Phone Pending

Status: APP_CANDIDATE_DELIVERED / BACKEND_AND_PHONE_PENDING. Exact main App source
is `dbcf94cf6424eec00e5fb0d8fae7140e82928ba2`, version `1.0.93+119`.
E-Track parent `45057066631/1` and original Trace signer `45057226109/1` succeed;
both Android APK and Windows EXE/ZIP jobs pass. Trace workflow commit remains
`12ff41fc11eb4920ab32d69ae0f7e1cc095f996e`, not the App product source. No new
MCU or duplicate ordinary App build. Main backend `45057066635` and governance
`45057066443` pass; no deployment was dispatched by this continuation.

Native inspection verifies package `com.wen.gaia.gaia`, original certificate
SHA-256 `3cecee6330a930e020b454b6d4a79568f4494ca324ae7bcf2c1914e51b04ab47`,
both ARM ABIs, original backend, BLE V2 profile and inventory support. The native
APK/manifest hashes match GitHub assets. CI fully uploads/read-back verifies the
two original R2 assets, then registers `rel_trace_android_v1_0_93` with
`ok=true`, `idempotent=false`. The GitHub tag is a prerelease, not latest;
Stable/Beta are not published. Exact original logs/receipts are retained under
`resume-candidate-01/02`, `resume-signer-logs-01/`, `resume-formal-metadata-01/`
and `resume-records-01/formal-candidate.json`. The first observer merely expired;
the second observes the same parent/signer without dispatching or rebuilding.

| Immutable asset | Bytes | SHA-256 |
| --- | --- | --- |
| `ble-monitor-android.apk` | 49,636,885 | `95bdc67e7e2ea7e6f2cd089e8f1fe4bc5d73aa9ba05aa81adceadc95d78035f0` |
| `ble-monitor-windows.exe` | 161,792 | `2ce1f10c7a54249d1eed78f94c0d5034efc4a89b83abf6379ee4a6761292be19` |
| `ble-monitor-windows.zip` | 20,886,436 | `52cd8295c8d45968ac356f937c8cb21fc85ac6e0a8a77ccf728e4c788cbdc667` |

Formal Windows/Android full tests pass 993/68 and 1045/16 (passed/skipped), with
clean analysis. Windows has zero build warning/error lines; Android has ten
warning lines and zero error lines: existing Gradle/AGP/Kotlin deprecations and
seven plugins requiring SDK 36. Dependency/Actions warnings remain as recorded
above; no toolchain/dependency upgrade was added to conceal them. GitHub's hosted
pre-upload metadata digest differs from CI's post-R2 metadata digest, since the
uploader adds verified R2 state to its own working metadata. Neither immutable
GitHub asset nor APK/manifest bytes were replaced; those stages are not conflated.
No package was downloaded again just to improve this report.

Owner actions, in order:

1. Run the existing `deploy-cloudflare-admin.yml` from main with `source_sha=dbcf94cf6424eec00e5fb0d8fae7140e82928ba2`, `project_name=trace-update-admin-staging`, `branch=main`, `include_worker=true`, `include_public=true`. Verify actual Worker/Admin/Public sources and retain current mail/settings/5+5 quotas. There is no new migration in this batch; do not rerun applied SQL, change secrets or rebuild packages.
2. Publish App `1.0.93+119` in the original Admin and update the phone without clearing data. Check populated account/terminal/device views, modal/scroll/focus behavior, visible logout and registration requirements. Report the installed App and current MCU versions before the OTA observation window.
3. Only if the current MCU is 3.3.48, use the existing formal 3.3.50 as the full migration target. Owner publishes it; no delta generation is required. Prepare source/package/task-bound observation and full log retrieval before inviting the real transfer. Account-page binding offers `兼容升级`; `稍后` must not transfer. After reboot verification, read and bind the real UID normally.

Live backend deployment, phone installation/layouts, actual legacy full OTA,
post-reboot UID/binding, automatic discovery/global popup/Later/recovery and
history/log correlation remain NOT_RUN by this continuation. Existing P01/U01,
successful firmware installation/OTA observations and original evidence are not
replayed. All selected outputs stay project-local; no PowerShell, extra agent,
device access, backend mutation, email, channel/delta action or external cleanup.
Historical helper loss remains disclosed and unresolved. Only this batch's
record blocks are eligible for the scoped main closeout; other local edits stay.

## Account And Layout Batch, 2026-11-22

### Account Relationships And Unified Results

Status: REMOTE_DELIVERED / MAIL_ACTIVATION_AND_PHONE_VALIDATION_PENDING. Owner approved proceeding with
unified Admin feedback and account/App-terminal/MCU relationships; mailbox SMTP
activation is explicitly last. Test recipient is owner-provided, not automatically
an approved sender. No domain purchase, credential configuration or real send.

The new 0019 migration keeps installation identity separate from account and
hardware UID. Legacy terminal metadata stays unknown. Account/session ownership
is checked server-side; public and Admin session views never expose token hashes.
Latest terminal/device observations are timestamped reports, not proof of online
presence or cryptographic device ownership. Reports do not consume the 5/5 update
allowances and failures must not change a BLE/OTA outcome. Unbinding removes the
corresponding observations. Sessions can be revoked individually; terminal and
device views link to the owning account. Retention is 90 days for observations.

Admin reuses its existing result/confirmation dialogs. Account/feedback operations
no longer duplicate the result as inline notices; inventory-detail failures now
request the common error dialog too. Loading/stale-data status remains inline.
Mail remains unconfigured, cloud admission remains protected, and the existing
original-signed 1.0.91 installer remains the bootstrap path for 1.0.89.

Self-tests so far: accounts-host-203 has 27 passing cases; accounts-check-202
typecheck passes; ui-account-links-201 has 77 browser cases passing. Original
accounts-host-201 preserves four fixture failures (missing Content-Type, corrected
without weakening production validation). Expanded browser and dual-host Flutter
checks are pending. Evidence stays in .cache/ota-followup-20261122/. No new release,
deployment, channel/delta operation, account creation or physical-device test yet.

Development c8c80bf0 has successful dual-host Flutter run 45010872358. Original
4badaac8 run 45009223527 passes its tests (Linux 1010/16 skips, Windows 958/68
skips) but fails analysis because package_info_plus was only transitive. The fix
declares the existing locked 9.0.1 directly; no dependency version or SDK upgrade.
Backend 45009338170 passes 528 Worker and 297 browser tests plus three typechecks.
Local ui-account-links-202 retains six old inline-result oracle failures; the
same checks now assert the common result dialog and ui-account-links-203 passes
all 97 version-operation cases. Account desktop/mobile screenshots and six
targeted tests pass in ui-account-links-204 after scoped typography/button fixes.

SMTP is the final implementation step: native TLS-only QQ/Foxmail adapter,
one-message deadline, bounded replies, no raw protocol logs, and existing orphan
code invalidation. accounts-host-215 passes 34 account/terminal/mail tests and
accounts-check-216 passes. Local Admin typecheck 205 is NOT_RUN successfully:
its retained dependency tree lacks @types/node; do not confuse that host failure
with CI's correctly installed dependency tree. Formal source CI remains required.
No SMTP configuration or real send occurred. ACCOUNT-EMAIL.md specifies the
remaining owner mailbox steps. All 130 Trace releases including drafts and the
1.0.92 tag prefix were checked (keyring-read-219/220); 1.0.92+118 is unoccupied
and selected for original-signed delivery. MCU version/source are unchanged.

Final delivery: App source `29d619ffd2c3a00ab6b6be30b67b2efc8a0f1c79`;
backend source `95470e8e3ea0f9245736f7076a8ff86eaa004925` only adds an Admin
unknown-total display correction. Original Trace run **45013457550** completes
admission/Windows/Android successfully and registers **rel_trace_android_v1_0_92**.
APK **1.0.92+118**, 49,604,117 bytes, SHA-256
`cc7e9b63756ee59818f8766f890976dd18ff734265db625f7ffa64a37e3f4c85`;
package `com.wen.gaia.gaia`, original signer SHA-256
`3cecee6330a930e020b454b6d4a79568f4494ca324ae7bcf2c1914e51b04ab47`.
Original signing CI verifies complete R2 bytes. GitHub v1.0.92 is non-draft and
all APK/EXE/ZIP assets are uploaded. Evidence: keyring-status-235,
keyring-logs-237 and keyring-read-238. No extra APK download or phone install.

Parent **45013327189** failed during post-dispatch observation with generic
BACKEND_UNAVAILABLE, request 2fbe44e6-ad90-46c9-b994-431401be9b0d. The exact
child's title binds source and original parent. Its continued run was observed,
not dispatched again. The parent is NOT green and was not rerun; actual signing
and automatic candidate registration completed independently of that lost receipt.
Failure evidence remains keyring-logs-227. Later same-version main pushes skip
App/firmware packaging, as confirmed by **45015301092**.

Final backend **45015301099** passes 535 Worker/297 browser cases and all three
typechecks. Deployment **45016534804** succeeds, applying only
`0019_account_terminals.sql`. Live readback keyring-cloud-live-240 verifies:
Worker `8e4b67c2-e14f-457a-8fee-12c8b56d1090`, Admin
`53c211c8-f9ca-4eef-959c-ef88df448007`, Public
`0ce6b61a-a0a1-4940-b233-a18c799cad63`, exact source/assets and real owner access.
Runtime/schedules, four channels and 60 delta identities match snapshot 224.
Account/terminal/device lists are empty on the live service, so real populated
account details remain owner-validation work; no synthetic live user was created.
Worker/Public/Admin report mail unavailable and email verification disabled.
No sender secret was entered, email sent, channel published or device operated.

Warnings retained: Worker dependencies 13 vulnerabilities (3 moderate/10 high),
Admin/Public 4 high each; Node/Actions deprecations and local experimental SQLite.
These were not hidden or remediated by unrelated dependency upgrades. Self-tests
and source/read-only live checks are not independent acceptance or phone/SMTP
inbox verification. Controlled-output audit:
`.cache/ota-followup-20261122/account-relations-delivery-audit-01.json`.

### Mail And Feedback Follow-Up

Owner asks to finish actual email delivery and align account/management notices
with the existing dialog UX. Root owns this bounded change on main above 8a9bd9e8.
Code inspection confirms App account errors and Admin account/feedback errors are
inline-only. Reuse TraceDialog and the Admin actor-scoped feedback queue; preserve
forms/drafts, cancellation, in-flight ownership and no duplicate mutations.
Mail currently uses Resend but no sender/API input or controlled recipient is
registered. Ask for the existing secure configuration locator/sender/recipient;
do not invent a domain, scrape secrets or send to guessed addresses. Complete
code/test work while this input is pending. No MCU change, device operation,
Stable/Beta publication or delta generation is included. Self-tests are not
independent acceptance or real mail delivery. All controlled outputs stay in the
project, reusing the existing host/CI adapters under .cache/ota-followup-20261122.

Development source `599dc4a3e1b8fbbd91c6b0882b0165ccd72b8fee` passes Flutter CI
**44995783785**: Linux 1007 passed/16 platform skips, Windows 955 passed/68 skips;
both analyze and eight candidate contracts pass. No debug APK was requested and
native Android inputs are unchanged. Backend **44995837038** passes Worker,
Public and full Admin browser checks. Local originals: `accounts-host-101`
(21 account/mail cases), `accounts-check-102` (Worker types),
`ui-account-feedback-101` (77 related browser cases), and `keyring-logs-110`.
All mail-provider calls in self-tests are mocked; no live message was sent.

Changes also preserve the expanded Admin settings panel and unsaved drafts,
report acknowledged mutations separately from a failed detail refresh, and avoid
late App dialogs after the page has closed. App account binding/password dialogs
now use TraceDialog; explicit feedback-page failures also use that component,
while passive outbox status remains nonmodal to avoid background popup loops.
Registration accepts an optional recovery email. Sending is one request per
mailbox/minute and five/hour, independent of OTA allowances. Rejected/uncertain
sends invalidate their code; reset flow checks verify old-session revocation.

All 129 Trace releases including drafts and matching tags were read in
`keyring-read-107/109`; **1.0.91+117** is the new delivery target. Version-only
metadata and this operational note follow the tested source. Formal APK/EXE,
candidate ingestion, updated backend deployment and mail activation are distinct
pending outcomes at this checkpoint. The sender/configuration/real-recipient
inputs remain missing. See the new supported [email contract](../../app/bluetooth_flutter_Trace/cloudflare/update-service/docs/ACCOUNT-EMAIL.md).

Main delivery source is `3296c633ee005fd6e48d20b51ab8c7b4ade0bd31`. Exact-source
backend **44996846216** and governance **44996846670** pass. Backend deployment
**44997943728** succeeds with no pending migration or SQL replay. Live readback
`keyring-cloud-live-119` verifies Admin `50873c88-50bf-4b39-8fd0-22e6a40d6098`,
Public `a2b388e3-a824-4dbd-8ea1-282092c58128` and Worker version
`e3b6c7a9-3b75-4274-866f-0dad40d5528c`, all on that exact source. A real existing
owner session reads the new HTML/ten assets and account endpoints. Four channels,
60 delta IDs/attempts/input hashes and runtime/schedules match this operation's
`keyring-cloud-live-116` baseline. Worker/Public/Admin all explicitly report mail
unconfigured; no real email or account creation occurred. Earlier counts of 59
belong to the previous deployment's original observation, not this later baseline.
Deployment warnings remain Worker 13 dependencies (3 moderate/10 high), Admin/
Public 4 high each, plus Node/Actions deprecations. Source/CI evidence and local
outputs remain under the existing task boundary. Audit:
`.cache/ota-followup-20261122/account-mail-feedback-audit-01.json`.

Formal App **1.0.91+117** delivery is complete: Trace original-signing run
**44996956524** passes admission/Windows/Android; E-Track parent **44996846280**
passes checks/App and skips firmware. Native steps confirm full-byte R2 readback
and candidate registration, with no channel publication. GitHub release metadata
(`keyring-read-130`) confirms v1.0.91, prerelease/non-draft, exact E-Track source
and all uploaded original package assets. APK: 49,587,733 bytes, SHA-256
`0e0bb33d892a38b296cc359e9a49e34419ada5eb26868f3e3de168834e7d45a2`.
Windows EXE SHA-256:
`6c94bf99d2b97094924b544aadf3a32e3796ca96cb1a49f2d5450b533961bc55`;
Windows ZIP SHA-256:
`3024f88551ec96d29c2f2ee5084f46516d366d91aa919acd5cb1b20fe019691b`.
Agent did not install the App or publish Stable/Beta. A transient status GET
failure (`keyring-status-125`) and Android log-read timeout (`keyring-logs-127`)
are preserved; a fresh read verifies completion and only the missing Android
log is requested in `keyring-logs-129`. No workflow/build/upload is replayed.

Remaining mandatory external input: approved sender/domain, existing protected
Resend input locator and an owner-controlled recipient. A normal username/password
account remains usable; mail verification and password reset remain unavailable
until configuration and a real delivery/verification test pass. No plaintext
secret is requested in chat. Source changes and candidate/backend delivery are
complete, not live mail or phone/MCU acceptance. Documentation changes are scoped
to the existing task/index/main board/deployment memory; unrelated files remain.

### Initial Account Batch Delivery

Status: SOURCE_CANDIDATES_AND_BACKEND_DELIVERED / PHONE_AND_DEVICE_VALIDATION_PENDING.
Latest MCU: 3.3.50, source `91916e11469fce94282a9e1a0254048f4e4a9d7f`,
successful candidate CI `44970721130`. App remains 1.0.90+116; it was not rebuilt.
Product source: main `8a6dd4a3f051ba137256795f8d889eef6ece3e2b`, delivered after
the development checks below; baseline remains `409fc640bc86272c34a2a6ce3f85dfef2c8498a9`.
Owner explicitly selected **5 automatic and 5 manual checks per account per day**,
separate pools shared by devices/phones, not journal-derived or reset by reinstall.
Server day is Asia/Shanghai; the prior one-hour automatic spacing is retained.
Client cooldown only saves requests; the server owns daily admission atomically.
Successful update/no-update responses consume one check; backend failures do not.
Request IDs deduplicate retries. Download preparation refreshes the same checked
asset without charging again and never silently changes target/package identity.

Implementation delivered: new-api-referenced login/register/reset controls,
OS-vault App sessions, Access-protected Admin account/registration/login statistics,
UID device association, anonymous local Bluetooth with authenticated cloud/OTA
admission, mobile-data firmware preparation and network-restoration continuation.
Factory UID is an identifier, **not a cryptographic ownership proof**. The App
reads it from a current BLE generation and asks the user to confirm association;
this does not introduce device provisioning/signing keys or an anti-cloning claim.
Existing BCB, OTA success identity verification and active-write ownership remain.

MCU text-layout regression failed against the old code in `tests-20`; `tests-24`
passes 77 host cases including physical-screen bounds and additive UID query
session preservation. Legacy binary INFO and CAPS remain compatible. Real-LVGL
images in `images-30` were inspected for checking/downloading/blocker/focus states.
`build-30` passes GCC App/Boot targets and simulator: 396 incremental warning lines,
zero errors; Boot was up-to-date. App bin SHA-256 is
`a056315c5c76dbb3bb894aa6177fccddb061cc3156695c616e4ca4097a066024`.
These are development outputs, not a versioned candidate or an installed image.

Backend `accounts-host-03` passed 532 cases; its Git-ownership-blocked script suite
subsequently passed 24 cases in `accounts-host-05` using per-process safe.directory.
Native Windows workerd crashed before testing in `accounts-test-01`; failure is
retained, not retried. Actual Linux workerd CI `44963616712` passes 514 tests,
Worker/Public/Admin typechecks and 293 Admin browser cases on `2acde4c6045dbcf764be198ac81cb50e1e2118ee`.
Raw logs: `.cache/ota-followup-20261122/keyring-logs-40/`.
Flutter checks-only CI `44963472466` passes both hosts on that same source,
including repaired disconnect/resume and prepared-grant persistence tests.
Native/debug CI `44963606753` passes, including device-OTA native tests and a debug
APK (not installed); logs are in `keyring-logs-51`. A follow-up batch restores
credential-free immutable GitHub fallback downloads and tests account-page
registration switches, separate quota display, small screens and readable actions.
That batch plus authenticated announcements passes both hosts in `44965098761`,
source `1a1c82fefc433868adceb8012569a3f1b3cb796e`. The intermediate `44964618134`
failure was a void-return await in the new UI test teardown; evidence is retained
in `keyring-logs-47`, not retroactively passed. Backend `accounts-host-07` additionally
passes the real bind/foreign-account denial/OTA authorization/uncharged-denial case.
APP 1.0.90+116 and MCU 3.3.49 use that delivered main source after draft/release/tag
checks (`keyring-read-45`, `keyring-read-50`). Main backend CI `44965965282` and
governance CI `44965965329` pass. Formal candidate run: `44965965276`.
Original-signer run `Eitan-S-23/Trace/44966121776` completed successfully on both
Windows and Android. Parent `44965965276` confirms App accepted/completed with
channelPublished=false; its overall result is FAILURE solely because firmware
upload failed. Android candidate registration succeeded as
`rel_trace_android_v1_0_90`, idempotent=false. APK inspection confirms original
package/signing/backend and BLE V2: 49604117 bytes, SHA-256
`a7c641e28e043770f991fa6d1168a6f0687d01a2831c6bceaae7b0d5884f980b`.
R2 APK/manifest verification succeeded. App is not published or installed.
Original logs: `keyring-logs-74` and `keyring-logs-76`; sanitized receipt:
`.cache/ota-followup-20261122/app-1.0.90-delivery-receipt.json`.
Main backend logs `keyring-logs-71` confirm 514 Worker tests and 293 Admin cases.
Latest development counts: Linux 1001 passed/16 platform skips; Windows 949
passed/68 platform skips; each host also passes eight candidate contract tests.
No deployment, phone action, J-Link or OTA occurred in this account/layout batch.
Owner reported the earlier automatic popup works; do not repeat OTA to recapture it.

Rollout must install UID-capable MCU firmware through the existing OTA route before
requiring account binding on the cloud side. Older firmware cannot invent a UID.
Owner retains all Cloudflare migrations/deployment/configuration/channel/delta
operations. The delivered source/candidate and self-tests are not independent
acceptance, live account availability or owner phone/device verification.

### Firmware 3.3.49 Delivery Failure

Historical failure, superseded by the 3.3.50 delivery below. Do not use 3.3.49 as
the rollout target or ask the owner to repeat the completed read-only reconciliation.

Formal GCC build, full/recovery native byte verification and private-key cleanup
pass, with 641 compiler warning lines and zero compile errors. The upload stage
fails with `R2_VERIFY_FAILED`, `R2 S3 request failed: HTTP 500`, request ID
`329d43b1-7e6b-4443-a51d-131076602363` at 2026-11-22 00:21:15 UTC.
No ready-metadata or successful registration receipt exists in the retained log.
R2 object persistence after the error is UNKNOWN, not proved absent or complete.
The subsequent artifact-retention step was skipped after this failure; the agent
did not rerun packaging/upload or fabricate a recoverable asset archive.

Original job: `44965965276/job/137035319862`; raw log under
`.cache/ota-followup-20261122/keyring-logs-62/` and bounded sanitized handoff at
`.cache/ota-followup-20261122/firmware-3.3.49-failure-receipt.json`.
Final raw image SHA-256: `0cdaa78e2f6391608b428060d114f339d15ef7fb9d1dcdb2bef7749dc38ca2a8`.
Full ETU: 304649 bytes, `4fc2fd9d30d03bf20c7cf95aa85d8f3c93330da8c497b70374847fd9650269e2`.
Recovery: 635868 bytes, `9d8fb8374ec4e8fdd7665c4811fced2beb8d367ffc76ff669393f5b50f6c4d6f`.
Owner next action: read-only reconcile R2 prefix
`trace/firmware/e-track-at32f435/30349-mcu-e-track-at32f435-v3.3.49/`
and any 3.3.49 candidate against these identities. Do not publish an incomplete
candidate, overwrite immutable assets, rotate credentials on the basis of a 500,
or deploy the account gate before a usable UID-firmware transition is delivered.
Recovery must be chosen from the actual preserved object state, not a blind rerun.
Object metadata (`sha256`, `kind`) and byte lengths are useful initial owner
reconciliation inputs; they alone do not replace the pipeline's full-byte check.

### Firmware Recovery Completed

Owner's subsequent authorization allowed autonomous completion of the ingestion
blocker. Existing owner credential was reused in memory; no login, new credential,
permission change, deployment, channel/delta mutation or device action occurred.
Read-only `keyring-cloud-live-79` confirms no 30349 candidate/asset rows (zero D1
writes), and both exact R2 keys return 404/code 10007. This replaces UNKNOWN with
ABSENT for that observation, not a deletion of earlier evidence.

The implementation agent then attempted GitHub failed-job continuation before
checking the first-attempt-only contract. Attempt 2 was rejected by admission,
before compilation/upload; successful App work was preserved. This was an agent
recovery-entry mistake, not a product failure. Evidence: `keyring-rerun-80`,
`keyring-logs-83`; no guard was weakened and no further rerun was requested.

Source `02241a0d4545b16e1f550a5f4837f4e5ad4eab43` fixes artifact retention after
upload failure and includes finalized/full/recovery packages plus partial receipts,
strictly after successful private-key cleanup. `retention-tests-01` passes 65
candidate regression cases, retaining intentional negative-test output.

The supported `Tools/ota/release_candidate.py mcu` entry then increments only the
MCU version, checks drafts/tags, commits/pushes and observes the exact first-attempt
run. 3.3.50 is DELIVERED: `44970721130`, source `91916e11469fce94282a9e1a0254048f4e4a9d7f`.
App job is SKIPPED. Both assets were uploaded and full-byte verified; registration
is ready/unpublished with assetsRegistered=2 and idempotent=false:
`fw_ac0c77fc2d6252f5eadec5cd995547c100b8de97e4ab3d9808179e63ee4653dc`.
Target raw SHA-256: `6e763fb66958d4a4db3b9cbf7b02351184c189165d5499faf26986421273762a`.
Full ETU: 304580 bytes, `8e8617850199e86db3375d07c6bc84b8db4ea24eb1f684c45a13501ee63faca4`.
Recovery: 635868 bytes, `e137fd75dd54f59c5f304755e01f05dc5dc02d773601d34afe1f3b48699e9a89`.
Compiler warnings/errors: 641/0. The corrected artifact-retention step succeeds.
Canonical one-command receipt:
`.cache/candidate-release/20261122T011631Z-a16389c9/result.json`.

The thin local wrapper returned 1 during its final log write because it did not
create its own output directory. The supported CLI's DELIVERED receipt, independent
GitHub job readback `keyring-status-88`, and released CLI lock establish actual
success; no successful release was repeated to repair the wrapper log. The wrapper
is a preserved one-use adapter, not the product one-command script.

### Owner-Authorized Account Backend Deployment

2026-11-22: the owner explicitly asks to deploy the new backend now. This changes
the earlier owner-only deployment boundary, not channel/delta or device authority.
Fresh primary/remote main is `3dbf49cffef43b4f4484557113c1da1bb09fa553` with no
tracked pending changes before this operation. Source remains the already-tested
`8a6dd4a3f051ba137256795f8d889eef6ece3e2b`; no product rebuild/version change.

Read-only preflight `keyring-cloud-live-94` confirms old Admin `2ad213fa` and
Worker/Public `7e088a08`, migrations through 0017, and Android Stable 1.0.89.
The user was told that deploying the login gate restricts old App cloud calls;
installation of App 1.0.90+116 and firmware 3.3.50 is still unconfirmed. Do not
infer installation from this deployment or publish either channel automatically.

Existing `deploy-cloudflare-admin.yml`, Actions **44972869444**, succeeds on its
first attempt at 2026-11-22 01:45:41 UTC. Inputs select original Admin/main and
include Worker and Public. Existing E_TRACK_CI is reused unchanged. Only pending
**0018_accounts.sql** is applied; prior migrations are not replayed. Live IDs:

- Worker version: `4a6ece7d-d99d-4012-bf74-48aea9eaf5e4`.
- Admin deployment: `e314773a-497c-41d4-85b6-8d0e8a112d19`.
- Public deployment: `e87e25c6-e7ff-4503-828f-0bb964067802`.

`keyring-cloud-live-97` independently reads back all source IDs and unchanged
Worker settings/schedules plus Pages production/preview runtime configuration.
A real existing Access owner session works; HTML and ten JS/CSS assets match
committed bytes, including account-management.js. Admin settings/account list/
login statistics work (zero accounts at observation; no fabricated user history).
Worker and Public `/api/auth/status` both return registration enabled, password
registration enabled, email verification disabled, timezone Asia/Shanghai and
separate daily limits **5 automatic / 5 manual**. Anonymous update checks return
401 / LOGIN_REQUIRED. No account or quota is created/consumed by these probes.
All four channel pointers and 59 existing delta IDs/attempts/input hashes match
the before snapshot. No Stable/Beta or delta operation, package download,
phone/MCU operation, new credential or credential configuration change occurred.

Deployment warnings remain visible: Worker dependency audit reports 13
vulnerabilities (3 moderate/10 high); Admin/Public each report 4 high. Node
punycode/url.parse and upload-artifact runtime deprecations are retained. No
unreviewed dependency upgrades were mixed into deployment. Live registration/
login CPU suitability, phone OS-vault behavior, device binding and OTA acceptance
remain unverified; this is deployment self-verification, not independent acceptance.

Originals under `.cache/ota-followup-20261122/`: `keyring-read-92`,
`keyring-dispatch-93`, `keyring-cloud-live-94/97`, `keyring-status-95/96`, and
`keyring-logs-98`. All controlled host outputs, helper files and record edits
are project-local; the existing hosted workflow confines controllable outputs
to its checkout. No PowerShell, local package install, profile write, device
collector or unrelated cleanup was invoked. Thin wrappers reuse the existing
owner/keyring/CI/readback routes, not a replacement deployer. Scope audit is
`account-backend-deployment-audit-01.json` in that same evidence directory.

### Owner Rollout Order

This was the recommended firmware/App-first sequence. The later explicit owner
request has now completed step 3 through the agent, as recorded above, without
confirming steps 1 or 2. Phone/device adoption and real validation remain open;
do not repeat deployment. The earlier plan is retained for transition context:

1. Publish firmware 3.3.50 using the existing working backend and App. Use the
   device's actual installed version as a delta base, or select full OTA. Verify
   3.3.50 and the repaired text layout. No extra J-Link installation is required.
2. Publish/install original-signed App 1.0.90+116 through the old backend. Account
   login will only become available after the matching backend rollout below.
3. Run the existing `deploy-cloudflare-admin.yml` on main with the verified backend
   `source_sha=8a6dd4a3f051ba137256795f8d889eef6ece3e2b`,
   `project_name=trace-update-admin-staging`, `branch=main`,
   `include_worker=true`, `include_public=true`. All three components changed.
   The supported entry applies only pending migrations, including 0018_accounts.sql;
   preserve env.staging, Access, signing, channels and existing credentials.
4. Confirm deployment/source receipts, open the Admin Accounts tab, verify separate
   5/5 allowances and registration settings, then register/login in the App and bind
   the connected device by its 24-hex UID. UID association is not attestation.
5. Check anonymous local BLE versus cloud denial, account-bound OTA admission,
   remaining allowances and Admin login/device records. Do not consume an OTA just
   to reproduce earlier successful device evidence; owner controls actual trials.

Email verification/reset is optional and needs owner-configured mail delivery.
No mail provider credentials were configured and no message was sent. Default
registration is open, password registration is on and email verification is off;
Admin may close registration. Login statistics represent logins, not online users.
Actual Worker CPU-plan suitability and phone OS-vault behavior remain live checks.

### Account Batch Write Audit

Initial account-implementation audit: all agent-controlled outputs remained under
`D:/github/my/E-Track`: scoped product
and test files, existing records, Git metadata, contained host/CI adapter outputs,
and `.cache/ota-followup-20261122/`. No PowerShell, external SDK installation,
credential/configuration change, manual cloud API/deployment, phone/J-Link/OTA
operation or unrelated-file cleanup was performed. Prior failed runs/evidence
remain intact. The final continuation audit is retained at
`.cache/ota-followup-20261122/account-delivery-audit-01.json`.
The subsequent authorized read-only reconciliation and MCU-only recovery use
the same project boundary. Their final audit is `account-delivery-audit-02.json`
in that directory; original failures, fixtures and receipts remain preserved.

## Owner Feedback Follow-Up, 2026-11-22

Status: IN_PROGRESS / LOCAL_PENDING. Owner: Codex root, primary main checkout,
baseline fa52d91772126641f7ee23eadf7de8106f2aa5b7. Existing untracked evidence
and worktrees are preserved. No additional agents, backend manual operations,
phone actions, reminder resets or repeat OTA for evidence.

Original input: `.cc-connect/attachments/om_x100b7f2966a3aca0cd00ed31aab24f5/companion-diagnostics.zip`.
541 events confirm MCU-originated 30344 -> 30345 and 30345 -> 30346 identity-verified
success. Each is followed by service destruction in the same process and delayed
control recovery (357.895 / 997.857 seconds). Runtime reports success with its old
link generation; native state handling can classify this as disconnected/idle,
stop the companion and apply failure backoff. Notification connection reporting
itself is correct according to the owner. Fix handoff, not merely notification.

MCU safety text currently conflates recording/power/busy reasons; focused install
label overrides the inherited readable color. The post-transfer arc is a fixed
75-degree spinner. Owner explicitly approves estimated stage-completion drawing
on this MCU screen, superseding its former indeterminate-only presentation for
this bounded change, not BLE durable percentages or final success verification.
APP state intervals (0.124/0.102 s applying-to-wait, 1.344/1.553 s wait-to-probe,
22.286/22.310 s probe-to-identity) are coarse observations, not MCU internal step
timings. MCU apply/backup is synchronous: use actual phase boundaries and label
estimated weights; never delay reset, introduce unsafe storage callbacks or imply
that pre-reboot processing is verified whole-upgrade success.

Batch: real blockers/title/focus and stage ring; post-OTA control recovery without
false stop/backoff; reconnect automatic checks, shared persisted three/day quota
and one-hour spacing; bounded compact history with details and same-gesture
scroll chaining; package identity exports and recovery-episode lifecycle timing.
Development checks: actual LVGL host harness, App full Ubuntu/Windows development
CI and native regressions, then formal source-bound APK/EXE/MCU candidates.
User authorizes direct installation of repaired production GCC firmware, retaining
Boot/config/user data and complete confirmation state; prepare a fresh binding and
readback route before any device mutation. Then invoke the existing version-only
candidate CLI twice for two forward MCU candidates, keeping channels/deltas under
owner control. Versions remain unreserved until draft/tag/source checks pass.
Self-tests, source delivery, ingestion, installation and user acceptance remain
separate. Latest feedback/research above is not a completed implementation claim.

### Follow-Up Development Checkpoint

Local commits `46d28e88` and `b239e70a` are pushed only to
`dev/flutter/ota-followup-20261122`; remote main remains `fa52d917`.
Host tests-02: 75 passing tests, including actual LVGL blocker/focus/360-degree
milestone coverage. Font coverage failed first (new missing glyphs), then six
needed characters were generated with the existing font tool. Build-01 exposed
the missing Power_GetInfo declaration; build-02 includes the correct shared HAL
header and passes GCC App/Boot plus simulator, 396 incremental warnings, 0 errors.
Retained outputs: `.cache/ota-followup-20261122/`, actual visuals `images-01/`.

First App CI `44936589249` analyzed cleanly but failed 22 tests: 15 sensor fixtures
still assumed the old check interval, two real scroll-activity failures, and five
page cases exposed ListTile's missing Material surface. Fixtures now explicitly
seed the new recent automatic-check budget without weakening telemetry assertions;
scroll chaining moves only residual distance through the parent's public jumpTo;
history owns a transparent Material surface. `44938012236` passes full Ubuntu and
Windows checks on `b239e70a`; native/debug build `44938125700` is still running.
No debug APK is installed and this is not independent acceptance.

Draft/tag preflight keyring-read-01 covers all E-Track releases and all 127 Trace
releases, including drafts. 3.3.47 and 1.0.89 are unoccupied; new local version
inputs are MCU 3.3.47 and App 1.0.89+115, not yet built/ingested on main.

Passive device/preinstall-01 confirms running 3.3.46: full 634380-byte image SHA
7fe4b594aaa257d5249cc9d222dc2c6256ea20772cf2a9f47f6b7e1b6986e927,
unchanged Boot SHA 01e4b9e162bfaaf9fda070aa13c0cec3f377b8d696db01f731e0ab3d1464e527,
advancing health, confirmed runtime, no recorder/SD/debugger activity or faults.
Backup slot is 30345 / 634380 bytes / CRC 3909915030. Candidate is 30346; staging
matches the 30346 full ETU (303729 bytes, SHA prefix 96fef3368bfacd93), corroborating
the owner's full-transfer report without replay. All regions are backed up.
No halt/reset/RAM/EEPROM/Flash write occurred and the observer/owner lock closed.
Direct installation will bind 30346 -> 30347 and the complete inactive BCB record,
preserving old active BCB, Boot, configuration and all QSPI regions. Two later
version-only candidates will be 30348 then 30349 if their live reservations pass.

Native/debug development run `44938125700` has now completed successfully on both
hosts, same `b239e70a` product source. Checks-only run counts were Linux 988 pass /
16 skip and Windows 936 pass / 68 skip, each plus 8 candidate checks; Flutter
3.47.9 / Dart 3.13.7. Exact native counts and artifact hashes are being archived
from the successful original run, not rebuilt. Original failed runs remain.
Preparing the bounded main versioned delivery; no manual channel/delta action.

### Direct Installation Admission

Formal source `3802e85f0d46c25912bb5389366651a9d1c8927e` is on main. Candidate run
`44939228682` firmware job `136952954586` passed and registered 3.3.47 ready,
unpublished, two assets; 643 warning lines / zero compiler errors. App signing is
tracked independently. Exact 635548-byte target SHA is
333cd548bb86ca6bf4565d69673e694ef9ad045249bd7187343e60bfdd01bd59;
full ETU SHA 14e9d30f3020986572c526c54e50e3992d8a3aa4eb9de23820d586a0eda02c68.
The original CI header finalization reproduces both published raw and recovery
hashes, with no backend download. Exact current/target ELF/map are bound in
`device/assets/manifest.json`; no old ABI/RAM addresses are used.

`device/repair-host-01`: 115 complete-record/wire assertions pass for 30346 ->
30347, backup 30345 / length 634380 / CRC 3909915030. One adapter assertion
failed before fixtures/device access because the old direct-install candidate
version was 30340 rather than its running 30341; its failure is preserved and
the guard is rebound to the actually observed 30346 candidate.

Finite install-01: sole Codex root owner; fresh current image/Boot/region/idle
checks; standard AT32F435RGT7/SWD 1000 App load; full byte readback; re-establish
actual post-loader storage-idle halt; exact whole inactive BCB transaction with
old active record/configuration preserved; deliberate restart and current-map
RTT signature, full image, CONFIRMED 30347, healthy runtime and unchanged QSPI.
Existing bounded 2350-second native route is reused, including known slow host
GPIO EEPROM reads. No new flasher or safety waiver to hide that cost. On any
uncertain programming outcome, reconcile read-only and resume only missing work.
User OTA, channel/delta changes and phone actions remain outside this operation.

### Interrupted Installation Continuation

Owner stopped the slow route, then explicitly requested completion of the same
installation. App programming and full readback succeeded in install-01; the
worker was stopped during post-program EEPROM reading, before its record write.
The device was left halted at the new HAL_Update rendezvous. Do not reprogram.
The observed gap is the host GPIO transport cost, not EEPROM write latency.
finish.py reuses the exact tested complete-record C draft and SEGGER native
connection, but calls this exact firmware's existing safe EEPROM HAL at the
storage-idle breakpoint. It does not introduce a Flash algorithm or replacement
BCB state machine. A fresh full image/Boot/context check and EEPROM/configuration
comparison precede the single inactive-record write; an existing hardware
breakpoint bounds each internal call to two seconds. Stack/core context is saved,
the interrupted read bus is released, and the complete resulting record plus
unchanged active record/configuration are verified before a standard reset/run.
Only then can the exact-map health and CONFIRMED 30347 startup checks complete.
The continuation has a 180-second owner deadline, project-local finish-01 outputs
and the existing SEGGER native-history exception. No further candidate or OTA.

Continuation result: `device/finish-01/result.json` is PASS, 50.907 seconds.
Fresh App/Boot bytes matched before and after; raw App SHA remains
333cd548bb86ca6bf4565d69673e694ef9ad045249bd7187343e60bfdd01bd59.
The internal 256-byte read took 43 ms, 64-byte safe write/readback took 45 ms,
and final 256-byte read took 33 ms (host-observed call intervals). Complete
inactive-record bytes matched the prior C-generated plan; old active record and
all configuration bytes were unchanged. Temporary stack/core state was restored,
then one deliberate reset/run completed. Exact-map RTT contains
`OTA: BCB already CONFIRMED vcode=30347`; main-loop observations advanced from
1166 to 7137/7138, CFSR/HFSR are zero, CPU is not halted, watchdog debug freeze is
restored to zero. No additional App/Boot/QSPI programming or OTA was performed.
This proves installation/running health, not independent UI/OTA acceptance;
actual screen/buttons remain for the owner to inspect.

Closure: native/Commander/old installer processes were absent and the owned
device reservation was removed after success. All 72 finish-01 output entries
resolve inside the project. The SEGGER/PowerShell metadata audit has no changes;
PowerShell was not invoked. Original interrupted install evidence is preserved.
The stop had left the MCU paused; reporting that fact did not restore it. The
old host bit-bang route is not appropriate for another quick direct installation.
These note/index/board updates are local pending, not another product delivery.
App signer final receipt was not re-queried during this recovery. Versions
3.3.48/3.3.49 were not generated; channel/delta operations remain with the owner.

### Owner-Requested 3.3.48 One-Command Candidate

Owner subsequently requested one new MCU package immediately. Installation
records were delivered in `c7a655a26548a67e8c9d44d0d67a3279b524f018`, allowing the
existing one-command entry to run from clean, current main. The existing keyring
wrapper invoked `Tools/ota/release_candidate.py mcu --timeout-minutes 10` without
changing that tool. It checked authenticated Release lists including drafts and
tags, changed only the MCU version/release notes, and committed/pushed exactly
`Tools/ota/original-admin-release.json`. App remains 1.0.89+115; no App rebuild.

Result is DELIVERED: **3.3.48 / 30348**, product functionality unchanged from
3.3.47, source `5d81e6b9be2e666a90723a9997fd3a482f583801`.
Formal run `44943905784` passed checks and firmware, with App skipped. Original
source-bound registration confirms ready, two verified assets,
channelPublished=false and productionApproved=false. CI has 641 warning lines
and zero error lines. Release ID:
`fw_5e32a34ce17d47aef851f912d026c8dea51bff22e55f093109e5eef5f343352a`.

Receipt: `.cache/candidate-release/20261121T195939Z-ea346b99/result.json`.
Raw image SHA: `06c26201ac2de4b21669e7eb8ac1d5ac3406c23e154461c2dd9f4d216883d48f`.
Full ETU: 304390 bytes, SHA
`f86fc4046ab6bfec4d33727360f3a26e5e1cc8ae997d5447d3e8cbfe9e738828`.
Recovery: 635556 bytes, SHA
`1cab2b7ddedfff5df3d59221916238bb3f504040daccc6bc75c9a48c8cb2614a`.
No extra package download, device operation, backend manual API, channel or delta
operation. 3.3.49 was not generated. Last verified device baseline remains 3.3.47;
the owner chooses channel publication and any 3.3.47 -> 3.3.48 delta.
The script exited successfully; this candidate is not an OTA test result.

## Scope

User-reported baseline: Android 1.0.85, MCU 3.3.35, target 3.3.36.
The device-originated update disconnects and returns to the phone-connection
prompt. The App remains in reconnect/identity verification while the MCU keeps
running. Investigate both entry points without assuming a reset or deadlock.

The Admin scope includes both App/MCU delta dialogs, announcements and an audit
of other nested scrolling containers. Preserve modal background locks and
gesture/focus ownership. No redesign, channel changes or package regeneration.

Active root: `D:/github/my/E-Track`, primary main `1d05da5a` matched to remote.
Another agent is reducing disk usage. Preserve unrelated changes and evidence.
No main commit/push, release or deployment is authorized by this task.

## Initial Evidence

The original 3.3.35 App-only J-Link installation preserved the old confirmed
BCB. Its startup RTT reported `vcode=30330`, while the full App image is 30335.
`ota_backup.c` requires the confirmed BCB version to equal the validated running
App version before backup or STAGED commit. These relevant source files are
byte-identical between original 3.3.35 source `48ad9f03` and current main.

Thus the previous statement about matching delta baseline hashes was correct
but incomplete: it did not establish the installation prerequisite. Neither
removing this safety guard nor overwriting a BCB version field is an authorized
repair. The standard supported complete-state reconciliation must be reviewed
separately before any persistent device-state change.

END2 OK precedes candidate application/backup/STAGED commit. OtaService then
disconnects intentionally and waits for the target identity. A later activation
failure can therefore produce exactly this apparent reconnect stall without an
MCU reset. A fresh passive RTT snapshot is the next discriminating observation.

## Bounded Observation

- Sole operator: this root session; shared device lock and foreign-debugger check.
- Input: original hash-bound 3.3.35 ELF/map and full App image from
  `.cache/jlink-335-20261119/assets/manifest.json`.
- One passive snapshot of full App/Boot, matching RTT buffer, initialized
  confirmation state and advancing health counters. No Flash/RAM writes,
  explicit halt, reset, OTA, EEPROM access or consumed RTT read pointer.
- Reuse the existing standard Commander, bounded process, path guards and
  SU desktop launcher. Native call limit 120 seconds, whole observation 180 seconds.
- Outputs: `.cache/ota-companion-20261120/observe-01/`; shared temporary lock
  `.cache/p34-live-device.lock`. Only the existing SU SEGGER native-history
  exception permits external automatic writes; all controllable outputs stay local.
- Preserve the current firmware/state. An uncertain outcome stops new device
  operations for reconciliation; never repeat an OTA to repair host collection.

## Findings And Original Observations

The passive observation completed at `observe-01/result.json` under the output
directory above. The full running App still hashes to
`05d0b280cf2b0df09cff1b4f1bda15a7924d6b1cf44789997a9ac12eba43a55a`;
the full Boot remains
`01e4b9e162bfaaf9fda070aa13c0cec3f377b8d696db01f731e0ab3d1464e527`.
Initialized state is CONFIRMED, health counters advance and fault registers are
clear. The matching live RAM contains the current boot's original
`OTA: BCB already CONFIRMED vcode=30330` line. No new reset, halt or write was
requested. The retained RTT text ends inside a metrics line, so this is not a
complete activation trace or a newly read EEPROM dump. No missing ACK/error
value is inferred from that truncated text.

The original 3.3.35 `ota_backup_stage` code explicitly rejects this mismatch
with `OTA_BACKUP_ERR_APP_HEADER` before erasing backup or writing BCB. Added
`t13_app_only_install_stale_bcb` reproduces 30335/30336 images against confirmed
30330, verifies zero Flash/EEPROM writes and unchanged boot records, and uses a
separate consistent fixture as a successful control. The original guard is
unchanged. This establishes a definite installation blocker independent of
which UI initiated the transfer or whether the selected ETU is full or delta.

The App intentionally disconnects after END2 OK and then waits for target
identity. MCU activation happens after that ACK. Thus transfer completion is
not evidence of activation or reboot. Do not remove the backup guard, declare
success from END2, or try another full/delta transfer against this unresolved
state. The earlier installation was physically correct but NOT OTA_READY.

## Scroll Audit

| Container | Result / Change |
| --- | --- |
| App and MCU delta base lists | Shared `.delta-base-list` now chains vertically to its sheet |
| Announcements | `.announcement-list` now chains to the page |
| Firmware operation history | Same fix for `.firmware-history-list` |
| Long confirmation details and errors | Inner text now chains to the dialog; the error header permits native vertical touch pan and retains its existing no-drag message marker |
| App/MCU main version lists, delta job list, distribution table and horizontal tabs | Existing native chaining retained; no new containment added |
| Outer sheets, confirmation dialog and floating resource panel | Retain containment; modal background locks and dismiss/focus rules are unchanged |
| Feedback and task/notification content | No separate bounded inner scroller requiring a change |

Twelve new browser cases exercise actual desktop wheel/mobile touch input at
both boundaries, assert that the correct owner scrolls, preserve the modal and
its background position, and verify zero business mutations. They never move
the owning scroller in order to satisfy an assertion. Native gesture latching
can consume the first gesture at a scripted boundary; the oracle explicitly
checks continued input with at most one further independent gesture. Original
single-gesture failures and geometry are retained rather than relabeled green.

## Development Checks

Original outputs are under `.cache/ota-companion-20261120/`.

- `backup-01`: 155975 backup assertions and 24 health assertions pass, including
  the new stale-version and consistent-state controls. This is a host test, not
  a physical EEPROM repair.
- `ui-before-01`: eight real list-boundary failures and two initial fixture
  failures. `ui-before-02` corrects the long-dialog fixtures and reproduces all
  four long-text wheel/touch failures before the CSS fix.
- `ui-after-01/02/03`: preserve the eight passing cases, four single-gesture
  failures, and diagnostic geometry. `ui-oracle-01/02` discriminates native
  continued-gesture behavior without changing the product again.
- `ui-after-04`: all 12 final boundary/ownership cases pass.
- `types-01`: Admin TypeScript check passes.
- `ui-full-01`: all 285 Admin browser tests pass, including modal gestures,
  Back/focus behavior and the 12 new native scroll cases. Elapsed time 11.3 minutes.
  The original Node `NO_COLOR`/`FORCE_COLOR` environment warning is retained;
  it is not a product error and was not suppressed.

No Flutter or MCU product source/build inputs changed. There is no reason to
rebuild 1.0.85, 3.3.35 or 3.3.36, re-sign a package or generate another delta to
deliver these Admin CSS and test changes. Local self-tests are not independent
acceptance or evidence that the Admin has been deployed.

## Prevention And Remaining Work

The OTA error is a cross-layer/implicit-assumption failure: raw image identity,
CONFIRMED state and advancing runtime were treated as sufficient while the
confirmed version invariant was omitted. A direct-install qualification must
also bind the current BCB version and validate the subsequent backup/STAGED
preconditions. Preserve the fail-closed guard and use a supported complete-state
reconciliation, not a blind field write or an App-only downgrade. The previous
installation record and shared index are explicitly corrected.

The UI error is incomplete propagation of an earlier version-list fix: inner
lists were still using the containment intended for outer modal boundaries.
The shared CSS, native-input tests and Admin README now distinguish those owners.
This repository has no `.trellis/` spec tree; knowledge is kept in its existing
operational records and component guide instead of inventing another workflow.

Physical state repair and a real 3.3.35 -> 3.3.36 OTA remain pending. No Boot,
EEPROM/BCB, QSPI or user SD data was written in this investigation. Any proposed
persistent-state recovery needs a reviewed bounded plan and explicit authority
for its affected records before execution. Main commit/push and Admin deployment
also remain unperformed and require authorization. All source/record changes
are LOCAL_PENDING, not remote delivery.

## Authorized Continuation

The user's subsequent `authorization` reply approves backing up and repairing
the persistent upgrade-control state, with a controlled restart if necessary,
and committing/pushing/deploying the Admin scrolling fix. It does not authorize
Boot replacement, SD-data changes, channel/delta mutations or other releases.
The earlier pending statements above describe the pre-authorization checkpoint.

The root session is the sole device operator. First capture the current full
App/Boot, candidate/backup/recovery slots and staging journal/payload while the
App is healthy and idle. Then preserve both EEPROM records and configuration
before a reviewed identity-bound transaction. Reuse the existing inactive-BCB
commit and firmware validation routines; never patch a version field in place.
The existing P3-4 rollback helper is specifically pinned to 30287 -> 30286 and
is not directly applicable to this confirmed-30330/running-30335 mismatch.
No previous recovery plan is replayed merely because its files exist.

The finite continuation is: one backed-up state inspection, the minimum
validated reconciliation/restoration sequence, and one prepared 3.3.35 ->
3.3.36 OTA observation if device/App prerequisites are available. A failed or
uncertain operation is reconciled before any further mutation. Retain the
successfully upgraded original target. All selected host output stays under
`.cache/ota-companion-20261120/`; the established SU SEGGER native-history
exception remains the only permitted automatic external write.

Admin delivery uses exact-source main CI and the existing Admin-only deployment
workflow. Worker/Public, schema, Access, secrets and channel/delta identities
stay unchanged. Reuse the completed host/browser checks; any new recovery code
receives its own targeted host checks before device execution.

### Current Flash Backup

`state-01/result.json` records a fresh passive full-region backup. App 3.3.35
and the complete unchanged Boot match their original hashes. Runtime, watchdog,
SD and QSPI remain healthy; no active transfer, recorder or debugger breakpoint
was present. No halt, reset, RAM/Flash write or EEPROM access occurred, and all
owned native processes closed. The watched external metadata is unchanged.

The candidate header is erased. The verified backup is 30329, length 614416,
CRC32 2010600807, raw SHA-256
`a853e482ba5f9c55265a56b9b5dcf3131ddf75c912f4e1dd714cb1b565fe8483`.
The valid recovery is 30276. Staging has a committed 313-byte package for 30336.
The four full QSPI regions are archived before any repair. An erased candidate
header means candidate application has not completed; it does not prove that
backup-version rejection was the first activation error. Keep that distinction
while investigating the remaining activation path.

### Selected Reconciliation Route

Use standard Commander only for the existing storage-idle main-loop rendezvous
and deliberate resume/restart. Reuse the qualified CoreSight GPIO/EEPROM ports
to capture both BCB copies twice and all configuration bytes, then run an
identity-bound draft of the existing Boot physical-recovery confirmation kernel.
The C kernel validates the original full 3.3.35 image before deriving one entire
inactive BCB record; the wire adapter writes its eight 8-byte pages, waits for
each write cycle and verifies readback. The old active record, configuration
bytes 128..255, App, Boot and all QSPI regions must remain unchanged.

This reuses `recovery_confirm/{confirm,confirm_io,eeprom_page,gpio_page,read_pair}`
and the unchanged Boot/BCB implementation rather than adding a flasher or
temporarily replacing the App. The old model's image/version pins do not fit
this board; bind a separate task-local host model to 30330 -> 30335 and the
actual original App/Boot and verified 30329 backup. Its pure-C ABI remains
host-only; no arbitrary target-function call or executable RAM upload is used.
The only missing reader capability is configuration bytes 128..255; a read-only
adapter extends that range and is checked against the existing EEPROM wire
model. No page write is added to the read-only snapshot interface.

Before EEPROM mutation, require the saved stable pair, fresh identical pair,
settled CONFIRMED/no-copy/no-resume state, verified backup reference and exact
full image identity. Test complete/partial writes, drift, invalid identities
and immutable configuration offline first. Two finite native cells are planned:
one read-only EEPROM backup/resume (1200 seconds), followed by the admitted
single transaction/restart (2400 seconds). A changed or uncertain state stops
the mutation path. No App/Boot/QSPI/SD programming is part of this route.

### EEPROM And Candidate Confirmation

`repair-host-02/result.json` passes 115 assertions for the source-bound adapter
and exact image pins, including partial-record writes and both native/model
EEPROM framing. The earlier 115-assertion host run is retained separately;
the second binds the added actual SDIO2 idle/DATA0 admission checks.

`eeprom-read-01/result.json` completes the authorized read-only EEPROM cell.
Both records pass CRC and the repeated pair is stable. B is active, sequence
1003, state CONFIRMED, boot_try/copy_phase/resume_block all zero, current version
30330 and backup 30329/614416/2010600807. All 256 bytes are saved before repair.
The ordinary App resumes healthy without a reset; no EEPROM payload, App,
Boot, QSPI or SD write occurred. Native AP state and debug freeze/breakpoints
are restored and the shared device lock is released.

The candidate header is not committed, but its complete 630760-byte payload
already hashes to original 3.3.36
`44325d8921509881c52e0ba96c65a0c9591181a0f78794ed8cecb7a3154ce49b`.
This strengthens the diagnosis: the supplied delta has already reconstructed
the correct target, while the independently read confirmed-version mismatch
blocks the backup/STAGED transaction. A complete BLEACT log is still not
claimed. The next cell rechecks all saved Flash/EEPROM bytes before committing
only the inactive BCB, then performs the authorized restart and readback.

### Reconciliation Completed

`eeprom-repair-01/result.json` completes that transaction. Eight verified 8-byte
pages commit the whole inactive A record: sequence 1004, CONFIRMED, current
version 30335, with boot_try/copy_phase/resume_block still zero. The previous
active B record and all configuration bytes 128..255 remain unchanged. The old
candidate reference is deliberately preserved by the confirmed-state kernel;
it is not silently promoted to a new staged candidate.

One authorized ordinary reset then produces the fresh original RTT line
`OTA: BCB already CONFIRMED vcode=30335`. Full App/Boot readback matches the
original hashes above, all four QSPI regions are unchanged, and runtime,
watchdog and SD health pass. No App, Boot, QSPI or SD programming occurred.
Owned hardware processes closed and the shared device lock was released.
The exact adapter SHA-256 is
`c6911ce040b423c99cfe2f1530ba582e7184f4a327a567777ae8002d096fc8e8`;
do not edit this completed source or replay its read/repair cells.

This removes the demonstrated backup/version prerequisite failure. It is not
yet evidence that a subsequent wireless OTA succeeds. `phone-01/result.json`
finds no ready USB phone; its private ADB server closes, the original key is
unchanged, and no phone launch, install, reset or data mutation occurs. The
remaining physical check is one prepared device-originated 3.3.35 -> 3.3.36
OTA using original App 1.0.85, followed by target/Boot confirmation and original
App-log retrieval. Do not repeat a successful upgrade to recover host logs.

### Initial Admin Delivery And Desktop Follow-Up

Main `9ed63498fd3ba83f2dd454c8c3ccf3ea0791805e` delivers the initial CSS,
regression and investigation record. Exact-source backend Actions `44599364344`
passes 501 Worker tests, 285 browser tests and the contracts/typechecks;
candidate Actions `44599364349` passes with App/MCU builds skipped. Admin-only
deployment `44602404051` succeeds with deployment ID
`25aa04d3-155d-4858-979b-28f6e23b2fb2`. Configuration, Worker/Public, schema,
secrets and channel/delta state are preserved.

Actual live desktop checks nevertheless expose a narrower Chromium wheel gap:
with a pre-scrolled background and sparse delta jobs, exhausted inner-list
wheel input can remain latched instead of reaching the sheet. Computed
overscroll is already auto, events are trusted/not prevented, and both owners
scroll normally when targeted directly. Diagnostic removal of outer containment
does not fix it. Preserve `keyring-cloud-live-01..04` as failed probes, not
successful delivery evidence. `keyring-cloud-live-05` passes real touch at both
edges for App/MCU deltas, announcements and history; all ten served assets match
9ed63498 and no business state is changed. Touch-only success does not waive
desktop verification.

The follow-up in `sheet-gestures.js` forwards only exhausted vertical wheel
input from the named inner lists/text to an eligible ancestor. In-range native
scrolling, touch/drag, nested scroll ownership, zoom/horizontal input, modal
containment and hidden background locks remain intact. Pixel, line and page
units are handled explicitly. Sparse-job/pre-scrolled fixtures reproduce both
desktop failures before the fix while their two touch controls pass
(`ui-sparse-before-01`). After the fix, `ui-scroll-after-01` passes all 18 scroll
cases and `types-02` passes. The existing Node color-environment warnings remain
visible. Full exact-source CI and a second Admin deployment/live wheel-and-touch
readback remain pending for this follow-up; no App or firmware rebuild is needed.

### Continuation Audit Checkpoint

Controllable outputs remain under `.cache/ota-companion-20261120/`. Completed
native sessions include authorized automatic updates under
`C:/Users/SU/AppData/Roaming/SEGGER/`. The watched
`C:/Users/SU/AppData/Local/Microsoft/Windows/PowerShell/StartupProfileData-NonInteractive`
also changed in both hash and modification time; no selected command invoked
PowerShell, and its writer is not attributed. Do not declare it unchanged,
blame another agent or clean it. The other watched PowerShell startup cache
remained unchanged during those snapshots. A final continuation path/process
audit is still required; the earlier `final-audit.json` belongs to its original
checkpoint and must not be overwritten.

## Follow-Up Delivery Completed

Main `2ad213fae81f395c0e70efed472d8386e1741564` delivers the exhausted-wheel
fix and completed state-repair record. Backend Actions `44613804222` passes
all 291 browser tests, 501 Worker tests, 60 Public/Access/deployment contracts
and the three typechecks. Original logs are in `keyring-logs-03/`. Candidate
`44613804107` and ordinary build `44613804194` both skip App/MCU packaging;
no shipping artifact was rebuilt. Existing test-fixture image/text warnings
and Actions/Node deprecation warnings are retained, not hidden as zero warnings.

Admin-only Actions `44615534351` succeeds and verifies deployment
`77ec808f-c927-4d17-af10-401f84c04990` on that exact source, with production and
preview runtime configuration unchanged. Its originals are in `keyring-logs-04/`.
Worker/Public, schema, credentials, channel pointers and delta enablement are
not changed or redeployed.

`keyring-cloud-live-06/result.json` completes the full real-owner readback.
HTML and all nine JS/CSS assets match Git object bytes. All 16 real native-input
observations execute and pass: App delta, MCU delta, announcements and history,
each with wheel/touch at both boundaries. No check is waived for missing rows
or geometry. Modal backgrounds remain locked; page errors, unexpected writes
and synthetic business records are all zero. Channel and delta identities match
before/after. Long confirmation/error dialogs are covered by the exact-source
browser suite without manufacturing errors or mutations in the live Admin.
Earlier failed desktop and touch-only probes remain immutable history.

## Current USB Prerequisite

`notify-usb-01/result.json` confirms one delivered real current-user Feishu
mention requesting cable/unlock only, explicitly not an OTA start. `phone-02`,
`phone-03` and `phone-04` preserve the later private-5048 read-only attempts:
zero ready devices, all owned processes/ports closed and the original key
unchanged. The user's subsequent confirmation that USB is connected is valid;
an empty private ADB inventory is not proof of a missing cable.

Read-only Windows PnP inspection identifies the exact `10ADA4197U001CK` phone,
its iQOO Z8x MTP interface and WINUSB ADB interface, all with device error code
zero. WMIC identifies the existing PID 19052 as
`D:/install/leidian/LDPlayer4/adb.exe`, serving port 5037. One explicit read-only
`host:devices-l` inventory request to that already-running socket returns OKAY
and lists the expected serial as `device`; it performs no phone command and
cannot start, stop or version-replace the foreign server. These observations
support an existing ADB/USB-owner conflict, not an App or firmware failure.
No foreign process was stopped and no automatic UI input was injected.

The next step requires the user to close that ADB service, or explicitly approve
stopping only this identified service and its current debug connections. Do not
kill unrelated processes, silently use the global server for device operations,
clear App data, install a replacement APK or start OTA before collection works.
After private USB enumeration succeeds, verify V2312A, installed 1.0.85/111 and
APK SHA-256 `72460beec718e9991d3df82ce3fe8770c4c8fa38108c422c292dfdf583f3bb87`.

Original release 1.0.85 does not enable `TRACE_DEV_DEVICE_OBSERVATION`, so its
development-only `p34-observations` finished snapshots must not be assumed to
exist. Use its real PID-bound logcat and native connection diagnostics, paired
with one RTT reader and full target/Boot/confirmation readback. Do not rebuild
the release or fabricate a snapshot/footer to satisfy the development collector.
Both original 3.3.35 and 3.3.36 maps locate `_SEGGER_RTT` at `0x200537a8`; a fresh
signature and current full-image identity still gate actual capture. The USB
link is for observation, while the user initiates the real update on the MCU
and firmware transfer still uses BLE. Real post-repair OTA remains NOT_RUN.

## Continuation Write Audit

`continuation-audit-01/result.json` verifies all 62 recorded owned command
closures, absent device lock and closed private ADB port. It accounts for 1,010
task-cache files (217,911,709 bytes) without moving/deleting historical files.
The only remaining related process is the separately identified foreign ADB;
it is not an owned collector. Controllable outputs, subprocess homes/caches,
notification receipts and Git metadata remain under the project root. The
notification CLI inherited log path is disabled. No credentials are copied.

The completed native adapter still matches its recorded hash. Authorized SEGGER
history updates remain recorded separately. The Windows PowerShell startup
cache named above has changed again since the native audit, with no process
attribution; no selected PowerShell invocation or external cleanup occurred.
Do not infer that a concurrent agent caused it or relabel it as unchanged.
The final post-delivery audit uses a fresh successor directory, not a rewrite
of the original investigation or native receipts. This is implementation
verification, not independent acceptance or whole APP-COMPANION card completion.

## Authorized USB Handoff And OTA Window

The user explicitly permits stopping only the identified LDPlayer ADB service.
`adb-release-01` stops before any action because WMIC's piped UTF-16 output was
decoded incorrectly; `adb-release-02` is blocked by that preserved no-stop lock.
The third cell reconciles the dead, zero-operation owner and uses the exact
old executable's standard `kill-server` once. PID 19052 and port 5037 close.
No emulator or phone is restarted. `phone-05` now sees V2312A and verifies the
original 1.0.85/111 APK hash above, PID 15804; the old empty private inventory
was an ADB ownership issue. Original keys and App data are unchanged.

The prepared functional observation reuses `live_mcu.MCU` binding/inspection,
standard Commander/RTTLogger, the existing private ADB/Windows Job primitives
and qualified SU launcher. This ARM-OB reports S/N -1, so the thin argument
adapter retains the proven default USB selection; exact full App/Boot reads
and the absence of another debugger gate it. No new flashing/storage protocol,
firmware build, AT tuning, debugger write or explicit reset is introduced.

One window captures original PID-bound logcat and one RTT reader, first checks
the running 30335/Boot/health and both original ELF/maps, then waits for the
user's device-originated update. Preparation is bounded to 900 seconds; arming
the actual test starts a separate 600-second transfer/reboot/verification budget.
No automatic phone UI input occurs. The preserved 313-byte staging package may
resume; this is a functional activation check, not a fresh-throughput comparison.
After fresh target Boot confirmation, allow App reconnect, close the reader and
perform full original-30336/unchanged-Boot plus health readback. Retain the target.
An unknown result stops mutations for reconciliation, never another OTA to
recreate lost logs. Outputs stay in `ota-inputs-01/` and `ota-session-01..03/` under
the existing task cache; sensitive raw phone logs use a private ACL. The normal
release has no development snapshot, so no footer is fabricated or bypassed.

## First Post-Repair Attempt

`ota-session-01` stopped before device inspection because the authorized LDPlayer
ADB had restarted. `ota-session-02` could not qualify that SYSTEM-owned process
from SU and did not stop it. The third adapter keeps identity/stop admission in
the SYSTEM parent and native capture in the existing SU desktop. It qualifies
and stops only the same authorized service, now PID 25296, then retains private
port 5048. The failed preparations are not OTA attempts.

The successful collector starts at 22:10:35 UTC, acknowledges the arm at
22:21:21 UTC, and delivers the one start reminder at 22:21:39 UTC. Original
App 1.0.85/111, PID 15804, then performs GET_INFO/CAPS2 and one BEGIN2. At
06:21:56.176 Shanghai time it receives ACK_BEGIN2 status 14 (`ERR_BUSY`), epoch
4202504752, with durable/accepted/credit all zero. The original log contains
no DATA2 or END2 write. App abort/terminal records complete without a transfer.
This is a real failed start, not NOT_RUN: the collector's `otaObserved=false`
only means its narrower BLEACT activation marker was not observed.

The collector closes at 22:25:28 UTC. Full original 30335 App and unchanged
Boot, confirmed state, SD/runtime and idle receiver/overlay checks pass. Staging
headers/journal remain unchanged; no target confirmation occurs. Original App
PID and key are preserved, all owned tools close and private ADB stops. The
terminal handle is subsequently unavailable; verify both recorded owner PIDs
are gone and preserve its completed receipts before reconciling any leftover
owner lock. No phone restart, APK installation, automatic UI input or MCU reset
was requested. The user is told USB can be disconnected; no further phone
operation is needed for this diagnosis.

`ERR_BUSY` has several BEGIN admission sites; it does not uniquely establish a
battery failure or an old session. Current 30335 source no longer checks GPS
speed, but still requires recording to be closed and either charging or at
least 30 percent battery, as well as available overlay memory. The relevant
files are byte-identical to original 48ad9f03. One additional passive snapshot,
`busy-read-01`, reuses the original observer and exact ELF/map to read those
runtime predicates. Its Power ADC offset is verified from the original ELF;
PH2 charging input follows the board configuration and vendor GPIO layout.
It neither requires USB phone access nor changes device state. It can identify
the current blocker but cannot reconstruct a transient predicate at the exact
earlier BEGIN instant. No retry, rebuild or safety-guard removal is planned.

## Current Admission And Remaining Boundary

`busy-read-01/result.json` completes the passive check: ADC 2043 maps to the
firmware's clamped 3300 mV and 0 percent, PH2 does not indicate charging,
recording is closed, receiver state is IDLE and overlay owner is FREE. The
current safety predicate is therefore false. This is a definite current
admission blocker, not proof of the exact earlier BEGIN branch. Both App and
device-originated BLE entry points use the same receiver guard; simulated GPS
speed is absent from 30335's predicate. Do not bypass the guard based on USB or
J-Link supply alone. A further OTA requires the MCU to recognize charging or
report at least 30 percent, with recording stopped, and a newly prepared window.

The later snapshot also contains `Reset: NRST WDT`, and its initialized health
tick is 148997 versus 1981441 at the prior observation's end. A later boot has
occurred; its timing and cause are unknown. Neither collector issued a reset,
halt, Flash write or RAM write. This is not the target-activation reset: full
App remains the original 30335, full Boot is unchanged and BCB confirmation
remains 30335. The new boot explicitly prevents treating the later RAM snapshot
as the earlier BEGIN's instantaneous state. No new reset or retry is performed
to reconstruct the missing interval.

Original App logs preserve the complete ACK error and terminal records. Android
truncates the long `OTA_LINK_STATS` JSON; it is not a complete statistics export
or a usable throughput sample. The attempted read-only UI observer first missed
Android's `topResumedActivity=` spelling; its successor could not establish a
focused window from that device's `dumpsys window windows` output. No screenshot
was taken and those false/inconclusive foreground receipts do not override the
real foreground/GATT records. No UI input, relaunch or replacement App was used
to repair observation, and USB was released after the original log retrieval.

The Admin scrolling work remains deployed and verified on 2ad213fa. The
functional 30335 -> 30336 upgrade is still unsuccessful, not whole-card PASS.
Retain original 30335 and its repaired control state. Current work is limited
to original-evidence analysis and scoped main documentation delivery; no more
phone use, firmware/App rebuild, backend deployment or channel/delta change.

## Observation Closure Audit

`observation-audit-01/result.json` independently recomputes the failed start
from the original complete ACK record, checks 160 recorded owned command
closures, and verifies the absent device lock and closed private ADB port.
The old parent and SU child PIDs both exited; `busy-read-01/reconciled-owner.json`
preserves their completed outcome before the leftover lock was removed. The
remaining ADB PID belongs to a separate server, not the closed private collector;
no further stop or phone command is performed.

All selected outputs remain in the active root: task-cache originals, the three
shared documentation files and authorized Git metadata. The prior audit files
and completed repair/collection sources remain immutable. No credentials were
copied. The PowerShell startup cache again changed without an attributed writer;
no selected command launched PowerShell and no external file was cleaned. The
passive follow-up's watched SEGGER files were unchanged; its native-history
exception remains the only authorized external output boundary. A fresh
post-delivery audit is required instead of overwriting this checkpoint.

## Autonomous Remediation Authorization

The user's latest instruction authorizes continuing necessary scoped work,
including its required authorization, without stopping for routine approval.
The preceding analysis-only boundary is superseded for this remediation batch.
Root remains the sole operator; no subagents, channel promotion, firmware safety
bypass, Boot replacement, App-data clearing or unrelated cleanup is included.

Use the exclusive sparse worktree `.worktrees/ota-companion-fix-20261120`, branch
`dev/flutter/ota-companion-fix-20261120`, from current main `2db67b95`.
Controllable outputs stay in `.cache/ota-companion-fix-20261120` and this worktree;
the prior originals and completed helpers stay immutable. There is no Trellis
tree. Existing main records remain authoritative until this batch is integrated.

The finite batch preserves matched ACK command/status through transport and
service, explains BEGIN/DATA/END rejection without claiming ERR_BUSY uniquely
identifies battery, and projects safe owner-produced failure text through the
existing notification label. Reboot probes retain valid non-target responses
for deadline feedback without shortening the window or weakening target
version/full raw SHA checks. Cancelled, stale-link and abandoned callbacks may
not replace current owner state. ABORT ordering, durable/credit, retry limits
and statistics outcome names remain unchanged.

Add transport/service/snapshot regression cases, then run full Ubuntu/Windows
Flutter development CI and required exact-source APK/EXE verification. Shipping
uses a new App version and the existing original-signed candidate route; do not
rebuild immutable 1.0.85 or MCU 3.3.35/3.3.36, publish channels or regenerate a
delta merely to test feedback. Necessary main integration/push is in this scope.

Separately prepare one MCU-only passive watch (at most 240 seconds) using the
standard Commander, original 30335 ELF/map and existing contained host/observer
primitives. Verify idle state, sample health/power and clock registers, preserve
RTT memory without consuming its reader pointer, and inspect whether a fresh
boot occurs. No reset, halt, RAM/Flash write, OTA or phone is required. A missing
device or no reset in this bounded interval does not establish the historical
watchdog cause. Any further hardware change must follow discriminating evidence;
real OTA remains gated on firmware-reported safe power and a prepared phone.

### Initial Development Feedback

Development source `9e4811f15928f189fad2c62229b8ab38feecaced`, run
`44637193444`, fails both hosts because the new service test references an
incorrect harness name. Use the existing `_BackgroundOwnerHarness`; no product
analysis error is reported. The service integration file did not compile, so
its new cases are NOT_RUN, not passing. Other test counts are Linux 799 passed /
16 skipped / 1 failed and Windows 755 passed / 60 skipped / 1 failed. Original
console logs are preserved in `keyring-logs-01` under the new task cache.

The follow-up also makes notification-safe failure text an explicit terminal
field. Generic backend/transport error details are not automatically forwarded
to the notification; this avoids leaking an exception's signed URL or token.
This is an internal projection change, not a native notification schema change.

Second development run `44638689257`, source `80fd49e02c8c1832249aed95e5ebbb73f8024f22`,
passes analysis on both hosts. Linux reports 971 passed / 16 skipped / 2 failed;
Windows reports 919 passed / 68 skipped / 2 failed. Both failures are old-identity
and wrong-full-SHA regression expectations still naming REBOOT_RECONNECT_FAILED.
Update those two assertions to TARGET_FIRMWARE_NOT_CONFIRMED, retaining their
false-success/current-identity guards. Reuse the stronger existing full-SHA
case rather than retaining a duplicate new fixture. The new rejection, cleanup,
notification and stale/late-response cases pass in this failed batch. Original
full logs/reports are retained in `keyring-artifacts-01/02`; no failed run is
relabelled successful and no tests are disabled.

### Passive Watch Result

`passive-watch-01/result.json` completes one standard-Commander observation.
Thirteen samples cover 121508 firmware milliseconds with advancing main-loop
and watchdog-feed counters, clear fault registers, SD ready and idle receiver/
overlay. No counter discontinuity is observed. Reported core clock is 288 MHz,
SysTick reload is 287999 and DWT deltas agree with approximately 288000 cycles
per millisecond. There is no evidence here of a clock-rate defect or a new reset;
this short interval does not establish the cause of the earlier WDT boot.

Every sample reports ADC 2040..2042, clamped 3300 mV / zero percent, no charging
and recording closed. The power admission predicate remains false. Full original
30335 App and unchanged Boot match before/after, confirmation remains 30335,
all owned debugger commands close and the shared lock is absent. No phone,
reset, halt or RAM/Flash write occurs. Watched SEGGER and PowerShell metadata
remain unchanged during this watch. Do not repeat it merely to obtain a reset.

### Recorded Feedback Contract

#### Scope And Trigger

This is the implementation record for rejected BLE commands and post-transfer
identity feedback, not a change to frozen OTA acceptance or the wire protocol.
The defect combines lost cross-layer error metadata with the false assumption
that failing to verify a target always means the device never responded.

#### Signatures

- `OtaTransportException(message, {code, status, ackCommand})` preserves the
  matched response command at the receive boundary.
- `OtaTerminalState.mcuRejection({required status, ackCommand})` maps safe text
  and the existing status-specific retryability.
- `OtaTerminalState.taskFailureReason` and `OtaTaskSnapshot.failureReason` are
  optional owner-produced text; `toMap()['label']` remains the native interface.
- `_probeTargetIdentity(..., onNonTargetIdentity)` reports only validated,
  current-link, same-hardware non-target identities within the active wait.

#### Contracts

Do not infer an ACK command from the phase after ABORT. Publish failed terminal
state only after bounded cleanup and owner-generation rechecks. Error snapshots
do not grant credit or durable progress. Keep valid non-target observations local
to the wait: they do not refresh the service's current identity. Target success
still requires both version and the complete raw SHA. Retain the full window and
stable probe statistics outcome names. Raw backend/transport strings are not
notification-safe by default.

#### Validation And Error Matrix

| Input | Feedback / invariant |
| --- | --- |
| BEGIN2 ERR_BUSY | Named command/status, recording/power/idle guidance; zero DATA/END, no automatic retry |
| DATA2/END2 rejection | Original command/status survives ABORT; no reboot-success claim |
| Valid non-target responses until deadline | TARGET_FIRMWARE_NOT_CONFIRMED; last observed version, not a claim of current connectivity |
| No usable identity response | REBOOT_RECONNECT_FAILED; retain uncertainty and later recheck |
| Wrong hardware | Existing DEVICE_IDENTITY_CHANGED, not a non-target observation |
| Cancelled, abandoned or stale-link callback | Cannot alter the current owner's feedback, identity or success |

#### Good, Base And Bad Cases

Good: an old response followed by the correct target within the window succeeds.
Base: no reply times out without inventing an identity. Bad: the target version
with a different full raw SHA remains unconfirmed, never completed.

#### Tests Required

`ota_pipeline_transport_test.dart` checks matched BEGIN/DATA/END/ABORT metadata.
`ota_service_upgrade_test.dart` exercises the real owner flow, ABORT/cancel
ordering, notification projection and all identity cases above.
`ota_background_test.dart` checks failed-only projection with no invented percent.
Full Linux/Windows Actions checks and original-signed APK/EXE builds remain
distinct from a phone installation or successful physical OTA.

#### Wrong Versus Correct

Wrong: remove the battery guard, call END ACK success, or label every timeout a
disconnected device. Correct: preserve the original rejection, finish cleanup,
retain only valid observations and report exactly what was or was not verified.

## App Remediation Delivery

Source `cc43904369908a1f5c744485d7b84dc8ad9fc134` is integrated and pushed to
primary/remote main, with only the nine reviewed App/test/version/task-record
files. The shipping App version is `1.0.86+112`; the installed phone was not
replaced. Existing MCU 3.3.35/3.3.36 inputs, original signing keys, backend
deployment and Stable/Beta pointers are unchanged by this batch.

Full development Actions [44640100650](https://github.com/Eitan-S-23/E-Track/actions/runs/44640100650)
passes both hosts on this exact source. Flutter is 3.47.9
(`c197ca5199e9ee5661e865596c9c07294dfab51c`), Dart 3.13.7. Linux has 972 passed /
16 platform skips; Windows has 920 passed / 68 platform skips; both have zero
failures, successful strict analysis and eight additional candidate checks.
Original reports/logs are archived under `keyring-artifacts-03/04` and
`keyring-logs-03` in `.cache/ota-companion-fix-20261120`.

Original candidate parent [44641314474](https://github.com/Eitan-S-23/E-Track/actions/runs/44641314474)
selects App only and skips firmware. Its original-signing child
[44641546808](https://github.com/Eitan-S-23/Trace/actions/runs/44641546808) binds
the exact E-Track source to signing workflow `12ff41fc11eb4920ab32d69ae0f7e1cc095f996e`.
Windows analysis/tests, EXE/ZIP construction and immutable draft reservation
pass. Android analysis/tests, original-signed APK construction, native signature/
package/ABI/configuration verification and candidate registration also pass.
Both the original-signing child and its parent finish successfully. The ordinary main `build.yml`
`44641314587` correctly skips duplicate APK/EXE jobs; that skip is not build
evidence. No successful build was replayed to recover another stage.

The APK is 48898789 bytes, SHA-256
`556ec00495521745136b9f4709a25bb62bb122930c47469cb710e4161129852f`, package
`com.wen.gaia.gaia`, version `1.0.86+112`, with only the two original ARM ABIs.
Its original certificate SHA-256 is
`3cecee6330a930e020b454b6d4a79568f4494ca324ae7bcf2c1914e51b04ab47`.
The native inspection matches the immutable GitHub APK asset; the existing
Windows asset IDs, sizes and digests remain unchanged after Android completes.
R2 full-byte verification passes for APK and manifest, and the actual backend
response registers `rel_trace_android_v1_0_86` with `ok=true, idempotent=false`.
GitHub release 452090111 is an available prerelease, not GitHub latest or a
Stable/Beta publication. No App or MCU delta was generated.

The GitHub metadata asset records the pre-R2 document; the final native CI
`CANDIDATE_FILE` records its subsequent R2-verified registration form. Their file
hashes legitimately differ; do not overwrite the immutable asset to equate them.
Originals are in `keyring-logs-04/05`, `keyring-read-03/04` and final status
receipts `keyring-status-18/19` under the same task cache.

The earlier failed development runs remain immutable. Known Actions Node 20
deprecation, existing `detail-back` widget hit-test warning, and Android
Gradle/AGP/Kotlin and plugin-SDK compatibility warnings are retained, not
suppressed or counted as new product failures. No toolchain/dependency change
was included to hide those warnings. Development/build success
does not constitute independent whole-card acceptance, an installed phone App
or a successful physical 3.3.35 -> 3.3.36 upgrade.

All phone collectors remain released. The retained original MCU's last passive
observation is healthy and confirmed at 30335, but reports zero percent and no
charging throughout. Physical OTA therefore still requires the device to
recognize charging or at least 30 percent with recording closed, plus a prepared
phone/BLE session. Simulated GPS speed is not this 3.3.35 admission condition.
No further reset, firmware programming, BLE retry, package regeneration or
charging-state spoof is performed to hide that prerequisite.

## Charger Readiness Restored

The owner now confirms that the MCU is connected to a charger. A new passive
observation starting at `2026-11-20T09:08:08Z`, using the original qualified
Commander observer and the exact 30335 ELF/map, captures four samples over 7864
firmware milliseconds. The base App and Boot are byte-identical before/after;
the running confirmation remains 30335, runtime/watchdog counters advance, SD is
ready, the receiver and overlay are idle, and fault registers remain clear.
There is no halt, reset, RAM/Flash write, RTT read-pointer change or phone action.

The actual charger signal is now asserted: PH2 is an input with pull-up and reads
low. PA0 remains analog; ADC1 is enabled in 12-bit, one-channel/channel-0 mode.
ADC values 2570-2574 map to 4142-4148 mV before clamping, with reported usage 100
percent and charging true. Recording is closed. All four evaluations of the
unchanged shared OTA safety predicate are true. Thus the previous power blocker
has cleared without any firmware or protection change. This does not prove the
exact cause of the older BEGIN rejection or the historical WDT reset.

Originals are under `.cache/ota-companion-fix-20261120/charger-check-01`:
`result.json`, `snapshot.jlink`, raw binary samples, native logs, command closure
receipts and `audit.json`. The observer closes normally. Its external audit sees
an unattributed change to
`C:/Users/SU/AppData/Local/Microsoft/Windows/PowerShell/StartupProfileData-NonInteractive`;
this entry does not infer the writing process. No PowerShell was invoked by the
observer and no external cleanup was performed; SEGGER metadata is unchanged.

The original-signed 1.0.86 APK is downloaded once through the standard `gh release
download` route, with the existing owner keyring, into
`.cache/ota-companion-fix-20261120/apk-download-01/apk/ble-monitor-android.apk`.
All 48898789 bytes hash to the already verified
`556ec00495521745136b9f4709a25bb62bb122930c47469cb710e4161129852f`.
No rebuild, re-signing, release/channel change, credential copy or phone operation
is involved. The exact App, original 30335/30336 images, Boot, reference package,
ADB/key and standard native tools are bound in `ota-ready-01/plan.json` and
`phone-plan.json` under the same cache; both ELF symbol tables still match.

Prepared entries are `phone_setup.py` and `observe_ota.py` in that cache.
Their check-only paths pass. Installation reuses the private ADB owner, permits
only the known 1.0.85 APK to be replaced by these exact 1.0.86 bytes, preserves
app data, verifies installed bytes/version, and does not use production
`run-as`, automatic UI taps or an OTA command. The collector reuses original
logcat/RTT and full final readback, with the new App identity; it does not replay
historical PID-specific ADB stops, BCB repair or firmware installation.

The next finite cell remains device-originated 30335 -> 30336 after phone
installation, fresh MCU/connection checks and acknowledged collector readiness.
The owner keeps the charger/J-Link connected, then supplies the phone USB
connection and any required unlock/install dialog. The user starts the update
only after the collectors and actual App query are ready. Phone USB was not
enumerated during this preparation, so neither installation nor a collector
window was started. The original 30335 is retained; successful 30336 upgrade,
disconnect resolution on hardware and whole-card acceptance are still unverified.

## User OTA Completed And Target Verified

The owner reports manually completing the App update to 1.0.86, opening its
device-firmware page and successfully starting the 30335 -> 30336 update there.
This is the **phone-App-originated** entry, not a new observation of the MCU's
own "update now" button. The App version and user-visible completion are owner
observations; the installed APK was not re-read after that manual update.

Before this success, the bounded USB setup preserved two host failures and an
actual cancelled installation. `adb-release-01` failed on the localized netstat
header before any stop. `adb-release-02` released only the identity-bound
LDPlayer ADB PID 5668. `phone-setup-01` then found no target device and issued no
installation. A restarted, identity-bound LDPlayer ADB PID 21968 was released
in `adb-release-03`, immediately followed by `phone-setup-02`. That one actual
installation returned `INSTALL_FAILED_ABORTED: User rejected permissions`.
Its private ADB owner closed cleanly, no App data was cleared, and no MCU OTA
was started. The owner's subsequent cancellation was respected: there was no
installation retry, logcat/RTT capture window or automatic upgrade command.
These originals remain in `.cache/ota-companion-fix-20261120`.

After the owner's successful upgrade, `target-verify-01` in that same cache
starts at `2026-11-20T10:37:29Z`. It reuses the qualified passive observer with
the exact original **30336** ELF/map and binary, not the old 30335 expectation.
All 630760 App bytes, before and after sampling, match the original backend
target SHA-256
`44325d8921509881c52e0ba96c65a0c9591181a0f78794ed8cecb7a3154ce49b`.
The full 65536-byte Boot remains unchanged, SHA-256
`01e4b9e162bfaaf9fda070aa13c0cec3f377b8d696db01f731e0ab3d1464e527`.

The current retained RTT ring contains `Reset: NRST SW` and
`OTA: TEST_BOOT confirmed vcode=30336`. The initialized App confirmation snapshot
is state 4 with confirmation flag 1; this is the current boot's snapshot, not a
fresh EEPROM dump. Three samples span 2295 firmware milliseconds with increasing
main-loop/watchdog counts, no counter discontinuity, SD ready, receiver/overlay
idle, clear fault registers, 288 MHz core and SysTick LOAD 287999. Reported power
is charging/100 percent. The observer performs no halt, reset, RAM/Flash write,
RTT pointer update or phone operation. Native command closure is acknowledged;
the selected SEGGER/PowerShell metadata is unchanged during this observation.

The bounded result is **user-assisted App-originated OTA success with
passive target/Boot/confirmation verification**. It is not a fresh formal
independent acceptance campaign. No simultaneous phone log was collected, so
transfer timings, reconnect internals and actual delta-versus-full selection
remain unknown. A final target readback does not reconstruct those missing logs,
isolate the App fix from restored charging readiness, or explain the older WDT
event. The device-originated entry has not been independently rerun after the fix.

Retain 30336. Do not downgrade, repeat this successful OTA or create a new firmware
version solely to recover logs or test the other entry. The owner can disconnect
phone USB and use the device normally. A future genuine forward firmware update
can exercise the device-originated entry if needed. Admin scroll and App software
delivery remain complete; their originals, older failures and separate whole-card
acceptance obligations are unchanged.

## Device-Initiated Forward Verification Authorized

The owner's next request explicitly asks for a new MCU firmware release and
verification through the MCU's own update entry. This supersedes the preceding
recommendation to defer that check. It does not reinterpret the successful
phone-page 30335 -> 30336 OTA as a device-originated observation or replay it
to recover missing logs.

Fresh primary and remote main are `e0db1a1e946ae620dc82ab91f208a62925692345`.
Live original Admin inspection confirms Stable 30336, channel revision 10,
the exact previously read-back base hash, 48 existing delta jobs and no 30337
release. The GitHub release listing, including drafts, has no 30337 reservation.
Original discovery: `.cache/ota-device-init-20261120/keyring-inspect-01/`.
The writable root is `D:/github/my/E-Track`; no new project-external write
authority is inferred. The existing SEGGER native-history exception remains.

Prepare 3.3.37 as a version-only forward target from current main. No additional
MCU behavior defect has yet been established; release notes must not claim one.
Keep App 1.0.86+112, the original keys, GCC/V2 profile, Boot, layout, BLE identity,
recording/power admission and all integrity/confirmation gates unchanged. Use
the normal main-push candidate builder, then verify and publish only this MCU
release on the existing Stable channel. Preserve both App channels, MCU Beta,
all previous delta jobs and configuration. If an exact 30336 delta is generated,
use the original backend base bytes and verify reconstruction before enabling it.

The finite device matrix is one initial 30336 -> 30337 **device-originated**
screening cell. The MCU checks for the offer and its physical Update Now control
supplies consent; the phone remains the connected companion, not the initiator.
Retain 30336 until that actual OTA. Directly flashing 30337 would invalidate the
required observation, so J-Link is for passive observation/final identity here.
Prepare the immutable target, current/target ELF and map, original phone-log
retrieval, bounded MCU observation and owned-process cleanup before asking for
any short phone window. USB, if needed, collects diagnostics rather than
reinstalling the already confirmed App. No automatic UI taps or data clearing.

Allow ordinary apply/reboot and reconnect; require exact target image bytes,
unchanged Boot, confirmed version and advancing healthy runtime. Preserve any
failure and reconcile device state before an evidence-driven further cell; do
not blindly retry, bypass admission, downgrade, replace Boot or write BCB.
Successful publication, device initiation, final installation and formal
whole-card acceptance remain distinct. The final retained device should be the
verified forward target, with no restoration to an older App-only image.

## Device-Initiated Full Success And Next Delta Candidate

The owner reports publishing the 3.3.37 full package and successfully upgrading
from the MCU's own update entry. This supplies the previously missing
**device-originated full-package** user observation, distinct from the earlier
phone-page 30335 -> 30336 success. No synchronized collector or fresh physical
readback was executed for this owner-run cell; precise timing, raw installed
identity and the delta path are not newly measured or inferred from the report.

The next request authorizes building and registering one newer MCU candidate,
and explicitly reserves the remaining delta generation, channel publication and
physical test to the owner. Prepare **3.3.38 / 30338**, with no additional MCU
behavior change or App rebuild. Do not generate/enable a delta, advance any
channel, operate the phone/MCU or retry the completed full-package test.

Fresh primary/remote main is `6edaccef096490270b51dbb68512211c6a499499`.
Existing candidate 30337 comes from successful original-Admin run
`44727375725`; the owner's Stable publication is visible at channel revision 11,
release `fw_c1d9c33ca5b4e7f6301f5f4220be3833c689253f8dbae571394dbac8c5ee0259`.
Its backend target-image SHA-256 is
`40040046dc334ec8d36f745b6981a3a25056f214a3bb408db278b9e2b2d34f20`.
This is the packaged target identity, not the unfinalized source-build binary's
hash. Future delta selection must use this exact backend 30337 release.

The existing Admin and GitHub release listing, including drafts, show no 30338
reservation. Original read-only inspection and preserved channel/delta rows are
in `.cache/ota-device-delta-20261120/keyring-inspect-01/`. The selected writable
root remains `D:/github/my/E-Track`. New output, Git metadata, host homes/caches,
logs and artifacts stay inside that root. Reuse the existing original key-bound
GCC candidate workflow and protected credential routes; no new keys, credentials,
backend deployment, Boot installation or acceptance-rule changes are needed.

## Background Restart And MCU Progress Follow-Up

The owner reports successful 3.3.38 testing and requests MCU BLE progress plus
diagnosis of the connected notification after closing App 1.0.86. The precise
delta/full selection of that owner-run upgrade was not collected. Passive
readback verifies the finalized 30338 image SHA-256
`c0b7cf0da62072d2bcad4436d716e1cb987fa4113e2b1d679dcdb0c066f3b44c`, unchanged
physical Boot, current confirmation, advancing runtime and clear faults.

Evidence root: `.cache/ota-progress-background-20261120/`. The first phone
capture at 20:55 and MCU capture at 20:59 were **after recovery**, not failure
evidence: the owner's private diagnostic history subsequently establishes a
successful 20:51:30 control handshake. The 681 ms negotiation does not support
the initial lost-CAPS hypothesis. Preserve those snapshots with this correction.

After acknowledged current-session notification `notify-01`, continuous USB
window 03 and passive MCU trace 02 capture the actual failure:

- 21:38:21.779: Android `single-cleaner` kills App PID 31113; it exits at
  21:38:22.086. The owner used the same closing action as before.
- 21:38:23.125: Android starts PID 19302 for `CompanionService`.
- MCU requests reach `PHONE_REQUIRED` with advancing runtime. There is no
  MCU halt/reset/Flash write or OTA in this observation.
- Phone sample 088 at 21:41:24 shows no connected companion device or bound
  companion-device service, but the restored CompanionService record still
  has foreground notification 2410. Sample 084 retains the false text
  `device connected, background service running`.
- `failure-phone-03` at 21:46 confirms PID 19302 and a responsive native
  Service dump, but no Flutter initialization in that process's logcat.
  Recovery job 2412 last ran at 21:36:27 and next becomes eligible at 21:51:27;
  this is an eligibility window, not a guaranteed exact execution time.

This distinguishes process existence, Service recreation, Flutter execution
and a working BLE link. Existing Service initialization only occurs in
`onStartCommand`; `onCreate` merely assigns `active`. Proposed repair is a
bounded, idempotent Service-creation bootstrap, preserving disable/permission,
ownership, deadline and cleanup guards, and replacing stale connected text
before runtime/link acknowledgement. A control-timeout defect is not claimed
as the observed cause.

The finite follow-up is one query-only invocation of the existing Android
recovery job 2412 while App UI stays closed, only if it has not already
recovered. Capture before/after process, original logs, job/connection state;
no package install, OTA consent, force-stop, reset, firmware/BCB write or
permission change. This distinguishes delayed task dispatch from a broken
recovery handler. Window 04 renews the cleanly closed USB observation lease;
both MCU traces have completed and their native debuggers are closed.

All selected outputs stay inside this project; automatic SEGGER native history
remains within the existing exception. A new sparse development checkout ran
out of disk while copying unnecessary history. Only this turn's new copies
were retired after comparison (including the verified truncated prefix), with
original main/evidence files preserved. Its initial index setup is incomplete,
not product progress. No new product version, candidate, channel or delta has
been generated for this follow-up.

### Natural Recovery And Development Result

The conditional job experiment did **not** force job 2412. Its receipt
`recovery-job-01/result.json` says `triggered:false`, `AlreadyRecovered`,
`appOpened:false`. `recovered-phone-01` at 22:01:41-22:01:53 local time finds
the same PID 19302 with the companion device connected again, and the job dump
records its last execution at 21:51:27. This supports delayed scheduled recovery;
it does not establish the exact reconnection instant. Empty logcat alone is not
proof that no Flutter engine existed. The installed build did not instrument
every OEM callback, so recreation without a prompt start command remains the
leading lifecycle explanation, not a directly observed callback trace.

The checkout/index recovery completed. The exclusively owned branch is
`dev/flutter/ota-progress-background-20261120`, worktree
`.worktrees/ota-progress-background-20261120`, latest development commit
`df29425926e3749ca90f1a9c21b829c45747d897`. It contains the creation bootstrap,
sanitized native dump, MCU progress and their regressions. It is pushed to the
development branch only. Main integration, a version increment, original-signed
App release/Windows EXE, firmware candidate generation and installation are not
performed by this follow-up. Retain installed App 1.0.86 and firmware 3.3.38;
do not use the unfinalized local build as an OTA/delta baseline.

#### Scope And Signatures

This is the implementation record for the existing background/progress contracts,
not a new acceptance rule. There is no BLE command or phone control schema change.

- `CompanionService.onCreate()` posts creation recovery. An explicit
  `onStartCommand()` consumes that callback; both use `startRuntime(reason)`.
  Enable/permission, runtime acknowledgement, bounded deadlines and cleanup
  remain required. A recreated service begins with INITIALIZING, not cached
  CONNECTED text. `dump()` separately exposes service/runtime/GATT/link state
  and at most the existing bounded sanitized diagnostic history.
- `HAL::BT_CompanionGetInfo(CompanionUpdateInfo*)` adds local-only `phase`,
  `totalBytes`, `durableBytes`, `transferVersion` from the receiver, not the
  phone's sent-byte count. `CompanionTransferPercent(info)` returns `-1` when
  no valid transfer ratio exists; multiplication uses 64 bits.
- `BT_CompanionSetProgressRefresh(CompanionProgressRefresh)` registers one
  main-loop display observer. Applying, backup and reboot boundaries refresh
  the open modal with `lv_refr_now`, never `lv_timer_handler`, UART ISR or a
  QSPI operation callback. Original END/overlay/activation/BCB order is retained.
- `CreateUpdateProgress(...)` shares the existing SD bar/numeric styling with
  BLE; it does not reuse SD file-import logic. Back closes only the view.

#### Validation And Error Matrix

| Input/event | Required projection/behavior | Executed development oracle |
| --- | --- | --- |
| Service created without Activity or start Intent | Initialize once, await actual runtime/link acknowledgements | Native Service and real headless-bridge tests |
| Explicit start before creation runnable | Consume pending runnable; no duplicate initialization/dispatch | Native lifecycle test |
| Disabled, permission loss, destroyed or startup timeout | No silent ownership; release resources and reject late reply | Native guard/deadline tests |
| 4096 durable of 8192 total | 50 percent and actual byte counts | HAL method and real-LVGL tests |
| Zero total, durable beyond total, inactive session | Unknown/hidden ratio, never fabricated completion | HAL boundary and real-LVGL tests |
| Apply, backup, reboot | Phase text/indeterminate display; no success claim | Phase observer and synchronous display-flush tests |
| Activation error or new transfer | Show failure or discard prior phase; preserve activation return value | HAL error and fresh-admission tests |
| Close/reopen or late phase callback | No task cancellation, stale object access or input-group leak | Real-LVGL lifecycle tests |

Good/base/bad cases: an idle service is not a connected device; an acknowledged
runtime plus a real GATT link is required. A 50 percent durable transfer is valid;
100 percent sent by the phone, a stale notification, or a timer-generated apply
percentage is not. The target is not successful until the normal post-reboot
identity verification. These checks do not establish physical background
reliability or display behavior on an installed new image.

#### Executed Tests And Build

- Full dual-host checks and debug APK/native run
  [44765814170](https://github.com/Eitan-S-23/E-Track/actions/runs/44765814170)
  pass on the exact development commit. Flutter 3.47.9 / Dart 3.13.7:
  Linux 972 passed / 16 skipped, Windows 920 passed / 68 skipped, zero failures.
  Native JUnit originals total 127 passed, zero skipped/failures/errors:
  Service 31, integration 72, GATT 6 and device OTA 18.
  Both full original report/log artifacts are archived in `keyring-artifacts-01/02`.
- Debug APK compilation and signature verification pass. CI metadata records
  132595964 bytes, SHA-256
  `c82de927a52d68db441c6a8ba24bcd78850f725c8b1d1414ff78da26e29e7032`.
  This is a development-signed artifact, not a shipping App or an installed fix.
  Standard App Windows EXE/release-mode verification remains NOT_RUN.
- `tests-01`: 61 control/HAL/real-LVGL tests pass. PNGs in `images-01` are
  lossless conversions of the original LVGL framebuffer, not design mockups.
  Percentage, byte counts, phase text, focus and layout were checked.
- `protocol-01`: actual V2 receiver suite reports 221 checks, zero failures.
  Its SD test failed because the sparse checkout omitted golden vectors.
  After restoring only required tracked dependencies, `protocol-02` passes
  29 SD core checks and **7** adapter scenarios. The script's older aggregate
  footer still says 5; use the actual scenario output rather than that footer.
- The default build batch was attempted first. `build-01/02` retain missing
  sparse dependency failures; `build-03` retains include-lookup failures in the
  deep default output directory despite the required headers being present.
  `build-04` uses the same GCC Release App/Boot targets in worktree-local
  `.cache/gcc`, `CMAKE_OBJECT_PATH_MAX=200`, then the standard simulator MSBuild.
  All pass: 641 GCC warnings plus 102 simulator warnings, zero errors.
  Artifacts, nanosecond timestamps and full hashes are in `build-04/artifacts.json`.
  App size is text 629680 / data 940 / bss 560224; Boot 14720 / 4 / 9780.

#### Regression Lesson And Remaining Delivery

The defect category is an implicit lifecycle assumption across native service,
Flutter runtime and BLE ownership, with missing creation-only test coverage.
The first two native runs (`44752125648`, `44756194263`) each retain 29 failures:
the test injected its fake runtime after `ServiceController.create()` had already
drained the new callback. Merely pausing the looper did not help: Robolectric
4.14.1 calls `idleIfPaused()` inside `create()`. The corrected fixture attaches
the service, installs its dependencies and directly invokes the real `onCreate`
callback before explicitly advancing the queue. No product guard or assertion
was disabled. Wrong: infer that a paused controller leaves posted work queued.
Correct: verify the framework callback boundary and test both creation-only and
explicit-start orderings. The third run's 127/127 originals close this test issue.

The next delivery owner must integrate the bounded development commit under
actual main authority, increment App/MCU versions for original candidates, and
retain manual channel/delta decisions. Only after installing those builds can
the owner validate close-App/background MCU checks and the MCU progress view.
An upgrade started on old 3.3.38 still runs the old UI: displaying the new progress
requires an already-installed receiver containing this change. Do not replay the
successful historical 3.3.38 upgrade merely to repair collection.

#### Observation Closure And Write Audit

Both USB windows have successful closure receipts. The final `audit-01` queries
the host without starting ADB/J-Link: private port 5048 is closed, original USB
owner PIDs 900/1600 are absent, the device lock is absent, and no Commander, RTT
logger or J-Link GDB server is running. No phone UI launch, installation, new OTA,
reset or firmware/BCB write was performed for this development follow-up.

Selected source, Git, log, build, image, compiler/MSBuild home/cache/temp and
download outputs remain project-local. The build host's WinINet compatibility
junction `build-04/host/userprofile/AppData/Local/Microsoft/Windows/INetCache/Content.IE5`
was inspected with `fsutil reparsepoint query` and canonical resolution: it targets
the sibling `INetCache/IE` inside the same project-local host profile, not an
external directory. It was not removed or reused as an output path.

Watched SEGGER metadata and the PowerShell 7 startup sample remain unchanged.
`C:/Users/SU/AppData/Local/Microsoft/Windows/PowerShell/StartupProfileData-NonInteractive`
changed in hash/mtime during observation and again before final audit. This is
an observed external change, not attribution: no PowerShell was invoked by the
recorded task commands, and no process-level writer evidence was collected.
It was not cleaned, moved or modified by a remediation command. Do not describe
the session as proving zero unrelated external filesystem changes. The board,
index and this task note remain local pending documentation, not remote delivery.

### Global Update Prompt Follow-Up

The owner's 2026-11-21 request authorizes completing the update prompt on every
MCU page. Continue in the existing exclusive development worktree, based on
`df29425926e3749ca90f1a9c21b829c45747d897`; primary and remote main remain
`16d9174005f35deec7957794bf417ea079daec2e`. This is implementation and host
validation, not a new release, device installation or channel/delta operation.

Source inspection finds the phone's periodic, manual and device-requested checks
already share `CompanionRuntime._prepare`: the existing OFFER is sent after
download verification, acknowledged by SEEN, and deduplicated using SHOWN.
Metered-download policy, verified-package readiness and old-device fallback are
preserved. The missing behavior is MCU `CompanionPoll`, which allows only three
pages and incorrectly requires installation eligibility before showing a prompt.

Remove that page/recording/power visibility gate without weakening installation
admission. Recheck automatic prompts after the asynchronous open boundary so a
withdrawn, expired or busy offer cannot open a stale dialog. Preserve one modal,
input ownership, duplicate suppression, Later and fresh-consent checks. SD work
must not gain a second upgrade action; a LiveMap-originated consent must release
its snapshot overlay through the existing page lifecycle before BLE can acquire
that shared workspace. No Flash/BCB/protocol or map-rendering change is planned.

Validation will extend the existing real-LVGL/source-bound regressions for all
registered pages, unsafe-but-visible offers, asynchronous changes, focus and
consent, map exit and concurrent SD work. Reuse the existing contained short-path
GCC App/Boot and simulator build route; prior App CI remains applicable only to
unchanged App inputs. New findings and actual results will be recorded here.

#### Implemented Behavior And Development Checks

The bounded follow-up changes only `FirmwareUpdate.cpp` and four MCU host-test
files in the existing development worktree. There are no new App, HAL receiver,
Boot, wire-format or release-version changes. The product file SHA-256 tested and
built is `dd1432e16be04124421eca1a4b1977571f7234faaa08060b7a0728692f29956c`.
These edits are local on top of `df294259`; they are not a new pushed commit or
main integration. Earlier background/progress development commits remain intact.

`CompanionPromptPending(info)` accepts a live, promptable offer independently of
page name, recording and battery state. `CompanionQueueOpen(automatic)` keeps a
single asynchronous opening and promotes an explicit manual request over a
pending automatic one. `CompanionOpen` rechecks the live offer and page transition
before creating the top-layer modal. The existing 250 ms poll retries after a
page transition without consuming SHOWN prematurely.

`CompanionInstallOffer(displayed)` retains fresh offer binding and installation
eligibility. Only a deliberate Now choice from LiveMap invokes existing
`PageManager::BackHome`, whose force-unload path releases the snapshot overlay
before sending CHOICE. The receiver's final recording/power and overlay checks
remain unchanged. Later and ordinary presentation never navigate or install.
`companionSdBusy` follows successful SD Begin through FinishImport/ReleaseUI;
during that work the notification remains visible, but check/install are disabled
and the dialog explains the active SD task. Dismissal does not cancel that task.

| Event | Required behavior | Development oracle |
| --- | --- | --- |
| Offer on any stable page, including a future page name | Top-layer modal, one presentation, no implicit installation | `global_pages`, registry coverage |
| Low battery or open recording | Show version and safe-condition explanation; Now disabled | `global_unsafe`, actual HAL/control safety suite |
| Safety or SD state changes after press | No stale action or consent | `global_unsafe`, `global_busy`, `sd_work_blocks_choices` |
| Page transition before or after queueing | Preserve pending offer; display when stable | `global_transition` |
| Withdrawn, expired, acknowledged or busy offer before async open | No automatic stale dialog | `global_stale`, control expiry tests |
| Active BLE transfer/apply | No competing automatic offer or second task | `global_busy`, existing progress/control cases |
| LiveMap Now or rejected navigation | Release workspace before consent, or send no consent | `global_map_install`, `map_release_before_consent`, lifecycle source bindings |
| Later, duplicate callbacks, deleted old focus | Single close/choice, original input groups restored, no freed focus | `global_pages`, existing ownership/repeat/focus cases |

Wrong: reuse the installation predicate to decide whether users may learn about
an update, or send Now while LiveMap still owns BLE's shared workspace. Correct:
show a current offer globally, preserve its identity and separately enforce
actual installation readiness and page/resource lifecycle.

Evidence remains under `.cache/ota-progress-background-20261120/`:

- `tests-02` is the deliberate pre-fix reproduction: all six new global-prompt
  cases fail on the previous product source, with the original 12 modal tests
  passing. Preserve this red result.
- `tests-03` passes all 18 modal tests, but the broader command fails because the
  old source-extraction safety fixture lacks the new helper dependencies and two
  requested module names do not exist. This is retained as a harness/setup
  failure, not mislabeled as a complete passing batch. The fixture now extracts
  the actual helpers, and the invocation uses the four real suites.
- `tests-04` passes **72 tests**, zero failures/errors: 24 control, 27 actual
  HAL/control/recorder boundary, 20 real-LVGL/source-lifecycle and one menu test.
  The real-LVGL cases exercise all nine registered pages plus FileBrowser and an
  unknown future page. They also retain existing progress and repeated-close
  coverage. No fake boundary result is called a physical page/encoder test.
- `images-02` contains lossless PNGs of the actual test framebuffer. The normal
  global offer, recording-blocked and SD-busy dialogs were visually inspected:
  complete Chinese glyphs, target version, readable explanation and correct
  disabled/focused actions, without overlap. The fixture's version 3.3.31 is not
  a device observation or shipping version.
- `build-05` reuses the already-qualified contained short build path: GCC Release
  App and Boot targets plus simulator MSBuild succeed. The incremental run has
  **396 GCC warning lines, zero simulator warnings and zero errors**; it is not
  a new clean-build warning count. App size is text/data/bss
  `630252 / 940 / 560224`; unchanged Boot is `14720 / 4 / 9780`.
  `build-05/artifacts.json` records all ELF/HEX/BIN/MAP/EXE bytes, timestamps and
  SHA-256 values. The new unfinalized App BIN is 632624 bytes, SHA-256
  `2e2f7ed3899009f411633987e2e717d2527272c965fcd9cc5d44b51c9b822b85`.
  It is not a publishable replacement for existing 3.3.38 or a delta baseline.

No new Flutter build was needed for this MCU-only follow-up. Prior App CI proves
only its unchanged App inputs. No new version, signed candidate, publication,
installation, actual phone/MCU operation or formal independent acceptance was
performed. A newly built receiver must be installed before this global popup can
be observed on hardware; the previously verified installed 3.3.38 is not changed
by a host test. Main delivery and the owner's channel/delta decisions remain
separate from these local source and build results.

`audit-02` confirms the private ADB port, previous USB owners and native debugger
processes remain closed, with no device lock or new device command. Selected
source/docs, helper, test fixtures, build outputs, images and compiler/MSBuild
home/cache/temp locations remain under `D:/github/my/E-Track`. The new
`build-05/host/userprofile/AppData/Local/Microsoft/Windows/INetCache/Content.IE5`
junction was inspected with `fsutil` and canonical path resolution; its actual
target is the sibling project-local `INetCache/IE`. It was neither cleaned nor
used as an agent output alias. No new project-external controlled output is
identified. As in the prior audit, the watched Windows PowerShell startup sample
has changed since `audit-01`; no PowerShell command was invoked here, and the
writer is unknown without process-level evidence. No external cleanup or
attribution was performed. Unrelated primary-checkout files remain untouched.

### Authorized Three-Part Delivery, 2026-11-21

The owner's request to complete all three proposed steps authorizes bounded main
integration/push, original-signed App and production GCC candidate delivery,
installation and the finite device follow-up below. Channel publication and
delta generation/selection remain reserved to the owner. No Boot replacement,
user-data clearing, arbitrary BCB field edit or project-external output is added.

The fresh primary/remote entry is `16d9174005f35deec7957794bf417ea079daec2e`.
Reuse the existing three development commits through `df294259` and the five
validated global-popup files; do not replay their successful host/development
checks. Preserve unrelated disk-cleanup work and all earlier failed receipts.
Delivery outputs are confined to `.cache/ota-companion-delivery-20261121/`.

`keyring-inspect-01/versions.json` checks the original Admin, D1 and 127 GitHub
releases, including unpublished drafts: App `1.0.87+113`, receiver `3.3.39` and
forward target `3.3.40` are all available. The read-only inspection preserves a
baseline of App/firmware channels and the 50 existing delta jobs. It does not
reserve versions or change business state.

| Step | Operation | Required result |
| --- | --- | --- |
| Source and candidates | Commit the bounded task files, preserve main documentation, merge ancestry, increment both App version fields and firmware release notes, push main once | Exact-source original APK/EXE and GCC candidate jobs succeed; original Admin and stored bytes agree |
| Install fixed receiver | Prepare original candidate bytes and exact ELF/map; inspect current App/Boot, confirmation, staging and health before standard J-Link installation | Retain Boot/recovery/user data; complete supported installation state, full target hash, matching confirmed version and advancing health, not App-only identity |
| Install fixed phone App | Use the owner's original backend update route; prepare USB log collection only when useful | Actual original-signed 1.0.87/113 installed; no debug overwrite, data clearing or automated taps |
| Prepare forward target | Version-only 3.3.40 candidate through the same main pipeline | Genuinely higher immutable target, left unpublished for the owner's channel/delta choice |
| Global prompt and Later | With the fixed receiver on a non-OTA page, make a verified higher offer available, then choose Later | One top-layer prompt; Later retains the page and never starts an upgrade |
| Background response | Close App through the owner's normal route, observe acknowledged runtime/link recovery, then check from MCU without reopening App | Original logs distinguish actual usable companion link from stale connected notification; no scheduled ten-minute recovery dependency |
| Device-originated update | Owner chooses Now with safe admission and the selected package | Durable MCU progress and apply state are visible; post-reboot exact target/confirmation and original phone logs establish outcome |

The last physical observations remain App `1.0.86+112` and finalized 3.3.38;
current USB/J-Link availability has not yet been probed. A 3.3.38-to-fixed-version
transfer cannot validate the new receiver UI. No successful OTA is repeated to
repair a collector; uncertain installation/state is reconciled before proceeding.
Candidate registration, channel publication, installation, physical observations
and formal independent acceptance are separate milestones.

#### Local Integration Prepared

Global-popup commit `0942629eef7b4ba6d82b12fb919dcb481656b11b` preserves the
existing development history. Main documentation commit `2de42c8f` and the task
branch are joined by ordinary two-parent merge
`f954bd01336030171b4482806c9ce13f90fd6528`; no squash, source copying or unrelated
worktree changes were used. The release inputs now request App `1.0.87+113` and
GCC receiver `3.3.39`. Official jobs and installation are not yet observed.

The initial documentation commit attempt stopped before staging because a newly
added board line carried CRLF in the historically mixed-EOL file. Its failed
receipt remains at `keyring-commit-02/`; the existing scoped formatter changed
only that line's ending, after which `keyring-commit-03` succeeded. This host
formatting issue did not change product source or replay a device/build operation.

#### Receiver Installation Binding

Main `71166bade110a61d0eb0787531a343e0e2c45df3` is pushed. Candidate run
`44791221159` has completed its firmware job and registered unpublished 3.3.39
as `fw_91fc008ead324345e5bc42b20e4e2bd921c3342065175cbf61ac34f996836bc1`.
The original 632508-byte target SHA-256 is
`258ccb7969ea0200668dd6ad225eb86c2893fe74e3e4e31503527605e23667ec`.
`prepare-02` reuses the existing exact-CI finalization route, without compiling
or repackaging a new release: its finalized App and recovery container match both
original registered hashes, and its executable bytes match the original ELF/map.
`keyring-artifacts-01` retains original source/proof/registration artifacts.

`preinstall-01` is a fresh passive full backup: running App is the original
30338, physical Boot is unchanged, current-boot RTT says CONFIRMED 30338, runtime
advances, recorder/receiver/debugger owners are idle and all four QSPI regions
are saved. Candidate and committed staging are 30338, backup is validated 30337
(630760 bytes, CRC32 2374097487), and recovery remains validated 30276. No halt,
reset, RAM/Flash or EEPROM mutation occurred in that observation. Its startup
NRST/WDT marker is preserved, not attributed to a new agent reset.

The definite direct-install constraint is that existing CONFIRMED state does
not automatically adopt a newly flashed App version. Reuse standard SEGGER 8.18
Commander for App programming and the existing host-only physical-recovery C
kernel plus exact eight-page EEPROM transport for complete-state confirmation.
The small task-bound entry joins these already-qualified operations; it does
not implement another Flash algorithm or change product Boot/BCB logic.

The one installation cell has a 2400-second outer deadline. Recheck all captured
Flash bytes and storage ownership, stop at the qualified storage-idle main-loop
boundary with watchdog freeze, back up repeated A/B and configuration bytes,
and derive the entire inactive record from the validated target before writing.
Program only the App through Commander and verify complete target/unchanged Boot
while still halted. Reassert and verify watchdog freeze, recheck identical EEPROM,
then use the C-bound 30338 -> 30339 transaction for exactly one inactive 64-byte
record. Preserve the old active record, all configuration and QSPI bytes. Only a
fully verified transaction permits the ordinary reset, fresh matching 30339
confirmation and original-target/runtime readback. Uncertain results retain the
held state and owner for reconciliation; no blind retry, old-App resume, downgrade
or arbitrary version-field patch is admitted.

`repair-host-01` passes 115 existing C/EEPROM assertions for these exact identities.
The final source-bound `repair-host-02` also binds the added post-program watchdog
freeze check before the physical cell. These are installation-adapter self-tests,
not independent acceptance or an already installed receiver.

#### App Candidate Delivered And Forward Target Prepared

Original Trace signing run `44791450526` is EXECUTED SUCCESS for source
`71166bade110a61d0eb0787531a343e0e2c45df3`, with both Android APK and Windows EXE
jobs successful. Strict analysis/tests, original signer/package/ABI/configuration,
signed metadata, complete R2 readback and candidate registration all succeed.
`keyring-logs-01` retains the original run/jobs and sanitized native job logs.
`keyring-inspect-02` independently sees App 1.0.87/113 and MCU 3.3.39 in the
original backend; Trace's immutable v1.0.87 release exists. This is not yet an
installed 1.0.87 observation. No channel or delta operation was performed.

That same fresh inspection confirms 3.3.40 is unoccupied. The next main delivery
changes only firmware version/release notes plus the current operational record;
App remains 1.0.87/113 and MCU product behavior remains identical to 3.3.39.
The receiver installation cell is still running and cannot yet be called a PASS.
Preparing the forward candidate does not depend on prematurely claiming that
installation, and does not require rebuilding the successful App.

#### Commander Post-Programming Reconciliation

`install-01` backed up both valid BCB records/configuration and derived the exact
inactive A record from active B/sequence 1049/CONFIRMED/current 30338. Its one
Commander write produced the complete correct 632508-byte 30339 image and
unchanged full Boot. It then stopped before any EEPROM write: the post-program
DHCSR was `0x01010009`, not a held core. The original Commander log explains the
host assumption failure: `loadbin` performs an implicit reset/halt and runs its
loader. The receipt's `resetRequested=false` means no explicit `r` was sent;
it is not evidence of zero hardware resets. Its `held=true` is bookkeeping from
the earlier rendezvous and is superseded by the actual DHCSR observation.

`reconcile-01` freshly verifies the entire target/Boot again without writes.
VTOR is zero, RTT is not initialized, SDIO2 count/status are zero and the
target-App counters are not a valid running-App observation. These are loader/
pre-App state, not evidence of a 3.3.39 product crash. No EEPROM payload was
written by the failed cell, and its full backup/expected inactive record remain
preserved. Do not repeat the already successful Flash write.

The bounded continuation reuses that exact C draft and transport. It first
rechecks complete App/Boot and idle SDIO, performs the ordinary bootstrap only
if VTOR is still zero, then requires initialized advancing target runtime and
unchanged QSPI before a new storage-idle rendezvous. It reads a fresh repeated
BCB pair and all configuration, requires exact equality to the captured bytes,
and completes only the same inactive-record transaction. Final reset/readback
still requires verified confirmation. `confirm-host-01` checks the exact draft,
source binding and no-programming-command entry; all 115 original C/EEPROM
assertions are reused. The 2400-second continuation adopts only the stopped
installation's ownership receipt and preserves it in the new output. No new
Flash algorithm, repeated firmware programming, Boot/QSPI write, OTA, channel
change or weakening of the confirmation gate is introduced.

#### Installed State And Missing-Popup Diagnosis

Installation continuation `confirm-01` succeeded at 2026-11-20T19:47:18Z:
the already-written original 3.3.39 App was bootstrapped, then the original
inactive-record transaction wrote and verified exactly eight EEPROM pages.
Active B/sequence 1049/current 30338 became active A/sequence 1050/current 30339,
CONFIRMED with zero bootTry/copyPhase/resumeBlock. Old active B, configuration,
all four QSPI regions and full physical Boot were preserved. Original target
readback, fresh matching confirmation and advancing runtime passed. There was
no second App programming operation; `install-01` remains a preserved failure.

Main `145843da78bcf6ce142f75480c450223864654db` delivered version-only forward
target 3.3.40 through successful candidate run `44798898781`; App was correctly
skipped. `keyring-inspect-04` observes external publication of Stable App 1.0.87
(revision 63) and firmware 3.3.40 (revision 14), and 53 delta jobs. The public
selection for exact installed 30339 is the verified 314-byte patch with SHA-256
`482c8da4a808532071a8ad990423b7e31e302bd1b566a1bb29418aaf48634ab3`.
The earlier unpublished-baseline failure in `keyring-inspect-03` is preserved.
This agent did not publish either channel or generate/enable a delta.

The owner reports correct installed versions but no global update popup. Fresh
evidence is under `.cache/ota-companion-delivery-20261121/`:

- `popup-phone-01` safely handed off only the authorized phone from the actual
  LDPlayer ADB PID 18752 after process/port/creation identity and attached-device
  checks. The emulator was not stopped. Private ADB 5048 then verified original
  App 1.0.87/113, APK SHA-256
  `86bc6ec3346ee9daaaefc5e5d5b66ca8ce1ce74d31fd7a4dabd2229ab1a19828`.
- `popup-phone-02/phone/adb-00006.stdout` invokes Android's singular service dump,
  unlike the first snapshot's ordinary service inventory. Its native original
  diagnostics show engineLive/gattConnected/linkAcknowledged/runtimeAcknowledged
  all true. An acknowledged offer reached READY_AWAITING_DEVICE_CHOICE, a LATER
  choice reached DEFERRED, and later service recreation recovered and prepared
  another acknowledged offer without opening the App during collection.
- `popup-mcu-01` failed its host ABI assertion before any J-Link device command:
  this GCC build uses a short enum, so Control is 720 bytes, not the assumed 724.
  Original failure/symbol output remain intact. Its exact dead owner lock was
  reconciled and released with a receipt before the corrected passive read.
- `popup-mcu-02` full App readback matches installed original 3.3.39
  `258ccb7969ea0200668dd6ad225eb86c2893fe74e3e4e31503527605e23667ec`;
  full Boot remains `01e4b9e162bfaaf9fda070aa13c0cec3f377b8d696db01f731e0ab3d1464e527`.
  Confirmation and advancing runtime pass. Both control samples show target
  30340, request 1, DEFERRED, hasOffer=false, prompt=false and the above selected
  patch hash equal to shownSha. The global UI manager exists, but no modal or
  queued opening exists. No halt, reset, RAM/Flash write or OTA was requested.

The current no-popup state is consistent with existing same-package suppression,
not an absent installed implementation or failed current BLE link. It does not
establish whether the initial automatic popup appeared: CompanionRefresh marks
an offer SHOWN when presented inside a manually opened update dialog as well,
and its Back/Later path sends LATER. The phone persists SHOWN across recreation;
the MCU additionally suppresses the same package even for a fresh prompt=1 offer.
Before changing the documented no-continuous-repeat policy, ask whether the owner
manually opened the MCU update dialog and returned, or the first unsolicited
prompt never appeared. This observation does not close popup/background/progress
physical acceptance. No product code, version, build, CI or publication changed
in this diagnostic follow-up, and no successful OTA was repeated.

Both private ADB collectors closed their owned server/port and verified the
original key unchanged. The passive debugger closed and released its lock.
Selected helpers, logs, readbacks, launcher COM generation and child-process
home/cache/temp outputs are project-local. The native audit reports no changes
to watched external SEGGER or PowerShell paths; no PowerShell was invoked and no
external cleanup was performed. These operational-note/board/index updates are
local pending changes, not a new delivered main revision.

### UI, History And Launch Diagnostics Batch, 2026-11-21

Owner authorization now covers the full implementation, main delivery, original
App/GCC candidate builds, direct J-Link installation of 3.3.41, and preparation
of 3.3.42/3.3.43 in the original backend. Do not perform an extra package-download
verification or initiate a device OTA/manual update check. Retain ordinary build
integrity checks and retrieve artifacts actually required for installation.
First deliver the new App; after it is installed, publish 3.3.42 Stable with an
exact 3.3.41-base delta. Keep 3.3.43 unpublished until the owner completes the
first OTA, then publish it with a 3.3.42-base delta. Do not advance Stable past
the first test target prematurely. Full Boot/user data and supported confirmation
state are preserved during the direct receiver installation.

Implementation starts from main `145843da` in exclusive worktree
`.worktrees/ota-ui-20261121`, branch `dev/flutter/ota-ui-20261121`. Prior pending
operational notes and other agents' disk-cleanup work remain untouched. The App
history API is still a stub; launch diagnostics currently keep only 80 records
and conflate wake trigger with actual UI visibility. Implement durable per-device
OTA attempts/outcomes and a bounded searchable/exportable diagnostic journal.
Record native process/service/UI lifecycle, explicit launch source, task/attempt
identity and monotonic timing. Missing termination/start-source evidence stays
unknown; do not infer foreground/background from `presence` alone or invent old
history. Upgrades become successful only after target identity verification.

Visual thesis: precise, calm cyan telemetry on the existing dark petrol display,
with one strong firmware/progress focal point and readable native typography.
Content: concise available-version decision, then durable transfer progress and
honest apply/reboot phases. Motion: restrained dialog arrival, a small activity
highlight independent of progress, and phase transitions without fake percentages.
Use existing LVGL primitives and a small necessary generated asset rather than
full-screen animation frames or a new graphics stack.

Generate popup groups P01-P05 and process groups U01-U05 with keyframes; retain
and deliver every design, including unselected ones, with explicit final choices.
Two owner-provided image APIs may run concurrently. Their keys enter only through
non-echoing stdin and child environments; public config contains environment
references only. The unmodified installed image2 CLI is reused through a thin
project-local config adapter because its CLI has no custom-config switch. Its
global config/pool remains untouched, and all controllable outputs are under
`.cache/ota-ui-20261121/` and `generated-images/ota-ui-20261121/`.
`images-01` is a host metadata-path failure before credentials or requests;
preserve it. `images-02` is the actual two-provider generation batch.

#### Successor Implementation Scope

The current owner handoff supersedes the wider publication/generation text above:
only P01 (`popup/1/1.png`) and U01 (`process/1/1.png`) under
`generated-images/ota-ui-20261121/` are selected. No further generation, backend
login/API mutation, deployment, channel/delta operation, phone update, manual
check, OTA, data clearing or additional agents by this session. Owner handles
those manual backend/phone actions. Agent implements, self-tests, integrates and
pushes bounded main changes, observes automatic candidate CI, then installs
exact-source original GCC 3.3.41 through supported complete-state J-Link
transactions preserving Boot/configuration/user data. 3.3.42 and 3.3.43 are
immutable candidates; owner tests 30341 -> 30342 before 30342 -> 30343.

Entry: main/remote `145843da78bcf6ce142f75480c450223864654db`; existing task
worktree clean. Process/cwd inventory found no other task-worktree owner or
active J-Link/ADB process. Three pending main-note edits were inspected and
retained. No `.trellis` exists in either checkout. No setup/repair, old tests,
OTA or installation replay. Git ownership uses per-command `safe.directory`,
never global configuration. All controllable outputs stay in the project.

Research: `OtaService.startOtaUpgrade` is the shared App/MCU path. Its existing
targetVerified branch requires new-link version/full raw hash agreement. Persist
attempts before transfer; preserve indeterminate post-transfer outcomes and
reconcile only fresh matching identity. Replace the native 80-row preferences
history with bounded segmented storage/query/export and explicit loss reporting.
Record real Activity lifecycle independently of wake trigger. Keep creation-only
Service bootstrap intact; instrumentation does not resolve unproved recurring
connection timeouts. P01/U01 use LVGL primitives without shadows, fake progress
or delayed small transfers. Existing safety/deduplication/consent remain intact.

Self-tests: full dual-host development CI and applicable native tests; existing
MCU/UI host tests and standard GCC/simulator entry. No local Flutter/Gradle build
or external SDK install. Prepare observation/retrieval before owner testing.
Implementation, CI, installation and independent acceptance remain distinct.

#### Implementation And Self-Test Delivery

The bounded product/test chain is `6c14b654`, `3c522b65`, `28cdb9fc`,
`c562d2bc`. Main fast-forward integration is complete locally; `integrate-01`
checks the three pre-existing main-note files byte-for-byte before/after.
The exclusive development branch is remotely at `28cdb9fc`; `c562d2bc` changes
only two MCU font references after real-LVGL inspection, not the tested App tree.
Main now prepares App **1.0.88+114** and MCU **3.3.41**. Candidate packaging,
automatic registration and direct installation are still pending at this entry.
Release occupancy was checked by listing all 126 Trace releases (including
drafts) and both E-Track releases, not a tag lookup. No 1.0.88 reservation exists;
the preceding App is 1.0.87+113. Existing assets were not modified.

Contracts implemented:
- `OtaUpgradeHistory` serializes a per-device append journal before transfer;
  one task ID binds origin, old/target identity, package kind, stage, monotonic
  duration, retry count and outcome. END uncertainty/process interruption stays
  awaitingVerification; successful reconciliation requires target version/full
  hash/hardware and a fresh connection (or a fresh process), never cached INFO.
  Corrupt/read/write failures are visible. No historical records are fabricated.
- P01/U01 use native LVGL objects/arcs and existing subset fonts. Byte progress
  and phase truth remain in the receiver. A constant-length activity arc is not
  progress. Screenshot inspection found missing subset glyphs and a disabled
  button overlapping the active view; both were corrected without animation
  delays or safety-policy changes. The current-version field is read from the
  validated MCU identity cache; zero is unknown rather than a build-time guess.
- Native journal input is allowlisted, disk IO is serialized off the UI/radio
  path, repeated events carry counts and the pending queue is bounded at 512.
  Seven-day/20-MiB retention, cursor/time/device/task/level/search queries and ZIP
  export include explicit pruning/drop/IO/malformed/process-death gaps. Detailed
  mode adds queue/heap observations for at most 15 minutes/2000 events.
- Native UI create/resume/pause/stop/destroy, service creation/destruction,
  task removal and available process-exit reasons are separate observations.
  `user_requested_or_force_stop` stays ambiguous; a missing callback is not a
  fabricated force-stop. Missing close/boot evidence yields unknown timing.
  `LINK_REUSED` explicitly means no reconnect. GATT, identity and acknowledged
  control readiness are distinct. Existing creation-only bootstrap is unchanged.
- Check schedule/execution, offer acknowledgement, MCU SHOWN and same-package
  suppression are recorded. SHOWN origin remains unknown because the existing
  protocol does not distinguish manual opening from an unsolicited popup.
  No protocol expansion, dedup reset, schedule change or claimed BLE repair.

Original self-test evidence is under `.cache/ota-ui-20261121/`:
- `tests-01`: 44 tests execute successfully, with one additional suite setup
  failure because its host stub lacked the new identity-cache field. This is
  not a product pass for the entire invocation. `tests-02` fixes the stub and
  passes all 27 safety tests. `tests-05` passes all 20 actual-LVGL modal tests,
  including original negative controls, global pages, safety and real progress.
- `build-01` preserves the standard batch's Windows dependency-path failure.
  Project-local short builds `build-02`/`03`/`04` pass GCC App+Boot and simulator.
  Full build has 743 warnings/zero errors; incremental warning counts and all
  timestamps/hashes are recorded in each `artifacts.json`. Existing wchar/RWX
  and simulator conversion warnings are not hidden or relabeled as fixed.
- First development `44882186277` is red: Linux's exact event-order assertion
  still expected two recovery events, while the new timeline emits five. The
  updated assertion checks all five in order. `44884790401` retains a Windows
  P35-R03 cancellation-probe test failure (expected 2 writes, observed 1);
  untouched transport code and same-source `44885200017` later pass both hosts,
  native tests and debug build. No transport timing/assertion was weakened.
- Final App source `28cdb9fc`: checks-only `44889136340` and native/debug
  `44889483329` both pass on Linux/Windows. The checks-only full suites report
  Linux 979 passed/16 skipped and Windows 927 passed/68 skipped, plus eight
  candidate tests per host. Native/debug status is separately verified, not
  a release-mode APK/EXE claim. SDK is Flutter 3.47.9 / Dart 3.13.7.
- Current visual evidence is `images-05/` (original rendered PPMs retained in
  the task worktree). Earlier `images-03/04` preserve the glyph/layout findings.
  Only the two selected design boards were opened; no new image generation.
- `keyring-commit-03` is a transport failure before any Git operation; HEAD and
  empty index were reconciled before the successful successor. Failed log/ZIP
  retrieval receipts remain preserved; they caused no device action or CI rerun.

The USB observation route now supports read-only service dump pagination:
`dumpsys activity service com.wen.gaia.gaia/.CompanionService --journal`, then
`--journal --before <nextCursor>`. Pages carry sequence/loss metadata; a timeout
is an explicit error. This does not start the App/service or check for updates.
Prepare the current ADB ownership and bounded retrieval before owner testing;
if no service exists, preserve that fact rather than opening the App to conceal
the failure. User-triggered complete ZIP export is the alternate after-test route.
No phone UI, OTA, data clearing, debugger access or installation has occurred
during these implementation/self-test operations. Physical automatic discovery,
global popup, background recovery, history and target confirmation remain open.

#### Formal Candidates And Installation Matrix

Source **50b9af34090214e1a64424d6280352bcfd6aa82f** is pushed on main.
Original candidate `44893270196` firmware job passes and registers 3.3.41
full/recovery with its own R2 verification. Original Trace signer `44893376360`
passes Android and Windows for App 1.0.88+114. No manual backend action,
channel publication, delta generation or phone operation by this agent.
Native development originals now archived: all four JUnit suites total **132**
tests, zero failures/errors/skips. Full checks are 979 Linux/927 Windows passed
(16/68 platform skips); the final incremental GCC/simulator build has 396
warnings, zero errors. All earlier failures remain preserved.

The fresh passive snapshot `device-41/preinstall-01` rejects the assumed 3.3.39:
the actual full App is already **3.3.40**, SHA-256
`add8309a32fea14e66c1d70ebd9327d5292085c7efe701d41464c8a998127496`.
No Flash/RAM/EEPROM write, halt or reset was requested. Offline successor
`preinstall-02` reuses those exact readbacks, verifies original 3.3.40 CI
bytes/header and proves all observed symbol addresses/sizes and session accessor
offsets equal the initial map. It verifies healthy advancing runtime, confirmed
state, idle ownership, unchanged original Boot and every QSPI slot payload.
There was no repeated physical read or replay of the owner's successful OTA.
The old failure stays a version-binding failure, not a fabricated 3.3.39 PASS.

Finite installation cell `device-41/install-01` (Codex sole owner):
- Input is the original 3.3.41 candidate from `44893270196`, final raw image
  634372 bytes, SHA-256
  `c09d26b59130108dd5e53d127cd54301ffd2cc3c4757ec7e5f73ce39bbe6037a`.
  The exact CI compiler binary/ELF/map, original build timestamp and metadata
  reconstruct only the fixed FW header. Target and recovery hashes both match
  CI; no source recompilation or backend download verification was performed.
- Current input is the observed 3.3.40. Backup is 3.3.39 / 632508 bytes /
  CRC32 2578887756, validated from its original slot. Boot SHA remains
  `01e4b9e162bfaaf9fda070aa13c0cec3f377b8d696db01f731e0ab3d1464e527`.
  Recheck full App/Boot/QSPI, initialized health, storage/recording inactivity,
  complete repeated BCB pair and both configuration quarters before mutation.
- Use standard SEGGER Commander, AT32F435RGT7/SWD 1000, App-only loadbin once.
  Verify full target/Boot and fresh post-loader execution/storage state, not old
  held bookkeeping. Normal target bootstrap is followed by a new symbol-bound
  storage-idle rendezvous. Then use the existing qualified complete inactive
  64-byte BCB transaction (eight exact pages), preserving old active record and
  all configuration. No single-field version patch or mass erase.
- Final restart must prove full target, unchanged Boot/QSPI/configuration,
  matching confirmed BCB and advancing healthy runtime, with current-map RTT
  signature/buffer and matching startup confirmation. Any uncertain write stops
  dependent actions; read-only reconciliation precedes only the missing step,
  never another successful Flash programming.
- Existing bounded native runner deadline is 2400 seconds; all controllable
  outputs/COM caches/settings/logs/readbacks remain in `device-41/`. Adopt only
  this session's closed read-only reservation after verifying both owned PIDs
  have exited. Do not touch other locks or kill unrelated debugger processes.
  SEGGER's existing SU history/config exception is unchanged. No other device,
  phone UI, OTA, recording stop or data-clearing operation is authorized here.

Preinstall audit observed a hash/mtime change in
`C:/Users/SU/AppData/Local/Microsoft/Windows/PowerShell/StartupProfileData-NonInteractive`.
The reviewed launcher uses Python/WMI/Commander, not PowerShell; no process-level
evidence attributes that concurrent change to this session. Its origin remains
unknown. Do not infer attribution from the filename/mtime or clean the cache.
Other watched SEGGER/PowerShell paths were unchanged in that window.

3.3.41 candidate parent `44893270196` is now completely successful (checks,
App and firmware); Trace `44893376360` succeeds on its unchanged signing
executor `12ff41fc`, bound to E-Track main `50b9af34`. Direct installation
`device-41/install-01` has started under the above matrix, not yet verified.
The current main change prepares **3.3.42 only**, preserving App 1.0.88+114 and
every firmware functional input. This is the first owner-published target from
3.3.41; no Stable/Beta switch, delta operation or phone instruction is issued.

3.3.42 is now remotely delivered at `3dd630ffe6443e6d56d336aecf4941b7488f8c35`.
Candidate `44899719630` passes checks and firmware, with App correctly skipped.
Original log `keyring-logs-09/job-136833116501.log` records registration
`fw_89dd50a67ce280bae883bda2cede743679d5fe4a9712b7d27edd0df80e1bff3e`,
`ok=true`, `state=ready`, two assets, `channelPublished=false`,
`productionApproved=false`. Target raw SHA-256 is
`cae6f46fbc18a3ef429a170993d0b95dda79b5140fad957992fe42153f34916c`;
full ETU SHA-256 is
`f8d5edd825de19eb1d40463b2ebded9468c1b0df792f3eb850b61d4f90a1f337`;
recovery SHA-256 is
`edbc1987d9f71d874b4a76c7091d56fa3341a9c1d10c497fa239b5c6190683d9`.
These are CI receipts, not an additional backend download or channel operation.
Both ordinary APK/EXE jobs are also skipped. Existing GitHub releases, including
drafts, were enumerated again in `keyring-read-04`; no MCU 3.3.43 tag is reserved.

The next bounded commit prepares **3.3.43 only**; no functional/App changes.
It remains unpublished until the owner completes 30341 -> 30342 and authorizes
the second round through the exact 30342 baseline. The live 30341 installation
has already verified its sole Flash write/full readback and target bootstrap;
the complete-state EEPROM transaction/final running verification is still in
progress. Do not replay the Flash write or alter its source-bound worker.

#### Verified Delivery And Owner Handoff

This entry supersedes the earlier local-pending/in-progress snapshots above.
Product and version commits are remotely delivered on main through
`b8ba677d4e30d34f0c05c70fbc5364db727f488e`. The final note/index/board synchronization
is documentation-only; its later commit is not the immutable package source.

| Candidate | Exact E-Track source | Original CI | Automatic registration |
| --- | --- | --- | --- |
| App 1.0.88+114 | `50b9af34090214e1a64424d6280352bcfd6aa82f` | E-Track `44893270196`; Trace `44893376360` | `rel_trace_android_v1_0_88`, `ok=true`, no channel publication |
| MCU 3.3.41 | `50b9af34090214e1a64424d6280352bcfd6aa82f` | `44893270196` | `fw_86f323a298198cbac8e5b9aac8ef3b5cbd8a77c12148b47ae38cc1028995b715`, ready, two assets, unpublished |
| MCU 3.3.42 | `3dd630ffe6443e6d56d336aecf4941b7488f8c35` | `44899719630` | `fw_89dd50a67ce280bae883bda2cede743679d5fe4a9712b7d27edd0df80e1bff3e`, ready, two assets, unpublished |
| MCU 3.3.43 | `b8ba677d4e30d34f0c05c70fbc5364db727f488e` | `44901056840` | `fw_2dda2fd61b7b7a428dd70dffdb3c44e67adb2f1f98cc9886050e1827da94c5c7`, ready, two assets, unpublished |

Original Trace executor remains `12ff41fc11eb4920ab32d69ae0f7e1cc095f996e`.
Admission, Windows and Android pass. Complete originals are now retained at
`keyring-logs-12/`; the Android native log contains the registration response and
source/version/R2-verified metadata. Immutable GitHub release `v1.0.88`, ID
453608300, is a non-latest prerelease, not a Stable/Beta publication.
APK SHA-256: `23309735b69933bd6a3da500cf8527b9ba3aad177135c42f8e0c738f706279b4`
(49161061 bytes). Windows EXE SHA-256:
`bba72a681c950ba7fde0d0f9a7b9e2f720b0e46b2bd3778cd8836069cf692c18`
(161792 bytes); Windows ZIP SHA-256:
`7fc29960a0d7ac8f4f1515c702f38159f8292c8d48d3f4b4a58b3be187a7656e`
(20721534 bytes). No debug APK was installed or substituted.

3.3.43 original receipt is `keyring-logs-11/job-136837123942.log`:
raw SHA-256 `a3a9c50eba6de06825d3d1e134063fbc0e770adb48fa591ee04014b6edc1a357`,
full ETU SHA-256 `7c6a9f1b762030a246d07998a0a32ecc00c55b1ab93b0f030eed82cc6fa6df42`,
recovery SHA-256 `c825672feb955e15453bde0953982fcce8589e75a7a816a3af122dcb58cdd884`.
For 3.3.41 the full ETU hash is
`092c41cdd2a21d9e2bd54dc4130da8cb077581a02d666354b2464648fa0a9363` and recovery is
`5ebfe3737523c71f28b1802efc969988e61e0e6a08330be4f3635137652c67db`.
3.3.42 hashes are recorded immediately above. Both successor runs skip App,
including ordinary APK/EXE builds. Offline original planner checks also prove
3.3.43 selects firmware only and all functional inputs are unchanged from 3.3.41.

**Installation completed, not merely programmed:** `device-41/install-01`
finished 2026-11-21 11:58:36 UTC, once, with `ok=true`. Full post-restart App
is 634372 bytes, raw SHA-256
`c09d26b59130108dd5e53d127cd54301ffd2cc3c4757ec7e5f73ce39bbe6037a`.
Boot remains `01e4b9e162bfaaf9fda070aa13c0cec3f377b8d696db01f731e0ab3d1464e527`.
All candidate/backup/recovery/staging QSPI regions compare byte-for-byte unchanged;
no Boot/QSPI/SD programming was requested. Complete inactive BCB A is sequence
1066, currentVersion 30341, CONFIRMED, with zero bootTry/copyPhase/resumeBlock.
Its old active B and both configuration quarters remain byte-identical. Historical
candidateVersion 30340/backupVersion 30339 are retained transaction metadata, not
the running identity; they are not patched independently. Current-map RTT has the
verified signature/buffer and `OTA: BCB already CONFIRMED vcode=30341`.
The current App health counter advances 1274 -> 35840, CFSR/HFSR are zero,
storage gates pass, watchdog freeze/breakpoints are restored and CPU is not held.
All owned Commander exits are zero/closed, the SU worker exited and the device
lock is released. No second Flash write, diagnostic OTA or successful-OTA replay.

Self-test results remain distinct from independent acceptance and user testing:
Linux 979 passed/16 skipped, Windows 927 passed/68 skipped, eight candidate tests
per host, native JUnit 132/132, actual LVGL modal 20/20, safety 27/27. Local full
GCC/simulator build: 743 warnings, zero errors; final incremental: 396 warnings,
zero errors. Each of the three formal MCU job logs has 641 `warning:` diagnostic
lines and zero `error:` lines. These are explicit log-line counts, not unique
defect counts or a warning-free claim. All earlier test/build/retrieval failures
remain retained, including `keyring-logs-10` fetch failure and a transient
REMOTE_MAIN_UNVERIFIED result that later reconciled to MAIN_MATCHED.

**Observation route prepared, no phone window consumed:** reuse the qualified
`live_phone.Phone` private owner via `.cache/ota-ui-20261121/phone_journal.py`.
`phone-selftest-01` tests two-page original-byte retrieval plus malformed/duplicate/
cursor/error rejection and rejects install, start, force-stop, clear and tap
commands. `phone-prepare-01` pins the existing ADB/key and exact release APK;
there is no SDK install, phone access or newly generated key. A live read uses a
fresh `phone-read-NN` directory, private port 5048, 600-second deadline, maximum
160 pages, service-specific dumpsys, original stdout, sequence/loss metadata and
acknowledged private-server closure. Any existing 5037/5048 owner blocks startup;
this helper never stops another ADB server. Missing service or wrong installed
APK is preserved, never concealed by launching/reinstalling the App. Page/deadline
truncation is explicit; this is not an atomic ZIP or fabricated complete export.
Owner's post-test diagnostic ZIP is the alternate retrieval route. Live producer
readiness must be verified after the owner updates the phone, before an OTA test.

Owner sequence:
1. Publish App **1.0.88+114** in the existing backend and update the phone, without
   clearing data/deduplication. Do not manually check MCU updates or change MCU
   Stable yet. Report installation so the prepared passive observation can bind
   the installed APK, actual runtime, last check and next expected check.
2. After that observation route is ready, publish MCU **3.3.42 Stable**, generate
   and enable only **3.3.41 -> 3.3.42** delta. Keep 3.3.43 unpublished. Do not open
   the App or manually check merely to provoke a notification: the normal roughly
   12-hour schedule/Android delay remains unchanged, not instant server push.
3. Observe automatic discovery and an unsolicited prompt on LiveMap/another page.
   Choose Later once and verify no transfer starts. Preserve its deduplication;
   later installation may use the MCU update page with explicit consent. Match
   real stage/progress, reboot/reconnect target identity, history and task-linked
   logs. Manual-page SHOWN does not prove the earlier automatic popup.
4. Only after the first round completes, publish **3.3.43 Stable** and generate/
   enable **3.3.42 -> 3.3.43** delta. Verify App UI close/background/reconstruction
   with actual lifecycle and usable-link records, not a foreground trigger or
   notification alone. Do not force-stop or clear state unless a separate case is
   explicitly chosen. Collect existing originals after failures; never replay a
   successful OTA merely to fix host logging.

Still open: physical automatic discovery/global popup/Later, App- and MCU-origin
upgrade history correspondence, process recovery/continued connection timeouts,
and owner-controlled two-delta OTA results. Logging is not a Bluetooth fix; the
historical watchdog cause remains undetermined. These are not independent PASS.

Selected design remains **P01/U01**. All original paths (relative to project root)
are listed here without opening the other eight images:

| ID | Original path | Selection |
| --- | --- | --- |
| P01 | `generated-images/ota-ui-20261121/popup/1/1.png` | Implemented |
| P02 | `generated-images/ota-ui-20261121/popup/2/1.png` | Original only |
| P03 | `generated-images/ota-ui-20261121/popup/3/1.png` | Original only |
| P04 | `generated-images/ota-ui-20261121/popup/4/1.png` | Original only |
| P05 | `generated-images/ota-ui-20261121/popup/5/1.png` | Original only |
| U01 | `generated-images/ota-ui-20261121/process/1/1.png` | Implemented |
| U02 | `generated-images/ota-ui-20261121/process/2/1.png` | Original only |
| U03 | `generated-images/ota-ui-20261121/process/3/1.png` | Original only |
| U04 | `generated-images/ota-ui-20261121/process/4/1.png` | Original only |
| U05 | `generated-images/ota-ui-20261121/process/5/1.png` | Original only |

Write audit: controlled edits, Git metadata, output/cache/temp/home directories,
CI logs, original firmware readbacks and simulator evidence stay within
`D:/github/my/E-Track`. Three build-host INetCache junctions resolve inside that
same project; the initial strict audit rejected them and retained `closeout-01`,
then the read-only audit resolved actual targets without weakening write guards.
The existing SU SEGGER native-history exception was used and recorded. Both
preinstall and installation watches observed changes to
`C:/Users/SU/AppData/Local/Microsoft/Windows/PowerShell/StartupProfileData-NonInteractive`;
no reviewed command launched PowerShell and no process-level evidence attributes
the changes to this session. Attribution remains UNKNOWN; no cleanup or external
write authority is inferred. The audit is a controlled-path/environment review
plus watched native paths, not machine-wide IO tracing. No unrelated files,
historical evidence or external caches were cleaned. `closeout-02` rechecks only
existing original bytes/receipts, not hardware or OTA.

#### Check Page Layout Regression

Owner feedback after installing App 1.0.88+114: the physical MCU 3.3.41 check
page repeats "obtain firmware through phone" / "phone connected" and stacks
all buttons near Back. This is a real UI failure, not a retraction of the prior
full-image/Boot/CONFIRMED installation evidence. App installation is owner-reported;
the agent has not obtained live new-App logs. App export is the preferred manual
retrieval route now; USB is optional, not a new testing prerequisite.

Root cause in `CompanionLayout(false)`: Check occupied x=16/y=202/w=188/h=32,
while Back and Install occupied y=208/h=32. Install remained visible with no
offer. Previous progress/offer tests passed but did not assert idle button bounds;
the connected idle state was missing from the reviewed screenshot selection.
The duplicate sentences were separate `companionVersion`/`companionMessage`
labels, not a Bluetooth status defect.

Local repair on main above `deb11bda`, not committed/pushed or installed:
- Check and Install use the same right-side slot x=104/y=208/w=104/h=32 at
  240x320, with mutually exclusive visibility. Back/Later stays x=12/w=84.
- CONNECTED keeps the existing single status title, with no repeated message.
  Idle version text uses only validated `currentVersion`; zero stays blank.
- Safety eligibility, consent, focus ownership, Later behavior, pending offers,
  transfer bytes/stages and P01/U01 design selection are unchanged.

`layout-red-01` reproduces two failures on the delivered source: "visible buttons
overlap" and repeated idle instructions. `layout-green-01` passes **74** tests:
22 actual-LVGL, 24 control, 27 safety, one menu regression. Both render-build
logs have zero warning/error lines; Git separately reports two LF-to-CRLF
normalization warnings. Tests check visible-button separation/panel containment
across connected, disconnected, checking, no-update, failed, offered, unsafe and
offer-withdrawn states; unknown version, button actions and return are checked.
Original PPMs are under `.cache/companion-modal-tests/run-x9u3b3z6` (red) and
`run-q_3lmwa5` (green). `.cache/ota-ui-20261121/images-06` / `images-07` contain
before/after PNGs. The ready-offer and transfer-50 PNG bytes are unchanged.

The repair has no production GCC/simulator build, CI, new candidate, device
operation or independent acceptance yet. Existing 3.3.41/42/43 have identical
affected UI source and remain immutable. Do not overwrite their assets, reuse
their version identities for corrected bytes or claim they contain this fix.
A corrected forward version and revised owner-controlled test sequence are
required before physical validation of the corrected UI; no new version or
installation authorization is inferred here.

All edits and controllable test/generated-image/temp/home outputs are project-local.
Only this batch's menu test temporary directory is automatically removed by its
existing test runner; original evidence and other caches are retained. No
PowerShell, phone, J-Link, cloud operation, external SDK or extra agent was used.

#### Corrected UI Installation Authorization

The owner now explicitly requests flashing the repaired MCU UI for inspection.
Deliver it as new immutable **3.3.44**, with App 1.0.88+114 unchanged, then use
the exact original CI GCC image/ELF/map for standard J-Link App-only installation.
Retain all existing candidates; no Admin login, channel/delta mutation, backend
deployment, phone operation or OTA is included. Direct installation advances the
physical baseline; the old 30341 -> 30342 -> 30343 OTA matrix is not executed or
claimed complete. Subsequent owner-controlled deltas need a separately agreed
forward sequence from the verified corrected baseline.

Preparation: main `deb11bda`, seven explicitly scoped repair/test/record/version
files only. Existing 74 passing host tests and red reproduction are retained.
`keyring-read-05` enumerates all current E-Track releases including drafts; no
3.3.44 reservation is present. No active ADB/J-Link/build process or device lock
was observed. Firmware-only main push uses the established automatic candidate
route; no local substitute, App rebuild or extra backend download check.

Finite device matrix under `.cache/ota-ui-20261121/device-44/`: fresh passive
3.3.41 identity/health/ownership/slot snapshot; source-bound input reconstruction
and existing complete-record/wire host tests; one App-only Commander load at
AT32F435RGT7/SWD 1000, fresh post-loader state and storage-idle rendezvous, exact
complete inactive BCB transaction preserving the old active record/configuration,
then full-image/Boot/QSPI/CONFIRMED/healthy-runtime/current-RTT verification.
Reuse qualified primitives, not old version-bound execution receipts. Preserve
any failure and reconcile before only the missing step, never repeat a successful
Flash write for logs. Keep one owner and finite deadlines, project-local outputs,
and the exact existing SU SEGGER native-history exception. No mass erase, Boot
or QSPI programming, user-data clearing, forced recording stop or extra agent.

#### Corrected UI Installed

Source `4d8c1bb1112a8195add5c2ada30de30cb53d4281` is delivered on main. Formal
firmware CI `44910534689` passes, App is skipped; 641 warning lines, zero error
lines. Automatic registration is ready/unpublished, two assets, release ID
`fw_b9812370f4789d459f26fd2e9e0797c959896ff11e0a19d681287a87f0a8f058`.
Raw App is 634380 bytes, SHA-256
`d44ef10d14af602e1d624f906e002d351483d31301273ddc06a003e050eb4833`.
Full ETU SHA-256 is `c73f39c4ee842b125f86932dacc2c9090be3d1680a8726ef2de14799dc1073b6`;
recovery SHA-256 is `4a1f1bdc8f60f07ad2576f6dc7f2df1f7f2bf331df7872899dfc1af576858347`.
Original receipt/logs are `keyring-artifacts-06` / `keyring-logs-13` under the
existing task evidence root. No extra backend download, manual publication or App rebuild.

`device-44/preinstall-01` freshly verified original 3.3.41, healthy runtime and
stored slots without halt/reset/data writes. `prepare-02` reconstructed only the
exact CI header and matched the raw/recovery hashes; `repair-host-01` passed 115
existing complete-record/wire assertions. `install-01` completed successfully at
2026-11-21 14:42:11 UTC. Full App and preserved Boot/QSPI readbacks match; inactive
BCB B is sequence 1067, currentVersion 30344, CONFIRMED, bootTry/copyPhase/resumeBlock
zero. Old BCB A and both configuration quarters are byte-identical. Current-map
RTT says `OTA: BCB already CONFIRMED vcode=30344`; runtime health advances
1240 -> 36061, CFSR/HFSR are zero, watchdog freeze restored, CPU not held.

Measured Flash programming plus full App/Boot readback: **74.3 seconds**. The much
longer complete procedure comes from host-driven, individual J-Link GPIO accesses
for I2C record/configuration reads, eight 8-byte record writes and verification.
It is not EEPROM's intrinsic write time and must not be described as a normal
34-minute EEPROM requirement. This known-slow implementation was not changed
while running. Future acceleration requires a separately qualified supported
transaction route; do not waive state consistency or improvise a writer mid-run.

The terminal wait handle disappeared and its parent exited while the isolated SU
native installer continued. WMI identified the same native command/PID 24536;
no second installer was launched and no process was stopped. `owner-reconcile-01`
retains a host CSV/null-field parsing failure; private-scoped `owner-reconcile-02`
rebound only this reservation to the live native process. `finish-01` later
verified that process exited, checked original bytes/results offline, and removed
only its exact reservation. No second Flash write or successful-OTA replay.

The preinstall watched paths were unchanged. Installation audit records the
authorized SU SEGGER history/config update and a changed PowerShell startup
sampling file at the previously documented path. No reviewed launcher invokes
PowerShell; process attribution of that concurrent cache change remains UNKNOWN,
not an inferred authorization or cleanup target. All controllable outputs and
owned reservation updates/removal stayed project-local; no external cleanup.

Owner may inspect the repaired MCU check page now; visual feedback remains
pending, not independent acceptance or an OTA PASS. Do not automatically check,
start OTA, publish channels or create deltas. The current baseline is 3.3.44;
the old 30341 -> 30342 -> 30343 matrix was not executed and cannot be reused as
forward updates. Existing candidates and original failures remain intact.

#### Owner-Requested Forward Candidate 3.3.45

The owner now confirms that the installed 3.3.44 check-update page is normal.
This is owner visual feedback for the reported layout/text defects, not an OTA
PASS or independent acceptance. The owner requests one new upgrade package in
the backend only, retaining all Stable/Beta and delta generation/enabling actions.

Codex root owns this bounded APP-COMPANION-01 follow-up on primary main, starting
at `af383fadc17374de3c2ef5aab45059b5bb7c7a9f`, freshly matched to remote main.
Prepare **3.3.45 / 30345** with identical product functionality to 3.3.44; only
the firmware release version/notes and these operational records change.
App 1.0.88+114 is unchanged. The forward test baseline is **3.3.44 -> 3.3.45**,
not the superseded 3.3.41/42/43 sequence. Prior immutable assets are preserved.

Entry evidence under `.cache/ota-ui-20261121/`: `keyring-read-06` lists all
E-Track Releases including drafts (two entries, no pagination remainder), and
`keyring-read-07` checks all E-Track tag refs; neither reserves 3.3.45.
Existing CI registration retains its immutable backend collision checks; no
manual Admin API/login, deployment or credential change is allowed. No active
device/index lock was present. `candidate45-preflight-01` verifies the root and
controlled output paths before edits. `.trellis` is absent in this checkout;
the current project contracts and existing task record remain the applicable
workflow, without introducing a new task system.

`candidate45-tests-01` passes all 90 existing original-Admin/candidate regressions.
The actual configuration passed the component planner: firmware required with
version code 30345, App 1.0.88+114 not required, channelPublished=false and
automaticDeltas=false. This local self-test does not claim a formal build or OTA.

Status: CANDIDATE_DELIVERED / OWNER_PUBLICATION_AND_OTA_PENDING. Source
`38560f467144f4d7c43479a1a436287d3b4f3fe0` is pushed to main. Formal CI
`44917879986` passes checks and firmware; App is skipped. All product sources
are unchanged from the installed 3.3.44 source `4d8c1bb1`; only version metadata
and operational records differ. Firmware log has 641 warning lines and zero
error lines. The existing native verification, upload readback and private-key
cleanup stages pass; no additional backend download was performed.

`keyring-logs-14` preserves the original CI logs; `candidate45-receipt-01` checks
the source/run/version binding and automatic receipt. Registration is `ok=true`,
`state=ready`, `assetsRegistered=2`, `channelPublished=false`, and
`productionApproved=false`, release ID:
`fw_9d4829678bebc41c91383f8a0a964da704a38e852edd1c35961bd49f47df4cb3`.

| Artifact | Bytes | SHA-256 |
| --- | --- | --- |
| Target App image identity | See CI source proof | `a4b1b2a5cee58883c7048710999fc3e6eb51eb2e97c34f421a0fb601ebd3adaf` |
| Full ETU | 303728 | `28958f208776c6237616cc86e76297e28495e6ce40da41e513be4a23bd8d06d4` |
| Recovery | 634388 | `288279f26a3168db0a15c8f797bca00924707b11ea667f06b37839bfa4a9ec8e` |

Next owner action: publish **3.3.45** to Stable and generate/enable exactly the
**3.3.44 -> 3.3.45** delta, then inspect the OTA interface on the existing
3.3.44 device. No agent login/Admin API, channel or delta mutation, deployment,
J-Link/ADB operation, check/OTA trigger or reminder reset was performed. The
device remains on its previously verified baseline until the owner's upgrade.
Do not claim this candidate delivery as an OTA PASS; real progress, reboot
identity, history and diagnostic consistency still need the owner's observation.
An intentionally small version-only delta may complete quickly; no animation
delay is introduced to prolong the progress screen.

Output audit: reviewed launcher defaults and child environments keep controllable
Git files, logs, test fixtures and temporary/cache files under the project.
Manual edits touch only the four scoped tracked files plus the ignored thin
test/receipt wrapper; candidate operations reuse the existing Git/CI adapter.
No local PowerShell, external SDK install, credential write or external cleanup.
An initial inline-shell quoting error made no file output; the existing guarded
route was used instead. A board-only mixed-EOL diff warning was fixed by
normalizing only this turn's rows, preserving all unrelated historical bytes.
The audit is path/environment review, not machine-wide process IO tracing.

#### Full Upgrade Candidate And One-Command Entry

Owner requests another MCU candidate for a full OTA test and a reusable one-command
version-only App/MCU delivery entry. Root owns this bounded follow-up from current
main `f2b44a2a0317763132028fc28573e842cebd7755`. Target the next unoccupied MCU
version, expected 3.3.46; do not infer that the owner has already installed 3.3.45.
Stable/Beta and delta operations remain owner-only. For this test, the owner
should publish the new target without an enabled matching delta, and verify
that the selected package kind is full before upgrading.

Reuse decision: the existing original-admin-candidate workflow already performs
the formal build, signing, byte verification, upload and unpublished registration.
The tracked original_candidate.py is an APK verifier, not a version/push entry;
the current task's qualified Git/CI wrappers are private, source-bound steps.
Add only a thin tracked CLI and Windows batch launcher using standard Git/gh and
the existing output guard. No replacement builder, uploader, backend client or
credential provisioning. The entry changes only the selected version file,
rejects dirty/diverged main and occupied drafts/tags, binds its push/CI receipts,
and offers read-only continuation after interruption. It does not run a device
test, publish a channel, generate a delta or claim OTA success.

Implementation is LOCAL_PENDING: `release_candidate.bat mcu|app` uses the tracked
`Tools/ota/release_candidate.py`. It stages exactly one version file, checks the
commit's parent/bytes, sends a normal non-force main push, and waits for the
source-bound candidate workflow and its completed registration/signer receipt.
`--dry-run` does not mutate source; `--resume <result.json>` only observes the
original source. A pending source or active owner blocks a new release.

`oneclick-tests-01` passes 21 offline entry tests and 90 existing candidate tests.
The new offline suite is also in the candidate workflow's credential-free checks.
No local Flutter/Gradle/firmware build or SDK installation is introduced. The
only gap this thin entry fills is version editing and Git/CI orchestration;
formal builds and backend ingestion are still the existing implementations.
Next: deliver the tool/docs, then exercise it for the requested full-test MCU
candidate without changing the App version or touching the installed device.

Tool source `b944fdca` is delivered on main. First real entry preserved a GitHub
GET transport EOF in `.cache/candidate-release/20261121T160030Z-2d8286aa`.
It stopped in PREFLIGHT with no version edit/commit/push. Standard gh did not
inherit the Windows system proxy, while the existing qualified CI adapter uses
that same configured loopback proxy. The bounded fix reads the existing system
proxy and passes it to child processes only when no explicit proxy environment
variable exists; no system settings or credentials change. This is a host-route
failure, not a package/MCU/OTA failure, and its original receipt is preserved.

Second real entry (`.cache/candidate-release/20261121T160744Z-0b35b56e`) reaches
the version edit but stops at diff-check before staging/commit/push: isolating
global Git settings removed the project's required core.autocrlf=true. The exact
source-bound edit is restored to its original 3.3.45 content, with the failed
receipt and before-version bytes retained; no 3.3.46 asset/build existed to retry.
Pin the same per-command autocrlf option as the already-qualified Git adapter.
Add an actual isolated Git/index CRLF test, since pure mocked command tests do
not qualify host Git conversion behavior. These host-route failures are not
firmware defects; there is no skipped or overwritten candidate version.

#### One-Command Delivery Verified And Owner Success Report

2026-11-22 local date: the tracked entry is delivered on main, including proxy
and real-Git CRLF qualification. `oneclick-tests-03` passes **24 entry tests and
90 existing candidate tests**. Final tool source before the version-only release
is `73eef39480fd9c29866489b8a219428a35cc297b`.

The actual one-command MCU invocation succeeds end-to-end. Receipt:
`.cache/candidate-release/20261121T162320Z-26ffba75/result.json`, phase DELIVERED.
It changes/commits exactly `Tools/ota/original-admin-release.json`, producing
**3.3.46 / 30346**, source `1eb1b52b2ff4eb4b317047ff580256e05e8fd2e7`.
Formal CI **44924357926** succeeds and the source-bound original receipt confirms
two verified assets, state ready, channelPublished=false and
productionApproved=false at registration. Firmware logs contain 641 warning
lines and zero error lines. App is skipped and remains 1.0.88+114.

Release ID: `fw_9719d26f71e7bc268c78176935c6b6c9802fcc00ec1beb0b151537d7a0d66fd1`.
Target image SHA-256: `7fe4b594aaa257d5249cc9d222dc2c6256ea20772cf2a9f47f6b7e1b6986e927`.
Full ETU: 303729 bytes, SHA-256
`96fef3368bfacd93a5283e7fa1511c7f88bd4e7b677326b955e3a1f941e2c6ab`.
Recovery: 634388 bytes, SHA-256
`d81e36ff447442d23839aad1cd7a51fbdc7434e1e263d51c53406cac2b52ba65`.
No additional backend package download or physical device operation. The
terminal handle was unavailable on later inspection, but the persisted DELIVERED
receipt and closed owner lock establish completion; no invocation was replayed.

The App command's actual online dry-run also passes:
`.cache/candidate-release/20261121T171041Z-cfa711fe/result.json`. It selects
1.0.89+115, but does not edit, commit, push or build it. App's new CLI path has
offline tests and real preflight, not a newly executed App release. Do not
produce an extra App merely to claim an end-to-end test.

The owner reports "upgrade succeeded". Record this as OWNER_SUCCESS_REPORTED,
not as a new agent observation. Target version, full/delta kind and origin were
not specified; clarification is pending. Do not infer a current installed
baseline, current channel state, or independent acceptance from the build
receipt. Do not reflash/repeat the successful OTA or require USB merely for logs.

Remaining scoped validation: correlate existing upgrade history/diagnostics with
reboot identity, true progress, origin, elapsed time and result; observe automatic
discovery/notification without opening App or manual checking, map/global popup
and Later without an install; verify lifecycle recovery and notification versus
actual control-session readiness, especially recurring Bluetooth timeouts;
exercise diagnostic persistence/filtering/search/complete exports and bounded
retention. Use the owner's App-exported logs first. Logging alone does not prove
Bluetooth repair; the historical watchdog cause remains undetermined. Independent
acceptance remains distinct from these self-tests and owner feedback.

Output review: all scoped source/docs/Git changes and controllable tests/logs/
caches remain inside the primary root; test temporary directories are owned and
contained. No PowerShell, new SDK, global Git/proxy/credential setting, device
tool or backend manual operation was invoked. Original host failures and receipts
remain intact. This is output/environment review, not machine-wide IO tracing.
