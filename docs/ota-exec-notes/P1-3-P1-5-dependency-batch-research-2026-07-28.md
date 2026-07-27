# P1-3/P1-4/P1-5 dependency-batch research (2026-07-28)

> Session: Codex implementation session.
> Baseline: clean `main` and `origin/main` at
> `169e3136bdf84d3d8235aa2aeb95c1003691d265` after `git fetch origin`.
> Contract status: no conflict found. `PLAN-OTA.md` and
> `docs/ota-binary-contracts.md` remain unchanged.

## 1. Required material read

- `AGENTS.md`, including OTA execution, GCC/AC5, J-Link, and RTT rules.
- `PLAN-OTA-EXEC.md` cards P1-3, P1-4, and P1-5.
- `PLAN-OTA.md` storage layout, Boot state machine, recovery asset, and
  bootstrap sections.
- `docs/ota-binary-contracts.md` fw_header, BCB, ETSL, recovery, R4, and R8
  clauses.
- P1-1 implementation evidence, the P1-2 linker decision, the P1-2
  implementation evidence, and `.claude/verification-report-ota-plan.md`.

## 2. Current implementation gap

- `boot/src/boot_main.c` only arbitrates BCB, probes candidate ETSL, validates
  the internal App, then holds. It has no P1-3 state transitions and no P1-4
  handoff.
- `boot/platform/at32/boot_platform_at32.c` already provides bounded EEPROM,
  QSPI read, and internal Flash erase/program primitives. It lacks the final
  handoff and the optional QSPI write primitives needed only by bootstrap
  recovery-slot installation.
- `boot_fw_header_validate()` is already the unified validator and must be
  reused for candidate, post-copy App, rollback/recovery App, bootstrap App,
  and every jump.
- `eeprom_bcb.c` already provides the required whole-record, inactive-block,
  `seq+1`, readback-verified commit. State transitions must use one
  `bcb_commit()` each and must never write fields independently.
- The App has no TEST_BOOT confirmation path. The minimal required addition is
  a 30-second post-initialization confirmation that changes only
  TEST_BOOT -> CONFIRMED and sets `cur_vcode=cand_vcode`.
- Existing J-Link scripts flash individual Boot/App images only. There is no
  one-click finalized-App bootstrap, rollback-to-legacy failure path, blank-BCB
  preparation, or normal-reset evidence capture.

## 3. P1-3 implementation shape

- Add a pure-C `boot_state_machine` module with injected EEPROM, external
  Flash read, internal Flash erase/program/read, and logging callbacks. The
  same source will be compiled by the MCU Boot target and a PC simulator test.
- External slot acceptance is: ETSL magic/type/padding/marker, bounded length,
  full payload CRC32, unified fw_header validation, exact image length/version,
  and ETSL `sha8` comparison. Candidate/backup BCB metadata must agree with the
  validated slot.
- Copy one logical 4 KiB block at a time. Each block is filled with `0xFF`,
  source bytes are read, exactly that App block is erased, the complete block
  is programmed and read back, then one BCB transaction persists
  `resume_block+1`. A failed progress commit may cause that one block to be
  repeated after reset, never a whole-App erase.
- STAGED candidate rejection enters the contracted rollback path without
  erasing the current App. APPLYING source or post-copy validation failure also
  enters rollback.
- TEST_BOOT validates the internal App, persists `boot_try-1`, then returns a
  jump action. `boot_try==0` performs the atomic first rollback transition
  `{state=ROLLBACK,copy_phase=2,resume_block=0}`.
- ROLLBACK prefers a fully validated backup slot. If backup is invalid it
  validates and copies the recovery slot with the same progress rules; if both
  are invalid it requests physical recovery.
- The PC flash/EEPROM model will retain state across repeated state-machine
  invocations and inject failures at transition commits, every copy progress
  boundary, write/readback, exhausted tries, invalid candidate/backup, and
  recovery fallback.
- Backup locking is enforced by behavior: Boot never writes external slots,
  App confirmation only writes BCB, and the J-Link-only slot installer will
  reject candidate/backup writes unless BCB is in a stable state.

## 4. P1-4 implementation shape

- The state machine returns a jump action only after unified validation and
  provides the validated MSP/Reset_Handler values.
- The AT32 handoff disables and clears `NVIC->ICER[0..7]` and
  `NVIC->ICPR[0..7]`, stops/clears SysTick, clears PendSV/SysTick pending in
  ICSR, and explicitly establishes `PRIMASK=0`, `BASEPRI=0`, `FAULTMASK=0`,
  and `CONTROL=0` before transfer.
- It writes `VTOR=OTA_APP_ORIGIN`, executes DSB+ISB, reloads the two App vector
  words, sets MSP in a naked final branch helper, executes DSB+ISB again, and
  branches to vector[1]. The jump does not depend on PRIMASK masking.
- Real-device injection will pend SysTick and one external IRQ immediately
  before handoff, then confirm normal App thread mode, App VTOR, cleared fault
  status, and RTT output. Repeated normal resets provide the round-trip sample.

## 5. P1-5 implementation shape

- Add an ASCII PowerShell deployment script under `Tools/jlink/`. It fresh
  builds Release `X_Track_Boot` and `X_Track_App_GCC`, copies the raw App bin,
  finalizes its fw_header, verifies it, then programs Boot at `0x08000000` and
  the finalized App at `0x08010000` with `AT32F435RGT7`/SWD 1000 kHz.
- If the input is a recovery container, the script verifies and strips its
  final 8-byte length/CRC trailer before programming the App partition.
- A J-Link-only noinit bootstrap command in Boot will support clearing the two
  BCB records and, optionally, installing the current validated App into the
  recovery slot. Recovery installation erases the header first, writes and
  verifies payload/header fields, and writes the ETSL commit marker last.
- Normal Boot startup with no valid BCB validates the internal App, commits a
  CONFIRMED BCB with `cur_vcode` from fw_header, then uses the normal P1-4
  handoff. The final evidence must come from an ordinary MCU reset after both
  images are installed.
- The deployment script never deletes or overwrites legacy build artifacts. On
  deployment failure it retains the finalized inputs/logs and can reflash the
  existing legacy hex as the recovery path; no force push is permitted.

## 6. Explicit exclusions

- No P2 BLE/SD receive, AES, LZMA, bspatch, candidate generation, or backup
  self-copy production path is added.
- No P1-6 20-point power-loss matrix or user-assisted physical power cut is
  claimed. P1-3 host reset injection and P1-4 pending-IRQ injection are within
  this batch; physical power-loss acceptance remains P1-6.
- The three cards remain `进行中` after implementation and evidence. Only a
  later non-implementation session may independently accept them.
