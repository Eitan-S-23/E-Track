import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:crypto/crypto.dart';
import 'package:cryptography/cryptography.dart';
import 'package:dio/dio.dart' hide Response;
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:get/get.dart';
import 'package:path_provider/path_provider.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:vcdiff_decoder/vcdiff_decoder.dart' as vcdiff;

import '../config/share_links.dart';
import '../pages/trace_ui.dart';

class AppUpdateService extends GetxService with WidgetsBindingObserver {
  static AppUpdateService get to => Get.find<AppUpdateService>();

  static const MethodChannel _platform = MethodChannel('trace/app_update');
  static const String _lastDailyCheckKey = 'app_update_last_daily_check';
  static const String _pendingInstallApkPathKey =
      'app_update_pending_install_apk_path';
  static const String _pendingInstallVersionCodeKey =
      'app_update_pending_install_version_code';
  static const String _unknownAppSourcesCode = 'UNKNOWN_APP_SOURCES';
  static const String _appNotForegroundCode = 'APP_NOT_FOREGROUND';
  static const String _patchAlgorithmTracePatch = 'tracepatch';
  static const String _patchAlgorithmVcdiff = 'vcdiff';
  static const int _manifestSchemaVersion = 2;
  static const String _clientCapabilities =
      'patch,full,fallback,errorCode,payloadSignature,vcdiff';

  final Dio _dio = Dio(
    BaseOptions(
      connectTimeout: const Duration(seconds: 12),
      receiveTimeout: const Duration(seconds: 20),
      sendTimeout: const Duration(seconds: 12),
    ),
  );

  final isChecking = false.obs;
  final isUpdating = false.obs;
  final updateProgress = 0.0.obs;
  final updateStatus = ''.obs;

  bool _isRetryingPendingInstall = false;
  DateTime? _lastForegroundUpdateAt;
  double _lastForegroundProgress = -1;
  String? _lastForegroundStatus;

  @override
  void onInit() {
    super.onInit();
    if (!Platform.isAndroid) return;

    WidgetsBinding.instance.addObserver(this);
    WidgetsBinding.instance.addPostFrameCallback((_) {
      unawaited(_resumePendingInstallIfPermitted(showMessage: false));
    });
  }

  @override
  void onClose() {
    if (Platform.isAndroid) {
      WidgetsBinding.instance.removeObserver(this);
    }
    super.onClose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state != AppLifecycleState.resumed || !Platform.isAndroid) return;

    unawaited(_resumePendingInstallAfterForegroundSettles(showMessage: true));
  }

  Future<void> _resumePendingInstallAfterForegroundSettles({
    required bool showMessage,
  }) async {
    await Future<void>.delayed(const Duration(milliseconds: 350));
    if (WidgetsBinding.instance.lifecycleState != AppLifecycleState.resumed) {
      return;
    }
    await _resumePendingInstallIfPermitted(
      showMessage: showMessage,
      force: true,
    );
  }

  Future<void> checkDailyOnStartup() async {
    if (!Platform.isAndroid) return;

    final prefs = await SharedPreferences.getInstance();
    final today = _dateKey(DateTime.now());
    if (prefs.getString(_lastDailyCheckKey) == today) return;

    await prefs.setString(_lastDailyCheckKey, today);
    unawaited(checkForUpdates(manual: false));
  }

  Future<void> checkForUpdates({bool manual = true}) async {
    if (!Platform.isAndroid) {
      if (manual) {
        Get.snackbar('暂不支持', '当前平台暂不支持 APK 增量自更新');
      }
      return;
    }

    if (isUpdating.value) {
      if (manual) {
        Get.snackbar('正在更新', '请等待当前增量更新完成');
      }
      return;
    }

    if (isChecking.value) {
      if (manual) {
        Get.snackbar('正在检查更新', '后台检查仍在进行，请稍候');
      }
      return;
    }

    if (await _handlePendingInstallBeforeUpdateCheck(manual: manual)) {
      return;
    }

    isChecking.value = true;
    var checkingDialogOpen = false;
    var cancelledByUser = false;
    var checkingDialogCloseRequested = false;
    BuildContext? checkingDialogContext;
    Future<void>? checkingDialogClosed;
    final checkingDialogPresented = Completer<void>();
    final manifestCancelToken = CancelToken();

    Future<void> waitForCheckingDialogPresented() async {
      if (checkingDialogPresented.isCompleted) return;
      try {
        await checkingDialogPresented.future.timeout(
          const Duration(milliseconds: 350),
        );
      } on TimeoutException {
        // A close request before the route is built is handled when the
        // delayed checking dialog finally appears.
      }
    }

    Future<void> waitForCheckingDialogClosed() async {
      final dialogClosed = checkingDialogClosed;
      if (dialogClosed == null) return;
      try {
        await dialogClosed.timeout(const Duration(milliseconds: 350));
      } on TimeoutException {
        // Do not block result dialogs on a route that has already been asked
        // to close.
      }
    }

    void markCheckingDialogPresented(BuildContext context) {
      checkingDialogContext = context;
      if (!checkingDialogPresented.isCompleted) {
        checkingDialogPresented.complete();
      }
      if (!checkingDialogCloseRequested) return;

      WidgetsBinding.instance.addPostFrameCallback((_) {
        _closeDialogRouteForContext(context);
      });
    }

    Future<void> closeCheckingDialog({bool force = false}) async {
      if (!force && !checkingDialogOpen && checkingDialogContext == null) {
        return;
      }

      checkingDialogCloseRequested = true;
      await waitForCheckingDialogPresented();

      final context = checkingDialogContext;
      if (context != null) {
        _closeDialogRouteForContext(context);
      } else if (Get.isDialogOpen == true) {
        Get.back<void>();
      }

      checkingDialogOpen = false;
      checkingDialogContext = null;
      await waitForCheckingDialogClosed();
    }

    void cancelChecking(BuildContext context) {
      cancelledByUser = true;
      checkingDialogCloseRequested = true;
      manifestCancelToken.cancel('用户取消检查更新');
      _closeDialogRouteForContext(context);
      checkingDialogOpen = false;
      checkingDialogContext = null;
    }

    updateProgress.value = 0;
    updateStatus.value = '正在检查更新...';
    if (manual) {
      checkingDialogOpen = true;
      checkingDialogClosed = _showCheckingDialog(
        onCancel: cancelChecking,
        onPresented: markCheckingDialogPresented,
      ).whenComplete(() {
        checkingDialogOpen = false;
        checkingDialogContext = null;
        if (!checkingDialogPresented.isCompleted) {
          checkingDialogPresented.complete();
        }
      });
      await waitForCheckingDialogPresented();
    }

    try {
      updateStatus.value = '读取本机版本...';
      final localInfo = await _getLocalAppInfo();

      updateStatus.value = '校验本机安装包...';
      final localApkSha256 = await _sha256File(File(localInfo.sourceApkPath));

      updateStatus.value = '获取更新清单...';
      final updateInfo = await _fetchUpdateInfo(
        localInfo,
        cancelToken: manifestCancelToken,
      ).timeout(
        const Duration(seconds: 30),
        onTimeout: () {
          manifestCancelToken.cancel('获取更新清单超时');
          throw const _UpdateException(
            'MANIFEST_TIMEOUT',
            '获取更新清单超时，请检查网络后重试',
          );
        },
      );

      if (updateInfo.versionCode <= localInfo.versionCode) {
        await closeCheckingDialog();
        if (manual) {
          _showCheckResultDialog(
            title: '已是最新版本',
            message: '当前版本 ${localInfo.versionName} '
                '(${localInfo.versionCode})',
          );
        }
        return;
      }

      final patch = updateInfo.patchFor(
        versionCode: localInfo.versionCode,
        oldSha256: localApkSha256,
      );
      if (patch == null) {
        await closeCheckingDialog();
        _showNoIncrementalPatchDialog(localInfo, updateInfo);
        return;
      }

      await closeCheckingDialog();
      _showUpdateDialog(localInfo, updateInfo, patch);
    } on DioException catch (e) {
      await closeCheckingDialog();
      if (cancelledByUser || e.type == DioExceptionType.cancel) {
        return;
      }
      if (manual) {
        _showCheckFailedDialog(_formatDioException(e));
      }
    } on _UpdateException catch (e) {
      await closeCheckingDialog();
      if (manual) {
        _showCheckFailedDialog(e.messageWithCode);
      }
    } catch (e) {
      await closeCheckingDialog();
      if (manual) {
        _showCheckFailedDialog('$e');
      }
    } finally {
      await closeCheckingDialog();
      isChecking.value = false;
    }
  }

  Future<_LocalAppInfo> _getLocalAppInfo() async {
    final result = await _platform.invokeMapMethod<String, dynamic>('getAppInfo');
    if (result == null) {
      throw Exception('无法读取当前应用版本');
    }
    return _LocalAppInfo.fromMap(result);
  }

  Future<bool> _openInstaller(
    String apkPath, {
    int? expectedVersionCode,
  }) async {
    await _savePendingInstallApkPath(
      apkPath,
      expectedVersionCode: expectedVersionCode,
    );
    try {
      final result = await _platform.invokeMethod<Object?>('installApk', {
        'apkPath': apkPath,
      }).timeout(
        const Duration(seconds: 5),
        onTimeout: () => <String, Object?>{
          'requested': true,
          'launched': false,
        },
      );

      final launched = _installerLaunchConfirmed(result);
      if (launched) {
        await _clearPendingInstallApkPath();
      }
      return launched;
    } on PlatformException catch (e) {
      if (e.code == _appNotForegroundCode) {
        return false;
      }
      if (e.code != _unknownAppSourcesCode) {
        await _clearPendingInstallApkPath();
      }
      rethrow;
    } catch (_) {
      await _clearPendingInstallApkPath();
      rethrow;
    }
  }

  bool _installerLaunchConfirmed(Object? result) {
    if (result is bool) return result;
    if (result is Map) {
      return result['launched'] == true;
    }
    return false;
  }

  Future<bool> _canRequestPackageInstalls() async {
    if (!Platform.isAndroid) return false;

    try {
      return await _platform.invokeMethod<bool>('canRequestPackageInstalls') ??
          false;
    } catch (_) {
      return false;
    }
  }

  Future<void> _startUpdateForegroundService() async {
    if (!Platform.isAndroid) return;
    _lastForegroundUpdateAt = null;
    _lastForegroundProgress = -1;
    _lastForegroundStatus = null;
    await _invokeUpdateForegroundService(
      'startUpdateForegroundService',
      force: true,
    );
  }

  void _queueUpdateForegroundService({bool force = false}) {
    if (!Platform.isAndroid) return;
    unawaited(_invokeUpdateForegroundService(
      'updateUpdateForegroundService',
      force: force,
    ));
  }

  Future<void> _stopUpdateForegroundService() async {
    if (!Platform.isAndroid) return;
    try {
      await _platform.invokeMethod<bool>('stopUpdateForegroundService');
    } catch (_) {
      // 更新 UI 失败不应掩盖真实下载或安装错误。
    }
  }

  Future<void> _invokeUpdateForegroundService(
    String method, {
    required bool force,
  }) async {
    final status = updateStatus.value;
    final progress = updateProgress.value.clamp(0.0, 1.0).toDouble();
    final progressPercent = (progress * 100).round().clamp(0, 100).toInt();
    final now = DateTime.now();

    if (!force) {
      final lastAt = _lastForegroundUpdateAt;
      final progressMoved = (progress - _lastForegroundProgress).abs() >= 0.02;
      final statusChanged = status != _lastForegroundStatus;
      final enoughTimePassed =
          lastAt == null || now.difference(lastAt).inMilliseconds >= 900;
      if (!progressMoved && !statusChanged && !enoughTimePassed) {
        return;
      }
    }

    _lastForegroundUpdateAt = now;
    _lastForegroundProgress = progress;
    _lastForegroundStatus = status;

    try {
      await _platform.invokeMethod<bool>(method, {
        'status': status,
        'progress': progressPercent,
      });
    } catch (_) {
      // 前台通知是后台保活增强，失败时继续走原更新流程。
    }
  }

  Future<void> _savePendingInstallApkPath(
    String apkPath, {
    int? expectedVersionCode,
  }) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_pendingInstallApkPathKey, apkPath);
    if (expectedVersionCode != null) {
      await prefs.setInt(_pendingInstallVersionCodeKey, expectedVersionCode);
    }
  }

  Future<String?> _pendingInstallApkPath() async {
    final prefs = await SharedPreferences.getInstance();
    final apkPath = prefs.getString(_pendingInstallApkPathKey);
    if (apkPath == null || apkPath.isEmpty) return null;
    return apkPath;
  }

  Future<int?> _pendingInstallVersionCode() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getInt(_pendingInstallVersionCodeKey);
  }

  Future<void> _clearPendingInstallApkPath() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_pendingInstallApkPathKey);
    await prefs.remove(_pendingInstallVersionCodeKey);
  }

  Future<bool> _clearPendingInstallIfAlreadyApplied() async {
    final expectedVersionCode = await _pendingInstallVersionCode();
    if (expectedVersionCode == null) return false;

    try {
      final localInfo = await _getLocalAppInfo();
      if (localInfo.versionCode >= expectedVersionCode) {
        await _clearPendingInstallApkPath();
        return true;
      }
    } catch (_) {
      // 读取版本失败时保持 pending 记录，避免丢失安装入口。
    }
    return false;
  }

  Future<void> _resumePendingInstallIfPermitted({
    required bool showMessage,
    bool force = false,
  }) async {
    if (_isRetryingPendingInstall) return;

    final apkPath = await _pendingInstallApkPath();
    if (apkPath == null) return;
    final canResumeWhileUpdating = force && _isWaitingForInstaller;
    if (isUpdating.value && !canResumeWhileUpdating) return;
    if (await _clearPendingInstallIfAlreadyApplied()) return;

    final apkFile = File(apkPath);
    if (!await apkFile.exists()) {
      await _clearPendingInstallApkPath();
      if (showMessage) {
        Get.snackbar('安装包已失效', '请重新检查更新并下载安装包');
      }
      return;
    }

    final canInstall = await _canRequestPackageInstalls();
    if (!canInstall) {
      if (showMessage) {
        Get.snackbar('仍需授权', '安装包已保留，请开启安装未知应用权限后返回 Trace');
      }
      return;
    }

    _isRetryingPendingInstall = true;
    isUpdating.value = true;
    updateProgress.value = 1;
    updateStatus.value = '打开系统安装器...';
    _closeUpdateDialogIfOpen();
    _queueUpdateForegroundService(force: true);
    try {
      final launched = await _openInstaller(apkPath);
      if (launched) {
        await _stopUpdateForegroundService();
      } else {
        _markInstallerReadyForForegroundRetry();
      }
      if (!launched && showMessage) {
        Get.snackbar('安装包已就绪', '请点按通知里的“继续安装”，或再次回到 Trace 自动打开系统安装器');
      }
    } on PlatformException catch (e) {
      if (e.code == _unknownAppSourcesCode) {
        if (showMessage) {
          Get.snackbar('仍需授权', '安装包已保留，请开启安装未知应用权限后返回 Trace');
        }
        return;
      }
      if (showMessage) {
        Get.snackbar('安装失败', _formatUpdateFailure(e));
      }
    } catch (e) {
      if (showMessage) {
        Get.snackbar('安装失败', _formatUpdateFailure(e));
      }
    } finally {
      _closeUpdateDialogIfOpen();
      isUpdating.value = false;
      _isRetryingPendingInstall = false;
    }
  }

  bool get _isWaitingForInstaller {
    return updateProgress.value >= 0.99 && updateStatus.value.contains('安装');
  }

  void _markInstallerReadyForForegroundRetry() {
    updateProgress.value = 1;
    updateStatus.value = '安装包已就绪，请点按通知或回到 Trace 继续安装';
    unawaited(_showInstallReadyNotification());
  }

  Future<void> _showInstallReadyNotification() async {
    if (!Platform.isAndroid) return;
    final apkPath = await _pendingInstallApkPath();
    if (apkPath == null) return;
    try {
      await _platform.invokeMethod<bool>('showInstallReadyNotification', {
        'apkPath': apkPath,
        'status': updateStatus.value,
      });
    } catch (_) {
      _queueUpdateForegroundService(force: true);
    }
  }

  void _closeUpdateDialogIfOpen() {
    if (Get.isDialogOpen != true) return;
    try {
      Get.back<void>();
    } catch (_) {
      // Dialog state can be stale after Android background/foreground switches.
    }
  }

  Future<bool> _handlePendingInstallBeforeUpdateCheck({
    required bool manual,
  }) async {
    final apkPath = await _pendingInstallApkPath();
    if (apkPath == null) return false;
    if (await _clearPendingInstallIfAlreadyApplied()) return false;

    if (!await File(apkPath).exists()) {
      await _clearPendingInstallApkPath();
      return false;
    }

    if (await _canRequestPackageInstalls()) {
      await _resumePendingInstallIfPermitted(showMessage: manual);
      return true;
    }

    if (!manual) return true;

    try {
      await _openInstaller(apkPath);
    } on PlatformException catch (e) {
      if (e.code == _unknownAppSourcesCode) {
        Get.snackbar('需要授权', '请开启安装未知应用权限，返回 Trace 后会自动继续安装');
        return true;
      }
      Get.snackbar('安装失败', _formatUpdateFailure(e));
    } catch (e) {
      Get.snackbar('安装失败', _formatUpdateFailure(e));
    }
    return true;
  }

  Future<_RemoteUpdateInfo> _fetchUpdateInfo(
    _LocalAppInfo localInfo, {
    required CancelToken cancelToken,
  }) async {
    final requests = <_ManifestRequest>[
      if (ShareLinks.cloudflareUpdateManifestUrl.isNotEmpty)
        _ManifestRequest(
          url: _cloudflareManifestUrl(localInfo),
          source: _ManifestSource.cloudflare,
        ),
      if (ShareLinks.emergencyUpdateManifestUrl.isNotEmpty)
        _ManifestRequest(
          url: ShareLinks.emergencyUpdateManifestUrl,
          source: _ManifestSource.emergency,
        ),
      if (ShareLinks.cloudflareUpdateManifestUrl.isEmpty)
        _ManifestRequest(
          url: ShareLinks.legacyGithubLatestManifestUrl,
          source: _ManifestSource.legacyGithubLatest,
        ),
    ];

    Object? lastError;
    StackTrace? lastStackTrace;
    for (final request in requests) {
      try {
        updateStatus.value = '正在连接更新服务...';
        final response = await _dio.get<String>(
          request.url,
          cancelToken: cancelToken,
          options: Options(responseType: ResponseType.plain),
        );
        final raw = response.data;
        if (raw == null || raw.trim().isEmpty) {
          throw _UpdateException('EMPTY_MANIFEST', '更新清单为空');
        }
        final json = jsonDecode(raw) as Map<String, dynamic>;
        final updateInfo = _RemoteUpdateInfo.fromJson(
          json,
          source: request.source,
          localVersionCode: localInfo.versionCode,
        );
        await _verifyPayloadSignature(updateInfo);
        return updateInfo;
      } on DioException catch (error, stackTrace) {
        final errorCode = _errorCodeFromResponse(error.response);
        if (_isTerminalPublicError(errorCode)) {
          throw _UpdateException(
            errorCode!,
            _messageFromResponse(error.response) ?? '更新服务器拒绝当前请求',
          );
        }
        lastError = error;
        lastStackTrace = stackTrace;
      } on _UpdateException catch (error, stackTrace) {
        if (_isTerminalPublicError(error.errorCode) ||
            request.source == _ManifestSource.legacyGithubLatest) {
          rethrow;
        }
        lastError = error;
        lastStackTrace = stackTrace;
      } catch (error, stackTrace) {
        lastError = error;
        lastStackTrace = stackTrace;
      }
    }

    if (lastError != null) {
      Error.throwWithStackTrace(lastError, lastStackTrace ?? StackTrace.current);
    }
    throw _UpdateException('NO_MANIFEST_SOURCE', '没有可用的更新清单地址');
  }

  String _cloudflareManifestUrl(_LocalAppInfo localInfo) {
    final uri = Uri.parse(ShareLinks.cloudflareUpdateManifestUrl);
    final queryParameters = Map<String, String>.from(uri.queryParameters);
    queryParameters.addAll({
      'appId': ShareLinks.appId,
      'platform': 'android',
      'channel': ShareLinks.updateChannel,
      'versionCode': localInfo.versionCode.toString(),
      'schemaVersion': _manifestSchemaVersion.toString(),
      'capabilities': _clientCapabilities,
    });
    return uri.replace(queryParameters: queryParameters).toString();
  }

  Future<T?> _showTraceUpdateDialog<T>(
    Widget dialog, {
    bool barrierDismissible = true,
  }) {
    return Get.dialog<T>(
      dialog,
      barrierDismissible: barrierDismissible,
      barrierColor: Colors.black.withOpacity(0.62),
    );
  }

  void _closeDialogRouteForContext(BuildContext context) {
    if (!context.mounted) return;

    final navigator = Navigator.of(context, rootNavigator: true);
    final route = ModalRoute.of(context);
    if (route != null && route.isActive) {
      if (route.isCurrent) {
        if (navigator.canPop()) {
          navigator.pop();
        }
      } else {
        navigator.removeRoute(route);
      }
      return;
    }

    if (navigator.canPop()) {
      navigator.pop();
    }
  }

  void _showUpdateDialog(
    _LocalAppInfo localInfo,
    _RemoteUpdateInfo updateInfo,
    _RemoteUpdatePatch patch,
  ) {
    _showTraceUpdateDialog(
      TraceDialog(
        title: '发现新版本',
        icon: Icons.system_update_alt,
        color: TraceColors.cyan,
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('当前版本：${localInfo.versionName} (${localInfo.versionCode})'),
            const SizedBox(height: 6),
            Text('最新版本：${updateInfo.versionName} (${updateInfo.versionCode})'),
            const SizedBox(height: 12),
            Text('推荐包类型：增量包 ${_formatBytes(patch.size)}'),
            if (updateInfo.hasFullDownload) ...[
              const SizedBox(height: 6),
              Text('全量包大小：${_formatBytes(updateInfo.apkSize)}'),
            ],
            if (updateInfo.releaseNotes.isNotEmpty) ...[
              const SizedBox(height: 12),
              const Text('更新说明：'),
              const SizedBox(height: 4),
              Text(updateInfo.releaseNotes),
            ],
            const SizedBox(height: 6),
            const Text('将下载增量包并在本机合成新版安装包。'),
          ],
        ),
        actions: [
          TraceDialogAction(
            label: '稍后',
            onPressed: TraceDialog.close,
          ),
          if (updateInfo.hasFullDownload)
            TraceDialogAction(
              label: '全量安装',
              color: TraceColors.cyanSoft,
              onPressed: (context) {
                TraceDialog.close(context);
                _showFullFallbackDialog(
                  localInfo,
                  updateInfo,
                  reason: '你选择直接安装全量 APK。',
                );
              },
            ),
          TraceDialogAction(
            label: '增量更新',
            isPrimary: true,
            onPressed: (context) {
              TraceDialog.close(context);
              unawaited(_applyIncrementalUpdate(localInfo, updateInfo, patch));
            },
          ),
        ],
      ),
    );
  }
  void _showNoIncrementalPatchDialog(
    _LocalAppInfo localInfo,
    _RemoteUpdateInfo updateInfo,
  ) {
    _showTraceUpdateDialog(
      TraceDialog(
        title: '发现新版本',
        icon: Icons.system_update_alt,
        color: TraceColors.amber,
        message: updateInfo.hasFullDownload
            ? '最新版本 ${updateInfo.versionName} 已发布，但当前版本 ${localInfo.versionName} 没有匹配当前安装包的增量更新包。可以改用全量 APK，大小约 ${_formatBytes(updateInfo.apkSize)}，建议在 Wi-Fi 下下载。'
            : '最新版本 ${updateInfo.versionName} 已发布，但当前版本 ${localInfo.versionName} 没有匹配当前安装包的增量更新包，且更新清单未提供可用的全量 APK 下载地址。',
        actions: [
          TraceDialogAction(
            label: '稍后',
            color: TraceColors.amber,
            onPressed: TraceDialog.close,
          ),
          if (updateInfo.hasFullDownload)
            TraceDialogAction(
              label: '下载全量包',
              isPrimary: true,
              color: TraceColors.amber,
              onPressed: (context) {
                TraceDialog.close(context);
                _showFullFallbackDialog(
                  localInfo,
                  updateInfo,
                  reason: '当前安装包没有可用增量补丁。',
                );
              },
            ),
        ],
      ),
    );
  }
  void _showFullFallbackDialog(
    _LocalAppInfo localInfo,
    _RemoteUpdateInfo updateInfo, {
    required String reason,
  }) {
    _showTraceUpdateDialog(
      TraceDialog(
        title: '改用全量包',
        icon: Icons.download_for_offline,
        color: TraceColors.cyanSoft,
        message: '$reason\n\n将下载完整 APK，大小约 ${_formatBytes(updateInfo.apkSize)}。下载完成后会校验 SHA-256，再打开系统安装器。建议在 Wi-Fi 下继续。',
        actions: [
          TraceDialogAction(
            label: '稍后',
            color: TraceColors.cyanSoft,
            onPressed: TraceDialog.close,
          ),
          TraceDialogAction(
            label: '继续下载',
            isPrimary: true,
            color: TraceColors.cyanSoft,
            onPressed: (context) {
              TraceDialog.close(context);
              unawaited(_downloadAndInstallFullApk(localInfo, updateInfo));
            },
          ),
        ],
      ),
    );
  }
  Future<void> _applyIncrementalUpdate(
    _LocalAppInfo localInfo,
    _RemoteUpdateInfo updateInfo,
    _RemoteUpdatePatch patch,
  ) async {
    if (isUpdating.value) return;

    isUpdating.value = true;
    updateProgress.value = 0;
    updateStatus.value = '准备增量更新...';
    _showProgressDialog();

    Object? failure;
    var keepForegroundService = false;
    try {
      await _startUpdateForegroundService();
      if (patch.size <= 0 ||
          patch.size > _TracePatchApplier.maxPatchSizeBytes) {
        throw Exception('增量包大小超出安全限制');
      }

      final tempDir = await getTemporaryDirectory();
      final fileToken = DateTime.now().microsecondsSinceEpoch;
      final patchExtension =
          patch.algorithm == _patchAlgorithmVcdiff ? 'vcdiff' : 'tpatch';
      final patchFile = File(
        '${tempDir.path}/trace_${localInfo.versionCode}_${updateInfo.versionCode}_$fileToken.$patchExtension',
      );
      final outputApk = File(
        '${tempDir.path}/trace_update_${updateInfo.versionCode}_$fileToken.apk',
      );

      updateStatus.value = '下载增量包...';
      _queueUpdateForegroundService(force: true);
      await _downloadWithFallback(
        urls: patch.downloadUrls,
        savePath: patchFile.path,
        phaseName: '下载增量包',
        progressStart: 0,
        progressSpan: 0.45,
        onReceiveProgress: (received, total) {
          if (total > 0) {
            updateProgress.value = (received / total * 0.45).clamp(0.0, 0.45);
            _queueUpdateForegroundService();
          }
        },
      );

      updateStatus.value = '校验增量包...';
      _queueUpdateForegroundService(force: true);
      final patchSha = await _sha256File(patchFile);
      if (patchSha != patch.sha256) {
        throw Exception('增量包校验失败');
      }

      updateStatus.value = '合成新版安装包...';
      _queueUpdateForegroundService(force: true);
      void onPatchProgress(double progress) {
        updateProgress.value = (0.45 + progress * 0.45).clamp(0.45, 0.90);
        _queueUpdateForegroundService();
      }

      if (patch.algorithm == _patchAlgorithmVcdiff) {
        await _VcdiffPatchApplier().apply(
          oldApkPath: localInfo.sourceApkPath,
          patchPath: patchFile.path,
          outputApkPath: outputApk.path,
          expectedOldSha256: patch.oldSha256,
          expectedNewSha256: patch.newSha256,
          expectedNewSize: updateInfo.apkSize,
          onProgress: onPatchProgress,
        );
      } else {
        await _TracePatchApplier().apply(
          oldApkPath: localInfo.sourceApkPath,
          patchPath: patchFile.path,
          outputApkPath: outputApk.path,
          expectedOldSha256: patch.oldSha256,
          expectedNewSha256: patch.newSha256,
          onProgress: onPatchProgress,
        );
      }

      updateStatus.value = '打开系统安装器...';
      updateProgress.value = 1;
      _queueUpdateForegroundService(force: true);
      final launched = await _openInstaller(
        outputApk.path,
        expectedVersionCode: updateInfo.versionCode,
      );
      keepForegroundService = !launched;
      if (!launched) {
        _markInstallerReadyForForegroundRetry();
      }
    } on PlatformException catch (e) {
      failure = e;
    } catch (e) {
      failure = e;
    } finally {
      if (!keepForegroundService) {
        await _stopUpdateForegroundService();
      }
      if (Get.isDialogOpen == true) {
        Get.back<void>();
      }
      isUpdating.value = false;
    }

    if (failure == null) return;
    if (failure is PlatformException &&
        (failure as PlatformException).code == _unknownAppSourcesCode) {
      Get.snackbar('需要授权', '请开启安装未知应用权限，返回 Trace 后会自动继续安装');
      return;
    }
    _showIncrementalUpdateFailedDialog(
      localInfo,
      updateInfo,
      patch,
      error: failure,
    );
  }

  Future<void> _downloadAndInstallFullApk(
    _LocalAppInfo localInfo,
    _RemoteUpdateInfo updateInfo,
  ) async {
    if (isUpdating.value) return;
    if (!updateInfo.hasFullDownload) {
      Get.snackbar('无法全量更新', '更新清单未提供可用的全量 APK 下载地址');
      return;
    }

    isUpdating.value = true;
    updateProgress.value = 0;
    updateStatus.value = '准备下载全量包...';
    _showProgressDialog();

    Object? failure;
    var keepForegroundService = false;
    try {
      await _startUpdateForegroundService();
      final tempDir = await getTemporaryDirectory();
      final fileToken = DateTime.now().microsecondsSinceEpoch;
      final partialApk = File(
        '${tempDir.path}/trace_full_${updateInfo.versionCode}_$fileToken.apk.part',
      );
      final outputApk = File(
        '${tempDir.path}/trace_full_${updateInfo.versionCode}_$fileToken.apk',
      );

      try {
        updateStatus.value = '下载全量包...';
        _queueUpdateForegroundService(force: true);
        await _downloadWithFallback(
          urls: updateInfo.fullDownloadUrls,
          savePath: partialApk.path,
          phaseName: '下载全量包',
          progressStart: 0,
          progressSpan: 0.70,
          onReceiveProgress: (received, total) {
            if (total > 0) {
              updateProgress.value = (received / total * 0.70).clamp(0.0, 0.70);
              _queueUpdateForegroundService();
            }
          },
        );

        updateStatus.value = '校验安装包...';
        updateProgress.value = 0.80;
        _queueUpdateForegroundService(force: true);
        final apkSha = await _sha256File(partialApk);
        if (apkSha != updateInfo.apkSha256) {
          throw Exception('全量安装包校验失败');
        }

        if (await outputApk.exists()) {
          await outputApk.delete();
        }
        await partialApk.rename(outputApk.path);

        updateStatus.value = '打开系统安装器...';
        updateProgress.value = 1;
        _queueUpdateForegroundService(force: true);
        final launched = await _openInstaller(
          outputApk.path,
          expectedVersionCode: updateInfo.versionCode,
        );
        keepForegroundService = !launched;
        if (!launched) {
          _markInstallerReadyForForegroundRetry();
        }
      } catch (_) {
        if (await partialApk.exists()) {
          await partialApk.delete();
        }
        rethrow;
      }
    } on PlatformException catch (e) {
      failure = e;
    } catch (e) {
      failure = e;
    } finally {
      if (!keepForegroundService) {
        await _stopUpdateForegroundService();
      }
      if (Get.isDialogOpen == true) {
        Get.back<void>();
      }
      isUpdating.value = false;
    }

    if (failure == null) return;
    if (failure is PlatformException &&
        (failure as PlatformException).code == _unknownAppSourcesCode) {
      Get.snackbar('需要授权', '请开启安装未知应用权限，返回 Trace 后会自动继续安装');
      return;
    }
    _showFullUpdateFailedDialog(localInfo, updateInfo, error: failure);
  }

  Future<void> _downloadWithFallback({
    required List<String> urls,
    required String savePath,
    required String phaseName,
    required double progressStart,
    required double progressSpan,
    required ProgressCallback onReceiveProgress,
  }) async {
    if (urls.isEmpty) {
      throw _UpdateException('DOWNLOAD_URL_MISSING', '更新清单缺少下载地址');
    }

    Object? lastError;
    StackTrace? lastStackTrace;
    for (var index = 0; index < urls.length; index += 1) {
      final url = urls[index];
      if (url.isEmpty) continue;
      final sourceLabel = _downloadEndpointLabel(url, index);
      try {
        updateStatus.value = '$phaseName（$sourceLabel）...';
        _queueUpdateForegroundService(force: true);
        await _dio.download(
          url,
          savePath,
          onReceiveProgress: (received, total) {
            if (total > 0) {
              final phaseProgress = received / total;
              updateProgress.value =
                  (progressStart + phaseProgress * progressSpan)
                      .clamp(0.0, 1.0);
              final transfer = _formatTransfer(received, total);
              updateStatus.value = '$phaseName（$sourceLabel）... $transfer';
            } else {
              final downloaded = _formatBytes(received);
              updateStatus.value = '$phaseName（$sourceLabel）... 已下载 $downloaded';
            }
            _queueUpdateForegroundService();
            onReceiveProgress(received, total);
          },
        );
        return;
      } catch (error, stackTrace) {
        lastError = error;
        lastStackTrace = stackTrace;
        final partialFile = File(savePath);
        if (await partialFile.exists()) {
          await partialFile.delete();
        }
        if (index < urls.length - 1) {
          updateStatus.value = '$phaseName（$sourceLabel）失败，尝试备用下载...';
          _queueUpdateForegroundService(force: true);
        }
      }
    }

    if (lastError != null) {
      Error.throwWithStackTrace(lastError, lastStackTrace ?? StackTrace.current);
    }
    throw _UpdateException('DOWNLOAD_URL_MISSING', '更新清单缺少下载地址');
  }

  void _showIncrementalUpdateFailedDialog(
    _LocalAppInfo localInfo,
    _RemoteUpdateInfo updateInfo,
    _RemoteUpdatePatch patch, {
    required Object error,
  }) {
    _showTraceUpdateDialog(
      TraceDialog(
        title: '增量更新失败',
        icon: Icons.error_outline,
        color: TraceColors.amber,
        message: '错误：${_formatUpdateFailure(error)}\n\n${updateInfo.hasFullDownload ? '你可以重试增量更新，或改用全量 APK。全量包大小约 ${_formatBytes(updateInfo.apkSize)}，建议在 Wi-Fi 下下载。' : '你可以稍后重试增量更新。当前更新清单未提供全量 APK 下载地址。'}',
        actions: [
          TraceDialogAction(
            label: '稍后',
            color: TraceColors.amber,
            onPressed: TraceDialog.close,
          ),
          TraceDialogAction(
            label: '重试',
            color: TraceColors.amber,
            onPressed: (context) {
              TraceDialog.close(context);
              unawaited(_applyIncrementalUpdate(localInfo, updateInfo, patch));
            },
          ),
          if (updateInfo.hasFullDownload)
            TraceDialogAction(
              label: '改用全量包',
              isPrimary: true,
              color: TraceColors.amber,
              onPressed: (context) {
                TraceDialog.close(context);
                _showFullFallbackDialog(
                  localInfo,
                  updateInfo,
                  reason: '增量更新失败：${_formatUpdateFailure(error)}',
                );
              },
            ),
        ],
      ),
    );
  }
  void _showFullUpdateFailedDialog(
    _LocalAppInfo localInfo,
    _RemoteUpdateInfo updateInfo, {
    required Object error,
  }) {
    _showTraceUpdateDialog(
      TraceDialog(
        title: '全量更新失败',
        icon: Icons.error_outline,
        color: TraceColors.amber,
        message: '错误：${_formatUpdateFailure(error)}',
        actions: [
          TraceDialogAction(
            label: '稍后',
            color: TraceColors.amber,
            onPressed: TraceDialog.close,
          ),
          TraceDialogAction(
            label: '重试',
            isPrimary: true,
            color: TraceColors.amber,
            onPressed: (context) {
              TraceDialog.close(context);
              unawaited(_downloadAndInstallFullApk(localInfo, updateInfo));
            },
          ),
        ],
      ),
    );
  }
  void _showCheckResultDialog({
    required String title,
    required String message,
  }) {
    _showTraceUpdateDialog(
      TraceDialog(
        title: title,
        icon: Icons.check_circle_outline,
        color: TraceColors.mint,
        message: message,
        actions: [
          TraceDialogAction(
            label: '知道了',
            isPrimary: true,
            color: TraceColors.mint,
            onPressed: TraceDialog.close,
          ),
        ],
      ),
    );
  }
  void _showCheckFailedDialog(String message) {
    _showTraceUpdateDialog(
      TraceDialog(
        title: '检查更新失败',
        icon: Icons.error_outline,
        color: TraceColors.amber,
        message: message,
        actions: [
          TraceDialogAction(
            label: '稍后',
            color: TraceColors.amber,
            onPressed: TraceDialog.close,
          ),
          TraceDialogAction(
            label: '重试',
            isPrimary: true,
            color: TraceColors.amber,
            onPressed: (context) {
              TraceDialog.close(context);
              unawaited(checkForUpdates());
            },
          ),
        ],
      ),
    );
  }
  void _showProgressDialog() {
    _showTraceUpdateDialog(
      Obx(
        () => TraceDialog(
          title: '应用更新中',
          icon: Icons.downloading,
          color: TraceColors.cyan,
          content: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(updateStatus.value),
              const SizedBox(height: 16),
              LinearProgressIndicator(
                value: updateProgress.value,
                color: TraceColors.cyan,
                backgroundColor: TraceColors.cyan.withOpacity(0.14),
              ),
              const SizedBox(height: 8),
              Text('${(updateProgress.value * 100).toStringAsFixed(0)}%'),
            ],
          ),
        ),
      ),
      barrierDismissible: false,
    );
  }
  Future<void> _showCheckingDialog({
    required ValueChanged<BuildContext> onCancel,
    required ValueChanged<BuildContext> onPresented,
  }) {
    var didNotifyPresented = false;
    return _showTraceUpdateDialog<void>(
      Builder(
        builder: (context) {
          if (!didNotifyPresented) {
            didNotifyPresented = true;
            WidgetsBinding.instance.addPostFrameCallback((_) {
              if (context.mounted) {
                onPresented(context);
              }
            });
          }

          return Obx(
            () => TraceDialog(
              title: '检查更新',
              icon: Icons.radar,
              color: TraceColors.cyan,
              content: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      const SizedBox(
                        width: 24,
                        height: 24,
                        child: CircularProgressIndicator(
                          strokeWidth: 2.6,
                          color: TraceColors.cyan,
                        ),
                      ),
                      const SizedBox(width: 16),
                      Expanded(child: Text(updateStatus.value)),
                    ],
                  ),
                  const SizedBox(height: 12),
                  const Text(
                    '正在连接更新服务；如暂时不可用，会自动重试备用通道，最多等待 30 秒。',
                    style: TextStyle(fontSize: 12),
                  ),
                ],
              ),
              actions: [
                TraceDialogAction(
                  label: '取消',
                  color: TraceColors.cyan,
                  onPressed: onCancel,
                ),
              ],
            ),
          );
        },
      ),
      barrierDismissible: false,
    ).then((_) {});
  }

  String _dateKey(DateTime value) {
    return '${value.year.toString().padLeft(4, '0')}-'
        '${value.month.toString().padLeft(2, '0')}-'
        '${value.day.toString().padLeft(2, '0')}';
  }

  String _formatBytes(int bytes) {
    if (bytes >= 1024 * 1024) {
      return '${(bytes / 1024 / 1024).toStringAsFixed(1)} MB';
    }
    if (bytes >= 1024) {
      return '${(bytes / 1024).toStringAsFixed(1)} KB';
    }
    return '$bytes B';
  }

  String _formatTransfer(int received, int total) {
    final percent = total <= 0 ? 0 : received / total * 100;
    return '${percent.toStringAsFixed(0)}% '
        '(${_formatBytes(received)} / ${_formatBytes(total)})';
  }

  String _downloadEndpointLabel(String url, int index) {
    final uri = Uri.tryParse(url);
    final host = uri?.host.toLowerCase() ?? '';
    final path = uri?.path.toLowerCase() ?? '';
    if (host == 'github.com' || path.endsWith('/api/public/github-fallback')) {
      return index == 0 ? '主下载' : '备用下载';
    }
    if (path.endsWith('/api/public/download')) {
      return index == 0 ? '主下载' : '备用下载';
    }
    return index == 0 ? '主下载' : '备用下载';
  }

  String _formatUpdateFailure(Object error) {
    if (error is _UpdateException) {
      return error.messageWithCode;
    }
    if (error is DioException) {
      return _formatDioException(error);
    }
    if (error is PlatformException) {
      return error.message ?? error.code;
    }
    return '$error';
  }

  String _formatDioException(DioException error) {
    final errorCode = _errorCodeFromResponse(error.response);
    final message = _messageFromResponse(error.response);
    if (errorCode != null) {
      return message == null ? errorCode : '$errorCode：$message';
    }

    switch (error.type) {
      case DioExceptionType.connectionTimeout:
      case DioExceptionType.sendTimeout:
      case DioExceptionType.receiveTimeout:
        return '连接更新服务器超时，请检查网络后重试';
      case DioExceptionType.badResponse:
        final statusCode = error.response?.statusCode;
        return statusCode == null
            ? '更新服务器返回异常响应'
            : '更新服务器返回 HTTP $statusCode';
      case DioExceptionType.connectionError:
        return '无法连接更新服务器，请检查网络或稍后重试';
      case DioExceptionType.cancel:
        return '检查更新已取消';
      case DioExceptionType.badCertificate:
        return '更新服务器证书校验失败';
      case DioExceptionType.unknown:
        return error.message ?? '未知网络错误';
    }
  }

  Future<String> _sha256File(File file) async {
    final digest = await sha256.bind(file.openRead()).first;
    return digest.toString();
  }

  Future<void> _verifyPayloadSignature(_RemoteUpdateInfo updateInfo) async {
    final signature = updateInfo.payloadSignature;
    if (updateInfo.source == _ManifestSource.emergency && signature == null) {
      throw _UpdateException('SIGNATURE_MISSING', '紧急更新清单缺少 payloadSignature');
    }
    if (signature == null) return;

    if (signature.algorithm != 'ed25519') {
      throw _UpdateException(
        'SIGNATURE_UNSUPPORTED',
        '不支持的更新清单签名算法：${signature.algorithm}',
      );
    }
    if (ShareLinks.updatePayloadPublicKeyBase64.isEmpty) {
      throw _UpdateException('SIGNATURE_KEY_MISSING', '客户端未内置更新清单验签公钥');
    }

    final publicKeyBytes = base64Decode(ShareLinks.updatePayloadPublicKeyBase64);
    final signatureBytes = base64Decode(signature.signatureBase64);
    final payload = utf8.encode(_canonicalJson(updateInfo.signedPayload));
    final algorithm = Ed25519();
    final isValid = await algorithm.verify(
      payload,
      signature: Signature(
        signatureBytes,
        publicKey: SimplePublicKey(
          publicKeyBytes,
          type: KeyPairType.ed25519,
        ),
      ),
    );
    if (!isValid) {
      throw _UpdateException('SIGNATURE_INVALID', '更新清单签名校验失败');
    }
  }

  String? _errorCodeFromResponse(dynamic response) {
    final data = response?.data;
    if (data is Map<String, dynamic>) {
      return data['errorCode'] as String?;
    }
    if (data is String && data.trim().isNotEmpty) {
      try {
        final json = jsonDecode(data);
        if (json is Map<String, dynamic>) {
          return json['errorCode'] as String?;
        }
      } catch (_) {
        return null;
      }
    }
    return null;
  }

  String? _messageFromResponse(dynamic response) {
    final data = response?.data;
    if (data is Map<String, dynamic>) {
      return (data['message'] ?? data['maintenanceMessage']) as String?;
    }
    if (data is String && data.trim().isNotEmpty) {
      try {
        final json = jsonDecode(data);
        if (json is Map<String, dynamic>) {
          return (json['message'] ?? json['maintenanceMessage']) as String?;
        }
      } catch (_) {
        return null;
      }
    }
    return null;
  }

  bool _isTerminalPublicError(String? errorCode) {
    return errorCode == 'NO_UPDATE' ||
        errorCode == 'CHANNEL_STOPPED' ||
        errorCode == 'CLIENT_TOO_OLD' ||
        errorCode == 'SIGNATURE_MISSING' ||
        errorCode == 'SIGNATURE_UNSUPPORTED' ||
        errorCode == 'SIGNATURE_KEY_MISSING' ||
        errorCode == 'SIGNATURE_INVALID';
  }
}

class _TracePatchApplier {
  static final List<int> _magic = utf8.encode('TRACEPATCH1\n');
  static const int maxPatchSizeBytes = 512 * 1024 * 1024;
  static const int _maxManifestLengthBytes = 2 * 1024 * 1024;
  static const int _maxOperationCount = 200000;
  static const int _maxOutputApkSizeBytes = 1024 * 1024 * 1024;

  Future<void> apply({
    required String oldApkPath,
    required String patchPath,
    required String outputApkPath,
    required String expectedOldSha256,
    required String expectedNewSha256,
    required ValueChanged<double> onProgress,
  }) async {
    final oldApk = File(oldApkPath);
    final patchFile = File(patchPath);
    final outputApk = File(outputApkPath);
    final oldApkSize = await oldApk.length();
    final patchSize = await patchFile.length();
    if (patchSize <= _magic.length + 4 || patchSize > maxPatchSizeBytes) {
      throw Exception('增量包大小超出安全限制');
    }

    final oldSha = await sha256.bind(oldApk.openRead()).first;
    if (oldSha.toString() != expectedOldSha256) {
      throw Exception('当前安装包与增量包不匹配');
    }

    final oldRaf = await oldApk.open();
    final patchRaf = await patchFile.open();
    final outRaf = await outputApk.open(mode: FileMode.write);

    try {
      final magic = await _readExactly(patchRaf, _magic.length);
      if (!_listEquals(magic, _magic)) {
        throw Exception('增量包格式错误');
      }

      final manifestLengthBytes = await _readExactly(patchRaf, 4);
      final manifestLength =
          ByteData.sublistView(Uint8List.fromList(manifestLengthBytes))
              .getUint32(0, Endian.little);
      if (manifestLength <= 0 || manifestLength > _maxManifestLengthBytes) {
        throw Exception('增量包清单长度超出安全限制');
      }
      if (_magic.length + 4 + manifestLength > patchSize) {
        throw Exception('增量包清单长度无效');
      }
      final manifestBytes = await _readExactly(patchRaf, manifestLength);
      final manifest = jsonDecode(utf8.decode(manifestBytes)) as Map<String, dynamic>;

      if (manifest['newSha256'] != expectedNewSha256) {
        throw Exception('增量包目标版本校验失败');
      }

      final newSize = _jsonInt(manifest['newSize']);
      if (newSize <= 0 || newSize > _maxOutputApkSizeBytes) {
        throw Exception('增量包输出大小超出安全限制');
      }
      var written = 0;
      final operations = manifest['operations'] as List<dynamic>;
      if (operations.isEmpty || operations.length > _maxOperationCount) {
        throw Exception('增量包操作数量超出安全限制');
      }

      for (final operation in operations) {
        final op = operation as Map<String, dynamic>;
        final kind = op['op'] as String;
        final length = _jsonInt(op['length']);
        if (length <= 0) {
          throw Exception('增量包操作长度无效');
        }

        if (kind == 'copy') {
          final offset = _jsonInt(op['offset']);
          if (offset < 0 || offset + length > oldApkSize) {
            throw Exception('增量包 copy 操作越界');
          }
          await oldRaf.setPosition(offset);
          await _copyBytes(oldRaf, outRaf, length);
        } else if (kind == 'data') {
          await _copyBytes(patchRaf, outRaf, length);
        } else {
          throw Exception('未知增量操作: $kind');
        }

        written += length;
        if (written > newSize) {
          throw Exception('增量包输出大小与清单不匹配');
        }
        if (newSize > 0) {
          onProgress((written / newSize).clamp(0.0, 1.0));
        }
      }

      if (written != newSize) {
        throw Exception('增量包输出大小与清单不匹配');
      }
    } finally {
      await oldRaf.close();
      await patchRaf.close();
      await outRaf.close();
    }

    final newSha = await sha256.bind(outputApk.openRead()).first;
    if (newSha.toString() != expectedNewSha256) {
      throw Exception('合成安装包校验失败');
    }
  }

  Future<void> _copyBytes(
    RandomAccessFile input,
    RandomAccessFile output,
    int length,
  ) async {
    var remaining = length;
    while (remaining > 0) {
      final chunkSize = remaining > 64 * 1024 ? 64 * 1024 : remaining;
      final chunk = await _readExactly(input, chunkSize);
      await output.writeFrom(chunk);
      remaining -= chunk.length;
    }
  }

  Future<List<int>> _readExactly(RandomAccessFile file, int length) async {
    final bytes = await file.read(length);
    if (bytes.length != length) {
      throw Exception('增量包读取失败');
    }
    return bytes;
  }

  bool _listEquals(List<int> a, List<int> b) {
    if (a.length != b.length) return false;
    for (var i = 0; i < a.length; i++) {
      if (a[i] != b[i]) return false;
    }
    return true;
  }

  int _jsonInt(Object? value) {
    if (value is int) return value;
    if (value is num) return value.toInt();
    throw Exception('增量包数值字段错误');
  }
}

class _VcdiffPatchApplier {
  static const int maxPatchSizeBytes = 512 * 1024 * 1024;
  static const int _maxOutputApkSizeBytes = 1024 * 1024 * 1024;

  Future<void> apply({
    required String oldApkPath,
    required String patchPath,
    required String outputApkPath,
    required String expectedOldSha256,
    required String expectedNewSha256,
    required int expectedNewSize,
    required ValueChanged<double> onProgress,
  }) async {
    final oldApk = File(oldApkPath);
    final patchFile = File(patchPath);
    final outputApk = File(outputApkPath);
    final patchSize = await patchFile.length();
    if (patchSize <= 0 || patchSize > maxPatchSizeBytes) {
      throw Exception('VCDIFF 增量包大小超出安全限制');
    }

    final oldSha = await sha256.bind(oldApk.openRead()).first;
    if (oldSha.toString() != expectedOldSha256) {
      throw Exception('当前安装包与 VCDIFF 增量包不匹配');
    }
    onProgress(0.10);

    final oldBytes = await oldApk.readAsBytes();
    final patchBytes = await patchFile.readAsBytes();
    onProgress(0.25);

    final outputBytes = vcdiff.decode(oldBytes, patchBytes);
    if (outputBytes.length > _maxOutputApkSizeBytes) {
      throw Exception('VCDIFF 输出安装包大小超出安全限制');
    }
    if (expectedNewSize > 0 && outputBytes.length != expectedNewSize) {
      throw Exception('VCDIFF 输出安装包大小与清单不匹配');
    }
    onProgress(0.80);

    await outputApk.writeAsBytes(outputBytes, flush: true);
    onProgress(0.95);

    final newSha = await sha256.bind(outputApk.openRead()).first;
    if (newSha.toString() != expectedNewSha256) {
      throw Exception('VCDIFF 合成安装包校验失败');
    }
    onProgress(1);
  }
}

class _LocalAppInfo {
  const _LocalAppInfo({
    required this.versionName,
    required this.versionCode,
    required this.sourceApkPath,
  });

  final String versionName;
  final int versionCode;
  final String sourceApkPath;

  factory _LocalAppInfo.fromMap(Map<String, dynamic> map) {
    return _LocalAppInfo(
      versionName: map['versionName'] as String,
      versionCode: (map['versionCode'] as num).toInt(),
      sourceApkPath: map['sourceApkPath'] as String,
    );
  }
}

class _RemoteUpdateInfo {
  const _RemoteUpdateInfo({
    required this.source,
    required this.schemaVersion,
    required this.appId,
    required this.channel,
    required this.versionName,
    required this.versionCode,
    required this.releaseTag,
    required this.apkAssetName,
    required this.apkSha256,
    required this.apkSize,
    required this.releaseNotes,
    required this.minClientVersionCode,
    required this.capabilities,
    required this.fullDownloadUrl,
    required this.fullFallbackUrl,
    required this.assets,
    required this.payloadSignature,
    required this.patches,
  });

  final _ManifestSource source;
  final int schemaVersion;
  final String appId;
  final String channel;
  final String versionName;
  final int versionCode;
  final String releaseTag;
  final String apkAssetName;
  final String apkSha256;
  final int apkSize;
  final String releaseNotes;
  final int minClientVersionCode;
  final List<String> capabilities;
  final String? fullDownloadUrl;
  final String? fullFallbackUrl;
  final List<Object?> assets;
  final _PayloadSignature? payloadSignature;
  final List<_RemoteUpdatePatch> patches;

  bool get hasFullDownload {
    return apkSha256.isNotEmpty &&
        apkSize > 0 &&
        fullDownloadUrls.isNotEmpty;
  }

  List<String> get fullDownloadUrls {
    return [
      if (fullDownloadUrl != null && fullDownloadUrl!.isNotEmpty)
        fullDownloadUrl!,
      if (fullFallbackUrl != null && fullFallbackUrl!.isNotEmpty)
        fullFallbackUrl!,
    ];
  }

  Map<String, Object?> get signedPayload {
    return {
      'appId': appId,
      'platform': 'android',
      'versionName': versionName,
      'versionCode': versionCode,
      'releaseTag': releaseTag,
      'apkAssetName': apkAssetName,
      'apkSha256': apkSha256,
      'apkSize': apkSize,
      'patches': patches.map((patch) => patch.signedPayload).toList(),
      'assetHashes': assets,
      'minClientVersionCode': minClientVersionCode,
      'capabilities': capabilities,
    };
  }

  factory _RemoteUpdateInfo.fromJson(
    Map<String, dynamic> json, {
    required _ManifestSource source,
    required int localVersionCode,
  }) {
    final errorCode = json['errorCode'] as String?;
    if (errorCode == 'NO_UPDATE') {
      return _RemoteUpdateInfo.noUpdate(source: source);
    }
    if (errorCode != null) {
      throw _UpdateException(
        errorCode,
        (json['message'] ?? json['maintenanceMessage'] ?? errorCode)
            .toString(),
      );
    }
    if (json['updateAvailable'] == false) {
      return _RemoteUpdateInfo.noUpdate(source: source);
    }

    final schemaVersion = _jsonIntWithDefault(json['schemaVersion'], 1);
    final platform = (json['platform'] ?? 'android').toString();
    if (platform != 'android') {
      throw _UpdateException('PLATFORM_MISMATCH', '更新清单平台不匹配：$platform');
    }

    final minClientVersionCode =
        _jsonIntWithDefault(json['minClientVersionCode'], 0);
    if (minClientVersionCode > localVersionCode) {
      throw _UpdateException('CLIENT_TOO_OLD', '当前版本过旧，需要先安装兼容版本');
    }

    final releaseTag = (json['releaseTag'] ?? '').toString();
    final apkAssetName =
        (json['apkAssetName'] ?? 'ble-monitor-android.apk').toString();
    final fullDownloadUrl = _stringOrNull(json['fullDownloadUrl']) ??
        (releaseTag.isEmpty
            ? null
            : ShareLinks.githubReleaseAssetUrl(releaseTag, apkAssetName));
    final fullFallbackUrl = _stringOrNull(json['fullFallbackUrl']);

    return _RemoteUpdateInfo(
      source: source,
      schemaVersion: schemaVersion,
      appId: (json['appId'] ?? ShareLinks.appId).toString(),
      channel: (json['channel'] ?? ShareLinks.updateChannel).toString(),
      versionName: (json['versionName'] ?? '').toString(),
      versionCode: _jsonInt(json['versionCode']),
      releaseTag: releaseTag,
      apkAssetName: apkAssetName,
      apkSha256: (json['apkSha256'] ?? '').toString().toLowerCase(),
      apkSize: _jsonIntWithDefault(json['apkSize'], 0),
      releaseNotes: (json['releaseNotes'] ?? '').toString(),
      minClientVersionCode: minClientVersionCode,
      capabilities: _stringList(json['capabilities']),
      fullDownloadUrl: fullDownloadUrl,
      fullFallbackUrl: fullFallbackUrl,
      assets: (json['assets'] as List<dynamic>?)?.cast<Object?>() ?? const [],
      payloadSignature: _PayloadSignature.tryParse(json['payloadSignature']),
      patches: ((json['patches'] as List<dynamic>?) ?? const [])
          .map(
            (item) => _RemoteUpdatePatch.fromJson(
              item as Map<String, dynamic>,
              releaseTag: releaseTag,
            ),
          )
          .toList(),
    );
  }

  factory _RemoteUpdateInfo.noUpdate({required _ManifestSource source}) {
    return _RemoteUpdateInfo(
      source: source,
      schemaVersion: 1,
      appId: ShareLinks.appId,
      channel: ShareLinks.updateChannel,
      versionName: '',
      versionCode: 0,
      releaseTag: '',
      apkAssetName: '',
      apkSha256: '',
      apkSize: 0,
      releaseNotes: '',
      minClientVersionCode: 0,
      capabilities: const [],
      fullDownloadUrl: null,
      fullFallbackUrl: null,
      assets: const [],
      payloadSignature: null,
      patches: const [],
    );
  }

  _RemoteUpdatePatch? patchFor({
    required int versionCode,
    required String oldSha256,
  }) {
    final normalizedOldSha = oldSha256.toLowerCase();
    _RemoteUpdatePatch? bestPatch;
    for (final patch in patches) {
      if (patch.fromVersionCode == versionCode &&
          patch.oldSha256.toLowerCase() == normalizedOldSha &&
          patch.downloadUrls.isNotEmpty) {
        if (!_isSupportedPatchAlgorithm(patch.algorithm)) continue;
        if (bestPatch == null ||
            _patchAlgorithmPriority(patch.algorithm) >
                _patchAlgorithmPriority(bestPatch.algorithm) ||
            (_patchAlgorithmPriority(patch.algorithm) ==
                    _patchAlgorithmPriority(bestPatch.algorithm) &&
                patch.size < bestPatch.size)) {
          bestPatch = patch;
        }
      }
    }
    return bestPatch;
  }

  bool _isSupportedPatchAlgorithm(String algorithm) {
    return algorithm == AppUpdateService._patchAlgorithmVcdiff ||
        algorithm == AppUpdateService._patchAlgorithmTracePatch;
  }

  int _patchAlgorithmPriority(String algorithm) {
    if (algorithm == AppUpdateService._patchAlgorithmVcdiff) return 2;
    if (algorithm == AppUpdateService._patchAlgorithmTracePatch) return 1;
    return 0;
  }
}

class _RemoteUpdatePatch {
  const _RemoteUpdatePatch({
    required this.fromVersionCode,
    required this.toVersionCode,
    required this.assetName,
    required this.algorithm,
    required this.sha256,
    required this.size,
    required this.oldSha256,
    required this.newSha256,
    required this.downloadUrl,
    required this.fallbackUrl,
  });

  final int fromVersionCode;
  final int toVersionCode;
  final String assetName;
  final String algorithm;
  final String sha256;
  final int size;
  final String oldSha256;
  final String newSha256;
  final String? downloadUrl;
  final String? fallbackUrl;

  List<String> get downloadUrls {
    return [
      if (downloadUrl != null && downloadUrl!.isNotEmpty) downloadUrl!,
      if (fallbackUrl != null && fallbackUrl!.isNotEmpty) fallbackUrl!,
    ];
  }

  Map<String, Object?> get signedPayload {
    return {
      'fromVersionCode': fromVersionCode,
      'toVersionCode': toVersionCode,
      'assetName': assetName,
      'sha256': sha256,
      'size': size,
      'oldSha256': oldSha256,
      'newSha256': newSha256,
    };
  }

  factory _RemoteUpdatePatch.fromJson(
    Map<String, dynamic> json, {
    required String releaseTag,
  }) {
    final assetName = (json['assetName'] ?? '').toString();
    final tagAssetUrl = releaseTag.isEmpty || assetName.isEmpty
        ? null
        : ShareLinks.githubReleaseAssetUrl(releaseTag, assetName);
    return _RemoteUpdatePatch(
      fromVersionCode: _jsonInt(json['fromVersionCode']),
      toVersionCode: _jsonIntWithDefault(json['toVersionCode'], 0),
      assetName: assetName,
      algorithm: _patchAlgorithmFromJson(json, assetName),
      sha256: (json['sha256'] ?? '').toString().toLowerCase(),
      size: _jsonInt(json['size']),
      oldSha256: (json['oldSha256'] ?? '').toString().toLowerCase(),
      newSha256: (json['newSha256'] ?? '').toString().toLowerCase(),
      downloadUrl: _stringOrNull(json['downloadUrl']) ?? tagAssetUrl,
      fallbackUrl: _stringOrNull(json['fallbackUrl']),
    );
  }

  static String _patchAlgorithmFromJson(
    Map<String, dynamic> json,
    String assetName,
  ) {
    final raw = (json['algorithm'] ?? json['patchFormat'] ?? json['format'])
        ?.toString()
        .toLowerCase();
    if (raw == 'vcdiff' || raw == 'xdelta3') {
      return AppUpdateService._patchAlgorithmVcdiff;
    }
    if (raw == 'tracepatch' || raw == 'trace') {
      return AppUpdateService._patchAlgorithmTracePatch;
    }
    final lowerAssetName = assetName.toLowerCase();
    if (lowerAssetName.endsWith('.vcdiff') ||
        lowerAssetName.endsWith('.xdelta')) {
      return AppUpdateService._patchAlgorithmVcdiff;
    }
    return AppUpdateService._patchAlgorithmTracePatch;
  }
}

enum _ManifestSource {
  cloudflare,
  emergency,
  legacyGithubLatest,
}

extension _ManifestSourceLabel on _ManifestSource {
  String get label {
    switch (this) {
      case _ManifestSource.cloudflare:
        return '更新服务';
      case _ManifestSource.emergency:
        return '备用更新服务';
      case _ManifestSource.legacyGithubLatest:
        return '备用更新服务';
    }
  }
}

class _ManifestRequest {
  const _ManifestRequest({
    required this.url,
    required this.source,
  });

  final String url;
  final _ManifestSource source;
}

class _PayloadSignature {
  const _PayloadSignature({
    required this.algorithm,
    required this.keyVersion,
    required this.signatureBase64,
  });

  final String algorithm;
  final String keyVersion;
  final String signatureBase64;

  static _PayloadSignature? tryParse(Object? value) {
    if (value == null) return null;
    if (value is String && value.isNotEmpty) {
      return _PayloadSignature(
        algorithm: 'ed25519',
        keyVersion: 'default',
        signatureBase64: value,
      );
    }
    if (value is Map<String, dynamic>) {
      final signature = (value['signature'] ?? value['value'])?.toString();
      if (signature == null || signature.isEmpty) return null;
      return _PayloadSignature(
        algorithm: (value['algorithm'] ?? 'ed25519').toString().toLowerCase(),
        keyVersion: (value['keyVersion'] ?? 'default').toString(),
        signatureBase64: signature,
      );
    }
    return null;
  }
}

class _UpdateException implements Exception {
  const _UpdateException(this.errorCode, this.message);

  final String errorCode;
  final String message;

  String get messageWithCode => '$errorCode：$message';

  @override
  String toString() => messageWithCode;
}

String _canonicalJson(Object? value) {
  if (value is Map) {
    final entries = value.entries
        .map((entry) => MapEntry(entry.key.toString(), entry.value))
        .toList()
      ..sort((a, b) => a.key.compareTo(b.key));
    return '{${entries.map((entry) {
      return '${jsonEncode(entry.key)}:${_canonicalJson(entry.value)}';
    }).join(',')}}';
  }
  if (value is List) {
    return '[${value.map(_canonicalJson).join(',')}]';
  }
  return jsonEncode(value);
}

int _jsonInt(Object? value) {
  if (value is int) return value;
  if (value is num) return value.toInt();
  if (value is String) return int.parse(value);
  throw Exception('更新清单数值字段错误');
}

int _jsonIntWithDefault(Object? value, int defaultValue) {
  if (value == null) return defaultValue;
  return _jsonInt(value);
}

String? _stringOrNull(Object? value) {
  if (value == null) return null;
  final stringValue = value.toString();
  return stringValue.isEmpty ? null : stringValue;
}

List<String> _stringList(Object? value) {
  if (value == null) return const [];
  if (value is String) {
    return value
        .split(',')
        .map((item) => item.trim())
        .where((item) => item.isNotEmpty)
        .toList();
  }
  if (value is List) {
    return value.map((item) => item.toString()).toList();
  }
  return const [];
}
