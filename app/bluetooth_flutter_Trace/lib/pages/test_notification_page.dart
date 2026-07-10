import 'package:flutter/material.dart';
import 'package:get/get.dart';
import '../services/notification_service.dart';
import '../services/alert_service.dart';
import '../models/device_settings.dart';
import '../models/device_data.dart';

class TestNotificationPage extends StatelessWidget {
  const TestNotificationPage({super.key});

  /// 测试前台报警
  void _testForegroundAlert() {
    // 模拟设备数据来触发报警
    final mockData = DeviceData(
      deviceId: 'test_device',
      deviceName: '测试设备',
      timestamp: DateTime.now(),
      current: 100.0,
      currentUnit: 'mA',
      voltage: 5000.0,
      power: 500.0,
      dataType: BleDataType.scanResponse,
    );

    // 调用报警服务的公开方法
    AlertService.to.checkThresholds(mockData, 1000.0);
  }

  /// 测试后台通知
  void _testBackgroundNotification() {
    // 获取通知服务实例
    final notificationService = Get.find<NotificationService>();

    // 显示后台通知
    notificationService.showDeviceAlertNotification(
      deviceName: '测试设备',
      exceededItems: ['后台测试电流超阈值', '后台测试电压超阈值'],
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('测试后台通知'),
      ),
      body: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Text(
              '后台通知功能测试',
              style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 20),
            const Text(
              '这个页面用于测试应用在后台时是否能正常显示通知',
              textAlign: TextAlign.center,
              style: TextStyle(fontSize: 16),
            ),
            const SizedBox(height: 40),
            ElevatedButton(
              onPressed: () {
                // 测试前台通知（应该能正常显示）
                _testForegroundAlert();
              },
              child: const Text('测试前台通知'),
            ),
            const SizedBox(height: 20),
            ElevatedButton(
              onPressed: () {
                // 测试后台通知
                _testBackgroundNotification();
              },
              child: const Text('测试后台通知'),
            ),
            const SizedBox(height: 20),
            ElevatedButton(
              onPressed: () {
                // 返回上一页
                Get.back();
              },
              child: const Text('返回'),
            ),
          ],
        ),
      ),
    );
  }
}
