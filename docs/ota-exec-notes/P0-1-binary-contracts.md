# P0-1 five binary contracts research

Date: 2026-07-24
Implementer: Codex

## Sources (read-only)

- `PLAN-OTA.md` v1.3.2 sections 2, 3, 4, 5.1 (and 6.1 for version_code encode rule cross-check)
- `PLAN-OTA-REVIEW-LOG.md` R4 (R3 five high-risk reconfirm + remaining P0 constraints) and R8 (five implementation acceptance items)
- `docs/ota-exec-notes/PRE-1-version-code.md` (version_code formula)
- `bsdiff_lzma_AES128-main/bsdiff/user/bs_user_interface.h` and `bspatch/user/interface.h` (`patch_header_t`)
- `bsdiff_lzma_AES128-main/bsdiff/lib/crc32.c` (IEEE CRC-32 reflected table, init 0xFFFFFFFF, final xor 0xFFFFFFFF)

## Findings to freeze in contracts

1. `FW_HEADER_OFFSET = 0x400` must be the single shared constant for linker / CI finalize / boot parse / recovery verify.
2. `version_code = major*10000 + minor*100 + patch` (u32); PRE-1 migration `2007 < 20700` stays normative.
3. Native `patch_header_t` is 40B on 32-bit ABI: 6*u32 + 5B LZMA props + 3B pad + u64. Host tool may write host-endian/sizeof; packer rewrites normalized layout. MCU must field-parse, never `memcpy` into a host struct.
4. CRC-32 used by BCB / fw_header / .etu / ETRJ / payload / recovery trailer matches the vendor table (poly reflected 0xEDB88320, init/xor 0xFFFFFFFF).
5. PLAN-OTA names BLE frame CRC as `crc16-ccitt` but does not freeze poly/init; contract freezes CRC-16/CCITT-FALSE (poly 0x1021, init 0xFFFF, no refin/refout, xorout 0).
6. PLAN-OTA gives ACK `status` field but no status table; contract freezes the status/error code table as the sole source.
7. INFO integer widths and BEGIN layout are incomplete in PLAN-OTA prose; contract freezes sequential little-endian field tables (R4 residual / C5).
8. R4 five high-risk closures and R8 five implementation acceptance items are numbered R4-1..R4-5 and R8-1..R8-5 with single contract anchors.

## Implementation decision

- Produce `docs/ota-binary-contracts.md` as the only byte-level definition site for the five contracts.
- Keep PLAN-OTA.md read-only; do not edit scheme text in this card.
- Evidence only; non-implementer session performs acceptance. No git commit/push.

## Deliverables

- `docs/ota-binary-contracts.md` (new)
- `docs/ota-exec-notes/P0-1-binary-contracts.md` (this note)

## Implementation record (2026-07-24, Codex)

Produced `docs/ota-binary-contracts.md` v1.0 with nine sections:

- §0 global: LE default (only 4 BE exceptions in inner header), CRC32-IEEE params frozen against vendor `crc32.c` table (0xEDB88320/0xFFFFFFFF/reflect/xor), CRC16-CCITT-FALSE frozen (0x1021/0xFFFF), magic table, address constants (`FW_HEADER_OFFSET=0x400` as four-party single source), capacity limits, PRE-1 version_code encoding, JEDEC whitelist.
- §1 fw_header 96B field table + SHA double-zero fill order + boot validation order.
- §2 .etu 64B outer header field table, flags legal combos (full=0x000B / patch=0x0007), payload two forms, **40B normalized inner header field-by-field offset/endian/CRC-coverage table** (ph_hcrc BE over 40B with bytes 0..3 zeroed; ph_psize/ph_ocrc/ph_ncrc BE; ph_osize/ph_nsize/u64 LE; pad 3B explicit zero), App receive checklist ordered.
- §3 BCB 64B×2 field table, seq arbitration ((int16)(a-b)>0, tie→A), safe-write transaction (8B pages, ACK polling ≤10ms, full readback), R4-1 atomic transition rules.
- §4 ETSL 32B (slot_type enum frozen 1..4; commit_marker u32 0x434F4D54 = on-flash bytes 54 4D 4F 43), staging 4KB page full offset table (ETSL@0x000 / rsv@0x020 / ETRJ@0x040 44B / pad@0x06C 4B / bitmap@0x070 64B / pad to 0xFFF), bitmap bit numbering (byte n>>3, bit n&7 LSB-first), marker-last write order (R4-3/R8-2), retx block erase-first rule (R8-1), resume strategy chosen = persistent session recovery (R4-3).
- §5 BLE frame layout (8B header + payload + crc16 LE over cmd..payload), cmd table, INFO 50B / BEGIN 101B / DATA / END 32B / ACK 9-10B payload tables, 128B segment / 32-per-block credit window (R4-4/R8-3/R8-4), **status code table frozen as sole source** (0x00..0x12 + 0xFF).
- §6 recovery trailer 8B (image_len u32 LE + crc32 u32 LE over app.bin), two-layer validation split, physical-recovery downgrade exception, J-Link strip-tail (R4-5).
- §7 R4-1..R4-5 + R8-1..R8-5 numbered with single contract anchors (R8-5 marked CF-side, no bytes here).
- §8 worked examples with computed CRCs: fw_header 0xFE1DCBD1, .etu full 0x14D0AA63, .etu patch 0x4CFFA9FF, BCB 0x507F7BAC, ETRJ 0xC0178C87, GET_INFO `a55a000000000000100e`, ACK `a55a820100000900000000000000000000ae56`.
- §9 downstream reference list (P0-2 packer, P0-3 vectors, P0-4 eeprom_bcb, P1/P2 parsers, P3 BLE, P4 CI).

## Implementation self-check (not acceptance)

- Field-size sums: fw_header=96, etu=64, inner=40, BCB=64, ETSL=32, ETRJ=44, INFO=50, BEGIN=101 — all OK (script output recorded in session).
- Sample hex lengths: 96/64/64/44/10/19B — OK; found+fixed one doc typo (BLE header 7B→8B) during self-check.
- R4/R8 anchor grep: 17 hits, §7 tables map every item to exactly one anchor.
- PLAN-OTA.md untouched (read-only honored). No git commit/push performed.

Awaiting non-implementer acceptance per PLAN-OTA-EXEC.md §0.3.