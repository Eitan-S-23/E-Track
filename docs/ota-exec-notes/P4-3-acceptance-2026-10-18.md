# P4-3 Independent Acceptance

Latest result: **formal PASS**, contract `P4-3-v1`, round
`P43-20261018-01`, all seven required criteria satisfied. Input freeze:
`1ddd948bbf7d0dc2097c14d87def767314342f8f`; product source remains 0067b6c.
See the final formal-result section and `docs/acceptance-contracts/P4-3-v1/`.
The pre-review/NOT_RUN statements below are dated history, not the latest result.
No new deployment, main merge or production-role certification is claimed.

Latest review: **P43-ACCEPT-02 CLOSED / remediation re-review PASS** on
`0067b6c3caa9ee263c53ae372fdc63cc7f74250f`, delivery
`21f5b89bddb6b5e823909d237724f8dc448e9dd5`. See the final re-review section.
The original PRODUCT_FAIL below is historical and remains preserved byte-for-byte
in the new review increment. Whole-card formal acceptance remains NOT_RUN;
this is not a deployment or main-integration result.

Review ID: `P43-REVIEW-20261018-01`.
Reviewer: Codex, the user-assigned non-implementing P4-3 acceptance session.
Disposition: **PRODUCT_FAIL**, one required product correction, `P43-ACCEPT-02`.
Task status remains IN_PROGRESS; the implementation owner is unchanged.

This is the concentrated pre-review and original-evidence reconciliation required
by acceptance execution contract sections 0.1 and 7.3. The known blocker prevents
formal admission. Formal execution and final bundle validation are **NOT_RUN**;
no FROZEN contract, formal PASS, REUSED origin, bundle commit or freeze-index entry
has been fabricated. There is no earlier P4-3 formal bundle in FREEZE-INDEX.
The sole Spec remains `docs/ota-prompts/prompt-P4-3-implementation.md`.

## Inputs And Boundary

| Input | Identity |
| --- | --- |
| Active writable worktree | `D:/github/my/E-Track/.cache/p4-3-implementation-20261017` |
| Branch | `dev/p4-3/admin-controls-20261017` |
| Delivered implementation baseline | `a96aa03da14a912aaf783d875d6a379846c21289` |
| Product candidate | `972e74c43cd36b7a308e457296aaf7bb06120e78` |
| Local evidence commit / review HEAD | `08277242b3326541b27f306aee16233cd344ea95` |
| Review HEAD tree | `9e9fd6ceb612e638ba153ec3eb978ec8e225e341` |
| Profile configuration blob | `bb590b65c20e600bfa4748e64ed46b88b6f400d4` |
| Original native CI | `39084376785/1`, exact product candidate |
| Original isolated deployment | `406adf06-caf4-49b6-a83d-9554ba393da1` |

The canonical root rules, task-worktree rules, collaboration index, P4-2 handoff,
sole Spec and applicable frozen OTA-XC clauses were read. Root/worktree differences
in the execution contract consist of the P4-1-only delegation section; that grant
is not reused. The task worktree contains the newer published P4-1/P4-2 index
entries. The dirty shared root and local main were not modified. No `.trellis`
directory exists here, so no replacement task/Spec was created.

Read-only GitHub API receipts at `2026-10-18T02:54:53Z` through `02:54:57Z` confirm
remote main is `a96aa03...`, the task branch still points to `972e74c...`, and CI
39084376785 is completed/success at that same candidate. Thus `0827724` is actually
local-only, not merely an outdated remote-tracking-ref assumption. This review did
not push it or infer commit/push/deployment authority from the acceptance request.

## Required Finding: P43-ACCEPT-02

**DECIDED: P2, required product fix.** This is an unknown-result lifecycle defect,
not a failure of the repaired shared-cookie CAS path and not an Access bypass.

Entry: `admin/public/index.html`, `runFirmwareReleaseAction`, line 5215:
every HTTP error below 500 unconditionally clears `state.firmwarePendingAction`.
The retry path at lines 5167-5177 has not established the original outcome merely
because a later replay was rejected by authentication, CSRF, authorization or
rate limiting. Its following successful GET refresh clears the other write lock.

Reproduced sequence using the unchanged actual UI functions:

1. A recovery request commits, but its response is lost. The UI correctly retains
   the original actor, body and Idempotency-Key.
2. The operator explicitly reconciles that request. Reads occur first, and the
   identical key/body are submitted, but this replay receives a JSON 401, 403 or
   429 before its durable result is returned.
3. The catch clears the pending request. A successful state refresh cannot reveal
   whether the earlier recovery capability was issued. Nevertheless both locks
   are now gone.
4. Another operator confirmation generates a new key and can issue a second
   recovery capability for the same unresolved intent. The original key is no
   longer available through the UI. This is not an automatic second POST: the
   defect permits it after an additional confirmation while losing reconciliation.

Basis: the sole Spec's unknown-result/release-action requirements,
`OTA-XC-ADMIN-IDEMPOTENCY`, and the UI's explicit requirement to reconcile the
original request before another release action. A replay's pre-business rejection
is not evidence that the original transaction failed. Do not infer its outcome
from release state, reason, requestId or an unrelated successful GET.

The bounded offline probe extracts `setFirmwareData`, refresh/failure handling,
`runFirmwareReleaseAction`, `mutate` and `api` directly from the current HTML.
Transport/dialog/render dependencies and small role/ready/UUID fixture helpers
are simulated; this is not a browser integration test. It uses no real token,
network, browser, D1, R2 or device. It reports **4 failing scenarios and 2 passing
controls**, exit 1:

| Replay response | Pending key retained | New key accepted / durable mock effects | Oracle |
| --- | --- | --- | --- |
| 401 TOKEN_EXPIRED | No | Yes / 2 | FAIL |
| 403 CSRF_INVALID | No | Yes / 2 | FAIL |
| 403 ROLE_FORBIDDEN | No | Yes / 2 | FAIL |
| 429 RATE_LIMITED | No | Yes / 2 | FAIL |
| 503 BACKEND_UNAVAILABLE | Yes | No / 1 | PASS control |
| 409 IDEMPOTENCY_RESULT_EXPIRED | No | Yes / 2, separately confirmed | PASS control |

Preferred correction: distinguish a first request's definitive rejection from an
unresolved original request's reconciliation. Preserve the pending actor, exact
body and key, and block unrelated/new-key actions after pre-business or uncertain
replay failures. Release it only on a validated definitive outcome, including the
explicit expired-result branch that permits a newly confirmed intent. Do not
weaken CSRF/Access, auto-replay writes or replace the key on session refresh.

Next owner: P4-3 implementation agent. Add the missing interrupted-reconciliation
cases beside the current unknown-release tests in
`admin/test/firmware-ui.spec.ts`. After restoring auth/CSRF, an explicitly confirmed
same-key replay must return the original URL/requestId with exactly one effect.
Keep the 503, expired-result and changed-actor controls. Rerun this source-reading
probe and affected UI tests, then obtain source-bound native CI for the repaired
batch under actual existing authority. No product fix was authored by this reviewer.

## Existing Evidence Reconciled

All six development archives were independently listed and every entry was
extracted to stdout for size/SHA-256 verification: **1,199 archive entries** in
total. This is a count across increments, not 1,199 distinct experiments. The
latest increment has 585 entries, 25,197,295 bytes and SHA-256
`865730da8d32bba4de6cab9cc821639c8b41638f8e119928e3cd4f0eadef942b`.
Its 220 local drill-file copies also match the archived bytes. An altered-byte
negative was rejected. No archive or historical failure was changed.

| Area | Independent observation |
| --- | --- |
| Native CI and checked input | Original ZIP/logs, workflow metadata and serving manifests agree on candidate 972e74c: Worker 270/270, mock UI 12/12, compiled router 3/3. This review re-evaluated originals, not reran those tests. |
| Deployment reconciliation | The saved original platform JSON matches the independent readback digest, source and successful deployment ID. Before/after/readback configurations are identical and bind only the named test D1/R2. The original CLI null exit/SIGTERM remains a failure receipt; no second deployment was sent. |
| Live owner and served bytes | Saved session status 200/owner, actor hash and response requestId agree. Saved served HTML matches the checked CI HTML SHA-256. This does not establish real publisher/viewer sessions. |
| Original HTTP and D1 | 55 raw D1 responses, 53 sanitized snapshot projections, 54 Admin request/response originals and 18 public response bodies were independently reconciled. Private values were not printed or repackaged. Successful D1 SELECT receipts have zero rows written and changed_db=false. |
| Audit/state chain | 24 channel changes, 3 recovery issuances and 1 disable match unique successful original responses, reasons and actor identity. Both revision chains are continuous. Original audits remain unchanged; matching release-action result rows are completed with the specified retention/expiry. |
| CAS and cancellation | Both repaired stale-tab requests really returned CAS_CONFLICT/409, with no loser state/audit change. The cancellation before/after snapshots are identical. The drill-05 403-versus-409 product failure is retained, not relabeled. |
| Selection and stop flags | Both channels' low clients select 20801, upgraded 20801/30208 clients get NO_UPDATE, and the identical old URL is served or rejected according to independent flags. Successful binary bytes match asset size/digest, not merely HTTP status. |
| Recovery and final disable | Actual recovery bytes match the asset; the same URL later returns TOKEN_EXPIRED/401 and the original key returns IDEMPOTENCY_RESULT_EXPIRED/409. Conditional low disable/replay/new-key rejection leave one effect. Backfill/reference checks precede the disable. |
| Final recorded state | At drill-06 completion, stable revision 13 and beta revision 11 both point to high 3.2.8 with both stops set. Low 2.8.1 is disabled. High identity and all six asset rows are unchanged. These are timestamped historical observations, not a fresh live-state assertion. |

All nine original probe/drill outcomes, including setup, transport, collector and
product failures, remain explicit in the offline output. The evaluator also
rejects a modified final stop flag and an unbound audit requestId. It does not
execute the original live collector or treat its summary PASS as the oracle.

All 21 declared screenshot hashes match. Five were visually inspected: English
cancel confirmation, Chinese retract success, English CAS conflict, Chinese fresh
confirmation, and Chinese final state. Wording, fresh empty reason, revisions,
stop flags and masked identities agree with the original HTTP/D1 records. No new
screenshots or mock-as-live images were created.

## Remaining Limits

- Real publisher/viewer Access sessions remain absent, as explicitly allowed to
  remain a disclosed gap in LIVE-02. Signed-fixture API tests and mock role controls
  do not prove the full deployed role matrix. Do not fabricate those identities,
  borrow owner results or silently close P4-4/production configuration obligations.
- Inherited dependency findings are retained: Admin/Public 4 high each; Worker
  8 high and 3 moderate. The inspected source/dependency reachability analysis is
  not a risk waiver. Root still owns a separate assessed dependency update.
- Current CI originals contain 24 npm warning lines across four jobs, two Actions
  warning annotations and four expected native negative-test exception lines.
  Drill-06 has two browser error lines corresponding to the expected HTTP 409s.
  This is not a warning-free result.
- The previously reported Cryptnet cache exception remains open. The four exact
  files below were inspected read-only, not cleaned, moved or overwritten. One
  metadata timestamp advanced after the prior report; attribution remains unknown.
- Local evidence commit 0827724 and this review are not delivered to main. Remote
  synchronization and eventual commits/bundle-index closeout remain root-owned
  actions requiring their actual authorization.

### Read-Only CRL Follow-Up

Base: `C:/Users/SU/AppData/LocalLow/Microsoft/CryptnetUrlCache/`.
Observed at approximately `2026-10-18T02:39Z`:

| Relative path | Bytes | UTC mtime |
| --- | --- | --- |
| `Content/ABD721CDC3648033BA8C827AF15A4543` | 309 | 2026-10-18T01:02:18.774Z |
| `MetaData/ABD721CDC3648033BA8C827AF15A4543` | 192 | 2026-10-18T02:03:16.368Z |
| `Content/B6E4D06BF128A1673A8DAFB4E25B990D` | 308 | 2026-10-18T01:03:00.875Z |
| `MetaData/B6E4D06BF128A1673A8DAFB4E25B990D` | 192 | 2026-10-18T01:03:00.875Z |

The earlier report recorded the ABD metadata at 01:02:18.777Z. The newer timestamp
does not prove which process refreshed it. This session used cmd.exe and
Node/OpenSSL for its public reads, not PowerShell, native curl/Schannel or a browser.
No cache cleanup is recommended without path-specific user authorization, and no
machine-wide zero-external-write or exclusive-causation claim is made.

## Commands, Delivery And Next Step

The existing `.cache/p43-run.cjs` adapter supplied contained logs, receipts and
TEMP/home/cache overrides. The archive and CI inspectors were reused. The two new
bounded scripts only interpret original data or execute original UI functions
against synthetic transport; they do not replace any production protocol/tool.

| Receipt label | Executed command after the existing adapter | Exit |
| --- | --- | --- |
| `p43-acceptance-ui-reconcile-01` | `node .cache/p43-acceptance-20261018/ui-reconcile-probe.cjs` | 1, product oracle failure |
| `p43-acceptance-archives-01` | Recorded inline Node assertions and `tar -tf`/`tar -xOf` for all six inventories | 0 |
| `p43-acceptance-ci-01` | `node .cache/p43-evidence.cjs inspect-csrf` | 0 |
| `p43-acceptance-originals-01` | `node .cache/p43-acceptance-20261018/inspect-originals.cjs` | 0 |
| `p43-acceptance-identity-01` | Recorded inline Node assertions on original deployment/session/served bytes | 0 |
| `p43-acceptance-platform-01` | Recorded read-only Node/OpenSSL GitHub API requests for task/main refs and CI identity | 0 |

Exact commands, timestamps, exit codes, raw outputs and diagnostic source are
preserved in `P4-3-acceptance-2026-10-18/review-originals.zip` and its inventory.
The review archive contains 14 byte-verified entries, 18,497 bytes, SHA-256
`81efe70aaf1c35c70584c882ec5fbd84feefc390ef7154484bfcda5f0dc85092`.
It is a diagnostic review archive, not a v3 formal acceptance bundle. The local
probe's source bytes use the existing checkout line endings; normalizing CRLF
confirms exact equality to the source-bound CI HTML, without editing either file.
Both new scripts pass `node --check`. No whole host suite, native CI, build,
deployment, live mutation, recovery issuance, asset deletion or device operation
was repeated. No sub-agent was delegated. Product files were not edited.

All actively chosen writes are confined to this worktree: the two diagnostic
scripts under `.cache/p43-acceptance-20261018`, prefixed receipts/logs under
`.cache/p43/logs`, this report/evidence directory, and scoped additions to the
existing implementation issue table and P4-3 board/log. Output guards checked
directory boundaries and existing parent reparse points before writes. Shared Git
metadata was not intentionally written; its index mtime remains 01:48:21.801Z,
matching the pre-review evidence commit, and the staged diff is empty. This is a
bounded path/timestamp audit, not a machine-wide write trace. All 22 selected
output/edited paths passed the final directory-boundary and reparse-point audit;
no new project-external write was identified in this bounded audit. No
project-external cleanup was performed.

Next: implementation addresses P43-ACCEPT-02 as one batch, retaining this failed
probe and adding affected browser regressions. The independent reviewer then
checks the entire remediation batch and formal admission. Historical successful
cloud observations remain available as hash-bound external inputs under section
0.1, not fictitious REUSED formal PASS entries. Re-evaluate applicability and only
obtain genuinely missing/changed observations; do not replay the completed cloud
campaign, re-enable the low release or silently issue more recovery URLs. Formal
contracts, input/profile gates, negative oracles and bundle validation remain
required before whole-card PASS and authorized closeout.

## P43-REVIEW-20261018-02: Independent Remediation Re-Review

Disposition: **DECIDED PASS for P43-ACCEPT-02**, independently closed on the exact
repair commit 0067b6c. No additional required product finding was identified in
this bounded remediation review. This does not turn the implementation's runs
into independent executions or declare the complete card formally accepted.

The user explicitly resumed this same acceptance thread with repair/evidence
commits. The active root remains
`D:/github/my/E-Track/.cache/p4-3-implementation-20261017`. HEAD is
`21f5b89bddb6b5e823909d237724f8dc448e9dd5`, tree
`9b780073354d2e9bf37d61e4ede44572682f0fd0`. Existing reviewer edits were present
at entry and preserved. Only the HTML and its browser test file changed between
0827724 and the product repair; the evidence delivery adds records, not product
inputs. The source/configuration subtree is clean against 0067b6c.

### Finding Closure And Actual Checks

The repair keeps the original pending actor/path/body/key when a reconciliation
receives authentication, CSRF, role, rate-limit, backend, conflict or state errors.
Reads cannot unlock that unresolved intent. Only a validated result, or a
correlated 409 IDEMPOTENCY_RESULT_EXPIRED for the pending path, resolves it.
Definitively rejected first requests still allow separately confirmed intents.
Firmware error envelopes must contain valid error fields and matching nonempty
body/header requestIds; wrong-status or uncorrelated expiry does not unlock.
No Access, role, CSRF, CAS or server idempotency condition was weakened.

| Independent check | Actual result |
| --- | --- |
| Original source-reading probe, unchanged SHA-256 `a90152a6c9edaffeb215742cbcdd86aafe1ec4527cec514fe8032c58ea728523` | Re-executed by this non-implementer: 6/6, exit 0. All four former 401/403/429 failures retain the original request and prevent a new key; the 503 and explicit expiry controls still pass. No network/browser/cloud operation. |
| Development increment `accept02-01.zip` | All 158 entries, listing, sizes and extracted SHA-256 values independently verified. Every corresponding local copy matches. Archive: 42,197,684 bytes, SHA-256 `751c8c7b989a913a4dda9212da81ba8a6103c86459ce702d4e716b53dc7d845d`. |
| Prior evidence preservation | The six previous development archive hashes and the original review archive hash still match. They were not rebuilt or replayed. An altered-input negative was rejected. |
| Native CI original ZIP/artifacts | Run 39098302062/1, source 0067b6c, four successful jobs: Worker 270/270, mock UI 36/36, compiled router 3/3, typechecks. Actual logs, checkout marker, source/run manifests and all serving hashes agree. This is independent evaluation, not a new CI run. |
| Windows timeout follow-up | Original full run remains 34 PASS / 2 timeouts. Recorded targeted commands cover exactly the English retract test and disable/wrong-status-expiry test, each 1/1, at 13.9s and 15.9s under an explicit 60-second bound. This is not relabeled as a 36/36 Windows full run. CI passes all 36 with its unchanged 30-second bound. |
| Server and UI applicability | Git proves unchanged Worker, Pages functions, public service, migrations, scripts, package locks and workflow/config inputs. Compiled facade difference is only one Wrangler-generated temporary-path comment; executable text and routing bytes are identical. Outside `runFirmwareReleaseAction` and `api`, the checked old/new HTML is identical. |

The 24 added browser cases retain the original 12 cases. Both release actions
exercise ten interrupted-replay responses twice, with intervening manual reads,
then explicitly retrieve the same requestId/URL with one durable mock effect.
Four controls cover definitive first-request rejection. This addresses the
original finding across both callers rather than merely satisfying its six-case
diagnostic. These fixtures are not represented as real publisher/viewer sessions.

At `2026-10-18T06:23:48Z` through `06:23:50Z`, read-only GitHub API responses
confirm the task branch is at 21f5b89, the successful CI is at 0067b6c, and main
remains a96aa03. The former local-only 0827724 evidence is now an ancestor of the
pushed delivery. No fetch, push, commit or main update was performed here.

The new checked HTML is 266,118 bytes, SHA-256
`1a5feb4ffb04bf164c139cc1f221baabee3296ca51caf6f02f4e3c13411a0a58`.
The checkout matches it after the already-established Git line-ending
normalization. The new facade is 107,859 bytes, SHA-256
`ba966cfd178dce339de9d211e631da78663503b5c7ae0dd463c62163bed18d90`.
The real deployment was not updated; its last recorded source remains 972e74c.
Therefore the UI fix is verified in source/CI, not claimed live at the isolated
Admin origin. The old real CAS/stop/download/audit observations remain historical
inputs with their original source/date, not current-UI execution evidence.

### Receipts And Preserved Limits

New exact command records and raw outputs are
`.cache/p43/logs/p43-review02-{probe,ci,evidence,compatibility,remote,preserve}-01.{json,log}`.
They are packaged in `P4-3-acceptance-2026-10-18/review02-originals.zip` with
`review02.inventory.json`: 13 entries, 17,116 bytes, SHA-256
`2c80e9b45524d654eb09859e83e6d2233fbf63b23d15502aa6cb98b848e35243`.
The existing tar route verified the listing and every extracted entry's size and
SHA-256; no original archive was overwritten. The packaging command and result
are retained in `.cache/p43/logs/p43-review02-package-01.{json,log}`.
The pre-update review report is preserved as
`.cache/p43-review02/before-acceptance-report.md`, 15,569 bytes, SHA-256
`d99da352bcb5a288157fef1e2552647dec0321bd2b9ce374f4eabf1562bfc0fe`.
This preserves the original review and its failure without freezing this mutable
operational note or rewriting its first evidence archive.

The Windows failures, original red probe and both targeted successes remain
attached to their real commands. CI still has 24 npm warnings, two Actions
warning annotations, four expected negative-test exception lines and the inherited
dependency advisories. No dependency was changed or risk waived. Real
publisher/viewer coverage, the historical CRL exception and the newly reported
external cache timestamps remain unresolved attribution/coverage limits; no
external cache was modified or cleaned. No live operation or browser was started.

This continuation uses the inspected existing cmd/Node execution adapter and its
project-local TEMP/home/cache/log settings. All chosen new files and edits are
inside the active worktree: prefixed review logs, the preserved report, this
acceptance increment, and scoped report/issue-table/board additions. Product
files and prior archives remain unchanged; no intentional writes to another
worktree, shared Git metadata or user profile were performed.

The final bounded audit at 2026-10-18T06:52:17Z passed all 20 selected file paths
through the directory-boundary/reparse guard. The new archive and all local
inputs still match their recorded hashes. The source/configuration scope is
clean against 0067b6c, the staged diff is empty, and `git diff --check` exits 0.
Git's existing LF-to-CRLF advisory for the implementation note is retained, not
reported as a content error. The shared task index remains 2,498,441 bytes with
mtime 2026-10-18T05:08:24.511Z, identical to this continuation's entry.

Read-only external-cache follow-up at 2026-10-18T06:53:29Z found the following
timestamps. Under the earlier documented `CryptnetUrlCache` base, both
`Content/ABD721CDC3648033BA8C827AF15A4543` (309 bytes) and
`MetaData/ABD721CDC3648033BA8C827AF15A4543` (192 bytes) now have mtime
2026-10-18T05:11:29.717Z; both B6E4D06BF128A1673A8DAFB4E25B990D files retain
2026-10-18T01:03:00.875Z. The file
`C:/Users/SU/AppData/Local/Microsoft/Windows/PowerShell/StartupProfileData-NonInteractive`
is 1,004 bytes at 2026-10-18T06:40:20.109Z; its sibling under
`C:/Users/SU/AppData/Local/Microsoft/PowerShell/` is 68,032 bytes at
2026-10-17T08:37:13.169Z. These advances do not identify their writer. All selected
command entry points used cmd/Node, not PowerShell, a browser or native Schannel.
No external cleanup, move or deliberate modification was performed. Attribution
remains unresolved; no machine-wide zero-write claim is made.

### Formal Entry And Needed Authority

The product remediation barrier has been cleared. The formal v3 input-delivery
barrier has not: the diagnostic/semantic runners are still in ignored `.cache`
paths and are not represented as committed runner inputs in the frozen profile
configuration. The first review deliberately did not create a formal contract
while this product finding was open. Its cached commands and this re-review must
not simply be relabeled as an executed frozen acceptance round.

The next root-owned step is to place the bounded reused evaluation runners under
`docs/acceptance-contracts/P4-3-v1/tools/`, bind their actual dependencies in
`Tools/provenance/manifest_profiles.json`, and prepare the v3 contract/matrix from
the existing sole Spec. This is input registration, not new product criteria,
permission expansion or another freezing agent. Preserve all existing failures
and use the saved cloud observations as external inputs under section 0.1;
new execution is the offline evaluation, not another cloud campaign.

Before formal execution, those runner/profile inputs require a scoped commit,
and a profile change requires the existing acceptance-governance CI. The current
acceptance continuation has not been treated as permission to write outside its
active worktree or to inherit a previous implementation session's Git/CI grant.
The precise authorization requested is:

- Writable roots: this active task worktree and `D:/github/my/E-Track/.git`, only
  the task worktree index, objects, task-branch refs/reflogs and necessary command
  metadata; no other worktree index, main ref or cleanup.
- Operations: scoped acceptance-runner/profile/contract/evidence commits, push
  only `dev/p4-3/admin-controls-20261017`, and run/read
  `.github/workflows/acceptance-governance.yml` on that branch. Preserve original
  commit IDs and user changes; no force push, PR merge, main synchronization,
  deployment, account changes, new CI secrets, R2/D1 mutation or device action.
- Purpose/effects: make the exact acceptance inputs reachable from a Git freeze
  point, execute the required governance checks, then independently evaluate and
  validate the contract/matrix. After a genuine formal result, evidence and
  FREEZE-INDEX registration remain separate commits as required. Git objects,
  task history and CI evidence will be created; none grants production readiness.

Until that boundary is expressly granted, formal execution and final validation
remain NOT_RUN. This is not an unresolved product defect or a request to repeat
the successful implementation validation. No whole-card PASS or completion state
is claimed. The sole pending owner is the user-assigned root acceptance agent,
after the bounded Git/CI authority is decided.

## P43-AUTH-20261018: Formal Execution Authority

The user expressly authorized this root acceptance session to continue until
P4-3 is completed or implementation remediation is required. This grants the
bounded worktree/shared-Git, acceptance commits, task-branch push and governance
CI operations requested above. Only this worktree and its necessary shared Git
metadata are writable; no main change, merge, force push, deployment, cloud
business mutation, device action, new CI secret or external cleanup is planned.
The independent reviewer prepares and approves the existing Spec's v3 input
binding under this delegation; no extra reviewer or competing Spec is introduced.

Formal preparation reuses the reviewed CI, source probe and original-evidence
oracles. Only their contained I/O and dependency registration change. Sensitive
local originals remain unpublished: the contract binds their exact size/hash
registry, public redacted original archives and the independent raw/projection
checks. Missing or changed private originals fail closed, rather than trusting a
handwritten summary. This local retrieval limit will remain explicit in the
final package; it does not authorize sharing session/token material.

### Input Qualification

Six bounded Node entries reuse the original probe, CI checks and live-state
oracles. `P43Evaluation` registers those entries plus the Worker test inputs not
covered by Cloudflare. The copied 585-entry live and 158-entry remediation ZIPs
retain their original bytes; Git reuses the existing identical archive blobs.
The private registry binds 186 local originals, and the live evaluator verifies
every one against the original public receipt and/or projection without
publishing its sensitive values. Node/tar identities are recorded separately.

The first adapter qualification, `dev-ci-01`, is a preserved HARNESS_FAIL before
formal freeze: Windows bsdtar returned 569 entries with exit 0 from ZIP stdin,
versus all 585 entries when given the same seekable file. The adapter now uses
standard tar file inputs and two guarded hash-named nested ZIP caches; it does
not implement another ZIP parser. `dev-ci-02` passes all 743 entry checks,
source/build/CI bindings and six negative oracles. `dev-live-01` verifies 186
private originals, 55 D1 responses, 53 projections, 54 HTTP exchanges, 18 public
bodies, 21 screenshots and the original 24/3/1 effects, including both tamper
negatives. `dev-ui-01` passes 6/6. The failed and successful exact receipts/logs
are retained under the new bundle's `preparation/`; these are qualification,
not formal executions and not a repeated cloud operation.

Global hooks were inspected before Git writes. They remain enabled; the existing
adapter clears notification/API environment keys, supplies an explicit commit
message and contains hook temporary paths. No global Git configuration is
changed. The forthcoming input commit is confined to this task's acceptance
tools, profile/attributes, prepared originals, reviewer records and existing
task board. Product source remains 0067b6c.

## P43-20261018-01: Formal Result

**DECIDED PASS: P4-3 independent implementation acceptance.** The original
implementation owner is preserved. P43-ACCEPT-02 is closed; no additional required
product remediation was identified. This completes this card's approved scope,
not deployment/main integration or the retained P4-4/P5/production obligations.

| Binding | Value |
| --- | --- |
| Contract | `docs/acceptance-contracts/P4-3-v1.contract.json`, unchanged after freeze |
| Input commit | `1ddd948bbf7d0dc2097c14d87def767314342f8f` |
| Input tree | `855c15853c572b83d9684235dbf69a247d4968b2` |
| Contract SHA-256 | `5517F3D4778C702B251985C38DF81BC904569BE53F8764BC3E7B9ECF65C10858` |
| Final matrix | `docs/acceptance-contracts/P4-3-v1/evidence-matrix.json` |
| New governance CI | `39110429390/1`, exact input commit, all three jobs successful |
| Formal commands | `formal-ci`, `formal-live`, `formal-ui`, `formal-governance`: four independent offline executions, each exit 0 |
| Final validation | `VALIDATION=PASS contract=P4-3-v1 round=P43-20261018-01 overall=PASS` |

The seven PASS criteria are API contracts/security/atomicity, both channel
operations and CAS, public selection/download stop semantics, release-action
idempotency/disable/recovery, bilingual UI/reconciliation, asset retention, and
acceptance governance. Their exact gates, command dependencies and original
evidence hashes are in the frozen contract and final matrix. This round has zero
formal REUSED entries: previous implementation and review observations are
external original inputs, not forged previous EXECUTED PASS anchors.

The formal evaluators independently checked all 743 public archive entries and
all 186 required private originals. Original effects remain 24 channel updates,
three recovery issuances and one disable; both channel chains and all six asset
rows agree. The current-source probe is 6/6, the source-bound product CI remains
270/36/3, and the repaired UI/server applicability checks pass. Historical
933b790 data is justified by the exact session-cookie-only server delta to
972e74c; the latter's server executable is unchanged at 0067b6c. The formal
governance evaluation finds eight successful suites (323 tests), plus the two
17-test host-helper results and the original adapter/spec-probe outcomes in the
three successful jobs. New governance logs contain three warning annotations
and zero error annotations; prior product-CI warnings/advisories remain as above.

The first formal precheck failed only because the helper emitted a lowercase
matrix contract hash and this validator compares that field to uppercase hex.
The failed output and initial NOT_RUN matrix are preserved. The mutable matrix
field is normalized at the packaging boundary; the existing helper's lowercase
input/output convention is not mistaken for a different digest. The unchanged
contract, frozen runners and criteria were not rewritten. `formal-precheck-02`
then passed with NOT_RUN before the four commands; final validation passed after
them. No passed observation was repeated for this formatting correction.

The bundle README records the exact limitations and controlled private-original
retrieval requirement. Its native/Windows failures, pre-review failure, adapter
failure and first-precheck failure are preserved alongside successes. Source/CI
verification of 0067b6c is not an assertion that it is deployed: the recorded
deployment remains 972e74c. Real publisher/viewer sessions, inherited dependency
advisories and external-cache attribution are not silently closed or waived.
The subsequent closeout commit registers the separate bundle commit and updates
only this card; no main merge, new secret, cloud mutation, device action or
external cleanup is part of this acceptance.

### Bundle Registration

The independent evidence bundle is committed separately as
`7e11e96c4acb2735710d626682a6d1a018efadf6`, after input commit 1ddd948.
It self-validates at that exact bundle HEAD with overall PASS; the raw command
and result are retained in `P4-3-acceptance-2026-10-18/closeout-bundle-check.*`.
The following closeout commit adds the P4-3-v1 FREEZE-INDEX row and completes
only the P4-3 card, preserving its implementation owner. It does not modify the
frozen contract, matrix, input profiles, runner bytes or original archives.

The seven-criterion decision and retained limits apply to the task branch
`dev/p4-3/admin-controls-20261017`. Main integration remains separate and must
preserve the input/bundle commit ancestry, not squash or rebase it. No extra
implementation correction is required by this acceptance. Future deployment,
real publisher/viewer configuration and inherited dependency treatment belong to
their explicit follow-up scope; no CRL/cache cleanup or deliberate modification
was performed.

All selected output namespaces remain the active worktree's acceptance/report
directories and `.cache/p43*`, plus the expressly authorized task Git index,
objects and task-branch refs/reflogs under the shared `.git`. Raw CRLF logs are
preserved using only a scoped `cr-at-eol` whitespace attribute, not by rewriting
the evidence. Final post-commit validation, branch readback and bounded path/cache
audit are performed before the session handoff; this is not a claim of a
machine-wide filesystem trace or attribution of unrelated cache timestamp changes.
