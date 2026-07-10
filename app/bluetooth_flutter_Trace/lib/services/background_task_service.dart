import 'dart:async';
import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:get/get.dart';
import '../controllers/ble_controller.dart';
import '../controllers/monitor_controller.dart';
import 'notification_service.dart';

class BackgroundTaskService extends GetxService {
  static BackgroundTaskService get to => Get.find();

  final NotificationService _notificationService = Get.find();
  final BleController _bleController = Get.find();
  final MonitorController _monitorController = Get.find();

  Timer? _backgroundCheckTimer;
  AppLifecycleObserver? _lifecycleObserver;
  bool _isBackgroundMode = false;

  @override
  void onInit() {
    super.onInit();
    _initializeBackgroundTask();
    _startBackgroundCheck();
  }

  @override
  void onClose() {
    _backgroundCheckTimer?.cancel();
    final observer = _lifecycleObserver;
    if (observer != null) {
      WidgetsBinding.instance.removeObserver(observer);
      _lifecycleObserver = null;
    }
    super.onClose();
  }

  /// 初始化后台任务
  Future<void> _initializeBackgroundTask() async {
    // 监听应用生命周期变化
    _lifecycleObserver ??= AppLifecycleObserver(this);
    WidgetsBinding.instance.addObserver(_lifecycleObserver!);

    // 初始化通知服务（确保在后台也能显示通知）
    await _notificationService.initialize();

    debugPrint('后台任务服务已初始化');
  }

  /// 开始后台检查定时器
  void _startBackgroundCheck() {
    // 每30秒检查一次后台状态和设备连接
    _backgroundCheckTimer = Timer.periodic(const Duration(seconds: 30), (timer) {
      if (_isBackgroundMode) {
        _performBackgroundCheck();
      }
    });
  }

  /// 执行后台检查
  Future<void> _performBackgroundCheck() async {
    try {
      final monitoringDevices = _monitorController.monitoringDevices;
      if (monitoringDevices.isEmpty) {
        return;
      }

      // 检查蓝牙扫描状态，如果停止了就重启
      if (!_bleController.isScanning.value) {
        debugPrint('后台模式：重新启动蓝牙扫描');
        await _bleController.startScan();
      }

      // 检查是否有监控中的设备
      debugPrint('后台模式：监控设备数量 ${monitoringDevices.length}');
    } catch (e) {
      debugPrint('后台检查失败: $e');
    }
  }

  /// 设置后台模式状态
  void setBackgroundMode(bool isBackground) {
    _isBackgroundMode = isBackground;
    debugPrint('应用状态切换: ${isBackground ? '后台' : '前台'}');
    if (isBackground) {
      unawaited(_performBackgroundCheck());
    }
  }

  /// 确保后台通知权限
  Future<void> ensureNotificationPermission() async {
    if (Platform.isAndroid) {
      final AndroidFlutterLocalNotificationsPlugin? androidImpl =
          _notificationService.flutterLocalNotificationsPlugin
              .resolvePlatformSpecificImplementation<AndroidFlutterLocalNotificationsPlugin>();

      if (androidImpl != null) {
        await androidImpl.requestNotificationsPermission();
      }
    }
  }
}

/// 应用生命周期观察者
class AppLifecycleObserver extends WidgetsBindingObserver {
  final BackgroundTaskService _backgroundTaskService;

  AppLifecycleObserver(this._backgroundTaskService);

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    switch (state) {
      case AppLifecycleState.resumed:
        _backgroundTaskService.setBackgroundMode(false);
        break;
      case AppLifecycleState.paused:
      case AppLifecycleState.inactive:
      case AppLifecycleState.detached:
      case AppLifecycleState.hidden:
        _backgroundTaskService.setBackgroundMode(true);
        break;
    }
  }
}
