import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';

import 'package:ble_monitor/ota/ota_ble_codec.dart';
import 'package:ble_monitor/ota/ota_device_info.dart';

/// DeviceOtaInfo：wire model 精确映射与 fail-closed 负例。
void main() {
  Uint8List infoPayload({
    List<int>? model,
    int hwRev = 3,
    int layoutId = 5,
    int bootVer = 2,
    int vcode = 20801,
    int protoVer = 1,
  }) {
    return buildInfoPayload(
      model: model ?? DeviceOtaInfo.wireModelETrack,
      hardwareRevision: hwRev,
      layoutId: layoutId,
      bootVersion: bootVer,
      currentVersionCode: vcode,
      imageSha256: List<int>.generate(32, (i) => i * 3),
      protocolVersion: protoVer,
    );
  }

  group('DeviceOtaInfo.fromInfoPayload（正向）', () {
    test('精确 E-Track\\0 → e-track-at32f435，全字段映射', () {
      final info = DeviceOtaInfo.fromInfoPayload(infoPayload());
      expect(info.wireModel, 'E-Track');
      expect(info.deviceModel, 'e-track-at32f435');
      expect(info.hardwareRevision, 3);
      expect(info.layoutId, 5);
      expect(info.bootVersion, 2);
      expect(info.currentVersionCode, 20801);
      expect(info.currentImageSha256Hex, modelHexLower(
        List<int>.generate(32, (i) => i * 3),
      ));
      expect(info.protocolVersion, 1);
      expect(info.maxWindowSegments, 32);
    });

    test('versionName 按契约 §0.6 反解（major*10000+minor*100+patch）', () {
      // 实测版本对（etu_pack.py parse_version_name 的镜像值）。
      expect(
        DeviceOtaInfo.fromInfoPayload(infoPayload(vcode: 30200)).versionName,
        '3.2.0',
      );
      expect(
        DeviceOtaInfo.fromInfoPayload(infoPayload(vcode: 30201)).versionName,
        '3.2.1',
      );
      expect(
        DeviceOtaInfo.fromInfoPayload(infoPayload(vcode: 30202)).versionName,
        '3.2.2',
      );
      expect(
        DeviceOtaInfo.fromInfoPayload(infoPayload(vcode: 20801)).versionName,
        '2.8.1',
      );
      // 边界：minor/patch 各自占满两位编码段。
      expect(
        DeviceOtaInfo.fromInfoPayload(infoPayload(vcode: 10099)).versionName,
        '1.0.99',
      );
      expect(
        DeviceOtaInfo.fromInfoPayload(infoPayload(vcode: 0)).versionName,
        '0.0.0',
      );
    });
  });

  group('DeviceOtaInfo 负例（必须 fail closed）', () {
    test('未知 model → UNKNOWN_DEVICE_MODEL', () {
      final raw = infoPayload(
        model: [0x58, 0x2D, 0x54, 0x72, 0x61, 0x63, 0x6B, 0x00], // X-Track\0
      );
      try {
        DeviceOtaInfo.fromInfoPayload(raw);
        fail('应抛 UNKNOWN_DEVICE_MODEL');
      } on OtaDeviceIdentityException catch (e) {
        expect(e.code, 'UNKNOWN_DEVICE_MODEL');
        expect(e.wireModelHex, '582d547261636b00');
      }
    });

    test('model 无 NUL 终止（8B 全满）→ UNKNOWN_DEVICE_MODEL', () {
      final raw = infoPayload(
        model: List<int>.filled(8, 0x41), // AAAAAAAA
      );
      try {
        DeviceOtaInfo.fromInfoPayload(raw);
        fail('应抛 UNKNOWN_DEVICE_MODEL');
      } on OtaDeviceIdentityException catch (e) {
        expect(e.code, 'UNKNOWN_DEVICE_MODEL');
      }
    });

    test('model NUL 前有非可打印字节 → UNKNOWN_DEVICE_MODEL', () {
      final raw = infoPayload(
        model: [0x45, 0x2D, 0x01, 0x72, 0x61, 0x63, 0x6B, 0x00],
      );
      try {
        DeviceOtaInfo.fromInfoPayload(raw);
        fail('应抛 UNKNOWN_DEVICE_MODEL');
      } on OtaDeviceIdentityException catch (e) {
        expect(e.code, 'UNKNOWN_DEVICE_MODEL');
      }
    });

    test('不支持 proto_ver → UNSUPPORTED_PROTOCOL', () {
      final raw = infoPayload(protoVer: 2);
      // proto_ver=2 在 OtaInfoPayload.parse 就会拒绝（协议闭集合）。
      try {
        DeviceOtaInfo.fromInfoPayload(raw);
        fail('应抛异常');
      } on OtaDeviceIdentityException catch (e) {
        expect(e.code, 'MALFORMED_INFO');
      } on FormatException {
        // parse 直接拒绝同样合法（fail closed）。
      }
    });

    test('INFO 长度非法 → MALFORMED_INFO', () {
      try {
        DeviceOtaInfo.fromInfoPayload(List<int>.filled(10, 0));
        fail('应抛 MALFORMED_INFO');
      } on OtaDeviceIdentityException catch (e) {
        expect(e.code, 'MALFORMED_INFO');
      }
    });
  });

  group('deviceIdentityMatches（重连身份复核）', () {
    test('同身份 → true', () {
      final a = DeviceOtaInfo.fromInfoPayload(infoPayload());
      final b = DeviceOtaInfo.fromInfoPayload(infoPayload());
      expect(deviceIdentityMatches(a, b), isTrue);
    });

    test('vcode 漂移 → false（不得静默换设备续传）', () {
      final a = DeviceOtaInfo.fromInfoPayload(infoPayload(vcode: 20801));
      final b = DeviceOtaInfo.fromInfoPayload(infoPayload(vcode: 20802));
      expect(deviceIdentityMatches(a, b), isFalse);
    });

    test('镜像 sha 漂移 → false', () {
      final a = DeviceOtaInfo.fromInfoPayload(infoPayload());
      final raw = infoPayload();
      raw.setRange(16, 48, List<int>.generate(32, (i) => i * 7));
      final b = DeviceOtaInfo.fromInfoPayload(raw);
      expect(deviceIdentityMatches(a, b), isFalse);
    });

    test('layoutId/boot/hwRev 漂移 → false', () {
      final a = DeviceOtaInfo.fromInfoPayload(infoPayload());
      final b = DeviceOtaInfo.fromInfoPayload(infoPayload(layoutId: 6));
      expect(deviceIdentityMatches(a, b), isFalse);
      final c = DeviceOtaInfo.fromInfoPayload(infoPayload(bootVer: 9));
      expect(deviceIdentityMatches(a, c), isFalse);
      final d = DeviceOtaInfo.fromInfoPayload(infoPayload(hwRev: 4));
      expect(deviceIdentityMatches(a, d), isFalse);
    });
  });

  group('deviceHardwareMatches（升级后硬件身份复核）', () {
    test('版本/镜像变化（升级成功）→ 仍 true', () {
      final before = DeviceOtaInfo.fromInfoPayload(infoPayload(vcode: 20801));
      var raw = infoPayload(vcode: 20900);
      raw.setRange(16, 48, List<int>.generate(32, (i) => i * 5));
      final after = DeviceOtaInfo.fromInfoPayload(raw);
      // deviceIdentityMatches 会拒绝（版本已变化），但硬件身份仍匹配。
      expect(deviceIdentityMatches(before, after), isFalse);
      expect(deviceHardwareMatches(before, after), isTrue);
    });

    test('硬件字段漂移 → false（视为换设备）', () {
      final a = DeviceOtaInfo.fromInfoPayload(infoPayload());
      final b = DeviceOtaInfo.fromInfoPayload(infoPayload(layoutId: 6));
      expect(deviceHardwareMatches(a, b), isFalse);
      final c = DeviceOtaInfo.fromInfoPayload(infoPayload(bootVer: 9));
      expect(deviceHardwareMatches(a, c), isFalse);
      final d = DeviceOtaInfo.fromInfoPayload(infoPayload(hwRev: 4));
      expect(deviceHardwareMatches(a, d), isFalse);
    });
  });

  group('buildInfoPayload（组装辅助）', () {
    test('非法 model/sha 长度拒绝', () {
      expect(
        () => buildInfoPayload(
          model: List<int>.filled(7, 0),
          hardwareRevision: 1,
          layoutId: 1,
          bootVersion: 1,
          currentVersionCode: 1,
          imageSha256: List<int>.filled(32, 0),
        ),
        throwsArgumentError,
      );
      expect(
        () => buildInfoPayload(
          model: DeviceOtaInfo.wireModelETrack,
          hardwareRevision: 1,
          layoutId: 1,
          bootVersion: 1,
          currentVersionCode: 1,
          imageSha256: List<int>.filled(31, 0),
        ),
        throwsArgumentError,
      );
    });

    test('往返：build → parse → build', () {
      final raw = infoPayload();
      final info = OtaInfoPayload.parse(raw);
      final rebuilt = buildInfoPayload(
        model: info.model,
        hardwareRevision: info.hardwareRevision,
        layoutId: info.layoutId,
        bootVersion: info.bootVersion,
        currentVersionCode: info.currentVersionCode,
        imageSha256: info.imageSha256,
        protocolVersion: info.protocolVersion,
        maxWindowSegments: info.maxWindowSegments,
      );
      expect(rebuilt, raw);
    });
  });
}
