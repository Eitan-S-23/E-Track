import 'dart:convert';
import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:crypto/crypto.dart';
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
    OtaDiagnostics.withInstance(diagnostics, () {
      emitOtaObservation('OTA_LINK_STATS ${jsonEncode({'fixture': '测量' * 600})}');
    });
    await expectLater(diagnostics.exportSnapshot(), throwsStateError);
    expect(directoryCalls, 0);
    expect(await root.list().length, 0);
    expect(diagnostics.status.value.enabled, isFalse);
  });

  test('P35-SMOKE-LOG-01 real UTF-8 summary survives file/export/strict host parser', () async {
    await initialize();
    late String summary;
    await OtaDiagnostics.withInstance(diagnostics, () async {
      final stats = OtaLinkStats(label: 'query', clockUs: () => 40);
      stats.recordGetInfo(durationUs: 20);
      expect(await diagnostics.beginUpgrade(input()), isTrue);
      stats.recordFailure(stage: 'fixture', reason: '测量记录完整性');
      summary = 'OTA_LINK_STATS ${jsonEncode(stats.toJson())}';
      expect(utf8.encode(summary).length, greaterThan(1024));
      stats.emitSummary();
      // A synthetic file-route test is not a successful upgrade/performance run.
      await diagnostics.finishUpgrade(completed: false);
    });
    final snapshot = diagnostics.status.value.lastExport!;
    final original = await snapshot.readAsBytes();
    final rows = (await snapshot.readAsLines()).map(jsonDecode).toList();
    final footer = rows.last as Map<String, dynamic>;
    final prefix = original.sublist(0, footer['bytes'] as int);
    final messages = rows.where((row) => row['kind'] == 'line')
        .map((row) => row['message'] as String).toList();
    expect(messages.last, summary);
    expect(footer['records'], rows.length - 1);
    expect(footer['producerLines'], messages.length);
    expect(footer['sha256'], sha256.convert(prefix).toString());
    expect(footer['upgradeStarts'], 1);
    expect(footer['upgradeEnds'], 1);
    expect(footer['lost'], 0);
    expect(footer['healthy'], isTrue);
    expect(footer['outcome'], 'not-completed');

    final repo = Directory.current.parent.parent;
    final parser = File('${repo.path}/Tools/ota/p3-4-link-stats/observation_capture.py');
    expect(await parser.exists(), isTrue);
    Future<ProcessResult> parse(File file, {Directory? out}) => Process.run(
      Platform.isWindows ? 'python' : 'python3', [
        '-I', '-S', '-B', '-X', 'utf8', parser.path,
        out == null ? 'inspect' : 'extract', '--input', file.path,
        '--expect-sentinel', 'OTAOBS0123456789abcdef01234567',
        '--expect-target', 'AA:BB:CC:DD:EE:FF',
        if (out != null) ...['--out-root', out.path],
      ], workingDirectory: repo.path);
    final out = Directory('${root.path}/extracted');
    final result = await parse(snapshot, out: out);
    expect(result.exitCode, 0, reason: '${result.stdout}\n${result.stderr}');
    final record = jsonDecode(result.stdout as String) as Map<String, dynamic>;
    final unwrapped = utf8.encode('${messages.join('\n')}\n');
    expect(await File('${out.path}/observations.log').readAsBytes(), unwrapped);
    expect(record['records'], footer['records']);
    expect(record['producerLines'], messages.length);
    expect(record['rawSha256'], sha256.convert(original).toString());
    expect(record['unwrappedSha256'], sha256.convert(unwrapped).toString());
    expect(record['eligibleForThreshold'], isFalse);
    expect(record['independentAcceptance'], 'NOT_RUN');

    final lines = utf8.decode(original).split('\n')..removeLast();
    final damaged = <String, List<int>>{
      'missing-footer': utf8.encode('${lines.take(lines.length - 1).join('\n')}\n'),
      'missing-record': utf8.encode('${[lines.first, ...lines.skip(2)].join('\n')}\n'),
      'clipped-summary': utf8.encode('${lines.map((line) =>
          line.contains('OTA_LINK_STATS ') ? line.substring(0, 1024) : line).join('\n')}\n'),
      'truncated': original.sublist(0, original.length - 1),
      'corrupt-prefix': [...original]..[100] ^= 1,
      'corrupt-counter': utf8.encode('${[...lines.take(lines.length - 1),
          jsonEncode({...footer, 'producerLines': messages.length + 1})].join('\n')}\n'),
    };
    for (final entry in damaged.entries) {
      final file = File('${root.path}/${entry.key}.jsonl');
      await file.writeAsBytes(entry.value, flush: true);
      final rejectedOut = Directory('${root.path}/reject-${entry.key}');
      final rejected = await parse(file, out: rejectedOut);
      expect(rejected.exitCode, 2, reason: entry.key);
      expect(rejected.stderr, contains('CAPTURE_REJECTED'), reason: entry.key);
      expect(await rejectedOut.exists(), isFalse, reason: entry.key);
    }
    final missing = await parse(File('${root.path}/absent.jsonl'));
    expect(missing.exitCode, 2);
    expect(missing.stderr, contains('CAPTURE_REJECTED'));
    await diagnostics.close();
    expect(await snapshot.readAsBytes(), original);
    final afterClose = await parse(snapshot);
    expect(afterClose.exitCode, 0, reason: '${afterClose.stderr}');
    oldPrint('P35-SMOKE-LOG-01 ${jsonEncode({
      'summaryBytes': utf8.encode(summary).length, 'snapshotBytes': original.length,
      'records': footer['records'], 'producerLines': messages.length,
      'snapshotSha256': sha256.convert(original).toString(),
      'unwrappedSha256': sha256.convert(unwrapped).toString(),
      'damagedVariantsRejected': damaged.length, 'missingFileRejected': true,
    })}');
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
