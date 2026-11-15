# Project Closeout: Firmware, Main Board And P51 Preparation

## Scope And Status

User-authorized order: build the corrected MCU and verify automatic Admin
ingestion; synchronize the local/remote main board and its maintenance rule;
finish the remaining preparation before the four-hour P51 campaign. Do not wait
for the user's manual upgrade between these independent work items. This scope
does not mark P5 complete, publish a channel, start a four-hour run, or rewrite
historical acceptance evidence.

Current closeout: MCU candidate ingestion and the original main-board/rule
delivery are complete. The latest original App and MCU 3.3.27 have now been
observed; safe App restart/reconnection and recording originals are verified.
The complete upgrade short cycle still lacks compatible current-backend reference
inputs. `canStartFourHour=false`. See the superseding
[current-App follow-up](P51-CURRENT-APP-2026-11-15.md).

Working root: `D:/github/my/E-Track/.cache/p35-integration-20261028/source`.
New receipts are under `.cache/project-closeout-20261115-01/` in that worktree.
Remote-main baseline before this documentation update:
`339af3a095ae42ee3442de3fb6dc1449525205ba`.

## Corrected MCU Candidate

Firmware **3.3.27 / 30327** was built by the existing `Original Admin Candidates`
workflow from `release/candidates` commit
`7574ed7e29551c163643120b42c355bac23cb3a9`.
Run `43634976957`, attempt 1, completed successfully: checks and firmware passed,
App was skipped. Only the version-only display formatter/model/view, its host
regression, and the firmware release request were delivered. Existing source-bound
13-case formatter checks and two ARM compilation results were reused, not rerun.

The new workflow compiled GCC App and matching Boot, packaged normal full and
recovery assets, performed native byte verification, and automatically registered
the ready candidate:
`fw_f2db8606a3ae0d846cca55c2efc17218656b6d5bb95a9fb06b1fcf653f5661bd`.
Backend readback matches source, version and run. Both current channel pointers
were preserved: Beta 3.3.26 revision 10 and Stable 3.3.26 revision 3, as actually
observed at this task's entry. Earlier notes describing Stable 3.3.25 are history.
There was no device installation, channel publication or automatic delta enablement.

Original compiler/package log: 641 warning diagnostic lines and zero error
diagnostic lines. App FLASH 614416 bytes; Boot FLASH 14724 bytes. These are actual
log counts, not a warning-free build claim. `build-log-02/result.json` links the
preserved successful job log and all six native source/package/registration
receipts. `backend-01/result.json` records independent backend readback.

The first approval request lost its network response. A fresh source/run/pending
read confirmed it still waited; the same authorized pending step was then approved.
No build was redispatched and no environment protection changed. Two local
post-processing issues were corrected using existing originals: the echoed script
line was excluded from JSON receipt parsing, and mixed-EOL Git board bytes were
read from the exact object rather than GraphQL text. Neither required another
firmware build, log download or mutation replay.

## Main Progress Reconciliation

Read-only inventory: 20 registered worktrees, 66 local branches, 81 current remote
branches. The project root is on an archive branch; `.cache/p34-final` is the actual
local main worktree. Its tracked files were clean and none of its 18426 untracked
evidence files overlapped the checked current main tree. Do not overwrite these
files while synchronizing main. Task records in the active worktree are not all
committed, and task-branch delivery is not main integration.

P1 originals on remote branch `dev/firmware/p51-packaging-20261104`, exact commit
`362653bb38d6fd1f9fb9bdca0339c1a6d6e77547`:

| Task | Repository-relative original | Result and remaining work |
| --- | --- | --- |
| P1-7-v4 | `docs/acceptance-contracts/P1-7-v4/final-matrix-02.json` | Five EXECUTED PASS, overall PASS; bundle f3af9ee656593e7f5581835c596bc6df53b4b54f; product/evidence main integration pending |
| P1-6-v3 | `docs/acceptance-contracts/P1-6-v3/final-matrix.json` | Fourteen AUTO PASS, six PHYSICAL NOT_OBSERVED; overall EVIDENCE_GAP; rows 03/05/07/15/16/17 remain |

P3 is 8/8 complete and P4 is 4/4 complete within their recorded candidate/staging
boundaries. They are not reopened. P5 is in progress, 0/3 closed. P5-2 fault
coverage and P5-3 final documentation/risk closure remain outstanding. P1-6's
physical gaps still block whole-project/final-release acceptance.

The new Main Progress Board rule is in the shared collaboration contract and
AGENTS.md, with PROJECT-08 in the shared index. It requires current-main status,
precise task/evidence locations and preserving local synchronization; it does
not merge unrelated product branches or create another tracking framework.

Board/rule commit: `07dafdb8c53d63b15d20e0749c6ea1cc60bf7681`. All 34 local
documentation checks and 36 existing governance regressions passed. These are
self-tests, not an invented independent acceptance. The original governance CI
`43637479097` passed all three jobs; its original log and job results are retained
in `main-ci-details-01`. Main App workflow `43637479128` ran path detection only;
APK, EXE, Pages and Release jobs were skipped. No extra product build was caused
by this documentation change.

The existing `.cache/p34-final` worktree fast-forwarded from
`b42d3e25db85d6aba397cb4d0fb34bb5b653904f` to that exact remote main commit.
Its tracked tree is clean, all six updated document contents match, and all
18426 untracked evidence files retain their size/mtime. No overlaps, deletions,
reset, archive-branch switch or task-worktree replacement occurred. Original
fetch/merge and comparison receipts are in `local-main-01`.

## P51 Preparation Carried Forward

The current detailed local notes are `docs/ota-exec-notes/P51-v2-scripts-2026-11-10.md`
and `docs/ota-exec-notes/P51-CLOUD-ENDPOINT-2026-11-10.md` in the working root above.
Their evidence roots are `.cache/p51-v2-scripts-20261109-01/` and
`.cache/p51-cloud-service-20261110-01/`. These latest notes are not represented as
already merged product changes on main.

Existing verified inputs/results, to reuse when still applicable:

- V2-only automation: window 24, DATA batch 12; development CI 42657269733 at
  `2685b053e6262872236cbb603eee1ecee54bd175`, both host suites passed.
- Protected packaging CI 42660592576 at `00597d8ec3917526c5b14d39086eab41bf087384`
  passed full/patch/recovery roundtrips and eleven native cases.
- Benchmark APK SHA-256 `d0c8b2a195dc57ec512119c46726c1cee02133eb5d02bfd52e60c30367602ecc`;
  this is distinct from the user's normal App and requires actual installed-state
  verification, not an assumption based on an old installation receipt.
- Fixed 1 MiB patch SHA-256 `f0f998c7121e4ab0e0a35d8088360289f91f9d06d24f434135531a78a067a4dd`,
  base 30321 / target 30322 and their complete-state restoration bindings.
- Stable isolated endpoint `https://e-track-p51-benchmark.pages.dev`; its earlier
  71 HTTP checks and 30/30 complete downloads passed, but are not 30 OTA upgrades
  or a four-hour stability observation. No paid service is introduced.

Current checks are in `p51-network-01/result.json`: the actual existing runner
validated its immutable APK/package/restoration/cloud bindings and performed
fresh health/latest/full-byte-download checks. The original 1 MiB download is
byte-identical. No source rebuild, package generation, deployment or installation
was necessary.

The private-ADB check is `p51-phone-01/result.json`, status
`P51_PHONE_CONNECTION_REQUIRED`. Its original client reports
`device '10ADA4197U001CK' not found`; the separate connected-device enumeration
also found no matching phone. The owned ADB server was closed, port 5093 is free,
and the read-only device lease was released. No App installation, UI action,
MCU operation, short transfer or four-hour campaign ran.

The existing current-session notification route delivered a real connection
reminder, recorded in `p51-user-action/notifications/connect-phone/result.json`.
It requests USB connection/unlock and the existing debug authorization if prompted,
not a manual firmware upgrade or chat reply. Delivery is not evidence that the
phone was connected. `p51-ready.json` records exact input/observation pins and
`canStartFourHour=false` rather than declaring preparation fully complete.

The phone-absent state and old readiness inputs above are historical, not the
current continuation command. Do not rerun the old benchmark-App readiness route.
The current original App is 1.0.77 / 103 and its connected MCU reports 3.3.27.
Both normal channels currently return NO_UPDATE for that identity. Follow
[P51 current-App/backend preparation](P51-CURRENT-APP-2026-11-15.md) for the
verified recorder lifecycle, deferred navigation bug and actual remaining inputs.
Native App/Boot/BCB/staging admission, the complete upgrade/restore short cycle
and four hours remain outstanding; historical v20 inputs are not a shortcut.

The user confirmed the browser notification problem was VPN-related and requested
no further investigation. The deferred favicon outcome remains outside this batch;
no paid Cloudflare Access customization or replacement credential is requested.
