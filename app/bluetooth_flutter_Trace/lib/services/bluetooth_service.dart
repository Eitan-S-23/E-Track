import 'dart:async';
import 'dart:io';
import 'package:flutter/foundation.dart';
import 'package:flutter_blue_plus/flutter_blue_plus.dart';
import 'package:get/get.dart';

// Windows蓝牙支持 - 条件性导入
import 'package:win_ble/win_ble.dart';

import '../ota/ota_device_observation.dart';

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

  /// 该 adapter 是否提供真实特征通知流（RC3-09）：WinBle 提供
  /// [characteristicValueStreamOf]；FlutterBluePlus 的订阅在 service
  /// 层按特征展开（`ch.onValueReceived`），不走 adapter。测试替身可
  /// 置 true 在任意平台驱动 Windows 通知路径。
  bool get supportsCharacteristicValueStream;

  /// 真实特征通知事件流（RC3-09）：保留每片及顺序、**不去重**——
  /// FFF1 为 notify-only 分片流，同值通知可能是有效重发，重复片由
  /// 协议层幂等处理（ACK bitmap 对 delta=0 幂等重发）。不支持时抛
  /// [UnsupportedError]（先查 [supportsCharacteristicValueStream]）。
  Stream<List<int>> characteristicValueStreamOf(
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

  @override
  bool get supportsCharacteristicValueStream => false;

  @override
  Stream<List<int>> characteristicValueStreamOf(
      String deviceAddress, String serviceId, String characteristicId) {
    throw UnsupportedError(
        'FlutterBluePlus notify events are consumed per-characteristic in '
        'BluetoothService, not via adapter');
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

  @override
  bool get supportsCharacteristicValueStream => true;

  @override
  Stream<List<int>> characteristicValueStreamOf(
      String deviceAddress, String serviceId, String characteristicId) {
    // WinBle.characteristicValueStreamOf 已按 address/serviceId/
    // characteristicId 过滤真实通知事件（win_ble 1.1.1 API）。value
    // 是平台通道字节（Uint8List），拷贝为普通 List<int> 防止跨流
    // 共享底层缓冲被后续通知覆写。
    return WinBle.characteristicValueStreamOf(
      address: deviceAddress,
      serviceId: serviceId,
      characteristicId: characteristicId,
    ).map<List<int>>((value) => List<int>.from(value as List));
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

  /// OTA 物理连接代次（RC3-08⑦）：按地址计数，每次链路状态迁移 +1。
  ///
  /// 逻辑对象（transport/订阅流）活着不代表底层链路还是绑定时那一条：
  /// App 在后台期间系统可能断开旧连接并重连（甚至连到同地址的另一台
  /// 设备），此时 transport 仍可读写，只是写到了新链路上。代次是唯一
  /// 能把「同一个 Dart 对象」与「同一条物理连接」区分开的观测量。
  ///
  /// 计数点：主动 connect 成功、主动 disconnect、平台上报的断开事件。
  /// connect 幂等成功也计数——宁可多判一次失效（fail-closed），也不
  /// 把「可能已换链路」当作没变。
  final Map<String, int> _otaLinkGenerations = <String, int>{};

  /// OTA 链路观测订阅（RC3-08⑦）：与 [_deviceConnectionSubscriptions]
  /// 分开保存，避免与遥控连接路径互相顶掉对方的监听。
  final Map<String, StreamSubscription> _otaLinkWatchers = {};

  /// 读取 [deviceAddress] 当前的 OTA 物理连接代次（RC3-08⑦）。
  int otaLinkGeneration(String deviceAddress) =>
      _otaLinkGenerations[deviceAddress.toLowerCase()] ?? 0;

  /// 设备作用域句柄缓存（RC3-05⑤）。
  final Map<String, _OtaDeviceScope> _otaDeviceScopes =
      <String, _OtaDeviceScope>{};

  /// 取 [deviceAddress] 对应设备的**作用域句柄**（RC3-05⑤）。
  ///
  /// 同一地址恒定返回同一个对象，**真实重连也不更换**。写通道废弃标记
  /// 按对象身份作用域（`Expando`），它要回答的问题是「MCU 侧的悬空半帧
  /// 还在不在」——而该状态属于 MCU 的 UART 帧解析器，不随 BLE 连接事件
  /// 改变：`Libraries/OTA/ota_ble_session.c` 的 `session_teardown` 不复位
  /// `session->demux`，`ota_ble_demux_init` 只在开机 `ota_ble_session_init`
  /// 调用一次；解析器只在帧被吃完（CRC 通过或失败）时自复位
  /// （`ota_ble_frame.c` PAYLOAD/CRC 态）。若按链路代次作用域，一次截断
  /// 写会因重连而静默解除，继续往悬空解析器里写。
  ///
  /// 解除由传输层用 GET_INFO → INFO 往返证明（见
  /// `OtaBleTransport.getDeviceInfo`），本方法只负责给出稳定的作用域句柄。
  Object otaDeviceScope(String deviceAddress) {
    final key = deviceAddress.toLowerCase();
    final cached = _otaDeviceScopes[key];
    if (cached != null) {
      return cached.identity;
    }
    final identity = Object();
    _otaDeviceScopes[key] = _OtaDeviceScope(identity);
    return identity;
  }

  /// 记录一次链路状态迁移（RC3-08⑦）。
  void _bumpOtaLinkGeneration(String deviceAddress) {
    final key = deviceAddress.toLowerCase();
    _otaLinkGenerations[key] = (_otaLinkGenerations[key] ?? 0) + 1;
  }

  /// 监听平台上报的断开事件（RC3-08⑦）：断开即代次前进。
  ///
  /// 只在 OTA 连接入口注册；重复注册前先取消旧订阅，防止一个地址上
  /// 挂多个监听把一次断开计成多次。
  void _watchOtaLink(String deviceAddress, Stream<bool> connectedStream) {
    final key = deviceAddress.toLowerCase();
    _otaLinkWatchers.remove(key)?.cancel();
    _otaLinkWatchers[key] = connectedStream.listen((isConnected) {
      if (!isConnected) {
        _bumpOtaLinkGeneration(deviceAddress);
      }
    });
  }

  /// OTA 通知通道所有者令牌（RC3-08⑦）。
  ///
  /// CCCD 是 **按特征共享** 的平台资源：同一 (地址, 服务, 特征) 上只有
  /// 一个开关。被放弃的探测绑定（MTU 协商失败、订阅后发现身份不符等）
  /// 在 dispose 里取消自己的通知流时，如果无条件调平台关通知，就会把
  /// 后来者刚打开的 CCCD 关掉——后来者的 transport 还活着、读写都成功，
  /// 但再也收不到任何通知，表现为全部命令 WRITE/ACK 超时。
  ///
  /// 令牌**按发起顺序**分配（在任何 await 之前登记），取消时只有仍是
  /// 记录在册的 owner 才执行平台关通知，Dart 侧监听一律取消（本流必须
  /// 停止吐值）。按发起顺序而非完成顺序分配是必须的：先发起、后完成的
  /// 旧探测若在返回时才取号，会拿到最新令牌并把活着的新 owner 顶掉，
  /// 于是它被放弃时的取消动作就合法地关掉了新 owner 的 CCCD。
  final Map<String, int> _otaNotifyOwners = <String, int>{};
  int _otaNotifyTokenSeq = 0;

  String _otaNotifyKey(String address, String serviceId, String charId) =>
      '${address.toLowerCase()}|${serviceId.toLowerCase()}'
      '|${charId.toLowerCase()}';

  /// 每个 (地址, 服务, 特征) 上的平台 CCCD 开关串行链（RC3-08⑦）。
  ///
  /// 复核 owner 令牌与真正调用平台之间隔着 await，只在检查处判断挡不住
  /// 「旧订阅的取消动作在新订阅成功之后才落地」——排队期间 owner 已经换人，
  /// 迟到动作照样会关掉新 owner 依赖的共享 CCCD。把订阅与取消都按**排队顺序**
  /// 串行执行、并在**执行时刻**复核令牌，才有可判定的先后。
  /// 条目数按会话内出现过的特征键数有界；不回收条目，因为回收会与已排队的
  /// 动作分裂成两条并行链，反而破坏顺序。
  final Map<String, Future<void>> _otaNotifyOpSerial = <String, Future<void>>{};

  /// 排队执行一次共享 CCCD 平台操作（RC3-08⑦）。
  ///
  /// 轮到执行时若令牌已易主则整体跳过：旧订阅既不该重开、也不该关闭已经
  /// 由新 owner 接管的平台开关。前序动作的异常不阻断链条。
  Future<void> _runNotifyOwnerOp(
    String ownerKey,
    int ownerToken,
    Future<void> Function() op,
  ) {
    final previous = _otaNotifyOpSerial[ownerKey] ?? Future<void>.value();
    final next = previous.catchError((Object _) {}).then((_) async {
      if (_otaNotifyOwners[ownerKey] != ownerToken) return;
      await op();
    });
    _otaNotifyOpSerial[ownerKey] =
        next.then<void>((_) {}, onError: (Object _) {});
    return next;
  }

  /// 释放令牌（RC3-08⑦）：只清自己仍持有的那一个，不得顶掉新 owner。
  void _releaseNotifyOwner(String ownerKey, int ownerToken) {
    if (_otaNotifyOwners[ownerKey] == ownerToken) {
      _otaNotifyOwners.remove(ownerKey);
    }
  }

  // 蓝牙适配器实例
  late BluetoothAdapter _adapter;

  /// 测试注入 adapter（RC3-09）：不经 [initBluetooth] 平台分支，直接
  /// 驱动 adapter 接口的通知订阅路径。真实路径仍由 [initBluetooth]
  /// 按平台选择，此注入不改变生产行为。
  @visibleForTesting
  set adapterForTest(BluetoothAdapter adapter) => _adapter = adapter;

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
    // OTA 链路观测订阅同样释放（RC3-08⑦）。
    for (var subscription in _otaLinkWatchers.values) {
      subscription.cancel();
    }
    _otaLinkWatchers.clear();

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
        // P3-3 T1a 设备观测：显式启用时逐台落 logcat（未启用时是空操作）。
        _observeScanResults(results);
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
            // RC3-08⑦：遥控路径观测到的断开同样是物理链路迁移。
            _bumpOtaLinkGeneration(device.remoteId.str);
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
            // RC3-08⑦：同上，断开即物理链路迁移。
            _bumpOtaLinkGeneration(device.remoteId.str);
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
    } finally {
      // RC3-08⑦：主动断开（含失败）后链路状态不可信，代次前进。
      _bumpOtaLinkGeneration(device.remoteId.str);
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

  /// OTA 专用写入（RC2-08）：UUID 用 [_strictBleUuidEquals] 严格匹配。
  ///
  /// 遥控透传 [writeByAddress] 的宽松匹配与调试字符串提取不适用于
  /// OTA 传输（OTA-XC-FLUTTER-TRANSPORT 红线：非 FFF2 特征不得被
  /// 模糊匹配命中）。serviceId/characteristicId 必须来自
  /// [findExactOtaCharacteristicsByAddress] 的发现结果。
  Future<void> writeOtaCharacteristicByAddress(
    String deviceAddress,
    String serviceId,
    String characteristicId,
    List<int> data, {
    bool writeWithResponse = false,
  }) async {
    try {
      if (Platform.isWindows) {
        await _adapter.writeCharacteristic(
          deviceAddress,
          serviceId,
          characteristicId,
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
          final sid = svc.uuid.toString();
          if (!_strictBleUuidEquals(sid, serviceId)) continue;
          for (final ch in svc.characteristics) {
            final cid = ch.uuid.toString();
            if (!_strictBleUuidEquals(cid, characteristicId)) continue;
            await ch.write(Uint8List.fromList(data),
                withoutResponse: !writeWithResponse);
            return;
          }
        }
        throw UnsupportedError('未找到目标OTA特征: $characteristicId');
      }
    } catch (e) {
      debugPrint('OTA写入失败($deviceAddress/$serviceId/$characteristicId): $e');
      rethrow;
    }
  }

  /// 订阅通知（Windows 走 WinBle 通知事件流，移动端走FlutterBlue特征）
  Stream<List<int>>? subscribeNotifyByAddress(
      String deviceAddress, String serviceId, String characteristicId) {
    try {
      if (_adapter.supportsCharacteristicValueStream) {
        // Windows（RC3-09）：消费真实特征通知事件，不再 250ms 轮询读
        // + last 去重（会丢连续分片/同值通知）。可读特征额外做一次
        // 初始读给出当前值；notify-only 特征读失败属预期，忽略。
        return Stream<List<int>>.multi((controller) async {
          StreamSubscription<List<int>>? sub;
          try {
            await _adapter.subscribeToCharacteristic(
                deviceAddress, serviceId, characteristicId);
          } catch (_) {}
          try {
            // 初始读直连 adapter（notify-only 特征读失败属预期，忽略；
            // 可读特征给出当前值）。
            final current = await _adapter.readCharacteristic(
                deviceAddress, serviceId, characteristicId);
            if (current.isNotEmpty) {
              controller.add(current);
            }
          } catch (_) {}
          sub = _adapter
              .characteristicValueStreamOf(
                  deviceAddress, serviceId, characteristicId)
              .listen(controller.add,
                  onError: controller.addError, onDone: controller.close);
          controller.onCancel = () async {
            await sub?.cancel();
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

  /// 精确发现 OTA 特征（OTA 专用，无降级）。
  ///
  /// 在 FFF0 服务内要求同时存在精确 FFF2（可写）与 FFF1（可通知）
  /// 两个特征；缺任一即返回 null。禁止任取第一个可写/通知特征——
  /// 那是遥控透传 `findTransparentUuidsByAddress` 的降级策略，
  /// OTA 传输红线（OTA-XC-FLUTTER-TRANSPORT）不允许复用。
  ///
  /// UUID 比较用 [_strictBleUuidEquals]：短格式或 Bluetooth Base UUID
  /// 精确等价，其他 128-bit UUID 不得冒充标准服务/特征（PR06）。
  /// 返回 { 'serviceId', 'writeCharId'(FFF2), 'notifyCharId'(FFF1),
  /// 'writeMode'('with'/'without'——FFF2 实际支持的写模式) }。
  Future<Map<String, String>?> findExactOtaCharacteristicsByAddress(
    String deviceAddress, {
    String serviceUuid = 'fff0',
    String writeCharUuid = 'fff2',
    String notifyCharUuid = 'fff1',
  }) async {
    try {
      final services = await discoverServicesByAddress(deviceAddress);
      String? normalizeId(dynamic obj) => _extractUuidFromAny(obj);

      for (final svc in services) {
        final sid = normalizeId(svc);
        if (sid == null) continue;
        if (!_strictBleUuidEquals(sid, serviceUuid)) continue;

        final characteristics = Platform.isWindows
            ? await _adapter.discoverCharacteristics(deviceAddress, sid)
            : _safeMobileCharacteristicsList(svc);

        String? writeId;
        String? writeMode;
        String? notifyId;
        for (final ch in characteristics) {
          final cid = normalizeId(ch);
          if (cid == null) continue;
          if (writeId == null &&
              _strictBleUuidEquals(cid, writeCharUuid)) {
            // 绑定实际支持的写模式：仅 withoutResponse 时禁止强制
            // withResponse 写（PR06）。
            final mode = _otaWriteMode(ch);
            if (mode != null) {
              writeId = cid;
              writeMode = mode;
            }
          }
          if (notifyId == null &&
              _strictBleUuidEquals(cid, notifyCharUuid) &&
              _hasCharacteristicNotify(ch)) {
            notifyId = cid;
          }
        }
        if (writeId == null || notifyId == null) {
          // 精确匹配失败：不做任何降级，直接视为无 OTA 特征。
          return null;
        }
        return {
          'serviceId': sid,
          'writeCharId': writeId,
          'notifyCharId': notifyId,
          'writeMode': writeMode!,
        };
      }
      return null;
    } catch (e) {
      debugPrint('精确发现OTA特征失败($deviceAddress): $e');
      return null;
    }
  }

  /// OTA 专用通知订阅：等待订阅真正就绪后才返回流（PR10）。
  ///
  /// 与遥控透传 [subscribeNotifyByAddress] 的区别：
  /// - 返回 Future——订阅完成、监听建立后才 resolve，调用方
  ///   （OtaService 绑定 transport）可安全地在 resolve 后立即发送
  ///   GET_INFO；
  /// - UUID 用 [_strictBleUuidEquals] 精确匹配；
  /// - Windows 端 `subscribeToCharacteristic` 失败返回 null（不静默吞掉）。
  ///
  /// Windows 通知路径（RC3-09）：FFF1 为 notify-only 分片流，不可读——
  /// 订阅后消费真实特征通知事件（[BluetoothAdapter
  /// .characteristicValueStreamOf]），保留每片及顺序、不去重（同值
  /// 通知是有效重发，由协议层 ACK 幂等处理）。原 250ms 轮询读 + last
  /// 去重会丢连续分片/同值通知，已删除。
  /// 特征不存在/订阅失败/平台异常均返回 null，不抛出。
  ///
  /// 所有权按**发起顺序**分配（RC3-08⑦）：令牌在任何 await 之前登记。
  /// 若在平台订阅返回后才分配，先发起、后完成的旧探测会拿到最新令牌，把
  /// 已经在上层活着的新 owner 顶掉；旧探测随后被放弃时，它的取消动作就会
  /// 关掉新 owner 依赖的共享 CCCD——新 transport 读写都成功却收不到任何
  /// 通知，表现为全部 ACK 超时。等平台订阅返回后若已易主，本地直接放弃：
  /// 既不建立监听，也不动平台开关（那是新 owner 的）。
  Future<Stream<List<int>>?> subscribeOtaNotifyByAddress(
    String deviceAddress,
    String serviceId,
    String characteristicId,
  ) async {
    final ownerKey =
        _otaNotifyKey(deviceAddress, serviceId, characteristicId);
    final ownerToken = ++_otaNotifyTokenSeq;
    _otaNotifyOwners[ownerKey] = ownerToken;
    try {
      if (_adapter.supportsCharacteristicValueStream) {
        try {
          await _runNotifyOwnerOp(ownerKey, ownerToken, () async {
            await _adapter.subscribeToCharacteristic(
                deviceAddress, serviceId, characteristicId);
          });
        } catch (e) {
          debugPrint('OTA订阅特征失败($deviceAddress/$characteristicId): $e');
          _releaseNotifyOwner(ownerKey, ownerToken);
          return null;
        }
        if (_otaNotifyOwners[ownerKey] != ownerToken) return null;
        // WinBle 无 CCCD 就绪回调：订阅调用返回即视为就绪。通知流在
        // 订阅前建立也可（broadcast 流，早到事件由订阅方过滤丢弃），
        // 这里订阅成功后再监听，保证取消订阅后流不再吐值。
        final notifyStream = _adapter.characteristicValueStreamOf(
            deviceAddress, serviceId, characteristicId);
        late StreamSubscription<List<int>> sub;
        final controller = StreamController<List<int>>();
        sub = notifyStream.listen(
          controller.add,
          onError: controller.addError,
          onDone: controller.close,
        );
        controller.onCancel = () async {
          await sub.cancel();
          // RC3-08⑦：只有仍是 owner 才关平台通知，否则会关掉更新
          // owner 刚打开的共享 CCCD。
          await _runNotifyOwnerOp(ownerKey, ownerToken, () async {
            _releaseNotifyOwner(ownerKey, ownerToken);
            try {
              await _adapter.unSubscribeFromCharacteristic(
                  deviceAddress, serviceId, characteristicId);
            } catch (_) {}
          });
        };
        return controller.stream;
      } else {
        final device = _findDeviceByAddress(deviceAddress);
        if (device == null) {
          _releaseNotifyOwner(ownerKey, ownerToken);
          return null;
        }
        final services = await device.discoverServices();
        for (final svc in services) {
          final sid = svc.uuid.toString();
          if (!_strictBleUuidEquals(sid, serviceId)) continue;
          for (final ch in svc.characteristics) {
            final cid = ch.uuid.toString();
            if (!_strictBleUuidEquals(cid, characteristicId)) continue;
            // 先完成 CCCD 订阅再返回流：resolve 后即可安全发命令。
            try {
              await _runNotifyOwnerOp(
                  ownerKey, ownerToken, () => ch.setNotifyValue(true));
            } catch (e) {
              debugPrint(
                  'OTA订阅通知失败($deviceAddress/$characteristicId): $e');
              _releaseNotifyOwner(ownerKey, ownerToken);
              return null;
            }
            if (_otaNotifyOwners[ownerKey] != ownerToken) return null;
            late StreamSubscription<List<int>> sub;
            final controller = StreamController<List<int>>();
            sub = ch.onValueReceived.listen(
              controller.add,
              onError: controller.addError,
              onDone: controller.close,
            );
            controller.onCancel = () async {
              await sub.cancel();
              // RC3-08⑦：与 Windows 分支同一约束——CCCD 按特征共享，
              // 非 owner 不得关闭。
              await _runNotifyOwnerOp(ownerKey, ownerToken, () async {
                _releaseNotifyOwner(ownerKey, ownerToken);
                try {
                  await ch.setNotifyValue(false);
                } catch (_) {}
              });
            };
            return controller.stream;
          }
        }
        _releaseNotifyOwner(ownerKey, ownerToken);
        return null;
      }
    } catch (e) {
      debugPrint('OTA订阅通知失败($deviceAddress/$characteristicId): $e');
      _releaseNotifyOwner(ownerKey, ownerToken);
      return null;
    }
  }

  /// 请求协商更大的 ATT MTU（移动端专用；Windows WinBle 协议栈自管理）。
  ///
  /// 返回协商后的单次写入净荷上限（MTU-3）；失败或平台不支持时返回
  /// 保守值 20（ATT 默认 MTU 23 - 3）。OTA 分片以该值为准。
  Future<int> requestOtaMtu(String deviceAddress, {int requested = 247}) async {
    try {
      if (Platform.isWindows) {
        // WinBle 由协议栈管理分片；返回保守默认写入大小。
        return 20;
      }
      final device = _findDeviceByAddress(deviceAddress);
      if (device == null) return 20;
      final negotiated = await device.requestMtu(requested);
      if (negotiated >= 23) {
        return negotiated - 3;
      }
      return 20;
    } catch (e) {
      debugPrint('协商MTU失败($deviceAddress): $e');
      return 20;
    }
  }

  /// OTA 重连专用：按地址主动断开（RC2-07）。
  ///
  /// 设备重启前旧 GATT 连接可能悬挂（协议栈仍报告已连接），在旧连接
  /// 上会读到重启前的 INFO/通知。升级完成后等重启时必须先主动断开。
  /// 尽力语义：失败不抛出（断不开由上层轮询兜底）。
  ///
  /// 收尾动作绑定**发起时刻**的链路状态（RC3-08⑦）：断开是异步尽力操作，
  /// 等待平台返回期间可能有更新的连接重建了同地址链路（重启等待流程就是
  /// 「断开→重连」紧邻发生）。若收尾不设防，迟到完成会把新链路刚注册的
  /// 观测订阅取消、把新连接刚登记的设备与连接订阅一并清掉——代次虽已前进，
  /// 但新链路的观测被自己的收尾动作拆掉，后续断开再无观测入口。
  Future<void> disconnectOtaDeviceByAddress(String deviceAddress) async {
    final key = deviceAddress.toLowerCase();
    final startGeneration = otaLinkGeneration(key);
    final startWatcher = _otaLinkWatchers[key];
    try {
      if (Platform.isWindows) {
        await _adapter.disconnect(deviceAddress);
        if (otaLinkGeneration(key) == startGeneration) {
          _deviceConnectionSubscriptions[deviceAddress]?.cancel();
          _deviceConnectionSubscriptions.remove(deviceAddress);
        }
      } else {
        final device = _findDeviceByAddress(deviceAddress) ??
            BluetoothDevice.fromId(deviceAddress);
        await device.disconnect();
      }
      if (otaLinkGeneration(key) == startGeneration) {
        connectedDevices.removeWhere((d) => d.remoteId.str.toLowerCase() == key);
      }
    } catch (e) {
      debugPrint('OTA主动断开失败($deviceAddress): $e');
    } finally {
      // RC3-08⑦：断开尝试后链路状态不再是绑定时那一条，成功与否都
      // 前进代次——断开失败同样意味着链路状态不可信（尽力语义下上层
      // 会重连），不得让失败路径把代次留在旧值上冒充"链路未变"。
      // 代次已被并发操作推进时不重复推进：链路失效的语义已经达成，
      // 再加一次只会让后续绑定的代次快照更难对上。
      if (otaLinkGeneration(key) == startGeneration) {
        _bumpOtaLinkGeneration(deviceAddress);
      }
      if (identical(_otaLinkWatchers[key], startWatcher)) {
        _otaLinkWatchers.remove(key)?.cancel();
      }
    }
  }

  /// OTA 重连专用：按地址发起连接（RC2-07）。
  ///
  /// Windows 走 WinBle 地址连接；移动端优先复用已连接/扫描缓存的
  /// 设备对象，否则按 remoteId 直接构造（设备重启后不在任何缓存里）。
  /// 返回是否成功；失败由调用方继续轮询。
  Future<bool> connectOtaDeviceByAddress(String deviceAddress) async {
    try {
      if (Platform.isWindows) {
        await _adapter.connect(deviceAddress);
        // RC3-08⑦：新链路建立即前进代次，并监听平台断开事件——系统在
        // App 后台期间断开重连时，代次是上层判定"绑定的那条链路还在
        // 不在"的唯一依据。
        _bumpOtaLinkGeneration(deviceAddress);
        _watchOtaLink(deviceAddress, WinBle.connectionStreamOf(deviceAddress));
        return true;
      }
      final device = _findDeviceByAddress(deviceAddress) ??
          BluetoothDevice.fromId(deviceAddress);
      // flutter_blue_plus 对已连接设备 connect 是幂等成功，不会抛错。
      await device.connect(timeout: const Duration(seconds: 10));
      if (!connectedDevices.contains(device)) {
        connectedDevices.add(device);
      }
      _bumpOtaLinkGeneration(deviceAddress);
      _watchOtaLink(
        deviceAddress,
        device.connectionState
            .map((state) => state == BluetoothConnectionState.connected),
      );
      return true;
    } catch (e) {
      debugPrint('OTA重连失败($deviceAddress): $e');
      return false;
    }
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
            _getProperty(ch, 'canRead') == true) {
          return true;
        }
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
            _getProperty(ch, 'indicate') == true) {
          return true;
        }
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
      // win_ble 1.1.1 的 Properties 是 bool? 字段式对象（无 getField()/operator[]，
      // toString() 是默认实例串）：先按字段名显式访问成员，bool? 为 true 才算具备。
      for (final k in keySet) {
        if (_propField(props, k)) return true;
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

  /// 按 win_ble Properties 的字段名读取 bool 能力位。
  /// 字段是 `bool?`：仅显式为 true 视为具备，null/false 一律视为不具备；
  /// 成员不存在（NoSuchMethodError）安全返回 false，不冒泡。
  bool _propField(dynamic props, String lowerKey) {
    try {
      final dynamic v;
      switch (lowerKey) {
        case 'broadcast':
          v = props.broadcast;
          break;
        case 'read':
          v = props.read;
          break;
        case 'writewithoutresponse':
          v = props.writeWithoutResponse;
          break;
        case 'write':
          v = props.write;
          break;
        case 'notify':
          v = props.notify;
          break;
        case 'indicate':
          v = props.indicate;
          break;
        case 'authenticatedsignedwrites':
          v = props.authenticatedSignedWrites;
          break;
        case 'reliablewrite':
          v = props.reliableWrite;
          break;
        case 'writableauxiliaries':
          v = props.writableAuxiliaries;
          break;
        default:
          return false;
      }
      return v == true;
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

  // ---- P3-3 T1a 设备观测适配（仅显式启用的 dev APK 生效） ----

  /// 把扫描批次喂给观测器。观测器未装配（默认构建）时立即返回，
  /// 不产生任何计算与日志。
  void _observeScanResults(List<dynamic> results) {
    final observer = OtaDeviceObserver.instance;
    if (observer == null) return;
    if (results is! List<ScanResult>) return;
    observer.onAdvertisements(
      results.map(_observedAdvertisement).toList(growable: false),
    );
  }

  /// 观测专用扫描入口：等适配器就绪后再启动，并**返回是否已下发扫描**。
  ///
  /// UI 入口 `BleController.startScan()` 在适配器状态尚未填充时按"蓝牙未开"
  /// 直接返回并尝试弹提示；观测是在首帧回调里发起的，那一刻
  /// [adapterState] 仍在异步初始化，于是扫描根本没启动，日志只留下
  /// `scanned=0`——与"扫了 120s 但目标不在场"长得一模一样。2026-09-12 真机
  /// 实测即为此：`.obs` 包全程零扫描批次，而同机另一进程正常收到 169 台。
  ///
  /// 这里按有界重试等状态到位（最多 30s，1s 未就绪重试一次），复用同一条
  /// 扫描实现，不另写扫描逻辑。
  ///
  /// 返回值的边界：[startScan] 内部吞掉平台异常，因此这里只能保证"适配器
  /// 已经是 on 且已下发扫描"，不能保证平台一定兑现。不额外探测平台状态
  /// 制造更弱的证据——若平台拒绝，观测侧仍会以 `target_not_seen scanned=0`
  /// 收尾，与"设备不在场"的差别由本方法返回 false 的那条路径显式区分。
  Future<bool> startObservationScan() async {
    const attempts = 30;
    for (var attempt = 0; attempt < attempts; attempt++) {
      if (adapterState.value == BluetoothAdapterState.on) {
        await startScan();
        return true;
      }
      await Future<void>.delayed(const Duration(seconds: 1));
    }
    debugPrint('观测扫描未启动: 适配器状态在 ${attempts}s 内未就绪 '
        '(adapterState=${adapterState.value})');
    return false;
  }

  /// 观测专用连接入口：按已扫描到的地址连接，并**返回真实结果**。
  ///
  /// UI 入口 [connectDevice] 只弹提示不返回成败，观测侧需要确定的
  /// `ok/fail` 证据，故在其上做一层结果判定（复用同一条连接实现，
  /// 不另写连接逻辑）。
  Future<bool> connectObservedDevice(ObservedAdvertisement advertisement) async {
    try {
      final device = _findDeviceByAddress(advertisement.address.toLowerCase());
      if (device == null) return false;
      if (device.isConnected) return true;
      await connectDevice(device);
      return device.isConnected;
    } catch (e) {
      // 观测行已记录连接失败；这里只保证不把异常抛给扫描监听。
      debugPrint('观测连接失败(${advertisement.address}): $e');
      return false;
    }
  }

  /// 单条扫描结果的观测快照；厂商数据拼成小写 hex 串。
  ObservedAdvertisement _observedAdvertisement(ScanResult result) {
    final data = result.advertisementData;
    final advName = data.advName;
    final platformName = result.device.platformName;
    return ObservedAdvertisement(
      address: result.device.remoteId.str,
      name: advName.isNotEmpty ? advName : platformName,
      rssi: result.rssi,
      connectable: data.connectable,
      serviceUuids:
          data.serviceUuids.map((uuid) => uuid.toString()).toList(growable: false),
      manufacturerDataHex: data.manufacturerData.values
          .expand((bytes) => bytes)
          .map((byte) => byte.toRadixString(16).padLeft(2, '0'))
          .join(),
    );
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

  /// 严格 UUID 等价（OTA 红线，PR06）：仅接受短格式（4 位 hex）或
  /// Bluetooth Base UUID `0000xxxx-0000-1000-8000-00805f9b34fb` 的精确
  /// 等价；其他 128-bit UUID 一律不等价，不得冒充标准服务/特征。
  /// 遥控透传的宽松匹配 [_uuidLikeEquals] 不受影响。
  bool _strictBleUuidEquals(String a, String b) {
    String norm(String x) =>
        x.toLowerCase().replaceAll('-', '').replaceAll('0x', '').trim();
    final na = norm(a);
    final nb = norm(b);
    if (na == nb) return true;
    const baseSuffix = '00001000800000805f9b34fb'; // Base UUID 去前 4 位后缀
    String? to16(String x) {
      if (x.length == 4) return x;
      if (x.length == 32 &&
          x.startsWith('0000') &&
          x.endsWith(baseSuffix)) {
        return x.substring(4, 8);
      }
      return null; // 非标准 128-bit：禁止截断冒充
    }
    final a16 = to16(na);
    final b16 = to16(nb);
    return a16 != null && a16 == b16;
  }

  /// OTA 写模式检测：优先 withResponse，其次 withoutResponse，不可写为 null。
  /// 绑定实际支持的写模式，禁止对仅 withoutResponse 的特征强制
  /// withResponse 写（PR06）。
  String? _otaWriteMode(dynamic ch) {
    try {
      bool withResp;
      bool withoutResp;
      if (Platform.isWindows) {
        withResp = _getProperty(ch, 'writeWithResponse') == true ||
            _getProperty(ch, 'write') == true ||
            _propContains(_getProperty(ch, 'properties'), ['write']);
        withoutResp = _getProperty(ch, 'writeWithoutResponse') == true ||
            _propContains(
                _getProperty(ch, 'properties'), ['writeWithoutResponse']);
        // WinBle 的 canWrite/isWritable 语义未区分模式：保守按有响应写。
        if (!withResp && !withoutResp) {
          final ambiguous = _getProperty(ch, 'canWrite') == true ||
              _getProperty(ch, 'isWritable') == true;
          if (ambiguous) withResp = true;
        }
      } else {
        withResp = ch.properties.write == true;
        withoutResp = ch.properties.writeWithoutResponse == true;
      }
      if (withResp) return 'with';
      if (withoutResp) return 'without';
      return null;
    } catch (_) {
      return null;
    }
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
        case 'uuid':
          // win_ble BleCharacteristic.uuid：字符串字段，直接成员访问。
          return object.uuid;
        case 'properties':
          // win_ble BleCharacteristic.properties：字段式对象而非 Map，
          // 必须整对象返回给 _propContains/_propField 做字段式判定。
          return object.properties;
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

/// 设备作用域句柄缓存（RC3-05⑤）：按地址恒定返回同一对象，不随链路代次
/// 变化——写通道废弃标记的作用域是「MCU 侧帧解析器状态所属的设备」，
/// 见 [BluetoothService.otaDeviceScope]。
class _OtaDeviceScope {
  _OtaDeviceScope(this.identity);

  final Object identity;
}
