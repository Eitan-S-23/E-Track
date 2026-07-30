# P2-1 staging implementation evidence (2026-07-29)

> Implementer: Codex P2-1 implementation session.
> Status: in progress. Implementation and true-board reset re-entry evidence
> are complete, but only a separate non-implementation session may accept the
> card and mark it complete.

## 1. Scope and baseline

```text
origin/main = bd9f4da0bee476d4ee2f4ba3f3e25b1e17b0d9ec
checkout    = D:\github\my\E-Track\.cache\checkout-B-P2-20260729
branch      = p2-1
```

This card implements only the staging receiver and its durable receive log.
P2-2 package parsing, AES-CTR, LZMA-Alone extraction, downgrade policy, and
candidate-image validation remain out of scope. The frozen `PLAN-OTA.md` and
`docs/ota-binary-contracts.md` were not changed.

## 2. Implementation

The portable receiver is in `Libraries/OTA/ota_staging.c` and
`Libraries/OTA/ota_staging.h`. It uses explicit fixed-offset little-endian
serialization rather than structure persistence.

- The header sector contains ETSL at `0x000`, ETRJ at `0x040`, and the
  persistent block bitmap at `0x070`; payload starts after the 4 KiB slot
  header.
- ETRJ records magic, the complete 32-byte package SHA-256, total length, and
  CRC32 over its immutable 40-byte prefix. A matching valid ETRJ resumes in
  place. An invalid record or a different package identity rebuilds the whole
  header sector before writing and reading back the new ETRJ.
- The receiver owns one 4 KiB RAM block divided into 32 segments of 128 bytes.
  Segments may arrive out of order inside the current block. Identical in-RAM
  retransmissions are idempotent; conflicting retransmissions are rejected.
- Before an uncommitted block is written or rewritten, its complete 4 KiB NOR
  sector is erased. Data is programmed and read back before the persistent
  block bit is cleared. A reset after data readback but before the bit clear
  therefore retransmits, re-erases, and rewrites the same block.
- DATA below `durable_off` is acknowledged as a duplicate without any erase or
  program operation.
- Finalization writes and reads back the first 28 ETSL bytes before programming
  the four-byte `0x434F4D54` commit marker separately. Re-entry after the field
  write programs only the erased marker; a committed matching ETSL is
  idempotent.

`USER/HAL/HAL_OTA_Staging.cpp` binds the receiver to the existing safe QSPI
path, restores XIP after every erase/program operation, and rejects use when
OTA QSPI is disabled. Both Keil targets and the isolated GCC App target include
the staging source. The CI host-test step now runs the portable staging suite.

## 3. Host tests

The final rerun used the current uncommitted implementation and completed with
zero failures:

```text
fw_header vectors       16/16 PASS
Boot Ymodem/ETSL        19/19 PASS
BCB                     27/27 PASS
Boot state machine      96/96 PASS
P2-1 staging            48/48 PASS
OTA golden vectors       9/9 PASS
P2-1 evidence protocol  59/59 PASS
```

The 48 staging checks include the frozen ETRJ CRC sample, golden `toy-full.etu`
payload, matching-session resume, invalid/different-session rebuild, out-of-
order and duplicate DATA, full-sector retransmit after interruption, readback
failure, bitmap durability, ETSL marker-last finalization, finalize re-entry,
and range/state rejection.

## 4. Test-enabled GCC build

The fresh evidence build is
`.cache/p2-1-test-gcc-20260729-r2` with
`P2_1_TEST_ENABLE:BOOL=ON`. It completed with zero errors and the repository's
existing App warnings.

```text
Boot binary 14208 bytes
  SHA-256 5a83295128b4266e44f251b825edb765907e5787540cdb9540e951dc3be6c057

Finalized test App 567160 bytes, vcode=20800
  SHA-256     44a9011e27f08ef5c43851733bc5e2a14d28c8ce56d31437d28d61899add8be9
  header CRC  2c50b6cf
```

The evidence-only control block is exactly `0x80` bytes at `0x20057F80` in
both test linker layouts. The two App breakpoint symbols are:

```text
HAL_OTA_StagingEvidenceCheckpoint = 0x08041FC8
HAL_OTA_StagingEvidenceDone       = 0x08042084
```

The compile-time option defaults to `OFF`; the production ELF contains none of
the control region or evidence-only symbols.

## 5. True-board reset re-entry

The only valid hardware evidence root is:

```text
.cache/p2-1-hardware-evidence-20260729-r3
P2_1_HARDWARE=PASS checks=59
```

Session and payload identity:

```text
session SHA-256 955818d42a5780a09d2f57b178515aed746bbd443278038181a0c2fed4c92945
payload CRC32   0xF1895AA4
payload SHA-256 f1a9116e64d5ce92231de69558afad42a650a9ee7ad481813ef824d649784ded
```

At the first halt, PC was `0x08041FC8`, VTOR was `0x08010000`, CFSR was zero,
and the control status was `CHECKPOINT`. ETRJ and the complete payload had been
read back, while `durable_off=0` and the persistent bitmap remained `0xFF`.
Counters were header/data/program=`1/1/1`.

After an ordinary reset, the second halt was exactly `0x08042084`, again with
App VTOR and zero CFSR. The receiver reported `resumed=1`,
`durable_off=4096`, persistent bitmap `0xFE`, and counters `1/2/2`. ETRJ was
unchanged across reset, the payload was byte-identical, ETSL fields matched the
session, and its separately programmed marker was valid.

Exactly two halt events were required and observed. All J-Link commands were
run serially; no logger or viewer overlapped the evidence run.

These diagnostic directories are explicitly invalid and must never be cited
as pass evidence:

```text
.cache/p2-1-hardware-evidence-20260729-r1
.cache/p2-1-hardware-evidence-20260729-r2
```

`r1` cleared breakpoint handle 0 although J-Link V8.18 assigned handle 1.
`r2` completed the staging behavior but the harness tested the post-DATA
`progress.resumed` value instead of the latched begin result and emitted
`FAIL/detail=0x60`. The harness-only check was corrected; the staging core was
unchanged. Only `r3` is valid.

## 6. Production builds and board restore

The fresh production GCC build is
`.cache/p2-1-production-gcc-20260729` with
`P2_1_TEST_ENABLE:BOOL=OFF`. It completed with zero errors and existing App
warnings. Its link map has no `P2_1_CTRL` region or evidence-only symbol.

```text
Production Boot 14208 bytes
  SHA-256 411f3e1d703f07bd107d0f1f4f9687a54bd69981c63cc70d3f421ad15494ac3c

Production App 563036 bytes, vcode=20800, build_ts=1785326196
  raw build SHA-256    d117d7e3fbc43ed128798b35eaabd51619a92152ed7920577dca1ec74c064f4e
  finalized SHA-256    0c26a86caf93faab71fea0fb7da4e917d0933eeaede39d6c8650a8a76e0577b8
  double-zero SHA-256  72fa3a5d72cb1681a97d5628831b6c8ece3ff39e233df5795fda7ae53bbbcd59
  header CRC32         f0410611
```

Boot and finalized App were serially programmed and both J-Link VerifyBin
operations passed. The first 3-second reset window halted in Boot
`sha256_transform` at `0x08000344`; VTOR was still `0x08000000` and CFSR was
zero. This was a short observation window during full App validation, not a
pass result and not a reset reason. The script had already resumed the core, so
the next diagnostic continued in place without another reset.

The continued diagnostic then observed:

```text
PC     = 0x08042CE4 (App main)
VTOR   = 0x08010000
CFSR   = 0x00000000
RTT    = 0x20044E04
memory = 53 45 47 47 45 52 20 52 54 54 (SEGGER RTT)
```

The board was resumed and left running the production App. All
`JLinkRTTLogger`, `JLinkRTTViewer`, `JLink`, and `JLinkGUIServer` processes were
cleaned and the final process-set check was empty.

The independent Keil target `X-Track-App-AC5` also built successfully with ARM
Compiler 5.06 update 5:

```text
Program Size: Code=265320 RO-data=288536 RW-data=1292 ZI-data=454424
0 Error(s), 0 Warning(s)
Build Time Elapsed: 00:04:51
Track-App-AC5.bin: 554660 bytes
SHA-256: e1b7ec81e47df827f137d3a8d0b0ffb8527d2a3eabe824e00cfecddf008bb64f
```

## 7. Acceptance status

P2-1 remains `进行中`. The implementation session does not self-accept or mark
the card complete. A separate non-implementation session must rerun the card's
acceptance checks and append its result before completion.
