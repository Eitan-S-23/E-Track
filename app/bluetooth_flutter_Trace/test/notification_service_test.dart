import 'dart:async';
import 'package:ble_monitor/services/notification_service.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  const channel = MethodChannel('dexterous.com/flutter/local_notifications');
  setUp(() { debugDefaultTargetPlatformOverride = TargetPlatform.android; });
  tearDown(() {
    debugDefaultTargetPlatformOverride = null;
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(channel, null);
  });

  test('concurrent initialization and permission callers share one native request', () async {
    final gate = Completer<bool>();
    final entered = Completer<void>();
    var initializes = 0;
    var permissions = 0;
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(channel, (call) async {
      if (call.method == 'initialize') { initializes++; return true; }
      if (call.method == 'requestNotificationsPermission') {
        permissions++;
        if (!entered.isCompleted) entered.complete();
        return gate.future;
      }
      return null;
    });
    final service = NotificationService.forTesting();
    final first = service.initialize();
    final second = service.initialize();
    final permission = service.requestNotificationPermission();
    await entered.future;
    expect(initializes, 1);
    expect(permissions, 1);
    gate.complete(false);
    await Future.wait([first, second]);
    expect(await permission, isFalse);
    expect(await service.requestNotificationPermission(), isFalse);
    expect(permissions, 2, reason: 'denial does not permanently suppress explicit retry');
  });

  test('failed initialization can be retried without a stuck single-flight future', () async {
    var calls = 0;
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(channel, (call) async {
      if (call.method == 'initialize' && calls++ == 0) {
        throw PlatformException(code: 'transient');
      }
      return true;
    });
    final service = NotificationService.forTesting();
    await expectLater(service.initialize(), throwsA(isA<PlatformException>()));
    await service.initialize();
    expect(calls, 2);
  });
}
