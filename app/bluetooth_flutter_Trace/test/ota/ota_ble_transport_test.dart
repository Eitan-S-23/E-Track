import 'dart:async';
import 'dart:typed_data';

import 'package:ble_monitor/ota/ota_ble_codec.dart';
import 'package:ble_monitor/ota/ota_ble_transport.dart';
import 'package:crypto/crypto.dart';
import 'package:flutter_test/flutter_test.dart';

import 'ota_pipeline_transport_test.dart' show TestPipelinePeer, package, until;

// V2 wire/credit tests live in ota_pipeline_transport_test.dart.
// Preserve the shared byte-stream and physical-write safety checks here.
class _ControlledPeer extends TestPipelinePeer {
  int dataChunks = 0;
  int? failChunk, holdChunk;
  Completer<void>? gate;
  final entered = Completer<void>();
  Duration delay = Duration.zero;
  bool dropDataAck = false, dropInfo = false, garbagePrefix = false;

  @override
  void reply(int cmd, int session, int seq, List<int> payload) {
    if ((dropDataAck && cmd == OtaBleCodec.rspAckData2) ||
        (dropInfo && cmd == OtaBleCodec.rspInfo)) {
      return;
    }
    if (garbagePrefix) events.add([0, 7, 0xa5, 0]);
    super.reply(cmd, session, seq, payload);
  }

  @override
  Future<void> writeChunk(List<int> chunk) async {
    final data = pending.isNotEmpty
        ? pending.length >= 3 && pending[2] == OtaBleCodec.cmdData2
        : chunk.length >= 3 && chunk[2] == OtaBleCodec.cmdData2;
    if (data) {
      dataChunks++;
      if (dataChunks == holdChunk) {
        if (!entered.isCompleted) entered.complete();
        await gate!.future;
      }
      if (delay != Duration.zero) await Future<void>.delayed(delay);
      if (dataChunks == failChunk) throw StateError('injected native write failure');
    }
    await super.writeChunk(chunk);
  }
}

class _Rebound implements OtaBleChannel {
  _Rebound(this.peer);
  final TestPipelinePeer peer;
  @override
  Object get deviceScope => peer.deviceScope;
  @override
  bool get isConnected => peer.isConnected;
  @override
  Stream<List<int>> get notifications => peer.notifications;
  @override
  Future<int> maxWriteChunkSize() => peer.maxWriteChunkSize();
  @override
  Future<void> writeChunk(List<int> chunk) => peer.writeChunk(chunk);
}

Future<OtaAckResult> _transfer(OtaBleTransport transport, Uint8List bytes) =>
    transport.transfer(package: bytes, packageSha256: sha256.convert(bytes).bytes,
        etuHeader: bytes.sublist(0, 64));

Matcher _code(String code) =>
    isA<OtaTransportException>().having((e) => e.code, 'code', code);

void main() {
  test('GET_INFO is shared metadata, not a V1 transfer', () async {
    final peer = _ControlledPeer()..garbagePrefix = true..notifySize = 1;
    final transport = OtaBleTransport(channel: peer);
    addTearDown(peer.events.close);
    addTearDown(transport.dispose);
    final info = await transport.getDeviceInfo();
    expect(info.currentVersionCode, 30286);
    expect(peer.frames.single.cmd, OtaBleCodec.cmdGetInfo);
    expect(peer.frames.single.session, 0);
    expect(peer.pending, isEmpty);
  });

  test('invalid batching fails before subscribing or writing', () async {
    final peer = TestPipelinePeer();
    addTearDown(peer.events.close);
    for (final batch in [0, 2, 4, 8, 11, 13, 32]) {
      expect(() => OtaBleTransport(channel: peer, dataBatchFrames: batch),
          throwsArgumentError);
    }
    expect(peer.events.hasListener, isFalse);
    expect(peer.writes, isEmpty);
  });

  for (final size in [20, 125, 244]) {
    for (final batch in [1, 3, 12]) {
      test('V2 batch $batch at chunk $size preserves blocks and short tail', () async {
        final peer = _ControlledPeer()..chunkSize = size..notifySize = 1;
        final transport = OtaBleTransport(channel: peer, dataBatchFrames: batch);
        addTearDown(peer.events.close);
        addTearDown(transport.dispose);
        final bytes = package(8321);
        expect((await _transfer(transport, bytes)).isOk, isTrue);
        expect(peer.received, bytes);
        expect(peer.frames.where((f) => f.cmd == 0x12).last.payload.length, 9);
        expect(peer.frames.map((f) => f.cmd).toSet(), {0x10, 0x11, 0x12, 0x13});
        expect(peer.writes.every((chunk) => chunk.length <= size), isTrue);
        expect(peer.pending, isEmpty);
      });
    }
  }

  test('completed V2 does not emit a legacy cleanup ABORT', () async {
    final peer = TestPipelinePeer();
    final transport = OtaBleTransport(channel: peer);
    addTearDown(peer.events.close);
    addTearDown(transport.dispose);
    expect((await _transfer(transport, package(1024))).isOk, isTrue);
    final writes = peer.writes.length;
    await transport.abortBestEffort();
    expect(peer.writes.length, writes);
  });

  test('disconnected query does not write', () async {
    final peer = TestPipelinePeer()..connected = false;
    final transport = OtaBleTransport(channel: peer);
    addTearDown(peer.events.close);
    addTearDown(transport.dispose);
    await expectLater(transport.getDeviceInfo(), throwsA(_code('DISCONNECTED')));
    await transport.abortBestEffort();
    expect(peer.writes, isEmpty);
  });

  test('disposed transport cannot be reused', () async {
    final peer = TestPipelinePeer();
    final transport = OtaBleTransport(channel: peer);
    addTearDown(peer.events.close);
    await transport.dispose();
    await expectLater(_transfer(transport, package(1024)), throwsA(_code('DISPOSED')));
    expect(peer.writes, isEmpty);
  });

  test('partial native error quarantines the device across wrappers', () async {
    final peer = _ControlledPeer()..chunkSize = 20..failChunk = 2;
    final original = OtaBleTransport(channel: peer);
    addTearDown(peer.events.close);
    addTearDown(original.dispose);
    await expectLater(_transfer(original, package(1024)), throwsStateError);
    final writes = peer.writes.length;
    expect(peer.pending, isNotEmpty);
    await original.abortBestEffort(allowResync: false);
    final rebound = OtaBleTransport(channel: _Rebound(peer));
    addTearDown(rebound.dispose);
    await expectLater(_transfer(rebound, package(1024)), throwsA(_code('WRITE_TIMEOUT')));
    expect(peer.writes.length, writes);
  });

  for (final lateFailure in [false, true]) {
    test('late settlement cannot clear timeout quarantine: error=$lateFailure', () async {
      final peer = _ControlledPeer()
        ..chunkSize = 20
        ..holdChunk = 2
        ..gate = Completer<void>();
      final original = OtaBleTransport(channel: peer,
          writeTimeout: const Duration(milliseconds: 25),
          noProgressTimeout: const Duration(milliseconds: 200));
      addTearDown(peer.events.close);
      addTearDown(original.dispose);
      final failure = expectLater(_transfer(original, package(1024)),
          throwsA(_code('WRITE_TIMEOUT')));
      await peer.entered.future;
      await failure;
      if (lateFailure) peer.failChunk = 2;
      peer.gate!.complete();
      await Future<void>.delayed(const Duration(milliseconds: 20));
      final writes = peer.writes.length;
      final rebound = OtaBleTransport(channel: _Rebound(peer));
      addTearDown(rebound.dispose);
      await expectLater(_transfer(rebound, package(1024)), throwsA(_code('WRITE_TIMEOUT')));
      expect(peer.writes.length, writes);
      expect(peer.frames.any((f) => f.cmd == 0x13), isFalse);
    });
  }

  test('slow fragmented writes share one durable deadline', () async {
    final peer = _ControlledPeer()..chunkSize = 20..delay = const Duration(milliseconds: 15);
    final transport = OtaBleTransport(channel: peer,
        writeTimeout: const Duration(milliseconds: 50),
        noProgressTimeout: const Duration(milliseconds: 100));
    addTearDown(peer.events.close);
    addTearDown(transport.dispose);
    final watch = Stopwatch()..start();
    await expectLater(_transfer(transport, package(9000)),
        throwsA(isA<OtaTransportException>().having((e) => e.code, 'bounded failure',
            isIn(['NO_DURABLE_PROGRESS', 'WRITE_TIMEOUT']))));
    expect(watch.elapsed, lessThan(const Duration(seconds: 1)));
    expect(peer.frames.any((f) => f.cmd == 0x13), isFalse);
  });

  test('lost DATA ACKs consume bounded retries without a new BEGIN', () async {
    final peer = _ControlledPeer()..dropDataAck = true;
    final transport = OtaBleTransport(channel: peer, retries: 1, dataBatchFrames: 1,
        ackTimeout: const Duration(milliseconds: 25),
        noProgressTimeout: const Duration(seconds: 2));
    addTearDown(peer.events.close);
    addTearDown(transport.dispose);
    await expectLater(_transfer(transport, package(1024)), throwsA(_code('TIMEOUT')));
    expect(peer.frames.where((f) => f.cmd == 0x11).length, 1);
    expect(peer.frames.any((f) => f.cmd == 0x13), isFalse);
    expect(peer.sequences.values.every((s) => s.length == 2 && s.toSet().length == 1), isTrue);
  });

  test('notify error retires an identity waiter without an uncaught callback', () async {
    final peer = _ControlledPeer()..dropInfo = true;
    final transport = OtaBleTransport(channel: peer);
    addTearDown(peer.events.close);
    addTearDown(transport.dispose);
    final failure = expectLater(transport.getDeviceInfo(), throwsStateError);
    await until(() => peer.frames.isNotEmpty);
    peer.events.addError(StateError('injected notify error'));
    await failure;
  });

  test('simultaneous transfers cannot acquire a second V2 session', () async {
    final peer = _ControlledPeer()..dropDataAck = true;
    final transport = OtaBleTransport(channel: peer);
    addTearDown(peer.events.close);
    addTearDown(transport.dispose);
    final stopped = expectLater(_transfer(transport, package(1024)),
        throwsA(_code('CANCELLED')));
    await until(() => peer.sequences.isNotEmpty);
    await expectLater(_transfer(transport, package(1024)), throwsA(_code('BUSY')));
    transport.cancel();
    await stopped;
    expect(peer.frames.where((f) => f.cmd == 0x11).length, 1);
  });
}
