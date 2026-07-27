# P1-1 Boot skeleton implementation evidence (2026-07-27)

> Implementer: Codex implementation session.
> Status: local implementation evidence is complete; clean-checkout CI and independent acceptance are pending.
> The card remains `进行中`. This implementation session must not mark it `完成`.
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

Final SHA-256 values:

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

The official installed Keil Flash algorithm declares 2 KiB erase sectors:

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

## 7. Explicit exclusions and next evidence

- P1-4 handoff and P1-5 bootstrap are not part of this card and are not implemented here.
- Boot ends in `boot_platform_hold()` after inspection/recovery, so this implementation was not
  flashed or used for ordinary reset/run startup acceptance.
- The clean-checkout GitHub Actions run ID/result must be appended after push.
- A separate non-implementation session must independently review this evidence and the current
  source before changing P1-1 from `进行中` to `完成`.
