# P1-1 Boot skeleton implementation evidence (2026-07-27)

> Implementer: Codex implementation session.
> Status: implementation, clean-checkout CI, and independent acceptance are complete.
> Independent acceptance: Codex non-implementation session, 2026-07-28, from clean
> `origin/main=03217f9bb911531cb9ad0be92762f08fc87319ce`.
> The card is accepted and may be marked `完成`.
> P1-4/P1-5 are not implemented, so Boot intentionally holds and no normal reset/run handoff was attempted.

## 1. Scope and dependency isolation

`X_Track_Boot` is a separate GCC executable target using the controlled
`cmake/linker/x-track-boot-gcc.ld.S` source and isolated `<build>/boot/` outputs.
Its explicit source list contains only:

- pure-C Boot runtime, CRC32, SHA-256, `fw_header`, ETSL, Ymodem, recovery, and platform code;
- the existing pure-C EEPROM BCB implementation;
- the AT32 startup/system files and the CRM/Flash/GPIO/QSPI/USART vendor drivers needed by Boot.

It does not inherit App/Arduino/Bluetooth/SdFat/SEGGER RTT include paths or App compile definitions.
The linked map and explicit source list contain no LZMA, bspatch, Bluetooth/TinyBT, or AES dependency.
Boot is compiled with `-Werror`; the final Release build has zero Boot warnings and errors.

Automated check:

```text
P1_1_BOOT_ASSERTIONS=PASS bin=10452 vector=0x08000000/0x20c msp=0x20058000 reset=0x08001aa5
```

## 2. Link layout, size, and artifacts

Final Release build command:

```text
cmake --build .cache/p1-1-final --target X_Track_App_GCC X_Track_Boot --parallel
```

Final Boot linker/map result:

```text
FLASH       0x08000000 / 0x00010000
RAM         0x20000000 / 0x00058000
.isr_vector 0x08000000 / 0x20c
entry       0x08001aa5
boot.bin    10452 bytes / 65536 bytes (15.95%)
RAM used    5664 bytes / 360448 bytes (1.57%)
```

`arm-none-eabi-readelf -lW` reports only an `R E` Flash LOAD segment and `RW` RAM LOAD
segments. There is no RWX LOAD segment.

Local Windows GNU 13.3.1 SHA-256 values:

```text
X-Track-Boot.bin eff3edbe72f7799636d175963e54c3dd35be358419b1fa83cf9c4d9a0d065170
X-Track-Boot.hex 51c10477dd8eff4f956c1c6fcf72a5351c8d5391f5df7c3362594184d75ebaad
X-Track-Boot.elf 53f9774ee4b7deb24bab1e33dcdc3e73bd5ef6fcc50078956ecf1d9fcb37312a
X-Track-Boot.map 36b5ee3acf4717c32a8efa1628f4054a0cd968446d2c2d263bd3aa41eb80275c
```

## 3. Unified fw_header validation

`boot_fw_header_validate()` reads through an injected image reader and validates:

1. magic and header CRC32;
2. header version and bounded `image_len`;
3. full-image SHA-256 using the frozen double-zero rule;
4. hardware revision, layout ID, and minimum Boot version;
5. initial MSP and Thumb Reset_Handler ranges;
6. a non-empty, fully zero-padded ASCIIZ version field and `0xFF` header padding.

The host test compiles the same MCU C sources (`boot_fw_header.c`, `boot_crc32.c`, and
`boot_sha256.c`) and derives offset/size limits from `Libraries/OTA/ota_layout.h`.

```text
P1_1_FW_HEADER_VECTORS=PASS cases=16
```

Covered cases: valid, bad magic, stale header CRC, wrong header version, short image length,
bad image SHA, wrong hardware/layout, Boot too old, bad MSP, bad Reset_Handler, top-of-RAM MSP,
missing/empty/dirty-padded version name, and dirty header padding.

The same host C validator accepted the current finalized App-GCC image:

```text
raw App size/SHA-256:       560988 / c71e4d85751e85fa08d6ef19829b1892eb33a4cbc2a870e51a2dbd96668d7683
final App size/SHA-256:     560988 / 0a97b711d2c79f31f254c2da0df8c37eb930c7804389080ff0bd21bb6fa9a101
stored/recomputed image SHA: 0c5deb0677ff282a6d23764dfce0dd5fd32a779cb069d7986003bec083c83c4d
stored/recomputed header CRC: 6ced5e47
validator result: ok
```

## 4. BCB, QSPI, and ETSL skeleton

- The Boot target links the existing `eeprom_bcb.c` and calls `bcb_arbiter()` through a
  Boot-local EEPROM HAL. The existing strict host suite remains `27/27 PASS`, `0 failure(s)`.
- QSPI initialization exits stale XIP/continuous-read state with `0x66/0x99`, reads JEDEC
  `0x9F`, applies the frozen whitelist, and uses bounded 100 ms command waits. Failure skips
  the external-slot branch fail-closed.
- Candidate ETSL is read from `OTA_EXT_CANDIDATE`; marker, type, padding, and per-slot length
  limits are parsed by `boot_slot_header_parse()`.
- Host protocol tests cover valid candidate/staging headers plus missing marker, oversize,
  wrong-type, and dirty-padding rejection.

## 5. Physical recovery and internal Flash programming

- Recovery entry requires PA15 to remain asserted for at least 3000 ms after GPIO setup.
- UART5 Ymodem supports 128-byte and 1 KiB packets, CRC16-XMODEM, sequence wrap, duplicate
  packet idempotence, retry/NAK, cancellation, and bounded byte/packet waits.
- The Ymodem final ACK is emitted only after the 8-byte recovery trailer length/CRC transport
  check succeeds. The slower full `fw_header`/SHA validation runs after transport completion,
  preserving the contract's two validation layers without making the sender wait for SHA.
- Recovery writes only `[OTA_APP_ORIGIN, OTA_APP_ORIGIN + OTA_APP_LENGTH)`, pads the final word
  with `0xFF`, verifies every programmed chunk, checks trailer `image_len == fw_header.image_len`,
  and permits the physical-recovery version downgrade exception by not comparing vcode.

Host protocol result:

```text
P1_1_BOOT_PROTOCOLS=PASS
19 checks, 0 failure(s)
```

The protocol suite covers valid 1 KiB/128-byte transfer, CRC retry, duplicate DATA idempotence,
sink failure abort/CAN behavior, and the ETSL cases listed above.

### 5.1 AT32 erase-unit correction

The official installed Keil Flash algorithm declares 2 KiB erase sectors. The descriptor is at
ELF virtual address `0x410` (file offset `0x444`), not raw file offset `0x410`:

```text
AT32F435_1024.FLM DevDscr @ 0x410: 00080000 00000000
```

The first little-endian word is sector size `0x800`, address `0`. Therefore a logical OTA
4 KiB copy block must erase two consecutive hardware sectors. `boot_platform_flash_erase_4k()`
now erases `address` and `address + 0x800`, rejects unaligned/out-of-App blocks, and verifies the
complete 4 KiB range is `0xFFFFFFFF` before programming.

## 6. CI integration and local gates

The workflow now:

- triggers on `boot/**`, `cmake/**`, and `tests/boot/**` for both push and pull request;
- builds `X_Track_App_GCC` and `X_Track_Boot` in the same clean configure;
- runs the 16 fw_header vectors, 19 protocol checks, and Boot artifact assertions;
- uploads App and Boot as separate artifacts, preserving the gated release job's existing
  `firmware-release-assets/X-Track-App-GCC.bin` path while still publishing all four Boot files.

Local gates:

```text
WORKFLOW_YAML_PARSE=PASS
python -m py_compile: PASS
git diff --check: exit 0 (only the repository's existing LF/CRLF warning)
```

### 6.1 Clean-checkout CI

Implementation commit `b4783931053d6995009ec2352b64566ba6ea9596` was pushed to
`origin/main`. GitHub Actions `MCU Firmware Build` run `30283525908` completed
`success` from a clean checkout:

```text
Build firmware:                         PASS
P1_1_FW_HEADER_VECTORS:                 PASS cases=16
P1_1_BOOT_PROTOCOLS:                    PASS checks=19
P1_1_BOOT_ASSERTIONS:                   PASS bin=10452 vector=0x08000000/0x20c
Upload firmware artifact:               PASS firmware-2.7-nightly.32 (4 files)
Upload Boot artifact:                   PASS boot-2.7-nightly.32 (4 files)
Register firmware to Cloudflare:        SKIPPED (push run; release gate unchanged)
```

The downloaded clean-checkout Boot artifact contains:

```text
X-Track-Boot.bin  10452 bytes  7989a7299b426eff0df644902d8d3bf1a3ba462b01f10ebdf6f6006a68821a1e
X-Track-Boot.hex  29470 bytes  d1c16844ea7bcc206ced0325e8a99866f042d76a3be7f69fe76695867f12131e
X-Track-Boot.elf  29632 bytes  673f1107d410c32edfdbfbfd5747ca6fcf19c768af8f81991a3f6f215245fb2f
X-Track-Boot.map  91631 bytes  5b77f44908164400eb814f5440d0f89dbb9e0838eb8150b9f8ac8dc4466bab9e
```

The Windows and Linux GNU 13.3.1 Boot binaries have the same size and layout but
different hashes. Binary/symbol comparison localized the difference to the linked
newlib `memset`/`memcpy`/`memcmp` ordering and the resulting branch offsets; the
source-controlled Boot code and all layout assertions are unchanged. The CI Linux
artifact hashes above are the clean-checkout reference values.

## 7. Explicit exclusions and next evidence

- P1-4 handoff and P1-5 bootstrap are not part of this card and are not implemented here.
- Boot ends in `boot_platform_hold()` after inspection/recovery, so this implementation was not
  flashed or used for ordinary reset/run startup acceptance.

## 8. Independent acceptance (2026-07-28)

### 8.1 Baseline and method

- Acceptance was performed in a separate worktree created directly from clean
  `origin/main=03217f9bb911531cb9ad0be92762f08fc87319ce`. The starting worktree was clean.
- `git diff b478393..03217f9` contains only the evidence/board closeout; the P1-1 implementation
  under test is the exact `b4783931053d6995009ec2352b64566ba6ea9596` source.
- No implementation-session build directory was reused. CMake configured a fresh Release tree and
  built `X_Track_App_GCC` plus `X_Track_Boot` with Windows Arm GNU Toolchain 13.3.Rel1 (GCC 13.3.1).
- P1-4/P1-5 remained excluded. No flash operation and no ordinary J-Link reset/run startup claim
  were made.

### 8.2 Boot layout, vectors, RAM, permissions, and dependency redlines

The fresh build and independent artifact validator passed:

```text
P1_1_BOOT_ASSERTIONS=PASS bin=10452 vector=0x08000000/0x20c
                              msp=0x20058000 reset=0x08001aa5
```

Independent `readelf -lW` inspection showed the same loadable layout locally and in the downloaded
CI ELF:

```text
entry 0x08001aa5
LOAD 0x08000000 filesz/memsz 0x28d0  R E
LOAD 0x20000000 filesz 0x0004 memsz 0x0420  RW
LOAD 0x20000420 filesz 0x0000 memsz 0x1200  RW
```

There is no RWX LOAD segment. Flash use is `10452/65536` bytes. RAM use is
`.data 4 + .bss 1052 + heap/stack reservation 4608 = 5664` bytes. The vector table is at the Boot
origin and its initial MSP is the top of the contracted main RAM. The explicit Boot source/include/
definition sets and the linked map contain no LZMA, bspatch, Bluetooth/TinyBT, AES, Arduino,
SdFat, or SEGGER RTT dependency. Boot compiles with `-Werror`; the fresh dual-target build retained
the App target's pre-existing warnings, but produced no Boot warning or error.

Fresh local Boot hashes were:

```text
X-Track-Boot.bin  10452  eff3edbe72f7799636d175963e54c3dd35be358419b1fa83cf9c4d9a0d065170
X-Track-Boot.hex  29470  51c10477dd8eff4f956c1c6fcf72a5351c8d5391f5df7c3362594184d75ebaad
X-Track-Boot.elf  29636  53f9774ee4b7deb24bab1e33dcdc3e73bd5ef6fcc50078956ecf1d9fcb37312a
```

### 8.3 Unified `fw_header` and host suites

- The same Boot C validator sources passed all 16 golden cases: valid image; bad magic/header CRC/
  header version/image length/SHA/hardware/layout/minimum Boot/MSP/Reset_Handler; top-of-RAM MSP;
  invalid version ASCIIZ forms; and dirty header padding.
- A fresh `X-Track-App-GCC.bin` was finalized through `Tools/etu_pack.py`, accepted by
  `Tools/etu_unpack.verify_fw_header`, and then accepted by the independently compiled
  `boot_fw_header_validate()` host executable. Result: `image_len=561164`, stored/recomputed
  double-zero SHA-256
  `e0f6dbdaabb925020f3fbbc6cab93fbe57f025385fc4a09730f581273544d899`, and stored/recomputed
  header CRC32 `df9393ee`.
- Ymodem/ETSL host suite: `19 checks, 0 failure(s)`. It exercised 1 KiB and 128-byte packets,
  DATA CRC retry, duplicate idempotence, sink failure/CAN, and ETSL marker/type/padding/length
  rejection.
- Shared BCB host suite: all `27/27` checks passed, including wrap arbitration, equal-seq A choice,
  both-invalid handling, `seq+1` commit ownership, readback failure, stale active rejection, and
  bootstrap.

### 8.4 QSPI, internal Flash, and physical recovery

- QSPI command completion is bounded by `BOOT_QSPI_TIMEOUT_MS=100`. Initialization disables XIP,
  sends `0x66/0x99`, reads JEDEC with `0x9F`, and applies the frozen whitelist. `boot_main.c` enters
  the external candidate branch only when initialization and the slot-header read both succeed;
  failure skips that branch fail-closed.
- The installed official `AT32F435_1024.FLM` is an ELF. Its `DevDscr` section starts at virtual
  address `0x370` / file offset `0x3A4`; therefore the first sector descriptor at virtual address
  `0x410` maps to file offset `0x444`, not raw file offset `0x410`. The bytes are
  `00 08 00 00 00 00 00 00`, proving sector size `0x800` (2 KiB) from address zero.
- Fresh Boot disassembly contains two `flash_sector_erase` calls, the second at `address+0x800`,
  followed by a complete `0x1000`-byte `0xFFFFFFFF` verification loop. Programming is constrained
  to the App interval, word-aligned, and followed by readback comparison.
- PA15 is configured input/pull-up and treated as active low. The compiled loop compares elapsed
  milliseconds against 2999 with an unsigned `>` branch, which accepts only elapsed time
  `>=3000 ms` while the key remains continuously asserted.

### 8.5 Clean-checkout CI and artifact isolation

GitHub run `30283525908` was queried independently. It is a successful push run for
`headSha=b4783931053d6995009ec2352b64566ba6ea9596`; build, the two Boot host suites, App layout,
Boot assertions, and both upload steps succeeded. The Cloudflare registration job was skipped as
required for a push run.

The downloaded artifacts are isolated and contain exactly four files each:

```text
firmware-2.7-nightly.32: X-Track-App-GCC.{bin,hex,elf,map}
boot-2.7-nightly.32:     X-Track-Boot.{bin,hex,elf,map}
```

The CI Boot binary is `10452` bytes with SHA-256
`7989a7299b426eff0df644902d8d3bf1a3ba462b01f10ebdf6f6006a68821a1e`.

### 8.6 Windows/CI Boot hash difference

The local and CI binaries have identical length, entry point, program headers, loadable section
sizes, and all source-controlled symbol addresses. Of 224 common defined symbols, exactly three
addresses differ:

```text
Windows: memcmp 0x08002418, memset 0x08002438, memcpy 0x08002448
CI:      memset 0x08002418, memcpy 0x08002428, memcmp 0x08002444
```

Each function body is byte-identical between toolchains. The binaries differ in 97 bytes total.
Every differing byte is accounted for by the reordered contiguous newlib block
`0x08002418..0x08002464` or by one of 22 `BL`/`B.W` call sites whose branch displacement targets
one of those three functions; unexplained differing bytes: `0`. This independently confirms that
the local/CI Boot binary hash difference is caused by newlib `memset`/`memcpy`/`memcmp` link order
and the resulting branch offsets, not by a source, layout, or behavior change.

### 8.7 Decision

All P1-1 acceptance items pass. P1-1 may be marked `完成`, and P1 progress may advance to `2/6`.
P1-4 handoff and P1-5 bootstrap remain outside this card and require their own later evidence.
