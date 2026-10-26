import 'package:ble_monitor/utils/safe_snackbar.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:get/get.dart';

void main() {
  tearDown(Get.reset);
  testWidgets('startup notification without an overlay does not throw', (tester) async {
    safeSnackbar('Error', 'No connection');
    await tester.pump();
    expect(tester.takeException(), isNull);
  });
  testWidgets('notification is visible after root Scaffold is ready', (tester) async {
    await tester.pumpWidget(const GetMaterialApp(home: Scaffold(body: Text('Home'))));
    safeSnackbar('Error', 'No connection');
    await tester.pump();
    await tester.pump();
    expect(find.text('Error: No connection'), findsOneWidget);
    expect(tester.takeException(), isNull);
    await tester.pump(const Duration(seconds: 5));
  });
}
