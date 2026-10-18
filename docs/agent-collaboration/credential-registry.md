# Credential Registry

Operational inventory, not a secret store or acceptance input. Rules live in
[Reuse Before Requesting Credentials](../agent-collaboration-contract.md#reuse-before-requesting-credentials).
Dates and successful observations below are historical, not perpetual validity
claims. This inventory is not exhaustive; an unlisted credential is not proved
absent. Owner-confirmed changes update the same ID with source and date, without
overwriting old failures or widening authority.

## CF-CI-01: Existing E-Track CI Token

| Field | Recorded fact |
| --- | --- |
| Canonical name | `e-track-ci` |
| Historical alias | `e-track-p41-ci`; the user explicitly confirmed these are the same token |
| Authorized users | User standing authorization, 2026-10-18: any E-Track agent may use this existing token for authorized project work, across tasks, roles and worktrees; not exclusive to the original agent or task. Do not request token-use permission again merely because the agent changed. |
| Kind / platform | Dedicated Cloudflare API token; distinct from local provisioning credentials |
| Owner | Existing Cloudflare credential owner / user; repository configuration owner `Eitan-S-23`. The GitHub name is not proof of a Cloudflare identity or Admin role. |
| Protected local input | `D:/github/my/E-Track/.cache/p41-dev-20261015/.cache/cf-auth-input/p41-ci-token.txt` |
| GitHub consumer | Secret `FIRMWARE_REHEARSAL_CLOUDFLARE_API_TOKEN` in `firmware-rehearsal`; workflow maps it to `CLOUDFLARE_API_TOKEN` |
| Other protected input, NOT interchangeable | `D:/github/my/E-Track/.cache/p41-dev-20261015/.cache/cf-auth-input/token.txt` is the local provisioning credential, not the dedicated CI token and not for CI export |
| Known secret metadata | Rehearsal secret `updated_at=2026-10-16T06:11:27Z`, observed 2026-10-18; metadata does not expose or verify stored bytes |
| Historical OTA test scope | `P41-CF-CREDENTIAL-02` permits the existing-account dedicated token for the exact P4-1 test Worker/D1/R2; P4-4 consumes that same test configuration. This test-resource exception is distinct from the project-wide agent-use authorization above. |
| Production boundary | Existing test authority does not authorize production use. Same-account capability is not hard production permission isolation. A production-use/isolation decision is not automatically a requirement for a new token. |
| Rotation / emergency revocation | Credential owner controls Cloudflare rotation/revocation; configuration owner coordinates affected protected consumers, records new metadata and assesses evidence applicability. No automated rotation or deletion is authorized by this record. |

The locator above is a named protected input on the recorded Windows host, not a
portable dependency or permission to write into that completed worktree. If it
is unavailable, first reconcile the existing platform secret/protected route
with its owner. Do not create an empty replacement and then report the original
credential missing. Do not read/display `token.txt` as a fallback CI credential.

The user explicitly confirmed project-wide agent use in the 2026-10-18 follow-up
to this registry. No per-agent token or repeat token-use approval is required.
The recorded authorization is implemented in the collaboration contract linked
above. It does not approve every technically available API operation, inherit a
different task's approvals, authorize permission expansion/rotation, or remove
production gates. Token values stay in protected inputs, never in chat or evidence.

### Provenance And Observed Capabilities

- Owner-confirmed alias and protected locator:
  [P4-3 Updated E-Track-CI Authorization](../ota-exec-notes/P4-3-implementation-2026-10-17.md#updated-e-track-ci-authorization),
  delivered on main `0779f677507fa2c8a88c1799c8d2909bbae5a0a0`. That record explicitly
  corrects the preceding agent's incomplete credential inventory. P4-3's bounded
  Access/telemetry remediation is not a standing grant for future mutations.
- Accepted same-account exception:
  [OTA-XC-SECRETS](../ota-cross-system-contracts.md#ota-xc-secrets),
  `P41-CF-CREDENTIAL-02`, and record 16 in
  [spec decisions](../ota-spec-decisions.md). No new account/subscription,
  provisioning-token export, second token/hash approval variable or claim of
  hard production isolation follows from that exception.
- Historical runtime: [P4-1 v4 record](../ota-exec-notes/P4-1-implementation-2026-10-15.md#p4-1-v4-independent-acceptance-pass),
  evidence commit `7f136c07505f56582640761944ab5add093252e4`, canonical run
  `38946949709/1` at `b9d7d18c76e6495fbebf6758df6e4427e79e97b5`.
  Successful test R2 upload/readback and Worker registration qualify those
  original inputs, not an arbitrary production target or subsequently changed key.
- P4-4 read-only observation, 2026-10-18 12:31..12:40 UTC: token verify active;
  test Worker settings and Access app/policy GETs succeeded. Token self-policy
  and permission-catalog GETs returned `403/9109`; Pages GET returned `403/10000`.
  These are different APIs. Management denial does not prove token absence or
  publication failure; Pages denial is not a successful current Pages readback.
  Source: `1e28caf350de7e02a7961350a10018bb5e566e51`, repository-relative
  `docs/ota-exec-notes/P4-4-configuration-2026-10-18.md`, E1/E3, and the unchanged
  `docs/ota-exec-notes/P4-4-integration-2026-10-18/initial.zip`. Read via
  `git show COMMIT:PATH` if that task record is not yet on main.

### Recurrence And Correction

On 2026-10-18 the user identified a repeat of the P4-3 discovery error: the alias
and locator were buried in a long task note, rather than reachable directly from
agent entry points. P4-4 had already used the existing token, but then overstated
management 403s as requiring a separate new production credential. Both failure
modes need prevention: discover known inputs first, and keep existence,
operation-specific capability and authorized scope separate.

`P44-CREDENTIAL-01`'s unconditional new-token request is superseded, not its
underlying 403 receipts. Production target/settings and credential-use boundaries
remain owner decisions; the registry does not populate absent secrets or qualify
production. The empty later P4-4 input slot is not evidence that CF-CI-01 is absent.
