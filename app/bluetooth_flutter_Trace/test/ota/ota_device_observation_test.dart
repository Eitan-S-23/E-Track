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
      startScan: () async => started++,
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
      startScan: () async {},
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
      startScan: () async {},
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
      startScan: () async {},
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
    final target_line =
        lines.singleWhere((line) => line.startsWith('OTA_OBS target'));
    expect(target_line, contains('matched_by=namePrefix'));
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
        startScan: () async {},
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
      startScan: () async {},
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
}
