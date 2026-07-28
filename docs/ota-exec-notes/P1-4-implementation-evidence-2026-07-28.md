# P1-4 implementation evidence (2026-07-28)

> Implementer: Codex dependency-batch implementation session.
> Status: acceptance remediation, implementation, and evidence are complete.
> The card remains in progress and requires a new non-implementation
> acceptance session.

## 1. Commits and acceptance remediation

Original P1-4 implementation:

```text
3fe2e006ebd155a2315d0a02f9ff6b96df3d8524
  feat(ota): implement P1-4 Boot to App handoff
```

Acceptance remediation:

```text
f0ce213d505c4da732479479c348295f98413604
  fix(ota): restore VTOR as first App call
```

The first independent acceptance session passed the Boot handoff sequence,
pending-interrupt injection, repeated ordinary resets, GCC build, and CI, but
rejected P1-4 because `ota_handoff_capture()` preceded the P1-2-frozen
`ota_vtor_check()` call. The remediation changes only that App startup order
and adds a validator assertion that prevents recurrence.

## 2. Frozen Boot handoff contract

The implementation still performs the frozen sequence:

1. Write all eight NVIC ICER banks.
2. Write all eight NVIC ICPR banks.
3. stop SysTick and clear PendST/PendSV.
4. establish PRIMASK=0, BASEPRI=0, FAULTMASK=0, and CONTROL=0.
5. write VTOR=0x08010000, then DSB and ISB.
6. reload MSP and Reset_Handler from the validated App vector table.
7. set MSP in the naked final stub, execute DSB and ISB, then BX vector[1].

`boot_handoff_to_app()` performs the shared full fw_header/vector validation
immediately before cleanup. It fails closed on any header, vector, Thread-mode,
or post-VTOR vector mismatch. There is no `cpsid`, `__disable_irq`, or
PRIMASK=1 jump path.

## 3. App first-call proof

Final source order:

```text
USER/main.cpp:146  ota_vtor_check();
USER/main.cpp:147  ota_handoff_capture();
USER/main.cpp:149  Core_Init();
```

The fresh deployment App ELF proves the same call order:

```text
08042c00 <main>:
  08042c02  bl 08042e3c <ota_vtor_check>
  08042c06  bl 08042d3c <ota_handoff_capture>
  08042c0a  bl 08017a18 <Core_Init>
```

Therefore an invalid VTOR fails closed before handoff capture or any normal
App initialization. Capture still occurs before `Core_Init()` and records
VTOR, PRIMASK, BASEPRI, FAULTMASK, CONTROL, SysTick CTRL, SCB ICSR, and the OR
of all eight NVIC enable and pending banks.

`tests/boot/validate_boot_handoff.py` now rejects any source order other than
`ota_vtor_check()` -> `ota_handoff_capture()` -> `Core_Init()`.

## 4. Host and linked-artifact checks

Commands were run from the detached validation checkout at
`dbb5c37103537a2a8163b494f5a59e44bcaa7695` against the fresh deployment
build directory:

```powershell
python tests/boot/validate_boot_artifact.py `
  --build-dir .cache/p1-5-deploy-remediation-2-20260728/gcc-release
python tests/boot/validate_boot_handoff.py `
  --build-dir .cache/p1-5-deploy-remediation-2-20260728/gcc-release
```

Results:

```text
P1_1_BOOT_ASSERTIONS=PASS bin=14208 vector=0x08000000/0x20c
  msp=0x20058000 reset=0x08002885
P1_4_BOOT_HANDOFF_ASSERTIONS=PASS nvic_banks=8 primask=0 basepri=0
  faultmask=0 control=0 vtor=0x08010000 branch=MSP/DSB/ISB/BX
```

Required regressions also passed:

```text
P1_1_FW_HEADER_VECTORS=PASS cases=16
P1_1_BOOT_PROTOCOLS=PASS checks=19 failures=0
P0_4_BCB=PASS checks=27 failures=0
P1_3_STATE_MACHINE=PASS checks=96 failures=0
P1_5_PREPARE_TOOL=PASS checks=42 powershell_checks=8
```

The two Python runners that use `TemporaryDirectory` were executed unchanged
with their temporary directory context mapped in-process to pre-created
writable directories. This avoids the documented Windows MinGW ACL failure;
test source and tested firmware source were not modified.

## 5. Fresh GCC Release artifacts

The P1-5 deployment script created a nonexistent build directory and built
fresh Release `X_Track_App_GCC` and `X_Track_Boot` targets. The independent
four-file sets were:

```text
X-Track-Boot.bin 14208
  411f3e1d703f07bd107d0f1f4f9687a54bd69981c63cc70d3f421ad15494ac3c
X-Track-Boot.hex 40037
  89b6938bf014b1b5a45434414054184099fc13ebf13c8bead5efc6ec883cd6e2
X-Track-Boot.elf 36148
  4a0961b5a5ac10e93da26204ef8001195081016fb30e44ea43f711288efde767
X-Track-Boot.map 97769
  3d208f31f1708c317b2be426db7f551bc66b1c1abce359a8535275ec041b0eda

X-Track-App-GCC.bin 563068
  f9675251636217538a4d9590ca59c4d8d442f2da93e221dc32b805fe4fe82b7d
X-Track-App-GCC.hex 1582442
  7b2691351478360133366b51514997a7a9e2a5260dfda8135db008344c99a491
X-Track-App-GCC.elf 810688
  847a28e19a78d26f07f8bcd2c8070bd14c71fe7ae4b3feeeed9d70eb0b971fea
X-Track-App-GCC.map 2131413
  8c5a9f821de043ab0d57ccde704996e385063241f8924c2b124fc33f9585877c
```

Boot is below 64 KiB. Its LOAD segments are `R E` plus `RW`, never RWX, and
the linked map contains no LZMA, bspatch, BLE/Bluetooth, or AES dependency.
The App retains the repository's known compiler warnings, short-wchar linker
warnings, and App RWX LOAD warning. CMake also reports the known Windows long
object-path warnings. Boot itself remains warning-fatal and passed.

## 6. Real-MCU evidence

The first independent acceptance already passed the evidence-only pending
SysTick plus external IRQ injection and three repeated production ordinary
resets. That accepted evidence remains archived in:

```text
D:\github\my\E-Track\.cache\p1-4-hardware-20260728\
```

The fixed-call-order App was then used by the successful remediation
deployment and direct recovery-container run. Ordinary reset evidence was:

```text
deployment reset 1:
  PC=0x0804A3E6 VTOR=0x08010000 CFSR=0x00000000
deployment reset 2:
  PC=0x08029B1E VTOR=0x08010000 CFSR=0x00000000
direct recovery reset:
  PC=0x0802EAEA VTOR=0x08010000 CFSR=0x00000000
```

Each run re-resolved `_SEGGER_RTT=0x20044E04` from the matching App map,
verified the live `SEGGER RTT` signature, and captured:

```text
OTA: HANDOFF vtor=0x08010000 primask=0 basepri=0 faultmask=0 control=0
  systick=0x00000000 icsr=0x00000000 iser=0x00000000 ispr=0x00000000
```

The board was resumed after inspection and no JLinkRTTLogger or
JLinkRTTViewer process remained.

## 7. Remaining status

P1-4 remediation implementation and evidence are complete, but this
implementation session does not mark the card complete. A different
non-implementation session must independently verify the first-call contract
and decide acceptance.

P1-6's 20-point power-loss matrix and physical power-cut cases were not run
and are not claimed by this evidence.
