import 'package:flutter/material.dart';
import 'package:get/get.dart';
import '../models/device_data.dart';

class SavedDeviceCard extends StatelessWidget {
  final SelectedDevice device;
  final DeviceData? latestData;
  final double powerConsumption;
  final VoidCallback onTap;
  final VoidCallback onToggleMonitoring;
  final VoidCallback onDelete;

  const SavedDeviceCard({
    Key? key,
    required this.device,
    required this.latestData,
    required this.powerConsumption,
    required this.onTap,
    required this.onToggleMonitoring,
    required this.onDelete,
  }) : super(key: key);

  @override
  Widget build(BuildContext context) {
    return Obx(() => Container(
          margin: const EdgeInsets.only(bottom: 16),
          decoration: BoxDecoration(
            color: Colors.white,
            borderRadius: BorderRadius.circular(16),
            boxShadow: [
              BoxShadow(
                color: Colors.black.withOpacity(0.08),
                blurRadius: 12,
                offset: const Offset(0, 4),
              ),
            ],
            border: Border.all(
              color: device.isMonitoring.value
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
                padding: const EdgeInsets.all(20),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    // 设备标题和操作
                    _buildDeviceHeader(),
                    const SizedBox(height: 16),

                    // 实时数据或无数据状态
                    if (latestData != null) ...[
                      _buildDataDisplay(),
                      const SizedBox(height: 16),
                      _buildPowerInfo(),
                    ] else
                      _buildNoDataState(),

                    const SizedBox(height: 16),

                    // 操作按钮
                    _buildActionButtons(),
                  ],
                ),
              ),
            ),
          ),
        ));
  }

  Widget _buildDeviceHeader() {
    return Row(
      children: [
        // 左侧设备图标和名称信息
        Container(
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(
            color: device.isMonitoring.value
                ? const Color(0xFF4A90E2)
                    .withOpacity(0.1) // 注意：这里修正了withValues的错误用法
                : Colors.grey.shade100,
            borderRadius: BorderRadius.circular(12),
          ),
          child: Icon(
            _getDeviceIcon(),
            color: device.isMonitoring.value
                ? const Color(0xFF4A90E2)
                : Colors.grey.shade600,
            size: 24,
          ),
        ),
        const SizedBox(width: 16),

        // 中间设备名称和ID信息
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                device.deviceName,
                style: const TextStyle(
                  fontSize: 18,
                  fontWeight: FontWeight.w600,
                  color: Color(0xFF2E3A59),
                ),
              ),
              const SizedBox(height: 4),
              // 仅保留deviceId，数据统计移到按钮下方
              Text(
                device.deviceId,
                style: TextStyle(
                  fontSize: 12,
                  color: Colors.grey.shade600,
                  // fontFamily: 'monospace',  // 可根据需要恢复
                ),
                overflow: TextOverflow.ellipsis,
                maxLines: 1,
              ),
            ],
          ),
        ),

        const SizedBox(width: 12),

        // 右侧：开关按钮 + 数据统计（垂直排列）
        Column(
          mainAxisAlignment: MainAxisAlignment.center, // 垂直居中对齐
          children: [
            // 监控状态切换开关
            Switch(
              value: device.isMonitoring.value,
              onChanged: (_) => onToggleMonitoring(),
              activeColor: const Color(0xFF4CAF50),
              materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
            ),
            const SizedBox(height: 4), // 按钮和文本之间的间距
            // 数据统计文本（现在在按钮下方）
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
              decoration: BoxDecoration(
                color: Colors.grey.shade100,
                borderRadius: BorderRadius.circular(8),
              ),
              child: Text(
                '${device.dataHistory.length} 条数据',
                style: TextStyle(
                  fontSize: 10,
                  color: Colors.grey.shade600,
                  fontWeight: FontWeight.w500,
                ),
              ),
            ),
          ],
        ),
      ],
    );
  }

  Widget _buildDataDisplay() {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.grey.shade50,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: Colors.grey.shade200),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(
                Icons.analytics,
                color: const Color(0xFF4A90E2),
                size: 16,
              ),
              const SizedBox(width: 6),
              Text(
                '最新数据',
                style: TextStyle(
                  fontSize: 14,
                  fontWeight: FontWeight.w600,
                  color: Colors.grey.shade700,
                ),
              ),
              const Spacer(),
              Text(
                _formatTime(latestData!.timestamp),
                style: TextStyle(
                  fontSize: 12,
                  color: Colors.grey.shade500,
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          Row(
            children: [
              Expanded(
                child: _buildDataItem(
                  '电流',
                  '${latestData!.current.toStringAsFixed(1)}${latestData!.currentUnit}',
                  Icons.flash_on,
                  const Color(0xFFFF9800),
                ),
              ),
              Container(
                width: 1,
                height: 30,
                color: Colors.grey.shade300,
              ),
              Expanded(
                child: _buildDataItem(
                  '电压',
                  '${latestData!.voltage.toStringAsFixed(1)}mV',
                  Icons.battery_charging_full,
                  const Color(0xFF4CAF50),
                ),
              ),
              Container(
                width: 1,
                height: 30,
                color: Colors.grey.shade300,
              ),
              Expanded(
                child: _buildDataItem(
                  '功率',
                  '${latestData!.power.toStringAsFixed(2)}mW',
                  Icons.power,
                  const Color(0xFF9C27B0),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildDataItem(
      String label, String value, IconData icon, Color color) {
    return Column(
      children: [
        Icon(
          icon,
          color: color,
          size: 16,
        ),
        const SizedBox(height: 4),
        Text(
          label,
          style: TextStyle(
            fontSize: 10,
            color: Colors.grey.shade600,
          ),
        ),
        const SizedBox(height: 2),
        Text(
          value,
          style: TextStyle(
            fontSize: 12,
            fontWeight: FontWeight.w600,
            color: color,
          ),
        ),
      ],
    );
  }

  Widget _buildPowerInfo() {
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
            size: 18,
          ),
          const SizedBox(width: 8),
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                '本次记录耗电量: ${device.sessionConsumption.toStringAsFixed(3)} mAh',
                style: const TextStyle(
                  fontSize: 12,
                  fontWeight: FontWeight.w500,
                  color: Color(0xFF2196F3),
                ),
              ),
              const SizedBox(height: 2),
              Text(
                '累计耗电量: ${powerConsumption.toStringAsFixed(3)} mAh',
                style: const TextStyle(
                  fontSize: 14,
                  fontWeight: FontWeight.w600,
                  color: Color(0xFF2196F3),
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
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.grey.shade50,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: Colors.grey.shade200),
      ),
      child: Row(
        children: [
          Icon(
            Icons.signal_wifi_off,
            color: Colors.grey.shade400,
            size: 20,
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
                  device.isMonitoring.value ? '等待设备广播数据...' : '监控已暂停',
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

  Widget _buildActionButtons() {
    return Row(
      children: [
        Expanded(
          child: ElevatedButton.icon(
            onPressed: onTap,
            icon: const Icon(Icons.analytics, size: 16),
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
              padding: const EdgeInsets.symmetric(vertical: 10),
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(8),
              ),
              elevation: 0,
            ),
          ),
        ),
        const SizedBox(width: 12),
        Container(
          decoration: BoxDecoration(
            border: Border.all(color: Colors.red.shade300),
            borderRadius: BorderRadius.circular(8),
          ),
          child: IconButton(
            onPressed: onDelete,
            icon: const Icon(Icons.delete_outline),
            color: Colors.red,
            iconSize: 20,
            constraints: const BoxConstraints(
              minWidth: 40,
              minHeight: 40,
            ),
          ),
        ),
      ],
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
