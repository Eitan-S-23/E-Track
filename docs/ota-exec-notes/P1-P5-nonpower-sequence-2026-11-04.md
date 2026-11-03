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
