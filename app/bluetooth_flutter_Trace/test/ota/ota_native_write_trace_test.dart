import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ble_monitor/ota/ota_native_write_trace.dart';
import 'package:ble_monitor/ota/ota_observation_log.dart';
import 'package:ble_monitor/ota/ota_diagnostics.dart';

const capture = '1791437508254294-28859c8670dc4095b0eae5c2';
const target = 'E3:49:E1:14:D6:CB';
const binding = <String, Object?>{'captureId': capture, 'remoteId': target};

Map<String, Object?> snapshot({int count = 1}) => {
  'schema': 1, ...binding, 'clock': 'System.nanoTime-relative-ns', 'snapshot': 1,
  'pid': 123, 'capacity': 8192, 'sampleCount': count, 'overflow': 0,
  'correlationErrors': 0, 'incomplete': 0, 'apiErrors': 0, 'callbackErrors': 0,
  'rows': List.generate(count, (i) => <int>[i + 1, 1, 3, 1438416925,
      100, 200, 300, 400, 500, 0, 0]),
};

void main() {
  test('non-Android diagnostics do not call native code', () async {
    final lines = <String>[];
    final trace = OtaNativeWriteTrace(isAndroid: false, invoke: (_, __) => throw StateError('called'));
    await trace.start(captureId: capture, target: target, record: lines.add);
    await trace.collect(record: lines.add, flush: () async { fail('flushed'); });
    await trace.close();
    expect(lines, isEmpty);
  });

  test('collection is bound and flushed in small batches outside writes', () async {
    final calls = <String>[];
    final lines = <String>[];
    var flushes = 0;
    final raw = snapshot(count: 129);
    final trace = OtaNativeWriteTrace(isAndroid: true, invoke: (method, args) async {
      calls.add(method);
      expect(args, binding);
      return method == 'p34TraceSnapshot' ? raw : true;
    });
    await trace.start(captureId: capture, target: target.toLowerCase(), record: lines.add);
    expect(calls, ['p34TraceStart']);
    await trace.collect(record: lines.add, flush: () async { flushes++; });
    expect(flushes, 3);
    expect(lines.where((s) => s.startsWith('OTA_LINK_NATIVE_WRITE ')), hasLength(129));
    expect(lines.last, 'OTA_LINK_NATIVE_END snapshot=1 samples=129');
    expect(lines.every((line) => OtaObservationLog.prefixes.any(line.startsWith)), isTrue);
    expect(raw['rows'], hasLength(129));
    await trace.close();
    expect(calls, ['p34TraceStart', 'p34TraceSnapshot', 'p34TraceStop']);
  });

  test('early callbacks remain measured instead of clamped to zero', () {
    final raw = snapshot();
    final row = (raw['rows']! as List<List<int>>).single;
    row[6] = 600;
    expect(OtaNativeWriteTrace.validate(raw, binding)['rows'], [row]);
  });

  test('pending, overflow and API/callback failures stay visible', () {
    final raw = snapshot();
    final row = (raw['rows']! as List<List<int>>).single;
    row[7] = row[8] = row[10] = -1;
    raw['incomplete'] = 1;
    raw['overflow'] = 5;
    expect(OtaNativeWriteTrace.validate(raw, binding)['incomplete'], 1);
    row[9] = 201;
    raw['incomplete'] = 0;
    raw['apiErrors'] = 1;
    expect(OtaNativeWriteTrace.validate(raw, binding)['apiErrors'], 1);
    row[9] = 0;
    row[7] = 400;
    row[8] = 500;
    row[10] = 5;
    raw['apiErrors'] = 0;
    raw['callbackErrors'] = 1;
    expect(OtaNativeWriteTrace.validate(raw, binding)['callbackErrors'], 1);
  });

  test('invalid binding, counters, clock, shape and payload fields fail closed', () {
    final mutations = <void Function(Map<String, Object?>)>[
      (v) => v['captureId'] = 'another',
      (v) => v['remoteId'] = 'E3:49:E1:14:D6:CC',
      (v) => v['schema'] = 2,
      (v) => v['clock'] = 'wall-clock',
      (v) => v['pid'] = 0,
      (v) => v['sampleCount'] = 0,
      (v) => v['overflow'] = -1,
      (v) => v['incomplete'] = 1,
      (v) => v['capacity'] = 8193,
      (v) => v['payload'] = 'not permitted',
      (v) => (v['rows']! as List<List<int>>).single[0] = 2,
      (v) => (v['rows']! as List<List<int>>).single[3] = -1,
      (v) => (v['rows']! as List<List<int>>).single[5] = 99,
      (v) => (v['rows']! as List<List<int>>).single[8] = 399,
      (v) => (v['rows']! as List<List<int>>).single.removeLast(),
    ];
    for (final mutate in mutations) {
      final raw = snapshot();
      mutate(raw);
      expect(() => OtaNativeWriteTrace.validate(raw, binding), throwsFormatException);
    }
    expect(() => OtaNativeWriteTrace.validate(null, binding), throwsFormatException);
  });

  test('invalid native output is a diagnostic failure, not fabricated samples', () async {
    final lines = <String>[];
    final trace = OtaNativeWriteTrace(isAndroid: true, invoke: (method, _) async =>
        method == 'p34TraceSnapshot' ? {'rows': []} : true);
    await trace.start(captureId: capture, target: target, record: lines.add);
    await trace.collect(record: lines.add, flush: () async { fail('invalid output flushed'); });
    expect(lines.last, contains('phase=snapshot'));
    expect(lines.any((s) => s.startsWith('OTA_LINK_NATIVE_END')), isFalse);
    await trace.close();
  });

  test('uncertain start is stopped by its exact binding on close', () async {
    final calls = <String>[];
    final lines = <String>[];
    final trace = OtaNativeWriteTrace(isAndroid: true, invoke: (method, args) async {
      calls.add(method);
      expect(args, binding);
      if (method == 'p34TraceStart') throw TimeoutException('native response');
      return true;
    });
    await trace.start(captureId: capture, target: target, record: lines.add);
    await trace.collect(record: lines.add, flush: () async {});
    await trace.close();
    expect(calls, ['p34TraceStart', 'p34TraceStop']);
    expect(lines.single, contains('phase=start'));
  });

  test('missing plugin does not become a successful trace', () async {
    final lines = <String>[];
    final trace = OtaNativeWriteTrace(isAndroid: true, invoke: (_, __) async => throw MissingPluginException());
    await trace.start(captureId: capture, target: target, record: lines.add);
    expect(lines.single, contains('ERROR'));
    await trace.close();
  });

  test('concurrent exports share one collection and close waits for it', () async {
    final response = Completer<Object?>();
    final calls = <String>[];
    final lines = <String>[];
    final trace = OtaNativeWriteTrace(isAndroid: true, invoke: (method, _) async {
      calls.add(method);
      if (method == 'p34TraceSnapshot') return await response.future;
      return true;
    });
    await trace.start(captureId: capture, target: target, record: lines.add);
    final first = trace.collect(record: lines.add, flush: () async {});
    final second = trace.collect(record: lines.add, flush: () async {});
    final closed = trace.close();
    expect(identical(first, second), isTrue);
    expect(calls, ['p34TraceStart', 'p34TraceSnapshot']);
    response.complete(snapshot());
    await Future.wait([first, second, closed]);
    expect(calls.last, 'p34TraceStop');
    expect(lines.any((s) => s.startsWith('OTA_LINK_NATIVE_META ')), isTrue, reason: lines.join('\n'));
    final meta = lines.singleWhere((s) => s.startsWith('OTA_LINK_NATIVE_META '));
    expect(jsonDecode(meta.substring('OTA_LINK_NATIVE_META '.length))['sampleCount'], 1);
  });

  test('diagnostics preserve the first runtime stamp and start native once before INFO', () async {
    final root = await Directory.systemTemp.createTemp('native-observation-order-');
    final calls = <String>[];
    final native = OtaNativeWriteTrace(isAndroid: true, invoke: (method, args) async {
      calls.add(method);
      if (method == 'p34TraceSnapshot') return {...snapshot(count: 0), ...args};
      return true;
    });
    final diagnostics = OtaDiagnostics(nativeTrace: native);
    try {
      await diagnostics.initialize(enabled: true, target: target,
          sentinel: 'OTAOBS96bb2c74d5ad6ccecaf30e40', directoryProvider: () async => root);
      expect(calls, isEmpty);
      diagnostics.record('OTA_EXPERIMENT {}');
      await diagnostics.startNativeWrites();
      await diagnostics.startNativeWrites();
      expect(calls, ['p34TraceStart']);
      await diagnostics.captureNativeWrites();
      await diagnostics.close();
      final directory = await Directory('${root.path}/p34-observations').list().single as Directory;
      final rows = await File('${directory.path}/events.jsonl').readAsLines();
      expect(jsonDecode(rows[1])['message'], 'OTA_EXPERIMENT {}');
      expect(calls, ['p34TraceStart', 'p34TraceSnapshot', 'p34TraceStop']);
    } finally {
      await diagnostics.close();
      await root.delete(recursive: true);
    }
  });
}
