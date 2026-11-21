import 'package:ble_monitor/services/account_service.dart';
import 'package:dio/dio.dart';

/// Explicit authenticated fixture for transport tests; account admission has its own suite.
class TestAccountService extends AccountService {
  TestAccountService({this.signedIn = true});
  bool signedIn;
  int authorizations = 0;
  final preparations = <String, Map<String, dynamic>>{};
  @override
  Future<void> initialize() async {}
  @override
  String? get accountId => signedIn ? 'test-account' : null;
  @override
  bool get loggedIn => signedIn;
  @override
  Future<void> requireLogin() async {
    if (!signedIn) throw const AccountException('LOGIN_REQUIRED', 'Please sign in');
  }
  @override
  Future<Map<String, String>> headers(Uri uri, {String? uid}) async {
    await requireLogin();
    return {'Authorization': 'Bearer test-account-token', if (uid != null) 'X-Device-Uid': uid};
  }
  @override
  void protect(Dio dio, {String? Function()? deviceUid}) {}
  @override
  Future<void> authorizeOta(String uid) async { await requireLogin(); authorizations++; }
  @override
  Future<void> savePreparation(String uid, Map<String, dynamic> value) async { preparations[uid] = value; }
  @override
  Future<Map<String, dynamic>?> loadPreparation(String uid) async => preparations[uid];
}
