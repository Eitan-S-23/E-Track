import 'package:flutter/foundation.dart'
    show debugPrint, debugPrintThrottled;
import 'package:flutter_test/flutter_test.dart';

import 'package:ble_monitor/ota/ota_link_stats.dart';

/// OtaLinkStats 纯单元测试（P3-4 链路观测）：
/// - nearest-rank 分位数冻结口径（ceil(q*N)，不插值不删样本）；
/// - ACK 延迟样本规则（首发起点、重发不更新、重复确认不重复采样、
///   共享 ACK 多段各自成样本、无首发段不计分母）；
/// - fail-closed 完整性（complete / partial:missing=N）；
/// - ACK 分类计数、durable 单调去重、绑定阶段幂等、END ACK 覆盖式；
/// - toJson 导出与 emitSummary 幂等。
///
/// transport 层接线（真实 transfer + fake MCU）在
/// `ota_ble_transport_test.dart` 的 `P3-4 链路观测接线` 组覆盖。
void main() {
  test('nearestRank：空样本返回 null', () {
    expect(OtaLinkStats.nearestRank(const <int>[], 0.99), isNull);
  });

  test('nearestRank：N=1 任意分位返回唯一值', () {
    expect(OtaLinkStats.nearestRank(const [42], 0.5), 42);
    expect(OtaLinkStats.nearestRank(const [42], 0.99), 42);
  });

  test('nearestRank：N=100 p99 取第 99 个（ceil 语义，不插值）', () {
    final samples = List<int>.generate(100, (i) => i + 1);
    // ceil(0.99*100)=99 → 升序第 99 个 = 99（不是 99.01 插值）。
    expect(OtaLinkStats.nearestRank(samples, 0.99), 99);
    // ceil(0.50*100)=50 → 第 50 个 = 50（偶数 N 不取平均）。
    expect(OtaLinkStats.nearestRank(samples, 0.50), 50);
  });

  test('nearestRank：N=3 p99 取最大（ceil(2.97)=3）', () {
    expect(OtaLinkStats.nearestRank(const [10, 30, 20], 0.99), 30);
  });

  group('ACK 延迟样本规则', () {
    test('首发+确认恰一样本；重发不更新起点、计入重传帧', () async {
      final stats = OtaLinkStats(label: 'upgrade');
      stats.recordSegmentSendEnd(offsetBytes: 0, lengthBytes: 128);
      await Future<void>.delayed(const Duration(milliseconds: 5));
      // 重发同段：不创建新样本、不更新首发结束时刻。
      stats.recordSegmentSendEnd(offsetBytes: 0, lengthBytes: 128);
      stats.recordAckConfirm(
          blockStart: 0, segs: const [0], segmentSize: 128);
      expect(stats.ackLatencySamplesUs, hasLength(1));
      expect(stats.segmentsUnique, 1);
      expect(stats.segmentSendTotal, 2);
      expect(stats.retransmitFrames, 1);
      // 样本值 ≥ 5ms（首发结束到确认的真实间隔，非零）。
      expect(stats.ackLatencySamplesUs.single,
          greaterThanOrEqualTo(4000)); // Stopwatch 容差
      expect(stats.ackSampleIntegrity, 'complete');
    });

    test('重复确认不重复采样', () {
      final stats = OtaLinkStats(label: 'upgrade');
      stats.recordSegmentSendEnd(offsetBytes: 0, lengthBytes: 128);
      stats.recordAckConfirm(
          blockStart: 0, segs: const [0], segmentSize: 128);
      stats.recordAckConfirm(
          blockStart: 0, segs: const [0], segmentSize: 128);
      expect(stats.ackLatencySamplesUs, hasLength(1));
    });

    test('共享同一 ACK 的多段各自成样本（起点各异）', () async {
      final stats = OtaLinkStats(label: 'upgrade');
      stats.recordSegmentSendEnd(offsetBytes: 0, lengthBytes: 128);
      await Future<void>.delayed(const Duration(milliseconds: 2));
      stats.recordSegmentSendEnd(offsetBytes: 128, lengthBytes: 128);
      await Future<void>.delayed(const Duration(milliseconds: 2));
      stats.recordSegmentSendEnd(offsetBytes: 256, lengthBytes: 128);
      // durable 跨块前移：一个 ACK 同时确认旧块全部在途段。
      stats.recordAckConfirm(
          blockStart: 0, segs: const [0, 1, 2], segmentSize: 128);
      expect(stats.ackLatencySamplesUs, hasLength(3));
      // 起点各异：后发段的样本值更小。
      expect(stats.ackLatencySamplesUs[0],
          greaterThan(stats.ackLatencySamplesUs[1]));
      expect(stats.ackLatencySamplesUs[1],
          greaterThan(stats.ackLatencySamplesUs[2]));
    });

    test('无首发记录的段跳过且不计入完整性分母（resume 前缀/bitmap 跳过段）',
        () {
      final stats = OtaLinkStats(label: 'upgrade');
      // resume 位图跳过段（未发送）被 bitmap 确认：无起点，不产生样本。
      stats.recordAckConfirm(
          blockStart: 4096, segs: const [5], segmentSize: 128);
      expect(stats.ackLatencySamplesUs, isEmpty);
      expect(stats.ackSampleIntegrity, 'complete');
      // 该确认仍被记为该段「已有有效确认」并暂挂：本实例始终没发过它，
      // 因此既不是样本，也不算无效观测（P34-R01：无效观测只针对
      // 「确认早于首发登记」的已发送段）。
      expect(stats.ackEarlyInvalid, 0);
      expect(stats.toJson()['transfer']['ackEarlyUnsent'], 1);
    });

    test('fail-closed：已发送未确认段如实报 partial:missing=N', () {
      final stats = OtaLinkStats(label: 'upgrade');
      stats.recordSegmentSendEnd(offsetBytes: 0, lengthBytes: 128);
      stats.recordSegmentSendEnd(offsetBytes: 128, lengthBytes: 128);
      stats.recordSegmentSendEnd(offsetBytes: 256, lengthBytes: 128);
      stats.recordAckConfirm(
          blockStart: 0, segs: const [0], segmentSize: 128);
      expect(stats.ackSampleIntegrity, 'partial:missing=2');
      // 负例（摘要变异检出）：补确认后完整性恢复 complete——摘要与
      // 采样行双通道交叉可校验的前提是完整性声明如实反映缺口。
      stats.recordAckConfirm(
          blockStart: 0, segs: const [1, 2], segmentSize: 128);
      expect(stats.ackSampleIntegrity, 'complete');
    });

    test('bitmap 确认走同一通路：置位段逐段成样本', () {
      final stats = OtaLinkStats(label: 'upgrade');
      stats.recordSegmentSendEnd(offsetBytes: 0, lengthBytes: 128);
      stats.recordSegmentSendEnd(offsetBytes: 256, lengthBytes: 128);
      // bitmap=0b101 → 段 0 与段 2（off 256）；段 1 未发送不产生样本。
      stats.recordBitmapConfirm(
          durableOff: 0, bitmap: 0x05, segmentSize: 128);
      expect(stats.ackLatencySamplesUs, hasLength(2));
      expect(stats.ackSampleIntegrity, 'complete');
    });

    test('bitmap=0 的 BEGIN 权威确认是 no-op', () {
      final stats = OtaLinkStats(label: 'upgrade');
      stats.recordBitmapConfirm(
          durableOff: 0, bitmap: 0, segmentSize: 128);
      expect(stats.ackLatencySamplesUs, isEmpty);
    });
  });

  group('ACK 分类计数与 durable 推进', () {
    test('六类分类独立累加', () {
      final stats = OtaLinkStats(label: 'upgrade');
      stats.recordAckClass('ok');
      stats.recordAckClass('ok');
      stats.recordAckClass('duplicate');
      stats.recordAckClass('error');
      stats.recordAckClass('malformed');
      stats.recordAckClass('noProgress');
      stats.recordAckClass('abort');
      expect(stats.acksOk, 2);
      expect(stats.acksDuplicate, 1);
      expect(stats.acksError, 1);
      expect(stats.acksMalformed, 1);
      expect(stats.acksNoProgress, 1);
      expect(stats.acksAbort, 1);
    });

    test('durable 单调去重：重复与倒退忽略', () {
      final stats = OtaLinkStats(label: 'upgrade');
      stats.recordDurableAdvance(4096);
      stats.recordDurableAdvance(4096); // 重复
      stats.recordDurableAdvance(0); // 倒退
      stats.recordDurableAdvance(8192);
      expect(stats.durableOffsets, [4096, 8192]);
      expect(stats.durableTimesUs, hasLength(2));
    });
  });

  group('绑定与传输阶段', () {
    test('charsDiscovery/mtu/subscribe 幂等只记首次', () {
      final stats = OtaLinkStats(label: 'upgrade');
      stats.recordCharsDiscovery(durationUs: 100, found: true);
      stats.recordCharsDiscovery(durationUs: 200, found: false);
      stats.recordMtu(requested: 247, chunkBytes: 244, durationUs: 300);
      stats.recordMtu(requested: 512, chunkBytes: 20, durationUs: 400);
      stats.recordSubscribe(durationUs: 500, ok: true);
      stats.recordSubscribe(durationUs: 600, ok: false);
      final json = stats.toJson();
      expect(json['bind']['charsUs'], 100);
      expect(json['bind']['found'], isTrue);
      expect(json['bind']['mtuRequested'], 247);
      expect(json['bind']['mtuChunkBytes'], 244);
      expect(json['bind']['mtuUs'], 300);
      expect(json['bind']['subscribeUs'], 500);
      expect(json['bind']['subscribeOk'], isTrue);
    });

    test('transferStart 幂等、outcome 幂等；endAckArrival 由采信点单次调用'
        '（P34-R03）', () async {
      final stats = OtaLinkStats(label: 'upgrade');
      stats.recordTransferStart();
      final firstStart = stats.toJson()['transfer']['startUs'];
      await Future<void>.delayed(const Duration(milliseconds: 2));
      stats.recordTransferStart(); // 幂等：起点不变
      expect(stats.toJson()['transfer']['startUs'], firstStart);
      stats.recordEndAckArrival();
      final firstEnd = stats.toJson()['transfer']['endAckUs'];
      await Future<void>.delayed(const Duration(milliseconds: 2));
      // 同一传输内 END 重试只有被采信的那一轮调用本方法（transport 侧
      // 唯一调用点在采信点，不再由帧分发层按 cmd 覆盖）——这里直接再调
      // 一次即等价于「同一接收点的最新观测」，语义与 [recordTransferStart]
      // 的幂等不同，故显式断言其为「后到者胜」以固定该差异。
      stats.recordEndAckArrival();
      final secondEnd = stats.toJson()['transfer']['endAckUs'];
      expect(secondEnd, greaterThan(firstEnd!));
      stats.recordTransferOutcome(ok: true);
      stats.recordTransferOutcome(ok: false); // 幂等：终态不被覆盖
      final t = stats.toJson()['transfer'];
      expect(t['outcome'], 'ok');
      expect(t['elapsedUs'], greaterThan(0));
    });

    test('getInfo / gattWrite / discover / platformWrite 累计与错误计数',
        () {
      final stats = OtaLinkStats(label: 'upgrade');
      stats.recordGetInfo(durationUs: 1000);
      stats.recordGetInfo(durationUs: 2000);
      stats.recordGattWrite(durationUs: 500, bytes: 128);
      stats.recordGattWrite(durationUs: 700, bytes: 128, error: true);
      stats.recordDiscover(durationUs: 900);
      stats.recordPlatformWrite(durationUs: 600, bytes: 128);
      final json = stats.toJson();
      expect(json['getInfo']['calls'], 2);
      expect(json['getInfo']['totalUs'], 3000);
      expect(json['gattWrites']['calls'], 2);
      expect(json['gattWrites']['bytes'], 256);
      expect(json['gattWrites']['errors'], 1);
      expect(json['discovers']['calls'], 1);
      expect(json['platformWrites']['calls'], 1);
      expect(json['platformWrites']['bytes'], 128);
    });
  });

  group('toJson / emitSummary', () {
    test('schema 与 transfer 域字段齐全', () {
      final stats = OtaLinkStats(label: 'upgrade', device: 'AA:BB');
      stats.recordTransferStart();
      stats.recordEndAckArrival();
      stats.recordTransferOutcome(ok: true);
      final json = stats.toJson();
      expect(json['schema'], 1);
      expect(json['label'], 'upgrade');
      expect(json['device'], 'AA:BB');
      expect(json['clock'], 'stopwatch-mono-us');
      final transfer = json['transfer'] as Map<String, dynamic>;
      expect(transfer['outcome'], 'ok');
      expect(transfer['ackSamples'], 'complete');
      expect(transfer['ackLatency']['count'], 0);
      expect(transfer['ackLatency']['p99Us'], isNull);
      expect(transfer['durable']['events'], 0);
      expect(transfer['durable']['finalOff'], isNull);
      expect((transfer['acks'] as Map<String, dynamic>)['ok'], 0);
    });

    test('emitSummary 幂等：仅首次输出一行 OTA_LINK_STATS', () {
      final logs = <String>[];
      debugPrint = (String? message, {int? wrapWidth}) {
        if (message != null) logs.add(message);
      };
      try {
        final stats = OtaLinkStats(label: 'upgrade');
        stats.emitSummary();
        stats.emitSummary();
        final summaryLines =
            logs.where((l) => l.startsWith('OTA_LINK_STATS ')).toList();
        expect(summaryLines, hasLength(1));
        expect(summaryLines.single, contains('"label":"upgrade"'));
      } finally {
        // 恢复默认实现，避免污染后续测试的日志捕获。
        debugPrint = debugPrintThrottled;
      }
    });

    test('流式样本行格式：kind/us/off 字段', () {
      final logs = <String>[];
      debugPrint = (String? message, {int? wrapWidth}) {
        if (message != null) logs.add(message);
      };
      try {
        final stats = OtaLinkStats(label: 'probe');
        stats.recordSegmentSendEnd(offsetBytes: 256, lengthBytes: 128);
        stats.recordAckConfirm(
            blockStart: 0, segs: const [2], segmentSize: 128);
        final first = logs.firstWhere(
            (l) => l.startsWith('OTA_LINK_SAMPLE label=probe '));
        expect(first, contains('kind=segment_first_send'));
        expect(first, contains('off=256'));
        expect(first, contains('len=128'));
        final ack = logs.firstWhere(
            (l) => l.contains('kind=ack_latency'));
        expect(ack, contains('off=256'));
        expect(ack, isNot(contains('len=')));
      } finally {
        debugPrint = debugPrintThrottled;
      }
    });
  });

  group('P34 整改：早到确认 / 续传确认 / 失败留痕 / 轮次归属', () {
    test('早到确认：无样本、记为无效观测；随后登记首发也不得造假样本'
        '（P34-R01）', () {
      final stats = OtaLinkStats(label: 'upgrade');
      // 确认先到（本段首发尚未登记）：此刻不存在合法起点。
      stats.recordAckConfirm(blockStart: 0, segs: const [2], segmentSize: 128);
      expect(stats.ackLatencySamplesUs, isEmpty);
      // 首发随后登记：不得把「首发结束」当这次早到确认的起点（起点晚于
      // 终点，是伪造样本）。如实记为无效观测并进入完整性缺口。
      stats.recordSegmentSendEnd(offsetBytes: 256, lengthBytes: 128);
      expect(stats.ackLatencySamplesUs, isEmpty);
      expect(stats.ackEarlyInvalid, 1);
      expect(stats.ackSampleIntegrity, 'partial:missing=1,early=1');
      // 迟到重复确认同样不得顶替出样本（该段已有有效确认）。
      stats.recordAckConfirm(blockStart: 0, segs: const [2], segmentSize: 128);
      expect(stats.ackLatencySamplesUs, isEmpty);
      expect(stats.ackEarlyInvalid, 1);
      // 摘要双通道一致：JSON 必须暴露同一无效观测事实。
      final t = stats.toJson()['transfer'] as Map<String, dynamic>;
      expect(t['ackEarlyInvalid'], 1);
      expect(t['ackSamples'], 'partial:missing=1,early=1');
    });

    test('resume BEGIN 确认并集：durable 前缀补样本，未发送前缀只是暂挂'
        '（P34-R02）', () async {
      final stats = OtaLinkStats(label: 'upgrade');
      stats.recordSegmentSendEnd(offsetBytes: 0, lengthBytes: 128);
      stats.recordSegmentSendEnd(offsetBytes: 128, lengthBytes: 128);
      await Future<void>.delayed(const Duration(milliseconds: 5));
      stats.recordSegmentSendEnd(offsetBytes: 4096, lengthBytes: 128);
      // durable 前缀 [0,4096)（本例只发过前两段）+ 当前块 bitmap 段 0。
      stats.recordResumeConfirm(
        durableOff: 4096,
        bitmap: 0x01,
        segmentSize: 128,
        arrivalUs: stats.nowUs(),
      );
      // 前缀已发送的 2 段（DATA ACK 丢失）+ bitmap 段（off 4096）共 3 样本。
      expect(stats.ackLatencySamplesUs, hasLength(3));
      expect(stats.ackSampleIntegrity, 'complete');
      expect(stats.ackEarlyInvalid, 0);
      // 终点取该有效 ACK 的到达时刻（非调用时刻）：前缀段样本 = 到达 −
      // 各自首发结束，含丢 ACK 后的重发等待与 ABORT + resume 全程。
      expect(stats.ackLatencySamplesUs[0], greaterThanOrEqualTo(4000));
      expect(stats.ackLatencySamplesUs[1], greaterThanOrEqualTo(4000));
      // 未发送的 30 个前缀段不制造样本，只暂挂为未发送确认。
      final t = stats.toJson()['transfer'] as Map<String, dynamic>;
      expect(t['ackEarlyUnsent'], 30);
      expect(t['ackSamples'], 'complete');
    });

    test('失败留痕幂等：只记首次终结阶段与原因（P34-R05）', () {
      final stats = OtaLinkStats(label: 'upgrade');
      stats.recordFailure(stage: 'discover', reason: 'ota-chars-missing');
      stats.recordFailure(stage: 'transfer', reason: 'later-diag');
      final f = stats.toJson()['failure'] as Map<String, dynamic>;
      expect(f['stage'], 'discover');
      expect(f['reason'], 'ota-chars-missing');
      // 未进入传输的失败不得伪装成成功传输：终态字段与原因并存。
      stats.recordTransferOutcome(ok: false);
      expect(stats.toJson()['transfer']['outcome'], 'fail');
      expect(f['stage'], 'discover');
    });

    test('probe 轮次：attempt 序号、逐轮结论与阶段窗口（P34-R06）', () {
      // 轮次外壳（不带 attempt）：每轮记一条，序号即尝试序号。
      final stats = OtaLinkStats(label: 'probe', device: 'AA:BB');
      stats.phaseStart('reconnect');
      stats.phaseStart('probe_attempt');
      stats.recordAttemptOutcome('timedOut');
      stats.phaseEnd('probe_attempt');
      stats.recordAttemptOutcome('completed');
      stats.phaseEnd('reconnect');
      final json = stats.toJson();
      expect(json['label'], 'probe');
      expect(json['attempt'], isNull, reason: '轮次外壳不冒充某一轮');
      expect(json['attempts'], <Map<String, Object>>[
        <String, Object>{'n': 1, 'outcome': 'timedOut'},
        <String, Object>{'n': 2, 'outcome': 'completed'},
      ]);
      expect(json['attemptEndUs'], isNotNull);
      final phases = json['phases'] as Map<String, dynamic>;
      expect((phases['probe_attempt'] as List).length, 2);
      final reconnect = phases['reconnect'] as List;
      expect(reconnect.length, 2);
      expect(reconnect[1] as int, greaterThanOrEqualTo(reconnect[0] as int));

      // 单轮实例（带 attempt）：结论序号必须等于本轮的尝试序号，不得回落
      // 成实例内下标 1——同一份 JSON 里 `attempt=3` 配 `n=1` 会把轮次归属
      // 读错（P34-R06）。
      final one = OtaLinkStats(label: 'probe', device: 'AA:BB', attempt: 3);
      one.recordAttemptOutcome('completed');
      final oneJson = one.toJson();
      expect(oneJson['attempt'], 3);
      expect(oneJson['attempts'], <Map<String, Object>>[
        <String, Object>{'n': 3, 'outcome': 'completed'},
      ]);
    });

    test('失败往返与失败尝试同样入账（getInfo/discover/platformWrite）'
        '（P34-R04）', () {
      final stats = OtaLinkStats(label: 'upgrade');
      stats.recordGetInfo(durationUs: 1000);
      stats.recordGetInfo(durationUs: 400, ok: false);
      stats.recordDiscover(durationUs: 900);
      stats.recordDiscover(durationUs: 120, error: true);
      stats.recordPlatformWrite(durationUs: 600, bytes: 128);
      stats.recordPlatformWrite(durationUs: 50, bytes: 0, error: true);
      final json = stats.toJson();
      final info = json['getInfo'] as Map<String, dynamic>;
      expect(info['calls'], 2);
      expect(info['failures'], 1);
      expect(info['totalUs'], 1400); // 失败往返的耗时同样登记
      final disc = json['discovers'] as Map<String, dynamic>;
      expect(disc['calls'], 2);
      expect(disc['errors'], 1);
      expect(disc['minUs'], 120);
      final pw = json['platformWrites'] as Map<String, dynamic>;
      expect(pw['calls'], 2);
      expect(pw['errors'], 1);
    });

    test('MTU 来源与写模式可区分回退值与真实协商值（P34-R04）', () {
      final negotiated = OtaLinkStats(label: 'upgrade');
      negotiated.recordMtu(
          requested: 517,
          chunkBytes: 509,
          durationUs: 400,
          source: 'negotiated');
      negotiated.recordCharsDiscovery(
          durationUs: 700, found: true, writeMode: 'writeWithResponse');
      final a = negotiated.toJson()['bind'] as Map<String, dynamic>;
      expect(a['mtuChunkBytes'], 509);
      expect(a['mtuSource'], 'negotiated');
      expect(a['writeMode'], 'writeWithResponse');
      // 回退值与真实协商值同为 20：只有 source 能区分二者。
      final fallback = OtaLinkStats(label: 'upgrade');
      fallback.recordMtu(
          requested: 517,
          chunkBytes: 20,
          durationUs: 900,
          source: 'error-fallback');
      final b = fallback.toJson()['bind'] as Map<String, dynamic>;
      expect(b['mtuChunkBytes'], 20);
      expect(b['mtuSource'], 'error-fallback');
      expect(b['mtuSource'], isNot(a['mtuSource']));
    });
  });
}
