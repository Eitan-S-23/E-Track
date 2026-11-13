import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:flutter/widgets.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:ble_monitor/ota/ota_device_info.dart';
import 'package:ble_monitor/services/version_inventory_service.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  late DateTime now;
  late List<Map<String, dynamic>> sent;
  late VersionInventoryService service;
  late StreamController<bool> activity;
  Completer<void>? gate;
  Map<String, dynamic>? acknowledgement;
  var allowed = true;
  var fail = false;
  var refresh = 'initial';
  var controls = 0;
  var reads = 0;
  var invalidIdentity = false;
  setUp(() {
    SharedPreferences.setMockInitialValues({});
    now = DateTime.utc(2026, 11, 11);
    sent = [];
    allowed = true; fail = false; refresh = 'initial'; controls = 0; reads = 0;
    activity = StreamController<bool>.broadcast(sync: true);
    gate = null;
    acknowledgement = null;
    invalidIdentity = false;
    service = VersionInventoryService(
      supported: true, endpoint: Uri.parse('https://example.test/api/public/version-inventory'),
      clock: () => now, canReport: () => allowed,
      runtimeActivity: [activity.stream],
      readAppIdentity: () async {
        reads++;
        return {'versionCode': 100, 'versionName': '1.0.74',
          'imageSha256': invalidIdentity ? '' : 'a' * 64};
      },
      sender: (uri, body, token, cancel) async {
        if (gate != null) await gate!.future;
        if (fail) throw StateError('offline');
        if (body == null) { controls++; return {'ok': true, 'refreshId': refresh}; }
        expect(token, matches(RegExp(r'^[0-9a-f]{64}$')));
        sent.add(jsonDecode(jsonEncode(body)) as Map<String, dynamic>);
        return acknowledgement ?? {'ok': true, 'accepted': true, 'refreshId': refresh};
      },
    );
  });
  tearDown(() async { service.onClose(); await activity.close(); });

  DeviceOtaInfo info([int version = 30321]) {
    final bytes = Uint8List(50);
    bytes.setRange(0, 8, DeviceOtaInfo.wireModelETrack);
    bytes[8] = 1; bytes[10] = 1; bytes[11] = 1;
    ByteData.sublistView(bytes).setUint32(12, version, Endian.little);
    bytes.fillRange(16, 48, 0xbb);
    bytes[48] = 1; bytes[49] = 24;
    return DeviceOtaInfo.fromInfoPayload(bytes);
  }
  Future<void> observe([int version = 30321]) async {
    service.observeDevice('AA:BB:CC:DD:EE:FF', info(version));
    // Drain the preference write, without advancing the five-second debounce timer.
    await Future<void>.delayed(Duration.zero);
  }

  test('coalesces daily reports and hashes the installed APK only once per process', () async {
    await service.poll();
    await service.poll();
    now = now.add(const Duration(hours: 2)); await service.poll();
    expect(sent, hasLength(1)); expect(controls, 0); expect(reads, 1);
    now = now.add(const Duration(days: 1)); await service.poll();
    expect(sent, hasLength(2)); expect(sent.last['sequence'], 2);
  });
  test('does no reporting or hashing while an upgrade owns the runtime', () async {
    allowed = false; await service.poll();
    expect(sent, isEmpty); expect(reads, 0);
    allowed = true; await service.poll(); expect(sent, hasLength(1));
  });
  test('opt out persists and prevents network traffic', () async {
    await service.setEnabled(false); await service.poll();
    expect(sent, isEmpty);
    expect((await SharedPreferences.getInstance()).getBool('version_inventory_v1_enabled'), false);
  });
  test('backs off an offline endpoint without throwing into App or OTA flow', () async {
    fail = true; await expectLater(service.poll(), completes);
    fail = false; await service.poll(); expect(sent, isEmpty);
    now = now.add(const Duration(hours: 2)); await service.poll(); expect(sent, hasLength(1));
  });
  test('responds once to a new refresh during a low-frequency control check', () async {
    await service.poll(); refresh = 'new-refresh';
    now = now.add(const Duration(hours: 4)); await service.poll();
    await service.poll();
    expect(controls, 1); expect(sent, hasLength(2));
  });
  test('stores no raw Bluetooth address and does not claim a globally unique device', () async {
    await service.initialize(); await observe(); await service.poll();
    final text = jsonEncode(sent.single);
    expect(text.toLowerCase(), isNot(contains('aa:bb:cc:dd:ee:ff')));
    final device = (sent.single['devices'] as List).single as Map;
    expect(device['identityScope'], 'installation');
    expect(device['deviceKey'], matches(RegExp(r'^[0-9a-f]{64}$')));
  });
  test('cached MCU age increases on a later daily report and its nonce stays unchanged', () async {
    await service.initialize(); await observe(); await service.poll();
    now = now.add(const Duration(days: 3)); await service.poll();
    final first = (sent.first['devices'] as List).single as Map;
    final last = (sent.last['devices'] as List).single as Map;
    expect(last['observationId'], first['observationId']);
    expect(last['ageSeconds'], 3 * 86400);
  });
  test('same-version reconnect is coalesced but a changed MCU version is reported', () async {
    await service.initialize(); await observe(); await service.poll();
    await observe(); await service.poll(); expect(sent, hasLength(1));
    await observe(30324); await service.poll(); expect(sent, hasLength(2));
  });
  test('expired MCU observations are excluded instead of presented as current', () async {
    await service.initialize(); await observe(); await service.poll();
    now = now.add(const Duration(days: 91)); await service.poll();
    expect(sent.last['devices'], isEmpty);
  });
  test('concurrent triggers share one in-flight operation', () async {
    await Future.wait([service.poll(), service.poll(), service.poll()]);
    expect(sent, hasLength(1));
  });
  test('background callbacks do not hash or report until foreground', () async {
    service.didChangeAppLifecycleState(AppLifecycleState.paused);
    await service.poll();
    expect(sent, isEmpty); expect(reads, 0);
    service.didChangeAppLifecycleState(AppLifecycleState.resumed);
    await service.poll(); expect(sent, hasLength(1));
  });

  testWidgets('automatically resumes a pending snapshot when the runtime becomes idle', (tester) async {
    allowed = false;
    service.onInit();
    await tester.pump();
    now = now.add(const Duration(seconds: 5));
    await tester.pump(const Duration(seconds: 5));
    expect(sent, isEmpty);
    expect(service.status.value, InventoryReportStatus.busy);
    allowed = true;
    activity.add(false);
    now = now.add(const Duration(seconds: 5));
    await tester.pump(const Duration(seconds: 5));
    expect(sent, hasLength(1));
    expect(service.status.value, InventoryReportStatus.reported);
  });

  testWidgets('retries at the backoff deadline without another tap or restart', (tester) async {
    fail = true;
    await service.poll();
    expect(service.status.value, InventoryReportStatus.retrying);
    fail = false;
    now = now.add(const Duration(hours: 1));
    await tester.pump(const Duration(hours: 1));
    expect(sent, hasLength(1));
    expect(service.failureCode.value, isNull);
  });

  testWidgets('retains a changed device that arrives during an in-flight report', (tester) async {
    await service.initialize();
    gate = Completer<void>();
    final pending = service.poll();
    await tester.pump();
    service.observeDevice('AA:BB:CC:DD:EE:FF', info(30324));
    await tester.pump();
    gate!.complete();
    await pending;
    gate = null;
    now = now.add(const Duration(seconds: 5));
    await tester.pump(const Duration(seconds: 5));
    expect(sent, hasLength(2));
    expect((sent.last['devices'] as List).single['versionCode'], 30324);
  });

  testWidgets('background interruption does not impose an hour of backoff', (tester) async {
    await service.initialize();
    gate = Completer<void>();
    final pending = service.poll();
    await tester.pump();
    service.didChangeAppLifecycleState(AppLifecycleState.paused);
    fail = true;
    gate!.complete();
    await pending;
    expect((await SharedPreferences.getInstance()).getString('version_inventory_v1_retry'), isNull);
    gate = null;
    fail = false;
    service.didChangeAppLifecycleState(AppLifecycleState.resumed);
    now = now.add(const Duration(seconds: 5));
    await tester.pump(const Duration(seconds: 5));
    expect(sent, hasLength(1));
  });

  testWidgets('opt-out cancels an already scheduled retry', (tester) async {
    fail = true;
    await service.poll();
    await service.setEnabled(false);
    fail = false;
    now = now.add(const Duration(hours: 2));
    await tester.pump(const Duration(hours: 2));
    expect(sent, isEmpty);
    expect(service.status.value, InventoryReportStatus.disabled);
  });

  testWidgets('a quick foreground return does not reinterpret cancelled work as failure', (tester) async {
    await service.initialize();
    gate = Completer<void>();
    final pending = service.poll();
    await tester.pump();
    service.didChangeAppLifecycleState(AppLifecycleState.paused);
    service.didChangeAppLifecycleState(AppLifecycleState.resumed);
    fail = true;
    gate!.complete();
    await pending;
    expect(service.failureCode.value, isNull);
    gate = null;
    fail = false;
    now = now.add(const Duration(seconds: 5));
    await tester.pump(const Duration(seconds: 5));
    expect(sent, hasLength(1));
  });

  testWidgets('a lagging duplicate receipt cannot create a zero-delay reporting loop', (tester) async {
    acknowledgement = {'ok': true, 'accepted': false, 'acknowledged': true,
      'refreshId': refresh, 'reportedAt': now.subtract(const Duration(days: 2)).millisecondsSinceEpoch ~/ 1000};
    await service.poll();
    now = now.add(const Duration(minutes: 1));
    await tester.pump(const Duration(minutes: 1));
    expect(sent, hasLength(1));
    expect(service.nextAttemptAt.value!.isAfter(now), isTrue);
  });

  test('a temporary missing APK identity is re-read after backoff', () async {
    invalidIdentity = true;
    await service.poll();
    expect(service.failureCode.value, 'APP_IDENTITY_UNAVAILABLE');
    invalidIdentity = false;
    now = now.add(const Duration(hours: 1));
    await service.poll();
    expect(reads, 2);
    expect(sent, hasLength(1));
  });

  test('does not turn an unacknowledged stale sequence into a successful report', () async {
    acknowledgement = {'ok': true, 'accepted': false, 'acknowledged': false, 'refreshId': refresh, 'sequence': 4};
    await service.poll();
    expect(service.lastReportedAt.value, isNull);
    expect(service.failureCode.value, 'REPORT_NOT_ACCEPTED');
    acknowledgement = null;
    now = now.add(const Duration(hours: 1));
    await service.poll();
    expect(sent.last['sequence'], 5);
  });

  test('a matching duplicate retains the server receipt time rather than making it fresh', () async {
    final receipt = now.subtract(const Duration(minutes: 5));
    acknowledgement = {'ok': true, 'accepted': false, 'acknowledged': true, 'refreshId': refresh,
      'reportedAt': receipt.millisecondsSinceEpoch ~/ 1000, 'sequence': 4};
    await service.poll();
    expect(service.lastReportedAt.value, receipt);
    expect((await SharedPreferences.getInstance()).getInt('version_inventory_v1_sequence'), 4);
    await service.poll();
    expect(sent, hasLength(1));
  });
}
