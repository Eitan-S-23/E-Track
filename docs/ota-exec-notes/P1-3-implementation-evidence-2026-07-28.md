# P1-3 implementation evidence (2026-07-28)

> Implementer: Codex dependency-batch implementation session.
> Status: implementation and evidence are complete, including real-MCU
> STAGED-to-CONFIRMED evidence through the P1-5 bootstrap path. This card
> remains in progress and requires independent acceptance.

## 1. Scope and frozen contracts

This implementation uses the frozen `fw_header`, BCB, ETSL, recovery asset,
and Boot state-machine contracts without changing their byte layouts or
constants. P2 receive/decrypt/decompress logic and the P1-6 physical 20-point
power-loss matrix are not included.

Implementation commit:
6ea38d7b8914bcc46559f3b723d06d0ad0d47c79.

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

## 7. Real-MCU STAGED-to-CONFIRMED evidence

Hardware evidence directory:

~~~text
D:\github\my\E-Track\.cache\p1-3-hardware-20260728\
  commit-7b8638b-staged-confirmed
~~~

The production v2.8.0 and candidate v2.8.1 assets were prepared from the same
fresh P1-5 GCC build and both passed the complete host validator:

~~~text
v2.8.0  len=563036
sha256=f9615a62fdccd4f4e7d0f6ac8cc78e672b02780096602bcf30dc09198755be2c

v2.8.1  len=563036
sha256=1d870ce448486b52bc5a8fa497e36b84cf0bbebf181603abfb63f1cdc51a5916
fw_header double-zero sha256=
  1d870ce448486b52bc5a8fa497e36b84cf0bbebf181603abfb63f1cdc51a5916
header_crc32=0xbadb35b6
~~~

Slot preparation used the authenticated NOLOAD bootstrap command path:

~~~text
pre-stage BCB:
  state=4 cur_vcode=20800

install-backup-v20800:
  progress=138/138 image_vcode=20800 image_len=563036
  image_crc32=221449039

install-candidate-v20801:
  progress=138/138 image_vcode=20801 image_len=563036
  image_crc32=221449039

STAGED:
  active=2 state=1 boot_try=3 copy_phase=0 resume_block=0
  cur_vcode=20800 cand_vcode=20801 backup_vcode=20800
~~~

The final accepted run used a 180-second full slot-validation window followed
by one uninterrupted 240-second ordinary MCU reset window. The final register,
RTT, and BCB evidence was:

~~~text
P1_3_UNINTERRUPTED_WINDOW=PASS seconds=240
  vtor=0x08010000 cfsr=0x00000000

OTA: HANDOFF vtor=0x08010000 primask=0 basepri=0 faultmask=0 control=0
  systick=0x00000000 icsr=0x00000000 iser=0x00000000 ispr=0x00000000
OTA: TEST_BOOT confirmed vcode=20801

CONFIRMED snapshot:
  active=2 state=4 boot_try=0 copy_phase=0 resume_block=0
  cur_vcode=20801 cand_vcode=20801 backup_vcode=20800

P1_3_STAGED_TO_CONFIRMED=PASS cur_vcode=20801
~~~

The backup version remained v20800 from STAGED through confirmation. The host
suite separately checks that every byte of the backup slot remains unchanged
through this interval.

## 8. Diagnostic injection and exclusions

An earlier diagnostic run intentionally interrupted the apply path. At 25
seconds it proved the first atomic boundary:

~~~text
state=2 copy_phase=1 resume_block=0
cur_vcode=20800 cand_vcode=20801 backup_vcode=20800
~~~

A later J-Link reset happened while the PC was in
flash_operation_status_get during a live internal-Flash operation. The next
snapshot returned active=0xFFFFFFFF, which is BCB_ARBITER_ERROR (EEPROM I/O
failure), not proof of double-invalid BCB records. This is an injected
mid-Flash condition belonging to the excluded P1-6 fault/power matrix and is
not counted as a pass. The validated direct-recovery path restored v2.8.0 and
BCB CONFIRMED/20800 before the final uninterrupted run. P1-5 follow-up commit
88879f99f68b43dc3497ac0575d86691968c44e3 makes the host result parser reject
such a snapshot instead of printing a transport-level PASS.

No P1-6 20-point power-loss matrix, physical power interruption, P2 transport,
decryption, decompression, or patching work was performed. Rollback and all
reset-boundary behavior remain covered by the deterministic 96-check host
suite; this implementation session does not claim independent acceptance.
