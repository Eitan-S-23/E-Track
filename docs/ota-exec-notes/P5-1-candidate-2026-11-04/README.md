# P5-1 Protected Candidate Preparation

This is preparation evidence, not a frozen P5-1 acceptance bundle or release.

- Reviewed packaging source: `446b0a99b8538714be7e54e640eeb6e58658e76b`.
- GitHub run: `41778918087`, attempt 1, successful artifact-only execution.
- Artifact: `13298118510`, 3082312 bytes, SHA256
  `121e8e26ee8171b017d81ca163cc40387f2bde168bdb82fb349aca5af54ee446`.
- Candidate: 3.3.16 / 30316; exact 30313 base and external approved group16 Boot.
- Linux checks: 10 Python and 23 Node tests; native decoder positive and four
  rejection cases. Native compile: zero warnings and zero errors. No MCU rebuild.
- Independent owner: six original-artifact checks passed, including hashes,
  fw_header/recovery, ETU CRC/base fields, exact 1 MiB reference alias, native
  source/results, stage receipts, protected-key execution and private cleanup.

`artifact.zip` and `workflow-logs.zip` are exact GitHub downloads. `provenance.zip`
contains root operation originals, input/run/approval/policy records and exact
review script versions under their original worktree-relative paths. Its index
hash-binds every member. `review.json`, `github-artifact.json` and `index.json`
are the local review, original GitHub metadata and archive inventory.

Two owner-side inspection errors are preserved: isolated Python initially did
not expose installed PyCryptodome, and an unnecessary line-ending normalization
changed the hash comparison for a CRLF source. Corrected inspection consumes the
same unchanged CI archive and exact source bytes. No CI/OTA was repeated.

The user delegated the protected-run approval to root. This was not a human
approval click. One exact branch policy was added; existing reviewers and all
three boot-chain gates remain unchanged. There was no cloud firmware registration,
production publication, key export, device operation or new installed firmware.

Next: P51-EXECUTION-03 must bind the supported complete-state base restoration,
SD package placement and product UI, BLE latest/download endpoint and collectors,
then freeze the actual four-cell and same-group 30/30/four-hour schedule. Existing
P3-5 evidence must be assessed for parameter applicability before any repeat.
Do not use an App-only downgrade across changed BCB state, count preparation as
hardware PASS, replay P1-6, or erase the six unresolved electrical power-cut cases.
