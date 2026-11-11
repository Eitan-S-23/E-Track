import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:ble_monitor/ota/ota_device_info.dart';
import 'package:ble_monitor/services/version_inventory_service.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  late DateTime now;
  late List<Map<String, dynamic>> sent;
  late VersionInventoryService service;
  var allowed = true;
  var fail = false;
  var refresh = 'initial';
  var controls = 0;
  var reads = 0;
  setUp(() {
    SharedPreferences.setMockInitialValues({});
    now = DateTime.utc(2026, 11, 11);
    sent = [];
    allowed = true; fail = false; refresh = 'initial'; controls = 0; reads = 0;
    service = VersionInventoryService(
      supported: true, endpoint: Uri.parse('https://example.test/api/public/version-inventory'),
      clock: () => now, canReport: () => allowed,
      readAppIdentity: () async {
        reads++;
        return {'versionCode': 100, 'versionName': '1.0.74', 'imageSha256': 'a' * 64};
      },
      sender: (uri, body, token, cancel) async {
        if (fail) throw StateError('offline');
        if (body == null) { controls++; return {'ok': true, 'refreshId': refresh}; }
        expect(token, matches(RegExp(r'^[0-9a-f]{64}$')));
        sent.add(jsonDecode(jsonEncode(body)) as Map<String, dynamic>);
        return {'ok': true, 'accepted': true, 'refreshId': refresh};
      },
    );
  });
  tearDown(() { service.onClose(); });

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
}
