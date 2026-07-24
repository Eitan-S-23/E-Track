# PRE-4 Actions green rework (after acceptance reject)

Date: 2026-07-24
Implementer: Codex
Card: PRE-4 (reopened after reject)

## Reject summary

Acceptance was rejected because:

1. Failed app run: https://github.com/Eitan-S-23/E-Track/actions/runs/30073428519
   - Workflow: `Build APK and EXE Release`
   - APK/EXE build jobs: success
   - `Create GitHub Release` / `Enforce fixed Android release signing`: failure
   - `FIXED_SIGNING_CONFIGURED=false` (repo has no fixed Android signing secrets)
2. MCU clean-checkout green was unproven; first dispatch then failed (below)

Closure required by reject note:

- (A) Fix `build.yml` so main push without signing secrets does not enter Create Release/CF,
  OR configure fixed signing secrets and get green
- (B) Trigger one successful `MCU Firmware Build` clean checkout and keep run URL

## (A) App workflow root cause + fix

Path-detect job env from failed run:

- `EVENT_NAME=push`
- `BEFORE_SHA=0000000000000000000000000000000000000000`
- zero `before` => script forces `app_build_required=true` (brand-new branch tip)
- release job `if` also allowed main/master push into formal Create Release/CF
- hard-failed without fixed Android signing secrets

Fix applied locally in `.github/workflows/build.yml`:

- Remove main/master push from `Create GitHub Release` job condition
- Formal path only: tag `v*` OR `workflow_dispatch(publish_release=true)`
- Formal path still hard-fails without fixed signing secrets

## (B) MCU dispatch result: YES, GCC compile error

Failed run: https://github.com/Eitan-S-23/E-Track/actions/runs/30080113197
- event: `workflow_dispatch` publish=false
- head: `ed755b8` (current origin/main)
- job `Build firmware (arm-none-eabi-gcc)` failed at step **Build firmware**

### Exact error

```text
FAILED: CMakeFiles/X_Track.dir/.../Bluetooth.cpp.obj
Libraries/Bluetooth/Bluetooth.h:5:10: fatal error: HAL\HAL.h: No such file or directory
```

### Classification

This is a **Linux GCC compile error**, not a missing-generated-file / missing-vendor problem.

- Checkout, toolchain install, CMake configure all succeeded
- Failure is preprocessor include resolution under `arm-none-eabi-g++`
- Keil AC5 / Windows often accepts `#include "HAL\HAL.h"` (backslash)
- Linux GCC does **not** treat `\` as a path separator inside include strings

### Not caused by generated CMakeLists

`MDK-ARM_F435/cmake-generated/` is produced by `keil_uvprojx2cmake.py` and must not be hand-edited.
This failure is in **hand-written source headers**, not in the generated CMake graph:

- first hit: `Libraries/Bluetooth/Bluetooth.h`
- same class also present in USB stack sources under `Libraries/USB_MSC/**` and
  `MDK-ARM_F435/Platform/middlewares/usb_drivers/**`, plus `USER/HAL/HAL_USB.cpp`

Generated-script concerns (absolute paths / PACK mapping / multilib -isystem) are a
**different** class of CI risk; they did not fire on this run (configure already passed).

### Secondary warning (not the hard fail)

```text
CMAKE_OBJECT_PATH_MAX ... object dir has 97 characters ... max full path 140
```

Deep build dir `MDK-ARM_F435/cmake-generated/build-ci` on the runner is long.
Generator intentionally uses path-shortening at 140. CI-side mitigation without
editing generated files: build in a short dir such as `/tmp/etfw`.

## Fix applied locally for MCU green

1. Source portability (hand-written sources only; not cmake-generated):
   - rewrite `#include "...\..."` -> `#include ".../..."` in the affected USB/BT/HAL files
2. Workflow only (not generated):
   - `firmware-build.yml`: `BUILD_DIR=/tmp/etfw`, `-DCMAKE_OBJECT_PATH_MAX=1024`
3. App formal-release gate (see A)

## Still open before PRE-4 can be completed

- User-confirmed commit + push of the local fixes
- Re-run / auto-trigger:
  - `MCU Firmware Build` green run URL
  - `Build APK and EXE Release` no longer red on ordinary main push
- Independent acceptance session per board §0.3

## Commands / evidence

```text
gh run view 30080113197
# fatal error: HAL\HAL.h: No such file or directory

rg '#include .*\\' Libraries USER/HAL MDK-ARM_F435/Platform
# after local rewrite: no remaining backslash includes in those trees
```

## Post-push verification (2026-07-24)

Commit: `f914854` on `main`

- MCU Firmware Build: SUCCESS
  https://github.com/Eitan-S-23/E-Track/actions/runs/30083347995
  - Build firmware / Generate bin-hex / Upload artifact: success
  - Register firmware to Cloudflare: skipped (push path, expected)
- Build APK and EXE Release: SUCCESS
  https://github.com/Eitan-S-23/E-Track/actions/runs/30083348008
  - Create GitHub Release: skipped
  - No signing-secret hard-fail on ordinary main push

Closure A+B implementer-side satisfied; PRE-4 remains awaiting independent acceptance.

## Project memory

Durable agent-facing write-up (do not rely on this note alone):

- `AGENTS.md` section **GCC / Linux CI 源码可移植防坑（PRE-4 实测,2026-07-24）**

