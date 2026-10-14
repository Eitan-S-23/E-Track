# P4-2 Development Evidence

These are original development CI/local test records, not a formal acceptance
bundle or proof of deployed Cloudflare state. `inventory.json` binds the exact
copied bytes and records all three native runs, including both failures.
The directory-local attributes preserve those bytes in Git.

- `4413bf9`, run `38588241206`: native tests 144 passed, six failed.
- `9b2af3e`, run `38590614768`: the six product failures passed; the new R2
  oracle was wrong. Native tests 155 passed, one failed.
- `fc4fbbb`, run `38591559979`: Public/Admin/Worker jobs succeeded, native tests
  156/156. All source fixes and the corrected negative oracle are present.
- `p42-r2-etag-final-host-01`: latest local complete suite 190/190, including
  real SQLite migration/script tests but disclosed in-memory platform doubles.
- `independent-r2-review.md`: original non-implementing reviewer approved the
  bounded repair. It did not adjudicate the final native CI run or formal P4-2.

The task record in the parent directory explains scope, authorization, failures,
root cause, source identity, independent review and outstanding real-data/account
observations. JSON command receipts preserve exit codes; do not add counts from
overlapping test runs or label the copied originals as new executions.
