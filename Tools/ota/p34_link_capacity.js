/* Diagnostic repeated-payload capacity, never durable OTA throughput. */
(function (scope) {
  "use strict";
  const wire = typeof module !== "undefined" ? require("./uart_probe.js") : scope.UartProbe;
  const requireValue = (ok, message) => { if (!ok) throw new Error(message); };
  const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

  class CapacityProbe extends wire.Probe {
    constructor(write, {now = () => performance.now(), active = () => true,
      connected = () => true, sleep = delay} = {}) {
      super(write, now, active);
      this.connected = connected;
      this.sleep = sleep;
      this.used = false;
      this.lastClock = -Infinity;
      this.writeTimeoutMs = 1000;
    }

    stamp() {
      const value = this.now();
      requireValue(Number.isFinite(value) && value >= this.lastClock, "non-monotonic clock");
      this.lastClock = value;
      return value;
    }

    receive(data) {
      if (this.events.length >= 65536 || this.frames.length >= 32768) {
        this.error = "bounded capture exhausted";
        return;
      }
      const first = this.frames.length;
      super.receive(data);
      if (this.liveSession) {
        for (const frame of this.frames.slice(first).filter((f) => f.cmd === 0x82)) {
          const ack = wire.ack(frame);
          if (ack.session !== this.liveSession || ack.status !== 0 || ack.durable !== 0 || ack.bitmap !== 1) {
            this.error = "unexpected DATA ACK identity/status/progress";
          }
        }
      }
    }

    async query(expected) {
      requireValue(!this.used && this.connected() && this.active(), "inactive or spent connection");
      this.bound = false;
      this.identity = null;
      const actual = await super.query(expected);
      this.bound = false;
      requireValue(actual.modelHex === "452d547261636b00", "unexpected wire model");
      this.identity = actual;
      this.bound = true;
      return actual;
    }

    async sendBounded(bytes, deadline, data = false) {
      requireValue(this.connected() && !this.writeUncertain, "unresolved or disconnected write");
      let accepted = 0;
      for (let at = 0; at < bytes.length; at += this.chunkBytes) {
        const remaining = deadline - this.stamp();
        if (remaining <= 0 || !this.connected() || (data && (!this.active() || this.error))) {
          // Do not append ABORT to a possibly incomplete DATA frame.
          this.writeUncertain = data ? accepted % 142 !== 0 : accepted !== 0;
          throw new Error(this.error || "write boundary deadline/disconnection/lifecycle");
        }
        this.writeTimeoutMs = Math.min(1000, remaining);
        try {
          await super.send(bytes.slice(at, at + this.chunkBytes));
        } catch (error) {
          this.writeUncertain = true;
          throw error;
        }
        accepted += Math.min(this.chunkBytes, bytes.length - at);
      }
    }

    async replies(seqs, session, deadline, frameStart) {
      for (;;) {
        requireValue(this.connected() && this.active() && !this.error,
          this.error || "connection/lifecycle changed");
        const replies = this.frames.slice(frameStart).filter((f) => f.cmd === 0x82);
        for (const frame of replies) {
          const value = wire.ack(frame);
          requireValue(value.session === session && value.status === 0 &&
            value.durable === 0 && value.bitmap === 1 && seqs.has(value.seq),
          "unexpected DATA ACK identity/status/progress");
        }
        if (new Set(replies.map((f) => f.seq)).size === seqs.size) return;
        requireValue(this.stamp() < deadline, "missing DATA ACK; no retransmission in diagnostic");
        await this.sleep(1);
      }
    }

    async measure(input, {chunkBytes, window = 31, durationMs = 10000, maxFrames = 16000}) {
      requireValue(!this.used && this.bound && this.identity && this.connected() && this.active(),
        "fresh identity-bound connection required");
      requireValue([142, 244].includes(chunkBytes) && Number.isInteger(window) &&
        window >= 1 && window <= Math.min(31, this.identity.maxWindow), "invalid chunk/window");
      requireValue(Number.isInteger(durationMs) && durationMs >= 1000 && durationMs <= 10000 &&
        Number.isInteger(maxFrames) && maxFrames >= window && maxFrames <= 16000,
      "invalid finite measurement bounds");
      const begin = wire.beginPayload(input), data = wire.dataPayload(input, 0);
      this.used = true;
      this.chunkBytes = chunkBytes;
      const result = {kind: "repeated-payload-link-capacity", durableThroughput: false,
        uniquePayloadBytes: 128, chunkBytes, window, durationMs, sentFrames: 0,
        endSent: false, abortConfirmed: false, result: "INCOMPLETE"};
      let session = 0, beginAttempted = false;
      const started = this.stamp();
      try {
        const seq = this.sequence();
        beginAttempted = true;
        await this.sendBounded(wire.frame(1, 0, seq, begin), started + 2000);
        const reply = wire.ack(await this.wait((f) => f.cmd === 0x81 && f.seq === seq, 1000));
        requireValue(reply.status === 0 && reply.session > 0 && reply.assignedSession === reply.session,
          "BEGIN rejected or ambiguous session");
        session = reply.session;
        requireValue(reply.durable === 0 && reply.bitmap === 0, "BEGIN is not zero-durable");
        result.session = session;
        this.liveSession = session;
        const dataStart = this.stamp(), hardStop = Math.min(dataStart + 20000, started + 23000);
        result.dataStartMs = dataStart;
        while (result.sentFrames < maxFrames && this.stamp() - dataStart < durationMs) {
          requireValue(this.connected() && this.active(), "connection/lifecycle changed");
          const count = Math.min(window, maxFrames - result.sentFrames), seqs = new Set();
          const bytes = new Uint8Array(count * 142), first = this.frames.length;
          for (let n = 0; n < count; n++) {
            const seq = this.sequence();
            seqs.add(seq);
            bytes.set(wire.frame(2, session, seq, data), n * 142);
          }
          await this.sendBounded(bytes, hardStop, true);
          await this.replies(seqs, session, Math.min(hardStop, this.stamp() + 2000), first);
          result.sentFrames += count;
        }
        result.dataEndMs = this.stamp();
        result.elapsedMs = result.dataEndMs - dataStart;
        requireValue(result.elapsedMs >= durationMs && result.elapsedMs <= 20000,
          "insufficient sustained duration or hard deadline");
        result.repeatedPayloadBytes = result.sentFrames * 128;
        result.linkPayloadKiBps = result.repeatedPayloadBytes / 1024 / (result.elapsedMs / 1000);
        result.result = "ACKED_LINK_SAMPLE";
      } catch (error) {
        result.error = String(error);
      } finally {
        if (beginAttempted && this.connected() && !this.writeUncertain) {
          try {
            const seq = this.sequence();
            await this.sendBounded(wire.frame(4, session, seq), this.stamp() + 1000);
            const ack = wire.ack(await this.wait((f) => f.cmd === 0x84 && f.seq === seq &&
              (f.session === session || f.session === 0), 1000));
            requireValue(ack.status === 255 && ack.durable === 0, "ABORT not confirmed at zero durable");
            result.abortConfirmed = true;
          } catch (error) { result.abortError = String(error); }
        }
        result.writeUncertain = this.writeUncertain;
        result.events = this.events;
        result.identity = this.identity;
        if (!result.abortConfirmed && result.result === "ACKED_LINK_SAMPLE") result.result = "UNRECONCILED";
        this.bound = false;
        this.liveSession = null;
      }
      return result;
    }
  }
  if (typeof module !== "undefined") module.exports = {CapacityProbe};
  else scope.P34Capacity = {CapacityProbe};
})(globalThis);
