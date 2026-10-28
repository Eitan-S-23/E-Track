import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:math';

import 'package:crypto/crypto.dart';
import 'package:flutter/foundation.dart';
import 'package:path_provider/path_provider.dart';

import 'ota_observation_log.dart';

/// Explicit, Release-capable observation only. Never drives the OTA state machine.
/// Published lines have already been flushed to app-owned storage. A failed
/// writer stops telemetry, not an in-flight upgrade, and cannot become healthy.
class OtaP35Recorder {
  OtaP35Recorder({this.directoryProvider, this.writerFactory,
    void Function(String)? emit, this.maxBytes = 128 * 1024 * 1024,
    this.maxPending = 256, this.maxDuration = const Duration(hours: 1)})
      : _emit = emit ?? ((line) => debugPrintSynchronously(line));

  final Future<Directory> Function()? directoryProvider;
  final Future<OtaObservationWriter> Function(File)? writerFactory;
  final void Function(String) _emit;
  final int maxBytes, maxPending;
  final Duration maxDuration;
  final status = ValueNotifier<String>('off');
  final Stopwatch _clock = Stopwatch();
  final List<String> _pending = [];
  OtaObservationWriter? _writer;
  Future<void>? _draining, _stopping;
  Completer<void>? _opened;
  Timer? _heartbeat, _deadline;
  Map<String, Object?> Function()? _snapshot;
  String? captureId, error;
  File? file;
  int _seq = 0, _bytes = 0, _written = 0, lost = 0;
  bool _starting = false, _accepting = false, _stopRequested = false;
  late _DigestSink _digest;
  late ByteConversionSink _hash;
  bool get active => _accepting;
  bool get healthy => active && error == null;

  Future<bool> start(Map<String, Object?> Function() snapshot) async {
    if (_starting || active || captureId != null || _stopRequested) return false;
    _starting = true;
    _opened = Completer<void>();
    status.value = 'starting';
    try {
      final base = await (directoryProvider?.call() ?? _defaultDirectory());
      final root = Directory('${base.path}/p35-observations');
      await root.create(recursive: true);
      if (await root.list().length >= 32) throw StateError('archive-full');
      captureId = List.generate(16, (_) => Random.secure().nextInt(256))
          .map((b) => b.toRadixString(16).padLeft(2, '0')).join();
      file = File('${root.path}/$captureId.jsonl');
      await file!.create(exclusive: true);
      _writer = await (writerFactory?.call(file!) ?? _open(file!));
      _digest = _DigestSink();
      _hash = sha256.startChunkedConversion(_digest);
      final header = 'OTA_P35_CAPTURE ${jsonEncode({
        'schema': 1, 'kind': 'open', 'captureId': captureId,
      })}';
      await _writer!.append(utf8.encode('$header\n'));
      await _writer!.flush();
      _emit(header);
      if (_stopRequested) return false;
      _snapshot = snapshot;
      _clock.start();
      _accepting = true;
      status.value = 'recording';
      record();
      _heartbeat = Timer.periodic(const Duration(seconds: 1), (_) => record('heartbeat'));
      _deadline = Timer(maxDuration, () {
        _fail('duration-limit');
        unawaited(stop());
      });
      return true;
    } catch (_) {
      _fail('open-failed');
      final writer = _writer;
      _writer = null;
      try { await writer?.close(); } catch (_) { /* Failure is already latched. */ }
      return false;
    } finally {
      _starting = false;
      _opened!.complete();
    }
  }

  void record([String event = 'state']) {
    if (!healthy) return;
    try {
      final row = <String, Object?>{..._snapshot!(), 'schema': 1,
        'captureId': captureId, 'seq': ++_seq, 'monoUs': _clock.elapsedMicroseconds,
        'event': event, 'healthy': true, 'lost': 0, 'error': null};
      final line = 'OTA_P35_STATE ${jsonEncode(row)}\n';
      final length = utf8.encode(line).length;
      if (length > 3500 || _bytes + length > maxBytes || _pending.length >= maxPending) {
        lost++;
        _fail('capture-limit');
        return;
      }
      _bytes += length;
      _pending.add(line);
      _drain();
    } catch (_) {
      lost++;
      _fail('snapshot-failed');
    }
  }

  void _drain() {
    if (_draining != null) return;
    _draining = _writePending().whenComplete(() => _draining = null);
  }

  Future<void> _writePending() async {
    try {
      while (_pending.isNotEmpty) {
        final batch = List<String>.of(_pending);
        _pending.clear();
        final bytes = utf8.encode(batch.join());
        await _writer!.append(bytes);
        await _writer!.flush();
        _hash.add(bytes);
        _written += batch.length;
        // No throttled debugPrint queue between persistence and the consumer.
        for (final line in batch) { _emit(line.trimRight()); }
      }
    } catch (_) {
      lost += _seq - _written;
      _pending.clear();
      _fail('write-failed');
    }
  }

  void _fail(String code) {
    error ??= code;
    status.value = 'failed:$error';
    _heartbeat?.cancel();
    _deadline?.cancel();
    try {
      _emit('OTA_P35_ERROR ${jsonEncode({
        'captureId': captureId, 'error': error, 'lost': lost,
      })}');
    } catch (_) { /* Missing heartbeat still fails the host closed. */ }
  }

  void fail(String code) { if (active) _fail(code); }

  Future<void> stop() {
    _stopRequested = true;
    return _stopping ??= _stop();
  }

  Future<void> _stop() async {
    await _opened?.future;
    _accepting = false;
    _heartbeat?.cancel();
    _deadline?.cancel();
    await _draining;
    final writer = _writer;
    if (writer == null) return;
    try {
      _hash.close();
      final footer = 'OTA_P35_CAPTURE ${jsonEncode({
        'schema': 1, 'kind': 'close', 'captureId': captureId,
        'records': _written, 'sha256': _digest.value.toString(),
        'healthy': error == null && lost == 0 && _written == _seq,
        'lost': lost, 'error': error,
      })}';
      await writer.append(utf8.encode('$footer\n'));
      await writer.flush();
      _emit(footer);
    } catch (_) {
      _fail('close-failed');
    } finally {
      try { await writer.close(); } catch (_) { _fail('close-failed'); }
      _writer = null;
      if (error == null) status.value = 'closed';
    }
  }

  static Future<Directory> _defaultDirectory() async {
    // Android shell can retrieve these app-owned files without run-as or a
    // debuggable APK. Uninstall/clear-data still removes them; never auto-delete.
    final directory = Platform.isAndroid ? await getExternalStorageDirectory()
        : await getApplicationSupportDirectory();
    if (directory == null) throw StateError('storage-unavailable');
    return directory;
  }

  static Future<OtaObservationWriter> _open(File file) async =>
      _Writer(await file.open(mode: FileMode.writeOnly));
}

class _Writer implements OtaObservationWriter {
  _Writer(this.file);
  final RandomAccessFile file;
  @override
  Future<void> append(List<int> bytes) async { await file.writeFrom(bytes); }
  @override
  Future<void> flush() async { await file.flush(); }
  @override
  Future<void> close() async { await file.close(); }
}

class _DigestSink implements Sink<Digest> {
  Digest? value;
  @override
  void add(Digest data) { value = data; }
  @override
  void close() {}
}
