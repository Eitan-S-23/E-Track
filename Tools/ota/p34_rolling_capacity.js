/* Separate diagnostic candidate; the fixed-window evidence stays immutable. */
(function (scope) {
  "use strict";
  const wire = typeof module !== "undefined" ? require("./uart_probe.js") : scope.UartProbe;
  const base = typeof module !== "undefined" ? require("./p34_link_capacity.js") : scope.P34Capacity;
  const check = (ok, message) => { if (!ok) throw new Error(message); };

  class RollingCapacityProbe extends base.CapacityProbe {
    async measure(input, {chunkBytes, window = 31, durationMs = 10000, maxFrames = 16000}) {
      check(!this.used && this.bound && this.identity && this.connected() && this.active(),
        "fresh identity-bound connection required");
      check([142, 244].includes(chunkBytes) && Number.isInteger(window) && window >= 1 &&
        window <= Math.min(31, this.identity.maxWindow), "invalid chunk/window");
      check(Number.isInteger(durationMs) && durationMs >= 1000 && durationMs <= 10000 &&
        Number.isInteger(maxFrames) && maxFrames >= window && maxFrames <= 16000,
      "invalid finite measurement bounds");
      const begin = wire.beginPayload(input), data = wire.dataPayload(input, 0);
      this.used = true;
      this.chunkBytes = chunkBytes;
      const result = {kind: "repeated-payload-link-capacity", sender: "rolling-credit-v1",
        durableThroughput: false, uniquePayloadBytes: 128, chunkBytes, window, durationMs,
        sentFrames: 0, acknowledgedFrames: 0, peakOutstanding: 0,
        endSent: false, abortConfirmed: false, result: "INCOMPLETE"};
      let session = 0, beginAttempted = false;
      const started = this.stamp();
      try {
        const seq = this.sequence();
        beginAttempted = true;
        await this.sendBounded(wire.frame(1, 0, seq, begin), started + 2000);
        const reply = wire.ack(await this.wait((f) => f.cmd === 0x81 && f.seq === seq, 1000));
        check(reply.status === 0 && reply.session > 0 && reply.assignedSession === reply.session,
          "BEGIN rejected or ambiguous session");
        session = reply.session;
        check(reply.durable === 0 && reply.bitmap === 0, "BEGIN is not zero-durable");
        this.liveSession = session;
        result.session = session;
        const dataStart = this.stamp(), hardStop = Math.min(dataStart + 20000, started + 23000);
        result.dataStartMs = dataStart;
        const pending = new Map(), issued = new Set(), acknowledged = new Set();
        let cursor = this.frames.length;
        const collect = () => {
          check(this.connected() && this.active() && !this.error,
            this.error || "connection/lifecycle changed");
          for (; cursor < this.frames.length; cursor++) {
            const frame = this.frames[cursor];
            if (frame.cmd !== 0x82) continue;
            const ack = wire.ack(frame);
            check(ack.session === session && ack.status === 0 && ack.durable === 0 &&
              ack.bitmap === 1 && issued.has(ack.seq), "unexpected DATA ACK identity/status/progress");
            if (!acknowledged.has(ack.seq)) {
              check(pending.delete(ack.seq), "unreserved DATA ACK");
              acknowledged.add(ack.seq);
            }
          }
          const now = this.stamp();
          check(now < hardStop, "hard deadline");
          for (const deadline of pending.values()) {
            check(now < deadline, "missing DATA ACK; no retransmission in diagnostic");
          }
        };
        while (true) {
          collect();
          const sending = result.sentFrames < maxFrames && this.stamp() - dataStart < durationMs;
          if (!sending && pending.size === 0) break;
          const count = sending ? Math.min(window - pending.size, maxFrames - result.sentFrames) : 0;
          if (count === 0) {
            await this.sleep(1);
            continue;
          }
          // Reserve before writes: notifications can arrive before a platform Future resolves.
          const bytes = new Uint8Array(count * 142), seqs = [];
          for (let n = 0; n < count; n++) {
            const next = this.sequence();
            check(!issued.has(next), "sequence reused");
            issued.add(next);
            pending.set(next, Infinity);
            seqs.push(next);
            bytes.set(wire.frame(2, session, next, data), n * 142);
          }
          result.peakOutstanding = Math.max(result.peakOutstanding, pending.size);
          await this.sendBounded(bytes, hardStop, true);
          const ackDeadline = Math.min(hardStop, this.stamp() + 2000);
          for (const next of seqs) pending.set(next, ackDeadline);
          result.sentFrames += count;
        }
        result.acknowledgedFrames = acknowledged.size;
        check(acknowledged.size === result.sentFrames, "incomplete final ACK set");
        result.dataEndMs = this.stamp();
        result.elapsedMs = result.dataEndMs - dataStart;
        check(result.elapsedMs >= durationMs && result.elapsedMs <= 20000,
          "insufficient sustained duration or hard deadline");
        result.repeatedPayloadBytes = acknowledged.size * 128;
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
            check(ack.status === 255 && ack.durable === 0, "ABORT not confirmed at zero durable");
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
  if (typeof module !== "undefined") module.exports = {RollingCapacityProbe};
  else scope.P34Capacity = {CapacityProbe: RollingCapacityProbe};
})(globalThis);
