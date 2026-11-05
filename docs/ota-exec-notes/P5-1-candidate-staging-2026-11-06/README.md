# P51 Immutable Candidate Staging

PROTECTED_STAGING_DELIVERY_REVIEW_PASS, independently verified by root.
This preparation result is not P5 physical acceptance or production approval.

Actual delivery source: `7a5bf6058dbdbc1c5c64a79dec3b0df765985be3`.
Workflow `firmware-build.yml`, run `42093030305`, attempt 1, succeeded in the
existing protected `firmware-rehearsal` environment. Approval was the user's
delegated root action, not a claimed human click. Only the staging job executed;
six other jobs were skipped. All gate values and reviewer/branch rules stayed
unchanged. Original compilation remains source
`1430c8ff7f3bcd9a35bfe158ba697b99021f75f2`, run `41900439548/1`, artifact
`13359301400`, build timestamp `1793820855`.

Artifact `13447170644`: 1682251 bytes, SHA-256
`1ac066b1f5948c35bf3d88239eab59bf770517a5e400d7540aae9df33773e3c5`.
`artifact.zip`, `workflow-logs.zip`, provenance, API receipts and the independent
result are preserved here and bound by `inventory.json`.

## Actual Outcome

The original 291700-byte FULL, 1048576-byte PATCH/reference and 615140-byte
recovery were uploaded unchanged. Each complete readback preceded the single
successful registration. Release
`fw_cac2b99e842cc9407b9677ead0c2efeda601e4781242c4928cd2128df219965b`
is ready on isolated staging, with the exact target image and three available
assets. It is not attached to any channel. Stable72 and beta11, including their
complete channel states, are unchanged. The other 28 release records are also
unchanged. No GitHub Release/tag was created.

The original artifact-candidate metadata remains nonformal and immutable. The
separate registration description uses the backend's required formal schema;
it does not establish production eligibility. The independent evidence keeps
`productionPublishable=false` and `approvalEligible=false`.

## Verification And Failure

Root verified 268 distinct original host tests and ran six final-source targeted
tests before integration. Actual Linux CI ran 56 Node and six Python tests,
all passing. Root then performed 38 actual-output/provenance/backend checks,
including byte comparison against the original candidate archive, canonical
metadata parsing and post-delivery policy checks. See `verification.json`.

No compiler ran in this delivery. CI retained three action/runtime deprecation
warnings: DEP0040, DEP0169 and the Node20-to-Node24 action warning. No error was
reported; the Git default-branch hint is not counted as a compiler warning.

The first direct download stopped at 768996 of 1682251 bytes after its 180-second
bound. Its process tree closed; original partial bytes and the timeout receipt
remain under `failure/`. A subsequent GET of the exact same artifact ID/digest
used the existing local proxy route and verified the complete archive. No CI,
upload, registration, device operation or initialization was replayed.

## Remaining Scope

Root next binds actual latest/download selection and the SD/BLE observation and
restore commands, then freezes the P5 execution contract and matrix. Four
combinations, same-group30/30 and the real four-hour campaign remain NOT_RUN.
The last verified device state is 30317 CONFIRMED with backup30313. Do not use
the later30319-to30317 restore fixture until the real preceding OTA created its
matching backup. No current phone/device state was observed during staging.

All selected local outputs stayed in the authorized integration worktree.
Only explicitly authorized task Git metadata was changed outside that worktree.
Main-worktree index/config/HEAD, unrelated dirty files and historical assets were
preserved. This archive does not alter a frozen acceptance bundle.
