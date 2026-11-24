# P1-6 implementation evidence (2026-07-29)

> Implementer: Codex P1-6 implementation session.
> Status: in progress. The 20-point matrix below was frozen before injection.
> All 14 automatic rows now have independent true-board artifacts and pass.
> Six rows require real physical power removal and remain pending user
> participation. This implementation session does not mark P1-6 complete.

## 1. Scope and immutable inputs

Baseline and checkout:

```text
origin/main = bd9f4da0bee476d4ee2f4ba3f3e25b1e17b0d9ec
checkout    = D:\github\my\E-Track\.cache\checkout-A-P1-6-20260729
branch      = p1-6
```

The frozen `PLAN-OTA.md` and `docs/ota-binary-contracts.md` are inputs. They
must not be changed to accommodate the test harness or observed behavior.
P2 staging, parsing, decryption, decompression, and patching are out of scope.

The evidence-only Boot hook is required to be compile-time disabled by
default. After the automatic matrix, production Boot and App must be rebuilt
without the hook and restored to the board before this evidence is committed.

## 2. Asset and state notation

- `V0/H0`: known-good current App and backup. `H0` is the full-image
  fw_header double-zero SHA-256. The raw binary SHA-256 is recorded separately.
- `V1/H1`: valid candidate with `V1 > V0`.
- `VR/HR`: valid recovery image.
- `S0`: internal App=`V0/H0`; BCB=`STAGED,try=3,phase=NONE,resume=0,
  cur=V0,cand=V1,backup=V0`; candidate=`V1/H1`; backup=`V0/H0`;
  recovery=`VR/HR`.
- `A(k)`: BCB=`APPLYING,phase=APPLY,resume=k`; blocks below `k` have been
  programmed from candidate and fully read back.
- `T(n)`: internal App=`V1/H1`; BCB=`TEST_BOOT,try=n,phase=NONE,resume=0`.
- `R(k)`: BCB=`ROLLBACK,phase=ROLLBACK,resume=k`; blocks below `k` have been
  programmed from backup and fully read back.

Frozen true-board assets:

```text
V0 vcode=20800 length=563636 blocks=138
  raw SHA-256         5f8e560b752ac38a183279f59206b06d128aca8af1866ca397f9080bd858a5e4
  double-zero SHA-256 5984c7d515ce3c076cb537a59b3a03a01352c197dfaf79f6059a83d8b13b8ef3
  header CRC32        130841ec
V1 vcode=20801 length=563636 blocks=138
  raw SHA-256         132b9fdcb59c1425b8f6e16c8a97b38d4fa3810e471648b343665be4cbcda1b0
  double-zero SHA-256 095fa307707a6260dbd0957eb2c3b953a191910d0b8f1547a28e6638b011448d
  header CRC32        ac62aca2
```

The fresh S0 slot snapshot verified candidate=`V1/20801`, backup=`V0/20800`,
and recovery=`V0/20800`, each with length 563636 and its frozen hash.

For every row, the run artifact must contain the raw BCB A/B bytes and
arbitrated fields before injection, slot headers and validated versions,
injection checkpoint and mechanism, every observed post-reset BCB state,
final internal App version, raw binary SHA-256, fw_header double-zero SHA-256,
and exactly one terminal result: `BOOTABLE` or `PHYSICAL_RECOVERY`.

## 3. Frozen 20-point matrix

`AUTO` means J-Link halt/reset or a deterministic evidence-only command.
`PHYSICAL` means real board power removal while a device write transaction is
in flight; J-Link reset is not an acceptable substitute.

| ID | Class | Pre-injection state | Injection location and method | Required post-reset trajectory | Required final image/result | Execution |
|---|---|---|---|---|---|---|
| 01 | AUTO | `S0`; candidate metadata remains valid | Flip one candidate payload bit after slot installation, leaving ETSL and BCB metadata unchanged | `STAGED -> ROLLBACK/phase=2/resume=0 -> CONFIRMED(V0)` | `V0/H0`; `BOOTABLE` | PASS: `r3/row-01` |
| 02 | AUTO | `S0` | Arm checkpoint after complete candidate validation and before the `STAGED -> APPLYING` BCB commit; ordinary J-Link reset | Old `STAGED` remains authoritative; validation and apply restart | `V1/H1`; `BOOTABLE` | PASS: `r3/row-02` |
| 03 | PHYSICAL | `S0` | Remove board power while the inactive BCB record for `APPLYING/phase=1/resume=0` is being written | Arbitration yields only old `STAGED` or complete new `APPLYING`; no mixed semantic fields | `V1/H1`; `BOOTABLE` | PENDING USER PHYSICAL POWER |
| 04 | AUTO | `A(0)` | Arm checkpoint after `APPLYING` is durable and before the first internal-Flash erase; ordinary J-Link reset | Resume at block 0 | `V1/H1`; `BOOTABLE` | PASS: `r3/row-04` |
| 05 | PHYSICAL | `A(k)`, target `k=64` unless asset length is smaller | Remove board power while the second 2 KiB sector erase of apply block `k` is in flight | `resume=k` remains; reboot erases the whole 4 KiB block again | `V1/H1`; `BOOTABLE` | PENDING USER PHYSICAL POWER |
| 06 | AUTO | `A(k)`, target `k=64` unless asset length is smaller | Arm checkpoint after the complete 4 KiB erase and before programming block `k`; ordinary J-Link reset | `resume=k` remains; reboot re-erases then programs block `k` | `V1/H1`; `BOOTABLE` | PASS: `r3/row-06` |
| 07 | PHYSICAL | `A(k)`, target `k=64` unless asset length is smaller | Remove board power during the middle of the word-program loop for apply block `k` | `resume=k` remains; reboot first re-erases then rewrites block `k` | `V1/H1`; `BOOTABLE` | PENDING USER PHYSICAL POWER |
| 08 | AUTO | `A(k)`, target `k=64` unless asset length is smaller | Arm checkpoint after full block readback and before `resume_block=k+1` commit; ordinary J-Link reset | Block may be complete but is not durable progress; reboot repeats block `k` | `V1/H1`; `BOOTABLE` | PASS: `r3/row-08` |
| 09 | AUTO | `A(k+1)`, target `k=64` unless asset length is smaller | Arm checkpoint after the middle progress commit; ordinary J-Link reset | Resume at `k+1`; committed prefix is not erased again | `V1/H1`; `BOOTABLE` | PASS: `r3/row-09` |
| 10 | AUTO | `A(N)` | Arm checkpoint after final resume commit and before post-copy full-image validation; ordinary J-Link reset | Copy loop is skipped; full validation leads to `TEST_BOOT` | `V1/H1`; `BOOTABLE` | PASS: `r3/row-10` |
| 11 | AUTO | `T(3)` | Arm checkpoint after `APPLYING -> TEST_BOOT,try=3` commit and before try decrement; ordinary J-Link reset | Next boot durably commits `3 -> 2` before handoff | `V1/H1`; `BOOTABLE` | PASS: `r3/row-11` |
| 12 | AUTO | `T(2)` | Arm checkpoint after `boot_try 3 -> 2` commit and before App handoff; ordinary J-Link reset | Next boot commits `2 -> 1`; healthy App later confirms | `V1/H1`; `BOOTABLE` | PASS: `r3/row-12` |
| 13 | AUTO | `CONFIRMED,cur=V1` | Arm App-side checkpoint after `TEST_BOOT -> CONFIRMED` is durable and before continued App execution; ordinary J-Link reset | Boot validates and directly jumps to confirmed `V1` | `V1/H1`; `BOOTABLE` | PASS: `r3/row-13` |
| 14 | AUTO | First boot is `T(3)` | Perform three ordinary resets before the 30-second App confirmation window; allow fourth boot to run | `T3 -> T2 -> T1 -> T0 -> ROLLBACK/phase=2,resume=0 -> CONFIRMED(V0)` | `V0/H0`; `BOOTABLE` | PASS: `r3/row-14` |
| 15 | PHYSICAL | `T(0)` | Remove board power while the inactive BCB record for `ROLLBACK/phase=2/resume=0` is being written | Arbitration yields only old `T(0)` or complete new `R(0)`; old state retries the same atomic transition | `V0/H0`; `BOOTABLE` | PENDING USER PHYSICAL POWER |
| 16 | PHYSICAL | `R(k)`, target `k=64` unless asset length is smaller | Remove board power while the second 2 KiB sector erase of rollback block `k` is in flight | `resume=k` remains; reboot erases the whole 4 KiB block again | `V0/H0`; `BOOTABLE` | PENDING USER PHYSICAL POWER |
| 17 | PHYSICAL | `R(k)`, target `k=64` unless asset length is smaller | Remove board power during the middle of the word-program loop for rollback block `k` | `resume=k` remains; reboot first re-erases then rewrites block `k` | `V0/H0`; `BOOTABLE` | PENDING USER PHYSICAL POWER |
| 18 | AUTO | `R(k+1)`, target `k=64` unless asset length is smaller | Arm checkpoint after the middle rollback progress commit; ordinary J-Link reset | Resume at `k+1`; committed prefix is not erased again | `V0/H0`; `BOOTABLE` | PASS: `r3/row-18` |
| 19 | AUTO | `CONFIRMED,cur=V0` after rollback | Arm checkpoint after rollback final confirmation and before App handoff; ordinary J-Link reset | Boot directly validates and jumps to backup version | `V0/H0`; `BOOTABLE` | PASS: `r3/row-19` |
| 20 | AUTO | `T(0)`; internal image remains `V1/H1` | Corrupt both backup and recovery payloads, then ordinary J-Link reset | `T0 -> R(0) -> PHYSICAL_RECOVERY`; internal App must not be erased before a valid source exists | Internal still `V1/H1`; `PHYSICAL_RECOVERY` | PASS: `r3/row-20` |

The matrix is frozen as of 2026-07-29 before any injection. Row substitution,
class changes, or weakened expected outcomes require explicit review; editing
the frozen OTA plan or binary contract is not an allowed shortcut.

## 4. Automatic run ledger

Evidence root:

```text
.cache/p1-6-auto-evidence-20260729-r3
```

Every `row-XX` evidence bundle is audited by reading `row-summary.json`
together with the adjacent `row-manifest.json`. The summary records the
execution, raw BCB observations and arbitrated fields along the trajectory,
checkpoint and injection mechanism, final App hashes, and terminal
classification. The manifest records the candidate, backup, and recovery slot
identities, versions, and hashes. Together they provide the complete evidence
set for each matrix row.

| ID | Injection and observed trajectory | Final |
|---|---|---|
| 01 | Candidate payload bit corruption; `STAGED -> R(0) -> CP11` | V0, `BOOTABLE` |
| 02 | One J-Link process reaches `CP1(0,0)`, writes the complete retarget block magic-last, resets, and reaches `CP1 -> CP2 -> CP12` | V1, `BOOTABLE` |
| 04 | `CP2(1,0)` reset; next observation `CP3(1,0)` | V1, `BOOTABLE` |
| 06 | `CP4(1,64)` reset; next observation `CP3(1,64)` | V1, `BOOTABLE` |
| 08 | `CP5(1,64)` reset; block 64 repeats from `CP3(1,64)` | V1, `BOOTABLE` |
| 09 | `CP6(1,65)` reset; resumes at `CP3(1,65)` | V1, `BOOTABLE` |
| 10 | `CP7(1,138)` reset; copy skips to validation and `CP8(0,3)` | V1, `BOOTABLE` |
| 11 | `CP8(0,3)` reset; durable decrement reaches `CP9(2,0)` | V1, `BOOTABLE` |
| 12 | `CP9(2,0)` reset; durable decrement reaches `CP9(1,0)` | V1, `BOOTABLE` |
| 13 | App confirmation halts at `CP12(20801,4)`; ordinary reset directly boots confirmed V1 | V1, `BOOTABLE` |
| 14 | `CP8 T3 -> CP9 T2 -> CP9 T1 -> CP9 T0 -> CP10 R0 -> CP11` | V0, `BOOTABLE` |
| 18 | Rollback reaches `CP6(2,65)`; reset resumes at `CP3(2,65)` and finishes at `CP11` | V0, `BOOTABLE` |
| 19 | Rollback reaches `CP11`; ordinary reset directly boots confirmed V0 | V0, `BOOTABLE` |
| 20 | Backup and recovery payloads are both corrupted; ordinary reset reaches `CP13(0xFFFFFFFD,5)` without erasing internal V1 | V1, `PHYSICAL_RECOVERY` |

The aggregate audit found `14/14` summaries, with zero missing or invalid rows.
Rows 01, 14, 18, and 19 ended on frozen V0; rows 02, 04, 06, 08-13, and 20
ended on frozen V1. Row 20 is the only `PHYSICAL_RECOVERY` terminal.

The following diagnostics are explicitly invalid and are not cited as pass
evidence:

```text
.cache/p1-6-auto-evidence-20260729-r3/invalid-row-02-disconnect-gap
.cache/p1-6-matrix-20260729/02-candidate-validated-reset
.cache/p1-6-matrix-20260729/02-candidate-validated-reset-r2
.cache/p1-6-matrix-20260729/02-r2-candidate-validated-reset
```

They used or investigated a disconnect gap between control retarget and reset.
The valid row 02 keeps retarget write/readback/verify, reset/continue, and the
first capture in one J-Link process.

## 5. Host and build verification

Final host rerun:

```text
fw_header vectors       16/16 PASS
Boot Ymodem/ETSL        19/19 PASS
BCB                     27/27 PASS
Boot state machine      96/96 PASS
P1-6 control protocol   21/21 PASS
OTA golden vectors       9/9 PASS
```

A fresh GCC 13.3.1 Release build was created at
`.cache/p1-6-test-gcc-20260729-final` with `P1_6_TEST_ENABLE=ON`. It completed
with zero errors and the repository's existing App warnings. Boot was 18208
bytes and App was 563636 bytes. In both ELF files `.p1_6_control` was exactly
`0x200` bytes at `0x20057E00`.

## 6. Physical run ledger

Rows 03, 05, 07, 15, 16, and 17 require the user to be physically present.
They are intentionally not claimed. The two EEPROM rows require a controlled
power-cut fixture or hardware trigger capable of hitting the approximately
millisecond-scale page-write window; an operator reacting to a console line is
not deterministic evidence.

## 7. Final production restore

Production evidence root:

```text
.cache/p1-6-production-restore-20260729
```

Before replacing the test Boot, its validated control protocol cleared BCB A/B;
the result reported no active record. `deploy-ota-bootstrap.ps1` then performed
a fresh GCC Release build with `P1_6_TEST_ENABLE:BOOL=OFF`, finalized App 2.8.0
(`vcode=20800`), and serially flashed Boot and App. Neither production map
contains `p1_6`, `P1_6_TEST_ENABLE`, or `boot_p1_6_test`.

```text
production Boot     14216 bytes
  raw SHA-256 c42b503aea443282e528688c92b1bd5bc93d6937f2a3c63bf3bf051ed7246e7d
production App      563044 bytes
  raw SHA-256 aa9f71f1fa23dcd3b7cff076d421de28bd9740f05fe27bec947eb00f15fd89c0
  double-zero SHA-256 c9531153649fa76ba982c7037d36d90a2ca78cb1fca6ee19cbdd309f6ec4b85b
  header CRC32 c793bb15
```

Both ordinary-reset gates reached App-range PCs with `VTOR=0x08010000` and
`CFSR=0`:

```text
reset 1 PC=0x08042CE4
reset 2 PC=0x0804A722
```

The current production App map resolved `_SEGGER_RTT=0x20044E04`. Live memory
readback was `53 45 47 47 45 52 20 52 54 54` (`SEGGER RTT`). Both bounded RTT
captures contained the current Boot handoff, `QSPI: JEDEC=0xEF4018
whitelisted, OTA enabled`, and `OTA: BCB already CONFIRMED vcode=20800`.
No `JLinkRTTLogger`, `JLinkRTTViewer`, `JLink`, or `JLinkGUIServer` process
remained after the run.

## 8. Acceptance status

P1-6 remains `进行中`. Even after all automatic rows pass, the six physical
rows remain pending until actually executed. Only a different non-implementation
session may independently accept all 20 rows and mark the card complete.

## 9. Physical power-cut preparation (2026-11-24)

Preparation owner: Codex root / `P16-PHYSICAL-PREP-20261124`.
Source entry: main `13518dc76200418c7ff7dc143c9b4e4e91d4f4eb`,
matched to fresh remote main. Existing pending documents are preserved.
The owner requests starting the preparation and notification when physical
help is needed. This is not a new formal execution or Boot-replacement grant.

Status: `PREPARATION_ONLY`; no device command, shutdown, reset, flash,
installation, power cut, CI, commit or push has been performed in this step.
The six PHYSICAL rows remain unobserved. The earlier 14 AUTO results remain
historical evidence; a later formal successor must evaluate their dependencies
and original anchors, not replay them merely because the operator changed.
The original P1-6-v3 bundle is at Git object
`362653bb38d6fd1f9fb9bdca0339c1a6d6e77547`,
`docs/acceptance-contracts/P1-6-v3/final-matrix.json`.

### Source and tool constraints

- The already inspected `PCB/Trace.enet` routes normal USB/battery power
  through the U21/Q9 latch to U17 and `3V3_MCU`. The MCU, BCB EEPROM and
  external Flash share that switched rail. A separate bench supply is not
  a prerequisite and does not remove the need to press the start key.
- H2 pin 6 is wired directly to `3V3_MCU`. A debugger supply there could
  bypass the latch; a VTref-only connection is different. Actual cable
  wiring is unknown. The USB-powered CH340N signal path also needs a
  residual-voltage check. These are unmeasured possibilities, not defects.
- `HAL::Power_Shutdown()` sets a request; the App event monitor later
  drives PD2 low. This is not an established host remote-power API, and
  that App monitor does not run during Boot apply/rollback.
- `boot_platform_flash_erase_4k()` calls the blocking vendor erase routine.
  Calling shutdown after it returns cannot prove power loss during erase.
  A qualified trigger must account for instruction stalls and rail decay,
  rather than assume an interrupt or host command hits the required window.
- `Tools/jlink/test-p1-6-matrix.ps1` only admits AUTO rows and binds the
  old 138-block assets. It was inspected, not executed. Do not use its
  reset points or old production restore as a current physical-test route.
  Reuse applicable control decoding and standard J-Link operations rather
  than creating a replacement flasher.
- A host process-name snapshot found no matching debugger/RTT/serial
  collector. This is not proof of exclusive physical ownership. Actual
  board identity, storage state, supply and ownership remain unchecked.

### Next actions and stop conditions

1. Ask the owner which USB, battery and J-Link connections are present,
   whether the debugger has a 3.3 V supply lead, and whether a multimeter
   or oscilloscope is available. Do not ask for the netlist again or
   request unplugging anything before resolving the connections.
2. Identify the actual board/firmware, confirmed BCB and staging state
   through a qualified bounded route before a mutation. Resolve recording
   and storage-idle conditions, exact original assets/readbacks and supported
   recovery first; never assume candidate 3.3.52 is currently installed.
3. Prepare the first idle power check with an external voltage observation
   on `3V3_MCU` relative to GND, a known shutdown route and owner key restart.
   Confirm header orientation before probing. A multimeter can screen
   residual DC power, not certify millisecond write-window timing. Screen
   blanking, lost BLE/SWD and RTC backup power are not main-rail evidence.
4. If the idle check proves true shutdown and repeatable restart, qualify
   a trigger and synchronized voltage/write-activity capture before the six
   faults. Use applicable device thresholds and real transaction timing.
   Do not start erase/write faults without this observation route. A test
   Boot, if necessary, needs a specifically bounded installation/restoration
   authorization; otherwise compare the minimum independent cutoff fixture.
5. Before physical execution, bind the exact inputs, protected regions,
   finite cells, deadlines, restoration and raw evidence to the existing
   task and acceptance route. Rows 03/05/07 must end at V1/H1; 15/16/17 at
   V0/H0, with the required state trajectory and confirmation. Unknown
   timing, unverified backup, conflicting ownership or unexpected device
   state stops dependent actions. J-Link rescue restores safety, not PASS.

No voltage trace, actual cutoff latency or new hardware result exists yet.
Only these preparation notes and the bounded board entry were edited.
Physical execution and independent acceptance remain separate next stages.

### Owner wiring follow-up (2026-11-24)

`P16-WIRING-20261124`: the owner confirms that both J-Link and USB are
currently connected and each can independently power the working MCU.
No multimeter or oscilloscope is available. These facts resolve the broad
supply/instrument question above; do not ask it again. Battery connection
and the exact debugger connector/power-versus-reference wiring have not
been independently established.

With two independent supply paths, cutting only one or issuing the App
shutdown request does not establish main-rail power loss. The next physical
prerequisite is identifying the actual J-Link connector and whether its
supply can be isolated while retaining valid SWD, ground and any required
reference connection. Request a clear connection/label photograph, not
another schematic. Do not tell the owner to pull an unidentified VCC/VTref
wire, change wiring while powered, or try a generic debugger power command.
No controllable supply capability of this particular probe is established.

The six write-in-flight cases stay NOT_OBSERVED. First qualify the cutoff
and synchronized rail/transaction observation, using borrowed measurement
equipment or a separately validated fixture if necessary. A reset, manual
USB pull, dark screen or lost debugger connection is not a substitute.
There is still no reason to purchase an additional bench power supply.
No target connection, power command, shutdown, reset, flash or physical
experiment was performed while recording this reply.

### USB-powered J-Link read check (2026-11-24)

`P16-JLINK-USB-ONLY-01`: the owner reports removing J-Link's 3V3 wire
and authorizes checking whether the debugger remains usable with USB power.
This is a bounded connection/read check, not power-loss fault injection.
No matching debugger process was present in the host snapshot. Enumerate
the probe first, require a single identified USB probe, then use the standard
SEGGER Commander at SWD 1000 kHz with generic CORTEX-M4 and GUI disabled.
Read CPUID (0xE000ED00), DHCSR (0xE000EDF0, twice) and four App vector words
(0x08010000). No halt, reset, flash, RAM write, target-power or fault command
is permitted; do not retry an uncertain target result. Deadlines are 20 s
for probe enumeration and 30 s for the target read. Fresh logs/settings/temp
are contained in `.cache/p1-6-power-preflight-20261124/jlink-usb-only-01/`.
The existing SEGGER native-history exception applies; it is not permission
to change probe supply configuration. A readable target proves SWD access,
not absence of signal backfeed, rail discharge or write-in-flight coverage.

Outcome: `TARGET_MEMORY_READ_OK`, one enumeration and one target session,
both exit 0. The probe identifies as ARM-OB STM32 (2012 firmware); SW-DP is
0x2BA01477 and CPUID is 0x410FC241. App vectors read as
`20058000 0801BFAD 0801C037 0801C037`. DHCSR is 0x01010001 in both samples
250 ms apart: S_HALT/S_LOCKUP clear, instruction-retirement activity present.
The SDK log contains no reset, halt or power-control call and no debugger
process remains. Native JLinkDLL.ini contents are unchanged. Commander reports
VTref=3.300 V, which is not independently validated rail-voltage evidence for
this probe. No programming or whole-App health test was requested or performed.
Original console/SDK logs and `result.json` are in the fresh directory above.
The existing six PHYSICAL rows remain NOT_OBSERVED.

### Idle shutdown route preparation (2026-11-24)

`P16-IDLE-POWER-01`: continue the owner-authorized preparation after the
successful USB-only J-Link read. The next experiment is a normal idle
shutdown/restart screen, not any PHYSICAL matrix row. Current source routes
the long-press through `HAL::Power_Shutdown()`; the event monitor calls
`App_Uninit()`, which requests configuration/storage save and recorder stop
before releasing POWER_EN. No ready host shutdown command was found.

Use the ordinary owner key action instead of a guessed RAM request address,
forced PC/function call, direct GPIO cutoff or new firmware. Existing ELF
discovery does not bind an artifact to the installed image. Do not infer
live recording, BCB or staging state from a header or from source alone.

Before asking for the key action, collect one bounded read-only header/core
baseline in `.cache/p1-6-power-preflight-20261124/idle-power-01/`: CPUID,
DHCSR and the 96-byte fw_header at 0x08010400. Use the already verified
single USB probe and standard Commander route, with a 30 s deadline.
No halt/reset/flash/power or target-memory write command is included.
Owner action will require no active recording, upgrade or file transfer;
leave USB and J-Link wiring unchanged, shut down normally, and report the
screen state before powering back on. Then inspect debugger availability
once and arrange the normal key restart. If the state is uncertain, stop;
do not blindly retry or claim lost SWD proves electrical power removal.

The owner has no external measuring instrument. This screen can establish
normal shutdown/restart behavior and debugger availability only. It cannot
certify rail decay, lack of backfeed or a write-in-flight fault. The six
PHYSICAL rows remain NOT_OBSERVED until a qualified observation/trigger route
exists. No automatic or manual shutdown has yet occurred in this stage.

Before-action result: Commander exits 0 and reads a CRC-valid fw_header with
version_code=30351 (3.3.51), image_bytes=635860, hardware_rev=1 and layout=1.
The header-stored image SHA-256 is
`d5c14bdb028bb598dd15ae51b9629f2db9d950aa378456d15bff320899fc3112`;
the complete image was not read or verified in this screen. DHCSR=0x01010001
shows execution activity without halt/lockup. Original result and raw header
are `idle-power-01/before-result.json` and `idle-power-01/fw-header.bin`.
No shutdown, reset, halt, program/BCB write or supply command was sent.
Next owner action: only when no recording, upgrade or file transfer is active,
long-press the normal power key, release it on the shutdown indication, keep
USB/debug wiring unchanged, and report the screen state without restarting.
Releasing the key matters because the key itself can sustain the power latch.

### Automatic idle request qualification (2026-11-24)

`P16-IDLE-AUTO-01` supersedes the manual-shutdown request above, which was
cancelled in conversation. The owner requested continuing with the existing
switch circuit, USB supply and J-Link 3V3 lead disconnected, without assuming
an oscilloscope is necessary. Do not ask for the cancelled manual-shutdown
experiment again. Physical key restart is still needed after actual shutdown.

The exact 3.3.51 artifacts were retrieved once from CI run `45176505831`,
artifact `14818886769`, source `ddc0a638ecbe34cb874e15dca51f33ed98360182`.
Original receipt: `.cache/p1-6-power-preflight-20261124/keyring-artifacts-01/result.json`.
The finalized App is 635860 bytes, raw SHA-256
`7d2af1699caaa5887ed6e07cc9a4ca96e079153e7bea602f9f3362ecba18f89a`.
The matching ELF and map are retained under that receipt's `download/source/app/`.
No rebuild, release, cloud mutation or repeat download is required.

First collect one 90-second-bounded read-only Commander snapshot in
`.cache/p1-6-power-preflight-20261124/idle-auto-01/`, with the existing
single-probe, generic CORTEX-M4, 1000-kHz route. Compare the full installed App
to the finalized artifact before trusting its RAM layout; preserve the complete
64-KiB Boot region without changing it. Two live samples cover recording,
BLE session/ISR activity, companion install-pending/phase, SD import state,
overlay ownership, cached confirmation, shutdown request/once guard and callback.
The confirmation sample is the App's startup/confirmation cache, not a new raw
EEPROM BCB arbitration. Do not mislabel it as a persistent-state readback.

Exact ELF disassembly resolves the shutdown request at `0x2000456B`, one byte,
and the normal `App_Uninit` Thumb callback at `0x08030C09`. These are qualified
addresses only after whole-image matching. A possible later one-byte request
of `1` invokes the existing event monitor and normal save/shutdown path; it
is not a function call, remote API, GPIO cutoff or Boot fault injection.
It does not set `Power_Shutdown`'s separate execute-once flag. A host one-shot
receipt must prevent repeats, and both request and once flag must initially
be clear. No request write is included in this first snapshot.

The snapshot stops on identity mismatch, a busy/unexpected state, conflicting
debugger ownership or uncertain result. No halt/reset, EEPROM/BCB/Flash write,
Boot replacement or recovery command is authorized by this idle qualification.
Expected later normal shutdown side effects are the existing configuration and
storage saves, recorder stop and backlight fade before POWER_EN release.
All six PHYSICAL rows remain NOT_OBSERVED; functional shutdown alone cannot
prove the required write-in-flight interruption or voltage-decay timing.

Qualification outcome: `TARGET_CONNECT_FAILED_WITH_RESET_FALLBACK`.
Commander identified the existing USB probe but failed to connect to the MCU
and exited 1. Its original console and SDK logs contain
`Connect fallback: Reset via Reset pin & Connect.` This was automatic vendor
behavior inside `JLINK_Connect`, not an explicit reset in the command file.
The no-reset assumption did not hold on connection failure. Whether the target
actually reset is unobserved; this must not be reported as zero reset attempts.

No savebin command ran, so no full App/Boot or live-state sample was obtained.
No shutdown request, target RAM write or programming command was sent. The
owned process exited and no debugger remained; native JLinkDLL.ini contents
were unchanged. `idle-auto-01/result.json` retains the original UNKNOWN result;
`connection-review.json` records this interpretation without rewriting it.

Stop further target access and retire this connection invocation for the
no-reset idle check. Do not replay it just to obtain a successful snapshot.
Before another session, qualify a vendor no-reset-fallback connection route
and reconcile the actual powered/running state with the owner. Ask only whether
the screen is currently usable; if off, the owner can start normally with the
power key while leaving USB and the existing wiring unchanged. There is no
request to remove power, reconnect J-Link 3V3 or obtain measuring instruments.
The normal automatic-shutdown experiment and all six PHYSICAL rows remain
unexecuted. These documentation changes are local only, with no commit/push.
