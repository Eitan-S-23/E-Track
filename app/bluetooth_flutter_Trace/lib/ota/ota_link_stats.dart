import 'dart:convert' as convert;

import 'dart:math' as math;

import 'ota_diagnostics.dart';

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
///   日志输出发生在时间戳之后。帧间日志会轻微拉长传输总时长；外层计时
///   （如 GATT 写外壳）**包含**其内部记录点与日志开销，因此所有对照组合
///   必须使用同一插桩版本（同一提交），不同调用次数下的开销不可视为相等。
/// - **fail-closed 完整性**：`outcome=ok` 的传输若存在已发送但无 ACK 样本
///   的段，摘要如实输出 `partial:missing=N` 而非静默缺行；确认早于首发
///   登记、无合法起点的观测另计 `early=M` 并留痕，不截负时间、不造样本。
/// - **失败可见**：早退、异常与取消都必须经 [recordFailure] 留下终结后的
///   阶段/原因；未进入传输的失败不得伪装成成功传输。
///
/// 日志契约（logcat 采集）：
/// - `OTA_LINK_SAMPLE label=<upgrade|probe|query> kind=<...> us=<n> [off=<n>] ...`
///   逐事件流式输出（原始样本，跨轮合并的原料）；
/// - `OTA_LINK_STATS {json}` 每绑定结束时输出一次聚合摘要（幂等，仅首次）。
/// - `OTA_LINK_RETIRE label=<...> attempt=<n|-> reason=<...> us=<n>` 与
///   `OTA_LINK_LATE label=<...> attempt=<n|-> kind=<...> us=<n> [extra]`：
///   观测流封存标记与其后的迟到观测（见 [retire]）。两种前缀都不在解析器
///   契约的样本/摘要前缀内，按既定解析语义被忽略——封存只改变**归属**，
///   不改变任何既有行的字段或数值语义。
///
/// ACK 延迟样本语义（OTA-XC-BLE-TUNING 冻结定义的工程映射）：
/// 从该段**首次完整发送结束**（`recordSegmentSendEnd` 首次记录该字节偏移）
/// 到**首个由 durable_off/bitmap 明确确认该段的有效 ACK 到达**
/// （`recordAckConfirm` / `recordBitmapConfirm` / `recordResumeConfirm`）。
/// 多个段可共享同一确认（终点同、起点各异）；重复、无推进、错误与畸形 ACK
/// 不产生样本（在 ACK 分类计数中如实登记）；重传不创建新样本（首发结束
/// 时刻不变）。确认先于首发登记到达时不存在合法起点，该观测作废并计数
/// （`ackEarlyInvalid`），既不截负时间也不让迟到重复确认补造样本。
class OtaLinkStats {
  OtaLinkStats({
    required this.label,
    this.device,
    this.attempt,
    int Function()? clockUs,
  }) : _clockUs = clockUs;

  /// 绑定用途：升级传输 / 重启探测 / 身份查询。
  final String label;

  /// 目标设备地址（仅标识用，不参与任何判据）。
  final String? device;

  /// 重启探测的重连轮次序号（1 起；非探测路径为 null）。
  ///
  /// 每次连接尝试必须是独立实例：绑定阶段字段（发现/MTU/订阅）幂等只记
  /// 首次，共享实例会让首轮失败值污染后续轮次的最终摘要。
  final int? attempt;

  late final Stopwatch _clock = Stopwatch()..start();

  /// 测试注入的时钟（微秒）。生产路径恒为 null。
  ///
  /// 只为判定性用例提供可控时序（到达戳必须等于分发时刻而非写结算时刻，
  /// 只有可控时钟能给出精确断言）；注入后 [nowUs] 与所有经它取的时间戳
  /// 一并改为该时钟，实例内仍是单一时钟域。
  final int Function()? _clockUs;

  /// 实例内单调时钟（微秒）。同实例内时间戳同源。
  int nowUs() {
    final injected = _clockUs;
    if (injected != null) return injected();
    return _clock.elapsedMicroseconds;
  }

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
  String? _charsWriteMode;
  int _mtuRequested = 0;
  int _mtuChunkBytes = 0;
  int? _mtuUs;
  String? _mtuSource;
  int? _subscribeUs;
  bool _subscribeOk = false;

  /// OTA 特征发现（findExact 整体）耗时与结果；幂等只记首次。
  ///
  /// [writeMode] 为绑定实际使用的写模式（writeWithResponse /
  /// writeWithoutResponse / unknown），用于核查写模式是否与预期混组。
  void recordCharsDiscovery({
    required int durationUs,
    required bool found,
    String? writeMode,
  }) {
    if (_charsDiscoveryUs != null) return;
    _charsDiscoveryUs = durationUs;
    _charsFound = found;
    _charsWriteMode = writeMode;
  }

  /// MTU 协商结果：请求值与协商后的单次写入净荷上限。
  ///
  /// [source] 记录该净荷上限的来源（windows-stack-managed /
  /// device-missing / negotiated / negotiated-too-small / error-fallback）：
  /// 回退值与真实协商值同为 20，没有来源就无法区分二者。
  void recordMtu({
    required int requested,
    required int chunkBytes,
    required int durationUs,
    String? source,
  }) {
    if (_mtuUs != null) return;
    _mtuRequested = requested;
    _mtuChunkBytes = chunkBytes;
    _mtuUs = durationUs;
    _mtuSource = source;
  }

  /// OTA 通知订阅耗时与结果；幂等只记首次。
  void recordSubscribe({required int durationUs, required bool ok}) {
    if (_subscribeUs != null) return;
    _subscribeUs = durationUs;
    _subscribeOk = ok;
  }

  // ---- GET_INFO 往返 ----

  final List<int> _getInfoDurationsUs = [];
  int _getInfoFailures = 0;

  /// 一次 GET_INFO 往返（含实例内部的有界重试）。
  ///
  /// [ok] 为 false 时同样登记耗时与失败次数：失败往返同样消耗链路时间，
  /// 不能因为「没有身份值可采」就从统计中消失。
  void recordGetInfo({required int durationUs, bool ok = true}) {
    final extra = ok ? 'ok=1' : 'ok=0';
    if (!_startObservation('get_info', durationUs, extra: extra)) return;
    _getInfoDurationsUs.add(durationUs);
    if (!ok) _getInfoFailures++;
    _emitSample('get_info', durationUs, extra: extra);
  }

  // ---- 失败分类（早退 / 异常 / 取消的统一留痕）----

  String? _failureStage;
  String? _failureReason;

  /// 记录本实例终结的失败阶段与原因（幂等，只记首次）。
  ///
  /// 早退（特征不存在、绑定返回 null、取消、身份不一致）不经异常路径，
  /// 也必须留下终结摘要与原因；未进入传输的失败不得伪装成成功传输。
  void recordFailure({required String stage, required String reason}) {
    _failureStage ??= stage;
    _failureReason ??= reason;
  }

  // ---- 重连尝试结论（probe 多轮归属）----

  final List<String> _attemptOutcomes = [];
  int? _attemptOutcomeUs;

  /// 本轮重连尝试的结论（completed / abandoned / cancelled / error /
  /// no_verdict）。每轮独立实例，轮次结论不与后续轮次混组。
  ///
  /// 导出时每条记为一个 `{'n': 序号, 'outcome': ...}`：序号是**尝试序号**
  /// （轮次外壳按记录顺序递增；单轮实例取 [attempt]），不是本实例内的
  /// 数组下标。
  void recordAttemptOutcome(String outcome) {
    _attemptOutcomes.add(outcome);
    _attemptOutcomeUs ??= nowUs();
  }

  // ---- 废弃尝试的观测流封存（P34-DA03）----

  String? _retiredReason;
  int? _retiredUs;

  /// 本实例的观测流是否已封存（封存后不再产生 `OTA_LINK_SAMPLE`）。
  bool get retired => _retiredReason != null;

  /// 封存观测流：此后到达的观测一律记为显式迟到记录，不再进入样本流。
  ///
  /// 适用场景是**被放弃的重连尝试**：`.timeout` 只放弃 Future，平台发现
  /// 调用仍在飞行，其回调稍后仍会落到本实例（`recordDiscover` /
  /// `recordCharsDiscovery` 等）并在此实例上产生样本行。若继续按普通样本
  /// 输出，这些迟到样本会落在**下一轮尝试**的摘要块内：解析器按块内计数
  /// 核对会把它们判为 STRAGGLER（"样本归属不明，不得进入任何数值池"），
  /// 结果是下一轮的合法观测被降级、本轮的迟到观测又无法归属。
  ///
  /// 封存后：
  /// - 迟到观测仍被**完整记录**（kind、耗时/字节与到达时刻都不丢），只是
  ///   改走 `OTA_LINK_LATE label=<label> attempt=<n> kind=<...> us=<n>`；
  ///   该前缀不在解析器契约的样本/摘要前缀内，按既定语义被解析器忽略，
  ///   因此既不污染任何数值池，也不被静默丢弃。
  /// - **数值池与统计计数同时停止吸收**（见 [_startObservation]）：只写
  ///   `OTA_LINK_LATE` 行，不再改变任何样本列表、次数计数与字节累计。本
  ///   实例的终结摘要在封存时刻已经发射且不可重发，迟到数值既进不了那份
  ///   摘要，又会被误读成本轮（已放弃轮次）的合法统计。
  /// - 轮次自身的账目仍照常登记：[recordAttemptOutcome]、[phaseEnd]、
  ///   [recordFailure]、[emitSummary] 与传输/绑定字段（[recordTransferStart]、
  ///   [recordCharsDiscovery]、[recordMtu]、[recordSubscribe]）不属观测流，
  ///   它们只服务本实例自己的那份摘要，不会跨轮次串扰。
  /// - [emitSummary] 仍然按幂等规则输出本实例的**唯一**终结摘要（封存不
  ///   代替摘要，否则被放弃的尝试会失去 `attempts[].outcome=abandoned`
  ///   与失败阶段字段）；摘要内 `retired` 段说明该实例已被封存及原因。
  ///
  /// 幂等：重复调用只保留首次原因与时刻。
  void retire({required String reason}) {
    if (_retiredReason != null) return;
    _retiredReason = reason;
    _retiredUs = nowUs();
    emitOtaObservation('OTA_LINK_RETIRE label=$label attempt=${attempt ?? '-'} '
        'reason=$reason us=$_retiredUs');
  }

  // ---- 传输阶段（BEGIN 首帧写 → END ACK 到达）----

  int? _transferStartUs;
  int? _endAckArrivalUs;
  String? _transferOutcome;

  /// Shared origin for diagnostic prefix timing; never an END substitute.
  int? get transferStartUs => _transferStartUs;

  /// 传输起点：本 transfer 首个 BEGIN 帧**写调用开始**（幂等）。
  ///
  /// 契约口径（`docs/ota-cross-system-contracts.md`，XC-BLE-THROUGHPUT）是
  /// 「从 BEGIN 首字节开始发送到成功 END ACK 完整到达」。Dart 侧唯一可观测
  /// 的代理点就是**写调用发起时刻**：它不晚于首字节真正上线，且早于写串行
  /// 队列排队、帧分片与平台写回调，因此本实现测得的传输时长是契约时长的
  /// **保守上界**（只会偏长）。调用方必须在写调用时刻记录，不得在排队完成
  /// 后才记；映射与队列行为的完整声明见
  /// `docs/ota-exec-notes/P3-4-da-remediation-2026-09-18.md`（源注释不改写
  /// 契约文本）。
  void recordTransferStart() {
    _transferStartUs ??= nowUs();
    phaseStart('transfer');
  }

  /// END ACK 完整到达（**仅在本次请求的 END ACK 经 waiter 关联校验与
  /// payload/durable 校验、被采信为本次传输的成功终点时**调用）。
  ///
  /// [atUs] 必须是该应答帧**到达分发点**时记录的同源时刻（等待者在
  /// 采信匹配帧的同一同步块内打戳），不得在本次调用处另取时钟：写 Future
  /// 结算、ACK 解析与校验、日志输出都发生在到达之后，用它们之后的时刻会
  /// 把写结算延迟与处理开销算进传输时长（P34-DA01）。参数为必填而非
  /// 回退取时钟，就是为了让「事后补时刻」无法编译通过。
  ///
  /// 不采用「帧分发时看到 cmd==ACK_END 即覆盖」：无关、重复或非法的 END
  /// 应答不得覆盖成功终点的时刻。
  void recordEndAckArrival({required int atUs}) {
    _endAckArrivalUs = atUs;
  }

  /// 传输终态（幂等）：成功 true / 失败 false（错误码由上层 catch 补记）。
  ///
  /// 语义是**整轮传输阶段**的结论，而非「是否调用过 transfer」：未进入
  /// 传输就失败的轮次（特征缺失、绑定失败、取消、异常）同样以 fail 收尾，
  /// 否则只看本字段的消费者会把整轮失败读成"没发生过传输"（P34-R05）。
  /// 是否真的开始过传输由 [startUs]/[elapsedUs] 是否为空区分。
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

  /// 已收到过有效确认的段（字节偏移），**含尚未登记首发的早到确认**。
  ///
  /// 与 [_sampledOffsets] 的区别：早到确认建立了「该段已被确认」这一事实
  /// （后续迟到重复确认不算新确认），但它不产生样本（无合法起点）。
  final Set<int> _confirmedOffsets = {};

  /// 早到确认时刻（字节偏移 → 该确认到达时刻）。
  ///
  /// 确认先于本段首发发送结束登记到达（同 microtask 内分发的 ACK 或
  /// 跨实例的 resume 前缀确认）。此时不存在合法起点，既不能把负时间截成
  /// 0，也不能让随后登记的首发为迟到重复确认造假样本。
  final Map<int, int> _earlyConfirmUs = {};

  /// 早到确认计数：确认先于首发发送结束登记，无合法起点，不产出样本。
  int ackEarlyInvalid = 0;

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
    final extra = 'off=$offsetBytes len=$lengthBytes';
    final now = nowUs();
    // 封存后不得再登记首发时刻：那会给已放弃轮次补造可配对的 ACK 样本。
    if (!_startObservation(
        _sentOffsets.contains(offsetBytes)
            ? 'segment_retransmit'
            : 'segment_first_send',
        now,
        extra: extra)) {
      return;
    }
    segmentSendTotal++;
    if (_sentOffsets.add(offsetBytes)) {
      _firstSendEndUs[offsetBytes] = now;
      _onSegmentFirstSend(offsetBytes, lengthBytes, now);
    } else {
      _emitSample('segment_retransmit', now, extra: extra);
    }
  }

  /// 首发登记收尾：区分「先被确认」的无效观测与正常首发。
  void _onSegmentFirstSend(int offsetBytes, int lengthBytes, int now) {
    final early = _earlyConfirmUs.remove(offsetBytes);
    if (early != null) {
      // 确认早于发送结束登记：该段永远得不到合法样本（既不截负时间，
      // 也不让随后的迟到重复确认顶替）。显式记为无效观测并留痕。
      ackEarlyInvalid++;
      _emitSample('ack_early_invalid', early, extra: 'off=$offsetBytes');
    }
    _emitSample('segment_first_send', now,
        extra: 'off=$offsetBytes len=$lengthBytes');
  }

  /// ACK 确认集合 → 逐段生成 ACK 延迟样本。
  ///
  /// [blockStart] 为确认时刻 MCU 的块起点（= 更新前 durable_off），
  /// [segs] 为本 ACK 明确确认的块内段号集合（ACK 自身段、durable 前移
  /// 回收的旧块在途段、或 bitmap 置位段）。共享同一 ACK 的段各自成样本。
  /// [atUs] 为该确认的真实到达时刻（缺省取调用时刻）；resume BEGIN 等
  /// 场景必须传「有效 ACK 自身到达的时刻」，而非后续处理时刻。
  void recordAckConfirm({
    required int blockStart,
    required Iterable<int> segs,
    required int segmentSize,
    int? atUs,
  }) {
    final now = atUs ?? nowUs();
    if (_retiredReason != null) {
      // 封存后逐段只留迟到记录：不写确认集合、不更新早到时刻、不产出样本。
      // 判别语句只读封存时的冻结状态，不改变任何统计字段。
      for (final seg in segs) {
        final offset = blockStart + seg * segmentSize;
        final firstEnd = _firstSendEndUs[offset];
        if (firstEnd == null) {
          _emitSample('ack_early', now, extra: 'off=$offset');
        } else {
          _emitSample('ack_latency', now - firstEnd, extra: 'off=$offset');
        }
      }
      return;
    }
    for (final seg in segs) {
      final offset = blockStart + seg * segmentSize;
      if (!_confirmedOffsets.add(offset)) continue; // 已有有效确认
      final firstEnd = _firstSendEndUs[offset];
      if (firstEnd == null) {
        // 早到确认：本段首发尚未登记（或本实例从未发送该段，如 resume
        // 带回的 durable 前缀）。暂挂时刻待判别；若后续登记首发，则记为
        // 无效观测而不补造样本。
        _earlyConfirmUs[offset] = now;
        _emitSample('ack_early', now, extra: 'off=$offset');
        continue;
      }
      if (!_sampledOffsets.add(offset)) continue; // 已采样则不重复
      final latency = now - firstEnd; // 首发已登记 ⇒ 非负，不截断
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
    int? atUs,
  }) {
    if (bitmap == 0) return;
    final segs = <int>[];
    for (var seg = 0; seg < 32; seg++) {
      if ((bitmap >> seg) & 1 == 1) segs.add(seg);
    }
    recordAckConfirm(
      blockStart: durableOff,
      segs: segs,
      segmentSize: segmentSize,
      atUs: atUs,
    );
  }

  /// 续传 BEGIN 的有效确认并集：durable 前缀 + 当前块 bitmap。
  ///
  /// MCU 回带 `durableOff` 意味着 `[0, durableOff)` 已被其明确确认（这些
  /// 段的 DATA ACK 可能丢失）。本实例确实发送过且尚未采样的前缀段在此获得
  /// 真实终点样本；本实例从未发送的前缀段（新实例续传）自然进入早到暂存，
  /// 判为无效观测——**不给未发送的 resume 前缀制造样本**。
  ///
  /// [arrivalUs] 为该有效 ACK 帧**到达分发点**的同源时刻（P34-DA01）：由
  /// 等待者在采信匹配帧的同一同步块内打戳并随结果带回。调用方不得在 await
  /// 返回后另取时钟——写结算、帧解析与校验都发生在到达之后，事后取时刻会
  /// 把它们的开销算进该确认覆盖段的 ACK 延迟。
  void recordResumeConfirm({
    required int durableOff,
    required int bitmap,
    required int segmentSize,
    required int arrivalUs,
  }) {
    if (durableOff > 0) {
      final segCount = durableOff ~/ segmentSize;
      if (segCount > 0) {
        recordAckConfirm(
          blockStart: 0,
          segs: List<int>.generate(segCount, (seg) => seg),
          segmentSize: segmentSize,
          atUs: arrivalUs,
        );
      }
    }
    recordBitmapConfirm(
      durableOff: durableOff,
      bitmap: bitmap,
      segmentSize: segmentSize,
      atUs: arrivalUs,
    );
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
    if (!_startObservation('ack_class', nowUs(), extra: 'class=$kind')) return;
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
    if (!_startObservation('durable', nowUs(), extra: 'off=$off')) return;
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
    final extra = 'bytes=$bytes${error ? ' error=1' : ''}';
    if (!_startObservation('gatt_write', durationUs, extra: extra)) return;
    gattWriteDurationsUs.add(durationUs);
    gattWriteBytes += bytes;
    if (error) gattWriteErrors++;
    _emitSample('gatt_write', durationUs, extra: extra);
  }

  final List<int> discoverDurationsUs = [];
  int discoverErrors = 0;

  /// 一次服务发现调用（discoverServices()，含移动端逐分片写路径内的
  /// 重复发现——P3-4 待测热点归因数据）。
  ///
  /// 失败尝试同样登记（含其耗时与 [error] 计数）：只统计成功的发现会低估
  /// 实际调用次数与链路开销。
  void recordDiscover({required int durationUs, bool error = false}) {
    final extra = error ? 'error=1' : '';
    if (!_startObservation('discover', durationUs, extra: extra)) return;
    discoverDurationsUs.add(durationUs);
    if (error) discoverErrors++;
    _emitSample('discover', durationUs, extra: extra);
  }

  final List<int> platformWriteDurationsUs = [];
  int platformWriteBytes = 0;
  int platformWriteErrors = 0;

  /// 一次平台特征写（移动端 ch.write / Windows adapter.writeCharacteristic）
  /// ——与 GATT 写方法计时的差值即发现/查找开销。失败尝试同样计入。
  void recordPlatformWrite({
    required int durationUs,
    required int bytes,
    bool error = false,
  }) {
    final extra = 'bytes=$bytes${error ? ' error=1' : ''}';
    if (!_startObservation('platform_write', durationUs, extra: extra)) return;
    platformWriteDurationsUs.add(durationUs);
    platformWriteBytes += bytes;
    if (error) platformWriteErrors++;
    _emitSample('platform_write', durationUs, extra: extra);
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

  /// ACK 样本完整性：`complete`，或 `partial:missing=N` /
  /// `partial:early=M` / `partial:missing=N,early=M`。
  ///
  /// 分母为**已实际发送**的唯一段（resume 位图跳过段未发送、无起点，
  /// 不计入）。`missing` = 已发送唯一段数 − 已采样段数；`early` = 确认先于
  /// 首发登记、无合法起点而作废的段数。早到段同时也计入 `missing`
  /// （它们确实缺样本），`early` 只额外说明缺失的原因。
  String get ackSampleIntegrity {
    final missing = _sentOffsets.length - _sampledOffsets.length;
    final parts = <String>[];
    if (missing > 0) parts.add('missing=$missing');
    if (ackEarlyInvalid > 0) parts.add('early=$ackEarlyInvalid');
    return parts.isEmpty ? 'complete' : 'partial:${parts.join(',')}';
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
      'attempt': attempt,
      'clock': 'stopwatch-mono-us',
      'phases': {
        for (final e in _phases.entries)
          e.key: e.value.length == 2 ? [e.value[0], e.value[1]] : [e.value[0]],
      },
      'failure': {
        'stage': _failureStage,
        'reason': _failureReason,
      },
      'attempts': [
        for (var i = 0; i < _attemptOutcomes.length; i++)
          // n 恒为重连尝试序号：轮次外壳按记录顺序递增（每轮一条），
          // 单轮实例直接用其 attempt 序号——同一份 JSON 里 attempt=2
          // 而 n=1 会让归属被读错（P34-R06）。
          {'n': attempt ?? (i + 1), 'outcome': _attemptOutcomes[i]},
      ],
      'attemptEndUs': _attemptOutcomeUs,
      // 封存标记（P34-DA03）：非 null 说明本实例的观测流在 us 时刻被封存，
      // 此后到达的观测只出现在 OTA_LINK_LATE 行，不进入本摘要的数值池。
      'retired': _retiredReason == null
          ? null
          : {'reason': _retiredReason, 'us': _retiredUs},
      'bind': {
        'charsUs': _charsDiscoveryUs,
        'found': _charsFound,
        'writeMode': _charsWriteMode,
        'mtuRequested': _mtuRequested,
        'mtuChunkBytes': _mtuChunkBytes,
        'mtuSource': _mtuSource,
        'mtuUs': _mtuUs,
        'subscribeUs': _subscribeUs,
        'subscribeOk': _subscribeOk,
        'phaseUs': bindPhase != null && bindPhase.length == 2
            ? bindPhase[1] - bindPhase[0]
            : null,
      },
      'getInfo': {
        'calls': _getInfoDurationsUs.length,
        'failures': _getInfoFailures,
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
        'ackEarlyInvalid': ackEarlyInvalid,
        'ackEarlyUnsent': _earlyConfirmUs.length,
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
        'errors': discoverErrors,
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
        'errors': platformWriteErrors,
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
    emitOtaObservation('OTA_LINK_STATS ${convert.jsonEncode(toJson())}');
  }

  /// 观测入账闸门（封存语义见 [retire]）：未封存返回 true，调用方照常登记
  /// 数值池与计数；已封存则只写一条显式迟到记录并返回 false，调用方必须
  /// 立即返回，**不得**改动任何样本列表、次数计数或字节累计。
  ///
  /// 封存后仍要写行，是为了让"被放弃轮次里到底还发生了什么"不依赖行序、
  /// 不被静默丢弃：`OTA_LINK_LATE` 自带 label 与 attempt，可独立归属。
  bool _startObservation(String kind, int us, {String extra = ''}) {
    if (_retiredReason == null) return true;
    _emitSample(kind, us, extra: extra);
    return false;
  }

  void _emitSample(String kind, int us, {String extra = ''}) {
    // 封存后的观测走显式迟到通道（见 [retire]）：样本行必须停止产出，
    // 否则它会归属到下一轮尝试的摘要块。迟到记录同样带 label/attempt，
    // 归属不依赖上下文行序。
    final prefix = _retiredReason == null ? 'OTA_LINK_SAMPLE' : 'OTA_LINK_LATE';
    final line = StringBuffer('$prefix label=$label');
    if (_retiredReason != null) line.write(' attempt=${attempt ?? '-'}');
    line.write(' kind=$kind us=$us');
    if (extra.isNotEmpty) {
      line.write(' ');
      line.write(extra);
    }
    emitOtaObservation(line.toString());
  }
}
