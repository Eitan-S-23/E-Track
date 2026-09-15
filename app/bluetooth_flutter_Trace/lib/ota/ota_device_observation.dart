import 'dart:async';

import 'package:flutter/foundation.dart';

import 'ota_device_info.dart';

/// P3-3 T1a 真机设备观测（dev 分支 + dev APK 专用）。
///
/// 动机：此前每轮设备观测都要人工驱动 UI（点进四级页面 + 截图判读），既慢又
/// 不可复现；而应用自身日志出口在"设备名称"一处恒定饱和（实测扫到 17 台、
/// 日志只吐 5 台），不能作为全量扫描的证据。本文件把观测变成**机器可读的
/// logcat 行**：全量扫描结果逐台落盘，命中目标后自动绑定并读取设备身份
/// ——观测者只读日志，不再点界面。
///
/// 三道闸门（任一不满足都不产生观测行为）：
/// 1. 编译期必须显式注入 `TRACE_DEV_DEVICE_OBSERVATION=true`。默认 false，
///    未注入时 [OtaDeviceObserver.instance] 保持 null，扫描监听里的接线
///    立即返回、不产生任何日志行，默认行为与改动前一致。
/// 2. 启用后必须同时注入 target 与 sentinel，否则
///    [OtaDeviceObservationConfig.problem] 非空，观测不启动（fail-closed），
///    只输出一行 `OTA_OBS config=INVALID`，不产出"看起来在观测"的假象。
/// 3. 构建侧（`Tools/flutter/dev_apk.py`）在归档阶段要求 sentinel 与固件查询
///    地址的**字面量**确实出现在产物 Dart kernel blob 中，否则不产出产物记录
///    ——"声称已注入、实际没注入"的假阳性 APK 无法离开 CI。
///
/// 本文件只读扫描结果与时钟、只写日志，不改变任何控制流；所有输出行以
/// `OTA_OBS ` 开头，字段顺序固定，便于 logcat 侧逐行解析。**结局是全的**：
/// 命中并读身份成功 / 连接失败 / 连接抛异常 / 连接超时 / 身份为空 /
/// 身份抛异常 / 身份超时 / 窗口到期仍未命中 / 扫描压根没启动（含启动路径
/// 自己抛异常或超时）/ 扫描流中途报错 / 绑定链路意外异常兜底 —— 每个结局
/// 各有且仅有一行 `done`，不允许出现"没有任何终止行"。
///
/// 环境变量名（构建侧同名注入，改一个必须同步改另一个）：
/// - `TRACE_DEV_DEVICE_OBSERVATION`
/// - `TRACE_DEV_OBSERVATION_TARGET`
/// - `TRACE_DEV_OBSERVATION_SENTINEL`
/// - `TRACE_CLOUDFLARE_FIRMWARE_LATEST_URL`（既有常量，观测构建一并注入）

/// 编译期观测配置。
@immutable
class OtaDeviceObservationConfig {
  const OtaDeviceObservationConfig({
    required this.enabled,
    required this.target,
    required this.sentinel,
  });

  /// 当前构建的观测配置，全部来自编译期常量。
  ///
  /// `fromEnvironment` 的键必须写成字面量，不能用常量变量转发。
  static const OtaDeviceObservationConfig fromBuild =
      OtaDeviceObservationConfig(
    enabled: bool.fromEnvironment(
      'TRACE_DEV_DEVICE_OBSERVATION',
      defaultValue: false,
    ),
    target: String.fromEnvironment(
      'TRACE_DEV_OBSERVATION_TARGET',
      defaultValue: '',
    ),
    sentinel: String.fromEnvironment(
      'TRACE_DEV_OBSERVATION_SENTINEL',
      defaultValue: '',
    ),
  );

  /// 是否显式启用。未启用时本文件不产生任何行为。
  final bool enabled;

  /// 目标板的 BLE 广播名（精确或前缀匹配）或 MAC 地址。
  final String target;

  /// 构建侧按（target, 固件查询地址）算出的指纹。运行期把它打进日志，用于
  /// 把手上这台 APK 与 CI 记录的那次构建对上——两者不一致即说明装的不是
  /// 同一个产物。
  final String sentinel;

  /// 配置问题；`null` 表示可用。**未启用时恒为 `null`**：默认构建不是"非法
  /// 配置"，它只是不观测。
  String? get problem {
    if (!enabled) return null;
    if (target.trim().isEmpty) return 'missing_target';
    if (sentinel.trim().isEmpty) return 'missing_sentinel';
    return null;
  }

  /// 是否真的执行观测：显式启用且配置完整。
  bool get active => enabled && problem == null;

  /// 启动行。仅在 [enabled] 为真时输出；配置非法时给出 `config=INVALID`，
  /// 让"启用了但没生效"在日志里一眼可见。
  String get statusLine => problem == null
      ? 'OTA_OBS config=enabled target=$target sentinel=$sentinel'
      : 'OTA_OBS config=INVALID problem=$problem target=$target sentinel=$sentinel';

  /// 目标匹配规则（按强度依次尝试，命中即返回）。
  ///
  /// 地址规则只对**地址形态的 target**生效（含分隔符，或去掉分隔符后恰好
  /// 12 位 hex）；且比较是**全等**而非子串。两者合起来保证像 `aabb` 这种
  /// 短名字不会被归一化地址的 hex 片段误命中，同时 `AABBCCDDEEFF` 这种
  /// 无分隔符写法仍能命中。
  OtaObservationMatch match(ObservedAdvertisement advertisement) {
    final wanted = target.trim().toLowerCase();
    if (wanted.isEmpty) return OtaObservationMatch.none;
    if (advertisement.address.toLowerCase() == wanted) {
      return OtaObservationMatch.address;
    }
    final wantedHex = wanted.replaceAll(RegExp('[^0-9a-f]'), '');
    if (wantedHex.isNotEmpty &&
        (wanted.contains(':') || wantedHex.length == 12)) {
      if (advertisement.normalizedAddress == wantedHex) {
        return OtaObservationMatch.address;
      }
    }
    if (advertisement.normalizedName == wanted) {
      return OtaObservationMatch.nameExact;
    }
    // 前缀兜底：部分 BLE 模块会在配置名后追加短地址。仅对长度 >= 4 的
    // target 生效，且命中规则会原样写进日志（matched_by=namePrefix），
    // 误绑可被事后识别。
    if (wanted.length >= 4 && advertisement.normalizedName.startsWith(wanted)) {
      return OtaObservationMatch.namePrefix;
    }
    return OtaObservationMatch.none;
  }
}

/// 目标匹配结果；[label] 直接作为日志里的 `matched_by` 取值。
///
/// 枚举值不用 `name`：那是 `Enum` 自带的实例成员，同名静态常量会与继承来的
/// getter 冲突。
enum OtaObservationMatch {
  none('none'),
  address('address'),
  nameExact('name'),
  namePrefix('namePrefix');

  const OtaObservationMatch(this.label);

  final String label;
}

/// 一次扫描广播的最小可观测快照（纯值对象，不依赖任何插件类型）。
@immutable
class ObservedAdvertisement {
  const ObservedAdvertisement({
    required this.address,
    required this.name,
    required this.rssi,
    required this.connectable,
    this.serviceUuids = const <String>[],
    this.manufacturerDataHex = '',
  });

  final String address;
  final String name;
  final int rssi;
  final bool connectable;
  final List<String> serviceUuids;
  final String manufacturerDataHex;

  /// 归一化地址：只保留小写 hex，使 `AA:BB:CC:DD:EE:FF` 与 `aabbccddeeff` 互认。
  String get normalizedAddress =>
      address.toLowerCase().replaceAll(RegExp('[^0-9a-f]'), '');

  /// 归一化广播名：小写去空白，用于与 target 比较。
  String get normalizedName => name.toLowerCase().trim();

  /// 单台设备的观测行；字段固定顺序，`-` 表示空值。
  String get line => 'OTA_OBS adv addr=$address name=${_orDash(name)} '
      'rssi=$rssi connectable=$connectable '
      'uuids=${serviceUuids.isEmpty ? '-' : serviceUuids.join('|')} '
      'mfg=${_orDash(manufacturerDataHex)}';

  static String _orDash(String value) => value.isEmpty ? '-' : value;
}

/// 启动扫描。返回值 = **扫描是否真的启动**：适配器未就绪、平台拒绝等情况下
/// 必须返回 false，观测侧据此给出确定的 `scan_not_started` 终止行，而不是让
/// "扫了 120s 什么都没扫到"与"扫描根本没启动"在日志里长得一模一样。
///
/// 抛异常同样是"没启动"：观测侧会把异常收进同一结局并留下原文，不会让它变成
/// 一条没有终止行的野异常。
typedef OtaObservationStart = Future<bool> Function();
typedef OtaObservationStop = Future<void> Function();
typedef OtaObservationConnect = Future<bool> Function(
    ObservedAdvertisement advertisement);
typedef OtaObservationIdentityRead = Future<DeviceOtaInfo?> Function(
    String address);

/// 终局清理钩子（OBS-02）：终止行落盘后调用，用于拆除观测占用的物理
/// 资源（如断开观测连接）。参数是本次绑定过的目标地址（小写），从未
/// 进入绑定阶段时为 null（此时通常只需停扫描，停扫描已由观测器自理）。
/// **清理自身失败不得覆盖已发布的终态**——它只是尽力而为的收尾，异常
/// 在这里就地吞掉并记录一行 `cleanup_error`。
typedef OtaObservationCleanup = Future<void> Function(String? address);

/// 观测器：把扫描批次转成 `OTA_OBS` 行，命中目标后绑定并读取身份。
///
/// 依赖全部由构造参数注入（连接/读身份不进本文件），因此本类可脱离 GetX、
/// 插件通道与设备在纯单元测试里驱动。
class OtaDeviceObserver {
  OtaDeviceObserver({
    required this.config,
    required this.startScan,
    required this.stopScan,
    required this.connect,
    required this.readIdentity,
    this.cleanup,
    this.identityStatus,
    this.window = defaultWindow,
    this.startTimeout = defaultStartTimeout,
    this.connectTimeout = defaultConnectTimeout,
    this.identityTimeout = defaultIdentityTimeout,
    void Function(String line)? emit,
  }) : _emit = emit ?? debugPrint;

  /// 观测窗口的缺省时长。窗口到期仍未命中目标，即输出 `target_not_seen`
  /// 终止行——"没有任何终止行"必须被消灭：logcat 侧不允许用"没有错误行"
  /// 反推"尚未读取"。
  static const Duration defaultWindow = Duration(seconds: 120);

  /// 扫描启动自身的等待上限：启动路径挂死（适配器状态永不到位、平台
  /// `startScan()` 永不返回）时观测不能跟着无限等——到时给出确定的
  /// `scan_start_timeout` 终止行。
  ///
  /// 注意与 [OtaObservationStart] 返回 false 的区别：那是"启动被拒绝"
  /// （适配器未就绪、平台明确报错），立即收尾；这里处理的是"启动调用
  /// **永远不完成**"，两者在日志上必须可区分。
  static const Duration defaultStartTimeout = Duration(seconds: 60);

  /// 命中目标后连接的等待上限：`connect` 调用挂死时同样不能无限等，
  /// 到时输出 `connect_timeout`。
  static const Duration defaultConnectTimeout = Duration(seconds: 30);

  /// 读取身份（GET_INFO 往返）的等待上限：到时输出 `identity_timeout`。
  ///
  /// 注意：`Future.timeout` 只是**放弃等待**，不取消底层操作。该边界只
  /// 保证观测侧必有一条终止行，不声称连接已被物理拆除——清理仍交给
  /// 装配处注入的 [OtaObservationCleanup]。
  static const Duration defaultIdentityTimeout = Duration(seconds: 30);

  /// 进程内唯一实例。**仅在显式启用且配置完整时被赋值**；扫描监听据此
  /// 判断是否需要观测，未启用时是 null。
  static OtaDeviceObserver? instance;

  /// 由编译期配置装配并启动观测。
  ///
  /// 未启用返回 null（默认行为不变）；启用但配置非法时先输出一行
  /// `config=INVALID` 再返回 null——fail-closed，既不启动观测，也不静默
  /// 装作成功。
  static OtaDeviceObserver? startFromBuild({
    required OtaObservationStart startScan,
    required OtaObservationStop stopScan,
    required OtaObservationConnect connect,
    required OtaObservationIdentityRead readIdentity,
    OtaObservationCleanup? cleanup,
    String Function()? identityStatus,
    void Function(String line)? emit,
  }) {
    const config = OtaDeviceObservationConfig.fromBuild;
    if (!config.enabled) return null;
    final reporter = emit ?? debugPrint;
    if (!config.active) {
      reporter(config.statusLine);
      return null;
    }
    final observer = OtaDeviceObserver(
      config: config,
      startScan: startScan,
      stopScan: stopScan,
      connect: connect,
      readIdentity: readIdentity,
      cleanup: cleanup,
      identityStatus: identityStatus,
      emit: reporter,
    );
    instance = observer;
    observer.start();
    return observer;
  }

  final OtaDeviceObservationConfig config;
  final OtaObservationStart startScan;
  final OtaObservationStop stopScan;
  final OtaObservationConnect connect;
  final OtaObservationIdentityRead readIdentity;
  final OtaObservationCleanup? cleanup;

  /// 读取服务侧最近一次身份失败的原因文案（`OtaService.upgradeStatus`）。
  /// 服务侧已把「设备未暴露 OTA 服务（FFF0/FFF2/FFF1）」/「OTA 通知订阅失败」/
  /// 「GET_INFO 失败: …」/「设备身份识别失败: …」分开写；这里原样转述，
  /// 不在观测侧另造一套分类，避免两处口径漂移。
  final String Function()? identityStatus;

  /// 观测窗口：到期未命中即给出终止行。
  final Duration window;

  /// 各阶段等待上限（OBS-02）。见同名 default 常量的文档。
  final Duration startTimeout;
  final Duration connectTimeout;
  final Duration identityTimeout;

  final void Function(String line) _emit;

  /// 已观测过的地址（归一化）：同一台设备只输出一次广播明细，避免日志被
  /// 每秒重复行淹没。
  final Set<String> _seenAddresses = <String>{};

  bool _started = false;

  /// 终止结局的唯一闸门：一旦置位，既不再发起绑定，也不会再输出第二行
  /// `done`。窗口到期、命中绑定、流错误与启动失败共用它，判定与置位都在
  /// 同一 isolate 上同步完成，不存在竞态。**`_settle` 之后迟到的回调
  /// （窗口、启动完成、connect/readIdentity 的迟到完成）一律只做清理，
  /// 不得再输出终止行或覆盖终态。**
  bool _settled = false;

  /// 已发布的终态结果（供测试与装配处断言"结局唯一且可读"）。
  String? get result => _result;
  String? _result;

  Timer? _windowTimer;

  /// 占据终止闸门（OBS-02）：从此窗口、启动完成、迟到批次都不得再产出
  /// 任何结局。绑定路径先占闸门、再走异步链路，`done` 行由
  /// [_publishDone] 在链路终点发布。
  void _claim() {
    if (_settled) return;
    _settled = true;
    _windowTimer?.cancel();
    _windowTimer = null;
  }

  /// 绑定阶段已进入的目标地址（小写）；null = 从未绑定。
  String? _boundAddress;

  /// 发布唯一终止行：所有结局必须经此出口，保证 `done` 行恰好一行。
  /// 调用方必须已经 [claim]（或在同一步内先 claim）。
  void _publishDone(String line) {
    assert(_settled, 'done 行发布前必须先占据终止闸门');
    if (_result != null) return;
    _result = line;
    _emit(line);
    final hook = cleanup;
    if (hook != null) {
      // 清理是尽力而为：失败不得覆盖已发布的终态，也不得把异常抛回
      // 调用方（那会变成没有终止行的野异常——正是本闸门要消灭的形态）。
      unawaited(hook(_boundAddress).catchError((Object error) {
        _emit('OTA_OBS cleanup result=error detail=$error');
      }));
    }
  }

  /// 占闸门 + 发布终态 + 尽力停扫描的一步式出口（启动失败/流错误/窗口
  /// 到期等"扫描侧"结局专用）。
  void _finishScanDone(String line) {
    _claim();
    if (_result != null) return;
    _publishDone(line);
    _stopScanQuietly();
  }

  /// 停止扫描的统一出口：扫描未启动时也调用（回收半开状态），失败不抛。
  void _stopScanQuietly() {
    unawaited(stopScan().catchError((Object error) {
      _emit('OTA_OBS stop result=error detail=$error');
    }));
  }

  /// 已见过的去重地址数（供测试断言）。
  int get observedDevices => _seenAddresses.length;

  /// 是否已经开始过观测（重复调用不会重复扫描）。
  bool get started => _started;

  void start() {
    if (!config.active || _started) return;
    _started = true;
    _emit(config.statusLine);
    unawaited(_beginScan());
  }

  /// 真正开始扫描后才开观测窗口。
  ///
  /// 启动是异步的（适配器状态可能还没填充），如果在 [start] 里就开计时，
  /// 等待期会被算进观测窗口，窗口到期时可能一次扫描都还没跑起来。
  Future<void> _beginScan() async {
    bool started;
    try {
      started = await startScan().timeout(
        startTimeout,
        onTimeout: () => throw TimeoutException('startScan', startTimeout),
      );
    } catch (error) {
      // 启动路径的实现在失败时会弹 UI 提示，而弹提示那一步自身也会抛
      // （2026-09-12 真机实测：`No Overlay widget found.`）。异常若逃出去，
      // 这里就再也不会写下终止行——"启动炸了"会退化成"没有任何终止行"，
      // 正是本文件要消灭的形态。因此把它归入同一个结局并留下原因。
      // 启动超时（TimeoutException）同样走这里，但结果行可区分。
      final timedOut = error is TimeoutException;
      _emit('OTA_OBS start result=${timedOut ? 'timeout' : 'error'} '
          'detail=$error');
      _finishScanDone(timedOut
          ? 'OTA_OBS done result=scan_start_timeout waitedMs='
              '${startTimeout.inMilliseconds}'
          : 'OTA_OBS done result=scan_not_started');
      return;
    }
    if (_settled) return;
    if (!started) {
      // 扫描没启动就不必再等窗口：等下去只会把"没扫"伪装成"扫了没看到"。
      _finishScanDone('OTA_OBS done result=scan_not_started');
      return;
    }
    _emit('OTA_OBS window=open windowMs=${window.inMilliseconds}');
    _windowTimer = Timer(window, _onWindowExpired);
  }

  /// 窗口到期仍未命中目标：给出确定且唯一的终止行，并停止扫描。
  void _onWindowExpired() {
    _windowTimer = null;
    if (_settled) return;
    _finishScanDone('OTA_OBS done result=target_not_seen waitedMs='
        '${window.inMilliseconds} scanned=${_seenAddresses.length} '
        'target=${config.target}');
  }

  /// 扫描流中途报错（OBS-01）：观测的第三个可区分结局。
  ///
  /// 装配处（`BluetoothService` 的 `onError` 回调）在扫描流出错时调用。
  /// 与 `scan_not_started`（压根没启动）、`target_not_seen`（扫了但目标
  /// 不在场）不同，本结局表示"扫过且流活着，随后流报错"——三者在日志上
  /// 必须一眼可辨，否则真机故障会被错误归类。
  void onScanStreamError(Object error) {
    if (!config.active || _settled) return;
    _emit('OTA_OBS stream result=error detail=$error');
    _finishScanDone('OTA_OBS done result=scan_stream_error '
        'scanned=${_seenAddresses.length}');
  }

  /// 消费一批扫描结果。未启用/已产生终止结局时是安全的空操作。
  void onAdvertisements(List<ObservedAdvertisement> batch) {
    if (!config.active) return;
    final fresh = <ObservedAdvertisement>[];
    for (final advertisement in batch) {
      if (advertisement.normalizedAddress.isEmpty) continue;
      if (_seenAddresses.add(advertisement.normalizedAddress)) {
        fresh.add(advertisement);
      }
    }
    _emit('OTA_OBS scan total=${batch.length} new=${fresh.length} '
        'seen=${_seenAddresses.length}');
    for (final advertisement in fresh) {
      _emit(advertisement.line);
    }
    if (_settled) return;
    for (final advertisement in batch) {
      final matched = config.match(advertisement);
      if (matched == OtaObservationMatch.none) continue;
      _claim();
      unawaited(_bind(advertisement, matched));
      return;
    }
  }

  /// 绑定链路（OBS-02）：连接与读身份各有等待上限；任何一步抛异常都收进
  /// 确定的终止行；链路终点由 [_publishDone] 发布唯一的 `done`。
  ///
  /// 分段收口：连接段的异常（含超时）在此结束；读身份段的异常（含超时）
  /// 在连接成功后单独收口。任何路径都不允许漏出"没有 done 行"的观测。
  Future<void> _bind(
    ObservedAdvertisement advertisement,
    OtaObservationMatch matched,
  ) async {
    // 绑定用地址必须是平台侧原样地址（`_findDeviceByAddress` 按小写比较）。
    final address = advertisement.address.toLowerCase();
    // 绑定已进入：终局清理钩子据此断开观测连接（此前为 null，清理只停
    // 扫描——停扫描由观测器自理）。
    _boundAddress = address;
    // OBS-03：target 行的地址必须是 advertisement.address 的**字段值**。
    // 旧代码写 `$advertisement.address` 会被解析成 `$advertisement` 后跟
    // 字面文本 `.address`，落盘成 `Instance of 'ObservedAdvertisement'.address`，
    // 使 target 行的地址无法与 connect/identity 行对上。
    _emit('OTA_OBS target addr=${advertisement.address} '
        'name=${advertisement.name.isEmpty ? '-' : advertisement.name} '
        'rssi=${advertisement.rssi} matched_by=${matched.label}');
    try {
      // 先停扫描：中央设备同时扫描与连接会互相挤占射频。停扫失败不阻断
      // 绑定（失败细节由 _stopScanQuietly 单独落一行错误）。
      await stopScan().catchError((Object error) {
        _emit('OTA_OBS stop result=error detail=$error');
      });
      final connected = await connect(advertisement).timeout(
        connectTimeout,
        onTimeout: () => throw TimeoutException('connect', connectTimeout),
      );
      _emit('OTA_OBS connect addr=$address '
          'result=${connected ? 'ok' : 'fail'}');
      if (!connected) {
        _publishDone('OTA_OBS done result=connect_failed');
        return;
      }
    } on TimeoutException {
      // connect 的超时：与"连接被明确拒绝"（result=fail）分开。
      _emit('OTA_OBS connect addr=$address result=timeout');
      _publishDone('OTA_OBS done result=connect_timeout');
      return;
    } catch (error) {
      // 连接段的预期外异常：不得变成没有终止行的野异常。
      _emit('OTA_OBS bind result=error detail=$error');
      _publishDone('OTA_OBS done result=bind_error');
      return;
    }
    DeviceOtaInfo? info;
    try {
      info = await readIdentity(address).timeout(
        identityTimeout,
        onTimeout: () => throw TimeoutException('identity', identityTimeout),
      );
    } on TimeoutException catch (error) {
      _emit('OTA_OBS identity addr=$address result=timeout detail=$error');
      _publishDone('OTA_OBS done result=identity_timeout');
      return;
    } catch (error) {
      _emit('OTA_OBS identity addr=$address result=error detail=$error');
      _publishDone('OTA_OBS done result=identity_error');
      return;
    }
    if (info == null) {
      _emit('OTA_OBS identity addr=$address result=fail '
          'status=${_reportedStatus()}');
      _publishDone('OTA_OBS done result=identity_failed');
      return;
    }
    _emit('OTA_OBS identity addr=$address result=ok wire=${info.wireModel} '
        'model=${info.deviceModel} vcode=${info.currentVersionCode} '
        'hw=${info.hardwareRevision} layout=${info.layoutId} '
        'boot=${info.bootVersion} proto=${info.protocolVersion} '
        'window=${info.maxWindowSegments} sha=${info.currentImageSha256Hex}');
    _publishDone('OTA_OBS done result=ok');
  }

  /// 失败原因文案；读取不到时用 `-`，不留空字段。
  String _reportedStatus() {
    final status = identityStatus?.call();
    if (status == null || status.trim().isEmpty) return '-';
    return status.trim();
  }
}
