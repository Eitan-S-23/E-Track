import 'dart:async';
import 'package:ble_monitor/services/bluetooth_reconnect.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('adapter off waits, adapter on reconnects the exact remembered target', (tester) async {
    final calls = <String>[];
    final reconnect = BluetoothReconnect(connect: (address) async {
      calls.add(address);
      return true;
    });
    addTearDown(reconnect.dispose);
    reconnect.remember('AA:BB:CC:DD:EE:FF');
    reconnect.linkChanged('aa:bb:cc:dd:ee:ff', false);
    await tester.pump(const Duration(minutes: 2));
    expect(calls, isEmpty);
    reconnect.adapterChanged(true);
    await tester.pump(const Duration(seconds: 1));
    expect(calls, ['AA:BB:CC:DD:EE:FF']);
    await tester.pump(const Duration(minutes: 2));
    expect(calls, hasLength(1));
  });

  testWidgets('duplicate disconnections do not reset the five-attempt budget', (tester) async {
    var calls = 0;
    final reconnect = BluetoothReconnect(connect: (_) async { calls++; return false; });
    addTearDown(reconnect.dispose);
    reconnect.adapterChanged(true);
    reconnect.remember('a');
    for (final seconds in BluetoothReconnect.delays) {
      reconnect.linkChanged('a', false);
      reconnect.linkChanged('a', false);
      await tester.pump(Duration(seconds: seconds));
    }
    expect(calls, 5);
    reconnect.linkChanged('a', false);
    await tester.pump(const Duration(minutes: 5));
    expect(calls, 5);
  });

  testWidgets('intentional disconnect and disposal cancel pending retries', (tester) async {
    var calls = 0;
    final reconnect = BluetoothReconnect(connect: (_) async { calls++; return true; });
    reconnect.adapterChanged(true);
    reconnect.remember('a');
    reconnect.linkChanged('a', false);
    reconnect.forget('A');
    await tester.pump(const Duration(seconds: 10));
    expect(calls, 0);
    reconnect.remember('b');
    reconnect.linkChanged('b', false);
    reconnect.dispose();
    await tester.pump(const Duration(seconds: 10));
    expect(calls, 0);
  });

  testWidgets('OTA hold waits for an existing attempt and suppresses new attempts', (tester) async {
    final gate = Completer<bool>();
    var calls = 0;
    final reconnect = BluetoothReconnect(connect: (_) { calls++; return gate.future; });
    addTearDown(reconnect.dispose);
    reconnect.adapterChanged(true);
    reconnect.remember('a');
    reconnect.linkChanged('a', false);
    await tester.pump(const Duration(seconds: 1));
    final release = reconnect.hold();
    var settled = false;
    final wait = reconnect.settled.then((_) => settled = true);
    await tester.pump(const Duration(minutes: 2));
    expect(settled, isFalse);
    gate.complete(false);
    await tester.pump();
    await wait;
    expect(settled, isTrue);
    await tester.pump(const Duration(minutes: 2));
    expect(calls, 1);
    release();
    release();
    await tester.pump(const Duration(seconds: 2));
    expect(calls, 2);
    reconnect.dispose();
  });

  testWidgets('forgotten in-flight target cannot schedule another retry', (tester) async {
    final gate = Completer<bool>();
    var calls = 0;
    final reconnect = BluetoothReconnect(connect: (_) { calls++; return gate.future; });
    addTearDown(reconnect.dispose);
    reconnect.adapterChanged(true);
    reconnect.remember('a');
    reconnect.linkChanged('a', false);
    await tester.pump(const Duration(seconds: 1));
    reconnect.forget('a');
    gate.complete(false);
    await tester.pump();
    await tester.pump(const Duration(minutes: 2));
    expect(calls, 1);
  });
}
