# Shared Agent Records

Latest update checks, 2026-11-25: UPDATE-CHECK-ISOLATION,
MAIN_DELIVERED / CI_CHECKS_PASSED / CLOUD_DEPLOYED / LIVE_VERIFIED, Codex root.
Owner's explicit follow-up authorizes migration 0020 and matching Worker/Admin/
Public deployment of source 703fea1f8df8621870d802610a9c99d4357ab147; successful
Actions 45476279470 follows already-successful exact-source checks 45468883658.
Only the pending migration is applied. Four daily limits are independently 5;
the existing account detail returns both budgets and installed-client APP aliases.
Owner/static/auth readback passes, with 11 served files matching the commit and
original settings, runtime/schedules, four channels and 69 delta records preserved.
No new App/MCU version/build, phone/device operation, channel/delta or credential
change. Bluetooth cooldown, firmware cache/dedup and APP daily-marker behavior
remain unchanged. Original TLS/harness failures and dependency warnings remain.
Evidence: .cache/update-check-isolation-20261125/rollout-01/receipt-01 and
keyring-cloud-live-601/603. Self-tests/live checks are not independent acceptance.
Older pending documents are excluded from this scoped record delivery. See
[the rollout record](../ota-exec-notes/OTA-COMPANION-2026-11-20.md#independent-update-check-rollout-2026-11-25).

Latest background recovery, 2026-11-25: COMPANION-BACKGROUND-WAKE,
MAIN_DELIVERED / CANDIDATE_DELIVERED / PHONE_VERIFICATION_NOT_RUN, Codex root.
Owner confirms Bluetooth ON during the new failure; later OFF was testing.
Development 283c65d756e3db434f16c72370e8c222e888fc0b is merged to main source
629155427508e67be843a8f84d3296b03907e13a, App 1.0.95+121. Original-signing
parent CI 45433637395 / Trace 45434018855 both pass APK/Windows and register
rel_trace_android_v1_0_95 automatically; two App assets are R2-verified.
APK SHA256 487b04f58ac8df6a4802b3e72abbb81838141c7252dd255a6633e15cf937dfe6,
49636885 bytes; original package/signer/backend/BLE V2/inventory checks pass.
Android build retains 10 warning lines/zero errors, Windows zero/zero; firmware skips.
Recovery retains the service through existing capped backoff without a wake
lock and requests guarded sticky recreation. Four-attempt windows and the
60-minute maximum cooldown remain; cache/dedup/OTA ownership are unchanged.
Both-host development CI 45421424363 / 45421702392, 149 native tests and debug
APK pass. Historical OEM queue delay remains unknown; this is not real-phone
verification. Main merge/push is explicitly owner-authorized; original pending
documents and unrelated Dialplate/tests are preserved. Later main 258c7051 /
916b9022 changes the separate MCU task; the entire App tree remains identical.
First observer timeout is preserved; second observes the same source, no rerun.
No device/manual cloud
operation, additional agent, channel publication or whole-card independent PASS.
Evidence .cache/companion-wake-20261124/delivery/ and the existing
[companion note](../ota-exec-notes/OTA-COMPANION-2026-11-20.md#bluetooth-on-background-recovery-2026-11-24).

Latest owner closeout, 2026-11-23: OWNER-CLOSEOUT-2300,
OWNER_VERIFIED_PASS / CANDIDATE_DELIVERED. The owner
confirms normal Bluetooth operation at 23:00 Shanghai and both follow-up lists:
automatic discovery/cross-page prompt/Later/history/logs, plus account-name and
logout/relogin terminal-deduplication phone checks. These checks are closed,
not requests for further clarification, remediation or another OTA. Previous
failures and cooldown observations remain historical evidence; policy unchanged.
MCU 3.3.52 source ba3d5cc44344bfa0c8a2747949789d0380390be8 is DELIVERED in CI
45184334373: two verified full/recovery assets ready, 641 warnings/zero errors.
Original receipt: .cache/candidate-release/20261123T132806Z-d8ae7394/result.json.
Owner confirms backend receipt; installed version and later channel/delta state
are not inferred. Formal whole-card independent acceptance is not claimed.
Owner authorizes scoped main delivery of these three new record blocks only;
older pending edits remain untouched. Receipt:
.cache/owner-closeout-20261123/delivery/result.json. No App/MCU rebuild,
backend/device operation or new independent review is requested.
This entry supersedes earlier pending labels for the confirmed checks and 3.3.52
build while preserving older records. See [owner closeout](../ota-exec-notes/OTA-COMPANION-2026-11-20.md#owner-confirmed-functional-closeout-and-3352-delivery-2026-11-23).

Latest owner-directed work, 2026-11-23: MCU-TEST-3352, Codex root,
IN_PROGRESS / LOCAL_PENDING. Owner requests another version-only MCU candidate
through the unchanged one-click entry from main 7c9aae6c / metadata 3.3.51.
Qualified document/credential adapter is rebound to fresh evidence; prior 24/7
self-tests and successful Git-proxy route reused. Firmware functionality, App
1.0.94+120/reconnect policy, channels/deltas and device state unchanged. Existing
diagnostic review and six pending documents preserved. No replay, extra agent,
backend deployment or manual publication. Evidence .cache/mcu-test-3352-20261123;
see [new candidate](../ota-exec-notes/OTA-COMPANION-2026-11-20.md#owner-requested-mcu-3352-candidate-2026-11-23).

Latest original-log review, 2026-11-23: COMPANION-ARCHIVE-2101, Codex root,
LOCAL_PENDING / ORIGINAL_ARCHIVE_REVIEWED. Owner export has 2022 valid contiguous
rows, CRC/count/metadata checks pass; process-death loss remains unknown. At
20:19:49 an automatic background check returns NO_UPDATE. Three later real
reconnections reach CONTROL_READY but source=reconnect is skipped for the
one-hour minimum_interval; earliest fresh-query eligibility is 21:19:49, not
the ordinary next-day 08:19 schedule. 3.3.48 -> 3.3.50 full upgrade records
post-reboot identity success in 60.209 s, preserving an earlier ERR_BUSY failure.
Four recent CONNECTING failures remain separate; no Bluetooth-stability fix or
new 3.3.51 query/OTA is inferred. Analysis only, no check/device/backend/code/
build/commit/push operation. Evidence .cache/companion-log-20261123-2101; see
[archive review](../ota-exec-notes/OTA-COMPANION-2026-11-20.md#owner-diagnostic-archive-review-2026-11-23).

Latest owner-directed work, 2026-11-23: MCU-TEST-CANDIDATE, Codex root,
CANDIDATE_DELIVERED / OWNER_PUBLICATION_AND_OTA_PENDING. Owner reports successful 3.3.48 -> 3.3.50
compatibility upgrade and device binding, and cancels the old delta-policy
remediation. These OWNER_REPORTED outcomes supersede the pending choice and
upgrade/binding statements below, without fabricating a hardware readback.
The supported one-click entry delivers version-only MCU 3.3.51 / 30351,
source ddc0a638, first-push CI 45176505831. Original-entry 24 and adapter seven
offline tests pass; firmware has 641 warning lines, zero errors. Full/recovery
are R2-verified, ready/unpublished, with App skipped. A connection-reset push
failure is retained; one reconciled same-SHA push and original --resume complete
delivery, without another bump/build. Six older pending documents are preserved.
App 1.0.94+120, migration policy, credentials/backend/channels/deltas and device
state remain unchanged. UID is the chip's factory 96-bit identifier, formatted
as 24 lowercase hex characters, not a BLE/account/App identifier. Evidence:
.cache/mcu-test-20261123 and .cache/candidate-release/20261123T124217Z-28d10bbe;
owner publishes 3.3.51 and generates/enables exact 3.3.50 -> 3.3.51 if testing
delta. No device operation or actual/independent OTA acceptance. See [test candidate](../ota-exec-notes/OTA-COMPANION-2026-11-20.md#owner-requested-mcu-test-candidate-2026-11-23).

Latest compatibility feedback, 2026-11-23: LEGACY-DELTA-SELECTION, Codex root,
LOCAL_PENDING / EXISTING_FULL_ONLY_LIMIT_CONFIRMED. Real metadata confirms one
ready/enabled/retained 3.3.48 -> 3.3.50 delta, matching base/target raw SHA and
9916 bytes versus 304580-byte full. Stable and both runtime delta flags are
correct. Two retained manual uid-v1 checks nevertheless select full because
App, Worker and Public deliberately enforce full-only compatibility migration.
This is a code-policy limitation, not failed publication or proof of hardware
delta incompatibility. No product/gate change, account check, channel/delta
mutation, download or device action. Coordinated backwards-compatible App/
backend delta migration would retain signed package/base/target and reboot
identity checks; the owner's policy choice is still pending. New local record
only, not main delivery. Evidence .cache/legacy-delta-20261123/inspect-01.
See [selection diagnosis](../ota-exec-notes/OTA-COMPANION-2026-11-20.md#compatibility-delta-selection-diagnosis-2026-11-23).

Latest resource work, 2026-11-23: RESOURCE-QUOTA-DISPLAY, Codex root,
CODE_ON_MAIN / ADMIN_LIVE_VERIFIED. Product c503165f, exact-source CI
45157043450 (603 Worker/314 browser tests and three typechecks), Admin-only
deployment 45160962404. Local broader host 645 and 60 contracts also pass.
Real owner/source/11 assets/API/UI verify all 11 supported account balances;
Workers/Pages remaining 99680, R2 A/B 999552/9997153 and estimated Standard
storage remaining 8.729 GB-month. Actual R2 period is 2026-10-28 to 2026-11-28
UTC, with complete 27-day samples. Account totals stay separate from project
metrics; hard limits, included usage and invoice estimates remain distinct.
CPU is a per-invocation limit; unsupported complete DO storage stays unknown.
Desktop/mobile/200% text pass with reachable Close and zero page errors.
Worker/Public identities/runtime, settings, 19 migrations, four channels and
63 delta identities are preserved; no credentials/channel/delta/device actions
or additional agent. Existing warnings and failed offline composition evidence
are retained. These are implementation/live checks, not independent acceptance.
Evidence .cache/quota-display-20261123; six older pending documents are preserved
through scoped closeout rather than staged wholesale.
See [quota implementation](../ota-exec-notes/OTA-COMPANION-2026-11-20.md#cloudflare-account-quota-display-2026-11-23).

Latest resource resolution, 2026-11-23: RESOURCE-QUOTA-PERMISSION-01, Codex root,
LOCAL_PENDING / BILLING_READ_CONFIRMED / QUOTA_IMPLEMENTATION_PENDING. Owner
corrects account-owned versus personal-token selection; exact CF-CI-01 reads at
08:32 UTC now return 200 for subscriptions and account settings. R2 Paid/Teams
Free Base and 2026-10-28..2026-11-28 UTC period are observed, not a Workers Paid
or remaining-quota assertion. No token replacement, cloud mutation, deployment,
App/firmware build or device action. Evidence: .cache/resource-quota-20261123/permission-02/result.json.
Earlier failure originals and pending content remain; this is capability testing,
not a completed quota implementation. See [the successful retest](../ota-exec-notes/OTA-COMPANION-2026-11-20.md#personal-token-billing-read-confirmed-2026-11-23).

Latest resource probe, 2026-11-23: RESOURCE-QUOTA-PERMISSION-01, Codex root,
LOCAL_PENDING / BILLING_READ_NOT_CONFIRMED. Owner-reported e-track-ci permission
update is tested using the existing CF-CI-01 input: subscriptions GET remains
403; token verify is 200/active. A separate account-settings read has a transport
failure and is not classified as denied. Saved Billing Read/account scope/input
identity need an owner redacted-summary check, not a new token or repeated GET.
No cloud/configuration/credential/channel/device change or quota repair claim.
Evidence: .cache/resource-quota-20261123/{permission-01,verification-01}/result.json.
See [the quota permission probe](../ota-exec-notes/OTA-COMPANION-2026-11-20.md#resource-quota-permission-probe-2026-11-23)
and [CF-CI-01 capability](credential-registry.md#billing-permission-update-probe-2026-11-23).

Latest rollout, 2026-11-23: ACCOUNT-BACKEND-ROLLOUT, Codex root, CODE_ON_MAIN /
APP_CANDIDATE_DELIVERED / BACKEND_LIVE_VERIFIED / OWNER_PHONE_DEVICE_PENDING.
Owner-requested exact cc8039e4 backend deployment 45076742719 succeeds once
from workflow main f2bb573c. Worker 788ecbc4, Admin 3831978c, Public 6049bb98
and owner/static/API readbacks verify actual sources/runtime. No migration replay,
configuration/credential/channel/delta/device change; mail/email-on revision 2,
5/5, schedules, four channels and 62 delta identities are preserved. Warnings
remain. Existing App 1.0.94+120 candidate is unpublished; Stable remains 1.0.93.
Phone installation/identity/terminal UI, real MCU UID/binding and remaining
background/global OTA/history observations still need the owner's final window.
One actual account/terminal and no bound device are returned. Existing 3.3.50 is
not rebuilt/reinstalled; check actual MCU before any compatibility OTA. Complete
App export first; USB optional for specific missing native/system evidence only.
No collector or independent acceptance. Earlier pending checkpoints are history.
Originals and scoped pending-preservation audit: `.cache/account-identity-20261123/rollout-*`,
`keyring-cloud-live-401/402`. See [the live rollout and final owner route](../ota-exec-notes/OTA-COMPANION-2026-11-20.md#account-backend-rollout-completed-2026-11-23).

Latest work, 2026-11-23: ACCOUNT-IDENTITY-01, Codex root, CODE_ON_MAIN /
APP_CANDIDATE_DELIVERED / OWNER_VALIDATION_DEFERRED. Main product source `cc8039e4`
fixes reactive username/email and installation-keyed terminal display/revocation,
preserving login history, distinct scopes, dialogs/scroll/logout and 5/5 quotas.
Flutter 45069815624 passes Linux 1059/16 and Windows 1007/68 (passed/skipped),
plus 8 candidate tests per host. Full original artifact digests/12 logs are
verified. Backend 45069818091 and main 45071318738 pass 575 Worker/308 browser
tests and three typechecks. Local 13 terminal cases pass; failed shared-IP fixture
isolation and an artifact-list EOF remain recorded, without weakened limits.
Automatic parent 45071318837 / Trace 45071476388 deliver App 1.0.94+120, original
APK/Windows, R2 readback and rel_trace_android_v1_0_94 unpublished. GitHub tag is
v1.0.94, not the backend release ID; native APK SHA starts 4b0729c5736e66e4.
Android has 10 build warnings/0 errors; Windows 0/0. Original observer timeout/
metadata EOF/tag-404 remain, with third same-run observation and formal audit;
no rebuild or asset overwrite. Full identities are in Identity Formal Candidate Delivered.
Firmware 3.3.50 and prior successful device/mail operations are unchanged.
Provider usage reads succeed; subscription HTTP 403 leaves account remaining
unknown. Admin/Public source remains 95470e8e at the 05:10 snapshot. Owner retains
backend/channel/delta/device actions and assistance stays last. Existing five
pending documents/1,150 untracked entries and dependency warnings are preserved.
Details: Identity Implementation And Development Checkpoint, implementation
contract and deferred owner route in the companion note; new controlled evidence
`.cache/account-identity-20261123/`. This is self-test, not physical acceptance.

Latest checkpoint, 2026-11-23: ACCOUNT-UX-LEGACY-01, Codex root, CODE_ON_MAIN /
APP_CANDIDATE_DELIVERED / BACKEND_AND_PHONE_PENDING. Product source
`dbcf94cf6424eec00e5fb0d8fae7140e82928ba2` is fast-forwarded and pushed to main.
Full Flutter 45055320407 passes Linux 1045/16 and Windows 993/68 (passed/skipped),
with 8 candidate-profile tests on each host. Complete dual-host artifacts and
12 raw command logs are verified. Backend 45055321435 passes 568 Worker/308
browser tests and three typechecks. The busy-search defect is fixed; its gated
regression and the earlier 16-case original are retained without another run.
App 1.0.93+119 is draft/tag-checked; automatic parent 45057066631 and original
Trace signer 45057226109 pass Android/Windows and original R2 candidate ingestion,
`rel_trace_android_v1_0_93`, unpublished. APK SHA-256 starts `95bdc67e7e2ea7e6`;
full asset identities are in Formal App Delivered, Backend And Phone Pending.
Windows has zero build warning/error lines; Android has 10 warnings, zero errors.
No firmware/duplicate App rebuild, backend deployment, mail/configuration,
channel/delta, phone or device operation. Owner retains all manual backend and
phone actions. Existing advisories, earlier failed receipts and the four-helper
loss remain recorded. Current details and exact compatibility-route constraints
are in Implementation And Development Checkpoint, Legacy Migration Implementation
Contract and the owner handoff in the existing OTA companion note. Owner first
deploys the pinned backend and updates the phone; prepare the observation route
before a real 3.3.48-to-3.3.50 full OTA. This is not physical/independent acceptance.

The initial same-day entry below is retained; its unexecuted-state statements
are superseded only by the actual checkpoint above, not by independent acceptance.

Latest work, 2026-11-23: ACCOUNT-UX-LEGACY-01, Codex root, IN_PROGRESS /
LOCAL_PENDING. Owner approves the consolidated interface/registration/legacy
migration repairs. Existing dev/flutter/ota-ui-20261121 worktree is synchronized
to current main 6073f443 without rebuilding it. Owner-reported registration/login
after reopening and password reset succeeded; earlier no-account/pending statements
below describe their dated checkpoints. Mail remains activated; no resend or
required-verification change. Firmware 3.3.48 lacks the UID protocol; the existing
formal 3.3.50 candidate is the proposed full-OTA migration target. No new App,
deployment, hardware action or acceptance yet. Shared UI rules and bounded
regressions are part of this batch; see Account UI And Legacy Migration Follow-Up
in the existing companion note. Preserve the disclosed four-helper loss and all
existing evidence. Root owns implementation, tests and authorized delivery; owner
retains phone actions, channel publication and actual OTA.

Current registration diagnosis: LOCAL_PENDING / INVESTIGATED_NOT_FIXED. Live
settings now require email verification (revision 2), no matching account exists,
and only the expired host-test code is retained. Scoped telemetry query succeeds
but yields no matching auth events; original phone request is unavailable. Four
offline tests reproduce stale-form/missing-code INVALID_PARAMETER and confirm
the supplied username/Foxmail/eight-character fixture are otherwise accepted.
App generic errors discard field details/requestId. Need only the owner's
observation of whether the form showed a verification-code field; no passwords.
No live business mutation/product edit/deployment. See Registration Failure
Investigation in the companion note and .cache/registration-investigation-20261122/.

Latest owner feedback: real SMTP test email received, delivery OWNER_CONFIRMED.
No code stored/used, no additional send or settings mutation. App registration,
reset and session-revocation checks remain pending; required email stays off.
Evidence: .cache/account-mail-activation/owner-inbox-confirmed.json. Local record/
support-tool changes and the previously disclosed cache-helper loss remain open.

SMTP live follow-up: REMOTE_ACTIVATED / SERVER_ACCEPTED / OWNER_INBOX_PENDING.
Owner local input succeeded; Pages-only Actions 45028304682 activates backend
95470e8e, no Worker/schema rebuild. Live owner/source/readiness/preservation checks
pass and one actual test email is SMTP-accepted. No confirmed inbox, registration/
reset flow or required-email switch. Local tools/records still pending commit.
Four old cache helper scripts were mistakenly overwritten and not restored;
incident paths and mitigation are in the SMTP Activated section of the companion
note and activation-audit.json. Historical receipts/product code are unchanged.

SMTP activation follow-up: Codex root, LOCAL_PENDING / INPUT_READY. Owner delegates
three-target mail configuration. Root configure-account-mail.cmd is ready; 26
offline tests and live read-only target/readiness preflight pass. Existing Pages
provider-only slots are supported; mailbox/code slots remain absent. Owner enters
sender/fresh code locally, then agent activates Pages and verifies actual mail.
No cloud write, send, build or commit/push in this preparation. Existing deployment
and phone-validation status below remains unchanged. See the current OTA companion
note, Owner-Assisted SMTP Activation Preparation, and .cache/account-mail-activation/.

Current work: ACCOUNT-RELATIONS-20261122, Codex root, REMOTE_DELIVERED /
MAIL_ACTIVATION_AND_PHONE_VALIDATION_PENDING. App 1.0.92+118 source 29d619ff is
original-signed and registered by Trace 45013457550. Parent 45013327189 lost its
post-dispatch receipt and remains failed; no duplicate request/build occurred.
Backend 95470e8e passes 535 Worker/297 browser cases and deploys in 45016534804;
live source/owner/list/readiness checks pass, only 0019 applied, runtime/four
channels/60 delta identities unchanged. Timestamped account/terminal/UID relations
and shared dialogs are delivered, not live phone acceptance. Mailbox code is
delivered but unconfigured; real mail and user steps are in ACCOUNT-EMAIL.md.
See Account Relationships And Unified Results in the current OTA companion note.

Previous follow-up: COMPANION-FEEDBACK-20261122, Codex root, ACCOUNT_MAIL_FEEDBACK_DELIVERED / MAIL_ACTIVATION_PENDING, source 3296c633.
Owner requests actual email completion and consistent App/Admin failure dialogs.
Account and adjacent feedback prompts now use the existing dialog components;
mail sender/domain and controlled real recipient remain missing owner inputs.
Source 599dc4a3 passes full Flutter 44995783785 (Linux 1007/Windows 955, platform
skips retained) and backend 44995837038. Local account/mail 21 and related browser
77 cases pass. App 1.0.91+117 formal APK/EXE and candidate delivery succeed in Trace
44996956524 / E-Track 44996846280; exact-source backend 44996846216 passes.
Backend 44997943728 is deployed and live-readback verified: unchanged runtime,
four channels and 60 baseline delta identities. Mail remains unconfigured and
no message/account was created. No MCU rebuild, phone/device action or channel
publication occurred. Evidence: keyring-cloud-live-116/119, keyring-logs-124/128,
keyring-status-126 and keyring-read-130 under .cache/ota-followup-20261122/.
Prior source/candidates/backend delivery and pending phone/device validation below
are preserved; no MCU, channel/delta or device action belongs to this follow-up.
Owner approved separate account-wide automatic/manual daily check limits of 5/5.
Login, binding, Admin account views, cloud admission and the MCU text-layout follow-up
have passed development self-tests and reached main `8a6dd4a3`. The owner's later
explicit deployment request is executed by Actions 44972869444: Worker/Admin/Public
now serve that exact source; only pending migration 0018 was applied. Live owner/
source/settings/5+5/anonymous-denial readbacks pass and four channels/59 delta jobs
are unchanged. Evidence: .cache/ota-followup-20261122/keyring-cloud-live-94/97 and
keyring-logs-98. Existing dependency/Node warnings remain, not silently repaired.
Latest App source `1a1c82fe` passes both hosts (`44965098761`); native/debug
`44963606753` and backend/293 Admin UI cases `44963616712` pass on unchanged native
and backend product inputs. Main backend/governance CI pass. App 1.0.90+116 formal
Windows/Android builds and ingestion pass in Trace run 44966121776; candidate
rel_trace_android_v1_0_90 is unpublished and not installed. MCU 3.3.49's R2 failure
is superseded by 3.3.50, source 91916e11469fce94282a9e1a0254048f4e4a9d7f,
CI 44970721130: ready/unpublished, two verified assets, 641 warnings/0 errors,
App skipped. Existing one-command entry completed; source 02241a0d also fixes
failure-time artifact retention (65 regression cases). Agent reconciled old objects
read-only after authorization; owner no longer needs to repeat that check.
The recommended firmware/App-first order was superseded by the explicit deploy-now
request, not by evidence of installation. App 1.0.90+116 and UID-capable 3.3.50
adoption remain unconfirmed; old App cloud requests now require login-capable App.
No channel publication, delta generation, phone update or device operation occurred.
See Account And Layout Batch in the existing task note. Prior 3.3.47 install
and 3.3.48 candidate evidence below remain unchanged.
Original owner ZIP, same-process post-OTA service stop finding, UI/check/history
scope and direct-install/two-candidate authority are recorded in
[the existing task note](../ota-exec-notes/OTA-COMPANION-2026-11-20.md#owner-feedback-follow-up-2026-11-22).
Main product source is `3802e85f0d46c25912bb5389366651a9d1c8927e`. Firmware 3.3.47
was registered as a candidate and is now installed, CONFIRMED and running.
Interrupted direct-install recovery `device/finish-01` completed in 50.907 s
without another Flash write; old BCB/configuration preserved and debugger closed.
Human UI/OTA checks remain; App final signing receipt was not re-queried during
recovery. Owner-requested 3.3.48 is now DELIVERED by the unchanged one-command
entry, source `5d81e6b9`, CI `44943905784`: ready, two verified assets, unpublished;
641 warning lines, zero errors, App skipped. Receipt is under
`.cache/candidate-release/20261121T195939Z-ea346b99/`. No 3.3.49, channel/delta or
device operation accompanied this candidate. Last verified device is 3.3.47.

Project-wide entry for all E-Track agents and components. Rules live in the
[collaboration contract](../agent-collaboration-contract.md), not in a task cache.
This index and its topic records are operational history, not acceptance inputs.

| Topic | Scope | Record |
| --- | --- | --- |
| COMPANION-ONECLICK-20261121 | DELIVERED / OWNER_SUCCESS_REPORTED_DETAILS_PENDING. One-command MCU entry actually delivers 3.3.46 source `1eb1b52b`, formal CI `44924357926`, two verified assets ready/unpublished at ingestion; App skipped. 24 entry + 90 candidate tests pass, 641 firmware warnings/zero errors. App online dry-run selects 1.0.89+115 without mutation/build. Owner reports upgrade success; target/kind/origin need confirmation, not another OTA. Background discovery/global popup/Later/recovery and history/log correlation remain open; no agent device or manual backend operation. Original transport/EOL failures preserved. | [Verified entry and owner report](../ota-exec-notes/OTA-COMPANION-2026-11-20.md#one-command-delivery-verified-and-owner-success-report) |
| COMPANION-FORWARD-345-20261121 | CANDIDATE_DELIVERED / OWNER_PUBLICATION_AND_OTA_PENDING. Owner confirms installed 3.3.44 check page. Version-only 3.3.45 source `38560f46`, formal CI `44917879986` PASS, ready/unpublished automatic registration with two verified assets; App skipped. Local 90 candidate tests pass; firmware 641 warning lines, zero errors. No device operation or extra backend download. Owner alone publishes Stable and generates/enables exact 3.3.44 -> 3.3.45 delta. Real OTA UI/progress/identity/history checks remain pending, not inferred from candidate delivery. | [Owner-requested forward candidate](../ota-exec-notes/OTA-COMPANION-2026-11-20.md#owner-requested-forward-candidate-3345) |
| COMPANION-CHECK-LAYOUT-20261121 | FIX_DELIVERED / OWNER_VISUAL_CHECK_CONFIRMED. 3.3.44 source `4d8c1bb1`, formal CI `44910534689`, automatic ready/unpublished candidate; App skipped. 74 UI/control/safety/menu tests and 115 complete-record/wire assertions pass. Owner-requested J-Link install completed once: full target hash, CONFIRMED 30344, normal runtime and preserved Boot/config/QSPI verified; native worker/lock closed. Flash plus readback 74.3 s; slow host GPIO-driven EEPROM work is a tooling limitation, not intrinsic EEPROM timing. Owner subsequently confirms the check page is normal. Old 3.3.41/42/43 assets unchanged; forward OTA test now targets 3.3.45, not a claimed completed first round. | [Corrected UI installation result](../ota-exec-notes/OTA-COMPANION-2026-11-20.md#corrected-ui-installed) |
| COMPANION-UI-HISTORY-20261121 | DELIVERED / OWNER_TEST_PENDING. P01/U01, per-device history and native lifecycle/journal are on main. App 1.0.88+114 and MCU 3.3.41: source `50b9af34`, parent `44893270196`, signer `44893376360`, automatic registration PASS. MCU-only 3.3.42 (`3dd630ff`, `44899719630`) and 3.3.43 (`b8ba677d`, `44901056840`) ready/unpublished; App skipped. Exact formal 3.3.41 installed once, full readback/CONFIRMED/healthy runtime and preserved Boot/config/QSPI verified; owner lock released. Self-tests are not independent acceptance; background timeout repair and phone OTA remain unproved. Owner alone updates phone and publishes 30341 -> 30342, then 30342 -> 30343. | [Final delivery and owner steps](../ota-exec-notes/OTA-COMPANION-2026-11-20.md#verified-delivery-and-owner-handoff) |
| COMPANION-DELIVERY-20261121 | Source/candidates delivered on main 145843da: original App 1.0.87+113 APK/Windows and GCC 3.3.39/3.3.40 succeed. confirm-01 finishes 3.3.39 installation without repeating Flash programming; original App/Boot/BCB and preserved configuration/QSPI verified. Latest observations LOCAL_PENDING: USB verifies original phone 1.0.87, live acknowledged link; passive MCU confirms 3.3.39 and 3.3.40 marked shown/DEFERRED. This can also arise from manual UI and does not establish global-popup success. Owner published channels/delta; no agent publication or diagnostic OTA/reset. Clarify first-popup absence versus repeated same-package suppression; physical acceptance remains open. | [Installed state and missing-popup diagnosis](../ota-exec-notes/OTA-COMPANION-2026-11-20.md#installed-state-and-missing-popup-diagnosis) |
| COMPANION-GLOBAL-PROMPT-20261121 | LOCAL_PENDING: current update offers now prompt on every stable MCU page, without recording/power suppressing visibility. Explicit consent and receiver safety remain; map Now releases its overlay, SD work blocks a second check/install, stale queued dialogs are rejected. Local changes above development `df294259` pass 72 host tests and incremental GCC App/Boot/simulator build (396 warnings, zero errors). No App change, new commit/push, release or device operation; old red/harness results retained. | [Scope and implementation](../ota-exec-notes/OTA-COMPANION-2026-11-20.md#global-update-prompt-follow-up) |
| OTA-COMPANION-20261120 | App-originated physical OTA PASS: owner-confirmed App 1.0.86 upgrades 30335 -> 30336 from the phone firmware page. Passive full readback matches the original backend 30336 bytes and unchanged Boot; current RTT confirms TEST_BOOT 30336, with initialized confirmed state and healthy advancing runtime. The agent's earlier USB install was cancelled by the owner; no retry or collector-driven OTA followed. Transfer timing/package kind and the device-originated entry are not newly measured; retain 30336 without downgrade/replay. Software source `cc439043` and original APK/EXE builds remain delivered; Admin 2ad213fa/77ec808f and all 16 live scroll checks remain delivered. Historical low-power/busy/WDT records are preserved, not reclassified. Whole-card acceptance remains separate. | [User OTA and verified target](../ota-exec-notes/OTA-COMPANION-2026-11-20.md#user-ota-completed-and-target-verified), [App remediation delivery](../ota-exec-notes/OTA-COMPANION-2026-11-20.md#app-remediation-delivery), [Admin delivery](../ota-exec-notes/OTA-COMPANION-2026-11-20.md#follow-up-delivery-completed) |
| JLINK-335-INSTALL-20261119 | User-authorized device installation complete: original CI 3.3.35 from `48ad9f03`, full raw SHA-256 `05d0b280cf2b0df09cff1b4f1bda15a7924d6b1cf44789997a9ac12eba43a55a`. App-only programming, unchanged physical Boot, confirmed state/storage, 25-second running checks and companion session pass. The device no longer retains 3.3.33. Pre-write host-check failure and startup WDT marker preserved; no observed repeat reset. No new OTA, rebuild, publication or whole-card acceptance. Documentation remains LOCAL_PENDING on main. | [Installation and audit](../ota-exec-notes/JLINK-335-2026-11-19.md) |
| COMPANION-INSIGHTS-20261119 | Main 7e088a08 is delivered. Original candidate 44529237716 and Trace signer 44529522207 pass: App 1.0.85+111 APK/Windows EXE/ZIP and MCU 3.3.36 full/recovery are registered, signature/hash and real owner/R2 readbacks verified. Reuse full development 44524540524 and native/debug 44524692240: Linux 958/16, Windows 906/68 (passed/skipped), 117 native with no failure/skip. GCC has 641 warnings and zero errors. Backend 44529237548 passes 501/273/60; deployment 44531533628 applies only 0017 and updates Worker/Admin/Public with unchanged runtime configuration. Real version details, linked App/Back and mobile layout pass; legacy metadata stays unknown. No channel promotion, delta generation, device operation or whole-card acceptance. | [Delivery](../ota-exec-notes/APP-COMPANION-01.md#candidate-and-backend-delivery), [live inventory](../ota-exec-notes/APP-ADMIN-UX-01.md#delivered-source-and-live-readback) |
| COMPANION-STABLE-ROLLOUT-20261119 | Owner-authorized continuation completes original staging Stable publication: App 1.0.84+110 / revision 60 and MCU 3.3.35 / revision 9. Only two selected deltas were added/enabled: 778654 bytes (98.40% smaller) and 8236 bytes (97.27%). Original generators, keys, Beta and 42 prior jobs remain unchanged; 44 jobs total. Source-bound CI reconstruction, signatures/R2 checks and Public patch downloads pass. Both full downloads now pass: the follow-up directly retrieves all 48718441 APK bytes and hash-matches them in 194.350 seconds; earlier timeout/partial evidence is retained. No full rebuild, backend redeploy or device operation. This supersedes the candidate-only handoff below for this batch, not whole-card acceptance. | [Rollout and evidence](../ota-exec-notes/APP-COMPANION-01.md#stable-rollout-completed-2026-11-19), [complete APK readback](../ota-exec-notes/APP-COMPANION-01.md#complete-public-apk-readback-2026-11-19) |
| COMPANION-FAST-20261119 | Main 48ad9f03 delivers bounded immediate/2/4/8-second recovery, Bluetooth-on wake, GPS-motion gate removal and E-Track module naming before the single startup reset. Full dual-host development, 107 native and 151 host/planner tests pass. Candidate parent 44441921617 and original Trace signer 44442089690 succeed: App 1.0.84+110 APK/Windows and MCU 3.3.35 full/recovery are built and registered. Real Admin/D1 and hash readbacks confirm exact source/run and available bytes. Local GCC/simulator: 743 warnings; CI GCC: 641 warnings; zero errors. No channel promotion, delta generation, physical operation or whole-card acceptance. | [Current record](../ota-exec-notes/APP-COMPANION-01.md#fast-reconnect-and-candidate-delivery-2026-11-19) |
| ADMIN-NOTIFICATION-SCOPE-20261119 | Main source 9e19f9d1 and Admin-only Actions 44437264265 are delivered: deployment 9c636437, unchanged E_TRACK_CI/runtime configuration. Backend 483 Worker/267 browser/60 contracts pass. Real owner notification 55 opens its correct firmware panel; source bytes and scope are verified, channels/delta identities preserved. Worker/Public/schema and publication are untouched. Older deployment entries below remain dated history. | [Deployment memory](../../CLOUDFLARE-DEPLOYMENT.md), [notification fix](../ota-exec-notes/APP-ADMIN-UX-01.md#firmware-notification-hotfix-2026-11-19) |
| APP-MAIN-CANDIDATES-20261119 | Owner-approved main App entry and 1.0.83+109 delivery integrate validated boot/icon/metadata source ab0ef2c5. Only explicit App version increments request original-signed candidates; ordinary App edits retain verification, duplicate versioned builds are skipped. Trace executor 12ff41fc accepts exact main history anchored at a377846c, whose complete App tree matches original 1.0.82 source a977c848. Original keys, MCU 3.3.34 and manual channel publication are unchanged. Host 65+8 and workflow YAML checks pass; original-signed builds/ingestion await this main push's automatic run. Owner handles later publication/deltas/phone; no device operation or whole-card acceptance. | [Workflow](../original-admin-candidates.md), [delivery](../ota-exec-notes/APP-COMPANION-01.md#app-main-candidate-migration-and-1083-2026-11-19) |
| CLOUDFLARE-DEPLOYMENT | Latest Actions 44531533628 deploys source 7e088a08 through unchanged E_TRACK_CI: Worker 84b2bec5, Admin 289c9cce, Public fbc0e58a. Only pending 0017 applies; named environment, runtime/preview configuration, Access, signing/generator references and schedules are preserved. Real owner, HTML/nine static assets, scoped inventory details and nested Back pass. Existing legacy records have unknown model/IP/quality data; no synthetic report or channel/delta mutation. Earlier feedback/deployment receipts remain historical originals in the root memory. | [Root deployment memory](../../CLOUDFLARE-DEPLOYMENT.md), [inventory deployment](../ota-exec-notes/APP-ADMIN-UX-01.md#delivered-source-and-live-readback) |
| APP-ADMIN-UX-01 | Feedback/navigation source 344abd6d passes dual-host App CI 44243311453 and backend 44243622777 (483 Worker, 261 browser), and is delivered with this bounded 25-file main integration. Original-signed 1.0.82+108 candidate a977c848 passes E-Track 44245598054 and Trace APK/EXE 44245743035; signer, signed capability, hashes and Android R2 candidate pass. New 107-to-108 delta 44250220531/1 is ready/enabled, revision 4: 2,439,333 bytes, 94.99% smaller than full; reconstruction, signature and full R2 readback pass. Only one new job, 38 total; original 37 jobs/four channels unchanged. No Stable/Beta promotion, phone/MCU operation or independent acceptance. USB is not a delivery prerequisite; actual phone upgrade/performance remains unmeasured. | [Feedback and delta delivery](../ota-exec-notes/APP-ADMIN-UX-01.md#feedback-and-delta-delivered-2026-11-18), [board](../../PLAN-OTA-EXEC.md#app-admin-ux-01) |
| PROJECT-WORKFLOW | All components, roles and worktrees | [Project workflow decisions](project-workflow.md) |
| PROJECT-MAIN-BOARD | Main is the shared progress entry; check actual branches and fresh remote state, preserve task evidence, synchronize milestone status and distinguish acceptance from delivery | [Current board](../../PLAN-OTA-EXEC.md) and [PROJECT-08](project-workflow.md#project-08-main-board-is-the-shared-progress-entry) |
| ADMIN-ACTION-CONTROLS-01 | Direct Sync and explicit pre-association cancel/retry feedback are now deployed in Admin a5afcc59 on source 28459a89, after regression and live source/API checks. The user already confirmed associated-run controls work. No real cancellation/restart was performed as a test. Original successful 43932189981/1, historical failures and withdrawal records remain untouched. | [Controls and preserved diagnostics](../../PLAN-OTA-EXEC.md#admin-action-controls-01), [current delivery](../ota-exec-notes/APP-ADMIN-UX-01.md#follow-up-delivered-through-actions-2026-11-18) |
| APP-COMPANION-01 | MCU 3.3.34 from main c85b39c6 is published to original Stable revision 8. Candidate Actions 44369848861 and governance 44369848829 pass; GCC has 641 warning lines and zero errors. The exact locally installed 3.3.33 image is registered as an unpublished base, not rebuilt or given a fabricated Actions identity. Delta 44372037247/1 is ready/enabled: 8066 bytes, 97.32% smaller than full. Actual R2 reconstruction equals the archived CI GCC target; Public selects/downloads that patch, retains full fallback and returns NO_UPDATE for 30334. All 40 original jobs and App/MCU Beta channels are unchanged. Earlier UI and startup-reset fixes are now delivered on main. No device operation, App update, Boot programming or protected-gate change in this publication. R01-R05/T01/T02 review remains bounded; D0-D5 and formal whole-card acceptance remain open, C1-C6 unchecked. | [Card](../../PLAN-OTA-EXEC.md#app-companion-01), [Spec](../ota-prompts/prompt-APP-COMPANION-01.md), [published result](../ota-exec-notes/APP-COMPANION-01.md#published-and-byte-verified) and [independent T01/T02 review](../ota-exec-notes/APP-COMPANION-01.md#independent-t01t02-review-3028a057) |
| PROJECT-CREDENTIAL-REUSE | All agents: discover existing credentials before requesting replacements; `e-track-ci` = `e-track-p41-ci`, protected locator and dated capability/scope evidence; no plaintext or production authority implied | [Credential registry](credential-registry.md) |
| PROJECT-TOOL-REUSE | Existing tools first, evidenced custom-tool exceptions and stopping unnecessary tool expansion; all agents | [PROJECT-04: group16 lesson](project-workflow.md#project-04-reuse-tools-before-replacing-them) |
| PROJECT-CANDIDATE-INSTALL | Prefer standard J-Link for candidate installation after state checks; reserve OTA for required observations, not redundant provisioning | [PROJECT-05: J-Link installation before OTA measurement](project-workflow.md#project-05-j-link-installation-before-ota-measurement) |
| PROJECT-USER-NOTIFICATIONS | Manual real mentions only for continued operations needing an out-of-chat action without a reply; chat authorization/decisions use the automatic completion reminder | [PROJECT-06: Mid-task reminders, not duplicate final notifications](project-workflow.md#project-06-only-manual-mentions-for-mid-task-blockers) |
| PROJECT-ACCEPTANCE-FLOW | Two owners, one canonical Spec, independent evaluation of existing originals and one final campaign; no automatic replay or separate freeze agent | [PROJECT-07: Evaluate existing evidence](project-workflow.md#project-07-evaluate-existing-evidence-before-repeating-work) |
| P3-4-PROGRESS | P3-4 operational status, next work, transfer/install timing and evidence; owner: Codex root, original card ownership unchanged; local evidence and remote delivery remain separate | [P3-4 project progress](../../P3-4项目进度表.md) |
| P4-2-IMPLEMENTATION | Independent implementation PASS; real legacy activation remains owned by the Cloudflare/D1 migration owner plus OTA reviewer, coordinated by root; configuration, Access and rehearsal gates remain open for their downstream owners | [P4-2 acceptance and activation handoff](../ota-exec-notes/P4-2-acceptance-2026-10-15.md) |
| P4-1-DEVELOPMENT-20261015 | Source/owner-decision record `c715ec6b00f8d9b06a820213da72421694b1e44c`, branch `dev/p4-1/unattended-20261015`; runtime code remains reviewed `18c4da4`. The owner approved the same check-only run `38859822756`; native binding qualification passed with three existing R2 objects verified and identical D1 count/channel observations. All five test environment secrets are configured, gate=false; 18-file original archive is linked in the task note. Implementation prerequisites are ready for the user-selected independent agent's consolidated review, exact target/descriptor approval and freeze. Protected real-key/canonical rehearsal/production-zero-effect and whole-card acceptance remain NOT_RUN, not extra pre-admission campaigns. No main merge, new dispatch, production/device operation or other card start; P41-AUDIT-01 remains attribution-unresolved. Branch handoff remains pending main integration after acceptance | [P4-1 native qualification and implementation handoff](../ota-exec-notes/P4-1-implementation-2026-10-15.md#native-qualification-passed-implementation-handoff-ready) |
| P4-1-ACCEPTANCE-20261016 | Independent P4-1-v1 PRODUCT_FAIL; bundle `7f014a8887dc79646ff392ee8cfa6a1ce2c9cf67` on `dev/p4-1/unattended-20261015`, frozen source `2d3daae4ac5441d3eb736b654c237ae53760067c`. One canonical run 38897470681 failed before the first R2 write: pinned Miniflare rejects Node-global Headers. Actual-key GCC/partial three-asset byte checks passed; business snapshots unchanged. Required fix P41-NATIVE-01 belongs to a separate implementation owner; exact invariant/regression oracle and original failed matrix are in the task note. Current relay has no implementation binding; no product edit, blind rerun or PR #27 merge. Evidence/records pending main integration, not whole-card PASS | [P4-1 failed staging acceptance and repair handoff](../ota-exec-notes/P4-1-implementation-2026-10-15.md#p4-1-v1-result-product_fail) |
| P4-1-NATIVE-01-REPAIR-20261017 | Implementation repair `5d4d07571451905ac156a1a721fa8b8ce764ed7c` on `dev/p4-1/unattended-20261015`: actual uploader codec red/green, host 41/41, pipeline 136/136, types and four PR workflows pass; native Linux suite 156/156. The 61-file development archive preserves both failures, originals and closing audit. Original independent reviewer owns consolidated review and successor/minimum-rerun planning. v1 PRODUCT_FAIL and frozen inputs remain unchanged; real native R2 writes/readback/ready still unverified, no staging/qualification/merge/production/device action. Pending main integration, not whole-card PASS | [P41-NATIVE-01 repair and source-bound CI handoff](../ota-exec-notes/P4-1-implementation-2026-10-15.md#source-bound-ci-and-return-to-the-original-reviewer) |
| P4-1-STAGING-PASS-20261017 | Independent v4 PASS, bundle `7f136c07505f56582640761944ab5add093252e4`, frozen input `b9d7d18c76e6495fbebf6758df6e4427e79e97b5`, branch `dev/p4-1/unattended-20261015`. P41-NATIVE-01 is resolved by successful real-key canonical run 38946949709, full three-asset R2 bytes, ready/idempotency and protected-business zero-effect evidence. v1 PRODUCT_FAIL, v2 HARNESS_FAIL and v3 ENV_BLOCKED remain immutable; two staging workflows total. P4-4 may consume the same originals under its own criteria; no new task, production release, gate unlock or device permission. This is the pre-merge evidence handoff for authorized PR #27 delivery, pending exact-head CI and integration at this record's commit | [P4-1 v4 independent staging acceptance](../ota-exec-notes/P4-1-implementation-2026-10-15.md#p4-1-v4-independent-acceptance-pass) |
| P3-4-SESSION-AUTH-20261013 | Approved minimum successor, one additional qualification, exact one-slot old-query cleanup and consumption; do not ask again for the same unspent scope. Local record on `acceptance/p3-4-v2-20261009`, historical execution source `02013607ca38eaf5cff0d5c4fc3de8259fbff916`; main integration remains separate | [P3-4 authorization and execution record](../ota-exec-notes/P3-4-v12-candidate-acceptance-2026-10-13.md#user-authorization-register) |
| P3-4-OFFLINE-CLOSEOUT-20261013 | Candidate-stage v15 PASS on `fcbace8b3f782714a139a77a12cb9305dbaef7cc`; local bundle `15a025b9c2690e864456a32fb2820422846fb85b` verified with 8838 exact raw blobs. One direct reference PASS reused, three criteria evaluated offline. Main delivery and P3-5/P5/release remain separate; old v11/v12/v13/v14 outcomes, trial5 deferral and 3/3 preserved | [Candidate-stage decision and local delivery](../ota-exec-notes/P3-4-v13-offline-acceptance-2026-10-13.md#candidate-stage-closure) |
| P3-4-LOCAL-CLOSEOUT-AUTH-20261014 | User-approved local P3-4 source/evidence/record/freeze-index chain in R and `D:/github/my/E-Track/.git`; explicit v14 metadata correction and subsequent necessary same-scope authorizations also granted. No repeated per-command/commit/agent approval. Excludes shared main worktree/ref/index, push/merge/CI/release, devices, unrelated or product/gate changes and global configuration edits; preserved history is not waived | [Recorded authorization and continuation](../ota-exec-notes/P3-4-v13-offline-acceptance-2026-10-13.md#candidate-stage-closure) |
| P3-4-GIT-DELIVERY-20261014 | COMPLETE for the candidate stage: user-authorized PR #26 merged as `17147e4265336945576ec218c8541079d4d8bf6c`, with App/governance/firmware CI on `719737d` and post-merge App CI successful. Main is in p34-final; shared work is byte-preserved on `archive/p34-root-before-delivery-20261014`. Same-scope authority needs no repeated question. Old local-only exclusions are historical; immutable failures/evidence, device pause, 3/3, no release and P3-5/P5 obligations remain | [Delivered result and authority](../ota-exec-notes/P3-4-v13-offline-acceptance-2026-10-13.md#delivered-result) |
| P34-HOST-CLOSE-01 | CLOSED by independent caller review on 2026-10-14: 20/20 affected checks pass; original 17/17 and 134/134 self-tests and incremental source bindings verified. Accepted primitive/18 tests unchanged. Reviewed bytes committed as `fcbace8b3f782714a139a77a12cb9305dbaef7cc`; no remaining caller repair, new device action or repeated permission request. A/B and v11/v12/v13/3-of-3 unchanged; v12 cause unestablished. Whole-card adjudication and main delivery remain separate | [Closed host lifecycle review and task-level handoff](../ota-exec-notes/P3-4-v13-offline-acceptance-2026-10-13.md#caller-integration-review-p34-host-close-01) |
| P34-V14-PREFLIGHT-01 | CLOSED under explicit user authority; pre-correction originals and rejected preflight preserved. A later native FC path error left v14 EVIDENCE_GAP with one reference EXECUTED PASS. Direct v15 corrects only seven filename spellings, reuses that anchor and passes the required 16 offline commands. No accepted-host regression, old failure rewrite, new device action or quota reset | [Preserved preparation failures and v15 closure](../ota-exec-notes/P3-4-v13-offline-acceptance-2026-10-13.md#candidate-stage-closure) |

| P3-8-ACCEPTANCE-20261026 | COMPLETE and delivered through PR #32 merge `e76691734c1fbc5220213353b8ba2a22dba05819` after development 40269055572, governance 40269473471 and standard APK/EXE 40269473445 passed. Independent P3-8-v5 has seven offline EXECUTED PASS criteria; bundle `1006c936b144151718cd5668db780502badb88d2`, freeze `2be0540feda1aec0ca001afb8456bb7bd82183ce`, with original ancestry preserved. Background/notification, explicit durable recovery, final 30289 identity and cleanup pass within recorded limits. Fixed signing and historical failures retained; no repeated OTA/APK download or Release. Production-fast qualification and P3-5/P5 remain separate | [P3-8 acceptance and delivery](../ota-exec-notes/P3-8-closeout-2026-10-26.md#delivered-result) |

| FAST-RELEASE-20261026 | Implementation candidate pending root build/independent review/main integration. Product source `57e6f064cec0c819aef8e348cd7690ca868c6a7e`, branch `dev/flutter/fastpath-backend-20261026`: explicit release-mode adaptive v2 selection, unchanged baseline/experiment/owner safeguards, actual negotiation/fallback logs/UI. Full dual-host CI 40290802257 and fixed-signed development APK CI 40291265828 PASS. Backend implementation/deployment/ready originals reconcile; current test channels stopped, target 30209 below retained 30289, host public queries edge-blocked. No backend product repair, mutation, standard APK/EXE, P3-5/P5 or production qualification claimed. Root owns exact-ref nonpublishing build and scoped real-backend/forward-asset preparation. | [Implementation and readiness handoff](../ota-exec-notes/Flutter-release-fastpath-2026-10-26.md) |

| P35-SMOKE-FOLLOWUP-20261028 | Supersedes the pending software-review state above: source `392158684d2c2e9492e6140ca41e86bb7f118efc`, branch `dev/flutter/p35-smoke-followup-20261027`. UI, file-route and lifecycle/R01 bounded independent software reviews PASS. Exact-source endpoint-bound nonpublishing APK/EXE run 40652822499/1 passes; root is preparing authorized main integration and targeted phone follow-up. Historical red results and immutable archives retained. No formal P3-5/P5, ten-disconnect or production qualification claimed. | [Root review and follow-up](../ota-exec-notes/Flutter-release-fastpath-2026-10-26/smoke-independent-review-20261027.md#authorized-integration-and-device-follow-up-2026-10-28) |

| P35-ACCEPTANCE-20261103 | Independent P3-5-v5 PASS: 18 required offline EXECUTED PASS criteria, source `54a860d122afba3c7361e0b77a50c29905f37ad2`, bundle `62a018aa9e84cc857b456686c9e6e1298155c9de`, local closeout `b7e88e1b34086b43c545e4cc204691c0e4f724ee`. Original 30309 ten-window group and separate 30313 zero-durable supplement remain distinct; v4 and earlier failures are preserved. User authorized PR/CI/merge delivery of `dev/flutter/p35-automation-20261029`; the PR merge receipt binds final main delivery. No new device test, P5/endurance or production release. | [P3-5 acceptance and delivery](../ota-exec-notes/P3-5-local-closeout-2026-11-02.md#mainline-delivery-authorization) |

| OTA-BACKGROUND-PROGRESS-20261120 | Development self-tests complete on `df29425926e3749ca90f1a9c21b829c45747d897`, branch `dev/flutter/ota-progress-background-20261120`; main integration pending. Real cleaner-kill/stale-notification/missing-link and later natural recovery captured. Creation-only bootstrap and MCU durable progress implemented; dual-host checks, 127 native tests, debug APK, 61 MCU/UI tests and GCC App/Boot/simulator pass. App 1.0.86 / finalized 3.3.38 retained, no new install/OTA/release/channel mutation. Root owns authorized main/candidate delivery; installed verification and standard App EXE remain open. | [Original observations, contracts and results](../ota-exec-notes/OTA-COMPANION-2026-11-20.md#natural-recovery-and-development-result) |

Add one row when a durable cross-agent handoff is needed. Link an existing task
note instead of duplicating its evidence. Include an exact source commit when the
record has not yet reached main; do not use a machine-private path as its only
address. The topic owner updates the same stable IDs and reports integration.
