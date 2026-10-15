# P4-1 Readiness Development Evidence

This is development evidence, not a formal acceptance bundle. P4-1 remains
IN_PROGRESS. Native cloud binding qualification, canonical rehearsal, complete
production-zero-effect observations and whole-card independent acceptance remain
NOT_RUN. No main merge, Release/tag, protected configuration mutation or device
operation is represented by this archive.

## Identity And Originals

- Branch: `dev/p4-1/unattended-20261015`, draft PR 27, pending integration.
- Tested source: `18c4da4d28c1f2bcf7175f4b461e2a6bf462a23e`.
- Actual PR checkout: `5b1c50f526f0edf90884b58c1c321593b7db0d1f`.
- Both trees: `5a6977eeace9ea96668f800b50e02b259bfcfe45`.
- Observed main: `b42d3e25db85d6aba397cb4d0fb34bb5b653904f`.
- Original inventory: `inventory.json`, SHA-256
  `61c2710ad57e32bce8445de6bccbf36113f32e61616a6245c55dae176e2a7068`.

The 98-file original archive is 8,059,081 bytes, including the inventory itself.
Its 97 entries cover byte-preserved originals, selected byte-identical metadata,
derived inspections and historical helper snapshots. This README and later
closeout annotations are outside that immutable original inventory. Historical
helpers describe their original `.cache` invocation locations; do not run them
from the archive or treat them as a new acceptance runner.

`github/` retains all four raw Actions log ZIPs, source/PR/job/run API responses
and eight artifact ZIPs. Every artifact's full length and SHA-256 matches the
authenticated GitHub listing. `artifact-members.json` binds every member's bytes
and explicitly labels its ZIP timestamp. `ci-inspection.json` records the exact
oracles, separate test counts, compiler diagnostics and artifact identities.

## Actual CI

| Workflow | Run | Result |
| --- | --- | --- |
| MCU Firmware Build | 38788072495 | SUCCESS |
| Cloudflare Update Service Checks | 38788072597 | SUCCESS |
| Acceptance Governance | 38788072424 | SUCCESS |
| Build APK and EXE Release | 38788072457 | SUCCESS; path detection only |

Separate tooling suites passed: script/migration 34, pipeline host 134, native
workerd 156, workflow/Bash 57, real byte preparation 22, pack 8 and golden vectors
9. The backend's additional 156 native tests are a repeated suite, not 156 extra
distinct cases. Governance counts are 127/36/3/14/11/62/39/29; the two Flutter
helper jobs each ran 17 host tests, not Flutter compilation or device operations.

Both the ordinary and key-bound development GCC builds succeeded. Each actual
compiler/linker step contains 640 warnings and zero errors; the separate vendor
tool build contains six warnings. Expected negative host-test diagnostics are
retained, not counted as compiler errors or hidden as failures of the whole job.

The keyed build's actual CMake cache disables the compiler cache; the captured
Ninja rules have no cache launcher. Its App key compile command, header/source
fingerprints and packaged input agree. Both GCC full/recovery paths recover
byte-identical finalized Apps; the synthetic three-asset fixture also verifies
patch equality. All are explicitly development-only and `r2Verified=false`.
No formal package, device compatibility or cloud qualification is inferred.
The existing Boot is not an AES consumer; its bytes match across both builds.

The workflow's separate cleanup step reports `privateBuildKeyAbsent=true`, and
none of the eight artifact ZIPs contains `private-key.h`. The private build tree
is not an uploaded artifact. Binding qualification, rehearsal and production jobs
were skipped, as were App/EXE builds, GitHub Release and Pages deployment.

## Local Review And Remaining Inputs

`commands/` retains 15 closed local receipts and their original streams, including
the final 134/57/22/23 self-test counts, Worker typecheck and scoped stage/commit.
Earlier staged passes are preserved separately, not added to the final counts.
The preflighted label `p41-ready-gov-r2` was not run and has no invented receipt.

`observations/independent-development-review.json` preserves the reviewer's key
cache/cleanup closure and its subsequent decision-record message. That message
explicitly separates prior verbatim excerpts from reconstructed summaries; the
old GOV-ENTRY message is not available verbatim and is not fabricated. Neither
message is whole-card acceptance or retrospective review of the new CI results.

`observations/read-only.json` and the environment API response preserve the real
configuration gap: no GitHub environments, no variables and no firmware rehearsal
or OTA secret. The local provisioning token was active; policy GET 403 did not
make it invalid. No token value is included or exported to CI.

Owner input is still required for a production-free Cloudflare test account,
reviewed target/fixture rebinding, protected environment preparation and an
approved non-development OTA key. Exact target/descriptor approval must use the
real keyed candidate, not the earlier probe. Preserve the original 3.2.7 bootstrap
archive and the device owner's later key-provisioning responsibility. A main
merge and a second key-hash approval variable are not prerequisites to invent.
Do not start the new whole-card acceptance agent before actual setup is ready.

## Closeout Records

The separate `closeout-inventory.json` binds the archival command receipts,
23-test documentation regression, output audit and its selected-path/incident
record. It does not modify the 97 original inventory entries. The audit verified
7349 existing selected entries, scanned 927 ZIP members, found no private header
or supplied credential value in the evidence, and confirmed the unchanged
shared-root index. Historical P41-AUDIT-01 remains attribution-unresolved.
The bounded transport failures and owned empty `20)` cleanup are explicitly
recorded; no partial artifact or planned-only command is labelled successful.
