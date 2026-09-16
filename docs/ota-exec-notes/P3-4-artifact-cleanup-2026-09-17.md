# P3-4: Authorized Actions Artifact Cleanup (2026-09-17)

Owner: root coordination session, not the implementation or acceptance agent.
The user explicitly requested cleanup after discussion of obsolete development
APKs. This operation is repository maintenance, not product acceptance.

## Result

Repository: `Eitan-S-23/E-Track` (ID `1310649784`, still private).
Authenticated account: `Eitan-S-23`.

| Measure | Before | After |
| --- | ---: | ---: |
| All artifacts | 345 | 305 |
| All artifact bytes | 4,548,046,614 | 1,538,665,642 |
| Development debug APK artifacts | 52 | 12 |
| Development debug APK bytes | 3,912,027,453 | 902,646,481 |

Deleted 40 obsolete development APK artifacts, releasing 3,009,380,972 bytes
(2.8027 GiB). Listed storage decreased from 4.2357 GiB to 1.4330 GiB.
All 40 IDs have distinct HTTP 204 receipts and are absent from the final inventory.
The other 305 artifacts retain the same IDs, names, sizes, digests and source-run
bindings. Artifact ZIPs were not downloaded again to make this comparison.

This does not establish that the account's effective upload allowance has
recovered. Billing/account-level usage can update later; the actual allowance and
other shared usage were not determined. CI was not rerun, and run 35098277162's
upload failure and missing detailed evidence were not rewritten.

## Scope And Retention

Only `flutter-dev-debug-apk-*` artifacts on these completed P3-3 validation
branches were eligible:

- `dev/flutter/apk/p3-3-admission`
- `dev/flutter/apk/p3-3-t1a`
- `dev/flutter/apk/p3-3-batch6`

The latest APK on each branch and APKs directly referenced by existing evidence
were retained. No P3-4 APK artifact was in the inventory. Reference checks covered
tracked Markdown/JSON under `docs/` and the current board, without rebuilding
historical evidence or running historical tests.

| Retained artifact ID | Reason |
| --- | --- |
| 10399696022 | Latest admission-branch APK |
| 10397716463 | P3-3 Git closeout build evidence, run 34970506983 |
| 10378708222 | Explicit P3-3-v8/v9 frozen-evidence reference |
| 10298405373 | Latest T1A-branch APK |
| 10295579024 | Device-observation instrumentation evidence |
| 10274975471 | Development package-suffix evidence |
| 10269124401 | T1A instrumentation/A1-gap evidence |
| 10195957620 | Latest batch6-branch APK |
| 10195103592 | Batch9 delivery evidence |
| 10178414611 | Batch9 delivery evidence |
| 10142353404 | Flutter OTA research/development-build evidence |
| 10114677343 | Flutter OTA research/development-build evidence |

Retaining these remote copies is not a substitute for preserving required
evidence before their normal expiration. No retention policy was changed.

All `android-apk`, `windows-exe`, development-log artifacts and other non-target
artifacts were preserved. No workflow run, run log, Release, tag, branch, cache,
frozen bundle or local APK was deleted. Repository visibility, billing settings,
credentials and remotes were not changed.

## Fixed Deletion IDs

```text
10365501558 10359354491 10359033578 10358596960 10355291628
10349735025 10347848164 10343464703 10324166360 10323812014
10322504771 10321904870 10321261387 10318732642 10317086026
10316917553 10314869853 10313848058 10312970652 10312415446
10310803548 10310152327 10308383886 10308333857 10298265642
10296898496 10296638297 10296592229 10295834857 10295828455
10275095329 10274925068 10195747864 10188818842 10180444202
10177829361 10170341555 10156023702 10155052090 10116614979
```

Before deletion, the plan was bound to the initial inventory and reference-review
SHA-256 values. Each target was re-read and matched by ID, name, size, digest,
creation time, run ID, branch and source commit. The reviewed recent-run snapshots
had no active workflow on a targeted branch. Only the exact artifact DELETE
endpoint in the authorized repository was used.

## Interruptions And Reconciliation

The Python urllib transport encountered TLS `UNEXPECTED_EOF_WHILE_READING` twice.
The first invocation stopped after 28 HTTP 204 receipts. A read-only inventory
confirmed exactly those 28 removals and all 305 non-target artifacts unchanged.
The second invocation stopped after another 3 receipts.

There was no blind restart of the complete deletion list. The HTTP client was
changed to GitHub CLI, without disabling TLS verification or changing credentials.
A fresh inventory confirmed 31 removals and 9 still-present original targets.
Only those 9 were subsequently deleted. Final reconciliation found 40 unique
success receipts, no remaining target IDs and no non-target changes.

The two failure records and all three receipt journals remain in the local
operation directory. They are not relabeled as successful invocations.

## Local Records And Write Audit

Active project root: `D:\github\my\E-Track`.
Operation records: `.cache/artifact-cleanup-20260917/`.

| Record | SHA-256 |
| --- | --- |
| inventory.json | 81c3343f4e72be09d3e2311ef860212bc7a44746be5b803c2237630184c3cb89 |
| delete-plan.json | 08fd71f1be453a4c37a2c7b608f50e77bde567ea732a56a45bd8c93199176fca |
| reference-review.json | f366592f611983fdd2dcfcc02e281befbfda2f4280d4096e3022df36aacd27ba |
| operations.jsonl | 02ff024c0cc4c7808cd0362fe9ef94faf66cdc2be654da52a085c0225c8a036c |
| resume-operations.jsonl | 58587e1d083125df99f3513e4381b934314fca591e41aa9f5a05714cc7f617ab |
| final-operations.jsonl | 9e462f07fa128cd0d65e89ed172c0797bf533676b55c869e0c05b62b0aa6358a |
| final-after-delete.json | 35b18274839e5d87abe801ad09e25cd5718b1171a2d645354e238f806153b7dd |
| verification.json | 36217f0424500792c57e8e5f4382af5347304314d006c3b6bf062c8207cc7cc9 |

All controlled local outputs were normalized and checked against the active
project root, including complete parent-chain reparse checks. Commands used
`cmd.exe` and an explicit project working directory. Python ran isolated with
bytecode writes disabled. GitHub CLI HOME, AppData, temporary, cache and XDG state
locations were redirected into the operation directory; its generated
`state/gh/device-id` is inside that directory. No token was written to a file or
printed. The external GitHub CLI configuration was read-only and its content
hashes remained unchanged.

Local changes consist only of the operation directory, this note and the board's
cleanup update/session entry. Existing product/test edits and historical frozen
evidence were not modified. No commit, push, merge, build, CI dispatch, deployment,
installation or device operation was performed. P3-4 remains in progress, and
formal acceptance and hardware observations remain NOT_RUN.
