# Recovery Provisioning: Offline Design R1

## 1. Scope And Status

Response to the original review of early-exception note section 16. Root owns
this proposal. This is an uncommitted local design, not an executed device plan,
production change, acceptance, or authorization to write NOR. No existing Boot
or App is replaced by this proposal. EARLY-03 remains conditionally closed.

EARLY-06: recovery 20800 is excluded from usable recovery. Its two identical
readbacks remain intact. Do not recalculate its CRC/SHA to legitimize unknown
contents. Recovery is optional in the original contract, not a new universal
OTA requirement. This batch chooses to establish a trusted recovery path before
the R2 transition because existing rollback Apps lack early-exception evidence.

Correction to section 16: physical recovery can also follow BCB I/O failure;
it is not restricted to all three image sources being unusable. Neither YMODEM
nor flash-recovery-container.ps1 provisions NOR: both write internal App.
Do not deliberately corrupt state to enter them.

## 2. Proposed RAM Ownership

Preferred implementation is a separate RAM-resident provisioner with a narrow
host mailbox, not a callable App service or a copy of a test install_slot.
RAM overlay [0x20058000,0x20080000) is a candidate placement only. Its actual
availability, linker map, vector placement, stack and non-overlapping mailbox
must be proved against the exact active App and target before execution.

The finalized R2 payload exceeds RAM capacity. Do not stage the whole image in
RAM. Host pins an immutable finalized file plus full digest. A first streaming
pass validates the full ETFW header, length, CRC/SHA, vectors, hardware/layout
and Boot admission constraints without NOR writes. Keep 4096-byte chunk digests
in RAM (at most 240 entries = 7680 bytes for a 0xF0000 image). During programming,
receive a full chunk into a separate 4096-byte buffer and verify its digest
before any page from that chunk is programmed. Re-read the full NOR payload and
run the same complete admission checks before marker commit. Transport CRC alone
does not establish source identity. No recovery-container trailer is included.

Control takeover is destructive to the running context, although not to App
Flash. No return to interrupted C++ execution is supported. Before loading RAM:
prove idle OTA, read/arbitrate both real EEPROM BCB slots through a reviewed
reader, preserve raw bytes, and require a confirmed/non-copying state consistent
with the exact internal image. A RAM mirror is not sufficient. Reject pending
APPLY/ROLLBACK/TEST_BOOT and unknown BCB state without NOR writes.

Takeover must cover the interval before RAM vectors are established, not just
the later RAM loop. Bind an instruction-level sequence for interrupt masking,
safe vector installation, MSP selection and DMA/QSPI quiescence. NMI cannot be
masked by PRIMASK. Any unproved exception path in that transition blocks target
execution. Stop and acknowledge all relevant DMA/peripheral bus masters before
changing QSPI mode. Do not assume a halted CPU means DMA is halted.

RAM code, literals, vector handlers, stack, mailbox and all transitive callees
must be independent of NOR XIP. No libc, RTT, App globals or App callbacks.
Use polling with a bound independent of SysTick interrupts. The bound Boot
qspi_wait_ready uses boot_platform_millis(), so copying it while interrupts are
disabled is not acceptable. A chosen free-running timer, its source clock and
wrap-safe deadline need target evidence. Do not use historical DWT as a baseline.

Watchdog configuration/running state must be established. It cannot be assumed
disabled. Feed only inside a bounded owned operation with a finite overall host
deadline, never indefinitely while waiting for a disconnected host. Reset during
NOR busy can outlive MCU reset: establish part-specific maximum erase/program
time and existing Boot initialization behavior before allowing watchdog expiry
as an exit. If these cannot be proved, RAM execution is blocked, not retried.

## 3. State And Operation Table

| State | Permitted mutation | Completion / failure rule |
| --- | --- | --- |
| HOST_VALIDATE | None | Exact finalized source and manifest; invalid type/range/identity stops |
| TAKEOVER | Reviewed RAM/core/peripheral changes only | BCB, Boot and internal App preserved; failed ownership stops before NOR erase |
| SOURCE_VALIDATE | RAM mailbox and manifest only | Full source admission; all checks complete before destructive operation |
| INVALIDATE | Erase header sector at 0x200000 | Read back all 4096 bytes as FF before touching payload; any error stops |
| ERASE | Only payload sectors inside [0x201000,0x300000) | Aligned 4096-byte operations; verify FF; stop on failed/uncertain return |
| PROGRAM | Only payload pages inside admitted payload extent | Verified chunk; <=256 bytes, no page crossing; read back each page |
| VERIFY | None on NOR | Full payload and Boot admission; reject stale/missing/extra source bytes |
| HEADER | Program exactly offsets 0..27 in recovery slot | Read back exact metadata; marker must remain FF |
| COMMIT | Program exactly offsets 28..31 | Marker last; re-read complete slot admission, never infer failure means unwritten |
| EXIT | Reviewed reset sequence, never resume App context | QSPI idle and reset-safe; preserve status/receipts; otherwise retain explicit uncertain state |

All erase/program wrappers hardcode recovery base and length, use subtraction
range checks before arithmetic, and reject other slot types. No arbitrary
address/opcode mailbox, chip erase, status-register protection changes, EEPROM
write or internal Flash write API. Also guard lowest-level command emission,
not just the host caller. Keep Boot, App, candidate, backup, staging and BCB
unchanged. Do not erase unused trailing recovery sectors gratuitously.

After any transport loss, timeout, verification failure or uncertain return:
stop new NOR mutations. On a later reviewed retry, inspect actual storage and
restart from header invalidation after repeating full source/ownership checks.
A fully committed valid image may exist despite an error return. A partial
header invalidation may leave an old valid slot intact; no payload writes are
allowed until the header sector is confirmed erased. This is not a promise
against arbitrary bit damage or electrical faults.

## 4. Transition Identities (Proposed, Not Executed)

R2-A and R2-B denote provisional offline finalized versions from the selected R2
BIN, not reserved production versions. Their preparation is recorded below;
regenerated live VTOR profiles are still required before use. Do not apply a raw-BIN-only profile
to a finalized image. Current identities are from the preserved readback report.

| Step | Internal App | Candidate | Backup | Recovery | BCB / rollback condition |
| --- | --- | --- | --- | --- | --- |
| Observed | 30275 | 30275 | 30274 | 20800 invalid | Physical EEPROM not yet established; no writes |
| Provision recovery | 30275 unchanged | 30275 unchanged | 30274 unchanged | R2-A after verified commit | Same raw EEPROM; verified confirmed baseline prerequisite |
| First backup header erased, copy incomplete | 30275 unchanged | R2-A payload; header validity determined from bytes | Uncommitted/unavailable, NOT preserved 30274 | R2-A | Pre-STAGED BCB unchanged; valid internal App remains primary; independent restore route mandatory if it fails |
| First backup committed, STAGED not yet committed | 30275 unchanged | May be uncommitted during candidate header rewrite | 30275 committed | R2-A | Old BCB may not describe this backup; final dual-slot validation precedes STAGED; no inference of rollback eligibility from version alone |
| First ordinary OTA prepared | 30275 | R2-A | 30275 after normal backup transaction | R2-A | Existing Boot owns all transitions; never edit backup/BCB |
| First TEST_BOOT / failure | R2-A or rollback 30275 | R2-A | 30275 | R2-A | Old 30275 rollback remains a specific unresolved early-path risk |
| First confirmed | R2-A | R2-A | 30275 | R2-A | Require actual confirmation evidence, not reconnect alone |
| Second backup header erased, copy incomplete | R2-A unchanged | R2-B payload; header validity determined from bytes | Uncommitted/unavailable, NOT preserved 30275 | R2-A | Pre-STAGED BCB unchanged; valid internal R2-A or independently verified restore route |
| Second backup committed, STAGED not yet committed | R2-A unchanged | May be uncommitted during candidate header rewrite | R2-A committed | R2-A | Final dual-slot validation then atomic STAGED; uncertain commit requires real EEPROM arbitration |
| Second ordinary OTA prepared | R2-A | R2-B | R2-A after normal backup transaction | R2-A | Preserve original Boot; interruptions follow actual durable BCB |
| Second TEST_BOOT / failure | R2-B or rollback R2-A | R2-B | R2-A | R2-A | Both proposed targets require finalized identity binding |
| Second confirmed | R2-B | R2-B | R2-A | R2-A | Only then evaluate group16; read/validate complete finite set |

This table does not waive the first transition's old-App exception gap. Reviewer
must explicitly assess that bounded old-App rollback path or select another
route before any first OTA. Recovery is not automatically selected while an
otherwise-valid old backup exists. Do not force it by damaging backup/BCB.
Correction EARLY-08-R1: the old backup header is erased before copying; its
physical slot is not guaranteed available until the new marker is committed.
Host archival copies are not bootable physical slots. After backup commit,
candidate metadata is rewritten, both slots are fully checked, then BCB STAGED
is atomically committed. Determine the selected copy by actual slot/BCB
validation, never infer it solely from the planned step. Device recovery must
remain possible if the provisioned slot is still uncommitted or EEPROM I/O fails.
The exact existing physical recovery trigger and internal-App restore route,
including human action if unavoidable, remain an execution prerequisite.

## 5. SDK Side Effects (EARLY-07)

Preserve sdk_write_audit_passed=false and all 23 historical CPU_WriteMem records.
The known addresses are DWT_CTRL, CPACR, DHCSR and DEMCR; historical values and
transient restoration are unknown. No reconnect to reconstruct them; no guessed
register restoration. Existing exact image comparisons remain usable.

A future takeover runner must pin J-Link executable/DLL hashes, version, probe,
connection mode and commands. The register mutation budget must distinguish
attachment effects from explicit takeover writes. Capture available before/after
values and SDK logs, but label unobserved transients unknown. A supported reset
sequence must establish a fresh execution/timing baseline before performance
measurements; endpoint equality is not proof. Unexpected register/peripheral
activity stops dependent actions and records the retained halt/run/QSPI/watchdog
state. No automatic repeated connection or blind resume. JLinkDLL.ini is the
only previously specifically authorized external output; all other controllable
logs/temp/mailbox/receipts stay inside this project.

## 6. Host Evidence And Remaining Gates

Tools/ota/p34_recovery_transaction_model.py is a synthetic transaction model,
not a target implementation or an existing Boot validator. It exercises prefix
tears for every program byte, representative erase prefixes, all full-write
failed returns, stop-on-error, bounded retry, protected trailing bytes, wrong
slot/range/source zero-write cases and independent corruption negatives.
Its synthetic SHA8 is not ETFW double-zero SHA and must never produce a device
artifact. It does not close EARLY-06-R1 by itself.

Still required before a deployable route: finalized-source/Boot validation
integration and negatives; source-change-between-passes tests; header readback
and busy/read failure injection; repeated interruptions with physical state
retained; actual RAM linker/IRQ/DMA/timebase/watchdog/SDK proof; exact BCB reader
and retained-state recovery instructions. No claim of target compilation,
electrical testing, physical provisioning or performance improvement.

Next owner is the root implementer: extend the model with the bound production
admission oracle and streaming manifest, finalize exact R2 identities offline,
then submit this single consolidated route/evidence batch to the original
reviewer. No new user permission is needed for those offline steps. Target
execution remains blocked by the technical unknowns above, not by repetition
of an authorization request.

## 7. Executed Offline Evidence

Transaction model command: python -I -S -B -X utf8
Tools/ota/p34_recovery_transaction_model.py, run at the project root.
Four tests passed, including 8392 prefix-tear/uncertain-return cases, in 86.107s.
Original log and command/source/log binding are in
.cache/p34-recovery-model1/tests.log and result.json. The scope remains synthetic;
this is neither target writer validation nor an independent acceptance result.

Source preparation command: python -I -S -B -X utf8
Tools/ota/p34_recovery_sources.py, run at the project root.
Exit 0; two generated images and eight rejected integrity negatives. Reused the
four exact pure finalizer functions and six constants via AST from etu_pack.py,
without importing its package/device dependencies. Input source, original BIN,
ELF and MAP hashes are bound in .cache/p34-recovery-sources1/result.json.
The command and log are in .cache/p34-recovery-sources-run1. This is not a new
ELF build: bytes outside [0x400,0x460) match the reviewed raw BIN exactly.

| Proposed role | Provisional version | Bytes | File SHA-256 |
| --- | --- | --- | --- |
| R2-A / recovery and first candidate | 3.2.76-r2a / 30276 | 619580 | 7445ef63d5f4cbef95761f27075333d7d09c9d43585a28b84e6575ccfb274fcf |
| R2-B / second candidate | 3.2.77-r2b / 30277 | 619580 | e4737cfcbbb884c4a7fa407ea733486425674c7ed2723d0f8cf3263beb4e8802 |

Each has 152 chunk digests (4864 bytes), full finalized-file CRC/SHA, stored
ETFW image SHA and exact two vector-table byte sequences in the manifest. These
are source inventory data, not an executable live collector policy. The code
rejects a truncated image, an appended eight-byte trailer, payload corruption
and header corruption for each source. Version numbers are provisional local
design choices; no release reservation, packaging, upload or device use occurred.

Complete Boot admission and compatibility with runtime version reporting have
not been checked. Do not promote these artifacts merely because integrity checks
passed. No existing evidence, firmware source, backup or device state changed.

## 8. Native Admission, Streaming And Finalized Observation Follow-Up

The prior section's NOT_RUN statements describe the earlier preparation batch.
New evidence below does not modify those original receipts or authorize hardware.

### 8.1 Exact Native Recovery Admission

New host harness tests/boot/p34_recovery_admission_host.c includes the bound
.cache/p34-bc-target/f/boot/src/boot_state_machine.c unchanged and calls its
private validate_external_source with SOURCE_RECOVERY and a bounded memory
reader. It links the same snapshot's slot, firmware-header, CRC and SHA code.
It does not copy those algorithms into a permissive Python validator.

Tools/ota/p34_recovery_admission.py produced
.cache/p34-recovery-admission2/result.json: 22 cases passed, including both
finalized images, nine slot/payload corruptions, eight correctly resealed but
incompatible firmware variants, two read failures and a truncated slot.
The recovery validator verifies metadata, full payload CRC/SHA, hardware/layout,
minimum Boot version, vectors, padding and ETFW/ETSL identity agreement.
This is full recovery-source admission on the host, not execution of BCB state
transitions, candidate selection or the physical recovery route.

First attempt in .cache/p34-recovery-admission1 failed to link: MinGW retained
unused state-machine sections referencing BCB functions despite section GC.
Its compile receipt/log are preserved. The successful attempt links the bound
real eeprom_bcb.c rather than adding success-returning stubs. No BCB callback
is installed or used by the tested recovery validator. Successful compile log
is empty: zero compiler/linker diagnostics under -Wall -Wextra -Werror.
This was a native host build only; no App or Boot target rebuild occurred.

### 8.2 Streaming Model With Real Admission Oracle

Tools/ota/p34_recovery_stream.py produced
.cache/p34-recovery-stream1/result.json: 18 scenarios and 39 native admission
calls passed. It preserves the earlier synthetic model and reuses its NOR
mutation semantics. The modeled transaction now uses real finalized bytes and
the actual ETFW double-zero SHA8 in ETSL metadata.

Coverage: normal completion; changed or short chunks at positions 0, 75 and 151;
read failure at header erase, payload erase, page readback, complete payload,
metadata readback and final commit readback; three interruptions retaining the
same storage (full marker write with error return, next header erase torn at 29
bytes, next first page torn at 127 bytes), then a successful retry; four zero-
mutation invalid-source/scope cases. Rejected streamed chunks are checked before
their sector erase or page program. No operation follows an injected write error.

Before physical-model metadata commit, a host-only virtual committed header
allows the exact validator to check the modeled payload. It does not write the
NOR marker. Post-commit failure can leave a valid image, which is explicitly
accepted by the oracle rather than treated as unwritten. Logs and per-call
input snapshots remain separate, with source/executable bindings.

Limits: Python holds full fixtures for the host model; this is not a RAM memory
budget proof or a target streaming implementation. The model does not implement
timer/busy-line deadlines, electrical faults or DMA exclusion. The preserved
8392-case synthetic matrix supplies prefix tear coverage, not native admission
for every one of those synthetic cases. Do not multiply or combine counts into
a claim of exhaustive native fault validation.

### 8.3 Finalized VTOR Policy

Tools/ota/p34_finalized_vtor.py accepts only the two exact provisional finalized
digests, stable VTOR at 0x08010000 or 0x08010800, the complete corresponding
524-byte table and a non-halt/non-reset observation. Its 34 host tests passed;
.cache/p34-finalized-vtor1 contains input bindings and the original execution
receipt/log. It always returns operational_readiness=NOT_ESTABLISHED.
This is not yet wired to a live reader and is not physical observation evidence.
The historical raw-R2 classifier and existing collectors were not modified.

### 8.4 Consolidated Review Request And Execution Gate

Owner: original reviewer for the following bounded design/evidence decisions;
root remains the implementer. These are not repeat permission requests.

1. EARLY-06-R1: review sections 2-3 and the new native/stream evidence. Decide
   whether this transaction design is suitable for isolated RAM implementation,
   with target ownership/timebase/watchdog proof still mandatory before use.
   Expected invariant: writes confined to the recovery slot, verified source,
   marker last, actual-storage arbitration after uncertain returns. If further
   host cases are needed, identify the smallest discriminating case, not a rerun
   of the closed Boot checkpoint campaign.
2. EARLY-08: assess the explicit first-transition old-30275 rollback risk in
   section 4. Preferred route is two ordinary upgrades under original Boot only
   after a separately verified restore route exists. If the old target cannot
   be accepted even for this bounded transition, require a different migration
   design; do not silently treat recovery repair as removing that path.
3. EARLY-07: review the proposed reset-based ownership boundary. Historical SDK
   writes remain unknown; no guessed restoration or DWT baseline reuse. A later
   concrete target plan must bind the SDK, register effects, failure-retained
   state and part-specific busy/reset behavior before any connection for repair.

The complete RAM takeover instruction sequence, DMA quiescence, independent
timebase, watchdog/NOR-busy reset compatibility, real BCB reader and full retained-
state restore recipe remain unimplemented. This batch requests design review,
not EARLY-06/07/08 closure or hardware approval. No self-test result establishes
those physical prerequisites. Original reviewer is external to this root thread;
no automatic relay delivery or independent review is claimed.

## 9. Review Decisions And Isolated C Core Implementation

The original review of section 8.4 permits isolated RAM implementation. It
conditionally accepts two-hop migration under original Boot while retaining
the old-30275 early-exception risk, and accepts reset-based ownership rather
than guessed debug-register restoration. It does not authorize device use.

EARLY-08-R1 correction is applied directly to section 4 with four intermediate
rows (two per hop). Backup header erasure makes the previous physical backup
unavailable; internal App remains unchanged. A newly committed backup still
precedes candidate header rewrite, final dual-slot verification and atomic
STAGED. Host archive availability does not imply physical rollback eligibility.
This matches the bound ota_backup.c transaction, without changing that code.

### 9.1 C Core And Host Evidence

Tools/ota/ram_recovery/writer.c and writer.h implement an isolated synchronous
transaction core, not a device-access program. The interface contains relative
source reads and fixed recovery-only checked NOR operations. No public arbitrary
address write, chip erase, EEPROM write, BCB edit or internal Flash write entry
is provided. Port callbacks are host fixtures for now, not a target mailbox ABI.

The core calls the bound boot_fw_header_validate with vectors enabled before
any NOR mutation. It captures the validated 96-byte header and checks that the
manifest pass sees the same header, then verifies the pinned full-file SHA.
It owns the chunk table in its workspace, generates it only before writing, and
rejects second-delivery changes before erasing that chunk's payload sector.
Erase regions and every programmed page are read back; the entire payload is
hashed and revalidated before metadata. Metadata and marker are checked after
their separate writes; a second full pinned-payload hash follows marker commit.
Any error ends the invocation, including failed returns after physical success.

tests/boot/p34_ram_writer_host.c includes the C core for private boundary tests.
Tools/ota/p34_ram_writer.py builds it with the same bound Boot crypto/header
sources, not Python approximations. Both finalized R2 images passed 23 checks
each (46 executed checks) in .cache/p34-ram-writer1. The twelve transaction
scenarios per image include four successful-return/corrupt-content classes:
header-sector erase, payload-sector erase, programmed page, metadata, plus
post-marker payload corruption. It also covers physical-success/error-return
at erase, page, metadata and marker, changed second delivery, and read failure.
Eleven argument/boundary checks per image reject underflow/outside/overflow,
page crossing, overlong page, unaligned/outside erase, invalid lengths and
wrong pinned digest before mutations. No operations occur after injected errors.

Successful transactions each performed 2576 modeled mutations and left all
untouched trailing sectors unchanged. Host workspace sizeof is 12252 bytes.
This is not a worst-case stack figure or an ARM layout claim. Compile log is
empty with -Wall -Wextra -Werror. Original Python evidence remains unchanged.

### 9.2 ARM Compilation, With Unresolved Boundaries Kept Explicit

Tools/ota/p34_ram_writer_arm.py reuses the exact boot_fw_header compile-command
ABI template from .cache/p34-bc-target/b16/compile_commands.json, changing only
the source and output operands. It builds writer.o, not App/Boot or an executable
RAM image. .cache/p34-ram-writer-arm1 binds the template, tool, object, stack
records and unresolved-symbol/disassembly output. Compile log is empty.

Compiler static frame records: rr_run 456B, verify_payload 176B, validate 48B,
erase_checked 32B, image_read 24B, put32 0B. These are individual frames, not a
call-chain bound. They must not be compared directly with the overlay budget.

Unresolved calls include Boot SHA/CRC/header functions and memcmp/memcpy/memset.
They must be linked to verified RAM-resident implementations in the later
freestanding image; no claim of an existing libc-free or NOR-XIP-free target
image is made. Target callback implementations and their transitive callees
also remain unbound. Current outputs cannot be loaded as a working RAM writer.

### 9.3 Remaining Implementation Work, Not A New Permission Request

Continue with the freestanding link and actual read/program ports, followed by
the takeover/vector/MSP sequence, DMA/QSPI idle proof, independent timebase and
watchdog/NOR-busy exit behavior. These require concrete source/artifact proofs,
not replacing unknowns with nominal timings. No device connection is needed to
prepare those artifacts. The real BCB reader and independent internal-App restore
operation table are still required before the first migration. Neither fixing
the backup table nor host writer success closes that device gate.

If a restore route needs new BCB mutation semantics, stop that affected design
for an explicit scope decision instead of adding such writes to this recovery-
only writer. Existing normal Boot/OTA transactions remain the only permitted
BCB writers under this design. No golden-slot forced selection is introduced.

### 9.4 Freestanding Core Link Follow-Up

Continued beyond the object-only compile: memory.c provides stateless byte
memcpy/memset/memcmp implementations, compiled with -ffreestanding -fno-builtin.
Tools/ota/p34_ram_core_link.py links writer, these primitives and the bound
Boot SHA/CRC/header functions with -nostdlib into the candidate overlay using
core.ld. It preserves inherited CPU/float ABI flags. No implicit libc is linked.

.cache/p34-ram-core-link2 holds the successful core.elf/map, per-source compile
receipts, disassembly, section listing and an empty undefined-symbol report.
Code/RO data: 3116B; data: 0B; NOLOAD storage including workspace, alignment and
8192B reserved stack: 20452B. Total allocated extent is 23568B starting at
0x20058000, ending at 0x2005dc10, within the candidate overlay ending 0x20080000.
The ELF has separate RX and RW LOAD segments. These flags do not configure MPU
or establish hardware stack protection. NOLOAD storage must be initialized by
a future reviewed loader; it is not magically zeroed on debugger loading.

First link in .cache/p34-ram-core-link1 failed under --fatal-warnings on a RWX
LOAD segment. That log is preserved. The linker description now uses distinct
code/state program headers; no warning suppression was added. Successful build
and link logs are empty. The object-only result in section 9.2 is unchanged;
its unresolved calls are resolved by this new, separately bound artifact.

.cache/p34-ram-core-host1 repeats the 46 C-core checks with the actual new memory
primitives and freestanding compiler flags. All passed; this verifies the new
dependency in the existing host scenarios, not ARM execution.

Important boundaries: ELF entry is callable rr_run, NOT a reset/takeover entry.
It requires valid initialized workspace, arguments, stack and synchronous port
callbacks. There is no vector table or QSPI/mailbox/BCB reader implementation.
Absence of undefined direct symbols does not resolve these indirect callback
targets, prove their RAM residency or close exception/nesting stack bounds.
The 8192B stack is a reservation, not a measured or established worst-case bound.
This artifact must not be sent to a debugger as a device loader.

The C core currently makes a complete firmware-validation source scan followed
by a manifest/hash source scan before writes, then the programmed-chunk scan.
Thus it has an additional read-only preflight traversal versus an optimized
two-delivery implementation. This is intentionally disclosed; no transport time
or OTA speed improvement is claimed. Optimizing the traversal is secondary to
preserving validated-header, pinned-file and immutable-chunk-table agreement.

### 9.5 C Output Cross-Checked By Unchanged Boot Admission

An additional fixture, tests/boot/p34_ram_writer_emit.c, reuses rather than edits
the previous harness, executes it with the new freestanding memory primitives,
then emits the C writer's successful complete 1MiB modeled NOR slot.
.cache/p34-ram-writer-cross1 records two emissions and two calls to the already
bound native Boot recovery validator. Both returned SOURCE_OK, with 4845 reads
each and versions 30276/30277 respectively. Thus actual C-generated ETSL metadata,
payload and marker pass the unchanged recovery-source admission path, not only
the writer's own success checks. This remains host evidence, not physical NOR
programming, DMA/watchdog behavior or ARM execution.

## 10. Read-Only BCB Protocol And Fixed Peripheral Ports

Implementation continued without another permission request or a device call.
All outputs below are isolated host/ARM artifacts, not physical observations.

### 10.1 BCB Reader

bcb_reader.c/h implement the exact A,B,A,B capture sequence over bounded GPIO
callbacks. Each transaction sends only 0xA0, pointer 0x00 or 0x40, repeated START,
0xA1, then receives 64 bytes, with NACK after the last byte and STOP. There is no
EEPROM payload-write function. This does change the EEPROM address pointer and
GPIO levels; "read-only" means no NVM programming, not bus-level zero writes.

The four raw blocks and completed-read count remain available on failure. Only
identical complete rounds are arbitrated by the unchanged snapshot bcb_arbiter
using an in-memory read callback and NULL write callback. The snapshot adapter
is explicitly non-reentrant and requires exclusive execution ownership. Two
matching rounds are not an atomicity/concurrency proof. BCB_ARBITER_NONE remains
an observation of two invalid slots, not permission to initialize or repair BCB.

.cache/p34-bcb-reader1 records 5499 passing host checks: five arbitration cases
(including equality and sequence wrap), a changed second round, NACK at each
block, all 5488 pause boundaries faulted independently, and SCL stuck low.
Outgoing command bytes and all master ACK/NACK bits are checked. Every timeout
fails capture, releases both lines and does not retry. If SCL cannot rise, a
successful STOP is not claimed. The finite stretch-poll cap also prevents an
infinite software loop if the supplied timebase stops. Actual electrical timing
and analog bus recovery are not modeled.

at32_bcb_port.c/h provide the fixed PB6/PB7 open-drain mapping using bound SDK
register definitions and GPIO initialization. They require a separately proven
288MHz clock, RAM vectors/MSP, Thread mode, PRIMASK and exclusive bus/DMA ownership.
The port checks mode and vector region but does not claim those checks establish
all preconditions. It deliberately establishes a new DWT baseline by enabling
DEMCR.TRCENA, clearing CYCCNT and enabling DWT.CTRL.CYCCNTENA; no restoration of
historical SDK values is attempted. Its nominal 5us pause and 2s capture deadline
are conditional on the clock precondition and include a finite spin cap.
.cache/p34-bcb-reader-arm1 records successful ARM compilation, not target timing
validation. There has still been no fresh physical EEPROM BCB capture.

### 10.2 QSPI Port

at32_qspi_port.c/h provide fixed QSPI1 ports restricted to recovery offset
[0x200000,0x300000). Public and internal command checks reject other ranges;
public program rejects page crossing/zero/oversize requests before WREN.
Only status, JEDEC, read, WREN, page program and 4KiB erase opcodes exist. No chip
erase, status-register write, reset command or EEPROM function is exposed.

The bound SDK qspi_xip_enable has unbounded waits. This implementation does not
call it: it retains the SDK's TX-ready, 64-NOP, xiprcmdf, abort-wait, 64-NOP,
xipsel-clear, abort-wait order with bounded waits. GPIO/clock/DMA/controller
ownership remains a prerequisite; a sampled controller-idle field alone is not
proof that no other bus master can access NOR.

WREN is followed by checking WEL and nonbusy status. Command, FIFO and NOR busy
polls share one operation deadline plus a finite polling cap. Errors latch the
port failed and reject subsequent operations. Failure does NOT imply NOR is
idle: a timed-out physical erase/program can still be running. No automatic
XIP restore, App resume or reset is attempted. A supervisor and chip-specific
watchdog/reset plan are still required. The current 100ms command/read and
2000ms program/erase limits are experimental bounds inherited in scale from
the Boot implementation, not certified device maximum timings.

.cache/p34-qspi-port-host1 records 14 passing behavior-model cases: normal
erase/program/read; seven invalid range/size/page cases with zero WREN or
programming; command/FIFO failure, WEL refusal, frozen-DWT termination; two
invalid erase addresses. Failed ports emit no further commands. The mock is
explicitly not a model of the silicon register layout, XIP flush electrical
behavior or NOR power loss. .cache/p34-qspi-port-arm1 records compilation using
the real SDK definitions; it is not hardware execution.

### 10.3 Linked Core And Ports

Tools/ota/p34_ram_ports_link.py compiled the core, both ports, reader, original
BCB/crypto/header implementation and bound GPIO/CRM/QSPI SDK sources into
.cache/p34-ram-ports-link1/ports.elf. All compile/link logs are empty. The result
binds project SDK headers in addition to sources, command template and tool.

Text/RO: 6380B; initialized data: 0B; BSS/alignment plus the reserved 8192B stack:
21484B. Total allocated extent 27864B remains within the proposed overlay.
No unresolved direct symbols; bcb_commit, boot_platform_eeprom_write and the
unbounded qspi_xip_enable are absent from the linked symbol table. This does
not prove all indirect targets, exception paths or whole-call-chain stack bounds.
Zero-initialization of the module's BSS (including the original BCB CRC cache)
must be established by the future loader before use.

Entry remains callable rr_run, not a reset/takeover handler. There is no source
mailbox, integrated supervisor, safe takeover sequence, independently derived
clock check, watchdog handling or exit/restore entry yet. No debugger launch
script is generated. Do not load-and-go this ELF. The independent restore route
covering the actual BCB and the first old-App rollback risk remains a device-use
gate; current work does not close EARLY-06/07/08 or establish OTA speed gains.

## 11. Source Mailbox And C Writer Integration

source_mailbox.c/h implement a single-producer request/reply mailbox with a
4096-byte source cache. Requests contain only file offset/length, generation and
sequence, not MCU/NOR addresses or execute commands. Reply commit is written last;
the consumer checks generation, exact extent and commit before and after copying,
then transport CRC. Request sequence never wraps. Timeouts and invalid replies
latch failure; later reads cannot issue another request. ARM builds use DMB
barriers. A separately initialized producer/consumer, aligned word access and
exclusive ownership are prerequisites, not properties inferred from stale RAM.

Transport CRC is not authentication. The C writer's pinned whole-file and fixed
chunk SHA checks remain authoritative. Source freshness/generation must be
established by the future supervisor and host, not an arbitrary RAM readiness
flag. Neither the mailbox nor these tests implement a live J-Link host producer.

.cache/p34-source-mailbox1 records 13 host cases and an ARM compile. Cases include
cache reuse, a cross-block read, final partial block, timeout, bad generation,
wrong offset/length, corrupted data, wrong sequence, bounds and sequence exhaustion.
The test clock crosses uint32 wrap. This is protocol-level verification, not an
asynchronous bus or debugger atomicity/electrical proof.

.cache/p34-mailbox-writer1 adds six integration scenarios (three per finalized
image), repeats the inherited 46 writer checks, and checks both successful C
outputs using the original native Boot recovery-source validator. Normal runs
each make 456 mailbox requests and 2576 modeled NOR mutations. Replacing second-
delivery data while supplying a correctly recomputed transport CRC returns
RR_SOURCE at request 305 with only the already-completed header erase (one
mutation), before any payload erase/program. A wrong generation fails the first
request with zero mutations. No existing evidence or producer was modified.
The mailbox is not yet included in the section 10 linked peripheral image.

## 12. EARLY-09: Direct Internal-App Restore Is Not Complete Recovery

### 12.1 New Concrete Finding

EARLY-09 | NEED_EVIDENCE / SCOPE_DECISION.
The bound R2 ota_backup.c:386-392 requires CONFIRMED.cur_vcode to equal the
actual internal App fw_header version before staging another OTA. Original
Boot's CONFIRMED branch validates and jumps to a valid internal App without
rewriting an otherwise valid BCB to its new version. Thus directly programming
R2-A into internal App while retaining CONFIRMED.cur_vcode=30275 can boot R2-A
but leaves normal OTA blocked. Such a write/reset sequence is not the complete
independent recovery route required by EARLY-08.

tests/boot/p34_restore_state_host.c uses actual finalized R2-A and unchanged
bound Boot/App transaction sources with memory I/O. In the constructed initial
CONFIRMED/30275 fixture, boot_state_machine_run jumps to 30276 without EEPROM
writes, and ota_backup_stage rejects with APP_HEADER before any external slot
access or Flash writes. This confirms the specific state inconsistency; it is
not evidence of an observed device failure.

The same host-only fixture then calls the existing
boot_state_machine_accept_physical_recovery transaction. It fully validates
internal App and commits CONFIRMED/30276 through the original BCB transaction.
Subsequent ota_backup_stage passes the current-version gate and reaches the
intentionally failing candidate read (reported as CANDIDATE_HEADER by the actual
API). No internal/NOR Flash writes occur in this host exploration.

Successful evidence: .cache/p34-restore-state3 with original compile/run receipts
and source bindings. Two harness failures remain preserved: state1 omitted the
mandatory non-NULL internal erase/program ports even for the no-copy branch;
state2 expected CANDIDATE_READ rather than the actual CANDIDATE_HEADER mapping.
The corrected harness supplies failing Flash ports and checks the exact result
plus operation counters. No production assertion or behavior was weakened.

### 12.2 Required Direction Decision

Preferred proposal for original-reviewer/root scope assessment: separately
design a narrowly bounded independent restore route that validates an exact
approved internal-App replacement and uses the original Boot recovery-confirmation
transaction to restore coherent BCB state. Preserve its failure arbitration and
normal commit semantics; do not hand-edit BCB fields or invent another commit
algorithm. This is a proposal only, not permission to invoke that function on a
device, bypass its physical entry, or extend the NOR writer's interfaces.

An alternative is an existing supported restore entry that provably converges
the same states without invoking a new debugger-controlled confirmation path.
The original YMODEM route still requires its legitimate reachability conditions;
do not damage candidate/backup/BCB to force them. Neither raw image archival nor
the repaired recovery slot alone solves the version/selection issue.

Decision requested: may the separate constrained recovery-confirmation route
proceed to offline design, and under what entry/pre-state constraints? If not,
identify the supported alternative that also resolves CONFIRMED/version mismatch
without depending on the old App or automatic golden-slot selection.

Required later oracle: exact image and BCB identities before/after; every permitted
starting state explicitly covered; reads/commits failing after physical success
remain uncertain until real arbitration; no NOR/Boot/other slots changed by the
confirmation action; no acceptance of an invalid internal image; and normal OTA
can pass its current-version gate afterward. Current evidence covers only one
constructed CONFIRMED state, not an all-state restore implementation.

The current recovery NOR writer remains NOR-only and the new BCB port remains
NVM-read-only. No physical-confirmation device wrapper, entry bypass or EEPROM
write port was added. This scope decision is now an actual dependency for a
complete restore supervisor, rather than another request for already-granted
isolated build permission. Physical timing, DMA/SD/watchdog quiescence, clock
derivation, takeover and exit proofs remain outstanding and are not waived.

## 13. EARLY-09 Host-Only Confirmation Supervisor

### 13.1 Accepted Scope And Independent Interface

The original reviewer approved separate offline design/host verification of a
restricted confirmation route. No device call, physical-entry bypass, original
Boot modification or device-side EEPROM write port is approved by that decision.
The implementation is isolated in Tools/ota/recovery_confirm, not ram_recovery.
Its headers require RR_CONFIRM_HOST_ONLY. It was compiled only for the host and
is not an input to any existing ARM/RAM target build or device runner.

confirm.h exposes rc_confirm(plan, request, host_hal, result). The plan is a
trusted, immutable supervisor-owned operation ID and exact 128-byte expected
BCB pair. It is not a caller-provided desired BCB record. The request identifies
that operation and supplies the acquired Boot/App byte views for the host model.
There is no requested target version, target EEPROM address, arbitrary field
patch or clear command. The destination is derived from the original arbiter;
the target version and two artifact hashes are fixed in the component:

- Complete 65536-byte original Boot SHA-256:
  a63346db0dc673dc42adf6064892c466af5c4571df53cb55fe5b6ea154c1fdf4.
- Exact 619580-byte finalized R2-A SHA-256:
  7445ef63d5f4cbef95761f27075333d7d09c9d43585a28b84e6575ccfb274fcf.

Operation-ID equality is a binding predicate, NOT authentication, physical
presence or proof of device authorization. In a future design, the caller must
not control the trusted plan, and the byte views must come from the exact owned
device acquisition, not arbitrary supplied files. This host implementation uses
known files and constructed EEPROM fixtures; it does not establish that future
entry/provenance chain. No naked Flash function-address call is introduced.

The component reuses the unmodified bound Boot transaction source, including
boot_state_machine_accept_physical_recovery and bcb_commit. All hardware I/O in
these executions is replaced by explicit memory fixtures. The model is serialized,
non-reentrant and assumes immutable plan/image buffers and exclusive EEPROM
ownership. Sequential matching reads do not themselves establish atomicity or
exclude an unobserved concurrent writer. These remain entry prerequisites.

### 13.2 Pre-State And Operation Table

| Observed/input condition | Host supervisor behavior | EEPROM writes |
| --- | --- | --- |
| Wrong operation, length, complete Boot hash or R2-A hash | RC_REJECTED before transaction | Zero |
| Expected pair has no valid A/B selection | RC_REJECTED, no initialization | Zero |
| IDLE/STAGED/APPLYING/TEST_BOOT/ROLLBACK/unknown state | RC_REJECTED | Zero |
| CONFIRMED with nonzero copy phase/resume, unsupported current version or noncanonical active record | RC_REJECTED | Zero |
| Live complete pair differs from both approved pre-state and exact derived post-state | RC_REJECTED | Zero |
| Initial EEPROM acquisition fails | RC_UNKNOWN | Zero |
| Exact already-consistent state or exact completed result of this plan | Re-read/compare; RC_ALREADY, no transaction | Zero |
| Exact approved CONFIRMED pre-state, current 30275 or 30276, no copy progress | One guarded original confirmation transaction, then independent observation | At most one 64-byte host write call |

The narrow canonical guard requires padding compatible with original serialization,
reserved=0 and boot_try<=3. A target-consistent state additionally has boot_try=0.
No arbitrary current-version migration is accepted. The complete inactive slot
also belongs to the expected pair, even if it is not the selected slot.

Before invoking the transaction, the supervisor derives the exact result from
the expected selected record: state=CONFIRMED, boot_try=0, copy_phase=NONE,
resume_block=0 and cur_vcode=30276. Candidate/backup fields are not rewritten.
The expected sequence is old+1 modulo 16 bits; the original bcb_commit still
performs the actual sequence assignment and slot transaction.

The injected host write guard permits only the exact derived 64-byte record at
the inactive slot, once. It checks original-transaction reads for pre-write drift
and re-reads the complete pre-state immediately before allowing the host write.
It does not replace the original commit algorithm. An unexpected attempted
record/address, read failure or observed drift cannot become a generic write.

### 13.3 Results Come From Storage, Not Kernel Return

After the original transaction returns, the supervisor independently reads A/B
twice and invokes the original arbiter on the observation. It compares complete
records and the complete expected pair. transaction_status/outcome are diagnostic
only, never the confirmation oracle.

| Result | Meaning and next action |
| --- | --- |
| RC_CONFIRMED | Complete stable observed pair equals the exact expected result, selected slot agrees; can be true after a failed kernel return |
| RC_ALREADY | Exact target state was verified without a new transaction or sequence increment |
| RC_NOT_CONFIRMED | Original active record remains selected and unchanged; inactive slot may be torn, so this does NOT mean EEPROM was unchanged |
| RC_REJECTED | Entry/pre-state/identity predicate failed; no allowed confirmation write was issued |
| RC_UNKNOWN | Reads failed, observations differ or the result is outside the expected outcomes; retain evidence, no automatic retry |

No loop retries the confirmation transaction. Calling rc_confirm again is not
a general read-only probe: if the exact approved original state remains, it is
an execution request. UNKNOWN recovery must first use the separate read-only
observer or other approved read-only acquisition, not blind resubmission.

observe.c/h expose rc_readback(read_hal, observation). This function accepts a
NULL write callback, reads A/B twice and arbitrates only the saved observation.
It never calls the confirmation transaction. Stable reads can describe an
ineligible or invalid BCB state and do not mean confirmation succeeded. The
actual operation outcome still requires comparison with the immutable plan.

### 13.4 Executed Host Evidence

Tools/ota/p34_confirm_supervisor.py produced
.cache/p34-confirm-supervisor1/result.json with 173 passing checks. The matrix
covers A/B active slots, ordinary and wraparound sequence increments, preservation
of nonzero candidate/backup fields, completed-operation idempotence, already-
consistent state, illegal states/progress/version, invalid pair, record drift,
operation mismatch, wrong Boot and App identities, and corrupted App data.

For both active slots at sequence 65535, prefix lengths 0..64 model interrupted
sequential EEPROM writes, including full physical success with a failed return
(130 cases). The oracle uses resulting bytes, not the injected prefix length or
the failure code. Fifteen individual read positions are faulted, including
before-commit and post-commit observation reads; persistent read failure remains
UNKNOWN. These are byte-prefix and read-failure models, not electrical or
arbitrary-bit corruption tests.

The same batch includes a real valid candidate/staging composition: after
confirmation of R2-A, the unchanged ota_backup_stage processes exact finalized
R2-B using modeled NOR and EEPROM, returns OTA_BACKUP_OK and commits STAGED with
current/backup 30276 and candidate 30277. Confirmation makes zero NOR calls;
normal staging then makes 310 NOR erase/program calls and the second EEPROM
write. The recovery region is unchanged. This proves this staging combination,
not reboot, TEST_BOOT, final confirmation or a complete OTA cycle.

.cache/p34-confirm-followup1 adds nine checks and reruns the unchanged 173-check
base: short physical write with a successful HAL return; no new write on a
repeated request after a torn inactive slot; complete physical write/error return
classified CONFIRMED despite the kernel error; post-write UNKNOWN followed by
exact-target idempotence; short input lengths; nonzero reserved and invalid try.
The two idempotence examples do not authorize blind retries after general UNKNOWN.

.cache/p34-confirm-observe1 adds six read-only scenarios and reruns the unchanged
base: persistent failure, stable unchanged pre-state after failure clears,
stable completed post-state, partially written inactive slot, ineligible STAGED
observation, and changing rounds. The observer never increases the write count.

All three compile/run pairs exit 0, compile logs are empty under
-Wall -Wextra -Werror, and receipts bind commands/logs and inputs. Counts above
must not be added as wholly new independent cases: the 173-check base is reused
in both extensions. No old checkpoint campaign was rerun or modified.

### 13.5 Review Handoff And Remaining Gate

EARLY-09-R1/R2: host implementation and targeted evidence are ready for the
original reviewer; no closure or independent acceptance is claimed here.
The requested review is one consolidated batch covering the trusted-plan
interface/pre-state table, exact transaction reuse/field preservation,
post-error observation semantics, idempotence and valid normal staging case.

Actual device entry legitimacy, physical acquisition/operation identity binding,
EEPROM timing/settling after uncertain writes and exclusive execution ownership
are not established by the host model. No device EEPROM writer, target build,
original Boot modification or physical-entry bypass was added. The NOR writer
and existing BCB read-only port are unchanged. Their takeover/clock/DMA/SD/
watchdog/exit gates and EARLY-08's complete physical restore route remain open.

## 14. Original Review Disposition And Offline Entry Policy

This section appends the user's original-reviewer disposition; it does not
rewrite section 13, its receipts, or the frozen confirmation implementation.
EARLY-09-R1/R2 are closed within the reviewed HOST_ONLY scope. EARLY-09 remains
NEED_EVIDENCE for physical use. No device execution or target EEPROM writer is
introduced here. NOR-only writer and BCB read-only interfaces stay unchanged.

EARLY-09-R3 clarification: in the already-complete branch, differing successive
reads return RC_REJECTED, not RC_UNKNOWN. No confirmation write occurs there.
Section 13.3's general RC_UNKNOWN description is not exhaustive for that branch.
Both outcomes require stop/read-only reconciliation; neither permits retry or
classification as ALREADY/CONFIRMED. RC_NOT_CONFIRMED does not mean zero physical
change, and rc_readback's stable flag does not establish physical settlement.

### 14.1 New Evidence, Separate From Closed Confirmation Tests

Tools/ota/recovery_confirm/entry_policy.py models binding, physical-settlement
prerequisites and result routing. Tools/ota/p34_entry_policy.py records 15 passing
offline scenarios in .cache/p34-entry-policy1. These are implementation self-tests,
not independent acceptance, target execution or additional BCB fault coverage.
The real-gates.json explicitly retains device_execute_ready=false.

The counterexample permits equal old BCB reads at 1000 and 2000 microseconds
while a previously launched physical write finishes at 5100 microseconds.
Observation agreement alone therefore cannot authorize confirmation or exit.
Model evidence identifiers are hypothetical trusted inputs, not signatures,
authentication, an implemented acquisition verifier or proof of device facts.

### 14.2 Separate Acquisition And Execution Plans

The acquisition plan must bind the intended physical board, probe/session,
complete original Boot, permitted read regions, entry profile and operation ID.
It must not require a BCB digest before the first permitted BCB acquisition.
Only after qualified exclusive entry and physical settlement may complete raw
A/B bytes be acquired and arbitrated under the unchanged rules.

The execution plan then seals those exact 128 bytes, their digest, exact internal
App and source hashes, operation identity and acquisition epoch. Both slots,
including the inactive bytes, are mandatory. Version labels alone are inadequate.
Probe identity is not board identity. Historical reads are not a fresh snapshot.
Any reset, reconnect, ownership loss, changed image, BCB drift or uncertain
physical writer invalidates the execution eligibility, even if an operation ID
is reused. The adapter must bind actual observations to this plan; a caller's
assertion that a digest matches is not a trusted capture route.

Use immutable plan/source storage and a single exclusive non-reentrant owner.
Host transport completion, debugger read success and duplicate frames do not
establish physical device ownership. Provenance/authentication and a target
supervisor implementing these requirements remain unimplemented.

### 14.3 Settlement And Result State Table

| Phase | Required evidence | Missing evidence or failure |
| --- | --- | --- |
| Qualify entry | Reset class, power behavior, media disposition, watchdog/debug state and bounded takeover | No entry/reset script; remain in offline preparation |
| Acquire exclusive ownership | CPU/exception/DMA ownership, qualified bus idle, no other possible EEPROM writer | UNKNOWN; no confirmation or assumed coherent snapshot |
| Establish settlement | Exact EEPROM part and operating limits; upper bound on last possible physical STOP; independently bounded elapsed time; stable power; ready ACK after the full horizon | UNKNOWN or wait without classifying; no automatic retry/reset |
| Capture and seal | Settled complete A/B pair, unchanged Boot/App and physical-session binding | Reject stale or drifting acquisition; do not fabricate a new expected pair |
| Confirm once | Eligible exact CONFIRMED pre-state and independently qualified confirmation component | No write for illegal state; no cancellation of an active OTA transaction |
| Observe after attempt | New settlement proof, complete reads, original arbitration, exact derived pair comparison | UNKNOWN stays UNKNOWN; return code cannot override storage |
| Classify | Exact planned post-state or already-complete state and all physical gates | Only then report confirmation, not full OTA completion |
| Exit | Settled NOR/EEPROM, defined DMA/SD disposition, watchdog/power/reset behavior and verified recovery entry | No automatic resume/reset; unresolved exit prevents deployment |

The settlement horizon is latest_possible_STOP + part_max_tWR, not host request
time + a guessed delay. A timeout or interrupted transaction may leave STOP time
unknown. Readiness polling itself needs qualified bus ownership and part-specific
ACK semantics. Clock failure, epoch changes or absent STOP bounds invalidate the
calculation. Equality of two reads is an additional consistency check only.

EEPROM.h's AT24C02 and 5 ms comments do not identify the fitted manufacturer,
grade, voltage/temperature limits or maximum write time. No matching BOM or part
datasheet was located in the tracked inputs. Exact fitted-part identification
has been requested; numerical physical settlement remains UNKNOWN meanwhile.

### 14.4 Takeover Profile Under Evaluation, Not An Executable Entry

Prefer a separately qualified original-Boot holdpoint over arbitrary live-App
halt/resume. The saved group1 disassembly suggests 0x0800199c, following successful
boot_platform_init and before QSPI initialization, initial BCB arbitration and
App handoff. This is a candidate for analysis only: exact complete-Boot/ELF byte
binding, breakpoint mechanism, reset behavior and exception ownership still need
proof. No debugger command file or load-and-go entry is supplied.

Reset before that holdpoint is itself an operation requiring safe media and
power conditions; it cannot solve an unknown in-flight write by assumption.
The existing configure_power_hold path also changes PD2 with a delay. Board power
topology and the effect of that sequence must be qualified before using it as an
entry. Do not resume an interrupted C++ context after RAM has been repurposed.

Tools/ota/p34_recovery_manual.py extracted 25 bounded pages from the repository's
RM_AT32F435_437_V2.07_CH.pdf into .cache/p34-recovery-manual1, binding the input
PDF and parser sources. Relevant manual constraints are:

- Pages 323-325: WDT uses LICK (30-60 kHz); hardware startup is possible; halt
  does not inherently pause WDT; an out-of-window reload can cause reset; the
  command register is write-only and configuration reads have update conditions.
- Pages 678-679: relevant DEBUG pause/configuration state is PORESET-reset, not
  ordinary-system-reset state. WDT and WWDT pause bits require explicit binding.
- Pages 142 and 652: DMA/EDMA request/acknowledgement includes transfer activity;
  CPU halt or masking interrupts is not evidence that a transfer has drained.
- Page 61: clock failure can switch clock source and raise NMI. A nominal clock
  constant is not an elapsed-time proof across that event.

Consequently neither blind watchdog feeding, assumed debug freeze nor ordinary
reset establishes a safe new baseline. A software decision to hold is not proof
the physical device can remain held: if an active watchdog may reset before
settlement, this profile is inadmissible until a bounded remedy is proved.
Natural watchdog reset is not an approved recovery action or timeout guarantee.

### 14.5 Bounded Next Work And Responsibility

Root/implementation next binds the candidate Boot holdpoint to the exact saved
65536-byte Boot and matching ELF, and develops a finite takeover/exit operation
table covering interrupts, DMA/SD, QSPI busy state, watchdog and retained debug
state. This is offline work, not approval to connect or reset. The original
reviewer should review this consolidated entry/settlement design before any
device adapter can rely on it; no old checkpoint matrix needs rerunning.

Hardware-specific open inputs are the fitted EEPROM specification, actual board
power/reset behavior, debugger connection effects, trustworthy clock/STOP bounds
and watchdog configuration. Unknowns must remain named, not replaced with default
timings. A future device plan must separately qualify read acquisition, internal
App restoration, restricted confirmation and exit across real BCB states.
EARLY-08's full recovery route and EARLY-09 physical use remain open. No production
rule, firmware, device state or measured performance is changed by this section.

### 14.6 Saved Holdpoint Byte Binding

Tools/ota/p34_recovery_holdpoint.py ran successfully and wrote
.cache/p34-recovery-holdpoint1/result.json. Its ELF32 ARM program-header mapping
finds exactly one executable Flash mapping for 0x0800199c. The ten bytes
1c22002101a801f07ffd match both that ELF mapping and the complete original Boot
backup. The 14780-byte baseline BIN also matches the complete backup's prefix;
the untouched 65536-byte backup remains the restoration authority.

This closes only the artifact/address identity subcheck mentioned in 14.4.
It does not prove the hardware breakpoint fires, reset reaches it safely,
exceptions cannot run, media is quiescent, or the original Boot is still on the
physical device. device_execute_ready remains false. No target build or device
connection was performed. The next discriminating inputs are the actual EEPROM
part limits and board/reset/watchdog entry conditions, not another BCB host run.

## 15. Finite Takeover And Exit Design Follow-Up

This continues offline work despite the outstanding EEPROM part question.
It is not a device command sequence. No existing Boot, App, NOR writer, BCB
reader or HOST_ONLY confirmation code is modified by this section.

### 15.1 Executed Static Inventory

Tools/ota/p34_recovery_entry_audit.py produced
.cache/p34-recovery-entry-audit1/result.json with eight unique source/instruction
anchors and ELF load-segment analysis. This is a reproducible inventory, not
independent acceptance or execution of the described target paths.

The saved Boot vector's initial MSP is 0x20058000. Saved RAM ports ELF segments
are [0x20058000,0x200598ec) and [0x200598ec,0x2005ecd8), with no overlap with the
saved Boot PT_LOAD ranges. A normally descending Boot stack lies below its
initial MSP, but this observation does not prove a captured live MSP, absence
of corruption/DMA, or future bootstrap placement. Never clear the entire linker
MEMORY region merely because the current ELF occupies only part of it.

Additional concrete dependencies:

| Bound location | Consequence for entry/exit |
| --- | --- |
| Boot platform init calls configure_eeprom_gpio before returning | The candidate holdpoint is before BCB arbitration, not before all EEPROM bus effects. GPIO release could form a STOP depending on the previous physical bus state. A prior STOP bound cannot ignore entry itself. |
| Boot QSPI init enables clocks/muxes and sends 0x66/0x99 | The pre-QSPI holdpoint does not supply QSPI pin/clock setup. Moving the breakpoint after init is not a harmless fix when NOR may still be busy. |
| rr_at32_bcb_capture sets CYCCNT=0 | A previously recorded raw DWT timestamp cannot span capture unchanged. Supervisor timing must be independent or explicitly start a new qualified epoch after this effect. |
| rr_qspi_prepare clears state with memset | Calling prepare again after failure would clear the sticky software barrier. It is not a read-only settlement probe and must not be the timeout recovery route. |
| rr_qspi_read uses usable, which excludes failed state | Existing interfaces do not provide post-timeout NOR status observation. Host timeout plus failed read is not proof that physical programming stopped. |
| R2 HAL_Init at 0x08040f60 calls WDG_Init | Watchdog activation is present in the selected linked App, not merely an unused source function. Arbitrary live-App halt cannot assume an inactive watchdog. |
| core.ld ENTRY(rr_run) and no vector/bootstrap implementation | Linked ports are callable components, not a runnable takeover image. A VTOR range check cannot certify table contents or exception safety. |

### 15.2 Entry Operation Table And Rejected Shortcuts

The preferred profile remains a qualified cold/original-Boot entry, rather than
arbitrary live-App halt. Each row is a design obligation, not permission to
perform its action. Failure before qualification means do not start that action.

| Step | Operation boundary and prerequisite | Failure disposition |
| --- | --- | --- |
| E0 Seal plan | Bind full Boot, finalized source, board identity, exact probe/SDK mode, permitted side effects and acquisition operation; do not yet invent expected BCB bytes | Invalid/unknown provenance: no target access |
| E1 Qualify reset/power | Establish prior EEPROM/NOR settlement and SD/DMA disposition, board PD2 behavior, WDT/WWDT hardware/software state and retained debug state | Unknown media state cannot be cured by reset or power removal; reject entry profile |
| E2 Reach bound holdpoint | Original Boot only; qualified reset class and breakpoint installation must prevent passing the selected point; verify actual PC, Thread mode, privilege, MSP, VTOR and image identity | Wrong PC, missed breakpoint, exception entry or stale epoch: no RAM overlay load and no automatic reset retry |
| E3 Acquire bus/interrupt ownership | Bound CPU stop/resume semantics; actual DMA/EDMA/peripheral request disposition, SysTick and pending exceptions; account for GPIO changes already performed by Boot init | IRQ masking alone is insufficient; do not toggle bus pins to manufacture idle |
| E4 Load isolated bootstrap | Exact future ELF load/zero ranges, vectors, buffers and stack independently bound; verify loaded bytes before execution; preserve old Boot stack until the switch is qualified | Partial load never runs; no jump to rr_run or overwritten interrupted context |
| E5 Establish exception-safe RAM execution | Future bootstrap must define every applicable vector, both MSP phases, NMI/HardFault behavior, barriers and terminal behavior before peripheral access | PRIMASK does not mask NMI/HardFault; unknown vector or stack blocks entry |
| E6 Establish timing and buses | Qualified clock/epoch and bounded watchdog service policy; explicit QSPI pin/clock setup without assuming old App state or blindly sending reset opcodes | No nominal-288MHz-only proof; no inherited DWT baseline |
| E7 Acquire BCB | Account for latest possible STOP including pin setup; establish physical settlement; read complete pair under exclusive ownership, arbitrate and seal execution plan | Failure or drift: no confirmation; read-only reconciliation only after renewed qualification |
| E8 Execute selected component | NOR provisioning, internal-App restoration and confirmation remain separate capabilities and plans; confirmation still has no device implementation | Never add EEPROM writes to existing read-only/NOR-only interfaces |
| E9 Reconcile and exit | Apply the independent table below, compare full expected state and retained recovery route | No return to interrupted App; no automatic reset on error |

E1 cannot be discharged merely by observing E7 later: the earlier reset and GPIO
operations themselves need safe preconditions. A separately qualified power-on
history could establish a different entry profile, but switching profiles needs
its own power/media proof, not an assumed equivalent reset. No production Boot
init code is changed to simplify this experiment.

### 15.3 Timeout, Disconnect And Exit Ownership

| Event | What is known | Required route; forbidden inference |
| --- | --- | --- |
| Host times out before target acknowledgement | Delivery/execution may be ambiguous | Retain operation identity; do not resend mutation or reset. Only an independently qualified observer may determine target state. |
| Source mailbox stalls before a mutation | Source is unavailable, not corrupt by definition | Stop transaction within its bound; already launched media operations still need settlement. Do not extend watchdog lifetime by blind feeding. |
| NOR operation times out | A command may still be physically active | Sticky failure stays set. A future separately reviewed status-only observer may inspect the same chip/controller epoch, with no WREN/program/erase/reset and no clearing of failure. No such adapter is implemented here. |
| EEPROM write returns failure | The inactive slot may be partial or complete | Wait for qualified physical settlement, then use the separate observer and exact original plan; no rc_confirm retry. |
| Debugger disconnects | Exclusive ownership and observation continuity may be lost | Local target terminal behavior must already be bounded and safe. A host cannot promise HOLD if watchdog or exception behavior can reset it. |
| Clock switches, DWT restarts or counter continuity is lost | Prior elapsed-time evidence is invalid | Start a new qualified timing epoch only when a new conservative physical bound can be established; never subtract timestamps across epochs. |
| All comparisons match | Storage identity is known under the stated assumptions | Still require settled devices, qualified watchdog and reset/power path before exit; successful bytes alone do not grant safe reset. |

The future NOR status observer is a separate capability, not a relaxation of
writer.failed or a new prepare call. A controller that cannot safely issue status
while its command engine is in an unknown state remains UNKNOWN. JEDEC ID alone
does not supply chip-specific reset-during-busy guarantees or maximum operation
times. Equivalent settlement evidence is needed for NOR as for EEPROM.

The future supervisor must use one owned timing abstraction. Existing BCB capture
resets DWT, so one admissible design is a new supervisor-owned timebase and a
separately reviewed port integration that never silently resets it. Another is
explicit phase-local epochs with conservative bounds re-established at every
reset. Neither option is implemented or authorized for physical use by this note.

### 15.4 Bounded Implementation Handoff

Owner: root/entry implementation. Next offline deliverable is an isolated RAM
bootstrap design with exact vector/load/stack ranges and terminal paths, plus a
status-only observation design that cannot reset the NOR writer's failure state.
The original reviewer should resolve these boundaries together with E0-E9 before
any executable device adapter is added. No new permission is needed to continue
offline analysis; actual entry remains blocked on its technical gates.

Keep the EEPROM part question local to the physical timing proof. It does not
block source/ELF analysis, bootstrap layout design or observer capability design.
No new speedup, device fault, independent acceptance or deployment readiness is
claimed here. These findings do not reopen the closed Boot checkpoint or R2
conditional stack evidence.

### 15.5 Proposed Isolated Bootstrap Layout And Exception Contract

Proposal only; no target bootstrap has been implemented or linked. Preserve the
existing ports image as evidence rather than changing its entry symbol to imply
it is runnable. A future combined image needs new ELF/MAP/stack/disassembly
bindings and exact-load assertions; the present non-overlap result cannot be
inherited by that future image.

Candidate reservations for evaluating that combined image:

| Half-open RAM range | Proposed owner |
| --- | --- |
| [0x20058000,0x20060000) | Existing callable core/ports and its current data/stack reservations; actual saved occupied end is 0x2005ecd8 |
| [0x20060000,0x20060400) | 1024-byte-aligned immutable-during-execution RAM vector reservation |
| [0x20060400,0x20062000) | Dedicated bootstrap and zero-dependency terminal code, subject to actual link fit |
| [0x20062000,0x20063000) | Supervisor plan/control reservation, never an arbitrary write mailbox |
| [0x20063000,0x20064000) | Unallocated separation; not assumed to be an MPU guard |
| [0x20064000,0x20066000) | Proposed supervisor MSP reservation (8192 bytes), not a proven worst-case bound |

The saved generated full-device startup template contains 131 words (524 bytes),
so a 512-byte table reservation is insufficient. The proposed 1024-byte range is
a layout reservation, not proof of the final vector content. Bind the actual
device IRQ set and every final vector word from the new ELF before use. Preserve
reserved-zero slots; all applicable faults and interrupts target the dedicated
terminal entry, not App, libc, logging, RTOS or the interrupted Boot's callbacks.

The candidate entry contract is privileged Thread mode, Thumb state, an intact
qualified old Boot MSP, no active exception, established ownership and qualified
watchdog handling. Failure of these conditions forbids execution; a debugger must
not forge Thread mode to escape an interrupted handler. Exact debugger register
operations and their side effects remain a separately reviewed profile.

Proposed bootstrap phases:

1. While the original Boot vectors/MSP remain selected, do not repurpose Boot
   storage or call the ports. The qualified entry must already account for NMI,
   faults and DMA during loading. Verify complete new code/vector bytes first.
2. Use a small assembly-only transition with no push/pop or C locals across the
   MSP change. Preserve PRIMASK=1 throughout; establish the RAM VTOR with DSB/ISB
   and switch to the aligned new MSP under a separately verified instruction
   sequence. Do not return through the interrupted LR.
3. With RAM VTOR active but old MSP still selected, an exception must enter the
   same initialization-independent terminal code. With new MSP selected it must
   behave identically. Both hardware-frame budgets require actual target proof.
4. Initialize only designated new data/BSS ranges and seal the operation inputs
   before any C-level dispatch. Never clear a broad SRAM range or assume a
   nonzero readiness flag proves the bootstrap has run.
5. Enter only a fixed selected capability after its physical gates. Any unexpected
   return falls into terminal code, not original Boot/App continuation.

The proposed terminal entry is the previously reviewed style of maskable-IRQ
disable plus a local branch loop, with no memory access or software stack frame.
This is a design reuse, not reuse of an old ELF as proof of new code. It neither
feeds a watchdog nor guarantees indefinite physical hold. The entry profile
must therefore prove that an asynchronous watchdog/power reset cannot violate
media safety; otherwise the profile remains inadmissible before execution.

The full bootstrap stack proof must include the assembly transition, C dispatch,
actual retained port/callback call chains and applicable hardware exception
frames. An 8192-byte reservation or a zero-frame terminal handler is not that
proof. Do not import R2's initialization-stack bound into this different program.

### 15.6 Separate NOR Status Observation Proposal

This interface is deliberately not added to at32_qspi_port.c in the current batch.
The proposed observer has no writer-state pointer, cannot call rr_qspi_prepare,
and cannot clear failed or initialized fields. It reports raw status and evidence
of the controller/session/time bounds, never a recovered write capability.

Proposed input is a sealed observation binding: exact chip/profile, controller
epoch, operation identity and the qualified timeout source. Proposed output is
one of OBS_BUSY, OBS_IDLE_STATUS_ONLY or OBS_UNKNOWN, with raw status and timing
provenance. OBS_IDLE_STATUS_ONLY does not certify payload/header/marker integrity
or authorize exit; the independent full readback/Boot-admission oracle still owns
that decision. It must never be translated to writer.initialized=true.

Minimal capability restrictions and verification cases:

- The only allowed NOR instruction is the profile's status-read opcode (0x05
  for the presently investigated profiles). No WREN, erase, program, chip reset,
  XIP transition or peripheral-reset shortcut is reachable from this interface.
- Entry requires a controller state in which issuing status is already proved
  safe. An outstanding command/FIFO/DMA ambiguity returns OBS_UNKNOWN without
  issuing another command. Do not clear hardware flags to hide that ambiguity.
- Busy status remains busy. Timeout, stopped/changed clock, unexpected chip or
  session identity, transport failure and inconsistent ownership remain UNKNOWN.
- Duplicate observation requests can repeat only observations; a sequence number
  never grants write authority. Writer failure state must be byte-identical before
  and after every modeled outcome.
- Tests for the eventual implementation must trace every bus opcode and register
  mutation, inject busy/idle/timeout/controller-unknown outcomes and prove that
  the observer never dispatches the writer or returns a resume token.

This proposal intentionally leaves genuinely unobservable controller states
UNKNOWN. For those states, a complete physical recovery plan needs a separately
qualified remedy; silently escalating to reset would violate the design.

### 15.7 Verification And Consolidated Review Boundary

New ELF parser checks ran through the contained receipt helper:
.cache/p34-recovery-entry-check1 contains the command/log receipt and result for
eight passing tests. They cover zero-fill extent, non-ARM/wrong encoding,
truncated headers, out-of-file payload, file/memory inconsistency, address wrap
and absent load segments. They validate the new inventory helper only, not RAM
execution or physical safety. The closed confirmation/checkpoint matrices were
not rerun. No project Trellis directory is present; existing host-tool patterns
and project governance were used.

The original reviewer now has one bounded design packet: E0-E9, the proposed
bootstrap ownership/exception contract, and the independent NOR observer
capability. Requested decision is whether these are the appropriate isolated
implementation boundaries, not permission to execute a device plan. Root keeps
physical identification and timing questions separate rather than blocking all
offline progress on the EEPROM part alone.

## 16. EARLY-10/11 First Isolated Implementation

The original review of section 15 accepts corresponding isolated implementation,
including bootstrap, independent observer and supervisor timebase integration.
This section records implementation self-tests, not closure or device execution.
No original Boot, existing NOR writer, BCB reader or HOST_ONLY confirmation
component was changed. The EEPROM part question did not block this work.

### 16.1 Owned Timebase Interface And Fixed Status Observer

Tools/ota/recovery_entry/runtime.c/h provide re_begin/re_alive and re_observe.
The time interface only samples; it has no set/reset callback. A deadline binds
the expected nonzero epoch and frequency, a less-than-half-range tick budget and
monotonically increasing elapsed ticks. Clock/epoch change, backward elapsed
time, timeout and exhausted 4096-poll bound latch deadline failure. A stopped
counter cannot hang the software loop. Single counter wrap is modeled; an actual
unobserved full wrap is excluded by the required clock/observation qualification,
not proved by modulo arithmetic. No minimum physical waiting interval is proved
by these maximum-wait tests.

re_observe accepts independent I/O and clock callbacks, no writer-state pointer.
It requires an externally qualified exclusive ownership callback and rejects
stale command completion, RX data, unsupported control state, XIP and abort.
The control profile is divider 8/mode 0, with only xipidle ignored. These register
checks alone do not establish controller/DMA quiescence. There is deliberately
no physical MMIO adapter or fabricated ownership provider in this batch.

Every permitted register mutation is fixed:

| QSPI-relative offset | Value | Purpose |
| --- | --- | --- |
| 0x00 | 0x00000000 | No address |
| 0x04 | 0x01000000 | One instruction byte, no address or dummy cycles |
| 0x08 | 0x00000001 | One receive byte |
| 0x0C | 0x05000000 | Launch only opcode 0x05, mode 111, read direction |

The observer reads control/FIFO/completion at 0x10/0x18/0x24 and one data byte at
0x100. It does not clear completion, reset the controller, change XIP or call
prepare. Consequently a subsequent observation seeing stale completion rejects
with UNKNOWN; this is not yet a reusable physical-controller observation route.
BUSY and IDLE_STATUS_ONLY are descriptive, not recovery/write/exit permits.
After any ambiguous partial register operation the caller must retain UNKNOWN.

Tools/ota/p34_entry_runtime.py produced .cache/p34-entry-runtime1 with 15 passing
C host scenarios, compile/run receipts and empty compile log under
-Wall -Wextra -Werror. Cases include busy/idle, unknown ownership/controller,
stale RX/completion, timeout/stopped counter, epoch/frequency change, write-return
failure, counter wrap/backward movement and invalid deadline budget. The mock
records every write offset/value and forbids any outside the four command words.
Writer state is not passed to the observer and is compared unchanged in tests;
this does not prove that an arbitrary future callback cannot have side effects.
Target adapters must be separately bound and audited.

### 16.2 New Terminal-Only RAM Scaffold

bootstrap.S and bootstrap.ld now build a new ELF, not a relabeled ports ELF.
Tools/ota/p34_entry_bootstrap.py reuses the bound GCC Boot compile options and
adds freestanding/no-builtin plus explicit assembler GNU-stack metadata.

The first build (.cache/p34-entry-bootstrap1) failed at link because runtime.o
lacked .note.GNU-stack metadata while the assembly object provided it; fatal
warnings remained enabled. That failure is preserved. A new build in
.cache/p34-entry-bootstrap2 passed with zero compile/link warnings and errors.
GNU-stack metadata is not an MPU or SRAM execution-permission guarantee.

The new ELF has 1200 bytes text, zero initialized data and four bytes BSS.
Its entry is 0x20060401 (Thumb), table is 0x20060000, terminal is 0x2006047f,
new MSP is 0x20066000 and only [0x20062000,0x20062004) is zeroed. The 131 vector
words preserve the declared reserved-zero slots; all other applicable exception
slots target the four-byte terminal (72b6fee7). The second table word targets the
bootstrap, but this is not a reset-load procedure or permission to boot it.

Actual disassembly checks IPSR, CONTROL bits nPRIV/SPSEL/FPCA, PRIMASK, old MSP
alignment/range and FPCCR.LSPACT before the transition. It writes VTOR with
DSB/ISB, switches MSP without a C frame or push/pop, zeros only the four-byte BSS,
sets its own seen word and branches to terminal. There is no old-LR return,
media dispatch, watchdog feeding, reset or application continuation. The observer
is retained in the ELF for target compilation evidence but is not called by the
bootstrap. The marker is diagnostic only, not a readiness/authentication token.

Important: the old-MSP range check is a coarse rejection guard, not proof of
remaining exception-frame room. An actual entry plan must further bind the
captured old MSP and its margin below it. Invalid-context branches also do not
prove safe execution from an already invalid/unprivileged context; the qualified
entry must reject those contexts before running any new instruction.

### 16.3 Exact-Profile Load Checks And Negative Cases

load_contract.py is explicitly an offline checker, not a debugger loader or a
general secure ELF parser. It checks ARM ELF identity/entry, each PT_LOAD's VMA
and physical/LMA equality, exact three permitted load regions, file mapping,
segment overlap, section membership, exact zero range, segment permissions,
first MSP, every vector target and terminal bytes. A trusted whole-artifact
digest is still required; semantic checks do not authenticate executable code.

.cache/p34-entry-contract1 records six passing unittest methods against the new
ELF, including VMA-in-range/LMA-out-of-range, wrong entry, wrong fault vector,
zero-range relocation into the new stack and seven invalid-context subcases.
The latter cover PSP selection, FPCA, unprivileged mode, active exception,
PRIMASK, wrong stack region and lazy FP activity. These host predicates agree
with the stated guards but are not instruction-level exception execution tests.
The positive sample remains device_execute_ready=false.

### 16.4 Stack And Integration Boundaries Still Open

The bootstrap-to-terminal path has no calls, software stack frames or SP-relative
accesses in its current disassembly. That is a new-product path fact, not use of
R2's old stack evidence. Both MSP stages still require bound physical entry and
hardware exception-frame margins. In particular, the broad old-MSP acceptance
range must not be treated as a sufficient hardware-stack budget.

The retained C compiler records are re_begin=24B, re_alive=24B and re_observe=88B,
all static. Observer/timebase callbacks have no physical implementations here,
so the dispatched observer's complete target chain remains UNKNOWN. Do not sum
these records into a false complete bound. New dispatch/adapters will require
their own ELF and callback/exception analysis.

Next implementation work is a qualified target clock/ownership adapter and a
supervisor dispatch that preserves these independent capabilities, plus tighter
old-stack margin admission and target-bound complete-chain verification. No
existing BCB capture is called across the new clock deadline: it still resets
DWT and cannot be silently connected. Status observation alone cannot perform
post-failure full NOR readback. The exact controller recovery/read-only route,
physical entry, media settlement and exit remain their named open gates.

### 16.5 Old-Stack Margin Refinement In The Same Batch

The broad old-MSP guard noted above was tightened without waiting for a new
review round. Current bootstrap3 requires MSP >= 0x200570d8, retaining at least
216 bytes above the lower comparison boundary 0x20057000. The same check is in
the host predicate, and the exact literal is checked in the new ELF. The previous
revision's modified source bytes were preserved under
.cache/p34-entry-revision2-sources; bootstrap2/contract1 are superseded experiments,
not current source bindings. Bootstrap3 also saves its actual compilation sources
inside its own output directory before compiling.

.cache/p34-entry-bootstrap3 is the selected scaffold. It retains the same entry,
table, terminal, zero range and size. .cache/p34-entry-contract2 has seven passing
test methods, including rejection of the old insufficient-margin literal and an
additional invalid-context subcase below the margin. Original failed build and
earlier test receipts were not overwritten or represented as new execution.

For the qualified entry only, PRIMASK remains 1, Thread uses MSP, FPCA/LSPACT are
clear, no FP instructions execute, and all new exception handlers terminate
without returning. The scaffold itself adds zero software stack bytes; two
conservative 108-byte hardware frames reserve 216 bytes for NMI/HardFault paths.
That reservation is enforced below the admitted old MSP and fits in the new
8192-byte stack. This does not establish the preceding Boot execution, load-time
exceptions, invalid-context behavior, watchdog hold duration, arbitrary faults
or a future observer dispatch. Original Boot vector behavior and actual entry
state remain part of physical qualification. The observer's target callback
chain remains UNKNOWN, independently of this terminal-only path calculation.

## 17. Root Takeover: Linked Dispatch And Non-Resetting Capture Clock

Owner: current Codex root, 2026-10-05. The user requested takeover and continuous
execution until actual intervention is needed. This batch completes the interrupted
offline callback/stack analysis and advances the admitted isolated implementation.
It does not authorize itself as independent acceptance or infer physical facts from
the user's operating authorization. No device, original Boot, NOR writer, original
BCB reader, or HOST_ONLY confirmation component was changed or executed.

### 17.1 Linked Call Graph And Load Boundary

`Tools/ota/recovery_entry/stack_audit.py` reuses the conservative `bound` graph
walker from `p34_boot_stack.py`. It distinguishes ELF STT_FUNC symbols from nm's
T/t literal-table labels, verifies instruction bytes against actual ELF load
bytes, includes direct/tail edges, and accounts for the private supervisor's
fixed callback target supersets. Unknown targets, dynamic/missing/duplicate frames,
unbound indirect transfers, unexpected FP instructions and recursion fail closed.
This is a source-reviewed callback binding, not a general pointer-analysis engine.

The first parser run rejected a literal table that nm marked `t`; classification
was corrected to use ELF symbol types, not by assigning the table a zero frame.
The original saved supervisor2 ELF then gave 288 software bytes plus 216 exception
reserve. `.cache/p34-entry-stack1/result.json` records that intermediate analysis;
it is not the current dispatch product. Seven analyzer tests passed, and were
checked again after the final parser extension in
`.cache/p34-entry-dispatch3/stack-followup`.

The selected new artifact is `.cache/p34-entry-dispatch3/entry.elf`:

- SHA-256: `a405f117232ffd0924b1a980e66004cb15fae637db6bf69df171775d108ee019`.
- GNU size: text 2516, initialized data 0, BSS 64 bytes.
- Exact zero range: `[0x20062000,0x20062040)`; no broad PT_LOAD-gap clearing.
- Full dispatched software-chain bound: 336 bytes; with 216-byte exception
  reserve: 552 bytes, against the 8192-byte new MSP reservation.
- The old-MSP assembly transition still has no software frame and retains its
  216-byte admission margin. Neither calculation proves load-time Boot behavior,
  watchdog hold duration, physical reset entry or an arbitrary invalid context.

The longest conservative chain is bootstrap -> entry_dispatch -> dispatch_once
-> supervise_once -> observe -> begin -> begin_limited -> sample -> qualified
-> platform_snapshot. Tail edges retain the complete caller frame. The exact load
checker now verifies the zero-loop literals as well as segment/section bounds;
the original four-byte scaffold and new 64-byte dispatched variant are explicit
profiles and cannot substitute for each other.

### 17.2 One-Shot Dispatch Contract

`re_dispatch_once(const re_profile *)` consumes one trusted, immutable profile
per bootstrap. Target entry only passes `re_compiled_profile`, an 80-byte const
object verified as all zero in the ELF. It is deliberately unqualified: the
selected binary cannot issue NOR commands through its ordinary entry path.
Do not patch RAM flags or treat an operation ID as authentication. A physical
profile requires original acquisition evidence and a separately reviewed build.

The target bootstrap branches to `re_entry_dispatch` only when built with
`RE_ENTRY_DISPATCH`; the normal scaffold variant still terminates. The C entry
and assembly terminal are declared non-returning. No interrupted Boot LR or App
continuation is a valid exit. Reports contain started/epoch/operation, observation,
status-valid/raw status and a last-written completion marker. DSB precedes that
marker; incomplete reports remain UNKNOWN. Completed BUSY or IDLE_STATUS_ONLY
reports are diagnostics, never write/integrity/reset/exit permits. A repeated call
does not touch hardware or replace the previous report, including after rejection.

| Case | Required result |
| --- | --- |
| Qualified mock, idle/busy NOR | One fixed 0x05 observation; correct diagnostic |
| Invalid profile or missing input | UNKNOWN; zero platform reads/writes |
| Unknown controller, clock drift, timeout or partial write failure | UNKNOWN; no retry |
| Duplicate dispatch | No further I/O, barrier or report mutation |
| Wrong LMA/vector, stack overlap, wrong zero-loop endpoint | Reject offline load check |
| Earlier four-byte scaffold offered as dispatch image | Reject profile mismatch |

### 17.3 Minimum Wait And BCB Clock Integration

`re_begin_limited(clock, epoch, hz, tick_budget, poll_limit, deadline)` adds a
bounded sample count (1..1000000) without resetting the underlying counter.
Existing `re_begin` retains its 4096-sample default. `re_wait_minimum(clock,
deadline, ticks)` proves a positive minimum elapsed interval only under the
already-qualified clock, within the original cumulative deadline. It never
creates a new epoch or restarts the whole-capture budget. A failed initialization
is rejected before reading uninitialized deadline fields.

`re_capture_once(session, profile, clock, pins, observation)` wraps the unchanged
`rr_bcb_capture` A/B/A/B reader and unchanged original arbiter. Its pause uses
1440 ticks at the required 288 MHz; cumulative budget is at most 576000000 ticks
and one million samples. These are software bounds, not evidence of EEPROM tWR.
The capture still transmits only read-address/pointer sequences, not NVM data.

Pin callbacks require already-configured, exclusively owned open-drain GPIO.
The wrapper does not initialize GPIO or enable/reset DWT. If clock or ownership
qualification fails, it suppresses every subsequent pin change, including the
old reader's best-effort line release: an unqualified STOP must not be manufactured
as cleanup. Physical bus disposition remains UNKNOWN; this is not a safe-HOLD
claim. Rejected calls consume the session, and output data is usable only after
a successful return with the original arbiter result. No write interface exists.

This closes the portable timing integration only. The capture wrapper and runtime
compile for ARM, but are not linked into the selected NOR-dispatch product or
bound to physical GPIO callbacks. The old `rr_at32_bcb_capture` still establishes
its own DWT baseline and must not be called inside this new timing epoch.
Selecting/configuring a real pin/clock acquisition adapter depends on the E1/E3/E6
physical profile; hypothetical callbacks are not device evidence.

### 17.4 Executed Development Verification

Commands use `python -I -S -B -X utf8` from the project root. New outputs and
controllable HOME/TEMP/cache paths remain under the project `.cache` directories.

| Entry / evidence | Executed scope |
| --- | --- |
| `Tools/ota/p34_entry_dispatch.py` / `.cache/p34-entry-dispatch3` | 8 dispatch, 55 supervisor, 15 runtime, 12 minimum-wait scenarios; 7 load/stack unittest methods; GCC target link, symbols/disassembly/size; zero warnings/errors |
| `tests/boot/test_p34_entry_stack.py` / dispatch3 `stack-followup` | 7 analyzer tests: actual product, byte drift, dynamic/missing frames, missing function body, recursion and conservative tail accounting |
| `Tools/ota/p34_entry_capture.py` / `.cache/p34-entry-capture1` | 8 new capture/time/ownership integration scenarios; normal and counter-wrap complete captures; clock loss, stopped clock, invalid admission, deadline and inconsistent pair; ARM object compilation only |

Minimum-wait testing includes 5501 consecutive pauses without a counter/epoch
reset. Capture testing reuses the original wire fixture, not its closed 5499-case
campaign. Closed confirmation/Boot checkpoint matrices were not rerun. Earlier
dispatch1/2 products remain as superseded iterations, with their actual source
snapshots and logs; they are not relabeled as the final build.

The final audit re-read 158 dispatch and 28 capture input/output records: all
186 sizes and SHA-256 bindings matched. No formal acceptance, hardware execution,
speed result, release, commit or push is claimed. Repository Trellis metadata is
absent; existing project/host-tool conventions apply.

### 17.5 Physical Entry: Concrete Missing Inputs

The next physical route remains the qualified original-Boot profile in E0-E9.
Source/model work does not replace its missing facts:

| Gate | Still required | Next owner/action |
| --- | --- | --- |
| E1 media settlement | Fitted EEPROM manufacturer/full part and maximum write-cycle semantics; NOR part/profile and prior-operation history | User supplies existing BOM/marking/board reference; root binds datasheets and STOP horizon before dependent actions |
| E1 reset/power | Board power/PD2 behavior, power source, watchdog option/reset class and retained debug state | Root resolves from board documentation and a bounded reviewed acquisition profile, not by blind reset |
| E2/E3 acquisition | Exact probe/SDK effects, breakpoint-before-effects guarantee and DMA/SD/exception ownership | Root constructs the finite acquisition plan from the qualified starting state; no speculative debugger script |
| E6/E7 target capture | Physical clock continuity and already-qualified pin configuration | Bind real callbacks and new combined ELF/stack after profile choice; do not use generic mock qualification flags |
| E8/E9 restoration/exit | Separate physical confirmation adapter, full integrity reconciliation and safe exit route | Preserve HOST_ONLY confirmation and separate capabilities until the physical prerequisites are met |

The repository search still finds only generic AT24C02/approximately-5ms text,
not manufacturer/full ordering code or fitted-device evidence. An asynchronous
request for an existing BOM/marking remains outstanding. No immediate disassembly,
power removal, reset or new device operation was requested. Authorization is no
longer the missing item; these physical inputs cannot be invented by software.

## 18. User-Supplied AT24C02S SOT-23-5 Datasheet

The user supplied the EEPROM datasheet and identified the fitted package as
SOT-23-5. This replaces section 17.5's missing-datasheet condition; do not ask
again for the same file or keep classifying the 5 ms value as a source comment.
The user-to-device association is supplied by the user, not a new physical
marking/probe observation. No device was accessed for this document analysis.

Source: `.cc-connect/attachments/om_x100b63077fcc3ca4b4850cb5e80f004/`
`f863e74e-a546-4b73-b073-66756f5404e4_BC6BD607A5D8CE4770A7F285C60742AB.pdf`.
The 20-page, 1255990-byte file is titled AT24C02S Datasheet Rev.1.4. SHA-256:
`80511a6fe61d1e5b60b136cafb5c34310092249da30142ce3ef47a4f222ddefe`.
Unmodified source and parser inputs are bound by
`.cache/p34-eeprom-reference1/result.json`; text extraction uses one-based PDF
page numbers. The source attachment was not renamed or overwritten.

### 18.1 Device And Package Facts

| Item | Datasheet statement and page |
| --- | --- |
| Density / page size | 2 Kbit = 256 bytes; 8 bytes per write page (1, 10) |
| SOT-23-5 pins | 1 SCL, 2 GND, 3 SDA, 4 VCC, 5 WCB (2, right-hand diagram); the table below that diagram instead lists the eight-pin package |
| WCB | High inhibits all array writes; low allows writing; floating is internally pulled down (3, 9) |
| LI / MI supplies | LI 1.6..5.5 V; MI 1.7..5.5 V (1, 4). Use the common 1.7..5.5 V range unless the variant is independently identified |
| AC timing conditions | VCC 1.7..5.5 V, ambient -40..85 C, stated loading conditions (5); do not silently extend the 5 ms AC-table guarantee below 1.7 V |
| SCL maximum | 400 kHz for 1.7 <= VCC < 2.5 V; 1 MHz for 2.5 <= VCC <= 5.5 V (5) |
| Address format | 1010 E2 E1 E0 R/W (9). The five-pin diagram has no external E pins; it does not explicitly state their internal bond options. Preserve the existing 0x50 profile, but bind its actual ACK/device association during qualified acquisition |

The footer identifies `tdsemic.net`, but page 13 retains a `P24C02A` ordering
example and `P = Puya Semiconductor`. Treat this as an internal document
inconsistency, not proof that the fitted device is a Puya P24C02A or an Atmel part.
It does not remove the explicit, mutually consistent AT24C02S timing statements
on pages 1, 5, 6, 10 and 11. No alternative part number is invented here.

### 18.2 Write Completion And Bus Semantics

Page 5 table 3-3 explicitly specifies **tWR maximum 5 ms** for both voltage
columns. Page 6 defines the interval as the valid STOP of a write sequence to
the end of the internal clear/write cycle. Page 10 says inputs are disabled
during that cycle. Page 11 says the device responds to address ACK polling only
after the internal write cycle has completed.

Therefore the finite settlement profile may use 5000 microseconds as its
datasheet maximum under the stated device/voltage/temperature/power assumptions.
The existing 10 ms software ACK-poll timeout is a host/firmware wait bound, not
the chip's specified maximum. A qualified address ACK is meaningful completion
evidence, not just equality of two data snapshots. The current model's extra
requirement of an ACK after its conservative STOP+5ms horizon is stricter than
the datasheet, not a manufacturer requirement; it is not silently relaxed here.

The latest possible STOP must include any GPIO or protocol transition caused by
entry itself. Losing power, counter continuity, ownership or the STOP bound still
invalidates an elapsed-time argument. This datasheet does not prove a particular
board's supply, last STOP or WCB state, and does not authorize resetting a busy
system to manufacture an idle observation.

Page-write addresses wrap inside the same 8-byte page, so every write must use
at most `8 - (address & 7)` bytes before its STOP. Page boundaries do not impose
the same restriction on sequential reads: those advance through the 256-byte
array and wrap at its end (10..12). The original RAM reader's pointer write,
repeated START, read-address, ACKs, final NACK and STOP match the documented
random/sequential read protocol. Its pointer phase contains no array data byte.

The application EEPROM helper's separate STOP between setting the pointer and
requesting data is not the exact repeated-START sequence illustrated on pages
11..12. No production/Boot code is changed on that observation, and existing
hardware results are not invalidated or rerun. New acquisition continues to use
the already-established RAM reader's documented repeated-START sequence.

Page 8 documents protocol recovery as START, nine clocks, START then STOP.
That is not an instruction to inject recovery clocks during an unknown write,
nor evidence of media integrity or safe power removal. Do not add it as automatic
failure cleanup to the read-only capture wrapper.

### 18.3 Consequence For The Current Implementation

No EEPROM algorithm, page size or timeout needs an immediate change merely to
match this manual. The existing eight-byte splitting and bounded ACK polling
have a concrete reference now. A 5-microsecond pause exceeds the listed minimum
low/high/setup times, provided the 288 MHz timing premise is real; it does not
prove SDA/SCL electrical rise time or external pull-up characteristics.

The EEPROM documentation/nominal maximum-write-time input is now available.
Remaining physical entry work concerns actual power/reset, clock/probe/ownership
and acquisition history, not another request for an EEPROM datasheet. Existing
HOST_ONLY confirmation and device_execute_ready=false boundaries remain until
their independent physical prerequisites are met. This analysis did not run an
OTA, reset, EEPROM write, hardware read or performance experiment.

## 19. Fixed BCB Target Adapter And Host Retrieval Route

Owner: current Codex root, 2026-10-05. Continued implementation after the user
requested no stage-completion pauses. This supersedes section 17's unlinked BCB
wrapper status, but not the physical-entry prerequisites or independent review.
The supplied EEPROM manual remains accepted as the nominal timing reference;
no repeated request for that manual is pending.

### 19.1 Fixed Pins, Shared Snapshot Predicate, Separate Capabilities

`qualification.c::re_snapshot_matches` now provides the same pure comparison
for the existing NOR adapter and new BCB adapter. It does not establish ownership.
`bcb_target.c::re_capture_target_once` binds the actual platform snapshot and
fixed GPIO callbacks to the previously tested capture/timebase wrapper. All
callback failures latch; no retry, reinitialization, watchdog feed or resume
operation is provided.

`bcb_platform_at32.c` only permits PB6/PB7. Before using them it checks GPIOB's
clock is already enabled, selected pins are output/open-drain/pull-up/moderate
drive, and at initial admission both output release bits and input levels are
high. The masks match the original Boot's `configure_eeprom_gpio`, not generic
reset defaults. Idle is required once at entry, not during legitimate data bits.
Subsequent access still checks pin configuration and the shared CPU/clock/DMA
snapshot. No GPIO mode, pull, clock-enable, DWT or peripheral-reset write exists.

Target disassembly confirms the only pin-output stores are GPIOB base 0x40020400
plus 0x18 (set) or 0x28 (clear), after restricting the value to bit 6 or 7 and
checking configuration. Input reads use +0x10. The 12 GPIO-model scenarios compare
the register image before/after and reject invalid modes, wrong pins/values,
disabled clock and non-idle entry. This is not electrical waveform validation.

BCB and NOR are separate linked entry variants. The BCB variant branches from
the same checked assembly transition into `re_bcb_entry_dispatch`, obtains one
capture, publishes a diagnostic and terminates without returning. Its const
80-byte compiled profile is still all zero, so normal entry rejects before GPIO
or platform reads. The selected BCB ELF contains no `bcb_commit`, NOR observer,
NOR MMIO writer, old DWT-resetting BCB entry or unused writer workspace symbol.
Existing writer/reader/arbiter source bytes were not modified.

### 19.2 Actual Target Layout And Executed Tests

The original arbiter brings a 1024-byte CRC table and four-byte ready flag.
The initial 328-byte BCB BSS assumption was rejected by the exact-load checker;
it was not accepted as an incomplete zero range. Current BSS is exactly 1356
bytes, `[0x20062000,0x2006254c)`, including bootstrap marker, 316-byte report,
session, snapshot pointer, CRC-ready flag and table. It remains below the sealed
input reservation at 0x20062800 and well below the stack at 0x20064000.

| Selected artifact | GNU text/data/BSS | Conservative stack including 216B exception reserve | SHA-256 |
| --- | --- | --- | --- |
| `.cache/p34-entry-bcb4/entry.elf` | 4008 / 0 / 1356 | 1164B of 8192B | `01aa1d4806f1fcb6476dfc42189f70bdbeb3e627ed8704f411a87d27c51ee77c` |
| `.cache/p34-entry-dispatch4/entry.elf` | 2536 / 0 / 64 | 556B of 8192B | `7be00361090da2233346a55386c3785cfc138baf9c5083fedc5866e24ee101bf` |

Both selected builds use the contained `p34_entry_dispatch.py` runner, with
`--capability bcb` or its default NOR capability and a fresh output directory.
Both compile/link with zero warnings and errors, retain full source snapshots,
and pass eight exact load/stack checks. The BCB worst path includes the actual
reader, original arbiter and CRC implementation; private callback and indirect
tail-call targets are explicit conservative supersets, not assumed zero frames.

The new BCB path passes 12 target-adapter/dispatch scenarios and 12 GPIO scenarios.
The shared change also passes the existing 55 supervisor, 8 NOR dispatch,
15 runtime and 12 minimum-wait scenarios. These are scoped development checks,
not an independent acceptance campaign or a repetition of closed confirmation
and Boot checkpoint matrices. bcb1's snapshot include-path compile failure and
bcb2's exact-BSS check failure remain preserved. bcb3 is the intermediate linked
product before host report round-trip coverage; bcb4 is selected.

### 19.3 Report Decode And RAM Staging Contracts

`report.py::decode_bcb(raw, expected_epoch, expected_operation)` accepts the exact
316-byte little-endian report only with a nonzero matching expected epoch and
32-byte operation, started/completion fields, valid counters and known result
codes. A successful capture must contain equal complete A/B pairs; the host
recomputes record CRC/magic/schema validity and original 16-bit sequence
arbitration rather than trusting the target's active-slot number. Both-invalid
is a complete capture but not an admitted BCB record. Failure reports cannot
claim stable usable data. Every result explicitly carries no device permission.

Eight decoder tests consume all 12 C-produced report scenarios and cover
truncation, binding/marker changes, inconsistent pairs, forged active slot,
both-invalid records, wrap/tie/half-range sequence cases and false stable failure.
BCB record validity alone is not the separate plan/canonical-state confirmation
gate. No report authorizes EEPROM writes, reset or retry.

`loader.py::stage_elf` is an offline-tested RAM staging layer with no debugger
adapter and no execute/reset/retry API. It requires a trusted ELF digest and
qualified original-Boot context (exact complete Boot hash and 0x0800199c holdpoint,
MSP/VTOR, halted privileged Thread state, consistent xPSR/IPSR and explicit power,
watchdog and ownership prerequisites). It writes only file-backed vector/code
segments, in <=256-byte chunks, with immediate and final whole-segment comparison
and context/deadline checks. It never zeros BSS or segment gaps from the host.
Any failure consumes the session and leaves potentially partial RAM unexecuted.

`.cache/p34-entry-loader2` contains nine passing model tests, including cross-chunk
corruption, context changes, wrong digest/LMA, deadline, invalid power/stack/Thumb
context and duplicate invocation after success or failure. A real transport must
bound each callback itself; the model's outer deadline is not a way to interrupt
a hung native debugger call. Its only success is RAM_IMAGE_VERIFIED_NOT_EXECUTED.
It must not be connected to a live debugger by simply fabricating context flags.

### 19.4 Probe Connection Investigation And Next Physical Gate

The installed `UM08001_JLink.pdf` is a four-page getting-started document pointing
to SEGGER's online manual. The current command reference was retrieved and bound
in `.cache/p34-probe-reference1`; the oldid URL returned HTTP 410, so the retained
live response is identified by its actual digest, not claimed as an immutable URL.
The installed V8.18 DLL was read as bytes, not loaded or executed. It contains
the investigated command strings, but that is not an executed capability test.

Relevant documented candidates for a future bounded connection profile:

- ForceAttachTarget skips target initialization, including RAM initialization.
- InhibitConnectRetries disables fallback connection attempts that may toggle
  reset. It is distinct from omitting an explicit reset command.
- SetLogVerbose logs actual target data reads/writes. Earlier logs contain write
  addresses/counts but not values, so they cannot prove transient state unchanged.
- DisableCortexMXPSRAutoCorrectTBit prevents an implicit XPSR correction.
- RAM initialization and restart-on-close/debug-deinit policies need explicit
  version-bound selection; none is assumed from an old default setting.

These are reference findings, not a generated or executed debugger script. The
old `sdk_write_audit_passed=false` remains unchanged. The intended next probe is
minimal acquisition, not a reset, firmware load or recovery repair: first qualify
the board/power and connection effects, then capture complete original values
with no automatic fallback, and classify any unknown result before further work.

The supply question pending at this point was subsequently answered by the user;
see section 19.5. No unplugging, reset or new short device window was requested.
Remaining physical observations include watchdog/retained debug state and DMA/SD
disposition under that actual supply profile. EEPROM timing documentation is no
longer the missing input. The actual debug transport and nonzero physical profile
must follow those facts, not precede them.

The selected NOR/BCB bundles' 163+235 input/output size and SHA-256 bindings were
re-read and matched. No device was opened, flashed, halted, reset, read or written
in this continuation. No commit, push, release or new throughput claim was made.

### 19.5 Direct J-Link Supply And Observation Preparation

User confirmation: J-Link 3.3V and GND connect directly to the board supply;
the board stays powered while J-Link remains connected. Use this as the current
physical supply premise, not USB/battery speculation. Do not unplug the probe,
toggle its supply, or ask the same supply question again. This is user-provided
wiring information, not a measured voltage/brownout guarantee, watchdog freeze
qualification or proof that reset leaves all peripheral state unchanged.

Important command distinction: SEGGER's retained command reference explicitly
says `DisablePowerSupplyOnClose` **disables target power on close**. It is not a
keep-power command and must not be sent here. `SetRestartOnClose = 0` suppresses
automatic resume; `SetSkipDebugDeInit = 1` avoids normal debug-bit cleanup, but
neither promises that attach made no transient changes. No target-power command
appears in the new observation policy.

`recovery_entry/probe.py::Observation(backend, emit, seconds=30)` now models the
fixed configuration-before-connect sequence, one attempt per object, exact
read scope, and close-on-error behavior. It has no DLL loading, write, halt,
reset, flash, power or recovery API. An injected real backend still needs native
history authority, verified signatures, an owned finite worker and real SDK
qualification; a successful model does not supply them.

- Before opening: suppress GUI/firmware update, enable verbose logs, set explicit
  no-resume/skip-debug-deinit close policy. Repeat close policy after device selection.
- Before connecting: generic CORTEX-M4, ForceAttachTarget, no RAM initialization,
  no fallback connection retries, no FlashBP/FlashDL/XPSR correction, SWD 1000kHz.
  Check every setting response, including the cache command's previous-value
  semantics; a rejected setting must prevent target connect.
- Reads: aligned <=4096-byte chunks inside complete 64KiB original Boot only,
  plus the named core registers in `CORE_READS`. DWT is read as CTRL+CYCCNT in
  eight bytes, not the V8.18 cached scalar path. RAM/GPIO/NOR access is excluded.
- Keep the first DHCSR value and its reset-sticky flag. Reading DHCSR itself
  clears S_RESET_ST; do not discard it and claim a reset-free observation.
- On late/short/failed reads, consume the session and close once. Even an evidence
  sink failure attempts close. A failed close is uncertain, not retry permission.
  A native call requires an outer process deadline; Python clock checks cannot
  interrupt a hung DLL. Raw post-attach values are not pre-attach originals.

Selected `.cache/p34-entry-probe2/result.json`: 17 development unittest methods
PASS. The previous 15-test revision remains in `p34-entry-probe1/source`.
Tests include every rejected configuration, zero-return plus error text, partial
open, unexpected auto-connect, failed connect, invalid SDK statuses, cache return
semantics, read boundaries, sticky reset retention, timeouts, short reads, failed
evidence sink and failed close. Five unchanged historical SDK logs still contain
23 CPU_WriteMem calls. `scan_sdk_writes` inventories them and preserves unknown
write spellings; it does not invent a verbose payload grammar or promote empty
logs to success. Both SDK audit and transient-state proof remain false.

Read-only Windows USB/process enumeration in this continuation found exactly
`USB\VID_1366&PID_0101\000000123456` and no competing debugger processes. It did
not open J-Link. The x64 DLL was inspected as bytes: PE machine 0x8664, SHA-256
`6b6f7f15c0f3dfe93c985e14dc6e7e3efa47ad563579def9370602a019873908`.

Finite next acquisition cell, **NOT_STARTED**:

| Field | Planned scope and stopping rule |
| --- | --- |
| Owner/root | Current Codex root, same board/probe, `D:\github\my\E-Track`; serialize against all other probe users |
| Entry | Recheck USB ownership, source/DLL bindings and contained outputs immediately before loading SDK; qualify actual backend and finite worker first |
| Matrix | One no-reset attach to discriminate current connection effects; two fixed core samples around one complete Boot read; no automatic repeat after an uncertain result |
| Time | <=30s observation, separate <=5s close allowance, <=45s outer worker lifetime including setup; no unbounded native call |
| Outputs | Fresh project-local `.cache` directory, SDK/callback/event logs, exact raw reads, native-history before/after metadata and closed/failed receipts |
| Expected comparison | Complete Boot hash `a63346db0dc673dc42adf6064892c466af5c4571df53cb55fe5b6ea154c1fdf4`; never compare a compact BIN padded with FF |
| Mutations excluded | No deliberate target writes/reset/halt/resume, no firmware or EEPROM/NOR operation, no power command; attach itself is not assumed bus-level read-only |
| Decision | Reconcile actual SDK writes and reset/halt/identity changes before any dependent operation. Unknown values/format or failed close do not qualify RAM entry; retain current firmware and power |

The user subsequently answered "allowed" to the exact filesystem question:
native J-Link history/config updates under `C:\Users\SU\AppData\Roaming\SEGGER\`,
primarily `JLinkDLL.ini`, are authorized for this operation. No cleanup of existing
files is authorized; controllable logs/readbacks remain project-contained.

Execution preparation after that approval: `p34_probe_acquire.py` and
`recovery_entry/native_probe.py` bind only the verified V8.18 observation API
signatures. Every native call is limited to five seconds in an owned Windows
job; the whole worker is limited to 45 seconds. Termination/reaping may add up
to 15 seconds in the parent, without extending the worker's device access.
The inherited job helper is reused from `Tools/flutter/dev_checks.py`; no WMI,
PowerShell, detached process or independent device service is needed.
`.cache/p34-native-probe-test1` passes 23 host tests, including a real owned
worker exiting normally and a deliberately stalled callback killed at its
native-call bound. No J-Link was loaded by these host tests.

The approved finite cell now starts with `.cache/p34-native-settings1`: load the
hash-bound DLL and validate the fixed settings without probe selection/OpenEx.
Only after this succeeds, use `.cache/p34-native-acquire1` for the already planned
observation. Parent/worker receipts bind sources, native history before/after,
settings and original byte logs. A failed settings phase is not a failed device
connection. Neither phase grants target writes, resets or RAM execution.

Before the first actual attach, the settings-only phase discriminated V8.18
return semantics. `native-settings1` stopped before OpenEx at RestartOnClose's
return value 1. `native-settings2` repeated the same intended settings without
opening a probe: RestartOnClose=0 returned [1,0], InhibitConnectRetries=1 [0,1],
and SetEnableMemCache=0 [1,0]; all other selected commands returned [0,0] with
empty error text. The policy now checks the second response against the exact
desired value, not generic success. These original responses and DLL hash are
test inputs. Selected `p34-native-probe-test3` passes 24 tests and
`p34-native-settings3` reports NATIVE_SETTINGS_PASS_NO_PROBE_OPEN. The initial
failure and source snapshots are retained; the planned first actual observation
remains `.cache/p34-native-acquire1`, with no device retry consumed by settings.

### 19.6 First Current Observation And DAP Discriminator

Actual `.cache/p34-native-acquire1` completed in a 3.85-second owned worker with
native close returned and no timeout or competing debugger afterward. The full
65536-byte Boot hash matches the exact original hash in section 19.5. Both core
samples show CPUID 0x410FC241, App VTOR 0x08010000, running CPU, no observed reset
sticky flag, DWT_CTRL 0x40000001, DEMCR 0x01000000, CPACR 0x00f00000 and FPCCR
0xc0000018. DWT count advanced from 0x94e82696 to 0xbe3e3ec7. These are sampled
states, not proof that no transient reset/halt occurred at any other instant.

The explicit ForceAttach/no-RAM-init configuration did NOT remove the SDK's five
internal CPU_WriteMem calls: DHCSR, DEMCR, DWT_CTRL and CPACR twice. The verbose
log includes payloads for public ReadMemEx but not these internal writes. Thus
their values remain unknown; no write-audit or transient-state proof is promoted.
Native history/config hashes were unchanged in this observation. No intentional
target memory write, halt, reset, power command or firmware operation was sent.

Next finite discriminator, `.cache/p34-native-dap1`: use the same 45s/5s owned
limits and power/authority boundary, but bypass JLINKARM_Connect entirely.
Public pylink and pyOCD source references retained in
`.cache/p34-native-reference2` show CoreSight Configure plus direct AP/DP access
without a high-level CPU connection. References are input bytes, not executed
packages. `dap_probe.py` permits only DP SELECT writes (AP0 bank F/0) and AP TAR
writes (fixed core-register/16-byte Boot-vector read addresses and restoring the
observed original TAR). No AP data-register, CSW, DP power request, sticky-error
clear, target memory or reset write is allowed. DP power must already be ready,
IDR/CSW must match the admitted port and existing word-read mode. A failure stops;
it does not automatically repair or retry the port. DP SELECT is host debug-port
state and is not claimed restored to an unreadable previous value.

Read two fixed core samples and the 16-byte Boot-vector prefix only, compare that
prefix with the just-captured full Boot, restore/verify AP TAR, and close. This
is a different connection route justified by the five unobservable writes, not
a repeated OTA or a blind repeat of the same attach. `.cache/p34-native-probe-test4`
passes 28 host tests including forbidden AP data writes, no power/CSW repair and
close after TAR-restore failure. `.cache/p34-native-settings4` passes the bound
native settings check without opening a probe. If this route also writes CPU
state or cannot establish its port prerequisites, retain the failure and stop
dependent mutations; actual BCB capture and RAM execution remain unqualified.

DAP1 result: no high-level CPU connection, no CPU_WriteMem, normal native close;
DPIDR matches 0x2ba01477, but DP CTRL/STAT is 0x00000040, so the already-powered
debug-port prerequisite rejected before AP selection or memory reads. This is
not loss of the board's physical 3.3V supply. The debug access domain was not
requested on. No target-state repair or same-input retry followed.

Bounded successor DAP2 (same fixed reads/deadlines, `.cache/p34-native-dap2`):
explicitly permit the standard DP system/debug access requests at bits 30/28
for the observed idle CTRL/STAT, without the debug-reset request bit 26 or any
sticky-error clear. The pyOCD DAP reference identifies these bits and the proper
close order: deassert the system request, wait for its ACK to drop, then deassert
debug and wait again. Each handshake is capped at 32 reads inside the existing
worker deadline. This is debug-port access setup, NOT the J-Link target-power
command excluded by the direct-3.3V supply premise.

AP CSW may change only its transfer-size/increment fields to word/no-increment,
with exact readback; no active/disabled AHB port may be reconfigured. Preserve
and verify CSW/TAR restoration before dropping debug access requests. AP data
register writes remain prohibited. A detected host test failure in test5 showed
that an invalid active CSW must not be registered for cleanup; the source was
fixed, and selected test6 passes all 30 tests. The failed test/source remains
preserved. Native-settings5 passes the new source-bound settings preflight.
DP power/CSW setup here supersedes the intentionally narrower DAP1 prerequisite,
not its historical failed result or the ban on physical power/reset/data writes.

DAP2 executed successfully in 1.40 seconds. Core samples show running CPU and
advancing DWT, with the same named debug configuration as acquire1. The 16-byte
Boot prefix matches. No CPU_WriteMem appears; JLINKARM_Connect is not called.
TAR, CSW and debug/system access requests are restored and verified; native
close returned, no worker timeout, unchanged native history metadata. This is
evidence for the new read route, not retrospective proof for acquire1's five
unknown-value writes, and not a complete proof of all target transients.

Next `.cache/p34-native-state1` is one DAP connection with two fixed passive
register/header passes. `state_probe.py` binds the vendor-defined CRM clocks,
debug pause bits, watchdog configuration (excluding command register), GPIOB/D
configuration/levels, all DMA/EDMA channel controls, QSPI control/status (excluding
data FIFO/command stores), SDIO control/status (excluding FIFO/interrupt clear),
and the 96-byte App header. No write capability is added. Each pass is explicitly
non-atomic and cannot establish DMA quiescence, EEPROM ownership, WDT running
state or a complete App hash. Header CRC/version is corroboration only. The
vendor headers are source-bound inputs. Selected native-probe-test7 passes 32
tests; native-settings6 validates the current fixed settings without OpenEx.

State1 completed in 1.75 seconds, with the same successful DAP restoration and
no CPU_WriteMem. Both App-header CRCs pass and report 30275, length 617588.
Both passes show WDT DIV=5/RLD=3124/WIN=4095, no DEBUG pause bits, enabled DMA1
channel 3 and DMA2 channel 4, QSPI DMA disabled, sampled SDIO data-control/status
zero, and PD2 high. PB6/PB7 are sampled released/high but their App pull/drive
configuration does not match the original-Boot BCB adapter. These facts reject
direct use of the App context as an already-owned recovery entry. Do not infer
that a halt freezes WDT or DMA, or reconfigure the pins merely to satisfy a mask.

Next image1 is a single passive DAP read of exactly 617588 current App bytes,
compared with the previously bound 30275 raw hash
`4d248fd7e3f6db9d08afdc3712f383064779a3b732ae3b7d550a4f2c393114f6`.
It uses AP word auto-increment, <=1024-byte bursts which never cross the AP's
1KiB increment boundary, no AP data writes, and original CSW/TAR/request restore.
The longer read gets a declared 540s observation / 600s worker deadline; every
native burst remains capped at five seconds. This extends passive observation
time, not a timeout for a running writer or a target mutation allowance. Original
App bytes and per-chunk progress are retained in `.cache/p34-native-image1`.
Selected native-probe-test8 passes 33 tests, and native-settings7 passes the
source-bound settings preflight. No source-pinned helper will change while running.

### 19.7 Current Evidence And Independent Entry Decision

Image1 completed in 130.29 seconds with DAP_FULL_APP_MATCH: all 617588 bytes match
the exact 30275 raw image, not merely its header or version string. The acquired
bytes also match the map-bearing `.cache/p34-sha-candidate/b/app-gcc` BIN outside
the finalized header [0x400,0x460), so that build's map can locate subsequent
passive App-state observations. No halt/reset/power/firmware operation was issued.
Native close and TAR/CSW/DP restoration succeeded; no CPU_WriteMem is present.

`.cache/p34-native-audit1/result.json` rechecks 563 generated files and source
bindings, the three successful DAP API-write traces, complete App identity and
map-bearing build equivalence. Four mutation tests reject CPU memory writes,
unknown SDK write APIs, AP data-register writes and the DP debug-reset request
bit. It reports logged API writes within the specific read profile, not a proof
of all electrical transients or retrospective success for old high-level SDK
writes. Selected host test8 remains 33 PASS. All selected local outputs are under
the project root; SEGGER history/config metadata remained unchanged throughout
the authorized native sessions. No external cleanup, commit, push or release.

Review decision ENTRY-20, owner: Codex root, pending independent responder:

- Decide the smallest admissible control-transfer route to original-Boot
  holdpoint 0x0800199c, before QSPI initialization/BCB arbitration, for the separate
  bounded BCB reader. This asks for technical findings and missing evidence, not
  permission to provision NOR or rewrite BCB.
- New facts are exact Boot/App identities, user-confirmed direct 3.3V supply,
  DAP-only observation with scoped/restored debug-port state, unpaused watchdog
  configuration, enabled display DMA1/3 and SDIO DMA2/4, and App EEPROM pin
  configuration differing from the original Boot's adapter. Enabled DMA is not
  proof a transfer was active; two sampled idle SDIO values are not quiescence.
- Preferred next direction is a qualified original-Boot entry, not silently
  relaxing the BCB adapter to run in the existing App context. Before any reset
  or halt, establish the smallest remaining current OTA/NOR/SD disposition and
  watchdog-mode facts from the exact App/Boot source/map and passive observation.
  Do not assume a current BCB RAM mirror is an actual EEPROM read, that watchdog
  stops on halt, or that ordinary reset clears all debug freeze configuration.
- Review should name the necessary observation/repair, preserved invariants,
  fail-closed exit and verification oracle. Original App/Boot/candidate/backup
  and EEPROM must remain unchanged; no successful OTA is to be repeated and
  no invalid recovery content is to be legitimized by recomputing checksums.

The cc-connect relay discovery was attempted with contained CLI home/temp/log
outputs after inspecting its local command implementation. It returned "no
binding for this chat" before contacting another agent, retained in
`.cache/p34-entry-review1/discover.log`. No binding, session key or agent target
was invented; the daemon was not restarted or reconfigured. Root has asked the
user to allow a read-only independent review sub-agent. That request is pending;
no sub-agent or independent acceptance has been started. Physical BCB acquisition,
RAM execution and NOR provisioning remain NOT_EXECUTED, not silently passed.

### 20. ENTRY-20 Independent Review And Passive Follow-Up

The user explicitly authorized one read-only independent review sub-agent.
`entry20_review` returned DECIDED: prefer the unchanged original-Boot system-reset
route, not an interrupted-App RAM takeover. Four required evidence/fix areas:
bind a media-safe stopped App rendezvous before reset; establish watchdog state
through loading/run/failure; let Boot's required SysTick initialization run before
masking IRQs at the verified holdpoint; and independently qualify the post-Boot
STOP/settlement, actual BCB capture and retained-state exit. This is technical
review, not formal acceptance or permission to bypass those gates.

In particular, WDT pause applies only to an actually halted core, not the RAM
terminal spin. No remaining watchdog budget can be inferred from its divider
and reload registers. The preferred discriminator is hardware auto-start option
versus software-start WDT and the chosen reset domain. Also, do not assume an
FPB v1 Flash comparator can trap the RAM terminal address. The reviewer is now
checking the candidate scheduling rendezvous at the exact App WFI 0x08045a78.

The read-only review accidentally created an empty project-root file named
`media_qualified` through cmd redirection. The reviewer disclosed it immediately
and did not clean it. Root verified its size was zero and removed only that
project-local artifact with apply_patch. No product source or external file was
changed by the reviewer; no device operation occurred in the review.

Next passive cell `.cache/p34-native-entry-facts1`: two DAP state passes with
the existing no-target-write profile. Add only the FLASH USD latch, first USD
word (FAP/SSB) and EOPB0 word (not QSPI keys); FPB control/six comparators; DMA
counts/endpoints; and exact image/map-bound BLE state/ISR/epoch, overlay-owner
and confirmation-mirror words. The accessor instructions directly bind session
state offset 0xcc and ISR offset 0x1ac in the 0x240-byte session at 0x20052988.
Mirrors remain corroboration, never actual EEPROM BCB or a media-safe-reset grant.
Option complement/latch agreement is required even for reporting software-start
selection. Tests bind the actual WFI/accessor bytes and negative option cases.
Selected native-probe-test9 passes 35 tests. No halt, reset, EEPROM/Flash option
write or hardware breakpoint installation is included in this cell.

#### 20.1 Actual Facts1 And Corrected Manual Interpretation

`.cache/p34-native-entry-facts1/worker.json` completed two passive DAP passes,
normal close and port restoration, with no CPU_WriteMem. BLE state/ISR/overlay
were zero, epoch 2, confirmation mirror state 4/done 1. These are RAM mirrors,
not actual EEPROM BCB. FP_CTRL was 0x261 with six zero comparators. Watchdog
DIV/RLD/WIN were 5/3124/4095 with debug pause disabled; these do not reveal its
remaining time. Display DMA1/3 count changed from 0x12ff to zero. DMA2/4 had
peripheral address 0x50061080 and zero count, identifying the actual SDIO2 FIFO.
The earlier unused SDIO1 samples are explicitly not card-idle evidence.

FLASH_USD was 0x03fffffc and FAP/SSB word 0xffff5aa5. RM v2.07 p89 explicitly
accepts erased FF/FF option pairs; p103 defines the latched nWDT_ATO_EN bit.
The first facts1 decoder incorrectly rejected this documented special case.
Preserve that original receipt; the corrected interpretation is a valid,
latch-consistent software-start selection, not proof that WDT is now stopped.
The correction and actual SDIO2/PC0-DAT0 mapping pass 36 host tests in
`.cache/p34-native-probe-test10`; they have not yet been used for a new capture.

Finite successor cell: consolidate the reviewer's exact Recorder/file/cache RAM
mapping with fixed SDIO2 command/response/data/status and SD-ready/DAT0 reads;
run a fresh source-bound host test batch, native settings without probe open,
then two passive passes in `.cache/p34-native-entry-facts2`. Root remains the
sole hardware operator, outputs stay under the project, and only the previously
authorized SEGGER native history boundary is allowed externally. The existing
45-second owned worker/5-second native-call bounds and normal close apply.
No arbitrary RAM traversal, media commands, halt/reset, breakpoint, WDT pause,
EEPROM/NOR/Flash write or new OTA is authorized by this observation cell.

The WFI review also establishes that PAUSE leaves the Recorder file open;
CMD12 completion is not a later card-ready observation, and SdioCard::isBusy
returns false on CMD13 failure, so syncBlocks must not be used as a fail-closed
readiness oracle. A stopped WFI is a scheduling boundary, not automatically a
successful NOR/SD/filesystem disposition. Any later control adapter must qualify
those conditions before reset and preserve a safe failure/retention path.

#### 20.2 Executed Filesystem/SDIO2 Observation

ENTRY-20-FS independently bound Recorder base 0x20051c14/size 0x78 and its
file/driver/cache/active fields at 0x20051c78/7c/80/84. Instructions at
0x0803197e and 0x080318ec use offsets 0x64 and 0x70. SD/FatVolume is
0x20052de0; data-cache header is +0x24 and separate FAT-cache header +0x230.
Each cache header contains status byte +0, owner pointer +4 and LBN +8.
FatCache::sync at 0x080137b6 tests dirty bit 0; bit 1 is mirroring, not dirty.
Unknown status bits must not be treated as clean. Cache owner must match SD.

`.cache/p34-native-probe-test11` passes 38 host tests, including bound cache
instructions and paused/open Recorder distinctions. Native settings9 passed
without probe open. The finite facts2 cell completed in 2.05 seconds with normal
close, restored TAR/CSW/DP and no CPU_WriteMem. Both samples show:

- Recorder active/file/driver/cache zero; data/FAT cache status zero, both owners
  0x20052de0. Data LBN 15219, FAT LBN 0xffffffff. No dynamic pointer read needed.
- SD-ready 1, DAT0 high, CMD 0x44d/RSPCMD 13/RSP1 0x900, STS/DTCNT zero,
  DMA2/4 count zero, and last_error/transfer_error/stop_flag zero. This is an
  observed CMD13 TRAN/READY_FOR_DATA response, not merely a CMD12 completion.
- BLE idle/ISR inactive/overlay free, epoch 2; BCB mirrors remain 4/done 1.
  Software-start watchdog option is valid and latch-consistent. Core kept
  running at App VTOR with advancing DWT and no sampled reset-sticky flag.

Null Recorder pointers do not prove prior close succeeded: the adapter deletes
the file and LVGL clears the pointers even after close failure. Clean shared
caches do not exclude other writers or establish historical filesystem integrity.
The current observation narrows the reset prerequisites but authorizes no reset.

Next host-only control policy is `recovery_entry/rendezvous.py`: exact WFI
0x08045a78 only, verified watchdog halt pause before installing a verified FPB
comparator, stopped Thread/privilege/Thumb/context checks, two stopped media
observations, no reset/resume/RAM execution methods. Failures retain state for
reconciliation; no automatic recovery mutation. Ten model tests pass in
`.cache/p34-entry-rendezvous-test1`. It has no real hardware transport yet and
has not paused the device. ENTRY-20-CONTROL review is checking remaining NOR
and non-Recorder writer ownership before connecting an adapter.

#### 20.3 Reviewed Halt-Only Matrix

ENTRY-20-CONTROL independently permits a halt-and-observe cell, not reset.
WFI excludes the local StorageService::SaveFile call, but USB MSC can write SD
outside FatCache and SD-file FirmwareUpdate can span loop iterations. NOR
settlement also remains separate. These are reset gates, not reasons to replace
the unchanged running App or perform blind media repairs.

The new `control_probe.py` adapter is separate from the unchanged read-only DAP
transport. Its only AP data writes are DEBUG_APB1_PAUSE WDT bit 12 preserving
other bits; FP_COMP0 value 0x48045a79 (lower-halfword Flash WFI) and zero for
owned removal; and DCRSR selectors 15/16/17/20 with REGWnR clear to read core
registers. There are no DHCSR, AIRCR, DCRDR, PC/MSP, firmware or RAM writes.
It checks live exact header/WFI bytes, CPU/VTOR, unused FPB v1 comparators,
initial debug control and inactive WWDT. CONTROL.FPCA may be set during this
observation-only halt; privilege/MSP must still match. No FPU state is changed.

Review fixes: reject/reset-latch the first halted sample rather than losing
DHCSR S_RESET_ST; reject late final observations; and preserve logical debug
requests during retained reconnect even if it fails before any selector write.
The latter policy is established before connect, independent of current-session
mutations. Close still runs after failed retention checks. Fresh source-bound
`.cache/p34-entry-control-test3` passes 22 mocked adapter/policy tests, including
real mocked close/new-DAP-open/observe/close and early-mismatch paths.

Finite cells, root sole operator, current user P3-4 continuation authority:

1. `.cache/p34-entry-wfi1`: set/read back WDT halt pause, install/read back the
   fixed WFI comparator, observe exact halted Thread context, remove/read back
   only that comparator, then take two stopped media/USB observations. Retain
   the unchanged App halted, WDT pause and logical DP requests. No resume/reset.
2. Only after a successful normally closed predecessor, reconnect once in
   `.cache/p34-entry-wfi-retained1`; verify halt/context/pause/comparator and
   observe media again, retaining state without any new pause/comparator write.
   Only read-selector writes are allowed. A failed cell is reconciled, not replayed.

Each owned worker is bounded to 45 seconds, each native call to 5 seconds;
rendezvous acquisition is 15 seconds. The project-local output/source/cache
paths were preflighted. Only the existing explicit SEGGER history/config
boundary is allowed outside the project, with before/after hashes and no cleanup.
The J-Link physical 3.3V/GND supply stays connected. Logical DP system/debug
requests are deliberately retained, not misreported as restored. Physical
close/reopen retention remains an observation to obtain, not a model-test claim.

#### 20.4 Executed WFI Stop And Reconnect

Both planned cells executed and closed normally. `p34-entry-wfi1` stopped at
0x08045a78 and removed its comparator. `p34-entry-wfi-retained1` reconnected
about 60 seconds later and observed the same retained context: xPSR 0x21000000,
MSP 0x20057fa0, CONTROL 4, PRIMASK/BASEPRI/FAULTMASK zero, VTOR 0x08010000,
FPCCR 0xc0000018, no observed reset/lockup. WDT halt-pause is 0x1000; WWDT
control zero. DP logical requests were deliberately retained; TAR/CSW restored.
Native SEGGER history hashes stayed unchanged and no debugger worker remains.

Stopped SDIO2/Recorder/cache observations still have the facts2 values, with
display and SD DMA counts zero. USB connection word is 0x104: current SUSPENDED
(4), prior DEFAULT (1), not proof of an active configured host. MSC BOT word is
zero. No MCU reset, CPU-register value change, RAM/EEPROM/NOR/Flash write or OTA
occurred. The App is now intentionally halted; do not describe it as running.

ENTRY-20-UPDATER identifies the PageManager pool at 0x2004f524/528/52c and the
FirmwareUpdate object by vptr 0x080a0b10 plus manager/name identity. A bounded
successor read can exclude its pending/timer/file/phase state without invoking
App code. ENTRY-20-NOR conditionally supports a separate host-driven controller
status reader from this unchanged halted context, not RAM code execution.

Before that reader is executable: bind live XIP profile and all possible bus
masters; qualify command serial clock; test ordered CMD words and software-once
05/35 status reads, current JEDEC ID, stale/partial/ambiguous commands and exact
configuration restoration. CTRL bits 18:16 select a NOR status bit, not QSPI
activity; true XIPIDLE is bit 7. Switching XIPSEL automatically flushes/aborts
the controller, requiring idle and no masters first. Never issue NOR reset,
WREN, program/erase, resume/suspend, or replay saved CMD_W3 on restoration.

Next finite read cell `.cache/p34-entry-owner1` uses `p34_halted_probe.py`:
revalidate retained context, inspect the nine-entry PageManager pool twice with
RAM bounds and unique vptr/manager/name identity, capture pending/timer/file/phase
and bounded error text, and read QSPI command/configuration words without reading
FIFO data or keys. It does not change controller configuration or issue NOR
commands. Nine host tests pass in `p34-entry-owner-test2`, including a full worker
with mocked native boundary and the exact live-image instruction/name anchors.
The established 45-second worker and 5-second native-call bounds, explicit history
authority and retained-close behavior apply. Any pointer/profile mismatch is
retained as a failed observation, not permission to invoke App code.

#### 20.5 Smaller Direct EEPROM Read Route

`p34-entry-owner1` executed successfully: both nine-page traversals identified
the same FirmwareUpdate object, phase/file/pending/timer/mode zero and empty
error text. QSPI configuration was read, not changed: XIP 0x6b/1-1-4 and idle.
This still does not establish NOR settlement. The NOR status observer is now
deferred: independent ENTRY-20-BCB-DIRECT review accepts a smaller EEPROM-only
host path from the verified WFI halt, avoiding NOR changes and MCU reset just
to obtain BCB. The original RAM reader and its Boot-only gates remain unchanged.

Retention precision: pre-close DP requests were high, but subsequent
post-CORESIGHT_Configure observations start at 0x40. Logical request retention
across close is not proved, and the hidden clearing phase is unknown. Physical
halt/context/WDT-pause retention was directly re-observed; every new connection
must revalidate it. Do not equate the adapter's deferred restore with SDK-wide
logical power retention or physical supply switching.

The direct reader preserves App PB6/PB7 output/open-drain configuration rather
than forcing Boot pull/drive settings. `p34_host_bcb.py` compiles the unchanged
fixed `ram_recovery/bcb_reader.c` plus the existing BCB arbiter into a contained
host DLL. `host_bcb.py` provides bounded native GPIO callbacks, not an arbitrary
I2C payload API. It verifies the physical START/repeated-START/STOP transitions
and every master-transmitted A0/pointer/A1 bit, including R/W, against the fixed
605-rising-clock-per-record sequence. A missed repeated START must not allow A1
to become EEPROM payload. Slave data/ACK ownership is handled separately.

Review fixes also latch BaseException at the ctypes callback boundary, check
the deadline after C arbitration and leave pointer-change status unknown on
failure. Lost halt, bad physical/latch level, NACK, uncertain GPIO store or
timeout suppresses all subsequent pin callbacks, including C cleanup STOP.
No blind bus recovery, reset or replay follows. Successful completion requires
released/high lines, unchanged GPIO configuration and unchanged halted context.

Fresh `.cache/p34-host-bcb-test2` has 12 passing tests and zero compiler
warnings/errors. The independent reviewer compared the current implementation,
runner and tests byte-for-byte to those snapshots. Coverage includes the full
mocked native worker, all twelve transmitted-byte ACK failures, missed repeated
START/RW-bit failures, final NACK, uncertain delivered stores, timeout, callback
BaseException, changed pairs, both-invalid pairs, sequence wrap and ties.

Finite cell `.cache/p34-host-bcb1`: root alone revalidates the retained context,
GPIO/DMA ownership, then waits at least 5 ms after a conservative possible STOP
bound. Keep one native connection through exactly A/B/A/B (64 bytes each), final
bus/context verification and close. Maximum capture 300 seconds, worker 360,
native call 5 seconds; slow host clocking is permitted by the supplied part's
minimum timing requirements, not claimed as electrical rise/fall qualification.
Output DLL/log/raw/snapshot/cache paths are project-local and preflighted; the
existing exact SEGGER history/config authorization remains the only external
write boundary. Supply stays connected. No EEPROM payload write, GPIO
configuration change, NOR operation, reset, RAM execution or firmware update.
Raw invalid records remain invalid; capture success and BCB admission differ.

#### 20.6 Actual BCB And Entry Audit

`.cache/p34-host-bcb1` completed the one planned acquisition in 98.357 seconds
(owned worker 100.645 seconds), with normal close, 5748 verified GPIO stores,
2060 SDA samples and no callback fault. Both A/B passes are byte-identical and
both records pass magic/schema/CRC checks. B is selected by the original arbiter:

- B: CONFIRMED, seq 12849, boot_try/copy_phase/resume_block zero; current and
  candidate version 30275; candidate address 0x1000, length 617588, full CRC
  0xdd24b91f; backup metadata version 30274, length 617588, CRC 0xdd24b91f.
- A: historical TEST_BOOT, seq 12848, boot_try 2, current version 30274. It is
  not the active pending state. Padding is FF and reserved word zero in both.
- First-pair SHA-256 is
  72b8eb65d7a99b3c0a085b225dde0b6d7d680015b874366a97f1c36cbb89e049.
  The original 256-byte acquisition is preserved as `capture-raw.bin`, not
  synthesized from the RAM mirror.

Independent ENTRY-20-BCB-STATE read the raw file, recalculated each CRC and
signed-16 sequence arbitration, and compared the selected candidate metadata
with the saved complete current App. Its full-file CRC is indeed 0xdd24b91f.
This closes the unknown real-BCB confirmed/non-copying baseline at this capture
epoch. Backup/recovery physical validity and future takeover/restore/exit are
not implied. Reconnect requires new execution-epoch ownership/settlement and
BCB equivalence checks, not reuse of the capture's execution eligibility.

The successful read ended with PB6/PB7 released/high, unchanged GPIO
configuration, unchanged halted WFI context and WDT halt pause. No EEPROM
payload, NOR, RAM image or firmware was written; no MCU reset or App resume.
The EEPROM's internal address pointer was used by the read sequence.

`.cache/p34-entry-audit2/result.json` audits 1229 files across the selected
preparations/captures and their frozen source snapshots. It reconciles actual
SDK AP data writes against the journal's exact pause/comparator/core-selector
and GPIO capabilities, rejects three unsafe trace mutants, and independently
reconstructs all 256 BCB bytes from logged physical SDA observations. The wire
trace has 2420 rising clocks, eight STARTs and four STOPs, with the fixed address,
pointer and ACK/NACK pattern. It also verifies current selected test bindings
(38 native, 22 control, 9 owner, 12 BCB methods) and BCB/current-App consistency.
This does not rehabilitate historical high-level SDK writes or certify analog
waveforms. All selected output paths are project-contained; authorized SEGGER
history/config hashes remain unchanged. No external cleanup, commit, push or
release occurred, and no owned hardware worker remains running.

Next destructive operation, if approved and technically qualified, is confined
to rebuilding the optional recovery slot with the already source-admitted
30276 R2-A image. Current proposal erases only header/payload sectors
[0x200000,0x299000), programs its 619580-byte payload at 0x201000 and commits
the 32-byte slot header marker-last; [0x299000,0x300000) remains untouched.
Original Boot/internal App, EEPROM BCB, candidate, backup and staging must stay
unchanged. Section 1 remains explicit that this design is not NOR-write
authorization. Root must obtain the exact new destructive scope and finish the
remaining physical NOR/ownership/restoration qualification before executing it.

### 21. Authorized Recovery-Only Successor

The user's subsequent explicit approval authorizes rebuilding NOR
[0x200000,0x299000) with version 30276 / 3.2.76-r2a, using the pinned
619580-byte `.cache/p34-recovery-sources1/r2-a.bin` (full SHA-256
7445ef63d5f4cbef95761f27075333d7d09c9d43585a28b84e6575ccfb274fcf).
It does not remove technical gates or authorize Boot/App/BCB/candidate/backup/
staging changes. Preserve [0x299000,0x300000). Root is the sole physical-link
operator; writable root remains D:/github/my/E-Track. Existing authorization
for native SEGGER history/config updates under the exact Roaming/SEGGER
directory remains applicable; no external cleanup, commit, push or release.

Preferred smaller route: keep the unchanged 30275 App halted at its verified
WFI with WDT halt-pause, and drive QSPI through a separate host adapter.
Do not qualify or alter the rejected/unqualified RAM-entry route by assumption.
The original full Boot/App captures and actual A/B/A/B capture in section 20
remain comparison inputs, not fresh execution-epoch qualification.

Finite successor cells, performed serially after bound host tests and review:

1. `NOR-21-STATUS`: one retained-context/master/clock requalification,
   conservative /12 command-clock switch, fresh 05/35 status and exact 9F
   identity reads, then verified XIP/config restoration. No WREN, erase,
   program, NOR reset, suspend/resume, unlock or status-register writes.
   Native calls have a five-second bound; worker limit 90 seconds. A failure
   latches all further controller writes and retains actual halt/config state.
2. `NOR-21-PREPARE`: test a host DLL using the unchanged portable transaction
   core and bound Boot admission sources; enforce the narrower authorized
   range in callbacks. Complete physical-part/protection, FIFO, stale-complete,
   ambiguous-command, deadline, marker-last and restoration negative tests.
3. `NOR-21-REBUILD`: only after the first two cells qualify, one same-connection
   actual BCB-equivalence/owner/settlement requalification, full preservation of
   original affected recovery bytes and protected-state evidence, recovery-only
   transaction, physical full-payload/header/Boot-admission verification, and
   unchanged protected regions/BCB checks. Define measured finite worker/IO
   budgets before this cell; do not start an open-ended writer.

Do not replay saved CMD_W3 when restoring configuration: it is a command
trigger, not passive state. CTRL bits 18:16 select the status busy-bit index,
not controller activity. XIPSEL transitions require idle/no other masters and
bounded automatic abort completion. A fresh identity plus WIP/SUS/protection
assessment is required; historical JEDEC is not write authorization. Keep
J-Link's physical 3.3V supply connected throughout. No automatic MCU reset or
resume follows either success or failure; a separate unchanged-App resume
qualification is required. No new P3-4 performance measurement is claimed.

#### 21.1 Status Adapter And Host Transaction Preparation

The first status adapter test receipt, `.cache/p34-host-nor-test1`, has 16
passing methods. Independent NOR-21-STATUS review reproduced two native-boundary
gaps: failed byte-FIFO access could leave AP CSW in byte/no-increment format,
and checking DP sticky errors only after all three bytes could overconsume FIFO
after an earlier bus error. Neither issue was exercised on hardware.

The fixes keep the old read-only DAP adapter unchanged. The new Port owns its
temporary AP CSW and an AP-register-only close step; no QSPI command/config or
FIFO accesses occur in failure cleanup. Sticky DP errors are not repaired and
make restoration explicitly uncertain. Each consuming byte read now checks DP
status before the next byte. `.cache/p34-host-nor-test2` has 18 passing methods,
including every native FIFO-substep negative return/BaseException and sticky
errors after byte one/two. The original test1 receipt is preserved.

Master exclusion binds all F435 AHB masters: retained halted M4, disabled EDMA
streams, and DMA1/3 plus DMA2/4 with exact controls 0x1093/0x2a81, zero counts
and disjoint peripheral/RAM endpoints. F435 has no EMAC. USB/DVP/SDIO are bus
slaves; do not invent an additional USB AHB-master traversal. The actual media
and updater owner samples and the full App header must be freshly consistent.

`.cache/p34-host-writer-test1` separately compiles unchanged `writer.c` with
bound Boot header/CRC/SHA sources and a host-only stack wrapper into `writer.dll`.
Nine host test methods pass, with zero compiler warnings/errors. Its callback
boundary rejects writes outside [0x200000,0x299000), page crossing and combined
metadata/marker writes before reaching the port. Callback exceptions/deadlines
latch failure. The final modeled slot is byte-identical to the earlier C-core
cross-check slot; the unchanged original Boot recovery validator accepts it as
30276 (4845 read callbacks). This is memory-model evidence, not physical NOR
admission or permission to execute a writer. No hardware writer entry exists yet.

#### 21.2 Physical Status Result And Finite Read Qualification

`NOR-21-STATUS` executed in `.cache/p34-host-nor-status1` with normal close
and a 4.984-second owned worker lifetime. Both fresh samples were JEDEC EF4018,
SR1=00, SR2=02. Original clock/XIP/passive configuration, WFI context, WDT
pause and owners were verified after the operation. No NOR payload write,
WREN, reset or App resume occurred. Authorized SEGGER history hashes remained
unchanged and no debugger process remained. FIFO 3 -> 1 is expected operational
flush/consumption, not passive configuration drift.

Independent review reconstructed the native trace: exactly 46 target writes
(12 core-read selectors, four CTRL writes, 24 ordered command words and six
completed-command acknowledgements), six byte/no-increment FIFO reads and
restored AP CSW/TAR. No high-level CPU_WriteMem call occurred. This establishes
the halted-host status/restoration route, not an exact Winbond suffix or writer
qualification.

Add one finite non-mutating `NOR-21-READ` cell: SFDP [0,256) as two 128-byte
5Ah commands, a 4096-byte 03h candidate prefix at 0x1000, and 128-byte reads
at recovery 0x200000 and preserved boundary 0x299000. Compare candidate bytes
with the complete original App capture; preserve all raw bytes regardless of
whether SFDP is supported. Read-only bounds are 36 data commands, six status/
identity commands, 60-second adapter, 80-second observation and 90-second owned
worker. It adds no erase/program/WREN opcode. `.cache/p34-host-nor-read-test1`
contains seven passing methods including all native FIFO burst substeps and
sticky errors after each of 32 words. Pending independent implementation review
precedes physical use.

SFDP can qualify a compatible three-byte/read/page/erase command profile, not
prove BV/FV/JV suffix or live individual-block locks. A later scoped writer
must never unlock or write status registers. Unknown protection can fail closed
through WEL checks, complete erased-sector verification and exact page readback;
test ignored protected operations and unchanged WEL before using that route.
Unsupported SFDP is not permission for NOR reset, undocumented status commands
or broader writes. Additional parameter bytes, if needed, get a bounded read
successor rather than a fabricated compatible profile.

#### 21.3 Physical Read Profile And Mapped-Read Cell

`NOR-21-READ` completed in `.cache/p34-host-nor-read1`: 9.768-second worker,
normal close/restoration and an exact 4096-byte candidate/App match. Independent
review reconstructed all four raw files from SDK FIFO values and matched all
226 target writes to the journal. The preserved-boundary 00..7f ramp is real
recorded device data, not a mock inference. The candidate read took 3.602 seconds
(about 1.14 decimal KB/s), so a multi-megabyte transaction requires a measured
longer budget, not the earlier 1800-second model limit.

Physical SFDP SHA-256:
19cbc7362f912e2b0700516740e3d781136c0c9e5ae4a5ef6c32b9832491edd9.
The header and BFPT are revision 1.5, 16 DWORDs at 0x80. Geometry is 16 MiB,
three-byte-only addressing, 256-byte pages and 4 KiB/20h erase. The recorded
maximum 4 KiB erase time is 896 ms and maximum page program is 4224 us; do not
reuse the BV reference's shorter bounds. QER=4 conflicts with the observed 35h
status response. It is retained as a discrepancy, never used to set QE/status.
The common 03/05/06/02/20 profile does not require resolving an exact suffix.

`.cache/p34-nor-profile-reference1` pins Linux v6.12 SFDP source/header and
Zephyr v3.7.0 JESD216 timing decoder by hashes supplied by independent review.
`.cache/p34-nor-profile1` has five passing host tests and the decoded profile;
all 256 single-byte profile mutations are rejected. This remains profile
evidence, not authorization or a completed writer gate.

One finite `NOR-21-MAPPED` cell now qualifies faster preservation reads. Set and
verify XIP_CMD_W3.BYPASSC=1 while command mode is settled, then read in XIP at
/12, with 1024-byte TAR-boundary chunks. Compare candidate4096/recovery128/
boundary128 with the original FIFO captures. Restore BYPASSC=0 in command mode,
then original CTRL and owners/context. CSTS bit3 is read-only operational cache
state and is retained raw but excluded from configurable-bit equality. XIPSEL
automatic ABORT alone is not evidence of cache-data invalidation.

The `.cache/p34-host-nor-mapped-test1` six-test receipt and all six independently
rerun methods pass. Bounds remain 60-second adapter, 80-second observation,
90-second owned worker, five-second native calls. No mapped store/NOR payload
write or automatic resume/reset is allowed. The subsequent finite preservation
scope is full candidate+backup [0,0x200000), tail [0x299000,0x300000), staging
[0x300000,0x500000), plus a separate preimage of [0x200000,0x299000). Archival
availability does not authorize automatically restoring any region. Any later
four-hour writer must audit every nested timer and complete durable preimages,
space checks, current BCB/owner/settlement qualification before its first erase.

#### 21.4 Qualified Mapped Route And Recovery Executor

`NOR-21-MAPPED` completed in `.cache/p34-host-nor-mapped1` with a 6.977-second
owned worker, normal close and all three mapped/FIFO byte comparisons equal.
The mapped 4096-byte candidate read took 0.893 seconds, about 4.59 decimal KB/s.
BYPASSC, original CTRL, owners and exact halted context were restored. No NOR
payload mutation occurred in any of the three qualification cells.

The new `host_nor_device.py` adapter uses that bypassed mapped route for physical
reads, switching to command mode only after all prior commands/reads settle.
Its source-derived action manifest fixes all 2576 mutations and their contents:
153 sector erases, 2421 payload page programs, one 28-byte metadata program and
one four-byte marker program. It checks the exact next action/address/data before
WREN. Its separate Port validates the narrower range again at command emission.
Page writes use at most two 128-byte word/no-increment FIFO fills, with a DP
error check after every word; no status writes, unlocks, block/chip erase,
NOR reset, mapped stores, Boot/App writes or EEPROM payload writes exist.

`p34_host_nor_device.py` defines the one authorized rebuild cell in
`.cache/p34-host-nor-rebuild1`, not yet executed at this note's preparation.
Execution order is retained-context/owner/header verification, actual BCB
comparison, fresh identity/SFDP, durable full preimages, source/preimage binding
and renewed owners, unchanged C core transaction, actual after-images/protected
hashes, unchanged Boot recovery validator, fresh complete original Boot/App
hashes, actual post-BCB comparison, then controller restoration and retained halt.
`Device.finish()` is not called merely because the action list was consumed.
Any failed core, readback, protected-state check or admission bypasses restoration
and retains the actual command/controller state. Native close and AP-only cleanup
still have their own allowance; no retry or guessed old-image restoration follows.

Explicit budgets: owned parent 14400 seconds; distinct long Observation and
controller Gate 13800 seconds; writer callback guard 13200 seconds; each actual
BCB read 300 seconds; each native call/burst five seconds. WIP polling limits
are three seconds for 4 KiB erase and 0.5 seconds for a page, exceeding the
pinned SFDP maxima without claiming calibrated analog timing. Preimage work
must finish before elapsed 6000 seconds, leaving more than two hours for write/
verify/cleanup. Initial evidence reserve is 20 GiB, maintained above 10 GiB.
The historical Observation's 600-second constructor and historical readers'
short windows remain unchanged; the new LongObservation has its own initializer.

`.cache/p34-host-writer-test2` has 11 passing methods, including ignored protected
erase/program and the explicit longer finite callback bound, zero compiler
warnings/errors. `.cache/p34-host-nor-device-test2` has 15 passing methods:
actual C DLL through the controller model; protected erase/program with WEL
retained or cleared; every mutation-command word delivered/error-return;
ambiguous delivered marker; TX faults; long-observation boundaries; and the
complete worker with mocked control/BCB boundary but real C DLL, archives,
original validator and Boot/App hash comparisons. These are development
self-tests, not independent hardware acceptance. Final independent executor
review precedes the first physical erase.

Final NOR-21-DEVICE review found no remaining blocker for this one scoped cell.
All test2 inputs/snapshots and DLL bindings matched; the reviewer independently
reran 14 non-writing integration/fault methods, all PASS, and reviewed the
archive-producing worker case from its original evidence. Root now proceeds
with the recorded `.cache/p34-host-nor-rebuild1` cell under the user's existing
authorization. This is pre-execution review, not a physical success claim.

#### 21.5 Physical Execution And Offline Audit Preparation

The authorized cell is now actually spent: `.cache/p34-host-nor-rebuild1`
started the physical transaction after all durable preimages and actual BCB
equivalence checks. At 2026-10-05T13:30:20Z all 2576 mutations have settled and
the worker is reading back protected staging. This is an in-progress observation,
not completion or permission to replay. The sole worker keeps the original App
halted; do not change its source dependencies, interrupt supply, reset or resume.

`Tools/ota/p34_nor_audit.py` streams the closed SDK log against the exact target
write journal and source-derived action sequence. It compares consumed FIFO,
mapped and internal Flash read bytes, reconstructs archived region hashes and
both GPIO-observed BCB captures, and checks AP/controller/cache restoration.
Its receipt binds every consumed log, plan, worker, frozen source snapshot and
raw archive, with a second hash check after parsing. It must run only after
normal worker closure; live logs cannot be final evidence. Parser failures are
host evidence failures, never grounds for repeating physical provisioning.

The current auditor's `.cache/p34-nor-audit-test4` has four passing host tests,
including the three closed real qualification traces, injected unauthorized
writes, wrong read bytes, command order/range and FIFO format/data failures.
The earlier test2 negative fixture redirected a read rather than a target write;
that failure is preserved. Test3 predates the consumed-input hash binding and
is not current-source qualification.

### 22. RESUME-22: Unchanged-App Resume Plan

This separate finite cell restores normal execution of original App 30275 only
after `RECOVERY_30276_VERIFIED_ORIGINAL_APP_HALTED`, normal native/parent closure,
unchanged Boot/App/BCB/protected NOR, physical Boot admission and a complete
closed SDK/journal audit. Recovery 30276 is not installed as the internal App.
Root remains the sole physical operator under the existing continuation scope;
J-Link supply remains connected. No Boot/App/EEPROM write, reset, PC/SP/RAM
patch, step, host watchdog feed, NOR command or repeated resume is permitted.

The new `recovery_entry/app_resume.py` capability can issue one DHCSR store,
0xe000edf0=0xa05f0001. An uncertain store might already have resumed execution;
only running-safe observations follow, with no retry or automatic re-halt.
Keep WDT halt-pause configured. The App's original watchdog/main-loop path
resumes from its verified WFI without host feed. Logical DP request retention
across native close is not claimed from SDK intent alone.

Entry rechecks exact retained context, all zero FPB comparators, owners, original
vectors and QSPI configuration. The actual halt DHCSR is 0x00030003. Require
normal SysTick CTRL bits=7, LOAD=287999, CURRENT<=LOAD, priority byte=0, vector
15=0x08017a9d; PRIMASK/BASEPRI/FAULTMASK remain zero. Reject active exceptions,
NMI/PendSV and fault/SVC/DebugMon pending hazards, and enabled pending IRQs with
absent/default-loop vectors. Preserve historical sticky fault flags rather than
requiring zero; detect changes using implemented CFSR/HFSR masks after resume.
SysTick COUNTFLAG read-clear is acknowledged, not a pending-interrupt clear.

The runner rechecks `control.context()` immediately before creating the resume
observer, retaining any previously consumed reset-sticky observation. It binds
all audit-consumed input hashes before opening the probe. Running observations
check original App identity, no reset/lockup/new fault, and positive bounded
modulo deltas of millis, main-loop and watchdog-feed counters for 20 seconds.
A fresh final sample also checks progress since the last five-second checkpoint;
progress in the first 15 seconds alone cannot pass. No stopped-only DCRSR/media
operation or RTT ring-pointer write occurs after the resume store.

Bounds: 60-second owned parent, 50-second native observation, five seconds per
native call, fixed 20-second sustained running interval. Eligibility hashing is
performed again by the worker before opening the native probe; actual budget
headroom must remain sufficient. Output is a fresh project-local
`.cache/p34-app-resume1`, with contained host/temp/config paths and the separately
authorized native Roaming/SEGGER history scope. Failure retains original logs
and actual state for reconciliation, not a new reset/resume attempt.

Independent review found and fixed final-window stall acceptance, missing audit
input bindings and loss of Control's reset latch at observer handoff. Current
`.cache/p34-app-resume-test3` has 16 passing host methods, including all three
regressions, uncertain delivered/undelivered stores, counter wrap, failed wake,
fault/reset observation and full mocked native worker. Test1/test2 are preserved
old-source receipts. Final bounded re-review and the still-pending real recovery
audit precede execution. These tests do not establish a hardware resume result
or any new OTA speed measurement.

### 23. NOR-21-AUDIT: Closed Worker And Native Trace Loss

The physical worker closed normally at 2026-10-05T13:39:52Z after 4402.378
seconds. It reports all 2576 settled mutations, exact physical recovery payload,
original Boot admission (`result=0 reads=4845 version=30276`), unchanged complete
Boot/App, protected NOR and actual BCB. Original App 30275 remains halted with
the controller restored. No reset/resume occurred. Native SEGGER history hashes
remained unchanged and no debugger process remained.

The subsequent strict offline SDK audit FAILED. Its immutable diagnosis is
`.cache/p34-nor-audit1/failure.json`: sdk.log has 6514574 lines, with the last
nonblank line 2402388 at relative 683359.808 ms (end byte 110983621), followed
by 4112186 blank lines. This precedes the first actual mutation at 12:47:00Z.
The 29-byte callbacks.log contains no replacement operation trace. The native
DLL contains a maximum-log-size message, but that message is absent here;
the cause of blank output is not established. Do not claim a proved size cap.

Independent review matched all 145 executor inputs to both snapshots and current
sources and reconstructed the complete source-bound host journal and archives.
This is not SDK equality or proof that the missing native interval had no extra
writes. Keep the original audit failure and RESUME-22 gate unchanged. Repeating
the programming or entire read campaign cannot recover missing historical logs.

Finite successor plan, root-owned within existing recovery/observation scope:

1. Offline `p34_nor_reconcile.py`: verify every attempt/return, fixed WREN and
   mutation/TX sequence, observed settlement, archive/BCB bytes, exact closed
   inputs/DLL and original admission. Emit only
   `JOURNAL_ARCHIVES_RECONCILED_SDK_INCOMPLETE`, with historical_sdk_audit_passed
   and resume_authorized both false. Missing return, altered TX/settlement,
   changed archives or sources fail. No device action.
2. `NOR-23-STATUS`: reuse the unchanged, tested `p34_host_nor.py status` in one
   fresh `.cache/p34-host-nor-status2` cell. Exact hn.Status/owners checks,
   05/35/9F only, retained original context and original configuration restored;
   no WREN, erase, program, reset, resume or EEPROM payload writes. Keep existing
   90-second parent/80-second observation/five-second native bounds. Require
   current test2 bindings before execution, then independently audit this new
   closed SDK log with the original strict trace parser. This proves current
   status/context, not missing historical writes.
3. Only after both receipts and independent scoped review, implement a separately
   named resume eligibility route that explicitly preserves the historical SDK
   gap. It may reuse the qualified single-store/running-observer implementation,
   but cannot add a generic bypass to RESUME-22 or emit the old SDK PASS. Its
   plan must bind these exact receipts and original images, carry the residual
   historical visibility limitation and keep the same no-reset/no-replay rules.

All outputs stay under this project; no native history cleanup, Git publication
or firmware performance claim. A failed fresh status or changed retained context
stops dependent actions for reconciliation, not an automatic retry.

#### 23.1 Reconciliation And Fresh Status Results

`.cache/p34-nor-reconcile-test1` has eight passing host tests. Actual
`.cache/p34-nor-reconcile1/result.json` checks 127596 attempt/return pairs,
249220 target writes, 15529 NOR commands, 2576 exact mutations/settlements and
619612 TX bytes. All archived NOR/Boot/App/BCB bytes and inputs match. Independent
review reran the eight tests and added in-memory WEL/WIP/TX/return negatives;
all rejected. The receipt explicitly retains the historical SDK failure and
does not itself authorize resume.

The unchanged `NOR-23-STATUS` cell closed normally at 14:04:28Z in 4.993 seconds.
Both samples were EF4018 / SR1=00 / SR2=02; original context/configuration and
owners were retained. Native history hashes remained unchanged. The original
strict parser fully audited this new SDK log: 46 target writes, six commands,
zero mutations, six matching FIFO bytes. Audit1/2 are preserved host-only
predecessors; audit3 binds the final successor audit-producing source. No status
or programming operation is repeated to regenerate an analysis receipt.

`p34_reconciled_resume.py` is the separate `RESUME-23-RECONCILED` entry. It binds
the exact reconciliation, all consumed original evidence and source/DLL inputs,
fresh status2 SDK audit, original App identity and retained-context checks. The
historical gap is explicit in both plan and parent receipt. `p34_app_resume`'s
old complete-audit gate remains strict; only its unchanged native execution body
is factored for reuse. Neither route has a skip-audit flag. The shared core still
checks the latched reset/context immediately before one DHCSR resume store and
performs the reviewed 20-second sustained health observation.

Offline eligibility validation matched 412 unique records in 15.278 seconds.
Use a 120-second owned parent for this successor, with an explicit worker-entry
45-second hashing cutoff before probe open, unchanged 50-second native observation
and five-second per-call bounds. This reserves time for observation/close instead
of forcing real hashing work into an arbitrary ten-second assumption. The device
action scope is unchanged. Exhausted pre-open headroom must produce zero native
entry calls. Final source-bound tests and scoped independent review precede
the one planned `.cache/p34-reconciled-resume1` execution; no resume is yet claimed.

#### 23.2 Original App Resumed Without Reset

Final independent RESUME-23 review found no remaining blocker for the one
`.cache/p34-reconciled-resume1` cell. Test4 binds 16 original plus 11 successor
host tests; independent read-only reruns and the added headroom negative passed.
The reviewer independently matched the status2 SDK trace and measured 412-record
eligibility in 16.15 seconds. Test1's missing mock-plan `evidence` field is a
preserved host fixture failure; test2/test3 predate the final budget/source binding.

The actual cell ran at 14:20:20Z and closed normally at 14:21:00Z, parent exit0,
no timeout, 40.168 seconds. Worker result is `ORIGINAL_APP_RESUMED_STABLE`:
exactly one attempted/returned DHCSR resume, no reset observed and unchanged
App header/VTOR 0x08010000. The 20 samples cover 21.008 seconds, including the
fresh final checkpoint. First-to-last millis delta is 21040; main-loop and
watchdog-feed deltas are each 5548. CFSR/HFSR remain zero. These are observed
runtime-health facts, not a new OTA performance test or universal liveness proof.

Native SDK close returned, no debugger process remained, and authorized SEGGER
history hashes remained unchanged. Keep J-Link physical supply connected. The
board is no longer intentionally halted; do not run stopped-only selectors or
replay either resume/provisioning entry. Parent explicitly preserves
`historical_sdk_audit_passed=false`; the old long SDK trace failure remains real.
Closing native trace/source/output review follows without another device command.

Closed-original independent review matched exactly 13 target writes: 12
pre-resume DCRSR read selectors and one DHCSR A05F0001, with zero target writes
after resume. AP CSW/TAR were restored and native close was present. All 620
post-resume memory words match the 20 samples and original headers; 97 baseline
words and 189 resume-read journal words also correlate. All 116 source/snapshot
bindings and 412 evidence records match. This short-cell PASS does not erase
the historical NOR SDK gap. Root's output preflight audit checked 1007 files in
15 selected new output trees, all project-local, with three normally closed
workers and unchanged authorized native history. Later reader work below adds
separate project-local outputs; no PowerShell, external cleanup or Git publish.

### 24. Finalized R2 Capture And Nonmutating Reader Qualification

Continuation remains technical work, not another generic permission request.
`p34_finalized_vtor_capture.py` is a new HOST_ONLY adapter: one exact planned
30276 or 30277 digest/version, full 619580B image and selected 524B vector table,
caller connection/boot generations and persistent reset latch around every read.
The legacy/raw-R2 capture and old DAP whitelist remain unchanged. A plan for A
rejects B, even though both are valid finalized artifacts. Successful host capture
still reports operational_readiness=NOT_ESTABLISHED and native_route_validated=false.
`.cache/p34-finalized-capture1` has six passing methods including version/table,
old-image, failed/short/non-byte read, clock/deadline, owner/generation and consumed
reset-latch negatives; independent read-only rerun passed. This is not native
qualification or an OTA success claim.

Separate `recovery_entry/finalized_reader.py` permits only DHCSR, VTOR and the
fixed finalized App extent. Logical reads split at 1024-byte TAR boundaries;
AP data-register writes are absent. It verifies word/increment format, native
return values and DP sticky status, latches failures and preserves reset history.
It has no connect/reset/resume, NOR/EEPROM access or retry entry. Its caller owns
a finite native process and pure host lease callback. The seven initial mocked
SDK tests passed; review found two deadline escapes (initial lease time was not
charged, and final log emission could return late). Both are repaired with an
entry-derived absolute deadline and final checks, plus zero-further-I/O negatives.
Owner observation also rejects halt/lockup; no new whitelist is added to Dap.

`p34_finalized_reader_device.py` defines a separate finite read-only qualification
on the CURRENT old App. It must independently complete transport, not treat the
finalized classifier's early digest rejection as transport success. Read 619580B,
require the first 617588B to equal original 30275 exactly, and preserve the extra
1992B at [0x080A6C74,0x080A743C) solely as unclassified tail. Recheck the original
96B header, primary 524B table, VTOR/DHCSR, owner/reset continuity and old OTA idle
fields. Only then apply the finalized classifier OFFLINE to the same saved bytes,
requiring rejection. No duplicate read is needed to prove that negative result.

Planned single cell: `.cache/p34-finalized-reader-device1`, root sole operator,
same J-Link supply retained. Parent 300s, observation 270s, reader/transport 240s,
native calls/bursts <=5s and each caller's remaining allowance. All output,
source/temp/config/logs are project-local; native Roaming/SEGGER scope unchanged.
No halt, reset, resume, AP data write, internal-image replacement, EEPROM/NOR
command, host watchdog feed or automatic retry. Compare current original bytes,
retain failure evidence, normally close and fully correlate the CLOSED SDK log
with raw data before declaring transport qualification. A transport success
still does not qualify actual R2 runtime generation or complete-state recovery.
Final bound model tests and independent worker review precede physical execution.

The old-30275 rollback and complete-state confirmation/restore conditions remain
for the first normal R2 OTA. `recovery_confirm/confirm.h` is still HOST_ONLY, not
a physical EEPROM-write capability. Existing source-bound recovery tests should
not be rerun merely because this reader changes, and no user decision is needed
just to continue this offline/nonmutating work. Different destructive scope or
waiving the complete-state recovery prerequisite would require a specific decision.

#### 24.1 Completed Extended Read And SDK Audit

The planned cell above is now spent, not replayable. The worker closed normally
at 2026-10-05T15:19:53Z after 144.806 seconds, exit 0 and no timeout:
`.cache/p34-finalized-reader-device1` reports
`EXTENDED_OLD_APP_READ_FINALIZED_REJECTED`. The original 617588B prefix matches
30275 exactly; the extra 1992B remain unclassified, not part of that firmware.
Original header/table/VTOR and eight OTA-idle field reads were checked, followed
by a terminal owner/reset observation. This last check repairs the reviewed
late-reset gap after the idle reads. Seven worker tests in device-test4 passed;
the finalized reader's ten current tests are in `.cache/p34-finalized-reader3`.

`.cache/p34-finalized-reader-audit1` reports `EXTENDED_READ_SDK_AUDIT_PASS`.
The closed SDK trace reconstructs 931 frames / 155373 words / 619580 payload
bytes, all eight idle reads, zero target data writes, native close and AP/DP
restoration. Independent review repeated the reconstruction and checked 52
execution inputs/snapshots and 116 audit records. Five audit regression methods
passed in audit-test2, including the shared parser binding. No halt, reset,
resume, new OTA or programming occurred. This proves the old-App transport cell,
not physical R2 admission, uninterrupted reset continuity or a complete-state
provisioning route. It does not repair the historical NOR SDK gap in section 23.

### 25. HOST_ONLY Confirmation Page Transport

`recovery_confirm/page_port.py` connects the unchanged `rc_confirm()` core to
an injected EEPROM memory model through `p34_confirm_page.py` and its host DLL.
The exact inactive 64B record is derived by the original C transaction using
the actual captured BCB pair as a fixture and hypothetical internal R2-A bytes;
Python does not invent BCB fields. The actual old App is rejected before model
EEPROM I/O. There is no physical GPIO write port or device entry.

One record attempt becomes eight aligned 8B pages. Each page requires a known
released STOP upper timestamp, at least the documented 5ms write-cycle wait,
one ready ACK and exact readback. Unknown STOP, busy/read failure or exhausted
time blocks independent observation; no payload retry is allowed. A delivered
page returning an error is settled before the unchanged C observer arbitrates
actual surviving bytes. A delivered final-page error may correctly be CONFIRMED.

RECOVERY-CONFIRM-PORT-01 identified two required repairs: an initial failed read
did not permanently forbid later same-port writes, and the actual Boot-local
quoted `eeprom_bcb.h` include was absent from evidence inputs. Both are fixed:
first error is latched, write requires observation eligibility, and both Boot
and App headers are bound and checked for normalized-byte equality.
`.cache/p34-confirm-page2` has nine passing methods, including all 64 page/prefix
tears and the zero-further-I/O initial-read failure regression. GCC
`-Wall -Wextra -Werror` produced no diagnostics. Independent bounded review
matched all 49 inputs/snapshots, DLL and compiler, reran the new regression and
closed both findings. Page1 remains historical evidence, not current-source PASS.

This work adds no EEPROM authority. Actual App replacement, the original
transaction's inactive BCB record and a fresh Boot/reset exit still need exact
scope and technical qualification. CONFIRMED-only confirmation cannot overwrite
STAGED/APPLYING/TEST_BOOT/ROLLBACK, and replaced App bytes must never resume via
the old WFI context. J-Link power stays connected; no commit/push/release occurs.

### 26. COMPLETE-STATE-26: Pure Flash Plan And Original Boot Branch Model

This is preparation for a scope decision, not an authorized device plan.
`recovery_confirm/flash_plan.py` accepts only the pinned finalized R2-A bytes.
`geometry(image, unit=2048)` returns the physical-sector minimum;
`geometry(image, unit=4096)` reports the different existing Boot-port boundary.
`model_manifest(image, preimage)` requires the complete 620544B preimage, including
all collateral bytes, and never fills a missing suffix. `simulate()` performs
only byte-array erase/program steps. Its `reset_allowed=false` is a prohibition,
not a physical reset safety proof; no register or transport capability exists.

| Geometry | Exclusive end | Physical sectors | Payload-external bytes |
| --- | --- | --- | --- |
| Direct 2KiB candidate | 0x080A7800 | 303: Bank1 224, Bank2 79 | 964 |
| Existing 4KiB Boot port | 0x080A8000 | 304, in 152 calls | 3012 |

Both start at 0x08010000; payload ends at 0x080A743C. The actual RGT7 Flash
header and `b1/compile_commands.json` are now bound. The runner requires the
specific Flash translation unit for `X_Track_Boot` with `-DAT32F435RGT7`.
Bank2 starts at 0x08080000. This configuration provenance is not qualification
of either bank's native status, protection, unlock/program/erase or completion
handling. Existing Flash library loop-count timeouts are not a host wall-clock
settlement oracle, and failure is not permission to clear state or reset.

The current physical capture stops at payload end. The additional 964B remain
MISSING; tests use explicitly synthetic non-FF bytes and cannot supply a device
preimage. Good: full hypothetical preimage preserves each suffix byte. Bad:
passing the present 619580B capture raises ValueError rather than appending FF.
No generated model bytes are classified as physical observations.

`p34_complete_state_plan.py --output-dir <fresh-project-local-directory>` runs
seven Python methods and a separate C harness linked with the unchanged Boot
and restricted confirmation sources. All eight physical input archives match
their original result bindings. These are host self-tests, not MCU builds or
formal acceptance. The two interruption scopes are deliberately distinct:

- Python tests every one of 606 boundaries between modeled 2KiB erase and whole
  sector-program steps. Previously programmed sectors match the desired bytes,
  at most one sector is erased, and unattempted sectors remain exact. This does
  not simulate individual Flash words, analog failures or controller settlement.
- C resets its memory model to original 30275 before EACH of 303 isolated-sector
  erasures, then runs the original Boot state machine. 302 damaged-App cases
  select actual backup 30274; one erasure beyond the old App leaves 30275 valid.
  These outcomes do not classify all sequential mixed-image interruption states.

Other C cases establish: a valid recovery does not displace a valid original App;
complete internal R2-A with old CONFIRMED BCB jumps to 30276 while cur_vcode stays
30275; the restricted original transaction commits inactive A, seq12850, then
the modeled boot returns internal/BCB 30276 without another write. If both
internal App and backup are invalid, recovery 30276 is selected instead.

The recovery case now asserts actual erase AND program high-water addresses
0x080A8000 and verifies all 3012 payload-external bytes became FF. This branch
extends 2048B beyond the proposed direct-write envelope, so its behavior is NOT
covered by the direct 964B preservation model. Do not use it as an automatic
failure exit under a narrower direct-write scope.

`.cache/p34-complete-state-plan1` retains the first passing model and its review.
Review found no HOST_ONLY algorithm issue but requested Flash configuration
provenance and explicit fallback footprint. Both are in successor
`.cache/p34-complete-state-plan2`: seven methods PASS, all 606 modeled boundaries
and 303 isolated Boot erasures checked; GCC `-Wall -Wextra -Werror` produced
zero diagnostics. The prior model is not relabeled as a current-source result.
Independent bounded re-review closed both follow-ups: all 67 inputs/snapshots,
compiler and executable bindings matched, with three normally closed execution
receipts and the explicit recovery-footprint assertions. No old campaign or
additional test/model run was performed by that follow-up review.

#### 26.1 Pending Physical Scope And Qualification

Root asked the user for this exact new candidate scope: direct internal App
[0x08010000,0x080A7800), restore the captured final 964B exactly, original
transaction-generated inactive EEPROM A [0x00,0x40) only if the complete current
BCB pair still matches the plan, and a separately qualified controlled reset
through the retained Boot after verified completion. No response to that new
scope is recorded here. It must not be inferred from prior recovery-NOR approval.
No Boot/NOR/option/protection changes, power interruption, force-confirmation of
pending states or old-context resume are part of this candidate. An uncommanded
reset may invoke the Boot fallback just described; preservation is not guaranteed
across that failure and it cannot be hidden by a model PASS.

Before any physical writer, root still owns these concrete gates: fresh full
erase-envelope preimage and exact original Boot/App/BCB/owners; separate bounded
two-bank native adapter with ambiguous-return/no-retry/error/lock/readback tests;
actual EEPROM page port with known STOP and completion; and a fresh Boot/reset
entry/exit model binding watchdog, debug retention, SD/DMA settlement and R2 ELF
health/vector addresses. A failed or busy operation does not permit reset,
continuing payload, guessed restoration or widening the write range. Use the
finalized full-image reader only after actual R2 installation, not as proof now.
The board has not been touched by COMPLETE-STATE-26; the last measured state
remains original 30275 running with recovery 30276 available. No new performance
result, commit, push or release has been produced.

Output-path audit `.cache/p34-complete-state-output-audit1/result.json` checked
17 generated trees and 629 files, including the inherited finalized-reader and
page-model outputs omitted from the earlier summary's audit. All resolved inside
the active project. No external output path, PowerShell invocation, cleanup or
physical device operation was selected in this continuation. This audit captures
the files before this final documentation addendum; its path-boundary finding
does not claim a frozen hash for this subsequently updated task note.

### 27. Recovery Ports And Nonmutating Flash Preflight

The user's subsequent "do it" continues implementation, tests and qualification
of this recovery prerequisite for the reviewed group1-to-group16 Boot APPLY
checkpoint route. It is not a new BLE throughput result, nor a blanket grant to
replace Boot or write arbitrary EEPROM. The exact destructive scope in 26.1 is
still held until the complete physical route and its failure exits are qualified.
J-Link remains connected as the board's direct 3.3V/GND supply.

`p34_recovery_ports.py` now tests separate native word, GPIO EEPROM page,
two-bank Flash, C-derived confirmation and fresh-Boot exit adapters. These are
capabilities, not a complete physical coordinator. The C HOST_ONLY library
produces an immutable inactive-record draft; physical wire results must return
through an independent actual A/B/A/B observation into the unchanged C oracle.
No target callbacks are smuggled into the host model, and no Python-generated
BCB fields replace the original transaction.

`.cache/p34-recovery-ports3` has 21 passing HOST_ONLY tests and 70 bound inputs.
Independent re-review closed F27-1/2/3: exact address/value write allowlists
intersect each operation, both Flash banks must be idle/locked/error-free before
the first unlock, and read-only USD/FAP, EPPS and SLIB checks precede mutation.
The reset adapter permits only one AIRCR attempt and requires independently
admitted fresh Boot context before release. Its injected admission callback and
each port's ownership callbacks are not yet physical qualification.

The edge-driven EEPROM slave tests do not establish wall-clock feasibility.
One modeled 64B read uses approximately 76115 native calls and an 8B page about
14680; mock elapsed time excludes actual native overhead. Existing 15s/60s
HOST_ONLY limits, the proposed separate operation limits and the default 600s
EEPROM budget must not be reported as measured physical budgets.

#### 27.1 Prepared Read-Only Cell

`p34_recovery_preflight.py capture` is restricted to the still-running original
30275. It reads the entire original 65536B Boot and the 620544B App envelope
[0x08010000,0x080A7800), retaining the final 964B separately. It verifies the
original 617588B App prefix and header, checks DHCSR/VTOR/OTA idle around each
chunk, and compares Flash identity/protection/clock metadata before and after.
No halt, reset, target DRW write, power command or EEPROM access is available.
Each completed chunk is archived even if a subsequent owner/reset check fails.

The finite plan is one capture in `.cache/p34-recovery-preflight1`, followed by
offline audit of that same closed directory, never a replay to repair a log.
Parent deadline is 360s. The worker's common 330s deadline starts before setup;
connection time is deducted, reads get at most 300s, and fewer than 240s left
rejects before any capture read. A normal capture is explicitly
`FLASH_PREFLIGHT_CAPTURED_NOT_WRITE_ADMITTED`.

P27-1/2/3 repairs preserve per-archive close errors while still attempting native
close, require actual SDK/journal closure and archive reconstruction, and use
the shared deadline above. `.cache/p34-recovery-preflight-tests4` closed normally
with 10 passing methods and 53 source/input bindings. Tests3 is preserved: its
negative paths rejected correctly but expected the wrong exception class.
Tests4 changes those expectations, not production guards. The tests are all
HOST_ONLY, including synthetic SDK traces, not new device evidence.

The successful audit oracle requires 672 chunk reads, 5420 single-word reads,
176988 target words, 1346 samples of each owner field, two samples of each of 18
metadata addresses, exact archive reconstruction, AP restoration, actual native
close and normal parent closure. Forbidden DRW/high-level operations, removed
guards, chunk mismatch, changed archive, bad owner and missing close are negative
cases. Native-call timing statistics do not qualify the complete GPIO path.

Before execution, all controllable outputs, host environment directories and
53 source snapshots were checked within the active project; USB123456 was
present and no competing debugger process was found. The only external writer
allowance remains the already authorized native history/config directory
`C:\Users\SU\AppData\Roaming\SEGGER`; no cleanup is authorized. Independent
P27 re-review closed all three findings and independently matched all 53 inputs
and snapshots plus the normally closed 10-test receipt. It admits only this
bounded nonmutating cell, not a writer or reset. At this record's preparation,
no new hardware operation has run, and the historical NOR SDK audit gap remains.

Remaining work after a valid capture: bind same-connection halt/media ownership,
durable preimages, serialized sector execution, immutable current C BCB draft,
final complete integrity checks and actual reset-catch/R2 health qualification.
Long-mutation SDK log continuity must also be solved and qualified, not assumed
from a shorter capture. No R2 internal installation, group16 activation, new OTA,
speed improvement, commit, push or release is claimed by this section.

#### 27.2 Executed Physical Preflight And Independent Reconciliation

The cell in 27.1 is now spent. `.cache/p34-recovery-preflight1/parent.json`
closed normally at 2026-10-05T18:37:16Z, exit 0, no timeout, 171.142768s.
The complete Boot retained SHA a63346db0dc673dc42adf6064892c466af5c4571df53cb55fe5b6ea154c1fdf4.
The actual 620544B envelope has SHA
b777d7ff8ffe2ec449758d90a18ed81200dd8c93276312104272326d48888e39;
its final 964B have SHA
52d9e1380a568696b47f4acb538a43ce2e406b6ef0b4e2a7b1cd5a43beae3334.
These collateral bytes include real non-FF data. MISSING_964_BYTES is closed;
replacing them with FF is not permissible. The preceding 619580B also match the
previous independently audited extended capture exactly.

`audit.json` reports `FLASH_PREFLIGHT_SDK_READ_AUDIT_PASS`. Independent review
recomputed the entire 27.44MB SDK / 2.19MB journal trace and matched all fields,
all 53 source/input snapshots, normal native close, restored AP TAR/CSW/DP and
unchanged authorized SEGGER history. The observed counts are 672 chunks,
5420 single-word reads, 176988 target words and 201373 native register calls.
Mean native-call time is 0.760545ms, p99 1.056ms, maximum 460.149ms. These are
native-call observations, not GPIO end-to-end timing qualification.

Both metadata samples match: ID 70083347 / 1024KiB, exact five-register 288MHz
clock profile, Flash DIVR 11 (/3, 96MHz), PSR 330, CONTR 80, USD 03FFFFFC,
EPPS0/1 FFFFFFFF, SLIB 0, CTRL1/2 80, STS1 20 (old ODF) and STS2 0.
The static protection/clock/idle predicates used by `Sector` match. The core was
running; no same-erase-epoch halt/WDT/media admission was obtained. No target
data writes, halt, reset, EEPROM operation, new OTA or App replacement occurred.

#### 27.3 Finite SDK Log Rotation Discriminator

Independent review supports a separate bounded read-only mechanism experiment,
not replay of 27.1 to recreate missing evidence. New
`p34_recovery_log_probe.py` reuses the unchanged `acquire` and `scan_trace`.
It rotates only the host SDK log after each 128 archived 1024B chunks: five
SetLogFile calls, six distinct raw files, one continuous probe connection and
one final native Close. No intermediate Close/Open/Connect, fake Close records,
merged log presented as original, target DRW, reset or power command is allowed.

Each switch reads DP CTRLSTAT, AP CSW and AP TAR before and after, requires exact
equality and healthy DP/word format, and records monotonic bounds. This adds
register reads, not target data reads; the existing full 672/5420/176988 oracle
remains unchanged. Each prior log is hashed after switching and checked again
after final close. A switching exception permanently fails the operation; no
next capture chunk, retry or replacement of old evidence is permitted.
Archive and native close are still attempted independently.

HOST_ONLY tests and bounded independent re-review precede the new cell at
`.cache/p34-recovery-log-probe1`. Output/log/source/test/temp locations remain
inside this project, with only the existing native SEGGER history permission.
The parent/worker deadlines remain 360s/330s and include switching overhead.
Final audit directly streams the six original files in order through the
existing strict scanner with cross-file parser state and compares the complete
Boot/envelope against 27.2. Partial native calls, missing/extra/reordered data,
forbidden writes and absent final close cannot become PASS by segmentation.

This qualifies a logging mechanism only. Online sealing currently records
hashes rather than fully admitting a completed mutation segment; therefore even
a successful probe is not long-mutation logging safety. It cannot repair or
explain the historical NOR SDK blank-tail gap. A future actual GPIO timing cell
uses one 64B repeated-START BCB read under a separately fresh, settled halt/media
entry and verified original-App exit, not a same-value EEPROM probe write.
No analog waveform timing is claimed without instrument evidence.

The first eight-test HOST_ONLY result is preserved in log-tests1. A root
self-review added native segment-head/tail state binding and complete-call/frame
boundary checks without changing the original scanner. Successor
`.cache/p34-recovery-log-tests2` passed nine methods in 20.450s; independent
review matched all 58 inputs/snapshots and the normal exit-0 test receipt,
and admitted the one cell above. Two non-blocking audit checks are retained
for physical-evidence review: sealed-before-close records equal final records
0..4, and switches occur at archive chunks 128/256/384/512/640 with one state
event between each attempt/return. No new physical cell has run at this addendum.

#### 27.4 Executed Six-Segment Read And Physical Boundary Values

The 27.3 cell is now spent. `.cache/p34-recovery-log-probe1` closed normally at
2026-10-05T19:07:41Z, exit 0, no timeout, 166.586062s. Offline audit and
independent direct recomputation both report `SEGMENTED_SDK_READ_AUDIT_PASS`:
six original files total 27445914B, 672 chunks, 5420 single-word reads,
176988 target words and 201403 native register calls. All 58 input/snapshot
bindings, images, collateral and authorized history hashes matched. There was
one actual Close, no high-level CPU Connect/halt/reset and no target DRW store.

Independent review checked the two explicit supplement oracles: all five
sealed-before-close records equal final records 0..4 and their files remain
unchanged; the switches are at complete archive chunks 128/256/384/512/640,
each with one state event between attempt and return. DP CTRLSTAT remains
F0000040, CSW 23000052; actual TAR values before/after the five switches are
0801F000 / 0803F000 / 0805F000 / 0807F000 / 0809F000. Each measured switch/state
window was approximately 7.38..8.27ms. These actual values reflect a 4KiB TAR
wrap at these boundaries, not the generic model's conservative 1KiB wrap.
The existing 1KiB transfer chunks are still safe; do not impose the model's
computed terminal TAR on hardware in place of the observed register values.

This closes the bounded read-only log-rotation qualification only. Mutation
logging, physical GPIO timing and historical NOR SDK gap repair remain false.

### 28. Fixed GPIO Read Timing Preparation

`recovery_confirm/gpio_read.py` adds a sole-use `Read64` over the existing native
Pins/Words path. It requests only EEPROM address 0, length 64, maximum 300s;
page and write-ready-ACK interfaces are explicitly unavailable. Its independent
`wire_trace` reconstructs the A0/pointer0/repeated-START/A1 read from GPIO stores
and physical SDA samples, including 63 master ACKs, final NACK and STOP. A
returned byte array alone cannot establish a read-only physical transaction.

`.cache/p34-gpio-read-tests1` has four HOST_ONLY passing methods, including
exact full EEPROM preservation, unavailable write interfaces, expired/failed
read with no retry/cleanup and corrupted trace rejection. The full injected
native path uses 76115 SDK calls, 1435 GPIO stores and 13788 target word reads.
Its clock models sleeps, not actual native overhead. There is no physical entry
in this runner and no board operation in this stage. Independent review is
requested before integrating a new fresh-WFI/media/unchanged-App-exit supervisor.
Old PC/SP/WFI snapshots and the historical retained-resume worker are not replayed.

#### 28.1 Decoder Review Closed In HOST_ONLY Scope

P27-GPIO-1/1a/2 found missing physical-evidence checks in the first decoder,
not a new device failure. The successor rejects changed actual R/W bits,
actual final ACK instead of NACK, conflicting SCL/SDA samples, wrong master
release and START/STOP positions, and any extra events outside its exact
measurement slice. Each START/STOP now needs a fresh matching INPUT pre-state
from the current GPIO latch epoch and a matching post-state before the next
store or measurement return. Deleting all boundary samples or only either side
is a failure, never vacuous success. No additional target I/O was added.

`.cache/p34-gpio-read-tests3` passed seven methods; independent review matched
all 74 inputs/snapshots and repeated the relevant normal/negative models. All
three findings are closed for the strict measurement interval only. Original
tests1/2 remain historical. Full-cell absence of persistent writes, actual GPIO
duration and device-entry/exit qualification are not established by this result.

#### 28.2 Whole-Session Native Call Journal

`recovery_confirm/ap_journal.py` wraps only native AP/DP calls after the Dap
constructor binds signatures and before connecting. It journals exact arguments,
results, read values and monotonic call intervals. Callback/native/clock failure
latches out further AP calls while allowing the underlying native Close. That
close alone does not prove AP restoration. The auditor compares every actual
SDK AP call with this independent call journal and an injected exact target
read/write scope; high-level CPU control remains prohibited.

P27-AP-1/2/3 found and closed three HOST_ONLY issues: a DRW reaching a 1KiB
boundary now invalidates the inferred TAR until an explicit TAR write instead
of guessing wrap; CSW/TAR access requires bank 0, with bank F0 limited to AP3
identity reads; invalid/nonfinite/boolean/backwards clocks fail before the next
native call. A bad returned clock retains the already attempted call and forbids
another. `.cache/p34-ap-journal-tests2` passed nine methods with seven bound inputs;
independent review repeated the new boundary/bank/clock cases and closed all
findings. No frozen reader/scanner, previous physical log or target was changed.

#### 28.3 Fresh GPIO Session Integration Draft

`p34_gpio_read_device.py` is an unexecuted integration candidate. It binds a new
current Control/rendezvous result, two actual updater/SD-media observations,
the fixed original App and inactive-A fixture, the new single-read measurement,
post-read context/media/owner/vector checks and the existing original-App resume
and 20s health observer. A failed read, archive or postcheck cannot invoke resume;
there is no reset, EEPROM page, NOR or internal Flash writer. A failed or uncertain
resume is never retried. Controlled evidence closure is distinct from device
health. The parent is bounded at 450s and the worker shares a 420s deadline from
entry, including setup, read, exit and native close allowance.

The full-cell auditor also reconciles native target stores against high-level
action markers and phase boundaries: one WDT halt-pause store, arm/disarm only
before the read, GPIO stores only inside that read, read-register selectors
outside it, and one original-context release after the completed read. The
strict measurement slice is not substituted for this whole-cell check.
`.cache/p34-gpio-device-tests1` is the current HOST_ONLY integration test run;
no physical GPIO cell is admitted or executed by this draft record.

The first integration run closed with five HOST_ONLY passing methods and 122
source/input bindings. Independent review is pending. A subsequent root
self-review added explicit correlation of every GPIO-interval target read with
the AP call journal and measurement count; the first test result is historical
for that changed integration source until its successor tests run. This is not
physical GPIO evidence and does not reopen the completed component reviews.

Intermediate path audit `.cache/p34-recovery-output-audit1/result.json` checked
17 generated trees and 1193 files, including all inherited recovery-port and
preflight tests plus the new log/GPIO/AP integration outputs. All selected paths
resolved inside the active root. Both new physical workers closed normally and
their authorized SEGGER history hashes remained unchanged. No PowerShell,
project-external output selection or cleanup occurred. The audit predates later
unfinished integration edits and is not a frozen current-source hash claim.

#### 28.4 Consolidated Integration Repairs And Component Reuse

P28 review accepted reuse of the unchanged component oracles, without new
hardware campaigns or NOR/reset/MSP requirements. The new reuse manifest binds
control test3 (22 methods), owner test2 (9) and App-resume test3 (16), including
their exact source snapshots. Only the old orchestration wrapper
`Tools/ota/p34_app_resume.py` is excluded from current-source equivalence; its
original snapshot is retained, and neither that wrapper nor its old halted
context is used by this new session.

The reviewed whole-cell manifest now enforces pause before comparator arm before
disarm before the GPIO interval; the sole DHCSR release must be the last target
DRW write. GPIO samples are correlated individually with native AP read values,
not merely trusted from a higher-level journal. Measurement word/store counts
and monotonic interval are checked separately. The complete auditor also checks
actual SDK/journal identity, original read bytes, phase-scoped writes, original
App exit, native Close and actual AP restoration receipts.

The real-component HOST_ONLY bridge uses unmodified Control/rendezvous/owner/
Resume with JournalSDK and the existing edge-driven EEPROM slave. Test3 closed
with seven passing methods and 426 bindings, including normal completion,
pre-entry header rejection, a delivered GPIO error and a delivered DHCSR error.
On the last case the model core runs, but the AP error latch prevents further
observation and AP restoration while Native Close still returns. The result is
explicitly `UNKNOWN_AFTER_RELEASE_ATTEMPT`, with release attempted, not returned,
and a retained native error; it is not misreported as a proven retained halt.
No retry, reset or latch bypass is introduced to manufacture a healthy result.

Successor `.cache/p34-gpio-device-tests4` exercises the actual composed auditor
on synthetic SDK records from the real-component bridge, plus matched record
mutations for ordering, outside-interval stores, extra/early release, reads,
Close/restore, counters/timing and source/snapshot drift. These fixtures are
explicitly HOST_ONLY, not physical evidence. A bounded batch re-review must
close the integration findings before the planned physical GPIO cell. Neither
test3 nor this test-run description authorizes internal App/BCB replacement.

#### 28.5 Prepared Physical Read Cell, Not Yet Executed

Test4 closed with eight passing methods, 426 source/input bindings and a real
HOST_ONLY invocation of the composed auditor. The 13 negative classes are
included in those methods, not reported as separate hardware runs. Root has
requested one consolidated re-review of P28-AUDIT-ORDER, P28-INTEGRATION and
P28-AUDIT-HOST before proceeding. Existing P3-4 debug/read authority is the
candidate scope here; this is not the pending destructive scope from 26.1.

The finite cell is `.cache/p34-gpio-device1`: one new WFI rendezvous on original
30275, one EEPROM random-read of inactive A [0,64), physical GPIO protocol/elapsed
time evidence, then one same-context original-App resume and the existing 20s
health observation. It uses SWD1000 / USB123456 and the pinned V8.18 DLL. The
source App, original A fixture, test4 and exact reused component receipts must
all match immediately before the worker opens the probe. A new complete BCB
pair or actual R2/Boot reset qualification is not claimed by this 64B read.

Target stores are limited to WDT halt-pause bit preservation, the owned WFI
comparator arm/disarm, read-only core-register selectors, PB6/PB7 one-bit
set/clear edges and the final no-reset DHCSR release. The EEPROM's volatile
read pointer changes; no EEPROM payload, internal Flash, NOR, option/protection
or RAM-code write is available. The bus must start released/high, wait at least
5ms from its last possible STOP, and finish with physically evidenced STOP and
the original GPIO latch/configuration. J-Link's direct supply remains connected.

Any read, archive, context/media/owner/vector or time-budget failure prevents
release and retains evidence. Once a release is attempted, an uncertain result
must be recorded as unknown rather than assumed halted or retried. Native Close
is still attempted once; an AP failure may prevent AP restoration and is not
hidden by a successful Close. Any subsequent reconciliation is a separate
read-only decision based on that actual outcome, not a replay of this cell.
Parent/worker limits are 450s/420s, the EEPROM read has 300s, and verified exit
requires at least 40s remaining. All controllable files and caches stay under
the project; only previously authorized native SEGGER history/config remains
an external-write exception, with no cleanup authority.

Independent final P28 review closed all three integration findings: all 426
current inputs and snapshots plus reuse.json matched. A read-only re-execution
of the composed model audit reproduced 80354 native calls, 15610 target reads,
1459 target stores, 1435 GPIO stores, 13788 measurement reads and one Close.
The reviewer separately rejected the matched pause-order/post-release-selector
mutations and repeated the artifact-free real-component bridge cases. This
admits only the planned read measurement under its live gates, not Flash/BCB
replacement or an analog waveform claim. Physical execution is the next action;
this paragraph itself remains pre-execution evidence.

#### 28.6 Executed GPIO Read And Same-Context Original-App Exit

The cell in 28.5 is spent. `.cache/p34-gpio-device1` closed normally at
2026-10-05T20:43:31.995Z, exit 0, no timeout, 100.427822s. Its result is
`GPIO_READ_ORIGINAL_APP_RESUMED`; offline audit and independent review both
closed `GPIO_SESSION_SDK_AUDIT_PASS`. All 426 current inputs and snapshots,
reuse bindings, archives and authorized native history hashes matched.

The single physical A64 read returned the original bytes (SHA
a5265e814364f0648f46796ffb48eb6ecc018149fbedd4264e51654ad11031f5), in
72.92436400003498s. Its strict interval contains 76115 native calls, 13788
target reads and 1435 GPIO stores, with two STARTs, 605 rising clocks and one
STOP. The physical decoder checks command direction, slave ACK, 63 master
ACKs plus final NACK, released SDA during data and evidenced START/STOP levels.
These digital samples do not establish analog rise/fall/setup/hold margins.

The complete cell has 80360 native calls, 15612 target reads and 1459 stores:
1435 GPIO, one watchdog pause, two comparator, 20 read-register selectors and
one final release. Native Close occurred once. Five freshly read contexts were
identical: PC 08045A78, MSP 20057FA0, xPSR 21000000, CONTROL 4, mask fields 0.
The release was followed by 21 running samples spanning 20.9319242s: millis
advanced 20959, loop count 5314 and watchdog feeds 5312, without observed reset,
lockup or new fault. Actual final AP reads establish TAR E000EF38, CSW 23000052
and DP 00000040, rather than relying on Close alone.

The original App remains running, and J-Link's direct power remains connected.
No App/Boot/NOR/EEPROM payload programming, reset or OTA occurred. This is only
an A64 observation, not a fresh complete A/B pair. Same-context resume is valid
only for the unchanged App; it must never be used after App replacement.

### 29. Runtime Counts Before A Long Recovery Transaction

`python -I -S -B -X utf8 Tools/ota/p34_recovery_runtime_budget.py run
--output-dir .cache/p34-runtime-budget1` completed `RECOVERY_RUNTIME_HOST_PASS`:
two helper tests, 83 current input/snapshot bindings, a normally closed host
model worker and independent read-only review. This tool does not load the
J-Link DLL or access the board. It uses the original HOST_ONLY C confirmation
DLL and the injected GPIO/Flash models; all 303 Flash sectors were modeled
sequentially with the actual full envelope preimage and its non-FF 964B suffix.

| Operation | Model native calls | GPIO-sample extrapolation |
| --- | ---: | ---: |
| Representative read64 | 76115 | 72.924364s |
| Representative page8 | 14660 | 14.045473s |
| Representative ready ACK | 1795 | 1.719756s |
| Representative read8 | 13755 | 13.178409s |
| Entire original-C EEPROM transaction | 698350 | 669.076130s |
| All 303 Flash sectors | 9780900 | 9370.898139s |

The baseline native-call duration sum is 46.6372405s; the projections use the
larger inclusive 72.924364s interval, not only native-call durations. The whole
EEPROM count includes two prewrite read64 operations, eight page/ACK/read8
triplets and four final read64 operations. GPIO configuration checks occur
periodically, so later instances have slightly different counts: multiplying
the representative subcounts would incorrectly give 698370. Use the complete
transaction count, not that sum.

Independent source/byte reconciliation found 152410 non-FF Flash words,
224 Bank1 plus 79 Bank2 sectors, and all 303 sectors nonempty. The corresponding
formulas are `303*2100 + 152410*60 = 9780900` native calls and
`303*13 + 152410*2 = 308759` target stores. Final model bytes equal exact R2-A
plus the actual captured suffix. These are host execution counts, not physical
Flash erase/program results or exhaustive sequential Boot interruption tests.

The default EEPROM 600s cannot be used as a qualified complete transaction
budget: even this single-sample projection is about 669s. The model explicitly
uses 1800s for both EEPROM wire and transaction and 2400s for the underlying
Words lifetime. Those values are modeling inputs, not admitted hardware limits.
Flash's approximately 2.6-hour projection likewise is not a coordinator timeout
or worst-case upper bound. Fresh entry, complete BCB capture, archive durability,
owner checks, extra busy polls, eight 5ms settlement waits, journal/rotation/audit
overhead, final integrity, reset/catch and health observation require separate
allowances. No measured EEPROM-write or Flash-write qualification was obtained.

### 30. Online Sealed-Segment Audit Primitive

Scope: fail before a subsequent mutation if the just-finished original SDK
segment is incomplete. `recovery_confirm/mutation_audit.py` is a new capability;
the already reviewed `ap_journal.py` and read-only `log_segments.py` are unchanged.
There is no physical coordinator or device command entry in this module.

Signatures: `Cursor.verify(lines, rows, read_allowed=..., expected_stores=...,
final=False, bind_words=True)` validates one complete native/journal interval.
`SealedGate.begin(index)` consumes the next segment position;
`seal(index, rows, ...)` reads and hashes the switched-away original file.
`flash_stores(image, preimage, index)` derives a separate exact ordered DRW
oracle from the pinned R2-A bytes and full physical envelope preimage.

Contracts: successful intermediate segments have zero Close calls, contiguous
AP sequence/monotonic timing, matched native values and target word/chunk frames,
and exactly the planned stores. State carries across segments. Unknown TAR at
a conservative 1KiB boundary requires an explicit reload; an observed read does
not justify guessing the hardware wrap. Every new segment's first DP/CSW/TAR
reads must equal the sealed predecessor's last three reads. Final closure needs
one real Close and restored AP state, and rehashes all originals. The host gate
cannot grant missing device ownership, physical qualification or user authority.

| Case | Required result |
| --- | --- |
| Complete intermediate segment | Advance exactly one index, no synthetic Close |
| Blank/truncated log, partial AP or target frame | Latch failure; next begin rejected |
| Jointly changed journal/native payload outside independent store plan | Reject |
| Clock/sequence/bank/boundary-state drift | Reject and retain prior cursor state or failed gate |
| Current file changes during audit, or old original changes by final closure | Reject |
| Complete final segment without one Close/restored AP | Reject |

Initial `.cache/p34-mutation-audit-tests1` passed seven HOST_ONLY methods in
6.618s. Tests exercise real Sector/Words/JournalSDK composition at indices
0, 1, 223, 224 and 302, ordered store reconciliation and actual suffix bytes,
plus the negative classes above using explicitly synthetic in-memory SDK logs.
This is not physical mutation logging qualification; independent review is
pending at this addendum. Correct integration must switch the SDK file on the
same connection, put post-switch AP state reads in the new segment, finish the
old segment audit, and only then allow the next target operation. Merely hashing
files after all writes, or fabricating Close records to reuse the old complete
session auditor, is not that integration.

Remaining root work is the complete source-bound coordinator: fresh halt/media
ownership and full BCB capture, durable same-session preimages, audited serial
sectors, exact C-derived inactive-record commit, complete final integrity and
fresh Boot/reset/R2-health exit. The destructive scope from 26.1 remains held.
The historical NOR SDK gap remains false, recovery is not complete, and no new
OTA speed, commit, push, release or Boot activation is claimed.

#### 30.1 Consolidated Audit Repairs And Original-Tail Compatibility

Independent review reproduced three gaps in tests1, retained as historical
evidence: missing native read values could match two null journal fields;
intermediate DP CTRL/STAT drop/reacquire writes were not independently bound;
and a final Close entry alone did not establish AP restoration or completion.
They are repaired together in `.cache/p34-mutation-audit-tests2`: ten passing
methods and 77 current input/snapshot bindings. Independent re-review closed
P30-READ, P30-DP and P30-FINAL and found no new blocker in this batch.

Every read now requires exactly one native uint32 value, with nonboolean
uint32 journal/Words fields and operation-appropriate read/write payloads.
`expected_dp_writes=()` denies CTRL/STAT writes by default; setup or final
restore must supply its independent exact ordered sequence. These logical
debug requests are not the J-Link board's physical 3.3V supply controls.
Final verification additionally requires native TAR/CSW/DP readbacks after
their last relevant changes, exact `metadata.original_dp`, an actual SDK
`Closed` marker and `native_closed is True` from the enclosing close receipt.
Writing the desired TAR without reading it back is insufficient.

The reviewer reused the frozen P28 original SDK/events/worker hashes, carried
the real prefix state and sequence, and validated its final seven AP calls
without renumbering or a synthetic Close: TAR E000EF38 write/read, CSW 23000052
read, DP 10000040/00000040 writes with 30000040/00000040 readbacks, actual
JLINK_Close and `T565C 097:837.264 Closed`. The final sequence is 80360, with
the original worker close_returned=True. This confirms compatibility with
existing physical evidence; it is not a new hardware test or mutation license.

### 31. Same-Connection Online Switch Integration

`recovery_confirm/online_log.py` adds the log-switch controller around the
reviewed gate, not the full installation coordinator. Its `emit` owns the
JournalSDK/Words event partition. `switch(...)` first disables target admission,
rejects partial AP/target frames, reads the old DP/CSW/TAR tail, calls the
existing Dap SetLogFile path once, places the three post-switch AP-only reads
in the new segment, checks state equality, then seals/audits the old original.
Only after successful sealing does it begin the next segment and make
`target_allowed()` true again. Every future physical writer must intersect
that predicate with its own media/context/ownership checks; this class is not
a substitute for them.

An ambiguous SetLogFile return, missing old log, changed AP state, audit/hash
failure, malformed frame, busy AP proxy or clock/journal failure permanently
inhibits subsequent target operations. No retry, reconnect or automatic native
Close is performed in that error path. The outer owner remains responsible for
its qualified close/retained-state handling. `prepare_close()` separately
inhibits writes; `finish(...)` obtains native_closed from the actual Dap
close_returned field, not a caller-supplied constant.

Initial `.cache/p34-online-log-tests1` passed five HOST_ONLY methods, including
real Words/JournalSDK/SealedGate composition through an independently logging
in-memory SDK, normal complete closure, delivered switch error, old-log loss,
state change, partial frame/native-busy rejection, exhausted/invalid timing,
failed event persistence and absence of a native close return. No physical
connection was opened. Independent integration review is pending here.

The newly surfaced long-operation consequence must carry into the still-missing
full coordinator: `Observation` is intentionally bounded to at most 600s and
cannot be reused for media reads throughout a multi-hour Flash sequence. Use a
separately scoped current-phase read window on the same already-owned Dap,
with a finite global supervisor deadline and explicit post-mutation no-resume
state. Do not silently extend a spent observation or reconnect as a timeout fix.

Root restated the exact pending 26.1 App/A64/verified-old-Boot-reset scope to the
user, including the larger old-Boot fallback extent and its collateral risk.
No reply is recorded at this addendum. Independent host work continues; that
question, general continuation, and these host tests grant no destructive
admission by themselves. Boot replacement and replay of NOR provisioning remain
outside this scope.

#### 31.1 New-File Head And Normal-Close Admission Repairs

P31 review reproduced two integration gaps while the original five tests still
passed: a healthy SetLogFile return and complete old log did not prove that the
new file was recording, and prepare_close omitted the complete-frame precheck.
They are repaired together in `.cache/p34-online-log-tests2`, seven passing
HOST_ONLY methods and 81 current input/snapshot bindings. Tests1 is preserved.

After sealing the old file, `verify_head()` copies the accepted cursor state
without advancing the real cursor, reads the actual active new file, and
requires a stable nonempty prefix of at most 64KiB containing exactly the three
post-switch AP state calls. Those calls must match the new journal and old
tail, with no target read/write. The prefix is hashed before and after parsing.
Missing, unreadable, unflushed, partial or mismatched raw heads fail closed;
there is no SetLogFile retry or target calibration write. Tests lose only the
new sink while preserving the old valid log, and verify that no second target
store is allowed. Physical visibility/flushing of an active SDK prefix remains
unqualified until a separately bounded read-only integration observation.

`prepare_close()` now inhibits target operations first, requires at least 60s
of remaining close allowance, and checks complete AP and Words frames before
returning normal-close admission. Pending chunk, pending word store, pending
AP call and a 59s allowance all fail before native close or DP restoration.
Failure does not eliminate the outer owner's separate emergency native-close
and uncertain/retained-state responsibilities. Independent re-review of this
successor batch is pending at this addendum.

#### 31.2 Bug Analysis: Evidence Must Precede Admission

1. Root cause category: cross-layer contract and implicit assumption. An SDK
   return or journal state was mistaken for evidence in the original log file.
2. Earlier fixes: P30 repaired sealed-file parsing correctly, but that did not
   cover the new active sink or admission to normal close in P31's new layer.
3. Prevention: uint32 values, independent DP/store plans, final native readbacks,
   Close completion and the active raw head are now explicit runtime checks;
   regressions corrupt raw and journal separately and together.
4. Systematic expansion: the future install/reset coordinator must inspect its
   proof before granting the next write or release, not discover missing proof
   in a final report. Error-path native Close must not imply verified recovery.
5. Knowledge capture: these executable contracts and negative oracles are kept
   in this existing task note because this repository has no .trellis tree.
   No new governance workflow, commit, push or historical evidence rewrite is
   authorized or performed by this documentation update.

#### 31.3 Independent Re-review And Output Boundary

Independent re-review closed P31-HEAD and P31-CLOSE-FRAME with no new blocker
in this HOST_ONLY batch. All seven tests, 81 inputs and 81 snapshots matched.
The reviewer independently repeated both new negative methods and the normal
composed path. It also checked cursor isolation: after a switch the sealed
cursor remains at sequence 8, while the temporary head verifier and real
JournalSDK reach 11. Active-prefix verification does not consume the later
sealed segment's calls. The 60s close allowance is a host prerequisite, not
physical timing qualification.

Intermediate output audit `.cache/p34-recovery-output-audit2/result.json`
checked 25 generated trees and 3393 files, including all inherited ports,
preflight, read-log, GPIO/AP and runtime-budget outputs plus online-tests1.
All resolved inside the project; no external writes, PowerShell or cleanup
were selected in this continuation. A successor boundary audit includes
online-tests2 and these final note changes. No native hardware process was
started, and no App/EEPROM/Boot/NOR write or new OTA occurred in this batch.

Next root action remains complete recovery-coordinator implementation and its
source-bound integration validation. The additional actual App/A64/reset
scope requested above is pending; even approval would not qualify missing
ownership, fresh full preimages/BCB, physical logging, reset or R2-health gates.
Do not mistake these closed host batches for a runnable admitted installer or
for completed group16 performance work.

### 32. Explicit Successor Authority And AP-Only Log Visibility Cell

The user replied to the exact preceding App/A64/reset scope question:
"If you need authorization from me, I grant it now." This grants the requested
direct App envelope [0x08010000,0x080A7800), exact preservation of its final
964B, only the unchanged original C transaction's inactive A [0,64) record,
and verified completion followed by reset through the retained original Boot
to R2. The disclosed unintended-reset/old-Boot fallback risk remains. It does
not authorize Boot replacement, NOR reprovisioning, arbitrary EEPROM fields,
J-Link supply interruption, commit/push/release or new external filesystem
paths. Technical qualification remains separate from this now-resolved scope.

The immediate finite cell is deliberately smaller than another image capture:
`.cache/p34-online-probe1`, using `p34_online_log_probe.py`. One source-bound
Native/Dap/Observation connection performs AP/DP register setup and identity,
one live SetLogFile switch, actual active-prefix visibility and two-segment
closure. No target memory read/write, halt, reset, FIFO, Flash or EEPROM access
is available. Existing exact native SEGGER history/config authority applies;
all controllable files, snapshots, logs and host directories remain in-project.

The worker has 90s and the owned parent 120s. DLL/setup must leave at least
80s before connection, and normal close requires at least 60s remaining.
DP logical request setup/restore comes from the original Dap state, independently
of the journal. Failure preserves the outcome and attempts the outer native
close once; if an online error latches the AP proxy, it cannot claim restored
AP state merely because Native Close returned. There is no retry or escalation
to target writes to make a missing active log appear.

`.cache/p34-online-probe-tests1` passed four HOST_ONLY methods using the real
Native/Dap/Observation/JournalSDK/OnlineLog classes and an independently logging
in-memory native SDK. They cover normal no-target-access closure, lost new
sink with one native Close but no false AP restoration, uncertain Close with
no retry, and six offline raw/head/closure mutations. Offline audit also binds
the exact observed active-prefix byte length/hash to the beginning of the
original final SDK file. Independent review precedes physical execution.

Successful execution would qualify active-prefix visibility for this AP-only
cell, not physical long-mutation logging, App installation, EEPROM commit,
fresh Boot exit or OTA throughput. It does not repair the historical NOR SDK
trace gap. No new hardware operation has run at this preparation addendum.

#### 32.1 First Physical Cell Failed Closed On SDK File-Close Grammar

Independent review admitted the AP-only cell after checking all four tests and
119 current inputs/snapshots. The owned cell `.cache/p34-online-probe1` then
closed at 2026-10-05T22:13:05.041Z with exit 1, no timeout, 0.944054s. It did
not qualify active-prefix visibility. Its failure is preserved, not retried
with unchanged code or renamed as success.

The original sdk-000.log shows the distinguishing real V8.18 grammar:
`JLINK_SetLogFile(...)` followed by `T5270 000:115.893 Closed`. This is the
old log file closing, not a native probe Close. The initial parser rejected it
as an unpaired native Closed marker. sdk-001.log then contains the three
actual post-switch AP reads and, later, a real `JLINK_Close()` / Closed pair.
The online failure latch blocked the normal AP-restoration attempts, while
Native Close returned once. tar_restored/csw_restored/dp_restored remain false;
the native AP error and the original failed result remain explicit.

`.cache/p34-online-probe1-reconcile1/result.json` independently binds both
original logs, journal, plan, worker and parent, and verifies all 119 original
snapshots without demanding current-source equivalence after the fix. The
reconciled inventory is 13 old-segment plus three new-head AP/DP calls, zero
target reads or stores, one file close and one completed native Close. The last
actual AP samples were DP F0000040, CSW 23000052, TAR E000EF38; the initial DP
was 00000040. These are pre-Close observations, not proof of post-Close state
or successful restoration to 40. No MCU health, halt/reset, NVM access, active
head-read execution or historical NOR-gap repair is claimed. Native history
hashes were unchanged and the parent found no remaining debugger process.

#### 32.2 Grammar Repair And Bounded Successor

The repair gives Cursor an explicit `switched_away` phase. A sealed non-final
file requires exactly one SetLogFile / file Closed barrier, rejects any AP
call after that barrier and cannot contain native Close. A final file instead
requires its real native Close / Closed pair and may not contain SetLogFile.
An active prefix permits neither close. The Closed text is never classified
without its operation context, and the old complete-close requirements remain.
Mocks now render the observed file-close grammar instead of omitting it.

Successor host evidence is `.cache/p34-mutation-audit-tests3` (11 methods),
`.cache/p34-online-log-tests3` (seven), and
`.cache/p34-online-probe-tests2` (four), all normally closed. Previous receipts
and the failed physical cell are unchanged. Current runner bindings point at
these new source-bound receipts; changing that binding is not a retroactive
revalidation of old evidence.

The proposed successor `.cache/p34-online-probe2` has the same AP-only scope and
90s/120s worker/parent limits. It first observes the actual new connection's
original DP. If that is F0000040, the already host-tested branch preserves it;
it does not silently relabel the previous connection's missing 40 restoration
as completed or forcibly remove logical requests. This is a changed-source
discriminating observation, not replay of a NOR/App/BCB operation. Independent
re-review of both repair and failed-cell reconciliation precedes execution.

#### 32.3 Executed AP-Only Successor

`.cache/p34-online-probe2` closed normally at 2026-10-05T22:39:35.330Z,
exit 0, no timeout, 2.5477416s. The original SDK audit and independent
reproduction agree: 23 AP/DP calls, zero target reads/writes, one live file
switch and one completed native Close. Fresh initial DP was 40; exact writes
were 50000040, 10000040, 40, with final DP/TAR/CSW readbacks 40/E000EF38/23000052.
The verified active prefix was 692B, SHA-256
`b6093975bc63d8a690eb9e450ff73b9996d8fc9fc538094e754a44ec7b3912f4`.
History hashes were unchanged and no residual debugger was recorded.

This qualifies active-prefix visibility only for this SDK/AP-only run. It
does not observe MCU health, qualify long mutation logging, repair probe1,
explain the DP change between sessions or repair the historical NOR trace gap.

### 33. Held Observation And Stable Pair Adapters

`held_window.py` provides <=60s passive STATE_WORDS windows on an existing
owner, intersecting every native guard with the nonincreasing global budget.
It cannot renew a spent original Observation, connect, reset or write. The
HELD-GLOBAL regression shrinks remaining time to 0.01s, then a 0.02s first
CSW call prevents any target access. `.cache/p34-held-window-tests2` passed
seven methods/81 bindings; independent review closed the finding.

`read_pair.py` seals page/ACK methods and permits exactly four64B reads in
0/64/0/64 order. Each completed read invokes the archive/seal callback before
the next; callback errors stop without replay. `.cache/p34-read-pair-tests1`
passed five methods/80 bindings and independent review. Stable pair bytes
remain neither C confirmation nor reset qualification.

### 34. Flash Sequence Integration And Boundary Repair

`flash_sequence.py` serializes all303 fixed sectors against the exact captured
original envelope, retaining the real964B suffix. Independent review found
SEQ-BOUNDARY: final log sealing could lose owner/reserve but still return
success. The repair rechecks native-return, sector-return, seal-return,
emit-return and final handoff, with the correct incremented log index. A
single bounded guard covers the entire switch/seal/active-head operation,
not just Flash native calls. Same-Dap identity and actual clean AP-only head
are required before the first sector; entry traffic must already be sealed.

`.cache/p34-flash-sequence-tests4` passed nine methods/82 bindings. Independent
review closed SEQ-BOUNDARY and SEQ-INTEGRATION and reran five affected methods.
Two real Sector/Words/JournalSDK/OnlineLog/SealedGate operations match exact
independent stores, preserve all bytes after4096B, and deliberately stop before
sector2. Old-file/new-head failures prevent the following sector. Full303
success remains an orchestration model, separate from the earlier303 runtime
model and five representative real-Sector port tests, not physical execution.

Failed tests2 (fixture TAR support/time handling) and tests3 (test-only repeated
string-concatenation timeout) remain unchanged. tests4 replaces only that
in-memory log accumulation with fragment appends; production parsing is not
relaxed. Configured28800/300/3600s bounds are not measured write timing.

### 35. EEPROM Segmented Transaction Preparation

`eeprom_sequence.py` adds an independent master-edge store oracle and a wire
bound to the original C Draft's inactive A. Each complete read/page STOP/ready
ACK is archived and sealed before the next operation. Native calls intersect
operation, wire and global downstream-reserve budgets; settled page STOP is
not confused with completion, and the original5ms/ACK rules remain unchanged.
No new connection, Flash/NOR payload or reset capability exists.

`.cache/p34-eeprom-sequence-tests2` passed seven methods. The unchanged original
C transaction drives all30 operations through real Words/Pins/slave models,
with per-segment independent native store comparison. An additional real
JournalSDK/OnlineLog/SealedGate composition covers page/ACK/read8. Archive and
seal failures stop without replay; final owner/reserve loss cannot report
confirmation. Independent review is pending at this addendum. These are host
models, not physical EEPROM write qualification.

### 36. Fresh NOR Capture Preparation

`nor_capture.py` avoids the old60s reader and byte/no-increment JEDEC FIFO.
It uses bounded word/increment Words, exact SR1/SR2 status reads, /12 bypassed
XIP, fixed retained region hashes and32KiB archive/seal boundaries. OPEN/CLOSE
MMIO stores are checked against independent phase sequences; no payload write
opcode, FIFO data read or mapped-memory store is permitted. Failure retains
the changed controller state rather than performing speculative cleanup/reset.

`.cache/p34-nor-capture-tests1` passed five methods, including the complete
626688B recovery region through real Words/JournalSDK/OnlineLog/SealedGate
with simulated time exceeding60s, exact archives and passive configuration
restoration. The other three fixed regions have not yet had a complete model
run. Independent review is pending. No fresh JEDEC/package identity, physical
capture, installation or historical audit repair is claimed.

The complete physical coordinator and source-bound R2 runtime-health collector
remain unfinished. No App/EEPROM/NOR/Boot payload operation, MCU halt/reset,
new OTA, commit, push or release was executed in these host batches. Current
MCU health remains the last P28 observation, not a new observation. App/A64/
original-Boot-reset authorization in section32 is resolved and must not be
requested again; group16 Boot replacement remains outside that scope.

#### 35.1 Archive Bound And Independent Review

EEP-ARCHIVE-BOUND identified that a direct archive callback could block beyond
the downstream reserve. Wire now guards the archive with the minimum of300s,
global-minus-reserve, EEPROM and Words allowances, then retains the post-call
boundary check. `.cache/p34-eeprom-sequence-tests3` passed eight methods/82
bindings. Independent review closed the finding and replayed both the late
archive/retained STOP negative and the real page/ACK/read8 logging composition.
Archive time does not move stop_upper: elapsed logging time legitimately
counts toward the minimum write-cycle wait before the sole ready ACK.

#### 36.1 NOR Review And Matching Archive Bound

The same archive guard was added to NOR Capture before physical integration.
`.cache/p34-nor-capture-tests2` passed six methods/85 bindings; all six were
independently replayed, including full recovery capture,21 sealed segments,
14 OPEN and14 CLOSE control stores, exact bytes and passive configuration
restore. No blocking finding remains in that tested recovery-region scope.
All four region lengths/hashes match retained files; full model execution of
candidate-backup/tail/staging remains explicitly unperformed. This is not a
fresh hardware capture or a replacement for the historical failed SDK audit.

### 37. Exact R2 Runtime Health Monitor Preparation

`r2_health.py` binds the finalized R2-A and original map SHA, checking eight
diagnostic symbols and their sizes. It is a passive existing-Dap capability,
not a release/reset entry. It permits at most120s to reach runtime VTOR plus
HAL/SD/diagnostics-ready and the App's CONFIRMED state snapshot, then requires
at least30s of host-observed main-loop, tick and watchdog-feed progress with
stable health epoch and no reset/halt/lockup/fault. Full runtime524B vectors
and96B identity header are checked before and after the stable window. The
final real log audit must contain zero target writes. Physical BCB reading
and complete installation remain outside this monitor's claim.

`.cache/p34-r2-health-tests2` passed four methods using real Words/JournalSDK/
OnlineLog/SealedGate and an in-memory running target. Specific failure oracles
cover reset/halt/lockup/fault, SD/state/epoch loss, stalled tick/main-loop/feed,
permanent early phase, mismatched identity/map, early sleep and lost logs.
tests1 retains a floating-point subtraction false-positive in the minimum
sleep check; tests2 compares the absolute deadline and asserts the intended
negative paths, rather than accepting any unrelated exception. Independent
review is pending. No R2 health has yet been observed on the physical board.

#### 37.1 Fixed Readiness Deadline Reviewed

R2-READY-DEADLINE found that a ready sample could be accepted after120s because
the old test came after the ready branch. The fixed start+120 deadline is now
checked before every sample and after its return, before accepting readiness.
`.cache/p34-r2-health-tests3` passed five methods/92 bindings; independent
replay closed the issue with normal, late-ready and deadline-crossing cases.
Neither late case creates the first stable-health sample or a final seal.

### 38. Complete Body And Host Integration Candidate

`recovery_confirm/install.py` now composes the real components in fixed order:
fresh WFI/owner entry, full original internal archives, stable BCB/C draft,
four NOR region archives, fresh media state,303 Flash sectors, the unchanged
C-driven30-operation EEPROM transaction, complete internal/NOR revalidation,
fresh media and stable final pair/C observation, original Boot reset/catch,
separate release, and the R2 health monitor. The body owns719 segments after
the separate setup segment, leaving one final-close file:721 preflighted SDK
positions total. It never resumes the original WFI context, including failures.
Returning READY_FOR_FINAL_NATIVE_CLOSE is not final native-close acceptance.

The first body review identified INSTALL-STATE-RESERVE: the short Window had
received global remaining time without subtracting the parent's90s reserve.
That connection now receives self.left()-90; the new regression tightens
global remaining to90.01s and proves a <=0.01s guard, one CSW call and no later
target read/seal after the injected0.02s return.

The body tests were extended, in one integration batch, beyond the original
six-method orchestration/model scope. Real native-model entry/control/owner
now reaches the new raw-log audit with exactly15 permitted stores; a damaged
seal prevents internal capture. Real complete internal capture and real GPIO
pair reads bind to their actual segments; their first-seal failures stop.
Two adjacent real Flash sectors run under parent delegation and hand the
advanced index back, with both normal deliberate stop and bad-log coverage.
Real Exit reset/catch, seal, release, seal and Monitor compose with exactly
7 reset-phase and6 release-phase stores; either seal failure prevents the next
phase and the terminal helper cannot be replayed. These remain host models,
not a physical complete303-sector campaign. tests3/4 passed11/12 methods.

`p34_install_recovery.py` adds the contained host candidate:29 exact archives,
per-block flush/fsync/readback hashes, separate source-bound setup and normal
or error-retaining native close, lossless BCB-byte JSON, and progress records.
The configured worker/parent limits are28000/28200s, with20GiB minimum project
drive evidence margin. They are configured bounds, not qualified worst-case
Flash/EEPROM timings. Failed/uncertain cells are never replayed. Unchanged
already-high DP requests are reported as preserved only after the final raw
audit, not relabelled as dp_restored. Native history uses only the previously
approved SEGGER directory; all chosen other outputs remain project-local.

The first host-only five-method run passed, including complete durable file
sets, preserved partial archives, actual Native/Dap/Observation/log-close
composition with a body stand-in, close/archive/body failure, and binary result
serialization. Final host/source binding now also requires the current body
test receipt. Successor body/host runs and independent integration review are
in progress. The candidate has not been invoked with execute or worker.

Output audit4 covers47 selected inherited/new trees and5373 files, before
the later readiness/body/host additions. A successor must include those
additions before final physical admission or closeout. No physical App,
EEPROM, Boot or NOR programming, halt/reset, supply change or new OTA occurred
in this continuation. Recovery and group16 speed measurement remain incomplete.

### 39. Admitted Physical Recovery Cell

Independent review closed INSTALL-STATE-RESERVE and all requested real-component
seams. body6 has12 tests/469 inputs and snapshots; host2 has5 tests/476 bindings.
Nine affected methods were independently replayed without filesystem mutation,
and all29 actual host-test archives were checked. No blocking host issue remains.
The proposed cell is `.cache/p34-recovery-install1`, confirmed absent before
admission. This is one finite recovery transition, not an OTA benchmark or
permission to replay any failed/uncertain operation.

| Field | Bound Plan |
| --- | --- |
| Operator/root | Codex root, sole physical owner; D:\github\my\E-Track |
| Authority | Section32 exact App/A64/retained-original-Boot-reset grant; existing SEGGER native history exception only |
| Device | Existing USB probe123456, SWD1000; direct J-Link3.3V/GND supply must stay connected |
| Inputs | Original Boot65536B `a63346db...`; original App30275 `4d248fd7...`; exact620544B preimage `b777d7ff...`; R2-A619580B `7445ef63...`; historical BCB pair `57282afe...`; all four retained NOR regions |
| Pre-erase proof | New WFI/media/software/master ownership; full internal/BCB/NOR captures, durable archives and exact native-segment audits |
| Mutation |303 exact2KiB App sectors in [08010000,080A7800), preserving964B; only original C inactive A64 transaction; zero Boot/NOR payload writes |
| Final proof | Full internal/NOR/BCB revalidation, fresh media, original Boot reset/catch then independent release, >=30s R2 health, actual final native Close/audit |
| Limits |28000s worker,28200s parent; existing phase/port limits and downstream reserves;20GiB minimum project-drive free space |
| Failures | Preserve original logs/archives/uncertainty; no retry, reset fallback or old-WFI-context resume; retain debugger requests if core state may be held |
| Evidence |721 preflighted native logs,29 exact archives, source snapshots, events/progress, plan/worker/parent and final source-drift check |
| Explicit exclusions | Boot group16 replacement, NOR provisioning replay, other EEPROM bytes, supply changes, external cleanup, commit/push/release |

The fixed fallback risk remains: an unintended reset can let the original
Boot write through080A8000, beyond the direct envelope. That disclosed risk is
not used as an automatic exit. Configured limits and the earlier inclusive
GPIO extrapolation suggest hours of host-driven work, not qualified physical
write timing or a new performance result. The physical cell has not completed
at this admission record. After closure, independently recalculate log/plan,
all29 archives, original C BCB oracle and the post-release health window without
repeating device operations.

Prestart output audit5 covers56 trees/8307 files and finds no selected external
write. USB123456 is present and no debugger process is listed. This note is the
only subsequent source-document delta before the planned cell; the tested
implementation sources and receipts are unchanged.

## 40. Failed Installation Entry And Retained Successor

Physical cell `.cache/p34-recovery-install1` closed at2026-10-06T01:22:14Z,
exit1, elapsed9.647523s, without timeout. It failed with
`DMA endpoint/count changed` after acquiring the original App WFI halt but
before internal archives, GPIO transactions, NOR commands or payload writes.
The App remains intentionally halted: PC08045A78, MSP20057FA0, xPSR21000000,
CONTROL4, FAULTMASK/BASEPRI/PRIMASK0, VTOR08010000, FPCCRC0000018. The comparator
is disarmed and WDT halt pause remains1000. There is no current running-health
claim. No reset, release or supply change occurred.

Offline `.cache/p34-failed-install-audit1/result.json` and the independent
reviewer's original-log reconciliation agree:1584 native AP/DP calls,513 target
reads,15 target stores, one actual native Close. Stores are only PAUSE1000,
WFI comparator arm/disarm and three groups of four DCRSR read selectors.
There are zero App/EEPROM/NOR payload stores and no AIRCR/DHCSR store. TAR and
CSW have restoration readbacks. Original DP40 was intentionally retained at
F0000040; `dp_restored=false` remains explicit. The audit's separate retained
final-readback oracle does not rewrite this as normal DP restoration, and does
not repair the historical NOR SDK gap. SEGGER history hashes are unchanged.

The rejected display DMA address200171E0 is the exact original executable's
`lv_disp_buf1`; the old hardcoded200045E0 is `lv_disp_buf2`. The original map
and nm symbols give size12C00 for each. Frozen lv_port_disp.cpp65-69 passes both
to LVGL; HAL_Display.cpp75 assigns the supplied buffer to DMA maddr. Full App
bytes match the build/ELF extraction outside the96B finalized header. This is
not permission for arbitrary addresses within either buffer. The installation
successor qualifies only those two exact bases, retaining zero DMA counts,
fixed peripheral endpoints, control/clock/WDT/software-owner checks. Historical
`recovery_entry/host_nor.py` remains unchanged.

Preferred successor is a new retained-context installation cell, not a replay
of Fresh Entry and not an original-App resume. Its entry first preserves debug
requests even if the first read fails, then checks exact controls/context,
two fresh stopped media observations and software owners, followed by a sealed
12-selector-only entry segment. All original fresh internal/BCB/four-region
NOR preimages and post-write validation remain mandatory. At this note the
successor is implemented but still undergoing host tests and independent review;
it has not operated hardware. Existing App/A64/original-Boot authority applies;
Boot replacement, NOR reprovisioning and other EEPROM bytes remain excluded.

No new throughput measurement exists. Group16's approximately5.64s saving is
still projected, not measured. This work repairs the recovery prerequisite.

### 41. Retained Successor Admission

RETAIN-CLOSE-LIFECYCLE found two host failures before successor hardware use:
an optional DP read could skip Close, and Observation.connect could close before
the outer retained policy. The unified close policy is now installed before
connect; optional retained readback is enclosed in try/finally to the original
one-use Close. Independent fault replay confirms exactly one native Close,
retained F0000040, no false restoration, no target access and no post-Close DAP
read. Normal and uncertain-close regressions remain correct.

Current body8:16 tests/489 bindings; host4:6 tests/496 bindings. Both current
sources and snapshots were independently verified. body7/host3 remain preserved
as superseded; the exact failed-cell audit remains valid. Output audit6 covers
2540 files/1602 directories, with no selected external output and unchanged
native SEGGER history. This admission note is the subsequent documentation delta.

Execute the new `.cache/p34-recovery-install2` cell under the same user-authorized
App envelope/A64/original-Boot scope as section39, with only the entry changed to
the independently reconciled install1 retained context. No fresh WFI rendezvous,
App resume, NOR provisioning replay or Boot replacement is included. Sole owner
is root; worker28000s/parent28200s, per-native bounds and all downstream reserves
remain unchanged. All29 fresh archives and721 logs are preflighted under the
project; free space is approximately110GiB, above the20GiB entry minimum. Probe
123456 is present without a competing debugger. Sources must not change while
the worker runs. A failed or uncertain outcome requires closed-state analysis,
not replay. Full offline reconciliation remains required after actual closure.

### 42. Physical Partial Flash Failure, No Automatic Replay

install2 started2026-10-06T03:12:56Z and closed FAILED at03:48:15Z,
elapsed2119.917293s, parent exit1 without timeout. The retained entry passed;
independent raw reconstruction found13 setup AP calls and1543 entry calls,
507 target reads and exactly12 DCRSR selector stores. All three contexts and
both media/owner samples matched. The new connection initially observed DP40,
then requested50000040 and observedF0000040. A pre-Close retained DP observation
must not be described as proof that the requests persist across native Close.

Complete original Boot/envelope and A/B/A/B passed. All four NOR captures
matched and sealed (candidate/backup2097152B, recovery626688B, tail421888B,
staging2097152B). FLASH started03:46:54Z. Sectors0 and1 were programmed,
fully read back and audited at03:47:27Z and03:48:01Z. Sector2 failed with
`Flash completion unknown at operational deadline`; the App is PARTIALLY
UPDATED, not a runnable original30275 and not a complete R2. EEPROM pages0,
reset/release false, supply unchanged. No old-App resume/reset is permitted.

The final payload store was08011224=8965FF72, native return0. The subsequent
SR40023C0C read was20: EOP set, BUSY/errors clear. There is no following readback
of that payload word and no relock store. The raw SDK and host journal show
approximately581ms between native calls during the held-owner check, while
the delayed native TAR call itself was approximately1.137ms. Status was read
approximately635.56ms after payload return, beyond the500ms host operational
deadline. This supports host-observation lateness, NOT a proof of the Flash's
physical completion latency and NOT permission to mark the pending word verified.

Native Close returned; TAR/CSW restored with readbacks; DP restoration was
deferred and remains explicitly false. All496 execution sources remained
unchanged at closure, SEGGER history is unchanged, and no debugger process
remained. Original sdk000..195, full events, before archives and failed receipts
are retained. Next: reconcile the exact partial native store prefix, then a
bounded read-only retained-context/controller/full-envelope observation. No
pending word, erase, reset or complete installation may be blindly replayed.

The independent post-close auditor is additive only and has never been a
worker dependency. Its first review found physical wire-boundary and current
input binding gaps. Those fixes have7 passing host tests in
`.cache/p34-install-offline-tests3`; existing closed BCB segments23..26 also
decode with the stricter physical START/STOP witnesses. Earlier tests1/2 are
preserved. A transient overly broad imported-module inventory rejected an
unused historical NOR writer; required roots now name actually consumed
helpers, while every frozen execution input is still rehashed before/after.
The latest auditor review remains secondary to this real partial-Flash state.

Recovery is incomplete and no new OTA throughput result exists.

### 43. Read-Only Partial-Flash Settlement Admission

The complete failed-cell prefix audit passed in
`.cache/p34-flash-failure-audit1`: all196 SDK logs, before archives/physical BCB,
two complete sector readbacks and exact287-store third-sector prefix. The
independent reviewer verified502 inputs and independently reconstructed the
620544B expected envelope, SHA256
`dadadad5ea6d0a5af0227880dea37960486dc8f340e7b7dc93700d5e88e0985c`.
It is still a HOST reconstruction, not physical observation. The third sector
had138 words submitted,137 individually read back, with1496B expected erased tail.

Admitted next cell: `.cache/p34-flash-settlement1`, root as sole operator,
worker180s/parent240s, original J-Link supply unchanged. It reads held/reset/pause,
two-bank SR/CTRL/metadata, exact retained CPU context and affected6KiB; only8
DCRSR read-selector stores are permitted. No status clear, controller mode write,
relock, payload, erase, EEPROM/NOR transaction, reset or resume is included.
All5 native logs and affected.bin are preflighted within the project; native
history/config exception remains the same approved SEGGER directory.

SETTLEMENT-WFI-SCOPE adds only08045A78 to the seal scope. SETTLEMENT-CALL-BOUND
wraps Control initial/context, archive and seals in port/global-minus60 guards
before/after each call. tests3 has6 tests/505 current input/snapshot bindings,
independently verified, including actual Dap/Control/Words scopes and late-return
failure before any next selector/chunk/seal. Both findings are closed; earlier
test outputs remain preserved. No settlement hardware result exists at admission.

Future no-erase remainder/polling classes are separately prepared and have3
host tests, but no device entry or write qualification. They are not part of
this read-only cell. A future writer may only begin08011228 after actual settled
readback matches, with no replay of the first2 sectors or preceding138 words.

### 44. Physical Settlement And Third-Sector Finish Admission

settlement1 completed at2026-10-06T05:06:27Z, elapsed38.5317889s, exit0,
without timeout. The closed native logs independently reconcile3229 AP calls,
1885 target reads, exactly8 DCRSR selectors and one actual Native Close.
The retained CPU context is unchanged; both-bank controller observations match
the failed installation. Physical affected.bin is6144B, SHA256
`3e23d523d781ec11c454710ec66e6e42ca3bafd8fb0fa7e99fbf9a33d7808142`.
It freshly verifies08011224=8965FF72 and the1496B erased remainder. Only this
6KiB was re-observed; the full expected envelope remains a host reconstruction.
No repair/reset/resume or EEPROM/NOR operation occurred. DP restoration remains
false by the retained-close policy; source and approved SEGGER history hashes
are unchanged, and no debugger remained.

FINISH-HOST independent review is DECIDED with no blocking findings for host
SHA256 `fc294c0de7b5253530c37f48ab3d34a6c2b75974c8d98980224dca19e98b4066`.
finish-tests3 has5 tests and519 matching source/snapshot bindings. Additional
review probes cover7 budget cases and6 mocked worker-lifecycle cases. These are
host evidence, not proof of physical completion. The frozen offline auditor's
terminal-idle wire gap remains open and requires an additive strict successor;
do not modify that source dependency in place. It does not affect this cell's
no-EEPROM scope.

Admitted cell: `.cache/p34-flash-finish1`, sole operator root, same authorized
App boundary and unchanged J-Link supply. Fresh retained identity/capacity,
context/controllers and exact6KiB must pass before the exact750-store suffix:
374 status clears,374 new words starting08011228, then CTRL0/CTRL80. No erase,
prefix replay, EEPROM/NOR, reset or resume. Worker180s/parent240s include local
guards and60s close reserve. All6 SDK logs, receipts, source snapshots and host
environment paths are preflighted below this project; only the existing exact
SEGGER native-history exception applies. Failure requires closed-state
reconciliation, never blind replay. Successful closure still leaves300 App
sectors and the original-C A64/final-validation/reset-health sequence unfinished.
Recovery and OTA optimization are not complete; there is no new speed sample.

### 45. Third Sector Physically Complete; Full Successor Preparation

finish1 closed normally at2026-10-06T05:47:46Z, elapsed70.7684361s, exit0,
without timeout. Independent replay of all6 original SDK segments and the
native journal found26980 AP calls,6700 target reads and758 target stores:
exactly8 DCRSR selectors plus the approved750-store suffix. All374 new words
and the final2048B sector readback equal R2-A. Third-sector SHA256 is
`a3223b1b3e2aaec835c98808bfa37112ddb1f1008d901d661c8219e44c40b9d6`.
No erase, completed-prefix replay, EEPROM/NOR, reset or resume occurred.
All252 metadata samples agree; final Bank1 SR20/CTRL80 and Bank2 SR0/CTRL80.
Both observed CPU contexts remain the original paused runtime. Exactly one
Native Close completed, TAR/CSW restored; DP restoration remains explicitly
false. All519 current and snapshot bindings and SEGGER history are unchanged;
the parent found no remaining debugger. There were no late-completion events.

The first3 sectors are now complete R2-A, but the App is still a partial image
and must stay halted. The next additive coordinator retains the original asset
and C-oracle checks. It expects the R2 header with the original halted context,
separately reads/seals the3 completed sectors, captures full current internal
bytes as R2[:6144]+original[6144:], then fresh original BCB and all NOR regions.
Only sectors3..302 are erased/programmed, with ObservedSector's completed-state
polling, per-word/full-sector readbacks and the original964B collateral. The3
prefix read segments replace the3 omitted write segments; total719 body
segments and post-Flash positions496 onward stay unchanged. Original-C A64,
all final captures, original-Boot reset/catch/release and R2 health remain gates.

The additive strict auditor rejects every non-idle physical INPUT after STOP,
including high/low/high terminal sequences. Frozen legacy sources remain
unchanged. It uses the successor's exact segment layout and pins the new area's
events/plan before early prefix interpretation, checking those same versions
after delegated native audit (STRICT-PREFIX-INPUT-BINDING). First selftest9
methods had8 passes and1 test-fixture error: the Wire stand-in omitted the C
transaction's address/record fields. The failed tests1 receipt is preserved;
the fixture is repaired and a real R2-header/old-context entry seam is added.
tests2 and full integration review are pending here. No full successor hardware
has been admitted by this preparation note, and no OTA speed claim is made.

### 46. Full Continuation Admission After Finish1

CONTINUATION-INTEGRATION is independently DECIDED with no remaining blocking
findings. tests2 passed11 methods in47.252s; all536 current/snapshot bindings
match. Independent replay includes the repaired real C transaction, actual
retained Control/Dap/log entry with R2 header and old context, early evidence
drift, exact300-sector mapping and the real sectors3/4 store/seal seam. Both
strict-auditor findings are resolved additively, not by rewriting the legacy
auditor or old receipts. Reviewed host SHA256:
`2502aea13aceef504afeff60acb8ab0075d3beb00f4b7b5af5a88629486a6f91`;
strict auditor SHA256:
`2951f13dc303340ef7e33f4335543478a0b848c3537a57232c9030a1c2d153f6`.

Root admits one `.cache/p34-recovery-continue1` physical continuation using
tests2, existing App/A64/original-Boot authority and the unchanged J-Link supply.
This is not replay of install2 or finish1. Inputs bind their actual closed
receipts, original sources, all6 finish logs and exact R2/original assets.
Fresh entry must establish old halted context with R2 header,3 completed-sector
readbacks, full current internal envelope, original BCB A/B/A/B and all4 NOR
regions before writing. Only sectors3..302 are programmed; final964B are
preserved. Original-C A64 confirmation, full internal/NOR/BCB final validation,
fresh retained-Boot reset/catch/release and actual R2 health/Native Close remain
required. There is no old-App resume, Boot payload write or NOR reprovisioning.

Worker28000s/parent28200s, per-sector300s, per-native bounds and downstream/close
reserves remain finite. Failure retains the actual evidence and prohibits blind
replay. All721 SDK logs,29 archives, receipts, snapshots and host home/temp/cache
paths are preflighted below this project, with over108GiB free. Sole physical
operator is root, probe123456, no competing debugger. The only external output
exception remains native history/config under the exact approved SEGGER path.
Output audit7 covered5957 files/3639 directories and unchanged external history;
this admission note and the new physical cell are subsequent outputs. No speed
result or recovery completion is claimed before that cell and its audit close.

### 47. Offline Next-Transition Package During The Physical Continuation

The physical continuation passed its entire before-state capture and began
REMAINING_FLASH at2026-10-06T06:50:51Z. Sectors3..38 were audited by07:11:02Z;
this is progress only, not a closed-cell result. No active dependency was edited.

An independent offline preparation uses the existing exact R2-A30276 and
R2-B30277 images for a later normal original-Boot OTA, to establish an R2 backup.
R2-B differs only within the firmware header; it is not a changed-executable
workload, group16 experiment or production release. The new helper is
`Tools/ota/p34_r2_transition_package.py`. Package2 result and5 native command
receipts are at `.cache/p34-r2-ota-package2`; full.etu is294052B, SHA256
`a67ff12d91a83c7f4bf0324f98ee68c1880547f39a37f3e2137707c3aed196e0`.
Positive decode reproduces all619580B, image header validation and workspace
guards/lifecycle pass. Payload corruption, truncation, same-version and wrong
flags reject before candidate preparation. No firmware rebuild or device/network
operation occurred in package preparation.

Package1's stdlib LZMA check failed before package generation: liblzma rejects
the project's rewritten finite-size header with retained encoder EOS. Its
source and failure receipt are preserved. A read-only discriminating check
restored only the original unknown-size field and decoded the exact R2-B bytes.
Package2 uses that normalization solely for the independent stdlib cross-check;
the real encrypted package and all native tests consume the unchanged finite-
size stream. Its properties are lc2/lp0/pb0, dictionary16384B. Native workspace
peak33072B is a HOST observation, not MCU peak memory evidence.

R2-PACKAGE-REVIEW is independently DECIDED for offline qualification:13 inputs,
15 outputs and5 command receipts verified, all5 native outcomes independently
reproduced. The17-dependency compatibility bridge was recomputed by root in
`.cache/p34-r2-decoder-bridge1`:16 dependencies are byte-identical between the
historical decoder sources and R2. Only boot_crc32.c differs for the R2 nibble
opt-in. All16 table entries match four reflected CRC steps; nibble CRC matches
zlib for the actual ETU header, payload and R2-B. Source/build/Ninja receipts
are hash-bound; no regeneration, new nonce or repeat firmware campaign occurred.

Limits: boot_ok is native firmware-header validation, not physical Boot/EEPROM
transition. Recovery must first close successfully, and R2-aware sender/collector
and final verification entry remain to be prepared before any OTA. The package
does not make the route send-ready or prove throughput. Original group1 Boot is
still retained; no group16 deployment or Boot replacement is authorized here.

### 48. R2-OTA-ROUTE Design Handoff, Not Send-Ready

Independent read-only design review recommends an additive normal-transition
adapter, not entry into the historical SHA/reconnect group table. Reuse the
latest p34_sha_trial phone/service lifecycle and schema9 configuration, original
snapshot retrieval and p34_info_retry_trial.installed historical APK evidence;
recheck actual installed APK/device before use. Derive the new predecessor from
the successful closed recovery, never forge confirmed_predecessor's old OTA
chain. Preserve query/download admission before the single user Start through
Backend.observe_install, downloaded_package and finish_install_snapshot.

The minimal new checkpoint composes finalized_reader.Reader and
p34_finalized_vtor_capture with separately scoped whole-Boot and paired-R2
runtime-health reads. capture_old remains30275-only; r2_health.Monitor remains
R2-A-only (both geometry and returned version) and must not be passed R2-B as
though it were A. Every DHCSR consumer shares a persistent reset latch and
fresh connection/boot generation. Require full619580B expected image,524B active
table, stable expected header, advancing initialized runtime and no fault state.
An observed reset rejects the whole capture, even if endpoint VTORs agree.

No continuous performance trace is needed solely to establish an R2 backup.
Old p34_full_trace.Trace needs more than another allowed VTOR: epoch/channel
handling and image profiles are version-bound. Its pure timing parsers can be
reused, but no trace or old proof is relabeled as a new physical observation.
Preserve921600/window28/batch12/prefer2m, negotiated244B writes without response,
foreground/high-priority and INFO1000ms/12 attempts/500ms cadence unless a new
evidence-based parameter change is separately planned. Verify actual baud.

Before Start: recovery's actual Close, independent archive/transport audit and
R2-A health; all old hardware owners closed; exact package2 and Boot/R2 maps;
fresh idle/CONFIRMED evidence tied to the current generation; live HTTPS metadata,
phone download-byte identity, producer health, private ADB and retrieval/cleanup.
RAM state4 is not an exact EEPROM pair or sequence. After the normal upgrade,
require full R2-B/unchanged-Boot readback, fresh confirmation/health, one original
completed App snapshot and separately qualified backup-slot header/full payload
matching R2-A. App success and health flags alone do not prove that backup.
Live NOR reading needs fresh idle/mapping/owner qualification; never borrow the
halted NOR writer, force XIP or repeat OTA to repair a failed collector.

Smallest new host cases: incorrect predecessor/package/APK, early BEGIN/stale
download, header/vector/epoch mismatch or consumed reset, failed reader handoff/
Close, snapshot loss without OTA replay, and wrong/corrupt backup. Necessary user
interaction is connecting/downloading if not already done, then Start exactly
once AFTER downloaded-input admission, keeping foreground/USB connected. Unlock
or OS permission dialogs are conditional; no automatic taps, HCI setup or manual
log export is needed. These are design recommendations only: no new trial or
checkpoint implementation, phone operation or Boot-write authority is implied.

### 49. Paired Health Component And Physical Progress

The additive `recovery_confirm/r2_paired_health.py` now admits only the exact
R2-A/B hashes with their actual30276/30277 versions and unchanged reviewed map.
It reuses version-neutral sampling/identity/budget helpers, not the A-only
geometry admission or hardcoded returned version. Its consumed reset indicator
stays latched. The enclosing checkpoint must share that latch and invalidate
ownership on every reader/monitor failure. This module has no device entry and
does not establish complete image/Boot readback, physical BCB or backup validity.

`.cache/p34-r2-paired-health-tests2` passed3 top-level methods in18.209s, including
10 nested invocations of the5 original health methods for both images. The
original reset/fault/clock/readiness/identity/log barriers stay enforced; explicit
version, consumed reset and lost-owner checks pass. tests1's fixture failure
referenced nonexistent native.calls; it is preserved, and the repaired assertion
compares actual raw log bytes across refused replay. No product guard changed.
R2-PAIRED-HEALTH independent review verified97 current/snapshot bindings and
additional cross-version/unknown-image rejection. Reviewed module SHA256 is
`2729bb349b684cc57c85390c76a9b037aa66e8a168d57d44ead2bc0e7f370115`.
Whole checkpoint and trial integration remain unfinished; this is not an OTA.

Physical continuation progress, not final closure: all300 remaining sectors
were audited by2026-10-06T09:35:56Z. Original-C EEPROM operations0..29 completed
and arbitration passed at09:48:11Z. Full after-internal Boot/App/collateral
capture passed by09:51:17Z; after-NOR capture is still running. No reset/release
or R2 runtime-health result has yet been observed at this note.

### 50. Physical Recovery Closed And Strict Offline Audit Passed

The continue1 parent closed normally at2026-10-06T10:22:25.972145Z, exit0,
elapsed14719.2361356s, without timeout or remaining debugger processes. The
worker reports `R2_INSTALLED_ORIGINAL_BOOT_CLOSED`, unchanged frozen inputs,
300 audited remaining sectors,8 EEPROM pages, actual reset/release and exactly
one returned Native Close. The completed first3 sectors were verified, not
rewritten. Full after-Boot/App/collateral/NOR and A/B/A/B captures passed.
Original TAR/CSW and DP40 were restored with readbacks; unlike the preceding
halted cells, DP restoration is now true. Native SEGGER history is unchanged.

Root's `.cache/p34-recovery-continue-audit1/result.json` independently replays
all721 SDK segments and29 archives against the strict continuation layout:
`INSTALL_TRANSPORT_ARCHIVES_AUDIT_PASS`,14422680 native calls,5284330 target
reads and330539 target writes. This includes control/GPIO/Flash transactions,
not330539 firmware words. Every physical INPUT after STOP was idle. The audit
explicitly leaves `runtime_health_independently_reconciled=false`; separate
reviewer reset/release/health interpretation is still running, not implied by
transport PASS. No frozen installation/audit source was modified after execution.

Worker health observed version30276,28 samples over30.1564587s after reset and
original-Boot release. EEPROM before-state was A TEST_BOOT seq12848 and B
CONFIRMED seq12849/current30275. Final pre-reset A is CONFIRMED seq12850/current
30276 and B64 is unchanged. The256B archives are repeated A/B/A/B reads, not
EEPROM addresses128..255. Post-boot RAM confirmation does not constitute a new
physical EEPROM read. Backup version remains30274; recovery has not established
an R2 backup. Boot replacement, NOR replay and supply changes did not occur.

The additive R2 checkpoint composes the real finalized Reader/capture, whole
original-Boot reads and paired health on one caller-owned connection. Component
tests2 passed3 methods,101 current/snapshot bindings, with full A/B positives
and reset/archive/Boot/owner/seal failures. tests1 is preserved: a negative test
expected ValueError where the capture layer intentionally returns CaptureError;
only that assertion and its failure-state checks changed. Review is pending.
The new native owner has a selftest-only CLI while its real connection/Close
integration and raw24-segment replay are tested. It has no EEPROM/NOR/phone
capability and explicitly cannot prove OTA readiness or a valid backup.

Next work remains the reviewed normal R2-A->R2-B route from section48: actual
closed recovery admission, fresh checkpoint, prepared phone/service/snapshot
route, and separately qualified final backup readback. No normal R2 OTA was
started, no new throughput measurement exists, and the four-hour J-Link repair
is not OTA performance evidence. Historical provisioning's SDK gap remains open.

### 51. Independent Recovery Closure And Read-Only Checkpoint Admission

CONTINUE1-INDEPENDENT is CLOSED PASS. The independent reviewer published
`.cache/p34-recovery-continue1-independent-review1/result.json`, SHA256
`157f85a60780e21a722fdbd72077a6c8f0144898702d119b856e12fe8a934a06`.
Its721-segment replay agrees with the strict audit and independently binds958
health target reads to30 total/28 ready samples,30.156458700017538s. Tick advances
1079->31336, loops270->9456 and watchdog feeds283->9456. Faults stay clear,
SD/diagnostics are1 and confirmation flags010104. Original Boot vector catch,
reset/release7/6-store sequences and final zero-target-store Close are verified.
This closes recovery's independent health/exit review, not historical provisioning
or R2-backup qualification. The actual final EEPROM pair is still pre-reset.

The24-log checkpoint component and native owner have no remaining blocking
review findings. Component tests2 passed3 methods/101 bindings; owner tests2
passed3 methods/144 bindings with actual modeled Dap/Observation/JournalSDK,
full A/B reads, DP restoration/preservation, native Close and offline raw replay.
Owner tests1 is preserved: its in-memory Buffer returned text for binary open;
the fixture was corrected, not the filesystem or product audit behavior.

Capture tests2 passed7 methods/153 bindings and independent rerun7/7. R2CAP-01
now converts every outer failure to FAILED/nonzero while retaining already
completed checkpoint/Close evidence and never retrying Native Close. R2CAP-02
requires the worker's actual current selftest receipt, compact closed-recovery
identity/worker/parent/review/audit references, exact900/1020s budgets, connection
generation and native-history binding before any native load. Missing/stale
bindings reject without loading the DLL. tests1 and both findings are retained.
Reviewed capture SHA256:
`282527357cdd0a0c6310f8cc044b439de6f9064ff4395843029791a36c95fe15`.

Root admits one fresh `.cache/p34-r2-checkpoint1` read-only observation under
the existing device scope. Entry is the independently closed R2-A recovery,
not a fabricated historical OTA predecessor. The parent rehashes original
recovery inputs/logs/archives before entry; the worker binds153 current inputs,
exact R2-A619580B/original Boot65536B/map and qualified DLL, then reads them on
one caller-owned connection and observes30s health. Worker900s/parent1020s,
component close reserve90s, per-native deadlines and strict segment seals apply.
All24 logs,2 archives, project/events/callback files, snapshots and host caches
are preflighted below this root. Only the existing exact SEGGER native history
exception applies. Root is sole physical operator; no new phone/transfer, halt,
reset, target payload write, EEPROM/NOR access or supply change is permitted.
Success requires real Native Close and subsequent archive/transport/health
reconciliation; it remains ota_ready=false and backup_observed=false.

Offline next-route work also derived the576B R2 session ABI from its original
Ninja C flags in `.cache/p34-r2-live-layout1`, with0 compiler warnings/errors.
The original21-member probe gives state offset204 and isr_active offset428;
session base is20052988, epoch20052BC8, retained word20052658, boot baud2005265C
and retention error20052654. No firmware was rebuilt or installed. This is
address/ABI evidence only: live QSPI mapping/ownership and an actual baud
observation remain unqualified. No new OTA speed measurement exists.

### 52. Fresh Read-Only R2 Checkpoint Closed And Independently Reconciled

checkpoint1 ran2026-10-06T11:15:34.152746Z to11:19:00.991146Z, elapsed
206.8383916s, exit0 without timeout. It archived exact R2-A619580B and original
Boot65536B, retained unchanged153 current inputs, restored TAR/CSW/DP40 and
returned one Native Close. No debugger remained; approved SEGGER history hashes
were unchanged. No halt, reset, payload store, EEPROM/NOR or phone action ran.

The independent `.cache/p34-r2-checkpoint1-independent-review1/result.json`
is CLOSED PASS, SHA256
`4c62015646915103c526288a7368b216ff2674485b9b10ac3708c1515fe2a772`.
It replays24 SDK logs against179428 native calls,172927 target reads and0 target
writes, with actual Close. Exact App coverage uses606 native chunks, Boot64;
all repeated header/vector bytes agree. All505 DHCSR samples have clear
reset/halt/lockup bits and all190 VTOR reads equal08010800. The942 native
health target reads bind28 samples over30.188855900021736s; ticks3449774->3480058
and loops/feeds941099->949224 advance with stable epoch, clear faults,
SD/diagnostics1 and flags010104. Changed-tick and unbound-time negatives reject.
Original receipts, archives, source snapshots and final raw logs are hash-bound.

Recovery and this fresh image/Boot/health checkpoint are therefore closed in
their stated development-review scopes. They do not establish live NOR mapping,
physical post-Boot EEPROM or R2-backup validity; `ota_ready=false` is intentional.
No old install/finish CLI may be replayed against this now-running R2 state.
Next-route source inspection confirms the original R2 startup normally enables
QSPI XIP for USB/filesystem reads, but the old nor_capture changes control/cache
state under a halted owner and must not be reused live. The derived R2 ABI and
matching-map SysTick/profile symbol derivation are usable offline inputs for a
new passive owner/baud/NOR qualification, not a physical observation by themselves.
No normal R2 OTA or new speed measurement has occurred.

### 53. Passive State Preparation And Bounded Native Admission

The additive passive-state and exact-instruction UI components now have scoped
independent development review PASS. Passive tests1 covers4 methods/107 bindings;
UI binding tests1 covers5 methods/22 bindings and5 original disassembly logs.
The combined state/UI tests1 covers2 methods/121 bindings. The reviewer also
executed3 mid-UI reset/read-error/owner-loss negatives: shared failure state
latched and replay made no further native calls. No new firmware was compiled.
An unloaded FirmwareUpdate page, cleared pending flags, idle BLE and unchanged
epoch are observations, not permanent writer exclusion or mapped-NOR permission.

Sender asset descriptors tests2 passed4 methods/35 bindings and independent
review after R2ASSET-01/02 dependency and ELF-anchor repairs. The unchanged R2
package2 is294052B, SHA256
`a67ff12d91a83c7f4bf0324f98ee68c1880547f39a37f3e2137707c3aed196e0`.
Its sole transition is30276->30277 with identical executable bytes. Original
schema9 sender axes and the canonical Boot/map/21-member ABI remain bound.
This is not a sender implementation, phone verification or OTA predecessor.
The earlier failed assets1 receipt is retained.

The new `Tools/ota/p34_r2_state_device.py` tests1 passed6 methods/167 inputs.
It composes the reviewed passive/UI probe with real modeled Dap, Observation,
JournalSDK and a three-log setup/state/Close lifecycle. Positive idle/busy UI,
DP restore/preserve, image/reset/UI/log/uncertain-close failures, offline head
corruption, checkpoint evidence corruption, pre-DLL worker admission and late
outer failure are tested. The predecessor is fixed independently closed
checkpoint1, not recovery replay or an invented historical OTA. Native-owner
independent review passed167 bindings and6 tests, plus2/4-log-layout negatives
that reject before target reads and Close once. Reviewed owner SHA256 is
`eaf16cb01f63706d4b4a0a1c95c589b514ef3f2432d08e184533e94fb25547ce`.
No physical state sample has yet run.

Root's next finite cell is `.cache/p34-r2-state1`, only after this owner review.
It reads exact R2-A header/vector identity, passive BLE/overlay/baud/clock/QSPI
words and bounded SRAM UI pointers twice, one second apart. Worker180s and
parent240s preserve a60s close reserve. The original native DLL/profile,
current selftest, immutable checkpoint proof, generation and SEGGER history
are checked before native load. One actual Close and TAR/CSW/DP restoration
must be raw-log reconciled; all other outcomes remain failed/unknown, with no
automatic retry. Root is the sole device operator. No halt/reset, power action,
target payload store, NOR/EEPROM access, phone or network operation is included.
All controllable outputs are preflighted under the active project root; only
the existing exact SEGGER history/config exception remains applicable.

After this cell, use observed raw status to decide the separate live mapped-NOR
route. Do not use the passive decoder's CSTS-masked config comparison as read
admission. XIP/idle/abort/CSTS, DMA/EDMA and every possible writer still need
qualification; cached logical observation cannot claim uncached chip contents.
No new OTA performance sample exists. The last transfer rates remain about
17.5 decimalKB/s; the50KB/s and general20s install/reconnect gates are unmet.

### 54. Passive State Closed And Independently Reconciled

state1 ran2026-10-06T12:42:15.267145Z..12:42:22.561526Z, elapsed7.2943844s,
exit0, no timeout or remaining debugger. The independently published receipt
`.cache/p34-r2-state1-independent-review1/result.json` is CLOSED PASS, SHA256
`57474293d8bf3e849ba3d684fd7784539fe23bddd5fd56f74492137acd526d7d`.
It reconciles167 current/snapshot bindings,3 raw SDK logs,1150 native calls,
469 target reads,0 target stores and exactly one Close with TAR/CSW/DP restored.
Approved native history is unchanged; no firmware/power/phone operation ran.

Both native-time-bound passive snapshots match the exact raw QSPI profile:
CTRL00100080, CTRL2=0, XIP_CMD_W3=0 (CSTS0, cache enabled). UI object20035718
has the unique R2 vptr/name/backpointer; root/timer/async/work/cost are0 and its
mode BYTE is0. The full mode word20035700 contains unrelated bytes and must not
be compared as an enum. Similarly BLE state BYTE is0 despite word00010000;
the disable BYTE at word+1 is0 despite raw word1. Epoch remains0, retained baud
word5034F708 and divider156 imply nominal923076baud under the exact known clock.
All12 DHCSR samples have clear reset/halt/lockup and all12 VTOR samples08010800;
the matching header/vector table were each read twice. This is not a fresh full
image/Boot or30s-health window, NOR/EEPROM capture, or all-DMA qualification.

### 55. Bounded Old-Backup Mapped Observation Preparation

R2-LIVE-NOR design review accepts a finite mapped-logical comparison under
paired guards, not physical-uncached/atomic/permanent-writer-exclusion claims.
No new firmware or generic gate framework is required. The pending implementation
batch is `r2_mapped_backup.py` plus `p34_r2_backup_device.py`. Component tests1
passed4 methods/179 bindings, native-owner tests1 passed5 methods/186 bindings.
Full native-owner review is still pending; no mapped backup read has run.

After that review, root's next cell is `.cache/p34-r2-backup1`. Its sole input is
the independently closed R2-A/state1 lineage and unchanged original recovery
archive `after-candidate-backup.bin`,2MiB/SHA256
`c5a72cbf45608b25edcc5939ff8ac8fbbed25b970bb6e1d2830d2a50f36e1a48`.
Read the exact known32B backup header at90100000 before admitting any payload;
then read only617588B at90101000 and require full-byte equality and SHA256
`22a0c48da12e24e61368c1617bb9b6098a8416ab598f59dc005a2b594ea70002`.
It is version30274, not R2. No candidate, recovery slot or arbitrary NOR region
is exposed. No command/FIFO/controller write or cache/mode change is implemented.

Execution uses19 logical blocks of at most32KiB/30s, each bracketed by exact
R2 passive/UI and DMA/EDMA checks. UI is located once and sampled in20 reads;
all22 DMA/EDMA control words are observed. Only source-known SPI1 display and
SDIO2 DMA with SRAM memory endpoints may be active; any EDMA or other DMA
enable rejects. Each at-most1KiB AP burst additionally checks reset/VTOR,
BLE/overlay/epoch and raw XIPSEL/IDLE/ABORT/CSTS/QSPI request state. Any drift,
nonidle state, AP failure, timeout or byte mismatch invalidates the capture;
do not wait through, repair or blindly replay it. One private function binding
reuses the frozen state-owner connection/Close implementation without changing
its module globals or executed source.21 raw logs include setup and final Close.
Worker900s/parent1020s, port780s and60s Close reserve are fixed.

Root is sole device operator. The allowed action is read-only mapped baseline
observation under the existing task scope, not halt/reset, NOR provisioning,
EEPROM access, Boot replacement, phone transfer or supply change. All outputs
and subprocess home/temp/cache paths remain below the active project root;
only the already approved SEGGER native history/config exception applies.
Post-close review must reconcile exact native reads/guards/archives/Close before
using this result. No uncached-chip, electrical-speed-grade, new-R2-backup or
OTA-readiness assertion follows from a successful mapped logical comparison.

R2MAP-01/02 were required host fixes from the combined review, before any
physical mapped capture.01 reproduced expiry after the first payload chunk
followed by31 more reads because the block limit was only checked at the end.
02 reproduced first-archive expiry followed by an unguarded second archive.
Both tests1 receipts remain original host results, not physical admission.
The successor puts the block deadline inside `Capture.check` and caps the real
native guard by block/component/global reserve. Each archive now has an
individual30s maximum guard with pre/post owner/time checks; first-save failure
prevents the second. Component tests2 passed6 methods/179 inputs and owner
tests2 passed6 methods/186 inputs. New actual-port/owner cases verify no next
chunk, no second archive, shrinking native/archive timeouts and one Close on
returning failures. Combined remediation review is pending. No generic helper,
firmware, frozen state/checkpoint component or historical audit was changed.

Both R2MAP findings are now independently resolved. Recheck verified179/186
current/snapshot bindings and ran5 affected methods, including full native
capture/replay and native failure paths, PASS in62.090s/exit0. Component SHA256
`3302375f834bfbbd5c8c8a60299776bc556de75d0467d00bbaf35e1decd0779b`;
owner SHA256 `a66ec9d1b7735dcda70f057a7c71cae700e56cdba26811449f6a13c28a646962`.
Output audit9 passed1453 selected files/902 directories, including retained
tests1 failures/findings and all post-audit8 preparation/state/review outputs.
Root admits the single planned baseline mapped observation after fresh output
preflight, with tests2. Hard timeout is an uncertain result, never automatic
reconnection or replay. No OTA/performance acceptance is implied.

### 56. Pre-NOR Qualification Failure And Byte-Display Successor

backup1 returned FAILED at2026-10-06T13:31:35.842026Z after10.0775312s, exit1,
no timeout. Its independent failed-prefix review is
`.cache/p34-r2-backup1-independent-review1/result.json`, SHA256
`86ac6ec2f69d0d1d47e443c105fae827c1e2140118a03070015f53625c365e53`.
This reconciles186 current/snapshot inputs,2 SDK logs,781 native calls,
274 target reads,0 target writes,0 NOR reads and one returned Close. TAR/CSW/DP
and history are restored/unchanged, no debugger remains, and no archive exists.
It is not a successful21-log backup capture. All executed sources stay immutable.

R2DMA-01 is a source-backed host qualification false rejection. Display DMA1/3
had exact BYTE-width1093 control, fixed SPI1 peripheral4001300C and memory
200145DF. Frozen `HAL_Display.cpp` uses BYTE memory/peripheral widths and splits
at65535 bytes; an odd continuation address is legal. A particular preceding
buffer or transfer history was not observed. SD DMA2/4 was2A81 with peripheral
50061080 and aligned memory20052E10; all other DMA/EDMA enables were0.
No controller, firmware, EEPROM, NOR or power repair is indicated.

The additive `r2_mapped_backup_byte.py` replaces only the qualification lookup
in a private copy of the original snapshot method. Display addresses may be
byte-granular inside SRAM only under the same exact control/peripheral profile;
SD retains word-aligned SRAM. Raw recorded endpoints are never normalized or
rewritten. `p34_r2_backup_byte_device.py` privately binds that capture into the
unchanged native owner/worker/CLI and adds the exact independently reconciled
failed-prefix predecessor. No original module globals or source files change.

After source-bound selftests and independent review, the next finite cell is
`.cache/p34-r2-backup2`, with the identical header/payload,21-log layout,
900/1020s worker/parent,780s component,30s logical-block/individual-archive caps
and60s Close reserve from section55. It continues a diagnosed pre-NOR rejection,
not a repeated successful observation. All previous no-write/no-reset/no-power
and mapped-logical-only limitations remain. No normal OTA or speed sample exists.

Byte-display tests2 passed5 methods/194 input/snapshot bindings. The positive
uses the actual odd200145DF display and aligned20052E10 SD addresses through
the complete modeled native owner,21 logs and617588B archive; every raw guard
retains the odd address. Negatives reject outside-SRAM display addresses,
word-unaligned SD, changed controls/peripheral/CSTS, altered failed-prefix proof,
invalid worker plans and late outer failure. Frozen original globals are checked
unchanged. tests1 is preserved: its positive capture passed, while two reused
test seams expected `os`/`ctypes` module attributes absent from the new entry;
explicit standard-library imports repaired the seam, not the physical guard.
No hardware operation was attempted by either host test run.

### 57. Old Backup Closed And Normal OTA Host Remediation

The byte-display successor was independently approved with component SHA256
`e926392ebc308b2351b71fc78ff6d4e9742b54e7eba1a0bf2cb30567a7638475`
and entry SHA256
`e93388e854906a714f6a46af78d19a48ab0a4b4d8cebfb3d6b081913b3fa9c5c`.
backup2 ran2026-10-06T14:00:11.394498Z..14:04:21.761992Z,250.367381s,
exit0/no timeout. Its independent original-log reconciliation is
`.cache/p34-r2-backup2-independent-review1/result.json`, SHA256
`92d2320f5fe409615722907e06a66903b62aa06149da985574e23fef50e0c4cc`.
All21 logs,235553 native calls and170368 target reads reconcile; target writes0.
The32B header and617588B payload exactly match the archived30274 backup.
All39 full guards,1249 cheap guards and1331 DHCSR/VTOR pairs qualify; maximum
block17.108360s and burst0.384524s. There is exactly one Close, restored
TAR/CSW/DP, unchanged history and no remaining debugger. This is a mapped-logical
30274 observation, not an uncached-chip/electrical/permanent-exclusion result,
not a new R2 backup and not an OTA speed measurement. Executed dependencies
remain frozen; no backup/recovery replay is permitted to recreate evidence.

The normal R2 phone entry and two post-OTA owners were prepared without device
operations. Postcheck identity requires the complete R2-B App/original Boot and
health; its separate mapped-backup owner expects complete R2-A619580B and the
corresponding ETSL header. Both require the original completed App snapshot.
The phone entry inherits the schema9 provision/observer/download/finished-snapshot
path, forbids the old native checkpoint and does not start the old full trace.
A captured App snapshot explicitly leaves `final_device_verified=false` until
the separate identity and backup checks actually complete.

Consolidated host findings and remediation:

| ID | Evidence and repair | Local verification |
| --- | --- | --- |
| R2POST-01 | Base observation reader rejected valid radio/PHY producers. Both phone and postcheck now use the existing fixed radio/PHY reader with its original query binding. | Real encoded schema9/radio/PHY query and completed fixtures; credential, loss and corrupted records reject. |
| R2POST-02 | Admission boolean alone did not bind original prestart evidence. Validate original query events and both health samples, successful query, schema9 runtime configuration, matching capture/PID and zero starts/ends in health-ready; fingerprint all11 originals. | Missing originals, changed PID/config/policy/capture, unsuccessful query and already-started health reject. |
| R2PHONE-01 | Capture-capacity and fixed-reader contracts were absent from closure. Add the actual helper, both fixed prefix contracts and exact original query implementation/import helpers. | Required records present in host/runtime source sets. |
| R2PHONE-02 | trial-tests1 timed out180s; context-probe1 closed75s with stack inside historical ACK asset loading, not parser work. Privately bind only Backend.context to a copied CLI view skipping historical reconstruction; set actual R2 group/full package/asset/APK fields explicitly. | No historical loader calls/global registry mutation; real Context/config/target and in-memory prepare/validate positive/negative plans pass. |

Postcheck-tests1/2 and trial-tests1 remain original historical results. The
context-probe1 timeout and original stack are retained. The reviewer separately
confirmed the private-context repair direction in an artifact-free16.282s probe.
Current `.cache/p34-r2-postcheck-tests3` passed3 methods;
`.cache/p34-r2-trial-tests2` passed3 methods in19.820s. Combined independent
remediation review is pending. No phone/J-Link/network/OTA operation occurred
during these tests. No new transfer/install timing is available.

### 58. Finite Normal R2 Transition Plan

Root remains sole physical operator under the user's continuing P3-4 authority;
all selected outputs stay under `D:/github/my/E-Track`. J-Link3.3V/GND supply
stays connected. No commit/push/release, Boot replacement, arbitrary EEPROM edit,
NOR provisioning or replay of the completed recovery is included.

The finite matrix consists of current-phone read-only admission, one normal
R2-A30276 to R2-B30277 transition, then separate read-only B identity/health
and A mapped-backup verification. This header-only same-executable transition
establishes an R2 backup through the normal updater, not group16 performance.
Use existing `.cache/p34-r2-ota-package2/full.etu`,294052B/SHA256
`a67ff12d91a83c7f4bf0324f98ee68c1880547f39a37f3e2137707c3aed196e0`;
do not regenerate nonce/package. APK is the existing verified schema9 build,
131659530B/SHA256
`53434b036d5879166ccd1c9e28bc919a0d61c74784230fd8591756cd089c0f3c`.
Actual phone-installed hash/identity and log capacity still need current USB
verification; historical installation is not current admission.

Known physical baseline is the independently closed R2-A checkpoint/state and
backup2. Original Boot SHA256 remains
`a63346db0dc673dc42adf6064892c466af5c4571df53cb55fe5b6ea154c1fdf4`.
Latest physical EEPROM sample was before recovery reset: A CONFIRMED12850,
current30276; backup metadata30274; B64 unchanged. No post-reset physical BCB
sample exists. Historical provisioning SDK-log limitations remain unresolved.

Normal phone output is `.cache/p34-r2-normal-ota1`, not yet launched. Keep the
existing finite coordinator/network/cell lifetimes, prestart admission and
no-progress/active-transfer watchdogs. Postchecks retain900s worker/1020s parent,
their close reserve, separate ownership and no-reset/write boundaries. Only
invite the user to connect/download and tap Start when the live original query
and exact downloaded bytes qualify. No automated taps. Keep foreground and USB.
After terminal snapshot retrieval, close phone/network before either J-Link
postcheck. If outcome is uncertain, retrieve original evidence and inspect state;
never replay OTA to replace a lost collector result. Retain verified R2-B.

If current capacity is8, first inspect the actual capture inventory and preserve
latest/unknown captures; the inherited query-only capacity path cannot treat a
completed capture as unused. Any needed existing-capture archival must bind exact
verified historical evidence and preserve bytes without deletion/overwrite.
This is preparatory phone data management, not an OTA or speed result. Boot
group16 remains a later, separately scoped operation after verified R2-A backup.

### 59. Host Batch Reviewed And Phone Physically Unavailable

The independent reviewer resolved R2POST-01/02 and R2PHONE-01/02 together, with
254 postcheck and262 trial current/source-copy bindings. All6 methods passed
independently in55.170s. Reviewed postcheck SHA256 is
`45ebce77acb157e2782f3b5b8ccf1ee2794b6fd7d6a3c7e3a367574f3bd61995`;
trial SHA256 is
`bf1b220f4fe7dabaabea44cc1b0d481d19ddd5c1b512ae59c47e7f97dcea157d`.
This is reviewed development tooling, not physical OTA or formal acceptance.
Audit10 passed2100 selected files/1184 directories for all post-audit9 backup,
failed/successful host tests and context-probe outputs. Historical audits and
failed receipts were not rewritten. No new external filesystem write was observed.

Actual phone admission used the separate source-bound
`.cache/p34-r2-phone-state1/inspect.py` with direct `Backend.inspect`, deliberately
not `Crc.inspect` and not its capacity mutation path. It reuses the tested R2
Context, original exact-APK USB admission and capture;600s owned job. Parent ran
2026-10-06T15:30:32.064663Z..15:31:16.962251Z,44.8975915s, exit1/no timeout.
The nine original `get-state` calls all returned
`device '10ADA4197U001CK' not found`. Result is `PHONE_NOT_READY`, not an APK
mismatch or measured capacity failure. Actual APK/phone inventory remain unknown.
No App start/stop/configuration change, archive, BLE action or MCU operation was
reached. Normal `.cache/p34-r2-normal-ota1` remains unlaunched.

The private ADB server used5062 and closed normally: stop/server/launcher exits0,
port closed, original read-only adbkey hash unchanged. All selected host outputs
remain under phone-state1 and the existing project-local device-lock path.
No J-Link connection or supply change occurred. Root requested the actual necessary
user action: connect/unlock the named test phone over USB and allow its debugging
dialog if shown; do not disconnect the board's J-Link. A renewed read-only phone
window requires that changed external state and a fresh output directory, not
replay of phone-state1 or a blind OTA. All successful recoveries remain retained.

Performance is unchanged: latest header-only30274->30275 sample17.542732 decimal
KB/s and20.361587s END-to-identity; changed-executable30273->30274 sample17.456203
decimal KB/s and36.426757s install/reconnect. No new transfer occurred in this
continuation.50KB/s and general20s objectives are still unmet.

### 60. Connected Phone Admission And Exact Inactive Archival

The user confirmed the test phone is now connected. This external-state change
admits a fresh read-only window, not replay of phone-state1. The exact unchanged
inspection script was placed in `.cache/p34-r2-phone-state2`; source-pinned
parent ran2026-10-06T15:46:44.777154Z..15:47:19.381469Z,34.6044175s, exit0,
no timeout. Actual phone identity, schema9 APK hash and Nearby permissions pass.
App PID is absent and current configuration/snapshot match the historical30275
capture. The private ADB server closed normally with all three exits0, port5062
closed and the original adbkey unchanged. No App launch/configuration/archive,
BLE transfer or MCU action ran.

The current inventory contains8 captures. Latest protected capture is
`1791112203004255-d72cb83d6d8ace1100542bab`; its snapshot SHA256 is
`835cf90d3b02c9546af1864589da574a0ec5d84c72777f82a74ca9a6967a69ce`.
The config SHA256 is
`a78004a2c32da7fb48fc90aaea26c88f9e7ce15fbe41dc2011714ba807e4f6ca`.
The older SHA-bootstrap30274 capture
`1791109543492381-a4d3bfe9d005aecc87088458` is present; its original snapshot
SHA256 is `6f8b9f9b8fa30a31a4a4fafcf8187380d77bd76f9ab4870e1cd51832d18f5472`.
Both `.cache/p34-sha-candidate/trials/bootstrap` and `measure` original
`p34_radio_archive.proof` checks pass. These are historical phone records, not
the physical R2 MCU predecessor.

The next finite preparatory action is `.cache/p34-r2-phone-archive1`,600s owned
parent/worker. Privately bind the original `p34_radio_archive.worker` to those
exact historical selected/protected roots and the tested current R2 Context USB
runtime. Keep the original path, health, snapshot, current-config, stopped-App,
host-copy/readback, no-overwrite and post-move equality guards. Original source
remains unchanged. Only the older App-internal directory may move from
`files/p34-observations/1791109543492381-a4d3bfe9d005aecc87088458` to
`files/p34-archived-observations/1791109543492381-a4d3bfe9d005aecc87088458`,
after local archival/readback. No deletion, replacement APK, configuration change
or OTA is included. Protect all7 other captures and the current configuration.
Resolve exact private paths on the phone before mutation; existing destination,
changed bytes/state or uncertain move stops the route without retry.

The additive adapter tests the full unchanged archival worker with a model USB
runtime: one successful move, altered snapshot and unknown-file rejection, and
one uncertain move with no retry. Selftest/independent review precede execution;
these models are not physical evidence. Successful actual archival must leave7
captures, the protected/config bytes unchanged and USB fully closed before normal
R2 OTA starts. The R2 package, Boot/supply constraints and section58 postchecks
are unchanged. There is still no new speed result.

State2 independent review verified332 source bindings and24 original read-only
ADB commands, including correct phone/model/user0/APK/permissions,8 captures,
absent App process and protected snapshot/config. Its closure and key/port checks
pass. The selected older phone snapshot still requires the archive worker's
fresh comparison with its verified original.

R2ARCH-01 was found before physical archival: the current USB context emits a
write-once `transport-ready.json` through wrapped `phone_identity`; the original
archive worker repeats `phone_identity` after entry. The first4 models used a
no-op identity and missed that duplicate receipt. Keep those original test
receipts. A private worker-phone facade now extracts the original raw identity
from the exact validated wrapper closure, retaining its current contained ADB
command globals. The USB entry remains unchanged; the second check still reads
serial/model but does not repeat readiness or overwrite a receipt. No original
module/source/global is modified. New `tests2.json` passes5 cases including the
actual wrapper/facade seam (one receipt, two serial/model checks) and wrong-phone
rejection. Physical archival remains unstarted pending this minimal recheck.

### 61. Archive Closed And Normal R2 OTA Awaiting User Start

R2ARCH-01 minimal review passed350 bindings and all5 model cases. Actual
archive1 ran2026-10-06T16:18:29.958957Z..16:19:48.949623Z,78.9907229s,
exit0/no timeout. Independent review reconciled62 original ADB commands and
all3 host copies against pre-move and post-move bytes: one force-stop and one
exact `mv -n`, no deletion/OTA/install. Destination absence before and source
absence after are explicit. Protected snapshot/config remain byte-identical;
inventory8->7 removes only the selected directory. USB stop/server/launcher0,
port5062 closed and original adbkey unchanged. Result SHA256 is
`e8c9c356d337ebc538089739ae9c206728a1c23c21a6310630c472a4b8c3cd8b`.
This completed archive is not to be replayed.

Normal `.cache/p34-r2-normal-ota1` coordinator launched at16:23:02.952820Z
with6000s lifetime. Its prestart inspection reverified7 captures and stopped
App; the original configuration was retained through the normal retirement
route before provision. The normal network/phone workers own their bounded
lifetimes. At16:28:10.339603Z the phone cell reported
`READY_FOR_FULL_INSTALL_START`, PID29815, target30277, baud921600/window28.
Root independently revalidated original query events, surrounding health,
schema9 runtime configuration, zero starts/ends in health-ready and the complete
downloaded294052B package with SHA256
`a67ff12d91a83c7f4bf0324f98ee68c1880547f39a37f3e2137707c3aed196e0`.
Current capture is `1791304064275106-3ef9bdad22c698f5be45adf8`.

The user was asked to tap Start once, keep the App foreground and USB connected,
and not switch back to chat during transfer. No host-automated tap, J-Link
operation or Boot/supply change occurred. A completed original snapshot has not
yet arrived at this recording point; no new throughput/install result is claimed.
The1500s App-start window and900s active-transfer limit remain unchanged; do not
alter running source or reset/replay a transfer to extend them. If the user starts,
retrieve the original cell outcome and close both phone/network workers first.
Then use the prepared postcheck identity and backup outputs
`.cache/p34-r2-post-identity1` and `.cache/p34-r2-post-backup1`, both preflighted
against254 inputs. Do not relaunch normal-ota1; if it closes before Start,
reconcile the original unused capture/configuration before any renewed window.

### 62. Original R2 OTA Complete And First Postcheck Reset Latch

The user reports completion. Original cell closed at2026-10-06T16:48:18.389825Z
with `R2_OTA_SNAPSHOT_CAPTURED`; all3 worker owners exited0/nonforced and the
phone/network resources closed normally. Original completed snapshot1013333B,
SHA256 `d5a6fc35145ff32913880505928531c5e92d38050827a4a50958b5504c0108b1`,
contains8961 records/8958 producer lines and30276->30277 with exact R2 image
and package identities. Independent review verified331 intent inputs, the
11-input real trigger, original ADB-bound blobs and closing receipts.

Public original MONO durations:17.898428s transfer,20.494210s END to verified
reboot identity,38.392638s total.294052B/transfer =16.428928842 decimal kB/s.
Both50kB/s and20s targets remain unmet. The separate link stopwatch duration is
17.894114s; do not subtract clocks with different origins. Actual link summary
has2298 unique/sent DATA frames, no retransmit/error/duplicate and73 durable
events ending294052. Unlike historical incomplete ACK samples, this run reports
2298 complete samples, early-invalid0/early-unsent0, P99=146546us. This is only
the current single-run App distribution, not formal P99/reliability acceptance.
No host MCU trace was collected during OTA; native install-phase timing remains
unobserved. Public timing is not final physical image or backup verification.

The planned read-only identity1 postcheck ran16:54:33.580140Z..16:54:59.234927Z,
25.6547897s, exit1/no timeout. It rejected at its first and sole target read:
DHCSR E000EDF0 returned03010001, including S_RESET_ST/S_RETIRE_ST but no
S_HALT/S_LOCKUP. The strict Reader correctly latched reset_seen and rejected
before any VTOR/App/Boot payload read; no archive exists.27 original AP/DP
calls and two raw SDK logs are retained. One Close returned with TAR/CSW/DP
restored, no target payload writes/reset, history unchanged and no debugger.

An initial sticky reset indication from the completed normal OTA is a hypothesis,
not yet a demonstrated absence of repeated resets. The minimal proposed
discriminator is one fresh unchanged identity2 owner after the first DHCSR read,
with all reset latching retained. Success would only establish continuity of
that new observation; it would not erase identity1 or date the previous reset.
Repeated initial reset must stop that path and trigger reset diagnosis, never
an unbounded retry or masked latch. No new OTA, halt, reset, Boot replacement,
EEPROM/NOR operation is included. Independent failed-prefix review is pending.

### 63. R2-B And New R2-A Backup Postchecks Closed

Identity1 failed-prefix review completed:254 unchanged current/source-copy
bindings,27 native calls, one DHCSR read, zero target writes and exactly one
Close with restored TAR/CSW/DP. worker.json SHA256 is
`73af858ae5c7d48586f3e8a547a89fa5b26260e32b2d3ea95575595894c64541`.
The reviewer accepted one unchanged fresh-epoch identity2 discriminator, not
latch suppression or an unlimited retry. No source modification was needed.

Identity2 ran17:08:43.884716Z..17:13:03.767765Z,259.8830383s,exit0/no timeout.
The exact619580B R2-B30277 App and65536B original Boot both match. Independent
24-log replay reconstructed full byte coverage:179428 native calls,172927 target
reads, zero target writes and one completed Close. All505 DHCSR observations
were free of reset/halt/lockup, all190 VTOR reads matched runtime vectors.
28 native-bound health samples span30.7988045s with clear faults, readiness,
SD/diagnostics, stable epoch and positive tick/main-loop/watchdog progress.
All254 inputs and copied sources match; history is unchanged and no debugger
remains. worker.json SHA256 is
`b0db8168b18564a61b7ea65c8b5956ca52f945d3809ff833a0b011cbd6a6052a`.
This continuity conclusion covers only identity2, not identity1's preceding
interval or the unknown time/cause of its initial sticky reset indication.

The separate backup1 postcheck ran17:16:21.294779Z..17:22:00.399486Z,
339.1046819s,exit0/no timeout. Root verified the archived32B header SHA256
`9e2e3b18f46dffb76a7d31b66654ec206ca6c830f7b1b15b6d9c4006171e25c6`
and complete619580B payload against frozen R2-A30276 SHA256
`7445ef63d5f4cbef95761f27075333d7d09c9d43585a28b84e6575ccfb274fcf`.
Header is `4554534c02ffffff3c740900f49fcd9044760000deb4484dd0614f49544d4f43`.
The owner reports21 closed logs, restored TAR/CSW/DP, unchanged history and no
debugger. Independent mapped/native reconciliation is pending. This is a
mapped-logical backup match, not uncached-chip/electrical margin, permanent
writer exclusion or a physical post-reset EEPROM sample.

Backup1 independent review subsequently closed PASS.254 plan/current/copied
source inputs and the original trigger match.21 raw SDK logs reconcile236259
native calls,170906 target reads,zero target writes and one completed Close.
The32B header and606 payload chunks reconstruct exact contiguous
`[0x90101000,0x9019843c)`,last60B,total619580B. Header CRC/length/version/key
prefix/TMOC and all payload bytes independently match R2-A. Initial/final current
App header and524B vectors match R2-B.39 full raw UI/passive/DMA guards,
1253 cheap guards,1335 DHCSR/VTOR pairs and19 block records all qualify with
epoch0. worker.json SHA256 is
`ad5637390057c517a4d89bfd8206e017490ccdc506c724cee3b0b033db3be35f`.
No remaining finding in this bounded postcheck scope. Mapping/electrical/BCB
and reset-cause limitations above remain; no formal acceptance is implied.

All root hardware/phone/network jobs are now closed. Retain R2-B30277 and the
new R2-A backup. Original OTA timing and identity1's failed observation remain
unchanged; do not rerun this OTA or either successful postcheck to recreate logs.

### 64. Next Boot Replacement Scope Requested, Not Executed

Existing reviewed isolated group16 binary is14800B, SHA256
`2f84014278421de7a84a0f621a494a9974fbf51c56b768974b0c5e647105ec80`,
at `.cache/p34-bc-target/b16/boot/X-Track-Boot.bin`. The existing group1 control
is14780B, SHA256
`f0ed3994f7f7a7d39dac92a09b0fedf2f2b7b05ee038ac400eba2c569c586954`,
and exactly matches the prefix of the just-verified original full Boot. Each
existing build reports1 warning/0 errors; no new compilation ran in this turn.
No production default or frozen acceptance input was changed.

The candidate fits the first16KiB/eight2KiB Flash sectors. Original bytes after
the old control's end up to16KiB are FF, but bytes beyond16KiB in the64KiB Boot
region are NOT all FF. Therefore an eventual Boot-only replacement must preserve
the complete `[0x08004000,0x08010000)` suffix, not mass-erase64KiB and pad it.
The complete65536B original Boot backup remains the exact recovery reference.

Root asked the user for the specific next scope: after validated programming/
recovery preparation, replace only `[0x08000000,0x08004000)` with the group16
experimental Boot, restore original Boot on failure if required, leave App,
EEPROM and external Flash payloads unchanged during replacement, and keep
J-Link supply connected. No Boot mutation is currently authorized/executed by
this note, and no unattended write is scheduled. The broad prior continuation
authority does not silently remove the explicitly excluded Boot-replacement
scope. Keep one operator, finite stages, original failure evidence and no blind
replay. Authorizing replacement would not itself establish the safe entry/exit
implementation, finite App set, compatible recovery behavior or flash readiness.

R2's619580B image uses152 copy blocks rather than the old617588B image's151.
Grouped copy-progress count would be152->10; the142 fewer transactions imply
only a nominal5.68s page-cycle estimate, not measured savings or a20s promise.
Review the final partial group's152-block shape in the minimum next host scope;
do not replay the old complete fault campaign simply to change its image size.
This candidate affects Boot installation work, not the unmet BLE throughput.

### 65. Boot First 16KiB Authorized, Preparation Started

The user's subsequent explicit reply, "授权", approves the exact section64
request. Root may replace only `[0x08000000,0x08004000)` with the existing
group16 candidate after validating programming and restoration, and restore the
original first16KiB if required. Preserve `[0x08004000,0x08010000)`, complete
App, EEPROM and external Flash payloads during replacement. Keep J-Link power
connected. This supersedes only section64's pending authorization, not its
historical record or technical preconditions. No repeated permission question
is required for this scope. No Boot programming has yet occurred.

Next bounded preparation: recheck original/candidate/control bindings and the
existing finite-R2 proof; test the152-block final partial group without rerunning
the old151-block campaign; qualify a new first16KiB-only programming/restoration
entry for a fresh running R2-B admission. Do not invoke the historical whole64KiB
Commander activation or replay completed App/EEPROM recovery. Reuse individually
qualified native primitives with exact current identities, finite budgets,
source-bound original logs and explicit failure settlement. Consolidate the
route for the existing independent reviewer before mutation. New results remain
development evidence, not formal acceptance, a production change or measured
speed improvement. Sole operator: Codex root; writable root: `D:\github\my\E-Track`.

#### 65.1 R2 Tail And First16KiB Port Self-Tests

`Tools/ota/p34_boot_r2_tail.py` rechecks the frozen model sources, target
snapshot/artifacts and stack-analysis bindings without rebuilding Boot. Its
synthetic header-only and dense fixtures use the exact finalized R2 length
619580B,152 blocks,1084B in the last block. They are shape tests, not a replay
of the physical R2 payload. `.cache/p34-boot-r2-tail2/result.json` reports:
group1:51 scenarios,152 progress commits; group16:231 scenarios,10 commits,
208 cuts restricted to the last8 blocks and subsequent transitions, maximum
verified-but-uncheckpointed rework8. Final partial flush, final-block failures,
transaction errors and152 per-block rollback commits pass. New host compiles
have zero warnings/errors; reused target builds still each have one warning.

Preserved harness failures: `p34-boot-r2-tail-preflight1/result.json` rejected
byte equality between individually hash-verified LF and mixed-line-ending
copies; normalized source text is identical. `p34-boot-r2-tail1/g16-run.log`
failed the synthetic history-only frontier oracle: a cut can leave a valid
committed physical BCB before its test callback records history. The repaired
oracle observes valid physical model records before recovery as well as history;
it does not remove the final152-frontier requirement. No firmware change or
device retry was involved. Earlier output remains unchanged.

`recovery_confirm/boot16.py` introduces exact original/candidate asset binding,
an eight-sector first16KiB plan and an independent ordered write oracle. It
reuses the frozen controller sequence/observed-settlement loop, not the old
App geometry. Restoration targets only the known original first16KiB; suffix
drift fails before any write. `.cache/p34-boot16-tests1/result.json` passes7
methods: every activation/restoration sector and its exact stores, partial
prefix restoration, bad asset/range/suffix rejection, out-of-scope writes,
admission faults, uncertain controller failures with no implicit cleanup/resume,
and late already-settled status observations. These are host-only ports, not
a connected device entry or completed safe-recovery route. R2 rendezvous,
coordinator, failure settlement, exit and independent review remain pending.

#### 65.2 R2 Entry Direction And Finite Qualification Cell

The existing independent reviewer accepted the design direction, not programming
readiness: use exact R2 main-loop WFI `0x080461C0`, bytes `30BFA9E7`, FPBv1
comparator `0x480461C1`, runtime VTOR `0x08010800`. The display-wait WFI and
VTOR-error-loop WFI are not valid rendezvous points. Keep PC/xPSR/MSP/special
registers unchanged, no RAM code or register-value writes, no reset. Release
the same R2 context after the complete operation instead of entering Boot merely
to test replacement. This avoids deliberate EEPROM/Boot state transitions.
Physical BCB recapture is deferred for this no-reset/no-payload-write cell;
RAM confirmation flags are not relabeled as physical BCB evidence. A later
actual Boot/OTA transition requires its own state admission.

Held media admission requires raw software/UI/QSPI ownership and two stopped
observations, SDIO2 status/DTCNT and DMA counts zero, exact CMD13/RSPCMD13 with
RSP1=0x900, SD-ready/DATA0, clean cache/transfer/stop flags, released EEPROM
pins, and idle unconfigured USB/BOT. Source review distinguishes exhausted
noncircular DMA with EN still set from an in-flight transfer: the former can be
accepted only with exact modes/endpoints and zero counts. SDIO DTEN may likewise
remain set after completion. Do not disable/drain a peripheral to manufacture
admission. This is a current inactivity predicate, not historical filesystem
integrity or physical NOR WIP/BCB proof.

`boot16_entry.py` and `.cache/p34-boot16-entry-tests2/result.json` pass8 host
methods, adding explicit exhausted-EN positive and circular/M2M/in-flight/USB
negative cases. Release checks known context, pending exceptions and unchanged
debug controls; clear only an owned new DFSR breakpoint bit, issue one DHCSR
release, observe running, then restore the original watchdog-freeze value.
Uncertain release cannot be retried. Original entry-tests1 remains7 methods.

The next finite device qualification is deliberately separate from programming:

| Field | Bound |
| --- | --- |
| Authority/operator | Existing device-development and new Boot preparation authority; Codex root only |
| Starting identity | R2-B30277, original Boot; direct prior identity2 original full capture and exact current header/runtime/WFI rebinding |
| Matrix | One new R2 entry/release qualification cell; not another OTA, install or repeated speed sample |
| Operations | Read-only admission; owned halt-freeze and one WFI comparator; read selectors; same-context release; restore owned debug setting |
| Prohibited | Flash/EEPROM/NOR/RAM payload writes; reset; PC/MSP/VTOR writes; power changes |
| Timing | 120s entry/release phases,15s rendezvous wait,600s worker,720s parent,>=30s health and reserved Close |
| Evidence | Six original native log segments, exact DRW plans, AP/journal reconciliation, source copies, failed outcomes retained |
| Output | `.cache/p34-boot16-entry-probe1`, all controllable host outputs project-local; existing exact SEGGER native-history exception only |
| Failure | No payload mutation; do not repeat an uncertain control store. Retain halt/pause on unresolved entry; reconcile actual state before a successor |
| Success | One normal native Close, AP restored, same R2 running healthy, original halt-freeze restored; no claim that group16 Boot ran |

The cell is not yet executed. Its coordinator is `Tools/ota/p34_boot16_probe.py`,
with no Flash-programming CLI. The first host test failed because the new mock
shadowed an inherited dictionary with a set; probe-tests1 remains failed.
Probe-tests2 passed3 real-transport/log/health/Close methods. The later
probe-tests3 binds the consolidated USB/DMA entry and source closure; consume
its actual result only when present. Root also removed the reviewer's accidentally
created empty project-root `inten` after checking its exact path and zero size;
no external path was touched by that cleanup. No Boot erase/write has occurred.

Consolidated review fixes before any device launch: BOOT16-EMIT-01 replaces
the temporary Reader class with a namespace so a strict `(event, **fields)`
callback is not rebound as a method; a strict-callback regression passes.
Source-derived initialized USB idle is low16=7 (state IDLE7/BOT0), also admitted
with connection0/1 alongside zero-initialized0. BOOT16-PROBE-01 retains logical
debug requests for every mutated, non-normal failure, not merely when a release
store did not return. Returned-but-still-halted, post-release log failure and
pause-restore failure all retain DP requests with no second release/reset.
Original Close is attempted in finally even if the retention observation fails.

Latest receipts are entry-tests3:9 methods and probe-tests4:5 methods. The latter
also reparses all six original mock SDK segments and18 exact debug stores,
rejecting altered active-head hashes or missing actual Close. The physical
probe is still pending final bounded review; historical receipts are unchanged.

The existing independent reviewer subsequently closed BOOT16-ENTRY/PROBE
preparation for this exact no-payload-write cell. Entry-tests3:9/55 inputs and
probe-tests5:5/352 inputs were independently reconciled with current sources and
archived copies. All180 loaded project modules are covered. Callback and
failure-retention regressions were independently executed without artifacts;
no remaining finding in this bounded scope. This does not qualify the later
Flash-programming coordinator. Probe SHA256 is
`f582e01fd49196e6d7fe3c1cdea9008cae63e3f6d6847d810c2535b456e03df6`;
entry SHA256 is `6f163337976b2bc95d3d89cbbdca8c9cfd2accd801594f2929529dc99bdf8162`.
Root is starting the already-planned `p34-boot16-entry-probe1` cell with tests5.

#### 65.3 Physical Entry Probe Rejected Before Any Target Write

Original `p34-boot16-entry-probe1` ran
2026-10-06T18:43:04.173144Z..18:43:17.745985Z,13.5728447s,exit1/no timeout.
It failed during RUNNING media admission with
`active storage/display transfer or WWDT prevents long halt`. Fresh R2-B
header/runtime-table/main-WFI matched before the failure. Display DMA had8300
remaining byte transfers, CTRL0x1093 and SRAM source0x200271DF. SD DMA count0,
SDIO2 DTCNT0/DTCTRL0x9B/status0,command0x44D,response-command13,response0x900,
DMA CTRL0x2A81 and SRAM endpoint0x20052E10 were observed. The short-circuiting
guard stopped before reading WWDT; do not describe WWDT as observed inactive.

There were ZERO target data writes: no pause change,breakpoint,halt,Flash write,
release or reset. Original pause was0x1000,DFSR8,DEMCR0x01000000,FP_CTRL0x261,
all six comparators zero. Normal native Close returned; TAR/CSW/DP restoration
and unchanged native history are verified. No debugger remains. The prior
complete App/Boot and30s health evidence remains historical; this failure does
not produce a new full-image or health observation.

Root offline `.cache/p34-boot16-entry-probe1-analysis1/result.json` reparses
the two original native logs:1451 native calls,408 target reads,0 target writes,
one completed Close; all352 current and archived source bindings match.
SHA256 `04a42497b609880fdaecf1062662de9ba72267f6794bfde80a6e60bd0f2c7c19`.
Executed entry/probe sources and all raw failure evidence are now frozen.

Next question is narrow: the RUNNING display-count-zero precondition appears
over-restrictive for an ordinary source-qualified SRAM-to-SPI refresh. Root
requested independent reconciliation and a successor allowing only this known
display activity before the exact main-WFI halt, while preserving zero-count
held admission and all SD/USB/NOR/software guards. Do not simply retry the same
probe to hunt for a passing sample, disable/drain peripherals, weaken held
storage protection or report this as an MCU defect or a speed improvement.

#### 65.4 Running Display Successor, Not A Blind Retry

Independent review closed BOOT16-RUN-01 as a safely rejected preparation
predicate and confirmed the original zero-write/Close/source audit. Its selected
successor permits only source-qualified display activity before the main-WFI
halt, not active SD/storage. A nonzero byte-DMA chunk must have CTRL0x1093,
SPI peripheral0x4001300C,count<=65535 and conservative
`SRAM_START <= memory && memory+65535 <= SRAM_END`. This bounds bytes already
transferred as well as the remaining counter; odd byte addresses remain valid.
The actual0x200271DF source passes this bound.

New `recovery_confirm/boot16_display_entry.py` inherits the frozen control and
all same-context release logic. Its first held observation permits one read-only
completion phase of at most1s, including every native-call deadline; DMA
mode/peripheral/source must remain unchanged,count must not increase and must
reach zero. No DMA/IRQ command is issued and no CPU instruction runs during
this phase. The subsequent two full held-media observations use the original
zero-display/zero-SD rules unchanged. Timeouts,reset or drift retain halt/pause;
there is no random retry to hunt for a quiet frame.

`Tools/ota/p34_boot16_display.py` privately injects this Control into the exact
frozen execute/worker implementation. It checks the original entry/probe/failure
hashes and includes original evidence and the correct frozen
`MDK-ARM_F435/Platform/HAL/HAL_Display.cpp`. An initial host preflight referenced
the wrong USER/HAL location and rejected before creating outputs; it did not
access hardware. Display-tests1 passes4 methods including5 inherited owner
regressions. Display-tests2 adds native-deadline capping and passes5 top-level
methods,362 input bindings; tests1 is preserved. Tests cover running8300->held0,
held progress to0,stuck/increasing counts,endpoint/mode/reset changes and
storage/USB/WWDT/cache/span rejection.

Planned next cell: `.cache/p34-boot16-entry-probe2`, consuming display-tests2.
Only the diagnosed display admission/completion changes; the section65.2
600s/720s lifetimes, six raw logs, zero payload writes/reset, same-context release,
pause restoration and30s health remain. This is a finite successor after new
evidence and a tested repair, not a replay of probe1. No execution is scheduled
until the consolidated successor review closes; no additional user permission
is needed for this unchanged preparation scope. Group16 is still not installed.

The original reviewer closed this successor preparation with no remaining
finding. It independently executed5 methods in20.488s and checked all362
current/source-copy bindings plus all183 loaded project modules. Display-tests2
SHA is `1e70ad02675804ddb9da4703e7a541c4bd3ff8f0efbe5d584ededdbf22e4ea1a`;
runner SHA is `c3388afb566f35ede0bc42031b1222807ae94ca798cadc3859bf92fdaff2f9c8`.
Root is now starting the planned probe2 cell. This closes preparation only,
not the device outcome, Boot programming route or any performance target.

#### 65.5 Probe2 Rejected Before Halt At Suspended USB Admission

Probe2 ran 2026-10-06T19:11:48.414916Z..19:12:01.951853Z,
13.5369379s,exit1/no timeout. Running-display admission progressed, then the USB
guard rejected raw connection word `0x00000104` at0x20053538 and raw MSC word0
at0x200007E8. WWDT0 at0x40002C00 was actually observed this time. No target data
write occurred: no pause/comparator/selector/halt/release/reset or Flash action.
Native Close returned, TAR/CSW/DP restored, native history unchanged and no
debugger remains. Executed display successor/runner and its raw failure are
now frozen as well as probe1.

Root offline `.cache/p34-boot16-entry-probe2-analysis1/result.json` reparses
the two original logs:1466 native calls,411 target reads,0 target writes and
one completed Close; all362 current/source-copy bindings match. SHA256
`f3f52f269c2dfc62c4d7364e49de737b05ff64932a80399c1042763a82f02b71`.
The complete already-captured legacy media snapshot has no decoded blocker;
confirmation flags0x010104 were read, but health-ready0x20053ABC was not yet
read. Do not claim the unexecuted downstream qualification passed.

Frozen USB getter and suspend source interpret low byte4 as SUSPENDED and the
next byte1 as prior DEFAULT state, with address/remote fields zero. The suspend
handler saves current state to old_conn_state before storing4; wakeup restores
the old state. Root requested independent classification of this exact
suspended-from-unconfigured/BOT0 combination before choosing a successor or
asking for actual USB isolation. Do not assume it proves an active storage
transfer, blindly repeat the probe, or silently delete the USB protection.

#### 65.6 Exact Suspended-Default USB Successor

Independent review confirmed the original probe2 failure/audit and classified
BOOT16-USB-02: the exact32-bit connection word0x00000104 with rawMSC0 may be
admitted for this same-context preparation. Its prior state is DEFAULT1 and
wakeup restores DEFAULT, not CONFIGURED. The frozen core dispatches non-EP0
class traffic only while CONFIGURED; MSC bulk endpoints initialize only on the
addressed-to-configured transition, and class reset/suspend/wakeup event handlers
are storage no-ops. HAL uses USB_VBUS_IGNORE, so this is NOT physical-disconnect
evidence. No user USB unplug, disable or drain is needed for this exact case.

New `boot16_usb_entry.py` preserves full raw USB words and separately records
current/prior states,address,remote-wakeup and the exact admission reason.
Only raw104+rawMSC0 is added: generic suspended4,204,304,nonzeroaddress/remote,
nonzeroMSC,configured or addressed states remain rejected. Running and held
snapshots recheck this. Existing unconfigured0/1 idle behavior,display span and
one-second completion,SD/WWDT/USB/dirty-cache rejection, and same-context
release/health/Close remain unchanged.

`Tools/ota/p34_boot16_usb.py` is the new source-bound entry, not an edit of either
executed predecessor. USB-tests1 passes4 top-level methods including5 inherited
owner/log/Close and4 display/storage/deadline regressions. USB-tests2 retains
these tests, records the decoded reason and adds frozen USB configuration/header
bodies to source binding. Consume the actual latest receipt, not a test-count
assumption. The prospective no-payload-write cell is
`.cache/p34-boot16-entry-probe3` with the same section65.2 lifetimes/log layout.
It is pending bounded successor review, with no hardware action yet. This work
does not replace Boot, access BCB or produce a speed sample.

The independent reviewer closed USB successor preparation with no remaining
finding:4 methods independently executed in21.728s,384 current/source-copy
bindings and all186 loaded project modules match. USB-tests2 SHA256 is
`57a3e131e4d75fd8f2b9b3b21fe6c3131c3fb7754bf9983788020b7aa71bbf85`;
runner SHA256 is `e4940d06fa6dff59e773b8e68ee55e06da61d17e136e4f0c2bb33ac35a60228c`.
Root is now starting the already-planned probe3 with tests2. No Boot
programming or extra physical-disconnect claim is implied by this closure.

### 65.7 Probe3 closed; Boot programming is still pending

The planned `.cache/p34-boot16-entry-probe3` completed in 51.2102948s,
2026-10-06T19:42:32.714178Z through 19:43:23.924469Z. Root's original-log
reconciliation is `.cache/p34-boot16-entry-probe3-analysis1/result.json`
(SHA256 `c2ca0464fbfc1eeb4bd893440124e35a8ee01147e7a67a6bb74cc9a03eecc66c`).
The existing independent reviewer closed BOOT16-PROBE3-CLOSURE PASS:
384 input/source-copy bindings, 9627 native calls, 2510 target reads, exactly
18 planned debug stores, one native Close, four qualified media records,
and 28 healthy samples over 30.1764732s. All 13 original header/vector/WFI
chunks match frozen B. CPU selector groups agree on PC080461C0,
xPSR21000000, MSP20057FA0, special04000000, FPCCRC0000018. The earlier
conversation-summary MSP20057DA0 was a transcription error, not device data;
future restoration compares the actual saved context, never that constant.
Watchdog-freeze returned to its original1000, no reset was performed and
original Boot was untouched. Native history was unchanged; no debugger remained.
Do not rerun this successful qualification for logs.

BOOT16-PROGRAM-DESIGN selects fresh held full Boot64/App B capture, eight
bounded2KiB first16KiB sectors, complete expected Boot64/B postcapture, then
one same-context release and paired health. It is not programming approval.
Persist preimages and exact context/debug ownership before any Flash attempt.
Restoration is a separately reconciled consumed-once retained-context route;
suffix/App mismatch, uncertain native call, busy/error/reset or attempted
release prohibit automatic cleanup/retry. A settled unlocked controller is
eligible for only CTRL0 then CTRL80, with exact status20 and fresh guards
before each store; status0 is not silently accepted as completion.

Prepared verification-only full Boot is
`.cache/p34-boot16-assets1/expected-complete-boot.bin`, SHA256
`01e4b9e162bfaaf9fda070aa13c0cec3f377b8d696db01f731e0ab3d1464e527`.
Never program this whole64KiB file. The first16KiB candidate and original
restoration files in the same directory have SHA256
`8599a7162ad64a6daa2571653f4ea575d297fde6c032ee8355d55312492bbb9e` and
`9c8daee1f93668ced63a03bfa23d4eb31791a1d7496d84c39be5ae77fbcbe6f7`.
The new `boot16_program` body and `boot16_settle` adapter are preparation
only; neither has been device-executed. Settlement-tests1 predates a
pre-store guard refinement and is not evidence for the changed source.
No new throughput or installation sample exists. Latest actual OTA remains
17.898428s transfer /16.428929 decimal kB/s and20.494210s END-to-identity;
the50kB/s and20s goals remain unmet. Physical post-OTA BCB observation and
the historical NOR native-log gap remain unclosed, not inferred from RAM.

### 66. User-directed standard SEGGER group16 screening

The user explicitly requested testing group16 now after challenging the custom
flash-driver detour. Root switches to installed SEGGER V8.18 Commander with
AT32F435RGT7/SWD1000, not the unfinished custom programming coordinator.
Retire the no-reset/same-CPU-context requirement for this route: standard RAM
flash-loader scratch and a deliberate post-verification reset/start are intended.
This does not authorize programming outside Boot[08000000,08004000), mass erase,
arbitrary EEPROM/NOR edits, supply interruption or release/publication.

Finite stages: fresh original Boot64/B capture; known R2 main-WFI halt with
watchdog freeze and settled storage observation; standard loadbin of the exact
16384B candidate with explicit noreset; full expected Boot64 and unchanged B
verify/readback; deliberate reset/start; full identity and30s health. The original
first16KiB remains ready for a diagnosed necessary restoration through the same
standard loader, never a blind automatic retry. All original failed/custom
tooling evidence remains intact. Commander uses no standalone erase command.
Each stage has180s process limit, explicit project-local settings/log/readbacks
under `.cache/p34-group16-commander1`; the existing SEGGER native-history-only
exception remains. Root is sole hardware operator; J-Link3.3V/GND stays connected.

Then prepare one new legal header-only30277->30278 FULL OTA, using the same R2
execution body and sender parameters as the30276->30277 group1 baseline.
Measure BEGIN-to-END and END-to-reconnected identity separately; package/header
identity changes are explicit. No replay of the successful earlier OTA. This is
single-run group16 screening, not50kB/s or general20s acceptance, nor a general
changed-executable comparison. Phone start remains the user-owned UI action.

#### 66.1 Group16 physically installed by standard Commander

All five stages in `.cache/p34-group16-commander1` completed. Fresh before
Boot64/B match the originals. The hardware comparator stopped at PC080461C0,
MSP20057FA0; SD/display DMA counts and SDIO data count/status were zero, caches
clean. Standard `loadbin candidate-first16.bin,08000000,noreset` then succeeded.
Original `program/sdk.log` explicitly compares, erases and programs only
08000000-08003FFF, eight2KiB sectors. Its reported download total is2.279s;
this is debugger programming time, NOT an OTA timing result.

Both standard verifybin checks succeeded, and independent binary readbacks show
full Boot64 SHA01e4b9e162bfaaf9fda070aa13c0cec3f377b8d696db01f731e0ab3d1464e527
and unchanged619580B R2-B SHAe4737cfcbbb884c4a7fa407ea733486425674c7ed2723d0f8cf3263beb4e8802.
The existing reviewer independently corroborated the exact erase/program range,
preserved suffix and B bytes. RAM-loader-era fault/T-bit changes are retained in
the original program log; that state was deliberately reset, not resumed as
healthy original context. After `r/g`, runtime VTOR08010800, flags010104, SD1 and
zero CFSR/HFSR were observed. The following full readback and paired30s health
observations pass, with ready1 and advancing loop/feed counts. All Commander
processes closed; physical supply remained3.300V and connected.

The new `.cache/p34-group16-screen/assets/full.etu` is294068B, SHA256
c5564c76efafa8b8e7cea766eae0d46de59881a45b8c0c394c954bcdab3477f5.
It targets30278/3.2.78-r2c from30277, same executable outside the96B header.
Existing encoders and native decoder passed exact reconstruction/Boot validity
and four rejection cases. Sender check binds334 source records and exact
schema9 configuration, reusing the normal original-query/snapshot collectors.
This is development preparation, not independent acceptance or measured gain.

The phone was connected and its current completed R2 capture independently
matched the original snapshot. Its8 slots required one existing archive operation:
the old30275 capture1791112203004255-d72cb83d6d8ace1100542bab was copied/verified
locally then moved within the App to p34-archived-observations. Latest30277
capture1791304064275106-3ef9bdad22c698f5be45adf8 and configuration stayed unchanged;
7 slots remain, USB closed, no deletion or OTA in this preparatory step.
The new finite OTA coordinator is now being launched at
`.cache/p34-group16-screen/trial`. No group16 OTA timing is available yet.

#### 66.2 Group16 OTA ready, awaiting the user's Start action

Coordinator launched2026-10-06T21:14:38Z, with6000s bound. After fresh phone
inspection and7-slot admission, the ordinary sender reported READY_FOR_FULL_INSTALL_START
at21:18:32Z, PID16144, capture1791321470258661-e783c69dc0c036b5200d5678,
baud921600/window28/target30278. Root separately revalidated the original query
producer, matching configuration/capture/PID, zero starts/ends, healthy/no loss,
and exact downloaded294068B package SHA c5564c76efafa8b8e7cea766eae0d46de59881a45b8c0c394c954bcdab3477f5.
User was asked to tap Start once and keep App foreground/USB connected.
At21:28:19Z the original health still has upgradeStarts0/upgradeEnds0; no OTA
has begun. This is the actual human-action boundary, not another authorization
request. Keep the bounded owners active; do not automate taps or repeat/reflash.

After completion, reuse the original snapshot via the bound trigger; the prepared
`.cache/p34-group16-screen/postcheck.py` reads public MONO boundaries and performs
standard no-reset Boot64/C full readback plus paired health only after all three
phone/network owners close. It has not run yet. Do not run the old B postcheck or
replay30276->30277. Native Boot install subphase instrumentation remains absent;
report END-to-verified-identity as that combined interval, not pure Flash time.

#### 66.3 First actual group16 OTA result and retained C

The user completed the planned30277->30278 upgrade. Original snapshot is
`.cache/p34-group16-screen/trial/cells/s04/finished/snapshot.jsonl`,1011018B,
SHA25617748eaea5d7297b0c26edd2688bc3895fc547b50f083db2faf097dc36f2fe56,
8940 records/8937 producer lines. The original completed query/snapshot trigger
passed again; no transfer was repeated. All three coordinator/network/phone
owners exited0 without forced termination. Private ADB5062 closed with its
original key unchanged. Current results:

| Public MONO interval | Original group1 | Group16 screen |
| --- | ---: | ---: |
| BEGIN budget start to END ACK | 17.898428s | 17.483523s |
| END ACK to reboot/reconnect identity | 20.494210s | 17.029138s |
| Combined | 38.392638s | 34.512661s |
| Transfer decimal kB/s | 16.428929 | 16.819722 |

The END-to-identity difference is3.465072s/16.9076%; combined difference is
3.879977s/10.1060%. These are one-run observations, not a stable-distribution
claim or pure Flash/EEPROM timing. The nominal5.68s estimate was not achieved
as the measured combined saving.50kB/s and general20s goals remain unmet.

The new link summary has2298 unique/sent DATA,0 retransmissions and all2298
ACKs OK, with0 duplicate/error/malformed/early-invalid/early-unsent.73 durable
events end at294068B; ACK P99 is145698us. Link's own17480900us transfer stopwatch
is a distinct clock scope; public MONO above remains the comparison clock.
Both runs have two reconnect attempts (first no-verdict, second complete).
GET_INFO calls/failures fell11/10 to8/7; those readiness/reconnection waits
remain part of the combined interval, not an independently measured Boot phase.

`.cache/p34-group16-screen/analysis/comparison1.json` reconstructs both original
timing sets and link summaries. Runtime config changes are exactly
firmwareLatestUrl plus current/target version+hash and package size+hash;
all performance controls match. The package is16B larger and the target changes
only the96B version/integrity header, so this is an equivalent-shape header-only
screen, not evidence for arbitrary executable-changing upgrades.

The prepared standard postcheck completed without reset, reflash or EEPROM/NOR
payload commands: `.cache/p34-group16-screen/post-ota/result.json`.
Full65536B Boot equals the group16 expected image SHA
01e4b9e162bfaaf9fda070aa13c0cec3f377b8d696db01f731e0ab3d1464e527;
full619580B App equals30278 SHA
71b762978eed25aa30978db1131c25264b0cbbab6d7b97768501649f82d8d95a.
Paired30s health is ready with stable epoch and increasing loop/feed counters;
VTOR08010800, flags010104, SD1 and zero CFSR/HFSR. No debugger remains.
Retain group16 and C30278 for subsequent work, with production defaults and
historical failed/frozen evidence unchanged. Physical BCB and new mapped backup
were not recaptured by this postcheck; it does not close the old NOR log gap.

The existing independent reviewer closed GROUP16-OTA-CORROBORATION PASS after
recomputing both original envelopes/public metrics, configuration/package and
pre-BEGIN2M PHY bindings, all DATA/ACK samples, and postcheck bytes. No concrete
discrepancy was found. The two raw health read starts are30.003740s apart and
loop/feed each advance8385 with epoch0/ready1; this is paired observation, not
the earlier28-sample continuous monitor. Each run also has one failed reboot
discovery; zero-error claims apply to DATA transfer, not every reconnect call.
The installed experimental state is retained, with no further experiment started.
