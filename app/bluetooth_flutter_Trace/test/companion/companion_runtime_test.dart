import 'dart:async';

import 'package:ble_monitor/companion/companion_platform.dart';
import 'package:ble_monitor/companion/companion_protocol.dart';
import 'package:ble_monitor/companion/companion_runtime.dart';
import 'package:ble_monitor/ota/ota_device_info.dart';
import 'package:ble_monitor/ota/ota_firmware_latest.dart';
import 'package:ble_monitor/ota/ota_link_stats.dart';
import 'package:ble_monitor/ota/ota_upgrade_consent.dart';
import 'package:ble_monitor/services/bluetooth_service.dart';
import 'package:ble_monitor/services/ota_service.dart';
import 'package:flutter/services.dart';
import 'package:flutter_blue_plus/flutter_blue_plus.dart'
    show BluetoothConnectionState, BluetoothDevice;
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

const _address = 'aa:bb:cc:dd:ee:ff';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  const channel = MethodChannel('test/companion-runtime');
  const codec = StandardMethodCodec();
  final messenger = TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger;
  late _Ble ble;
  late _Ota ota;
  late CompanionRuntime runtime;
  late SharedPreferences preferences;
  late Completer<void> ready;
  late List<Map<dynamic, dynamic>> states;
  late Map<String, Object?> settings;
  bool acceptState = true, throwState = false;
  var runtimeId = 'runtime-1';

  Future<Object?> callback(String method, Object? arguments) {
    final result = Completer<Object?>();
    messenger.handlePlatformMessage(channel.name,
      codec.encodeMethodCall(MethodCall(method, arguments)), (data) {
        result.complete(data == null ? null : codec.decodeEnvelope(data));
      });
    return result.future;
  }

  Future<void> until(bool Function() condition) async {
    final deadline = DateTime.now().add(const Duration(seconds: 5));
    while (!condition()) {
      if (DateTime.now().isAfter(deadline)) fail('Runtime did not settle: ${runtime.status.value}');
      await Future<void>.delayed(const Duration(milliseconds: 1));
    }
    // Allow the flight's finally block to retire before another platform event.
    await Future<void>.delayed(Duration.zero);
  }

  Future<void> start({String reason = 'periodic'}) async {
    runtime.onInit();
    await ready.future;
    expect(await callback('wake', {'runtimeId': runtimeId, 'revision': 'revision-1',
      'address': _address, 'reason': reason}), isTrue);
  }

  Future<void> wake(String reason) async {
    expect(await callback('wake', {'runtimeId': runtimeId, 'revision': 'revision-1',
      'address': _address, 'reason': reason}), isTrue);
  }

  CompanionMessage choice(CompanionMessage offer, String value) => CompanionMessage(
    'CHOICE', offer.session, offer.request, [offer.fields[0], offer.fields[1], offer.fields[2], value]);

  setUp(() async {
    SharedPreferences.setMockInitialValues({});
    preferences = await SharedPreferences.getInstance();
    ready = Completer<void>();
    states = [];
    settings = {'intervalHours': 12, 'wifiOnly': true, 'unmetered': true};
    acceptState = true;
    throwState = false;
    runtimeId = 'runtime-1';
    ble = _Ble();
    ota = _Ota(ble);
    runtime = CompanionRuntime(platform: CompanionPlatform(channel: channel, supported: true),
      bluetooth: ble, ota: ota);
    messenger.setMockMethodCallHandler(channel, (call) async {
      if (call.method == 'ready') {
        ready.complete();
        return settings;
      }
      if (call.method == 'snapshot') return settings;
      if (call.method == 'state') {
        states.add(Map<dynamic, dynamic>.from(call.arguments as Map));
        if (throwState) throw PlatformException(code: 'OWNER_LOST');
        return acceptState;
      }
      return null;
    });
  });

  tearDown(() async {
    ota.releaseGates();
    await callback('lost', {'runtimeId': runtimeId});
    runtime.onClose();
    await Future<void>.delayed(Duration.zero);
    await ble.notifications.close();
    await ble.device.states.close();
    await ota.activity.close();
    ota.onClose();
    ble.onClose();
    messenger.setMockMethodCallHandler(channel, null);
  });

  test('cold wake establishes identity and performs one periodic query', () async {
    await start();
    await until(() => runtime.status.value == 'NO_UPDATE');
    expect(ble.connects, 1);
    expect(ota.reads, 2);
    expect(ota.checks, 1);
    expect(ota.owners.every((id) => id == runtimeId), isTrue);
    expect(states.last['checkFinished'], isTrue);
    expect(await callback('probe', {'runtimeId': runtimeId}), runtimeId);
    expect(await callback('probe', {'runtimeId': 'old'}), isNull);
    expect(await callback('wake', {'runtimeId': runtimeId, 'revision': 'wrong',
      'address': _address, 'reason': 'manual'}), isFalse);
    expect(ota.checks, 1);
  });

  test('temporary initialization failure can retry on the next native wake', () async {
    ble.failFirstInitialization = true;
    await start();
    await until(() => runtime.status.value == 'NO_UPDATE');
    expect(ble.initializations, 2);
    expect(ota.checks, 1);
  });

  for (final throwing in [false, true]) {
    test('native state ${throwing ? 'error' : 'rejection'} stops before connecting', () async {
      acceptState = false;
      throwState = throwing;
      await start();
      await until(() => runtime.status.value == 'NATIVE_OWNER_UNAVAILABLE');
      expect(runtime.handles(_address), isFalse);
      expect(ble.connects, 0);
      expect(ota.checks, 0);
      expect(ble.disconnects, 1);
    });
  }

  test('recent recovery skips HTTP but a device request bypasses the interval', () async {
    await start();
    await until(() => runtime.status.value == 'NO_UPDATE');
    await wake('recovery');
    await until(() => runtime.status.value == 'CONNECTED');
    expect(ota.checks, 1);
    final session = ota.messages.firstWhere((m) => m.kind == 'HELLO').session;
    ble.emit(CompanionMessage('CHECK', session, 1));
    await until(() => ota.checks == 2 && runtime.status.value == 'NO_UPDATE');
    ble.emit(CompanionMessage('CHECK', session, 1));
    await Future<void>.delayed(const Duration(milliseconds: 10));
    expect(ota.checks, 2, reason: 'The same MCU request is not replayed');
    await runtime.manualCheck(_address);
    await until(() => ota.checks == 3 && runtime.status.value == 'NO_UPDATE');
  });

  test('manual work arriving during a query is coalesced instead of dropped', () async {
    await start();
    await until(() => runtime.status.value == 'NO_UPDATE');
    ota.checkGate = Completer<void>();
    await wake('periodic');
    await until(() => ota.checks == 2);
    final first = runtime.manualCheck(_address);
    final second = runtime.manualCheck(_address);
    expect(ota.checks, 2);
    ota.checkGate!.complete();
    await first;
    await second;
    await until(() => ota.checks == 3 && runtime.status.value == 'NO_UPDATE');
    expect(ota.maxConcurrent, 1);
  });

  test('HTTP failure is not published as no-update or a finished check', () async {
    ota.noUpdate = false;
    await start();
    await until(() => runtime.status.value == 'CHECK_FAILED');
    expect(states.last['checkFinished'], isFalse);
    expect(ota.messages.where((m) => m.kind == 'STATE').last.fields, ['FAILED']);
  });

  test('offer follows verified download; metered policy defers the bytes', () async {
    ota.latest = _latest();
    settings['unmetered'] = false;
    await start();
    await until(() => runtime.status.value == 'WAIT_UNMETERED_NETWORK');
    expect(ota.downloads, 0);
    expect(ota.offers, isEmpty);
    settings['unmetered'] = true;
    ota.downloadGate = Completer<void>();
    final check = runtime.manualCheck(_address);
    await until(() => ota.downloads == 1);
    expect(ota.offers, isEmpty);
    ota.downloadGate!.complete();
    await check;
    await until(() => runtime.status.value == 'READY_AWAITING_DEVICE_CHOICE');
    expect(ota.offers, hasLength(1));
    expect(preferences.getString('companion_ready_$_address'), ota.latest!.asset!.sha256);
    expect(ota.upgrades, 0);
  });

  test('prepared package is reoffered after reconnect within the normal interval', () async {
    ota.latest = _latest();
    await start();
    await until(() => runtime.status.value == 'READY_AWAITING_DEVICE_CHOICE');
    final first = ota.offers.single;
    ble.emit(CompanionMessage('SHOWN', first.session, first.request, [first.fields[0], first.fields[2]]));
    await until(() => preferences.containsKey('companion_seen_$_address'));
    await callback('lost', {'runtimeId': runtimeId});
    runtimeId = 'runtime-2';
    await wake('recovery');
    await until(() => ota.offers.length == 2 && runtime.status.value == 'READY_AWAITING_DEVICE_CHOICE');
    expect(ota.checks, 2);
    expect(ota.downloads, 1);
    expect(ota.offers.last.session, isNot(first.session));
    expect(ota.offers.last.fields[4], '0', reason: 'Reconnection does not repeat an already displayed prompt');
    ble.emit(choice(first, 'NOW'));
    await Future<void>.delayed(const Duration(milliseconds: 10));
    expect(ota.upgrades, 0);
  });

  test('later consumes the offer and a replay cannot start the sender', () async {
    ota.latest = _latest();
    await start();
    await until(() => runtime.status.value == 'READY_AWAITING_DEVICE_CHOICE');
    final offer = ota.offers.single;
    ble.emit(choice(offer, 'LATER'));
    await until(() => runtime.status.value == 'DEFERRED');
    ble.emit(choice(offer, 'NOW'));
    await Future<void>.delayed(const Duration(milliseconds: 10));
    expect(ota.upgrades, 0);
  });

  test('matching device consent starts once and verified success clears pending', () async {
    ota.latest = _latest();
    await start();
    await until(() => runtime.status.value == 'READY_AWAITING_DEVICE_CHOICE');
    final offer = ota.offers.single;
    ble.emit(choice(offer, 'NOW'));
    ble.emit(choice(offer, 'NOW'));
    await until(() => runtime.status.value == 'TARGET_IDENTITY_VERIFIED');
    expect(ota.upgrades, 1);
    expect(ota.lastConsent!.packageSha256, offer.fields[2]);
    expect(ota.lastConsent!.linkGeneration, ble.generation);
    expect(ota.lastConsent!.address, _address);
    expect(preferences.containsKey('companion_ready_$_address'), isFalse);
  });

  test('lost native owner cancels its pending query before disconnecting', () async {
    ota.readGate = Completer<void>();
    await start();
    await until(() => ota.reads == 1);
    await callback('lost', {'runtimeId': runtimeId});
    expect(runtime.handles(_address), isFalse);
    expect(ota.releases, 1);
    expect(ota.isUpgrading, isFalse);
    expect(ble.disconnects, 1);
    expect(ota.checks, 0);
    expect(ota.messages, isEmpty);
  });

  test('stopping companion never disconnects a foreign foreground task', () async {
    await start();
    await until(() => runtime.status.value == 'NO_UPDATE');
    ota.foreignBusy = true;
    await callback('lost', {'runtimeId': runtimeId});
    expect(runtime.handles(_address), isFalse);
    expect(ble.disconnects, 0);
    expect(ota.isUpgrading, isTrue);
    ota.foreignBusy = false;
  });
}

FirmwareLatestInfo _latest() => FirmwareLatestInfo.parse({
  'schemaVersion': 2, 'requestId': 'fixture', 'updateAvailable': true,
  'appId': 'trace', 'deviceModel': 'e-track-at32f435', 'channel': 'stable',
  'releaseId': 'release-1', 'versionName': '3.3.28', 'versionCode': 30328,
  'releaseTag': 'fixture', 'targetImageSha256': '62' * 32,
  'targetHardware': 'AT32F435RGT7', 'transport': 'ble', 'minAppVersionCode': 0,
  'asset': {'assetId': 'asset-1', 'kind': 'full', 'fileName': 'fixture-full.etu',
    'sha256': 'ab' * 32, 'sizeBytes': 1024, 'baseVersionCode': 0,
    'baseImageSha256': null, 'downloadUrl': 'https://localhost:9/fixture-full.etu',
    'expiresAt': 2000000000},
});

class _Device extends BluetoothDevice {
  _Device() : super.fromId(_address);
  final states = StreamController<BluetoothConnectionState>.broadcast();
  @override
  Stream<BluetoothConnectionState> get connectionState => states.stream;
}

class _Ble extends BluetoothService {
  final device = _Device();
  final notifications = StreamController<List<int>>.broadcast(sync: true);
  bool connected = false, failFirstInitialization = false;
  int connects = 0, disconnects = 0, generation = 0, initializations = 0;
  void emit(CompanionMessage message) => notifications.add(message.encode());
  @override
  bool get foregroundScanningAllowed => true;
  @override
  void companionOwnerChanged(String? runtimeId) {}
  @override
  Future<void> initBluetooth() async {
    initializations++;
    if (initializations == 1 && failFirstInitialization) throw StateError('adapter unavailable');
  }
  @override
  Future<bool> connectCompanionDeviceByAddress(String address) async {
    connects++; connected = true; generation++; return true;
  }
  @override
  Future<void> disconnectCompanionDeviceByAddress(String address) async {
    disconnects++; connected = false; generation++;
  }
  @override
  int otaLinkGeneration(String address) => generation;
  @override
  BluetoothDevice otaDeviceForObservation(String address) => device;
  @override
  Future<Map<String, String>?> findExactOtaCharacteristicsByAddress(String address,
      {String serviceUuid = 'fff0', String writeCharUuid = 'fff2', String notifyCharUuid = 'fff1',
      OtaLinkStats? stats, int? discoveryTimeoutSeconds}) async =>
    {'serviceId': 'fff0', 'writeCharId': 'fff2', 'notifyCharId': 'fff1', 'writeMode': 'with'};
  @override
  Future<Stream<List<int>>?> subscribeOtaNotifyByAddress(String address,
      String serviceId, String characteristicId, {OtaLinkStats? stats}) async => notifications.stream;
}

class _Ota extends OtaService {
  _Ota(this.ble);
  final _Ble ble;
  final activity = StreamController<bool>.broadcast(sync: true);
  final messages = <CompanionMessage>[];
  final owners = <String?>[];
  final info = DeviceOtaInfo.fromInfoPayload(buildInfoPayload(model: DeviceOtaInfo.wireModelETrack,
    hardwareRevision: 3, layoutId: 5, bootVersion: 2, currentVersionCode: 30327,
    imageSha256: List.filled(32, 0x42)));
  FirmwareLatestInfo? latest;
  OtaUpgradeConsent? lastConsent;
  String? verified, owner;
  bool noUpdate = true, foreignBusy = false, _busy = false;
  int reads = 0, checks = 0, downloads = 0, upgrades = 0, releases = 0, _concurrent = 0, maxConcurrent = 0;
  Completer<void>? readGate, checkGate, downloadGate, _done;
  List<CompanionMessage> get offers => messages.where((m) => m.kind == 'OFFER').toList();
  void releaseGates() {
    for (final gate in [readGate, checkGate, downloadGate]) {
      if (gate != null && !gate.isCompleted) gate.complete();
    }
  }
  Future<T> operation<T>(String? runtimeId, Future<T> Function() body) async {
    owners.add(runtimeId);
    _concurrent++;
    if (_concurrent > maxConcurrent) maxConcurrent = _concurrent;
    owner = runtimeId; _busy = true; _done = Completer<void>();
    activity.add(true);
    try { return await body(); }
    finally {
      _concurrent--; _busy = false; owner = null;
      _done!.complete();
      activity.add(false);
    }
  }
  @override
  bool get isUpgrading => _busy || foreignBusy;
  @override
  bool get companionTextAllowed => !isUpgrading;
  @override
  Stream<bool> get taskActivity => activity.stream;
  @override
  bool hasCurrentDeviceIdentity(String? address) => ble.connected && address == _address;
  @override
  String? get verifiedPackageSha256 => verified;
  @override
  FirmwareLatestInfo? get latestInfo => latest;
  @override
  bool get lastCheckWasNoUpdate => noUpdate;
  @override
  Future<DeviceOtaInfo?> readDeviceInfo(String address, {String? companionRuntimeId}) =>
    operation(companionRuntimeId, () async { reads++; await readGate?.future; return info; });
  @override
  Future<FirmwareLatestInfo?> checkFirmwareUpdate({String? channel, String? companionRuntimeId}) =>
    operation(companionRuntimeId, () async { checks++; await checkGate?.future; return latest; });
  @override
  Future<bool> downloadFirmware({String? companionRuntimeId}) => operation(companionRuntimeId, () async {
    downloads++; await downloadGate?.future; verified = latest!.asset!.sha256; return true;
  });
  @override
  Future<bool> startOtaUpgrade(String address, {String? companionRuntimeId, OtaUpgradeConsent? consent}) =>
    operation(companionRuntimeId, () async { upgrades++; lastConsent = consent; return true; });
  @override
  Future<bool> sendCompanionMessage(String address, CompanionMessage message, {String? companionRuntimeId}) async {
    owners.add(companionRuntimeId);
    messages.add(message);
    if (message.kind == 'HELLO') ble.emit(CompanionMessage('CAPS', message.session, 0, ['1']));
    if (message.kind == 'OFFER') {
      ble.emit(CompanionMessage('SEEN', message.session, message.request,
        [message.fields[0], message.fields[2]]));
    }
    return true;
  }
  @override
  Future<bool> releaseCompanionTask(String runtimeId) async {
    if (foreignBusy || _busy && owner != runtimeId) return false;
    if (_busy) { releases++; releaseGates(); await _done!.future; }
    return true;
  }
}
