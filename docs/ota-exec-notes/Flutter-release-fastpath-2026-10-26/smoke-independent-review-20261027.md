# P35 Smoke Remediation: Independent Root Review

## Disposition

Reviewer: original root responsibility, 2026-10-27; no product implementation
in this review. No blocking product findings in the bounded remediation.
This is a lightweight independent source/original-CI review under execution
contract section 0, not formal P3-5 acceptance or post-fix device execution.

| Issue | Decision | Limit |
| --- | --- | --- |
| P35-SMOKE-UI-01 | DECIDED: software remediation review PASS. Five async feedback sites and shared helper address the recorded Overlay failure; deferred regressions and full host tests pass. | No post-fix Android UI observation; no release APK/EXE build. |
| P35-SMOKE-LOG-01 | DECIDED: existing host-tested complete-file route satisfies the requested 1200-byte UTF-8 integrity oracle. No new logging product code is required for this bounded gap. | Does not recover historical clipped logcat, qualify Android retrieval, or establish P99/throughput/P3-5. |

## Bound Inputs

Base: `18f6b3d3af0c24b1ce81573700cd61005b7c530e`.
Reviewed source: `50130043967456db7dc8f559b97016c52ba69893`.
Branch: `dev/flutter/p35-smoke-followup-20261027`.
Six changed files: two product UI/helper files, three tests, one task record.
No service/BLE/firmware/dependency/workflow delta. Product files in the delivered
worktree equal the reviewed commit; `git diff --check BASE SOURCE` exited 0.

Implementation record, read-only input:
`D:/github/my/E-Track/.cache/p35-firmware-20261027/.cache/p35-flutter-followup-20261027/docs/ota-exec-notes/Flutter-release-fastpath-2026-10-26/smoke-remediation-20261027.md`.
The final local section remains uncommitted; it was read but not modified.
The earlier committed part is available via `git show 50130043:docs/ota-exec-notes/Flutter-release-fastpath-2026-10-26/smoke-remediation-20261027.md`.
This review is also local/uncommitted, pending authorized integration. Neither
record is claimed published to main.

## Review And Evidence

The page checks mounted after asynchronous completion and supplies its own
context to safeSnackbar. The helper rechecks that context on the scheduled frame,
suppresses covered/transitioning/background delivery, and uses ScaffoldMessenger
with a mounted, same-Messenger Scaffold check instead of GetX Overlay lookup.
Existing service callers retain root-context fallback. No blanket exception
suppression was added. Existing Material SnackBar presentation replaces the
page's prior top/icon GetX presentation; foreground feedback remains tested.

Thirteen deferred real-button cases exercise successful download with/without
the page, covered route, failed/cancelled downloads and check/cleanup/export/share
feedback. Eight helper cases cover root fallback, no GetX navigator, delivery-time
disposal/navigation, background/missing dependencies and unrelated-error propagation.
The review checked shared helper callers and the service ownership boundary.
These tests do not constitute native phone observations or prove every possible
navigation queue sequence; no new blocker was established in the actual scope.

Read and independently compared three generations of original CI evidence:

| Run / attempt | Source | Ubuntu pass/skip/fail | Windows pass/skip/fail |
| --- | --- | --- | --- |
| 40509082166 / 1 | ad58a1b9 | 786 / 16 / 8 | 767 / 35 / 8 |
| 40510986837 / 1 | 491de8b3 | 802 / 16 / 3 | 783 / 35 / 3 |
| 40513386721 / 1 | 50130043 | 805 / 16 / 0 | 786 / 35 / 0 |

Final run: https://github.com/Eitan-S-23/E-Track/actions/runs/40513386721.
Both final jobs have successful conclusions in the archived GitHub response;
six runner commands per host exited 0, no timeouts, analyze reports no issues,
and candidate-profile tests separately passed 8/0/0 on each host. Full test
counts were recomputed from terminal raw-log lines, not copied from the handoff.
Flutter 3.47.8 / Dart 3.13.7; framework
`737ba8f885dc774b53b442759999a312c9461e4e` on both hosts.

Six ZIP hashes/sizes match the archived API artifact metadata. Forty-six retained
extracted members match their ZIP bytes and inventories; the original red logs
contain the actual `_downloadFirmware` / `Overlay.of` failure. No new download,
remote query, dispatch, or full test rerun was performed. Archived remote metadata
is the source for these historical run conclusions, not a claim of a fresh API poll.

Final log oracle on both hosts reports 1200 UTF-8 summary bytes, five envelope
records/two producer lines, six rejected damaged variants and missing-input
rejection. The test executes actual OtaLinkStats -> record -> finish/export ->
existing Python CLI, checks prefix/extracted bytes and hashes, verifies disabled
capture, and checks immutable snapshot bytes after close. The common unwrapped
SHA-256 is `bb9d11524e9a4e1c258cd5cc26eec1f9b45309b66b8f8eec3706f7b553c79222`.
The test explicitly uses not-completed and asserts no performance/acceptance claim.
Snapshot files were temporary CI fixtures; this review evaluates their original
test execution/assertions, not a separately retained snapshot binary.

SDK regeneration is explicit, not mislabeled source immutability: CI binds its
analysis_options exclude additions and two Windows plugin registry/CMake updates.
They do not exclude lib/test or change the reviewed product files. After restoration
Ubuntu is clean; Windows has only generated_plugin_registrant.h EOL drift, with
no semantic/untracked changes. The review's first offline check incorrectly
required clean=true on Windows and failed before writing a result. Its output
and correction are retained in `.cache/p35-smoke-review-20261027/review-attempt-01.txt`.
The corrected check allows only that named EOL case and preserves all original CI
records. This was a reviewer-check defect, not a product failure or a new CI run.

Reproducible offline evidence check:
`python -I -S -B -X utf8 .cache/p35-smoke-review-20261027/review.py`.
Executed exit 0; result and SHA-256 input inventory:
`.cache/p35-smoke-review-20261027/result.json`.
The command preserves the existing result; do not rerun into the same output.

## Remaining Work And Authority

No new implementation repair is requested on this batch. Root owns the next
bounded build/observation plan. Standard release-mode Android APK and Windows
EXE remain NOT_RUN, as do post-fix phone observation and formal P3-5/P5. A
separately authorized nonpublishing standard build is the next build-gate action;
development checks do not authorize `build.yml`, publishing or installation.
Shipping/reinstall version and signing identity must be handled under existing
rules when that concrete artifact is prepared, not silently treated as unchanged.

Phone validation should target the repaired async feedback, not replay the
completed 30289 -> 30292 upgrade. The last retained MCU state is 30292 from the
historical smoke; this review did not read or change the board. Formal ten
disconnect recoveries still require their original dependencies, admitted forward
assets, exact APK/configuration, original-file retrieval route and finite plan.
File capture remains an explicit diagnostic opt-in, not enabled in the standard
APK by this patch. The earlier first-check failure root cause and reconnect
history remain unresolved historical observations, not silently fixed by UI work.

## Write Audit

Active writable root: `D:/github/my/E-Track`. This review creates only this note
and `.cache/p35-smoke-review-20261027/` (offline script, first-check failure note,
result and final audit). Paths were normalized and ancestor reparse checks passed
before writes. All shell calls used cmd with explicit cwd; Python used -I -S -B.
No PowerShell, local Flutter/Gradle, SDK/cache download, Git index/ref write,
commit/push, external controlled output, device operation or cleanup occurred.
Other worktrees and their originals were read-only. The implementation's 821-file
historical preservation audit remains its prior observation; this review does not
claim to have independently re-executed that unrelated whole-device inventory.

## Authorized Standard Build Follow-Up

The user explicitly authorized preparation and execution of a nonpublishing
standard APK/EXE build after the review above. This section supersedes the
standard-build NOT_RUN status only; no device/OTA authority was granted.

Root prepared an exclusive worktree under
`D:/github/my/E-Track/.cache/p35-standard-build-20261027/source` and branch
`dev/flutter/p35-standard-20261027`. Commit
`53c6a804beac4d7bd045845ec1338674f03e2826` changes only pubspec version
`1.0.62+88` to `1.0.63+89` as required for a rebuilt app. Product lib/test,
firmware, dependencies and workflow bytes still equal reviewed `50130043`.
The original implementation worktree, uncommitted handoff and root originals
were not modified. No mainline merge, push or release occurred. This is root
build preparation, not a new product fix or independent hardware acceptance.

The authenticated GitHub account was verified as Eitan-S-23. One scoped push
triggered development checks, and one explicit `build.yml` dispatch requested
standard builds. The dispatch preserved the previous P35 settings:
`release_application_id_suffix=.p35acceptance`,
`release_ota_link_profile=adaptive-v2-candidate`, and the existing credential-free
P41-test firmware latest endpoint. `publish_release=false`,
`replace_existing_release=false`, no release tag. Diagnostic file capture remains
disabled; this is not a new diagnostic APK or a claim about negotiated BLE state.

| Run / attempt | Outcome |
| --- | --- |
| 40519432070 / 1, development checks | Ubuntu 805 pass / 16 skip / 0 fail; Windows 786 / 35 / 0; candidate checks 8 / 0 / 0 each. Both jobs successful. |
| 40519548574 / 1, standard build | Android release APK and Windows release EXE successful; analyze and full tests passed on both hosts with the same respective counts. |
| 40519548574 / 1, publication jobs | Deploy GitHub Pages SKIPPED; Create GitHub Release SKIPPED, including its Cloudflare steps. |

Standard run: https://github.com/Eitan-S-23/E-Track/actions/runs/40519548574.
Development run: https://github.com/Eitan-S-23/E-Track/actions/runs/40519432070.
Original full console logs, API/dispatch/status receipts and four downloaded
artifact ZIPs are under `.cache/p35-standard-build-20261027/records/`.
The two standard and two development archives match the API size/SHA-256 digests.
Standard artifacts expire 2026-11-10; required bytes are already retained locally.
No failed build or blind rerun was needed.

Warnings remain explicit. Counting emitted lines containing `warning:`,
`##[warning]`, or Kotlin `w: file:` in the final per-job console gives Android 26
and Windows 3, plus one runner-image notice in Detect changed paths. These are
occurrences, not 30 distinct defects. They include Gradle/AGP/Kotlin deprecation,
seven plugins requesting SDK 36, a keystore-format warning and Actions/Node
notices. Analyze found no issues. Build jobs/tests did not fail; this is not a
zero-warning qualification, and no toolchain/dependency change was folded in.
Negative-test diagnostic strings are not counted as compiler failures.

Vendor-tool offline verification reused the installed aapt/apksigner and JDK 17;
no local build or SDK installation was performed. APK signature verified with one
signer, SHA-256
`9e9b89c5e7fdc802b1fe71806a988a866db49cd988a739caeee56cb69f3df579`.
aapt confirms `com.wen.gaia.gaia.p35acceptance`, version `1.0.63+89`, and no
debuggable flag. ARM32/ARM64 compiled libraries contain the intended endpoint
and candidate-profile literals. Windows PE is x64, and the EXE bytes match the
same EXE in the intact Windows runtime ZIP.

Local outputs under `.cache/p35-standard-build-20261027/received/`:

| File | Bytes | SHA-256 |
| --- | --- | --- |
| ble-monitor-android.apk | 47429928 | 040c5ca12f428c1a42e6c2fbcdfeff47ac361497e8a0f128e3c5d45818339e32 |
| ble-monitor-windows.zip | 20516722 | 03054399ef9af4049fc3db6c117360affb84eb29ae4e2da0520c1e10b5980e60 |
| ble-monitor-windows.exe | 93184 | 4f5baa77906abb288f108da82fce518c169f7cccd159e82bf431cbf1db3f365d |

Use the Windows ZIP as the complete runtime package; the small EXE is not a
standalone distribution. Original verification stdout/stderr and the structured
result are retained in `records/signature.*`, `records/badging.*` and
`artifact-verification.json`. The host did not launch either application.

Write audit for this follow-up: controlled local writes are confined to
`.cache/p35-standard-build-20261027/`, this appended note, and the common project
Git objects/new owned worktree index/ref/reflogs/upstream metadata under `.git`.
The existing GitHub CLI credential and vendor tools were read-only inputs;
credentials stayed in memory. Home/AppData/temp/CLI cache and Java output paths
were redirected inside the project. No local PowerShell ran. Git hooks retained
their checks; explicit commit text avoided AI-message generation, and the hook
notification key was empty. Hosted build SDK/Gradle/cache/temp/signing activity
is that of the expressly authorized standard workflow, not a local installation.
Final artifact/source/receipt audit: `.cache/p35-standard-build-20261027/final-audit.json`.

Remaining: installation and targeted post-fix UI observation are NOT_RUN and
require separate device authority. Formal P3-5/P5 remains NOT_RUN. Do not replay
the completed 30289 -> 30292 OTA or label this build as a successful device test.

## Lifecycle Independent Review, 2026-10-28

Original root, lightweight source/original-evidence review under execution
contract section 0. Reviewed source `a2e4b1af025594fd239fe42367fd25e7780bf35f`
on `dev/flutter/p35-smoke-followup-20261027`, against `50130043`. The implementation
worktree and its local concentrated handback were read-only inputs. No new role,
product implementation, CI run, build, phone/MCU operation or network query.

Disposition: **NOT PASS for P35-SMOKE-LIFECYCLE-01**. The query-only defect has
credible red/green evidence and the repair isolates query/download ownership,
but the new phase filter introduces the blocking END-retry regression below.
P35-SMOKE-UI-01 and P35-SMOKE-LOG-01 retain their earlier bounded conclusions.

### P35-SMOKE-LIFECYCLE-01-R01: Paused END Retry Cannot Resume

DECIDED: P1 required product fix, introduced by this batch. This is a source-level
control-flow finding, not a newly executed Flutter test or observed phone fault.
All following anchors are in the reviewed source's Flutter package:

1. `lib/ota/ota_ble_transport.dart:1445` marks END started and calls
   `onApplyBoundary(true)` before writing the END frame.
   `lib/services/ota_service.dart:2666` consequently changes the service phase
   from `transferring` to `applying`; this precedes successful END acknowledgment.
2. With no acknowledged background owner, an inactive/paused event still calls
   `_safeBackgroundFallback` (`ota_service.dart:321`). Operation kind remains
   `transfer`, so it pauses the actual transport even in `applying`.
3. For the supported v1 path, `ota_ble_transport.dart:973` creates `_resumeGate`
   and stops the no-progress clock. If the first END response times out, the
   handler at 804 permits the next retry. That retry waits without a timeout in
   `_waitIfPaused` at 720/995, before sending another END or registering its ACK
   waiter.
4. On resumed, the new condition at `ota_service.dart:1898` rejects `applying`,
   clears only `_foregroundPaused`, publishes a snapshot and returns. It never
   releases the transport gate. Repeated resumed or explicit resume calls take
   the same branch. The new `stale()` phase check at 1929 also excludes this
   still-live END owner from recovery.
5. The transfer Future and busy owner can therefore remain pending indefinitely,
   despite foreground return; the stopped budget cannot expire the gate wait.
   The normal task UI cannot cancel it (`canCancelTask`, lines 185-187, excludes
   applying/END-started). A late ACK after the timed-out waiter was removed does
   not release `_resumeGate` either.

This is not an objection to excluding completed/query owners, and not an
invitation to cancel a possibly applying MCU. It violates the original handoff's
requirement to preserve END, real-transfer safety and owner completion. The
existing fake `_onEnd` at `test/ota/ota_service_upgrade_test.dart:5323` answers
immediately; the added 14 cases exercise HTTP or DATA/discovery/INFO timing, not
this END-loss/pause/resume path. Their green result does not cover this case.

Preferred minimal direction: make recovery eligibility describe the live paused
transport operation, including a still-pending END exchange, rather than equating
it with the UI's `transferring` phase. Align entry and post-await stale predicates.
Retain owner epoch, cancellation generation, transport identity, link generation,
strict characteristic/INFO checks and owner retirement. Do not globally allow
queries to resume, blindly unpause without recheck, re-enable user cancellation
after END, reset the budget or fabricate target success. If treating END as a
separate recovery stage, it must have an explicit bounded outcome and preserve
the existing END/reboot identity contract, not silently drop the gate.

Executable oracle for the original implementation owner:

- Reuse the real service/transport and existing fake peer with background owner
  denied (v1 or negotiated v1 fallback). Let DATA finish and reach the actual
  first END boundary; do not set service phase/private pause flags by hand.
- Suppress the first END response (or model a lost first END), deliver inactive
  then paused, and return to foreground both before and after its ACK timeout.
  Allow the peer to acknowledge a valid retry. Assert the operation settles
  within the existing bounded retry/identity route, not just that the UI unpauses.
- For a still-connected matching peer, preserve strict recheck and END sequence
  semantics; success still requires the final target version/full raw SHA.
  If the peer/link is gone, require the existing safe bounded failure instead of
  a permanently busy owner. Preserve no-false-success and non-cancellable END UI.
- Include repeated resumed, a late first END ACK and cancellation/owner-retirement
  isolation. Keep all current query/download/real-transfer regressions unchanged.
  Preserve a failing run on a2e4b1af and a repaired green development batch on both
  hosts. No new physical OTA, APK install, firmware build or cloud mutation needed.

Next owner: original Flutter implementer, within the already authorized lifecycle
scope. Return the minimal repair and deterministic regression to this root. A
different evidence-based resolution is acceptable if it proves the gate always
settles in the above reachable sequence. No additional scope approval is needed
for this same-batch defect; no new acceptance/freeze agent is requested.

### Evidence Reconciled

Git comparisons independently confirmed: only service/test changed from 50130043;
final service equals 28860cf8, old-service comparison fec94361 equals the 50130043
service, and red/green test blobs are identical
(`4507eb393bfac65275601b32c7dc8a565dbdf677`). Delivered service/test match final Git
objects after checkout EOL normalization. `git diff --check 50130043 a2e4b1af`
exited 0. The implementation has only its already-reported local document changes.

| Original run / attempt | Source | Ubuntu pass / skip / fail | Windows pass / skip / fail |
| --- | --- | --- | --- |
| 40599854488 / 1 | fec94361 | 807 / 16 / 20 | 788 / 35 / 20 |
| 40600996231 / 1 | a2e4b1af | 827 / 16 / 0 | 808 / 35 / 0 |

Raw terminal anchors: red Ubuntu 23748, Windows 24353; green Ubuntu 23306,
Windows 23900 in their respective tests.log. Both green analyzers report no
issues; candidate entry tests separately report 8/0/0 each. Reports bind all-scope,
checks-only execution, exact source, attempt 1 and unchanged lockfile per host.
SDK: Flutter 3.47.8 / Dart 3.13.7, framework
737ba8f885dc774b53b442759999a312c9461e4e. Generated input deltas remain recorded;
Windows restored status includes its declared EOL-only generated header, not a
semantic source edit. Console truncation is not absence of full raw logs.

The red raw logs have 20 actual error entries per host: eight earlier lifecycle
tests, eight new HTTP timing/sentinel cases and four successor-owner cases. The
two added transfer late-callback tests were already green, as the handback states.
The expanded concurrent reporter does not print a unique green heading for every
fast case: it repeats another running test's heading as the count advances. Do
not invent 14 separately named green log anchors; identical source registration,
unfiltered full-test command, aggregate counts/unchanged skips and zero failures
support the suite result. This does not establish the missing END regression.

All 34 extracted members in `.cache/lifecycle-matrix-{red,fixed}/` match their
inventories and the bytes of the four original ZIPs in the implementation
worktree. ZIP SHA-256 values match the handback. Archived status responses bind
red failure and green success to their exact commits and jobs (green Ubuntu
122528780655, Windows 122528780779). No fresh remote-status claim is made.

### Review Boundary And Audit

Root ran no new Flutter tests; R01's deterministic executable reproduction is
NOT_RUN and belongs in the next implementation batch. Existing green CI is valid
development evidence, not a waiver of the source-level regression. The phone's
original check-click root cause remains unproved. Formal P3-5/P5, ten disconnect
recoveries and release/device qualification remain outside this review.

This review appends only this existing root note, local/uncommitted and pending
authorized integration. Active write root is D:/github/my/E-Track; the exact note
and ancestor chain passed host_io.checked_output before editing. All shells were
cmd with explicit cwd; offline JSON/hash/Git checks used Python -I -S -B. No new
cache, temporary file, index/ref, commit/push, external controlled output, move or
deletion was selected. Final audit retains the pre-existing note prefix and checks
the 45 snapshotted implementation records/originals unchanged. Two intermediate
read-only audit attempts stopped on an absent NOT_RUN timeout field and a wrong
assumption about per-test reporter headings; neither was a product test, wrote
files, changed originals or justified rerunning CI.

## R01 Re-Review, 2026-10-28

Original root, same lightweight independent source/original-evidence review under
execution contract section 0. No production/test implementation by this reviewer.
Reviewed source: `392158684d2c2e9492e6140ca41e86bb7f118efc` on the original
`dev/flutter/p35-smoke-followup-20261027` branch, against `a2e4b1af`.

DECIDED: **bounded independent software review PASS** for
P35-SMOKE-LIFECYCLE-01-R01, closing the remaining software blocker in
P35-SMOKE-LIFECYCLE-01 on this source. No new in-scope blocking findings.
This supersedes the preceding NOT PASS only for the repaired source and this
software scope; the historical finding and red evidence remain intact.
P35-SMOKE-UI-01 and P35-SMOKE-LOG-01 retain their earlier bounded results.

### Repair And Regression Oracle

The production delta is confined to ota_service.dart (8 additions, 4 deletions).
`_hasLiveTransferRecoveryOwner` at 1875 requires a busy transfer operation and
either transferring or applying with the actual transport's endStarted flag.
Resume entry at 1904 and stale evaluation at 1933 consume the same predicate.
This admits the still-pending END exchange without reopening query/download or
retired-owner recovery. Epoch, cancellation, transport identity, lifecycle and
strict link/characteristic/INFO guards remain unchanged. END OK changes phase to
waitingReboot before awaiting disposal, so that completed exchange is excluded.
No transport/protocol, retry/timeout/budget, firmware, dependency, build setting,
logging default or user-cancellation gate changed.

Eight added tests use the real OtaService/transport and an existing peer extended
only to drop or defer processing of the first END. Previous assertions are intact.
The original END validation/sequence/durable/content checks now live unchanged
in _handleEnd. A failing test's onClose cleanup occurs after the six-second
settlement assertion; it cannot turn the timeout into PASS.

- Four real END cases cover baseline and adaptive-candidate negotiated v1 fallback,
  with foreground return before/after ACK timeout and duplicate resumed. They
  require one BEGIN, two ENDs using the same sequence, zero ABORT, strict resume
  INFO and fresh target verification (version 20900 and full raw SHA `62` x 32),
  settled owner and completed phase. Normal cancellation remains disabled.
- Null discovery and changed-link cases require bounded safe failure, no extra
  INFO/retry END or false success, and retained package. Physical ABORT remains
  suppressed when the old link generation is no longer valid.
- Deferred first END processing produces a late ACK after actual peer apply.
  It does not release the paused retry or establish success. The foreground
  source-identity recheck safely rejects the changed identity, as before; this
  test does not claim automatic successful recovery of an already-applied image.
- Closed-owner late ACK and repeated resumed events cannot revive the owner,
  issue new BLE work or publish completion. This preservation case already passed
  on the red source; the other seven cases were real red discriminators.

The preceding query/download/successor-owner/real-transfer negatives remain in the
unfiltered full suite. Candidate-profile checks additionally select the two new
adaptive fallback tests by the existing name filter; their count is now 10, not 8.

### Original Execution Evidence

Red source `abce1f536638be1e2d6b83a426fc0faf53022774` has the unchanged a2e4b1af
service. Its test blob is identical to the repaired source:
`9d7a822534dbff994dafe8fff54a8c1084da1981`. Delivered service/test match final Git
objects after checkout EOL normalization. Only these two files differ from
a2e4b1af; `git diff --check a2e4b1af 39215868` exits 0.

| Original run / attempt | Ubuntu pass / skip / fail | Windows pass / skip / fail |
| --- | --- | --- |
| 40640015806 / 1, abce1f53 | 828 / 16 / 7 | 809 / 35 / 7 |
| 40642081269 / 1, 39215868 | 835 / 16 / 0 | 816 / 35 / 0 |

Independently read raw terminal anchors: red tests.log Ubuntu 24065, Windows
23776; green Ubuntu 23951, Windows 24058. Each red host contains exactly seven
R01 error records reporting `TimeoutException ... Future not completed` at the
six-second assertion. Both green analyzers report no issues; candidate_tests.log
line 168 reports 10 passed on each host. All six green runner commands exit 0
without timeout. Red candidate commands remain NOT_RUN, not assumed PASS.

Reports and original SDK output bind all-scope, checks-only runs, attempt 1,
Flutter 3.47.8 / Dart 3.13.7, framework
737ba8f885dc774b53b442759999a312c9461e4e. Per-host lockfiles are unchanged and
diagnostics complete. Recorded generated-toolchain deltas remain explicit;
restored Ubuntu is clean, Windows retains its declared EOL-only generated header
with no semantic/untracked delta. This is not a byte-clean Windows assertion.

The four R01 ZIP hashes/sizes match archived GitHub artifact API records, including
exact source, run, branch and artifact IDs: red Ubuntu 12795520439, red Windows
12795510903, green Ubuntu 12795873786, green Windows 12795523255. All 34 extracted
members match both ZIP bytes and `.cache/lifecycle-r01-{red,fixed}/inventory.json`
under the implementation worktree. Archived status responses confirm the red
failure and green success; green jobs are Ubuntu 122662286557 and Windows
122662286268. No new API query/download or CI execution occurred in this review.
The implementer's broader 124-original audit is retained as its observation;
this re-review independently checks the affected R01 originals, not a duplicate
of unrelated completed archive campaigns.

### Limits And Write Audit

This is independent evaluation of real development execution, not a newly run
Flutter test or formal hardware acceptance. The phone's original check-click
cause remains unproved. No new APK/EXE was requested, built or installed; old
standard artifacts do not bind this changed source. Native Android/device
observations, formal P3-5/P5, ten disconnect recoveries and release qualification
remain outside this PASS. No replay or fresh identity read of retained 30292.

This turn appends only this existing root note, local/uncommitted pending
authorized integration. Writable root D:/github/my/E-Track and the exact output's
ancestor chain passed host_io before editing. All commands used cmd with explicit
cwd; offline inspection used Python -I -S -B. No product/test edit, new cache or
temporary output, Git index/ref update, commit/push/merge, external controlled
write, network/device action, move or deletion. The final audit checks the old
note prefix and 47 snapshotted R01 originals/metadata/implementation inputs remain
unchanged. The original implementation agent's uncommitted closeout documents
were not modified. No remaining action is required from that agent for R01;
main integration, builds and any device work remain separately authorized tasks.

## Authorized Integration And Device Follow-Up, 2026-10-28

The current user explicitly authorized the proposed subsequent integration and
real-device verification, asking root to continue until genuine human action is
needed. This is not permission for production publication, clearing App data,
replacing Boot, downgrading the retained MCU or changing unrelated worktrees.
Root is the sole operator; writable root remains D:/github/my/E-Track.

Initial remote reconciliation: main remains 91fed6bc and the reviewed branch is
392158684d2c2e9492e6140ca41e86bb7f118efc. No standard build exists for that source.
The existing endpoint-bound 40590849204 binary is from 28860cf8 and excludes R01.
The dirty root and implementation records remain preserved, not merge inputs.

Finite next batch:

1. Build the reviewed source once through build.yml, publication/replacement
   false, adaptive-v2-candidate and the already-selected isolated test latest
   endpoint. Keep the existing application ID/signing; archive actual outputs,
   both host checks, warnings, endpoint and signature evidence before install.
2. Prepare a clean project-local integration worktree, reconcile all inherited
   changes and existing acceptance originals, preserve commit ancestry and run
   required integration checks. Do not label branch delivery as main delivery.
3. Near actual use, start the existing bounded private USB route, identify the
   same phone/package and preserve existing App data. Install only after source,
   artifact and current-package checks. Prepare original file/logcat collection
   before requesting any required in-App action; no automatic UI taps.
4. First device observation is query/lifecycle smoke on the retained 30292 target,
   not another firmware upgrade. Validate real INFO/NO_UPDATE/error/lifecycle
   evidence without a fabricated transfer, stale failure or pending owner. Any
   necessary user connection/query action is requested only at this ready point.

No MCU reset/flash or new OTA is planned by this batch. Existing 30289 -> 30292
success/readback remains historical input; formal P3-5/P5 and ten-disconnect
execution still require their admitted immutable criteria/asset plan. Failure or
uncertain install/dispatch is reconciled before retry; original logs are retained.
Owned USB workers have finite deadlines and verified closure. New receipts,
host directories, artifacts and integration tree use .cache/p35-integration-20261028.
The thin run.py adapts the existing standard-build receipt wrapper and reuses
host_io; no replacement build, BLE or archive framework is introduced.

### Exact-Source Candidate Build And Integration Preparation

Run 40652822499/1 on 39215868 completed success. Android job 122696839641
and Windows job 122696839760 passed analyze/full tests/build/signature/upload;
Release and Pages jobs were skipped with no executed steps. Raw full test totals
are Android 835 passed/16 skipped (line 24925), Windows 816/35 (line 24479),
zero failures. Analyze no-issue lines are 837/442. Flutter 3.47.8 is bound by
the actually restored framework cache key; no separate Dart version observation
is invented for this standard workflow.

Actual APK: com.wen.gaia.gaia, 1.0.62+88, release ARM64/ARMv7, 47429900 bytes,
SHA-256 4231372ada6f25829bded58070359f697016cf772b7fb20f0b93078e0691a404.
Vendor verification confirms one signer, the existing fixed certificate
9e9b89c5e7fdc802b1fe71806a988a866db49cd988a739caeee56cb69f3df579.
Both AOT libraries contain the chosen permanent test endpoint and candidate
profile. Windows EXE is AMD64, 93184 bytes, SHA-256
b94bdb2d1ec7f49ea958b3db5bb3b287bd7aacabd471e1f1d141298d7d0c9764,
matching its bundle member. Bundle SHA-256:
cc8c35034a5b8761e7c26d8caa79be6ba53e766212648a15e790c8b03a7f4e02.

Original API ZIPs: Android 12800183867,
a4f85780e17a3f4fd8e2d0e7c273bfcb7dfd32dbe518f32e9fc2494860ce7589;
Windows 12799888545,
42b1c3d98385cf4bdb212340c1ecbf550245e02f1c0de5e15b55883132184b0b.
Lengths match the API. Local vendor/inventory receipt is
.cache/p35-integration-20261028/artifact-verification.json under the root.

Warnings remain disclosed: Android has 21 explicit Warning lines (10 wrapper,
10 build, one JKS notice), one Kotlin jvmTarget deprecation and two nonfatal
file-watcher exceptions. Both hosts have two Node runtime deprecations and a
Node-20 Actions annotation; Windows has no explicit compiler warning/error.
The successful job is not a warning-free or production-signing qualification.

The owned integration branch integrate/p35-followup-20261028 starts at the exact
reviewed source, with main 91fed6bc an ancestor. No product code was rewritten.
The bounded inherited product/tool/workflow diff passes whitespace checks.
An unfiltered check also reports historical byte-exact log whitespace and two
old board CRLF lines; these originals are preserved rather than normalized.
Initial sparse worktree population used no-checkout, then read-tree after output
preflight; it completed clean. A quoted --jq status lookup yielded the literal
filter, not a status result; the later unfiltered lookup supplies the actual
completed run and does not redispatch.

Four previously local handoff/review notes are now integration inputs without
modifying their originals. followup-originals-20261028/inventory.json binds 42
unchanged originals, including all six lifecycle red/green ZIP pairs, their
inventories/status/artifact metadata, and this candidate's build/vendor evidence.
This is portable original-evidence delivery, not a new formal acceptance bundle.
The full APK/EXE and API ZIPs remain in the project-local artifact archive.

Main integration and installed-device observations are still pending at this
entry. Existing firmware state, frozen evidence, completed cards, baseline
shipping defaults and production gates remain unchanged.

### Integration Resume Checks

The interrupted staging receipt records exit 0. All 42 archived originals match
their inventory lengths, SHA-256 values and staged Git bytes. A token/private-key
signature scan, including ZIP members, found no matches. The single new trailing
blank line in this review note was removed; original evidence remains byte-exact.
Remote main was reconciled again as 91fed6bc before integration.

The first commit attempt was rejected by the existing global secret-pattern hook;
HEAD remained 39215868. Its six matches are four shell environment-variable
references and two public Android debug-keystore defaults in the original CI
console. They are not exposed signing credentials. After checking those exact
matches, the retry uses the hook's documented per-command GIT_NO_SECRET_CHECK=1
exception for this evidence-only commit; conflict/debug checks remain enabled.
The failed receipt is preserved under records/integration-commit-01.* in the
project-local integration area. No build, download, install or OTA was repeated.

### Main Delivery And Corrected Test-Package Authorization

Controlled fast-forward delivered e41bca268a5f69ac84bee18d4f392a6e2890a17d to
remote main. Main checks completed successfully: build.yml 40659783155,
firmware-build.yml 40659783133, governance 40659783120 and Cloudflare checks
40659783056. APK/EXE analyze/test/build/upload steps executed; Release and Pages
were skipped. Firmware production, rehearsal and binding jobs were skipped.
These are integration checks, not new device or formal acceptance observations.

Before any installation, root reconciled the prior installed test App as
com.wen.gaia.gaia.p35acceptance, versionCode 89, APK SHA-256
040c5ca12f428c1a42e6c2fbcdfeff47ac361497e8a0f128e3c5d45818339e32. The earlier
40652822499 candidate instead has the unsuffixed application ID and versionCode
88. It was not installed and cannot be used to update that test App. Its original
build result remains valid only for its actual identity, not for device admission.

After root disclosed the mismatch, the user explicitly approved rebuilding for
the original .p35acceptance App with a versionCode greater than 89, leaving the
ordinary App untouched. The exclusive candidate/p35acceptance-20261028 branch
changes only pubspec version to 1.0.64+90 plus this record; product logic remains
the reviewed 39215868 implementation. This version change is not a main delivery.
Use build.yml with release_application_id_suffix=.p35acceptance,
release_ota_link_profile=adaptive-v2-candidate, the same permanent isolated test
latest endpoint, publish_release=false and replace_existing_release=false.

Before data-preserving replacement, verify both host results and actual APK
application ID/version/signature/endpoint, then inspect the same phone and both
installed package identities. Preserve old test data and the ordinary App.
Only query/lifecycle smoke on retained MCU 30292 is planned; no uninstall, data
clear, forced downgrade, MCU flash/reset, new OTA or cloud mutation. New build
receipts use records/p90-* and artifact/phone outputs use p35acceptance-90 under
the existing project-local integration area. Prior receipts remain immutable.
