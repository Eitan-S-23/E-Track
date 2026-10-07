part of 'ota_ble_transport.dart';

/// Explicit development extension. The v1 codec and INFO stay unchanged.
class _PipelineWire {
  static const caps = 0x10;
  static const begin = 0x11;
  static const data = 0x12;
  static const end = 0x13;
  static const abort = 0x14;
  static const capsReply = 0x90;
  static const ackBegin = 0x91;
  static const ackData = 0x92;
  static const ackEnd = 0x93;
  static const ackAbort = 0x94;

  static Uint8List word(int value) =>
      (ByteData(4)..setUint32(0, value, Endian.little)).buffer.asUint8List();
}

class _PipelineAck {
  _PipelineAck(OtaBleFrame frame, {this.arrivalUs}) {
    final base = frame.cmd == _PipelineWire.ackBegin ? 2 : 1;
    if (frame.payload.length != base + OtaPipelineWindow.ackBytes ||
        !OtaBleCodec.knownStatuses.contains(frame.payload[0])) {
      throw const OtaTransportException('Invalid v2 ACK', code: 'ACK_MALFORMED');
    }
    status = frame.payload[0];
    session = base == 2 ? frame.payload[1] : frame.session;
    body = Uint8List.sublistView(frame.payload, base);
    final bytes = ByteData.sublistView(body);
    epoch = bytes.getUint32(0, Endian.little);
    durable = bytes.getUint32(4, Endian.little);
    accepted = bytes.getUint32(8, Endian.little);
    credit = bytes.getUint32(12, Endian.little);
    if (session != frame.session ||
        (status == OtaBleCodec.statusOk && session == 0)) {
      throw const OtaTransportException('Invalid v2 session', code: 'ACK_MALFORMED');
    }
  }

  late final int status, session, epoch, durable, accepted, credit;
  late final Uint8List body;
  final int? arrivalUs;
}

class _PipelineWaiter extends _ResponseWaiter {
  _PipelineWaiter(super.expectedCmd, super.session, super.seq, this.epoch);
  final int epoch;

  @override
  bool matches(OtaBleFrame frame) {
    if (!super.matches(frame)) return false;
    final base = expectedCmd == _PipelineWire.ackBegin ? 2 : 1;
    if (frame.payload.length < base + 4) return true; // Report malformed, not credit.
    final echoed = ByteData.sublistView(frame.payload).getUint32(base, Endian.little);
    return echoed == epoch ||
        (echoed == 0 && (frame.payload[0] == OtaBleCodec.statusErrCrc ||
            frame.payload[0] == OtaBleCodec.statusErrFrame));
  }
}

class _PipelineAckView {
  _PipelineAckView(this.window, this.session, this.beginSeq, this.onDurable, this.stats)
      : eligibleEnd = window.acceptedOffset;
  final OtaPipelineWindow window;
  final int session, beginSeq;
  final void Function(int) onDurable;
  final OtaLinkStats? stats;
  final Set<int> sentSeqs = {};
  final Map<int, int> sendCounts = {};
  int eligibleEnd;
  Object? _error;
  bool retryRequested = false;
  Completer<void>? _change;

  void onAck(OtaBleFrame frame) {
    if (!window.active || frame.session != session ||
        (frame.cmd != _PipelineWire.ackData && frame.cmd != _PipelineWire.ackAbort)) {
      return;
    }
    if (frame.payload.length >= 5 &&
        ByteData.sublistView(frame.payload).getUint32(1, Endian.little) != window.epoch) {
      return;
    }
    try {
      final ack = _PipelineAck(frame);
      if (ack.epoch != window.epoch) return;
      if (frame.cmd == _PipelineWire.ackData &&
          !sentSeqs.contains(frame.seq) && frame.seq != beginSeq) {
        return;
      }
      if (ack.status != OtaBleCodec.statusOk) {
        stats?.recordAckClass('error');
        if (frame.cmd == _PipelineWire.ackData &&
            const {OtaBleCodec.statusErrFrame, OtaBleCodec.statusErrCrc,
              OtaBleCodec.statusErrSeq, OtaBleCodec.statusErrOffset}.contains(ack.status)) {
          retryRequested = true;
          _signal();
          return; // Error snapshots never grant credit.
        }
        throw OtaTransportException('v2 receiver stopped', code: 'ACK_STATUS', status: ack.status);
      }
      if (frame.cmd != _PipelineWire.ackData) {
        throw const OtaTransportException('Invalid v2 ABORT ACK', code: 'ACK_MALFORMED');
      }
      if (ack.accepted > eligibleEnd) {
        throw const OtaTransportException('ACK confirms undispatched DATA', code: 'ACK_MALFORMED');
      }
      final before = window.durableOffset;
      final changed = window.acknowledge(ack.body);
      stats?.recordAckClass(changed ? 'ok' : 'duplicate');
      if (window.durableOffset > before) {
        stats?.recordAckConfirm(blockStart: before,
          segs: List.generate((window.durableOffset - before + 127) ~/ 128, (i) => i),
          segmentSize: 128);
        stats?.recordDurableAdvance(window.durableOffset);
        onDurable(window.durableOffset);
      }
      if (changed) _signal();
    } on FormatException {
      fail(const OtaTransportException('Invalid v2 credit', code: 'ACK_MALFORMED'));
    } on OtaTransportException catch (error) {
      fail(error);
    }
  }

  void check() {
    final error = _error;
    if (error != null) throw error;
  }

  void fail(Object error) {
    _error ??= error;
    window.cancel();
    _signal();
  }

  void _signal() {
    final change = _change;
    _change = null;
    if (change != null && !change.isCompleted) change.complete();
  }

  Future<bool> wait(Duration timeout) async {
    check();
    if (retryRequested) return true;
    final change = Completer<void>();
    _change = change;
    try {
      await change.future.timeout(timeout);
      return true;
    } on TimeoutException {
      return false;
    } finally {
      if (identical(_change, change)) _change = null;
      if (!change.isCompleted) change.complete();
    }
  }
}

extension _PipelineTransfer on OtaBleTransport {
  Future<_PipelineAck> _pipelineRoundTrip({
    required int cmd,
    required int seq,
    required int epoch,
    required Uint8List payload,
    required int session,
  }) async {
    final frame = OtaBleCodec.encodeCommand(cmd: cmd, session: session, seq: seq, payload: payload);
    for (var attempt = 0; ; attempt++) {
      await _waitIfPaused();
      _checkUsable();
      _checkNoProgress();
      final waiter = _PipelineWaiter(cmd + 0x80, cmd == _PipelineWire.begin ? -1 : session, seq, epoch);
      _waiters.add(waiter);
      try {
        await _writeFrame(frame);
        final response = await waiter.future.timeout(_capByBudget(ackTimeout));
        final ack = _PipelineAck(response, arrivalUs: waiter.arrivalUs);
        if (ack.status == OtaBleCodec.statusOk && ack.epoch == epoch) return ack;
        if (attempt < retries &&
            (ack.status == OtaBleCodec.statusErrCrc || ack.status == OtaBleCodec.statusErrFrame)) {
          continue;
        }
        throw OtaTransportException('v2 command rejected', code: 'ACK_STATUS', status: ack.status);
      } on TimeoutException {
        _checkNoProgress();
        if (attempt >= retries) {
          throw const OtaTransportException('v2 command timed out', code: 'TIMEOUT');
        }
      } finally {
        _waiters.remove(waiter);
      }
    }
  }

  Future<OtaAckResult?> _tryPipelineTransfer({
    required Uint8List package,
    required List<int> packageSha256,
    required List<int> etuHeader,
    required int? windowSegments,
    required void Function(int, int)? onDurableProgress,
    required void Function(int, int)? onSent,
  }) async {
    if (_pipelineEpoch != null) {
      throw const OtaTransportException('Previous v2 session requires teardown', code: 'BUSY');
    }
    _busy = true;
    var negotiated = false;
    var transferStarted = false;
    var ok = false;
    try {
      // Fresh per attempt, never inherited from a prior connection/transport.
      final epoch = _deviceWriteLedger.nextPipelineEpoch();
      _pipelineEpoch = epoch;
      final querySeq = _nextQuerySeq();
      await _waitIfPaused();
      _checkUsable();
      Uint8List caps;
      try {
        caps = await _roundTrip(
          OtaBleCodec.encodeCommand(cmd: _PipelineWire.caps, session: 0, seq: querySeq,
            payload: _PipelineWire.word(epoch)),
          _PipelineWire.capsReply, session: 0, seq: querySeq, timeout: ackTimeout);
      } on OtaTransportException catch (error) {
        if (error.code == 'TIMEOUT' && _channel.isConnected && !_writeChannelPoisoned) return null;
        rethrow;
      }
      if (!OtaPipelineWindow.acceptsCapabilities(caps, epoch)) {
        throw const OtaTransportException('Invalid v2 capability', code: 'ACK_MALFORMED');
      }
      negotiated = true;
      // Validate lengths before opening a receiver session.
      final prefix = OtaBleCodec.encodeBeginPayload(totalLen: package.length,
        packageSha256: packageSha256, etuHeader: etuHeader);
      OtaPipelineWindow(epoch: epoch, totalBytes: package.length, durableOffset: 0);
      prefix[0] = 2;
      final beginSeq = _nextSeq();
      _noProgressClock = Stopwatch()..start();
      _inTransfer = true;
      transferStarted = true;
      final beginAck = await _pipelineRoundTrip(cmd: _PipelineWire.begin, seq: beginSeq,
        epoch: epoch, session: 0, payload: Uint8List.fromList([...prefix, ..._PipelineWire.word(epoch)]));
      _session = beginAck.session;
      final window = OtaPipelineWindow(epoch: epoch, totalBytes: package.length,
        durableOffset: beginAck.durable, maxInFlightSegments: (windowSegments ?? 24).clamp(1, 24).toInt());
      window.acknowledge(beginAck.body);
      final resume = beginAck.durable;
      final view = _PipelineAckView(window, _session, beginSeq, (durable) {
        _noProgressClock?.reset();
        onDurableProgress?.call(durable, package.length);
      }, stats);
      _pipelineView = view;
      onDurableProgress?.call(resume, package.length);
      var sentBytes = 0;

      Future<void> sendOffsets(List<int> offsets) async {
        await _waitIfPaused();
        _checkUsable();
        _checkNoProgress();
        view.check();
        final stream = BytesBuilder(copy: false);
        final ends = <int>[];
        final sequences = <int>[];
        for (final offset in offsets) {
          if ((view.sendCounts[offset] ?? 0) >= retries + 1) {
            throw const OtaTransportException('v2 DATA retry limit', code: 'TIMEOUT');
          }
          final seq = (beginSeq + 1 + (offset - resume) ~/ 128) & 0xffff;
          sequences.add(seq);
          final end = math.min(offset + 128, package.length);
          stream.add(OtaBleCodec.encodeCommand(cmd: _PipelineWire.data, session: _session, seq: seq,
            payload: [..._PipelineWire.word(epoch),
              ...OtaBleCodec.encodeDataPayload(offset, package.sublist(offset, end))]));
          ends.add(stream.length);
        }
        var registered = 0, finished = 0, previousEnd = 0;
        await _writeFrameChecked(stream.takeBytes(), allowCancelled: false, frameEnds: ends,
          onChunkStarting: (end) {
            // Reuse the measured batch writer. Only fully dispatched frames
            // become ACK-eligible; reservations for future chunks grant no progress.
            while (registered < ends.length && ends[registered] <= end) {
              final offset = offsets[registered];
              view.sendCounts[offset] = (view.sendCounts[offset] ?? 0) + 1;
              view.sentSeqs.add(sequences[registered]);
              view.eligibleEnd = math.max(view.eligibleEnd, math.min(offset + 128, package.length));
              registered++;
            }
          },
          onChunkCompleted: (end) {
            final completing = ends.skip(finished).takeWhile((boundary) => boundary <= end).length;
            stats?.recordDataBatchChunk(bytes: end - previousEnd, completedFrames: completing);
            previousEnd = end;
            while (finished < ends.length && ends[finished] <= end) {
              final offset = offsets[finished++];
              final len = math.min(128, package.length - offset);
              stats?.recordSegmentSendEnd(offsetBytes: offset, lengthBytes: len);
              sentBytes += len;
            }
            onSent?.call(sentBytes, package.length);
          });
        view.check();
      }

      while (!window.complete) {
        await _waitIfPaused();
        _checkUsable();
        _checkNoProgress();
        view.check();
        if (!_channel.isConnected) {
          throw const OtaTransportException('BLE disconnected', code: 'DISCONNECTED');
        }
        if (!view.retryRequested) {
          final offsets = window.reserve(maxSegments: dataBatchFrames);
          if (offsets.isNotEmpty) {
            await sendOffsets(offsets);
            continue;
          }
        }
        final changed = await view.wait(_capByBudget(ackTimeout));
        view.check();
        _checkNoProgress();
        if (!changed || view.retryRequested) {
          view.retryRequested = false;
          for (final offset in window.retryOffsets(maxSegments: 24)) {
            if (offset < window.acceptedOffset) continue;
            await sendOffsets([offset]);
          }
        }
      }
      view.check();
      _checkUsable();
      final endSeq = (beginSeq + 1 + (package.length - resume + 127) ~/ 128) & 0xffff;
      final endAck = await _pipelineRoundTrip(cmd: _PipelineWire.end, seq: endSeq,
        epoch: epoch, session: _session,
        payload: Uint8List.fromList([..._PipelineWire.word(epoch), ...packageSha256]));
      view.check();
      _checkUsable();
      if (endAck.durable != package.length || endAck.accepted != package.length ||
          endAck.credit != package.length) {
        throw const OtaTransportException('Incomplete v2 END ACK', code: 'ACK_MALFORMED');
      }
      final endStats = stats;
      if (endStats != null && endAck.arrivalUs != null) {
        endStats.recordEndAckArrival(atUs: endAck.arrivalUs!);
      }
      _seq = (endSeq + 1) & 0xffff;
      _pipelineEpoch = null;
      ok = true;
      return OtaAckResult(status: OtaBleCodec.statusOk, durableOff: package.length, blockBitmap: 0);
    } on FormatException {
      throw const OtaTransportException('Invalid v2 credit', code: 'ACK_MALFORMED');
    } on ArgumentError {
      throw const OtaTransportException('Invalid v2 bounds', code: 'ACK_MALFORMED');
    } finally {
      _pipelineView?.window.cancel();
      _pipelineView = null;
      _noProgressClock = null;
      _inTransfer = false;
      _busy = false;
      if (!negotiated) _pipelineEpoch = null;
      if (transferStarted) stats?.recordTransferOutcome(ok: ok);
    }
  }
}
