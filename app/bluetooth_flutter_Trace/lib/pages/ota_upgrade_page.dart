import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_blue_plus/flutter_blue_plus.dart';
import 'package:get/get.dart';
import 'package:flutter_animate/flutter_animate.dart';
import '../ota/ota_firmware_latest.dart';
import '../services/ota_service.dart';

/// OTA 固件升级页。
///
/// 数据流（P3-3，PR16：UI 由 [OtaPhase] 驱动，不解析状态文本）：
/// - 进入页面即解析连接设备（显式传入优先，否则从已连接列表解析）并
///   GET_INFO 建立设备身份；
/// - 检查更新：latest schema v2 → 发现新版本卡片；
/// - 下载：HTTP 进度条（sidecar/断点续传由服务层处理）；
/// - 传输：MCU durable 进度条（ACK 唯一真相）；
/// - END ACK 后：等待重启 → 重连复核 → 完成卡片（目标版本）；
/// - 终止态（CLIENT_TOO_OLD/兼容 409/未知设备）：明确提示且不提供盲目重试。
class OtaUpgradePage extends StatefulWidget {
  final BluetoothDevice? connectedDevice;

  const OtaUpgradePage({Key? key, this.connectedDevice}) : super(key: key);

  @override
  State<OtaUpgradePage> createState() => _OtaUpgradePageState();
}

class _OtaUpgradePageState extends State<OtaUpgradePage>
    with WidgetsBindingObserver {
  /// 已注册时直接复用：避免每次 build 都构造一个被 GetX 丢弃的
  /// OtaService/Dio 实例。
  OtaService get otaService => Get.isRegistered<OtaService>()
      ? Get.find<OtaService>()
      : Get.put(OtaService(), permanent: true);

  bool _isChecking = false;
  /// 自动解析出的已连接设备（无显式 connectedDevice 参数时，
  /// PR18：speedometer 等入口 `Get.to(OtaUpgradePage())` 不传参）。
  BluetoothDevice? _resolvedDevice;
  bool _resolveAttempted = false;
  /// 连接状态变化订阅（RC3-08④）：不再一次性解析连接列表，目标断连
  /// 即失效解析结果，空闲时新设备连入即时解析。
  /// RC3-01：flutter_blue_plus 1.35.5 的实际事件 API 是
  /// `FlutterBluePlus.events.onConnectionStateChanged`（返回
  /// `Stream<OnConnectionStateChangedEvent>`），不存在顶层
  /// `FlutterBluePlus.connectionStateChanged`。
  StreamSubscription<OnConnectionStateChangedEvent>? _connectionSub;
  /// App 生命周期后台标记（RC3-08④）：后台期间停止主动发起身份读取
  /// 等 GATT 操作，回前台后重新发现连接并读身份。
  bool _backgrounded = false;

  /// 当前连接设备地址（GET_INFO/传输的入口；无连接则为 null）。
  String? get _deviceAddress =>
      (widget.connectedDevice ?? _resolvedDevice)?.remoteId.str.toLowerCase();

  bool get _deviceReady =>
      _deviceAddress != null && otaService.deviceInfo != null;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _listenConnectionChanges();
    // 进入页面即解析连接并建立设备身份。
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _resolveDeviceAndRead();
    });
  }

  @override
  void didUpdateWidget(covariant OtaUpgradePage oldWidget) {
    super.didUpdateWidget(oldWidget);
    // 显式设备参数变化（RC3-08④）：旧解析结果与设备身份快照（DTO 按
    // 地址绑定，由 service 层失效）不再适用于新目标，重新解析并读取。
    if (widget.connectedDevice != oldWidget.connectedDevice) {
      _resolveAttempted = false;
      _resolveDeviceAndRead();
    }
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.paused ||
        state == AppLifecycleState.inactive) {
      _backgrounded = true;
      // RC3-08：后台暂停传输发送循环（DATA/END 停发，无进展预算
      // 停表）——后台继续发帧会与系统资源回收竞争；暂停超过 MCU
      // 会话超时窗口时 MCU 可能回 ACK_ABORT（协议行为），回前台后
      // 可整体重试（BEGIN 幂等 + durable 续传）。
      otaService.pauseForBackground();
    } else if (state == AppLifecycleState.resumed && _backgrounded) {
      _backgrounded = false;
      // RC3-08：回前台恢复传输发送循环与预算计时。
      otaService.resumeFromBackground();
      // 回前台重新解析连接并读身份：后台期间连接可能已变化。
      _resolveAttempted = false;
      _resolveDeviceAndRead();
    }
  }

  @override
  void dispose() {
    _connectionSub?.cancel();
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  /// 订阅系统连接状态变化（RC3-08④）。FlutterBluePlus 的
  /// events.onConnectionStateChanged 是纯 Dart 广播流，监听本身不触发
  /// 平台调用（RC3-01：1.35.5 实际 API 形态）；订阅异常（平台通道
  /// 缺失）时退化为进入页面时的一次性解析。
  void _listenConnectionChanges() {
    try {
      _connectionSub =
          FlutterBluePlus.events.onConnectionStateChanged.listen((event) {
        if (!mounted || _backgrounded) return;
        final changedAddress = event.device.remoteId.str.toLowerCase();
        final currentAddress = _deviceAddress;
        if (event.connectionState == BluetoothConnectionState.disconnected) {
          if (changedAddress == currentAddress &&
              widget.connectedDevice == null) {
            // 自动解析的目标断连：失效解析结果（显式传入设备保留参数，
            // 由调用方与 service 层 DTO 地址绑定负责失效）。
            setState(() {
              _resolvedDevice = null;
            });
          }
        } else if (event.connectionState == BluetoothConnectionState.connected &&
            currentAddress == null) {
          // 页面空闲（无目标）时有设备连入：立即解析并读取身份。
          _resolveAttempted = false;
          _resolveDeviceAndRead();
        }
      });
    } catch (_) {
      // 测试环境/平台通道不可用：保持进入页面时的一次性解析行为。
    }
  }

  /// 解析连接设备（显式参数优先，否则从系统已连接列表取第一台），
  /// 然后读取设备身份。BLE 平台通道不可用时静默降级为未连接。
  Future<void> _resolveDeviceAndRead() async {
    await _resolveConnectedDevice();
    await _readDeviceInfo();
  }

  Future<void> _resolveConnectedDevice() async {
    if (widget.connectedDevice != null) return;
    if (_resolveAttempted) return;
    _resolveAttempted = true;
    try {
      final devices = await FlutterBluePlus.connectedDevices;
      for (final device in devices) {
        if (device.isConnected) {
          if (mounted) {
            setState(() {
              _resolvedDevice = device;
            });
          }
          break;
        }
      }
    } catch (_) {
      // 平台通道不可用（测试环境/权限缺失）：保持未连接状态。
    }
  }

  Future<void> _readDeviceInfo() async {
    // 后台停写（RC3-08④）：后台期间不主动发起 GET_INFO 等 GATT
    // 操作，回前台时由生命周期回调统一重新读取。
    if (_backgrounded) return;
    await _resolveConnectedDevice();
    final address = _deviceAddress;
    if (address == null) return;
    await otaService.readDeviceInfo(address);
    if (mounted) setState(() {});
  }

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

            // 检查更新按钮（RC2-04：Obx 包裹——canCheck 依赖
            // isUpgrading/phase，忙锁变化须即时禁用/恢复按钮）。
            Obx(() => _buildCheckUpdateButton())
                .animate(delay: 200.ms)
                .fadeIn(duration: 600.ms)
                .slideY(begin: 0.3, end: 0),

            const SizedBox(height: 24),

            // 终止态提示
            Obx(() {
              final terminal = otaService.terminalState;
              if (terminal == null) return const SizedBox.shrink();
              return _buildTerminalCard(terminal);
            }),

            // 固件信息
            Obx(() {
              // phase/进度变化触发刷新（latestInfo 本身非 Rx）。
              otaService.phaseRx.value;
              final latest = otaService.latestInfo;
              if (latest == null || !latest.hasUpdate) {
                return const SizedBox.shrink();
              }
              return _buildFirmwareInfoCard(latest)
                  .animate()
                  .fadeIn(duration: 600.ms)
                  .scale(
                      begin: const Offset(0.8, 0.8),
                      end: const Offset(1, 1));
            }),

            const SizedBox(height: 24),

            // 升级进度（phase 驱动）
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
    final deviceInfo = otaService.deviceInfo;
    final connected = _deviceAddress != null;
    final identityConfirmed = deviceInfo != null;
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: identityConfirmed
              ? [const Color(0xFF4CAF50), const Color(0xFF2E7D32)]
              : connected
                  ? [const Color(0xFF4A90E2), const Color(0xFF2A6DB5)]
                  : [const Color(0xFF8E8E93), const Color(0xFF636366)],
        ),
        borderRadius: BorderRadius.circular(16),
        boxShadow: [
          BoxShadow(
            color: identityConfirmed
                ? const Color(0xFF4CAF50).withOpacity(0.3)
                : Colors.grey.withOpacity(0.3),
            blurRadius: 12,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: Column(
        children: [
          Icon(
            identityConfirmed
                ? Icons.verified
                : connected
                    ? Icons.bluetooth_connected
                    : Icons.bluetooth_disabled,
            size: 48,
            color: Colors.white,
          ),
          const SizedBox(height: 16),
          Text(
            identityConfirmed
                ? '设备身份已确认'
                : connected
                    ? '设备已连接，待确认身份'
                    : '未连接设备',
            style: const TextStyle(
              fontSize: 18,
              fontWeight: FontWeight.w600,
              color: Colors.white,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            identityConfirmed && deviceInfo != null
                ? '${deviceInfo.deviceModel} • 固件 vcode ${deviceInfo.currentVersionCode}'
                : (widget.connectedDevice ?? _resolvedDevice)?.platformName ??
                    '连接码表后自动读取设备身份',
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
    // 终止闭锁与 service 层 _terminalLocked 对齐（RC3-12③）：非
    // retryableLater 的终止态下禁用检查入口（解锁入口是重新读取设备
    // 身份，而非盲目重查）；retryableLater（如重启重连失败）仍可查。
    final terminal = otaService.terminalState;
    final terminalLocked = terminal != null && !terminal.retryableLater;
    final canCheck = !_isChecking &&
        !otaService.isUpgrading &&
        otaService.isFirmwareServiceConfigured &&
        _deviceReady &&
        !terminalLocked;
    final hint = _deviceAddress == null
        ? '连接码表后将自动读取设备身份'
        : otaService.deviceInfo == null
            ? '设备身份未确认（未识别到 OTA 服务或身份读取失败），暂不能检查更新'
            : terminalLocked
                ? '已进入终止状态（${terminal.code}），重新读取设备身份后可解锁检查'
                : '基于设备身份查询可用固件';
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
          Text(
            hint,
            style: const TextStyle(
              fontSize: 14,
              color: Colors.grey,
            ),
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 20),
          Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              ElevatedButton.icon(
                onPressed: canCheck ? _checkForUpdate : null,
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
                  padding: const EdgeInsets.symmetric(
                      horizontal: 32, vertical: 12),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(8),
                  ),
                ),
              ),
              // RC3-12③：终止闭锁但身份快照仍在时（如下载侧
              // HARDWARE_INCOMPATIBLE 闭锁），同样提供实际可执行的
              // 恢复入口——重新 GET_INFO 成功即重建查询链并解锁，
              // 不只给文字提示。
              if (_deviceAddress != null &&
                  (otaService.deviceInfo == null || terminalLocked)) ...[
                const SizedBox(width: 12),
                OutlinedButton.icon(
                  onPressed: _isChecking ? null : _readDeviceInfo,
                  icon: const Icon(Icons.refresh),
                  label: Text(terminalLocked && otaService.deviceInfo != null
                      ? '重新读取身份解锁'
                      : '重试读取'),
                  style: OutlinedButton.styleFrom(
                    foregroundColor: const Color(0xFF4A90E2),
                  ),
                ),
              ],
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildTerminalCard(OtaTerminalState terminal) {
    final retryable = terminal.retryableLater;
    return Container(
      width: double.infinity,
      margin: const EdgeInsets.only(bottom: 24),
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: retryable ? Colors.orange.shade50 : Colors.red.shade50,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(
          color: retryable
              ? Colors.orange.withOpacity(0.3)
              : Colors.red.withOpacity(0.3),
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(
                retryable ? Icons.info : Icons.block,
                color: retryable ? Colors.orange.shade700 : Colors.red.shade700,
                size: 24,
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Text(
                  retryable ? '暂不可更新' : '无法升级',
                  style: TextStyle(
                    fontSize: 16,
                    fontWeight: FontWeight.w600,
                    color: retryable
                        ? Colors.orange.shade800
                        : Colors.red.shade800,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          Text(
            terminal.userMessage,
            style: TextStyle(
              fontSize: 14,
              color: retryable
                  ? Colors.orange.shade900
                  : Colors.red.shade900,
              height: 1.4,
            ),
          ),
          if (terminal.requestId != null) ...[
            const SizedBox(height: 8),
            Text(
              'requestId: ${terminal.requestId}',
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

  Widget _buildFirmwareInfoCard(FirmwareLatestInfo latest) {
    final asset = latest.asset!;
    final canDownload =
        _deviceReady && !otaService.isUpgrading && otaService.phase != OtaPhase.readyToInstall;
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
          _buildInfoRow('版本号', latest.versionName ?? '--'),
          const SizedBox(height: 12),
          _buildInfoRow('文件大小', _formatBytes(asset.sizeBytes)),
          const SizedBox(height: 12),
          _buildInfoRow('资产类型', asset.isPatch ? '增量包' : '完整包'),
          const SizedBox(height: 12),
          _buildInfoRow('SHA-256', asset.sha256),
          const SizedBox(height: 12),
          _buildDescriptionSection(
              '更新说明', latest.releaseNotes ?? '暂无说明'),
          const SizedBox(height: 20),
          Row(
            children: [
              Expanded(
                child: OutlinedButton(
                  // 忽略 = 放弃本次更新并清理已校验固件包（RC3-12②）：
                  // await 状态转换（readyToInstall→idle 复位按钮可用性）
                  // 并区分两类失败——忙碌拒绝已由 service 层提示，此处
                  // 只对删除失败（非忙碌）补充暴露，不静默当作已清理。
                  onPressed: () async {
                    final ok = await otaService.cleanupFirmware();
                    if (!ok) {
                      if (!otaService.isUpgrading) {
                        Get.snackbar('错误', '固件包清理失败，请重试',
                            backgroundColor: Colors.red.withOpacity(0.1),
                            colorText: Colors.red.shade700,
                            snackPosition: SnackPosition.TOP,
                            icon: const Icon(Icons.error_outline,
                                color: Colors.red));
                      }
                      return;
                    }
                    if (mounted) setState(() {});
                  },
                  style: OutlinedButton.styleFrom(
                    foregroundColor: Colors.grey,
                    side: BorderSide(color: Colors.grey.shade300),
                  ),
                  child: const Text('忽略'),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: ElevatedButton(
                  onPressed: canDownload ? _downloadFirmware : null,
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

  /// 升级进度/状态卡（PR16：全部由 [OtaPhase] 驱动，不解析状态文本）。
  Widget _buildUpgradeProgressCard() {
    final phase = otaService.phase;
    final hasFirmware = otaService.downloadedFirmwareFile != null;
    final inDownload = phase == OtaPhase.downloading;
    final inTransfer =
        phase == OtaPhase.transferring ||
        phase == OtaPhase.waitingReboot ||
        phase == OtaPhase.reconnectVerify;
    if (!otaService.isUpgrading &&
        phase != OtaPhase.readyToInstall &&
        phase != OtaPhase.completed &&
        phase != OtaPhase.cancelled &&
        phase != OtaPhase.failed &&
        !hasFirmware) {
      return const SizedBox.shrink();
    }
    if (phase == OtaPhase.completed) {
      return _buildCompletedCard();
    }

    final busy = inDownload || inTransfer;
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
                child: Icon(
                  inTransfer ? Icons.bluetooth_audio : Icons.download,
                  color: const Color(0xFF4A90E2),
                  size: 24,
                ),
              ),
              const SizedBox(width: 12),
              Text(
                inTransfer
                    ? '固件传输（设备确认）'
                    : inDownload
                        ? '下载进度'
                        : '固件就绪',
                style: const TextStyle(
                  fontSize: 18,
                  fontWeight: FontWeight.w600,
                  color: Color(0xFF2E3A59),
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              if (busy) ...[
                const SizedBox(
                  width: 16,
                  height: 16,
                  child: CircularProgressIndicator(strokeWidth: 2),
                ),
                const SizedBox(width: 8),
              ],
              Expanded(
                child: Text(
                  otaService.upgradeStatus.isEmpty ? ' ' : otaService.upgradeStatus,
                  style: const TextStyle(
                    fontSize: 14,
                    color: Color(0xFF2E3A59),
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          if (inTransfer) ...[
            _buildProgressRow('设备已确认（durable）', otaService.durableProgress),
            const SizedBox(height: 8),
            _buildProgressRow('网络下载', otaService.downloadProgress),
          ] else if (phase != OtaPhase.cancelled &&
              (inDownload || otaService.downloadProgress > 0)) ...[
            // cancelled 不显示进度行：取消时 partial 已删/验证包保留，
            // 停留在取消瞬间的进度快照会误导（RC3-05①）。
            _buildProgressRow('网络下载', otaService.downloadProgress),
          ],
          if (busy) ...[
            const SizedBox(height: 16),
            SizedBox(
              width: double.infinity,
              child: OutlinedButton(
                onPressed: () {
                  _showCancelDialog(inTransfer);
                },
                style: OutlinedButton.styleFrom(
                  foregroundColor: Colors.red,
                  side: const BorderSide(color: Colors.red),
                ),
                child: Text(inTransfer ? '取消升级' : '取消下载'),
              ),
            ),
          ],
          // 已校验固件包就绪（含取消后保留的包，RC3-05①）：提供传输
          // 入口——取消下载/取消传输时选择保留的验证包可直接重新发起。
          if ((phase == OtaPhase.readyToInstall || phase == OtaPhase.cancelled) &&
              hasFirmware) ...[
            const SizedBox(height: 16),
            SizedBox(
              width: double.infinity,
              child: ElevatedButton.icon(
                onPressed:
                    _deviceReady && !otaService.isUpgrading ? _startUpgrade : null,
                icon: const Icon(Icons.bluetooth_audio),
                label: const Text('开始 BLE 传输'),
                style: ElevatedButton.styleFrom(
                  backgroundColor: const Color(0xFF4CAF50),
                  foregroundColor: Colors.white,
                ),
              ),
            ),
          ],
        ],
      ),
    );
  }

  /// 升级完成卡片：目标版本已通过重启后 GET_INFO 复核。
  Widget _buildCompletedCard() {
    final latest = otaService.latestInfo;
    final deviceInfo = otaService.deviceInfo;
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: Colors.green.shade50,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: Colors.green.withOpacity(0.3)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(
                Icons.verified,
                color: Color(0xFF2E7D32),
                size: 24,
              ),
              const SizedBox(width: 12),
              const Text(
                '固件升级完成',
                style: TextStyle(
                  fontSize: 18,
                  fontWeight: FontWeight.w600,
                  color: Color(0xFF2E7D32),
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          Text(
            '设备已重启并运行目标固件: ${latest?.versionName ?? '--'}'
            '${deviceInfo != null ? '（vcode ${deviceInfo.currentVersionCode}）' : ''}',
            style: TextStyle(
              fontSize: 14,
              color: Colors.green.shade900,
              height: 1.4,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildProgressRow(String label, double progress) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text(
              label,
              style: const TextStyle(
                fontSize: 12,
                color: Color(0xFF2E3A59),
              ),
            ),
            Text(
              '${(progress * 100).toStringAsFixed(1)}%',
              style: const TextStyle(
                fontSize: 12,
                color: Colors.grey,
              ),
            ),
          ],
        ),
        const SizedBox(height: 4),
        ClipRRect(
          borderRadius: BorderRadius.circular(4),
          child: LinearProgressIndicator(
            value: progress,
            backgroundColor: Colors.grey.shade200,
            valueColor:
                const AlwaysStoppedAnimation<Color>(Color(0xFF4A90E2)),
            minHeight: 8,
          ),
        ),
      ],
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
      await otaService.checkFirmwareUpdate();
    } catch (e) {
      Get.snackbar('错误', '检查更新失败: $e',
          backgroundColor: Colors.red.withOpacity(0.1),
          colorText: Colors.red.shade700,
          snackPosition: SnackPosition.TOP,
          icon: const Icon(Icons.error_outline, color: Colors.red));
    } finally {
      if (mounted) {
        setState(() {
          _isChecking = false;
        });
      }
    }
  }

  void _downloadFirmware() async {
    final success = await otaService.downloadFirmware();
    if (!success) return;

    Get.snackbar('成功', '固件已下载并校验，可开始 BLE 传输',
        backgroundColor: Colors.green.withOpacity(0.1),
        colorText: Colors.green.shade700,
        snackPosition: SnackPosition.TOP,
        icon: const Icon(Icons.check_circle, color: Colors.green));
    if (mounted) setState(() {});
  }

  void _startUpgrade() async {
    final address = _deviceAddress;
    if (address == null) return;
    final success = await otaService.startOtaUpgrade(address);
    if (!success) return;
    if (mounted) setState(() {});
  }

  /// 取消确认对话框（RC3-05①：冻结取消策略不在 UI 放宽）。
  ///
  /// - 未完成的下载分片（.part/sidecar）**恒删**，不提供「保留续传」
  ///   选项——partial 包未通过整包校验，续传语义由 MCU durable 层承担；
  /// - 可选择保留/删除的只有**已校验完成包**：
  ///   - BLE 传输阶段：保留（可直接重新传输）或删除（下次重新下载）；
  ///   - 下载阶段：默认保留（取消的是下载，不动已校验包；彻底放弃
  ///     走「忽略」入口删除）。
  void _showCancelDialog(bool isBlePhase) {
    Get.dialog(
      AlertDialog(
        title: Text(isBlePhase ? '取消升级' : '取消下载'),
        content: Text(isBlePhase
            ? '取消将中止 BLE 传输并尽力通知设备取消。设备已确认落盘的数据由设备保留，下次传输自动续传。已校验的固件包可选择保留（直接重新传输）或删除。'
            : '取消将停止下载，未完成的下载分片将被删除（不支持保留续传）。已校验的固件包不受影响，可稍后直接开始传输。'),
        actions: [
          TextButton(
            onPressed: () => Get.back(),
            child: const Text('继续'),
          ),
          if (isBlePhase)
            OutlinedButton(
              onPressed: () async {
                Get.back();
                // RC3-12②：等待取消完全落地（含文件删除与状态发布）后
                // 刷新 UI，按钮可用性与文件/phase 状态保持一致。
                await otaService.cancelUpgrade(keepPackage: true);
                if (mounted) setState(() {});
              },
              child: const Text('保留固件包并取消'),
            ),
          ElevatedButton(
            onPressed: () async {
              Get.back();
              // 下载阶段保留已校验包（若有）；彻底删除走「忽略」。
              // RC3-12②：等待取消完全落地后再刷新 UI。
              await otaService.cancelUpgrade(keepPackage: !isBlePhase);
              if (mounted) setState(() {});
            },
            style: ElevatedButton.styleFrom(
              backgroundColor: Colors.red,
              foregroundColor: Colors.white,
            ),
            child: Text(isBlePhase ? '取消并删除固件包' : '确认取消'),
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
