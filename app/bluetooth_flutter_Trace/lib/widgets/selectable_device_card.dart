import 'package:flutter/material.dart';
import 'package:flutter_blue_plus/flutter_blue_plus.dart';
import 'package:flutter_animate/flutter_animate.dart';
import '../controllers/ble_controller.dart';
import '../controllers/monitor_controller.dart';

class SelectableDeviceCard extends StatelessWidget {
  final BluetoothDevice device;
  final BleController bleController;
  final MonitorController monitorController;
  final bool isConnected;
  final bool isSelected;
  final VoidCallback onTap;
  final VoidCallback onSelect;
  final VoidCallback onConnect;

  const SelectableDeviceCard({
    Key? key,
    required this.device,
    required this.bleController,
    required this.monitorController,
    required this.isConnected,
    required this.isSelected,
    required this.onTap,
    required this.onSelect,
    required this.onConnect,
  }) : super(key: key);

  @override
  Widget build(BuildContext context) {
    final rssi = bleController.getDeviceRssi(device);
    final deviceName = bleController.getDeviceName(device);
    final deviceId = bleController.getDeviceId(device);
    final isConnectable = bleController.isConnectable(device);

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
          color: isSelected
              ? const Color(0xFF4A90E2)
              : isConnected
                  ? const Color(0xFF4A90E2).withValues(alpha: 0.3)
                  : Colors.transparent,
          width: isSelected ? 2.0 : 1.5,
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
                    // 选择框
                    GestureDetector(
                      onTap: onSelect,
                      child: Container(
                        padding: const EdgeInsets.all(4),
                        decoration: BoxDecoration(
                          color: isSelected
                              ? const Color(0xFF4A90E2)
                              : Colors.transparent,
                          shape: BoxShape.circle,
                          border: Border.all(
                            color: isSelected
                                ? const Color(0xFF4A90E2)
                                : Colors.grey.shade400,
                            width: 2,
                          ),
                        ),
                        child: Icon(
                          Icons.check,
                          color: isSelected ? Colors.white : Colors.transparent,
                          size: 16,
                        ),
                      ),
                    ),
                    const SizedBox(width: 12),

                    // 设备图标
                    Container(
                      padding: const EdgeInsets.all(12),
                      decoration: BoxDecoration(
                        color: isSelected
                            ? const Color(0xFF4A90E2).withValues(alpha: 0.2)
                            : isConnected
                                ? const Color(0xFF4A90E2).withValues(alpha: 0.1)
                                : Colors.grey.shade100,
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: Icon(
                        _getDeviceIcon(),
                        color: isSelected || isConnected
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
                                  style: TextStyle(
                                    fontSize: 16,
                                    fontWeight: FontWeight.w600,
                                    color: isSelected
                                        ? const Color(0xFF4A90E2)
                                        : const Color(0xFF2E3A59),
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
                          color: bleController.getRssiColor(rssi),
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
                            bleController.getRssiDescription(rssi),
                            bleController.getRssiColor(rssi),
                          ),
                          if (bleController.getServiceUuids(device).isNotEmpty)
                            _buildPropertyChip(
                              '${bleController.getServiceUuids(device).length}个服务',
                              const Color(0xFF4A90E2),
                            ),
                          // 显示0xFF厂商数据标识
                          if (_hasManufacturerData())
                            _buildPropertyChip('厂商数据', const Color(0xFFFF9800)),
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
    final deviceName = device.platformName.toLowerCase();

    if (deviceName.contains('phone') || deviceName.contains('iphone')) {
      return Icons.phone_android;
    } else if (deviceName.contains('watch') || deviceName.contains('band')) {
      return Icons.watch;
    } else if (deviceName.contains('headphone') ||
        deviceName.contains('earphone') ||
        deviceName.contains('airpods')) {
      return Icons.headphones;
    } else if (deviceName.contains('speaker')) {
      return Icons.speaker;
    } else if (deviceName.contains('keyboard')) {
      return Icons.keyboard;
    } else if (deviceName.contains('mouse')) {
      return Icons.mouse;
    } else if (deviceName.contains('tv')) {
      return Icons.tv;
    } else if (deviceName.contains('car')) {
      return Icons.directions_car;
    } else if (deviceName.contains('beacon')) {
      return Icons.location_on;
    } else if (_hasManufacturerData()) {
      return Icons.electrical_services; // 电量监控设备图标
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

  bool _hasManufacturerData() {
    final result = bleController.getScanResult(device);
    if (result != null) {
      final manufData = result.advertisementData.manufacturerData;
      // 检查是否有足够长度的厂商数据（至少5字节）
      return manufData.values.any((data) => data.length >= 5);
    }
    return false;
  }
}
