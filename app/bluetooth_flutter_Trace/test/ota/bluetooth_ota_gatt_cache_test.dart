import 'dart:async';
import 'dart:io';

import 'package:flutter_blue_plus/flutter_blue_plus.dart' as fbp;
import 'package:flutter_test/flutter_test.dart';
import 'package:ble_monitor/ota/ota_link_stats.dart';
import 'package:ble_monitor/services/bluetooth_service.dart';

class _MobileAdapter extends Fake implements BluetoothAdapter {
  @override
  bool get supportsCharacteristicValueStream => false;
}

class _GattCharacteristic extends Fake implements fbp.BluetoothCharacteristic {
  _GattCharacteristic(String id, {bool write = false, bool without = false,
      bool notify = false})
      : uuid = fbp.Guid(id),
        properties = fbp.CharacteristicProperties(write: write,
            writeWithoutResponse: without, notify: notify);

  @override
  final fbp.Guid uuid;
  @override
  final fbp.CharacteristicProperties properties;
  final values = StreamController<List<int>>.broadcast(sync: true);
  final writes = <List<int>>[];
  final modes = <bool>[];
  final notifyChanges = <bool>[];
  final writeEntered = Completer<void>();
  final notifyEntered = Completer<void>();
  Completer<void>? writeGate;
  Completer<void>? notifyGate;

  @override
  Stream<List<int>> get onValueReceived => values.stream;

  @override
  Future<void> write(List<int> value, {bool withoutResponse = false,
      bool allowLongWrite = false, int timeout = 15}) async {
    writes.add(List<int>.of(value));
    modes.add(withoutResponse);
    if (!writeEntered.isCompleted) writeEntered.complete();
    await writeGate?.future;
  }

  @override
  Future<bool> setNotifyValue(bool notify,
      {int timeout = 15, bool forceIndications = false}) async {
    notifyChanges.add(notify);
    if (!notifyEntered.isCompleted) notifyEntered.complete();
    await notifyGate?.future;
    return true;
  }
}

class _GattService extends Fake implements fbp.BluetoothService {
  _GattService(this.characteristics, {String id = 'fff0'}) : uuid = fbp.Guid(id);
  @override
  final fbp.Guid uuid;
  @override
  final List<fbp.BluetoothCharacteristic> characteristics;
}

class _GattDevice extends Fake implements fbp.BluetoothDevice {
  _GattDevice(String address) : remoteId = fbp.DeviceIdentifier(address);
  @override
  final fbp.DeviceIdentifier remoteId;
  @override
  bool isConnected = true;
  final connections = StreamController<fbp.BluetoothConnectionState>.broadcast(sync: true);
  final resets = StreamController<void>.broadcast(sync: true);
  final writer = _GattCharacteristic('fff2', write: true, without: true);
  final notifier = _GattCharacteristic('fff1', notify: true);
  late List<fbp.BluetoothService> services = [_GattService([writer, notifier])];
  int discoveries = 0;
  final discoveryEntered = Completer<void>();
  Completer<List<fbp.BluetoothService>>? discoveryGate;

  @override
  Stream<fbp.BluetoothConnectionState> get connectionState => connections.stream;
  @override
  Stream<void> get onServicesReset => resets.stream;
  @override
  Future<List<fbp.BluetoothService>> discoverServices(
      {bool subscribeToServicesChanged = true, int timeout = 15}) async {
    discoveries++;
    if (!discoveryEntered.isCompleted) discoveryEntered.complete();
    final gate = discoveryGate;
    discoveryGate = null;
    return gate == null ? services : await gate.future;
  }

  void drop() {
    isConnected = false;
    connections.add(fbp.BluetoothConnectionState.disconnected);
  }

  Future<void> close() async {
    await connections.close();
    await resets.close();
    await writer.values.close();
    await notifier.values.close();
  }
}

class _WinCharacteristic {
  _WinCharacteristic(this.uuid, this.properties);
  final String uuid;
  final Map<String, bool> properties;
}

class _WinAdapter extends Fake implements BluetoothAdapter {
  final characteristics = <_WinCharacteristic>[];
  @override
  Future<List<dynamic>> discoverServices(String deviceAddress) async => ['fff0'];
  @override
  Future<List<dynamic>> discoverCharacteristics(String address, String service) async =>
      characteristics;
}

void main() {
  group('P3-4 mobile GATT candidate matrix', () {
    late BluetoothService service;
    late _GattDevice device;
    late List<_GattDevice> devices;

    void configure({bool reuse = true, bool preferWithout = false}) {
      service = BluetoothService(reuseOtaCharacteristics: reuse,
          preferOtaWithoutResponse: preferWithout);
      service.adapterForTest = _MobileAdapter();
      service.connectedDevices.addAll(devices);
    }

    Future<Map<String, String>?> discover([_GattDevice? target]) =>
        service.findExactOtaCharacteristicsByAddress((target ?? device).remoteId.str);
    Future<void> write({bool withResponse = true, OtaLinkStats? stats,
        _GattDevice? target}) => service.writeOtaCharacteristicByAddress(
          (target ?? device).remoteId.str, 'fff0', 'fff2', [1, 2, 3],
          writeWithResponse: withResponse, stats: stats);

    setUp(() {
      device = _GattDevice('AA:BB:CC:DD:EE:01');
      devices = [device];
      configure();
    });
    tearDown(() async {
      service.onClose();
      for (final item in devices) { await item.close(); }
    });

    for (final reuse in [false, true]) {
      for (final without in [false, true]) {
        test('reuse=$reuse, preferWithout=$without preserves bytes and statistics', () async {
          configure(reuse: reuse, preferWithout: without);
          final stats = OtaLinkStats(label: 'upgrade');
          final found = await service.findExactOtaCharacteristicsByAddress(
              device.remoteId.str, stats: stats);
          expect(found!['writeMode'], without ? 'without' : 'with');
          final stream = await service.subscribeOtaNotifyByAddress(
              device.remoteId.str, 'fff0', 'fff1', stats: stats);
          expect(stream, isNotNull);
          final received = <List<int>>[];
          final sub = stream!.listen(received.add);
          await write(withResponse: !without, stats: stats);
          await write(withResponse: !without, stats: stats);
          device.notifier.values.add([7, 7]);
          device.notifier.values.add([7, 7]);
          await Future<void>.delayed(Duration.zero);
          expect(received, [[7, 7], [7, 7]]);
          expect(device.writer.writes, [[1, 2, 3], [1, 2, 3]]);
          expect(device.writer.modes, [without, without]);
          expect(device.discoveries, reuse ? 1 : 4);
          final data = stats.toJson();
          expect((data['discovers'] as Map)['calls'], reuse ? 1 : 4);
          expect((data['platformWrites'] as Map)['calls'], 2);
          expect((data['gattWrites'] as Map)['calls'], 2);
          await sub.cancel();
        });
      }
    }

    test('cache miss and write-mode mismatch never rediscover or write', () async {
      await expectLater(write(), throwsStateError);
      expect(device.discoveries, 0);
      await discover();
      await expectLater(write(withResponse: false), throwsStateError);
      expect(device.writer.writes, isEmpty);
      expect(device.discoveries, 1);
    });

    test('nonstandard service UUID cannot populate the cache', () async {
      device.services = [_GattService([device.writer, device.notifier],
          id: '1111fff0-0000-1000-8000-00805f9b34fb')];
      expect(await discover(), isNull);
      await expectLater(write(), throwsStateError);
      expect(device.writer.writes, isEmpty);
    });

    test('missing FFF1 revokes a previously valid binding', () async {
      await discover();
      device.services = [_GattService([device.writer])];
      expect(await discover(), isNull);
      expect(service.otaGattBindingToken(device.remoteId.str), isNull);
      await expectLater(write(), throwsStateError);
    });

    test('disconnect invalidates before another platform write', () async {
      await discover();
      final generation = service.otaLinkGeneration(device.remoteId.str);
      device.drop();
      expect(service.otaLinkGeneration(device.remoteId.str), greaterThan(generation));
      await expectLater(write(), throwsStateError);
      expect(device.writer.writes, isEmpty);
    });

    test('service reset invalidates and requires fresh discovery', () async {
      await discover();
      final old = service.otaGattBindingToken(device.remoteId.str);
      device.resets.add(null);
      await expectLater(write(), throwsStateError);
      await discover();
      expect(identical(service.otaGattBindingToken(device.remoteId.str), old), isFalse);
      await write();
      expect(device.discoveries, 2);
    });

    test('an identical fresh recheck preserves the paused transport lease', () async {
      await discover();
      final token = service.otaGattBindingToken(device.remoteId.str);
      expect(await discover(), isNotNull);
      expect(identical(token, service.otaGattBindingToken(device.remoteId.str)), isTrue);
      await write();
      expect(device.discoveries, 2, reason: 'recheck is real, not a cached answer');
    });

    test('late discovery cannot overwrite a post-reset binding', () async {
      final gate = Completer<List<fbp.BluetoothService>>();
      device.discoveryGate = gate;
      final old = discover();
      await device.discoveryEntered.future;
      device.resets.add(null);
      expect(await discover(), isNotNull);
      final current = service.otaGattBindingToken(device.remoteId.str);
      gate.complete(device.services);
      expect(await old, isNull);
      expect(identical(current, service.otaGattBindingToken(device.remoteId.str)), isTrue);
    });

    test('an old discovery error cannot clear the new binding', () async {
      final gate = Completer<List<fbp.BluetoothService>>();
      device.discoveryGate = gate;
      final old = discover();
      await device.discoveryEntered.future;
      expect(await discover(), isNotNull);
      final current = service.otaGattBindingToken(device.remoteId.str);
      gate.completeError(StateError('old discovery failed'));
      expect(await old, isNull);
      expect(identical(current, service.otaGattBindingToken(device.remoteId.str)), isTrue);
    });

    test('device switch revokes the former device even while connected', () async {
      final other = _GattDevice('AA:BB:CC:DD:EE:02');
      devices.add(other);
      service.connectedDevices.add(other);
      await discover();
      await discover(other);
      await expectLater(write(), throwsStateError);
      await write(target: other);
      expect(device.writer.writes, isEmpty);
      expect(other.writer.writes, hasLength(1));
    });

    test('late successful platform write is not a successful current GATT write', () async {
      await discover();
      device.writer.writeGate = Completer<void>();
      final stats = OtaLinkStats(label: 'upgrade');
      final result = expectLater(write(stats: stats), throwsStateError);
      await device.writer.writeEntered.future;
      device.resets.add(null);
      device.writer.writeGate!.complete();
      await result;
      expect((stats.toJson()['platformWrites'] as Map)['errors'], 0);
      expect((stats.toJson()['gattWrites'] as Map)['errors'], 1);
      await expectLater(write(), throwsStateError);
      expect(device.writer.writes, hasLength(1));
    });

    test('late notify readiness after reset is rejected', () async {
      await discover();
      device.notifier.notifyGate = Completer<void>();
      final pending = service.subscribeOtaNotifyByAddress(device.remoteId.str, 'fff0', 'fff1');
      await device.notifier.notifyEntered.future;
      device.resets.add(null);
      device.notifier.notifyGate!.complete();
      expect(await pending, isNull);
    });

    test('canceling an old notify owner does not disable the new owner', () async {
      await discover();
      final first = (await service.subscribeOtaNotifyByAddress(
          device.remoteId.str, 'fff0', 'fff1'))!.listen((_) {});
      final second = (await service.subscribeOtaNotifyByAddress(
          device.remoteId.str, 'fff0', 'fff1'))!.listen((_) {});
      await first.cancel();
      expect(device.notifier.notifyChanges, [true, true]);
      await second.cancel();
      expect(device.notifier.notifyChanges, [true, true, false]);
    });

    test('closing service prevents an in-flight discovery from publishing', () async {
      final gate = Completer<List<fbp.BluetoothService>>();
      device.discoveryGate = gate;
      final pending = discover();
      await device.discoveryEntered.future;
      service.onClose();
      gate.complete(device.services);
      expect(await pending, isNull);
      expect(service.otaGattBindingToken(device.remoteId.str), isNull);
    });
  }, skip: Platform.isWindows);

  group('P3-4 write preference respects real capability', () {
    for (final preferWithout in [false, true]) {
      for (final caps in [[true, true], [true, false], [false, true], [false, false]]) {
        test('prefer=$preferWithout, with=${caps[0]}, without=${caps[1]}', () async {
          final service = BluetoothService(preferOtaWithoutResponse: preferWithout);
          final adapter = _WinAdapter();
          adapter.characteristics.addAll([
            _WinCharacteristic('fff2', {'write': caps[0], 'writeWithoutResponse': caps[1]}),
            _WinCharacteristic('fff1', {'notify': true}),
          ]);
          service.adapterForTest = adapter;
          final result = await service.findExactOtaCharacteristicsByAddress('AA:BB');
          final expected = caps[1] && (preferWithout || !caps[0]) ? 'without' :
              caps[0] ? 'with' : null;
          expect(result?['writeMode'], expected);
          service.onClose();
        });
      }
    }
  }, skip: !Platform.isWindows);
}
