# P1-5 implementation evidence (2026-07-28)

> Implementer: Codex dependency-batch implementation session.
> Status: implementation and evidence are complete. The card remains in
> progress and requires independent acceptance.

## 1. Scope and commits

The implementation preserves the frozen fw_header, BCB, ETSL, recovery
trailer, and Boot state-machine contracts. It adds only the one-time deployment
and bootstrap mechanisms required by P1-5.

Implementation commits:

~~~text
7b8638b7f48aaa82dc9fdd09636a0992d6b35ce2
  feat(ota): add P1-5 J-Link bootstrap deployment

1be13ec08b7957566a1e41c8c83bf0b23ae4711b
  fix(ota): wait for complete P1-5 slot staging

88879f99f68b43dc3497ac0575d86691968c44e3
  fix(ota): reject failed P1-5 BCB snapshots
~~~

The two follow-up fixes were found during real-MCU evidence collection:

- stage-slots validates complete candidate and backup images, so its bounded
  default wait is 180 seconds rather than 10 seconds;
- snapshot-bcb now rejects BCB_ARBITER_ERROR instead of printing a misleading
  transport-level PASS.

No OTA receive, decrypt, decompress, patch, or P1-6 power-loss behavior was
added.

## 2. Host tests

Commands and final results:

~~~text
python tests/boot/test_bootstrap.py
P1_5_BOOTSTRAP=PASS checks=101 failures=0

python tests/boot/test_prepare_bootstrap_app.py
P1_5_PREPARE_TOOL=PASS checks=12

P1_1_FW_HEADER_VECTORS=PASS cases=16
P1_1_BOOT_PROTOCOLS=PASS checks=19 failures=0
P0_4_BCB=PASS checks=27 failures=0
P1_3_STATE_MACHINE=PASS checks=96 failures=0
~~~

The standard fw_header and protocol Python runners failed only when
tempfile.TemporaryDirectory created a Windows directory whose ACL denied the
linker. Both runners were rerun unchanged through a fixed existing directory
compatibility wrapper and passed 16/16 and 19/19. This is an environment
warning, not a firmware or vector failure.

## 3. Fresh GCC Release build

The final production migration script created a nonexistent build directory
and ran:

~~~powershell
cmake -S MDK-ARM_F435/cmake-generated -B <run>/gcc-release \
  -G "MinGW Makefiles" \
  -DCMAKE_MAKE_PROGRAM=D:/install/mingw64/bin/make.exe \
  -DCMAKE_BUILD_TYPE=Release -DCMAKE_OBJECT_PATH_MAX=1024 \
  -DARM_TOOLCHAIN_ROOT=D:/singlechip/gcc+gdb+openocd/tools/\
arm-gnu-toolchain-13.3.rel1-ming
cmake --build <run>/gcc-release \
  --target X_Track_App_GCC X_Track_Boot --parallel 1
~~~

Results:

~~~text
P1_5_FRESH_RELEASE=PASS

P1_1_BOOT_ASSERTIONS=PASS bin=16844 vector=0x08000000/0x20c
  msp=0x20058000 reset=0x0800327d
P1_4_BOOT_HANDOFF_ASSERTIONS=PASS nvic_banks=8 primask=0 basepri=0
  faultmask=0 control=0 vtor=0x08010000 branch=MSP/DSB/ISB/BX

Boot LOAD:
  0x08000000 filesz/memsz 0x041c8 R E
  0x20000000 filesz/memsz 0x00004 RW
  remaining RAM LOAD segments RW with zero file size
~~~

Boot is 16,844 bytes, below 64 KiB, has no RWX LOAD, and its linked map/source
scan has zero LZMA, bspatch, Bluetooth/TinyBT/BLE, or AES dependency.

Boot independent four-file artifact:

~~~text
X-Track-Boot.bin 16844
  a2c51dabb766e3f1e8632cc968366b40bdf858083e184dc5ee04112c586f8adc
X-Track-Boot.hex 47454
  01fcc365bb6fe4489d9ce956bba5e888442f764bdf882d50913c5ac3a8669a98
X-Track-Boot.elf 42200
  ecd2e48d4ef73cd8d2e1289887d90275a01a6b9be7fd396615be9e5f86e90a34
X-Track-Boot.map 96601
  aac042d82d8d863ea2323a9a3ffb0c5e9b015656794901b084ad679ee7ad6191
~~~

App independent four-file artifact:

~~~text
X-Track-App-GCC.bin 563036
  fe0b681779b75df466033a6cffaaf7ba24af2262dcf3cc6b2cc570d9cfcc660d
X-Track-App-GCC.hex 1582352
  fd21a4fd1f3aa73b588fb567517755eef111dbd9fb754043b5d052d9dca503bb
X-Track-App-GCC.elf 810688
  677a46ac18e0a45cd21193b2089cbfc965a7680a80b3e413f02046e4fc38707d
X-Track-App-GCC.map 2129766
  602a4c7b610101929291a8acec032000d78f933e7aeca79e1df46d88d51b71e7
~~~

The App retained the repository's existing compiler, short-wchar, newlib
syscall, format/restrict, and App RWX linker warnings. Boot is warning-fatal and
completed successfully.

## 4. Pure legacy starting state

The legacy AC5 artifacts were preserved and never deleted:

~~~text
MDK-ARM_F435/Objects/X-Track.hex 1552994
  bd4c52ad5f0a89189a607d0537367a98796d504a6d3399e83d15b53ed29d5f04
MDK-ARM_F435/Objects/X-Track.axf 6771000
  d44e54480b60ae1e762a746a584f60ad37ad1d6b0c1491ee31ca7dae2828d6e8
MDK-ARM_F435/Track.bin 552108
  0b950eb90f8c288b35e445e508c39b9e5f194f9183d5e9fdec58e49b68bcc49c
~~~

The legacy HEX was reflashed before the accepted one-click migration. An
ordinary MCU reset, not a restricted debugger start, proved:

~~~text
P1_5_PURE_LEGACY_START=PASS
  vtor=0x08000000 cfsr=0x00000000
~~~

Evidence directory:

~~~text
D:\github\my\E-Track\.cache\p1-5-hardware-20260728\
  commit-7b8638b-legacy-start
~~~

## 5. One-click migration and first start

Command:

~~~powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass \
  -File Tools/jlink/deploy-ota-bootstrap.ps1 \
  -Version 2.8.0 -InstallRecovery \
  -LegacyHex D:\github\my\E-Track\MDK-ARM_F435\Objects\X-Track.hex \
  -RunDirectory D:\github\my\E-Track\.cache\p1-5-hardware-20260728\
commit-7b8638b-final-migration
~~~

Console result:

~~~text
P1_5_LEGACY_SNAPSHOT=PASS
P1_5_FRESH_RELEASE=PASS
P1_5_NORMAL_RESET=PASS vtor=0x08010000 rtt=0x20044E04
P1_5_DEPLOYMENT=PASS
~~~

The script programmed and VerifyBin-checked Boot at 0x08000000 and the
finalized App at 0x08010000. The finalized/deployed App was:

~~~text
len=563036 vcode=20800 version=2.8.0
msp=0x20058000 reset=0x0801B3B9
sha256=f9615a62fdccd4f4e7d0f6ac8cc78e672b02780096602bcf30dc09198755be2c
~~~

After both BCB records were cleared, the first Boot start validated the App and
created:

~~~text
active=1 state=4 cur_vcode=20800
boot_try=0 copy_phase=0 resume_block=0
~~~

cur_vcode therefore came from the validated fw_header. The ordinary-reset RTT
line proved the exact P1-4 handoff:

~~~text
OTA: HANDOFF vtor=0x08010000 primask=0 basepri=0 faultmask=0 control=0
  systick=0x00000000 icsr=0x00000000 iser=0x00000000 ispr=0x00000000
~~~

Optional recovery installation completed 138/138 blocks. The implementation
writes and verifies the ETSL fields first and the commit marker last.

## 6. Direct recovery-container flash

The migration produced an unchanged physical recovery container:

~~~text
recovery-v2.8.0.bin 563044
sha256=574e1157baf2bf31a2fd9002ef4fe6907d1d7ca715b59d2dc5736a592987b641
~~~

Command:

~~~powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass \
  -File Tools/jlink/flash-recovery-container.ps1 \
  -RecoveryContainer <migration>/recovery-v2.8.0.bin \
  -LegacyHex D:\github\my\E-Track\MDK-ARM_F435\Objects\X-Track.hex \
  -RunDirectory D:\github\my\E-Track\.cache\p1-5-hardware-20260728\
commit-7b8638b-direct-recovery
~~~

Result:

~~~text
P1_5_RECOVERY_TRAILER_STRIPPED=PASS
  container_len=563044 app_len=563036 bytes_removed=8
  app_sha256=f9615a62fdccd4f4e7d0f6ac8cc78e672b02780096602bcf30dc09198755be2c
P1_5_RECOVERY_FLASH=PASS
ordinary reset: VTOR=0x08010000 CFSR=0x00000000
~~~

Only recovery-stripped-app.bin was flashed at 0x08010000; the eight-byte
container trailer was not written into the App partition. The source container
and legacy recovery artifacts remained intact.

## 7. Hardware parameters and final state

Every flash and command used:

~~~text
Device=AT32F435RGT7
Interface=SWD
Speed=1000 kHz
~~~

RTT collection followed map re-resolution, live SEGGER RTT signature
verification, single bounded logger use, and residual logger cleanup. The board
was finally left on production Boot plus v2.8.1 App, with BCB
CONFIRMED/cur_vcode=20801 and ordinary-reset VTOR=0x08010000, after the P1-3
and P1-4 evidence runs.

## 8. Exclusions and acceptance status

The P1-6 20-point power-loss matrix and tests requiring physical power removal
were not run. A diagnostic mid-internal-Flash J-Link reset is documented in the
P1-3 evidence only as an excluded injection and was recovered through the
validated direct-recovery path. No claim is made that P1-6 passed.

The final clean-checkout CI run is recorded after the evidence closeout commit
is pushed, so its run ID, exact head SHA, and downloaded artifact inventory are
reported in the implementation session's final report. This card remains in
progress pending a non-implementation session's independent acceptance.
