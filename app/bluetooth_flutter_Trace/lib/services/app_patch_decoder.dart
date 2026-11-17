import 'dart:async';

import 'package:flutter/services.dart';

/// Explicit format identity; legacy release manifests remain unchanged.
const appBsdiffLzmaFormat = 'bsdiff-lzma-v1';
const appBsdiffMinVersionCode = 107;

bool supportsAppPatch(String format, int sourceVersionCode) => switch (format) {
      appBsdiffLzmaFormat => sourceVersionCode >= appBsdiffMinVersionCode,
      'vcdiff' => sourceVersionCode >= 41,
      'tracepatch' => true,
      _ => false,
    };

class AppPatchDecoder {
  AppPatchDecoder({MethodChannel? channel})
      : _channel = channel ?? const MethodChannel('trace/app_patch');

  final MethodChannel _channel;
  String? _activeId;
  bool _cancelled = false;
  static int _sequence = 0;

  Future<void> cancel() async {
    final id = _activeId;
    if (id != null) {
      _cancelled = true;
      await _channel.invokeMethod<bool>('cancel', {'id': id});
    }
  }

  Future<void> apply({
    required String oldApkPath,
    required String patchPath,
    required String outputApkPath,
    required String expectedOldSha256,
    required String expectedPatchSha256,
    required String expectedNewSha256,
    required int expectedNewSize,
    required void Function(double) onProgress,
  }) async {
    if (_activeId != null) throw StateError('A patch is still running');
    if (expectedNewSize <= 0 || expectedNewSize > 256 * 1024 * 1024) {
      throw const FormatException('Patch output exceeds limit');
    }
    final id = '${DateTime.now().microsecondsSinceEpoch.toRadixString(16)}-'
        '${(++_sequence).toRadixString(16)}';
    _activeId = id;
    _cancelled = false;
    var completed = 0;
    _channel.setMethodCallHandler((call) async {
      final args = call.arguments;
      if (call.method != 'progress' || args is! Map ||
          args['id'] != id || _activeId != id || _cancelled) return;
      final next = args['completed'];
      if (next is! int || args['total'] != expectedNewSize ||
          next < completed || next > expectedNewSize) return;
      completed = next;
      onProgress(next / expectedNewSize);
    });
    try {
      final result = await _channel.invokeMapMethod<String, dynamic>('apply', {
        'id': id,
        'algorithm': appBsdiffLzmaFormat,
        'oldApkPath': oldApkPath,
        'patchPath': patchPath,
        'outputApkPath': outputApkPath,
        'oldSha256': expectedOldSha256,
        'patchSha256': expectedPatchSha256,
        'newSha256': expectedNewSha256,
        'newSize': expectedNewSize,
      });
      if (_cancelled) {
        throw PlatformException(code: 'PATCH_CANCELLED', message: 'Patch cancelled');
      }
      if (result?['id'] != id || result?['bytes'] != expectedNewSize ||
          result?['sha256'] != expectedNewSha256) {
        throw const FormatException('Native patch result identity mismatch');
      }
      onProgress(1);
    } finally {
      _activeId = null;
      _channel.setMethodCallHandler(null);
    }
  }
}
