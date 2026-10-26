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

## Executed Development Result

Both review findings above were independently closed at host commit
`677d3e39e750ff4d910f390273a632f9955e6dcf`. Its checks-only CI run
40239121973 completed successfully on Windows and Ubuntu. Original APK run
40237667185 at `3daf949f19c697b41b884b5246024bdad750f27b` also passed both hosts:
Ubuntu 772 passed / 16 skipped; Windows 753 passed / 35 skipped; no failed Dart
tests. The original native JUnit report has 18 passed, zero skipped/failures/errors.
Local helper and runner regressions passed 45 and 65 tests respectively.

The original pipeline APK was ZIP-digest/CRC, metadata, package-ID, sentinel and
signer verified, installed without clearing data, then verified on the phone:
`fe27b7587300f74f2e58996ae47cbf302f927e6a8a7c69b9749d28146c3157b1`.
One inactive query-only capture was preserved locally and moved intact to the
diagnostic App's archive directory; no capture files were deleted.

The bounded adapter `.cache/recovery-fast/session.py` reuses existing Phone,
Network, Android samples and passive MCU readers. Independent FAST-SESSION-01
found that cleanup errors could leave the supervisor reporting success. It was
fixed before launch and independently closed: all cleanups execute, original
facts/errors are saved, and an error or still-open ADB port causes nonzero exit.
Three offline failure/clean-path cases passed in `cleanup-selftest-001`.

### Actual Cell And Identity

Evidence root: `.cache/recovery-fast/session-001/`; the sole cell was a legal
30288 -> 30289 reference transfer, started by the user after phone download bytes
were verified. It completed; do not replay it to recreate evidence.

| Observation | Actual result |
| --- | --- |
| Package | 1048576 bytes; SHA-256 `861b645c1b10518c99b6c13012199eeb4ca2b87762ef601b485cdd1daa2c42c7` |
| Start state | durable=0, bitmap=0; full 8192 DATA segments |
| Link | schema 10; protocol v2; window 24; batch 12; GATT reuse; without-response writes; MTU payload 244 |
| BEGIN through END ACK | 63.071407 seconds; 16.235566 KiB/s |
| Earlier accepted candidate reference | 63.708034 seconds for full 1 MiB; current result restores that level, not a new stability claim |
| Prior slow resumed transfer | 632 KiB in 514.833441 seconds; normalized current transfer throughput is 13.23 times higher, not a same-size duration ratio |
| Upgrade discovery / retransmission | 1 discovery / 0 retransmitted DATA frames |
| ACK quality | 8192 latency samples; no missing/early samples; P99 612809 us; no matching or ignored ACK errors |
| After END | Normal apply/reconnect; fourth reconnect probe verifies target; public END-to-verified interval 33.913107 seconds, not a standalone Flash timing |
| Retained App | 3.2.89-p38 / 30289, full 613952-byte SHA-256 `245189f7b2f02d968068b3ade77000a0b82a8de20b140bd41e2530675713bad0` |
| Boot | Unchanged 65536-byte SHA-256 `01e4b9e162bfaaf9fda070aa13c0cec3f377b8d696db01f731e0ab3d1464e527` |
| Final health | Confirmed, SD ready, OTA idle, fault-free, same-boot clock advancing; target staging committed and fully durable |

`usb/snapshot.jsonl` is the original sealed App snapshot, SHA-256
`1bebea26fe7e8ca64f5a6d294f1781feba0fb93cf719c14966bb46e55d7c614f`.
The existing strict parser passed, and all OTA_EXPERIMENT stamps extracted from
these same bytes matched canonical `usb/runtime.json` SHA-256
`70bad87ce59666905c7ca3049b62bf635c28caa086ae12f472bf2075f48480e5`.
`check_observation` confirmed the negotiated fast profile and exact image/package
identities. Full passive device readback bytes/state are in `final-state/`.

### Background And Closure

User notifications were sent through the current-session bridge and each send
receipt was successful. The user, not the adapter, performed navigation, start
and lock. Samples 0014 through 0018 record Asleep/lockscreen plus the active OTA
wake lock, with observed durable advancing from 565248 to 1048576 bytes in the
same PID/capture and one BEGIN. Notification 2408 and the foreground service were
recorded; this does not claim a visual/OEM notification-display acceptance.

Final sample 9999 has no DeviceOtaService, no active trace:DeviceOta wake lock
and no remaining scoped notification. USB/network cleanup receipts have no
errors; `session-worker/exit.json` records completed=true. Post-close checks found
private ADB 5078, HTTP 60372 and tunnel metrics 60383 closed, and the supervisor
PID absent. All 578 command receipts in this continuation's output trees used the
active worktree as cwd. Controllable host artifacts remained in that worktree;
J-Link's native SEGGER history updates are covered by standing authorization.
No local Flutter/Gradle build, mainline merge, release, Boot replacement, MCU
downgrade, data clear or automatic UI tap was performed.

This closes the one-cell development speed/background observation, not the
whole-card P3-8 formal acceptance or a multi-run stability campaign. The earlier
query-only timeout remains in the originals; it is not a DATA-transfer failure.

Independent reviewer `fastpath_review` subsequently re-parsed the same original
snapshot, checked both runtime stamps, matched each locked sample to a genuine
snapshot prefix, verified original App/Boot bytes and header integrity, decoded
the raw health fields, and checked terminal/host closure receipts. Disposition:
the bounded development result above is supported, with no new blocker. This was
offline read-only evaluation of this cell, not a newly executed hardware run or
whole-card formal acceptance. No replay is required. The final execution note is
worktree-local pending integration; the code fixes remain on the development
branch at the commits named above.
