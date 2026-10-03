import 'dart:async';

import 'package:ble_monitor/ota/ota_ble_transport.dart';
import 'package:ble_monitor/ota/ota_probe_retry.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  const timeout = OtaTransportException('silent INFO', code: 'TIMEOUT');

  test('retries a settled timeout without replacing the binding', () async {
    var calls = 0;
    expect(await retryInfoOnCurrentLink<int>(
      query: () async { if (++calls < 3) throw timeout; return 42; },
      isCurrent: () => true,
      interval: Duration.zero,
    ), 42);
    expect(calls, 3);
  });

  for (final limit in [1, 3, 12]) {
    test('persistent timeout is bounded to $limit attempts', () async {
      var calls = 0;
      await expectLater(retryInfoOnCurrentLink<int>(
        query: () async { calls++; throw timeout; },
        isCurrent: () => true,
        interval: Duration.zero,
        maxAttempts: limit,
      ), throwsA(same(timeout)));
      expect(calls, limit);
    });
  }

  for (final code in ['WRITE_TIMEOUT', 'DISCONNECTED', 'MALFORMED_INFO', 'UNKNOWN']) {
    test('does not retry $code', () async {
      var calls = 0;
      final error = OtaTransportException('not a response timeout', code: code);
      await expectLater(retryInfoOnCurrentLink<int>(
        query: () async { calls++; throw error; },
        isCurrent: () => true,
        interval: Duration.zero,
      ), throwsA(same(error)));
      expect(calls, 1);
    });
  }

  test('invalid owner sends nothing', () async {
    var calls = 0;
    expect(await retryInfoOnCurrentLink<int>(
      query: () async => ++calls,
      isCurrent: () => false,
      interval: Duration.zero,
    ), isNull);
    expect(calls, 0);
  });

  test('late successful response cannot revive a cancelled owner', () async {
    final reply = Completer<int>();
    var current = true;
    final result = retryInfoOnCurrentLink<int>(
      query: () => reply.future,
      isCurrent: () => current,
      interval: Duration.zero,
      maxAttempts: 12,
    );
    current = false;
    reply.complete(42);
    expect(await result, isNull);
  });

  test('binding invalidated while waiting cannot retry', () async {
    var current = true;
    var calls = 0;
    expect(await retryInfoOnCurrentLink<int>(
      query: () async {
        calls++;
        scheduleMicrotask(() => current = false);
        throw timeout;
      },
      isCurrent: () => current,
      interval: Duration.zero,
    ), isNull);
    expect(calls, 1);
  });

  test('outer abandonment during retry delay prevents the next write', () async {
    var current = true;
    var calls = 0;
    final result = retryInfoOnCurrentLink<int>(
      query: () async {
        calls++;
        Timer.run(() => current = false);
        throw timeout;
      },
      isCurrent: () => current,
      interval: const Duration(milliseconds: 20),
      maxAttempts: 12,
    );
    expect(await result, isNull);
    expect(calls, 1);
  });

  test('rejects unbounded policy before calling the transport', () async {
    for (final limit in [0, 13]) {
      await expectLater(retryInfoOnCurrentLink<int>(
        query: () async => 42,
        isCurrent: () => true,
        interval: Duration.zero,
        maxAttempts: limit,
      ), throwsRangeError);
    }
  });

  test('expanded diagnostic budget reaches a later response on one binding', () async {
    var calls = 0;
    expect(await retryInfoOnCurrentLink<int>(
      query: () async { if (++calls < 12) throw timeout; return 42; },
      isCurrent: () => true,
      interval: Duration.zero,
      maxAttempts: 12,
    ), 42);
    expect(calls, 12);
  });
}
