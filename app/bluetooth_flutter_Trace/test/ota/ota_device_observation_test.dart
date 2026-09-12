import 'package:flutter_test/flutter_test.dart';

import 'package:ble_monitor/ota/ota_device_info.dart';
import 'package:ble_monitor/ota/ota_device_observation.dart';

/// 顶层常量（不是 main 内的局部常量）：既是默认参数取值的常量来源，也避免
/// 参数名与常量名相互遮蔽。
const _target = 'XTrace';
const _fingerprint = 'OTAOBS0123456789abcdef01234567';

/// P3-3 T1a 设备观测插桩的离线回归。
///
/// 覆盖三件事：默认关闭时零行为、启用后配置非法即 fail-closed、以及
/// 全量扫描落盘 + 命中目标自动读身份的观测行契约。连接/读身份由注入的
/// 回调替代，不触碰 FlutterBluePlus 或平台通道。
void main() {
  ObservedAdvertisement advertisement({
    String address = 'AA:BB:CC:DD:EE:FF',
    String name = 'XTrace',
    int rssi = -60,
    bool connectable = true,
    List<String> uuids = const <String>[],
    String mfg = '',
  }) =>
      ObservedAdvertisement(
        address: address,
        name: name,
        rssi: rssi,
        connectable: connectable,
        serviceUuids: uuids,
        manufacturerDataHex: mfg,
      );

  OtaDeviceObservationConfig config({
    bool enabled = true,
    String target = _target,
    String sentinel = _fingerprint,
  }) =>
      OtaDeviceObservationConfig(
        enabled: enabled,
        target: target,
        sentinel: sentinel,
      );

  /// 线端 INFO payload（50B，见 `OtaInfoPayload.parse`）：model 8B +
  /// hwRev 2B(LE) + layout 1B + boot 1B + versionCode 4B(LE) +
  /// image_sha256 32B + proto 1B + max_window_segs 1B。
  DeviceOtaInfo identity() => DeviceOtaInfo.fromInfoPayload(<int>[
        0x45, 0x2D, 0x54, 0x72, 0x61, 0x63, 0x6B, 0x00, // 'E-Track\0'
        0x01, 0x00, // hardwareRevision = 1
        0x01, // layoutId = 1
        0x01, // bootVersion = 1
        0x01, 0x00, 0x00, 0x00, // currentVersionCode = 1
        ...List<int>.filled(32, 0xAA), // image_sha256 = aa..aa
        0x01, // protocolVersion = 1
        0x04, // maxWindowSegments = 4
      ]);

  /// 观测器把绑定链交给未 await 的 Future；测试按标记轮询若干微任务。
  Future<void> pumpUntil(List<String> lines, String marker) async {
    for (var i = 0; i < 64 && !lines.any((line) => line.contains(marker)); i++) {
      await Future<void>.delayed(Duration.zero);
    }
  }

  test('默认（未注入）配置不观测，且不算非法配置', () {
    const disabled = OtaDeviceObservationConfig(
      enabled: false,
      target: '',
      sentinel: '',
    );
    expect(disabled.active, isFalse);
    // 未启用不是"非法"：problem 只在显式启用后才有意义。
    expect(disabled.problem, isNull);
    // 编译期默认值必须是关闭：除非构建侧显式注入，产物不得自带观测行为。
    expect(OtaDeviceObservationConfig.fromBuild.enabled, isFalse);
    expect(OtaDeviceObservationConfig.fromBuild.active, isFalse);
  });

  test('startFromBuild 在默认构建下不装配观测器也不启动扫描', () async {
    var started = 0;
    final observer = OtaDeviceObserver.startFromBuild(
      startScan: () async {
        started++;
        return true;
      },
      stopScan: () async {},
      connect: (_) async => true,
      readIdentity: (_) async => null,
      emit: (_) {},
    );
    expect(observer, isNull);
    expect(OtaDeviceObserver.instance, isNull);
    expect(started, 0);
  });

  test('启用后 target 或 sentinel 缺失即 fail-closed', () {
    final missingTarget = config(target: '   ');
    expect(missingTarget.active, isFalse);
    expect(missingTarget.problem, 'missing_target');
    expect(missingTarget.statusLine,
        contains('OTA_OBS config=INVALID problem=missing_target'));

    final missingSentinel = config(sentinel: '');
    expect(missingSentinel.active, isFalse);
    expect(missingSentinel.problem, 'missing_sentinel');

    final ok = config();
    expect(ok.active, isTrue);
    expect(ok.problem, isNull);
    // 启动行必须带 sentinel：运行中的 APK 要能与 CI 记录的配置指纹对上。
    expect(ok.statusLine, 'OTA_OBS config=enabled target=XTrace sentinel=$_fingerprint');
  });

  test('目标匹配：地址优先，短名字不得命中地址 hex', () {
    // 精确地址。
    expect(config(target: 'aa:bb:cc:dd:ee:ff').match(advertisement()),
        OtaObservationMatch.address);
    // 归一化地址（去分隔符、大小写不敏感）。
    expect(config(target: 'AABBCCDDEEFF').match(advertisement()),
        OtaObservationMatch.address);
    expect(config(target: 'aa-bb-cc-dd-ee-ff').match(advertisement()),
        OtaObservationMatch.address);
    // 名字精确匹配（大小写不敏感）。
    expect(config(target: 'xtrace').match(advertisement()),
        OtaObservationMatch.nameExact);
    // 模块名带后缀时的前缀兜底。
    expect(config(target: 'XTrace').match(advertisement(name: 'XTrace-1A2B')),
        OtaObservationMatch.namePrefix);
    // 反证：短名字不得被地址 hex 子串误命中（`aabb` 出现在地址里）。
    expect(config(target: 'aabb').match(advertisement(name: '其它设备')),
        OtaObservationMatch.none);
    // 反证：不相干的设备不匹配。
    expect(config().match(advertisement(address: '11:22:33:44:55:66', name: 'AIMA')),
        OtaObservationMatch.none);
  });

  test('未启用时喂入扫描结果产生零输出', () {
    final lines = <String>[];
    final observer = OtaDeviceObserver(
      config: config(enabled: false),
      startScan: () async => true,
      stopScan: () async {},
      connect: (_) async => true,
      readIdentity: (_) async => null,
      emit: lines.add,
    );
    observer.onAdvertisements(<ObservedAdvertisement>[
      advertisement(),
      advertisement(address: '11:22:33:44:55:66', name: 'AIMA'),
    ]);
    expect(lines, isEmpty);
    expect(observer.observedDevices, 0);
  });

  test('全量扫描逐台落盘，同一台只报一次明细', () {
    final lines = <String>[];
    final observer = OtaDeviceObserver(
      config: config(),
      startScan: () async => true,
      stopScan: () async {},
      connect: (_) async => true,
      readIdentity: (_) async => null,
      emit: lines.add,
    );
    observer.start();
    expect(lines.first,
        'OTA_OBS config=enabled target=XTrace sentinel=$_fingerprint');

    final first = <ObservedAdvertisement>[
      advertisement(address: '11:22:33:44:55:66', name: 'AIMA', rssi: -70),
      advertisement(address: 'AA:BB:CC:DD:EE:FF', name: 'XTrace', rssi: -55),
    ];
    observer.onAdvertisements(first);
    expect(lines.where((line) => line.startsWith('OTA_OBS scan')).single,
        'OTA_OBS scan total=2 new=2 seen=2');
    expect(lines.where((line) => line.startsWith('OTA_OBS adv')).length, 2);
    // 日志出口不再饱和：扫描到的每一台都有明细，不依赖 UI 渲染了几张卡片。
    expect(lines.any((line) => line.contains('addr=11:22:33:44:55:66')), isTrue);
    expect(lines.any((line) => line.contains('rssi=-70')), isTrue);
    expect(lines.any((line) => line.contains('connectable=true')), isTrue);

    // 第二轮仍是同一批：只报总数，不重复明细。
    lines.clear();
    observer.onAdvertisements(first);
    expect(lines, <String>['OTA_OBS scan total=2 new=0 seen=2']);
    expect(observer.observedDevices, 2);
  });

  test('命中目标后先停扫描再连接，成功即读出完整身份并收尾', () async {
    final lines = <String>[];
    var stopped = false;
    var stopBeforeConnect = false;
    String? boundAddress;
    final observer = OtaDeviceObserver(
      config: config(),
      startScan: () async => true,
      stopScan: () async => stopped = true,
      connect: (_) async {
        stopBeforeConnect = stopped;
        return true;
      },
      readIdentity: (address) async {
        boundAddress = address;
        return identity();
      },
      emit: lines.add,
    );
    observer.onAdvertisements(<ObservedAdvertisement>[
      advertisement(address: 'AA:BB:CC:DD:EE:FF', name: 'XTrace-1A2B', rssi: -48),
    ]);
    await pumpUntil(lines, 'OTA_OBS done');

    expect(stopBeforeConnect, isTrue, reason: '必须停扫描再连接');
    // 绑定用平台原样地址（小写），不是归一化 hex：服务侧按 remoteId 查设备。
    expect(boundAddress, 'aa:bb:cc:dd:ee:ff');
    final targetLine =
        lines.singleWhere((line) => line.startsWith('OTA_OBS target'));
    expect(targetLine, contains('matched_by=namePrefix'));
    expect(lines.singleWhere((line) => line.startsWith('OTA_OBS connect')),
        'OTA_OBS connect addr=aa:bb:cc:dd:ee:ff result=ok');
    final identityLine =
        lines.singleWhere((line) => line.startsWith('OTA_OBS identity'));
    expect(identityLine, contains('result=ok'));
    expect(identityLine, contains('wire=E-Track'));
    expect(identityLine, contains('model=e-track-at32f435'));
    expect(identityLine, contains('hw=1'));
    expect(identityLine, contains('layout=1'));
    expect(identityLine, contains('boot=1'));
    expect(identityLine, contains('proto=1'));
    expect(identityLine, contains('sha=${'a' * 64}'));
    expect(lines.last, 'OTA_OBS done result=ok');
  });

  test('连接失败 / 身份失败 / 身份异常都收在确定的终止行', () async {
    Future<List<String>> run({
      required bool connected,
      required DeviceOtaInfo? info,
      required bool throws,
    }) async {
      final lines = <String>[];
      final observer = OtaDeviceObserver(
        config: config(),
        startScan: () async => true,
        stopScan: () async {},
        connect: (_) async => connected,
        readIdentity: (_) async {
          if (throws) throw StateError('fixture');
          return info;
        },
        emit: lines.add,
      );
      observer.onAdvertisements(<ObservedAdvertisement>[advertisement()]);
      await pumpUntil(lines, 'OTA_OBS done');
      return lines;
    }

    expect((await run(connected: false, info: null, throws: false)).last,
        'OTA_OBS done result=connect_failed');
    expect((await run(connected: true, info: null, throws: false)).last,
        'OTA_OBS done result=identity_failed');
    final errored = await run(connected: true, info: null, throws: true);
    expect(errored.last, 'OTA_OBS done result=identity_error');
    expect(errored.singleWhere((line) => line.startsWith('OTA_OBS identity')),
        contains('result=error'));
  });

  test('只绑定一次：绑定完成后后续扫描批次不再触发第二条链路', () async {
    final lines = <String>[];
    var connects = 0;
    final observer = OtaDeviceObserver(
      config: config(),
      startScan: () async => true,
      stopScan: () async {},
      connect: (_) async {
        connects++;
        return true;
      },
      readIdentity: (_) async => identity(),
      emit: lines.add,
    );
    observer.onAdvertisements(<ObservedAdvertisement>[advertisement()]);
    await pumpUntil(lines, 'OTA_OBS done');
    observer.onAdvertisements(<ObservedAdvertisement>[
      advertisement(address: '11:22:33:44:55:66', name: 'XTrace'),
    ]);
    await Future<void>.delayed(Duration.zero);
    expect(connects, 1);
    expect(lines.where((line) => line.startsWith('OTA_OBS done')).length, 1);
  });

  test('扫描未启动：立刻给出 scan_not_started，不等窗口也不伪装成"扫了没看到"', () async {
    final lines = <String>[];
    var stopped = 0;
    final observer = OtaDeviceObserver(
      config: config(),
      startScan: () async => false,
      stopScan: () async => stopped++,
      connect: (_) async => true,
      readIdentity: (_) async => identity(),
      window: const Duration(milliseconds: 60),
      emit: lines.add,
    );
    observer.start();
    await pumpUntil(lines, 'OTA_OBS done');

    // 真机踩过：适配器状态未就绪时扫描压根没下发，日志只剩 scanned=0，
    // 与"扫了 120s 但目标不在场"长得一模一样。必须有一条确定的区分行。
    expect(lines.singleWhere((line) => line.startsWith('OTA_OBS done')),
        'OTA_OBS done result=scan_not_started');
    expect(lines.any((line) => line.startsWith('OTA_OBS window')), isFalse,
        reason: '扫描没启动就不该开窗口');
    expect(stopped, 1, reason: '没启动也要回收扫描状态');

    // 窗口时长过去后不得补出第二条终止行。
    await Future<void>.delayed(const Duration(milliseconds: 160));
    expect(lines.where((line) => line.startsWith('OTA_OBS done')).length, 1);
  });

  test('启动路径自己抛异常：照样收进 scan_not_started，不留野异常', () async {
    final lines = <String>[];
    var stopped = 0;
    // 显式标注返回类型：`() async => throw …` 推出的是 `Future<Never>`，
    // 这里要的是"签名就是 Future<bool>、但调用时失败"的那条路径。
    Future<bool> throwingStart() async {
      throw StateError('No Overlay widget found.');
    }

    final observer = OtaDeviceObserver(
      config: config(),
      startScan: throwingStart,
      stopScan: () async => stopped++,
      connect: (_) async => true,
      readIdentity: (_) async => identity(),
      window: const Duration(milliseconds: 60),
      emit: lines.add,
    );
    observer.start();
    await pumpUntil(lines, 'OTA_OBS done');

    // 真机 2026-09-12：启动失败路径内部弹 UI 提示又因缺 Overlay 再抛一次。
    // 异常逃出去就没有终止行，"启动炸了"与"尚未读取"无法区分。
    expect(lines.last, 'OTA_OBS done result=scan_not_started');
    expect(lines.singleWhere((line) => line.startsWith('OTA_OBS start')),
        contains('No Overlay widget found.'));
    expect(lines.any((line) => line.startsWith('OTA_OBS window')), isFalse);
    expect(stopped, 1);
  });

  test('窗口到期仍未命中：输出确定的 target_not_seen 终止行并停扫描', () async {
    final lines = <String>[];
    var stopped = 0;
    final observer = OtaDeviceObserver(
      config: config(),
      startScan: () async => true,
      stopScan: () async => stopped++,
      connect: (_) async => true,
      readIdentity: (_) async => identity(),
      window: const Duration(milliseconds: 60),
      emit: lines.add,
    );
    observer.start();
    // 窗口在扫描**真正启动后**才开：启动是异步的，先等 `window=open` 落盘再喂
    // 扫描结果，断言才不依赖微任务调度顺序，也不会把 30s 适配器等就绪的时间
    // 误算进 60ms 观测窗口。
    await pumpUntil(lines, 'OTA_OBS window=open');
    expect(lines.singleWhere((line) => line.startsWith('OTA_OBS window')),
        'OTA_OBS window=open windowMs=60');
    observer.onAdvertisements(<ObservedAdvertisement>[
      advertisement(address: '11:22:33:44:55:66', name: 'AIMA'),
    ]);
    expect(lines.any((line) => line.startsWith('OTA_OBS done')), isFalse,
        reason: '窗口内不得提前下终止结论');

    await Future<void>.delayed(const Duration(milliseconds: 160));

    // "没有终止行"被消灭：目标板没出现时也必须有一条确定结局。
    expect(lines.singleWhere((line) => line.startsWith('OTA_OBS done')),
        'OTA_OBS done result=target_not_seen waitedMs=60 scanned=1 '
        'target=XTrace');
    expect(stopped, 1);

    // 窗口结算后再出现目标：不得再起第二条链路（终止结局唯一）。
    observer.onAdvertisements(<ObservedAdvertisement>[advertisement()]);
    await Future<void>.delayed(Duration.zero);
    expect(lines.where((line) => line.startsWith('OTA_OBS done')).length, 1);
  });

  test('窗口内命中即取消窗口：不会补出 target_not_seen', () async {
    final lines = <String>[];
    final observer = OtaDeviceObserver(
      config: config(),
      startScan: () async => true,
      stopScan: () async {},
      connect: (_) async => true,
      readIdentity: (_) async => identity(),
      window: const Duration(milliseconds: 60),
      emit: lines.add,
    );
    observer.start();
    observer.onAdvertisements(<ObservedAdvertisement>[advertisement()]);
    await pumpUntil(lines, 'OTA_OBS done');
    await Future<void>.delayed(const Duration(milliseconds: 160));
    expect(lines.where((line) => line.startsWith('OTA_OBS done')),
        <String>['OTA_OBS done result=ok']);
    // 命中发生在窗口打开之前（`start()` 异步启动扫描），结算后 `_beginScan()`
    // 不得再补开窗口——否则终止结局会有第二行候选。
    expect(lines.any((line) => line.startsWith('OTA_OBS window')), isFalse);
  });

  test('身份为空时原样转述服务侧原因，不把三类失败压成一个词', () async {
    final lines = <String>[];
    const reason = '设备未暴露 OTA 服务（FFF0/FFF2/FFF1）';
    final observer = OtaDeviceObserver(
      config: config(),
      startScan: () async => true,
      stopScan: () async {},
      connect: (_) async => true,
      readIdentity: (_) async => null,
      identityStatus: () => reason,
      emit: lines.add,
    );
    observer.onAdvertisements(<ObservedAdvertisement>[advertisement()]);
    await pumpUntil(lines, 'OTA_OBS done');
    expect(lines.singleWhere((line) => line.startsWith('OTA_OBS identity')),
        'OTA_OBS identity addr=aa:bb:cc:dd:ee:ff result=fail status=$reason');
    expect(lines.last, 'OTA_OBS done result=identity_failed');
  });

  test('失败原因读不到时用 - 占位，不留空字段', () async {
    final lines = <String>[];
    final observer = OtaDeviceObserver(
      config: config(),
      startScan: () async => true,
      stopScan: () async {},
      connect: (_) async => true,
      readIdentity: (_) async => null,
      identityStatus: () => '   ',
      emit: lines.add,
    );
    observer.onAdvertisements(<ObservedAdvertisement>[advertisement()]);
    await pumpUntil(lines, 'OTA_OBS done');
    expect(lines.singleWhere((line) => line.startsWith('OTA_OBS identity')),
        'OTA_OBS identity addr=aa:bb:cc:dd:ee:ff result=fail status=-');
  });
}
