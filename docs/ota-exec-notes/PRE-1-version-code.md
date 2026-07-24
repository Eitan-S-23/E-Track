# PRE-1 version_code research

Date: 2026-07-24
Implementer: Codex

## Sources checked

- `PLAN-OTA-EXEC.md` PRE-1 task card and acceptance criteria.
- `.claude/verification-report-ota-plan.md` supplement D.
- `PLAN-OTA.md` header, sections 3.1, 4, and 6.1.
- `.github/workflows/firmware-build.yml` version extraction step.
- `USER/App/Version.h` current `VERSION_SOFTWARE` value (`v2.7`).

## Findings

- Pre-change workflow computed `major * 1000 + minor`, so patch releases collided: both 2.8.0 and 2.8.1 mapped to 2008.
- Pre-change workflow displayed a manual `workflow_dispatch` version name but computed the code from `Version.h`; a manual release could publish a mismatched name/code pair.
- The repository's current two-component version `v2.7` must remain accepted and is equivalent to 2.7.0 for encoding.
- The old normative formula remains only in the workflow. `PLAN-OTA-DRAFT.md`, the verification report, and the execution card contain historical/audit descriptions and are outside PRE-1's implementation scope.

## Implementation decision

- Freeze `version_code = major * 10000 + minor * 100 + patch` as an unsigned 32-bit value.
- Require numeric `major.minor[.patch]`; default an omitted patch to zero; require `minor` and `patch` in 0..99; reject u32 overflow.
- Compute from the effective release version (manual input when supplied, otherwise `Version.h`) so `version_name` and `version_code` cannot diverge.
- Document mappings 2.8.0 -> 20800 and 2.8.1 -> 20801, plus the migration ordering 2007 < 20700 for legacy 2.7 versus 2.7.0 under the new encoding.

## Implementation evidence (2026-07-24)

Files changed (PRE-1 scope):
- `PLAN-OTA.md` -> v1.3.1 header; §3.1 version_code formula; §6.1 encode-from-name rule
- `.github/workflows/firmware-build.yml` Extract firmware version step

Local encode checks (PowerShell mirror of workflow formula):
```
2.8.0 => 20800
2.8.1 => 20801
2.7 => 20700
v2.7 => 20700
2.7.0 => 20700
2.7-nightly.123 => 20700
2.8.1-nightly.9 => 20801
ACCEPTANCE_OK (2007 < 20700)
```

Grep residual old formula after change:
- Active/normative path: workflow no longer uses `major * 1000 + minor`.
- Remaining mentions are migration notes in `PLAN-OTA.md` (old formula retired), task wording in `PLAN-OTA-EXEC.md`, and historical draft/audit docs outside PRE-1 write scope.

Awaiting non-implementer acceptance per PLAN-OTA-EXEC §0.3.
