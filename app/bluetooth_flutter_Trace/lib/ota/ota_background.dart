import 'dart:async';
import 'dart:io';

import 'package:flutter/services.dart';

/// A process-unique operation identity, never reconstructed from cached progress.
class OtaTaskKey {
  const OtaTaskKey({required this.taskId, required this.generation,
    required this.deviceToken, required this.packageSha256});

  final String taskId;
  final int generation;
  final String deviceToken;
  final String packageSha256;

  Map<String, Object> toMap() => {
    'taskId': taskId, 'generation': generation,
    'deviceToken': deviceToken, 'packageSha256': packageSha256,
  };

  bool matches(Object? value) => value is Map &&
      value['taskId'] == taskId && value['generation'] == generation &&
      value['deviceToken'] == deviceToken &&
      value['packageSha256'] == packageSha256;
}

/// Both UI and native notification project this owner-produced snapshot.
class OtaTaskSnapshot {
  const OtaTaskSnapshot({required this.key, required this.revision,
    required this.phase, required this.totalBytes, required this.durableBytes,
    required this.receivedBytes, required this.canCancel,
    required this.targetVerified, required this.backgroundAcquired,
    this.backgroundReason});

  final OtaTaskKey key;
  final int revision;
  final String phase;
  final int totalBytes;
  final int durableBytes;
  final int receivedBytes;
  final bool canCancel;
  final bool targetVerified;
  final bool backgroundAcquired;
  final String? backgroundReason;

  double? get progress => totalBytes <= 0 ? null : switch (phase) {
    'downloading' => (receivedBytes / totalBytes).clamp(0.0, 1.0),
    'transferring' => (durableBytes / totalBytes).clamp(0.0, 1.0),
    _ => null,
  };

  String get label => switch (phase) {
    'downloading' => 'Downloading firmware',
    'checkingPackage' => 'Verifying package',
    'transferring' => 'Transferring (MCU durable confirmation)',
    'applying' => 'Device applying package; not yet verified',
    'reconnecting' => 'Waiting for device reboot and reconnect',
    'verifying' => 'Verifying target version and raw SHA-256',
    'completed' => 'Target firmware identity verified',
    'cancelled' => 'Cancelled',
    'paused' => 'Safely paused; return to foreground',
    'ready' => 'Package verified; ready to transfer',
    _ => 'Device OTA stopped',
  };

  Map<String, Object?> toMap() => {
    ...key.toMap(), 'revision': revision, 'phase': phase,
    'totalBytes': totalBytes, 'durableBytes': durableBytes,
    'receivedBytes': receivedBytes, 'canCancel': canCancel,
    'targetVerified': targetVerified, 'label': label,
  };
}

/// The native reply is sent only AFTER startForeground + a same-engine owner
/// probe. A request return, cached engine reference or notification is not ACK.
class OtaBackgroundClient {
  OtaBackgroundClient({MethodChannel? channel, bool? supported,
    this.acquireTimeout = const Duration(seconds: 6),
    this.checkInterval = const Duration(seconds: 3)})
      : _channel = channel ?? const MethodChannel('trace/device_ota'),
        supported = supported ?? Platform.isAndroid;

  final MethodChannel _channel;
  final bool supported;
  final Duration acquireTimeout;
  final Duration checkInterval;
  OtaTaskKey? _key;
  bool _acquired = false;
  bool _closed = false;
  int _epoch = 0;
  Timer? _checkTimer;
  Timer? _publishTimer;
  OtaTaskSnapshot? _pending;
  String? reason;
  bool Function()? _ownerLive;
  void Function(String reason)? _onLost;
  Future<void> Function()? _onCancel;
  void Function()? _onOpen;
  bool _checking = false;

  bool get isAcquired => _acquired && !_closed;

  Future<bool> acquire(OtaTaskSnapshot initial, {
    required bool Function() ownerLive,
    required void Function(String reason) onLost,
    required Future<void> Function() onCancel,
    required void Function() onOpen,
  }) async {
    if (_closed) return false;
    final key = initial.key;
    final epoch = ++_epoch;
    _key = key;
    _acquired = false;
    reason = null;
    _ownerLive = ownerLive;
    _onLost = onLost;
    _onCancel = onCancel;
    _onOpen = onOpen;
    if (!supported) {
      reason = 'PLATFORM_UNSUPPORTED';
      return false;
    }
    _channel.setMethodCallHandler(_handle);
    try {
      final reply = await _channel.invokeMethod<Object?>('acquire', initial.toMap())
          .timeout(acquireTimeout);
      if (_closed || epoch != _epoch || !identical(_key, key)) {
        await _releaseNative(key);
        return false;
      }
      if (reply is! Map || reply['status'] != 'ACQUIRED' ||
          !key.matches(reply) || !ownerLive()) {
        reason = reply is Map ? '${reply['reason'] ?? 'OWNER_UNAVAILABLE'}'
            : 'INVALID_ACQUIRE_REPLY';
        await _releaseNative(key);
        return false;
      }
      _acquired = true;
      _checkTimer = Timer.periodic(checkInterval, (_) => unawaited(_check(epoch)));
      return true;
    } catch (error) {
      if (epoch == _epoch && !_closed) {
        reason = error is TimeoutException ? 'ACQUIRE_TIMEOUT' : 'SERVICE_UNAVAILABLE';
      }
      await _releaseNative(key);
      return false;
    }
  }

  Future<Object?> _handle(MethodCall call) async {
    final key = _key;
    if (_closed || key == null || !key.matches(call.arguments)) return false;
    switch (call.method) {
      case 'probe':
        return {'ownerLive': _ownerLive?.call() == true, ...key.toMap()};
      case 'lost':
        _lose('EXECUTION_OWNERSHIP_LOST');
        return true;
      case 'cancel':
        // The owner rechecks the CURRENT phase before the first cancel await.
        await _onCancel?.call();
        return true;
      case 'open':
        _onOpen?.call();
        return true;
      default:
        throw MissingPluginException('Unknown device OTA callback');
    }
  }

  Future<void> _check(int epoch) async {
    if (!isAcquired || epoch != _epoch || _checking) return;
    _checking = true;
    try {
      final reply = await _channel.invokeMethod<Object?>('check', _key!.toMap())
          .timeout(const Duration(seconds: 2));
      if (epoch == _epoch && reply != true) _lose('SERVICE_OR_PERMISSION_LOST');
    } catch (_) {
      if (epoch == _epoch) _lose('SERVICE_CHECK_FAILED');
    } finally {
      _checking = false;
    }
  }

  void _lose(String value) {
    if (_closed || reason == value && !_acquired) return;
    _acquired = false;
    reason = value;
    _checkTimer?.cancel();
    _publishTimer?.cancel();
    _onLost?.call(value);
  }

  void publish(OtaTaskSnapshot snapshot, {bool urgent = false}) {
    if (!isAcquired || !_key!.matches(snapshot.key.toMap())) return;
    _pending = snapshot;
    if (urgent) {
      _publishTimer?.cancel();
      _publishTimer = null;
      unawaited(_flush());
    } else {
      _publishTimer ??= Timer(const Duration(milliseconds: 250), () {
        _publishTimer = null;
        unawaited(_flush());
      });
    }
  }

  Future<void> _flush() async {
    final pending = _pending;
    final epoch = _epoch;
    _pending = null;
    if (pending == null || !isAcquired) return;
    try {
      final ok = await _channel.invokeMethod<bool>('publish', pending.toMap())
          .timeout(const Duration(seconds: 2));
      if (ok != true && epoch == _epoch) _lose('NOTIFICATION_UNAVAILABLE');
    } catch (_) {
      if (epoch == _epoch) _lose('NOTIFICATION_UPDATE_FAILED');
    }
  }

  Future<void> _releaseNative(OtaTaskKey key) async {
    if (!supported) return;
    try {
      await _channel.invokeMethod<void>('release', key.toMap())
          .timeout(const Duration(seconds: 2));
    } catch (_) {
      // Native owner heartbeat and its absolute lease still bound resource life.
    }
  }

  Future<void> release(OtaTaskKey key) async {
    if (_key?.matches(key.toMap()) == true) {
      ++_epoch;
      _acquired = false;
      _key = null;
      _checkTimer?.cancel();
      _publishTimer?.cancel();
      _pending = null;
      _ownerLive = null;
      _onLost = null;
      _onCancel = null;
      _onOpen = null;
    }
    await _releaseNative(key);
  }

  Future<void> close() async {
    _closed = true;
    final key = _key;
    if (key != null) await release(key);
    if (supported) _channel.setMethodCallHandler(null);
  }
}
