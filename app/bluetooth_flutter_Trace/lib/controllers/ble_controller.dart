import 'package:flutter/material.dart';
import 'package:flutter_blue_plus/flutter_blue_plus.dart';
import 'package:get/get.dart';
import '../utils/permission_helper.dart';
import '../services/bluetooth_service.dart' as bt_service;

class BleController extends GetxController {
  static BleController get to => Get.find();

  // 使用跨平台蓝牙服务
  bt_service.BluetoothService get _bluetoothService =>
      Get.find<bt_service.BluetoothService>();

  // 蓝牙适配器状态
  var adapterState = BluetoothAdapterState.unknown.obs;

  // 扫描状态
  var isScanning = false.obs;

  // 发现的设备列表
  var discoveredDevices = <BluetoothDevice>[].obs;

  // 连接的设备列表
  var connectedDevices = <BluetoothDevice>[].obs;

  // 设备扫描结果数据
  var scanResults = <ScanResult>[].obs;

  final List<Worker> _workers = [];

  @override
  void onInit() {
    super.onInit();
    initBluetooth();
  }

  @override
  void onClose() {
    _disposeWorkers();
    super.onClose();
  }

  /// 初始化蓝牙
  Future<void> initBluetooth() async {
    try {
      _disposeWorkers();

      // 监听BluetoothService的状态变化
      _workers.add(ever(_bluetoothService.adapterState, (state) {
        adapterState.value = state;
        if (state != BluetoothAdapterState.on) {
          discoveredDevices.clear();
          scanResults.clear();
          isScanning.value = false;
        }
      }));

      _workers.add(ever(_bluetoothService.isScanning, (scanning) {
        isScanning.value = scanning;
      }));

      _workers.add(ever(_bluetoothService.discoveredDevices, (devices) {
        discoveredDevices.assignAll(devices);
      }));

      _workers.add(ever(_bluetoothService.connectedDevices, (devices) {
        connectedDevices.assignAll(devices);
      }));

      _workers.add(ever(_bluetoothService.scanResults, (results) {
        debugPrint('BleController接收到扫描结果: ${results.length} 个设备');
        scanResults.assignAll(results);
      }));

      // 获取当前状态
      adapterState.value = _bluetoothService.adapterState.value;
      isScanning.value = _bluetoothService.isScanning.value;
      discoveredDevices.value = _bluetoothService.discoveredDevices.value;
      connectedDevices.value = _bluetoothService.connectedDevices.value;
      scanResults.value = _bluetoothService.scanResults.value;

      debugPrint('蓝牙控制器初始化成功，平台: ${_bluetoothService.getPlatformInfo()}');
    } catch (e) {
      debugPrint('初始化蓝牙失败: $e');
      Get.snackbar('错误', '初始化蓝牙失败: $e', snackPosition: SnackPosition.BOTTOM);
    }
  }

  void _disposeWorkers() {
    for (final worker in _workers) {
      worker.dispose();
    }
    _workers.clear();
  }

  /// 请求蓝牙权限
  Future<bool> requestPermissions() async {
    return await PermissionHelper.requestBluetoothPermissions();
  }

  /// 开启蓝牙
  Future<void> turnOnBluetooth() async {
    await _bluetoothService.turnOnBluetooth();
  }

  /// 开始扫描设备
  Future<void> startScan() async {
    try {
      // 检查权限
      if (!await requestPermissions()) {
        return;
      }

      // 检查蓝牙状态
      if (adapterState.value != BluetoothAdapterState.on) {
        Get.snackbar('提示', '请先开启蓝牙', snackPosition: SnackPosition.BOTTOM);
        return;
      }

      // 使用跨平台蓝牙服务扫描（持续扫描）
      await _bluetoothService.startScan();

      Get.snackbar('提示', '开始扫描蓝牙设备...', snackPosition: SnackPosition.BOTTOM);
    } catch (e) {
      isScanning.value = false;
      debugPrint('扫描失败: $e');
      Get.snackbar('错误', '扫描失败: $e', snackPosition: SnackPosition.BOTTOM);
    }
  }

  /// 停止扫描
  Future<void> stopScan() async {
    await _bluetoothService.stopScan();
  }

  /// 连接设备
  Future<void> connectDevice(BluetoothDevice device) async {
    await _bluetoothService.connectDevice(device);
  }

  /// 断开设备连接
  Future<void> disconnectDevice(BluetoothDevice device) async {
    await _bluetoothService.disconnectDevice(device);
  }

  /// 更新已连接的设备列表
  Future<void> updateConnectedDevices() async {
    await _bluetoothService.updateConnectedDevices();
  }

  /// 获取设备的扫描结果数据
  ScanResult? getScanResult(BluetoothDevice device) {
    return _bluetoothService.getScanResult(device);
  }

  /// 获取设备RSSI
  int getDeviceRssi(BluetoothDevice device) {
    final result = getScanResult(device);
    return result?.rssi ?? 0;
  }

  /// 获取设备广播数据
  List<int> getAdvertisementData(BluetoothDevice device) {
    final result = getScanResult(device);
    return result?.advertisementData.manufacturerData.values.firstOrNull ?? [];
  }

  /// 获取设备服务UUID列表
  List<String> getServiceUuids(BluetoothDevice device) {
    final result = getScanResult(device);
    return result?.advertisementData.serviceUuids
            .map((uuid) => uuid.toString())
            .toList() ??
        [];
  }

  /// 检查设备是否可连接
  bool isConnectable(BluetoothDevice device) {
    final result = getScanResult(device);
    return result?.advertisementData.connectable ?? false;
  }

  /// 格式化设备名称
  String getDeviceName(BluetoothDevice device) {
    debugPrint('获取设备名称，设备ID: ${device.remoteId}');

    // 通过扫描结果获取设备名称
    final scanResult = getScanResult(device);
    if (scanResult != null) {
      final advName = scanResult.advertisementData.advName;
      debugPrint('扫描结果中设备名称: $advName');
      if (advName.isNotEmpty) {
        return advName;
      }
    }

    // 如果扫描结果中没有名称，回退到平台提供的设备名称。
    final deviceName = device.platformName;

    debugPrint('最终设备名称: $deviceName');
    return deviceName.isNotEmpty ? deviceName : '未知设备';
  }

  /// 格式化设备ID
  String getDeviceId(BluetoothDevice device) {
    return device.remoteId.toString();
  }

  /// 获取信号强度描述
  String getRssiDescription(int rssi) {
    if (rssi >= -50) return '优秀';
    if (rssi >= -60) return '良好';
    if (rssi >= -70) return '一般';
    if (rssi >= -80) return '较差';
    return '很差';
  }

  /// 获取信号强度颜色
  Color getRssiColor(int rssi) {
    if (rssi >= -50) return Colors.green;
    if (rssi >= -60) return Colors.lightGreen;
    if (rssi >= -70) return Colors.orange;
    if (rssi >= -80) return Colors.red;
    return Colors.red.shade800;
  }
}
