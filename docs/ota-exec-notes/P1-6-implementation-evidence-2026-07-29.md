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

Every `row-XX/row-summary.json` contains the pre-injection raw BCB A/B bytes,
arbitrated fields, slot/version/hash evidence, checkpoint and injection
mechanism, each reset trajectory, final App version, raw SHA-256, double-zero
SHA-256, header CRC32, and one terminal classification.

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
