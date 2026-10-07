import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:ble_monitor/ota/ota_pipeline_window.dart';

Uint8List ack(int epoch, int durable, int accepted, int credit) {
  final data = ByteData(16);
  for (final entry in [epoch, durable, accepted, credit].asMap().entries) {
    data.setUint32(entry.key * 4, entry.value, Endian.little);
  }
  return data.buffer.asUint8List();
}

void main() {
  test('send crosses a block boundary before durable advances', () {
    final window = OtaPipelineWindow(epoch: 123, totalBytes: 12288, durableOffset: 0);
    final sent = <int>[];
    while (window.submittedOffset < 8192) {
      final batch = window.reserve();
      expect(batch, isNotEmpty);
      sent.addAll(batch);
      window.acknowledge(ack(123, 0, window.submittedOffset, 8192));
    }
    expect(sent, [for (var off = 0; off < 8192; off += 128) off]);
    expect(window.durableOffset, 0);
    expect(window.reserve(), isEmpty);
    expect(window.complete, isFalse);
    window.acknowledge(ack(123, 4096, 8192, 12288));
    expect(window.reserve().first, 8192);
  });

  test('physical in-flight cap is 24 even with two-block credit', () {
    final window = OtaPipelineWindow(epoch: 123, totalBytes: 12288, durableOffset: 0);
    expect(window.reserve(maxSegments: 24).length, 24);
    expect(window.reserve(), isEmpty);
    expect(window.retryOffsets(maxSegments: 24).length, 24);
    final submitted = window.submittedOffset;
    window.acknowledge(ack(123, 0, 128, 8192));
    expect(window.reserve(), [submitted]);
  });

  test('stale epochs and coherent delayed ACKs cannot change credit', () {
    final window = OtaPipelineWindow(epoch: 123, totalBytes: 12288, durableOffset: 0);
    window.reserve();
    expect(window.acknowledge(ack(122, 0, 128, 8192)), isFalse);
    expect(window.acceptedOffset, 0);
    window.acknowledge(ack(123, 0, 1024, 8192));
    expect(window.acknowledge(ack(123, 0, 512, 8192)), isFalse);
    expect(window.acceptedOffset, 1024);
  });

  test('bad ACK is fail-closed, not best-effort credit', () {
    for (final payload in [
      ack(123, 1, 128, 8193),
      ack(123, 0, 128, 12288),
      ack(123, 0, 129, 8192),
      ack(123, 4096, 128, 12288),
      ack(123, 0, 8192, 8192),
      Uint8List(15),
    ]) {
      final window = OtaPipelineWindow(epoch: 123, totalBytes: 12288, durableOffset: 0);
      window.reserve();
      expect(() => window.acknowledge(payload), throwsFormatException);
      expect(window.active, isFalse);
      expect(() => window.reserve(), throwsStateError);
    }
  });

  test('resume starts from durable only and handles a short final segment', () {
    final window = OtaPipelineWindow(epoch: 124, totalBytes: 4096 + 17, durableOffset: 4096);
    expect(window.reserve(), [4096]);
    expect(window.submittedOffset, 4113);
    window.acknowledge(ack(124, 4096, 4113, 4113));
    expect(window.complete, isFalse);
    window.acknowledge(ack(124, 4113, 4113, 4113));
    expect(window.complete, isTrue);
    expect(window.retryOffsets(), isEmpty);
    window.cancel();
    expect(window.complete, isFalse);
    expect(window.acknowledge(ack(124, 4113, 4113, 4113)), isFalse);
  });

  test('invalid constructor does not manufacture a resumable prefix', () {
    expect(() => OtaPipelineWindow(epoch: 0, totalBytes: 8192, durableOffset: 0), throwsArgumentError);
    expect(() => OtaPipelineWindow(epoch: 1, totalBytes: 8192, durableOffset: 128), throwsArgumentError);
    expect(() => OtaPipelineWindow(epoch: 1, totalBytes: 8192, durableOffset: 0, maxInFlightSegments: 32), throwsArgumentError);
  });

  test('capability and ACK payload vectors agree with C', () {
    final caps = Uint8List.fromList([80, 50, 66, 76, 2, 2, 128, 0, 123, 0, 0, 0, 24, 0, 0, 0]);
    expect(OtaPipelineWindow.acceptsCapabilities(caps, 123), isTrue);
    expect(OtaPipelineWindow.acceptsCapabilities(caps, 124), isFalse);
    for (var i = 0; i < caps.length; i++) {
      final changed = Uint8List.fromList(caps);
      changed[i] ^= 1;
      expect(OtaPipelineWindow.acceptsCapabilities(changed, 123), isFalse);
    }
    expect(OtaPipelineWindow.acceptsCapabilities(Uint8List(15), 123), isFalse);
    expect(ack(123, 0, 8192, 8192), [123, 0, 0, 0, 0, 0, 0, 0, 0, 32, 0, 0, 0, 32, 0, 0]);
  });
}
