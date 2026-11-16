import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:get/get.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:ble_monitor/pages/discover_tab_page.dart';
import 'package:ble_monitor/services/announcement_service.dart';
import 'package:ble_monitor/services/app_prompt_coordinator.dart';

void main() {
  final queue = AppPromptCoordinator.instance;
  final items = [
    TraceAnnouncement(id: 'first', type: TraceAnnouncementType.manual,
      title: 'First notice', body: 'Visible content', pinned: true,
      publishedAt: DateTime.utc(2026, 11, 17, 12)),
    const TraceAnnouncement(id: 'second', type: TraceAnnouncementType.manual,
      title: 'Second notice', body: 'Unread content'),
  ];

  Future<void> mount(WidgetTester tester) async {
    SharedPreferences.setMockInitialValues({});
    await AnnouncementService.unseen(items);
    Get.testMode = true;
    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
    await tester.pumpWidget(GetMaterialApp(navigatorObservers: [queue],
      home: const Scaffold(body: Text('home'))));
  }

  Future<void> dispose(WidgetTester tester) async {
    await tester.pumpWidget(const SizedBox());
    queue.dispose();
    Get.reset();
  }

  testWidgets('backgrounding during entry never consumes an invisible notice or its unvisited page', (tester) async {
    await mount(tester);
    final prompt = createAnnouncementPrompt(announcements: items, automatic: true);
    await tester.pump();
    await tester.pump();
    expect(AnnouncementService.wasPresented(items.first), isFalse);
    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.paused);
    await tester.pump(const Duration(milliseconds: 350));
    expect(AnnouncementService.wasPresented(items.first), isFalse);
    expect(AnnouncementService.wasPresented(items.last), isFalse);

    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
    await tester.pump();
    await tester.pump();
    expect(find.text('First notice'), findsOneWidget);
    expect(find.text('\u7f6e\u9876'), findsOneWidget);
    expect(find.textContaining('\u53d1\u5e03\u4e8e '), findsOneWidget);
    expect(AnnouncementService.wasPresented(items.first), isTrue);
    expect(AnnouncementService.wasPresented(items.last), isFalse);
    await tester.tap(find.text('\u77e5\u9053\u4e86'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 350));
    await prompt.closed;
    expect((await AnnouncementService.unseen(items)).single.id, 'second');
    await dispose(tester);
  });

  testWidgets('manual reading removes that notice from an already queued automatic prompt', (tester) async {
    await mount(tester);
    var ready = false;
    final automatic = createAnnouncementPrompt(announcements: items,
      automatic: true, ready: () => ready);
    final manual = createAnnouncementPrompt(announcements: [items.first]);
    await tester.pump();
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 350));
    await tester.pump();
    expect(find.text('First notice'), findsOneWidget);
    expect(AnnouncementService.wasPresented(items.first), isTrue);
    await tester.tap(find.text('\u77e5\u9053\u4e86'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 350));
    await manual.closed;

    ready = true;
    queue.notify();
    await tester.pump();
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 350));
    await tester.pump();
    expect(find.text('First notice'), findsNothing);
    expect(find.text('Second notice'), findsOneWidget);
    expect(AnnouncementService.wasPresented(items.last), isTrue);
    automatic.cancel();
    await tester.pump();
    await automatic.closed;
    await dispose(tester);
  });
}
