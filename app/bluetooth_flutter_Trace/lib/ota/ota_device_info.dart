import 'dart:typed_data';

import 'ota_ble_codec.dart';

/// 设备 OTA 身份 DTO（冻结依据 docs/ota-cross-system-contracts.md
/// OTA-XC-FLUTTER-DEVICE-DTO + OTA-XC-DEVICE-MODEL）。
///
/// 数据唯一来源是 MCU GET_INFO 的 INFO payload；本类不做任何字段
/// 默认值或别名兜底，缺失/非法即构造失败（fail closed）。
class DeviceOtaInfo {
  DeviceOtaInfo._({
    required this.wireModel,
    required this.deviceModel,
    required this.hardwareRevision,
    required this.layoutId,
    required this.bootVersion,
    required this.currentVersionCode,
    required this.currentImageSha256Hex,
    required this.protocolVersion,
    required this.maxWindowSegments,
  });

  /// wire model 的 ASCII 值（NUL 前，如 `E-Track`；PR14：DTO 必含）。
  final String wireModel;
  /// 云端 query 使用的设备型号标识（显式映射表产物，禁止透传 wire 值）。
  final String deviceModel;
  final int hardwareRevision;
  final int layoutId;
  final int bootVersion;
  final int currentVersionCode;
  /// 当前镜像 raw SHA-256（64 位小写 hex）。
  final String currentImageSha256Hex;
  final int protocolVersion;
  final int maxWindowSegments;

  /// wire model 8B（含 NUL）精确值 `E-Track\0`（OTA-XC-DEVICE-MODEL）。
  static const List<int> wireModelETrack = [
    0x45, 0x2D, 0x54, 0x72, 0x61, 0x63, 0x6B, 0x00,
  ];

  /// wire model → deviceModel 显式映射表；只有表内条目可用。
  static const Map<String, String> modelMapping = {
    'E-Track': 'e-track-at32f435',
  };

  /// 支持的协议版本闭集合（当前仅 1）。
  static const int supportedProtocolVersion = 1;

  /// 从 INFO payload 解析并完成身份映射。
  ///
  /// 抛出 [OtaDeviceIdentityException]（错误码 `UNKNOWN_DEVICE_MODEL` 或
  /// `UNSUPPORTED_PROTOCOL`），携带原始 8 字节诊断摘要；不抛裸异常、
  /// 不吞错误，失败后调用方不得发出任何云端请求。
  factory DeviceOtaInfo.fromInfoPayload(List<int> payload) {
    final OtaInfoPayload info;
    try {
      info = OtaInfoPayload.parse(payload);
    } on FormatException catch (e) {
      throw OtaDeviceIdentityException(
        code: 'MALFORMED_INFO',
        message: e.message,
        wireModelHex: _wireModelHexOf(payload),
      );
    }
    return DeviceOtaInfo.fromInfoPayloadParsed(info);
  }

  /// 同 [fromInfoPayload]，但接受已解析的 [OtaInfoPayload]（重连复核复用）。
  factory DeviceOtaInfo.fromInfoPayloadParsed(OtaInfoPayload info) {
    final wire = info.model;
    // model 必须是合法 ASCIIZ：NUL 之前只能出现 ASCII 可打印字符且
    // 末字节必须是 NUL（8B 定长字段全满无 NUL 也按非法处理）。
    final nulIndex = wire.indexOf(0);
    if (nulIndex != wireModelETrack.length - 1) {
      throw OtaDeviceIdentityException(
        code: 'UNKNOWN_DEVICE_MODEL',
        message: 'wire model 非精确 E-Track\\0（NUL 位置 $nulIndex）',
        wireModelHex: modelHexLower(wire),
      );
    }
    for (var i = 0; i < nulIndex; i++) {
      final b = wire[i];
      if (b < 0x20 || b > 0x7E) {
        throw OtaDeviceIdentityException(
          code: 'UNKNOWN_DEVICE_MODEL',
          message: 'wire model 含非 ASCII 可打印字节 @${i}',
          wireModelHex: modelHexLower(wire),
        );
      }
    }
    final mapped = modelMapping[info.modelAscii];
    if (mapped == null) {
      throw OtaDeviceIdentityException(
        code: 'UNKNOWN_DEVICE_MODEL',
        message: 'wire model 未登记映射: "${info.modelAscii}"',
        wireModelHex: modelHexLower(wire),
      );
    }
    if (info.protocolVersion != supportedProtocolVersion) {
      throw OtaDeviceIdentityException(
        code: 'UNSUPPORTED_PROTOCOL',
        message: '协议版本不受支持: ${info.protocolVersion}',
        wireModelHex: modelHexLower(wire),
      );
    }
    return DeviceOtaInfo._(
      wireModel: info.modelAscii,
      deviceModel: mapped,
      hardwareRevision: info.hardwareRevision,
      layoutId: info.layoutId,
      bootVersion: info.bootVersion,
      currentVersionCode: info.currentVersionCode,
      currentImageSha256Hex: info.imageSha256Hex,
      protocolVersion: info.protocolVersion,
      maxWindowSegments: info.maxWindowSegments,
    );
  }

  /// 解析失败时尽量保留的 wire model 原始字节 hex（诊断用）。
  static String _wireModelHexOf(List<int> payload) {
    if (payload.length >= 8) {
      return modelHexLower(payload.sublist(0, 8));
    }
    return modelHexLower(payload);
  }
}

/// 设备身份解析失败的稳定领域错误。
class OtaDeviceIdentityException implements Exception {
  OtaDeviceIdentityException({
    required this.code,
    required this.message,
    required this.wireModelHex,
  });

  /// `UNKNOWN_DEVICE_MODEL` / `UNSUPPORTED_PROTOCOL` / `MALFORMED_INFO`。
  final String code;
  final String message;
  /// 原始 wire model 字节 hex（可能为截断前缀，仅供诊断）。
  final String wireModelHex;

  @override
  String toString() => 'OtaDeviceIdentityException($code): $message '
      '[wireModel=$wireModelHex]';
}

/// 重连身份复核：新 INFO 与升级会话开始时快照的身份必须逐字段一致，
/// 任何漂移都终止会话（不静默换设备续传）。
bool deviceIdentityMatches(DeviceOtaInfo a, DeviceOtaInfo b) {
  return a.deviceModel == b.deviceModel &&
      a.hardwareRevision == b.hardwareRevision &&
      a.layoutId == b.layoutId &&
      a.bootVersion == b.bootVersion &&
      a.currentVersionCode == b.currentVersionCode &&
      a.currentImageSha256Hex == b.currentImageSha256Hex &&
      a.protocolVersion == b.protocolVersion;
}

/// 升级完成后的硬件身份复核：与 [deviceIdentityMatches] 不同，版本号与
/// 镜像 SHA 此时已按预期变化（旧→目标），只比较不会因升级而变化的
/// 硬件字段；任何漂移都视为换设备（PR07）。
bool deviceHardwareMatches(DeviceOtaInfo a, DeviceOtaInfo b) {
  return a.deviceModel == b.deviceModel &&
      a.wireModel == b.wireModel &&
      a.hardwareRevision == b.hardwareRevision &&
      a.layoutId == b.layoutId &&
      a.bootVersion == b.bootVersion &&
      a.protocolVersion == b.protocolVersion;
}

/// INFO payload 组装辅助（测试/假设备使用）：按 §5.2.1 顺序小端填充。
Uint8List buildInfoPayload({
  required List<int> model,
  required int hardwareRevision,
  required int layoutId,
  required int bootVersion,
  required int currentVersionCode,
  required List<int> imageSha256,
  int protocolVersion = 1,
  int maxWindowSegments = 32,
}) {
  if (model.length != 8) {
    throw ArgumentError('model 必须为 8 字节');
  }
  if (imageSha256.length != 32) {
    throw ArgumentError('image_sha256 必须为 32 字节');
  }
  final payload = Uint8List(50);
  payload.setRange(0, 8, model);
  payload[8] = hardwareRevision & 0xFF;
  payload[9] = (hardwareRevision >> 8) & 0xFF;
  payload[10] = layoutId & 0xFF;
  payload[11] = bootVersion & 0xFF;
  payload[12] = currentVersionCode & 0xFF;
  payload[13] = (currentVersionCode >> 8) & 0xFF;
  payload[14] = (currentVersionCode >> 16) & 0xFF;
  payload[15] = (currentVersionCode >> 24) & 0xFF;
  payload.setRange(16, 48, imageSha256);
  payload[48] = protocolVersion & 0xFF;
  payload[49] = maxWindowSegments & 0xFF;
  return payload;
}
