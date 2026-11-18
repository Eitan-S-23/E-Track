import 'package:ble_monitor/pages/feedback_page.dart';
import 'package:ble_monitor/services/feedback_service.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:get/get.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  late FeedbackService service;
  setUp(() {
    Get.testMode = true;
    SharedPreferences.setMockInitialValues({});
    service = FeedbackService(endpoint: Uri.parse('https://feedback.test/api/public/feedback'), supported: true,
      canSend: () => false,
      readIdentity: () async => {'platform': 'android', 'versionName': '1.0.82', 'versionCode': 108},
      sender: (_, body, token, cancel) async => throw StateError('UI must not send real requests'));
  });
  tearDown(() { service.onClose(); Get.reset(); });

  Future<void> open(WidgetTester tester, {double width = 390, double scale = 1}) async {
    await service.initialize();
    tester.view.physicalSize = Size(width, 900); tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.reset);
    tester.platformDispatcher.textScaleFactorTestValue = scale;
    addTearDown(tester.platformDispatcher.clearTextScaleFactorTestValue);
    await tester.pumpWidget(GetMaterialApp(home: Scaffold(body: Builder(builder: (context) => TextButton(
      onPressed: () => Navigator.of(context).push(MaterialPageRoute<void>(builder: (_) => FeedbackPage(service: service))),
      child: const Text('Help parent'))))));
    await tester.tap(find.text('Help parent')); await tester.pumpAndSettle();
  }

  testWidgets('feedback is persisted with a clear queued status and survives reopening', (tester) async {
    try {
      await open(tester);
      await tester.enterText(find.byKey(const ValueKey('feedback-text')), 'My first feedback');
      await tester.ensureVisible(find.byKey(const ValueKey('feedback-submit')));
      await tester.tap(find.byKey(const ValueKey('feedback-submit'))); await tester.pumpAndSettle();
      expect(service.pending.single['body'], 'My first feedback');
      expect(service.sent, isEmpty);
      expect(tester.widget<TextField>(find.byKey(const ValueKey('feedback-text'))).controller!.text, '');
      await tester.tap(find.byKey(const ValueKey('detail-back'))); await tester.pumpAndSettle();
      expect(find.text('Help parent'), findsOneWidget);
      await tester.tap(find.text('Help parent')); await tester.pumpAndSettle();
      expect(find.text('\u5f85\u53d1\u9001\uff081\uff09'), findsOneWidget); expect(find.text('My first feedback'), findsOneWidget);
      expect(tester.takeException(), isNull);
    } finally { service.onClose(); await tester.pumpWidget(const SizedBox.shrink()); }
  });

  testWidgets('back preserves an unsaved draft unless explicitly discarded', (tester) async {
    try {
      await open(tester);
      await tester.enterText(find.byKey(const ValueKey('feedback-text')), 'Unsaved');
      await tester.tap(find.byKey(const ValueKey('detail-back'))); await tester.pumpAndSettle();
      expect(find.textContaining('\u653e\u5f03\u5c1a\u672a\u63d0\u4ea4'), findsOneWidget);
      await tester.tap(find.text('\u53d6\u6d88')); await tester.pumpAndSettle();
      expect(tester.widget<TextField>(find.byKey(const ValueKey('feedback-text'))).controller!.text, 'Unsaved');
      await tester.tap(find.byKey(const ValueKey('detail-back'))); await tester.pumpAndSettle();
      await tester.tap(find.text('\u786e\u5b9a')); await tester.pumpAndSettle();
      expect(find.text('Help parent'), findsOneWidget); expect(service.pending, isEmpty);
    } finally { service.onClose(); await tester.pumpWidget(const SizedBox.shrink()); }
  });

  testWidgets('feedback remains usable at narrow width and large text', (tester) async {
    try {
      await open(tester, width: 320, scale: 2);
      expect(find.byKey(const ValueKey('detail-back')), findsOneWidget);
      await tester.enterText(find.byKey(const ValueKey('feedback-text')), 'A short issue');
      await tester.ensureVisible(find.byKey(const ValueKey('feedback-submit')));
      await tester.tap(find.byKey(const ValueKey('feedback-submit'))); await tester.pumpAndSettle();
      expect(service.pending, hasLength(1)); expect(tester.takeException(), isNull);
    } finally { service.onClose(); await tester.pumpWidget(const SizedBox.shrink()); }
  });
}
