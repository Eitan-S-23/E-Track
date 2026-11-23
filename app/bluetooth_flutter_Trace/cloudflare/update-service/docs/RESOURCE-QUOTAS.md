# Admin Account Quotas

## Scope And Data Contract

`GET /api/admin/resource-usage` remains Access/role protected. `metrics` contains
only configured project resources. `account.plans` and `account.quotas` contain
account-wide data, including other projects. Project counts never reduce account
allowances. No token, complete subscription response, client secrets or billing
payment fields are returned or cached.

Each quota includes `used`, `allowance`, `remaining`, `overage`, `limitKind`,
`state`, `reason`, `planName`, `periodStart`, `periodEnd`, `quotaResetAt`,
`lastSuccessAt`, `estimation`, `coverage` and a fixed pricing reference.
`remaining` is an estimate, not an invoice or monetary credit balance. Hard Free
limits and paid included usage are distinct; exceeding included usage need not
stop the service. CPU per invocation is a limit, not a reducible account balance.

## Plan Classification

The account subscriptions endpoint is SinglePage in Cloudflare's SDK. A complete
valid response plus account type `standard` and absence of any current Workers,
unknown Workers/enterprise or contracted plan establishes the documented default
Workers Free plan. Denied, malformed, incomplete or unknown plans never become
Free automatically. A canceled plan with a future/unknown end is not assumed Free.
Recognized Workers Paid/Standard subscriptions use their actual monthly period;
legacy/custom/Enterprise plans remain unknown rather than receiving guessed limits.
R2 Paid is independent of Workers Paid. `component_values` are never allowances.

The R2 Standard included amounts are 10 GB-month, one million Class A operations
and ten million Class B operations per monthly subscription period. Only Standard
operations/storage are compared to these amounts; Infrequent Access has no free
tier. Missing or invalid billing periods prevent balance calculation.

## Metering

Workers and Pages Functions are separate datasets; both account totals are
required for their shared request allowance. Empty/missing datasets are unknown,
not zero. D1 and DO rows/compute queries omit project filters. D1 Free storage
uses the sum of every database's current `file_size`, converted using decimal GB.
The inventory is capped at three 100-row pages and rejects missing, duplicate,
truncated or inconsistent count/page metadata. A complete empty inventory is a real zero.

R2 storage groups by UTC date and bucket over the actual billing window. All
observed daily bucket peaks are summed and divided by 30 and 1e9, following the
official GB-month examples. Every elapsed UTC day must have a sample. Missing
days, malformed groups, duplicated bucket-days, overflow or reaching the 1000-row
cap prevent a balance estimate. `coverage` records the day counts and 30-day
normalization. Current-day peaks are provisional; the estimate is not an invoice
and must not be relabeled as exact billing usage, especially for non-30-day cycles.

DO account storage and paid D1/DO storage GB-month are currently unsupported
complete meters. Their established allowance is shown, but remaining stays
unknown. Current storage bytes cannot replace monthly storage metering. Paid DO
request analytics count actual WebSocket messages; billing uses a 20:1 ratio,
so the request balance is explicitly an analytics estimate.

## Bounds And Refresh

The original twelve project queries and account collection run serially in
batches of at most three provider requests. Account collection uses three initial
REST reads, six aggregate queries and one storage query; inventory pagination
can add at most two reads. Each response is capped at 256 KiB with a seven-second
timeout, manual redirects and no automatic credential-bearing redirect/retry.
The existing D1 15-minute cache and 90-second refresh lease are reused under a
new `resource-usage-v2` namespace. Old cache rows are not deleted.

Failed refreshes preserve the previous successful value, plan, measurement
window, reset time and success time as stale. They do not attach yesterday's
counts to today's allowance. The UI separates account quotas and project usage,
preserves real zero, identifies missing data and keeps the existing scroll panel,
refresh button and actor-generation ownership.

## References

- https://developers.cloudflare.com/workers/platform/pricing/
- https://developers.cloudflare.com/d1/platform/pricing/
- https://developers.cloudflare.com/durable-objects/platform/pricing/
- https://developers.cloudflare.com/r2/pricing/

The referenced pricing pages and their official `cloudflare/cloudflare-docs`
source were checked on 2026-11-23. This is an Admin-only import change; the main
Worker entry does not import `resource_usage`. No schema, bindings, credentials,
Worker/Public deployment, App/MCU release, channel or delta change is required.
