# P2-4 SD File Manager Research (2026-07-31)

## Scope

P2-4 replaces the OTA App/simulator `About device` menu entry with an SD file
manager, filters files to case-insensitive `.etu`, shows current and target
versions before a second confirmation, copies the selected package into the
existing staging receiver, and enters the existing full/patch candidate apply
chain.

The task stops before P2-5. It must not copy the current image to backup, write
BCB `STAGED`, or request a reboot. P2-6 RAM evidence is also out of scope.

## Frozen Contracts

- `PLAN-OTA.md` section 5.2 is the UI/data-flow authority.
- The outer header is 64 bytes and is parsed field-by-field. Valid v1 flags are
  `0x000B` for full and `0x0007` for patch.
- Header CRC covers bytes 0..59. The encrypted payload CRC covers bytes after
  the 64-byte header. Package length must equal `64 + payload_len`.
- The target version must be greater than the running version. A full package
  requires zero base version/SHA. A patch requires the running version and the
  first eight bytes of the raw running-image SHA-256.
- `ota_staging_begin()` requires the SHA-256 of the complete `.etu`, while
  `ota_staging_finalize()` requires the CRC32 of the complete `.etu` rather
  than the payload-only CRC from the outer header.
- SD import therefore uses two passes: validate/hash the complete file first,
  then feed aligned 128-byte segments to the existing 4 KiB staging window.
  The second pass is hashed again so a file changed between passes cannot be
  committed.
- After marker-last staging finalization, full packages call
  `HAL::OTA_PackageApplyStaging()` and patch packages call
  `HAL::OTA_PatchApplyStaging()`. These existing APIs build and validate the
  candidate but deliberately do not modify BCB state.

## RouteSelect and LVGL Rules

- Start at LVGL path `/`; do not bypass the drive-letter stripping contract.
- Directory entries are identified by a leading `/`. Hidden names and
  `System Volume Information` are skipped.
- Preserve directories and filter only non-directory files, using a
  case-insensitive `.etu` suffix check.
- Build child paths as `/<name>` at root and `<parent>/<name>` elsewhere.
- Use `lv_async_call()` for directory transitions so list event callbacks do
  not destroy their own object tree.
- Disable the default `lv_list_add_btn()` row layout and explicitly align the
  icon and label.
- On unload, remove only objects owned by this page from the default group;
  never call `lv_group_remove_all_objs()` after a parent page may have rebuilt
  its group.
- Use plain labels, images, bars, and rectangles. Do not add shadows, draw
  callbacks, masks, or custom `lv_draw_*` paths.

## Integration Boundaries

- The legacy `X-Track` target does not link the App OTA package/patch chain.
  FirmwareUpdate registration and menu routing must therefore be guarded by
  `OTA_TARGET_APP || _WIN32`; the legacy target keeps its existing About page.
- The App AC5 target already links staging, full, patch, boot CRC/SHA, and
  firmware-header validation. A new page group must copy RouteSelect's full
  `<GroupOption>` including `--cpp11`.
- The simulator has no production QSPI/HAL OTA backend. It will use a NOR-like
  in-memory staging backend and stop at simulated candidate-ready after the
  real header/hash/staging code succeeds.
- Production `App.cpp` must remain on `manager.Push("Pages/Startup")` after
  simulator evidence is captured.

## UI Text and Fonts

`font_cn_16.c.chars` contains the characters needed for `文件管理`, `当前版本`,
`文件版本`, `开始导入`, `导入中`, `已就绪`, `导入失败`, `文件无效`, and `返回`.
The page will use these existing-glyph strings and ASCII `FULL`/`PATCH` labels;
no font regeneration is required.

## Validation Plan

1. Add a portable host suite for full/patch preflight, rejection cases,
   payload/whole-package integrity, marker-last staging, resume, and
   between-pass mutation rejection.
2. Build and inspect a dedicated simulator screenshot, then restore and rebuild
   the production Startup entry. Check at least two simulator launches.
3. Build the fresh GCC Release OTA App and the AC5 `X-Track-App-AC5` target,
   recording errors, warnings, Program Size, timestamps, and hashes.
4. Record only P2-4 evidence and leave its task status `in progress` for the
   requested independent acceptance.
