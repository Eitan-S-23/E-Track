# P1-5 implementation evidence (2026-07-28)

> Implementer: Codex dependency-batch implementation session.
> Status: acceptance remediation, implementation, and evidence are complete.
> The card remains in progress and requires a new non-implementation
> acceptance session.

## 1. Remediation commits and final scope

Commits after the failed independent acceptance:

```text
5a613094c11e2f5ed12a29f0ca819f77655fad83
  fix(build): make legacy AC5 rebuild reproducible
6ed3e41eb2b43ead518a9f68d1f423636b8a68db
  fix(ota): constrain P1-5 bootstrap remediation
b7be7b092aeb9cf1354e55ec9fa467601e25524a
  fix(ota): parse final J-Link reset sample
30da456235ac194beab845da99b650659310b64a
  fix(ota): wait for delayed App confirmation evidence
dbb5c37103537a2a8163b494f5a59e44bcaa7695
  fix(ota): make bootstrap evidence summaries auditable
```

`6ed3e41` removes the out-of-scope production Boot command protocol, QSPI
write API, Boot overlay linker allocation, workflow/CMake additions, and the
associated bootstrap C tests. The final workflow, production Boot sources,
Boot linker script, and Boot artifact validator are byte-identical to the
P1-4 base commit `3fe2e006ebd155a2315d0a02f9ff6b96df3d8524`.

The old `P1_5_BOOTSTRAP=PASS checks=101` result belonged to that removed
production command protocol. It is withdrawn and is not a current test or
acceptance claim. The historical implementation commits `7b8638b`,
`1be13ec`, and `88879f9` remain in history, but their out-of-scope production
mechanism is superseded by this remediation.

Final P1-5 functionality is limited to `Tools/jlink`, the bootstrap manual,
and host verification. The only non-tool prerequisite is the separately
identified fresh legacy AC5 build repair in `MDK-ARM_F435/proj.uvprojx` and
`MDK-ARM_F435/scatter/X-Track-Legacy-AC5.sct`. That minimum prerequisite is
registered in `PLAN-OTA-EXEC.md` section 9; it changes no frozen fw_header,
BCB, ETSL, recovery trailer, partition, or Boot state-machine contract.

The deployment tool does not clear EEPROM and does not install an external
recovery slot. The optional recovery-slot installation path is therefore not
claimed. A recovery container is generated and retained as a host asset only.

## 2. Acceptance blockers and fixes

### 2.1 Selected legacy image cannot be overwritten

The explicitly selected `LegacyHex` is copied before device modification as:

```text
selected-legacy-<sha256>-<basename>
```

Repository-default audit artifacts use distinct `repo-default-*` role names.
Rollback references only the selected hash-named copy. A real PowerShell test
uses different contents with the same basename and verifies that both copies
remain distinct and byte-identical to their sources.

### 2.2 PASS requires final healthy App state

Each ordinary-reset gate now requires:

- the last J-Link PC sample to be inside the App partition;
- exact `VTOR=0x08010000`;
- exact `CFSR=0x00000000`;
- the map-derived live RTT signature;
- a current `OTA: HANDOFF vtor=0x08010000` line;
- matching `CONFIRMED vcode=<validated fw_header version_code>`.

The parser intentionally selects the last PC/VTOR/CFSR sample. Regression
samples cover a connection-time Boot PC followed by an App PC, nonzero CFSR,
and a final PC outside the App partition.

### 2.3 Recovery input is immutable

`prepare-bootstrap-app.py` rejects all input/App-output/recovery-output path
collisions before opening an output file. `flash-recovery-container.ps1`
writes only a separate `recovery-stripped-app.bin`, verifies an exact 8-byte
length reduction, and verifies the source length and SHA-256 both before and
after the device operation.

### 2.4 Scope is tool-only again

No production Boot command channel, QSPI write API, OTA receiver, decryptor,
decompressor, bspatch path, BLE path, or AES path remains. No external
recovery slot is modified. The production files touched by the rejected
implementation were restored exactly to the accepted P1-4 base.

### 2.5 Fresh legacy AC5 build is reproducible

The legacy target explicitly excludes the two OTA-App-only sources and uses a
tracked legacy scatter file rather than a stale generated object-directory
scatter file. This closes the independent acceptance failure in
`ota_vtor_check.c` without weakening that source's OTA App guard.

## 3. Host regression results

Final host run at detached checkout
`dbb5c37103537a2a8163b494f5a59e44bcaa7695`:

```text
P1_1_FW_HEADER_VECTORS=PASS cases=16
P1_1_BOOT_PROTOCOLS=PASS checks=19 failures=0
P0_4_BCB=PASS checks=27 failures=0
P1_3_STATE_MACHINE=PASS checks=96 failures=0
P1_5_PREPARE_TOOL=PASS checks=42 powershell_checks=8
```

The 42 P1-5 checks include real PowerShell execution for:

- final-sample J-Link parsing;
- exact-zero CFSR rejection;
- App-partition PC rejection;
- basename-colliding legacy preservation;
- normal-reset PASS-line formatting;
- recovery PASS-line formatting;
- App/recovery path collision rejection;
- recovery source preservation.

The fw_header and protocol Python runners retain their source unchanged. Their
`TemporaryDirectory` context was mapped in-process to pre-created writable
directories to avoid the documented Windows MinGW ACL failure.

## 4. Fresh legacy AC5 build

The validation checkout performed a fresh uVision/AC5 build of target
`X-Track`. Log:

```text
D:\github\my\E-Track\.cache\p1-remediation-verify-20260728\
  ac5-legacy-fresh.log
```

Result:

```text
Program Size: Code=263496 RO-data=288312 RW-data=1244 ZI-data=453392
".\Objects\X-Track.axf" - 0 Error(s), 0 Warning(s).
Build Time Elapsed: 00:04:10
```

Legacy artifacts were preserved and never deleted:

```text
X-Track.axf 6873256
  e89c5d4cc7bbf092ffc46fc21dca4c2753a4d62d5a5550a258ed1a04cc040856
X-Track.hex 1552994
  d535544ee703fde6e27c73a6268f9f914e890e5c819804d6303a4fe61b64a4c3
Track.bin 552108
  23eafd2832b2640d7cec566a177535e6d4497e10364c58ed760f664145350c57
X-Track.map 3698075
  404708505008852c8b583ae1c53eae9d4d8e1cb58147f9ea116afdca728d021b
```

## 5. Fresh GCC Release build and layout

The successful one-click run created a nonexistent build directory and ran a
fresh Release build of `X_Track_App_GCC` and `X_Track_Boot`.

Boot four-file set:

```text
X-Track-Boot.bin 14208
  411f3e1d703f07bd107d0f1f4f9687a54bd69981c63cc70d3f421ad15494ac3c
X-Track-Boot.hex 40037
  89b6938bf014b1b5a45434414054184099fc13ebf13c8bead5efc6ec883cd6e2
X-Track-Boot.elf 36148
  4a0961b5a5ac10e93da26204ef8001195081016fb30e44ea43f711288efde767
X-Track-Boot.map 97769
  3d208f31f1708c317b2be426db7f551bc66b1c1abce359a8535275ec041b0eda
```

App four-file set:

```text
X-Track-App-GCC.bin 563068
  f9675251636217538a4d9590ca59c4d8d442f2da93e221dc32b805fe4fe82b7d
X-Track-App-GCC.hex 1582442
  7b2691351478360133366b51514997a7a9e2a5260dfda8135db008344c99a491
X-Track-App-GCC.elf 810688
  847a28e19a78d26f07f8bcd2c8070bd14c71fe7ae4b3feeeed9d70eb0b971fea
X-Track-App-GCC.map 2131413
  8c5a9f821de043ab0d57ccde704996e385063241f8924c2b124fc33f9585877c
```

Validators and layout checks:

```text
P1_1_BOOT_ASSERTIONS=PASS bin=14208 vector=0x08000000/0x20c
  msp=0x20058000 reset=0x08002885
P1_4_BOOT_HANDOFF_ASSERTIONS=PASS nvic_banks=8 primask=0 basepri=0
  faultmask=0 control=0 vtor=0x08010000 branch=MSP/DSB/ISB/BX
BOOT_FORBIDDEN_DEPENDENCIES=0
```

Boot is below 64 KiB and has no RWX LOAD. App and Boot remain independent
four-file artifact sets. The App retains known compiler, short-wchar linker,
and RWX LOAD warnings. CMake retains known Windows long-object-path warnings.
Boot itself is warning-fatal and passed.

## 6. Pure legacy precondition and one-click migration

An evidence-only Boot build with `BOOT_HANDOFF_TEST_CLEAR_BCB=ON` erased both
BCB records and halted after the clear path. The fresh AC5 HEX was then loaded
without deleting any legacy artifact. A subsequent ordinary reset proved the
pure legacy state:

```text
PC=0x08023C4C VTOR=0x08000000 CFSR=0x00000000
```

Precondition evidence:

```text
D:\github\my\E-Track\.cache\p1-remediation-verify-20260728\.cache\
  p1-hw-precondition-20260728
```

The accepted migration command was:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\Tools\jlink\deploy-ota-bootstrap.ps1 `
  -Version 2.8.2 `
  -LegacyHex .\MDK-ARM_F435\Objects\X-Track.hex `
  -RunDirectory .\.cache\p1-5-deploy-remediation-2-20260728
```

The script preserved the selected legacy HEX under its role and SHA name,
built fresh artifacts, finalized the App, and generated:

```text
finalized/deploy App len=563068 version=2.8.2 vcode=20802
msp=0x20058000 reset=0x0801B3B9
sha256=2e3acc8da18111f595ca2829beae17fb1d482eec5870d171521071a909d00efb

recovery container len=563076
sha256=7bc5695f66f1b408e679ae6ab0fb15ba9c9cf77b0555bd6328eb96ab8939fd01
```

J-Link reported two distinct `Verify successful.` results for Boot at
`0x08000000` and finalized App at `0x08010000`. The two ordinary-reset gates
then produced:

```text
reset 1: PC=0x0804A3E6 VTOR=0x08010000 CFSR=0x00000000
reset 2: PC=0x08029B1E VTOR=0x08010000 CFSR=0x00000000
```

Both bounded RTT captures contained:

```text
OTA: HANDOFF vtor=0x08010000 primask=0 basepri=0 faultmask=0 control=0
  systick=0x00000000 icsr=0x00000000 iser=0x00000000 ispr=0x00000000
OTA: BCB already CONFIRMED vcode=20802
```

The blank-BCB state-machine host cases prove that the first durable record is
`CONFIRMED` and that `cur_vcode` comes from the validated fw_header. The
hardware precondition plus the matching `20802` record proves the same path on
this board. The deployment tool itself does not clear or synthesize BCB data.

## 7. Direct recovery-container flash

Final command at `dbb5c37103537a2a8163b494f5a59e44bcaa7695`:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\Tools\jlink\flash-recovery-container.ps1 `
  -RecoveryContainer .\.cache\p1-5-deploy-remediation-2-20260728\recovery-v2.8.2.bin `
  -AppMap .\.cache\p1-5-deploy-remediation-2-20260728\gcc-release\app-gcc\X-Track-App-GCC.map `
  -LegacyHex .\MDK-ARM_F435\Objects\X-Track.hex `
  -RunDirectory .\.cache\p1-5-recovery-remediation-2-20260728
```

Result:

```text
P1_5_RECOVERY_TRAILER_STRIPPED=PASS
  container_len=563076 app_len=563068 bytes_removed=8
  app_sha256=2e3acc8da18111f595ca2829beae17fb1d482eec5870d171521071a909d00efb
  source_sha256=7bc5695f66f1b408e679ae6ab0fb15ba9c9cf77b0555bd6328eb96ab8939fd01
  source_preserved=1
P1_5_RECOVERY_FLASH=PASS
  pc=0x0802EAEA vtor=0x08010000 cfsr=0x00000000
  rtt=0x20044E04 source_preserved=1
```

`VerifyBin` passed for the stripped App at `0x08010000`. The live RTT
signature was `SEGGER RTT`, and the bounded capture contained the current
Boot-to-App HANDOFF line. Independent post-run hashing confirmed that the
source recovery container remained exactly 563076 bytes with the same SHA.

## 8. Failure recovery path

An earlier run intentionally failed after device modification because the
original evidence window was too short for the delayed App confirmation. The
catch path automatically loaded:

```text
selected-legacy-d535544e...-X-Track.hex
```

J-Link reported successful download from that selected hash-named path. The
subsequent successful run uses two 90-second reset windows and two bounded
30-second RTT captures; it does not weaken the matching-vcode predicate.

The distinct-content basename-collision host test proves that a repository
default with the same filename cannot replace this rollback source.

## 9. Hardware parameters and final state

Every J-Link operation used:

```text
Device=AT32F435RGT7
Interface=SWD
Speed=1000 kHz
```

RTT use followed the required sequence: stop stale logger, resolve the exact
map symbol, verify the RAM signature, run one bounded logger, then confirm no
logger remains. The board is running production Boot plus finalized v2.8.2
App after a real MCU reset. Final observed state is App-range PC,
VTOR=0x08010000, CFSR=0, and valid HANDOFF evidence. No JLinkRTTLogger or
JLinkRTTViewer process remains.

## 10. Exclusions and acceptance status

No frozen binary contract was changed. No external recovery slot was
installed, so this evidence makes no marker-last installation claim. The
P1-6 20-point power-loss matrix and physical power-cut cases were not run and
are not claimed.

P1-5 remediation implementation and evidence are complete, but this
implementation session does not mark the card complete. A different
non-implementation session must independently re-run the acceptance checks and
decide whether to close the card.
