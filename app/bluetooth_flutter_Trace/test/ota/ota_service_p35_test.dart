import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:ble_monitor/ota/ota_ble_codec.dart';
import 'package:ble_monitor/ota/ota_device_info.dart';
import 'package:ble_monitor/ota/ota_link_stats.dart';
import 'package:ble_monitor/ota/ota_p35_recorder.dart';
import 'package:ble_monitor/services/bluetooth_service.dart';
import 'package:ble_monitor/services/ota_service.dart';
import 'package:flutter_blue_plus/flutter_blue_plus.dart'
    show BluetoothConnectionState, BluetoothDevice;
import 'package:flutter_test/flutter_test.dart';

const lower = 'aa:bb:cc:dd:ee:ff';
const upper = 'AA:BB:CC:DD:EE:FF';

class _NativeDevice extends BluetoothDevice {
  _NativeDevice(super.remoteId, this.nativeCache) : super.fromId();

  // Mirrors the SDK's case-sensitive native connection-state cache.
  final Map<String, bool> nativeCache;
  final states = StreamController<BluetoothConnectionState>.broadcast();

  @override
  bool get isConnected => nativeCache[remoteId.str] ?? false;

  @override
  Stream<BluetoothConnectionState> get connectionState async* {
    yield isConnected
        ? BluetoothConnectionState.connected
        : BluetoothConnectionState.disconnected;
    yield* states.stream;
  }
}

class _QueryBle extends BluetoothService {
  _QueryBle() {
    device = _NativeDevice(upper, nativeCache);
    connectedDevices.add(device);
    otaDeviceFactoryForTest = (address) {
      factoryCalls++;
      return _NativeDevice(address, nativeCache);
    };
  }

  final nativeCache = <String, bool>{upper: true};
  late final _NativeDevice device;
  final notifications = StreamController<List<int>>.broadcast();
  int generation = 1;
  int factoryCalls = 0;
  int infoCalls = 0;

  void setLink(bool connected, {bool emit = true}) {
    generation++;
    nativeCache[upper] = connected;
    if (emit) {
      device.states.add(connected
          ? BluetoothConnectionState.connected
          : BluetoothConnectionState.disconnected);
    }
  }

  @override
  int otaLinkGeneration(String deviceAddress) => generation;

  @override
  Future<bool> connectOtaDeviceByAddress(String deviceAddress) async {
    setLink(true);
    return device.isConnected;
  }

  @override
  Future<Map<String, String>?> findExactOtaCharacteristicsByAddress(
    String deviceAddress, {
    String serviceUuid = 'fff0',
    String writeCharUuid = 'fff2',
    String notifyCharUuid = 'fff1',
    OtaLinkStats? stats,
    int? discoveryTimeoutSeconds,
  }) async => {
        'serviceId': 'fff0',
        'writeCharId': 'fff2',
        'notifyCharId': 'fff1',
        'writeMode': 'with',
      };

  @override
  Future<int> requestOtaMtu(String deviceAddress,
          {int requested = 247, OtaLinkStats? stats}) async =>
      247;

  @override
  Future<Stream<List<int>>?> subscribeOtaNotifyByAddress(
    String deviceAddress,
    String serviceId,
    String characteristicId, {
    OtaLinkStats? stats,
  }) async => notifications.stream;

  @override
  Future<void> writeOtaCharacteristicByAddress(
    String deviceAddress,
    String serviceId,
    String characteristicId,
    List<int> data, {
    bool writeWithResponse = false,
    OtaLinkStats? stats,
  }) async {
    final request = OtaBleCodec.decodeFrame(data);
    if (request.cmd != OtaBleCodec.cmdGetInfo) {
      throw StateError('P35 regression must never send an upgrade command');
    }
    infoCalls++;
    notifications.add(OtaBleCodec.encodeCommand(
      cmd: OtaBleCodec.rspInfo,
      session: 0,
      seq: request.seq,
      payload: buildInfoPayload(
        model: DeviceOtaInfo.wireModelETrack,
        hardwareRevision: 3,
        layoutId: 5,
        bootVersion: 2,
        currentVersionCode: 30293,
        imageSha256: List<int>.filled(32, 0x71),
      ),
    ));
  }
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  late Directory root;
  late _QueryBle ble;
  late OtaService service;
  late OtaP35Recorder recorder;
  late List<String> lines;
  Future<Directory> Function()? directoryProvider;
  bool supported = true;

  List<Map<String, dynamic>> rows() => lines
      .where((line) => line.startsWith('OTA_P35_STATE '))
      .map((line) => jsonDecode(line.substring('OTA_P35_STATE '.length))
          as Map<String, dynamic>)
      .toList();

  Future<void> flush() async {
    await Future<void>.delayed(const Duration(milliseconds: 20));
  }

  Future<void> waitFor(bool Function() ready, String reason) async {
    final clock = Stopwatch()..start();
    while (!ready()) {
      if (clock.elapsed >= const Duration(seconds: 5)) {
        fail('P35 observation deadline: $reason');
      }
      await Future<void>.delayed(const Duration(milliseconds: 1));
    }
  }

  Future<Map<String, dynamic>> rowAfter(int seq, String event) async {
    bool matches(Map<String, dynamic> row) =>
        (row['seq'] as int) > seq && row['event'] == event;
    // Publication follows the real file flush, not a fixed host scheduling delay.
    await waitFor(() => rows().any(matches), '$event after seq $seq');
    return rows().firstWhere(matches);
  }

  setUp(() async {
    final parent = Directory('${Directory.current.path}/.dart_tool/p35-service-tests');
    await parent.create(recursive: true);
    root = await parent.createTemp('case-');
    ble = _QueryBle();
    lines = [];
    directoryProvider = null;
    supported = true;
    recorder = OtaP35Recorder(
      emit: lines.add,
      directoryProvider: () => directoryProvider?.call() ?? Future.value(root),
    );
    service = OtaService(
      bluetoothService: ble,
      p35Recorder: recorder,
      p35PlatformCheck: () => supported,
      onNotify: (_, __) {},
    );
    expect(await service.readDeviceInfo(lower), isNotNull);
  });

  tearDown(() async {
    await service.stopP35Recording();
    service.onClose();
    ble.onClose();
    await flush();
    await ble.device.states.close();
    await ble.notifications.close();
    await root.delete(recursive: true);
  });

  test('real P35 service uses canonical native state, not the lowercase cache miss', () async {
    final wrongKey = _NativeDevice(lower, ble.nativeCache);
    expect(wrongKey.isConnected, isFalse);
    await wrongKey.states.close();
    expect(ble.device.isConnected, isTrue);
    expect(await service.startP35Recording(), isTrue);
    expect(await service.reconnectP35Target(), isTrue);
    await flush();
    await service.stopP35Recording();
    expect(ble.factoryCalls, 0, reason: 'reuse the actual canonical connection');
    expect(ble.infoCalls, 2, reason: 'initial query and explicit post-arm GET_INFO');
    expect(rows().every((row) => row['linkConnected'] == true), isTrue);
    expect(rows().where((row) => row['event'] == 'identity'), hasLength(1));
    expect(rows().last['freshConnection'], isTrue);
    expect(await recorder.file!.readAsString(), '${lines.join('\n')}\n');
  });

  test('actual disconnect and reconnect never refresh a cached identity', () async {
    expect(await service.startP35Recording(), isTrue);
    await waitFor(
      () => ble.device.states.hasListener &&
          rows().where((row) => row['event'] == 'state').length >= 2,
      'initial snapshot and subscribed native state',
    );
    var seq = rows().last['seq'] as int;
    ble.setLink(false);
    var row = await rowAfter(seq, 'state');
    expect(row['linkConnected'], isFalse);
    expect(row['freshConnection'], isFalse);
    seq = row['seq'] as int;
    ble.setLink(true);
    row = await rowAfter(seq, 'state');
    expect(row['linkConnected'], isTrue);
    expect(row['freshConnection'], isFalse);
    expect(service.hasCurrentDeviceIdentity(lower), isFalse);
    seq = row['seq'] as int;
    expect(await service.readDeviceInfo(lower), isNotNull);
    row = await rowAfter(seq, 'identity');
    expect(row['freshConnection'], isTrue);
  });

  test('generation-only invalidation remains visible in a recorded heartbeat', () async {
    await service.startP35Recording();
    await flush();
    ble.generation++;
    recorder.record('heartbeat');
    await flush();
    expect(rows().last['event'], 'heartbeat');
    expect(rows().last['linkConnected'], isTrue);
    expect(rows().last['freshConnection'], isFalse);
  });

  test('disconnect during async recorder open cannot publish a stale connected flag', () async {
    final entered = Completer<void>();
    final gate = Completer<Directory>();
    directoryProvider = () {
      entered.complete();
      return gate.future;
    };
    final starting = service.startP35Recording();
    await entered.future;
    ble.setLink(false, emit: false);
    gate.complete(root);
    expect(await starting, isTrue);
    await flush();
    expect(rows(), isNotEmpty);
    expect(rows().every((row) => row['linkConnected'] == false), isTrue);
    expect(rows().every((row) => row['freshConnection'] == false), isTrue);
  });

  test('platform admission remains false with no recorder or connection side effects', () async {
    supported = false;
    expect(await service.startP35Recording(), isFalse);
    expect(recorder.captureId, isNull);
    expect(lines, isEmpty);
    expect(ble.factoryCalls, 0);
  });

  test('a connection stream error stays an unhealthy immutable capture', () async {
    await service.startP35Recording();
    await flush();
    ble.device.states.addError(StateError('synthetic connection stream failure'));
    await flush();
    expect(recorder.error, 'connection-stream-failed');
    await service.stopP35Recording();
    final footer = jsonDecode(lines.last.substring('OTA_P35_CAPTURE '.length));
    expect(footer['healthy'], isFalse);
    expect(footer['error'], 'connection-stream-failed');
  });

  test('stop cancels the connection reader and does not reactivate recording', () async {
    await service.startP35Recording();
    await flush();
    await service.stopP35Recording();
    final count = lines.length;
    ble.setLink(false);
    await flush();
    expect(lines.length, count);
    expect(recorder.status.value, 'closed');
    expect(await service.startP35Recording(), isFalse);
  });
}
