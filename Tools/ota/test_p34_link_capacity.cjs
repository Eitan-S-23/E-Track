"use strict";
const {test} = require("node:test");
const assert = require("node:assert/strict");
const {CapacityProbe} = require("./p34_link_capacity.js");
const wire = require("./uart_probe.js");
const input = {packageBytes: 8192, packageSha256: "12".repeat(32), prefixHex: "34".repeat(3968)};

function response(cmd, session, seq, status = 0, durable = 0) {
  const p = new Uint8Array(cmd === 0x81 ? 10 : 9), start = cmd === 0x81 ? 2 : 1;
  p[0] = status;
  if (cmd === 0x81) p[1] = session;
  const v = new DataView(p.buffer);
  v.setUint32(start, durable, true);
  v.setUint32(start + 4, cmd === 0x82 ? 1 : 0, true);
  const bytes = new Uint8Array(p.length + 10), view = new DataView(bytes.buffer);
  bytes.set([0xa5, 0x5a, cmd, session]);
  view.setUint16(4, seq, true); view.setUint16(6, p.length, true); bytes.set(p, 8);
  view.setUint16(bytes.length - 2, wire.crc16(bytes.subarray(2, -2)), true);
  return bytes;
}

function fixture(options = {}) {
  let ms = 0, pending = Buffer.alloc(0), dataCount = 0, writes = 0;
  const frames = [], chunks = [];
  const probe = new CapacityProbe(async (chunk) => {
    ++writes;
    if (options.rejectWrite === writes) throw new Error("platform write failed");
    ms += options.stepMs ?? 2;
    chunks.push(chunk.length);
    pending = Buffer.concat([pending, chunk]);
    while (pending.length >= 8 && pending.length >= pending.readUInt16LE(6) + 10) {
      const len = pending.readUInt16LE(6) + 10, frame = pending.subarray(0, len);
      pending = pending.subarray(len);
      frames.push(Buffer.from(frame));
      assert.equal(wire.crc16(frame.subarray(2, -2)), frame.readUInt16LE(len - 2));
      const cmd = frame[2], seq = frame.readUInt16LE(4);
      if (cmd === 1) probe.receive(response(0x81, 7, seq, options.beginStatus ?? 0, options.beginDurable ?? 0));
      if (cmd === 2) {
        dataCount++;
        if (options.drop === dataCount) continue;
        const ack = response(0x82, options.wrongSession ? 8 : 7, seq,
          options.nak === dataCount ? 2 : 0, options.dataDurable ?? 0);
        probe.receive(ack);
        if (options.duplicateAck) probe.receive(ack);
      }
      if (cmd === 4) probe.receive(response(0x84, 7, seq, 255));
    }
  }, {now: () => ms, active: () => !options.pauseAfter || dataCount < options.pauseAfter,
    connected: () => !options.disconnectAfter || dataCount < options.disconnectAfter,
    sleep: async (duration) => { ms += duration; }});
  probe.bound = true;
  probe.identity = {version: 30230, maxWindow: 32};
  return {probe, frames, chunks, advance: (value) => { ms = value; }};
}

test("window1 never sends another DATA before its delayed ACK", async () => {
  let ms = 0, pending = null, count = 0, probe;
  probe = new CapacityProbe(async (bytes) => {
    const seq = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength).getUint16(4, true);
    ms += 2;
    if (bytes[2] === 1) probe.receive(response(0x81, 7, seq));
    if (bytes[2] === 2) {
      assert.equal(pending, null);
      assert.equal(bytes.length, 142);
      pending = response(0x82, 7, seq);
      count++;
    }
    if (bytes[2] === 4) {
      assert.equal(pending, null);
      probe.receive(response(0x84, 7, seq, 255));
    }
    assert.notEqual(bytes[2], 3);
  }, {now: () => ms, sleep: async () => {
    ms += 20;
    if (pending) { const ack = pending; pending = null; probe.receive(ack); }
  }});
  probe.bound = true; probe.identity = {version:30230, maxWindow:32};
  const result = await probe.measure(input, {chunkBytes:142, window:1, durationMs:1000});
  assert.equal(result.result, "ACKED_LINK_SAMPLE");
  assert.equal(result.sentFrames, count);
  assert.equal(result.abortConfirmed, true);
});

for (const chunkBytes of [142, 244]) {
  test(`sustained ${chunkBytes}-byte writes retain zero durable and exact ACKs`, async () => {
    const f = fixture(), result = await f.probe.measure(input, {chunkBytes, durationMs: 1000});
    assert.equal(result.result, "ACKED_LINK_SAMPLE");
    assert.equal(result.abortConfirmed, true);
    assert.equal(result.durableThroughput, false);
    assert.ok(result.elapsedMs >= 1000);
    assert.ok(result.sentFrames > 31);
    assert.ok(f.chunks.every((n) => n <= chunkBytes));
    const data = f.frames.filter((p) => p[2] === 2);
    assert.equal(data.length, result.sentFrames);
    assert.equal(new Set(data.map((p) => p.readUInt16LE(4))).size, data.length);
    assert.ok(data.every((p) => p.readUInt32LE(8) === 0));
    assert.equal(f.frames.at(-1)[2], 4);
    assert.ok(f.frames.every((p) => [1, 2, 4].includes(p[2])));
    await assert.rejects(f.probe.measure(input, {chunkBytes}), /fresh/);
  });
}

test("invalid bounds never send BEGIN", async () => {
  for (const value of [{window: 32}, {window: 0}, {chunkBytes: 512}, {durationMs: 20000}, {maxFrames: 65535}]) {
    const f = fixture();
    await assert.rejects(f.probe.measure(input, {chunkBytes: 244, ...value}), /invalid/);
    assert.equal(f.frames.length, 0);
  }
});

test("unbound identity and reduced INFO credit fail before BEGIN", async () => {
  for (const identity of [null, {maxWindow: 8}]) {
    const f = fixture(); f.probe.identity = identity;
    await assert.rejects(f.probe.measure(input, {chunkBytes: 244}), /identity|window/);
    assert.equal(f.frames.length, 0);
  }
});

for (const options of [{nak: 3}, {drop: 3}, {wrongSession: true}, {dataDurable: 4096}, {pauseAfter: 3}]) {
  test(`bad or missing ACK/lifecycle cannot report capacity: ${JSON.stringify(options)}`, async () => {
    const f = fixture(options), result = await f.probe.measure(input, {chunkBytes: 244, durationMs: 1000});
    assert.equal(result.result, "INCOMPLETE");
    assert.equal(result.linkPayloadKiBps, undefined);
    assert.equal(result.abortConfirmed, !result.writeUncertain);
    assert.ok(f.frames.filter((p) => p[2] === 2).length <= 31);
  });
}

test("repeated ACK notifications do not inflate the byte numerator", async () => {
  const f = fixture({duplicateAck: true});
  const result = await f.probe.measure(input, {chunkBytes: 244, durationMs: 1000});
  assert.equal(result.result, "ACKED_LINK_SAMPLE");
  assert.equal(result.repeatedPayloadBytes, f.frames.filter((p) => p[2] === 2).length * 128);
});

test("partial platform write failure forbids appending ABORT or reusing the probe", async () => {
  const f = fixture({rejectWrite: 3});
  const result = await f.probe.measure(input, {chunkBytes: 244});
  assert.equal(result.writeUncertain, true);
  assert.equal(result.abortConfirmed, false);
  assert.ok(f.frames.every((p) => p[2] !== 4));
  await assert.rejects(f.probe.measure(input, {chunkBytes: 244}), /fresh/);
});

test("disconnect does not transmit ABORT on a different connection", async () => {
  const f = fixture({disconnectAfter: 3});
  const result = await f.probe.measure(input, {chunkBytes: 142});
  assert.equal(result.result, "INCOMPLETE");
  assert.equal(result.abortConfirmed, false);
});

test("pause at a complete frame boundary sends only bounded ABORT", async () => {
  const f = fixture({pauseAfter: 3});
  const result = await f.probe.measure(input, {chunkBytes: 142});
  assert.equal(result.result, "INCOMPLETE");
  assert.equal(f.frames.filter((p) => p[2] === 2).length, 3);
  assert.equal(result.abortConfirmed, true);
});

test("pause midway through a packed frame never appends ABORT bytes", async () => {
  const f = fixture({pauseAfter: 3});
  const result = await f.probe.measure(input, {chunkBytes: 244});
  assert.equal(result.writeUncertain, true);
  assert.equal(result.abortConfirmed, false);
  assert.ok(f.frames.every((p) => p[2] !== 4));
});

test("resumed BEGIN is rejected without DATA", async () => {
  const f = fixture({beginDurable: 4096});
  const result = await f.probe.measure(input, {chunkBytes: 142});
  assert.equal(result.result, "INCOMPLETE");
  assert.ok(f.frames.every((p) => p[2] !== 2));
});

test("short frame cap is not a sustained measurement", async () => {
  const f = fixture();
  const result = await f.probe.measure(input, {chunkBytes: 244, maxFrames: 31});
  assert.equal(result.result, "INCOMPLETE");
  assert.equal(result.abortConfirmed, true);
});

test("non-monotonic clock fails closed", () => {
  const f = fixture(); f.probe.stamp(); f.advance(-1);
  assert.throws(() => f.probe.stamp(), /monotonic/);
});

function infoResponse(seq, model, version) {
  const payload = Buffer.alloc(50);
  Buffer.from(model).copy(payload);
  payload.writeUInt16LE(1, 8); payload[10] = 1; payload[11] = 1;
  payload.writeUInt32LE(version, 12); payload.fill(0x12, 16, 48);
  payload[48] = 1; payload[49] = 32;
  const bytes = Buffer.alloc(60);
  bytes.set([0xa5, 0x5a, 0x80, 0]); bytes.writeUInt16LE(seq, 4);
  bytes.writeUInt16LE(50, 6); payload.copy(bytes, 8);
  bytes.writeUInt16LE(wire.crc16(bytes.subarray(2, -2)), 58);
  return bytes;
}

test("GET_INFO binds the exact wire model, firmware and window", async () => {
  let probe;
  probe = new CapacityProbe(async (p) => probe.receive(infoResponse(
    new DataView(p.buffer).getUint16(4, true), "E-Track\0", 30230)));
  const value = await probe.query({version: 30230, imageSha256: "12".repeat(32)});
  assert.equal(value.maxWindow, 32);
  assert.equal(probe.bound, true);
});

test("failed identity refresh invalidates a previously bound probe", async () => {
  for (const [model, version] of [["X-Track\0", 30230], ["E-Track\0", 30229]]) {
    let probe;
    probe = new CapacityProbe(async (p) => probe.receive(infoResponse(
      new DataView(p.buffer).getUint16(4, true), model, version)));
    probe.bound = true; probe.identity = {version: 30230, maxWindow: 32};
    await assert.rejects(probe.query({version: 30230, imageSha256: "12".repeat(32)}), /model|match/);
    assert.equal(probe.bound, false);
    assert.equal(probe.identity, null);
    await assert.rejects(probe.measure(input, {chunkBytes: 244}), /identity/);
  }
});
