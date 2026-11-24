# BOOT-CP-10: Early Exception Design For Independent Review

Status: DESIGN_PROPOSED, not implemented or independently approved.
Owner: Codex root. Authorized writable root: D:/github/my/E-Track.
User approved design/review followed by isolated implementation, host validation
and GCC App build. Independent design review is required before implementation.
No production default, frozen contract, Boot handoff, device, CI or publication
change is included. No existing evidence is to be regenerated in place.

## 1. Bound Baseline And Problem

Use the source-bound .cache/p34-sha-candidate/f snapshot as the implementation
input, copied into a fresh .cache/p34-early-fault/f after design approval. Its
App ELF reproduces30274/30275 outside the96B finalized firmware header; provenance
is in .cache/p34-app-handoff/result.json and preinit-analysis.json.
Do not substitute unrelated dirty root source files or assign a future OTA
version/package during this prerequisite repair.

Existing Boot sets App VTOR before switching MSP. The primary App HardFault
vector invokes libc, RTT, serial and backtrace paths before App startup has
initialized data/BSS/objects. _impure_ptr overlaps Boot's copy buffer; the BSS
readiness flag cannot identify this phase. This is an existing initialization
gap, not a demonstrated grouping fault or an observed crash.

Relevant baseline entry points:
- MDK-ARM_F435/cmake-generated/cmake/sources/startup_at32f435_437_gcc.S:
  App primary vectors and Reset_Handler; Boot uses a DIFFERENT startup file.
- cmake/linker/x-track-app-gcc.ld.S: primary vectors at App origin, fw_header
  at origin+0x400, then .text; current vector bytes0x20c.
- USER/main.cpp and its generated CMake source: Reset data/BSS/constructors
  precede main; main calls ota_vtor_check/capture before Core_Init and setup.
- setup initializes RTT and LVGL before HAL_Init.
- USER/HAL/HAL.cpp: diagnostic serial begin, FaultHandle_Init, then remaining
  hardware/display/watchdog/timer initialization.
- USER/HAL/HAL_FaultHandle.cpp and its actual generated GCC source:
  FaultHandle_Init initializes cm_backtrace and sets s_faultHandleReady.
- Libraries/OTA/ota_vtor_check.c: early main entry expects primary App VTOR.
- Libraries/cm_backtrace/cmb_cfg.h: baseline CMB_USING_OS_PLATFORM is disabled.

Generated-source selection and macro values must be bound again before applying
the design; changing only USER source while compiling an old generated copy is
not implementation.

## 2. Selected Architecture: Two Immutable Flash Tables

Keep the fixed primary table at OTA_APP_ORIGIN. It remains the table selected by
Boot and by App SystemInit, so it works before the first App instruction and
before RAM initialization. Preserve primary MSP, Reset_Handler, table size and
all reserved-zero entries.

For the opt-in experimental App, replace these PRIMARY entries with a common
assembly-only early exception handler:
NMI(2), HardFault(3), MemManage(4), BusFault(5), UsageFault(6), SVC(11),
DebugMon(12), PendSV(14).

Keep SysTick(15) and external IRQ entries unchanged: Core_Init/HAL initialization
requires normal tick and initialized-peripheral interrupts before promotion.
This relies on the existing Boot handoff disabling/clearing external interrupts
and SysTick, then App data/BSS/constructors completing before Core_Init enables
them. Audit actual enable ordering and handler dependencies; an early external
IRQ that violates this premise is a design blocker, not permission to waive it.
SVC/PendSV must not be used by startup before promotion in the selected build;
reject an RTOS-startup configuration rather than silently breaking scheduling.

A SECOND Flash table has the original baseline vector entries, including the
existing HardFault_Handler. Derive both tables from the same canonical entry
list; do not maintain an independently hand-copied interrupt list. Match every
entry in artifact validation, allowing differences only in the eight named
primary exception slots. The runtime table itself must match the original list.

Place runtime vectors in a dedicated read-only linker section AFTER fw_header,
aligned to1024 bytes for the131-word table. Do not add a second table to the
fixed primary .isr_vector output section. Add assertions for alignment, exact
size, Flash bounds and no fw_header overlap. Primary vectors remain0x20c bytes;
fw_header stays exactly96B at+0x400. Account for extra table and alignment bytes
in final image/OTA capacity checks; no size-saving claim is made.

Flash tables avoid mutable RAM vector contents and require no readiness token
before startup. The old BSS flag can still serve existing runtime diagnostic
logic, but it has NO role in deciding the early-vs-runtime vector table.

## 3. Early Handler Contract

Implement in standalone Thumb assembly, not a compiler-generated C handler:
disable maskable interrupts, then branch forever to a local label. No stack
access, global load/store, libc, RTT, serial, RTOS, backtrace, heap, watchdog feed
or manual reset request. No WFI dependency is necessary.

The software frame is0 bytes. NMI is not claimed to be masked. Further legal
exception nesting only adds architectural frames, with the same early target
for the eight entries. Account for core, optional floating context and alignment
for both Boot-MSP and App-MSP phases. A running independent watchdog may reset
the device naturally; otherwise early failure halts indefinitely until external
reset. This is explicit failure behavior, not an upgrade timeout guarantee.

Tradeoff: faults during initialization lose the previous attempted full log or
display, in exchange for not using uninitialized facilities. Full diagnostics
are retained once runtime promotion completes. This tradeoff needs reviewer
confirmation. Do not add an emergency RAM log without a separate memory-owner
and initialization analysis.

## 4. Runtime Promotion Point And Ordering

Keep FaultHandle_Init in its existing position as dependency initialization.
Do NOT switch vectors there merely because s_faultHandleReady becomes true.
Add an explicit FaultHandle_EnableRuntimeVectors call at the successful END of
HAL_Init, after display, watchdog, timer and all selected diagnostic dependencies
are ready, before returning to setup/App_Init. For the baseline configuration,
the diagnostic paths are single-threaded and cm_backtrace OS integration is off.

Before permitting the call, verify from the exact build:
1. Reset completed .data/BSS initialization and all C++ constructors.
2. Core_Init completed; the diagnostic serial object and UART setup are valid.
3. RTT init/nonblocking setup and cm_backtrace_init completed.
4. Any enabled display, reboot-button and watchdog dependencies are initialized.
5. No scheduler-dependent backtrace route is enabled without an explicit proof.

The promotion routine checks Thread mode and requires the current VTOR to equal
the primary App table. Unexpected state fails to the early halt path, not a
best-effort transition. It does not authorize arbitrary table addresses. A second
promotion is not needed; repeated HAL_Init is outside the selected lifecycle.

Save PRIMASK, mask configurable interrupts, execute DSB, write the aligned known
Flash runtime-table address to VTOR, then DSB/ISB and restore PRIMASK. Runtime
dependencies must already be established BEFORE the VTOR store. NMI immediately
before the store uses the safe early table; after the store it uses the fully
initialized runtime table. The transition must not depend on NMI exclusion.

No Boot instruction or handoff ordering changes. No write to BCB/copy policy.
App SystemInit still chooses the primary table at every reset. Audit all later
VTOR writes and prevent any normal path from undoing promotion unexpectedly.
The explicit existing FileBrowser reboot/Boot-transfer path is not treated as
an ordinary runtime VTOR value; it remains outside this isolated experiment.

## 5. Compatibility And Scope

ota_vtor_check and ota_handoff_capture run at main entry before promotion;
their strict primary-address semantics and original handoff evidence remain
unchanged. Do not broaden them to accept any App Flash address.

After promotion live VTOR intentionally differs from OTA_APP_ORIGIN. New host
artifact checks must bind that exact runtime-table symbol and immutable contents.
Any future live collector/admission gate expecting a permanent primary address
needs an explicitly versioned opt-in adapter before device use; do not disable
or weaken historical checks. This design/build batch contains no live collector
or device operation and does not declare that compatibility already resolved.

Use an experimental CMake option default OFF, scoped to GCC OTA App only. OFF
must preserve the previous App build behavior and reproduce its raw BIN where
the source/toolchain/environment binding is unchanged. Boot, legacy and AC5
remain unaffected. No option may silently enable early vectors in production.

## 6. Validation Matrix After Design Approval

- Host model: reset/dirty RAM selects primary; pre-switch NMI and post-switch
  NMI select only the intended table; unexpected mode/table refuses promotion;
  saved PRIMASK is restored; initialization failure never promotes. Models must
  not be presented as executed MCU exceptions.
- Generator negatives: missing/duplicate primary list, altered reserved entry,
  unapproved exception substitution, table mismatch and header overlap fail.
- GCC OFF/ON App builds in new isolated output directories. Keep known build
  warnings visible; do not rebuild Boot or its closed host fault campaign.
- ELF/BIN/MAP verify both table contents, Thumb targets, sizes, alignment, primary
  MSP/Reset and fw_header location. Raw extraction must match the bound build.
- Disassemble early entry: no BL/BLX, SP adjustment/access, RAM access or runtime
  dependency; only the approved mask/local halt instructions. Prove runtime
  HardFault still reaches Dump/Trace/Hook rather than being optimized away.
- Check promotion's actual call site, dependency order, barriers and exact VTOR
  store. Bind generated startup/CMake sources, not merely intended USER edits.
- Recompute the limited two-MSP early-exception budget from the new binaries;
  preserve the previous runtime diagnostic paths and analyze any changed frame.
- Report new image size/ABI/stack and all provenance with no performance claim.

Do not mutate source-bound previous results, reuse old ELF evidence for new code,
assign candidate/backup/recovery identities prematurely or issue OTA packages.

## 7. Decision Requested From Independent Reviewer

Review this design, not a nonexistent implementation. Consolidate any blockers
with invariants, preferred minimal change, exact test oracle and next owner.
Specifically decide whether primary exception selection, immutable table layout,
end-of-HAL_Init promotion, early-halt tradeoff and live-VTOR compatibility boundary
adequately close BOOT-CP-10 without changing Boot handoff behavior.

Missing dependencies or contradictory startup ordering must remain explicit.
No implementation, build or device command is requested from the reviewer.
Once design is approved, root can implement and build under the user's existing
authorization without asking that same permission again. Actual deployment,
successor production governance and finite hardware plan remain later gates.

## 8. Approved Design And Isolated Implementation

The user relayed the original reviewer's DESIGN APPROVED decision with
EARLY-01..04 constraints. This supersedes DESIGN_PROPOSED above, but does not
mean implementation approval or flash permission. The existing authorization
was used for the following isolated implementation and self-tests only.

Canonical source-bound snapshot: .cache/p34-early-fault/f; prepared.json binds
the3276 original files, generated modifications and added files. No production
source or previous candidate/Boot/evidence was modified. Source edits are generated
by Tools/ota/p34_early_fault.py; promotion implementation and predicate are
Tools/ota/p34_early_fault.cpp and p34_early_fault_policy.h. The original USER/main
and USER/HAL/HAL.cpp are the REAL App inputs; the fault implementation is the
generated HAL_FaultHandle source. Actual compile_commands were checked, not an
unused generated main copy.

Changes confined to the snapshot:
- One shared vector-entry include drives both Flash tables; only the approved
  eight primary slots substitute p34_early_exception. Both tables keep131 words.
- The App linker retains primary vectors/fw_header and places the1024-aligned
  second table after the header, with size/alignment/overlap/Flash-bound assertions.
- The standalone assembly early entry is exactly cpsid i followed by a local
  branch loop; it never accesses SP or globals, calls runtime helpers or feeds WDT.
- HAL_Init calls p34_enable_runtime_vectors at its end. Promotion checks mode,
  exact primary VTOR and diagnostic dependencies; failure enters the early halt.
- A snapshot-only backtrace readiness accessor verifies init_ok and nonzero
  stack/code sizes, covering cm_backtrace_init's otherwise silent early return.
- Readiness also checks the selected Serial5 binding, UART5 enable/transmitter,
  RTT upstream count/buffer/size and nonblocking-trim mode. The early vectors do
  NOT consult this RAM state; the predicate is used only after normal startup.
- Unreviewed display-diagnostic/automatic-reboot/debug-off and OS-backtrace
  configurations fail compilation rather than silently inheriting this proof.

### Executed Evidence

| Evidence | Result and interpretation |
| --- | --- |
| tests/result.json |66 pure promotion-policy combinations;1 original vector-list positive and6 malformed-list negatives PASS |
| promotion-tests/result.json |16 scenarios compiling the ACTUAL promotion source with host CMSIS mocks: refusal, saved PRIMASK, IDVDSR ordering and before/after-store NMI table selection PASS. Pointer width is adapted to uintptr_t for the host; this is not ARM exception execution |
| dependency-tests/result.json |512 combinations of the exact generated readiness expression PASS; tests mock the nine predicate terms, including the serial binding which is constant in the actual pinned configuration |
| off2/result.json |GCC App OFF build reproduces the617588B bound raw baseline exactly; no early handler, promotion or runtime-vector symbols leaked |
| on/result.json |GCC App ON build619272B, +1684B; no Boot/legacy/AC5 build or device action |
| validation.json |New ELF extraction, original-symbol-resolved runtime table, exact eight-slot primary differences, early instruction bytes, header placement, real compile entries and runtime HardFault calls PASS;8 corrupted-table/placement negatives rejected |
| initialization-evidence.json |Bound source ordering and selected new .su frames; phase2 aggregate remains UNKNOWN, not a stack PASS |

Runtime table is0x08010800; primary is0x08010000; fw_header remains exactly
0x08010400..0x08010460. Table validation resolves ORIGINAL entry symbols in the
NEW ELF, not old absolute handler addresses. Runtime HardFault still calls
Dump, Trace and Hook. Actual promotion assembly saves PRIMASK, masks configurable
interrupts, DSB, stores the exact runtime-table address, DSB/ISB, restores PRIMASK.
Before that store the primary table remains safe; after it the checked dependencies
are established. Unexpected mode/table/dependencies takes the early halt branch.

OFF has638 pre-existing compile/link warnings and0 errors. ON has640 warnings
and0 errors. The two added warnings are NOT hidden: (1) Serial5's pinned macro
produces a tautological pointer comparison; this is a compile-time binding in
the actual configuration, not dynamic object validation; (2) the added promotion
TU inherits the existing App -fshort-wchar options and gets the same2-byte-vs4-byte
wchar linker warning as many existing App objects. It exposes no wchar interface,
but the warning remains for review. No broad ABI flags or warnings were suppressed.

### Preserved OFF Reproduction Failure

The first off/ build compiled successfully but failed its strict BIN equality
gate (617580B versus617588B). Four LVGL __FILE__ strings embedded the shorter
new source path, shifting linked addresses. Its configure/build/tool receipts
and original outputs remain untouched; no PASS result was manufactured.

Tools/ota/p34_early_fault_build.py is the corrected route. It adds
-fmacro-prefix-map for the new snapshot prefix to the bound old prefix, affecting
macro strings only, not actual filesystem paths. Fresh off2/ then matched every
baseline byte, and on/ used the same mapping. This is why OFF was rebuilt; it
was not a blind retry or weakened comparison. Actual source and output paths
remain in the new project-local snapshot and are recorded in compile_commands.

### EARLY-02 Dependency And IRQ Ordering

Source-bound startup completes data/BSS and constructors before main/Core_Init.
Core_Init sets priority grouping4 and starts the SysTick counter only after its
BSS initialization. The observed SysTick priority is0, NOT the Boot priority15.
setup initializes RTT/nonblocking mode and LVGL before HAL_Init. Serial5 begin
is the supported UART5 constructor path; it configures GPIO/UART before enabling
RX and returning. cm_backtrace init uses no heap; its failure to establish a
nonzero stack size is caught by the new accessor. Existing display/auto-reboot
diagnostic options are rejected when ON, and OS backtrace is disabled/guarded.

For retained non-fault primary vectors, the inspected source order is:
- UART objects/ring buffers are constructed before begin; IRQ callback state
  starts initialized, and Bluetooth's optional hook is installed explicitly.
- Timer_CallbackFunction is assigned before NVIC/peripheral interrupt enable;
  the final HAL timer starts only after power/encoder/audio initialization.
- EXTI callback is stored before line and NVIC enable.
- Display DMA is reset/configured after screen initialization, before IRQ enable.
- Usb_Init enables NVIC before usbd_init, but the reset peripheral's global gate
  remains disabled. usbd_core_init binds class/descriptor/endpoint state, clears
  status and masks, then enables the peripheral global interrupt at the END.
  This relies on the same normal-reset/peripheral-state premise, not arbitrary
  debugger entry with a live inherited USB controller.

These are static ordering observations, not device IRQ injections or proof of
every peripheral failure behavior. USB/media callback paths and other active
IRQ callees must still be included in the aggregate stack analysis below.

### EARLY-03 Two Separate Stack Stages

Stage1, App VTOR with Boot MSP: the new image's eight fault entries all resolve
to the verified zero-frame early assembly handler. Under the previously reviewed
Boot reset/IRQ premises, its conditional2568B comparison remains conservative
against4096B; it no longer executes the uninitialized App diagnostic graph.
Boot mismatch log/hold is still Boot code. The actual vector/entry bytes, not a
runtime RAM flag, establish early selection before Reset_Handler executes.

Stage2, App MSP through HAL_Init before runtime promotion: budget8192B from the
new App linker, but aggregate upper bound remains UNKNOWN. New .su observations
include main96B, HAL_Init24B, promotion16B and diagnostic-ready8B. SysTick's
software frame is0; UART wrapper frames0 lead into HardwareSerial::IRQHandler8;
TMR4 wrapper8 and HAL callback8 lead to further work; USB wrapper0 leads into
usbd_irq_handler16 and class/media callbacks. These are NOT complete chains.
Observed priority levels include0 (SysTick/DMA/default timers),1 (UART/USB),2
(HAL timer), so a provisional5x108=540B architectural nesting allowance cannot
be added to a guessed thread number and declared safe. Active call chains,
indirect callbacks and full legal nesting remain to be closed on this ELF.
No Boot2568B reuse or zero-frame-early-handler shortcut is used for stage2.

EARLY-03 therefore remains a real pre-use evidence gap. The new data make the
remaining task concrete: traverse Reset/Core/setup/HAL initialization and its
enabled UART/USB/timer/DMA/media callback chains against bound .su/disassembly,
then independently review the aggregate. No new build is needed for that work.

EARLY-04 remains a device gate: no live collector was changed to accept the
runtime VTOR, and no old App/physical backup/recovery is presumed repaired.
This batch does not close BOOT-CP-10 or authorize any flash/OTA operation.

## 9. Call-Graph Follow-Up And USB Startup Dependency (2026-10-04)

This is implementation-agent evidence, not independent acceptance. The existing
ON/OFF source snapshots and build receipts were not edited or rebuilt. No device,
Boot, Git commit/push or project-external write was performed in this follow-up.

### Reusable Offline Analysis

`Tools/ota/p34_early_stack_graph.py` reads the bound ON disassembly and BIN.
It slices main through the actual HAL_Init call at 0x08045fb2, retains the
full HAL_Init graph, and resolves constructor calls from the actual Flash
preinit/init arrays. Six parser checks cover direct edges, indirect/tail edges,
phase-slice escape, cyclic reachability termination and missing targets.
`.cache/p34-early-fault/stack-graph1/result.json` records 681 directly reachable
initialization functions with 112 unresolved sites, and a deliberately broad
primary-vector superset of 109 functions with 51 unresolved sites.
These counts are an inventory, not an upper bound or product-defect count.

`Tools/ota/p34_early_stack_callbacks.py` binds the nine MSC class and ten
descriptor pointers to their actual initialized-data bytes and new ELF symbols.
It adds conservative source-bound serial, TMR4, encoder and audio callback
unions. Two negative checks reject non-Thumb table entries. Stack-return idioms
are classified without assigning a stack-frame budget.
`.cache/p34-early-fault/stack-callbacks1/result.json` records 86 classified sites
across the image, 681 initialization functions/100 remaining sites, and 213
primary-vector-superset functions/37 remaining sites. Added callees explain why
function counts increase. Disabled IRQs have NOT been silently removed from the
persisted superset. Local switch tables, remaining virtual calls, library frames,
recursive paths and actual NVIC nesting still need analysis. Total remains UNKNOWN.

The first inventory execution failed before writing its result due to a duplicate
Python dictionary keyword; the unbound runner was corrected and rerun. The
successful result binds the corrected runner. Old results were not overwritten.

### EARLY-05 | NEED_EVIDENCE | SD Backend Can Be Entered Before Startup Completes

Owner: root/implementation provides this finding; original reviewer decides the
minimal follow-on startup-dependency remediation scope. EARLY-02 requires stopping
the affected configuration on an initialization dependency contradiction rather
than silently expanding implementation. ON remains a built, unapproved artifact;
the same startup order exists in the baseline, not a new double-vector defect.

Source facts, all under `.cache/p34-early-fault/f/`:

- `USER/HAL/HAL.cpp` calls Usb_Init before SD_Init. The ON disassembly confirms
  these calls at 0x08040e24 and 0x08040e30; vector promotion is at 0x08040ec4.
- `Libraries/USB_MSC/msc_diskio.h` selects MSC_USE_SD_CARD, not QSPI. The earlier
  USB-controller/class initialization ordering is insufficient to establish its
  storage backend's readiness.
- `MDK-ARM_F435/Platform/Core/at32_sdio.c:190` publishes card information before
  card selection, speed and bus-width work. A nonzero capacity is not evidence
  that sd_init or the encompassing SD.begin/HAL::SD_Init has completed.
- `USER/HAL/HAL_SD_CARD.cpp:209` sets SD_IsReady only after SD.begin and subsequent
  work. `SdFat.h:397` returns the address of the constructed card member, so
  `SD.card() != NULL` is not a readiness check.
- `msc_disk_capacity` checks capacity, not SD_IsReady. `bot_scsi_capacity` ignores
  that function's return value; `bot_scsi_test_unit` checks transfer length, not
  backend readiness. `bot_scsi_read10` uses cached block bounds, then calls
  `msc_disk_read`, whose SD branch calls readBlocks without a readiness check.
- ON `msc_disk_read` reaches the virtual call at 0x08014d74. The linked
  `SdioCardEX::readBlocks` at 0x080142b0 can call SdioCard::begin on read failure
  at 0x080142d2. Thus omitting SD initialization/recovery from the possible USB
  call graph would also understate the IRQ analysis. This is a static path,
  not a claim that a real device has executed reentrant initialization.

Bounded discriminating test:

`Tools/ota/p34_early_usb_preinit.py` extracts five exact function bodies from
the bound source into a new generated include, then compiles
`tests/boot/test_p34_early_usb_preinit.cpp` with native GCC, -Wall -Wextra -Werror.
All generated inputs, native executable and original command/log receipts live
under `.cache/p34-early-fault/usb-preinit1/`; compile/run exit codes are zero.
The four-case witness covers zero capacity, capacity known but backend not ready,
ready backend and an out-of-range request. In the second case a valid READ10
reaches the backend once; backend rejection still propagates USB_FAIL. Controls
reject before the backend for zero capacity and out-of-range requests.

Result: `EARLY_USB_PREINIT_WITNESS cases=4 backend_called_before_ready=1`.
Host structures/stubs do not prove MCU ABI, real enumeration timing, electrical
behavior, memory corruption or a field failure. The test demonstrates the missing
software readiness gate for the modeled intermediate state; it does not assert
that every cold boot or every USB command fails.

Preferred bounded direction for review: separate cold-start USB activation from
its current early position, so host storage access cannot run during the initial
SD initialization attempt; explicitly reject unavailable media in MSC capacity,
read and write paths using established post-runtime-initialization readiness.
A failed SD attempt must not publish usable capacity or initiate SD recovery from
the early USB interrupt. Preserve normal diagnostics, Boot handoff, BCB, grouping,
and OFF baseline evidence. Do not merely enlarge the stack or assume the host
will not enumerate. Runtime hot-plug/reinitialization and ISR recovery semantics
need an explicit scope decision rather than being silently redesigned here.

Verification oracle for a follow-on design: valid host requests at each initial
SD phase, including failure, cannot enter a not-ready storage backend; after a
successful publication they can. Include capacity/test-unit/read/write and an
unavailable-card case, preserve expected enumeration/removal behavior, and bind
new source/ELF if implementation changes. Then resume the remaining EARLY-03
thread/IRQ frame and nesting analysis against the chosen configuration.

BOOT-CP-10 remains open. No existing Boot host fault matrix needs reopening.

## 10. EARLY-05 Approved Remediation Batch (2026-10-05)

The original reviewer directly reviewed section 9 and authorized the bounded
EARLY-02 prerequisite remediation in the existing isolated experiment. This
does not authorize devices, production integration, release or a change to the
Boot handoff. EARLY-05 is DECIDED as to direction/scope, not independently closed.
The original four-case defect witness remains unchanged.

### Implementation And Cold-Start Scope

`Tools/ota/p34_early_usb_gate.py` prepared a fresh snapshot at
`.cache/p34-early-usb/f`. Only four files differ from the previous early-vector
snapshot: HAL.cpp, msc_diskio.cpp, msc_diskio.h and msc_bot_scsi.c. All behavior
changes are guarded by P34_EARLY_FAULT_VECTORS, and storage/protocol changes also
require MSC_USE_SD_CARD. Boot, startup/vector architecture, linker, BCB, APPLY
policy, SDIO transactions and the QSPI backend are unchanged.

- ON calls SD_Init to completion before Usb_Init, retaining the earlier QSPI
  initialization. The SD result does not force App termination. USB can enumerate
  with unavailable media; neither a fixed delay nor nonzero capacity establishes
  completion. OFF retains the original order and code path.
- A narrow C-callable p34_msc_media_ready(lun) uses HAL::SD_GetReady. There is no
  second readiness variable. SD capacity, read and write functions reject not-ready
  media before touching their backend. Capacity outputs are cleared on failure.
- TEST UNIT READY, READ CAPACITY, READ FORMAT CAPACITIES, READ10 and WRITE10 check
  readiness. Both capacity commands check the capacity function's return and reject
  zero geometry before subtracting one or publishing a response.
- Unavailable-media failure clears cached geometry, valid response length and
  pending block length, marks failure and reports NOT READY/MEDIUM NOT PRESENT.
  Existing BOT command/data handlers handle stalls or failed CSWs. Untransferred
  bytes are not deducted from the residue. Subsequent read/write chunks still
  traverse the bottom-level gate; a first-command-only check is not used.
- Actual ready-media read/write errors report MEDIUM ERROR with ASC 0x11/0x0C,
  rather than fake success or absent-media success. Existing backend recovery is
  not removed or bypassed by this change.

Self-review identified that the first helper also invalidated otherwise valid
geometry after ready-media I/O errors, unnecessarily preventing a normal retry
without another capacity query. The initial snapshot, 40-case test and OFF/ON
builds are preserved as intermediate evidence, not silently updated.
`Tools/ota/p34_early_usb_retry.py` creates `.cache/p34-early-usb-r2/f`, with only
one further predicate change inside p34_msc_failure: geometry invalidation is
limited to NOT READY. Response length, failed status and residual handling still
apply to real I/O failures. This is the selected remediation revision.

### Host Matrix And Evidence Reuse

`tests/boot/test_p34_early_usb_gate.cpp` uses the original MSC type/constants
header with platform includes removed, and extracted actual modified function
bodies including the dispatcher, CBW decoding, data callbacks, stall and CSW
paths. USB endpoint and SD hardware objects are host stubs; this is not target
ABI, real USB enumeration, interrupt timing or electrical testing.

The first matrix has 40 passing cases. It covers each selected command for cold
zero capacity, known capacity before readiness, failed initialization and no card;
ready success; valid geometry followed by readiness revocation; both zero-capacity
response paths; invalid ranges; read/write continuation after revocation; write
revocation before its first backend block; actual read/write failure; and readiness
revocation between the command check and the lower read gate.

R2 regenerates the same extracted functions with its single helper change and
adds two successful read/write retries after a ready-media I/O failure. Result:
`EARLY_USB_GATE_PASS cases=42`. The unchanged 40 scenarios still pass. Compile
and execution receipts both have exit 0; compilation uses -Wall -Werror and has
an empty diagnostic log. Inputs, generated include/harness, executable, commands
and logs are bound in `.cache/p34-early-usb-r2/tests/result.json`.

The initial `tests` CLI was once invoked before asynchronous snapshot preparation
finished; it failed on missing prepared.json before compiling or writing test
evidence. It was rerun after preparation completed. Dependent build/test stages
were subsequently awaited before use; no PASS receipt was made for that invocation.

The executed OFF control is `.cache/p34-early-usb/off2/result.json`: its 617588B
BIN exactly equals the original bound baseline, SHA-256
65cec892c2e93db3aa5d9d7288cb9bc834cdee648c824e6cd96b788ba091ce2e.
It has 638 existing compiler/linker warnings and zero errors. The intermediate ON
BIN is 619564B, with 639 warnings/zero errors. Relative to the prior 640-warning
early-vector ON build, normalized warning messages add none and remove one
unused-lun warning. Original warning logs, including wchar ABI warnings, remain.

R2 reuses that exact executed OFF control because its only additional predicate
is inside the ON-and-SD-only helper, wholly excluded from OFF preprocessing.
`control-reuse.json` points directly to the original receipt and binary. The exact
receipt copy under R2/off2 is for the build runner's control check, NOT evidence
of an OFF build executed in R2. The artifact validator checks the single-helper
delta and exclusion before accepting this reuse; no frozen receipt is rewritten.

### Remaining Boundaries

EARLY-05 implementation/self-tests are not independent closure. EARLY-03 still
requires aggregate thread/IRQ frame and nesting analysis on the selected new ELF.
In particular, ready-media read failure can still execute SdioCard::begin from
the USB path and must stay in that analysis. A readiness check is not a lock for
hot-plug/reinitialization against an already-started I/O; no such guarantee or
runtime recovery redesign is introduced here. BOOT-CP-10 remains open.

No device operation, Boot target build, old Boot fault-matrix rerun, Git commit,
push, production-default change or measured OTA speedup is part of this batch.

### Selected R2 Target And Call-Graph Evidence

R2 ON build completed: 619580B BIN, SHA-256
387a48705d81941834b6644d22da9573df3160b1717e56338cd86cdf948bcdb3.
It is 16B larger than the intermediate ON and 1992B larger than the executed
OFF control. The new USB remediation accounts for 308B beyond the previous
619272B early-vector ON image. These are image sizes, not timing savings.
R2 has 639 compiler/linker warnings, zero errors; its configuration log has no
warning. The original warning logs are retained; no warning suppression or
toolchain/ABI flag change was used.

`Tools/ota/p34_early_usb_validate.py --retry` completed with
`EARLY_USB_ARTIFACT_CHECKS_PASS`. Its 63 input bindings are recorded in
`.cache/p34-early-usb-r2/validation.json`, together with the source diff at
`source-diff.patch`. The actual HAL call sequence is SD_Init, Usb_Init,
p34_enable_runtime_vectors. Three negative order samples (reversed, missing,
duplicate) are rejected. The old executed OFF still has the old USB/SD order
and no p34_msc helper symbols; control reuse is explicitly distinguished from
a new execution.

The new ELF's primary/runtime vector comparison retains exactly the eight
approved differences, reserved zero entries, MSP/Reset meaning and fixed header
location. Runtime VTOR is 0x08010800; the early entry is 0x0801bf2a with exact
bytes 72b6fee7. All five selected commands and capacity/read/write backends have
their readiness gate in the bound actual disassembly. The linked ready-media
read recovery still calls SdioCard::begin. No old ELF is used to certify new code.

Selected compiler frames are HAL_Init24B, promotion16B, ready query8B,
capacity/read/write16B each, failure helper0B, and READ10/WRITE10 40B each.
These are standalone static frames, not a call-chain or nesting bound.

`Tools/ota/p34_early_usb_stack.py --retry` re-executed the existing inventory
analyzers against R2 and bound the wrapper, source inputs and output files in
`stack-refresh.json`. Direct initialization remains 681 functions/112 unresolved
sites; callback refinement leaves 681/100. The primary-vector superset grows
from 109/51 to 216/37 after callback refinement. Both actual USB tables and their
two negative checks remain covered, with 86 classified sites across the image.
The increase from the previous 213-function refined IRQ superset is retained,
not hidden by assuming that a ready gate eliminates every later storage path.
These are deliberately conservative inventories, not full stack closure.

Implementation handoff: original reviewer can now assess EARLY-05's bounded
remediation using R2, the 42-case matrix, original OFF anchor and new target
binding. EARLY-03/BOOT-CP-10 remain open. Runtime-VTOR collector compatibility,
finite candidate/backup/recovery identities, full stack analysis and actual
device permissions remain separate gates; this batch is not flash readiness.

## 11. R2 Review Closure And EARLY-03 Analysis (2026-10-05)

The original reviewer closed EARLY-05's approved cold-start ordering, readiness
and failure-propagation scope. No matrix rerun or firmware rebuild is required
for that closure. EARLY-05-R1 limits the retry evidence: Fixture::command resets
msc_state to IDLE before decoding the next command. The two added cases prove
retained geometry permits a new command, NOT complete BOT STALL-clear/CBW recovery.
The reviewer found no change breaking the existing clear-feature/failed-CSW path.
Do not rewrite the old 42-case evidence or generalize it to full USB recovery.

### New Offline Evidence

The selected R2 BIN/ELF and source snapshot remain unchanged. New tools only read
existing artifacts and create project-contained analysis:

- `Tools/ota/p34_r2_stack_inventory.py` and `stack-analysis1/result.json` bind
  actual virtual-table slots for SdioCardEX, HardwareSerial, TwoWire and the
  constructed ST7789 screen; they retain SD recovery and the registered date-time
  callback. Custom operator-new targets include both first_alloc and lv_mem_alloc.
  Checked local switch tables require an adjacent unsigned range guard and reject
  local entries that bypass it. Nine checks exercise the parser/bound rules.
- The only new toolchain invocation is `arm-none-eabi-nm -n -S -C` on the existing
  R2 ELF, with a command/log receipt. No compilation or device execution occurred.
- `Tools/ota/p34_r2_stack_frames.py` and `stack-frames1/result.json` handle C++
  extern-C signatures, const spelling and compiler clone names. Missing records
  are not treated as zero: a separate conservative linked-code check accepts
  only fixed stack allocation before control transfer, with no allocation-prefix
  reentry or unknown SP assignment. Ten checks cover name matching, ranges,
  missing frames, late allocation and dynamic stack assignments.
- The frame matcher was slow due to repeated canonicalization. It completed
  normally with exit 0 before an attempted interruption was delivered; no result
  was discarded or rerun. Later steps reuse the saved frame index rather than
  repeating the matching pass. Its source and result remain frozen.
- `Tools/ota/p34_r2_irq_budget.py` and `irq-budget1/result.json` add whole-routine
  inspection for nine library frame gaps, including the conditional 16B
  __aeabi_uldivmod allocation. The latter's actual preindexed store and matching
  SP release are checked. Arithmetic and missing-entry negative checks are kept.

### Conditional IRQ Software Bounds

These are conservative graph bounds, not measured watermarks. Tail calls retain
the caller's whole maximum frame, and USB callback unions can produce paths that
are not a single executable trace. That overapproximation must not be described
as a measured or exact physical deepest path.

| Entry | Software Bound |
| --- | ---: |
| SysTick_Handler | 0B |
| USART1 / USART2 / UART5 | 36B each |
| EDMA_Stream1_IRQHandler | 8B |
| DMA1_Channel3_IRQHandler | 24B |
| TMR4_GLOBAL_IRQHandler | 160B |
| OTGFS1_IRQHandler | 484B |

The USB graph still includes readBlocks and SD reinitialization. The TMR4 bound
includes encoder/buzzer/timer clock work and the uint64 division helper. No
selected bounded entry has an absent disassembly body or unresolved outgoing edge.

Under the explicitly recorded source-derived candidate IRQ set and normal
reset/reviewed Boot entry assumptions, priority bands are 0, 1 and 2. Group4 has
four preempt-priority bits and no subpriority bits; Serial's default subpriority3
does not create another nesting level. The temporary SysTick_Config priority
occurs before external IRQ setup and is replaced by explicit priority0.

Per-band software maxima are 24 + 484 + 160 = 668B. Conservatively adding five
108B hardware frames (basic32 + possible FP72 + alignment4, including HardFault
and NMI levels) yields a CONDITIONAL 1208B interrupt allowance. Configurable
fault priorities are assumed at reset0 and core early entries have zero software
frames. Final active-set completeness/temporal-priority review remains explicit.

The ELF reserves [0x20056000, 0x20058000), or8192B. Subtracting this conditional
allowance leaves a thread comparison limit of6984B, NOT a proved free-stack margin.
This applies only before runtime VTOR publication, not runtime diagnostics,
PSP/RTOS operation, arbitrary debugger state or hot-plug concurrency.

### Remaining Closure Work

The initialization graph now has709 reachable functions and71 unresolved control
sites. The larger71 count (versus69 earlier) includes newly exposed virtual paths
and conditional control checks; do not hide new edges to improve the count.
After the nine manual library checks, the outstanding initialization frame
semantics concern `__restore_core_regs`, which restores SP from an unwind context.
It cannot be assigned zero just because it lacks a conventional local allocation.

The next bounded work is initialization control, not another build: resolve
Print/LVGL callback ownership for the cold-start phase; classify shared ARM
arithmetic entry/tail regions; bind libc formatting/stream callbacks; then handle
C++ exception personality and restored-control targets from the matching ELF.
Keep the source/ELF binding and valid-state assumptions explicit. Do not prune
allocation/error/unwind paths just because normal startup is expected to succeed.

EARLY-03 and BOOT-CP-10 remain open; full_system_bound remains UNKNOWN. These
implementation self-checks are not independent acceptance or flash authorization.
No Boot matrix, R2 native matrix or firmware build was rerun, and no device,
Git write, production setting or project-external output was used in this step.

### Shared Arithmetic And Formatting Followup

The next offline batch reuses the same R2 ELF, BIN, disassembly and saved frame
index. It does not repeat the slow signature matcher, compiler, Boot campaign or
USB matrix. All new output is under `.cache/p34-early-usb-r2/`.

`Tools/ota/p34_r2_arithmetic_stack.py` records
`arithmetic-stack1/result.json`. Its instruction-level exploration follows
cross-symbol branches into the shared arithmetic bodies, models conditional
control nondeterministically, and tracks LR and saved return words. Unknown
control, stack replacement, underflow and growing-stack paths are rejected;
shared bodies are not represented as additional ordinary function frames.
Ten self-checks include conditional helper calls, shared tails, dead code,
unknown register targets, invalid SP assignment and repeated allocation.

The selected entry bounds are __adddf3, __aeabi_ui2d, __aeabi_i2d and
__aeabi_l2d at 12B each; __aeabi_dmul and __aeabi_ddiv at 16B each. Nineteen
previously unresolved control sites are classified. One site, 0x0805370c, is
unreachable from its arithmetic entry: its fragment follows an unconditional
branch, and the complete parsed image has no direct incoming reference to
0x08053708/0x0805370c. This is an entry-scoped result, not a guarantee against
arbitrary corrupted control flow.

The first runner invocation rejected the requirement that every previously
listed site be visited, before writing a result. Inspection identified that dead
fragment; the final check explicitly binds its address and incoming-reference
absence, with a dead-fragment self-check. The successful invocation returned 0.
The earlier failure was not a firmware/test-matrix failure or a PASS receipt.

`Tools/ota/p34_r2_control_followup.py` records `control-followup1/result.json`.
It retains the arithmetic whole-body bounds, verifies both single-block
SdioCardEX calls against the actual syncBlocks Flash vtable word and receiver
load sequence, and checks register_tm_clones' immutable zero literal and CBZ.
The zero guard has a passing sample and two rejected mutation samples. This
classifies 22 sites cumulatively and leaves 49 initialization sites unknown.
Neither SD recovery nor existing graph edges are removed.

`Tools/ota/p34_r2_printf_targets.py` records `printf-targets1/result.json`.
The two resolved formatting callers supply PC-relative literals for __ssputs_r
and __sfputs_r. The evidence checks the four argument sequences, preserved
callback registers, fifth-argument forwarding into _printf_common, and all
22 affected BLX sites. Both destinations are retained as a conservative union.
Two mutated argument sequences are rejected; execution returned 0.

This formatting classification is conditional on the currently resolved caller
set and the matching AAPCS callee-preservation contract. A future newly resolved
indirect caller must recheck that set; FILE output subcallbacks are NOT closed
by identifying __sfputs_r. No additional reachable functions were introduced by
these refinements, so no unexamined bodies were silently assigned zero cost.

The latest initialization inventory has 27 unresolved control sites, down from
71 before this batch. The remaining frame/control-restoration gap is still
__restore_core_regs. Print/LVGL ownership, FILE/signal callbacks and exception
personality/landing-pad/restored-control semantics require further work. The
conditional IRQ allowance is unchanged and the initialization total is still
UNKNOWN; reduced unknown-site counts are not a proof of total stack safety.

EARLY-03 and BOOT-CP-10 remain open. These are implementation self-tests, not
independent review, device readiness or measured OTA speed improvement. No
firmware, production source, existing evidence or device was changed.

## 12. Conditional Startup Bound And Review Handoff (2026-10-05)

Operating instruction reaffirmed by the user: continue the authorized work
without asking the user to restart each batch. Batch completion is not a reason
to stop. Ask only for a genuinely necessary input, external action or changed
permission boundary. This does not authorize flashing, production integration,
Git publication or project-external file writes.

The following new, write-once results bind the unchanged selected R2 image.
All paths below are relative to `.cache/p34-early-usb-r2/`.

### Phase And Callback Evidence

`cold-phase1/result.json`, produced by `Tools/ota/p34_r2_cold_phase.py`, retains
the old unsliced graph and produces a separate conditional cold-start slice.
It checks actual BSS symbols and Flash literals, the only linked filesystem
registration caller, the initial linked-list/NULL guards, GPS open-error return,
and the only startup animation descriptor producer. Five state checks include
four negatives for nonzero cache, registered filesystem and nonzero animation
var/getter fields. It leaves 678 initialization functions and 12 unknown sites.

The LVGL investigation is not a UI optimization: GPS startup attempts to open
its saved position through LVGL's filesystem interface before filesystem-driver
registration. The bound open path returns NO_DRIVER and GPS returns before
read/seek/tell/close. Initial cache invalidation is bypassed when its BSS pointer
is NULL. The backlight descriptor is zero-initialized and writes neither var nor
get_value_cb, so the guarded callbacks do not run in this initialization call.
These conclusions require the stated cold-start ownership/non-reentrancy
conditions, not an assumption that allocations or storage always succeed.
They do not apply to runtime, hotplug or repeated warm HAL initialization.

`runtime-targets1/result.json`, produced by `Tools/ota/p34_r2_runtime_targets.py`,
binds HardwareSerial's actual byte/buffer vtable words, the newly reached Print
buffer loop, standard FILE write/seek literals, the data-load image's abort
terminate handler, and the zero initial signal table. No linked custom FILE
factory or signal/terminate setter was found by its named-symbol checks.
Ownership assumptions remain explicit and need reviewer confirmation; absence
of a named setter is not a general proof against arbitrary RAM mutation.
Nine newly reached functions are inventoried instead of silently inheriting an
old scope. Three word checks include two negative samples. Five unresolved
initialization sites remain, all in exception-unwind control; restored-SP
semantics remain unresolved in this unsliced graph. The first invocation failed
before any output because an input was named HAL_I2C.cpp rather than the actual
HAL_I2C_Scan.cpp. The corrected invocation exited 0, without a firmware build.

### Contextual Thread Result

`thread-bound1/result.json`, produced by `Tools/ota/p34_r2_thread_bound.py`,
records a conditional 1692B normal-startup software bound. The previously
source-derived 1208B conditional IRQ allowance would give 2900B total against
8192B reserved, leaving a CONDITIONAL 5292B comparison margin. This is not
measured headroom, independent acceptance or an unconditional system bound.

The remaining unwind reachability was traced to one Account constructor's
exception-cleanup fragment. A normal instruction CFG cannot reach that fragment;
adding an ordinary branch into it is a negative check that must reach it.
The graph has no reachable native/forced exception initiator, __cxa_throw is not
linked, and all four linked std::__throw_* helpers consist of saved registers
followed by abort, not exception raising. Allocation-failure abort paths remain
in the calculation. Under these bounded normal-startup conditions, the cleanup
entry, unwinder and __restore_core_regs are not entered; the result does NOT
assign a zero stack frame to restored-SP code or certify arbitrary unwinding.

Two graph cycles require context rather than an arbitrary recursion limit:

- __assert_func uses the bound literal `assertion "%s" failed: file "%s",
  line %d%s%s` plus newline. Its fiprintf path cannot request float conversion.
  Float conversion remains in all other formatting contexts, including the
  conservative deepest path. Appending a float conversion is a rejected sample.
- pinMode's recursive dispatch modes are 4 and 9. Its self-call passes 3;
  PWM_Init passes 8. These linked immediate arguments select plain GPIO on the
  nested invocation. Caller frames remain conservatively counted.

The software maximum includes GPS last-track-name formatting, float conversion,
newlib big-number allocation assertion, integer assertion reporting and standard
FILE output. It is an overapproximated context graph path, not a claim that this
entire trace occurs on the device. The negative CFG/format checks both passed.

### Review Scope And Remaining Gates

EARLY-03 / BOOT-CP-10: NEED_EVIDENCE, implementation evidence ready for focused
review of the new phase/ownership/context assumptions. Root does not independently
close its own proof. Preserve previous matrices, OFF control and R2 build; no
rerun is requested just to review these host analyses.

Preferred review: verify the cold-state slices, Print/FILE/native exception
ownership, normal constructor CFG and contextual cycle handling. If a condition
cannot be established, restore that edge or mark UNKNOWN; do not tune the
expected result or silently discard allocation failures. Next owner is the
original independent reviewer, with root responsible for any scoped followup.

Final IRQ active-set completeness remains a distinct review/evidence item.
Source and graph cross-checking identifies nvic_irq_enable through QSPI EDMA,
HardwareSerial, Timer_SetInterruptBase and Usb_Init, plus inline display DMA
enable and SysTick setup. EXTI registration is not in the current startup graph;
USB wakeup enable is excluded by the bound low-power configuration. This does
not turn a caller list into an exhaustive machine-store proof. The eight-entry
IRQ set and temporal priority assumptions in section 11 remain conditional.

Both-MSP review must retain the existing Boot handoff's NVIC disable/clear and
SysTick stop before App VTOR, the vector-mismatch log/hold branch, and R2's pure
early core handlers. The prior 2568B Boot-vector calculation is not silently
substituted for a new two-stage acceptance result. Runtime-VTOR compatibility,
finite image identities and device replacement/recovery authorization remain
later gates. No new performance result or flash readiness is claimed.

Automatic handoff was checked without changing bindings: current CC_PROJECT is
codex-project, but `cc-connect relay send --to __list_bound_targets__` returned
`no binding for this chat`. No agent was contacted, spawned or assigned work.
The original reviewer therefore needs the existing user-mediated handoff or a
binding established by the user; root must not invent a target/session or bind
an unrelated reviewer. No daemon or project-external files were changed.

## 13. EARLY-03-R1 Derived IRQ Closure (2026-10-05)

The original reviewer directly reviewed section 12; no new binding or transfer
is required. The 1692B conditional thread result is accepted under its listed
conditions. EARLY-03-R2 accepts the bounded context methods, not an unconditional
system guarantee. EARLY-03-R1 identifies a real coverage gap in the eight-entry
IRQ budget: TMR4's encoder callback can enable TIM1 through Buzz_Tone/tone.
The old 1208B/2900B/5292B figures therefore remain historical conditional
calculations, not independent closure. No product fault or stack overflow was
demonstrated, and no firmware correction/build is requested.

### Added TIM1 And Fixed Point

New runner: `Tools/ota/p34_r2_irq_closure.py`.
New write-once result: `.cache/p34-early-usb-r2/irq-closure1/result.json`.

The runner binds the exact Tone_TimerHandler literal, TIM1 address 0x40010000,
priority arguments 0/1, callback BSS table and load/store offsets. The source
and linked callback route are retained, not excluded by assuming an idle encoder
or short promotion window. Group4 discards subpriority as a nesting distinction.

The shared TMR1_OVF_TMR10 entry has two callback slots. The TIM1 slot dispatches
Tone_TimerHandler. TIM10's slot remains zero under the bound cold-start registry:
only the reviewed HAL TIM4 and Tone TIM1 registrations are reachable. TIM10
flag testing and clearing stay in the function graph; the callback is not
assigned an invented target or treated as absent solely from the IRQ name.

Software maximum for the shared entry is 16B:
TMR1_OVF_TMR10_IRQHandler (8) -> Tone_TimerHandler (0) -> noTone (8)
-> digitalWrite (0). Counter/toggle and timer-disable branches remain covered.

For every candidate IRQ, the runner traverses its resolved callback graph and
checks the reachable NVIC-enable caller and timer-registration owner. The only
IRQ-derived registration is toneSetTimer -> Timer_SetInterruptBase -> TIM1.
The finite closure begins with eight seeds, adds TIM1 in round one, and adds
nothing in round two. TIM1's handler introduces no further registration.
Unknown derived-enable owners or unresolved outgoing IRQ control are rejected.
Existing source-bound inline display DMA and SysTick enables remain seeds.

The only newly reached functions relative to the eight-entry IRQ union are the
shared TMR1 entry and Tone_TimerHandler. Their bound instructions modify timer,
GPIO and Tone state, not the Print/FILE/LVGL/signal/terminate ownership used in
the accepted startup analysis. The shared entry's callback table is read-only
in its handler; this check does not claim general RAM-corruption protection.

Five self-checks cover a multi-round derived-enable chain, a cycle that reaches
a fixed point, an unclassified derived IRQ rejection, no-op closure, same-band
budget invariance and unknown-frame rejection (the chain/cycle share one case).
Execution returned 0. No old analysis tool/result was edited or rerun.

### Updated Conditional Comparisons

TIM1 is priority0 and its 16B software bound is below that band's existing24B
maximum. The now nine-entry candidate set still has priority-band maxima
24 + 484 + 160 = 668B. Five conservatively budgeted hardware frames contribute
540B, so the revised conditional IRQ allowance remains1208B. Adding another
priority0 IRQ does not add a nesting level.

`Tools/ota/p34_r2_two_msp.py` produces
`.cache/p34-early-usb-r2/two-msp1/result.json`. It binds the existing Boot
group1/group16 analysis to R2's exact primary vector slots, initial MSP and
stackless early-handler bytes. It checks the unchanged cleanup/VTOR/mismatch
ordering and the four-instruction MSP branch. The mismatch log/hold branch is
included in the inherited whole-Boot software bound, not shortened away.

| Stage | Conditional Software | Exception/IRQ Allowance | Combined | Comparison Budget | Margin |
| --- | ---: | ---: | ---: | ---: | ---: |
| Boot MSP, including R2 App-vector handoff window | 2136B | 432B | 2568B | prior4096B comparison | 1528B |
| R2 App MSP before runtime promotion | 1692B | 1208B | 2900B | 8192B reserved | 5292B |

The first stage retains the conservative four hardware-frame allowance;
R2's early core targets have zero software frame, with external NVIC/SysTick
disabled/cleared/stopped before App VTOR. The second stage uses the separate
thread and derived-IRQ analysis. These stages are not added together, and the
Boot4096B comparison is not a hardware stack guard. Both variants give the same
comparisons. No result is extended to old App images or unknown future images.

Three mutation checks reject changed initial MSP, changed early vector target,
and changed early-handler bytes. The first invocation rejected an overbroad
source-order search that included a separate test-injection function; it wrote
no result. Restricting the check to boot_handoff_to_app fixed the harness scope,
without modifying Boot or weakening its ordering requirement. The final run
returned0; frozen Boot input digests remain unchanged.

### Disposition

EARLY-03-R1: implementation evidence supplied, original reviewer owns closure.
The target is the finite derived-enable fixed point, shared-slot ownership and
updated two-MSP pairing, not a new firmware campaign. EARLY-03 / BOOT-CP-10 are
not independently closed by this note. Existing EARLY-05 closure stays intact.

No device operation, firmware compilation, package generation, Git commit/push,
production setting or project-external write occurred. These are offline
self-checks, not exception execution, a runtime watermark or an OTA speedup.

## 14. EARLY-03 Closure And Offline Use-Gate Preparation (2026-10-05)

The original reviewer closed EARLY-03-R1 and EARLY-03 for the specified artifacts
and cold-start conditions after reviewing section 13. Nine IRQ paths, TIM10's
unregistered shared slot, the derived-enable fixed point and the separate MSP
comparisons were accepted. Preserve all older failures, budgets and result
fields; full_system_bound is not changed into an unconditional guarantee.
This is not formal independent acceptance and does not authorize flashing.

BOOT-CP-10 / EARLY-04 remain NEED_EVIDENCE for actual-use compatibility and a
finite, exact candidate/backup/recovery set. The reviewer's project-local empty
file `758))')` is left untouched. Root neither repeats the read-only claim for
that review nor treats its accidental file as part of firmware evidence.

### Versioned Offline VTOR Policy

Added `Tools/ota/p34_r2_vtor_policy.py`, with profile schema
`p34-r2-dual-vectors/v1`. It is deliberately separate from frozen collectors.
The generated `.cache/p34-early-use1/profile.json` binds the exact 619580B raw R2
image and both complete 524B vector tables, not just two allowed addresses.

The classifier requires the complete expected image identity, unchanged VTOR
before/after the observation, the exact selected vector-table bytes and no
halt/reset indication. Its outcomes distinguish app-early at0x08010000 from
app-runtime at0x08010800. Neither outcome establishes operational readiness,
BCB confirmation, successful upgrade or a stable reset generation. Matching
endpoint VTOR reads alone cannot prove that no intervening reset occurred.
Existing ownership, boot-generation, clock/session and confirmation checks must
remain part of any future collector integration.

The profile is restricted to the reviewed raw R2 artifact. A finalized firmware
header changes the whole-image hash and is rejected, intentionally. The actual
candidate must receive its own exact version/package/profile binding later;
the policy does not mask the header or accept future images by address alone.
Full-image verification is an admission operation, not proposed per-sample
high-frequency throughput polling.

The compatibility audit found these historical assumptions and left them intact:

- `p34_full_trace.phase` accepts the old primary App origin and rejects R2's
  runtime table. Both behaviors are explicitly checked in the new host tests.
- `p34_boot_device.validate_snapshot` binds a historical full App hash and
  primary-only VTOR. It must not be reused for R2 merely by changing the address.
- `baud_interruption` has a primary-only readiness condition; historical
  results are not reinterpreted under the new policy.
- R2 main still performs ota_vtor_check/ota_handoff_capture before promotion.
  Those strict early checks require no relaxation.

The new classifier is callable and offline-tested, but has NOT been wired into
a live collector or run on hardware. EARLY-04 is therefore not declared closed.

### Finite Image Inventory

`.cache/p34-early-use1/images.json` records exact files and hashes where known,
and explicit unknowns instead of inheriting R2's conclusion:

| Role | Current Evidence | Use Boundary |
| --- | --- | --- |
| Isolated candidate source | R2 raw BIN, matching ELF/MAP, profile | Not a finalized OTA package; no new version assigned |
| Last recorded App | 30275 historical image hash4d248fd7e3f6db9d08afdc3712f383064779a3b732ae3b7d550a4f2c393114f6 | No fresh physical read; old preinit gap not repaired |
| Historical predecessor | 30274 image hash22a0c48da12e24e61368c1617bb9b6098a8416ab598f59dc005a2b594ea70002 | Not proof of physical backup identity |
| Physical backup App | UNKNOWN_NOT_READ | Must bind its actual payload before a device-use plan |
| Selected recovery App | NOT_SELECTED | Needs exact finalized image, matching evidence and complete restore route |
| Known-good full Boot backup | 65536B, hasha63346db0dc673dc42adf6064892c466af5c4571df53cb55fe5b6ea154c1fdf4 | Preserve exactly; no padded compact BIN substitution |

The bound isolated group1/group16 Boot build result is linked separately.
Historical App images remain useful provenance, not newly certified safe
candidate/backup/recovery images. A possible fallback to the old known-good
configuration would retain its old behavior and requires its own approved
complete-state restore route; it cannot be advertised as covered by R2 analysis.

### Execution Evidence And Next Gate

`Tools/ota/p34_r2_use_gate.py` generated the profile/inventory and executed the
policy tests in a project-contained child environment. Its first invocation
failed before output because a Boot input-manifest record was treated as a
list; this was corrected without touching the bound Boot manifest. The final
invocation succeeded with `R2_VTOR_POLICY_PASS cases=22`.

The 22 checks cover early/runtime classification, unrelated and misaligned
addresses, changed VTOR, wrong/short table bytes, halt/reset indications,
wrong/truncated/header-modified image, altered profile, and unchanged historical
collector behavior. Original command, cwd, exit0 and log digest are retained in
`policy-tests.json` and `policy-tests.log`, bound by `result.json`. These are
executed implementation host checks, not an independent EXECUTED PASS signature.
No old stack or Boot matrix was rerun to create those receipts.

The finite inventory is not yet deployable. Remaining work is final candidate
and recovery selection, finalized artifact/profile binding, actual physical
backup identity, and a versioned live collector with unchanged non-VTOR gates.
Physical identity acquisition and any later replacement/recovery action must
meet their own device authorization and host-output preflight; no read, halt,
reset, flash, phone install or device connection was attempted here.

EARLY-03 stays closed within the accepted scope. BOOT-CP-10 / EARLY-04 remain
open rather than treating this offline preparation as actual-use readiness.
All new outputs are under the project root; existing evidence and the reported
accidental empty file remain unchanged. There is no new OTA performance result.

## 15. Read-Only Capture Adapter And Next Identity Gate (2026-10-05)

Continued without another batch-start request. Added a separate adapter in
`Tools/ota/p34_r2_vtor_capture.py`; the frozen policy and collectors remain
unchanged. The callable accepts an already-owned reader with explicit
address/length/remaining-time arguments. It does not open a connection, load a
native DLL, reset, halt, resume, write target memory, reinstall an App or retry.

The admitted raw-R2 image has a fixed 619580B read scope. A complete capture
uses at most157 reads: core/VTOR before,152 bounded image chunks, one full
524B selected table, and VTOR/core after. Unknown initial VTOR stops after two
reads; an initial halt/reset marker stops after one. Every completed read gets
an address/length/digest record. A failure retains the completed/failed read
ledger in CaptureError and starts no replacement operation.

The adapter checks a monotonic overall deadline and passes remaining time to
each read. It cannot interrupt a reader that ignores its timeout contract:
the future native owner must enforce that independently, with an owned finite
process/runtime. This host test is not evidence that J-Link native deadlines
have been enforced. Full-image reading is admission-only, not a per-packet
or high-frequency OTA timing loop.

Equal endpoint VTORs are not promoted into boot-generation evidence. Successful
results explicitly retain boot_generation=NOT_ESTABLISHED,
operational_readiness=NOT_ESTABLISHED and native_route_validated=false. The
already-bound non-VTOR confirmation/session/clock checks must still be retained
when an actual device route is connected. No former startup or successful OTA
observation is reused as a current boot epoch.

`Tools/ota/p34_r2_vtor_capture_tests.py` exercises26 fixture cases: both legal
phases, reader failure, short/non-byte reads, timeout, backwards clock, initial
and final reset/halt indications, vector transition, table/image corruption,
unrelated addresses, invalid deadlines and oversized/changed profiles. It
checks exact stop counts, no automatic retry and the absence of a readiness
claim. `Tools/ota/p34_r2_capture_check.py` executed this test child with contained
home/temp/cache paths and recorded exit0, command and log digest under
`.cache/p34-early-capture1/`. This is new adapter coverage, not a rerun of the
closed Boot, USB or stack campaigns.

### Concrete Next Step

The next useful observation is actual device identity, not another OTA or APK
installation. A host-only Windows device/process query found the expected
J-Link USB identifier and no competing debugger. No J-Link connection or
target-memory operation was executed during that query.

Proposed next boundary, pending the required device/native-history permission:

- One finite read-only identity pass for the existing board, with a sole owner,
  uncached reads, bounded workers and preserved failure outcomes.
- Read Boot[0x08000000,0x08010000) and App within
  [0x08010000,0x08100000), validating headers before deciding exact payload size.
- After confirming the memory-mapped NOR route is already usable, inspect the
  candidate/backup/recovery slots at offsets0/0x100000/0x200000 within the existing
  NOR mapping, each at most1MiB. Do not enable XIP or call firmware routines to
  make an unavailable route work. A failed prerequisite remains a recorded gap.
- Read only directly available status needed to associate the images. A RAM
  BCB mirror must be labelled as such, not represented as a fresh EEPROM read.
  No EEPROM/BCB write or manual peripheral transaction is included.
- No flash, reset, halt/resume, power cycle, phone install or automatic recovery.
  Unexpected identity, active OTA or an unusable mapped route stops dependent
  reads; do not rerun an upgrade to manufacture evidence.
- All controllable files would be under the project-local
  `.cache/p34-early-identity1/`, preflighted again before execution. The native
  J-Link history file `C:/Users/SU/AppData/Roaming/SEGGER/JLinkDLL.ini` may be
  updated by the vendor library. That exact outside-project update requires
  explicit permission; it is not covered by general continuation. No cleanup,
  overwrite by root, neighboring paths or future flash authority is implied.

No device-use or early-exception gate is falsely closed by these fixture tests.
The raw R2 profile still cannot admit a finalized-header candidate, an old App
or an unknown backup. The actual payload identities are needed before selecting
the final safe recovery/candidate set and authorizing any replacement experiment.

## 16. Authorized Identity Observation (2026-10-05)

The user explicitly authorized the proposed finite read-only identity pass and
the possible vendor update of C:/Users/SU/AppData/Roaming/SEGGER/JLinkDLL.ini.
The broad accompanying continuation permission avoids repeated questions for
these same operations; this batch remains read-only, with no flash/reset/halt
or BCB mutation. Unspecified outside-project paths are not opened for writing.

`Tools/ota/p34_early_identity.py` uses the existing bounded uncached Commander
route, exact USB123456/SWD1000 selection and a fresh project-local directory.
Initial observation captures the whole64KiB Boot, the bounded960KiB App slot,
VTOR/DHCSR and QSPI control, without reading NOR first. NOR reads are a separate
dependent step, permitted only after matching the expected30275 image, exact
full Boot backup and already-enabled/nonbusy XIP mapping. Commands are limited
to cache settings, savebin and quit; no target state-restoration command exists.
Each subprocess has a180s deadline, original command/log receipt and a retained
failure result. Header CRC/image-hash identity parsing is checked against the
bound30275 image and two corrupt negatives before connecting. This parser does
not replace the complete firmware admission contract.

### Observed Identities And Parse Correction

The initial pass completed. Current App payload is617588B/version30275 with
SHA-2564d248fd7e3f6db9d08afdc3712f383064779a3b732ae3b7d550a4f2c393114f6.
The complete65536B Boot exactly matches the preserved known-good backup,
a63346db0dc673dc42adf6064892c466af5c4571df53cb55fe5b6ea154c1fdf4.
Both VTOR samples are0x08010000 and QSPI CTRL is0x00100080 (XIP selected,
sampled nonbusy). These are original readbacks, not earlier user reports.

Before NOR reading, the additional idle gate bound the matching30275 symbols
and actual session-access disassembly: state offset204 and ISR-active offset428
in the576B session at0x20052988. Both were zero. App header/XIP/phase were checked
again, and a post-read observation again found both session fields zero. These
endpoint observations do not make the multi-second reads an atomic snapshot.

The first NOR analysis incorrectly passed the whole ETSL slot to the direct
App-image parser. Its retained `no ETFW header` results reflect that layer error,
not missing firmware in all three slots. The contract places the32B ETSL metadata
at slot start and the App payload at+0x1000. Corrected OFFLINE analysis used the
already-saved bytes, without repeating the candidate or backup reads.

| Physical Slot | Version | Payload Length | Identity/Integrity |
| --- | ---: | ---: | --- |
| Candidate | 30275 | 617588B | Full payload matches current30275; slot CRC and image SHA pass |
| Backup | 30274 | 617588B | SHA22a0c48da12e24e61368c1617bb9b6098a8416ab598f59dc005a2b594ea70002; slot CRC and image SHA pass |
| Recovery | 20800 (2.8.0 header) | 563636B | NOT_ADMISSIBLE: payload CRC and image SHA mismatch |

Recovery's ETSL payload CRC is0xbe7907de, while the actual payload CRC is
0x6647069e. Actual payload SHA-256 is
e73f42bb165fdf0322ba0fdfc967214d31be4c5aabb308ab174b40afb4d4ada0.
One bounded recovery-only reread produced exactly the same full1MiB slot bytes,
SHA-256e410f3225cb15b373742eeffdb22b0b9a36723edc6c814fa6b2318b72a2bd722.
Thus these two observations agree on invalid recovery content; no cause or
historical time of damage is inferred. Candidate and backup identities are now
physically observed, but these OLD Apps still do not inherit R2 early-path safety.

### SDK Side Effects And Preserved Failure

Five owned Commander invocations completed: initial, idle, NOR, post, and the
recovery verification. Command lists contain no flash, reset, halt or resume.
However, vendor attachment is NOT bus-level read-only. SDK logs record23 calls
writing4B core/debug registers across these attachments: DWT_CTRL0xe0001000,
CPACR0xe000ed88, DHCSR0xe000edf0 and DEMCR0xe000edfc. Written values and any
temporary restore were not independently captured. Therefore do not claim
zero target writes, unchanged debug state or use this observation as DWT timing
evidence. No flash/EEPROM/BCB write command was sent.

The first finish routine correctly stopped when later logs included DHCSR and
DEMCR beyond its initial two-address DWT/CPACR expectation. Its guard was NOT
expanded to turn the failure into PASS; no additional device access followed.
`p34_early_identity_report.py` produced a separate OFFLINE inventory with
sdk_write_audit_passed=false and the original log/command/readback bindings.
`p34_readonly_batch.py` centralizes the bounded command generation for reuse;
its name describes requested operations, not absence of vendor attach effects.

The explicitly authorized JLinkDLL.ini has the same2270B/hash before and after
all five invocations. All controlled outputs remain under
`.cache/p34-early-identity1/`. The summary is `summary.json`; original per-stage
results, binaries and sdk.log files remain intact.

One source query mistakenly included unescaped angle brackets in cmd. It failed
before locating the input; a root-directory timestamp audit found no newly
created file. It was replaced by a plain identifier query. The prior reviewer's
reported empty file was not deleted or changed.

### Next Bounded Technical Plan

Do not proceed directly to group16 Boot replacement. The newly observed recovery
failure is a concrete recovery-route gate, not another permission quota.
Recommended ordering for original reviewer/root coordination:

1. Preserve the actual current App, complete Boot and both NOR observations as
   immutable fallbacks/evidence. The verified30274 backup remains distinct from
   the unusable20800 recovery slot. No automatic downgrade or slot repair.
2. Prepare exact finalized R2 candidate and golden-recovery artifacts offline.
   Require matching ELF/MAP, header-only delta proof, full firmware/ETSL integrity
   checks and new exact VTOR profiles; the old raw-R2 hash policy intentionally
   cannot admit finalized bytes. Select versioned artifacts explicitly rather
   than relabel old30274/30275 as repaired.
3. Independently review the finite provisioning/recovery route before mutation.
   The existing Boot physical YMODEM path is NOT a general NOR recovery-slot
   writer: boot_recovery.c programs internal App at OTA_APP_ORIGIN and boot_main
   enters it only after App/backup/recovery are unusable. Do not damage working
   images or force that emergency condition to make it usable as a repair tool.
   A supported, bounded NOR provisioning route must be established separately,
   including exact erase/program/commit/readback boundaries and power-loss cases.
4. Only after safe candidate/backup/recovery identities and the real collector
   route are established, perform the agreed App transition under the original
   Boot. Group16 replacement and measured apply/reconnect comparison remain later
   technical gates. Preserve BCB atomicity and the full Boot restore route.

The user's advance permission is recorded; no repeated authorization is needed
for the same approved work. It does not make an invalid recovery image valid or
waive the required implementation/review evidence. Current stop is on further
device changes while the recovery and SDK-route findings are resolved, not on
offline analysis. No OTA speed improvement is inferred from these identity reads.

## 17. Section 16 Review Response: Offline Recovery Route R1

The original review's EARLY-06 exclusion is retained: recovery 20800 is unusable;
its original reads and failed SDK audit remain unchanged. Correction to section
16.4 above: BCB I/O failure can also lead to physical recovery. The prior phrase
"only after App/backup/recovery are unusable" is not exhaustive. Neither internal
App recovery entry is a NOR provisioning writer.

The consolidated route, ownership state table, transition inventory and SDK
side-effect policy are in
[Recovery Provisioning Design R1](P3-4-recovery-provisioning-design-2026-10-05.md).
This is local, uncommitted work, not independent acceptance or production delivery.

Executed new offline work only:

- Synthetic recovery transaction model: four tests passed, 8392 prefix fault
  cases; .cache/p34-recovery-model1 contains original log and source/log receipt.
- Two provisional finalized R2 sources: 30276 and 30277, each 619580 bytes;
  .cache/p34-recovery-sources1 contains files, exact hashes, 152-chunk manifests
  and header-only delta checks. Eight integrity negatives rejected; original
  command/log in .cache/p34-recovery-sources-run1. No Boot admission claim.
- Explicit first-transition rollback target remains old 30275; a second normal
  OTA under original Boot is proposed to form an R2 backup. Repairing recovery
  alone does not close the old-App exception risk or force recovery selection.

EARLY-06-R1/07/08 remain NEED_EVIDENCE. Next implementation work is binding the
real admission validator and streaming fault cases, exact finalized collector
profiles, and a provable RAM takeover/timebase/DMA/watchdog/BCB recovery route.
The original reviewer must assess the consolidated route before target execution.
No repeated user authorization is required for the offline work. No connection,
NOR mutation, App/Boot replacement, rebuild, OTA or speed measurement occurred.

### 17.1 Continued Implementation, Not A Permission Stop

After the user identified the premature stage-summary stop, implementation
continued without another authorization request. The recovery design record
section 8 now contains one consolidated review packet and these new executions:

- Exact snapshot recovery admission: 22 host cases passed. Native validator
  includes the unchanged private Boot recovery-source function; both provisional
  finalized R2 images pass. .cache/p34-recovery-admission2 holds the evidence.
- Streamed finalized-image model: 18 scenarios and 39 native validator calls
  passed, including chunk replacement, short delivery, six read failures and
  three retained-storage interruptions followed by retry.
- Exact finalized VTOR observation policy: 34 host tests passed. Existing raw
  policy and live collectors unchanged; no operational readiness claim.

One failed native link attempt remains in .cache/p34-recovery-admission1;
the second links the real snapshot BCB implementation and emits no diagnostics.
All new receipts are separate from previous successful and failed evidence.
No firmware target rebuild, device connection, flash mutation or speed result.

Remaining review boundary is explicit in the recovery record section 8.4:
RAM provisioning transaction design and target ownership prerequisites, bounded
first-transition old-App rollback risk, and SDK/reset failure ownership. These
remain technical gates; advance permission is recorded and is not requested again.
