import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:crypto/crypto.dart';
import 'package:flutter/foundation.dart';

import 'ota_diagnostics.dart';

/// Diagnostic correlation only. Never used as a query lock or cancellation token.
class OtaQueryTrace {
  OtaQueryTrace._(this.diagnostics)
      : id = '${DateTime.now().microsecondsSinceEpoch}-${++_nextId}',
        _clock = Stopwatch()..start();

  static final _zoneKey = Object();
  static int _nextId = 0;
  static OtaQueryTrace? get current => Zone.current[_zoneKey] as OtaQueryTrace?;
  static OtaQueryTrace? start(OtaDiagnostics diagnostics, String origin) {
    if (!diagnostics.enabled) return null;
    final trace = OtaQueryTrace._(diagnostics);
    trace.event('start', {'origin': origin});
    return trace;
  }

  final OtaDiagnostics diagnostics;
  final String id;
  final Stopwatch _clock;
  int _sequence = 0;
  Future<File?>? _snapshot;

  static String digest(String text) => sha256.convert(utf8.encode(text)).toString();

  Future<T> bind<T>(Future<T> Function() body) =>
      runZoned(body, zoneValues: {_zoneKey: this});

  void event(String stage, [Map<String, Object?> fields = const {}]) {
    // Never serialize exception messages, URLs, headers or free-form bodies.
    Object? safe(Object? value) {
      if (value == null || value is bool || value is int) return value;
      if (value is String && RegExp(r'^[A-Za-z0-9_.-]{1,128}$').hasMatch(value)) {
        return value;
      }
      return 'redacted';
    }
    final line = 'OTA_QUERY ${jsonEncode({
      'schema': 1, 'queryId': id, 'seq': ++_sequence,
      'elapsedUs': _clock.elapsedMicroseconds, 'stage': safe(stage),
      'fields': {for (final entry in fields.entries) entry.key: safe(entry.value)},
    })}';
    diagnostics.record(line);
    debugPrint(line);
  }

  Future<void> checkpoint() async {
    try {
      await diagnostics.checkpointQuery();
    } catch (_) {
      event('capture_failure', {'operation': 'checkpoint'});
    }
  }

  // One immutable query-only snapshot per invocation, separate from OTA exports.
  Future<File?> snapshot() => _snapshot ??= _saveSnapshot();

  Future<File?> _saveSnapshot() async {
    try {
      event('snapshot_requested');
      return await diagnostics.checkpointQuery(snapshot: true);
    } catch (_) {
      event('capture_failure', {'operation': 'snapshot'});
      await checkpoint();
      return null;
    }
  }
}
