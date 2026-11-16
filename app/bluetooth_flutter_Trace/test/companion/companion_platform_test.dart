import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ble_monitor/companion/companion_platform.dart';
import 'package:ble_monitor/ota/ota_background.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  const channel = MethodChannel('test/companion');
  final messenger = TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger;
  tearDown(() { messenger.setMockMethodCallHandler(channel, null); });

  test('opening a settings page is never interpreted as a grant', () async {
    final calls = <String>[];
    messenger.setMockMethodCallHandler(channel, (call) async {
      calls.add(call.method);
      if (call.method == 'settings') return true;
      return {'enabled': false, 'vendorAutostart': 'unknown', 'problem': 'NOTIFICATIONS_DISABLED'};
    });
    final platform = CompanionPlatform(channel: channel, supported: true);
    expect(await platform.openSettings('autostart'), isTrue);
    final state = await platform.snapshot();
    expect(state['enabled'], isFalse);
    expect(state['vendorAutostart'], 'unknown');
    expect(state['problem'], 'NOTIFICATIONS_DISABLED');
    expect(calls, ['settings', 'snapshot']);
  });
  test('missing native result cannot enable the companion', () async {
    messenger.setMockMethodCallHandler(channel, (_) async => null);
    final platform = CompanionPlatform(channel: channel, supported: true);
    expect((await platform.snapshot())['enabled'], isFalse);
    await expectLater(platform.configure(enabled: true, intervalHours: 12, wifiOnly: true), throwsStateError);
  });
  test('non-Android fallback does not make platform calls', () async {
    messenger.setMockMethodCallHandler(channel, (_) async => fail('unsupported platform invoked Android'));
    final platform = CompanionPlatform(channel: channel, supported: false);
    expect((await platform.snapshot())['problem'], 'ANDROID_ONLY');
  });
  test('companion OTA uses an explicit distinct admission and exact task acknowledgment', () async {
    final calls = <MethodCall>[];
    messenger.setMockMethodCallHandler(channel, (call) async {
      calls.add(call);
      if (call.method == 'acquireCompanion') return {...call.arguments as Map, 'status': 'ACQUIRED'};
      return null;
    });
    final client = OtaBackgroundClient(channel: channel, supported: true);
    final key = OtaTaskKey(taskId: 'task', generation: 1, deviceToken: 'aa' * 32, packageSha256: 'bb' * 32);
    final snapshot = OtaTaskSnapshot(key: key, revision: 1, phase: 'downloading',
      totalBytes: 1024, durableBytes: 0, receivedBytes: 0, canCancel: true,
      targetVerified: false, backgroundAcquired: false);
    expect(await client.acquire(snapshot, companionRuntimeId: 'runtime', ownerLive: () => true,
      onLost: (_) {}, onCancel: () async {}, onOpen: () {}), isTrue);
    expect(calls.first.method, 'acquireCompanion');
    expect((calls.first.arguments as Map)['companionRuntimeId'], 'runtime');
    await client.close();
  });
}
