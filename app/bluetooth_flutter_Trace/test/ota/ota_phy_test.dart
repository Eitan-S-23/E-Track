import 'dart:async';

import 'package:ble_monitor/ota/ota_phy.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';

Map<String, Object?> reply(Map<String, Object?> request) => {
  ...request, 'schema': 1, 'connectionGeneration': 3, 'elapsedMicros': 12000,
  'status': 'observed', 'beforeReadStatus': 0, 'beforeTxPhy': 1,
  'beforeRxPhy': 1, 'txPhy': 2, 'rxPhy': 2,
  if (request['policy'] == 'prefer2m') ...{
    'updateStatus': 0, 'readStatus': 0, 'updateTxPhy': 2, 'updateRxPhy': 2,
  },
};

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  Future<OtaPhyObservation> run(OtaPhyClient client, {String policy = 'prefer2m'}) =>
      client.observe(policy: policy, remoteId: 'aa:bb:cc:dd:ee:ff', requestId: 'trial-1');

  test('channel request binds normalized device and returns actual readback', () async {
    final messenger = TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger;
    messenger.setMockMethodCallHandler(OtaPhyClient.channel, (call) async {
      expect(call.method, 'p34ObservePhy');
      final request = Map<String, Object?>.from(call.arguments as Map);
      expect(request, {'policy': 'prefer2m', 'remoteId': 'AA:BB:CC:DD:EE:FF', 'requestId': 'trial-1'});
      return reply(request);
    });
    addTearDown(() => messenger.setMockMethodCallHandler(OtaPhyClient.channel, null));
    final result = await run(const OtaPhyClient(isAndroid: true));
    expect(result.permitsTransfer, isTrue);
    expect(result.fields['beforeTxPhy'], 1);
    expect(() => result.fields['txPhy'] = 1, throwsUnsupportedError);
  });

  for (final policy in ['observe', 'prefer2m']) {
    for (final phy in [1, 2, 3]) {
      test('$policy records actual PHY $phy, never request acceptance as 2M', () async {
        final client = OtaPhyClient(isAndroid: true, invoke: (_, request) async => {
          ...reply(request), 'txPhy': phy, 'rxPhy': phy,
        });
        final result = await run(client, policy: policy);
        expect(result.permitsTransfer, policy == 'observe' || phy == 2);
        expect(result.fields['txPhy'], phy);
      });
    }
  }
  test('one direction remaining 1M blocks the 2M candidate', () async {
    final result = await run(OtaPhyClient(isAndroid: true, invoke: (_, request) async => {
      ...reply(request), 'rxPhy': 1,
    }));
    expect(result.permitsTransfer, isFalse);
  });
  test('malformed, stale and incomplete callback evidence fails closed', () async {
    final mutations = <Map<String, Object?>>[
      {'schema': 2}, {'requestId': 'old'}, {'remoteId': '00:00:00:00:00:00'},
      {'policy': 'observe'}, {'connectionGeneration': 0}, {'elapsedMicros': -1},
      {'txPhy': 0}, {'rxPhy': 2.0}, {'beforeReadStatus': 1},
      {'updateStatus': null}, {'readStatus': null}, {'updateTxPhy': null},
      {'status': 'requested'},
    ];
    for (final mutation in mutations) {
      final result = await run(OtaPhyClient(isAndroid: true,
          invoke: (_, request) async => {...reply(request), ...mutation}));
      expect(result.permitsTransfer, isFalse, reason: '$mutation');
      expect(result.fields['status'], 'invalid-native-result');
    }
    final accepted = await run(OtaPhyClient(isAndroid: true, invoke: (_, __) async => true));
    expect(accepted.permitsTransfer, isFalse);
  });
  for (final status in ['timeout', 'disconnected', 'read-failed', 'update-failed', 'native-call-failed']) {
    test('native $status cannot confirm transfer', () async {
      final result = await run(OtaPhyClient(isAndroid: true,
          invoke: (_, request) async => {...reply(request), 'status': status}));
      expect(result.permitsTransfer, isFalse);
    });
  }
  test('unsupported platform never invokes the native bridge', () async {
    final result = await run(OtaPhyClient(isAndroid: false,
        invoke: (_, __) async => throw StateError('must not invoke')));
    expect(result.fields['status'], 'unsupported-platform');
  });
  test('missing plugin and platform failures are explicit, not observed PHY', () async {
    for (final error in [MissingPluginException(), PlatformException(code: 'PHY_STALE')]) {
      final result = await run(OtaPhyClient(isAndroid: true, invoke: (_, __) async => throw error));
      expect(result.permitsTransfer, isFalse);
      expect(result.fields.containsKey('txPhy'), isFalse);
    }
  });
  testWidgets('bounded channel timeout rejects a later successful result', (tester) async {
    final pending = Completer<Object?>();
    Map<String, Object?>? request;
    final future = run(OtaPhyClient(isAndroid: true, invoke: (_, args) {
      request = args;
      return pending.future;
    }));
    await tester.pump(const Duration(seconds: 5));
    final result = await future;
    expect(result.fields['status'], 'channel-timeout');
    pending.complete(reply(request!));
    await tester.pump();
    expect(result.permitsTransfer, isFalse);
  });
}
