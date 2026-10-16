# P4-1 Existing-Account Preparation

The owner selected the existing Cloudflare account after the capability boundary
was explained, then supplied a separate CI token. Current rules are in
`OTA-XC-SECRETS` / `P41-CF-CREDENTIAL-02`; the existing P4-1 task note owns status.
No new account, R2 subscription, resource migration or bootstrap rewrite is needed.

`probe.json` is the original sanitized helper receipt. It shows five successful
Cloudflare GETs and a successful public test-Worker health check. The expected
account and fixed Worker/D1/R2 bindings match; the supplied API token is active
and differs from the local provisioning token. The account ID and credential
values are redacted before writing. Full policy/ownership and minimum permissions
are not inferred from the unprefixed token or successful reads.

The exact probe helper and public verification documentation are retained beside
the receipt. No Cloudflare write or native remote-preview session occurred in
this probe. These observations are not canonical rehearsal, production-zero-
effect evidence or independent acceptance.

The contained `PostP26SpecGovernanceTests` pass 24/24, including the new bounded
same-account exception regression. Its original receipt and streams are retained
without line-ending conversion. Product workflow/runtime code remains the reviewed
`18c4da4d28c1f2bcf7175f4b461e2a6bf462a23e` implementation; only current governance,
operational records and this governance test change in this preparation batch.
