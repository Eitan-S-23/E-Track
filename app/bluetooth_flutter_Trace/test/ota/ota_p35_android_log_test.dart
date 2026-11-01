import 'dart:convert';

import 'package:ble_monitor/ota/ota_p35_android_log.dart';
import 'package:ffi/ffi.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('native emitter preserves exact UTF-8 record and Info priority', () {
    const line = 'OTA_P35_STATE {"label":"\u4e2d\u6587","seq":1}';
    var calls = 0;
    emitP35AndroidLog(line, write: (priority, tag, message) {
      calls++;
      expect(priority, 4);
      expect(tag.toDartString(), 'ETrackP35');
      expect(message.toDartString(), line);
      return utf8.encode(line).length;
    });
    expect(calls, 1);
  });

  test('native zero or negative return fails instead of silent fallback', () {
    for (final result in [0, -1, -11]) {
      expect(() => emitP35AndroidLog('OTA_P35_CAPTURE {}',
        write: (_, _, _) => result), throwsStateError);
    }
  });

  test('invalid or oversized records never enter the native writer', () {
    for (final line in ['unrelated', 'OTA_P35_STATE {}\n',
      'OTA_P35_STATE {}\r', 'OTA_P35_STATE {}\x00',
      'OTA_P35_STATE ${'\u4e2d' * 1200}']) {
      var calls = 0;
      expect(() => emitP35AndroidLog(line, write: (_, _, _) {
        calls++;
        return 1;
      }), throwsArgumentError);
      expect(calls, 0);
    }
  });

  test('capture and error prefixes retain their original bytes', () {
    for (final line in ['OTA_P35_CAPTURE {}', 'OTA_P35_ERROR {}']) {
      emitP35AndroidLog(line, write: (_, _, message) {
        expect(message.toDartString(), line);
        return 1;
      });
    }
  });
}
