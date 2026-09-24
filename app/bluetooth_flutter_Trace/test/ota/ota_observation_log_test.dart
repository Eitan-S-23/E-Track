import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:crypto/crypto.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ble_monitor/ota/ota_observation_log.dart';

const sentinel = 'OTAOBS0123456789abcdef01234567';
const sample = 'OTA_LINK_SAMPLE label=query kind=get_info us=10 ok=1';
Map<String, Object?> input() => {
  'packageSha256': 'a' * 64, 'packageBytes': 284466,
  'currentVersionCode': 30206, 'currentImageSha256': 'b' * 64,
  'targetVersionCode': 30207, 'targetImageSha256': 'c' * 64,
  'deviceAddress': 'AA:BB:CC:DD:EE:FF', 'appLifecycle': 'resumed',
};

class MemoryWriter implements OtaObservationWriter {
  final bytes = <int>[];
  bool failAppend = false;
  bool failFlush = false;
  int closes = 0;
  Completer<void>? gate;
  @override
  Future<void> append(List<int> data) async {
    await gate?.future;
    if (failAppend) throw const FileSystemException('fixture append');
    bytes.addAll(data);
  }
  @override
  Future<void> flush() async {
    if (failFlush) throw const FileSystemException('fixture flush');
  }
  @override
  Future<void> close() async { closes++; }
}

void main() {
  late Directory root;
  final logs = <OtaObservationLog>[];
  setUp(() async {
    final parent = Directory('${Directory.current.path}/.dart_tool/p34-log-tests');
    await parent.create(recursive: true);
    root = await parent.createTemp('case-');
  });
  tearDown(() async {
    for (final log in logs) { await log.close(); }
    logs.clear();
    await root.delete(recursive: true);
  });
  Future<OtaObservationLog> open({MemoryWriter? writer,
      int maxBytes = OtaObservationLog.defaultMaxBytes,
      int maxPendingBytes = OtaObservationLog.defaultMaxPendingBytes,
      int maxStoreBytes = OtaObservationLog.defaultMaxStoreBytes,
      void Function(OtaObservationCheckpoint)? onCheckpoint}) async {
    final log = await OtaObservationLog.open(root: root,
      target: 'AA:BB:CC:DD:EE:FF', sentinel: sentinel,
      maxBytes: maxBytes, maxPendingBytes: maxPendingBytes,
      maxStoreBytes: maxStoreBytes, flushInterval: const Duration(days: 1),
      onCheckpoint: onCheckpoint,
      writerFactory: writer == null ? null : (_) async => writer);
    logs.add(log);
    return log;
  }

  test('header is flushed before ready and has no invented baud', () async {
    final log = await open();
    final lines = await log.file.readAsLines();
    final header = jsonDecode(lines.single) as Map<String, dynamic>;
    expect(header['kind'], 'open');
    expect(header['sentinel'], sentinel);
    expect(header.containsKey('baud'), isFalse);
    final health = jsonDecode(await log.healthFile.readAsString());
    expect(health['records'], 1);
    expect(health['producerLines'], 0);
    expect(health['healthy'], isTrue);
  });

  test('header or host marker does not establish an app producer', () async {
    final log = await open();
    expect(await log.beginUpgrade(input()), isFalse);
    expect(log.record('P34_CAPTURE_PROBE host-injected'), isFalse);
    expect((await log.checkpoint()).healthy, isFalse);
    expect(await log.beginUpgrade(input()), isFalse);
  });

  test('complete immutable export binds every exact prefix byte', () async {
    final log = await open();
    expect(log.record(sample), isTrue);
    expect(await log.beginUpgrade(input()), isTrue);
    log.record('OTA_MONO MONO_BUDGET_START monoUs=100 wallUs=200');
    await log.endUpgrade(completed: true);
    final exported = await log.exportSnapshot();
    final bytes = await exported.readAsBytes();
    final lines = utf8.decode(bytes).split('\n')..removeLast();
    final footer = jsonDecode(lines.last) as Map<String, dynamic>;
    final prefix = bytes.sublist(0, footer['bytes'] as int);
    expect(footer['kind'], 'snapshot');
    expect(footer['sha256'], sha256.convert(prefix).toString());
    expect(footer['records'], lines.length - 1);
    expect(footer['upgradeStarts'], 1);
    expect(footer['upgradeEnds'], 1);
    expect(footer['outcome'], 'completed');
    expect(footer['healthy'], isTrue);
    for (var i = 0; i < lines.length - 1; i++) {
      expect(jsonDecode(lines[i])['seq'], i + 1);
    }
    log.record(sample);
    await log.checkpoint();
    expect(await exported.readAsBytes(), bytes);
  });

  test('prefix verdict is retained without turning the envelope into upgrade success', () async {
    final log = await open();
    expect(log.record(sample), isTrue);
    expect(await log.beginUpgrade(input()), isTrue);
    const message = 'OTA_PREFIX_PROBE {"schema":1,"outcome":"durable-prefix-aborted"}';
    expect(log.record(message), isTrue);
    await log.endUpgrade(completed: false);
    final file = await log.exportSnapshot();
    final rows = (await file.readAsLines()).map(jsonDecode).toList();
    expect(rows.any((row) => row['message'] == message), isTrue);
    expect(rows.last['outcome'], 'not-completed');
    expect(rows.last['healthy'], isTrue);
  });

  test('no export during an invocation and no second invocation', () async {
    final log = await open();
    log.record(sample);
    expect(await log.beginUpgrade(input()), isTrue);
    await expectLater(log.exportSnapshot(), throwsStateError);
    await log.endUpgrade(completed: false);
    expect(await log.beginUpgrade(input()), isFalse);
    final exported = await log.exportSnapshot();
    final footer = jsonDecode((await exported.readAsLines()).last);
    expect(footer['outcome'], 'not-completed');
  });

  test('identity input is closed and typed', () async {
    final log = await open();
    log.record(sample);
    for (final bad in [
      {...input()}..remove('currentImageSha256'),
      {...input(), 'extra': 'not an identity field'},
      {...input(), 'packageBytes': true},
      {...input(), 'packageBytes': 63},
      {...input(), 'currentVersionCode': -1},
      {...input(), 'targetVersionCode': 0x100000000},
      {...input(), 'targetImageSha256': 'D' * 64},
      {...input(), 'deviceAddress': 'https://example.invalid/credential'},
      {...input(), 'appLifecycle': 'assumed-foreground'},
    ]) {
      expect(await log.beginUpgrade(bad), isFalse);
    }
    expect(await log.beginUpgrade(input()), isTrue);
  });

  test('prefix, multiline and credential-shaped records are rejected', () async {
    final badLines = [
      'ordinary debug output', '$sample\n$sample', '$sample\r', '$sample\u0000',
      'OTA_MONO https://example.invalid/?signature=fixture',
      'OTA_MONO authorization: fixture',
      'OTA_MONO token=fixture',
      'OTA_MONO ${'x' * OtaObservationLog.maxLineBytes}',
    ];
    for (var i = 0; i < badLines.length; i++) {
      final log = await OtaObservationLog.open(root: Directory('${root.path}/case$i'),
          target: 'AA:BB:CC:DD:EE:FF', sentinel: sentinel);
      logs.add(log);
      log.record(sample);
      expect(log.record(badLines[i]), isFalse);
      final health = await log.checkpoint();
      expect(health.error, 'invalid-record');
      expect(health.lost, 1);
      expect(await log.file.readAsString(), contains(sample));
      expect(await log.file.readAsString(), isNot(contains(badLines[i])));
      await expectLater(log.exportSnapshot(), throwsStateError);
    }
  });

  test('pending capacity is bounded and accepted records are retained', () async {
    final writer = MemoryWriter();
    final log = await open(writer: writer, maxPendingBytes: 1024);
    var accepted = 0;
    while (log.record(sample)) { accepted++; }
    final state = await log.checkpoint();
    expect(accepted, greaterThan(0));
    expect(state.error, 'capture-capacity');
    expect(state.lost, 1);
    expect('\n'.allMatches(utf8.decode(writer.bytes)).length, accepted + 1);
  });

  test('file capacity fails instead of overwriting the oldest samples', () async {
    final log = await open(maxBytes: 1024, maxPendingBytes: 4096);
    while (log.record(sample)) {}
    final state = await log.checkpoint();
    expect(state.error, 'capture-capacity');
    expect(await log.file.length(), lessThanOrEqualTo(1024));
    expect((await log.file.readAsString()).startsWith('{"seq":1,'), isTrue);
  });

  for (final operation in ['write', 'flush']) {
    test('I/O $operation failure is latched without an unhandled future', () async {
      final writer = MemoryWriter();
      final log = await open(writer: writer);
      writer.failAppend = operation == 'write';
      writer.failFlush = operation == 'flush';
      log.record(sample);
      final state = await log.checkpoint().timeout(const Duration(seconds: 2));
      expect(state.healthy, isFalse);
      expect(state.error, 'io-$operation');
      expect(await log.beginUpgrade(input()), isFalse);
      await expectLater(log.exportSnapshot(), throwsStateError);
    });
  }

  test('status callback failure cannot strand a checkpoint', () async {
    var fail = false;
    final log = await open(onCheckpoint: (_) {
      if (fail) throw StateError('fixture callback');
    });
    fail = true;
    final state = await log.checkpoint().timeout(const Duration(seconds: 2));
    expect(state.error, 'status-callback');
  });

  test('checkpoint preserves its boundary across later queued events', () async {
    final writer = MemoryWriter();
    final log = await open(writer: writer);
    log.record(sample);
    writer.gate = Completer<void>();
    final before = log.checkpoint();
    final started = log.beginUpgrade(input());
    writer.gate!.complete();
    expect((await before).upgradeStarts, 0);
    expect((await before).outcome, isNull);
    expect(await started, isTrue);
  });

  test('exports and capture directories are unique and never overwrite', () async {
    final first = await open();
    final a = await first.exportSnapshot();
    final original = await a.readAsBytes();
    final b = await first.exportSnapshot();
    final second = await open();
    expect(a.path, isNot(b.path));
    expect(first.directory.path, isNot(second.directory.path));
    expect(await a.readAsBytes(), original);
    await first.exportSnapshot();
    await first.exportSnapshot();
    await expectLater(first.exportSnapshot(), throwsStateError);
  });

  test('close is idempotent and refuses further records', () async {
    final writer = MemoryWriter();
    final log = await open(writer: writer);
    log.record(sample);
    await log.close();
    await log.close();
    expect(writer.closes, 1);
    expect(log.record(sample), isFalse);
    await expectLater(log.exportSnapshot(), throwsStateError);
  });

  test('storage limit does not delete existing evidence', () async {
    final marker = File('${root.path}/preserved.bin');
    await marker.writeAsBytes(List.filled(1024, 7));
    await expectLater(open(maxBytes: 1024, maxStoreBytes: 2048),
        throwsA(isA<FileSystemException>()));
    expect(await marker.readAsBytes(), List.filled(1024, 7));
  });

  test('capture store does not follow a link', () async {
    final preserved = File('${root.path}/preserved.bin');
    await preserved.writeAsString('original');
    await Link('${root.path}/alias').create(preserved.path);
    await expectLater(open(), throwsA(isA<FileSystemException>()));
    expect(await preserved.readAsString(), 'original');
  }, skip: Platform.isWindows);
}
