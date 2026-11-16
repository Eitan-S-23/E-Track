import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';

import 'package:ble_monitor/ota/ota_ble_codec.dart';
import 'package:ble_monitor/ota/ota_device_info.dart';

/// CRC16-CCITT-FALSE 参考向量自校验（实现不抄常数，必须能复算公开向量）。
void main() {
  group('OtaBleCodec.crc16（CRC16-CCITT-FALSE）', () {
    test('空输入 = 0xFFFF（初值）', () {
      expect(OtaBleCodec.crc16(<int>[]), 0xFFFF);
    });

    test('公开向量 "123456789" = 0x29B1', () {
      final bytes = '123456789'.codeUnits;
      expect(OtaBleCodec.crc16(bytes), 0x29B1);
    });

    test('单字节 0x00 序列稳定', () {
      // CRC16-CCITT-FALSE of 4 zero bytes（独立复算 0x84C0）。
      expect(OtaBleCodec.crc16([0, 0, 0, 0]), 0x84C0);
    });
  });

  group('OtaBleCodec.seqCompare（16bit 回绕）', () {
    test('普通差', () {
      expect(OtaBleCodec.seqCompare(10, 5), 5);
      expect(OtaBleCodec.seqCompare(5, 10), -5);
    });

    test('回绕：0 与 0xFFFF 相差 1', () {
      expect(OtaBleCodec.seqCompare(0, 0xFFFF), 1);
      expect(OtaBleCodec.seqCompare(0xFFFF, 0), -1);
    });
  });

  group('OtaBleCodec.encodeCommand / decodeFrame', () {
    test('编解码往返：字段与 CRC 一致', () {
      final frame = OtaBleCodec.encodeCommand(
        cmd: OtaBleCodec.cmdData2,
        session: 7,
        seq: 0x1234,
        payload: List<int>.generate(16, (i) => i),
      );
      final decoded = OtaBleCodec.decodeFrame(frame);
      expect(decoded.cmd, OtaBleCodec.cmdData2);
      expect(decoded.session, 7);
      expect(decoded.seq, 0x1234);
      expect(decoded.payload, List<int>.generate(16, (i) => i));
    });

    test('CRC 损坏必须拒绝', () {
      final frame = OtaBleCodec.encodeCommand(
        cmd: OtaBleCodec.cmdGetInfo,
        session: 0,
        seq: 1,
      );
      frame[4] ^= 0x01; // 破坏 seq（CRC 覆盖域内）
      expect(() => OtaBleCodec.decodeFrame(frame), throwsFormatException);
    });

    test('sync 字非法必须拒绝', () {
      final frame = OtaBleCodec.encodeCommand(
        cmd: OtaBleCodec.cmdGetInfo,
        session: 0,
        seq: 1,
      );
      frame[0] = 0x00;
      expect(() => OtaBleCodec.decodeFrame(frame), throwsFormatException);
    });

    test('长度不符必须拒绝', () {
      final frame = OtaBleCodec.encodeCommand(
        cmd: OtaBleCodec.cmdGetInfo,
        session: 0,
        seq: 1,
        payload: List<int>.filled(4, 0xAB),
      );
      final truncated = frame.sublist(0, frame.length - 1);
      expect(() => OtaBleCodec.decodeFrame(truncated), throwsFormatException);
    });
  });

  group('OtaBleCodec payload 编码', () {
    test('BEGIN2 payload: 105 bytes, protocol 2 and epoch', () {
      final sha = List<int>.generate(32, (i) => i);
      final etu = List<int>.generate(64, (i) => 0x40 + (i & 0x3F));
      final payload = OtaBleCodec.encodeBegin2Payload(
          epoch: 0x12345678,
        totalLen: 0x123456,
        packageSha256: sha,
        etuHeader: etu,
      );
      expect(payload.length, 105);
      expect(payload.sublist(101), [0x78, 0x56, 0x34, 0x12]);
      expect(payload[0], 2);
      expect(
        payload.sublist(1, 5),
        [0x56, 0x34, 0x12, 0x00], // Little-endian length.
      );
      expect(payload.sublist(5, 37), sha);
      expect(payload.sublist(37, 101), etu);
    });

    test('BEGIN payload：sha/etu 长度非法必须拒绝', () {
      expect(
        () => OtaBleCodec.encodeBegin2Payload(
          epoch: 0x12345678,
          totalLen: 1,
          packageSha256: List<int>.filled(31, 0),
          etuHeader: List<int>.filled(64, 0),
        ),
        throwsArgumentError,
      );
      expect(
        () => OtaBleCodec.encodeBegin2Payload(
          epoch: 0x12345678,
          totalLen: 1,
          packageSha256: List<int>.filled(32, 0),
          etuHeader: List<int>.filled(63, 0),
        ),
        throwsArgumentError,
      );
    });

    test('DATA payload：off 对齐与 128B 约束', () {
      final ok = OtaBleCodec.encodeData2Payload(7,
        256,
        List<int>.filled(128, 1),
      );
      expect(ok.length, 136);
      expect(ok.sublist(0, 4), [7, 0, 0, 0]);
      expect(ok.sublist(4, 8), [0x00, 0x01, 0x00, 0x00]);
      expect(
        () => OtaBleCodec.encodeData2Payload(7, 129, List<int>.filled(128, 1)),
        throwsArgumentError,
      );
      expect(
        () => OtaBleCodec.encodeData2Payload(7, 0, List<int>.filled(129, 1)),
        throwsArgumentError,
      );
      expect(
        () => OtaBleCodec.encodeData2Payload(7, 0, <int>[]),
        throwsArgumentError,
      );
    });

    test('END payload：32B sha 复述', () {
      final sha = List<int>.generate(32, (i) => 0xFF - i);
      expect(OtaBleCodec.encodeEnd2Payload(7, sha), [7, 0, 0, 0, ...sha]);
    });
  });

  group('OtaInfoPayload.parse', () {
    Uint8List infoPayload({
      List<int> model = DeviceOtaInfo.wireModelETrack,
      int hwRev = 3,
      int layoutId = 5,
      int bootVer = 2,
      int vcode = 20801,
    }) {
      return buildInfoPayload(
        model: model,
        hardwareRevision: hwRev,
        layoutId: layoutId,
        bootVersion: bootVer,
        currentVersionCode: vcode,
        imageSha256: List<int>.generate(32, (i) => i * 3),
      );
    }

    test('合法 50B：字段逐位正确', () {
      final info = OtaInfoPayload.parse(infoPayload());
      expect(info.modelAscii, 'E-Track');
      expect(info.hardwareRevision, 3);
      expect(info.layoutId, 5);
      expect(info.bootVersion, 2);
      expect(info.currentVersionCode, 20801);
      expect(info.imageSha256, List<int>.generate(32, (i) => i * 3));
      expect(info.protocolVersion, 1);
      expect(info.maxWindowSegments, 32);
    });

    test('长度非 50B 必须拒绝', () {
      expect(
        () => OtaInfoPayload.parse(List<int>.filled(49, 0)),
        throwsFormatException,
      );
    });

    test('proto_ver != 1 必须拒绝', () {
      final raw = infoPayload();
      raw[48] = 2;
      expect(() => OtaInfoPayload.parse(raw), throwsFormatException);
    });

    test('max_window_segs = 0 必须拒绝', () {
      final raw = infoPayload();
      raw[49] = 0;
      expect(() => OtaInfoPayload.parse(raw), throwsFormatException);
    });
  });

  group('V2 ACK payloads', () {
    List<int> body(int cmd, {int status = 0}) {
      final base = cmd == OtaBleCodec.rspAckBegin2 ? 2 : 1;
      final bytes = ByteData(base + 16)..setUint8(0, status);
      if (base == 2) bytes.setUint8(1, 7);
      bytes.setUint32(base, 0x12345678, Endian.little);
      bytes.setUint32(base + 4, 4096, Endian.little);
      bytes.setUint32(base + 8, 4224, Endian.little);
      bytes.setUint32(base + 12, 12288, Endian.little);
      return bytes.buffer.asUint8List();
    }

    for (final cmd in [0x91, 0x92, 0x93, 0x94]) {
      test('command $cmd decodes epoch, durable, accepted and credit', () {
        final ack = OtaAckPayload.parse(cmd, body(cmd));
        expect(ack.status, 0);
        expect(ack.session, cmd == 0x91 ? 7 : isNull);
        expect(ack.epoch, 0x12345678);
        expect(ack.durableOff, 4096);
        expect(ack.acceptedOff, 4224);
        expect(ack.creditEnd, 12288);
      });
      test('command $cmd rejects unknown status and malformed length', () {
        expect(() => OtaAckPayload.parse(cmd, body(cmd, status: 0x7f)),
            throwsFormatException);
        expect(() => OtaAckPayload.parse(cmd, body(cmd).sublist(1)),
            throwsFormatException);
        expect(() => OtaAckPayload.parse(cmd, [...body(cmd), 0]),
            throwsFormatException);
      });
    }
    test('legacy response IDs never parse as V2', () {
      for (final cmd in [0x81, 0x82, 0x83, 0x84]) {
        expect(() => OtaAckPayload.parse(cmd, body(0x92)), throwsFormatException);
      }
    });
    test('invalid epochs and lengths fail before encoding', () {
      for (final epoch in [-1, 0, 0x100000000]) {
        expect(() => OtaBleCodec.encodeEpoch(epoch), throwsArgumentError);
      }
      for (final length in [0, -1, 0x180001]) {
        expect(() => OtaBleCodec.encodeBegin2Payload(totalLen: length, epoch: 7,
            packageSha256: List.filled(32, 0), etuHeader: List.filled(64, 0)),
            throwsArgumentError);
      }
    });
  });

  group('modelHexLower', () {
    test('小写 hex 输出', () {
      expect(modelHexLower([0x0A, 0xBC, 0xDE, 0xF0]), '0abcdef0');
    });
  });
}
