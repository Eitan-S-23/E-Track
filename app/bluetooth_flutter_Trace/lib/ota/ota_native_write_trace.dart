import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter/services.dart';

typedef NativeTraceInvoker = Future<Object?> Function(
    String method, Map<String, Object?> arguments);

/// Observer only: native durations are not radio time or MCU durable progress.
class OtaNativeWriteTrace {
  OtaNativeWriteTrace({this.invoke, this.isAndroid});

  static const channel = MethodChannel('etrack/ota_phy');
  final NativeTraceInvoker? invoke;
  final bool? isAndroid;
  Map<String, Object?>? _binding;
  Map<String, Object?>? _attempted;
  Future<void>? _collecting;

  Future<Object?> _call(String method, Map<String, Object?> binding) =>
      (invoke != null ? invoke!(method, binding)
          : channel.invokeMethod<Object?>(method, binding))
          .timeout(const Duration(seconds: 2));

  Future<void> start({required String captureId, required String target,
      required void Function(String) record}) async {
    if (!(isAndroid ?? Platform.isAndroid)) return;
    final binding = <String, Object?>{
      'captureId': captureId, 'remoteId': target.toUpperCase(),
    };
    try {
      if (!RegExp(r'^\d{13,20}-[0-9a-f]{24}$').hasMatch(captureId) ||
          !RegExp(r'^[0-9A-F]{2}(:[0-9A-F]{2}){5}$').hasMatch(binding['remoteId']! as String) ||
          _attempted != null) {
        throw const FormatException('native start');
      }
      _attempted = binding;
      if (await _call('p34TraceStart', binding) != true) throw const FormatException('native start rejected');
      _binding = binding;
      record('OTA_LINK_NATIVE_READY ${jsonEncode(binding)}');
    } on Exception {
      record('OTA_LINK_NATIVE_ERROR phase=start reason=unavailable');
    }
  }

  Future<void> collect({required void Function(String) record,
      required Future<void> Function() flush}) {
    if (_binding == null) return Future<void>.value();
    return _collecting ??= _collect(record, flush).whenComplete(() => _collecting = null);
  }

  Future<void> _collect(void Function(String) record, Future<void> Function() flush) async {
    final binding = _binding!;
    try {
      final raw = await _call('p34TraceSnapshot', binding);
      final value = validate(raw, binding);
      final rows = value.remove('rows')! as List;
      record('OTA_LINK_NATIVE_META ${jsonEncode(value)}');
      var emitted = 0;
      for (final row in rows) {
        record('OTA_LINK_NATIVE_WRITE snapshot=${value['snapshot']} row=${jsonEncode(row)}');
        if (++emitted % 64 == 0) await flush();
      }
      record('OTA_LINK_NATIVE_END snapshot=${value['snapshot']} samples=$emitted');
      await flush();
    } on Exception {
      record('OTA_LINK_NATIVE_ERROR phase=snapshot reason=unavailable-or-invalid');
    }
  }

  static Map<String, Object?> validate(Object? raw, Map<String, Object?> binding) {
    const fields = {'schema', 'captureId', 'remoteId', 'clock', 'snapshot', 'capacity',
      'sampleCount', 'overflow', 'correlationErrors', 'incomplete', 'apiErrors',
      'callbackErrors', 'rows', 'pid'};
    bool integer(Object? value, int low, int high) =>
        value is int && value >= low && value <= high;
    if (raw is! Map || raw.keys.any((key) => !fields.contains(key)) ||
        raw.length != fields.length || raw['schema'] != 1 ||
        raw['captureId'] != binding['captureId'] || raw['remoteId'] != binding['remoteId'] ||
        raw['clock'] != 'System.nanoTime-relative-ns' ||
        !integer(raw['snapshot'], 1, 0x7fffffff) || !integer(raw['pid'], 1, 0x7fffffff) ||
        !integer(raw['capacity'], 1, 8192) || !integer(raw['sampleCount'], 0, 8192) ||
        raw['rows'] is! List) {
      throw const FormatException('native snapshot binding');
    }
    for (final field in ['overflow', 'correlationErrors', 'incomplete', 'apiErrors', 'callbackErrors']) {
      if (!integer(raw[field], 0, 0x7fffffff)) throw const FormatException('native counters');
    }
    final rows = raw['rows'] as List;
    if (rows.length != raw['sampleCount'] || rows.length > (raw['capacity'] as int)) {
      throw const FormatException('native sample count');
    }
    var incomplete = 0, apiErrors = 0, callbackErrors = 0;
    for (var i = 0; i < rows.length; i++) {
      final row = rows[i];
      if (row is! List || row.length != 11 || row.any((v) => v is! int) ||
          row[0] != i + 1 || !integer(row[1], 1, 64) || !integer(row[2], 1, 512) ||
          !integer(row[3], 0, 0xffffffff)) {
        throw const FormatException('native sample identity');
      }
      final values = row.cast<int>();
      if (values[4] < 0 || values[5] < values[4] ||
          (values[6] != -1 && values[6] < values[5]) ||
          (values[7] != -1 && values[7] < values[5]) ||
          (values[8] != -1 && (values[7] < 0 || values[8] < values[7])) ||
          (values[6] == -1 && values[9] != -1) ||
          (values[7] == -1 && values[10] != -1)) {
        throw const FormatException('native sample clock');
      }
      if (values[6] < 0 || (values[9] == 0 && (values[7] < 0 || values[8] < 0))) incomplete++;
      if (values[6] >= 0 && values[9] != 0) apiErrors++;
      if (values[7] >= 0 && values[10] != 0) callbackErrors++;
    }
    if (incomplete != raw['incomplete'] || apiErrors != raw['apiErrors'] ||
        callbackErrors != raw['callbackErrors']) {
      throw const FormatException('native missing/error counters');
    }
    return Map<String, Object?>.from(raw);
  }

  Future<void> close() async {
    final active = _attempted;
    if (active == null) return;
    _binding = null;
    _attempted = null;
    try {
      await _collecting;
      await _call('p34TraceStop', active);
    } on Exception {
      // Native storage remains bounded and engine detach always clears it.
    }
  }
}
