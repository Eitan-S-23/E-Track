import 'package:ble_monitor/ota/ota_device_info.dart';
import 'package:ble_monitor/ota/ota_firmware_latest.dart';
import 'package:ble_monitor/ota/ota_legacy_migration.dart';
import 'package:ble_monitor/services/account_service.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  final now = DateTime.utc(2026, 11, 23);
  DeviceOtaInfo source([int version = 30348]) => DeviceOtaInfo.fromInfoPayload(buildInfoPayload(
    model: DeviceOtaInfo.wireModelETrack, hardwareRevision: 1, layoutId: 1, bootVersion: 1,
    currentVersionCode: version, imageSha256: List.filled(32, 0xaa)));
  Map<String, dynamic> body() => {
    'schemaVersion': 2, 'requestId': 'fixture-request', 'updateAvailable': true, 'appId': 'trace',
    'deviceModel': 'e-track-at32f435', 'channel': 'stable', 'releaseId': 'release-350',
    'versionCode': 30350, 'versionName': '3.3.50', 'releaseTag': 'mcu-e-track-at32f435-v3.3.50',
    'targetImageSha256': LegacyOtaMigration.targetImage, 'targetHardware': 'AT32F435RGT7',
    'transport': 'ble', 'minAppVersionCode': 118,
    'asset': {'assetId': 'asset-full', 'kind': 'full', 'fileName': 'e-track-v3.3.50-full.etu',
      'sha256': 'b' * 64, 'sizeBytes': 500, 'baseVersionCode': 0, 'baseImageSha256': null,
      'downloadUrl': 'https://account.example/api/public/firmware/download?signature=fixture',
      'expiresAt': now.millisecondsSinceEpoch ~/ 1000 + 300},
    'legacyMigration': {'mode': 'uid-v1', 'accountId': 'account', 'checkId': 'manual-check-0001',
      'sourceVersionCode': 30348, 'sourceImageSha256': 'a' * 64, 'hardwareRevision': 1,
      'layoutId': 1, 'bootVersion': 1, 'protocolVersion': 1, 'targetVersionCode': 30350,
      'targetImageSha256': LegacyOtaMigration.targetImage, 'targetReleaseId': 'release-350',
      'assetId': 'asset-full', 'assetSha256': 'b' * 64,
      'expiresAt': now.add(const Duration(hours: 24)).millisecondsSinceEpoch},
  };
  LegacyOtaMigration parse(Map<String, dynamic> value) => LegacyOtaMigration.parse(value,
    latest: FirmwareLatestInfo.parse(value), source: source(), accountId: 'account',
    checkId: 'manual-check-0001', now: now);

  test('manual compatibility check retains its ID and cannot become automatic', () {
    final original = AccountCheck('account', automatic: false);
    final legacy = AccountCheck.forLegacy(original);
    expect(legacy.id, original.id);
    expect(legacy.headers()['X-Legacy-Migration'], 'uid-v1');
    expect(legacy.headers(refresh: true)['X-Update-Refresh'], '1');
    expect(original.headers().containsKey('X-Legacy-Migration'), isFalse);
    expect(() => AccountCheck.forLegacy(AccountCheck('account', automatic: true)), throwsArgumentError);
  });
  test('accepts only the exact account/source/target full preparation', () {
    final value = body(), grant = parse(value);
    expect(grant.matches(source(), FirmwareLatestInfo.parse(value), 'account', 'manual-check-0001'), isTrue);
    expect(grant.matches(source(30350), FirmwareLatestInfo.parse(value), 'account', 'manual-check-0001'), isFalse);
    expect(grant.matches(source(), FirmwareLatestInfo.parse(value), 'other', 'manual-check-0001'), isFalse);
    expect(grant.authorization()['legacyCheckId'], 'manual-check-0001');
    expect(grant.authorization().containsKey('uid'), isFalse);
    expect(grant.authorization().containsKey('token'), isFalse);
  });
  for (final key in ['mode', 'accountId', 'checkId', 'sourceVersionCode', 'sourceImageSha256',
    'hardwareRevision', 'layoutId', 'bootVersion', 'protocolVersion', 'targetVersionCode',
    'targetImageSha256', 'targetReleaseId', 'assetId', 'assetSha256', 'expiresAt']) {
    test('rejects a missing or changed $key', () {
      final value = body(), raw = value['legacyMigration'] as Map<String, dynamic>;
      raw.remove(key);
      expect(() => parse(value), throwsA(isA<OtaLatestParseException>()));
      raw[key] = 'not-the-expected-value';
      expect(() => parse(value), throwsA(isA<OtaLatestParseException>()));
    });
  }
  test('expired grants and alternate targets cannot authorize an upgrade', () {
    final value = body();
    (value['legacyMigration'] as Map)['expiresAt'] = now.millisecondsSinceEpoch;
    expect(() => parse(value), throwsA(isA<OtaLatestParseException>()));
    final other = body(); other['versionCode'] = 30351;
    expect(() => parse(other), throwsA(isA<OtaLatestParseException>()));
  });
  test('patch and recovery responses cannot use the full-only migration', () {
    for (final kind in ['patch', 'recovery']) {
      final value = body(), asset = value['asset'] as Map<String, dynamic>;
      asset['kind'] = kind;
      asset['fileName'] = 'e-track-v3.3.48-to-v3.3.50-$kind.etu';
      asset['baseVersionCode'] = 30348; asset['baseImageSha256'] = 'a' * 64;
      expect(() => parse(value), throwsA(isA<OtaLatestParseException>()));
    }
  });
}
