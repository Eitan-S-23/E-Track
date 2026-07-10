import 'package:flutter/material.dart';
import 'package:flutter_blue_plus/flutter_blue_plus.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:get/get.dart';
import '../controllers/ble_controller.dart';
import '../controllers/monitor_controller.dart';
import '../pages/device_detail_page.dart';
import '../pages/monitor_page.dart';
import '../pages/saved_devices_page.dart';
import '../widgets/selectable_device_card.dart';
import '../utils/permission_helper.dart';

class HomePage extends StatelessWidget {
  const HomePage({Key? key}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    final bleController = Get.put(BleController(), permanent: true);
    final monitorController = Get.put(MonitorController(), permanent: true);

    return Obx(
      () => Scaffold(
        backgroundColor: const Color(0xFFF5F7FA),
        appBar: AppBar(
          title: const Text(
            'BLE 设备监控',
            style: TextStyle(
              fontWeight: FontWeight.w600,
              fontSize: 20,
            ),
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
            // 已保存设备按钮
            IconButton(
              icon: const Icon(Icons.bookmark),
              onPressed: () {
                Get.to(() => const SavedDevicesPage());
              },
            ),
            // 监控页面按钮
            IconButton(
              icon: const Icon(Icons.monitor),
              onPressed: () {
                Get.to(() => const MonitorPage());
              },
            ),
            // 蓝牙状态图标
            IconButton(
              icon: Icon(
                bleController.adapterState.value == BluetoothAdapterState.on
                    ? Icons.bluetooth
                    : Icons.bluetooth_disabled,
                color:
                    bleController.adapterState.value == BluetoothAdapterState.on
                        ? Colors.blue
                        : Colors.grey,
              ),
              onPressed: () {
                if (bleController.adapterState.value !=
                    BluetoothAdapterState.on) {
                  bleController.turnOnBluetooth();
                }
              },
            ),
          ],
        ),
        body: Column(
          children: [
            // 状态卡片
            _buildStatusCard(bleController, monitorController),
            // 控制部分
            _buildControlSection(bleController, monitorController),
            // 设备列表
            Expanded(child: _buildDeviceList(bleController, monitorController)),
          ],
        ),
      ),
    );
  }

  Widget _buildStatusCard(
      BleController bleController, MonitorController monitorController) {
    return Container(
      margin: const EdgeInsets.all(16),
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [
            bleController.adapterState.value == BluetoothAdapterState.on
                ? const Color(0xFF4A90E2)
                : const Color(0xFF8E8E93),
            bleController.adapterState.value == BluetoothAdapterState.on
                ? const Color(0xFF357ABD)
                : const Color(0xFF636366),
          ],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(16),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.1),
            blurRadius: 10,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: Colors.white.withValues(alpha: 0.2),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Icon(
                  bleController.adapterState.value == BluetoothAdapterState.on
                      ? Icons.bluetooth
                      : Icons.bluetooth_disabled,
                  color: Colors.white,
                  size: 24,
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      '蓝牙状态',
                      style: TextStyle(
                        color: Colors.white.withValues(alpha: 0.9),
                        fontSize: 14,
                        fontWeight: FontWeight.w500,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      _getAdapterStateText(bleController.adapterState.value),
                      style: const TextStyle(
                        color: Colors.white,
                        fontSize: 18,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          Row(
            children: [
              Expanded(
                child: _buildStatusItem(
                  '已发现',
                  bleController.discoveredDevices.length.toString(),
                  Icons.devices,
                ),
              ),
              Container(
                width: 1,
                height: 40,
                color: Colors.white.withValues(alpha: 0.3),
              ),
              Expanded(
                child: _buildStatusItem(
                  '已选择',
                  monitorController.selectedDevices.length.toString(),
                  Icons.check_circle,
                ),
              ),
              Container(
                width: 1,
                height: 40,
                color: Colors.white.withValues(alpha: 0.3),
              ),
              Expanded(
                child: _buildStatusItem(
                  '已保存',
                  monitorController.savedDevices.length.toString(),
                  Icons.bookmark,
                ),
              ),
            ],
          ),
        ],
      ),
    ).animate().fadeIn(duration: 600.ms).slideY(begin: -0.3, end: 0);
  }

  Widget _buildStatusItem(String label, String value, IconData icon) {
    return Column(
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(icon, color: Colors.white.withValues(alpha: 0.8), size: 16),
            const SizedBox(width: 4),
            Text(
              label,
              style: TextStyle(
                color: Colors.white.withValues(alpha: 0.8),
                fontSize: 12,
              ),
            ),
          ],
        ),
        const SizedBox(height: 4),
        Text(
          value,
          style: const TextStyle(
            color: Colors.white,
            fontSize: 20,
            fontWeight: FontWeight.bold,
          ),
        ),
      ],
    );
  }

  Widget _buildControlSection(
      BleController bleController, MonitorController monitorController) {
    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 16),
      child: Column(
        children: [
          // 扫描控制
          Row(
            children: [
              Expanded(
                child: ElevatedButton.icon(
                  onPressed: bleController.adapterState.value ==
                          BluetoothAdapterState.on
                      ? () async {
                          if (bleController.isScanning.value) {
                            bleController.stopScan();
                          } else {
                            final hasPermissions = await PermissionHelper
                                .checkBluetoothPermissions();
                            if (!hasPermissions) {
                              PermissionHelper
                                  .showBluetoothPermissionEducation();
                            } else {
                              bleController.startScan();
                            }
                          }
                        }
                      : () {
                          PermissionHelper.showBluetoothDisabledDialog();
                        },
                  icon: bleController.isScanning.value
                      ? const SizedBox(
                          width: 16,
                          height: 16,
                          child: CircularProgressIndicator(
                            strokeWidth: 2,
                            valueColor:
                                AlwaysStoppedAnimation<Color>(Colors.white),
                          ),
                        )
                      : const Icon(Icons.search),
                  label: Text(
                    bleController.isScanning.value ? '停止扫描' : '开始扫描',
                    style: const TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: bleController.isScanning.value
                        ? const Color(0xFFFF6B6B)
                        : const Color(0xFF4A90E2),
                    foregroundColor: Colors.white,
                    padding: const EdgeInsets.symmetric(vertical: 16),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(12),
                    ),
                    elevation: 0,
                    shadowColor: Colors.transparent,
                  ),
                ),
              ),
              const SizedBox(width: 12),
              Container(
                decoration: BoxDecoration(
                  color: Colors.white,
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(color: Colors.grey.shade200),
                ),
                child: IconButton(
                  onPressed: () {
                    bleController.updateConnectedDevices();
                    monitorController.clearSelection();
                    Get.snackbar('提示', '已刷新设备列表',
                        snackPosition: SnackPosition.BOTTOM);
                  },
                  icon: const Icon(Icons.refresh),
                  color: const Color(0xFF4A90E2),
                ),
              ),
            ],
          ),

          // 选择控制（当有选中设备时显示）
          if (monitorController.selectedDevices.isNotEmpty) ...[
            const SizedBox(height: 12),
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: const Color(0xFF4A90E2).withValues(alpha: 0.1),
                borderRadius: BorderRadius.circular(12),
                border: Border.all(
                    color: const Color(0xFF4A90E2).withValues(alpha: 0.3)),
              ),
              child: Column(
                children: [
                  Row(
                    children: [
                      Icon(
                        Icons.check_circle,
                        color: const Color(0xFF4A90E2),
                        size: 20,
                      ),
                      const SizedBox(width: 8),
                      Text(
                        '已选择 ${monitorController.selectedDevices.length} 个设备',
                        style: const TextStyle(
                          fontWeight: FontWeight.w600,
                          color: Color(0xFF4A90E2),
                        ),
                      ),
                      const Spacer(),
                      TextButton(
                        onPressed: () {
                          monitorController.clearSelection();
                        },
                        child: const Text('清除'),
                      ),
                    ],
                  ),
                  const SizedBox(height: 12),
                  Row(
                    children: [
                      Expanded(
                        child: ElevatedButton.icon(
                          onPressed: () {
                            monitorController.confirmSelection();
                            Get.to(() => const MonitorPage());
                          },
                          icon: const Icon(Icons.monitor),
                          label: const Text('开始监控'),
                          style: ElevatedButton.styleFrom(
                            backgroundColor: const Color(0xFF4CAF50),
                            foregroundColor: Colors.white,
                            padding: const EdgeInsets.symmetric(vertical: 12),
                            shape: RoundedRectangleBorder(
                              borderRadius: BorderRadius.circular(8),
                            ),
                          ),
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: ElevatedButton.icon(
                          onPressed: () {
                            monitorController.saveSelectedDevices();
                          },
                          icon: const Icon(Icons.save),
                          label: const Text('保存设备'),
                          style: ElevatedButton.styleFrom(
                            backgroundColor: const Color(0xFFFF9800),
                            foregroundColor: Colors.white,
                            padding: const EdgeInsets.symmetric(vertical: 12),
                            shape: RoundedRectangleBorder(
                              borderRadius: BorderRadius.circular(8),
                            ),
                          ),
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ).animate().fadeIn(duration: 300.ms).slideY(begin: -0.1, end: 0),
          ],
        ],
      ),
    ).animate().fadeIn(duration: 800.ms).slideX(begin: -0.3, end: 0);
  }

  Widget _buildDeviceList(
      BleController bleController, MonitorController monitorController) {
    if (bleController.discoveredDevices.isEmpty) {
      return _buildEmptyState(bleController);
    }

    return Container(
      margin: const EdgeInsets.only(top: 16),
      child: ListView.builder(
        padding: const EdgeInsets.symmetric(horizontal: 16),
        itemCount: bleController.discoveredDevices.length,
        itemBuilder: (context, index) {
          final device = bleController.discoveredDevices[index];
          final isConnected = bleController.connectedDevices
              .any((d) => d.remoteId == device.remoteId);

          return Obx(() {
            final isSelectedNow = monitorController.isDeviceSelected(device);
            return SelectableDeviceCard(
              device: device,
              bleController: bleController,
              monitorController: monitorController,
              isConnected: isConnected,
              isSelected: isSelectedNow,
              onTap: () {
                Get.to(() => DeviceDetailPage(device: device));
              },
              onSelect: () {
                monitorController.selectDevice(device);
              },
              onConnect: () {
                if (isConnected) {
                  bleController.disconnectDevice(device);
                } else {
                  bleController.connectDevice(device);
                }
              },
            );
          });
        },
      ),
    );
  }

  Widget _buildEmptyState(BleController bleController) {
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
              Icons.bluetooth_searching,
              size: 64,
              color: Colors.grey.shade400,
            ),
          ),
          const SizedBox(height: 24),
          Text(
            bleController.isScanning.value ? '正在搜索设备...' : '暂未发现设备',
            style: TextStyle(
              fontSize: 18,
              fontWeight: FontWeight.w600,
              color: Colors.grey.shade600,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            bleController.isScanning.value
                ? '请确保目标设备处于可发现状态'
                : '点击"开始扫描"按钮搜索附近的蓝牙设备',
            style: TextStyle(
              fontSize: 14,
              color: Colors.grey.shade500,
            ),
            textAlign: TextAlign.center,
          ),
          if (!bleController.isScanning.value &&
              bleController.adapterState.value == BluetoothAdapterState.on) ...[
            const SizedBox(height: 24),
            ElevatedButton.icon(
              onPressed: bleController.startScan,
              icon: const Icon(Icons.search),
              label: const Text('开始扫描'),
              style: ElevatedButton.styleFrom(
                backgroundColor: const Color(0xFF4A90E2),
                foregroundColor: Colors.white,
                padding:
                    const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(12),
                ),
              ),
            ),
          ],
        ],
      ),
    );
  }

  String _getAdapterStateText(BluetoothAdapterState state) {
    switch (state) {
      case BluetoothAdapterState.on:
        return '已开启';
      case BluetoothAdapterState.off:
        return '已关闭';
      case BluetoothAdapterState.turningOn:
        return '正在开启...';
      case BluetoothAdapterState.turningOff:
        return '正在关闭...';
      default:
        return '未知状态';
    }
  }
}
