import 'dart:async';
import 'dart:io';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:get/get.dart';
import 'package:vibration/vibration.dart';
import 'package:audioplayers/audioplayers.dart';
import '../models/device_settings.dart';
import '../models/device_data.dart';
import 'database_service.dart';
import 'notification_service.dart';

class AlertService extends GetxController {
  static AlertService get to => Get.find();

  final DatabaseService _dbService = DatabaseService();
  final AudioPlayer _audioPlayer = AudioPlayer();
  final NotificationService _notificationService = NotificationService();
  StreamSubscription<PlayerState>? _playerStateSubscription;
  StreamSubscription<void>? _playerCompleteSubscription;

  // 存储设备设置的缓存
  final Map<String, DeviceSettings> _deviceSettingsCache = {};

  // 存储上次报警时间，避免频繁报警
  final Map<String, DateTime> _lastAlertTime = {};

  // 存储上次报警的数据，用于判断是否是相同的异常
  final Map<String, String> _lastAlertDataHash = {};

  // 报警冷却时间（秒）- 减少冷却时间让报警更及时
  static const int alertCooldownSeconds = 5;

  // 跟踪当前是否有报警对话框显示
  bool _isAlertDialogShowing = false;
  String? _currentAlertDialogHash;

  // 跟踪上次显示的Snackbar
  DateTime? _lastSnackbarTime;
  String? _lastSnackbarMessage;

  @override
  void onInit() {
    super.onInit();
    _loadAllDeviceSettings();
    _initializeAudioPlayer();
  }

  @override
  void onClose() {
    _playerStateSubscription?.cancel();
    _playerCompleteSubscription?.cancel();
    _audioPlayer.dispose();
    super.onClose();
  }

  /// 初始化音频播放器
  void _initializeAudioPlayer() {
    try {
      // 设置音频播放器配置
      _audioPlayer.setReleaseMode(ReleaseMode.stop);
      _audioPlayer.setPlayerMode(PlayerMode.mediaPlayer);

      // 设置音量（确保默认音量不为0）
      _audioPlayer.setVolume(1.0);

      // 监听播放状态
      _playerStateSubscription =
          _audioPlayer.onPlayerStateChanged.listen((PlayerState state) {
        debugPrint('音频播放器状态: $state');
      });

      // 监听播放完成
      _playerCompleteSubscription = _audioPlayer.onPlayerComplete.listen((_) {
        debugPrint('音频播放完成');
      });

      debugPrint('音频播放器初始化完成');
    } catch (e) {
      debugPrint('音频播放器初始化失败: $e');
    }
  }

  /// 加载所有设备设置到缓存
  Future<void> _loadAllDeviceSettings() async {
    try {
      final settingsList = await _dbService.getAllDeviceSettings();
      for (var settings in settingsList) {
        _deviceSettingsCache[settings.deviceId] = settings;
      }
    } catch (e) {
      debugPrint('加载设备设置失败: $e');
    }
  }

  /// 获取设备设置（优先从缓存获取）
  Future<DeviceSettings> getDeviceSettings(String deviceId) async {
    if (_deviceSettingsCache.containsKey(deviceId)) {
      return _deviceSettingsCache[deviceId]!;
    }

    var settings = await _dbService.getDeviceSettings(deviceId);
    if (settings == null) {
      // 如果没有设置，创建默认设置
      settings = DeviceSettings(deviceId: deviceId);
      await _dbService.saveDeviceSettings(settings);
    }

    _deviceSettingsCache[deviceId] = settings;
    return settings;
  }

  /// 保存设备设置
  Future<void> saveDeviceSettings(DeviceSettings settings) async {
    try {
      await _dbService.saveDeviceSettings(settings);
      _deviceSettingsCache[settings.deviceId] = settings;
    } catch (e) {
      debugPrint('保存设备设置失败: $e');
      rethrow;
    }
  }

  /// 检查数据是否超出阈值并触发报警
  Future<void> checkThresholds(DeviceData data, double powerConsumption) async {
    try {
      final settings = await getDeviceSettings(data.deviceId);

      debugPrint('阈值设置 - 设备: ${data.deviceName}(${data.deviceId}) | \n'
          ' current: ${settings.currentThreshold}${settings.currentUnit},'
          ' voltage: ${settings.voltageThreshold}${settings.voltageUnit},'
          ' power: ${settings.powerThreshold}${settings.powerUnit},'
          ' consumption: ${settings.powerConsumptionThreshold}${settings.powerConsumptionUnit},'
          ' alertEnabled: ${settings.alertEnabled}, type: ${settings.alertType}');

      if (!settings.alertEnabled) return;

      List<String> exceededThresholds = [];

      // 转换电流到统一单位进行比较
      final currentInTargetUnit =
          _convertCurrent(data.current, data.currentUnit, settings.currentUnit);

      debugPrint(
          '阈值检查 - 设备: ${data.deviceName}, 电流: ${data.current}${data.currentUnit} = ${currentInTargetUnit.toStringAsFixed(6)}${settings.currentUnit}, 阈值: ${settings.currentThreshold}${settings.currentUnit}');

      // 检查电流阈值 - 确保阈值大于0才检查
      if (settings.currentThreshold > 0 &&
          currentInTargetUnit > settings.currentThreshold) {
        exceededThresholds.add(
            '电流: ${currentInTargetUnit.toStringAsFixed(2)}${settings.currentUnit} > ${settings.currentThreshold}${settings.currentUnit}');
        debugPrint(
            '🚨 电流超出阈值: ${currentInTargetUnit.toStringAsFixed(2)} > ${settings.currentThreshold}');
      }

      // 转换电压到统一单位进行比较
      final voltageInTargetUnit =
          _convertVoltage(data.voltage, 'mV', settings.voltageUnit);

      // 检查电压阈值
      if (settings.voltageThreshold > 0 &&
          voltageInTargetUnit > settings.voltageThreshold) {
        exceededThresholds.add(
            '电压: ${voltageInTargetUnit.toStringAsFixed(2)}${settings.voltageUnit} > ${settings.voltageThreshold}${settings.voltageUnit}');
        debugPrint(
            '电压超出阈值: ${voltageInTargetUnit.toStringAsFixed(2)} > ${settings.voltageThreshold}');
      }

      // 转换功率到统一单位进行比较
      final powerInTargetUnit =
          _convertPower(data.power, 'mW', settings.powerUnit);

      // 检查功率阈值
      if (settings.powerThreshold > 0 &&
          powerInTargetUnit > settings.powerThreshold) {
        exceededThresholds.add(
            '功率: ${powerInTargetUnit.toStringAsFixed(2)}${settings.powerUnit} > ${settings.powerThreshold}${settings.powerUnit}');
        debugPrint(
            '功率超出阈值: ${powerInTargetUnit.toStringAsFixed(2)} > ${settings.powerThreshold}');
      }

      // 转换耗电量到统一单位进行比较
      final powerConsumptionInTargetUnit = _convertPowerConsumption(
          powerConsumption, 'mAh', settings.powerConsumptionUnit);

      // 检查耗电量阈值
      if (settings.powerConsumptionThreshold > 0 &&
          powerConsumptionInTargetUnit > settings.powerConsumptionThreshold) {
        exceededThresholds.add(
            '耗电量: ${powerConsumptionInTargetUnit.toStringAsFixed(2)}${settings.powerConsumptionUnit} > ${settings.powerConsumptionThreshold}${settings.powerConsumptionUnit}');
        debugPrint(
            '耗电量超出阈值: ${powerConsumptionInTargetUnit.toStringAsFixed(2)} > ${settings.powerConsumptionThreshold}');
      }

      // 如果有超出阈值的项目，触发报警
      if (exceededThresholds.isNotEmpty) {
        // 创建当前异常数据的哈希值
        final currentDataHash =
            '${data.current}_${data.voltage}_${data.power}_${powerConsumption}';

        // 首先检查基本的冷却时间（所有报警间隔至少5秒）
        final lastAlert = _lastAlertTime[data.deviceId];
        if (lastAlert != null) {
          final timeSinceLastAlert =
              DateTime.now().difference(lastAlert).inSeconds;
          if (timeSinceLastAlert < alertCooldownSeconds) {
            debugPrint(
                '距离上次报警仅${timeSinceLastAlert}秒，需要等待${alertCooldownSeconds - timeSinceLastAlert}秒');
            return;
          }
        }

        // 然后检查是否是相同的连续异常数据
        final lastDataHash = _lastAlertDataHash[data.deviceId];
        if (lastDataHash == currentDataHash) {
          // 相同的异常数据，需要更长的冷却时间
          if (lastAlert != null) {
            final timeSinceLastAlert =
                DateTime.now().difference(lastAlert).inSeconds;
            if (timeSinceLastAlert < 60) {
              // 相同数据60秒内只报警一次
              debugPrint('相同异常数据${timeSinceLastAlert}秒内已报警，跳过');
              return;
            }
          }
        }

        // 触发报警并更新记录
        // 先更新时间戳，防止异步执行期间重复触发
        _lastAlertTime[data.deviceId] = DateTime.now();
        _lastAlertDataHash[data.deviceId] = currentDataHash;

        // 然后触发报警
        await _triggerAlert(data.deviceName, exceededThresholds, settings);
      } else {
        // 没有异常，清除上次的异常数据哈希
        _lastAlertDataHash.remove(data.deviceId);

        // 如果当前对话框是这个设备的，可以考虑清除对话框状态
        // 这样下次出现新的异常时可以显示对话框
        if (_currentAlertDialogHash?.startsWith(data.deviceName) == true) {
          // 如果当前显示的对话框是这个设备的，但设备已恢复正常
          // 我们不自动关闭对话框（让用户手动关闭），但允许下次显示新的对话框
          debugPrint('设备 ${data.deviceName} 已恢复正常，清除对话框哈希缓存');
        }
      }
    } catch (e) {
      debugPrint('检查阈值时出错: $e');
    }
  }

  /// 触发报警
  Future<void> _triggerAlert(String deviceName, List<String> exceededItems,
      DeviceSettings settings) async {
    final message = '设备 $deviceName 异常:\n${exceededItems.join('\n')}';

    debugPrint('=== 开始触发报警 ===');
    debugPrint('设备: $deviceName');
    debugPrint('异常项目: ${exceededItems.join(', ')}');
    debugPrint('报警类型: ${settings.alertType}');
    debugPrint('自定义铃声路径: ${settings.customSoundPath}');

    // 显示应用内通知（仅当前台运行时显示）
    if (Get.context != null) {
      // 检查是否需要显示Snackbar（避免短时间内重复显示相同内容）
      bool shouldShowSnackbar = true;
      if (_lastSnackbarMessage == message && _lastSnackbarTime != null) {
        final timeSinceLastSnackbar =
            DateTime.now().difference(_lastSnackbarTime!).inSeconds;
        if (timeSinceLastSnackbar < 8) {
          // 8秒内不重复显示相同的Snackbar
          shouldShowSnackbar = false;
          debugPrint('相同的Snackbar在${timeSinceLastSnackbar}秒前已显示，跳过');
        }
      }

      if (shouldShowSnackbar) {
        // 关闭之前的Snackbar（如果存在）
        if (Get.isSnackbarOpen) {
          Get.closeCurrentSnackbar();
        }

        Get.snackbar(
          '⚠️ 异常用电量报警',
          message,
          snackPosition: SnackPosition.TOP,
          backgroundColor: const Color(0xFFFF6B6B),
          colorText: Colors.white,
          duration: const Duration(seconds: 8), // 延长显示时间
          isDismissible: true,
          margin: const EdgeInsets.all(16),
          borderRadius: 8,
          showProgressIndicator: true,
          progressIndicatorBackgroundColor: Colors.white24,
          progressIndicatorValueColor:
              const AlwaysStoppedAnimation<Color>(Colors.white),
        );

        _lastSnackbarMessage = message;
        _lastSnackbarTime = DateTime.now();
        debugPrint('Snackbar通知已显示');
      }

      // 创建对话框内容的哈希值，用于去重
      final dialogHash = '$deviceName-${exceededItems.join('-')}';

      // 只有当没有对话框显示或者是不同的报警内容时才显示新对话框
      if (!_isAlertDialogShowing || _currentAlertDialogHash != dialogHash) {
        _showAlertDialog(deviceName, exceededItems, dialogHash);
      } else {
        debugPrint('相同的报警对话框已显示，跳过重复显示');
      }
    } else {
      debugPrint('Get.context为null，跳过前台通知显示，但仍触发声音和系统通知');
    }

    // 始终显示后台通知（无论前台后台）
    try {
      await _notificationService.showDeviceAlertNotification(
        deviceName: deviceName,
        exceededItems: exceededItems,
      );
      debugPrint('后台通知已发送');
    } catch (e) {
      debugPrint('发送后台通知失败: $e');
    }

    debugPrint('报警消息: $message');

    // 根据设置触发震动和/或声音
    try {
      switch (settings.alertType) {
        case AlertType.vibration:
          debugPrint('触发震动报警');
          await _triggerVibration();
          break;
        case AlertType.sound:
          debugPrint('触发铃声报警');
          await _playAlertSound(settings.customSoundPath);
          break;
        case AlertType.both:
          debugPrint('触发震动+铃声报警');
          await Future.wait([
            _triggerVibration(),
            _playAlertSound(settings.customSoundPath),
          ]);
          break;
      }
    } catch (e) {
      debugPrint('触发物理报警失败: $e');
    }

    debugPrint('=== 报警触发完成 ===');
  }

  /// 触发震动
  Future<void> _triggerVibration() async {
    try {
      if (await Vibration.hasVibrator() == true) {
        // 更强烈的震动模式：连续三次震动
        await Vibration.vibrate(
            pattern: [0, 300, 200, 400, 200, 500, 200, 300]);
        debugPrint('报警震动已触发');
      } else {
        debugPrint('设备不支持震动（如Windows），但仍会显示通知');
        // Windows不支持震动，但不应该静默失败
        // 通知和弹窗会在_triggerAlert中处理
      }
    } catch (e) {
      debugPrint('震动失败: $e');
    }
  }

  /// 播放报警声音
  Future<void> _playAlertSound(String? customSoundPath) async {
    try {
      if (customSoundPath != null && customSoundPath.isNotEmpty) {
        // 播放自定义铃声
        debugPrint('播放自定义铃声: $customSoundPath');

        // 检查文件是否存在
        final soundFile = File(customSoundPath);
        if (!await soundFile.exists()) {
          debugPrint('自定义铃声文件不存在: $customSoundPath');
          // 回退到默认铃声
          await _playDefaultAlertSound();
          return;
        }

        // 停止之前的播放并设置音量
        await _audioPlayer.stop();
        await _audioPlayer.setVolume(1.0);

        try {
          // 尝试播放自定义铃声
          await _audioPlayer.play(DeviceFileSource(customSoundPath));
          debugPrint('自定义报警声音已播放');
        } catch (e) {
          debugPrint('播放自定义铃声失败: $e');
          // 如果自定义铃声播放失败，回退到默认铃声
          await _playDefaultAlertSound();
        }
      } else {
        // 播放默认报警声音
        await _playDefaultAlertSound();
      }
    } catch (e) {
      debugPrint('播放声音失败: $e');
      // 最后的回退：尝试使用SystemSound
      try {
        await SystemSound.play(SystemSoundType.alert);
      } catch (e2) {
        debugPrint('SystemSound也失败: $e2');
      }
    }
  }

  /// 播放默认报警声音
  Future<void> _playDefaultAlertSound() async {
    debugPrint('播放默认报警声音');

    try {
      // 在Windows上，尝试播放Windows系统声音
      if (Platform.isWindows) {
        // Windows系统声音文件路径
        const windowsAlertSound =
            r'C:\Windows\Media\Windows Notify System Generic.wav';
        final soundFile = File(windowsAlertSound);

        if (await soundFile.exists()) {
          debugPrint('播放Windows系统提示音: $windowsAlertSound');
          await _audioPlayer.stop();
          await _audioPlayer.setVolume(1.0);
          await _audioPlayer.play(DeviceFileSource(windowsAlertSound));
          debugPrint('Windows系统提示音已播放');
          return;
        }

        // 如果系统声音文件不存在，尝试其他Windows声音
        final alternativeSounds = [
          r'C:\Windows\Media\Windows Ding.wav',
          r'C:\Windows\Media\Windows Error.wav',
          r'C:\Windows\Media\Windows Exclamation.wav',
          r'C:\Windows\Media\chord.wav',
          r'C:\Windows\Media\notify.wav',
        ];

        for (String soundPath in alternativeSounds) {
          final altSoundFile = File(soundPath);
          if (await altSoundFile.exists()) {
            debugPrint('播放Windows系统声音: $soundPath');
            await _audioPlayer.stop();
            await _audioPlayer.setVolume(1.0);
            await _audioPlayer.play(DeviceFileSource(soundPath));
            debugPrint('Windows系统声音已播放');
            return;
          }
        }

        // 如果没有找到系统声音文件，使用Flutter SystemSound作为最后的手段
        debugPrint('未找到Windows系统声音文件，使用Flutter SystemSound');
        await _playSystemSoundFallback();
      } else {
        // 非Windows平台，使用Flutter SystemSound
        await _playSystemSoundFallback();
      }
    } catch (e) {
      debugPrint('播放默认声音失败: $e');
      // 最后的回退：使用SystemSound
      await _playSystemSoundFallback();
    }

    debugPrint('默认报警声音处理完成');
  }

  /// 使用SystemSound作为回退方案
  Future<void> _playSystemSoundFallback() async {
    try {
      for (int i = 0; i < 3; i++) {
        await SystemSound.play(SystemSoundType.alert);
        if (i < 2) await Future.delayed(const Duration(milliseconds: 300));
      }
    } catch (e) {
      debugPrint('SystemSound回退也失败: $e');
    }
  }

  /// 停止播放报警声音
  Future<void> stopAlertSound() async {
    try {
      await _audioPlayer.stop();
      debugPrint('报警声音已停止');
    } catch (e) {
      debugPrint('停止声音失败: $e');
    }
  }

  /// 显示报警对话框
  void _showAlertDialog(
      String deviceName, List<String> exceededItems, String dialogHash) {
    if (Get.context != null) {
      // 标记对话框正在显示
      _isAlertDialogShowing = true;
      _currentAlertDialogHash = dialogHash;

      Get.dialog(
        AlertDialog(
          icon: const Icon(
            Icons.warning_amber_rounded,
            color: Colors.orange,
            size: 48,
          ),
          title: const Text(
            '⚠️ 设备异常报警',
            style: TextStyle(
              fontSize: 20,
              fontWeight: FontWeight.bold,
              color: Colors.red,
            ),
          ),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                '设备：$deviceName',
                style: const TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.w600,
                ),
              ),
              const SizedBox(height: 12),
              const Text(
                '异常项目：',
                style: TextStyle(
                  fontSize: 14,
                  fontWeight: FontWeight.w500,
                ),
              ),
              const SizedBox(height: 8),
              ...exceededItems.map((item) => Padding(
                    padding: const EdgeInsets.only(bottom: 4),
                    child: Text(
                      '• $item',
                      style: const TextStyle(fontSize: 14, color: Colors.red),
                    ),
                  )),
            ],
          ),
          actions: [
            TextButton(
              onPressed: () async {
                Get.back();
                // 停止播放报警声音
                await stopAlertSound();
                // 标记对话框已关闭
                _isAlertDialogShowing = false;
                _currentAlertDialogHash = null;
              },
              child: const Text('确定'),
            ),
            ElevatedButton(
              onPressed: () async {
                Get.back();
                // 停止播放报警声音
                await stopAlertSound();
                // 标记对话框已关闭
                _isAlertDialogShowing = false;
                _currentAlertDialogHash = null;
                // 可以跳转到设备详情页面
                Get.toNamed('/monitor');
              },
              style: ElevatedButton.styleFrom(
                backgroundColor: Colors.orange,
                foregroundColor: Colors.white,
              ),
              child: const Text('查看详情'),
            ),
          ],
        ),
        barrierDismissible: false, // 不允许点击外部关闭
      ).then((_) async {
        // 确保在对话框被意外关闭时也能重置状态和停止声音
        await stopAlertSound();
        _isAlertDialogShowing = false;
        _currentAlertDialogHash = null;
      });
    }
  }

  /// 电流单位转换
  double _convertCurrent(double value, String fromUnit, String toUnit) {
    if (fromUnit == toUnit) return value;

    // 先转换为基准单位 (A)
    double valueInAmps;
    switch (fromUnit) {
      case 'nA':
        valueInAmps = value * 1e-9;
        break;
      case 'uA':
        valueInAmps = value * 1e-6;
        break;
      case 'mA':
        valueInAmps = value * 1e-3;
        break;
      case 'A':
        valueInAmps = value;
        break;
      default:
        return value; // 未知单位，不转换
    }

    // 转换为目标单位
    switch (toUnit) {
      case 'nA':
        return valueInAmps * 1e9; // 使用乘法更清晰
      case 'uA':
        return valueInAmps * 1e6;
      case 'mA':
        return valueInAmps * 1e3;
      case 'A':
        return valueInAmps;
      default:
        return value; // 未知单位，不转换
    }
  }

  /// 电压单位转换
  double _convertVoltage(double value, String fromUnit, String toUnit) {
    if (fromUnit == toUnit) return value;

    // 先转换为基准单位 (V)
    double valueInVolts;
    switch (fromUnit) {
      case 'mV':
        valueInVolts = value / 1000.0;
        break;
      case 'V':
        valueInVolts = value;
        break;
      default:
        return value; // 未知单位，不转换
    }

    // 转换为目标单位
    switch (toUnit) {
      case 'mV':
        return valueInVolts * 1000.0;
      case 'V':
        return valueInVolts;
      default:
        return value; // 未知单位，不转换
    }
  }

  /// 功率单位转换
  double _convertPower(double value, String fromUnit, String toUnit) {
    if (fromUnit == toUnit) return value;

    // 先转换为基准单位 (W)
    double valueInWatts;
    switch (fromUnit) {
      case 'mW':
        valueInWatts = value / 1000.0;
        break;
      case 'W':
        valueInWatts = value;
        break;
      default:
        return value; // 未知单位，不转换
    }

    // 转换为目标单位
    switch (toUnit) {
      case 'mW':
        return valueInWatts * 1000.0;
      case 'W':
        return valueInWatts;
      default:
        return value; // 未知单位，不转换
    }
  }

  /// 耗电量单位转换
  double _convertPowerConsumption(
      double value, String fromUnit, String toUnit) {
    if (fromUnit == toUnit) return value;

    // 先转换为基准单位 (Ah)
    double valueInAh;
    switch (fromUnit) {
      case 'mAh':
        valueInAh = value / 1000.0;
        break;
      case 'Ah':
        valueInAh = value;
        break;
      default:
        return value; // 未知单位，不转换
    }

    // 转换为目标单位
    switch (toUnit) {
      case 'mAh':
        return valueInAh * 1000.0;
      case 'Ah':
        return valueInAh;
      default:
        return value; // 未知单位，不转换
    }
  }
}
