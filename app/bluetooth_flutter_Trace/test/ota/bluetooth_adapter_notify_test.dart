import 'dart:async';
import 'dart:io' show Platform;

import 'package:flutter/services.dart';
import 'package:flutter_blue_plus/flutter_blue_plus.dart' show BluetoothAdapterState;
import 'package:flutter_test/flutter_test.dart';
import 'package:win_ble/win_ble.dart' as win_ble;

import 'package:ble_monitor/services/bluetooth_service.dart';

/// BluetoothAdapter 测试替身（RC3-09）：驱动 Windows 通知路径。
///
/// 不绕开 adapter 的 fake 替代——被测对象是 [BluetoothService] 经
/// [BluetoothAdapter] 接口的订阅/通知链路本身，替身只实现 adapter
/// 契约（真实 WinBleAdapter 转发 `WinBle.characteristicValueStreamOf`，
/// 行为由 win_ble 1.1.1 的订阅表回放语义保证：订阅时传入的
/// address/serviceId/characteristicId 原样匹配通知事件）。
class _FakeNotifyAdapter implements BluetoothAdapter {
  /// 真实特征通知事件源（模拟 WinBle.characteristicValueStream）。
  final StreamController<List<int>> notifyController =
      StreamController<List<int>>.broadcast();

  int subscribeCalls = 0;
  int unsubscribeCalls = 0;
  List<String> lastSubscribeArgs = const [];
  List<String> lastStreamArgs = const [];
  Object? subscribeError;

  /// 平台侧 CCCD 当前是否开启（RC3-08⑦）。
  ///
  /// 真实协议栈里 CCCD 是按特征共享的单一开关：关掉后该特征上的通知
  /// 对**所有**订阅者一起停止。替身据此建模，测试用 [notifyEnabled]
  /// 门控发事件，才能检出「迟到 dispose 关掉新 owner 通知」这类缺陷，
  /// 而不只是数调用次数。
  bool notifyEnabled = false;
  /// false 模拟 notify-only 特征（readCharacteristic 抛错）。
  bool readSupported = true;
  List<int> initialReadValue = const [];

  /// 发现链注入（RC3-09）：按 win_ble 1.1.1 真实形态——
  /// discoverServices 返回字符串 UUID 列表（List<String>），
  /// discoverCharacteristics 返回真实 [win_ble.BleCharacteristic]
  /// （uuid/properties 字段式对象，无 getField/toJson 之外的成员）。
  List<String> servicesToReturn = const [];
  List<dynamic> characteristicsToReturn = const [];

  /// OTA 写入调用记录：[地址, 服务, 特征, 数据, writeWithResponse]。
  final writes = <List<dynamic>>[];

  @override
  bool get supportsCharacteristicValueStream => true;

  @override
  Stream<List<int>> characteristicValueStreamOf(
      String deviceAddress, String serviceId, String characteristicId) {
    lastStreamArgs = [deviceAddress, serviceId, characteristicId];
    return notifyController.stream;
  }

  @override
  Future<void> subscribeToCharacteristic(
      String deviceAddress, String serviceId, String characteristicId) async {
    subscribeCalls++;
    lastSubscribeArgs = [deviceAddress, serviceId, characteristicId];
    final error = subscribeError;
    if (error != null) throw error;
    notifyEnabled = true;
  }

  @override
  Future<void> unSubscribeFromCharacteristic(
      String deviceAddress, String serviceId, String characteristicId) async {
    unsubscribeCalls++;
    notifyEnabled = false;
  }

  @override
  Future<List<int>> readCharacteristic(
      String deviceAddress, String serviceId, String characteristicId) async {
    if (!readSupported) {
      throw PlatformException(code: 'read_failed');
    }
    return initialReadValue;
  }

  // ---- 以下成员与通知路径无关（本替身不触发） ----

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
      BluetoothAdapterState.unknown;

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
  Future<List<dynamic>> discoverServices(String deviceAddress) async =>
      servicesToReturn;

  @override
  Future<List<dynamic>> discoverCharacteristics(
      String deviceAddress, String serviceId) async =>
      characteristicsToReturn;

  @override
  Future<void> writeCharacteristic(String deviceAddress, String serviceId,
      String characteristicId, List<int> data,
      {bool writeWithResponse = false}) async {
    writes.add(
        [deviceAddress, serviceId, characteristicId, data, writeWithResponse]);
  }
}

const _addr = '11:22:33:44:55:66';
const _svc = 'fff0';
const _ch = 'fff1';

/// 等待异步流投递完成（broadcast 流非同步投递，flush 事件队列）。
Future<void> _flush() async {
  await Future<void>.delayed(Duration.zero);
  await Future<void>.delayed(Duration.zero);
}

void main() {
  late _FakeNotifyAdapter fake;
  late BluetoothService service;

  setUp(() {
    fake = _FakeNotifyAdapter();
    service = BluetoothService();
    service.adapterForTest = fake;
  });

  tearDown(() async {
    await fake.notifyController.close();
  });

  group('subscribeOtaNotifyByAddress（Windows 通知路径，RC3-09）', () {
    test('notify-only 特征：订阅成功且通知事件透传（不读特征）', () async {
      fake.readSupported = false; // FFF1 notify-only：读会失败。
      final stream = await service.subscribeOtaNotifyByAddress(_addr, _svc, _ch);
      expect(stream, isNotNull);
      expect(fake.subscribeCalls, 1);
      expect(fake.lastSubscribeArgs, [_addr, _svc, _ch]);
      // 通知流按同一三元组建立。
      expect(fake.lastStreamArgs, [_addr, _svc, _ch]);

      final received = <List<int>>[];
      final sub = stream!.listen(received.add);
      fake.notifyController.add([0x01, 0x02]);
      await _flush();
      expect(received, [
        [0x01, 0x02]
      ]);
      await sub.cancel();
    });

    test('连续多片：按序全部送达（轮询读版会丢片）', () async {
      final stream = await service.subscribeOtaNotifyByAddress(_addr, _svc, _ch);
      final received = <List<int>>[];
      final sub = stream!.listen(received.add);
      // 模拟 MCU 连续分片通知（60B INFO/ACK 流）。
      fake.notifyController.add([1, 1, 1]);
      fake.notifyController.add([2, 2, 2]);
      fake.notifyController.add([3, 3, 3]);
      await _flush();
      expect(received, [
        [1, 1, 1],
        [2, 2, 2],
        [3, 3, 3],
      ]);
      await sub.cancel();
    });

    test('重复片：不去重（同值通知是有效重发，由协议层幂等）', () async {
      final stream = await service.subscribeOtaNotifyByAddress(_addr, _svc, _ch);
      final received = <List<int>>[];
      final sub = stream!.listen(received.add);
      fake.notifyController.add([9, 9]);
      fake.notifyController.add([9, 9]);
      await _flush();
      // 原 last 去重版只投递一次；通知流必须两次都透传。
      expect(received.length, 2);
      expect(received[0], received[1]);
      await sub.cancel();
    });

    test('流取消：取消底层监听并退订特征', () async {
      final stream = await service.subscribeOtaNotifyByAddress(_addr, _svc, _ch);
      final sub = stream!.listen((_) {});
      await sub.cancel();
      expect(fake.unsubscribeCalls, 1);
      expect(fake.lastSubscribeArgs, [_addr, _svc, _ch]);
    });

    test('订阅失败：返回 null（不静默吞掉）', () async {
      fake.subscribeError = PlatformException(code: 'subscribe_failed');
      final stream = await service.subscribeOtaNotifyByAddress(_addr, _svc, _ch);
      expect(stream, isNull);
      expect(fake.subscribeCalls, 1);
    });
  });

  group('subscribeNotifyByAddress（遥控透传 Windows 通知路径，RC3-09）', () {
    test('notify-only 特征：初始读失败被忽略，通知正常透传', () async {
      fake.readSupported = false;
      final stream = service.subscribeNotifyByAddress(_addr, _svc, _ch);
      expect(stream, isNotNull);
      final received = <List<int>>[];
      final sub = stream!.listen(received.add);
      await _flush();
      // notify-only：初始读抛错，不产生数据、不报错。
      expect(received, isEmpty);
      fake.notifyController.add([7, 7]);
      await _flush();
      expect(received, [
        [7, 7]
      ]);
      await sub.cancel();
    });

    test('可读特征：初始读给出当前值，后续值来自通知且不去重', () async {
      fake.initialReadValue = [9, 9];
      final stream = service.subscribeNotifyByAddress(_addr, _svc, _ch);
      final received = <List<int>>[];
      final sub = stream!.listen(received.add);
      await _flush();
      expect(received, [
        [9, 9]
      ]);
      fake.notifyController.add([9, 9]);
      fake.notifyController.add([9, 9]);
      await _flush();
      // 同值通知不去重（原轮询 last 去重丢失）。
      expect(received.length, 3);
      await sub.cancel();
    });
  });

  // 以下用例走 [findExactOtaCharacteristicsByAddress] 的 Windows 分支
  // （Platform.isWindows 门控），仅在 Windows 上有意义；ubuntu CI 跳过，
  // 由 workflows/build.yml 的 windows-2022 `flutter test` 执行。
  group('findExactOtaCharacteristicsByAddress（真实 win_ble 对象形态，RC3-09）',
      skip: !Platform.isWindows ? 'Windows 对象形态发现链，由 Windows CI 执行' : false, () {
    /// 标准 OTA 形态：FFF0 服务内 FFF2（可写）+ FFF1（可通知），
    /// 混入非目标服务与可写/只读诱饵特征（顺序在前，验证精确选择
    /// 不取「第一个可写/可通知」）。
    void injectStandardShape() {
      fake.servicesToReturn = ['180f', 'fff0', 'fff4'];
      fake.characteristicsToReturn = [
        // 诱饵：可写但 UUID 非 FFF2——宽松选择会错拿它。
        win_ble.BleCharacteristic(
            uuid: 'fff5', properties: win_ble.Properties(write: true)),
        win_ble.BleCharacteristic(
            uuid: 'fff3', properties: win_ble.Properties(read: true)),
        win_ble.BleCharacteristic(
            uuid: 'fff2', properties: win_ble.Properties(write: true)),
        win_ble.BleCharacteristic(
            uuid: 'fff1', properties: win_ble.Properties(notify: true)),
      ];
    }

    test('真实 BleCharacteristic（无 getField）：能力从 Properties 字段读取，'
        '精确选择 FFF2/FFF1（RC3-09 修复鉴别）', () async {
      injectStandardShape();
      final found = await service.findExactOtaCharacteristicsByAddress(_addr);
      // 旧实现经 _getProperty 的 object.getField(...) 读能力：真实
      // BleCharacteristic 无 getField，能力全回 null → 发现返回 null，
      // 正常 FFF2/FFF1 被拒绝。修复后必须命中真实 Properties 字段。
      expect(found, isNotNull,
          reason: '真实对象形态下能力读取不得回 null 拒绝正常特征');
      expect(found!['serviceId'], 'fff0');
      expect(found['writeCharId'], 'fff2',
          reason: '不得取列表中更早出现的可写诱饵 fff5');
      expect(found['notifyCharId'], 'fff1');
      expect(found['writeMode'], 'with');
    });

    test('FFF2 仅 writeWithoutResponse：writeMode 绑定为 without', () async {
      injectStandardShape();
      fake.characteristicsToReturn = [
        win_ble.BleCharacteristic(
            uuid: 'fff2',
            properties: win_ble.Properties(writeWithoutResponse: true)),
        win_ble.BleCharacteristic(
            uuid: 'fff1', properties: win_ble.Properties(notify: true)),
      ];
      final found = await service.findExactOtaCharacteristicsByAddress(_addr);
      expect(found, isNotNull);
      expect(found!['writeMode'], 'without',
          reason: '仅无响应写时禁止按有响应写绑定（PR06）');
    });

    test('FFF2 无任何写能力：整体发现失败，不降级取其他可写特征', () async {
      injectStandardShape();
      fake.characteristicsToReturn = [
        // 诱饵：可写但 UUID 非 FFF2。
        win_ble.BleCharacteristic(
            uuid: 'fff5', properties: win_ble.Properties(write: true)),
        // FFF2 存在但不可写（read/notify）。
        win_ble.BleCharacteristic(
            uuid: 'fff2',
            properties: win_ble.Properties(read: true, notify: true)),
        win_ble.BleCharacteristic(
            uuid: 'fff1', properties: win_ble.Properties(notify: true)),
      ];
      final found = await service.findExactOtaCharacteristicsByAddress(_addr);
      expect(found, isNull,
          reason: 'OTA 红线：缺精确可写 FFF2 时不降级取 fff5 诱饵');
    });

    test('FFF1 无通知能力：整体发现失败（indicate 不满足时同理）', () async {
      injectStandardShape();
      fake.characteristicsToReturn = [
        win_ble.BleCharacteristic(
            uuid: 'fff2', properties: win_ble.Properties(write: true)),
        // FFF1 存在但不可通知（只写）。
        win_ble.BleCharacteristic(
            uuid: 'fff1', properties: win_ble.Properties(write: true)),
      ];
      final found = await service.findExactOtaCharacteristicsByAddress(_addr);
      expect(found, isNull);
    });

    test('发现→写入：writeOtaCharacteristicByAddress 按发现结果精确转发',
        () async {
      injectStandardShape();
      final found = await service.findExactOtaCharacteristicsByAddress(_addr);
      expect(found, isNotNull);
      await service.writeOtaCharacteristicByAddress(
        _addr,
        found!['serviceId']!,
        found['writeCharId']!,
        [0x01, 0x02],
        writeWithResponse: found['writeMode'] == 'with',
      );
      expect(fake.writes, hasLength(1));
      expect(fake.writes.single,
          [_addr, 'fff0', 'fff2', [0x01, 0x02], true]);
    });

    test('发现→订阅→通知：真实三元组贯通，通知片按序透传', () async {
      injectStandardShape();
      final found = await service.findExactOtaCharacteristicsByAddress(_addr);
      expect(found, isNotNull);
      final stream = await service.subscribeOtaNotifyByAddress(
          _addr, found!['serviceId']!, found['notifyCharId']!);
      expect(stream, isNotNull);
      // 订阅三元组来自发现结果，不是测试硬编码。
      expect(fake.lastSubscribeArgs, [_addr, 'fff0', 'fff1']);
      final received = <List<int>>[];
      final sub = stream!.listen(received.add);
      fake.notifyController.add([0xA5]);
      fake.notifyController.add([0x5A, 0x01]);
      await _flush();
      expect(received, [
        [0xA5],
        [0x5A, 0x01],
      ]);
      await sub.cancel();
      expect(fake.unsubscribeCalls, 1);
      expect(fake.lastSubscribeArgs, [_addr, 'fff0', 'fff1']);
    });
  });

  group('重新绑定资源所有权（RC3-09）', () {
    test('取消旧流后再订阅：旧流关闭不再吐值，退订与订阅一一对应', () async {
      final s1 = await service.subscribeOtaNotifyByAddress(_addr, _svc, _ch);
      final received1 = <List<int>>[];
      final sub1 = s1!.listen(received1.add);
      await sub1.cancel();
      expect(fake.unsubscribeCalls, 1,
          reason: '取消旧流必须退订底层特征');

      // 重新绑定：新的订阅、新的流。
      final s2 = await service.subscribeOtaNotifyByAddress(_addr, _svc, _ch);
      expect(fake.subscribeCalls, 2);
      final received2 = <List<int>>[];
      final sub2 = s2!.listen(received2.add);
      fake.notifyController.add([1]);
      fake.notifyController.add([2, 2]);
      await _flush();
      // 旧流的内部监听已随 cancel 拆除：新通知只进新流。
      expect(received1, isEmpty, reason: '旧流关闭后不得再投递');
      expect(received2, [
        [1],
        [2, 2],
      ]);
      await sub2.cancel();
      expect(fake.unsubscribeCalls, 2);
    });

    test('订阅失败后再重试：失败不留残留状态，重试可成功', () async {
      fake.subscribeError = PlatformException(code: 'subscribe_failed');
      final s1 = await service.subscribeOtaNotifyByAddress(_addr, _svc, _ch);
      expect(s1, isNull);
      // 失败路径不得已建流（否则通知会泄漏给无人消费的控制器）。
      expect(fake.lastStreamArgs, isEmpty);

      fake.subscribeError = null;
      final s2 = await service.subscribeOtaNotifyByAddress(_addr, _svc, _ch);
      expect(s2, isNotNull);
      expect(fake.subscribeCalls, 2);
      final received = <List<int>>[];
      final sub = s2!.listen(received.add);
      fake.notifyController.add([7]);
      await _flush();
      expect(received, [
        [7]
      ]);
      await sub.cancel();
    });
  });

  group('共享 CCCD 所有权（RC3-08⑦）', () {
    /// 平台侧发通知：CCCD 关闭时协议栈根本不会上报。
    void emit(_FakeNotifyAdapter fake, List<int> data) {
      if (!fake.notifyEnabled) return;
      fake.notifyController.add(data);
    }

    test('迟到的旧订阅取消：不得关闭新 owner 的共享 CCCD', () async {
      // 旧绑定：探测/放弃路径（MTU 协商失败、身份不符等）订阅已成功，
      // 但该 transport 随后被丢弃，dispose 迟到。
      final stale = await service.subscribeOtaNotifyByAddress(_addr, _svc, _ch);
      final staleReceived = <List<int>>[];
      final staleSub = stale!.listen(staleReceived.add);

      // 新 owner 在旧 dispose 之前完成订阅：CCCD 现由它持有。
      final fresh = await service.subscribeOtaNotifyByAddress(_addr, _svc, _ch);
      expect(fake.subscribeCalls, 2);
      final freshReceived = <List<int>>[];
      final freshSub = fresh!.listen(freshReceived.add);

      // 迟到的旧 dispose。
      await staleSub.cancel();
      expect(fake.unsubscribeCalls, 0,
          reason: 'CCCD 按特征共享：非 owner 的迟到取消不得调平台退订');
      expect(fake.notifyEnabled, isTrue);

      emit(fake, [0x11]);
      await _flush();
      expect(staleReceived, isEmpty, reason: '旧流自身必须停止吐值');
      expect(freshReceived, [
        [0x11]
      ], reason: '新 owner 的通知不得被旧绑定的 dispose 关掉');

      // owner 自己取消时才真正退订。
      await freshSub.cancel();
      expect(fake.unsubscribeCalls, 1);
      expect(fake.notifyEnabled, isFalse);
    });

    test('所有权转移后再重订：owner 归属跟随最新一次订阅', () async {
      final first = await service.subscribeOtaNotifyByAddress(_addr, _svc, _ch);
      final firstSub = first!.listen((_) {});
      final second = await service.subscribeOtaNotifyByAddress(_addr, _svc, _ch);
      final secondSub = second!.listen((_) {});

      // 第二次订阅接管后，第一次取消不退订。
      await firstSub.cancel();
      expect(fake.unsubscribeCalls, 0);
      // 第二次（当前 owner）取消才退订。
      await secondSub.cancel();
      expect(fake.unsubscribeCalls, 1);

      // 退订后重新订阅仍是一次全新的 owner，取消照常退订：
      // 所有权记录不得在释放后留下残留把后续取消一并吞掉。
      final third = await service.subscribeOtaNotifyByAddress(_addr, _svc, _ch);
      expect(fake.subscribeCalls, 3);
      final thirdSub = third!.listen((_) {});
      await thirdSub.cancel();
      expect(fake.unsubscribeCalls, 2);
      expect(fake.notifyEnabled, isFalse);
    });
  });
}
