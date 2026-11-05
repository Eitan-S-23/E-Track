# P51 Candidate Staging Implementation

Task: P51-CANDIDATE-STAGING-01. Local uncommitted implementation/self-tests
complete, pending root independent review; not acceptance or remote delivery.
Worktree: `D:/github/my/E-Track/.cache/p35-integration-20261028/source`.
Entry HEAD: `045f1f89effb11f672d3a91ff7f7ab32704f4800`.
Branch: `dev/flutter/p51-timing-20261104`. Root retains actual delivery/acceptance.

## Design And Scope

The original `p51-artifact-candidate-v2` remains immutable and cannot be parsed
as registration metadata. Ordinary execute must still bind compile source to
execution source and must not become an unchanged-candidate bypass.

Add a separate default-off `stage_candidate` dispatch, a protected isolated
staging dispatcher and read-only archive adapter. Reuse the existing immutable
archive resolver, standard metadata builder/parser, Worker health/preflight,
conditional uploader/full readback and registration helper with retries=1.
Do not build/finalize/encrypt/search, modify UI, initialize or operate hardware.

Standard registration commitSha/runId mean original compilation source/run;
asset names/R2 keys and the full/patch base identities remain stable across
delivery retries. Independent source proof includes original attempt/artifact/
timestamp; independent delivery proof includes actual workflow source/ref/run/
attempt. Standard isFormalRelease=true is the existing v2 schema's registration
namespace requirement, not production approval. It applies only to the new
staging description, never to the archived metadata. Staging evidence uses a
distinct protocol/mode and productionPublishable=false; existing promotion
checks must reject it, even with correct hashes and invented approval inputs.

Only the pinned p41 test Worker and bucket are admissible. All local identities
are checked before cloud factory calls; health/preflight precede uploading;
all complete readbacks precede one registration. Failures/uncertainty stop without
automatic retries. No channel or GitHub Release, D1 direct write or deletion.

Evidence planned under `.cache/p51-candidate-staging-impl-20261105-01/`, with
project-local temp/cache paths and existing owned launcher. Original root
readiness probes and candidate bytes are reused, not re-executed. Actual backend
deduplication and current stable72/beta11 observations remain root obligations;
the release-list timeout does not prove 30319 is absent.

## Implemented Scope

- `.github/scripts/firmware-candidate-staging.mjs`: separate gate/inputs/execute
  dispatcher, pinned source/asset verification and standard registration projection.
- `Tools/ota/p51-staging-inputs.py` and `.json`: immutable archive admission and
  exact three-asset copying, reusing `p51-package.py::resolve_supplement` without
  calling its packaging, compiler, encryption, finalization or search functions.
- `.github/workflows/firmware-build.yml`: default-off protected `stage-candidate`
  job; existing build/development/rehearsal/production/binding jobs exclude this
  mode. Mixed package/stage inputs still reach explicit rejecting gates.
- Existing candidate admission and ordinary releaseConfig reject stage mixing;
  the existing 300-second bounded R2 operation wrapper is exported/reused.
- Two new host test files and the existing workflow expectation updates.
  No Worker/Flutter/UI/MCU product source, old candidate input or metadata changed.

All asset copies retain the original bytes, sizes and digests from preparation.
Canonical display/download names come from the existing standard metadata policy;
this changes no original archive member or SD filename. Exactly original FULL,
30318-to-30319 PATCH and recovery are uploaded. Neither original initialization
package nor either ordinary/generated Boot can enter the upload inventory.

## Source Fields And Registration Semantics

| Field | Meaning |
| --- | --- |
| Standard metadata `commitSha` | Original compile source `1430c8ff7f3bcd9a35bfe158ba697b99021f75f2` |
| Standard metadata `runId` | Original compilation run `41900439548`, stable across delivery attempts |
| Independent proof `originalOwner.runAttempt/artifactId/buildTimestamp` | `1 / 13359301400 / 1793820855` |
| Independent delivery `commitSha/runId/runAttempt/workflowCommit/workflowRef` | Actual reviewed delivery checkout and actual Actions owner, never rewritten |
| `sourceProofSha256` | Exact saved source-proof file bytes, not an unlabelled canonical-JSON surrogate |
| `metadataSha256` | Canonical ready registration bytes after every full R2 readback |

The exact raw archive, artifact receipt, original candidate metadata, finalized
image, build/keyed evidence and native-verification bytes are pinned. The original
metadata stays `isFormalRelease=false`, `productionPublishable=false` and
`readyRegistered=false`. The new standard descriptor uses `isFormalRelease=true`
only because the unchanged v2 registration parser requires that namespace.
It does not grant production eligibility, change the archive's flags, prove a
GitHub Release exists, or constitute P5 acceptance. Canonical githubUrl values
are schema-required references; this mode never publishes those assets to GitHub.
The independent delivery protocol is `p51-immutable-candidate-staging-v1`, mode
`immutable-candidate-staging`, approvalEligible/productionPublishable=false.
Actual production promotion rejects these bytes even with consistent metadata,
build hashes and a hypothetical successful original-source approval record.

The dispatcher checks the full original archive digest again at execution,
compares materialized evidence and assets before invoking the cloud factory,
and revalidates the metadata builder's exact target/asset/base projection.
Wrong profiles or materialized target/hash changes cannot be admitted as a
staging package. Original compiled-key proof is consumed only as pinned metadata;
no plaintext/protected AES key is required or read by this mode.

## Executed Host Verification

All commands use cmd.exe, explicit active-root cwd and project-local controlled
TEMP/TMP/TMPDIR, HOME/USERPROFILE, APPDATA/LOCALAPPDATA and cache/fixture paths.
E/run.py uses the existing WindowsJob launcher with a 600-second suite deadline;
selected archive subprocesses have 90-second bounds. Each row below exited 0:

    python -I -S -B -X utf8 .cache\p51-candidate-staging-impl-20261105-01\run.py entry
    python -I -S -B -X utf8 .cache\p51-candidate-staging-impl-20261105-01\run.py python-01
    python -I -S -B -X utf8 .cache\p51-candidate-staging-impl-20261105-01\run.py staging-01
    python -I -S -B -X utf8 .cache\p51-candidate-staging-impl-20261105-01\run.py legacy-01
    python -I -S -B -X utf8 .cache\p51-candidate-staging-impl-20261105-01\run.py followup-01
    python -I -S -B -X utf8 .cache\p51-candidate-staging-impl-20261105-01\run.py identity-01
    python -I -S -B -X utf8 .cache\p51-candidate-staging-impl-20261105-01\run.py diff-01

| Run | Actual suite | Result |
| --- | --- | --- |
| python-01 | test_p51_staging_inputs.py | 6/6, 2.970 test seconds |
| staging-01 | test_firmware_staging.mjs | 54/54, 15.297 seconds |
| legacy-01 | test_firmware_candidate/workflow/s3/build_profile.mjs | 206/206, 40.292 seconds |
| followup-01 | Existing-object and updated workflow cases | 3/3, 9.213 seconds |
| identity-01 | Exact saved-source-proof hash and generated metadata identity | 1/1, 4.764 seconds |
| diff-01 | Scoped git diff --check | PASS, four Git LF/CRLF advisories |

There are 268 distinct top-level tests; workflow/source-binding targeted reruns
are not extra distinct tests. The final two existing-object tests were added
after staging-01 and executed only in followup-01. Final source-binding metadata
checks were added during closeout and executed in identity-01, without replaying
the rest of the validated matrix. The closeout recognized target-directory YAML
imports needed an explicit staging PYTHONPATH and added/tested that mapping;
it also made the source-proof hash an exact raw-file binding. No failed test run
is hidden: all executed suites succeeded. Three early read-only path/filename
lookups failed (missing optional file or cmd wildcard syntax); corrected lookups
are recorded in the session. They made no filesystem writes.

Exact argv/cwd/environment are in E/RUN/command.json; unfiltered originals and
exit/tree-closure receipts are in E/RUN/evidence/native/host-suite.{stdout.txt,
stderr.txt,process.json}. Negative delivery traces are retained in each generated
fixture's evidence/staging-delivery-steps.json, including failed-or-uncertain and
automaticRetry=false. No old failed or successful evidence was overwritten.
Test diagnostics have zero warnings/errors; ARM/native compiler warnings/errors
are NOT_RUN, not claimed as zero. Git advisories are not compiler warnings.
The task-date evidence paths remain 20261105 across the 2026-11-06 continuation.

Verified wrong archive/source/run/attempt/artifact/timestamp, target/base/profile,
tampered assets/evidence and output escape rejection. Gate=true, production
bucket/Worker, mixed modes, unknown/control-plane/AES credentials, approval and
base-version ambient pollution all fail before any cloud-port invocation.
Python transformation/compiler/search spies all remain uncalled. The Node route
uses real metadata/parser/preflight/upload/full-stream hashing/register helpers;
only checkout identity, S3 storage and HTTP responses are explicit test doubles.
Existing S3 SDK regression uses its existing test transport, not real credentials.

Full-readback corruption/interruption, health/preflight conflict and uncertain R2
results never register. Registration conflict/uncertainty emits exactly one
request and no ready evidence, using registerFirmware retries=1. Matching existing
objects are fully read back with zero put calls and one idempotent registration;
a conflicting existing object is neither overwritten nor registered. Abort closes
the owned storage port. No deliberate replay registration is needed here.

## Boundaries And Identity

E/entry.json binds actual entry HEAD/branch/dirty tracked files, original archive,
artifact receipt, unchanged UI source and root preparation note. E/audit.json
binds final changed/new file hashes, every local output hash, original/raw-log
hashes and owned-process closure. Four existing tracked files changed; other
entry identities remain byte-identical. Shared dirty changes were not reset,
cleaned, staged, committed or switched. The index and HEAD remain unchanged.

All chosen outputs, fake test headers/assets and test cleanup targets are within
the authorized worktree, principally E; outputPath/host_io guards check normalized
directory-boundary membership and parent links before writes. The closing audit
enumerates ignored evidence, not merely git status. No controllable output was
selected outside this root, no external artifact was cleaned, and no PowerShell
startup, package installation, download, private credential access, real network,
sub-agent/contact, ARM build, device operation or actual CI occurred locally.
Existing candidate metadata and archive bytes remain unchanged. All owned suite
receipts and aborted test storage ports report closure; no native-active marker
or Python bytecode remains. No `.trellis` exists; no competing task/spec was made.

## Proposed Dispatch And Remaining Root Work

After independent review and integration, root selects the actual reviewed tooling
commit/ref. Dispatch firmware-build.yml at that same ref with:

    stage_candidate=true
    package_candidate=false
    publish=false
    rehearsal=false
    check_bindings=false
    candidate_reviewed_commit=<actual reviewed delivery checkout SHA, not original compile SHA>
    candidate_mode=archived-original
    version_name=3.3.19
    firmware_build_profile=p34-v2-candidate
    candidate_base_version=<empty>
    candidate_full_base_version=<empty>
    approved_rehearsal_run_id=<empty>
    release_notes=<empty; immutable staging description supplied by the dispatcher>

The stage job uses only firmware-rehearsal's existing five named secrets and
FIRMWARE_REHEARSAL_TRACE_R2_BUCKET. No AES/GitHub publication/control-plane key
is injected. OTA_BOOT_CHAIN_READY must remain false. Destination is exactly
`https://e-track-firmware-p41-test.tangjichentudou.workers.dev` and
`e-track-firmware-p41-test-releases`. The job is serial with existing release
operations, has a 20-minute job/15-minute delivery bound, and emits an explicit
three-asset plus safe-proof/evidence upload inventory. Python/S3 dependencies are
contained; no firmware toolchain, finalize, encryption or witness step exists.

Real protected CI and actual upload/registration are NOT_RUN. Before dispatch,
root must fresh-reconcile the exact 30319 release/asset inventory and use matching
existing work. A timed-out release-list GET does not prove absence. Conflict or
uncertainty requires reconciliation before a new run; changing run directories
does not justify a blind retry. Stable72/beta11 are the latest retained channel
observations, not permission to mutate either; never use the old revision70.
Endpoint/installed Release APK98 binding, channel control, approved execution
source commit, independent staging evidence checks and formal freeze remain
root work. This entry does not grant a Debug endpoint override to APK98.
Four combinations, 30-of-30 and four hours remain NOT_RUN here; no P5 result,
production approval or resumed initialization is claimed. Implementation stops
at this local handoff for root's independent review.
