import 'package:ble_monitor/pages/profile_tab_page.dart';
import 'package:ble_monitor/pages/trace_ui.dart';
import 'package:ble_monitor/services/version_inventory_service.dart';
import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:get/get.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  const toggleKey = ValueKey('version-inventory-toggle');
  const preference = 'version_inventory_v1_enabled';
  late VersionInventoryService inventory;
  late int requests;

  setUp(() {
    Get.testMode = true;
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
      addTearDown(inventory.onClose);
      await body(tester);
    });
  }

  Future<void> openSettings(
    WidgetTester tester, {
    Brightness brightness = Brightness.light,
    TargetPlatform platform = TargetPlatform.android,
    double width = 390,
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
    ));
    await tester.pump(const Duration(seconds: 1));
    await tester.ensureVisible(find.text('应用设置'));
    await tester.tap(find.text('应用设置'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 400));
    expect(find.byKey(toggleKey), findsOneWidget);
    expect(tester.takeException(), isNull);
  }

  Color renderedTextColor(WidgetTester tester, String text) {
    final richText = find.descendant(
      of: find.text(text),
      matching: find.byType(RichText),
    );
    return tester.renderObject<RenderParagraph>(richText).text.style!.color!;
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

        await tester.tap(find.text('参与版本统计'));
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

  settingsTest('saved opt-out is displayed without enabling reporting', (tester) async {
    SharedPreferences.setMockInitialValues({preference: false});
    await openSettings(tester);
    expect(tester.widget<SwitchListTile>(find.byKey(toggleKey)).value, isFalse);
    expect(find.text('已关闭'), findsOneWidget);
    expect(find.text('版本统计已关闭'), findsOneWidget);
    expect(find.textContaining('不上传位置、联系人或骑行记录'), findsOneWidget);
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
    await tester.tap(find.text('参与版本统计'));
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
    expect(find.text('参与版本统计'), findsOneWidget);
    expect(tester.takeException(), isNull);
    await tester.ensureVisible(find.text('知道了'));
    await tester.tap(find.text('知道了'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 400));
    expect(find.byKey(toggleKey), findsNothing);
    expect(inventory.enabled.value, isTrue);
    await tester.pumpWidget(const SizedBox.shrink());
  });
}
