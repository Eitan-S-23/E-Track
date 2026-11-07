# P51 App Web Independent Review

## Findings And Disposition

No blocking implementation, security-regression or core-observation evidence
finding was identified in the bounded nine-file batch. **SCOPED_REVIEW_PASS**:
the tested source and the retained isolated website observations may be consumed
by root's scoped source delivery. This is an independently executed offline
evaluation of existing originals, not another live website execution, not a clean
filesystem-boundary verdict, and not P5 completion or production qualification.

Reviewer: `/root/app_web_review`, a non-implementer of this batch. Authority and
reuse basis: canonical `docs/acceptance-execution-contract.md` section 0 and
`docs/agent-collaboration-contract.md` Independence And Closeout, read from
`D:/github/my/E-Track`. The task worktree has no `.trellis` directory; existing
contracts and the root task handoff were used rather than inventing a new Spec.

One concentrated disposition list:

| ID | Disposition | Basis, direction and oracle |
| --- | --- | --- |
| P51-AWR-01 | DECIDED: source/observation review passed | Nine source identities, actual CI and 9 real POSTs match their originals. No product repair or replay is required. Root may deliver the exact eight non-pubspec blobs under its separate main-scope audit. |
| P51-AWR-02 | DECIDED: retained boundary exception, not resolved | The implementation report accurately retains 13 distinct external cache changes, overlapping windows and UNKNOWN attribution. Do not label this clean boundary, add overlapping counts, delete caches, or attribute them to a process without evidence. Root owns any separately authorized investigation/cleanup; keep the exact prior audit. This does not invalidate the independently hash-checked product observations. |
| P51-AWR-03 | OUT_OF_SCOPE: integration and final qualification | Do not merge the whole historical task branch or carry the test version bump into main merely to deliver the UI/proxy fix. Root owns the exact dependency/trigger audit and integration result. App self-update, production promotion, Windows update-path qualification and remaining P5 obligations stay unclaimed. The two-Release cap does not reset. |

## Scope And Identities

Active project root, abbreviated R:
`D:/github/my/E-Track/.cache/p35-integration-20261028/source`.
Only writable review subtree:
`R/.cache/p51-app-web-review-20261108-01`.
Original implementation area, abbreviated A:
`R/.cache/p51-app-release-20261108-01`.

The reviewed remote branch is `release/p51-app-web-20261108`:

| Commit | CI | Scope |
| --- | --- | --- |
| `67fc15541e645cbbde3236157385590ba41144f7` | `42398324376` | Endpoint/visibility workflow, proxy and tests; test App 1.0.73+99 |
| `4474dddf006562f71304d4791e4a5641676bca89` | `42398527444` | Test App version only, 1.0.74+100 |
| `54ded0b3dd877346fdae0137fed79c89d4661b27` | `42401395702` | App rollback UI, tests and README |

The local worktree HEAD was `faee2f908f3ad55e7c954d44dc5b7a5ed488ed95`; it is
not mislabeled as any of those delivered commits. Original GitHub blob replies,
tree/commit responses and branch readbacks were checked. The latest nine working
files match the delivered SHA-256 and Git blob IDs after LF normalization.
The first commit's test pubspec is superseded only by the second commit's pubspec.

Exact file identities and commit/tree bindings: `evidence-02/source.json`.
The nine files are the two workflows, two endpoint/proxy tests, App pubspec,
public proxy `_worker.js`, Admin `public/index.html`, `test/app-ui.spec.ts` and
Admin README. The eleven selected delivery files all match the original manifest.
`evidence-02/inputs.json` records 491 distinct hashed source/evidence inputs.

## Verification

### Implementation And Safety

`admin/public/index.html:5026` selects rollback only for a known older integer
version. Current/equal-code, disabled/archived, missing-current identity and
stopped-latest cases are locked. `publishRelease` at line 5036 preserves explicit
confirmation, Stable's typed `stable`, role checks, captured CAS revision and the
existing CSRF-protected mutation path at line 5483. Failed requests are not
automatically replayed. The failure wording does not claim that an uncertain
rollback was confirmed. `renderActionLocks` at line 6199 follows the same mode.

The public proxy forwards only seven exact GET paths, preserving the request
origin and streaming response; the added four App paths do not forward Admin/CI
or writes. All 14 existing proxy tests independently passed. The workflow's
App manifest define is independent of the MCU override; all 15 endpoint and
Release-visibility tests independently passed, including ordinary versus
prerelease visibility, prerelease/not-latest and failing-build propagation cases.
The test adapter changed only the fixed output-directory prefix, not assertions
or source, and invokes a fake Flutter function rather than building an App.

Current Cloudflare best-practice and HTTP service-binding documentation were
retrieved with verified Python/OpenSSL HTTPS, all three reference GETs returned
200. The registry identifies workers-types `5.20261107.1`; no dependencies or
compiler were installed. Existing CI supplies typecheck evidence.

A scoped secret-pattern scan over delivered text and changed workflow/test/UI
sources returned no matching private-key, GitHub-token, JWT or cookie literal.
This is not a universal secret-discovery guarantee. Private credentials, cookies
and signed URLs remain excluded from the selected delivery. The offline evaluator
reads public-key material and private original responses without exporting their
contents; its input index contains identities and paths, not private values.

### Actual Website And Assets

`evidence-02/web.json` independently re-evaluates the private response bytes
against each sanitized response's byte count and SHA-256. The actual order is
two notes writes, two baseline publications, four forward/rollback publications,
then one disable. All 9 writes have HTTP 200/`ok:true` originals. Their matching
readbacks and preserved helpers show they came through page clicks with explicit
request guards, not a direct API-write substitute.

Desktop/mobile cancellation precedes all writes in the original first window;
the collector asserts no POST and both screenshots are retained. The first
window's final-LF assertion and the second window's browser-download timeout are
preserved with exit 1 and successful cleanup. The next window's first complete
channel response equals its predecessor's final response. The six publish/CAS
steps are checked exactly, including both rollback flags and revisions 0->1->2->3.
No successful POST was repeated to repair collection.

Final state: Stable99/Beta99, revision 3, latest/download enabled; 100 disabled
and unreferenced. The returned complete MCU channel/release DTOs match the
Stable90/Beta11 anchor in every saved window. Signed payloads, release/source/run
identity and original assets are unchanged. Notes are restored as trimmed text,
not as byte-identical text, as the implementation report correctly states.

The five latest-response originals match the appropriate security payload,
assets and signature, and a version100 client is not offered a downgrade. The
previously issued URL returns 410 `ASSET_DISABLED` / `Asset or release is disabled`.
In the unchanged backend, token expiry/signature checking precedes this disabled
state check (`worker/src/downloads.ts:72`, `:154`, `:212`), so the result is not
an expired-token rejection misreported as a disable observation.

Exactly two retained GitHub Release/asset inventories match before/after:
Release IDs `437744712`, `437746785`, both prereleases; saved authenticated
GitHub latest response is 404. Both complete R2 downloads equal the archived CI
APKs byte-for-byte, HTTP 200, source `r2`:

| Version | Bytes | SHA-256 |
| --- | --- | --- |
| 99 | 47741488 | `5a1696a3f9a1832d78342a42bae131f736287ec17d92202b2ec23917cb10679d` |
| 100 | 47741484 | `a2ea831e60e37697f98667f94642dfa7c7cd175975e70a8d27a36df205f17685` |

Ed25519 verification and two tamper negatives were independently rerun per
version using the original signature verifier. Both ARM ABIs contain the isolated
App/MCU endpoints and matching public key. Hashed original aapt/apksigner logs
confirm non-debuggable `com.wen.gaia.gaia.p51web`, exact version and the pinned
single certificate. No APK was rebuilt, installed or modified.

All four selected original screenshots were visually inspected: mobile cancel,
Stable publish, Stable rollback and disabled final state. Confirmation text and
controls are readable; the rollback explains 100->99 and no downgrade for already
updated clients. Magenta regions are the declared identity masks. No new browser
or live screenshot session was launched by this reviewer.

### CI And Commands

Saved actual GitHub conclusions are successful for all three expected source
commits. Both App runs have successful Android, Windows and Release jobs.
Hashed raw test logs confirm Android 925 passed/16 skipped and Windows 906
passed/35 skipped for each run. The Admin run has 54 UI tests, Worker 288 tests,
typechecks and the compiled-router smoke. The existing diagnostics disclose ten
toolchain/SDK warnings per APK build and 21 Worker error-diagnostic lines,
including intentional rejection and constraint cases. They are retained rather
than turned into a zero-error-log claim.

All commands used `cmd.exe`, `login:false`, explicit R cwd. The Python prefix was
`python -I -S -B -X utf8`; script paths below are relative to this review subtree.
No Powershell, Schannel curl, Git write, CI dispatch, deployment or device command
was executed by this reviewer.

| Command | Exit | Result/output |
| --- | --- | --- |
| `review.py evidence` | 1 | Reviewer-only tree-response schema assumption; `evidence-01/failed.json` and exact old evaluator retained |
| `review.py evidence evidence-02` | 0 | Original-input evaluation; source/assets/web/CI JSON and hashed input index |
| `review.py tests` | 0 | 14 proxy + 15 endpoint/visibility tests; `tests-01/`, all inner owned receipts retained |
| `review.py references` | 0 | Three read-only HTTPS responses, `references-01/` |
| `review.py audit` | 0 | 116 output entries and 5 observed shared-cache changes; attribution UNKNOWN |

The reviewer-only first failure was `KeyError: .github/workflows/build.yml`:
GitHub's create-tree response lists the top level, not a recursive path index.
The evaluator was corrected to bind exact submitted paths to saved blob replies,
the returned tree to its commit, and the commit to its branch readback. Only that
offline evaluator was rerun, once, in a new output directory. No implementation
or original evidence was edited and no website/CI/device operation was repeated.

## Limits And Handoff

This review evaluates the original operation dates and retained final state;
it is not a fresh remote-state/credential-liveness observation. Real owner actions
and retained test inventories are established; Viewer/Publisher/CAS negatives use
the original mock/Worker checks, not a new live account-role campaign. Live App
github-fallback/announcements, App installer/self-update and Windows endpoint
behavior were not newly exercised. Existing physical and long-run obligations
remain with P5, without reopening successful SD/BLE merely because the reviewer
changed.

The implementation's exact 13-path boundary anomaly remains in the delivered
`boundary-audit.json`; its limited mid-task coverage and UNKNOWN attribution are
accurate. This review's output guard checks every selected path under its single
allowed subtree. `snapshot-before.json`, `snapshot-after.json` and `audit.json`
provide its bounded shared-cache comparison and exact output list. No external
cleanup or clean-whole-machine claim is made.

The review-window comparison itself observed five changes, immediately disclosed
to root. Under `C:/Users/SU/AppData/LocalLow/Microsoft/CryptnetUrlCache/`, the
`Content/D1BEC81CCAFDC823A062FF26A89A6B6D_FDA4BA3EAD8ECC04C1D36E59534F506A`
and matching `MetaData/` record disappeared; the
`MetaData/8B2B9A00839EED1DFDCCC3BFC2F5DF12` and
`MetaData/F15827BEC5BABE89C21DCDAE77464BF1` records changed. Also changed:
`C:/Users/SU/AppData/Local/Microsoft/Windows/PowerShell/StartupProfileData-NonInteractive`.
The exact before/after sizes, times and digests are retained in `audit.json`.
The reviewer performed no external deletion or PowerShell invocation. These are
shared-cache observations, not proved attribution to this review, Python, Node
or another concurrent process. Do not add them to the earlier 13 as if they were
disjoint incidents. No cleanup or further external modification was attempted.
`report-final.json` binds this disclosure-updated report; the earlier audit retains
the pre-disclosure report identity without being overwritten.

Review outputs are local, uncommitted and not frozen acceptance inputs. Root
owns source/evidence integration and P5 reconciliation. Deliver the eight exact
tested non-pubspec blobs only after the main-scope/dependency audit; preserve the
two immutable test Releases and all historical failures. Do not rebuild APKs for
the Admin-only integration or treat this report as permission to start another
Release, website cycle or device campaign.
