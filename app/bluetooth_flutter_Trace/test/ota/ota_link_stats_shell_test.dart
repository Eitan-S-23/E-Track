import 'dart:async';
import 'dart:io' show Platform;

import 'package:flutter_blue_plus/flutter_blue_plus.dart'
    show BluetoothAdapterState;
import 'package:flutter_test/flutter_test.dart';
import 'package:get/get.dart';

import 'package:ble_monitor/ota/ota_link_stats.dart';
import 'package:ble_monitor/services/bluetooth_service.dart';

/// P34-R04/R07：**真实计时外壳**的 stats 上报测试。
///
/// service 层用例（`ota_service_upgrade_test.dart`）覆写的就是这些外壳，
/// 由替身自行上报——删掉生产的 recordXxx 调用点，那些用例照过。本文件
/// 反过来：装配**真实 [BluetoothService]**，只替换平台适配器
/// （[BluetoothService.adapterForTest]），断言的每一处字段都必须由生产
/// 外壳写入，具备变异鉴别力（删点即红）。
///
/// 平台分支互补（双宿主 CI）：Windows 宿主走 `_adapter` 分支，可完整驱动
/// 「发现成功 / 写模式判定 / 平台写成功与异常」；非 Windows 宿主走
/// FlutterBluePlus 分支且无已连接设备，可确定地驱动「未找到设备 /
/// 平台操作失败」的失败登记。断言按 [Platform.isWindows] 显式分支，
/// 不用"任意平台都过"的弱断言把未覆盖的分支藏起来。
class _FakeServiceObject {
  _FakeServiceObject(this.uuid);

  final String uuid;
}

class _FakeCharacteristicObject {
  _FakeCharacteristicObject(this.uuid, this.properties);

  final String uuid;

  /// 字段式属性对象（对齐 win_ble 的 `Properties`）：生产侧 `_propContains`
  /// 对 Map 按键名 + `value == true` 判定。
  final Map<String, bool> properties;
}

class _ShellProbeAdapter implements BluetoothAdapter {
  _ShellProbeAdapter();

  List<_FakeServiceObject> services = [];
  List<_FakeCharacteristicObject> characteristics = [];

  /// 非 null 时按该异常拒绝 `discoverServices`（平台发现失败路径）。
  Object? discoverServicesError;

  /// 非 null 时按该异常拒绝 `writeCharacteristic`（平台写失败路径）。
  Object? writeError;

  int discoverServicesCalls = 0;
  int writeCharacteristicCalls = 0;

  @override
  Future<List<dynamic>> discoverServices(String deviceAddress) async {
    discoverServicesCalls++;
    final error = discoverServicesError;
    if (error != null) throw error;
    return services;
  }

  @override
  Future<List<dynamic>> discoverCharacteristics(
      String deviceAddress, String serviceId) async {
    return characteristics;
  }

  @override
  Future<void> writeCharacteristic(
      String deviceAddress, String serviceId, String characteristicId,
      List<int> data,
      {bool writeWithResponse = false}) async {
    writeCharacteristicCalls++;
    final error = writeError;
    if (error != null) throw error;
  }

  // ---- 与本文件断言路径无关的平台能力 ----

  @override
  Future<void> init() async {}

  @override
  Future<void> startScan({Duration? timeout}) async {}

  @override
  Future<void> stopScan() async {}

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
  Stream<BluetoothAdapterState> get adapterStateChanged =>
      const Stream.empty();

  @override
  Stream<List<dynamic>> get scanResults => const Stream.empty();

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
  Future<List<int>> readCharacteristic(
          String deviceAddress, String serviceId, String characteristicId) async =>
      <int>[];

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
          String deviceAddress, String serviceId, String characteristicId) =>
      throw UnsupportedError('本替身不提供特征值流');
}

/// 真实设备的 OTA 特征集：FFF0 服务内 FFF2（可写）+ FFF1（可通知）。
void _otaServiceTree(_ShellProbeAdapter adapter,
    {bool writeWithResponse = true, bool withNotify = true}) {
  adapter.services = [_FakeServiceObject('fff0')];
  adapter.characteristics = [
    _FakeCharacteristicObject('fff2',
        writeWithResponse ? {'write': true} : {'writeWithoutResponse': true}),
    if (withNotify) _FakeCharacteristicObject('fff1', {'notify': true}),
  ];
}

void main() {
  late BluetoothService service;
  late _ShellProbeAdapter adapter;

  setUp(() {
    // 无 GetMaterialApp 的测试环境里 Get.snackbar 缺 Overlay 会抛异常；
    // testMode 让它降级为 debugPrint，测试聚焦外壳上报而非 UI 提示。
    Get.testMode = true;
    adapter = _ShellProbeAdapter();
    service = BluetoothService();
    service.adapterForTest = adapter;
  });

  group('P34-R04/R07 真实外壳 stats 上报', () {
    test('findExact 外壳：发现计时/成败/写模式 + stats 透传到内部服务发现',
        () async {
      _otaServiceTree(adapter);
      final stats = OtaLinkStats(label: 'upgrade');
      final result = await service.findExactOtaCharacteristicsByAddress(
        'AA:BB',
        stats: stats,
      );
      final json = stats.toJson();
      final bind = json['bind'] as Map<String, dynamic>;
      final discovers = json['discovers'] as Map<String, dynamic>;
      // 两宿主共同断言：外壳真实登记了本次发现（时钟真走过、成败已落定）。
      expect(bind['charsUs'], isNotNull, reason: '外壳必须登记发现耗时');
      // 内部服务发现必须拿到同一 stats（R04：只测外层无法归因逐分片
      // 重复发现这一待测热点）。
      expect(discovers['calls'], 1, reason: 'stats 必须透传给内部服务发现');

      if (Platform.isWindows) {
        expect(result, isNotNull);
        expect(result!['writeMode'], 'with');
        expect(bind['found'], isTrue);
        expect(bind['writeMode'], 'with', reason: '绑定实际采用的写模式');
        expect(discovers['errors'], 0);

        // 写模式不是硬编码 'with'：仅支持无响应写的 FFF2 必须记 'without'。
        _otaServiceTree(adapter, writeWithResponse: false);
        final stats2 = OtaLinkStats(label: 'upgrade');
        final result2 = await service.findExactOtaCharacteristicsByAddress(
            'AA:BB',
            stats: stats2);
        expect(result2!['writeMode'], 'without');
        expect((stats2.toJson()['bind'] as Map<String, dynamic>)['writeMode'],
            'without');

        // 发现但不合格（缺 FFF1）：found=false，且必须没有写模式——
        // 不得让"发现了 FFF2"留下绑定成功的假象。
        _otaServiceTree(adapter, withNotify: false);
        final stats3 = OtaLinkStats(label: 'upgrade');
        expect(
            await service.findExactOtaCharacteristicsByAddress('AA:BB',
                stats: stats3),
            isNull);
        final bind3 = stats3.toJson()['bind'] as Map<String, dynamic>;
        expect(bind3['found'], isFalse);
        expect(bind3['writeMode'], isNull);
      } else {
        // 非 Windows 宿主无已连接设备：真实外壳走 FlutterBluePlus 分支，
        // 立即以「未找到设备」失败——失败尝试同样入账（calls=1/errors=1）
        // 正是 R04 要求补的缺口。
        expect(result, isNull);
        expect(bind['found'], isFalse);
        expect(bind['writeMode'], isNull);
        expect(discovers['errors'], 1, reason: '未找到设备的失败发现必须计数');
      }
    });

    test('findExact 外壳：发现失败（平台异常/设备缺失）登记 errors 且 found=false',
        () async {
      adapter.discoverServicesError = StateError('platform discovery down');
      final stats = OtaLinkStats(label: 'upgrade');
      final result = await service.findExactOtaCharacteristicsByAddress(
        'AA:BB',
        stats: stats,
      );
      expect(result, isNull);
      final json = stats.toJson();
      final bind = json['bind'] as Map<String, dynamic>;
      expect(bind['charsUs'], isNotNull);
      expect(bind['found'], isFalse);
      final discovers = json['discovers'] as Map<String, dynamic>;
      expect(discovers['calls'], 1);
      expect(discovers['errors'], 1, reason: '平台异常同样是可归因的发现尝试');
    });

    test('requestOtaMtu 外壳：净荷上限来源可区分回退值与真实协商值', () async {
      final stats = OtaLinkStats(label: 'upgrade');
      final chunk = await service.requestOtaMtu('AA:BB', stats: stats);
      final bind = stats.toJson()['bind'] as Map<String, dynamic>;
      expect(bind['mtuRequested'], 247);
      expect(bind['mtuUs'], isNotNull);
      expect(bind['mtuChunkBytes'], chunk);
      // 关键区分（R04）：本例两宿主都会落到 20，但那不是真实协商结果。
      // 只有 source 能把「20 是协商结果」与「20 是回退值」分开。
      expect(bind['mtuSource'], isNotNull, reason: '净荷上限来源必须登记');
      if (Platform.isWindows) {
        // WinBle 由协议栈管理分片，不做 ATT 协商。
        expect(chunk, 20);
        expect(bind['mtuSource'], 'windows-stack-managed');
      } else {
        // 无已连接设备：拿不到协商值，回退默认净荷。
        expect(chunk, 20);
        expect(bind['mtuSource'], 'device-missing');
      }
      expect(bind['mtuSource'], isNot('negotiated'),
          reason: '回退的 20 不得被记成真实协商值');
    });

    test('writeOtaCharacteristicByAddress 外壳：成功与失败的写都登记', () async {
      if (!Platform.isWindows) {
        // 非 Windows 分支在找到设备前即失败：外层外壳仍必须登记一次失败
        // GATT 写（平台写尚未发生，platformWrites 保持 0）。
        final stats = OtaLinkStats(label: 'upgrade');
        await expectLater(
          service.writeOtaCharacteristicByAddress(
              'AA:BB', 'fff0', 'fff2', List<int>.filled(128, 0),
              stats: stats),
          throwsA(isA<UnsupportedError>()),
        );
        final json = stats.toJson();
        final w = json['gattWrites'] as Map<String, dynamic>;
        expect(w['calls'], 1);
        expect(w['errors'], 1);
        expect(w['bytes'], 128);
        expect((json['platformWrites'] as Map<String, dynamic>)['calls'], 0);
        return;
      }
      // Windows：平台写成功 → 外层 GATT 写与平台写各记一次。
      final ok = OtaLinkStats(label: 'upgrade');
      await service.writeOtaCharacteristicByAddress(
          'AA:BB', 'fff0', 'fff2', List<int>.filled(128, 0),
          stats: ok);
      final okJson = ok.toJson();
      final okW = okJson['gattWrites'] as Map<String, dynamic>;
      expect(okW['calls'], 1);
      expect(okW['errors'], 0);
      expect(okW['bytes'], 128);
      final okP = okJson['platformWrites'] as Map<String, dynamic>;
      expect(okP['calls'], 1);
      expect(okP['errors'], 0);
      expect(adapter.writeCharacteristicCalls, 1);

      // 平台写抛异常：外层与平台两层都必须记 error 并如实上抛——
      // 只统计成功写会让异常尝试从阶段统计中消失（R04）。
      adapter.writeError = StateError('gatt write failed');
      final bad = OtaLinkStats(label: 'upgrade');
      await expectLater(
        service.writeOtaCharacteristicByAddress(
            'AA:BB', 'fff0', 'fff2', List<int>.filled(128, 0),
            stats: bad),
        throwsA(isA<StateError>()),
      );
      final badJson = bad.toJson();
      final badW = badJson['gattWrites'] as Map<String, dynamic>;
      expect(badW['calls'], 1);
      expect(badW['errors'], 1);
      final badP = badJson['platformWrites'] as Map<String, dynamic>;
      expect(badP['calls'], 1);
      expect(badP['errors'], 1);
    });

    test('discoverServicesByAddress 外壳：成功与失败尝试都计入 calls/errors',
        () async {
      if (Platform.isWindows) {
        adapter.services = [_FakeServiceObject('fff0')];
        final stats = OtaLinkStats(label: 'upgrade');
        final services =
            await service.discoverServicesByAddress('AA:BB', stats: stats);
        expect(services, hasLength(1));
        final d = stats.toJson()['discovers'] as Map<String, dynamic>;
        expect(d['calls'], 1);
        expect(d['errors'], 0);
        expect(adapter.discoverServicesCalls, 1);
      } else {
        // 无已连接设备：立即失败并抛出，但尝试与耗时必须已登记。
        final stats = OtaLinkStats(label: 'upgrade');
        await expectLater(
          service.discoverServicesByAddress('AA:BB', stats: stats),
          throwsA(isA<UnsupportedError>()),
        );
        final d = stats.toJson()['discovers'] as Map<String, dynamic>;
        expect(d['calls'], 1);
        expect(d['errors'], 1);
      }
    });

    test('stats 为 null 时外壳零行为差异：返回值不变、无新增异常', () async {
      _otaServiceTree(adapter);
      final result =
          await service.findExactOtaCharacteristicsByAddress('AA:BB');
      if (Platform.isWindows) {
        expect(result, isNotNull, reason: '无 stats 不影响绑定返回值');
        expect(result!['writeMode'], 'with');
      } else {
        expect(result, isNull, reason: '无 stats 不改变"未找到设备"的结局');
      }
      expect(await service.requestOtaMtu('AA:BB'), 20);
    });
  });
}
