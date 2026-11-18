import 'dart:async';
import 'dart:convert';
import 'dart:io' show Platform;

import 'package:ble_monitor/controllers/ble_controller.dart';
import 'package:ble_monitor/pages/device_detail_page.dart';
import 'package:ble_monitor/pages/speedometer_page.dart';
import 'package:ble_monitor/services/bluetooth_device_metadata.dart';
import 'package:ble_monitor/services/bluetooth_service.dart' as bt;
import 'package:ble_monitor/widgets/device_card.dart';
import 'package:flutter/material.dart';
import 'package:flutter_blue_plus/flutter_blue_plus.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:get/get.dart';
import 'package:shared_preferences/shared_preferences.dart';

const _address = 'AA:BB:CC:DD:EE:FF';
const _other = 'AA:BB:CC:DD:EE:01';
const _broadcastOnly = '\u6b64\u8bbe\u5907\u4e0d\u652f\u6301\u8fde\u63a5\uff0c\u4ec5\u5e7f\u64ad\u6570\u636e';

class _Device extends BluetoothDevice {
  _Device(super.remoteId, {this.label = ''}) : super.fromId();

  String label;
  bool nameUnavailable = false;
  bool linked = false;
  int connects = 0;
  final events = StreamController<BluetoothConnectionState>.broadcast();

  @override
  String get platformName {
    if (nameUnavailable) throw StateError('native name unavailable');
    return label;
  }
  @override
  bool get isConnected => linked;
  @override
  Stream<BluetoothConnectionState> get connectionState => events.stream;
  @override
  Future<void> connect({Duration timeout = const Duration(seconds: 35),
      int? mtu = 512, bool autoConnect = false}) async {
    connects++;
    linked = true;
  }
  @override
  Future<void> disconnect({int timeout = 35, bool queue = true, int androidDelay = 2000}) async {
    linked = false;
  }
}

class _Adapter implements bt.BluetoothAdapter {
  @override
  Future<void> init() async {}
  @override
  Future<BluetoothAdapterState> getAdapterState() async => BluetoothAdapterState.on;
  @override
  Stream<BluetoothAdapterState> get adapterStateChanged => const Stream.empty();
  @override
  Future<List<dynamic>> getConnectedDevices() async => [];
  @override
  bool get supportsCharacteristicValueStream => false;
  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

ScanResult _scan(_Device device, {String name = '', bool connectable = true}) => ScanResult(
  device: device,
  advertisementData: AdvertisementData(advName: name, txPowerLevel: null,
      appearance: 0, connectable: connectable, manufacturerData: {}, serviceData: {}, serviceUuids: []),
  rssi: -60,
  timeStamp: DateTime.now(),
);

Future<void> _settleDetail(WidgetTester tester) async {
  await tester.pump();
  // Delayed entry animations may not schedule a frame until their timer fires.
  await tester.pump(const Duration(seconds: 2));
  await tester.pumpAndSettle();
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  late List<_Device> devices;

  _Device device(String address, {String name = ''}) {
    final value = _Device(address, label: name);
    devices.add(value);
    return value;
  }

  bt.BluetoothService service({Future<List<BluetoothDevice>> Function()? reader}) =>
      Get.put(bt.BluetoothService(adapter: _Adapter(), systemDeviceReader: reader ?? () async => []));

  setUp(() {
    Get.testMode = true;
    SharedPreferences.setMockInitialValues({});
    devices = [];
  });

  tearDown(() async {
    Get.reset();
    for (final item in devices) {
      await item.events.close();
    }
  });

  test('known names and connection capability survive a fresh service without a scan', () async {
    final memory = BluetoothDeviceMetadata();
    memory.rememberConnection(_address, name: 'E-Track Original');
    await memory.settled;
    memory.close();

    final restored = service();
    await restored.deviceMetadata.restore();
    final handle = device(_address.toLowerCase());
    expect(restored.scanResults, isEmpty);
    expect(restored.getDeviceName(handle), 'E-Track Original');
    expect(restored.getDeviceConnectability(handle), isTrue);
    expect(restored.isDeviceConnected(handle), isFalse);
  });

  test('slow restoration cannot replace a new name or erase the old name on a nameless reconnect', () async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(BluetoothDeviceMetadata.storageKey,
        jsonEncode({_address.toLowerCase(): 'Old', _other.toLowerCase(): 'Retained'}));
    final gate = Completer<SharedPreferences>();
    final memory = BluetoothDeviceMetadata(preferences: () => gate.future);
    final loading = memory.restore();
    memory.rememberConnection(_address, name: 'New');
    memory.rememberConnection(_other);
    gate.complete(prefs);
    await loading;
    await memory.settled;
    expect(memory.nameOf(_address), 'New');
    expect(memory.nameOf(_other), 'Retained');
    memory.rememberConnection(_address, name: '   ');
    memory.rememberConnection(_address, name: 'Unknown Device');
    await memory.settled;
    expect(memory.nameOf(_address), 'New');
    memory.close();
  });

  test('persistent metadata is bounded and does not treat malformed data as a live connection', () async {
    SharedPreferences.setMockInitialValues({BluetoothDeviceMetadata.storageKey: 'not json'});
    final memory = BluetoothDeviceMetadata();
    await memory.restore();
    expect(memory.wasConnected(_address), isFalse);
    for (var i = 0; i < BluetoothDeviceMetadata.capacity + 3; i++) {
      memory.rememberConnection('device-$i', name: 'Device $i');
    }
    await memory.settled;
    final prefs = await SharedPreferences.getInstance();
    final stored = jsonDecode(prefs.getString(BluetoothDeviceMetadata.storageKey)!) as Map;
    expect(stored, hasLength(BluetoothDeviceMetadata.capacity));
    expect(memory.wasConnected('device-0'), isFalse);
    memory.close();
  });

  test('metadata storage failure does not discard the current display name', () async {
    final memory = BluetoothDeviceMetadata(preferences: () async => throw StateError('storage unavailable'));
    memory.rememberConnection(_address, name: 'E-Track Live');
    await memory.settled;
    expect(memory.nameOf(_address), 'E-Track Live');
    memory.close();
  });

  test('real connection overrides a false advertisement but missing data remains unknown', () async {
    final ble = service();
    final current = device(_address);
    final unknown = device(_other);
    expect(ble.getDeviceConnectability(unknown), isNull);
    ble.scanResults.assignAll([_scan(current, connectable: false)]);
    expect(ble.getDeviceConnectability(current), isFalse);
    ble.connectedDevices.add(current);
    expect(ble.getDeviceConnectability(current), isTrue);
    ble.connectedDevices.clear();
    expect(ble.getDeviceConnectability(current), isFalse);
    ble.scanResults.clear();
    expect(ble.getDeviceConnectability(current), isTrue);
    expect(ble.isDeviceConnected(current), isFalse);
    await ble.deviceMetadata.settled;
  });

  test('system name hydration matches the address and never adopts another app connection', () async {
    var queries = 0;
    final ble = service(reader: () async {
      queries++;
      return [device(_other, name: 'Another App'), device(_address, name: 'E-Track System')];
    });
    final current = device(_address.toLowerCase());
    ble.connectedDevices.add(current);
    await ble.refreshConnectedDeviceMetadata();
    await ble.deviceMetadata.settled;
    expect(queries, 1);
    expect(ble.getDeviceName(current), 'E-Track System');
    expect(ble.connectedDevices, [current]);
    expect(ble.deviceMetadata.wasConnected(_other), isFalse);
    expect(ble.scanResults, isEmpty);
  });

  test('only known devices retain later advertisement names', () async {
    final ble = service();
    final current = device(_address);
    final stranger = device(_other);
    ble.connectedDevices.add(current);
    ble.scanResults.assignAll([
      _scan(current, name: 'E-Track Renamed'),
      _scan(stranger, name: 'Nearby Device'),
    ]);
    await ble.deviceMetadata.settled;
    ble.scanResults.clear();
    expect(ble.getDeviceName(current), 'E-Track Renamed');
    expect(ble.deviceMetadata.wasConnected(_other), isFalse);
  });

  test('a connection arriving during a name query receives its own refresh', () async {
    final first = Completer<List<BluetoothDevice>>();
    var queries = 0;
    final ble = service(reader: () {
      queries++;
      return queries == 1 ? first.future : Future.value([device(_other, name: 'Second Device')]);
    });
    ble.connectedDevices.add(device(_address));
    final second = device(_other);
    ble.connectedDevices.add(second);
    final pending = ble.refreshConnectedDeviceMetadata();
    first.complete([device(_address, name: 'First Device')]);
    await pending;
    await ble.deviceMetadata.settled;
    expect(queries, 2);
    expect(ble.getDeviceName(second), 'Second Device');
  });

  test('closing the service rejects a late platform name result', () async {
    final gate = Completer<List<BluetoothDevice>>();
    final ble = service(reader: () => gate.future);
    final current = device(_address);
    ble.connectedDevices.add(current);
    final pending = ble.refreshConnectedDeviceMetadata();
    await Get.delete<bt.BluetoothService>(force: true);
    gate.complete([device(_address, name: 'Too Late')]);
    await pending;
    expect(ble.deviceMetadata.nameOf(_address), isNull);
  });

  test('companion connection completes while optional system metadata is still pending', () async {
    final gate = Completer<List<BluetoothDevice>>();
    final ble = service(reader: () => gate.future);
    final current = device(_address);
    ble.otaDeviceFactoryForTest = (_) => current;
    expect(await ble.connectCompanionDeviceByAddress(_address.toLowerCase()), isTrue);
    expect(current.connects, 1);
    expect(ble.getDeviceConnectability(current), isTrue);
    gate.completeError(StateError('name query unavailable'));
    await ble.refreshConnectedDeviceMetadata();
    expect(ble.isDeviceConnected(current), isTrue);
    await ble.deviceMetadata.settled;
  }, skip: Platform.isWindows);

  test('a failed native name read cannot turn a successful companion connection into failure', () async {
    final ble = service(reader: () async => throw StateError('system names unavailable'));
    final current = device(_address)..nameUnavailable = true;
    ble.deviceMetadata.rememberConnection(_address, name: 'E-Track Retained');
    await ble.deviceMetadata.settled;
    ble.otaDeviceFactoryForTest = (_) => current;
    expect(await ble.connectCompanionDeviceByAddress(_address), isTrue);
    await ble.refreshConnectedDeviceMetadata();
    expect(current.connects, 1);
    expect(ble.isDeviceConnected(current), isTrue);
    expect(ble.getDeviceConnectability(current), isTrue);
    expect(ble.getDeviceName(current), 'E-Track Retained');
    await ble.deviceMetadata.settled;
  }, skip: Platform.isWindows);

  for (final kind in ['device', 'speedometer']) {
    testWidgets('$kind details react to connection, late name, rename and true broadcast-only state', (tester) async {
      final gate = Completer<List<BluetoothDevice>>();
      final ble = service(reader: () => gate.future);
      await ble.initBluetooth();
      final current = device(_address);
      await tester.pumpWidget(GetMaterialApp(home: kind == 'device'
          ? DeviceDetailPage(device: current) : SpeedometerDeviceDetailPage(device: current)));
      await _settleDetail(tester);
      expect(find.text(_broadcastOnly), findsNothing);

      ble.connectedDevices.add(current);
      await tester.pump();
      expect(find.byType(ElevatedButton), findsOneWidget);
      expect(find.text(_broadcastOnly), findsNothing);
      gate.complete([device(_address, name: 'E-Track Restored')]);
      await ble.refreshConnectedDeviceMetadata();
      await ble.deviceMetadata.settled;
      await _settleDetail(tester);
      expect(find.text('E-Track Restored'), findsWidgets);

      ble.scanResults.assignAll([_scan(current, name: 'E-Track Renamed')]);
      await ble.deviceMetadata.settled;
      await _settleDetail(tester);
      expect(find.text('E-Track Renamed'), findsWidgets);
      ble.scanResults.clear();
      await _settleDetail(tester);
      expect(find.text('E-Track Renamed'), findsWidgets);

      ble.connectedDevices.clear();
      ble.scanResults.assignAll([_scan(current, name: 'E-Track Renamed', connectable: false)]);
      await _settleDetail(tester);
      expect(find.text(_broadcastOnly), findsOneWidget);
      expect(find.byType(ElevatedButton), findsNothing);
    });
  }

  testWidgets('device list card updates its name without replacing the device object', (tester) async {
    final ble = service();
    await ble.initBluetooth();
    final controller = Get.put(BleController());
    final current = device(_address);
    ble.connectedDevices.add(current);
    ble.deviceMetadata.rememberConnection(_address, name: 'Before');
    await ble.deviceMetadata.settled;
    await tester.pumpWidget(GetMaterialApp(home: Scaffold(body: DeviceCard(
        device: current, controller: controller, isConnected: true, onTap: () {}, onConnect: () {}))));
    await tester.pumpAndSettle();
    expect(find.text('Before'), findsOneWidget);
    ble.deviceMetadata.rememberConnection(_address, name: 'After');
    await ble.deviceMetadata.settled;
    await tester.pumpAndSettle();
    expect(find.text('Before'), findsNothing);
    expect(find.text('After'), findsOneWidget);
  });
}
