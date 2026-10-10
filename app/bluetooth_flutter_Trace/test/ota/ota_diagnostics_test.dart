import 'dart:convert';
import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ble_monitor/ota/ota_diagnostics.dart';
import 'package:ble_monitor/ota/ota_link_stats.dart';
import 'package:ble_monitor/ota/ota_mono.dart';
import 'package:ble_monitor/ota/ota_experiment_config.dart';

void main() {
  late Directory root;
  late OtaDiagnostics diagnostics;
  late DebugPrintCallback oldPrint;
  setUp(() async {
    final parent = Directory('${Directory.current.path}/.dart_tool/p34-diagnostics-tests');
    await parent.create(recursive: true);
    root = await parent.createTemp('case-');
    diagnostics = OtaDiagnostics();
    oldPrint = debugPrint;
    debugPrint = (String? message, {int? wrapWidth}) {};
  });
  tearDown(() async {
    await diagnostics.close();
    debugPrint = oldPrint;
    await root.delete(recursive: true);
  });

  Future<void> initialize() => diagnostics.initialize(enabled: true,
    target: 'AA:BB:CC:DD:EE:FF', sentinel: 'OTAOBS0123456789abcdef01234567',
    directoryProvider: () async => root);
  Map<String, Object?> input() => {
    'packageSha256': 'a' * 64, 'packageBytes': 284466,
    'currentVersionCode': 30206, 'currentImageSha256': 'b' * 64,
    'targetVersionCode': 30207, 'targetImageSha256': 'c' * 64,
    'deviceAddress': 'AA:BB:CC:DD:EE:FF', 'appLifecycle': 'resumed',
  };

  test('disabled route never requests a filesystem directory', () async {
    var directoryCalls = 0;
    await diagnostics.initialize(enabled: false, target: '', sentinel: '',
      directoryProvider: () async { directoryCalls++; return root; });
    expect(await diagnostics.beginUpgrade(input()), isTrue);
    await diagnostics.finishUpgrade(completed: true);
    expect(directoryCalls, 0);
    expect(await root.list().length, 0);
    expect(diagnostics.status.value.enabled, isFalse);
  });

  test('actual stats and MONO producers persist without debugPrint', () async {
    await initialize();
    await OtaDiagnostics.withInstance(diagnostics, () async {
      final stats = OtaLinkStats(label: 'query', clockUs: () => 40);
      stats.recordGetInfo(durationUs: 20);
      stats.emitSummary();
      otaMonoLog('MONO_FIXTURE');
      final file = await diagnostics.exportSnapshot();
      final text = await file.readAsString();
      expect(text, contains('OTA_LINK_SAMPLE label=query kind=get_info'));
      expect(text, contains('OTA_LINK_STATS '));
      expect(text, contains('OTA_MONO MONO_FIXTURE '));
      expect(diagnostics.status.value.producerLines, 3);
    });
  });

  test('logical upgrade finishes and saves an immutable file automatically', () async {
    await initialize();
    await OtaDiagnostics.withInstance(diagnostics, () async {
      OtaLinkStats(label: 'query').recordGetInfo(durationUs: 1);
      expect(await diagnostics.beginUpgrade(input()), isTrue);
      otaMonoLog('MONO_END_ACK_OK');
      otaMonoLog('MONO_REBOOT_VERIFIED');
      await diagnostics.finishUpgrade(completed: true);
    });
    final file = diagnostics.status.value.lastExport;
    expect(file, isNotNull);
    final footer = jsonDecode((await file!.readAsLines()).last);
    expect(footer['upgradeStarts'], 1);
    expect(footer['upgradeEnds'], 1);
    expect(footer['outcome'], 'completed');
  });

  test('failed setup blocks a measured upgrade without throwing into OTA', () async {
    await diagnostics.initialize(enabled: true, target: 'AA', sentinel: 'invalid',
        directoryProvider: () async => root);
    expect(diagnostics.status.value.ready, isFalse);
    expect(diagnostics.status.value.error, 'capture-initialization');
    expect(await diagnostics.beginUpgrade(input()), isFalse);
    await diagnostics.finishUpgrade(completed: false);
  });

  test('a new process can export the previous finished record without USB', () async {
    await initialize();
    diagnostics.record('OTA_LINK_SAMPLE label=query kind=get_info us=1 ok=1');
    expect(await diagnostics.beginUpgrade(input()), isTrue);
    await diagnostics.finishUpgrade(completed: true);
    final oldPath = diagnostics.status.value.lastExport!.path;
    await diagnostics.close();
    diagnostics = OtaDiagnostics();
    await initialize();
    expect(await FileSystemEntity.identical(
        diagnostics.status.value.lastExport!.path, oldPath), isTrue);
    expect(diagnostics.status.value.fromPreviousProcess, isTrue);
    expect(diagnostics.status.value.producerLines, 0);
    expect(await diagnostics.beginUpgrade(input()), isFalse);
  });

  test('logging failure does not change a successful transfer verdict', () async {
    await initialize();
    diagnostics.record('OTA_LINK_SAMPLE label=query kind=get_info us=1 ok=1');
    expect(await diagnostics.beginUpgrade(input()), isTrue);
    diagnostics.record('invalid fixture');
    await diagnostics.finishUpgrade(completed: true);
    expect(diagnostics.status.value.ready, isFalse);
    expect(diagnostics.status.value.error, isNotNull);
    expect(diagnostics.status.value.lastExport, isNull);
  });

  test('runtime profile binds the original upgrade input without changing its schema', () async {
    await initialize();
    diagnostics.record('OTA_LINK_SAMPLE label=query kind=get_info us=1 ok=1');
    final binding = input();
    final runtime = OtaExperimentRuntime(enabled: true);
    final text = jsonEncode({
      'schema': 1, 'runId': 'b921600-001', 'target': binding['deviceAddress'],
      'requestedBaud': 921600, 'reuseGatt': true, 'withoutResponse': true,
      'firmwareLatestUrl': 'https://fixture.trycloudflare.com/api/public/firmware/latest',
      for (final entry in binding.entries)
        if (entry.key != 'deviceAddress' && entry.key != 'appLifecycle') entry.key: entry.value,
    });
    await runtime.initialize(expectedTarget: 'AA:BB:CC:DD:EE:FF', readConfig: () async => text);
    await OtaExperimentRuntime.withInstance(runtime, () async {
      expect(await diagnostics.beginUpgrade({...binding, 'packageSha256': 'f' * 64}), isFalse);
      expect(await diagnostics.beginUpgrade(binding), isTrue);
      await diagnostics.finishUpgrade(completed: true);
    });
    final file = diagnostics.status.value.lastExport!;
    final rows = (await file.readAsLines()).map((line) => jsonDecode(line) as Map<String, dynamic>).toList();
    expect(rows.singleWhere((row) => row['kind'] == 'upgrade-start')['input'], binding);
    expect(rows.where((row) => row['kind'] == 'line').any((row) =>
        (row['message'] as String).contains(runtime.config!.sourceSha256)), isTrue);
    expect(rows.last['healthy'], isTrue);
    expect(rows.last['lost'], 0);
  });

  test('runtime experiment cannot bypass missing configuration or missing capture', () async {
    final runtime = OtaExperimentRuntime(enabled: true);
    await initialize();
    diagnostics.record('OTA_LINK_SAMPLE label=query kind=get_info us=1 ok=1');
    await OtaExperimentRuntime.withInstance(runtime, () async {
      expect(await diagnostics.beginUpgrade(input()), isFalse);
      expect(await OtaDiagnostics().beginUpgrade(input()), isFalse);
    });
  });
}
