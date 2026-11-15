import 'dart:convert';
import 'package:flutter_test/flutter_test.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:ble_monitor/companion/companion_protocol.dart';
import 'package:ble_monitor/utils/permission_helper.dart';

void main() {
  final session = 'ab' * 16, offerId = 'cd' * 16, sha = '12' * 32, target = '34' * 32;
  final messages = [
    CompanionMessage('HELLO', session, 0), CompanionMessage('CAPS', session, 0, ['1']),
    CompanionMessage('CHECK', session, 7), CompanionMessage('STATE', session, 7, ['NO_UPDATE']),
    CompanionMessage('OFFER', session, 7, [offerId, '3030028', sha, target, '1']),
    CompanionMessage('SEEN', session, 7, [offerId, sha]),
    CompanionMessage('CHOICE', session, 7, [offerId, '3030028', sha, 'NOW']),
    CompanionMessage('CHOICE', session, 7, [offerId, '3030028', sha, 'LATER']),
  ];
  for (final message in messages) {
    test('round trip ${message.kind} ${message.fields.lastOrNull}', () {
      final line = message.encode();
      expect(line.length, lessThanOrEqualTo(320));
      final parsed = CompanionMessage.parse(ascii.decode(line))!;
      expect((parsed.kind, parsed.session, parsed.request), (message.kind, session, message.request));
      expect(parsed.fields, message.fields);
      final decoder = CompanionDecoder();
      final received = <CompanionMessage>[];
      for (final byte in line) { received.addAll(decoder.add([byte], idleTextAllowed: true)); }
      expect(received, hasLength(1));
      expect(received.single.fields, message.fields);
    });
  }
  test('CRC has the standard CCITT-FALSE check value', () {
    expect(CompanionMessage.checksum(ascii.encode('123456789')), 0x29b1);
  });
  test('corruption, unknown schema, invalid numbers and extra fields fail closed', () {
    final valid = ascii.decode(messages[2].encode());
    for (final malformed in [valid.replaceFirst('CHECK', 'CHACK'), valid.replaceFirst('ETC1', 'ETC2'),
      valid.replaceFirst('|7*', '|07*'), valid + 'junk', '!ETC1|CHECK*0000\n']) {
      expect(CompanionMessage.parse(malformed), isNull);
    }
    for (final invalid in [CompanionMessage('STATE', session, 7, ['SOMETHING_NEW']),
      CompanionMessage('CHECK', session, 0), CompanionMessage('CHECK', session, 0x100000000),
      CompanionMessage('CAPS', session, 0, ['2']), CompanionMessage('HELLO', session.toUpperCase(), 0),
      CompanionMessage('OFFER', session, 7, [offerId, '1', sha, target, 'true']),
      CompanionMessage('CHOICE', session, 7, [offerId, '1', sha, 'AUTO'])]) {
      expect(invalid.valid, isFalse);
      expect(invalid.encode, throwsFormatException);
    }
  });
  test('binary-owner bytes and partial lines cannot fabricate a control message', () {
    final decoder = CompanionDecoder();
    final bytes = messages[2].encode();
    expect(decoder.add(bytes.sublist(0, 9), idleTextAllowed: true), isEmpty);
    expect(decoder.add(bytes, idleTextAllowed: false), isEmpty);
    expect(decoder.add(bytes.sublist(9), idleTextAllowed: true), isEmpty);
    expect(decoder.add(bytes, idleTextAllowed: true), hasLength(1));
    expect(decoder.add([...List.filled(400, 65), 10, ...bytes], idleTextAllowed: true), hasLength(1));
    expect(decoder.add([255, ...bytes], idleTextAllowed: true), isEmpty);
    expect(decoder.add(bytes, idleTextAllowed: true), hasLength(1));
  });
  test('consent binds full package, version, operation, device, generation and expiry', () {
    final now = DateTime.utc(2026, 11, 16);
    CompanionOffer offer() => CompanionOffer(session: session, request: 7, id: offerId,
      address: 'aa:bb', linkGeneration: 4, identity: 'identity', version: 3030028,
      packageSha: sha, targetSha: target, expiresAt: now.add(const Duration(minutes: 5)));
    final current = offer();
    final choice = messages[6];
    expect(current.matches(choice, 'aa:bb', 4, now), isTrue);
    expect(current.matches(choice, 'aa:cc', 4, now), isFalse);
    expect(current.matches(choice, 'aa:bb', 5, now), isFalse);
    expect(current.matches(choice, 'aa:bb', 4, current.expiresAt), isFalse);
    for (final stale in [CompanionMessage('CHOICE', '00' * 16, 7, choice.fields),
      CompanionMessage('CHOICE', session, 8, choice.fields),
      CompanionMessage('CHOICE', session, 7, ['00' * 16, '3030028', sha, 'NOW']),
      CompanionMessage('CHOICE', session, 7, [offerId, '3030029', sha, 'NOW']),
      CompanionMessage('CHOICE', session, 7, [offerId, '3030028', target, 'NOW'])]) {
      expect(current.matches(stale, 'aa:bb', 4, now), isFalse);
    }
    current.consumed = true;
    expect(current.matches(choice, 'aa:bb', 4, now), isFalse);
  });
  test('permission groups are SDK specific and never request background location', () {
    expect(PermissionHelper.bluetoothPermissionsFor(22), isEmpty);
    for (final sdk in [23, 29, 30]) {
      expect(PermissionHelper.bluetoothPermissionsFor(sdk), [Permission.locationWhenInUse]);
    }
    for (final sdk in [31, 33, 35, 36]) {
      expect(PermissionHelper.bluetoothPermissionsFor(sdk), [Permission.bluetoothScan, Permission.bluetoothConnect]);
    }
  });
}
