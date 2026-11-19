import 'dart:async';

class CompanionRecoveryExpired implements Exception {
  const CompanionRecoveryExpired(this.stage);
  final String stage;
}

/// A deadline revokes the attempt, not just the caller's wait. The radio owner
/// must acknowledge cleanup before a replacement attempt is admitted.
class CompanionRecoveryAttempt {
  CompanionRecoveryAttempt(this.id, Duration deadline) {
    _timer = Timer(deadline, cancel);
  }

  final String id;
  final _elapsed = Stopwatch()..start();
  final _cancelled = Completer<void>();
  late final Timer _timer;
  String stage = 'INITIALIZING';
  bool current = true;
  int get elapsedMs => _elapsed.elapsedMilliseconds;

  Future<T> wait<T>(Future<T> operation) async {
    final value = await Future.any([
      operation,
      _cancelled.future.then<T>((_) => throw CompanionRecoveryExpired(stage)),
    ]);
    if (!current) throw CompanionRecoveryExpired(stage);
    return value;
  }

  void cancel() {
    current = false;
    _timer.cancel();
    if (!_cancelled.isCompleted) _cancelled.complete();
  }

  void finish() {
    current = false;
    _timer.cancel();
    _elapsed.stop();
  }
}
