# P4-1 Protected Setup Observations

Owner-authorized preparation on 2026-10-16, starting at record commit
`fefcb3f2b493527e14affa236207a8d5f4deb682`, branch
`dev/p4-1/unattended-20261015`. Implementation source remains
`18c4da4d28c1f2bcf7175f4b461e2a6bf462a23e`.
This is neither a formal acceptance bundle nor a rehearsal result.

The [task record](../P4-1-implementation-2026-10-15.md#authorized-protected-setup-and-account-blocker)
owns the current action and boundaries. These observations show:

- Cloudflare `GET /user` returned 403/9109. No account-creation POST or Cloudflare
  mutation occurred. The owner must create the production-free account and
  provide its account-owned token through the ignored private input file.
- Six GitHub writes created `firmware-rehearsal`, its exact branch/reviewer
  protections, three variables and a non-development OTA Secret. Gate=false;
  approval/dispatch count=0, no production environment change or cloud token export.
- Secret name/fingerprint verification is not protected real-key compilation.
  Native cloud qualification, canonical rehearsal and independent acceptance
  remain NOT_RUN. The previous readiness and bootstrap archives are unchanged.

## Evidence Kinds

`operations/create-account.json` and `operations/github-configuration.json` are
byte-identical original helper receipts, not full HTTP wire captures. Helper
sources are retained for the exact assertions and output selection.
`operations/read-only.sanitized.json` is explicitly a derived copy: existing
Cloudflare account IDs and names (which can contain email) are redacted. Its raw
source stays ignored/local; its original size and SHA-256 are recorded, without
claiming that redacted bytes are originals.

`references/` contains public documentation retrieved on 2026-10-16. The account
creation documentation is newer and more specific than the legacy API reference's
Global API key example. Account API tokens support Workers/D1/R2/KV, but the native
preview endpoint's effective permissions still require a real check. R2 checkout
and possible usage billing require owner action; no paid-plan change was made.

The OTA key, Cloudflare token, private input template and original account/email
response are deliberately excluded. `inventory.json` binds every retained file
except itself. `.gitattributes` disables line-ending conversion for original bytes.

## Local Verification

The affected `PostP26SpecGovernanceTests` pass 23/23, exit 0, using the contained
runner. Its original receipt/stdout/stderr are under `commands/`. No native build,
Cloudflare qualification, workflow dispatch or acceptance campaign was repeated.
