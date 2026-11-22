# Account Verification Email

## Current Integration

Account mail uses the existing Resend HTTPS API, not SMTP or Cloudflare Email
Routing. Cloudflare hosts the application; it does not automatically provide a
verified sender. Registration/password reset UI must not imply that a message
was delivered merely because configuration values exist.

The owner must identify an approved sender/domain, the existing protected Resend
configuration locator, and a real test recipient they control. Never invent a
domain, scrape unrelated secret files, put keys in chat/argv/Git, send to a guessed
recipient, or enable a paid service without its owner's decision.

## Configuration Contract

The current architecture executes account handlers in both Worker and Public
Pages; Admin independently gates the email-verification setting. The same two
protected settings are therefore needed on the existing named Worker environment
and the production environments of both existing Pages projects:

- `ACCOUNT_MAIL_API_KEY`: existing sending-only Resend key, limited to the sender
  domain where supported. Never returned by an API or emitted in logs.
- `ACCOUNT_MAIL_FROM`: approved sender, optionally `E-Track <address@domain>`.

Reuse the exact targets and credential routes in the root
`CLOUDFLARE-DEPLOYMENT.md`. This document does not authorize a configuration change.
Do not alter preview settings, Access, signing keys, channels or delta settings.
Do not generate a replacement key to work around an input-location problem.
Resend must verify the sender domain's required DNS records first. Do not modify
existing MX records or inbound mail routing just to set up outbound mail.

`GET /api/auth/status` returns `emailDeliveryAvailable` and
`passwordResetAvailable` based on configuration presence. Admin
`GET /api/admin/accounts/settings` exposes only the availability boolean, not
the key or sender. `registration_enabled` and `email_verification_enabled` are
separate settings. Keep email verification off until actual delivery and the
verification flow have passed. Ordinary registration may save an optional email
for future password recovery; the address remains unverified until proved.

## Behavioral Contract

- `POST /api/auth/email-code` accepts `email` and `purpose=register|reset`.
- Six-digit codes expire after 10 minutes, are purpose/email-bound, can be used
  once, and permit at most five validation attempts. Only hashes are stored.
- Per mailbox, both purposes share one send request per minute and five per hour;
  existing IP/identity authentication rate limits still apply. These limits are
  separate from the account's daily 5 automatic/5 manual update checks.
- Resend receives plain text and HTML, an idempotency key and a 15-second deadline.
  No credential-bearing redirect is followed. Rejected/uncertain sends invalidate
  that request's code and return `EMAIL_DELIVERY_FAILED`, not success.
- Unconfigured sends return `EMAIL_DELIVERY_UNAVAILABLE`; early resends return
  `EMAIL_SEND_COOLDOWN`. App and Admin show explicit failure dialogs.
- An unknown password-reset account receives the same acknowledgement shape,
  without sending email or exposing whether an account exists.
- A successful reset verifies mailbox possession and revokes existing sessions.

## Live Completion

After the owner supplies approved inputs, configure only these named settings via
the existing protected Cloudflare route. Then read auth status through both
Worker and Public Pages and inspect the Admin availability state. Record presence
and targets only; never record values or their credential-bearing hashes.

Send one registration verification message to the approved recipient. Distinguish
provider acceptance from the recipient actually receiving it (including spam).
Finish a controlled registration/login, request a reset after the resend interval,
verify the new password and revoked old session, and verify code reuse rejection.
Use a clearly identified test account only with owner agreement; do not modify or
delete a real user's account or consume device OTA opportunities. API/mock tests
are not actual mail delivery. Missing sender/recipient inputs leave this section
pending rather than passed.

References checked 2026-11-22:
- https://resend.com/docs/api-reference/emails/send-email
- https://developers.cloudflare.com/workers/best-practices/workers-best-practices/
