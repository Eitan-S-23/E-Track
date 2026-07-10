import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'package:get/get.dart';
import 'package:flutter_blue_plus/flutter_blue_plus.dart';
import '../controllers/ble_controller.dart';
import '../services/bluetooth_service.dart' as bt_service;
import '../services/database_service.dart';

const List<IconData> _customButtonIconChoices = <IconData>[
  Icons.lightbulb_outline,
  Icons.power_settings_new,
  Icons.campaign,
  Icons.music_note,
  Icons.flash_on,
  Icons.favorite,
  Icons.lock_open,
  Icons.doorbell,
  Icons.wifi,
  Icons.bolt,
  Icons.speaker,
  Icons.thermostat,
  Icons.directions_bike,
  Icons.toys,
  Icons.settings_remote,
  Icons.sensors,
];

IconData _customButtonIconForCode(int? codePoint) {
  if (codePoint == null) {
    return Icons.touch_app;
  }

  for (final icon in _customButtonIconChoices) {
    if (icon.codePoint == codePoint) {
      return icon;
    }
  }

  return Icons.touch_app;
}

class RemoteControlPage extends StatefulWidget {
  const RemoteControlPage({Key? key}) : super(key: key);

  @override
  State<RemoteControlPage> createState() => _RemoteControlPageState();
}

class _RemoteControlPageState extends State<RemoteControlPage> {
  final BleController _ble = Get.find<BleController>();
  final bt_service.BluetoothService _bt =
      Get.find<bt_service.BluetoothService>();

  bool isScanning = false;
  bool isConnected = false;
  String? connectedDeviceName;
  BluetoothDevice? connectedDevice;

  String? serviceIdFFF0; // 实际匹配到的服务ID
  String? writeCharId; // 实际匹配到的可写特征ID
  String? notifyCharId; // 若存在可通知特征

  final List<String> _rxLogs = <String>[]; // 旧的接收日志（保留兼容）
  final List<_RxEntry> _rxEntries = <_RxEntry>[]; // 新的原始接收数据

  bool _showHex = true; // 接收显示模式

  // 发送输入与循环设置
  final TextEditingController _sendController = TextEditingController();
  bool _sendAsHex = false;
  bool _loopSend = false;
  int _sendIntervalMs = 1000;
  final TextEditingController _intervalController =
      TextEditingController(text: '1000');
  Timer? _loopTimer;
  StreamSubscription? _connectedDevicesSub;
  bool _handlingAutoDisconnect = false;

  // 自定义按钮列表（全局共享）
  List<CustomButton> customButtons = [];

  @override
  void initState() {
    super.initState();
    _subscribeConnectionChanges();
    _loadCustomButtons();
  }

  void _subscribeConnectionChanges() {
    _connectedDevicesSub = _ble.connectedDevices.listen((list) {
      if (!mounted) return;
      if (isConnected && connectedDevice != null) {
        final stillConnected =
            list.any((d) => d.remoteId.str == connectedDevice!.remoteId.str);
        if (!stillConnected) {
          _onAutoDisconnected();
        }
      }
    });
  }

  Future<void> _onAutoDisconnected() async {
    if (_handlingAutoDisconnect) return;
    _handlingAutoDisconnect = true;
    await _detachNotify();
    _stopLoopTimer();
    if (!mounted) return;
    setState(() {
      isConnected = false;
      connectedDeviceName = null;
      connectedDevice = null;
      serviceIdFFF0 = null;
      writeCharId = null;
      notifyCharId = null;
      _rxLogs.clear();
      _rxEntries.clear();
    });
    // 弹窗提示，并回到扫描界面（自动开始扫描）
    if (!Get.isDialogOpen!) {
      Get.defaultDialog(
        title: '蓝牙已断开',
        middleText: '设备连接已断开，已返回扫描界面',
        confirm: TextButton(
          onPressed: () => Get.back(),
          child: const Text('确定'),
        ),
      );
    }
    await _startScanReal();
    _handlingAutoDisconnect = false;
  }

  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF8F9FA),
      appBar: AppBar(
        title: Text(
          isConnected ? (connectedDeviceName ?? '未知设备') : '遥控',
          style: const TextStyle(
            fontSize: 20,
            fontWeight: FontWeight.w600,
            color: Color(0xFF2E3A59),
          ),
        ),
        backgroundColor: Colors.white,
        foregroundColor: const Color(0xFF2E3A59),
        elevation: 0,
        centerTitle: false,
        actions: [
          if (isConnected)
            TextButton.icon(
              onPressed: _disconnectDevice,
              icon: const Icon(Icons.link_off, size: 18),
              label: const Text('断开'),
              style: TextButton.styleFrom(
                  foregroundColor: const Color(0xFF4A90E2)),
            ),
          IconButton(
            icon: const Icon(Icons.add),
            onPressed: _showAddButtonDialog,
          ),
        ],
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // 顶部连接卡片已移除

            // 扫描或设备列表
            if (!isConnected) _buildScanOrList(),

            if (!isConnected) const SizedBox(height: 24),

            // 自定义按钮区域 + RX日志
            if (isConnected) ...[
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  const Text(
                    '自定义按钮',
                    style: TextStyle(
                      fontSize: 18,
                      fontWeight: FontWeight.w600,
                      color: Color(0xFF2E3A59),
                    ),
                  ),
                  TextButton.icon(
                    onPressed: _showAddButtonDialog,
                    icon: const Icon(Icons.add, size: 18),
                    label: const Text('添加'),
                    style: TextButton.styleFrom(
                      foregroundColor: const Color(0xFF4A90E2),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 16),
              Container(
                height: 220,
                child: GridView.builder(
                  shrinkWrap: true,
                  physics: const BouncingScrollPhysics(),
                  gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                    crossAxisCount: 2,
                    childAspectRatio: 1.2,
                    crossAxisSpacing: 12,
                    mainAxisSpacing: 12,
                  ),
                  itemCount: customButtons.length,
                  itemBuilder: (context, index) {
                    final button = customButtons[index];
                    return _buildCustomButton(button);
                  },
                ),
              ),
              const SizedBox(height: 24),
              Row(
                children: [
                  const Text(
                    '接收数据',
                    style: TextStyle(
                      fontSize: 18,
                      fontWeight: FontWeight.w600,
                      color: Color(0xFF2E3A59),
                    ),
                  ),
                  const Spacer(),
                  TextButton.icon(
                    onPressed: () => setState(() => _showHex = !_showHex),
                    icon: Icon(
                        _showHex ? Icons.hexagon_outlined : Icons.translate,
                        size: 18),
                    label: Text(_showHex ? 'HEX' : '文本'),
                    style: TextButton.styleFrom(
                      foregroundColor: const Color(0xFF4A90E2),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 12),
              Container(
                width: double.infinity,
                height: 200,
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: Colors.white,
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(color: Colors.grey.shade200),
                ),
                child: _rxEntries.isEmpty
                    ? Align(
                        alignment: Alignment.topLeft,
                        child: Text('暂无数据',
                            style: TextStyle(color: Colors.grey[600])),
                      )
                    : Scrollbar(
                        thumbVisibility: true,
                        child: ListView.builder(
                          reverse: true,
                          itemCount:
                              _rxEntries.length > 200 ? 200 : _rxEntries.length,
                          itemBuilder: (context, index) {
                            final e = _rxEntries[_rxEntries.length - 1 - index];
                            return Padding(
                              padding: const EdgeInsets.symmetric(vertical: 2),
                              child: Text(
                                _formatRxEntry(e),
                                style: const TextStyle(fontSize: 12),
                              ),
                            );
                          },
                        ),
                      ),
              ),
              const SizedBox(height: 16),
              const Text(
                '发送数据',
                style: TextStyle(
                  fontSize: 18,
                  fontWeight: FontWeight.w600,
                  color: Color(0xFF2E3A59),
                ),
              ),
              const SizedBox(height: 12),
              Container(
                width: double.infinity,
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: Colors.white,
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(color: Colors.grey.shade200),
                ),
                child: Column(
                  children: [
                    TextField(
                      controller: _sendController,
                      decoration: const InputDecoration(
                        hintText: '输入要发送的数据（文本或十六进制）',
                        border: OutlineInputBorder(),
                        isDense: true,
                        contentPadding:
                            EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                      ),
                      minLines: 1,
                      maxLines: 3,
                    ),
                    const SizedBox(height: 8),
                    // 16进制发送 单独一行
                    Row(
                      children: [
                        Switch(
                          value: _sendAsHex,
                          onChanged: (v) => setState(() => _sendAsHex = v),
                          activeColor: const Color(0xFF4A90E2),
                        ),
                        const Text('16进制发送'),
                        const Spacer(),
                        ElevatedButton.icon(
                          onPressed: _sendInputOnce,
                          icon: const Icon(Icons.send, size: 18),
                          label: const Text('发送'),
                          style: ElevatedButton.styleFrom(
                            backgroundColor: const Color(0xFF4A90E2),
                            foregroundColor: Colors.white,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 8),
                    // 循环发送 + 间隔 单独一行
                    Row(
                      children: [
                        Switch(
                          value: _loopSend,
                          onChanged: (v) {
                            setState(() => _loopSend = v);
                            if (v) {
                              _startLoopTimer();
                            } else {
                              _stopLoopTimer();
                            }
                          },
                          activeColor: const Color(0xFF4A90E2),
                        ),
                        const Text('循环发送'),
                        const SizedBox(width: 12),
                        SizedBox(
                          width: 150,
                          child: TextField(
                            controller: _intervalController,
                            keyboardType: TextInputType.number,
                            decoration: const InputDecoration(
                              labelText: '间隔(ms)',
                              border: OutlineInputBorder(),
                              isDense: true,
                            ),
                            onChanged: (v) {
                              final parsed = int.tryParse(v.trim());
                              if (parsed != null && parsed > 0) {
                                _sendIntervalMs = parsed;
                                if (_loopSend) {
                                  _startLoopTimer();
                                }
                              }
                            },
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            ],

            // 空状态提示
            if (!isConnected && !isScanning) ...[
              const SizedBox(height: 32),
              _buildEmptyState(),
            ],
          ],
        ),
      ),
    );
  }

  @override
  void dispose() {
    _loopTimer?.cancel();
    _sendController.dispose();
    _intervalController.dispose();
    _connectedDevicesSub?.cancel();
    super.dispose();
  }

  Future<void> _loadCustomButtons() async {
    try {
      final db = DatabaseService();
      final rows = await db.getCustomButtons();
      final list = rows.map((m) => CustomButtonDb.fromDbMap(m)).toList();
      if (mounted) setState(() => customButtons = list);
    } catch (e) {
      debugPrint('加载自定义按钮失败: $e');
    }
  }

  // 已弃用：保留占位避免误用（不再引用）
  // Widget _buildScanButton() => const SizedBox.shrink();

  Widget _buildScanOrList() {
    final devices = _ble.discoveredDevices;

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: Colors.grey.shade200),
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
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              const Text(
                '附近设备',
                style: TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.w600,
                  color: Color(0xFF2E3A59),
                ),
              ),
              if (!isScanning)
                ElevatedButton.icon(
                  onPressed: _startScanReal,
                  icon: const Icon(Icons.play_arrow),
                  label: const Text('开始扫描'),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: const Color(0xFF4A90E2),
                    foregroundColor: Colors.white,
                  ),
                )
              else
                ElevatedButton.icon(
                  onPressed: _stopScanReal,
                  icon: const Icon(Icons.stop),
                  label: const Text('停止扫描'),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: Colors.grey,
                    foregroundColor: Colors.white,
                  ),
                ),
            ],
          ),
          const SizedBox(height: 12),
          if (isScanning) const LinearProgressIndicator(minHeight: 3),
          const SizedBox(height: 12),
          Obx(() {
            final list = devices;
            if (list.isEmpty) {
              return const Text(
                '未发现设备，点击开始扫描',
                style: TextStyle(color: Colors.grey),
              );
            }
            return ListView.separated(
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              itemCount: list.length,
              separatorBuilder: (_, __) => Divider(
                height: 1,
                color: Colors.grey.shade200,
              ),
              itemBuilder: (context, index) {
                final dev = list[index];
                final name = _ble.getDeviceName(dev);
                final rssi = _ble.getDeviceRssi(dev);
                final connectable = _ble.isConnectable(dev);
                return ListTile(
                  leading: Icon(
                    connectable
                        ? Icons.bluetooth_searching
                        : Icons.bluetooth_disabled,
                    color: connectable ? const Color(0xFF4A90E2) : Colors.grey,
                  ),
                  title: Text(name.isEmpty ? '未知设备' : name),
                  subtitle: Text(
                    '地址: ${dev.remoteId.str}   RSSI: $rssi',
                    style: const TextStyle(fontSize: 12),
                  ),
                  trailing: ElevatedButton(
                    onPressed: connectable ? () => _connect(dev) : null,
                    style: ElevatedButton.styleFrom(
                      backgroundColor:
                          connectable ? const Color(0xFF4CAF50) : Colors.grey,
                      foregroundColor: Colors.white,
                    ),
                    child: const Text('连接'),
                  ),
                );
              },
            );
          }),
        ],
      ),
    );
  }

  Widget _buildCustomButton(CustomButton button) {
    return Card(
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(16),
        side: BorderSide(color: Colors.grey.shade200),
      ),
      child: InkWell(
        onTap: () => _sendCustomData(button),
        onLongPress: () => _editButton(button),
        borderRadius: BorderRadius.circular(16),
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(16),
            gradient: LinearGradient(
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
              colors: [
                button.color.withOpacity(0.1),
                button.color.withOpacity(0.05),
              ],
            ),
          ),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.start,
            crossAxisAlignment: CrossAxisAlignment.center,
            children: [
              Container(
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  color: button.color.withOpacity(0.2),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Icon(
                  button.icon,
                  size: 28,
                  color: button.color,
                ),
              ),
              const SizedBox(height: 8),
              Text(
                button.name,
                style: TextStyle(
                  fontSize: 13,
                  fontWeight: FontWeight.w600,
                  color: button.color.withOpacity(0.8),
                ),
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 2),
              Flexible(
                child: Text(
                  button.isHex
                      ? 'HEX: ${button.data.map((e) => e.toRadixString(16).toUpperCase()).join(' ')}'
                      : 'TXT: ${button.textPayload ?? ''}',
                  style: TextStyle(
                    fontSize: 10,
                    color: Colors.grey.shade600,
                  ),
                  textAlign: TextAlign.center,
                  overflow: TextOverflow.ellipsis,
                  maxLines: 2,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildEmptyState() {
    return Center(
      child: Column(
        children: [
          Container(
            padding: const EdgeInsets.all(24),
            decoration: BoxDecoration(
              color: Colors.grey.withOpacity(0.1),
              borderRadius: BorderRadius.circular(16),
            ),
            child: Icon(
              Icons.bluetooth_disabled,
              size: 64,
              color: Colors.grey.shade400,
            ),
          ),
          const SizedBox(height: 24),
          const Text(
            '未连接设备',
            style: TextStyle(
              fontSize: 20,
              fontWeight: FontWeight.w600,
              color: Color(0xFF2E3A59),
            ),
          ),
          const SizedBox(height: 12),
          Text(
            '连接蓝牙设备后即可使用\n自定义按钮功能',
            style: TextStyle(
              fontSize: 14,
              color: Colors.grey.shade600,
              height: 1.5,
            ),
            textAlign: TextAlign.center,
          ),
        ],
      ),
    );
  }

  Future<void> _startScanReal() async {
    setState(() => isScanning = true);
    try {
      await _ble.startScan();
    } catch (_) {}
  }

  Future<void> _stopScanReal() async {
    await _ble.stopScan();
    if (mounted) setState(() => isScanning = false);
  }

  Future<void> _connect(BluetoothDevice device) async {
    try {
      await _ble.connectDevice(device);
      await _stopScanReal();
      final name = _ble.getDeviceName(device);
      setState(() {
        isConnected = true;
        connectedDeviceName = name.isEmpty ? '未知设备' : name;
        connectedDevice = device;
        _rxLogs.clear();
        _rxEntries.clear();
      });
      // 预解析透传服务（先试 fff0，再试 fe59，再用通用降级）
      Map<String, String>? ids = await _bt.findTransparentUuidsByAddress(
          device.remoteId.str,
          serviceUuidHint: 'fff0');
      ids ??= await _bt.findTransparentUuidsByAddress(device.remoteId.str,
          serviceUuidHint: 'fe59');
      if (ids != null) {
        serviceIdFFF0 = ids['serviceId'];
        writeCharId = ids['writeCharId'];
        notifyCharId = ids['notifyCharId'] ?? ids['writeCharId'];
        // 建立监听
        _attachNotify();
      }
      Get.snackbar('连接成功', '已连接到 $connectedDeviceName',
          snackPosition: SnackPosition.BOTTOM,
          backgroundColor: Colors.green,
          colorText: Colors.white);
    } catch (e) {
      Get.snackbar('连接失败', '$e', snackPosition: SnackPosition.BOTTOM);
    }
  }

  Future<void> _disconnectDevice() async {
    // 先取消监听
    await _detachNotify();
    if (connectedDevice != null) {
      try {
        await _ble.disconnectDevice(connectedDevice!);
      } catch (_) {}
    }
    setState(() {
      isConnected = false;
      connectedDeviceName = null;
      connectedDevice = null;
      serviceIdFFF0 = null;
      writeCharId = null;
      notifyCharId = null;
      _rxLogs.clear();
      _rxEntries.clear();
      _stopLoopTimer();
    });
    Get.snackbar('已断开连接', '设备已断开连接', snackPosition: SnackPosition.BOTTOM);
  }

  Future<void> _sendCustomData(CustomButton button) async {
    if (!isConnected || connectedDevice == null) return;
    try {
      // 若尚未解析到特征，尝试查找FFF0/FE59及可写特征
      if (serviceIdFFF0 == null || writeCharId == null) {
        Map<String, String>? ids = await _bt.findTransparentUuidsByAddress(
            connectedDevice!.remoteId.str,
            serviceUuidHint: 'fff0');
        ids ??= await _bt.findTransparentUuidsByAddress(
            connectedDevice!.remoteId.str,
            serviceUuidHint: 'fe59');
        if (ids != null) {
          serviceIdFFF0 = ids['serviceId'];
          writeCharId = ids['writeCharId'];
          notifyCharId = ids['notifyCharId'] ?? ids['writeCharId'];
        }
      }
      if (serviceIdFFF0 != null && writeCharId != null) {
        final payload =
            button.isHex ? button.data : utf8.encode(button.textPayload ?? '');
        if (payload.isEmpty) {
          Get.snackbar('错误', '按钮数据为空', snackPosition: SnackPosition.BOTTOM);
          return;
        }
        await _bt.writeByAddress(connectedDevice!.remoteId.str, serviceIdFFF0!,
            writeCharId!, payload,
            writeWithResponse: true);
        Get.snackbar(
            '指令已发送',
            button.isHex
                ? '${button.name}: ${button.data.map((e) => e.toRadixString(16).toUpperCase()).join(' ')}'
                : '${button.name}: ${button.textPayload ?? ''}',
            snackPosition: SnackPosition.BOTTOM,
            backgroundColor: button.color,
            colorText: Colors.white,
            duration: const Duration(seconds: 2));
      } else {
        Get.snackbar('错误', '未找到FFF0服务或可写特征',
            snackPosition: SnackPosition.BOTTOM);
      }
    } catch (e) {
      Get.snackbar('发送失败', '$e', snackPosition: SnackPosition.BOTTOM);
    }
  }

  void _editButton(CustomButton button) {
    _showEditButtonDialog(button);
  }

  void _showAddButtonDialog() {
    _showEditButtonDialog(null);
  }

  void _showEditButtonDialog(CustomButton? button) {
    final nameController = TextEditingController(text: button?.name ?? '');
    final isHexDefault = button?.isHex ?? true;
    final dataController = TextEditingController(
      text: button == null
          ? ''
          : (button.isHex
              ? button.data
                  .map((e) => e.toRadixString(16).toUpperCase())
                  .join(' ')
              : button.textPayload ?? ''),
    );
    bool isHexSelected = isHexDefault;
    IconData selectedIcon = button?.icon ?? Icons.touch_app;
    Color selectedColor = button?.color ?? Colors.blue;

    showDialog(
      context: context,
      builder: (context) => StatefulBuilder(
        builder: (context, setState) => AlertDialog(
          title: Text(button == null ? '添加按钮' : '编辑按钮'),
          content: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                TextField(
                  controller: nameController,
                  decoration: const InputDecoration(
                    labelText: '按钮名称',
                    border: OutlineInputBorder(),
                  ),
                ),
                const SizedBox(height: 16),
                // Hex选择
                Row(
                  children: [
                    Switch(
                      value: isHexSelected,
                      onChanged: (v) => setState(() => isHexSelected = v),
                      activeColor: const Color(0xFF4A90E2),
                    ),
                    const Text('Hex'),
                  ],
                ),
                const SizedBox(height: 8),
                TextField(
                  controller: dataController,
                  decoration: InputDecoration(
                    labelText: isHexSelected ? '发送数据 (十六进制，空格分隔)' : '发送数据 (文本)',
                    hintText: isHexSelected ? '例如: 01 02 03' : '例如: hello',
                    border: const OutlineInputBorder(),
                  ),
                ),
                const SizedBox(height: 16),
                // 图标选择
                const Text('选择图标:'),
                const SizedBox(height: 8),
                Wrap(
                  spacing: 8,
                  children: _customButtonIconChoices
                      .map<Widget>((IconData icon) => GestureDetector(
                            onTap: () => setState(() => selectedIcon = icon),
                            child: Container(
                              padding: const EdgeInsets.all(8),
                              decoration: BoxDecoration(
                                color: selectedIcon == icon
                                    ? Colors.blue.withOpacity(0.2)
                                    : Colors.transparent,
                                borderRadius: BorderRadius.circular(8),
                              ),
                              child: Icon(icon),
                            ),
                          ))
                      .toList(),
                ),
                const SizedBox(height: 16),
                // 颜色选择
                const Text('选择颜色:'),
                const SizedBox(height: 8),
                Wrap(
                  spacing: 8,
                  children: <Color>[
                    Colors.blue,
                    Colors.red,
                    Colors.green,
                    Colors.orange,
                    Colors.purple,
                    Colors.teal,
                    Colors.indigo,
                    Colors.brown,
                    Colors.cyan,
                    Colors.pink,
                    Colors.deepPurple,
                    Colors.lime,
                  ]
                      .map<Widget>((Color color) => GestureDetector(
                            onTap: () => setState(() => selectedColor = color),
                            child: Container(
                              width: 32,
                              height: 32,
                              decoration: BoxDecoration(
                                color: color,
                                shape: BoxShape.circle,
                                border: selectedColor == color
                                    ? Border.all(color: Colors.black, width: 2)
                                    : null,
                              ),
                            ),
                          ))
                      .toList(),
                ),
              ],
            ),
          ),
          actions: [
            if (button != null)
              TextButton(
                onPressed: () {
                  // 删除数据库并更新内存
                  DatabaseService().deleteCustomButton(button.id).then((_) {
                    setState(() {
                      customButtons.removeWhere((b) => b.id == button.id);
                    });
                  });
                  Navigator.pop(context);
                },
                child: const Text('删除', style: TextStyle(color: Colors.red)),
              ),
            TextButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('取消'),
            ),
            ElevatedButton(
              onPressed: () {
                final name = nameController.text.trim();
                final dataStr = dataController.text.trim();

                if (name.isEmpty || dataStr.isEmpty) return;

                try {
                  final id = button?.id ??
                      DateTime.now().millisecondsSinceEpoch.toString();
                  List<int> hexData = <int>[];
                  String? textPayload;
                  if (isHexSelected) {
                    hexData = _parseHexInput(dataStr);
                  } else {
                    textPayload = dataStr;
                  }

                  final newButton = CustomButton(
                    id: id,
                    name: name,
                    icon: selectedIcon,
                    data: hexData,
                    color: selectedColor,
                    isHex: isHexSelected,
                    textPayload: textPayload,
                  );

                  // 保存数据库
                  DatabaseService()
                      .upsertCustomButton(
                    id: id,
                    name: name,
                    iconCode: selectedIcon.codePoint,
                    colorValue: selectedColor.value,
                    isHex: isHexSelected,
                    payload: isHexSelected
                        ? _bytesToHex(hexData)
                        : textPayload ?? '',
                  )
                      .then((_) {
                    setState(() {
                      if (button != null) {
                        final index =
                            customButtons.indexWhere((b) => b.id == button.id);
                        if (index != -1) {
                          customButtons[index] = newButton;
                        }
                      } else {
                        customButtons.add(newButton);
                      }
                    });
                    Navigator.pop(context);
                  });
                } catch (e) {
                  Get.snackbar('错误', '数据格式不正确');
                }
              },
              child: Text(button == null ? '添加' : '保存'),
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _attachNotify() async {
    if (connectedDevice == null || serviceIdFFF0 == null) return;
    final targetService = serviceIdFFF0!;
    final targetChar = notifyCharId ?? writeCharId;
    if (targetChar == null) return;
    try {
      final stream = _bt.subscribeNotifyByAddress(
          connectedDevice!.remoteId.str, targetService, targetChar);
      stream?.listen((event) {
        setState(() {
          _rxEntries
              .add(_RxEntry(time: DateTime.now(), data: List<int>.from(event)));
        });
      });
    } catch (_) {}
  }

  Future<void> _detachNotify() async {
    if (connectedDevice == null || serviceIdFFF0 == null) return;
    final targetChar = notifyCharId ?? writeCharId;
    if (targetChar == null) return;
    try {
      await _bt.unSubscribeNotifyByAddress(
          connectedDevice!.remoteId.str, serviceIdFFF0!, targetChar);
    } catch (_) {}
  }
}

class CustomButton {
  final String id;
  final String name;
  final IconData icon;
  final List<int> data;
  final Color color;
  final bool isHex;
  final String? textPayload; // 当isHex=false时使用

  CustomButton({
    required this.id,
    required this.name,
    required this.icon,
    required this.data,
    required this.color,
    required this.isHex,
    this.textPayload,
  });
}

extension CustomButtonDb on CustomButton {
  static CustomButton fromDbMap(Map<String, dynamic> m) {
    final isHex = (m['isHex'] ?? 1) == 1;
    final payload = (m['payload'] ?? '') as String;
    List<int> data = <int>[];
    String? textPayload;
    if (isHex) {
      // 允许payload存的是空格分隔hex
      data = payload
          .split(RegExp(r'\s+'))
          .where((p) => p.isNotEmpty)
          .map((p) => int.parse(p, radix: 16))
          .toList();
    } else {
      textPayload = payload;
    }
    final iconCode = m['iconCode'];
    return CustomButton(
      id: m['id'] as String,
      name: m['name'] as String,
      icon: _customButtonIconForCode(iconCode is int ? iconCode : null),
      data: data,
      color: Color(m['colorValue'] as int),
      isHex: isHex,
      textPayload: textPayload,
    );
  }
}

class _RxEntry {
  final DateTime time;
  final List<int> data;
  _RxEntry({required this.time, required this.data});
}

extension on _RemoteControlPageState {
  String _formatRxEntry(_RxEntry e) {
    final t = '[${e.time.toIso8601String().substring(11, 19)}] ';
    return _showHex
        ? '$t${_bytesToHex(e.data)}'
        : '$t${_autoDecodeToString(e.data)}';
  }

  String _bytesToHex(List<int> data) {
    return data.map((b) => b.toRadixString(16).padLeft(2, '0')).join(' ');
  }

  String _autoDecodeToString(List<int> data) {
    try {
      if (data.length >= 2) {
        // UTF-16 BOM detection
        if (data[0] == 0xFF && data[1] == 0xFE) {
          // UTF-16 LE
          final bytes = Uint8List.fromList(data.sublist(2));
          final bd = ByteData.view(bytes.buffer);
          final codeUnits = <int>[];
          for (int i = 0; i + 1 < bytes.length; i += 2) {
            codeUnits.add(bd.getUint16(i, Endian.little));
          }
          return String.fromCharCodes(codeUnits);
        }
        if (data[0] == 0xFE && data[1] == 0xFF) {
          // UTF-16 BE
          final bytes = Uint8List.fromList(data.sublist(2));
          final bd = ByteData.view(bytes.buffer);
          final codeUnits = <int>[];
          for (int i = 0; i + 1 < bytes.length; i += 2) {
            codeUnits.add(bd.getUint16(i, Endian.big));
          }
          return String.fromCharCodes(codeUnits);
        }
      }
      // Try UTF-8 strict first
      return utf8.decode(data, allowMalformed: false);
    } catch (_) {
      try {
        // Fallback ASCII (allow invalid)
        return ascii.decode(data, allowInvalid: true);
      } catch (_) {
        try {
          // Fallback Latin1 to preserve bytes
          return latin1.decode(data, allowInvalid: true);
        } catch (_) {
          // Final fallback to hex
          return _bytesToHex(data);
        }
      }
    }
  }

  Future<void> _ensureTransparentIds() async {
    if (connectedDevice == null) return;
    if (serviceIdFFF0 != null && writeCharId != null) return;
    Map<String, String>? ids = await _bt.findTransparentUuidsByAddress(
        connectedDevice!.remoteId.str,
        serviceUuidHint: 'fff0');
    ids ??= await _bt.findTransparentUuidsByAddress(
        connectedDevice!.remoteId.str,
        serviceUuidHint: 'fe59');
    if (ids != null) {
      serviceIdFFF0 = ids['serviceId'];
      writeCharId = ids['writeCharId'];
      notifyCharId = ids['notifyCharId'] ?? ids['writeCharId'];
    }
  }

  List<int> _parseHexInput(String input) {
    final cleaned = input
        .replaceAll(RegExp(r'[^0-9a-fA-F]'), ' ')
        .replaceAll(RegExp(r'0x', caseSensitive: false), ' ')
        .trim();
    if (cleaned.isEmpty) return <int>[];
    if (cleaned.contains(' ')) {
      final parts = cleaned.split(RegExp(r'\s+'));
      return parts
          .where((p) => p.isNotEmpty)
          .map((p) => int.parse(p, radix: 16))
          .toList();
    } else {
      // continuous hex string
      if (cleaned.length % 2 != 0) {
        throw FormatException('十六进制长度必须为偶数');
      }
      final out = <int>[];
      for (int i = 0; i < cleaned.length; i += 2) {
        out.add(int.parse(cleaned.substring(i, i + 2), radix: 16));
      }
      return out;
    }
  }

  Future<void> _sendInputOnce() async {
    if (!isConnected || connectedDevice == null) return;
    try {
      await _ensureTransparentIds();
      if (serviceIdFFF0 == null || writeCharId == null) {
        Get.snackbar('错误', '未找到可写特征', snackPosition: SnackPosition.BOTTOM);
        return;
      }
      final text = _sendController.text.trim();
      if (text.isEmpty) return;
      final bytes = _sendAsHex ? _parseHexInput(text) : utf8.encode(text);
      if (bytes.isEmpty) return;
      await _bt.writeByAddress(
        connectedDevice!.remoteId.str,
        serviceIdFFF0!,
        writeCharId!,
        bytes,
        writeWithResponse: true,
      );
      Get.snackbar(
          '发送成功',
          _sendAsHex
              ? _bytesToHex(bytes)
              : (text.length > 50 ? text.substring(0, 50) + '…' : text),
          snackPosition: SnackPosition.BOTTOM,
          backgroundColor: const Color(0xFF4A90E2),
          colorText: Colors.white,
          duration: const Duration(seconds: 2));
    } catch (e) {
      Get.snackbar('发送失败', '$e', snackPosition: SnackPosition.BOTTOM);
    }
  }

  void _startLoopTimer() {
    _loopTimer?.cancel();
    if (!_loopSend) return;
    _loopTimer =
        Timer.periodic(Duration(milliseconds: _sendIntervalMs), (_) async {
      await _sendInputOnce();
    });
  }

  void _stopLoopTimer() {
    _loopTimer?.cancel();
    _loopTimer = null;
  }
}
