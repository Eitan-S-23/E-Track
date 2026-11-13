import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:math';

import 'package:crypto/crypto.dart';
import 'package:dio/dio.dart';
import 'package:flutter/widgets.dart';
import 'package:get/get.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../config/share_links.dart';
import '../ota/ota_device_info.dart';

typedef InventorySender = Future<Map<String, dynamic>> Function(
    Uri uri, Map<String, dynamic>? body, String token, CancelToken cancel);

enum InventoryReportStatus { waiting, busy, sending, reported, retrying, disabled }

/// Optional telemetry, independent of the update or BLE task's success path.
class VersionInventoryService extends GetxService with WidgetsBindingObserver {
  VersionInventoryService({
    required this.readAppIdentity,
    required this.canReport,
    Uri? endpoint,
    InventorySender? sender,
    DateTime Function()? clock,
    bool? supported,
    this.runtimeActivity = const [],
  })  : endpoint = endpoint ?? _configuredEndpoint(),
        _sender = sender ?? _send,
        _clock = clock ?? DateTime.now,
        _supported = supported ?? Platform.isAndroid;

  static const _prefix = 'version_inventory_v1_';
  static const _day = Duration(days: 1);
  static const _controlInterval = Duration(hours: 4);
  final Future<Map<String, dynamic>> Function() readAppIdentity;
  final bool Function() canReport;
  final Uri? endpoint;
  final InventorySender _sender;
  final DateTime Function() _clock;
  final bool _supported;
  final List<Stream<bool>> runtimeActivity;
  final List<StreamSubscription<bool>> _activitySubscriptions = [];
  final enabled = true.obs;
  final ready = false.obs;
  final status = InventoryReportStatus.waiting.obs;
  final lastReportedAt = Rxn<DateTime>();
  final nextAttemptAt = Rxn<DateTime>();
  final failureCode = RxnString();
  bool get available => _supported && endpoint != null;
  final Map<String, Map<String, dynamic>> _devices = {};
  Future<void>? _initialization;
  SharedPreferences? _prefs;
  Map<String, dynamic>? _app;
  String _token = '';
  String _refreshId = '';
  String _lastState = '';
  DateTime? _lastReport;
  DateTime? _lastControl;
  DateTime? _retryAfter;
  CancelToken? _cancel;
  Timer? _deferred;
  bool _running = false;
  bool _closed = false;
  bool _foreground = true;
  bool _pending = false;

  static Uri? _configuredEndpoint() {
    const source = ShareLinks.cloudflareUpdateManifestUrl;
    final uri = Uri.tryParse(source);
    if (uri == null || uri.scheme != 'https' || uri.host.isEmpty || uri.userInfo.isNotEmpty) return null;
    return uri.replace(path: '/api/public/version-inventory', query: '', fragment: '');
  }

  static Future<Map<String, dynamic>> _send(Uri uri,
      Map<String, dynamic>? body, String token, CancelToken cancel) async {
    final dio = Dio(BaseOptions(
      connectTimeout: const Duration(seconds: 8),
      receiveTimeout: const Duration(seconds: 8),
      sendTimeout: const Duration(seconds: 8),
      responseType: ResponseType.json,
    ));
    try {
      final result = await dio.requestUri<Map<String, dynamic>>(uri,
          data: body, cancelToken: cancel,
          options: Options(method: body == null ? 'GET' : 'POST',
              followRedirects: false,
              headers: body == null ? null : {'Authorization': 'Bearer $token'},
              contentType: Headers.jsonContentType));
      if (result.data == null || result.data!['ok'] != true) throw StateError('Inventory response rejected');
      return result.data!;
    } finally { dio.close(); }
  }

  Future<void> initialize() => _initialization ??= _initialize();

  Future<void> _initialize() async {
    final prefs = await SharedPreferences.getInstance();
    _prefs = prefs;
    enabled.value = prefs.getBool('${_prefix}enabled') ?? true;
    _token = prefs.getString('${_prefix}token') ?? '';
    if (!RegExp(r'^[0-9a-f]{64}$').hasMatch(_token)) {
      final random = Random.secure();
      _token = List.generate(32, (_) => random.nextInt(256).toRadixString(16).padLeft(2, '0')).join();
      await prefs.setString('${_prefix}token', _token);
    }
    _refreshId = prefs.getString('${_prefix}refresh') ?? '';
    _lastState = prefs.getString('${_prefix}state') ?? '';
    _lastReport = DateTime.tryParse(prefs.getString('${_prefix}reported') ?? '');
    _lastControl = DateTime.tryParse(prefs.getString('${_prefix}control') ?? '');
    _retryAfter = DateTime.tryParse(prefs.getString('${_prefix}retry') ?? '');
    lastReportedAt.value = _lastReport;
    failureCode.value = prefs.getString('${_prefix}failure');
    status.value = !enabled.value ? InventoryReportStatus.disabled
        : (_retryAfter?.isAfter(_clock().toUtc()) ?? false) ? InventoryReportStatus.retrying
        : _lastReport != null ? InventoryReportStatus.reported : InventoryReportStatus.waiting;
    try {
      final stored = jsonDecode(prefs.getString('${_prefix}devices') ?? '[]');
      if (stored is List && stored.length <= 4) {
        for (final value in stored) {
          if (value is Map<String, dynamic> && value['deviceKey'] is String &&
              value['observedAt'] is String && DateTime.tryParse(value['observedAt'] as String) != null) {
            _devices[value['deviceKey'] as String] = value;
          }
        }
      }
    } catch (_) { _devices.clear(); }
    ready.value = true;
  }

  @override
  void onInit() {
    super.onInit();
    if (!_supported || endpoint == null) return;
    unawaited(initialize().catchError((Object error) {}));
    WidgetsBinding.instance.addObserver(this);
    for (final activity in runtimeActivity) {
      _activitySubscriptions.add(activity.listen((busy) {
        if (!busy) _schedule();
      }));
    }
    _schedule();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    _foreground = state == AppLifecycleState.resumed;
    if (_foreground) {
      _schedule();
    } else {
      _deferred?.cancel();
      nextAttemptAt.value = null;
      _cancel?.cancel('Reporting deferred until foreground');
    }
  }

  void _schedule() {
    _pending = true;
    if (_running) return;
    _arm(_clock().toUtc().add(const Duration(seconds: 5)));
  }

  void _arm(DateTime when) {
    if (_closed || !_foreground || !_supported || endpoint == null ||
        (ready.value && !enabled.value)) return;
    if (_retryAfter != null && _retryAfter!.isAfter(when)) when = _retryAfter!;
    // Keep the earliest wake-up so repeated identity events cannot starve it.
    if ((_deferred?.isActive ?? false) && nextAttemptAt.value != null &&
        !nextAttemptAt.value!.isAfter(when)) return;
    _deferred?.cancel();
    nextAttemptAt.value = when;
    final delay = when.difference(_clock().toUtc());
    _deferred = Timer(delay.isNegative ? Duration.zero : delay, () {
      _deferred = null;
      nextAttemptAt.value = null;
      unawaited(poll());
    });
  }

  void _scheduleNext() {
    if (_closed || !_foreground || !enabled.value) return;
    if (!canReport()) {
      status.value = InventoryReportStatus.busy;
      return; // The runtime's idle event resumes the pending snapshot.
    }
    final now = _clock().toUtc();
    if (_retryAfter?.isAfter(now) ?? false) {
      _arm(_retryAfter!);
    } else if (_pending) {
      _schedule();
    } else {
      final control = (_lastControl ?? now).add(_controlInterval);
      var report = (_lastReport ?? now).add(_day);
      // Server receipt time can lag the phone clock. Never spin on an old receipt.
      if (!report.isAfter(now)) report = now.add(_controlInterval);
      _arm(control.isBefore(report) ? control : report);
    }
  }

  Future<void> setEnabled(bool value) async {
    await initialize();
    enabled.value = value;
    await _prefs!.setBool('${_prefix}enabled', value);
    if (!value) {
      _deferred?.cancel();
      nextAttemptAt.value = null;
      status.value = InventoryReportStatus.disabled;
      _cancel?.cancel('Reporting disabled');
    }
    else {
      _retryAfter = null;
      failureCode.value = null;
      status.value = InventoryReportStatus.waiting;
      await _prefs!.remove('${_prefix}retry');
      await _prefs!.remove('${_prefix}failure');
      _schedule();
    }
  }

  void observeDevice(String address, DeviceOtaInfo info) {
    if (_closed || !_supported || endpoint == null) return;
    unawaited(_rememberDevice(address, info));
  }

  Future<void> _rememberDevice(String address, DeviceOtaInfo info) async {
    try {
      await initialize();
      if (!enabled.value || _closed) return;
      final key = sha256.convert(utf8.encode('$_token:${address.toLowerCase()}')).toString();
      // Local address never leaves the phone; this is not a globally unique MCU ID.
      _devices.remove(key);
      _devices[key] = {
        'deviceKey': key, 'identityScope': 'installation', 'deviceModel': info.deviceModel,
        'versionCode': info.currentVersionCode, 'imageSha256': info.currentImageSha256Hex,
        'hardwareRevision': info.hardwareRevision, 'layoutId': info.layoutId,
        'observationId': _uuid(), 'observedAt': _clock().toUtc().toIso8601String(),
      };
      while (_devices.length > 4) { _devices.remove(_devices.keys.first); }
      await _prefs!.setString('${_prefix}devices', jsonEncode(_devices.values.toList()));
      _schedule();
    } catch (_) { /* Reporting must not change an already-confirmed OTA outcome. */ }
  }

  String _uuid() {
    final random = Random.secure();
    final bytes = List.generate(16, (_) => random.nextInt(256));
    bytes[6] = (bytes[6] & 15) | 64;
    bytes[8] = (bytes[8] & 63) | 128;
    final hex = bytes.map((b) => b.toRadixString(16).padLeft(2, '0')).join();
    return '${hex.substring(0, 8)}-${hex.substring(8, 12)}-${hex.substring(12, 16)}-${hex.substring(16, 20)}-${hex.substring(20)}';
  }

  Future<void> poll() async {
    if (_closed || !_foreground || !_supported || endpoint == null) return;
    if (_running) { _pending = true; return; }
    _running = true;
    _pending = false;
    _deferred?.cancel();
    nextAttemptAt.value = null;
    try {
      await initialize();
      final now = _clock().toUtc();
      if (!enabled.value || _closed || !_foreground || !canReport() || (_retryAfter?.isAfter(now) ?? false)) return;
      _app ??= await readAppIdentity();
      if (!enabled.value || _closed || !_foreground || !canReport()) return;
      final app = _app!;
      if (app['versionCode'] is! int || app['versionName'] is! String ||
          !RegExp(r'^[0-9a-f]{64}$').hasMatch(app['imageSha256']?.toString() ?? '')) {
        _app = null;
        throw StateError('APP_IDENTITY_UNAVAILABLE');
      }
      final devices = _devices.values.where((d) {
        final age = now.difference(DateTime.parse(d['observedAt'] as String));
        return !age.isNegative && age <= const Duration(days: 90);
      }).map((d) => Map<String, dynamic>.from(d)).toList();
      devices.sort((a, b) => (a['deviceKey'] as String).compareTo(b['deviceKey'] as String));
      // Daily coalescing ignores a fresh read of an otherwise unchanged MCU.
      final state = jsonEncode([app, devices.map((d) => {...d}..remove('observationId')..remove('observedAt')).toList()]);
      var due = state != _lastState || _lastReport == null || now.isBefore(_lastReport!) || now.difference(_lastReport!) >= _day;
      _cancel = CancelToken();
      if (!due && (_lastControl == null || now.difference(_lastControl!) >= _controlInterval)) {
        final result = await _sender(endpoint!.replace(path: '${endpoint!.path}/control'), null, '', _cancel!);
        if (_closed || !enabled.value || !_foreground || _cancel!.isCancelled) return;
        if (result['refreshId'] is! String) throw StateError('Missing refresh identity');
        due = result['refreshId'] != _refreshId;
        _lastControl = now;
        await _prefs!.setString('${_prefix}control', now.toIso8601String());
      }
      if (!due) {
        status.value = _lastReport != null ? InventoryReportStatus.reported : InventoryReportStatus.waiting;
        return;
      }
      if (!enabled.value || _closed || !_foreground || !canReport()) return;
      status.value = InventoryReportStatus.sending;
      final sequence = (_prefs!.getInt('${_prefix}sequence') ?? 0) + 1;
      await _prefs!.setInt('${_prefix}sequence', sequence);
      if (_closed || !enabled.value || !_foreground || !canReport() || _cancel!.isCancelled) return;
      final body = <String, dynamic>{'appId': ShareLinks.appId, 'platform': 'android', 'sequence': sequence,
        ...app, 'devices': devices.map((d) {
          final observed = DateTime.parse(d.remove('observedAt') as String);
          return {...d, 'ageSeconds': now.difference(observed).inSeconds};
        }).toList()};
      final result = await _sender(endpoint!, body, _token, _cancel!);
      if (_closed || !enabled.value || !_foreground || _cancel!.isCancelled) return;
      final accepted = result['accepted'] == true;
      final reportedAt = result['reportedAt'];
      final validReceipt = reportedAt is int && reportedAt > 0 && reportedAt <= 8640000000000;
      final receivedSequence = result['sequence'];
      if (result['ok'] == true && receivedSequence is int &&
          receivedSequence > sequence && receivedSequence <= 9007199254740991) {
        await _prefs!.setInt('${_prefix}sequence', receivedSequence);
      }
      final acknowledged = accepted || (result['acknowledged'] == true && validReceipt);
      if (result['ok'] != true || !acknowledged || result['refreshId'] is! String ||
          (reportedAt != null && !validReceipt)) {
        throw StateError('REPORT_NOT_ACCEPTED');
      }
      _refreshId = result['refreshId'] as String;
      _lastReport = validReceipt
          ? DateTime.fromMillisecondsSinceEpoch(reportedAt * 1000, isUtc: true) : now;
      _lastControl = now;
      _lastState = state;
      _retryAfter = null;
      lastReportedAt.value = _lastReport;
      failureCode.value = null;
      status.value = InventoryReportStatus.reported;
      await _prefs!.setString('${_prefix}refresh', _refreshId);
      await _prefs!.setString('${_prefix}reported', _lastReport!.toIso8601String());
      await _prefs!.setString('${_prefix}control', now.toIso8601String());
      await _prefs!.setString('${_prefix}state', state);
      await _prefs!.remove('${_prefix}retry');
      await _prefs!.remove('${_prefix}failure');
    } catch (error) {
      // Lifecycle/consent cancellation is not a failed endpoint or an hour ban.
      if (_closed || !_foreground || !enabled.value || (_cancel?.isCancelled ?? false)) return;
      _retryAfter = _clock().toUtc().add(const Duration(hours: 1));
      var code = 'REPORT_UNAVAILABLE';
      if (error is DioException) {
        final data = error.response?.data;
        final serverCode = data is Map ? data['errorCode'] : null;
        code = serverCode is String && RegExp(r'^[A-Z_]{1,64}$').hasMatch(serverCode)
            ? serverCode : 'NETWORK_ERROR';
      } else if (error is StateError &&
          ['REPORT_NOT_ACCEPTED', 'APP_IDENTITY_UNAVAILABLE'].contains(error.message)) {
        code = error.message;
      }
      failureCode.value = code;
      status.value = InventoryReportStatus.retrying;
      try {
        await _prefs?.setString('${_prefix}retry', _retryAfter!.toIso8601String());
        await _prefs?.setString('${_prefix}failure', code);
      } catch (_) { /* Best-effort telemetry only. */ }
    } finally {
      _running = false;
      _cancel = null;
      _scheduleNext();
    }
  }

  @override
  void onClose() {
    _closed = true;
    _deferred?.cancel();
    nextAttemptAt.value = null;
    for (final subscription in _activitySubscriptions) { unawaited(subscription.cancel()); }
    _cancel?.cancel('Reporting service closed');
    if (_supported && endpoint != null) WidgetsBinding.instance.removeObserver(this);
    super.onClose();
  }
}
