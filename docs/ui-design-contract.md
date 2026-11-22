# Interface Extension Contract

## Scope

Applies to new and extended Flutter App, Cloudflare Admin and MCU interfaces.
Follow the existing application's colors, typography, spacing, buttons, dialogs,
focus behavior and motion. Reuse shared components before adding another style.
An external product can inform organization, not silently replace E-Track's
design language. Account organization follows newAPI's separated user lists and
authentication settings; Admin interaction continues to use E-Track dialogs.
This contract does not rewrite historical frozen acceptance or grant operations.

## Components And Behavior

| Surface | Existing entry | Required behavior |
| --- | --- | --- |
| Flutter details/results | `TraceDialog`, `TraceDialogAction` | Reuse existing colors, actions and accessible semantics |
| Admin details/results | Shared overlay, confirmation and feedback infrastructure | Reuse focus containment, background inertness, Escape and focus restoration |
| MCU content | Existing LVGL page and modal objects | Calculate bounds after layout against the actual 240 x 320 display |

- Growing collections use pagination or a bounded scroll region, never an
  unbounded column that pushes essential actions off screen. List rows show
  summaries; selecting a record opens its details in the shared dialog.
- A dialog's long content scrolls internally. Close, confirm and cancel remain
  reachable without scrolling through the entire record. Prevent background
  scrolling while an overlay owns the interaction.
- Nested lists pass remaining wheel/touch drag movement to their scrolling
  parent at either edge. Opening a dialog must not accidentally chain scrolling
  to the inert background. Do not treat CSS appearance as proof of this behavior.
- Persistent primary controls such as account logout remain visible outside
  growing lists. Safe-area insets, short screens and enlarged text must not
  obscure them. Forms may scroll to accommodate the keyboard.
- A selectable item is tappable across its full row, including empty space;
  the text glyphs are not the only hit target. Preserve keyboard and screen-reader
  activation, clear focus and adequate contrast.
- Success, failure, record details and destructive confirmations follow the
  neighboring shared dialog pattern. Field validation may stay next to its
  field. Do not substitute inline expanded details or permanent error paragraphs.
- Remove repetitive permanent explanations. Use concise labels and optional
  help for secondary detail, but retain real errors, safety decisions, missing
  information and unverified state. A valid login is not proof of online presence.
- Account entry labels subscribe to the active identity: signed-out shows the
  login/register action; signed-in shows username, falling back to email. Logout,
  restored login and account switches update it without reopening the page.
  Long identities have bounded width and accessible full text.
- Terminal lists identify installations by account and persistent installation
  ID, not by login session, model or display name. Repeated logins stay in history
  without duplicating the terminal. Missing legacy identities stay unknown.
  Terminal logout revokes that account's active sessions for the installation,
  not one arbitrary login or another account/device. State comes from all retained
  sessions, never a truncated display page; valid login does not mean online.
- Layout derives from available dimensions, not overlapping fixed coordinates.
  Long text wraps within its allocated region; use a supported smaller font or
  scrolling where necessary. Text must not cross into the footer/button region.
- Keep each view's response data, pagination and in-flight ownership separate.
  Rendering and loading failures must restore usable controls; stale responses
  cannot update a different view, account or closed dialog.

## Validation Matrix

| Case | Assertions |
| --- | --- |
| Empty and populated lists | Appropriate empty state; bounded height; correct paging |
| List top and bottom | Wheel and touch continue into the parent; dialog background stays fixed |
| Open and close details | Existing modal semantics, focus restored, primary actions reachable |
| Short/narrow viewport and 200% text | No clipped text, overlapping actions or unreachable logout |
| Long names, hashes and translations | Wrap or deliberate truncation; full value available in details |
| Whole-row selection | Tapping row whitespace activates the same item as tapping its name |
| Repeated module/tab switches | No mixed response shapes, stuck busy state or stale render |
| Failed load/save and actor change | Controls recover; intended drafts retained; cross-actor data discarded |
| MCU long/status text | Final laid-out bounds fit content above fixed footer on 240 x 320 |

## Required Tests

Use actual widget/browser/LVGL layout tests where the surface supports them.
Assert final geometry, scrolling, focus, hit areas and asynchronous error paths,
not only text presence, API success or an empty screenshot. Run the applicable
full development checks after the targeted regressions stabilize. Report self-test,
deployed source and user/device observations separately.

## Good, Base And Bad Cases

- Good: a terminal summary opens a shared detail dialog with a bounded body and
  an always-visible close button; logout is outside the account's scrolling body.
- Base: an empty list occupies a concise empty state; no fake history is created.
- Bad: placing a new settings form in every relation list or rendering the full
  account detail inline; old responses break another tab and leave buttons busy.

Wrong: attach click handling only to a label, shrink a screenshot until it looks
acceptable, or rely on `overflow: auto` without testing scroll boundaries.
Correct: make the whole row interactive, test the actual small-screen layout,
and exercise both wheel/touch edges with the real shared scrolling mechanism.
