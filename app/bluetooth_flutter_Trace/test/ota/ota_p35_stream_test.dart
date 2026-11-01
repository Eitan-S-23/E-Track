import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:ble_monitor/ota/ota_p35_stream.dart';
import 'package:crypto/crypto.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('loopback batches wait for exact host hash ACK and cannot reopen', () async {
    final stream = OtaP35Stream(port: 0);
    await stream.open();
    final peer = await Socket.connect(InternetAddress.loopbackIPv4, stream.boundPort);
    final pending = <int>[];
    final received = <List<int>>[];
    final listener = peer.listen((data) {
      pending.addAll(data);
      while (pending.length >= 4) {
        final length = ByteData.sublistView(Uint8List.fromList(pending),0,4).getUint32(0);
        if (pending.length < length+4) break;
        final bytes = pending.sublist(4,length+4);
        pending.removeRange(0,length+4);
        received.add(bytes);
        peer.add(ascii.encode('ACK $length ${sha256.convert(bytes)}\n'));
      }
    });
    try {
      for (var i=0; i<300; i++) { await stream.send(utf8.encode('batch $i\n' * 20)); }
      expect(received, hasLength(300));
      expect(utf8.decode(received.last), 'batch 299\n' * 20);
      await expectLater(stream.open(), throwsStateError);
    } finally {
      await stream.close();
      await listener.cancel();
      peer.destroy();
    }
  });

  test('missing, mismatched and unsolicited ACK latch failure without retry', () async {
    for (final mode in ['missing','mismatch','unsolicited']) {
      final stream = OtaP35Stream(port: 0, ackTimeout: const Duration(milliseconds: 50));
      await stream.open();
      final peer = await Socket.connect(InternetAddress.loopbackIPv4, stream.boundPort);
      final listener = peer.listen((_) {
        if (mode == 'mismatch') peer.add(ascii.encode('ACK 4 wrong\n'));
      });
      try {
        if (mode == 'unsolicited') {
          peer.add(ascii.encode('ACK 4 wrong\n'));
          await Future<void>.delayed(const Duration(milliseconds: 20));
        }
        await expectLater(stream.send(utf8.encode('body')),
          throwsA(anyOf(isA<StateError>(), isA<TimeoutException>())), reason: mode);
        await expectLater(stream.send(utf8.encode('again')), throwsStateError);
      } finally {
        await stream.close();
        await listener.cancel();
        peer.destroy();
      }
    }
  });
}
