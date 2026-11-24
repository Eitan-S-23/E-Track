# Account Verification Email

## Current Integration

Account mail supports the existing Resend HTTPS API and an explicitly selected
QQ/Foxmail SMTP mailbox. An unset provider preserves Resend behavior. Cloudflare
Access administrator OTP is separate and supplies no reusable sender credential.
Registration/password reset UI must not imply actual inbox delivery merely
because configuration values exist or the provider accepts a message.

## Owner-Selected Mailbox Route (Activation Last)

### Preferred Local Input (Owner-Delegated Configuration)

The owner now delegates Cloudflare configuration to the agent. Do not require
the owner to navigate three dashboards. On the existing Windows host, open
`configure-account-mail.cmd` at the project root, enter the full sender mailbox,
then a fresh SMTP authorization code at the hidden prompt. No password/code is
accepted through chat, command-line arguments or a plaintext input file.

The launcher uses `python -I -S -B Tools/cloudflare/configure_account_mail.py
--configure`; the agent's preparation uses `--check` without any mailbox input.
It reuses CF-CI-01 and the existing local proxy, preflights the exact Worker and
two Pages projects, and writes only the three mail secrets below. Production-only
Pages PATCH preserves the existing configuration hash and all unrelated/Preview
settings. No credential values are stored locally; sanitized progress receipts
are in `.cache/account-mail-activation/`. A provider-only setting from earlier
dashboard preparation is allowed, but existing mailbox credentials stop an
initial setup so partial writes can be reconciled rather than blindly repeated.

Configuration is not deployment or email delivery. The launcher deliberately
does not redeploy, send mail, enable required verification, create an account or
change a password. After entry, the owner reports only the displayed outcome.
The agent then activates affected Pages through the existing pinned-source
deployment route with Worker/migrations excluded, verifies readiness at all
three targets, and sends one registration-code email to the approved recipient.
Only actual inbox/spam receipt qualifies delivery; registration/reset tests and
an owner-approved required-email switch remain separate.

The dashboard instructions below remain an optional manual route, not required
owner work for the delegated setup.

### Settings And Manual Alternative

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

Cloudflare entry: Workers & Pages, open each existing target, Settings, Variables
and Secrets. Add each setting with type Secret, not ordinary text. For Pages,
select Production (not Preview). The exact targets are:

| Target | Scope |
| --- | --- |
| `trace-update-service-staging` | Existing Worker, corresponding to wrangler `env.staging` |
| `trace-update-public-staging` | Existing Pages project, Production |
| `trace-update-admin-staging` | Existing Pages project, Production |

After saving, report only "configured" and the approved sender address, never
the authorization code. Pages settings may require a new deployment to take
effect; the agent will use the existing pinned-source deployment route only if
needed, then verify readiness. Do not toggle required registration email yet.
Provider acceptance and actual recipient inbox receipt are separate checks.

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

For the optional Resend route only, the owner must identify an approved sender/domain,
the protected Resend configuration locator, and a real test recipient they control. Never invent a
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

Subsequent owner feedback confirms actual receipt of the test email. The code was
not stored or used; see owner-inbox-confirmed.json beside the original send-test
receipt. This closes delivery, not App registration/reset/session validation.
Required registration email remains disabled. For an App verification flow,
request a fresh code inside that flow so it has the matching verificationId;
the host smoke-test message is not an App-issued challenge.

2026-11-22 live checkpoint: owner entered the mailbox settings through the local
launcher; all three target settings and unrelated configuration checks passed.
Pages-only Actions 45028304682 activates existing backend source 95470e8e,
without Worker/schema operations. Real Admin/Worker/Public checks report mail
available and required verification disabled. One Public registration-email
request to the owner-approved test recipient was accepted by the application
and QQ SMTP at 13:45 UTC. Inbox receipt and controlled registration/reset are
still unverified. Do not rerun setup, send another test automatically, create a
test account, or change a real password. See root deployment memory and
`.cache/account-mail-activation/send-test-01/result.json` for this checkpoint.

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
