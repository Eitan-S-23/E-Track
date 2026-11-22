import 'dart:convert';
import 'dart:typed_data';
import 'package:ble_monitor/services/account_service.dart';
import 'package:ble_monitor/services/announcement_service.dart';
import 'package:dio/dio.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';

class _Http implements HttpClientAdapter {
  final requests = <RequestOptions>[];
  int status = 200;
  Map<String, dynamic> response = {};
  ResponseBody Function(RequestOptions)? respond;
  @override
  Future<ResponseBody> fetch(RequestOptions options, Stream<Uint8List>? stream, Future<void>? cancel) async {
    requests.add(options);
    if (respond != null) return respond!(options);
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
  test('announcements use account admission but do not spend an update check', () async {
    final uri = endpoint.replace(path: '/api/public/announcements');
    expect(await AnnouncementService.fetchRemoteAnnouncements(
      accountService: service, dio: dio, endpoint: uri), isEmpty);
    expect(http.requests, isEmpty);
    await login();
    http.response = {'announcements': [{'id': 'notice', 'title': 'News', 'body': 'Details'}]};
    final items = await AnnouncementService.fetchRemoteAnnouncements(
      accountService: service, dio: dio, endpoint: uri);
    expect(items.single.id, 'notice');
    expect(http.requests.last.headers['Authorization'], 'Bearer $token');
    expect(http.requests.last.headers['X-Update-Check-Id'], isNull);
    expect(http.requests.last.followRedirects, isFalse);
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
  test('signed fallback downloads stream without forwarding account or device credentials', () async {
    await login();
    final download = Dio()..httpClientAdapter = http;
    service.protect(download, deviceUid: () => '1234567890abcdef12345678');
    const target = 'https://github.com/Eitan-S-23/Trace/releases/download/v1.0.90/ble-monitor-android.apk';
    http.respond = (request) => request.uri.host == 'account.example'
        ? ResponseBody.fromString('', 302, headers: {'location': [target]})
        : ResponseBody.fromBytes([1, 2, 3], 206);
    final response = await download.get<ResponseBody>(
      'https://account.example/api/public/github-fallback?signature=test-signature',
      options: Options(responseType: ResponseType.stream, headers: {
        'Range': 'bytes=3-', 'If-Range': '"etag"', 'Cookie': 'private-cookie',
        'X-Update-Check-Id': 'private-check', 'X-Install-Token': 'private-install',
      }));
    expect(response.statusCode, 206);
    expect(await response.data!.stream.expand((bytes) => bytes).toList(), [1, 2, 3]);
    final redirected = http.requests.last;
    expect(redirected.uri.toString(), target);
    expect(redirected.headers, {'Range': 'bytes=3-', 'If-Range': '"etag"'});
    expect(redirected.followRedirects, isTrue);
  });
  test('fallback rejects foreign, plaintext and mutable targets without a second request', () async {
    await login();
    final download = Dio()..httpClientAdapter = http;
    service.protect(download);
    for (final target in [
      'https://unrelated.example/file.apk',
      'http://github.com/Eitan-S-23/Trace/releases/download/v1/file.apk',
      'https://github.com/Eitan-S-23/Trace/releases/latest/download/file.apk',
      'https://github.com/other/project/releases/download/v1/file.apk',
    ]) {
      http.requests.clear();
      http.respond = (_) => ResponseBody.fromString('', 302, headers: {'location': [target]});
      await expectLater(download.get('https://account.example/api/public/github-fallback'), throwsA(isA<DioException>()));
      expect(http.requests, hasLength(1));
    }
  });
  test('prepared grant survives recreation and remains isolated by account', () async {
    await login();
    const uid = '1234567890abcdef12345678';
    await service.savePreparation(uid, {'id': 'prepared-check-00001', 'accountId': 'one'});
    final restored = AccountService(dio: dio, endpoint: endpoint);
    expect((await restored.loadPreparation(uid))?['id'], 'prepared-check-00001');
    http.response = {'token': 'acct_${'b' * 64}', 'account': {'id': 'two', 'username': 'other'}, 'quota': {}};
    await restored.login('other', 'test-password');
    expect(await restored.loadPreparation(uid), isNull);
  });
  test('server session rejection clears the stale local session with a readable error', () async {
    await login(); http.status = 401; http.response = {'errorCode': 'LOGIN_REQUIRED'};
    await expectLater(service.refresh(), throwsA(isA<AccountException>().having((e) => e.code, 'code', 'LOGIN_REQUIRED')));
    expect(service.loggedIn, isFalse);
  });
}
