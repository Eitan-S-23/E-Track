import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:math';
import 'dart:typed_data';

import 'package:crypto/crypto.dart';

abstract class OtaObservationWriter {
  Future<void> append(List<int> bytes);
  Future<void> flush();
  Future<void> close();
}

class _FileWriter implements OtaObservationWriter {
  _FileWriter(this.file);
  final RandomAccessFile file;

  @override
  Future<void> append(List<int> bytes) async {
    await file.writeFrom(bytes);
  }

  @override
  Future<void> flush() async {
    await file.flush();
  }

  @override
  Future<void> close() async {
    await file.close();
  }
}

class OtaObservationCheckpoint {
  const OtaObservationCheckpoint({
    required this.records,
    required this.bytes,
    required this.producerLines,
    required this.upgradeStarts,
    required this.upgradeEnds,
    required this.outcome,
    required this.lost,
    required this.error,
  });

  final int records;
  final int bytes;
  final int producerLines;
  final int upgradeStarts;
  final int upgradeEnds;
  final String? outcome;
  final int lost;
  final String? error;
  bool get healthy => lost == 0 && error == null;

  Map<String, Object?> toJson() => {
        'records': records,
        'bytes': bytes,
        'producerLines': producerLines,
        'upgradeStarts': upgradeStarts,
        'upgradeEnds': upgradeEnds,
        'outcome': outcome,
        'lost': lost,
        'error': error,
        'healthy': healthy,
      };
}

/// Append-only, bounded diagnostic data. Never used as protocol state.
class OtaObservationLog {
  OtaObservationLog._({
    required this.root,
    required this.directory,
    required this.captureId,
    required this.writer,
    required this.maxBytes,
    required this.maxPendingBytes,
    required this.maxStoreBytes,
    required this.onCheckpoint,
  });

  static const defaultMaxBytes = 64 * 1024 * 1024;
  static const defaultMaxPendingBytes = 1024 * 1024;
  static const defaultMaxStoreBytes = 256 * 1024 * 1024;
  static const maxLineBytes = 16 * 1024;
  static const _batchBytes = 32 * 1024;
  static const prefixes = [
    'OTA_LINK_SAMPLE ',
    'OTA_LINK_STATS ',
    'OTA_LINK_RETIRE ',
    'OTA_LINK_LATE ',
    'OTA_MONO ',
    'OTA_IDENTITY ',
    'OTA_EXPERIMENT ',
  ];

  final Directory root;
  final Directory directory;
  final String captureId;
  final OtaObservationWriter writer;
  final int maxBytes;
  final int maxPendingBytes;
  final int maxStoreBytes;
  final void Function(OtaObservationCheckpoint)? onCheckpoint;
  File get file => File('${directory.path}/events.jsonl');
  File get healthFile => File('${directory.path}/health.json');

  final BytesBuilder _pending = BytesBuilder(copy: false);
  Future<void> _work = Future<void>.value();
  Timer? _timer;
  bool _timerCheckpoint = false;
  bool _closed = false;
  bool _accepting = true;
  bool _writeFailed = false;
  Future<void>? _closing;
  int _queuedBytes = 0;
  int _records = 0;
  int _bytes = 0;
  int _producerLines = 0;
  int _upgradeStarts = 0;
  int _upgradeEnds = 0;
  int _lost = 0;
  int _exports = 0;
  bool _exporting = false;
  String? _outcome;
  String? _error;

  bool get healthy => _error == null && _lost == 0 && !_closed;
  bool get upgradeActive => _upgradeStarts != _upgradeEnds;

  static Future<OtaObservationLog> open({
    required Directory root,
    required String target,
    required String sentinel,
    int maxBytes = defaultMaxBytes,
    int maxPendingBytes = defaultMaxPendingBytes,
    int maxStoreBytes = defaultMaxStoreBytes,
    Duration flushInterval = const Duration(seconds: 1),
    void Function(OtaObservationCheckpoint)? onCheckpoint,
    Future<OtaObservationWriter> Function(File)? writerFactory,
  }) async {
    if (!RegExp(r'^OTAOBS[0-9a-f]{24}$').hasMatch(sentinel) ||
        target.trim().isEmpty || target.length > 80 ||
        RegExp(r'[\x00-\x1f\x7f]|://').hasMatch(target) ||
        maxBytes < 1024 || maxBytes > defaultMaxBytes ||
        maxPendingBytes < 1024 || maxPendingBytes > defaultMaxPendingBytes ||
        maxStoreBytes < maxBytes || flushInterval <= Duration.zero) {
      throw const FormatException('invalid observation configuration');
    }
    if (await FileSystemEntity.type(root.path, followLinks: false) ==
        FileSystemEntityType.link) {
      throw const FileSystemException('linked observation root');
    }
    await root.create(recursive: true);
    root = Directory(await root.resolveSymbolicLinks());
    final used = await _storageBytes(root);
    final directories = await root.list(followLinks: false)
        .where((entry) => entry is Directory).length;
    if (directories >= 8 || used + maxBytes + 8192 > maxStoreBytes) {
      throw const FileSystemException('observation storage limit');
    }
    final random = Random.secure();
    final suffix = List.generate(12, (_) => random.nextInt(256)
        .toRadixString(16).padLeft(2, '0')).join();
    final id = '${DateTime.now().toUtc().microsecondsSinceEpoch}-$suffix';
    final directory = Directory('${root.path}/$id');
    if (await directory.exists()) {
      throw const FileSystemException('observation identity collision');
    }
    await directory.create();
    final file = File('${directory.path}/events.jsonl');
    await file.create(exclusive: true);
    final writer = writerFactory == null
        ? _FileWriter(await file.open(mode: FileMode.writeOnlyAppend))
        : await writerFactory(file);
    final log = OtaObservationLog._(
      root: root, directory: directory, captureId: id, writer: writer,
      maxBytes: maxBytes, maxPendingBytes: maxPendingBytes,
      maxStoreBytes: maxStoreBytes, onCheckpoint: onCheckpoint,
    );
    log._append('open', {
      'schema': 1,
      'captureId': id,
      'sentinel': sentinel,
      'target': target,
      'pid': pid,
      'platform': Platform.operatingSystem,
      'openedAt': DateTime.now().toUtc().toIso8601String(),
      'limits': {'captureBytes': maxBytes, 'pendingBytes': maxPendingBytes},
    });
    await log.checkpoint();
    if (!log.healthy) {
      await log.close();
      throw const FileSystemException('observation initialization failed');
    }
    log._timer = Timer.periodic(flushInterval, (_) {
      if (log._timerCheckpoint || log._closed) return;
      log._timerCheckpoint = true;
      unawaited(log.checkpoint().whenComplete(() {
        log._timerCheckpoint = false;
      }));
    });
    return log;
  }

  static Future<int> _storageBytes(Directory root) async {
    var bytes = 0;
    var entries = 0;
    await for (final entry in root.list(recursive: true, followLinks: false)) {
      if (++entries > 256 || entry is Link) {
        throw const FileSystemException('unsafe observation storage');
      }
      if (entry is File) bytes += await entry.length();
    }
    return bytes;
  }

  static Future<File?> latestSnapshot(Directory root) async {
    if (!await root.exists()) return null;
    if (await FileSystemEntity.type(root.path, followLinks: false) ==
        FileSystemEntityType.link) {
      return null;
    }
    final candidates = <File>[];
    await for (final directory in root.list(followLinks: false)) {
      if (directory is! Directory || !RegExp(r'^\d{13,20}-[0-9a-f]{24}$')
          .hasMatch(directory.uri.pathSegments.where((s) => s.isNotEmpty).last)) {
        continue;
      }
      await for (final entry in directory.list(followLinks: false)) {
        if (entry is File && RegExp(r'^snapshot-[1-4]\.jsonl$')
            .hasMatch(entry.uri.pathSegments.last)) {
          candidates.add(entry);
        }
      }
      if (candidates.length > 32) return null;
    }
    candidates.sort((a, b) => b.path.compareTo(a.path));
    for (final file in candidates) {
      try {
        final length = await file.length();
        if (length <= 0 || length > defaultMaxBytes + 8192) continue;
        final reader = await file.open();
        try {
          final start = max(0, length - 8192);
          await reader.setPosition(start);
          final tail = await reader.read(length - start);
          if (tail.isEmpty || tail.last != 10) continue;
          final previousNewline = tail.lastIndexOf(10, tail.length - 2);
          if (previousNewline < 0) continue;
          final footer = jsonDecode(utf8.decode(tail.sublist(previousNewline + 1)));
          if (footer is Map<String, dynamic> && footer['kind'] == 'snapshot' &&
              footer['schema'] == 1 && footer['healthy'] == true &&
              footer['upgradeStarts'] == 1 && footer['upgradeEnds'] == 1 &&
              footer['bytes'] == start + previousNewline + 1) {
            return file;
          }
        } finally {
          await reader.close();
        }
      } catch (_) {
        // Interrupted exports stay on disk, but are not presented as finished.
      }
    }
    return null;
  }

  void _fail(String code) {
    _error ??= code;
  }

  bool record(String line) {
    if (!prefixes.any(line.startsWith) ||
        line.contains('\n') || line.contains('\r') || line.contains('\u0000') ||
        RegExp(r'https?://|authorization\s*:|(?:token|signature|api_key)=',
                caseSensitive: false).hasMatch(line) ||
        utf8.encode(line).length > maxLineBytes) {
      _lost++;
      _fail('invalid-record');
      return false;
    }
    if (!_append('line', {'message': line})) return false;
    _producerLines++;
    return true;
  }

  Future<bool> beginUpgrade(Map<String, Object?> input) async {
    // One business invocation per capture. Internal protocol retries stay intact.
    if (!healthy || _exporting || _upgradeStarts != 0 || _producerLines == 0 ||
        _exports >= 4 || !validInput(input)) {
      return false;
    }
    if (!_append('upgrade-start', {'input': input})) return false;
    _upgradeStarts++;
    final status = await checkpoint();
    return status.healthy;
  }

  static bool validInput(Map<String, Object?> input) {
    const fields = {'packageSha256', 'packageBytes', 'currentVersionCode',
      'currentImageSha256', 'targetVersionCode', 'targetImageSha256',
      'deviceAddress', 'appLifecycle'};
    if (input.length != fields.length || !fields.containsAll(input.keys)) {
      return false;
    }
    for (final key in ['packageSha256', 'currentImageSha256', 'targetImageSha256']) {
      final value = input[key];
      if (value is! String || !RegExp(r'^[0-9a-f]{64}$').hasMatch(value)) return false;
    }
    for (final key in ['currentVersionCode', 'targetVersionCode', 'packageBytes']) {
      final value = input[key];
      if (value is! int || value < 0 || value > 0xffffffff) return false;
    }
    if ((input['packageBytes']! as int) < 64) return false;
    final address = input['deviceAddress'];
    return address is String &&
        RegExp(r'^[a-zA-Z0-9:._-]{1,128}$').hasMatch(address) &&
        const {'resumed', 'inactive', 'paused', 'hidden', 'detached', 'unknown'}
            .contains(input['appLifecycle']);
  }

  Future<void> endUpgrade({required bool completed}) async {
    if (_upgradeStarts != 1 || _upgradeEnds != 0) return;
    final outcome = completed ? 'completed' : 'not-completed';
    if (_append('upgrade-end', {'outcome': outcome})) {
      _upgradeEnds++;
      _outcome = outcome;
    }
    await checkpoint();
  }

  bool _append(String kind, Map<String, Object?> fields) {
    if (!healthy || !_accepting) {
      _lost++;
      return false;
    }
    final bytes = utf8.encode('${jsonEncode({
      'seq': _records + 1, 'kind': kind, ...fields,
    })}\n');
    if (_bytes + bytes.length > maxBytes ||
        _queuedBytes + bytes.length > maxPendingBytes) {
      _lost++;
      _fail('capture-capacity');
      return false;
    }
    _records++;
    _bytes += bytes.length;
    _queuedBytes += bytes.length;
    _pending.add(bytes);
    if (_pending.length >= _batchBytes) _scheduleWrite();
    return true;
  }

  void _scheduleWrite() {
    if (_pending.isEmpty) return;
    final chunk = _pending.takeBytes();
    _work = _work.then((_) async {
      try {
        if (!_writeFailed) await writer.append(chunk);
      } catch (_) {
        _writeFailed = true;
        _fail('io-write');
      } finally {
        _queuedBytes -= chunk.length;
      }
    });
  }

  OtaObservationCheckpoint _state() =>
      OtaObservationCheckpoint(
        records: _records, bytes: _bytes, producerLines: _producerLines,
        upgradeStarts: _upgradeStarts, upgradeEnds: _upgradeEnds,
        outcome: _outcome, lost: _lost, error: _error,
      );

  OtaObservationCheckpoint _atBoundary(OtaObservationCheckpoint value) =>
      OtaObservationCheckpoint(records: value.records, bytes: value.bytes,
        producerLines: value.producerLines, upgradeStarts: value.upgradeStarts,
        upgradeEnds: value.upgradeEnds, outcome: value.outcome,
        lost: _lost, error: _error);

  Future<OtaObservationCheckpoint> checkpoint() {
    final boundary = _state();
    _scheduleWrite();
    final done = Completer<OtaObservationCheckpoint>();
    _work = _work.then((_) async {
      try {
        if (!_closed) await writer.flush();
      } catch (_) {
        _fail('io-flush');
      }
      var status = _atBoundary(boundary);
      try {
        final pending = File('${healthFile.path}.tmp');
        await pending.writeAsString('${jsonEncode({
          'schema': 1, 'captureId': captureId,
          'time': DateTime.now().toUtc().toIso8601String(), ...status.toJson(),
        })}\n', flush: true);
        await pending.rename(healthFile.path);
      } catch (_) {
        _fail('io-health');
        status = _atBoundary(boundary);
      }
      try {
        onCheckpoint?.call(status);
      } catch (_) {
        _fail('status-callback');
        status = _atBoundary(boundary);
      }
      done.complete(status);
    });
    return done.future;
  }

  Future<File> exportSnapshot() async {
    if (_closed || _exporting || upgradeActive || _exports >= 4) {
      throw StateError('observation export unavailable');
    }
    _exporting = true;
    try {
      final status = await checkpoint();
      if (!status.healthy) throw StateError('observation capture incomplete');
      final used = await _storageBytes(root);
      if (used + (maxBytes - status.bytes) + status.bytes + 8192 > maxStoreBytes) {
        throw const FileSystemException('observation export storage limit');
      }
      final output = File('${directory.path}/snapshot-${++_exports}.jsonl');
      await output.create(exclusive: true);
      final destination = await output.open(mode: FileMode.writeOnlyAppend);
      final digest = _DigestSink();
      final hasher = sha256.startChunkedConversion(digest);
      var copied = 0;
      try {
        await for (final bytes in file.openRead(0, status.bytes)) {
          copied += bytes.length;
          hasher.add(bytes);
          await destination.writeFrom(bytes);
        }
        hasher.close();
        if (copied != status.bytes) throw StateError('observation prefix truncated');
        await destination.writeFrom(utf8.encode('${jsonEncode({
          'kind': 'snapshot', 'schema': 1, 'captureId': captureId,
          ...status.toJson(), 'sha256': digest.value.toString(),
          'exportedAt': DateTime.now().toUtc().toIso8601String(),
        })}\n'));
        await destination.flush();
      } finally {
        await destination.close();
      }
      return output;
    } finally {
      _exporting = false;
    }
  }

  Future<void> close() => _closing ??= _close();

  Future<void> _close() async {
    _timer?.cancel();
    _accepting = false;
    await checkpoint();
    _closed = true;
    try {
      await writer.close();
    } catch (_) {
      _fail('io-close');
    }
  }
}

class _DigestSink implements Sink<Digest> {
  Digest? value;
  @override
  void add(Digest data) => value = data;
  @override
  void close() {}
}
