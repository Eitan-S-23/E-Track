import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:crypto/crypto.dart';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:get/get.dart' hide Response;
import 'package:path_provider/path_provider.dart';

import '../config/share_links.dart';
import '../ota/ota_ble_codec.dart';
import '../ota/ota_ble_transport.dart';
import '../ota/ota_device_info.dart';
import '../ota/ota_diagnostics.dart';
import '../ota/ota_experiment_config.dart';
import '../ota/ota_download.dart';
import '../ota/ota_firmware_latest.dart';
import '../ota/ota_link_stats.dart';
import '../ota/ota_mono.dart';
import 'app_update_service.dart';
import 'bluetooth_service.dart';

/// OTA 升级领域阶段（PR16：UI 由 phase 驱动，不解析状态文本）。
enum OtaPhase {
  /// 初始/无操作。
  idle,
  /// latest 查询中。
  checkingUpdate,
  /// 固件下载中。
  downloading,
  /// 下载完成并校验，待安装。
  readyToInstall,
  /// BLE 传输中（durable 进度）。
  transferring,
  /// END ACK OK：包传输完成，等待设备重启。
  waitingReboot,
  /// 重连成功，GET_INFO 复核目标身份中。
  reconnectVerify,
  /// 目标身份确认，升级完成。
  completed,
  /// 用户取消。
  cancelled,
  /// 失败（终态或可稍后重试，见 terminalState）。
  failed,
}

/// OTA 固件升级服务（编排层）。
///
/// 分层（OTA-XC 各条款的 Flutter 侧唯一编排入口）：
/// - 设备身份：GET_INFO → [DeviceOtaInfo]（无设备不发任何请求）；
/// - 检查更新：typed latest schema v2（终止态错误进入 [OtaTerminalState]，
///   并闭锁资产/文件/入口，直到重新 [readDeviceInfo] 建立有效查询链）；
/// - 下载：[OtaFirmwareDownload]（sidecar/Range/摘要/原子 rename）；
/// - BLE 传输：[OtaBleTransport]（credit 窗口、durable 进度、断点续传）；
/// - 成功闭环：END ACK OK 只代表包传完；完成 = 设备重启重连 +
///   GET_INFO 目标身份（versionCode/raw image SHA）复核通过（PR07）。
///
/// 红线：不硬编码 deviceModel/版本；未知值 fail closed；
/// MCU ACK 是 credit 与 durable 的唯一真相；取消按层归责；
/// 同一时间只允许一个升级族操作（下载/传输互斥，取消代次防竞态）。
class OtaService extends GetxController {
  static OtaService get to => Get.find();

  /// [downloadDio]/[firmwareDirProvider]/[latestUriBuilder]/[onNotify]/
  /// [downloadFileGate]
  /// 为测试注入点：生产缺省用独立下载 Dio、应用文档目录下的
  /// firmware/、ShareLinks latest 构造与 Get.snackbar 通知（行为不变）。
  /// [onNotify] 隔离 UI 副作用（RC3-02）：测试注入记录器后不再依赖
  /// runZonedGuarded 吞 GetQueue 无 overlay 上下文的异步 TypeError——
  /// 空 handler 会把产品代码的真实未处理异常一并吞掉，测试失去鉴别力。
  /// [downloadFileGate] 让用例在同资产文件族的串行闸内安排后来者接管
  /// （RC3-04/05），生产缺省用进程内共享闸 [OtaFilePathGate.shared]。
  /// [rebootWindow]/[rebootProbeTimeout]/[rebootProbeInterval] 为重启
  /// 复核时序注入点（O4 实测整改）：设备复位→BLE 可连接实测 ≥97s，
  /// 60s 固定窗口造成升级已成功但复核假阴性；生产默认 180s 总窗口 +
  /// 单轮探测 20s 上限 + 3s 轮询间隔，测试注入短值实测时序行为。
  OtaService({
    BluetoothService? bluetoothService,
    Dio? dio,
    Dio? downloadDio,
    Future<Directory> Function()? firmwareDirProvider,
    Uri Function(DeviceOtaInfo info, int appVersionCode, String? channel)?
        latestUriBuilder,
    void Function(String title, String message)? onNotify,
    OtaFilePathGate? downloadFileGate,
    Duration? rebootWindow,
    Duration? rebootProbeTimeout,
    Duration? rebootProbeInterval,
  })  : _bluetoothService = bluetoothService,
        _notifyImpl = onNotify,
        _downloadFileGate = downloadFileGate ?? OtaFilePathGate.shared,
        _dio = dio ??
            Dio(
              BaseOptions(
                // metadata 请求超时（OTA-XC-RETRY-POLICY：连接 15s/接收 20s）。
                connectTimeout: const Duration(seconds: 15),
                receiveTimeout: const Duration(seconds: 20),
                sendTimeout: const Duration(seconds: 15),
                headers: const {
                  'Accept': 'application/json',
                },
              ),
            ),
        // 下载用独立 Dio：大文件流式接收不适用 metadata 的 20s 接收超时。
        _downloadDio = downloadDio ??
            Dio(
              BaseOptions(
                connectTimeout: const Duration(seconds: 15),
                sendTimeout: const Duration(seconds: 15),
                // RC3-11：流式下载的接收空闲保护——60s 内无任何数据块
                // 判定连接挂死（正常下载块间隔为毫秒级），防止无
                // receiveTimeout 的下载流永久悬挂。
                receiveTimeout: const Duration(seconds: 60),
              ),
            ),
        _firmwareDirProvider = firmwareDirProvider ?? _defaultFirmwareDir,
        _latestUriBuilder = latestUriBuilder ?? _defaultLatestUriBuilder,
        _rebootWindow = rebootWindow ?? const Duration(seconds: 180),
        _rebootProbeTimeout = rebootProbeTimeout ?? const Duration(seconds: 20),
        _rebootProbeInterval =
            rebootProbeInterval ?? const Duration(seconds: 3);

  final BluetoothService? _bluetoothService;
  final void Function(String title, String message)? _notifyImpl;
  final Dio _dio;
  final Dio _downloadDio;

  /// 重启复核总窗口（O4 实测整改）：设备复位→BLE 可连接实测 ≥97s
  /// （BCB 搬运 ~600KB + 启动 + BLE 起播），旧 60s 固定窗口使升级已
  /// 成功的会话以 REBOOT_RECONNECT_FAILED 假阴性收场。
  final Duration _rebootWindow;
  /// 重启复核单轮探测上限：防单轮 connect 挂起吞掉剩余全部窗口——
  /// O4 logcat 实测第一轮 connect 抛错后后续轮挂起（日志静默），
  /// 外层按剩余总预算封顶的 timeout 一轮即耗尽窗口。
  final Duration _rebootProbeTimeout;
  /// 重启复核轮询间隔。
  final Duration _rebootProbeInterval;

  /// 同资产文件族的跨 attempt 串行闸（RC3-04/05）：下载器的写入/rename/
  /// 清理共用它，避免上一 attempt 迟到的清理删掉新 attempt 的同名文件。
  final OtaFilePathGate _downloadFileGate;
  final Future<Directory> Function() _firmwareDirProvider;
  final Uri Function(DeviceOtaInfo info, int appVersionCode, String? channel)
      _latestUriBuilder;

  /// UI 通知唯一出口（RC3-02）：测试注入替身后 Get.snackbar 不再在
  /// 无 widget 树的测试宿主里异步抛错。
  void _notify(String title, String message) {
    final impl = _notifyImpl;
    if (impl != null) {
      impl(title, message);
    } else {
      Get.snackbar(title, message);
    }
  }

  /// 生产缺省：ShareLinks latest query 构造（含全部身份参数与回执校验）。
  static Uri _defaultLatestUriBuilder(
    DeviceOtaInfo info,
    int appVersionCode,
    String? channel,
  ) {
    final original = ShareLinks.firmwareLatestUri(
      deviceModel: info.deviceModel,
      currentVersionCode: info.currentVersionCode,
      currentImageSha: info.currentImageSha256Hex,
      hardwareRevision: info.hardwareRevision,
      layoutId: info.layoutId,
      bootVersion: info.bootVersion,
      protocolVersion: info.protocolVersion,
      appVersionCode: appVersionCode,
      channel: channel,
    );
    final experiment = OtaExperimentRuntime.current.requireForOta();
    return experiment?.latestUri(original, versionCode: info.currentVersionCode,
        imageSha256: info.currentImageSha256Hex) ?? original;
  }

  BluetoothService get _ble =>
      _bluetoothService ?? Get.find<BluetoothService>();

  final _upgradeProgress = 0.0.obs;
  final _downloadProgress = 0.0.obs;
  final _durableProgress = 0.0.obs;
  final _upgradeStatus = ''.obs;
  final _isUpgrading = false.obs;
  final _terminalState = Rxn<OtaTerminalState>();
  final _phase = OtaPhase.idle.obs;

  DeviceOtaInfo? _deviceInfo;
  FirmwareLatestInfo? _latestInfo;
  OtaFirmwareAsset? _asset;
  String? _releaseId;
  File? _firmwareFile;
  _VerifiedPackage? _verified;
  OtaFirmwareDownload? _download;
  /// 当前在途下载的取消令牌。在发起 download 前创建并传入——
  /// OtaFirmwareDownload 内部 token 注册发生在其首个 await 之后，
  /// 极早期取消（注册前）经内部 map 会丢失；持有本字段使
  /// [cancelUpgrade] 在任何时序下都能立即停止在途请求（RC2-04）。
  CancelToken? _activeDownloadToken;

  /// 下载尝试序号（RC3-04/05）：每次 `_downloadOnce` 自增，作为
  /// OtaFirmwareDownload 删除边界的归属判定依据。删除动作在 await 之间
  /// 执行，序号一变即说明该 attempt 已不是文件所有者，迟到的清理必须让位。
  int _downloadAttemptSeq = 0;

  /// 在途 latest 请求令牌（RC3-04）：cancelUpgrade 立即中断在途
  /// metadata 请求，不等待其自然超时。
  CancelToken? _activeLatestToken;
  OtaBleTransport? _transport;
  /// 当前 [_transport] 绑定时的物理链路快照（RC3-08⑦）。
  ///
  /// transport 对象活着不等于底层链路还是绑定时那一条：后台期间系统
  /// 可能断开旧连接后重连（甚至连到同地址的另一台设备）。恢复发送前
  /// 必须用这三项与现场重新比对——链路代次（BluetoothService 观测的
  /// 真实连接迁移）、可重新发现的 OTA 特征、以及 INFO 身份，缺一不可：
  /// 只读 INFO 无法区分「同一条链路」与「新链路上的同型号设备」。
  String? _boundAddress;
  Map<String, String>? _boundChars;
  int? _boundLinkGeneration;
  /// 取消代次：cancelUpgrade 递增；在途操作发现代次变化即静默退出。
  int _cancelGeneration = 0;
  /// 后台复核 failClosed 已决定终止（RC3-08/12②）：failClosed 发布终止态
  /// 时**不**前进取消代次——它终止的是「当前正在进行」的传输，不构成用户
  /// 取消语义（取消路径的代次递增 + 资产清理由 cancelUpgrade 承担）。因此
  /// 仅靠 `generation == _cancelGeneration` 无法区分「本 owner 正常在途」与
  /// 「本 owner 已被 failClosed 决定终止」。在途物理写随后以 WRITE_TIMEOUT/
  /// 原生异常退出时，三个 catch 分支必须消费本标记并静默让出，否则会用
  /// 通用失败文案 + failed phase 覆盖 failClosed 已发布的终止原因/可重试
  /// 语义/收尾相位（cancelled）。
  bool _failClosedDecided = false;
  /// 当前 owner 的完成信号（RC3-04）：非 null 表示有升级族操作在途。
  /// cancelUpgrade 等待它确认旧 owner 完全退出（含 finally）后才解锁，
  /// 防止新入口在旧 owner 尚未退出时进入造成并发发布/transport 撕裂。
  Future<void>? _ownerDone;
  /// owner 登记代数（RC3-04⑤）：_runExclusive 每次登记时自增。仅凭
  /// 「_ownerDone == null」无法区分「从未有 owner」与「后来 owner 已
  /// 跑完退出」——cancelUpgrade 以「取消窗口内 epoch 未前进」识别
  /// 没有任何后来者进出，避免覆盖后来者的包与终态。
  int _ownerEpoch = 0;
  /// 设备身份快照所属的 BLE 地址（RC3-08）：换设备连接时旧快照立即
  /// 失效，不得用 A 设备的身份给 B 设备发请求/传输。
  String? _deviceInfoAddress;
  /// 签署当前保留资产的身份与地址（RC3-12⑦）。
  ///
  /// 资产（_latestInfo/_asset/_releaseId/_firmwareFile/_verified）由某次
  /// 设备身份查询签发，其有效性绑定该身份，而不是绑定「上一次快照」。
  /// 读取失败会把 _deviceInfo/_deviceInfoAddress 一并清空，因此仅用
  /// previous 快照比对会漏掉「身份 A 有资产 → 读取失败 → 读到 B」：B 与
  /// null 不算漂移，A 的清单与包被沿用给 B，随后的 BEGIN 复核是 B 比 B
  /// 也一样通过。资产自带签署者后，任何无法证明归属当前身份/地址的资产
  /// 都直接作废（fail-closed）。
  DeviceOtaInfo? _assetOwnerInfo;
  String? _assetOwnerAddress;
  /// 最近一次成功 latest 查询使用的显式 channel（RC3-10⑤）：URL 过期
  /// 自动刷新必须绑定同一查询身份，不得退回默认通道。
  String? _lastCheckedChannel;

  double get upgradeProgress => _upgradeProgress.value;
  double get downloadProgress => _downloadProgress.value;
  double get durableProgress => _durableProgress.value;
  String get upgradeStatus => _upgradeStatus.value;
  bool get isUpgrading => _isUpgrading.value;
  bool get isFirmwareServiceConfigured =>
      _latestUriBuilder != _defaultLatestUriBuilder ||
      ShareLinks.hasFirmwareUpdateEndpoint;
  File? get downloadedFirmwareFile => _firmwareFile;
  DeviceOtaInfo? get deviceInfo => _deviceInfo;
  FirmwareLatestInfo? get latestInfo => _latestInfo;
  OtaTerminalState? get terminalState => _terminalState.value;
  /// 当前领域阶段（UI 唯一驱动源）。
  OtaPhase get phase => _phase.value;
  Rx<OtaPhase> get phaseRx => _phase;
  /// 状态文案的 Rx 暴露（RC3-12）：终态发布次序的发布时刻观测点——
  /// 监听器在赋值同步段内触发，可在回调里核对 IO 事实（如包文件是否
  /// 已删除），而非仅在取消流程返回后补断言。
  Rx<String> get upgradeStatusRx => _upgradeStatus;

  @override
  void onInit() {
    super.onInit();
    _upgradeStatus.value = isFirmwareServiceConfigured
        ? '固件服务已就绪'
        : '固件服务未配置';
  }

  @override
  void onClose() {
    _transport?.dispose();
    _dio.close(force: true);
    _downloadDio.close(force: true);
    super.onClose();
  }

  // ---- 设备身份（GET_INFO） ----

  /// 通过 BLE GET_INFO 建立设备身份快照。
  ///
  /// 前置：设备已连接且能发现精确 FFF0/FFF2/FFF1 特征。
  /// 失败（无连接、无 OTA 特征、身份解析失败）时置状态并返回 null——
  /// 不用任何默认身份发请求，且旧快照立即失效（PR09）。
  /// 成功即解锁终止态（重建有效查询链，PR11）。
  ///
  /// 升级族互斥（RC3-04）：非升级期间与其他入口经同一 owner 锁串行，
  /// 并发 readDeviceInfo 不得互相 dispose 对方的 transport。
  Future<DeviceOtaInfo?> readDeviceInfo(String deviceAddress) async {
    if (_isUpgrading.value) {
      // 升级进行中禁止重建 transport：_bindTransport 会 dispose
      // 在途 transport，打断传输（RC2-04）。返回现有快照。
      return _deviceInfo;
    }
    return _runExclusive((generation) async {
      _deviceInfo = null; // 先失效旧快照，成功才重建
      _deviceInfoAddress = null;
      final stats = OtaDiagnostics.current.enabled
          ? OtaLinkStats(label: 'query', device: deviceAddress)
          : null;
      DeviceOtaInfo? fail(String stage, String reason) {
        stats?.recordFailure(stage: stage, reason: reason);
        return null;
      }

      stats?.phaseStart('bind');
      try {
        final otaChars = await _ble.findExactOtaCharacteristicsByAddress(
          deviceAddress,
          stats: stats,
        );
        // 发现链取消检查（RC3-04）：等待发现期间用户取消，不继续
        // 绑定/GET_INFO。
        if (generation != _cancelGeneration) {
          return fail('cancelled', 'generation-changed');
        }
        if (otaChars == null) {
          _upgradeStatus.value = '设备未暴露 OTA 服务（FFF0/FFF2/FFF1）';
          return fail('discover', 'ota-chars-missing');
        }
        final transport = await _bindTransport(deviceAddress, otaChars,
            stats: stats);
        stats?.phaseEnd('bind');
        // 绑定链取消检查（RC3-04）：订阅/MTU 交换期间取消，不发
        // GET_INFO。
        if (generation != _cancelGeneration) {
          // RC3-04⑤：迟到完成的 bind 产物无人接管——transport 与其订阅
          // 不释放会悬挂占用通知通道（PR10 一个连接代次仅一个订阅，
          // 残留订阅会顶掉下一次绑定的流）。释放后静默退出。
          await transport?.dispose();
          if (transport != null && identical(_transport, transport)) {
            _transport = null;
          }
          return fail('cancelled', 'generation-changed');
        }
        if (transport == null) {
          _upgradeStatus.value = 'OTA 通知订阅失败';
          return fail('bind', 'notify-subscribe-failed');
        }
        final info = await transport.getDeviceInfo();
        // 发布身份前取消检查（RC3-04）：取消后不发布新快照。
        if (generation != _cancelGeneration) {
          return fail('cancelled', 'generation-changed');
        }
        _deviceInfo = info;
        // 快照绑定来源地址（RC3-08）：换设备连接时旧快照失效。
        _deviceInfoAddress = deviceAddress;
        // RC3-08⑤/12⑤/12⑦：资产失效以「签署这批资产的身份/地址」为
        // 基准，不是「上一次快照」。旧写法捕获 previousInfo/
        // previousAddress 后立即把两者置空，一旦中间夹了一次读取失败，
        // 下次成功读到的 B 与 null 比对不算漂移，A 签发的 latest/资产/
        // 已验证包就被沿用给 B，之后 BEGIN 的 recheck 是 B 比 B 同样
        // 放行。改为比对资产签署者后，A→(失败)→B 也能判定失效；身份
        // 字段巧合相同但地址已变（同型号另一台设备）同样失效。
        if (_hasFirmwareAssets && !_assetsBelongTo(info, deviceAddress)) {
          final owner = _assetOwnerInfo;
          // 签署者缺失（无法证明归属）与身份字段不符同级处理。
          final identityDrift =
              owner == null || !deviceIdentityMatches(owner, info);
          _clearFirmwareInfo();
          _terminalState.value = null;
          _upgradeStatus.value = identityDrift
              ? '设备身份已变更，旧的固件清单与下载包已作废，请重新检查更新'
              : '设备地址已变更，旧的固件清单与下载包已作废，请重新检查更新';
        } else {
          // 显式重新建立有效查询链：终止态解锁（PR11）。
          _terminalState.value = null;
          _upgradeStatus.value =
              '设备身份已确认: ${info.deviceModel} (vcode ${info.currentVersionCode})';
        }
        return info;
      } on OtaDeviceIdentityException catch (e) {
        _deviceInfo = null;
        _upgradeStatus.value = '设备身份识别失败: ${e.code}';
        _terminalState.value = OtaTerminalState(
          code: e.code,
          message: e.toString(),
        );
        return fail('identity', e.code);
      } catch (e) {
        _deviceInfo = null;
        _upgradeStatus.value = 'GET_INFO 失败: $e';
        return fail('query', e.runtimeType.toString());
      } finally {
        stats?.phaseEnd('bind');
        // The retained transport may receive late callbacks after this query.
        stats?.retire(reason: 'query-finished');
        stats?.emitSummary();
      }
    });
  }

  // ---- 检查更新（latest schema v2） ----

  /// 检查固件更新。必须先 [readDeviceInfo] 成功建立 [DeviceOtaInfo]。
  ///
  /// 返回 latest DTO；`updateAvailable=false`/终止态/解析失败都返回 null
  /// 并通过 [upgradeStatus]/[terminalState]/[phase] 解释原因。
  ///
  /// 入口互斥（RC3-04）：与其他升级族入口经同一 owner 锁串行；取消
  /// 代次贯穿 latest 重试与发布，取消后不发布旧状态。
  Future<FirmwareLatestInfo?> checkFirmwareUpdate({String? channel}) async {
    if (_isUpgrading.value) {
      _notify('提示', '升级流程进行中，请先取消或等待完成');
      return null;
    }
    final locked = _terminalLocked();
    if (locked != null) {
      _upgradeStatus.value = locked;
      return null;
    }
    final info = _deviceInfo;
    if (info == null) {
      _upgradeStatus.value = '未建立设备身份，先连接设备完成 GET_INFO';
      _notify('错误', '请先连接设备后再检查固件更新');
      return null;
    }
    if (!isFirmwareServiceConfigured) {
      _upgradeStatus.value = '固件服务未配置';
      _notify('错误', '固件更新地址未配置，无法检查更新');
      return null;
    }
    return _runExclusive((generation) async {
      final int appVersionCode;
      try {
        appVersionCode =
            await Get.find<AppUpdateService>().getLocalAppVersionCode();
      } catch (_) {
        _upgradeStatus.value = '无法读取本机 App 版本（appVersionCode）';
        _notify('错误', '无法读取本机应用版本，不能检查固件更新');
        return null;
      }
      // App-info await 后取消检查（RC3-04）：读取本地版本期间用户
      // 取消，不发 latest 请求。
      if (generation != _cancelGeneration) return null;
      return _checkLatestLocked(info, appVersionCode, channel,
          generation: generation);
    });
  }

  /// latest 查询主体（入口互斥/闭锁/身份检查已由调用方完成，RC2-04）。
  ///
  /// 独立拆出的原因：downloadFirmware 的 URL 失效刷新直接调用本方法，
  /// 不再临时解除 `_isUpgrading` 忙锁（原临时解锁存在竞态窗口）。
  ///
  /// [generation]（RC3-04）：调用方的取消代次，贯穿重试与发布；取消后
  /// 静默退出，不发布旧清单/状态。null 表示调用方不参与取消代次。
  Future<FirmwareLatestInfo?> _checkLatestLocked(
    DeviceOtaInfo info,
    int appVersionCode,
    String? channel, {
    int? generation,
  }) async {
    _phase.value = OtaPhase.checkingUpdate;
    _terminalState.value = null;
    final gen = generation;
    try {
      _upgradeStatus.value = '检查固件更新中...';
      _upgradeProgress.value = 0.0;

      final uri = _latestUriBuilder(info, appVersionCode, channel);
      final response = await _getLatestWithRetry(uri, gen);
      if (response == null) return null; // 取消：静默退出，不发布状态
      final body = _readJsonObject(response.data);
      final latest = FirmwareLatestInfo.parse(
        body,
        expectedDeviceModel: info.deviceModel,
        // 回显校验用与请求一致的 channel（RC2-04）：query 构造的
        // effectiveChannel 默认值即 ShareLinks.updateChannel。
        expectedChannel: channel ?? ShareLinks.updateChannel,
      );

      if (!latest.updateAvailable) {
        _clearFirmwareInfo();
        final code = latest.errorCode ?? 'NO_UPDATE';
        if (code == 'CHANNEL_STOPPED') {
          _upgradeStatus.value = '固件通道已停发，稍后重试';
          _terminalState.value = OtaTerminalState(
            code: 'CHANNEL_STOPPED',
            message: latest.maintenanceMessage ?? '固件通道已停发',
            retryableLater: true,
          );
          _phase.value = OtaPhase.failed;
          return null;
        }
        _upgradeStatus.value = '固件已是最新版本';
        _phase.value = OtaPhase.idle;
        return null;
      }

      // 发布前取消检查（RC3-04）：取消后不得发布新清单/状态。
      if (gen != null && gen != _cancelGeneration) return null;
      // 清单变化使旧下载包失效（PR12）：同包重复检查不失效。
      _invalidatePackageIfChanged(latest);
      _latestInfo = latest;
      _asset = latest.asset;
      _releaseId = latest.releaseId;
      // 登记签署者（RC3-12⑦）：本批资产由本次查询所用的身份/地址签发，
      // 后续任何身份读取都以此为失效基准。
      _assetOwnerInfo = info;
      _assetOwnerAddress = _deviceInfoAddress;
      // 记忆本次查询身份（RC3-10⑤）：URL 过期刷新绑定同一 channel。
      _lastCheckedChannel = channel;
      _upgradeStatus.value = '发现新固件: ${latest.versionName}';
      if (_verified != null) {
        _phase.value = OtaPhase.readyToInstall;
      } else {
        _phase.value = OtaPhase.idle;
      }
      return latest;
    } on OtaLatestParseException catch (e) {
      // 解析失败是稳定终态：闭锁资产/文件，重试同样请求无意义（PR11）。
      _clearFirmwareInfo();
      _terminalState.value = OtaTerminalState(
        code: 'LATEST_SCHEMA_INVALID',
        message: e.message,
      );
      _upgradeStatus.value = '固件清单解析失败: ${e.message}';
      _notify('错误', '固件清单不符合 schema v2: ${e.message}');
      _phase.value = OtaPhase.failed;
      return null;
    } on FormatException catch (e) {
      // 200 响应体非 JSON 对象（如空 body/数组）：与解析失败同级稳定
      // 终态，清旧资产防止继续消费过期清单（RC3-10）。
      _clearFirmwareInfo();
      _terminalState.value = OtaTerminalState(
        code: 'LATEST_SCHEMA_INVALID',
        message: e.message,
      );
      _upgradeStatus.value = '固件清单解析失败: ${e.message}';
      _notify('错误', '固件清单不符合 schema v2: ${e.message}');
      _phase.value = OtaPhase.failed;
      return null;
    } catch (error) {
      // retryExhausted=true：到达这里的一定是 _getLatestWithRetry 三次
      // 尝试耗尽后的错误（RC2-04）——BACKEND_UNAVAILABLE/RATE_LIMITED
      // 此时进入可稍后重试终态并清旧资产，避免沿用可能过期的清单。
      if (gen != null && gen != _cancelGeneration) return null; // 取消：静默
      final terminal = _terminalFromDioError(error, retryExhausted: true);
      if (terminal != null) {
        _terminalState.value = terminal;
        _clearFirmwareInfo();
        _upgradeStatus.value = '设备不兼容: ${terminal.code}';
        _notify('提示', terminal.userMessage);
        _phase.value = OtaPhase.failed;
        return null;
      }
      final message = _friendlyDioMessage(error);
      _upgradeStatus.value = '检查更新失败: $message';
      _notify('错误', '检查固件更新失败: $message');
      _phase.value = OtaPhase.failed;
      return null;
    }
  }

  // ---- 下载（sidecar + Range 续传） ----

  /// 下载当前选中的固件资产并校验 SHA-256。成功后 [downloadedFirmwareFile] 可用。
  ///
  /// 下载 URL 过期/资产冲突/本地 partial 损坏会自动重新 latest 一次并
  /// 重下（仅一次，防拉锯）。
  Future<bool> downloadFirmware() async {
    if (_isUpgrading.value) {
      _notify('提示', '升级流程进行中，请先取消或等待完成');
      return false;
    }
    final locked = _terminalLocked();
    if (locked != null) {
      _upgradeStatus.value = locked;
      return false;
    }
    final asset = _asset;
    final releaseId = _releaseId;
    if (asset == null || releaseId == null) {
      _notify('错误', '固件下载信息无效，请重新检查更新');
      return false;
    }
    final info = _deviceInfo;
    if (info == null) {
      _notify('错误', '设备身份未确认，无法下载固件');
      return false;
    }
    // owner 锁在首个 await 前取得（RC3-04）：同步置位无竞态窗口。
    return await _runExclusive((generation) async {
      _phase.value = OtaPhase.downloading;
      var downloaded = await _downloadOnce(asset, releaseId, generation);
      // 401 TOKEN_*/410/416/409/本地 partial 损坏：自动重新 latest 一次
      // 再重下（同一次用户操作，仅一次，防拉锯）。
      // RC3-10⑤：当前存在稳定终止态时不得自动刷新——_checkLatestLocked
      // 成功会清掉终止态，服务端明确拒绝的稳定闭锁被自动路径洗白；
      // retryableLater 终态语义是「允许稍后重试」，URL_EXPIRED 刷新
      // 属于合法稍后重试，不受此守卫拦截。
      if (downloaded == null &&
          generation == _cancelGeneration &&
          _needsFreshManifest &&
          (_terminalState.value == null ||
              _terminalState.value!.retryableLater)) {
        _needsFreshManifest = false;
        // 刷新清单不解除忙锁（RC2-04）：直接调用无锁版本查询体，
        // 消除原临时解锁的竞态窗口。刷新绑定原查询 channel（RC3-10⑤），
        // 取消代次贯穿（RC3-04）。
        final int appVersionCode;
        try {
          appVersionCode =
              await Get.find<AppUpdateService>().getLocalAppVersionCode();
        } catch (_) {
          _upgradeStatus.value = '无法读取本机 App 版本（appVersionCode）';
          return false;
        }
        if (generation != _cancelGeneration) return false; // 取消：静默退出
        final latest = await _checkLatestLocked(
          info,
          appVersionCode,
          _lastCheckedChannel,
          generation: generation,
        );
        final newAsset = _asset;
        final newReleaseId = _releaseId;
        if (latest != null &&
            latest.updateAvailable &&
            newAsset != null &&
            newReleaseId != null) {
          downloaded = await _downloadOnce(newAsset, newReleaseId, generation);
        }
      }
      return downloaded ?? false;
    }) ?? false;
  }

  bool _needsFreshManifest = false;

  Future<bool?> _downloadOnce(
    OtaFirmwareAsset asset,
    String releaseId,
    int generation,
  ) async {
    // 发请求前取消检查（RC3-04）：注册前取消（owner 已登记、请求尚未
    // 分发到 adapter）在此静默退出，不发出任何请求。
    if (generation != _cancelGeneration) return false;
    try {
      // 归属判定（RC3-04/05）：每次下载尝试取一个单调序号，删除边界上
      // 复核序号未变才允许删。**但序号只回答「还属不属于我」**——两次
      // attempt 必然共用同一 assetId、文件名与 `.part` 路径（续传语义），
      // 所以序号判定通过不等于可以按路径删；真正的互斥来自所有 attempt
      // 共用的 [OtaFilePathGate]：创建/rename/删除同族文件都在闸内串行，
      // 归属复核也放在闸内，判定与破坏性 IO 之间不再有可插入的 await。
      //
      // 每次 `_downloadOnce` 都 new 一个新的 [OtaFirmwareDownload]，因此
      // 下载器实例内的 `_cancelTokens`/`_inFlight` **不跨 attempt 共享**，
      // 也谈不上被新 attempt 覆盖。跨 attempt 真正共享的只有：文件路径、
      // 文件名、assetId，以及这里的串行闸。
      final attemptSeq = ++_downloadAttemptSeq;
      _download = OtaFirmwareDownload(
        dio: _downloadDio,
        dirProvider: _firmwareDirProvider,
        stillOwns: () => _downloadAttemptSeq == attemptSeq,
        fileGate: _downloadFileGate,
      );
      // 发起前创建并登记令牌：cancelUpgrade 可取消任何时序下的在途请求。
      final token = CancelToken();
      _activeDownloadToken = token;
      _downloadProgress.value = 0.0;
      _upgradeProgress.value = 0.0;
      _upgradeStatus.value = '下载固件中...';
      final file = await _download!.download(
        asset: asset,
        releaseId: releaseId,
        downloadUrl: asset.downloadUrl,
        cancelToken: token,
        onProgress: (received, total) {
          final progress = total > 0 ? (received / total).clamp(0.0, 1.0) : 0.0;
          _downloadProgress.value = progress;
          _upgradeProgress.value = progress;
          _upgradeStatus.value =
              '下载中: ${(progress * 100).toStringAsFixed(1)}% '
              '(${_formatBytes(received)}/${_formatBytes(total)})';
        },
      );
      // 取消代次变化：不发布固件文件/已验证状态（RC2-04）。
      if (generation != _cancelGeneration) return false;
      _downloadProgress.value = 1.0;
      _upgradeProgress.value = 1.0;
      _firmwareFile = file;
      _verified = _VerifiedPackage(
        assetId: asset.assetId,
        releaseId: releaseId,
        sha256: asset.sha256,
        sizeBytes: asset.sizeBytes,
        versionCode: _latestInfo?.versionCode ?? 0,
        file: file,
      );
      _upgradeStatus.value = '固件已下载并校验';
      _phase.value = OtaPhase.readyToInstall;
      return true;
    } on OtaDownloadException catch (e) {
      if (e.code == 'CANCELLED') {
        // cancelled 终态由 cancelUpgrade 在包清理完成后统一发布
        // （RC3-12）：本处抢先发布会让「cancelled 即包已处置」的 UI
        // 契约提前成立，出现 cancelled 已显示、partial 随后才删的中间态。
        return false;
      }
      // 终止型/未知 HTTP 错误闭锁（RC3-10）：服务端明确终止码
      // （HARDWARE_INCOMPATIBLE 等）或未知 errorCode 不进刷新重试，
      // 直接闭锁入口并清资产，携带 requestId 供排查。错误体不可解析
      // （httpError == null）但状态为稳定 4xx 时同样闭锁——空/坏体
      // 的 4xx 是服务端明确拒绝，本地证据码 HTTP_<status>，不静默
      // 降级为可重试失败（fail closed）。
      // RC3-10⑤：已知 errorCode 中既非自动重试类（RATE_LIMITED/
      // BACKEND_UNAVAILABLE）也非稍后重试类（CHANNEL_STOPPED）的，
      // 同样视为稳定拒绝——INVALID_PARAMETER/UNKNOWN_DEVICE_MODEL
      // 等已知非兼容码重发同请求必然复现，留在普通失败分支会允许
      // 用户无限次撞同一堵墙而不闭锁。
      final httpError = e.httpError;
      // RC3-10/11：autoRetryable/retryableLater 的 HTTP 状态约束已收敛到
      // OtaHttpError（errorCode 必须与 OTA-XC-HTTP-ERROR 表的状态匹配才
      // 成立），此处不再重复维护第二份状态表，避免两处判定漂移；错配响应
      // （如 403 携带 CHANNEL_STOPPED）因此落入下面的稳定拒绝分支。
      final autoRetryable = httpError != null && httpError.isAutoRetryable;
      final stableReject =
          (httpError != null &&
              (httpError.isTerminal ||
                  httpError.isUnknown ||
                  (!autoRetryable && !httpError.isRetryableLater))) ||
              (httpError == null &&
                  e.httpStatus != null &&
                  e.httpStatus! >= 400 &&
                  e.httpStatus! < 500);
      if (stableReject) {
        final String code;
        if (httpError != null) {
          code = httpError.isUnknown
              ? 'HTTP_${httpError.httpStatus}_${httpError.errorCode}'
              : httpError.errorCode;
        } else {
          code = 'HTTP_${e.httpStatus}';
        }
        _terminalState.value = OtaTerminalState(
          code: code,
          // RC3-10：终态携带兼容性上下文字段——CLIENT_TOO_OLD 的
          // 「需 ≥ minAppVersionCode」、HARDWARE_INCOMPATIBLE 等的
          // required/actual 展示依赖这些字段，缺失时 userMessage 退化为
          // 无版本号文案（对齐 _terminalFromDioError 的字段传递）。
          minAppVersionCode: httpError?.minAppVersionCode,
          requiredValue: httpError?.requiredValue,
          actualValue: httpError?.actualValue,
          message: httpError != null
              ? '${httpError.message ?? '固件下载被服务端拒绝'}'
                  '（requestId: ${httpError.requestId ?? '无'}）'
              : '${e.message}（HTTP ${e.httpStatus}，无错误体）',
          requestId: httpError?.requestId,
        );
        // RC3-10⑤：稳定终止后复位刷新标志——残留的 _needsFreshManifest
        // 会让下一次 downloadFirmware 的外层自动刷新条件成立，经
        // _checkLatestLocked 清掉刚发布的终止态，稳定闭锁被洗白。
        _needsFreshManifest = false;
        _clearFirmwareInfo();
        _upgradeStatus.value = '固件下载终止: $code';
        _notify('错误', _terminalState.value!.userMessage);
        _phase.value = OtaPhase.failed;
        return null;
      }
      if (e.code == 'RANGE_AT_END' ||
          e.code == 'URL_EXPIRED' ||
          e.code == 'ASSET_CONFLICT' ||
          e.code == 'LOCAL_CORRUPT') {
        _needsFreshManifest = true;
      }
      _firmwareFile = null;
      _verified = null;
      _upgradeStatus.value = '固件下载失败: ${e.message}';
      _notify('错误', '固件下载失败: ${e.message}');
      _phase.value = OtaPhase.failed;
      return null;
    } catch (error) {
      if (error is DioException && CancelToken.isCancel(error)) {
        // 同 CANCELLED 分支（RC3-12）：不在此处发布 cancelled 终态。
        return false;
      }
      final message = _friendlyDioMessage(error);
      _firmwareFile = null;
      _verified = null;
      _upgradeStatus.value = '固件下载失败: $message';
      _notify('错误', '固件下载失败: $message');
      _phase.value = OtaPhase.failed;
      return null;
    } finally {
      _activeDownloadToken = null;
    }
  }

  // ---- BLE 传输（startOtaUpgrade 状态机） ----

  /// 执行 BLE OTA 传输。前置：设备连接 + 固件已下载校验。
  ///
  /// 流程：GET_INFO（重连身份复核）→ BEGIN（同 package_sha256 续传）→
  /// credit 窗口推进 → END → 等待设备重启 → 重连 GET_INFO → 目标身份
  /// （versionCode/raw image SHA）复核（PR07 完整闭环）。
  Future<bool> startOtaUpgrade(String deviceAddress) async {
    final file = _firmwareFile;
    final info = _deviceInfo;
    final asset = _asset;
    if (file == null) {
      _notify('错误', '固件文件不存在，请先下载固件');
      return false;
    }
    if (info == null) {
      _notify('错误', '设备身份未确认，无法开始升级');
      return false;
    }
    if (asset == null) {
      _notify('错误', '固件资产信息缺失，请重新检查更新');
      return false;
    }
    // 身份快照必须属于目标设备（RC3-08）：跨设备复用旧快照直接拒绝。
    if (_deviceInfoAddress != deviceAddress) {
      _upgradeStatus.value = '设备身份快照与目标设备不符，请重新连接设备';
      _notify('错误', '设备身份与连接不符，请重新连接设备后再升级');
      return false;
    }
    // 资产必须由当前身份签发（RC3-12⑦）：BEGIN 前的 recheck 只比对
    // 「当前 INFO 与会话快照」，两者可以同为 B 而清单/包属于 A，比对
    // 恒等通过。这里直接查资产签署者，无法证明归属即拒绝入口。
    if (!_assetsBelongTo(info, deviceAddress)) {
      _upgradeStatus.value = '固件清单与下载包不属于当前设备身份，请重新检查更新';
      _notify('错误', '固件包与当前设备身份不符，请重新检查更新');
      return false;
    }
    if (_isUpgrading.value) {
      _notify('提示', '升级已在进行中');
      return false;
    }
    final locked = _terminalLocked();
    if (locked != null) {
      _upgradeStatus.value = locked;
      return false;
    }
    return await _runExclusive((generation) async {
      // 每轮升级重置 failClosed 决策（RC3-08/12②）：上个 owner 未被消费的
      // 残留决策不得沿用到新一轮传输的 catch。
      _failClosedDecided = false;
      _terminalState.value = null;
      _durableProgress.value = 0.0;
      _phase.value = OtaPhase.transferring;
      // P3-4 链路观测：本轮升级的单一时钟域实例（发现→绑定→复核→传输
      // 全链路同源时间戳；重启探测用独立 probe 实例，见 _waitForTargetIdentity）。
      final linkStats = OtaLinkStats(label: 'upgrade', device: deviceAddress);
      OtaBleTransport? activeTransport;
      final diagnostics = OtaDiagnostics.current;
      var diagnosticStarted = false;
      var diagnosticCompleted = false;
      // P3-4 观测：早退/取消统一留痕（阶段 + 原因）后返回 false——未进入
      // 传输的失败不得伪装成成功传输，也不得从终结摘要里静默消失。
      bool fail(String stage, String reason) {
        linkStats.recordFailure(stage: stage, reason: reason);
        return false;
      }
      try {
        // 就地读取并校验包字节（RC2-04）：锁后一次读取，长度+SHA 校验
        // 与传输共用同一份字节快照，替代原先 verifyFileMatchesAsset 二次
        // 读文件 + readAsBytesSync 再读一次的多份文件视图（文件在两次
        // 读取之间被改将无法被发现）。
        final package = await file.readAsBytes();
        if (generation != _cancelGeneration) {
          return fail('cancelled', 'generation-changed');
        }
        final packageDigest = sha256.convert(package);
        if (package.length < 64) {
          _upgradeStatus.value = '固件包长度非法: ${package.length}';
          _phase.value = OtaPhase.failed;
          return fail('validate', 'package-too-short');
        }
        if (package.length != asset.sizeBytes ||
            packageDigest.toString() != asset.sha256) {
          _firmwareFile = null;
          _verified = null;
          _upgradeStatus.value = '固件文件与清单不符（长度或 SHA-256），请重新下载';
          _notify('错误', '固件文件校验失败，请重新下载');
          _phase.value = OtaPhase.failed;
          return fail('validate', 'package-mismatch');
        }
        final etuHeader = package.sublist(0, 64);
        final packageSha256 = packageDigest.bytes;

        if (diagnostics.enabled) {
          diagnosticStarted = await diagnostics.beginUpgrade({
            'packageSha256': packageDigest.toString(),
            'packageBytes': package.length,
            'currentVersionCode': info.currentVersionCode,
            'currentImageSha256': info.currentImageSha256Hex,
            'targetVersionCode': _latestInfo?.versionCode,
            'targetImageSha256': _latestInfo?.targetImageSha256,
            'deviceAddress': deviceAddress,
            'appLifecycle': WidgetsBinding.instance.lifecycleState?.name ?? 'unknown',
          });
          if (generation != _cancelGeneration) {
            return fail('cancelled', 'generation-changed');
          }
          if (!diagnosticStarted) {
            _phase.value = OtaPhase.failed;
            _upgradeStatus.value = '诊断记录未就绪，未开始 BLE 传输；请先检查记录状态';
            return fail('observation', 'capture-not-ready');
          }
        }

        // P3-4 观测：绑定阶段自严格发现起（对齐 research §3.1「绑定 =
        // 发现 + MTU + 订阅」：发现耗时属于阶段内，不是阶段前）。外壳记录
        // 耗时/成败/写模式，内部服务发现另行计时——stats 必须透传，否则
        // 发现计数与写模式都采不到。
        linkStats.phaseStart('bind');
        final otaChars = await _ble.findExactOtaCharacteristicsByAddress(
          deviceAddress,
          stats: linkStats,
        );
        if (generation != _cancelGeneration) {
          return fail('cancelled', 'generation-changed');
        }
        if (otaChars == null) {
          _upgradeStatus.value = '设备未暴露 OTA 服务（FFF0/FFF2/FFF1）';
          _phase.value = OtaPhase.failed;
          return fail('discover', 'ota-chars-missing');
        }
        // P3-4 观测：绑定阶段终点 = 订阅流就绪（MTU 协商 + 通知订阅完成）。
        final transport = await _bindTransport(deviceAddress, otaChars,
            stats: linkStats);
        linkStats.phaseEnd('bind');
        if (generation != _cancelGeneration) {
          // RC3-04⑤：迟到完成的 bind 产物无人接管——transport 与其订阅
          // 不释放会悬挂占用通知通道（PR10 一个连接代次仅一个订阅，
          // 残留订阅会顶掉下一次绑定的流）。释放后静默退出，对齐
          // readDeviceInfo 的同型分支。
          await transport?.dispose();
          if (transport != null && identical(_transport, transport)) {
            _transport = null;
          }
          return fail('cancelled', 'generation-changed');
        }
        if (transport == null) {
          _upgradeStatus.value = 'OTA 通知订阅失败';
          _phase.value = OtaPhase.failed;
          return fail('bind', 'notify-subscribe-failed');
        }
        activeTransport = transport;
        // 重连身份复核：当前 INFO 必须与会话开始时快照一致。
        final recheck = await transport.getDeviceInfo();
        if (generation != _cancelGeneration) {
          return fail('cancelled', 'generation-changed');
        }
        if (!deviceIdentityMatches(recheck, info)) {
          _terminalState.value = OtaTerminalState(
            code: 'DEVICE_IDENTITY_CHANGED',
            message: '设备身份与升级会话开始时不一致，已终止',
          );
          _upgradeStatus.value = '设备身份复核失败';
          _phase.value = OtaPhase.failed;
          return fail('recheck', 'device-identity-changed');
        }
        if (diagnostics.enabled) {
          emitOtaObservation('OTA_IDENTITY ${jsonEncode({
            'phase': 'pre-transfer',
            'versionCode': recheck.currentVersionCode,
            'imageSha256': recheck.currentImageSha256Hex,
            'deviceAddress': deviceAddress,
          })}');
        }

        // ETU 包字节与身份已在上锁后就地校验（RC2-04）。

        _upgradeStatus.value = 'BLE 传输中...';
        final ack = await transport.transfer(
          package: package,
          packageSha256: packageSha256,
          etuHeader: etuHeader,
          // INFO.max_window_segs 消费：在途段上限（PR04 附带）。
          windowSegments: recheck.maxWindowSegments,
          onDurableProgress: (durableOff, total) {
            final p = total > 0 ? (durableOff / total).clamp(0.0, 1.0) : 0.0;
            _durableProgress.value = p;
            _upgradeProgress.value = p;
            _upgradeStatus.value =
                '传输中: ${_formatBytes(durableOff)}/${_formatBytes(total)}（MCU 落盘确认）';
          },
          onSent: (sent, total) {
            // GATT 已写字节只作为传输活性参考，不进 durable 进度。
            debugPrint('OTA sent $sent/$total');
          },
        );
        // P3-4 观测：传输终态已定（transport finally 已记录 outcome），但
        // 摘要必须等到下面两个**立即失败分支**登记完失败元数据之后再落：
        // 它们调用的 fail() 会记录阶段/原因，而 emitSummary 幂等（仅首次
        // 生效），finally 的第二次调用不再输出——先封存会让非 OK END 与
        // 取消路径的失败原因永远进不了原始日志（P34-DA02）。
        if (generation != _cancelGeneration) {
          return fail('cancelled', 'generation-changed');
        }
        if (!ack.isOk) {
          final terminal = OtaTerminalState(
            code: 'MCU_ACK_${ack.status.toRadixString(16).toUpperCase()}',
            message: 'MCU 返回失败状态 0x${ack.status.toRadixString(16)}，'
                'durable=${ack.durableOff}',
            retryableLater: !OtaBleCodec.abortStatuses.contains(ack.status),
          );
          _terminalState.value = terminal;
          _upgradeStatus.value = '升级失败: ${terminal.code}';
          _phase.value = OtaPhase.failed;
          return fail('transfer', 'mcu-ack-0x${ack.status.toRadixString(16)}');
        }
        // P3-4 观测：传输终态与失败元数据都已就位，落一份摘要——后续重启
        // 等待可能长达整个复核窗口，终态摘要不应等到那时。幂等：末尾
        // finally 的收尾摘要不会重复输出，整轮仍只有一条 OTA_LINK_STATS。
        linkStats.emitSummary();
        // ---- END OK 只是包传完（PR07）----
        _durableProgress.value = 1.0;
        _upgradeProgress.value = 1.0;
        _phase.value = OtaPhase.waitingReboot;
        _upgradeStatus.value = '升级包传输完成，等待设备重启...';
        await activeTransport.dispose();
        activeTransport = null;
        _transport = null;

        // 等待设备重启并复核目标身份（RC3-08②：三态判定，旧身份不误判）。
        final latest = _latestInfo;
        if (latest == null) {
          _terminalState.value = OtaTerminalState(
            code: 'TARGET_IDENTITY_MISMATCH',
            message: '固件清单缺失，无法复核升级结果',
            retryableLater: true,
          );
          _upgradeStatus.value = '目标身份复核失败（清单缺失）';
          _phase.value = OtaPhase.failed;
          return fail('manifest', 'manifest-missing');
        }
        final outcome = await _waitForTargetIdentity(
          deviceAddress,
          info,
          latest,
          generation,
        );
        if (generation != _cancelGeneration) {
          return fail('cancelled', 'generation-changed');
        }
        switch (outcome.kind) {
          case _RebootKind.targetVerified:
            // 终点观测（补测轮取证）：复核链在新连接上 GET_INFO 比对
            // 全等后唯一到达此分支——它是「原升级调用成功完成」的直接
            // 终态（与 timedOut 后手动查询互斥），此前无打点采不到证。
            otaMonoLog('MONO_REBOOT_VERIFIED');
            // 刷新本地快照为升级后身份。
            _deviceInfo = outcome.info;
            _deviceInfoAddress = deviceAddress;
            diagnosticCompleted = true;
            if (diagnostics.enabled) {
              emitOtaObservation('OTA_IDENTITY ${jsonEncode({
                'phase': 'post-reboot',
                'versionCode': outcome.info!.currentVersionCode,
                'imageSha256': outcome.info!.currentImageSha256Hex,
                'deviceAddress': deviceAddress,
              })}');
            }
            _phase.value = OtaPhase.completed;
            _upgradeStatus.value =
                '固件升级完成: 设备已运行 ${latest.versionName}（vcode ${latest.versionCode}）';
            return true;
          case _RebootKind.timedOut:
            _terminalState.value = OtaTerminalState(
              code: 'REBOOT_RECONNECT_FAILED',
              message: '设备未在 ${_rebootWindow.inSeconds} 秒复核窗口内'
                  '恢复连接确认目标固件——升级可能已完成（设备重启恢复'
                  '慢于窗口），请稍后重新连接设备确认版本',
              retryableLater: true,
            );
            _upgradeStatus.value = '等待设备重启复核超时'
                '（${_rebootWindow.inSeconds} 秒，升级可能已完成，可稍后'
                '重连确认）';
            _phase.value = OtaPhase.failed;
            return fail('reboot', 'reboot-reconnect-failed');
          case _RebootKind.identityChanged:
            _terminalState.value = OtaTerminalState(
              code: 'DEVICE_IDENTITY_CHANGED',
              message: '重启后设备硬件身份与会话开始时不一致，已终止',
            );
            _upgradeStatus.value = '重启后设备身份复核失败';
            _phase.value = OtaPhase.failed;
            return fail('reboot', 'device-identity-changed');
          case _RebootKind.cancelled:
            // 静默：状态由 cancelUpgrade 发布（观测仍留痕）。
            return fail('cancelled', 'reboot-wait-cancelled');
        }
      } on OtaTransportException catch (e) {
        if (e.code == 'DISCONNECTED') {
          // 断连使旧身份快照失效（PR09）：恢复须重新 GET_INFO。
          _deviceInfo = null;
          _deviceInfoAddress = null;
        }
        if (generation != _cancelGeneration) {
          // 用户取消窗口内的在途错误（RC3-12②）：不能只按 `e.code` 分流。
          // 取消时刻正在途的物理写可能以 WRITE_TIMEOUT 结束，也可能被
          // abortBestEffort / 原生层以任意异常抛出；这些都不是「升级失败」
          // 的新事实，而是取消造成的退出路径。此刻 cancelUpgrade 的清理
          // （partial / 已验证包）尚未跑完，若在这里发布失败文案并置
          // `_phase = failed`，「失败且已收尾」的可观测状态会先于清理成立——
          // UI 据此放开重试入口，随后取消路径又把 phase 覆盖成 cancelled，
          // 用户看到文案与相位来回跳，且可能对着还没删完的包重发。
          // 终止语义与包处置由 cancelUpgrade 在本 owner（含 finally）完全退出后
          // 一次性发布，这里静默让出，也不重复 ABORT——取消路径已对取消时刻的
          // transport 做过尽力 ABORT。
          return fail('cancelled', 'cancel-window');
        }
        if (_consumeFailClosedDecision()) {
          // 后台复核 failClosed 已决定终止（RC3-08/12②）：终止态发布时不
          // 前进代次，在途写在它之后以 WRITE_TIMEOUT/原生异常退出同样落在
          // 本分支。终止原因/可重试语义/收尾相位（cancelled）归属
          // failClosed 已发布的 [_terminalState]/[_upgradeStatus]，这里静默
          // 让出，也不重复 ABORT——failClosed 已尽力 ABORT 过。
          return fail('recheck', 'fail-closed');
        }
        if (e.code != 'CANCELLED') {
          // RC3-07/02 四阶段：此处是「中止决定」，终态发布要等 ABORT
          // 收尾完成后才打 MONO_TERMINAL——旧打点把决定提前宣告成终态，
          // 延迟 ABORT 期间的真机日志会被误读为「已终止」。
          otaMonoLog('MONO_TERMINAL_DECIDED', code: e.code);
          _upgradeStatus.value = 'BLE 传输失败: ${e.message}';
          // 连接仍在时尽力 ABORT（清理 MCU 侧会话）。
          final abortTransport = activeTransport;
          if (abortTransport != null) {
            otaMonoLog('MONO_ABORT_BEGIN', code: e.code);
            try {
              await abortTransport.abortBestEffort();
            } finally {
              otaMonoLog('MONO_ABORT_DONE', code: e.code);
            }
          }
          otaMonoLog('MONO_TERMINAL', code: e.code);
          // P3-4 观测：真实链路失败（非取消、非已决终止）留痕。
          linkStats.recordFailure(
              stage: 'transfer', reason: 'transport:${e.code}');
          _phase.value = OtaPhase.failed;
        } else {
          // 非取消来源的 CANCELLED：发送循环是被 abortBestEffort 停掉的
          // （例如后台复核失败 fail closed）。终止原因由发起中止的路径
          // （failClosed）发布到 _terminalState/_upgradeStatus，此处保持
          // 既有收尾语义为 cancelled：已验证包仍在本地、UI 据此保留重新
          // 发起传输入口（retryableLater 终止态正是「可重试续传」）。
          // 与下面的用户取消分支不同，这一支不存在「清理未完成」的窗口——
          // 本路径不删任何资产。
          //
          // 文案不得在此无条件发布（RC3-12）：`e.message` 对 CANCELLED 恒为
          // 传输层的「OTA 传输已取消」，抢先写会把 failClosed 刚发布的
          // 「设备复核失败（后台恢复），升级已终止，可重试续传」覆盖成
          // 通用链路失败文案，丢掉终止原因与可重试语义。
          linkStats.recordFailure(
              stage: 'cancelled', reason: 'transport-cancelled');
          _phase.value = OtaPhase.cancelled;
        }
        // 本 catch 的两支都只在 `generation == _cancelGeneration`（本 owner
        // 仍是当前 owner）时发布：用户取消窗口已在上面统一让出。
        return false;
      } on OtaDeviceIdentityException catch (e) {
        if (generation != _cancelGeneration) {
          // 与上面同一条取消窗口让出规则（RC3-12②），也与重启复核的
          // `_RebootKind.identityChanged` 分支保持一致——那条路径在发布前
          // 已做 `generation != _cancelGeneration` 前置判定，本 catch 若不
          // 判定就是同一语义的两个出口行为不一致。且 `_terminalState` 不被
          // cancelUpgrade 重置：取消后由迟到身份异常写入的 DEVICE_IDENTITY_*
          // 会一直挂在 phase=cancelled 旁边，UI 展示自相矛盾的终止原因。
          return fail('cancelled', 'cancel-window');
        }
        if (_consumeFailClosedDecision()) {
          // 同 typed catch（RC3-08/12②）：failClosed 已决终止不得被迟到的
          // 身份异常覆盖成 DEVICE_IDENTITY_* + failed。
          return fail('recheck', 'fail-closed');
        }
        // RC3-07/02：身份异常路径无在途业务写（GET_INFO 期间不发
        // DATA/END），没有 ABORT 收尾段——决定即终态，两事件同点落盘。
        otaMonoLog('MONO_TERMINAL_DECIDED', code: e.code);
        otaMonoLog('MONO_TERMINAL', code: e.code);
        // P3-4 观测：身份异常多发生在传输前的 GET_INFO 复核，留痕后由
        // finally 统一输出终结摘要。
        linkStats.recordFailure(stage: 'recheck', reason: 'identity:${e.code}');
        _terminalState.value = OtaTerminalState(
          code: e.code,
          message: e.toString(),
        );
        _upgradeStatus.value = '设备身份识别失败: ${e.code}';
        _phase.value = OtaPhase.failed;
        return false;
      } catch (e) {
        if (generation != _cancelGeneration) {
          // 原生/未知异常同样不得抢在取消清理前发布失败态（RC3-12②）：
          // 取消引发的在途写异常会走这一支，发布职责归属 cancelUpgrade。
          return fail('cancelled', 'cancel-window');
        }
        if (_consumeFailClosedDecision()) {
          // 同 typed catch（RC3-08/12②）：failClosed 之后在途写以原生异常
          // 退出走这一支，不得覆盖 failClosed 已发布的终止态。
          return fail('recheck', 'fail-closed');
        }
        // RC3-07/02 四阶段：同 typed catch——决定、ABORT 收尾、终态发布
        // 分开打点，未知异常的收尾时长同样可观测。
        otaMonoLog('MONO_TERMINAL_DECIDED', code: 'UNKNOWN');
        // P3-4 观测：未知异常留痕（含异常文本），由 finally 统一输出摘要。
        linkStats.recordFailure(stage: 'unknown', reason: '$e');
        _upgradeStatus.value = '升级失败: $e';
        final abortTransport = activeTransport;
        if (abortTransport != null) {
          otaMonoLog('MONO_ABORT_BEGIN', code: 'UNKNOWN');
          try {
            await abortTransport.abortBestEffort();
          } finally {
            otaMonoLog('MONO_ABORT_DONE', code: 'UNKNOWN');
          }
        }
        otaMonoLog('MONO_TERMINAL', code: 'UNKNOWN');
        _phase.value = OtaPhase.failed;
        return false;
      } finally {
        // P3-4 观测：本实例的一切退出路径（全部早退、取消、三类异常、
        // 成功）都在此落终结摘要——早退路径的失败阶段/原因由上面的
        // fail()/recordFailure 留下，未进入传输的失败不伪装成成功传输。
        // 传输终态兜底（P34-R05）：未进入传输就退出的轮次（特征缺失、绑定
        // 失败、取消、异常）此前没有终态，消费者只看 transfer.outcome 时
        // 会把整轮失败读成"没发生过传输"。本方法幂等，且唯一返回 true 的
        // 路径在 END ACK 采信点之后、已由 transport 登记 'ok'，因此兜底
        // 不会改写成功轮次；是否真的开始过传输由 startUs/elapsedUs 是否
        // 为空区分。
        linkStats.recordTransferOutcome(ok: false);
        // emitSummary 幂等：已提前输出过的路径不会重复。
        linkStats.emitSummary();
        if (diagnosticStarted) {
          await diagnostics.finishUpgrade(completed: diagnosticCompleted);
        }
      }
    }) ?? false;
  }

  /// 消费一次 failClosed 已决终止（RC3-08/12②）。代次未变但在途写在
  /// failClosed 之后以非 CANCELLED 错误退出时，三个 catch 分支都必须
  /// 认出这是「已决终止的收尾」而非新的升级失败：终止原因/可重试语义
  /// 已由 failClosed 发布到 [_terminalState]/[_upgradeStatus]，收尾相位
  /// 统一为 cancelled（与 CANCELLED 分支一致——已验证包仍在本地、UI 据此
  /// 保留重试续传入口）。返回 true 表示调用方应静默让出。
  bool _consumeFailClosedDecision() {
    if (!_failClosedDecided) return false;
    _failClosedDecided = false;
    _phase.value = OtaPhase.cancelled;
    return true;
  }

  /// 取消升级（分层归责，PR08；RC3-04/05① 收紧）：
  /// - 递增取消代次（在途操作发现即静默退出）；
  /// - HTTP 在途 → cancel token；`.part` 与 sidecar **恒删**
  ///   （keepPartial:false，冻结取消策略不放宽——partial 包没有完成
  ///   过整包校验，续传语义由 MCU durable 层承担，App 侧半包不参与）；
  /// - BLE 在途 → transport.cancel() 停止发送循环 + 尽力 ABORT
  ///   （MCU durable 落盘字节天然保留，可续传）；
  /// - 等待在途 owner（含其 finally）完全退出后才发布 cancelled，
  ///   防止旧 owner 晚到的进度/失败发布覆盖取消终态；等待绑定取消
  ///   时刻的 owner 快照，不追等快照之后新登记的 owner（RC3-04⑤：取消
  ///   不得等待并处置后来者）；
  /// - [keepPackage] 只决定**已校验完成包**（_firmwareFile/_verified）
  ///   的去留：false 时一并删除。
  Future<void> cancelUpgrade({bool keepPackage = false}) async {
    _cancelGeneration++;
    // RC3-04⑤：代次自增后**同步**快照当前 owner 与 owner 代数，之后的
    // 等待只认这份快照。若等 await 时才读 _ownerDone，旧 owner 退出与新
    // owner 登记之间没有间隙屏障——取消会等到新 owner 退出、再删新操作
    // 刚建立的包并覆盖其终态，取消变成对后来者的破坏。快照 owner 退出后
    // 登记的新 owner 属于新操作，不由本取消等待或处置。
    // ownerEpoch（RC3-04⑤）：_runExclusive 每次登记自增。仅靠
    // 「_ownerDone == null」无法识别「进入又结束的后来 owner」——等待
    // 期间新 owner 跑完全程后 _ownerDone 回到 null，删包与终态发布会
    // 作用于新 owner 已结束的状态、覆盖其终态。结尾以「epoch 未前进」
    // 识别整个取消窗口内没有任何后来者进出。
    final ownerAtCancel = _ownerDone;
    final epochAtCancel = _ownerEpoch;
    // RC3-04：在途 latest 请求立即中断（不等待其自然超时）。
    _activeLatestToken?.cancel();
    // 先直接取消持有令牌（覆盖 OtaFirmwareDownload 内部注册前的
    // 极早期取消窗口），再走其自身的取消/清理路径。
    _activeDownloadToken?.cancel();
    // RC3-04⑤：下载资源快照同样在首个 await 前同步读取——ABORT 等待
    // 期间新 owner 进入并建立自己的 _asset/_download 时，本取消不得
    // 删新 owner 的 partial 文件（快照的是取消时刻的在途下载）。
    final assetId = _asset?.assetId;
    final download = _download;
    // RC3-05：先停 BLE 传输（发送循环停止、尽力 ABORT），再停下载——
    // 下载清理会等待在途请求退出，传输先停可避免等待期间仍在发送
    // 数据段。
    final transport = _transport;
    if (transport != null && !transport.isCancelled) {
      // RC3-07/02 四阶段：用户取消路径同样区分决定/收尾——取消的
      // 「决定」是用户动作（无对应日志事件），这里只标记停止业务写
      // 与 ABORT 收尾两段；终态发布（cancelled）在函数尾部。
      otaMonoLog('MONO_ABORT_BEGIN', code: 'USER_CANCEL');
      try {
        await transport.abortBestEffort();
      } finally {
        otaMonoLog('MONO_ABORT_DONE', code: 'USER_CANCEL');
      }
    }
    // epoch 屏障（RC3-04⑦）：ABORT 等待期间可能有新 owner 登记并重新
    // 下载**同一资产**。两次 attempt 的 assetId、文件名与 `.part` 路径
    // 必然相同（续传语义要求复用同一 `.part`），对快照 download 调
    // cancel(keepPartial:false) 最终会落到同一个文件路径上——旧取消会
    // 把后来者正在写的 partial 连根拔掉。
    //
    // 注意取消资源**不是**「按 assetId 共享的同一张表」：每次
    // `_downloadOnce` 都 new 一个新的 [OtaFirmwareDownload]，实例内的
    // `_cancelTokens`/`_inFlight` 各归各，不存在被新 attempt 覆盖一说；
    // 跨 attempt 真正共享的是文件路径、文件名、assetId（以及串行闸）。
    // 旧在途下载在本函数首个 await 之前已由 `_activeDownloadToken.cancel()`
    // 中止，其自身退出路径会按取消语义处置字节，跳过这次清理不留在途写入方。
    final ownerTookOver = _ownerEpoch != epochAtCancel;
    if (assetId != null && download != null && !ownerTookOver) {
      try {
        await download.cancel(assetId, keepPartial: false);
      } catch (e) {
        // RC3-05：partial 清理失败不吞——继续取消流程，失败事实经
        // 通知暴露，不静默当作已清理。
        _notify('提示', '操作已取消，但本地临时文件清理失败: $e');
      }
    }
    // 等待在途 owner 完全退出（含其 finally 清理）——只等取消时刻的
    // 快照（RC3-04⑤）。
    if (ownerAtCancel != null) {
      await ownerAtCancel;
    }
    // 慢退出兜底清理（RC3-05⑤）：取消时在途下载在 5s 上限内没退出，
    // 下载层当时不做删除（可能仍有写盘方），改为登记延后清理。此处 owner
    // 已退出（下载只在本 owner 锁内发起，owner 退出即在途已结算），await
    // 它把删除真正做完；否则用户看到「已取消」而 partial 要留到 24h 兜底
    // 才清。归属判定仍在删除边界内复核，新 attempt 接管同一资产时不删。
    final deferredCleanup = download?.pendingCancelCleanup;
    if (deferredCleanup != null) {
      try {
        await deferredCleanup;
      } catch (e) {
        // 与即时清理同一处置：失败不吞，经通知暴露。
        _notify('提示', '操作已取消，但本地临时文件清理失败: $e');
      }
    }
    // 删除已验证包（RC3-12）：纳入 owner 串行——防止删除与并发新操作
    // （如取消后立刻开始的传输，就地读包）竞争同一文件；新操作已抢入
    // 时 _runExclusive 拒绝并让位，不删新操作正用的包（RC3-04）。
    // epoch 屏障（RC3-04⑤）：仅当取消窗口内没有后来 owner 进出时才
    // 删包——后来的新操作可能刚建立自己的包，删它属于越权处置。
    String? cleanupFailure;
    var cleanupRan = false; // 自己的删包 owner 也会登记（epoch +1）
    if (!keepPackage &&
        _firmwareFile != null &&
        _ownerEpoch == epochAtCancel &&
        _ownerDone == null) {
      await _runExclusive<void>((_) async {
        cleanupRan = true;
        final file = _firmwareFile;
        if (file == null) return;
        try {
          if (await file.exists()) {
            await file.delete();
          }
          _firmwareFile = null;
          _verified = null;
        } catch (e) {
          // 删除失败不吞错：保留文件与已校验标记，状态消息说明包
          // 仍在，传输入口保持可用（下次清理重试）。
          cleanupFailure = '固件包清理失败: $e';
        }
      });
    }
    // 发布前防新 owner 竞态：等待期间若有新入口抢入（_ownerDone 重新
    // 登记，或后来者已跑完整个流程退出——epoch 前进而 _ownerDone 回到
    // null），取消状态让位给新操作的进度/终态展示；否则发布取消终态。
    // phase 与 status 在同一同步段赋值（RC3-12）：Obx 重建时文件状态
    // 与 phase/Rx 一致，不会出现 cancelled 已显示、包随后才删的中间态。
    final expectedEpoch = epochAtCancel + (cleanupRan ? 1 : 0);
    if (_ownerEpoch == expectedEpoch && _ownerDone == null) {
      _upgradeStatus.value = cleanupFailure != null
          ? '操作已取消（$cleanupFailure，固件包已保留）'
          : '操作已取消';
      _phase.value = OtaPhase.cancelled;
      // RC3-07/02 四阶段：取消路径的真正终态发布——在 ABORT 收尾、
      // 下载清理与删包全部完成后才打。
      otaMonoLog('MONO_TERMINAL', code: 'USER_CANCEL');
    }
  }

  /// App 进入后台（RC3-08）：暂停传输发送循环——后台继续发 DATA/END
  /// 会与系统资源回收（BLE 栈挂起、进程冻结）竞争；暂停期间无进展
  /// 预算停表，不消耗 30s 总预算。注意：暂停超过 MCU 会话超时窗口时
  /// MCU 可能回 ACK_ABORT（协议行为）；回前台后传输失败可整体重试
  /// （BEGIN 幂等 + durable 续传）。
  void pauseForBackground() {
    _transport?.pauseForBackground();
  }

  /// App 回前台（RC3-08）：恢复传输发送循环与无进展预算计时。
  ///
  /// RC3-08⑤：恢复发送**前**先复核设备——后台期间设备可能被更换
  /// （系统断开旧连接、重连到别的设备），对变更后的设备继续发 DATA
  /// 会把旧包字节写进新设备。任一复核不通过或复核本身失败都 fail
  /// closed：置终止态并尽力 ABORT、不恢复发送。复核期间传输保持暂停
  /// （先探测后 resume，见函数尾）。
  ///
  /// RC3-08⑦ 三级复核，缺一不可：
  /// 1. **物理链路代次**：BluetoothService 观测到的 connect/disconnect
  ///    迁移。代次变了说明绑定时那条链路已不在，即使地址、身份字段
  ///    全同也可能是新链路（同型号另一台设备同样匹配身份字段）；
  /// 2. **重新发现**：链路重建后 GATT 句柄/特征可能整体变化，旧
  ///    serviceId/charId 写下去不再指向 OTA 通道。重新发现结果必须与
  ///    绑定时完全一致；
  /// 3. **INFO 身份**：仍按会话开始快照逐字段比对。
  ///
  /// RC3-04⑦ 迟到发布屏障：三级复核都要 await，期间用户可能取消并
  /// 开始新一轮（新 owner、新 transport）。每个 await 之后都要确认
  /// 「取消代次未变且全局 transport 仍是本次快照」，否则静默退出——
  /// 迟到的复核结论属于已结束的旧会话，发布它会用旧终止态覆盖新
  /// owner 的进度/终态。
  Future<void> resumeFromBackground() async {
    final transport = _transport;
    if (transport == null) return;
    final sessionInfo = _deviceInfo;
    if (sessionInfo == null) {
      transport.resumeFromBackground();
      return;
    }
    final generation = _cancelGeneration;
    // 快照绑定现场：resume 期间 _bindTransport 可能被新 owner 调用并
    // 覆盖这三项，因此比对基准必须在首个 await 前取。
    final address = _boundAddress;
    final boundChars = _boundChars;
    final boundLink = _boundLinkGeneration;
    bool stale() =>
        generation != _cancelGeneration || !identical(_transport, transport);

    Future<void> failClosed(String code, String message,
        {bool retryableLater = false}) async {
      if (stale()) return;
      // 记录「终止已决」供本 owner 的 catch 消费（RC3-08/12②）：failClosed
      // 不前进代次，在途写随后以非 CANCELLED 错误退出时必须认出这是已决
      // 终止的收尾，而不是新的升级失败。
      _failClosedDecided = true;
      // RC3-07/02 四阶段：failClosed 的「中止决定」。这里发布终止态是
      // 决策本身（状态字段），物理收尾（ABORT）在其后；真正的
      // MONO_TERMINAL 在 ABORT 完成后打——旧打点与状态发布同时落，
      // 把「已决」混同「已收尾」。
      otaMonoLog('MONO_TERMINAL_DECIDED', code: code);
      _terminalState.value = OtaTerminalState(
        code: code,
        message: message,
        retryableLater: retryableLater,
      );
      _upgradeStatus.value = retryableLater
          ? '设备复核失败（后台恢复），升级已终止，可重试续传'
          : '设备复核失败（后台恢复），升级已终止';
      _notify('错误', _terminalState.value!.userMessage);
      // RC3-07/02 四阶段：failClosed 的 ABORT 收尾与终态发布分开打点。
      // abortBestEffort 尽力而为（断连静默失败），收尾时长由
      // MONO_ABORT_BEGIN→MONO_ABORT_DONE 之差可观测。
      otaMonoLog('MONO_ABORT_BEGIN', code: code);
      try {
        await transport.abortBestEffort();
      } finally {
        otaMonoLog('MONO_ABORT_DONE', code: code);
      }
      otaMonoLog('MONO_TERMINAL', code: code);
    }

    if (address == null || boundChars == null || boundLink == null) {
      // 无绑定现场即无法证明链路未变（fail closed）：正常路径下
      // _bindTransport 必然写入三项，缺失说明 transport 来源不可核。
      await failClosed(
        'DEVICE_RECHECK_FAILED',
        '后台恢复时缺少连接绑定信息，无法确认链路未变更，已终止升级',
        retryableLater: true,
      );
      return;
    }
    // 非空副本供下面的闭包使用（闭包内不做可空判定）。
    final boundAddress = address;
    final boundLinkGen = boundLink;

    /// await 之后的统一复核（RC3-08⑦）。
    ///
    /// 链路代次会因平台上报的断开在**任意两个 await 之间**前进：只在入口
    /// 同步读一次，挡不住「后台期间断开又重连」正好落在 await 期间——
    /// 旧会话会继续在绑定于旧链路的 transport 上发送字节，正是本节要防的
    /// 情形。返回 true 表示本会话不得继续，且两种原因必须区别处置：
    /// - 已被取消 / 被新 owner 接管：静默退出。取消方已发布自己的终态，
    ///   旧会话再写一次就是用旧结论覆盖新 owner 的状态；
    /// - 链路已变更：必须由本会话发布终止态，没有别人替它发布。
    Future<bool> aborted() async {
      if (stale()) return true;
      final currentLink = _ble.otaLinkGeneration(boundAddress);
      if (currentLink == boundLinkGen) return false;
      await failClosed(
        'DEVICE_LINK_CHANGED',
        '后台恢复期间蓝牙链路已变更（链路代次 $boundLinkGen→$currentLink），'
            '无法确认仍是同一条连接，已终止升级',
        retryableLater: true,
      );
      return true;
    }

    // 1. 物理链路代次。
    if (await aborted()) return;

    // 2. 重新发现 OTA 特征（有界）。
    Map<String, String>? rediscovered;
    try {
      rediscovered = await _ble
          .findExactOtaCharacteristicsByAddress(boundAddress)
          .timeout(const Duration(seconds: 5));
    } catch (e) {
      if (await aborted()) return;
      await failClosed(
        'DEVICE_RECHECK_FAILED',
        '后台恢复时重新发现 OTA 服务失败（$e），已终止升级',
        retryableLater: true,
      );
      return;
    }
    if (await aborted()) return;
    if (rediscovered == null || !_charsMatch(rediscovered, boundChars)) {
      await failClosed(
        'DEVICE_LINK_CHANGED',
        '后台恢复时 OTA 服务/特征与绑定时不一致，已终止升级',
        retryableLater: true,
      );
      return;
    }

    // 3. INFO 身份。
    try {
      final current = await transport.getDeviceInfo(
          timeout: const Duration(seconds: 3));
      if (await aborted()) return;
      if (!deviceIdentityMatches(current, sessionInfo)) {
        await failClosed(
          'DEVICE_IDENTITY_CHANGED',
          '后台恢复时设备身份与会话开始时不一致，已终止升级',
        );
        return;
      }
    } catch (e) {
      // RC3-08⑤：复核失败 fail closed——读取不到当前身份就无法确认
      // 后台期间设备未被更换（系统断开旧连接后可能重连到别的设备），
      // 继续发送会把旧包字节写进未知设备。置终止态并尽力 ABORT 停止
      // 发送循环；MCU durable 层保留已落盘字节，重试经 BEGIN 幂等 +
      // durable 续传恢复，不依赖本会话续发。
      if (await aborted()) return;
      await failClosed(
        'DEVICE_RECHECK_FAILED',
        '后台恢复时无法复核设备身份（$e），已终止升级',
        retryableLater: true,
      );
      return;
    }
    // 复核期间被取消/被新 owner 接管时不得恢复旧发送循环。
    if (await aborted()) return;
    transport.resumeFromBackground();
  }

  /// 重新发现结果是否与绑定时完全一致（RC3-08⑦）。
  ///
  /// 逐键全等（含 writeMode）：写模式变化意味着写入语义变了，同样
  /// 不能沿用旧通道继续发。
  bool _charsMatch(Map<String, String> a, Map<String, String> b) {
    if (a.length != b.length) return false;
    for (final entry in a.entries) {
      if (b[entry.key] != entry.value) return false;
    }
    return true;
  }

  /// 清理已下载固件包（RC3-12①）。
  ///
  /// - 忙碌拒绝：升级/下载在途时不得清包（直接返回 false 提示）；
  /// - 严格删除不吞错：删除抛异常时返回 false 并保留文件引用，由
  ///   UI 向用户暴露失败，不得静默当作已清理；
  /// - 状态转换：readyToInstall 清理后回 idle 并复位进度条。
  Future<bool> cleanupFirmware() async {
    if (_isUpgrading.value) {
      _notify('提示', '升级进行中，无法清理固件包，请先取消');
      return false;
    }
    // RC3-12①：纳入 owner 串行——不再只在入口检查一次 busy：入口
    // 检查通过后、删除完成前的新入口（下载/传输）会被 _runExclusive
    // 拒绝，防止删除与就地读包的传输竞争同一文件。
    final result = await _runExclusive<bool>((_) async {
      final file = _firmwareFile;
      var ok = true;
      if (file != null) {
        try {
          if (await file.exists()) {
            await file.delete();
          }
        } catch (e) {
          debugPrint('清理固件包失败: $e');
          ok = false;
        }
      }
      if (ok) {
        _firmwareFile = null;
        _verified = null;
        if (_phase.value == OtaPhase.readyToInstall) {
          _phase.value = OtaPhase.idle;
          _upgradeProgress.value = 0.0;
          _downloadProgress.value = 0.0;
          _upgradeStatus.value = '固件包已清理';
        }
      }
      return ok;
    });
    return result ?? false;
  }

  List<Map<String, dynamic>> getUpgradeHistory() {
    return const [];
  }

  // ---- 内部 ----

  /// 入口互斥执行器（RC3-04）：所有会发起在途操作的最新检查/下载/
  /// 读身份/升级入口，都必须在首个 await 前经此取得 owner 身份。
  ///
  /// - 二重入口：第二个调用直接拒绝（null），不排队——排队会让用户
  ///   的「取消后再检查」变成先重放旧请求再执行新请求；
  /// - 串行等待：取得 owner 前先 `await previous`，确保上一个 owner
  ///   （含其 finally 的 transport/订阅清理）完全退出后才进入 body；
  /// - 取消代次同步锚定：登记 owner 的同一同步段读取代次并传给
  ///   body。此后任何 [cancelUpgrade]（递增代次）都使 body 的代次
  ///   失配而静默退出——覆盖「owner 已登记但 body 尚未启动」的
  ///   注册前取消窗口，取消后的操作不会把成功状态发布成已取消；
  /// - finally 只释放自身：`identical` 检查保证不会把后来者登记的
  ///   `_ownerDone` 误清；取消路径由此保证旧 owner 退出后
  ///   [cancelUpgrade] 才发布 cancelled 状态，避免晚到的旧状态
  ///   覆盖取消终态。
  Future<T?> _runExclusive<T>(Future<T?> Function(int generation) body) async {
    if (_isUpgrading.value) {
      _notify('提示', '操作进行中，请先取消或等待完成');
      return null;
    }
    _isUpgrading.value = true;
    final done = Completer<void>();
    final previous = _ownerDone;
    final generation = _cancelGeneration;
    _ownerEpoch++; // 登记即前进（RC3-04⑤）：取消窗口用它识别后来者
    _ownerDone = done.future;
    try {
      await previous;
      // RC3-04：排队等待期间被取消（代次已变）则不进入 body——禁止
      // 执行已被取消的操作（如恢复下载 body 前不查取消导致取消后又
      // 发起请求）。
      if (generation != _cancelGeneration) return null;
      return await body(generation);
    } finally {
      if (!done.isCompleted) done.complete();
      if (identical(_ownerDone, done.future)) {
        _ownerDone = null;
        _isUpgrading.value = false;
      }
    }
  }

  /// 终止态闭锁（PR11）：非 retryableLater 的终止态下拒绝一切
  /// latest/下载/传输入口；只有重新 [readDeviceInfo] 成功才解锁。
  /// 返回非 null 即为拒绝原因文案。
  String? _terminalLocked() {
    final terminal = _terminalState.value;
    if (terminal == null || terminal.retryableLater) return null;
    return '已进入终止状态（${terminal.code}）：重新连接设备完成身份识别后可重试';
  }

  /// 清单变化使旧下载包失效（PR12）。
  void _invalidatePackageIfChanged(FirmwareLatestInfo latest) {
    final verified = _verified;
    if (verified == null) return;
    final asset = latest.asset;
    if (asset == null ||
        asset.assetId != verified.assetId ||
        latest.releaseId != verified.releaseId ||
        asset.sha256 != verified.sha256 ||
        asset.sizeBytes != verified.sizeBytes ||
        latest.versionCode != verified.versionCode) {
      _verified = null;
      _firmwareFile = null;
    }
  }

  /// 等待设备重启并复核目标身份（RC3-08②：三态判定）。
  ///
  /// 1. 先按地址**主动断开**旧连接：设备重启前协议栈可能仍报告已
  ///    连接，旧连接上会读到重启前的 INFO/通知（假身份复核）；
  /// 2. 以总截止窗口（O4 整改后 180s，实测设备复位→BLE 可连接 ≥97s）
  ///    轮询 connect + 发现精确特征 + 绑定 transport + GET_INFO
  ///    三态判定：
  ///    - 目标身份（vcode 与 raw image SHA 等于清单目标）→
  ///      targetVerified；
  ///    - 旧身份（等于会话开始快照）：MCU 尚未重启完成，丢弃本轮
  ///      连接继续等——**不得把重启后的第一次可连接误当已重启**；
  ///    - 硬件身份变化（非同一台设备）→ identityChanged 终止。
  ///    vcode/sha 非目标也非旧身份的中间态按「未重启完成」继续等待，
  ///    由总截止兜底为 REBOOT_RECONNECT_FAILED（可稍后重试）。
  /// 取消代次变化立即静默退出（cancelled）。
  Future<_RebootOutcome> _waitForTargetIdentity(
    String deviceAddress,
    DeviceOtaInfo sessionInfo,
    FirmwareLatestInfo latest,
    int generation,
  ) async {
    // P3-4 链路观测：重启等待分两级实例（与升级传输的 upgrade 实例时间戳
    // 不相减）——roundStats 是整个重连等待的轮次外壳（reconnect 阶段起止 +
    // 总体结论），每轮连接尝试另有独立实例（见循环内）。所有返回路径统一
    // 记录结论并输出聚合摘要（幂等）。
    final roundStats = OtaLinkStats(label: 'probe', device: deviceAddress);
    roundStats.phaseStart('reconnect');
    // RC3-08⑤：截止先于主动断开建立——断开本身可能耗时（等协议栈状态
    // 迁移），总预算必须覆盖断开与全部轮询，不得从断开完成后才开始
    // 计费（否则断开耗时会无声挤占重启等待窗口）。
    final deadline = DateTime.now().add(_rebootWindow);
    // RC3-08⑦：主动断开自身必须有界。disconnectOtaDeviceByAddress 是
    // 尽力平台调用（WinBle disconnect / flutter_blue_plus disconnect），
    // 协议栈异常或设备已在重启途中时可能永不 resolve——无界 await 会把
    // 「至多一个窗口必返回」的重启等待变成永久挂起：deadline 已建立却
    // 永远走不到检查它的循环，取消代次同样无人再读。超时不当失败处理：
    // 断开只是让 MCU 侧尽早释放旧连接，后续轮询本来就要重新 connect。
    await _ble
        .disconnectOtaDeviceByAddress(deviceAddress)
        .timeout(const Duration(seconds: 5), onTimeout: () {});
    var attemptNo = 0;
    while (DateTime.now().isBefore(deadline)) {
      if (generation != _cancelGeneration) {
        roundStats.recordAttemptOutcome('cancelled');
        roundStats.phaseEnd('reconnect');
        roundStats.emitSummary();
        return const _RebootOutcome(_RebootKind.cancelled);
      }
      // RC3-08：单轮探测链（connect/discover/bind/INFO）受剩余总预算与
      // 单轮上限（O4 整改 20s）双重封顶——正常成功轮（connect ≤10s +
      // discover/MTU/subscribe/INFO 数秒）不会触顶；任一环节挂死时至多
      // 吞掉单轮上限，后续轮仍有机会，不再一轮挂起耗尽全部剩余窗口
      // （O4 logcat 实测：第一轮 connect 抛错后后续轮挂起即吞掉 59s）。
      // 最小 1s 保证 timeout 参数恒为正，总等待至多越线 1s。
      // RC3-08⑤：外层超时同时置 abandoned 标志——probe 在每个 await 后
      // 检查并提前退出（onTimeout 返回 null 只是放弃等待，并不取消
      // probe 内部动作；无标志时迟到的 bind/GET_INFO 会继续占用平台
      // 订阅通道）。
      final remaining = deadline.difference(DateTime.now());
      final roundCap = remaining < _rebootProbeTimeout
          ? remaining
          : _rebootProbeTimeout;
      var probeAbandoned = false;
      bool probeAborted() =>
          probeAbandoned || generation != _cancelGeneration;
      _RebootOutcome? outcome;
      // P3-4 观测：本轮连接尝试独立成实例（attempt 从 1 起）。绑定阶段字段
      // （发现/MTU/订阅）幂等只记首次，共享实例会把首轮的失败值带进后续轮
      // 次的摘要；独立实例还使迟到完成的回调只落在自己的轮次上，且本轮摘要
      // 在本轮结论时定格（emitSummary 幂等，迟到写入不再改写已发布摘要）。
      attemptNo++;
      final attemptStats = OtaLinkStats(
        label: 'probe',
        device: deviceAddress,
        attempt: attemptNo,
      );
      attemptStats.phaseStart('probe_attempt');
      try {
        outcome = await _probeTargetIdentity(
          deviceAddress,
          sessionInfo,
          latest,
          probeAborted,
          stats: attemptStats,
        ).timeout(
          roundCap < const Duration(seconds: 1)
              ? const Duration(seconds: 1)
              : roundCap,
          onTimeout: () {
            probeAbandoned = true;
            return null;
          },
        );
      } catch (_) {
        // 重启期间连接/读取失败是预期路径，继续轮询。
      }
      // 单轮结论归一：取消代次变化时 probe 内部静默返回 null（与循环顶部的
      // 取消检查同一语义），不得记成「本轮没有结论」——取消是本 wait 的
      // 决定性事实，先于等待放弃判定。
      final cancelled = generation != _cancelGeneration;
      final attemptOutcome = outcome != null
          ? _rebootOutcomeName(outcome.kind)
          : cancelled
              ? 'cancelled'
              : (probeAbandoned ? 'abandoned' : 'no_verdict');
      // P3-4 观测：本轮没有等到结论即封存本实例的观测流。
      //
      // 外层 `.timeout` 只放弃等待，**不取消**在飞的平台发现/绑定调用：
      // 它们稍后恢复时仍会在本实例上产生样本行（discover / platform_write
      // 等），而本实例摘要已经/即将定格。届时这些迟到样本会落在**下一轮**
      // 尝试的摘要块内，被解析器按块内计数核对判为 STRAGGLER（"样本归属
      // 不明，不得进入任何数值池"）——下一轮的合法观测被降级，本轮的迟到
      // 观测又无从归属（P34-DA03）。封存后迟到观测改走 `OTA_LINK_LATE`
      // （带 label + attempt），归属明确、不被静默丢弃，也不进入任何
      // 数值池；本实例仍输出唯一终结摘要（含 `attempts[].outcome` 与
      // `retired`），封存不代替摘要。
      //
      // 取得结论的轮次（completed / identityChanged / timedOut）不封存：
      // 该路径上每个 await 都已返回、平台调用无在飞工作，观测流自然
      // 排空，样本行不会越过本轮摘要。
      if (outcome == null) {
        attemptStats.retire(
          reason: probeAbandoned
              ? 'outer-timeout'
              : (cancelled ? 'cancelled' : 'no-verdict'),
        );
      }
      attemptStats.recordAttemptOutcome(attemptOutcome);
      // P3-4 观测：轮次外壳逐轮汇总全部尝试结论（含「本轮未获判定」）。
      // 只在 outcome != null 时记，会让空转的轮次在整体摘要里消失——
      // 只看轮次摘要的消费者会把「探测 2 次」读成「只探测过 1 次」
      // （P34-R06）。序号即尝试序号，与每轮独立摘要的 n 一致。
      roundStats.recordAttemptOutcome(attemptOutcome);
      attemptStats.phaseEnd('probe_attempt');
      attemptStats.emitSummary();
      if (outcome != null) {
        roundStats.phaseEnd('reconnect');
        roundStats.emitSummary();
        return outcome;
      }
      // 轮询间隔同样受剩余预算封顶（RC3-08）：不足一个间隔时按剩余量
      // 等待，不越过截止线。
      final rest = deadline.difference(DateTime.now());
      if (rest > Duration.zero) {
        await Future<void>.delayed(
          rest < _rebootProbeInterval ? rest : _rebootProbeInterval,
        );
      }
    }
    roundStats.recordAttemptOutcome('timedOut');
    roundStats.phaseEnd('reconnect');
    roundStats.emitSummary();
    return const _RebootOutcome(_RebootKind.timedOut);
  }

  /// 轮次结论文本（P3-4 观测字段；取值稳定，已发布后勿改）。
  static String _rebootOutcomeName(_RebootKind kind) {
    switch (kind) {
      case _RebootKind.targetVerified:
        return 'completed';
      case _RebootKind.timedOut:
        return 'timedOut';
      case _RebootKind.identityChanged:
        return 'identityChanged';
      case _RebootKind.cancelled:
        return 'cancelled';
    }
  }

  /// 单轮重启探测（RC3-08 抽出）：connect → discover → bind → GET_INFO
  /// → 三态判定。返回 null 表示本轮未获判定（连接失败/未重启完成），
  /// 由调用方继续轮询；transport 的建立与释放在本函数内闭环。
  ///
  /// RC3-08⑤：[aborted]（外层剩余预算超时/取消代次变化）在每个 await
  /// 后检查——迟到完成的步骤立即放弃并走 finally 释放；probe 使用
  /// 独立绑定（[_bindProbeTransport]），不触碰全局 transport 与 phase
  /// 之外的状态，迟到完成不再误杀新 owner 登记的连接。
  Future<_RebootOutcome?> _probeTargetIdentity(
    String deviceAddress,
    DeviceOtaInfo sessionInfo,
    FirmwareLatestInfo latest,
    bool Function() aborted, {
    OtaLinkStats? stats,
  }) async {
    OtaBleTransport? probe;
    try {
      if (await _ble.connectOtaDeviceByAddress(deviceAddress)) {
        if (aborted()) return null;
        // P3-4 观测：本轮绑定阶段自严格发现起（与升级路径同一包含关系，
        // 对齐 research §3.1「绑定 = 发现 + MTU + 订阅」）。findExact 外壳
        // 记录耗时/成败/写模式，内部服务发现另行计时——stats 必须透传；
        // 发现失败时本阶段不闭合，「已开始未完成」如实保留。
        stats?.phaseStart('bind');
        final otaChars = await _ble.findExactOtaCharacteristicsByAddress(
          deviceAddress,
          stats: stats,
        );
        if (aborted()) return null;
        if (otaChars != null) {
          probe = await _bindProbeTransport(deviceAddress, otaChars, aborted,
              stats: stats);
          stats?.phaseEnd('bind');
          if (aborted()) return null;
          if (probe != null) {
            _phase.value = OtaPhase.reconnectVerify;
            final target = await probe.getDeviceInfo();
            if (aborted()) return null;
            if (!deviceHardwareMatches(target, sessionInfo)) {
              return const _RebootOutcome(_RebootKind.identityChanged);
            }
            if (target.currentVersionCode == latest.versionCode &&
                target.currentImageSha256Hex == latest.targetImageSha256) {
              // 目标身份确认：连接已不需要，身份交给主流程。
              return _RebootOutcome(_RebootKind.targetVerified, info: target);
            }
            // 旧身份/中间态：MCU 尚未重启完成，本轮连接由 finally
            // 统一释放后继续轮询。
          }
        }
      }
      return null;
    } finally {
      if (probe != null) {
        await probe.dispose();
      }
    }
  }

  /// probe 专用绑定（RC3-08⑤）：与 [_bindTransport] 建立同样的
  /// transport，但**不释放、不占用全局 _transport**——重启等待结束后
  /// 新 owner 可能已登记自己的 transport，迟到完成的 probe 若走全局
  /// 绑定路径会 dispose 新 owner 的连接。绑定失败时已建立的部分资源
  /// 在本函数内释放。
  ///
  /// [aborted] 在每个 await 之后复核（RC3-08⑦）：探测可能在 MTU 协商或
  /// 平台订阅期间被取代。订阅晚于新 owner 发起时，令牌机制已保证它拿不到
  /// 所有权（不会关掉新 owner 的共享 CCCD）；这里再保证不把已被取代的
  /// 探测结果交付出去——建立完成的 transport 当场释放，本地监听一并取消。
  Future<OtaBleTransport?> _bindProbeTransport(
    String deviceAddress,
    Map<String, String> otaChars,
    bool Function() aborted, {
    OtaLinkStats? stats,
  }) async {
    OtaBleTransport? transport;
    final linkGeneration = _ble.otaLinkGeneration(deviceAddress);
    final bindingToken = _ble.otaGattBindingToken(deviceAddress);
    bool linkCurrent() =>
        linkGeneration == _ble.otaLinkGeneration(deviceAddress) &&
        identical(bindingToken, _ble.otaGattBindingToken(deviceAddress));
    try {
      final mtuChunk =
          await _ble.requestOtaMtu(deviceAddress, stats: stats);
      if (aborted() || !linkCurrent()) return null;
      final serviceId = otaChars['serviceId']!;
      final writeId = otaChars['writeCharId']!;
      final notifyId = otaChars['notifyCharId']!;
      // 绑定 FFF2 实际支持的写模式（PR06）。
      final writeWithResponse = otaChars['writeMode'] != 'without';
      // 订阅就绪后才返回流（PR10），随后才允许发 GET_INFO。
      final notifyStream = await _ble.subscribeOtaNotifyByAddress(
        deviceAddress,
        serviceId,
        notifyId,
        stats: stats,
      );
      if (notifyStream == null) {
        return null;
      }
      final channel = _ChannelAdapter(
        ble: _ble,
        linkGeneration: linkGeneration,
        bindingToken: bindingToken,
        deviceAddress: deviceAddress,
        serviceId: serviceId,
        writeCharId: writeId,
        chunkSize: mtuChunk,
        notifyStream: notifyStream,
        writeWithResponse: writeWithResponse,
        stats: stats,
      );
      transport = OtaBleTransport(channel: channel, stats: stats);
      if (aborted() || !linkCurrent()) {
        // 已被取代：当场释放（dispose 取消本地通知监听），平台 CCCD 的开
        // 关归新 owner，令牌复核保证这里的释放不会误关别人的通知流。
        await transport.dispose();
        transport = null;
        return null;
      }
      return transport;
    } catch (e) {
      debugPrint('绑定 probe transport 失败: $e');
      await transport?.dispose();
      return null;
    }
  }

  /// 建立 OTA transport：精确特征绑定 + MTU 协商 + 通知订阅就绪。
  /// 重建前先释放旧 transport（PR10：一个连接代次仅一个订阅）。
  ///
  /// [stats] 为可选 P3-4 链路观测（默认 null 零行为差异）：透传到 MTU
  /// 协商、通知订阅、写通道与 transport 实例。
  Future<OtaBleTransport?> _bindTransport(
    String deviceAddress,
    Map<String, String> otaChars, {
    OtaLinkStats? stats,
  }) async {
    final linkGeneration = _ble.otaLinkGeneration(deviceAddress);
    final bindingToken = _ble.otaGattBindingToken(deviceAddress);
    bool linkCurrent() =>
        linkGeneration == _ble.otaLinkGeneration(deviceAddress) &&
        identical(bindingToken, _ble.otaGattBindingToken(deviceAddress));
    try {
      final old = _transport;
      _transport = null;
      if (old != null) {
        await old.dispose();
      }
      final mtuChunk =
          await _ble.requestOtaMtu(deviceAddress, stats: stats);
      if (!linkCurrent()) return null;
      final serviceId = otaChars['serviceId']!;
      final writeId = otaChars['writeCharId']!;
      final notifyId = otaChars['notifyCharId']!;
      // 绑定 FFF2 实际支持的写模式（PR06）。
      final writeWithResponse = otaChars['writeMode'] != 'without';
      // 订阅就绪后才返回流（PR10），随后才允许发 GET_INFO。
      final notifyStream = await _ble.subscribeOtaNotifyByAddress(
        deviceAddress,
        serviceId,
        notifyId,
        stats: stats,
      );
      if (notifyStream == null) {
        return null;
      }
      final channel = _ChannelAdapter(
        ble: _ble,
        linkGeneration: linkGeneration,
        bindingToken: bindingToken,
        deviceAddress: deviceAddress,
        serviceId: serviceId,
        writeCharId: writeId,
        chunkSize: mtuChunk,
        notifyStream: notifyStream,
        writeWithResponse: writeWithResponse,
        stats: stats,
      );
      final transport = OtaBleTransport(channel: channel, stats: stats);
      if (!linkCurrent()) {
        await transport.dispose();
        return null;
      }
      _transport = transport;
      // RC3-08⑦：记录本次绑定所依附的物理链路（地址 + 链路代次 +
      // 实际发现到的特征）。后台恢复据此判断链路是否已被换掉。
      _boundAddress = deviceAddress;
      _boundChars = Map<String, String>.unmodifiable(otaChars);
      _boundLinkGeneration = linkGeneration;
      return transport;
    } catch (e) {
      debugPrint('绑定 OTA transport 失败: $e');
      return null;
    }
  }

  /// metadata 请求的有界自动重试（OTA-XC-RETRY-POLICY）：共 3 次尝试；
  /// 429 优先 Retry-After，否则 1s/2s 退避，单次等待上限 30s。
  ///
  /// RC3-10：分类先于重试。可解析错误体先按稳定 errorCode 分类，仅
  /// isAutoRetryable（RATE_LIMITED/BACKEND_UNAVAILABLE）自动重试；
  /// 终止码与未知码原样抛出，交 [_terminalFromDioError] 归入稳定终态
  /// ——禁止未分类先按 429/503 重试、更禁止被后续 200 洗成成功。
  /// 无可解析体的错误仅按网络错误类型或裸 429/503 状态码重试。
  ///
  /// [generation]（RC3-01/RC3-04）：调用方进入时的取消代次，可空
  /// （调用方不参与代次）。每次 await 返回后核对，代次已变（用户已
  /// 取消）则返回 null，调用方静默退出——禁止把取消前的旧响应发布成
  /// 新状态。请求本身绑定 CancelToken（cancelUpgrade 立即中断在途
  /// latest 请求）。
  Future<Response<dynamic>?> _getLatestWithRetry(Uri uri, int? generation) async {
    var attempts = 0;
    while (true) {
      final token = CancelToken();
      _activeLatestToken = token;
      try {
        final response = await _dio.getUri(uri, cancelToken: token);
        if (_generationCancelled(generation)) return null;
        return response;
      } on DioException catch (e) {
        if (CancelToken.isCancel(e)) return null; // 取消：静默退出
        if (!_isAutoRetryableLatestError(e) || attempts >= 2) rethrow;
        attempts++;
        final retryAfter = _retryAfterSecondsOf(e) ?? (attempts == 1 ? 1 : 2);
        await Future<void>.delayed(
          Duration(seconds: retryAfter.clamp(1, 30)),
        );
        if (_generationCancelled(generation)) return null;
      } finally {
        if (identical(_activeLatestToken, token)) _activeLatestToken = null;
      }
    }
  }

  /// 代次取消判定（RC3-04）：generation 为 null 表示调用方不参与代次。
  bool _generationCancelled(int? generation) =>
      generation != null && generation != _cancelGeneration;

  /// latest 请求的自动重试判定（RC3-10）——先分类，后重试：
  /// - 可解析错误体 → 按 OtaHttpError 稳定 errorCode 分类，仅
  ///   isAutoRetryable 时重试（该判定内部已要求 HTTP 状态符合
  ///   OTA-XC-HTTP-ERROR 表：RATE_LIMITED=429、BACKEND_UNAVAILABLE=503）；
  ///   终止/未知/坏 schema 均不重试（fail closed，交
  ///   _terminalFromDioError 处置）；
  /// - 无体/不可解析体 → 仅裸 429/503 状态码重试；
  /// - 无响应（网络错误）→ 仅瞬态连接类错误重试。
  /// RC3-10⑤：可解析体的重试不能只凭 errorCode——非 429/503 状态携带
  /// RATE_LIMITED/BACKEND_UNAVAILABLE 码是服务端矛盾信号（或中间层
  /// 篡改），按 fail closed 处理，不得据此自动重试。
  bool _isAutoRetryableLatestError(DioException e) {
    final response = e.response;
    if (response != null) {
      Map<String, dynamic>? map;
      try {
        map = _readJsonObject(response.data);
      } catch (_) {
        map = null;
      }
      if (map != null) {
        try {
          final httpError = OtaHttpError.fromBody(
            map,
            response.statusCode ?? 0,
            requestIdHeader: _firstHeader(response.headers, 'x-request-id'),
          );
          // 状态约束在 OtaHttpError 内（RC3-10/11），此处不重复维护状态表。
          return httpError.isAutoRetryable;
        } on OtaLatestParseException {
          // 坏 schema：不重试未知。
          return false;
        }
      }
      final status = response.statusCode;
      return status == 429 || status == 503;
    }
    return e.type == DioExceptionType.connectionTimeout ||
        e.type == DioExceptionType.sendTimeout ||
        e.type == DioExceptionType.receiveTimeout ||
        e.type == DioExceptionType.connectionError;
  }

  int? _retryAfterSecondsOf(DioException e) {
    final header = _firstHeader(e.response?.headers, 'retry-after');
    if (header != null) {
      final parsed = int.tryParse(header);
      if (parsed != null) return parsed.clamp(1, 30);
    }
    final body = e.response?.data;
    if (body is Map && body['retryAfter'] is int) {
      return (body['retryAfter'] as int).clamp(1, 30);
    }
    return null;
  }

  static Future<Directory> _defaultFirmwareDir() async {
    final directory = await getApplicationDocumentsDirectory();
    final firmwareDir = Directory('${directory.path}/firmware');
    if (!await firmwareDir.exists()) {
      await firmwareDir.create(recursive: true);
    }
    return firmwareDir;
  }

  void _clearFirmwareInfo() {
    _latestInfo = null;
    _asset = null;
    _releaseId = null;
    _firmwareFile = null;
    _verified = null;
    // 签署者随资产一起清除（RC3-12⑦）：残留 owner 会让下一批资产在
    // 尚未登记签署者时看起来"已归属"。
    _assetOwnerInfo = null;
    _assetOwnerAddress = null;
  }

  /// 是否仍持有任何固件资产（RC3-12⑦）。
  bool get _hasFirmwareAssets =>
      _latestInfo != null ||
      _asset != null ||
      _releaseId != null ||
      _firmwareFile != null ||
      _verified != null;

  /// 保留的资产是否确属 [info]/[address] 这一身份（RC3-12⑦）。
  ///
  /// 没有资产时为真（无可失效对象）。有资产但签署者缺失时为假——无法
  /// 证明归属即视为不属于（fail-closed），不做"大概是同一台"的推定。
  bool _assetsBelongTo(DeviceOtaInfo info, String address) {
    if (!_hasFirmwareAssets) return true;
    final owner = _assetOwnerInfo;
    return owner != null &&
        deviceIdentityMatches(owner, info) &&
        _assetOwnerAddress == address;
  }

  /// 终止型/闭锁型 HTTP 错误分类（PR11）：所有非 2xx 状态的错误体都
  /// 尝试解析（不只 426/409）；未知 errorCode/未知状态 fail closed 进
  /// 终止态；网络错误（无响应）不算终止。
  ///
  /// [retryExhausted]：调用方（_getLatestWithRetry 三次尝试耗尽后的
  /// catch）传入 true 时，RATE_LIMITED/BACKEND_UNAVAILABLE 不再返回
  /// null，而是进入可稍后重试终态（调用方同时清旧资产——旧清单可能
  /// 已过期，RC2-04）；重试未耗尽（重试层会继续）时返回 null。
  OtaTerminalState? _terminalFromDioError(
    Object error, {
    bool retryExhausted = false,
  }) {
    if (error is! DioException) return null;
    final response = error.response;
    if (response == null) return null; // 网络错误：瞬态，不终止
    final status = response.statusCode ?? 0;
    Map<String, dynamic> map;
    try {
      map = _readJsonObject(response.data);
    } catch (_) {
      // 错误响应无可解析体：按未知 HTTP 状态 fail closed（PR11）。
      return OtaTerminalState(
        code: 'HTTP_$status',
        message: '固件服务返回 HTTP $status 且无错误体',
      );
    }
    try {
      final httpError = OtaHttpError.fromBody(
        map,
        status,
        requestIdHeader: _firstHeader(response.headers, 'x-request-id'),
      );
      // 状态约束在 OtaHttpError.isAutoRetryable / isRetryableLater 内部
      // （RATE_LIMITED=429、BACKEND_UNAVAILABLE=503、CHANNEL_STOPPED=200/503），
      // 此处不重复判定；状态错配的响应直接落到下面的稳定终态分支（RC3-10/11）。
      if (httpError.isAutoRetryable) {
        if (!retryExhausted) return null; // 重试层还会继续
        // 自动重试耗尽：可稍后重试终态（不闭锁入口，但调用方会清资产）。
        return OtaTerminalState(
          code: httpError.errorCode,
          message: httpError.message ?? httpError.errorCode,
          retryableLater: true,
          requestId: httpError.requestId,
        );
      }
      if (httpError.isRetryableLater) {
        return OtaTerminalState(
          code: httpError.errorCode,
          message: httpError.message ?? httpError.errorCode,
          retryableLater: true,
          requestId: httpError.requestId,
        );
      }
      // 终止码与未知码（含 UNKNOWN_DEVICE_MODEL 等 400 类）都进稳定终态。
      return OtaTerminalState(
        code: httpError.errorCode,
        message: httpError.message ?? httpError.errorCode,
        minAppVersionCode: httpError.minAppVersionCode,
        requiredValue: httpError.requiredValue,
        actualValue: httpError.actualValue,
        requestId: httpError.requestId,
      );
    } on OtaLatestParseException {
      return OtaTerminalState(
        code: 'HTTP_$status',
        message: '固件服务错误响应体不符合 schema（HTTP $status）',
      );
    }
  }

  String? _firstHeader(dynamic headers, String name) {
    try {
      return headers.value(name) as String?;
    } catch (_) {
      return null;
    }
  }

  Map<String, dynamic> _readJsonObject(Object? value) {
    final parsed = value is String ? jsonDecode(value) : value;
    if (parsed is Map<String, dynamic>) return parsed;
    if (parsed is Map) {
      return parsed.map((key, entry) => MapEntry(key.toString(), entry));
    }
    throw const FormatException('固件清单不是JSON对象');
  }

  String _formatBytes(int bytes) {
    if (bytes < 1024) return '$bytes B';
    final kb = bytes / 1024;
    if (kb < 1024) return '${kb.toStringAsFixed(1)} KB';
    final mb = kb / 1024;
    return '${mb.toStringAsFixed(2)} MB';
  }

  String _friendlyDioMessage(Object error) {
    if (error is DioException) {
      if (CancelToken.isCancel(error)) return '用户已取消';
      final status = error.response?.statusCode;
      final body = error.response?.data;
      final serverMessage = body is Map
          ? (body['message'] ?? body['errorCode'])?.toString()
          : body is String && body.isNotEmpty
              ? body
              : null;
      if (status != null && serverMessage != null) {
        return 'HTTP $status: $serverMessage';
      }
      if (status != null) return 'HTTP $status';
      return error.message ?? error.type.name;
    }
    return error.toString();
  }
}

/// 重启复核结果分类（RC3-08②）。
enum _RebootKind {
  /// 已运行目标固件（vcode + raw image SHA 等于清单目标）。
  targetVerified,

  /// 60 秒总截止内未确认目标固件在运行（可稍后重试）。
  timedOut,

  /// 重启后硬件身份与会话开始时不一致（换设备/异常，终止）。
  identityChanged,

  /// 用户取消（静默退出，状态由 cancelUpgrade 发布）。
  cancelled,
}

/// [_RebootOutcome] 见 OtaService._waitForTargetIdentity。
class _RebootOutcome {
  const _RebootOutcome(this.kind, {this.info});

  final _RebootKind kind;
  /// targetVerified 时携带升级后的设备身份快照。
  final DeviceOtaInfo? info;
}

/// 已验证的下载包（PR12）：绑定 assetId/releaseId/sha256/size/versionCode
/// 与落盘文件。清单变化即失效；BEGIN 前必须复核当前字节仍匹配。
class _VerifiedPackage {
  _VerifiedPackage({
    required this.assetId,
    required this.releaseId,
    required this.sha256,
    required this.sizeBytes,
    required this.versionCode,
    required this.file,
  });

  final String assetId;
  final String releaseId;
  final String sha256;
  final int sizeBytes;
  final int versionCode;
  final File file;
}

/// 终止态（CLIENT_TOO_OLD / 兼容 409 / 设备身份失败等）。
///
/// 进入终止态后 UI 不得提供「重试同样请求」的默认路径，
/// 也不得转换为 NO_UPDATE；非 retryableLater 的终止态同时闭锁
/// 下载/传输入口，直到重新 readDeviceInfo 建立有效查询链。
class OtaTerminalState {
  OtaTerminalState({
    required this.code,
    required this.message,
    this.retryableLater = false,
    this.minAppVersionCode,
    this.requiredValue,
    this.actualValue,
    this.requestId,
  });

  final String code;
  final String message;
  /// CHANNEL_STOPPED / BACKEND_UNAVAILABLE / REBOOT_RECONNECT_FAILED 等：
  /// 允许用户稍后重试（不闭锁入口）。
  final bool retryableLater;
  final int? minAppVersionCode;
  final int? requiredValue;
  final int? actualValue;
  final String? requestId;

  String get userMessage {
    switch (code) {
      case 'CLIENT_TOO_OLD':
        final min = minAppVersionCode;
        return min == null
            ? '当前 App 版本过低，需先升级 App 再更新固件'
            : '当前 App 版本过低（需 ≥ $min），请先升级 App';
      case 'HARDWARE_INCOMPATIBLE':
        return '硬件版本不兼容（需要 $requiredValue，实际 $actualValue）';
      case 'LAYOUT_INCOMPATIBLE':
        return '硬件布局不兼容（需要 $requiredValue，实际 $actualValue）';
      case 'BOOT_TOO_OLD':
        return 'Bootloader 版本过低（需 ≥ $requiredValue，当前 $actualValue）';
      case 'PROTOCOL_UNSUPPORTED':
        return '固件协议版本不受支持（需 ≥ $requiredValue，当前 $actualValue）';
      case 'UNKNOWN_DEVICE_MODEL':
        return '无法识别设备型号，请确认连接的是 E-Track 码表';
      case 'CHANNEL_STOPPED':
        return '固件通道已停发，请稍后再试';
      default:
        return message;
    }
  }
}

/// 把 OtaBleChannel 适配到 BluetoothService 的按地址读写。
class _ChannelAdapter implements OtaBleChannel {
  _ChannelAdapter({
    required BluetoothService ble,
    required this.linkGeneration,
    required this.bindingToken,
    required this.deviceAddress,
    required this.serviceId,
    required this.writeCharId,
    required this.chunkSize,
    required this.notifyStream,
    required this.writeWithResponse,
    this.stats,
  })  : _ble = ble,
        // 绑定时取设备作用域句柄（RC3-05⑤），供传输层界定写通道废弃标记。
        // 取一次而非每次现取：现取会让已被放弃的旧 adapter 在重连后"继承"
        // 新链路的干净状态，重新开始写已经不可信的通道。设备作用域按地址
        // 恒定（重连不更换），所以重建 wrapper 与真实重连都拿到同一句柄；
        // 解除只能靠传输层用 GET_INFO → INFO 往返证明 MCU 解析器已重新同步。
        deviceScope = ble.otaDeviceScope(deviceAddress);

  final BluetoothService _ble;
  final int linkGeneration;
  final Object? bindingToken;
  final String deviceAddress;
  final String serviceId;
  final String writeCharId;
  final int chunkSize;
  final Stream<List<int>> notifyStream;
  /// FFF2 实际支持的写模式（PR06 绑定）。
  final bool writeWithResponse;
  /// P3-4 链路观测（可选；null 时零行为差异）：透传 GATT 写计时。
  final OtaLinkStats? stats;
  bool _connected = true;

  bool get _bindingCurrent =>
      linkGeneration == _ble.otaLinkGeneration(deviceAddress) &&
      identical(bindingToken, _ble.otaGattBindingToken(deviceAddress));

  /// 本通道所属设备的作用域句柄（RC3-05⑤）：MCU 侧帧解析器状态不随
  /// BLE 连接事件改变，因此重连后仍是同一作用域。
  @override
  final Object? deviceScope;

  @override
  Future<void> writeChunk(List<int> chunk) async {
    try {
      if (!isConnected) throw StateError('STALE_OTA_CHANNEL');
      // OTA 专用严格写入（RC2-08）：UUID 精确匹配 FFF0/FFF2，
      // 不复用遥控透传 writeByAddress 的宽松匹配。
      await _ble.writeOtaCharacteristicByAddress(
        deviceAddress,
        serviceId,
        writeCharId,
        chunk,
        writeWithResponse: writeWithResponse,
        stats: stats,
      );
      if (!isConnected) throw StateError('STALE_OTA_CHANNEL_COMPLETION');
    } catch (e) {
      // 写失败同样标记断连（PR09）：不能只依赖通知流 error/done。
      _connected = false;
      rethrow;
    }
  }

  @override
  Stream<List<int>> get notifications {
    final controller = StreamController<List<int>>();
    final sub = notifyStream.listen(
      (value) {
        if (_connected && !_bindingCurrent) {
          _connected = false;
          controller.addError(StateError('STALE_OTA_CHANNEL_NOTIFICATION'));
        } else if (isConnected) {
          controller.add(value);
        }
      },
      onError: (Object e) {
        _connected = false;
        controller.addError(e);
      },
      onDone: () {
        _connected = false;
        controller.close();
      },
    );
    controller.onCancel = () async {
      await sub.cancel();
    };
    return controller.stream;
  }

  @override
  Future<int> maxWriteChunkSize() async => chunkSize;

  @override
  bool get isConnected => _connected && _bindingCurrent;
}
