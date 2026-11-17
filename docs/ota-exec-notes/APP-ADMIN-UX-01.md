# App And Admin UX Improvements

## Entry

- User requested implementation on 2026-11-17 after the consolidated list.
- Owner: root implementation session. Status: original-signed packages and
  bounded App/backend main delivery complete; Worker/schema deployed. Admin
  and Public Pages deployment remains pending reconciliation of the existing
  applicable publishing credential. The prior login-only conclusion is withdrawn.
- App baseline: delivered 1.0.78 / 104, commit
  `b15017a30413e5bf10ea32a19008503c8bd922ae`.
- Primary main: `990d8b4d73bde3cdd37316c66800a98481bed38b`.
  Existing main board/index/review edits are preserved and remain LOCAL_PENDING.
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
