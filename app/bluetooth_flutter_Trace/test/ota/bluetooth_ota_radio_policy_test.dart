import 'package:ble_monitor/services/bluetooth_service.dart';
import 'package:flutter_blue_plus/flutter_blue_plus.dart';
import 'package:flutter_test/flutter_test.dart';

class _Service extends BluetoothService {
  bool supported = true;
  int generation = 0;
  @override
  bool get supportsOtaAndroidPriority => supported;
  @override
  int otaLinkGeneration(String address) => generation;
}

class _Device extends BluetoothDevice {
  _Device(super.remoteId) : super.fromId();
  final requests = <ConnectionPriority>[];
  bool connected = true;
  @override
  bool get isConnected => connected;
  @override
  Future<void> requestConnectionPriority({required ConnectionPriority connectionPriorityRequest}) async {
    requests.add(connectionPriorityRequest);
  }
}

void main() {
  test('real service forwards high/balanced with canonical native ID', () async {
    final service = _Service();
    final device = _Device('E3:49:E1:14:D6:CB');
    service.otaDeviceFactoryForTest = (id) {
      expect(id, device.remoteId.str);
      return device;
    };
    final lease = service.requestOtaHighPriority('e3:49:e1:14:d6:cb');
    await lease.ready;
    await lease.close();
    expect(device.requests, [ConnectionPriority.high, ConnectionPriority.balanced]);
    service.onClose();
  });

  test('connection generation change blocks balanced restore', () async {
    final service = _Service();
    final device = _Device('E3:49:E1:14:D6:CB');
    service.otaDeviceFactoryForTest = (_) => device;
    final lease = service.requestOtaHighPriority(device.remoteId.str);
    await lease.ready;
    service.generation++;
    await lease.close();
    expect(device.requests, [ConnectionPriority.high]);
    service.onClose();
  });

  test('unsupported priority never reaches the native factory', () {
    final service = _Service()..supported = false;
    service.otaDeviceFactoryForTest = (_) => throw StateError('unexpected factory');
    expect(() => service.requestOtaHighPriority('E3:49:E1:14:D6:CB'), throwsUnsupportedError);
    service.onClose();
  });
}
