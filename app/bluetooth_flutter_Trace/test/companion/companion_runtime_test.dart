import 'dart:async';
import '../account_fixture.dart';

import 'package:ble_monitor/companion/companion_platform.dart';
import 'package:ble_monitor/companion/companion_protocol.dart';
import 'package:ble_monitor/companion/companion_runtime.dart';
import 'package:ble_monitor/ota/ota_device_info.dart';
import 'package:ble_monitor/ota/ota_firmware_latest.dart';
import 'package:ble_monitor/ota/ota_link_stats.dart';
import 'package:ble_monitor/ota/ota_upgrade_consent.dart';
import 'package:ble_monitor/services/bluetooth_service.dart';
import 'package:ble_monitor/services/ota_service.dart';
import 'package:flutter/services.dart';
import 'package:flutter_blue_plus/flutter_blue_plus.dart'
    show BluetoothConnectionState, BluetoothDevice;
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

const _address = 'aa:bb:cc:dd:ee:ff';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  const channel = MethodChannel('test/companion-runtime');
  const codec = StandardMethodCodec();
  final messenger = TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger;
  late _Ble ble;
  late _Ota ota;
  late CompanionRuntime runtime;
  late SharedPreferences preferences;
  late Completer<void> ready;
  late List<Map<dynamic, dynamic>> states;
  late List<Map<dynamic, dynamic>> diagnostics;
  late List<Map<dynamic, dynamic>> schedules;
  late Map<String, Object?> settings;
  var controlTime = 0;
  bool acceptState = true, throwState = false;
  bool acceptSchedule = true;
  var runtimeId = 'runtime-1';

  Future<Object?> callback(String method, Object? arguments) {
    final result = Completer<Object?>();
    messenger.handlePlatformMessage(channel.name,
      codec.encodeMethodCall(MethodCall(method, arguments)), (data) {
        result.complete(data == null ? null : codec.decodeEnvelope(data));
      });
    return result.future;
  }

  Future<void> until(bool Function() condition) async {
    final deadline = DateTime.now().add(const Duration(seconds: 5));
    while (!condition()) {
      if (DateTime.now().isAfter(deadline)) fail('Runtime did not settle: ${runtime.status.value}');
      await Future<void>.delayed(const Duration(milliseconds: 1));
    }
    // Allow the flight's finally block to retire before another platform event.
    await Future<void>.delayed(Duration.zero);
  }

  Future<void> start({String reason = 'periodic'}) async {
    runtime.onInit();
    await ready.future;
    expect(await callback('wake', {'runtimeId': runtimeId, 'revision': 'revision-1',
      'address': _address, 'reason': reason}), isTrue);
  }

  Future<void> wake(String reason) async {
    expect(await callback('wake', {'runtimeId': runtimeId, 'revision': 'revision-1',
      'address': _address, 'reason': reason}), isTrue);
  }

  CompanionMessage choice(CompanionMessage offer, String value) => CompanionMessage(
    'CHOICE', offer.session, offer.request, [offer.fields[0], offer.fields[1], offer.fields[2], value]);

  setUp(() async {
    SharedPreferences.setMockInitialValues({});
    preferences = await SharedPreferences.getInstance();
    ready = Completer<void>();
    states = [];
    diagnostics = [];
    schedules = [];
    controlTime = 0;
    settings = {'intervalHours': 12, 'wifiOnly': true, 'unmetered': true};
    acceptState = true;
    acceptSchedule = true;
    throwState = false;
    runtimeId = 'runtime-1';
    ble = _Ble();
    ota = _Ota(ble);
    runtime = CompanionRuntime(platform: CompanionPlatform(channel: channel, supported: true),
      bluetooth: ble, ota: ota, controlClock: () => controlTime);
    messenger.setMockMethodCallHandler(channel, (call) async {
      if (call.method == 'ready') {
        ready.complete();
        return settings;
      }
      if (call.method == 'snapshot') return settings;
      if (call.method == 'scheduleCheck') {
        schedules.add(Map<dynamic, dynamic>.from(call.arguments as Map));
        return acceptSchedule;
      }
      if (call.method == 'diagnostic' || call.method == 'journal') {
        diagnostics.add(Map<dynamic, dynamic>.from(call.arguments as Map));
        return true;
      }
      if (call.method == 'state') {
        states.add(Map<dynamic, dynamic>.from(call.arguments as Map));
        if (throwState) throw PlatformException(code: 'OWNER_LOST');
        return acceptState;
      }
      return null;
    });
  });

  tearDown(() async {
    ble.releaseGates();
    ota.releaseGates();
    await callback('lost', {'runtimeId': runtimeId});
    runtime.onClose();
    await Future<void>.delayed(Duration.zero);
    await ble.notifications.close();
    await ble.device.states.close();
    await ota.activity.close();
    ota.onClose();
    ble.onClose();
    messenger.setMockMethodCallHandler(channel, null);
  });

  test('cold wake establishes identity and performs one periodic query', () async {
    await start();
    await until(() => runtime.status.value == 'NO_UPDATE');
    expect(ble.connects, 1);
    expect(ota.reads, 2);
    expect(ota.checks, 1);
    expect(ota.owners.every((id) => id == runtimeId), isTrue);
    expect(states.last['checkFinished'], isTrue);
    expect(await callback('probe', {'runtimeId': runtimeId}), runtimeId);
    expect(await callback('probe', {'runtimeId': 'old'}), isNull);
    expect(await callback('wake', {'runtimeId': runtimeId, 'revision': 'wrong',
      'address': _address, 'reason': 'manual'}), isFalse);
    expect(ota.checks, 1);
  });

  test('successful check persists its actual twelve-hour native deadline; control probes do not replace it', () async {
    await start();
    await until(() => runtime.status.value == 'NO_UPDATE');
    final checked = preferences.getInt('companion_attempt_$_address')!;
    expect(schedules.single['nextCheckAt'], checked + const Duration(hours: 12).inMilliseconds);
    expect(schedules.single['runtimeId'], runtimeId);
    controlTime = const Duration(hours: 2).inMilliseconds;
    await callback('probe', {'runtimeId': runtimeId});
    await until(() => diagnostics.any((d) => d['status'] == 'CONTROL_CHECK_READY'));
    expect(schedules, hasLength(1));
    expect(ota.checks, 1);
  });

  test('server cooldown preserves its returned deadline and does not become failure or restart the hour', () async {
    ota.noUpdate = false;
    ota.cloudFailure = 'CHECK_TOO_SOON';
    ota.cloudRetryAt = DateTime.now().add(const Duration(minutes: 32)).millisecondsSinceEpoch;
    await start();
    await until(() => runtime.status.value == 'CHECK_WAITING');
    final retry = ota.cloudRetryAt!;
    expect(ota.checks, 1);
    expect(schedules.last['nextCheckAt'], retry);
    expect(preferences.getInt('account_auto_retry_${ota.accounts.accountId}'), retry);
    expect(preferences.getInt('companion_attempt_$_address'), isNull);
    expect(preferences.getInt('account_auto_last_${ota.accounts.accountId}'), isNull);
    expect(states.last['checkFinished'], isTrue);
    expect(states.any((s) => s['status'] == 'CHECK_FAILED'), isFalse);
    expect(diagnostics.any((d) => d['reason'] == 'CHECK_TOO_SOON' && d['clockSource'] == 'server_deadline'), isTrue);
    final before = schedules.length;
    await wake('foreground');
    await until(() => schedules.length > before && runtime.status.value == 'CHECK_WAITING');
    expect(ota.checks, 1);
    expect(schedules.last['nextCheckAt'], retry, reason: 'Opening UI must not postpone the pending retry to twelve hours');
    expect(ota.upgrades, 0);
    expect(ota.messages.where((m) => m.kind == 'STATE').last.fields, ['BUSY']);
  });

  test('expired persisted cooldown is retried by recovery without UI and cleared only after a successful query', () async {
    ota.noUpdate = false;
    ota.cloudFailure = 'CHECK_TOO_SOON';
    ota.cloudRetryAt = DateTime.now().add(const Duration(minutes: 20)).millisecondsSinceEpoch;
    await start();
    await until(() => runtime.status.value == 'CHECK_WAITING');
    await preferences.setInt('account_auto_retry_${ota.accounts.accountId}', DateTime.now().millisecondsSinceEpoch - 1);
    ota.cloudFailure = null;
    ota.cloudRetryAt = null;
    ota.noUpdate = true;
    await wake('recovery');
    await until(() => ota.checks == 2 && runtime.status.value == 'NO_UPDATE');
    expect(preferences.getInt('account_auto_retry_${ota.accounts.accountId}'), isNull);
    expect(ota.automaticChecks, [true, true]);
    expect(ble.connects, 1);
  });

  test('local one-hour spacing schedules only the remaining time without advancing successful-check markers', () async {
    await start();
    await until(() => runtime.status.value == 'NO_UPDATE');
    final checked = preferences.getInt('companion_attempt_$_address');
    final last = DateTime.now().subtract(const Duration(minutes: 50)).millisecondsSinceEpoch;
    await preferences.setInt('account_auto_last_${ota.accounts.accountId}', last);
    await wake('periodic');
    await until(() => runtime.status.value == 'CHECK_WAITING');
    expect(ota.checks, 1);
    expect(schedules.last['nextCheckAt'], last + const Duration(hours: 1).inMilliseconds);
    expect(preferences.getInt('companion_attempt_$_address'), checked);
    expect(preferences.getInt('account_auto_last_${ota.accounts.accountId}'), last);
  });

  test('explicit manual check remains available during automatic cooldown without changing the automatic budget marker', () async {
    ota.noUpdate = false;
    ota.cloudFailure = 'CHECK_TOO_SOON';
    ota.cloudRetryAt = DateTime.now().add(const Duration(minutes: 20)).millisecondsSinceEpoch;
    await start();
    await until(() => runtime.status.value == 'CHECK_WAITING');
    ota.cloudFailure = null;
    ota.noUpdate = true;
    await runtime.manualCheck(_address);
    await until(() => ota.checks == 2 && runtime.status.value == 'NO_UPDATE');
    expect(ota.automaticChecks, [true, false]);
    expect(preferences.getInt('account_auto_last_${ota.accounts.accountId}'), isNull);
    expect(preferences.getInt('account_auto_retry_${ota.accounts.accountId}'), isNull);
  });

  test('missing server deadline uses an explicit bounded fallback rather than a fabricated server timestamp', () async {
    ota.noUpdate = false;
    ota.cloudFailure = 'CHECK_TOO_SOON';
    final before = DateTime.now().millisecondsSinceEpoch;
    await start();
    await until(() => runtime.status.value == 'CHECK_WAITING');
    final after = DateTime.now().millisecondsSinceEpoch;
    final at = schedules.last['nextCheckAt'] as int;
    expect(at, greaterThanOrEqualTo(before + const Duration(hours: 1).inMilliseconds));
    expect(at, lessThanOrEqualTo(after + const Duration(hours: 1).inMilliseconds));
    expect(diagnostics.any((d) => d['reason'] == 'CHECK_TOO_SOON' && d['clockSource'] == 'fallback_hour'), isTrue);
  });

  test('native scheduling failure retains a real successful query and link, with an explicit diagnostic gap', () async {
    acceptSchedule = false;
    await start();
    await until(() => runtime.status.value == 'NO_UPDATE');
    expect(runtime.handles(_address), isTrue);
    expect(ota.checks, 1);
    expect(diagnostics.any((d) => d['status'] == 'CHECK_WAKE_SCHEDULE_FAILED' && d['reason'] == 'native_schedule_rejected'), isTrue);
  });

  test('temporary initialization failure can retry on the next native wake', () async {
    ble.failFirstInitialization = true;
    await start();
    await until(() => runtime.status.value == 'NO_UPDATE');
    expect(ble.initializations, 2);
    expect(ota.checks, 1);
  });

  for (final throwing in [false, true]) {
    test('native state ${throwing ? 'error' : 'rejection'} stops before connecting', () async {
      acceptState = false;
      throwState = throwing;
      await start();
      await until(() => runtime.status.value == 'NATIVE_OWNER_UNAVAILABLE');
      expect(runtime.handles(_address), isFalse);
      expect(ble.connects, 0);
      expect(ota.checks, 0);
      expect(ble.disconnects, 1);
    });
  }

  test('recent recovery skips HTTP but a device request bypasses the interval', () async {
    await start();
    await until(() => runtime.status.value == 'NO_UPDATE');
    await wake('recovery');
    await until(() => runtime.status.value == 'CONNECTED');
    expect(ota.checks, 1);
    final session = ota.messages.firstWhere((m) => m.kind == 'HELLO').session;
    ble.emit(CompanionMessage('CHECK', session, 1));
    await until(() => ota.checks == 2 && runtime.status.value == 'NO_UPDATE');
    ble.emit(CompanionMessage('CHECK', session, 1));
    await Future<void>.delayed(const Duration(milliseconds: 10));
    expect(ota.checks, 2, reason: 'The same MCU request is not replayed');
    await runtime.manualCheck(_address);
    await until(() => ota.checks == 3 && runtime.status.value == 'NO_UPDATE');
  });

  test('foreground repairs silent notification loss without opening an OTA page', () async {
    await start();
    await until(() => runtime.status.value == 'NO_UPDATE');
    final session = ota.messages.firstWhere((m) => m.kind == 'HELLO').session;
    final subscriptions = ble.subscriptions;
    ble.notifyEnabled = false;
    await wake('foreground');
    await until(() => runtime.status.value == 'CONNECTED' && ble.subscriptions > subscriptions);
    expect(ota.messages.where((m) => m.kind == 'HELLO').last.session, session);
    expect(ble.connects, 1);
    expect(ota.reads, 2);
    expect(ota.checks, 1, reason: 'Control repair must not spend an update query');
    ble.emit(CompanionMessage('CHECK', session, 1));
    await until(() => ota.checks == 2 && runtime.status.value == 'NO_UPDATE');
  });

  test('native heartbeat repairs an idle channel and coalesces overlapping probes', () async {
    await start();
    await until(() => runtime.status.value == 'NO_UPDATE');
    expect(await callback('probe', {'runtimeId': runtimeId}), runtimeId);
    expect(ota.messages.where((m) => m.kind == 'HELLO'), hasLength(1));
    controlTime = const Duration(hours: 2).inMilliseconds;
    ble.notifyEnabled = false;
    ota.helloGate = Completer<void>();
    expect(await callback('probe', {'runtimeId': 'obsolete'}), isNull);
    expect(await callback('probe', {'runtimeId': runtimeId}), runtimeId);
    await until(() => ota.messages.where((m) => m.kind == 'HELLO').length == 2);
    for (var i = 0; i < 3; i++) {
      expect(await callback('probe', {'runtimeId': runtimeId}), runtimeId);
    }
    ota.helloGate!.complete();
    await until(() => diagnostics.any((d) => d['status'] == 'CONTROL_CHECK_READY') && runtime.status.value == 'NO_UPDATE');
    expect(ble.connects, 1);
    expect(ota.checks, 1);
    expect(ota.messages.where((m) => m.kind == 'HELLO'), hasLength(2));
    final session = ota.messages.lastWhere((m) => m.kind == 'HELLO').session;
    ble.emit(CompanionMessage('CHECK', session, 1));
    await until(() => ota.checks == 2 && runtime.status.value == 'NO_UPDATE');
  });

  for (final closed in [false, true]) {
    test('notification ${closed ? 'completion' : 'error'} repairs itself while GATT remains connected', () async {
      await start();
      await until(() => runtime.status.value == 'NO_UPDATE');
      if (closed) {
        await ble.closeReaders();
      } else {
        ble.notifications.addError(StateError('fixture notify error'));
      }
      await until(() => diagnostics.any((d) => d['status'] == 'CONTROL_CHECK_READY') && runtime.status.value == 'NO_UPDATE');
      expect(ble.connects, 1);
      expect(ble.disconnects, 0);
      expect(ota.checks, 1);
      expect(diagnostics.any((d) => d['status'] == 'CONTROL_CHANNEL_LOST' &&
        d['reason'] == (closed ? 'notify_closed' : 'notify_error')), isTrue);
      final session = ota.messages.lastWhere((m) => m.kind == 'HELLO').session;
      ble.emit(CompanionMessage('CHECK', session, 1));
      await until(() => ota.checks == 2 && runtime.status.value == 'NO_UPDATE');
    });
  }

  test('a device check arriving during same-session repair is served once', () async {
    await start();
    await until(() => runtime.status.value == 'NO_UPDATE');
    final session = ota.messages.firstWhere((m) => m.kind == 'HELLO').session;
    ota.helloGate = Completer<void>();
    await wake('foreground');
    await until(() => ota.messages.where((m) => m.kind == 'HELLO').length == 2);
    ble.emit(CompanionMessage('CHECK', session, 1));
    ble.emit(CompanionMessage('CHECK', session, 1));
    expect(ota.checks, 1);
    ota.helloGate!.complete();
    await until(() => ota.checks == 2 && runtime.status.value == 'NO_UPDATE');
    expect(ble.connects, 1);
    expect(ota.maxConcurrent, 1);
  });

  test('health check preserves an existing offer and its one-time Later choice', () async {
    ota.latest = _latest();
    await start();
    await until(() => runtime.status.value == 'READY_AWAITING_DEVICE_CHOICE');
    final offer = ota.offers.single;
    controlTime = const Duration(minutes: 2).inMilliseconds;
    expect(await callback('probe', {'runtimeId': runtimeId}), runtimeId);
    await until(() => diagnostics.any((d) => d['status'] == 'CONTROL_CHECK_READY') && runtime.status.value == 'READY_AWAITING_DEVICE_CHOICE');
    expect(ota.offers, hasLength(1));
    expect(ota.downloads, 1);
    expect(ota.checks, 1);
    expect(ota.messages.lastWhere((m) => m.kind == 'HELLO').session, offer.session);
    ble.emit(choice(offer, 'LATER'));
    await until(() => runtime.status.value == 'DEFERRED');
    ble.emit(choice(offer, 'NOW'));
    await Future<void>.delayed(Duration.zero);
    expect(ota.upgrades, 0);
  });

  test('health recovery waits for the existing OTA owner instead of taking its radio', () async {
    await start();
    await until(() => runtime.status.value == 'NO_UPDATE');
    ota.foreignBusy = true;
    ota.activity.add(true);
    controlTime = const Duration(minutes: 2).inMilliseconds;
    expect(await callback('probe', {'runtimeId': runtimeId}), runtimeId);
    await Future<void>.delayed(Duration.zero);
    expect(ota.messages.where((m) => m.kind == 'HELLO'), hasLength(1));
    expect(ble.disconnects, 0);
    ota.foreignBusy = false;
    ota.activity.add(false);
    await until(() => diagnostics.any((d) => d['status'] == 'CONTROL_CHECK_READY') && runtime.status.value == 'NO_UPDATE');
    expect(ota.checks, 1);
    expect(ble.connects, 1);
  });

  test('old firmware without companion replies keeps its foreground update fallback', () async {
    runtime = CompanionRuntime(platform: CompanionPlatform(channel: channel, supported: true),
      bluetooth: ble, ota: ota, controlClock: () => controlTime,
      controlResponseTimeout: const Duration(milliseconds: 30));
    ota.answerHello = false;
    await start();
    await until(() => runtime.status.value == 'NO_UPDATE');
    controlTime = const Duration(minutes: 2).inMilliseconds;
    expect(await callback('probe', {'runtimeId': runtimeId}), runtimeId);
    await until(() => runtime.status.value == 'DEVICE_CONTROL_UNSUPPORTED');
    expect(diagnostics.any((d) => d['status'] == 'CONTROL_CHECK_UNSUPPORTED'), isTrue);
    expect(ble.connects, 1);
    expect(ble.disconnects, 0);
    expect(ota.checks, 1);
    final hellos = ota.messages.where((m) => m.kind == 'HELLO').length;
    expect(await callback('probe', {'runtimeId': runtimeId}), runtimeId);
    await Future<void>.delayed(Duration.zero);
    expect(ota.messages.where((m) => m.kind == 'HELLO'), hasLength(hellos));
    ota.answerHello = true;
    await wake('foreground');
    await until(() => runtime.status.value == 'CONNECTED');
    expect(ble.connects, 1);
    expect(ota.checks, 1);
  });

  test('missing control response retires GATT and leaves retries to native cooldown', () async {
    runtime = CompanionRuntime(platform: CompanionPlatform(channel: channel, supported: true),
      bluetooth: ble, ota: ota, controlClock: () => controlTime,
      controlResponseTimeout: const Duration(milliseconds: 30));
    await start();
    await until(() => runtime.status.value == 'NO_UPDATE');
    ota.answerHello = false;
    controlTime = const Duration(minutes: 2).inMilliseconds;
    expect(await callback('probe', {'runtimeId': runtimeId}), runtimeId);
    await until(() => runtime.status.value == 'CONNECTION_FAILED');
    expect(ble.disconnects, 1);
    expect(states.last['connected'], isFalse);
    expect(diagnostics.any((d) => d['status'] == 'CONTROL_CHECK_FAILED' && d['errorCode'] == 'CONTROL_RESPONSE_TIMEOUT'), isTrue);
    for (var i = 0; i < 3; i++) {
      expect(await callback('probe', {'runtimeId': runtimeId}), runtimeId);
    }
    await Future<void>.delayed(Duration.zero);
    expect(ble.connects, 1, reason: 'Heartbeat must not bypass the native retry window');
    expect(ota.checks, 1);
    ota.answerHello = true;
    await wake('recovery');
    await until(() => runtime.status.value == 'CHECK_WAITING');
    expect(ble.connects, 2);
    expect(ota.checks, 1);
  });

  test('manual work arriving during a query is coalesced instead of dropped', () async {
    await start();
    await until(() => runtime.status.value == 'NO_UPDATE');
    ota.checkGate = Completer<void>();
    await wake('manual');
    await until(() => ota.checks == 2);
    final first = runtime.manualCheck(_address);
    final second = runtime.manualCheck(_address);
    expect(ota.checks, 2);
    ota.checkGate!.complete();
    await first;
    await second;
    await until(() => ota.checks == 3 && runtime.status.value == 'NO_UPDATE');
    expect(ota.maxConcurrent, 1);
  });

  test('failed foreground identity read restores the MCU control session promptly', () async {
    await start();
    await until(() => runtime.status.value == 'NO_UPDATE');
    final oldSession = ota.messages.firstWhere((m) => m.kind == 'HELLO').session;
    ota.identityAvailable = false;
    ota.activity.add(false); // Foreground GET_INFO has failed and released its owner.
    await until(() => ota.reads == 3 && runtime.status.value == 'CHECK_WAITING');
    expect(ota.checks, 1, reason: 'Identity recovery does not bypass the HTTP interval');
    final newSession = ota.messages.lastWhere((m) => m.kind == 'HELLO').session;
    expect(newSession, isNot(oldSession));
    ble.emit(CompanionMessage('CHECK', newSession, 1));
    await until(() => ota.checks == 2 && runtime.status.value == 'NO_UPDATE');
  });

  test('HTTP failure is not published as no-update or a finished check', () async {
    ota.noUpdate = false;
    await start();
    await until(() => runtime.status.value == 'CHECK_FAILED');
    expect(states.last['checkFinished'], isFalse);
    expect(ota.messages.where((m) => m.kind == 'STATE').last.fields, ['FAILED']);
  });

  for (final reuse in [false, true]) {
    for (final delay in ['discovery', 'subscription', 'completed-subscription']) {
      test('late $delay cannot occupy a new control session; reuse=$reuse', () async {
        ble.reuse = reuse;
        ble.completedSubscription = delay == 'completed-subscription';
        await start();
        await until(() => runtime.status.value == 'NO_UPDATE');
        final oldSession = ota.messages.lastWhere((m) => m.kind == 'HELLO').session;
        final gate = _Gate();
        if (delay == 'discovery') { ble.discoveryGate = gate; } else { ble.subscriptionGate = gate; }
        ota.foreignBusy = true;
        ota.activity.add(true);
        ota.foreignBusy = false;
        ota.activity.add(false);
        await gate.entered.future;
        ble.loseConnection();
        await until(() => ota.messages.where((m) => m.kind == 'HELLO').length == 2 && runtime.status.value == 'CHECK_WAITING');
        expect(gate.release.isCompleted, isFalse, reason: 'S2 must not wait for the stale attachment');
        final session = ota.messages.lastWhere((m) => m.kind == 'HELLO').session;
        expect(session, isNot(oldSession));
        final request = CompanionMessage('CHECK', session, 1).encode();
        ble.notifications.add(request.sublist(0, 15));
        gate.release.complete();
        await gate.finished.future;
        await Future<void>.delayed(const Duration(milliseconds: 10));
        ble.notifications.add(request.sublist(15));
        await until(() => ota.checks == 2 && runtime.status.value == 'NO_UPDATE');
        ble.emit(CompanionMessage('CHECK', oldSession, 99));
        await Future<void>.delayed(const Duration(milliseconds: 10));
        expect(ota.checks, 2);
        expect(ble.connects, 2, reason: 'No third reconnect may be needed to restore CHECK');
      });
    }
  }

  test('a completed foreign identity query restores the companion owner without another HTTP interval', () async {
    await start();
    await until(() => runtime.status.value == 'NO_UPDATE');
    final session = ota.messages.lastWhere((m) => m.kind == 'HELLO').session;
    ota.identityAddress = 'bb:cc:dd:ee:ff:00';
    expect(ota.deviceInfo, isNotNull);
    ota.activity.add(false);
    await until(() => ota.reads == 3 && runtime.status.value == 'CHECK_WAITING');
    expect(ota.identityAddress, _address);
    expect(ota.checks, 1);
    final restored = ota.messages.lastWhere((m) => m.kind == 'HELLO').session;
    expect(restored, isNot(session));
    ble.emit(CompanionMessage('CHECK', restored, 1));
    await until(() => ota.checks == 2 && runtime.status.value == 'NO_UPDATE');
  });

  test('an in-flight S1 metadata response cannot publish an offer into S2', () async {
    await start();
    await until(() => runtime.status.value == 'NO_UPDATE');
    final session = ota.messages.lastWhere((m) => m.kind == 'HELLO').session;
    ota.checkGate = Completer<void>();
    ble.emit(CompanionMessage('CHECK', session, 1));
    await until(() => ota.checks == 2);
    ota.latest = _latest();
    ble.loseConnection();
    await Future<void>.delayed(const Duration(milliseconds: 10));
    ota.checkGate!.complete();
    await until(() => ota.messages.where((m) => m.kind == 'HELLO').length == 2 && runtime.status.value == 'CHECK_WAITING');
    expect(ota.offers, isEmpty);
    expect(ota.downloads, 0);
    final restored = ota.messages.lastWhere((m) => m.kind == 'HELLO').session;
    ble.emit(CompanionMessage('CHECK', restored, 1));
    await until(() => runtime.status.value == 'READY_AWAITING_DEVICE_CHOICE');
    expect(ota.offers.single.session, restored);
    expect(ota.maxConcurrent, 1);
  });

  test('mobile data downloads immediately and offers only verified bytes', () async {
    ota.latest = _latest();
    settings['unmetered'] = false;
    ota.downloadGate = Completer<void>();
    await start();
    await until(() => ota.downloads == 1);
    expect(ota.offers, isEmpty);
    ota.downloadGate!.complete();
    await until(() => runtime.status.value == 'READY_AWAITING_DEVICE_CHOICE');
    expect(ota.offers, hasLength(1));
    expect(preferences.getString('companion_ready_$_address'), ota.latest!.asset!.sha256);
    expect(ota.upgrades, 0);
  });

  test('prepared package is reoffered after reconnect within the normal interval', () async {
    ota.latest = _latest();
    await start();
    await until(() => runtime.status.value == 'READY_AWAITING_DEVICE_CHOICE');
    final first = ota.offers.single;
    ble.emit(CompanionMessage('SHOWN', first.session, first.request, [first.fields[0], first.fields[2]]));
    await until(() => preferences.containsKey('companion_seen_$_address'));
    await callback('lost', {'runtimeId': runtimeId});
    runtimeId = 'runtime-2';
    await wake('recovery');
    await until(() => ota.offers.length == 2 && runtime.status.value == 'READY_AWAITING_DEVICE_CHOICE');
    expect(ota.checks, 1, reason: 'Cached offer reattachment consumes no automatic request');
    expect(ota.downloads, 1);
    expect(ota.offers.last.session, isNot(first.session));
    expect(ota.offers.last.fields[4], '0', reason: 'Reconnection does not repeat an already displayed prompt');
    ble.emit(choice(first, 'NOW'));
    await Future<void>.delayed(const Duration(milliseconds: 10));
    expect(ota.upgrades, 0);
  });

  test('later consumes the offer and a replay cannot start the sender', () async {
    ota.latest = _latest();
    await start();
    await until(() => runtime.status.value == 'READY_AWAITING_DEVICE_CHOICE');
    final offer = ota.offers.single;
    ble.emit(choice(offer, 'LATER'));
    await until(() => runtime.status.value == 'DEFERRED');
    ble.emit(choice(offer, 'NOW'));
    await Future<void>.delayed(const Duration(milliseconds: 10));
    expect(ota.upgrades, 0);
  });

  test('matching device consent starts once and verified success clears pending', () async {
    ota.latest = _latest();
    await start();
    await until(() => runtime.status.value == 'READY_AWAITING_DEVICE_CHOICE');
    final offer = ota.offers.single;
    ble.emit(choice(offer, 'NOW'));
    ble.emit(choice(offer, 'NOW'));
    await until(() => runtime.status.value == 'TARGET_IDENTITY_VERIFIED');
    expect(ota.upgrades, 1);
    expect(ota.lastConsent!.packageSha256, offer.fields[2]);
    expect(ota.lastConsent!.linkGeneration, ble.generation);
    expect(ota.lastConsent!.address, _address);
    expect(preferences.containsKey('companion_ready_$_address'), isFalse);
  });

  test('lost native owner cancels its pending query before disconnecting', () async {
    ota.readGate = Completer<void>();
    await start();
    await until(() => ota.reads == 1);
    await callback('lost', {'runtimeId': runtimeId});
    expect(runtime.handles(_address), isFalse);
    expect(ota.releases, 1);
    expect(ota.isUpgrading, isFalse);
    expect(ble.disconnects, 1);
    expect(ota.checks, 0);
    expect(ota.messages, isEmpty);
  });

  test('OTA reboot hands off to new control without idle disconnected success', () async {
    ota.latest = _latest(); ota.rebootOnUpgrade = true;
    await start();
    await until(() => runtime.status.value == 'READY_AWAITING_DEVICE_CHOICE');
    final offer = ota.offers.single;
    ble.emit(choice(offer, 'NOW'));
    await until(() => ble.connects == 2 && runtime.status.value == 'CHECK_WAITING');
    final success = states.singleWhere((s) => s['status'] == 'TARGET_IDENTITY_VERIFIED');
    expect(success['connected'], isFalse);
    expect(success['busy'], isTrue, reason: 'No disconnected idle gap before control recovery');
    expect(states.last['connected'], isTrue);
    expect(runtime.handles(_address), isTrue);
    expect(ota.upgrades, 1);
  });

  test('offline automatic wake does not consume quota or block manual checking', () async {
    settings['networkAvailable'] = false;
    await start();
    await until(() => runtime.status.value == 'NO_NETWORK');
    expect(ota.checks, 0);
    expect(preferences.containsKey('companion_auto_check_budget_v1'), isFalse);
    settings['networkAvailable'] = true;
    await runtime.manualCheck(_address);
    await until(() => runtime.status.value == 'NO_UPDATE');
    expect(ota.checks, 1);
    expect(preferences.containsKey('companion_auto_check_budget_v1'), isFalse);
  });

  test('stopping companion never disconnects a foreign foreground task', () async {
    await start();
    await until(() => runtime.status.value == 'NO_UPDATE');
    ota.foreignBusy = true;
    await callback('lost', {'runtimeId': runtimeId});
    expect(runtime.handles(_address), isFalse);
    expect(ble.disconnects, 0);
    expect(ota.isUpgrading, isTrue);
    ota.foreignBusy = false;
  });

  test('stalled first connect has an overall deadline and cannot publish a late link', () async {
    runtime = CompanionRuntime(platform: CompanionPlatform(channel: channel, supported: true),
      bluetooth: ble, ota: ota, recoveryDeadline: const Duration(milliseconds: 50));
    ble.connectGate = Completer<void>();
    await start(reason: 'recovery');
    await until(() => runtime.status.value == 'CONNECTION_TIMEOUT');
    expect(ble.connects, 1); expect(ble.disconnects, 1); expect(ota.reads, 0);
    ble.connectGate!.complete();
    await Future<void>.delayed(const Duration(milliseconds: 10));
    expect(ble.connected, isFalse); expect(ota.checks, 0);
    ble.connectGate = null;
    await wake('foreground');
    await until(() => runtime.status.value == 'NO_UPDATE');
    expect(ble.connects, 2);
  });

  test('failed INFO retires physical GATT before the next recovery', () async {
    ota.failIdentity = true;
    await start();
    await until(() => runtime.status.value == 'DEVICE_IDENTITY_UNAVAILABLE');
    expect(ble.disconnects, 1); expect(ota.checks, 0);
    ota.failIdentity = false;
    await wake('recovery');
    await until(() => runtime.status.value == 'NO_UPDATE');
    expect(ble.connects, 2); expect(ble.connected, isTrue);
  });

  test('cleanup rejection cannot acknowledge a new wake or start another connection', () async {
    ota.failIdentity = true; ble.cleanupAccepted = false;
    await start();
    await until(() => runtime.status.value == 'RECOVERY_CLEANUP_UNCONFIRMED');
    expect(await callback('wake', {'runtimeId': runtimeId, 'revision': 'revision-1',
      'address': _address, 'reason': 'recovery'}), isFalse);
    expect(ble.connects, 1);
  });
}

FirmwareLatestInfo _latest() => FirmwareLatestInfo.parse({
  'schemaVersion': 2, 'requestId': 'fixture', 'updateAvailable': true,
  'appId': 'trace', 'deviceModel': 'e-track-at32f435', 'channel': 'stable',
  'releaseId': 'release-1', 'versionName': '3.3.28', 'versionCode': 30328,
  'releaseTag': 'fixture', 'targetImageSha256': '62' * 32,
  'targetHardware': 'AT32F435RGT7', 'transport': 'ble', 'minAppVersionCode': 0,
  'asset': {'assetId': 'asset-1', 'kind': 'full', 'fileName': 'fixture-full.etu',
    'sha256': 'ab' * 32, 'sizeBytes': 1024, 'baseVersionCode': 0,
    'baseImageSha256': null, 'downloadUrl': 'https://localhost:9/fixture-full.etu',
    'expiresAt': 2000000000},
});

class _Device extends BluetoothDevice {
  _Device() : super.fromId(_address);
  final states = StreamController<BluetoothConnectionState>.broadcast();
  @override
  Stream<BluetoothConnectionState> get connectionState => states.stream;
}

class _Ble extends BluetoothService {
  final device = _Device();
  final notifications = StreamController<List<int>>.broadcast(sync: true);
  final _readers = <StreamController<List<int>>>{};
  bool notifyEnabled = true;
  int subscriptions = 0;
  bool connected = false, failFirstInitialization = false;
  bool reuse = false, completedSubscription = false;
  bool cleanupAccepted = true;
  Completer<void>? connectGate;
  _Gate? discoveryGate, subscriptionGate;
  final _gates = <_Gate>[];
  int _notifyOwner = 0;
  int connects = 0, disconnects = 0, generation = 0, initializations = 0;
  void emit(CompanionMessage message) {
    if (notifyEnabled) notifications.add(message.encode());
  }
  Future<void> closeReaders() async {
    for (final reader in _readers.toList()) { await reader.close(); }
  }
  Stream<List<int>> _notificationStream() {
    final controller = StreamController<List<int>>(sync: true);
    _readers.add(controller);
    final subscription = notifications.stream.listen(controller.add,
      onError: controller.addError, onDone: controller.close);
    controller.onCancel = () async {
      _readers.remove(controller);
      await subscription.cancel();
    };
    return controller.stream;
  }
  void loseConnection() {
    connected = false;
    generation++;
    device.states.add(BluetoothConnectionState.disconnected);
  }
  void releaseGates() {
    if (connectGate != null && !connectGate!.isCompleted) connectGate!.complete();
    for (final gate in _gates) {
      if (!gate.release.isCompleted) gate.release.complete();
    }
  }
  Future<void> _wait(_Gate? gate) async {
    if (gate == null) return;
    _gates.add(gate);
    gate.entered.complete();
    await gate.release.future;
    gate.finished.complete();
  }
  @override
  bool get reuseOtaCharacteristics => reuse;
  @override
  bool get foregroundScanningAllowed => true;
  @override
  void companionOwnerChanged(String? runtimeId) {}
  @override
  Future<void> initBluetooth() async {
    initializations++;
    if (initializations == 1 && failFirstInitialization) throw StateError('adapter unavailable');
  }
  @override
  Future<bool> connectCompanionDeviceByAddress(String address) async {
    connects++; final before = generation;
    await connectGate?.future;
    if (before != generation) return false;
    connected = true; generation++; return true;
  }
  @override
  Future<bool> cancelCompanionRecovery(String address, String attempt) async {
    if (!cleanupAccepted) return false;
    await disconnectCompanionDeviceByAddress(address); return true;
  }
  @override
  Future<void> disconnectCompanionDeviceByAddress(String address) async {
    disconnects++; connected = false; generation++;
  }
  @override
  int otaLinkGeneration(String address) => generation;
  @override
  BluetoothDevice otaDeviceForObservation(String address) => device;
  @override
  Future<Map<String, String>?> findExactOtaCharacteristicsByAddress(String address,
      {String serviceUuid = 'fff0', String writeCharUuid = 'fff2', String notifyCharUuid = 'fff1',
      OtaLinkStats? stats, int? discoveryTimeoutSeconds}) async {
    final captured = generation, gate = discoveryGate;
    discoveryGate = null;
    await _wait(gate);
    if (reuse && captured != generation) return null;
    return {'serviceId': 'fff0', 'writeCharId': 'fff2', 'notifyCharId': 'fff1', 'writeMode': 'with'};
  }
  @override
  Future<Stream<List<int>>?> subscribeOtaNotifyByAddress(String address,
      String serviceId, String characteristicId, {OtaLinkStats? stats}) async {
    subscriptions++;
    notifyEnabled = true;
    final owner = ++_notifyOwner, gate = subscriptionGate;
    subscriptionGate = null;
    // A stream can already exist when delivery of its Future crosses reconnect.
    final completed = completedSubscription ? _notificationStream() : null;
    await _wait(gate);
    return completed ?? (owner == _notifyOwner ? _notificationStream() : null);
  }
}

class _Gate {
  final entered = Completer<void>();
  final release = Completer<void>();
  final finished = Completer<void>();
}

class _Ota extends OtaService {
  _Ota(this.ble) : super(accountService: TestAccountService());
  final _Ble ble;
  final activity = StreamController<bool>.broadcast(sync: true);
  final messages = <CompanionMessage>[];
  final owners = <String?>[];
  final automaticChecks = <bool>[];
  final info = DeviceOtaInfo.fromInfoPayload(buildInfoPayload(model: DeviceOtaInfo.wireModelETrack,
    hardwareRevision: 3, layoutId: 5, bootVersion: 2, currentVersionCode: 30327,
    imageSha256: List.filled(32, 0x42)));
  FirmwareLatestInfo? latest;
  OtaUpgradeConsent? lastConsent;
  String? verified, owner;
  String? cloudFailure;
  int? cloudRetryAt;
  @override
  String identityAddress = _address;
  bool noUpdate = true, foreignBusy = false, _busy = false, identityAvailable = false;
  bool failIdentity = false, rebootOnUpgrade = false;
  bool answerHello = true;
  int reads = 0, checks = 0, downloads = 0, upgrades = 0, releases = 0, _concurrent = 0, maxConcurrent = 0;
  Completer<void>? readGate, checkGate, downloadGate, helloGate, _done;
  List<CompanionMessage> get offers => messages.where((m) => m.kind == 'OFFER').toList();
  void releaseGates() {
    for (final gate in [readGate, checkGate, downloadGate, helloGate]) {
      if (gate != null && !gate.isCompleted) gate.complete();
    }
  }
  Future<T> operation<T>(String? runtimeId, Future<T> Function() body) async {
    owners.add(runtimeId);
    _concurrent++;
    if (_concurrent > maxConcurrent) maxConcurrent = _concurrent;
    owner = runtimeId; _busy = true; _done = Completer<void>();
    activity.add(true);
    try { return await body(); }
    finally {
      _concurrent--; _busy = false; owner = null;
      _done!.complete();
      activity.add(false);
    }
  }
  @override
  bool get isUpgrading => _busy || foreignBusy;
  @override
  bool get companionTextAllowed => !isUpgrading;
  @override
  Stream<bool> get taskActivity => activity.stream;
  @override
  bool hasCurrentDeviceIdentity(String? address) => identityAvailable && ble.connected && address == identityAddress;
  @override
  DeviceOtaInfo? get deviceInfo => identityAvailable ? info : null;
  @override
  String? get verifiedPackageSha256 => verified;
  @override
  FirmwareLatestInfo? get latestInfo => latest;
  @override
  bool get lastCheckWasNoUpdate => noUpdate;
  @override
  String? get hardwareUid => identityAvailable ? '1234567890abcdef12345678' : null;
  @override
  bool get canResumePreparation => latest != null && verified != null && identityAvailable;
  @override
  Future<DeviceOtaInfo?> readDeviceInfo(String address, {String? companionRuntimeId}) =>
    operation(companionRuntimeId, () async {
      reads++; await readGate?.future; identityAvailable = !failIdentity; identityAddress = address;
      return failIdentity ? null : info;
    });
  @override
  Future<FirmwareLatestInfo?> checkFirmwareUpdate({String? channel, String? companionRuntimeId,
      bool automatic = false, bool refreshPrepared = false, bool legacyMigration = false}) =>
    operation(companionRuntimeId, () async {
      checks++; automaticChecks.add(automatic);
      lastCloudError = cloudFailure; lastCloudRetryAt = cloudRetryAt;
      await checkGate?.future; return latest;
    });
  @override
  Future<bool> downloadFirmware({String? companionRuntimeId}) => operation(companionRuntimeId, () async {
    downloads++; await downloadGate?.future; verified = latest!.asset!.sha256; return true;
  });
  @override
  Future<bool> startOtaUpgrade(String address, {String? companionRuntimeId, OtaUpgradeConsent? consent}) =>
    operation(companionRuntimeId, () async {
      upgrades++; lastConsent = consent;
      if (rebootOnUpgrade) { ble.generation++; identityAvailable = false; verified = null; }
      return true;
    });
  @override
  Future<bool> sendCompanionMessage(String address, CompanionMessage message, {String? companionRuntimeId}) async {
    owners.add(companionRuntimeId);
    messages.add(message);
    if (message.kind == 'HELLO') {
      await helloGate?.future;
      if (answerHello) ble.emit(CompanionMessage('CAPS', message.session, 0, ['1']));
    }
    if (message.kind == 'OFFER') {
      ble.emit(CompanionMessage('SEEN', message.session, message.request,
        [message.fields[0], message.fields[2]]));
    }
    return true;
  }
  @override
  Future<bool> releaseCompanionTask(String runtimeId) async {
    if (foreignBusy || _busy && owner != runtimeId) return false;
    if (_busy) { releases++; releaseGates(); await _done!.future; }
    return true;
  }
  @override
  Future<bool> retireCompanionConnection(String runtime, Future<bool> Function() closeGatt) async {
    if (foreignBusy || (_busy && owner != runtime)) return false;
    final release = releaseCompanionTask(runtime);
    final closed = await closeGatt();
    return await release && closed;
  }
}
