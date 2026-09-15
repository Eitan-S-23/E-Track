import 'package:flutter_test/flutter_test.dart';

import 'package:ble_monitor/config/share_links.dart';

/// latest query 构造（OTA-XC-CLOUD-QUERY-MAPPING）：typed 全参数与校验。
void main() {
  // RC3-01：String 乘法不是 const 可表达式，必须用 final。
  const validSha = '0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef';

  group('ShareLinks.firmwareLatestQuery（正向）', () {
    test('全参数生成 10 个 query 项', () {
      final query = ShareLinks.firmwareLatestQuery(
        deviceModel: 'e-track-at32f435',
        currentVersionCode: 20801,
        currentImageSha: validSha,
        hardwareRevision: 3,
        layoutId: 5,
        bootVersion: 2,
        protocolVersion: 1,
        appVersionCode: 60,
      );
      expect(query, {
        'appId': 'trace',
        'deviceModel': 'e-track-at32f435',
        'channel': 'stable',
        'currentVersionCode': '20801',
        'currentImageSha': validSha,
        'hardwareRevision': '3',
        'layoutId': '5',
        'bootVersion': '2',
        'protocolVersion': '1',
        'appVersionCode': '60',
      });
    });

    test('channel 覆盖', () {
      final query = ShareLinks.firmwareLatestQuery(
        deviceModel: 'e-track-at32f435',
        currentVersionCode: 1,
        currentImageSha: validSha,
        hardwareRevision: 0,
        layoutId: 0,
        bootVersion: 0,
        protocolVersion: 1,
        appVersionCode: 0,
        channel: 'beta',
      );
      expect(query['channel'], 'beta');
    });
  });

  group('ShareLinks.firmwareLatestQuery（负例）', () {
    void expectRejected({
      String deviceModel = 'e-track-at32f435',
      int currentVersionCode = 1,
      String currentImageSha = validSha,
      int hardwareRevision = 0,
      int layoutId = 0,
      int bootVersion = 0,
      int protocolVersion = 1,
      int appVersionCode = 0,
    }) {
      expect(
        () => ShareLinks.firmwareLatestQuery(
          deviceModel: deviceModel,
          currentVersionCode: currentVersionCode,
          currentImageSha: currentImageSha,
          hardwareRevision: hardwareRevision,
          layoutId: layoutId,
          bootVersion: bootVersion,
          protocolVersion: protocolVersion,
          appVersionCode: appVersionCode,
        ),
        throwsArgumentError,
      );
    }

    test('deviceModel 为空拒绝', () {
      expectRejected(deviceModel: '');
    });

    test('currentVersionCode 负数拒绝', () {
      expectRejected(currentVersionCode: -1);
    });

    test('currentImageSha 大写/短/长/非 hex 拒绝', () {
      expectRejected(currentImageSha: 'A' * 64);
      expectRejected(currentImageSha: 'a' * 63);
      expectRejected(currentImageSha: 'a' * 65);
      expectRejected(currentImageSha: 'z' * 64);
    });

    test('hardwareRevision 负数拒绝', () {
      expectRejected(hardwareRevision: -1);
    });

    test('layoutId/bootVersion/protocolVersion 超 0..255 拒绝', () {
      expectRejected(layoutId: 256);
      expectRejected(layoutId: -1);
      expectRejected(bootVersion: 256);
      expectRejected(bootVersion: -1);
      expectRejected(protocolVersion: 256);
      expectRejected(protocolVersion: -1);
    });

    test('appVersionCode 超 0..2100000000 拒绝', () {
      expectRejected(appVersionCode: -1);
      expectRejected(appVersionCode: 2100000001);
    });

    test('channel 非 stable/beta 拒绝', () {
      for (final bad in ['nightly', '', 'STABLE', 'stable ']) {
        expect(
          () => ShareLinks.firmwareLatestQuery(
            deviceModel: 'e-track-at32f435',
            currentVersionCode: 1,
            currentImageSha: validSha,
            hardwareRevision: 0,
            layoutId: 0,
            bootVersion: 0,
            protocolVersion: 1,
            appVersionCode: 0,
            channel: bad,
          ),
          throwsArgumentError,
          reason: 'channel=$bad 必须拒绝',
        );
      }
    });
  });
}
