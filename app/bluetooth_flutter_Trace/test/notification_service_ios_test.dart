import 'package:ble_monitor/services/notification_service.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';

// The plugin caches its platform on first construction. Keep Darwin in its own
// test-file isolate rather than switching an already-created Android singleton.
void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  const channel = MethodChannel('dexterous.com/flutter/local_notifications');
  setUp(() { debugDefaultTargetPlatformOverride = TargetPlatform.iOS; });
  tearDown(() {
    debugDefaultTargetPlatformOverride = null;
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(channel, null);
  });

  for (final granted in [false, true]) {
    test('iOS retains first-install authorization and reports explicit result $granted', () async {
      final calls = <MethodCall>[];
      TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
          .setMockMethodCallHandler(channel, (call) async {
        calls.add(call);
        return call.method == 'requestPermissions' ? granted : true;
      });
      final service = NotificationService.forTesting();
      await service.initialize();
      expect(calls.single.method, 'initialize');
      final initialization = calls.single.arguments as Map;
      expect(initialization['requestAlertPermission'], isTrue);
      expect(initialization['requestBadgePermission'], isTrue);
      expect(initialization['requestSoundPermission'], isTrue);
      expect(await service.requestNotificationPermission(), granted);
      expect(await service.requestNotificationPermission(), granted);
      final requests = calls.where((call) => call.method == 'requestPermissions').toList();
      expect(requests, hasLength(2), reason: 'Explicit retries must query the actual native result');
      for (final request in requests) {
        expect(request.arguments, containsPair('alert', true));
        expect(request.arguments, containsPair('badge', true));
        expect(request.arguments, containsPair('sound', true));
      }
      expect(calls.where((call) => call.method == 'requestNotificationsPermission'), isEmpty);
    });
  }
}
