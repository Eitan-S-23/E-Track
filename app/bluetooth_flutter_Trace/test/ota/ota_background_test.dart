import 'dart:async';

import 'package:ble_monitor/ota/ota_background.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  const channel = MethodChannel('trace/device_ota');
  const codec = StandardMethodCodec();
  final messenger = TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger;
  final key = OtaTaskKey(taskId: 'process_1', generation: 1,
      deviceToken: 'a' * 64, packageSha256: 'b' * 64);
  OtaTaskSnapshot snapshot({String phase = 'transferring'}) => OtaTaskSnapshot(
      key: key, revision: 1, phase: phase, totalBytes: 8192,
      durableBytes: 4096, receivedBytes: 8192, canCancel: true,
      targetVerified: false, backgroundAcquired: false);

  Future<Object?> callback(String method, Object args) async {
    final result = Completer<Object?>();
    // Simulates native -> Dart on the actual registered platform channel.
    messenger.handlePlatformMessage(channel.name,
        codec.encodeMethodCall(MethodCall(method, args)), (data) {
          result.complete(data == null ? null : codec.decodeEnvelope(data));
        });
    return result.future;
  }

  tearDown(() => messenger.setMockMethodCallHandler(channel, null));

  test('snapshot transfer is durable; apply/reboot have no invented percentage', () {
    expect(snapshot().progress, .5);
    expect(snapshot(phase: 'downloading').progress, 1);
    for (final phase in ['checkingPackage', 'applying', 'reconnecting', 'verifying']) {
      expect(snapshot(phase: phase).progress, isNull);
    }
    expect(snapshot().toMap()['targetVerified'], isFalse);
    expect(key.matches({...key.toMap(), 'generation': 2}), isFalse);
    expect(key.matches({...key.toMap(), 'packageSha256': 'c' * 64}), isFalse);
    expect(key.matches({...key.toMap(), 'deviceToken': 'c' * 64}), isFalse);
  });

  test('request success boolean is NOT an acquired owner', () async {
    messenger.setMockMethodCallHandler(channel, (call) async => call.method == 'acquire' ? true : null);
    final client = OtaBackgroundClient(supported: true);
    addTearDown(client.close);
    expect(await client.acquire(snapshot(), ownerLive: () => true,
      onLost: (_) {}, onCancel: () async {}, onOpen: () {}), isFalse);
    expect(client.isAcquired, isFalse);
  });

  test('delayed acknowledgement, same-engine probe and bound callbacks', () async {
    final ack = Completer<Object>();
    messenger.setMockMethodCallHandler(channel, (call) async =>
        call.method == 'acquire' ? ack.future : null);
    final client = OtaBackgroundClient(supported: true);
    addTearDown(client.close);
    var cancelled = 0, opened = 0;
    final acquiring = client.acquire(snapshot(), ownerLive: () => true,
        onLost: (_) {}, onCancel: () async { cancelled++; }, onOpen: () { opened++; });
    expect(client.isAcquired, isFalse);
    expect(await callback('probe', key.toMap()), {'ownerLive': true, ...key.toMap()});
    ack.complete({'status': 'ACQUIRED', ...key.toMap()});
    expect(await acquiring, isTrue);
    await callback('cancel', {...key.toMap(), 'generation': 2});
    await callback('open', {...key.toMap(), 'taskId': 'old_process'});
    expect(cancelled, 0);
    expect(opened, 0);
    await callback('cancel', key.toMap());
    await callback('open', key.toMap());
    expect(cancelled, 1);
    expect(opened, 1);
  });

  for (final reason in ['NOTIFICATION_PERMISSION_DENIED', 'CHANNEL_DISABLED',
    'BLUETOOTH_PERMISSION_DENIED', 'SERVICE_START_REJECTED', 'ENGINE_UNAVAILABLE']) {
    test('rejected acquisition remains foreground-only: $reason', () async {
      messenger.setMockMethodCallHandler(channel, (call) async => call.method == 'acquire'
          ? {'status': 'UNAVAILABLE', 'reason': reason, ...key.toMap()} : null);
      final client = OtaBackgroundClient(supported: true);
      addTearDown(client.close);
      expect(await client.acquire(snapshot(), ownerLive: () => true,
        onLost: (_) {}, onCancel: () async {}, onOpen: () {}), isFalse);
      expect(client.reason, reason);
    });
  }

  test('timeout releases task; a late acquired response cannot revive it', () async {
    final ack = Completer<Object>();
    final calls = <String>[];
    messenger.setMockMethodCallHandler(channel, (call) async {
      calls.add(call.method);
      return call.method == 'acquire' ? ack.future : null;
    });
    final client = OtaBackgroundClient(supported: true,
        acquireTimeout: const Duration(milliseconds: 5));
    addTearDown(client.close);
    expect(await client.acquire(snapshot(), ownerLive: () => true,
      onLost: (_) {}, onCancel: () async {}, onOpen: () {}), isFalse);
    expect(client.reason, 'ACQUIRE_TIMEOUT');
    ack.complete({'status': 'ACQUIRED', ...key.toMap()});
    await Future<void>.delayed(Duration.zero);
    expect(client.isAcquired, isFalse);
    expect(calls, contains('release'));
  });

  test('ownership loss is visible; old cleanup does not release newer Dart owner', () async {
    final lost = <String>[];
    messenger.setMockMethodCallHandler(channel, (call) async => call.method == 'acquire'
        ? {'status': 'ACQUIRED', ...key.toMap()} : true);
    final client = OtaBackgroundClient(supported: true);
    addTearDown(client.close);
    await client.acquire(snapshot(), ownerLive: () => true,
      onLost: lost.add, onCancel: () async {}, onOpen: () {});
    await client.release(OtaTaskKey(taskId: 'old', generation: 9,
        deviceToken: key.deviceToken, packageSha256: key.packageSha256));
    expect(client.isAcquired, isTrue);
    await callback('lost', key.toMap());
    expect(client.isAcquired, isFalse);
    expect(lost, ['EXECUTION_OWNERSHIP_LOST']);
  });

  test('owner becoming unavailable before ACK rejects handoff', () async {
    messenger.setMockMethodCallHandler(channel, (call) async => call.method == 'acquire'
        ? {'status': 'ACQUIRED', ...key.toMap()} : null);
    final client = OtaBackgroundClient(supported: true);
    addTearDown(client.close);
    expect(await client.acquire(snapshot(), ownerLive: () => false,
        onLost: (_) {}, onCancel: () async {}, onOpen: () {}), isFalse);
  });
}
