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
        cmd: OtaBleCodec.cmdData,
        session: 7,
        seq: 0x1234,
        payload: List<int>.generate(16, (i) => i),
      );
      final decoded = OtaBleCodec.decodeFrame(frame);
      expect(decoded.cmd, OtaBleCodec.cmdData);
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
    test('BEGIN payload：101B、proto_ver=1、字段位置', () {
      final sha = List<int>.generate(32, (i) => i);
      final etu = List<int>.generate(64, (i) => 0x40 + (i & 0x3F));
      final payload = OtaBleCodec.encodeBeginPayload(
        totalLen: 0x12345678,
        packageSha256: sha,
        etuHeader: etu,
      );
      expect(payload.length, 101);
      expect(payload[0], 1);
      expect(
        payload.sublist(1, 5),
        [0x78, 0x56, 0x34, 0x12], // 小端
      );
      expect(payload.sublist(5, 37), sha);
      expect(payload.sublist(37, 101), etu);
    });

    test('BEGIN payload：sha/etu 长度非法必须拒绝', () {
      expect(
        () => OtaBleCodec.encodeBeginPayload(
          totalLen: 1,
          packageSha256: List<int>.filled(31, 0),
          etuHeader: List<int>.filled(64, 0),
        ),
        throwsArgumentError,
      );
      expect(
        () => OtaBleCodec.encodeBeginPayload(
          totalLen: 1,
          packageSha256: List<int>.filled(32, 0),
          etuHeader: List<int>.filled(63, 0),
        ),
        throwsArgumentError,
      );
    });

    test('DATA payload：off 对齐与 128B 约束', () {
      final ok = OtaBleCodec.encodeDataPayload(
        256,
        List<int>.filled(128, 1),
      );
      expect(ok.length, 132);
      expect(ok.sublist(0, 4), [0x00, 0x01, 0x00, 0x00]);
      expect(
        () => OtaBleCodec.encodeDataPayload(129, List<int>.filled(128, 1)),
        throwsArgumentError,
      );
      expect(
        () => OtaBleCodec.encodeDataPayload(0, List<int>.filled(129, 1)),
        throwsArgumentError,
      );
      expect(
        () => OtaBleCodec.encodeDataPayload(0, <int>[]),
        throwsArgumentError,
      );
    });

    test('END payload：32B sha 复述', () {
      final sha = List<int>.generate(32, (i) => 0xFF - i);
      expect(OtaBleCodec.encodeEndPayload(sha), sha);
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

  group('OtaAckPayload.parse', () {
    test('BEGIN ACK 10B：status/session/durable/bitmap', () {
      final payload = <int>[
        0x00, 0x07, 0x10, 0x00, 0x00, 0x00, 0xFF, 0x00, 0x00, 0x00,
      ];
      final ack = OtaAckPayload.parse(OtaBleCodec.rspAckBegin, payload);
      expect(ack.status, 0x00);
      expect(ack.session, 7);
      expect(ack.durableOff, 16);
      expect(ack.blockBitmap, 0xFF);
    });

    test('普通 ACK 9B：无 session 字段（status+durable4B LE+bitmap4B LE）', () {
      final payload = <int>[
        0x00, 0x00, 0x00, 0x40, 0x00, 0x0F, 0x00, 0x00, 0x00,
      ];
      final ack = OtaAckPayload.parse(OtaBleCodec.rspAckData, payload);
      expect(ack.session, isNull);
      // durable = payload[1..5) = 00 00 40 00 (LE) = 0x400000。
      expect(ack.durableOff, 0x400000);
      // bitmap = payload[5..9) = 0F 00 00 00 (LE) = 0x0F。
      expect(ack.blockBitmap, 0x0F);
    });

    test('未知 status 必须拒绝（fail closed）', () {
      final payload = <int>[0x7F, 0, 0, 0, 0, 0, 0, 0, 0];
      expect(
        () => OtaAckPayload.parse(OtaBleCodec.rspAckData, payload),
        throwsFormatException,
      );
    });

    test('长度不符必须拒绝', () {
      expect(
        () => OtaAckPayload.parse(OtaBleCodec.rspAckBegin,
            List<int>.filled(9, 0)),
        throwsFormatException,
      );
      expect(
        () => OtaAckPayload.parse(OtaBleCodec.rspAckData,
            List<int>.filled(10, 0)),
        throwsFormatException,
      );
    });
  });

  group('modelHexLower', () {
    test('小写 hex 输出', () {
      expect(modelHexLower([0x0A, 0xBC, 0xDE, 0xF0]), '0abcdef0');
    });
  });
}
