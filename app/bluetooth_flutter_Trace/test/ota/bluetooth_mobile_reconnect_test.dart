import 'dart:async';
import 'dart:io' show Platform;

import 'package:ble_monitor/services/bluetooth_service.dart';
import 'package:flutter/services.dart';
import 'package:flutter_blue_plus/flutter_blue_plus.dart'
    show BluetoothConnectionState, BluetoothDevice;
import 'package:flutter_test/flutter_test.dart';

class _Device extends BluetoothDevice {
  _Device(super.remoteId) : super.fromId();

  final states = StreamController<BluetoothConnectionState>.broadcast();
  bool connected = false;
  bool failConnect = false;
  bool connectWithoutLink = false;
  int connects = 0;
  int disconnects = 0;
  int? requestedMtu = 999;
  Duration? connectTimeout;

  @override
  bool get isConnected => connected;

  @override
  Stream<BluetoothConnectionState> get connectionState => states.stream;

  @override
  Future<void> connect({
    Duration timeout = const Duration(seconds: 35),
    int? mtu = 512,
    bool autoConnect = false,
  }) async {
    connects++;
    requestedMtu = mtu;
    connectTimeout = timeout;
    if (failConnect || mtu != null) {
      throw PlatformException(code: 'requestMtu', message: 'device is disconnected');
    }
    connected = !connectWithoutLink;
  }

  @override
  Future<void> disconnect({int timeout = 35, bool queue = true, int androidDelay = 2000}) async {
    disconnects++;
    connected = false;
  }
}

void main() {
  const lower = 'e3:49:e1:14:d6:cb';
  const upper = 'E3:49:E1:14:D6:CB';
  late BluetoothService service;
  late List<_Device> created;

  setUp(() {
    service = BluetoothService();
    created = [];
    service.otaDeviceFactoryForTest = (id) {
      final device = _Device(id);
      created.add(device);
      return device;
    };
  });

  tearDown(() async {
    service.onClose();
    for (final device in created) {
      await device.states.close();
    }
  });

  group('mobile OTA reconnect boundary', skip: Platform.isWindows, () {
    test('cold lowercase MAC uses native spelling and defers automatic MTU', () async {
      expect(await service.connectOtaDeviceByAddress(lower), isTrue);
      final device = created.single;
      expect(device.remoteId.str, upper);
      expect(device.requestedMtu, isNull);
      expect(device.connectTimeout, const Duration(seconds: 10));
      expect(service.connectedDevices.single, same(device));
      expect(service.otaLinkGeneration(lower), 1);
    });

    test('canonical cached device is reused without a second factory object', () async {
      final cached = _Device(upper);
      created.add(cached);
      service.connectedDevices.add(cached);
      expect(await service.connectOtaDeviceByAddress(lower), isTrue);
      expect(created, hasLength(1));
      expect(cached.connects, 1);
      expect(cached.requestedMtu, isNull);
    });

    test('lowercase cached object cannot leak into later MTU/discovery', () async {
      final stale = _Device(lower);
      created.add(stale);
      service.connectedDevices.add(stale);
      expect(await service.connectOtaDeviceByAddress(lower), isTrue);
      expect(stale.connects, 0);
      expect(service.connectedDevices.single.remoteId.str, upper);
      expect(service.connectedDevices.single, same(created.last));
    });

    test('disconnect uses the same canonical cold-cache identifier', () async {
      await service.disconnectOtaDeviceByAddress(lower);
      expect(created.single.remoteId.str, upper);
      expect(created.single.disconnects, 1);
      expect(service.connectedDevices, isEmpty);
    });

    test('Apple UUID identifiers are not uppercased', () async {
      const uuid = 'e006b3a7-ef7b-4980-a668-1f8005f84383';
      expect(await service.connectOtaDeviceByAddress(uuid), isTrue);
      expect(created.single.remoteId.str, uuid);
    });

    test('cached UUID spelling is preserved for a case-insensitive lookup', () async {
      const uuid = 'E006B3A7-EF7B-4980-A668-1F8005F84383';
      final cached = _Device(uuid);
      created.add(cached);
      service.connectedDevices.add(cached);
      expect(await service.connectOtaDeviceByAddress(uuid.toLowerCase()), isTrue);
      expect(created, hasLength(1));
      expect(service.connectedDevices.single, same(cached));
    });

    test('connect exception does not publish a connected device or generation', () async {
      service.otaDeviceFactoryForTest = (id) {
        final device = _Device(id)..failConnect = true;
        created.add(device);
        return device;
      };
      expect(await service.connectOtaDeviceByAddress(lower), isFalse);
      expect(service.connectedDevices, isEmpty);
      expect(service.otaLinkGeneration(lower), 0);
    });

    test('a resolved connect without a live link is not success', () async {
      service.otaDeviceFactoryForTest = (id) {
        final device = _Device(id)..connectWithoutLink = true;
        created.add(device);
        return device;
      };
      expect(await service.connectOtaDeviceByAddress(lower), isFalse);
      expect(service.connectedDevices, isEmpty);
      expect(service.otaLinkGeneration(lower), 0);
    });
  });
}
