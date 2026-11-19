import 'package:ble_monitor/pages/feedback_page.dart';
import 'package:ble_monitor/pages/companion_diagnostics_page.dart';
import 'package:ble_monitor/services/feedback_service.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:get/get.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  late FeedbackService service;
  var diagnosticReads = 0;
  setUp(() {
    Get.testMode = true;
    SharedPreferences.setMockInitialValues({});
    diagnosticReads = 0;
  });
  tearDown(() { service.onClose(); Get.reset(); });

  Future<void> settle(WidgetTester tester) async {
    // The real page atmosphere repeats; assert state after a bounded frame window.
    for (var frame = 0; frame < 30; frame++) {
      await tester.pump(const Duration(milliseconds: 20));
    }
  }

  Future<void> open(WidgetTester tester, {double width = 390, double scale = 1, bool diagnostics = false}) async {
    // The serialized edit future must belong to this test's FakeAsync zone.
    service = FeedbackService(endpoint: Uri.parse('https://feedback.test/api/public/feedback'), supported: true,
      canSend: () => false,
      readIdentity: () async => {'platform': 'android', 'versionName': '1.0.82', 'versionCode': 108},
      sender: (_, body, token, cancel) async => throw StateError('UI must not send real requests'));
    await service.initialize();
    tester.view.physicalSize = Size(width, 900); tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.reset);
    tester.platformDispatcher.textScaleFactorTestValue = scale;
    addTearDown(tester.platformDispatcher.clearTextScaleFactorTestValue);
    await tester.pumpWidget(GetMaterialApp(home: Scaffold(body: Builder(builder: (context) => TextButton(
      onPressed: () => Navigator.of(context).push(MaterialPageRoute<void>(builder: (_) => FeedbackPage(service: service,
        diagnosticsSupported: diagnostics, readDiagnostics: () async {
          diagnosticReads++;
          return CompanionDiagnosticSnapshot([{'state':'CONNECTION_TIMEOUT','stage':'DISCOVERING','elapsedMs':25000}]);
        }))),
      child: const Text('Help parent'))))));
    await tester.tap(find.text('Help parent')); await settle(tester);
  }

  testWidgets('feedback is persisted with a clear queued status and survives reopening', (tester) async {
    try {
      await open(tester);
      await tester.enterText(find.byKey(const ValueKey('feedback-text')), 'My first feedback');
      await tester.pump();
      expect(tester.widget<FilledButton>(find.byKey(const ValueKey('feedback-submit'))).onPressed, isNotNull);
      await tester.ensureVisible(find.byKey(const ValueKey('feedback-submit')));
      await tester.pump();
      await tester.tap(find.byKey(const ValueKey('feedback-submit'))); await settle(tester);
      expect(find.textContaining('\u5df2\u4fdd\u5b58\u3002'), findsOneWidget);
      expect(service.pending.single['body'], 'My first feedback');
      expect(service.sent, isEmpty);
      expect(tester.widget<TextField>(find.byKey(const ValueKey('feedback-text'))).controller!.text, '');
      await tester.tap(find.byKey(const ValueKey('detail-back'))); await settle(tester);
      expect(find.text('Help parent'), findsOneWidget);
      await tester.tap(find.text('Help parent')); await settle(tester);
      expect(find.text('\u5f85\u53d1\u9001\uff081\uff09'), findsOneWidget); expect(find.text('My first feedback'), findsOneWidget);
      expect(tester.takeException(), isNull);
    } finally { service.onClose(); await tester.pumpWidget(const SizedBox.shrink()); }
  });

  testWidgets('back preserves an unsaved draft unless explicitly discarded', (tester) async {
    try {
      await open(tester);
      await tester.enterText(find.byKey(const ValueKey('feedback-text')), 'Unsaved');
      await tester.pump();
      expect(tester.widget<PopScope<void>>(find.byType(PopScope<void>)).canPop, isFalse);
      await tester.tap(find.byKey(const ValueKey('detail-back'))); await settle(tester);
      expect(find.textContaining('\u653e\u5f03\u5c1a\u672a\u63d0\u4ea4'), findsOneWidget);
      await tester.tap(find.text('\u53d6\u6d88')); await settle(tester);
      expect(tester.widget<TextField>(find.byKey(const ValueKey('feedback-text'))).controller!.text, 'Unsaved');
      await tester.tap(find.byKey(const ValueKey('detail-back'))); await settle(tester);
      await tester.tap(find.text('\u786e\u5b9a')); await settle(tester);
      expect(find.text('Help parent'), findsOneWidget); expect(service.pending, isEmpty);
    } finally { service.onClose(); await tester.pumpWidget(const SizedBox.shrink()); }
  });

  testWidgets('feedback remains usable at narrow width and large text', (tester) async {
    try {
      await open(tester, width: 320, scale: 2);
      expect(find.byKey(const ValueKey('detail-back')), findsOneWidget);
      await tester.enterText(find.byKey(const ValueKey('feedback-text')), 'A short issue');
      await tester.pump();
      expect(tester.widget<FilledButton>(find.byKey(const ValueKey('feedback-submit'))).onPressed, isNotNull);
      await tester.ensureVisible(find.byKey(const ValueKey('feedback-submit')));
      await tester.pump();
      await tester.tap(find.byKey(const ValueKey('feedback-submit'))); await settle(tester);
      expect(find.textContaining('\u5df2\u4fdd\u5b58\u3002'), findsOneWidget);
      expect(service.pending, hasLength(1)); expect(tester.takeException(), isNull);
    } finally { service.onClose(); await tester.pumpWidget(const SizedBox.shrink()); }
  });
  testWidgets('connection diagnostics are attached only after explicit opt-in', (tester) async {
    try {
      await open(tester, diagnostics:true);
      expect(diagnosticReads, 0);
      await tester.enterText(find.byKey(const ValueKey('feedback-text')), 'Background reconnect is slow');
      await tester.ensureVisible(find.byKey(const ValueKey('feedback-attach-diagnostics')));
      await tester.tap(find.byKey(const ValueKey('feedback-attach-diagnostics'))); await tester.pump();
      await tester.ensureVisible(find.byKey(const ValueKey('feedback-submit')));
      await tester.tap(find.byKey(const ValueKey('feedback-submit'))); await settle(tester);
      expect(diagnosticReads, 1);
      expect(service.pending.single['body'], contains('CONNECTION_TIMEOUT'));
      expect((service.pending.single['body'] as String).length, lessThanOrEqualTo(2000));
      expect(tester.takeException(), isNull);
    } finally { service.onClose(); await tester.pumpWidget(const SizedBox.shrink()); }
  });
  test('diagnostic export whitelists fields and never includes addresses, URLs or tokens', () async {
    service = FeedbackService(supported:false, canSend:() => false);
    const channel = MethodChannel('trace/companion');
    final messenger = TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger;
    messenger.setMockMethodCallHandler(channel, (_) async => {'history':[
      {'state':'CONNECTION_TIMEOUT','stage':'DISCOVERING','elapsedMs':25000,'errorCode':133,
        'address':'aa:bb:cc:dd:ee:ff','url':'https://private.invalid/?token=secret','token':'secret'},
      {'state':'https://private.invalid/?token=secret'},
    ]});
    try {
      final snapshot = await CompanionDiagnosticSnapshot.read();
      expect(snapshot.rows, hasLength(1));
      expect(snapshot.text, contains('133'));
      expect(snapshot.text, isNot(contains('aa:bb'))); expect(snapshot.text, isNot(contains('secret')));
      expect(snapshot.text, isNot(contains('private.invalid')));
    } finally { messenger.setMockMethodCallHandler(channel, null); }
  });
}
