# P1/P5 Non-Power-Cut Execution Sequence

Owner: current root / original independent reviewer. Active worktree:
`D:/github/my/E-Track/.cache/p35-integration-20261028/source`.
User-approved scope is recorded as OTA-DEC-018, record 18. This is local work
pending integration, not a frozen acceptance bundle or a release authorization.

## Current Disposition

- P1-7 remains locally accepted; no repeat of its key or startup campaign.
- P1-6 AUTO rows 01/02/04/06/08/09/10/11/12/13/14/18/19/20 retain their historical
  implementation PASS report, but independent raw-evidence closure is still open.
- P1-6 PHYSICAL rows 03/05/07/15/16/17 remain ENV_BLOCKED: no qualified timed
  electrical power-cut fixture. J-Link lamp behavior and USB reset do not qualify.
- P5-1 remains formally not dispatchable until the AUTO evidence and other
  necessary candidate/source/recovery preconditions pass. Its four combinations,
  same-group 30/30 and real four-hour requirements are unchanged.
- Once those prerequisites and P5-1 main paths pass, only ready non-power cases
  of P5-2 may proceed. Missing physical/low-voltage/other required cases stay in
  the matrix. P5-3 drafts may proceed, not final product/risk closure.

## P16-RAW-01 Archive Followup

The earlier direct-path/Everything searches are reused, not repeated. This
followup inspected central directories of 2258 project-indexed ZIP/TAR/GZ
archives, including the path index of the existing deduplicated packet. No
final r3 directory or row-summary/row-manifest original was found. Twenty-two
archives were unreadable, mostly existing partial downloads plus a corrupt
test fixture; their exact paths/errors remain recorded. No extraction or
external modification occurred. This is not proof that all external backups
are absent or an attribution of when/how files were lost.

Evidence: `.cache/p16-nonpower-20261104-01/archive-scan.json` and
`row-disposition.json`. No raw row may be manufactured from the narrative.
Without a newly supplied archive, plan fresh observations only for the missing
14 AUTO rows, not a blanket rerun of the six unavailable physical rows or the
completed P1-7/P3-5 campaigns. A subsequently recovered valid row must be
evaluated before dispatching its proposed recollection.

## P16-RUNNER-01 Existing Runner Applicability

Preferred entry remains `Tools/jlink/test-p1-6-matrix.ps1`, its existing
`p1-6-common.ps1` / `jlink-common.ps1` primitives and `p1_6_protocol.py`.
Do not implement another flash/SWD driver. Read-only review found:

| Constraint | Required Preparation Before Any Injection |
| --- | --- |
| Runner hardcodes V0=20800, V1=20801 and 138 blocks | Bind new finalized V0/V1 assets explicitly, parameterize version/block expectations, retain row IDs and checkpoint meaning |
| Current retained App is 30313, 614092 bytes, 150 blocks | Do not force it into the old 138-block manifest or claim old fixture equality |
| Some legacy cleanup stops all matching debugger processes | Use exclusive ownership and close only owned processes; do not kill the user's debugger |
| Standard PowerShell entry has native startup-cache side effects | Obtain the narrowly scoped external-write exception before using PowerShell; no speculative startup or cleanup |
| Test-only Boot/App control region and source changed since July | Build/bind the selected current-source test variants; verify control address/layout and production isolation, not stale addresses |
| Row setup clears BCB and corrupts test slots | Freeze exact test assets, row actions and full known-state restoration first; no mutation of retained state from an unbound old plan |

The replacement matrix must preserve magic-last retarget/write/verify/reset
within one native J-Link session for row 02, full before/after BCB A/B originals,
checkpoint identities and final raw/header hashes. Firmware programming and
restoration must use the supported native tools and explicit write bounds.
Retained physical Boot is not automatically interchangeable with a default CI
Boot. Preserve/read back the exact known-good Boot, App and required persistent
state before installing any instrumented fixture; restore production and verify
health/fault/FPB state at completion. No probe-backed breakpoint may be assumed
cleared merely because a later GDB session deleted its own logical breakpoints.

The most recent sole-J-Link-supply read confirms 30313 and the physical Boot,
running health, no fault, no active hardware comparator and released ownership:
`.cache/p17-jlink-only-20261104-01/run-01/result.json`. This is a dated known-good
reference, not permission to skip a fresh pre-mutation check.

## Execution And Authority

This turn changes only the approved sequencing documents, a host regression and
local discovery/test records. It neither marks the 14 AUTO rows PASS nor runs
their injection matrix. Current host checks are independent sanity/regression
checks, not replacements for missing original board observations.

Formal new runner/contract/evidence/index commits need task-scoped local Git
authority: shared `D:/github/my/E-Track/.git` objects, task refs/reflogs and active
worktree metadata, excluding main worktree/index/ref, push/merge and unrelated
changes. Earlier P1-7/P3-5 scoped closeout commits are not silently extended.
PowerShell native startup-cache writes, if allowed, are limited to
`C:/Users/SU/AppData/Local/Microsoft/Windows/PowerShell/` and
`C:/Users/SU/AppData/Local/Microsoft/PowerShell/`; no cleanup or global setting
changes. All controllable scripts/logs/temp/cache/builds remain in this worktree.

Until those bounded prerequisites are available, the safe autonomous work is
row-level source/evidence review, host checks, candidate/runner preparation and
P5 input inventory, not uncommitted formal acceptance or another power experiment.

## Host Verification Completed

The interrupted conversation did not lose the host worker's completion: all six
commands have closed receipts. The first four checks failed before execution of
their test cases because this worktree is sparse: the tracked Boot/OTA/EEPROM
sources have skip-worktree flags and are absent on disk. These are host-input
failures, not product or network failures. The original stdout/stderr and exit-1
receipts remain unchanged in `host-tests/` and `host-results.json`.

The correction uses standard `git archive` at current source
`a52896156627d91cd8a7728324c0601ae25bbf93`, exporting only 74 required source/test
files under the new `source-snapshot-01/` directory. Every exported byte stream
matches its Git blob; present working files match with line endings normalized.
No sparse-index change, shared-index write, source mutation or network fetch was
needed. `retry-host.py` runs the unchanged test entries in this contained snapshot.

| Check | Actual Result | Evidence Under `.cache/p16-nonpower-20261104-01/` |
| --- | --- | --- |
| P1-6 control protocol | 21 checks, zero failures | `host-retry-01/control.stdout` |
| Ymodem/ETSL protocols | 19 checks, zero failures | `host-retry-01/protocols.stdout` |
| Firmware-header vectors | 16 cases passed | `host-retry-01/headers.stdout` |
| Boot state machine | 96 checks, zero failures | `host-retry-01/state.stdout` |
| Existing acceptance/governance classes | 46 tests passed | `host-tests/governance.stderr` |
| New non-power sequencing regression | 8 tests passed | `host-tests/sequence.stderr` |

All four retry stderr files are empty. The three host C compilations use
`-Wall -Wextra -Werror`; no new firmware build or firmware warning count is
claimed. The 152 host checks/cases plus 54 Python regression methods are not
14 new board observations and do not close P16-RAW-01.

`git diff --check` initially reported CR-at-EOL as trailing whitespace in the
existing mixed-line-ending board. The invocation-local
`git --no-optional-locks -c core.whitespace=cr-at-eol diff --check` passes.
No persistent Git configuration or unrelated line-ending rewrite was performed.
The audit entry is `audit.py`; its outputs are `policy-checks.json` and
`write-audit.json`. This is a local uncommitted result, not final acceptance.

## P5 Preparation Inventory

No P5 contract or device campaign was created. The next owner is this root:

| Input Or Observation | Available Basis / Remaining Work |
| --- | --- |
| P1-7 | Existing v4 local PASS and registered bundle `f3af9ee656593e7f5581835c596bc6df53b4b54f`; no replay |
| P1-6 | Recollect only the missing 14 AUTO rows after runner/asset/recovery admission; retain six PHYSICAL rows as blocked |
| BLE ten-recovery prerequisites | P3-5-v5 registered bundle `62a018aa9e84cc857b456686c9e6e1298155c9de`; evaluate applicability to the eventual P5 candidate rather than repeat it for new logs |
| P4 staging prerequisite | Index records P4-1-v4 and P4-4-v8 pre-P5 PASS, not production release; exact future source/asset dependencies still require binding |
| Known-good restoration identity | Dated 30313 App and historical group16 physical Boot from `p17-jlink-only-20261104-01`; fresh full-state backup and verification required before mutation |
| P5-1 same-candidate assets | Finalized App, full, base-bound patch, recovery/metadata and Actions APK still need an explicit common candidate binding; 30313 alone is not this asset set |
| P5-1 observations | SD/BLE x full/patch, one predeclared same-group 30/30 and real four-hour soak remain required; old successful snippets cannot be assembled into this group |
| P5-2 partial sequence | After P5-1 main paths, first reconcile original Boot/HTTP/BLE/admin fault observations; dispatch only actually ready missing non-power cases |
| P5-2 environment cases | Precise supply removal, measured low voltage and weak signal remain distinct obligations; this sequence does not make them ready |

## Consolidated Authority Needed Before The Board Campaign

Do not infer this permission from old P1-7/P3-5 closeout approvals. Request once
for the following bounded preparation and missing-AUTO campaign:

1. Local P1-6/non-power-sequence runner, contract, evidence and registration
   commits, including required sparse-source materialization, using shared
   `D:/github/my/E-Track/.git` only for task objects/refs/reflogs and
   `worktrees/source1` metadata. Exclude main's ref/index/worktree, remote
   push/merge, unrelated changes, hooks/global configuration and production.
2. Only native PowerShell automatic startup writes under
   `C:/Users/SU/AppData/Local/Microsoft/Windows/PowerShell/` and
   `C:/Users/SU/AppData/Local/Microsoft/PowerShell/`. No cleanup or settings
   changes; all controllable outputs remain under this active worktree.
3. On the already identified board/probe only, after verified recoverable backup,
   temporarily install isolated GCC P1-6 test Boot/App and use the existing
   deterministic AUTO row mechanisms: planned resets/halts, BCB test setup and
   candidate/backup/recovery test-slot corruption where each row requires it.
   Restore the exact retained group16 Boot, 30313 App and required persistent
   state afterward, with full readback and health/fault/FPB checks. Do not touch
   unrelated user data, mass erase, test physical supply removal or leave an
   instrumented Boot installed. If backup/recovery admission fails, stop before
   mutation. This is explicit temporary Boot/test-state authority, not an
   assumption that the standing OTA policy permits arbitrary BCB/Boot edits.

The instrumented assets, runner adaptation, timeout/ownership behavior and
restoration route are not yet qualified. Authorization would allow that work
to proceed; it would not itself satisfy the preflight or certify safe recovery.
No new device or network command, PowerShell process, Git write, product edit,
external write, commit or release occurred during this continuation.

## Authorized Continuation

2026-11-04: the user replied "允许" to the immediately preceding consolidated
request for all three boundaries above: scoped local Git work, native PowerShell
startup caches, and temporary P1-6 test Boot/App plus the 14 AUTO fault injections
after verified backup/recovery. This supersedes the pending-authorization state,
not any safety preflight. No per-row approval is needed within this scope.
Remote push/merge, main changes, unrelated data and physical power-cut experiments
remain excluded. New work and original failure receipts use
`.cache/p16-auto-20261104-01/`; earlier host/discovery records remain immutable.

## P16-BOOT-SCOPE-01: Actual Boot Policy Differs From The Old Matrix

NEED_DECISION, discovered before any board command on 2026-11-04. This is a
candidate/criterion applicability issue, not a new hardware or network failure.
The authorized temporary installation has NOT occurred.

The ordinary current-tree Boot commits apply progress after every 4 KiB block.
The retained physical group16 Boot was built from a separately preserved source
variant, not that current-tree body. Its exact 14800-byte prefix is SHA256
`2f84014278421de7a84a0f621a494a9974fbf51c56b768974b0c5e647105ec80`; it equals
the prefix of the known retained 65536-byte Boot original
`01e4b9e162bfaaf9fda070aa13c0cec3f377b8d696db01f731e0ab3d1464e527`.
This is comparison against dated raw originals, not a fresh device sample.

Read-only source reconciliation found the original variant under
`D:/github/my/E-Track/.cache/p34-bc-target/f/boot/`. Its `snapshot.json` binds
`src/boot_state_machine.c` to SHA256
`7710df775b1d05521710d3f4b48fd279572c9af11f0a92305ab27e7aa2e5b568` and
`include/p34_boot_checkpoint.h` to SHA256
`01dc17cfd305c2765c5f4eb80109fdf6eab77a678a0c5ebb4c7db7fcaae4b7b1`.
Both original bindings match. These external files were not modified or copied
into production source.

The actual behavioral delta is material:

- Group16 commits apply progress only when the completed block count is a
  multiple of 16 or equals the total. Rollback still commits every block.
- It compares existing internal blocks and skips erase/program for equal blocks.
- Old AUTO row 09 requires CP6/apply/resume=65, which does not occur for group16
  on these image lengths. Rows 06/08/09 also need appropriate changed blocks;
  a same-executable V0/V1 pair differing only in the header does not exercise
  the same erase points under the skip-identical optimization.

It would be wrong to install the newly built ordinary test Boot, pass the old
matrix and present that as group16 qualification. It would also be wrong to
silently change the old frozen row expectations or disable the optimization
just to reach their checkpoints. The prior P1-6 report and P3-4/P3-5 results
remain historical results within their recorded scope, not retroactively failed.

Preferred next direction: retain the actual group16 candidate; explicitly bind
its existing source and build configuration, then approve a successor AUTO
matrix covering its real before/after durable-group boundaries, skip-identical
branches and unchanged rollback/recovery requirements. Preserve the old row
lineage and six unexecuted PHYSICAL obligations. Use known-safe test fixtures
that actually differ at the required blocks; no arbitrary executable corruption
to manufacture coverage. This requires a candidate/criterion scope decision,
not another per-command Git/PowerShell/device permission request.

Alternative: intentionally choose the ordinary per-block Boot as the subsequent
P5 candidate, which changes the retained candidate and requires reassessment of
upstream evidence applicability. It is not a transparent restoration or the
recommended default. Until the decision, do not install either test build or
declare P5 ready. This root owns the next action after the decision.

## Authorized Preparation Results

- Expanded only the current worktree's sparse source set: 3038 tracked files
  checked, shared main index hash unchanged. No production source was edited.
- Initial build failed because a response-file path was 263 characters; GCC
  compiled without those response-file flags. Its original four missing-header
  diagnostics and exit-1 receipt are retained. A fresh build with
  `CMAKE_OBJECT_PATH_MAX=220` succeeded without any compiler/source workaround.
- Current-tree test and production App+Boot builds both pass, each with 641
  warnings and zero errors. Test App is 614776 bytes, test Boot 18720 bytes;
  production App is 614184 bytes, production Boot 14724 bytes. These are NOT the
  retained group16/30313 images and have not been finalized, installed or released.
- Existing matrix edits replace fixed version/block expectations with original
  image-header/hash and linked-control/VTOR checks, require an explicit probe,
  and remove process-name-wide cleanup. The thin native adapter reuses existing
  owned Windows Job/stream capture; it does not implement Flash or SWD. These
  edits remain uncommitted preparation, not a qualified physical runner.
- Nine Python binding/negative/ownership tests and two native PowerShell syntax
  checks pass. The latter only parse scripts; no native device call was made.
  These checks do not qualify fixture installation/restoration or close AUTO rows.
- No commit, push, merge, network operation, J-Link session, halt, reset or
  persistent-state mutation occurred. The only approved project-external writes
  were the sparse-checkout worktree metadata and any recorded native PowerShell
  startup-cache changes; no external cleanup was performed.

Evidence: `.cache/p16-auto-20261104-01/boot-scope.json`, `audit.json`,
`materialize-01/`, `build-test-01/`, `build-test-02/`, `build-production-02/`,
`tests-01/` and `syntax-01/`. Source/bundle freeze and the 14 board rows are
still NOT_RUN; P1-6's six PHYSICAL rows remain ENV_BLOCKED.

## OTA-DEC-019 Group16 Preparation And Recovery Review

The user selected the retained accelerated Boot. OTA-DEC-019 and the new canonical
P1-6 Spec supersede only the obsolete per-block APPLY expectations. The old
20-row report, earlier failures, six PHYSICAL obligations and P5 numerical gates
remain unchanged. No further lamp/USB or power-removal experiment is planned.

The preserved external group16 source was rehashed against its original snapshot.
A fresh baseline build reproduces all 14800 retained executable bytes, SHA256
`2f84014278421de7a84a0f621a494a9974fbf51c56b768974b0c5e647105ec80`.
Its compilation has zero warnings/errors; configure retains one warning for two
unused registry variables. The instrumented same-source Boot is 18804 bytes,
SHA256 `3b81e559ac4e758abcfe3bbac390bc49a17ee2106e03d2f9179db16aed1fd012`,
with zero configure/compile warnings/errors. Earlier test-App build remains 641
warnings and zero errors. None is a newly published firmware or CI release.

Fixtures use the same linked test executable and versions 30314/30315. Differences
outside their normal fw_header are confined to appended, non-executed bytes.
K=160, APPLY A=176, ROLLBACK R=161 and N=195 with a partial final block. In row 08,
durable K stays 160 while revalidation skips equal K and the next erase is K+1.

Read-only backup captured the full 1 MiB internal Flash and each of the three
1 MiB source slots. Original group16/30313, advancing health, unchanged staging,
no active comparator and no debug freeze passed before/after capture. Standard
AT32F435RGT7 Commander attachment also passed without halt/reset/Flash. These
are real read-only observations, not qualification of a completed restoration.
Evidence root: `.cache/p16g-20261104-01/`, especially `backup-01/`,
`native-qualifier/`, `baseline/`, `instrumented/` and `fixtures/`.

Recovery inputs are exact slices of the pinned backup: affected Boot=0x5000,
App=0xC3000 at 0x08010000, and original candidate/backup/recovery payloads.
Only existing standard Commander and the existing test Boot INSTALL_SLOT and
CLEAR_BCB primitives are used. The command interceptor holds before the ordinary
state machine, so intermediate old payloads are never intentionally booted.
The first test command snapshots both original BCB records before any BCB clear.
Normal App execution is followed by a bound HAL_Update storage-idle halt; the
one owned physical comparator is cleared and read back, not logically deleted.
Debug freeze protects halted windows; production restart clears it again.

Restoration scope is explicit: the whole internal 1 MiB must equal its original;
all three original slot headers and full declared payloads must match; staging
header/journal must remain unchanged. The BCB returns to a known CONFIRMED 30313
with no pending apply/rollback. BCB A/B sequence bytes and unused slot tails are
not claimed byte-identical. Full raw originals and full final slot readbacks are
retained so those differences stay visible. Test setup writes only BCB A/B and
the three dedicated OTA slots, not user settings or unrelated external storage.

Host-02 matrix binding, native ownership, dry matrix and syntax checks passed.
The first idle-halt mock failed because its PowerShell high-bit address literal
was signed, not because of a physical board failure. Host-03 exposes that exact
error; host-04 fixes the mock and all seven idle-halt cases pass. The first
recovery-input attempt rejected a map-regex whitespace assumption before writes;
the corrected exact linked-symbol parser produced `restore-inputs/plan.json`.
These host failures do not authorize repeating any device operation.

At this preparation checkpoint the original board is still untouched by any
reset/halt/Flash/test-state mutation. Formal admission and the fourteen AUTO rows
are still pending. All controllable outputs stay inside this active worktree;
approved native PowerShell/SEGGER side effects remain limited to their named
directories. Local task Git scope is already authorized; no push/merge/main change.

Final preparation checks in `host-final/` pass: 17 asset/native/restoration tests,
7 native-halt mocks, 10 sequencing/group16 regressions, 46 existing governance
methods, the real-fixture dry matrix and four PowerShell syntax checks. Python
sources also parse without generating bytecode. The shared-root governance was
compared read-only; it is older than this task branch's existing authorized
failure-record and P4-1/credential additions, not a newer conflicting policy.
No historical frozen file was changed to adopt the new group16 matrix.

## Native Installation Failure And Verified Recovery

Preparation source was committed as `b48faa056aedfe39d27efecb8f6752fb5c355326`,
with frozen-plan binding in `b3510b5ed315d303d2ee3109b8d7e72f4b73e660`.
The v1 outer caller rejected its timeout (>18000 seconds) before the campaign
entry created any directory or device lock. Its launch receipt is preserved.
Source `66cb723f95cba0ae13ba9e5c447d23972aefc933` bounds the matrix to 10800
seconds, setup to 2400 each and the outer caller to 18000. Nineteen host matrix/
plan/deadline tests pass. The v2 actual NOT_RUN precheck passed; plan-only output
is not substituted for that admission. A misplaced first plan output remains
inside the worktree alongside the corrected relative-path output.

The v2 campaign verified fresh full internal Flash and all three slots against
the backup, then established a real idle halt and cleared the owned comparator.
Its first native load programmed/verified the 18804-byte test Boot. The second
load in the SAME Commander process timed out in the vendor RAM CRC routine
before App erase/program. The old-probe/native cache interaction is an evidenced
route problem, not a proved electrical or network fault. Fourteen AUTO rows,
BCB test setup and slot writes were never reached. Preserve `campaign-02/`,
`launch-02/` and their error/cleanup receipts; do not silently replay that entry.

Passive `reconcile-01/` reads proved the complete App partition and every byte
outside the 0x5000 Boot prefix unchanged. Core diagnostics showed RAMCode
PC=0x2000041A and fault/lockup status, not a running product observation.
The dead campaign's original lock was archived and transferred to the bounded
recovery owner. A fresh standard Commander session restored ONLY the original
0x5000 Boot prefix, then normally restarted production. `recover-boot-01/`
independently verified the whole internal 1 MiB and all three full 1 MiB slots
byte-identical to backup, original group16/30313, advancing healthy operation,
unchanged staging, clear fault/comparators and freeze=0. Ownership was released.
No App/BCB/slot restoration write or physical power operation was required.

The minimal repair uses one standard Commander process per downloaded image,
retaining the same verification, image bytes and write bounds. Eight idle-halt/
download-separation host checks pass. This does not add a Flash driver, change
the device firmware under test, waive a row or claim the matrix passed. The
next successor must retain the v2 failed installation as its actual predecessor
and admit only the still-missing AUTO observations after the verified recovery.

## P1-6-v3 AUTO Closeout

2026-11-04: all fourteen AUTO rows executed successfully after the scoped native
session repair. Source freeze `c614421eb2512f7cc962d4dbef81548b0d24474c`, tree
`e4ab92149c7e9ec506d5fa45de9779d91cc9f70d`; compact original evidence is committed
as `6876afd2617be90d504ade5708e79d2c40928fd2`. The bundle contains 7633 files;
each staged Git blob was checked against the working-file bytes before commit.
Per-bundle -text attributes preserve original binary and text streams. No remote
push, merge, production release or main worktree/index change occurred.

Both actual FROZEN/NOT_RUN admission and final validation passed. The final
matrix is `docs/acceptance-contracts/P1-6-v3/final-matrix.json`: fourteen
EXECUTED PASS and six NOT_OBSERVED, overall EVIDENCE_GAP. That whole-contract
result retains missing electrical tests; it does not negate the now-complete
AUTO subsection or imply a product failure. No older P1-7/P3-5 campaign replay.

Independent raw review anchored every row trajectory to captured 512-byte
control records, checked active BCB CRC/fields and the exact final full image.
Actual group16 frontiers are K=160, A=176, R=161 and N=195. Row08 keeps durable
160 while revalidating/skipping equal block160 and erasing161. Row09 retains
the committed prefix at176. The final partial group commits195. Trial counts
3->2->1->0 lead to rollback; rollback resumes161 with its prefix preserved.
The both-sources-corrupt row reaches recovery while preserving valid internal
V1. All thirteen BOOTABLE terminals and the one PHYSICAL_RECOVERY terminal
match their frozen meanings; the latter is NOT an electrical power-cut test.

Existing group16 host originals were evaluated without repeating their models:
1793 group16 scenarios/1691 modeled cuts, 39 source-switch extensions, and
336 byte-prefix tears/36 I/O faults/11 sequences/3 negative oracles. Actual
state-machine text matches the target ignoring CRLF. Three changed inventory
headers are demonstrably outside the original compiler dependency closure.
Raw inputs and review method are preserved in the bundle's originals area.

The final restoration readback verifies the complete internal 1 MiB against the
pre-test original, including original group16 Boot and 30313 App. Original
candidate/backup/recovery headers and their complete declared image payloads
match. Staging/journal are unchanged. Final BCB is CONFIRMED30313, runtime
advances, SD is ready, fault registers and debug freeze are zero, no active
hardware comparator remains, and the owned device lock/processes are closed.
As predeclared, BCB sequence bytes and unused slot tails differ; they are not
claimed byte-identical. Full before/after slot dumps retain those differences.
No unrelated settings or storage region was intentionally rewritten.

The finite campaign is `.cache/p16g-20261104-01/campaign-03/`; its completed
outer receipt is `launch-03/campaign.closed.json`. v1 pre-entry timeout rejection,
v2 native preparation failure and the separately verified Boot-only recovery
remain preserved. No successful row was repeated to repair packaging.

Six PHYSICAL rows 03/05/07/15/16/17 still require qualified electrical conditions.
P1 remains6/7 and P5 remains0/3. P5-1's AUTO prerequisite is now satisfied:
next prepare one production-candidate full/patch/recovery/App group and assess
upstream applicability, then freeze the four combinations/30-of-30/four-hour
campaign. Those candidate bindings do not yet exist; temporary P1-6 fixtures
are not P5 production artifacts. Do not reuse the exact-byte Boot reproduction
as a claim that the ordinary current-tree Boot automatically became group16.

Final build/test counts: instrumented Boot compile/configure0 warnings0 errors;
baseline Boot compile0/0 with one preserved configure warning; reused test-App
build641 warnings0 errors. Latest host checks are19 matrix/plan/deadline methods,
8 idle/native-session mocks,10 sequence regressions and46 governance methods.
All controlled outputs, copied originals and archives remain in the active
worktree. Authorized external effects are task Git objects/ref/worktree metadata
and native PowerShell/SEGGER startup/history paths only; no external cleanup.

## P5-1 Entry Inventory After AUTO Closure

2026-11-04. The user requested checking P1-6 and starting P5-1 if the available
P1-6 work was complete, with authorization for necessary in-scope work. The
fourteen AUTO observations are complete; the six electrical cases are not.
This continuation therefore starts P5-1 preparation under OTA-DEC-018, not a
replay of P1-6 or a new USB/power-removal experiment. The active writable root
remains `D:/github/my/E-Track/.cache/p35-integration-20261028/source`.

One offline inventory ran successfully with 18 checks, including wrong-version
and wrong-image-hash rejection by the existing firmware byte checker. Originals,
exact input hashes, check results and the source comparison are recorded in
`.cache/p51-preparation-20261104-01/`. This is preparation evidence, not 18
product tests, formal admission, or any P5-1 physical PASS. No formal P5-1
contract was created. The readiness row in `PLAN-OTA-EXEC.md` remains authoritative.

### Existing Inputs Reconciled

- The P1-6-v3 matrix contains exactly fourteen observed EXECUTED PASS AUTO rows;
  six PHYSICAL rows remain unobserved and overall EVIDENCE_GAP remains unchanged.
- Firmware CI run 41463640594, source
  `18f6b3d3af0c24b1ce81573700cd61005b7c530e`, already produced a complete 30313
  App/full/patch/recovery/metadata group. The full is 290929 bytes, patch 25561
  bytes and recovery 614100 bytes. All three actual files match metadata hashes.
- The finalized App is 614092 bytes with SHA256
  `4126d801e6bd6efd57a9f20d5a128a50cfb5a46580dc10d9a2227702247d5805`.
  Preserved CI full-decoded, patch-decoded and recovery App bytes all match it.
  The existing parser independently checked the header, image hash and ETU
  outer/base fields. This did not newly decrypt the encrypted packages.
- The patch requires exact base 30207, SHA256
  `aaf5ccdb047ef8b3ff4ae0837f9593ceca857d90c98ea0bc09360e411bf4196f`.
  Its preserved base bytes equal the committed P4-1 bootstrap original. This
  proves base availability, not permission or a validated route to downgrade
  the current board to that base.
- The retained Actions APK still hashes to
  `f37c3282cd6420672d766b1761bd84f68fd29297248069a74a0bdb9fea78e1f8`.
  This is the P3-5 candidate APK, not a new installation or a current-phone query.
- The reproduced non-instrumented group16 Boot is 14800 bytes with SHA256
  `2f84014278421de7a84a0f621a494a9974fbf51c56b768974b0c5e647105ec80`.
  Its state-machine source, checkpoint header and CMake input match the preserved
  source snapshot. No new Boot build or device read was required.

### Remaining Preparation And Next Owner

| ID | Observed fact | Direction and verification |
| --- | --- | --- |
| P51-CANDIDATE-01 | The 30313 CI Boot is 14724 bytes, SHA256 `3554e193f498d23210f5ef32e09de64575b7cd39104fafcc950740e5e8a7ec34`; it is not the retained group16 Boot. Current worktree `boot/src/boot_state_machine.c` still commits every copied block and lacks the retained skip-identical implementation. | Root binds the selected App/APK and approved group16 source/artifact explicitly. The existing independent group16 evidence remains valid; this is not a reason to rerun P1-6 or install the CI Boot. If final delivery needs production-source integration, return that bounded change to implementation ownership and obtain independent review, rather than silently modifying product code in P5 acceptance. |
| P51-ASSETS-02 | The last verified board already runs 30313, none of the three existing assets is the required 1048576-byte reference, and P1-6 versions 30314/30315 are temporary fault-test fixtures. | Prepare a legal forward version/base pair and all corresponding assets from the selected production executable. Reuse existing pack/unpack and reference machinery. Qualify its key binding: `Tools/ota/p34-acceptance/reference.py` currently only supports the development-key route. Do not reuse an old-version reference, append arbitrary ETU bytes or promote P1-6 test images. Check exact ETU length, real decoding, target bytes and negative controls before freezing. |
| P51-EXECUTION-03 | The prior ten-recovery campaign and current restored board are dated observations, not a declared P5 statistical group or a fresh starting-state check. | Bind the safe CONFIRMED start/restore route and sole collector ownership; independently assess P3-5 applicability to the selected parameters. Then declare four real SD/BLE x full/patch cells, one same-group 30/30 reference campaign and real four-hour soak. Preserve all attempts; do not count setup/idle/restore time as transfer or rebuild successful old evidence by replay. |

These items are asset/candidate/runner preparation, not an observed new firmware
failure or a network diagnosis. No network test was needed for this inventory.
No user physical action is needed at this preparation stage. Request an actual
SD/phone action only after its input and complete observation route are ready.
The current authorization is recorded once; do not ask again for the same scope.
Production release, gate unlocking, arbitrary BCB manipulation, unrelated
filesystem writes and other devices remain outside this preparation.

All chosen writes in this continuation are this appendix and the six files in
the new project-local preparation directory. There were no builds, Git writes,
network calls, device operations, native PowerShell/SEGGER invocations, product
edits, deletions or external writes. Existing dirty files and frozen evidence
were not reverted or rewritten. Early read-only query errors did not run a
device action and are not product failures.

### P51-ASSETS-02: Exact-Base Reference Preparation

The next bounded preparation reuses `Tools/ota/p34-acceptance/reference.py`,
its progressing-delta size search and real native decoder. Its existing entry
always re-finalizes both images at timestamp 1786320000, changing the hash of
the actual 30313 base; it also explicitly forbids release-key input. The minimum
adapter is an exact-base option and explicit target build timestamp, with tests
for unchanged base/executable bytes and rejection of a wrong or damaged base.
No replacement encoder, flasher, protocol, product code or workflow is needed.

Prepare an offline 30313-to-30316 reference from the existing CI executable,
skipping the P1-6-only 30314/30315 fixtures. The generated encrypted reference is
development-key-only and NOT_INSTALLABLE; retain the key-independent raw delta,
compressed stream and exact-size witness for subsequent protected packaging.
This is not authorization to extract a firmware key, export a protected CI key,
publish a release or send the development package to the board. The current
process has no OTA_AES_KEY input; that does not imply the CI secret is absent.
All host test, compiler, home/cache/temp and search outputs are confined to
`.cache/p51-reference-20261104-01/`. The search retains its existing 128-sample
limit and has a bounded outer host window. Failed attempts are retained.

### Exact-Base Reference Prepared; Protected Packaging Handoff

The exact-base adapter and eight targeted unit methods passed. The existing
bounded search generated an exact 1048576-byte legal reference PATCH for
30313 -> 30316. Its unchanged real C decoder passed one complete decode and
four required rejections: payload CRC, truncated length, same version and wrong
base SHA. Each negative stopped before candidate preparation. Native compilation
retained zero warnings and zero errors. All owned test/build processes closed.

The base is byte-identical to the original 30313 CI App. The proposed 30316 App
remains 614092 bytes, SHA256
`6845544537f10da0367443342bed3618ff7986dbac86a7ccf1f9cfcd80e6edc2`;
all bytes outside fw_header equal the existing executable. The target timestamp
is explicitly 1793038630. This locally finalized target is not a new CI run,
released image or installed firmware. Source remains the original
`18f6b3d3af0c24b1ce81573700cd61005b7c530e` CI executable family.

The retained witness uses 186518 progressing delta groups, a 5090524-byte raw
delta and a 1048472-byte fully consumed LZMA stream. Native decoding reconstructs
all target bytes with guards/workspace cleanup intact. These are host decoding
facts, not a measured device speed or runtime-memory claim. The raw delta and
compressed witness can be reused in protected packaging without repeating this
size search. The encrypted host fixture explicitly remains DEVELOPMENT-ONLY,
NOT_INSTALLABLE and NOT_PUBLISHABLE.

Evidence: `.cache/p51-reference-20261104-01/reference/`, exact outer command
receipts under `host-tests/` and `launch/`, and `handoff.json`/`audit.json`.
Only validation tooling changed: the existing reference entry now optionally
preserves the exact base and accepts an explicit target timestamp; its legacy
default finalization is covered by regression. No production code/workflow,
frozen bundle or prior result was changed, and no device operation occurred.

P51-PACKAGING-01 is the next implementation boundary, not a new device failure.
The protected candidate/reference path must use the approved CI secret inside
its protected environment, bind group16 rather than silently selecting the old
CI Boot, and return full/base-bound patch/recovery/reference assets with exact
source, target, key and CI provenance. The reference remains exactly 1048576
bytes and must decode to the bound target; wrong base/hash/key and missing
provenance must fail. Reuse the existing encoder/packer and native decoder;
do not export the key, weaken the release gates or promote the development
fixture. Any production build/packaging integration belongs to an implementation
owner, followed by this independent acceptance owner, not self-acceptance.

The current chat's cc-connect discovery returned `no binding for this chat`.
No implementation agent was contacted or spawned; no daemon/configuration was
changed. The read-only CLI query had CC_LOG_FILE removed to avoid inherited
external log writes. It is not evidence of a GitHub/network failure. Assigning
the separate implementation work is the remaining coordination step; the
current ordinary P5 authorization is not being re-requested.

No 4/4, 30/30, four-hour soak, firmware CI, publication, Git commit/push, MCU
flash/reset or physical test was run here. Controllable outputs and caches are
inside the active worktree. Existing unrelated changes remain untouched.

### P51 Implementation Delegation Authorized

The user explicitly answered "allow" to starting a separate implementation
sub-agent for P51-PACKAGING-01. Root started `p51_packaging_impl` for that bounded
implementation; root remains the independent acceptance owner. Initial work is
read-only design, followed by root-preflighted file/test outputs. No additional
agent, hardware work, production release, secret export or gate relaxation is
included. The old absent cc-connect binding does not block this explicitly
authorized built-in child-agent route.

The proposed direction is a protected artifact-only preparation path reusing
existing key/pack/decode helpers and the exact archived App/group16 inputs,
without relabeling them as same-invocation outputs of the existing production
release pipeline. Root separately captures read-only GitHub workflow/environment,
branch-policy, secret-name and active-run metadata in
`.cache/p51-owner-20261104-01/remote-readiness/`. These GETs do not qualify secret
values, dispatch CI, change protection or provide release authority. A model
provider rate-limit interruption of the child was resumed as the same task,
without another agent or replayed product operation.

### Protected Packaging Implementation Reviewed Locally

The authorized implementation child finished P51-PACKAGING-01 and stopped
editing. Its ten source/data/test files and preserved failed attempts are bound
by `.cache/p51-packaging-impl-20261104-01/audit.json` and `handoff.md`.
Root independently rehashed the delivered files and original test outputs,
reviewed the code and reran 10 Python methods plus 23 new-entry and 90 existing
workflow checks. All passed with unchanged delivered source. Review output:
`.cache/p51-owner-20261104-01/review-01/`.

- P51-REVIEW-01 is closed: bounded per-stage compiler/decoder diagnostics and
  observations are saved before failure, with case-insensitive full-key/word
  redaction. The original build input is hash checked before key matching.
- P51-REVIEW-02 is closed: the existing WindowsJob/gated launcher and POSIX
  process-group ownership handle native timeouts. A real parent/child timeout
  regression passes. An uncertain active-tree marker prevents cleanup/upload
  rather than falsely claiming resource closure.
- P51-REVIEW-03 is closed: portable manifest paths reject Windows drive/colon,
  backslash, absolute and dot-segment escapes before filesystem access.

The new `package_candidate` workflow mode is artifact-only. Ordinary jobs are
unchanged unless this explicit mode is selected; conflicting modes fail before
secret use. The existing protected `firmware-rehearsal` reviewer remains. The
dispatch supplies `candidate_reviewed_commit` equal to the actual runner SHA;
no permanent source-approval variable or key export is introduced. Only the
single packaging step receives the existing secret. Exact original App/key
binding and explicit external group16 Boot provenance are checked. The valid
1 MiB PATCH doubles as the reference alias, not an additional release asset kind.

This is LOCAL_IMPLEMENTATION_REVIEW_PASS, not protected-key verification,
Linux CI, registered release, P5-1 4/4, 30/30 or four-hour acceptance. Native
host decoding uses synthetic keys and retains zero compile warnings/errors.
Root's prior exact-base helper is committed as
`6c6dff05feb3f6723c68c4551cd3753f915e2cd6`; the reviewed implementation is the
next scoped local commit on `dev/firmware/p51-packaging-20261104`.

Read-only GitHub checks found the workflow active, the packaging secret name
present (value unverified), both boot-chain gates false, and no active/waiting
firmware runs. Only three older task branches are currently admitted to
`firmware-rehearsal`; the new P51 branch is not. The remaining remote action
needs explicit authorization to push this branch, add exactly its environment
branch-policy entry, and dispatch/review the one artifact-only candidate run.
Do not move an older allowed branch, remove reviewers, unlock production or
silently change environment policy. No remote write or CI dispatch has occurred.

All local controlled outputs remain under the active worktree, plus previously
authorized task Git objects/ref/reflog and worktrees/source1 metadata. Main
index/ref/config, unrelated dirty files and frozen evidence are not changed.
No additional agent, production/native firmware build or device action was used.

### P51 Protected CI Authorization Continuation

The user explicitly authorized the previously named remote scope and then
confirmed full same-scope authority without repeated approval requests. Root
may push `dev/firmware/p51-packaging-20261104` at reviewed implementation
`446b0a99b8538714be7e54e640eeb6e58658e76b`, add exactly that branch to the
existing firmware-rehearsal allowlist, dispatch the artifact-only candidate and
approve its protected run on the user's behalf. Such approval is user-delegated
agent action, not a claimed human click. Existing reviewers, other policies and
all production/rehearsal boot-chain gates must remain unchanged and closed.
No device operation, production publication, key export or unrelated write is
part of this continuation. Per-operation intent, raw responses and readbacks
are retained under `.cache/p51-owner-20261104-01/ci-*` using the existing host
and GitHub adapters. Uncertain mutations are reconciled, never blindly replayed.

### P51-ASSETS-02 Closed: Protected CI And Independent Artifact Review

The authorized exact branch push succeeded without force. Exactly one new
firmware-rehearsal branch policy was added; all existing policies/reviewers and
repository, rehearsal and production boot-chain gates remained unchanged.
Root made one artifact-only dispatch and its user-delegated protected approval.
Run `41778918087`, attempt 1, completed successfully at reviewed source
`446b0a99b8538714be7e54e640eeb6e58658e76b`. All ordinary firmware, rehearsal,
binding-qualification and production jobs were skipped as intended.

Artifact `13298118510` uploaded and downloaded successfully: 3082312 bytes,
SHA256 `121e8e26ee8171b017d81ca163cc40387f2bde168bdb82fb349aca5af54ee446`.
Original archive, workflow logs, provenance and independent result are preserved
in `docs/ota-exec-notes/P5-1-candidate-2026-11-04/`; see its README and index.
This continuation did not observe a push, upload or download failure.

Six independent original-artifact checks passed. Candidate App 30316 is 614092
bytes, SHA256 `6845544537f10da0367443342bed3618ff7986dbac86a7ccf1f9cfcd80e6edc2`.
The exact-base PATCH and reference alias are both 1048576 bytes, SHA256
`2e0c738dadac308e554caa594fde3b4ed65e06a0f7ae81049e9a335f34399b16`.
Full is 291069 bytes; recovery is 614100 bytes and contains the exact target.
The 14800-byte external group16 Boot is unchanged. The protected key matches
the original CI build binding; no key was exported or read locally.

Actual Linux CI originals show 10 Python tests and 23 Node checks passing.
The real native decoder produced the exact target and rejected payload CRC,
truncated length, same-version and wrong-base-hash negatives before prepare.
Native compilation had 0 warnings and 0 errors. There was no MCU firmware
rebuild, and historical 641-warning firmware builds are not relabeled warning-free.
All native process trees closed and private-header/decoder cleanup passed.

Two root inspection failures were local review-entry mistakes, not CI/product
failures: an isolated Python import path omitted the already installed crypto
dependency; normalizing a CRLF native source changed its comparison hash.
Failed source versions and records remain; the final review checks exact bytes
from the unchanged archive and source. Neither caused another CI run or OTA.

P51-ASSETS-02 is closed for protected candidate preparation. P51-EXECUTION-03
remains pending: bind supported complete-state starting/restoration inputs,
SD placement/UI and BLE service/collector routes, independently assess old P3-5
parameter applicability, then freeze the actual 4/4, same-group 30/30 and real
four-hour campaign. No P5-1 contract or physical PASS is created by this record.
No user physical action is needed until the observation route is ready.

All controlled local outputs are under the active worktree and authorized task
Git metadata. The shared main index/ref/config, unrelated changes and frozen
evidence remain unchanged. The board and phone were not operated in this stage.

### P51-EXECUTION-03: Current State And Recovery Preparation

The following preparation belongs to `.cache/p51-execution-20261104-01/`.
It is not a P5-1 physical campaign or a frozen acceptance contract. Continuation
messages do not replay the completed observations or previous protected CI.

`current-01/observation.json` records one completed passive inspection:
CURRENT_30313_CONFIRMED_HEALTHY, exact selected App and group16 Boot, CONFIRMED,
advancing loop/watchdog and SD ready. Six owned commands closed; the device lock
was removed normally. No halt, reset, flash or persistent write occurred. Native
SEGGER history updates use the existing standing exception. Only fixed C/D and
optical F volumes were present; no host-mounted removable SD volume was found.

`old-statistics-inventory.json` establishes the actual logging gap: the preserved
30313 capture has 5306 state records but zero OTA_LINK_SAMPLE/OTA_LINK_STATS in
the retained App/Logcat originals. State-recorder timestamps are not the original
link clock. Do not replay that successful OTA or infer ACK latency from state time.

Root adapted the existing P34 validation-only restore fixture, not a production
rollback path: optional exact compile-time bindings and explicit mailbox version
pairs support 30316 -> 30313, selected backup length/CRC/SHA and full Boot-region
hash. Default P34 bindings remain unchanged. Default and P51 native transaction
tests each passed 22 cases; five P51 mailbox methods passed. The complete live
route regression passed 135 methods after correcting an obsolete test mock. Its
earlier 134-method run with one mock error remains in `live-regressions-01/`.

The first restore build failed on a Windows GCC response-file path limit and is
preserved in `restore-build-01/`. The successful build reused the same supported
entry with project-local `.cache/p51r` and object-path-max 240: 643 warnings,
zero errors, App-only fixture, no Boot rebuild. The finalized restore fixture is
111836 bytes, SHA256
`b481a1bc45660655f7fadb7b785a2a30cd183b7372c7a422f05c30dbf8ef3b60`.
`restore-prepared-01/` verifies actual linked expected/Boot/backup bytes and the
640-byte control mailbox. It has not been installed; physical restoration is
NOT_RUN. No arbitrary BCB write or App-only version downgrade is admitted.

`backend-read-01/` records a read-only check of the existing isolated test service:
27 releases, highest version 30313, no 30316; stable revision 70, beta revision 11.
The existing Access session covers the planned twelve-hour host window. No new
credential, channel mutation, release registration or network blocker was found.
Artifact-only metadata is not silently relabeled as a registered formal release.

### P51-TIMING-01/02: Reliable Link Observations Before New Device Work

The existing authorized implementation owner `p51_packaging_impl` now owns the
minimal App observation extension. Root retains independent review and serial
Git/CI/device ownership. Explicit p51-arm-timing opts into a separate diagnostic
record type in the existing file, FIFO, acknowledged stream, sequence/hash/seal.
Original OtaLinkStats samples retain their source clock and runtime owner; default
recording, transport parameters and ACK algorithms must remain unchanged.

Initial host self-tests passed 70 runner and 15 live-stream methods. Flutter
analyze/tests and nonpublishing Release APK/EXE verification remain pending.
Root found P51-TIMING-02 before physical execution: binary Logcat framing and
shared file-cursor/seal/recovery consumers still assumed state-only schema 1,
and state array indexing assumed sequence equals array position. The same owner
is correcting those consumers together with mixed-record/diagnostic-tail/loss
tests and checking a realistic summary against the existing 3500-byte limit.
No physical observation is invalidated because no P51 transfer has started.

After the consolidated handoff, root will commit only this batch on
`dev/flutter/p51-timing-20261104`, use its automatic full dual-host development
checks once, then the already-authorized nonpublishing APK/EXE workflow. Planned
version is 1.0.72+98; preserve the existing side-by-side application identity,
test endpoint and adaptive-v2-candidate link profile. No production release,
test-channel activation or new OTA is authorized merely by these CI receipts.

The four-cell route is still being bound: production latest selects a matching
patch automatically, so BLE full needs a legitimate nonmatching baseline or a
supported full-selection route, not a fabricated current hash or edited D1 row.
The one-hour/128MiB recorder limits remain; declare per-cell sealing/retrieval
for long observations rather than recording four hours into one file. Preserve
all failed attempts, original CI/evidence and the six P1-6 PHYSICAL obligations.

### P51 Interrupted Host Preparation Reconciled

The full-cell baseline preparation had already completed and was not replayed.
It is the same 30313 executable, with only its normal fw_header timestamp/hash
changed, raw SHA256
`68251b1bb66a1d36a8e166d2e7f64639e251911a3bbdc39da9e935691f9876ea`.
It is separate from the original-base 30/30 group. Actual service selection and
physical installation remain NOT_RUN; no current-device identity is inferred.

The `.cache/p51rf` configure succeeded, but its build stopped after 131 reported
steps and left no build/result receipt. No compiler/Ninja/Python process remained
at continuation. The existing Ninja directory was incrementally completed using
the unchanged build entry's process/environment primitives, not reconfigured or
clean-built. `.cache/p51rf-resume-01/` binds the original interruption separately
from the successful suffix and size receipts. Original logs are byte-preserved.
Partial/suffix warning counts are 57/586, both with zero error diagnostics; these
are separate logs, not a new clean-build warning count. The fixture is App-only;
the retained group16 Boot and protected candidate packages were not rebuilt.

`restore-full-prepared-01/` under the execution directory validates the actual
linked expected versions, full Boot hash, alternate backup hash and 640-byte
mailbox. Final fixture: 111836 bytes, SHA256
`b6d22016c19325d267bbfba0eecac8679e529828d72f8eefa1e9178eec51587f`.
It remains PREPARED_NOT_INSTALLED, not a physical restoration PASS.

Timing-consumer host receipts in `python-07/` include runner 72, stream 15,
binary Logcat 9, mirror 3 and cleanup 3 passing methods. The smoke command's
180-second timeout remains a failure with cleanup complete. Its six completed
entry methods were not replayed. `.cache/p51-smoke-resume-01/` uses verbose,
bounded per-method suffix checks and periodic stack diagnostics: the interrupted
seventh method passed in 89.388 seconds, with a sampled stack in Windows path
validation, not a device command. Remaining route checks are still in progress.
The diagnostic's periodic 'Timeout' text is a stack timer, not a fabricated
test failure or permission to ignore the outer command deadline.

The consolidated WIP source includes mixed-record cursor/seal/Logcat recovery
and a realistic 1MiB summary-size regression, without widening the 3500-byte
ceiling or changing OTA parameters. Root's `app-review-inputs.json` binds exactly
17 source/test/version files for serialized development CI. Flutter checks and
APK/EXE verification are pending; no device, cloud mutation, formal admission,
merge or release follows merely from this WIP source commit.

### P51 Continuation Checkpoint And Service-Entry Decision

The local smoke suffix completed: 31 unit methods, the remaining seven entry
methods and 37 route methods all passed. These 75 methods have closed owned
receipts under `.cache/p51-smoke-resume-01/`; the original six completed entry
methods and the overall 180-second timeout are not relabeled as a successful
whole-suite invocation. No product code or test assertion changed to achieve
this result. The real local paths remain fully checked; no boundary guard was
disabled to shorten execution.

WIP source `792a8a372d21ff4abd056deae28ef9b8e64bec6a` is pushed on
`dev/flutter/p51-timing-20261104`. Its only automatic development run is
`41794760486`, with Ubuntu and Windows jobs still running at this checkpoint.
The prior commit adapter stopped after staging because it compared Windows
backslash paths to Git POSIX paths. The exact 18-file staged set was inspected;
the corrected suffix committed without re-creating the branch or re-staging.
That host failure is preserved in `app-commit-01/`; `app-commit-02/` records the
actual successful commit. No force push, main integration or release occurred.
APK/EXE verification and all P51 physical observations remain NOT_RUN. Reconcile
the existing CI run before dispatching any later validation; do not replay it.

P51-SERVICE-ENTRY-01 is NEED_DECISION, not a credential or observed backend
failure. The approved protected packaging route deliberately emits
`p51-artifact-candidate-v1`, `isFormalRelease=false`, `readyRegistered=false`.
The existing firmware registration client requires schema 2 and
`isFormalRelease=true`; the ordinary release workflow rebuilds its own App/Boot
instead of consuming this explicitly external group16/exact-size candidate.
Changing the candidate flag or pretending those bytes came from that ordinary
workflow would lose the approved provenance and is not an acceptable shortcut.

Recommended boundary: explicitly authorize a minimal, independently reviewed
isolated-test-service entry for these unchanged 30316 assets, preserving their
artifact-only originals and exact App/group16/source/run identities. It would
include the three test assets' upload/full readback/registration and only the
necessary temporary test-channel selection followed by restoration, using the
existing P41 test resources. This is beyond the specifically artifact-only CI
allowance, not a request to repeat ordinary development CI authorization.
It excludes production, gate unlocking, existing evidence rewrites, key export,
other devices and unrelated external filesystem writes. Root must obtain this
scope decision before implementing or executing that integration. Do not start
a board/phone operation merely because the local preparation or development
workflow succeeds. The next owner is the current root after the decision.

Continuation output and closed-command inventory:
`.cache/p51-execution-20261104-01/continuation-audit.json`. Chosen local outputs
remain in the active worktree; external writes are limited to the previously
authorized task Git objects/refs/reflogs and worktrees/source1 metadata. No
PowerShell, SEGGER, ADB, physical reset/install, test-service mutation, external
cleanup or unrelated worktree edit was performed in this continuation.

Final read-only CI reconciliation: `app-status-04/` records development run
`41794760486` completed SUCCESS at the same `792a8a372d21ff4abd056deae28ef9b8e64bec6a`.
Both Ubuntu and Windows jobs succeeded; this supersedes only the earlier
in-progress checkpoint, not APK/EXE or hardware NOT_RUN. No second development
dispatch occurred. The session audit verified 75 remaining smoke methods,
172 closed command receipts and 5361 retained output/source files before that
last CI GET. Its own earlier CI_RUNNING label is an as-of record, preserved;
the additional status-04 output guard/closed receipts and Git write audit were
checked separately. The user-facing next step remains P51-SERVICE-ENTRY-01.

### P51-SERVICE-ENTRY-01 Authorized

The user replied with full authorization for the exact proposed isolated service
entry and explicitly requested no repeated same-scope permission questions.
This supersedes NEED_DECISION: proceed with unchanged candidate assets, existing
test resources/credentials, independent input checks, immutable upload/full
readback/registration, and necessary temporary test-channel switching/restoration.
Original artifact-only metadata and all original source/run identities remain
immutable. A separate schema-2 test registration record is not production
promotion or a claim that the ordinary release workflow rebuilt these inputs.
No new backend or production pipeline implementation is required when the
existing public helpers cover these operations. Production release, gate unlock,
key export, unrelated devices and external filesystem writes remain excluded.
The already-authorized exact-source nonpublishing APK/EXE build may proceed.
New local service-entry records are under `.cache/p51-service-20261104-01/`.

### P51 Isolated Service Entry Completed And Restored

The authorized entry reused the existing metadata builder, S3 port, immutable
uploader, full readback, preflight, registration and channel CAS/restore helpers.
No backend product or workflow code changed. The original artifact-only metadata
and all three candidate assets remain byte-identical. A separate schema-2 test
registration explicitly binds the external group16 Boot, original App source and
packaging run; it is not an ordinary release-workflow rebuild or production release.

Target 30316 is registered ready with three verified assets as
`fw_945e0c02b4c1daa4f219f8ba2ce09b283292b7f413a92afd43720aadeaefd3ff`.
One intended idempotency replay returned the same release. The temporary stable
selection naturally returned full for the declared alternate 30313 fixture and
patch for the original 30313 base. Public R2-backed downloads matched the exact
291069-byte full and 1048576-byte patch originals. These were host fixture
queries, not observations of the current board or a physical OTA.

`selection-01/result.json` records `P51_TEST_SELECTION_PASS_RESTORED`:
stable revision 70 -> 71 -> 72, original pointer/settings restored; disabled
beta revision 11 unchanged. No channel remains activated for a future campaign.
The direct Node timeout, Python DNS failure and first proxy-adapter failure are
retained as separate failed attempts. The corrected proxy route succeeded without
credential rotation, production mutation or rewriting those failures.

The exact-source nonpublishing App build `41796295859`, attempt 1, succeeded
on source `792a8a372d21ff4abd056deae28ef9b8e64bec6a`; both Android APK and Windows
EXE jobs passed, Release and Pages jobs skipped. Development run `41794760486`
already passed both hosts. No duplicate dispatch occurred. Artifact IDs are
`13305708928` (Android) and `13305174904` (Windows), pinned in
`app-artifacts-01/` under the execution directory.

Both initial archive GETs hit their bounded 240-second deadlines after partial
delivery. Their closed/cleanup-complete receipts and original prefixes remain in
`app-download-android-01/` and `app-download-windows-01/`. The continuation uses
verified HTTP Range suffixes through the approved local proxy; final archive
identity and vendor APK checks must pass before any installation. Build success,
service readiness and local fixture preparation do not satisfy P5-1 4/4, 30/30,
four-hour soak or physical restoration qualification.

### P51 App Artifacts Preserved; Phone Connection Required

Both Range continuations completed with HTTP 206 and exact Content-Range. Their
unchanged 10584064-byte Android and 10338304-byte Windows prefixes plus actual
suffixes reconstruct the complete CI archives and match the pinned GitHub
digests. `app-download-android-02/`, `app-download-windows-02/` and `app-logs-01/`
preserve the originals; no CI redispatch or successful download replay occurred.

`app-verified-01/verification.json` records vendor verification of fixed signing,
Release/non-debuggable manifest, side-by-side application ID, version 1.0.72+98,
CI APK hash and both ABI native libraries' test endpoint/adaptive-v2/timing
markers. APK: 47643192 bytes, SHA256
`b0a5cd5cbb45ba7e75ad492b65d4843ef70c33fbda365abaea495c48b3ebbcf1`.
The Windows executable is x64 and equals its bundled copy; the original Windows
ZIP and EXE are both preserved. This verification reused the existing vendor
verifier and installed read-only tools, not a local Flutter build.

The single read-only private-ADB preparation at 2026-11-04T08:57:58Z found the
authorized phone serial `10ADA4197U001CK` (expected model V2312A) absent. The
original `device not found` diagnostic is retained in `phone-inspect-01/`.
No package identity, current OTA state or unlocked state was inferred. The private
server closed normally, port 5093 closed and the device lock was released.
Only fixed C/D and optical F volumes were present; SD placement remains pending.

Next action is to reconnect and unlock that original test phone over USB, without
changing the board's power/firmware or starting OTA manually. Root then reconciles
its actual installed APK and old captures before any necessary update. No new
permission question is needed. Complete recovery qualification, SD/UI collection,
upstream applicability and precise finite-campaign freeze still precede formal
four-cell/30-of-30/four-hour execution; none is claimed by this preparation.

The continuation changed only this task-note appendix and new project-local
retrieval/verification/phone-check records. No commit/push, production operation,
device install/launch/reset/flash, test-channel change or external cleanup was
performed. `continuation-02-audit.json` records output containment, closed owned
commands, retained failed prefixes, artifact hashes and absent private ports/locks.

### P51 Phone Reconnected: Bounded App Preparation

The user reports the original phone reconnected. The current root continues
under the existing authority, with one necessary test-package update only:
V2312A / `10ADA4197U001CK`, private ADB 5093, expected old fixed-signed 1.0.71+97
to verified 1.0.72+98. The existing private-ADB, capture seal and vendor-install
routes are reused. Before mutation require exact phone/old APK identity, absent
OTA service, no running test process and sealed old captures; preserve ordinary
App identity and all captures, install with `-r` without data clear, then verify
the full installed APK hash/version and unchanged originals. An uncertain install
is reconciled, not retried. The finite host window is 900 seconds with a separate
180-second install deadline and explicit owned-server cleanup. No App launch,
UI tap, radio change, MCU operation or OTA is part of this update. Outputs are
`phone-update-01/` and `phone-binding.json` under the execution directory.

### P51 Phone Updated; SD Placement Pending

The phone preparation succeeded exactly once. `phone-update-01/result.json`
records `INSTALLED_AND_VERIFIED`, installed versionCode 98 and full APK SHA256
`b0a5cd5cbb45ba7e75ad492b65d4843ef70c33fbda365abaea495c48b3ebbcf1`.
All nine old capture files passed their original seal/hash checks before and
after installation; the ordinary App identity is unchanged. There was no App
launch, UI tap, recorder ARM, data clear, radio write or OTA. Private ADB closed
normally, and the device lock was released. The initial host input rejection
(`run_id` required the existing `p35-` prefix) happened before any device command;
its source and explicit failure summary remain in
`phone-update-preflight-failure-01/`. Only the invocation ID was corrected.

`current-02/` is a fresh passive board inspection before card handling, not a
repeat of the accepted campaigns. Full current 30313 App and retained group16
Boot bytes match, current-boot confirmation/health/stack/storage gates pass and
debug freeze remains zero. SD is ready with no active OTA/storage owner, no
halt/fault or active SDIO transfer at the sample. All six owned commands closed;
no reset, halt, flash or board persistent write was requested. This is a dated
sample, not a physical restoration qualification or a guarantee against later
user actions.

`sd-ready-01/P51/` contains the exact canonical-name full and patch files from
the reviewed candidate, with `sd-ready-01/manifest.json` binding their hashes,
lengths, target and patch base. The bytes were copied only within the worktree.
Windows still exposes fixed C/D and optical F, not a removable SD volume. The
next physical prerequisite is connecting the test card with a reader while
preserving board power and without starting an upgrade. The intended new card
directory is `P51`; there is no formatting, deletion or replacement of existing
card content. Identify the actual volume and check that directory before any
card write; no unknown drive or inferred root is authorized by this note alone.

The new preparation changes are local helpers, copies, receipts and this note.
The phone write is limited to the approved side-by-side test-package update.
The only permitted PC-external automatic write is existing SEGGER native history;
all controllable subprocess/cache/temp/J-Link outputs are project-local. No Git
write, CI/network mutation, test-channel activation or production action occurred.
`phone-update-audit-01.json` binds the successful installation, nine preserved
captures, passive board originals, local SD files, closed receipts and port/lock
checks. Formal recovery qualification, SD/BLE cells and long-test freeze/execution
remain pending; neither this install nor the passive sample counts toward 30/30.

### P51-SD-ROUTE-01: Reuse The Board USB MSC Interface

The user pointed out the existing SD-as-USB-disk feature. The previous reader
request was premature: absence of a mounted volume did not establish absence of
the standard USB route. Prefer the board's native data USB connector, leaving
the card installed and preserving the existing J-Link supply/debug connection.

Read-only verification against actual App source
`18f6b3d3af0c24b1ce81573700cd61005b7c530e` confirms
`Libraries/USB_MSC/msc_diskio.h` selects `MSC_USE_SD_CARD`, not QSPI Flash.
The retained 30313 map includes linked HAL USB/MSC code; HAL initialization
starts USB and the disk callbacks access SD sectors through SDIO. USB uses
OTGFS1 / PA11-PA12, identifies as VID 2E3C / PID 5720 (AT32 Mass Storage), and
does not require the disconnected PA9 VBUS signal. The old hotplug README's
QSPI/VBUS description is not the current candidate configuration.

The approved preparation route is native USB enumeration, identify the actual
SD volume, then bounded file placement/readback in its new `P51` directory.
Windows safe eject and disconnecting only the data USB connection must precede
board-side SD upgrade; do not run host block access and board SD import together.
The existing LiveMap USB exclusion is not claimed as proof of global SD locking.
If native enumeration fails, diagnose that observation before choosing a reader.
At this check the host exposes fixed C/D and optical E/F, with no removable SD
volume; no USB connection, card write,
device action or code change was performed. This appendix is the only write,
inside the active worktree. It supersedes the reader-only prerequisite, not the
remaining recovery, collection or formal acceptance gates.

### P51 Native USB SD File Placement Complete

The user connected the board data USB after the bounded file-placement request.
The actual disk is `AT32 SD Card USB Device`, parent
`USB\VID_2E3C&PID_5720\0E31DBF910C8`, mapped to FAT32 `E:` and volume
`\\?\Volume{4f8b85af-161d-11f1-ae99-8b882b800350}\`. A read-only storage descriptor
independently confirms AT32 / SD Card / 1.00 / 0E31DBF910C8 / USB/removable.
The permitted external file boundary is only its new `E:\P51` directory and
the two named package files; no other drive or root file is in scope.

`sd-copy-01/` records exactly two exclusive-create writes, flush/fsync and full
readback matching the already-reviewed source length/SHA256 for full and patch.
The original root names are preserved, with only `P51` added. No format, overwrite,
deletion, recovery-image copy or OTA occurred. Files intentionally remain on the
card for the pending SD cells; they are not disposable host-cache outputs.

The standard Windows `CM_Request_Device_EjectW` request for that exact USB parent
returned success. A subsequent native PnP enumeration confirms the disk is no
longer connected. All file handles and owned command processes closed; the device
lock is absent. This is safe host ejection, not evidence that the physical cable
has been removed or that board-side USB/SD state has already recovered.

Next user action: disconnect only the board data USB cable, leaving J-Link supply
and the SD card in place. Do not start the SD upgrade yet. The next owner checks
post-USB device/storage state before recovery qualification or formal execution.
`copy-sd.py`, `copied.json`, `eject.json`, `result.json` and `write-audit.json`
preserve the precise route and boundaries. No Git, CI, network publication,
firmware flash/reset or acceptance result changed in this step.

### P51 Post-USB State Verified

The user confirmed physical removal of the data USB cable. `current-03/` reuses
the passive inspection entry with a fresh output label; its previous source is
preserved under `post-usb-inspect-inputs/`. Full original 30313 App and group16
Boot bytes, confirmation, advancing health, stack guard and idle SD/storage
checks pass. No reset, halt, flash or persistent board write was performed.

The additional one-byte USB read is bound to the exact retained executable:
`HAL::USB_IsPlugged` loads the literal 0x20052d18 and its actual getter loads
offset 740, giving 0x20052ffc. The raw getter opcodes and literal are verified
against the full App before using this address. Observed state is 4 (SUSPENDED),
not 3 (CONFIGURED), and native PnP enumeration has no matching SD disk. This is
actual board-side release evidence, not an inference from host ejection alone.
The original logs/readbacks and closed owned-command receipts remain in the new
directory; port/lock and write checks are recorded in `write-audit.json`.

Before SD import, verify the ordinary board file browser sees `P51` and both
copied ETU names, without selecting Start Import. Host byte verification plus
USB/SD health does not prove the already-mounted board filesystem's directory
view has refreshed. This is a no-upgrade placement check, not a fifth matrix
cell or grounds to recopy already verified files. Any missing directory should
be diagnosed before a deliberate remount/restart, not repaired by arbitrary
memory/BCB writes.

Further read-only route review confirms the existing P35 single-upgrade runner
can bind either package; no new cloud pipeline is needed. Its link-diagnostic
audit preserves the new original lines, but the older P34 formal statistics
entry expects a different snapshot/runtime envelope. Do not fabricate that
envelope or present the count-only diagnostic audit as complete P5 performance
adjudication. Exact four-cell/long-test evaluation and frozen commands remain
required before formal execution. No successful prior test was replayed and no
new OTA result, source commit, CI or production action is claimed here.

### P51-UI-01: Long Filenames Wrap Inside Fixed-Height Rows

The user confirms `P51` contains two visible files after USB removal, resolving
the board-directory visibility question. They also report that long filenames
are split over several lines inside each single file row and become crowded.
This is a user-reported visual observation, not an agent screenshot or a new
upgrade observation. Do not describe it as an unreadable/corrupt filesystem:
the two copied original byte streams already passed full host readback.

Disposition: OPEN_PRODUCT_UI_FINDING for the SD file-selection surface. Keep
the affected SD UI verdict pending and do not start import while ambiguity is
unresolved. No completed upstream acceptance is retroactively reopened.

Static source evidence is consistent with the report. At
`FirmwareUpdate::AddRow` (`USER/App/Pages/FirmwareUpdate/FirmwareUpdate.cpp`),
the parent row is fixed at `ROW_H=38`, while the label uses `LV_LABEL_LONG_DOT`
and width `LIST_W-76` with no height constraint. The bundled LVGL label defaults
to `LV_SIZE_CONTENT` height; DOT mode does not set the text-expand flag and only
inserts ellipsis when the measured text exceeds the label's own height. The
label can therefore wrap/grow to multiple lines inside the fixed parent row.
The relevant page source is unchanged between retained App source `18f6b3d`
and current HEAD. `RouteSelect::AddRow` has the same pattern, but no separate
physical RouteSelect failure is claimed.

Preferred implementation repair: explicitly size the filename label to one
font line, retain bounded horizontal ellipsis and vertical centering, and keep
the complete stored path/name unchanged for selection and the confirmation
view. Do not edit LVGL globally, shorten/rename the accepted SD files, alter FAT
handling, inflate all rows, or change OTA/package semantics to conceal this UI
problem. The implementation owner should use both actual canonical filenames
and long ASCII/CJK/shared-prefix cases in a headless/simulator layout regression:
after layout, label height equals one line, bounds fit the 38-pixel row, icons
and adjacent rows do not overlap, and selection/confirmation still resolves
the original full path and correct FULL/PATCH kind.

This acceptance root records the finding and repair oracle, not a live product
fix. Apply any repair as a separately reviewed implementation candidate, then
bind its actual dependencies and minimum rechecks before resuming the affected
SD verdict; do not modify the selected 30313/30316 images in place. No production
source, firmware, SD file, App installation, device state or frozen bundle was
changed in this review. Only this project-local note was appended; source/linked
LVGL inspection and Git comparison were read-only. No new build or visual
regression was run, so no repaired-layout PASS is claimed.

### P51-UI-01: Independent Local Review, 2026-11-04

DECIDED: the delivered list/confirmation repair passes independent local UI
review. No blocking new defect was found in this bounded change set. This
supersedes OPEN_PRODUCT_UI_FINDING for the reviewed source behavior only; it
does not make the unchanged installed 30313 image repaired, start SD import,
close P5 or replace the required candidate binding/build/device evidence.

The root reviewer did not edit product code. Reviewed the implementation handoff
`P51-UI-01-implementation-2026-11-04.md`, all four product files, all three test
files, both page lifecycles, bundled LVGL DOT/scroll restoration, actual encoder
port and downstream selected-name consumers. HEAD remains
`792a8a372d21ff4abd056deae28ef9b8e64bec6a`; the delivered source/test/font hashes
match `fixed-04/inputs.json` before and after review. The worktree remains dirty
and uncommitted. Existing unrelated changes and historical evidence are retained.
No `.trellis/` exists in this worktree; no replacement workflow was created.

Independent output base: `.cache/p51-ui-review-20261104-01/`.
The existing real-LVGL runner was rebuilt and run once with a fresh output:

```cmd
python -B -X utf8 tests/ui/test_file_browser.py --phase fixed --reuse-lvgl .cache/p51-ui-impl-20261104-01/old/lvgl --output .cache/p51-ui-review-20261104-01/regression
```

An outer Python invocation supplied `GIT_OPTIONAL_LOCKS=0` and
`PYTHONDONTWRITEBYTECODE=1`; the reviewed runner puts compiler TEMP/TMP/TMPDIR
inside its output. All commands used `cmd.exe` and the explicit active worktree.
The retained library hash and all current source/configuration bindings were
checked before reuse, rather than treating the previous summary as a new test.
`regression/commands.json` contains the seven actual compile/run commands,
working directories, logs and exit codes. All return 0; original log reports
`P51_UI_FIXED_SELFTEST=PASS checks=14820 begins=1 pops=2`. The Begin is a service
double with the work timer immediately removed, not a real import.

Results independently confirm 19-pixel labels inside 38-pixel rows, complete
text restoration through repeated DOT/scroll transitions, horizontal suffix
visibility only on the focused overflowing row, no short-name animation and
clean disappearance/rebuild/destruction. Real native encoder edit/scroll/exit,
full confirmation names, fixed type/version/button regions, reset scroll,
cancel-without-Begin and unchanged full selection paths pass. The shared helper
is justified for RouteSelect's identical row defect; its GPX path behavior is
unchanged. This is not MCU filesystem evidence.

All 11 independent PNG outputs equal their `fixed-04` counterparts byte-for-byte.
The reviewer inspected old crowded rows and the fixed PATCH top/bottom, selected
suffix, CJK and RouteSelect frames. Independent executable SHA-256:
`092eef36a88ae0742397448c2ad790ca5b894e8017ca70a57a4798a6c0c671b5`.
Its hash is not required to match the implementation executable, whose build
location differs. Exact build flags and retained library are recorded.

Review findings and scope decisions:

| ID | Disposition | Basis, direction and next owner |
| --- | --- | --- |
| P51-UI-01 | DECIDED, local repair verified | List focus and full confirmation-name oracle pass for both pages. Root owns the next source integration, exact candidate/build bindings and affected SD checks; no additional UI repair batch is required for this finding. |
| P51-UI-FONT-01 | OUT_OF_SCOPE, existing display debt | Three existing PageFactory unused-parameter compiler warnings and 118 runtime missing-U+0076 warnings match the original fixed run; zero errors. The unchanged version font renders the `v` prefix as a box while numeric versions and FULL/PATCH remain visible. Root recommends a separately scoped font correction; do not silently regenerate fonts or relabel the warning count as zero. RouteSelect's existing 48-byte navigation display-metadata cap is also unchanged; it is not the full file-path buffer. |
| P51-UI-WORK-01 | OUT_OF_SCOPE, existing progress-page display debt | The unchanged `CreateWorkUI` name label still uses content-height DOT and may extend into the progress bar. A bounded service-double probe found the same name bounds y=106..162 and bar y=148..163 with a supported 63-byte name and an explicit 47-byte old-cap display control; percent bounds y=176..197 are separate in this case. This is not evidence of a newly introduced expansion regression. Root recommends a separate bounded work-name layout repair, retaining full identity and unobstructed progress, with an original-vs-fixed page regression before closing that issue. |

`work-probe.cpp` includes the existing test adapter and actual page source; it
does not create a replacement framework. `probe/commands.json`, `build.log`,
`run.log`, `work-full-name.png` and `work-old-cap-control.png` preserve its two
successful commands and observations. The control changes only the display text
to the previous buffer limit; it is not claimed as execution of an old firmware.
Probe compile warnings: 3 existing unused-parameter warnings; runtime warnings
and errors: 0. No Step/Apply/Stage, filesystem package access or device call ran.
The unrelated existing work-page defect does not invalidate the bounded
list/confirmation repair or authorize changing its scope during review.

The tracked product diff passes `git diff --check` (three LF/CRLF advisories,
not compiler warnings). Production GCC/Boot/AC5, standalone Win32 simulator,
CI, real package/filesystem, new candidate generation and device/OTA verification
remain NOT_RUN in this review. No old P1/P3/P4/P2-5 result was reopened. Before
P5 execution, root must bind the reviewed UI into the actual new candidate and
recompute affected dependencies; never rewrite existing 30313/30316 assets or
claim the host executable is the installed firmware.

Output audit: `audit.json` hashes the 47 generated evidence/probe files, binds
review inputs and the nine successful commands, and records 11 matching PNGs.
All controllable writes were prechecked within the active worktree: this note
and the new review output base, including compiler temporary files. Reparse
parents were rejected; Git optional index writes were disabled. No product
source, original evidence, package, SD file, external path or installed state
was modified; no commit/push/CI or cleanup was performed. Final audit also
checks the note and audit file themselves without rewriting original evidence.

### P51 UI Follow-Up: Independent Review, 2026-11-04

DECIDED: P51-UI-FONT-01 and P51-UI-WORK-01 pass the bounded independent local
UI review. No blocking defect was found in the delivered follow-up. These two
items were brought into local implementation scope by the user's follow-up
dispatch; their former OUT_OF_SCOPE disposition no longer describes this batch.
The original list/confirmation/RouteSelect repair remains verified. This does
not constitute a production build, installed-image claim or P5 acceptance.

#### Evidence Attribution Correction

The previous review's description of the `v` warning as a product display defect
was too broad and is withdrawn. The unchanged production
`OtaUpdate::Session::FormatVersion` returns `3.3.13`, without `v`; the earlier
service double supplied `v3.3.13`. The 118 original warnings and screenshots
prove missing U+0076 when that test input is rendered with the 24 font, not the
actual product formatter's spelling or an observed board defect. The root
should have checked this service boundary before making that attribution.
The prior list geometry, path and lifecycle observations are not invalidated
by this formatter-only discrepancy. All original logs and records are retained.

The implementation disclosed and corrected the mismatch: the test runner now
extracts and links the verbatim product formatting function, preserving it in
`format_version.cpp`. Root compared that generated text with the unchanged
source, including its bounds/termination behavior. The current UI intentionally
adds `v` in its own display buffer, as requested in this follow-up, and leaves
the numeric value, formatting service and version gates unchanged. Therefore
this is verified support for the requested prefixed presentation, not proof
that an earlier installed firmware had the synthetic test's missing prefix.

#### Reviewed Scope And Results

Root reviewed the localized FirmwareUpdate version-font selection, scrolling
text helpers, ShowConfirm/StartImport/FinishImport and disappearance/release
paths, plus the expanded test oracle and formatter extraction. The page-local
font descriptor copy uses native fallback; all 12 shared font C sources remain
byte-identical. The 124-pixel version column fits the tested formatter boundary
values without placeholder glyphs, wrapping or caption overlap. Ordinary numeric
glyphs retain the existing large font; longest uint32 representations select
the existing smaller family. This tests display coverage, not OTA admissibility
of arbitrary version codes.

The work-name viewport remains 186 x 19 pixels. Long names scroll horizontally
without focus, short names remain still, and the complete path passed to the
Begin double is unchanged. Start resets scrolling and status color. The scoped
status viewport also prevents the PATCH success text/type collision found by
the implementation's first follow-up run. This is within the dispatched
working/result visible-field requirement, not an OTA-state-machine change.
Working, projected success/failure, consecutive inputs and page lifecycle tests
preserve separated progress/type/detail/button regions and clean animations.

Source HEAD remains `792a8a372d21ff4abd056deae28ef9b8e64bec6a`, with local dirty
implementation. Current FirmwareUpdate.cpp SHA-256:
`e646c2724e7bae1b6bab5010b4353b6be230515844530c850b21219e624d243c`.
All test/product/font/configuration bindings agree with the implementation's
`fixed-04/inputs.json`; the other previously reviewed product files are unchanged.
The original overlap baseline, PATCH assertion failure and `lv_color_eq` test
compile failure were read and retained, not replaced by the successful run.

Independent evidence: `.cache/p51-ui-followup-review-20261104-01/`.
One fresh local run used the existing runner:

```cmd
python -B -X utf8 tests/ui/test_file_browser.py --phase fixed --reuse-lvgl .cache/p51-ui-impl-20261104-01/old/lvgl --output .cache/p51-ui-followup-review-20261104-01/regression
```

The outer invocation set `GIT_OPTIONAL_LOCKS=0` and
`PYTHONDONTWRITEBYTECODE=1`; the runner contained TEMP/TMP/TMPDIR. All commands
used cmd.exe and this explicit worktree. After a conversation/runtime
interruption, process handle 70842 was unavailable. Root recovered the completed
inner command receipts, logs, PNGs and summary rather than rerunning the test.
The outer terminal completion receipt is unavailable; all seven recorded
compile/run commands exited 0 and the completed summary reports exit 0.

Raw result: `P51_UI_FIXED_SELFTEST=PASS checks=30543 begins=9 pops=2`.
The nine Begin calls are path-recording doubles; every work timer was removed
before advancing LVGL, and no Step/Apply/Stage or real import ran. Compiler
warnings: 3 existing PageFactory unused parameters. Runtime warnings, compiler
errors and runtime errors: 0. The complete original list/confirmation/RouteSelect
regression still executes, including native encoder scrolling and cancellation.

All 20 independent PNGs match the implementation's final PNGs byte-for-byte;
seven unchanged list/RouteSelect frames also match the prior independent review.
Root inspected normal/max versions, work-name start/suffix, PATCH success and
failure frames. Independent executable SHA-256:
`3936a55d1e83ba1fd63af0525401e60a0740caf288eca8525ddddf22e6a499de`.
`audit.json` binds the 57 generated files, exact source inputs, shared library,
seven command receipts, screenshot comparisons and the interruption limitation.

#### Boundary And Next Action

Root did not change production code or the implementation handoff. The only
review writes are the new evidence directory (including compiler temporaries
and generated formatter) and this appended task note. Canonical paths and all
parent reparse attributes were prechecked; the final audit includes ignored
outputs, not just Git status. No controlled external output, cleanup, original
evidence rewrite, Git mutation, CI, package generation or device operation was
performed. Product diff and note whitespace checks pass with Git LF/CRLF
advisories kept separate from compiler warning counts.

Both follow-up display items are closed for the reviewed local source; no
additional implementation round or third reviewer is required for this batch.
Root next owns authorized source integration, production candidate build and
exact new firmware/package/restore bindings, then the minimum affected P5
execution. Production GCC/Boot/AC5, standalone simulator, CI, package generation,
real filesystem/phone/SD/board/OTA and formal acceptance remain NOT_RUN here.
Existing 30313/30316 images and unrelated P1/P3/P4/P2-5 results remain unchanged;
do not overwrite those assets or replay their successful observations merely
because this UI review is complete.

### P51 UI Source Committed And Production Targets Compiled

2026-11-04: the user said to proceed after root's completed follow-up review.
Root committed only the nine reviewed UI/test/implementation-handoff files as
`b871d57e66645f43b29a8006a58ca6a3692951f3`, tree
`74f3bbffe4e237a491aa643d9d7481769d29cb38`, on the existing local task branch
`dev/flutter/p51-timing-20261104`. No branch switch, amend, push, main change or
unrelated staging occurred. `commit.json` under the new output directory binds
the exact committed worktree bytes. All 55 other pre-existing dirty/untracked
files were byte-checked unchanged before this intentional task-note append.

Evidence directory: `.cache/p51-ui-delivery-20261104-01/`.
Build directory: `.cache/p51ub/`.
The thin local `run.py` reuses the existing P34 owned-command and contained
environment helpers, the generated production CMake entry and the canonical
`firmwareCMakeOptions('p34-v2-candidate')` definition. It does not replace the
build system, key loader or packaging pipeline. The source commit and build
each ran once; continuation messages did not replay either operation.

Production-target compile result: PASS, not an installable candidate. CMake
Release configure, both `X_Track_App_GCC` and `X_Track_Boot`, GNU size and the
existing build-profile validator all exit 0. Toolchain: Arm GNU 13.3.Rel1;
SOURCE_DATE_EPOCH=1786320000; compiler cache OFF; all profile test injections OFF.
The short project-local build uses CMAKE_OBJECT_PATH_MAX=240 because this
worktree's Windows response-file path limit had already been evidenced during
restore preparation. This deliberate local-path difference from CI's 1024 is
recorded; no external short directory or source flags workaround was used.

Configure warnings/errors: 0/0. Compile/link warnings/errors: 641/0. The full
warning log is retained, including wchar_t ABI, unused parameter and existing
library/platform diagnostics; matching a historical total is not a claim that
every warning was independently proved unchanged. These are not the three
warnings of the separate headless UI test and must not be reported as such.

GNU size output:

| Target | text | data | bss | dec |
| --- | ---: | ---: | ---: | ---: |
| App | 612836 | 940 | 558664 | 1172440 |
| Boot | 14720 | 4 | 9780 | 24504 |

The App raw binary is 615208 bytes, SHA-256
`73248f3fac8a68745a2098dbc725b6ee1b2499d10e8fb4b40ff44b1ea002b89a`,
modified 2026-11-04T12:12:24.207107Z. The ordinary source Boot binary is 14724
bytes, SHA-256
`5842ff3e19ba9e1eaaea10f27e825c7b6efc278b200531014b0dba61264f6594`,
modified 2026-11-04T12:12:19.426358Z. `build-result.json` records all eight
ELF/HEX/BIN/MAP lengths, hashes and timestamps; exact commands/configuration,
original diagnostics and closed command receipts are in `build/`.

Neither binary may be installed for P5: the App has the default source key,
no protected key binding and an unfinalized 96-byte fw_header reservation; the
ordinary source Boot is not the retained external group16 Boot. No private key
was read/exported and no package was generated. The original 30313/30316
assets, retained device state and protected CI/service receipts remain intact.

### P51-NEW-SOURCE-01: Protected Candidate Build Capability Gap

DECIDED: a bounded implementation change is required before new candidates can
be produced. This is a tooling capability gap, not another UI product failure
or missing-credential diagnosis. No failed CI dispatch was needed to establish
it, and no existing protected run should be blindly repeated.

Concrete evidence:

- `.github/workflows/firmware-build.yml` package-candidate job is explicitly
  packaging-only; it has no ARM compiler/build step and skips the ordinary build.
- `.github/scripts/firmware-candidate.mjs::candidateAdmission` accepts only
  version 3.3.16. Its metadata states the old executable is unchanged and the
  target is a header-only derivation from original CI.
- `Tools/ota/p51-package.py::resolve_inputs` binds source `18f6b3d`, original
  30313 bytes, the fixed 30316 target hash/timestamp and old reference stream.
  Substituting the new binary/manifest is not supported and would violate that
  original lineage. Preserve this working legacy mode and its old input file.
- The existing keyed-build helper supports protected rehearsal/production,
  while this candidate route correctly requires publish/rehearsal/check_bindings
  false. Fabricating a different mode or running an uploading ordinary rehearsal
  is not an acceptable way to obtain artifact-only new-source outputs.

Preferred minimal direction for a separate implementation owner: extend the
existing protected artifact-only entry with an explicit reviewed new-source
variant, reusing the existing GCC/key, finalization, reference encoder, native
decoder and metadata helpers. Keep the legacy archived-original mode unchanged.
Bind the exact source commit, profile, protected key build and approved external
group16 Boot. Return the new baseline/target App and matching ELF/MAP plus full,
base-bound exact-1MiB patch/reference, recovery and complete provenance. The
baseline used for SD selection must also contain the repaired UI; merely
changing the upgrade target leaves the user choosing files through the old UI.
Choose and verify a fresh forward version pair before dispatch, without reusing
or overwriting the already bound 30313/30316 identities.

Required oracle: credential-free positive/negative admission, source/base/key
mismatch rejection, immutable old inputs, artifact-only job graph and no
cloud/publishing credential leakage; then exact-source protected compilation,
native full/patch/recovery reconstruction, complete source/key/Boot provenance
and verified private cleanup before upload. Do not weaken production/rehearsal
gates, export keys, patch key bytes from an old ELF, substitute the ordinary Boot
or create a second general release pipeline. Root retains independent review;
the next decision is assigning/authorizing that bounded implementation agent,
not re-requesting the existing CI credential or device permissions.

P5 freeze, new protected dispatch, new asset service registration, installation
and physical matrix remain unexecuted until this capability and candidate
bindings are available. Unrelated accepted observations remain reusable only
under their real dependencies; no new four-combination or long-test PASS exists.

Delivery audit completed before another conversation interruption. Its lost
outer process handle was reconciled from complete `audit.json`, not rerun:
1181 project paths checked, all seven Git/build commands have successful closed
receipts, no unexpected external write observed. Controlled build/log/cache/
temporary outputs remain in the two named worktree directories. The sole
external writes are the previously authorized task Git object/ref/reflog and
`D:/github/my/E-Track/.git/worktrees/source1` metadata for this nine-file commit;
automatic Git maintenance was disabled. No hook/global configuration, main
worktree/index/ref, remote, device, SD or old evidence was modified. This note
is the only subsequent intentional change among the preserved task records.

### P51-NEW-SOURCE-01: Independent Local Review Completed

2026-11-04: root independently reviewed the bounded implementation handed off
in `P51-new-source-implementation-2026-11-04.md`. Result:
LOCAL_INDEPENDENT_REVIEW_PASS, with no blocking findings in the reviewed scope.
This closes the local implementation-review step, not the protected execution,
candidate binding or P5 acceptance. No further implementation batch is requested.

Reviewed base HEAD remains `b871d57e66645f43b29a8006a58ca6a3692951f3` on
`dev/flutter/p51-timing-20261104`; the new-source implementation remains
uncommitted. Evidence: `.cache/p51-new-source-review-20261104-01/`.
`source-inputs.json` and the closing `audit.json` bind all 11 implementation/test/
handoff files to the implementer's `final-02.json`. The reviewed UI/product paths
remain unchanged from HEAD, with no untracked product inputs. The archived v1
manifest retains SHA-256
`f07b239edcae98736cac220fa111e302560809ebc10ad9db8289bcdc256573c9`.

The concentrated review covered explicit mode admission, exact source/workflow/
baseline provenance, canonical forward versions, protected artifact-only gates,
the single keyed compilation and two/optional-three header finalizations,
external group16 Boot versus ordinary compile-only Boot, native full/patch/
recovery verification, metadata drift rejection and process-owned cleanup before
the explicit public upload set. Existing archived-original behavior is retained;
no product UI, protocol, filesystem or version-gate repair was made by root.

Root executed the four selected host commands once through the existing P34
contained-environment/owned-command helper. The interrupted outer handle was
reconciled from completed original receipts, not by replaying commands:

| Original result directory | Selected result | Exit | Elapsed seconds |
| --- | --- | ---: | ---: |
| `node/` | 167/167 candidate/workflow/profile tests | 0 | 39.033 |
| `python/` | 13/13 packaging tests | 0 | 209.387 |
| `keyed/` | 17/17 key-wiring tests; 139 unrelated explicitly skipped | 0 | 19.936 |
| `reference/` | 8/8 reference tests | 0 | 1.627 |

Total: 205 selected host tests passed, no command timed out. Exact argv, cwd,
limits, log sizes/digests and results remain in each `intent.json`, `test.json`
and `test.log`; the closing audit independently rechecks these log bindings.
Scoped implementation `git diff --check` exits 0 with eight LF/CRLF advisories.
The key-wiring log retains one Node SQLite ExperimentalWarning and the expected
redacted compiler-error negative case; these are not a failed production build.
The native all-assets verification reports zero compiler warnings/errors.

The actual reference search and native decoders ran. The separate synthetic
pipeline integration reuses the exact search recipe, then re-encodes and checks
full consumption and reconstruction; its search selector and keyed compiler are
test doubles. Its 12 native all-assets cases pass, including distinct full-start
selection, exact-byte positive results, guards/workspace lifecycle and zero
prepare/program calls on rejected inputs. Root rehashed all eight prepared assets
and raw BIN/ELF/MAP identities against the original SELFTEST metadata. The patch
and reference are byte aliases of exactly 1,048,576 bytes. These public-key,
synthetic-version fixtures are not protected-compiled UI or installable assets.

All 34 actual native process receipts confirm WindowsJob tree closure without
cleanup errors, including the injected timeout. The retained empty active marker
and literal `fixture` private header belong solely to the deliberate
`active-keyed-*` rejection fixture; they are not real protected key residue or a
live process. A first closing-audit attempt expected TAP `#` summary markers,
while Node emitted its spec reporter markers. It stopped before writing the
audit; root corrected only that matcher, recorded the failure in `audit.json`,
and did not rerun tests or modify original logs.

Boundary audit: 642 output files checked under the review directory and 48 new
workflow-test fixture directories in `.cache/firmware-workflow-tests/`. Existing
host_io normalized-path/reparse-parent guards were applied before writes and
during the audit. HOME, APPDATA, LOCALAPPDATA, temporary and cache directories
were contained; known possible Vite cache locations were checked. No unexpected
external write was observed. This is a controlled-output/cache audit, not an
asserted whole-machine filesystem trace. Root's only tracked-file edit in this
review is this appended task record; unrelated dirty work and old observations
were preserved. No commit/index mutation, push, protected dispatch, credential
retrieval, upload, formal candidate generation or device operation occurred.

Next owner: root. Integrate only the reviewed paths under existing effective
authority; check occupied identities and recovery feasibility before selecting
fresh B/T and optional F. Bind the eventual reviewed execution commit and run the
existing protected artifact-only `new-source` entry, retaining gate=false and
publish/rehearsal/check_bindings=false. Inspect actual ARM toolchain/build,
warnings/errors, source/key/group16 provenance, exact-reference/native receipts
and real private cleanup before binding candidates. Linux toolchain extraction,
protected ARM CI, concrete version reservation, formal assets, recovery/device
binding and the P5 physical matrix remain NOT_RUN. This local review neither
requires unrelated historical replay nor closes those downstream obligations.

### P51 New-Source Delivery Continuation

2026-11-04: the user explicitly directed root not to stop between autonomous
steps when user intervention is unnecessary. Continue the already delegated
source/CI/candidate preparation chain, retaining all production and device
preconditions. Reuse `dev/firmware/p51-packaging-20261104` and its existing
firmware-rehearsal policy; do not add a branch policy or alter reviewers/gates.
Root will fast-forward that remote branch from its reconciled evidence commit
`7f965c6ded4162ffd7aedd7c8730a7956244be0c`, preserving the prior packaging run.

New receipts: `.cache/p51-new-source-delivery-20261104-01/`.
Read-only `prepare-03` confirms no active firmware workflow, unchanged required
reviewers/four branch policies and repository/rehearsal/production gates=false.
GitHub firmware tag/release inventory has no 3.3.17/18/19 occupation; isolated
test-service `service-01` lists 28 releases, maximum version 30316, with no
mutation requests. Root selects F=3.3.17, B=3.3.18 and T=3.3.19 for this source
candidate. Both starts include the reviewed UI; F has a truthful distinct
identity for FULL selection, while B is the exact PATCH base. Same-source
finalized images remain compatible with the existing bound-backup/restore route;
actual per-image recovery bindings and device health must pass before installation.

Two preparation failures were reconciled without any mutation: `prepare-01`
received EOF on its first GitHub GET; `prepare-02` found the remote at the known
root evidence commit rather than the earlier packaging commit. Its SHA matches
the retained `commit-evidence/result.json` and is an ancestor of current HEAD.
No third-party branch change, overwrite, force push or replayed dispatch occurred.
The reviewed implementation plus this root note are the only planned commit
paths; unrelated dirty files remain outside the index.

### P51 New-Source CI Failed At Reference Synthesis

Root committed the 12 reviewed implementation/test/handoff/task-record paths as
`db049b6b2b9e0bc0ff0c534d52b686494b7d704c`, tree
`44805a995a1b62b6d22a92ae268bc73fb45928fa`. All 54 unrelated dirty files were
byte-preserved. A first commit was rejected solely because the global debug
statement hook matched a public test's success sentinel. Root verified that
single line and unchanged staged bytes, then applied the hook's debug-only
exception for that one commit; secret scanning remained enabled. No hook/global
configuration was edited. `commit-01` failure and `commit-02` success remain.

The exact source was fast-forward pushed to the existing packaging branch.
GitHub proxy TLS/EOF failures stopped two pre-dispatch read stages before POST;
bounded HTTP/1.1 probes showed the proxy route failed while direct API TLS worked.
Root selected process-local NO_PROXY for api.github.com only, without changing
system networking. `dispatch-03` made the only actual dispatch, run
`41849745315/1`; root supplied the already user-delegated protected approval.
No policy/reviewer/gate change or second dispatch occurred.

Actual result: CI FAILURE, confined to new-source reference synthesis. Source
admission, contained Arm GNU 13.3.Rel1 checksum/extraction and the 50 Node/13
Python Linux regressions passed. Real keyed GCC configure, App/ordinary-Boot
build and size passed: 641 compile/link warnings, 0 compiler errors. Warnings
are preserved, not hidden or automatically proved identical to historical ones.
The ordinary Boot remains compile-only, never a replacement for group16.

The reference search consumed its 256 unique measurements without finding exactly
1,048,576 bytes. Original near misses were 1,048,575 and 1,048,577 bytes. The
source-package subprocess exited 1 without timeout; no candidate metadata or
full/patch/recovery package was created. Private cleanup and evidence upload
passed, and all three actual compiler process groups closed cleanly.

Artifact `13335076821`: 1,815,505 bytes, SHA-256
`c7ab23cd19071b4ba053d0cab44b647878407af0832926e948b0eae7225c72f0`.
The archive, workflow logs and 302 rehashed extracted originals are retained in
`.cache/p51-new-source-delivery-20261104-01/download-01/`. The independent failure
analysis and a separate finite 61-new-measurement count-neighborhood probe are
in `failure-analysis-01/` and `reference-probe-01/`. The latter also found no exact
witness; it did not run CI, access the key, alter the codec or create encrypted
packages. The prewritten success verifier was NOT_RUN because this failed run
does not meet its admission conditions.

Finding `P51-REFERENCE-SEARCH-01` and the concrete input hashes, implementation
direction, invariants and regression oracle are in
`P51-reference-search-remediation-2026-11-04.md`. Return only this bounded search/
failure-diagnostic repair to an implementation owner; keep the reviewed UI,
archived-original mode and old asset identities unchanged. Do not blindly rerun
the same deterministic CI or install its partial artifacts. This is a tooling
failure, not an observed MCU/UI failure or P5 physical verdict.

Root exhausted the existing handoff routes before asking for intervention:
the tool tree has no live implementation agent, and cc-connect discovery reports
no binding for this chat. One implementation-owner routing/authorization is
required; the old explicitly bounded child scope is not silently expanded.
After that handoff, root can independently review/self-test evidence and resume
the existing CI/candidate chain without new per-step requests.

Controlled logs, caches, downloads, extraction and diagnostic files remain inside
the active worktree. The only external writes were the previously authorized
task Git objects/ref/reflog/index paths; shared main HEAD/index/config were checked
unchanged. No encryption key export, system proxy/daemon change, service mutation,
device operation, SD rewrite, historical replay or P5 freeze occurred. New failure
notes remain local pending the next scoped documentation delivery.

### P51 Reference Search Repair Independently Reviewed, 2026-11-05

Root resumed the implementer's completed batch without starting another agent.
Result: INDEPENDENT_REFERENCE_REPAIR_REVIEW_PASS for the local repair, no blocking
finding. This does not reclassify failed run 41849745315 or assert a new protected
candidate/P5 result. The three code/test edits and handoff are bound to
`.cache/p51-reference-search-impl-20261104-01/final.json` at base `db049b6b`.

Independent evidence: `.cache/p51-reference-search-review-20261105-01/`.
Root inspected the complete diff, checked the actual code/handoff digests and
byte-verified 774 original delivery files plus 55 unrelated work files unchanged.
AST checks confirm the old search, patch stream/encoder/strict decoder, legacy
input resolver, packaging and native process/decoder functions are unchanged.
New-source alone selects the adaptive strategy; both manifests, workflow, keyed
build/admission helpers and product UI are unchanged.

The implementer's 209 selected host tests and 112 closed process receipts were
independently checked from originals; 139 unrelated Vitest tests remain explicitly
skipped. Root additionally executed the four focused scheduler/cache/diagnostic
tests successfully. This is not another 209-test campaign or a native/MCU rebuild.

Root replayed the real final scheduler with the four original input/cache sets.
All selected cached points still counted against 256; no missing measurement was
silently re-encoded. The selected witness was freshly encoded and strictly
verified for each case, including truncated/tail negatives. Results were exactly
137/177/26/229 unique selections with original raw/compressed identities. The last
case consumed 192 first-seed measurements and then selected seed 8. Each case's
11 actual native decoder originals, source hashes, observations and process
closure were independently evaluated, not redundantly executed.

The two-sample real-input exhaustion record reports reference-search and
REFERENCE_SEARCH_BUDGET_EXHAUSTED, with no selected stream/success assets.
The earlier count/salt-only proposal failure remains retained. No codec padding,
budget/deadline increase, private-key export, gate relaxation or device operation
was used to obtain this local result.

Next: root will commit only the reviewed repair/handoff and related root records,
then preflight the intended version pair with that exact commit timestamp and
the retained real GCC raw image. That is a diagnostic prediction, not a substitute
for the next CI's actual keyed build/raw identity. Only after a legal bounded
witness is demonstrated will root proceed to one exact-source protected run.
Linux timing, actual new build/reference/native receipts, candidate/recovery
binding and P5 remain downstream checks. Existing authority is retained; no
per-step user intervention or new implementation agent is required at this point.

### P51-REFERENCE-SEARCH-02: Next Bound Input Exhausts Adaptive Budget

Root committed only the six reviewed code/test/handoff/root-record paths as
`b1422489a3cb5a56428f5e640513d195ca29e46f`, tree
`880ae72af11349d82dae9011213d4e0a6bf62945`. All 54 unrelated work files remain
byte-identical. No hook exception was required. The commit has NOT been pushed;
the existing remote candidate branch still points to `db049b6b` as observed in
the read-only preparation. No new protected dispatch or approval occurred.

The exact-next-input preflight then failed, so candidate preparation is NOT_READY.
This does not erase the preceding independent verification of the four fixed
regressions or its 209 original test results. It adds a new, actually executed
counterexample to delivery readiness before spending another protected CI run.

Evidence under `.cache/p51-reference-search-review-20261105-01/`:
`next-inputs/failed.json`, `next-inputs/reference/search-report.json`, all 256
individual measurement records and `preflight-01/predict.{stdout,stderr,closed.json}`.
The unchanged raw GCC image from run 41849745315 was finalized with the current
commit's actual timestamp 1793813128, B=3.3.18 and T=3.3.19. These are diagnostic
predictions using a retained compiled image, not a new ARM build or admitted
firmware. Both images are 615132 bytes:

- Base SHA-256: `69f83b830e10b7d4247714183c48747f9599b6b27f6dd08e14482c9b9b66d03c`.
- Target SHA-256: `83f5cc00ae8f279f18f92a4e298b0f62535fb6c7c3d56ad027857401dbd06c2a`.

The adaptive v2 search charged 192 seed-7 and 64 seed-8 measurements, found no
exact witness, and reported REFERENCE_SEARCH_BUDGET_EXHAUSTED at reference-search.
The closest result was count=210016, seed=7, salt=4, ETU length 1048577. Total
measured encoding time was about 988.7 seconds; preflight search/verification
elapsed 997.53 seconds on this Windows host. The 1800-second diagnostic command
exited 1 normally, without timeout; its job and process tree are closed. These
times are not Linux CI measurements and do not justify changing its 660-second
source-package timeout silently. No selected stream, encrypted package or
successful candidate metadata was created.

Read-only GitHub protection and test-service occupation checks passed. The first
local preparation wrapper imported a different module named runner, colliding
with pipeline_cloud's import; root fixed only the task-local wrapper import and
used a new receipt directory. That host entry failure made no cloud mutation and
did not restart the running preflight. No production/validation implementation
was modified by root beyond committing the independently reviewed bytes.

Return the new fixed counterexample to the external implementation owner under
P51-REFERENCE-SEARCH-02, with the original 256-sample failure reused rather than
re-executed. Preserve all earlier failures/successes. Do not change timestamp,
version, seed or rerun the unchanged search merely to obtain a lucky pass; do not
hardcode a known witness or widen budget/timeouts without an evidenced proposal.
The existing remediation note now carries the next-input hashes and oracle.
Per the user's explicit direction, root will provide a remediation prompt and
will not open a child agent. No device, SD, service mutation, additional CI or
P5 freeze has been performed.

### P51-REFERENCE-SEARCH-02: Independent Follow-Up Review

2026-11-05: root independently reviewed the implementer's isolated-frontier v4
batch at base `b1422489a3cb5a56428f5e640513d195ca29e46f`. Result:
INDEPENDENT_REFERENCE_FOLLOWUP_REVIEW_PASS, no blocking finding in this bounded
repair. This does not erase the v2 next-input failure, v3 regression or original
protected CI failure. No new product implementation was authored by root.

Evidence: `.cache/p51-reference-followup-review-20261105-01/`.
`execute.py` reuses the existing owned process and output guards; `review.py`
independently binds the final source/handoff/plan hashes and preserves all 5225
prior evidence files plus 55 unrelated work files. All 269 original process
closures were checked; no active native marker remained. Nine nonadaptive
encoder functions are AST-identical to the committed baseline. Existing
manifests, package/native functions, keyed build and workflow are unchanged.

The 19-test original successful suite and expected failure receipts were reviewed,
including retained python-01 timeout-fixture failure and rejected v3 old-header
search. Root freshly executed the six scheduler/cache tests, all passing.
Eight real charged-cache scheduler replays found the original exact witnesses
in 62/126/69/159/157/197/38/249 unique selections, with no missing cache point
newly measured. Each selected stream was freshly encoded, strictly decoded to
the exact target, and tested for rejection of truncation/trailing bytes. Each
case's eleven original native checks and decoder source bindings were reviewed,
not repeated. No new cold/native/ARM campaign is claimed.

The three declared variants reproduce the plan's exact version/timestamp input
bytes. The fixed cold original reports 62 fresh encodings, zero cache reuse and
313.479 seconds for search plus strict verification on Windows. Five final main
traces match the v2 prefixes of 46/137/177/25/229 points. The new frontier cannot
change main anchors/visited decisions; both histories share one physical cache
and 256-point budget. Its at-most-26-point allocation and observed overlap are
checked separately, not summed into an inflated unique count.

Root will commit only the two reviewed implementation/test files, implementer
handoff and these related root records, then test the next commit's actual
timestamp at the already selected F/B/T=3.3.17/18/19 using retained raw GCC bytes.
That prediction remains distinct from an actual new CI build and is mandatory
before the existing authorized artifact-only dispatch. No input timestamp/seed
will be selected to chase a known witness. No protected CI, service mutation,
device operation or P5 acceptance occurred in this review.

### P51 New-Source Candidate: Actual CI And Original Review Passed

Root committed only the five reviewed code/test/handoff/root-record files as
`1430c8ff7f3bcd9a35bfe158ba697b99021f75f2`, tree
`0d2bb53f248f9c8f90bef052f2ea7069ec4de8bb`; 54 unrelated dirty files were
preserved. The unchanged hooks passed without an exception. Root then cold-tested
that commit's actual timestamp 1793820855 at F/B/T=3.3.17/18/19. It found a strict
exact witness in 140 measurements, 527.130 seconds, with no change to seed,
timestamp, budget or deadlines. This was a prediction, not an ARM build.

After unused-version/remote/protection/service reconciliation, root fast-forwarded
the already-authorized candidate branch and dispatched exactly one protected
artifact-only run `41900439548/1`, with one user-delegated approval. It succeeded.
No branch-policy or gate/reviewer change was made. Repository, rehearsal and
production boot-chain gates remain false; post-CI channels/releases exactly
match the pre-CI service snapshot. No publication or ready registration occurred.

Artifact `13359301400` is 6586031 bytes, SHA-256
`a906221d772a0df5b6b069a250a5b8f951b97371bacd1a8be4b0d77c51988e0b`.
Root retrieved 252 original members, checked their allowlist/path/archive binding,
and passed all seven independent artifact evaluations. The raw GCC image and all
three finalized inputs exactly match the prediction, including the 140-point
v4 witness. Selected compressed bytes were independently re-encoded and strictly
decoded. Original protected-key/native evidence has 12 checks and 16 closed
process receipts, all passing, with zero native warnings/errors. Private cleanup
passed and no private key/header was exported. Linux Node 50 and Python 19 tests
pass; GCC diagnostics contain 641 warnings and zero errors, not zero warnings.

The exact originals and provenance are archived in
`docs/ota-exec-notes/P5-1-new-source-candidate-2026-11-05/`. Its README records
the actual App/full/patch/reference/recovery/group16 identities and limits. The
ordinary Boot built by CI is compile-only. Previous 30313/30316 assets and every
failed search/run remain unchanged. P51-REFERENCE-SEARCH-02 is closed for this
candidate preparation; it is not a universal witness-existence guarantee.

No MCU, phone, SD, 30/30, four-hour or P5 formal acceptance action occurred. Next
execution preparation must use the actual new assets, rebind both rollback
fixtures and validate current device/collector state before installing anything.
Do not reuse the old 30313/30316 fixture bindings or claim P5 from this CI result.
