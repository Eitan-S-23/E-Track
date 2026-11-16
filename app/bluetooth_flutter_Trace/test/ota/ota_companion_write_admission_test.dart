import 'dart:async';
import 'dart:typed_data';

import 'package:ble_monitor/ota/ota_ble_codec.dart';
import 'package:ble_monitor/ota/ota_ble_transport.dart';
import 'package:crypto/crypto.dart';
import 'package:flutter_test/flutter_test.dart';

import 'ota_pipeline_transport_test.dart' show TestPipelinePeer, package;

class _PreparationGate implements OtaBleChannel {
  _PreparationGate(this.peer, this.mode);
  final TestPipelinePeer peer;
  final String mode;
  final entered = Completer<void>();
  final gate = Completer<void>();
  int _mtuReads = 0;

  void release() { if (!gate.isCompleted) gate.complete(); }

  Future<void> _wait() {
    if (!entered.isCompleted) entered.complete();
    return gate.future;
  }

  @override
  Object get deviceScope => peer.deviceScope;
  @override
  bool get isConnected => peer.isConnected;
  @override
  Stream<List<int>> get notifications => peer.notifications;

  @override
  Future<int> maxWriteChunkSize() async {
    _mtuReads++;
    // CAPS2 is the first write. Hold the following BEGIN2 size lookup.
    if (mode.startsWith('mtu') && _mtuReads == 2) await _wait();
    return peer.maxWriteChunkSize();
  }

  @override
  Future<void> writeChunk(List<int> chunk, {OtaWriteAdmission? admission}) async {
    final command = peer.pending.isEmpty && chunk.length >= 3 ? chunk[2] : null;
    if (mode.startsWith('native') && command == OtaBleCodec.cmdBegin2) await _wait();
    await peer.writeChunk(chunk, admission: admission);
    if (mode == 'queued-info' && command == OtaBleCodec.cmdGetInfo) await _wait();
  }
}

Future<OtaAckResult> _transfer(OtaBleTransport transport, Uint8List bytes) =>
    transport.transfer(package: bytes, packageSha256: sha256.convert(bytes).bytes,
        etuHeader: bytes.sublist(0, 64));

Matcher _code(String code) =>
    isA<OtaTransportException>().having((error) => error.code, 'code', code);

int _frames(TestPipelinePeer peer, int command) =>
    peer.frames.where((frame) => frame.cmd == command).length;

void main() {
  test('write admission is synchronous, one-shot and revocable before dispatch', () {
    var checks = 0;
    final admission = OtaWriteAdmission(() { checks++; });
    expect(admission.dispatched, isFalse);
    admission.dispatch();
    expect(admission.dispatched, isTrue);
    expect(admission.rejected, isFalse);
    expect(admission.dispatch, throwsStateError);
    expect(checks, 1);
    final retired = OtaWriteAdmission(() { checks++; })..retire();
    expect(retired.dispatch, throwsStateError);
    expect(retired.dispatched, isFalse);
    expect(retired.rejected, isTrue);
    expect(checks, 1);
    final error = StateError('expired');
    final refused = OtaWriteAdmission(() { checks++; throw error; });
    expect(refused.dispatch, throwsA(same(error)));
    expect(refused.dispatched, isFalse);
    expect(refused.dispatch, throwsStateError);
    expect(checks, 2, reason: 'A refused gate cannot be rearmed');
  });

  test('timed-out V2 preparation cannot write late or poison the channel', () async {
    final peer = TestPipelinePeer();
    final channel = _PreparationGate(peer, 'native');
    var guards = 0;
    final transport = OtaBleTransport(channel: channel,
      writeTimeout: const Duration(milliseconds: 20),
      beforeInitialBegin: () { guards++; });
    addTearDown(peer.events.close);
    addTearDown(transport.dispose);
    try {
      await expectLater(_transfer(transport, package(1024)), throwsA(_code('WRITE_TIMEOUT')));
      expect(channel.entered.isCompleted, isTrue);
      expect(guards, 0);
      expect(peer.frames.map((frame) => frame.cmd), [OtaBleCodec.cmdCaps2]);
      channel.release();
      await Future<void>.delayed(Duration.zero);
      expect(_frames(peer, OtaBleCodec.cmdBegin2), 0);
      expect(peer.writes.length, 1, reason: 'Only CAPS2 reached the peer');
      await transport.getDeviceInfo();
      expect(_frames(peer, OtaBleCodec.cmdGetInfo), 1, reason: 'No extra resynchronization');
      expect(peer.writes.length, 2);
    } finally {
      channel.release();
    }
  });

  for (final mode in ['mtu', 'mtu-pause', 'queued-info', 'native-pause']) {
    for (final allow in [false, true]) {
      test('V2 initial admission after $mode: allow=$allow', () async {
        final peer = TestPipelinePeer()..chunkSize = 20;
        final channel = _PreparationGate(peer, mode);
        var valid = true, guards = 0;
        final transport = OtaBleTransport(channel: channel, beforeInitialBegin: () {
          guards++;
          if (!valid) throw const OtaTransportException('expired', code: 'STALE_DEVICE_CONSENT');
          valid = false; // Already admitted fragments, DATA and END must finish safely.
        });
        addTearDown(peer.events.close);
        addTearDown(transport.dispose);
        Future<void>? info;
        if (mode == 'queued-info') {
          info = transport.getDeviceInfo().then((_) {});
          await channel.entered.future.timeout(const Duration(seconds: 2));
        }
        final operation = _transfer(transport, package(1024));
        final observed = allow
            ? expectLater(operation, completion(isA<OtaAckResult>().having((ack) => ack.isOk, 'isOk', isTrue)))
            : expectLater(operation, throwsA(_code('STALE_DEVICE_CONSENT')));
        try {
          await channel.entered.future.timeout(const Duration(seconds: 2));
          expect(guards, 0);
          expect(_frames(peer, OtaBleCodec.cmdBegin2), 0);
          final pause = mode.endsWith('-pause');
          if (pause) transport.pauseForBackground();
          valid = allow;
          channel.release();
          if (pause) {
            await transport.getDeviceInfo(timeout: const Duration(seconds: 1));
            expect(guards, 0, reason: 'Paused BEGIN must release the writer for INFO');
            expect(_frames(peer, OtaBleCodec.cmdBegin2), 0);
            transport.resumeFromBackground();
          }
          await info;
          await observed;
          expect(guards, 1);
          expect(_frames(peer, OtaBleCodec.cmdBegin2), allow ? 1 : 0);
          expect(_frames(peer, OtaBleCodec.cmdEnd2), allow ? 1 : 0);
          expect(peer.pending, isEmpty, reason: 'Rejected consent cannot leave a BEGIN prefix');
          if (!allow) {
            expect(peer.frames.every((frame) =>
                frame.cmd == OtaBleCodec.cmdCaps2 || frame.cmd == OtaBleCodec.cmdGetInfo), isTrue);
          }
        } finally {
          channel.release();
          transport.resumeFromBackground();
          await observed;
        }
      });
    }
  }
}
