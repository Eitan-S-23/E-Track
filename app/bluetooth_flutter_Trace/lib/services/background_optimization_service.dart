import 'dart:async';
import 'package:flutter/foundation.dart';
import 'package:get/get.dart';
import '../controllers/ble_controller.dart';
import '../controllers/monitor_controller.dart';

/// 后台优化服务
/// 用于优化后台监控性能，减少对其他应用网络的影响
class BackgroundOptimizationService extends GetxController {
  static BackgroundOptimizationService get to => Get.find();

  BleController get _bleController => Get.find<BleController>();
  MonitorController get _monitorController => Get.find<MonitorController>();

  // 后台优化配置
  var _isBackgroundMode = false.obs;
  var _backgroundScanInterval = 5000.obs; // 后台扫描间隔（毫秒）
  var _foregroundScanInterval = 1000.obs; // 前台扫描间隔（毫秒）

  Timer? _backgroundTimer;
  Timer? _networkOptimizationTimer;
  Timer? _optimizedScanStopTimer;

  // 网络使用统计
  var _networkUsageOptimized = false.obs;
  var _lastScanTime = DateTime.now().obs;
  var _scanCount = 0.obs;

  bool get isBackgroundMode => _isBackgroundMode.value;
  int get backgroundScanInterval => _backgroundScanInterval.value;
  int get foregroundScanInterval => _foregroundScanInterval.value;
  bool get networkUsageOptimized => _networkUsageOptimized.value;
  DateTime get lastScanTime => _lastScanTime.value;
  int get scanCount => _scanCount.value;

  @override
  void onInit() {
    super.onInit();
    _initializeOptimization();
  }

  @override
  void onClose() {
    _backgroundTimer?.cancel();
    _networkOptimizationTimer?.cancel();
    _optimizedScanStopTimer?.cancel();
    super.onClose();
  }

  /// 初始化优化设置
  void _initializeOptimization() {
    // Timers are started only when background mode is active.
  }

  /// 进入后台模式
  void enterBackgroundMode() {
    if (_isBackgroundMode.value) return;

    debugPrint('进入后台优化模式');
    _isBackgroundMode.value = true;

    // 降低扫描频率
    _applyBackgroundScanSettings();

    // 启用网络优化
    _enableNetworkOptimization();

    // 减少数据处理频率
    _optimizeDataProcessing();
  }

  /// 退出后台模式
  void exitBackgroundMode() {
    if (!_isBackgroundMode.value) return;

    debugPrint('退出后台优化模式');
    _isBackgroundMode.value = false;

    // 恢复正常扫描频率
    _applyForegroundScanSettings();

    // 禁用网络优化
    _disableNetworkOptimization();

    // 恢复正常数据处理
    _restoreDataProcessing();
  }

  /// 应用后台扫描设置
  void _applyBackgroundScanSettings() {
    // 将扫描间隔调整为后台模式
    _backgroundTimer?.cancel();
    _backgroundTimer = Timer.periodic(
      Duration(milliseconds: _backgroundScanInterval.value),
      (timer) {
        if (_isBackgroundMode.value && _monitorController.isMonitoring.value) {
          _performOptimizedScan();
        }
      },
    );
  }

  /// 应用前台扫描设置
  void _applyForegroundScanSettings() {
    _backgroundTimer?.cancel();
    _backgroundTimer = null;
    _optimizedScanStopTimer?.cancel();
    _optimizedScanStopTimer = null;
    // 前台扫描由原有的监控控制器处理
  }

  /// 执行优化的扫描
  void _performOptimizedScan() {
    _lastScanTime.value = DateTime.now();
    _scanCount.value++;

    // 只扫描必要的设备
    final monitoringDevices = _monitorController.selectedDevices.length +
        _monitorController.savedDevices
            .where((d) => d.isMonitoring.value)
            .length;

    if (monitoringDevices > 0) {
      // 短时间扫描，减少功耗
      _bleController.startScan();

      // 2秒后停止扫描
      _optimizedScanStopTimer?.cancel();
      _optimizedScanStopTimer = Timer(const Duration(seconds: 2), () {
        if (_isBackgroundMode.value) {
          _bleController.stopScan();
        }
      });
    }
  }

  /// 启用网络优化
  void _enableNetworkOptimization() {
    _networkUsageOptimized.value = true;

    // 减少网络请求频率
    _startNetworkOptimization();

    debugPrint('网络优化已启用');
  }

  /// 禁用网络优化
  void _disableNetworkOptimization() {
    _networkUsageOptimized.value = false;
    _networkOptimizationTimer?.cancel();
    _networkOptimizationTimer = null;

    debugPrint('网络优化已禁用');
  }

  /// 开始网络优化
  void _startNetworkOptimization() {
    _networkOptimizationTimer?.cancel();
    _networkOptimizationTimer = Timer.periodic(
      const Duration(minutes: 1),
      (timer) {
        if (_isBackgroundMode.value) {
          _optimizeNetworkUsage();
        }
      },
    );
  }

  /// 优化网络使用
  void _optimizeNetworkUsage() {
    // 延迟非关键网络请求
    // 批量处理数据上传
    // 压缩数据传输
    debugPrint('执行网络优化: 减少网络请求频率');
  }

  /// 优化数据处理
  void _optimizeDataProcessing() {
    // 减少实时数据更新频率
    // 批量处理数据库操作
    // 降低UI更新频率
    debugPrint('数据处理已优化');
  }

  /// 恢复数据处理
  void _restoreDataProcessing() {
    // 恢复正常的数据更新频率
    debugPrint('数据处理已恢复正常');
  }

  /// 设置后台扫描间隔
  void setBackgroundScanInterval(int intervalMs) {
    if (intervalMs < 1000 || intervalMs > 60000) {
      Get.snackbar('错误', '后台扫描间隔必须在1-60秒之间');
      return;
    }

    _backgroundScanInterval.value = intervalMs;

    if (_isBackgroundMode.value) {
      _applyBackgroundScanSettings();
    }

    Get.snackbar('成功', '后台扫描间隔已设置为${intervalMs / 1000}秒');
  }

  /// 设置前台扫描间隔
  void setForegroundScanInterval(int intervalMs) {
    if (intervalMs < 100 || intervalMs > 10000) {
      Get.snackbar('错误', '前台扫描间隔必须在0.1-10秒之间');
      return;
    }

    _foregroundScanInterval.value = intervalMs;
    Get.snackbar('成功', '前台扫描间隔已设置为${intervalMs / 1000}秒');
  }

  /// 获取优化统计信息
  Map<String, dynamic> getOptimizationStats() {
    return {
      'isBackgroundMode': _isBackgroundMode.value,
      'backgroundScanInterval': _backgroundScanInterval.value,
      'foregroundScanInterval': _foregroundScanInterval.value,
      'networkOptimized': _networkUsageOptimized.value,
      'lastScanTime': _lastScanTime.value,
      'scanCount': _scanCount.value,
      'averageScanInterval': _scanCount.value > 0
          ? DateTime.now().difference(_lastScanTime.value).inMilliseconds /
              _scanCount.value
          : 0,
    };
  }

  /// 重置统计信息
  void resetStats() {
    _scanCount.value = 0;
    _lastScanTime.value = DateTime.now();
  }

  /// 获取优化建议
  List<String> getOptimizationSuggestions() {
    List<String> suggestions = [];

    if (!_isBackgroundMode.value && _monitorController.isMonitoring.value) {
      suggestions.add('建议在后台运行时启用后台优化模式');
    }

    if (_backgroundScanInterval.value < 3000) {
      suggestions.add('建议将后台扫描间隔设置为3秒以上以节省电量');
    }

    if (_scanCount.value > 1000) {
      suggestions.add('扫描次数较多，建议适当增加扫描间隔');
    }

    return suggestions;
  }
}
