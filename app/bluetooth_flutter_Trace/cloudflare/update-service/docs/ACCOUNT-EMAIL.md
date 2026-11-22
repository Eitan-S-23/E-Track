# Account Verification Email

## Current Integration

Account mail supports the existing Resend HTTPS API and an explicitly selected
QQ/Foxmail SMTP mailbox. An unset provider preserves Resend behavior. Cloudflare
Access administrator OTP is separate and supplies no reusable sender credential.
Registration/password reset UI must not imply actual inbox delivery merely
because configuration values exist or the provider accepts a message.

## Owner-Selected Mailbox Route (Activation Last)

The owner selected a mailbox route without purchasing a domain. No mailbox has
been configured or used for sending. The provided test recipient is not assumed
to be the sender. Prefer a dedicated project QQ/Foxmail mailbox.

The existing Worker staging and Admin/Public Pages production environments each
need these encrypted settings (do not change preview or any existing secret):

- `ACCOUNT_MAIL_PROVIDER`: `qq-smtp`.
- `ACCOUNT_SMTP_USERNAME`: the complete approved `@qq.com` or `@foxmail.com`
  sender/login address. The From header uses this same mailbox as `E-Track`.
- `ACCOUNT_SMTP_AUTH_CODE`: its SMTP authorization code, not the mailbox password.

Use Cloudflare encrypted Secrets, not source, chat, command-line arguments, D1,
ordinary variables or browser storage. A personal backup belongs in the owner's
password manager. Never send these values to a third-party SMTP test website.
The application exposes readiness only. Configuration presence is not an inbox
test, and email verification must remain off until the controlled flow passes.

Owner steps at activation: select the sender; enable SMTP in that mailbox's
settings and obtain its authorization code; enter the three named encrypted
settings in the exact existing targets above; confirm the code message reaches
the approved test inbox (including spam). Then complete controlled registration
and password-reset verification before enabling required registration mail.
Do not enable IMAP/POP or change personal mailbox settings beyond what the
provider actually requires for SMTP. Provider UI labels may change; verify the
current settings screen when giving the final click-by-click instructions.

The SMTP route uses fixed `smtp.qq.com:465` with TLS from the start, a 15-second
transaction deadline and a 32 KiB response cap. It sends one text/HTML message,
waits for post-DATA acceptance, and closes on success, rejection and timeout.
There is no configurable SMTP target, plaintext fallback, raw protocol logging
or automatic retry of uncertain delivery. The existing code invalidation and
mailbox rate limits remain shared across providers. A rejected mailbox can be
replaced through these settings without an App/MCU rebuild; verify its real
delivery before switching, and do not assume an unusable old mailbox can roll back.

Reuse review: worker-mailer 1.3.1 was inspected, not installed. Its connect error
path does not close its socket, and close() only requests socket closure after a
successful QUIT/read; it also starts an unscoped console.error callback. These
conflict with bounded cleanup and no protocol/credential logging. This project's
small one-message LOGIN/TLS transaction uses the native Cloudflare socket API;
it is not a general SMTP server/client or a replacement deployment tool. Fake
socket tests cover fragmented multiline replies, auth/recipient/DATA rejection,
timeout, injection and response bounds. They do not prove real QQ delivery.

The owner must identify an approved sender/domain, the existing protected Resend
configuration locator, and a real test recipient they control. Never invent a
domain, scrape unrelated secret files, put keys in chat/argv/Git, send to a guessed
recipient, or enable a paid service without its owner's decision.

## Resend Configuration Contract

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
