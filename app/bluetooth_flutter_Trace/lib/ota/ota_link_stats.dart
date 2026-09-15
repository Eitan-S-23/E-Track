import 'dart:convert' as convert;

import 'dart:math' as math;

import 'package:flutter/foundation.dart';

/// P3-4 BLE 链路观测统计收集器（单绑定实例，纯观测组件）。
///
/// 依据 `docs/ota-cross-system-contracts.md` OTA-XC-BLE-PERFORMANCE 的分阶段
/// 测量要求与 OTA-XC-BLE-TUNING 的冻结统计语义（研究底稿见
/// `docs/ota-exec-notes/P3-4-research-link-timing-2026-09-16.md`）：
///
/// - **单一时钟域**：每个绑定（升级传输 / 重启探测 / 身份查询）一个实例，
///   实例内 `Stopwatch` 单调时钟，全部时间戳同源。跨绑定、跨进程（主机
///   vs MCU RTT）的时间戳不得相减。
/// - **只读观测**：不参与任何控制流、超时与判据；`null` 传入时调用点
///   零行为差异。
/// - **观测者效应口径**：采样时间戳全部取自被观测调用（await 边界）前后，
///   日志输出发生在时间戳之后，单样本值不受输出开销污染；帧间日志会轻
///   微拉长传输总时长，因此所有对照组合必须使用同一发送器版本（同一
///   插桩提交），口径一致。
/// - **fail-closed 完整性**：`outcome=ok` 的传输若存在已发送但无 ACK 样本
///   的段，摘要如实输出 `partial:missing=N` 而非静默缺行。
///
/// 日志契约（logcat 采集）：
/// - `OTA_LINK_SAMPLE label=<upgrade|probe|query> kind=<...> us=<n> [off=<n>] ...`
///   逐事件流式输出（原始样本，跨轮合并的原料）；
/// - `OTA_LINK_STATS {json}` 每绑定结束时输出一次聚合摘要（幂等，仅首次）。
///
/// ACK 延迟样本语义（OTA-XC-BLE-TUNING 冻结定义的工程映射）：
/// 从该段**首次完整发送结束**（`recordSegmentSendEnd` 首次记录该字节偏移）
/// 到**首个由 durable_off/bitmap 明确确认该段的有效 ACK 到达**
/// （`recordAckConfirm` / `recordBitmapConfirm`）。多个段可共享同一确认
/// （终点同、起点各异）；重复、无推进、错误与畸形 ACK 不产生样本
/// （在 ACK 分类计数中如实登记）；重传不创建新样本（首发结束时刻不变）。
class OtaLinkStats {
  OtaLinkStats({required this.label, this.device});

  /// 绑定用途：升级传输 / 重启探测 / 身份查询。
  final String label;

  /// 目标设备地址（仅标识用，不参与任何判据）。
  final String? device;

  final Stopwatch _clock = Stopwatch()..start();

  /// 实例内单调时钟（微秒）。同实例内时间戳同源。
  int nowUs() => _clock.elapsedMicroseconds;

  // ---- 阶段标记（起止时刻，幂等：只记首次）----

  final Map<String, List<int>> _phases = {};

  /// 标记阶段开始（bind / getinfo / transfer / reconnect 等）。
  void phaseStart(String name) {
    _phases.putIfAbsent(name, () => [nowUs()]);
  }

  /// 标记阶段结束；未开始或已结束时为 no-op。
  void phaseEnd(String name) {
    final p = _phases[name];
    if (p != null && p.length == 1) {
      p.add(nowUs());
    }
  }

  // ---- 绑定阶段（发现 / MTU / 订阅）----

  int? _charsDiscoveryUs;
  bool _charsFound = false;
  int _mtuRequested = 0;
  int _mtuChunkBytes = 0;
  int? _mtuUs;
  int? _subscribeUs;
  bool _subscribeOk = false;

  /// OTA 特征发现（findExact 整体）耗时与结果；幂等只记首次。
  void recordCharsDiscovery({required int durationUs, required bool found}) {
    if (_charsDiscoveryUs != null) return;
    _charsDiscoveryUs = durationUs;
    _charsFound = found;
  }

  /// MTU 协商结果：请求值与协商后的单次写入净荷上限。
  void recordMtu({
    required int requested,
    required int chunkBytes,
    required int durationUs,
  }) {
    if (_mtuUs != null) return;
    _mtuRequested = requested;
    _mtuChunkBytes = chunkBytes;
    _mtuUs = durationUs;
  }

  /// OTA 通知订阅耗时与结果；幂等只记首次。
  void recordSubscribe({required int durationUs, required bool ok}) {
    if (_subscribeUs != null) return;
    _subscribeUs = durationUs;
    _subscribeOk = ok;
  }

  // ---- GET_INFO 往返 ----

  final List<int> _getInfoDurationsUs = [];

  /// 一次 GET_INFO 往返（含实例内部的有界重试）。
  void recordGetInfo({required int durationUs}) {
    _getInfoDurationsUs.add(durationUs);
    _emitSample('get_info', durationUs);
  }

  // ---- 传输阶段（BEGIN 首帧写 → END ACK 到达）----

  int? _transferStartUs;
  int? _endAckArrivalUs;
  String? _transferOutcome;

  /// 传输起点：本 transfer 首个 BEGIN 帧写开始（幂等）。
  void recordTransferStart() {
    _transferStartUs ??= nowUs();
    phaseStart('transfer');
  }

  /// END ACK 完整到达（应用层观测点：帧分发；**覆盖式**——END 重试时
  /// 最后一次到达即「成功 END ACK 完整到达」，与 outcome=ok 配对）。
  void recordEndAckArrival() {
    _endAckArrivalUs = nowUs();
  }

  /// 传输终态（幂等）：成功 true / 失败 false（错误码由上层 catch 补记）。
  void recordTransferOutcome({required bool ok}) {
    _transferOutcome ??= ok ? 'ok' : 'fail';
    phaseEnd('transfer');
  }

  // ---- 段发送与 ACK 延迟样本 ----

  /// 累计段发送次数（首发 + 重发）。
  int segmentSendTotal = 0;

  /// 已发送过的唯一段（字节偏移）集合。
  final Set<int> _sentOffsets = {};

  /// 每个已发送段的首次完整发送结束时刻（us）。
  final Map<int, int> _firstSendEndUs = {};

  /// 已生成 ACK 延迟样本的段（字节偏移）。
  final Set<int> _sampledOffsets = {};

  /// ACK 延迟原始样本（us）。跨轮合并与 nearest-rank P99 由分析侧执行。
  final List<int> ackLatencySamplesUs = [];

  /// 登记一次段发送结束（首发与重发共用；偏移首次出现即视为首发）。
  ///
  /// [offsetBytes] 为段起始字节偏移（段号是块内 0-31，跨块不唯一，
  /// 唯一段标识必须用字节偏移）。
  void recordSegmentSendEnd({
    required int offsetBytes,
    required int lengthBytes,
  }) {
    segmentSendTotal++;
    final now = nowUs();
    if (_sentOffsets.add(offsetBytes)) {
      _firstSendEndUs[offsetBytes] = now;
      _emitSample('segment_first_send', now,
          extra: 'off=$offsetBytes len=$lengthBytes');
    } else {
      _emitSample('segment_retransmit', now,
          extra: 'off=$offsetBytes len=$lengthBytes');
    }
  }

  /// ACK 确认集合 → 逐段生成 ACK 延迟样本。
  ///
  /// [blockStart] 为确认时刻 MCU 的块起点（= 更新前 durable_off），
  /// [segs] 为本 ACK 明确确认的块内段号集合（ACK 自身段、durable 前移
  /// 回收的旧块在途段、或 bitmap 置位段）。共享同一 ACK 的段各自成样本。
  void recordAckConfirm({
    required int blockStart,
    required Iterable<int> segs,
    required int segmentSize,
  }) {
    final now = nowUs();
    for (final seg in segs) {
      final offset = blockStart + seg * segmentSize;
      final firstEnd = _firstSendEndUs[offset];
      if (firstEnd == null) continue; // 无首发记录（resume 位图跳过段等）
      if (!_sampledOffsets.add(offset)) continue; // 重复确认不重复采样
      final latency = math.max(0, now - firstEnd);
      ackLatencySamplesUs.add(latency);
      _emitSample('ack_latency', latency, extra: 'off=$offset');
    }
  }

  /// 权威位图确认（BEGIN ACK / resume）：bitmap 置位段由 durable_off/
  /// bitmap 明确确认，同样构成有效 ACK 样本终点。
  void recordBitmapConfirm({
    required int durableOff,
    required int bitmap,
    required int segmentSize,
  }) {
    if (bitmap == 0) return;
    final segs = <int>[];
    for (var seg = 0; seg < 32; seg++) {
      if ((bitmap >> seg) & 1 == 1) segs.add(seg);
    }
    recordAckConfirm(
        blockStart: durableOff, segs: segs, segmentSize: segmentSize);
  }

  // ---- ACK 分类计数 ----

  int acksOk = 0;
  int acksDuplicate = 0;
  int acksError = 0;
  int acksMalformed = 0;
  int acksNoProgress = 0;
  int acksAbort = 0;

  /// ACK 分类：ok / duplicate / error / malformed / noProgress / abort。
  /// 重复、无推进、错误与畸形 ACK 不产生样本，只计数（fail-closed 留痕）。
  void recordAckClass(String kind) {
    switch (kind) {
      case 'ok':
        acksOk++;
        break;
      case 'duplicate':
        acksDuplicate++;
        break;
      case 'error':
        acksError++;
        break;
      case 'malformed':
        acksMalformed++;
        break;
      case 'noProgress':
        acksNoProgress++;
        break;
      case 'abort':
        acksAbort++;
        break;
    }
  }

  // ---- durable 推进 ----

  final List<int> durableTimesUs = [];
  final List<int> durableOffsets = [];

  /// durable 推进事件（单调去重；含 resume BEGIN ACK 带回的权威进展）。
  void recordDurableAdvance(int off) {
    if (durableOffsets.isNotEmpty && off <= durableOffsets.last) return;
    durableOffsets.add(off);
    durableTimesUs.add(nowUs());
    _emitSample('durable', nowUs(), extra: 'off=$off');
  }

  // ---- GATT 写 / 服务发现 / 平台写 ----

  final List<int> gattWriteDurationsUs = [];
  int gattWriteBytes = 0;
  int gattWriteErrors = 0;

  /// 一次 OTA GATT 写方法调用（writeOtaCharacteristicByAddress 整体，
  /// channel 层观测点）。
  void recordGattWrite({
    required int durationUs,
    required int bytes,
    bool error = false,
  }) {
    gattWriteDurationsUs.add(durationUs);
    gattWriteBytes += bytes;
    if (error) gattWriteErrors++;
    _emitSample('gatt_write', durationUs,
        extra: 'bytes=$bytes${error ? ' error=1' : ''}');
  }

  final List<int> discoverDurationsUs = [];

  /// 一次服务发现调用（discoverServices()，含移动端逐分片写路径内的
  /// 重复发现——P3-4 待测热点归因数据）。
  void recordDiscover({required int durationUs}) {
    discoverDurationsUs.add(durationUs);
    _emitSample('discover', durationUs);
  }

  final List<int> platformWriteDurationsUs = [];
  int platformWriteBytes = 0;

  /// 一次平台特征写（移动端 ch.write / Windows adapter.writeCharacteristic）
  /// ——与 GATT 写方法计时的差值即发现/查找开销。
  void recordPlatformWrite({required int durationUs, required int bytes}) {
    platformWriteDurationsUs.add(durationUs);
    platformWriteBytes += bytes;
    _emitSample('platform_write', durationUs, extra: 'bytes=$bytes');
  }

  // ---- 导出 ----

  /// nearest-rank 分位数（OTA-XC-BLE-TUNING 冻结口径：升序第
  /// ceil(q*N) 个，不插值不删样本；N 为 0 时返回 null）。
  static int? nearestRank(List<int> samples, double q) {
    if (samples.isEmpty) return null;
    final sorted = [...samples]..sort();
    final rank = math.max(1, (q * sorted.length).ceil());
    return sorted[rank - 1];
  }

  /// ACK 样本完整性：`complete` 或 `partial:missing=N`。
  ///
  /// 分母为**已实际发送**的唯一段（resume 位图跳过段未发送、无起点，
  /// 不计入）；outcome=ok 但存在已发送无样本段时如实报 partial。
  String get ackSampleIntegrity {
    final missing = _sentOffsets.length - _sampledOffsets.length;
    return missing > 0 ? 'partial:missing=$missing' : 'complete';
  }

  /// 已发送唯一段数。
  int get segmentsUnique => _sentOffsets.length;

  /// 重传 DATA 帧数 = 累计发送次数 − 唯一段数。
  int get retransmitFrames =>
      segmentSendTotal - _sentOffsets.length;

  Map<String, dynamic> toJson() {
    final bindPhase = _phases['bind'];
    return <String, dynamic>{
      'schema': 1,
      'label': label,
      'device': device,
      'clock': 'stopwatch-mono-us',
      'phases': {
        for (final e in _phases.entries)
          e.key: e.value.length == 2 ? [e.value[0], e.value[1]] : [e.value[0]],
      },
      'bind': {
        'charsUs': _charsDiscoveryUs,
        'found': _charsFound,
        'mtuRequested': _mtuRequested,
        'mtuChunkBytes': _mtuChunkBytes,
        'mtuUs': _mtuUs,
        'subscribeUs': _subscribeUs,
        'subscribeOk': _subscribeOk,
        'phaseUs': bindPhase != null && bindPhase.length == 2
            ? bindPhase[1] - bindPhase[0]
            : null,
      },
      'getInfo': {
        'calls': _getInfoDurationsUs.length,
        'totalUs': _getInfoDurationsUs.fold(0, (a, b) => a + b),
      },
      'transfer': {
        'startUs': _transferStartUs,
        'endAckUs': _endAckArrivalUs,
        'elapsedUs': (_transferStartUs != null && _endAckArrivalUs != null)
            ? _endAckArrivalUs! - _transferStartUs!
            : null,
        'outcome': _transferOutcome,
        'segmentsUnique': _sentOffsets.length,
        'segmentSendTotal': segmentSendTotal,
        'retransmitFrames': retransmitFrames,
        'acks': {
          'ok': acksOk,
          'duplicate': acksDuplicate,
          'error': acksError,
          'malformed': acksMalformed,
          'noProgress': acksNoProgress,
          'abort': acksAbort,
        },
        'ackSamples': ackSampleIntegrity,
        'ackLatency': {
          'count': ackLatencySamplesUs.length,
          'minUs': ackLatencySamplesUs.isEmpty
              ? null
              : ackLatencySamplesUs.reduce(math.min),
          'p50Us': nearestRank(ackLatencySamplesUs, 0.50),
          'p95Us': nearestRank(ackLatencySamplesUs, 0.95),
          'p99Us': nearestRank(ackLatencySamplesUs, 0.99),
          'maxUs': ackLatencySamplesUs.isEmpty
              ? null
              : ackLatencySamplesUs.reduce(math.max),
        },
        'durable': {
          'events': durableOffsets.length,
          'finalOff': durableOffsets.isEmpty ? null : durableOffsets.last,
        },
      },
      'gattWrites': {
        'calls': gattWriteDurationsUs.length,
        'bytes': gattWriteBytes,
        'errors': gattWriteErrors,
        'minUs': gattWriteDurationsUs.isEmpty
            ? null
            : gattWriteDurationsUs.reduce(math.min),
        'p50Us': nearestRank(gattWriteDurationsUs, 0.50),
        'p95Us': nearestRank(gattWriteDurationsUs, 0.95),
        'maxUs': gattWriteDurationsUs.isEmpty
            ? null
            : gattWriteDurationsUs.reduce(math.max),
      },
      'discovers': {
        'calls': discoverDurationsUs.length,
        'minUs': discoverDurationsUs.isEmpty
            ? null
            : discoverDurationsUs.reduce(math.min),
        'p50Us': nearestRank(discoverDurationsUs, 0.50),
        'p95Us': nearestRank(discoverDurationsUs, 0.95),
        'maxUs': discoverDurationsUs.isEmpty
            ? null
            : discoverDurationsUs.reduce(math.max),
      },
      'platformWrites': {
        'calls': platformWriteDurationsUs.length,
        'bytes': platformWriteBytes,
        'minUs': platformWriteDurationsUs.isEmpty
            ? null
            : platformWriteDurationsUs.reduce(math.min),
        'p50Us': nearestRank(platformWriteDurationsUs, 0.50),
        'p95Us': nearestRank(platformWriteDurationsUs, 0.95),
        'maxUs': platformWriteDurationsUs.isEmpty
            ? null
            : platformWriteDurationsUs.reduce(math.max),
      },
    };
  }

  bool _summaryEmitted = false;

  /// 输出一次 `OTA_LINK_STATS {json}` 聚合摘要（幂等，仅首次调用生效）。
  ///
  /// 输出必须是 jsonEncode 的规范 JSON（单行），供日志采集侧直接解析；
  /// 不得退化为 Dart Map.toString（键无引号，分析侧无法解析）。
  void emitSummary() {
    if (_summaryEmitted) return;
    _summaryEmitted = true;
    debugPrint('OTA_LINK_STATS ${convert.jsonEncode(toJson())}');
  }

  void _emitSample(String kind, int us, {String extra = ''}) {
    final line = StringBuffer('OTA_LINK_SAMPLE label=$label kind=$kind us=$us');
    if (extra.isNotEmpty) {
      line.write(' ');
      line.write(extra);
    }
    debugPrint(line.toString());
  }
}
