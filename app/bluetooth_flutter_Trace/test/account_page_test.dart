import 'dart:async';

import 'package:ble_monitor/pages/account_page.dart';
import 'package:ble_monitor/pages/trace_ui.dart';
import 'package:ble_monitor/services/account_service.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:get/get.dart';

import 'account_fixture.dart';

class _Accounts extends TestAccountService {
  _Accounts() : super(signedIn: false);
  bool registration = true;
  bool verification = false, reset = false;
  AccountException? settingsError, actionError;
  Completer<void>? pendingLogin;
  final calls = <Map<String, dynamic>>[];
  @override
  Future<void> loadSettings() async {
    if (settingsError != null) throw settingsError!;
    settings.assignAll({
    'registrationEnabled': registration,
    'passwordRegistrationEnabled': registration,
    'passwordResetAvailable': reset,
    'emailVerificationEnabled': verification,
    });
  }
  @override
  Future<void> login(String username, String password) async {
    if (pendingLogin != null) await pendingLogin!.future;
    if (actionError != null) throw actionError!;
    signedIn = true;
    account.value = {'id': 'one', 'displayName': username};
  }
  @override
  Future<Map<String, dynamic>> call(String path, {Map<String, dynamic>? body, bool anonymous = false, String? uid}) async {
    calls.add({'path': path, 'body': body});
    if (actionError != null) throw actionError!;
    return {'ok': true, 'verificationId': '11111111-1111-4111-8111-111111111111'};
  }
  @override
  Future<void> refresh() async {}
}

void main() {
  late _Accounts accounts;
  setUp(() {
    Get.testMode = true;
    accounts = _Accounts();
    Get.put<AccountService>(accounts);
  });
  tearDown(() { Get.reset(); });

  Future<void> show(WidgetTester tester, {double scale = 1}) async {
    tester.view.physicalSize = const Size(320, 568);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    await tester.pumpWidget(GetMaterialApp(
      builder: (context, child) => MediaQuery(
        data: MediaQuery.of(context).copyWith(textScaler: TextScaler.linear(scale)), child: child!),
      home: const AccountPage(),
    ));
    for (var i = 0; i < 4; i++) { await tester.pump(); }
  }
  Future<void> frames(WidgetTester tester) async {
    for (var i = 0; i < 20; i++) { await tester.pump(const Duration(milliseconds: 20)); }
  }

  testWidgets('initial load errors use the shared scrollable result dialog', (tester) async {
    accounts.settingsError = const AccountException('NETWORK', '账号服务暂时不可用，请稍后重试');
    await show(tester, scale: 2); await frames(tester);
    expect(find.byType(TraceDialog), findsOneWidget);
    expect(find.text('操作未完成'), findsOneWidget);
    expect(find.text('账号服务暂时不可用，请稍后重试'), findsOneWidget);
    await tester.ensureVisible(find.text('知道了'));
    await tester.tap(find.text('知道了')); await frames(tester);
    expect(find.byType(TraceDialog), findsNothing);
    expect(find.text('暂不登录，继续使用蓝牙'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('failed login is a dialog and retains the form for correction', (tester) async {
    accounts.actionError = const AccountException('INVALID_CREDENTIALS', '账号或密码不正确');
    await show(tester);
    await tester.enterText(find.byType(TextFormField).at(0), 'rider');
    await tester.enterText(find.byType(TextFormField).at(1), 'wrong-password');
    await tester.ensureVisible(find.widgetWithText(FilledButton, '登录'));
    await tester.tap(find.widgetWithText(FilledButton, '登录')); await frames(tester);
    expect(find.byType(TraceDialog), findsOneWidget);
    expect(find.text('账号或密码不正确'), findsOneWidget);
    await tester.tap(find.text('知道了')); await frames(tester);
    expect(tester.widget<TextFormField>(find.byType(TextFormField).first).controller!.text, 'rider');
    expect(tester.widget<TextFormField>(find.byType(TextFormField).last).controller!.text, 'wrong-password');
    expect(accounts.loggedIn, isFalse);
  });

  testWidgets('registration accepts an optional recovery email and confirms success in a dialog', (tester) async {
    await show(tester);
    await tester.ensureVisible(find.text('创建账号')); await tester.tap(find.text('创建账号')); await frames(tester);
    final values = ['rider', 'rider@example.test', 'valid-password', 'valid-password'];
    for (var i = 0; i < values.length; i++) { await tester.enterText(find.byType(TextFormField).at(i), values[i]); }
    await tester.ensureVisible(find.widgetWithText(FilledButton, '注册'));
    await tester.tap(find.widgetWithText(FilledButton, '注册')); await frames(tester);
    expect(accounts.calls.single['body']['email'], 'rider@example.test');
    expect(find.byType(TraceDialog), findsOneWidget);
    expect(find.text('账号已创建，请登录。'), findsOneWidget);
    expect(accounts.loggedIn, isFalse);
  });

  testWidgets('mail errors are dialogs and a successful resend is bounded', (tester) async {
    accounts.reset = true;
    accounts.actionError = const AccountException('EMAIL_DELIVERY_FAILED', '验证码发送未成功，请稍后重试');
    await show(tester);
    await tester.ensureVisible(find.text('忘记密码？')); await tester.tap(find.text('忘记密码？')); await frames(tester);
    await tester.enterText(find.byType(TextFormField).first, 'rider@example.test');
    await tester.ensureVisible(find.text('获取邮箱验证码')); await tester.tap(find.text('获取邮箱验证码')); await frames(tester);
    expect(find.text('验证码发送未成功，请稍后重试'), findsOneWidget);
    await tester.tap(find.text('知道了')); await frames(tester);
    accounts.actionError = null;
    await tester.tap(find.text('获取邮箱验证码')); await frames(tester);
    expect(find.byType(TraceDialog), findsOneWidget);
    expect(find.textContaining('10 分钟内有效'), findsOneWidget);
    await tester.tap(find.text('知道了')); await frames(tester);
    final resend = find.ancestor(of: find.textContaining('秒后可重新获取'), matching: find.byType(TextButton));
    expect(resend, findsOneWidget);
    expect(tester.widget<TextButton>(resend).onPressed, isNull);
    expect(accounts.calls, hasLength(2));
    await tester.pumpWidget(const SizedBox.shrink()); await tester.pump();
    expect(tester.takeException(), isNull);
  });

  testWidgets('a late login failure does not open a dialog after the page is closed', (tester) async {
    accounts.pendingLogin = Completer<void>();
    accounts.actionError = const AccountException('NETWORK', 'late failure');
    await show(tester);
    await tester.enterText(find.byType(TextFormField).at(0), 'rider');
    await tester.enterText(find.byType(TextFormField).at(1), 'valid-password');
    await tester.ensureVisible(find.widgetWithText(FilledButton, '登录'));
    await tester.tap(find.widgetWithText(FilledButton, '登录')); await tester.pump();
    await tester.pumpWidget(const SizedBox.shrink());
    accounts.pendingLogin!.complete(); await frames(tester);
    expect(find.byType(TraceDialog), findsNothing);
    expect(tester.takeException(), isNull);
  });

  testWidgets('registration follows the server switch and local Bluetooth remains accessible', (tester) async {
    accounts.registration = false;
    await show(tester);
    expect(find.text('创建账号'), findsNothing);
    expect(find.text('暂未开放注册'), findsOneWidget);
    expect(find.text('暂不登录，继续使用蓝牙'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('small-screen registration scrolls and secondary actions retain readable contrast', (tester) async {
    await show(tester, scale: 1.5);
    await tester.ensureVisible(find.text('创建账号'));
    await tester.tap(find.text('创建账号'));
    await tester.pump();
    expect(find.text('确认密码'), findsOneWidget);
    await tester.ensureVisible(find.text('返回登录'));
    final context = tester.element(find.text('返回登录'));
    final color = TextButtonTheme.of(context).style!.foregroundColor!.resolve({})!;
    expect(color, TraceColors.cyanSoft);
    final contrast = (color.computeLuminance() + .05) / (TraceColors.deep.computeLuminance() + .05);
    expect(contrast, greaterThanOrEqualTo(4.5));
    expect(tester.takeException(), isNull);
  });

  testWidgets('account displays separate allowances and full hardware identity without overflow', (tester) async {
    accounts.signedIn = true;
    accounts.account.value = {'id': 'one', 'displayName': 'Rider'};
    accounts.quota.assignAll({'automatic': {'remaining': 4, 'limit': 5}, 'manual': {'remaining': 3, 'limit': 5}});
    accounts.devices.assignAll([{
      'uid': '1234567890abcdef12345678', 'name': 'E-Track', 'model': 'AT32F435',
      'hardware_revision': 1, 'firmware_version': 30349,
    }]);
    await show(tester, scale: 2);
    expect(find.textContaining('自动剩余 4 / 5'), findsOneWidget);
    expect(find.textContaining('手动剩余 3 / 5'), findsOneWidget);
    await tester.ensureVisible(find.text('UID 1234567890abcdef12345678'));
    expect(find.text('UID 1234567890abcdef12345678'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });
}
