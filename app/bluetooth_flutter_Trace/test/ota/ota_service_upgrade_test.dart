import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:crypto/crypto.dart';
import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:get/get.dart';

import 'package:ble_monitor/ota/ota_ble_codec.dart';
import 'package:ble_monitor/ota/ota_device_info.dart';
import 'package:ble_monitor/ota/ota_download.dart';
import 'package:ble_monitor/services/app_update_service.dart';
import 'package:ble_monitor/services/bluetooth_service.dart';
import 'package:ble_monitor/services/ota_service.dart';

/// OtaService 升级集成测试（RC3 集中复审缺口补齐）：
/// 复审结论「8 个测试文件均无真实 startOtaUpgrade 调用」——本文件用
/// 真实 [OtaService] + 完整 MCU 应答 fake BLE 走通 readDeviceInfo →
/// checkFirmwareUpdate → downloadFirmware → startOtaUpgrade 全链路。
///
/// 覆盖的复审条目：
/// - RC3-02：真实 startOtaUpgrade 调用（此前只有 transport 层直测）；
/// - RC3-04：传输在途二次入口互斥（同步段忙锁拒绝）与取消后旧回调
///   晚到不复活状态（DATA ACK 挂起 → 取消 → 补发 ACK）；
/// - RC3-08：重启复核三态判定——旧身份不误判（rebootDelayProbes 模拟
///   MCU 未重启完的快速重连探测）、目标身份确认、硬件身份变化终止；
/// - RC3-12：清包纳入 owner 串行（清包期间新传输入口被拒、完成状态
///   一致发布）、取消删除包与 cancelled 终态一次性一致、终止闭锁经
///   真实 readDeviceInfo 成功解锁——状态转换由真实 service 执行，
///   不经 fake 预置字段。
///
/// fake MCU 复刻 ota_ble_session.c / ota_staging.c 真值语义（精简
/// happy path 版，完整注入矩阵见 ota_ble_transport_test.dart 的
/// _McuSim）：seq delta 三分支、BEGIN sha/totalLen 会话管理、DATA 段
/// 校验链与块收齐提交 durable、END 内容级流式摘要（journal 前缀 +
/// 顺序新收段的 sha256 必须等于 BEGIN 携带的 package sha——复述一致
/// 但内容不符同样 ERR_SHA，RC3-03）、ABORT teardown 保留 durable、
/// END OK 后切换重启后身份。
///
/// 测试可信度（RC3-02 准则）：不用 runZonedGuarded 吞异步异常；任何
/// 异步异常上抛即测试失败。GET_INFO 应答在 MCU 真值里语义就是
/// 「重启完成前仍报旧身份」，用 rebootDelayProbes 显式建模，不是
/// 随机 sleep。
/// 标准 CRC-32/ISO-HDLC（RC3-03⑤）：与 MCU boot_crc32 同构——init
/// 0xFFFFFFFF、多项式 0xEDB88320 反射、final ^0xFFFFFFFF。fake 的
/// ETU 头 CRC 门禁用。
/// 顶层声明（RC3-01）：_UpgradeFakeBle 的 inspect 门禁在 main()
/// 作用域之外引用，局部声明会造成编译期作用域错误。
int crc32Of(List<int> bytes) {
  var crc = 0xFFFFFFFF;
  for (final b in bytes) {
    crc ^= b;
    for (var i = 0; i < 8; i++) {
      final bit = crc & 1;
      crc >>= 1;
      if (bit == 1) crc ^= 0xEDB88320;
    }
  }
  return crc ^ 0xFFFFFFFF;
}

void main() {
  setUp(() {
    Get.testMode = true;
  });

  tearDown(() {
    Get.reset();
  });

  /// 升级前身份（会话开始快照）：vcode 20801，raw sha = i*3。
  final preRebootPayload = buildInfoPayload(
    model: DeviceOtaInfo.wireModelETrack,
    hardwareRevision: 3,
    layoutId: 5,
    bootVersion: 2,
    currentVersionCode: 20801,
    imageSha256: List<int>.generate(32, (i) => i * 3),
  );

  /// 重启后目标身份：vcode 20900 + 清单 targetImageSha256（'62'*32 hex）。
  final postRebootPayload = buildInfoPayload(
    model: DeviceOtaInfo.wireModelETrack,
    hardwareRevision: 3,
    layoutId: 5,
    bootVersion: 2,
    currentVersionCode: 20900,
    // 32×0x62B 的 hex 串是 '62'*32（0x62 恰是 ASCII 'b'，勿混淆成
    // hex 数字 'b'——后者是 0xBB，身份比对将永不匹配，RC3-02）。
    imageSha256: List<int>.filled(32, 0x62),
  );

  /// 重启后硬件身份变化（换设备场景）：hardwareRevision 漂移。
  final postRebootOtherHardwarePayload = buildInfoPayload(
    model: DeviceOtaInfo.wireModelETrack,
    hardwareRevision: 4,
    layoutId: 5,
    bootVersion: 2,
    currentVersionCode: 20900,
    imageSha256: List<int>.filled(32, 0x62),
  );

  /// 资产文件名（ASSET-NAMING：full 必须以 -full.etu 结尾）。
  const pkgName = 'e-track-at32f435-v2.9.0-full.etu';

  /// fake 设备身份常量（preRebootPayload 的镜像）：构造合法 ETU 头的
  /// 基准。运行期门禁基准取 fake 当前应答身份（见
  /// _UpgradeFakeBle._currentIdentityPayload）。main 内使用，fake 类
  /// 的运行期基准不引用这些编译期常量（RC3-01）。
  const fakeDeviceHardwareRev = 3;
  const fakeDeviceLayoutId = 5;
  const fakeDeviceBootVersion = 2;

  /// 构造合法 ETU 头（64B，RC3-03⑤）：字段布局对齐 MCU 真值
  /// ota_sd.c（偏移 enum + ota_sd_inspect_header）——magic "ETU1"、
  /// header_len=64、flags=0x000B（full）、algorithm=1、key=1、
  /// payload_len、payload_crc32 占位（inspect 不查）、target_vcode
  /// 20900（高于 fake 升级前 vcode 20801）、base_vcode=0、
  /// hardware_rev/layout_id/min_boot 与 fake 设备身份匹配、
  /// base_sha8 全零（full 要求）、header_crc32 覆盖前 60B。
  Uint8List buildEtuHeader(int payloadLen, {int targetVcode = 20900}) {
    final h = Uint8List(64);
    h.setRange(0, 4, [0x45, 0x54, 0x55, 0x31]); // "ETU1"
    void put16(int off, int v) {
      h[off] = v & 0xFF;
      h[off + 1] = (v >> 8) & 0xFF;
    }

    void put32(int off, int v) {
      h[off] = v & 0xFF;
      h[off + 1] = (v >> 8) & 0xFF;
      h[off + 2] = (v >> 16) & 0xFF;
      h[off + 3] = (v >> 24) & 0xFF;
    }

    put16(4, 64); // header_len
    put16(6, 0x000B); // flags：full
    put32(8, 1); // algorithm v1
    put32(12, 1); // key v1
    put32(32, payloadLen);
    put32(36, 0x11223344); // payload_crc32 占位
    put32(40, targetVcode);
    put32(44, 0); // base_vcode：full 恒 0
    put16(48, fakeDeviceHardwareRev);
    h[50] = fakeDeviceLayoutId;
    h[51] = fakeDeviceBootVersion; // min_boot <= 设备 boot_version
    // [52:60] base_sha8 保持全零（full 要求）。
    put32(60, crc32Of(h.sublist(0, 60)));
    return h;
  }

  /// 1024B = 8 段 × 128B：单块内完成（32 段容量），跨块语义由
  /// transport test 覆盖，本文件聚焦 service 集成链路。
  /// 前 64B 为合法 ETU 头（RC3-03⑤）：fake BEGIN inspect 门禁对齐
  /// 真值 ota_sd_inspect_header，随机字节会被 ERR_HDR 拒绝，全部
  /// 正常路径用例失去意义。
  Uint8List assetBytes() {
    final bytes = Uint8List.fromList(
        List<int>.generate(1024, (i) => (i * 7 + 3) & 0xFF));
    bytes.setRange(0, 64, buildEtuHeader(1024 - 64));
    return bytes;
  }

  /// latest 响应体：目标 vcode 20900，asset 与 [assetBytes] 匹配。
  String latestBody(Uint8List bytes) {
    final sha = sha256.convert(bytes).toString();
    return '{"schemaVersion":2,"requestId":"req-1","updateAvailable":true,'
        '"appId":"trace","deviceModel":"e-track-at32f435",'
        '"channel":"stable","releaseId":"rel-1","versionName":"2.9.0",'
        '"versionCode":20900,"releaseTag":"t","releaseNotes":"n",'
        '"targetImageSha256":"${'62' * 32}","targetHardware":"AT32F435RGT7",'
        '"transport":"ble","minAppVersionCode":0,'
        '"asset":{"assetId":"asset-1","kind":"full",'
        '"fileName":"$pkgName","sha256":"$sha",'
        '"sizeBytes":${bytes.length},"baseVersionCode":0,'
        '"baseImageSha256":null,'
        '"downloadUrl":"https://localhost:9/$pkgName",'
        '"expiresAt":1780000000}}';
  }

  OtaService makeService({
    required _UpgradeFakeBle ble,
    required Directory firmwareDir,
    List<String>? notifyLog,
    HttpClientAdapter? latestAdapter,
    HttpClientAdapter? downloadAdapter,
    // 目录提供器替身（RC3-04/05）：取消清理的目录解析是删除前的一处
    // 真实 IO await，用例用它把清理停在该窗口内编排「后来者接管」。
    Future<Directory> Function()? firmwareDirProvider,
    // 同资产文件族串行闸替身（RC3-04/05）：用例把清理停在「已取到删除
    // 闸、删除体尚未执行」的窗口内，编排后来者在删除 await 中接管。
    OtaFilePathGate? downloadFileGate,
  }) {
    // RC3-02⑤：默认值不得用 const []——记录替身恒 add，const 列表首条
    // 通知即抛 UnsupportedError。默认改为可增长列表。
    final log = notifyLog ?? <String>[];
    final latest = Dio()
      ..httpClientAdapter =
          latestAdapter ?? _LatestOkAdapter(latestBody(assetBytes()));
    final download = Dio()
      ..httpClientAdapter =
          downloadAdapter ?? _DownloadOkAdapter(assetBytes());
    final service = OtaService(
      bluetoothService: ble,
      dio: latest,
      downloadDio: download,
      firmwareDirProvider: firmwareDirProvider ?? () async => firmwareDir,
      latestUriBuilder: (info, appVersionCode, channel) =>
          Uri.parse('http://localhost:9/api/firmware/latest'),
      // onNotify 替身（RC3-02）：通知进 log 供断言，不走 Get.snackbar。
      onNotify: (title, message) => log.add('$title: $message'),
      downloadFileGate: downloadFileGate,
    );
    Get.put<OtaService>(service);
    return service;
  }

  Directory tempFirmwareDir() {
    final tempDir =
        Directory.systemTemp.createTempSync('ota_service_upgrade_test');
    addTearDown(() {
      if (tempDir.existsSync()) tempDir.deleteSync(recursive: true);
    });
    return tempDir;
  }

  /// 常规前置：read → check → download 完成（readyToInstall）。
  Future<_UpgradeFakeBle> prepareDownloaded({
    required Directory tempDir,
    required List<String> notifyLog,
    List<int> rebootPayload = const [],
    int rebootDelayProbes = 0,
  }) async {
    final ble = _UpgradeFakeBle(
      preRebootPayload: preRebootPayload,
      postRebootPayload:
          rebootPayload.isEmpty ? postRebootPayload : rebootPayload,
      rebootDelayProbes: rebootDelayProbes,
    );
    final service = makeService(ble: ble, firmwareDir: tempDir, notifyLog: notifyLog);
    Get.put<AppUpdateService>(_FakeAppUpdateService());

    expect(await service.readDeviceInfo('AA:BB'), isNotNull);
    expect(await service.checkFirmwareUpdate(), isNotNull);
    expect(await service.downloadFirmware(), isTrue);
    expect(service.phase, OtaPhase.readyToInstall);
    return ble;
  }

  test('端到端成功闭环：read → check → download → start → completed', () async {
    final tempDir = tempFirmwareDir();
    final notifyLog = <String>[];
    final ble = await prepareDownloaded(
      tempDir: tempDir,
      notifyLog: notifyLog,
    );
    final service = Get.find<OtaService>();
    expect(ble.beginCalls, 0, reason: '前置阶段不得发起 BEGIN');

    final ok = await service.startOtaUpgrade('AA:BB');
    expect(ok, isTrue);
    expect(service.phase, OtaPhase.completed);
    expect(service.terminalState, isNull);
    expect(
      service.upgradeStatus,
      contains('vcode 20900'),
      reason: '完成文案须携带目标 vcode（目标身份已确认）',
    );

    // MCU 侧收满：8 段全部落 staging、块收齐提交 durable=1024、
    // END 校验通过（sha 复述与 BEGIN 一致、durable==total）。
    expect(ble.beginCalls, 1);
    expect(ble.endCalls, 1);
    expect(ble.dataOffsets,
        List<int>.generate(8, (i) => i * OtaBleCodec.dataSegmentSize));
    expect(ble.stagedDurable, 1024);
    expect(ble.endShaBytes, isNotNull);
    expect(_bytesEqual(ble.endShaBytes!, ble.beginShaBytes!), isTrue,
        reason: 'END sha 复述必须与 BEGIN sha 一致（真值校验）');
    // 第一次探测即确认目标（无重启延迟注入）。
    expect(ble.probeCount, 1);
    expect(ble.abortCalls, 0, reason: '成功路径不得发 ABORT');
  });

  test('MCU 未重启完：旧身份探测不误判，第二次探测确认目标（RC3-08）',
      () async {
    final tempDir = tempFirmwareDir();
    final notifyLog = <String>[];
    final ble = await prepareDownloaded(
      tempDir: tempDir,
      notifyLog: notifyLog,
      rebootDelayProbes: 1, // 第一次探测仍报旧身份（MCU 重启中）。
    );
    final service = Get.find<OtaService>();

    final ok = await service.startOtaUpgrade('AA:BB');
    // 真实时间：第一次探测（旧身份丢弃）→ 3 秒轮询间隔 → 第二次探测。
    expect(ok, isTrue);
    expect(service.phase, OtaPhase.completed);
    expect(ble.probeCount, 2,
        reason: '旧身份必须被丢弃并继续轮询，不得把重启前身份当成功');
    expect(ble.endCalls, 1);
  }, timeout: const Timeout(Duration(seconds: 30)));

  test('重启后硬件身份变化：identityChanged 终止（RC3-08）', () async {
    final tempDir = tempFirmwareDir();
    final notifyLog = <String>[];
    final ble = await prepareDownloaded(
      tempDir: tempDir,
      notifyLog: notifyLog,
      rebootPayload: postRebootOtherHardwarePayload,
    );
    final service = Get.find<OtaService>();

    final ok = await service.startOtaUpgrade('AA:BB');
    expect(ok, isFalse);
    expect(service.phase, OtaPhase.failed);
    expect(service.terminalState?.code, 'DEVICE_IDENTITY_CHANGED');
    // 传输本身已完成（END OK），失败在重启复核。
    expect(ble.endCalls, 1);
    expect(ble.probeCount, 1);
  });

  test('传输在途二次 start：同步段忙锁拒绝，不打断在途传输（RC3-04）',
      () async {
    final tempDir = tempFirmwareDir();
    final notifyLog = <String>[];
    final ble = await prepareDownloaded(
      tempDir: tempDir,
      notifyLog: notifyLog,
    );
    final service = Get.find<OtaService>();

    // 挂起全部 DATA ACK：transfer 阻塞在等 ACK，owner 在途。
    ble.dataGate = Completer<void>();
    final startFuture = service.startOtaUpgrade('AA:BB');
    await ble.dataGated.future; // entered barrier：第一份 ACK 已挂起。
    expect(service.isUpgrading, isTrue);

    // 二次入口：同步段忙锁直接拒绝（false + 提示），不排队、不打断。
    final second = await service.startOtaUpgrade('AA:BB');
    expect(second, isFalse);
    expect(notifyLog, contains('提示: 升级已在进行中'));
    expect(ble.beginCalls, 1, reason: '被拒入口不得重建 BLE 会话');

    // 释放挂起 ACK：在途传输继续走完全程。
    ble.releaseDataGate();
    expect(await startFuture, isTrue);
    expect(service.phase, OtaPhase.completed);
    expect(ble.endCalls, 1);
  });

  test('传输在途取消：ABORT 送达 MCU、cancelled 终态不被旧 ACK 复活、包保留（RC3-04/05）',
      () async {
    final tempDir = tempFirmwareDir();
    final notifyLog = <String>[];
    final ble = await prepareDownloaded(
      tempDir: tempDir,
      notifyLog: notifyLog,
    );
    final service = Get.find<OtaService>();

    // 挂起全部 DATA ACK：MCU 侧段已落盘（gate 只挂 ACK 发送），
    // transport 阻塞在等 ACK。
    ble.dataGate = Completer<void>();
    final startFuture = service.startOtaUpgrade('AA:BB');
    await ble.dataGated.future;
    // 块收齐 barrier（RC3-02⑤）：dataGated 只证明第一份 ACK 挂起，
    // 第八段提交此前仍可能在途；取消若先于它生效，durable 断言就
    // 依赖未定的发送时序。等真实 journal 提交（8 段收齐 = 1024B）
    // 后再取消，断言才有 barrier 保证。
    var waitTicks = 0;
    while (ble.stagedDurable < 1024) {
      expect(waitTicks++ < 500, isTrue, reason: '等待块提交超时');
      await Future<void>.delayed(const Duration(milliseconds: 5));
    }

    await service.cancelUpgrade(keepPackage: true);

    // 取消终态已发布（owner 完全退出后），返回 false。
    expect(service.phase, OtaPhase.cancelled);
    expect(await startFuture, isFalse);
    // ABORT 确实送达 MCU（尽力通知设备取消），durable 保留（真值
    // teardown 语义：设备已落盘字节保留，下次传输续传）。
    expect(ble.abortCalls, 1);
    expect(ble.stagedDurable, 1024,
        reason: 'MCU durable 落盘字节天然保留（设备侧续传语义）');
    // keepPackage=true：已校验完成包保留。
    expect(service.downloadedFirmwareFile, isNotNull);

    // 旧回调晚到：挂起的 DATA ACK 补发（transport 已取消，waiters
    // 已清空），cancelled 终态不得被复活为 completed/failed。
    ble.releaseDataGate();
    await Future<void>.delayed(const Duration(milliseconds: 100));
    expect(service.phase, OtaPhase.cancelled);
    expect(ble.endCalls, 0, reason: '取消后 transport 不得继续发 END');
  });

  test('小 MTU 分片在途取消：ABORT 经写串行化完整送达，不撕裂在途帧'
      '（RC3-05⑤）', () async {
    final tempDir = tempFirmwareDir();
    final notifyLog = <String>[];
    final ble = await prepareDownloaded(
      tempDir: tempDir,
      notifyLog: notifyLog,
    );
    final service = Get.find<OtaService>();

    // 小写净荷（注入 20，等价 ATT MTU 23）：142B DATA 帧跨 8 片；
    // 每片写延迟 30ms——传输窗口期 DATA 帧几乎恒处于多片写在途状态，
    // 此时发起 cancelUpgrade，ABORT 与在途帧分片真交错（不是等
    // transfer 退出后再 ABORT）。fake 默认 247 时每帧单片，撕裂永不
    // 发生，用例无鉴别力。
    ble.otaMtu = 20;
    ble.writeChunkDelay = const Duration(milliseconds: 30);
    final startFuture = service.startOtaUpgrade('AA:BB');

    // 两段 DATA 落地后立即取消：此刻第 3 帧正处于多片写在途。
    var waitTicks = 0;
    while (ble.dataOffsets.length < 2) {
      expect(waitTicks++ < 500, isTrue, reason: '等待前两段 DATA 落地超时');
      await Future<void>.delayed(const Duration(milliseconds: 5));
    }
    await service.cancelUpgrade(keepPackage: true);

    expect(service.phase, OtaPhase.cancelled);
    expect(await startFuture, isFalse);
    // ABORT 必须以完整帧送达：fake 的跨 chunk 帧重组 + decodeFrame
    // （同步字/长度/CRC16）全部通过才会计数。无写串行化时 ABORT 会
    // 插进在途 DATA 帧的分片之间，字节流撕裂：ABORT 重组失败
    // （abortCalls 停 0）、被插入的 DATA 帧 CRC 失败。
    expect(ble.abortCalls, 1);
    expect(ble.beginCalls, 1);
    expect(ble.endCalls, 0, reason: '取消后不得继续发 END');
    // 无撕裂段：已收 DATA 偏移严格按 128 步长连续（无丢失/重复/
    // 错位）。撕裂会表现为半帧丢失或重组错误，无法构成干净序列。
    expect(ble.dataOffsets.length, greaterThanOrEqualTo(2));
    for (var i = 0; i < ble.dataOffsets.length; i++) {
      expect(ble.dataOffsets[i], i * 128,
          reason: '取消交错不得撕裂在途 DATA 帧');
    }
  }, timeout: const Timeout(Duration(seconds: 60)));

  test('清包纳入 owner：清包期间新传输入口被拒，完成后状态一致发布（RC3-12）',
      () async {
    final tempDir = tempFirmwareDir();
    final notifyLog = <String>[];
    await prepareDownloaded(
      tempDir: tempDir,
      notifyLog: notifyLog,
    );
    final service = Get.find<OtaService>();
    final pkgFile = service.downloadedFirmwareFile;
    expect(pkgFile, isNotNull);
    expect(await pkgFile!.exists(), isTrue);
    expect(service.phase, OtaPhase.readyToInstall);

    // 不 await：cleanupFirmware 的同步段已登记 owner（_isUpgrading
    // 置位），文件删除完成前的新入口必须被拒——不能只靠入口一次性
    // busy 检查（否则删除与就地读包的传输会竞争同一文件）。
    final cleanupFuture = service.cleanupFirmware();
    final startDuringCleanup = await service.startOtaUpgrade('AA:BB');
    expect(startDuringCleanup, isFalse,
        reason: '清包占用 owner 期间不得开始传输');
    expect(notifyLog, contains('提示: 升级已在进行中'));

    expect(await cleanupFuture, isTrue);
    // 状态一致发布：文件删除、引用清空、phase 回 idle、进度复位，
    // 同一轮完成——不存在「cancelled/已清理已显示但传输入口仍可用」。
    expect(service.downloadedFirmwareFile, isNull);
    expect(await pkgFile.exists(), isFalse);
    expect(service.phase, OtaPhase.idle);
    expect(service.upgradeStatus, '固件包已清理');
    expect(service.downloadProgress, 0.0);
    expect(service.durableProgress, 0.0);

    // 清包后传输入口失去包：明确失败提示，不得空引用/崩溃。
    notifyLog.clear();
    expect(await service.startOtaUpgrade('AA:BB'), isFalse);
    expect(notifyLog, contains('错误: 固件文件不存在，请先下载固件'));
  });

  test('传输在途取消删除包：cancelled 终态与包删除一次性一致发布（RC3-12）',
      () async {
    final tempDir = tempFirmwareDir();
    final notifyLog = <String>[];
    final ble = await prepareDownloaded(
      tempDir: tempDir,
      notifyLog: notifyLog,
    );
    final service = Get.find<OtaService>();
    final pkgFile = service.downloadedFirmwareFile;
    expect(pkgFile, isNotNull);

    ble.dataGate = Completer<void>();
    final startFuture = service.startOtaUpgrade('AA:BB');
    await ble.dataGated.future;

    await service.cancelUpgrade(keepPackage: false);

    // cancelled 与包删除在取消流程内一次完成：await 返回后两事实同时
    // 成立，不存在 cancelled 已显示、包随后才删的中间态（phase 与
    // 文件状态在同一同步段发布）。
    expect(service.phase, OtaPhase.cancelled);
    expect(service.downloadedFirmwareFile, isNull);
    expect(await pkgFile!.exists(), isFalse);
    expect(await startFuture, isFalse);

    // 晚到的旧 ACK 不复活终态，也不恢复包引用。
    ble.releaseDataGate();
    await Future<void>.delayed(const Duration(milliseconds: 100));
    expect(service.phase, OtaPhase.cancelled);
    expect(service.downloadedFirmwareFile, isNull);

    // 取消后无包：传输入口立即不可用（有明确提示，不是残留入口）。
    notifyLog.clear();
    expect(await service.startOtaUpgrade('AA:BB'), isFalse);
    expect(notifyLog, contains('错误: 固件文件不存在，请先下载固件'));
  });

  test('终止闭锁经重新读取身份解锁：身份漂移作废旧清单与包（RC3-08⑤/12⑤）',
      () async {
    final tempDir = tempFirmwareDir();
    final notifyLog = <String>[];
    final ble = await prepareDownloaded(
      tempDir: tempDir,
      notifyLog: notifyLog,
      rebootPayload: postRebootOtherHardwarePayload,
    );
    final service = Get.find<OtaService>();

    // 硬件身份变化 → 终止态闭锁（包保留）。
    expect(await service.startOtaUpgrade('AA:BB'), isFalse);
    expect(service.terminalState?.code, 'DEVICE_IDENTITY_CHANGED');

    // 闭锁期间传输入口被拒：不进 owner、不触 BLE。
    final beginCallsLocked = ble.beginCalls;
    expect(await service.startOtaUpgrade('AA:BB'), isFalse);
    expect(ble.beginCalls, beginCallsLocked);
    expect(service.upgradeStatus, contains('已进入终止状态'));

    // 页面「重新读取身份解锁」入口对应的服务端动作：真实
    // readDeviceInfo 成功 → 清除终止态。但重读到的是其它硬件身份
    // （rev 3→4），与上次快照不符：旧的固件清单与下载包随之作废
    // （RC3-08⑤/12⑤）——旧包按 rev3 兼容性签发，不得沿用到新硬件
    // 继续"成功"传输（该路径此前恰被当正例，掩盖了身份失效缺口）。
    final info = await service.readDeviceInfo('AA:BB');
    expect(info, isNotNull);
    expect(info!.currentVersionCode, 20900);
    expect(service.terminalState, isNull);
    expect(service.upgradeStatus, contains('设备身份已变更'));
    expect(service.downloadedFirmwareFile, isNull);

    // 旧包已作废：入口给出明确指引而非沿用旧包；不触 BLE 重建会话。
    notifyLog.clear();
    final beginCallsAfterInvalidate = ble.beginCalls;
    expect(await service.startOtaUpgrade('AA:BB'), isFalse);
    expect(notifyLog, contains('错误: 固件文件不存在，请先下载固件'));
    expect(ble.beginCalls, beginCallsAfterInvalidate);
  });

  test('下载 INVALID_PARAMETER 稳定闭锁：终止态在入口拦截后续下载'
      '（RC3-10⑤）', () async {
    final tempDir = tempFirmwareDir();
    final notifyLog = <String>[];
    final ble = _UpgradeFakeBle(
      preRebootPayload: preRebootPayload,
      postRebootPayload: postRebootPayload,
    );
    final latestAdapter = _LatestOkAdapter(latestBody(assetBytes()));
    // 下载侧状态机（按请求顺序消费）：
    // ① 401/TOKEN_EXPIRED → URL_EXPIRED 可重试（置刷新标志，无终止态
    //    时自动刷新合法）；
    // ② 400/INVALID_PARAMETER → 已知非重试码，稳定拒绝闭锁。
    // 只预置这两条：闭锁后的第二次 downloadFirmware 被入口锁拦下，
    // 不会发出第三个请求——再预置一条只会永远留在队列里，让"跨调用
    // 覆盖"看起来成立而实际空转（原用例即如此）。
    final downloadAdapter = _DownloadStagedAdapter([
      _DownloadStagedReply.json(401,
          '{"errorCode":"TOKEN_EXPIRED","message":"授权过期",'
          '"requestId":"req-e"}'),
      _DownloadStagedReply.json(400,
          '{"errorCode":"INVALID_PARAMETER","message":"参数非法",'
          '"requestId":"req-9"}'),
    ]);
    final service = makeService(
      ble: ble,
      firmwareDir: tempDir,
      notifyLog: notifyLog,
      latestAdapter: latestAdapter,
      downloadAdapter: downloadAdapter,
    );
    Get.put<AppUpdateService>(_FakeAppUpdateService());

    expect(await service.readDeviceInfo('AA:BB'), isNotNull);
    expect(await service.checkFirmwareUpdate(), isNotNull);
    expect(latestAdapter.calls, 1);

    // 第一轮：URL_EXPIRED 无终止态 → 自动重新 latest（合法，calls 1→2）
    // 再重下；重下命中 INVALID_PARAMETER → 已知非兼容码稳定拒绝：
    // 闭锁终止态、清资产并复位刷新标志，requestId 贯通供排查。
    expect(await service.downloadFirmware(), isFalse);
    expect(latestAdapter.calls, 2);
    expect(downloadAdapter.requests, 2, reason: '两条预置响应都被真实消费');
    expect(downloadAdapter.remaining, 0);
    expect(service.terminalState?.code, 'INVALID_PARAMETER');
    expect(service.terminalState?.retryableLater, isFalse);
    expect(service.terminalState?.requestId, 'req-9');
    expect(service.phase, OtaPhase.failed);
    expect(service.downloadedFirmwareFile, isNull);

    // 第二轮：非 retryableLater 终止态存在 → 入口 _terminalLocked 直接
    // 拒绝，连 HTTP 都不发（既不查 latest 也不重下）。这条断言的判据是
    // 入口锁，不是内层刷新守卫——刷新标志的复位另由下一个用例鉴别。
    expect(await service.downloadFirmware(), isFalse);
    expect(latestAdapter.calls, 2);
    expect(downloadAdapter.requests, 2);
    expect(service.upgradeStatus, contains('已进入终止状态'));
    expect(service.terminalState?.code, 'INVALID_PARAMETER');
    expect(service.phase, OtaPhase.failed);
  });

  test('稳定终止复位刷新标志：解锁重查后的普通失败不得触发本轮自动刷新'
      '（RC3-10⑤）', () async {
    final tempDir = tempFirmwareDir();
    final notifyLog = <String>[];
    final ble = _UpgradeFakeBle(
      preRebootPayload: preRebootPayload,
      postRebootPayload: postRebootPayload,
    );
    final latestAdapter = _LatestOkAdapter(latestBody(assetBytes()));
    // 预置响应顺序是鉴别力的全部关键：只要稳定拒绝那一刻标志不是真的
    // 处于 true，本条用例就退化成空转（只要 ② 缺位，外层刷新路径在刷新
    // 前就会把 ① 置的标清掉，稳定拒绝时标志本来就是 false）。
    //   ① 401 TOKEN_EXPIRED → URL_EXPIRED（可重试码）：置刷新标志，并经
    //      外层自动刷新重下一次；
    //   ② 同一次 downloadFirmware 内的第二次尝试再次 URL_EXPIRED：外层
    //      刷新只做一次，此处重新置位后调用结束，标志真实残留为 true；
    //   ③ 400 INVALID_PARAMETER：稳定拒绝分支——本次要鉴别的那一行必须
    //      在这里把残留的 true 复位；
    //   ④ 200 但字节与清单 sha 不符：SHA_MISMATCH 既不是稳定拒绝码，也
    //      不在 {RANGE_AT_END/URL_EXPIRED/ASSET_CONFLICT/LOCAL_CORRUPT}
    //      刷新码集合内，本轮自身既不置位也不闭锁——是否发生第四次
    //      latest 完全取决于 ③ 是否复位了标志。
    // 鉴别力：删掉 _downloadOnce 稳定拒绝分支里的 `_needsFreshManifest
    // = false`，残留标志会让 ④ 之后的外层自动刷新条件成立 → latest 4 次
    // （计数断言直接打红），并额外发出一次下载尝试（预置已耗尽，fake 抛
    // StateError，由 _downloadOnce 兜底为普通失败）。
    final downloadAdapter = _DownloadStagedAdapter([
      _DownloadStagedReply.json(401,
          '{"errorCode":"TOKEN_EXPIRED","message":"授权过期",'
          '"requestId":"req-e"}'),
      _DownloadStagedReply.json(401,
          '{"errorCode":"TOKEN_EXPIRED","message":"授权过期",'
          '"requestId":"req-e2"}'),
      _DownloadStagedReply.json(400,
          '{"errorCode":"INVALID_PARAMETER","message":"参数非法",'
          '"requestId":"req-9"}'),
      _DownloadStagedReply.raw(
        200,
        Uint8List.fromList(List<int>.generate(
            assetBytes().length, (i) => (i * 11 + 5) & 0xFF)),
      ),
    ]);
    final service = makeService(
      ble: ble,
      firmwareDir: tempDir,
      notifyLog: notifyLog,
      latestAdapter: latestAdapter,
      downloadAdapter: downloadAdapter,
    );
    Get.put<AppUpdateService>(_FakeAppUpdateService());

    expect(await service.readDeviceInfo('AA:BB'), isNotNull);
    expect(await service.checkFirmwareUpdate(), isNotNull);

    // 第一轮：① 置刷新标志 → 外层自动刷新重下 → ② 重新置位。调用结束时
    // 标志真实残留为 true（刷新路径只在刷新前清掉 ① 置的那一份），
    // URL_EXPIRED 不闭锁资产。
    expect(await service.downloadFirmware(), isFalse);
    expect(latestAdapter.calls, 2, reason: '① 之后应恰好自动刷新一次');
    expect(downloadAdapter.requests, 2);
    expect(service.terminalState, isNull, reason: '可重试失败不闭锁');

    // 第二轮：进入稳定拒绝分支时标志为 true（该状态在测试侧不可直接读取，
    // 由下面第三轮的 latest 计数反证；若这里标志本来就是 false，本条鉴别
    // 就失效，故 ② 不可省）。稳定拒绝闭锁资产并复位标志。
    expect(await service.downloadFirmware(), isFalse);
    expect(downloadAdapter.requests, 3);
    expect(service.terminalState?.code, 'INVALID_PARAMETER');

    // 真实 readDeviceInfo 成功（同一身份、同一地址）→ 终止态解除；
    // 稳定拒绝已清资产，必须重新检查更新才能再下载。
    expect(await service.readDeviceInfo('AA:BB'), isNotNull);
    expect(service.terminalState, isNull);
    expect(await service.checkFirmwareUpdate(), isNotNull);
    expect(latestAdapter.calls, 3);

    // 第三轮：SHA 校验失败（普通失败，不闭锁）。刷新标志已在第二轮
    // 稳定拒绝时复位 → 本轮不得自动重新 latest、不得重下。
    notifyLog.clear();
    expect(await service.downloadFirmware(), isFalse);
    expect(latestAdapter.calls, 3, reason: '残留刷新标志不得触发第四次 latest');
    expect(downloadAdapter.requests, 4, reason: '不得因残留标志再重下一次');
    expect(downloadAdapter.remaining, 0);
    expect(service.phase, OtaPhase.failed);
    expect(service.terminalState, isNull, reason: 'SHA 不符是普通失败，不闭锁');
    expect(service.downloadedFirmwareFile, isNull);
    expect(
      notifyLog.any((line) => line.contains('SHA-256 校验失败')),
      isTrue,
      reason: '失败原因如实上报，不得静默',
    );
  });

  // ---- RC3-03：fake MCU 段判据模型测试 ----
  // 这些用例直接对 fake 打帧，不经 transport：产品 transport 永远不会
  // 发出错位段、非尾部短段或同 offset 异内容段，靠它驱动无法进入 fake
  // 的这些分支。fake 判据本身错了，上层一切"MCU 会拒绝"的断言都是自证。
  group('fake MCU 段判据（RC3-03，直接打帧）', () {
    /// 任意长度合法资产：前 64B 为与 total 自洽的 ETU 头
    /// （inspect 要求 64+payload_len == total_len），否则 BEGIN 直接
    /// ERR_LEN，后续 DATA 判据一条都进不去。
    Uint8List assetOfLength(int total) {
      final bytes = Uint8List.fromList(
          List<int>.generate(total, (i) => (i * 7 + 3) & 0xFF));
      bytes.setRange(0, 64, buildEtuHeader(total - 64));
      return bytes;
    }

    /// 裸 DATA payload 组装：绕开 [OtaBleCodec.encodeDataPayload] 的
    /// 客户端侧参数断言（它会先抛错位/超长），本组测的是 MCU 侧判据。
    Uint8List rawDataPayload(int offset, List<int> content) {
      final p = Uint8List(4 + content.length);
      p[0] = offset & 0xFF;
      p[1] = (offset >> 8) & 0xFF;
      p[2] = (offset >> 16) & 0xFF;
      p[3] = (offset >> 24) & 0xFF;
      p.setRange(4, p.length, content);
      return p;
    }

    /// 建好一个 ACTIVE 会话的 fake：BEGIN(seq=10) → session=1、
    /// expected_seq=11、durable=0。返回值即 fake 本体。
    Future<_UpgradeFakeBle> activeFake(Uint8List asset) async {
      final ble = _UpgradeFakeBle(
        preRebootPayload: preRebootPayload,
        postRebootPayload: postRebootPayload,
      );
      await ble.writeOtaCharacteristicByAddress(
        'AA:BB',
        'fff0',
        'fff2',
        OtaBleCodec.encodeCommand(
          cmd: OtaBleCodec.cmdBegin,
          session: 0,
          seq: 10,
          payload: OtaBleCodec.encodeBeginPayload(
            totalLen: asset.length,
            packageSha256: sha256.convert(asset).bytes,
            etuHeader: Uint8List.fromList(asset.sublist(0, 64)),
          ),
        ),
      );
      expect(ble.beginAckStatuses, [OtaBleCodec.statusOk],
          reason: '模型前置：BEGIN 必须建立 ACTIVE 会话');
      return ble;
    }

    /// 对已 ACTIVE 的 fake 写一帧 DATA（session 恒 1：首个会话）。
    Future<void> writeData(
      _UpgradeFakeBle ble,
      int seq,
      int offset,
      List<int> content,
    ) async {
      await ble.writeOtaCharacteristicByAddress(
        'AA:BB',
        'fff0',
        'fff2',
        OtaBleCodec.encodeCommand(
          cmd: OtaBleCodec.cmdData,
          session: 1,
          seq: seq,
          payload: rawDataPayload(offset, content),
        ),
      );
    }

    /// 顺序灌满 [0, count*128)，seq 从 11 起递增。返回下一个可用 seq。
    Future<int> fillSegments(
        _UpgradeFakeBle ble, Uint8List asset, int count) async {
      for (var i = 0; i < count; i++) {
        await writeData(
            ble, 11 + i, i * 128, asset.sublist(i * 128, (i + 1) * 128));
      }
      return 11 + count;
    }

    test('offset 未按 128B 对齐 → ERR_OFFSET（真值 :526-532）', () async {
      final asset = assetOfLength(1024);
      final ble = await activeFake(asset);
      await writeData(ble, 11, 64, asset.sublist(64, 192));
      expect(ble.dataAckStatuses.last, OtaBleCodec.statusErrOffset,
          reason: '旧 fake 把三条判据并成一条 ERR_LEN，错分类');
    });

    test('非尾部短段 → ERR_FRAME（真值 :533-541）', () async {
      // 段净荷恒 128B，唯一例外是包尾段。off=0、len=64 既非 128 也不
      // 触及包尾（0+64 != 1024），真值判 ERR_FRAME。
      // ERR_FRAME 在 transport 的 _resumeStatuses 里 → 有界重 BEGIN
      // 续传；旧 fake 的 ERR_LEN 不在其中 → 直接终止。分类错误会把
      // 可恢复错误伪装成终止错误。
      final asset = assetOfLength(1024);
      final ble = await activeFake(asset);
      await writeData(ble, 11, 0, asset.sublist(0, 64));
      expect(ble.dataAckStatuses.last, OtaBleCodec.statusErrFrame);
    });

    test('尾部短段（off+len == total_len）放行（真值 :533-541 反向）',
        () async {
      // 与上一例只差 offset：证明 ERR_FRAME 不是"见短段就拒"。
      // total_len 取 1028（非 128 整数倍）才存在真正的尾部短段。
      final asset = assetOfLength(1028);
      final ble = await activeFake(asset);
      final seq = await fillSegments(ble, asset, 8);
      // 尾部段：off=1024，len=4，off+len == 1028 == total_len。
      await writeData(ble, seq, 1024, asset.sublist(1024, 1028));
      expect(ble.dataAckStatuses.last, OtaBleCodec.statusOk);
      expect(ble.stagedDurable, 1028, reason: '9 段收齐 → 块提交到包尾');
    });

    test('整段跨越包尾（off+len > total_len）→ ERR_OFFSET（真值 :542-548）',
        () async {
      // len==128 过得了会话层长度门，但 1024+128 > 1028，命中范围判据的
      // 第二个析取项。与下一例（off >= total_len，第一个析取项）区分。
      final asset = assetOfLength(1028);
      final ble = await activeFake(asset);
      await writeData(ble, 11, 1024, List<int>.filled(128, 0xAB));
      expect(ble.dataAckStatuses.last, OtaBleCodec.statusErrOffset);
    });

    test('off >= total_len → ERR_OFFSET（真值 :542-548）', () async {
      final asset = assetOfLength(1024);
      final ble = await activeFake(asset);
      await writeData(ble, 11, 1024, List<int>.filled(128, 0xAB));
      expect(ble.dataAckStatuses.last, OtaBleCodec.statusErrOffset);
    });

    test('同 offset 同内容重发 → DUPLICATE 幂等 OK'
        '（真值 ota_staging_receive :508-516）', () async {
      final asset = assetOfLength(1024);
      final ble = await activeFake(asset);
      await writeData(ble, 11, 0, asset.sublist(0, 128));
      // seq 12 = 当前 expected_seq：走 staging 重复段分支，而不是
      // 会话层"seq 落后即幂等回 OK"的分支。
      await writeData(ble, 12, 0, asset.sublist(0, 128));
      expect(ble.dataAckStatuses.last, OtaBleCodec.statusOk);
      expect(ble.stagedDurable, 0, reason: '块未收齐，durable 不前移');
    });

    test('同 offset 不同内容 → ABORTED 且会话 teardown'
        '（真值 ota_staging.c:510-513 → ota_ble_session.c:585-591）',
        () async {
      // 旧 fake 只看 offset 是否已收过，内容不同也回 OK：把"同一段收到
      // 两份互相矛盾的数据"这类真实损坏静默吞掉，只能拖到 END 整包 SHA
      // 才暴露，MCU 侧的 fail-closed teardown 语义完全不被建模。
      final asset = assetOfLength(1024);
      final ble = await activeFake(asset);
      await writeData(ble, 11, 0, asset.sublist(0, 128));
      final corrupted = Uint8List.fromList(asset.sublist(0, 128));
      corrupted[7] ^= 0xFF;
      await writeData(ble, 12, 0, corrupted);
      expect(ble.dataAckStatuses.last, OtaBleCodec.statusAborted);
      // teardown 已发生：后续同会话 DATA 落 ERR_STATE。
      await writeData(ble, 13, 128, asset.sublist(128, 256));
      expect(ble.dataAckStatuses.last, OtaBleCodec.statusErrState);
      // teardown 只清 RAM 层，journal durable 保留（此处本就是 0）。
      expect(ble.stagedDurable, 0);
    });

    test('已提交 offset 的重复 DATA 幂等 OK（真值 :550-558）', () async {
      final asset = assetOfLength(1024);
      final ble = await activeFake(asset);
      final seq = await fillSegments(ble, asset, 8);
      expect(ble.stagedDurable, 1024, reason: '8 段收齐 → 块提交');
      // durable 之后重发首段：走会话层幂等分支，不进 staging，因此即便
      // 内容被改也不触发 ERR_DATA（真值同款：已提交区间不再比对 RAM
      // 块缓冲——该区间的正确性由 END 的整包 SHA 兜底）。
      final corrupted = Uint8List.fromList(asset.sublist(0, 128));
      corrupted[3] ^= 0xFF;
      await writeData(ble, seq, 0, corrupted);
      expect(ble.dataAckStatuses.last, OtaBleCodec.statusOk);
    });
  });

  // ---- 取消/后台恢复的 owner 与资源生命周期（RC3-04⑦/08⑦/12⑦）----
  // 复审缺口：此前用例只在 cancel/resume 返回后断言终态字段，取消窗口
  // 内「后来者下载」「迟到复核结论」「发布与删除的次序」「失败读取后的
  // 资产归属基准」都无法观测。本组用闸门把 service 停在真实交错点再编排
  // 后续操作，并在发布时刻挂监听器核对 IO 事实，而非事后补断言。
  group('取消与后台恢复的 owner/资源生命周期（RC3-04⑦/08⑦/12⑦）', () {
    test('身份 A 持有资产 → 读取失败 → 成功读取 B：A 资产整体作废（RC3-12⑦）',
        () async {
      final tempDir = tempFirmwareDir();
      final notifyLog = <String>[];
      final ble = await prepareDownloaded(
        tempDir: tempDir,
        notifyLog: notifyLog,
      );
      final service = Get.find<OtaService>();
      expect(service.downloadedFirmwareFile, isNotNull);

      // 中间一次读取失败（服务发现失败）：快照清空，但资产签署者基准
      // 不得被失败读取洗掉——旧实现把漂移基准绑在上次快照上，失败读取
      // 置空快照后，下次成功读到的 B 与 null 比对不算漂移，A 签发的
      // 清单/资产/已验证包被沿用给 B。
      ble.discoverReplies.add(null);
      expect(await service.readDeviceInfo('AA:BB'), isNull);
      expect(service.upgradeStatus, '设备未暴露 OTA 服务（FFF0/FFF2/FFF1）');
      expect(service.downloadedFirmwareFile, isNotNull,
          reason: '失败读取不得顺手作废已校验资产（读取与下载是两条线）');

      // 随后成功读取到不同硬件身份 B：以资产签署者（A）为基准判漂移，
      // A 的清单/资产/包字段整体作废。
      ble.discoverReplies.clear();
      ble.infoOverride = postRebootOtherHardwarePayload;
      final infoB = await service.readDeviceInfo('AA:BB');
      expect(infoB, isNotNull);
      expect(infoB!.currentVersionCode, 20900, reason: '读到的是 B 的身份');
      expect(service.downloadedFirmwareFile, isNull,
          reason: '身份 A 的已下载包不得沿用到身份 B（RC3-12⑦）');
      expect(service.upgradeStatus, contains('设备身份已变更'));

      // 旧入口立即失效：给出明确指引，不重建 BLE 会话。
      notifyLog.clear();
      final beginCalls = ble.beginCalls;
      expect(await service.startOtaUpgrade('AA:BB'), isFalse);
      expect(notifyLog, contains('错误: 固件文件不存在，请先下载固件'));
      expect(ble.beginCalls, beginCalls);
    });

    test('取消清理持闸期间不得发布取消文案或 phase：清理与终态发布原子（RC3-12）',
        () async {
      final tempDir = tempFirmwareDir();
      final notifyLog = <String>[];
      final ble = await prepareDownloaded(
        tempDir: tempDir,
        notifyLog: notifyLog,
      );
      final service = Get.find<OtaService>();
      final pkgFile = service.downloadedFirmwareFile;
      expect(pkgFile, isNotNull);

      // 传输在途：首个 DATA ACK 挂在闸门内。
      ble.dataGate = Completer<void>();
      final startFuture = service.startOtaUpgrade('AA:BB');
      await ble.dataGated.future;

      // 发布时刻观测（RC3-12）：取消文案每发布一次即记录当时的 IO 事实。
      // 进度卡的 Obx 直接读 upgradeStatus、phase 决定传输入口能否重新
      // 进入，二者都必须与「包已处置」一致——只看取消返回后的最终值
      // 会漏掉「文案/phase 先发布、清理后跑」的中间态。
      var cancelTextPublishes = 0;
      final fileExistsAtPublish = <bool>[];
      final sub = service.upgradeStatusRx.listen((status) {
        if (status != '操作已取消') return;
        cancelTextPublishes++;
        fileExistsAtPublish.add(pkgFile!.existsSync());
      });

      // 清理前的 IO 屏障：ABORT 物理写在途，cancelUpgrade 停在
      // await transport.abortBestEffort()——包删除与终态发布都还没开始。
      ble.abortWriteGate = Completer<void>();
      final cancelFuture = service.cancelUpgrade(keepPackage: false);
      await ble.abortWriteEntered.future;

      // 释放 DATA ACK 闸门，让旧 owner 的真实退出路径跑完（传输以
      // CANCELLED 中止、service 捕获后必须静默退出）。旧 owner 的退出
      // 不得在清理完成前留下任何「已取消」可观测状态：文案与 cancelled
      // phase 都由 cancelUpgrade 在清理后一次性发布，否则 UI 会按
      // 「已取消且包已处置」渲染并重新放开已作废的传输入口。
      ble.releaseDataGate();
      expect(await startFuture, isFalse, reason: '旧 owner 已在 ABORT 在途期间退出');
      expect(cancelTextPublishes, 0,
          reason: '清理未完成不得发布取消文案（取消文案 ⇒ 包已处置）');
      expect(service.phase, isNot(OtaPhase.cancelled),
          reason: '清理未完成不得置 cancelled（否则传输入口重新可用）');
      expect(service.terminalState, isNull, reason: '取消清理期间不得产生终止态');
      expect(pkgFile!.existsSync(), isTrue,
          reason: '闸门未释放时包清理尚未开始，不得提前处置资产');

      // 释放 ABORT 写：取消路径完成清理后一次性发布文案 + phase。
      ble.abortWriteGate!.complete();
      await cancelFuture;
      await Future<void>.delayed(Duration.zero);
      await sub.cancel();

      expect(cancelTextPublishes, 1,
          reason: '取消文案只发布一次，且发生在包清理之后');
      expect(fileExistsAtPublish, [false],
          reason: '「操作已取消」发布时包文件必须已删除（发布时刻 IO 屏障）');
      expect(await startFuture, isFalse);
      expect(service.phase, OtaPhase.cancelled);
      expect(service.upgradeStatus, '操作已取消');
      expect(service.downloadedFirmwareFile, isNull);
      expect(await pkgFile.exists(), isFalse);
    }, timeout: const Timeout(Duration(seconds: 30)));

    test('取消窗口内同资产重下：旧取消不得拔掉后来者的下载（RC3-04⑦）',
        () async {
      final tempDir = tempFirmwareDir();
      final notifyLog = <String>[];
      final ble = _UpgradeFakeBle(
        preRebootPayload: preRebootPayload,
        postRebootPayload: postRebootPayload,
      );
      final downloadAdapter = _DownloadGatedAdapter(assetBytes());
      final service = makeService(
        ble: ble,
        firmwareDir: tempDir,
        notifyLog: notifyLog,
        downloadAdapter: downloadAdapter,
      );
      Get.put<AppUpdateService>(_FakeAppUpdateService());

      // 首轮：闸门未设，read → check → download 直接完成。
      expect(await service.readDeviceInfo('AA:BB'), isNotNull);
      expect(await service.checkFirmwareUpdate(), isNotNull);
      expect(await service.downloadFirmware(), isTrue);
      expect(service.downloadedFirmwareFile, isNotNull);

      // 传输在途（首个 DATA ACK 挂起）。
      ble.dataGate = Completer<void>();
      final startFuture = service.startOtaUpgrade('AA:BB');
      await ble.dataGated.future;

      // 取消发起，ABORT 物理写被闸住：cancelUpgrade 停在
      // await transport.abortBestEffort()。transport.cancel() 已同步失败
      // 全部等待者——旧 owner 不等 ABORT 写完成即可退出，这就是
      // 「取消等待期间新 owner 可登记」的真实窗口。
      ble.abortWriteGate = Completer<void>();
      final cancelFuture = service.cancelUpgrade(keepPackage: true);
      await ble.abortWriteEntered.future;
      expect(await startFuture, isFalse,
          reason: '旧 owner 必须在 ABORT 在途期间即可退出');

      // owner 2：清掉旧包，让后续重下是真实的新文件写入
      // （cleanupFirmware 保留清单，重下无需重新 check）。
      expect(await service.cleanupFirmware(), isTrue);
      expect(service.downloadedFirmwareFile, isNull);

      // owner 3：同一资产重新下载，首块后闸住——此刻 `.part` 与 sidecar
      // 均已落盘（sidecar 先于流循环写入），正是旧取消目录扫描的匹配
      // 目标（同 assetId、同 partial 文件名）。
      final holdGate = Completer<void>();
      downloadAdapter.gate = holdGate;
      final redownload = service.downloadFirmware();
      await downloadAdapter.entered.future;

      // 释放 ABORT 写：cancelUpgrade 走到 epoch 屏障。
      ble.abortWriteGate!.complete();
      await cancelFuture;

      // 屏障生效：取消窗口内后来者进出过（owner 2/3），旧取消不得再对
      // 同 assetId 执行 cancel(keepPartial:false)——那会取消新下载令牌并
      // 删除它正在写的 partial。两主机各自的失败形态：Windows 删除打开
      // 中的文件抛错 → 「本地临时文件清理失败」通知；POSIX unlink 成功
      // → 重下在最终 rename 处失败。断言组合在两主机都有鉴别力。
      expect(notifyLog.any((l) => l.contains('本地临时文件清理失败')), isFalse,
          reason: '旧取消不得触碰后来者的 partial（Windows 鉴别点）');
      holdGate.complete();
      expect(await redownload, isTrue,
          reason: '旧取消不得拔掉后来者的下载（POSIX 鉴别点）');
      expect(service.phase, OtaPhase.readyToInstall);
      expect(service.downloadedFirmwareFile, isNotNull);

      ble.releaseDataGate();
    }, timeout: const Timeout(Duration(seconds: 60)));

    test('取消清理停在内层 IO 时后来者接管同资产：删除边界归属复核（RC3-04/05）',
        () async {
      final tempDir = tempFirmwareDir();
      final notifyLog = <String>[];
      final ble = _UpgradeFakeBle(
        preRebootPayload: preRebootPayload,
        postRebootPayload: postRebootPayload,
      );
      final downloadAdapter = _DownloadGatedAdapter(assetBytes());
      // 目录闸门（RC3-04/05）：只挂起取消清理的那一次目录解析。此时取消
      // 已越过 owner 代次检查、进入老 downloader 的删除流程；目录之后的
      // 枚举与 sidecar 读同样在 await 中，后来者正是在这个窗口里接管
      // 同一资产——按 assetId/文件名匹配挡不住，只有删除边界上的归属
      // 复核能拦下旧清理。
      final dirGate = Completer<void>();
      final dirGateEntered = Completer<void>();
      var dirGateArmed = false;
      Future<Directory> gatedDirProvider() async {
        if (dirGateArmed) {
          dirGateArmed = false;
          if (!dirGateEntered.isCompleted) dirGateEntered.complete();
          await dirGate.future;
        }
        return tempDir;
      }

      final service = makeService(
        ble: ble,
        firmwareDir: tempDir,
        notifyLog: notifyLog,
        downloadAdapter: downloadAdapter,
        firmwareDirProvider: gatedDirProvider,
      );
      Get.put<AppUpdateService>(_FakeAppUpdateService());

      // 首轮完整下载（未设闸门）：取消时无在途下载方，partial 清理直达
      // 目录解析这一 IO 点。
      expect(await service.readDeviceInfo('AA:BB'), isNotNull);
      expect(await service.checkFirmwareUpdate(), isNotNull);
      expect(await service.downloadFirmware(), isTrue);
      expect(service.downloadedFirmwareFile, isNotNull);

      dirGateArmed = true;
      final cancelFuture = service.cancelUpgrade(keepPackage: true);
      await dirGateEntered.future;

      // 后来者接管同一资产：新 attempt 序号前进，写出与旧 attempt 同名
      // 的 `.part` 与 sidecar（assetId、文件名本来就相同）。
      final holdGate = Completer<void>();
      downloadAdapter.gate = holdGate;
      final redownload = service.downloadFirmware();
      await downloadAdapter.entered.future;

      // 放行旧清理：枚举读到的是新 attempt 的 sidecar（assetId 匹配），
      // 归属已在删除边界转移，旧清理必须整体放弃。
      dirGate.complete();
      await cancelFuture;

      expect(notifyLog.any((l) => l.contains('本地临时文件清理失败')), isFalse,
          reason: '旧清理不得删除后来者正在写的 partial（Windows 鉴别点）');
      holdGate.complete();
      expect(await redownload, isTrue,
          reason: '旧清理不得按路径删掉后来者的 partial/sidecar（POSIX 鉴别点）');
      expect(service.downloadedFirmwareFile, isNotNull);
      expect(service.phase, OtaPhase.readyToInstall);
    }, timeout: const Timeout(Duration(seconds: 60)));

    test('清理已取删除闸、删除体未执行时后来者接管：part/sidecar/tmp 均不得按路径删除'
        '（RC3-04/05）', () async {
      // 与上一条的鉴别力差别：上一条把接管编排在**目录解析**这个外层
      // await 上，拦下它的是 `_deleteAssetPartials` 的外层归属判定。
      // 本条的接管落在 `_deletePartial` **已排到串行闸、删除体尚未执行**
      // 的窗口内——外层判定此刻已经通过。只在闸外再做一次 epoch 判断
      // （或只补一次删除前判断）在这里都会红：判定与 delete() 之间的
      // await 正是后来者挤进来的缝隙，旧清理会按路径删掉后来者的
      // `.part`/sidecar/tmp。
      final tempDir = tempFirmwareDir();
      final notifyLog = <String>[];
      final ble = _UpgradeFakeBle(
        preRebootPayload: preRebootPayload,
        postRebootPayload: postRebootPayload,
      );
      final downloadAdapter = _DownloadGatedAdapter(assetBytes());
      final gate = _TakeoverGate();
      final service = makeService(
        ble: ble,
        firmwareDir: tempDir,
        notifyLog: notifyLog,
        downloadAdapter: downloadAdapter,
        downloadFileGate: gate,
      );
      Get.put<AppUpdateService>(_FakeAppUpdateService());

      // 前置：read → check → download 完成——取消时 `_download` 快照存在，
      // 才会走到 downloader 的资产清理（无在途下载方，清理直达删除闸）。
      expect(await service.readDeviceInfo('AA:BB'), isNotNull);
      expect(await service.checkFirmwareUpdate(), isNotNull);
      expect(await service.downloadFirmware(), isTrue);

      // 清掉首轮完成包（保留清单，重下无需重新 check）：后来者的 rename
      // 是真实的新文件落成，不依赖平台对「rename 覆盖既有文件」的差异。
      expect(await service.cleanupFirmware(), isTrue);
      expect(service.downloadedFirmwareFile, isNull);

      // 盘上留一份该资产的中断残留，作为旧清理的匹配目标：接管前它属于
      // 旧 owner，接管后同名同路径由后来者接管。
      final bytes = assetBytes();
      const partName = '$pkgName.part';
      final part = File('${tempDir.path}${Platform.pathSeparator}$partName');
      part.writeAsBytesSync(Uint8List.sublistView(bytes, 0, 256), flush: true);
      final sidecar = File('${part.path}.json');
      sidecar.writeAsStringSync(
        jsonEncode({
          'assetId': 'asset-1',
          'releaseId': 'rel-1',
          'sha256': sha256.convert(bytes).toString(),
          'sizeBytes': bytes.length,
          'strongEtag': null,
          'updatedAtMs': DateTime.now().millisecondsSinceEpoch,
        }),
        flush: true,
      );

      // 取消：清理到达删除闸时被替身挂起（闸已取到、删除体未执行）。
      gate.arm();
      final cancelFuture = service.cancelUpgrade(keepPackage: true);
      await gate.entered.future;

      // 后来者接管（真实 service owner 路径）：新 attempt 序号前进，重下
      // 同一资产。（旧残留的 sidecar 无强 ETag，后来者按合同作废重下，
      // 走的正是「删除旧残留 + 重建同一路径」的流程——`entered` 时刻它
      // 自己的字节是否已落盘取决于写盘与读流的事件顺序，因此下面先做
      // 有界观察，不等落盘就让断言跑起来会把编排时机问题误判成产品缺陷。）
      final holdGate = Completer<void>();
      downloadAdapter.gate = holdGate;
      final redownload = service.downloadFirmware();
      await downloadAdapter.entered.future;
      // 有界观察同名 `.part` 落盘（上限 2s，只在目录内容变化时记录时间线）。
      // 前置锚点：后来者的文件必须在放行旧清理之前存在——后续「旧清理不得
      // 按路径删除」的鉴别力以此为前提，否则断言的对象根本不存在。时间线、
      // 闸调用序、抓取序一并写进失败原因，用于区分「编排时机」与「旧清理
      // 越权删除」两种解释。
      final timeline = <String>[];
      var lastSeen = _dirSnapshot(tempDir);
      final deadline = DateTime.now().add(const Duration(seconds: 2));
      while (!part.existsSync() && DateTime.now().isBefore(deadline)) {
        await Future<void>.delayed(const Duration(milliseconds: 5));
        final now = _dirSnapshot(tempDir);
        if (now != lastSeen) {
          lastSeen = now;
          timeline.add(now);
        }
      }
      final afterTakeover = _dirSnapshot(tempDir);
      final takeoverBytes = part.existsSync() ? part.lengthSync() : -1;
      expect(part.existsSync(), isTrue,
          reason: '前置：后来者进入写盘阶段后同名 .part 必须已创建；'
              '接管后目录=$afterTakeover；目录时间线=$timeline；'
              '闸调用=${gate.calls}；抓取=${downloadAdapter.fetches}；'
              'phase=${service.phase}；status=${service.upgradeStatus}；'
              '通知=$notifyLog');

      // 同族 tmp：旧清理的第三个删除目标，同样不得被按路径删除。
      final sidecarTmp = File('${sidecar.path}.tmp');
      sidecarTmp.writeAsStringSync('{"assetId":"asset-1"}', flush: true);

      // 放行旧清理：闸内归属复核必须看到归属已转移，整体放弃删除。
      gate.resume.complete();
      await cancelFuture;

      expect(notifyLog.any((l) => l.contains('本地临时文件清理失败')), isFalse,
          reason: '旧清理不得触碰后来者的同族文件（Windows 鉴别点：'
              '删除在写文件抛错会走清理失败通知）');
      expect(part.existsSync(), isTrue,
          reason: '旧清理不得按路径删除后来者的 .part；'
              '接管后目录=$afterTakeover（.part ${takeoverBytes}B），'
              '放行后目录=${_dirSnapshot(tempDir)}；'
              '闸调用=${gate.calls}；抓取=${downloadAdapter.fetches}');
      expect(sidecar.existsSync(), isTrue,
          reason: '旧清理不得按路径删除后来者的 sidecar；'
              '放行后目录=${_dirSnapshot(tempDir)}；'
              '闸调用=${gate.calls}');
      expect(sidecarTmp.existsSync(), isTrue,
          reason: '旧清理不得按路径删除同族 tmp；'
              '放行后目录=${_dirSnapshot(tempDir)}；'
              '闸调用=${gate.calls}');

      // 后来者继续完成下载（POSIX 鉴别点：旧清理若删掉在写文件，重下会在
      // 最终 rename 处失败或落到错误字节）。
      holdGate.complete();
      expect(await redownload, isTrue, reason: '旧清理不得拔掉后来者的下载');
      expect(service.phase, OtaPhase.readyToInstall);
      expect(service.downloadedFirmwareFile, isNotNull);
    }, timeout: const Timeout(Duration(seconds: 60)));

    test('后台恢复一级复核：链路代次变化 → DEVICE_LINK_CHANGED 可重试终止（RC3-08⑦）',
        () async {
      final tempDir = tempFirmwareDir();
      final notifyLog = <String>[];
      final ble = await prepareDownloaded(
        tempDir: tempDir,
        notifyLog: notifyLog,
      );
      final service = Get.find<OtaService>();

      ble.dataGate = Completer<void>();
      final startFuture = service.startOtaUpgrade('AA:BB');
      await ble.dataGated.future;
      // 基线：readDeviceInfo 绑定 + startOtaUpgrade 绑定复核各一次。
      expect(ble.discoverCalls, 2);
      expect(ble.getInfoCalls, 2);

      // 后台 → 绑定后链路代次前进（模拟系统断开重连）。
      notifyLog.clear();
      service.pauseForBackground();
      ble.linkGeneration = 1;
      await service.resumeFromBackground();

      // 一级复核即终止：不得触发重新发现、不得发 INFO。
      expect(ble.discoverCalls, 2,
          reason: '链路代次不符时不得继续二三级复核');
      expect(ble.getInfoCalls, 2);
      expect(service.terminalState?.code, 'DEVICE_LINK_CHANGED');
      expect(service.terminalState?.retryableLater, isTrue);
      expect(notifyLog.any((l) => l.startsWith('错误: ') && l.contains('已终止')),
          isTrue, reason: 'fail closed 必须经通知暴露终止事实');
      expect(await startFuture, isFalse);
      expect(service.phase, OtaPhase.cancelled);
      expect(ble.abortCalls, 1, reason: 'fail closed 必须尽力 ABORT 停止发送循环');
    });

    test('后台恢复一级复核补位：复核 await 期间链路代次前进 → DEVICE_LINK_CHANGED（RC3-08⑦）',
        () async {
      final tempDir = tempFirmwareDir();
      final notifyLog = <String>[];
      final ble = await prepareDownloaded(
        tempDir: tempDir,
        notifyLog: notifyLog,
      );
      final service = Get.find<OtaService>();

      ble.dataGate = Completer<void>();
      final startFuture = service.startOtaUpgrade('AA:BB');
      await ble.dataGated.future;
      expect(ble.discoverCalls, 2);
      expect(ble.getInfoCalls, 2);

      service.pauseForBackground();
      // 入口那次一级复核读到的代次还没变，链路代次在**重新发现 await
      // 期间**才前进（系统断开重连正好落在两个 await 之间）。只在入口
      // 同步读一次挡不住这种交错：旧会话会继续在绑定于旧链路的
      // transport 上发送字节，正是本节要防的情形。
      ble.rediscoverGate = Completer<void>();
      final resumeFuture = service.resumeFromBackground();
      await ble.rediscoverEntered.future;
      ble.linkGeneration = 1;
      ble.rediscoverGate!.complete();
      await resumeFuture;

      // 二级复核已进入并返回了一致的结果，仍必须以新代次作废。
      expect(ble.discoverCalls, 3);
      expect(ble.getInfoCalls, 2, reason: '链路已变时不得继续三级复核');
      expect(service.terminalState?.code, 'DEVICE_LINK_CHANGED');
      expect(service.terminalState?.retryableLater, isTrue);
      expect(notifyLog.any((l) => l.startsWith('错误: ') && l.contains('已终止')),
          isTrue, reason: 'fail closed 必须经通知暴露终止事实');
      expect(await startFuture, isFalse);
      expect(service.phase, OtaPhase.cancelled);
      expect(ble.abortCalls, 1, reason: 'fail closed 必须尽力 ABORT 停止发送循环');
    }, timeout: const Timeout(Duration(seconds: 30)));

    test('后台恢复二级复核：特征重发现不一致 → DEVICE_LINK_CHANGED（RC3-08⑦）',
        () async {
      final tempDir = tempFirmwareDir();
      final notifyLog = <String>[];
      final ble = await prepareDownloaded(
        tempDir: tempDir,
        notifyLog: notifyLog,
      );
      final service = Get.find<OtaService>();

      ble.dataGate = Completer<void>();
      final startFuture = service.startOtaUpgrade('AA:BB');
      await ble.dataGated.future;

      service.pauseForBackground();
      // 链路代次未变，但重新发现返回了不同的写模式（GATT 重建后语义
      // 变化）——旧句柄/写模式沿用会把帧写进非 OTA 通道。
      ble.discoverReplies.add({
        'serviceId': 'fff0',
        'writeCharId': 'fff2',
        'notifyCharId': 'fff1',
        'writeMode': 'without',
      });
      await service.resumeFromBackground();

      expect(ble.discoverCalls, 3, reason: '二级复核确实执行了重新发现');
      expect(ble.getInfoCalls, 2, reason: '特征不一致时不得发 INFO');
      expect(service.terminalState?.code, 'DEVICE_LINK_CHANGED');
      expect(service.terminalState?.retryableLater, isTrue);
      expect(await startFuture, isFalse);
      expect(ble.abortCalls, 1);
    });

    test('后台恢复三级复核：INFO 身份漂移 → DEVICE_IDENTITY_CHANGED（RC3-08⑦）',
        () async {
      final tempDir = tempFirmwareDir();
      final notifyLog = <String>[];
      final ble = await prepareDownloaded(
        tempDir: tempDir,
        notifyLog: notifyLog,
      );
      final service = Get.find<OtaService>();

      ble.dataGate = Completer<void>();
      final startFuture = service.startOtaUpgrade('AA:BB');
      await ble.dataGated.future;

      service.pauseForBackground();
      // 链路代次与特征都一致，但 INFO 报出了另一台设备的硬件身份：
      // 继续发送会把旧包字节写进新设备，必须 fail closed 且不可重试。
      ble.infoOverride = postRebootOtherHardwarePayload;
      await service.resumeFromBackground();

      expect(ble.discoverCalls, 3, reason: '二级复核通过后才轮到 INFO');
      expect(ble.getInfoCalls, 3, reason: '三级复核确实发了 INFO');
      expect(service.terminalState?.code, 'DEVICE_IDENTITY_CHANGED');
      expect(service.terminalState?.retryableLater, isFalse,
          reason: '身份漂移是稳定拒绝，不得标成可重试');
      expect(await startFuture, isFalse);
      expect(service.phase, OtaPhase.cancelled);
      expect(ble.abortCalls, 1);
    });

    test('后台复检迟到发布：取消后的复核结论不得覆盖取消终态（RC3-04⑦）',
        () async {
      final tempDir = tempFirmwareDir();
      final notifyLog = <String>[];
      final ble = await prepareDownloaded(
        tempDir: tempDir,
        notifyLog: notifyLog,
      );
      final service = Get.find<OtaService>();

      ble.dataGate = Completer<void>();
      final startFuture = service.startOtaUpgrade('AA:BB');
      await ble.dataGated.future;

      service.pauseForBackground();
      // 把 resume 停在二级复核（重新发现）中途，然后用户取消——
      // 若无迟到发布屏障，闸门释放后 mismatch 结论会以旧会话的
      // 终止态覆盖取消终态。
      ble.discoverReplies.add({
        'serviceId': 'fff0',
        'writeCharId': 'fff2',
        'notifyCharId': 'fff1',
        'writeMode': 'without',
      });
      ble.rediscoverGate = Completer<void>();
      final resumeFuture = service.resumeFromBackground();
      await ble.rediscoverEntered.future;

      notifyLog.clear();
      await service.cancelUpgrade(keepPackage: true);
      expect(service.phase, OtaPhase.cancelled);
      expect(service.upgradeStatus, '操作已取消');
      expect(await startFuture, isFalse);

      // 释放复核闸门：迟到的复核结论必须静默丢弃。
      ble.rediscoverGate!.complete();
      await resumeFuture;
      await Future<void>.delayed(const Duration(milliseconds: 100));
      expect(service.terminalState, isNull,
          reason: '迟到复核结论不得覆盖取消终态');
      expect(notifyLog.any((l) => l.contains('已终止')), isFalse,
          reason: '迟到复核结论不得再发终止通知');
      expect(service.phase, OtaPhase.cancelled);
      expect(service.upgradeStatus, '操作已取消');
    }, timeout: const Timeout(Duration(seconds: 30)));

    test('后台恢复三级复核通过：恢复发送并完成传输（RC3-08⑦ 正例）', () async {
      final tempDir = tempFirmwareDir();
      final notifyLog = <String>[];
      final ble = await prepareDownloaded(
        tempDir: tempDir,
        notifyLog: notifyLog,
      );
      final service = Get.find<OtaService>();

      ble.dataGate = Completer<void>();
      final startFuture = service.startOtaUpgrade('AA:BB');
      await ble.dataGated.future;

      service.pauseForBackground();
      await service.resumeFromBackground();

      // 三级复核全部真实执行（重新发现 + INFO），且不置终止态。
      expect(ble.discoverCalls, 3);
      expect(ble.getInfoCalls, 3);
      expect(service.terminalState, isNull, reason: '复核通过不得置终止态');

      // 恢复后释放挂起 ACK：传输走完全程（含 END 与重启后身份复核）。
      ble.releaseDataGate();
      expect(await startFuture, isTrue);
      expect(service.phase, OtaPhase.completed);
      expect(ble.endCalls, 1);
      expect(ble.abortCalls, 0, reason: '复核通过不得发 ABORT');
      // 复核的 GET_INFO 不得消耗会话 seq（RC3-08⑦）：会话外查询混入
      // 会话计数器会让恢复后的 DATA 整体跳号被 ERR_SEQ 拒绝，触发内部
      // ABORT+BEGIN 重对齐并整段重发（beginCalls>1 / 段重复）。
      expect(ble.beginCalls, 1, reason: '复核通过不得触发内部恢复重对齐');
      expect(ble.dataOffsets.length, 8, reason: '1024B 包恰好 8 段，不得重发');
      expect(ble.dataOffsets.toSet().length, 8, reason: '段偏移不得重复');
    }, timeout: const Timeout(Duration(seconds: 30)));
  });
}

/// latest 固定 200 JSON mock（本文件所有用例的 HTTP 侧行为恒 ok，
/// 注入矩阵在 ota_service_session_test.dart 覆盖）。
class _LatestOkAdapter implements HttpClientAdapter {
  _LatestOkAdapter(this.body);

  final String body;

  /// latest 请求数（RC3-10⑤）：观测下载失败后的自动刷新是否发生。
  int calls = 0;

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    calls++;
    return ResponseBody.fromString(body, 200, headers: {
      'content-type': ['application/json'],
    });
  }

  @override
  void close({bool force = false}) {}
}

/// download 固定 200 完整 body mock（流式 + Content-Length 一致，
/// RC3-11 长度校验依据）。
class _DownloadOkAdapter implements HttpClientAdapter {
  _DownloadOkAdapter(this.bytes);

  final Uint8List bytes;

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    return ResponseBody(
      Stream<Uint8List>.fromIterable([bytes]),
      200,
      headers: {
        'content-length': ['${bytes.length}'],
      },
    );
  }

  @override
  void close({bool force = false}) {}
}

/// 下载侧预置响应（RC3-10⑤）：JSON 错误体，或 200 原始包体
/// （content-length 与字节数一致，供 SHA 校验分支使用）。
class _DownloadStagedReply {
  _DownloadStagedReply.json(this.status, this.body) : bytes = null;

  _DownloadStagedReply.raw(this.status, Uint8List data)
      : body = null,
        bytes = data;

  final int status;
  final String? body;
  final Uint8List? bytes;
}

/// 下载侧状态机：按请求顺序逐个消费预置响应（每请求一份，耗尽即抛）。
///
/// [requests]/[remaining] 供用例断言"目标响应真正被消费"与"没有多发
/// 请求"：只断言终态而不数请求，会让预置却从未被消费的响应伪装成覆盖
/// （RC3-10⑤ 原用例即因此空转）。
class _DownloadStagedAdapter implements HttpClientAdapter {
  _DownloadStagedAdapter(this.replies);

  final List<_DownloadStagedReply> replies;
  var _index = 0;

  /// 已消费的下载请求数。
  int get requests => _index;

  /// 未被消费的预置响应数。
  int get remaining => replies.length - _index;

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    if (_index >= replies.length) {
      throw StateError('download 请求数超出预置: ${_index + 1}');
    }
    final reply = replies[_index++];
    final bytes = reply.bytes;
    if (bytes != null) {
      return ResponseBody(
        Stream<Uint8List>.fromIterable([bytes]),
        reply.status,
        headers: {
          'content-length': ['${bytes.length}'],
        },
      );
    }
    return ResponseBody.fromString(reply.body!, reply.status, headers: {
      'content-type': ['application/json'],
    });
  }

  @override
  void close({bool force = false}) {}
}

/// 删除闸替身（RC3-04/05）：在「已排到串行闸、删除体尚未执行」之间插入
/// 一次编排窗口。
///
/// [arm] 后下一次 [run] 不会立即执行删除体，而是先完成 [entered] 并等
/// [resume]；用例在该窗口内让后来者接管同一资产（真实 service owner 路径
/// 重下，写出同名 `.part`/sidecar）。此时旧清理的外层归属判定都已通过，
/// 只有闸内复核能拦下按路径删除。
///
/// 注意替身在调用 `super.run` **之前** 挂起，因此窗口内闸链尚为空：
/// 后来者自己的写入/rename 仍能正常取闸，不会与本次编排互锁。
class _TakeoverGate extends OtaFilePathGate {
  bool _armed = false;

  /// 旧清理已到达删除闸（删除体未执行）。
  final entered = Completer<void>();

  /// 用例放行旧清理继续走进删除体。
  final resume = Completer<void>();

  /// 闸调用序（诊断用）：`<桶尾>#armed` 或 `<桶尾>#pass`。
  final List<String> calls = <String>[];

  void arm() => _armed = true;

  @override
  Future<T> run<T>(String bucket, Future<T> Function() body) {
    calls.add('${bucket.split(Platform.pathSeparator).last}'
        '#${_armed ? 'armed' : 'pass'}');
    if (!_armed) return super.run(bucket, body);
    _armed = false;
    return () async {
      if (!entered.isCompleted) entered.complete();
      await resume.future;
      return super.run(bucket, body);
    }();
  }
}

/// 下载侧可闸适配器（RC3-04⑦）：正文首块交付后挂起，[entered] 完成
/// 即证明下载已真实进入写盘阶段（`.part` 与 sidecar 已落盘），测试据此
/// 在「取消窗口内新 owner 的同资产下载在途」时刻做后续编排。
class _DownloadGatedAdapter implements HttpClientAdapter {
  _DownloadGatedAdapter(this.bytes);

  final Uint8List bytes;

  /// 非 null 且未完成时，首块之后挂起正文流。
  Completer<void>? gate;

  /// 首块已交付且正文流正被闸住。
  final Completer<void> entered = Completer<void>();

  /// 抓取序（诊断用）：每次 fetch 一行，记录是否带 Range 与当时有无闸门。
  final List<String> fetches = <String>[];

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    fetches.add('range=${options.headers.containsKey('Range')}'
        '|gate=${gate != null}');
    final half = bytes.length ~/ 2;
    Stream<Uint8List> body() async* {
      yield Uint8List.sublistView(bytes, 0, half);
      final g = gate;
      if (g != null && !g.isCompleted) {
        if (!entered.isCompleted) entered.complete();
        await g.future;
      }
      yield Uint8List.sublistView(bytes, half);
    }

    return ResponseBody(body(), 200, headers: {
      'content-length': ['${bytes.length}'],
    });
  }

  @override
  void close({bool force = false}) {}
}

/// fake AppUpdateService：固定 appVersionCode，跳过平台通道。
class _FakeAppUpdateService extends AppUpdateService {
  @override
  Future<int> getLocalAppVersionCode() async => 42;
}

/// 目录内容快照（只取文件名），用于把「盘上到底有什么」写进断言失败原因。
String _dirSnapshot(Directory dir) {
  if (!dir.existsSync()) return '(目录不存在)';
  final names = dir
      .listSync()
      .map((e) => e.uri.pathSegments.last)
      .toList()
    ..sort();
  return names.isEmpty ? '(空)' : names.join(',');
}

bool _bytesEqual(List<int> a, List<int> b) {
  if (a.length != b.length) return false;
  for (var i = 0; i < a.length; i++) {
    if (a[i] != b[i]) return false;
  }
  return true;
}

/// BEGIN ACK payload 组包（§5.6，10B）。
Uint8List packBeginAck(int status, int session, int durableOff, int bitmap) {
  final p = Uint8List(10);
  p[0] = status;
  p[1] = session;
  _writeU32(p, 2, durableOff);
  _writeU32(p, 6, bitmap);
  return p;
}

/// DATA/END/ABORT ACK payload 组包（§5.6，9B）。
Uint8List packAck(int status, int durableOff, int bitmap) {
  final p = Uint8List(9);
  p[0] = status;
  _writeU32(p, 1, durableOff);
  _writeU32(p, 5, bitmap);
  return p;
}

void _writeU32(Uint8List p, int at, int v) {
  p[at] = v & 0xFF;
  p[at + 1] = (v >> 8) & 0xFF;
  p[at + 2] = (v >> 16) & 0xFF;
  p[at + 3] = (v >> 24) & 0xFF;
}

/// 完整 MCU 应答 fake BLE（extends BluetoothService 覆写 OTA 公开
/// 方法；onInit 空实现阻止真实平台通道初始化）。
///
/// GET_INFO 应答按重启状态机切换：
/// - END OK 前：恒报 preRebootPayload（升级前身份）；
/// - END OK 后（MCU 已切新固件）：前 [rebootDelayProbes] 次探测仍报
///   旧身份（重启未完成的快速重连窗口），之后报 postRebootPayload。
class _UpgradeFakeBle extends BluetoothService {
  _UpgradeFakeBle({
    required this.preRebootPayload,
    required this.postRebootPayload,
    this.rebootDelayProbes = 0,
  });

  final List<int> preRebootPayload;
  final List<int> postRebootPayload;
  final int rebootDelayProbes;

  final _notifyController = StreamController<List<int>>.broadcast();

  // ---- MCU 会话状态（复刻 ota_ble_session.c 真值精简版）----
  static const int _idle = 0;
  static const int _active = 1;
  int _state = _idle;
  int _sessionId = 0;
  int _nextSessionId = 1;
  int _expectedSeq = 0;
  Uint8List _beginSha = Uint8List(0);
  int _totalLen = 0;
  int _stagedDurable = 0;
  int _stagedBitmap = 0;
  final _segContent = <int, Uint8List>{};
  /// journal 落盘字节（真实提交块追加；erase 清零）。长度恒等于
  /// [_stagedDurable]，是流式 SHA resume 前缀的唯一数据源。
  Uint8List _stagedBytes = Uint8List(0);
  /// 会话流式 SHA 字节流（真值增量 SHA 的等价模型）：BEGIN 时重置为
  /// journal durable 前缀，新写入段按接收顺序追加，END 一次性 final
  /// （RC3-03 内容级 oracle）。
  final _shaBytes = <int>[];

  // ---- 重启状态机（RC3-08）----
  bool _rebooted = false;
  int _probeCount = 0;
  /// END OK 后的 GET_INFO 探测次数（观测断言用）。
  int get probeCount => _probeCount;
  /// journal durable 落盘偏移（观测断言用；teardown 保留）。
  int get stagedDurable => _stagedDurable;

  /// 当前 GET_INFO 应答身份 payload（不递增 probe 计数）——BEGIN
  /// inspect 门禁的设备基准（RC3-03⑤）：升级前报 preReboot 身份，
  /// END OK 重启后按 probe 状态机切换。
  List<int> get _currentIdentityPayload {
    if (!_rebooted) return preRebootPayload;
    return _probeCount <= rebootDelayProbes
        ? preRebootPayload
        : postRebootPayload;
  }

  /// fake 版 ota_sd_inspect_header（RC3-03⑤）：对齐真值 ota_sd.c 检查
  /// 链与 ota_ble_session.c status_for_inspect_error 映射。返回 null
  /// 表示通过，否则返回 ACK status 码。
  int? fakeInspectEtuHeader(Uint8List etu, int totalLen) {
    final device = OtaInfoPayload.parse(_currentIdentityPayload);
    int le16(int off) => etu[off] | (etu[off + 1] << 8);

    int le32(int off) =>
        etu[off] |
        (etu[off + 1] << 8) |
        (etu[off + 2] << 16) |
        (etu[off + 3] << 24);

    // magic/header_len/header_crc/flags/algorithm/key → ERR_HDR(0x08)。
    if (etu[0] != 0x45 || etu[1] != 0x54 || etu[2] != 0x55 || etu[3] != 0x31) {
      return OtaBleCodec.statusErrHdr;
    }
    if (le16(4) != 64) return OtaBleCodec.statusErrHdr;
    if (crc32Of(etu.sublist(0, 60)) != le32(60)) {
      return OtaBleCodec.statusErrHdr;
    }
    final flags = le16(6);
    if (flags != 0x000B && flags != 0x0007) return OtaBleCodec.statusErrHdr;
    if (le32(8) != 1) return OtaBleCodec.statusErrHdr; // algorithm v1
    if (le32(12) != 1) return OtaBleCodec.statusErrHdr; // key v1
    // 设备匹配链：hardware_rev/layout_id/min_boot/target_vcode。
    if (le16(48) != device.hardwareRevision) {
      return OtaBleCodec.statusErrHwRev;
    }
    if (etu[50] != device.layoutId) return OtaBleCodec.statusErrLayout;
    if (etu[51] > device.bootVersion) return OtaBleCodec.statusErrBootVer;
    if (le32(40) <= device.currentVersionCode) {
      return OtaBleCodec.statusErrVersion;
    }
    final payloadLen = le32(32);
    if (flags == 0x000B) {
      // full（真值 ota_sd.c:316-328）：base_vcode=0 且 base_sha8 全零，
      // 否则 ERR_BASE；payload_len==0 属长度域，真值返回
      // OTA_SD_ERR_PACKAGE_LENGTH → ERR_LEN，不是 ERR_BASE。
      if (le32(44) != 0 || le32(52) != 0 || le32(56) != 0) {
        return OtaBleCodec.statusErrBase;
      }
      if (payloadLen == 0) return OtaBleCodec.statusErrLen;
    } else {
      // patch（真值 ota_sd.c:329-341）：base_vcode 必须等于设备当前
      // 版本，base_sha8 必须等于设备 image_sha256 前 8B（真值链
      // HAL_Bluetooth.cpp:94 → ota_sd_device_t.base_image_sha8）；
      // payload_len 必须严格大于 patch 内层头 40B。旧 fake 完全没有
      // patch 分支，任何 base 域都会被放行。
      if (le32(44) != device.currentVersionCode) {
        return OtaBleCodec.statusErrBase;
      }
      for (var i = 0; i < 8; i++) {
        if (etu[52 + i] != device.imageSha256[i]) {
          return OtaBleCodec.statusErrBase;
        }
      }
      if (payloadLen <= 40) return OtaBleCodec.statusErrLen;
    }
    // package_len 恒 64+payload_len 且 payload_len <= 0x180000-64。
    if (payloadLen > 0x180000 - 64 || 64 + payloadLen != totalLen) {
      return OtaBleCodec.statusErrLen;
    }
    return null;
  }

  // ---- 测试注入：DATA ACK 挂起闸门 ----
  /// 非 null 且未完成时，DATA ACK 不发送（帧照常处理落盘），挂起在
  /// _gatedAcks；[releaseDataGate] 后按序补发。
  Completer<void>? dataGate;
  /// entered barrier：第一份 ACK 已挂起（测试据此确认 transfer 在途）。
  final Completer<void> dataGated = Completer<void>();
  final _gatedAcks = <void Function()>[];
  /// MTU 注入（RC3-05⑤）：默认 247；小 MTU 用例测 cancelUpgrade 与
  /// 分片写的交错。注意语义对齐真值 requestOtaMtu：返回值就是写净荷
  /// 上限（真值=协商 MTU-3、最低 20），注入 20 等价 ATT MTU 23。
  int otaMtu = 247;

  /// 分片写延迟（RC3-05⑤）：每笔 writeOtaCharacteristic 完成前等待
  /// 该时长，模拟慢速 BLE 写通道；配合小 [otaMtu] 构造「取消发起时
  /// DATA 帧正处于多片写在途」的真实交错窗口。
  Duration? writeChunkDelay;

  // ---- 测试注入：后台恢复复核与取消窗口（RC3-04⑦/08⑦）----
  /// 链路代次注入（RC3-08⑦ 一级复核）：resumeFromBackground 经
  /// BluetoothService.otaLinkGeneration 读取当前代次，fake 覆写为可变
  /// 字段，测试在传输在途后改值模拟「后台期间断开重连」。
  int linkGeneration = 0;

  /// findExact 调用观测计数：断言二级复核是否真的执行了重新发现
  /// （一级复核失败时不得触发），与 getInfoCalls 配对使用。
  int discoverCalls = 0;

  /// 重新发现应答队列（RC3-08⑦ 二级复核）：非空时
  /// [findExactOtaCharacteristicsByAddress] 按调用顺序弹出（元素 null
  /// 表示该次发现失败返回 null），弹尽后回落默认特征表——绑定与复核
  /// 两次调用可分别注入不同结果。
  final List<Map<String, String>?> discoverReplies = [];

  /// 重新发现闸门（RC3-04⑦ 迟到发布）：非 null 且未完成时，
  /// findExact 在返回前挂起，[rediscoverEntered] 完成；用于把
  /// resumeFromBackground 的复核停在中途，构造「复核未决时用户取消」
  /// 的真实交错。
  Completer<void>? rediscoverGate;
  final Completer<void> rediscoverEntered = Completer<void>();

  /// GET_INFO 应答身份覆写（RC3-08⑦ 三级复核 / RC3-12⑦）：非 null 时
  /// GET_INFO 恒回该 payload（如另一台硬件的身份），模拟后台期间设备
  /// 被更换或重读到不同身份。
  List<int>? infoOverride;

  /// GET_INFO 观测计数（不分重启前后）：断言三级复核确实发了 INFO，
  /// 而不是在更早层级就返回了。
  int getInfoCalls = 0;

  /// ABORT 物理写闸门（RC3-04⑦）：非 null 且未完成时，ABORT 帧的
  /// writeOtaCharacteristic 在送达 fake 前挂起，[abortWriteEntered]
  /// 完成。MTU 247 下 ABORT 帧（10B）单片送达，chunk 头 3 字节即
  /// sync0/sync1/cmdAbort，判定可靠。用于把 cancelUpgrade 停在
  /// `await transport.abortBestEffort()` 处，构造「ABORT 在途期间新
  /// owner 进出」的取消窗口。
  Completer<void>? abortWriteGate;
  final Completer<void> abortWriteEntered = Completer<void>();

  // ---- 观测 ----
  int beginCalls = 0;
  int endCalls = 0;
  int abortCalls = 0;
  final dataOffsets = <int>[];
  /// 每帧 DATA 的判定结果（判定时刻记录，不受 ACK 闸门延迟影响）：
  /// RC3-03 段判据模型测试的观测点。
  final dataAckStatuses = <int>[];
  /// BEGIN ACK 的 status 序列（观测点，同上）。
  final beginAckStatuses = <int>[];
  Uint8List? beginShaBytes;
  Uint8List? endShaBytes;

  // ---- BLE 公开方法覆写（OTA 专用链路）----

  @override
  Future<bool> connectOtaDeviceByAddress(String deviceAddress) async => true;

  @override
  Future<void> disconnectOtaDeviceByAddress(String deviceAddress) async {}

  @override
  int otaLinkGeneration(String deviceAddress) => linkGeneration;

  @override
  Future<Map<String, String>?> findExactOtaCharacteristicsByAddress(
    String deviceAddress, {
    String serviceUuid = 'fff0',
    String writeCharUuid = 'fff2',
    String notifyCharUuid = 'fff1',
  }) async {
    discoverCalls++;
    // 复核闸门（RC3-04⑦）：绑定调用（startOtaUpgrade/readDeviceInfo）
    // 不设闸，测试只在传输在途后设闸，挂起的是 resume 的重新发现。
    final gate = rediscoverGate;
    if (gate != null && !gate.isCompleted) {
      if (!rediscoverEntered.isCompleted) rediscoverEntered.complete();
      await gate.future;
    }
    if (discoverReplies.isNotEmpty) {
      final reply = discoverReplies.removeAt(0);
      return reply == null ? null : Map<String, String>.of(reply);
    }
    return {
      'serviceId': 'fff0',
      'writeCharId': 'fff2',
      'notifyCharId': 'fff1',
      'writeMode': 'with',
    };
  }

  @override
  Future<int> requestOtaMtu(String deviceAddress, {int requested = 247}) async {
    return otaMtu;
  }

  @override
  Future<Stream<List<int>>?> subscribeOtaNotifyByAddress(
    String deviceAddress,
    String serviceId,
    String characteristicId,
  ) async {
    return _notifyController.stream;
  }

  @override
  Future<void> writeOtaCharacteristicByAddress(
    String deviceAddress,
    String serviceId,
    String characteristicId,
    List<int> data, {
    bool writeWithResponse = false,
  }) async {
    final delay = writeChunkDelay;
    if (delay != null) {
      // 慢速写：延迟期间数据未入 _feed——调用方（transport 的逐片
      // await 写序列）在写完成前不会发下一片，构造真实分片在途。
      await Future<void>.delayed(delay);
    }
    // ABORT 物理写闸门（RC3-04⑦）：cancelUpgrade 停在
    // `await transport.abortBestEffort()` 时，ABORT 帧正处于本写调用
    // 在途未送达——闸住此处的就是那个窗口。
    if (data.length >= 3 &&
        data[0] == OtaBleCodec.frameSync0 &&
        data[1] == OtaBleCodec.frameSync1 &&
        data[2] == OtaBleCodec.cmdAbort) {
      final gate = abortWriteGate;
      if (gate != null && !gate.isCompleted) {
        if (!abortWriteEntered.isCompleted) abortWriteEntered.complete();
        await gate.future;
      }
    }
    _feed(data);
  }

  // ---- 帧分片重组与分发（跨 chunk 帧重组，真值 MCU 同款）----

  final _pending = <int>[];

  void _feed(List<int> chunk) {
    _pending.addAll(chunk);
    while (true) {
      if (_pending.length <
          OtaBleCodec.frameHeaderSize + OtaBleCodec.frameCrcSize) {
        return;
      }
      if (_pending[0] != OtaBleCodec.frameSync0 ||
          _pending[1] != OtaBleCodec.frameSync1) {
        _pending.removeAt(0);
        continue;
      }
      final len = _pending[6] | (_pending[7] << 8);
      final frameEnd =
          OtaBleCodec.frameHeaderSize + len + OtaBleCodec.frameCrcSize;
      if (_pending.length < frameEnd) return;
      final frame = Uint8List.fromList(_pending.sublist(0, frameEnd));
      _pending.removeRange(0, frameEnd);
      final f = OtaBleCodec.decodeFrame(frame);
      switch (f.cmd) {
        case OtaBleCodec.cmdGetInfo:
          _onGetInfo(f);
          break;
        case OtaBleCodec.cmdBegin:
          _onBegin(f);
          break;
        case OtaBleCodec.cmdData:
          _onData(f);
          break;
        case OtaBleCodec.cmdEnd:
          _onEnd(f);
          break;
        case OtaBleCodec.cmdAbort:
          _onAbort(f);
          break;
        default:
          break;
      }
    }
  }

  void _send(int cmd, int session, int seq, List<int> payload) {
    if (cmd == OtaBleCodec.rspAckBegin && payload.isNotEmpty) {
      beginAckStatuses.add(payload[0]);
    }
    _notifyController.add(OtaBleCodec.encodeCommand(
      cmd: cmd,
      session: session,
      seq: seq,
      payload: payload,
    ));
  }

  // ---- 命令处理（真值语义）----

  void _onGetInfo(OtaBleFrame f) {
    // INFO 帧：session=0、seq 回显请求 seq（§5.6）。
    // 重启状态机：END OK 前恒旧身份；之后前 rebootDelayProbes 次
    // 探测仍旧身份（MCU 重启中），再报新身份。
    getInfoCalls++;
    final List<int> payload;
    final override = infoOverride;
    if (override != null) {
      payload = override;
    } else if (!_rebooted) {
      payload = preRebootPayload;
    } else {
      _probeCount++;
      payload =
          _probeCount <= rebootDelayProbes ? preRebootPayload : postRebootPayload;
    }
    _send(OtaBleCodec.rspInfo, 0, f.seq, payload);
  }

  void _onBegin(OtaBleFrame f) {
    beginCalls++;
    final totalLen = f.payload[1] |
        (f.payload[2] << 8) |
        (f.payload[3] << 16) |
        (f.payload[4] << 24);
    final sha = Uint8List.fromList(f.payload.sublist(5, 37));
    beginShaBytes = sha;
    final shaMatch = _beginSha.length == 32 && _bytesEqual(_beginSha, sha);
    // ---- BEGIN 门禁（RC3-03⑤，真值 session_handle_begin :331-368）----
    // proto_ver/total_len/inspect 三道门禁 session=0 拒绝且不动现有
    // 状态。门禁未接入前，恢复正例读到 vcode=20900 后再装 20900 仍
    // "成功"，与 MCU 真值相悖（target_vcode 门禁必拒）。
    if (f.payload[0] != 1) {
      _send(OtaBleCodec.rspAckBegin, 0, f.seq,
          packBeginAck(OtaBleCodec.statusErrProto, 0, 0, 0));
      return;
    }
    if (totalLen == 0 || totalLen > 0x180000) {
      _send(OtaBleCodec.rspAckBegin, 0, f.seq,
          packBeginAck(OtaBleCodec.statusErrLen, 0, 0, 0));
      return;
    }
    final inspectStatus = fakeInspectEtuHeader(
        Uint8List.fromList(f.payload.sublist(37, 101)), totalLen);
    if (inspectStatus != null) {
      _send(OtaBleCodec.rspAckBegin, 0, f.seq,
          packBeginAck(inspectStatus, 0, 0, 0));
      return;
    }
    if (_state == _active && _totalLen == totalLen && shaMatch) {
      // 重复 BEGIN（同 sha 同包长）：幂等回当前进度，不重置
      // expected_seq（真值 :377-386）。
      _send(
        OtaBleCodec.rspAckBegin,
        _sessionId,
        f.seq,
        packBeginAck(
            OtaBleCodec.statusOk, _sessionId, _stagedDurable, _stagedBitmap),
      );
      return;
    }
    // 新会话：不同包先 teardown（真值 :390-393）。
    if (_state == _active) {
      _teardown();
    }
    // 不同 sha：整页重建，清旧包 journal（真值 erase staging，
    // RC3-03⑤——缺此分支时新包会从旧包 durable 续传，喂错字节）。
    if (_stagedBytes.isNotEmpty && !shaMatch) {
      _eraseStaged();
    }
    _beginSha = sha;
    _totalLen = totalLen;
    // 流式 SHA 重建（真值 :449-456）：sha_init + journal durable 前缀
    // 回填（session_digest_resume_prefix 从 staging 读回 [0, durable)）。
    _shaBytes..clear()..addAll(_stagedBytes);
    _sessionId = _nextSessionId;
    _nextSessionId = (_nextSessionId + 1) & 0xFF;
    if (_nextSessionId == 0) _nextSessionId = 1;
    _expectedSeq = (f.seq + 1) & 0xFFFF;
    _state = _active;
    _send(
      OtaBleCodec.rspAckBegin,
      _sessionId,
      f.seq,
      packBeginAck(
          OtaBleCodec.statusOk, _sessionId, _stagedDurable, _stagedBitmap),
    );
  }

  void _onData(OtaBleFrame f) {
    final off = f.payload[0] |
        (f.payload[1] << 8) |
        (f.payload[2] << 16) |
        (f.payload[3] << 24);
    dataOffsets.add(off);
    if (_state != _active) {
      // teardown 后（如 ABORT 已处理）：session=0 的 ERR_STATE NAK。
      _emitDataAck(OtaBleCodec.statusErrState, f);
      return;
    }
    if (f.session != _sessionId) {
      _emitDataAck(OtaBleCodec.statusErrSession, f);
      return;
    }
    final delta = OtaBleCodec.seqCompare(f.seq, _expectedSeq);
    if (delta > 0) {
      _emitDataAck(OtaBleCodec.statusErrSeq, f);
      return;
    }
    if (delta < 0) {
      // 重发帧：幂等重发当前 ACK，不重写 staging（真值 :511-518）。
      _emitDataAck(OtaBleCodec.statusOk, f);
      return;
    }
    _expectedSeq = (f.seq + 1) & 0xFFFF;

    // 段校验链（真值 ota_ble_session.c:526-548）：三条独立判据，错误码
    // 互不相同——对齐不符 → ERR_OFFSET；非尾部短段/空段 → ERR_FRAME；
    // 越包尾 → ERR_OFFSET。旧 fake 把三者并成一条 ERR_LEN，既错分类，
    // 又把 transport 的可恢复分支（ERR_FRAME/ERR_SEQ 在
    // _resumeStatuses 里）伪装成不可恢复的终止错误。
    final content = Uint8List.fromList(f.payload.sublist(4));
    if (off % OtaBleCodec.dataSegmentSize != 0) {
      _emitDataAck(OtaBleCodec.statusErrOffset, f);
      return;
    }
    if (content.length != OtaBleCodec.dataSegmentSize &&
        off + content.length != _totalLen) {
      _emitDataAck(OtaBleCodec.statusErrFrame, f);
      return;
    }
    if (off >= _totalLen || off + content.length > _totalLen) {
      _emitDataAck(OtaBleCodec.statusErrOffset, f);
      return;
    }
    if (off < _stagedDurable) {
      // 已提交 offset 的重复 DATA：幂等 OK，不重写 staging、不重复喂
      // 摘要（真值 :550-558，RC3-03⑤——缺此分支时重发段会经
      // _segContent 误判 DUPLICATE 或重复喂 SHA，污染内容 oracle）。
      _emitDataAck(OtaBleCodec.statusOk, f);
      return;
    }
    // staging 层长度判据（真值 ota_staging_receive :485-493）：
    // expected_len = min(total-off, 128)，不符即 ERR_RANGE → ERR_OFFSET。
    // 会话层只挡"非尾部短段"，尾部段还要在这里钉死精确长度。
    final expectedLen = (_totalLen - off) < OtaBleCodec.dataSegmentSize
        ? (_totalLen - off)
        : OtaBleCodec.dataSegmentSize;
    if (content.length != expectedLen) {
      _emitDataAck(OtaBleCodec.statusErrOffset, f);
      return;
    }
    // 越当前 4KB 窗（RC3-03⑤，真值 ota_staging_receive :499-503）：
    // durable==total 或 off-durable >= 块长 → ERR_RANGE 映射
    // ERR_OFFSET。缺此门禁时 fake 照单接收窗口外段，掩盖 transport
    // 侧窗口纪律的真实性。
    const windowSize =
        OtaBleCodec.segmentsPerBlock * OtaBleCodec.dataSegmentSize;
    if (_stagedDurable == _totalLen || off - _stagedDurable >= windowSize) {
      _emitDataAck(OtaBleCodec.statusErrOffset, f);
      return;
    }
    final staged = _segContent[off];
    if (staged != null) {
      // 位图已置位的同段重发（真值 ota_staging_receive :508-516）：
      // 内容相同 → DUPLICATE 幂等 OK；内容不同 → ERR_DATA，会话层
      // 映射 ABORTED 并 teardown（ota_ble_session.c:585-591）。旧 fake
      // 无条件回 OK，等于把"同 offset 两份不同数据"这类真实损坏
      // 静默吞掉。
      if (!_bytesEqual(staged, content)) {
        _emitDataAck(OtaBleCodec.statusAborted, f);
        _teardown();
        return;
      }
      _emitDataAck(OtaBleCodec.statusOk, f);
      return;
    }
    _segContent[off] = content;
    // 新写入段喂流式 SHA（真值 :571）：以 wire 数据按接收顺序喂，
    // 与 journal 落盘无关（RAM 摘要与 flash 落盘分离，真值同款）。
    _shaBytes.addAll(content);

    // 块收齐提交（真值 :585-598）：先组装块字节（RAM 清空前——journal
    // 提交需要完整块内容），staging durable 前移、位图清零。
    const blockSize =
        OtaBleCodec.segmentsPerBlock * OtaBleCodec.dataSegmentSize;
    final blockStart = (_stagedDurable ~/ blockSize) * blockSize;
    final seg = (off - blockStart) ~/ OtaBleCodec.dataSegmentSize;
    final blockEnd =
        (blockStart + blockSize) > _totalLen ? _totalLen : blockStart + blockSize;
    final segsInBlock =
        ((blockEnd - blockStart) + OtaBleCodec.dataSegmentSize - 1) ~/
            OtaBleCodec.dataSegmentSize;
    _stagedBitmap |= 1 << seg;
    if (_stagedBitmap == (1 << segsInBlock) - 1) {
      final blockBytes = <int>[];
      for (var s = 0; s < segsInBlock; s++) {
        blockBytes.addAll(_segContent[blockStart + s * OtaBleCodec.dataSegmentSize]!);
      }
      _stagedDurable = blockEnd;
      _stagedBitmap = 0;
      _segContent.removeWhere((k, _) => k >= blockStart && k < blockEnd);
      // journal 追加块字节（流式 SHA 的 resume 前缀数据源）。
      _stagedBytes = Uint8List.fromList([..._stagedBytes, ...blockBytes]);
    }
    _emitDataAck(OtaBleCodec.statusOk, f);
  }

  void _onEnd(OtaBleFrame f) {
    endCalls++;
    endShaBytes = Uint8List.fromList(f.payload);
    if (_state != _active || f.session != _sessionId) {
      _send(OtaBleCodec.rspAckEnd, f.session, f.seq,
          packAck(OtaBleCodec.statusErrState, _stagedDurable, 0));
      return;
    }
    final delta = OtaBleCodec.seqCompare(f.seq, _expectedSeq);
    if (delta > 0) {
      _send(OtaBleCodec.rspAckEnd, _sessionId, f.seq,
          packAck(OtaBleCodec.statusErrSeq, _stagedDurable, 0));
      return;
    }
    if (delta < 0) {
      // END 重发（seq 落后）：幂等回 OK（真值 :636-642）。
      _send(OtaBleCodec.rspAckEnd, _sessionId, f.seq,
          packAck(OtaBleCodec.statusOk, _stagedDurable, 0));
      return;
    }
    _expectedSeq = (f.seq + 1) & 0xFFFF;

    // sha 复述 + durable==total 校验（真值 :646-662）。
    final shaOk = f.payload.length == 32 && _bytesEqual(f.payload, _beginSha);
    if (!shaOk) {
      _send(OtaBleCodec.rspAckEnd, _sessionId, f.seq,
          packAck(OtaBleCodec.statusErrSha, _stagedDurable, 0));
      _eraseStaged();
      _teardown();
      return;
    }
    if (_stagedDurable != _totalLen) {
      _send(OtaBleCodec.rspAckEnd, _sessionId, f.seq,
          packAck(OtaBleCodec.statusErrState, _stagedDurable, 0));
      _teardown();
      return;
    }
    // 内容级流式摘要 final（真值 :664-668）：sha256(journal durable
    // 前缀 + 顺序新收段) 必须等于 BEGIN 携带的 package_sha256——
    // 复述一致但内容不符（错字节/漏段）同样 ERR_SHA（RC3-03）。
    final digest = sha256.convert(_shaBytes);
    if (!_bytesEqual(digest.bytes, _beginSha)) {
      _send(OtaBleCodec.rspAckEnd, _sessionId, f.seq,
          packAck(OtaBleCodec.statusErrSha, _stagedDurable, 0));
      _eraseStaged();
      _teardown();
      return;
    }
    _send(OtaBleCodec.rspAckEnd, _sessionId, f.seq,
        packAck(OtaBleCodec.statusOk, _stagedDurable, 0));
    _teardown();
    // END OK：MCU 校验整包通过，切新固件重启。
    _rebooted = true;
  }

  void _onAbort(OtaBleFrame f) {
    abortCalls++;
    if (_state == _active && f.session != _sessionId) {
      // session 不符：不动 durable 状态（真值 :695-702）。
      _send(OtaBleCodec.rspAckAbort, f.session, f.seq,
          packAck(OtaBleCodec.statusErrSession, _stagedDurable, 0));
      return;
    }
    // session 匹配或非 ACTIVE：ACK ABORTED + teardown（durable 保留）。
    _send(OtaBleCodec.rspAckAbort, _sessionId, f.seq,
        packAck(OtaBleCodec.statusAborted, _stagedDurable, 0));
    _teardown();
  }

  /// DATA ACK 发射（应答时刻组装 payload 快照，RC3-03；受 dataGate
  /// 挂起控制：帧处理照常，仅 ACK 发送挂起）。
  void _emitDataAck(int status, OtaBleFrame f) {
    dataAckStatuses.add(status);
    final payload = packAck(
        status, _stagedDurable, _state == _active ? _stagedBitmap : 0);
    final session = _sessionId;
    void emit() {
      _send(OtaBleCodec.rspAckData, session, f.seq, payload);
    }

    final gate = dataGate;
    if (gate != null && !gate.isCompleted) {
      if (!dataGated.isCompleted) dataGated.complete();
      _gatedAcks.add(emit);
      return;
    }
    emit();
  }

  /// 释放 ACK 闸门：挂起的 ACK 按接收顺序补发。
  void releaseDataGate() {
    dataGate = null;
    final pending = List<void Function()>.of(_gatedAcks);
    _gatedAcks.clear();
    for (final emit in pending) {
      emit();
    }
  }

  /// teardown（真值 ota_staging.c）：RAM 层（段内容 + 会话 SHA 流）
  /// 清空，journal durable 与字节保留（重新 BEGIN 同 sha 时以前缀
  /// 重建 SHA resume）。
  void _teardown() {
    _state = _idle;
    _sessionId = 0;
    _stagedBitmap = 0;
    _segContent.clear();
    _shaBytes.clear();
  }

  /// 整页擦除（END sha 不符时）：journal durable 与字节一并归零。
  void _eraseStaged() {
    _stagedDurable = 0;
    _stagedBitmap = 0;
    _segContent.clear();
    _shaBytes.clear();
    _stagedBytes = Uint8List(0);
  }
}
