import 'dart:convert';
import 'dart:typed_data';
import 'package:ble_monitor/services/account_service.dart';
import 'package:dio/dio.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';

class _Http implements HttpClientAdapter {
  final requests = <RequestOptions>[];
  int status = 200;
  Map<String, dynamic> response = {};
  @override
  Future<ResponseBody> fetch(RequestOptions options, Stream<Uint8List>? stream, Future<void>? cancel) async {
    requests.add(options);
    return ResponseBody.fromString(jsonEncode(response), status, headers: {Headers.contentTypeHeader: ['application/json']});
  }
  @override
  void close({bool force = false}) {}
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  late Dio dio;
  late _Http http;
  late AccountService service;
  final endpoint = Uri.parse('https://account.example/api/public/latest');
  final token = 'acct_${'a' * 64}';
  setUp(() {
    FlutterSecureStorage.setMockInitialValues({});
    dio = Dio(); http = _Http(); dio.httpClientAdapter = http;
    service = AccountService(dio: dio, endpoint: endpoint);
  });
  Future<void> login() async {
    http.response = {'token': token, 'account': {'id': 'one', 'username': 'rider'}, 'quota': {
      'automatic': {'remaining': 5, 'limit': 5}, 'manual': {'remaining': 5, 'limit': 5}}};
    await service.login('rider', 'test-password');
  }
  test('anonymous cloud checks fail before HTTP while no Bluetooth service is required', () async {
    await expectLater(service.newCheck(automatic: false), throwsA(isA<AccountException>()));
    expect(http.requests, isEmpty);
  });
  test('secure session survives service recreation and separate check kinds get unique IDs', () async {
    await login();
    final restored = AccountService(dio: dio, endpoint: endpoint);
    await restored.initialize();
    expect(restored.accountId, 'one');
    final auto = await restored.newCheck(automatic: true), manual = await restored.newCheck(automatic: false);
    expect(auto.id, isNot(manual.id));
    expect(auto.headers()['X-Update-Check-Kind'], 'automatic');
    expect(manual.headers()['X-Update-Check-Kind'], 'manual');
    expect(auto.headers(refresh: true)['X-Update-Check-Id'], auto.id);
  });
  test('account credentials stay on approved HTTPS origins and redirects are disabled', () async {
    await login();
    final download = Dio()..httpClientAdapter = http;
    service.protect(download, deviceUid: () => '1234567890abcdef12345678');
    http.response = {};
    await download.get('https://account.example/api/public/firmware/download');
    expect(http.requests.last.headers['Authorization'], 'Bearer $token');
    expect(http.requests.last.followRedirects, isFalse);
    await download.get('https://unrelated.example/api/public/download');
    expect(http.requests.last.headers['Authorization'], isNull);
    expect(await service.headers(Uri.parse('http://account.example/api/public/latest')), isEmpty);
  });
  test('logout removes the vault session but cannot alter server quota', () async {
    await login(); http.response = {'ok': true};
    await service.logout();
    final restored = AccountService(dio: dio, endpoint: endpoint);
    await restored.initialize();
    expect(restored.loggedIn, isFalse);
    expect(http.requests.last.uri.path, '/api/account/logout');
    expect(http.requests.where((r) => r.uri.path.contains('reset-quota')), isEmpty);
  });
  test('server session rejection clears the stale local session with a readable error', () async {
    await login(); http.status = 401; http.response = {'errorCode': 'LOGIN_REQUIRED'};
    await expectLater(service.refresh(), throwsA(isA<AccountException>().having((e) => e.code, 'code', 'LOGIN_REQUIRED')));
    expect(service.loggedIn, isFalse);
  });
}
