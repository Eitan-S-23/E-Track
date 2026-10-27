import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:get/get.dart';
import 'package:ble_monitor/utils/safe_snackbar.dart';

void main() {
  tearDown(Get.reset);

  testWidgets('service root fallback still presents visible feedback', (tester) async {
    await tester.pumpWidget(const GetMaterialApp(home: Scaffold()));
    safeSnackbar('service', 'ready');
    await tester.pumpAndSettle();
    expect(find.text('service: ready'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('page context works without any GetX navigator or Overlay lookup', (tester) async {
    late BuildContext context;
    await tester.pumpWidget(MaterialApp(home: Scaffold(body: Builder(builder: (value) {
      context = value;
      return const Text('page');
    }))));
    safeSnackbar('page', 'ready', context: context);
    await tester.pumpAndSettle();
    expect(find.text('page: ready'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('queued page feedback is dropped after disposal, not retargeted', (tester) async {
    late BuildContext context;
    await tester.pumpWidget(MaterialApp(home: Scaffold(body: Builder(builder: (value) {
      context = value;
      return const Text('page');
    }))));
    safeSnackbar('page', 'ready', context: context);
    await tester.pumpWidget(const GetMaterialApp(home: Scaffold(body: Text('replacement'))));
    await tester.pumpAndSettle();
    expect(find.byType(SnackBar), findsNothing);
    expect(tester.takeException(), isNull);
  });

  testWidgets('covered current route is checked again at delivery', (tester) async {
    late BuildContext context;
    await tester.pumpWidget(MaterialApp(home: Scaffold(body: Builder(builder: (value) {
      context = value;
      return const Text('page');
    }))));
    safeSnackbar('page', 'ready', context: context);
    unawaited(Navigator.of(context).push(MaterialPageRoute<void>(
        builder: (_) => const Scaffold(body: Text('next')))));
    await tester.pumpAndSettle();
    expect(find.byType(SnackBar), findsNothing);
    expect(tester.takeException(), isNull);
  });

  testWidgets('incoming route animation does not queue feedback for later', (tester) async {
    await tester.pumpWidget(const MaterialApp(home: Scaffold(body: Text('home'))));
    late BuildContext moving;
    unawaited(Navigator.of(tester.element(find.text('home'))).push(MaterialPageRoute<void>(
        builder: (_) => Scaffold(body: Builder(builder: (value) {
          moving = value;
          return const Text('moving');
        })))));
    await tester.pump();
    safeSnackbar('page', 'ready', context: moving);
    await tester.pump(const Duration(milliseconds: 50));
    await tester.pumpAndSettle();
    expect(find.byType(SnackBar), findsNothing);
    expect(tester.takeException(), isNull);
  });

  testWidgets('background page feedback stays suppressed', (tester) async {
    late BuildContext context;
    await tester.pumpWidget(MaterialApp(home: Scaffold(body: Builder(builder: (value) {
      context = value;
      return const Text('page');
    }))));
    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.paused);
    safeSnackbar('page', 'ready', context: context);
    await tester.pump();
    expect(find.byType(SnackBar), findsNothing);
    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
    await tester.pumpAndSettle();
    expect(find.byType(SnackBar), findsNothing);
    expect(tester.takeException(), isNull);
  });

  testWidgets('missing Navigator or Messenger is not an exception', (tester) async {
    safeSnackbar('startup', 'ready');
    await tester.pump();
    late BuildContext context;
    await tester.pumpWidget(Directionality(textDirection: TextDirection.ltr,
        child: Builder(builder: (value) {
          context = value;
          return const Text('no messenger');
        })));
    safeSnackbar('page', 'ready', context: context);
    await tester.pump();
    expect(find.byType(SnackBar), findsNothing);
    expect(tester.takeException(), isNull);
  });

  testWidgets('missing Scaffold is guarded and unrelated errors propagate', (tester) async {
    late BuildContext context;
    await tester.pumpWidget(MaterialApp(home: Builder(builder: (value) {
      context = value;
      return const Text('no scaffold');
    })));
    safeSnackbar('page', 'ready', context: context);
    await tester.pump();
    expect(tester.takeException(), isNull);
    expect(find.byType(SnackBar), findsNothing);
    await tester.pumpWidget(MaterialApp(home: _BrokenMessenger(
        child: Scaffold(body: Builder(builder: (value) {
          context = value;
          return const Text('broken');
        })))));
    safeSnackbar('page', 'ready', context: context);
    await tester.pump();
    expect(tester.takeException(), isA<FlutterError>().having(
        (error) => error.message, 'message', 'unrelated notification failure'));
  });
}

class _BrokenMessenger extends ScaffoldMessenger {
  const _BrokenMessenger({required super.child});
  @override
  ScaffoldMessengerState createState() => _BrokenMessengerState();
}

class _BrokenMessengerState extends ScaffoldMessengerState {
  @override
  ScaffoldFeatureController<SnackBar, SnackBarClosedReason> showSnackBar(
      SnackBar snackBar, {AnimationStyle? snackBarAnimationStyle}) {
    throw FlutterError('unrelated notification failure');
  }
}
