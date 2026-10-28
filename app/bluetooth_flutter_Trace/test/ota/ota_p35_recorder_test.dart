import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:ble_monitor/ota/ota_observation_log.dart';
import 'package:ble_monitor/ota/ota_p35_recorder.dart';
import 'package:flutter_test/flutter_test.dart';

Map<String, Object?> snapshot() => {
  'deviceAddress': 'aa:bb:cc:dd:ee:ff', 'phase': 'idle',
  'currentVersionCode': 30293, 'currentImageSha256': 'a' * 64,
  'targetVersionCode': 30294, 'targetImageSha256': 'b' * 64,
  'packageSha256': 'c' * 64, 'packageBytes': 9000, 'packageVerified': true,
  'releaseId': 'synthetic', 'latestUrl': 'https://fixture.invalid/api/public/firmware/latest',
  'durable': 0, 'bitmap': null, 'protocol': 2, 'session': 1, 'sendOffset': null,
  'linkConnected': true, 'freshConnection': true,
};

class Writer implements OtaObservationWriter {
  final bytes = <int>[];
  Completer<void>? gate;
  bool fail = false;
  @override
  Future<void> append(List<int> value) async {
    if (fail) throw const FileSystemException('synthetic disk failure');
    bytes.addAll(value);
  }
  @override
  Future<void> flush() async { await gate?.future; }
  @override
  Future<void> close() async {}
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  late Directory root;
  setUp(() async {
    final parent = Directory('${Directory.current.path}/.dart_tool/p35-recorder-tests');
    await parent.create(recursive: true);
    root = await parent.createTemp('case-');
  });
  tearDown(() async { await root.delete(recursive: true); });

  test('disabled recorder has no storage or log side effects', () async {
    final lines = <String>[];
    final r = OtaP35Recorder(emit: lines.add, directoryProvider: () async => throw StateError('must not open'));
    r.record(); await r.stop();
    expect(lines, isEmpty);
    expect(r.captureId, isNull);
  });

  test('ten resume events remain one loss-accounted persisted capture', () async {
    final lines = <String>[];
    final r = OtaP35Recorder(emit: lines.add, directoryProvider: () async => root);
    expect(await r.start(snapshot), isTrue);
    for (var i = 0; i < 10; i++) { r.record('beginAck'); r.record('data'); }
    await r.stop();
    final raw = await r.file!.readAsString();
    expect(raw, '${lines.join('\n')}\n');
    final rows = lines.where((l) => l.startsWith('OTA_P35_STATE '))
        .map((l) => jsonDecode(l.substring(14)) as Map<String, dynamic>).toList();
    expect(rows.map((r) => r['seq']), List.generate(21, (i) => i + 1));
    expect(rows.where((r) => r['event'] == 'beginAck'), hasLength(10));
    expect(r.status.value, 'closed');
    expect(await r.start(snapshot), isFalse);
  });

  test('Dart originals pass the real isolated Python archive consumer', () async {
    final r = OtaP35Recorder(emit: (_) {}, directoryProvider: () async => root);
    await r.start(snapshot);
    r.record('identity');
    await r.stop();
    final repo = Directory.current.parent.parent;
    final result = await Process.run(Platform.isWindows ? 'python' : 'python3',
      ['-I', '-S', '-B', '-X', 'utf8', 'Tools/ota/p35-automation/runner.py', 'audit',
       '--archive', r.file!.path, '--capture-id', r.captureId!], workingDirectory: repo.path);
    expect(result.exitCode, 0, reason: '${result.stdout}\n${result.stderr}');
    expect(jsonDecode(result.stdout as String)['integrity'], 'VERIFIED');
  });

  test('live lines are not published ahead of the disk flush', () async {
    final writer = Writer(); final lines = <String>[];
    final r = OtaP35Recorder(emit: lines.add, directoryProvider: () async => root,
      writerFactory: (_) async => writer);
    await r.start(snapshot);
    writer.gate = Completer<void>();
    r.record();
    await Future<void>.delayed(Duration.zero);
    expect(lines.where((l) => l.startsWith('OTA_P35_STATE ')), isEmpty);
    writer.gate!.complete();
    await r.stop();
    expect(lines.where((l) => l.startsWith('OTA_P35_STATE ')), hasLength(2));
  });

  test('writer failure latches and cannot be hidden by later heartbeat', () async {
    final writer = Writer(); final lines = <String>[];
    final r = OtaP35Recorder(emit: lines.add, directoryProvider: () async => root,
      writerFactory: (_) async => writer);
    await r.start(snapshot);
    await Future<void>.delayed(Duration.zero);
    writer.fail = true;
    r.record(); await Future<void>.delayed(Duration.zero);
    expect(r.error, 'write-failed');
    final count = lines.length; r.record('heartbeat');
    expect(lines.length, count);
    writer.fail = false; await r.stop();
    expect(lines.last, contains('"healthy":false'));
  });

  test('bounded queue rejects overload rather than dropping healthy records', () async {
    final writer = Writer();
    final r = OtaP35Recorder(emit: (_) {}, directoryProvider: () async => root,
      writerFactory: (_) async => writer, maxPending: 1);
    await r.start(snapshot);
    writer.gate = Completer<void>();
    r.record(); r.record();
    expect(r.healthy, isFalse);
    expect(r.error, 'capture-limit');
    writer.gate!.complete(); await r.stop();
  });

  test('snapshot errors are capture errors, never OTA exceptions', () async {
    final r = OtaP35Recorder(emit: (_) {}, directoryProvider: () async => root);
    await r.start(() => throw StateError('synthetic'));
    expect(r.error, 'snapshot-failed');
    await r.stop();
  });

  test('stop during asynchronous open cannot resurrect recording', () async {
    final directory = Completer<Directory>();
    final lines = <String>[];
    final r = OtaP35Recorder(emit: lines.add, directoryProvider: () => directory.future);
    final starting = r.start(snapshot);
    final stopping = r.stop();
    directory.complete(root);
    expect(await starting, isFalse);
    await stopping;
    expect(r.active, isFalse);
    expect(r.status.value, 'closed');
    expect(lines.where((l) => l.startsWith('OTA_P35_STATE ')), isEmpty);
    expect(await r.start(snapshot), isFalse);
  });
}
