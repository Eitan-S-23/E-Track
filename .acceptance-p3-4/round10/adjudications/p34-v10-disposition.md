# P3-4 v10 Bounded Independent Disposition

DECIDED: EVIDENCE_GAP, not a demonstrated product failure. Q-TRANSFER cannot
PASS under the frozen v10 criterion. Its qualification is incompletely observed;
retain the actual command exit 1 and all existing originals. No source, contract,
matrix, device or prior evidence was modified by this review.

## Binding And Preserved Facts

- Contract: docs/acceptance-contracts/P3-4-v10.contract.json; SHA-256
  7ae9b1736674d6d2d934dca0ad1158187efa0abd807754d7b32a349dac5de65f.
- Original CMD-Q-TRANSFER.closed.json SHA-256:
  6c4664386bb49c21d67ca030f3d209141d7ffe047ede58fb68513da348adb99f.
  It records normal owned-process closure with exit 1, not a successful action.
- Recovered original snapshot: round10/diagnostics/no-start/phone/salvage/
  snapshot-1.jsonl; 4801006 bytes; SHA-256
  33ba9b04ee56e3dc7505e9d15de499c9819af7edd4fc9e31b509fbca0fbb2d18.
  Independent read-only observation_capture.verify and acceptance_stats.inspect
  both passed for PID 13122 and capture
  1791806205073776-2639ebf186f273ac86fb0c92.
- The App original proves one completed, zero-start 1048576-byte transfer,
  target 30287, transferUs 71582792, throughputKiBs 14.305114000023917,
  zero retransmissions and no reported observation error. Preserve the existing
  runtime/package/capture binding receipt and the newly obtained target/Boot
  originals separately from the failed action. No extra OTA is needed to retain
  or parse this evidence.
- Physical accounting is qualification 1/1 consumed, calibration 0/12. An
  observer timeout does not erase an actual successful OTA. Qualification is
  expressly excluded from calibration and final performance statistics.

## Missing Gates And Permitted Next Step

Q-TRANSFER expressly requires matching same-attempt MCU package/epoch/actual-baud
and clean terminal metrics, required clock/WDT/old-App stack-guard evidence
before reboot, full target/Boot readback, closed collectors, and the actual
action result.json. The original RTT has no P34_METRICS and no terminal
transfer_snapshot/result/observations was produced. A current target readback
cannot recreate old-App pre-reset stack/clock/metrics. This is a substantive
evidence gap, not merely a missing wrapper JSON. Do not manufacture a result or
change the exit code to make the recovered success look like a completed runner.

CMD-Q-RESTORE explicitly requires Q-TRANSFER complete and valid. Calibration
setup requires valid Q-RESTORE and all preceding cells valid and closed.
Therefore neither the v10 Q-RESTORE command nor its dependent calibration may
run under current admission. Keep their formal status unobserved.

The smallest current action is to finish only the already authorized read-only
target/Boot/state verification, preserve originals and close owned collectors;
retain target 3.2.87. Existing, genuinely retained same-attempt pre-reboot
originals could close part of the gap if found, but current target RAM or a new
OTA cannot be substituted. If none exists, leave Q-TRANSFER unresolved.

Root owns any subsequent execution-plan/admission decision and must freeze a
controlled successor before changing that plan. Existing conditional authority
for the same-device pinned recovery route is not a need for repeated per-reset
permission, but is also not permission to waive Q, fabricate its PASS or enlarge
the 1/1 quota. New device operations, increased quota or relaxed required gates
need actual scope authorization. This disposition authorizes none of them.

Basis: v10 Q-TRANSFER, Q-RESTORE, CMD-Q-RESTORE, calibration setup and
operating_rules.evidence; acceptance-execution-contract sections 2, 4, 7 and
7.1 distinguish evidence gaps, original command results and physical quotas.

## Start Communication And Timing

The actual start message in .cache/p34-v10-stage1-20261012/qualification1.py:53
says to start once now and stay foreground, but states neither the 120-second
window nor that the invitation expires. That is a bounded operational
communication gap, not evidence of user error or a proven exact cause.

The host phase spans monotonic 925496.5254044 to 925616.5254044; the sent receipt
is 925499.431532. The last original health read, adb-00324, ended at
925620.526288 with starts=ends=0. These are observations of stored checkpoints,
not an exact tap timestamp. The recovered App's MONO_BUDGET_START is on its own
clock. Do not subtract App wall/monotonic values from host monotonic values or
claim an exact out-of-window tap without a valid clock mapping. For a future
authorized cell, communicate the actual remaining window and expiry clearly;
do not rewrite this attempt's deadline or ask for another successful OTA.

Output audit: this disposition is the only additional write for this follow-up,
inside the previously authorized independent-review directory. All examination
was host-side read-only; no ADB, J-Link, OTA, reset, cleanup, commit or push ran.
