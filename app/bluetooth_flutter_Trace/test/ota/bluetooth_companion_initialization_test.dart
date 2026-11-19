import 'dart:async';

import 'package:ble_monitor/services/bluetooth_service.dart';
import 'package:flutter/services.dart';
import 'package:flutter_blue_plus_android/flutter_blue_plus_android.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  test('adapter readiness waits for the real plugin lazy restart acknowledgement', () async {
    const channel = MethodChannel('flutter_blue_plus/methods');
    final messenger = TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger;
    final restarted = Completer<int>();
    final calls = <String>[];
    messenger.setMockMethodCallHandler(channel, (call) async {
      calls.add(call.method);
      if (call.method == 'flutterRestart') return restarted.future;
      if (call.method == 'isSupported') return true;
      throw StateError('Unexpected native call: ${call.method}');
    });
    addTearDown(() => messenger.setMockMethodCallHandler(channel, null));
    FlutterBluePlusAndroid.registerWith();
    var ready = false;
    final initialized = FlutterBluePlusAdapter().init().then((_) { ready = true; });
    await Future<void>.delayed(Duration.zero);
    expect(calls, ['flutterRestart']);
    expect(ready, isFalse);
    restarted.complete(0);
    await initialized;
    expect(calls, ['flutterRestart', 'isSupported']);
    expect(ready, isTrue);
  });
}
