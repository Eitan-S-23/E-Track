import 'package:flutter/material.dart';
import 'package:flutter_blue_plus/flutter_blue_plus.dart';
import 'package:get/get.dart';
import 'package:flutter_animate/flutter_animate.dart';
import '../services/ota_service.dart';

class OtaUpgradePage extends StatefulWidget {
  final BluetoothDevice? connectedDevice;

  const OtaUpgradePage({Key? key, this.connectedDevice}) : super(key: key);

  @override
  State<OtaUpgradePage> createState() => _OtaUpgradePageState();
}

class _OtaUpgradePageState extends State<OtaUpgradePage> {
  OtaService get otaService => Get.put(OtaService(), permanent: true);

  Map<String, dynamic>? _firmwareInfo;
  bool _isChecking = false;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF8F9FA),
      appBar: AppBar(
        title: const Text(
          '码表固件',
          style: TextStyle(
            fontSize: 20,
            fontWeight: FontWeight.w600,
            color: Color(0xFF2E3A59),
          ),
        ),
        backgroundColor: Colors.white,
        foregroundColor: const Color(0xFF2E3A59),
        elevation: 0,
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // 连接状态卡片
            _buildConnectionStatusCard()
                .animate()
                .fadeIn(duration: 600.ms)
                .slideY(begin: 0.3, end: 0),

            const SizedBox(height: 24),

            // 检查更新按钮
            _buildCheckUpdateButton()
                .animate(delay: 200.ms)
                .fadeIn(duration: 600.ms)
                .slideY(begin: 0.3, end: 0),

            const SizedBox(height: 24),

            // 固件信息
            if (_firmwareInfo != null)
              _buildFirmwareInfoCard().animate().fadeIn(duration: 600.ms).scale(
                  begin: const Offset(0.8, 0.8), end: const Offset(1, 1)),

            const SizedBox(height: 24),

            // 升级进度
            Obx(() => _buildUpgradeProgressCard())
                .animate(delay: 400.ms)
                .fadeIn(duration: 600.ms)
                .slideY(begin: 0.3, end: 0),

            const SizedBox(height: 24),

            // 升级历史
            _buildUpgradeHistoryCard()
                .animate(delay: 600.ms)
                .fadeIn(duration: 600.ms)
                .slideY(begin: 0.3, end: 0),
          ],
        ),
      ),
    );
  }

  Widget _buildConnectionStatusCard() {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: widget.connectedDevice != null
              ? [const Color(0xFF4CAF50), const Color(0xFF2E7D32)]
              : [const Color(0xFF8E8E93), const Color(0xFF636366)],
        ),
        borderRadius: BorderRadius.circular(16),
        boxShadow: [
          BoxShadow(
            color: (widget.connectedDevice != null
                    ? const Color(0xFF4CAF50)
                    : Colors.grey)
                .withOpacity(0.3),
            blurRadius: 12,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: Column(
        children: [
          Icon(
            widget.connectedDevice != null
                ? Icons.bluetooth_connected
                : Icons.bluetooth_disabled,
            size: 48,
            color: Colors.white,
          ),
          const SizedBox(height: 16),
          Text(
            widget.connectedDevice != null ? '设备已连接' : '未连接设备',
            style: const TextStyle(
              fontSize: 18,
              fontWeight: FontWeight.w600,
              color: Colors.white,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            widget.connectedDevice?.platformName ?? '未连接设备时也可先下载固件',
            style: const TextStyle(
              fontSize: 14,
              color: Colors.white70,
            ),
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 16),
          Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Container(
                padding:
                    const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                decoration: BoxDecoration(
                  color: Colors.white.withOpacity(0.2),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(
                      otaService.isFirmwareServiceConfigured
                          ? Icons.cloud_done
                          : Icons.cloud_off,
                      size: 16,
                      color: Colors.white,
                    ),
                    const SizedBox(width: 8),
                    Text(
                      otaService.isFirmwareServiceConfigured
                          ? '固件服务可用'
                          : '固件服务未配置',
                      style: const TextStyle(
                        fontSize: 12,
                        color: Colors.white,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildCheckUpdateButton() {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.05),
            blurRadius: 8,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Column(
        children: [
          const Icon(
            Icons.system_update,
            size: 48,
            color: Color(0xFF4A90E2),
          ),
          const SizedBox(height: 16),
          const Text(
            '检查固件更新',
            style: TextStyle(
              fontSize: 18,
              fontWeight: FontWeight.w600,
              color: Color(0xFF2E3A59),
            ),
          ),
          const SizedBox(height: 8),
          const Text(
            '检查并下载最新单片机固件',
            style: TextStyle(
              fontSize: 14,
              color: Colors.grey,
            ),
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 20),
          ElevatedButton.icon(
            onPressed: !_isChecking && otaService.isFirmwareServiceConfigured
                ? _checkForUpdate
                : null,
            icon: _isChecking
                ? const SizedBox(
                    width: 16,
                    height: 16,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Icon(Icons.search),
            label: Text(_isChecking ? '检查中...' : '检查更新'),
            style: ElevatedButton.styleFrom(
              backgroundColor: const Color(0xFF4A90E2),
              foregroundColor: Colors.white,
              padding: const EdgeInsets.symmetric(horizontal: 32, vertical: 12),
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(8),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildFirmwareInfoCard() {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: const Color(0xFF4A90E2).withOpacity(0.2)),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.05),
            blurRadius: 8,
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
                  Icons.new_releases,
                  color: Color(0xFF4A90E2),
                  size: 24,
                ),
              ),
              const SizedBox(width: 12),
              const Text(
                '发现新版本',
                style: TextStyle(
                  fontSize: 18,
                  fontWeight: FontWeight.w600,
                  color: Color(0xFF2E3A59),
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          _buildInfoRow('版本号', '${_firmwareInfo!['version'] ?? '--'}'),
          const SizedBox(height: 12),
          _buildInfoRow('文件大小', _formatBytes(_firmwareInfo!['fileSizeBytes'])),
          const SizedBox(height: 12),
          _buildInfoRow('SHA-256', '${_firmwareInfo!['sha256'] ?? '--'}'),
          const SizedBox(height: 12),
          _buildDescriptionSection('更新说明', '${_firmwareInfo!['description'] ?? ''}'),
          const SizedBox(height: 20),
          Row(
            children: [
              Expanded(
                child: OutlinedButton(
                  onPressed: () {
                    setState(() {
                      _firmwareInfo = null;
                    });
                  },
                  style: OutlinedButton.styleFrom(
                    foregroundColor: Colors.grey,
                    side: BorderSide(color: Colors.grey.shade300),
                  ),
                  child: const Text('取消'),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: ElevatedButton(
                  onPressed: _downloadFirmware,
                  style: ElevatedButton.styleFrom(
                    backgroundColor: const Color(0xFF4A90E2),
                    foregroundColor: Colors.white,
                  ),
                  child: const Text('下载固件'),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildInfoRow(String label, String value) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SizedBox(
          width: 80,
          child: Text(
            label,
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
              color: Color(0xFF2E3A59),
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildDescriptionSection(String label, String description) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          label,
          style: TextStyle(
            fontSize: 14,
            color: Colors.grey.shade600,
          ),
        ),
        const SizedBox(height: 8),
        Container(
          width: double.infinity,
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(
            color: const Color(0xFF4A90E2).withOpacity(0.05),
            borderRadius: BorderRadius.circular(8),
            border: Border.all(
              color: const Color(0xFF4A90E2).withOpacity(0.1),
            ),
          ),
          child: Text(
            description,
            style: const TextStyle(
              fontSize: 14,
              color: Color(0xFF2E3A59),
              height: 1.4,
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildUpgradeProgressCard() {
    if (!otaService.isUpgrading && otaService.upgradeProgress == 0) {
      return const SizedBox.shrink();
    }

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.05),
            blurRadius: 8,
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
                  Icons.download,
                  color: Color(0xFF4A90E2),
                  size: 24,
                ),
              ),
              const SizedBox(width: 12),
              const Text(
                '下载进度',
                style: TextStyle(
                  fontSize: 18,
                  fontWeight: FontWeight.w600,
                  color: Color(0xFF2E3A59),
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          Text(
            otaService.upgradeStatus,
            style: const TextStyle(
              fontSize: 14,
              color: Color(0xFF2E3A59),
            ),
          ),
          const SizedBox(height: 12),
          ClipRRect(
            borderRadius: BorderRadius.circular(4),
            child: LinearProgressIndicator(
              value: otaService.upgradeProgress,
              backgroundColor: Colors.grey.shade200,
              valueColor:
                  const AlwaysStoppedAnimation<Color>(Color(0xFF4A90E2)),
              minHeight: 8,
            ),
          ).animate().scaleX(duration: 300.ms),
          const SizedBox(height: 8),
          Text(
            '${(otaService.upgradeProgress * 100).toStringAsFixed(1)}%',
            style: const TextStyle(
              fontSize: 12,
              color: Colors.grey,
            ),
          ),
          if (otaService.isUpgrading) ...[
            const SizedBox(height: 16),
            SizedBox(
              width: double.infinity,
              child: OutlinedButton(
                onPressed: () {
                  _showCancelDialog();
                },
                style: OutlinedButton.styleFrom(
                  foregroundColor: Colors.red,
                  side: const BorderSide(color: Colors.red),
                ),
                child: const Text('取消下载'),
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildUpgradeHistoryCard() {
    final history = otaService.getUpgradeHistory();

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.05),
            blurRadius: 8,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            '升级历史',
            style: TextStyle(
              fontSize: 18,
              fontWeight: FontWeight.w600,
              color: Color(0xFF2E3A59),
            ),
          ),
          const SizedBox(height: 16),
          if (history.isEmpty)
            const Text(
              '暂无升级记录',
              style: TextStyle(
                fontSize: 14,
                color: Colors.grey,
              ),
            )
          else
            ...history.map((record) => _buildHistoryItem(record)).toList(),
        ],
      ),
    );
  }

  Widget _buildHistoryItem(Map<String, dynamic> record) {
    final isSuccess = record['status'] == 'success';

    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Colors.grey.shade50,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: Colors.grey.shade200),
      ),
      child: Row(
        children: [
          Icon(
            isSuccess ? Icons.check_circle : Icons.error,
            color: isSuccess ? Colors.green : Colors.red,
            size: 20,
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  record['device'],
                  style: const TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.w500,
                  ),
                ),
                Text(
                  '版本 ${record['version']} • ${_formatDate(record['date'])}',
                  style: TextStyle(
                    fontSize: 12,
                    color: Colors.grey.shade600,
                  ),
                ),
              ],
            ),
          ),
          Text(
            isSuccess ? '成功' : '失败',
            style: TextStyle(
              fontSize: 12,
              color: isSuccess ? Colors.green : Colors.red,
              fontWeight: FontWeight.w500,
            ),
          ),
        ],
      ),
    );
  }

  void _checkForUpdate() async {
    setState(() {
      _isChecking = true;
    });

    try {
      // TODO: replace with values read from the connected code table once the
      // device firmware protocol is finalized.
      const deviceModel = 'igpsport-bsc300';
      const currentVersion = '0.0.0';

      final firmwareInfo = await otaService.checkFirmwareUpdate(
        deviceModel,
        currentVersion,
      );

      setState(() {
        _firmwareInfo = firmwareInfo;
        _isChecking = false;
      });
    } catch (e) {
      setState(() {
        _isChecking = false;
      });
      Get.snackbar('错误', '检查更新失败: $e',
          backgroundColor: Colors.red.withOpacity(0.1),
          colorText: Colors.red.shade700,
          snackPosition: SnackPosition.TOP,
          icon: const Icon(Icons.error_outline, color: Colors.red));
    }
  }

  void _downloadFirmware() async {
    final downloadSuccess = await otaService.downloadFirmware();
    if (!downloadSuccess) return;

    setState(() {
      _firmwareInfo = null;
    });
    Get.snackbar('成功', '固件已下载，BLE分包传输功能待实现',
        backgroundColor: Colors.green.withOpacity(0.1),
        colorText: Colors.green.shade700,
        snackPosition: SnackPosition.TOP,
        icon: const Icon(Icons.check_circle, color: Colors.green));
  }

  void _showCancelDialog() {
    Get.dialog(
      AlertDialog(
        title: const Text('取消下载'),
        content: const Text('确定要取消当前的下载过程吗？'),
        actions: [
          TextButton(
            onPressed: () => Get.back(),
            child: const Text('继续下载'),
          ),
          ElevatedButton(
            onPressed: () {
              Get.back();
              otaService.cancelUpgrade();
            },
            style: ElevatedButton.styleFrom(
              backgroundColor: Colors.red,
              foregroundColor: Colors.white,
            ),
            child: const Text('取消下载'),
          ),
        ],
      ),
    );
  }

  String _formatBytes(Object? value) {
    final bytes = value is int
        ? value
        : value is num
            ? value.toInt()
            : int.tryParse('${value ?? ''}') ?? 0;
    if (bytes <= 0) return '--';
    if (bytes < 1024) return '$bytes B';
    final kb = bytes / 1024;
    if (kb < 1024) return '${kb.toStringAsFixed(1)} KB';
    return '${(kb / 1024).toStringAsFixed(2)} MB';
  }

  String _formatDate(DateTime date) {
    return '${date.month}月${date.day}日';
  }
}
