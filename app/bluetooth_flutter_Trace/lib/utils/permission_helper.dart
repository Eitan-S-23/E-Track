import 'dart:io';
import 'package:flutter/material.dart';
import 'package:get/get.dart';
import 'package:permission_handler/permission_handler.dart';

class PermissionHelper {
  /// 请求所有必要的蓝牙权限
  static Future<bool> requestBluetoothPermissions() async {
    try {
      List<Permission> permissions = [];

      if (Platform.isAndroid) {
        // Android 权限
        permissions.addAll([
          Permission.bluetooth,
          Permission.bluetoothScan,
          Permission.bluetoothConnect,
          Permission.location,
        ]);
      } else if (Platform.isIOS) {
        // iOS 权限
        permissions.addAll([
          Permission.bluetooth,
        ]);
      }

      Map<Permission, PermissionStatus> statuses = await permissions.request();

      // 检查是否所有权限都被授予
      bool allGranted = true;
      List<String> deniedPermissions = [];

      for (var entry in statuses.entries) {
        if (!entry.value.isGranted) {
          allGranted = false;
          deniedPermissions.add(_getPermissionName(entry.key));
        }
      }

      if (!allGranted) {
        _showPermissionDialog(deniedPermissions);
        return false;
      }

      return true;
    } catch (e) {
      debugPrint('请求权限时发生错误: $e');
      Get.snackbar(
        '权限错误',
        '请求权限时发生错误: $e',
        snackPosition: SnackPosition.BOTTOM,
        backgroundColor: Colors.red,
        colorText: Colors.white,
      );
      return false;
    }
  }

  /// 检查权限状态
  static Future<bool> checkBluetoothPermissions() async {
    try {
      List<Permission> permissions = [];

      if (Platform.isAndroid) {
        permissions.addAll([
          Permission.bluetooth,
          Permission.bluetoothScan,
          Permission.bluetoothConnect,
          Permission.location,
        ]);
      } else if (Platform.isIOS) {
        permissions.addAll([
          Permission.bluetooth,
        ]);
      }

      for (Permission permission in permissions) {
        PermissionStatus status = await permission.status;
        if (!status.isGranted) {
          return false;
        }
      }

      return true;
    } catch (e) {
      debugPrint('检查权限时发生错误: $e');
      return false;
    }
  }

  /// 显示权限说明对话框
  static void _showPermissionDialog(List<String> deniedPermissions) {
    Get.dialog(
      AlertDialog(
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(16),
        ),
        title: Row(
          children: [
            Icon(
              Icons.security,
              color: Colors.orange.shade600,
              size: 24,
            ),
            const SizedBox(width: 12),
            const Text(
              '权限需要',
              style: TextStyle(
                fontSize: 18,
                fontWeight: FontWeight.w600,
              ),
            ),
          ],
        ),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              '为了正常使用蓝牙功能，应用需要以下权限：',
              style: TextStyle(fontSize: 14),
            ),
            const SizedBox(height: 12),
            ...deniedPermissions.map((permission) => Padding(
                  padding: const EdgeInsets.only(bottom: 4),
                  child: Row(
                    children: [
                      Icon(
                        Icons.circle,
                        size: 6,
                        color: Colors.grey.shade600,
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text(
                          permission,
                          style: const TextStyle(fontSize: 14),
                        ),
                      ),
                    ],
                  ),
                )),
            const SizedBox(height: 12),
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: Colors.blue.shade50,
                borderRadius: BorderRadius.circular(8),
                border: Border.all(color: Colors.blue.shade200),
              ),
              child: Row(
                children: [
                  Icon(
                    Icons.info_outline,
                    color: Colors.blue.shade600,
                    size: 16,
                  ),
                  const SizedBox(width: 8),
                  const Expanded(
                    child: Text(
                      '您可以稍后在设置中手动授予这些权限',
                      style: TextStyle(
                        fontSize: 12,
                        fontWeight: FontWeight.w500,
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Get.back(),
            child: Text(
              '稍后',
              style: TextStyle(
                color: Colors.grey.shade600,
                fontWeight: FontWeight.w500,
              ),
            ),
          ),
          ElevatedButton(
            onPressed: () {
              Get.back();
              openAppSettings();
            },
            style: ElevatedButton.styleFrom(
              backgroundColor: const Color(0xFF4A90E2),
              foregroundColor: Colors.white,
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(8),
              ),
            ),
            child: const Text(
              '去设置',
              style: TextStyle(fontWeight: FontWeight.w600),
            ),
          ),
        ],
      ),
      barrierDismissible: false,
    );
  }

  /// 显示蓝牙权限教育对话框
  static void showBluetoothPermissionEducation() {
    Get.dialog(
      AlertDialog(
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(16),
        ),
        title: Row(
          children: [
            Container(
              padding: const EdgeInsets.all(8),
              decoration: BoxDecoration(
                color: const Color(0xFF4A90E2).withOpacity(0.1),
                borderRadius: BorderRadius.circular(8),
              ),
              child: const Icon(
                Icons.bluetooth,
                color: Color(0xFF4A90E2),
                size: 20,
              ),
            ),
            const SizedBox(width: 12),
            const Text(
              '蓝牙权限说明',
              style: TextStyle(
                fontSize: 18,
                fontWeight: FontWeight.w600,
              ),
            ),
          ],
        ),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              '此应用需要蓝牙权限来：',
              style: TextStyle(
                fontSize: 14,
                fontWeight: FontWeight.w500,
              ),
            ),
            const SizedBox(height: 12),
            _buildPermissionItem(
              Icons.search,
              '扫描附近的蓝牙设备',
              '发现可连接的BLE设备',
            ),
            _buildPermissionItem(
              Icons.link,
              '连接到蓝牙设备',
              '与选定的设备建立连接',
            ),
            _buildPermissionItem(
              Icons.radio,
              '接收广播数据',
              '获取设备发送的广告信息',
            ),
            _buildPermissionItem(
              Icons.location_on,
              '访问位置信息',
              '在Android上蓝牙扫描需要位置权限',
            ),
            const SizedBox(height: 16),
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: Colors.green.shade50,
                borderRadius: BorderRadius.circular(8),
                border: Border.all(color: Colors.green.shade200),
              ),
              child: Row(
                children: [
                  Icon(
                    Icons.verified_user,
                    color: Colors.green.shade600,
                    size: 16,
                  ),
                  const SizedBox(width: 8),
                  const Expanded(
                    child: Text(
                      '我们不会收集或存储您的个人数据',
                      style: TextStyle(
                        fontSize: 12,
                        fontWeight: FontWeight.w500,
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Get.back(),
            child: Text(
              '取消',
              style: TextStyle(
                color: Colors.grey.shade600,
                fontWeight: FontWeight.w500,
              ),
            ),
          ),
          ElevatedButton(
            onPressed: () {
              Get.back();
              requestBluetoothPermissions();
            },
            style: ElevatedButton.styleFrom(
              backgroundColor: const Color(0xFF4A90E2),
              foregroundColor: Colors.white,
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(8),
              ),
            ),
            child: const Text(
              '授予权限',
              style: TextStyle(fontWeight: FontWeight.w600),
            ),
          ),
        ],
      ),
    );
  }

  static Widget _buildPermissionItem(
      IconData icon, String title, String description) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            padding: const EdgeInsets.all(6),
            decoration: BoxDecoration(
              color: const Color(0xFF4A90E2).withOpacity(0.1),
              borderRadius: BorderRadius.circular(6),
            ),
            child: Icon(
              icon,
              size: 16,
              color: const Color(0xFF4A90E2),
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: const TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.w600,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  description,
                  style: TextStyle(
                    fontSize: 12,
                    color: Colors.grey.shade600,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  /// 获取权限的友好名称
  static String _getPermissionName(Permission permission) {
    switch (permission) {
      case Permission.bluetooth:
        return '蓝牙权限';
      case Permission.bluetoothScan:
        return '蓝牙扫描权限';
      case Permission.bluetoothConnect:
        return '蓝牙连接权限';
      case Permission.location:
        return '位置权限';
      case Permission.locationWhenInUse:
        return '使用时位置权限';
      case Permission.locationAlways:
        return '始终位置权限';
      default:
        return permission.toString();
    }
  }

  /// 显示蓝牙未开启的对话框
  static void showBluetoothDisabledDialog() {
    Get.dialog(
      AlertDialog(
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(16),
        ),
        title: Row(
          children: [
            Icon(
              Icons.bluetooth_disabled,
              color: Colors.orange.shade600,
              size: 24,
            ),
            const SizedBox(width: 12),
            const Text(
              '蓝牙未开启',
              style: TextStyle(
                fontSize: 18,
                fontWeight: FontWeight.w600,
              ),
            ),
          ],
        ),
        content: const Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              '请开启蓝牙以使用此功能',
              style: TextStyle(fontSize: 14),
            ),
            SizedBox(height: 12),
            Text(
              '您可以：',
              style: TextStyle(
                fontSize: 14,
                fontWeight: FontWeight.w500,
              ),
            ),
            SizedBox(height: 8),
            Text(
              '• 点击"开启蓝牙"按钮\n• 或在设置中手动开启蓝牙',
              style: TextStyle(fontSize: 14),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Get.back(),
            child: Text(
              '稍后',
              style: TextStyle(
                color: Colors.grey.shade600,
                fontWeight: FontWeight.w500,
              ),
            ),
          ),
          ElevatedButton(
            onPressed: () {
              Get.back();
              // 这里可以添加开启蓝牙的逻辑
            },
            style: ElevatedButton.styleFrom(
              backgroundColor: const Color(0xFF4A90E2),
              foregroundColor: Colors.white,
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(8),
              ),
            ),
            child: const Text(
              '开启蓝牙',
              style: TextStyle(fontWeight: FontWeight.w600),
            ),
          ),
        ],
      ),
    );
  }
}
