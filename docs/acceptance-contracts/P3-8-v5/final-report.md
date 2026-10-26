# P3-8 v5 Independent Acceptance: PASS

Independent reviewer/acceptor: `/root/fastpath_review`, 2026-10-26.
All seven required criteria are EXECUTED PASS through one real offline
evaluation of existing original observations. No new device, OTA, local build,
artifact download, remote operation or release was performed by this reviewer.

The frozen NOT_RUN precheck and rerun plan passed with actual previous v4 and
v3 origin inputs. The plan required one shared command; it ran once for
11.9190755 seconds, exited 0 and closed its process job/handle cleanly.
The final validation reports:

    VALIDATION=PASS contract=P3-8-v5 round=20261026-P38-v5 overall=PASS

## Frozen Identities

- Freeze commit: `2be0540feda1aec0ca001afb8456bb7bd82183ce`.
- Freeze tree: `01a9ae76c845961a7a45516cdac5d3825af7a5ce`.
- Contract SHA-256: `1122b8aad76acbc7457764b1041cf7b7b9f0335c549d8ae20d09b33c2456f1b3`.
- Final matrix SHA-256: `33c412364c235aaf72a7ec25ce1ff73f4c7bbbf62bba131d134a0bbb1d006af4`.
- Actual success/closure: `execution/result.json`, `execution/offline.closed.json`.
- Complete final-validator receipts: `validation/validate.stdout`,
  `validation/validate.closed.json`.

## Boundaries

Historical v1-v4 failures remain unchanged. Recovery proves explicit resume
from MCU durable 401408, not automatic reconnect. D2 screenshot proves page
return, not visible numeric progress; its native notification percentages are
bound separately to durable originals. Fast-run observations do not grant
production fast-path release configuration. Fixed-signing run 40249303504
binds the real fixed certificate and APK bytes/hash without downloading again.
Standard build warning lines remain Android 10, Windows 0; skipped tests remain
Android 16, Windows 35. Details and source applicability are in `review.md`.

## Recheck

Check out the eventual bundle commit with full source history and fetch the
preserved `acceptance/p3-8-device-20261024` branch before rechecking. Its exact
tip is `3f3c32efa7bd9fb9f2c068dedab0517b99f74360`; no old product code needs
merging. From this worktree root, revalidate existing evidence only:

    python -I -S -B -X utf8 Tools/acceptance/validate_bundle.py --contract docs/acceptance-contracts/P3-8-v5.contract.json --matrix docs/acceptance-contracts/P3-8-v5/evidence-matrix.json --repo-root . --previous-contract docs/acceptance-contracts/P3-8-v5/inputs/history/v4/contract.json --previous-matrix docs/acceptance-contracts/P3-8-v5/inputs/history/v4/evidence-matrix.json --reuse-source docs/acceptance-contracts/P3-8-v5/inputs/history/v3/contract.json docs/acceptance-contracts/P3-8-v5/inputs/history/v3/evidence-matrix.json

Do not rerun the offline command against the now-final matrix or overwrite
the immutable result. Root owns the separate evidence commit, later
FREEZE-INDEX registration, task closeout and any separately authorized release.
