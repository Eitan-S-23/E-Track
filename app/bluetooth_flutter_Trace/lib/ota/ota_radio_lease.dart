import 'dart:async';

/// A bounded wait does not cancel native work. The owner retains the queue
/// until that work settles, even when the caller has already closed its lease.
class OtaRadioLease {
  OtaRadioLease(this.ready, this._release);

  final Future<void> ready;
  final Future<void> Function() _release;
  Future<void>? _closed;

  Future<void> close() => _closed ??= _release();
}

class OtaPriorityQueue {
  Future<void> _tail = Future<void>.value();
  Object? _owner;

  Future<void> _enqueue(Future<void> Function() action) {
    final task = _tail.then((_) => action());
    _tail = task.then<void>((_) {}, onError: (Object _, StackTrace __) {});
    return task;
  }

  OtaRadioLease acquire({
    required bool Function() isCurrent,
    required Future<void> Function(bool high) request,
  }) {
    final token = Object();
    _owner = token;
    var released = false;
    var attempted = false;
    bool owns() => identical(_owner, token) && isCurrent();
    final ready = _enqueue(() async {
      if (released || !owns()) throw StateError('ota-priority-owner-changed');
      attempted = true;
      await request(true);
      if (released || !owns()) throw StateError('ota-priority-owner-changed');
    });
    return OtaRadioLease(ready, () {
      released = true;
      return _enqueue(() async {
        try {
          if (attempted && owns()) await request(false);
        } finally {
          if (identical(_owner, token)) _owner = null;
        }
      });
    });
  }
}
