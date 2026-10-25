# Recovery And Accepted Fast-Path Integration

## Scope

User request: restore the accepted link configuration in the current recovery
APK, prevent silent fallback, run software checks and a bounded joint device
validation. Worktree: `.cache/flutter-recovery-20261025`, branch
`dev/flutter/ota-recovery-20261025`. Product source remains the recovery batch
`b5111325`; this change does not alter Dart behavior, MCU code, release defaults
or frozen acceptance evidence. No mainline merge/release is authorized.

## RECOVERY-FAST-01

The prior installed APK was built as `runtime`, not `runtime-pipeline`.
The preparation adapter emitted schema 1 with reuseGatt/withoutResponse false.
The successful 30287 -> 30288 transfer therefore used v1, four segments and
single-frame writes: 632 KiB in 514.833441 seconds, 5061 discoveries, no retransmits.
This was an integration/configuration regression, not evidence of slower UART.

Accepted P3-4 v15 candidate-stage evidence retains the fast configuration:
runtime-pipeline, schema 10, v2, 24 segments, 12-frame batches, GATT reuse,
without-response GATT writes with unchanged MCU ACK/durable validation.
The preserved 1 MiB reference is 63.708034 seconds. Its original PASS and limits
are not rewritten or promoted to a new performance claim.

Reuse existing `dev_apk.py`, `Phone`, reference encoder/native decoder and strict
App snapshot readers. Add only the named `p34-qualified-v1` settings contract
in `Tools/flutter/ota_link_profile.py`. Build selection must explicitly combine
`ota_link_candidate=runtime-pipeline` and `ota_link_profile=p34-qualified-v1`.
APK metadata remains build intent; actual v2/window/batch/write-mode/input
validation consumes the existing strict parser's real observation.

The profile generator rejects plain runtime/baseline APK metadata and produces
forward-only source/target-bound schema-10 settings. The checker rejects missing,
changed or unknown runtime fields and observed v1/window/batch fallback. Existing
baseline experiments remain available only when the profile is not requested.

## Validation And Device Matrix

1. Existing Python build/profile and sparse-checkout regressions, then full
   Ubuntu/Windows development CI and one explicitly requested debug APK.
   No local Flutter/Gradle build or SDK installation. Preserve failed results.
2. Reuse current verified 30288 App/unchanged Boot as the starting identity.
   Generate the legal 30288 -> 30289 1 MiB reference with the existing encoder
   and actual C decoder, with wrong CRC/length/version/base-hash negatives.
3. Verify signed side-by-side APK, existing observations/cached package, firmware
   identity and staging before replacing the known diagnostic APK without clearing
   data. Bind fresh capture, exact fast runtime and immutable package first.
4. One fast 30288 -> 30289 transfer with acquired background/lock observation,
   then normal apply/reconnect, immutable snapshot, full target and unchanged Boot
   readback, confirmation and terminal service/lock cleanup. A further disconnect
   recovery cell is only prepared if the changed profile's missing recovery
   observation requires it; it is not a replay of this completed transfer.

No 30288 downgrade, Boot replacement, protocol shortcut or repeat of the prior
slow success. If profile negotiation, identity or observations fail, preserve the
failure and stop dependent mutation; do not accept a silent slow fallback.
Development outcomes remain distinct from independent P3-8 adjudication.

## Independent Review Batch

Reviewer `fastpath_review` found two host contract gaps in `3daf949f`:
FAST-REVIEW-01 requires every original OTA_EXPERIMENT stamp to match schema 10,
the current run ID and the SHA-256 of canonical written runtime bytes.
FAST-REVIEW-02 aligns host URL validation with Dart: reject localhost/IP and
even empty query/fragment delimiters. Both have distinguishing negatives.
These are host-only follow-ups; App sources, APK build defines and `dev_apk.py`
remain byte-identical to the successful APK run 40237667185 at `3daf949f`.
The APK is reused with its exact original commit/hash, not relabeled as rebuilt.
The follow-up runs checks-only CI and needs reviewer closure, not another OTA.
