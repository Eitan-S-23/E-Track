import 'package:ble_monitor/ota/ota_experiment_config.dart';
import 'package:ble_monitor/ota/ota_link_profile.dart';
import 'package:ble_monitor/services/bluetooth_service.dart';
import 'package:ble_monitor/services/ota_service.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  test('compiled profile drives both real services without a runtime file', () {
    final profile = OtaLinkProfile.build;
    final runtime = OtaExperimentRuntime(enabled: false);
    OtaExperimentRuntime.withInstance(runtime, () {
      final bluetooth = BluetoothService();
      final service = OtaService(bluetoothService: bluetooth);
      expect(runtime.config, isNull);
      expect(service.linkProfile, same(profile));
      expect(bluetooth.reuseOtaCharacteristics, profile.reuseGatt);
      expect(bluetooth.preferOtaWithoutResponse, profile.preferWithoutResponse);
      expect(service.linkSelection, isNull); // Build intent is not negotiation.
    });
  });

  test('release candidate and baseline stay explicit and reject unknown input', () {
    expect(OtaLinkProfile.parse('baseline'), same(OtaLinkProfile.baseline));
    final candidate = OtaLinkProfile.parse('adaptive-v2-candidate');
    expect(candidate, same(OtaLinkProfile.adaptiveCandidate));
    expect(candidate.requested, {
      'profile': 'adaptive-v2-candidate', 'protocol': 2,
      'windowSegments': 24, 'dataBatchFrames': 12,
      'reuseGatt': true, 'preferWithoutResponse': true,
    });
    for (final name in ['', 'runtime', 'p34-qualified-v1', 'unknown']) {
      expect(() => OtaLinkProfile.parse(name), throwsArgumentError);
    }
  });

  test('explicit baseline injection remains available in a candidate build', () {
    final bluetooth = BluetoothService(linkProfile: OtaLinkProfile.baseline);
    final service = OtaService(linkProfile: OtaLinkProfile.baseline,
        bluetoothService: bluetooth);
    expect(service.linkProfile.pipeline, isFalse);
    expect(bluetooth.reuseOtaCharacteristics, isFalse);
    expect(bluetooth.preferOtaWithoutResponse, isFalse);
  });
}
