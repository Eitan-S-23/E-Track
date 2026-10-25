import 'dart:async';

/// Reconnect known devices only. This never starts or resumes an OTA task.
class BluetoothReconnect {
  BluetoothReconnect({required this.connect});

  final Future<bool> Function(String address) connect;
  static const delays = [1, 2, 4, 8, 16];
  final _targets = <String, _ReconnectTarget>{};
  final _active = <Future<void>>{};
  bool _available = false;
  bool _closed = false;
  int _holds = 0;

  void remember(String address) {
    if (_closed) return;
    final target = _targets.putIfAbsent(address.toLowerCase(),
        () => _ReconnectTarget(address));
    linkChanged(address, true);
    target.attempts = 0;
  }

  void forget(String address) {
    _targets.remove(address.toLowerCase())?.timer?.cancel();
  }

  void adapterChanged(bool available) {
    if (_closed || _available == available) return;
    _available = available;
    for (final target in _targets.values) {
      target.timer?.cancel();
      target.timer = null;
      if (!available) target.connected = false;
      target.attempts = 0;
      _schedule(target);
    }
  }

  void linkChanged(String address, bool connected) {
    final target = _targets[address.toLowerCase()];
    if (target == null || _closed) return;
    target.connected = connected;
    if (connected) {
      target.attempts = 0;
      target.timer?.cancel();
      target.timer = null;
    } else {
      _schedule(target);
    }
  }

  /// Claim synchronously, then await [settled] before starting exclusive BLE IO.
  void Function() hold() {
    _holds++;
    for (final target in _targets.values) {
      target.timer?.cancel();
      target.timer = null;
    }
    var released = false;
    return () {
      if (released) return;
      released = true;
      _holds--;
      for (final target in _targets.values) {
        _schedule(target);
      }
    };
  }

  Future<void> get settled async { await Future.wait(_active.toList()); }

  void _schedule(_ReconnectTarget target) {
    if (_closed || !_available || _holds != 0 || target.connected ||
        target.running || target.timer != null || target.attempts >= delays.length ||
        !identical(_targets[target.address.toLowerCase()], target)) return;
    target.timer = Timer(Duration(seconds: delays[target.attempts]), () {
      target.timer = null;
      target.running = true;
      target.attempts++;
      late final Future<void> future;
      future = _attempt(target).whenComplete(() => _active.remove(future));
      _active.add(future);
    });
  }

  Future<void> _attempt(_ReconnectTarget target) async {
    var connected = false;
    try {
      // The platform connector has its own finite native connection timeout.
      connected = await connect(target.address);
    } catch (_) {
      connected = false;
    } finally {
      target.running = false;
      if (!_closed && identical(_targets[target.address.toLowerCase()], target)) {
        target.connected = connected && _available;
        if (target.connected) target.attempts = 0;
        _schedule(target);
      }
    }
  }

  void dispose() {
    _closed = true;
    for (final target in _targets.values) {
      target.timer?.cancel();
    }
    _targets.clear();
  }
}

class _ReconnectTarget {
  _ReconnectTarget(this.address);
  final String address;
  bool connected = true;
  bool running = false;
  int attempts = 0;
  Timer? timer;
}
