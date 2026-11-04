# P51-UI-01 Local Implementation Handoff

Owner: implementation agent. Next owner: root for independent review, candidate
binding and P5. This is LOCAL UNCOMMITTED implementation/self-test evidence,
not independent acceptance, a P2-5 rerun, P5 closure or a firmware identity claim.

## Boundary And Source Identity

The only writable root was
`D:/github/my/E-Track/.cache/p35-integration-20261028/source`.
Read-only entry Git checks confirmed that root and HEAD
`792a8a372d21ff4abd056deae28ef9b8e64bec6a`. The three modified product files
were initially clean. All pre-existing unrelated dirty/untracked files were
left alone; no branch switch, staging, commit, push, CI or cleanup was performed.
The requested contracts and P51-UI-01 task note were read. This worktree has no
`.trellis/`; no task/governance infrastructure was created or changed.

Exact worktree-byte SHA-256 values (not Git blob IDs):

| File | Before | Final |
| --- | --- | --- |
| `USER/App/Pages/FirmwareUpdate/FirmwareUpdate.cpp` | `5d24b520223286671ecfe39f654e1fbc9d02225dd93f49504eaa83b2ecb86003` | `0d688e1188e188dd4f30a1165c5ee2f7cdd59cf71a05e0ba775b8f542f4bf549` |
| `USER/App/Pages/FirmwareUpdate/FirmwareUpdate.h` | `72441129fd46c9ee7c582a2c3c7180312521a7643b6b99f10f7d63db6b3e698e` | `60ce56f7cfdb0119156805a5162e9aef4c422448c2635c4866b29c47120093f6` |
| `USER/App/Pages/RouteSelect/RouteSelect.cpp` | `3632c5b16b221e3c071ba35ba59a1f900dfc9ad08f27ae65d0453e65190ee547` | `9861c72016df277dbe598325735fe403fdc30239a66a1dff871368a406107ce6` |
| New `USER/App/Utils/lv_ext/lv_file_browser_label.h` | absent | `baf6dae92e02d2fcbbb2a145e9501a37a7741a18b9c23f252e297dea873cf4c3` |

Before bindings are in `.cache/p51-ui-impl-20261104-01/old-02/inputs.json`;
final source, test, font, configuration and library bindings are in
`.cache/p51-ui-impl-20261104-01/fixed-04/inputs.json`.

## Root Cause And Repair

Actual old-page execution with bundled LVGL and project fonts reproduced the
defect before product edits: FULL label height 38, PATCH 57, font line height 19,
parent row height 38. Reviewed `old-list.png` shows wrapped/crowded rows;
`old-confirm-patch.png` shows the PATCH name overlapping the current version.
DOT's content-sized height, rather than filesystem damage, caused the row issue.

The small header-only `FileBrowserLabel` helper fixes both AddRow call sites:
explicit font-line height and existing width/alignment, DOT when unfocused,
native `LV_LABEL_LONG_SCROLL` horizontal playback on focus. Native long-mode
switching restores DOT's modified display buffer and removes offset animations.
Three-cycle tests compare the complete restored text byte-for-byte, including
63-byte names. Short names produce no offset animation. The helper stores no
page/row references and creates no timer; page ClearGroup explicitly stops all
owned row-label scrolling, including page disappearance.

FirmwareUpdate confirmation now contains a 194 x 56 pixel filename viewport
(at a 240 x 320 display), full WRAP content, vertical-only native scrolling and
a cyan native scrollbar. Type, current/target versions and the two original
buttons have fixed separate bounds. Cancel remains the initial focus; an
overflowing filename area is an additional focus target. With the encoder,
focus the filename area, short-press to edit/scroll, rotate to read it, and
long-press to leave edit mode. Existing LVGL input behavior implements this.
Re-showing a file resets its scroll position; reappearing while scrolled still
includes the area in the group, checking both top and bottom overflow.

FirmwareUpdate's display-name buffers now use the existing
`LV_FS_MAX_FN_LENGTH=64`, not the unrelated 48-byte navigation display-name cap.
This is necessary to show supported 48-63 byte names completely. Its full path,
row identity, Inspect/Begin calls and OTA logic are unchanged. RouteSelect gets
only the same row display/focus fix: its navigation name cap, command payload,
GPX filter and selection path remain unchanged. No other page refactor occurred.

## Executed Local Checks

All commands used `cmd.exe` and explicit cwd equal to the writable root.
The test reuses the bundled LVGL CMake library entry, not a new build system.
It compiles the actual two page implementations and PageBase as C++11 with
GCC/G++ 15.2.0 and actual project fonts. Only the host clock and service boundary
are substituted: an in-memory directory driver, recorded OTA Inspect/Begin and
navigation/router doubles. There is no package read/write or hardware action.
Rendered 240 x 320 screenshots come from the actual LVGL software framebuffer.

First command (before product edits):

```cmd
python -X utf8 -B tests\ui\test_file_browser.py --phase old --output .cache/p51-ui-impl-20261104-01/old
```

It failed exit 1 with 9 compiler errors in the test adapter: a mismatched stub
signature, font constness and existing unused parameters promoted to errors.
The raw `old/page-build.log`, successful LVGL configure/build logs and exact
subprocess argv/cwd/exit codes in `old/commands.json` were retained. Minimal
adapter repairs did not edit product/runtime/library code. Unused parameters
remain visible warnings via `-Wno-error=unused-parameter`, not suppressed output.

Subsequent exact command template:

```cmd
python -X utf8 -B tests\ui\test_file_browser.py --phase PHASE --reuse-lvgl .cache/p51-ui-impl-20261104-01/old/lvgl --output .cache/p51-ui-impl-20261104-01/RUN
```

| PHASE | RUN | Exit | Result |
| --- | --- | --- | --- |
| old | old-02 | 0 | old defect reproduced, 10 assertions; 3 build warnings, 0 errors |
| fixed | fixed | 0 | first repair regression, 12,377 assertions |
| fixed | fixed-02 | 0 | native encoder and lifetime additions, 13,945 assertions |
| fixed | fixed-03 | 0 | identity/navigation and other-row checks, 14,820 assertions |
| fixed | fixed-04 | 0 | final scrollbar/screenshot naming regression, 14,820 assertions |

All four fixed runs have 3 build warnings and 0 errors. Final fixed-04 also
records 118 LVGL runtime warning lines, all missing U+0076 in the unchanged
`bahnschrift_24` font. The old run already emitted that same missing glyph
(4 runtime warnings). This pre-existing version-prefix rendering issue is
OUT_OF_SCOPE for this filename repair, disclosed to root rather than silently
changing fonts. Version digits and FULL/PATCH remain legible in the screenshots;
the complete version strings also match the expected values in tests.

The final checks cover both canonical filenames, `a.etu`, two 63-byte ASCII
names with a shared 55-byte prefix and different suffixes, a 57-byte CJK/mixed
name, short/60-byte directory names and the parent entry. In both pages, every
label stays 19 pixels inside its 38-pixel row and clear of the icon. Only the
focused overflowing name animates, reaches the full suffix, and keeps y offset
zero. Each focus change checks every other row remains DOT without label
animations. Defocus, page disappear/reappear, list rebuild and final destruction
leave no stale label animations (zero total animations after root destruction).

Confirm checks cover complete name/path equality, FULL/PATCH, v3.3.13/v3.3.16,
fixed non-overlapping regions, native encoder scroll-to-bottom/edit exit,
reappearance while scrolled, and scroll reset for the next file. All six cancel
cases leave Begin count unchanged. One synthetic Start invokes the service
double exactly once with `/P51/e-track-at32f435-v3.3.13-to-v3.3.16-patch.etu`;
its work timer is immediately released, so no import work is executed.
Directory/up actions, page Back and a GPX selection preserve their original
paths; both router Back callbacks are observed.

`git diff --check -- USER/App/Pages/FirmwareUpdate/FirmwareUpdate.cpp USER/App/Pages/FirmwareUpdate/FirmwareUpdate.h USER/App/Pages/RouteSelect/RouteSelect.cpp`
returned 0, with only three Git LF-to-CRLF advisory warnings.

## Evidence And Limits

All paths below are relative to this worktree. Preserve the old/failed runs.

- Old screenshots: `.cache/p51-ui-impl-20261104-01/old-02/old-list.png` and `old-confirm-patch.png` in the same directory.
- Final screenshots: `.cache/p51-ui-impl-20261104-01/fixed-04/fixed-list-unfocused.png`, `fixed-list-patch-focused-start.png`, `fixed-list-patch-focused-suffix.png`, `fixed-confirm-full.png`, `fixed-confirm-patch-top.png`, `fixed-confirm-patch.png`, `fixed-confirm-cjk-bottom.png`, and `fixed-route-list.png` in that directory.
- Each run preserves `commands.json`, `inputs.json`, raw compile/layout logs and (when execution completed) `summary.json`. The final layout log includes per-case dimensions, offsets, paths and cancel counts.
- Final host executable: `.cache/p51-ui-impl-20261104-01/fixed-04/test_file_browser.exe`; SHA-256 `d7c43a522eea7948386c893f75b4629cca004d67559d57fdbf98b59dff554452`.
- Reused real LVGL library: `.cache/p51-ui-impl-20261104-01/old/lvgl/lib/liblvgl.a`; SHA-256 `b0eb2897cc3e3c1425bc9f726f8e56f0ab790dc592fb885bbd1fb29ba782766b`; unchanged bundled Git tree `dcff470c61aa9ab601a13cec1631105031c3c7da`.

Reviewed old and final framebuffer images; this is actual headless visual/layout
verification, not a board observation. Standalone Win32 simulator, production
App/Boot/AC5 builds, CI, real filesystem/package reads, candidate generation,
board installation, OTA and formal acceptance are NOT_RUN. The CJK subset only
proves rendering for the tested supported glyphs, not all Unicode characters.
The unchanged RouteSelect `routeName[48]` cap still limits navigation display
metadata for longer names; its full `gpxPath` is separate. This pre-existing
out-of-scope contract was not expanded or used to restore row text.

## Output Audit And Next Owner

Before writes, absolute paths and complete parent chains were checked for
worktree containment and reparse points. The new evidence base did not exist.
Every test output is in that base: CMake tree, compiler objects/executables,
TEMP/TMP/TMPDIR, logs, BMP/PNG and JSON. The runner rejects existing run output
directories and unsafe paths. Python used `-B`; no PowerShell or installed-tool
directory writes, moves/deletes, downloads or global configuration changes were
requested. Final resolved-path audit checked 528 paths/ancestors successfully,
including ignored build/test outputs rather than relying only on Git status.
The only other writes are the four product files, three new `tests/ui` files and
this new handoff. No controllable project-external output was found.

Saved 30316 packages, source firmware/SD files, captures, failed records and
frozen acceptance directories were not touched. The board remains outside this
session's operations; none of this code is described as installed 30313/30316.

Root: review the four product files and the real-LVGL oracle, classify the
disclosed pre-existing font/navigation-display issues, then own any commit,
new candidate identity/assets and minimum affected P5 checks. Do not mutate old
assets or replay unaffected P1/P3/P4/P2-5 observations for this local UI repair.
