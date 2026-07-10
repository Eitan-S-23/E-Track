import 'package:flutter/material.dart';
import 'package:flutter_blue_plus/flutter_blue_plus.dart';
import 'package:get/get.dart';
import '../controllers/ble_controller.dart';
import '../controllers/monitor_controller.dart';
import '../services/scan_settings_service.dart';
import 'monitor_page.dart';
import 'saved_devices_page.dart';
import 'scan_settings_page.dart';
import 'device_comparison_page.dart';
import 'device_detail_page.dart';
import '../widgets/selectable_device_card.dart';

class PowerMeterPage extends StatelessWidget {
  const PowerMeterPage({Key? key}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    final bleController = Get.put(BleController(), permanent: true);
    final monitorController = Get.put(MonitorController(), permanent: true);
    final scanSettings = Get.put(ScanSettingsService(), permanent: true);

    return Scaffold(
      backgroundColor: const Color(0xFFF8F9FA),
      appBar: AppBar(
        title: const Text(
          '功率计',
          style: TextStyle(
            fontSize: 20,
            fontWeight: FontWeight.w600,
            color: Color(0xFF2E3A59),
          ),
        ),
        backgroundColor: Colors.white,
        elevation: 0,
        actions: [
          // 扫描设置按钮
          Obx(() => IconButton(
                icon: Badge(
                  label: Text('${scanSettings.scanIntervalSeconds}s'),
                  backgroundColor: const Color(0xFF4A90E2),
                  textColor: Colors.white,
                  child: const Icon(Icons.timer, color: Color(0xFF2E3A59)),
                ),
                onPressed: () {
                  Get.to(() => const ScanSettingsPage());
                },
              )),
          // 设备对比按钮
          IconButton(
            icon: const Icon(Icons.compare_arrows, color: Color(0xFF2E3A59)),
            onPressed: () {
              Get.to(() => const DeviceComparisonPage());
            },
          ),
          // 已保存设备按钮
          IconButton(
            icon: const Icon(Icons.bookmark, color: Color(0xFF2E3A59)),
            onPressed: () {
              Get.to(() => const SavedDevicesPage());
            },
          ),
        ],
      ),
      body: Column(
        children: [
          // 状态卡片
          Container(
            margin: const EdgeInsets.all(16),
            padding: const EdgeInsets.all(16),
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
            ),
            child: Obx(() => Row(
                  children: [
                    // 蓝牙状态
                    Expanded(
                      child: _buildStatusItem(
                        icon: Icons.bluetooth,
                        title: '蓝牙状态',
                        value: bleController.adapterState.value ==
                                BluetoothAdapterState.on
                            ? '已开启'
                            : '未开启',
                        color: bleController.adapterState.value ==
                                BluetoothAdapterState.on
                            ? const Color(0xFF50C878)
                            : Colors.red,
                      ),
                    ),
                    Container(
                      height: 40,
                      width: 1,
                      color: Colors.grey[300],
                    ),
                    // 扫描状态
                    Expanded(
                      child: _buildStatusItem(
                        icon: Icons.radar,
                        title: '扫描状态',
                        value: bleController.isScanning.value ? '扫描中' : '已停止',
                        color: bleController.isScanning.value
                            ? const Color(0xFF4A90E2)
                            : Colors.grey,
                      ),
                    ),
                    Container(
                      height: 40,
                      width: 1,
                      color: Colors.grey[300],
                    ),
                    // 选中设备数
                    Expanded(
                      child: _buildStatusItem(
                        icon: Icons.devices,
                        title: '已选设备',
                        value: '${monitorController.selectedDevices.length}',
                        color: const Color(0xFF2E3A59),
                      ),
                    ),
                  ],
                )),
          ),

          // 扫描控制按钮
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16),
            child: Row(
              children: [
                Expanded(
                  child: Obx(() => ElevatedButton.icon(
                        onPressed: bleController.isScanning.value
                            ? bleController.stopScan
                            : bleController.startScan,
                        icon: Icon(
                          bleController.isScanning.value
                              ? Icons.stop
                              : Icons.play_arrow,
                          color: Colors.white,
                        ),
                        label: Text(
                          bleController.isScanning.value ? '停止扫描' : '开始扫描',
                          style: const TextStyle(
                            fontSize: 16,
                            fontWeight: FontWeight.w600,
                            color: Colors.white,
                          ),
                        ),
                        style: ElevatedButton.styleFrom(
                          backgroundColor: bleController.isScanning.value
                              ? Colors.red
                              : const Color(0xFF4A90E2),
                          padding: const EdgeInsets.symmetric(vertical: 16),
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(12),
                          ),
                        ),
                      )),
                ),
                const SizedBox(width: 12),
                Obx(() => monitorController.selectedDevices.isNotEmpty
                    ? ElevatedButton.icon(
                        onPressed: () {
                          Get.to(() => const MonitorPage());
                        },
                        icon: const Icon(Icons.monitor, color: Colors.white),
                        label: const Text(
                          '监控',
                          style: TextStyle(
                            fontSize: 16,
                            fontWeight: FontWeight.w600,
                            color: Colors.white,
                          ),
                        ),
                        style: ElevatedButton.styleFrom(
                          backgroundColor: const Color(0xFF50C878),
                          padding: const EdgeInsets.symmetric(
                            horizontal: 24,
                            vertical: 16,
                          ),
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(12),
                          ),
                        ),
                      )
                    : const SizedBox.shrink()),
              ],
            ),
          ),

          const SizedBox(height: 16),

          // 设备列表
          Expanded(
            child: Obx(() {
              if (bleController.discoveredDevices.isEmpty) {
                return Center(
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Icon(
                        Icons.bluetooth_searching,
                        size: 64,
                        color: Colors.grey[400],
                      ),
                      const SizedBox(height: 16),
                      Text(
                        bleController.isScanning.value
                            ? '正在搜索设备...'
                            : '点击开始扫描发现设备',
                        style: TextStyle(
                          fontSize: 16,
                          color: Colors.grey[600],
                        ),
                      ),
                    ],
                  ),
                );
              }

              return ListView.builder(
                padding: const EdgeInsets.symmetric(horizontal: 16),
                itemCount: bleController.discoveredDevices.length,
                itemBuilder: (context, index) {
                  final device = bleController.discoveredDevices[index];
                  return Padding(
                    padding: const EdgeInsets.only(bottom: 12),
                    child: Obx(() => SelectableDeviceCard(
                          device: device,
                          bleController: bleController,
                          monitorController: monitorController,
                          isConnected: false,
                          isSelected:
                              monitorController.isDeviceSelected(device),
                          onTap: () {
                            Get.to(() => DeviceDetailPage(device: device));
                          },
                          onSelect: () =>
                              monitorController.selectDevice(device),
                          onConnect: () {},
                        )),
                  );
                },
              );
            }),
          ),
        ],
      ),
    );
  }

  Widget _buildStatusItem({
    required IconData icon,
    required String title,
    required String value,
    required Color color,
  }) {
    return Column(
      children: [
        Icon(icon, color: color, size: 20),
        const SizedBox(height: 4),
        Text(
          title,
          style: TextStyle(
            fontSize: 12,
            color: Colors.grey[600],
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
    );
  }
}
