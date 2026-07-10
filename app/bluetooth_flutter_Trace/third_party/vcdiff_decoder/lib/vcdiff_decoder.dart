import 'dart:typed_data';

// Trace-local VCDIFF decoder patched for xdelta3-generated APK deltas.
const int _magic1 = 0xd6;
const int _magic2 = 0xc3;
const int _magic3 = 0xc4;
const int _version = 0x00;

const int _vcdDecompress = 0x01;
const int _vcdCodeTable = 0x02;
const int _vcdAppHeader = 0x04;

const int _vcdSource = 0x01;
const int _vcdTarget = 0x02;
const int _vcdAdler32 = 0x04;

const int _nearSize = 4;
const int _sameSize = 3;

/// Decodes an RFC 3284 VCDIFF delta using [source] as the old file.
Uint8List decode(Uint8List source, Uint8List delta) {
  return _Decoder(source, delta).decode();
}

class VcdiffException implements Exception {
  const VcdiffException(this.message);

  final String message;

  @override
  String toString() => '$runtimeType: $message';
}

class InvalidMagicException extends VcdiffException {
  const InvalidMagicException(super.message);
}

class InvalidVersionException extends VcdiffException {
  const InvalidVersionException(super.message);
}

class InvalidFormatException extends VcdiffException {
  const InvalidFormatException(super.message);
}

class CorruptedDataException extends VcdiffException {
  const CorruptedDataException(super.message);
}

class InvalidChecksumException extends VcdiffException {
  const InvalidChecksumException(super.message);
}

class _Decoder {
  _Decoder(this.source, this.delta);

  final Uint8List source;
  final Uint8List delta;

  Uint8List decode() {
    final cursor = _Cursor(delta);
    _parseHeader(cursor);

    final target = _OutputBuffer();
    while (!cursor.isDone) {
      final windowTarget = _decodeWindow(cursor, target.view());
      target.addBytes(windowTarget);
    }
    return target.toBytes();
  }

  void _parseHeader(_Cursor cursor) {
    if (delta.length < 5) {
      throw InvalidFormatException(
        'VCDIFF file too small: expected at least 5 bytes, got ${delta.length}',
      );
    }

    final first = cursor.readByte();
    final second = cursor.readByte();
    final third = cursor.readByte();
    if (first != _magic1 || second != _magic2 || third != _magic3) {
      throw InvalidMagicException('Invalid VCDIFF magic bytes');
    }

    final version = cursor.readByte();
    if (version != _version) {
      throw InvalidVersionException(
        'Invalid VCDIFF version: expected $_version, got $version',
      );
    }

    final indicator = cursor.readByte();
    final validBits = _vcdDecompress | _vcdCodeTable | _vcdAppHeader;
    if ((indicator & ~validBits) != 0) {
      throw InvalidFormatException(
        'Invalid VCDIFF header indicator: $indicator',
      );
    }
    if ((indicator & _vcdDecompress) != 0) {
      throw InvalidFormatException('Secondary compression is not supported');
    }
    if ((indicator & _vcdCodeTable) != 0) {
      throw InvalidFormatException('Custom code tables are not supported');
    }
    if ((indicator & _vcdAppHeader) != 0) {
      cursor.skip(cursor.readVarint());
    }
  }

  Uint8List _decodeWindow(_Cursor cursor, Uint8List previousTarget) {
    final winIndicator = cursor.readByte();
    final validBits = _vcdSource | _vcdTarget | _vcdAdler32;
    if ((winIndicator & ~validBits) != 0) {
      throw InvalidFormatException(
        'Invalid VCDIFF window indicator: $winIndicator',
      );
    }
    if ((winIndicator & _vcdSource) != 0 &&
        (winIndicator & _vcdTarget) != 0) {
      throw InvalidFormatException(
        'VCD_SOURCE and VCD_TARGET cannot both be set',
      );
    }

    var sourceSegment = Uint8List(0);
    if ((winIndicator & (_vcdSource | _vcdTarget)) != 0) {
      final sourceSegmentSize = cursor.readVarint();
      final sourceSegmentPosition = cursor.readVarint();
      final sourceData =
          (winIndicator & _vcdSource) != 0 ? source : previousTarget;
      final sourceSegmentEnd = sourceSegmentPosition + sourceSegmentSize;
      if (sourceSegmentPosition < 0 ||
          sourceSegmentSize < 0 ||
          sourceSegmentEnd > sourceData.length) {
        throw InvalidFormatException(
          'Source segment position $sourceSegmentPosition + size '
          '$sourceSegmentSize exceeds source length ${sourceData.length}',
        );
      }
      sourceSegment = Uint8List.sublistView(
        sourceData,
        sourceSegmentPosition,
        sourceSegmentEnd,
      );
    }

    final deltaEncodingLength = cursor.readVarint();
    final deltaEnd = cursor.offset + deltaEncodingLength;
    if (deltaEncodingLength < 0 || deltaEnd > delta.length) {
      throw InvalidFormatException(
        'Delta encoding length $deltaEncodingLength exceeds remaining input',
      );
    }

    final deltaCursor = _Cursor(delta, cursor.offset, deltaEnd);
    final targetWindowLength = deltaCursor.readVarint();
    final deltaIndicator = deltaCursor.readByte();
    if (deltaIndicator != 0) {
      throw InvalidFormatException(
        'Compressed delta sections are not supported',
      );
    }

    final dataLength = deltaCursor.readVarint();
    final instructionLength = deltaCursor.readVarint();
    final addressLength = deltaCursor.readVarint();

    int? checksum;
    if ((winIndicator & _vcdAdler32) != 0) {
      checksum = deltaCursor.readUint32();
    }

    final dataSection = deltaCursor.readView(dataLength);
    final instructionSection = deltaCursor.readView(instructionLength);
    final addressSection = deltaCursor.readView(addressLength);
    if (!deltaCursor.isDone) {
      throw InvalidFormatException('VCDIFF delta section length mismatch');
    }
    cursor.offset = deltaEnd;

    final output = _executeInstructions(
      targetWindowLength: targetWindowLength,
      sourceSegment: sourceSegment,
      dataSection: dataSection,
      instructionSection: instructionSection,
      addressSection: addressSection,
    );

    if (checksum != null) {
      final computed = _adler32(output);
      if (computed != checksum) {
        throw InvalidChecksumException(
          'Checksum validation failed: expected '
          '0x${checksum.toRadixString(16).padLeft(8, '0')}, got '
          '0x${computed.toRadixString(16).padLeft(8, '0')}',
        );
      }
    }

    return output;
  }

  Uint8List _executeInstructions({
    required int targetWindowLength,
    required Uint8List sourceSegment,
    required Uint8List dataSection,
    required Uint8List instructionSection,
    required Uint8List addressSection,
  }) {
    final dataCursor = _Cursor(dataSection);
    final instructionCursor = _Cursor(instructionSection);
    final addressCache = _AddressCache(addressSection);
    final output = _OutputBuffer(targetWindowLength);

    while (!instructionCursor.isDone) {
      final code = instructionCursor.readByte();
      final instructions = _defaultCodeTable[code];
      for (final instruction in instructions) {
        if (instruction.type == _InstructionType.noop) continue;

        var size = instruction.size;
        if (size == 0) {
          size = instructionCursor.readVarint();
        }
        if (size < 0) {
          throw InvalidFormatException('Negative instruction size');
        }

        switch (instruction.type) {
          case _InstructionType.add:
            output.addBytes(dataCursor.readView(size));
            break;
          case _InstructionType.run:
            output.addRepeatedByte(dataCursor.readByte(), size);
            break;
          case _InstructionType.copy:
            final here = sourceSegment.length + output.length;
            final address = addressCache.decode(here, instruction.mode);
            if (address < 0 || address >= here) {
              throw InvalidFormatException(
                'COPY instruction address $address is outside decoded data',
              );
            }
            if (address < sourceSegment.length) {
              final end = address + size;
              if (end > sourceSegment.length) {
                throw InvalidFormatException(
                  'COPY instruction address $address + size $size exceeds '
                  'source segment length ${sourceSegment.length}',
                );
              }
              output.addBytes(
                Uint8List.sublistView(sourceSegment, address, end),
              );
            } else {
              output.copyFromSelf(address - sourceSegment.length, size);
            }
            break;
          case _InstructionType.noop:
            break;
        }

        if (output.length > targetWindowLength) {
          throw InvalidFormatException(
            'Decoded target window exceeds declared length',
          );
        }
      }
    }

    if (!dataCursor.isDone) {
      throw CorruptedDataException('Unused bytes remain in data section');
    }
    if (!addressCache.isDone) {
      throw CorruptedDataException('Unused bytes remain in address section');
    }
    if (output.length != targetWindowLength) {
      throw InvalidFormatException(
        'Decoded target window length ${output.length} does not match '
        'declared length $targetWindowLength',
      );
    }

    return output.toBytes();
  }
}

class _AddressCache {
  _AddressCache(Uint8List addresses) : _cursor = _Cursor(addresses);

  final _Cursor _cursor;
  final List<int> _near = List<int>.filled(_nearSize, 0);
  final List<int> _same = List<int>.filled(_sameSize * 256, 0);
  int _nextNearSlot = 0;

  bool get isDone => _cursor.isDone;

  int decode(int here, int mode) {
    late final int address;
    if (mode == 0) {
      address = _cursor.readVarint();
    } else if (mode == 1) {
      final offset = _cursor.readVarint();
      if (offset > here) {
        throw InvalidFormatException(
          'HERE mode offset $offset exceeds current position $here',
        );
      }
      address = here - offset;
    } else if (mode < 2 + _nearSize) {
      // RFC 3284 initializes near cache entries to zero. Zero is a valid
      // address, so it must not be treated as "uninitialized".
      address = _near[mode - 2] + _cursor.readVarint();
    } else if (mode < 2 + _nearSize + _sameSize) {
      final sameSlot = mode - 2 - _nearSize;
      final index = _cursor.readByte();
      address = _same[sameSlot * 256 + index];
    } else {
      throw InvalidFormatException('Invalid address cache mode $mode');
    }

    _update(address);
    return address;
  }

  void _update(int address) {
    _near[_nextNearSlot] = address;
    _nextNearSlot = (_nextNearSlot + 1) % _nearSize;
    _same[address % _same.length] = address;
  }
}

class _Cursor {
  _Cursor(this.bytes, [this.offset = 0, int? limit])
      : limit = limit ?? bytes.length;

  final Uint8List bytes;
  int offset;
  final int limit;

  bool get isDone => offset == limit;

  int readByte() {
    if (offset >= limit) {
      throw CorruptedDataException('Unexpected EOF at offset $offset');
    }
    return bytes[offset++];
  }

  int readUint32() {
    if (offset + 4 > limit) {
      throw CorruptedDataException('Unexpected EOF while reading uint32');
    }
    final value = (bytes[offset] << 24) |
        (bytes[offset + 1] << 16) |
        (bytes[offset + 2] << 8) |
        bytes[offset + 3];
    offset += 4;
    return value;
  }

  int readVarint() {
    var value = 0;
    for (var i = 0; i < 5; i++) {
      final byte = readByte();
      value = (value << 7) | (byte & 0x7f);
      if ((byte & 0x80) == 0) return value;
    }
    throw InvalidFormatException('Variable-length integer is too long');
  }

  Uint8List readView(int length) {
    if (length < 0 || offset + length > limit) {
      throw CorruptedDataException(
        'Unexpected EOF: need $length bytes at offset $offset',
      );
    }
    final view = Uint8List.sublistView(bytes, offset, offset + length);
    offset += length;
    return view;
  }

  void skip(int length) {
    readView(length);
  }
}

class _OutputBuffer {
  _OutputBuffer([int initialCapacity = 0])
      : _buffer = Uint8List(
          initialCapacity.clamp(1024, 1024 * 1024).toInt(),
        );

  Uint8List _buffer;
  int length = 0;

  Uint8List view() => Uint8List.sublistView(_buffer, 0, length);

  void addByte(int byte) {
    _ensureCapacity(1);
    _buffer[length++] = byte;
  }

  void addRepeatedByte(int byte, int count) {
    _ensureCapacity(count);
    _buffer.fillRange(length, length + count, byte);
    length += count;
  }

  void addBytes(Uint8List bytes) {
    _ensureCapacity(bytes.length);
    _buffer.setRange(length, length + bytes.length, bytes);
    length += bytes.length;
  }

  void copyFromSelf(int start, int count) {
    if (start < 0 || start >= length) {
      throw InvalidFormatException(
        'COPY references target position $start but target has $length bytes',
      );
    }
    _ensureCapacity(count);
    for (var i = 0; i < count; i++) {
      final copyPosition = start + i;
      if (copyPosition >= length) {
        throw InvalidFormatException(
          'COPY would read beyond target position $copyPosition',
        );
      }
      _buffer[length++] = _buffer[copyPosition];
    }
  }

  Uint8List toBytes() {
    final result = Uint8List(length);
    result.setRange(0, length, _buffer);
    return result;
  }

  void _ensureCapacity(int additionalLength) {
    final requiredLength = length + additionalLength;
    if (requiredLength <= _buffer.length) return;

    var newLength = _buffer.length;
    while (newLength < requiredLength) {
      newLength *= 2;
    }
    final expanded = Uint8List(newLength);
    expanded.setRange(0, length, _buffer);
    _buffer = expanded;
  }
}

enum _InstructionType { noop, add, run, copy }

class _Instruction {
  const _Instruction(this.type, this.size, this.mode);

  final _InstructionType type;
  final int size;
  final int mode;
}

const _noop = _Instruction(_InstructionType.noop, 0, 0);

final List<List<_Instruction>> _defaultCodeTable = _buildDefaultCodeTable();

List<List<_Instruction>> _buildDefaultCodeTable() {
  final entries = List.generate(256, (_) => [_noop, _noop]);
  entries[0] = const [_Instruction(_InstructionType.run, 0, 0), _noop];

  for (var i = 0; i < 18; i++) {
    entries[i + 1] = [_Instruction(_InstructionType.add, i, 0), _noop];
  }

  var index = 19;
  for (var mode = 0; mode < 9; mode++) {
    entries[index++] = [_Instruction(_InstructionType.copy, 0, mode), _noop];
    for (var size = 4; size < 19; size++) {
      entries[index++] = [
        _Instruction(_InstructionType.copy, size, mode),
        _noop,
      ];
    }
  }

  for (var mode = 0; mode < 6; mode++) {
    for (var addSize = 1; addSize < 5; addSize++) {
      for (var copySize = 4; copySize < 7; copySize++) {
        entries[index++] = [
          _Instruction(_InstructionType.add, addSize, 0),
          _Instruction(_InstructionType.copy, copySize, mode),
        ];
      }
    }
  }

  for (var mode = 6; mode < 9; mode++) {
    for (var addSize = 1; addSize < 5; addSize++) {
      entries[index++] = [
        _Instruction(_InstructionType.add, addSize, 0),
        _Instruction(_InstructionType.copy, 4, mode),
      ];
    }
  }

  for (var mode = 0; mode < 9; mode++) {
    entries[index++] = [
      _Instruction(_InstructionType.copy, 4, mode),
      const _Instruction(_InstructionType.add, 1, 0),
    ];
  }

  return entries;
}

int _adler32(Uint8List bytes) {
  const base = 65521;
  var a = 1;
  var b = 0;
  for (final byte in bytes) {
    a = (a + byte) % base;
    b = (b + a) % base;
  }
  return (b << 16) | a;
}
