import 'dart:async';
import 'dart:typed_data';

import 'package:crypto/crypto.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:ble_monitor/ota/ota_ble_codec.dart';
import 'package:ble_monitor/ota/ota_ble_transport.dart';
import 'package:ble_monitor/ota/ota_device_info.dart';
import 'package:ble_monitor/ota/ota_link_stats.dart';

/// OtaBleTransport：fake MCU 严格对照 Libraries/OTA/ota_ble_session.c 真值
/// （seq 模型 §5.1、BEGIN 幂等/新会话分支、DATA 段校验链、END durable+sha
/// 复述、ABORT teardown 保留 staging），覆盖 credit 窗口、断点续传、
/// 短尾块、取消、超时、丢 ACK 位图回收与 abortStatuses fail closed
/// （OTA-XC-FLUTTER-TRANSPORT）。
/// fake 设备身份（与 _FakeMcuHost/_McuSim 的 INFO 应答一致）：
/// BEGIN inspect 门禁的比对基准。
/// 顶层声明（RC3-01）：_McuSim 在 main() 作用域之外引用，局部声明
/// 会造成编译期作用域错误。
const fakeDeviceHardwareRev = 3;
const fakeDeviceLayoutId = 5;
const fakeDeviceBootVersion = 2;
const fakeCurrentVcode = 20801;

/// fake 设备 INFO 应答里的 image_sha256（32B 原始域）。
/// 顶层单一来源：INFO 应答与 inspect 门禁必须读同一份，否则 patch 的
/// base_sha8 比对会退化成"自证"。
final List<int> fakeDeviceImageSha256 =
    List<int>.unmodifiable(List<int>.generate(32, (i) => i * 3));

/// patch 包 base_sha8 的比对域 = 设备 image_sha256 的前 8 字节。
/// 真值链：HAL_Bluetooth.cpp:94 把 info.image_sha256 前 8B 复制进
/// ota_sd_device_t.base_image_sha8，ota_sd.c:331-336 再与 ETU 头
/// [52:60] 逐字节 memcmp。
final List<int> fakeDeviceBaseSha8 =
    List<int>.unmodifiable(fakeDeviceImageSha256.sublist(0, 8));

/// 标准 CRC-32/ISO-HDLC（RC3-03）：与 MCU boot_crc32 同构——init
/// 0xFFFFFFFF、多项式 0xEDB88320 反射、final ^0xFFFFFFFF。fake 的
/// ETU 头 CRC 门禁用。
/// 顶层声明（RC3-01）：_McuSim 在 main() 作用域之外引用。
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

/// 断言业务帧（非 GET_INFO 探针）在写通道废弃态被拒绝（RC3-05⑤）。
/// [where] 只用于失败原因定位。判据是错误码 + 拒绝发生在写之前
/// （调用方由 `pendingByteCount` 另行核对字节数未变）。
Future<void> _expectBusinessWriteRefused(
    OtaBleTransport transport, String where) async {
  try {
    await transport.begin(
      totalLen: 4096,
      packageSha256: List<int>.filled(32, 7),
      etuHeader: List<int>.filled(64, 9),
      timeout: const Duration(milliseconds: 300),
    );
    fail('$where：废弃态下业务帧必须被拒绝');
  } on OtaTransportException catch (e) {
    expect(e.code, 'WRITE_TIMEOUT', reason: '$where：拒绝码应为写通道废弃');
  }
}

void main() {
  /// 构造合法 ETU 头（64B，RC3-03）：字段布局对齐 MCU 真值
  /// ota_sd.c（偏移 enum + ota_sd_inspect_header）——magic "ETU1"、
  /// header_len=64、flags（默认 0x000B full，可传 0x0007 patch）、
  /// algorithm=1、key=1、payload_len、payload_crc32 占位（fake 不校验
  /// 内容 CRC）、target_vcode（默认高于 fake 当前版本）、base_vcode、
  /// hardware_rev/layout_id/min_boot 与 fake 设备身份匹配、
  /// base_sha8（默认按 flags 取全零/设备摘要前 8B）、
  /// header_crc32 覆盖前 60B。
  Uint8List buildEtuHeader(
    int payloadLen, {
    int targetVcode = 20900,
    int flags = 0x000B,
    int? baseVcode,
    List<int>? baseSha8,
  }) {
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

    final isPatch = flags == 0x0007;
    put16(4, 64); // header_len
    put16(6, flags);
    put32(8, 1); // algorithm v1
    put32(12, 1); // key v1
    put32(32, payloadLen);
    put32(36, 0x11223344); // payload_crc32 占位
    put32(40, targetVcode);
    // base_vcode：full 恒 0；patch 必须等于设备当前版本。
    put32(44, baseVcode ?? (isPatch ? fakeCurrentVcode : 0));
    put16(48, fakeDeviceHardwareRev);
    h[50] = fakeDeviceLayoutId;
    h[51] = fakeDeviceBootVersion; // min_boot <= 设备 boot_version
    // base_sha8：full 必须全零；patch 必须等于设备 image_sha256 前 8B。
    final sha8 =
        baseSha8 ?? (isPatch ? fakeDeviceBaseSha8 : List<int>.filled(8, 0));
    h.setRange(52, 60, sha8);
    put32(60, crc32Of(h.sublist(0, 60)));
    return h;
  }

  Uint8List packageBytes(int size) {
    // RC3-03：包前 64B 必须是合法 ETU 头——fake MCU 的 BEGIN inspect
    // 门禁对齐真值 ota_sd_inspect_header，任意伪随机字节会被
    // ERR_HDR 拒绝，所有正常路径用例失去意义。头后保持伪随机正文。
    final bytes = Uint8List.fromList(
        List<int>.generate(size, (i) => (i * 11 + 5) & 0xFF));
    bytes.setRange(0, 64, buildEtuHeader(size - 64));
    return bytes;
  }

  Uint8List etuHeaderOf(Uint8List package) =>
      Uint8List.fromList(package.sublist(0, 64));

  /// BEGIN 携带的 package_sha256 用真实 SHA-256（RC3-03）：fake MCU 的
  /// 内容级流式摘要 oracle 要求摘要与字节真实对应，任意的 32B 会立即
  /// 撞 END ERR_SHA，使全部正常路径用例失去意义。
  List<int> shaOf(Uint8List package) => sha256.convert(package).bytes;

  group('getDeviceInfo', () {
    test('GET_INFO 往返解析身份，INFO session=0 且 seq 回显', () async {
      final mcu = _McuSim();
      final transport = OtaBleTransport(channel: mcu);
      final info = await transport.getDeviceInfo();
      expect(info.deviceModel, 'e-track-at32f435');
      expect(info.hardwareRevision, 3);
      expect(mcu.writtenFrames.length, 1);
      expect(mcu.writtenFrames.first[2], OtaBleCodec.cmdGetInfo);
      // INFO 应答帧 session=0、seq=请求 seq（请求 seq=0）。
      final infoFrame = mcu.sentFrames.single;
      expect(infoFrame.session, 0);
      expect(infoFrame.seq, 0);
    });

    test('断连：写帧抛 DISCONNECTED', () async {
      final mcu = _McuSim()..connected = false;
      final transport = OtaBleTransport(channel: mcu);
      try {
        await transport.getDeviceInfo();
        fail('应抛 DISCONNECTED');
      } on OtaTransportException catch (e) {
        expect(e.code, 'DISCONNECTED');
      }
    });
  });

  group('P34 durable recovery under liveness ACKs', () {
    for (final unknownSeq in [false, true]) {
      test('missing block tail is retried despite ignored ACKs '
          '(unknownSeq=$unknownSeq)', () async {
        final package = packageBytes(8192);
        final mcu = _TailLossWithLivenessMcu(unknownSeq: unknownSeq);
        final stats = OtaLinkStats(label: 'upgrade');
        final transport = OtaBleTransport(
          channel: mcu,
          stats: stats,
          ackTimeout: const Duration(milliseconds: 150),
          noProgressTimeout: const Duration(milliseconds: 900),
        );
        try {
          final ack = await transport.transfer(
            package: package,
            packageSha256: shaOf(package),
            etuHeader: etuHeaderOf(package),
          );
          expect(ack.isOk, isTrue);
          expect(ack.durableOff, package.length);
          expect(mcu.stagedDurable, package.length);
          expect(mcu._stagedBytes, orderedEquals(package));
          expect(mcu.tailAttempts, hasLength(2));
          expect(mcu.tailAttempts.last.seq, mcu.tailAttempts.first.seq);
          expect(mcu.tailAttempts.last.payload,
              orderedEquals(mcu.tailAttempts.first.payload));
          expect(mcu.livenessAcks, greaterThan(0));
          expect(stats.acksDuplicate, greaterThan(0));
          expect(stats.retransmitFrames, 1);
          expect(mcu.beginCalls, 1);
          expect(mcu.abortCalls, 0);
          expect(mcu.endCalls, 1);
        } finally {
          mcu.stopLiveness();
          await transport.dispose();
        }
      });
    }

    test('liveness ACKs do not extend the durable deadline', () async {
      final package = packageBytes(8192);
      final mcu = _TailLossWithLivenessMcu(permanentLoss: true);
      final transport = OtaBleTransport(
        channel: mcu,
        ackTimeout: const Duration(milliseconds: 150),
        noProgressTimeout: const Duration(milliseconds: 900),
        retries: 999,
      );
      try {
        await expectLater(
          transport.transfer(
            package: package,
            packageSha256: shaOf(package),
            etuHeader: etuHeaderOf(package),
          ),
          throwsA(isA<OtaTransportException>().having(
              (error) => error.code, 'code', 'NO_DURABLE_PROGRESS')),
        );
        expect(mcu.tailAttempts.length, greaterThan(1));
        expect(mcu.tailAttempts.map((frame) => frame.seq).toSet(), hasLength(1));
        expect(mcu.stagedDurable, 4096);
        expect(mcu.endCalls, 0);
      } finally {
        mcu.stopLiveness();
        await transport.dispose();
      }
    });
  });

  group('transfer', () {
    test('完整传输 8192：BEGIN→两块 DATA→END ACK OK，durable 逐块前进',
        () async {
      final package = packageBytes(8192); // 2 个 4KB 块
      final mcu = _McuSim();
      final durableProgress = <int>[];
      final transport = OtaBleTransport(channel: mcu);
      final ack = await transport.transfer(
        package: package,
        packageSha256: shaOf(package),
        etuHeader: etuHeaderOf(package),
        onDurableProgress: (off, total) => durableProgress.add(off),
      );
      expect(ack.isOk, isTrue);
      expect(ack.status, OtaBleCodec.statusOk);
      expect(ack.durableOff, 8192);
      // BEGIN 报 0 起点 + 每块提交后各一次。
      expect(durableProgress, [0, 4096, 8192]);
      // BEGIN + 64 DATA + 1 END；DATA 帧数精确 64（无重发）。
      expect(
        mcu.writtenFrames.where((f) => f[2] == OtaBleCodec.cmdData).length,
        64,
      );
      // DATA 帧使用 BEGIN ACK 分配的 session（MCU session_id 从 1 起）。
      final dataSessions = mcu.dataFrames.map((f) => f.session).toSet();
      expect(dataSessions, {1});
      // BEGIN 只发一次（正常路径不重复 BEGIN）。
      expect(mcu.beginCalls, 1);
      expect(mcu.writtenFrames.last[2], OtaBleCodec.cmdEnd);
      // END 帧净荷复述 package_sha256（32B）。
      final endFrame = mcu.writtenFrames.last;
      expect(endFrame.length,
          OtaBleCodec.frameHeaderSize + 32 + OtaBleCodec.frameCrcSize);
    });

    test('短尾块 4096+129B：33 段，最后 1 段 1B，全部送达', () async {
      final package = packageBytes(4096 + 129);
      final mcu = _McuSim();
      final durableProgress = <int>[];
      final transport = OtaBleTransport(channel: mcu);
      final ack = await transport.transfer(
        package: package,
        packageSha256: shaOf(package),
        etuHeader: etuHeaderOf(package),
        onDurableProgress: (off, total) => durableProgress.add(off),
      );
      expect(ack.isOk, isTrue);
      expect(ack.durableOff, 4225);
      expect(durableProgress.last, 4225);
      // 尾块只含 2 段：off 4096（128B）与 4224（1B）。
      final tailOffsets =
          mcu.dataOffsets.where((off) => off >= 4096).toList();
      expect(tailOffsets, [4096, 4224]);
      // 最后一段 DATA payload = 4B offset + 1B 数据。
      final lastData = mcu.dataFrames.last;
      expect(lastData.payload.length, 5);
      expect(
          lastData.payload[0] |
              (lastData.payload[1] << 8) |
              (lastData.payload[2] << 16) |
              (lastData.payload[3] << 24),
          4224);
    });

    test('断点续传（真值 journal）：块 0 已提交，BEGIN 报 [4096,0]，'
        '只发块 1，SHA 跨会话前缀连续（RC3-03）', () async {
      final package = packageBytes(8192); // 2 块
      final mcu = _McuSim();
      // 手工构造"上次传输在块 0 提交后中断"：BEGIN(seq=10) + 块 0 的
      // 32 段 DATA（seq=11..42）→ 块收齐提交 journal durable=4096 →
      // ABORT teardown（模拟断线：RAM 清空，durable/字节保留）。
      Uint8List beginFrame(int seq) => OtaBleCodec.encodeCommand(
            cmd: OtaBleCodec.cmdBegin,
            session: 0,
            seq: seq,
            payload: OtaBleCodec.encodeBeginPayload(
              totalLen: package.length,
              packageSha256: shaOf(package),
              etuHeader: etuHeaderOf(package),
            ),
          );
      await mcu.writeChunk(beginFrame(10));
      for (var i = 0; i < 32; i++) {
        await mcu.writeChunk(OtaBleCodec.encodeCommand(
          cmd: OtaBleCodec.cmdData,
          session: 1,
          seq: 11 + i,
          payload: OtaBleCodec.encodeDataPayload(i * 128,
              package.sublist(i * 128, i * 128 + OtaBleCodec.dataSegmentSize)),
        ));
      }
      await mcu.writeChunk(OtaBleCodec.encodeCommand(
        cmd: OtaBleCodec.cmdAbort,
        session: 1,
        seq: 43,
      ));
      // 新 transport resume：BEGIN 回真实 journal 状态 [4096, 0]。
      final transport = OtaBleTransport(channel: mcu);
      final ack = await transport.transfer(
        package: package,
        packageSha256: shaOf(package),
        etuHeader: etuHeaderOf(package),
      );
      expect(ack.isOk, isTrue);
      // BEGIN ACK 权威值 = [durable=4096, bitmap=0]（RAM 不持久，真值）。
      expect(mcu.beginAckStates.last, [4096, 0]);
      // 只发块 1：32 段（off 4096..3968+4096），不重发已提交块。
      final newOffsets = mcu.dataOffsets
          .skip(32) // 手工构造的 32 段在前
          .toList();
      expect(newOffsets.length, 32);
      expect(newOffsets.first, 4096);
      expect(newOffsets.last, 4096 + 31 * 128);
      // END OK 依赖内容级流式摘要跨会话连续：journal 前缀（块 0 字节）
      // + 本次新收段 == 整包 SHA（fake 真值 oracle，RC3-03）。
      expect(ack.durableOff, 8192);
    }, timeout: const Timeout(Duration(seconds: 60)));

    test('credit 窗口上限：windowSegments=4 时在途段不超过 4', () async {
      final package = packageBytes(4096);
      final mcu = _McuSim()
        ..ackDelay = const Duration(milliseconds: 30);
      final transport = OtaBleTransport(channel: mcu);
      final ack = await transport.transfer(
        package: package,
        packageSha256: shaOf(package),
        etuHeader: etuHeaderOf(package),
        windowSegments: 4,
      );
      expect(ack.isOk, isTrue);
      expect(mcu.maxInFlight, lessThanOrEqualTo(4));
      // 窗口收紧不丢段：32 段全部送达。
      expect(mcu.dataOffsets.length, 32);
    }, timeout: const Timeout(Duration(seconds: 60)));

    test('重复 ACK 幂等：同段双份 ACK 不破坏传输', () async {
      final package = packageBytes(4096);
      final mcu = _McuSim()..duplicateDataAck = true;
      final transport = OtaBleTransport(channel: mcu);
      final ack = await transport.transfer(
        package: package,
        packageSha256: shaOf(package),
        etuHeader: etuHeaderOf(package),
      );
      expect(ack.isOk, isTrue);
      expect(mcu.dataOffsets.length, 32);
    });

    test('通知单字节分片：帧重组不受分片粒度影响', () async {
      final package = packageBytes(4096);
      final mcu = _McuSim()..chunkMode = _ChunkMode.byte;
      final transport = OtaBleTransport(channel: mcu);
      final ack = await transport.transfer(
        package: package,
        packageSha256: shaOf(package),
        etuHeader: etuHeaderOf(package),
      );
      expect(ack.isOk, isTrue);
      expect(mcu.dataOffsets.length, 32);
    }, timeout: const Timeout(Duration(seconds: 60)));

    test('通知流混入垃圾前缀：丢字节重同步后传输仍成功', () async {
      final package = packageBytes(4096);
      final mcu = _McuSim()..garbagePrefixBytes = 3;
      final transport = OtaBleTransport(channel: mcu);
      final ack = await transport.transfer(
        package: package,
        packageSha256: shaOf(package),
        etuHeader: etuHeaderOf(package),
      );
      expect(ack.isOk, isTrue);
      expect(mcu.dataOffsets.length, 32);
    });

    test('MCU 谎报提交（落盘静默丢失）：END ERR_STATE 暴露 → resume BEGIN '
        'durable 倒退 → fail closed ACK_MALFORMED（RC3-03）', () async {
      final package = packageBytes(4096);
      final mcu = _McuSim()..loseSegmentOff = 16 * 128; // 段 16
      final transport = OtaBleTransport(channel: mcu);
      try {
        await transport.transfer(
          package: package,
          packageSha256: shaOf(package),
          etuHeader: etuHeaderOf(package),
        );
        fail('应 fail closed');
      } on OtaTransportException catch (e) {
        // 谎报链：DATA ACK 曾报 durable=4096（块尾）骗过块循环，END 按
        // 真实 journal durable=0 拒绝 ERR_STATE；resume 的 ABORT teardown
        // 清谎报层后 BEGIN 回真实 [0,0]，与 transport 已采信的 lastDurable
        // =4096 倒退 → fail closed（RC3-03：修复用例曾期望重发整块成功
        // ——与 BEGIN 倒退拒绝矛盾，真值 MCU 不会谎报 durable，此故障
        // 模型必须终止而非续传）。
        expect(e.code, 'ACK_MALFORMED');
      }
      // END 一次 ERR_STATE；resume 在 BEGIN 倒退处终止（无第二次 END）。
      expect(mcu.endCalls, 1);
      expect(mcu.beginCalls, 2); // BEGIN + resume BEGIN
      expect(mcu.abortCalls, 1); // resume 前主动 ABORT
      // resume 的 BEGIN ACK 回真实 staging 状态：teardown 已清 RAM 层，
      // journal durable=0、bitmap=0。
      expect(mcu.beginAckStates.length, 2);
      expect(mcu.beginAckStates[1], [0, 0]);
      // 首发 32 段后即终止（resume BEGIN 抛出，无重发）。
      expect(
        mcu.writtenFrames.where((f) => f[2] == OtaBleCodec.cmdData).length,
        32,
      );
      expect(mcu.dataOffsets.toSet().length, 32);
      // 谎报期间 MCU ACK 曾报 durable=4096（块尾）骗过块循环，
      // END 校验按真实 journal durable=0 拒绝。
      expect(mcu.sentFrames.any((f) =>
          f.cmd == OtaBleCodec.rspAckData &&
          f.payload.length == 9 &&
          f.payload[0] == OtaBleCodec.statusOk &&
          (f.payload[1] |
                  (f.payload[2] << 8) |
                  (f.payload[3] << 16) |
                  (f.payload[4] << 24)) ==
              4096), isTrue);
    }, timeout: const Timeout(Duration(seconds: 60)));

    test('abortStatuses（ERR_OTA_DISABLED）→ terminal，不重试', () async {
      final package = packageBytes(4096);
      final mcu = _McuSim()..dataAckStatus = OtaBleCodec.statusErrOtaDisabled;
      final transport = OtaBleTransport(channel: mcu);
      final ack = await transport.transfer(
        package: package,
        packageSha256: shaOf(package),
        etuHeader: etuHeaderOf(package),
      );
      expect(ack.terminal, isTrue);
      expect(ack.status, OtaBleCodec.statusErrOtaDisabled);
    });

    test('BEGIN ACK 拒绝（ERR_HW_REV）→ 抛 ACK_STATUS', () async {
      final package = packageBytes(4096);
      final mcu = _McuSim()..beginAckStatus = OtaBleCodec.statusErrHwRev;
      final transport = OtaBleTransport(channel: mcu);
      try {
        await transport.transfer(
          package: package,
          packageSha256: shaOf(package),
          etuHeader: etuHeaderOf(package),
        );
        fail('应抛 ACK_STATUS');
      } on OtaTransportException catch (e) {
        expect(e.code, 'ACK_STATUS');
        expect(e.status, OtaBleCodec.statusErrHwRev);
      }
    });

    test('BEGIN 门禁：target_vcode 不高于当前版本 → ERR_VERSION（RC3-03⑤）',
        () async {
      final package = packageBytes(4096);
      // 同版本重装（20801）：真实 MCU inspect 链的 target_vcode 门禁
      // 必拒——此前 fake 缺此检查，恢复正例读完 vcode 再装同版本仍
      // "成功"，与真值相悖。
      final header = buildEtuHeader(package.length - 64, targetVcode: 20801);
      final mcu = _McuSim();
      final transport = OtaBleTransport(channel: mcu);
      try {
        await transport.transfer(
          package: package,
          packageSha256: shaOf(package),
          etuHeader: header,
        );
        fail('应抛 ACK_STATUS');
      } on OtaTransportException catch (e) {
        expect(e.code, 'ACK_STATUS');
        expect(e.status, OtaBleCodec.statusErrVersion);
      }
    });

    test('BEGIN 门禁：ETU 头内容与 CRC 不符 → ERR_HDR（RC3-03⑤）',
        () async {
      final package = packageBytes(4096);
      // 篡改 target_vcode 低位但不更新 header_crc32：真值检查顺序为
      // magic→header_len→header_crc→…→version，CRC 门在前必拒。
      final header = buildEtuHeader(package.length - 64);
      header[40] ^= 0xFF;
      final mcu = _McuSim();
      final transport = OtaBleTransport(channel: mcu);
      try {
        await transport.transfer(
          package: package,
          packageSha256: shaOf(package),
          etuHeader: header,
        );
        fail('应抛 ACK_STATUS');
      } on OtaTransportException catch (e) {
        expect(e.code, 'ACK_STATUS');
        expect(e.status, OtaBleCodec.statusErrHdr);
      }
    });

    // RC3-03：patch 包（flags=0x0007）此前完全没有门禁分支——fake 只查
    // full 的 base 域，patch 头无论 base_vcode/base_sha8 填什么都放行。
    // 真值 ota_sd.c:329-341 对 patch 的 base 绑定与 full 一样是硬门禁：
    // base_vcode 必须等于设备当前版本、base_sha8 必须等于设备
    // image_sha256 前 8B，否则 ERR_BASE；payload_len<=40（patch 内层头）
    // 属长度域 ERR_LEN。下面三例逐条区分这三条真值规则。
    test('BEGIN 门禁：patch 的 base_vcode 不匹配设备当前版本 → ERR_BASE'
        '（RC3-03）', () async {
      final package = packageBytes(4096);
      // 设备当前版本 20801；patch 声称基线 20700（旧基线包错投）。
      final header = buildEtuHeader(
        package.length - 64,
        flags: 0x0007,
        baseVcode: 20700,
      );
      final mcu = _McuSim();
      final transport = OtaBleTransport(channel: mcu);
      try {
        await transport.transfer(
          package: package,
          packageSha256: shaOf(package),
          etuHeader: header,
        );
        fail('应抛 ACK_STATUS');
      } on OtaTransportException catch (e) {
        expect(e.code, 'ACK_STATUS');
        expect(e.status, OtaBleCodec.statusErrBase);
      }
    });

    test('BEGIN 门禁：patch 的 base_sha8 与设备镜像摘要不符 → ERR_BASE'
        '（RC3-03）', () async {
      final package = packageBytes(4096);
      // 版本号对得上但基线镜像不是本机这一份（同版本不同构建）：
      // 真值仍必拒，否则打到错误基线上会做出坏镜像。
      final wrongSha8 = List<int>.of(fakeDeviceBaseSha8);
      wrongSha8[7] ^= 0x01;
      final header = buildEtuHeader(
        package.length - 64,
        flags: 0x0007,
        baseSha8: wrongSha8,
      );
      final mcu = _McuSim();
      final transport = OtaBleTransport(channel: mcu);
      try {
        await transport.transfer(
          package: package,
          packageSha256: shaOf(package),
          etuHeader: header,
        );
        fail('应抛 ACK_STATUS');
      } on OtaTransportException catch (e) {
        expect(e.code, 'ACK_STATUS');
        expect(e.status, OtaBleCodec.statusErrBase);
      }
    });

    test('BEGIN 门禁：patch payload_len 不大于内层头 40B → ERR_LEN'
        '（RC3-03）', () async {
      // package_len = 64+40 = 104：base 域全部合法，只有 payload_len
      // 恰好等于内层头长度。真值用 `<=` 判定，边界值 40 必须落 ERR_LEN
      // 而不是通过——这一例同时钉死边界方向。
      final package = packageBytes(104);
      final header = buildEtuHeader(40, flags: 0x0007);
      final mcu = _McuSim();
      final transport = OtaBleTransport(channel: mcu);
      try {
        await transport.transfer(
          package: package,
          packageSha256: shaOf(package),
          etuHeader: header,
        );
        fail('应抛 ACK_STATUS');
      } on OtaTransportException catch (e) {
        expect(e.code, 'ACK_STATUS');
        expect(e.status, OtaBleCodec.statusErrLen);
      }
    });

    test('BEGIN 门禁：patch base 域与长度全部合法 → 放行（RC3-03 反向）',
        () async {
      // 与上三例只差在被测字段本身：证明新增的 patch 分支不是"见
      // patch 就拒"的常量拒绝，而是逐字段判定。
      final package = packageBytes(4096);
      final header = buildEtuHeader(package.length - 64, flags: 0x0007);
      package.setRange(0, 64, header); // 包体首 64B 与 BEGIN 头一致
      final mcu = _McuSim();
      final transport = OtaBleTransport(channel: mcu);
      final ack = await transport.transfer(
        package: package,
        packageSha256: shaOf(package),
        etuHeader: header,
      );
      expect(ack.status, OtaBleCodec.statusOk);
    });

    test('BEGIN 门禁：full 的 payload_len=0 落 ERR_LEN 而非 ERR_BASE'
        '（RC3-03）', () async {
      // 真值把空 full 归到 OTA_SD_ERR_PACKAGE_LENGTH（→ERR_LEN），
      // 旧 fake 把它并进 base 分支返回 ERR_BASE：错误码归类错误会让
      // 上层"基线不匹配 vs 包本身为空"两类终态诊断互相冒充。
      final package = packageBytes(64); // package_len=64，payload_len=0
      final header = buildEtuHeader(0);
      final mcu = _McuSim();
      final transport = OtaBleTransport(channel: mcu);
      try {
        await transport.transfer(
          package: package,
          packageSha256: shaOf(package),
          etuHeader: header,
        );
        fail('应抛 ACK_STATUS');
      } on OtaTransportException catch (e) {
        expect(e.code, 'ACK_STATUS');
        expect(e.status, OtaBleCodec.statusErrLen);
      }
    });

    test('BEGIN 门禁：full 携带非零 base_sha8 仍是 ERR_BASE（RC3-03 反向）',
        () async {
      // 与上一例配对：证明 full 分支被拆成 base/长度两条后，base 侧
      // 判据没有被顺手删掉。
      final package = packageBytes(4096);
      final header = buildEtuHeader(
        package.length - 64,
        baseSha8: List<int>.filled(8, 0x5A),
      );
      final mcu = _McuSim();
      final transport = OtaBleTransport(channel: mcu);
      try {
        await transport.transfer(
          package: package,
          packageSha256: shaOf(package),
          etuHeader: header,
        );
        fail('应抛 ACK_STATUS');
      } on OtaTransportException catch (e) {
        expect(e.code, 'ACK_STATUS');
        expect(e.status, OtaBleCodec.statusErrBase);
      }
    });

    test('fake 门禁：越当前 4KB 窗的段 → ERR_OFFSET（RC3-03⑤）', () async {
      final package = packageBytes(8192);
      final mcu = _McuSim();
      // 手工 BEGIN 建立 ACTIVE（durable=0）后直接对 fake 写越窗段：
      // 真值 ota_staging_receive 的 ERR_RANGE 语义（off-durable >=
      // 块长必拒，映射 ERR_OFFSET）。缺此门禁时 fake 照单接收窗口外
      // 段，掩盖 transport 侧窗口纪律的真实性。
      await mcu.writeChunk(OtaBleCodec.encodeCommand(
        cmd: OtaBleCodec.cmdBegin,
        session: 0,
        seq: 10,
        payload: OtaBleCodec.encodeBeginPayload(
          totalLen: package.length,
          packageSha256: shaOf(package),
          etuHeader: etuHeaderOf(package),
        ),
      ));
      await mcu.writeChunk(OtaBleCodec.encodeCommand(
        cmd: OtaBleCodec.cmdData,
        session: 1,
        seq: 11,
        payload: OtaBleCodec.encodeDataPayload(4096,
            package.sublist(4096, 4096 + OtaBleCodec.dataSegmentSize)),
      ));
      expect(mcu.dataAckStatuses.last, OtaBleCodec.statusErrOffset);
      // 窗口内段（off=0）不受影响：正常 OK。
      await mcu.writeChunk(OtaBleCodec.encodeCommand(
        cmd: OtaBleCodec.cmdData,
        session: 1,
        seq: 12,
        payload: OtaBleCodec.encodeDataPayload(0,
            package.sublist(0, OtaBleCodec.dataSegmentSize)),
      ));
      expect(mcu.dataAckStatuses.last, OtaBleCodec.statusOk);
    });

    test('未知 ACK status → ACK 解析失败（fail closed）', () async {
      final package = packageBytes(4096);
      final mcu = _McuSim()..dataAckStatus = 0x7F;
      final transport = OtaBleTransport(channel: mcu);
      try {
        await transport.transfer(
          package: package,
          packageSha256: shaOf(package),
          etuHeader: etuHeaderOf(package),
        );
        fail('应 fail closed');
      } on OtaTransportException catch (e) {
        // 视图解析失败路径（未知 status 0x7F 不在闭集合内）。
        expect(e.code, 'ACK_MALFORMED');
      }
    });

    test('全丢 ACK：DATA 照常提交，内部 ABORT+BEGIN 用 journal 恢复后 '
        'END 合法成功（RC3-02⑤）', () async {
      final package = packageBytes(4096);
      final mcu = _McuSim()..respondDataAck = false;
      final transport = OtaBleTransport(
        channel: mcu,
        ackTimeout: const Duration(milliseconds: 60),
        retries: 2,
      );
      // respondDataAck=false 只丢应答，不阻止 DATA 提交：4096B 收满后
      // 重发超限触发内部 ABORT teardown + BEGIN 重对齐；新 BEGIN 幂等
      // 回 [4096, 0]（journal 全前缀重建 SHA），无段可发直接 END 成功。
      // §6.14.3：不得为迁就 TIMEOUT 期望而声称该输入必然失败——合法
      // 持久化恢复就是这个输入的正确结果。
      final ack = await transport.transfer(
        package: package,
        packageSha256: shaOf(package),
        etuHeader: etuHeaderOf(package),
      );
      expect(ack.isOk, isTrue);
      expect(ack.durableOff, 4096);
      // 重发确实发生（首发 32 段 + 2 轮窗口重发）。
      expect(
        mcu.writtenFrames.where((f) => f[2] == OtaBleCodec.cmdData).length,
        greaterThanOrEqualTo(64),
      );
      expect(mcu.stagedDurable, 4096);
    }, timeout: const Timeout(Duration(seconds: 60)));

    test('无 ACK 且无 resume 余量（retries=0）：重发超限抛 TIMEOUT，'
        'journal 保留可续传（RC3-02⑤）', () async {
      final package = packageBytes(4096);
      final mcu = _McuSim()..respondDataAck = false;
      final transport = OtaBleTransport(
        channel: mcu,
        ackTimeout: const Duration(milliseconds: 60),
        retries: 0, // resumeLeft=0：重发超限不得再走 ABORT+BEGIN 恢复
      );
      try {
        await transport.transfer(
          package: package,
          packageSha256: shaOf(package),
          etuHeader: etuHeaderOf(package),
        );
        fail('应中止');
      } on OtaTransportException catch (e) {
        expect(e.code, 'TIMEOUT');
      }
      // TIMEOUT 是当轮等待的失败，不是 MCU 数据丢失（RC3-02⑤）：全丢
      // ACK 期间 fake 已把 4096B 真正提交 journal。协议允许的后续是新
      // 连接再 transfer 续传——同一 transport 的 seq 连续计数会超前
      // MCU expected_seq（同包 BEGIN 幂等不重置，真值 :377-386），无段
      // 可发时 END 被超前的 seq 拒 ERR_SEQ，且 retries=0 无 resume 余量
      // 重对齐；新连接的 transport seq 从头开始，BEGIN（无 seq 检查）
      // 幂等回 [4096, 0]，END 落后 seq 幂等回当前进度 OK（真值
      // :636-642），内容 SHA 跨轮连续即 OK。
      expect(mcu.stagedDurable, 4096);
      mcu.respondDataAck = true;
      // 新连接语义：旧 transport 已因 TIMEOUT 结束但持有通知订阅，先
      // dispose 释放（fake 已改 broadcast，不 dispose 会让两个 transport
      // 同时消费同一 ACK 流，产生串台）。
      await transport.dispose();
      final transport2 = OtaBleTransport(channel: mcu);
      final ack2 = await transport2.transfer(
        package: package,
        packageSha256: shaOf(package),
        etuHeader: etuHeaderOf(package),
      );
      expect(ack2.isOk, isTrue);
      expect(ack2.durableOff, 4096);
    }, timeout: const Timeout(Duration(seconds: 60)));

    test('无 durable 进展超时：NO_DURABLE_PROGRESS 中止', () async {
      final package = packageBytes(4096);
      final mcu = _McuSim()..respondDataAck = false;
      final transport = OtaBleTransport(
        channel: mcu,
        ackTimeout: const Duration(milliseconds: 50),
        retries: 999, // 压制重发超限，让 no-progress 窗口先触发
        noProgressTimeout: const Duration(milliseconds: 300),
      );
      try {
        await transport.transfer(
          package: package,
          packageSha256: shaOf(package),
          etuHeader: etuHeaderOf(package),
        );
        fail('应中止');
      } on OtaTransportException catch (e) {
        expect(e.code, 'NO_DURABLE_PROGRESS');
      }
    }, timeout: const Timeout(Duration(seconds: 60)));

    test('取消 mid-transfer：抛 CANCELLED 且停止发送循环', () async {
      final package = packageBytes(4096);
      final mcu = _McuSim()..respondDataAck = false;
      final transport = OtaBleTransport(
        channel: mcu,
        ackTimeout: const Duration(milliseconds: 400),
        retries: 5,
      );
      final future = transport.transfer(
        package: package,
        packageSha256: shaOf(package),
        etuHeader: etuHeaderOf(package),
      );
      // 等待发送窗口填满并进入 ACK 等待后取消。
      await Future<void>.delayed(const Duration(milliseconds: 100));
      expect(transport.isCancelled, isFalse);
      transport.cancel();
      expect(transport.isCancelled, isTrue);
      try {
        await future;
        fail('应抛 CANCELLED');
      } on OtaTransportException catch (e) {
        expect(e.code, 'CANCELLED');
      }
      // 取消后不再有新帧写入。
      final framesAfterCancel = mcu.writtenFrames.length;
      await Future<void>.delayed(const Duration(milliseconds: 100));
      expect(mcu.writtenFrames.length, framesAfterCancel);
      // 取消后的实例永久失效。
      try {
        await transport.getDeviceInfo();
        fail('取消后实例应失效');
      } on OtaTransportException catch (e) {
        expect(e.code, 'CANCELLED');
      }
    }, timeout: const Timeout(Duration(seconds: 60)));

    test('END ACK 非 OK（ERR_SHA）→ isOk false', () async {
      final package = packageBytes(4096);
      final mcu = _McuSim()..endAckStatus = OtaBleCodec.statusErrSha;
      final transport = OtaBleTransport(channel: mcu);
      final ack = await transport.transfer(
        package: package,
        packageSha256: shaOf(package),
        etuHeader: etuHeaderOf(package),
      );
      expect(ack.isOk, isFalse);
      expect(ack.status, OtaBleCodec.statusErrSha);
    });

    test('abortBestEffort：连接断开时静默失败不抛', () async {
      final mcu = _McuSim()..connected = false;
      final transport = OtaBleTransport(channel: mcu);
      // 不抛即通过。
      await transport.abortBestEffort();
    });

    test('dispose 后复用抛 DISPOSED', () async {
      final mcu = _McuSim();
      final transport = OtaBleTransport(channel: mcu);
      await transport.dispose();
      try {
        await transport.getDeviceInfo();
        fail('释放后实例应失效');
      } on OtaTransportException catch (e) {
        expect(e.code, 'DISPOSED');
      }
    });
  });

  group('MCU 会话真值对照（RC2-05/06）', () {
    test('DATA 回 ERR_SEQ（expected_seq 失配）：ABORT+BEGIN 重对齐后续传成功',
        () async {
      final package = packageBytes(4096);
      final mcu = _McuSim()..errSeqAtDataCounts = {3}; // 第 3 段 DATA
      final transport = OtaBleTransport(
        channel: mcu,
        ackTimeout: const Duration(milliseconds: 200),
      );
      final ack = await transport.transfer(
        package: package,
        packageSha256: shaOf(package),
        etuHeader: etuHeaderOf(package),
      );
      expect(ack.isOk, isTrue);
      // ERR_SEQ → ABORT（teardown）→ BEGIN（新会话重置 expected_seq）。
      expect(mcu.abortCalls, 1);
      expect(mcu.beginCalls, 2);
      // resume 的 BEGIN ACK 回真实进度：注入后 expected_seq 停在段 2，
      // 后续 DATA 全被 ERR_SEQ 拒收；ABORT teardown 清 RAM 层（真值
      // memset receiver），journal durable=0、bitmap=0——不是缺 1 段的
      // 位图（RC3-03 算例：缺 30 段是 RAM 保留模型的算例，真值整块重来）。
      expect(mcu.beginAckStates.length, 2);
      expect(mcu.beginAckStates[1], [0, 0]);
      // 首发 32 段 + resume 整块 32 段；无其他重发。
      expect(
        mcu.writtenFrames.where((f) => f[2] == OtaBleCodec.cmdData).length,
        64,
      );
    }, timeout: const Timeout(Duration(seconds: 60)));

    // RC3-06：一次 seq 断档 = 恰好一次预算处置。ERR_SEQ 注入后 MCU 的
    // expected_seq 停住，同一发窗里剩余 ~29 帧全部真实回 ERR_SEQ；若实现
    // 按「每份错误 ACK 扣一次预算」计费，retries=1 会在第二份就耗尽并抛
    // ACK_STATUS。传输成功即证明 30 份错误 ACK 只折算成一次恢复处置
    // （_TransferAckView 首错锁存 + takeError 取走清零）。
    test('同一发窗内连环 ERR_SEQ 只消耗一次恢复预算（retries=1 仍成功，'
        'RC3-06）', () async {
      final package = packageBytes(4096);
      final mcu = _McuSim()..errSeqAtDataCounts = {3};
      final transport = OtaBleTransport(
        channel: mcu,
        retries: 1, // 预算只有一次：多扣一次即失败
        ackTimeout: const Duration(milliseconds: 200),
      );
      final ack = await transport.transfer(
        package: package,
        packageSha256: shaOf(package),
        etuHeader: etuHeaderOf(package),
      );
      expect(ack.isOk, isTrue, reason: '一次断档在 retries=1 下必须仍能续传');
      // 连环 ERR_SEQ 只触发一轮 ABORT+BEGIN：预算恰好用掉 1。
      expect(mcu.abortCalls, 1);
      expect(mcu.beginCalls, 2);
      final errSeqAcks = mcu.dataAckStatuses
          .where((s) => s == OtaBleCodec.statusErrSeq)
          .length;
      expect(errSeqAcks, greaterThan(1),
          reason: '前置：本用例必须真的产生多份 ERR_SEQ ACK，否则不具鉴别力');
    }, timeout: const Timeout(Duration(seconds: 60)));

    // RC3-06：恢复预算有限。第二次断档落在 resume 轮（首发 32 帧后第 3
    // 帧 = 全局第 35 帧），此时 resumeLeft 已为 0：必须以 ACK_STATUS 终止，
    // 不得无限 ABORT+BEGIN 打转。
    test('恢复预算耗尽后不再重新 BEGIN：第二次 ERR_SEQ 抛 ACK_STATUS'
        '（RC3-06）', () async {
      final package = packageBytes(4096);
      // 3 = 首轮第 3 帧；35 = resume 轮（第 33 帧起）的第 3 帧。
      final mcu = _McuSim()..errSeqAtDataCounts = {3, 35};
      final transport = OtaBleTransport(
        channel: mcu,
        retries: 1,
        ackTimeout: const Duration(milliseconds: 200),
      );
      try {
        await transport.transfer(
          package: package,
          packageSha256: shaOf(package),
          etuHeader: etuHeaderOf(package),
        );
        fail('恢复预算耗尽后必须终止，不得继续 resume');
      } on OtaTransportException catch (e) {
        expect(e.code, 'ACK_STATUS');
        expect(e.status, OtaBleCodec.statusErrSeq);
        expect(e.message, contains('可恢复错误重试次数超限'));
      }
      // 只发生过一轮恢复：第二次断档直接终止，没有第三次 BEGIN。
      expect(mcu.abortCalls, 1);
      expect(mcu.beginCalls, 2);
      expect(mcu.errSeqAtDataCounts, isEmpty,
          reason: '前置：两次注入都必须真的命中，否则用例没走到目标分支');
    }, timeout: const Timeout(Duration(seconds: 60)));

    for (final status in [
      OtaBleCodec.statusErrCrc,
      OtaBleCodec.statusErrFrame,
    ]) {
      test('BEGIN frame error $status retries the identical frame', () async {
        final package = packageBytes(4096);
        final mcu = _McuSim()..beginFailures = [status];
        final transport = OtaBleTransport(channel: mcu, retries: 2);
        final durable = <int>[];
        final ack = await transport.transfer(
          package: package,
          packageSha256: shaOf(package),
          etuHeader: etuHeaderOf(package),
          onDurableProgress: (off, _) => durable.add(off),
        );
        expect(ack.isOk, isTrue);
        expect(mcu.beginCalls, 2);
        final begins = mcu.writtenFrames
            .where((frame) => frame[2] == OtaBleCodec.cmdBegin)
            .toList();
        expect(begins, hasLength(2));
        expect(begins[1], orderedEquals(begins[0]));
        expect(mcu.dataFrames, hasLength(32));
        expect(mcu.dataFrames.first.seq, mcu.beginFrames.last.seq + 1);
        expect(mcu.abortCalls, 0);
        expect(durable, [0, 4096]);
        await transport.dispose();
      });

      test('BEGIN frame error $status stops at the retry limit', () async {
        final package = packageBytes(4096);
        final mcu = _McuSim()..beginFailures = [status, status, status];
        final transport = OtaBleTransport(channel: mcu, retries: 2);
        await expectLater(
          transport.transfer(
            package: package,
            packageSha256: shaOf(package),
            etuHeader: etuHeaderOf(package),
          ),
          throwsA(isA<OtaTransportException>()
              .having((error) => error.code, 'code', 'ACK_STATUS')
              .having((error) => error.status, 'status', status)),
        );
        expect(mcu.beginCalls, 3);
        expect(mcu.beginFrames.map((frame) => frame.seq).toSet(), hasLength(1));
        expect(mcu.dataFrames, isEmpty);
        expect(mcu.stagedDurable, 0);
        await transport.dispose();
      });
    }

    test('BEGIN errors and timeouts share one retry allowance', () async {
      final package = packageBytes(4096);
      final mcu = _McuSim()
        ..beginFailures = [
          OtaBleCodec.statusErrCrc,
          null,
          OtaBleCodec.statusErrFrame,
        ];
      final transport = OtaBleTransport(
        channel: mcu,
        retries: 2,
        ackTimeout: const Duration(milliseconds: 30),
      );
      await expectLater(
        transport.transfer(
          package: package,
          packageSha256: shaOf(package),
          etuHeader: etuHeaderOf(package),
        ),
        throwsA(isA<OtaTransportException>()
            .having((error) => error.code, 'code', 'ACK_STATUS')
            .having((error) => error.status, 'status', OtaBleCodec.statusErrFrame)),
      );
      expect(mcu.beginCalls, 3);
      expect(mcu.beginFrames.map((frame) => frame.seq).toSet(), hasLength(1));
      expect(mcu.dataFrames, isEmpty);
      await transport.dispose();
    });

    test('BEGIN frame errors never reset the no-progress deadline', () async {
      final package = packageBytes(4096);
      final mcu = _McuSim()
        ..beginFailures = List<int?>.filled(20, OtaBleCodec.statusErrCrc)
        ..beginFailureDelay = const Duration(milliseconds: 40);
      final transport = OtaBleTransport(
        channel: mcu,
        retries: 100,
        ackTimeout: const Duration(seconds: 1),
        noProgressTimeout: const Duration(milliseconds: 150),
      );
      await expectLater(
        transport.transfer(
          package: package,
          packageSha256: shaOf(package),
          etuHeader: etuHeaderOf(package),
        ),
        throwsA(isA<OtaTransportException>()
            .having((error) => error.code, 'code', 'NO_DURABLE_PROGRESS')),
      );
      expect(mcu.beginCalls, lessThan(20));
      expect(mcu.dataFrames, isEmpty);
      await transport.dispose();
    });

    for (final fields in [(9, 0, 0), (10, 7, 0), (10, 0, 7), (10, 7, 7)]) {
      test('malformed failed BEGIN ACK $fields is never retried', () async {
        final package = packageBytes(4096);
        final mcu = _McuSim()
          ..beginFailures = [OtaBleCodec.statusErrCrc]
          ..beginFailurePayloadLength = fields.$1
          ..beginFailureHeaderSession = fields.$2
          ..beginFailurePayloadSession = fields.$3;
        final transport = OtaBleTransport(channel: mcu, retries: 2);
        await expectLater(
          transport.transfer(
            package: package,
            packageSha256: shaOf(package),
            etuHeader: etuHeaderOf(package),
          ),
          throwsA(isA<OtaTransportException>()
              .having((error) => error.code, 'code', 'ACK_MALFORMED')),
        );
        expect(mcu.beginCalls, 1);
        expect(mcu.dataFrames, isEmpty);
        await transport.dispose();
      });
    }

    test('BEGIN ACK 丢失：重试复用同一 seq，MCU 幂等回进度（expected_seq '
        '未重置）后传输成功', () async {
      final package = packageBytes(4096);
      final mcu = _McuSim()..dropBeginAckOnce = true;
      final transport = OtaBleTransport(
        channel: mcu,
        ackTimeout: const Duration(milliseconds: 50),
      );
      final ack = await transport.transfer(
        package: package,
        packageSha256: shaOf(package),
        etuHeader: etuHeaderOf(package),
      );
      expect(ack.isOk, isTrue);
      // 两次 BEGIN（ACK 丢失 + 重试），seq 完全相同（RC2-05 复用规则）。
      expect(mcu.beginCalls, 2);
      expect(mcu.beginFrames.length, 2);
      expect(mcu.beginFrames[0].seq, mcu.beginFrames[1].seq);
      // 幂等分支未重置 expected_seq：DATA 全部顺序通过，无 ERR_SEQ 重发。
      expect(
        mcu.writtenFrames.where((f) => f[2] == OtaBleCodec.cmdData).length,
        32,
      );
    }, timeout: const Timeout(Duration(seconds: 60)));

    test('丢部分 DATA ACK：MCU 位图权威置位，窗口按位图回收不重发（RC2-05）',
        () async {
      final package = packageBytes(4096);
      final mcu = _McuSim()..dropAckForOffsets = {0, 128}; // 段 0/1 的 ACK 丢
      final transport = OtaBleTransport(channel: mcu);
      final ack = await transport.transfer(
        package: package,
        packageSha256: shaOf(package),
        etuHeader: etuHeaderOf(package),
        windowSegments: 4,
      );
      expect(ack.isOk, isTrue);
      // 32 段全部送达且零重发：丢 ACK 的段由位图确认回收窗口。
      final dataFrames =
          mcu.writtenFrames.where((f) => f[2] == OtaBleCodec.cmdData).length;
      expect(dataFrames, 32);
      expect(mcu.dataOffsets.toSet().length, 32);
    }, timeout: const Timeout(Duration(seconds: 60)));

    test('未知 seq 的 ACK_DATA 到达：整帧忽略，不覆盖权威进度（RC2-06）',
        () async {
      final package = packageBytes(4096);
      final mcu = _McuSim()..strayAckAfterDataCount = 1;
      final transport = OtaBleTransport(channel: mcu);
      final ack = await transport.transfer(
        package: package,
        packageSha256: shaOf(package),
        etuHeader: etuHeaderOf(package),
      );
      expect(ack.isOk, isTrue);
      expect(mcu.dataOffsets.length, 32);
    });

    test('durable 倒退的 ACK：fail closed 抛 ACK_MALFORMED（RC2-06）',
        () async {
      final package = packageBytes(8192); // 2 块：块 0 提交后 durable=4096
      final mcu = _McuSim()..durableRegressAtDataCount = 33; // 块 1 段 0
      final transport = OtaBleTransport(channel: mcu);
      try {
        await transport.transfer(
          package: package,
          packageSha256: shaOf(package),
          etuHeader: etuHeaderOf(package),
        );
        fail('应 fail closed');
      } on OtaTransportException catch (e) {
        expect(e.code, 'ACK_MALFORMED');
      }
    }, timeout: const Timeout(Duration(seconds: 60)));

    test('abortBestEffort 连接正常：MCU 回 ACK ABORTED 并 teardown，'
        '此后无 DATA/END 帧', () async {
      final package = packageBytes(4096);
      final mcu = _McuSim();
      final transport = OtaBleTransport(channel: mcu);
      // 先建立会话（BEGIN），再走取消路径的尽力 ABORT。
      await transport.begin(
        totalLen: package.length,
        packageSha256: shaOf(package),
        etuHeader: etuHeaderOf(package),
      );
      await transport.abortBestEffort();
      expect(mcu.abortCalls, 1);
      // MCU 真值：session 匹配 → ACK ABORTED + teardown（staging 保留）。
      final abortAck = mcu.sentFrames
          .where((f) => f.cmd == OtaBleCodec.rspAckAbort)
          .single;
      expect(abortAck.payload[0], OtaBleCodec.statusAborted);
      // 取消旁路写通路（RC2-03）：ABORT 帧确实发出且未被自身拦截，
      // session 与 BEGIN ACK 分配的会话匹配。
      expect(mcu.abortFrames.single.session, 1);
      // 取消后不再有任何帧写入。
      final framesAfterAbort = mcu.writtenFrames.length;
      await Future<void>.delayed(const Duration(milliseconds: 50));
      expect(mcu.writtenFrames.length, framesAfterAbort);
      // teardown 后 MCU 对后续 DATA 回 ERR_STATE（session=0 NAK）。
      final dataFrame = OtaBleCodec.encodeCommand(
        cmd: OtaBleCodec.cmdData,
        session: 1,
        seq: 999,
        payload: OtaBleCodec.encodeDataPayload(
            0, package.sublist(0, OtaBleCodec.dataSegmentSize)),
      );
      await mcu.writeChunk(dataFrame);
      final nak = mcu.sentFrames.last;
      expect(nak.cmd, OtaBleCodec.rspAckData);
      expect(nak.payload[0], OtaBleCodec.statusErrState);
    });

    test('MCU 真值自检：同包重复 BEGIN 不重置 expected_seq', () async {
      // 直接对 fake 发帧（不经 transport），锁定 ota_ble_session.c:377
      // 语义：ACTIVE 同 sha 的重复 BEGIN 幂等回进度、不重置 expected_seq。
      // 若 fake 退化成重置，依赖它的 resume 用例将失去鉴别力。
      final package = packageBytes(4096);
      final mcu = _McuSim();
      Uint8List beginFrame(int seq) => OtaBleCodec.encodeCommand(
            cmd: OtaBleCodec.cmdBegin,
            session: 0,
            seq: seq,
            payload: OtaBleCodec.encodeBeginPayload(
              totalLen: package.length,
              packageSha256: shaOf(package),
              etuHeader: etuHeaderOf(package),
            ),
          );
      await mcu.writeChunk(beginFrame(10)); // 新会话：expected_seq = 11
      final beginAck = mcu.sentFrames.single;
      final session = beginAck.payload[1];
      Uint8List dataFrame(int seq, int off) => OtaBleCodec.encodeCommand(
            cmd: OtaBleCodec.cmdData,
            session: session,
            seq: seq,
            payload: OtaBleCodec.encodeDataPayload(
                off, package.sublist(off, off + OtaBleCodec.dataSegmentSize)),
          );
      await mcu.writeChunk(dataFrame(11, 0)); // 推进 expected_seq = 12
      await mcu.writeChunk(beginFrame(10)); // 重复 BEGIN 同 seq：幂等
      await mcu.writeChunk(dataFrame(12, 128)); // 必须仍顺序通过
      final lastAck = mcu.sentFrames.last;
      expect(lastAck.cmd, OtaBleCodec.rspAckData);
      expect(lastAck.payload[0], OtaBleCodec.statusOk);
      // 重复 BEGIN 的 ACK 幂等回当前进度（不重置）。
      expect(mcu.beginCalls, 2);
    });
  });

  group('RC3 忠实模型与 fail closed 回归', () {
    test('块尾段 ACK 丢失：重发触发幂等 ACK 携带 durable 前移，'
        '跨块回收在途窗口（RC3-06）', () async {
      final package = packageBytes(8192); // 2 块
      final mcu = _McuSim()..dropAckOnceForOffsets = {31 * 128}; // 块 0 尾段
      final transport = OtaBleTransport(channel: mcu);
      final ack = await transport.transfer(
        package: package,
        packageSha256: shaOf(package),
        etuHeader: etuHeaderOf(package),
      );
      expect(ack.isOk, isTrue);
      // 首发 64 段 + 块 0 尾段一次重发（其首发 ACK 丢失）；无其他重发。
      expect(
        mcu.writtenFrames.where((f) => f[2] == OtaBleCodec.cmdData).length,
        65,
      );
      expect(mcu.dataOffsets.toSet().length, 64);
      // 重发段 31 的幂等 ACK 报 durable=4096（块 0 已提交），transport
      // 据此前移 durable 并清空旧块在途记录——块 1 段号与块 0 重叠
      // （各 0..31），不回收则块 1 的段会被旧块残留误判在途。
      expect(ack.durableOff, 8192);
    }, timeout: const Timeout(Duration(seconds: 60)));

    test('BEGIN ACK durable 伪跳跃（> total）：fail closed 抛 ACK_MALFORMED'
        '（RC3-06）', () async {
      final package = packageBytes(4096);
      final mcu = _McuSim()..beginAckDurableOverride = 8192; // 越出包长
      final transport = OtaBleTransport(channel: mcu);
      try {
        await transport.transfer(
          package: package,
          packageSha256: shaOf(package),
          etuHeader: etuHeaderOf(package),
        );
        fail('应 fail closed');
      } on OtaTransportException catch (e) {
        expect(e.code, 'ACK_MALFORMED');
      }
    });

    test('BEGIN ACK bitmap 越出所属块有效位：fail closed 抛 ACK_MALFORMED'
        '（RC3-06）', () async {
      // 2560B 包 = 20 段：validMask = (1<<20)-1，注入 24 位 bitmap 越界。
      final package = packageBytes(2560);
      final mcu = _McuSim()..beginAckBitmapOverride = 0xFFFFFF;
      final transport = OtaBleTransport(channel: mcu);
      try {
        await transport.transfer(
          package: package,
          packageSha256: shaOf(package),
          etuHeader: etuHeaderOf(package),
        );
        fail('应 fail closed');
      } on OtaTransportException catch (e) {
        expect(e.code, 'ACK_MALFORMED');
      }
    });

    test('END ACK 报 OK 但 durable != total：fail closed 抛 ACK_MALFORMED'
        '（RC3-06）', () async {
      final package = packageBytes(4096);
      final mcu = _McuSim()..endAckDurableLie = 2048;
      final transport = OtaBleTransport(channel: mcu);
      try {
        await transport.transfer(
          package: package,
          packageSha256: shaOf(package),
          etuHeader: etuHeaderOf(package),
        );
        fail('应 fail closed');
      } on OtaTransportException catch (e) {
        expect(e.code, 'ACK_MALFORMED');
      }
      expect(mcu.endCalls, 1);
    }, timeout: const Timeout(Duration(seconds: 60)));

    test('MCU 会话超时主动 teardown：异步 rspAckAbort ABORTED → terminal'
        '（RC3-06）', () async {
      final package = packageBytes(4096);
      final mcu = _McuSim()..sessionAbortAfterDataCount = 5;
      final transport = OtaBleTransport(channel: mcu);
      final ack = await transport.transfer(
        package: package,
        packageSha256: shaOf(package),
        etuHeader: etuHeaderOf(package),
      );
      expect(ack.isOk, isFalse);
      expect(ack.terminal, isTrue);
      expect(ack.status, OtaBleCodec.statusAborted);
      // 会话已被 MCU teardown，transport 不再重试（无第二次 BEGIN）。
      expect(mcu.beginCalls, 1);
    });

    test('BEGIN ACK 全丢：无 durable 进展预算优先于重试空转（RC3-07）',
        () async {
      final package = packageBytes(4096);
      final mcu = _McuSim()..dropAllBeginAcks = true;
      final transport = OtaBleTransport(
        channel: mcu,
        ackTimeout: const Duration(milliseconds: 200),
        noProgressTimeout: const Duration(milliseconds: 300),
      );
      try {
        await transport.transfer(
          package: package,
          packageSha256: shaOf(package),
          etuHeader: etuHeaderOf(package),
        );
        fail('应中止');
      } on OtaTransportException catch (e) {
        // 预算（300ms）跨 BEGIN 重试保留：第一次 200ms 超时后剩余
        // 100ms 封顶第二次等待，耗尽即 NO_DURABLE_PROGRESS，而非跑满
        // 全部 BEGIN 重试轮次。
        expect(e.code, 'NO_DURABLE_PROGRESS');
      }
      // 断言意图是「预算优先于跑满重试（默认 5 次）」，不是精确 2 次：
      // 200ms+100ms 恰好压在 300ms 预算边界上，BEGIN#2 的超时唤醒与
      // 预算时钟读数之间存在调度间隙（CI 负载下毫秒级），间隙大于
      // 写帧耗耗时第 3 次 BEGIN 会在耗尽前一刻被放行、随后立即
      // NO_DURABLE_PROGRESS 终止（Ubuntu/Windows 实测 2 或 3 皆合法）。
      expect(mcu.beginCalls, lessThanOrEqualTo(3));
      expect(mcu.beginCalls, lessThan(5));
    }, timeout: const Timeout(Duration(seconds: 60)));

    test('MTU=23 下取消：在途 DATA 写完后 ABORT 从帧边界发出，无半帧残留'
        '（RC3-05⑤）', () async {
      final package = packageBytes(4096);
      final mcu = _McuSim()
        ..mtu = 23
        ..respondDataAck = false;
      final transport = OtaBleTransport(
        channel: mcu,
        ackTimeout: const Duration(milliseconds: 400),
        retries: 5,
      );
      final future = transport.transfer(
        package: package,
        packageSha256: shaOf(package),
        etuHeader: etuHeaderOf(package),
      );
      await Future<void>.delayed(const Duration(milliseconds: 100));
      // 真实取消路径（RC3-05⑤）：transfer 仍在途（DATA 窗口已写、ACK
      // 等待中）时即调 abortBestEffort——ABORT 与在途分片写交错，靠
      // 写串行化（_writeSerial）排在当前帧之后从帧边界发出。等
      // transfer 先退出再 ABORT 测不到这条交错路径。
      //
      // await 顺序（Dart uncaught 语义）：cancel()→fail→completeError 的
      // 错误级联在 abortBestEffort 首个 await 让出后的微任务中把 transfer
      // future 变成 error 完成；此刻它若无 listener，zone 会立即上报
      // uncaught async error，从 abortBestEffort 的 await 点压垮测试。
      // 必须先同步发起 abort（cancel 立即生效），紧接着 await future
      // 注册 listener，ABORT 写完成的收尾放错误断言之后。
      final abortFuture = transport.abortBestEffort();
      try {
        await future;
        fail('应抛 CANCELLED');
      } on OtaTransportException catch (e) {
        expect(e.code, 'CANCELLED');
      }
      await abortFuture;
      // 取消路径的尽力 ABORT：完整帧写出，MCU 重组缓冲无半帧残留
      // （若 ABORT 被吞成半帧 payload，abortFrames 将为空且 pending 非零）。
      expect(mcu.abortFrames, hasLength(1));
      expect(mcu.abortFrames.single.session, 1);
      expect(mcu.pendingByteCount, 0);
      expect(mcu.writtenFrames.last[2], OtaBleCodec.cmdAbort);
    }, timeout: const Timeout(Duration(seconds: 60)));

    test('快速重连 MCU 仍 ACTIVE：低 seq BEGIN 幂等不重置 expected_seq，'
        '落后 DATA 幂等 ACK 不带写入确认 → ERR_STATE 立即 resume 重对齐'
        '（RC3-08）', () async {
      final package = packageBytes(4096);
      final mcu = _McuSim();
      // 手工构造"掉线时 MCU 未 teardown"的 ACTIVE 态：BEGIN(seq=10) +
      // 段 0..4（seq=11..15），expected_seq 停在 16、RAM bitmap=0b11111。
      Uint8List beginFrame(int seq) => OtaBleCodec.encodeCommand(
            cmd: OtaBleCodec.cmdBegin,
            session: 0,
            seq: seq,
            payload: OtaBleCodec.encodeBeginPayload(
              totalLen: package.length,
              packageSha256: shaOf(package),
              etuHeader: etuHeaderOf(package),
            ),
          );
      await mcu.writeChunk(beginFrame(10));
      for (var i = 0; i < 5; i++) {
        await mcu.writeChunk(OtaBleCodec.encodeCommand(
          cmd: OtaBleCodec.cmdData,
          session: 1,
          seq: 11 + i,
          payload: OtaBleCodec.encodeDataPayload(i * 128,
              package.sublist(i * 128, i * 128 + OtaBleCodec.dataSegmentSize)),
        ));
      }
      // 新 transport（seq 从 0）：BEGIN 撞 ACTIVE 幂等分支，回 RAM 保留
      // 进度且不重置 expected_seq（真值 :377-386）。
      final transport = OtaBleTransport(
        channel: mcu,
        ackTimeout: const Duration(milliseconds: 100),
      );
      final ack = await transport.transfer(
        package: package,
        packageSha256: shaOf(package),
        etuHeader: etuHeaderOf(package),
      );
      expect(ack.isOk, isTrue);
      // 手工 BEGIN + 幂等 BEGIN + resume BEGIN；resume 前 ABORT 一次。
      expect(mcu.beginCalls, 3);
      expect(mcu.abortCalls, 1);
      // 幂等 BEGIN ACK 回 RAM 保留进度（ACTIVE 未 teardown，真值语义）。
      expect(mcu.beginAckStates[1], [0, 0x1F]);
      // ABORT teardown 清 RAM 后 resume 从整块开始（真值 memset receiver）；
      // END OK 依赖内容级流式摘要（fake 真值 oracle）：重发段全喂 +
      // 空前缀 == 整包 SHA（RC3-03）。
      expect(mcu.beginAckStates[2], [0, 0]);
      expect(mcu.dataOffsets.toSet().length, 32);
    }, timeout: const Timeout(Duration(seconds: 60)));

    test('慢 ACK（单片接近 ackTimeout）不误杀：整包正常完成（RC3-07）',
        () async {
      final package = packageBytes(4096);
      final mcu = _McuSim()
        ..ackDelay = const Duration(milliseconds: 80);
      final transport = OtaBleTransport(
        channel: mcu,
        ackTimeout: const Duration(milliseconds: 200),
      );
      final ack = await transport.transfer(
        package: package,
        packageSha256: shaOf(package),
        etuHeader: etuHeaderOf(package),
        windowSegments: 4,
      );
      expect(ack.isOk, isTrue);
      expect(ack.durableOff, 4096);
      expect(mcu.dataOffsets.length, 32);
    }, timeout: const Timeout(Duration(seconds: 60)));

    test('DATA ACK durable 跨块伪跳跃：8192B 包首块在途 ACK 报 durable=8192'
        ' → fail closed ACK_MALFORMED（RC3-06）', () async {
      final package = packageBytes(8192); // 2 块
      // 注入：第一个 DATA ACK durable 直接谎报到 8192（两块跨度），bitmap=0。
      // 该 ACK 可清 inFlight/位图回收窗口——若 transport 只做范围/对齐/
      // 单调校验，会误信跳跃、跳过第二块直接发 END。
      final mcu = _McuSim()..dataAckDurableJump = 8192;
      final transport = OtaBleTransport(channel: mcu);
      try {
        await transport.transfer(
          package: package,
          packageSha256: shaOf(package),
          etuHeader: etuHeaderOf(package),
        );
        fail('应 fail closed');
      } on OtaTransportException catch (e) {
        expect(e.code, 'ACK_MALFORMED');
      }
      // 跳跃 ACK 被拒后不得发 END（未传完即终止）。
      expect(mcu.endCalls, 0);
    }, timeout: const Timeout(Duration(seconds: 60)));

    test('合法 durable 前移（一个块跨度）不被误杀：块尾 ACK 携带提交'
        '（RC3-06 反例）', () async {
      final package = packageBytes(8192);
      final mcu = _McuSim();
      final transport = OtaBleTransport(channel: mcu);
      final ack = await transport.transfer(
        package: package,
        packageSha256: shaOf(package),
        etuHeader: etuHeaderOf(package),
      );
      // 块 0 提交时段 31 的 ACK durable 0→4096（正好一个块）、块 1 提交
      // 4096→8192：都是相邻 ACK 的合法前移，不得被伪跳跃校验误伤。
      expect(ack.isOk, isTrue);
      expect(ack.durableOff, 8192);
    });

    test('块尾提交不得掩盖在途畸形 ACK：块结束消费锁存错误，不进 END'
        '（RC3-06⑤）', () async {
      final package = packageBytes(4096); // 单块：默认发窗 32 段一次全在途
      // 注入：首段 ACK durable 谎报 8192 > total=4096 → transport 判
      // 畸形并锁存（不更新权威进度）。fake 照常收段、照常 ACK 后续段：
      // 段 31 的 ACK 携带整块提交（durable 0→4096）。时序上畸形 ACK
      // 在发窗内到达锁存、块尾提交把 durable 推到块尾，段循环经循环
      // 条件退出而不再经过段循环头的错误消费——修复前此处会带着未
      // 消费锁存错误直接进入 END：MCU 已全量 staged 仍回 END OK，
      // 畸形 ACK 被当成功收尾。
      final mcu = _McuSim()..dataAckDurableJump = 8192;
      final transport = OtaBleTransport(channel: mcu);
      try {
        await transport.transfer(
          package: package,
          packageSha256: shaOf(package),
          etuHeader: etuHeaderOf(package),
        );
        fail('应 fail closed');
      } on OtaTransportException catch (e) {
        expect(e.code, 'ACK_MALFORMED');
      }
      // 锁存错误在块结束被消费：END 不得发出（修复前会发 END 并拿到
      // OK，把在途畸形 ACK 洗白成成功收尾）。
      expect(mcu.endCalls, 0);
    }, timeout: const Timeout(Duration(seconds: 60)));

    test('BEGIN ACK 帧头 session 与 payload session 不一致：fail closed '
        'ACK_MALFORMED（RC3-06）', () async {
      final package = packageBytes(4096);
      final mcu = _McuSim()..beginAckSessionMismatch = true;
      final transport = OtaBleTransport(channel: mcu);
      try {
        await transport.transfer(
          package: package,
          packageSha256: shaOf(package),
          etuHeader: etuHeaderOf(package),
        );
        fail('应 fail closed');
      } on OtaTransportException catch (e) {
        expect(e.code, 'ACK_MALFORMED');
      }
    });

    test('END ACK OK 但 bitmap 越出尾块有效位：fail closed ACK_MALFORMED'
        '（RC3-06）', () async {
      // 2560B 包 = 20 段：尾块 validMask=(1<<20)-1；真值 END OK ACK 的
      // bitmap 是活跃块残留（非 0 合法），注入 24 位越界。
      final package = packageBytes(2560);
      final mcu = _McuSim()..endAckBitmapLie = 0xFFFFFF;
      final transport = OtaBleTransport(channel: mcu);
      try {
        await transport.transfer(
          package: package,
          packageSha256: shaOf(package),
          etuHeader: etuHeaderOf(package),
        );
        fail('应 fail closed');
      } on OtaTransportException catch (e) {
        expect(e.code, 'ACK_MALFORMED');
      }
      expect(mcu.endCalls, 1);
    });

    test('内容级流式摘要：复述一致但 BEGIN sha 与内容不符 → END ERR_SHA'
        '（RC3-03 oracle 鉴别力）', () async {
      final package = packageBytes(4096);
      // BEGIN 携带的 sha 改 1 字节：END 复述（同 sha）通过、durable==total
      // 通过，但内容级摘要 sha256(package) != BEGIN sha → ERR_SHA。
      // 修复前 fake 只校验复述与 durable，无法发现该类内容不一致。
      final lyingSha = List<int>.of(shaOf(package))..[0] ^= 0xFF;
      final mcu = _McuSim();
      final transport = OtaBleTransport(channel: mcu);
      final ack = await transport.transfer(
        package: package,
        packageSha256: lyingSha,
        etuHeader: etuHeaderOf(package),
      );
      expect(ack.isOk, isFalse);
      expect(ack.status, OtaBleCodec.statusErrSha);
      expect(mcu.endCalls, 1);
      // ERR_SHA 语义：整页擦除（真值 erase staging），durable 归零。
      expect(mcu.stagedDurable, 0);
    });

    test('ERR_DATA：同 offset 不同内容 → ABORTED + teardown，不喂摘要'
        '（RC3-03 fake 真值自检）', () async {
      // 直接对 fake 发帧（不经 transport），锁定真值 :571-585 语义：
      // 同 offset 重发但内容不同 → ABORTED + teardown（fail closed）。
      final package = packageBytes(4096);
      final mcu = _McuSim();
      await mcu.writeChunk(OtaBleCodec.encodeCommand(
        cmd: OtaBleCodec.cmdBegin,
        session: 0,
        seq: 10,
        payload: OtaBleCodec.encodeBeginPayload(
          totalLen: package.length,
          packageSha256: shaOf(package),
          etuHeader: etuHeaderOf(package),
        ),
      ));
      await mcu.writeChunk(OtaBleCodec.encodeCommand(
        cmd: OtaBleCodec.cmdData,
        session: 1,
        seq: 11,
        payload: OtaBleCodec.encodeDataPayload(
            0, package.sublist(0, OtaBleCodec.dataSegmentSize)),
      ));
      // 同 offset 不同内容（篡改 1 字节）。
      final mutated = Uint8List.fromList(
          package.sublist(0, OtaBleCodec.dataSegmentSize));
      mutated[5] ^= 0xFF;
      await mcu.writeChunk(OtaBleCodec.encodeCommand(
        cmd: OtaBleCodec.cmdData,
        session: 1,
        seq: 12,
        payload: OtaBleCodec.encodeDataPayload(0, mutated),
      ));
      final nak = mcu.sentFrames.last;
      expect(nak.cmd, OtaBleCodec.rspAckData);
      expect(nak.payload[0], OtaBleCodec.statusAborted);
      // teardown 后续 DATA：ERR_STATE（session=0 NAK）。
      await mcu.writeChunk(OtaBleCodec.encodeCommand(
        cmd: OtaBleCodec.cmdData,
        session: 1,
        seq: 13,
        payload: OtaBleCodec.encodeDataPayload(
            128, package.sublist(128, 128 + OtaBleCodec.dataSegmentSize)),
      ));
      expect(mcu.sentFrames.last.payload[0], OtaBleCodec.statusErrState);
    });

    test('慢写 + 小 MTU：单片不超写超时、累计超预算在片间被 cap 拦截'
        '（RC3-07⑤）', () async {
      final package = packageBytes(4096);
      // MTU=23（20B/片）：142B DATA 帧 = 8 片（7×20B + 尾片 2B）；每片
      // 写延迟 80ms 且仅 DATA 帧分片延迟（BEGIN 111B 的 6 片不吃预算）。
      // 片 1-6 累计 480ms 后，片 7 开始时剩余预算 40ms：片间边界检查
      // 不触发（480 < 520），但逐片 cap 把片 7 的写超时压到 40ms <
      // 80ms 写延迟 → WRITE_TIMEOUT 先于片 7 落地。这正是「同一 DATA
      // 帧各片均未单独超 10s 写超时、累计超过总预算」的反例：修复前
      // 每片各按 10s 上限跑满，整帧 8 片全部落地（640ms）后才在帧外
      // 撞上预算。
      // 预算取 520ms 而非整 500ms：片 7 边界检查（480ms）与 cap 触发
      // （40ms < 80ms）两侧各留 40ms 计时余量，避免定时器抖动把期望码
      // 滑成边界检查的 NO_DURABLE_PROGRESS。
      final mcu = _McuSim()
        ..mtu = 23
        ..writeChunkDelay = const Duration(milliseconds: 80)
        ..respondDataAck = false;
      final transport = OtaBleTransport(
        channel: mcu,
        noProgressTimeout: const Duration(milliseconds: 520),
        retries: 999, // 压制重发超限，让预算先触发
      );
      try {
        await transport.transfer(
          package: package,
          packageSha256: shaOf(package),
          etuHeader: etuHeaderOf(package),
        );
        fail('应中止');
      } on OtaTransportException catch (e) {
        // 片 7 cap=剩余预算 40ms < 80ms 写延迟：WRITE_TIMEOUT，而非
        // 片间边界检查的 NO_DURABLE_PROGRESS（片 7 开始时预算未归零）。
        expect(e.code, 'WRITE_TIMEOUT');
      }
      // 首个 DATA 帧截断在片 7：无完整 DATA 帧落地。修复前整帧 8 片
      // 全部写完（此计数为 1）后才被预算拦截，无法证明片间拦截。
      expect(
        mcu.writtenFrames.where((f) => f[2] == OtaBleCodec.cmdData).length,
        0,
      );
      // 截断证据：片 7 于 480ms 发起、560ms 落地，而预算 520ms 到期时
      // settle 宽限已被剩余预算封顶为 0——抛出时刻片 7 可能尚未落地。
      // 两种取值都仍是同一 DATA 帧的前缀（120B 或 140B）。
      expect(mcu.pendingByteCount, anyOf(120, 140));
      // 等片 7 迟到落地后：_pending 恰为 140B 半帧前缀，无尾片 2B、无后续
      // 帧字节混入（迟到物理写未被取消，只是不再阻塞终止发布）。
      await Future<void>.delayed(const Duration(milliseconds: 150));
      expect(mcu.pendingByteCount, 140);
    }, timeout: const Timeout(Duration(seconds: 60)));

    test('接近预算耗尽的写挂起：终止发布不得超出 durable 预算（RC3-07⑤）',
        () async {
      final package = packageBytes(4096);
      // MTU=23（20B/片）：DATA 帧 8 片，前 3 片各 300ms 慢写吃掉 900ms 预算，
      // 片 4 起写通道卡死（永不返回）。预算 1500ms、单次写超时 5s：片 4 的
      // cap = 剩余 ~600ms < 写挂起，超时在预算截止处触发（片 4 起点的预算
      // 检查仍在预算内，不会先抛 NO_DURABLE_PROGRESS）。
      // 修复前：超时处理器再等 2×writeTimeout = 10s（片 4 永不返回 → 等满），
      // 终止发布落在 ~11.5s；本批把 settle 宽限交给剩余预算封顶 → 宽限 = 0，
      // 抛出即预算截止。判据因此是「墙钟时间」而非错误码（两者相同）。
      final mcu = _McuSim()
        ..mtu = 23
        ..writeChunkDelay = const Duration(milliseconds: 300)
        ..hangAtDataChunk = 4
        ..respondDataAck = false;
      final transport = OtaBleTransport(
        channel: mcu,
        noProgressTimeout: const Duration(milliseconds: 1500),
        writeTimeout: const Duration(seconds: 5),
        retries: 999, // 压制重发超限，让预算先触发
      );
      final sw = Stopwatch()..start();
      try {
        await transport.transfer(
          package: package,
          packageSha256: shaOf(package),
          etuHeader: etuHeaderOf(package),
        );
        fail('应中止');
      } on OtaTransportException catch (e) {
        expect(e.code, 'WRITE_TIMEOUT');
      } finally {
        sw.stop();
      }
      expect(sw.elapsedMilliseconds, greaterThanOrEqualTo(1000),
          reason: '预算本身必须真的走完（片 1-3 各 300ms）');
      expect(sw.elapsedMilliseconds, lessThan(3000),
          reason: '终止发布不得超出 1500ms 预算：旧实现要再等 2×writeTimeout=10s');
      // 半帧已废弃：后续业务帧被拒（写通道不可信）。
      await _expectBusinessWriteRefused(transport, '预算耗尽写挂起后');
      await transport.dispose();
    }, timeout: const Timeout(Duration(seconds: 60)));

    test('写超时后迟到成功：仍抛 WRITE_TIMEOUT，终止发布等到迟到写落地'
        '（RC3-07⑤）', () async {
      final package = packageBytes(4096);
      // MTU=125（122B/片）：DATA 帧 142B = 片 1（122B）+ 片 2（20B）。
      // 片 1 写 200ms 才落地，而写超时 100ms：超时触发时物理写仍在途，
      // 预算未耗尽（默认 30s）→ settle 宽限 200ms 内迟到成功落地
      // （窗口 [100ms, 300ms] 两侧各留 100ms 余量）。
      final mcu = _McuSim()
        ..mtu = 125
        ..slowDataChunkAt = 1
        ..slowDataChunkDelay = const Duration(milliseconds: 200);
      final transport = OtaBleTransport(
        channel: mcu,
        writeTimeout: const Duration(milliseconds: 100),
      );
      try {
        await transport.transfer(
          package: package,
          packageSha256: shaOf(package),
          etuHeader: etuHeaderOf(package),
        );
        fail('应中止');
      } on OtaTransportException catch (e) {
        // 迟到成功不得把已截断的帧「救回」：处置仍是 WRITE_TIMEOUT。
        expect(e.code, 'WRITE_TIMEOUT');
        // settle 等到了迟到落地：抛出时刻这 122B 已在 MCU 侧。若实现直接
        // 上抛（不等 settle），串行队列会在物理写完成前放行下一帧。
        expect(mcu.pendingByteCount, 122,
            reason: '终止发布必须等迟到物理写 settle，否则队列提前放行下一帧');
      }
      // 片 2 从未发起（帧已废弃）；悬空半帧无后续字节混入。
      expect(mcu.writeTimeline, ['start#1', 'done#1']);
      expect(
        mcu.writtenFrames.where((f) => f[2] == OtaBleCodec.cmdData),
        isEmpty,
      );
      await _expectBusinessWriteRefused(transport, '迟到成功写超时后');
      await transport.dispose();
    }, timeout: const Timeout(Duration(seconds: 60)));

    test('写超时后迟到错误：迟到错误不覆盖本帧 WRITE_TIMEOUT 语义（RC3-07⑤）',
        () async {
      final package = packageBytes(4096);
      // 与迟到成功用例同参数：写超时 100ms，片 1 在 200ms 以底层异常收场，
      // 落在 settle 宽限窗口 [100ms, 300ms] 内。
      final mcu = _McuSim()
        ..mtu = 125
        ..slowDataChunkAt = 1
        ..slowDataChunkDelay = const Duration(milliseconds: 200)
        ..slowDataChunkFails = true;
      final transport = OtaBleTransport(
        channel: mcu,
        writeTimeout: const Duration(milliseconds: 100),
      );
      try {
        await transport.transfer(
          package: package,
          packageSha256: shaOf(package),
          etuHeader: etuHeaderOf(package),
        );
        fail('应中止');
      } on OtaTransportException catch (e) {
        // 迟到错误必须被 settle 吞掉：调用方看到的是本帧的写超时，
        // 而不是一条与帧边界无关的底层异常。
        expect(e.code, 'WRITE_TIMEOUT');
      } on StateError {
        fail('迟到底层错误不得穿透到调用方');
      }
      expect(mcu.writeTimeline, ['start#1', 'error#1']);
      expect(mcu.pendingByteCount, 0, reason: '迟到错误无字节落地');
      await _expectBusinessWriteRefused(transport, '迟到错误写超时后');
      await transport.dispose();
    }, timeout: const Timeout(Duration(seconds: 60)));

    test('预算耗尽前取消交错：settle 宽限被预算截断，提前放行的 ABORT 不得'
        '与迟到半帧交错（RC3-07⑤）', () async {
      final package = packageBytes(4096);
      // 预算 600ms、写超时 500ms、MTU=125：DATA 片 1（122B）写 1.5s 才落地。
      // 片 1 在 500ms 超时；修复前的 settle 宽限 2×500ms=1000ms 会把终止
      // 发布推迟到 1500ms（迟到写落地处，超出 600ms 预算），封顶后只剩
      // 剩余预算 100ms，终止发布落在预算截止（600ms）。
      final mcu = _McuSim()
        ..mtu = 125
        ..slowDataChunkAt = 1
        ..slowDataChunkDelay = const Duration(milliseconds: 1500);
      final transport = OtaBleTransport(
        channel: mcu,
        noProgressTimeout: const Duration(milliseconds: 600),
        writeTimeout: const Duration(milliseconds: 500),
      );
      final sw = Stopwatch()..start();
      final future = transport.transfer(
        package: package,
        packageSha256: shaOf(package),
        etuHeader: etuHeaderOf(package),
      );
      // 取消发生在「片 1 在途、DATA 尚未超时」：ABORT 入队排在 DATA 写之后。
      await Future<void>.delayed(const Duration(milliseconds: 50));
      final abortFuture = transport.abortBestEffort();
      try {
        await future;
        fail('应中止');
      } on OtaTransportException catch (e) {
        expect(e.code, anyOf('WRITE_TIMEOUT', 'CANCELLED'));
      }
      await abortFuture;
      sw.stop();
      expect(sw.elapsedMilliseconds, lessThan(1000),
          reason: 'settle 宽限被剩余预算截断：不得等到 1.5s 的迟到物理写');
      // 宽限归零 → 串行队列立即放行 ABORT；启动时的废弃复核必须拦住它，
      // 否则一个字节就混进悬空半帧（真值：MCU 按 len 吞全部字节）。
      expect(mcu.abortFrames, isEmpty);
      expect(mcu.pendingByteCount, 0);
      // 迟到片 1 落地后仍是干净的半帧前缀，无 ABORT 字节混入。
      await Future<void>.delayed(const Duration(milliseconds: 1000));
      expect(mcu.pendingByteCount, 122);
      expect(mcu.writeTimeline, ['start#1', 'done#1']);
      // 本实例已取消，begin 的 CANCELLED 会先于写门禁拦截业务帧，故按真实
      // 路径（每次 bind 新建包装通道）用同设备的第二个 transport 复核废弃
      // 标记：设备作用域未因取消或换包装而失效（RC3-05⑤）。
      final rebounded = OtaBleTransport(channel: _ReboundWrapper(mcu));
      await _expectBusinessWriteRefused(rebounded, '取消交错后');
      await rebounded.dispose();
      await transport.dispose();
    }, timeout: const Timeout(Duration(seconds: 60)));

    test('半帧后排队的写在启动时复核通道：取消提前入队的 ABORT 不得'
        '写进悬空帧（RC3-05⑤）', () async {
      final package = packageBytes(4096);
      // 分片写 200ms、单片写超时 60ms：首个 DATA 帧的片 1 必然超时；
      // 有界 settle（2×60ms）在 180ms 到期时底层写仍未返回 → 抛
      // WRITE_TIMEOUT 并废弃写通道，片 1 的 20B 在 200ms 迟到落地，
      // MCU 侧滞留 20B 悬空帧（142B 帧只到 20B）。
      final mcu = _McuSim()
        ..mtu = 23
        ..writeChunkDelay = const Duration(milliseconds: 200);
      final transport = OtaBleTransport(
        channel: mcu,
        writeTimeout: const Duration(milliseconds: 60),
      );
      final future = transport.transfer(
        package: package,
        packageSha256: shaOf(package),
        etuHeader: etuHeaderOf(package),
      );
      // 取消发生在「片 1 在途、DATA 尚未超时」的窗口：abortBestEffort
      // 不等待传输循环退出，ABORT 在此刻入队排在 DATA 写之后——入队
      // 时刻通道尚未废弃，因此只在 _writeFrameChecked 里检查是不够的。
      await Future<void>.delayed(const Duration(milliseconds: 40));
      final abortFuture = transport.abortBestEffort();
      try {
        await future;
        fail('应中止');
      } on OtaTransportException catch (e) {
        expect(e.code, anyOf('WRITE_TIMEOUT', 'CANCELLED'));
      }
      await abortFuture;
      // 等片 1 迟到落地后再断言，确保观测的是最终字节流。
      await Future<void>.delayed(const Duration(milliseconds: 250));
      // 修复前：DATA 写失败放行串行队列（~180ms）时 _pending 仍空，
      // ABORT 被 fake 当作完整帧解析（abortFrames=1），随后片 1 迟到，
      // 字节流变成「ABORT + 半个 DATA」。真机上 MCU 处于 PAYLOAD 态，
      // 会把 ABORT 的 A5 5A 吞进 payload：既收不到 ABORT，也无法恢复
      // 同步（ota_ble_frame.c 按 len 吞全部字节）。
      expect(mcu.abortFrames, isEmpty);
      expect(
        mcu.writtenFrames.where((f) => f[2] == OtaBleCodec.cmdAbort),
        isEmpty,
      );
      // 悬空半帧只有 DATA 片 1 的 20B，无任何后续帧字节混入。
      expect(mcu.pendingByteCount, 20);
    }, timeout: const Timeout(Duration(seconds: 60)));

    test('分片写底层报错同样留下半帧：写通道废弃，尽力 ABORT 被拒'
        '（RC3-05⑤）', () async {
      final package = packageBytes(4096);
      // 首个 DATA 帧（142B / MTU=23 → 8 片）的片 3 底层写报错：片 1-2
      // 的 40B 已落地 MCU，帧解析器悬空在 payload 态。按 DATA 分片计数
      // 注错，不受 BEGIN 片数影响。
      final mcu = _McuSim()
        ..mtu = 23
        ..failAtDataChunk = 3;
      final transport = OtaBleTransport(channel: mcu);
      try {
        await transport.transfer(
          package: package,
          packageSha256: shaOf(package),
          etuHeader: etuHeaderOf(package),
        );
        fail('应中止');
      } catch (_) {
        // 底层写错误的具体类型不是本用例判据。
      }
      expect(mcu.pendingByteCount, 40);
      // 写超时不是半帧的唯一入口：底层写错误必须同样废弃写通道，否则
      // 尽力 ABORT 的 10B 会被追加进悬空帧（pending 变 50），MCU 既
      // 收不到 ABORT 也无法恢复同步。
      await transport.abortBestEffort();
      expect(mcu.pendingByteCount, 40);
      expect(mcu.abortFrames, isEmpty);
      await transport.dispose();
    }, timeout: const Timeout(Duration(seconds: 60)));

    test('迟到写不污染后来的会话：同设备换包装对象与真实重连都仍拒写，'
        'GET_INFO 探针证明重新同步后才放行（RC3-05⑤）', () async {
      final package = packageBytes(4096);
      // MTU 125 → 单分片 122B：DATA 帧（142B）第 1 片落地、第 2 片注入失败，
      // MCU 侧悬空 122B，距该帧 len 还差 20B——两次 GET_INFO 探针即可把它
      // 吃满（见下方重新同步断言）。
      final mcu = _McuSim()
        ..mtu = 125
        ..failAtDataChunk = 2;
      // 真实路径上 OtaService 每次 bind 都新建 _ChannelAdapter 包住同一台
      // 设备：废弃标记必须锚定设备作用域，而不是包装对象身份。
      final first = OtaBleTransport(channel: _ReboundWrapper(mcu));
      try {
        await first.transfer(
          package: package,
          packageSha256: shaOf(package),
          etuHeader: etuHeaderOf(package),
        );
        fail('应中止');
      } catch (_) {
        // 同上：本用例判据是后续会话的写行为。
      }
      await first.dispose();
      expect(mcu.pendingByteCount, 122);

      // 「新 transport + 新包装对象」不等于「设备已复位」：MCU 侧那半帧
      // 仍悬空，业务帧会被吞进 payload。有界等待只保证本帧不与自己的
      // 迟到分片交错，并没有取消底层写，因此废弃标记的作用域必须是设备
      // ——按通道对象作用域会在这里放行，把新帧写进悬空 DATA 帧。
      final rebound = OtaBleTransport(channel: _ReboundWrapper(mcu));
      await _expectBusinessWriteRefused(rebound, '同一设备上的新包装对象');
      // 放行与否由字节数鉴别（两种情况下都只会超时，错误码无区分力）。
      expect(mcu.pendingByteCount, 122, reason: '被拒的帧不得落下任何字节');
      await rebound.dispose();

      // 真实重连 ≠ 重新同步：BLE 链路重建不会复位 MCU 的 UART 解析器
      // （真值：session_teardown 不动 session->demux，ota_ble_demux_init
      // 只在开机 ota_ble_session_init 调用一次）。旧实现按链路代次作用域，
      // 重连即静默解除标记，把新帧继续写进悬空解析器——本用例在此处
      // 鉴别该错误解除条件。
      mcu.reconnect();
      final reconnected = OtaBleTransport(channel: _ReboundWrapper(mcu));
      await _expectBusinessWriteRefused(reconnected, '真实重连后');
      expect(mcu.pendingByteCount, 122,
          reason: '重连本身不是重新同步证据；重连次数=${mcu.linkReconnects}');

      // 唯一可达且可证明的重新同步路径：继续投递字节把悬空帧吃满
      // （解析器按 len 吞完 → CRC 失败 → 自复位），再以 INFO 应答为证。
      // GET_INFO 是废弃期间唯一放行的帧，它在被吞期间会整帧消失，因此
      // 按上界有界重试；收到 INFO 才解除标记。
      expect(mcu.badCrcFrames, 0);
      final info = await reconnected.getDeviceInfo();
      expect(info.deviceModel, 'e-track-at32f435');
      expect(info.hardwareRevision, 3);
      expect(mcu.badCrcFrames, greaterThanOrEqualTo(1),
          reason: '悬空帧必须被后续字节吃满并以 CRC 失败收场');
      expect(mcu.pendingByteCount, 0,
          reason: '重新同步后不得残留半帧或被吞的探针字节');

      // 证据成立后业务帧恢复（不是「重连就放行」的同义反复：解除发生在
      // INFO 应答之后，前两次业务帧尝试在同一连接/不同连接上都被拒）。
      final ack = await reconnected.begin(
        totalLen: package.length,
        packageSha256: shaOf(package),
        etuHeader: etuHeaderOf(package),
      );
      expect(ack.status, OtaBleCodec.statusOk);
      await reconnected.dispose();
    }, timeout: const Timeout(Duration(seconds: 60)));

    test('设备复位后重新同步：本端仍 fail-closed，探针一次即成且不产生坏帧'
        '（RC3-05⑤）', () async {
      final package = packageBytes(4096);
      final mcu = _McuSim()
        ..mtu = 125
        ..failAtDataChunk = 2;
      final first = OtaBleTransport(channel: _ReboundWrapper(mcu));
      try {
        await first.transfer(
          package: package,
          packageSha256: shaOf(package),
          etuHeader: etuHeaderOf(package),
        );
        fail('应中止');
      } catch (_) {
        // 判据是复位后的写行为。
      }
      await first.dispose();
      expect(mcu.pendingByteCount, 122);

      // 断电/复位是唯一会清掉 MCU 侧解析器状态的事件（reboot ≠ 重连）。
      mcu.powerCycle();
      expect(mcu.pendingByteCount, 0);

      // 但本端拿不到「设备已复位」的直接证据，仍须 fail-closed：标记不因
      // 设备侧状态变化自动解除，只能由一次真实 GET_INFO → INFO 往返解除。
      final afterReset = OtaBleTransport(channel: _ReboundWrapper(mcu));
      await _expectBusinessWriteRefused(afterReset, '设备已复位但本端尚未取得同步证据');
      final info = await afterReset.getDeviceInfo();
      expect(info.deviceModel, 'e-track-at32f435');
      expect(mcu.badCrcFrames, 0,
          reason: '解析器已随复位清空，无需靠坏帧冲刷，探针首次即应被完整解析');
      expect(mcu.linkReconnects, 0, reason: '复位不是 BLE 重连，用例本身不得混淆二者');
      final ack = await afterReset.begin(
        totalLen: package.length,
        packageSha256: shaOf(package),
        etuHeader: etuHeaderOf(package),
      );
      expect(ack.status, OtaBleCodec.statusOk,
          reason: '废弃标记不是永久砖化：取得同步证据后业务帧恢复');
      await afterReset.dispose();
    }, timeout: const Timeout(Duration(seconds: 60)));

    test('在途旧物理写未结算时，INFO 应答不得解除隔离（RC3-05⑤ 迟到写）',
        () async {
      final package = packageBytes(4096);
      // MTU=23 → DATA 帧 8 片；片 1 的底层写在 1.8s 后才落地，单片写超时
      // 200ms。600ms 时本帧以 WRITE_TIMEOUT 收场并废弃写通道，而**片 1 仍
      // 在途**——`Future.timeout` 不取消底层 writeChunk。此刻 MCU 侧 0 字节、
      // 解析器同步，探针能被完整解析并回 INFO：旧实现正是在这里解除隔离，
      // 随后 1.8s 迟到的片 1（含同步字的帧首）落进「已恢复」的通道，重新
      // 制造悬空半帧。
      final mcu = _McuSim()
        ..mtu = 23
        ..slowDataChunkAt = 1
        ..slowDataChunkDelay = const Duration(milliseconds: 1800);
      final transport = OtaBleTransport(
        channel: _ReboundWrapper(mcu),
        writeTimeout: const Duration(milliseconds: 200),
        noProgressTimeout: const Duration(seconds: 4),
      );
      await expectLater(
        transport.transfer(
          package: package,
          packageSha256: shaOf(package),
          etuHeader: etuHeaderOf(package),
        ),
        throwsA(isA<OtaTransportException>()),
      );
      expect(mcu.pendingByteCount, 0,
          reason: '片 1 尚未落地：MCU 解析器此刻是同步的');
      await transport.dispose();

      // 同设备上新 transport 取重新同步证据。
      final rebound = OtaBleTransport(channel: _ReboundWrapper(mcu));
      final probe = rebound.getDeviceInfo();
      final probeOutcome =
          probe.then<Object?>((_) => null, onError: (Object e) => e);
      await Future<void>.delayed(const Duration(milliseconds: 100));
      expect(
        mcu.sentFrames.where((f) => f.cmd == OtaBleCodec.rspInfo).length,
        1,
        reason: '探针被 MCU 完整解析并回了 INFO——旧实现正是在此处解除隔离',
      );
      // 判据一：旧物理写未结算期间，业务帧必须继续被拒。
      await _expectBusinessWriteRefused(rebound, '在途旧物理写未结算时');
      expect(mcu.pendingByteCount, 0,
          reason: '被拒的帧不得落下任何字节；探针帧已被完整解析');

      // 判据二：迟到片 1 落地后仍是「帧首字节」，解析器重新悬空——那条
      // 早期 INFO 没有被当成恢复证据，隔离依然成立。字节数只判下界：
      // 落地 20B 之后，废弃期的探针仍按上界重试，被吞进这半帧正是预期
      // 路径，故残留可能是 20B 或其叠加，判据是「悬空」而非精确字节数。
      await Future<void>.delayed(const Duration(milliseconds: 1800));
      expect(mcu.pendingByteCount, greaterThanOrEqualTo(20),
          reason: '迟到的帧首分片落地，解析器悬空在新的半帧上；'
              '实际残留 ${mcu.pendingByteCount}B（被吞的探针字节会叠加）');
      await _expectBusinessWriteRefused(rebound, '迟到帧首分片落地后');

      // 终止探针（本用例只验证围栏，不验证完全恢复——后者由上一用例的
      // 探针冲刷路径覆盖）。
      rebound.cancel();
      expect(await probeOutcome, isA<OtaTransportException>());
      await rebound.dispose();
    }, timeout: const Timeout(Duration(seconds: 60)));

    test('隔离前发出的旧 INFO 重放不得解除隔离：查询 seq 按设备分配'
        '（RC3-05⑤ 跨实例串号）', () async {
      final package = packageBytes(4096);
      final mcu = _McuSim()
        ..mtu = 125
        ..failAtDataChunk = 2;
      // ① 干净链路上先取一次真实 INFO：该帧属于「隔离之前」的世代。
      final clean = OtaBleTransport(channel: _ReboundWrapper(mcu));
      final info = await clean.getDeviceInfo();
      expect(info.hardwareRevision, 3);
      final staleIndex = mcu.sentFrames.length - 1;
      expect(mcu.sentFrames[staleIndex].cmd, OtaBleCodec.rspInfo);
      await clean.dispose();

      // ② 制造隔离：片 1 落地、片 2 底层报错，MCU 侧悬空 122B；此后探针
      //    会被吞进 payload，不存在任何新的 INFO 应答。
      final first = OtaBleTransport(channel: _ReboundWrapper(mcu));
      try {
        await first.transfer(
          package: package,
          packageSha256: shaOf(package),
          etuHeader: etuHeaderOf(package),
        );
        fail('应中止');
      } catch (_) {
        // 注入的底层写错误按原类型上抛：传输层对「半帧即废弃」负责，
        // 不重包装通道异常。本用例判据是后续会话的写入行为与字节数。
      }
      expect(mcu.pendingByteCount, 122);
      await first.dispose();

      // ③ 新 transport 发探针（同设备作用域）。
      final rebound = OtaBleTransport(channel: _ReboundWrapper(mcu));
      final probe = rebound.getDeviceInfo();
      final probeOutcome =
          probe.then<Object?>((_) => null, onError: (Object e) => e);
      await Future<void>.delayed(const Duration(milliseconds: 50));
      // ④ 重放隔离前那条 INFO。旧实现下「每个实例的查询 seq 都从 0 起」，
      //    该帧的 seq 恰与新实例探针的 seq 相同，会被当成重新同步证据并
      //    解除隔离——而它证明不了任何关于当前解析器状态的事。
      mcu.replaySentFrame(staleIndex);
      await Future<void>.delayed(const Duration(milliseconds: 50));
      await _expectBusinessWriteRefused(rebound, '重放隔离前的旧 INFO 后');
      expect(mcu.pendingByteCount, 132,
          reason: '悬空 122B 加上被吞掉的探针帧 10B，被拒的帧不得落下字节');

      rebound.cancel();
      expect(await probeOutcome, isA<OtaTransportException>());
      await rebound.dispose();
    }, timeout: const Timeout(Duration(seconds: 60)));

    test('恢复探针写卡死：端到端预算封顶写/结算等待，到期退休且不解除隔离'
        '（RC3-07 黑洞）', () async {
      final package = packageBytes(4096);
      // 悬空半帧 122B（同「迟到写」用例）：隔离成立。此后 GET_INFO 探针
      // 写被永久卡死（hangControlCmd=cmdGetInfo）。旧实现里探针预算只管
      // 循环入口/应答等待，写分片与结算宽限是「探针之外的无界第三段等待」
      // （写 10s + 结算 20s，终止迟到预算之外）；RC3-07 修复后写分片
      // （_capByBudget(writeTimeout)）与结算宽限（_capByBudget(2×timeout)）
      // 都被探针预算（16s）封顶，终止发布不得晚于预算截止。
      final mcu = _McuSim()
        ..mtu = 125
        ..failAtDataChunk = 2
        ..hangControlCmd = OtaBleCodec.cmdGetInfo;
      final first = OtaBleTransport(channel: _ReboundWrapper(mcu));
      try {
        await first.transfer(
          package: package,
          packageSha256: shaOf(package),
          etuHeader: etuHeaderOf(package),
        );
        fail('应中止');
      } catch (_) {
        // 判据是后续恢复探针的行为，注入的底层写错误类型不作为判据。
      }
      await first.dispose();
      expect(mcu.pendingByteCount, 122);

      final stopwatch = Stopwatch()..start();
      final rebound = OtaBleTransport(channel: _ReboundWrapper(mcu));
      await expectLater(
        rebound.getDeviceInfo(),
        throwsA(
          isA<OtaTransportException>()
              .having((e) => e.code, 'code', 'TIMEOUT'),
        ),
      );
      stopwatch.stop();
      expect(
        stopwatch.elapsed,
        greaterThanOrEqualTo(const Duration(seconds: 15)),
        reason: '写卡死必须消耗完整探针预算（16s）才退休，不得提前放弃；'
            '实测 ${stopwatch.elapsed.inMilliseconds}ms',
      );
      expect(
        stopwatch.elapsed,
        lessThan(const Duration(seconds: 19)),
        reason: '终止发布不得拖到「写 10s + 结算 20s」之外的第三段等待；'
            '实测 ${stopwatch.elapsed.inMilliseconds}ms',
      );
      // 到期退休：仍无重新同步证据，隔离保持——业务帧继续被拒。
      await _expectBusinessWriteRefused(rebound, '探针写卡死、恢复到期退休后');
      // 卡死的探针写仍在设备账本在途：idle 等待超时正是「继续跟踪迟到
      // 物理写、不假装恢复」的体现。被拒的帧不得落下任何字节。
      expect(mcu.pendingByteCount, 122,
          reason: '探针写从未落地，被拒的帧不得落下字节');
      await rebound.dispose();
    }, timeout: const Timeout(Duration(seconds: 60)));

    test('探针写完成但 INFO 迟到于恢复预算：到期退休后迟到 INFO 不解除隔离'
        '（RC3-07 迟应答）', () async {
      final package = packageBytes(4096);
      // 隔离成立（悬空 122B）。探针写能完成，但 INFO 应答被延迟
      // （infoResponseDelay=5s）——每个探针的应答等待（≤800ms）都在
      // INFO 到达前超时，恢复进程按预算重试、最终到期退休。旧实现在
      // 「预算耗尽后的某次探针写完成 + INFO 迟到」时可能把迟到 INFO 当
      // 解除证据放行；RC3-07 的响应等待封顶 + 退休作废探针登记确保迟到
      // INFO 无权解除隔离。
      final mcu = _McuSim()
        ..mtu = 125
        ..failAtDataChunk = 2
        ..infoResponseDelay = const Duration(seconds: 5);
      final first = OtaBleTransport(channel: _ReboundWrapper(mcu));
      try {
        await first.transfer(
          package: package,
          packageSha256: shaOf(package),
          etuHeader: etuHeaderOf(package),
        );
        fail('应中止');
      } catch (_) {
        // 同上：判据是后续恢复探针的行为。
      }
      await first.dispose();
      expect(mcu.pendingByteCount, 122);

      final stopwatch = Stopwatch()..start();
      final rebound = OtaBleTransport(channel: _ReboundWrapper(mcu));
      await expectLater(
        rebound.getDeviceInfo(),
        throwsA(
          isA<OtaTransportException>()
              .having((e) => e.code, 'code', 'TIMEOUT'),
        ),
      );
      stopwatch.stop();
      expect(
        stopwatch.elapsed,
        greaterThanOrEqualTo(const Duration(seconds: 15)),
        reason: '迟应答同样必须消耗完整探针预算才退休；'
            '实测 ${stopwatch.elapsed.inMilliseconds}ms',
      );
      expect(
        stopwatch.elapsed,
        lessThan(const Duration(seconds: 19)),
        reason: '迟到应答不得把恢复拖延到预算之外；'
            '实测 ${stopwatch.elapsed.inMilliseconds}ms',
      );
      // 恢复事务已退休。等迟到 INFO 投递窗口过完（最后一次探针写 +5s
      // 之后），迟到的应答仍不得解除隔离——业务帧继续被拒。
      await Future<void>.delayed(const Duration(seconds: 6));
      await _expectBusinessWriteRefused(rebound, '迟到 INFO 投递后恢复已退休');
      await rebound.dispose();
    }, timeout: const Timeout(Duration(seconds: 60)));

    test('后台暂停/恢复：发窗在帧边界挂起，恢复后传输完成（RC3-08）',
        () async {
      final package = packageBytes(4096);
      // 窗口 4 + ACK 延迟 100ms：整包 ≈ 8 窗 × 100ms + END，传输时长
      // 足够在途中介入暂停并鉴别"挂起期间不前进"。
      final mcu = _McuSim()
        ..ackDelay = const Duration(milliseconds: 100);
      final transport = OtaBleTransport(
        channel: mcu,
        noProgressTimeout: const Duration(seconds: 30),
      );
      final future = transport.transfer(
        package: package,
        packageSha256: shaOf(package),
        etuHeader: etuHeaderOf(package),
        windowSegments: 4,
      );
      var settled = false;
      future.then((_) => settled = true, onError: (Object _) => settled = true);
      // 约 2 个窗口后暂停。
      await Future<void>.delayed(const Duration(milliseconds: 200));
      transport.pauseForBackground();
      // 等在途 ACK 收敛、发送循环到达帧边界闸门后取冻结快照。
      await Future<void>.delayed(const Duration(milliseconds: 400));
      final frozen = mcu.writtenFrames.length;
      // 挂起 800ms（远超 ACK 延迟）：无新帧、传输未完成、未误判取消、
      // 预算时钟停走不烧 30s 总预算——没有闸门时传输早已继续推进。
      await Future<void>.delayed(const Duration(milliseconds: 800));
      expect(mcu.writtenFrames.length, frozen);
      expect(settled, isFalse);
      expect(transport.isCancelled, isFalse);
      transport.resumeFromBackground();
      final ack = await future;
      expect(ack.isOk, isTrue);
      expect(ack.durableOff, 4096);
    }, timeout: const Timeout(Duration(seconds: 60)));

    test('传输在途 GET_INFO 复核不占会话 seq：DATA 连续不被 ERR_SEQ 打断（RC3-08⑦）',
        () async {
      final package = packageBytes(4096);
      // ACK 延迟让传输保持在途；期间插入一次 GET_INFO（service 三级
      // 复核的真实形态）。修复前 GET_INFO 从会话计数器取号，后续 DATA
      // 整体跳号被 MCU 会话层 ERR_SEQ 拒收（真值 session_seq_check 对
      // 会话帧严格连续）→ 内部 ABORT+BEGIN 重对齐 + 从 durable 整段重发。
      final mcu = _McuSim()..ackDelay = const Duration(milliseconds: 50);
      final transport = OtaBleTransport(
        channel: mcu,
        noProgressTimeout: const Duration(seconds: 30),
      );
      final future = transport.transfer(
        package: package,
        packageSha256: shaOf(package),
        etuHeader: etuHeaderOf(package),
      );
      // 等首批 DATA 在途（ACK 延迟窗口内）再复核。
      while (mcu.dataOffsets.isEmpty) {
        await Future<void>.delayed(const Duration(milliseconds: 5));
      }
      final info = await transport.getDeviceInfo(
          timeout: const Duration(seconds: 2));
      expect(info.deviceModel, 'e-track-at32f435');
      final ack = await future;
      expect(ack.isOk, isTrue);
      expect(ack.durableOff, 4096);
      expect(mcu.beginCalls, 1, reason: '复核不得触发 ERR_SEQ 内部恢复重对齐');
      expect(mcu.abortCalls, 0, reason: '复核是只读探测，不得发 ABORT');
      expect(mcu.dataOffsets.length, 32, reason: '4096B 恰 32 段，不得重发');
      expect(mcu.dataOffsets.toSet().length, 32);
    }, timeout: const Timeout(Duration(seconds: 60)));

    test('暂停挂起中取消：闸门解除不死锁，CANCELLED 立即返回（RC3-08）',
        () async {
      final package = packageBytes(4096);
      final mcu = _McuSim()..respondDataAck = false;
      final transport = OtaBleTransport(
        channel: mcu,
        ackTimeout: const Duration(milliseconds: 200),
        retries: 999,
        noProgressTimeout: const Duration(seconds: 30),
      );
      final future = transport.transfer(
        package: package,
        packageSha256: shaOf(package),
        etuHeader: etuHeaderOf(package),
      );
      await Future<void>.delayed(const Duration(milliseconds: 50));
      transport.pauseForBackground();
      // 等 ACK 超时（200ms）过期、重发循环推进到帧边界闸门：此刻传输
      // 确定性阻塞在 _waitIfPaused() 上。
      await Future<void>.delayed(const Duration(milliseconds: 600));
      // 不 resume 直接取消：cancel 必须解除闸门，让挂起循环继续走到
      // 取消检查并抛 CANCELLED——否则 owner await 永久死锁（本用例
      // 即为该死锁回归：修复前 cancel 不释放闸门，future 永不完成）。
      transport.cancel();
      try {
        await future;
        fail('应抛 CANCELLED');
      } on OtaTransportException catch (e) {
        expect(e.code, 'CANCELLED');
      }
    }, timeout: const Timeout(Duration(seconds: 60)));

    // RC3-02/04⑦：命令帧等待者的异步错误窗口。GET_INFO/BEGIN/END/ABORT
    // 是同一形状——`_waiters.add(waiter)` → `await _writeFrame(frame)` →
    // `await waiter.future`。物理写是 await 点：分片写让出期间发生
    // cancel()/dispose()/通知流 onError 时，waiter.fail() 会对一个**尚无
    // 监听者**的 future completeError，Dart 立即把它当 uncaught async
    // error 上报到该 future 的**创建 zone**——生产里越过调用方
    // try/catch 变成 zone 级错误，测试里直接判失败。
    //
    // 判据必须同时成立：zone 捕获列表为空（错误没有逃逸）**且**调用方
    // 仍拿到确定的错误（不是靠吞错变绿）。只断言前者会被「waiter 永不
    // fail、调用方挂死到超时」蒙过；只断言后者则修复前后都绿。
    test('延迟写期间取消：命令等待者错误不逃逸为 uncaught async error'
        '（RC3-02/04⑦）', () async {
      final outcome = await _runCommandWriteWindowDisturbance(
          (transport, channel) => transport.cancel());
      expect(
        outcome.callerError,
        isA<OtaTransportException>().having((e) => e.code, 'code', 'CANCELLED'),
      );
      expect(outcome.zoneErrors, isEmpty);
    });

    test('延迟写期间释放：命令等待者错误不逃逸为 uncaught async error'
        '（RC3-02/04⑦）', () async {
      // dispose() 自身要 await _frameSub.cancel()，此处不阻塞扰动时序；
      // 助手收尾会再次 dispose（fail/cancel 均幂等）。
      final outcome = await _runCommandWriteWindowDisturbance(
          (transport, channel) => unawaited(transport.dispose()));
      expect(
        outcome.callerError,
        isA<OtaTransportException>().having((e) => e.code, 'code', 'DISPOSED'),
      );
      expect(outcome.zoneErrors, isEmpty);
    });

    test('延迟写期间通知流报错：命令等待者错误不逃逸为 uncaught async '
        'error（RC3-02/04⑦）', () async {
      final outcome = await _runCommandWriteWindowDisturbance((transport,
              channel) =>
          channel.emitNotifyError(const _InjectedNotifyError()));
      // _dispatchError 原样下发（不包装），调用方观测到注入对象本身。
      expect(outcome.callerError, isA<_InjectedNotifyError>());
      expect(outcome.zoneErrors, isEmpty);
    });
  });

  group('P3-4 链路观测接线（OtaLinkStats）', () {
    test('clean run 8192：每唯一段恰一 ACK 样本，摘要完整、outcome=ok',
        () async {
      final package = packageBytes(8192); // 2 块 64 段
      // ACK 延迟 1ms：只为还原「确认到达晚于首发发送结束登记」这一正常
      // 时序（真机 ACK 至少一个连接间隔后才到），使本用例聚焦样本完整性
      // 而非早到竞态。零延迟下的早到确认由本组 P34-R01 反例专门覆盖，
      // 不得再用「真机不存在该竞争」回避该路径。
      final mcu = _McuSim()..ackDelay = const Duration(milliseconds: 1);
      final stats = OtaLinkStats(label: 'upgrade');
      final transport = OtaBleTransport(channel: mcu, stats: stats);
      final ack = await transport.transfer(
        package: package,
        packageSha256: shaOf(package),
        etuHeader: etuHeaderOf(package),
      );
      expect(ack.isOk, isTrue);
      // 64 唯一段，每段恰一 ACK 样本（冻结语义：首发结束→首个有效确认）。
      expect(stats.segmentsUnique, 64);
      expect(stats.ackLatencySamplesUs, hasLength(64));
      expect(stats.ackSampleIntegrity, 'complete');
      // 正常时序下不得出现早到无效观测（提前判失败即早到路径被误触）。
      expect(stats.ackEarlyInvalid, 0);
      expect(stats.retransmitFrames, 0);
      // 每段一 DATA ACK、无重复/错误/畸形。
      expect(stats.acksOk, 64);
      expect(stats.acksDuplicate, 0);
      expect(stats.acksMalformed, 0);
      // durable 序列：BEGIN ACK 起点 0 + 两次块提交（单调递增）。
      expect(stats.durableOffsets, [0, 4096, 8192]);
      // 传输时长（BEGIN 首帧写开始 → END ACK 到达，同一时钟域）> 0。
      final t = stats.toJson()['transfer'] as Map<String, dynamic>;
      expect(t['outcome'], 'ok');
      expect(t['elapsedUs'] as int?, greaterThan(0));
      expect(t['segmentsUnique'], 64);
    }, timeout: const Timeout(Duration(seconds: 60)));

    test('丢部分 DATA ACK：位图确认回收，样本仍每段恰一个', () async {
      final package = packageBytes(4096);
      final mcu = _McuSim()
        ..dropAckForOffsets = {0, 128} // 段 0/1 的 ACK 丢
        ..ackDelay = const Duration(milliseconds: 1); // 还原确认晚于首发的正常时序
      final stats = OtaLinkStats(label: 'upgrade');
      final transport = OtaBleTransport(channel: mcu, stats: stats);
      final ack = await transport.transfer(
        package: package,
        packageSha256: shaOf(package),
        etuHeader: etuHeaderOf(package),
        windowSegments: 4,
      );
      expect(ack.isOk, isTrue);
      // 32 段全部送达且零重发（位图回收，RC2-05）。
      expect(
        mcu.writtenFrames.where((f) => f[2] == OtaBleCodec.cmdData).length,
        32,
      );
      // 丢 ACK 段（0/1）的确认来自后续段 ACK 的 bitmap 置位——共享
      // 同一 ACK 的段各自成样本，终点相同、起点各异。
      expect(stats.segmentsUnique, 32);
      expect(stats.ackLatencySamplesUs, hasLength(32));
      expect(stats.ackSampleIntegrity, 'complete');
      expect(stats.ackEarlyInvalid, 0);
      expect(stats.retransmitFrames, 0);
      // 送达的 ACK 30 份（段 0/1 的被丢），全部 ok。
      expect(stats.acksOk, 30);
      expect(stats.acksDuplicate, 0);
    }, timeout: const Timeout(Duration(seconds: 60)));

    test('块尾段 ACK 丢后重发：重传计入计数，样本不新增（冻结语义）',
        () async {
      final package = packageBytes(8192);
      final mcu = _McuSim()
        ..dropAckOnceForOffsets = {31 * 128} // 块 0 尾段
        ..ackDelay = const Duration(milliseconds: 1); // 还原确认晚于首发的正常时序
      final stats = OtaLinkStats(label: 'upgrade');
      final transport = OtaBleTransport(channel: mcu, stats: stats);
      final ack = await transport.transfer(
        package: package,
        packageSha256: shaOf(package),
        etuHeader: etuHeaderOf(package),
      );
      expect(ack.isOk, isTrue);
      // 首发 64 段 + 块 0 尾段一次重发（首发 ACK 丢失），无其他重发。
      expect(
        mcu.writtenFrames.where((f) => f[2] == OtaBleCodec.cmdData).length,
        65,
      );
      // 重传不创建新样本：唯一段仍 64、样本仍 64、起点仍是首发结束。
      expect(stats.segmentsUnique, 64);
      expect(stats.retransmitFrames, 1);
      expect(stats.ackLatencySamplesUs, hasLength(64));
      expect(stats.ackSampleIntegrity, 'complete');
      expect(stats.ackEarlyInvalid, 0);
      // 重发段（off 3968）的确认来自重发触发的幂等 ACK（durable 前移
      // 4096，advanced 回收自身段）——样本终点含超时等待与重发全程。
      expect(stats.durableOffsets, [0, 4096, 8192]);
    }, timeout: const Timeout(Duration(seconds: 60)));

    test('重复 DATA ACK：duplicate 计数，样本数不变', () async {
      final package = packageBytes(4096);
      final mcu = _McuSim()
        ..duplicateDataAck = true
        ..ackDelay = const Duration(milliseconds: 1); // 还原确认晚于首发的正常时序
      final stats = OtaLinkStats(label: 'upgrade');
      final transport = OtaBleTransport(channel: mcu, stats: stats);
      final ack = await transport.transfer(
        package: package,
        packageSha256: shaOf(package),
        etuHeader: etuHeaderOf(package),
      );
      expect(ack.isOk, isTrue);
      // 每段两份 ACK：第二份 seq 已不在途 → duplicate 分类，不产生样本。
      expect(stats.acksOk, 32);
      expect(stats.acksDuplicate, 32);
      expect(stats.ackLatencySamplesUs, hasLength(32));
      expect(stats.ackSampleIntegrity, 'complete');
      expect(stats.ackEarlyInvalid, 0);
    }, timeout: const Timeout(Duration(seconds: 60)));

    test('零延迟 ACK 早到：不造假样本，显式计为无效观测（P34-R01）',
        () async {
      final package = packageBytes(4096);
      // ackDelay=0：DATA ACK 在写调用内同步 emit，其流监听微任务先于发送
      // 循环 recordSegmentSendEnd 的 continuation 运行——确认到达时本段
      // 首发尚未登记。此时既没有合法起点（不得把负延迟截成 0），也不得
      // 让随后的迟到重复确认顶替出「起点=重发结束」的假样本；必须显式
      // 记为无效观测并进入完整性缺口。
      final mcu = _McuSim();
      expect(mcu.ackDelay, Duration.zero);
      final stats = OtaLinkStats(label: 'upgrade');
      final transport = OtaBleTransport(channel: mcu, stats: stats);
      final ack = await transport.transfer(
        package: package,
        packageSha256: shaOf(package),
        etuHeader: etuHeaderOf(package),
      );
      // 观测缺陷不影响控制流：确认仍被视图消费，会话照常成功。
      expect(ack.isOk, isTrue);
      expect(stats.segmentsUnique, 32);
      // 32 段确认全部早到：零样本、零假样本，缺口如实上报。
      expect(stats.ackEarlyInvalid, 32);
      expect(stats.ackLatencySamplesUs, isEmpty);
      expect(stats.ackSampleIntegrity, 'partial:missing=32,early=32');
      final t = stats.toJson()['transfer'] as Map<String, dynamic>;
      expect(t['ackEarlyInvalid'], 32);
      expect(t['ackSamples'], 'partial:missing=32,early=32');
      expect((t['ackLatency'] as Map<String, dynamic>)['count'], 0);
      expect(t['elapsedUs'] as int?, greaterThan(0));
    }, timeout: const Timeout(Duration(seconds: 60)));

    test('同实例无 ACK 恢复：resume BEGIN 回带的 durable 前缀补齐丢失确认'
        '段的样本（P34-R02）', () async {
      final package = packageBytes(8192); // 2 块
      // 块 0 的 32 段 DATA ACK 全丢（MCU staging 照常提交）：客户端看不到
      // 任何确认 → 重发触顶 → ABORT + BEGIN resume。resume 的 BEGIN ACK
      // 回带 durable=4096，这 32 段由 durable_off 明确确认，样本终点即该
      // ACK 的到达时刻——不得因 DATA ACK 丢失在完整性分母里留下缺口。
      final mcu = _McuSim()
        ..dropAckForOffsets = {for (var i = 0; i < 32; i++) i * 128}
        ..ackDelay = const Duration(milliseconds: 1);
      final stats = OtaLinkStats(label: 'upgrade');
      final transport = OtaBleTransport(
        channel: mcu,
        stats: stats,
        retries: 1,
        ackTimeout: const Duration(milliseconds: 200),
      );
      final ack = await transport.transfer(
        package: package,
        packageSha256: shaOf(package),
        etuHeader: etuHeaderOf(package),
      );
      expect(ack.isOk, isTrue);
      expect(mcu.beginCalls, 2); // BEGIN + resume BEGIN
      expect(mcu.abortCalls, 1); // resume 前主动 ABORT teardown
      // 64 唯一段：块 0 的样本由 resume BEGIN ACK 补记，块 1 由 DATA ACK 采。
      expect(stats.segmentsUnique, 64);
      expect(stats.ackLatencySamplesUs, hasLength(64));
      expect(stats.ackSampleIntegrity, 'complete');
      expect(stats.ackEarlyInvalid, 0);
      // 丢 ACK 期间 MCU 已提交的 durable 进展如实登记（BEGIN ACK 带回）。
      expect(stats.durableOffsets, [0, 4096, 8192]);
    }, timeout: const Timeout(Duration(seconds: 60)));

    test('新实例续传：resume 前缀本实例从未发送 ⇒ 不制造样本，如实记为'
        '无效观测（P34-R02）', () async {
      final package = packageBytes(8192); // 2 块
      final mcu = _McuSim()..ackDelay = const Duration(milliseconds: 1);
      // 断线续传真值：上次会话在块 0 提交后中断（journal durable=4096，
      // RAM 层清空）。新实例——新 stats——只发块 1。
      await _prestageCommittedBlock0(mcu, package);
      expect(mcu.stagedDurable, 4096);
      final stats = OtaLinkStats(label: 'upgrade');
      final transport = OtaBleTransport(channel: mcu, stats: stats);
      final ack = await transport.transfer(
        package: package,
        packageSha256: shaOf(package),
        etuHeader: etuHeaderOf(package),
      );
      expect(ack.isOk, isTrue);
      expect(stats.segmentsUnique, 32); // 只有块 1 由本实例发送
      expect(stats.ackLatencySamplesUs, hasLength(32));
      // BEGIN ACK 回带的 durable 前缀（块 0 的 32 段）本实例从未发送：
      // 不得为它们补造样本，只如实记为未发送的早到确认（暂挂），既不进
      // 样本也不进完整性缺口——完整性只对「本实例发过的段」负责。
      expect(stats.ackEarlyInvalid, 0);
      expect(stats.ackSampleIntegrity, 'complete');
      final t = stats.toJson()['transfer'] as Map<String, dynamic>;
      expect(t['ackEarlyUnsent'], 32, reason: '未发送前缀段必须留痕可审计');
      expect(t['ackSamples'], 'complete');
      expect(t['ackEarlyInvalid'], 0);
    }, timeout: const Timeout(Duration(seconds: 60)));

    test('END 终点在采信点登记：重复/迟到的真 ACK_END 不覆盖终点'
        '（P34-R03）', () async {
      final package = packageBytes(4096);
      final mcu = _McuSim()..ackDelay = const Duration(milliseconds: 1);
      final stats = OtaLinkStats(label: 'upgrade');
      final transport = OtaBleTransport(channel: mcu, stats: stats);
      final ack = await transport.transfer(
        package: package,
        packageSha256: shaOf(package),
        etuHeader: etuHeaderOf(package),
      );
      expect(ack.isOk, isTrue);
      final before = stats.toJson()['transfer'] as Map<String, dynamic>;
      expect(before['endAckUs'], isNotNull);
      // 重放同一条真 ACK_END（通知缓冲重放/迟到重复：真实链路可能）：
      // 该帧与任何在途请求都无关联，不得据此改写已采信的成功终点。
      final endIdx = mcu.sentFrameBytes
          .lastIndexWhere((f) => f[2] == OtaBleCodec.rspAckEnd);
      expect(endIdx, isNonNegative, reason: '本次传输必有 ACK_END 应答');
      mcu.replaySentFrame(endIdx);
      await Future<void>.delayed(const Duration(milliseconds: 10));
      final after = stats.toJson()['transfer'] as Map<String, dynamic>;
      expect(after['endAckUs'], before['endAckUs']);
      expect(after['elapsedUs'], before['elapsedUs']);
      // 重放帧只按重复 ACK 分类，端点时刻与样本均不受影响。
      expect(stats.ackLatencySamplesUs, hasLength(32));
    }, timeout: const Timeout(Duration(seconds: 60)));

    test('未采信的 END 应答不登记终点：失败传输的 endAckUs/elapsedUs 为空'
        '（P34-R03）', () async {
      final package = packageBytes(4096);
      // END 整包校验失败（ERR_SHA）：MCU 确实发出 ACK_END 帧，但它是错误
      // 终态，不是成功终点——统计终点必须保持为空，摘要如实报 fail。
      final mcu = _McuSim()
        ..ackDelay = const Duration(milliseconds: 1)
        ..endAckStatus = OtaBleCodec.statusErrSha;
      final stats = OtaLinkStats(label: 'upgrade');
      final transport = OtaBleTransport(channel: mcu, stats: stats);
      final result = await transport.transfer(
        package: package,
        packageSha256: shaOf(package),
        etuHeader: etuHeaderOf(package),
      );
      expect(result.isOk, isFalse);
      expect(
        mcu.sentFrameBytes.any((f) => f[2] == OtaBleCodec.rspAckEnd),
        isTrue,
        reason: 'MCU 已回 ACK_END；本用例判据是它不得被登记为成功终点',
      );
      final t = stats.toJson()['transfer'] as Map<String, dynamic>;
      expect(t['endAckUs'], isNull, reason: '错误终态不得登记成功终点');
      expect(t['elapsedUs'], isNull);
      expect(t['outcome'], 'fail');
    }, timeout: const Timeout(Duration(seconds: 60)));

    test('传输起点在首个 BEGIN 帧写调用时刻登记（保守代理，含排队等待）'
        '（P34-R03）', () async {
      final package = packageBytes(4096);
      // BEGIN 写永不返回（写通道黑洞）：若起点在写完成后才登记，本用例
      // 观测到的起点必为空。契约文本是「从 BEGIN 首字节开始发送」；Dart 侧
      // 代理点取首个 BEGIN 帧的**写调用**开始（早于排队/分片/上线，故为
      // 保守上界），终点取被采信 ACK 的到达分发点时刻。
      final mcu = _McuSim()..hangControlCmd = OtaBleCodec.cmdBegin;
      final stats = OtaLinkStats(label: 'upgrade');
      final transport = OtaBleTransport(
        channel: mcu,
        stats: stats,
        writeTimeout: const Duration(milliseconds: 300),
      );
      final pending = transport.transfer(
        package: package,
        packageSha256: shaOf(package),
        etuHeader: etuHeaderOf(package),
      );
      await Future<void>.delayed(const Duration(milliseconds: 100));
      expect(mcu.controlChunkWrites, greaterThan(0), reason: 'BEGIN 已开始写');
      expect(stats.toJson()['transfer']['startUs'], isNotNull,
          reason: '写调用未返回前起点必须已登记（含排队等待）');
      // 收尾：写超时终止本次传输，不留悬挂 future。
      await expectLater(
        pending,
        throwsA(isA<OtaTransportException>()
            .having((e) => e.code, 'code', 'WRITE_TIMEOUT')),
      );
      await transport.dispose();
    }, timeout: const Timeout(Duration(seconds: 60)));

    test('END 终点取被采信 ACK 的到达时刻：写结算后时钟再推进也不改判'
        '（P34-DA01）', () async {
      final package = packageBytes(4096);
      final mcu = _McuSim();
      final channel = _FrameGateChannel(mcu)
        ..preGateCmd = OtaBleCodec.cmdEnd
        ..postGateCmd = OtaBleCodec.cmdEnd;
      var fakeUs = 1000000;
      final stats = OtaLinkStats(label: 'upgrade', clockUs: () => fakeUs);
      final transport = OtaBleTransport(channel: channel, stats: stats);
      final pending = transport.transfer(
        package: package,
        packageSha256: shaOf(package),
        etuHeader: etuHeaderOf(package),
      );
      // END 写进入前置闸门：此刻 MCU 尚未产生任何 ACK_END，到达时刻还
      // 不存在，天然排除「先到帧打戳」的混淆。
      await _pumpUntil(() => channel.preGateHits == 1,
          reason: 'END 写未到达前置闸门');
      // 到达窗口：时钟设为可辨识的到达时刻，再放行写。
      fakeUs = 7777000;
      channel.releasePre();
      // 真 ACK_END 已在分发点打戳（读到的时钟即 7777000），写仍被后置
      // 闸门挡住——「应答到达」与「写结算」由此分离成两个可辨识时刻。
      await _pumpUntil(() => channel.postGateHits == 1,
          reason: 'ACK_END 分发后未进入后置闸门');
      // 写结算之后的时刻：事后另取时钟的实现（含本用例的变异体）读到它。
      fakeUs = 8888000;
      channel.releasePost();
      final ack = await pending;
      expect(ack.isOk, isTrue);
      final t = stats.toJson()['transfer'] as Map<String, dynamic>;
      expect(t['endAckUs'], 7777000,
          reason: '终点必须是被采信 ACK 帧到达分发点的时刻');
      expect(t['elapsedUs'], 7777000 - 1000000,
          reason: '写结算与校验耗时不得计入传输时长');
      // 重复控制：同一条真 ACK_END 迟到重放（时钟已推进）不得改写终点。
      final endIdx = mcu.sentFrameBytes
          .lastIndexWhere((f) => f[2] == OtaBleCodec.rspAckEnd);
      expect(endIdx, isNonNegative, reason: '本次传输必有 ACK_END 应答');
      fakeUs = 9999000;
      mcu.replaySentFrame(endIdx);
      await Future<void>.delayed(const Duration(milliseconds: 10));
      final after = stats.toJson()['transfer'] as Map<String, dynamic>;
      expect(after['endAckUs'], 7777000);
      expect(after['elapsedUs'], 7777000 - 1000000);
      await transport.dispose();
    }, timeout: const Timeout(Duration(seconds: 60)));

    test('未采信的 END 类帧到达不登记终点：伪造 ACK_END 只按无关应答处理'
        '（P34-DA01）', () async {
      final package = packageBytes(4096);
      final mcu = _McuSim();
      final channel = _FrameGateChannel(mcu)
        ..preGateCmd = OtaBleCodec.cmdEnd
        ..postGateCmd = OtaBleCodec.cmdEnd;
      var fakeUs = 1000000;
      final stats = OtaLinkStats(label: 'upgrade', clockUs: () => fakeUs);
      final transport = OtaBleTransport(channel: channel, stats: stats);
      final pending = transport.transfer(
        package: package,
        packageSha256: shaOf(package),
        etuHeader: etuHeaderOf(package),
      );
      await _pumpUntil(() => channel.preGateHits == 1,
          reason: 'END 写未到达前置闸门');
      // 伪造一条 seq 不在途的 ACK_END：它是「到达的 END 类帧」，但不是
      // 本次请求的应答，分发点不得为等待者留下时刻。
      fakeUs = 1111000;
      mcu.sendFrame(OtaBleCodec.rspAckEnd, 1, 0x5A5A,
          packAck(OtaBleCodec.statusOk, package.length, 0));
      await Future<void>.delayed(const Duration(milliseconds: 5));
      // 之后才放行真 END 写，其 ACK 在 2222000 到达并被采信。
      fakeUs = 2222000;
      channel.releasePre();
      await _pumpUntil(() => channel.postGateHits == 1,
          reason: 'ACK_END 分发后未进入后置闸门');
      fakeUs = 3333000;
      channel.releasePost();
      final ack = await pending;
      expect(ack.isOk, isTrue);
      final t = stats.toJson()['transfer'] as Map<String, dynamic>;
      expect(t['endAckUs'], 2222000,
          reason: '终点只能来自被采信的应答，不得被先到的无关 END 类帧占用');
      expect(t['endAckUs'], isNot(1111000));
      await transport.dispose();
    }, timeout: const Timeout(Duration(seconds: 60)));

    test('resume BEGIN 前缀样本终点取该 BEGIN ACK 的到达时刻（P34-DA01）',
        () async {
      final package = packageBytes(4096); // 单块 32 段
      // 整块 DATA ACK 全丢：MCU 照常提交（staging 落盘），发送端无从得知，
      // 重发计数超限后走 ABORT + BEGIN 续传（RC3-08③）。续传 BEGIN 回带的
      // durable 前缀因此覆盖 32 个「已发送但从未获得 ACK 样本」的段。
      final mcu = _McuSim()
        ..dropAckForOffsets = {for (var i = 0; i < 32; i++) i * 128}
        ..ackDelay = const Duration(milliseconds: 1);
      // 闸门只挂在第 2 次 BEGIN（续传那一轮）：第 1 次 BEGIN 不受影响。
      final channel = _FrameGateChannel(mcu)
        ..preGateCmd = OtaBleCodec.cmdBegin
        ..preGateAt = 2
        ..postGateCmd = OtaBleCodec.cmdBegin
        ..postGateAt = 2;
      var fakeUs = 1000000;
      final stats = OtaLinkStats(label: 'upgrade', clockUs: () => fakeUs);
      final transport = OtaBleTransport(
        channel: channel,
        stats: stats,
        // 同「同实例无 ACK 恢复」用例的恢复参数：整块 ACK 全丢 → 重发触顶
        // （retries=1）→ ABORT + BEGIN 续传。
        retries: 1,
        ackTimeout: const Duration(milliseconds: 200),
      );
      final pending = transport.transfer(
        package: package,
        packageSha256: shaOf(package),
        etuHeader: etuHeaderOf(package),
      );
      // 重传触顶与 ABORT 往返都要真实时钟推进，故这里用非零 tick。
      await _pumpUntil(() => channel.preGateHits == 2,
          reason: '续传 BEGIN 未到达前置闸门',
          tick: const Duration(milliseconds: 5),
          maxTicks: 4000);
      // 续传 BEGIN ACK 的到达时刻：等待者在分发点打戳。
      fakeUs = 4444000;
      channel.releasePre();
      await _pumpUntil(() => channel.postGateHits == 2,
          reason: '续传 BEGIN ACK 分发后未进入后置闸门',
          tick: const Duration(milliseconds: 5),
          maxTicks: 4000);
      // 整个 BEGIN 往返（写结算 + 解析 + 校验）之后的时刻：旧实现在
      // await 返回后立即取时钟，读到的是它。
      fakeUs = 5555000;
      channel.releasePost();
      final ack = await pending;
      expect(ack.isOk, isTrue, reason: '续传后应正常收尾成功');
      // 32 个前缀段在续传确认中首次获得合法终点样本：终点 = 该 ACK 的
      // 到达时刻 − 各自首发结束时刻（首发发生在时钟恒为 1000000 期间）。
      expect(stats.ackLatencySamplesUs, hasLength(32));
      expect(stats.ackLatencySamplesUs.toSet(), {4444000 - 1000000},
          reason: '前缀样本终点必须取续传 BEGIN ACK 的到达时刻');
      expect(stats.ackLatencySamplesUs, isNot(contains(5555000 - 1000000)),
          reason: '往返返回后的时刻不得成为样本终点');
      await transport.dispose();
    }, timeout: const Timeout(Duration(seconds: 60)));
  });
}

/// 构造「上次会话在块 0 提交后中断」的 journal 状态：BEGIN(seq=10) +
/// 块 0 的 32 段 DATA(seq=11..42) → 块收齐提交 journal durable=4096 →
/// ABORT teardown（模拟断线：RAM 层清空，durable/字节保留）。返回后
/// [mcu.stagedDurable] 为 4096，且 MCU 处于 IDLE。
/// 文件级助手看不到 `main()` 作用域内的 [shaOf]/[etuHeaderOf]，BEGIN
/// 载荷必须在这里自算：摘要用真实 SHA-256、头用包前 64B（同 main 内定义）。
Future<void> _prestageCommittedBlock0(_McuSim mcu, Uint8List package) async {
  await mcu.writeChunk(OtaBleCodec.encodeCommand(
    cmd: OtaBleCodec.cmdBegin,
    session: 0,
    seq: 10,
    payload: OtaBleCodec.encodeBeginPayload(
      totalLen: package.length,
      packageSha256: sha256.convert(package).bytes,
      etuHeader: Uint8List.fromList(package.sublist(0, 64)),
    ),
  ));
  for (var i = 0; i < 32; i++) {
    await mcu.writeChunk(OtaBleCodec.encodeCommand(
      cmd: OtaBleCodec.cmdData,
      session: 1,
      seq: 11 + i,
      payload: OtaBleCodec.encodeDataPayload(
          i * 128,
          package.sublist(i * 128, i * 128 + OtaBleCodec.dataSegmentSize)),
    ));
  }
  await mcu.writeChunk(OtaBleCodec.encodeCommand(
    cmd: OtaBleCodec.cmdAbort,
    session: 1,
    seq: 43,
  ));
}

/// 通知流链路错误注入对象（RC3-02/04⑦）：自定义类型便于与产品异常
/// （OtaTransportException/StateError）区分，确认错误原样透传。
class _InjectedNotifyError implements Exception {
  const _InjectedNotifyError();

  @override
  String toString() => '_InjectedNotifyError(injected link failure)';
}

/// 命令帧延迟写窗口扰动的观测结果（RC3-02/04⑦）。
class _WriteWindowOutcome {
  _WriteWindowOutcome(this.callerError, this.zoneErrors);

  /// 调用方（await getDeviceInfo 的一方）最终观测到的错误；null 表示成功。
  final Object? callerError;

  /// 被守护 zone 捕获的未处理异步错误（逃逸判据，期望为空）。
  final List<Object> zoneErrors;
}

/// 物理写闸门通道：writeChunk 一直挂起到 [releaseAll]，用来稳定复现
/// 「等待者已注册、调用方仍卡在 await 物理写」这一窗口（RC3-02/04⑦）。
/// 真实 BLE 的分片写就是这样一个可让出、可长时间未完成的 await 点。
class _GatedWriteChannel implements OtaBleChannel {
  final _notify = StreamController<List<int>>.broadcast();
  final _gates = <Completer<void>>[];

  bool connected = true;
  int mtu = 247;

  /// 仍挂起的写分片数。
  int get pendingWrites => _gates.where((g) => !g.isCompleted).length;

  /// 放行全部挂起的写分片，让调用方继续走到 await waiter.future。
  void releaseAll() {
    for (final gate in _gates) {
      if (!gate.isCompleted) gate.complete();
    }
  }

  /// 注入通知流链路错误（对应真实 GATT 通知订阅 onError）。
  void emitNotifyError(Object error) => _notify.addError(error);

  @override
  Future<void> writeChunk(List<int> chunk) {
    final gate = Completer<void>();
    _gates.add(gate);
    return gate.future;
  }

  @override
  Stream<List<int>> get notifications => _notify.stream;

  @override
  Future<int> maxWriteChunkSize() async => connected ? mtu - 3 : 0;

  @override
  bool get isConnected => connected;

  /// 设备作用域句柄（RC3-05⑤）：本 fake 每次创建即代表一台设备。
  @override
  Object? deviceScope = Object();
}

/// 同一设备的新包装对象（RC3-05⑤）：除自身对象身份外全部转发给
/// [inner]，`deviceScope` 也如实透传，模拟真实路径上「同一台设备、
/// 每次 bind 新建 `_ChannelAdapter`」——包装对象换了，设备没换。
class _ReboundWrapper implements OtaBleChannel {
  _ReboundWrapper(this.inner);

  final OtaBleChannel inner;

  @override
  Object? get deviceScope => inner.deviceScope;

  @override
  Future<void> writeChunk(List<int> chunk) => inner.writeChunk(chunk);

  @override
  Stream<List<int>> get notifications => inner.notifications;

  @override
  Future<int> maxWriteChunkSize() => inner.maxWriteChunkSize();

  @override
  bool get isConnected => inner.isConnected;
}

/// 轮询等待 [condition] 成立：每个 tick 让出事件循环，超时报 [reason]
/// 而不是永远挂住（P34-DA01 闸门用例的同步点）。
///
/// [tick] 默认零延迟——只让出事件循环，适用于纯微任务/同步推进即可到达的
/// 闸门。凡是要等**真实时钟**推进的同步点（重传超时、ABORT + BEGIN 续传），
/// 必须传非零 [tick]：零延迟让出在真实时间上几乎是瞬时的，定时器永远等不到
/// 到期，条件不会成立（用例会以 [reason] 超时报红，不会挂住）。
Future<void> _pumpUntil(bool Function() condition,
    {String reason = '等待条件超时',
    int maxTicks = 400,
    Duration tick = Duration.zero}) async {
  for (var i = 0; i < maxTicks; i++) {
    if (condition()) return;
    await Future<void>.delayed(tick);
  }
  fail(reason);
}

/// 控制帧写闸门的直通通道（P34-DA01 确定性打戳用例）：写原样交给 [inner]
/// （应答照常产生），但在指定 cmd 的第 N 次写入前后各设一道闸门——
/// 前置闸门挂在进入内层之前（内层尚未产生应答），后置闸门挂在内层返回
/// 之后而写 Future 仍未结算（应答已可分发）。两道闸门把「应答到达」与
/// 「写结算」稳定分离，配合注入时钟即可判定终点取的是哪一个时刻。
///
/// 只门控**单分片**控制帧（首片即以同步字开头）：本组用例的 BEGIN/END
/// 帧在 247 字节 MTU 下都是单片，续片不参与门控。
class _FrameGateChannel implements OtaBleChannel {
  _FrameGateChannel(this.inner);

  final OtaBleChannel inner;

  /// 前置闸门：该 cmd 的第 [preGateAt] 次写入在进入内层前挂起。
  int? preGateCmd;
  int preGateAt = 1;
  /// 后置闸门：该 cmd 的第 [postGateAt] 次写入在内层返回后挂起。
  int? postGateCmd;
  int postGateAt = 1;

  final _preGate = Completer<void>();
  final _postGate = Completer<void>();
  int preGateHits = 0;
  int postGateHits = 0;

  void releasePre() {
    if (!_preGate.isCompleted) _preGate.complete();
  }

  void releasePost() {
    if (!_postGate.isCompleted) _postGate.complete();
  }

  int? _frameCmd(List<int> chunk) {
    if (chunk.length >= 3 &&
        chunk[0] == OtaBleCodec.frameSync0 &&
        chunk[1] == OtaBleCodec.frameSync1) {
      return chunk[2];
    }
    return null;
  }

  @override
  Future<void> writeChunk(List<int> chunk) async {
    final cmd = _frameCmd(chunk);
    if (cmd != null && cmd == preGateCmd) {
      preGateHits++;
      if (preGateHits == preGateAt) await _preGate.future;
    }
    await inner.writeChunk(chunk);
    if (cmd != null && cmd == postGateCmd) {
      postGateHits++;
      if (postGateHits == postGateAt) await _postGate.future;
    }
  }

  @override
  Stream<List<int>> get notifications => inner.notifications;

  @override
  Future<int> maxWriteChunkSize() => inner.maxWriteChunkSize();

  @override
  bool get isConnected => inner.isConnected;

  @override
  Object? get deviceScope => inner.deviceScope;
}

/// 在「GET_INFO 等待者已注册、物理写仍挂起」的窗口内执行 [disturb]，
/// 返回调用方观测到的错误与守护 zone 捕获的未处理异步错误。
///
/// transport 与请求都在守护 zone 内创建：等待者 completer 的归属 zone
/// 即该 zone，其未处理错误才会落进 zoneErrors 被计数。搬运结果的
/// [settled] 故意建在 zone 外，且只 complete **值**（把错误当值传出），
/// 因此助手自身不会引入新的未处理错误源。
Future<_WriteWindowOutcome> _runCommandWriteWindowDisturbance(
  void Function(OtaBleTransport transport, _GatedWriteChannel channel) disturb,
) async {
  final channel = _GatedWriteChannel();
  final zoneErrors = <Object>[];
  final settled = Completer<Object?>();
  OtaBleTransport? created;
  runZonedGuarded(() {
    final transport = OtaBleTransport(channel: channel);
    created = transport;
    transport.getDeviceInfo(timeout: const Duration(seconds: 2)).then(
          (_) => settled.complete(null),
          onError: (Object e) => settled.complete(e),
        );
  }, (Object error, StackTrace stack) => zoneErrors.add(error));
  final transport = created!;

  // 等 GET_INFO 走到 writeChunk 并挂在闸门上：此刻等待者已入 _waiters，
  // 调用方尚未 await waiter.future——正是要复现的窗口。
  final deadline = DateTime.now().add(const Duration(seconds: 5));
  while (channel.pendingWrites == 0) {
    if (DateTime.now().isAfter(deadline)) {
      fail('物理写未进入挂起状态，窗口未复现');
    }
    await Future<void>.delayed(const Duration(milliseconds: 5));
  }
  disturb(transport, channel);
  // 错误级联（completeError → 无监听者 → zone 上报）发生在随后的微任务，
  // 先让它跑完再放行物理写，否则窗口被写完成掩盖。
  await Future<void>.delayed(const Duration(milliseconds: 20));
  channel.releaseAll();
  final callerError = await settled.future.timeout(const Duration(seconds: 5));
  // 再给一拍，收集迟到的未处理错误。
  await Future<void>.delayed(const Duration(milliseconds: 50));
  await transport.dispose();
  return _WriteWindowOutcome(callerError, zoneErrors);
}

/// 通知分片粒度。
enum _ChunkMode { ble20, byte }

/// BEGIN ACK payload 组包（§5.6，10B）。
/// 顶层函数（RC3-01③）：static 方法不继承，子类裸调用父类 static
/// 在 Dart 中无法解析，统一移出类供宿主与模拟器共用。
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

/// fake MCU 宿主：分片重组、按 §5 应答（seq 回显、session 语义正确）。
abstract class _FakeMcuHost implements OtaBleChannel {
  final writtenFrames = <Uint8List>[];
  final sentFrames = <OtaBleFrame>[];
  // broadcast（RC3-02 续传用例）：续传语义 = 新连接再 transfer，同一
  // fake 需要支撑第二个 transport listen 同一通知流。单订阅流的
  // stream.map() 包装二次 listen 抛 "Stream has already been listened
  // to"；broadcast 每帧投递给当前全部订阅者，dispose 后的事件丢弃
  // （本 fake 的所有 sendFrame 都由存活 transport 的 writeChunk 触发，
  // 无「先 add 后 listen」依赖）。
  final _notifyController = StreamController<List<int>>.broadcast();
  bool connected = true;
  int mtu = 247;
  final _pending = <int>[];

  /// 本设备的作用域句柄（RC3-05⑤）：默认每台 fake 即一台独立设备。
  /// 用例可把同一对象包进多个包装通道，模拟真实路径上「同一台设备、
  /// 每次 bind 新建 `_ChannelAdapter`」；[reconnect] 只模拟 BLE 重连，
  /// **不更换**该句柄——MCU 侧解析器状态属于设备，重连不复位它。
  @override
  Object? deviceScope = Object();

  /// 模拟真实重连（RC3-05⑤）：BLE 链路重建，**MCU 侧帧解析器状态不变**。
  ///
  /// 真值：悬空半帧保存在 `ota_ble_session_t::demux.parser`，连接事件
  /// 不复位它——`ota_ble_session.c` 的 `session_teardown` 不动
  /// `session->demux`，`ota_ble_demux_init` 只在开机
  /// `ota_ble_session_init` 调用；解析器只在帧被吃完时自复位
  /// （`ota_ble_frame.c` PAYLOAD/CRC 态）。旧实现在这里 `_pending.clear()`，
  /// 等于凭空造出一个「重连即回到同步态」的干净解析器，把未经证明的
  /// 结论固化成用例前提。本方法只推进连接状态，`_pending`/`deviceScope`
  /// 原样保留。
  void reconnect() {
    _linkReconnects++;
  }

  /// 模拟本设备被复位/断电：唯一能清除 MCU 侧解析器状态的事件
  /// （开机 `ota_ble_session_init` → `ota_ble_demux_init`）。
  void powerCycle() {
    _pending.clear();
  }

  /// [reconnect] 调用次数（诊断用：区分「重连过」与「换了设备」）。
  int get linkReconnects => _linkReconnects;
  int _linkReconnects = 0;

  void onBeginFrame(OtaBleFrame f);
  void onDataFrame(OtaBleFrame f);
  void onEndFrame(OtaBleFrame f);
  void onAbortFrame(OtaBleFrame f);

  /// 本 chunk 所属帧的 cmd（判不出返回 null）。transport 按帧切片
  /// （每 chunk 只属于单帧），写入侧无垃圾注入，未完帧剩余 _pending
  /// 恒从 sync 开始：与 chunk 拼接后首个 sync 帧头的 cmd 即所属帧。
  /// chunk 自身以同步字开头即**新帧首片**，直接读自身帧头，不被悬空的
  /// `_pending` 前缀带偏——否则 DATA 半帧在途时，GET_INFO 探针首片会被
  /// 误判成 DATA 续片，卡死/慢写注入落空（RC3-07 黑洞：真实链路里探针写
  /// 卡死在传输层，字节根本到不了 MCU，注入必须在首片就命中）。只有续片
  /// （不以同步字开头）才拼接 `_pending` 恢复所属帧。
  int? _chunkFrameCmd(List<int> chunk) {
    if (chunk.length >= 3 &&
        chunk[0] == OtaBleCodec.frameSync0 &&
        chunk[1] == OtaBleCodec.frameSync1) {
      return chunk[2];
    }
    final head = _pending.isEmpty ? chunk : [..._pending, ...chunk];
    for (var i = 0; i + 2 < head.length; i++) {
      if (head[i] == OtaBleCodec.frameSync0 &&
          head[i + 1] == OtaBleCodec.frameSync1) {
        return head[i + 2];
      }
    }
    return null;
  }

  @override
  Future<void> writeChunk(List<int> chunk) async {
    // RC3-07⑤：慢写与写错误注入只作用于 DATA 帧分片——控制帧
    // （GET_INFO/BEGIN/END/ABORT）不延迟、不注错。若 BEGIN 也延迟，
    // 小 MTU 下 BEGIN 自身 6 片先吃掉预算，用例测不到「DATA 分片
    // 累计超预算」；按 DATA 分片计数注错则不受 BEGIN 片数影响。
    if (_chunkFrameCmd(chunk) == OtaBleCodec.cmdData) {
      dataChunkWrites++;
      writeTimeline.add('start#$dataChunkWrites');
      if (failAtDataChunk == dataChunkWrites) {
        throw StateError('injected GATT write failure');
      }
      if (hangAtDataChunk == dataChunkWrites) {
        // 写通道卡死：永不返回（无定时器，仅悬挂的 future）。
        await Completer<void>().future;
      }
      if (slowDataChunkAt == dataChunkWrites) {
        await Future<void>.delayed(slowDataChunkDelay);
        if (slowDataChunkFails) {
          writeTimeline.add('error#$dataChunkWrites');
          throw StateError('injected late GATT write failure');
        }
      } else if (writeChunkDelay != Duration.zero) {
        await Future<void>.delayed(writeChunkDelay);
      }
      writeTimeline.add('done#$dataChunkWrites');
    } else {
      // 控制帧（GET_INFO/BEGIN/END/ABORT）分片：慢写/卡死注入只按帧 cmd
      // 生效（[hangControlCmd]），默认不延迟不注错（RC3-07⑤：BEGIN 若
      // 延迟，小 MTU 下其自身分片会先吃掉预算，测不到「探针写卡死/慢写
      // 超预算」的目标路径）。
      controlChunkWrites++;
      if (hangControlCmd != null && _chunkFrameCmd(chunk) == hangControlCmd) {
        // 探针写通道卡死：永不返回（无定时器，仅悬挂的 future）。
        await Completer<void>().future;
      } else if (controlWriteDelay != Duration.zero) {
        await Future<void>.delayed(controlWriteDelay);
      }
    }
    _pending.addAll(chunk);
    // 分片写入重组：一次 chunk 可能含多帧或半帧。
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
      // 坏帧语义（ota_ble_frame.c:274-313）：CRC 失败 → 整帧丢弃 +
      // 解析器复位，剩余字节继续按同步字重新扫描，**不**向上抛错——
      // 真实 GATT 写不会因为 MCU 拒帧而失败。截断写留下的悬空帧正是
      // 这样被后续字节喂满后以 ERR_CRC 收场，这一点必须如实模拟，
      // 否则「探针被吞掉再重新同步」的路径在替身上根本走不到。
      final OtaBleFrame f;
      try {
        f = OtaBleCodec.decodeFrame(frame);
      } on FormatException {
        badCrcFrames++;
        continue;
      }
      writtenFrames.add(frame);
      switch (f.cmd) {
        case OtaBleCodec.cmdGetInfo:
          // INFO 帧：session=0、seq 回显请求 seq（§5.6）。
          if (infoResponseDelay != Duration.zero) {
            // 迟到 INFO 注入（RC3-07）：独立定时器延迟投递，不阻塞本写
            // 分片返回——「探针写已完成、应答晚到」是分离事件。应答等待
            // 超时后恢复事务退休，迟到的 INFO 不得再解除设备隔离。
            unawaited(
              Future<void>.delayed(infoResponseDelay)
                  .then((_) => _sendInfoFrame(f)),
            );
          } else {
            _sendInfoFrame(f);
          }
          break;
        case OtaBleCodec.cmdBegin:
          onBeginFrame(f);
          break;
        case OtaBleCodec.cmdData:
          onDataFrame(f);
          break;
        case OtaBleCodec.cmdEnd:
          onEndFrame(f);
          break;
        case OtaBleCodec.cmdAbort:
          onAbortFrame(f);
          break;
        default:
          break;
      }
    }
  }

  /// 回发 GET_INFO 的 INFO 应答（seq 回显请求 seq，§5.6）。
  void _sendInfoFrame(OtaBleFrame f) {
    sendFrame(
      OtaBleCodec.rspInfo,
      0,
      f.seq,
      buildInfoPayload(
        model: DeviceOtaInfo.wireModelETrack,
        hardwareRevision: 3,
        layoutId: 5,
        bootVersion: 2,
        currentVersionCode: 20801,
        imageSha256: fakeDeviceImageSha256,
      ),
    );
  }

  /// 上行应答帧：seq 回显请求 seq，按所选粒度分片回发。
  void sendFrame(int cmd, int session, int seq, List<int> payload) {
    final frame = OtaBleCodec.encodeCommand(
      cmd: cmd,
      session: session,
      seq: seq,
      payload: payload,
    );
    if (garbagePrefixBytes > 0) {
      _notifyController.add(List<int>.filled(garbagePrefixBytes, 0xA5 + 1));
      garbagePrefixBytes = 0;
    }
    _emitToNotify(frame);
    sentFrameBytes.add(frame);
    sentFrames.add(OtaBleCodec.decodeFrame(frame));
  }

  /// 按 [chunkMode] 把一条完整帧投递到通知流（分片粒度与真实链路一致）。
  void _emitToNotify(Uint8List frame) {
    switch (chunkMode) {
      case _ChunkMode.ble20:
        for (var off = 0; off < frame.length; off += 20) {
          final end = (off + 20).clamp(0, frame.length);
          _notifyController.add(frame.sublist(off, end));
        }
        break;
      case _ChunkMode.byte:
        for (var i = 0; i < frame.length; i++) {
          _notifyController.add(frame.sublist(i, i + 1));
        }
        break;
    }
  }

  /// 重放一条此前发出的应答（RC3-05⑤ 反例注入）：把该帧原始字节再次投递
  /// 到通知流，模拟迟到/重复的应答帧。真实链路上通知重放（缓冲重放、重传）
  /// 是可能的，而「重放的旧 INFO 能否解除写通道隔离」正是对应用例的判据。
  void replaySentFrame(int index) {
    _emitToNotify(Uint8List.fromList(sentFrameBytes[index]));
  }

  /// 已发出应答帧的原始字节（[replaySentFrame] 的数据源）。
  final sentFrameBytes = <Uint8List>[];

  /// 测试注入：一次性垃圾前缀字节（非同步字）。
  int garbagePrefixBytes = 0;
  _ChunkMode chunkMode = _ChunkMode.ble20;
  /// 每个写分片的固定延迟（RC3-07：慢写 + 小 MTU 压满 30s 总预算）。
  Duration writeChunkDelay = Duration.zero;
  /// DATA 帧分片写入次数（含被注入失败的那次），供注错定位。
  int dataChunkWrites = 0;
  /// 第 N 个 DATA 分片的底层写报错（1 基，RC3-05⑤）：模拟 GATT 写
  /// 失败在整帧中途中断。半帧成因不止写超时，底层错误同样让 MCU 帧
  /// 解析器悬空在 payload 态，处置必须一致。
  int? failAtDataChunk;
  /// 第 N 个 DATA 分片的底层写**永不返回**（写通道卡死，RC3-07⑤）：
  /// 只能被上层的写超时/预算终止，用来区分「从零时刻起的单次超时」与
  /// 「接近预算耗尽时的写挂起」。
  int? hangAtDataChunk;
  /// 第 N 个 DATA 分片的底层写在 [slowDataChunkDelay] 后才有结果
  /// （RC3-07⑤ 迟到落地）：[slowDataChunkFails] 为 false 时迟到成功
  /// 落地、为 true 时以异常收场。延迟刻意大于 writeTimeout，用于分辨
  /// 「settle 等到迟到结果」与「立即上抛」。
  int? slowDataChunkAt;
  Duration slowDataChunkDelay = Duration.zero;
  bool slowDataChunkFails = false;
  /// 非 DATA 控制帧分片写入次数（RC3-07 黑洞/慢写注入定位用）。控制帧
  /// （GET_INFO/BEGIN/END/ABORT）与 DATA 帧分开计数，避免 BEGIN 分片
  /// 数干扰 DATA 分片注入定位。
  int controlChunkWrites = 0;
  /// 卡死「所属帧 cmd == [hangControlCmd]」的控制帧写入（RC3-07 黑洞）：
  /// 底层写永不返回（仅悬挂的 future），只能被写超时/探针预算终止。按帧
  /// cmd 注入而非计数——同一 fake 上前序传输的 BEGIN/END/ABORT 控制写
  /// 不计入定位，`cmdGetInfo` 即唯一命中探针写。
  int? hangControlCmd;
  /// 每个非 DATA 控制帧分片写入的固定延迟（RC3-07 慢写）：GET_INFO 探针
  /// 等控制帧写被拖慢，用于分辨「探针写完成、应答在恢复事务退休后才到」
  /// 的应答等待封顶路径。
  Duration controlWriteDelay = Duration.zero;
  /// INFO 应答投递延迟（RC3-07 迟到应答）：GET_INFO 帧被解析后用独立
  /// 定时器延迟 [infoResponseDelay] 再 sendFrame(rspInfo)，**不阻塞本写
  /// 分片返回**——「写已完成、应答晚到」是分离事件，模拟探针写成功而
  /// INFO 在恢复事务退休之后才到的真实路径。
  Duration infoResponseDelay = Duration.zero;
  /// 分片写观测时间线（RC3-07⑤）：`start#n` / `done#n` / `error#n`，
  /// 用于断言终止发布与迟到物理写的先后次序。
  final writeTimeline = <String>[];
  /// 通知投递计数（RC3-02 排查遗留）：map 包装层逐事件累加，区分
  /// 「sendFrame 已 emit」与「事件真正投递到 transport 订阅者」。
  int deliveredChunks = 0;

  /// 重组缓冲中尚未组成完整帧的字节数（RC3-05② 断言：取消/中止
  /// 边界处 MCU 不得停留在半帧状态）。
  int get pendingByteCount => _pending.length;

  /// 被 MCU 以 CRC 失败丢弃的整帧数（RC3-05⑤ 重新同步路径的观测点）。
  /// 简化：真值下 MCU 还会回一个 ERR_CRC 的 NAK（`session_handle_frame_error`），
  /// 本替身不发——NAK 与本用例的判据无关，且悬空态下应用本来就在等探针应答。
  int badCrcFrames = 0;

  @override
  Stream<List<int>> get notifications =>
      _notifyController.stream.map((chunk) {
        deliveredChunks++;
        return chunk;
      });

  @override
  Future<int> maxWriteChunkSize() async => connected ? mtu - 3 : 0;

  @override
  bool get isConnected => connected;
}

class _TailLossWithLivenessMcu extends _McuSim {
  _TailLossWithLivenessMcu({
    this.unknownSeq = false,
    this.permanentLoss = false,
  });

  final bool unknownSeq;
  final bool permanentLoss;
  final tailAttempts = <OtaBleFrame>[];
  Timer? _livenessTimer;
  int livenessAcks = 0;

  void stopLiveness() {
    _livenessTimer?.cancel();
    _livenessTimer = null;
  }

  @override
  void onDataFrame(OtaBleFrame frame) {
    final off = ByteData.sublistView(frame.payload).getUint32(0, Endian.little);
    if (off == 8064) {
      tailAttempts.add(frame);
      if (permanentLoss || tailAttempts.length == 1) {
        // Drop DATA before the receiver sees it. Repeat the real preceding
        // ACK faster than ackTimeout, like the MCU's 500 ms liveness path.
        final previous = sentFrames.lastWhere(
            (sent) => sent.cmd == OtaBleCodec.rspAckData);
        _livenessTimer ??= Timer.periodic(const Duration(milliseconds: 25), (_) {
          livenessAcks++;
          sendFrame(OtaBleCodec.rspAckData, previous.session,
              unknownSeq ? 0xffff : previous.seq, previous.payload);
        });
        return;
      }
      stopLiveness();
    }
    super.onDataFrame(frame);
  }
}

/// MCU 语义模拟（Libraries/OTA/ota_ble_session.c 真值）：
/// - seq（§5.1）：delta=0 推进 expected_seq；delta<0 重发帧幂等回当前
///   ACK；delta>0 断档 ERR_SEQ 且不推进、不 teardown；
/// - BEGIN：新会话分配 session_id（非零回绕）、expected_seq=seq+1、
///   staging resume/重建 + 流式 SHA 重建（sha_init + journal durable
///   前缀回填，真值 :449-456 session_digest_resume_prefix）；ACTIVE
///   同 sha 同包长重复 BEGIN 幂等回当前进度（不重置 expected_seq，
///   真值 :377-386）；
/// - DATA：state→session→seq→段校验链→staging 接收（块收齐同步提交
///   durable 并清位图）；新写入段以 wire 数据喂流式 SHA（真值 :571，
///   按接收顺序）；幂等路径（delta<0 / off<durable / DUPLICATE）不喂；
///   同 offset 不同内容 ABORTED+teardown（ERR_DATA）；
/// - END：sha 复述 → durable==total → 内容级流式摘要 final 比对
///   （真值 :646/:655/:664，复述一致但内容不符同样 ERR_SHA）；
/// - ABORT/超时/缺段 teardown：清 RAM 层（段内容 + segment_bitmap +
///   会话 SHA 流，真值 memset receiver），journal durable 与字节保留，
///   重新 BEGIN 同 sha 报 [durable, 0] 并以前缀重建 SHA（跨会话摘要
///   连续，RC3-03）；
/// - ACK bitmap：ACTIVE 报 RAM segment_bitmap，IDLE 恒 0（真值
///   session_progress_bitmap）。
class _McuSim extends _FakeMcuHost {
  // ---- 会话 RAM 层（teardown 清空）----
  static const int _idle = 0;
  static const int _active = 1;
  int _state = _idle;
  int _sessionId = 0;
  int _nextSessionId = 1;
  int _expectedSeq = 0;
  Uint8List _beginSha = Uint8List(0);
  int _totalLen = 0;

  // ---- staging 持久层（teardown 保留 durable，重新 BEGIN 同 sha resume）----
  int _stagedDurable = 0;
  int _stagedBitmap = 0;
  /// journal 落盘字节（真实提交块追加；erase 清零）。长度恒等于
  /// [_stagedDurable]——是流式 SHA resume 前缀的唯一数据源。
  Uint8List _stagedBytes = Uint8List(0);
  /// ACK 报告位图：RAM segment_bitmap（ACTIVE 时与真实层一致；
  /// loseSegmentOff 谎报期间与真实层分离）。
  int _reportBitmap = 0;
  bool _stagedForSha = false;
  /// 会话流式 SHA 字节流（真值增量 SHA 的等价模型）：BEGIN 时重置为
  /// journal durable 前缀，新写入段按接收顺序追加，END 一次性 final。
  final _shaBytes = <int>[];
  /// DATA ACK durable 谎报偏移（loseSegmentOff 块收齐时置位：
  /// ACK 报块尾但 journal durable 不动；teardown 清零）。
  int _lieDurableBy = 0;
  final _segContent = <int, Uint8List>{};

  // ---- 测试注入 ----
  /// BEGIN ACK durable 谎报值（只改 ACK 数值，不动 staging 真实状态；
  /// 测 transport 的越界/伪跳跃 fail closed，RC3-06）。
  int? beginAckDurableOverride;
  /// BEGIN ACK bitmap 谎报值（同上，测越位 fail closed，RC3-06）。
  int? beginAckBitmapOverride;
  /// BEGIN ACK payload session 与帧头不一致（真值两者恒同值；测
  /// transport 帧头/payload 一致性校验，RC3-06）。
  bool beginAckSessionMismatch = false;
  /// DATA ACK durable 一次性伪跳跃增量（8192B 包首块在途时谎报
  /// durable=8192/bitmap=0，测跨窗伪跳跃 fail closed，RC3-06）。
  int? dataAckDurableJump;
  /// END ACK OK 时 bitmap 谎报值（测尾块有效位越界 fail closed，RC3-06）。
  int? endAckBitmapLie;
  /// BEGIN ACK 强制 status（模拟 inspect 阶段拒绝）。
  int? beginAckStatus;
  // Null models a rejected/dropped frame with no ACK, not a valid BEGIN.
  List<int?> beginFailures = [];
  int beginFailurePayloadLength = 10;
  int beginFailureHeaderSession = 0;
  int beginFailurePayloadSession = 0;
  Duration beginFailureDelay = Duration.zero;
  /// DATA ACK 强制 status（模拟会话中故障/终止态）。
  int? dataAckStatus;
  /// END ACK 强制 status（模拟整包校验失败）。
  int? endAckStatus;
  /// END ACK 强制 OK 且 durable 谎报（RC3-06 fail closed：transport
  /// 必须核对 OK 时 durable == total，不得盲信）。
  int? endAckDurableLie;
  /// 第 N 个 DATA ACK 后 MCU 主动 teardown 并异步送 rspAckAbort
  /// ABORTED（RC3-06：模拟会话超时，无请求关联的终止通知）。
  int? sessionAbortAfterDataCount;
  /// 所有 BEGIN 处理照常但不回 ACK（RC3-07：预算耗尽优先于
  /// BEGIN 重试空转；幂等分支同样生效，RC3-03）。
  bool dropAllBeginAcks = false;
  /// 该 offset 段 ACK 位图照常置位但 staging 不落（模拟 flash 静默
  /// 丢失；块收齐时谎报提交，END 校验 durable != total 暴露 → ERR_STATE）。
  int? loseSegmentOff;
  /// 这些序号的 DATA 回 ERR_SEQ（模拟 MCU expected_seq 与发送端失配）。
  /// 每个序号 one-shot（命中即移除），集合允许跨 resume 轮注入多次，用于
  /// 测恢复预算的有限性（RC3-06）。
  Set<int>? errSeqAtDataCounts;
  /// 第一次 BEGIN 处理照常但不回 ACK（模拟上行丢帧）。
  bool dropBeginAckOnce = false;
  /// 这些 offset 的 DATA ACK 丢弃（staging 照常，测位图回收窗口）。
  Set<int>? dropAckForOffsets;
  /// 这些 offset 的第一份 ACK 丢弃（one-shot；RC3-06 跨块回收：块尾段
  /// ACK 丢后靠重发触发的幂等 ACK 携带 durable 前移回收在途窗口）。
  Set<int>? dropAckOnceForOffsets;
  /// 第 N 个 DATA 处理后发一个 seq 不在途的伪造 ACK（RC2-06 忽略）。
  int? strayAckAfterDataCount;
  /// 第 N 个 DATA 的 ACK durable 强制倒退值（RC2-06 fail closed）。
  int? durableRegressAtDataCount;
  bool respondDataAck = true;
  bool duplicateDataAck = false;
  /// 每段 ACK 的延迟（测 credit 窗口上限用）。
  Duration ackDelay = Duration.zero;

  // ---- 观测 ----
  final dataOffsets = <int>[];
  final dataFrames = <OtaBleFrame>[];
  final beginFrames = <OtaBleFrame>[];
  final abortFrames = <OtaBleFrame>[];
  /// 每次 BEGIN ACK 的 [durableOff, blockBitmap]。
  final beginAckStates = <List<int>>[];
  /// 每次 DATA ACK 的 status（RC3-03⑤：fake 门禁负例的观测通道）。
  final dataAckStatuses = <int>[];
  int beginCalls = 0;
  int endCalls = 0;
  int abortCalls = 0;
  /// 当前 journal durable（真实提交层观测；ERR_SHA 整页擦除后归零）。
  int get stagedDurable => _stagedDurable;
  int _inFlight = 0;
  int maxInFlight = 0;
  final _timers = <Timer>[];

  static const int _segmentSize = OtaBleCodec.dataSegmentSize;
  static const int _blockSize =
      OtaBleCodec.segmentsPerBlock * OtaBleCodec.dataSegmentSize;

  void _teardown() {
    // 真值（ota_staging.c：teardown/re-begin 时 memset receiver）：
    // RAM 层（段内容缓冲 + segment_bitmap + 会话增量 SHA）清空，当前
    // 块段进度丢弃；journal durable/字节与 staging 归属保留，重新
    // BEGIN 同 sha 时报 [durable, 0] 并以 journal 前缀重建 SHA
    // （RC3-03：ACK 的 bitmap 恒为 RAM 态，IDLE 报 0）。
    _state = _idle;
    _sessionId = 0;
    _stagedBitmap = 0;
    _reportBitmap = 0;
    _segContent.clear();
    _shaBytes.clear();
    _lieDurableBy = 0;
  }

  void _eraseStaged() {
    _stagedDurable = 0;
    _stagedBitmap = 0;
    _reportBitmap = 0;
    _segContent.clear();
    _shaBytes.clear();
    _stagedBytes = Uint8List(0);
    _stagedForSha = false;
  }

  /// fake 版 ota_sd_inspect_header（RC3-03⑤）：对齐真值 ota_sd.c 检查链
  /// 与 ota_ble_session.c status_for_inspect_error 映射。返回 null 表示
  /// 通过，否则返回 ACK status 码。门禁未接入前，恢复正例读到
  /// target_vcode 后再装同版本仍会"成功"——与 MCU 真值行为相悖。
  int? fakeInspectEtuHeader(Uint8List etu, int totalLen, int currentVcode) {
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
    if (le16(48) != fakeDeviceHardwareRev) {
      return OtaBleCodec.statusErrHwRev;
    }
    if (etu[50] != fakeDeviceLayoutId) return OtaBleCodec.statusErrLayout;
    if (etu[51] > fakeDeviceBootVersion) return OtaBleCodec.statusErrBootVer;
    if (le32(40) <= currentVcode) return OtaBleCodec.statusErrVersion;
    final payloadLen = le32(32);
    if (flags == 0x000B) {
      // full（真值 :316-328）：base_vcode=0 且 base_sha8 全零，否则
      // ERR_BASE；payload_len==0 属长度域，真值返回
      // OTA_SD_ERR_PACKAGE_LENGTH → ERR_LEN，不是 ERR_BASE。
      if (le32(44) != 0 || le32(52) != 0 || le32(56) != 0) {
        return OtaBleCodec.statusErrBase;
      }
      if (payloadLen == 0) return OtaBleCodec.statusErrLen;
    } else {
      // patch（真值 :329-341）：base_vcode 必须等于设备当前版本，
      // base_sha8 必须等于设备 image_sha256 前 8B；两者任一不符
      // ERR_BASE。payload_len 必须严格大于 patch 内层头 40B
      // （ETU_PATCH_INNER_HEADER_SIZE），否则 ERR_LEN。
      if (le32(44) != currentVcode) return OtaBleCodec.statusErrBase;
      for (var i = 0; i < 8; i++) {
        if (etu[52 + i] != fakeDeviceBaseSha8[i]) {
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

  @override
  void onBeginFrame(OtaBleFrame f) {
    beginCalls++;
    beginFrames.add(f);
    final totalLen = f.payload[1] |
        (f.payload[2] << 8) |
        (f.payload[3] << 16) |
        (f.payload[4] << 24);
    final sha = Uint8List.fromList(f.payload.sublist(5, 37));
    final shaMatch = _beginSha.length == 32 && _bytesEqual(_beginSha, sha);
    if (beginAckStatus != null) {
      // inspect 阶段拒绝（真值 :337-368）：session=0，不动现有状态。
      sendFrame(OtaBleCodec.rspAckBegin, 0, f.seq,
          packBeginAck(beginAckStatus!, 0, 0, 0));
      return;
    }
    if (beginFailures.isNotEmpty) {
      final status = beginFailures.removeAt(0);
      if (status != null) {
        void respond() {
          sendFrame(
            OtaBleCodec.rspAckBegin,
            beginFailureHeaderSession,
            f.seq,
            packBeginAck(status, beginFailurePayloadSession, 0, 0)
                .sublist(0, beginFailurePayloadLength),
          );
        }

        if (beginFailureDelay == Duration.zero) {
          respond();
        } else {
          _timers.add(Timer(beginFailureDelay, respond));
        }
      }
      return;
    }
    // ---- BEGIN 门禁（RC3-03⑤，真值 session_handle_begin :331-368）----
    // proto_ver/total_len/inspect 三道门禁全部 session=0 拒绝且不动现有
    // 状态；fake 设备身份 = INFO 应答硬编码值（hardware_rev=3、
    // layout_id=5、boot_version=2、current_vcode=20801）。
    if (f.payload[0] != 1) {
      sendFrame(OtaBleCodec.rspAckBegin, 0, f.seq,
          packBeginAck(OtaBleCodec.statusErrProto, 0, 0, 0));
      return;
    }
    if (totalLen == 0 || totalLen > 0x180000) {
      sendFrame(OtaBleCodec.rspAckBegin, 0, f.seq,
          packBeginAck(OtaBleCodec.statusErrLen, 0, 0, 0));
      return;
    }
    final inspectStatus = fakeInspectEtuHeader(
        Uint8List.fromList(f.payload.sublist(37, 101)), totalLen,
        fakeCurrentVcode);
    if (inspectStatus != null) {
      sendFrame(OtaBleCodec.rspAckBegin, 0, f.seq,
          packBeginAck(inspectStatus, 0, 0, 0));
      return;
    }
    if (_state == _active && _totalLen == totalLen && shaMatch) {
      // 重复 BEGIN（同 sha 同包长）：幂等回当前进度，不重跑 staging、
      // 不重置 expected_seq（真值 :377-386）。丢 ACK 注入在幂等分支
      // 同样生效（RC3-03）：否则 dropAllBeginAcks 的第二次 BEGIN 会被
      // 幂等 ACK 洗成成功，预算耗尽用例失去鉴别力。
      if (!dropBeginAckOnce && !dropAllBeginAcks) {
        sendFrame(OtaBleCodec.rspAckBegin, _sessionId, f.seq,
            packBeginAck(OtaBleCodec.statusOk, _sessionId, _stagedDurable,
                _reportBitmap));
        beginAckStates.add([_stagedDurable, _reportBitmap]);
      } else {
        dropBeginAckOnce = false; // 一次性注入在幂等分支同样消耗。
      }
      return;
    }
    // 新会话分支：不同包先 teardown（真值 :390-393）。
    if (_state == _active) {
      _teardown();
    }
    _beginSha = sha;
    _totalLen = totalLen;
    if (_stagedForSha && shaMatch) {
      // 同 sha resume：保留 journal durable；RAM 层已在 teardown 清空，
      // ACK 报 [durable, 0]（真值 ota_staging_begin memset receiver）。
    } else if (_stagedForSha) {
      // 新 sha：整页重建，清旧包 durable（真值 erase staging）。
      _eraseStaged();
      _stagedForSha = true;
    } else {
      // 首次（无 staging）：干净起点（此前中断留下的 durable 由真实
      // 块提交构造——见「断点续传」用例，不再注入虚假恢复点）。
      _stagedDurable = 0;
      _stagedBitmap = 0;
      _segContent.clear();
      _stagedForSha = true;
    }
    _reportBitmap = _stagedBitmap; // resume 后报告层 = 真实层
    // 流式 SHA 重建（真值 :449-456）：sha_init + journal durable 前缀
    // 回填（session_digest_resume_prefix 从 staging 读回 [0, durable)）。
    _shaBytes..clear()..addAll(_stagedBytes);
    _sessionId = _nextSessionId;
    _nextSessionId = (_nextSessionId + 1) & 0xFF;
    if (_nextSessionId == 0) _nextSessionId = 1;
    _expectedSeq = (f.seq + 1) & 0xFFFF;
    _state = _active;
    if (!dropBeginAckOnce && !dropAllBeginAcks) {
      // 帧头 session 与 payload session 恒同值（真值 session_send_ack_begin）；
      // beginAckSessionMismatch 注入仅在 payload 侧注入异值，测 transport
      // 帧头/payload 一致性校验（RC3-06）。durable/bitmap 谎报注入只改
      // ACK 数值，不动 staging 真实状态。
      final ackSession =
          beginAckSessionMismatch ? (_sessionId ^ 0x5A) & 0xFF : _sessionId;
      sendFrame(
          OtaBleCodec.rspAckBegin,
          _sessionId,
          f.seq,
          packBeginAck(
              OtaBleCodec.statusOk,
              ackSession,
              beginAckDurableOverride ?? _stagedDurable,
              beginAckBitmapOverride ?? _stagedBitmap));
      beginAckStates.add([
        beginAckDurableOverride ?? _stagedDurable,
        beginAckBitmapOverride ?? _stagedBitmap
      ]);
    } else {
      dropBeginAckOnce = false; // 一次性：处理照常，仅 ACK 丢失。
    }
  }

  @override
  void onDataFrame(OtaBleFrame f) {
    dataFrames.add(f);
    final off = f.payload[0] |
        (f.payload[1] << 8) |
        (f.payload[2] << 16) |
        (f.payload[3] << 24);
    dataOffsets.add(off);
    // ERR_SEQ 注入：模拟 MCU expected_seq 与发送端失配（如 MCU 侧重启）。
    final injectErrSeq =
        errSeqAtDataCounts?.contains(dataFrames.length) ?? false;
    if (_state != _active) {
      // teardown 后：session=0 的 ERR_STATE NAK（真值 :491-496）。
      _emitDataAck(OtaBleCodec.statusErrState, f);
      return;
    }
    if (f.session != _sessionId) {
      _emitDataAck(OtaBleCodec.statusErrSession, f);
      return;
    }
    final delta = injectErrSeq
        ? 1 // 强制断档：不推进 expected_seq
        : OtaBleCodec.seqCompare(f.seq, _expectedSeq);
    if (delta > 0) {
      if (injectErrSeq) errSeqAtDataCounts!.remove(dataFrames.length);
      _emitDataAck(OtaBleCodec.statusErrSeq, f);
      return;
    }
    if (delta < 0) {
      // 重发帧（R8-4）：幂等重发当前 ACK，不重写 staging（真值 :511-518）。
      _emitDataAck(OtaBleCodec.statusOk, f);
      return;
    }
    if (injectErrSeq) errSeqAtDataCounts!.remove(dataFrames.length);
    _expectedSeq = (f.seq + 1) & 0xFFFF;

    // ---- 段校验链（真值 :526-548）----
    final dataLen = f.payload.length - 4;
    if (off % _segmentSize != 0) {
      _emitDataAck(OtaBleCodec.statusErrOffset, f);
      return;
    }
    if (dataLen != _segmentSize && off + dataLen != _totalLen) {
      _emitDataAck(OtaBleCodec.statusErrFrame, f);
      return;
    }
    if (off >= _totalLen || off + dataLen > _totalLen) {
      _emitDataAck(OtaBleCodec.statusErrOffset, f);
      return;
    }
    if (off < _stagedDurable) {
      // 已提交 offset 的重复 DATA：幂等 OK（真值 :550-558）。
      _emitDataAck(OtaBleCodec.statusOk, f);
      return;
    }
    // 越当前 4KB 窗（RC3-03⑤，真值 ota_staging_receive :499-503）：
    // durable==total 或 off-durable >= 块长 → ERR_RANGE 映射
    // ERR_OFFSET。缺此门禁时 fake 会照单接收窗口外段，掩盖 transport
    // 侧窗口纪律的真实性。
    if (_stagedDurable == _totalLen || off - _stagedDurable >= _blockSize) {
      _emitDataAck(OtaBleCodec.statusErrOffset, f);
      return;
    }

    // ---- staging 接收 ----
    final content = Uint8List.fromList(f.payload.sublist(4));
    final prior = _segContent[off];
    if (prior != null) {
      if (!_bytesEqual(prior, content)) {
        // 同 offset 不同内容（ERR_DATA）：ABORTED + teardown fail closed。
        _emitDataAck(OtaBleCodec.statusAborted, f);
        _teardown();
        return;
      }
      // DUPLICATE：同段同内容幂等 OK（真值 :576-580）。
      _emitDataAck(OtaBleCodec.statusOk, f);
      return;
    }
    _segContent[off] = content;
    // 新写入段喂流式 SHA（真值 :571）：以 wire 数据按接收顺序喂，
    // 与 journal 落盘成功与否无关（loseSegment 谎报期间照喂——
    // RAM 摘要与 flash 落盘分离，真值同款）。
    _shaBytes.addAll(content);

    final blockStart = (_stagedDurable ~/ _blockSize) * _blockSize;
    final seg = (off - blockStart) ~/ _segmentSize;
    final blockEnd =
        (blockStart + _blockSize) > _totalLen ? _totalLen : blockStart + _blockSize;
    final segsInBlock =
        ((blockEnd - blockStart) + _segmentSize - 1) ~/ _segmentSize;
    _reportBitmap |= 1 << seg;
    if (loseSegmentOff == off) {
      // 一次性注入：该段报告层照常置位但 staging 不落盘（模拟 flash
      // 静默丢失）；块收齐时谎报提交，END 校验 durable 暴露。
      loseSegmentOff = null;
    } else {
      _stagedBitmap |= 1 << seg;
    }
    if (_reportBitmap == (1 << segsInBlock) - 1) {
      // 块收齐（报告层视角）：先组装块字节（RAM 清空前——journal
      // 提交需要完整块内容），再弃置 RAM 段（真值 memset receiver）。
      final blockBytes = <int>[];
      var assembled = true;
      for (var s = 0; s < segsInBlock; s++) {
        final segBytes = _segContent[blockStart + s * _segmentSize];
        if (segBytes == null) {
          assembled = false;
          break;
        }
        blockBytes.addAll(segBytes);
      }
      _reportBitmap = 0;
      _segContent.removeWhere((k, _) => k >= blockStart && k < blockEnd);
      if (assembled && _stagedBitmap == (1 << segsInBlock) - 1) {
        // 真实提交：块收齐同步提交 durable 并清位图（真值 :585-598），
        // journal 追加块字节（流式 SHA 的 resume 前缀数据源）。
        _stagedDurable = blockEnd;
        _stagedBitmap = 0;
        _stagedBytes = Uint8List.fromList([..._stagedBytes, ...blockBytes]);
      } else {
        // 谎报提交：真实层缺段，journal durable 不动；ACK durable
        // 谎报块尾（_lieDurableBy），END 校验时暴露 ERR_STATE。
        _lieDurableBy = blockEnd - _stagedDurable;
        _stagedBitmap = 0;
      }
    }
    _emitDataAck(dataAckStatus ?? OtaBleCodec.statusOk, f);

    // ---- 附加注入（正常 ACK 之后）----
    if (strayAckAfterDataCount == dataFrames.length) {
      strayAckAfterDataCount = null;
      // 伪造 ACK：seq 0x7777 不在任何在途请求上（迟到/错误关联）。
      sendFrame(OtaBleCodec.rspAckData, _sessionId, 0x7777,
          packAck(OtaBleCodec.statusOk, _stagedDurable, _reportBitmap));
      return;
    }
    if (sessionAbortAfterDataCount == dataFrames.length) {
      sessionAbortAfterDataCount = null;
      // MCU 会话超时主动 teardown（真值 :708-715）：异步送 rspAckAbort
      // ABORTED（无请求关联），transport 必须按 terminal 处理。
      sendFrame(OtaBleCodec.rspAckAbort, _sessionId, f.seq,
          packAck(OtaBleCodec.statusAborted, _stagedDurable, _reportBitmap));
      _teardown();
    }
  }

  @override
  void onEndFrame(OtaBleFrame f) {
    endCalls++;
    if (_state != _active) {
      _sendAck(OtaBleCodec.rspAckEnd, OtaBleCodec.statusErrState, f);
      return;
    }
    if (f.session != _sessionId) {
      _sendAck(OtaBleCodec.rspAckEnd, OtaBleCodec.statusErrSession, f);
      return;
    }
    final delta = OtaBleCodec.seqCompare(f.seq, _expectedSeq);
    if (delta > 0) {
      _sendAck(OtaBleCodec.rspAckEnd, OtaBleCodec.statusErrSeq, f);
      return;
    }
    if (delta < 0) {
      // END 重发（seq 落后）：幂等回 OK（真值 :636-642）。
      _sendAck(OtaBleCodec.rspAckEnd, OtaBleCodec.statusOk, f);
      return;
    }
    _expectedSeq = (f.seq + 1) & 0xFFFF;

    if (endAckStatus != null) {
      // 注入的整包校验失败（真值语义：ERR_SHA 擦 staging + teardown）。
      _sendAck(OtaBleCodec.rspAckEnd, endAckStatus!, f);
      if (endAckStatus == OtaBleCodec.statusErrSha) {
        _eraseStaged();
      }
      _teardown();
      return;
    }
    if (endAckDurableLie != null) {
      // 注入：END ACK 强制 OK 但 durable 谎报（RC3-06 fail closed：
      // transport 必须核对 OK 时 durable == total，不得盲信状态字节）。
      _sendAck(OtaBleCodec.rspAckEnd, OtaBleCodec.statusOk, f,
          durableOverride: endAckDurableLie);
      endAckDurableLie = null;
      _teardown();
      return;
    }
    if (f.payload.length != 32 || !_bytesEqual(f.payload, _beginSha)) {
      // sha 复述不符：ERR_SHA + 擦 staging + teardown（真值 :646-653）。
      _sendAck(OtaBleCodec.rspAckEnd, OtaBleCodec.statusErrSha, f);
      _eraseStaged();
      _teardown();
      return;
    }
    if (_stagedDurable != _totalLen) {
      // 缺段：ERR_STATE teardown，发送端重新 BEGIN resume（真值 :655-662）。
      // 谎报偏移只作用于 DATA ACK；END 校验按真实 journal durable 暴露。
      _lieDurableBy = 0;
      _sendAck(OtaBleCodec.rspAckEnd, OtaBleCodec.statusErrState, f);
      _teardown();
      return;
    }
    // 内容级流式摘要 final（真值 :664-668）：sha256(journal durable
    // 前缀 + 顺序新收段) 必须等于 BEGIN 携带的 package_sha256——
    // 复述一致但内容不符（乱序段喂序错乱/漏段/错字节）同样 ERR_SHA。
    final digest = sha256.convert(_shaBytes);
    if (!_bytesEqual(digest.bytes, _beginSha)) {
      _sendAck(OtaBleCodec.rspAckEnd, OtaBleCodec.statusErrSha, f);
      _eraseStaged();
      _teardown();
      return;
    }
    if (endAckBitmapLie != null) {
      // 注入：END ACK OK + durable==total 但 bitmap 谎报越界（RC3-06：
      // transport 必须校验 bitmap 不越出尾块有效位。真值 END OK ACK
      // 在 teardown 前发送，bitmap 是活跃块残留非 0——非 0 合法，越界
      // 不合法）。
      final lie = endAckBitmapLie!;
      endAckBitmapLie = null;
      _sendAck(OtaBleCodec.rspAckEnd, OtaBleCodec.statusOk, f,
          bitmapOverride: lie);
      _teardown();
      return;
    }
    _sendAck(OtaBleCodec.rspAckEnd, OtaBleCodec.statusOk, f);
    _teardown();
  }

  @override
  void onAbortFrame(OtaBleFrame f) {
    abortCalls++;
    abortFrames.add(f);
    if (_state == _active && f.session != _sessionId) {
      // session 不符：不动 durable 状态（真值 :695-702）。
      _sendAck(OtaBleCodec.rspAckAbort, OtaBleCodec.statusErrSession, f);
      return;
    }
    // session 匹配或非 ACTIVE：ACK ABORTED + teardown（durable 保留）。
    _sendAck(OtaBleCodec.rspAckAbort, OtaBleCodec.statusAborted, f);
    _teardown();
  }

  /// DATA ACK 发射（受 respondDataAck/dropAckForOffsets/ackDelay 注入控制）。
  void _emitDataAck(int status, OtaBleFrame f) {
    if (!respondDataAck) return;
    final off = f.payload[0] |
        (f.payload[1] << 8) |
        (f.payload[2] << 16) |
        (f.payload[3] << 24);
    if (dropAckForOffsets?.contains(off) ?? false) return;
    if (dropAckOnceForOffsets?.remove(off) ?? false) return;
    int? durableOverride;
    int? bitmapOverride;
    if (durableRegressAtDataCount == dataFrames.length) {
      durableRegressAtDataCount = null;
      durableOverride = 2048; // 伪造倒退（真值不会倒退）
    } else if (dataAckDurableJump != null) {
      // 一次性伪跳跃（RC3-06）：ACK durable 谎报跨块跳跃增量（如
      // 8192B 包首块在途时直接报 durable=8192），测 transport 的
      // 「相邻 ACK durable 前移至多一个块」fail closed。
      // bitmap 显式置 0（RC3-06⑤）：_bitmapValid(0,·) 恒真，伪跳跃
      // ACK 仅剩 durable 跨窗检查能拒——若沿用 _reportBitmap（非 0），
      // bitmap 越界检查同样会拒，用例绿了也无法区分是哪条谓词拦下。
      durableOverride = _stagedDurable + _lieDurableBy + dataAckDurableJump!;
      bitmapOverride = 0;
      dataAckDurableJump = null;
    }
    // ACK payload 在应答时刻组装快照（RC3-03）：durable/bitmap/session
    // 取当前值，不受延迟窗口内块提交/teardown 的影响。
    dataAckStatuses.add(status);
    final payload = packAck(
        status,
        durableOverride ?? _stagedDurable + _lieDurableBy,
        bitmapOverride ?? (_state == _active ? _reportBitmap : 0));
    final session = _sessionId;

    void emit() {
      sendFrame(OtaBleCodec.rspAckData, session, f.seq, payload);
      if (duplicateDataAck) {
        // 重复 ACK：同 seq 同内容再发一份。
        sendFrame(OtaBleCodec.rspAckData, session, f.seq, payload);
      }
    }

    if (ackDelay == Duration.zero) {
      emit();
    } else {
      _inFlight++;
      if (_inFlight > maxInFlight) maxInFlight = _inFlight;
      _timers.add(Timer(ackDelay, () {
        _inFlight--;
        emit();
      }));
    }
  }

  /// END/ABORT ACK 发射：帧头 session 用当前会话（teardown 后为 0，
  /// 对应 MCU 错误态 NAK 的 session=0 回显）；bitmap 只在 ACTIVE 报
  /// RAM segment_bitmap，IDLE 恒 0（真值 session_progress_bitmap）；
  /// durable 携带 loseSegment 谎报偏移（仅 DATA ACK 语义内）。
  void _sendAck(int rspCmd, int status, OtaBleFrame req,
      {int? durableOverride, int? bitmapOverride}) {
    final durable = durableOverride ?? _stagedDurable + _lieDurableBy;
    sendFrame(rspCmd, _sessionId, req.seq,
        packAck(status, durable, bitmapOverride ?? (_state == _active ? _reportBitmap : 0)));
  }

  static bool _bytesEqual(List<int> a, List<int> b) {
    if (a.length != b.length) return false;
    for (var i = 0; i < a.length; i++) {
      if (a[i] != b[i]) return false;
    }
    return true;
  }
}
