export interface AccountMailEnv {
  ACCOUNT_MAIL_PROVIDER?: string;
  ACCOUNT_MAIL_API_KEY?: string;
  ACCOUNT_MAIL_FROM?: string;
  ACCOUNT_SMTP_USERNAME?: string;
  ACCOUNT_SMTP_AUTH_CODE?: string;
}
export interface AccountMail { id: string; to: string; subject: string; text: string; html: string }
type MailSocket = Pick<Socket, 'opened' | 'readable' | 'writable' | 'close'>;
export type OpenMailSocket = () => MailSocket;

export function emailDeliveryAvailable(env: AccountMailEnv): boolean {
  if (env.ACCOUNT_MAIL_PROVIDER === 'qq-smtp') {
    return /^[a-z0-9_.+-]+@(qq|foxmail)\.com$/i.test(env.ACCOUNT_SMTP_USERNAME?.trim() ?? '')
      && /^[a-z0-9]{8,128}$/i.test(env.ACCOUNT_SMTP_AUTH_CODE?.trim() ?? '');
  }
  return (!env.ACCOUNT_MAIL_PROVIDER || env.ACCOUNT_MAIL_PROVIDER === 'resend')
    && Boolean(env.ACCOUNT_MAIL_API_KEY?.trim() && env.ACCOUNT_MAIL_FROM?.trim());
}

/** A bounded one-message SMTP transaction. No configurable host, plaintext fallback,
 * protocol logging, persistent socket or automatic resend of an uncertain message. */
export async function sendQqMail(env: AccountMailEnv, mail: AccountMail, open?: OpenMailSocket): Promise<void> {
  if (env.ACCOUNT_MAIL_PROVIDER !== 'qq-smtp' || !emailDeliveryAvailable(env)) throw new Error('SMTP_UNCONFIGURED');
  const from = env.ACCOUNT_SMTP_USERNAME!.trim();
  if (!/^[^\s<>(),;:"\\\x00-\x1f@]{1,64}@[a-z0-9.-]+\.[a-z]{2,30}$/i.test(mail.to)
      || !/^[a-z0-9-]{1,64}$/i.test(mail.id) || /[\r\n]/.test(mail.subject)) throw new Error('SMTP_INVALID_MESSAGE');
  const socket = open ? open() : (await import('cloudflare:sockets')).connect(
    { hostname: 'smtp.qq.com', port: 465 }, { secureTransport: 'on', allowHalfOpen: false });
  const reader = socket.readable.getReader(), writer = socket.writable.getWriter();
  const encoder = new TextEncoder(), decoder = new TextDecoder();
  let pending = '', received = 0;
  let timeout: ReturnType<typeof setTimeout> | undefined;
  const reply = async (expected: number) => {
    let code: string | null = null;
    for (;;) {
      const end = pending.indexOf('\n');
      if (end < 0) {
        const chunk = await reader.read();
        if (chunk.done) throw new Error('SMTP_CONNECTION_CLOSED');
        received += chunk.value.byteLength;
        if (received > 32768) throw new Error('SMTP_RESPONSE_TOO_LARGE');
        pending += decoder.decode(chunk.value, { stream: true });
        continue;
      }
      const line = pending.slice(0, end).replace(/\r$/, ''); pending = pending.slice(end + 1);
      const match = /^(\d{3})([ -])/.exec(line);
      if (!match || (code !== null && code !== match[1])) throw new Error('SMTP_INVALID_RESPONSE');
      code = match[1];
      if (match[2] === '-') continue;
      if (Number(code) !== expected) throw new Error('SMTP_REJECTED_' + expected);
      return;
    }
  };
  const command = async (value: string, expected: number) => {
    await writer.write(encoder.encode(value + '\r\n')); await reply(expected);
  };
  const base64 = (value: string) => Buffer.from(value, 'utf8').toString('base64');
  const encodedBody = (value: string) => base64(value).match(/.{1,76}/g)?.join('\r\n') ?? '';
  const boundary = 'etrack-' + mail.id;
  const part = (kind: string, value: string) => `--${boundary}\r\nContent-Type: text/${kind}; charset=UTF-8\r\nContent-Transfer-Encoding: base64\r\n\r\n${encodedBody(value)}\r\n`;
  const message = `From: E-Track <${from}>\r\nTo: <${mail.to}>\r\nSubject: ${mail.subject}\r\n`
    + `Date: ${new Date().toUTCString()}\r\nMessage-ID: <${mail.id}@${from.split('@')[1]}>\r\nMIME-Version: 1.0\r\n`
    + `Content-Type: multipart/alternative; boundary="${boundary}"\r\n\r\n`
    + part('plain', mail.text) + part('html', mail.html) + `--${boundary}--\r\n.\r\n`;
  try {
    await Promise.race([
      (async () => {
        await socket.opened; await reply(220);
        await command('EHLO etrack-client', 250);
        await command('AUTH LOGIN', 334);
        await command(base64(from), 334);
        await command(base64(env.ACCOUNT_SMTP_AUTH_CODE!.trim()), 235);
        await command(`MAIL FROM:<${from}>`, 250);
        await command(`RCPT TO:<${mail.to}>`, 250);
        await command('DATA', 354);
        await writer.write(encoder.encode(message));
        await reply(250); // Only the post-DATA acceptance counts as accepted mail.
      })(),
      new Promise<never>((_, reject) => { timeout = setTimeout(() => reject(new Error('SMTP_TIMEOUT')), 15000); })
    ]);
  } finally {
    clearTimeout(timeout);
    // Closing the socket also interrupts reads/writes if the transaction timed out.
    await socket.close().catch(() => {});
  }
}

export async function sendAccountMail(env: AccountMailEnv, mail: AccountMail): Promise<void> {
  if (env.ACCOUNT_MAIL_PROVIDER === 'qq-smtp') return sendQqMail(env, mail);
  if (!emailDeliveryAvailable(env)) throw new Error('MAIL_UNCONFIGURED');
  const response = await fetch('https://api.resend.com/emails', { method: 'POST', redirect: 'error',
    headers: { Authorization: 'Bearer ' + env.ACCOUNT_MAIL_API_KEY!.trim(), 'Content-Type': 'application/json', 'Idempotency-Key': mail.id },
    body: JSON.stringify({ from: env.ACCOUNT_MAIL_FROM!.trim(), to: [mail.to], subject: mail.subject, text: mail.text, html: mail.html }),
    signal: AbortSignal.timeout(15000) });
  await response.body?.cancel();
  if (!response.ok) throw new Error('MAIL_PROVIDER_REJECTED');
}
