# Independent Update Check Quotas

Owner decision, 2026-11-25: APP self-update checks and MCU firmware checks must
not consume each other's quotas or delay each other's automatic checks.

## Scope And Compatibility

The server determines the component from its authenticated route:

| Route | Component |
| --- | --- |
| /api/public/latest | app |
| /api/public/firmware/latest | firmware |

No new request header, client version or firmware protocol is required. An
X-Update-Check-Component request header cannot change this classification.
Login, bound-device admission, immutable manifests, signed downloads, check-ID
idempotency, replay/refresh identity and lease ownership remain mandatory.

Automatic and manual checks have separate daily quotas for each component.
Automatic checks retain a one-hour minimum interval within the same account and
component. The 12-attempt/60-second account check limiter is also component-scoped.
This does not change Bluetooth recovery cooldown, MCU cache/dedup or the APP's
local daily-check marker. Download and installation do not consume check quotas.

## Settings And Responses

The existing automatic_daily_limit and manual_daily_limit settings now control
APP checks. firmware_automatic_daily_limit and firmware_manual_daily_limit
control firmware checks independently. Migration 0020 copies the currently
configured limits, including zero, to initialize firmware settings; it does not
choose new limits or enable a disabled check. Older Admin settings submissions
without firmware fields preserve their existing values.

Account/login/Admin quota responses contain components.app and
components.firmware, each with automatic/manual limit, used and remaining.
For installed clients, flat quota.automatic/manual remain aliases of APP quotas;
quota.component is app. They are not combined account totals.
Latest responses retain their signed body unchanged and expose
X-Update-Check-Component plus component-specific X-Update-Automatic-Remaining,
X-Update-Manual-Remaining and X-Update-Quota-Reset headers.

## Historical Rows

Migration 0020 adds component=legacy to existing checks and keeps all original
identities, timestamps, outcomes, payloads and leases. In particular, a hashed
NO_UPDATE request cannot prove its old route. Unclassified records are exposed
as unclassifiedLegacyChecks and do not debit either new component budget.
Only replaying the exact original request hash, ID and kind can identify a legacy
row's component. No check history, installed-client state or reminder dedup is
cleared. The transition to independently scoped budgets is not a reconstruction
of missing historical source information.

## Owner Rollout

This source change is not a deployed backend. After main delivery is authorized
and its checks pass, the owner applies migration 0020 to the existing D1 through
the established deployment route, then deploys the same source to Worker and
Public Pages, followed by Admin Pages. These surfaces embed the shared backend
and must not remain on mixed quota implementations.

Migration is required before new backend code; missing component columns are not
a reason to bypass quota admission. The new Admin handles an old response as
legacy/shared rather than falsely displaying independent budgets. Do not drop
the new columns or delete old rows to roll back a UI deployment.

No new APK or MCU build is needed for this server-side separation. A previously
written APP daily marker is untouched and is not evidence that a new automatic
check has run. Real phone checks and live backend results remain owner verification.
