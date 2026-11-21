import 'dart:async';
import 'dart:convert';
import 'dart:math';
import 'package:dio/dio.dart';
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
  final String accountId, id;
  final bool automatic;
  Map<String, String> headers({bool refresh = false}) => {
    'X-Update-Check-Id': id, 'X-Update-Check-Kind': automatic ? 'automatic' : 'manual',
    if (refresh) 'X-Update-Refresh': '1',
  };
}

/// Tokens are stored by the OS vault, never in diagnostics or ordinary preferences.
class AccountService extends GetxService {
  AccountService({Dio? dio, FlutterSecureStorage? storage, Uri? endpoint})
      : _dio = dio ?? Dio(BaseOptions(connectTimeout: const Duration(seconds: 15),
          receiveTimeout: const Duration(seconds: 20), sendTimeout: const Duration(seconds: 15))),
        _storage = storage ?? const FlutterSecureStorage(),
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
  String? _token;
  Future<void>? _initialization;
  int _generation = 0;
  int get generation => _generation;
  String? get accountId => account.value?['id'] as String?;
  bool get loggedIn => _token != null && accountId != null;

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
          profile is! Map || profile['id'] is! String) return;
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
        handler.next(options);
      } catch (error) {
        handler.reject(DioException(requestOptions: options, error: error,
          type: DioExceptionType.cancel, message: 'LOGIN_REQUIRED'));
      }
    }));
  }

  Future<Map<String, dynamic>> call(String path, {Map<String, dynamic>? body, bool anonymous = false, String? uid}) async {
    await initialize();
    final uri = endpoint.replace(path: path, query: '', fragment: '');
    if (!isCloudUri(uri)) throw const AccountException('INVALID_ENDPOINT', '账号服务地址无效');
    final captured = _generation;
    final auth = anonymous ? <String, String>{} : await headers(uri, uid: uid);
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
    'CHECK_QUOTA_EXCEEDED' => '该类检查今日已用完 5 次，次日北京时间零点恢复',
    'CHECK_TOO_SOON' => '距离上次自动检查不足一小时',
    'RATE_LIMITED' => '操作太频繁，请稍后重试',
    'EMAIL_VERIFICATION_REQUIRED' => '邮箱验证码无效或已过期',
    'CAS_CONFLICT' => '账号已存在或设置已变化，请刷新后重试',
    'INVALID_PARAMETER' => '请检查输入内容',
    _ => '云端请求未完成，请检查网络后重试',
  };

  Future<void> loadSettings() async => settings.assignAll(await call('/api/auth/status', anonymous: true));
  Future<void> login(String username, String password) async {
    final result = await call('/api/auth/login', body: {'username': username.trim(), 'password': password}, anonymous: true);
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
    _token = token;
    account.value = Map<String, dynamic>.from(result['account'] as Map);
    quota.assignAll(Map<String, dynamic>.from(result['quota'] as Map? ?? {}));
  }
  Future<void> refresh() async {
    final result = await call('/api/account/me');
    account.value = Map<String, dynamic>.from(result['account'] as Map);
    quota.assignAll(Map<String, dynamic>.from(result['quota'] as Map));
    final list = await call('/api/account/devices');
    devices.assignAll((list['devices'] as List).map((d) => Map<String, dynamic>.from(d as Map)));
  }
  Future<void> authorizeOta(String uid) async {
    await call('/api/account/ota/authorize', body: {}, uid: uid);
  }
  Future<void> logout() async {
    try { if (loggedIn) await call('/api/account/logout', body: {}); }
    finally { await _clear(); }
  }
  Future<void> _clear() async {
    _generation++;
    _token = null;
    account.value = null;
    quota.clear(); devices.clear();
    await _storage.delete(key: _storageKey);
  }
}
