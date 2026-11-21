import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:math';

import 'package:crypto/crypto.dart';
import 'package:get/get.dart';
import 'package:flutter/services.dart';

import 'ota_device_info.dart';

/// One serialized journal, independent of the page and of companion ownership.
/// A process interruption is unknown, never an inferred successful installation.
class OtaUpgradeHistory {
  OtaUpgradeHistory(this.directory);
  final Future<Directory> Function() directory;
  final revision = 0.obs;
  final problem = RxnString();
  final List<Map<String, dynamic>> _rows = [];
  Future<void>? _loaded;
  Future<void> _tail = Future<void>.value();
  final Map<String, Stopwatch> _clocks = {};
  static String deviceKey(String address) =>
      sha256.convert(utf8.encode(address.toLowerCase())).toString();
  static String hardwareKey(DeviceOtaInfo info) =>
      '${info.wireModel}/${info.hardwareRevision}/${info.layoutId}/${info.bootVersion}/${info.protocolVersion}';

  Future<File> _file() async => File('${(await directory()).path}/upgrade-history-v1.jsonl');

  Future<void> load() => _loaded ??= _load();

  Future<void> _load() async {
    try {
      final file = await _file();
      if (!await file.exists()) return;
      // Last complete revision of each attempt wins. A torn final append is
      // reported, not discarded silently or used to manufacture an outcome.
      await for (final line in file.openRead().transform(utf8.decoder).transform(const LineSplitter())) {
        try {
          final row = Map<String, dynamic>.from(jsonDecode(line) as Map);
          if (row['schema'] != 1 || row['taskId'] is! String || row['deviceKey'] is! String) {
            throw const FormatException('HISTORY_SCHEMA');
          }
          _rows.removeWhere((old) => old['taskId'] == row['taskId']);
          _rows.add(row);
        } catch (_) { problem.value = 'HISTORY_INCOMPLETE'; }
      }
      for (final row in _rows) {
        if (row['status'] == 'running') {
          row['status'] = 'awaitingVerification';
          row['errorCode'] = 'PROCESS_INTERRUPTED';
          row['durationMs'] = null;
        }
      }
    } catch (_) { problem.value = 'HISTORY_READ_FAILED'; }
    finally { revision.value++; }
  }

  List<Map<String, dynamic>> forDevice(String? address) {
    revision.value;
    final key = address == null ? null : deviceKey(address);
    return _rows.reversed.where((row) => key == null || row['deviceKey'] == key)
        .map((row) => Map<String, dynamic>.unmodifiable(row)).toList(growable: false);
  }

  Future<void> _serialize(Future<void> Function() action) {
    final next = _tail.then((_) => action());
    _tail = next.catchError((Object _) { problem.value = 'HISTORY_WRITE_FAILED'; });
    return next;
  }

  Future<void> _append(Map<String, dynamic> row) async {
    final file = await _file();
    await file.parent.create(recursive: true);
    await file.writeAsString('${jsonEncode(row)}\n', mode: FileMode.append, flush: true);
    _rows.removeWhere((old) => old['taskId'] == row['taskId']);
    _rows.add(row);
    revision.value++;
    if (Platform.isAndroid) {
      try {
        await const MethodChannel('trace/companion').invokeMethod<Object?>('journal', {
          'status': 'UPGRADE_HISTORY', 'taskId': row['taskId'], 'deviceKey': row['deviceKey'],
          'source': row['initiator'], 'outcome': row['status'], 'stage': row['stage'],
          'beforeVersion': row['beforeVersion'], 'targetVersion': row['targetVersion'],
          'elapsedMs': row['durationMs'], 'errorCode': row['errorCode'],
        }).timeout(const Duration(seconds: 1));
      } catch (_) { /* The durable local history is independent of diagnostics. */ }
    }
  }

  Future<String> begin({required String address, required DeviceOtaInfo before,
      required int targetVersion, required String targetSha, required String packageSha,
      required String kind, required String initiator}) async {
    await load();
    if (problem.value != null) throw StateError(problem.value!);
    final id = List.generate(16, (_) => Random.secure().nextInt(256))
        .map((v) => v.toRadixString(16).padLeft(2, '0')).join();
    final row = <String, dynamic>{'schema': 1, 'taskId': id,
      'deviceKey': deviceKey(address), 'device': before.wireModel,
      'hardwareKey': hardwareKey(before), 'beforeVersion': before.currentVersionCode,
      'beforeSha': before.currentImageSha256Hex, 'targetVersion': targetVersion,
      'targetSha': targetSha, 'packageSha': packageSha, 'kind': kind,
      'initiator': initiator, 'startedAt': DateTime.now().millisecondsSinceEpoch,
      'status': 'running', 'stage': 'preparing', 'durationMs': null};
    await _serialize(() => _append(row));
    _clocks[id] = Stopwatch()..start();
    return id;
  }

  Future<void> update(String id, {required String status, required String stage,
      String? errorCode, DeviceOtaInfo? verified, bool finish = false}) => _serialize(() async {
    final index = _rows.indexWhere((r) => r['taskId'] == id);
    final row = index < 0 ? null : _rows[index];
    if (row == null || row['status'] == 'success') return;
    if (status == 'success' && (verified == null || !_matches(row, verified))) {
      throw StateError('HISTORY_TARGET_NOT_VERIFIED');
    }
    final clock = _clocks[id];
    final next = {...row, 'status': status, 'stage': stage,
      'errorCode': errorCode, 'updatedAt': DateTime.now().millisecondsSinceEpoch,
      'durationMs': clock?.elapsedMilliseconds};
    if (verified != null) {
      next['afterVersion'] = verified.currentVersionCode;
      next['afterSha'] = verified.currentImageSha256Hex;
      next['verifiedAt'] = DateTime.now().millisecondsSinceEpoch;
    }
    await _append(next);
    if (finish) _clocks.remove(id)?.stop();
  });

  bool _matches(Map<String, dynamic> row, DeviceOtaInfo info) =>
      row['hardwareKey'] == hardwareKey(info) &&
      row['targetVersion'] != row['beforeVersion'] &&
      row['targetVersion'] == info.currentVersionCode &&
      row['targetSha'] == info.currentImageSha256Hex;

  /// Call only after a fresh GET_INFO, never for a cached/pre-transfer snapshot.
  Future<void> reconcile(String address, DeviceOtaInfo info) async {
    await load();
    final pending = _rows.reversed.where((r) => r['deviceKey'] == deviceKey(address) &&
        r['status'] == 'awaitingVerification' && _matches(r, info)).take(1).toList();
    for (final row in pending) {
      await update(row['taskId'] as String, status: 'success',
          stage: 'identityVerified', verified: info, finish: true);
    }
  }
}
