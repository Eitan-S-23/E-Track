# Verified P51 Start-State Supplement

Protected artifact-only CI: 42004577880, attempt 1, artifact 13404502804.
Actual tooling/workflow source: `4fe8468a6276ab46e6fd4304c98a93da64d193b3`.
Branch: `dev/firmware/p51-packaging-20261104`.

The original compiled source remains
`1430c8ff7f3bcd9a35bfe158ba697b99021f75f2`, run 41900439548/1,
artifact 13359301400, timestamp 1793820855. This operation compiled no ARM
firmware, changed no finalized image, performed no reference search and did not
regenerate the 30319 target packages. Only the two missing initialization FULL
envelopes were produced under the original protected key binding.

| Initialization Asset | Bytes | SHA-256 |
| --- | ---: | --- |
| initialize-30317-full.etu | 291656 | c771eba2acd90fd2815611b9df53312a4cba4e9187c09fdd84efa5b70842724d |
| initialize-30318-full.etu | 291652 | fc25b7fb85bf0a963bafafe457cedea7e1ec7bcc9dee3cead3ff9d2805bf0734 |

`artifact.zip` is the unmodified 607722-byte GitHub artifact. SHA-256:
`020bbd5a50b5ce9400d27f686f987c0bfe04ee3cc7e2e37c00419c0939d6d6aa`.
`inventory.json` binds the archived original ZIPs, GitHub receipts, metadata,
source record and independent verification result. The artifact contains only
the two initialization ETUs, separate metadata and allowlisted evidence/inputs;
no Boot, target package, private header or decoder executable is included.

Root independently checked six areas: actual CI/artifact provenance; separate
original compilation and actual supplemental workflow identity; immutable image,
Boot and key bindings; exact FULL envelope hashes/headers/CRCs; eight real native
byte/negative checks with ten closed native process receipts and private cleanup;
and actual Linux credential-free regressions (66 Node, 25 Python). Native compile
and runtime warnings/errors are 0/0. All other firmware workflow jobs were skipped.
Repository, rehearsal and production gates remained false; protected environment
and branch policies matched the preflight snapshot. No protected key was exported.

Original source/artifact packaging evidence remains in
`docs/ota-exec-notes/P5-1-new-source-candidate-2026-11-05/`.
The installer commit includes only its reviewed install-method delta; unrelated
restore fixture work remains uncommitted and intact. Root retained both local
review failures and the corrected test-environment regression originals.

These are preparation assets, not a release or P5 hardware result. Fresh device
App/BCB/Boot/storage checks and ordinary OTA/Boot confirmation must establish
matching starts. Do not use cross-version App-only flashing or a restore fixture
without its preceding real backup. Initialization is excluded from four-cell,
30/30 and four-hour statistics. No physical action was performed to create or
verify this archive.
