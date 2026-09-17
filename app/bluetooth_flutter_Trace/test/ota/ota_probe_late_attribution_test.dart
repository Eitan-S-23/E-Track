import 'dart:async';
import 'dart:convert' as convert;
import 'dart:io' show Platform;

import 'package:flutter/foundation.dart' show DebugPrintCallback, debugPrint;
import 'package:flutter_blue_plus/flutter_blue_plus.dart'
    show BluetoothAdapterState;
import 'package:flutter_test/flutter_test.dart';
import 'package:get/get.dart';

import 'package:ble_monitor/ota/ota_link_stats.dart';
import 'package:ble_monitor/services/bluetooth_service.dart';

/// P34-DA03：**被放弃尝试的迟到观测归因**（真实外壳 / 假适配器）。
///
/// 现场：重启探测每轮持有独立的 [OtaLinkStats] 实例与独立的单轮上限。
/// 上限到期时外层 `.timeout` 只放弃等待，**不取消**在飞的平台发现调用；
/// 该调用稍后恢复，观测仍会落到已封存轮次的实例上。若这些观测继续按普通
/// 样本输出，它们会落在**下一轮**尝试的摘要块内——解析器按块内计数核对会
/// 判为 STRAGGLER（归属不明，不得进入任何数值池），于是下一轮的合法观测被
/// 降级、本轮的迟到观测又无从归属。
///
/// 本文件用**真实外壳**（[BluetoothService.findExactOtaCharacteristicsByAddress]
/// → `discoverServicesByAddress` → `recordDiscover`）装配**假适配器**
/// （[BluetoothService.adapterForTest]）或只挂起平台调用入口的替身外壳，
/// 逐条断言**原始样本/摘要流**（debugPrint 行），而不是只读对象字段：
/// 行前缀、行序、摘要块内容与数值池三处都必须成立。
///
/// 两个用例覆盖同一契约的不同宿主能力：
/// - 用例 1（Windows 宿主）在假适配器内部挂起第 1 轮发现，完整复现
///   「挂起 → 到期封存 → 第 2 轮完成 → 放行第 1 轮」的交错。非 Windows
///   宿主没有可注入的适配器分支（`discoverServicesByAddress` 只在
///   `Platform.isWindows` 下走 `_adapter`），无设备即立即失败，构造不出
///   「在飞发现」；该用例显式 skip 并写明原因，不用"任意平台都过"的断言
///   把未覆盖的分支藏起来。
/// - 用例 2（双宿主）把挂起点放在平台调用**入口之上**（替身外壳，内部仍
///   委托真实的 `super.discoverServicesByAddress`），使同一契约在 Ubuntu
///   宿主同样执行：放行的发现（Windows=成功、无设备宿主=可归因的失败发现）
///   一律必须走 `OTA_LINK_LATE`。
/// - 用例 3（正对照）在同一交错下**不调用** `retire()`，证明未封存时原始流
///   确实产生"越块、无 attempt 绑定"的样本行（STRAGGLER 签名）。它是用例
///   1/2 鉴别力的凭据：修复前后两条流的差别正是被断言的那几行。
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

/// 假适配器：可让指定的第 N 次平台发现**挂起在飞行中**。
class _GatedDiscoverAdapter implements BluetoothAdapter {
  List<_FakeServiceObject> services = [];
  List<_FakeCharacteristicObject> characteristics = [];

  /// 需要挂起的 `discoverServices` 调用序号（1 起；0 = 不挂起）。
  int holdCall = 0;

  /// 挂起调用已进入平台调用（等待方据此确定"平台调用已在飞行"）。
  final Completer<void> entered = Completer<void>();

  final Completer<void> _released = Completer<void>();

  int discoverServicesCalls = 0;

  /// 放行挂起的调用（幂等）。
  void release() {
    if (!_released.isCompleted) _released.complete();
  }

  @override
  Future<List<dynamic>> discoverServices(String deviceAddress) async {
    discoverServicesCalls++;
    if (holdCall != 0 && discoverServicesCalls == holdCall) {
      if (!entered.isCompleted) entered.complete();
      await _released.future;
    }
    return services;
  }

  @override
  Future<List<dynamic>> discoverCharacteristics(
      String deviceAddress, String serviceId) async {
    return characteristics;
  }

  // ---- 与本文件断言路径无关的平台能力 ----

  @override
  Future<void> writeCharacteristic(
      String deviceAddress, String serviceId, String characteristicId,
      List<int> data,
      {bool writeWithResponse = false}) async {}

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
  Future<List<int>> readCharacteristic(String deviceAddress, String serviceId,
          String characteristicId) async =>
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

/// 挂起点在平台调用**入口之上**的替身外壳：内部仍委托真实的
/// [BluetoothService.discoverServicesByAddress]（含其 `recordDiscover` 上报），
/// 因此用例 2 在双宿主都能执行，不依赖 Windows 专有的 `_adapter` 分支。
class _HoldBeforePlatformService extends BluetoothService {
  int holdCall = 0;
  final Completer<void> entered = Completer<void>();
  final Completer<void> _released = Completer<void>();
  int discoverCalls = 0;

  void release() {
    if (!_released.isCompleted) _released.complete();
  }

  @override
  Future<List<dynamic>> discoverServicesByAddress(
    String deviceAddress, {
    OtaLinkStats? stats,
  }) async {
    discoverCalls++;
    if (holdCall != 0 && discoverCalls == holdCall) {
      if (!entered.isCompleted) entered.complete();
      await _released.future;
    }
    return super.discoverServicesByAddress(deviceAddress, stats: stats);
  }
}

/// 真实设备的 OTA 特征集：FFF0 服务内 FFF2（可写）+ FFF1（可通知）。
void _otaServiceTree(_GatedDiscoverAdapter adapter) {
  adapter.services = [_FakeServiceObject('fff0')];
  adapter.characteristics = [
    _FakeCharacteristicObject('fff2', {'write': true}),
    _FakeCharacteristicObject('fff1', {'notify': true}),
  ];
}

/// 捕获原始日志流（生产记录通道是 [OtaLinkStats] 直接调用的 `debugPrint`）。
class _PrintCapture {
  final List<String> lines = [];

  DebugPrintCallback? _original;

  void start() {
    _original = debugPrint;
    debugPrint = (String? message, {int? wrapWidth}) {
      if (message != null) lines.add(message);
    };
  }

  void stop() {
    final original = _original;
    if (original != null) debugPrint = original;
    _original = null;
  }
}

/// 第 1 轮尝试实例的时钟起点（注入时钟，微秒）。
const int _attempt1ClockUs = 1000000;

/// 单轮上限到时、封存第 1 轮的时钟时刻。
const int _retireClockUs = 2000000;

/// 第 2 轮尝试实例的时钟起点。
const int _attempt2ClockUs = 3000000;

/// 放行第 1 轮在飞发现的时钟时刻。
const int _releaseClockUs = 4000000;

/// 一次交错回合的原始日志流与两个被放弃/完成实例的返回值。
class _Interleave {
  _Interleave({
    required this.stream,
    required this.found2,
    required this.resumedAttempt1,
  });

  final List<String> stream;

  /// 第 2 轮（正常完成）发现外壳的返回值。
  final Map<String, String>? found2;

  /// 被放行的第 1 轮在飞发现恢复后的返回值。
  final Map<String, String>? resumedAttempt1;

  List<String> linesWithPrefix(String prefix) =>
      stream.where((l) => l.startsWith(prefix)).toList(growable: false);

  /// 逐条解析 `OTA_LINK_STATS` 摘要行（按尝试序号索引）——同时验证该行是
  /// jsonEncode 的规范 JSON（`Map.toString` 无法被 jsonDecode 接受）。
  Map<int, Map<String, dynamic>> get summaryByAttempt {
    final out = <int, Map<String, dynamic>>{};
    for (final line in linesWithPrefix('OTA_LINK_STATS ')) {
      final json = convert.jsonDecode(line.substring('OTA_LINK_STATS '.length))
          as Map<String, dynamic>;
      final attempt = json['attempt'] as int?;
      if (attempt == null) continue; // 轮次外壳实例（attempt=null）不在本用例范围
      out[attempt] = json;
    }
    return out;
  }

  /// 摘要行在原始流中的下标（按尝试序号索引），用于块序断言。
  Map<int, int> get summaryIndexByAttempt {
    final out = <int, int>{};
    for (var i = 0; i < stream.length; i++) {
      final line = stream[i];
      if (!line.startsWith('OTA_LINK_STATS ')) continue;
      final json = convert.jsonDecode(line.substring('OTA_LINK_STATS '.length))
          as Map<String, dynamic>;
      final attempt = json['attempt'] as int?;
      if (attempt == null) continue;
      out[attempt] = i;
    }
    return out;
  }
}

/// 交错时间线：第 1 轮平台发现在飞行中被放弃，第 2 轮正常完成，随后放行
/// 第 1 轮。步骤与生产 `_waitForTargetIdentity` 的单轮收尾一一对应
/// （retire → recordAttemptOutcome → phaseEnd → emitSummary 同一同步块）。
///
/// [seal] 为 false 时**不调用** [OtaLinkStats.retire]（其余步骤不变），
/// 用于正对照：同一交错下未封存的观测流会产生越块样本行，本文件的断言
/// 必须能把它判红。
Future<_Interleave> _runAbandonedAttemptTimeline({
  required BluetoothService service,
  required Future<void> Function() holdEntered,
  required void Function() release,
  bool seal = true,
}) async {
  final capture = _PrintCapture()..start();
  addTearDown(capture.stop);

  var clockUs = _attempt1ClockUs;
  final attempt1 = OtaLinkStats(
    label: 'probe',
    attempt: 1,
    clockUs: () => clockUs,
  );
  attempt1.phaseStart('probe_attempt');
  // 第 1 轮：`.timeout` 之后的平台调用仍在飞行，此处不 await。
  final inFlight =
      service.findExactOtaCharacteristicsByAddress('AA:BB', stats: attempt1);
  await holdEntered();

  clockUs = _retireClockUs;
  if (seal) attempt1.retire(reason: 'outer-timeout');
  attempt1.recordAttemptOutcome('abandoned');
  attempt1.phaseEnd('probe_attempt');
  attempt1.emitSummary();

  clockUs = _attempt2ClockUs;
  final attempt2 = OtaLinkStats(
    label: 'probe',
    attempt: 2,
    clockUs: () => clockUs,
  );
  attempt2.phaseStart('probe_attempt');
  final found2 = await service.findExactOtaCharacteristicsByAddress('AA:BB',
      stats: attempt2);
  attempt2.recordAttemptOutcome('completed');
  attempt2.phaseEnd('probe_attempt');
  attempt2.emitSummary();

  clockUs = _releaseClockUs;
  release();
  final resumedAttempt1 = await inFlight;

  return _Interleave(
    stream: List<String>.of(capture.lines),
    found2: found2,
    resumedAttempt1: resumedAttempt1,
  );
}

/// 迟到归因契约的公共断言：只读原始流（行前缀 / 行序）与流内摘要行。
///
/// [discoverySucceeds] 说明被放行的发现是否成功（Windows 假适配器成功、
/// 无设备宿主失败），据此断言迟到行的 `error=1` 与第 2 轮 `discovers.errors`。
void _expectLateAttributionContract(
  _Interleave it, {
  required bool discoverySucceeds,
}) {
  // 1) 封存标记恰好一条：带尝试号、原因与时刻（归属不依赖行序）。
  final retireLines = it.linesWithPrefix('OTA_LINK_RETIRE ');
  expect(retireLines, hasLength(1));
  expect(
    retireLines.single,
    'OTA_LINK_RETIRE label=probe attempt=1 reason=outer-timeout '
    'us=$_retireClockUs',
  );

  // 2) 迟到的真实发现必须走 LATE 通道，且自带 label + attempt。
  final lateLines = it.linesWithPrefix('OTA_LINK_LATE ');
  expect(lateLines, hasLength(1));
  expect(
    lateLines.single,
    startsWith('OTA_LINK_LATE label=probe attempt=1 kind=discover us='),
  );
  if (discoverySucceeds) {
    expect(lateLines.single, isNot(contains('error=1')),
        reason: 'Windows 假适配器上被放行的发现是成功观测');
  } else {
    expect(lateLines.single, contains('error=1'),
        reason: '无设备宿主上被放行的发现是失败观测，同样必须可归因');
  }

  // 3) 被放弃的尝试不得留下任何普通样本行：`OTA_LINK_SAMPLE label=probe`
  //    只应有第 2 轮的一条。此处是本文件的鉴别力所在——去掉封存（变异）后，
  //    第 1 轮的迟到发现会以 OTA_LINK_SAMPLE 落在第 2 轮摘要块内，
  //    本断言与 LATE 断言同时变红。
  final sampleLines = it.linesWithPrefix('OTA_LINK_SAMPLE ');
  expect(sampleLines, hasLength(1));
  expect(sampleLines.single, contains('label=probe kind=discover'));

  // 4) 块序：第 1 轮摘要 → 第 2 轮样本 → 第 2 轮摘要 → 迟到行。
  final summaryIndex = it.summaryIndexByAttempt;
  expect(summaryIndex.keys.toSet(), {1, 2});
  final sampleIndex =
      it.stream.indexWhere((l) => l.startsWith('OTA_LINK_SAMPLE '));
  final lateIndex = it.stream.indexWhere((l) => l.startsWith('OTA_LINK_LATE '));
  expect(summaryIndex[1]!, lessThan(sampleIndex));
  expect(sampleIndex, lessThan(summaryIndex[2]!));
  expect(summaryIndex[2]!, lessThan(lateIndex),
      reason: '迟到观测必须排在下一轮摘要块之后，且自带归属');

  // 5) 数值池：被放弃轮次不得吸收迟到观测；完成轮次干净且完整。
  final summaries = it.summaryByAttempt;
  final s1 = summaries[1]!;
  expect(s1['retired'], {'reason': 'outer-timeout', 'us': _retireClockUs});
  expect(s1['attempts'], [
    {'n': 1, 'outcome': 'abandoned'}
  ]);
  expect((s1['discovers'] as Map<String, dynamic>)['calls'], 0,
      reason: '迟到观测不得进入已封存轮次的数值池');
  expect(s1['failure'], {'stage': null, 'reason': null});

  final s2 = summaries[2]!;
  expect(s2['retired'], isNull);
  expect(s2['attempts'], [
    {'n': 2, 'outcome': 'completed'}
  ]);
  final d2 = s2['discovers'] as Map<String, dynamic>;
  expect(d2['calls'], 1);
  expect(d2['errors'], discoverySucceeds ? 0 : 1);
}

void main() {
  late BluetoothService service;
  late _GatedDiscoverAdapter adapter;

  setUp(() {
    // 无 GetMaterialApp 的测试环境里 Get.snackbar 缺 Overlay 会抛异常；
    // testMode 让它降级为 debugPrint，测试聚焦外壳上报而非 UI 提示。
    Get.testMode = true;
    adapter = _GatedDiscoverAdapter();
    service = BluetoothService();
    service.adapterForTest = adapter;
  });

  group('P34-DA03 被放弃尝试的迟到观测归因', () {
    test('假适配器挂起第 1 轮发现：封存 → 第 2 轮完成 → 放行，迟到观测显式归因',
        () async {
      _otaServiceTree(adapter);
      adapter.holdCall = 1;
      final it = await _runAbandonedAttemptTimeline(
        service: service,
        holdEntered: () => adapter.entered.future,
        release: adapter.release,
      );
      expect(adapter.discoverServicesCalls, 2, reason: '两轮各一次平台发现');
      expect(it.found2, isNotNull, reason: '第 2 轮发现在假适配器上成功');
      expect(it.resumedAttempt1, isNotNull, reason: '放行后第 1 轮发现也成功');
      _expectLateAttributionContract(it, discoverySucceeds: true);
    },
        skip: Platform.isWindows
            ? false
            : '本用例的挂起点在假适配器内部：discoverServicesByAddress 仅在 '
                'Platform.isWindows 下走可注入的 _adapter 分支，非 Windows 宿主'
                '无已连接设备、平台调用立即失败，构造不出「在飞发现」。Windows '
                '宿主由 flutter-dev-checks.yml 的 windows 作业执行；同一契约在'
                '双宿主的覆盖见下一条用例。');

    test('挂起点在平台调用入口之上（双宿主）：迟到发现同样显式归因', () async {
      _otaServiceTree(adapter);
      final shim = _HoldBeforePlatformService();
      shim.adapterForTest = adapter;
      shim.holdCall = 1;
      final it = await _runAbandonedAttemptTimeline(
        service: shim,
        holdEntered: () => shim.entered.future,
        release: shim.release,
      );
      expect(shim.discoverCalls, 2, reason: '两轮各一次发现外壳调用');
      _expectLateAttributionContract(
        it,
        discoverySucceeds: Platform.isWindows,
      );
      if (Platform.isWindows) {
        expect(it.found2, isNotNull);
        expect(it.resumedAttempt1, isNotNull);
      } else {
        expect(it.found2, isNull, reason: '无已连接设备：第 2 轮发现确定地失败');
        expect(it.resumedAttempt1, isNull,
            reason: '无已连接设备：放行的第 1 轮发现同样以失败收尾');
      }
    });

    test('正对照：不封存同一交错会产生越块样本行（本文件鉴别力的凭据）', () async {
      _otaServiceTree(adapter);
      final shim = _HoldBeforePlatformService();
      shim.adapterForTest = adapter;
      shim.holdCall = 1;
      final it = await _runAbandonedAttemptTimeline(
        service: shim,
        holdEntered: () => shim.entered.future,
        release: shim.release,
        seal: false,
      );

      // 未封存（变异体行为）：迟到的真实发现按普通样本输出，落在第 2 轮
      // 摘要块**之后**，且不带任何 attempt 绑定——这正是解析器判 STRAGGLER
      // 的签名（样本归属不明，不得进入任何数值池）。上面两条用例的断言
      // （LATE 行数、SAMPLE 行数、块序）在本流上必然变红，据此证明它们
      // 具备变异鉴别力，而不是"修复后怎么写都过"。
      expect(it.linesWithPrefix('OTA_LINK_RETIRE '), isEmpty);
      expect(it.linesWithPrefix('OTA_LINK_LATE '), isEmpty);
      final samples = it.linesWithPrefix('OTA_LINK_SAMPLE ');
      expect(samples, hasLength(2), reason: '未封存时第 1 轮的迟到发现变成第二个样本行');
      expect(
        samples.every((l) => l.contains('label=probe kind=discover')),
        isTrue,
        reason: '两条样本行前缀与字段一致，行序之外无从区分归属',
      );
      expect(samples.last, isNot(contains('attempt=')),
          reason: '普通样本行不带尝试号：归属只能靠上下文块，越块即失配');
      final summaryIndex = it.summaryIndexByAttempt;
      final strayIndex =
          it.stream.lastIndexWhere((l) => l.startsWith('OTA_LINK_SAMPLE '));
      expect(strayIndex, greaterThan(summaryIndex[2]!),
          reason: '越块样本行：落在第 2 轮摘要块内，会被判为 STRAGGLER');
      expect(it.summaryByAttempt[1]!['retired'], isNull);
      expect(it.summaryByAttempt[1]!['attempts'], [
        {'n': 1, 'outcome': 'abandoned'}
      ]);
    });
  });
}
