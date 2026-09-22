import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:crypto/crypto.dart';
import 'package:flutter/foundation.dart';
import 'package:path_provider/path_provider.dart';

/// A requested experiment profile, never evidence of the MCU's actual baud.
class OtaExperimentConfig {
  const OtaExperimentConfig._({
    required this.runId,
    required this.target,
    required this.requestedBaud,
    required this.reuseGatt,
    required this.withoutResponse,
    required this.firmwareLatestUri,
    required this.packageBytes,
    required this.packageSha256,
    required this.currentVersionCode,
    required this.currentImageSha256,
    required this.targetVersionCode,
    required this.targetImageSha256,
    required this.sourceSha256,
  });

  static const maxConfigBytes = 8192;
  static const _fields = {
    'schema', 'runId', 'target', 'requestedBaud', 'reuseGatt', 'withoutResponse',
    'firmwareLatestUrl', 'packageBytes', 'packageSha256', 'currentVersionCode',
    'currentImageSha256', 'targetVersionCode', 'targetImageSha256',
  };

  final String runId;
  final String target;
  final int requestedBaud;
  final bool reuseGatt;
  final bool withoutResponse;
  final Uri firmwareLatestUri;
  final int packageBytes;
  final String packageSha256;
  final int currentVersionCode;
  final String currentImageSha256;
  final int targetVersionCode;
  final String targetImageSha256;
  final String sourceSha256;

  factory OtaExperimentConfig.parse(String text, {required String expectedTarget}) {
    final bytes = utf8.encode(text);
    if (bytes.length > maxConfigBytes) {
      throw const FormatException('experiment-config-too-large');
    }
    final decoded = jsonDecode(text);
    if (decoded is! Map<String, dynamic> || decoded.length != _fields.length ||
        !_fields.containsAll(decoded.keys) || decoded['schema'] is! int || decoded['schema'] != 1) {
      throw const FormatException('experiment-config-schema');
    }
    String string(String key, RegExp pattern) {
      final value = decoded[key];
      if (value is! String || !pattern.hasMatch(value)) {
        throw const FormatException('experiment-config-field');
      }
      return value;
    }
    int integer(String key, int minimum, int maximum) {
      final value = decoded[key];
      if (value is! int || value < minimum || value > maximum) {
        throw const FormatException('experiment-config-number');
      }
      return value;
    }
    final runId = string('runId', RegExp(r'^[a-z][a-z0-9-]{0,47}$'));
    final target = string('target', RegExp(r'^(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$'));
    if (target.toLowerCase() != expectedTarget.toLowerCase()) {
      throw const FormatException('experiment-config-target');
    }
    final baud = integer('requestedBaud', 1, 1000000);
    if (!const {115200, 460800, 921600}.contains(baud) ||
        decoded['reuseGatt'] is! bool || decoded['withoutResponse'] is! bool) {
      throw const FormatException('experiment-config-profile');
    }
    final url = decoded['firmwareLatestUrl'];
    final uri = url is String ? Uri.tryParse(url) : null;
    if (uri == null || uri.scheme != 'https' || uri.userInfo.isNotEmpty ||
        !RegExp(r'^[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?\.[a-z]{2,}$').hasMatch(uri.host) ||
        uri.hasQuery || uri.hasFragment || (uri.hasPort && uri.port != 443) ||
        uri.path != '/api/public/firmware/latest') {
      throw const FormatException('experiment-config-endpoint');
    }
    final digest = RegExp(r'^[0-9a-f]{64}$');
    final currentVersion = integer('currentVersionCode', 1, 2100000000);
    final targetVersion = integer('targetVersionCode', 1, 2100000000);
    if (targetVersion <= currentVersion) {
      throw const FormatException('experiment-config-version-order');
    }
    return OtaExperimentConfig._(
      runId: runId, target: target, requestedBaud: baud,
      reuseGatt: decoded['reuseGatt'] as bool,
      withoutResponse: decoded['withoutResponse'] as bool,
      firmwareLatestUri: uri,
      packageBytes: integer('packageBytes', 64, 0xffffffff),
      packageSha256: string('packageSha256', digest),
      currentVersionCode: currentVersion,
      currentImageSha256: string('currentImageSha256', digest),
      targetVersionCode: targetVersion,
      targetImageSha256: string('targetImageSha256', digest),
      sourceSha256: sha256.convert(bytes).toString(),
    );
  }

  void requireDevice(String address) {
    if (address.toLowerCase() != target.toLowerCase()) {
      throw StateError('experiment-device-mismatch');
    }
  }

  Uri latestUri(Uri original, {required int versionCode, required String imageSha256}) {
    if (versionCode != currentVersionCode || imageSha256 != currentImageSha256) {
      throw StateError('experiment-baseline-mismatch');
    }
    return firmwareLatestUri.replace(queryParameters: original.queryParameters);
  }

  bool matchesUpgrade(Map<String, Object?> input) =>
      input['packageBytes'] == packageBytes && input['packageSha256'] == packageSha256 &&
      input['currentVersionCode'] == currentVersionCode &&
      input['currentImageSha256'] == currentImageSha256 &&
      input['targetVersionCode'] == targetVersionCode &&
      input['targetImageSha256'] == targetImageSha256 &&
      input['deviceAddress'] is String &&
      (input['deviceAddress'] as String).toLowerCase() == target.toLowerCase();

  String get observationLine => 'OTA_EXPERIMENT ${jsonEncode({
    'schema': 1, 'runId': runId, 'configSha256': sourceSha256,
    'requestedBaud': requestedBaud, 'reuseGatt': reuseGatt,
    'withoutResponse': withoutResponse, 'endpointHost': firmwareLatestUri.host,
    'deviceAddress': target, 'packageBytes': packageBytes,
    'packageSha256': packageSha256, 'currentVersionCode': currentVersionCode,
    'currentImageSha256': currentImageSha256, 'targetVersionCode': targetVersionCode,
    'targetImageSha256': targetImageSha256,
  })}';
}

/// Loaded once before service creation. Replacing the file cannot alter a run.
class OtaExperimentRuntime {
  OtaExperimentRuntime({required this.enabled});

  static final _shared = OtaExperimentRuntime(
    enabled: kDebugMode && const bool.fromEnvironment('OTA_P34_RUNTIME_CONFIG'),
  );
  static final _zoneKey = Object();
  static OtaExperimentRuntime get current =>
      Zone.current[_zoneKey] as OtaExperimentRuntime? ?? _shared;

  @visibleForTesting
  static T withInstance<T>(OtaExperimentRuntime runtime, T Function() body) =>
      runZoned(body, zoneValues: {_zoneKey: runtime});

  final bool enabled;
  Future<void>? _initialization;
  OtaExperimentConfig? _config;
  String? _error;
  OtaExperimentConfig? get config => _config;
  String? get error => _error;
  bool get ready => !enabled || _config != null;

  Future<void> initialize({required String expectedTarget,
      Future<String> Function()? readConfig,
      Future<Directory> Function()? directoryProvider}) =>
      _initialization ??= _load(expectedTarget, readConfig ??
          () => _readConfig(directoryProvider ?? getApplicationSupportDirectory));

  Future<void> _load(String expectedTarget, Future<String> Function() reader) async {
    if (!enabled) return;
    try {
      _config = OtaExperimentConfig.parse(await reader(), expectedTarget: expectedTarget);
    } catch (_) {
      _error = 'experiment-config-unavailable-or-invalid';
    }
  }

  static Future<String> _readConfig(Future<Directory> Function() directoryProvider) async {
    final directory = await directoryProvider();
    final file = File('${directory.path}/p34-experiment.json');
    final bytes = BytesBuilder(copy: false);
    await for (final chunk in file.openRead(0, OtaExperimentConfig.maxConfigBytes + 1)) {
      bytes.add(chunk);
    }
    if (bytes.length > OtaExperimentConfig.maxConfigBytes) {
      throw const FormatException('experiment-config-too-large');
    }
    return utf8.decode(bytes.takeBytes());
  }

  OtaExperimentConfig? requireForOta() {
    if (enabled && _config == null) {
      throw StateError(_error ?? 'experiment-config-not-initialized');
    }
    return _config;
  }
}
