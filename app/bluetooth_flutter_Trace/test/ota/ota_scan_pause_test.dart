import 'dart:async';

import 'package:ble_monitor/ota/ota_scan_pause.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  late OtaScanPause gate;
  late bool scanning;
  late Duration now;
  late List<String> calls;
  Completer<void>? starting;
  bool failStop = false;
  setUp(() {
    scanning = false;
    now = Duration.zero;
    calls = [];
    starting = null;
    failStop = false;
    gate = OtaScanPause(
      now: () => now,
      isScanning: () => scanning,
      startNative: (timeout) async {
        calls.add('start:${timeout?.inSeconds}');
        if (starting != null) await starting!.future;
        scanning = true;
      },
      stopNative: () async {
        calls.add('stop');
        if (failStop) throw StateError('native-stop-failed');
        scanning = false;
      },
    );
  });

  test('pause blocks watchdog restarts and restores demand once', () async {
    await gate.start();
    final lease = gate.pause();
    await lease.ready;
    await gate.start();
    expect(scanning, isFalse);
    await lease.close();
    await lease.close();
    expect(calls, ['start:null', 'stop', 'start:null']);
  });

  test('idle pause does not invent scanning demand', () async {
    final lease = gate.pause();
    await lease.ready;
    await lease.close();
    expect(calls, ['stop']);
  });

  test('pause waits for an in-flight native start before stopping it', () async {
    starting = Completer<void>();
    final start = gate.start();
    await Future<void>.delayed(Duration.zero);
    final lease = gate.pause();
    var ready = false;
    final paused = lease.ready.then((_) => ready = true);
    await Future<void>.delayed(Duration.zero);
    expect(ready, isFalse);
    starting!.complete();
    await start;
    await paused;
    expect(scanning, isFalse);
    await lease.close();
    expect(scanning, isTrue);
  });

  test('explicit stop during pause prevents restart', () async {
    await gate.start();
    final lease = gate.pause();
    await lease.ready;
    await gate.stop();
    await lease.close();
    expect(scanning, isFalse);
    expect(calls.where((c) => c.startsWith('start')), hasLength(1));
  });

  test('new demand after explicit stop is restored', () async {
    final lease = gate.pause();
    await lease.ready;
    await gate.stop();
    await gate.start();
    expect(scanning, isFalse);
    await lease.close();
    expect(scanning, isTrue);
  });

  test('old release cannot resume through a newer lease', () async {
    await gate.start();
    final first = gate.pause();
    await first.ready;
    final second = gate.pause();
    await second.ready;
    await first.close();
    expect(scanning, isFalse);
    await second.close();
    expect(scanning, isTrue);
  });

  test('restore preserves remaining timeout, not a fresh timeout', () async {
    await gate.start(timeout: const Duration(seconds: 10));
    final lease = gate.pause();
    await lease.ready;
    now = const Duration(seconds: 7);
    await lease.close();
    expect(calls.last, 'start:3');
  });

  test('expired scan demand is not restored', () async {
    await gate.start(timeout: const Duration(seconds: 10));
    final lease = gate.pause();
    await lease.ready;
    now = const Duration(seconds: 10);
    await lease.close();
    expect(scanning, isFalse);
    await gate.start();
    expect(scanning, isTrue);
  });

  test('native stop failure cannot claim a ready pause', () async {
    await gate.start();
    failStop = true;
    final lease = gate.pause();
    await expectLater(lease.ready, throwsStateError);
    failStop = false;
    await lease.close();
  });

  test('dispose blocks delayed restoration and new owners', () async {
    await gate.start();
    final lease = gate.pause();
    await lease.ready;
    await gate.dispose();
    await lease.close();
    expect(scanning, isFalse);
    expect(gate.pause, throwsStateError);
    await expectLater(gate.start(), throwsStateError);
  });
}
