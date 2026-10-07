import 'dart:typed_data';

/// Development protocol v2 credit bookkeeping, not enabled by OtaService.
/// A reservation must precede its physical write. Failed/uncertain writes cancel
/// this generation; a new BEGIN reconstructs state from MCU durable progress.
class OtaPipelineWindow {
  OtaPipelineWindow({
    required this.epoch,
    required this.totalBytes,
    required int durableOffset,
    this.maxInFlightSegments = 24,
  })  : _durable = durableOffset,
        _accepted = durableOffset,
        _submitted = durableOffset {
    if (epoch <= 0 || epoch > 0xffffffff ||
        totalBytes <= 0 || totalBytes > 0x180000 ||
        durableOffset < 0 || durableOffset > totalBytes ||
        !_aligned(durableOffset, blockBytes) ||
        maxInFlightSegments < 1 || maxInFlightSegments > 24) {
      throw ArgumentError('Invalid pipeline epoch, length, prefix or window');
    }
    _creditEnd = _limit(durableOffset + 2 * blockBytes, totalBytes);
  }

  static const blockBytes = 4096;
  static const segmentBytes = 128;
  static const ackBytes = 16;

  /// A missing response may fall back to v1. A malformed/mismatched response
  /// must not be interpreted as support, nor reused across connections.
  static bool acceptsCapabilities(Uint8List payload, int nonce) {
    if (nonce <= 0 || nonce > 0xffffffff || payload.length != 16) {
      return false;
    }
    final data = ByteData.sublistView(payload);
    return payload[0] == 80 && payload[1] == 50 && payload[2] == 66 &&
        payload[3] == 76 && payload[4] == 2 && payload[5] == 2 &&
        data.getUint16(6, Endian.little) == segmentBytes &&
        data.getUint32(8, Endian.little) == nonce &&
        data.getUint32(12, Endian.little) == 24;
  }
  final int epoch;
  final int totalBytes;
  final int maxInFlightSegments;
  int _durable;
  int _accepted;
  int _submitted;
  late int _creditEnd;
  bool _active = true;

  int get durableOffset => _durable;
  int get acceptedOffset => _accepted;
  int get submittedOffset => _submitted;
  int get creditEnd => _creditEnd;
  bool get active => _active;
  bool get complete => _active && _durable == totalBytes;

  static int _limit(int a, int b) => a < b ? a : b;
  bool _aligned(int offset, int unit) => offset == totalBytes || offset % unit == 0;

  /// Only call after a successful, generation-bound v2 BEGIN. This 16-byte
  /// payload is epoch/durable/accepted/creditEnd, each little-endian uint32.
  /// ACK frame CRC/status/session validation belongs to the transport layer.
  bool acknowledge(Uint8List payload) {
    if (!_active) {
      return false;
    }
    if (payload.length != ackBytes) {
      _active = false;
      throw const FormatException('Pipeline ACK length');
    }
    final data = ByteData.sublistView(payload);
    if (data.getUint32(0, Endian.little) != epoch) {
      return false;
    }
    final durable = data.getUint32(4, Endian.little);
    final accepted = data.getUint32(8, Endian.little);
    final credit = data.getUint32(12, Endian.little);
    if (durable > accepted || accepted > _submitted || accepted > credit ||
        credit != _limit(durable + 2 * blockBytes, totalBytes) ||
        !_aligned(durable, blockBytes) || !_aligned(accepted, segmentBytes)) {
      _active = false;
      throw const FormatException('Pipeline ACK exceeds verified send/credit bounds');
    }
    if (durable < _durable || accepted < _accepted || credit < _creditEnd) {
      if (durable <= _durable && accepted <= _accepted && credit <= _creditEnd) {
        return false; // Delayed coherent snapshot, never a credit rollback.
      }
      _active = false;
      throw const FormatException('Inconsistent pipeline ACK regression');
    }
    final changed = durable != _durable || accepted != _accepted || credit != _creditEnd;
    _durable = durable;
    _accepted = accepted;
    _creditEnd = credit;
    return changed;
  }

  /// Reserves absolute segment offsets across 4 KiB boundaries. It does not
  /// count accepted RAM bytes as persistent progress or expand physical in-flight
  /// credit beyond 24 segments. V2's extra epoch word would make 28 frames
  /// consume 4088 of 4095 ring bytes, leaving no useful control-frame headroom.
  List<int> reserve({int maxSegments = 12}) {
    if (!_active) {
      throw StateError('Pipeline generation is closed');
    }
    if (maxSegments < 1 || maxSegments > 24) {
      throw ArgumentError.value(maxSegments);
    }
    final offsets = <int>[];
    var outstanding = (_submitted - _accepted + segmentBytes - 1) ~/ segmentBytes;
    while (offsets.length < maxSegments && outstanding < maxInFlightSegments &&
        _submitted < _creditEnd) {
      offsets.add(_submitted);
      _submitted = _limit(_submitted + segmentBytes, totalBytes);
      outstanding++;
    }
    return offsets;
  }

  /// Retry only previously submitted unaccepted segments, with their original
  /// sequence numbers retained by the transport. This grants no new credit.
  List<int> retryOffsets({int maxSegments = 12}) {
    if (!_active) {
      throw StateError('Pipeline generation is closed');
    }
    if (maxSegments < 1 || maxSegments > 24) {
      throw ArgumentError.value(maxSegments);
    }
    return [
      for (var off = _accepted; off < _submitted &&
          off < _accepted + maxSegments * segmentBytes; off += segmentBytes) off,
    ];
  }

  void cancel() => _active = false;
}
