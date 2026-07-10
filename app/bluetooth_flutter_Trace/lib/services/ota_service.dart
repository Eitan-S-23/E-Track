import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:crypto/crypto.dart';
import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_blue_plus/flutter_blue_plus.dart';
import 'package:get/get.dart';
import 'package:path_provider/path_provider.dart';

import '../config/share_links.dart';

/// OTA firmware service.
///
/// The current implementation covers firmware discovery, download,
/// and checksum verification. BLE packet transfer is intentionally left as a
/// later step because the MCU packet protocol is not finalized yet.
class OtaService extends GetxController {
  static OtaService get to => Get.find();

  final Dio _dio = Dio(
    BaseOptions(
      connectTimeout: const Duration(seconds: 15),
      receiveTimeout: const Duration(minutes: 5),
      sendTimeout: const Duration(seconds: 15),
      headers: const {
        'Accept': 'application/json',
      },
    ),
  );

  final _upgradeProgress = 0.0.obs;
  final _upgradeStatus = ''.obs;
  final _isUpgrading = false.obs;

  String? _latestFirmwareVersion;
  String? _firmwareDescription;
  String? _firmwareDownloadUrl;
  String? _firmwareSha256;
  String? _firmwareFileName;
  int? _firmwareSizeBytes;
  File? _firmwareFile;
  CancelToken? _downloadCancelToken;

  double get upgradeProgress => _upgradeProgress.value;
  String get upgradeStatus => _upgradeStatus.value;
  bool get isUpgrading => _isUpgrading.value;
  bool get isFirmwareServiceConfigured => ShareLinks.hasFirmwareUpdateEndpoint;
  File? get downloadedFirmwareFile => _firmwareFile;

  @override
  void onInit() {
    super.onInit();
    _upgradeStatus.value = isFirmwareServiceConfigured
        ? '固件服务已就绪'
        : '固件服务未配置';
  }

  @override
  void onClose() {
    _dio.close(force: true);
    super.onClose();
  }

  /// Checks the firmware service for the latest published MCU firmware.
  Future<Map<String, dynamic>?> checkFirmwareUpdate(
    String deviceModel,
    String currentVersion, {
    int? currentVersionCode,
    String? channel,
  }) async {
    if (!isFirmwareServiceConfigured) {
      _upgradeStatus.value = '固件服务未配置';
      Get.snackbar('错误', '固件更新地址未配置，无法检查更新');
      return null;
    }

    try {
      _upgradeStatus.value = '检查固件更新中...';
      _upgradeProgress.value = 0.0;

      final uri = ShareLinks.firmwareLatestUri(
        deviceModel: deviceModel,
        currentVersion: currentVersion,
        currentVersionCode: currentVersionCode,
        channel: channel,
      );
      final response = await _dio.getUri(uri);
      final body = _readJsonObject(response.data);

      if (body['updateAvailable'] != true) {
        _clearFirmwareInfo();
        _upgradeStatus.value = '固件已是最新版本';
        Get.snackbar(
          '提示',
          '固件已是最新版本',
          backgroundColor: Colors.green.withOpacity(0.1),
          colorText: Colors.green.shade700,
          snackPosition: SnackPosition.TOP,
        );
        return null;
      }

      _latestFirmwareVersion = stringValue(body['versionName'] ?? body['version']);
      _firmwareDescription = stringValue(body['releaseNotes'] ?? body['description']);
      _firmwareDownloadUrl = stringValue(body['downloadUrl']);
      _firmwareSha256 = stringValue(body['sha256'])?.toLowerCase();
      _firmwareFileName = stringValue(body['fileName']);
      _firmwareSizeBytes = intValue(body['sizeBytes'] ?? body['file_size']);

      if (_latestFirmwareVersion == null ||
          _firmwareDownloadUrl == null ||
          _firmwareSha256 == null ||
          _firmwareFileName == null ||
          _firmwareSizeBytes == null) {
        throw const FormatException('固件清单缺少必要字段');
      }

      _upgradeStatus.value = '发现新固件: $_latestFirmwareVersion';
      return {
        'version': _latestFirmwareVersion,
        'versionCode': intValue(body['versionCode']),
        'description': _firmwareDescription ?? '',
        'downloadUrl': _firmwareDownloadUrl,
        'fileName': _firmwareFileName,
        'fileSizeBytes': _firmwareSizeBytes,
        'sha256': _firmwareSha256,
        'targetHardware': stringValue(body['targetHardware']),
        'transport': stringValue(body['transport']) ?? 'ble',
      };
    } catch (error) {
      final message = _friendlyDioMessage(error);
      _upgradeStatus.value = '检查更新失败: $message';
      Get.snackbar('错误', '检查固件更新失败: $message');
      return null;
    }
  }

  /// Downloads the firmware binary and verifies SHA-256.
  Future<bool> downloadFirmware() async {
    if (_firmwareDownloadUrl == null ||
        _latestFirmwareVersion == null ||
        _firmwareFileName == null ||
        _firmwareSha256 == null ||
        _firmwareSizeBytes == null) {
      Get.snackbar('错误', '固件下载信息无效，请重新检查更新');
      return false;
    }

    File? partialFile;
    try {
      _isUpgrading.value = true;
      _upgradeProgress.value = 0.0;
      _upgradeStatus.value = '下载固件中...';
      final cancelToken = CancelToken();
      _downloadCancelToken = cancelToken;

      final directory = await getApplicationDocumentsDirectory();
      final firmwareDir = Directory('${directory.path}/firmware');
      if (!await firmwareDir.exists()) {
        await firmwareDir.create(recursive: true);
      }

      final fileName = _safeFileName(_firmwareFileName!);
      final firmwarePath = '${firmwareDir.path}/$fileName';
      final partialPath = '$firmwarePath.part';
      partialFile = File(partialPath);
      if (await partialFile.exists()) {
        await partialFile.delete();
      }

      await _dio.download(
        _firmwareDownloadUrl!,
        partialPath,
        options: Options(
          responseType: ResponseType.bytes,
          followRedirects: true,
          validateStatus: (status) => status != null && status >= 200 && status < 300,
        ),
        cancelToken: cancelToken,
        onReceiveProgress: (received, total) {
          final expectedTotal = total > 0 ? total : _firmwareSizeBytes ?? 0;
          if (expectedTotal > 0) {
            final progress = (received / expectedTotal).clamp(0.0, 1.0).toDouble();
            _upgradeProgress.value = progress;
            _upgradeStatus.value =
                '下载中: ${(progress * 100).toStringAsFixed(1)}% (${_formatBytes(received)}/${_formatBytes(expectedTotal)})';
          }
        },
      );

      final downloadedSize = await partialFile.length();
      if (downloadedSize != _firmwareSizeBytes) {
        throw StateError(
          '文件大小不匹配，期望 ${_formatBytes(_firmwareSizeBytes!)}，实际 ${_formatBytes(downloadedSize)}',
        );
      }

      final downloadedSha256 = await _sha256File(partialFile);
      if (downloadedSha256 != _firmwareSha256) {
        throw StateError('SHA-256校验失败');
      }

      final finalFile = File(firmwarePath);
      if (await finalFile.exists()) {
        await finalFile.delete();
      }
      _firmwareFile = await partialFile.rename(firmwarePath);
      partialFile = null;

      _upgradeProgress.value = 1.0;
      _upgradeStatus.value = '固件已下载，等待后续BLE分包传输实现';
      return true;
    } catch (error) {
      final message = _friendlyDioMessage(error);
      _upgradeStatus.value = '固件下载失败: $message';
      Get.snackbar('错误', '固件下载失败: $message');
      return false;
    } finally {
      _isUpgrading.value = false;
      _downloadCancelToken = null;
      if (partialFile != null && await partialFile.exists()) {
        try {
          await partialFile.delete();
        } catch (error) {
          debugPrint('删除固件临时文件失败: $error');
        }
      }
    }
  }

  /// BLE packet transfer is deliberately not implemented yet.
  Future<bool> startOtaUpgrade(BluetoothDevice device) async {
    if (_firmwareFile == null || !(await _firmwareFile!.exists())) {
      Get.snackbar('错误', '固件文件不存在，请先下载固件');
      return false;
    }
    _upgradeStatus.value = '固件已下载，BLE分包传输待实现';
    Get.snackbar('提示', '固件已下载，BLE分包传输功能待实现');
    return false;
  }

  Future<void> cancelUpgrade() async {
    _downloadCancelToken?.cancel('用户取消下载');
    _isUpgrading.value = false;
    _upgradeStatus.value = '操作已取消';
  }

  Future<void> cleanupFirmware() async {
    if (_firmwareFile != null && await _firmwareFile!.exists()) {
      await _firmwareFile!.delete();
      _firmwareFile = null;
    }
  }

  List<Map<String, dynamic>> getUpgradeHistory() {
    return const [];
  }

  void _clearFirmwareInfo() {
    _latestFirmwareVersion = null;
    _firmwareDescription = null;
    _firmwareDownloadUrl = null;
    _firmwareSha256 = null;
    _firmwareFileName = null;
    _firmwareSizeBytes = null;
    _firmwareFile = null;
  }

  Map<String, dynamic> _readJsonObject(Object? value) {
    final parsed = value is String ? jsonDecode(value) : value;
    if (parsed is Map<String, dynamic>) return parsed;
    if (parsed is Map) {
      return parsed.map((key, entry) => MapEntry(key.toString(), entry));
    }
    throw const FormatException('固件清单不是JSON对象');
  }

  Future<String> _sha256File(File file) async {
    final digest = await sha256.bind(file.openRead()).first;
    return digest.toString();
  }

  String _safeFileName(String fileName) {
    final sanitized = fileName.replaceAll(RegExp(r'["\\/\r\n]'), '_').trim();
    return sanitized.isEmpty ? 'firmware_$_latestFirmwareVersion.bin' : sanitized;
  }

  String _formatBytes(int bytes) {
    if (bytes < 1024) return '$bytes B';
    final kb = bytes / 1024;
    if (kb < 1024) return '${kb.toStringAsFixed(1)} KB';
    final mb = kb / 1024;
    return '${mb.toStringAsFixed(2)} MB';
  }

  String _friendlyDioMessage(Object error) {
    if (error is DioException) {
      if (CancelToken.isCancel(error)) return '用户已取消';
      final status = error.response?.statusCode;
      final body = error.response?.data;
      final serverMessage = body is Map
          ? (body['message'] ?? body['errorCode'])?.toString()
          : body is String && body.isNotEmpty
              ? body
              : null;
      if (status != null && serverMessage != null) {
        return 'HTTP $status: $serverMessage';
      }
      if (status != null) return 'HTTP $status';
      return error.message ?? error.type.name;
    }
    return error.toString();
  }
}

String? stringValue(Object? value) {
  if (value == null) return null;
  final text = value.toString().trim();
  return text.isEmpty ? null : text;
}

int? intValue(Object? value) {
  if (value is int) return value;
  if (value is num) return value.toInt();
  if (value is String) return int.tryParse(value);
  return null;
}
