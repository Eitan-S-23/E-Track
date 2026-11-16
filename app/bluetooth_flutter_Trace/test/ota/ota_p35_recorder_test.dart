import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:ble_monitor/ota/ota_observation_log.dart';
import 'package:ble_monitor/ota/ota_link_stats.dart';
import 'package:ble_monitor/ota/ota_p35_android_log.dart';
import 'package:ble_monitor/ota/ota_p35_recorder.dart';
import 'package:ble_monitor/ota/ota_p35_stream.dart';
import 'package:flutter/foundation.dart';
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

class MemoryStream extends OtaP35Stream {
  final bytes = <int>[];
  bool reject = false;
  @override
  Future<void> open() async {}
  @override
  Future<void> send(List<int> data) async {
    if (reject) throw StateError('synthetic ACK failure');
    bytes.addAll(data);
  }
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

  Map<String, Object?> timedSnapshot() => {...snapshot(), 'runtime': {
    'backgrounded': false, 'acquired': false, 'reason': null, 'active': false,
    'paused': false, 'ownerEpoch': 7, 'revision': 1, 'task': null,
  }};

  test('mixed stream seals original source timings and passes the actual Python consumer', () async {
    final stream = MemoryStream();
    final r = OtaP35Recorder(emit: (_) {}, directoryProvider: () async => root);
    expect(await r.start(timedSnapshot, linkTimings: true), isFalse);
    expect(await r.start(timedSnapshot, reliable: true, stream: stream,
        stateSchema: 2, linkTimings: true), isTrue);
    var now = 100;
    final stats = OtaLinkStats(label: 'upgrade', clockUs: () => now,
        onObservation: r.bindLinkStats(ownerEpoch: 7, label: 'upgrade'));
    stats.recordTransferStart();
    stats.recordSegmentSendEnd(offsetBytes: 0, lengthBytes: 128);
    stats.recordAckConfirm(blockStart: 0, segs: [0], segmentSize: 128, atUs: 140);
    stats.recordEndAckArrival(atUs: 150);
    now = 150;
    stats.recordTransferOutcome(ok: true);
    stats.emitSummary();
    await r.stop();
    final raw = await r.file!.readAsBytes();
    expect(raw, stream.bytes);
    final lines = utf8.decode(raw).trim().split('\n');
    final diagnostics = lines.where((line) => line.startsWith('OTA_P35_DIAGNOSTIC '))
        .map((line) => jsonDecode(line.substring('OTA_P35_DIAGNOSTIC '.length)) as Map<String, dynamic>).toList();
    expect(diagnostics, hasLength(3));
    expect(diagnostics[0]['line'], contains('us=100 off=0 len=128'));
    expect(diagnostics[1]['line'], contains('us=40 off=0'));
    expect(diagnostics.map((row) => row['clockId']).toSet(), {'${r.captureId}:1'});
    final result = await Process.run(Platform.isWindows ? 'python' : 'python3',
      ['-I', '-S', '-B', '-X', 'utf8', 'Tools/ota/p35-automation/runner.py', 'audit-timing',
       '--archive', r.file!.path, '--capture-id', r.captureId!], workingDirectory: Directory.current.parent.parent.path);
    expect(result.exitCode, 0, reason: '${result.stdout}\n${result.stderr}');
    final report = jsonDecode(result.stdout as String);
    expect(report['groups'][0]['ackLatencyUs'], [40]);
    expect(report['archive']['records'], 5);
  });

  test('diagnostic owner and private input failures cannot produce a healthy seal', () async {
    for (final badOwner in [true, false]) {
      final directory = await root.createTemp('negative-');
      final r = OtaP35Recorder(emit: (_) {}, directoryProvider: () async => directory);
      await r.start(timedSnapshot, reliable: true, stream: MemoryStream(), stateSchema: 2, linkTimings: true);
      final observer = r.bindLinkStats(ownerEpoch: badOwner ? 8 : 7, label: 'upgrade');
      if (!badOwner) observer!('OTA_LINK_SAMPLE label=upgrade token=must-not-persist');
      expect(r.healthy, isFalse);
      await r.stop();
      final raw = await r.file!.readAsString();
      expect(raw, contains('"healthy":false'));
      expect(raw, isNot(contains('must-not-persist')));
    }
  });

  test('full successful 1MiB source summary fits unchanged 3500-byte recorder ceiling', () async {
    final originalPrint = debugPrint;
    debugPrint = (String? message, {int? wrapWidth}) {};
    addTearDown(() { debugPrint = originalPrint; });
    final stream = MemoryStream();
    final writer = Writer();
    final r = OtaP35Recorder(emit: (_) {}, directoryProvider: () async => root,
        writerFactory: (_) async => writer);
    await r.start(timedSnapshot, reliable: true, stream: stream, stateSchema: 2, linkTimings: true);
    final observer = r.bindLinkStats(ownerEpoch: 7, label: 'upgrade')!;
    // Summary-only size fixture, not a complete timing-evidence capture.
    var now = 1000000000;
    final stats = OtaLinkStats(label: 'upgrade', device: 'aa:bb:cc:dd:ee:ff',
        clockUs: () => now, onObservation: (line) {
          if (line.startsWith('OTA_LINK_STATS ')) observer(line);
        });
    stats.phaseStart('bind');
    stats.recordCharsDiscovery(durationUs: 1500000, found: true, writeMode: 'writeWithResponse');
    stats.recordMtu(requested: 517, chunkBytes: 509, durationUs: 1000000, source: 'negotiated');
    stats.recordSubscribe(durationUs: 500000, ok: true);
    now += 3000000;
    stats.phaseEnd('bind');
    stats.phaseStart('getinfo');
    stats.recordGetInfo(durationUs: 500000);
    now += 500000;
    stats.phaseEnd('getinfo');
    stats.configureDataBatch(3);
    stats.recordTransferStart();
    stats.recordBeginAck(protocol: 2, session: 65535, sequence: 65535,
        durableOffset: 0, bitmap: 0, atUs: now + 10000, ackTimeoutMs: 1500,
        maxRetries: 8, windowSegments: 32, epoch: 4294967295);
    for (var off = 0; off < 1048576; off += 128) {
      now += 100000;
      stats.recordSegmentSendEnd(offsetBytes: off, lengthBytes: 128);
      stats.recordAckConfirm(blockStart: off, segs: [0], segmentSize: 128, atUs: now + 50000);
      stats.recordAckClass('ok');
      stats.recordGattWrite(durationUs: 90000, bytes: 147);
      stats.recordDiscover(durationUs: 1000);
      stats.recordPlatformWrite(durationUs: 89000, bytes: 147);
      if ((off + 128) % 4096 == 0) stats.recordDurableAdvance(off + 128, atUs: now + 50000);
      if (off % 384 == 0) stats.recordDataBatchChunk(bytes: 441, completedFrames: 3);
    }
    now += 100000;
    stats.recordEndAckArrival(atUs: now);
    stats.recordTransferOutcome(ok: true);
    stats.emitSummary();
    expect(stats.toJson()['transfer']['segmentsUnique'], 8192);
    expect(stats.toJson()['transfer']['ackSamples'], 'complete');
    await r.stop();
    expect(r.error, isNull);
    expect(writer.bytes, stream.bytes);
    final line = utf8.decode(writer.bytes).split('\n')
        .singleWhere((line) => line.startsWith('OTA_P35_DIAGNOSTIC '));
    expect(utf8.encode('$line\n').length, lessThanOrEqualTo(3500));
    final wrapped = jsonDecode(line.substring('OTA_P35_DIAGNOSTIC '.length));
    expect(wrapped['line'], 'OTA_LINK_STATS ${jsonEncode(stats.toJson())}');
    expect(utf8.decode(writer.bytes), contains('"healthy":true'));
  });

  test('diagnostics share the primary stream failure latch and never replace source clock', () async {
    final stream = MemoryStream();
    final r = OtaP35Recorder(emit: (_) {}, directoryProvider: () async => root);
    await r.start(timedSnapshot, reliable: true, stream: stream, stateSchema: 2, linkTimings: true);
    final observer = r.bindLinkStats(ownerEpoch: 7, label: 'upgrade')!;
    await Future<void>.delayed(const Duration(milliseconds: 20));
    stream.reject = true;
    observer('OTA_LINK_SAMPLE label=upgrade kind=ack_latency us=40 off=0');
    await Future<void>.delayed(const Duration(milliseconds: 20));
    await r.stop();
    expect(r.error, 'live-stream-failed');
    expect(await r.file!.readAsString(), contains('"healthy":false'));
  });

  test('disabled recorder has no storage or log side effects', () async {
    final lines = <String>[];
    final r = OtaP35Recorder(emit: lines.add, directoryProvider: () async => throw StateError('must not open'));
    r.record(); await r.stop();
    expect(lines, isEmpty);
    expect(r.captureId, isNull);
  });

  test('runtime schema is explicit, persisted and independent of container schema', () async {
    final stream = MemoryStream();
    final r = OtaP35Recorder(emit: (_) {}, directoryProvider: () async => root);
    expect(await r.start(snapshot, stateSchema: 2), isFalse);
    final runtime = <String, Object?>{'backgrounded': true, 'acquired': true,
      'reason': null, 'active': true, 'paused': false, 'ownerEpoch': 3,
      'revision': 17, 'task': {'taskId': 'test_3', 'generation': 3,
        'deviceToken': 'd' * 64, 'packageSha256': 'c' * 64}};
    expect(await r.start(() => {...snapshot(), 'runtime': runtime},
        reliable: true, stream: stream, stateSchema: 2), isTrue);
    await r.stop();
    final raw = await r.file!.readAsBytes();
    expect(raw, stream.bytes);
    final lines = utf8.decode(raw).trim().split('\n');
    expect(jsonDecode(lines.first.substring('OTA_P35_CAPTURE '.length))['schema'], 1);
    final row = jsonDecode(lines[1].substring('OTA_P35_STATE '.length));
    expect(row['schema'], 2);
    expect(row['runtime'], runtime);
    expect(jsonDecode(lines.last.substring('OTA_P35_CAPTURE '.length))['healthy'], isTrue);
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

  test('native publication failure preserves originals and latches unhealthy', () async {
    final r = OtaP35Recorder(directoryProvider: () async => root, emit: (line) {
      if (line.startsWith('OTA_P35_STATE ')) {
        throw StateError('synthetic native writer rejection');
      }
    });
    await r.start(snapshot);
    await r.stop();
    expect(r.error, 'log-write-failed');
    expect(r.healthy, isFalse);
    r.record('heartbeat');
    final raw = await r.file!.readAsString();
    expect(raw, contains('OTA_P35_STATE '));
    final footer = jsonDecode(raw.trimRight().split('\n').last.substring(16))
        as Map<String, dynamic>;
    expect(footer['healthy'], isFalse);
    expect(footer['error'], 'log-write-failed');
  });

  test('acknowledged stream survives mirror EAGAIN but preserves its original rejection', () async {
    final stream = MemoryStream();
    var attempts = 0;
    final r = OtaP35Recorder(directoryProvider: () async => root, emit: (line) {
      attempts++;
      if (line.startsWith('OTA_P35_STATE ')) throw AndroidLogWriteFailure(-11, 586);
    });
    expect(await r.start(snapshot, reliable: true, stream: stream), isTrue);
    r.record(); r.record();
    await r.stop();
    final raw = await r.file!.readAsBytes();
    expect(stream.bytes, raw);
    expect(r.error, isNull);
    expect(r.status.value, 'closed');
    expect(attempts, 2);
    final diagnostic = jsonDecode(await r.logcatDiagnosticFile!.readAsString()) as Map<String,dynamic>;
    expect(diagnostic['status'], 'FAILED_DISABLED');
    expect(diagnostic['captureId'], r.captureId);
    expect(diagnostic['nativeResult'], -11);
    expect(diagnostic['expectedBytes'], 586);
    expect(diagnostic['record'], contains('"seq":1'));
    expect(utf8.decode(raw), contains('"healthy":true,"lost":0,"error":null'));
  });

  test('primary stream failure still latches unhealthy even when mirror is optional', () async {
    final stream = MemoryStream();
    final r = OtaP35Recorder(directoryProvider: () async => root, emit: (_) {});
    await r.start(snapshot, reliable: true, stream: stream);
    await Future<void>.delayed(Duration.zero);
    stream.reject = true;
    r.record();
    await Future<void>.delayed(const Duration(milliseconds: 20));
    await r.stop();
    expect(r.error, 'live-stream-failed');
    expect(await r.file!.readAsString(), contains('"healthy":false'));
  });

  test('snapshot errors are capture errors, never OTA exceptions', () async {
    final r = OtaP35Recorder(emit: (_) {}, directoryProvider: () async => root);
    await r.start(() => throw StateError('synthetic'));
    expect(r.error, 'snapshot-failed');
    await r.stop();
  });

  test('native failure details survive sealing and closed state notifies UI', () async {
    final lines = <String>[];
    final active = <bool>[];
    final r = OtaP35Recorder(directoryProvider: () async => root, emit: (line) {
      if (line.startsWith('OTA_P35_STATE ')) {
        throw AndroidLogWriteFailure(-11, 1234);
      }
      lines.add(line);
    });
    r.status.addListener(() => active.add(r.active));
    await r.start(snapshot);
    await r.stop();
    expect(r.error, 'log-write-failed:native=-11:expected=1234');
    expect(r.active, isFalse);
    expect(r.healthy, isFalse);
    expect(active.last, isFalse);
    expect(r.status.value, 'failed:log-write-failed:native=-11:expected=1234:closed');
    expect(lines.where((l) => l.startsWith('OTA_P35_ERROR ')).single,
      contains('log-write-failed:native=-11:expected=1234'));
    final raw = await r.file!.readAsString();
    expect(raw, contains('"healthy":false'));
    expect(raw, contains('log-write-failed:native=-11:expected=1234'));
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
