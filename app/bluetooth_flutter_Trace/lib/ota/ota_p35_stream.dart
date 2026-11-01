import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:crypto/crypto.dart';

/// Explicit observation only, loopback/ADB forwarding, one peer and no replay.
/// Every persisted batch needs a length/hash ACK from the host's durable sink.
class OtaP35Stream {
  OtaP35Stream({this.port = 49135,
    this.connectTimeout = const Duration(seconds: 5),
    this.ackTimeout = const Duration(seconds: 2)});

  final int port;
  final Duration connectTimeout, ackTimeout;
  ServerSocket? _server;
  Socket? _peer;
  StreamSubscription<Socket>? _accept;
  StreamSubscription<List<int>>? _input;
  Completer<Socket>? _connection;
  Completer<void>? _ack;
  String? _expectedAck;
  final List<int> _pending = [];
  Object? _failure;
  bool _used = false, _closed = false;
  int get boundPort => _server!.port;

  Future<void> open() async {
    if (_used) throw StateError('stream is single use');
    _used = true;
    _connection = Completer<Socket>();
    _server = await ServerSocket.bind(InternetAddress.loopbackIPv4, port, shared: false);
    _accept = _server!.listen((peer) {
      if (_closed || _peer != null) { peer.destroy(); return; }
      _peer = peer;
      peer.setOption(SocketOption.tcpNoDelay, true);
      _input = peer.listen(_receive, onError: _fail,
        onDone: () => _fail(StateError('stream peer closed')));
      _connection!.complete(peer);
    }, onError: _fail);
  }

  void _fail(Object error) {
    if (_closed) return;
    _failure ??= error;
    final ack = _ack;
    if (ack != null && !ack.isCompleted) ack.completeError(error);
    // send() owns the connection timeout; never leave an unobserved error Future.
  }

  void _receive(List<int> bytes) {
    if (_failure != null || _closed) return;
    _pending.addAll(bytes);
    if (_pending.length > 100 || _ack == null || _ack!.isCompleted) {
      _fail(StateError('unsolicited/oversized stream ACK'));
      return;
    }
    final newline = _pending.indexOf(10);
    if (newline < 0) return;
    if (newline != _pending.length - 1 ||
        ascii.decode(_pending, allowInvalid: true) != _expectedAck) {
      _fail(StateError('stream ACK identity mismatch'));
      return;
    }
    _pending.clear();
    _ack!.complete();
  }

  Future<void> send(List<int> bytes) async {
    if (_closed || _failure != null || _ack != null || bytes.isEmpty || bytes.length > 1024 * 1024) {
      throw StateError('stream unavailable/invalid batch: $_failure');
    }
    try {
      final peer = await _connection!.future.timeout(connectTimeout);
      if (_failure != null) throw StateError('stream failed: $_failure');
      _ack = Completer<void>();
      _expectedAck = 'ACK ${bytes.length} ${sha256.convert(bytes)}\n';
      final header = ByteData(4)..setUint32(0, bytes.length);
      // Start observing the ACK before writing, including asynchronous close errors.
      final confirmed = _ack!.future.timeout(ackTimeout);
      peer.add(header.buffer.asUint8List());
      peer.add(bytes);
      await confirmed;
    } catch (error) {
      _failure ??= error;
      rethrow;
    } finally {
      _ack = null;
      _expectedAck = null;
    }
  }

  Future<void> close() async {
    if (_closed) return;
    _closed = true;
    final ack = _ack;
    if (ack != null && !ack.isCompleted) ack.completeError(StateError('stream closed'));
    await _input?.cancel();
    _peer?.destroy();
    await _accept?.cancel();
    await _server?.close();
  }
}
