# Independent D2 Notification Adjudication

Reviewer: `/root/fastpath_review`, 2026-10-26. This is a review of existing
original observations, not another device execution or a new screenshot.
Formal criterion disposition is produced only after the v5 frozen precheck.

## Visible Observation

`inputs/notification/returned-page.png`, SHA-256
`fea746c428ed7e2fff0366a7231db11017e7aae0adf46e42988040f3d194eaa6`,
shows the returned firmware page with confirmed version 3.2.87, target
3.2.88-p38, 1.00 MB package and disabled check-update control. The lower
transfer progress is outside the screenshot. It does NOT show a numeric
transfer percentage, completion, final firmware 30289, or the fast-run UI.

The original v4 D2 `sample-0022/activities.txt` has MainActivity in current
focus. `intent-observation.txt` contains both stale generation 6 and current
generation 9 intents. Current sample 0022 contentIntent points specifically
to PendingIntentRecord `67adf79`, not stale `9cf637d`, with OPEN action and URI:

    trace-device-ota://task/df1d61f83389d977d7bb3f7f2451c86c_9_2/9/open

All five selected native records retain that current handle. The notification
record reports a click (posttimeToFirstClickMs=263481). Same PID 22309, same
capture `1792874413236283-485d08a1f060cb05ac4720ec`, one upgrade start and no
duplicate BEGIN support return to the existing owner, not starting an OTA.

## Numeric Truth

Native sample 0015/0018/0019/0020/0022 reports 21/26/28/30/34 percent,
progressMax=100, indeterminate=false, and the explicit label
`Transferring (MCU durable confirmation)`. This is not inferred from pixels.
Each corresponding original recorder health file binds capture, record count,
byte count, healthy/lost/error state and one start/no end. At those cutoffs,
the last observed MCU durable bytes are 225280/282624/307200/327680/368640.
Native percentages match observed durable checkpoints at or before their own
cutoff. Samples 0019/0020/0022 lag by exactly one 4096-byte confirmed block;
the native dump precedes the recorder health read. The offline oracle permits
at most this one-block sampling lag and rejects later/sent-byte substitution.
All offsets are within the same 1048576-byte package.

## Source Applicability

Compared historical v4 freeze `60cb25c459bcde95f2be42edc28ef3fdb2448111`
with current product baseline `410b7d57c7ed918103986f42a30af80960506826`.
The complete Android tree and `lib/ota/ota_background.dart` are byte-identical.
DeviceOtaService.kt lines 139-166 derives transfer percentage by integer
`100 * durable / total`, checks the requested task key, and binds an immutable
single-top/clear-top OPEN PendingIntent to taskId/generation.
OtaTaskSnapshot lines 27-70 is the shared owner-produced UI/native projection.

Reviewed the nonempty `ota_upgrade_page.dart` and `ota_service.dart` diff,
rather than claiming whole-file identity: new link-epoch/identity reconciliation,
restored verified-package recovery, safe snackbar and automatic-reconnect
serialization do not replace the active-owner reattachment branch or the
snapshot percentage/Intent semantics. New idle/terminal paths are supported
by current source-bound full hosted regressions, not this historical screenshot.
The evaluator also binds the final frozen lib/android/pubspec inputs to baseline
and the successful fixed-signer workflow source. No new visual fast-run or
production-fast-configuration acceptance is inferred.

## D1 Pause Limitation

Historical D1 first MONO_PAUSE is followed by one segment completion observation
at offset 8320, length 128. Source `60cb25c4` records segment send-end only
after `await _sendSegment`; this is not a GATT write-start marker. LINK_SAMPLE
and MONO have different stopwatch origins and cannot be subtracted.
All initial tail records remain in the immutable snapshot. Later repeated
MONO_PAUSE markers through MONO_RESUME have no further DATA completions.
Thus the evidence supports no sustained sending, NOT zero measured starts at
the first lifecycle instant. The evaluator rejects two completions, an absent
later quiet pause, reversed or missing markers. Current standard host tests
cover partial-frame pause drain, no new reserved frame, pause cancellation,
late batch poisoning, and background denial/owner-loss strict foreground
identity recheck; these distinguish bounded in-flight completion from starting
new work after budget/cancellation. They are software evidence, not new D1
physical timing observations.
