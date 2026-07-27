# P1-3 implementation evidence (2026-07-28)

> Implementer: Codex dependency-batch implementation session.
> Status: implementation and host/build evidence are complete. Hardware
> STAGED-to-CONFIRMED evidence will be backfilled after the P1-5 bootstrap path
> is installed. This card remains `进行中` and requires independent acceptance.

## 1. Scope and frozen contracts

This implementation uses the frozen `fw_header`, BCB, ETSL, recovery asset,
and Boot state-machine contracts without changing their byte layouts or
constants. P2 receive/decrypt/decompress logic and the P1-6 physical 20-point
power-loss matrix are not included.

Implementation commit: the P1-3 implementation commit containing this document.
Its exact SHA is recorded by the final evidence closeout commit after all three
dependency-batch cards have independent implementation commits.

## 2. State machine implementation

- `boot/src/boot_state_machine.c` is pure C with injected EEPROM, external
  Flash, and internal Flash operations. The same source is linked by Boot and
  compiled by the PC simulator.
- Blank/double-invalid BCB plus a valid internal App commits `CONFIRMED`, with
  `cur_vcode` taken only from the unified validated `fw_header`.
- `STAGED` validates ETSL marker/type/padding/length, payload CRC32, the complete
  unified `fw_header`, exact length/vcode, and the ETSL SHA prefix before the
  atomic `APPLYING/copy_phase=1/resume_block=0` commit.
- Apply and rollback copy one 4 KiB block as erase, full-block program, complete
  readback comparison, then one atomic `resume_block++` BCB commit. A reset
  repeats only the last uncommitted block.
- `TEST_BOOT` persists `boot_try--` before returning the jump action. The fourth
  reset after three consumed tries atomically commits
  `ROLLBACK/copy_phase=2/resume_block=0` before restoring any data.
- Rollback validates backup first and recovery second. On re-entry, the already
  verified internal prefix must match the selected source. A source change
  atomically resets `resume_block=0` before copying, preventing a mixed
  backup/recovery App image without adding a BCB field.
- Every post-copy App is checked by the same full `fw_header` validator before
  `TEST_BOOT`, `CONFIRMED`, or a jump action is allowed.
- The state machine never writes the backup slot. The host suite checks that the
  complete backup slot remains byte-for-byte unchanged from `STAGED` through
  App confirmation.
- `Libraries/OTA/ota_confirm.h` provides the minimal App confirmation operation.
  `USER/main.cpp` starts its 30-second healthy-runtime timer after `setup()` and
  retries confirmation from the normal loop. The existing App configuration
  enables a 10-second hardware watchdog and reloads it from `HAL::HAL_Update()`;
  a blocked loop therefore cannot reach the confirmation call.

`boot/src/boot_main.c` now runs the state machine and physical recovery
acceptance path. It deliberately still holds instead of jumping because the
exact P1-4 handoff is a separate implementation commit in this dependency
batch.

## 3. PC Flash/EEPROM simulation

Command:

```powershell
python tests/boot/test_boot_state_machine.py
```

Result:

```text
P1_3_STATE_MACHINE=PASS checks=96 failures=0
```

The 96 checks cover:

- blank BCB bootstrap, IDLE normalization, and stable CONFIRMED boot;
- all six persistent writes in the STAGED/apply/first-test-jump path, each with
  failure before the write and successful reset re-entry;
- all five persistent writes in boot-try exhaustion/rollback/confirmation, each
  with failure before the write and successful reset re-entry;
- apply and rollback resume points 0, 1, and 2 for a three-block image;
- a BCB write that reports failure after the new record became durable;
- erase failure, program failure, and complete write-after-readback mismatch;
- bad STAGED/APPLYING candidates, invalid CONFIRMED/TEST_BOOT Apps, invalid
  `copy_phase`, and an unknown BCB state;
- three consumed test boots followed by atomic rollback;
- bad backup, recovery fallback, both slots bad, and QSPI unavailable;
- backup/recovery source identity across reset and safe restart on source change;
- physical recovery acceptance and minimal App confirmation success/failure;
- backup-slot lock across apply and App confirmation.

This is a deterministic persistent-memory simulator, not the P1-6 physical
power-cut matrix.

## 4. Existing host regressions

Commands and results:

```text
python tests/boot/test_fw_header_vectors.py
P1_1_FW_HEADER_VECTORS=PASS cases=16

python tests/boot/test_boot_protocols.py
P1_1_BOOT_PROTOCOLS=PASS
summary: 19 checks, 0 failure(s)

gcc -std=c99 -Wall -Wextra -Werror -O2 -ILibraries/EEPROM \
  Libraries/EEPROM/eeprom_bcb.c tests/bcb/test_bcb_arbiter.c \
  -o .cache/test_bcb_arbiter.exe
.cache/test_bcb_arbiter.exe
P0_4_BCB=PASS checks=27 failures=0
```

The workflow now runs `tests/boot/test_boot_state_machine.py` beside the two
existing Boot host suites.

## 5. Fresh GCC Release build

The build directory did not exist before configuration:

```powershell
cmake -S MDK-ARM_F435/cmake-generated \
  -B .cache/p1-batch-gcc-release-20260728 -G Ninja \
  -DCMAKE_BUILD_TYPE=Release -DCMAKE_OBJECT_PATH_MAX=1024 \
  -DARM_TOOLCHAIN_ROOT=D:/singlechip/gcc+gdb+openocd/tools/arm-gnu-toolchain-13.3.rel1-ming
cmake --build .cache/p1-batch-gcc-release-20260728 \
  --target X_Track_App_GCC X_Track_Boot --parallel
```

Toolchain: Arm GNU Toolchain 13.3.Rel1, GCC 13.3.1. Both targets completed with
exit code zero. App retained the repository's existing compiler, newlib syscall,
short-wchar, and App RWX warnings. Boot is compiled with `-Werror` and completed
without a Boot warning or error.

Boot layout assertion:

```text
P1_1_BOOT_ASSERTIONS=PASS bin=13656 vector=0x08000000/0x20c
  msp=0x20058000 reset=0x08002715
```

Boot size and load segments:

```text
text=13652 data=4 bss=9772
LOAD 0x08000000 filesz/memsz 0x3554 R E
LOAD 0x20000000 filesz 0x0004 memsz 0x142c RW
LOAD 0x2000142c filesz 0 memsz 0x0004 RW
LOAD 0x20001430 filesz 0 memsz 0x1200 RW
```

The Boot binary is 13,656 bytes, below the 64 KiB limit, and has no RWX LOAD
segment. Exact-word map and explicit Boot source/include scans found zero LZMA,
bspatch, Bluetooth/TinyBT/BLE, or AES dependency.

## 6. Isolated artifacts and hashes

Boot four-file set:

```text
X-Track-Boot.bin 13656  6cc7275a2c01145c06a420bbc747b2749a12765027b7b37625fc8843acb56fbe
X-Track-Boot.hex 38478  ed8a68b403f5b8b7873b097cda5c74d490c7298463ad93f6578e8288e47aae59
X-Track-Boot.elf 35344  a6da3467df86bf0e498bd2a5f7acfabe53e175fc0fb9d260c1d811ff8517cb59
X-Track-Boot.map 85808  e5a4e0964ecc57b7ce145d9ba42518fb2849c1be2cd1b172c63137960e19be54
```

App four-file set:

```text
X-Track-App-GCC.bin 562516   33723a5b7e61aadc5ac8005083f74f95609743d65234ffa96dd1e61d25a0af6a
X-Track-App-GCC.hex 1580896  505880fb5be3155947d3ab1bd671f060981588b782e5ac20b3f29ea75d65d9e4
X-Track-App-GCC.elf 810068   8488a7456c0dc233d581c63d7206ea812b02a971abeef7e554cf1cb80335fc6e
X-Track-App-GCC.map 2152362  10d5953709ec6366b91e884959b461c19e5ea63a95fa188d7f91a43fbb2ed171
```

The workflow upload definitions remain two independent four-file artifacts.

## 7. Hardware evidence and exclusions

No ordinary reset/run startup claim is made by this P1-3 commit. The required
real-MCU STAGED-to-CONFIRMED trace depends on the exact P1-4 handoff and P1-5
bootstrap installation. It will be appended to this document after that path is
operational, while the evidence remains attributed to P1-3.

P1-4 handoff, P1-5 deployment, P2 OTA transport/decrypt/decompress, and the P1-6
20-point physical power-loss matrix are explicitly excluded from this commit.
