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
  Completer<void>? connectGate;
  int _cancelEpoch = 0;

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
    final epoch = _cancelEpoch;
    await connectGate?.future;
    if (epoch != _cancelEpoch) return;
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
    _cancelEpoch++;
    connected = false;
  }
}

class _AndroidService extends BluetoothService {
  @override
  bool get usesAndroidLifecycle => true;
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
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

  test('P35 observation reuses the canonical cached connection without I/O', () {
    final cached = _Device(upper)..connected = true;
    created.add(cached);
    service.connectedDevices.add(cached);
    final observed = service.otaDeviceForObservation(lower);
    expect(observed, same(cached));
    expect(observed.isConnected, isTrue);
    expect(created, hasLength(1));
    expect(cached.connects, 0);
    expect(cached.disconnects, 0);
  });

  test('P35 observation never reuses a lowercase native-cache key', () {
    final stale = _Device(lower);
    created.add(stale);
    service.connectedDevices.add(stale);
    final observed = service.otaDeviceForObservation(lower);
    expect(observed.remoteId.str, upper);
    expect(observed, isNot(same(stale)));
    expect(created.last, same(observed));
    expect(created.every((d) => d.connects == 0 && d.disconnects == 0), isTrue);
  });

  test('P35 observation preserves non-MAC UUID spelling', () {
    const uuid = 'e006b3a7-ef7b-4980-a668-1f8005f84383';
    final observed = service.otaDeviceForObservation(uuid);
    expect(observed.remoteId.str, uuid);
    expect(created.single.connects, 0);
  });

  group('mobile OTA reconnect boundary', skip: Platform.isWindows, () {
    test('companion stop invalidates an outstanding native connection', () async {
      final gate = Completer<void>();
      final device = _Device(upper)..connectGate = gate;
      created.add(device);
      service.connectedDevices.add(device);
      service.otaDeviceFactoryForTest = (_) => device;
      final pending = service.connectCompanionDeviceByAddress(lower);
      await service.disconnectCompanionDeviceByAddress(lower);
      gate.complete();
      expect(await pending, isFalse);
      expect(device.isConnected, isFalse);
      expect(service.connectedDevices, isEmpty);
    });

    test('simultaneous same-address connects share the native attempt', () async {
      final gate = Completer<void>();
      final device = _Device(upper)..connectGate = gate;
      created.add(device);
      service.connectedDevices.add(device);
      final first = service.connectOtaDeviceByAddress(lower);
      final second = service.connectOtaDeviceByAddress(upper);
      expect(device.connects, 1);
      gate.complete();
      expect(await first, isTrue);
      expect(await second, isTrue);
      expect(device.connects, 1);
    });

    test('manual disconnect invalidates a late native connect completion', () async {
      final gate = Completer<void>();
      final device = _Device(upper)..connectGate = gate;
      created.add(device);
      service.connectedDevices.add(device);
      service.otaDeviceFactoryForTest = (_) => device;
      final pending = service.connectOtaDeviceByAddress(lower);
      await service.disconnectDevice(device);
      gate.complete();
      expect(await pending, isFalse);
      expect(service.connectedDevices, isEmpty);
      expect(device.isConnected, isFalse);
    });

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

  group('Android companion scoped connection', skip: Platform.isWindows, () {
    const channel = MethodChannel('flutter_blue_plus/methods');
    const runtime = 'runtime';
    final attempt = List.filled(32, 'a').join();
    late _Device device;
    late Future<Object?> Function(MethodCall) native;
    final messenger = TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger;

    setUp(() {
      service.onClose();
      service = _AndroidService();
      device = _Device(upper);
      created.add(device);
      service.otaDeviceFactoryForTest = (_) => device;
      service.companionConnectionEventsForTest = (_) => device.states.stream;
      service.companionOwnerChanged(runtime);
      native = (call) async {
        if (call.method == 'companionClose') {
          device.connected = false;
          return {'closed': true, 'replaced': false};
        }
        return true;
      };
      messenger.setMockMethodCallHandler(channel, (call) => native(call));
    });
    tearDown(() => messenger.setMockMethodCallHandler(channel, null));

    test('the first real connected callback is not skipped', () async {
      native = (call) async {
        if (call.method == 'connect') {
          expect((call.arguments as Map)['companion_attempt'], attempt);
          device.connected = true;
          device.states.add(BluetoothConnectionState.connected);
        }
        return true;
      };
      expect(await service.beginCompanionRecovery(lower, runtime, attempt), isTrue);
      expect(await service.connectCompanionDeviceByAddress(lower), isTrue);
      expect(await service.finishCompanionRecovery(lower, attempt), isTrue);
      expect(service.connectedDevices.single, same(device));
    });

    test('physical closure succeeds even when the captured connect is cancelled', () async {
      final gate = Completer<Object?>();
      native = (call) async {
        if (call.method == 'connect') return gate.future;
        if (call.method == 'companionClose') return {'closed': true, 'replaced': false};
        return true;
      };
      expect(await service.beginCompanionRecovery(lower, runtime, attempt), isTrue);
      final pending = service.connectCompanionDeviceByAddress(lower);
      final cancelled = expectLater(pending, throwsA(isA<PlatformException>()
          .having((error) => error.code, 'code', 'CONNECTION_RETIRED')));
      await Future<void>.delayed(Duration.zero);
      expect(await service.cancelCompanionRecovery(lower, attempt), isTrue);
      await cancelled;
      expect(service.connectedDevices, isEmpty);
      final nextAttempt = List.filled(32, 'b').join();
      expect(await service.beginCompanionRecovery(lower, runtime, nextAttempt), isTrue);
      gate.complete(false);
      await Future<void>.delayed(Duration.zero);
      expect(service.connectedDevices, isEmpty);
      expect(await service.cancelCompanionRecovery(lower, nextAttempt), isTrue);
    });

    test('a late stream error cannot complete an already resolved callback twice', () async {
      final gate = Completer<Object?>();
      native = (call) async {
        if (call.method == 'connect') {
          device.connected = true;
          device.states.add(BluetoothConnectionState.connected);
          return gate.future;
        }
        return true;
      };
      expect(await service.beginCompanionRecovery(lower, runtime, attempt), isTrue);
      final pending = service.connectCompanionDeviceByAddress(lower);
      await Future<void>.delayed(Duration.zero);
      device.states.addError(StateError('late stream error'));
      await Future<void>.delayed(Duration.zero);
      gate.complete(true);
      expect(await pending, isTrue);
      expect(await service.finishCompanionRecovery(lower, attempt), isTrue);
    });
  });
}
