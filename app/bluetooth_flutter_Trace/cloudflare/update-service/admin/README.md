# Trace Update Admin

An Access-protected Pages Functions facade serves a shared App and MCU release
console. The lightweight HTML/JavaScript UI uses the same self-hosted
`public/admin.css` design system for both workspaces; no framework migration or
external font/CDN dependency is required.

The shared App/MCU distribution tabs and operator-selected delta dialogs are
documented in [Version Inventory And Delta Jobs](../docs/VERSION-INVENTORY-DELTA.md).
Counts describe reporting installations, not people or globally unique MCUs.
Dispatch and supplemental distribution have separate configuration gates;
showing a management dialog does not mean a real delta job has been qualified.

No direct admin mutation route is exposed on the standalone Worker. During the no-custom-domain phase, mutations go through this Pages Functions same-origin facade.

## Shared UI And Keyboard Behavior

Both workspaces use warm light surfaces, charcoal text and a single muted green
accent. Long labels, tags, filenames and hashes wrap instead of clipping. The
App's former 3D carousel is a compact version list, with six rows per page and
a bounded inner scroll area. More releases never stretch the whole workspace.
Scrolling never changes the selected version or its notes. Arrow Up/Down moves
explicit selection across page boundaries, Enter opens that version, and `/`
or Ctrl/Cmd+K focuses search when no editor or overlay owns the keyboard.

Search, language and refresh stay in the sticky top toolbar. App versions and
announcements are peer tabs directly below it, supporting Left/Right/Home/End
navigation. Each App tab and each MCU tab retains its own search query.
Announcement drafts survive tab, search and language changes in actor-scoped
memory; an unsaved indicator and explicit discard control remain available.
Successful saves clear drafts, failures retain them without automatic retry,
and actor changes discard them. The announcement API and role gates are unchanged.

The shared resource ball remains fixed and draggable on both workspaces. Its
desktop/mobile positions are saved separately using the existing local-storage
keys and clamped into the viewport. Tap/click opens resource usage; Shift+arrows
moves the ball from the keyboard. Drag/cancel gestures do not activate the panel
or swallow the next tap. Decorative content has one button hit target, and touch
taps use their completed pointer gesture rather than relying on a browser's
optional post-drag compatibility click. Dialogs and mobile navigation hide and
inert the ball so it cannot obstruct their controls.

Dialogs and mobile navigation contain Tab focus and make the underlying
workspace inert. Escape closes only the top layer and restores a usable focus
target. Enter follows the focused native control: it inserts a newline in the
operator-reason textarea and activates Cancel when Cancel has focus. It is not
a global confirmation shortcut. Reduced-motion preference disables UI animation.

Unsaved App notes are held in actor-scoped memory while selecting other versions,
closing the panel or changing language. The unsaved indicator and discard action
are explicit. Successful saves clear the draft; failures retain it without an
automatic retry. An actor change clears App drafts, viewer inputs are read-only,
and leaving the page with unsaved notes asks the browser to warn the operator.
These are not persistent drafts and do not change the App notes API's existing
concurrency semantics; MCU notes keep their separate expected-notes/CAS contract.

## Current API

### Sheet Gestures And Task History

App details, MCU details, delta management and Tasks share a drag owner. The fixed
header accepts downward and horizontal drags; the body accepts a downward drag
only if that touch started at scroll-top. Short movements rebound. Controls,
nested scrollers, text selection, upward scrolling and multi-touch retain their
normal behavior. Busy submissions and an overlaid confirmation block sheet drag.
Drafts are retained, not submitted or discarded by closing a sheet.

Same-document history gives each visible modal layer one Back step. Browser/Android
Back cancels the top confirmation or closes the top sheet, without mutation.
Explicit closure consumes that layer too, so the next Back reaches normal browser
history. Forward never replays a business action. Browser-reserved forward/edge
gestures cannot be universally overridden by page code; no global touch handler
is installed on the workspace when no modal is open.

The fixed Tasks toolbar button lists own App/MCU delta jobs in compact pages,
actual progress stages, unread results, and opt-in system reminders. Closing a
delta dialog or refreshing the page never cancels/restarts the server job. See
`../docs/VERSION-INVENTORY-DELTA.md` for the durable event/push model and limits.
Local UI tests use mocked business routes; the service-worker integration uses a
loopback server, Chromium push-event injection and an explicit mock OS notification
sink. Fetch, IndexedDB and the production script run in a real worker; this is not
proof of OS delivery or a real package generation. The Windows Headless Shell
denies notification permission, so real vendor/OS delivery remains a separate check
in a supported browser after its user grants notification permission.

Push enrollment has three separate boundaries: notification permission, the
browser's actual PushManager subscription, and the actor-bound server record.
An enabled label requires the latter two to match by endpoint SHA-256 with a
current expiry. A cached localStorage flag is not evidence of registration.
Page load/refresh checks subscriptions without requesting permission or changing
them. Explicit Enable reuses an existing matching-key browser subscription;
missing local/server metadata must never cause automatic unsubscribe.

Activity responses are tied to the subscription revision at request start so
an older response cannot undo a later successful enable/disable. Task refresh
cannot release another pending enrollment's busy lock. Browser/provider and
server-registration errors remain in the reminder settings independently of
task-fetch errors; successful task polling must not hide an enrollment failure.
The enrollment regressions in `test/version-operations.spec.ts` mock the browser
push boundary explicitly and do not establish actual vendor/OS delivery.

Notification clicks focus an existing same-origin Admin document and require a
MessageChannel acknowledgement of the open-Tasks intent. The page retains that
intent through loading, suspension and an active confirmation/operation; it does
not discard a draft or interrupt a mutation. A missing, non-Admin or unresponsive
client falls back to the absolute original-origin `/?tasks=1` URL. The URL intent
is consumed only after Tasks opens. Existing registrations are updated in place
on an authorized page visit, never unregistered to install a click-handler fix.

The Tasks badge counts unread results only; active jobs use the separate icon
state and accessible label. Notifications page in groups of six. A result is
marked read when clicked or at least 75% visible in the foreground task scroller
after a 500 ms settling delay. Hidden/inert panels, background pages and unseen
pages do not consume results. The server must acknowledge each read before the
badge changes; failed reads retain an error and do not spin an automatic retry.
Older activity responses cannot overwrite an acknowledged read. The explicit
Mark all read action retains the existing observed-ID cursor, not a future ID.

Migration `0010_notification_read_state.sql` must precede the Admin deployment.
It adds per-notification read timestamps without changing prior cursors, tasks,
subscriptions or deliveries. The API contract and error cases are documented in
`../docs/VERSION-INVENTORY-DELTA.md`. Tests use mock window APIs for notification
click routing; they do not simulate a physical Android notification tap.

The root page loads the current Access session, Android channels, and Android releases. It supports release note edits, beta/stable publish actions, disabling unpublished releases, and viewing R2-ready versus fallback-only asset counts through the API below.

- `GET /api/admin/session`
- `GET /api/admin/channels?appId=trace&platform=android`
- `GET /api/admin/releases?appId=trace&platform=android`
- `POST /api/admin/channels/:channel/publish`
- `POST /api/admin/releases/:releaseId/notes`
- `POST /api/admin/releases/:releaseId/disable`

For the Android API above, `stable` publish/rollback and disable require `owner`.
`beta` publish/rollback and release note edits require `publisher` or `owner`.
Read-only endpoints allow `viewer`.

Selecting an older Android release explicitly changes the action and confirmation
to channel rollback. The existing publish endpoint receives `rollback: true`
only after confirmation; newer and initially empty channels use `false`.
Stable still requires typing `stable`. Current/equal-code targets, unavailable
channel identity, disabled/archived releases and stopped latest channels are
locked. CAS revisions, CSRF and server-side role checks are unchanged. Rollback
only changes the offered channel version; already-updated clients do not
downgrade and need a higher `versionCode` for a corrective update. A failed or
uncertain rollback is never automatically repeated; refresh before confirming
a new intent.

## Firmware Controls

The firmware tab consumes the multi-asset DTOs defined by
`OTA-XC-HTTP-ADMIN` in `docs/ota-cross-system-contracts.md`. Its fixed routes are:

- `GET /api/admin/firmware/releases?appId=trace&deviceModel=e-track-at32f435`
- `GET /api/admin/firmware/channels?appId=trace&deviceModel=e-track-at32f435`
- `GET /api/admin/firmware/history?appId=trace&deviceModel=e-track-at32f435`
- `POST /api/admin/firmware/channels/{stable|beta}/{publish|retract|stop-latest|resume-latest|stop-downloads|resume-downloads}`
- `POST /api/admin/firmware/releases/{releaseId}/notes`
- `POST /api/admin/firmware/releases/{releaseId}/{disable|recovery-download|delete}`

The existing Phone / MCU navigation shares the original App Admin's session,
visual language and resources panel. MCU management uses a compact selectable
version list and an explicitly opened detail dialog, with status/channel filters, scoped text
search, version/date/package-size sorting, version comparison, compatibility
requirements, build provenance and complete wrapping image/package hashes.
Versions, Channels and History are peer tabs, pinned below the common toolbar.
The version rail renders six compact rows per page within a bounded height;
filters and sorting reset the page, and Up/Down selection crosses page boundaries.
Channel controls start expanded in their own tab, with a persistent selected-target
summary and a return-to-versions action. Tab navigation never changes that target.
Version, channel and loaded-history searches are independent; a channel/history
search cannot silently select a different release. The history list is bounded
and still uses the existing cursor-based load-more route. History is first read
when its tab is opened, not on every catalogue visit.
The resources panel opens from the restored shared movable resource ball.
Its placement and initial focus are synchronous with opening. Deferring them to
an animation frame can briefly expose the panel below the viewport or steal
focus after the operator has already closed it. A delayed-frame regression keeps
both the panel bounds and Escape focus restoration covered.
App and MCU details likewise establish focus/inert/keyboard ownership during
opening, not in a later animation callback; immediate Escape must not be lost.
Selecting a firmware version opens the same fixed dialog surface used by App
versions: a centered overlay on desktop and a bottom sheet on narrow screens.
Details never occupy a column beside the list or a section underneath it.
The title and close button stay in the shell's fixed header while App or MCU details
scroll below in a separate inner container, so the button cannot cover package text.
The close control remains directly clickable at the upper-right corner at the bottom
without scrolling back to the title. Reopening resets the inner scroll position.
The close button, backdrop and Escape return focus to the selected version.
The details scroll independently and the dialog traps Tab; the underlying workspace and
resource ball are inert. Publication/release actions hand off to the existing
explicit confirmation dialog. A note-edit confirmation owns focus above the
details, and cancelling it returns to the retained draft. Closing details never
submits an operation or discards a note draft.

Browser regressions explicitly open populated App/MCU detail dialogs, compare
their responsive geometry, check scroll/focus isolation and all close paths,
and retain existing API/role/CAS/reconciliation assertions. An empty catalogue
or a no-overflow check alone is not evidence of matching detail interactions.

Update-note editing requires publisher or owner. The exact JSON body contains
`appId`, `deviceModel`, `releaseNotes`, `expectedNotes` and nonblank `reason`.
Notes are limited to 8000 characters and reasons to 2000. The server compares
`expectedNotes` against the stored notes inside the database update and commits
the update and audit atomically. A stale value returns `CAS_CONFLICT`; disabled
or archived releases return `RELEASE_DISABLED` or `RELEASE_ARCHIVED`. A no-op
returns `idempotent: true` without another audit. Version/build identity, package
bytes and hashes are not editable through this route. No new migration is needed.
The UI retains an unsaved draft after conflict or unknown network results,
shows the server's current notes, and requires explicit reconciliation and a new
confirmation before another write. It never automatically resubmits the notes.

History permits viewer access and accepts optional `releaseId`, `limit` (1..50,
default 25), and `cursor`. Unknown or duplicated query parameters are rejected.
The response contains `history` and nullable `nextCursor`; the cursor is the
URL-encoded `YYYY-MM-DD HH:mm:ss|audit-id` pair. Results are ordered by timestamp
and audit ID descending, scoped through the actual firmware release/asset/channel
rows. A release filter also includes channel changes referencing that release
before or after the operation. Each record exposes its actor, action, time,
reason, request ID and whitelisted before/after values, never signed URLs,
signatures or storage keys. A history read failure does not disable otherwise
valid version management. Historical records and file deletion remain distinct
from deleting a version identity.

The release list includes `capabilities.recoveryDownload`. The Admin derives it
from its actual signing and public-origin configuration; without them the UI
disables recovery download and explains why. An empty firmware catalogue is
shown honestly, with the existing verified CI registration route identified as
the source of candidates. No synthetic package is created to populate the page.

An empty registered catalogue, no filter matches and failed reads have distinct
messages. The empty state links the existing firmware workflow and explains the
normal GCC build, verified package registration and subsequent manual channel
publication steps. A successful ordinary firmware build only creates build
artifacts; it does not register a release. Isolated benchmark packages are not
normal candidates and are not automatically imported into this catalogue.
The build-workflow link is navigation only: it dispatches no CI and writes no
release or channel. A working management UI does not prove that a normal candidate
has been registered or that live publication/deletion has been exercised.

The original-Admin `prepare_admin_candidate` workflow accepts an optional
`candidate_base_version`. It must match the exact finalized image pinned as
`installedBaseline` in `Tools/ota/admin-candidate-inputs.json`, not merely a version
label or a similarly named file. The source-admission step binds its bytes before
the packaging key is used. The shared vendor-bsdiff/LZMA packer then reconstructs
the target from that base and requires byte-for-byte equality before upload.
The candidate contains full, delta and recovery assets; omitting the base retains
the full/recovery-only path. This explicit staging base is not promoted to a
formal GitHub Release base, and production/acceptance gates remain unchanged.

Registration requires the requested delta and its verified base metadata; it
cannot silently register a full-only result after a delta was requested. Existing
registered assets are immutable, so adding a new delta uses a new candidate
version, not a replacement of an already-published package. CI registers a ready
candidate but does not publish it. On explicit channel publication, clients with
the exact base image receive the smaller delta; other bases retain full-package
fallback. Recovery images are separate owner recovery assets, not delta packages.

All channel mutations require a nonblank `reason` and an `expectedRevision`.
Stable requires owner; beta requires publisher or owner. Publish advances the
version. Retract selects a ready release without changing its identity, state,
hashes or assets. It only affects devices that have not upgraded: upgraded
devices do not downgrade and need a fix with a higher `versionCode`.

Latest and download switches are independent. Download stop blocks subsequent
uses of previously signed public URLs, not just new issuance. Token v2 does not
carry channel identity, so a stopped channel also blocks public downloads of
the same release referenced by another channel. Resume cannot bypass ready/R2
checks or clear the other stop flag. An unchanged switch/message with a current
revision is a no-op, with no new revision or audit.

Release disable is owner-only and rejects any channel reference. Recovery is
owner-only, never an automatic OTA path. Both actions use the existing canonical
UUIDv4 `Idempotency-Key`, actor scope, RFC 8785 fingerprint and permanent
tombstones. No URL, signature or raw key is copied into ordinary audit/logs.

File deletion is a separate owner-only action, available only after explicit
disable and when no channel references the version. It requires the same JSON
scope and reason, same-origin CSRF, and a typed release-tag confirmation in the
UI. Migration `0006_firmware_file_deletion.sql` seals the asset set and forbids
reopening archived/deleted data. Before any R2 deletion, the handler checks exact
release-scoped keys and stored HTTP ETags, then atomically archives the release
with an audit record. Only those exact objects are deleted, never a bucket or
prefix. Release and asset rows, hashes and prior audit history remain.

Unlike capability issuance, file cleanup is monotonic and resumable from the
archived release and `r2_deleted` asset states; it does not issue a capability or
use the disable/recovery idempotency-key table. Partial failure leaves the
version unavailable. Refresh, then explicitly confirm **Continue file deletion**
to finish cleanup. A completed repeat changes neither identity nor success
audit. There is no automatic destructive retry. The UI labels deletion separately
from disabling and channel retraction in both languages.

Firmware list/schema failures are displayed in the firmware section without
discarding the independently loaded App release list. Firmware writes remain
locked until valid state is read again; App management and Access protection are
not bypassed.

The UI reads state again after success, CAS conflict or an unknown network
outcome. It never automatically repeats a channel write. A failed read locks
further writes until reconciliation succeeds. An unknown release result retains
its exact key/body in page memory; the operator must re-read and explicitly
confirm replay as the same actor. An expired result requires a newly confirmed
action, not an automatic new key. A page reload loses that in-memory request;
read state and reconcile the original operation before starting another action.

The migration and security prerequisites from P4-2 still apply. Local tests or
mock screenshots do not establish a real Access owner session, deployment, or
the P42-EXT-03B Admin exercise. Those require separately authorized real evidence.

Every mutation requires:

- A valid Cloudflare Access JWT in `CF-Access-Jwt-Assertion`.
- The Access JWT issuer, audience, expiry, signature, and email allowlist to verify.
- Same-origin `Origin`.
- `X-CSRF-Token` matching the `trace_admin_csrf` cookie from `GET /api/admin/session`.

## Required Configuration

Configure these Pages secrets before deployment. Prefer the staging deployment script below, which writes them as Pages secrets so account-specific Access values are not committed. Do not also define these names in `wrangler.jsonc` `vars`; Pages rejects duplicate binding names.

```text
ACCESS_JWT_ISSUER=https://<team-name>.cloudflareaccess.com
ACCESS_JWT_AUD=<Access application AUD tag>
ADMIN_VIEWER_EMAILS=<comma-separated emails>
ADMIN_PUBLISHER_EMAILS=<comma-separated emails>
ADMIN_OWNER_EMAILS=<comma-separated emails>
ADMIN_ALLOWED_ORIGINS=<optional comma-separated extra origins>
```

The committed `wrangler.jsonc` intentionally does not define these Access values. The facade fails closed until the matching Pages secrets are configured.

## Staging Deploy

Set the Access values in the current PowerShell session, then run the script from the repository root:

```powershell
$env:ACCESS_JWT_ISSUER = "https://<team-name>.cloudflareaccess.com"
$env:ACCESS_JWT_AUD = "<Access application AUD tag>"
$env:ADMIN_OWNER_EMAILS = "you@example.com"
$env:ADMIN_PUBLISHER_EMAILS = "you@example.com"
$env:ADMIN_VIEWER_EMAILS = "you@example.com"
.\cloudflare\update-service\scripts\deploy-admin-staging.ps1 -Yes
```

The script creates `trace-update-admin-staging` if it does not exist, writes the Access values as Pages secrets, runs the admin typecheck, and deploys `admin/public` with the Pages Functions bundle.

If `pages project list` fails while `CLOUDFLARE_API_TOKEN` is set, Wrangler is using that token instead of the browser login. Either give that token Cloudflare Pages permissions or unset it for this PowerShell session:

```powershell
Remove-Item Env:CLOUDFLARE_API_TOKEN -ErrorAction SilentlyContinue
```

## Local Checks

Run from this admin directory with caches and temporary directories contained
in the active worktree (Windows: use `cmd.exe`, not uncontained PowerShell):

```text
npm ci
npm run check
npm exec -- playwright install chromium --only-shell
npm run test:ui
```

Set `PLAYWRIGHT_BROWSERS_PATH` to a worktree-local browser directory, `PW_OUTPUT_DIR`
to a fresh worktree-local evidence directory, and npm/TEMP/TMP/TMPDIR/home/cache
overrides before running locally. Windows dependency installation must use
`npm ci --ignore-scripts` on hosts where workerd is unavailable. Do not retry
native Windows workerd there: run the worker host suite and the existing Linux
`cloudflare-update-service.yml` workflow instead.

The browser suite serves the real HTML and CSS behind intercepted synthetic API routes.
Every screenshot says `MOCK UI / NO REAL ACCESS OR D1`; external requests are
blocked. It covers bilingual confirmation/cancel/conflict, role controls,
independent switches, unknown results, same-key recovery replay, actor changes,
failed reads and mobile layout. CI preserves screenshots, raw UI output and the
checkout SHA for 14 days. These are development checks, not independent acceptance.
Workspace tests also cover catalogue filtering/comparison, compact channel
controls, resource-panel access, note conflicts/drafts, paginated history and
populated long-text layouts in both languages at 1440, 1024, 768, 390 and 320 px.
`test/app-ui.spec.ts` additionally covers explicit App rollback versus forward
publish, bilingual labels, cancellation without a POST, stable typed confirmation,
role and unavailable-target locks, CAS without replay, and mobile confirmation.
Design regressions cover shared styles, bilingual long-text layout, modal focus
and cancellation, reason newlines, App draft retention/isolation, mobile version
navigation, floating resources and reduced motion. Interaction regressions cover
60/600-version bounded lists, pagination/filter boundaries, sticky tools and peer
tabs after scrolling, independent searches, announcement draft/API behavior,
pointer drag/click/cancel, keyboard activation and saved-position clamping.
Populated screenshots are
mock evidence; authenticated production-domain checks remain read-only.

## Source-Bound Deployment Input

For a separately authorized real exercise, dispatch the existing
`cloudflare-update-service.yml` at the intended source commit with
`prepare_admin_bundle=true`. After all three check jobs pass, Linux builds Pages
Functions with the pinned Wrangler and copies the unchanged static UI. A native
workerd smoke check exercises the compiled router and unauthenticated rejection.
The artifact includes source SHA/run, per-file SHA-256 and a build-only notice;
it includes no deployment configuration or credential. This does not deploy or
establish a real Access session.

Do not blindly run the historical staging deploy command for P4-3. The tracked
`admin/wrangler.jsonc` still names the protected old Trace staging database and
bucket. `--project-name` alone does not rebind them. The approved isolated target,
actual D1/R2 bindings, matching Access issuer/audience/owner, firmware download
origin/signing configuration and ready fixtures must be reconciled first.
Do not modify the old service or import another task's operation authorization.
