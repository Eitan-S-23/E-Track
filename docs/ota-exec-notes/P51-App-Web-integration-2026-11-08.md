# P51 App Web Main Integration

## Delivered Scope

PR [34](https://github.com/Eitan-S-23/E-Track/pull/34) merged as
`e6d28e3fb6718fb2ee467bac9d944cc0aedc024c`, tree
`9578c41f850daf09cd17fddb27ff9cfd6c43fd7a`. Its reviewed delivery commit is
`4e0717770f0fe4c04803f2e2d1d29f9eae75c7a2` and preceding main is
`df1db7515a8c16adbedbc23f4ed6af7b2b565a31`.

Only eight reviewed endpoint/proxy/Admin code, test and documentation blobs,
plus sixteen sanitized evidence/document files, were integrated. The original
test branch was 52 commits ahead and one behind main; it was not merged wholesale.
Main keeps App version `1.0.71+97`; the test APKs and their source commits retain
their separate identities. No MCU source, package, frozen P5 bundle or App
version was changed by this delivery.

The [independent report](P51-App-Web-2026-11-08-review.md) concludes
`SCOPED_REVIEW_PASS`, with no blocking finding for this bounded App web scope.
It checked the original source/491 inputs, both complete APK/R2 identities,
signature/tamper cases, nine real website mutations and four screenshots;
29 additional host checks passed. Original website operations, successful
upgrades and prior CI builds were not repeated.

## Actual CI

| Scope | Cloudflare Checks | App Path Detection | Governance |
| --- | --- | --- | --- |
| PR | 42407977036 | 42407977038 | 42407977045 |
| Merged main | 42408571980 | 42408572025 | 42408571962 |

All six completed successfully. Main notification run `42408572062` also passed.
Both Cloudflare runs executed 54 Admin UI tests and 283 Worker tests. The original
test branch's 288 Worker tests include five pending P51 firmware-selector tests;
that number is not attributed to this narrower main-based delivery.

Both App workflows ran path detection and explicitly skipped APK, EXE, GitHub
Release and Pages deployment. No new build, release, service deployment or device
action was requested. The two original test Release/asset inventories were
unchanged before and after merge. Do not redeploy the isolated Worker from this
main as an incidental closeout step: its live P51 selection changes have separate
pending firmware provenance.

Original downloaded CI logs and receipts are retained in
`P51-App-Web-2026-11-08/integration-ci.zip`, with hashes and diagnostic counts in
`P51-App-Web-2026-11-08/integration-result.json`. Warnings, expected negative-test
errors and diagnostic text remain intact; successful jobs do not mean empty
warning/error logs. No new test run was needed to archive these originals.
The first offline archival parser rejected GitHub's literal escaped ANSI text;
its failure is preserved in `p51-closeout-20261108-01/record-01`. Correcting that
log normalization does not rerun a CI test or website operation.

## Limits And Next Work

This closes the scoped remote-main App web delivery, not P5 or production
qualification. Local `main` is a different worktree and is not claimed updated.
Its shared Git metadata and worktree are outside the active writable root;
neither was modified by this delivery. Phone self-update was not tested here.

The old P5 v12 EVIDENCE_GAP bundle remains immutable. Existing four-route
functional observations keep their actual target versions; they do not prove
four literal final-30321 installs. First30, real four-hour duration, physical
fault cases and production gates remain open. The next bounded implementation
uses the recoverable 30320/30321 pair, a separate benchmark-only HTTPS fixture,
a release-mode verification APK and capacity-aware sealed recordings. It must
not replace normal packages or repeat completed SD observations.

All controllable local outputs are under
`D:/github/my/E-Track/.cache/p35-integration-20261028/source`.
Original App-window 13-path and reviewer-window five-change shared-cache
observations remain disclosed with UNKNOWN attribution in the original reports;
overlapping counts are not summed and no external cleanup occurred. The bounded
root delivery/merge/CI snapshots reported no changes in their individual windows,
not a whole-machine clean-boundary claim. Final record receipts retain the
continuation audit and process-closure checks.
