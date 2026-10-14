# P4-2 Closeout Originals

This directory preserves the read-only environment-entry attempts and the
original independent scope/final review responses. It is not a deployed-cloud
acceptance bundle and contains no credential or authentication configuration.

`entry-inventory.json` binds 18 byte-identical originals, including the closed
Wrangler/curl process receipts and initial scope request. The `*.stdout.txt` and
`*.stderr.txt` suffixes avoid the repository's generic log ignore rule without
changing the original bytes. `.gitattributes` disables text conversion here.

Native curl CR/CRLF and Wrangler's trailing blank lines are preserved. A full
`git diff --check` therefore reports whitespace in three raw stream files;
authored Markdown is checked separately. Do not edit original logs to silence
that check. The initial checker failure remains in the local command records.

The original CI/test data remains in the adjacent `P4-2-ci-2026-10-14` archive;
it is referenced, not duplicated. Review provenance records identify the exact
original-session message timestamp and response hash. Scope approval is not the
final implementation verdict; see `../P4-2-acceptance-2026-10-15.md`.

`main-integration/` preserves main's exact CI metadata, full backend/governance
log ZIPs, fast-forward/push receipts and the scoped write audit. Its inventory
records the successful 156/156 native summary from the actual ZIP and the
App build/release/deployment skips. These are delivery checks, not an assertion
that real Cloudflare resources were deployed or that activation gates passed.
