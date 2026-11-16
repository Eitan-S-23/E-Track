import 'dart:async';

import 'package:ble_monitor/companion/companion_platform.dart';
import 'package:ble_monitor/pages/companion_setup_page.dart';
import 'package:ble_monitor/utils/permission_helper.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:permission_handler/permission_handler.dart';

const _bluetooth = '\u6388\u4e88\u84dd\u7259\u6743\u9650';
const _bluetoothSettings = '\u6253\u5f00\u5e94\u7528\u6743\u9650\u8bbe\u7f6e';
const _bluetoothGranted = '\u5fc5\u8981\u84dd\u7259\u6743\u9650\u5df2\u6388\u4e88';
const _bluetoothDenied = '\u672a\u6388\u6743\u6216\u5df2\u64a4\u9500\uff0c\u53ef\u7ee7\u7eed\u4f7f\u7528\u65e0\u5173\u529f\u80fd';
const _permanent = '\u5df2\u6c38\u4e45\u62d2\u7edd\uff0c\u8bf7\u524d\u5f80\u7cfb\u7edf\u8bbe\u7f6e';
const _notification = '\u6388\u4e88\u901a\u77e5\u6743\u9650';
const _notificationSettings = '\u6253\u5f00\u901a\u77e5\u8bbe\u7f6e';
const _notificationDenied = '\u901a\u77e5\u672a\u6388\u6743';
const _enable = '\u540e\u53f0\u8fde\u63a5\u4e0e\u56fa\u4ef6\u68c0\u67e5';
const _skip = '\u8fd4\u56de / \u6682\u65f6\u8df3\u8fc7';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  const companion = MethodChannel('test/companion-setup');
  const permissions = MethodChannel('flutter.baseflow.com/permissions/methods');
  final messenger = TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger;
  late Map<String, Object?> snapshot;
  late Map<int, PermissionStatus> grants;
  late Map<int, PermissionStatus> requestResults;
  late List<List<int>> requests;
  late List<MethodCall> calls;
  Completer<Map<String, Object?>>? nextSnapshot;
  bool settingsAvailable = true;
  var reads = 0;

  setUp(() {
    snapshot = {'sdk': 34, 'enabled': false, 'associated': false,
      'serviceRunning': false, 'intervalHours': 12, 'wifiOnly': true,
      'batteryUnrestricted': false, 'vendorAutostart': 'unknown'};
    grants = {};
    requestResults = {};
    requests = [];
    calls = [];
    nextSnapshot = null;
    settingsAvailable = true;
    reads = 0;
    messenger.setMockMethodCallHandler(permissions, (call) async {
      if (call.method == 'checkPermissionStatus') {
        return (grants[call.arguments as int] ?? PermissionStatus.denied).index;
      }
      if (call.method == 'requestPermissions') {
        final values = List<int>.from(call.arguments as List);
        requests.add(values);
        for (final value in values) {
          grants[value] = requestResults[value] ?? PermissionStatus.denied;
        }
        return {for (final value in values) value: grants[value]!.index};
      }
      fail('Unexpected permission operation: ${call.method}');
    });
    messenger.setMockMethodCallHandler(companion, (call) async {
      calls.add(call);
      switch (call.method) {
        case 'snapshot':
          reads++;
          final pending = nextSnapshot;
          nextSnapshot = null;
          return pending == null ? Map<String, Object?>.from(snapshot) : await pending.future;
        case 'settings':
          return settingsAvailable;
        case 'configure':
          final arguments = Map<String, Object?>.from(call.arguments as Map);
          if (arguments['enabled'] == true && snapshot['problem'] != null) {
            throw PlatformException(code: 'COMPANION_UNAVAILABLE', message: '${snapshot['problem']}');
          }
          snapshot.addAll(arguments);
          return Map<String, Object?>.from(snapshot);
        default:
          fail('Unexpected companion operation: ${call.method}');
      }
    });
  });

  tearDown(() {
    messenger.setMockMethodCallHandler(companion, null);
    messenger.setMockMethodCallHandler(permissions, null);
  });

  Future<void> settle(WidgetTester tester) async {
    // The production atmosphere repeats forever. Advance a bounded route/action
    // window and assert the resulting state instead of waiting for zero frames.
    for (var frame = 0; frame < 30; frame++) {
      await tester.pump(const Duration(milliseconds: 20));
    }
  }

  Future<void> open(WidgetTester tester, {int sdk = 34, bool supported = true}) async {
    tester.view.physicalSize = const Size(1200, 3200);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    await tester.pumpWidget(MaterialApp(home: Builder(builder: (context) => Scaffold(
      body: TextButton(onPressed: () => Navigator.of(context).push(MaterialPageRoute<void>(
        builder: (_) => CompanionSetupPage(
          platform: CompanionPlatform(channel: companion, supported: supported),
          requiredBluetoothPermissions: () async => PermissionHelper.bluetoothPermissionsFor(sdk),
        ))), child: const Text('Open setup')),
    ))));
    await tester.tap(find.text('Open setup'));
    await settle(tester);
  }

  Future<void> tap(WidgetTester tester, String text) async {
    final button = find.text(text);
    await tester.ensureVisible(button);
    await tester.tap(button);
    await settle(tester);
  }

  Future<void> resume(WidgetTester tester) async {
    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.paused);
    await tester.pump();
    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
    await settle(tester);
  }

  void grantBluetooth() {
    for (final permission in PermissionHelper.bluetoothPermissionsFor(34)) {
      grants[permission.value] = PermissionStatus.granted;
    }
  }

  testWidgets('T01 setup and defer never prompt, associate or enable automatically', (tester) async {
    await open(tester);
    expect(find.text(_bluetoothDenied), findsOneWidget);
    expect(requests, isEmpty);
    expect(calls.map((c) => c.method), everyElement('snapshot'));
    await tap(tester, _skip);
    expect(find.byType(CompanionSetupPage), findsNothing);
    expect(find.text('Open setup'), findsOneWidget);
    await tester.tap(find.text('Open setup'));
    await settle(tester);
    expect(reads, 2);
    expect(requests, isEmpty);
    expect(snapshot['enabled'], isFalse);
  });

  for (final sdk in [30, 34]) {
    testWidgets('T01 SDK $sdk denial requests only the applicable Bluetooth permissions', (tester) async {
      await open(tester, sdk: sdk);
      await tap(tester, _bluetooth);
      expect(requests, [PermissionHelper.bluetoothPermissionsFor(sdk).map((p) => p.value).toList()]);
      expect(requests.single, isNot(contains(Permission.locationAlways.value)));
      expect(requests.single, isNot(contains(Permission.notification.value)));
      expect(find.text(_bluetoothDenied), findsOneWidget);
      await resume(tester);
      expect(requests, hasLength(1), reason: 'Resume must read, not repeat a denied prompt');
      await tap(tester, _skip);
      expect(find.text('Open setup'), findsOneWidget);
    });
  }

  testWidgets('T01 permanent denial goes to settings and waits for an actual grant', (tester) async {
    requestResults = {for (final permission in PermissionHelper.bluetoothPermissionsFor(34))
      permission.value: PermissionStatus.permanentlyDenied};
    await open(tester);
    await tap(tester, _bluetooth);
    expect(find.text(_permanent), findsOneWidget);
    await tap(tester, _bluetoothSettings);
    expect((calls.lastWhere((c) => c.method == 'settings').arguments as Map)['kind'], 'permissions');
    expect(find.text(_permanent), findsOneWidget);
    await resume(tester);
    expect(find.text(_permanent), findsOneWidget);
    expect(requests, hasLength(1));
    grantBluetooth();
    await resume(tester);
    expect(find.text(_bluetoothGranted), findsOneWidget);
    expect(find.text(_permanent), findsNothing);
    expect(snapshot['enabled'], isFalse, reason: 'Grant does not imply background opt-in');
  });

  testWidgets('T01 revoked permissions are re-read on settings return without prompting', (tester) async {
    grantBluetooth();
    grants[Permission.notification.value] = PermissionStatus.granted;
    snapshot.addAll({'enabled': true, 'associated': true, 'serviceRunning': true});
    await open(tester);
    expect(find.text(_bluetoothGranted), findsOneWidget);
    await tap(tester, _notificationSettings);
    grants.clear();
    snapshot.addAll({'serviceRunning': false, 'problem': 'BLUETOOTH_PERMISSION_DENIED'});
    await resume(tester);
    expect(find.text(_bluetoothGranted), findsNothing);
    expect(find.text(_bluetoothDenied), findsOneWidget);
    expect(find.text(_notificationDenied), findsOneWidget);
    expect(find.textContaining('BLUETOOTH_PERMISSION_DENIED'), findsOneWidget);
    expect(requests, isEmpty);
    expect(calls.where((c) => c.method == 'configure'), isEmpty);
  });

  testWidgets('T01 notification denial and permanent denial remain usable and explicit', (tester) async {
    await open(tester);
    await tap(tester, _notification);
    expect(requests, [[Permission.notification.value]]);
    expect(find.text(_notificationDenied), findsOneWidget);
    requestResults[Permission.notification.value] = PermissionStatus.permanentlyDenied;
    await tap(tester, _notification);
    await tap(tester, _notificationSettings);
    await resume(tester);
    expect(requests, hasLength(2));
    expect(find.text(_notificationDenied), findsOneWidget);
    expect(snapshot['enabled'], isFalse);
    await tap(tester, _skip);
    expect(find.text('Open setup'), findsOneWidget);
  });

  testWidgets('T01 disabled channel refuses enable despite notification permission', (tester) async {
    grantBluetooth();
    grants[Permission.notification.value] = PermissionStatus.granted;
    snapshot.addAll({'associated': true, 'problem': 'COMPANION_CHANNEL_DISABLED'});
    await open(tester);
    await tap(tester, _notificationSettings);
    await resume(tester);
    expect(find.textContaining('COMPANION_CHANNEL_DISABLED'), findsOneWidget);
    await tap(tester, _enable);
    expect(snapshot['enabled'], isFalse);
    expect(tester.widget<SwitchListTile>(find.widgetWithText(SwitchListTile, _enable)).value, isFalse);
    expect(find.textContaining('COMPANION_UNAVAILABLE'), findsOneWidget);
    snapshot['problem'] = null;
    await resume(tester);
    await tap(tester, _enable);
    expect(snapshot['enabled'], isTrue);
    expect(calls.where((c) => c.method == 'configure'), hasLength(2));
    expect(requests, isEmpty);
  });

  testWidgets('T01 OEM settings failure and success never assert unknown autostart grants', (tester) async {
    settingsAvailable = false;
    await open(tester);
    await tap(tester, '\u5382\u5546\u81ea\u542f\u52a8\u8bbe\u7f6e');
    expect(find.textContaining('\u6ca1\u6709\u53ef\u7528\u7684\u4e13\u7528\u5165\u53e3'), findsOneWidget);
    settingsAvailable = true;
    await tap(tester, '\u5382\u5546\u81ea\u542f\u52a8\u8bbe\u7f6e');
    await resume(tester);
    expect(find.text('\u5382\u5546\u81ea\u542f\u52a8\uff1a\u5f85\u4eba\u5de5\u6838\u5bf9 / \u5f85\u771f\u673a\u9a8c\u8bc1'), findsOneWidget);
    expect(snapshot['batteryUnrestricted'], isFalse);
    expect(snapshot['enabled'], isFalse);
    expect(requests, isEmpty);
  });

  testWidgets('T01 a delayed pre-settings refresh cannot overwrite resumed state', (tester) async {
    await open(tester);
    final delayed = Completer<Map<String, Object?>>();
    nextSnapshot = delayed;
    await tester.tap(find.byIcon(Icons.refresh));
    await tester.pump();
    snapshot['problem'] = 'CURRENT_PERMISSION_REVOKED';
    await resume(tester);
    delayed.complete({...snapshot, 'problem': 'STALE_PERMISSION_STATE'});
    await settle(tester);
    expect(find.textContaining('CURRENT_PERMISSION_REVOKED'), findsOneWidget);
    expect(find.textContaining('STALE_PERMISSION_STATE'), findsNothing);
    expect(requests, isEmpty);
  });

  testWidgets('T01 leaving during a settings refresh discards the late completion', (tester) async {
    await open(tester);
    final delayed = Completer<Map<String, Object?>>();
    nextSnapshot = delayed;
    await tester.tap(find.byIcon(Icons.refresh));
    await tester.pump();
    await tap(tester, _skip);
    delayed.complete({...snapshot, 'enabled': true});
    await settle(tester);
    expect(find.byType(CompanionSetupPage), findsNothing);
    expect(tester.takeException(), isNull);
    expect(requests, isEmpty);
  });

  testWidgets('T01 unsupported platforms keep a defer path and make no Android calls', (tester) async {
    await open(tester, supported: false);
    expect(calls, isEmpty);
    expect(requests, isEmpty);
    expect(find.text(_enable), findsNothing);
    await tap(tester, _skip);
    expect(find.text('Open setup'), findsOneWidget);
  });
}
