import 'package:ble_monitor/widgets/upgrade_history_list.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  List<Map<String, dynamic>> rows(int count) => List.generate(count, (i) => {
    'taskId': 'task-$i', 'beforeVersion': 30344 + i, 'targetVersion': 30345 + i,
    'startedAt': 1795275007448, 'status': 'success', 'kind': 'patch',
    'initiator': 'mcu', 'durationMs': 25041, 'stage': 'identityVerified',
    'afterVersion': 30345 + i, 'verifiedAt': 1795275032518,
  });
  Future<ScrollController> mount(WidgetTester tester, int count) async {
    final outer = ScrollController();
    await tester.pumpWidget(MaterialApp(home: Scaffold(body: SingleChildScrollView(
      controller: outer, child: Column(children: [
        const SizedBox(height: 120),
        UpgradeHistoryList(records: rows(count), outer: outer),
        const SizedBox(height: 1000),
      ]),
    ))));
    addTearDown(outer.dispose);
    return outer;
  }

  testWidgets('compact window and complete detail dialog', (tester) async {
    await mount(tester, 30);
    expect(tester.getSize(find.byKey(const ValueKey('upgrade-history-window'))).height, lessThanOrEqualTo(280));
    expect(find.textContaining('任务：'), findsNothing);
    await tester.tap(find.byKey(const ValueKey('upgrade-history-task-0')));
    await tester.pumpAndSettle();
    expect(find.text('升级记录详情'), findsOneWidget);
    expect(find.textContaining('任务：task-0'), findsOneWidget);
    expect(find.textContaining('包类型：差分'), findsOneWidget);
    expect(find.textContaining('核验后版本：3.3.45'), findsOneWidget);
    await tester.tap(find.text('关闭'));
    await tester.pumpAndSettle();
    expect(find.text('升级记录详情'), findsNothing);
  });

  testWidgets('same pointer crosses bottom and then moves parent without lifting', (tester) async {
    final outer = await mount(tester, 12);
    final list = tester.widget<ListView>(find.byKey(const ValueKey('upgrade-history-window')));
    final inner = list.controller!;
    inner.jumpTo(inner.position.maxScrollExtent - 20);
    await tester.pump();
    final gesture = await tester.startGesture(tester.getCenter(find.byKey(const ValueKey('upgrade-history-window'))));
    await gesture.moveBy(const Offset(0, -60));
    await tester.pump();
    final before = outer.offset;
    await gesture.moveBy(const Offset(0, -80));
    await tester.pump();
    expect(inner.offset, inner.position.maxScrollExtent);
    expect(outer.offset, greaterThan(before));
    await gesture.up();
    await tester.pumpAndSettle();
  });

  testWidgets('same pointer crosses top and short list passes to parent', (tester) async {
    for (final count in [1, 12]) {
      final outer = await mount(tester, count);
      outer.jumpTo(90);
      await tester.pump();
      final inner = tester.widget<ListView>(find.byKey(const ValueKey('upgrade-history-window'))).controller!;
      if (count > 1) inner.jumpTo(10);
      final gesture = await tester.startGesture(tester.getCenter(find.byKey(const ValueKey('upgrade-history-window'))));
      await gesture.moveBy(const Offset(0, 30));
      await tester.pump();
      final before = outer.offset;
      await gesture.moveBy(const Offset(0, 40));
      await tester.pump();
      expect(inner.offset, 0);
      expect(outer.offset, lessThan(before));
      await gesture.up();
      await tester.pumpAndSettle();
      await tester.pumpWidget(const SizedBox());
    }
  });
}
