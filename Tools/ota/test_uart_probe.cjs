"use strict";
const {test} = require("node:test");
const assert = require("node:assert/strict");
const p = require("./uart_probe.js");
const input = {packageBytes: 290776, packageSha256: "12".repeat(32), prefixHex: "34".repeat(3968)};

function response(cmd, session, seq, payload) {
  const bytes = new Uint8Array(payload.length + 10), view = new DataView(bytes.buffer);
  bytes.set([0xa5, 0x5a, cmd, session]);
  view.setUint16(4, seq, true); view.setUint16(6, payload.length, true);
  bytes.set(payload, 8); view.setUint16(bytes.length - 2, p.crc16(bytes.subarray(2, -2)), true);
  return bytes;
}
function ack(cmd, session, seq, status = 0, bitmap = 0) {
  const payload = new Uint8Array(cmd === 0x81 ? 10 : 9), view = new DataView(payload.buffer);
  payload[0] = status;
  if (cmd === 0x81) payload[1] = session;
  view.setUint32(cmd === 0x81 ? 6 : 5, bitmap, true);
  return response(cmd, session, seq, payload);
}
function fake(nakAt = -1) {
  const writes = [];
  let bitmap = 0, probe;
  probe = new p.Probe(async (bytes) => {
    writes.push(bytes);
    const view = new DataView(bytes.buffer), cmd = bytes[2], seq = view.getUint16(4, true);
    if (cmd === 1) probe.receive(ack(0x81, 7, seq));
    else if (cmd === 2) {
      const segment = view.getUint32(8, true) / 128;
      if (segment !== nakAt) bitmap = (bitmap | (1 << segment)) >>> 0;
      probe.receive(ack(0x82, 7, seq, segment === nakAt ? 2 : 0, bitmap));
    } else if (cmd === 4) probe.receive(ack(0x84, 7, seq, 255, bitmap));
  });
  probe.bound = true;
  return {probe, writes};
}

test("CRC-CCITT-FALSE known vector", () => assert.equal(p.crc16(Buffer.from("123456789")), 0x29b1));
test("GET_INFO exact contract bytes", () => assert.equal(p.hex(p.frame(0, 0, 0)), "a55a000000000000100e"));
test("INFO uses u16 hardware followed by u8 layout and boot", () => {
  const payload = new Uint8Array(50);
  payload.set([1, 0, 1, 1], 8);
  const value = p.info(new p.Parser().feed(response(0x80, 0, 0, payload))[0]);
  assert.equal(value.hardware, 1); assert.equal(value.layout, 1); assert.equal(value.bootVersion, 1);
});
test("all frozen status values parse; reserved values fail closed", () => {
  for (const status of [...Array.from({length: 19}, (_, i) => i), 255]) {
    assert.equal(p.ack(new p.Parser().feed(ack(0x82, 7, 1, status))[0]).status, status);
  }
  assert.throws(() => new p.Parser().feed(ack(0x82, 7, 1, 19)), /unknown ACK/);
});
test("END and unknown commands are unrepresentable", () => {
  for (const cmd of [3, 5, 0x83]) assert.throws(() => p.frame(cmd, 1, 1), /prohibited/);
});
test("the 32nd segment and short input are rejected before writing", () => {
  assert.throws(() => p.dataPayload(input, 31), /prohibited/);
  assert.throws(() => p.beginPayload({...input, prefixHex: "01"}), /incomplete/);
  assert.throws(() => p.beginPayload({...input, packageBytes: 4096}), /length/);
});
test("full legal first-block prefix can never commit a 4 KiB block", () => {
  const payloads = Array.from({length: p.MAX_SEGMENTS}, (_, i) => p.dataPayload(input, i));
  assert.equal(payloads.length * 128, 3968);
  assert.equal(new DataView(payloads.at(-1).buffer).getUint32(0, true), 3840);
});
test("split and coalesced ACKs retain exact boundaries", () => {
  const parser = new p.Parser(), a = ack(0x81, 7, 0), b = ack(0x82, 7, 1);
  assert.deepEqual(parser.feed(a.subarray(0, 7)), []);
  const both = new Uint8Array(a.length - 7 + b.length); both.set(a.subarray(7)); both.set(b, a.length - 7);
  assert.deepEqual(parser.feed(both).map((f) => f.cmd), [0x81, 0x82]);
});
test("CRC failure and nine-byte BEGIN ACK fail closed", () => {
  const bad = ack(0x82, 7, 1); bad[10] ^= 1;
  assert.throws(() => new p.Parser().feed(bad), /CRC/);
  assert.throws(() => new p.Parser().feed(response(0x81, 7, 0, new Uint8Array(9))), /payload size/);
});
test("unbound and oversized trials cannot send BEGIN", async () => {
  const {probe, writes} = fake(); probe.bound = false;
  await assert.rejects(probe.trial(input, {segments: 31, chunkBytes: 142}), /verify/);
  probe.bound = true;
  await assert.rejects(probe.trial(input, {segments: 32, chunkBytes: 142}), /segment count/);
  assert.equal(writes.length, 0);
});
test("31 ACKed DATA frames end in ABORT, never END", async () => {
  const {probe, writes} = fake();
  const value = await probe.trial(input, {id: "safe", segments: 31, chunkBytes: 142});
  assert.equal(value.allDataAcknowledged, true);
  assert.equal(value.abortConfirmed, true);
  assert.deepEqual(writes.map((b) => b[2]), [1, ...Array(31).fill(2), 4]);
  assert.equal(value.endSent, false);
});
test("CRC NAK stops subsequent DATA and does not create another BEGIN", async () => {
  const {probe, writes} = fake(3);
  const value = await probe.trial(input, {id: "nak", segments: 31, chunkBytes: 142});
  assert.equal(value.firstAckError.status, 2);
  assert.equal(value.sentSegments, 4);
  assert.equal(value.abortConfirmed, true);
  assert.deepEqual(writes.map((b) => b[2]), [1, 2, 2, 2, 2, 4]);
});
test("unresolved platform write forbids even cleanup transmission", async () => {
  let count = 0;
  const probe = new p.Probe(() => { count++; return new Promise(() => {}); });
  probe.bound = true; probe.writeTimeoutMs = 15;
  const value = await probe.trial(input, {id: "stalled", segments: 31, chunkBytes: 142});
  assert.equal(value.writeUncertain, true);
  assert.equal(value.abortConfirmed, false);
  assert.equal(count, 1);
});
test("background transition stops DATA but still permits bounded ABORT", async () => {
  const {probe, writes} = fake();
  probe.active = () => writes.filter((b) => b[2] === 2).length < 3;
  const value = await probe.trial(input, {id: "pause", segments: 31, chunkBytes: 142});
  assert.equal(value.sentSegments, 3); assert.equal(value.abortConfirmed, true);
  assert.match(value.error, /backgrounded/);
});
