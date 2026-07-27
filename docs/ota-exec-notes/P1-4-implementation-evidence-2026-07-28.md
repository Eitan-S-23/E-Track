# P1-4 implementation evidence (2026-07-28)

> Implementer: Codex dependency-batch implementation session.
> Status: implementation, disassembly assertions, host regressions, and fresh
> GCC build evidence are complete. Pending-IRQ injection and repeated normal
> reset hardware evidence will be backfilled through the P1-5 deployment path.
> This card remains in progress and requires independent acceptance.

## 1. Frozen handoff contract

The implementation preserves the frozen sequence:

1. Disable all eight NVIC banks through ICER[0..7].
2. Clear all eight NVIC pending banks through ICPR[0..7].
3. Stop and clear SysTick, then clear PendST and PendSV in SCB->ICSR.
4. Establish PRIMASK=0, BASEPRI=0, FAULTMASK=0, and CONTROL=0.
5. Set VTOR=0x08010000, then execute DSB and ISB.
6. Read MSP and Reset_Handler from the App vector table.
7. Set MSP in a naked final stub, execute DSB and ISB again, then branch with
   BX to vector word 1.

No __disable_irq, cpsid, or PRIMASK=1 path is present. The handoff also rejects
calls outside Thread mode.

## 2. Final validation and TEST_BOOT watchdog

- boot_handoff_to_app() performs a fresh unified boot_fw_header_validate()
  immediately before register cleanup.
- After VTOR barriers it reloads both vector words directly from 0x08010000
  and compares them with the validated values. Any failure holds fail-closed.
- A TEST_BOOT action starts the existing 10-second hardware watchdog before
  handoff. The App later reconfigures and reloads the same watchdog from its
  normal HAL loop, so a startup or loop hang cannot confirm the candidate.
- Physical recovery and ordinary CONFIRMED boot use the same final validator
  and handoff function.

## 3. App-side early evidence

ota_handoff_capture() runs at the first statement in App main(), before
Core_Init() and normal HAL initialization. It captures VTOR, PRIMASK, BASEPRI,
FAULTMASK, CONTROL, SysTick CTRL, SCB ICSR, and the OR of all eight NVIC enable
and pending banks. After RTT initialization ota_handoff_report() emits:

~~~text
OTA: HANDOFF vtor=... primask=... basepri=... faultmask=... control=...
  systick=... icsr=... iser=... ispr=...
~~~

Release symbol addresses:

~~~text
ota_handoff_capture       0x08042d3c
ota_handoff_report        0x08042dcc
_SEGGER_RTT               0x20044e04
g_ota_handoff_ispr_or     0x20044eb8
g_ota_handoff_primask     0x20044ed4
g_ota_handoff_vtor        0x20044ed8
~~~

The final hardware run must re-resolve addresses from its own linked artifact
and verify the live SEGGER RTT signature before logging.

## 4. Static and disassembly assertions

~~~text
python tests/boot/validate_boot_handoff.py --build-dir .cache/p1-4-release-make2
P1_4_BOOT_HANDOFF_ASSERTIONS=PASS nvic_banks=8 primask=0 basepri=0
  faultmask=0 control=0 vtor=0x08010000 branch=MSP/DSB/ISB/BX
~~~

The validator checks source ordering, linked Boot/App evidence symbols, and
the actual Arm disassembly. CI runs it after the Boot artifact assertions.

## 5. Pending-interrupt injection build

~~~text
cmake -S MDK-ARM_F435/cmake-generated -B .cache/p1-4-inject-make
  -G "MinGW Makefiles"
  -DCMAKE_MAKE_PROGRAM=D:/install/mingw64/bin/make.exe
  -DCMAKE_BUILD_TYPE=Release -DCMAKE_OBJECT_PATH_MAX=1024
  -DBOOT_HANDOFF_TEST_INJECT_PENDING=ON
  -DARM_TOOLCHAIN_ROOT=D:/singlechip/gcc+gdb+openocd/tools/arm-gnu-toolchain-13.3.rel1-ming
cmake --build .cache/p1-4-inject-make --target X_Track_Boot --parallel 1

X-Track-Boot.bin 14252 bytes
sha256 d01438701d19a936fe6e48752b6a9660317fc755dfb801691805f0db3a2d069b
~~~

Its disassembly writes SysTick PENDSTSET and external peripheral
NVIC->ISPR[0] immediately before normal cleanup. It contains no cpsid. The
final branch stub is:

~~~text
msr MSP, r0
dsb sy
isb sy
bx r1
~~~

This injection binary is evidence-only and is not the P1-5 production Boot.

## 6. Fresh GCC Release build

~~~text
cmake -S MDK-ARM_F435/cmake-generated -B .cache/p1-4-release-make2
  -G "MinGW Makefiles"
  -DCMAKE_MAKE_PROGRAM=D:/install/mingw64/bin/make.exe
  -DCMAKE_BUILD_TYPE=Release -DCMAKE_OBJECT_PATH_MAX=1024
  -DARM_TOOLCHAIN_ROOT=D:/singlechip/gcc+gdb+openocd/tools/arm-gnu-toolchain-13.3.rel1-ming
cmake --build .cache/p1-4-release-make2
  --target X_Track_App_GCC X_Track_Boot --parallel 1
~~~

Both targets completed with exit code zero. App retained the repository's
existing short-wchar/newlib/RWX warnings. Boot is compiled with -Werror and
had no Boot warning or error.

~~~text
P1_1_BOOT_ASSERTIONS=PASS bin=14208 vector=0x08000000/0x20c
  msp=0x20058000 reset=0x08002885
LOAD 0x08000000 filesz/memsz 0x377c R E
LOAD 0x20000000 filesz 0x0004 memsz 0x1438 RW
LOAD 0x20001438 filesz 0 memsz 0x1200 RW
~~~

Boot remains below 64 KiB, has no RWX LOAD, and has no LZMA, bspatch,
Bluetooth/TinyBT/BLE, or AES dependency.

## 7. Artifact hashes

Production Boot four-file set:

~~~text
X-Track-Boot.bin 14208  411f3e1d703f07bd107d0f1f4f9687a54bd69981c63cc70d3f421ad15494ac3c
X-Track-Boot.hex 40037  89b6938bf014b1b5a45434414054184099fc13ebf13c8bead5efc6ec883cd6e2
X-Track-Boot.elf 36148  4a0961b5a5ac10e93da26204ef8001195081016fb30e44ea43f711288efde767
X-Track-Boot.map 92018  c7d7ac520f845d8a50cc4dfa8dcf99f9eb7a80acf47b8ac3325f87cbdb6299ea
~~~

App four-file set:

~~~text
X-Track-App-GCC.bin 562916   2f8616f197e1a63b3f66ee8d1700c26bd107892872a32c73e10b99b35fcafaae
X-Track-App-GCC.hex 1582021  c692d31e98f45795870083c7702991e68020aaf679e500cc8f49a3b553aefaa8
X-Track-App-GCC.elf 810688   2bef7e636dcd800538475e566cdda55819a76d384f0e003c92feb69bc1d56e3e
X-Track-App-GCC.map 2242101  4601c0c7642d6d5a23da715e5e10e8f2fe1467e90d19466946837c8522647881
~~~

## 8. Regressions and pending hardware evidence

~~~text
P1_1_FW_HEADER_VECTORS=PASS cases=16
P1_1_BOOT_PROTOCOLS=PASS checks=19 failures=0
P0_4_BCB=PASS checks=27 failures=0
P1_3_STATE_MACHINE=PASS checks=96 failures=0
~~~

No normal-reset startup claim is made by this implementation commit. The
required injection run and repeated Boot-to-App normal resets will be recorded
after P1-5 installs finalized Boot and App images. P1-6 physical power-cut
testing remains explicitly excluded.
