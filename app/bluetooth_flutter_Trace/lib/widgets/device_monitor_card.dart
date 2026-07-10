import 'package:flutter/material.dart';
import 'package:get/get.dart';
import '../models/device_data.dart';
import '../controllers/monitor_controller.dart';

class DeviceMonitorCard extends StatelessWidget {
  final SelectedDevice device;
  final DeviceData? latestData;
  final double powerConsumption;
  final VoidCallback onTap;

  const DeviceMonitorCard({
    Key? key,
    required this.device,
    this.latestData,
    this.powerConsumption = 0.0,
    required this.onTap,
  }) : super(key: key);

  @override
  Widget build(BuildContext context) {
    final monitorController = Get.find<MonitorController>();

    return Obx(() {
      // Get real-time data from the controller
      final realtimeData =
          latestData ?? monitorController.getLatestData(device.deviceId);
      final currentPowerConsumption = powerConsumption > 0
          ? powerConsumption
          : monitorController.getDevicePowerConsumption(device.deviceId);
      final hasFormatError =
          !monitorController.isDeviceFormatValid(device.deviceId);
      final formatError =
          monitorController.getDeviceFormatError(device.deviceId);

      return Container(
        margin: const EdgeInsets.only(bottom: 16),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(16),
          border: hasFormatError
              ? Border.all(
                  color: Colors.red.shade300,
                  width: 2,
                )
              : null,
          boxShadow: [
            BoxShadow(
              color: Colors.black.withOpacity(0.08),
              blurRadius: 12,
              offset: const Offset(0, 4),
            ),
          ],
        ),
        child: Material(
          color: Colors.transparent,
          child: InkWell(
            onTap: onTap,
            borderRadius: BorderRadius.circular(16),
            child: Padding(
              padding: const EdgeInsets.all(20),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // 设备标题和状态
                  _buildDeviceHeader(hasFormatError, formatError),
                  const SizedBox(height: 16),

                  // 实时数据显示
                  if (realtimeData != null) ...[
                    _buildDataDisplay(realtimeData),
                    const SizedBox(height: 16),
                    _buildPowerConsumption(
                        realtimeData, currentPowerConsumption),
                  ] else
                    _buildNoDataState(),

                  const SizedBox(height: 12),

                  // 操作按钮
                  _buildActionButton(),
                ],
              ),
            ),
          ),
        ),
      );
    });
  }

  Widget _buildDeviceHeader(bool hasFormatError, String formatError) {
    return Row(
      children: [
        Container(
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(
            color: hasFormatError
                ? Colors.red.withValues(alpha: 0.1)
                : const Color(0xFF4A90E2).withValues(alpha: 0.1),
            borderRadius: BorderRadius.circular(12),
          ),
          child: Icon(
            hasFormatError ? Icons.warning : _getDeviceIcon(),
            color: hasFormatError ? Colors.red : const Color(0xFF4A90E2),
            size: 24,
          ),
        ),
        const SizedBox(width: 16),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Expanded(
                    child: Text(
                      device.deviceName,
                      style: const TextStyle(
                        fontSize: 18,
                        fontWeight: FontWeight.w600,
                        color: Color(0xFF2E3A59),
                      ),
                    ),
                  ),
                  if (hasFormatError)
                    Container(
                      padding: const EdgeInsets.symmetric(
                          horizontal: 6, vertical: 2),
                      decoration: BoxDecoration(
                        color: Colors.red.shade100,
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: Text(
                        '格式错误',
                        style: TextStyle(
                          fontSize: 10,
                          fontWeight: FontWeight.w600,
                          color: Colors.red.shade700,
                        ),
                      ),
                    ),
                ],
              ),
              if (hasFormatError) ...[
                const SizedBox(height: 6),
                Container(
                  padding: const EdgeInsets.all(8),
                  decoration: BoxDecoration(
                    color: Colors.red.shade50,
                    borderRadius: BorderRadius.circular(6),
                    border: Border.all(color: Colors.red.shade200),
                  ),
                  child: Row(
                    children: [
                      Icon(
                        Icons.error_outline,
                        size: 14,
                        color: Colors.red.shade600,
                      ),
                      const SizedBox(width: 6),
                      Expanded(
                        child: Text(
                          formatError,
                          style: TextStyle(
                            fontSize: 11,
                            color: Colors.red.shade700,
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              ],
              const SizedBox(height: 4),
              Text(
                device.deviceId,
                style: TextStyle(
                  fontSize: 12,
                  color: Colors.grey.shade600,
                  fontFamily: 'monospace',
                ),
              ),
            ],
          ),
        ),
        // 计算监控状态，无需嵌套Obx
        (() {
          final controller = Get.find<MonitorController>();
          final currentRealtimeData = controller.getLatestData(device.deviceId);
          // Check if device is actively receiving data (regardless of saved status)
          final isReceivingData = currentRealtimeData != null &&
              DateTime.now()
                      .difference(currentRealtimeData.timestamp)
                      .inSeconds <
                  30;
          final isMonitoring = controller.isMonitoring.value &&
              (device.isMonitoring.value || isReceivingData);

          return Container(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
            decoration: BoxDecoration(
              color: isMonitoring ? const Color(0xFF4CAF50) : Colors.orange,
              borderRadius: BorderRadius.circular(12),
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(
                  isMonitoring ? Icons.monitor : Icons.pause,
                  color: Colors.white,
                  size: 12,
                ),
                const SizedBox(width: 4),
                Text(
                  isMonitoring ? '监控中' : '已暂停',
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 10,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ],
            ),
          );
        })(),
      ],
    );
  }

  Widget _buildDataDisplay(DeviceData data) {
    return Row(
      children: [
        Expanded(
          child: _buildDataItem(
            '电流',
            '${data.current.toStringAsFixed(1)}${data.currentUnit}',
            Icons.flash_on,
            const Color(0xFFFF9800),
          ),
        ),
        Container(
          width: 1,
          height: 40,
          color: Colors.grey.shade200,
        ),
        Expanded(
          child: _buildDataItem(
            '电压',
            '${data.voltage.toStringAsFixed(1)}mV',
            Icons.battery_charging_full,
            const Color(0xFF4CAF50),
          ),
        ),
        Container(
          width: 1,
          height: 40,
          color: Colors.grey.shade200,
        ),
        Expanded(
          child: _buildDataItem(
            '功率',
            '${data.power.toStringAsFixed(2)}mW',
            Icons.power,
            const Color(0xFF9C27B0),
          ),
        ),
      ],
    );
  }

  Widget _buildDataItem(
      String label, String value, IconData icon, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(vertical: 8, horizontal: 12),
      child: Column(
        children: [
          Icon(
            icon,
            color: color,
            size: 20,
          ),
          const SizedBox(height: 4),
          Text(
            label,
            style: TextStyle(
              fontSize: 11,
              color: Colors.grey.shade600,
              fontWeight: FontWeight.w500,
            ),
          ),
          const SizedBox(height: 2),
          Text(
            value,
            style: TextStyle(
              fontSize: 14,
              fontWeight: FontWeight.w600,
              color: color,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildPowerConsumption(DeviceData data, double consumption) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: const Color(0xFF2196F3).withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(
          color: const Color(0xFF2196F3).withValues(alpha: 0.3),
        ),
      ),
      child: Row(
        children: [
          Icon(
            Icons.battery_std,
            color: const Color(0xFF2196F3),
            size: 20,
          ),
          const SizedBox(width: 8),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  '本次记录耗电量',
                  style: TextStyle(
                    fontSize: 11,
                    color: Colors.grey.shade600,
                    fontWeight: FontWeight.w500,
                  ),
                ),
                const SizedBox(height: 1),
                Text(
                  '${device.sessionConsumption.toStringAsFixed(3)} mAh',
                  style: const TextStyle(
                    fontSize: 14,
                    color: Colors.blue,
                    fontWeight: FontWeight.w600,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  '累计耗电量',
                  style: TextStyle(
                    fontSize: 12,
                    color: Colors.grey.shade700,
                    fontWeight: FontWeight.w500,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  '${consumption.toStringAsFixed(3)} mAh',
                  style: const TextStyle(
                    fontSize: 16,
                    fontWeight: FontWeight.w600,
                    color: Color(0xFF2196F3),
                  ),
                ),
              ],
            ),
          ),
          Column(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              Text(
                '最后更新: ${_formatTime(data.timestamp)}',
                style: TextStyle(
                  fontSize: 10,
                  color: Colors.grey.shade500,
                ),
              ),
              const SizedBox(height: 2),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 1),
                decoration: BoxDecoration(
                  color: data.dataType == BleDataType.scanResponse
                      ? Colors.green.shade100
                      : Colors.blue.shade100,
                  borderRadius: BorderRadius.circular(4),
                ),
                child: Text(
                  data.dataType == BleDataType.scanResponse ? '扫描响应' : '广播包',
                  style: TextStyle(
                    fontSize: 8,
                    color: data.dataType == BleDataType.scanResponse
                        ? Colors.green.shade700
                        : Colors.blue.shade700,
                    fontWeight: FontWeight.w500,
                  ),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildNoDataState() {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: Colors.grey.shade50,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: Colors.grey.shade200),
      ),
      child: Row(
        children: [
          Icon(
            Icons.signal_wifi_off,
            color: Colors.grey.shade400,
            size: 24,
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  '暂无数据',
                  style: TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.w600,
                    color: Colors.grey.shade600,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  '等待设备广播数据...',
                  style: TextStyle(
                    fontSize: 12,
                    color: Colors.grey.shade500,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildActionButton() {
    return Container(
      width: double.infinity,
      child: ElevatedButton.icon(
        onPressed: onTap,
        icon: const Icon(Icons.analytics, size: 18),
        label: const Text(
          '查看图表',
          style: TextStyle(
            fontSize: 14,
            fontWeight: FontWeight.w600,
          ),
        ),
        style: ElevatedButton.styleFrom(
          backgroundColor: const Color(0xFF4A90E2),
          foregroundColor: Colors.white,
          padding: const EdgeInsets.symmetric(vertical: 12),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(8),
          ),
          elevation: 0,
        ),
      ),
    );
  }

  IconData _getDeviceIcon() {
    final deviceName = device.deviceName.toLowerCase();

    if (deviceName.contains('phone') || deviceName.contains('iphone')) {
      return Icons.phone_android;
    } else if (deviceName.contains('watch') || deviceName.contains('band')) {
      return Icons.watch;
    } else if (deviceName.contains('sensor')) {
      return Icons.sensors;
    } else if (deviceName.contains('power') || deviceName.contains('energy')) {
      return Icons.electrical_services;
    } else {
      return Icons.electrical_services; // 默认电量监控图标
    }
  }

  String _formatTime(DateTime time) {
    final now = DateTime.now();
    final diff = now.difference(time);

    if (diff.inSeconds < 60) {
      return '${diff.inSeconds}秒前';
    } else if (diff.inMinutes < 60) {
      return '${diff.inMinutes}分钟前';
    } else if (diff.inHours < 24) {
      return '${diff.inHours}小时前';
    } else {
      return '${time.month}/${time.day} ${time.hour.toString().padLeft(2, '0')}:${time.minute.toString().padLeft(2, '0')}';
    }
  }
}
