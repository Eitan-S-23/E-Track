# P3-4 Batched Link Candidates

This is development work, not independent acceptance or new hardware authority.
The accepted P3-3-v9 and P3-4 parser bundles are unchanged. The board retains
3.2.7-p34b / 30207; no additional OTA, reset, installation or baud change was
performed to prepare these candidates.

## Baseline And Its Limits

Original snapshot, binding and strict parser receipt are under
`.cache/p3-4-baseline-session-20260922/resume-2/finished-retrieval/` in the active
P3-4 worktree. Target readback and Boot confirmation are under the sibling
`board/` directory. These remain original local evidence, not published artifacts.

- APK source: `5a45b03cd6d5f150605823fa328f4a7e92b7347b`.
- APK SHA-256: `1fbde2cf7f0c9b7ee8f45ff66db4c774c8f1a8392bc348c2e93e569180d06ccb`.
- FULL: 284643 bytes, SHA-256
  `da82725792afeb88b353de7c595596eafa47f1c1db9bfa4905803693b159d600`.
- BEGIN to successful END ACK: 267.787304 s, 1.038031585 KiB/s.
- 2224 unique DATA segments and 2224 sends: no DATA retransmissions.
- 71 durable events; final durable offset 284643.
- MTU 247, net chunk capacity 244, with-response writes, UART 115200 / 8N1.
- 2229 discoveries and 2227 GATT writes (315942 physical bytes).
- Nested totals: discovery 30.373288 s; platform writes 205.358956 s;
  enclosing GATT calls 236.893721 s. Do not add these as exclusive phases.
- END ACK to target identity verification: 63.753584 s on the App clock.
- Complete preserved log: 11442 records, 11439 producer lines, no loss.
  Strict parser: 17 groups, 11291 samples, no findings.
- ACK latency population is incomplete: 2220 valid samples for 2224 DATA segments,
  `partial:missing=4,early=4`. Partial P99 is not a production timeout input.
  MCU UART/staging intervals are still unknown; this is not a 1 MiB reference run.

115200 / 10 gives 11520 B/s (11.25 KiB/s) before protocol overhead. The observed
1.04 KiB/s does not establish that UART is saturated. This run recovered a
trustworthy comparison baseline; it was not a test proving the 115200 ceiling
or a decision to retain that baud in production. Earlier higher-baud AT exchanges
prove communication/recovery only, not full OTA throughput or reliability.

## One Prepared Screening Batch

The same source contains two independent, default-off debug candidates. Explicit
`flutter-dev-checks.yml` APK dispatch input `ota_link_candidate` selects them:

| Candidate | Reuse exact mobile GATT binding | Prefer without-response if supported |
| --- | --- | --- |
| baseline | no | no |
| reuse-with | yes | no |
| discover-without | no | yes |
| reuse-without | yes | yes |

The input changes only development APK build defines. Ordinary pushes remain
checks-only; release defaults and production baud are unchanged. APK metadata
records `requested_ota_link_candidate`, explicitly build intent. Actual discovery
counts and `writeMode` must be checked in original App observations; a preference
cannot create a capability missing from FFF2. No fixed speedup is claimed.

Prepare all variants and run the combined host/Flutter test batch before involving
the user or opening short-lived device workers. Screen this 2x2 matrix at fixed
115200 first, then hold the selected sender profile fixed while comparing supported
230400/460800/921600 settings with synchronized MCU/module readback. This avoids
rebuilding or rediscovering the test route after every observation. One physical
link remains serial. Do not combine several changed variables and attribute all
of the result to baud.

## Invariants And Development Oracles

- Reuse only a strictly discovered FFF0/FFF2/FFF1 binding owned by the current
  device and generation. Missing/invalid bindings fail closed, never rediscover
  silently inside an optimized write and never fall back to an arbitrary UUID.
- Disconnect, service reset, device switch and changed capabilities revoke the
  binding. Older discovery completions cannot replace or clear a newer binding.
- A real, identical foreground-resume rediscovery retains the same paused
  transport lease. It is still a fresh discovery, not a fabricated cached answer.
- Channel ownership is captured before asynchronous MTU/notify setup. Check it
  before and after platform writes and before accepting notifications. A stale
  channel must not send queued fragments or even ABORT into a replacement link.
  Ordinary cancellation on the original live link still sends a serialized ABORT.
- Native write success and stale GATT completion are separate facts in timing
  records. Cache hits do not increment discovery counts.
- Keep CRC, seq, packet layout, 128-byte DATA, frame serialization, MCU credit,
  durable truth, cancel guards, device identity and timeout/retry bounds unchanged.
- Tests cover the four configurations, exact IDs/capabilities, repeated writes,
  foreground-resume recheck, notification ownership and late/reset/switch paths.
  Python tests cover opt-in build injection, bad input rejection and honest
  metadata. Windows tests cover native-adapter write capability selection;
  Linux tests exercise the real mobile service path with platform objects replaced.

## Next Hardware Boundary

Development feedback is recorded separately from hardware:

- Governance/skill commit `73a3563af99ac5a9e0931126be1bc508490cb049` passed
  [Acceptance Governance](https://github.com/Eitan-S-23/E-Track/actions/runs/35652854571)
  on both helper hosts and the governance regression job. Original logs are kept
  under `.cache/governance-skill-feedback-20260922/`.
- Local host batch: 62 development-runner, 28 APK-helper and 19 observation-parser
  tests passed. The first host run's long-path failure is preserved under
  `.cache/p3-4-batch-20260922/host-test-001/`. Read-only reproduction showed
  `git hash-object` failing with `Filename too long`; process-local
  `core.longpaths=true` fixed that same fixture. No external short directory or
  global Git configuration was used. The corrected batch is `host-test-002/`.
- First WIP `6c6928b788c2c8b6db88a102ce493698c8b529a0` failed
  [Flutter development CI](https://github.com/Eitan-S-23/E-Track/actions/runs/35657253106):
  missing explicit const constructors in default expressions and a fake field
  colliding with the plugin's stream getter. Both are repaired as one source
  batch; the original failed job logs remain `logs-35657253106.zip`. This is not
  a performance result or an independent acceptance round.

The earlier one-transfer authorization is spent. The installed 30207 target is
not an equivalent starting state for replaying the old 30206-to-30207 FULL.
Before another full-OTA matrix, root must obtain a bounded authorization and a
legitimate, controlled initial image/BCB/durable-state and package plan. An
App-only downgrade across BCB, a silent repeat upgrade, a staging-only benchmark
reported as full OTA, or padding an invalid package to 1 MiB is not a shortcut.

Agree the comparison asset/state plan, candidate order, screening/recovery caps,
retained final version and genuine user actions once for the batch. Prepare both
collectors, final App snapshot retrieval and passive target/Boot verification
before that window. After screening, the unchanged reference-package, 30/30,
4-hour soak and 10/10 recovery criteria still apply; they are not satisfied by
these source changes or development CI.
