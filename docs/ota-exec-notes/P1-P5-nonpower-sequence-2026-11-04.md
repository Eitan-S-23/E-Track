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
