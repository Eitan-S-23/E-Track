import 'dart:convert';
import 'dart:typed_data';

/// OTA BLE 帧协议 codec（冻结依据 docs/ota-binary-contracts.md §5）。
///
/// 本文件只负责字节级编解码，不持有任何 BLE 连接或状态；
/// schema 唯一来源是二进制合同，禁止在此另立第二套字段定义。
///
/// 帧布局：`A5 5A | u8 cmd | u8 session | u16 seq | u16 len | payload | u16 crc16`
/// crc16 = CRC16-CCITT-FALSE，覆盖 cmd..payload（不含 A5 5A、不含自身），小端存储。
class OtaBleCodec {
  OtaBleCodec._();

  static const int frameSync0 = 0xA5;
  static const int frameSync1 = 0x5A;
  static const int frameHeaderSize = 8; // sync 2 + cmd 1 + session 1 + seq 2 + len 2
  static const int frameCrcSize = 2;

  // 命令表（§5.2）
  static const int cmdGetInfo = 0x00;
  static const int cmdBegin = 0x01;
  static const int cmdData = 0x02;
  static const int cmdEnd = 0x03;
  static const int cmdAbort = 0x04;
  static const int rspInfo = 0x80;
  static const int rspAckBegin = 0x81;
  static const int rspAckData = 0x82;
  static const int rspAckEnd = 0x83;
  static const int rspAckAbort = 0x84;

  // 状态码表（§5.7，唯一来源；未知值 fail closed）
  static const int statusOk = 0x00;
  static const int statusErrFrame = 0x01;
  static const int statusErrCrc = 0x02;
  static const int statusErrSeq = 0x03;
  static const int statusErrSession = 0x04;
  static const int statusErrState = 0x05;
  static const int statusErrOffset = 0x06;
  static const int statusErrLen = 0x07;
  static const int statusErrHdr = 0x08;
  static const int statusErrHwRev = 0x09;
  static const int statusErrLayout = 0x0A;
  static const int statusErrBootVer = 0x0B;
  static const int statusErrVersion = 0x0C;
  static const int statusErrBase = 0x0D;
  static const int statusErrBusy = 0x0E;
  static const int statusErrFlash = 0x0F;
  static const int statusErrSha = 0x10;
  static const int statusErrOtaDisabled = 0x11;
  static const int statusErrProto = 0x12;
  static const int statusAborted = 0xFF;

  /// 已知状态码闭集合；接收端遇到集合外的 status 一律按不可恢复错误处理。
  static const Set<int> knownStatuses = {
    statusOk,
    statusErrFrame,
    statusErrCrc,
    statusErrSeq,
    statusErrSession,
    statusErrState,
    statusErrOffset,
    statusErrLen,
    statusErrHdr,
    statusErrHwRev,
    statusErrLayout,
    statusErrBootVer,
    statusErrVersion,
    statusErrBase,
    statusErrBusy,
    statusErrFlash,
    statusErrSha,
    statusErrOtaDisabled,
    statusErrProto,
    statusAborted,
  };

  /// 发送端收到这些状态码后应当中止会话而不是重试（§5.7 处置列「放弃/中止」类）。
  static const Set<int> abortStatuses = {
    statusErrHwRev,
    statusErrLayout,
    statusErrBootVer,
    statusErrVersion,
    statusErrOtaDisabled,
    statusErrProto,
    statusAborted,
  };

  /// DATA 段净荷恒 128B（仅包尾段可短）。
  static const int dataSegmentSize = 128;
  /// 4KB 块 = 恰 32 段。
  static const int segmentsPerBlock = 32;
  /// credit 窗口 = 当前块。
  static const int creditWindowBlocks = 1;

  /// CRC16-CCITT-FALSE（§0.2：poly 0x1021、初值 0xFFFF、不反射、无最终异或）。
  static int crc16(List<int> bytes, [int start = 0, int? end]) {
    final stop = end ?? bytes.length;
    var crc = 0xFFFF;
    for (var i = start; i < stop; i++) {
      crc ^= bytes[i] << 8;
      for (var bit = 0; bit < 8; bit++) {
        if ((crc & 0x8000) != 0) {
          crc = ((crc << 1) ^ 0x1021) & 0xFFFF;
        } else {
          crc = (crc << 1) & 0xFFFF;
        }
      }
    }
    return crc;
  }

  /// seq 16bit 回绕比较（(int16)(a-b)），返回 a 相对 b 的有符号偏移。
  static int seqCompare(int a, int b) {
    final diff = (a - b) & 0xFFFF;
    if (diff >= 0x8000) return diff - 0x10000;
    return diff;
  }

  /// 组装一帧下行命令（GET_INFO/BEGIN/DATA/END/ABORT）。
  static Uint8List encodeCommand({
    required int cmd,
    required int session,
    required int seq,
    List<int> payload = const [],
  }) {
    if (payload.length > 0xFFFF) {
      throw ArgumentError('payload 超过帧长度上限: ${payload.length}');
    }
    final frame = Uint8List(frameHeaderSize + payload.length + frameCrcSize);
    frame[0] = frameSync0;
    frame[1] = frameSync1;
    frame[2] = cmd;
    frame[3] = session;
    frame[4] = seq & 0xFF;
    frame[5] = (seq >> 8) & 0xFF;
    frame[6] = payload.length & 0xFF;
    frame[7] = (payload.length >> 8) & 0xFF;
    for (var i = 0; i < payload.length; i++) {
      frame[frameHeaderSize + i] = payload[i];
    }
    final crc = crc16(frame, 2, frameHeaderSize + payload.length);
    frame[frame.length - 2] = crc & 0xFF;
    frame[frame.length - 1] = (crc >> 8) & 0xFF;
    return frame;
  }

  /// 解析一帧完整上行响应。字节不完整、CRC 不符或 sync 非法时抛 [FormatException]。
  static OtaBleFrame decodeFrame(List<int> bytes) {
    if (bytes.length < frameHeaderSize + frameCrcSize) {
      throw FormatException('BLE 帧过短: ${bytes.length}');
    }
    if (bytes[0] != frameSync0 || bytes[1] != frameSync1) {
      throw const FormatException('BLE 帧同步字非法');
    }
    final cmd = bytes[2];
    final session = bytes[3];
    final seq = bytes[4] | (bytes[5] << 8);
    final len = bytes[6] | (bytes[7] << 8);
    if (bytes.length != frameHeaderSize + len + frameCrcSize) {
      throw FormatException(
          'BLE 帧长度不符: 期望 ${frameHeaderSize + len + frameCrcSize}，实际 ${bytes.length}');
    }
    final payloadEnd = frameHeaderSize + len;
    final crcExpected = bytes[bytes.length - 2] | (bytes[bytes.length - 1] << 8);
    final crcActual = crc16(bytes, 2, payloadEnd);
    if (crcExpected != crcActual) {
      throw FormatException('BLE 帧 CRC16 失败: 期望 $crcExpected，实际 $crcActual');
    }
    return OtaBleFrame(
      cmd: cmd,
      session: session,
      seq: seq,
      payload: Uint8List.fromList(bytes.sublist(frameHeaderSize, payloadEnd)),
    );
  }

  /// BEGIN payload（§5.3，101B）。
  static Uint8List encodeBeginPayload({
    required int totalLen,
    required List<int> packageSha256,
    required List<int> etuHeader,
  }) {
    if (packageSha256.length != 32) {
      throw ArgumentError('package_sha256 必须为 32 字节');
    }
    if (etuHeader.length != 64) {
      throw ArgumentError('etu_header 必须为 64 字节');
    }
    final payload = Uint8List(101);
    payload[0] = 1; // proto_ver 恒 1
    payload[1] = totalLen & 0xFF;
    payload[2] = (totalLen >> 8) & 0xFF;
    payload[3] = (totalLen >> 16) & 0xFF;
    payload[4] = (totalLen >> 24) & 0xFF;
    payload.setRange(5, 37, packageSha256);
    payload.setRange(37, 101, etuHeader);
    return payload;
  }

  /// END payload：package_sha256 复述（32B）。
  static Uint8List encodeEndPayload(List<int> packageSha256) {
    if (packageSha256.length != 32) {
      throw ArgumentError('package_sha256 必须为 32 字节');
    }
    return Uint8List.fromList(packageSha256);
  }

  /// DATA payload：u32 off LE + data（恒 128B，仅包尾段可短）。
  static Uint8List encodeDataPayload(int offset, List<int> data) {
    if (offset % dataSegmentSize != 0) {
      throw ArgumentError('DATA off 必须按 128 对齐: $offset');
    }
    if (data.isEmpty || data.length > dataSegmentSize) {
      throw ArgumentError('DATA 段净荷必须在 1..128 字节内: ${data.length}');
    }
    final payload = Uint8List(4 + data.length);
    payload[0] = offset & 0xFF;
    payload[1] = (offset >> 8) & 0xFF;
    payload[2] = (offset >> 16) & 0xFF;
    payload[3] = (offset >> 24) & 0xFF;
    payload.setRange(4, payload.length, data);
    return payload;
  }
}

/// 解析后的 BLE 帧。
class OtaBleFrame {
  const OtaBleFrame({
    required this.cmd,
    required this.session,
    required this.seq,
    required this.payload,
  });

  final int cmd;
  final int session;
  final int seq;
  final Uint8List payload;
}

/// INFO payload（§5.2.1，50B 顺序小端）的解析结果。
class OtaInfoPayload {
  OtaInfoPayload._({
    required this.model,
    required this.hardwareRevision,
    required this.layoutId,
    required this.bootVersion,
    required this.currentVersionCode,
    required this.imageSha256,
    required this.protocolVersion,
    required this.maxWindowSegments,
  });

  /// 线端 model 原始 8 字节（ASCIIZ）。
  final Uint8List model;
  final int hardwareRevision;
  final int layoutId;
  final int bootVersion;
  final int currentVersionCode;
  /// 当前镜像完整 raw SHA-256（32B）。
  final Uint8List imageSha256;
  final int protocolVersion;
  final int maxWindowSegments;

  /// model 的 ASCIIZ 字符串（NUL 前的 ASCII）。
  String get modelAscii {
    final end = model.indexOf(0);
    return ascii.decode(end < 0 ? model : model.sublist(0, end));
  }

  /// image_sha256 的 64 位小写 hex 表示（跨系统摘要字符串统一格式）。
  String get imageSha256Hex => modelHexLower(imageSha256);

  /// 解析 INFO payload；长度非 50B、proto_ver 非法即抛 [FormatException]。
  /// 注意：model 合法性与 proto_ver 支持性由调用方按 OTA-XC-DEVICE-MODEL 判定。
  static OtaInfoPayload parse(List<int> payload) {
    if (payload.length != 50) {
      throw FormatException('INFO payload 长度非法: ${payload.length}，期望 50');
    }
    final protoVer = payload[48];
    if (protoVer != 1) {
      throw FormatException('INFO proto_ver 不受支持: $protoVer');
    }
    final maxWindowSegs = payload[49];
    if (maxWindowSegs <= 0) {
      throw FormatException('INFO max_window_segs 非法: $maxWindowSegs');
    }
    return OtaInfoPayload._(
      model: Uint8List.fromList(payload.sublist(0, 8)),
      hardwareRevision: payload[8] | (payload[9] << 8),
      layoutId: payload[10],
      bootVersion: payload[11],
      currentVersionCode: payload[12] |
          (payload[13] << 8) |
          (payload[14] << 16) |
          (payload[15] << 24),
      imageSha256: Uint8List.fromList(payload.sublist(16, 48)),
      protocolVersion: protoVer,
      maxWindowSegments: maxWindowSegs,
    );
  }
}

/// ACK payload（§5.6）的解析结果。
class OtaAckPayload {
  OtaAckPayload._({
    required this.status,
    this.session,
    required this.durableOff,
    required this.blockBitmap,
  });

  final int status;
  /// 仅 BEGIN ACK（0x81）携带，10B；其余 ACK 为 9B 无该字段。
  final int? session;
  final int durableOff;
  final int blockBitmap;

  /// 解析 ACK payload；长度不符或 status 未知即抛 [FormatException]。
  static OtaAckPayload parse(int ackCmd, List<int> payload) {
    final isBeginAck = ackCmd == OtaBleCodec.rspAckBegin;
    final expectedLen = isBeginAck ? 10 : 9;
    if (payload.length != expectedLen) {
      throw FormatException(
          'ACK payload 长度非法: ${payload.length}，期望 $expectedLen');
    }
    final status = payload[0];
    if (!OtaBleCodec.knownStatuses.contains(status)) {
      throw FormatException('未知 ACK 状态码: 0x${status.toRadixString(16)}');
    }
    var index = 1;
    int? session;
    if (isBeginAck) {
      session = payload[1];
      index = 2;
    }
    final durableOff = payload[index] |
        (payload[index + 1] << 8) |
        (payload[index + 2] << 16) |
        (payload[index + 3] << 24);
    final blockBitmap = payload[index + 4] |
        (payload[index + 5] << 8) |
        (payload[index + 6] << 16) |
        (payload[index + 7] << 24);
    return OtaAckPayload._(
      status: status,
      session: session,
      durableOff: durableOff,
      blockBitmap: blockBitmap,
    );
  }
}

/// 字节转 64 位小写 hex（跨系统摘要字符串统一格式）。
String modelHexLower(List<int> bytes) {
  final sb = StringBuffer();
  for (final b in bytes) {
    sb.write(b.toRadixString(16).padLeft(2, '0'));
  }
  return sb.toString();
}
