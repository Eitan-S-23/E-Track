# P51-REFERENCE-SEARCH-01: Bounded Search Miss On Actual New Source

Disposition: OPEN, packaging/reference tooling failure, not an observed MCU/UI
failure. Root preserves independent review ownership. No new protected run or
device operation should be started merely to try the unchanged deterministic
search again. The 205-test local review and the actual failed CI are distinct
observations; neither is rewritten.

## Exact Evidence

Active writable worktree:
`D:/github/my/E-Track/.cache/p35-integration-20261028/source`.
Current implementation commit: `db049b6b2b9e0bc0ff0c534d52b686494b7d704c`.
Existing local branch: `dev/flutter/p51-timing-20261104`.
Remote execution branch: `dev/firmware/p51-packaging-20261104`.
Do not switch either branch, amend the commit or touch unrelated dirty files.

Failed run: `41849745315/1`. Artifact `13335076821`, 1,815,505 bytes, SHA-256
`c7ab23cd19071b4ba053d0cab44b647878407af0832926e948b0eae7225c72f0`.
Evidence root: `.cache/p51-new-source-delivery-20261104-01/`.
Archive and workflow logs are retained as `download-01/archive.stdout` and
`download-01/workflow-logs.stdout`; the safe extraction is `download-01/extracted/`.
`download-01/result.json` hashes all 302 extracted files and both archives.

Actual Linux toolchain install/checksum and host regressions passed: 50 Node
tests and 13 Python tests. Real keyed GCC configure/build/size all passed, with
641 compile/link warnings and zero compiler errors. The ordinary built Boot is
compile-only, not the approved external group16 Boot. All three compiler process
groups closed; private candidate/key cleanup and evidence upload passed.

The later `source-package` stage evaluated exactly 256 reference encodings and
failed before outputting any full/patch/recovery package or candidate metadata.
It did not time out. `failure-analysis-01/result.json` binds this analysis.
The generic child diagnostic incorrectly remains at stage `admission`; the
256 complete measurement originals and search control flow locate the exhausted
budget inside reference search, not source admission or ARM compilation.

Raw keyed App: 615132 bytes, SHA-256
`78ca849d31976ab5e5037f5aa1f9d02d58f17ed006b1710653207168a0385438`.
Its exact build timestamp is `1793802751`. Root reconstructed the documented
header-only diagnostic pair from those original bytes without an encryption key:

- Base 3.3.18: `reference-probe-01/diagnostic-base.bin`, SHA-256
  `0c3362e302504c1890f9e5c4ba1f6d9b00e9396e6250d14507c027c2d50c776c`.
- Target 3.3.19: `reference-probe-01/diagnostic-target.bin`, SHA-256
  `46e576cd3b20b65ffafc420c44da3082ab060ecbf937b52fc16d7b74ca0884df`.

These hashes match every applicable original CI measurement. They are fixed
regression inputs, not an installable/candidate-admitted firmware set. Root did
not parse or export the compiled encryption key and did not encrypt a package.

Nearest original measurements at seed 7:

| Count | Salt | ETU bytes | Difference |
| ---: | ---: | ---: | ---: |
| 210160 | 52 | 1048577 | +1 |
| 210168 | 58 | 1048575 | -1 |

Root also ran a finite, separate diagnostic using the unchanged encoder: unseen
counts within +/-32 of 210160 at seed 7/salt 52. All 61 nonduplicate measurements
finished without an exact witness. Originals and the 300-second owned-command
receipt remain under `reference-probe-01/` and `reference-probe-command-01/`.
No result was padded, truncated, patched or promoted, and no CI rerun occurred.

## Required Remediation

Read project AGENTS.md, collaboration/acceptance contracts, this note and the
new-source implementation handoff before editing. Root owns candidate integration,
protected execution and independent adjudication; the implementation owner only
repairs/self-tests the bounded reference synthesis path and hands it back.

Start at `Tools/ota/p34-acceptance/encoding.py::search` and
`Tools/ota/p51-package.py::source_reference`. Current search bisects only salt=0,
then spends its remaining budget cycling salts at four counts chosen from that
original bracket. Compression length is not monotonic and the salted counts are
not re-centered. The recorded +/-32 probe also failed; do not present that simple
fixed-neighborhood change alone as a demonstrated solution.

Preferred direction: retain the existing legal progressing patch stream/encoder,
but use a bounded adaptive count/salt or seed search that actually finds a witness
for the fixed real pair, accounts for nonmonotonic lengths and preserves every
measurement. Keep the reviewed 256-unique-encoding limit unless concrete evidence
establishes why a different bounded policy is necessary; do not merely increase
timeouts, repeat CI or choose a lucky seed without a reproducible selection policy.
Improve the failure stage/cause receipt so reference budget exhaustion is reported
explicitly and safely. Avoid unrelated pipeline or firmware changes.

Invariants: preserve archived-original mode, old inputs, UI, filesystem/protocol/
Boot behavior, real base/target identities, key isolation and production gates.
No padding, compression tail, truncation, fake total length, ignored bytes,
nonprogressing controls or weakened full-consumption/decoder checks. No private
key retrieval/export, local production encryption, device operation, commit, push,
workflow dispatch, R2/D1 mutation or formal acceptance by the implementation owner.

Verification oracle:

1. Use the exact real diagnostic pair above in an unmocked encoder/search
   regression, preserving the 256-sample failure as the old-behavior anchor.
   Produce a legal exact 1048576-byte witness within the repaired declared limit;
   verify EOS/full consumption and exact target reconstruction.
2. Exercise multiple representative image/header/version/timestamp cases, plus
   nonmonotonic measurement patterns and genuine budget exhaustion. No hardcoded
   recipe specific to only this candidate. Reuse existing native decoder tests
   with public self-test keys, never request the protected AES key.
3. Rerun affected old/new source, candidate admission, reference, metadata and
   process-cleanup host tests. Preserve negative controls and actual command,
   warning/error, timeout and output-boundary receipts.
4. Confirm exhausted/no-witness runs fail closed with precise stage/cause, no
   admitted assets, no false native PASS and correct process/private cleanup.

All outputs stay in a fresh project-local ignored evidence directory after path
and reparse-parent preflight. No .trellis directory exists in this worktree.
Use apply_patch for manual edits and cmd.exe for commands. Save a separate
implementation handoff, not concurrent edits to root's main task record.

Root will independently review the repair batch, check the intended newly
finalized inputs before the next protected run, and then bind actual candidate
assets/recovery. No unrelated historical or completed UI campaign is reopened.

## Owner Routing

No implementation agent is currently live in the root tool tree. The read-only
cc-connect relay discovery returned `no binding for this chat`. The previous
P51-PACKAGING-01 child authorization was explicitly bounded to that prior child;
it does not silently create an additional implementation owner for this repair.
User routing/authorization for one independent implementation owner is the next
required intervention. No daemon, relay binding or account configuration was
changed to work around it.

## Independent Repair Review, 2026-11-05

The user returned the completed external implementation; no new child agent was
started. Root's local repair review is PASS with no blocking findings. See
`P51-reference-search-implementation-2026-11-04.md` and the 2026-11-05 review entry
in `P1-P5-nonpower-sequence-2026-11-04.md`. The four independent charged-cache
scheduler replays and fresh strict witness checks reproduce 137/177/26/229
selections. The initial failure and earlier owner-routing state above remain
historical facts, not current blockers. Actual next-source CI and candidate
binding remain pending; local review does not retroactively make run 41849745315
successful or close P5.
