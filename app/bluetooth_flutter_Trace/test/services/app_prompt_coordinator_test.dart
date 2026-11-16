import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:get/get.dart';
import 'package:ble_monitor/services/app_prompt_coordinator.dart';

void main() {
  testWidgets('updates precede notices and wait for the previous route to leave', (tester) async {
    final queue = AppPromptCoordinator();
    Get.testMode = true;
    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
    await tester.pumpWidget(GetMaterialApp(navigatorObservers: [queue],
      home: const Scaffold(body: Text('home'))));
    final notice = queue.enqueue<void>(builder: (_) => const AlertDialog(title: Text('notice')));
    final update = queue.enqueue<void>(priority: AppPromptCoordinator.updatePriority,
      builder: (_) => const AlertDialog(title: Text('update')));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 250));
    expect(find.text('update'), findsOneWidget);
    expect(find.text('notice'), findsNothing);
    Get.back<void>();
    await tester.pump();
    expect(find.text('notice'), findsNothing);
    await tester.pump(const Duration(milliseconds: 350));
    await tester.pump(const Duration(milliseconds: 350));
    expect(find.text('notice'), findsOneWidget);
    notice.cancel();
    await tester.pump(const Duration(milliseconds: 350));
    await update.closed;
    await notice.closed;
    await tester.pumpWidget(const SizedBox());
    queue.dispose();
    Get.reset();
  });

  testWidgets('cancelling a queued ticket never closes an unrelated dialog', (tester) async {
    final queue = AppPromptCoordinator();
    Get.testMode = true;
    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
    await tester.pumpWidget(GetMaterialApp(navigatorObservers: [queue],
      home: const Scaffold(body: Text('home'))));
    Get.dialog<void>(const AlertDialog(title: Text('foreign')));
    await tester.pump();
    final ticket = queue.enqueue<void>(builder: (_) => const AlertDialog(title: Text('stale')));
    await tester.pump();
    ticket.cancel();
    await tester.pump(const Duration(milliseconds: 400));
    expect(find.text('foreign'), findsOneWidget);
    expect(find.text('stale'), findsNothing);
    await ticket.closed;
    Get.back<void>();
    await tester.pump(const Duration(milliseconds: 400));
    await tester.pumpWidget(const SizedBox());
    queue.dispose();
    Get.reset();
  });

  testWidgets('busy and background defer rather than consume pending notices', (tester) async {
    final queue = AppPromptCoordinator();
    Get.testMode = true;
    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
    await tester.pumpWidget(GetMaterialApp(navigatorObservers: [queue],
      home: const Scaffold(body: Text('home'))));
    var busy = true;
    final ticket = queue.enqueue<void>(ready: () => !busy,
      builder: (_) => const AlertDialog(title: Text('notice')));
    await tester.pump(const Duration(seconds: 1));
    expect(find.text('notice'), findsNothing);
    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.paused);
    busy = false;
    queue.notify();
    await tester.pump(const Duration(seconds: 1));
    expect(find.text('notice'), findsNothing);
    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 300));
    expect(find.text('notice'), findsOneWidget);
    ticket.cancel();
    await tester.pump();
    await ticket.closed;
    await tester.pumpWidget(const SizedBox());
    queue.dispose();
    Get.reset();
  });
}
