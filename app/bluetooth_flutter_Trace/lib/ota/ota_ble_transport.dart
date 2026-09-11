import 'dart:async';
import 'dart:typed_data';

import 'ota_ble_codec.dart';
import 'ota_device_info.dart';

/// OTA BLE 传输测试注入点：生产实现绑定 flutter_blue_plus 的真实特征，
/// 测试用 fake 模拟 MCU 行为（ACK、丢帧、乱序、断连）。
abstract class OtaBleChannel {
  /// 向 FFF2（写特征）写入一个分片。返回写入是否成功。
  Future<void> writeChunk(List<int> chunk);

  /// 订阅 FFF1（通知特征）的原始字节流（可能一帧跨多个通知分片）。
  Stream<List<int>> get notifications;

  /// 当前可用的单次写入净荷上限（协商 MTU - 3）。无连接时为 0。
  Future<int> maxWriteChunkSize();

  /// 连接是否可用（fake 用于模拟断连）。
  bool get isConnected;

  /// 本通道所面向的**设备作用域句柄**（RC3-05⑤）。
  ///
  /// 同一台设备（同地址）在进程内必须恒定返回同一个对象，**BLE 重连
  /// 不得返回新对象**。传输层用它界定写通道废弃标记的作用域：悬空半帧
  /// 留在 MCU 的 UART 帧解析器里（`ota_ble_session_t::demux.parser`），
  /// 而 BLE 连接事件不复位它——`ota_ble_session.c` 的 `session_teardown`
  /// 不动 `session->demux`，`ota_ble_demux_init` 只在开机
  /// `ota_ble_session_init` 调用一次；解析器只在「本帧被吃完（CRC 通过
  /// 或失败）」时自复位（`ota_ble_frame.c` PAYLOAD/CRC 态）。因此重连
  /// 后的新连接面对的是同一个悬空解析器，标记不能随链路代次失效。
  ///
  /// 返回 null 表示无法区分，此时退化按通道对象自身隔离。
  Object? get deviceScope;
}

/// OTA BLE 传输 owner（冻结依据 docs/ota-binary-contracts.md §5、§4.5，
/// docs/ota-cross-system-contracts.md OTA-XC-FLUTTER-TRANSPORT、
/// OTA-XC-BLE-LIFECYCLE、OTA-XC-CANCEL-RECOVERY、OTA-XC-RETRY-POLICY）。
///
/// 职责（不含连接管理——特征发现与重连由 OtaService/BluetoothService 编排）：
/// - 帧分片：单帧按 maxWriteChunkSize() 切片写入；
/// - credit 窗口：一次只发当前 4KB 块（32 段），在途未确认段数受
///   INFO.max_window_segs 与冻结 4KB 窗口共同约束；
/// - durable 进度：只认 MCU ACK 的 durable_off/block_bitmap；
/// - 断点续传：重连后 BEGIN 同 package_sha256，按 bitmap 补发缺口段；
/// - ACK 关联：MCU 应答回显请求 seq（BEGIN ACK 帧头 session 是新会话），
///   按 cmd+session+seq 精确关联，异步 ACK_ABORT 同样分发；
/// - 可恢复错误（ERR_SEQ/ERR_SESSION/ERR_STATE）有界重新 BEGIN 续传。
class OtaBleTransport {
  OtaBleTransport({
    required OtaBleChannel channel,
    this.ackTimeout = defaultAckTimeout,
    this.retries = maxRetries,
    this.noProgressTimeout = defaultNoProgressTimeout,
    this.writeTimeout = defaultWriteTimeout,
  })  : _channel = channel {
    // 通知流订阅必须在构造内同步建立：async* 生成器的初始运行被延迟到
    // 微任务，此前「写入回调里同步回投的 ACK」在 broadcast 通知源上
    // 因无监听者被整帧丢弃（真实 BLE 通知流即 broadcast 语义）。显式
    // 订阅在构造返回前生效，零竞态；同时避免 async* 取消协议在
    // 「生成器尚未启动即 dispose」时 cancel 永不完成的挂死。
    _frameSub = channel.notifications.listen(
      _onNotifyChunk,
      onError: _dispatchError,
    );
  }

  final OtaBleChannel _channel;
  late final StreamSubscription<List<int>> _frameSub;
  /// 通知字节流的跨 chunk 重组缓冲（半帧回存，PR03）。
  final BytesBuilder _frameBuffer = BytesBuilder();

  /// 单次 ACK 等待超时。冻结推导规则为 clamp(3*P99_ACK, 500ms, 2000ms)
  /// （OTA-XC-RETRY-POLICY；P99 由 P3-4 实测产出前默认取上限 2000ms，
  /// 生产值由 OtaService 注入，不得超出 500..2000ms 范围）。
  static const Duration defaultAckTimeout = Duration(milliseconds: 2000);
  /// 有界重发/续传次数上限（OTA-XC-RETRY-POLICY）。
  static const int maxRetries = 5;
  /// 无 durable 进展的中止窗口（OTA-XC-RETRY-POLICY：30 秒）。
  static const Duration defaultNoProgressTimeout = Duration(seconds: 30);
  /// 单次 GATT 写等待上限（RC2-05）：写通道卡死不得无限阻塞传输循环。
  static const Duration defaultWriteTimeout = Duration(seconds: 10);

  final Duration ackTimeout;
  final int retries;
  final Duration noProgressTimeout;
  final Duration writeTimeout;

  /// 帧等待者队列（一问一答）：注册后才开始发送，响应到达即分发。
  final List<_FrameWaiterBase> _waiters = [];
  /// 传输期 ACK 视图：持续消费每段 ACK，不占用一问一答等待者。
  _TransferAckView? _ackView;

  int _seq = 0;
  // 会话外查询（GET_INFO，session=0）使用独立 seq 空间（RC3-08⑦）。
  // 合同 §5.1 定义 seq 为「会话内」帧序号，MCU 会话层对 BEGIN/DATA/END
  // 严格连续校验（ota_ble_session.c session_seq_check）；GET_INFO 不参与
  // 会话状态（§5.2，session=0，seq 仅作应答回显关联）。传输在途的后台
  // 恢复复核会发 GET_INFO——若它从会话计数器取号，后续 DATA 将整体跳号
  // 被 ERR_SEQ 拒绝，触发内部 ABORT+BEGIN 重对齐并从 durable 整段重发；
  // 只读复核不得破坏被复核的传输。该空间按**设备**分配而不是按实例
  // （RC3-05⑤），见 [_nextQuerySeq] 与 [_DeviceWriteLedger.nextQuerySeq]。
  int _session = 0;
  bool _busy = false;
  bool _cancelled = false;
  bool _disposed = false;

  int get session => _session;
  /// 本实例是否已被取消（取消后代次失效，禁止复用，由上层重建）。
  bool get isCancelled => _cancelled;

  /// 发送 GET_INFO 并解析身份。连接不可用或超时抛 [OtaTransportException]。
  /// INFO payload 链路损坏（MALFORMED_INFO）有界重发；身份不符是确定性
  /// 错误，直接抛 [OtaDeviceIdentityException]。
  ///
  /// 写通道处于废弃态（RC3-05⑤）时，本调用是唯一放行的出站流量，并按
  /// 重新同步探针处理：GET_INFO 帧本身可能整帧落进悬空帧的 payload 被吞掉，
  /// 因此按 [maxResyncProbes] / [resyncProbeTimeout] 有界重试，直到收到
  /// 一个**属于当前废弃世代、且发出时设备上没有在途旧物理写**的探针的
  /// INFO 应答——那才是「MCU 解析器已重新同步」的正向证明。探针预算
  /// （[maxResyncProbes] × [resyncProbeTimeout]，含等待在途旧写结算的开销）
  /// 用尽仍无证据即抛错，标记保持废弃，绝不假装恢复。
  Future<DeviceOtaInfo> getDeviceInfo(
      {Duration timeout = const Duration(seconds: 10)}) async {
    var attempts = 0;
    var probes = 0;
    // 废弃探针序列的端到端预算（RC3-05⑤）：次数上限 × 单次上限。它与
    // 调用方的 [timeout] 是两件事——后者描述「一次往返」的合理等待，直接
    // 拿它当整段探针序列的上界，会在最坏情形（悬空帧需约 14 次探针才被
    // 吃满，≈11s）提前放弃一个正在收敛的恢复过程。取两者较大值：既有硬
    // 上界，又不因调用方给了个短超时而缩掉既有的恢复能力。等待在途旧物理
    // 写的开销也计入同一预算，不再是「探针之外的无界第三段等待」。
    final probeBudget = resyncProbeTimeout * maxResyncProbes;
    final budget = timeout > probeBudget ? timeout : probeBudget;
    final clock = Stopwatch()..start();
    Duration remaining() {
      final left = budget - clock.elapsed;
      return left.isNegative ? Duration.zero : left;
    }

    while (true) {
      _checkUsable();
      final poisoned = _writeChannelPoisoned;
      if (poisoned && remaining() == Duration.zero) {
        throw const OtaTransportException(
            '写通道废弃：探针总时限内未取得重新同步证据（cmd=0x1）',
            code: 'TIMEOUT');
      }
      // 会话外查询取号（RC3-08⑦）：不消耗会话 seq 空间，见 _nextQuerySeq。
      final seq = _nextQuerySeq();
      final frame = OtaBleCodec.encodeCommand(
        cmd: OtaBleCodec.cmdGetInfo,
        session: 0,
        seq: seq,
      );
      // INFO 应答：session=0、seq 回显请求 seq（§5.6）。
      // late：下面的 catch 只会 rethrow 或 continue，赋值失败路径不会落到读取。
      late final Uint8List payload;
      try {
        payload = await _roundTrip(
          frame,
          OtaBleCodec.rspInfo,
          session: 0,
          seq: seq,
          timeout: poisoned
              ? (resyncProbeTimeout < remaining()
                  ? resyncProbeTimeout
                  : remaining())
              : timeout,
          resyncProbeSeq: seq,
        );
      } on OtaTransportException catch (e) {
        // 只有废弃态才把超时解释为「探针被悬空帧吞掉」：此时本探针是
        // 把悬空帧吃满、逼解析器自复位的唯一手段，重试才算进展。正常
        // 链路超时照旧上抛，不改变既有语义。
        if (!poisoned ||
            e.code != 'TIMEOUT' ||
            ++probes >= maxResyncProbes) {
          rethrow;
        }
        // 重试前先等设备上的旧物理写结算（RC3-05⑤）：只要它们还在途，
        // 下一个探针即使被解析也不能作为解除证据（见
        // [_resyncProbeAuthoritative]），先等它们落地再取证才有意义。
        await _awaitDeviceWritesIdle(remaining());
        continue;
      }
      if (poisoned && _writeChannelPoisoned) {
        // 应答到了、废弃却没解除：本探针发出时仍有在途旧物理写（或其间
        // 发生了重新废弃），其 INFO 不构成重新同步证据。不能把 payload
        // 当成功返回——上层据此认为链路可信，而迟到的旧分片随后仍会污染
        // 新会话。等旧写结算后用**新的**探针重新取证。
        if (++probes >= maxResyncProbes) {
          throw const OtaTransportException(
              '写通道废弃：探针预算耗尽仍未在无在途旧写时取得重新同步证据',
              code: 'TIMEOUT');
        }
        await _awaitDeviceWritesIdle(remaining());
        continue;
      }
      try {
        return DeviceOtaInfo.fromInfoPayload(payload);
      } on OtaDeviceIdentityException catch (e) {
        if (e.code != 'MALFORMED_INFO' || ++attempts > retries) {
          rethrow;
        }
      }
    }
  }

  /// 发送 BEGIN 携带包身份，解析 ACK（10B，含 session）。
  /// status != OK 时抛 [OtaTransportException]（携带 status）。
  /// 成功后记录新 session（RC3-03）：独立 begin 的后续 abort/错误帧
  /// 必须携带本会话 session，而非残留的 0。
  Future<OtaBeginAck> begin({
    required int totalLen,
    required List<int> packageSha256,
    required List<int> etuHeader,
    Duration timeout = defaultAckTimeout,
  }) async {
    final ack = await _beginRoundTrip(
      totalLen: totalLen,
      packageSha256: packageSha256,
      etuHeader: etuHeader,
      timeout: timeout,
    );
    _session = ack.session;
    return ack;
  }

  /// 传输完整包：credit 窗口推进 + 断点续传消费。
  ///
  /// [package] 是已通过 SHA-256 校验的完整 ETU 包字节；
  /// [windowSegments] 是 INFO.max_window_segs 报告的在途段上限（内部
  /// clamp 到 1..32；缺省 32 = 冻结 4KB 块窗口）；
  /// [onDurableProgress] 只在 ACK durable_off 前进时回调（UI durable 进度）；
  /// [onSent] 在每个段写入后回调（GATT 写入活跃度参考，含重发）。
  /// 返回最终 END ACK（status==OK 即包传输完成；成功重启与目标身份
  /// 复核由上层编排，见 OTA-XC-FLUTTER-TRANSPORT 调用顺序）。
  Future<OtaAckResult> transfer({
    required Uint8List package,
    required List<int> packageSha256,
    required List<int> etuHeader,
    int? windowSegments,
    void Function(int durableOff, int total)? onDurableProgress,
    void Function(int sentBytes, int total)? onSent,
  }) async {
    if (_busy) {
      throw const OtaTransportException('transport 忙：会话进行中', code: 'BUSY');
    }
    _checkUsable();
    _busy = true;
    final effectiveWindow = (windowSegments ?? OtaBleCodec.segmentsPerBlock)
        .clamp(1, OtaBleCodec.segmentsPerBlock);
    final view = _TransferAckView(
      blockSize:
          OtaBleCodec.segmentsPerBlock * OtaBleCodec.dataSegmentSize,
      segmentSize: OtaBleCodec.dataSegmentSize,
    );
    _ackView = view;
    // 无 durable 进展总预算（RC3-07）：单调时钟实例字段，覆盖 transfer
    // 全部等待点；预算跨 BEGIN/resume 保留（重新 BEGIN 本身不算进展），
    // 只在 durable 前进时 reset；finally 清空解除对后续命令的约束。
    _noProgressClock = Stopwatch()..start();
    try {
      final total = package.length;
      var resumeLeft = retries; // ERR_SEQ/ERR_SESSION/ERR_STATE → ABORT+BEGIN
      var sentBytes = 0;
      var lastDurable = 0; // 跨 BEGIN 保留：resume 不得倒退（RC3-06）
      var needsResume = false;
      while (true) {
        _checkUsable();
        _checkNoProgress();
        // ---- BEGIN（同 package_sha256 幂等：MCU 返回当前进度）----
        // 注意 MCU 真值（ota_ble_session.c:377）：同包重复 BEGIN 不重置
        // expected_seq。因此 resume 必须先 ABORT teardown（staging durable
        // 保留），让 BEGIN 走新会话分支重置 expected_seq = BEGIN.seq+1。
        final beginAck = await _beginRoundTrip(
          totalLen: total,
          packageSha256: packageSha256,
          etuHeader: etuHeader,
          timeout: _capByBudget(ackTimeout),
        );
        final beginTerminal = _abortStatusOf(beginAck.status);
        if (beginTerminal != null) {
          return OtaAckResult.terminal(
              beginTerminal,
              OtaAckResult(
                  status: beginAck.status,
                  durableOff: beginAck.durableOff,
                  blockBitmap: beginAck.blockBitmap));
        }
        if (beginAck.durableOff < lastDurable) {
          // BEGIN ACK 权威值校验（RC3-06）：MCU staging durable 单调，
          // 倒退即状态不可信，fail closed。
          throw const OtaTransportException(
              'BEGIN ACK durable_off 倒退（MCU 状态不可信）',
              code: 'ACK_MALFORMED');
        }
        _session = beginAck.session;
        view.reset(beginAck.durableOff, beginAck.blockBitmap, total);
        var durableOff = beginAck.durableOff;
        if (beginAck.durableOff > lastDurable) {
          // resume 后 BEGIN 带回更大 durable（丢 ACK 期间 MCU 已提交）：
          // 真实 staging 进展同样重置无进展预算窗口，否则刚获得恢复进展
          // 的传输仍按旧截止时间被判超时（RC3-07）。
          _noProgressClock?.reset();
        }
        _notifyDurable(onDurableProgress, durableOff, total);
        needsResume = false;
        // ---- 块循环：块起点按字节换算（durableOff ~/ blockSize）----
        while (durableOff < total && !needsResume) {
          _checkUsable();
          final blockStart = (view.durableOff ~/ view.blockSize) * view.blockSize;
          if (blockStart >= total) break;
          final blockEnd = (blockStart + view.blockSize).clamp(0, total);
          // 尾块段数向上取整（4096+129B → 33 段，最后一段 1B）。
          final segsInBlock =
              ((blockEnd - blockStart) + OtaBleCodec.dataSegmentSize - 1) ~/
                  OtaBleCodec.dataSegmentSize;
          while (view.durableOff < blockEnd) {
            _checkUsable();
            final midErr = view.takeError();
            if (midErr != null) {
              final decision = _classifyAckError(midErr, resumeLeft);
              if (decision.resume) {
                resumeLeft--;
                needsResume = true;
                break;
              }
              if (decision.terminal != null) {
                return OtaAckResult.terminal(
                    decision.terminal!, view.result());
              }
              throw _ackErrorException(midErr);
            }
            // 发送缺口段：受在途未确认段数（窗口）约束；窗口按 ACK/位图
            // 回收（RC2-05：丢 ACK 后位图确认仍能释放窗口）。
            // 发窗循环逐段检查预算（RC3-07）：MTU=23 时 32 段发窗本身
            // 可耗尽剩余预算，不得无截止连发。
            for (var seg = 0; seg < segsInBlock; seg++) {
              _checkNoProgress();
              await _waitIfPaused(); // 后台暂停挂起（RC3-08）
              // 块完成即停（RC3-02⑥）：段间 await 让出期间，块提交 ACK
              // （advanced）可把 durable 推到块尾并清空 inFlight、bitmap
              // 被 MCU 提交后的 0 覆盖——循环恢复后若不检查会按
              // 「无置位/无在途」对已完成块从头重发（新 seq），重发段的
              // 幂等 ACK（bitmap 不含段）再触发写入确认判定 ERR_STATE，
              // 引发无谓的 ABORT+BEGIN resume。
              if (view.durableOff >= blockEnd) break;
              if (view.inFlightCount >= effectiveWindow) break;
              if ((view.blockBitmap >> seg) & 1 == 1) continue; // 已收段幂等跳过
              if (view.isSegmentInFlight(seg)) continue; // 在途未确认
              final seq = _nextSeq();
              view.trackSend(seq, seg);
              await _sendSegment(package, blockStart, seg, seq);
              sentBytes += _segmentLength(package, blockStart, seg);
              onSent?.call(sentBytes, total);
            }
            if (view.durableOff >= blockEnd) break;
            _checkNoProgress();
            final changed =
                await view.waitForChange(_capByBudget(ackTimeout));
            if (changed) continue; // 有 ACK/错误到达，回到循环头重估
            // 无任何 ACK：重发在途且未被位图确认的段（复用原 seq——MCU
            // 对落后 seq 幂等 ACK，对超前 seq 报 ERR_SEQ，§5.1）。
            var overLimit = false;
            final pending =
                Map<int, int>.of(view.inFlight); // seq → seg 快照
            for (final entry in pending.entries) {
              _checkNoProgress();
              await _waitIfPaused(); // 后台暂停挂起（RC3-08）
              // 块完成即停（RC3-02⑥）：重发段间让出期间块提交 ACK 可能
              // 已把 durable 推到块尾——此时重发只会得到幂等 ACK 并触发
              // 写入确认判定 ERR_STATE（RC3-08 判定对「未写 staging 的
              // 幂等 ACK」fail closed 是对的，但本场景的重发本身不该发生）。
              if (view.durableOff >= blockEnd) break;
              final seg = entry.value;
              if ((view.blockBitmap >> seg) & 1 == 1) continue;
              view.trackSend(entry.key, seg); // 累计发送计数 +1
              if (view.sendCountOf(seg) > retries) overLimit = true;
              await _sendSegment(package, blockStart, seg, entry.key);
              sentBytes += _segmentLength(package, blockStart, seg);
              onSent?.call(sentBytes, total);
            }
            if (overLimit) {
              if (resumeLeft > 0) {
                // ACK 持续丢失（RC3-08③）：MCU 可能仍 ACTIVE 卡在旧
                // expected_seq（快速掉线重连场景，DATA 幂等 ACK 不写
                // staging）。ABORT teardown 后 BEGIN 重置 expected_seq
                // 续传，而非直接放弃。
                resumeLeft--;
                needsResume = true;
                break;
              }
              throw const OtaTransportException(
                  'ACK 重发次数超限，中止传输', code: 'TIMEOUT');
            }
          }
          // 块结束：同步权威 durable（最后一段的 ACK 可能刚到）。
          if (view.durableOff > durableOff) {
            durableOff = view.durableOff;
            _notifyDurable(onDurableProgress, durableOff, total);
            _noProgressClock?.reset(); // durable 前进即重置预算窗口
          }
          if (durableOff > lastDurable) {
            lastDurable = durableOff;
          }
          // 块结束锁存错误消费（RC3-06⑤）：发窗内 ACK 置 malformed/error
          // 后，后续合法提交 ACK 可把 durable 推到块尾，段循环经
          // 「durableOff >= blockEnd」break 直接退出、锁存错误未被消费
          // 即进入 END——MCU 已报错却被当成功收尾。块结束同步后再消费
          // 一次，处置链与段循环头一致（resume / terminal / 抛出）。
          final blockEndErr = view.takeError();
          if (blockEndErr != null) {
            final decision = _classifyAckError(blockEndErr, resumeLeft);
            if (decision.resume) {
              resumeLeft--;
              needsResume = true;
            } else if (decision.terminal != null) {
              return OtaAckResult.terminal(
                  decision.terminal!, view.result());
            } else {
              throw _ackErrorException(blockEndErr);
            }
          }
        }
        if (needsResume) {
          // MCU 仍 ACTIVE 时同包 BEGIN 不重置 expected_seq：先 ABORT
          // teardown（durable 保留），再由循环头 BEGIN 续传（RC2-05）。
          await _abortRoundTrip();
          _session = 0;
          continue;
        }
        // ---- END：复述 package_sha256（seq 复用重试，先注册等待者再发送）----
        final endSeq = _nextSeq(); // 循环外分配一次：重试复用（MCU 对
        // 落后 seq 幂等 ACK，新 seq 会因超前被 ERR_SEQ 拒绝，§5.1）。
        var endAttempts = 0;
        needsResume = false;
        while (true) {
          _checkUsable();
          await _waitIfPaused(); // 后台暂停挂起（RC3-08）
          // MCU teardown 后的 NAK 以 session=0 回显 seq：等待者按 cmd+seq
          // 关联，session 仅在错误态放宽（见 _ResponseWaiter.matches）。
          final waiter = _ResponseWaiter(OtaBleCodec.rspAckEnd, _session, endSeq);
          _waiters.add(waiter);
          try {
            final frame = OtaBleCodec.encodeCommand(
              cmd: OtaBleCodec.cmdEnd,
              session: _session,
              seq: endSeq,
              payload: OtaBleCodec.encodeEndPayload(packageSha256),
            );
            await _writeFrame(frame);
            final endFrame = await waiter.future
                .timeout(_capByBudget(ackTimeout),
                    onTimeout: () => throw TimeoutException('END ACK 超时'));
            final endAck = _parseAck(endFrame);
            final endTerminal = _abortStatusOf(endAck.status);
            if (endTerminal != null) {
              return OtaAckResult.terminal(
                  endTerminal, OtaAckResult.fromAck(endAck));
            }
            if (endAck.status == OtaBleCodec.statusErrState &&
                resumeLeft > 0) {
              resumeLeft--; // MCU 缺段 teardown → 重新 BEGIN resume 补齐
              needsResume = true;
              break;
            }
            if (endAck.status == OtaBleCodec.statusOk &&
                endAck.durableOff != total) {
              // END OK 核对（RC3-06）：MCU finalize 成功语义是
              // durable==total 且 ETRJ 匹配；OK 但 durable 不符即
              // 状态不可信，fail closed，不得当成功上报。
              throw const OtaTransportException(
                  'END ACK OK 但 durable_off != total（MCU 状态不可信）',
                  code: 'ACK_MALFORMED');
            }
            if (endAck.status == OtaBleCodec.statusOk &&
                endAck.durableOff == total &&
                !view.endBitmapValid(endAck.blockBitmap, total)) {
              // END ACK 权威位图校验（RC3-06）：MCU 真值 END OK ACK 发送
              // 时 teardown 尚未执行（ota_ble_session.c:686-689），bitmap
              // 是活跃块位图残留（可能非 0），故不校验 ==0；但置位段仍
              // 不得越出尾块有效位——越界即状态不可信，fail closed。
              throw const OtaTransportException(
                  'END ACK OK 但 block_bitmap 越出尾块有效位（MCU 状态不可信）',
                  code: 'ACK_MALFORMED');
            }
            return OtaAckResult.fromAck(endAck);
          } on TimeoutException {
            _checkNoProgress(); // 预算耗尽优先终止，不再空转重试（RC3-07）
            if (++endAttempts > retries) {
              throw const OtaTransportException(
                  'END 无应答重试超限', code: 'TIMEOUT');
            }
          } finally {
            _waiters.remove(waiter);
          }
        }
        if (needsResume) {
          await _abortRoundTrip();
          _session = 0;
          continue;
        }
      }
    } finally {
      _ackView = null;
      _noProgressClock = null; // 解除预算对 transfer 后命令（ABORT 等）约束
      _busy = false;
    }
  }

  int _segmentLength(Uint8List package, int blockStart, int seg) {
    final segOffset = blockStart + seg * OtaBleCodec.dataSegmentSize;
    final segEnd =
        (segOffset + OtaBleCodec.dataSegmentSize).clamp(0, package.length);
    return segEnd - segOffset;
  }

  /// 发送一个 DATA 段（首发与重发共用；重发复用原 seq）。
  Future<void> _sendSegment(
      Uint8List package, int blockStart, int seg, int seq) async {
    final segOffset = blockStart + seg * OtaBleCodec.dataSegmentSize;
    final segEnd =
        (segOffset + OtaBleCodec.dataSegmentSize).clamp(0, package.length);
    final frame = OtaBleCodec.encodeCommand(
      cmd: OtaBleCodec.cmdData,
      session: _session,
      seq: seq,
      payload: OtaBleCodec.encodeDataPayload(
          segOffset, package.sublist(segOffset, segEnd)),
    );
    await _writeFrame(frame);
  }

  /// 请求取消：停止发送循环、完成所有在途等待者（CANCELLED）。
  /// 取消后的实例永久失效（防竞态复用），由上层重建 transport。
  void cancel() {
    _cancelled = true;
    // 取消必须解除暂停等待（RC3-08）：挂起在 _waitIfPaused 的传输循环
    // 否则永远无法到达 _checkUsable 抛出取消，owner await 死锁。
    _releasePauseGate();
    // 本实例退出后其探针登记一并作废（RC3-05⑤）：写入者已不再持有这条
    // 恢复事务，迟到的应答不得经死人登记解除设备上的废弃标记。
    _resyncProbeSeq = null;
    _resyncProbeAuthoritative = false;
    const err = OtaTransportException('OTA 传输已取消', code: 'CANCELLED');
    _ackView?.fail(err);
    for (final w in List<_FrameWaiterBase>.of(_waiters)) {
      w.fail(err);
    }
    _waiters.clear();
  }

  /// 尽力 ABORT（取消/失败路径）：先置取消标志停止本端 DATA/END 发送，
  /// 再向 MCU 请求 teardown；连接断开时静默失败不抛。
  ///
  /// ABORT 帧走取消旁路写通路（RC2-03）：常规 [_writeFrame] 的可用性
  /// 检查会因 `_cancelled` 拒绝发送，导致 ABORT 被自身拦截。
  Future<void> abortBestEffort() async {
    cancel();
    if (_disposed) return;
    try {
      final frame = OtaBleCodec.encodeCommand(
        cmd: OtaBleCodec.cmdAbort,
        session: _session,
        seq: _nextSeq(),
      );
      await _writeFrameAfterCancel(frame);
    } catch (_) {
      // 尽力而为：断连等场景不阻断取消流程。
    }
  }

  /// 释放上游订阅并完成待处理等待者（页面退出/重绑时调用）。
  Future<void> dispose() async {
    _disposed = true;
    _releasePauseGate();
    // 与 [cancel] 同理（RC3-05⑤）：释放后本实例不再持有重新同步事务。
    _resyncProbeSeq = null;
    _resyncProbeAuthoritative = false;
    const err = OtaTransportException('transport 已释放', code: 'DISPOSED');
    _ackView?.fail(err);
    for (final w in List<_FrameWaiterBase>.of(_waiters)) {
      w.fail(err);
    }
    _waiters.clear();
    await _frameSub.cancel();
  }

  // ---- 后台暂停（RC3-08）----

  /// 暂停等待闸门：非 null 且未完成时，传输循环在帧边界挂起。
  Completer<void>? _resumeGate;
  bool _paused = false;

  /// 后台暂停（RC3-08）：页面进入后台时挂起在途 DATA/END 发送（发窗、
  /// 重发、END 循环在下一帧边界等待），预算时钟同步停走——后台挂起
  /// 不应烧掉无进展预算。幂等；取消/释放会解除等待（不必先恢复）。
  void pauseForBackground() {
    if (_disposed || _cancelled) return;
    _paused = true;
    _noProgressClock?.stop();
    _resumeGate ??= Completer<void>();
  }

  /// 从后台恢复（RC3-08）：解除暂停等待并恢复预算时钟。幂等。
  void resumeFromBackground() {
    if (!_paused) return;
    _paused = false;
    _noProgressClock?.start();
    _releasePauseGate();
  }

  /// 传输循环帧边界挂起点：未暂停时立即返回。
  Future<void> _waitIfPaused() async {
    final gate = _resumeGate;
    if (gate != null) {
      await gate.future;
    }
  }

  /// 解除暂停闸门并完成等待者（取消/释放/恢复共用）。
  void _releasePauseGate() {
    final gate = _resumeGate;
    _resumeGate = null;
    _paused = false;
    if (gate != null && !gate.isCompleted) {
      gate.complete();
    }
  }

  // ---- 内部：帧分发 ----

  void _dispatchFrame(OtaBleFrame f) {
    // 重新同步证据（RC3-05⑤）：INFO 只可能由「被 MCU 完整解析的 GET_INFO」
    // 触发，因此收到本实例在废弃状态下发出的那个 seq 的 INFO，就证明 MCU
    // 帧解析器已脱离悬空态。必须 seq 匹配——废弃前发出的 GET_INFO 其迟到
    // 应答同样以 session=0/rspInfo 到达，不能用它充当恢复证据。
    // 三个条件缺一不可（见 [_isResyncEvidence]）：seq 匹配只是其一，
    // 还要求应答属于本世代废弃、且该探针发出时设备上没有在途旧物理写。
    if (_isResyncEvidence(f)) {
      _clearWriteChannelPoison();
    }
    // 传输期 ACK 视图只消费 DATA ACK（每段独立应答，一问一答等待者
    // 无法覆盖）；BEGIN/END/ABORT ACK 由等待者按 cmd+session+seq 精确
    // 关联，视图不重复消费（RC2-06）。
    final view = _ackView;
    if (view != null && _viewAccepts(f)) {
      view.onAck(f);
    }
    for (final w in List<_FrameWaiterBase>.of(_waiters)) {
      w.offer(f);
    }
  }

  /// 传输期视图过滤：ACK_DATA 按 session 匹配（MCU teardown 后的错误
  /// NAK 以 session=0 回显，仅错误态放宽接受）；ACK_ABORT 是 MCU 会话
  /// 超时主动 teardown 的异步通知（§5.7，无请求关联、可能无等待者），
  /// 传输期到达必须消费终止会话，不得丢弃等超时（RC3-06）。
  /// seq 与在途段的关联由视图内部校验（未知/迟到 ACK 忽略，RC2-06）。
  bool _viewAccepts(OtaBleFrame f) {
    if (f.cmd == OtaBleCodec.rspAckData) {
      if (f.session == _session) return true;
      return f.session == 0 &&
          f.payload.isNotEmpty &&
          f.payload[0] != OtaBleCodec.statusOk;
    }
    if (f.cmd == OtaBleCodec.rspAckAbort) {
      return f.session == _session || f.session == 0;
    }
    return false;
  }

  void _dispatchError(Object e) {
    _ackView?.fail(e);
    for (final w in List<_FrameWaiterBase>.of(_waiters)) {
      w.fail(e);
    }
    _waiters.clear();
  }

  OtaAckPayload _parseAck(OtaBleFrame frame) {
    try {
      return OtaAckPayload.parse(frame.cmd, frame.payload);
    } on FormatException catch (e) {
      throw OtaTransportException(
          'ACK 解析失败: ${e.message}', code: 'ACK_MALFORMED');
    }
  }

  // ---- 内部：错误分类 ----

  /// 传输期 ACK 错误分类：abortStatuses → 终止返回；
  /// ERR_SEQ/ERR_SESSION/ERR_STATE → 有界重新 BEGIN 续传；其余 → 异常。
  _AckErrorDecision _classifyAckError(_AckError err, int resumeLeft) {
    final terminal = _abortStatusOf(err.status);
    if (terminal != null) {
      return _AckErrorDecision(terminal: terminal);
    }
    if (_resumeStatuses.contains(err.status)) {
      if (resumeLeft <= 0) {
        throw OtaTransportException(
            '可恢复错误重试次数超限: 0x${err.status.toRadixString(16)}',
            code: 'ACK_STATUS',
            status: err.status);
      }
      return const _AckErrorDecision(resume: true);
    }
    return const _AckErrorDecision();
  }

  OtaTransportException _ackErrorException(_AckError err) {
    if (err.status < 0) {
      return const OtaTransportException(
          'ACK 解析失败（未知状态或长度非法）', code: 'ACK_MALFORMED');
    }
    return OtaTransportException(
      'ACK 失败: 0x${err.status.toRadixString(16)} (cmd=0x${err.cmd.toRadixString(16)}, seq=${err.seq})',
      code: 'ACK_STATUS',
      status: err.status,
    );
  }

  /// 可恢复错误 → ABORT teardown + 重新 BEGIN 同 sha 续传：
  /// - ERR_SEQ（seq 断档）/ ERR_SESSION / ERR_STATE（MCU teardown）；
  /// - ERR_CRC / ERR_FRAME（帧级 NAK）：MCU expected_seq 停在坏帧处，
  ///   后续帧将连环 ERR_SEQ，必须 ABORT+BEGIN 重对齐（RC2-05）。
  static const Set<int> _resumeStatuses = {
    OtaBleCodec.statusErrSeq,
    OtaBleCodec.statusErrSession,
    OtaBleCodec.statusErrState,
    OtaBleCodec.statusErrCrc,
    OtaBleCodec.statusErrFrame,
  };

  // ---- 内部：命令 ----

  Future<OtaBeginAck> _beginRoundTrip({
    required int totalLen,
    required List<int> packageSha256,
    required List<int> etuHeader,
    required Duration timeout,
  }) async {
    final payload = OtaBleCodec.encodeBeginPayload(
      totalLen: totalLen,
      packageSha256: packageSha256,
      etuHeader: etuHeader,
    );
    // seq 在循环外分配一次、重试复用（RC2-05）：MCU 对同包重复 BEGIN
    // 幂等回进度但不重置 expected_seq（ota_ble_session.c:377），重试若
    // 消耗新 seq，后续 DATA 将因超前被 ERR_SEQ 拒绝。
    final seq = _nextSeq();
    var attempts = 0;
    while (true) {
      _checkUsable();
      // BEGIN ACK 帧头 session 是新分配的会话，与请求 session 无关：
      // 只按 cmd+seq 关联（session 从 payload 解析）。
      final waiter = _ResponseWaiter(OtaBleCodec.rspAckBegin, -1, seq);
      _waiters.add(waiter);
      try {
        final frame = OtaBleCodec.encodeCommand(
          cmd: OtaBleCodec.cmdBegin,
          session: _session,
          seq: seq,
          payload: payload,
        );
        await _writeFrame(frame);
        // BEGIN ACK 等待以剩余预算封顶（RC3-07）：重试循环每轮复用同一
        // timeout 参数，帧外不封顶会让单轮等待固定 2s，多次重试累计
        // 绕过 30s 总预算。
        final respFrame = await waiter.future
            .timeout(_capByBudget(timeout), onTimeout: () => throw TimeoutException('BEGIN ACK 超时'));
        final ack = _parseAck(respFrame);
        if (ack.status != OtaBleCodec.statusOk) {
          throw OtaTransportException(
            'BEGIN ACK 失败: status=0x${ack.status.toRadixString(16)}',
            code: 'ACK_STATUS',
            status: ack.status,
          );
        }
        // 成功 ACK 的 payload session 必须非零（MCU 错误态才回 session=0；
        // session=0 的成功 ACK 不可信，fail closed，RC2-06）。
        final session = ack.session ?? 0;
        if (session == 0) {
          throw const OtaTransportException(
              'BEGIN ACK 成功但 session 非法（0）', code: 'ACK_MALFORMED');
        }
        if (respFrame.session != session) {
          // BEGIN ACK 帧头/payload session 一致性（RC3-06）：MCU 真值
          // session_send_ack_begin 帧头与 payload 携带同一新会话值；
          // 两者不一致即链路损坏或实现缺陷，fail closed 不采信该 ACK。
          throw const OtaTransportException(
              'BEGIN ACK 帧头 session 与 payload session 不一致',
              code: 'ACK_MALFORMED');
        }
        return OtaBeginAck(
          status: ack.status,
          session: session,
          durableOff: ack.durableOff,
          blockBitmap: ack.blockBitmap,
        );
      } on TimeoutException {
        _checkNoProgress(); // 预算耗尽优先终止，不再空转重试（RC3-07）
        if (++attempts > retries) {
          throw const OtaTransportException('BEGIN 无应答重试超限', code: 'TIMEOUT');
        }
      } finally {
        _waiters.remove(waiter);
      }
    }
  }

  /// 受控 ABORT（resume 前清理 MCU 会话）：MCU 收到 ABORT 即 teardown，
  /// staging durable 保留；随后同 sha BEGIN 走新会话分支重置
  /// expected_seq 并按 bitmap 续传（RC2-05）。
  ///
  /// ACK 未到不阻断 resume（超时继续 BEGIN——ABORT 帧已达即 teardown；
  /// 写失败由调用方按断连语义上抛）。
  Future<void> _abortRoundTrip() async {
    if (_session == 0) return;
    final seq = _nextSeq();
    final waiter = _ResponseWaiter(OtaBleCodec.rspAckAbort, -1, seq);
    _waiters.add(waiter);
    try {
      final frame = OtaBleCodec.encodeCommand(
        cmd: OtaBleCodec.cmdAbort,
        session: _session,
        seq: seq,
      );
      await _writeFrame(frame);
      await waiter.future.timeout(_capByBudget(ackTimeout),
          onTimeout: () => throw TimeoutException('ABORT ACK 超时'));
    } on TimeoutException {
      // 尽力而为：不等待重试，BEGIN 会按新会话语义处理。
    } finally {
      _waiters.remove(waiter);
    }
  }

  /// 单帧写 + 等待响应（先注册等待者再发送；按 cmd+session+seq 关联）。
  /// [resyncProbeSeq] 非 null 时本帧同时充当写通道废弃的重新同步探针
  /// （RC3-05⑤）：废弃期间唯一放行的帧，应答到达即由 [_dispatchFrame]
  /// 解除标记。
  Future<Uint8List> _roundTrip(
    Uint8List frame,
    int expectedRsp, {
    required int session,
    required int seq,
    required Duration timeout,
    int? resyncProbeSeq,
  }) async {
    final waiter = _ResponseWaiter(expectedRsp, session, seq);
    _waiters.add(waiter);
    try {
      await _writeFrame(frame, resyncProbeSeq: resyncProbeSeq);
      final resp = await waiter.future.timeout(
        timeout,
        onTimeout: () => throw OtaTransportException(
            '等待响应超时 (cmd=0x${expectedRsp.toRadixString(16)})',
            code: 'TIMEOUT'),
      );
      return resp.payload;
    } finally {
      _waiters.remove(waiter);
    }
  }

  void _checkUsable() {
    if (_disposed) {
      throw const OtaTransportException('transport 已释放', code: 'DISPOSED');
    }
    if (_cancelled) {
      throw const OtaTransportException('OTA 传输已取消', code: 'CANCELLED');
    }
  }

  /// 无 durable 进展总预算时钟（RC3-07）：仅在 [transfer] 期间非空。
  /// 单调时钟绝对截止，durable 前进时 reset；预算覆盖全部等待点
  /// （分片写、ACK 等待、BEGIN/ABORT/END roundtrip、发窗循环），
  /// 防 MTU=23 时 32 段发窗可等数分钟而无总截止。
  Stopwatch? _noProgressClock;

  /// 剩余预算；null 表示不在传输期（不限）。耗尽返回 Duration.zero。
  Duration? get _noProgressLeft {
    final clock = _noProgressClock;
    if (clock == null) return null;
    final left = noProgressTimeout - clock.elapsed;
    return left.isNegative ? Duration.zero : left;
  }

  /// 预算耗尽即抛 NO_DURABLE_PROGRESS（优先于继续重试/写下一分片）。
  void _checkNoProgress() {
    final left = _noProgressLeft;
    if (left != null && left == Duration.zero) {
      throw const OtaTransportException(
          '无 durable 进展超时，中止传输', code: 'NO_DURABLE_PROGRESS');
    }
  }

  /// 用剩余预算封顶单次等待超时。
  Duration _capByBudget(Duration timeout) {
    final left = _noProgressLeft;
    if (left == null) return timeout;
    return left < timeout ? left : timeout;
  }

  int _nextSeq() {
    final s = _seq;
    _seq = (_seq + 1) & 0xFFFF;
    return s;
  }

  /// 会话外查询帧的 seq 分配（独立空间，见 `_seq`/`_session` 上方字段注释）。
  ///
  /// 号码按**设备**分配而非按实例（RC3-05⑤）：同设备上「换个 transport
  /// 再查」是常规路径（每次 bind 新建包装通道），实例各自从 0 起分配会
  /// 让两个实际不同的探针拿到同一个 seq——A 实例探针的应答（甚至废弃前
  /// 那次 GET_INFO 的迟到应答）会被 B 实例当成自己探针的证据，据此解除
  /// 隔离。设备作用域计数器保证同一设备上在途探针的 seq 互不相同。
  int _nextQuerySeq() => _deviceWriteLedger.nextQuerySeq();

  /// 登记一次「已交付底层、尚未结算」的物理写（RC3-05⑤）。
  ///
  /// `Future.timeout` 不取消底层 writeChunk：帧被判超时后串行队列放行
  /// 下一帧，而这一片仍可能在之后落地。账本记录这种在途写的条数，探针
  /// 只有在「发出时零在途」才算权威证据（[_resyncProbeAuthoritative]），
  /// 调用方也可等待其结算后再取证（[_awaitDeviceWritesIdle]）。
  void _trackOutstandingWrite(Future<void> write) {
    final ledger = _deviceWriteLedger;
    ledger.beginWrite();
    // whenComplete 派生链继承原错误，不消费会在「宽限归零、原 future 不再
    // 被 await」时变成未处理的异步错误。
    write.whenComplete(ledger.endWrite).catchError((_) {});
  }

  /// 等待设备上的在途物理写全部结算；[limit] 内未结算即抛 TIMEOUT。
  /// 拿不到「旧写已结束」的证据时不假装已恢复，废弃标记保持。
  Future<void> _awaitDeviceWritesIdle(Duration limit) async {
    final ledger = _deviceWriteLedger;
    if (ledger.outstanding == 0) return;
    try {
      await ledger.idle.timeout(limit);
    } on TimeoutException {
      throw OtaTransportException(
          '写通道废弃：${limit.inMilliseconds}ms 内旧物理写仍未结算，'
          '无法取得重新同步证据',
          code: 'TIMEOUT');
    }
  }

  /// 常规帧写入（数据/命令路径）：受取消/释放与预算检查约束，
  /// 实际分片与超时语义见 [_writeFrameLocked]。
  /// [resyncProbeSeq] 仅由 [getDeviceInfo] 的探针透传：非 null 表示本帧
  /// 是废弃期间唯一放行的重新同步探针（RC3-05⑤）。
  Future<void> _writeFrame(Uint8List frame, {int? resyncProbeSeq}) async {
    await _writeFrameChecked(frame,
        allowCancelled: false, resyncProbeSeq: resyncProbeSeq);
  }

  /// 取消旁路写通路（RC2-03）：仅用于取消后的尽力 ABORT——
  /// `_cancelled` 状态不再拦截（否则 ABORT 被自身写检查吞掉），
  /// `_disposed` 仍然拒绝（释放后不再占用写通道）。
  Future<void> _writeFrameAfterCancel(Uint8List frame) async {
    if (_disposed) {
      throw const OtaTransportException('transport 已释放', code: 'DISPOSED');
    }
    await _writeFrameChecked(frame, allowCancelled: true);
  }

  /// 写帧串行化队列（RC3-05）：DATA 分片写是多次 writeChunk 的序列，
  /// 而取消路径的 ABORT（abortBestEffort）不等待传输循环退出即发起写。
  /// 无串行 owner 时 ABORT 帧可插入 DATA 帧分片之间，MCU 收到
  /// 半帧 DATA+ABORT 混合流，帧边界被破坏。所有帧写入按先来后到排队，
  /// 一次只有一帧占用通道；链条吞掉前序帧的错误，保证取消帧不被
  /// 前序 DATA 的失败跳过（错误仍由各帧自身的 future 抛给调用方）。
  Future<void> _writeSerial = Future<void>.value();

  /// 写通道废弃标记（RC3-05⑤）：分片写中断意味着部分分片已落地 MCU，
  /// 帧解析器悬空在半帧 payload 中——后续任何帧（含取消路径的 ABORT）
  /// 的同步字都会被吞进悬空帧的 payload/CRC 位置，无法恢复同步。
  /// MCU 真值（ota_ble_frame.c:260-272 PAYLOAD 态按 len 吞全部字节，
  /// 含 A5 5A）。
  ///
  /// 解除条件必须是**接收方支持的、可观测的**重新同步证据，不能是
  /// 「换了连接」这种应用侧事件：解析器状态属于 MCU 而非 BLE 链路，
  /// 连接事件不复位它（见 [OtaBleChannel.deviceScope] 的引证）。可达的
  /// 重新同步只有两条：①（应用可控）继续投递字节，让悬空帧按自身 len
  /// 被吃完、CRC 失败、解析器自复位（ota_ble_frame.c:274-313 失败分支
  /// 同样 reset）——上界为 OTA_BLE_MAX_PAYLOAD(132) + 2 字节；②（应用
  /// 不可控）MCU 断电/复位。因此废弃期间**只放行** [getDeviceInfo] 的
  /// GET_INFO 探针帧（只读、幂等、被吞无副作用），并只在收到与之关联的
  /// INFO 应答时解除——INFO 只可能由「被完整解析的 GET_INFO」触发，是
  /// 接收方已回到同步态的正向证明（见 [_resyncProbeSeq]）。无证据即
  /// 保持 fail-closed，绝不因重连、超时或换 wrapper 假装恢复。
  ///
  /// 作用域是**设备**而非包装对象或 transport 实例：`Future.timeout`
  /// 不取消底层 writeChunk，迟到分片仍会落地；有界 settle 只保证「本帧不与
  /// 自己的迟到分片交错」，不等于物理写已被取消。传输路径上 settle 宽限
  /// 还被剩余 durable 预算封顶（RC3-07），预算耗尽时宽限为 0——此时不再
  /// 为迟到分片保留串行队列，交错风险转由本标记 + 探针重试承担。
  /// 若只标记实例，上层在
  /// 同一设备上重建 transport 即可继续写；若只标记包装对象，每次 bind
  /// 新建 `_ChannelAdapter` 也会让标记失效。两种情况下新帧都与旧连接的
  /// 迟到半帧交错，MCU 同样无法恢复同步。标记落在 [_deviceScope]，同一台
  /// 设备上的所有 wrapper 与重连后的新连接共享。Expando 随身份对象一起
  /// 回收，不产生全局泄漏。
  static final Expando<bool> _poisonedDevices =
      Expando<bool>('otaWriteDevicePoisoned');

  /// 废弃标记的作用域对象（RC3-05⑤）。取通道自报的设备作用域：同一台
  /// 设备上的 wrapper 可能被反复重建（每次 bind 新建 `_ChannelAdapter`）、
  /// 也可能经历真实重连，但 MCU 侧的悬空半帧在设备复位前一直存在。
  /// 通道未提供作用域时退回通道对象自身，保持旧语义不放大。
  Object get _deviceScope => _channel.deviceScope ?? _channel;

  /// 设备作用域的写在途账本与查询序号空间（RC3-05⑤）。
  static final Expando<_DeviceWriteLedger> _deviceLedgers =
      Expando<_DeviceWriteLedger>('otaDeviceWriteLedger');

  _DeviceWriteLedger get _deviceWriteLedger =>
      _deviceLedgers[_deviceScope] ??= _DeviceWriteLedger();

  bool get _writeChannelPoisoned => _poisonedDevices[_deviceScope] ?? false;

  void _poisonWriteChannel() {
    final ledger = _deviceWriteLedger;
    // 世代前进（RC3-05⑤）：新一段废弃使此前登记过的全部探针证据失效，
    // 包括同设备上其它实例登记的探针——它们是在解析器状态还不同的
    // 时刻发出的，其应答不能再为当前这段废弃作证。
    ledger.epoch++;
    _poisonedDevices[_deviceScope] = true;
    _resyncProbeSeq = null;
    _resyncProbeAuthoritative = false;
  }

  /// 同步探针的 seq（RC3-05⑤）：仅当本实例在**废弃状态下**发出了
  /// GET_INFO 探针时登记，收到同一 seq 的 INFO 应答才解除标记。避免用
  /// 陈旧 INFO（废弃前那次 GET_INFO 的迟到应答）误判为已重新同步。
  int? _resyncProbeSeq;

  /// 登记探针所属的废弃世代，核对时要求与设备账本的当前世代一致。
  int _resyncProbeEpoch = 0;

  /// 本探针在写出第一个分片时，设备上是否**没有**在途的旧物理写。
  ///
  /// 这是「INFO 应答能否作为重新同步证据」的第二个必要条件（RC3-05⑤）：
  /// `Future.timeout` 不取消底层 writeChunk，被判定超时的旧帧其分片仍可能
  /// 在探针之后才落地。若探针发出时仍有这种写在途，即使探针被 MCU 完整
  /// 解析并回了 INFO，解析器也只是「此刻」同步——迟到的旧分片随后照样在
  /// 它上面制造新的悬空半帧，用它解除隔离等于把未结算的旧写放进了新会话。
  /// 因此这种探针只用于「投递字节逼解析器复位」，不作解除证据。
  bool _resyncProbeAuthoritative = false;

  /// 废弃期间单次探针等待上限：比常规 ACK 超时略宽（悬空帧可能还要
  /// 先吃满若干字节才轮到探针被解析），但仍远小于用户可见的超时。
  static const Duration resyncProbeTimeout = Duration(milliseconds: 800);

  /// 废弃期间探针重试上限。上界依据：悬空帧最多还需
  /// OTA_BLE_MAX_PAYLOAD(132) + 2 = 134 字节才结束，一个 GET_INFO 帧
  /// 为 8 + 0 + 2 = 10 字节，最坏 14 次即可把探针送进已被解析的位置；
  /// 取 20 留余量（含首帧被整帧吞掉的情况）。超过即保持废弃并抛错。
  static const int maxResyncProbes = 20;

  /// 收到探针应答后的解除（RC3-05⑤）。只在本地确有在途探针时生效。
  void _clearWriteChannelPoison() {
    _poisonedDevices[_deviceScope] = false;
    _resyncProbeSeq = null;
    _resyncProbeAuthoritative = false;
  }

  /// 该 INFO 是否构成「MCU 解析器已回到同步态」的当前世代证据。
  bool _isResyncEvidence(OtaBleFrame f) {
    if (f.cmd != OtaBleCodec.rspInfo || f.session != 0) return false;
    if (!_writeChannelPoisoned) return false;
    if (_resyncProbeSeq == null || f.seq != _resyncProbeSeq) return false;
    if (!_resyncProbeAuthoritative) return false;
    return _resyncProbeEpoch == _deviceWriteLedger.epoch;
  }

  Future<void> _writeFrameChecked(
    Uint8List frame, {
    required bool allowCancelled,
    int? resyncProbeSeq,
  }) {
    if (_writeChannelPoisoned && resyncProbeSeq == null) {
      throw const OtaTransportException(
          '写通道已废弃：分片写中断后帧边界不可信，'
          '须由 GET_INFO 探针证明 MCU 已重新同步',
          code: 'WRITE_TIMEOUT');
    }
    final task = _writeSerial.then((_) => _writeFrameLocked(
          frame,
          allowCancelled: allowCancelled,
          resyncProbeSeq: resyncProbeSeq,
        ));
    _writeSerial = task.catchError((_) {});
    return task;
  }

  /// 帧分片写入：按当前可用写净荷上限切片。
  /// - 帧开始前检查取消/释放（RC3-05②）：一旦开始写就写完整帧，循环内
  ///   不再检查取消——MCU 永远收到完整帧，取消后的 ABORT 不会被吞成
  ///   半帧 payload；取消最多延迟一帧，帧完成后立即向调用方抛出。
  /// - 每个分片写入受 [writeTimeout] 限制，并受无 durable 进展总预算
  ///   约束（RC3-07：写通道卡死不得无限阻塞传输循环）；超时后的 settle
  ///   宽限同样由剩余预算封顶，故传输路径上「本帧抛出 WRITE_TIMEOUT」的
  ///   时刻不晚于预算截止（默认 30s），不会出现预算 + 20s 的第三段等待。
  /// - 取消旁路（RC3-05②）：预算检查/封顶只约束正常传输路径——预算
  ///   耗尽的职责是终止卡死的传输，而取消路径的 ABORT 是收拾残局的
  ///   尽力帧，若被预算拦截（checkNoProgress 抛出 / 剩余归零封顶成
  ///   立即超时）将永远发不出，MCU 会话残留 ACTIVE。取消路径仅保留
  ///   [writeTimeout] 单分片上限防连接卡死。
  Future<void> _writeFrameLocked(
    Uint8List frame, {
    required bool allowCancelled,
    int? resyncProbeSeq,
  }) async {
    // 排队期间通道可能已被前序帧废弃（RC3-05⑤）：[_writeFrameChecked] 只在
    // 入队时刻检查，而取消路径的 ABORT 常常在前序 DATA 写超时**之前**就已
    // 排队（abortBestEffort 不等待传输循环退出）。轮到它启动时若不复核，
    // ABORT 的同步字正好写进悬空半帧的 payload 位置，MCU 既收不到 ABORT
    // 也无法恢复同步。
    if (_writeChannelPoisoned) {
      if (resyncProbeSeq == null) {
        throw const OtaTransportException(
            '写通道已废弃：分片写中断后帧边界不可信，'
            '须由 GET_INFO 探针证明 MCU 已重新同步',
            code: 'WRITE_TIMEOUT');
      }
      // 探针是本帧唯一放行的通道占用者：登记 seq、世代与「发出时无在途旧
      // 写」，供 INFO 应答核对后解除标记（RC3-05⑤）。入队时才登记（此刻
      // 确实处于废弃态），排队期间被别的帧解除/重新废弃都不会把陈旧登记
      // 留在原地——重新废弃会前进世代并使本登记在核对时被拒。
      _resyncProbeSeq = resyncProbeSeq;
      _resyncProbeEpoch = _deviceWriteLedger.epoch;
      _resyncProbeAuthoritative = _deviceWriteLedger.outstanding == 0;
    }
    if (!allowCancelled) {
      _checkUsable();
      _checkNoProgress();
    } else if (_disposed) {
      throw const OtaTransportException('transport 已释放', code: 'DISPOSED');
    }
    if (!_channel.isConnected) {
      throw const OtaTransportException('BLE 连接不可用', code: 'DISCONNECTED');
    }
    final chunkSize = await _channel.maxWriteChunkSize();
    if (chunkSize <= 0) {
      throw const OtaTransportException(
          'MTU 未协商或过小，无法分片写入', code: 'MTU_UNAVAILABLE');
    }
    var dispatchedAny = false;
    var frameComplete = false;
    try {
      for (var offset = 0; offset < frame.length; offset += chunkSize) {
        // 逐片重算预算（RC3-07）：帧外一次计算会让 142B DATA 帧在
        // MTU=23 下的 8 个分片各按 10s 上限（均未单片超时）累计 72s，
        // 绕过 30s 总预算。每个分片以当次剩余预算封顶，片间预算耗尽
        // 即终止（单片写卡死仍受 writeTimeout 上限保护）。
        if (!allowCancelled) {
          _checkNoProgress();
        }
        final perChunkTimeout =
            allowCancelled ? writeTimeout : _capByBudget(writeTimeout);
        final end = (offset + chunkSize).clamp(0, frame.length);
        // 迟到物理写隔离（RC3-05⑤）：Future.timeout 不取消底层 writeChunk——
        // 直接上抛会让串行队列（_writeSerial）立即放行下一帧（含取消路径的
        // ABORT），迟到分片在 ABORT 之后落地，MCU 收到交错的半帧流。超时后
        // 先等待底层写 settle（宽限 2×writeTimeout），吞掉迟到错误再抛本帧
        // WRITE_TIMEOUT。
        // 该宽限**不是第三段预算**，仍由无 durable 进展的剩余预算封顶
        // （RC3-07）：不封顶时终止发布时刻可达「预算 + 20s」（默认 30s +
        // 20s = 50s），超出 30s 合同窗口；封顶后传输路径的终止发布上界
        // 恒为 noProgressTimeout。
        // 预算已耗尽时宽限为 0、立即上抛：此刻继续占住串行队列只会把终止
        // 推迟到合同窗口之外。安全性由废弃标记 + 在途写账本共同承担——
        // 废弃标记已拒绝全部业务帧与 ABORT（见 [_writeFrameChecked]），
        // 因此**不会有新的应用帧**与这一片交错；但这一片本身仍是在途的
        // 物理写，它若在某个探针应答之后落地，照样能在已同步的解析器上
        // 制造新的悬空半帧。故本片一并记入设备账本：在它结算之前，任何
        // 探针应答都不被当作重新同步证据（[_resyncProbeAuthoritative]）。
        // 取消路径在 transfer 退出后预算已解除（[_noProgressClock] 置空），
        // 宽限仍取 2×writeTimeout——该路径的终止上界是
        // writeTimeout + 2×writeTimeout，以单次写超时为唯一依据。
        final pendingWrite = _channel.writeChunk(frame.sublist(offset, end));
        _trackOutstandingWrite(pendingWrite);
        dispatchedAny = true;
        try {
          await pendingWrite.timeout(perChunkTimeout);
        } on TimeoutException {
          final settleGrace = _capByBudget(writeTimeout * 2);
          if (settleGrace > Duration.zero) {
            try {
              await pendingWrite.timeout(settleGrace);
            } catch (_) {} // 迟到错误不覆盖本帧超时语义
          }
          throw OtaTransportException(
              'BLE 单次写入超时（${writeTimeout.inSeconds}s）',
              code: 'WRITE_TIMEOUT');
        }
      }
      frameComplete = true;
    } catch (_) {
      // 半帧即废弃写通道（RC3-05⑤）：只要有分片已交付底层而整帧未写完，
      // MCU 帧解析器就悬空在 payload 态。写超时不是唯一入口——片间预算
      // 耗尽（_checkNoProgress 抛 NO_DURABLE_PROGRESS）与底层写错误同样
      // 留下半帧，三者处置必须一致，否则后续尽力 ABORT 会被悬空帧吞掉。
      // 一片未发（连接不可用、MTU 非法、首片前预算耗尽）不污染通道。
      if (dispatchedAny && !frameComplete) {
        _poisonWriteChannel();
      }
      rethrow;
    }
    // 帧完整落地后才暴露取消（RC3-05②）：保证字节流帧边界完整。
    if (!allowCancelled) {
      _checkUsable();
    }
  }

  /// 通知分片处理：跨 chunk 帧重组（一次通知可能带多帧或半帧），
  /// 完整帧同步分发。替代原 async* 生成器——订阅在构造内同步建立
  /// （见构造函数注释），ACK 不因订阅竞态丢失。
  void _onNotifyChunk(List<int> notifyChunk) {
    _frameBuffer.add(notifyChunk);
    final bytes = Uint8List.fromList(_frameBuffer.takeBytes());
    // 通知可能一次带多帧或半帧；循环解析完整帧。
    var offset = 0;
    while (offset + OtaBleCodec.frameHeaderSize + OtaBleCodec.frameCrcSize <=
        bytes.length) {
      if (bytes[offset] != OtaBleCodec.frameSync0 ||
          bytes[offset + 1] != OtaBleCodec.frameSync1) {
        // 丢失同步：丢弃直到下一个同步字（容错，不 crash）。
        offset += 1;
        continue;
      }
      final len = bytes[offset + 6] | (bytes[offset + 7] << 8);
      final frameEnd = offset +
          OtaBleCodec.frameHeaderSize +
          len +
          OtaBleCodec.frameCrcSize;
      if (frameEnd > bytes.length) break; // 半帧，继续收
      try {
        _dispatchFrame(OtaBleCodec.decodeFrame(bytes.sublist(offset, frameEnd)));
      } on FormatException {
        // 坏帧：跳过（不终止整个流；上层按超时/重试处理）。
      }
      offset = frameEnd;
    }
    // 半帧必须无条件回存（PR03）：offset < bytes.length 即有未消费尾部。
    if (offset < bytes.length) {
      _frameBuffer.add(bytes.sublist(offset));
    }
  }

  void _notifyDurable(
    void Function(int, int)? cb,
    int durableOff,
    int total,
  ) {
    cb?.call(durableOff, total);
  }

  int? _abortStatusOf(int status) {
    if (OtaBleCodec.abortStatuses.contains(status)) return status;
    return null;
  }
}

/// 传输期 ACK 视图：持续消费 DATA ACK 并维护按段在途窗口。
///
/// MCU 对每个 DATA 段独立应答（seq 回显），一问一答等待者无法覆盖。
/// 窗口按"未确认段"计数（RC2-05）：ACK 按 seq 回收段，MCU 权威位图
/// 置位的段同样回收（丢 ACK 后位图仍能释放窗口）；重发复用原 seq。
///
/// ACK 校验链（RC2-06，任一步失败不得覆盖权威进度）：
/// 1. payload 可解析（畸形记为错误，由传输循环终止）；
/// 2. ACK 的 seq 必须关联一个在途段——未知/迟到/重复 ACK 整帧忽略；
/// 3. status OK 时 durable_off 校验范围（0..total、块对齐或 ==total）
///    与单调不倒退，block_bitmap 不得越出所属块的有效位。
class _TransferAckView {
  _TransferAckView({required this.blockSize, required this.segmentSize});

  final int blockSize;
  final int segmentSize;

  int durableOff = 0;
  int blockBitmap = 0;
  int totalLen = 0;
  /// 在途段：请求 seq → 段号（ACK/位图置位即回收；窗口按此计数）。
  final Map<int, int> inFlight = {};
  /// 每段累计发送次数（首发+重发；超限由传输循环终止）。
  final Map<int, int> segSendCounts = {};
  _AckError? _error;
  bool _malformed = false;
  Completer<void>? _change;

  int get inFlightCount => inFlight.length;

  /// 段是否在途未确认（未收到 ACK 且未被位图确认）。
  bool isSegmentInFlight(int seg) => inFlight.containsValue(seg);

  /// 登记一次段发送（首发与重发共用；重发复用原 seq）。
  void trackSend(int seq, int seg) {
    inFlight[seq] = seg;
    segSendCounts[seg] = (segSendCounts[seg] ?? 0) + 1;
  }

  int sendCountOf(int seg) => segSendCounts[seg] ?? 0;

  /// BEGIN ACK 权威值校验（RC3-06）：durable/bitmap 必须过与 DATA ACK
  /// 相同的合法性检查，非法即 fail closed，不得盲信写入本地状态。
  void reset(int durable, int bitmap, int total) {
    totalLen = total;
    if (!_durableValid(durable)) {
      throw const OtaTransportException(
          'BEGIN ACK durable_off 非法（越界/未对齐）', code: 'ACK_MALFORMED');
    }
    if (!_bitmapValid(bitmap, durable)) {
      throw const OtaTransportException(
          'BEGIN ACK block_bitmap 越出所属块有效位', code: 'ACK_MALFORMED');
    }
    durableOff = durable;
    blockBitmap = bitmap;
    inFlight.clear();
    segSendCounts.clear();
    _error = null;
    _malformed = false;
  }

  void onAck(OtaBleFrame f) {
    final OtaAckPayload ack;
    try {
      ack = OtaAckPayload.parse(f.cmd, f.payload);
    } on FormatException {
      _malformed = true;
      _signal();
      return;
    }
    if (f.cmd != OtaBleCodec.rspAckData) {
      // 异步 ACK_ABORT（MCU 主动 teardown）：无请求关联，到达即终止。
      // 首错保留（??=）：迟到的 ERR ACK 不得覆盖已锁存的 terminal ABORTED。
      _error ??= _AckError(ack.status, f.cmd, f.seq);
      _signal();
      return;
    }
    // 未知/迟到/重复 ACK（seq 不在途）：忽略整帧，不覆盖权威进度。
    final seg = inFlight.remove(f.seq);
    if (seg == null) {
      _signal();
      return;
    }
    if (ack.status != OtaBleCodec.statusOk) {
      // 首错保留（??=）：不覆盖更早锁存的错误（如异步 ABORTED）。
      _error ??= _AckError(ack.status, f.cmd, f.seq);
      _signal();
      return;
    }
    if (!_durableValid(ack.durableOff) || ack.durableOff < durableOff) {
      // 超范围/未对齐/倒退：不可信 ACK，fail closed 记为畸形。
      _malformed = true;
      _signal();
      return;
    }
    if (ack.durableOff - durableOff > blockSize) {
      // 跨窗伪跳跃（RC3-06）：MCU 逐段处理（一次 ACK 至多 commit 一个
      // 块），且客户端发下一块段的前提是本块段 ACK/位图已回收窗口并
      // 更新过 durable——相邻两次被接受的 ACK 之间 durable 前移至多
      // 一个块。8192B 包首块在途时 ACK 报 durable=8192/bitmap=0 的
      // 伪造跳跃（可清 inFlight 跳过第二块发 END）在此 fail closed。
      _malformed = true;
      _signal();
      return;
    }
    if (!_bitmapValid(ack.blockBitmap, ack.durableOff)) {
      _malformed = true;
      _signal();
      return;
    }
    final advanced = ack.durableOff > durableOff;
    if (!advanced && (ack.blockBitmap >> seg & 1) == 0) {
      // 写入确认判定（RC3-08）：ACK 回收了在途段但既未推进 durable、
      // 权威位图也不含该段——这是 MCU 幂等 OK 冒充写入确认的路径
      // （快速重连 MCU 仍 ACTIVE、低 seq DATA 被幂等 ACK 不写 staging）。
      // 若误当已确认，客户端会跳过该段不补发，最终 END 校验失败。
      // fail closed 记 ERR_STATE，由传输循环 ABORT teardown + BEGIN
      // 重对齐（新会话重置 expected_seq，SHA 从 journal 前缀重建）。
      // 首错保留（??=）：不覆盖更早锁存的错误（如异步 ABORTED）。
      _error ??= _AckError(OtaBleCodec.statusErrState, f.cmd, f.seq);
      _signal();
      return;
    }
    durableOff = ack.durableOff;
    blockBitmap = ack.blockBitmap;
    if (advanced) {
      // durable 跨块前移（MCU 整块 commit 后推进）：旧块所有在途段
      // （含丢 ACK 的）一并回收，防跨块残留耗尽窗口；旧块计数同步清
      // 空（已提交段不再参与重发超限判定）。
      inFlight.clear();
      segSendCounts.clear();
    }
    _harvestBitmap();
    _signal();
  }

  /// durable_off 合法性：0..total，且为块边界（4KB 对齐）或包尾。
  bool _durableValid(int durable) {
    if (durable < 0 || durable > totalLen) return false;
    return durable == totalLen || durable % blockSize == 0;
  }

  /// bitmap 合法性：所属块（durable 所在块起点即 durable 本身）的有效
  /// 段之外的位不得置位。
  bool _bitmapValid(int bitmap, int durable) {
    final blockEnd = (durable + blockSize).clamp(0, totalLen);
    final segsInBlock =
        ((blockEnd - durable) + segmentSize - 1) ~/ segmentSize;
    final validMask = segsInBlock >= 32 ? -1 : (1 << segsInBlock) - 1;
    return bitmap & ~validMask == 0;
  }

  /// END ACK 权威位图校验入口（RC3-06）：END OK（durable==total）时
  /// bitmap 仍不得越出尾块有效位（MCU 真值：END OK ACK 在 teardown 前
  /// 发送，bitmap 是活跃块位图残留，非 0 合法，越界不合法）。
  bool endBitmapValid(int bitmap, int durable) => _bitmapValid(bitmap, durable);

  /// 位图确认的段回收在途记录（窗口释放的另一通路，RC2-05）。
  void _harvestBitmap() {
    if (blockBitmap == 0) return;
    inFlight.removeWhere((_, seg) => (blockBitmap >> seg) & 1 == 1);
    segSendCounts.removeWhere((seg, _) => (blockBitmap >> seg) & 1 == 1);
  }

  /// 首个非 OK ACK（畸形 ACK 以 status<0 表示）。消费语义（RC3-06）：
  /// 读取即清除锁存。段循环头已处置（resume/terminal/抛出）的错误在
  /// 块尾不得再次处置——否则同一错误双扣 resumeLeft，retries=1 时一次
  /// 可恢复错误即被拒，默认 5 次预算也被两次一组消耗而非五次独立恢复。
  _AckError? takeError() {
    if (_malformed) {
      _malformed = false;
      return const _AckError(-1, 0, 0);
    }
    final err = _error;
    _error = null;
    return err;
  }

  OtaAckResult result() => OtaAckResult(
        status: _error?.status ?? OtaBleCodec.statusOk,
        durableOff: durableOff,
        blockBitmap: blockBitmap,
      );

  /// 等待任意状态变化（新 ACK/错误/畸形帧）。超时返回 false。
  Future<bool> waitForChange(Duration timeout) {
    final c = Completer<void>();
    _change = c;
    return c.future.then((_) => true).timeout(timeout, onTimeout: () {
      // 超时必须注销并收尾孤儿 completer：then 链已被 timeout 绕过，
      // 留守的 c 会吃掉后续 [_signal]（transport 注册新等待者后等不到
      // 已发生的 ACK，假性二次超时重发）；更严重的是 cancel/fail 对
      // 孤儿 completeError 时错误无人消费，以 uncaught async error 从
      // 无关的 await 点冒出（MTU=23 取消用例：abortBestEffort 的写
      // await 点收走 CANCELLED，压垮测试的错误处理边界）。
      if (_change == c) _change = null;
      if (!c.isCompleted) c.complete();
      return false;
    });
  }

  void fail(Object e) {
    final c = _change;
    _change = null;
    if (c != null && !c.isCompleted) {
      c.completeError(e);
    }
  }

  void _signal() {
    final c = _change;
    _change = null;
    if (c != null && !c.isCompleted) {
      c.complete();
    }
  }
}

/// 传输期 ACK 错误记录（status/cmd/seq）。
class _AckError {
  const _AckError(this.status, this.cmd, this.seq);

  final int status;
  final int cmd;
  final int seq;
}

/// 块循环对 ACK 错误的处置决定。
class _AckErrorDecision {
  const _AckErrorDecision({this.resume = false, this.terminal});

  final bool resume;
  final int? terminal;
}

/// 帧等待者基类：匹配的帧到达即完成 future。
abstract class _FrameWaiterBase {
  _FrameWaiterBase() {
    // 命令帧的等待者必须先注册再发送（GET_INFO/BEGIN/END/ABORT 都是
    // 「_waiters.add(waiter) → await _writeFrame(frame) → await waiter.future」）。
    // 物理写本身是 await 点：分片写让出期间发生 cancel()/dispose()/通知流
    // onError 时，[fail] 会对一个**尚无监听者**的 future completeError，Dart
    // 立即把它上报为 uncaught async error，从当时正在执行的无关 await 点
    // （典型是 abortBestEffort 的写等待）冒出，测试直接判失败、生产里则
    // 越过调用方的 try/catch 变成 zone 级错误（RC3-02/04）。
    //
    // 构造即挂一个「只观察不处置」的监听者：错误从此刻起始终被观察，处置
    // 仍由调用方 await 同一个 future 完成——Future 支持多监听者，每个监听者
    // 各自收到同一结果，互不吞掉（与 Stream 的单订阅语义不同）。
    unawaited(_completer.future.then(
      (_) {},
      onError: (Object _, StackTrace __) {},
    ));
  }

  final Completer<OtaBleFrame> _completer = Completer<OtaBleFrame>();

  Future<OtaBleFrame> get future => _completer.future;

  bool matches(OtaBleFrame f);

  void offer(OtaBleFrame f) {
    if (_completer.isCompleted || !matches(f)) return;
    _completer.complete(f);
  }

  void fail(Object e) {
    if (!_completer.isCompleted) {
      _completer.completeError(e);
    }
  }
}

/// 一问一答等待者：按 cmd+session+seq 精确关联。
///
/// [session] 传 -1 表示不校验帧头 session（BEGIN ACK 帧头是 MCU 新分配
/// 的会话，session 只能从 payload 解析）。MCU teardown 后的错误 NAK 以
/// session=0 回显请求 seq：session 不匹配时仅错误态放宽接受。
class _ResponseWaiter extends _FrameWaiterBase {
  _ResponseWaiter(this.expectedCmd, this.session, this.seq);

  final int expectedCmd;
  final int session;
  final int seq;

  @override
  bool matches(OtaBleFrame f) {
    if (f.cmd != expectedCmd || f.seq != seq) return false;
    if (session < 0 || f.session == session) return true;
    return f.session == 0 &&
        f.payload.isNotEmpty &&
        f.payload[0] != OtaBleCodec.statusOk;
  }
}

/// BEGIN ACK 结果。
class OtaBeginAck {
  OtaBeginAck({
    required this.status,
    required this.session,
    required this.durableOff,
    required this.blockBitmap,
  });

  final int status;
  final int session;
  final int durableOff;
  final int blockBitmap;
}

/// ACK 统一结果（BEGIN/DATA/END）。
class OtaAckResult {
  OtaAckResult({
    required this.status,
    required this.durableOff,
    required this.blockBitmap,
    this.terminal = false,
  });

  factory OtaAckResult.fromAck(OtaAckPayload ack) => OtaAckResult(
        status: ack.status,
        durableOff: ack.durableOff,
        blockBitmap: ack.blockBitmap,
      );

  factory OtaAckResult.terminal(int status, OtaAckResult from) =>
      OtaAckResult(
        status: status,
        durableOff: from.durableOff,
        blockBitmap: from.blockBitmap,
        terminal: true,
      );

  final int status;
  final int durableOff;
  final int blockBitmap;
  /// 不可恢复中止（§5.7 abortStatuses）。
  final bool terminal;

  bool get isOk => status == OtaBleCodec.statusOk && !terminal;
}

/// 设备作用域的写在途账本与查询序号空间（RC3-05⑤）。
///
/// 为什么这些状态必须按设备而不是按 transport 实例：
/// - 写通道废弃标记本身落在设备作用域（`_poisonedDevices`），恢复证据
///   必须同域，否则「换个 wrapper 再查」就会把另一个实例的应答当成
///   本实例的证据；
/// - 会话外查询 seq 若按实例分配，各实例都从 0 起，两个实际不同的探针会
///   拿到同一个号码，谁先收到谁的应答无法区分；
/// - `Future.timeout` 不取消底层 `writeChunk`：一帧写超时后它的分片仍可能
///   在未来落地。只要设备上还有这种「已交付、未结算」的写在途，任何探针
///   应答都不构成「解析器已重新同步」的证明——迟到分片会在应答之后落到
///   同一个解析器上，重新制造悬空半帧。
///
/// 账本随设备身份对象一起回收（Expando），不产生全局泄漏。
class _DeviceWriteLedger {
  /// 会话外查询（GET_INFO，session=0）的 seq 空间。合同 §5.1 的 seq 只
  /// 约束会话内帧；GET_INFO 不参与会话状态（§5.2），seq 仅作应答回显关联。
  int _querySeq = 0;

  /// 取下一个会话外查询 seq（0..0xFFFF 回绕）。
  int nextQuerySeq() {
    final s = _querySeq;
    _querySeq = (_querySeq + 1) & 0xFFFF;
    return s;
  }

  /// 废弃世代：每次进入废弃态 +1。旧世代登记的探针应答不得解除新世代的
  /// 废弃（跨实例也成立——世代在设备上共享）。
  int epoch = 0;

  /// 已交付底层、尚未结算（成功/失败/迟到）的物理写条数。
  int outstanding = 0;

  Completer<void> _idle = Completer<void>()..complete();

  /// 设备上已无在途物理写时完成（当前已无在途则立即完成）。
  Future<void> get idle => _idle.future;

  void beginWrite() {
    if (outstanding == 0) {
      _idle = Completer<void>();
    }
    outstanding++;
  }

  void endWrite() {
    outstanding--;
    if (outstanding == 0 && !_idle.isCompleted) {
      _idle.complete();
    }
  }
}

/// 传输层稳定领域异常。
class OtaTransportException implements Exception {
  const OtaTransportException(this.message, {this.code, this.status});

  final String message;
  final String? code;
  /// BLE ACK 状态码（ACK_STATUS 时非空；-1 表示畸形 ACK）。
  final int? status;

  @override
  String toString() => 'OtaTransportException($code): $message';
}
