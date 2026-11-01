import 'dart:convert';

import 'package:ble_monitor/ota/ota_p35_android_log.dart';
import 'package:ffi/ffi.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('event emitter preserves exact UTF-8 record and dedicated numeric tag', () {
    const line = 'OTA_P35_STATE {"label":"\u4e2d\u6587","seq":1}';
    var calls = 0;
    emitP35AndroidLog(line, write: (tag, message) {
      calls++;
      expect(tag, p35AndroidEventTag);
      expect(message.toDartString(), line);
      return utf8.encode(line).length + 9;
    });
    expect(calls, 1);
  });

  test('failed, short or fixed-success returns cannot qualify an event write', () {
    for (final result in [0, -1, -11, 1, 18, 9999]) {
      expect(() => emitP35AndroidLog('OTA_P35_CAPTURE {}',
        write: (tag, message) => result), throwsStateError);
    }
  });

  test('invalid or oversized records never enter the native writer', () {
    for (final line in ['unrelated', 'OTA_P35_STATE {}\n',
      'OTA_P35_STATE {}\r', 'OTA_P35_STATE {}\x00',
      'OTA_P35_STATE ${'\u4e2d' * 1200}']) {
      var calls = 0;
      expect(() => emitP35AndroidLog(line, write: (tag, message) {
        calls++;
        return 1;
      }), throwsArgumentError);
      expect(calls, 0);
    }
  });

  test('capture and error prefixes retain their original bytes', () {
    for (final line in ['OTA_P35_CAPTURE {}', 'OTA_P35_ERROR {}']) {
      emitP35AndroidLog(line, write: (tag, message) {
        expect(message.toDartString(), line);
        return utf8.encode(line).length + 9;
      });
    }
  });
}
