# Version Inventory And Operator Delta Jobs

## Scope And Plan

User approved implementation on 2026-11-11. Active root is the existing
`.cache/p35-integration-20261028/source` worktree. Preserve all earlier dirty
files, registered packages and completed observations. Work area:
`.cache/version-inventory-delta-20261111-01/`.

Implement low-frequency, optional Android version reporting and dated MCU
observations; original-Admin inventory and refresh controls; multi-base delta
requests using existing Actions packaging tools, append-only assets and explicit
enablement. No automatic channel publication, old-package replacement, production
approval, phone installation, firmware flash or four-hour test is part of this
implementation batch. No new review agent is required for development feedback.

App counts are reported installation instances, not people. Current OTA INFO
has no qualified global device identifier. MCU observations are scoped to an
installation, clearly labelled as potentially duplicated across phones; do not
invent unique-device counts or mutate the frozen INFO frame for analytics.
Cached MCU data retains its original observation time and nonce. Unknown and
unreported versions are not zero users. Reports carry no raw Bluetooth address,
location or riding data. Users can disable reporting in the existing App.

Keep normal reports daily, coalesce changes and back off failures. Server-side
per-installation limits and a transactional daily budget protect the existing
free-tier service. Existing HTTPS/Cloudflare/D1/R2 and CI tools are reused.
Actions source and inputs must be pinned; registration must verify reconstruction
and target hashes before an optional patch can become visible. APP VCDIFF and MCU
ETU remain separate formats. Original immutable registration metadata stays intact.

Validation order: existing contained Node/SQLite and browser regressions; required
dual-host Flutter development CI and APK/EXE compilation for changed App inputs;
then source-bound staging migration/deployment and bounded real UI/server checks.
Only request a phone window after scripts and artifacts are ready. Missing live
credentials or client coverage is reported as missing, not simulated success.

## Status

Implementation and staging preparation in progress. No device operation.

## Implemented Contract

- The existing Android App reports its installed APK version/hash and up to four
  cached MCU INFO observations. Normal reports are daily; a control check occurs
  at most every four hours on foreground events. Backoff is one hour. No new BLE
  scan/connection, remote wake-up, perpetual polling or OTA ownership is added.
- The profile settings dialog contains an opt-out and disclosure. The server
  stores a digest of the random installation token, not the raw token or BLE
  address. One phone's MCU keys cannot deduplicate across phones. Report sequence
  checks and observation nonces prevent stale cached data from becoming fresh.
- D1 migrations 0007/0008 are additive. Inventory has an initial daily accepted
  report limit of 1000 and a per-installation limit of eight. This deliberately
  leaves room for D1 index writes, cleanup and the original update service under
  the free plan; it is not an account-wide quota guarantee. Data is retained for
  90 days, with bounded hourly cleanup. The new minute-17 staging cron only cleans
  inventory, not historical firmware idempotency receipts.
- Original Admin App/MCU sections have peer distribution tabs and compact paged
  7/30/90-day tables. Manual refresh requests future reports, not immediate replies.
  Unreported and stale data are never silently treated as zero users.
- Each target version's delta dialog selects up to five original bases. Reported
  30-day counts are guidance only; the operator makes the selection. Existing
  patches/jobs are reused. At most 20 new attempts/day are admitted transactionally.
- GitHub Actions downloads bound original packages. APK jobs verify version,
  package name and the same signing certificate; use the existing VCDIFF encoder;
  reconstruct byte-for-byte; sign a per-base manifest using the existing key.
  MCU jobs unpack existing full ETUs, reuse the existing bsdiff/ETU tools and
  validate all image/header/package identities. No original is finalized again.
- CI claims bind job, attempt, workflow commit and run. An unknown dispatch is
  reconciled against a unique GitHub run, never blindly retried. An explicit retry
  can bind a corrected workflow while retaining the previous attempt's identity.
- A generated asset is disabled until an owner explicitly enables it. Enabling
  requires a smaller verified object and a valid original target. Mutation nonces
  bind transaction side effects to the winning CAS. Channels and sealed original
  metadata do not change. Full fallback remains available.

## Validation Observed

- App WIP `60906e304044319b1237bac6ba51811219c6dccc`, Actions `43044268397`:
  four analyzer findings; Windows unpaced parser fixture overflowed its recorder
  queue. Both original logs and development artifacts are retained.
- App correction `ce458416cb96dc9be41981aa9cd3098198b21c1f`, Actions `43049945504`:
  strict analysis passed on both hosts. Linux 771 passed/16 skipped; Windows 752
  passed/35 skipped; eight additional candidate checks passed on each host.
  SDK: Flutter 3.47.9 / Dart 3.13.7. Production recorder limits were not changed;
  the parser contract now uses a memory writer before persisting its exact output,
  so an unpaced mock link does not measure Windows fsync scheduling.
- Local `host-01`: 395 backend tests and 13 delta orchestration tests passed.
  `host-02` also includes retention, GitHub reconciliation and concurrent-CAS tests.
- New browser scenarios `ui-01`: 13 passed. `ui-all-01`: 150 passed, one 320px
  English tab overflow found. The short tab label was corrected; no assertion was
  removed. A complete successor UI run is retained separately.

Node/SQLite and browser doubles are development checks, not real Cloudflare,
Access or hardware evidence. Native Workers CI, APK/EXE build, staging deployment
and live checks are recorded separately below when actually observed.

## Configuration And Remaining Gates

Original resources remain `trace-update-admin-staging.pages.dev`,
`trace-update-public-staging.pages.dev`, `trace-update-service-staging`,
`trace-update-staging` D1 and `trace-update-staging-releases` R2.

The cloud dispatcher needs project-scoped GitHub Actions write/read credentials
(`DELTA_GITHUB_TOKEN`), the exact workflow ref/commit and the existing APK public
verification key. Never export the host's personal GitHub credential into Pages.
Supplemental distribution stays disabled until those bindings and the real job
route are qualified. Firmware Actions retain the `firmware-rehearsal` approval
gate. This task does not bypass it, publish Stable/Beta, merge unrelated branches,
install an APK or declare the old P5-1 hardware campaign complete.

The App build candidate is bumped to `1.0.75+101`; existing installations do not
gain inventory support until an explicitly installed/published new App is used.
