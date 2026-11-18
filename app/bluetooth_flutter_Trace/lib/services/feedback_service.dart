import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:math';

import 'package:dio/dio.dart';
import 'package:flutter/services.dart';
import 'package:flutter/widgets.dart';
import 'package:get/get.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../config/share_links.dart';

class FeedbackReply {
  const FeedbackReply(this.status, this.body);
  final int status;
  final Map<String, dynamic> body;
}

typedef FeedbackSender = Future<FeedbackReply> Function(
    Uri uri, Map<String, dynamic> body, String token, CancelToken cancel);

class FeedbackService extends GetxService with WidgetsBindingObserver {
  FeedbackService({Uri? endpoint, FeedbackSender? sender,
    Future<Map<String, dynamic>> Function()? readIdentity,
    DateTime Function()? clock, bool Function()? canSend, bool? supported})
      : endpoint = endpoint ?? Uri.parse(ShareLinks.cloudflareUpdateManifestUrl)
            .replace(path: '/api/public/feedback', query: '', fragment: ''),
        _sender = sender ?? _send, _readIdentity = readIdentity ?? _identity,
        _clock = clock ?? DateTime.now, _canSend = canSend ?? (() => true),
        available = supported ?? (Platform.isAndroid || Platform.isWindows || Platform.isIOS);

  static const storageKey = 'feedback_outbox_v1';
  static const maxPending = 50;
  final Uri endpoint;
  final FeedbackSender _sender;
  final Future<Map<String, dynamic>> Function() _readIdentity;
  final DateTime Function() _clock;
  final bool Function() _canSend;
  final bool available;
  final ready = false.obs;
  final sending = false.obs;
  final revision = 0.obs;
  final failure = RxnString();
  SharedPreferences? _prefs;
  Future<void>? _initialization;
  Future<void> _edits = Future.value();
  Map<String, dynamic> _data = {};
  Timer? _timer;
  CancelToken? _cancel;
  bool _closed = false, _foreground = true;

  List<Map<String, dynamic>> get pending { revision.value; return _rows(_data['pending']); }
  List<Map<String, dynamic>> get sent { revision.value; return _rows(_data['sent']); }
  DateTime? get nextAttemptAt {
    revision.value;
    final value = _data['notBefore'] as int? ?? 0;
    return value > 0 ? DateTime.fromMillisecondsSinceEpoch(value, isUtc: true).toLocal() : null;
  }
  bool isSealed(String id) => _rows((_data['flight'] as Map?)?['messages']).any((item) => item['id'] == id);

  static List<Map<String, dynamic>> _rows(dynamic value) =>
      (value as List? ?? []).map((item) => Map<String, dynamic>.from(item as Map)).toList();
  Map<String, dynamic> _copy() => jsonDecode(jsonEncode(_data)) as Map<String, dynamic>;
  static String _randomHex(int count) {
    final random = Random.secure();
    return List.generate(count, (_) => random.nextInt(256).toRadixString(16).padLeft(2, '0')).join();
  }
  static String _uuid() {
    final value = _randomHex(16);
    return '${value.substring(0, 8)}-${value.substring(8, 12)}-4${value.substring(13, 16)}-'
        '8${value.substring(17, 20)}-${value.substring(20)}';
  }

  static Future<Map<String, dynamic>> _identity() async {
    Map<String, dynamic>? info;
    try { info = await const MethodChannel('trace/app_update').invokeMapMethod<String, dynamic>('getAppInfo'); }
    catch (_) { /* Feedback remains usable on platforms without the Android bridge. */ }
    return {'platform': Platform.operatingSystem,
      'versionName': info?['versionName'] is String ? info!['versionName'] : 'unknown',
      'versionCode': info?['versionCode'] is int ? info!['versionCode'] : 0};
  }

  static Future<FeedbackReply> _send(Uri uri, Map<String, dynamic> body, String token, CancelToken cancel) async {
    final dio = Dio(BaseOptions(connectTimeout: const Duration(seconds: 12),
      sendTimeout: const Duration(seconds: 15), receiveTimeout: const Duration(seconds: 15)));
    try {
      final result = await dio.postUri<Map<String, dynamic>>(uri, data: body, cancelToken: cancel,
        options: Options(followRedirects: false, validateStatus: (status) => status != null,
          headers: {'Authorization': 'Bearer $token'}, contentType: Headers.jsonContentType));
      if (result.data == null) throw const FormatException('Missing feedback receipt');
      return FeedbackReply(result.statusCode ?? 0, result.data!);
    } finally { dio.close(); }
  }

  @override
  void onInit() {
    super.onInit();
    WidgetsBinding.instance.addObserver(this);
    unawaited(poll());
  }

  Future<void> initialize() => _initialization ??= _initialize();
  Future<void> _initialize() async {
    if (endpoint.scheme != 'https' || endpoint.host.isEmpty || endpoint.userInfo.isNotEmpty) throw const FormatException('Invalid feedback endpoint');
    _prefs = await SharedPreferences.getInstance();
    final raw = _prefs!.getString(storageKey);
    if (raw == null) {
      await _commit({'token': _randomHex(32), 'pending': [], 'sent': [], 'flight': null,
        'notBefore': 0, 'blocked': false, 'failures': 0});
    } else {
      if (raw.length > 1024 * 1024) throw const FormatException('Oversized local outbox');
      final parsed = jsonDecode(raw);
      if (parsed is! Map<String, dynamic> || !RegExp(r'^[0-9a-f]{64}$').hasMatch(parsed['token']?.toString() ?? '') ||
          parsed['pending'] is! List || parsed['sent'] is! List || parsed['notBefore'] is! int ||
          parsed['blocked'] is! bool || parsed['failures'] is! int ||
          _rows(parsed['pending']).length > maxPending || _rows(parsed['sent']).length > 50) {
        throw const FormatException('Invalid local outbox; original data preserved');
      }
      for (final item in [..._rows(parsed['pending']), ..._rows(parsed['sent'])]) { _validateMessage(item); }
      final pendingIds = _rows(parsed['pending']).map((item) => item['id']).toSet();
      if (pendingIds.length != _rows(parsed['pending']).length) throw const FormatException('Duplicate local feedback');
      if (parsed['flight'] != null) {
        final flight = parsed['flight'];
        if (flight is! Map || flight['batchId'] is! String || flight['uncertain'] is! bool ||
            flight['messages'] is! List || _rows(flight['messages']).isEmpty || _rows(flight['messages']).length > 10) {
          throw const FormatException('Invalid pending batch');
        }
        for (final item in _rows(flight['messages'])) {
          _validateMessage(item);
          if (!pendingIds.contains(item['id']) || !_rows(parsed['pending']).any((row) => jsonEncode(row) == jsonEncode(item))) {
            throw const FormatException('Pending batch differs from outbox');
          }
        }
      }
      _data = parsed;
    }
    ready.value = true;
    revision.value++;
  }

  static void _validateMessage(Map<String, dynamic> item) {
    if (item['id'] is! String || !RegExp(r'^[0-9a-f-]{36}$').hasMatch(item['id'] as String) ||
        item['body'] is! String || (item['body'] as String).trim().isEmpty || (item['body'] as String).length > 2000 ||
        (item['body'] as String).contains('\u0000') || item['createdAt'] is! int ||
        (item['createdAt'] as int) < 0 || (item['createdAt'] as int) > 4102444800 ||
        !['android', 'windows', 'ios'].contains(item['platform']) || item['versionName'] is! String ||
        !RegExp(r'^[\w.+-]{1,64}$').hasMatch(item['versionName'] as String) || item['versionCode'] is! int ||
        (item['versionCode'] as int) < 0 || (item['versionCode'] as int) > 2100000000) {
      throw const FormatException('Invalid feedback content or App identity');
    }
  }

  Future<T> _exclusive<T>(Future<T> Function() operation) {
    final done = Completer<T>();
    _edits = _edits.then((_) async {
      try { done.complete(await operation()); }
      catch (error, stack) { done.completeError(error, stack); }
    });
    return done.future;
  }

  Future<void> _commit(Map<String, dynamic> next) async {
    if (!await _prefs!.setString(storageKey, jsonEncode(next))) throw StateError('Local feedback save failed');
    _data = next;
    revision.value++;
  }

  Future<void> add(String text) async {
    if (!available || _closed) throw StateError('Feedback unavailable');
    if (text.trim().isEmpty || text.length > 2000 || text.contains('\u0000')) throw const FormatException('Feedback length invalid');
    await initialize();
    final identity = await _readIdentity();
    final item = <String, dynamic>{'id': _uuid(), 'body': text.trim(),
      'createdAt': _clock().toUtc().millisecondsSinceEpoch ~/ 1000,
      'platform': identity['platform'], 'versionName': identity['versionName'], 'versionCode': identity['versionCode']};
    _validateMessage(item);
    await _exclusive(() async {
      if (pending.length >= maxPending) throw StateError('FEEDBACK_OUTBOX_FULL');
      final next = _copy();
      (next['pending'] as List).add(item);
      await _commit(next);
    });
    unawaited(poll());
  }

  Future<void> remove(String id) async {
    await initialize();
    await _exclusive(() async {
      if (isSealed(id)) throw StateError('Pending receipt must be reconciled first');
      final next = _copy();
      (next['pending'] as List).removeWhere((dynamic item) => (item as Map)['id'] == id);
      await _commit(next);
    });
  }

  Future<void> retry() async {
    await initialize();
    await _exclusive(() async { final next = _copy(); next['blocked'] = false; await _commit(next); });
    await poll();
  }

  int _serverDelay(Map<String, dynamic> body, String deadline) {
    final time = body['serverTime'], until = body[deadline];
    if (time is! int || until is! int || time <= 0 || until <= 0 || until - time > 2 * 86400) {
      throw const FormatException('Invalid server retry time');
    }
    return max(0, until - time);
  }

  Future<void> poll() async {
    if (_closed || !_foreground || !available || sending.value) return;
    sending.value = true;
    _timer?.cancel();
    try {
      await initialize();
      if (_closed || !_foreground || !_canSend() || pending.isEmpty || _data['blocked'] == true ||
          _clock().toUtc().millisecondsSinceEpoch < (_data['notBefore'] as int)) {
        return;
      }
      late Map<String, dynamic> flight;
      late bool canThaw;
      var prepared = false;
      await _exclusive(() async {
        if (pending.isEmpty) return;
        final next = _copy();
        next['flight'] ??= {'batchId': _uuid(), 'messages': pending.take(10).toList(), 'uncertain': false};
        flight = Map<String, dynamic>.from(next['flight'] as Map);
        canThaw = flight['uncertain'] == false;
        flight['uncertain'] = true;
        next['flight'] = flight;
        await _commit(next); // Persist the exact request before any network effect.
        prepared = true;
      });
      if (!prepared || _closed || !_foreground || !_canSend()) return;
      _cancel = CancelToken();
      final reply = await _sender(endpoint, {'appId': ShareLinks.appId,
        'batchId': flight['batchId'], 'messages': flight['messages']}, _data['token'] as String, _cancel!);
      final body = reply.body;
      if ((reply.status == 200 || reply.status == 201) && body['ok'] == true) {
        final ids = _rows(flight['messages']).map((item) => item['id']).toSet();
        final accepted = body['acceptedIds'];
        if (body['batchId'] != flight['batchId'] || accepted is! List || accepted.length != ids.length ||
            accepted.toSet().length != ids.length || !ids.containsAll(accepted) || body['receivedAt'] is! int) {
          throw const FormatException('Feedback acknowledgement differs from batch');
        }
        final delay = _serverDelay(body, 'nextAllowedAt');
        await _exclusive(() async {
          final next = _copy();
          (next['pending'] as List).removeWhere((dynamic item) => ids.contains((item as Map)['id']));
          next['sent'] = [..._rows(flight['messages']).map((item) => {...item, 'submittedAt': body['receivedAt']}), ...sent].take(50).toList();
          next['flight'] = null; next['blocked'] = false; next['failures'] = 0;
          next['notBefore'] = _clock().toUtc().millisecondsSinceEpoch + delay * 1000;
          await _commit(next);
        });
        failure.value = null;
      } else if (reply.status == 429 && body['errorCode'] == 'RATE_LIMITED') {
        final delay = _serverDelay(body, 'retryAt');
        await _exclusive(() async {
          final next = _copy();
          if (canThaw) next['flight'] = null;
          next['notBefore'] = _clock().toUtc().millisecondsSinceEpoch + max(1, delay) * 1000;
          await _commit(next);
        });
        failure.value = body['scope'] == 'ip' ? 'IP_DAILY_LIMIT' : 'RATE_LIMITED';
      } else if (reply.status >= 400 && reply.status < 500) {
        await _exclusive(() async { final next = _copy(); next['blocked'] = true; await _commit(next); });
        failure.value = 'SUBMISSION_REJECTED';
      } else {
        throw StateError('Feedback server unavailable');
      }
    } catch (_) {
      failure.value = ready.value ? 'SEND_DEFERRED' : 'LOCAL_STORAGE_UNAVAILABLE';
      if (ready.value) {
        try {
          await _exclusive(() async {
            final next = _copy();
            final attempts = min(8, (next['failures'] as int) + 1);
            next['failures'] = attempts;
            next['notBefore'] = _clock().toUtc().millisecondsSinceEpoch + min(3600, 300 * (1 << (attempts - 1))) * 1000;
            await _commit(next);
          });
        } catch (_) { failure.value = 'LOCAL_STORAGE_UNAVAILABLE'; }
      }
    } finally {
      _cancel = null;
      sending.value = false;
      _schedule();
    }
  }

  void _schedule() {
    _timer?.cancel();
    if (_closed || !_foreground || !ready.value || pending.isEmpty || _data['blocked'] == true) return;
    final remaining = (_data['notBefore'] as int) - _clock().toUtc().millisecondsSinceEpoch;
    _timer = Timer(Duration(milliseconds: remaining > 0 ? remaining.clamp(1000, 3600000).toInt() : 60000), () => unawaited(poll()));
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    _foreground = state == AppLifecycleState.resumed;
    if (_foreground) { unawaited(poll()); }
    else { _timer?.cancel(); _cancel?.cancel('background'); }
  }

  @override
  void onClose() {
    _closed = true;
    _timer?.cancel();
    _cancel?.cancel('closed');
    WidgetsBinding.instance.removeObserver(this);
    super.onClose();
  }
}
