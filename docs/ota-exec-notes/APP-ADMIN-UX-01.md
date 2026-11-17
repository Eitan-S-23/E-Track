# App And Admin UX Improvements

## Entry

- User requested implementation on 2026-11-17 after the consolidated list.
- Owner: root implementation session. The 2026-11-18 follow-up is now built,
  integrated and deployed: original-signed `1.0.80+106`, App source `80117099`,
  main integration `e7b990c7` and deployment-adapter repair `28459a89`.
  Actions deployment `44186088340` and real owner/source/API readbacks pass.
  The prior login-only conclusion remains withdrawn; `E_TRACK_CI` is working.
- List deletion modes, Sync, pre-association task feedback, scrolling and compact
  App settings are live in the backend and included in the new App candidate.
  Independent acceptance, installation and App codec migration are not claimed.
  See the final delivery section; earlier NOT_RUN/LOCAL_PENDING entries retain
  their historical checkpoint meaning.
- App baseline: delivered 1.0.78 / 104, commit
  `b15017a30413e5bf10ea32a19008503c8bd922ae`.
- Current product main: `28459a89fcd6792611052cb601b231bb947bcc6d`.
  Existing root records are consolidated without unrelated firmware changes.
- Preserve unrelated uncommitted firmware/recorder changes in the distribution
  worktree. No device operation, firmware change or recreation of successful
  delta run `43932189981/1` is included.
- Reuse existing UI components, typography, colors, spacing, dialogs and icons.
  No second design system or UI dependency is requested.

## Scope And Oracles

- UX01: Permanent, discoverable setup entry on the device home screen. Reuse
  the actual permission/setup page; seen/deferred is not permission granted.
- UX02: New manual announcements on usable main-screen entry, foreground return
  and a bounded foreground interval. Retain manual access, batch multiple notices,
  persist only presented identities. Never auto-announce offline placeholders.
- UX03: Server publication time displayed in local time and a pinned badge.
  Pinned first, then newest first; pinning never bypasses seen-state.
- UX04: Coordinate announcement and daily update dialogs. One visible dialog;
  simultaneously ready update prompts take precedence. Defer announcements
  through setup, downloads, installation and other important dialogs. Retain
  deferred items; never pop another dialog's route. No duplicate release prompts.
- UX05: Admin announcement create/edit in the existing modal style. Preserve
  drafts on failure, confirm discarding edits and retain list position.
- UX06: App inventory, packages and operations scoped to Android, Windows or iOS.
  iOS distribution capability must be explicit; no APK self-update on iOS and
  no fabricated iOS package or publishing support.
- UX07: Version multi-select, current-page select-all, confirmation and per-item
  results. Protect published releases, delta dependencies and active jobs; retain
  audit/tombstone rules. No real deletion during development verification.
- UX08: Notifications entry and Notification Center panel; single/bulk dismissal
  and clear-read. Hide completed job display records without deleting assets or
  required history. Candidate backfill must not resurrect dismissed messages.
- UX09: Every unfinished task has cancel and cancel-and-restart icon controls.
  Use standard icons, not text characters. Touch long-press, hover and keyboard
  focus explain actions. Long-press/release never executes. Retain accessible
  names, adequate targets, confirmation and busy guards.
- UX10: Accurate submission, queued, running, cancelling and terminal states
  with waiting time. Correlate exact provider run/attempt; waiting is not failed
  submission. Restart original parameters only after confirmed cancellation.
  Unknown/rejected cancellation cannot start another run. If the old attempt
  completes first, show its result. Late attempts cannot overwrite newer ones.

## Validation And Delivery

- Regression tests of actual UI/API paths, races, negative paths, platform
  isolation and partial deletion results, using existing test frameworks.
- Backend: TypeScript checks, Worker tests and Playwright UI tests. All controllable
  dependency caches, browser/test logs and temporary outputs stay project-local.
- Flutter: existing full Linux/Windows development CI under the standing
  `dev/flutter/**` authorization. No local Flutter/Gradle build. Changed App
  inputs also require authorized source-matched APK/EXE build verification.
- Keep package/signing identity. Shipping version/build increments belong to
  an authorized new release, never replacement bytes under an existing tag.
- Distinguish development, independent review, builds, candidate registration,
  channel publication, backend deployment, main integration and installation.
  Development does not grant production or device operations.
- App-closed immediate push/APNs is excluded; unseen announcements appear when
  the App next becomes usable.
- APP-COMPANION-01's remaining independent/device obligations are unchanged.

## Execution Log

- 2026-11-17: Read current main, delivered source, application build policy and
  collaboration rules. Product edits, CI, deployment and devices NOT_RUN at
  this entry checkpoint. Main metadata remains LOCAL_PENDING.

## Implementation Checkpoint

- Owned worktree: `.worktrees/app-admin-ux-20261117`; branch
  `dev/flutter/app-admin-ux-20261117`. Current source:
  `80cf8a26d9ec56285738b12be8539b19509aedda`, based on the delivered App above.
  The development branch is pushed. Product main integration is not performed.
- UX01-UX04: home permission entry reuses the setup route. A route-owning prompt
  coordinator serializes updates and announcements, defers through setup and
  update activity, and cannot close an unrelated dialog. Foreground polling is
  bounded; only actually presented manual notices are persisted as seen.
  Publication time and pinned badges use the existing App components and colors.
  Backgrounding before the entry animation completes cannot consume a notice;
  manually read notices are removed from an already queued automatic prompt.
- UX05-UX08: existing-style announcement editor sheet, platform-scoped App
  inventory/operations, App and firmware page selection/bulk deletion, and
  Notification Center dismissal. Server tombstones prevent candidate backfill
  from resurrecting dismissed messages. Completed-task hiding is actor/attempt
  specific and never deletes packages or job history.
- UX09-UX10: shared SVG cancel/restart controls appear on both task surfaces.
  Long-press explains without executing, including across list refreshes. Hover,
  keyboard focus, movement/cancellation and viewport containment are exercised.
  The server binds the exact repository/run/attempt, records cancellation intent,
  and restarts only after provider-confirmed cancellation. Rejected or unknown
  cancellation cannot redispatch. A late failure callback cannot bypass this
  through the older retry action. Original completion wins over restart.

## Development Results

All paths in this section are inside the primary project. The local host root is
`.worktrees/app-admin-ux-20261117/.cache/ux-host/`; CI originals are under
`.cache/app-admin-ux-20261117/`.

- `worker-check-03` and `admin-check-03`: TypeScript checks pass.
- `worker-host-03`: 493 passed, 16 files passed, no failed cases. This reuses the
  existing SQLite host adapter and actual handlers/SQL, not native Cloudflare or
  production R2/GitHub mutation evidence. Node reports its existing experimental
  SQLite warning; negative-path D1 errors remain in the original log.
- `admin-test-05`: all 10 new desktop/mobile cases pass.
- `admin-test-06`: all 244 browser tests pass in 8.5 minutes. Includes existing
  authorization, drafts, pagination, navigation, task/push and error-feedback
  regressions. The matching Playwright headless shell is project-local. Existing
  FORCE_COLOR/NO_COLOR warnings remain visible. Modal and task-tooltip screenshots
  were visually inspected; no new design system or icon dependency was introduced.
- Initial Flutter source `c75fcdc7` failed strict analysis for two unbraced returns;
  its tests nevertheless completed. Corrected source `6e6ee364` passes both hosts
  in run [43960036762](https://github.com/Eitan-S-23/E-Track/actions/runs/43960036762):
  Linux 903 passed / 16 skipped, Windows 856 passed / 63 skipped, plus 8 candidate
  cases on each host. Flutter 3.47.9, Dart 3.13.7; APK NOT_REQUESTED. Original job
  logs are in `keyring-logs-02/`; initial failure remains in `keyring-logs-01/`.
- Final App run [43964808676](https://github.com/Eitan-S-23/E-Track/actions/runs/43964808676)
  validates `80cf8a26`, including two added real announcement-dialog regressions.
  Both hosts and strict analysis pass: Linux 905 passed / 16 skipped, Windows
  858 passed / 63 skipped, plus 8 candidate cases each. Flutter 3.47.9 / Dart
  3.13.7; framework `c197ca5199e9ee5661e865596c9c07294dfab51c`, engine
  `89c39edfdfae2949f6806e4a315c0c08522238b7`. Scope is `all`; APK NOT_REQUESTED.
  Original conclusions and both complete console logs are in `keyring-logs-04/`.
  The runner's console includes bounded test-log tails; full development artifacts
  remain attached to the source run, not claimed as locally downloaded raw suites.
- Final backend run [43964809804](https://github.com/Eitan-S-23/E-Track/actions/runs/43964809804)
  passes on the same source: native Worker 451 tests / 13 files, public Pages
  checks, and all 244 Admin browser cases (6.3 minutes). The native configuration
  excludes the three host-only files; the separate host run includes their 42
  additional cases, giving 493. They are not represented as 493 native tests.
  Original executed-job logs and conclusions are in `keyring-logs-05/`. The workflow
  is check-only, with `prepare_admin_bundle=false`; the deployment-input job is
  correctly skipped, not a build/deployment success.

### Preserved Failures

- Native Windows `worker-test-01` failed before executing tests (workerd access
  violation). No system DLL installation or blind native rerun was attempted.
  `worker-host-01` then exposed outdated bare-job fixtures under the new retained
  input constraints; those fixtures were repaired without dropping negative
  assertions. `worker-host-02` passed 491 cases before the two cancellation races
  added at the current source.
- Installed-Chrome `admin-test-01` could not launch with the requested debug
  profile; matching project-local Playwright shell installation replaced that
  failed host route. `admin-test-02/03` preserve the missing request-ID fixture,
  genuinely disabled post-load controls and detached long-press target failures.
  `admin-test-04` exposed keyboard focus loss during refresh; the existing focus
  restoration now also matches task-control identity. `admin-test-05/06` pass.
- Backend run `43960037548` had 231 passing UI cases and 9 failures: six affected
  by the new fixture's missing request ID, plus three bounding-box readings only
  0.00003-0.00006 px over the unchanged limits. The latter assertions now round
  to 0.001 px, below a CSS layout subpixel; layout caps are not relaxed.
- `keyring-logs-03/failure.json` is a collector 404 for the deliberately skipped
  deployment-input job. The three executed jobs' original logs are present.
  The existing collector now excludes skipped jobs; this does not rerun CI or
  treat a skipped build as successful.

## Pre-Shipping Checkpoint

This subsection records the state before the user's subsequent shipping
authorization. The dated delivery result below supersedes its pending items.

- No standard APK/EXE build, shipping version bump, release, candidate registration,
  channel publication, backend migration/deployment or device operation was done.
  `pubspec.yaml` remains 1.0.78+104. Final App completion still requires authorized
  source-matched standard APK/EXE verification; a checks-only run is not a package.
- iOS is a distinct management/feed platform, not a fabricated iOS distribution
  implementation. Its package publishing is explicitly unavailable until the
  actual iOS route is configured. It never falls back to Android APK publication.
- App and firmware deletion conservatively preserve any retained delta-job
  dependency, including historical jobs. Hiding history is not permission to
  remove its inputs. No real release or notification was deleted in verification.
- Eventual authorized rollout must apply migration `0014_admin_ux.sql` before
  serving the new Worker/Admin readers, preserve existing bindings/credentials,
  and verify real Access plus provider permissions. Mock success is not live
  GitHub cancellation or live Access verification.
- Main remains `990d8b4d`; this task's board/note/index updates are LOCAL_PENDING,
  not committed or remotely delivered. Existing APP-COMPANION review records and
  its independent/device obligations remain unchanged.

## Filesystem Checkpoint

Every deliberately chosen code, dependency/browser cache, log, temporary/test,
Git and evidence output is under `D:/github/my/E-Track`. No project-external
cleanup was performed. The known SU/SYSTEM crash-dump and Windows Error Reporting
locations contain no matching workerd/Chrome dump observed in the bounded check.
The SU Chrome `User Data/Local State` file has a recent modification while the
user's Console Chrome processes are running; there is no before-image or process
attribution tying it to the earlier failed installed-Chrome launch. This remains
an audit limitation, not a claim of either an authorized external write or whole-OS
cleanliness. The final path/process check is recorded separately in the same cache.

## Authorized Delivery, 2026-11-17

The user authorized continuing packaging, deployment and main delivery without
another permission round. This is not a waiver of real-device acceptance or a
request to change the selected Beta/Stable channels.

### Original-Signed Packages

- Version `1.0.79+105`, source `59131a3ef0712d46e7b17694d585371b751ab7ba`.
  The only change after the tested `80cf8a26` is this version increment.
  Fresh inspection included all 117 existing Trace releases/drafts and the
  current candidate refs before reserving the version. No old package was rebuilt.
- E-Track [43968850096](https://github.com/Eitan-S-23/E-Track/actions/runs/43968850096)
  passes its checks and the original-App delivery wait. Firmware is correctly
  skipped because its inputs/version did not change.
- Original Trace [43969069993](https://github.com/Eitan-S-23/Trace/actions/runs/43969069993)
  succeeds: admission, Windows and Android, with strict analysis/tests, original
  APK signing/identity checks, R2 full-byte readback and candidate registration.
  There was one new-version build, no Android/Windows retry and no debug build.
- The APK retains `com.wen.gaia.gaia`, signer
  `3cecee6330a930e020b454b6d4a79568f4494ca324ae7bcf2c1914e51b04ab47`,
  both ARM ABIs, the original backend/key and BLE V2. It is 48,486,828 bytes,
  SHA-256 `74c5952f5abf8afd08984fee68464e39e72696c0af5b6119b3c2c1a241071826`.
- [Original v1.0.79 assets](https://github.com/Eitan-S-23/Trace/releases/tag/v1.0.79)
  include the APK, Windows EXE/runtime ZIP and metadata. Complete executed-job
  logs are in `keyring-shiplogs-01/`; `keyring-release-01/` contains the release
  inventory and three downloaded metadata files checked against asset digests.
  The GitHub metadata asset is the pre-R2 copy; the final R2-enriched metadata
  remains in the original job's `CANDIDATE_FILE` console record.
- Actual D1 readback confirms `rel_trace_android_v1_0_79`, version 105,
  state `candidate`; APK and manifest are available in original R2. Its APK hash
  matches the original signer inspection. Windows assets follow the existing
  GitHub distribution route. No fake iOS package or Windows D1 row was created.
  No new delta, channel publication or device installation was performed.

### Main And Service

- Main source delivery is `304d01f571f015f81465f4490587c8f3f8baf392`.
  This is a bounded 222-file App/backend/support source import, not a history
  merge of the long candidate branch. Every selected source tree equals the
  original checked/built source. Unrelated firmware source and frozen evidence
  are excluded; original commits/evidence remain on their existing branches.
- The main commit intentionally avoids duplicate CI/package creation with
  `[skip ci]`. It reuses the exact matching successful App/backend/original-build
  executions above, not an unexecuted claim about new main packaging. Scoped
  integration regressions additionally pass: runner 66, APK helper 50, original
  identity 8, timing 10 and public/Access contracts 20. The first APK-helper run
  failed because this SYSTEM host lacked command-scoped Git safe.directory;
  only that helper was rerun with the exact primary root allowed, without a
  global Git change or product/test modification. Originals are in
  `main-checks-01/` and `main-checks-02/`.
- Migration `0014_admin_ux.sql` was applied exactly once and its inventory plus
  added columns were read back. Worker version
  `54ad084f-1bc3-41a8-bcad-cdc28ff536d4` is deployed on the original service.
  Actual before/after bindings compare equal, including retained secrets and
  delta execution references. The first two local Worker bundle attempts failed
  before upload because external-config tsconfig paths were normalized against
  the wrong directory; the supported explicit `--tsconfig` argument resolved it.
  Product code and the already applied migration were not replayed or changed.
- `cloud/keyring-cloud-live-01/result.json` confirms unchanged App/MCU channel
  pointers and all 29 existing delta-job rows, matching candidate/R2 identity,
  and HTTP 200 Worker announcement feeds for Android, Windows and iOS. The
  successful historical delta `43932189981/1` is untouched.

### Remaining Pages Login Boundary

Historical checkpoint. Its requirement for another browser login is superseded
by the owner correction below; the original failures remain unchanged.

- Admin and Public Pages are not yet redeployed. Live Admin HTML still differs
  from the new source. Public Android/Windows announcement feeds return 200;
  Public iOS still returns 400 until that affected Functions bundle is deployed.
  The new Admin controls must not be described as live merely because source,
  Worker or APK delivery succeeded.
- Two documented preserved Pages OAuth inputs failed renewal with HTTP 400.
  Existing `e-track-ci` still successfully reads/deploys this Worker and D1, but
  its exact Admin Pages management read returns 403/10000. These are recorded
  operation-specific results, not missing credentials or a requested scope
  expansion. Source credential files were only read; failed copies are retained.
- The still-valid organization SSO was successfully exchanged for the actual
  original Admin session; `/api/admin/session` returns HTTP 200 and `owner`.
  Thus normal Admin login is healthy. This does not grant Pages deployment.
  Credentials remain only in the protected project-local directory.
- The standard Wrangler login was opened with automatic browser launch disabled
  and only the previous account/user-read and Pages-write scopes. Its first
  invocation rejected an explicitly supplied `offline_access` because Wrangler
  already adds that scope itself. The corrected link was given to the user, but
  no authorization callback arrived before Wrangler's deadline. That link is
  expired, not a successful login. No browser profile or Access policy changed.
- After a fresh user-confirmed management login, run the prepared original Admin
  deployment script with `--skip-secrets` and exact source commit, deploy the
  affected Public Pages bundle, then verify unchanged settings, real Access,
  exact served assets and the iOS feed. Do not rebuild/re-register the successful
  packages, reapply migration 0014 or replay old delta generation for this step.
  APP-COMPANION-01's D0-D5 and independent whole-card obligations remain separate.

### Alternate Deployment Route Check, 2026-11-17

- Read-only secret metadata in `keyring-pagesinventory-01/result.json` confirms
  the original repository `CLOUDFLARE_ACCOUNT_ID` and `CLOUDFLARE_API_TOKEN`
  slots exist. This is distinct from proving their values, identity or Pages
  capability. No secret was read from GitHub, exported, replaced or widened.
- Main `40e450c6004fdac009a47a5274e1c8dbc188d852` extends the existing manual
  Pages workflow to use those protected slots, pin the exact verified source,
  check the original account/projects/branch and live configuration before any
  deployment, preserve Access secrets and verify configuration afterwards.
  It can deploy the matching Public Functions in the same serialized operation.
  Its two actual inline guards pass 18 offline positive/negative checks in
  `.cache/app-admin-ux-20261117/pages-workflow-check/result.json`. These are
  deployment-tool self-tests, not another product or independent acceptance run.
- Actual [Pages run 43978919787](https://github.com/Eitan-S-23/E-Track/actions/runs/43978919787)
  checks shipping source `59131a3e`, then fails its exact Admin Pages GET with
  HTTP 403 / code 10000. Dependency installation, Admin/Public deployment and
  readback steps are skipped. It did not build an App, apply a migration,
  cancel a job or mutate Cloudflare. Its complete original job log and step
  conclusions are retained in `keyring-logs-06/`. This closes the untested
  alternate-route question; repeating the same credential is not a repair.
- Fresh Wrangler login `cloud/keyring-cloud-login-03/` was presented while its
  listener was active. Wrangler then reported `Timed out waiting for authorization
  code`; the saved expiry remains `2026-11-14T19:21:28.012Z`. The adapter's outer
  600-second timeout did not fire, hence `timedOut=false` in its receipt does not
  mean a successful callback. This third link is expired and must not be reused.
- `cloud/keyring-cloud-live-02/result.json` freshly verifies unchanged channel
  pointers and all 29 existing delta-job rows, the original 1.0.79 candidate/R2
  hashes, and the real Admin owner session. Worker feeds remain HTTP 200 on all
  three platforms; Public iOS remains HTTP 400 and Admin HTML is still old.
- The next required user action is one management-login confirmation in this
  Windows computer's browser, not another task authorization or new plaintext
  key. Generate a fresh bounded link when the user is at the computer. On success,
  use `keyring-cloud-inspect-03`, then the prepared Admin/Public deployments and
  readbacks. Do not rebuild packages, reapply 0014, redeploy the already delivered
  Worker or touch the successful historical delta to unblock Pages.

### Owner Correction And Credential Reconciliation

The user again confirmed that Cloudflare authority already exists and challenged
the repeated login request. The root agent withdrew the unsupported conclusion
that browser login was the only way forward. Authorization to perform this task,
the identity/capability of a specific credential, and a particular OAuth copy's
state are separate facts. The earlier inventory omitted named sources, and a CLI
login suggestion was incorrectly promoted into a user prerequisite.

- The protected primary service `.github-actions-secrets.staging.local.json`
  was identified through the original P4-4 owner handoff, not a private-cache scan.
  Its credential differs from `e-track-ci` and currently verifies `active`.
  Its exact Admin Pages GET returns 403/10000 through the existing proxy and
  through direct TLS. Its own policy GET returns 403/9109; no policy or absence
  claim is inferred from that separate management-read denial.
- The original standalone repository is `D:/github/my/bluetooth_flutter_Trace`,
  confirmed by its Git remote. The first check of `D:/github/my/Trace` used an
  incorrect guessed location and does not establish credential absence. The
  correct original service input exists, matches the approved account and is
  byte-equivalent in memory to an already tested token, so its failed GET was
  not repeated. No original repository file or credential was modified.
- The separately named `token.txt` provisioning input was checked only for a
  local exact Pages GET, returning 403/10000. It was never passed to GitHub/CI,
  exported, substituted for `e-track-ci`, or used to change token permissions.
  `cloud/keyring-cloud-sourceprobe-01/` and `sourcecheck-01/02/03` (each with the
  `keyring-cloud-` prefix) preserve the bounded observations and distinctions.
- Official Wrangler config resolution identifies
  `C:/Users/SU/AppData/Roaming/xdg.config/.wrangler/config/default.toml` as the
  existing default input. Its expiry is `2026-07-08T05:35:52.973Z`. One normal
  noninteractive refresh in the new protected project-only `xdg-global-01`
  copy also fails; `cloud/keyring-cloud-renewglobal-01/` retains the result.
  The original user file was read only, not overwritten or cleaned. No fresh
  browser login was launched after this correction.
- The current SYSTEM process has no Cloudflare environment inputs. A targeted
  read of SU's existing environment registry values for `CLOUDFLARE_API_TOKEN`,
  `CF_API_TOKEN` and `CLOUDFLARE_ACCOUNT_ID` finds none. The primary Admin/Worker
  `.env` and `.env.local` files are absent. These are named-source observations,
  not an assertion that every private source on the machine was searched.
- The live API reference accepts either Pages Read or Pages Write for the
  project GET. A write-only-versus-read-only explanation is therefore not
  assumed, and the original 403s are not relabelled as successful deployment.
  No new token, wider scope, CI secret change, Pages deployment, package build,
  migration, device action or business mutation occurred during reconciliation.

The remaining question is the name/protected locator or redacted scope receipt
for the existing Pages publishing credential the owner identifies. Ask for that
identity, not plaintext, another task-use authorization or a mandatory browser
login. Do not repeat the same denied inputs to simulate progress. Shared input
locations and this correction are indexed under `CF-PAGES-01` in the credential
registry. Successful package/Worker delivery and all independent device/formal
acceptance boundaries remain unchanged.

### Existing Local And GitHub Routes, 2026-11-17

The user explicitly requested reuse of credentials on this host or GitHub,
completion of Pages deployment, and root-level deployment memory. The root agent
continued the existing task; it did not rebuild App packages or replay deployment
of the already delivered Worker/schema.

- `.cache/app-admin-ux-20261117/keyring-pagesinventory-02/result.json` records
  both owning repositories' secret metadata, existing environments and Pages
  workflow histories. No additional Pages credential slot was identified in
  those environments. A secret name is not a returned secret or a capability test.
- `keyring-traceinspect-01/result.json` preserves the original Trace workflow and
  historical failed Pages runs. The bounded operational branch
  `Eitan-S-23/Trace:ops/pages-existing-credential-20261117`, commit
  `53d049b1122edaab476f2fa6a032a405bf6b071e`, changes only the Pages workflow.
  It reuses the main deployment guards and checks out the already verified
  E-Track source `59131a3e`, with Trace's existing secrets kept inside its runner.
  Main/release branches, secret values, protection rules and App sources are
  unchanged. Branch trigger inspection and `[skip ci]` prevent App/firmware builds.
- [Trace run 43996459438](https://github.com/Eitan-S-23/Trace/actions/runs/43996459438)
  actually executes its exact Admin project GET and returns HTTP 403/code 10000.
  Both dependency installs and both Pages deployments are skipped. This is not
  a missing-secret assertion, successful deployment or another E-Track-token retry.
  The original full log is `keyring-tracelogs-01/job-133749622535.log`; dispatch and
  run/step receipts are in `keyring-tracepages-01/` and `keyring-tracestatus-01/`.
- `cloud/keyring-cloud-lineage-01/result.json` traces five named inputs directly
  from successful local deployment scripts. They contain three distinct OAuth
  inputs; their exact current Admin GETs return HTTP 401/code 10000. Two duplicate
  inputs were not retried. Only sanitized provenance/expiry/equality observations
  are public; configuration files were not modified and values/hashes not exposed.
- `cloud/keyring-cloud-standard-01/result.json` records the installed Wrangler's
  supported token/global-key environment names for the actual SU user, machine
  and current process, the legacy/XDG configuration locations and primary
  root/App/service dotenv paths. No untested input was found at these named
  locations. There was no arbitrary private-cache scan, new login, token creation,
  permission expansion or credential export.
- Source syntax was checked; the new workflow parsed with installed PyYAML after
  the optional Node YAML package proved unavailable. No package installation or
  product-test replay was used for that local parser check. The actual Actions
  run independently parsed and executed the deployment preflight.

Pages remain NOT_DEPLOYED for this batch. The remaining owner-dependent input is
the protected name/location or restoration of an existing Pages-capable route,
not another general authorization and not a mandatory new-token request. Preserve
the successful packages, schema, Worker, historical delta and original failures.
Do not automatically dispatch either denied repository route again.

The root-level [deployment memory](../../CLOUDFLARE-DEPLOYMENT.md) records the exact
targets, existing inputs, normal commands, verification and these unresolved
results. Its successful-deployment checkpoint remains incomplete. Root and App
`AGENTS.md` now point to it; the App's older automatic-browser-login instruction
was removed rather than left to contradict the corrected root rule.

## Pages Deployed And Verified 2026-11-17

The owner's explicit deployment request and retry were completed using the
existing project-private OAuth route. Source worktree
`.worktrees/app-admin-ux-20261117` remains clean at
`59131a3ef0712d46e7b17694d585371b751ab7ba`; primary/remote main were last matched
at `1ff996b6dbd80eb18179551b6189975503be9c37`. Existing source-matched checks and
packages were reused. No product source, dependency, signing input or version
changed. These new operational records remain LOCAL_PENDING; no commit/push was
performed in this retry.

| Component | Canonical deployment | Source/stage |
| --- | --- | --- |
| `trace-update-admin-staging` | `63cdf429-13dc-41b4-aa93-966755ee9d79` | Full `59131a3e` source, success |
| `trace-update-public-staging` | `3865fc8c-8c36-4247-afbf-408b1a8e35b1` | Full `59131a3e` source, success |

The Admin used the tracked Node deployment helper with `--yes --skip-secrets
--commit-hash`; Public used the pinned Wrangler Pages entry, branch `main` and
the same full commit hash. Both original projects existed before upload.
Exact GETs confirm new canonical IDs and full source hashes. Production/preview
runtime configuration is identical, including Access secret slots, D1/R2/KV/DO
bindings and delta workflow references. Only provider-generated
`wrangler_config_hash` values changed. The raw full-object mismatch from the
first Admin readback is preserved, alongside the bounded runtime comparison;
no runtime field was waived or restored by a configuration write.

Real live checks pass using the still-valid existing application Access session:
`/api/admin/session` returns `owner`; Admin HTML and all seven JS/CSS assets
return HTTP 200 and match the source bytes exactly. Public announcements return
HTTP 200 for Android, Windows and iOS (6, 5 and 5 items respectively). This closes
the prior Public iOS HTTP 400 observation without fabricating iOS package support.
The channel/firmware-channel/all-29-job snapshot remains equal to the original;
the 1.0.79 candidate, APK/manifest hashes and available R2 states are unchanged.
No real cancel/restart/delete/publish action was used as a test.

Originals under `.cache/app-admin-ux-20261117/cloud/`:

- `pages-deployment-readback-01.json`: both canonical identities and strict
  runtime-configuration comparisons; full original GETs remain in `private/`.
- `keyring-cloud-admin-02/` and `keyring-cloud-public-02/`: actual upload intents,
  sanitized console logs, raw process outcomes and private Wrangler logs.
- `keyring-cloud-renew-03/`: normal canonical-grant renewal, with the CLI outcome
  recorded separately. A subsequent exact Public GET returns HTTP 200. This is
  working renewal evidence, not a one-month or permanent grant-lifetime claim.
- `keyring-cloud-live-06/result.json`: successful real owner/source/API/business
  readbacks. The corresponding original bodies remain private and project-local.
- `tooling-regression-01.json`: nine passing local wrapper checks. Runtime
  secrets/bindings/preview changes are rejected; only generated hash metadata is
  exempted. Read-only transport retries are bounded; HTTP 401 and mutation
  failures are not retried by that transport helper.
- `write-audit-01.json` and `write-audit-02.json`: original and final controlled
  output/process/Git audits. The first retains the six added-line CRLF warnings
  and a remote-main timeout; the final audit follows the scoped newline fix.
  The external-cache attribution gap below is not converted to PASS.

Preserved interruptions: `inspect-03` misread the Pages DO `service` field as
`script_name`; corrected evaluation confirms the original namespace/class/Worker.
`inspect-04` timed out during a read. `admin-01` performed an unnecessary early
`whoami` check without uploading. `public-01` encountered actual access-token
expiry at its project GET, before uploading. Normal renewal succeeded without
another login. Both later upload CLIs reported completion but did not exit;
only their exact owned trees were stopped after independent canonical readbacks.
Their raw exit-1 outcomes remain intact and are not deployment-failure claims.
`live-04/05` preserve transport failures, including an unreachable unchanged
Worker origin; `live-06` checks the two affected Pages origins instead. A transient
GitHub main-read failure was followed by a successful fresh main comparison.

No Worker/schema replay, new package, API-token creation, secret replacement,
channel publication, delta recreation, device operation or formal acceptance was
performed. All selected outputs stay inside E-Track. This retry launched neither
PowerShell nor Edge and did not clean historical external crash/cache artifacts;
their earlier attribution/authorization records remain separate and unchanged.

The retry's metadata audit additionally observed
`C:/Users/SU/AppData/Local/Microsoft/Windows/PowerShell/StartupProfileData-NonInteractive`
advance from `2026-11-17T14:23:09.520Z` to `2026-11-17T15:23:09.131Z`. The writer
and any content change are unestablished; this turn used cmd.exe and launched no
PowerShell command. The user was informed, and the external file was not changed,
copied or cleaned by the agent. A future investigation should identify the
background writer read-only before proposing path-specific cleanup. Controlled
outputs are project-local, but an unqualified no-external-write audit is not
claimed while this attribution remains unresolved.

## Actions Credential History Check 2026-11-18

Owner requested investigation of why Actions credentials appeared to stop
working. This was a remote read-only history/metadata inspection; no Secrets,
token policies, deployments, workflow dispatches or business data were changed.
Primary and fresh remote main still match `1ff996b6`; existing deployment records
and these findings are LOCAL_PENDING, without commit/push or board-status change.

- Dedicated Pages workflow `305765318` in Trace has six retained runs, all failed:
  five on July 2-5 and latest `43996459438`. E-Track workflow `319417526` has one
  retained run, failed `43978919787`. Queries requested 100 records and returned
  totals six/one; this is not a first-page-only conclusion. Deleted/unretained
  history is not observable and no universal never-worked claim is made.
- November runs fail the original Admin project GET with HTTP 403/code 10000,
  before deployment. July 2/5 job-log requests returned HTTP 410; their precise
  failure causes cannot be reconstructed from unavailable logs.
- Trace token Secret was last updated `2026-06-29T13:49:09Z`, its account Secret
  at `13:49:04Z`. E-Track token/account Secrets were created and last updated at
  `2026-11-07T17:48:02Z` / `17:48:00Z`. Metadata is not a value comparison or proof
  that Cloudflare-side policy, account scope or conditions stayed unchanged.
- Trace run `43969069993`, Android job `133661964252`, successfully uploaded and
  fully read back R2 candidate bytes at `2026-11-16T22:43:07..19Z`. Its exact
  `.github/workflows/build.yml` at `8797520045ddedbdcff9c7fe66a83c7a36882256` maps
  the repository's `CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ACCOUNT_ID` to that step.
  Candidate registration uses `TRACE_DEPLOY_TOKEN` separately. These successes
  are not Pages deployment or evidence that the two credential types interchange.
- At Trace commit `0d9e9210831dddbb60de051834c9ff6975fdfa24`, the old Pages
  workflow's green credential-check step only checked nonempty variables.
  Historical `STAGING-SETUP.md` describes the CI token as R2 read/write and
  distinguishes Pages permissions/browser OAuth. This supports a longstanding
  capability mismatch but does not expose the actual token policy.

Conclusion: no working-Pages-CI-to-broken-Pages-CI transition is demonstrated.
The existing CI input is not qualified for Pages. A longstanding Pages permission,
account-scope or condition mismatch is the leading explanation; exact policy,
expiry and revocation remain unconfirmed. The earlier named local management
token verified active, but its policy read was denied with 403/9109; neither
observation establishes the current encrypted GitHub Secret's status or bytes.
The credential owner can close the remaining gap with a redacted existing-policy
and protected-input mapping, without exposing token values or creating a new one.

Original evidence under `.cache/app-admin-ux-20261117/`:

- `keyring-readonly-01/`: complete retained workflow histories, Secret metadata,
  shipping job metadata and historical Pages workflow.
- `keyring-readonly-02/`: historical setup document, shipping run and preserved
  HTTP 410/transport-error receipts. The recent job-log download timed out.
- `keyring-readonly-03/trace-successful-shipping-workflow.json`: exact successful
  workflow source. Reused `keyring-shiplogs-01/job-133661964252.log` rather than
  downloading the existing 4,717,797-byte original again.
- `keyring-tracelogs-01/` and the earlier Pages failure/sourcecheck receipts
  remain unchanged. `ci-credential-history-20261118.json` records the bounded
  evidence and write audit; the ignored `ci.cjs` adapter and three query lists
  are the only investigation-specific helper changes.

All chosen helper, receipt and document outputs are project-local. The external
PowerShell startup-cache mtime advanced during this investigation from
`2026-11-17T15:38:09.655Z` to `2026-11-17T16:08:12.530Z` at
`C:/Users/SU/AppData/Local/Microsoft/Windows/PowerShell/StartupProfileData-NonInteractive`.
Closeout observed a further mtime update to `2026-11-17T16:23:09.796Z`.
No PowerShell command was launched; the writer and content changes remain
unestablished. The file was not edited, copied or cleaned. This unresolved
observation is not an unqualified no-external-write result.

## Historical Green Pages Run 2026-11-18

The owner correctly challenged the proposal to rerun deployment after the
credential preflight had already failed. That proposal is withdrawn. A deployment
is not needed to diagnose this denial. The requested first question is whether
Actions ever actually deployed these Pages successfully, not whether a job was
green or other Cloudflare operations worked.

Expanded the read-only review beyond `deploy-cloudflare-admin.yml`: current
inventories contain 11 E-Track and six Trace workflows; Trace's main workflow
history contains 45 commits. Both pages of its successful main App-build history
were retrieved (100 + 64); these are run-list observations, not 164 individually
verified deployments. Existing source and receipts were reused.

The decisive older route was inside `cloudflare-update-service.yml`:

| UTC time / source | Original observation |
| --- | --- |
| 2026-07-01 18:29, `397f0a98` | Added automatic `deploy-admin`. Run `28539132115`, job `84608112273`, failed. |
| 2026-07-01 18:37, `7705b36e` | Wrapped `npx wrangler pages deploy` failure in a warning followed by `exit 0`. Run `28539578982`, job `84609678528`, consequently reports success. |
| 2026-07-01 18:49, `01ad9854` | Rollback removed that automatic Pages deployment job. Later green checks no longer deployed Admin Pages. |

The green job retains this original GitHub check annotation:

> Admin Pages deploy unavailable
>
> Cloudflare API token could not deploy Pages. Add Cloudflare Pages Edit permissions to CLOUDFLARE_API_TOKEN, or deploy cloudflare/update-service/admin manually.

The exact source emits this message only after the deployment command returns
nonzero. The annotation and source therefore prove masked failure, not merely a
hypothetical risk in old code. The generic suggestion to add Pages Edit does NOT
prove the token's actual policy; the unavailable command log prevents recovering
that older provider error. Check annotations remain readable even when job-log
downloads have expired.

The briefly added `cloudflare-staging-publish.yml` invoked channel publication,
not Pages deployment. Its only July 1 manual run `28539688427` failed, and rollback
removed the file. Separate successful `Deploy GitHub Pages` jobs, such as
`84609627604`, published the GitHub documentation site, not Cloudflare Admin.
The previously verified R2 upload and candidate registration remain distinct.

Historical conclusion: no genuine successful Cloudflare Pages Actions deployment
has been established in the checked records. There WAS a green Pages job, but it
was demonstrably failed-and-swallowed. Earlier six-plus-one failure totals remain
correct only for the dedicated workflow and must not be presented as an exhaustive
count of all historical Pages jobs.

Current failure localization: the November workflow verifies the exact account ID,
nonempty Secret, fixed Admin target and source SHA before its GET; that GET then
returns 403/10000, before npm or Wrangler. This is a Cloudflare authorization
denial for the CI input, not missing authority to launch Actions. The exact token
policy/conditions and equality with the named local source remain unconfirmed.
No token replacement, permission expansion, deployment or workflow dispatch was
performed. Existing local Pages success and all original denials are preserved.

Evidence under `.cache/app-admin-ux-20261117/`:

- `keyring-readonly-05/07/08/09`: inventories, historical source diffs, complete
  requested run lists, original job/check metadata and the decisive annotation.
- `keyring-readonly-09/trace-pages-green-annotations.json` and
  `trace-pages-green-jobs.json`: warning and green job outcome, kept together.
- `keyring-readonly-07/trace-manual-staging-added.json`: exact failure-swallowing
  source at full commit `7705b36e652e5566c8d11aaaa6443bab44d52805`.
- `keyring-readonly-06/failure.json`: local query validation rejected a literal
  double-dot date range before the query batch. It is not an Actions/Cloudflare
  failure. A new exclusive batch used the exact July 1 date instead.
- `ci-pages-green-history-20261118.json`: bounded summary. The existing ignored
  `ci.cjs` received only the same-repository `check-runs` read allowlist addition;
  syntax and actual annotation GETs passed. New queries/receipts and document
  changes stay project-local. No new rule, main-board status change or commit/push.

## Actions Repair And Owner Input 2026-11-18

The owner requested both diagnosis and resolution. Reused the named local
provisioning reader for the repository-source token's exact policy, without
exporting it or creating a credential. `cloud/keyring-cloud-policy-01` verifies
the source token active, but user-policy GET returns 403/9109. The reader also
verifies active. `keyring-cloud-policy-02` checks the documented account-policy
route: reader GET returns 403/9109; target-token self-read returns 404/1003.
These are policy-read limits, not proof of expiry, revoked authority or a missing
credential. Full responses remain private. Owner-side inspection of the existing
token's Pages permissions, account scope and conditions is still required.

Implemented the separate workflow readback correction locally: compare all
production/preview runtime fields strictly while excluding only the provider's
generated `wrangler_config_hash` field at each environment root. Keep the original
Secret names, deployment entry, source/identity checks and hard failure gates.
No new Token, Secret or separate check-only workflow was introduced.

Added `tests/ota/test_pages_deployment_workflow.mjs`, which evaluates the actual
inline workflow comparator and covers metadata-only changes, every binding type,
Access slots, preview changes, missing environments, nested same-name variables
and input immutability. The existing Cloudflare checks workflow includes it and
its affected paths. Local combined Node tests: 33 PASS, zero failures/skips;
both workflow YAML files and the Python adapter parse. Original test output is
`.cache/app-admin-ux-20261117/pages-workflow-tests-20261118.json`.

Changes remain LOCAL_PENDING, uncommitted/unpushed. No Cloudflare mutation,
Actions dispatch, deployment, App build, Worker/schema replay or channel change.
The remaining account-side step must inspect/correct the existing CI token,
preserving its working R2 permissions; token values do not belong in chat.

## Named Pages Credential Migration 2026-11-18

The owner identified and updated `e-track-ci`, then requested using it for the
Pages deployment credential with a matching name. Exact Admin/Public reads now
pass through that token's registered protected input, recorded in
`cloud/keyring-cloud-pagesprobe-04/05/` under `.cache/app-admin-ux-20261117/`.
The older repository-source token is a different local input; its bytes do not
establish GitHub's previous encrypted Secret value.

GitHub excludes hyphens and stores Secret names uppercase. The new repository
Actions Secret is therefore `E_TRACK_CI`, while Cloudflare keeps `e-track-ci`.
The installed GitHub CLI successfully set this exact Secret from the protected
local input via stdin. No token value entered argv, logs or a new local file.
Metadata readback records creation/update at `2026-11-17T18:01:05Z`, with all
other Secret metadata unchanged. Original receipt:
`.cache/app-admin-ux-20261117/cloud/keyring-cloud-githubsecret-01/result.json`.

The local Pages workflow's four credential bindings now use `secrets.E_TRACK_CI`
while retaining the standard `CLOUDFLARE_API_TOKEN` environment variable. The
earlier narrow runtime-hash comparison fix remains intact. Combined Public,
Access and Pages regressions: 34 PASS, zero failures/skips. Six fixture-only
adapter checks cover correct input/target, existing Secret update, actor/token
rejection, CLI failure and changed metadata; the adapter syntax check passes.

The old repository `CLOUDFLARE_API_TOKEN` is still used by App/MCU R2 release
workflows and was not changed or deleted. No original Trace or rehearsal
environment Secret was modified. The Cloudflare token was not created, rotated
or renamed, and its policy was not changed by the agent.

Secret creation is complete, but the Pages workflow and documentation remain
uncommitted/unpushed on primary main `1ff996b6`. Remote Actions still uses the old
workflow reference until the owner authorizes publishing the bounded changes.
No workflow dispatch, deployment, package build, channel or device operation was
performed. Controlled edits and receipts remain within the primary project root.

## Latest App Delta Failure Readback 2026-11-18

Read-only diagnosis after the owner asked about the latest failed delta and the
Trace/E-Track split. The newest job is Android 104 -> 105, attempt 1,
`delta_e698035874eb9d13136c3d11b1cc7258c399ca5a5d49e44b7baac838c8f4e8a8`.
Its exact Trace run is `44128076257`, workflow source
`8f6d2ab64b1c400811613ae8540c15e0bdf28d9f`, branch
`dev/admin/original-delta-20261112`. GitHub records failure at
`2026-11-17T16:39:31Z`; D1 was reconciled to `CI_BUILD_FAILED` at
`2026-11-17T18:15:46Z`. The preceding Android 103 -> 104 run `43932189981`
remains successful and was not repeated.

Checkout, Node setup and xdelta preparation succeeded. The generation step
failed immediately. Its only emitted delta receipt is `failure.json` with
`stage=admission`, `errorCode=CI_ADMISSION_FAILED`, `claimOutcome=not_sent` and
`automaticReplay=false`. No job/claim/proof/upload/completion receipt was emitted.
This locates failure before claiming/downloading/generating, but does not identify
the underlying exception.

Important correction: the printed `BACKEND_UNAVAILABLE` and "Firmware operation
failed" text comes from the generator's `firmware-cli.mjs` fallback, not a proven
Worker response. The original exception name/message/cause and response metadata
were not retained. Do not claim HTTP 503, token expiry, permission rejection or
a signing/patch failure from this generic wrapper. Exact root cause remains
unconfirmed; improving bounded, redacted admission diagnostics is needed before
claiming recovery. No diagnostic workflow or job retry was dispatched.

The actual Trace workflow reads generator source from E-Track commit
`e669393dc4a263cdfd0f159ab62e008e302b41cd`, while using Trace's existing
`TRACE_DEPLOY_TOKEN` and original payload-signing key. These two generator/CLI
files are unchanged in the reviewed `59131a3e` source. This is a credential
placement decision, not a technical requirement that App deltas run in Trace.
Moving execution to E-Track would require preserving the original credentials
and updating workflow/attempt bindings, not just changing a repository string.

Originals under `.cache/app-admin-ux-20261117/`: `keyring-readonly-10/` binds the
latest run lists, `keyring-readonly-11/` holds the exact job steps/workflow source,
and `keyring-readonly-12/` records log/annotation retrieval. The raw log remains
private at `cloud/private/keyring-readonly-12-trace-latest-log.log`.
`cloud/keyring-cloud-deltainspect-01/result.json` records three SELECTs with zero
rows written and no database change. `keyring-cloud-deltainspect-02/result.json`
records Worker version `54ad084f` still active, correct D1 binding and enabled
persisted logs; fetched code confirms the generic CLI message is not its HTTP
error body. This is not evidence of a historical request reaching that Worker.
No Cloudflare resources, credentials, task states, artifacts or channels changed.
The diagnosis record remains LOCAL_PENDING; no commit/push or deployment.

## List Actions And Settings Follow-Up 2026-11-18

The user approved the consolidated implementation with "那就做吧". Work reused
`.worktrees/app-admin-ux-20261117`, branch
`dev/flutter/app-admin-ux-20261117`. The final development source is
`cbdf99514f48d1f0f85e77c31e0ad8592a84b1c9`, pushed using the existing authorized
Eitan-S-23 development route. Its 20-file delta from the prior deployed
`59131a3ef0712d46e7b17694d585371b751ab7ba` is limited to this App/Admin/backend
batch, tests and component documentation. Primary local and fresh remote main
remain `1ff996b6dbd80eb18179551b6189975503be9c37`; these root records are
LOCAL_PENDING, not published main progress.

### Implemented Behavior

- App/MCU versions, notifications, announcements and generated delta files use
  the existing SVG trash icon to enter deletion mode. Checkboxes, current-page
  selection, counts and the delete action are adjacent to their lists and hidden
  outside that mode. Workspace/list/platform changes clear selection. Existing
  role gates, confirmation, partial results and retained failed selection remain.
- Announcement batch deletion serially uses the existing per-item endpoint,
  preserves audit history and now scopes deletion lookup to the configured App.
  Notification deletion only dismisses that actor's display records; it does not
  delete files or cancel tasks. Announcement pages contain six items.
- Generated App/MCU delta files have individual selection and batch deletion.
  Only completed, disabled supplemental files are admitted. Namespace, size,
  SHA metadata, ETag, shared references and App asset identity are checked before
  CAS/audited retirement. R2 deletion happens after retirement; a partial failure
  stays `deleting` and an explicit confirmation can resume that same file. The
  successful build status, attempt, original result/proof, original APK/ETU,
  release/channel pointers and task history remain intact. Deleted files cannot
  be re-enabled or silently recreated. Job/file pages contain eight items.
- "核对构建结果" is now "同步" / "Sync". It runs directly without asking for a
  reason; the server provides an audit reason and still enforces Access, CSRF
  and revision checks. Cancel/restart controls no longer silently depend on the
  UI having a GitHub URL. An explicit action looks up the exact current run
  afresh, reports missing/ambiguous matches and never restarts before confirmed
  cancellation. The user's already-working associated-run behavior is retained.
- App and MCU version lists allow native outward scroll chaining at both ends,
  including continued mobile swipes. Existing overlay swipe/cancel and
  long-press suppression behavior is retained.
- The manual permission guide now lives under Help & Feedback, opening the
  existing `/companion-setup` page. The standalone profile/device shortcuts are
  removed; automatic first-use setup is unchanged. App Settings initially shows
  only the statistics entry. Selecting it opens the existing consent/details
  dialog, including explanations and last-report state. This keeps the initial
  view compact even for users already opted in and does not alter saved consent.

### Development Verification

| Check | Original Evidence | Outcome |
| --- | --- | --- |
| Worker production-logic and API host tests | task worktree `.cache/ux-host/worker-host-06/` | 505 PASS, 16 files; SQLite/R2 host doubles, not live Cloudflare |
| Worker TypeScript | task worktree `.cache/ux-host/worker-check-06/` | PASS |
| Admin TypeScript | task worktree `.cache/ux-host/admin-check-05/` | PASS |
| Public Pages TypeScript | task worktree `.cache/ux-host/public-check-01/` | PASS; same pinned TypeScript 6.0.3 and Workers types 4.20260628.1 reused from Worker dependencies |
| Full Admin Playwright | task worktree `.cache/ux-host/admin-test-14/` | 255 PASS; 8.6 minutes; browser/API mocks, not live owner mutation |
| Full Flutter development CI | [44171579034](https://github.com/Eitan-S-23/E-Track/actions/runs/44171579034) on `cbdf9951` | Ubuntu and Windows jobs both SUCCESS |

Flutter analyze, full tests, additional candidate tests and required workflow
steps pass on both hosts. Ubuntu records 906 passed / 16 skipped; Windows
records 859 passed / 63 skipped. Each host separately passes eight candidate
tests. Both resolve Flutter 3.47.9, framework
`c197ca5199e9ee5661e865596c9c07294dfab51c`, Dart 3.13.7 and engine
`89c39edfdfae2949f6806e4a315c0c08522238b7`.
Final job logs and exact job/run metadata are preserved at
`.cache/app-admin-ux-20261117/keyring-logs-11/`.

Original failed feedback is preserved, not relabelled or removed:

- `44168230202` on `fe0e75c8`: both hosts failed because two new
  `TraceDialog.close` calls omitted the required dialog context. Commit
  `3b4c3dfc` uses the owning dialog's Builder context, not the underlying page,
  and extends tests to verify the profile route survives both transitions.
  Original logs: `keyring-logs-07/` under the task's root cache.
- `44170084859` on `3b4c3dfc`: Ubuntu passed; Windows timed out during the
  180-second Flutter SDK clone before analysis/tests. Cleanup was confirmed.
  Original logs: `keyring-logs-08/`. Final source `cbdf9951` adds API authority
  regressions and the benchmark record; both hosts passed without weakening
  timeouts, assertions or workflow failure handling.
- Earlier UI feedback in `admin-test-07` through `admin-test-11` exposed stale
  disabled controls and editor/draft rerender defects. These were fixed before
  the 253-test full pass, 20-test targeted follow-up and final 255-test full pass.
  The final Admin source/tests are unchanged across `fe0e75c8..cbdf9951`.

Security regressions exercise the real Access facade for publisher-denied
delta deletion, unauthenticated/viewer/CSRF/origin denial and app-scoped,
audited announcement deletion. Business-logic tests also cover stale revisions,
enabled/in-progress files, changed R2 objects, partial deletion, no restoration,
original-file retention and fresh exact run lookup. This is implementation
self-testing, not independent acceptance. Host logs retain Node's experimental
SQLite warnings; Playwright retains its NO_COLOR/FORCE_COLOR warning.

### Same-APK Algorithm Result

The existing MCU bsdiff + LZMA core can operate on APK bytes. On the same original
signed 104 -> 105 APK pair, baseline VCDIFF flags produced 7,169,810 bytes and
the MCU core with `-aes 0` produced 2,328,597 bytes, a 67.5% reduction. Both,
plus the larger 7,256,484-byte tuned VCDIFF variant, reconstructed the exact
target SHA-256 and size. The original APKs were unchanged. Native desktop decode
was about 0.233 seconds versus 2.419 seconds; these are not phone measurements.

Original inputs/download identities, tool hashes, arguments, outputs and logs
are in `.cache/app-admin-ux-20261117/keyring-benchmark-01/`,
`keyring-benchmark-02/` and `delta-benchmark-01/result.json`. The committed
comparison and compatibility limits are in
`app/bluetooth_flutter_Trace/cloudflare/update-service/docs/VERSION-INVENTORY-DELTA.md`
at `cbdf9951`. Do not rerun this successful comparison just to consolidate it.
The xdelta tool was official 3.2.2 with the project's current flags, not a claim
about the exact historical GitHub binary. The earlier admission failure remains
separate from this successful offline codec comparison.

The production App format is still VCDIFF. A bsdiff/LZMA rollout still needs
client decoder integration, explicit format/capability negotiation and actual
phone memory/latency qualification. Keep signed-target verification and
compatible VCDIFF/full-package fallback for old clients. No firmware capsule,
encryption change or unqualified patch format was sent to installed Apps.

### Pre-Delivery Checkpoint And Write Boundary

Standard Android APK and Windows EXE build verification: NOT_RUN for this new
batch. No version/signing change, release, candidate ingestion, channel
publication, installation or device operation occurred. No real deletion or
task cancellation/restart was executed as a test. Independent acceptance,
main integration and this batch's backend deployment remain pending.

Apply `0015_delta_file_deletion.sql` before deploying the new Worker, Admin and
Public Pages handlers. The previous 0014 migration and `59131a3e` deployment
were not repeated. The already-created `E_TRACK_CI` Secret and locally pending
Pages workflow migration were preserved, not rewritten or dispatched. Root
owns the separately authorized exact-source APK/EXE build and Actions deployment
steps; the remaining codec rollout is a distinct client-compatibility change.

Canonical path checks covered source/docs, helpers, Git index/objects/refs/logs,
all selected receipts/downloads/benchmark outputs, browser/test/npm caches and
native temporary paths inside `D:/github/my/E-Track`. No active headless browser,
workerd or esbuild remained after the local suites. The benchmark's temporary
`temp_diff.data` removal was confined to its checked output directory; no
original or historical evidence was cleaned. Audit receipt:
`.cache/app-admin-ux-20261117/write-audit-20261118-followup.json`.
Named external metadata checks are not whole-machine write tracing. The known
PowerShell startup-cache mtime changed, attribution remains unestablished, and
this follow-up invoked no PowerShell or ordinary browser launch. That external
file and prior OAuth/crash artifacts remain untouched; no external cleanup is
claimed or performed.

## Authorized Delivery Continuation 2026-11-18

After the development closeout, the user explicitly requested continuing without
stopping for avoidable approval and granted the authority needed to finish.
This supersedes the preceding pending-authorization wording for scoped main
integration, original-signed APK/EXE build/candidate delivery and the existing
Cloudflare Worker/D1/Admin/Public deployment. It does not request live data
deletion, channel promotion, a replacement signing identity or device changes.
Reuse the same reviewed implementation and the already-created `E_TRACK_CI`
Secret. The next shipping version is `1.0.80+106`; fresh release inventory found
no existing draft or published reservation. The previous `1.0.79+105` artifacts
and successful delta jobs remain untouched.

## Follow-Up Delivered Through Actions 2026-11-18

### Packages And Main

- Implementation `cbdf99514f48d1f0f85e77c31e0ad8592a84b1c9` was versioned as
  `8011709906af2dd8a9178f458759d286b7f89f9f`, `1.0.80+106`, and pushed once to
  the existing `release/candidates` route. No existing release tag was replaced.
- E-Track [44175714326](https://github.com/Eitan-S-23/E-Track/actions/runs/44175714326)
  and original Trace [44175951793](https://github.com/Eitan-S-23/Trace/actions/runs/44175951793)
  both conclude SUCCESS. Android APK and Windows EXE/ZIP jobs pass. Firmware is
  skipped. Formal-build tests also record Ubuntu 906 PASS / 16 skipped and
  Windows 859 PASS / 63 skipped. Trace hosts the existing signing/distribution
  workflow; the built App source is the exact E-Track commit above, not the
  Trace workflow revision `8797520045ddedbdcff9c7fe66a83c7a36882256`.
- [v1.0.80](https://github.com/Eitan-S-23/Trace/releases/tag/v1.0.80) is a prerelease,
  not GitHub latest. APK package `com.wen.gaia.gaia`, original signer fingerprint
  `3cecee6330a930e020b454b6d4a79568f4494ca324ae7bcf2c1914e51b04ab47`,
  ARM32/ARM64 libraries and compiled backend/BLE V2 settings are verified. APK
  size is 48,486,828 bytes, SHA-256
  `d5ac06997b4dcd6b3dfcde7d8f40e25d12fc3c794322edd9815c3080a535d97d`.
- R2 upload/full readback and candidate registration pass. Live D1 independently
  confirms `rel_trace_android_v1_0_80`, version 106, `candidate`, with that APK
  and its manifest available under `trace/releases/106-v1.0.80/`. No Stable/Beta
  promotion or device installation was performed.
- Main `e7b990c714fb32954e209c8d3396c198c7b3a700` integrates only the 21-file
  App/backend/version delta and five deployment-support files. Existing newer
  App governance, unrelated firmware and frozen evidence remain intact. Exact
  App build inputs match `80117099`; the main integration skips duplicate App
  builds. Adapter-only repair `28459a89fcd6792611052cb601b231bb947bcc6d` changes
  no App or serving-handler inputs and needs no additional APK/EXE build.

Package originals: `.cache/app-admin-ux-20261117/keyring-ship-02/`,
`keyring-shipstatus-14/`, `keyring-shiplogs-10/` and `keyring-release-02/`.
Integration originals: `keyring-mainplan-04/`, `keyring-mainapply-02/`,
`keyring-maincommit-02/` and `keyring-supportfix-01/` in the same parent.

### Backend And Live Verification

Native backend CI [44181334359](https://github.com/Eitan-S-23/E-Track/actions/runs/44181334359)
passes on the integrated source. After the adapter repair,
[44184804298](https://github.com/Eitan-S-23/E-Track/actions/runs/44184804298)
also passes on `28459a89`: 463 native Worker tests in 13 files, 255 full browser
tests, 60 deployment/Public/Access contracts and Worker/Admin/Public TypeScript.
The earlier 505-test host suite includes 42 host-only cases; do not report all
505 as native Workers execution. Logs are in `keyring-logs-12/15/`; final local
support regressions are in `delivery-host-04/`.

Actions [44186088340](https://github.com/Eitan-S-23/E-Track/actions/runs/44186088340)
successfully uses `E_TRACK_CI` for all three deployed components. This is the
working GitHub Actions route requested by the owner, with no local-source upload
or fresh OAuth fallback. The existing token, legacy R2/Trace/rehearsal credentials,
Access policy, runtime secret slots and workflow references were not replaced.

| Component | Verified Identity |
| --- | --- |
| Worker version | `153bfa20-6c68-488a-93cc-1f027cc808d0` |
| Worker deployment | `d4bc9259-3496-42d9-a518-b8fc4a1627f7` |
| Admin Pages | `a5afcc59-b12e-452b-a5a4-0ba0d2aa7def` |
| Public Pages | `ec8b50c6-b436-41ca-a7b6-0a309a7fef13` |
| Deployed source | `28459a89fcd6792611052cb601b231bb947bcc6d` |
| D1 migration | `0015_delta_file_deletion.sql`, applied once; asset state and both guards verified |

Separate readbacks verify original Worker settings and schedules, both Pages
production/preview configurations, four channel pointers and all 37 existing
delta job rows against the original pre-deployment snapshot. Real existing
Access session returns `owner`. Served HTML and all eight JS/CSS files match
committed source bytes, not Windows checkout line endings. Admin releases,
announcements and the new delta candidate return 200; the candidate is version
106 with original signing and dispatch configured. Public Android, Windows and
iOS announcement APIs all return 200. No real deletion, cancellation or restart
was used as a test; UI/mutation regressions remain host/native/browser self-tests.

Readbacks: `cloud/keyring-cloud-delivery-01/03/04/`; sanitized Actions artifacts:
`keyring-artifacts-02/`; complete deployment log: `keyring-logs-16/`, under the
task's root cache. Private provider/session snapshots remain private and were
not uploaded. The first failed Actions receipt is preserved as described below.

### Environment-Label Failure And Prevention

1. Root cause: an implicit configuration assumption and test-coverage gap.
   Flattening `env.staging` preserved bindings but removed Wrangler-generated
   `cf:service=trace-update-service-dev` and `cf:environment=staging` labels.
2. Actual failure: run `44183120496` applied 0015 and uploaded correct Worker
   source as `bf1c50db-0105-4c54-a1f5-9aab1fbc24e2`, then its strict runtime check
   failed and Pages was skipped. Source, variables, secret slots, resource
   bindings, schedules and channel/job state were correct. This was not a token
   denial; neither a successful CLI exit nor a blanket tag exclusion was a fix.
3. Repair: retain the original named environment and use `--env staging`.
   Missing standard labels can be restored from the pinned source identity;
   conflicting labels and every other setting/custom tag remain strict.
   Tests cover the grouping, missing/conflicting labels and already-applied SQL.
4. Actual recovery: the successful run reports `migrated=false`, no pending
   migrations, `environmentLabelsRestored=true` and `runtimePreserved=true`.
   `configurationUnchanged=false` is relative to the intervening broken-label
   snapshot, not a hidden failure. Final readback matches the original complete
   configuration, including both labels. Only the affected Worker configuration
   was repaired; SQL and the successful App build were not repeated.
5. Reuse lesson: deployment adapters must preserve vendor environment semantics,
   not just copy apparent values. This differs from Pages' generated config hash.
   The domain guidance is now in root `CLOUDFLARE-DEPLOYMENT.md`, the existing
   canonical deployment guide; no new Trellis tree or replacement platform was
   created. Original failure logs/artifacts remain in `keyring-logs-14/`,
   `keyring-artifacts-01/` and `cloud/keyring-cloud-delivery-02/`.

### Remaining Boundaries

The user-facing interface/settings implementation, signed App build/candidate,
main integration and requested Actions deployment are delivered. Formal independent
acceptance and physical device observations are not claimed. The App codec is
still VCDIFF: the completed 104 -> 105 comparison is not a decoder/format rollout.
Client integration, old-client negotiation/fallback and phone memory/latency
qualification remain a separate change. No successful historical delta, old
release, channel pointer or original signing identity was replaced.

All selected local outputs remain under `D:/github/my/E-Track`; no external
cleanup or ordinary browser/device operation occurred. Existing root records
and unrelated untracked files were preserved. Delivery audit:
`.cache/app-admin-ux-20261117/write-audit-20261118-delivery.json`.
