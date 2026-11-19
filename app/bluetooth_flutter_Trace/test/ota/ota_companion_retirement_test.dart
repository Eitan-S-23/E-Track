import 'dart:async';
import 'package:ble_monitor/ota/ota_link_stats.dart';
import 'package:ble_monitor/services/bluetooth_service.dart';
import 'package:ble_monitor/services/ota_service.dart';
import 'package:flutter_test/flutter_test.dart';

class _Discovery extends BluetoothService {
  final entered = Completer<void>(), release = Completer<void>();
  int discoveries = 0;
  @override
  Future<Map<String, String>?> findExactOtaCharacteristicsByAddress(String address,
      {String serviceUuid = 'fff0', String writeCharUuid = 'fff2', String notifyCharUuid = 'fff1',
      OtaLinkStats? stats, int? discoveryTimeoutSeconds}) async {
    discoveries++;
    if (!entered.isCompleted) entered.complete();
    await release.future;
    return null;
  }
}

class _ForeignTransfer extends OtaService {
  @override
  bool get isUpgrading => true;
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  test('query cancellation and GATT cleanup jointly fence new OTA admission', () async {
    final ble = _Discovery();
    final ota = OtaService(bluetoothService: ble, onNotify: (title, message) {});
    expect(ota.beginCompanionConnection('runtime'), isTrue);
    expect(await ota.readDeviceInfo('aa:bb:cc:dd:ee:ff'), isNull);
    expect(ble.discoveries, 0, reason: 'A foreground task cannot race the recovering owner');
    final first = ota.readDeviceInfo('aa:bb:cc:dd:ee:ff', companionRuntimeId: 'runtime');
    await ble.entered.future;
    final closed = Completer<bool>();
    var closes = 0;
    final retirement = ota.retireCompanionConnection('runtime', () { closes++; return closed.future; });
    expect(await ota.readDeviceInfo('aa:bb:cc:dd:ee:ff'), isNull);
    expect(ble.discoveries, 1);
    ble.release.complete();
    expect(await first, isNull);
    expect(await ota.readDeviceInfo('aa:bb:cc:dd:ee:ff'), isNull,
      reason: 'Physical cleanup has not acknowledged yet, even though the query stopped');
    expect(ble.discoveries, 1);
    closed.complete(true);
    expect(await retirement, isTrue);
    expect(closes, 1);
    ota.endCompanionConnection('runtime');
    await ota.readDeviceInfo('aa:bb:cc:dd:ee:ff');
    expect(ble.discoveries, 2);
    ota.onClose(); ble.onClose();
  });
  test('connection recovery cannot retire a foreign transfer or apply owner', () async {
    final ota = _ForeignTransfer();
    var closed = false;
    expect(await ota.retireCompanionConnection('runtime', () async { closed = true; return true; }), isFalse);
    expect(closed, isFalse);
    ota.onClose();
  });
}
