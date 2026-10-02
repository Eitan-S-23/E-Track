import 'dart:async';

import 'ota_radio_lease.dart';

/// Optional development gate. Scan demand survives an OTA pause, but an
/// explicit stop, expired scan timeout or disposal prevents automatic restart.
class OtaScanPause {
  OtaScanPause({
    required this.startNative,
    required this.stopNative,
    required this.isScanning,
    Duration Function()? now,
  }) {
    final clock = Stopwatch()..start();
    _now = now ?? (() => clock.elapsed);
  }

  final Future<void> Function(Duration? timeout) startNative;
  final Future<void> Function() stopNative;
  final bool Function() isScanning;
  late final Duration Function() _now;
  final Set<Object> _owners = {};
  Future<void> _tail = Future<void>.value();
  bool _requested = false;
  bool _disposed = false;
  Duration? _deadline;

  Future<void> _enqueue(Future<void> Function() action) {
    final task = _tail.then((_) => action());
    _tail = task.then<void>((_) {}, onError: (Object _, StackTrace __) {});
    return task;
  }

  Future<void> _sync({bool forceStop = false}) async {
    final deadline = _deadline;
    final remaining = deadline == null ? null : deadline - _now();
    if (remaining != null && remaining <= Duration.zero) _requested = false;
    if (_disposed || _owners.isNotEmpty || !_requested) {
      if (forceStop || isScanning()) await stopNative();
      return;
    }
    if (!isScanning()) await startNative(remaining);
  }

  Future<void> start({Duration? timeout}) {
    if (_disposed) return Future<void>.error(StateError('ota-scan-disposed'));
    if (timeout != null && timeout <= Duration.zero) {
      return Future<void>.error(ArgumentError.value(timeout, 'timeout'));
    }
    if (_deadline != null && _deadline! <= _now()) _requested = false;
    if (!_requested) {
      _requested = true;
      _deadline = timeout == null ? null : _now() + timeout;
    }
    return _enqueue(_sync);
  }

  Future<void> stop() {
    _requested = false;
    _deadline = null;
    return _enqueue(() => _sync(forceStop: true));
  }

  OtaRadioLease pause() {
    if (_disposed) throw StateError('ota-scan-disposed');
    final token = Object();
    _owners.add(token);
    final ready = _enqueue(() => _sync(forceStop: true));
    return OtaRadioLease(ready, () {
      _owners.remove(token);
      return _enqueue(_sync);
    });
  }

  Future<void> dispose() {
    _disposed = true;
    _requested = false;
    return _enqueue(() => _sync(forceStop: true));
  }
}
