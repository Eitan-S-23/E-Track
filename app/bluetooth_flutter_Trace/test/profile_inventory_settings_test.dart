import 'package:ble_monitor/pages/profile_tab_page.dart';
import 'package:ble_monitor/pages/companion_setup_page.dart';
import 'package:ble_monitor/pages/trace_ui.dart';
import 'package:ble_monitor/services/version_inventory_service.dart';
import 'package:ble_monitor/services/account_service.dart';
import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:get/get.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'account_fixture.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  const toggleKey = ValueKey('version-inventory-toggle');
  const preference = 'version_inventory_v1_enabled';
  late VersionInventoryService inventory;
  late int requests;
  late TestAccountService accounts;

  setUp(() {
    Get.testMode = true;
    accounts = TestAccountService(signedIn: false);
    Get.put<AccountService>(accounts);
    requests = 0;
    SharedPreferences.setMockInitialValues({});
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(const MethodChannel('trace/app_update'),
            (call) async => {'versionName': '1.0.76'});
    inventory = VersionInventoryService(
      supported: true,
      endpoint: Uri.parse('https://example.com/api/public/version-inventory'),
      readAppIdentity: () async => {},
      canReport: () => false,
      sender: (uri, body, token, cancel) async {
        requests++;
        throw StateError('UI tests must not send inventory');
      },
    );
  });

  tearDown(() {
    inventory.onClose();
    Get.reset();
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(const MethodChannel('trace/app_update'), null);
    expect(requests, 0);
  });

  void settingsTest(String description, WidgetTesterCallback body) {
    testWidgets(description, (tester) async {
      try {
        await body(tester);
      } finally {
        inventory.onClose();
        await tester.pumpWidget(const SizedBox.shrink());
      }
    });
  }

  Future<void> settleSetup(WidgetTester tester) async {
    // Match the existing setup-page tests: the production background never settles.
    for (var frame = 0; frame < 30; frame++) {
      await tester.pump(const Duration(milliseconds: 20));
    }
  }

  Future<void> openSettings(
    WidgetTester tester, {
    Brightness brightness = Brightness.light,
    TargetPlatform platform = TargetPlatform.android,
    double width = 390,
    bool openInventory = true,
  }) async {
    await inventory.initialize();
    Get.put<VersionInventoryService>(inventory);
    tester.view.physicalSize = Size(width, 844);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.reset);
    await tester.pumpWidget(GetMaterialApp(
      theme: ThemeData(
        brightness: brightness,
        platform: platform,
        useMaterial3: true,
      ),
      home: const Scaffold(body: ProfileTabPage()),
      getPages: [GetPage(name: '/companion-setup',
        page: () => const CompanionSetupPage())],
    ));
    await tester.pumpAndSettle();
    // Native version metadata is optional; both labels must keep the same brand.
    expect(find.byWidgetPredicate((widget) => widget is Text &&
        (widget.data == 'E-Track' || widget.data == 'E-Track v1.0.76')),
        findsOneWidget);
    expect(find.textContaining('BLE Monitor'), findsNothing);
    expect(find.text('E-Track 智能设备管理助手'), findsOneWidget);
    // TraceGlowNode's caption is outside its circular InkWell.
    await tester.ensureVisible(find.byIcon(Icons.settings));
    await tester.tap(find.byIcon(Icons.settings));
    await tester.pumpAndSettle();
    expect(find.byKey(const ValueKey('version-inventory-entry')), findsOneWidget);
    expect(find.byKey(toggleKey), findsNothing);
    expect(find.textContaining('不上传位置、联系人、骑行记录或诊断日志'), findsNothing);
    expect(find.textContaining('最近上报：'), findsNothing);
    if (!openInventory) return;
    await tester.tap(find.byKey(const ValueKey('version-inventory-entry')));
    await tester.pumpAndSettle();
    expect(find.byKey(toggleKey), findsOneWidget);
    expect(find.byKey(const ValueKey('version-inventory-entry'), skipOffstage: false), findsOneWidget);
    expect(find.byType(ProfileTabPage, skipOffstage: false), findsOneWidget);
    expect(tester.takeException(), isNull);
  }

  Color renderedTextColor(WidgetTester tester, String text) {
    final richText = find.descendant(
      of: find.text(text).last,
      matching: find.byType(RichText),
    );
    return tester.renderObject<RenderParagraph>(richText).text.style!.color!;
  }

  for (final scale in [1.0, 2.0]) {
    testWidgets('profile identity updates without reopening and stays bounded at scale $scale', (tester) async {
      tester.view.physicalSize = const Size(320, 568); tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.reset);
      await tester.pumpWidget(GetMaterialApp(
        builder: (context, child) => MediaQuery(
          data: MediaQuery.of(context).copyWith(textScaler: TextScaler.linear(scale)), child: child!),
        home: const Scaffold(body: ProfileTabPage())));
      await tester.pumpAndSettle();
      final label = find.byKey(const ValueKey('profile-account-identity'));
      expect(tester.widget<Text>(label).data, '登录/注册');
      accounts.signedIn = true;
      accounts.account.value = {'id': 'one', 'username': 'rider', 'displayName': 'Alias', 'email': 'rider@example.test'};
      await tester.pump(); expect(tester.widget<Text>(label).data, 'rider');
      final email = '${'long' * 20}@example.test';
      accounts.account.value = {'id': 'two', 'username': '', 'email': email};
      await tester.pump();
      final text = tester.widget<Text>(label);
      expect(text.data, email); expect(text.semanticsLabel, email);
      expect(text.overflow, TextOverflow.ellipsis); expect(text.maxLines, 1);
      expect(tester.getSize(label).width, lessThanOrEqualTo(scale == 1 ? 118 : 180));
      expect(tester.getRect(label).right, lessThanOrEqualTo(320));
      accounts.account.value = {'id': 'three', 'username': 'another'};
      await tester.pump(); expect(tester.widget<Text>(label).data, 'another');
      accounts.signedIn = false; accounts.account.value = null;
      await tester.pump(); expect(tester.widget<Text>(label).data, '登录/注册');
      expect(tester.takeException(), isNull);
    });
  }

  double contrast(Color first, Color second) {
    final a = first.computeLuminance();
    final b = second.computeLuminance();
    return a > b ? (a + 0.05) / (b + 0.05) : (b + 0.05) / (a + 0.05);
  }

  for (final brightness in Brightness.values) {
    for (final platform in [TargetPlatform.android, TargetPlatform.iOS]) {
      settingsTest('statistics consent stays readable for $brightness / $platform',
          (tester) async {
        await openSettings(tester, brightness: brightness, platform: platform);
        expect(renderedTextColor(tester, '参与版本统计'), TraceColors.text);
        expect(contrast(TraceColors.text, TraceColors.deep), greaterThan(4.5));
        expect(renderedTextColor(tester, '已开启'), TraceColors.mint);
        final on = tester.widget<SwitchListTile>(find.byKey(toggleKey));
        expect(on.value, isTrue);
        final selected = {WidgetState.selected};
        expect(on.trackColor!.resolve(selected), TraceColors.mint);
        expect(on.thumbColor!.resolve(selected), TraceColors.deep);
        expect(on.trackOutlineColor!.resolve(selected), Colors.transparent);
        expect(contrast(on.thumbColor!.resolve(selected)!,
            on.trackColor!.resolve(selected)!), greaterThan(3));

        await tester.tap(find.text('参与版本统计').last);
        await tester.pump();
        await tester.pump(const Duration(milliseconds: 300));
        expect(inventory.enabled.value, isFalse);
        expect((await SharedPreferences.getInstance()).getBool(preference), isFalse);
        expect(renderedTextColor(tester, '参与版本统计'), TraceColors.text);
        expect(renderedTextColor(tester, '已关闭'), TraceColors.muted);
        expect(find.text('版本统计已关闭'), findsOneWidget);
        final off = tester.widget<SwitchListTile>(find.byKey(toggleKey));
        expect(off.value, isFalse);
        expect(off.trackColor!.resolve({}), TraceColors.ocean);
        expect(off.thumbColor!.resolve({}), TraceColors.muted);
        expect(off.trackOutlineColor!.resolve({}), TraceColors.muted);
        expect(contrast(TraceColors.muted, TraceColors.deep), greaterThan(4.5));
        expect(contrast(off.thumbColor!.resolve({})!,
            off.trackColor!.resolve({})!), greaterThan(3));

        await tester.tap(find.descendant(
          of: find.byKey(toggleKey),
          matching: find.byType(Switch),
        ));
        await tester.pump();
        await tester.pump(const Duration(milliseconds: 300));
        expect(inventory.enabled.value, isTrue);
        expect((await SharedPreferences.getInstance()).getBool(preference), isTrue);
        expect(find.text('已开启'), findsOneWidget);
        expect(tester.takeException(), isNull);
        await tester.pumpWidget(const SizedBox.shrink());
      });
    }
  }

  settingsTest('help contains the permission guide and preserves reporting opt-out', (tester) async {
    SharedPreferences.setMockInitialValues({preference: false});
    await openSettings(tester);
    await tester.tap(find.byKey(const ValueKey('detail-back')));
    await tester.pumpAndSettle();
    expect(find.byKey(const ValueKey('version-inventory-entry')), findsOneWidget);
    await tester.tap(find.text('知道了'));
    await tester.pumpAndSettle();
    expect(find.text('后台运行与权限'), findsNothing);
    expect(find.byKey(const ValueKey('help-permissions')), findsNothing);
    await tester.ensureVisible(find.byIcon(Icons.chat_bubble_outline));
    await tester.tap(find.byIcon(Icons.chat_bubble_outline));
    await tester.pumpAndSettle();
    await tester.ensureVisible(find.byKey(const ValueKey('help-permissions')));
    await tester.tap(find.byKey(const ValueKey('help-permissions')));
    await settleSetup(tester);
    expect(Get.currentRoute, '/companion-setup');
    expect(find.text('后台运行与权限'), findsOneWidget);
    expect(find.byKey(const ValueKey('help-permissions'), skipOffstage: false), findsOneWidget);
    expect(find.byType(ProfileTabPage, skipOffstage: false), findsOneWidget);
    expect(inventory.enabled.value, isFalse);
    Get.back<void>();
    await tester.pumpAndSettle();
    expect(find.byKey(const ValueKey('help-permissions')), findsOneWidget);
    expect(find.text('功率计功能：'), findsNothing);
    expect(find.text('码表功能：'), findsNothing);
    expect(find.text('遥控功能：'), findsNothing);
    expect(find.byKey(const ValueKey('help-feedback')), findsOneWidget);
    await tester.tap(find.text('确定'));
    await tester.pumpAndSettle();
    expect(find.byType(ProfileTabPage), findsOneWidget);
    await tester.tap(find.byIcon(Icons.settings));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const ValueKey('version-inventory-entry')));
    await tester.pumpAndSettle();
    expect(tester.widget<SwitchListTile>(find.byKey(toggleKey)).value, isFalse);
    expect((await SharedPreferences.getInstance()).getBool(preference), isFalse);
  });

  settingsTest('opening settings stays compact even when statistics are already enabled', (tester) async {
    SharedPreferences.setMockInitialValues({preference: true});
    await openSettings(tester, openInventory: false);
    expect(find.text('参与版本统计'), findsOneWidget);
    expect(find.byType(SwitchListTile), findsNothing);
    expect(find.textContaining('上报'), findsNothing);
    expect(inventory.enabled.value, isTrue);
    await tester.tap(find.byKey(const ValueKey('version-inventory-entry')));
    await tester.pumpAndSettle();
    expect(tester.widget<SwitchListTile>(find.byKey(toggleKey)).value, isTrue);
    expect(find.textContaining('不上传位置、联系人、骑行记录或诊断日志'), findsOneWidget);
    expect(find.textContaining('服务器记录上报出口 IP'), findsOneWidget);
    expect(find.textContaining('单日质量摘要'), findsOneWidget);
    expect((await SharedPreferences.getInstance()).getBool(preference), isTrue);
  });

  settingsTest('saved opt-out is displayed without enabling reporting', (tester) async {
    SharedPreferences.setMockInitialValues({preference: false});
    await openSettings(tester);
    expect(tester.widget<SwitchListTile>(find.byKey(toggleKey)).value, isFalse);
    expect(find.text('已关闭'), findsOneWidget);
    expect(find.text('版本统计已关闭'), findsOneWidget);
    expect(find.textContaining('不上传位置、联系人、骑行记录或诊断日志'), findsOneWidget);
    expect(find.textContaining('历史记录最多保留 90 天'), findsOneWidget);
    await tester.pumpWidget(const SizedBox.shrink());
  });

  settingsTest('loading state is readable and cannot change consent', (tester) async {
    await openSettings(tester);
    inventory.ready.value = false;
    await tester.pump();
    expect(find.text('正在读取设置'), findsOneWidget);
    expect(renderedTextColor(tester, '参与版本统计'), TraceColors.text);
    final loading = tester.widget<SwitchListTile>(find.byKey(toggleKey));
    expect(loading.onChanged, isNull);
    final disabled = {WidgetState.selected, WidgetState.disabled};
    expect(loading.thumbColor!.resolve(disabled), TraceColors.muted);
    expect(loading.trackColor!.resolve(disabled), TraceColors.ocean);
    expect(loading.trackOutlineColor!.resolve(disabled), TraceColors.muted);
    await tester.tap(find.text('参与版本统计').last);
    await tester.pump();
    expect(inventory.enabled.value, isTrue);
    expect((await SharedPreferences.getInstance()).getBool(preference), isNull);
    inventory.ready.value = true;
    await tester.pump();
    expect(tester.widget<SwitchListTile>(find.byKey(toggleKey)).onChanged, isNotNull);
    await tester.pumpWidget(const SizedBox.shrink());
  });

  settingsTest('reporting status updates without dimming the opt-in label', (tester) async {
    await openSettings(tester);
    inventory.status.value = InventoryReportStatus.busy;
    await tester.pump();
    expect(find.text('等待更新任务结束后上报'), findsOneWidget);
    inventory.failureCode.value = 'NETWORK_ERROR';
    inventory.status.value = InventoryReportStatus.retrying;
    await tester.pump();
    expect(find.textContaining('将在前台自动重试'), findsOneWidget);
    expect(renderedTextColor(tester, '参与版本统计'), TraceColors.text);
    expect(find.text('已开启'), findsOneWidget);
    inventory.lastReportedAt.value = DateTime.utc(2026, 11, 13, 12);
    inventory.status.value = InventoryReportStatus.reported;
    await tester.pump();
    expect(find.textContaining('最近上报：'), findsOneWidget);
    expect(find.textContaining('将在前台自动重试'), findsNothing);
    await tester.pumpWidget(const SizedBox.shrink());
  });

  settingsTest('narrow settings dialog supports large text without overflow', (tester) async {
    await openSettings(tester, width: 320);
    tester.platformDispatcher.textScaleFactorTestValue = 2;
    addTearDown(tester.platformDispatcher.clearTextScaleFactorTestValue);
    await tester.pump();
    expect(find.text('参与版本统计').last, findsOneWidget);
    expect(tester.takeException(), isNull);
    await tester.ensureVisible(find.byKey(const ValueKey('detail-back')));
    await tester.tap(find.byKey(const ValueKey('detail-back')));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 400));
    expect(find.byKey(toggleKey), findsNothing);
    expect(inventory.enabled.value, isTrue);
    await tester.pumpWidget(const SizedBox.shrink());
  });

  for (final direction in [-1.0, 1.0]) {
    settingsTest('statistics swipe $direction returns to its settings parent', (tester) async {
      await openSettings(tester);
      await tester.drag(find.text('版本统计'), Offset(direction * 180, 0));
      await tester.pumpAndSettle();
      expect(find.byKey(toggleKey), findsNothing);
      expect(find.byKey(const ValueKey('version-inventory-entry')), findsOneWidget);
    });
  }

  settingsTest('repeated Back taps cannot also dismiss the parent settings', (tester) async {
    await openSettings(tester);
    await tester.tap(find.byKey(const ValueKey('detail-back')));
    await tester.tap(find.byKey(const ValueKey('detail-back')));
    await tester.pumpAndSettle();
    expect(find.byKey(toggleKey), findsNothing);
    expect(find.byKey(const ValueKey('version-inventory-entry')), findsOneWidget);
  });

  settingsTest('permission Back icon and swipe restore Help rather than home', (tester) async {
    await openSettings(tester, openInventory: false);
    await tester.tap(find.text('知道了')); await tester.pumpAndSettle();
    await tester.ensureVisible(find.byIcon(Icons.chat_bubble_outline));
    await tester.tap(find.byIcon(Icons.chat_bubble_outline)); await tester.pumpAndSettle();
    for (final useButton in [true, false]) {
      await tester.tap(find.byKey(const ValueKey('help-permissions'))); await settleSetup(tester);
      if (useButton) {
        await tester.tap(find.byKey(const ValueKey('detail-back')));
      } else {
        await tester.drag(find.text('后台运行与权限'), const Offset(-180, 0));
      }
      await tester.pumpAndSettle();
      expect(find.byKey(const ValueKey('help-permissions')), findsOneWidget);
      expect(find.byType(CompanionSetupPage), findsNothing);
    }
  });
}
