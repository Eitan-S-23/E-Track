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
  @override
  Future<void> loadSettings() async => settings.assignAll({
    'registrationEnabled': registration,
    'passwordRegistrationEnabled': registration,
    'passwordResetAvailable': false,
  });
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
  tearDown(() async { await Get.reset(); });

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
