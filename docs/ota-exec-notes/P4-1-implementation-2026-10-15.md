# P4-1 Unattended Development

Status: IN_PROGRESS. Implementation self-tests are not independent acceptance.
Sole Spec: `docs/ota-prompts/prompt-P4-1-implementation.md` and its frozen references.

## Entry And Authority

- Baseline: local and remote main `b42d3e25db85d6aba397cb4d0fb34bb5b653904f`.
- P4-2 accepted product: `fc4fbbb8193fcc536ef408b7b662d44b30f869dc`; consume its
  actual v2 schema, scripts, versioned fixture, business handlers and tests.
- Exclusive branch: `dev/p4-1/unattended-20261015`; worktree:
  `D:/github/my/E-Track/.cache/p41-dev-20261015`.
- User authorizes scoped implementation/WIP commits, pushes as `Eitan-S-23`,
  existing checks/build-only Actions and project-contained evidence retrieval.
  No main merge, tag, Release, deployment, cloud resource/configuration write,
  device operation, external filesystem write or other-task work is authorized.
- Shared archive worktree, main's historical evidence, and the pre-existing
  initializing P4-1 worktree remain untouched. No reset/clean/stash is used.
- P3-5 is paused by this dispatch, not by a new dependency. P4-3/P4-4 are not
  started. The eventual configuration checklist is an interface handoff only.
- `.trellis` is absent. Do not create a competing task or Spec.

## Gap Register

| ID | Observed gap and invariant | Bounded action / owner | Feedback |
| --- | --- | --- | --- |
| P41-01 | `publish=false` skips release tooling; native Worker tests exclude `*.host.test.ts`. | P4-1 adds credential-free development execution in the existing firmware workflow; explicitly separate host script/migration and native workerd runs. | Pending first batch. |
| P41-02 | Workflow still supplies removed single-bin metadata flags and omits uploader asset/remote selectors. P4-2 scripts already enforce v2. | Replace only P4-1's consumers; retain one schema/backend. Enumerate other consumers without modifying their workflows. | Pending. |
| P41-03 | No formal base provenance/patch byte validation/recovery packaging in the workflow. | Thin orchestration of existing finalize/pack/unpack/recovery owners; actual byte and negative tests before widening. | Pending. |
| P41-04 | Existing release step edits tags and clobbers assets, defaults to staging bucket, and has no production environment declaration. | Immutable publish/readback, explicit environment configuration, first-step gate and shared rehearsal path; no real publish execution this batch. | Pending. |
| P41-05 | Canonical rehearsal provenance/rebuild comparison and version monotonicity are not wired. | Preserve frozen canonical `runId`; audit-only execution id; fail before remote writes on inconsistent inputs. | Pending. |
| P41-EXT | Actual isolated bindings/uploader credentials, approved formal base, rehearsal and independent approval unavailable. | P4-4/root configuration owner plus independent reviewer; keep real observations NOT_RUN. Do not retry expired login or D1 401. | NOT_RUN. |

## Batch Plan

1. Establish actual host/script/migration and native workerd feedback, including
   expected failures and no downstream effects. Commit a bounded WIP and inspect
   raw Actions steps, not just the run conclusion.
2. Add byte preparation and provenance validation through existing tools, then
   execute positive/negative byte and CLI tests.
3. Wire the same preparation/upload/register implementation into isolated
   rehearsal and gated production, verify ordering/failure/gates and all callers.
4. Run affected CI on the candidate commit, preserve originals and byte hashes,
   deliver configuration/real-rehearsal checklist, then request independent review.

Every meaningful batch obtains runtime feedback before further product changes.
Real R2/D1/Access, production-zero-side-effect snapshots and independent acceptance
are never inferred from fixtures or local doubles. P4-1 remains in progress.

## Initial Feedback

- npm mirror download failed with ECONNRESET; original `batch1-npm-ci` output is
  preserved. The pinned install succeeded (87 packages, exit 0) after explicitly
  switching the registry host to npmjs with integrity still enforced. No lockfile
  or tool version changed.
- Initial host run: migration 17/17 PASS, script suite failed to import (exit 1).
  Vite's `hashbangRE = /^#!.*\n/` does not strip CRLF shebangs, while direct Node
  imports succeed. These mode-100644 files are always invoked with Node. Removing
  only their unused shebangs fixes the cross-platform test entry without changing
  schema or business behavior; all three firmware CLI consumers are covered.
- Windows native run: zero tests, three workerd startup access violations (exit 1),
  consistent with the accepted P4-2 host limitation. No system runtime installation
  is authorized or attempted. Native evidence must come from Linux Actions.
- Build outputs move from `/tmp/etfw` to the Actions workspace `.cache/etfw`;
  the build inputs, targets and path-length setting are unchanged.

## Milestone 1: Runnable Feedback

- WIP `1735f9d4da8fc423f4fe8364cd1cdd2f333941d7`, run `38630966396`:
  explicit host script/migration tests 34/34, native workerd 156/156, Worker
  typecheck and GCC App/Boot build passed. Release job skipped under
  `publish=false`; no cloud credentials in the development job.
- Raw ZIP is `.cache/github/batch1-logs.zip` (234558 bytes). Its actual command
  lines, CLI output, `SQL_REJECT` constraints and separate 34/156 count lines were
  inspected. Duplicate job/step log copies in the ZIP are not additional tests.
- Negative originals include bad raw digest/missing artifact migration rejection
  before SQL writes, R2 collision rejection without overwrite, missing readback,
  skip-readback CLI exit 2 and actual native D1 ready/uniqueness constraints.
- Local repaired host run is also 34/34 (exit 0); local typecheck exit 0.

## Batch 2: Byte Preparation

The production preparation script calls the existing finalize, full/patch pack,
unpack and recovery helper. It checks subprocess exit/stdout, actual candidate
bytes, raw/base identities, recovery tail/header and same-run GCC App/Boot inputs.
The P4-2 builder remains the sole registration schema and naming implementation.

`--reproduce-from` reuses an approved envelope only after recomputed header plus
ciphertext equals every reference byte under the configured key. It is not a
nonce override; changed plaintext, key, header or corrupt reference fails before
output. Normal packaging keeps its random nonce. The vendor algorithm is not
changed. Its scratch cwd is contained and its success stdout is checked.

Local self-tests: production preparation 14/14 (actual Python/vendor processes),
package/replay 8/8, exits 0. The first Python run had 7 passing cases and one
harness error caused by `tempfile` caching a deleted test directory; the scoped
test override restores that cache per case. Original failure is preserved as
`batch2-pack`, corrected run as `batch2-pack-fixed`; no assertion was weakened.
Linux byte-generation CI is required before treating the host adapter as tested.

The Windows test artifacts are deliberately synthetic, not an approved formal
base or a rehearsal. The production transport must obtain and verify actual
source provenance before calling this offline preparation entry.
