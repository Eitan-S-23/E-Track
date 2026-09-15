import 'dart:convert';

/// latest schema v2 的 typed DTO 与 fail-closed 解析
/// （冻结依据 docs/ota-cross-system-contracts.md OTA-XC-HTTP-LATEST、
/// OTA-XC-HTTP-ERROR、OTA-XC-UNKNOWN-FIELDS、OTA-XC-COMPATIBILITY、
/// OTA-XC-CLOUD-QUERY-MAPPING、OTA-XC-ASSET-NAMING）。
///
/// 解析规则：
/// - `schemaVersion` major 必须为 2（同 major 的新增可选字段被忽略）；
/// - required 字段缺失或类型错误必须终止；
/// - 未知 `asset.kind`、未知 `errorCode` 必须终止，不得降级成成功或 NO_UPDATE；
/// - `NO_UPDATE` / `CHANNEL_STOPPED` 是 HTTP 200 业务结果，不是异常路径；
/// - false 分支必带 `errorCode`；true 分支不得携带 `errorCode`；
/// - 查询身份回显（appId/deviceModel/channel）与传输能力（transport）
///   必须与请求侧一致，防止清单与请求错配。
class FirmwareLatestInfo {
  FirmwareLatestInfo._({
    required this.requestId,
    required this.updateAvailable,
    this.errorCode,
    this.maintenanceMessage,
    this.releaseId,
    this.versionName,
    this.versionCode,
    this.releaseTag,
    this.releaseNotes,
    this.targetImageSha256,
    this.targetHardware,
    this.transport,
    this.minAppVersionCode,
    this.asset,
  });

  /// 无更新/停发通道：业务结果对象。
  factory FirmwareLatestInfo.noUpdate(String requestId) =>
      FirmwareLatestInfo._(requestId: requestId, updateAvailable: false);

  final String requestId;
  final bool updateAvailable;

  /// `updateAvailable=false` 时的业务结果码：`NO_UPDATE` / `CHANNEL_STOPPED`。
  /// `updateAvailable=true` 时恒为 null。
  final String? errorCode;
  /// 仅 `CHANNEL_STOPPED` 可附带。
  final String? maintenanceMessage;

  // 以下字段仅在 updateAvailable=true 时非空。
  final String? releaseId;
  final String? versionName;
  final int? versionCode;
  final String? releaseTag;
  final String? releaseNotes;
  /// 权威目标镜像 raw SHA-256（64 小写 hex）。
  final String? targetImageSha256;
  final String? targetHardware;
  final String? transport;
  final int? minAppVersionCode;
  final OtaFirmwareAsset? asset;

  /// 检查更新可用（`updateAvailable=true` 且带完整 release/asset 字段）。
  bool get hasUpdate => updateAvailable && asset != null;

  /// latest 合同的固定 appId（OTA-XC-CLOUD-QUERY-MAPPING）。
  static const String expectedAppId = 'trace';
  /// 客户端实现的传输通道闭集合（transport 字段能力协商）。
  static const Set<String> supportedTransports = {'ble'};
  /// 查询/回显 channel 闭集合（OTA-XC-CLOUD-QUERY-MAPPING）。
  static const Set<String> knownChannels = {'stable', 'beta'};

  /// 解析 HTTP 200 的 latest JSON。违反 schema v2 必填结构时抛
  /// [OtaLatestParseException]，调用方必须终止该次检查流程。
  ///
  /// [expectedDeviceModel] 传入本次查询使用的 deviceModel（来自
  /// DeviceOtaInfo 映射表）时校验回显一致，防止清单与请求错配。
  /// [expectedChannel] 传入本次查询使用的 channel 时同样校验回显一致。
  ///
  /// 回显校验按响应分支执行（RC2-02）：冻结合同 OTA-XC-HTTP-LATEST
  /// 规定 `updateAvailable=false`（NO_UPDATE/CHANNEL_STOPPED）是精简体，
  /// 只含 schemaVersion/requestId/updateAvailable/errorCode（可选
  /// maintenanceMessage），不含 appId/deviceModel/channel——不得因缺
  /// 回显拒绝合法 NO_UPDATE；true 分支才校验回显与全量 release 字段。
  static FirmwareLatestInfo parse(
    Map<String, dynamic> body, {
    String? expectedDeviceModel,
    String? expectedChannel,
  }) {
    final schemaVersion = _requireInt(body, 'schemaVersion');
    if (schemaVersion != 2) {
      // 合同只定义 schemaVersion=2；未知 major（或任何偏离值）终止。
      throw OtaLatestParseException('未知 schema major: $schemaVersion');
    }
    final requestId = _requireString(body, 'requestId');
    final updateAvailable = _requireBool(body, 'updateAvailable');
    if (!updateAvailable) {
      if (body.containsKey('errorCode') == false) {
        throw OtaLatestParseException('updateAvailable=false 缺 errorCode');
      }
      final errorCode = _requireString(body, 'errorCode');
      if (!_knownNoUpdateCodes.contains(errorCode)) {
        throw OtaLatestParseException('未知 errorCode: $errorCode');
      }
      return FirmwareLatestInfo._(
        requestId: requestId,
        updateAvailable: false,
        errorCode: errorCode,
        maintenanceMessage: _optionalString(body, 'maintenanceMessage'),
      );
    }
    // updateAvailable=true：查询身份回显（appId/deviceModel/channel）与
    // 传输能力（transport）必须与请求侧一致，防止清单与请求错配。
    if (body['errorCode'] != null) {
      throw OtaLatestParseException('updateAvailable=true 不得携带 errorCode');
    }
    final appId = _requireString(body, 'appId', label: 'appId');
    if (appId != expectedAppId) {
      throw OtaLatestParseException('appId 回显不符: $appId');
    }
    final deviceModel = _requireString(body, 'deviceModel');
    if (expectedDeviceModel != null && deviceModel != expectedDeviceModel) {
      throw OtaLatestParseException(
          'deviceModel 回显不符: $deviceModel（期望 $expectedDeviceModel）');
    }
    final channel = _requireString(body, 'channel');
    if (!knownChannels.contains(channel)) {
      throw OtaLatestParseException('channel 非法: $channel');
    }
    if (expectedChannel != null && channel != expectedChannel) {
      throw OtaLatestParseException(
          'channel 回显不符: $channel（期望 $expectedChannel）');
    }
    // release/asset 必填字段全量校验。
    final releaseId = _requireString(body, 'releaseId');
    final versionName = _requireString(body, 'versionName');
    final versionCode = _requireInt(body, 'versionCode');
    _checkFirmwareVersionCode(versionCode, 'versionCode');
    final releaseTag = _requireString(body, 'releaseTag');
    final targetImageSha256 = _requireSha256Hex(body, 'targetImageSha256');
    final targetHardware = _requireString(body, 'targetHardware');
    final transport = _requireString(body, 'transport');
    if (!supportedTransports.contains(transport)) {
      throw OtaLatestParseException('transport 不受支持: $transport');
    }
    final minAppVersionCode = _requireInt(body, 'minAppVersionCode');
    _checkAppVersionCode(minAppVersionCode, 'minAppVersionCode');
    final rawAsset = body['asset'];
    if (rawAsset is! Map<String, dynamic>) {
      throw OtaLatestParseException('asset 缺失或类型错误');
    }
    final asset = OtaFirmwareAsset.parse(rawAsset);
    if (asset.kind == 'recovery') {
      throw OtaLatestParseException('公开 latest 不得返回 recovery 资产');
    }
    return FirmwareLatestInfo._(
      requestId: requestId,
      updateAvailable: true,
      releaseId: releaseId,
      versionName: versionName,
      versionCode: versionCode,
      releaseTag: releaseTag,
      releaseNotes: _optionalString(body, 'releaseNotes'),
      targetImageSha256: targetImageSha256,
      targetHardware: targetHardware,
      transport: transport,
      minAppVersionCode: minAppVersionCode,
      asset: asset,
    );
  }

  static const Set<String> _knownNoUpdateCodes = {
    'NO_UPDATE',
    'CHANNEL_STOPPED',
  };
}

/// latest 选中资产（asset 对象）。
class OtaFirmwareAsset {
  OtaFirmwareAsset({
    required this.assetId,
    required this.kind,
    required this.fileName,
    required this.sha256,
    required this.sizeBytes,
    required this.baseVersionCode,
    required this.baseImageSha256,
    required this.downloadUrl,
    required this.expiresAt,
  });

  final String assetId;
  /// `full` / `patch`（`recovery` 出现即解析失败）。
  final String kind;
  final String fileName;
  /// 资产原始字节 SHA-256（64 小写 hex）。
  final String sha256;
  final int sizeBytes;
  /// full 恒 0。
  final int baseVersionCode;
  /// full 恒 null；patch 为 base 镜像 raw SHA-256。
  final String? baseImageSha256;
  final String downloadUrl;
  /// 十进制 Unix epoch 秒。
  final int expiresAt;

  bool get isPatch => kind == 'patch';

  /// MCU staging 区上限（ota_layout.h OTA_ETU_MAX_LENGTH = 0x180000）。
  static const int maxPackageBytes = 0x180000;
  /// ASSET-NAMING 冻结的文件名安全字符集与长度上限。
  static final RegExp _safeFileName = RegExp(r'^[A-Za-z0-9._-]+$');

  static OtaFirmwareAsset parse(Map<String, dynamic> raw) {
    final assetId = _requireString(raw, 'assetId', label: 'asset.assetId');
    final kind = _requireString(raw, 'kind', label: 'asset.kind');
    if (!_knownKinds.contains(kind)) {
      throw OtaLatestParseException('未知 asset.kind: $kind');
    }
    if (kind == 'recovery') {
      throw OtaLatestParseException('公开 latest 不得返回 recovery 资产');
    }
    final fileName = _requireString(raw, 'fileName', label: 'asset.fileName');
    if (fileName.length > 128 ||
        !_safeFileName.hasMatch(fileName)) {
      throw OtaLatestParseException('asset.fileName 非法: $fileName');
    }
    final expectedSuffix = kind == 'full' ? '-full.etu' : '-patch.etu';
    if (!fileName.endsWith(expectedSuffix)) {
      throw OtaLatestParseException(
          'asset.fileName 与 kind 不符: $fileName（期望 $expectedSuffix 结尾）');
    }
    final sha256 = _requireSha256Hex(raw, 'sha256', label: 'asset.sha256');
    final sizeBytes = _requireInt(raw, 'sizeBytes', label: 'asset.sizeBytes');
    if (sizeBytes <= 0 || sizeBytes > maxPackageBytes) {
      throw OtaLatestParseException(
          'asset.sizeBytes 超范围: $sizeBytes（上限 $maxPackageBytes）');
    }
    final baseVersionCode =
        _requireInt(raw, 'baseVersionCode', label: 'asset.baseVersionCode');
    _checkFirmwareVersionCode(baseVersionCode, 'asset.baseVersionCode');
    final baseImageSha256KeyPresent = raw.containsKey('baseImageSha256');
    final baseImageSha256 = raw['baseImageSha256'];
    final expiresAt = _requireInt(raw, 'expiresAt', label: 'asset.expiresAt');
    if (expiresAt <= 0) {
      throw OtaLatestParseException('asset.expiresAt 非正: $expiresAt');
    }
    if (kind == 'full') {
      if (baseVersionCode != 0) {
        throw OtaLatestParseException(
            'full 资产 baseVersionCode 必须为 0: $baseVersionCode');
      }
      // 键必须存在且值为 null：缺失键与显式 null 不符合同（PR14）。
      if (!baseImageSha256KeyPresent || baseImageSha256 != null) {
        throw OtaLatestParseException(
            'full 资产 baseImageSha256 键必须存在且为 null');
      }
    } else {
      // patch
      if (baseImageSha256 is! String) {
        throw OtaLatestParseException('patch 资产 baseImageSha256 缺失');
      }
      _checkSha256Hex(baseImageSha256, 'asset.baseImageSha256');
    }
    final downloadUrl =
        _requireString(raw, 'downloadUrl', label: 'asset.downloadUrl');
    _checkDownloadUrl(downloadUrl);
    return OtaFirmwareAsset(
      assetId: assetId,
      kind: kind,
      fileName: fileName,
      sha256: sha256,
      sizeBytes: sizeBytes,
      baseVersionCode: baseVersionCode,
      baseImageSha256: baseImageSha256 is String ? baseImageSha256 : null,
      downloadUrl: downloadUrl,
      expiresAt: expiresAt,
    );
  }

  /// downloadUrl 必须是带 host 的绝对 https URL（RC2-11：生产签发恒为
  /// https；本地测试注入通过直接构造 OtaFirmwareAsset 绕过 parse，
  /// 不在生产解析器放宽 scheme）。
  static void _checkDownloadUrl(String url) {
    final Uri parsed;
    try {
      parsed = Uri.parse(url);
    } on FormatException {
      throw OtaLatestParseException('asset.downloadUrl 非法 URL: $url');
    }
    if (!parsed.hasScheme ||
        parsed.scheme != 'https' ||
        parsed.host.isEmpty) {
      throw OtaLatestParseException(
          'asset.downloadUrl 必须是带 host 的 https URL: $url');
    }
  }

  static const Set<String> _knownKinds = {'full', 'patch', 'recovery'};
}

/// latest 解析失败的稳定领域异常。
class OtaLatestParseException implements Exception {
  OtaLatestParseException(this.message);

  final String message;

  @override
  String toString() => 'OtaLatestParseException: $message';
}

/// latest 侧的终止型 HTTP 错误（426/409 兼容类）与可重试错误（429/503）模型。
class OtaHttpError {
  OtaHttpError({
    required this.errorCode,
    required this.httpStatus,
    this.message,
    this.requestId,
    this.retryAfterSeconds,
    this.minAppVersionCode,
    this.requiredValue,
    this.actualValue,
  });

  /// HTTP-ERROR 表中的稳定 errorCode。
  final String errorCode;
  final int httpStatus;
  final String? message;
  final String? requestId;
  final int? retryAfterSeconds;

  /// `CLIENT_TOO_OLD` 携带的门槛。
  final int? minAppVersionCode;
  /// 兼容错误的 required/actual 数值（409 类）。
  final int? requiredValue;
  final int? actualValue;

  /// 收到该错误后 Flutter 必须进入终止状态（不得转 NO_UPDATE、不得下载/BLE）。
  ///
  /// 终止判定**不加** HTTP 状态约束：终止本身是保守侧，服务端把终止码挂在
  /// 非契约状态上时仍应终止，而不是降级成可重试。
  bool get isTerminal => _terminalCodes.contains(errorCode);

  /// 允许用户稍后重试（保留设备状态）。
  ///
  /// RC3-10/11：必须同时匹配 errorCode 与 OTA-XC-HTTP-ERROR 表规定的 HTTP
  /// 状态。只看 errorCode 会让"稍后重试"绕开状态约束——服务端（或错配的
  /// 中间层）把 `CHANNEL_STOPPED`/`BACKEND_UNAVAILABLE` 挂在 401/403/500
  /// 等状态上时，明确的稳定拒绝会被判成软失败，用户可以无限次撞同一堵墙
  /// 且入口不闭锁。状态不符按 fail closed 交给稳定拒绝分支处理。
  bool get isRetryableLater =>
      _retryLaterCodes.contains(errorCode) && _matchesRetryStatusContract;

  /// OTA-XC-RETRY-POLICY 允许自动重试的网络类错误（同样受状态约束）。
  bool get isAutoRetryable =>
      (errorCode == 'RATE_LIMITED' || errorCode == 'BACKEND_UNAVAILABLE') &&
      _matchesRetryStatusContract;

  /// 本响应的 HTTP 状态是否符合该 errorCode 的契约状态集合。
  bool get _matchesRetryStatusContract =>
      _retryStatusContract[errorCode]?.contains(httpStatus) ?? false;

  /// 重试类 errorCode 的契约 HTTP 状态（OTA-XC-HTTP-ERROR 表）。
  /// `CHANNEL_STOPPED` 另有 latest 侧 `disable_latest=1` 的 HTTP 200 业务
  /// 结果形态（OTA-XC-LATEST），两者都保留"稍后重试"语义。
  static const Map<String, Set<int>> _retryStatusContract = {
    'CHANNEL_STOPPED': {200, 503},
    'BACKEND_UNAVAILABLE': {503},
    'RATE_LIMITED': {429},
  };

  /// 已知 errorCode 闭集合（OTA-XC-HTTP-ERROR 表）。
  static const Set<String> knownErrorCodes = {
    'INVALID_PARAMETER',
    'TOKEN_INVALID',
    'TOKEN_EXPIRED',
    'ACCESS_FORBIDDEN',
    'ROLE_FORBIDDEN',
    'ORIGIN_FORBIDDEN',
    'CSRF_INVALID',
    'CLIENT_TOO_OLD',
    'UNKNOWN_DEVICE_MODEL',
    'HARDWARE_INCOMPATIBLE',
    'LAYOUT_INCOMPATIBLE',
    'BOOT_TOO_OLD',
    'PROTOCOL_UNSUPPORTED',
    'ASSET_DISABLED',
    'ASSET_ARCHIVED',
    'RATE_LIMITED',
    'CHANNEL_STOPPED',
    'BACKEND_UNAVAILABLE',
    'CAS_CONFLICT',
    'VERSION_REGRESSION',
    'RELEASE_CONFLICT',
    'RELEASE_INCOMPLETE',
    'R2_OBJECT_CONFLICT',
    'R2_VERIFY_FAILED',
    'RELEASE_NOT_FOUND',
    'RELEASE_NOT_READY',
    'RELEASE_DISABLED',
    'RELEASE_ARCHIVED',
    'RELEASE_IN_USE',
    'RELEASE_NOTES_REQUIRED',
    'RECOVERY_ASSET_UNAVAILABLE',
    'FORMAL_RELEASE_REQUIRED',
    'IDEMPOTENCY_RESULT_EXPIRED',
  };

  static const Set<String> _terminalCodes = {
    'CLIENT_TOO_OLD',
    'HARDWARE_INCOMPATIBLE',
    'LAYOUT_INCOMPATIBLE',
    'BOOT_TOO_OLD',
    'PROTOCOL_UNSUPPORTED',
  };

  static const Set<String> _retryLaterCodes = {
    'CHANNEL_STOPPED',
    'BACKEND_UNAVAILABLE',
  };

  /// 解析失败响应体（`{errorCode, message, requestId, retryAfter?}`）。
  /// 未知 `errorCode` 同样构造成功（保留 requestId），但 [isUnknown] 为 true，
  /// 调用方按不可恢复处理；结构非法则抛 [OtaLatestParseException]。
  factory OtaHttpError.fromBody(
    Map<String, dynamic> body,
    int httpStatus, {
    String? requestIdHeader,
  }) {
    final errorCode = body['errorCode'];
    if (errorCode is! String || errorCode.isEmpty) {
      throw OtaLatestParseException('错误响应缺 errorCode');
    }
    final requestId = body['requestId'] is String
        ? body['requestId'] as String
        : requestIdHeader;
    return OtaHttpError(
      errorCode: errorCode,
      httpStatus: httpStatus,
      message: body['message'] is String ? body['message'] as String : null,
      requestId: requestId,
      retryAfterSeconds:
          body['retryAfter'] is int ? body['retryAfter'] as int : null,
      minAppVersionCode: body['minAppVersionCode'] is int
          ? body['minAppVersionCode'] as int
          : null,
      requiredValue: _firstIntOf(body, const [
        'requiredHardwareRevision',
        'requiredLayoutId',
        'minBootVersion',
        'minProtocolVersion',
      ]),
      actualValue: _firstIntOf(body, const [
        'actualHardwareRevision',
        'actualLayoutId',
        'bootVersion',
        'protocolVersion',
      ]),
    );
  }

  bool get isUnknown => !knownErrorCodes.contains(errorCode);

  static int? _firstIntOf(Map<String, dynamic> body, List<String> keys) {
    for (final key in keys) {
      if (body[key] is int) return body[key] as int;
    }
    return null;
  }
}

// ---- 解析辅助（fail-closed，无别名兜底） ----

/// 字段键与诊断标签分离：嵌套对象（asset）内的键不带前缀，
/// 错误消息带标签便于定位（PR02）。
String _requireString(Map<String, dynamic> m, String name, {String? label}) {
  final v = m[name];
  if (v is! String || v.isEmpty) {
    throw OtaLatestParseException('${label ?? name} 缺失或非字符串');
  }
  return v;
}

int _requireInt(Map<String, dynamic> m, String name, {String? label}) {
  final v = m[name];
  if (v is! int) {
    throw OtaLatestParseException('${label ?? name} 缺失或非整数');
  }
  return v;
}

bool _requireBool(Map<String, dynamic> m, String name) {
  final v = m[name];
  if (v is! bool) {
    throw OtaLatestParseException('$name 缺失或非布尔');
  }
  return v;
}

String? _optionalString(Map<String, dynamic> m, String name) {
  final v = m[name];
  if (v == null) return null;
  if (v is! String) {
    throw OtaLatestParseException('$name 存在但非字符串');
  }
  return v;
}

String _requireSha256Hex(Map<String, dynamic> m, String name, {String? label}) {
  final v = _requireString(m, name, label: label);
  _checkSha256Hex(v, label ?? name);
  return v;
}

void _checkSha256Hex(String value, String name) {
  final ok = value.length == 64 &&
      RegExp(r'^[0-9a-f]{64}$').hasMatch(value);
  if (!ok) {
    throw OtaLatestParseException('$name 非 64 位小写 hex: $value');
  }
}

/// App 侧 versionCode 域（OTA-XC-APP-VERSION-GATE：0..2100000000，
/// appVersionCode 与 release.minAppVersionCode 同族）。
void _checkAppVersionCode(int value, String name) {
  if (value < 0 || value > 2100000000) {
    throw OtaLatestParseException('$name 超范围: $value');
  }
}

/// 固件 versionCode 域（RC2-02）：release.versionCode 与
/// asset.baseVersionCode 是 MCU/ETU 头的 u32（二进制合同
/// target_vcode/base_vcode 为 uint32），不得套用 App 域上限。
void _checkFirmwareVersionCode(int value, String name) {
  if (value < 0 || value > 0xFFFFFFFF) {
    throw OtaLatestParseException('$name 超范围: $value');
  }
}

/// latest JSON 顶层对象解析入口（UTF-8 字节 → DTO）。
FirmwareLatestInfo parseLatestResponse(
  List<int> bytes, {
  String? expectedDeviceModel,
  String? expectedChannel,
}) {
  Map<String, dynamic> body;
  try {
    final decoded = jsonDecode(utf8.decode(bytes));
    if (decoded is! Map<String, dynamic>) {
      throw OtaLatestParseException('latest 响应不是 JSON object');
    }
    body = decoded;
  } on FormatException catch (e) {
    throw OtaLatestParseException('latest 响应 JSON 解析失败: ${e.message}');
  } on OtaLatestParseException {
    rethrow;
  }
  return FirmwareLatestInfo.parse(
    body,
    expectedDeviceModel: expectedDeviceModel,
    expectedChannel: expectedChannel,
  );
}
