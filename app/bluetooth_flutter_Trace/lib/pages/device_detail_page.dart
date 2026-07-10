import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_blue_plus/flutter_blue_plus.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:get/get.dart';
import 'package:share_plus/share_plus.dart';
import '../config/share_links.dart';
import '../controllers/ble_controller.dart';
import 'ota_upgrade_page.dart';

// AD Type data structure
class AdTypeData {
  final int type;
  final String typeName;
  final String description;
  final List<int> data;
  final String hexData;
  final Color color;

  AdTypeData({
    required this.type,
    required this.typeName,
    required this.description,
    required this.data,
    required this.hexData,
    required this.color,
  });
}

class DeviceDetailPage extends StatelessWidget {
  final BluetoothDevice device;

  const DeviceDetailPage({Key? key, required this.device}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    final controller = Get.put(BleController(), permanent: true);
    final scanResult = controller.getScanResult(device);
    final isConnected =
        controller.connectedDevices.any((d) => d.remoteId == device.remoteId);

    return Scaffold(
      backgroundColor: const Color(0xFFF5F7FA),
      appBar: AppBar(
        title: Text(
          controller.getDeviceName(device),
          style: const TextStyle(
            fontWeight: FontWeight.w600,
            fontSize: 18,
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
          IconButton(
            icon: const Icon(Icons.share),
            onPressed: () => _shareDeviceInfo(context, controller),
          ),
        ],
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // 设备基本信息卡片
            _buildBasicInfoCard(controller, isConnected)
                .animate()
                .fadeIn(duration: 600.ms)
                .slideY(begin: 0.3, end: 0),
            const SizedBox(height: 16),

            if (isConnected)
              _buildFirmwareUpdateCard()
                  .animate(delay: 150.ms)
                  .fadeIn(duration: 600.ms)
                  .slideY(begin: 0.3, end: 0),
            if (isConnected) const SizedBox(height: 16),

            // 信号强度卡片
            _buildSignalCard(controller)
                .animate(delay: 200.ms)
                .fadeIn(duration: 600.ms)
                .slideY(begin: 0.3, end: 0),
            const SizedBox(height: 16),

            // 广播数据卡片
            if (scanResult != null)
              _buildAdvertisementCard(scanResult)
                  .animate(delay: 400.ms)
                  .fadeIn(duration: 600.ms)
                  .slideY(begin: 0.3, end: 0),
            if (scanResult != null) const SizedBox(height: 16),

            // 完整广播包数据卡片
            if (scanResult != null)
              _buildRawAdvertisementDataCard(scanResult)
                  .animate(delay: 500.ms)
                  .fadeIn(duration: 600.ms)
                  .slideY(begin: 0.3, end: 0),
            if (scanResult != null) const SizedBox(height: 16),

            // 服务UUID卡片
            _buildServicesCard(controller)
                .animate(delay: 600.ms)
                .fadeIn(duration: 600.ms)
                .slideY(begin: 0.3, end: 0),
            const SizedBox(height: 16),

            // 制造商数据卡片
            if (scanResult?.advertisementData.manufacturerData.isNotEmpty ==
                true)
              _buildManufacturerDataCard(scanResult!)
                  .animate(delay: 800.ms)
                  .fadeIn(duration: 600.ms)
                  .slideY(begin: 0.3, end: 0),
            if (scanResult?.advertisementData.manufacturerData.isNotEmpty ==
                true)
              const SizedBox(height: 16),

            // 连接控制
            _buildConnectionControl(controller, isConnected)
                .animate(delay: 1000.ms)
                .fadeIn(duration: 600.ms)
                .slideY(begin: 0.3, end: 0),
          ],
        ),
      ),
    );
  }

  Widget _buildFirmwareUpdateCard() {
    return Material(
      color: Colors.transparent,
      child: InkWell(
        borderRadius: BorderRadius.circular(16),
        onTap: () => Get.to(() => OtaUpgradePage(connectedDevice: device)),
        child: Ink(
          width: double.infinity,
          padding: const EdgeInsets.all(18),
          decoration: BoxDecoration(
            gradient: const LinearGradient(
              colors: [
                Color(0xFF0EA5E9),
                Color(0xFF2563EB),
              ],
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
            ),
            borderRadius: BorderRadius.circular(16),
            boxShadow: [
              BoxShadow(
                color: const Color(0xFF2563EB).withOpacity(0.22),
                blurRadius: 16,
                offset: const Offset(0, 8),
              ),
            ],
          ),
          child: Row(
            children: [
              Container(
                width: 46,
                height: 46,
                decoration: BoxDecoration(
                  color: Colors.white.withValues(alpha: 0.18),
                  borderRadius: BorderRadius.circular(14),
                  border: Border.all(
                    color: Colors.white.withValues(alpha: 0.24),
                  ),
                ),
                child: const Icon(
                  Icons.system_update_alt,
                  color: Colors.white,
                  size: 24,
                ),
              ),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      '检查单片机固件更新',
                      style: TextStyle(
                        color: Colors.white,
                        fontSize: 16,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      '下载最新码表固件',
                      style: TextStyle(
                        color: Colors.white.withValues(alpha: 0.82),
                        fontSize: 13,
                        fontWeight: FontWeight.w500,
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 12),
              Icon(
                Icons.chevron_right,
                color: Colors.white.withValues(alpha: 0.86),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildBasicInfoCard(BleController controller, bool isConnected) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [
            isConnected ? const Color(0xFF4A90E2) : const Color(0xFF8E8E93),
            isConnected ? const Color(0xFF357ABD) : const Color(0xFF636366),
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
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: Colors.white.withValues(alpha: 0.2),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Icon(
                  _getDeviceIcon(),
                  color: Colors.white,
                  size: 32,
                ),
              ),
              const SizedBox(width: 16),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      controller.getDeviceName(device),
                      style: const TextStyle(
                        color: Colors.white,
                        fontSize: 20,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Row(
                      children: [
                        Icon(
                          isConnected ? Icons.link : Icons.link_off,
                          color: Colors.white.withValues(alpha: 0.8),
                          size: 16,
                        ),
                        const SizedBox(width: 4),
                        Text(
                          isConnected ? '已连接' : '未连接',
                          style: TextStyle(
                            color: Colors.white.withValues(alpha: 0.9),
                            fontSize: 14,
                            fontWeight: FontWeight.w500,
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 20),
          _buildInfoRow(
              '设备ID', controller.getDeviceId(device), Icons.fingerprint),
          const SizedBox(height: 12),
          _buildInfoRow(
              '可连接', controller.isConnectable(device) ? '是' : '否', Icons.link),
        ],
      ),
    );
  }

  Widget _buildInfoRow(String label, String value, IconData icon) {
    return Row(
      children: [
        Icon(
          icon,
          color: Colors.white.withValues(alpha: 0.8),
          size: 16,
        ),
        const SizedBox(width: 8),
        Text(
          '$label: ',
          style: TextStyle(
            color: Colors.white.withValues(alpha: 0.8),
            fontSize: 14,
          ),
        ),
        Expanded(
          child: Text(
            value,
            style: const TextStyle(
              color: Colors.white,
              fontSize: 14,
              fontWeight: FontWeight.w600,
            ),
          ),
        ),
        IconButton(
          onPressed: () {
            Clipboard.setData(ClipboardData(text: value));
            Get.snackbar('提示', '已复制到剪贴板', snackPosition: SnackPosition.BOTTOM);
          },
          icon: Icon(
            Icons.copy,
            color: Colors.white.withValues(alpha: 0.8),
            size: 16,
          ),
          constraints: const BoxConstraints(),
          padding: const EdgeInsets.all(4),
        ),
      ],
    );
  }

  Widget _buildSignalCard(BleController controller) {
    final rssi = controller.getDeviceRssi(device);
    final signalStrength = ((rssi + 100) / 50 * 100).clamp(0, 100);

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(20),
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
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: controller.getRssiColor(rssi).withOpacity(0.1),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Icon(
                  Icons.signal_cellular_alt,
                  color: controller.getRssiColor(rssi),
                  size: 20,
                ),
              ),
              const SizedBox(width: 12),
              Text(
                '信号强度',
                style: TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.w600,
                  color: Colors.grey.shade800,
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          Row(
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      '${rssi} dBm',
                      style: TextStyle(
                        fontSize: 24,
                        fontWeight: FontWeight.bold,
                        color: controller.getRssiColor(rssi),
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      controller.getRssiDescription(rssi),
                      style: TextStyle(
                        fontSize: 14,
                        color: Colors.grey.shade600,
                      ),
                    ),
                  ],
                ),
              ),
              Container(
                width: 80,
                height: 80,
                child: CircularProgressIndicator(
                  value: signalStrength / 100,
                  backgroundColor: Colors.grey.shade200,
                  valueColor: AlwaysStoppedAnimation<Color>(
                    controller.getRssiColor(rssi),
                  ),
                  strokeWidth: 8,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildAdvertisementCard(ScanResult scanResult) {
    final advData = scanResult.advertisementData;

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(20),
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
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: const Color(0xFF4A90E2).withOpacity(0.1),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: const Icon(
                  Icons.broadcast_on_personal,
                  color: Color(0xFF4A90E2),
                  size: 20,
                ),
              ),
              const SizedBox(width: 12),
              Text(
                '广播数据',
                style: TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.w600,
                  color: Colors.grey.shade800,
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          _buildDataRow(
              '设备名称', advData.advName.isNotEmpty ? advData.advName : '未提供'),
          _buildDataRow('可连接', advData.connectable ? '是' : '否'),
          _buildDataRow('发射功率', '${advData.txPowerLevel ?? 'N/A'} dBm'),
          if (advData.serviceData.isNotEmpty)
            _buildDataRow('服务数据', '${advData.serviceData.length} 个'),
        ],
      ),
    );
  }

  Widget _buildServicesCard(BleController controller) {
    final serviceUuids = controller.getServiceUuids(device);

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(20),
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
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: const Color(0xFF9C27B0).withOpacity(0.1),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: const Icon(
                  Icons.settings_applications,
                  color: Color(0xFF9C27B0),
                  size: 20,
                ),
              ),
              const SizedBox(width: 12),
              Text(
                '服务 UUID',
                style: TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.w600,
                  color: Colors.grey.shade800,
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          if (serviceUuids.isEmpty)
            Text(
              '暂无发现的服务',
              style: TextStyle(
                fontSize: 14,
                color: Colors.grey.shade600,
              ),
            )
          else
            ...serviceUuids.map((uuid) => Container(
                  margin: const EdgeInsets.only(bottom: 8),
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: Colors.grey.shade50,
                    borderRadius: BorderRadius.circular(8),
                    border: Border.all(color: Colors.grey.shade200),
                  ),
                  child: Row(
                    children: [
                      Expanded(
                        child: Text(
                          uuid,
                          style: const TextStyle(
                            fontSize: 12,
                            fontFamily: 'monospace',
                            fontWeight: FontWeight.w500,
                          ),
                        ),
                      ),
                      IconButton(
                        onPressed: () {
                          Clipboard.setData(ClipboardData(text: uuid));
                          Get.snackbar('提示', '已复制UUID到剪贴板',
                              snackPosition: SnackPosition.BOTTOM);
                        },
                        icon: Icon(
                          Icons.copy,
                          size: 16,
                          color: Colors.grey.shade600,
                        ),
                        constraints: const BoxConstraints(),
                        padding: const EdgeInsets.all(4),
                      ),
                    ],
                  ),
                )),
        ],
      ),
    );
  }

  Widget _buildManufacturerDataCard(ScanResult scanResult) {
    final manufData = scanResult.advertisementData.manufacturerData;

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(20),
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
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: const Color(0xFFFF9800).withOpacity(0.1),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: const Icon(
                  Icons.business,
                  color: Color(0xFFFF9800),
                  size: 20,
                ),
              ),
              const SizedBox(width: 12),
              Text(
                '制造商数据',
                style: TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.w600,
                  color: Colors.grey.shade800,
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          ...manufData.entries.map((entry) => Container(
                margin: const EdgeInsets.only(bottom: 12),
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: Colors.grey.shade50,
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: Colors.grey.shade200),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      '公司ID: 0x${entry.key.toRadixString(16).padLeft(4, '0').toUpperCase()}',
                      style: const TextStyle(
                        fontSize: 14,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                    const SizedBox(height: 8),
                    Text(
                      '数据: ${entry.value.map((b) => b.toRadixString(16).padLeft(2, '0').toUpperCase()).join(' ')}',
                      style: const TextStyle(
                        fontSize: 12,
                        fontFamily: 'monospace',
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      'ASCII: ${String.fromCharCodes(entry.value.where((b) => b >= 32 && b <= 126))}',
                      style: TextStyle(
                        fontSize: 12,
                        color: Colors.grey.shade600,
                      ),
                    ),
                  ],
                ),
              )),
        ],
      ),
    );
  }

  Widget _buildConnectionControl(BleController controller, bool isConnected) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(20),
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
      ),
      child: Column(
        children: [
          if (controller.isConnectable(device))
            SizedBox(
              width: double.infinity,
              child: ElevatedButton.icon(
                onPressed: () {
                  if (isConnected) {
                    controller.disconnectDevice(device);
                  } else {
                    controller.connectDevice(device);
                  }
                },
                icon: Icon(isConnected ? Icons.link_off : Icons.link),
                label: Text(
                  isConnected ? '断开连接' : '连接设备',
                  style: const TextStyle(
                    fontSize: 16,
                    fontWeight: FontWeight.w600,
                  ),
                ),
                style: ElevatedButton.styleFrom(
                  backgroundColor: isConnected
                      ? const Color(0xFFFF6B6B)
                      : const Color(0xFF4A90E2),
                  foregroundColor: Colors.white,
                  padding: const EdgeInsets.symmetric(vertical: 16),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12),
                  ),
                  elevation: 0,
                ),
              ),
            )
          else
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: Colors.orange.shade50,
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: Colors.orange.shade200),
              ),
              child: Row(
                children: [
                  Icon(
                    Icons.info_outline,
                    color: Colors.orange.shade600,
                    size: 20,
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Text(
                      '此设备不支持连接，仅广播数据',
                      style: TextStyle(
                        color: Colors.orange.shade800,
                        fontSize: 14,
                        fontWeight: FontWeight.w500,
                      ),
                    ),
                  ),
                ],
              ),
            ),
        ],
      ),
    );
  }

  Widget _buildDataRow(String label, String value) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 80,
            child: Text(
              '$label:',
              style: TextStyle(
                fontSize: 14,
                color: Colors.grey.shade600,
              ),
            ),
          ),
          Expanded(
            child: Text(
              value,
              style: const TextStyle(
                fontSize: 14,
                fontWeight: FontWeight.w500,
              ),
            ),
          ),
        ],
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
    } else {
      return Icons.bluetooth;
    }
  }

  Future<void> _shareDeviceInfo(
    BuildContext context,
    BleController controller,
  ) async {
    final deviceInfo = '''
设备名称: ${controller.getDeviceName(device)}
设备ID: ${controller.getDeviceId(device)}
信号强度: ${controller.getDeviceRssi(device)} dBm
可连接: ${controller.isConnectable(device) ? '是' : '否'}
服务数量: ${controller.getServiceUuids(device).length}

打开 Trace: ${ShareLinks.landingPageUrl}
''';

    try {
      final result = await SharePlus.instance.share(
        ShareParams(
          title: '设备信息',
          subject: '设备信息',
          text: deviceInfo,
          sharePositionOrigin: _sharePositionOrigin(context),
        ),
      );
      if (result.status == ShareResultStatus.unavailable) {
        await _copyDeviceInfo(deviceInfo);
      }
    } catch (_) {
      await _copyDeviceInfo(deviceInfo);
    }
  }

  Future<void> _copyDeviceInfo(String deviceInfo) async {
    await Clipboard.setData(ClipboardData(text: deviceInfo));
    Get.snackbar('提示', '设备信息已复制到剪贴板', snackPosition: SnackPosition.BOTTOM);
  }

  Rect? _sharePositionOrigin(BuildContext context) {
    final renderObject = context.findRenderObject();
    if (renderObject is! RenderBox || !renderObject.hasSize) return null;
    return renderObject.localToGlobal(Offset.zero) & renderObject.size;
  }

  Widget _buildRawAdvertisementDataCard(ScanResult scanResult) {
    final parsedAdTypes = _parseAllAdvertisementData(scanResult);

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(20),
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
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: const Color(0xFF673AB7).withOpacity(0.1),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: const Icon(
                  Icons.data_object,
                  color: Color(0xFF673AB7),
                  size: 20,
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Text(
                  '完整广播包数据',
                  style: TextStyle(
                    fontSize: 16,
                    fontWeight: FontWeight.w600,
                    color: Colors.grey.shade800,
                  ),
                ),
              ),
              IconButton(
                onPressed: () => _copyRawData(scanResult),
                icon: const Icon(Icons.copy),
                iconSize: 16,
                color: Colors.grey.shade600,
              ),
            ],
          ),
          const SizedBox(height: 16),

          // 显示解析出的所有AD类型数据
          if (parsedAdTypes.isNotEmpty) ...[
            Text(
              '广播数据类型解析:',
              style: TextStyle(
                fontSize: 14,
                fontWeight: FontWeight.w600,
                color: Colors.grey.shade700,
              ),
            ),
            const SizedBox(height: 8),
            ...parsedAdTypes.map((adType) => _buildAdTypeItem(adType)),
          ] else ...[
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: Colors.grey.shade50,
                borderRadius: BorderRadius.circular(8),
                border: Border.all(color: Colors.grey.shade200),
              ),
              child: Row(
                children: [
                  Icon(
                    Icons.info_outline,
                    color: Colors.grey.shade500,
                    size: 20,
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Text(
                      '暂无可解析的广播数据',
                      style: TextStyle(
                        fontSize: 14,
                        color: Colors.grey.shade600,
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ],

          // 原始数据显示（保留原有功能）
          const SizedBox(height: 16),
          Text(
            '原始数据:',
            style: TextStyle(
              fontSize: 14,
              fontWeight: FontWeight.w600,
              color: Colors.grey.shade700,
            ),
          ),
          const SizedBox(height: 8),

          // 设备名称
          if (scanResult.advertisementData.advName.isNotEmpty)
            _buildRawDataItem('设备名称', scanResult.advertisementData.advName),

          // 发射功率
          if (scanResult.advertisementData.txPowerLevel != null)
            _buildRawDataItem(
                '发射功率', '${scanResult.advertisementData.txPowerLevel} dBm'),

          // 厂商数据
          if (scanResult.advertisementData.manufacturerData.isNotEmpty) ...[
            const SizedBox(height: 12),
            Text(
              '厂商数据 (0xFF):',
              style: TextStyle(
                fontSize: 12,
                fontWeight: FontWeight.w600,
                color: Colors.grey.shade600,
              ),
            ),
            const SizedBox(height: 8),
            ...scanResult.advertisementData.manufacturerData.entries.map(
              (entry) => Container(
                margin: const EdgeInsets.only(bottom: 8),
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: Colors.grey.shade50,
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: Colors.grey.shade200),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Text(
                          'Company ID: 0x${entry.key.toRadixString(16).padLeft(4, '0').toUpperCase()}',
                          style: const TextStyle(
                            fontSize: 12,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                        const Spacer(),
                        Container(
                          padding: const EdgeInsets.symmetric(
                              horizontal: 6, vertical: 2),
                          decoration: BoxDecoration(
                            color: _checkDataFormat(entry.value)
                                ? Colors.green.shade100
                                : Colors.red.shade100,
                            borderRadius: BorderRadius.circular(4),
                          ),
                          child: Text(
                            _checkDataFormat(entry.value) ? '格式正确' : '格式错误',
                            style: TextStyle(
                              fontSize: 10,
                              fontWeight: FontWeight.w600,
                              color: _checkDataFormat(entry.value)
                                  ? Colors.green.shade700
                                  : Colors.red.shade700,
                            ),
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 8),
                    Text(
                      'Hex: ${entry.value.map((b) => b.toRadixString(16).padLeft(2, '0').toUpperCase()).join(' ')}',
                      style: const TextStyle(
                        fontSize: 11,
                        fontFamily: 'monospace',
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      'Dec: [${entry.value.join(', ')}]',
                      style: TextStyle(
                        fontSize: 11,
                        color: Colors.grey.shade600,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      'Length: ${entry.value.length} bytes',
                      style: TextStyle(
                        fontSize: 11,
                        color: Colors.grey.shade600,
                      ),
                    ),
                    if (!_checkDataFormat(entry.value)) ...[
                      const SizedBox(height: 8),
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
                              Icons.warning,
                              color: Colors.red.shade600,
                              size: 16,
                            ),
                            const SizedBox(width: 8),
                            Expanded(
                              child: Text(
                                _getFormatErrorMessage(entry.value),
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
                  ],
                ),
              ),
            ),
          ],

          // 服务数据
          if (scanResult.advertisementData.serviceData.isNotEmpty) ...[
            const SizedBox(height: 12),
            Text(
              '服务数据:',
              style: TextStyle(
                fontSize: 12,
                fontWeight: FontWeight.w600,
                color: Colors.grey.shade600,
              ),
            ),
            const SizedBox(height: 8),
            ...scanResult.advertisementData.serviceData.entries.map(
              (entry) => Container(
                margin: const EdgeInsets.only(bottom: 8),
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: Colors.blue.shade50,
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: Colors.blue.shade200),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Service UUID: ${entry.key.toString()}',
                      style: const TextStyle(
                        fontSize: 12,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      'Data: ${entry.value.map((b) => b.toRadixString(16).padLeft(2, '0').toUpperCase()).join(' ')}',
                      style: const TextStyle(
                        fontSize: 11,
                        fontFamily: 'monospace',
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ],

          // 服务UUID列表
          if (scanResult.advertisementData.serviceUuids.isNotEmpty) ...[
            const SizedBox(height: 12),
            Text(
              '广播服务UUID:',
              style: TextStyle(
                fontSize: 12,
                fontWeight: FontWeight.w600,
                color: Colors.grey.shade600,
              ),
            ),
            const SizedBox(height: 8),
            Wrap(
              spacing: 8,
              runSpacing: 4,
              children: scanResult.advertisementData.serviceUuids
                  .map(
                    (uuid) => Container(
                      padding: const EdgeInsets.symmetric(
                          horizontal: 8, vertical: 4),
                      decoration: BoxDecoration(
                        color: Colors.blue.shade100,
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: Text(
                        uuid.toString(),
                        style: TextStyle(
                          fontSize: 10,
                          fontWeight: FontWeight.w500,
                          color: Colors.blue.shade700,
                        ),
                      ),
                    ),
                  )
                  .toList(),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildRawDataItem(String label, String value) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 80,
            child: Text(
              '$label:',
              style: TextStyle(
                fontSize: 12,
                color: Colors.grey.shade600,
                fontWeight: FontWeight.w500,
              ),
            ),
          ),
          Expanded(
            child: Text(
              value,
              style: const TextStyle(
                fontSize: 12,
                fontWeight: FontWeight.w500,
              ),
            ),
          ),
        ],
      ),
    );
  }

  bool _checkDataFormat(List<int> data) {
    // 检查是否符合指定格式：至少7字节，前3 4字节电流，第5字节单位，第6-7字节电压
    if (Platform.isWindows) {
      if (data.length < 7) return false;

      // 检查电流单位是否有效
      final currentUnit = data[4];
      return currentUnit == 1 ||
          currentUnit == 10 ||
          currentUnit == 50 ||
          currentUnit == 100;
    } else {
      if (data.length < 5) return false;

      // 检查电流单位是否有效
      final currentUnit = data[2];
      return currentUnit == 1 ||
          currentUnit == 10 ||
          currentUnit == 50 ||
          currentUnit == 100;
    }
  }

  String _getFormatErrorMessage(List<int> data) {
    if (Platform.isWindows) {
      if (data.length < 7) {
        return '数据长度不足：需要至少7字节，当前${data.length}字节';
      }

      final currentUnit = data[4];
      if (currentUnit != 1 &&
          currentUnit != 10 &&
          currentUnit != 50 &&
          currentUnit != 100) {
        return '电流单位无效：第5字节应为1(nA)、10(uA)、50(mA)或100(A)，当前为$currentUnit';
      }

      return '数据格式错误';
    } else {
      if (data.length < 5) {
        return '数据长度不足：需要至少5字节，当前${data.length}字节';
      }

      final currentUnit = data[2];
      if (currentUnit != 1 &&
          currentUnit != 10 &&
          currentUnit != 50 &&
          currentUnit != 100) {
        return '电流单位无效：第3字节应为1(nA)、10(uA)、50(mA)或100(A)，当前为$currentUnit';
      }

      return '数据格式错误';
    }
  }

  // Parse all advertisement data types
  List<AdTypeData> _parseAllAdvertisementData(ScanResult scanResult) {
    List<AdTypeData> adTypes = [];
    final advData = scanResult.advertisementData;

    // 0x01 - Flags
    final flags = <String>[];
    if (advData.connectable) flags.add('可连接');
    if (flags.isNotEmpty) {
      adTypes.add(AdTypeData(
        type: 0x01,
        typeName: 'Flags',
        description: 'BLE标志位: ${flags.join(', ')}',
        data: [advData.connectable ? 0x06 : 0x04], // Approximate flags
        hexData: advData.connectable ? '06' : '04',
        color: Colors.green,
      ));
    }

    // 0x02/0x03 - Service UUIDs (16-bit incomplete/complete)
    if (advData.serviceUuids.isNotEmpty) {
      final shortUuids = advData.serviceUuids
          .where((uuid) => uuid.toString().length <= 8)
          .toList();
      if (shortUuids.isNotEmpty) {
        final uuidData = <int>[];
        for (var uuid in shortUuids) {
          final uuidStr = uuid.toString().replaceAll('-', '').substring(0, 4);
          final bytes = int.parse(uuidStr, radix: 16);
          uuidData.add(bytes & 0xFF);
          uuidData.add((bytes >> 8) & 0xFF);
        }
        adTypes.add(AdTypeData(
          type: 0x03,
          typeName: 'Complete List of 16-bit Service UUIDs',
          description:
              '16位服务UUID列表: ${shortUuids.map((u) => u.toString().split('-')[0]).join(', ')}',
          data: uuidData,
          hexData: uuidData
              .map((b) => b.toRadixString(16).padLeft(2, '0').toUpperCase())
              .join(' '),
          color: Colors.blue,
        ));
      }
    }

    // 0x08/0x09 - Local Name (shortened/complete)
    if (advData.advName.isNotEmpty) {
      final nameBytes = advData.advName.codeUnits;
      adTypes.add(AdTypeData(
        type: 0x09,
        typeName: 'Complete Local Name',
        description: '完整本地名称: ${advData.advName}',
        data: nameBytes,
        hexData: nameBytes
            .map((b) => b.toRadixString(16).padLeft(2, '0').toUpperCase())
            .join(' '),
        color: Colors.orange,
      ));
    }

    // 0x0A - TX Power Level
    if (advData.txPowerLevel != null) {
      final powerByte = advData.txPowerLevel! >= 0
          ? advData.txPowerLevel!
          : 256 + advData.txPowerLevel!;
      adTypes.add(AdTypeData(
        type: 0x0A,
        typeName: 'TX Power Level',
        description: '发射功率等级: ${advData.txPowerLevel} dBm',
        data: [powerByte],
        hexData: powerByte.toRadixString(16).padLeft(2, '0').toUpperCase(),
        color: Colors.purple,
      ));
    }

    // 0x16 - Service Data (16-bit UUID)
    if (advData.serviceData.isNotEmpty) {
      for (var entry in advData.serviceData.entries) {
        final uuid = entry.key.toString();
        final serviceData = entry.value;
        adTypes.add(AdTypeData(
          type: 0x16,
          typeName: 'Service Data - 16-bit UUID',
          description: '服务数据 (UUID: ${uuid.split('-')[0]})',
          data: serviceData,
          hexData: serviceData
              .map((b) => b.toRadixString(16).padLeft(2, '0').toUpperCase())
              .join(' '),
          color: Colors.teal,
        ));
      }
    }

    // 0xFF - Manufacturer Specific Data
    if (advData.manufacturerData.isNotEmpty) {
      for (var entry in advData.manufacturerData.entries) {
        final companyId = entry.key;
        final manufData = entry.value;
        adTypes.add(AdTypeData(
          type: 0xFF,
          typeName: 'Manufacturer Specific Data',
          description:
              '厂商数据 (Company ID: 0x${companyId.toRadixString(16).padLeft(4, '0').toUpperCase()})',
          data: manufData,
          hexData: manufData
              .map((b) => b.toRadixString(16).padLeft(2, '0').toUpperCase())
              .join(' '),
          color: Colors.red,
        ));
      }
    }

    return adTypes;
  }

  Widget _buildAdTypeItem(AdTypeData adType) {
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: adType.color.withOpacity(0.1),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: adType.color.withOpacity(0.3)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                decoration: BoxDecoration(
                  color: adType.color,
                  borderRadius: BorderRadius.circular(4),
                ),
                child: Text(
                  '0x${adType.type.toRadixString(16).padLeft(2, '0').toUpperCase()}',
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 10,
                    fontWeight: FontWeight.bold,
                    fontFamily: 'monospace',
                  ),
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  adType.typeName,
                  style: TextStyle(
                    fontSize: 12,
                    fontWeight: FontWeight.w600,
                    color: adType.color.withOpacity(0.8),
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          Text(
            adType.description,
            style: const TextStyle(
              fontSize: 12,
              fontWeight: FontWeight.w500,
            ),
          ),
          if (adType.data.isNotEmpty) ...[
            const SizedBox(height: 6),
            Text(
              'Hex: ${adType.hexData}',
              style: const TextStyle(
                fontSize: 11,
                fontFamily: 'monospace',
                color: Colors.black87,
              ),
            ),
            const SizedBox(height: 2),
            Text(
              'Dec: [${adType.data.join(', ')}] (${adType.data.length} bytes)',
              style: TextStyle(
                fontSize: 11,
                color: Colors.grey.shade600,
              ),
            ),
          ],
        ],
      ),
    );
  }

  void _copyRawData(ScanResult scanResult) {
    final buffer = StringBuffer();
    buffer.writeln('=== 设备广播包完整数据 ===');
    buffer.writeln('设备名称: ${scanResult.device.platformName}');
    buffer.writeln('设备ID: ${scanResult.device.remoteId}');
    buffer.writeln('RSSI: ${scanResult.rssi} dBm');
    buffer.writeln('');

    if (scanResult.advertisementData.advName.isNotEmpty) {
      buffer.writeln('广播名称: ${scanResult.advertisementData.advName}');
    }

    if (scanResult.advertisementData.txPowerLevel != null) {
      buffer.writeln('发射功率: ${scanResult.advertisementData.txPowerLevel} dBm');
    }

    buffer.writeln(
        '可连接: ${scanResult.advertisementData.connectable ? '是' : '否'}');
    buffer.writeln('');

    if (scanResult.advertisementData.manufacturerData.isNotEmpty) {
      buffer.writeln('厂商数据:');
      for (var entry in scanResult.advertisementData.manufacturerData.entries) {
        buffer.writeln(
            '  Company ID: 0x${entry.key.toRadixString(16).padLeft(4, '0').toUpperCase()}');
        buffer.writeln(
            '  Hex: ${entry.value.map((b) => b.toRadixString(16).padLeft(2, '0').toUpperCase()).join(' ')}');
        buffer.writeln('  Dec: [${entry.value.join(', ')}]');
        buffer.writeln('  Length: ${entry.value.length} bytes');
        buffer.writeln(
            '  格式检查: ${_checkDataFormat(entry.value) ? '正确' : '错误 - ${_getFormatErrorMessage(entry.value)}'}');
        buffer.writeln('');
      }
    }

    if (scanResult.advertisementData.serviceData.isNotEmpty) {
      buffer.writeln('服务数据:');
      for (var entry in scanResult.advertisementData.serviceData.entries) {
        buffer.writeln('  Service UUID: ${entry.key}');
        buffer.writeln(
            '  Data: ${entry.value.map((b) => b.toRadixString(16).padLeft(2, '0').toUpperCase()).join(' ')}');
      }
      buffer.writeln('');
    }

    if (scanResult.advertisementData.serviceUuids.isNotEmpty) {
      buffer.writeln('服务UUID列表:');
      for (var uuid in scanResult.advertisementData.serviceUuids) {
        buffer.writeln('  ${uuid}');
      }
    }

    Clipboard.setData(ClipboardData(text: buffer.toString()));
    Get.snackbar('提示', '完整广播包数据已复制到剪贴板', snackPosition: SnackPosition.BOTTOM);
  }
}
