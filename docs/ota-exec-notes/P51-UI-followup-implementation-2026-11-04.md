# P51-UI-FONT-01 / P51-UI-WORK-01 Implementation Handoff

本地未提交实现；未制包、未操作设备。

Implementation self-tests only. Root owns independent review, source integration,
candidate binding and P5. No formal acceptance verdict or historical amendment.

## Scope And Identity

Writable root: `D:/github/my/E-Track/.cache/p35-integration-20261028/source`.
Read-only entry checks confirmed that root, HEAD
`792a8a372d21ff4abd056deae28ef9b8e64bec6a`, and the pre-existing dirty worktree.
The governance files remain identical to the previously read revision. Reviewed
the original handoff and root's Independent Local Review/follow-up findings.
No `.trellis/` exists; no new task or build framework was introduced.

This batch changes only `USER/App/Pages/FirmwareUpdate/FirmwareUpdate.cpp`,
`tests/ui/test_file_browser.cpp`, `tests/ui/test_file_browser.py`, and this new
handoff. All existing list/helper/RouteSelect/header changes and unrelated work
are retained. No staging, commits, branch changes, CI, cleanup or device action.

SHA-256 of changed files, before this batch -> final:

| File | Before | Final |
| --- | --- | --- |
| FirmwareUpdate.cpp | `0d688e1188e188dd4f30a1165c5ee2f7cdd59cf71a05e0ba775b8f542f4bf549` | `e646c2724e7bae1b6bab5010b4353b6be230515844530c850b21219e624d243c` |
| test_file_browser.cpp | `f9dc75e0d0f62511788f8262583513640c29f1192f236a284e66c3ad91d3f8a6` | `c00b0148b0786f77bec5d40c7c1393010af9aebd4c147b0f41f9df67eb6e7de7` |
| test_file_browser.py | `80e42f6eec4dddd555545599369021531b85a0aeb6c1eb492009320acb0c9542` | `7c7a2450a2ed5bc79f22669c359d725a70bdd8fb23f6b5d2e44ab6dc97a7d6dc` |

Before test identities are the reviewed previous delivery. The new baseline
already includes the test adapter expansion, but precedes product edits.
Complete baseline/final source, configuration, library and font identities are
in `.cache/p51-ui-followup-20261104-01/{baseline,fixed-04}/inputs.json`.

## FONT-01

`bahnschrift_24` has no U+0076; the existing 17/13 variants do. Reviewed
`Tools/font_gen/README.md`, its configuration and glyph maps before choosing
reuse over generation. A page-local copy of the 24-font descriptor uses the
existing 17 font as its native fallback, preserving ordinary numeric styling.
The two labels use a fixed 124-pixel right-aligned column, one font-line height,
and measured 24/17/13 family selection to fit long values without wrapping,
ellipsis or overlap with captions. No shared font descriptor/default or font
source was modified or regenerated; other consumers keep their original fonts.

Important test-fidelity correction: the actual product `Session::FormatVersion`
returns `3.3.13`, whereas the original service double returned `v3.3.13`.
Therefore the historical 118 warnings describe actual LVGL rendering of the
double's prefixed input, not proof of the product formatter's spelling or a
board observation. Original evidence and records remain unchanged. This batch
explicitly adds the requested `v` in ShowConfirm's display buffers and retains
the actual formatted value unchanged. The runner now extracts and links the
verbatim product formatting function instead of replacing it with a different
formatter; it retains the generated `format_version.cpp` for review. All other
OTA services remain bounded doubles, with Step/Apply/Stage aborting if called.

Version tests render both labels and check actual glyph resolution, full text,
single-line bounds, caption/panel separation, and width. Representative uint32
formatter inputs: 0, 30313, 30316, 9999999, 4294959999 and UINT32_MAX.
`v429495.99.99` / `v429496.72.95` fit using the existing 17 font; normal versions
retain the 24-font numeric glyphs. This tests the formatter's domain, not OTA
admissibility of every version code. Final U+0076/runtime warning count is zero.

Unchanged font source SHA-256 (same before/final):

| Font | SHA-256 |
| --- | --- |
| `USER/App/Resource/Font/font_bahnschrift_24.c` | `369748345235a21b46ad679e6fd4e7152d2be7d2128eaecd53f6040c335c3637` |
| `USER/App/Resource/Font/font_bahnschrift_17.c` | `4009bc8d26a5dbb816a17ad2a36f4af835f5ada8092d82cfdab10e10453759df` |
| `USER/App/Resource/Font/font_bahnschrift_13.c` | `41674c7b8da35bbaa1860395b725dafd4946c3d1b01a853fc0502d0b0a0145bf` |

All 12 existing font C-file hashes were also checked against the new baseline.
`OtaUpdate.cpp` is unchanged: `05824e8ff51e5de5abd0aae62996f60d1242690d28c4af92868934ddd5543045`.

## WORK-01

Reproduced the root's exact 63-byte name before product edits:
`aaaaaaaaaaaaaaa-aaaaaaaaaaaaaaa-aaaaaaaaaaaaaaa-aaaaaaafull.etu`.
Actual page/LVGL bounds matched the original probe: name y=106..162, bar
y=148..163. This is host evidence; the root's 47-byte display control remains
its original host control, not execution of an old firmware.

The work name is now 186 x 19 pixels at the existing position, with native
horizontal playback irrespective of group focus. Long names reach the complete
suffix, short names do not animate, and y-offset stays zero. Reset through
CLIP/text/SCROLL removes old native offsets before each new file. ClearGroup
stops owned work-label animations on disappearance/release, and reappearance
resumes them in working/result modes. No independent timer was added.

The expanded result-state oracle found an existing PATCH success-caption/type
boundary collision (first fixed run, retained failure at `status.x2 < kind.x1`).
Within WORK-01's required visible-field scope, the status label now also has a
fixed 136 x 19 pixel native-scrolling viewport. It retains the exact status text,
while remaining separate from FULL/PATCH. A new Start restores its original cyan
color instead of inheriting the previous result color. Percent/bar/detail/button
positions, panel size, progress source and result decisions are unchanged.

Seven working inputs cover both canonical ETU names, `a.etu`, the two 63-byte
shared-prefix/different-suffix names, supported 57-byte CJK/mixed text, and the
root probe name. Tests check geometry while animating, suffix reach, static short
text, full stored names, Begin paths, working/success/failure fields, consecutive
files, disappearance/reappearance, release, rebuild and zero final animations.
Success/failure are direct UI projections, not actual upgrade results. Two-digit
95 failure progress is explicitly injected in the test; zero/100 are also
checked. Every work timer is removed before advancing LVGL. No Step/Apply/Stage,
real package/filesystem or device service executes. Begin is a path-recording
double; all nine synthetic Begin calls receive the original complete paths.

## Commands And Results

Explicit cwd for every command: the writable root above; shell: `cmd.exe`.
Existing real-LVGL runner/library reused; no new framework or firmware build.

```cmd
python -X utf8 -B tests\ui\test_file_browser.py --phase PHASE --reuse-lvgl .cache/p51-ui-impl-20261104-01/old/lvgl --output .cache/p51-ui-followup-20261104-01/RUN
```

| PHASE | RUN | Exit | Observed result |
| --- | --- | --- | --- |
| followup-baseline | baseline | 0 | 13 assertions; exact old work overlap, product formatter spelling, explicit prefixed-font control; 3 compile / 3 runtime warnings, 0 errors |
| fixed | fixed | 1 | Retained PATCH result status/type assertion failure; 3 compile warnings, 0 runtime warnings/errors |
| fixed | fixed-02 | 0 | 28,819 assertions; 3 compile warnings, 0 runtime warnings/errors |
| fixed | fixed-03 | 1 | Test-adapter compile failure: this LVGL has no `lv_color_eq`; 1 compiler error, 3 compile warnings; layout NOT_RUN |
| fixed | fixed-04 | 0 | Final 30,543 assertions, begins=9, pops=2; 3 compile warnings, 0 runtime warnings, 0 compiler/runtime errors |

Minimal adapter repair for fixed-03 compares the supported color `.full` values;
no product workaround or log suppression. The three compile warnings remain the
existing PageFactory unused parameter, with the previous warning-visible flags.
Every run preserves exact argv/cwd/exit codes in `commands.json`, original logs,
bindings and available PNG/BMP/summary files. Old warnings and all failures remain.
The final runner also fails on runtime errors or a missing-U+0076 warning.

The complete prior list/confirmation/RouteSelect regression still executes:
focus-only scrolling, DOT restoration, native encoder scroll/edit/exit, cancel
without Begin, original paths, navigation and lifecycle assertions all pass.
Seven non-version list/RouteSelect PNGs equal root's previous regression images
byte-for-byte. Version/working regions intentionally differ and were inspected.

## Evidence, Limits And Audit

Evidence base: `.cache/p51-ui-followup-20261104-01/` (new, did not exist at entry).
Reviewed baseline prefix-control/work/result images and final screenshots:
`fixed-04/version-normal.png`, `version-max.png`, `work-probe-start.png`,
`work-probe-suffix.png`, `work-patch-suffix.png`, `work-cjk-suffix.png`,
`work-short.png`, `result-patch-success.png`, `result-probe-failure.png`, plus
the retained list/confirmation regression frames in that directory.

Final host executable: `fixed-04/test_file_browser.exe`, SHA-256
`a315ae556970a5852afb93e21642c92dab4def22d20606e174ff34dca4430304`.
Reused LVGL library SHA-256:
`b0eb2897cc3e3c1425bc9f726f8e56f0ab790dc592fb885bbd1fb29ba782766b`.
This host executable is not an MCU candidate or installed firmware.

NOT_RUN: production GCC/Boot/AC5, standalone Win32 simulator, CI, real package
or MCU filesystem, candidate generation/binding, phone/SD/device/OTA operations,
formal acceptance. Tested CJK uses existing supported subset glyphs; arbitrary
CJK font coverage is not claimed. No package, version gate, path selection,
Begin/Step/Apply/Stage semantics or execution sequence was changed.

Output preflight checked absolute resolved paths and complete reparse-parent
chains before writes. All controlled outputs stay in the new evidence base:
compiler objects/executables, generated formatter adapter, TEMP/TMP/TMPDIR,
logs, bindings, summaries and BMP/PNG. The existing runner rejects an existing
run directory. Python used `-B`; no PowerShell, package install, font generation,
external cache, download, move/delete or global configuration write occurred.
Final source/font audit and resolved output-tree audit checked 211 paths, including
ignored outputs, successfully; the new handoff boundary was checked separately.
No project-external output was found. `git diff --check` passes with one Git
LF/CRLF advisory, separate from compiler warnings. Existing packages, frozen
bundles, original captures/review probes and root's main task note remain untouched.

Root: perform one concentrated review of the localized font/display changes,
test-fidelity correction and the new original results. Then own integration and
new candidate build/bindings before restoring the affected P5 path. No third
freezing agent or unrelated P1/P3/P4/P2-5 replay is needed for this local batch.
