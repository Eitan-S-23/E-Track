import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:get/get.dart';
import '../controllers/monitor_controller.dart';
import '../services/scan_settings_service.dart';
import '../models/device_data.dart';
import '../pages/device_chart_page.dart';
import '../pages/scan_settings_page.dart';
import '../widgets/device_monitor_card.dart';
// import 'power_stats_page.dart';

class MonitorPage extends StatelessWidget {
  const MonitorPage({Key? key}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    final monitorController = MonitorController.to;

    return Scaffold(
      backgroundColor: const Color(0xFFF5F7FA),
      appBar: AppBar(
        title: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              '实时监控',
              style: TextStyle(
                fontWeight: FontWeight.w600,
                fontSize: 18,
              ),
            ),
            Text(
              '统计数据仅基于扫描响应包',
              style: TextStyle(
                fontSize: 10,
                color: Colors.grey.shade600,
                fontWeight: FontWeight.w400,
              ),
            ),
          ],
        ),
        backgroundColor: Colors.white,
        foregroundColor: const Color(0xFF2E3A59),
        elevation: 0,
        bottom: PreferredSize(
          preferredSize: const Size.fromHeight(1),
          child: Container(
            height: 1,
            color: Colors.grey.shade200,
          ),
        ),
        actions: [
          Obx(() => IconButton(
                icon: Icon(
                  monitorController.isMonitoring.value
                      ? Icons.pause_circle_filled
                      : Icons.play_circle_filled,
                  color: monitorController.isMonitoring.value
                      ? const Color(0xFFFF6B6B)
                      : const Color(0xFF4CAF50),
                ),
                onPressed: () {
                  if (monitorController.isMonitoring.value) {
                    monitorController.stopMonitoring();
                  } else {
                    monitorController.startMonitoring();
                  }
                },
              )),
        ],
      ),
      body: Obx(() {
        // 使用与状态栏一致的逻辑，直接使用monitoringDevices计算属性
        final monitoringDevices = monitorController.monitoringDevices;

        return Column(
          children: [
            // 状态栏
            _buildMonitorStatusBar(monitorController),

            // 设备列表
            Expanded(
              child: monitoringDevices.isEmpty
                  ? _buildEmptyState()
                  : ListView.builder(
                      padding: const EdgeInsets.all(16),
                      itemCount: monitoringDevices.length,
                      itemBuilder: (context, index) {
                        final device = monitoringDevices[index];

                        return DeviceMonitorCard(
                          device: device,
                          latestData: null,
                          powerConsumption: 0.0,
                          onTap: () {
                            Get.to(() =>
                                DeviceChartPage(deviceId: device.deviceId));
                          },
                        )
                            .animate(delay: (index * 100).ms)
                            .fadeIn(duration: 400.ms)
                            .slideX(begin: 0.3, end: 0);
                      },
                    ),
            ),
          ],
        );
      }),
      floatingActionButton:
          Obx(() => monitorController.selectedDevices.isNotEmpty
              ? FloatingActionButton.extended(
                  onPressed: () {
                    monitorController.saveSelectedDevices();
                  },
                  icon: const Icon(Icons.save),
                  label: const Text('保存设备'),
                  backgroundColor: const Color(0xFF4A90E2),
                  foregroundColor: Colors.white,
                )
              : const SizedBox.shrink()),
    );
  }

  Widget _buildMonitorStatusBar(MonitorController controller) {
    final scanSettings = Get.find<ScanSettingsService>();

    return Container(
      margin: const EdgeInsets.all(16),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: controller.isMonitoring.value
              ? [const Color(0xFF4CAF50), const Color(0xFF2E7D32)]
              : [const Color(0xFF8E8E93), const Color(0xFF636366)],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(12),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.1),
            blurRadius: 8,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Column(
        children: [
          Row(
            children: [
              Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: Colors.white.withValues(alpha: 0.2),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Icon(
                  controller.isMonitoring.value ? Icons.monitor : Icons.pause,
                  color: Colors.white,
                  size: 20,
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      controller.isMonitoring.value ? '监控中' : '已暂停',
                      style: const TextStyle(
                        color: Colors.white,
                        fontSize: 16,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                    const SizedBox(height: 2),
                    Text(
                      '${controller.monitoringDevices.length} 个设备',
                      style: TextStyle(
                        color: Colors.white.withValues(alpha: 0.8),
                        fontSize: 12,
                      ),
                    ),
                  ],
                ),
              ),
              if (controller.isMonitoring.value)
                Container(
                  padding: const EdgeInsets.all(4),
                  decoration: BoxDecoration(
                    color: Colors.white.withValues(alpha: 0.2),
                    shape: BoxShape.circle,
                  ),
                  child: const SizedBox(
                    width: 12,
                    height: 12,
                    child: CircularProgressIndicator(
                      strokeWidth: 2,
                      valueColor: AlwaysStoppedAnimation<Color>(Colors.white),
                    ),
                  ),
                ),
            ],
          ),
          const SizedBox(height: 12),
          // 扫描间隔信息和快速设置
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
            decoration: BoxDecoration(
              color: Colors.white.withValues(alpha: 0.15),
              borderRadius: BorderRadius.circular(8),
            ),
            child: LayoutBuilder(
              builder: (context, constraints) {
                final isNarrow = constraints.maxWidth < 320;
                final buttons = Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    _buildQuickIntervalButton(scanSettings, '0.5s', 0.5),
                    const SizedBox(width: 4),
                    _buildQuickIntervalButton(scanSettings, '1s', 1.0),
                    const SizedBox(width: 4),
                    _buildQuickIntervalButton(scanSettings, '2s', 2.0),
                    const SizedBox(width: 8),
                    GestureDetector(
                      onTap: () {
                        Get.to(() => const ScanSettingsPage());
                      },
                      child: Container(
                        padding: const EdgeInsets.symmetric(
                            horizontal: 8, vertical: 4),
                        decoration: BoxDecoration(
                          color: Colors.white.withValues(alpha: 0.2),
                          borderRadius: BorderRadius.circular(4),
                        ),
                        child: const Icon(
                          Icons.settings,
                          color: Colors.white,
                          size: 16,
                        ),
                      ),
                    ),
                  ],
                );

                final title = Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const Icon(
                      Icons.timer,
                      color: Colors.white,
                      size: 16,
                    ),
                    const SizedBox(width: 8),
                    Flexible(
                      child: Text(
                        '扫描间隔: ${scanSettings.scanIntervalSeconds}秒',
                        overflow: TextOverflow.ellipsis,
                        style: TextStyle(
                          color: Colors.white.withValues(alpha: 0.9),
                          fontSize: 12,
                          fontWeight: FontWeight.w500,
                        ),
                      ),
                    ),
                  ],
                );

                if (isNarrow) {
                  return Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      title,
                      const SizedBox(height: 8),
                      SingleChildScrollView(
                        scrollDirection: Axis.horizontal,
                        child: buttons,
                      ),
                    ],
                  );
                }

                return Row(
                  children: [
                    Expanded(child: title),
                    buttons,
                  ],
                );
              },
            ),
          ),
        ],
      ),
    ).animate().fadeIn(duration: 500.ms).slideY(begin: -0.2, end: 0);
  }

  Widget _buildQuickIntervalButton(
      ScanSettingsService scanSettings, String label, double seconds) {
    final isSelected =
        (scanSettings.scanIntervalSeconds - seconds).abs() < 0.01;

    return GestureDetector(
      onTap: () async {
        if (!isSelected) {
          await scanSettings.setScanIntervalSeconds(
            seconds,
            onChanged: () => MonitorController.to.refreshScanInterval(),
          );
        }
      },
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
        decoration: BoxDecoration(
          color: isSelected
              ? Colors.white.withValues(alpha: 0.3)
              : Colors.white.withValues(alpha: 0.1),
          borderRadius: BorderRadius.circular(4),
          border: isSelected
              ? Border.all(color: Colors.white.withValues(alpha: 0.5), width: 1)
              : null,
        ),
        child: Text(
          label,
          style: TextStyle(
            color: Colors.white,
            fontSize: 10,
            fontWeight: isSelected ? FontWeight.w600 : FontWeight.w400,
          ),
        ),
      ),
    );
  }

  Widget _buildEmptyState() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Container(
            padding: const EdgeInsets.all(24),
            decoration: BoxDecoration(
              color: Colors.grey.shade100,
              shape: BoxShape.circle,
            ),
            child: Icon(
              Icons.monitor,
              size: 64,
              color: Colors.grey.shade400,
            ),
          ),
          const SizedBox(height: 24),
          Text(
            '暂无监控设备',
            style: TextStyle(
              fontSize: 18,
              fontWeight: FontWeight.w600,
              color: Colors.grey.shade600,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            '请先选择要监控的设备',
            style: TextStyle(
              fontSize: 14,
              color: Colors.grey.shade500,
            ),
          ),
          const SizedBox(height: 24),
          ElevatedButton.icon(
            onPressed: () {
              Get.back(); // 返回主页面
            },
            icon: const Icon(Icons.add),
            label: const Text('选择设备'),
            style: ElevatedButton.styleFrom(
              backgroundColor: const Color(0xFF4A90E2),
              foregroundColor: Colors.white,
              padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(12),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
