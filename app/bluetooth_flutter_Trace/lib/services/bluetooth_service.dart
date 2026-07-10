import 'dart:async';
import 'dart:io';
import 'dart:typed_data';
import 'package:flutter/foundation.dart';
import 'package:flutter_blue_plus/flutter_blue_plus.dart';
import 'package:get/get.dart';

// Windows蓝牙支持 - 条件性导入
import 'package:win_ble/win_ble.dart';

// 抽象蓝牙适配器接口
abstract class BluetoothAdapter {
  Future<void> init();
  Future<void> startScan({Duration? timeout});
  Future<void> stopScan();
  Future<void> connect(String deviceAddress);
  Future<void> disconnect(String deviceAddress);
  Future<List<dynamic>> getConnectedDevices();
  Future<BluetoothAdapterState> getAdapterState();
  Stream<BluetoothAdapterState> get adapterStateChanged;
  Stream<List<dynamic>> get scanResults;
  Stream<String> get connectionStateChanged;

  // WinBle特有的方法
  Future<void> pair(String deviceAddress);
  Future<void> unPair(String deviceAddress);
  Future<bool> canPair(String deviceAddress);
  Future<bool> isPaired(String deviceAddress);
  Future<List<dynamic>> discoverServices(String deviceAddress);
  Future<List<dynamic>> discoverCharacteristics(
      String deviceAddress, String serviceId);
  Future<List<int>> readCharacteristic(
      String deviceAddress, String serviceId, String characteristicId);
  Future<void> writeCharacteristic(String deviceAddress, String serviceId,
      String characteristicId, List<int> data,
      {bool writeWithResponse = false});
  Future<void> subscribeToCharacteristic(
      String deviceAddress, String serviceId, String characteristicId);
  Future<void> unSubscribeFromCharacteristic(
      String deviceAddress, String serviceId, String characteristicId);
}

// FlutterBluePlus适配器（用于移动端）
class FlutterBluePlusAdapter implements BluetoothAdapter {
  @override
  Future<void> init() async {
    // FlutterBluePlus不需要显式初始化
  }

  @override
  Future<void> startScan({Duration? timeout}) async {
    if (timeout != null) {
      await FlutterBluePlus.startScan(timeout: timeout);
    } else {
      await FlutterBluePlus.startScan();
    }
  }

  @override
  Future<void> stopScan() async {
    await FlutterBluePlus.stopScan();
  }

  @override
  Future<void> connect(String deviceId) async {
    // 这里需要根据deviceId找到对应的设备并连接
    // 暂时简化处理
  }

  @override
  Future<void> disconnect(String deviceId) async {
    // 这里需要根据deviceId找到对应的设备并断开连接
    // 暂时简化处理
  }

  @override
  Future<List<dynamic>> getConnectedDevices() async {
    return FlutterBluePlus.connectedDevices;
  }

  @override
  Future<BluetoothAdapterState> getAdapterState() async {
    return FlutterBluePlus.adapterState.first;
  }

  @override
  Stream<BluetoothAdapterState> get adapterStateChanged =>
      FlutterBluePlus.adapterState;

  @override
  Stream<List<dynamic>> get scanResults =>
      FlutterBluePlus.scanResults.map((results) => results);

  @override
  Stream<String> get connectionStateChanged =>
      const Stream.empty(); // FlutterBluePlus使用不同的机制

  // WinBle特有的方法 - FlutterBluePlus不支持这些功能
  @override
  Future<void> pair(String deviceAddress) async {
    throw UnsupportedError('FlutterBluePlus does not support pairing');
  }

  @override
  Future<void> unPair(String deviceAddress) async {
    throw UnsupportedError('FlutterBluePlus does not support unpairing');
  }

  @override
  Future<bool> canPair(String deviceAddress) async {
    throw UnsupportedError('FlutterBluePlus does not support pairing check');
  }

  @override
  Future<bool> isPaired(String deviceAddress) async {
    throw UnsupportedError('FlutterBluePlus does not support pairing check');
  }

  @override
  Future<List<dynamic>> discoverServices(String deviceAddress) async {
    throw UnsupportedError(
        'FlutterBluePlus service discovery not implemented in adapter');
  }

  @override
  Future<List<dynamic>> discoverCharacteristics(
      String deviceAddress, String serviceId) async {
    throw UnsupportedError(
        'FlutterBluePlus characteristic discovery not implemented in adapter');
  }

  @override
  Future<List<int>> readCharacteristic(
      String deviceAddress, String serviceId, String characteristicId) async {
    throw UnsupportedError(
        'FlutterBluePlus characteristic read not implemented in adapter');
  }

  @override
  Future<void> writeCharacteristic(String deviceAddress, String serviceId,
      String characteristicId, List<int> data,
      {bool writeWithResponse = false}) async {
    throw UnsupportedError(
        'FlutterBluePlus characteristic write not implemented in adapter');
  }

  @override
  Future<void> subscribeToCharacteristic(
      String deviceAddress, String serviceId, String characteristicId) async {
    throw UnsupportedError(
        'FlutterBluePlus characteristic subscription not implemented in adapter');
  }

  @override
  Future<void> unSubscribeFromCharacteristic(
      String deviceAddress, String serviceId, String characteristicId) async {
    throw UnsupportedError(
        'FlutterBluePlus characteristic unsubscription not implemented in adapter');
  }
}

// WinBle适配器（用于Windows）
class WinBleAdapter implements BluetoothAdapter {
  StreamSubscription? _scanSubscription;
  final Map<String, StreamSubscription> _deviceConnectionSubscriptions = {};

  @override
  Future<void> init() async {
    try {
      // 对于Flutter项目，BleServer.exe应该在应用根目录
      // 确保使用正确的路径格式
      await WinBle.initialize(serverPath: 'BLEServer.exe');
      debugPrint('WinBle适配器初始化完成');
    } catch (e) {
      debugPrint('WinBle初始化失败: $e');
      // 如果初始化失败，可能是因为服务器文件不存在
      // 尝试使用windows文件夹下的文件
      try {
        await WinBle.initialize(serverPath: 'windows/BLEServer.exe');
        debugPrint('WinBle适配器初始化完成（使用windows路径）');
      } catch (e2) {
        debugPrint('WinBle初始化失败（两种路径都失败）: $e2');
        debugPrint('WinBle服务器文件可能不存在，将继续运行但蓝牙功能可能受限');
      }
    }
  }

  @override
  Future<void> startScan({Duration? timeout}) async {
    try {
      debugPrint('WinBle开始扫描设备...');
      WinBle.startScanning();
      debugPrint('WinBle扫描开始');

      // 处理扫描超时
      if (timeout != null) {
        Timer(timeout, () => stopScan());
      }
    } catch (e) {
      debugPrint('WinBle扫描启动失败: $e');
      rethrow;
    }
  }

  @override
  Future<void> stopScan() async {
    try {
      WinBle.stopScanning();
      _scanSubscription?.cancel();
      debugPrint('WinBle扫描停止');
    } catch (e) {
      debugPrint('WinBle扫描停止失败: $e');
      rethrow;
    }
  }

  @override
  Future<void> connect(String deviceAddress) async {
    try {
      await WinBle.connect(deviceAddress);
      debugPrint('WinBle连接设备: $deviceAddress');

      // 监听连接状态变化
      final connectionStream = WinBle.connectionStreamOf(deviceAddress);
      _deviceConnectionSubscriptions[deviceAddress] =
          connectionStream.listen((isConnected) {
        debugPrint('设备 $deviceAddress 连接状态: ${isConnected ? "已连接" : "已断开"}');
        // 这里可以触发连接状态变化的事件
      });
    } catch (e) {
      debugPrint('WinBle连接设备失败: $e');
      rethrow;
    }
  }

  @override
  Future<void> disconnect(String deviceAddress) async {
    try {
      await WinBle.disconnect(deviceAddress);
      _deviceConnectionSubscriptions[deviceAddress]?.cancel();
      _deviceConnectionSubscriptions.remove(deviceAddress);
      debugPrint('WinBle断开设备: $deviceAddress');
    } catch (e) {
      debugPrint('WinBle断开设备失败: $e');
      rethrow;
    }
  }

  @override
  Future<List<dynamic>> getConnectedDevices() async {
    try {
      // WinBle没有直接获取已连接设备的方法，这里返回空列表
      // 实际使用中需要维护一个已连接设备列表
      return [];
    } catch (e) {
      debugPrint('WinBle获取已连接设备失败: $e');
      rethrow;
    }
  }

  @override
  Future<BluetoothAdapterState> getAdapterState() async {
    try {
      await WinBle.getBluetoothState();
      // 简化处理：假设状态为on
      return BluetoothAdapterState.on;
    } catch (e) {
      debugPrint('WinBle获取适配器状态失败: $e');
      rethrow;
    }
  }

  @override
  Stream<BluetoothAdapterState> get adapterStateChanged =>
      Stream.value(BluetoothAdapterState.on);

  @override
  Stream<List<dynamic>> get scanResults {
    debugPrint('WinBleAdapter scanResults stream created');
    return WinBle.scanStream.map((device) {
      debugPrint('WinBleAdapter接收到设备: ${device.toString()}');
      return [device];
    });
  }

  @override
  Stream<String> get connectionStateChanged =>
      const Stream.empty(); // 使用设备特定的连接流

  // 实现WinBle特有的方法
  @override
  Future<void> pair(String deviceAddress) async {
    try {
      await WinBle.pair(deviceAddress);
      debugPrint('WinBle配对设备: $deviceAddress');
    } catch (e) {
      debugPrint('WinBle配对设备失败: $e');
      rethrow;
    }
  }

  @override
  Future<void> unPair(String deviceAddress) async {
    try {
      await WinBle.unPair(deviceAddress);
      debugPrint('WinBle取消配对设备: $deviceAddress');
    } catch (e) {
      debugPrint('WinBle取消配对设备失败: $e');
      rethrow;
    }
  }

  @override
  Future<bool> canPair(String deviceAddress) async {
    try {
      return await WinBle.canPair(deviceAddress);
    } catch (e) {
      debugPrint('WinBle检查配对能力失败: $e');
      rethrow;
    }
  }

  @override
  Future<bool> isPaired(String deviceAddress) async {
    try {
      return await WinBle.isPaired(deviceAddress);
    } catch (e) {
      debugPrint('WinBle检查配对状态失败: $e');
      rethrow;
    }
  }

  @override
  Future<List<dynamic>> discoverServices(String deviceAddress) async {
    try {
      return await WinBle.discoverServices(deviceAddress);
    } catch (e) {
      debugPrint('WinBle发现服务失败: $e');
      rethrow;
    }
  }

  @override
  Future<List<dynamic>> discoverCharacteristics(
      String deviceAddress, String serviceId) async {
    try {
      return await WinBle.discoverCharacteristics(
          address: deviceAddress, serviceId: serviceId);
    } catch (e) {
      debugPrint('WinBle发现特征失败: $e');
      rethrow;
    }
  }

  @override
  Future<List<int>> readCharacteristic(
      String deviceAddress, String serviceId, String characteristicId) async {
    try {
      return await WinBle.read(
          address: deviceAddress,
          serviceId: serviceId,
          characteristicId: characteristicId);
    } catch (e) {
      debugPrint('WinBle读取特征失败: $e');
      rethrow;
    }
  }

  @override
  Future<void> writeCharacteristic(String deviceAddress, String serviceId,
      String characteristicId, List<int> data,
      {bool writeWithResponse = false}) async {
    try {
      await WinBle.write(
        address: deviceAddress,
        service: serviceId,
        characteristic: characteristicId,
        data: Uint8List.fromList(data),
        writeWithResponse: writeWithResponse,
      );
    } catch (e) {
      debugPrint('WinBle写入特征失败: $e');
      rethrow;
    }
  }

  @override
  Future<void> subscribeToCharacteristic(
      String deviceAddress, String serviceId, String characteristicId) async {
    try {
      await WinBle.subscribeToCharacteristic(
        address: deviceAddress,
        serviceId: serviceId,
        characteristicId: characteristicId,
      );
    } catch (e) {
      debugPrint('WinBle订阅特征失败: $e');
      rethrow;
    }
  }

  @override
  Future<void> unSubscribeFromCharacteristic(
      String deviceAddress, String serviceId, String characteristicId) async {
    try {
      await WinBle.unSubscribeFromCharacteristic(
        address: deviceAddress,
        serviceId: serviceId,
        characteristicId: characteristicId,
      );
    } catch (e) {
      debugPrint('WinBle取消订阅特征失败: $e');
      rethrow;
    }
  }
}

/// 跨平台蓝牙服务
/// 为不同平台提供统一的蓝牙接口
class BluetoothService extends GetxController {
  static BluetoothService get to => Get.find();

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

  // 平台特定的控制器
  StreamSubscription? _scanSubscription;
  StreamSubscription? _adapterSubscription;
  Timer? _scanTimeoutTimer;
  final Map<String, StreamSubscription> _deviceConnectionSubscriptions = {};

  // 蓝牙适配器实例
  late BluetoothAdapter _adapter;

  @override
  void onInit() {
    super.onInit();
    initBluetooth();
  }

  @override
  void onClose() {
    _scanTimeoutTimer?.cancel();
    _scanSubscription?.cancel();
    _adapterSubscription?.cancel();
    isScanning.value = false;

    // 清理所有设备连接订阅
    for (var subscription in _deviceConnectionSubscriptions.values) {
      subscription.cancel();
    }
    _deviceConnectionSubscriptions.clear();

    super.onClose();
  }

  /// 初始化蓝牙
  Future<void> initBluetooth() async {
    try {
      // 根据平台选择适配器
      if (Platform.isWindows) {
        _adapter = WinBleAdapter();
      } else {
        _adapter = FlutterBluePlusAdapter();
      }

      // 初始化适配器
      await _adapter.init();

      if (Platform.isWindows) {
        await _initWindowsBluetooth();
      } else {
        await _initMobileBluetooth();
      }
    } catch (e) {
      debugPrint('初始化蓝牙失败: $e');
      Get.snackbar('错误', '初始化蓝牙失败: $e', snackPosition: SnackPosition.BOTTOM);
    }
  }

  /// 初始化Windows蓝牙
  Future<void> _initWindowsBluetooth() async {
    try {
      // 检查蓝牙适配器状态
      final adapterStateResult = await _adapter.getAdapterState();
      adapterState.value = adapterStateResult;

      debugPrint('Windows蓝牙状态: $adapterStateResult');

      // 监听适配器状态变化
      _adapterSubscription = _adapter.adapterStateChanged.listen((state) {
        adapterState.value = state;
      });
    } catch (e) {
      debugPrint('Windows蓝牙初始化失败: $e');
      adapterState.value = BluetoothAdapterState.unavailable;
      Get.snackbar('错误', 'Windows蓝牙初始化失败: $e',
          snackPosition: SnackPosition.BOTTOM);
    }
  }

  /// 初始化移动端蓝牙
  Future<void> _initMobileBluetooth() async {
    // 监听蓝牙适配器状态
    _adapterSubscription = _adapter.adapterStateChanged.listen((state) {
      adapterState.value = state;
      if (state != BluetoothAdapterState.on) {
        discoveredDevices.clear();
        scanResults.clear();
        isScanning.value = false;
      }
    });

    // 获取当前状态
    final currentState = await _adapter.getAdapterState();
    adapterState.value = currentState;

    // 获取已连接的设备
    await updateConnectedDevices();
  }

  /// 开始扫描设备
  Future<void> startScan({Duration? timeout}) async {
    if (isScanning.value) {
      debugPrint('扫描已在进行中');
      return;
    }

    try {
      await _startScan(timeout);
    } catch (e) {
      debugPrint('开始扫描失败: $e');
      Get.snackbar('错误', '开始扫描失败: $e', snackPosition: SnackPosition.BOTTOM);
    }
  }

  /// 通用蓝牙扫描（适用于所有平台）
  Future<void> _startScan(Duration? timeout) async {
    isScanning.value = true;
    _scanTimeoutTimer?.cancel();
    await _scanSubscription?.cancel();
    _scanSubscription = null;
    // 不要清空设备列表，让设备累计
    // discoveredDevices.clear();
    // scanResults.clear();

    try {
      debugPrint('${Platform.isWindows ? "Windows" : "Mobile"}蓝牙扫描已启动');

      // 使用适配器进行扫描
      await _adapter.startScan();

      // 监听扫描结果
      _scanSubscription = _adapter.scanResults.listen((results) {
        if (Platform.isWindows) {
          debugPrint('Windows平台处理扫描结果，设备数量: ${results.length}');

          // Windows平台：win_ble返回设备流，需要累计设备而不是清空
          for (var device in results) {
            debugPrint('处理设备: ${device.toString()}');
            try {
              // 安全地访问BleDevice属性，避免类型错误
              String deviceAddress = '';
              String deviceName = '未知设备';
              int rssi = -50;
              bool isConnectable = false; // 添加可连接状态
              List<String> serviceUuidStrings = []; // 服务UUID字符串列表
              Map<int, List<int>> manufacturerData = {}; // 制造商数据

              // 打印原始设备对象信息，便于调试
              debugPrint('===== Windows BLE设备原始数据 =====');
              debugPrint('设备对象类型: ${device.runtimeType}');
              debugPrint('设备对象字符串: $device');

              try {
                // 安全地处理address属性
                if (device.address != null) {
                  deviceAddress = device.address.toString();
                } else {
                  deviceAddress = device.toString();
                }
                debugPrint('设备地址: $deviceAddress');

                // 安全地处理name属性 - 优先使用name，如果为空或null则保持"未知设备"
                if (device.name != null && device.name.toString().isNotEmpty) {
                  deviceName = device.name.toString();
                  debugPrint('从device.name获取到设备名称: $deviceName');
                } else {
                  debugPrint('device.name为空或null，设备名称保持默认: $deviceName');
                }

                // 安全地处理rssi属性，确保是int类型
                if (device.rssi != null) {
                  if (device.rssi is int) {
                    rssi = device.rssi as int;
                  } else if (device.rssi is String) {
                    try {
                      rssi = int.parse(device.rssi.toString());
                    } catch (e) {
                      debugPrint('RSSI字符串转换失败: ${device.rssi}');
                      rssi = -50;
                    }
                  } else {
                    rssi = -50;
                  }
                }

                // 安全地处理服务UUID
                try {
                  if (device.serviceUuids != null) {
                    if (device.serviceUuids is List) {
                      serviceUuidStrings = device.serviceUuids
                          .map((uuid) => uuid.toString())
                          .toList();
                    }
                  }
                } catch (e) {
                  debugPrint('服务UUID获取失败: $e');
                }

                // 安全地处理制造商数据
                try {
                  debugPrint('===== 开始获取制造商数据 =====');
                  debugPrint('设备对象类型: ${device.runtimeType}');

                  // 打印设备对象的完整结构
                  debugPrint('设备对象详细信息:');
                  try {
                    // 尝试打印所有可能的属性
                    var commonProps = [
                      'address',
                      'name',
                      'rssi',
                      'manufacturerData',
                      'advertisementData',
                      'advertisingData',
                      'manufData',
                      'advData',
                      'data',
                      'serviceUuids',
                      'connectable'
                    ];
                    for (var prop in commonProps) {
                      try {
                        var value = _getProperty(device, prop);
                        if (value != null) {
                          debugPrint('  $prop: $value (${value?.runtimeType})');
                          // 如果是制造商数据，尝试打印具体内容
                          if (prop.contains('manufacturer') ||
                              prop.contains('adv') ||
                              prop.contains('data')) {
                            if (value is Map) {
                              debugPrint('    Map内容:');
                              value.forEach((k, v) {
                                debugPrint('      键: $k, 值: $v');
                                if (v is List) {
                                  final hexStr = v
                                      .map((b) =>
                                          b.toRadixString(16).padLeft(2, '0'))
                                      .join(' ');
                                  debugPrint('      16进制: $hexStr');
                                }
                              });
                            } else if (value is List) {
                              final hexStr = value
                                  .map((b) =>
                                      b.toRadixString(16).padLeft(2, '0'))
                                  .join(' ');
                              debugPrint('    List内容(16进制): $hexStr');
                              debugPrint('    List内容(10进制): $value');
                            }
                          }
                        }
                      } catch (e) {
                        // 静默忽略访问失败的属性
                      }
                    }
                  } catch (e) {
                    debugPrint('打印设备属性失败: $e');
                  }

                  // 尝试多种方式获取制造商数据
                  List<String> triedProps = [];

                  // 方法1: 直接属性访问
                  var props = [
                    'manufacturerData',
                    'advertisementData',
                    'advertisingData',
                    'manufData',
                    'advData',
                    'data'
                  ];

                  for (var prop in props) {
                    triedProps.add(prop);
                    try {
                      var value = _getProperty(device, prop);
                      if (value != null) {
                        debugPrint(
                            '找到属性 $prop: $value (类型: ${value.runtimeType})');
                        if (_extractManufacturerData(value, manufacturerData)) {
                          debugPrint(
                              '成功从 $prop 提取制造商数据，长度: ${manufacturerData.length}');
                          break;
                        }
                      }
                    } catch (e) {
                      debugPrint('访问属性 $prop 失败: $e');
                    }
                  }

                  debugPrint('尝试的属性: $triedProps');
                  debugPrint('最终制造商数据长度: ${manufacturerData.length}');

                  // 如果还是没有找到制造商数据，尝试其他可能的位置
                  if (manufacturerData.isEmpty) {
                    debugPrint('尝试从其他可能的位置获取制造商数据...');

                    // 尝试从advertisementData的嵌套结构中获取
                    try {
                      var advData = _getProperty(device, 'advertisementData');
                      if (advData != null && advData is Map) {
                        debugPrint('advertisementData结构: $advData');
                        if (advData.containsKey('manufacturerData')) {
                          var manufData = advData['manufacturerData'];
                          if (manufData != null) {
                            debugPrint(
                                '从advertisementData.manufacturerData获取: $manufData');
                            if (_extractManufacturerData(
                                manufData, manufacturerData)) {
                              debugPrint(
                                  '成功从advertisementData.manufacturerData提取制造商数据，长度: ${manufacturerData.length}');
                            }
                          }
                        }
                      }
                    } catch (e) {
                      debugPrint('从advertisementData获取制造商数据失败: $e');
                    }
                  }
                } catch (e) {
                  debugPrint('制造商数据获取失败: $e');
                }

                // 判断设备是否可连接
                isConnectable = _isDeviceLikelyConnectable(
                    device, serviceUuidStrings, manufacturerData);

                debugPrint(
                    '设备信息: 地址=$deviceAddress, 名称=$deviceName, RSSI=$rssi, 可连接=$isConnectable');
                debugPrint('制造商数据长度: ${manufacturerData.length}');
                debugPrint('服务UUID数量: ${serviceUuidStrings.length}');
              } catch (e) {
                debugPrint('设备属性访问错误: $e');
                // 设备属性访问错误，使用默认值
              }

              // 检查设备是否已存在
              final existingResultIndex = scanResults.indexWhere(
                  (result) => result.device.remoteId.str == deviceAddress);

              if (existingResultIndex >= 0) {
                // 更新现有设备的信号强度和时间戳
                final updatedResults = List<ScanResult>.from(scanResults);

                // 获取现有设备的名称，如果新扫描到的名称不为空则更新
                String finalDeviceName = deviceName;
                if (finalDeviceName == '未知设备' || finalDeviceName.isEmpty) {
                  // 尝试保持之前的名称
                  final existingName = updatedResults[existingResultIndex]
                      .advertisementData
                      .advName;
                  if (existingName.isNotEmpty && existingName != '未知设备') {
                    finalDeviceName = existingName;
                    debugPrint('保持现有设备名称: $finalDeviceName');
                  }
                } else {
                  debugPrint('更新设备名称为: $finalDeviceName');
                }

                // 如果设备名称发生了变化，也更新设备名称
                final updatedDevice = BluetoothDevice(
                  remoteId: updatedResults[existingResultIndex].device.remoteId,
                );
                // 创建更新后的advertisementData，保持可连接状态和服务UUID
                final updatedAdvData = AdvertisementData(
                  advName: finalDeviceName, // 使用最终的设备名称
                  txPowerLevel: updatedResults[existingResultIndex]
                      .advertisementData
                      .txPowerLevel,
                  appearance: updatedResults[existingResultIndex]
                      .advertisementData
                      .appearance,
                  connectable: isConnectable, // 更新可连接状态
                  manufacturerData: manufacturerData.isNotEmpty
                      ? manufacturerData
                      : updatedResults[existingResultIndex]
                          .advertisementData
                          .manufacturerData,
                  serviceData: updatedResults[existingResultIndex]
                      .advertisementData
                      .serviceData,
                  serviceUuids: [], // 暂时使用空列表，避免类型错误
                );

                updatedResults[existingResultIndex] = ScanResult(
                  device: updatedDevice,
                  advertisementData: updatedAdvData,
                  rssi: rssi,
                  timeStamp: DateTime.now(),
                );
                scanResults.value = updatedResults;

                debugPrint('更新设备 $deviceAddress，最终名称: $finalDeviceName');
              } else {
                // 创建新的ScanResult对象并添加到列表
                final newResults = List<ScanResult>.from(scanResults);
                final bluetoothDevice = BluetoothDevice(
                  remoteId: DeviceIdentifier(deviceAddress),
                );

                final scanResult = ScanResult(
                  device: bluetoothDevice,
                  advertisementData: AdvertisementData(
                    advName: deviceName,
                    txPowerLevel: null,
                    appearance: 0,
                    connectable: isConnectable, // 使用实际的可连接状态
                    manufacturerData: manufacturerData,
                    serviceData: {},
                    serviceUuids: [], // 暂时使用空列表，避免类型错误
                  ),
                  rssi: rssi,
                  timeStamp: DateTime.now(),
                );

                newResults.add(scanResult);
                scanResults.value = newResults;

                debugPrint('新增设备 $deviceAddress，名称: $deviceName');
              }
            } catch (e) {
              // 转换设备失败
            }
          }

          // 更新发现的设备列表（从scanResults中提取）
          final deviceList =
              scanResults.map((result) => result.device).toList();
          discoveredDevices.value = deviceList;
        } else {
          // 移动端：flutter_blue_plus直接返回ScanResult列表
          if (results is List<ScanResult>) {
            scanResults.value = results;
            discoveredDevices.value =
                results.map((result) => result.device).toList();
          }
        }
      }, onError: (Object error, StackTrace stackTrace) {
        debugPrint('扫描结果监听失败: $error');
        isScanning.value = false;
        _scanTimeoutTimer?.cancel();
      }, cancelOnError: false);

      debugPrint('${Platform.isWindows ? "Windows" : "Mobile"}蓝牙扫描正常启动');

      // 处理扫描超时
      if (timeout != null) {
        _scanTimeoutTimer = Timer(timeout, () => stopScan());
      }
    } catch (e) {
      isScanning.value = false;
      debugPrint('${Platform.isWindows ? "Windows" : "Mobile"}蓝牙扫描启动失败: $e');
      Get.snackbar(
          '错误', '${Platform.isWindows ? "Windows" : "Mobile"}蓝牙扫描启动失败: $e',
          snackPosition: SnackPosition.BOTTOM);
      throw Exception(
          '${Platform.isWindows ? "Windows" : "Mobile"}蓝牙扫描启动失败: $e');
    }
  }

  /// 创建模拟设备用于Windows测试
  // Future<void> _createSimulatedDevices() async {
  //   await Future.delayed(const Duration(seconds: 2));
  //   try {
  //     debugPrint('Windows平台暂时不创建模拟设备，建议使用真实设备测试');
  //   } catch (e) {
  //     debugPrint('Windows蓝牙初始化失败: $e');
  //   }
  // }

  /// 停止扫描
  Future<void> stopScan() async {
    if (!isScanning.value) return;

    try {
      await _adapter.stopScan();
      debugPrint('蓝牙扫描已停止');
    } catch (e) {
      debugPrint('停止扫描失败: $e');
    } finally {
      _scanTimeoutTimer?.cancel();
      _scanTimeoutTimer = null;
      await _scanSubscription?.cancel();
      _scanSubscription = null;
      isScanning.value = false;
    }
  }

  /// 连接设备
  Future<void> connectDevice(BluetoothDevice device) async {
    try {
      if (Platform.isWindows) {
        // Windows平台：使用win_ble的连接方式
        await _adapter.connect(device.remoteId.str);

        // 监听连接状态变化
        final connectionStream = WinBle.connectionStreamOf(device.remoteId.str);
        _deviceConnectionSubscriptions[device.remoteId.str] =
            connectionStream.listen((isConnected) {
          if (isConnected) {
            if (!connectedDevices.contains(device)) {
              connectedDevices.add(device);
            }
            Get.snackbar('成功', '设备连接成功', snackPosition: SnackPosition.BOTTOM);
          } else {
            connectedDevices.remove(device);
          }
        });
      } else {
        // 移动端：使用flutter_blue_plus的连接方式
        await device.connect(timeout: const Duration(seconds: 10));
        if (!connectedDevices.contains(device)) {
          connectedDevices.add(device);
        }
        // 监听移动端连接状态，及时反映断开
        try {
          _deviceConnectionSubscriptions[device.remoteId.str]?.cancel();
        } catch (_) {}
        _deviceConnectionSubscriptions[device.remoteId.str] =
            device.connectionState.listen((state) {
          if (state == BluetoothConnectionState.connected) {
            if (!connectedDevices.contains(device)) {
              connectedDevices.add(device);
            }
          } else if (state == BluetoothConnectionState.disconnected) {
            connectedDevices.remove(device);
          }
        });

        Get.snackbar('成功', '设备连接成功', snackPosition: SnackPosition.BOTTOM);
      }
    } catch (e) {
      debugPrint('连接设备失败: $e');
      Get.snackbar('错误', '连接设备失败: $e', snackPosition: SnackPosition.BOTTOM);
    }
  }

  /// 断开设备连接
  Future<void> disconnectDevice(BluetoothDevice device) async {
    try {
      if (Platform.isWindows) {
        // Windows平台：断开连接并清理订阅
        await _adapter.disconnect(device.remoteId.str);
        _deviceConnectionSubscriptions[device.remoteId.str]?.cancel();
        _deviceConnectionSubscriptions.remove(device.remoteId.str);
      } else {
        // 移动端：断开连接
        await device.disconnect();
      }

      connectedDevices.remove(device);
    } catch (e) {
      // 断开设备连接失败
    }
  }

  /// 更新已连接设备列表
  Future<void> updateConnectedDevices() async {
    try {
      await _adapter.getConnectedDevices();
      // 注意：这里需要将适配器的设备列表转换为BluetoothDevice格式
      // connectedDevices.value = connectedDevicesResult.map((device) => _convertFromAdapterDevice(device)).toList();
    } catch (e) {
      debugPrint('更新已连接设备列表失败: $e');
    }
  }

  /// 获取扫描结果
  ScanResult? getScanResult(BluetoothDevice device) {
    return scanResults.firstWhereOrNull(
      (result) => result.device.remoteId == device.remoteId,
    );
  }

  /// 检查设备是否已连接
  bool isDeviceConnected(BluetoothDevice device) {
    return connectedDevices.any((d) => d.remoteId == device.remoteId);
  }

  /// 启用蓝牙
  Future<void> turnOnBluetooth() async {
    if (Platform.isWindows) {
      Get.snackbar('提示', '请在系统设置中手动启用蓝牙', snackPosition: SnackPosition.BOTTOM);
      return;
    }

    try {
      if (Platform.isAndroid) {
        // 对于移动端适配器，这里需要特殊处理
        // 因为FlutterBluePlus.turnOn()不是适配器方法的一部分
        await FlutterBluePlus.turnOn();
      }
    } catch (e) {
      debugPrint('启用蓝牙失败: $e');
      Get.snackbar('错误', '启用蓝牙失败，请手动开启', snackPosition: SnackPosition.BOTTOM);
    }
  }

  /// 获取平台信息
  String getPlatformInfo() {
    if (Platform.isWindows) {
      return 'Windows (WinBLE)';
    } else if (Platform.isAndroid) {
      return 'Android (FlutterBluePlus)';
    } else if (Platform.isIOS) {
      return 'iOS (FlutterBluePlus)';
    } else {
      return '未知平台';
    }
  }

  /// 通过设备地址发现服务（用于遥控透传）
  Future<List<dynamic>> discoverServicesByAddress(String deviceAddress) async {
    try {
      if (Platform.isWindows) {
        return await _adapter.discoverServices(deviceAddress);
      } else {
        // 移动端：直接通过FlutterBluePlus发现服务（要求设备已连接）
        final device = _findDeviceByAddress(deviceAddress);
        if (device == null) {
          throw UnsupportedError('未找到设备，无法发现服务: $deviceAddress');
        }
        final services = await device.discoverServices();
        return services; // 返回动态列表，调用方做解析
      }
    } catch (e) {
      debugPrint('发现服务失败($deviceAddress): $e');
      rethrow;
    }
  }

  /// 通过设备地址与服务ID发现特征（用于遥控透传）
  Future<List<dynamic>> discoverCharacteristicsByAddress(
      String deviceAddress, String serviceId) async {
    try {
      if (Platform.isWindows) {
        return await _adapter.discoverCharacteristics(deviceAddress, serviceId);
      } else {
        final device = _findDeviceByAddress(deviceAddress);
        if (device == null) {
          throw UnsupportedError('未找到设备，无法发现特征: $deviceAddress');
        }
        final services = await device.discoverServices();
        for (final svc in services) {
          try {
            final id = svc.uuid.toString();
            if (_uuidLikeEquals(id, serviceId)) {
              return svc.characteristics;
            }
          } catch (_) {}
        }
        return <dynamic>[];
      }
    } catch (e) {
      debugPrint('发现特征失败($deviceAddress/$serviceId): $e');
      rethrow;
    }
  }

  /// 通过设备地址向指定服务/特征写入（用于遥控透传）
  Future<void> writeByAddress(
    String deviceAddress,
    String serviceId,
    String characteristicId,
    List<int> data, {
    bool writeWithResponse = false,
  }) async {
    try {
      // 兼容传入的 service/characteristic 字符串中包含调试信息的情况
      final normalizedServiceId = _extractUuidFromVerboseString(serviceId);
      final normalizedCharId = _extractUuidFromVerboseString(characteristicId);
      if (Platform.isWindows) {
        await _adapter.writeCharacteristic(
          deviceAddress,
          normalizedServiceId,
          normalizedCharId,
          data,
          writeWithResponse: writeWithResponse,
        );
      } else {
        final device = _findDeviceByAddress(deviceAddress);
        if (device == null) {
          throw UnsupportedError('未找到设备，无法写入: $deviceAddress');
        }
        final services = await device.discoverServices();
        for (final svc in services) {
          try {
            final sid = svc.uuid.toString();
            if (_uuidLikeEquals(sid, normalizedServiceId)) {
              for (final ch in svc.characteristics) {
                final cid = ch.uuid.toString();
                if (_uuidLikeEquals(cid, normalizedCharId)) {
                  await ch.write(Uint8List.fromList(data),
                      withoutResponse: !writeWithResponse);
                  return;
                }
              }
            }
          } catch (_) {}
        }
        throw UnsupportedError('未找到目标特征: $characteristicId');
      }
    } catch (e) {
      debugPrint('写入失败($deviceAddress/$serviceId/$characteristicId): $e');
      rethrow;
    }
  }

  /// 订阅通知（Windows 走 WinBle，移动端走FlutterBlue特征）
  Stream<List<int>>? subscribeNotifyByAddress(
      String deviceAddress, String serviceId, String characteristicId) {
    try {
      if (Platform.isWindows) {
        // Windows: 发起订阅，并通过轮询读取构建一个值流
        return Stream<List<int>>.multi((controller) async {
          List<int>? last;
          Timer? timer;
          try {
            await _adapter.subscribeToCharacteristic(
                deviceAddress, serviceId, characteristicId);
          } catch (_) {}

          Future<void> poll() async {
            try {
              final data = await readByAddress(
                  deviceAddress, serviceId, characteristicId);
              if (data.isNotEmpty) {
                if (last == null || !listEquals(last, data)) {
                  last = List<int>.from(data);
                  controller.add(data);
                }
              }
            } catch (e) {
              controller.addError(e);
            }
          }

          // 先立即读一次
          await poll();
          // 每250ms轮询一次
          timer = Timer.periodic(const Duration(milliseconds: 250), (_) async {
            await poll();
          });

          controller.onCancel = () async {
            timer?.cancel();
            try {
              await _adapter.unSubscribeFromCharacteristic(
                  deviceAddress, serviceId, characteristicId);
            } catch (_) {}
          };
        });
      } else {
        final device = _findDeviceByAddress(deviceAddress);
        if (device == null) return null;
        // 使用flutter_blue_plus发现对应特征并订阅
        return Stream<List<int>>.multi((controller) async {
          try {
            final services = await device.discoverServices();
            for (final svc in services) {
              final sid = svc.uuid.toString();
              if (_uuidLikeEquals(sid, serviceId)) {
                for (final ch in svc.characteristics) {
                  final cid = ch.uuid.toString();
                  if (_uuidLikeEquals(cid, characteristicId)) {
                    await ch.setNotifyValue(true);
                    final sub = ch.onValueReceived.listen(controller.add,
                        onError: controller.addError, onDone: controller.close);
                    controller.onCancel = () async {
                      await ch.setNotifyValue(false);
                      await sub.cancel();
                    };
                    return; // 成功建立监听
                  }
                }
              }
            }
            controller.close();
          } catch (e) {
            controller.addError(e);
            controller.close();
          }
        });
      }
    } catch (e) {
      debugPrint('订阅通知失败: $e');
      return null;
    }
  }

  Future<void> unSubscribeNotifyByAddress(
      String deviceAddress, String serviceId, String characteristicId) async {
    try {
      if (Platform.isWindows) {
        await _adapter.unSubscribeFromCharacteristic(
            deviceAddress, serviceId, characteristicId);
      } else {
        final device = _findDeviceByAddress(deviceAddress);
        if (device == null) return;
        final services = await device.discoverServices();
        for (final svc in services) {
          final sid = svc.uuid.toString();
          if (_uuidLikeEquals(sid, serviceId)) {
            for (final ch in svc.characteristics) {
              final cid = ch.uuid.toString();
              if (_uuidLikeEquals(cid, characteristicId)) {
                await ch.setNotifyValue(false);
                return;
              }
            }
          }
        }
      }
    } catch (e) {
      debugPrint('取消通知失败: $e');
    }
  }

  /// 读取特征值（跨平台）
  Future<List<int>> readByAddress(
      String deviceAddress, String serviceId, String characteristicId) async {
    try {
      if (Platform.isWindows) {
        return await _adapter.readCharacteristic(
            deviceAddress, serviceId, characteristicId);
      } else {
        final device = _findDeviceByAddress(deviceAddress);
        if (device == null) return <int>[];
        final services = await device.discoverServices();
        for (final svc in services) {
          final sid = svc.uuid.toString();
          if (_uuidLikeEquals(sid, serviceId)) {
            for (final ch in svc.characteristics) {
              final cid = ch.uuid.toString();
              if (_uuidLikeEquals(cid, characteristicId)) {
                return await ch.read();
              }
            }
          }
        }
        return <int>[];
      }
    } catch (e) {
      debugPrint('读取失败($deviceAddress/$serviceId/$characteristicId): $e');
      return <int>[];
    }
  }

  /// 查找透传服务与可写/通知特征（默认匹配 FFF0 服务）
  /// 返回 { 'serviceId': ..., 'writeCharId': ..., 'notifyCharId': ... }
  Future<Map<String, String>?> findTransparentUuidsByAddress(
    String deviceAddress, {
    String serviceUuidHint = 'fff0',
  }) async {
    try {
      // 发现服务
      final services = await discoverServicesByAddress(deviceAddress);

      String? normalizeId(dynamic obj) => _extractUuidFromAny(obj);

      // 遍历服务，优先寻找匹配 serviceUuidHint 的服务
      for (final svc in services) {
        final sid = normalizeId(svc);
        if (sid == null) continue;
        if (_uuidLikeEquals(sid, serviceUuidHint)) {
          // 发现特征
          final characteristics = Platform.isWindows
              ? await _adapter.discoverCharacteristics(deviceAddress, sid)
              : _safeMobileCharacteristicsList(svc);

          String? writeId;
          String? notifyId;
          for (final ch in characteristics) {
            final cid = normalizeId(ch);
            if (cid == null) continue;
            if (_isCharacteristicWritable(ch) && writeId == null) {
              writeId = cid;
            }
            if (_hasCharacteristicNotify(ch) && notifyId == null) {
              notifyId = cid;
            }
          }

          if (writeId != null || notifyId != null) {
            return {
              'serviceId': sid,
              if (writeId != null) 'writeCharId': writeId,
              if (notifyId != null) 'notifyCharId': notifyId,
            };
          }
        }
      }
      // 如果没匹配到 serviceUuidHint，使用降级：选择第一个拥有可写/通知特征的服务
      for (final svc in services) {
        final sidRaw = normalizeId(svc);
        if (sidRaw == null) continue;
        final characteristics = Platform.isWindows
            ? await _adapter.discoverCharacteristics(deviceAddress, sidRaw)
            : _safeMobileCharacteristicsList(svc);
        String? writeId;
        String? notifyId;
        for (final ch in characteristics) {
          final cid = normalizeId(ch);
          if (cid == null) continue;
          if (_isCharacteristicWritable(ch) && writeId == null) writeId = cid;
          if (_hasCharacteristicNotify(ch) && notifyId == null) notifyId = cid;
        }
        if (writeId != null || notifyId != null) {
          return {
            'serviceId': sidRaw,
            if (writeId != null) 'writeCharId': writeId,
            if (notifyId != null) 'notifyCharId': notifyId,
          };
        }
      }
      return null;
    } catch (e) {
      debugPrint('查找透传UUID失败($deviceAddress): $e');
      return null;
    }
  }

  // 移动端：安全获取服务的特征列表
  List<dynamic> _safeMobileCharacteristicsList(dynamic service) {
    try {
      final chars = service.characteristics;
      if (chars is List) return chars;
    } catch (_) {}
    return const <dynamic>[];
  }

  // 判断特征是否可写（跨平台）
  bool _isCharacteristicWritable(dynamic ch) {
    try {
      if (Platform.isWindows) {
        final canWrite = _getProperty(ch, 'canWrite') == true ||
            _getProperty(ch, 'write') == true ||
            _getProperty(ch, 'isWritable') == true ||
            _getProperty(ch, 'writeWithResponse') == true ||
            _getProperty(ch, 'writeWithoutResponse') == true;

        final props = _getProperty(ch, 'properties');
        final fromProps =
            _propContains(props, ['write', 'writeWithoutResponse']);
        return canWrite || fromProps;
      } else {
        // FlutterBluePlus Characteristic
        try {
          return ch.properties.write == true ||
              ch.properties.writeWithoutResponse == true;
        } catch (_) {
          return false;
        }
      }
    } catch (_) {
      return false;
    }
  }

  // 判断特征是否可读
  bool _hasCharacteristicRead(dynamic ch) {
    try {
      if (Platform.isWindows) {
        if (_getProperty(ch, 'read') == true ||
            _getProperty(ch, 'canRead') == true) return true;
        final props = _getProperty(ch, 'properties');
        if (_propContains(props, ['read'])) return true;
        return false;
      } else {
        return ch.properties.read == true;
      }
    } catch (_) {
      return false;
    }
  }

  // 判断特征是否支持通知/指示
  bool _hasCharacteristicNotify(dynamic ch) {
    try {
      if (Platform.isWindows) {
        if (_getProperty(ch, 'notify') == true ||
            _getProperty(ch, 'canNotify') == true ||
            _getProperty(ch, 'indicate') == true) return true;
        final props = _getProperty(ch, 'properties');
        if (_propContains(props, ['notify', 'indicate'])) return true;
        return false;
      } else {
        return ch.properties.notify == true || ch.properties.indicate == true;
      }
    } catch (_) {
      return false;
    }
  }

  // 判断 properties 中是否包含指定能力（兼容 Map 或 List/字符串）
  bool _propContains(dynamic props, List<String> keys) {
    try {
      if (props == null) return false;
      final keySet = keys.map((e) => e.toLowerCase()).toSet();
      if (props is Map) {
        for (final entry in props.entries) {
          final k = entry.key.toString().toLowerCase();
          if (keySet.contains(k) && entry.value == true) return true;
        }
        return false;
      }
      if (props is List) {
        for (final v in props) {
          final s = v.toString().toLowerCase();
          if (keySet.contains(s)) return true;
        }
        return false;
      }
      final s = props.toString().toLowerCase();
      for (final k in keySet) {
        if (s.contains(k)) return true;
      }
      return false;
    } catch (_) {
      return false;
    }
  }

  // 从任意对象中尽可能提取 UUID 字符串
  String? _extractUuidFromAny(dynamic obj) {
    try {
      // 优先直接访问动态属性（FlutterBluePlus的service/characteristic支持）
      final directUuid = obj.uuid;
      if (directUuid != null) return directUuid.toString();
    } catch (_) {}
    try {
      final directId = obj.id;
      if (directId != null) return directId.toString();
    } catch (_) {}
    try {
      final uuid = _getProperty(obj, 'uuid');
      if (uuid != null) return uuid.toString();
    } catch (_) {}
    try {
      final id = _getProperty(obj, 'id');
      if (id != null) return id.toString();
    } catch (_) {}
    try {
      final s = obj?.toString();
      if (s == null) return null;
      // 从类似 GUID 字符串中提取
      final lower = s.toLowerCase();
      if (lower.contains('uuid') || lower.contains('-')) return s;
      // 直接返回字符串（如仅16位或32位uuid）
      return s;
    } catch (_) {
      return null;
    }
  }

  /// 列出服务ID（字符串）
  Future<List<String>> listServiceIdsByAddress(String deviceAddress) async {
    final list = <String>[];
    try {
      final services = await discoverServicesByAddress(deviceAddress);
      for (final svc in services) {
        final sid = _extractUuidFromAny(svc);
        if (sid != null) list.add(sid);
      }
    } catch (e) {
      debugPrint('列出服务ID失败($deviceAddress): $e');
    }
    return list;
  }

  /// 列出某服务下的全部特征及其属性（读/写/通知）
  Future<List<Map<String, dynamic>>> listCharacteristicsWithPropertiesByAddress(
      String deviceAddress,
      {String serviceUuidHint = 'fff0'}) async {
    final result = <Map<String, dynamic>>[];
    try {
      // 找到服务ID
      final services = await discoverServicesByAddress(deviceAddress);
      String? normalizeId(dynamic obj) {
        try {
          final uuid = _getProperty(obj, 'uuid');
          if (uuid != null) return uuid.toString();
        } catch (_) {}
        try {
          final id = _getProperty(obj, 'id');
          if (id != null) return id.toString();
        } catch (_) {}
        return obj?.toString();
      }

      for (final svc in services) {
        final sid = normalizeId(svc);
        if (sid == null) continue;
        if (_uuidLikeEquals(sid, serviceUuidHint)) {
          final chars = Platform.isWindows
              ? await _adapter.discoverCharacteristics(deviceAddress, sid)
              : _safeMobileCharacteristicsList(svc);
          for (final ch in chars) {
            final cid = normalizeId(ch);
            if (cid == null) continue;
            result.add({
              'uuid': cid,
              'read': _hasCharacteristicRead(ch),
              'write': _isCharacteristicWritable(ch),
              'notify': _hasCharacteristicNotify(ch),
            });
          }
          break;
        }
      }
    } catch (e) {
      debugPrint('列出特征属性失败($deviceAddress): $e');
    }
    return result;
  }

  /// 辅助：根据地址在当前已知设备中查找设备
  BluetoothDevice? _findDeviceByAddress(String deviceAddress) {
    final foundConnected = connectedDevices.firstWhereOrNull(
        (d) => d.remoteId.str.toLowerCase() == deviceAddress.toLowerCase());
    if (foundConnected != null) return foundConnected;
    final foundScanned = scanResults
        .firstWhereOrNull((r) =>
            r.device.remoteId.str.toLowerCase() == deviceAddress.toLowerCase())
        ?.device;
    return foundScanned;
  }

  /// 辅助：宽松判断两个UUID是否等价（支持16位/128位、大小写、带不带连字符）
  bool _uuidLikeEquals(String a, String b) {
    String norm(String x) =>
        x.toLowerCase().replaceAll('-', '').replaceAll('0x', '').trim();
    final na = norm(a);
    final nb = norm(b);
    if (na == nb) return true;
    // 处理16位与128位互转（仅处理标准Base UUID场景）
    String to16(String x) => x.length >= 32 ? x.substring(4, 8) : x;
    return to16(na) == to16(nb);
  }

  /// 从可能包含调试描述的字符串中提取 UUID（支持 16位 或 128位）
  String _extractUuidFromVerboseString(String input) {
    final s = input.trim();
    // 优先匹配 128-bit UUID
    final re128 = RegExp(
        r'[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}');
    final m128 = re128.firstMatch(s);
    if (m128 != null) return m128.group(0)!.toLowerCase();
    // 再匹配 16-bit UUID（常见如 fe59 / fff0）
    final re16 = RegExp(r'\b[0-9a-fA-F]{4}\b');
    final m16 = re16.firstMatch(s);
    if (m16 != null) return m16.group(0)!.toLowerCase();
    // 尝试从键值对中解析（如 serviceUuid: fe59 或 characteristicUuid: ...）
    final kv =
        RegExp(r'(serviceUuid|characteristicUuid)\s*:\s*([0-9a-fA-F-]{4,36})');
    final mkv = kv.firstMatch(s);
    if (mkv != null) return mkv.group(2)!.toLowerCase();
    return s.toLowerCase();
  }

  // 辅助方法：安全获取对象属性
  dynamic _getProperty(dynamic object, String propertyName) {
    try {
      // 对于win_ble的BleDevice对象，尝试直接属性访问
      switch (propertyName) {
        case 'address':
          return object.address;
        case 'name':
          return object.name;
        case 'rssi':
          return object.rssi;
        case 'manufacturerData':
          return object.manufacturerData;
        case 'advertisementData':
          // win_ble可能将广播数据存储在不同的属性中
          if (object.advertisementData != null) {
            return object.advertisementData;
          } else if (object.manufData != null) {
            return object.manufData;
          } else if (object.data != null) {
            return object.data;
          }
          return null;
        case 'serviceUuids':
          return object.serviceUuids;
        case 'connectable':
          return object.connectable;
        default:
          // 尝试动态访问
          try {
            return object.getField(propertyName);
          } catch (e) {
            // 如果getField失败，尝试其他方法
            return null;
          }
      }
    } catch (e) {
      // 尝试通过点号访问嵌套属性
      if (propertyName.contains('.')) {
        var parts = propertyName.split('.');
        var current = object;
        for (var part in parts) {
          if (current == null) break;
          try {
            current = _getProperty(current, part);
          } catch (e) {
            return null;
          }
        }
        return current;
      }
      return null;
    }
  }

  // 辅助方法：从各种数据结构中提取制造商数据
  bool _extractManufacturerData(
      dynamic value, Map<int, List<int>> manufacturerData) {
    try {
      if (value == null) return false;

      debugPrint('尝试提取制造商数据，输入类型: ${value.runtimeType}');

      if (value is Map) {
        // 如果是Map，寻找manufacturerData键
        if (value.containsKey('manufacturerData') &&
            value['manufacturerData'] != null) {
          var manufData = value['manufacturerData'];
          if (manufData is Map) {
            manufacturerData.addAll(Map<int, List<int>>.from(manufData));
            return true;
          }
        }
        // 直接作为制造商数据
        manufacturerData.addAll(Map<int, List<int>>.from(value));
        return true;
      } else if (value is List) {
        // 如果是List，转为Map格式
        manufacturerData[0xFFFF] = value.cast<int>();
        return true;
      }

      debugPrint('无法从该类型提取制造商数据: ${value.runtimeType}');
      return false;
    } catch (e) {
      debugPrint('提取制造商数据失败: $e');
      return false;
    }
  }

  // 辅助方法：判断设备是否可能是可连接的
  bool _isDeviceLikelyConnectable(dynamic device,
      List<String> serviceUuidStrings, Map<int, List<int>> manufacturerData) {
    try {
      // 首先检查是否有明确的connectable属性
      if (device.connectable is bool) {
        return device.connectable as bool;
      }

      // 对于Windows平台，win_ble不提供connectable属性
      // 我们需要基于其他特征来判断

      // 检查设备名称中的关键词
      if (device.name != null && device.name.toString().isNotEmpty) {
        final name = device.name.toString().toLowerCase();
        // 信标类设备通常不可连接
        if (name.contains('beacon') ||
            name.contains('ibeacon') ||
            name.contains('eddystone') ||
            name.contains('tile') ||
            name.contains('tag')) {
          return false;
        }

        // 某些已知的可连接设备类型
        if (name.contains('sensor') ||
            name.contains('thermometer') ||
            name.contains('heart') ||
            name.contains('watch') ||
            name.contains('band') ||
            name.contains('scale') ||
            name.contains('meter')) {
          return true;
        }
      }

      // 检查服务UUID - 某些服务UUID表示设备是可连接的
      for (String uuid in serviceUuidStrings) {
        final lowerUuid = uuid.toLowerCase();
        // 标准GATT服务通常意味着设备是可连接的
        if (lowerUuid.contains('1800') || // Generic Access
            lowerUuid.contains('1801') || // Generic Attribute
            lowerUuid.contains('180a') || // Device Information
            lowerUuid.contains('180d') || // Heart Rate
            lowerUuid.contains('180f') || // Battery Service
            lowerUuid.contains('1805')) {
          // Current Time Service
          return true;
        }
        // iBeacon UUID pattern表示不可连接
        if (lowerUuid.length == 36 && lowerUuid.contains('-')) {
          return false;
        }
      }

      // 检查制造商数据
      // 如果只有制造商数据且没有服务UUID，很可能是广播设备（不可连接）
      if (manufacturerData.isNotEmpty && serviceUuidStrings.isEmpty) {
        // 检查是否是已知的信标格式
        for (var entry in manufacturerData.entries) {
          // Apple iBeacon (0x004C)
          if (entry.key == 0x004C) {
            return false;
          }
          // Google Eddystone (0x00E0)
          if (entry.key == 0x00E0) {
            return false;
          }
          // 如果制造商数据看起来像我们的自定义数据格式（用于监控的设备）
          // 这些设备通常只广播数据，不需要连接
          if (entry.value.length == 7 || entry.value.length == 5) {
            // 可能是我们的监控设备格式
            return false;
          }
        }
      }

      // 如果有服务UUID和制造商数据，可能是可连接设备
      if (serviceUuidStrings.isNotEmpty && manufacturerData.isNotEmpty) {
        return true;
      }

      // 默认情况下，如果我们不确定，假设设备不可连接
      // 这样更保守，避免误判
      return false;
    } catch (e) {
      debugPrint('判断设备可连接性时出错: $e');
      return false; // 出错时默认为不可连接
    }
  }
}
