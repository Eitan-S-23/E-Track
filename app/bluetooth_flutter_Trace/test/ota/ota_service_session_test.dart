import 'dart:async';
import 'dart:io';
import 'dart:typed_data';

import 'package:crypto/crypto.dart';
import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:get/get.dart';

import 'package:ble_monitor/ota/ota_ble_codec.dart';
import 'package:ble_monitor/ota/ota_device_info.dart';
import 'package:ble_monitor/services/app_update_service.dart';
import 'package:ble_monitor/services/bluetooth_service.dart';
import 'package:ble_monitor/services/ota_service.dart';

/// OtaService 会话级测试（RC2 批次补齐；RC3-02 重构测试可信度）：
/// - 入口互斥（挂起下载期间 checkFirmwareUpdate 直接返回，不发请求）；
/// - 取消两段式：注册前取消（请求未发出，计数断言）与 adapter 已进入
///   后取消（entered barrier，cancelFuture 打断在途请求）分开验证；
/// - 取消对已校验完成包的清理（keepPackage 语义，RC3-05①）；
/// - 刷新时取消（URL_EXPIRED → 重新 latest 挂起时取消，旧清单不发布）；
/// - URL_EXPIRED 自动刷新清单并重下（一次，不解除忙锁）；
/// - BACKEND_UNAVAILABLE 三次尝试耗尽 → retryableLater 终态并清资产。
///
/// 测试可信度（RC3-02）：不用 runZonedGuarded 吞异步异常——UI 通知
/// 副作用经构造器注入的 [OtaService.onNotify] 替身（[makeService] 的
/// notifyLog）隔离，Get.snackbar 不被调用；其余任何异步异常都必须
/// 上抛导致测试失败。
///
/// 依赖全部构造器注入：fake BluetoothService（GET_INFO mini 应答）、
/// fake AppUpdateService（固定 appVersionCode）、行为序列 mock Dio
/// （latest/download 各自独立）、临时目录 firmwareDirProvider、
/// latestUriBuilder（绕开 dart-define 环境变量）。
/// 普通测试 + 真实时间（退避真实等待）。
void main() {
  setUp(() {
    Get.testMode = true;
  });

  tearDown(() {
    Get.reset();
  });

  final infoPayload = buildInfoPayload(
    model: DeviceOtaInfo.wireModelETrack,
    hardwareRevision: 3,
    layoutId: 5,
    bootVersion: 2,
    currentVersionCode: 20801,
    imageSha256: List<int>.generate(32, (i) => i * 3),
  );

  /// 资产文件名（ASSET-NAMING：full 必须以 -full.etu 结尾）。
  final pkgName = 'e-track-at32f435-v2.9.0-full.etu';

  Uint8List assetBytes(int size) =>
      Uint8List.fromList(List<int>.generate(size, (i) => (i * 7 + 3) & 0xFF));

  /// latest 响应体：目标 vcode 20900，asset 与 [assetBytes] 匹配。
  /// downloadUrl 必须 https（RC2-11 解析器校验）。
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

  Dio latestDio(List<_LatestBehavior> behaviors) {
    final dio = Dio();
    dio.httpClientAdapter = _LatestMockAdapter(behaviors);
    return dio;
  }

  Dio downloadDio(
    List<_DownloadBehavior> behaviors, {
    Completer<void>? entered,
  }) {
    final dio = Dio();
    dio.httpClientAdapter = _DownloadMockAdapter(behaviors, entered: entered);
    return dio;
  }

  OtaService makeService({
    required _FakeBle ble,
    required Dio latest,
    required Dio download,
    required Directory firmwareDir,
    List<String>? notifyLog,
  }) {
    // RC3-02⑤：默认值不得用 const []——记录替身恒 add，const 列表首条
    // 通知即抛 UnsupportedError（忙锁提示等轻量通知也会触发）。默认
    // 改为可增长列表；调用方不传时同样可安全收集。
    final log = notifyLog ?? <String>[];
    final service = OtaService(
      bluetoothService: ble,
      dio: latest,
      downloadDio: download,
      firmwareDirProvider: () async => firmwareDir,
      latestUriBuilder: (info, appVersionCode, channel) =>
          Uri.parse('http://localhost:9/api/firmware/latest'),
      // onNotify 替身（RC3-02）：恒安装记录替身——不传 notifyLog 也不得
      // 回退 null（null 走真实 Get.snackbar，在无 overlay 上下文的测试
      // 宿主里异步抛错）；通知进 log 供断言。
      onNotify: (title, message) => log.add('$title: $message'),
    );
    Get.put<OtaService>(service);
    return service;
  }

  Directory tempFirmwareDir() {
    final tempDir =
        Directory.systemTemp.createTempSync('ota_service_session_test');
    addTearDown(() {
      if (tempDir.existsSync()) tempDir.deleteSync(recursive: true);
    });
    return tempDir;
  }

  test('双击防重入：挂起下载期间 checkFirmwareUpdate 不发新请求', () async {
    final tempDir = tempFirmwareDir();
    final bytes = assetBytes(1024);
    final ble = _FakeBle(infoPayload);
    final latest = latestDio([
      _LatestBehavior.ok(latestBody(bytes)),
    ]);
    // 下载请求挂起：不返回响应直到测试释放。
    final gate = Completer<void>();
    final download = downloadDio([
      _DownloadBehavior.gated(gate, bytes),
    ]);
    final service = makeService(
      ble: ble,
      latest: latest,
      download: download,
      firmwareDir: tempDir,
    );
    Get.put<AppUpdateService>(_FakeAppUpdateService());

    expect(await service.readDeviceInfo('AA:BB'), isNotNull);
    expect(await service.checkFirmwareUpdate(), isNotNull);
    final latestAdapter = latest.httpClientAdapter as _LatestMockAdapter;

    // 挂起下载（入口同步段已置忙锁）。
    final downloadFuture = service.downloadFirmware();
    expect(service.isUpgrading, isTrue);

    // 防重入：下载进行中第二次 check 被忙锁直接拒绝，latest 计数不变。
    final beforeRequests = latestAdapter.requestCount;
    final second = await service.checkFirmwareUpdate();
    expect(second, isNull);
    expect(latestAdapter.requestCount, beforeRequests,
        reason: '忙锁拒绝不得发出新的 latest 请求');

    // 释放挂起下载并收尾。
    gate.complete();
    expect(await downloadFuture, isTrue);
  });

  test('注册前取消：请求未发出（计数断言），取消终态且可重新下载', () async {
    final tempDir = tempFirmwareDir();
    final bytes = assetBytes(1024);
    final ble = _FakeBle(infoPayload);
    final latest = latestDio([
      _LatestBehavior.ok(latestBody(bytes)),
    ]);
    // 只放一个 ok 行为：注册前取消必须一个请求都不发；若实现缺陷
    // 发出了请求，requestCount 断言与行为耗尽会同时暴露。
    final download = downloadDio([
      _DownloadBehavior.ok(bytes),
    ]);
    final service = makeService(
      ble: ble,
      latest: latest,
      download: download,
      firmwareDir: tempDir,
    );
    Get.put<AppUpdateService>(_FakeAppUpdateService());

    await service.readDeviceInfo('AA:BB');
    await service.checkFirmwareUpdate();

    // 注册前取消：downloadFirmware 的同步段已取得 owner 并锚定取消
    // 代次，body 尚未执行；紧随的 cancelUpgrade 在 body 启动前递增
    // 代次（事件循环保证：同步代码先于 body 的 microtask 执行）。
    final downloadFuture = service.downloadFirmware();
    await service.cancelUpgrade();

    expect(await downloadFuture, isFalse);
    expect(service.phase, OtaPhase.cancelled);
    final downloadAdapter = download.httpClientAdapter as _DownloadMockAdapter;
    expect(downloadAdapter.requestCount, 0,
        reason: '注册前取消不得把请求分发到 adapter');
    // 未写任何 partial/sidecar。
    final partFile = File('${tempDir.path}/$pkgName.part');
    expect(partFile.existsSync(), isFalse);
    expect(File('${partFile.path}.json').existsSync(), isFalse);

    // 取消后入口不闭锁：可重新下载成功（唯一 ok 行为被此轮消费）。
    expect(await service.downloadFirmware(), isTrue);
    expect(downloadAdapter.requestCount, 1);
    final pkg = service.downloadedFirmwareFile;
    expect(pkg, isNotNull);
    expect(await pkg!.length(), bytes.length);
  });

  test('在途取消：adapter 已进入（entered barrier）后取消 → CANCELLED',
      () async {
    final tempDir = tempFirmwareDir();
    final bytes = assetBytes(1024);
    final ble = _FakeBle(infoPayload);
    final latest = latestDio([
      _LatestBehavior.ok(latestBody(bytes)),
    ]);
    // 第一次下载挂起（被取消打断）；第二次正常完成。
    final gate = Completer<void>();
    // entered barrier（RC3-02）：等 adapter 真正进入挂起行为后才取消，
    // 消除「取消早于请求分发、gated 行为未消费」的时序歧义。
    final entered = Completer<void>();
    final download = downloadDio([
      _DownloadBehavior.gated(gate, bytes),
      _DownloadBehavior.ok(bytes),
    ], entered: entered);
    final service = makeService(
      ble: ble,
      latest: latest,
      download: download,
      firmwareDir: tempDir,
    );
    Get.put<AppUpdateService>(_FakeAppUpdateService());

    await service.readDeviceInfo('AA:BB');
    await service.checkFirmwareUpdate();

    final downloadFuture = service.downloadFirmware();
    expect(service.isUpgrading, isTrue);
    // 等 adapter 进入 gated 行为（请求已分发、在途）。
    await entered.future;

    // 取消：在途请求被 CancelToken 打断。
    await service.cancelUpgrade();
    expect(await downloadFuture, isFalse);
    expect(service.phase, OtaPhase.cancelled);
    final downloadAdapter = download.httpClientAdapter as _DownloadMockAdapter;
    // gated 行为已消费恰好一次；下一行为留待重下。
    expect(downloadAdapter.requestCount, 1);
    // 挂起发生在响应前，未写任何 partial/sidecar（partial 恒删语义下
    // 无残留）。
    final partFile = File('${tempDir.path}/$pkgName.part');
    expect(partFile.existsSync(), isFalse);
    expect(File('${partFile.path}.json').existsSync(), isFalse);

    // 取消后入口不闭锁：可重新下载成功（消费第二个行为，不再命中
    // 已消费的 gate）。
    expect(await service.downloadFirmware(), isTrue);
    expect(downloadAdapter.requestCount, 2);
    final pkg = service.downloadedFirmwareFile;
    expect(pkg, isNotNull);
    expect(await pkg!.length(), bytes.length);
    expect(pkg.path.endsWith(pkgName), isTrue);
    expect(await File('${pkg.path}.part').existsSync(), isFalse);
  });

  test('取消清理已校验完成包：keepPackage=false 删文件，true 保留', () async {
    final tempDir = tempFirmwareDir();
    final bytes = assetBytes(1024);
    final ble = _FakeBle(infoPayload);
    final latest = latestDio([
      _LatestBehavior.ok(latestBody(bytes)),
      _LatestBehavior.ok(latestBody(bytes)),
    ]);
    final download = downloadDio([
      _DownloadBehavior.ok(bytes),
      _DownloadBehavior.ok(bytes),
    ]);
    final service = makeService(
      ble: ble,
      latest: latest,
      download: download,
      firmwareDir: tempDir,
    );
    Get.put<AppUpdateService>(_FakeAppUpdateService());

    await service.readDeviceInfo('AA:BB');
    await service.checkFirmwareUpdate();

    // 第一轮：下载成功后取消（keepPackage=false）→ 完成包被删除。
    expect(await service.downloadFirmware(), isTrue);
    final pkg1 = service.downloadedFirmwareFile;
    expect(pkg1, isNotNull);
    expect(await pkg1!.exists(), isTrue);
    await service.cancelUpgrade(keepPackage: false);
    expect(service.phase, OtaPhase.cancelled);
    expect(await pkg1.exists(), isFalse, reason: 'keepPackage=false 必须删除已校验完成包');
    expect(service.downloadedFirmwareFile, isNull);

    // 第二轮：下载成功后取消（keepPackage=true）→ 已校验完成包保留
    // （partial 仍恒删，本用例无 partial）。
    expect(await service.checkFirmwareUpdate(), isNotNull);
    expect(await service.downloadFirmware(), isTrue);
    final pkg2 = service.downloadedFirmwareFile;
    expect(pkg2, isNotNull);
    await service.cancelUpgrade(keepPackage: true);
    expect(service.phase, OtaPhase.cancelled);
    expect(await pkg2!.exists(), isTrue,
        reason: 'keepPackage=true 必须保留已校验完成包');
  });

  test('刷新时取消：URL_EXPIRED → 重新 latest 在途时取消，旧清单不发布',
      () async {
    final tempDir = tempFirmwareDir();
    final bytes = assetBytes(1024);
    final ble = _FakeBle(infoPayload);
    // latest：第一次（初检）正常；第二次（刷新）挂起（被取消打断的
    // 在途窗口）。
    final latestGate = Completer<void>();
    final latest = latestDio([
      _LatestBehavior.ok(latestBody(bytes)),
      _LatestBehavior.gated(latestGate),
    ]);
    final download = downloadDio([
      // 第一次下载：401 TOKEN_EXPIRED → URL_EXPIRED（刷新触发器）。
      _DownloadBehavior.status(401,
          body: '{"errorCode":"TOKEN_EXPIRED"}'),
    ]);
    final service = makeService(
      ble: ble,
      latest: latest,
      download: download,
      firmwareDir: tempDir,
    );
    Get.put<AppUpdateService>(_FakeAppUpdateService());

    await service.readDeviceInfo('AA:BB');
    await service.checkFirmwareUpdate();
    final latestAdapter = latest.httpClientAdapter as _LatestMockAdapter;
    expect(latestAdapter.requestCount, 1);

    // 下载 → 401 → 刷新 latest（第二次请求挂起）。
    final downloadFuture = service.downloadFirmware();
    // 等 401 已发生、刷新请求已进入（latest 计数到 2）。
    while (latestAdapter.requestCount < 2) {
      await Future<void>.delayed(const Duration(milliseconds: 5));
    }
    // 刷新在途时取消（RC3-04/RC3-02）：latest 请求已绑定 CancelToken
    // （_getLatestWithRetry），cancelUpgrade 立即中断在途刷新——owner
    // 由此解除阻塞，cancelUpgrade 得以返回；此后 gate.complete() 只是
    // 收尾孤儿 fetch（adapter 层 Future.any 已被 cancelFuture 打断），
    // 不再构成「cancel 等 owner、owner 等 gate、gate 等 cancel 返回」
    // 的死锁环。
    await service.cancelUpgrade();
    // 收尾孤儿 fetch：释放挂起的刷新响应（模拟服务器最终返回；
    // 代次已变，不得发布）。
    latestGate.complete();
    expect(await downloadFuture, isFalse);
    expect(service.phase, OtaPhase.cancelled);
    // 刷新请求确实发出（计数 2），但重下不得发生（下载计数仍为 1）。
    final downloadAdapter =
        download.httpClientAdapter as _DownloadMockAdapter;
    expect(latestAdapter.requestCount, 2);
    expect(downloadAdapter.requestCount, 1);
    // 无 partial 残留。
    final partFile = File('${tempDir.path}/$pkgName.part');
    expect(partFile.existsSync(), isFalse);
  });

  test('URL_EXPIRED 刷新路径：401 TOKEN_EXPIRED → 重新 latest → 重下成功',
      () async {
    final tempDir = tempFirmwareDir();
    final bytes = assetBytes(1024);
    final ble = _FakeBle(infoPayload);
    // latest：第一次（初检）正常 + 第二次（刷新）正常，共 2 次。
    final latest = latestDio([
      _LatestBehavior.ok(latestBody(bytes)),
      _LatestBehavior.ok(latestBody(bytes)),
    ]);
    final download = downloadDio([
      // 第一次下载：401 TOKEN_EXPIRED → URL_EXPIRED（刷新触发器）。
      _DownloadBehavior.status(401,
          body: '{"errorCode":"TOKEN_EXPIRED"}'),
      // 刷新后重下：成功。
      _DownloadBehavior.ok(bytes),
    ]);
    final service = makeService(
      ble: ble,
      latest: latest,
      download: download,
      firmwareDir: tempDir,
    );
    Get.put<AppUpdateService>(_FakeAppUpdateService());

    await service.readDeviceInfo('AA:BB');
    await service.checkFirmwareUpdate();

    expect(await service.downloadFirmware(), isTrue);
    final latestAdapter = latest.httpClientAdapter as _LatestMockAdapter;
    final downloadAdapter =
        download.httpClientAdapter as _DownloadMockAdapter;
    // latest 调 2 次（初检 + 刷新），download 调 2 次（401 + 重下）。
    expect(latestAdapter.requestCount, 2);
    expect(downloadAdapter.requestCount, 2);
    final pkg = service.downloadedFirmwareFile;
    expect(pkg, isNotNull);
    expect(await pkg!.length(), bytes.length);
  });

  test('BACKEND_UNAVAILABLE 三次尝试耗尽 → retryableLater 终态并清资产',
      () async {
    final tempDir = tempFirmwareDir();
    final bytes = assetBytes(1024);
    final ble = _FakeBle(infoPayload);
    // 第一轮 latest 正常（建立资产）；第二轮 check：503 三连（重试耗尽）。
    final latest = latestDio([
      _LatestBehavior.ok(latestBody(bytes)),
      _LatestBehavior.status(503,
          body: '{"errorCode":"BACKEND_UNAVAILABLE","retryAfter":1}'),
      _LatestBehavior.status(503,
          body: '{"errorCode":"BACKEND_UNAVAILABLE","retryAfter":1}'),
      _LatestBehavior.status(503,
          body: '{"errorCode":"BACKEND_UNAVAILABLE","retryAfter":1}'),
    ]);
    final download = downloadDio([]);
    final service = makeService(
      ble: ble,
      latest: latest,
      download: download,
      firmwareDir: tempDir,
    );
    Get.put<AppUpdateService>(_FakeAppUpdateService());

    await service.readDeviceInfo('AA:BB');
    expect(await service.checkFirmwareUpdate(), isNotNull);
    expect(service.latestInfo, isNotNull);

    // 第二次 check：503 → 自动重试 2 次（退避 1s/1s，真实时间）→ 耗尽。
    final latestAdapter = latest.httpClientAdapter as _LatestMockAdapter;
    expect(await service.checkFirmwareUpdate(), isNull);
    // 3 次尝试全部发出（1 初次 + 2 重试）。
    expect(latestAdapter.requestCount, 4);

    final terminal = service.terminalState;
    expect(terminal, isNotNull);
    expect(terminal!.code, 'BACKEND_UNAVAILABLE');
    expect(terminal.retryableLater, isTrue);
    // 资产已清：旧清单可能已过期（RC2-04）。
    expect(service.latestInfo, isNull);
    expect(service.downloadedFirmwareFile, isNull);
    // retryableLater 不闭锁入口。
    expect(service.isUpgrading, isFalse);
  }, timeout: const Timeout(Duration(seconds: 20)));
}

/// fake BLE：GET_INFO mini 应答；发现/订阅/MTU 返回固定合法值。
class _FakeBle extends BluetoothService {
  _FakeBle(this.infoPayload);

  final List<int> infoPayload;

  final _notifyController = StreamController<List<int>>.broadcast();

  @override
  void onInit() {
    super.onInit();
    // 空实现：阻止真实 initBluetooth（平台通道在测试宿主不可用）。
    // 仅经构造器注入使用，不经 Get.put 触发。
  }

  @override
  Future<Map<String, String>?> findExactOtaCharacteristicsByAddress(
    String deviceAddress, {
    String serviceUuid = 'fff0',
    String writeCharUuid = 'fff2',
    String notifyCharUuid = 'fff1',
  }) async {
    return {
      'serviceId': 'fff0',
      'writeCharId': 'fff2',
      'notifyCharId': 'fff1',
      'writeMode': 'with',
    };
  }

  @override
  Future<int> requestOtaMtu(String deviceAddress, {int requested = 247}) async {
    return 247;
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
    // 只应答 GET_INFO：INFO 帧 session=0、seq 回显请求 seq（§5.6）。
    final f = OtaBleCodec.decodeFrame(data);
    if (f.cmd == OtaBleCodec.cmdGetInfo) {
      _notifyController.add(OtaBleCodec.encodeCommand(
        cmd: OtaBleCodec.rspInfo,
        session: 0,
        seq: f.seq,
        payload: infoPayload,
      ));
    }
  }
}

/// fake AppUpdateService：固定 appVersionCode，跳过平台通道。
class _FakeAppUpdateService extends AppUpdateService {
  @override
  Future<int> getLocalAppVersionCode() async => 42;
}

/// latest 行为（一次请求消费一个）。
class _LatestBehavior {
  _LatestBehavior._(this.status, this.body, this.gate);

  factory _LatestBehavior.ok(String body) => _LatestBehavior._(200, body, null);
  factory _LatestBehavior.status(int status, {String body = ''}) =>
      _LatestBehavior._(status, body, null);

  /// 挂起直到 gate 完成（刷新时取消用例的在途窗口）。
  factory _LatestBehavior.gated(Completer<void> gate) =>
      _LatestBehavior._(200, '', gate);

  final int status;
  final String body;
  final Completer<void>? gate;
}

class _LatestMockAdapter implements HttpClientAdapter {
  _LatestMockAdapter(this.behaviors);

  final List<_LatestBehavior> behaviors;
  int requestCount = 0;

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    if (requestCount >= behaviors.length) {
      throw StateError('latest 请求数超出预期: ${requestCount + 1}');
    }
    final behavior = behaviors[requestCount];
    requestCount++;
    final gate = behavior.gate;
    if (gate != null) {
      // latest 请求绑定 CancelToken（RC3-04 修复后）：取消经 dio 的
      // whenCancel 传入 cancelFuture，与 gate 先到者胜——取消打断在途
      // 刷新（dio 层已让调用方收到 requestCancelled，fetch 返回值被
      // 丢弃）；gate 释放则正常返回。必须返回普通响应而非抛错——
      // 被取消的 operation 不再消费 fetch 结果，孤儿异常会变成
      // uncaught error。
      if (cancelFuture != null) {
        await Future.any([gate.future, cancelFuture]);
      } else {
        await gate.future;
      }
    }
    return ResponseBody.fromString(behavior.body, behavior.status, headers: {
      'content-type': ['application/json'],
    });
  }

  @override
  void close({bool force = false}) {}
}

/// download 行为（一次请求消费一个）。
class _DownloadBehavior {
  _DownloadBehavior._(
    this.status, {
    this.body,
    this.bytes,
    this.gate,
  });

  /// 正常 200 完整 body（Content-Length 一致）。
  factory _DownloadBehavior.ok(Uint8List bytes) =>
      _DownloadBehavior._(200, bytes: bytes);

  /// 直接返回状态码（401 分流用，json 错误体）。
  factory _DownloadBehavior.status(int status, {String body = ''}) =>
      _DownloadBehavior._(status, body: body);

  /// 挂起直到 gate 完成（或被取消打断）。
  factory _DownloadBehavior.gated(Completer<void> gate, Uint8List bytes) =>
      _DownloadBehavior._(200, bytes: bytes, gate: gate);

  final int status;
  final String? body;
  final Uint8List? bytes;
  final Completer<void>? gate;
}

class _DownloadMockAdapter implements HttpClientAdapter {
  _DownloadMockAdapter(this.behaviors, {this.entered});

  final List<_DownloadBehavior> behaviors;
  /// entered barrier（RC3-02）：首个 fetch 进入时完成，供测试等待
  /// 「请求已分发」再取消。
  final Completer<void>? entered;
  int requestCount = 0;

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    if (requestCount >= behaviors.length) {
      throw StateError('download 请求数超出预期: ${requestCount + 1}');
    }
    final behavior = behaviors[requestCount];
    requestCount++;
    // RC3-01：可空实例字段不能因判空自动提升，取局部变量后再解引用。
    final barrier = entered;
    if (barrier != null && !barrier.isCompleted) {
      barrier.complete();
    }
    // 挂起行为：等 gate 或取消（dio 把 CancelToken.whenCancel 传入）。
    // 取消时 dio 的 race 已让调用方收到 requestCancelled，fetch 的
    // 返回值会被丢弃；这里必须返回普通响应而非抛错——被取消的
    // operation 不再消费 fetch 结果，孤儿异常会变成 uncaught error。
    final gate = behavior.gate;
    if (gate != null) {
      if (cancelFuture != null) {
        await Future.any([gate.future, cancelFuture]);
      } else {
        await gate.future;
      }
    }
    final body = behavior.body;
    if (body != null) {
      return ResponseBody.fromString(body, behavior.status, headers: {
        'content-type': ['application/json'],
      });
    }
    final bytes = behavior.bytes!;
    return ResponseBody(
      Stream<Uint8List>.fromIterable([bytes]),
      behavior.status,
      headers: {
        'content-length': ['${bytes.length}'],
      },
    );
  }

  @override
  void close({bool force = false}) {}
}
