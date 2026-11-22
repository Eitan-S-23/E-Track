import { afterEach, describe, expect, it, vi } from 'vitest';
import { emailDeliveryAvailable, sendQqMail, type AccountMail, type OpenMailSocket } from '../src/account_mail';

const settings = { ACCOUNT_MAIL_PROVIDER: 'qq-smtp', ACCOUNT_SMTP_USERNAME: 'test_sender@foxmail.com', ACCOUNT_SMTP_AUTH_CODE: 'testauthcodeonly' };
const message: AccountMail = { id: 'test-message-01', to: 'receiver@example.test', subject: 'E-Track verification',
  text: 'Test code 123456', html: '<p>Test code 123456</p>' };
function smtp({ rejectAt = -1, hang = false, fragment = false, large = false } = {}) {
  const writes: string[] = [];
  let controller: ReadableStreamDefaultController<Uint8Array>, closed = 0;
  const encode = new TextEncoder();
  const emit = (value: string) => {
    for (const chunk of fragment ? Array.from(value) : [value]) controller.enqueue(encode.encode(chunk));
  };
  const open: OpenMailSocket = () => ({
    opened: Promise.resolve({ remoteAddress: 'smtp.qq.com:465', localAddress: 'test' }),
    readable: new ReadableStream({ start(c) { controller = c; if (!hang) emit(large ? 'x'.repeat(32769) : '220 test SMTP\r\n'); } }),
    writable: new WritableStream({ write(bytes) {
      writes.push(new TextDecoder().decode(bytes));
      if (writes.length === rejectAt) { emit('535 private-provider-response\r\n'); return; }
      emit(['', '250-test\r\n250 AUTH LOGIN\r\n', '334 user\r\n', '334 pass\r\n', '235 authenticated\r\n',
        '250 from\r\n', '250 recipient\r\n', '354 data\r\n', '250 accepted\r\n'][writes.length]);
    } }),
    async close() { closed++; controller.close(); }
  });
  return { open, writes, closed: () => closed };
}
afterEach(() => vi.useRealTimers());

describe('bounded QQ mailbox sending', () => {
  it('requires explicit provider and complete mailbox credentials, without requiring a domain', () => {
    expect(emailDeliveryAvailable({})).toBe(false);
    expect(emailDeliveryAvailable(settings)).toBe(true);
    expect(emailDeliveryAvailable({ ...settings, ACCOUNT_SMTP_AUTH_CODE: '' })).toBe(false);
    expect(emailDeliveryAvailable({ ...settings, ACCOUNT_SMTP_USERNAME: 'user@unapproved.example' })).toBe(false);
    expect(emailDeliveryAvailable({ ...settings, ACCOUNT_MAIL_PROVIDER: 'unknown' })).toBe(false);
    expect(emailDeliveryAvailable({ ACCOUNT_MAIL_API_KEY: 'test', ACCOUNT_MAIL_FROM: 'sender@example.test' })).toBe(true);
  });
  it('handles fragmented multiline responses and closes after post-DATA acceptance', async () => {
    const server = smtp({ fragment: true });
    await sendQqMail(settings, message, server.open);
    expect(server.closed()).toBe(1);
    expect(server.writes.slice(0, 2)).toEqual(['EHLO etrack-client\r\n', 'AUTH LOGIN\r\n']);
    expect(server.writes[7]).toContain('Content-Type: multipart/alternative');
    expect(server.writes[7]).toContain(Buffer.from(message.text).toString('base64'));
    expect(server.writes[7]).toContain(Buffer.from(message.html).toString('base64'));
    expect(server.writes[7]).toContain('Message-ID: <test-message-01@foxmail.com>');
    expect(server.writes[7].endsWith('\r\n.\r\n')).toBe(true);
  });
  for (const rejectAt of [4, 6, 8]) it(`rejects at SMTP step ${rejectAt}, closes and does not resend`, async () => {
    const server = smtp({ rejectAt });
    await expect(sendQqMail(settings, message, server.open)).rejects.toThrow(/^SMTP_REJECTED_/);
    expect(server.writes).toHaveLength(rejectAt); expect(server.closed()).toBe(1);
  });
  it('times out once and closes a server that never greets', async () => {
    vi.useFakeTimers(); const server = smtp({ hang: true });
    const done = expect(sendQqMail(settings, message, server.open)).rejects.toThrow('SMTP_TIMEOUT');
    await vi.advanceTimersByTimeAsync(15000); await done;
    expect(server.closed()).toBe(1); expect(server.writes).toEqual([]);
  });
  it('bounds server responses and rejects envelope/header injection before connecting', async () => {
    const server = smtp({ large: true });
    await expect(sendQqMail(settings, message, server.open)).rejects.toThrow('SMTP_RESPONSE_TOO_LARGE');
    expect(server.closed()).toBe(1);
    const open = vi.fn(server.open);
    for (const bad of [{ ...message, to: 'bad>name@example.test' }, { ...message, subject: 'test\r\nBcc: victim' }]) {
      await expect(sendQqMail(settings, bad, open)).rejects.toThrow('SMTP_INVALID_MESSAGE');
    }
    expect(open).not.toHaveBeenCalled();
  });
});
