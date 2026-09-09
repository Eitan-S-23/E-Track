import 'package:flutter_test/flutter_test.dart';

import 'package:ble_monitor/ota/ota_firmware_latest.dart';

/// 默认 base 镜像摘要（64 个 'a'）。顶层 const 字面量：默认参数必须
/// 是编译期常量，`'a' * 64` 不是 const 表达式（RC3-01②）。
const String _kDefaultBaseSha =
    'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa';

/// latest schema v2 typed 解析：正反例与终止态模型。
void main() {
  Map<String, dynamic> fullBody({
    String kind = 'patch',
    Object? baseVersionCode = 20800,
    Object? baseImageSha256 = _kDefaultBaseSha,
    String? fileName,
  }) {
    // fileName 必须与 kind 后缀一致（ASSET-NAMING）。
    final effectiveFileName = fileName ??
        (kind == 'full'
            ? 'e-track-at32f435-v2.8.1-full.etu'
            : 'e-track-at32f435-v2.8.0-to-v2.8.1-patch.etu');
    return {
      'schemaVersion': 2,
      'requestId': 'req-1',
      'updateAvailable': true,
      'appId': 'trace',
      'deviceModel': 'e-track-at32f435',
      'channel': 'stable',
      'releaseId': 'rel-1',
      'versionName': '2.8.1',
      'versionCode': 20801,
      'releaseTag': 'mcu-e-track-at32f435-v2.8.1',
      'releaseNotes': '修复',
      'targetImageSha256': 'b' * 64,
      'targetHardware': 'AT32F435RGT7',
      'transport': 'ble',
      'minAppVersionCode': 0,
      'asset': {
        'assetId': 'asset-1',
        'kind': kind,
        'fileName': effectiveFileName,
        'sha256': 'c' * 64,
        'sizeBytes': 12345,
        'baseVersionCode': baseVersionCode,
        'baseImageSha256': baseImageSha256,
        'downloadUrl': 'https://example.com/signed',
        'expiresAt': 1780000000,
      },
    };
  }

  /// false 分支（NO_UPDATE/CHANNEL_STOPPED）合法 body：合同精简体
  /// （RC2-02：只含 schemaVersion/requestId/updateAvailable/errorCode，
  /// 可选 maintenanceMessage；不含 appId/deviceModel/channel 回显）。
  Map<String, dynamic> noUpdateBody({
    String errorCode = 'NO_UPDATE',
    String? maintenanceMessage,
    bool withErrorCode = true,
  }) {
    return {
      'schemaVersion': 2,
      'requestId': 'req-n',
      'updateAvailable': false,
      if (withErrorCode) 'errorCode': errorCode,
      if (maintenanceMessage != null)
        'maintenanceMessage': maintenanceMessage,
    };
  }

  group('FirmwareLatestInfo.parse（正向）', () {
    test('完整 patch 响应：全字段', () {
      final info = FirmwareLatestInfo.parse(fullBody());
      expect(info.updateAvailable, isTrue);
      expect(info.hasUpdate, isTrue);
      expect(info.requestId, 'req-1');
      expect(info.releaseId, 'rel-1');
      expect(info.versionName, '2.8.1');
      expect(info.versionCode, 20801);
      expect(info.releaseTag, 'mcu-e-track-at32f435-v2.8.1');
      expect(info.targetImageSha256, 'b' * 64);
      expect(info.minAppVersionCode, 0);
      final asset = info.asset!;
      expect(asset.assetId, 'asset-1');
      expect(asset.kind, 'patch');
      expect(asset.isPatch, isTrue);
      expect(asset.sha256, 'c' * 64);
      expect(asset.sizeBytes, 12345);
      expect(asset.baseVersionCode, 20800);
      expect(asset.baseImageSha256, 'a' * 64);
      expect(asset.downloadUrl, 'https://example.com/signed');
      expect(asset.expiresAt, 1780000000);
    });

    test('full 资产：baseVersionCode=0、baseImageSha256=null', () {
      final info = FirmwareLatestInfo.parse(fullBody(
        kind: 'full',
        baseVersionCode: 0,
        baseImageSha256: null,
      ));
      expect(info.asset!.kind, 'full');
      expect(info.asset!.isPatch, isFalse);
      expect(info.asset!.baseVersionCode, 0);
      expect(info.asset!.baseImageSha256, isNull);
    });

    test('NO_UPDATE：HTTP 200 业务结果（合同精简体，无回显字段）', () {
      final info = FirmwareLatestInfo.parse(noUpdateBody());
      expect(info.updateAvailable, isFalse);
      expect(info.errorCode, 'NO_UPDATE');
      expect(info.hasUpdate, isFalse);
    });

    test('CHANNEL_STOPPED：可附维护消息', () {
      final info = FirmwareLatestInfo.parse(noUpdateBody(
        errorCode: 'CHANNEL_STOPPED',
        maintenanceMessage: '维护中',
      ));
      expect(info.errorCode, 'CHANNEL_STOPPED');
      expect(info.maintenanceMessage, '维护中');
    });

    test('固件 versionCode u32 上界 4294967295 通过（RC2-02）', () {
      final body = fullBody();
      body['versionCode'] = 4294967295;
      final info = FirmwareLatestInfo.parse(body);
      expect(info.versionCode, 4294967295);
    });

    test('asset.baseVersionCode u32 上界 4294967295 通过（RC2-02）', () {
      final body = fullBody();
      (body['asset'] as Map<String, dynamic>)['baseVersionCode'] = 4294967295;
      final info = FirmwareLatestInfo.parse(body);
      expect(info.asset!.baseVersionCode, 4294967295);
    });

    test('未知可选字段被忽略（同 major 兼容）', () {
      final body = fullBody();
      body['newOptionalField'] = 'whatever';
      final info = FirmwareLatestInfo.parse(body);
      expect(info.hasUpdate, isTrue);
    });
  });

  group('FirmwareLatestInfo.parse（负例 fail closed）', () {
    test('未知 schema major 拒绝', () {
      final body = fullBody();
      body['schemaVersion'] = 3;
      expect(() => FirmwareLatestInfo.parse(body),
          throwsA(isA<OtaLatestParseException>()));
    });

    test('updateAvailable=true 但缺 required 字段拒绝', () {
      for (final missing in [
        'releaseId', 'versionName', 'versionCode', 'releaseTag',
        'targetImageSha256', 'minAppVersionCode', 'asset',
      ]) {
        final body = fullBody();
        body.remove(missing);
        expect(
          () => FirmwareLatestInfo.parse(body),
          throwsA(isA<OtaLatestParseException>()),
          reason: '缺少 $missing 必须拒绝',
        );
      }
    });

    test('updateAvailable=false 但 errorCode 未知拒绝', () {
      expect(
        () => FirmwareLatestInfo.parse(
            noUpdateBody(errorCode: 'SOME_RANDOM_CODE')),
        throwsA(isA<OtaLatestParseException>()),
      );
    });

    test('recovery 资产拒绝（公开 latest 不得返回）', () {
      expect(
        () => FirmwareLatestInfo.parse(fullBody(kind: 'recovery')),
        throwsA(isA<OtaLatestParseException>()),
      );
    });

    test('未知 asset.kind 拒绝', () {
      expect(
        () => FirmwareLatestInfo.parse(fullBody(kind: 'delta')),
        throwsA(isA<OtaLatestParseException>()),
      );
    });

    test('full 但 baseVersionCode != 0 拒绝', () {
      expect(
        () => FirmwareLatestInfo.parse(fullBody(
          kind: 'full',
          baseVersionCode: 20800,
          baseImageSha256: null,
        )),
        throwsA(isA<OtaLatestParseException>()),
      );
    });

    test('patch 但 baseImageSha256 缺失拒绝', () {
      expect(
        () => FirmwareLatestInfo.parse(fullBody(
          kind: 'patch',
          baseVersionCode: 20800,
          baseImageSha256: null,
        )),
        throwsA(isA<OtaLatestParseException>()),
      );
    });

    test('sha256 非法（大写/短）拒绝', () {
      final body = fullBody();
      (body['asset'] as Map<String, dynamic>)['sha256'] = 'C' * 64;
      expect(() => FirmwareLatestInfo.parse(body),
          throwsA(isA<OtaLatestParseException>()));
      final body2 = fullBody();
      (body2['asset'] as Map<String, dynamic>)['sha256'] = 'c' * 63;
      expect(() => FirmwareLatestInfo.parse(body2),
          throwsA(isA<OtaLatestParseException>()));
    });

    test('sizeBytes 非正拒绝', () {
      final body = fullBody();
      (body['asset'] as Map<String, dynamic>)['sizeBytes'] = 0;
      expect(() => FirmwareLatestInfo.parse(body),
          throwsA(isA<OtaLatestParseException>()));
    });

    test('minAppVersionCode 超范围拒绝', () {
      final body = fullBody();
      body['minAppVersionCode'] = 2100000001;
      expect(() => FirmwareLatestInfo.parse(body),
          throwsA(isA<OtaLatestParseException>()));
    });
  });

  group('FirmwareLatestInfo.parse（PR14 回显与资产校验负例）', () {
    test('updateAvailable=false 缺 errorCode 键拒绝', () {
      expect(
        () => FirmwareLatestInfo.parse(noUpdateBody(withErrorCode: false)),
        throwsA(isA<OtaLatestParseException>()),
      );
    });

    test('updateAvailable=true 携带 errorCode 拒绝', () {
      final body = fullBody();
      body['errorCode'] = 'NO_UPDATE';
      expect(() => FirmwareLatestInfo.parse(body),
          throwsA(isA<OtaLatestParseException>()));
    });

    test('appId 回显不符拒绝', () {
      final body = fullBody();
      body['appId'] = 'other-app';
      expect(() => FirmwareLatestInfo.parse(body),
          throwsA(isA<OtaLatestParseException>()));
    });

    test('deviceModel 回显不符拒绝（expectedDeviceModel）', () {
      final body = fullBody();
      body['deviceModel'] = 'someone-else-device';
      expect(
        () => FirmwareLatestInfo.parse(body,
            expectedDeviceModel: 'e-track-at32f435'),
        throwsA(isA<OtaLatestParseException>()),
      );
    });

    test('deviceModel 回显一致通过（expectedDeviceModel）', () {
      final info = FirmwareLatestInfo.parse(fullBody(),
          expectedDeviceModel: 'e-track-at32f435');
      expect(info.hasUpdate, isTrue);
    });

    test('channel 非法拒绝', () {
      final body = fullBody();
      body['channel'] = 'nightly';
      expect(() => FirmwareLatestInfo.parse(body),
          throwsA(isA<OtaLatestParseException>()));
    });

    test('transport 非 ble 拒绝', () {
      final body = fullBody();
      body['transport'] = 'usb';
      expect(() => FirmwareLatestInfo.parse(body),
          throwsA(isA<OtaLatestParseException>()));
    });

    test('versionCode 超 u32（4294967296）拒绝（RC2-02：固件域非 App 域）',
        () {
      final body = fullBody();
      body['versionCode'] = 4294967296;
      expect(() => FirmwareLatestInfo.parse(body),
          throwsA(isA<OtaLatestParseException>()));
    });

    test('channel 回显不符拒绝（expectedChannel）', () {
      // body 的 channel 是 stable；请求侧期望 beta。
      expect(
        () => FirmwareLatestInfo.parse(fullBody(), expectedChannel: 'beta'),
        throwsA(isA<OtaLatestParseException>()),
      );
    });

    test('channel 回显一致通过（expectedChannel）', () {
      final info =
          FirmwareLatestInfo.parse(fullBody(), expectedChannel: 'stable');
      expect(info.hasUpdate, isTrue);
    });

    test('targetHardware 缺失拒绝', () {
      final body = fullBody();
      body.remove('targetHardware');
      expect(() => FirmwareLatestInfo.parse(body),
          throwsA(isA<OtaLatestParseException>()));
    });

    test('downloadUrl 非 https（http）拒绝（RC2-11）', () {
      final body = fullBody();
      (body['asset'] as Map<String, dynamic>)['downloadUrl'] =
          'http://example.com/signed';
      expect(() => FirmwareLatestInfo.parse(body),
          throwsA(isA<OtaLatestParseException>()));
    });

    test('downloadUrl 非 http(s) 拒绝', () {
      final body = fullBody();
      (body['asset'] as Map<String, dynamic>)['downloadUrl'] =
          'ftp://example.com/signed';
      expect(() => FirmwareLatestInfo.parse(body),
          throwsA(isA<OtaLatestParseException>()));
    });

    test('downloadUrl 无 host 拒绝', () {
      final body = fullBody();
      (body['asset'] as Map<String, dynamic>)['downloadUrl'] =
          'https:///signed';
      expect(() => FirmwareLatestInfo.parse(body),
          throwsA(isA<OtaLatestParseException>()));
    });

    test('fileName 含非法字符拒绝', () {
      final body = fullBody(fileName: 'bad name!.etu');
      expect(() => FirmwareLatestInfo.parse(body),
          throwsA(isA<OtaLatestParseException>()));
    });

    test('fileName 超长（>128）拒绝', () {
      final body =
          fullBody(fileName: '${'a' * 120}-patch.etu');
      expect(() => FirmwareLatestInfo.parse(body),
          throwsA(isA<OtaLatestParseException>()));
    });

    test('fileName 与 kind 后缀不符拒绝', () {
      final body = fullBody(kind: 'full', fileName: 'x-v1-patch.etu');
      expect(() => FirmwareLatestInfo.parse(body),
          throwsA(isA<OtaLatestParseException>()));
    });

    test('sizeBytes 超 OTA_ETU_MAX_LENGTH(0x180000) 拒绝', () {
      final body = fullBody();
      (body['asset'] as Map<String, dynamic>)['sizeBytes'] =
          OtaFirmwareAsset.maxPackageBytes + 1;
      expect(() => FirmwareLatestInfo.parse(body),
          throwsA(isA<OtaLatestParseException>()));
    });

    test('expiresAt 非正拒绝', () {
      final body = fullBody();
      (body['asset'] as Map<String, dynamic>)['expiresAt'] = 0;
      expect(() => FirmwareLatestInfo.parse(body),
          throwsA(isA<OtaLatestParseException>()));
    });

    test('full 缺 baseImageSha256 键拒绝（与显式 null 区分）', () {
      final body = fullBody(kind: 'full', baseVersionCode: 0);
      // 键完全缺失（区别于显式 null）：必须拒绝。
      (body['asset'] as Map<String, dynamic>).remove('baseImageSha256');
      expect(() => FirmwareLatestInfo.parse(body),
          throwsA(isA<OtaLatestParseException>()));
    });

    test('full 带 baseImageSha256 非 null 值拒绝', () {
      final body = fullBody(
        kind: 'full',
        baseVersionCode: 0,
        baseImageSha256: 'a' * 64,
      );
      expect(() => FirmwareLatestInfo.parse(body),
          throwsA(isA<OtaLatestParseException>()));
    });

    test('asset.baseVersionCode 超范围拒绝', () {
      final body = fullBody();
      (body['asset'] as Map<String, dynamic>)['baseVersionCode'] = -1;
      expect(() => FirmwareLatestInfo.parse(body),
          throwsA(isA<OtaLatestParseException>()));
    });
  });

  group('OtaHttpError', () {
    test('CLIENT_TOO_OLD 终止且携带门槛', () {
      final err = OtaHttpError.fromBody({
        'errorCode': 'CLIENT_TOO_OLD',
        'requestId': 'r1',
        'minAppVersionCode': 60,
      }, 426);
      expect(err.isTerminal, isTrue);
      expect(err.minAppVersionCode, 60);
      expect(err.isAutoRetryable, isFalse);
    });

    test('兼容 409 终止且区分维度', () {
      for (final code in [
        'HARDWARE_INCOMPATIBLE', 'LAYOUT_INCOMPATIBLE',
        'BOOT_TOO_OLD', 'PROTOCOL_UNSUPPORTED',
      ]) {
        final err = OtaHttpError.fromBody({
          'errorCode': code,
          'requestId': 'r',
        }, 409);
        expect(err.isTerminal, isTrue, reason: code);
      }
    });

    test('未知 errorCode：isUnknown，不可降级', () {
      final err = OtaHttpError.fromBody({
        'errorCode': 'TOTALLY_NEW',
        'requestId': 'r',
      }, 500);
      expect(err.isUnknown, isTrue);
      expect(err.isTerminal, isFalse);
    });

    test('RATE_LIMITED / BACKEND_UNAVAILABLE 可自动重试', () {
      final rate = OtaHttpError.fromBody({
        'errorCode': 'RATE_LIMITED',
        'retryAfter': 5,
      }, 429);
      expect(rate.isAutoRetryable, isTrue);
      expect(rate.retryAfterSeconds, 5);
      final backend = OtaHttpError.fromBody({
        'errorCode': 'BACKEND_UNAVAILABLE',
      }, 503);
      expect(backend.isAutoRetryable, isTrue);
      expect(backend.isRetryableLater, isTrue);
    });

    test('缺 errorCode 拒绝', () {
      expect(
        () => OtaHttpError.fromBody({'message': 'x'}, 500),
        throwsA(isA<OtaLatestParseException>()),
      );
    });
  });

  group('parseLatestResponse', () {
    test('UTF-8 字节 → DTO', () {
      final json = '{"schemaVersion":2,"requestId":"r","appId":"trace",'
          '"deviceModel":"e-track-at32f435","channel":"stable",'
          '"updateAvailable":false,"errorCode":"NO_UPDATE"}';
      final info = parseLatestResponse(json.codeUnits);
      expect(info.errorCode, 'NO_UPDATE');
    });

    test('非法 JSON 拒绝', () {
      expect(() => parseLatestResponse('not json'.codeUnits),
          throwsA(isA<OtaLatestParseException>()));
    });
  });
}
