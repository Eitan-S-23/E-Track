import 'dart:async';
import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:path_provider/path_provider.dart';

import 'ota_observation_log.dart';

class OtaDiagnosticStatus {
  const OtaDiagnosticStatus({this.enabled = false, this.ready = false,
    this.records = 0, this.producerLines = 0, this.error, this.lastExport,
    this.fromPreviousProcess = false});
  final bool enabled;
  final bool ready;
  final int records;
  final int producerLines;
  final String? error;
  final File? lastExport;
  final bool fromPreviousProcess;
}

/// Development-only file capture; it never supplies OTA state or timings.
class OtaDiagnostics {
  OtaDiagnostics();
  static final _shared = OtaDiagnostics();
  static final _zoneKey = Object();
  static OtaDiagnostics get current =>
      Zone.current[_zoneKey] as OtaDiagnostics? ?? _shared;

  @visibleForTesting
  static T withInstance<T>(OtaDiagnostics instance, T Function() body) =>
      runZoned(body, zoneValues: {_zoneKey: instance});

  final status = ValueNotifier(const OtaDiagnosticStatus());
  OtaObservationLog? _log;
  bool _initialized = false;
  String? _exportError;
  bool get enabled => status.value.enabled;

  Future<void> initialize({required bool enabled, required String target,
      required String sentinel, Future<Directory> Function()? directoryProvider,
      Future<OtaObservationWriter> Function(File)? writerFactory}) async {
    if (_initialized) return;
    _initialized = true;
    if (!enabled) return;
    status.value = const OtaDiagnosticStatus(enabled: true);
    try {
      final base = await (directoryProvider ?? getApplicationSupportDirectory)();
      final root = Directory('${base.path}/p34-observations');
      final previous = await OtaObservationLog.latestSnapshot(root);
      status.value = OtaDiagnosticStatus(enabled: true, lastExport: previous,
          fromPreviousProcess: previous != null);
      _log = await OtaObservationLog.open(
        root: root, target: target,
        sentinel: sentinel, writerFactory: writerFactory,
        onCheckpoint: (value) {
          status.value = OtaDiagnosticStatus(enabled: true,
            ready: value.healthy && _exportError == null, records: value.records,
            producerLines: value.producerLines, error: value.error ?? _exportError,
            lastExport: status.value.lastExport,
            fromPreviousProcess: status.value.fromPreviousProcess);
        },
      );
    } catch (_) {
      status.value = OtaDiagnosticStatus(enabled: true,
          error: 'capture-initialization', lastExport: status.value.lastExport,
          fromPreviousProcess: status.value.fromPreviousProcess);
    }
  }

  void record(String line) {
    if (!enabled) return;
    _log?.record(line);
  }

  Future<bool> beginUpgrade(Map<String, Object?> input) async {
    if (!enabled) return true;
    final log = _log;
    if (log == null) return false;
    return log.beginUpgrade(input);
  }

  Future<void> finishUpgrade({required bool completed}) async {
    final log = _log;
    if (!enabled || log == null) return;
    await log.endUpgrade(completed: completed);
    // Store an immutable snapshot before USB, page or process lifetime changes.
    try {
      await exportSnapshot();
    } catch (_) {
      _exportFailed();
    }
  }

  Future<File> exportSnapshot() async {
    final log = _log;
    if (!enabled || log == null) throw StateError('diagnostic capture unavailable');
    try {
      final output = await log.exportSnapshot();
      final old = status.value;
      status.value = OtaDiagnosticStatus(enabled: true, ready: old.ready,
        records: old.records, producerLines: old.producerLines,
        error: old.error, lastExport: output);
      return output;
    } catch (_) {
      _exportFailed();
      rethrow;
    }
  }

  void _exportFailed() {
    _exportError = 'capture-export';
    final old = status.value;
    status.value = OtaDiagnosticStatus(enabled: true, ready: false,
      records: old.records, producerLines: old.producerLines,
      error: old.error ?? 'capture-export', lastExport: old.lastExport,
      fromPreviousProcess: old.fromPreviousProcess);
  }

  Future<void> close() async {
    await _log?.close();
  }
}

void emitOtaObservation(String line) {
  // Timestamp construction stays at the caller; disk I/O is never awaited here.
  OtaDiagnostics.current.record(line);
  debugPrint(line);
}
