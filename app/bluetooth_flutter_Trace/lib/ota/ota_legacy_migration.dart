import 'ota_device_info.dart';
import 'ota_firmware_latest.dart';

/// A server-owned, account-scoped grant for the one pre-UID firmware transition.
class LegacyOtaMigration {
  LegacyOtaMigration._(this._value);

  static const sourceVersion = 30348;
  static const targetVersion = 30350;
  static const targetImage =
      '6e763fb66958d4a4db3b9cbf7b02351184c189165d5499faf26986421273762a';
  final Map<String, dynamic> _value;
  String get accountId => _value['accountId'] as String;
  String get checkId => _value['checkId'] as String;
  int get expiresAt => _value['expiresAt'] as int;

  static bool supports(DeviceOtaInfo info) =>
      info.deviceModel == 'e-track-at32f435' &&
      info.currentVersionCode == sourceVersion && info.protocolVersion == 1;

  static LegacyOtaMigration parse(Map<String, dynamic> body, {
    required FirmwareLatestInfo latest, required DeviceOtaInfo source,
    required String accountId, required String checkId, required DateTime now,
  }) {
    final raw = body['legacyMigration'];
    if (raw is! Map<String, dynamic> || !supports(source) ||
        raw['mode'] != 'uid-v1' || raw['accountId'] != accountId || raw['checkId'] != checkId ||
        raw['sourceVersionCode'] != source.currentVersionCode ||
        raw['sourceImageSha256'] != source.currentImageSha256Hex ||
        raw['hardwareRevision'] != source.hardwareRevision || raw['layoutId'] != source.layoutId ||
        raw['bootVersion'] != source.bootVersion || raw['protocolVersion'] != source.protocolVersion ||
        latest.versionCode != targetVersion || latest.targetImageSha256 != targetImage ||
        raw['targetVersionCode'] != latest.versionCode || raw['targetImageSha256'] != latest.targetImageSha256 ||
        raw['targetReleaseId'] != latest.releaseId || latest.asset?.kind != 'full' ||
        latest.asset?.baseVersionCode != 0 || latest.asset?.baseImageSha256 != null ||
        raw['assetId'] != latest.asset?.assetId || raw['assetSha256'] != latest.asset?.sha256 ||
        raw['expiresAt'] is! int || (raw['expiresAt'] as int) <= now.millisecondsSinceEpoch) {
      throw OtaLatestParseException('兼容升级授权与账号、设备或正式全量包不符，请重新检查更新');
    }
    return LegacyOtaMigration._(Map.unmodifiable(raw));
  }

  bool matches(DeviceOtaInfo info, FirmwareLatestInfo? latest, String? account, String? check) =>
      account == accountId && check == checkId && supports(info) &&
      _value['sourceImageSha256'] == info.currentImageSha256Hex &&
      _value['hardwareRevision'] == info.hardwareRevision && _value['layoutId'] == info.layoutId &&
      _value['bootVersion'] == info.bootVersion && _value['protocolVersion'] == info.protocolVersion &&
      latest?.versionCode == targetVersion && latest?.targetImageSha256 == targetImage &&
      latest?.releaseId == _value['targetReleaseId'] && latest?.asset?.kind == 'full' &&
      latest?.asset?.assetId == _value['assetId'] && latest?.asset?.sha256 == _value['assetSha256'];

  Map<String, dynamic> authorization() => {
    'legacyCheckId': checkId,
    for (final key in const ['sourceVersionCode', 'sourceImageSha256', 'hardwareRevision', 'layoutId',
      'bootVersion', 'protocolVersion', 'targetVersionCode', 'targetImageSha256', 'targetReleaseId',
      'assetId', 'assetSha256']) key: _value[key],
  };
}
