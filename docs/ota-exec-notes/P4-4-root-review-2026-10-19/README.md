# P4-4 Root Review And Configuration Preparation

Source: b56534d7b6c993c0795010d0404fb8a81f7eeb9d.
Implementation evidence: 15be25e593405396d8db8fb0011fc62e42d6d27d.
Branch: dev/p4-4/config-integration-20261018, pending main integration.

This archive is not a frozen P4-4 acceptance bundle. Formal rounds remain zero;
the review, development CI and configuration deployments are not formal PASS.
See [the root report](../P4-4-s3-preacceptance-2026-10-19.md) for findings,
the corrected deployment incident and the precise outstanding owner input.

`raw-output-inventory.json` binds every selected source and public copy by byte
length and SHA-256. `byteExact=true` means an unchanged original. Other entries
explicitly enumerate account-identifier, email, response-cookie or URL-query
redactions. Their original hashes and project-relative locators are retained;
those projections must not be misrepresented as byte-identical originals.
The original files are not edited. Private inputs/configuration, caches, home,
temporary directories and redundant build trees are not published.

`review/` retains the original defect reproductions and delivery reconciliation.
`preparation/` retains successor review, actual rejected token creation,
read-only platform/D1 observations, CI module input, deployment and restoration
receipts, raw module readbacks, failures and current admission metadata.
`helpers/` includes the reused output guard. Archived scripts retain their
actual source bytes and historical local input paths; they are documentary
inputs, not authorization or a portable runner to execute again. In particular,
do not replay deployment, token-creation or old defect-reproduction commands.

Worker code was deployed to both approved targets and independently downloaded
for exact CI-byte comparison. No firmware publication, new-chain rehearsal,
registration, channel mutation, R2 object write or device operation was performed.
Both actual token-creation endpoints returned 403/code 9109. The final successful
read-only GitHub refresh still finds all four S3 secret names absent and all
three boot-chain gates false. The existing reviewer must perform the later real
P4-4 rejection and approval; the P4-1 delegated exception is not reused.

The controlled-output audit is bounded to the inspected commands and selected
paths, not a machine-wide write trace. Known external PowerShell-cache timestamp
attribution remains unresolved; no external cleanup was performed.
