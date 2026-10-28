import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:ble_monitor/ota/ota_diagnostics.dart';
import 'package:ble_monitor/ota/ota_query_trace.dart';

void main() {
  test('disabled diagnostics do not create a trace', () {
    expect(OtaQueryTrace.start(OtaDiagnostics(), 'ui'), isNull);
  });

  test('correlation survives awaits, isolates concurrent calls and snapshots exact records', () async {
    final parent = Directory('${Directory.current.path}/.dart_tool/query-trace-tests')
      ..createSync(recursive: true);
    final root = parent.createTempSync('trace-');
    final diagnostics = OtaDiagnostics();
    addTearDown(() async {
      await diagnostics.close();
      await root.delete(recursive: true);
    });
    await diagnostics.initialize(enabled: true, target: 'test-device',
        sentinel: 'OTAOBS0123456789abcdef01234567', directoryProvider: () async => root);
    final a = OtaQueryTrace.start(diagnostics, 'ui')!;
    final b = OtaQueryTrace.start(diagnostics, 'ui')!;
    final gate = Completer<void>();
    final one = a.bind(() async {
      await gate.future;
      expect(OtaQueryTrace.current, same(a));
      a.event('http_response', {'status': 200, 'requestId': 'req-1'});
    });
    await b.bind(() async {
      await Future<void>.value();
      expect(OtaQueryTrace.current, same(b));
      b.event('gate_rejected', {'reason': 'busy'});
    });
    gate.complete();
    await one;
    expect(OtaQueryTrace.current, isNull);
    a.event('unsafe', {'url': 'https://private.invalid/?token=secret',
      'message': 'authorization: secret\nsecond line', 'body': {'secret': 'value'}});
    final file = (await a.snapshot())!;
    expect(await a.snapshot(), same(file));
    final lines = await file.readAsLines();
    final messages = lines.map(jsonDecode).where((row) => row['kind'] == 'line')
        .map((row) => jsonDecode((row['message'] as String).substring('OTA_QUERY '.length)))
        .toList();
    final own = messages.where((row) => row['queryId'] == a.id).toList();
    expect(own.map((row) => row['seq']), orderedEquals([1, 2, 3, 4]));
    expect(messages.any((row) => row['queryId'] == b.id), isTrue);
    expect(own[2]['fields'], {'url': 'redacted', 'message': 'redacted', 'body': 'redacted'});
    expect(lines.join(), isNot(contains('secret')));
    expect(jsonDecode(lines.last)['healthy'], isTrue);
    expect(jsonDecode(lines.last)['upgradeStarts'], 0);
    final checkpoint = await root.list(recursive: true)
        .where((file) => file.path.endsWith('health.json')).single;
    expect(jsonDecode(await File(checkpoint.path).readAsString())['producerLines'], messages.length);
  });

  test('capture failure does not throw into the application operation', () async {
    final diagnostics = OtaDiagnostics();
    diagnostics.status.value = const OtaDiagnosticStatus(enabled: true);
    final trace = OtaQueryTrace.start(diagnostics, 'ui')!;
    expect(await trace.bind(() async => 42), 42);
    await trace.checkpoint();
    expect(await trace.snapshot(), isNull);
  });
}
