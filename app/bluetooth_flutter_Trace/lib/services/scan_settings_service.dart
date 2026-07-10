import 'package:get/get.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:flutter/foundation.dart';

class ScanSettingsService extends GetxController {
  static ScanSettingsService get to => Get.find();

  // 扫描间隔（毫秒）
  var scanInterval = 1000.obs;

  // 扫描间隔（秒）
  double get scanIntervalSeconds => scanInterval.value / 1000.0;

  @override
  void onInit() {
    super.onInit();
    _loadSettings();
  }

  /// 加载设置
  Future<void> _loadSettings() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      scanInterval.value = prefs.getInt('scan_interval') ?? 1000;
    } catch (e) {
      debugPrint('加载扫描设置失败: $e');
    }
  }

  /// 保存设置
  Future<void> _saveSettings() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setInt('scan_interval', scanInterval.value);
    } catch (e) {
      debugPrint('保存扫描设置失败: $e');
    }
  }

  /// 设置扫描间隔（秒）
  Future<void> setScanIntervalSeconds(double seconds,
      {VoidCallback? onChanged}) async {
    if (seconds < 0.1 || seconds > 60.0) {
      Get.snackbar('错误', '扫描间隔必须在0.1-60秒之间');
      return;
    }

    final newValue = (seconds * 1000).round();
    if (scanInterval.value == newValue) {
      onChanged?.call();
      return;
    }

    scanInterval.value = newValue;
    await _saveSettings();
    onChanged?.call();

    Get.snackbar('成功', '扫描间隔已设置为 ${seconds}秒');
  }

  /// 设置扫描间隔（毫秒）
  Future<void> setScanIntervalMilliseconds(int milliseconds,
      {VoidCallback? onChanged}) async {
    if (milliseconds < 100 || milliseconds > 60000) {
      Get.snackbar('错误', '扫描间隔必须在100-60000毫秒之间');
      return;
    }

    if (scanInterval.value == milliseconds) {
      onChanged?.call();
      return;
    }

    scanInterval.value = milliseconds;
    await _saveSettings();
    onChanged?.call();

    Get.snackbar('成功', '扫描间隔已设置为 ${milliseconds}毫秒');
  }

  /// 获取预设间隔选项
  List<Map<String, dynamic>> getPresetIntervals() {
    return [
      {'label': '0.5秒', 'value': 0.5, 'milliseconds': 500},
      {'label': '1秒', 'value': 1.0, 'milliseconds': 1000},
      {'label': '2秒', 'value': 2.0, 'milliseconds': 2000},
      {'label': '3秒', 'value': 3.0, 'milliseconds': 3000},
      {'label': '5秒', 'value': 5.0, 'milliseconds': 5000},
      {'label': '10秒', 'value': 10.0, 'milliseconds': 10000},
    ];
  }
}
