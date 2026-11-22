import 'dart:async';
import 'dart:convert';
import 'dart:math';
import 'dart:io';
import 'package:dio/dio.dart';
import 'package:device_info_plus/device_info_plus.dart';
import 'package:package_info_plus/package_info_plus.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:get/get.dart' hide Response;
import '../config/share_links.dart';

class AccountException implements Exception {
  const AccountException(this.code, this.message);
  final String code, message;
  @override
  String toString() => message;
}

class AccountCheck {
  AccountCheck(this.accountId, {required this.automatic}) : id = AccountService.nonce();
  AccountCheck.restored(this.accountId, this.id, {required this.automatic});
  final String accountId, id;
  final bool automatic;
  Map<String, String> headers({bool refresh = false}) => {
    'X-Update-Check-Id': id, 'X-Update-Check-Kind': automatic ? 'automatic' : 'manual',
    if (refresh) 'X-Update-Refresh': '1',
  };
}

/// Tokens are stored by the OS vault, never in diagnostics or ordinary preferences.
class AccountService extends GetxService {
  AccountService({Dio? dio, FlutterSecureStorage? storage, Uri? endpoint,
      Future<Map<String, dynamic>> Function()? readTerminal})
      : _dio = dio ?? Dio(BaseOptions(connectTimeout: const Duration(seconds: 15),
          receiveTimeout: const Duration(seconds: 20), sendTimeout: const Duration(seconds: 15))),
        _storage = storage ?? const FlutterSecureStorage(), _readTerminal = readTerminal ?? _terminalMetadata,
        endpoint = endpoint ?? Uri.parse(ShareLinks.cloudflareUpdateManifestUrl);

  static AccountService get to => Get.find<AccountService>();
  static const _storageKey = 'etrack_account_session_v1';
  final Dio _dio;
  final FlutterSecureStorage _storage;
  final Uri endpoint;
  final account = Rxn<Map<String, dynamic>>();
  final quota = <String, dynamic>{}.obs;
  final settings = <String, dynamic>{}.obs;
  final devices = <Map<String, dynamic>>[].obs;
  final sessions = <Map<String, dynamic>>[].obs;
  final terminalReportProblem = RxnString();
  final Future<Map<String, dynamic>> Function() _readTerminal;
  Future<Map<String, dynamic>>? _terminalValue;
  DateTime? _terminalReported;
  final Map<String, DateTime> _deviceReports = {};
  String? _token;
  Future<void>? _initialization;
  int _generation = 0;
  int get generation => _generation;
  String? get accountId => account.value?['id'] as String?;
  bool get loggedIn => _token != null && accountId != null;

  static Future<Map<String, dynamic>> _terminalMetadata() async {
    final value = <String, dynamic>{'platform': Platform.operatingSystem,
      'versionName': '', 'versionCode': 0, 'model': '', 'osVersion': ''};
    try {
      final package = await PackageInfo.fromPlatform();
      value['versionName'] = package.version; value['versionCode'] = int.tryParse(package.buildNumber) ?? 0;
    } catch (_) { /* Legacy or unsupported host metadata stays unknown. */ }
    try {
      if (Platform.isAndroid) {
        final phone = await DeviceInfoPlugin().androidInfo;
        value['model'] = '${phone.brand} ${phone.model}';
        value['osVersion'] = '${phone.version.release} (SDK ${phone.version.sdkInt})';
      }
    } catch (_) { /* No hardware identifiers or account name are collected. */ }
    for (final key in ['versionName', 'model', 'osVersion']) {
      final clean = value[key].toString().replaceAll(RegExp(r'[\x00-\x1f\x7f]'), '').trim();
      final limit = key == 'versionName' ? 64 : 80;
      value[key] = clean.substring(0, min(clean.length, limit));
    }
    return value;
  }
  Future<Map<String, dynamic>> _terminal() => _terminalValue ??= _loadTerminal();
  Future<Map<String, dynamic>> _loadTerminal() async {
    const key = 'etrack_account_installation_v1';
    var id = await _storage.read(key: key);
    if (id == null || !RegExp(r'^[0-9a-f]{32}$').hasMatch(id)) {
      id = nonce(); await _storage.write(key: key, value: id);
    }
    return {...await _readTerminal(), 'installationId': id};
  }

  Future<void> reportTerminal() async {
    if (!loggedIn) return;
    final captured = _generation, terminal = await _terminal();
    if (captured != _generation || !loggedIn) return;
    final now = DateTime.now();
    if (_terminalReported != null && !now.isBefore(_terminalReported!) && now.difference(_terminalReported!) < const Duration(minutes: 5)) return;
    await call('/api/account/terminal', body: {'terminal': terminal});
    if (captured == _generation) _terminalReported = now;
  }

  /// Best-effort identity observation; never changes the BLE/OTA outcome or quota.
  Future<void> observeDevice(String uid, int firmwareVersion, String imageSha256, {bool force = false}) async {
    if (!loggedIn) return;
    final captured = _generation, key = '$uid:$firmwareVersion:$imageSha256', now = DateTime.now();
    final previous = _deviceReports[key];
    if (!force && previous != null && !now.isBefore(previous) && now.difference(previous) < const Duration(minutes: 5)) return;
    _deviceReports[key] = now;
    while (_deviceReports.length > 100) { _deviceReports.remove(_deviceReports.keys.first); }
    try {
      await reportTerminal();
      if (captured != _generation || !loggedIn) return;
      await call('/api/account/devices/observe', uid: uid, body: {'firmwareVersion': firmwareVersion, 'imageSha256': imageSha256});
      if (captured == _generation) terminalReportProblem.value = null;
    } on AccountException catch (error) {
      if (captured == _generation) terminalReportProblem.value = error.code;
    } catch (_) {
      if (captured == _generation) terminalReportProblem.value = 'REPORT_UNAVAILABLE';
    }
  }

  static String nonce() {
    final random = Random.secure();
    return List.generate(16, (_) => random.nextInt(256).toRadixString(16).padLeft(2, '0')).join();
  }
  @override
  void onInit() { super.onInit(); unawaited(initialize()); }
  Future<void> initialize() => _initialization ??= _restore();
  Future<void> _restore() async {
    try {
      final raw = await _storage.read(key: _storageKey);
      if (raw == null) return;
      final saved = jsonDecode(raw) as Map<String, dynamic>;
      final token = saved['token'];
      final profile = saved['account'];
      if (token is! String || !RegExp(r'^acct_[0-9a-f]{64}$').hasMatch(token) ||
          profile is! Map || profile['id'] is! String) { return; }
      _token = token;
      account.value = Map<String, dynamic>.from(profile);
    } catch (_) { /* An unavailable OS vault leaves cloud features signed out, not Bluetooth. */ }
  }

  Future<void> requireLogin() async {
    await initialize();
    if (!loggedIn) throw const AccountException('LOGIN_REQUIRED', '请先登录，蓝牙本地功能无需登录');
  }
  Future<AccountCheck> newCheck({required bool automatic}) async {
    await requireLogin();
    return AccountCheck(accountId!, automatic: automatic);
  }

  bool isCloudUri(Uri uri) {
    if (uri.scheme != 'https' || uri.userInfo.isNotEmpty || !uri.path.startsWith('/api/')) return false;
    final firmware = Uri.tryParse(ShareLinks.firmwareLatestUrl);
    return (endpoint.hasAuthority && uri.origin == endpoint.origin) ||
        (firmware != null && firmware.hasAuthority && uri.origin == firmware.origin);
  }
  Future<Map<String, String>> headers(Uri uri, {String? uid}) async {
    await requireLogin();
    if (!isCloudUri(uri)) return const {};
    return {'Authorization': 'Bearer $_token', if (uid != null) 'X-Device-Uid': uid};
  }
  void protect(Dio dio, {String? Function()? deviceUid}) {
    dio.interceptors.add(InterceptorsWrapper(onRequest: (options, handler) async {
      if (!isCloudUri(options.uri) || options.path.startsWith('/api/auth/')) { handler.next(options); return; }
      try {
        options.headers.addAll(await headers(options.uri, uid: deviceUid?.call()));
        options.followRedirects = false; // Never forward an account token to a redirect target.
        if (options.method == 'GET' && options.uri.path == '/api/public/github-fallback') {
          final validate = options.validateStatus;
          options.validateStatus = (status) => status == 302 || validate(status);
        }
        handler.next(options);
      } catch (error) {
        handler.reject(DioException(requestOptions: options, error: error,
          type: DioExceptionType.cancel, message: 'LOGIN_REQUIRED'));
      }
    }, onResponse: (response, handler) async {
      final request = response.requestOptions;
      if (response.statusCode != 302 || request.method != 'GET' ||
          !isCloudUri(request.uri) || request.uri.path != '/api/public/github-fallback') {
        handler.next(response);
        return;
      }
      final locations = response.headers['location'];
      final target = Uri.tryParse(locations?.length == 1 ? locations!.single : '');
      final base = Uri.parse(ShareLinks.githubReleaseDownloadBaseUrl);
      final valid = target != null && target.scheme == 'https' && target.hasAuthority && target.userInfo.isEmpty &&
          target.origin == base.origin && target.path.startsWith(base.path) &&
          target.pathSegments.length == base.pathSegments.length + 1 &&
          !target.pathSegments.contains('latest') && !target.hasQuery && !target.hasFragment;
      if (!valid) {
        if (response.data is ResponseBody) await (response.data as ResponseBody).stream.listen(null).cancel();
        handler.reject(DioException(requestOptions: request, response: response,
          type: DioExceptionType.badResponse, message: 'Untrusted update download redirect'));
        return;
      }
      try {
        if (response.data is ResponseBody) await (response.data as ResponseBody).stream.listen(null).cancel();
        // Only transport headers cross the boundary; no session, UID, check ID or cookies.
        final headers = <String, dynamic>{
          for (final entry in request.headers.entries)
            if (const {'accept', 'accept-encoding', 'range', 'if-range'}.contains(entry.key.toLowerCase()))
              entry.key: entry.value,
        };
        final redirected = await dio.fetch<dynamic>(request.copyWith(
          path: target.toString(), baseUrl: '', queryParameters: {}, headers: headers,
          followRedirects: true, validateStatus: (status) => status != null && status >= 200 && status < 300,
        ));
        handler.resolve(redirected);
      } on DioException catch (error) {
        handler.reject(error);
      } catch (error) {
        handler.reject(DioException(requestOptions: request, error: error));
      }
    }));
  }

  Future<Map<String, dynamic>> call(String path, {Map<String, dynamic>? body, bool anonymous = false, String? uid}) async {
    await initialize();
    final uri = endpoint.replace(path: path, query: '', fragment: '');
    if (!isCloudUri(uri)) throw const AccountException('INVALID_ENDPOINT', '账号服务地址无效');
    final captured = _generation;
    final auth = anonymous ? <String, String>{} : await headers(uri, uid: uid);
    if (captured != _generation) throw const AccountException('ACCOUNT_CHANGED', '账号已变化，请重试');
    try {
      final response = await _dio.requestUri<Map<String, dynamic>>(uri, data: body,
        options: Options(method: body == null ? 'GET' : 'POST', headers: auth,
          followRedirects: false, contentType: Headers.jsonContentType));
      if (captured != _generation) throw const AccountException('ACCOUNT_CHANGED', '账号已切换，请重试');
      return response.data ?? <String, dynamic>{};
    } on DioException catch (error) {
      final data = error.response?.data;
      final code = data is Map ? data['errorCode']?.toString() ?? 'NETWORK' : 'NETWORK';
      if (captured == _generation && (code == 'LOGIN_REQUIRED' || code == 'ACCOUNT_DISABLED')) await _clear();
      throw AccountException(code, messageFor(code));
    }
  }

  static String messageFor(String code) => switch (code) {
    'LOGIN_REQUIRED' => '请先登录，登录过期后需重新登录',
    'INVALID_CREDENTIALS' => '账号或密码不正确',
    'ACCOUNT_DISABLED' => '账号已停用，请联系管理员',
    'REGISTRATION_DISABLED' => '管理员已关闭注册',
    'DEVICE_NOT_BOUND' => '请先在账号页绑定当前码表',
    'DEVICE_ALREADY_BOUND' => '码表已绑定其他账号，请先由原账号解绑',
    'CHECK_QUOTA_EXCEEDED' => '该类检查今日额度已用完，次日北京时间零点恢复',
    'CHECK_TOO_SOON' => '距离上次自动检查不足一小时',
    'RATE_LIMITED' => '操作太频繁，请稍后重试',
    'EMAIL_VERIFICATION_REQUIRED' => '邮箱验证码无效或已过期',
    'EMAIL_DELIVERY_UNAVAILABLE' => '邮件发送尚未配置，请联系管理员',
    'EMAIL_DELIVERY_FAILED' => '验证码发送未成功，请稍后重试；如已收到邮件，请以重新获取的验证码为准',
    'EMAIL_SEND_COOLDOWN' => '请等待一分钟后再获取验证码',
    'BACKEND_UNAVAILABLE' => '账号服务暂时不可用，请稍后重试',
    'CAS_CONFLICT' => '账号已存在或设置已变化，请刷新后重试',
    'INVALID_PARAMETER' => '请检查输入内容',
    _ => '云端请求未完成，请检查网络后重试',
  };

  Future<void> loadSettings() async => settings.assignAll(await call('/api/auth/status', anonymous: true));
  Future<void> login(String username, String password) async {
    await initialize();
    final before = _generation, terminal = await _terminal();
    if (before != _generation) throw const AccountException('ACCOUNT_CHANGED', '账号已变化，请重试');
    final result = await call('/api/auth/login', body: {'username': username.trim(), 'password': password, 'terminal': terminal}, anonymous: true);
    final token = result['token'];
    if (token is! String || !RegExp(r'^acct_[0-9a-f]{64}$').hasMatch(token) || result['account'] is! Map) {
      throw const AccountException('INVALID_RESPONSE', '账号服务响应无效');
    }
    final captured = _generation;
    await _storage.write(key: _storageKey, value: jsonEncode({'token': token, 'account': result['account']}));
    if (captured != _generation) {
      await _storage.delete(key: _storageKey);
      throw const AccountException('ACCOUNT_CHANGED', '账号已变化，请重试');
    }
    _generation++;
    _terminalReported = DateTime.now(); _deviceReports.clear(); sessions.clear();
    _token = token;
    account.value = Map<String, dynamic>.from(result['account'] as Map);
    quota.assignAll(Map<String, dynamic>.from(result['quota'] as Map? ?? {}));
  }
  Future<void> refresh() async {
    await reportTerminal();
    final result = await call('/api/account/me');
    account.value = Map<String, dynamic>.from(result['account'] as Map);
    quota.assignAll(Map<String, dynamic>.from(result['quota'] as Map));
    final list = await call('/api/account/devices');
    devices.assignAll((list['devices'] as List).map((d) => Map<String, dynamic>.from(d as Map)));
    final logins = await call('/api/account/sessions');
    sessions.assignAll((logins['sessions'] as List? ?? []).map((s) => Map<String, dynamic>.from(s as Map)));
  }
  Future<void> revokeSession(Map<String, dynamic> session) async {
    await call('/api/account/sessions/revoke', body: {'sessionId': session['id']});
    if (session['current'] == true || session['current'] == 1) { await _clear(); }
    else {
      try { await refresh(); }
      catch (_) { throw const AccountException('REFRESH_FAILED', '登录已撤销，但列表刷新失败；请刷新查看，不必重复操作'); }
    }
  }
  Future<void> authorizeOta(String uid) async {
    await call('/api/account/ota/authorize', body: {}, uid: uid);
  }
  Future<void> savePreparation(String uid, Map<String, dynamic> value) async {
    await requireLogin();
    if (!RegExp(r'^[0-9a-f]{24}$').hasMatch(uid)) return;
    await _storage.write(key: 'etrack_prepared_${accountId}_$uid', value: jsonEncode(value));
  }
  Future<Map<String, dynamic>?> loadPreparation(String uid) async {
    await requireLogin();
    if (!RegExp(r'^[0-9a-f]{24}$').hasMatch(uid)) return null;
    final raw = await _storage.read(key: 'etrack_prepared_${accountId}_$uid');
    if (raw == null || raw.length > 65536) return null;
    try { return jsonDecode(raw) as Map<String, dynamic>; } catch (_) { return null; }
  }
  Future<void> logout() async {
    try { if (loggedIn) await call('/api/account/logout', body: {}); }
    finally { await _clear(); }
  }
  Future<void> _clear() async {
    _generation++;
    _token = null;
    account.value = null;
    quota.clear(); devices.clear(); sessions.clear(); _deviceReports.clear(); _terminalReported = null;
    terminalReportProblem.value = null;
    await _storage.delete(key: _storageKey);
  }
}
