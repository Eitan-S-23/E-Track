import 'dart:async';
import 'package:ble_monitor/companion/companion_recovery.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('an already resolved result cannot win after the attempt was revoked', () async {
    final attempt = CompanionRecoveryAttempt('revoked', const Duration(seconds: 1));
    attempt.cancel();
    await expectLater(attempt.wait(Future.value(42)), throwsA(isA<CompanionRecoveryExpired>()));
  });

  testWidgets('overall deadline revokes stalled work and late completion cannot advance it', (tester) async {
    final attempt = CompanionRecoveryAttempt('first', const Duration(seconds: 2));
    attempt.stage = 'VERIFYING_DEVICE';
    final pending = Completer<int>();
    var published = 0;
    CompanionRecoveryExpired? expired;
    final operation = () async {
      try { published = await attempt.wait(pending.future); }
      on CompanionRecoveryExpired catch (error) { expired = error; }
    }();
    await tester.pump(const Duration(seconds: 3));
    await operation;
    expect(expired?.stage, 'VERIFYING_DEVICE');
    expect(attempt.current, isFalse);
    pending.complete(42); await tester.pump();
    expect(published, 0);
  });

  testWidgets('stage changes do not extend the shared deadline', (tester) async {
    final attempt = CompanionRecoveryAttempt('second', const Duration(seconds: 3));
    await tester.pump(const Duration(seconds: 2));
    attempt.stage = 'DISCOVERING';
    await tester.pump(const Duration(seconds: 2));
    expect(attempt.current, isFalse);
  });

  testWidgets('completed work retires its deadline without canceling another attempt', (tester) async {
    final old = CompanionRecoveryAttempt('old', const Duration(seconds: 1));
    expect(await old.wait(Future.value(7)), 7);
    old.finish();
    final replacement = CompanionRecoveryAttempt('new', const Duration(seconds: 4));
    await tester.pump(const Duration(seconds: 2));
    expect(replacement.current, isTrue);
    old.cancel();
    expect(replacement.current, isTrue);
    replacement.finish();
  });
}
