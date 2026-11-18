import 'dart:async';
import 'dart:convert';

import 'package:ble_monitor/services/feedback_service.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  late DateTime now;
  late bool allowed;
  late List<Map<String, dynamic>> requests;
  late List<String> tokens;
  late List<FeedbackService> services;
  Future<FeedbackReply> Function(Map<String, dynamic>)? responder;

  FeedbackReply receipt(Map<String, dynamic> request) {
    final time = now.millisecondsSinceEpoch ~/ 1000;
    final nextDay = ((time + 28800) ~/ 86400 + 1) * 86400 - 28800;
    return FeedbackReply(201, {'ok': true, 'batchId': request['batchId'],
      'acceptedIds': (request['messages'] as List).map((dynamic row) => (row as Map)['id']).toList(),
      'receivedAt': time, 'serverTime': time, 'nextAllowedAt': nextDay});
  }

  FeedbackService create() {
    final service = FeedbackService(endpoint: Uri.parse('https://feedback.test/api/public/feedback'),
      supported: true, clock: () => now, canSend: () => allowed,
      readIdentity: () async => {'platform': 'android', 'versionName': '1.0.82', 'versionCode': 108},
      sender: (uri, body, token, cancel) async {
        expect(uri.host, 'feedback.test');
        final captured = jsonDecode(jsonEncode(body)) as Map<String, dynamic>;
        requests.add(captured); tokens.add(token);
        return responder == null ? receipt(captured) : responder!(captured);
      });
    services.add(service);
    return service;
  }

  Future<void> settled(FeedbackService service) async {
    for (var i = 0; i < 100; i++) {
      await Future<void>.delayed(Duration.zero);
      if (!service.sending.value) return;
    }
    fail('Feedback operation did not settle');
  }

  setUp(() {
    SharedPreferences.setMockInitialValues({'version_inventory_v1_enabled': false});
    now = DateTime.utc(2026, 11, 18, 4);
    allowed = false; requests = []; tokens = []; services = []; responder = null;
  });
  tearDown(() { for (final service in services) { service.onClose(); } });

  test('an empty outbox and disabled telemetry never create feedback requests', () async {
    final service = create(); allowed = true;
    await service.poll();
    expect(service.ready.value, isTrue); expect(requests, isEmpty);
    expect((await SharedPreferences.getInstance()).getBool('version_inventory_v1_enabled'), isFalse);
  });

  test('persists text before sending and collects at most ten messages in one daily batch', () async {
    final service = create();
    for (var i = 0; i < 12; i++) { await service.add('message $i'); await settled(service); }
    expect(service.pending, hasLength(12)); expect(requests, isEmpty);
    allowed = true; await service.poll();
    expect(requests, hasLength(1)); expect(requests.single['messages'], hasLength(10));
    expect(service.sent, hasLength(10)); expect(service.pending, hasLength(2));
    await service.add('later today'); await settled(service); await service.poll();
    expect(requests, hasLength(1)); expect(service.pending, hasLength(3));
    now = now.add(const Duration(days: 1)); await service.poll();
    expect(requests, hasLength(2)); expect(requests.last['messages'], hasLength(3));
    expect(service.pending, isEmpty);
  });

  test('daily limits and installation identity survive a restart or App upgrade', () async {
    final first = create(); allowed = true;
    await first.add('first'); await settled(first); first.onClose();
    final second = create(); await second.initialize();
    await second.add('after upgrade'); await settled(second);
    expect(requests, hasLength(1));
    now = now.add(const Duration(days: 1)); await second.poll();
    expect(tokens.toSet(), hasLength(1)); expect(requests, hasLength(2));
  });

  test('definite IP rejection keeps feedback locally and merges later text next day', () async {
    final service = create(); allowed = true;
    responder = (body) async => FeedbackReply(429, {'errorCode': 'RATE_LIMITED', 'scope': 'ip',
      'serverTime': now.millisecondsSinceEpoch ~/ 1000, 'retryAt': now.add(const Duration(hours: 12)).millisecondsSinceEpoch ~/ 1000});
    await service.add('first'); await settled(service);
    expect(service.failure.value, 'IP_DAILY_LIMIT'); expect(service.isSealed(service.pending.first['id'] as String), isFalse);
    await service.add('second'); await settled(service); expect(requests, hasLength(1));
    now = now.add(const Duration(hours: 12)); responder = null; await service.poll();
    expect(requests.last['messages'], hasLength(2)); expect(service.pending, isEmpty);
  });

  test('an uncertain send reuses its immutable batch after restart without losing newer feedback', () async {
    final first = create(); allowed = true;
    responder = (_) async => throw StateError('lost response');
    await first.add('original'); await settled(first);
    await first.add('newer'); await settled(first);
    expect(requests, hasLength(1)); first.onClose();
    final second = create(); await second.initialize();
    expect(second.pending, hasLength(2));
    now = now.add(const Duration(minutes: 6)); responder = null; await second.poll();
    expect(requests[1], requests[0]); expect(second.sent, hasLength(1));
    expect(second.pending.single['body'], 'newer');
    expect(tokens[0], tokens[1]);
  });

  test('concurrent additions and a pending send preserve all queued messages', () async {
    final service = create();
    await Future.wait(List.generate(15, (i) => service.add('concurrent $i')));
    await settled(service); expect(service.pending, hasLength(15));
    final gate = Completer<FeedbackReply>();
    responder = (_) => gate.future; allowed = true;
    final sending = service.poll();
    while (requests.isEmpty) { await Future<void>.delayed(Duration.zero); }
    await service.add('while sending');
    gate.complete(receipt(requests.first)); await sending;
    expect(service.sent, hasLength(10)); expect(service.pending, hasLength(6));
    expect(service.pending.any((item) => item['body'] == 'while sending'), isTrue);
  });

  test('wrong or duplicate acknowledgement IDs never delete pending text', () async {
    final service = create(); allowed = true;
    responder = (request) async => FeedbackReply(201, {...receipt(request).body, 'acceptedIds': ['foreign']});
    await service.add('keep this'); await settled(service);
    expect(service.pending.single['body'], 'keep this'); expect(service.sent, isEmpty);
    expect(service.failure.value, 'SEND_DEFERRED');
  });

  test('background and active update work defer sending without wakeups', () async {
    final service = create(); await service.add('pending'); await settled(service);
    service.didChangeAppLifecycleState(AppLifecycleState.paused); allowed = true;
    now = now.add(const Duration(days: 1)); await service.poll(); expect(requests, isEmpty);
    service.didChangeAppLifecycleState(AppLifecycleState.resumed); await settled(service);
    expect(requests, hasLength(1));
  });

  test('invalid content and full local queues are rejected without discarding existing messages', () async {
    final service = create();
    await expectLater(service.add(' '), throwsFormatException);
    await expectLater(service.add('x' * 2001), throwsFormatException);
    for (var i = 0; i < 50; i++) { await service.add('queued $i'); await settled(service); }
    await expectLater(service.add('overflow'), throwsStateError);
    expect(service.pending, hasLength(50)); expect(requests, isEmpty);
    final reopened = create(); await reopened.initialize(); expect(reopened.pending, hasLength(50));
  });

  test('corrupt storage is preserved rather than silently reset', () async {
    SharedPreferences.setMockInitialValues({FeedbackService.storageKey: '{invalid'});
    final service = create(); await service.poll();
    expect(service.failure.value, 'LOCAL_STORAGE_UNAVAILABLE'); expect(service.ready.value, isFalse);
    expect((await SharedPreferences.getInstance()).getString(FeedbackService.storageKey), '{invalid');
    expect(requests, isEmpty);
  });
}
