import 'dart:convert';

/// Additive idle-text control plane. Binary OTA framing/ACK semantics are unchanged.
class CompanionMessage {
  const CompanionMessage(this.kind, this.session, this.request, [this.fields = const []]);

  final String kind;
  final String session;
  final int request;
  final List<String> fields;
  static const maxLength = 320;
  static final _hex32 = RegExp(r'^[0-9a-f]{32}$');
  static final _sha = RegExp(r'^[0-9a-f]{64}$');
  static final _number = RegExp(r'^(0|[1-9][0-9]{0,9})$');
  static const states = {'CHECKING', 'NO_UPDATE', 'DOWNLOADING', 'VERIFYING',
    'DEFERRED', 'BUSY', 'NO_NETWORK', 'PHONE_REQUIRED', 'INCOMPATIBLE', 'FAILED',
    'STARTING', 'COMPLETE', 'WAIT_WIFI'};

  bool get valid {
    if (!_hex32.hasMatch(session) || request < 0 || request > 0xffffffff) return false;
    bool version(String s) => _number.hasMatch(s) && int.parse(s) > 0 && int.parse(s) <= 2100000000;
    return switch (kind) {
      'HELLO' || 'PING' || 'PONG' => fields.isEmpty && request == 0,
      'CAPS' => request == 0 && fields.length == 1 && fields[0] == '1',
      'CHECK' => request > 0 && fields.isEmpty,
      'STATE' => fields.length == 1 && states.contains(fields[0]),
      'OFFER' => fields.length == 5 && _hex32.hasMatch(fields[0]) &&
          version(fields[1]) && _sha.hasMatch(fields[2]) && _sha.hasMatch(fields[3]) &&
          (fields[4] == '0' || fields[4] == '1'),
      'SEEN' || 'SHOWN' => fields.length == 2 && _hex32.hasMatch(fields[0]) && _sha.hasMatch(fields[1]),
      'CHOICE' => fields.length == 4 && _hex32.hasMatch(fields[0]) &&
          version(fields[1]) && _sha.hasMatch(fields[2]) &&
          (fields[3] == 'NOW' || fields[3] == 'LATER'),
      _ => false,
    };
  }

  List<int> encode() {
    if (!valid) throw const FormatException('Invalid companion message');
    final body = ['!ETC1', kind, session, '$request', ...fields].join('|');
    final line = '$body*${checksum(ascii.encode(body)).toRadixString(16).padLeft(4, '0')}\n';
    if (line.length > maxLength) throw const FormatException('Companion message too long');
    return ascii.encode(line);
  }

  static CompanionMessage? parse(String line) {
    if (line.length > maxLength || !line.startsWith('!ETC1|')) return null;
    line = line.endsWith('\n') ? line.substring(0, line.length - 1) : line;
    final marker = line.lastIndexOf('*');
    if (marker < 0 || line.length - marker != 5) return null;
    final sum = line.substring(marker + 1);
    if (!RegExp(r'^[0-9a-f]{4}$').hasMatch(sum)) return null;
    final body = line.substring(0, marker);
    if (body.codeUnits.any((n) => n < 33 || n > 126) ||
        checksum(ascii.encode(body)) != int.parse(sum, radix: 16)) return null;
    final parts = body.split('|');
    if (parts.length < 4 || !_number.hasMatch(parts[3])) return null;
    final message = CompanionMessage(parts[1], parts[2], int.parse(parts[3]), parts.sublist(4));
    return message.valid ? message : null;
  }

  static int checksum(List<int> bytes) {
    var crc = 0xffff;
    for (final byte in bytes) {
      crc ^= byte << 8;
      for (var i = 0; i < 8; i++) {
        crc = ((crc & 0x8000) != 0 ? (crc << 1) ^ 0x1021 : crc << 1) & 0xffff;
      }
    }
    return crc;
  }
}

class CompanionDecoder {
  final _line = <int>[];
  bool _discarding = false;
  void reset() { _line.clear(); _discarding = false; }

  List<CompanionMessage> add(List<int> bytes, {required bool idleTextAllowed}) {
    if (!idleTextAllowed) { reset(); return const []; }
    final messages = <CompanionMessage>[];
    for (final byte in bytes) {
      if (byte == 10) {
        if (!_discarding && _line.isNotEmpty) {
          final message = CompanionMessage.parse(ascii.decode(_line));
          if (message != null) messages.add(message);
        }
        reset();
      } else if (byte < 33 || byte > 126 || _line.length >= CompanionMessage.maxLength - 1) {
        _discarding = true;
        _line.clear();
      } else if (!_discarding) {
        _line.add(byte);
      }
    }
    return messages;
  }
}

class CompanionOffer {
  CompanionOffer({required this.session, required this.request, required this.id,
    required this.address, required this.linkGeneration, required this.identity,
    required this.version, required this.packageSha, required this.targetSha,
    required this.expiresAt});
  final String session, id, address, identity, packageSha, targetSha;
  final int request, linkGeneration, version;
  final DateTime expiresAt;
  bool consumed = false;

  bool matches(CompanionMessage message, String connectedAddress, int generation,
      DateTime now) => !consumed && now.isBefore(expiresAt) &&
      address == connectedAddress && linkGeneration == generation && message.valid &&
      message.kind == 'CHOICE' && message.session == session && message.request == request &&
      message.fields[0] == id && message.fields[1] == '$version' && message.fields[2] == packageSha;
}
