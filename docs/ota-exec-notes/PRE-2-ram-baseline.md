# PRE-2 RAM baseline research

Date: 2026-07-24
Implementer: Codex

## Sources

- PLAN-OTA-EXEC PRE-2 card
- `.claude/verification-report-ota-plan.md` supplement C
- `MDK-ARM_F435/cmake-generated/cmake/generated_linker.ld` MEMORY block
- `USER/App/Pages/LiveMap/LiveMap.cpp` snapshotBuf / `.sram_ext`

## Code facts checked

- Linker (F435 GCC path used by CI `CMAKE_PROJECT_DIR=MDK-ARM_F435/cmake-generated`):
  - `RAM`: ORIGIN `0x20000000`, LENGTH `0x58000` = 352 KiB
  - `RW_IRAM2`: ORIGIN `0x20058000`, LENGTH `0x28000` = 160 KiB
  - Sum = `0x80000` = 512 KiB (EOPB0-extended on-chip RAM)
  - `.sram_ext (NOLOAD)` placed in `RW_IRAM2`
- LiveMap.cpp:
  - Comment: low 384K tail + EOPB0 high 128K continuous region
  - `snapshotBuf[SNAPSHOT_W * SNAPSHOT_H]` with W=256, H=320
  - RGB565: 256*320*2 = 163840 = `0x28000` = full RW_IRAM2
  - Static section attribute `.sram_ext` under ARDUINO; does not free on page unload

## Stale scheme text (pre-change)

- §1 MCU row: "RAM 384KB(App 现用 82.96%)"
- §9: "App 总 RAM 384KB,常态占用 82.96%(≈319KB,余 ~65KB)" and "60KB ≤ 65KB"
- These treat 384KB as total denominator and do not account for the 160KB region filled by `snapshotBuf`.

## Implementation decision

- §1: record 512KB total, 352+160 split, snapshotBuf occupancy; mark old 384/82.96/65 wording retired; defer measured %/peaks to P0-6/P2-6
- §9: three bullets — baseline, overlay evaluation with acceptance definition (A adopt / B reject) owned by P0-6, peak budget placeholder without inventing new KB math
- Header: v1.3.2 PRE-2 patch note
- Scope limited to PLAN-OTA.md; no code/linker changes
