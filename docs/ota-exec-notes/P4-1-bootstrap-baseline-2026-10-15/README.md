# Inaugural Bootstrap Baseline Candidate

This is a durable source archive for the candidate OTA-DEC-017 amendment, not a
formal Release, rehearsal, installable package, production approval or P4-1 PASS.
The original development labels and verification bytes are unchanged. Only the
exact finalized raw App is proposed as an inaugural patch baseline. Its existing
development-key encrypted packages are not proposed as release packages.

## Original Identity

- Repository: `Eitan-S-23/E-Track`.
- Source workflow: `.github/workflows/firmware-build.yml`, explicit build-only
  dispatch `38642386248`, attempt `1`, completed successfully.
- Source commit: `fa74905e84c489cccc248617d37ab9f56c8f961c`.
- Version: `3.2.7`, code `30207`, build timestamp `1792014177`.
- Final App: 605072 bytes,
  `aaf5ccdb047ef8b3ff4ae0837f9593ceca857d90c98ea0bc09360e411bf4196f`.
- GCC placeholder: 605072 bytes,
  `5f7c42bd43acef12a262e53c378fa1fee3f44a6571c081a373d60b494d23fe8e`.
- Matching Boot: 14724 bytes,
  `3554e193f498d23210f5ef32e09de64575b7cd39104fafcc950740e5e8a7ec34`.
- GCC development artifact: `11931006831`, ZIP SHA-256
  `4e46526eb7bab0a8d416cad29044efdccc206ff7a922cfc2ec593d3ccf60c149`.

The complete source ZIPs and original run/jobs/step evidence already exist in
Git commit `a29d0efef0fa408e786c739ea76b085ad2f95991` under
`docs/ota-exec-notes/P4-1-ci-2026-10-15/github/`. They are referenced rather than
duplicated or rewritten:

| Original | Artifact | ZIP SHA-256 |
| --- | --- | --- |
| `batch5-artifact-gcc.zip` | `11931006831` | `4e46526eb7bab0a8d416cad29044efdccc206ff7a922cfc2ec593d3ccf60c149` |
| `batch5-artifact-app-retry.zip` | `11930961851` | `d689a968383672b42be2253365be90db6a25973c28127755b08ab3fa2ef16859` |
| `batch5-artifact-boot.zip` | `11930422285` | `b3965ba603e9bbef96495b4c5a2134f7d957aa63322f477439eaed42cba61c96` |

The same directory retains `batch5-artifacts.json`, `batch5-runs.json`,
`batch5-jobs.json` and `batch5-logs.zip`. The first ZIP contains the complete
original preparation steps and full/recovery bytes. The selected files here
match the relevant ZIP members exactly, not a new build or re-finalization.
`provenance.json` composes the unchanged semantic API/verification/development
objects for runtime validation; `inventory.json` records exact archive bytes.

## Independent Scope

Non-implementing reviewer `/root/p41_bootstrap_review` independently recomputed
all three selected binary hashes, checked the three source ZIP hashes and the
six selected ZIP members, reconciled source run/attempt/commit and successful
GCC jobs, and executed the existing read-only firmware byte verifier with
`python -B`. It confirmed full header/raw integrity and that only the 96-byte
header differs from the original GCC placeholder. It performed no build,
credential read, cloud/network or device operation and wrote no files.

That review establishes a technically qualified candidate source. It does not
approve unreviewed later changes, alter the prior source run or waive activation
of the candidate contract. The source preparation has `base:null` and
`patchByteEqual:null`; it is not three-asset or remote-rehearsal evidence.

## Admission Still Required

After this archive and the exact target code exist as immutable commits, the
configuration owner can form the explicit descriptor defined only by
`OTA-XC-BOOTSTRAP-BASE`. Independent review and the protected environment must
bind its canonical SHA-256. Never commit a descriptor purporting to contain its
own commit hash, infer approval from this README, or replace a failed ordinary
formal-base lookup with this source.

The target must be strictly newer and exactly pinned. Complete current Release
inventory is checked at execution. Existing-target retries are production-only
and retain the original rehearsal reference, asset/notes checks and every
P5/gate/environment requirement. All three newly generated assets, actual patch
application, remote readback, ready/idempotency and production-zero-effect
observations remain required. No such formal operation was performed here.
