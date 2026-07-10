import 'package:flutter/material.dart';
import 'package:get/get.dart';
import 'dart:io';
import 'package:sqflite_common_ffi/sqflite_ffi.dart';
import 'controllers/ble_controller.dart';
import 'controllers/monitor_controller.dart';
import 'pages/main_app_page.dart';
import 'pages/home_page.dart';
import 'pages/monitor_page.dart';
import 'pages/saved_devices_page.dart';
import 'pages/speedometer_page.dart';
import 'pages/test_notification_page.dart';
import 'services/database_service.dart';
import 'services/scan_settings_service.dart';
import 'services/alert_service.dart';
import 'services/app_update_service.dart';
import 'services/background_optimization_service.dart';
import 'services/deep_link_service.dart';
import 'services/ota_service.dart';
import 'services/bluetooth_service.dart' as bt_service;
import 'services/responsive_service.dart';
import 'services/notification_service.dart';
import 'services/background_task_service.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();

  // Windows/Linux/macOS平台数据库初始化
  if (Platform.isWindows || Platform.isLinux || Platform.isMacOS) {
    sqfliteFfiInit();
    databaseFactory = databaseFactoryFfi;
  }

  try {
    // 初始化数据库
    await DatabaseService().database;
  } catch (e) {
    debugPrint('Database initialization error: $e');
  }

  runApp(const MyApp());
}

class MyApp extends StatelessWidget {
  const MyApp({Key? key}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    // 初始化响应式服务的屏幕信息
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (Get.isRegistered<ResponsiveService>()) {
        Get.find<ResponsiveService>()
            .updateScreenInfo(MediaQuery.of(context).size);
      }
    });
    return LayoutBuilder(
      builder: (context, constraints) {
        // 实时更新屏幕尺寸
        if (Get.isRegistered<ResponsiveService>()) {
          Get.find<ResponsiveService>().updateScreenInfo(
              Size(constraints.maxWidth, constraints.maxHeight));
        }

        return GetMaterialApp(
          title: 'BLE 广播接收器',
          theme: ThemeData(
            primarySwatch: Colors.blue,
            fontFamily: 'Roboto',
            useMaterial3: true,
            colorScheme: ColorScheme.fromSeed(
              seedColor: const Color(0xFF4A90E2),
              brightness: Brightness.light,
            ),
            appBarTheme: const AppBarTheme(
              backgroundColor: Colors.white,
              foregroundColor: Color(0xFF2E3A59),
              elevation: 0,
              centerTitle: false,
            ),
            elevatedButtonTheme: ElevatedButtonThemeData(
              style: ElevatedButton.styleFrom(
                elevation: 0,
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(12),
                ),
              ),
            ),
            cardTheme: const CardThemeData(
              elevation: 0,
            ),
          ),
          home: const MainAppPage(),
          initialBinding: BindingsBuilder(() {
            // 按依赖顺序注册服务
            Get.put(ResponsiveService(), permanent: true); // 首先注册响应式服务
            Get.put(ScanSettingsService(), permanent: true);
            Get.put(AlertService(), permanent: true);
            Get.put(OtaService(), permanent: true);
            Get.put(AppUpdateService(), permanent: true);
            Get.put(bt_service.BluetoothService(),
                permanent: true); // 注册跨平台蓝牙服务
            Get.put(BleController(), permanent: true);
            Get.put(MonitorController(), permanent: true);
            Get.put(BackgroundOptimizationService(), permanent: true);

            // 初始化通知服务
            Get.put(NotificationService(), permanent: true);
            Get.put(BackgroundTaskService(), permanent: true);
            Get.put(DeepLinkService(), permanent: true);

            WidgetsBinding.instance.addPostFrameCallback((_) {
              Get.find<NotificationService>().initialize();
              Get.find<AppUpdateService>().checkDailyOnStartup();
            });
          }),
          getPages: [
            GetPage(name: '/main', page: () => const MainAppPage()),
            GetPage(name: '/', page: () => const HomePage()),
            GetPage(name: '/monitor', page: () => const MonitorPage()),
            GetPage(
                name: '/saved-devices', page: () => const SavedDevicesPage()),
            GetPage(
                name: '/test-notification',
                page: () => const TestNotificationPage()),
            GetPage(
                name: '/speedometer', page: () => const SpeedometerPage()),
          ],
          debugShowCheckedModeBanner: false,
        );
      },
    );
  }
}
