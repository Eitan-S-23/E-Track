import 'dart:async';
import 'dart:io';

import 'package:ble_monitor/companion/companion_platform.dart';
import 'package:ble_monitor/companion/companion_protocol.dart';
import 'package:ble_monitor/companion/companion_runtime.dart';
import 'package:ble_monitor/controllers/ble_controller.dart';
import 'package:ble_monitor/controllers/monitor_controller.dart';
import 'package:ble_monitor/models/device_data.dart';
import 'package:ble_monitor/ota/ota_ble_codec.dart';
import 'package:ble_monitor/ota/ota_device_info.dart';
import 'package:ble_monitor/services/bluetooth_service.dart';
import 'package:ble_monitor/services/database_service.dart';
import 'package:ble_monitor/services/ota_service.dart';
import 'package:ble_monitor/services/scan_settings_service.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_blue_plus/flutter_blue_plus.dart' as fbp;
import 'package:flutter_test/flutter_test.dart';
import 'package:get/get.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:sqflite/sqflite.dart';

const _address = 'aa:bb:cc:dd:ee:ff';
const _sensor = 'AA:BB:00:00:00:01';
const _secondSensor = 'AA:BB:00:00:00:02';

void main() {
  // These are Android/mobile adapter scenarios. Windows has a different adapter
  // and is explicitly skipped, not passed by replacing the production scan path.
  void scenario(String name, Future<void> Function(_Harness) body, {bool history = false}) {
    testWidgets('T02 $name', (tester) async {
      Get.testMode = true;
      SharedPreferences.setMockInitialValues({
        'companion_attempt_$_address': DateTime.now().millisecondsSinceEpoch,
      });
      final harness = _Harness(tester, history: history);
      try {
        await harness.initialize();
        await body(harness);
      } catch (error, stack) {
        debugPrint('T02_PRIMARY_FAILURE $name: $error\n$stack');
        rethrow;
      } finally {
        await harness.close();
      }
    }, skip: Platform.isWindows);
  }

  scenario('headless real runtime collects and saves without mounting a page', (h) async {
    expect(h.monitor.savedDevices.first.dataHistory, hasLength(300));
    expect(h.store.historyLimits, everyElement(300));
    await h.wake();
    await h.until(() => h.adapter.starts == 1 && h.ble.isScanning.value);
    expect(h.device.infoRequests, 1, reason: 'The real OtaService verifies the MCU before idle collection');
    expect(h.ota.hasCurrentDeviceIdentity(_address), isTrue);
    expect(h.ble.foregroundScanningAllowed, isFalse);
    expect(find.byType(Scaffold), findsNothing);
    expect(h.uiRequests, 0);
    h.emit([_advertisement(_sensor)]);
    await h.until(() => h.monitor.realtimeData.containsKey(_sensor));
    final sample = h.monitor.realtimeData[_sensor]!;
    expect(sample.current, 100);
    expect(sample.currentUnit, 'mA');
    expect(sample.voltage, 24000);
    expect(sample.power, closeTo(2400, 0.001));
    expect(h.monitor.savedDevices.first.dataHistory, hasLength(300));
    await h.elapse(const Duration(seconds: 10));
    expect(h.store.saved, [sample.toMap()]);
    expect(h.monitor.persistenceError.value, isNull);
    expect(h.adapter.stops, greaterThan(0));
    expect(h.ble.companionScanningAllowed, isFalse);
    expect(h.adapter.results.hasListener, isFalse);
    await h.elapse(const Duration(seconds: 49));
    expect(h.adapter.starts, 1, reason: 'UI monitoring timers cannot bypass the background lease');
    await h.elapse(const Duration(seconds: 1));
    expect(h.adapter.starts, 2);
    expect(h.uiRequests, 0);
  }, history: true);

  scenario('background monitoring timers cannot scan before native wake', (h) async {
    await Get.find<BleController>().startScan(requestPermission: false);
    await h.elapse(const Duration(seconds: 65));
    expect(h.adapter.starts, 0);
    expect(h.ble.companionScanningAllowed, isFalse);
    expect(h.store.saved, isEmpty);
    await h.wake();
    await h.until(() => h.adapter.starts == 1);
  });

  for (final denied in <String, Object?>{
    'runtimeId': 'retired-runtime',
    'revision': 'retired-revision',
    'serviceRunning': false,
    'sensorBackgroundSupported': false,
    'problem': 'BLUETOOTH_SCAN_PERMISSION_DENIED',
  }.entries) {
    scenario('native ${denied.key} rejection suppresses telemetry until recovery', (h) async {
      final original = h.snapshot[denied.key];
      h.snapshot[denied.key] = denied.value;
      await h.wake();
      await h.elapse(const Duration(seconds: 61));
      expect(h.adapter.starts, 0);
      expect(h.store.saved, isEmpty);
      h.snapshot[denied.key] = original;
      await h.elapse(const Duration(seconds: 59));
      expect(h.adapter.starts, 1);
      expect(h.device.infoRequests, 1, reason: 'Telemetry recovery does not create another OTA owner');
    });
  }

  scenario('permission denial suppresses scanning and later grant recovers without UI', (h) async {
    h.permissionGranted = false;
    await h.wake();
    await h.elapse(const Duration(seconds: 61));
    expect(h.permissionReads, greaterThan(0));
    expect(h.adapter.starts, 0);
    h.permissionGranted = true;
    await h.elapse(const Duration(seconds: 59));
    expect(h.adapter.starts, 1);
    expect(h.uiRequests, 0);
  });

  scenario('owner loss during permission read fences a late successful answer', (h) async {
    final delayed = Completer<bool>();
    h.permissionGate = delayed;
    await h.wake();
    await h.until(() => h.permissionReads == 1);
    await h.callback('lost', {'runtimeId': 'runtime-1'});
    expect(h.runtime.handles(_address), isFalse);
    delayed.complete(true);
    await h.pump();
    await h.elapse(const Duration(minutes: 2));
    expect(h.adapter.starts, 0);
    expect(h.ble.companionScanningAllowed, isFalse);
    expect(h.device.isConnected, isFalse);
    await h.wake(id: 'runtime-2');
    await h.until(() => h.adapter.starts == 1);
    expect(h.device.infoRequests, 2);
  });

  scenario('late platform scan start cannot outlive a revoked lease', (h) async {
    final delayed = Completer<void>();
    h.adapter.startGate = delayed;
    await h.wake();
    await h.until(() => h.adapter.starts == 1);
    await h.callback('lost', {'runtimeId': 'runtime-1'});
    delayed.complete();
    await h.pump();
    h.emit([_advertisement(_sensor)]);
    await h.pump();
    expect(h.ble.isScanning.value, isFalse);
    expect(h.ble.companionScanningAllowed, isFalse);
    expect(h.adapter.results.hasListener, isFalse);
    expect(h.monitor.realtimeData, isEmpty);
    expect(h.store.saved, isEmpty);
  });

  scenario('stale unmonitored duplicate and out-of-window advertisements are not new samples', (h) async {
    await h.wake();
    await h.until(() => h.adapter.results.hasListener);
    h.emit([_advertisement(_sensor, stale: true), _advertisement('AA:BB:00:00:00:99')]);
    await h.pump();
    expect(h.monitor.realtimeData, isEmpty);
    h.emit([_advertisement(_sensor), _advertisement(_sensor)]);
    await h.pump();
    expect(h.monitor.savedDevices.first.dataHistory, hasLength(1));
    await h.elapse(const Duration(seconds: 8));
    expect(h.adapter.results.hasListener, isFalse);
    h.emit([_advertisement(_secondSensor)]);
    await h.elapse(const Duration(seconds: 2));
    expect(h.store.saved, hasLength(1));
    expect(h.store.saved.single['deviceId'], _sensor);
    expect(h.monitor.realtimeData.containsKey(_secondSensor), isFalse);
  });

  scenario('database failure retains the exact pending samples for a successful retry', (h) async {
    h.store.failDevice = _sensor;
    await h.wake();
    await h.until(() => h.adapter.results.hasListener);
    h.emit([_advertisement(_sensor)]);
    await h.pump();
    final sample = h.monitor.realtimeData[_sensor]!.toMap();
    await h.elapse(const Duration(seconds: 10));
    expect(h.monitor.persistenceError.value, 'DATA_SAVE_FAILED');
    expect(h.store.saved, isEmpty);
    expect(h.store.attempts, [[sample]]);
    h.store.failDevice = null;
    await h.elapse(const Duration(seconds: 10));
    expect(h.store.attempts, [[sample], [sample]]);
    expect(h.store.saved, [sample]);
    expect(h.monitor.persistenceError.value, isNull);
    await h.elapse(const Duration(seconds: 10));
    expect(h.store.attempts, hasLength(2), reason: 'A committed sample is not submitted again');
  });

  scenario('partial device-batch failure retries only the uncommitted device', (h) async {
    h.store.failDevice = _secondSensor;
    await h.wake();
    await h.until(() => h.adapter.results.hasListener);
    h.emit([_advertisement(_sensor), _advertisement(_secondSensor)]);
    await h.pump();
    await h.elapse(const Duration(seconds: 10));
    expect(h.monitor.persistenceError.value, 'DATA_SAVE_FAILED');
    expect(h.store.saved.map((s) => s['deviceId']), [_sensor]);
    h.store.failDevice = null;
    await h.elapse(const Duration(seconds: 10));
    expect(h.store.attempts.map((batch) => batch.single['deviceId']), [_sensor, _secondSensor, _secondSensor]);
    expect(h.store.saved.map((s) => s['deviceId']), [_sensor, _secondSensor]);
    expect(h.monitor.persistenceError.value, isNull);
  });

  scenario('in-flight database save is single-flight and retains later arrivals', (h) async {
    final delayed = Completer<void>();
    h.store.commitGate = delayed;
    await h.wake();
    await h.until(() => h.adapter.results.hasListener);
    h.emit([_advertisement(_sensor)]);
    await h.pump();
    await h.elapse(const Duration(seconds: 10));
    expect(h.store.attempts, hasLength(1));
    await h.elapse(const Duration(seconds: 50));
    expect(h.adapter.results.hasListener, isTrue);
    h.emit([_advertisement(_secondSensor)]);
    await h.pump();
    await h.elapse(const Duration(seconds: 10));
    expect(h.store.attempts, hasLength(1));
    delayed.complete();
    await h.pump();
    await h.elapse(const Duration(seconds: 10));
    expect(h.store.saved.map((s) => s['deviceId']), [_sensor, _secondSensor]);
    expect(h.store.maxTransactions, 1);
    expect(h.store.attempts, hasLength(2));
  });

  scenario('returning to the UI loads history once without a second collector', (h) async {
    await h.wake();
    await h.until(() => h.adapter.starts == 1);
    final before = h.store.deviceReads;
    final first = h.monitor.attachHistoryForUi();
    final second = h.monitor.attachHistoryForUi();
    await h.pump();
    await Future.wait([first, second]);
    expect(h.store.deviceReads, before + 1);
    expect(h.store.historyLimits.where((limit) => limit == null), hasLength(2));
    await h.callback('attachUi', null);
    expect(h.uiRequests, 1);
    expect(h.device.infoRequests, 1);
    expect(h.adapter.starts, 1);
    expect(identical(Get.find<MonitorController>(), h.monitor), isTrue);
    expect(identical(Get.find<BluetoothService>(), h.ble), isTrue);
  }, history: true);
}

class _Harness {
  _Harness(this.tester, {required bool history}) : store = _Database(history: history) {
    ble = _AndroidBluetooth(adapter, () => elapsedMs);
    ble.otaDeviceFactoryForTest = (_) => device;
    ota = OtaService(bluetoothService: ble,
      firmwareDirProvider: () async => throw StateError('No package IO in telemetry'),
      latestUriBuilder: (info, appVersion, channel) => throw StateError('Recent recovery must not query HTTP'));
    monitor = _AndroidMonitor(DatabaseService.forDatabase(store));
    runtime = CompanionRuntime(platform: CompanionPlatform(channel: channel, supported: true),
      bluetooth: ble, ota: ota, onShowUi: () { uiRequests++; }, checkBluetoothPermissions: () async {
        permissionReads++;
        final pending = permissionGate;
        permissionGate = null;
        return pending == null ? permissionGranted : await pending.future;
      });
  }

  final WidgetTester tester;
  final _Database store;
  final adapter = _Adapter();
  final device = _Device();
  late final _AndroidBluetooth ble;
  late final OtaService ota;
  late final _AndroidMonitor monitor;
  late final CompanionRuntime runtime;
  final channel = const MethodChannel('test/companion-telemetry');
  final messenger = TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger;
  final snapshot = <String, Object?>{'runtimeId': 'runtime-1', 'revision': 'revision-1',
    'serviceRunning': true, 'sensorBackgroundSupported': true, 'problem': null,
    'intervalHours': 12, 'wifiOnly': true};
  int elapsedMs = 0, permissionReads = 0, uiRequests = 0;
  bool permissionGranted = true, ready = false;
  Completer<bool>? permissionGate;

  Future<void> initialize() async {
    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.paused);
    messenger.setMockMethodCallHandler(channel, (call) async {
      if (call.method == 'ready') { ready = true; return snapshot; }
      if (call.method == 'snapshot') {
        debugPrint('T02_NATIVE_SNAPSHOT $snapshot');
        return Map<String, Object?>.from(snapshot);
      }
      if (call.method == 'state') {
        debugPrint('T02_NATIVE_STATE ${call.arguments}');
        return true;
      }
      fail('Unexpected native call: ${call.method}');
    });
    Get.put<ScanSettingsService>(ScanSettingsService());
    Get.put<BluetoothService>(ble);
    Get.put<BleController>(BleController());
    Get.put<MonitorController>(monitor);
    Get.put<OtaService>(ota);
    Get.put<CompanionRuntime>(runtime);
    await until(() => ready && monitor.isMonitoring.value);
  }

  Future<void> pump() async {
    for (var i = 0; i < 30; i++) { await tick(); }
  }

  Future<void> tick([Duration duration = Duration.zero]) async {
    elapsedMs += duration.inMilliseconds;
    await tester.pump(duration);
    // Dart's completed stream-cancellation future schedules in the root zone.
    // Yield only that microtask queue; project code/timers stay in FakeAsync.
    await tester.runAsync(() async {});
  }

  Future<void> until(bool Function() condition) async {
    for (var i = 0; i < 2000 && !condition(); i++) {
      await tick(const Duration(milliseconds: 1));
    }
    expect(condition(), isTrue, reason: 'runtime=${runtime.status.value}, OTA=${ota.upgradeStatus}, '
        'busy=${ota.isUpgrading}, owner=${runtime.handles(_address)}, '
        'discovery=${device.discoveries}, writes=${device.writes}, scans=${adapter.starts}, '
        'pendingNative=${messenger.pendingMessageCount}, elapsedMs=$elapsedMs');
    await pump();
  }

  Future<void> elapse(Duration duration) async {
    await tick(duration);
    await pump();
  }

  Future<Object?> callback(String method, Object? value) async {
    debugPrint('T02_NATIVE_EVENT $method');
    final completed = Completer<Object?>();
    const codec = StandardMethodCodec();
    messenger.handlePlatformMessage(channel.name, codec.encodeMethodCall(MethodCall(method, value)), (result) {
      debugPrint('T02_NATIVE_REPLY $method');
      completed.complete(result == null ? null : codec.decodeEnvelope(result));
    });
    await until(() => completed.isCompleted);
    return completed.future;
  }

  Future<void> wake({String id = 'runtime-1'}) async {
    if (id != 'runtime-1') snapshot['runtimeId'] = id;
    expect(await callback('wake', {'runtimeId': id, 'revision': 'revision-1',
      'address': _address, 'reason': 'recovery'}), isTrue);
    await until(() => runtime.status.value == 'CONNECTED' && !ota.isUpgrading);
  }

  void emit(List<fbp.ScanResult> results) { adapter.results.add(results); }

  Future<void> close() async {
    final scanGate = adapter.startGate;
    if (scanGate != null && !scanGate.isCompleted) scanGate.complete();
    final saveGate = store.commitGate;
    if (saveGate != null && !saveGate.isCompleted) saveGate.complete();
    final checkGate = permissionGate;
    if (checkGate != null && !checkGate.isCompleted) checkGate.complete(false);
    try {
      if (ready) await callback('lost', {'runtimeId': snapshot['runtimeId']});
    } finally {
      runtime.onClose();
      monitor.onClose();
      if (Get.isRegistered<BleController>()) Get.find<BleController>().onClose();
      ota.onClose();
      ble.onClose();
      Get.reset();
      messenger.setMockMethodCallHandler(channel, null);
      tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
      await pump();
      await adapter.results.close();
      await device.close();
      await tester.pumpWidget(const SizedBox.shrink());
    }
  }
}

class _AndroidBluetooth extends BluetoothService {
  _AndroidBluetooth(BluetoothAdapter adapter, int Function() clock)
      : super(adapter: adapter, companionClockMs: clock);
  @override
  bool get usesAndroidLifecycle => true;
}

class _AndroidMonitor extends MonitorController {
  _AndroidMonitor(DatabaseService database) : super(loadHistory: false, database: database);
  @override
  bool get usesAndroidLifecycle => true;
}

class _Adapter extends Fake implements BluetoothAdapter {
  final results = StreamController<List<dynamic>>.broadcast(sync: true);
  int starts = 0, stops = 0;
  Completer<void>? startGate;
  @override
  Future<void> init() async {}
  @override
  Future<List<dynamic>> getConnectedDevices() async => [];
  @override
  Future<fbp.BluetoothAdapterState> getAdapterState() async => fbp.BluetoothAdapterState.on;
  @override
  Stream<fbp.BluetoothAdapterState> get adapterStateChanged => const Stream.empty();
  @override
  Stream<List<dynamic>> get scanResults => results.stream;
  @override
  Future<void> startScan({Duration? timeout}) async { starts++; await startGate?.future; }
  @override
  Future<void> stopScan() async { stops++; }
  @override
  bool get supportsCharacteristicValueStream => false;
}

class _Device extends Fake implements fbp.BluetoothDevice {
  @override
  final remoteId = const fbp.DeviceIdentifier('AA:BB:CC:DD:EE:FF');
  @override
  final platformName = 'E-Track';
  @override
  bool isConnected = false;
  int infoRequests = 0, discoveries = 0, writes = 0;
  final connections = StreamController<fbp.BluetoothConnectionState>.broadcast(sync: true);
  final resets = StreamController<void>.broadcast(sync: true);
  final notifications = StreamController<List<int>>.broadcast(sync: true);
  final text = CompanionDecoder();
  late final writer = _Characteristic(this, notify: false);
  late final notifier = _Characteristic(this, notify: true);
  @override
  Stream<fbp.BluetoothConnectionState> get connectionState => connections.stream;
  @override
  Stream<void> get onServicesReset => resets.stream;
  @override
  Future<void> connect({Duration timeout = const Duration(seconds: 35), int? mtu = 512,
      bool autoConnect = false}) async {
    debugPrint('T02_GATT_CONNECT');
    isConnected = true;
    connections.add(fbp.BluetoothConnectionState.connected);
  }
  @override
  Future<void> disconnect({int timeout = 35, bool queue = true, int androidDelay = 2000}) async {
    debugPrint('T02_GATT_DISCONNECT');
    isConnected = false;
    connections.add(fbp.BluetoothConnectionState.disconnected);
  }
  @override
  Future<int> requestMtu(int desiredMtu, {double predelay = 0.35, int timeout = 15}) async {
    debugPrint('T02_GATT_MTU');
    return 247;
  }
  @override
  Future<List<fbp.BluetoothService>> discoverServices({bool subscribeToServicesChanged = true,
      int timeout = 15}) async {
    discoveries++;
    debugPrint('T02_GATT_DISCOVER $discoveries');
    return [_Gatt([writer, notifier])];
  }

  void write(List<int> bytes) {
    writes++;
    if (bytes.first == OtaBleCodec.frameSync0) {
      final frame = OtaBleCodec.decodeFrame(bytes);
      debugPrint('T02_GATT_COMMAND ${frame.cmd}');
      expectSync(frame.cmd, OtaBleCodec.cmdGetInfo, reason: 'No firmware transfer is authorized by telemetry');
      infoRequests++;
      notifications.add(OtaBleCodec.encodeCommand(cmd: OtaBleCodec.rspInfo, session: frame.session,
        seq: frame.seq, payload: buildInfoPayload(model: DeviceOtaInfo.wireModelETrack,
          hardwareRevision: 3, layoutId: 5, bootVersion: 2, currentVersionCode: 30327,
          imageSha256: List<int>.filled(32, 0x11))));
    } else {
      debugPrint('T02_GATT_TEXT ${String.fromCharCodes(bytes).trim()}');
      for (final message in text.add(bytes, idleTextAllowed: true)) {
        if (message.kind == 'HELLO') {
          notifications.add(CompanionMessage('CAPS', message.session, 0, ['1']).encode());
          debugPrint('T02_GATT_CAPS_SENT');
        }
      }
    }
  }
  Future<void> close() async { await connections.close(); await resets.close(); await notifications.close(); }
}

class _Characteristic extends Fake implements fbp.BluetoothCharacteristic {
  _Characteristic(this.device, {required this.notify});
  @override
  final _Device device;
  final bool notify;
  @override
  fbp.Guid get uuid => fbp.Guid(notify ? 'fff1' : 'fff2');
  @override
  fbp.CharacteristicProperties get properties => fbp.CharacteristicProperties(notify: notify, write: !notify);
  @override
  Stream<List<int>> get onValueReceived => device.notifications.stream;
  @override
  Future<bool> setNotifyValue(bool enable, {int timeout = 15, bool forceIndications = false}) async {
    debugPrint('T02_GATT_NOTIFY $enable');
    return true;
  }
  @override
  Future<void> write(List<int> value, {bool withoutResponse = false, bool allowLongWrite = false,
      int timeout = 15}) async {
    device.write(value);
    debugPrint('T02_GATT_WRITE_RETURN');
  }
}

class _Gatt extends Fake implements fbp.BluetoothService {
  _Gatt(this.characteristics);
  @override
  fbp.Guid get uuid => fbp.Guid('fff0');
  @override
  final List<fbp.BluetoothCharacteristic> characteristics;
}

class _Sensor extends Fake implements fbp.BluetoothDevice {
  _Sensor(String address) : remoteId = fbp.DeviceIdentifier(address);
  @override
  final fbp.DeviceIdentifier remoteId;
  @override
  String get platformName => 'Power sensor';
}

fbp.ScanResult _advertisement(String address, {bool stale = false}) => fbp.ScanResult(
  device: _Sensor(address), rssi: -50,
  timeStamp: DateTime.now().subtract(Duration(seconds: stale ? 60 : 0)),
  advertisementData: fbp.AdvertisementData(advName: 'Power sensor', txPowerLevel: null,
    appearance: 0, connectable: false, manufacturerData: {0xffff: [100, 0, 50, 0xc0, 0x5d]},
    serviceData: {}, serviceUuids: []),
);

/// Fake SQLite driver, not DatabaseService or MonitorController persistence.
class _Database extends Fake implements Database {
  _Database({required bool history}) {
    if (history) {
      for (var i = 0; i < 305; i++) {
        initial.add(DeviceData(deviceId: _sensor, deviceName: 'Power sensor',
          timestamp: DateTime(2026, 1, 1).add(Duration(seconds: i)), current: 50,
          currentUnit: 'mA', voltage: 24000, power: 1200, dataType: BleDataType.scanResponse).toMap());
      }
    }
  }
  final initial = <Map<String, Object?>>[];
  final saved = <Map<String, Object?>>[];
  final attempts = <List<Map<String, Object?>>>[];
  final historyLimits = <int?>[];
  int deviceReads = 0, transactions = 0, maxTransactions = 0;
  String? failDevice;
  Completer<void>? commitGate;
  @override
  Future<List<Map<String, Object?>>> query(String table, {bool? distinct, List<String>? columns,
      String? where, List<Object?>? whereArgs, String? groupBy, String? having, String? orderBy,
      int? limit, int? offset}) async {
    if (table == 'devices') {
      deviceReads++;
      return [for (final id in [_sensor, _secondSensor])
        {'deviceId': id, 'deviceName': 'Power sensor', 'isMonitoring': 1}];
    }
    expectSync(table, anyOf('daily_power_consumption', 'monthly_power_consumption'));
    return [];
  }
  @override
  Future<List<Map<String, Object?>>> rawQuery(String sql, [List<Object?>? arguments]) async {
    expectSync(sql, contains('device_data'));
    final rows = [...initial, ...saved].where((row) => row['deviceId'] == arguments!.first).toList();
    if (sql.contains('COUNT(*)')) return [{'count': rows.length}];
    final limit = sql.contains('LIMIT ?') ? arguments!.last as int : null;
    historyLimits.add(limit);
    rows.sort((a, b) => (a['timestamp'] as int).compareTo(b['timestamp'] as int));
    final ordered = sql.contains('DESC') ? rows.reversed.toList() : rows;
    return limit == null ? ordered : ordered.take(limit).toList();
  }
  @override
  Batch batch() => _Batch(this);
  @override
  Future<T> transaction<T>(Future<T> Function(Transaction txn) action, {bool? exclusive}) async {
    transactions++;
    if (transactions > maxTransactions) maxTransactions = transactions;
    try { return await action(_Transaction(this)); }
    finally { transactions--; }
  }
  Future<void> persist(List<Map<String, Object?>> rows) async {
    if (rows.isEmpty) return;
    attempts.add(rows.map(Map<String, Object?>.from).toList());
    await commitGate?.future;
    if (rows.any((row) => row['deviceId'] == failDevice)) throw StateError('SQLITE_IOERR');
    saved.addAll(rows);
  }
}

class _Transaction extends Fake implements Transaction {
  _Transaction(this.store);
  final _Database store;
  @override
  Batch batch() => store.batch();
}

class _Batch extends Fake implements Batch {
  _Batch(this.store);
  final _Database store;
  final rows = <Map<String, Object?>>[];
  @override
  void insert(String table, Map<String, Object?> values, {String? nullColumnHack,
      ConflictAlgorithm? conflictAlgorithm}) {
    if (table == 'device_data') {
      expectSync(conflictAlgorithm, ConflictAlgorithm.ignore);
      rows.add(Map<String, Object?>.from(values));
    }
  }
  @override
  Future<List<Object?>> commit({bool? exclusive, bool? noResult, bool? continueOnError}) async {
    await store.persist(rows);
    return [];
  }
}
