import 'package:flutter/material.dart';
import 'package:flutter_blue_plus/flutter_blue_plus.dart';
import 'package:flutter_animate/flutter_animate.dart';
import '../controllers/ble_controller.dart';

class DeviceCard extends StatelessWidget {
  final BluetoothDevice device;
  final BleController controller;
  final bool isConnected;
  final VoidCallback onTap;
  final VoidCallback onConnect;

  const DeviceCard({
    Key? key,
    required this.device,
    required this.controller,
    required this.isConnected,
    required this.onTap,
    required this.onConnect,
  }) : super(key: key);

  @override
  Widget build(BuildContext context) {
    final rssi = controller.getDeviceRssi(device);
    final deviceName = controller.getDeviceName(device);
    final deviceId = controller.getDeviceId(device);
    final isConnectable = controller.isConnectable(device);

    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.05),
            blurRadius: 10,
            offset: const Offset(0, 2),
          ),
        ],
        border: Border.all(
          color: isConnected
              ? const Color(0xFF4A90E2).withValues(alpha: 0.3)
              : Colors.transparent,
          width: 1.5,
        ),
      ),
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: onTap,
          borderRadius: BorderRadius.circular(16),
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              children: [
                Row(
                  children: [
                    // 设备图标
                    Container(
                      padding: const EdgeInsets.all(12),
                      decoration: BoxDecoration(
                        color: isConnected
                            ? const Color(0xFF4A90E2).withValues(alpha: 0.1)
                            : Colors.grey.shade100,
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: Icon(
                        _getDeviceIcon(),
                        color: isConnected
                            ? const Color(0xFF4A90E2)
                            : Colors.grey.shade600,
                        size: 24,
                      ),
                    ),
                    const SizedBox(width: 16),
                    // 设备信息
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(
                            children: [
                              Expanded(
                                child: Text(
                                  deviceName,
                                  style: const TextStyle(
                                    fontSize: 16,
                                    fontWeight: FontWeight.w600,
                                    color: Color(0xFF2E3A59),
                                  ),
                                  overflow: TextOverflow.ellipsis,
                                ),
                              ),
                              if (isConnected)
                                Container(
                                  padding: const EdgeInsets.symmetric(
                                    horizontal: 8,
                                    vertical: 4,
                                  ),
                                  decoration: BoxDecoration(
                                    color: const Color(0xFF4CAF50),
                                    borderRadius: BorderRadius.circular(12),
                                  ),
                                  child: const Text(
                                    '已连接',
                                    style: TextStyle(
                                      color: Colors.white,
                                      fontSize: 10,
                                      fontWeight: FontWeight.w600,
                                    ),
                                  ),
                                ),
                            ],
                          ),
                          const SizedBox(height: 4),
                          Text(
                            deviceId,
                            style: TextStyle(
                              fontSize: 12,
                              color: Colors.grey.shade600,
                              fontFamily: 'monospace',
                            ),
                          ),
                        ],
                      ),
                    ),
                    // 信号强度
                    Column(
                      children: [
                        Icon(
                          _getSignalIcon(rssi),
                          color: controller.getRssiColor(rssi),
                          size: 20,
                        ),
                        const SizedBox(height: 2),
                        Text(
                          '${rssi}dBm',
                          style: TextStyle(
                            fontSize: 10,
                            color: Colors.grey.shade600,
                            fontWeight: FontWeight.w500,
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
                const SizedBox(height: 16),
                Row(
                  children: [
                    // 设备属性标签
                    Expanded(
                      child: Wrap(
                        spacing: 8,
                        children: [
                          if (isConnectable)
                            _buildPropertyChip('可连接', Colors.green),
                          _buildPropertyChip(
                            controller.getRssiDescription(rssi),
                            controller.getRssiColor(rssi),
                          ),
                          if (controller.getServiceUuids(device).isNotEmpty)
                            _buildPropertyChip(
                              '${controller.getServiceUuids(device).length}个服务',
                              const Color(0xFF4A90E2),
                            ),
                        ],
                      ),
                    ),
                    // 连接按钮
                    if (isConnectable)
                      SizedBox(
                        height: 36,
                        child: ElevatedButton(
                          onPressed: onConnect,
                          style: ElevatedButton.styleFrom(
                            backgroundColor: isConnected
                                ? const Color(0xFFFF6B6B)
                                : const Color(0xFF4A90E2),
                            foregroundColor: Colors.white,
                            elevation: 0,
                            shape: RoundedRectangleBorder(
                              borderRadius: BorderRadius.circular(18),
                            ),
                            padding: const EdgeInsets.symmetric(horizontal: 16),
                          ),
                          child: Text(
                            isConnected ? '断开' : '连接',
                            style: const TextStyle(
                              fontSize: 12,
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                        ),
                      ),
                  ],
                ),
              ],
            ),
          ),
        ),
      ),
    ).animate().fadeIn(duration: 300.ms).slideX(begin: 0.1, end: 0);
  }

  Widget _buildPropertyChip(String label, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: color.withValues(alpha: 0.3),
          width: 1,
        ),
      ),
      child: Text(
        label,
        style: TextStyle(
          color: color,
          fontSize: 11,
          fontWeight: FontWeight.w600,
        ),
      ),
    );
  }

  IconData _getDeviceIcon() {
    // 通过扫描结果获取设备名称用于图标判断
    final scanResult = controller.getScanResult(device);
    final advName = scanResult?.advertisementData.advName;
    final deviceName =
        advName != null && advName.isNotEmpty ? advName : device.platformName;
    final name = deviceName.toLowerCase();

    if (name.contains('phone') || name.contains('iphone')) {
      return Icons.phone_android;
    } else if (name.contains('watch') || name.contains('band')) {
      return Icons.watch;
    } else if (name.contains('headphone') ||
        name.contains('earphone') ||
        name.contains('airpods')) {
      return Icons.headphones;
    } else if (name.contains('speaker')) {
      return Icons.speaker;
    } else if (name.contains('keyboard')) {
      return Icons.keyboard;
    } else if (name.contains('mouse')) {
      return Icons.mouse;
    } else if (name.contains('tv')) {
      return Icons.tv;
    } else if (name.contains('car')) {
      return Icons.directions_car;
    } else if (name.contains('beacon')) {
      return Icons.location_on;
    } else {
      return Icons.bluetooth;
    }
  }

  IconData _getSignalIcon(int rssi) {
    if (rssi >= -50) {
      return Icons.signal_wifi_4_bar;
    } else if (rssi >= -60) {
      return Icons.signal_wifi_4_bar;
    } else if (rssi >= -70) {
      return Icons.signal_cellular_alt_2_bar;
    } else if (rssi >= -80) {
      return Icons.signal_cellular_alt_1_bar;
    } else {
      return Icons.signal_cellular_alt;
    }
  }
}
