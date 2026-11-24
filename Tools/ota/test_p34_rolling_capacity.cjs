"use strict";
const {test} = require("node:test");
const assert = require("node:assert/strict");
const {RollingCapacityProbe} = require("./p34_rolling_capacity.js");
const wire = require("./uart_probe.js");
const input = {packageBytes: 8192, packageSha256: "12".repeat(32), prefixHex: "34".repeat(3968)};

function ack(cmd, seq, {session = 7, status = 0, durable = 0} = {}) {
  const payload = Buffer.alloc(cmd === 0x81 ? 10 : 9), offset = cmd === 0x81 ? 2 : 1;
  payload[0] = status;
  if (cmd === 0x81) payload[1] = session;
  payload.writeUInt32LE(durable, offset);
  payload.writeUInt32LE(cmd === 0x82 ? 1 : 0, offset + 4);
  const bytes = Buffer.alloc(payload.length + 10);
  bytes.set([0xa5, 0x5a, cmd, session]); bytes.writeUInt16LE(seq, 4);
  bytes.writeUInt16LE(payload.length, 6); bytes.set(payload, 8);
  bytes.writeUInt16LE(wire.crc16(bytes.subarray(2, -2)), bytes.length - 2);
  return bytes;
}

function fixture(options = {}) {
  let ms = 0, bytes = Buffer.alloc(0), count = 0, peak = 0, writes = 0, refilledBeforeTail = false;
  let firstDataSeq = null;
  const outstanding = new Set(), delayed = [], frames = [], chunks = [];
  let probe;
  const deliver = () => {
    for (let i = delayed.length - 1; i >= 0; i--) {
      const item = delayed[i];
      if (item.at > ms) continue;
      delayed.splice(i, 1);
      outstanding.delete(item.seq);
      probe.receive(item.bytes);
      if (options.duplicate) probe.receive(item.bytes);
    }
  };
  probe = new RollingCapacityProbe(async (chunk) => {
    writes++;
    if (options.reject === writes) throw Error("platform write failed");
    ms += 3;
    deliver();
    chunks.push(chunk.length);
    bytes = Buffer.concat([bytes, chunk]);
    while (bytes.length >= 8 && bytes.length >= bytes.readUInt16LE(6) + 10) {
      const size = bytes.readUInt16LE(6) + 10, frame = bytes.subarray(0, size);
      bytes = bytes.subarray(size);
      assert.equal(wire.crc16(frame.subarray(2, -2)), frame.readUInt16LE(size - 2));
      frames.push(Buffer.from(frame));
      const cmd = frame[2], seq = frame.readUInt16LE(4);
      if (cmd === 1) probe.receive(ack(0x81, seq, {durable: options.beginDurable ?? 0}));
      if (cmd === 2) {
        count++; outstanding.add(seq); peak = Math.max(peak, outstanding.size);
        if (firstDataSeq === null) firstDataSeq = seq;
        if (count > 31 && outstanding.has(firstDataSeq)) refilledBeforeTail = true;
        assert.ok(outstanding.size <= (options.window ?? 31), "wire credit exceeded");
        if (options.drop !== count) delayed.push({seq,
          at: ms + (count === 1 && options.slowFirst ? 250 : (options.delay ?? 25)),
          bytes: ack(0x82, options.unknown ? 30000 : seq, {
            session: options.wrongSession ? 8 : 7,
            status: options.nak === count ? 2 : 0, durable: options.durable ?? 0})});
        deliver();
      }
      if (cmd === 4 && !options.dropAbort) probe.receive(ack(0x84, seq, {status: 255}));
      assert.notEqual(cmd, 3);
    }
  }, {now: () => ms,
    active: () => !options.pause || count < options.pause,
    connected: () => !options.disconnect || count < options.disconnect,
    sleep: async (n) => { ms += n; deliver(); }});
  probe.bound = true; probe.identity = {version: 30235, maxWindow: 32};
  return {probe, frames, chunks, outstanding, peak: () => peak,
    refilledBeforeTail: () => refilledBeforeTail};
}

for (const chunkBytes of [142, 244]) {
  for (const duplicate of [false, true]) {
    test(`rolling ${chunkBytes}, duplicate=${duplicate}: credit and final ACKs`, async () => {
      const f = fixture({duplicate});
      const result = await f.probe.measure(input, {chunkBytes, durationMs: 1000});
      assert.equal(result.result, "ACKED_LINK_SAMPLE", result.error);
      assert.equal(result.abortConfirmed, true);
      assert.equal(result.durableThroughput, false);
      assert.equal(result.sentFrames, result.acknowledgedFrames);
      assert.equal(result.sentFrames, f.frames.filter((x) => x[2] === 2).length);
      assert.equal(result.repeatedPayloadBytes, result.sentFrames * 128);
      assert.ok(result.peakOutstanding <= 31 && f.peak() <= 31);
      assert.equal(f.outstanding.size, 0);
      assert.ok(f.chunks.every((n) => n <= chunkBytes));
      await assert.rejects(f.probe.measure(input, {chunkBytes}), /fresh/);
    });
  }
}

test("window1 and delayed ACKs never spend unacknowledged credit", async () => {
  const f = fixture({window: 1, delay: 35});
  const result = await f.probe.measure(input, {chunkBytes: 142, window: 1, durationMs: 1000});
  assert.equal(result.result, "ACKED_LINK_SAMPLE");
  assert.equal(f.peak(), 1);
});

test("window28 bounds complete wire bytes below the 4095-byte RX ring", async () => {
  const f = fixture({window: 28, delay: 80});
  const result = await f.probe.measure(input, {chunkBytes: 244, window: 28, durationMs: 1000});
  assert.equal(result.result, "ACKED_LINK_SAMPLE", result.error);
  assert.ok(result.peakOutstanding * 142 <= 4095);
  assert.ok(f.peak() * 142 <= 4095);
});

test("a delayed batch-tail ACK does not block all replenishment", async () => {
  const f = fixture({slowFirst: true});
  const result = await f.probe.measure(input, {chunkBytes: 244, durationMs: 1000});
  assert.equal(result.result, "ACKED_LINK_SAMPLE", result.error);
  assert.equal(f.refilledBeforeTail(), true);
  assert.ok(f.peak() <= 31);
});

for (const options of [{drop: 3}, {nak: 3}, {wrongSession: true}, {durable: 4096},
  {unknown: true}, {pause: 3}, {disconnect: 3}, {beginDurable: 4096}]) {
  test(`negative ACK/lifecycle ${JSON.stringify(options)}`, async () => {
    const f = fixture(options);
    const result = await f.probe.measure(input, {chunkBytes: 244, durationMs: 1000});
    assert.equal(result.result, "INCOMPLETE");
    assert.equal(result.linkPayloadKiBps, undefined);
    assert.ok(f.peak() <= 31);
    if (options.disconnect || options.pause) assert.equal(result.abortConfirmed, false);
  });
}

test("uncertain partial write never appends ABORT", async () => {
  const f = fixture({reject: 3});
  const result = await f.probe.measure(input, {chunkBytes: 244});
  assert.equal(result.writeUncertain, true);
  assert.equal(result.abortConfirmed, false);
  assert.ok(f.frames.every((x) => x[2] !== 4));
});

test("invalid bounds fail before BEGIN", async () => {
  for (const value of [{window: 32}, {window: 0}, {chunkBytes: 512}, {durationMs: 20000}]) {
    const f = fixture();
    await assert.rejects(f.probe.measure(input, {chunkBytes: 244, ...value}), /invalid/);
    assert.equal(f.frames.length, 0);
  }
});

test("short count cap cannot claim sustained capacity", async () => {
  const f = fixture();
  const result = await f.probe.measure(input, {chunkBytes: 244, maxFrames: 31});
  assert.equal(result.result, "INCOMPLETE");
  assert.equal(result.abortConfirmed, true);
});
