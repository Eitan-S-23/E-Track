import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:crypto/crypto.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ble_monitor/ota/ota_experiment_config.dart';
import 'package:ble_monitor/services/bluetooth_service.dart';

const target = 'AA:BB:CC:DD:EE:FF';

Map<String, Object?> profile({int baud = 115200, bool reuse = true, bool without = true}) => {
  'schema': 1, 'runId': 'b$baud-001', 'target': target, 'requestedBaud': baud,
  'reuseGatt': reuse, 'withoutResponse': without,
  'firmwareLatestUrl': 'https://fixture.trycloudflare.com/api/public/firmware/latest',
  'packageBytes': 284643, 'packageSha256': 'a' * 64,
  'currentVersionCode': 30208, 'currentImageSha256': 'b' * 64,
  'targetVersionCode': 30209, 'targetImageSha256': 'c' * 64,
};

Map<String, Object?> upgradeInput() => {
  'deviceAddress': target, 'packageBytes': 284643, 'packageSha256': 'a' * 64,
  'currentVersionCode': 30208, 'currentImageSha256': 'b' * 64,
  'targetVersionCode': 30209, 'targetImageSha256': 'c' * 64,
  'appLifecycle': 'resumed',
};

OtaExperimentConfig parse(Map<String, Object?> value) =>
    OtaExperimentConfig.parse(jsonEncode(value), expectedTarget: target);

void main() {
  for (final baud in [115200, 460800, 921600]) {
    test('accepts requested $baud without claiming actual hardware baud', () {
      final text = '${jsonEncode(profile(baud: baud))}\n';
      final config = OtaExperimentConfig.parse(text, expectedTarget: target);
      expect(config.requestedBaud, baud);
      expect(config.sourceSha256, sha256.convert(utf8.encode(text)).toString());
      final observation = jsonDecode(config.observationLine.substring('OTA_EXPERIMENT '.length));
      expect(observation['requestedBaud'], baud);
      expect(observation.containsKey('actualBaud'), isFalse);
      expect(config.observationLine, isNot(contains('https://')));
    });
  }

  test('rejects unknown, missing, malformed and nonintegral fields', () {
    final values = <Map<String, Object?>>[
      {...profile(), 'extra': true},
      {...profile()}..remove('packageSha256'),
      {...profile(), 'schema': 1.0},
      {...profile(), 'requestedBaud': 230400},
      {...profile(), 'requestedBaud': 921600.0},
      {...profile(), 'requestedBaud': '921600'},
      {...profile(), 'reuseGatt': 1},
      {...profile(), 'withoutResponse': 'true'},
      {...profile(), 'target': 'AA:00:00:00:00:00'},
      {...profile(), 'runId': '../escape'},
      {...profile(), 'packageBytes': 63},
      {...profile(), 'packageBytes': 0x100000000},
      {...profile(), 'packageSha256': 'A' * 64},
      {...profile(), 'targetVersionCode': 30208},
      {...profile(), 'targetVersionCode': 2100000001},
    ];
    for (final value in values) {
      expect(() => parse(value), throwsFormatException);
    }
    for (final text in ['[]', 'null', '{', ' ' * 8193]) {
      expect(() => OtaExperimentConfig.parse(text, expectedTarget: target), throwsFormatException);
    }
  });

  test('rejects credentials, queries, fragments and wrong endpoint shapes', () {
    for (final url in [
      'http://fixture.example/api/public/firmware/latest',
      'https://user:password@fixture.example/api/public/firmware/latest',
      'https://fixture.example/api/public/firmware/latest?token=secret',
      'https://fixture.example/api/public/firmware/latest#secret',
      'https://fixture.example:444/api/public/firmware/latest',
      'https://fixture.example/other',
      'https://localhost/api/public/firmware/latest',
      'https://127.0.0.1/api/public/firmware/latest',
    ]) {
      expect(() => parse({...profile(), 'firmwareLatestUrl': url}), throwsFormatException);
    }
  });

  test('preserves actual latest query fields while selecting the runtime endpoint', () {
    final config = parse(profile());
    final original = Uri.https('previous.example', '/api/public/firmware/latest', {
      'deviceModel': 'e-track-at32f435', 'currentVersionCode': '30208',
      'currentImageSha': 'b' * 64, 'hardwareRevision': '1', 'layoutId': '2',
      'bootVersion': '1', 'protocolVersion': '1', 'appVersionCode': '53',
      'channel': 'beta',
    });
    final uri = config.latestUri(original, versionCode: 30208, imageSha256: 'b' * 64);
    expect(uri.host, 'fixture.trycloudflare.com');
    expect(uri.queryParameters, original.queryParameters);
    expect(() => config.latestUri(original, versionCode: 30207, imageSha256: 'b' * 64), throwsStateError);
    expect(() => config.latestUri(original, versionCode: 30208, imageSha256: 'd' * 64), throwsStateError);
  });

  test('every bound package/device identity must match before upgrade', () {
    final config = parse(profile());
    final input = upgradeInput();
    expect(config.matchesUpgrade(input), isTrue);
    for (final key in input.keys.where((key) => key != 'appLifecycle')) {
      expect(config.matchesUpgrade({...input, key: null}), isFalse, reason: key);
    }
    expect(config.matchesUpgrade({...input, 'deviceAddress': 123}), isFalse);
    expect(() => config.requireDevice('AA:00:00:00:00:00'), throwsStateError);
    config.requireDevice(target.toLowerCase());
  });

  test('disabled builds never read a configuration file', () async {
    final runtime = OtaExperimentRuntime(enabled: false);
    var reads = 0;
    await runtime.initialize(expectedTarget: '', readConfig: () async { reads++; throw StateError('unused'); });
    expect(reads, 0);
    expect(runtime.ready, isTrue);
    expect(runtime.requireForOta(), isNull);
  });

  test('missing or invalid configuration fails closed without changing defaults', () async {
    final runtime = OtaExperimentRuntime(enabled: true);
    final service = BluetoothService(experiment: runtime);
    await expectLater(service.findExactOtaCharacteristicsByAddress(target), throwsStateError);
    await runtime.initialize(expectedTarget: target, readConfig: () async => '{}');
    expect(runtime.ready, isFalse);
    expect(runtime.error, isNotNull);
    await expectLater(service.writeOtaCharacteristicByAddress(target, 'fff0', 'fff2', [1]), throwsStateError);
  });

  test('one initialized profile is immutable even during concurrent initialize calls', () async {
    final runtime = OtaExperimentRuntime(enabled: true);
    final pending = Completer<String>();
    var reads = 0;
    final first = runtime.initialize(expectedTarget: target, readConfig: () { reads++; return pending.future; });
    final second = runtime.initialize(expectedTarget: 'other', readConfig: () async { reads++; return '{}'; });
    pending.complete(jsonEncode(profile(baud: 921600)));
    await Future.wait([first, second]);
    await runtime.initialize(expectedTarget: target, readConfig: () async { reads++; return jsonEncode(profile()); });
    expect(reads, 1);
    expect(runtime.requireForOta()!.requestedBaud, 921600);
  });

  for (final reuse in [false, true]) {
    for (final without in [false, true]) {
      test('same App selects reuse=$reuse without=$without from its immutable profile', () async {
        final runtime = OtaExperimentRuntime(enabled: true);
        await runtime.initialize(expectedTarget: target,
            readConfig: () async => jsonEncode(profile(reuse: reuse, without: without)));
        final service = BluetoothService(experiment: runtime,
            reuseOtaCharacteristics: !reuse, preferOtaWithoutResponse: !without);
        expect(service.reuseOtaCharacteristics, reuse);
        expect(service.preferOtaWithoutResponse, without);
        await expectLater(service.findExactOtaCharacteristicsByAddress('00:00:00:00:00:00'), throwsStateError);
      });
    }
  }

  test('actual bounded file loader handles a short file, rejects oversized files and never reloads', () async {
    final parent = Directory('${Directory.current.path}/.dart_tool/p34-experiment-tests');
    await parent.create(recursive: true);
    final root = await parent.createTemp('case-');
    try {
      final file = File('${root.path}/p34-experiment.json');
      await file.writeAsString(jsonEncode(profile(baud: 460800)));
      final first = OtaExperimentRuntime(enabled: true);
      await first.initialize(expectedTarget: target, directoryProvider: () async => root);
      expect(first.requireForOta()!.requestedBaud, 460800);
      await file.writeAsString(' ' * 8193);
      await first.initialize(expectedTarget: target, directoryProvider: () async => root);
      expect(first.requireForOta()!.requestedBaud, 460800);
      final second = OtaExperimentRuntime(enabled: true);
      await second.initialize(expectedTarget: target, directoryProvider: () async => root);
      expect(second.ready, isFalse);
      expect(second.requireForOta, throwsStateError);
    } finally {
      await root.delete(recursive: true);
    }
  });
}
