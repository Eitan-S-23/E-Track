import 'dart:async';
import 'dart:typed_data';

import 'package:crypto/crypto.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:ble_monitor/ota/ota_ble_codec.dart';
import 'package:ble_monitor/ota/ota_ble_transport.dart';
import 'package:ble_monitor/ota/ota_device_info.dart';

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
      // 截断证据：142B DATA 帧已送达 7 片 × 20B = 140B、尾片 2B 未发，
      // 超时后有界 settle 等到片 7 迟到落地再抛出，_pending 恰滞留
      // 140B 半帧（无后续帧字节混入）。
      expect(mcu.pendingByteCount, 140);
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

    test('迟到写不污染后来的会话：同一通道换 transport 仍拒写，新通道'
        '恢复正常（RC3-05⑤）', () async {
      final package = packageBytes(4096);
      final mcu = _McuSim()
        ..mtu = 23
        ..failAtDataChunk = 3;
      final first = OtaBleTransport(channel: mcu);
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
      expect(mcu.pendingByteCount, 40);

      // 「新 transport」不等于「新物理连接」：同一通道对象上重建实例，
      // MCU 侧那半帧仍悬空，任何新帧都会被吞进 payload。有界等待只保证
      // 本帧不与自己的迟到分片交错，并没有取消底层写，因此废弃标记的
      // 作用域必须是物理写通道对象——实例级标记会在这里放行。
      final rebound = OtaBleTransport(channel: mcu);
      try {
        await rebound.getDeviceInfo(
            timeout: const Duration(milliseconds: 300));
        fail('同一通道重建实例应仍被拒绝');
      } on OtaTransportException catch (e) {
        expect(e.code, 'WRITE_TIMEOUT');
      }
      // GET_INFO 一个字节都没写出去（10B 帧放行则 pending 变 50）。
      expect(mcu.pendingByteCount, 40);
      await rebound.dispose();

      // 真实重连 = 新的物理通道对象（OtaService 每次 bind 新建
      // _ChannelAdapter）：不受旧通道废弃标记影响，恢复预算保持有界，
      // 不会因一次半帧把设备永久锁死。
      final reconnected = _McuSim();
      final fresh = OtaBleTransport(channel: reconnected);
      final info = await fresh.getDeviceInfo();
      expect(info.deviceModel, 'e-track-at32f435');
      expect(info.hardwareRevision, 3);
      await fresh.dispose();
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

  void onBeginFrame(OtaBleFrame f);
  void onDataFrame(OtaBleFrame f);
  void onEndFrame(OtaBleFrame f);
  void onAbortFrame(OtaBleFrame f);

  /// 本 chunk 所属帧的 cmd（判不出返回 null）。transport 按帧切片
  /// （每 chunk 只属于单帧），写入侧无垃圾注入，未完帧剩余 _pending
  /// 恒从 sync 开始：与 chunk 拼接后首个 sync 帧头的 cmd 即所属帧。
  int? _chunkFrameCmd(List<int> chunk) {
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
      if (failAtDataChunk == dataChunkWrites) {
        throw StateError('injected GATT write failure');
      }
      if (writeChunkDelay != Duration.zero) {
        await Future<void>.delayed(writeChunkDelay);
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
      writtenFrames.add(frame);
      final f = OtaBleCodec.decodeFrame(frame);
      switch (f.cmd) {
        case OtaBleCodec.cmdGetInfo:
          // INFO 帧：session=0、seq 回显请求 seq（§5.6）。
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
    sentFrames.add(OtaBleCodec.decodeFrame(frame));
  }

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
  /// 通知投递计数（RC3-02 排查遗留）：map 包装层逐事件累加，区分
  /// 「sendFrame 已 emit」与「事件真正投递到 transport 订阅者」。
  int deliveredChunks = 0;

  /// 重组缓冲中尚未组成完整帧的字节数（RC3-05② 断言：取消/中止
  /// 边界处 MCU 不得停留在半帧状态）。
  int get pendingByteCount => _pending.length;

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
