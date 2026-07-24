# PRE-3 firmware-build.yml align to §6.1

Date: 2026-07-24
Implementer: Codex

## Sources

- PLAN-OTA-EXEC PRE-3 card
- PLAN-OTA.md §6.1 (nightly = artifact only 14d; no Release/CF register)
- Re-review A/B (push register + version_code UNIQUE; isFormalRelease)
- `.github/workflows/firmware-build.yml` pre-change

## Pre-change issues

- `register-cloudflare` job `if` allowed `github.event_name == 'push'` OR dispatch publish=true
- Artifact `retention-days: 30` vs scheme 14 days
- Create GitHub Release step created nightly prerelease tags on push path
- Cloudflare secrets soft-skip path treated push register as optional

## Changes made (scope = workflow only)

1. Header comments: push = build + artifact only (14d, no Release, no CF)
2. `retention-days: 30` -> `14`
3. `register-cloudflare.if` only:
   `github.event_name == 'workflow_dispatch' && github.event.inputs.publish == 'true'`
4. Secrets missing always hard-fails (job only formal publish)
5. Release tag simplified to formal `mcu-${DEVICE_MODEL}-v${VERSION_NAME}` (no nightly tag/prerelease branch)
6. Left `isFormalRelease` script alone (card: after push-register removal, hardcode true is correct for formal-only path)

## Validation

- PyYAML `yaml.safe_load` OK
- register if exact string without `push`
- `retention-days: 14` present; `30` absent
- `ACCEPTANCE_OK`
