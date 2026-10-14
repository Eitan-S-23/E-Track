# P4-2 Independent Local Review

## Decision

The delivered implementation is real and substantially addresses the P4-2
multi-asset scope. It is not merely a plan and does not need to be rewritten.
One required API error-handling repair was reproduced. The normal Worker runtime
and remote environment observations remain unavailable, as disclosed by the
implementer. P4-2 is not formally accepted or complete.

This is a bounded independent code/evidence review, not a frozen formal execution
round. No production code, developer tests, original delivery records, task board,
acceptance contract, shared main, device or remote account was changed. P3-4 stays
closed at its candidate-stage scope; the device pause and 3/3 remain unchanged.

The canonical task Spec remains
`docs/ota-prompts/prompt-P4-2-implementation.md`. This note is a local review
addendum, not a second Spec or a source of operating authority. It is uncommitted
on `p4-2-implementation-20261014` and pending any authorized integration.

## Reviewed Identity And Reusable Evidence

- Worktree: `D:/github/my/E-Track/.cache/p4-2-implementation`.
- Actual HEAD and main: `7e71f694bcf97c78bcfde9e3220dcf399d99f1a0`.
- Modified source is uncommitted; HEAD alone does not identify it.
- Actual backend fingerprint:
  `bb25c276f21a93d273c97c567841d01cc6b7d8fa8520217d83a5380b95d3427e`.
- All 36 files and 27 logs in the original `source-identity.json`, its tracked
  diff and its invocation adapter matched their recorded raw SHA-256 values.
- Original input inventory:
  `.cache/p4-2-delivery/final/source-identity.json`.
- Original handoff: `docs/ota-exec-notes/P4-2-implementation-2026-10-14.md`.

The original Worker/Admin/Public typecheck logs record success. The original
host run records 172 passed tests in five files. The host adapter executes actual
SQLite statements, constraints, triggers and transactions and imports the real
business modules. Its R2/KV/DO/JWKS/DigestStream substitutions are not native
Cloudflare runtime or remote account evidence. The old non-firmware invariant
test bodies were not weakened by the delivered diff.

The two saved workerd probes failed during startup and executed zero tests.
They are environment diagnostics, not product failures or successful validation
of the delivered source. No unchanged crashing native probe was repeated here.

Source review covered forward migration/backfill, registration/canonical
metadata, latest selection, download/token/Range, owner recovery/idempotency,
Admin routing/publish gate, CLI adaptations, and their test/config dependencies.
No additional confirmed product finding emerged from those checks. This is not
a claim that unexecuted native or remote behavior is correct.

## P42-REVIEW-01: Malformed JWT Is Reported As A Backend Failure

Disposition: DECIDED, required repair, P2. Owner: the P4-2 implementation agent.

Affected path:
`app/bluetooth_flutter_Trace/cloudflare/update-service/admin/functions/api/admin/[[path]].ts`.

- `jsonFromBase64Url()` at line 1369 lets `JSON.parse()` syntax errors escape.
- `bytesFromBase64Url()` at line 1379 lets `atob()` decoding errors escape.
- `errorJson()` at lines 1143-1146 maps both exceptions to HTTP 503
  `BACKEND_UNAVAILABLE`.
- The new owner recovery endpoint uses this existing parser through
  `requireAccessActor()` and therefore inherits the error-contract defect.

Basis: `OTA-XC-HTTP-ERROR` and `OTA-XC-HTTP-ADMIN`, especially
`docs/ota-cross-system-contracts.md:305` and `:751`. Invalid Access credentials
must produce HTTP 401 `TOKEN_INVALID`, not a retryable backend outage. This is an
incorrect API classification, not an observed authentication bypass.

Independent reproduction used the actual Pages `onRequest` entry. Two structurally
three-part assertions, one with invalid Base64URL and one with invalid decoded
JSON, produced 503 instead of 401. Missing assertion, wrong segment count,
unsupported algorithm, null header and null payload were the five passing
controls. Every case verified no network call, no database prepare, no download
URL and consistent response correlation before checking the status/code.

Preferred minimal repair:

1. Translate only malformed JWT input decoding/parsing failures into a generic
   `AdminError("TOKEN_INVALID", ..., 401)` at the parser boundary.
2. Preserve object validation, signature/issuer/audience/time checks and existing
   role/origin/CSRF guards. Keep genuine JWKS/backend/runtime failures as 503 and
   expired valid credentials as 401 `TOKEN_EXPIRED`; do not blanket-catch every
   authentication failure as invalid input.
3. Add the two missing negatives to the existing developer Admin test suite,
   retain the five controls and the existing valid signed-JWT/replay cases, and
   self-test the repair as one batch. Do not edit the independent failed probe or
   its original logs to make it green.

Verification oracle: both previously failing inputs return 401 `TOKEN_INVALID`
with no business side effects or credential echo; existing valid, expired,
role/origin/CSRF and backend-failure semantics remain intact.

## Independent Probe Records

The existing contained `.cache/local-run.cjs` adapter invoked the installed
Vitest entry, with the existing host configuration reused for module aliases.
The new probe/config files are confined to this review directory. No alternate
product implementation or general-purpose acceptance runner was created.

- `.cache/p4-2-logs/independent-review-probes-01.log` and matching `.json`:
  exit 1, zero tests. A Windows absolute include path was not discovered.
  This is a preserved reviewer preparation failure, not product evidence.
- `.cache/p4-2-logs/independent-review-probes-02.log` and matching `.json`:
  exit 1, seven actual tests, five passed and two failed against the required
  API oracle. Only the probe root/cache/include configuration changed after
  the discovery failure; product and original developer tests did not change.
- Probe: `.cache/p4-2-independent-review-20261014/review-probes.test.ts`.
- Config: `.cache/p4-2-independent-review-20261014/vitest.review.config.ts`.

The effective second command, from the Worker package through the contained
adapter, was `node node_modules/vitest/vitest.mjs run --config` followed by the
absolute review config path. Exact executable, arguments, cwd, start/end and exit
are in the receipt. No successful historical developer tests are added to this
seven-test count.

## Remaining Admission Work

### P42-EXT-01: Native Worker Runtime

Keep this existing ID open. SQLite results do not establish native D1 batch and
deferred-FK behavior, R2 conditional/range semantics, or DigestStream execution.
After the repair batch, use the existing
`.github/workflows/cloudflare-update-service.yml` on the exact reviewed source.
It already supports workflow_dispatch, runs on Ubuntu with Node 24, uses
contents:read, and runs Public/Admin checks plus Worker type generation,
typecheck and the unchanged normal `npm test`. It contains no deployment job.
There is no demonstrated need for a new workflow or another test platform.

The source must first have an authorized, scoped commit/push on the dedicated
P4-2 branch. P3-4 delivery authority is not P4-2 Git/CI authority. This review did
not stage, commit, push, dispatch, open a PR or alter a workflow. Root owns that
bounded delivery/CI decision; the implementer can finish the local repair first.

### P42-EXT-02 And P42-EXT-03: Remote Inputs And Rehearsal

Retain the original distinctions: actual legacy rows/manifests are not reconciled,
and real D1/R2/Access, uploader readback, signing bindings/origin and fixed cutover
epoch are not observed. An isolated, explicitly authorized environment plan is
needed before those external actions. No production migration, promotion or
hardware experiment is inferred from this review.

When arranging that plan, reuse any applicable originals first, bind the exact
environment/assets/identity, and observe only missing backend criteria. Do not
wait for P4-1 implementation to define P4-2's schema and do not reopen P3-4 or run
an OTA to qualify a host collector. P3-5 consumes the real backend only after its
remaining admission requirements are met.

## Write Audit

The active writable boundary was resolved as the named P4-2 worktree. Nineteen
controllable output roots were checked for actual containment before the probes;
the review root and its cache are also contained. Shell commands used cmd.exe,
login:false and an explicit workdir. Python used -I -S -B -X utf8. Test subprocesses
had project-local temporary/home/appdata/npm/Wrangler/cache paths, with inherited
Node preload/coverage/compile-cache settings removed or disabled. No npm install,
workerd launch, PowerShell, device tool or remote account command was run.

New chosen outputs are this review directory, the two uniquely named probe logs
and receipts, and normal contained invocation/Vite cache output. Original source,
developer tests, handoff, inventory, original logs and adapter are rechecked by
the companion audit. This is a controllable-output audit, not a machine-wide
write trace or an assertion that every ignored cache byte is immutable.

P42-WRITE-01 remains an implementation-session exception, not a clean-audit PASS.
The external log still exists at
`D:/DevCache/npm/_logs/2026-10-14T09_47_43_168Z-debug-0.log`, size 983, SHA-256
`5e8050d938c9755783ca1cb7b1da233107fc3c2ce633ba695fb5abe04baac873`.
This review only read its identity. Its removal is neither needed for code review
nor authorized here. The reported attempted cleanup of one unidentified old npm
log remains unknown; no absence/deletion/recovery conclusion was invented.
