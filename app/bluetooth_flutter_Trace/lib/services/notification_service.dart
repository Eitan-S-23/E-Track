import 'dart:io';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:flutter/material.dart';
import 'package:flutter/foundation.dart' show kIsWeb, visibleForTesting;
import 'package:local_notifier/local_notifier.dart';

class NotificationService {
  static final NotificationService _instance = NotificationService._internal();
  factory NotificationService() => _instance;

  NotificationService._internal();

  @visibleForTesting
  NotificationService.forTesting();

  final FlutterLocalNotificationsPlugin _flutterLocalNotificationsPlugin =
      FlutterLocalNotificationsPlugin();

  FlutterLocalNotificationsPlugin get flutterLocalNotificationsPlugin =>
      _flutterLocalNotificationsPlugin;

  // 震动模式常量
  static List<int> get vibrationPattern => [0, 300, 200, 400, 200, 500];

  bool _isInitialized = false;
  Future<void>? _initializing;
  Future<bool?>? _permissionRequest;
  bool? _permissionGranted;

  /// 初始化通知服务
  Future<void> initialize() {
    if (_isInitialized) return Future.value();
    final pending = _initializing;
    if (pending != null) return pending;
    late final Future<void> future;
    future = _initialize().whenComplete(() {
      if (identical(_initializing, future)) _initializing = null;
    });
    _initializing = future;
    return future;
  }

  Future<void> _initialize() async {

    const AndroidInitializationSettings initializationSettingsAndroid =
        AndroidInitializationSettings('@mipmap/ic_launcher');

    const DarwinInitializationSettings initializationSettingsIOS =
        DarwinInitializationSettings(
      requestAlertPermission: true,
      requestBadgePermission: true,
      requestSoundPermission: true,
    );

    const InitializationSettings initializationSettings =
        InitializationSettings(
      android: initializationSettingsAndroid,
      iOS: initializationSettingsIOS,
      linux: LinuxInitializationSettings(defaultActionName: 'Open notification'),
    );

    await _flutterLocalNotificationsPlugin.initialize(
      initializationSettings,
      onDidReceiveNotificationResponse: (NotificationResponse response) {
        // 处理通知点击事件
        _handleNotificationTap(response);
      },
    );

    // 请求权限
    await _requestPermissions();

    _isInitialized = true;
  }

  /// 请求通知权限
  Future<bool?> requestNotificationPermission() async {
    if (!_isInitialized) {
      await initialize();
      return _permissionGranted;
    }
    return _requestPermissions();
  }

  Future<bool?> _requestPermissions() {
    final pending = _permissionRequest;
    if (pending != null) return pending;
    late final Future<bool?> future;
    future = _requestPermissionsImpl().then((granted) {
      _permissionGranted = granted;
      return granted;
    }).whenComplete(() {
      if (identical(_permissionRequest, future)) _permissionRequest = null;
    });
    _permissionRequest = future;
    return future;
  }

  Future<bool?> _requestPermissionsImpl() async {
    if (kIsWeb) return true;

    // Android 13+ 需要特殊的权限处理
    final AndroidFlutterLocalNotificationsPlugin? androidImplementation =
        _flutterLocalNotificationsPlugin
            .resolvePlatformSpecificImplementation<
                AndroidFlutterLocalNotificationsPlugin>();

    if (androidImplementation != null) {
      return androidImplementation.requestNotificationsPermission();
    }
    return true;
  }

  /// 显示报警通知
  Future<void> showAlertNotification({
    required String title,
    required String body,
    String? deviceName,
    List<String>? exceededItems,
  }) async {
    // Windows平台使用local_notifier
    if (Platform.isWindows) {
      await _showWindowsNotification(
        title: title,
        body: body,
        deviceName: deviceName,
        exceededItems: exceededItems,
      );
      return;
    }

    // 其他平台使用flutter_local_notifications
    if (!_isInitialized) {
      await initialize();
    }

    const AndroidNotificationDetails androidNotificationDetails =
        AndroidNotificationDetails(
      'alert_channel',
      '设备报警',
      channelDescription: '功率计设备异常报警通知',
      importance: Importance.max,
      priority: Priority.high,
      showWhen: true,
      playSound: true,
      enableVibration: true,
      styleInformation: BigTextStyleInformation(''),
      fullScreenIntent: true, // 全屏显示
      category: AndroidNotificationCategory.alarm,
    );

    const DarwinNotificationDetails iOSNotificationDetails =
        DarwinNotificationDetails(
      presentAlert: true,
      presentBadge: true,
      presentSound: true,
      interruptionLevel: InterruptionLevel.critical,
    );

    const NotificationDetails notificationDetails = NotificationDetails(
      android: androidNotificationDetails,
      iOS: iOSNotificationDetails,
    );

    // 构建通知内容
    String notificationBody = body;
    if (exceededItems != null && exceededItems.isNotEmpty) {
      notificationBody += '\n\n异常项目:';
      for (var item in exceededItems) {
        notificationBody += '\n• $item';
      }
    }

    await _flutterLocalNotificationsPlugin.show(
      DateTime.now().millisecondsSinceEpoch ~/ 1000, // 唯一ID
      title,
      notificationBody,
      notificationDetails,
    );
  }

  /// 显示Windows平台的通知
  Future<void> _showWindowsNotification({
    required String title,
    required String body,
    String? deviceName,
    List<String>? exceededItems,
  }) async {
    try {
      // 初始化本地通知
      await localNotifier.setup(
        appName: 'BLE Monitor',
        shortcutPolicy: ShortcutPolicy.requireCreate,
      );

      // 构建通知内容
      String notificationBody = body;
      if (exceededItems != null && exceededItems.isNotEmpty) {
        notificationBody += '\n\n异常项目:';
        for (var item in exceededItems) {
          notificationBody += '\n• $item';
        }
      }

      // 创建通知
      final LocalNotification notification = LocalNotification(
        identifier: '${DateTime.now().millisecondsSinceEpoch}',
        title: title,
        body: notificationBody,
        actions: [
          LocalNotificationAction(
            text: '查看详情',
          ),
          LocalNotificationAction(
            text: '忽略',
          ),
        ],
      );

      // 监听通知点击事件
      notification.onShow = () {
        debugPrint('Windows通知已显示');
      };

      notification.onClick = () {
        debugPrint('Windows通知被点击');
        // 可以在这里添加跳转逻辑
      };

      notification.onClickAction = (actionIndex) {
        debugPrint('Windows通知动作被点击: $actionIndex');
        if (actionIndex == 0) {
          // "查看详情"被点击
          debugPrint('用户选择查看详情');
        } else if (actionIndex == 1) {
          // "忽略"被点击
          debugPrint('用户选择忽略');
        }
      };

      notification.onClose = (closeReason) {
        debugPrint('Windows通知被关闭: $closeReason');
      };

      // 显示通知
      await notification.show();

      debugPrint('Windows本地通知已发送: $title');
    } catch (e) {
      debugPrint('Windows通知发送失败: $e');
      // 如果local_notifier失败，尝试使用flutter_local_notifications作为备选
      try {
        if (!_isInitialized) {
          await initialize();
        }

        await _flutterLocalNotificationsPlugin.show(
          DateTime.now().millisecondsSinceEpoch ~/ 1000,
          title,
          body,
          const NotificationDetails(),
        );
      } catch (e2) {
        debugPrint('备选通知方案也失败: $e2');
      }
    }
  }

  /// 显示设备异常通知（后台专用）
  Future<void> showDeviceAlertNotification({
    required String deviceName,
    required List<String> exceededItems,
  }) async {
    const title = '⚠️ 设备异常报警';
    final body = '设备 $deviceName 检测到异常用电情况';

    await showAlertNotification(
      title: title,
      body: body,
      deviceName: deviceName,
      exceededItems: exceededItems,
    );
  }

  /// 处理通知点击事件
  void _handleNotificationTap(NotificationResponse response) {
    // 可以在这里添加点击通知后的逻辑，比如跳转到特定页面
    debugPrint('通知被点击: ${response.payload}');
  }

  /// 取消所有通知
  Future<void> cancelAllNotifications() async {
    await _flutterLocalNotificationsPlugin.cancelAll();
  }

  /// 取消特定通知
  Future<void> cancelNotification(int id) async {
    await _flutterLocalNotificationsPlugin.cancel(id);
  }
}
