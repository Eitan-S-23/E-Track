import 'dart:async';
import 'dart:math' as math;
import 'dart:typed_data';

import 'package:ble_monitor/ota/ota_ble_codec.dart';
import 'package:ble_monitor/ota/ota_ble_transport.dart';
import 'package:ble_monitor/ota/ota_link_stats.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter/foundation.dart' show debugPrint;

// Protocol peer only: synthetic bytes are never offered to a real device.
class _Peer implements OtaBleChannel {
  final events = StreamController<List<int>>.broadcast(sync: true);
  final pending = <int>[];
  final frames = <OtaBleFrame>[];
  final writes = <List<int>>[];
  final offsetsBeforeCommit = <int>[];
  final sequences = <int, List<int>>{};
  bool connected = true, supports = true, badCaps = false, holdDurable = false;
  bool badEnd = false, badBegin = false;
  bool holdLegacyAcks = false;
  int? dropOffset;
  int dropBegin = 0;
  int chunkSize = 244, notifySize = 3;
  int nonce = 0, total = 0, durable = 0, accepted = 0, beginSeq = 0, lastSeq = 0;
  int resume = 0;
  Uint8List received = Uint8List(0);
  void Function(OtaBleFrame)? onData;
  void Function(OtaBleFrame)? onEnd;
  void Function(Uint8List)? mutateDataAck;

  @override
  Object get deviceScope => this;
  @override
  bool get isConnected => connected;
  @override
  Stream<List<int>> get notifications => events.stream;
  @override
  Future<int> maxWriteChunkSize() async => chunkSize;

  int word(List<int> bytes, int offset) => ByteData.sublistView(Uint8List.fromList(bytes))
      .getUint32(offset, Endian.little);

  void reply(int cmd, int session, int seq, List<int> payload) {
    final frame = OtaBleCodec.encodeCommand(cmd: cmd, session: session, seq: seq, payload: payload);
    for (var offset = 0; offset < frame.length; offset += notifySize) {
      events.add(frame.sublist(offset, math.min(offset + notifySize, frame.length)));
    }
  }

  void ack(int cmd, int seq, {int status = 0, int? epoch, int? off, int? receivedOff}) {
    final base = cmd == 0x91 ? 2 : 1;
    final data = ByteData(base + 16);
    data.setUint8(0, status);
    if (base == 2) data.setUint8(1, 7);
    data.setUint32(base, epoch ?? nonce, Endian.little);
    data.setUint32(base + 4, off ?? durable, Endian.little);
    data.setUint32(base + 8, receivedOff ?? accepted, Endian.little);
    data.setUint32(base + 12, math.min(durable + 8192, total), Endian.little);
    final payload = data.buffer.asUint8List();
    if (cmd == 0x92) mutateDataAck?.call(payload);
    reply(cmd, 7, seq, payload);
  }

  void commit() {
    durable = accepted;
    ack(0x92, lastSeq);
  }

  @override
  Future<void> writeChunk(List<int> chunk) async {
    if (!connected) throw StateError('disconnected');
    writes.add(List<int>.of(chunk));
    pending.addAll(chunk);
    while (pending.length >= 10) {
      final size = 10 + pending[6] + (pending[7] << 8);
      if (pending.length < size) return;
      final frame = OtaBleCodec.decodeFrame(pending.sublist(0, size));
      pending.removeRange(0, size);
      frames.add(frame);
      switch (frame.cmd) {
        case 0x10:
          if (!supports) break;
          nonce = word(frame.payload, 0);
          final caps = ByteData(16);
          caps.buffer.asUint8List().setRange(0, 8, [80, 50, 66, 76, 2, 2, 128, 0]);
          caps.setUint32(8, nonce, Endian.little);
          caps.setUint32(12, badCaps ? 28 : 24, Endian.little);
          reply(0x90, 0, frame.seq, caps.buffer.asUint8List());
          break;
        case 0x11:
          expect(word(frame.payload, 101), nonce);
          total = word(frame.payload, 1);
          durable = accepted = resume;
          received = Uint8List(total);
          beginSeq = frame.seq;
          if (dropBegin > 0) { dropBegin--; break; }
          ack(0x91, frame.seq, receivedOff: badBegin ? resume + 128 : resume);
          break;
        case 0x12:
          final offset = word(frame.payload, 4);
          expect(word(frame.payload, 0), nonce);
          expect(frame.seq, (beginSeq + 1 + (offset - resume) ~/ 128) & 0xffff);
          sequences.putIfAbsent(offset, () => []).add(frame.seq);
          onData?.call(frame);
          if (dropOffset == offset) { dropOffset = null; break; }
          if (offset > accepted) { ack(0x92, frame.seq, status: 6); break; }
          if (offset == accepted) {
            expect(offset + frame.payload.length - 8, lessThanOrEqualTo(math.min(total, durable + 8192)));
            received.setRange(offset, offset + frame.payload.length - 8, frame.payload.sublist(8));
            accepted += frame.payload.length - 8;
            lastSeq = frame.seq;
            if (durable == 0) offsetsBeforeCommit.add(offset);
          }
          if (!holdDurable) {
            if (accepted == total) {
              durable = total;
            } else if (accepted - durable == 8192) {
              durable += 4096;
            }
          }
          ack(0x92, frame.seq);
          break;
        case 0x13:
          expect(frame.seq, (beginSeq + 1 + (total - resume + 127) ~/ 128) & 0xffff);
          if (onEnd != null) {
            onEnd!(frame);
            break;
          }
          ack(0x93, frame.seq, off: badEnd ? 0 : total);
          break;
        case 0x14:
          expect(word(frame.payload, 0), nonce);
          ack(0x94, frame.seq, status: 0xff);
          break;
        case 1:
          total = word(frame.payload, 1);
          final payload = Uint8List(10)..[1] = 7;
          reply(0x81, 7, frame.seq, payload);
          break;
        case 2:
          accepted = word(frame.payload, 0) + frame.payload.length - 4;
          if (accepted == total || accepted % 4096 == 0) durable = accepted;
          if (holdLegacyAcks) break;
          final bytes = ByteData(9)..setUint32(1, durable, Endian.little);
          final segments = (accepted - durable + 127) ~/ 128;
          bytes.setUint32(5, (1 << segments) - 1, Endian.little);
          reply(0x82, 7, frame.seq, bytes.buffer.asUint8List());
          break;
        case 3:
          final bytes = ByteData(9)..setUint32(1, total, Endian.little);
          reply(0x83, 7, frame.seq, bytes.buffer.asUint8List());
          break;
      }
    }
  }
}

Uint8List package(int len) => Uint8List.fromList(List.generate(len, (i) => i & 255));

Future<OtaAckResult> transfer(OtaBleTransport transport, Uint8List bytes,
    {void Function(int, int)? progress}) => transport.transfer(package: bytes,
      packageSha256: List.filled(32, 1), etuHeader: bytes.sublist(0, 64), onDurableProgress: progress);

OtaBleTransport sender(OtaBleChannel peer, {bool enabled = true, Duration? budget,
    int batch = 1, OtaLinkStats? stats}) =>
    OtaBleTransport(channel: peer, enablePipeline: enabled,
      dataBatchFrames: batch, stats: stats,
      ackTimeout: const Duration(milliseconds: 30),
      noProgressTimeout: budget ?? const Duration(seconds: 3));

Future<void> until(bool Function() condition) async {
  for (var i = 0; i < 1000; i++) {
    if (condition()) return;
    await Future<void>.delayed(const Duration(milliseconds: 1));
  }
  fail('condition did not become true within bounded wait');
}

void main() {
  test('v2 defaults preserve batch12 without an experiment configuration', () async {
    final peer = _Peer();
    final transport = OtaBleTransport(channel: peer, enablePipeline: true);
    expect(transport.dataBatchFrames, 12);
    final bytes = package(9000);
    expect((await transfer(transport, bytes)).isOk, isTrue);
    expect(peer.received, bytes);
    expect(peer.writes.any((chunk) => chunk.length == 244), isTrue);
    expect(peer.offsetsBeforeCommit, contains(4096));
    await transport.dispose();
    await peer.events.close();
  });

  test('v2 default falls back to four v1 credits and single-frame writes', () async {
    final peer = _Peer()..supports = false..holdLegacyAcks = true;
    final transport = OtaBleTransport(channel: peer, enablePipeline: true,
        ackTimeout: const Duration(milliseconds: 300));
    final bytes = package(1000);
    final pending = transport.transfer(package: bytes, packageSha256: List.filled(32, 1),
        etuHeader: bytes.sublist(0, 64), windowSegments: 24);
    // Observe the pending result even if an assertion below fails.
    final settled = pending.then<Object>((value) => value, onError: (Object error) => error);
    try {
      await until(() => peer.frames.where((frame) => frame.cmd == 2).length >= 4);
      await Future<void>.delayed(const Duration(milliseconds: 5));
      expect(peer.frames.where((frame) => frame.cmd == 2).length, 4);
      peer.holdLegacyAcks = false;
      final ack = ByteData(9)..setUint32(5, 0x0f, Endian.little);
      peer.reply(0x82, 7, peer.frames.lastWhere((frame) => frame.cmd == 2).seq,
          ack.buffer.asUint8List());
      expect((await pending).isOk, isTrue);
      expect(peer.writes.where((chunk) => chunk.length >= 3 && chunk[2] == 2)
          .every((chunk) => chunk.length <= 142), isTrue);
    } finally {
      await transport.dispose();
      await settled;
      await peer.events.close();
    }
  });

  for (final status in [0x0f, 0x7e]) {
    test('first matching v2 error preserves raw status $status without credit', () async {
      final peer = _Peer()..holdDurable = true;
      final stats = OtaLinkStats(label: 'upgrade');
      final transport = sender(peer, stats: stats);
      final progress = <int>[];
      peer.onData = (frame) => peer.ack(0x92, frame.seq, status: status);
      await expectLater(transfer(transport, package(1000), progress: (value, _) => progress.add(value)),
        throwsA(isA<OtaTransportException>().having((error) => error.code, 'code',
          status == 0x0f ? 'ACK_STATUS' : 'ACK_MALFORMED')));
      final error = ((stats.toJson()['transfer'] as Map)['acks'] as Map)['firstError'] as Map;
      expect(error['status'], status);
      expect(error['cmd'], 0x92);
      expect(error['session'], 7);
      expect(error['seq'], peer.frames.firstWhere((frame) => frame.cmd == 0x12).seq);
      expect(error['epoch'], peer.nonce);
      expect(error['durable'], 0);
      expect(error['accepted'], 0);
      expect(error['credit'], 1000);
      expect(progress, [0]);
      expect(peer.frames.any((frame) => frame.cmd == 0x13 || frame.cmd == 1), isFalse);
      await transport.dispose();
      await peer.events.close();
    });
  }

  test('stale epoch and unsent sequence errors cannot poison the active first error', () async {
    final peer = _Peer();
    final stats = OtaLinkStats(label: 'upgrade');
    final transport = sender(peer, stats: stats);
    peer.onData = (frame) {
      peer.ack(0x92, frame.seq, status: 15, epoch: peer.nonce ^ 1);
      peer.ack(0x92, (frame.seq + 2048) & 0xffff, status: 0x7e);
    };
    expect((await transfer(transport, package(1000))).isOk, isTrue);
    expect((stats.toJson()['transfer'] as Map)['acks'], isNot(contains('firstError')));
    await transport.dispose();
    await peer.events.close();
  });

  test('truncated matching ACK preserves missing fields as null, not zero', () async {
    final peer = _Peer();
    final stats = OtaLinkStats(label: 'upgrade');
    final transport = sender(peer, stats: stats);
    peer.onData = (frame) => peer.reply(0x92, 7, frame.seq, [15]);
    await expectLater(transfer(transport, package(1000)),
      throwsA(isA<OtaTransportException>().having((error) => error.code, 'code', 'ACK_MALFORMED')));
    final error = ((stats.toJson()['transfer'] as Map)['acks'] as Map)['firstError'] as Map;
    expect(error['payloadBytes'], 1);
    expect(error['status'], 15);
    for (final field in ['epoch', 'durable', 'accepted', 'credit']) {
      expect(error[field], isNull);
    }
    expect(peer.frames.any((frame) => frame.cmd == 0x13), isFalse);
    await transport.dispose();
    await peer.events.close();
  });

  for (final badBegin in [true, false]) {
    test('invalid v2 ${badBegin ? 'BEGIN' : 'END'} credit is retained', () async {
      final peer = _Peer()..badBegin = badBegin..badEnd = !badBegin;
      final stats = OtaLinkStats(label: 'upgrade');
      final transport = sender(peer, stats: stats);
      await expectLater(transfer(transport, package(1000)),
        throwsA(isA<OtaTransportException>().having((error) => error.code, 'code', 'ACK_MALFORMED')));
      final error = ((stats.toJson()['transfer'] as Map)['acks'] as Map)['firstError'] as Map;
      expect(error['cmd'], badBegin ? 0x91 : 0x93);
      expect(error['reason'], 'ACK_MALFORMED');
      expect(error['status'], 0);
      expect(error['epoch'], peer.nonce);
      await transport.dispose();
      await peer.events.close();
    });
  }

  test('v2 success and v1 fallback emit one compatible start and END marker', () async {
    final previousPrint = debugPrint;
    final logs = <String>[];
    debugPrint = (String? message, {int? wrapWidth}) {
      if (message != null) logs.add(message);
    };
    addTearDown(() => debugPrint = previousPrint);
    for (final supports in [true, false]) {
      logs.clear();
      final peer = _Peer()..supports = supports..dropBegin = supports ? 1 : 0;
      final transport = sender(peer);
      expect((await transfer(transport, package(1000))).isOk, isTrue);
      expect(logs.where((s) => s.startsWith('OTA_MONO MONO_BUDGET_START ')).length, 1);
      expect(logs.where((s) => s.startsWith('OTA_MONO MONO_END_ACK_OK ')).length, 1);
      expect(logs.any((s) => s.startsWith('OTA_MONO MONO_END_ACK_OK ') && s.endsWith('durable=1000')), isTrue);
      await transport.dispose();
      await peer.events.close();
    }
  });

  test('invalid v2 END emits no successful endpoint marker', () async {
    final previousPrint = debugPrint;
    final logs = <String>[];
    debugPrint = (String? message, {int? wrapWidth}) {
      if (message != null) logs.add(message);
    };
    addTearDown(() => debugPrint = previousPrint);
    final peer = _Peer()..badEnd = true;
    final transport = sender(peer);
    await expectLater(transfer(transport, package(1000)), throwsA(isA<OtaTransportException>()));
    expect(logs.where((s) => s.startsWith('OTA_MONO MONO_BUDGET_START ')).length, 1);
    expect(logs.any((s) => s.startsWith('OTA_MONO MONO_END_ACK_OK ')), isFalse);
    await transport.dispose();
    await peer.events.close();
  });

  test('v2 END timing uses only validated matched arrival, not later write settlement', () async {
    var clock = 100;
    final peer = _Peer();
    final stats = OtaLinkStats(label: 'pipeline', clockUs: () => clock);
    final transport = OtaBleTransport(channel: peer, enablePipeline: true, stats: stats);
    peer.onEnd = (frame) {
      clock = 300;
      peer.ack(0x93, frame.seq);
      clock = 350;
      peer.ack(0x93, (frame.seq + 1) & 0xffff);
      clock = 900;
    };
    expect((await transfer(transport, package(1000))).isOk, isTrue);
    expect((stats.toJson()['transfer'] as Map)['endAckUs'], 300);
    await transport.dispose();
    await peer.events.close();
  });

  test('incomplete v2 END does not record a successful transfer endpoint', () async {
    final peer = _Peer()..badEnd = true;
    final stats = OtaLinkStats(label: 'pipeline');
    final transport = OtaBleTransport(channel: peer, enablePipeline: true, stats: stats);
    await expectLater(transfer(transport, package(1000)), throwsA(isA<OtaTransportException>()));
    expect((stats.toJson()['transfer'] as Map)['endAckUs'], isNull);
    await transport.dispose();
    await peer.events.close();
  });

  test('batch12 cancellation completes only the partially dispatched frame before ABORT2', () async {
    final peer = _Peer();
    final transport = sender(peer, batch: 12);
    peer.onData = (_) => transport.cancel();
    await expectLater(transfer(transport, package(9000)),
        throwsA(isA<OtaTransportException>().having((e) => e.code, 'code', 'CANCELLED')));
    await transport.abortBestEffort();
    expect(peer.frames.where((f) => f.cmd == 0x12).length, lessThanOrEqualTo(2));
    expect(peer.frames.last.cmd, 0x14);
    expect(peer.pending, isEmpty);
    await transport.dispose();
    await peer.events.close();
  });
  test('pipeline preserves measured batch12 and rejects undispatched reservations', () async {
    final peer = _Peer();
    final transport = sender(peer, batch: 12);
    expect((await transfer(transport, package(9000))).isOk, isTrue);
    expect(peer.offsetsBeforeCommit, contains(4096));
    await transport.dispose();
    await peer.events.close();
    final bad = _Peer();
    bad.mutateDataAck = (payload) => ByteData.sublistView(payload).setUint32(9, 12 * 128, Endian.little);
    final rejected = sender(bad, batch: 12);
    await expectLater(transfer(rejected, package(9000)),
        throwsA(isA<OtaTransportException>().having((e) => e.code, 'code', 'ACK_MALFORMED')));
    expect(bad.frames.any((f) => f.cmd == 0x13), isFalse);
    await rejected.dispose();
    await bad.events.close();
  });
  test('real transport crosses block boundary, fragments frames and waits for durable END', () async {
    final peer = _Peer()..chunkSize = 20;
    final transport = sender(peer);
    final bytes = package(9000);
    final progress = <int>[];
    final result = await transfer(transport, bytes, progress: (off, _) => progress.add(off));
    expect(result.isOk, isTrue);
    expect(peer.offsetsBeforeCommit, contains(4096));
    expect(peer.received, bytes);
    expect(progress, [0, 4096, 9000]);
    expect(peer.frames.where((f) => f.cmd == 0x13).length, 1);
    expect(peer.pending, isEmpty);
    await transport.dispose();
    await peer.events.close();
  });

  test('missing capability falls back to v1; default makes no probe', () async {
    for (final enabled in [true, false]) {
      final peer = _Peer()..supports = false;
      final transport = sender(peer, enabled: enabled);
      expect((await transfer(transport, package(1000))).isOk, isTrue);
      expect(peer.frames.any((f) => f.cmd == 0x10), enabled);
      expect(peer.frames.any((f) => f.cmd == 1), isTrue);
      expect(peer.frames.any((f) => f.cmd == 0x11), isFalse);
      await transport.dispose();
      await peer.events.close();
    }
  });

  test('malformed capability or BEGIN never grants DATA or falls back', () async {
    for (final badBegin in [false, true]) {
      final peer = _Peer()..badCaps = !badBegin..badBegin = badBegin;
      final transport = sender(peer);
      await expectLater(transfer(transport, package(1000)),
          throwsA(isA<OtaTransportException>().having((e) => e.code, 'code', 'ACK_MALFORMED')));
      expect(peer.frames.any((f) => f.cmd == 0x12 || f.cmd == 1), isFalse);
      await transport.dispose();
      await peer.events.close();
    }
  });

  test('lost BEGIN and DATA retries retain sequence and package bytes', () async {
    final peer = _Peer()..dropBegin = 1..dropOffset = 0;
    final transport = sender(peer);
    final bytes = package(9000);
    expect((await transfer(transport, bytes)).isOk, isTrue);
    expect(peer.frames.where((f) => f.cmd == 0x11).map((f) => f.seq).toSet().length, 1);
    expect(peer.sequences[0]!.length, 2);
    for (final seqs in peer.sequences.values) { expect(seqs.toSet().length, 1); }
    expect(peer.received, bytes);
    await transport.dispose();
    await peer.events.close();
  });

  test('accepted RAM does not report durable progress or authorize END', () async {
    final peer = _Peer()..holdDurable = true;
    final transport = sender(peer);
    final progress = <int>[];
    final pending = transfer(transport, package(8192), progress: (off, _) => progress.add(off));
    await until(() => peer.accepted == 8192);
    expect(progress, [0]);
    expect(peer.frames.any((f) => f.cmd == 0x13), isFalse);
    peer.commit();
    expect((await pending).isOk, isTrue);
    expect(progress, [0, 8192]);
    await transport.dispose();
    await peer.events.close();
  });

  test('stale epoch is ignored but future accepted credit fails closed', () async {
    final peer = _Peer();
    final transport = sender(peer);
    peer.onData = (frame) => peer.ack(0x92, frame.seq, epoch: peer.nonce ^ 1, receivedOff: 0x100000);
    expect((await transfer(transport, package(1000))).isOk, isTrue);
    await transport.dispose();
    await peer.events.close();
    final badPeer = _Peer();
    badPeer.mutateDataAck = (payload) => ByteData.sublistView(payload).setUint32(9, 8192, Endian.little);
    final badTransport = sender(badPeer);
    await expectLater(transfer(badTransport, package(9000)),
        throwsA(isA<OtaTransportException>().having((e) => e.code, 'code', 'ACK_MALFORMED')));
    expect(badPeer.frames.where((f) => f.cmd == 0x12).length, 1);
    expect(badPeer.frames.any((f) => f.cmd == 0x13), isFalse);
    await badTransport.dispose();
    await badPeer.events.close();
  });

  test('cancel or background transition stops DATA and sends epoch-bound ABORT2', () async {
    for (final background in [false, true]) {
      final peer = _Peer()..chunkSize = 20;
      final transport = sender(peer);
      peer.onData = (_) { if (background) { transport.pauseForBackground(); } else { transport.cancel(); } };
      await expectLater(transfer(transport, package(9000)),
          throwsA(isA<OtaTransportException>().having((e) => e.code, 'code', 'CANCELLED')));
      if (!background) await transport.abortBestEffort();
      await until(() => peer.frames.any((f) => f.cmd == 0x14));
      expect(peer.frames.where((f) => f.cmd == 0x12).length, 1);
      expect(peer.frames.any((f) => f.cmd == 4 || f.cmd == 0x13), isFalse);
      expect(peer.pending, isEmpty);
      await transport.dispose();
      await peer.events.close();
    }
  });

  test('new transport resumes durable prefix with a fresh epoch', () async {
    final peer = _Peer()..resume = 4096;
    var lastEpoch = 0;
    for (var i = 0; i < 2; i++) {
      final transport = sender(peer);
      expect((await transfer(transport, package(4113))).isOk, isTrue);
      expect(peer.nonce, isNot(lastEpoch));
      lastEpoch = peer.nonce;
      expect(peer.sequences.keys, [4096]);
      expect(peer.received.sublist(4096), package(4113).sublist(4096));
      await transport.dispose();
    }
    await peer.events.close();
  });

  test('no durable progress, disconnect and invalid END cannot become success', () async {
    for (final mode in [0, 1, 2]) {
      final peer = _Peer()..holdDurable = mode == 0..badEnd = mode == 2;
      if (mode == 1) peer.onData = (_) => peer.connected = false;
      final transport = sender(peer, budget: const Duration(milliseconds: 150));
      await expectLater(transfer(transport, package(1000)), throwsA(isA<OtaTransportException>()));
      await transport.dispose();
      await peer.events.close();
    }
  });
}
