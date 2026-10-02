import 'dart:async';

import 'package:ble_monitor/ota/ota_radio_lease.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('same current owner restores balanced exactly once', () async {
    final calls = <bool>[];
    final lease = OtaPriorityQueue().acquire(
      isCurrent: () => true, request: (high) async { calls.add(high); });
    await lease.ready;
    await lease.close();
    await lease.close();
    expect(calls, [true, false]);
  });

  test('new physical generation never receives an old restore', () async {
    var current = true;
    final calls = <bool>[];
    final lease = OtaPriorityQueue().acquire(
      isCurrent: () => current, request: (high) async { calls.add(high); });
    await lease.ready;
    current = false;
    await lease.close();
    expect(calls, [true]);
  });

  test('a stale generation cannot acquire priority', () async {
    final calls = <bool>[];
    final lease = OtaPriorityQueue().acquire(
      isCurrent: () => false, request: (high) async { calls.add(high); });
    await expectLater(lease.ready, throwsStateError);
    await lease.close();
    expect(calls, isEmpty);
  });

  test('later owner survives earlier idempotent release', () async {
    final queue = OtaPriorityQueue();
    final calls = <String>[];
    final first = queue.acquire(isCurrent: () => true,
      request: (high) async { calls.add('first:$high'); });
    await first.ready;
    final second = queue.acquire(isCurrent: () => true,
      request: (high) async { calls.add('second:$high'); });
    await second.ready;
    await first.close();
    expect(calls, ['first:true', 'second:true']);
    await second.close();
    expect(calls.last, 'second:false');
  });

  test('timed out native request settles before balanced is sent', () async {
    final pending = Completer<void>();
    final calls = <bool>[];
    final lease = OtaPriorityQueue().acquire(isCurrent: () => true,
      request: (high) async {
        calls.add(high);
        if (high) await pending.future;
      });
    await expectLater(lease.ready.timeout(const Duration(milliseconds: 1)), throwsA(isA<TimeoutException>()));
    final closed = lease.close();
    await Future<void>.delayed(Duration.zero);
    expect(calls, [true]);
    pending.complete();
    await closed;
    expect(calls, [true, false]);
  });

  test('native failure is surfaced and does not poison subsequent owners', () async {
    final queue = OtaPriorityQueue();
    final first = queue.acquire(isCurrent: () => true,
      request: (high) async { if (high) throw StateError('native'); });
    await expectLater(first.ready, throwsStateError);
    await first.close();
    final next = queue.acquire(isCurrent: () => true, request: (_) async {});
    await next.ready;
    await next.close();
  });
}
