# P2-2 full-package implementation evidence (2026-07-29)

> Implementer: Codex P2-2 implementation session.
> Status: in progress. Implementation, host regression, builds, and true-board
> evidence are complete, but only a separate non-implementation session may
> accept the card and mark it complete.

## 1. Scope and baseline

```text
origin/main = bd9f4da0bee476d4ee2f4ba3f3e25b1e17b0d9ec
checkout    = D:\github\my\E-Track\.cache\checkout-B-P2-20260729
branch      = p2-1
P2-1 HEAD   = 80281db07ab00e6680d77f2ef079c6fe0498732a
```

This card implements only the frozen full-package `.etu` path with
`flags=0x000B`. Patch packages remain P2-3. P2-2 does not write an ETSL commit
marker, update either BCB copy, or enter STAGED. The frozen `PLAN-OTA.md` and
`docs/ota-binary-contracts.md` were not changed.

The design research and reuse decisions were frozen before implementation in
`docs/ota-exec-notes/P2-2-etu-full-package-research-2026-07-29.md`.

## 2. Portable parser and validation chain

`Libraries/OTA/ota_package.c` and `Libraries/OTA/ota_package.h` provide a
callback-based portable core. The 64-byte outer header is read by fixed offset
and explicit little-endian helpers. No host or MCU structure is overlaid on
package bytes.

The rejection order follows contract section 2.4:

1. magic, header length, and header CRC;
2. full-package flags, algorithm, and key ID;
3. hardware revision, layout ID, minimum Boot version, and strictly increasing
   target vcode;
4. full-package base fields and total package length;
5. complete encrypted-payload CRC before any candidate erase;
6. AES-128-CTR decryption and LZMA-Alone property/output-length validation;
7. bounded candidate erase, 1 KiB program, and immediate readback;
8. shared fw_header CRC/SHA/device validation plus outer/header vcode and image
   length agreement.

AES-CTR reuses the vendor AES block primitive but keeps counter, keystream,
and byte position across arbitrary input chunks. The nonce is the big-endian
128-bit counter and increments from byte 15 toward byte 0. LZMA uses the 7-Zip
decoder with frozen `lc=2/lp=0/pb=0`, a 4 KiB to 16 KiB dictionary, a 4 KiB
encrypted input buffer, and a 1 KiB output buffer.

Every candidate write checks both `image_len` and `OTA_APP_LENGTH` with
subtraction-based overflow-safe bounds. A successful program is read back and
compared before decoding continues. Late failures may leave an uncommitted
candidate payload, but its 4 KiB slot header remains erased and both BCB copies
remain byte-identical.

The shared fw_header validator now has an explicit validation flag. The legacy
Boot entry always enables MSP and Reset_Handler checks. P2-2 calls
`boot_fw_header_validate_ex(..., 0)` because the frozen toy image intentionally
contains vector sentinels; all CRC, double-zero SHA, device identity, Boot
version, version-name, padding, and image-length checks remain shared with
Boot.

`Libraries/OTA/ota_keys.c` accepts compile-time `OTA_AES_KEY_1_WORD0..3`
injection and rejects partial definitions. With no injected key, the build
uses the vendor example key and exposes that fact through
`ota_keys_uses_development_key()`. Production secret injection remains the
P4-4 deployment prerequisite.

## 3. HAL and overlay integration

`USER/HAL/HAL_OTA_Package.cpp` binds package reads to the staging payload and
candidate erase/program/readback to the existing safe QSPI path. XIP is
restored after every command-mode operation, and the port fails closed when
OTA QSPI is disabled.

The OTA workspace is a fixed 40 KiB array at `0x20058000`. It overlays the
existing 160 KiB LiveMap snapshot region rather than following it in memory.
An interrupt-protected owner byte makes LiveMap and package processing
mutually exclusive. LiveMap acquires on load and releases after unload; OTA
acquire fails while LiveMap owns the region.

Final map and ELF checks show:

```text
GCC .sram_ext    = 0x20058000, 0x28000, NOBITS
GCC .ota_overlay = 0x20058000, 0x0A000, NOBITS
AC5 .sram_ext    = 0x20058000, 0x28000, Zero/UNINIT
AC5 .ota_overlay = 0x20058000, 0x0A000, Zero/UNINIT
```

The evidence-only GCC layout reserves a 2 KiB NOBITS control block at
`0x20057800`; package bytes start at control offset `0x400`. The compile-time
test option defaults to OFF and is mutually exclusive with the P2-1 harness.
The production map has no P2-2 control region or evidence-only breakpoint
symbols.

## 4. Host regression

The final rerun against the current source completed with zero failures:

```text
fw_header vectors       16/16 PASS
Boot Ymodem/ETSL        19/19 PASS
BCB                     27/27 PASS
Boot state machine      96/96 PASS
P2-1 staging            48/48 PASS
P2-2 package           102/102 PASS
OTA golden vectors       9/9 PASS
P2-2 evidence protocol  16/16 PASS
```

The 102 P2-2 checks cover field-order rejection, package and payload lengths,
payload read/CRC failures, full-package base fields, AES/LZMA corruption,
dictionary and decoded-length limits, bounded writes, flash prepare/program/
readback failures, fw_header metadata mismatch, BCB immutability, fixed-pool
peak use, complete workspace wipe/release, and defensive release when a
successful acquire callback supplies a short workspace.

The production CI layout logic also passed with `.sram_ext` and
`.ota_overlay` at the same origin, and the Boot artifact/handoff validators
passed with App VTOR `0x08010000`.

## 5. Final builds

The final post-review build artifacts are preserved under:

```text
.cache/p2-2-final-build-assets-20260729
build_ts = 1785335957
```

Both fresh GCC configurations completed with zero errors and the repository's
existing newlib, wchar-width, and RWX-segment warnings.

```text
Test Boot: 14228 bytes
  SHA-256 50e651c62e01c58e29f6c4ab4cdb3da849d2ba04c42733e506c322bb500d6e77

Test App: 576912 bytes, vcode=20800
  raw SHA-256         6b706d35f243ac197800495afb4b7b1e6efc6e623a37356eda8c0cfcaa444db5
  finalized SHA-256   2f7ab81924cc151d56bf493da923f35a4e69b2be3af4ceb5ef9459b4d7a3c491
  double-zero SHA-256 ccdf5150ea2e0e6ca7e9479f6a62efaee4faae91ba68fd379bda065763dec098
  header CRC32        86f6fdcc

Production Boot: 14228 bytes
  SHA-256 50e651c62e01c58e29f6c4ab4cdb3da849d2ba04c42733e506c322bb500d6e77

Production App: 563188 bytes, vcode=20800
  raw SHA-256         3ecffdd8fe61ad080a3638cf3a264a3fdc7bf8c75d2a9ca77a8c6ca804a37eca
  finalized SHA-256   ea0f57a35992f6072d91588fc65a895cf2bd8c609db803906caf532b2999fcd8
  double-zero SHA-256 24ac3a2fb3a90f9eba54c26052b3250bced19e26bf95abb3ce99447f51ded581
  header CRC32        33e5420f
```

The final AC5 incremental build reused the generated dep/lnp commands and
reported no errors or warnings:

```text
Program Size: Code=265448 RO-data=288536 RW-data=1296 ZI-data=495380
Track-App-AC5.bin: 554784 bytes
SHA-256: 5f075ebcc706a8ab13a739bfed37462f67c68a39562152038226e084cfb8c926
```

## 6. True-board evidence

The only valid hardware evidence root is:

```text
.cache/p2-2-hardware-evidence-20260729-r3
P2_2_HARDWARE=PASS cases=4 checks=112
```

Its 73-entry SHA-256 manifest was independently recomputed with no missing or
mismatched file. All J-Link activity was strictly serial. Every case used one
Commander process, wrote the 2 KiB RAM control block as 512 explicit `w4`
operations, and wrote command magic last. No control block was restored with
J-Link `loadbin`, so there was no implicit reset in the evidence path.

```text
success         34 checks, expected=0,   actual=0
bad-header-crc  26 checks, expected=-5,  actual=-5
bad-payload     26 checks, expected=-15, actual=-15
equal-version   26 checks, expected=-12, actual=-12
```

For every case the first halt was the ready symbol at `0x08043308` and the
second halt was the done symbol at `0x0804330C`. VTOR was `0x08010000` and
CFSR was zero. The common raw BCB snapshot SHA-256 across all four cases was:

```text
2d72cc838e342d3061749bcaba88397b46a476424846af41edbfbbc1b90d6fba
```

The successful candidate was the 4096-byte frozen `toy-new.bin`:

```text
file SHA-256 f68f357c708c2d65e6b1547648e955ea47949d81bd52f2cded684a8f640e21c3
workspace peak 33008 bytes, below the fixed 40960-byte pool
candidate prepares/programs/bytes = 1/4/4096
candidate slot header remained fully erased
```

The three early-rejection cases performed zero candidate prepare/program
operations. All four cases staged exactly one package copy, wiped the overlay,
and left both BCB copies byte-identical.

The r3 run used the evidence App preserved in
`.cache/p2-2-hardware-assets-20260729`, finalized SHA-256
`196e01f8a05a7b89f0d6a67a4efb49735a3b9b49a92cd6e762507eb163c9c1f0`.
The final code review then added only the defensive short-workspace
wipe/release branch and its host assertion. The hardware port always returns
the exact 40960-byte overlay; r3 success took that exact-size path, while the
three rejection cases never acquired the workspace. The review delta is
therefore outside all four captured hardware trajectories. The separate
acceptance session must still decide whether any additional true-board rerun
is required.

These directories are diagnostic only and must never be cited as PASS:

```text
.cache/p2-2-hardware-evidence-20260729-r1
.cache/p2-2-hardware-evidence-20260729-r2
```

`r1` used J-Link `loadbin` against the RAM control block, which introduced an
implicit reset and invalidated injection semantics. `r2` completed and
verified all four binary cases, but summary aggregation failed and did not
produce a valid run-level PASS artifact. Production restore passed after both
diagnostic runs; only r3 is accepted implementation evidence.

## 7. Production board restore

After r3, production Boot and the finalized production App were serially
programmed and both VerifyBin operations passed. The final diagnostic observed:

```text
PC   = 0x08042D24 (production App)
VTOR = 0x08010000
CFSR = 0x00000000
RTT  = 0x20044E04
RAM  = 53 45 47 47 45 52 20 52 54 54 (SEGGER RTT)
```

The board was resumed in the production App. The final process check found no
`JLink`, `JLinkGUIServer`, `JLinkRTTLogger`, or `JLinkRTTViewer` process.

## 8. Acceptance status

P2-2 remains `in progress`. This implementation session does not self-accept,
push, or mark the card complete. A separate non-implementation session must
rerun the card's acceptance checks before completion.
