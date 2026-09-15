import 'dart:async';

import 'package:flutter_blue_plus/flutter_blue_plus.dart'
    show AdvertisementData, BluetoothAdapterState, BluetoothDevice,
    DeviceIdentifier, ScanResult;
import 'package:flutter_test/flutter_test.dart';
import 'package:get/get.dart';

import 'package:ble_monitor/ota/ota_device_observation.dart';
import 'package:ble_monitor/services/bluetooth_service.dart';

/// OBS-01 集成层回归：扫描启动失败 / 扫描流错误 / 正常空扫描三类结局必须
/// 经 **真实接线**（BluetoothService + adapter 替身 + OtaDeviceObserver）
/// 产生可区分的结果——只测手工注入 bool 的 observer 不算覆盖接线。
///
/// 替身实现 [BluetoothAdapter] 契约；`BluetoothService.startObservationScan`
/// 复用生产 `startScan`（不另写扫描逻辑），其内部经 `_adapter.startScan`
/// 与 `_adapter.scanResults` 真实走一遍启动与监听路径。
class _ScanProbeAdapter implements BluetoothAdapter {
  _ScanProbeAdapter({this.startScanError});

  /// 平台 startScan 的注入结果：非 null 时按该异常拒绝启动。
  final Object? startScanError;

  /// 扫描结果流出口：测试里注入批次或错误。
  final StreamController<List<dynamic>> scanController =
      StreamController<List<dynamic>>.broadcast();

  int startCalls = 0;
  int stopCalls = 0;
  bool scanning = false;

  @override
  Future<void> startScan({Duration? timeout}) async {
    startCalls++;
    final error = startScanError;
    if (error != null) throw error;
    scanning = true;
  }

  @override
  Future<void> stopScan() async {
    stopCalls++;
    scanning = false;
  }

  @override
  Stream<List<dynamic>> get scanResults => scanController.stream;

  @override
  Stream<BluetoothAdapterState> get adapterStateChanged =>
      const Stream.empty();

  // ---- 与扫描路径无关 ----

  @override
  Future<void> init() async {}

  @override
  Future<void> connect(String deviceAddress) async {}

  @override
  Future<void> disconnect(String deviceAddress) async {}

  @override
  Future<List<dynamic>> getConnectedDevices() async => [];

  @override
  Future<BluetoothAdapterState> getAdapterState() async =>
      BluetoothAdapterState.on;

  @override
  Stream<String> get connectionStateChanged => const Stream.empty();

  @override
  Future<void> pair(String deviceAddress) async {}

  @override
  Future<void> unPair(String deviceAddress) async {}

  @override
  Future<bool> canPair(String deviceAddress) async => false;

  @override
  Future<bool> isPaired(String deviceAddress) async => false;

  @override
  Future<List<dynamic>> discoverServices(String deviceAddress) async => [];

  @override
  Future<List<dynamic>> discoverCharacteristics(
      String deviceAddress, String serviceId) async => [];

  @override
  Future<List<int>> readCharacteristic(
      String deviceAddress, String serviceId, String characteristicId) async {
    return const [];
  }

  @override
  Future<void> writeCharacteristic(String deviceAddress, String serviceId,
      String characteristicId, List<int> data,
      {bool writeWithResponse = false}) async {}

  @override
  Future<void> subscribeToCharacteristic(
      String deviceAddress, String serviceId, String characteristicId) async {}

  @override
  Future<void> unSubscribeFromCharacteristic(
      String deviceAddress, String serviceId, String characteristicId) async {}

  @override
  bool get supportsCharacteristicValueStream => false;

  @override
  Stream<List<int>> characteristicValueStreamOf(
      String deviceAddress, String serviceId, String characteristicId) {
    throw UnsupportedError('scan probe has no notify stream');
  }
}

const _target = 'XTrace';
const _fingerprint = 'OTAOBS0123456789abcdef01234567';

/// 轮询微任务/事件队列直到谓词为真（有界）。
Future<bool> _pumpUntil(bool Function() ready) async {
  for (var i = 0; i < 400 && !ready(); i++) {
    await Future<void>.delayed(const Duration(milliseconds: 2));
  }
  return ready();
}

void main() {
  late BluetoothService service;
  late _ScanProbeAdapter adapter;

  setUp(() {
    // UI 入口约定：startScan 吞平台异常只弹提示。测试环境无 GetMaterialApp，
    // Get.snackbar 会因缺 Overlay 抛异常——testMode 让它降级为 debugPrint，
    // 测试聚焦扫描接线而非 UI 提示。
    Get.testMode = true;
    adapter = _ScanProbeAdapter();
    service = BluetoothService();
    service.adapterForTest = adapter;
    // 适配器已 on：startObservationScan 的就绪等待立即通过。
    service.adapterState.value = BluetoothAdapterState.on;
  });

  tearDown(() async {
    OtaDeviceObserver.instance = null;
    await adapter.scanController.close();
  });

  /// 装配观测器并接上真实服务入口（复用 main.dart 的装配形态）。
  List<String> wireObserver({Duration window = const Duration(seconds: 5)}) {
    final lines = <String>[];
    OtaDeviceObserver.instance = OtaDeviceObserver(
      config: const OtaDeviceObservationConfig(
        enabled: true,
        target: _target,
        sentinel: _fingerprint,
      ),
      startScan: () => service.startObservationScan(),
      stopScan: () => service.stopScan(),
      connect: (_) async => false,
      readIdentity: (_) async => null,
      window: window,
      emit: lines.add,
    );
    return lines;
  }

  test('适配器 on 但平台拒绝启动：scan_not_started，不与未见目标混淆',
      () async {
    adapter = _ScanProbeAdapter(
      startScanError: StateError('platform refused'),
    );
    service = BluetoothService();
    service.adapterForTest = adapter;
    service.adapterState.value = BluetoothAdapterState.on;
    final lines = wireObserver();
    final observer = OtaDeviceObserver.instance!;
    observer.start();

    expect(
      await _pumpUntil(
          () => lines.any((l) => l.startsWith('OTA_OBS done'))),
      isTrue,
      reason: '平台拒绝启动必须有终止行',
    );

    // OBS-01：旧实现 startObservationScan 无条件 return true，平台拒绝被
    // 吞成"扫描已启动"，只能以 target_not_seen scanned=0 收尾。修复后必须
    // 是 scan_not_started。
    expect(observer.result, 'OTA_OBS done result=scan_not_started');
    expect(adapter.startCalls, 1, reason: '启动确实下发到了平台');
    // 不开窗口：没扫就没必要伪装成"扫了没看到"。
    expect(lines.any((line) => line.startsWith('OTA_OBS window')), isFalse);
  });

  test('扫描中流报错：scan_stream_error 经真实 onError 接线通知观测器',
      () async {
    final lines = wireObserver();
    final observer = OtaDeviceObserver.instance!;
    observer.start();

    expect(
      await _pumpUntil(
          () => lines.any((l) => l.startsWith('OTA_OBS window'))),
      isTrue,
      reason: '扫描应已真正启动并打开观测窗口',
    );

    // 平台扫描流报错：BluetoothService 的 onError 回调必须把它转给观测器
    // （旧实现只 debugPrint，观测侧永远收不到）。
    adapter.scanController.addError(StateError('bt stack died'));
    expect(
      await _pumpUntil(
          () => lines.any((l) => l.startsWith('OTA_OBS done'))),
      isTrue,
      reason: '流错误必须有终止行',
    );

    expect(observer.result, 'OTA_OBS done result=scan_stream_error scanned=0',
        reason: '流错误必须经真实接线到达观测器，而不是只写 debugPrint');
    expect(lines.singleWhere((line) => line.startsWith('OTA_OBS stream')),
        contains('result=error'));
    // 流错误后 isScanning 复位（服务侧行为保持），扫描状态被回收。
    expect(service.isScanning.value, isFalse);
  });

  test('正常空扫描：窗口到期 target_not_seen，不与启动失败混淆', () async {
    final lines = wireObserver(window: const Duration(milliseconds: 60));
    final observer = OtaDeviceObserver.instance!;
    observer.start();

    expect(
      await _pumpUntil(
          () => lines.any((l) => l.startsWith('OTA_OBS done'))),
      isTrue,
      reason: '窗口到期必须有终止行',
    );

    expect(observer.result,
        'OTA_OBS done result=target_not_seen waitedMs=60 scanned=0 '
        'target=$_target');
    expect(adapter.startCalls, 1);
    expect(adapter.stopCalls, 1, reason: '窗口到期必须停扫描');
  });

  test('扫描批次经真实接线转成 ObservedAdvertisement（含目标匹配）', () async {
    final lines = wireObserver();
    final observer = OtaDeviceObserver.instance!;
    observer.start();

    expect(
      await _pumpUntil(
          () => lines.any((l) => l.startsWith('OTA_OBS window'))),
      isTrue,
    );

    // 平台吐一批 flutter_blue_plus ScanResult 形态的扫描结果：
    // 经 _startScan 的真实订阅 → _observeScanResults 的形态检查 →
    // 观测器批次行。XTrace 即目标，命中后走绑定链路（connect 返回 false
    // → connect_failed），证明匹配与绑定接线也是真实的。
    final aima = ScanResult(
      device: BluetoothDevice(remoteId: const DeviceIdentifier('11:22:33:44:55:66')),
      // AdvertisementData 构造器在 flutter_blue_plus 1.35.5 非 const，
      // 与生产代码 bluetooth_service.dart 的既有构造方式一致。
      advertisementData: AdvertisementData(
        advName: 'AIMA',
        txPowerLevel: null,
        appearance: 0,
        connectable: true,
        manufacturerData: {},
        serviceData: {},
        serviceUuids: [],
      ),
      rssi: -70,
      timeStamp: DateTime.now(),
    );
    final xtrace = ScanResult(
      device: BluetoothDevice(remoteId: const DeviceIdentifier('AA:BB:CC:DD:EE:FF')),
      advertisementData: AdvertisementData(
        advName: 'XTrace',
        txPowerLevel: null,
        appearance: 0,
        connectable: true,
        manufacturerData: {},
        serviceData: {},
        serviceUuids: [],
      ),
      rssi: -55,
      timeStamp: DateTime.now(),
    );
    adapter.scanController.add(<ScanResult>[aima, xtrace]);

    expect(
      await _pumpUntil(
          () => lines.any((l) => l.startsWith('OTA_OBS done'))),
      isTrue,
      reason: '命中目标后绑定链路必须给出终止行',
    );

    // 批次行：两台设备都进入观测（total=2）。
    expect(lines.singleWhere((line) => line.startsWith('OTA_OBS scan')),
        'OTA_OBS scan total=2 new=2 seen=2');
    expect(lines.any((line) => line.contains('addr=11:22:33:44:55:66')),
        isTrue, reason: '非目标设备也要落明细行');
    // 目标行（OBS-03：真实地址，不是对象插值）与绑定结局。
    expect(lines.singleWhere((line) => line.startsWith('OTA_OBS target')),
        contains('addr=AA:BB:CC:DD:EE:FF'));
    expect(observer.result, 'OTA_OBS done result=connect_failed',
        reason: '装配的 connect 返回 false：命中后的绑定接线真实走通');
  });
}
