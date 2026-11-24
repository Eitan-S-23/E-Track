/* Development-only, non-committing BLE receiver probe. No END encoder exists. */
(function (scope) {
  "use strict";
  const MAX_SEGMENTS = 31;
  const SEGMENT_BYTES = 128;
  const allowedStatus = new Set([...Array.from({length: 19}, (_, i) => i), 255]);
  const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  const hex = (bytes) => Array.from(bytes, (x) => x.toString(16).padStart(2, "0")).join("");

  function requireValue(ok, message) {
    if (!ok) throw new Error(message);
  }

  function bytesFromHex(value) {
    requireValue(typeof value === "string" && /^(?:[0-9a-f]{2})+$/i.test(value), "invalid hex input");
    return Uint8Array.from(value.match(/../g), (s) => parseInt(s, 16));
  }

  function crc16(data) {
    let crc = 0xffff;
    for (const byte of data) {
      crc ^= byte << 8;
      for (let bit = 0; bit < 8; bit++) {
        crc = ((crc << 1) ^ ((crc & 0x8000) ? 0x1021 : 0)) & 0xffff;
      }
    }
    return crc;
  }

  function frame(cmd, session, seq, payload = new Uint8Array()) {
    requireValue([0, 1, 2, 4].includes(cmd), "END and unknown commands are prohibited");
    requireValue(Number.isInteger(session) && session >= 0 && session <= 255 &&
      Number.isInteger(seq) && seq >= 0 && seq <= 65535, "invalid frame identity");
    requireValue((cmd === 0 || cmd === 4) ? payload.length === 0 :
      cmd === 1 ? payload.length === 101 : payload.length === 132, "invalid command payload size");
    const result = new Uint8Array(payload.length + 10);
    const view = new DataView(result.buffer);
    result.set([0xa5, 0x5a, cmd, session]);
    view.setUint16(4, seq, true);
    view.setUint16(6, payload.length, true);
    result.set(payload, 8);
    view.setUint16(result.length - 2, crc16(result.subarray(2, -2)), true);
    return result;
  }

  class Parser {
    constructor() { this.pending = new Uint8Array(); }
    feed(data) {
      const buffer = new Uint8Array(this.pending.length + data.length);
      buffer.set(this.pending);
      buffer.set(data, this.pending.length);
      requireValue(buffer.length <= 8192, "notification buffer limit");
      const result = [];
      let at = 0;
      while (buffer.length - at >= 2) {
        requireValue(buffer[at] === 0xa5 && buffer[at + 1] === 0x5a, "non-frame notification bytes");
        if (buffer.length - at < 8) break;
        const view = new DataView(buffer.buffer, buffer.byteOffset + at);
        const cmd = buffer[at + 2], size = view.getUint16(6, true);
        const expected = cmd === 0x80 ? 50 : cmd === 0x81 ? 10 : [0x82, 0x84].includes(cmd) ? 9 : -1;
        requireValue(size === expected, "invalid response command or payload size");
        if (buffer.length - at < size + 10) break;
        const raw = buffer.slice(at, at + size + 10);
        requireValue(crc16(raw.subarray(2, -2)) === view.getUint16(size + 8, true), "response CRC mismatch");
        const payload = raw.slice(8, -2);
        if (cmd !== 0x80) requireValue(allowedStatus.has(payload[0]), "unknown ACK status");
        result.push({cmd, session: raw[3], seq: view.getUint16(4, true), payload, raw});
        at += raw.length;
      }
      this.pending = buffer.slice(at);
      return result;
    }
  }

  function info(value) {
    requireValue(value.cmd === 0x80 && value.session === 0 && value.payload.length === 50, "invalid INFO");
    const p = value.payload, view = new DataView(p.buffer, p.byteOffset, p.length);
    return {modelHex: hex(p.subarray(0, 8)), hardware: view.getUint16(8, true), layout: p[10], bootVersion: p[11],
      version: view.getUint32(12, true), imageSha256: hex(p.subarray(16, 48)), protocol: p[48], maxWindow: p[49]};
  }

  function ack(value) {
    const p = value.payload, begin = value.cmd === 0x81;
    requireValue([0x81, 0x82, 0x84].includes(value.cmd) && p.length === (begin ? 10 : 9), "invalid ACK");
    const view = new DataView(p.buffer, p.byteOffset, p.length), start = begin ? 2 : 1;
    return {cmd: value.cmd, session: value.session, assignedSession: begin ? p[1] : null,
      seq: value.seq, status: p[0], durable: view.getUint32(start, true), bitmap: view.getUint32(start + 4, true)};
  }

  function beginPayload(input) {
    requireValue(Number.isInteger(input.packageBytes) && input.packageBytes > 4096 && input.packageBytes <= 2093056,
      "package length must exceed the non-committing probe");
    const sha = bytesFromHex(input.packageSha256), prefix = bytesFromHex(input.prefixHex);
    requireValue(sha.length === 32 && prefix.length >= MAX_SEGMENTS * SEGMENT_BYTES, "incomplete probe input");
    const result = new Uint8Array(101);
    result[0] = 1;
    new DataView(result.buffer).setUint32(1, input.packageBytes, true);
    result.set(sha, 5);
    result.set(prefix.subarray(0, 64), 37);
    return result;
  }

  function dataPayload(input, segment) {
    requireValue(Number.isInteger(segment) && segment >= 0 && segment < MAX_SEGMENTS,
      "the committing 32nd segment is prohibited");
    const prefix = bytesFromHex(input.prefixHex), offset = segment * SEGMENT_BYTES;
    requireValue(prefix.length >= offset + SEGMENT_BYTES, "short probe prefix");
    const result = new Uint8Array(132);
    new DataView(result.buffer).setUint32(0, offset, true);
    result.set(prefix.subarray(offset, offset + SEGMENT_BYTES), 4);
    return result;
  }

  class Probe {
    constructor(write, now = () => performance.now(), active = () => true) {
      this.write = write;
      this.now = now;
      this.active = active;
      this.seq = 0;
      this.parser = new Parser();
      this.frames = [];
      this.events = [];
      this.error = null;
      this.writeUncertain = false;
      this.bound = false;
      this.chunkBytes = 142;
      this.writeTimeoutMs = 3000;
    }
    sequence() {
      requireValue(this.seq < 65536, "probe sequence exhausted");
      return this.seq++;
    }
    receive(value) {
      const bytes = new Uint8Array(value.buffer, value.byteOffset, value.byteLength);
      this.events.push({kind: "notify", ms: this.now(), hex: hex(bytes)});
      try {
        for (const f of this.parser.feed(bytes)) {
          f.ms = this.now();
          this.frames.push(f);
        }
      } catch (error) { this.error = String(error); }
    }
    async send(data) {
      requireValue(!this.writeUncertain, "previous GATT write is unresolved");
      for (let at = 0; at < data.length; at += this.chunkBytes) {
        const part = data.slice(at, at + this.chunkBytes), before = this.now();
        let timer;
        const actual = Promise.resolve().then(() => this.write(part));
        actual.catch(() => {});
        try {
          await Promise.race([actual, new Promise((_, reject) => {
            timer = setTimeout(() => {
              this.writeUncertain = true;
              reject(new Error("GATT write deadline; no further writes permitted"));
            }, this.writeTimeoutMs);
          })]);
          this.events.push({kind: "write", beginMs: before, ms: this.now(), hex: hex(part)});
        } catch (error) {
          this.events.push({kind: "write-error", beginMs: before, ms: this.now(), hex: hex(part), error: String(error)});
          throw error;
        } finally { clearTimeout(timer); }
      }
    }
    async wait(matching, timeoutMs) {
      const end = this.now() + timeoutMs;
      while (this.now() < end) {
        requireValue(!this.error, this.error);
        const found = this.frames.find(matching);
        if (found) return found;
        await sleep(5);
      }
      throw new Error("ACK deadline");
    }
    async query(expected) {
      const seq = this.sequence();
      await this.send(frame(0, 0, seq));
      const actual = info(await this.wait((f) => f.cmd === 0x80 && f.seq === seq, 2500));
      requireValue(actual.version === expected.version && actual.imageSha256 === expected.imageSha256 &&
        actual.hardware === 1 && actual.layout === 1 && actual.protocol === 1 && actual.maxWindow >= MAX_SEGMENTS,
        "device INFO does not match the image-bound receiver");
      this.bound = true;
      return actual;
    }
    async trial(input, settings) {
      requireValue(this.bound, "query and verify the exact receiver before BEGIN");
      requireValue(this.active(), "probe runtime is not foreground");
      requireValue(Number.isInteger(settings.segments) && settings.segments >= 1 && settings.segments <= MAX_SEGMENTS,
        "invalid non-committing segment count");
      requireValue([20, 142, 244].includes(settings.chunkBytes), "unplanned GATT chunk size");
      const payload = beginPayload(input);
      this.chunkBytes = settings.chunkBytes;
      const eventStart = this.events.length, frameStart = this.frames.length, started = this.now();
      const result = {id: settings.id, startedMs: started, sentSegments: 0, beginAccepted: false, abortConfirmed: false,
        endSent: false, firstAckError: null, settings};
      let session = 0, abortNeeded = false;
      try {
        const seq = this.sequence();
        abortNeeded = true;
        await this.send(frame(1, 0, seq, payload));
        const reply = ack(await this.wait((f) => f.cmd === 0x81 && f.seq === seq, 2500));
        requireValue(reply.status === 0 && reply.session > 0 && reply.assignedSession === reply.session,
          "BEGIN rejected or invalid session");
        session = reply.session;
        requireValue(reply.durable === 0 && reply.bitmap === 0, "nonzero initial progress; probe stopped");
        result.beginAccepted = true;
        const seqs = new Set();
        for (let segment = 0; segment < settings.segments; segment++) {
          requireValue(this.active(), "page backgrounded; stop DATA");
          requireValue(!this.error, this.error);
          const nak = this.frames.slice(frameStart).find((f) => f.cmd === 0x82 && f.session === session && f.payload[0] !== 0);
          if (nak) { result.firstAckError = ack(nak); break; }
          const seq = this.sequence();
          seqs.add(seq);
          await this.send(frame(2, session, seq, dataPayload(input, segment)));
          result.sentSegments++;
        }
        const deadline = this.now() + 2500;
        while (this.now() < deadline) {
          requireValue(!this.error, this.error);
          const replies = this.frames.slice(frameStart).filter((f) => f.cmd === 0x82 && f.session === session && seqs.has(f.seq));
          const nak = replies.find((f) => f.payload[0] !== 0);
          if (nak) { result.firstAckError = ack(nak); break; }
          if (new Set(replies.map((f) => f.seq)).size === seqs.size) break;
          await sleep(5);
        }
        result.dataAcks = this.frames.slice(frameStart).filter((f) => f.cmd === 0x82 && f.session === session).map(ack);
        requireValue(result.dataAcks.every((a) => a.durable === 0), "unexpected durable progress");
        result.allDataAcknowledged = !result.firstAckError && result.sentSegments === settings.segments &&
          new Set(result.dataAcks.filter((a) => seqs.has(a.seq) && a.status === 0).map((a) => a.seq)).size === seqs.size &&
          result.dataAcks.some((a) => a.status === 0 && a.bitmap === 2 ** settings.segments - 1);
      } catch (error) { result.error = String(error); }
      finally {
        if (abortNeeded && !this.writeUncertain) {
          const seq = this.sequence(), bytes = frame(4, session, seq);
          for (let attempt = 0; attempt < 3 && !result.abortConfirmed; attempt++) {
            try {
              await this.send(bytes);
              const reply = ack(await this.wait((f) => f.cmd === 0x84 && f.seq === seq &&
                (f.session === session || f.session === 0), 1000));
              requireValue(reply.status === 255 && reply.durable === 0, "ABORT not confirmed at zero durable offset");
              result.abortConfirmed = true;
            } catch (error) { result.abortError = String(error); }
            if (this.error || this.writeUncertain) break;
          }
        }
      }
      result.finishedMs = this.now();
      result.events = this.events.slice(eventStart);
      result.writeUncertain = this.writeUncertain;
      return result;
    }
  }

  const api = {MAX_SEGMENTS, SEGMENT_BYTES, crc16, frame, Parser, info, ack, beginPayload, dataPayload, Probe, hex, bytesFromHex};
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else scope.UartProbe = api;
})(globalThis);
