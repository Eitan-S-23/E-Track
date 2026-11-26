import 'dart:async';
import 'dart:convert';
import 'dart:math';
import 'package:crypto/crypto.dart';
import 'package:flutter/services.dart';
import 'package:flutter_blue_plus/flutter_blue_plus.dart' show BluetoothConnectionState;
import 'package:get/get.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../ota/ota_device_info.dart';
import '../ota/ota_upgrade_consent.dart';
import '../services/bluetooth_service.dart';
import '../services/ota_service.dart';
import '../controllers/monitor_controller.dart';
import '../utils/permission_helper.dart';
import 'companion_platform.dart';
import 'companion_protocol.dart';
import 'companion_recovery.dart';
import '../services/account_service.dart';

typedef _ControlBinding = ({String address, String session, int generation, int epoch});

/// Page-independent gateway. Android owns scheduling/liveness; OtaService owns IO.
class CompanionRuntime extends GetxService {
  CompanionRuntime({CompanionPlatform? platform, BluetoothService? bluetooth, OtaService? ota,
      Future<bool> Function()? checkBluetoothPermissions, this.onShowUi,
      this.recoveryDeadline = const Duration(seconds: 25),
      this.controlHealthInterval = const Duration(minutes: 1),
      this.controlResponseTimeout = const Duration(seconds: 3),
      int Function()? controlClock})
      : platform = platform ?? CompanionPlatform(),
        _checkBluetoothPermissions = checkBluetoothPermissions ?? PermissionHelper.checkBluetoothPermissions,
        _controlMillis = controlClock,
        _bluetooth = bluetooth, _otaService = ota;

  final CompanionPlatform platform;
  final Duration recoveryDeadline;
  final Duration controlHealthInterval, controlResponseTimeout;
  final int Function()? _controlMillis;
  final _controlClock = Stopwatch()..start();
  int? _controlCheckedAt;
  int get _controlNow => _controlMillis?.call() ?? _controlClock.elapsedMilliseconds;
  final void Function()? onShowUi;
  final BluetoothService? _bluetooth;
  final OtaService? _otaService;
  final Future<bool> Function() _checkBluetoothPermissions;
  BluetoothService get _ble => _bluetooth ?? Get.find<BluetoothService>();
  OtaService get _ota => _otaService ?? Get.find<OtaService>();
  final status = 'DISABLED'.obs;
  final _decoder = CompanionDecoder();
  StreamSubscription<List<int>>? _text;
  StreamSubscription<BluetoothConnectionState>? _connection;
  StreamSubscription<bool>? _activity;
  Future<void>? _wakeFlight, _checkFlight, _attachFlight, _choiceFlight, _stopFlight;
  _ControlBinding? _attachBinding;
  Map<String, dynamic>? _pendingWake;
  CompanionMessage? _pendingChoice;
  int? _pendingDeviceCheck;
  String? _runtime, _revision, _address, _session;
  int _link = -1, _epoch = 0, _lastDeviceRequest = 0;
  int _stateSequence = 0;
  bool _closed = false, _supportsControl = false, _controlDirty = true;
  Completer<bool>? _capabilities;
  Completer<bool>? _offerAcknowledged;
  CompanionOffer? _offer;
  SharedPreferences? _preferences;
  Timer? _telemetryTimer;
  bool _telemetryBusy = false;
  CompanionRecoveryAttempt? _recovery;
  Future<bool>? _recoveryCleanup;
  bool _recoveryBlocked = false;

  static String _nonce() => List.generate(16, (_) => Random.secure().nextInt(256))
      .map((n) => n.toRadixString(16).padLeft(2, '0')).join();
  static String _identity(DeviceOtaInfo info) => [info.deviceModel, info.hardwareRevision,
    info.layoutId, info.bootVersion, info.protocolVersion, info.currentVersionCode,
    info.currentImageSha256Hex].join('|');

  bool handles(String? address) => _runtime != null && address?.toLowerCase() == _address;
  bool _current(int epoch) => !_closed && _runtime != null && epoch == _epoch;
  bool _sameLink() => _address != null && _link == _ble.otaLinkGeneration(_address!) &&
      _ota.hasCurrentDeviceIdentity(_address);
  _ControlBinding? _captureBinding() => _session == null || !_sameLink() ? null :
      (address: _address!, session: _session!, generation: _link, epoch: _epoch);
  bool _ownsBinding(_ControlBinding binding) => _current(binding.epoch) &&
      _address == binding.address && _session == binding.session && _link == binding.generation;
  bool _bindingCurrent(_ControlBinding binding) => _ownsBinding(binding) && _sameLink();

  @override
  void onInit() { super.onInit(); if (platform.supported) unawaited(_initialize()); }

  Future<void> _initialize() async {
    platform.channel.setMethodCallHandler(_handle);
    _activity = _ota.taskActivity.listen((busy) {
      if (busy && !_ota.companionTextAllowed) { _decoder.reset(); _controlDirty = true; }
      if (!busy && _wakeFlight == null && _checkFlight == null && _choiceFlight == null) {
        if (_pendingChoice != null || _pendingDeviceCheck != null) { _drainWake(); return; }
        final pending = _pendingWake;
        if (pending != null) { _pendingWake = null; _queueWake(pending); }
        else if (_runtime != null) {
          if (!_sameLink()) {
            // A failed foreground INFO retires the shared identity even when
            // GATT stays connected. Re-establish control, not the long HTTP timer.
            _queueWake({'runtimeId': _runtime, 'revision': _revision,
              'address': _address, 'reason': 'recovery'});
          } else {
            unawaited(_attachControl());
          }
        }
      }
    });
    try {
      _preferences = await SharedPreferences.getInstance();
      await _ble.initBluetooth().timeout(const Duration(seconds: 8));
    } catch (_) { status.value = 'RUNTIME_INITIALIZATION_FAILED'; }
    if (_closed) return;
    // A denied/unavailable adapter must not strand the engine's next wake.
    try {
      await platform.channel.invokeMethod<Object?>('ready');
    } catch (_) { status.value = 'RUNTIME_INITIALIZATION_FAILED'; }
  }

  Future<Object?> _handle(MethodCall call) async {
    if (_closed) return false;
    if (call.method == 'attachUi') { onShowUi?.call(); return true; }
    final args = call.arguments;
    if (args is! Map) return false;
    if (call.method == 'probe') {
      if (args['runtimeId'] != _runtime) return null;
      // The native liveness reply must not wait for BLE or its five-second watchdog.
      if (_controlNeedsCheck) _queueControlCheck('heartbeat');
      return _runtime;
    }
    if (call.method == 'lost') {
      if (args['runtimeId'] == _runtime) await _stop();
      return true;
    }
    if (call.method != 'wake' || args['runtimeId'] is! String || args['revision'] is! String ||
        args['address'] is! String || !RegExp(r'^[0-9a-fA-F]{2}(:[0-9a-fA-F]{2}){5}$').hasMatch(args['address'] as String)) { return false; }
    final wake = Map<String, dynamic>.from(args);
    if (_recoveryBlocked) return false;
    if (_runtime != wake['runtimeId']) {
      if (_ota.isUpgrading || _wakeFlight != null || _checkFlight != null || _choiceFlight != null || _stopFlight != null || _recoveryCleanup != null) return false;
      await _stop(disconnect: false);
      if (_closed || _runtime != null) return false;
      _runtime = wake['runtimeId'] as String;
      _revision = wake['revision'] as String;
      _address = (wake['address'] as String).toLowerCase();
      _epoch++;
      _ble.companionOwnerChanged(_runtime);
      _telemetryTimer = Timer.periodic(const Duration(minutes: 1), (_) => unawaited(_collectTelemetry()));
    }
    if (_revision != wake['revision'] || _address != (wake['address'] as String).toLowerCase()) return false;
    _queueWake(wake);
    return true;
  }

  void _queueWake(Map<String, dynamic> wake) {
    if (_recoveryBlocked) return;
    if (_wakeFlight != null || _checkFlight != null || _choiceFlight != null || _ota.isUpgrading) {
      // Preserve a manual/periodic request while another owner completes.
      if (_pendingWake == null || wake['reason'] == 'manual' || wake['checkPending'] == true) _pendingWake = wake;
      return;
    }
    late final Future<void> flight;
    final epoch = _epoch;
    flight = _wake(wake).catchError((Object _) async {
      if (_current(epoch)) await _state('FAILED', busy: false);
    }).whenComplete(() {
      if (identical(_wakeFlight, flight)) _wakeFlight = null;
      _drainWake();
    });
    _wakeFlight = flight;
  }

  void _drainWake() {
    if (_closed || _runtime == null || _wakeFlight != null || _checkFlight != null || _choiceFlight != null || _ota.isUpgrading) return;
    final choice = _pendingChoice;
    _pendingChoice = null;
    if (choice != null) { unawaited(_choose(choice)); return; }
    final check = _pendingDeviceCheck;
    _pendingDeviceCheck = null;
    if (check != null) { unawaited(_check('device', check)); return; }
    final next = _pendingWake;
    _pendingWake = null;
    if (next != null) { _queueWake(next); }
    else { unawaited(_collectTelemetry()); }
  }

  Future<void> _collectTelemetry() async {
    if (_telemetryBusy || _closed || _runtime == null || _ble.foregroundScanningAllowed ||
        _ota.isUpgrading || _wakeFlight != null || _checkFlight != null || _choiceFlight != null ||
        !Get.isRegistered<MonitorController>() || Get.find<MonitorController>().monitoringDevices.isEmpty) { return; }
    final runtime = _runtime!, epoch = _epoch;
    _telemetryBusy = true;
    try {
      final snapshot = await platform.snapshot();
      if (!_current(epoch) || snapshot['runtimeId'] != runtime || snapshot['revision'] != _revision ||
          snapshot['serviceRunning'] != true || snapshot['sensorBackgroundSupported'] != true ||
          snapshot['problem'] != null || !await _checkBluetoothPermissions()) { return; }
      if (!_current(epoch) || _ota.isUpgrading || _wakeFlight != null || _checkFlight != null || _choiceFlight != null) return;
      await _ble.startCompanionScan(runtime);
    } catch (_) { if (_current(epoch)) status.value = 'DATA_SYNC_UNAVAILABLE'; }
    finally { _telemetryBusy = false; }
  }

  Future<void> _wake(Map<String, dynamic> wake) async {
    final epoch = _epoch;
    final address = _address!;
    final controlOnly = wake['reason'] == 'control';
    // A failed control probe hands retries to native backoff, never its own queue.
    if (controlOnly && _session == null) return;
    _preferences ??= await SharedPreferences.getInstance();
    if (!_current(epoch)) return;
    final reconnecting = !_sameLink();
    if (reconnecting && !await _recoverConnection(wake)) return;
    if (!reconnecting && _sameLink()) {
      await _journal('LINK_REUSED');
      if ((_controlNeedsCheck || wake['reason'] == 'foreground' || wake['reason'] == 'manual') &&
          !await _refreshControl(wake)) {
        return;
      }
    }
    if (!_current(epoch) || !_sameLink()) return;
    if (controlOnly) {
      if (reconnecting) await _state(_supportsControl ? 'CONNECTED' : 'DEVICE_CONTROL_UNSUPPORTED', busy: false);
      return;
    }
    final binding = _captureBinding();
    if (binding == null) return;
    final settings = await platform.snapshot();
    if (!_bindingCurrent(binding)) return;
    final last = _preferences!.getInt('companion_attempt_$address') ?? 0;
    final interval = Duration(hours: settings['intervalHours'] as int? ?? 12);
    final manual = wake['reason'] == 'manual';
    final now = DateTime.now().millisecondsSinceEpoch;
    final retryAt = _preferences!.getInt('account_auto_retry_${_ota.accounts.accountId}') ?? 0;
    final due = now - last >= interval.inMilliseconds || retryAt > 0 && retryAt <= now;
    await _journal('CHECK_SCHEDULE', {'lastCheckAt': last,
      'nextCheckAt': last + interval.inMilliseconds, 'source': wake['reason']});
    final pendingPackage = reconnecting && _preferences!.containsKey('companion_ready_$address');
    if (manual || reconnecting || wake['checkPending'] == true || wake['reason'] == 'periodic' || due || pendingPackage ||
        (wake['reason'] == 'network' && _ota.canResumePreparation)) {
      await _check(manual ? 'manual' : reconnecting ? 'reconnect' : 'periodic', 0);
    } else {
      await _scheduleCheck(binding, retryAt > now ? retryAt : last + interval.inMilliseconds);
      await _journal('CHECK_NOT_EXECUTED', {'reason': 'not_due'});
      await _state(retryAt > now ? 'CHECK_WAITING' : _supportsControl ? 'CONNECTED' : 'DEVICE_CONTROL_UNSUPPORTED', busy: false);
    }
  }

  Future<bool> _recoverConnection(Map<String, dynamic> wake) async {
    final epoch = _epoch, address = _address!, runtime = _runtime!;
    if (!_ota.beginCompanionConnection(runtime)) return false;
    var releaseAdmission = false;
    final attempt = CompanionRecoveryAttempt(_nonce(), recoveryDeadline);
    _recovery = attempt;
    bool current() => attempt.current && _current(epoch) && identical(_recovery, attempt);
    Future<void> stage(String value) async {
      if (!current()) throw CompanionRecoveryExpired(attempt.stage);
      attempt.stage = value;
      if (!await attempt.wait(_state(value, busy: true)) || !current()) throw CompanionRecoveryExpired(value);
    }
    try {
      await _diagnostic('RECOVERY_STARTED', attempt, trigger: wake['reason'] as String?);
      _invalidateLink();
      await stage('INITIALIZING');
      await attempt.wait(_ble.initBluetooth());
      if (!current()) throw CompanionRecoveryExpired(attempt.stage);
      if (!await attempt.wait(_ble.beginCompanionRecovery(address, runtime, attempt.id))) throw StateError('LINK_OWNER_BUSY');
      await stage('CONNECTING');
      if (!await attempt.wait(_ble.connectCompanionDeviceByAddress(address))) throw StateError('DEVICE_OFFLINE');
      if (!current()) throw CompanionRecoveryExpired(attempt.stage);
      final generation = _ble.otaLinkGeneration(address);
      await _diagnostic('GATT_CONNECTED', attempt);
      await stage('DISCOVERING');
      final info = await attempt.wait(_ota.readCompanionDeviceInfo(address, runtime, stage));
      if (!current()) throw CompanionRecoveryExpired(attempt.stage);
      if (generation != _ble.otaLinkGeneration(address)) {
        throw StateError('LINK_GENERATION_CHANGED');
      }
      if (info == null) throw StateError('DEVICE_IDENTITY_UNAVAILABLE');
      await _diagnostic('IDENTITY_VERIFIED', attempt);
      _link = generation;
      _session = _nonce();
      _lastDeviceRequest = 0;
      final binding = _captureBinding();
      if (binding == null) throw StateError('LINK_GENERATION_CHANGED');
      await attempt.wait(_connection?.cancel() ?? Future<void>.value());
      if (!current() || !_bindingCurrent(binding)) throw StateError('LINK_GENERATION_CHANGED');
      _connection = _ble.otaDeviceForObservation(address).connectionState.listen((state) {
        if (!_ownsBinding(binding)) return;
        if (state == BluetoothConnectionState.disconnected || _ble.otaLinkGeneration(address) != binding.generation) {
          _invalidateLink();
          _queueWake({...wake, 'reason': 'recovery'});
        }
      }, onError: (Object _) {
        if (_ownsBinding(binding)) { _invalidateLink(); _queueWake({...wake, 'reason': 'recovery'}); }
      });
      await stage('NEGOTIATING_CONTROL');
      final supported = await _handshake(binding, attempt);
      if (!current() || !_bindingCurrent(binding)) throw StateError('LINK_GENERATION_CHANGED');
      _supportsControl = supported;
      _controlCheckedAt = _controlNow;
      if (supported) await _diagnostic('CONTROL_READY', attempt);
      if (!await attempt.wait(_ble.finishCompanionRecovery(address, attempt.id))) throw StateError('GATT_RETIREMENT_UNCONFIRMED');
      attempt.finish();
      if (identical(_recovery, attempt)) _recovery = null;
      releaseAdmission = true;
      await _diagnostic('RECOVERY_CONNECTED', attempt);
      return await _state('CONNECTED', busy: true);
    } catch (error) {
      final failedStage = attempt.stage;
      attempt.cancel();
      _invalidateLink();
      if (!_current(epoch)) return false; // The stop path owns physical retirement.
      await _diagnostic('RECOVERY_FAILED', attempt, error: error);
      final code = error is CompanionRecoveryExpired || error is TimeoutException ? 'CONNECTION_TIMEOUT'
          : error is StateError && error.message == 'DEVICE_IDENTITY_UNAVAILABLE' ? 'DEVICE_IDENTITY_UNAVAILABLE'
          : error is StateError && error.message == 'DEVICE_OFFLINE' ? 'DEVICE_OFFLINE' : 'CONNECTION_FAILED';
      await _state('RECOVERY_CLEANUP', busy: true, stage: failedStage);
      var cleaned = false;
      try { cleaned = await _cleanupRecovery(address, runtime, attempt).timeout(const Duration(seconds: 4)); }
      catch (_) { cleaned = false; }
      _recoveryBlocked = !cleaned;
      releaseAdmission = cleaned;
      if (_current(epoch)) await _state(cleaned ? code : 'RECOVERY_CLEANUP_UNCONFIRMED', busy: false, stage: failedStage);
      return false;
    } finally {
      attempt.finish();
      if (identical(_recovery, attempt)) _recovery = null;
      if (releaseAdmission) _ota.endCompanionConnection(runtime);
    }
  }

  Future<bool> _cleanupRecovery(String address, String runtime, CompanionRecoveryAttempt attempt) {
    final active = _recoveryCleanup;
    if (active != null) return active;
    late final Future<bool> cleanup;
    cleanup = _ota.retireCompanionConnection(runtime, () => _ble.cancelCompanionRecovery(address, attempt.id)).then((ok) {
      if (ok) { _recoveryBlocked = false; _ota.endCompanionConnection(runtime); }
      return ok;
    })
      .whenComplete(() { if (identical(_recoveryCleanup, cleanup)) _recoveryCleanup = null; });
    _recoveryCleanup = cleanup;
    return cleanup;
  }

  Future<void> _diagnostic(String value, CompanionRecoveryAttempt attempt, {Object? error, String? trigger}) async {
    final runtime = _runtime;
    if (runtime == null) return;
    final code = error is PlatformException ? error.details is int ? error.details : error.code
        : error is StateError ? error.message : null;
    try {
      await platform.channel.invokeMethod<Object?>('diagnostic', {'runtimeId': runtime, 'revision': _revision,
        'status': value, 'stage': attempt.stage, 'elapsedMs': attempt.elapsedMs, 'trigger': trigger,
        'recoveryId': attempt.id, 'deviceKey': _address == null ? null : sha256.convert(utf8.encode(_address!.toLowerCase())).toString(),
        'errorType': error?.runtimeType.toString(), 'errorCode': code}).timeout(const Duration(seconds: 1));
    } catch (_) { /* Local diagnostics never block recovery. */ }
  }

  Future<void> _journal(String event, [Map<String, Object?> details = const {}]) async {
    try {
      await platform.channel.invokeMethod<Object?>('journal', {'status': event,
        'deviceKey': _address == null ? null : sha256.convert(utf8.encode(_address!.toLowerCase())).toString(),
        ...details}).timeout(const Duration(seconds: 1));
    } catch (_) { /* Observation failure must not change radio ownership. */ }
  }

  Future<void> _scheduleCheck(_ControlBinding binding, int at) async {
    if (!_bindingCurrent(binding)) return;
    try {
      final accepted = await platform.channel.invokeMethod<bool>('scheduleCheck', {
        'runtimeId': _runtime, 'revision': _revision, 'nextCheckAt': at,
        'deviceToken': sha256.convert(utf8.encode(binding.address)).toString(),
      }).timeout(const Duration(seconds: 1));
      if (accepted != true && _bindingCurrent(binding)) {
        await _journal('CHECK_WAKE_SCHEDULE_FAILED', {'nextCheckAt': at, 'reason': 'native_schedule_rejected'});
      }
    } catch (_) {
      if (_bindingCurrent(binding)) await _journal('CHECK_WAKE_SCHEDULE_FAILED', {'nextCheckAt': at, 'reason': 'native_schedule_unavailable'});
    }
  }

  Future<void> _deferCheck(_ControlBinding binding, String source, int request, String reason, int at,
      {String clockSource = 'local_spacing'}) async {
    if (!_bindingCurrent(binding)) return;
    await _preferences!.setInt('account_auto_retry_${_ota.accounts.accountId}', at);
    await _scheduleCheck(binding, at);
    if (!_bindingCurrent(binding)) return;
    await _journal('CHECK_NOT_EXECUTED', {'source': source, 'reason': reason, 'nextCheckAt': at, 'clockSource': clockSource});
    await _deviceState('BUSY', request, binding: binding);
    if (_bindingCurrent(binding)) await _state('CHECK_WAITING', busy: false, checkFinished: true);
  }

  Future<void> _scheduleOrdinaryCheck(_ControlBinding binding, String reason) async {
    if (!_bindingCurrent(binding)) return;
    final settings = await platform.snapshot();
    if (!_bindingCurrent(binding)) return;
    final at = DateTime.now().millisecondsSinceEpoch + Duration(hours: settings['intervalHours'] as int? ?? 12).inMilliseconds;
    await _scheduleCheck(binding, at);
    if (_bindingCurrent(binding)) {
      await _journal('CHECK_SCHEDULE', {
        'lastCheckAt': _preferences!.getInt('companion_attempt_${binding.address}') ?? 0,
        'nextCheckAt': at, 'reason': reason,
      });
    }
  }

  void _invalidateLink() {
    _offer = null; _supportsControl = false; _session = null; _link = -1;
    _controlCheckedAt = null;
    _decoder.reset(); _controlDirty = true;
    _pendingChoice = null; _pendingDeviceCheck = null;
    final capabilities = _capabilities;
    if (capabilities != null && !capabilities.isCompleted) capabilities.complete(false);
    final acknowledged = _offerAcknowledged;
    if (acknowledged != null && !acknowledged.isCompleted) acknowledged.complete(false);
  }

  bool get _controlNeedsCheck {
    if (_runtime == null || _session == null || _closed) return false;
    final checked = _controlCheckedAt;
    return !_sameLink() || _text == null || _controlDirty || checked == null ||
        _controlNow - checked >= controlHealthInterval.inMilliseconds;
  }

  void _queueControlCheck(String source) {
    if (_closed || _runtime == null || _session == null || _recoveryBlocked) return;
    _queueWake({'runtimeId': _runtime, 'revision': _revision, 'address': _address,
      'reason': 'control', 'controlSource': source});
  }

  Future<bool> _handshake(_ControlBinding binding, CompanionRecoveryAttempt attempt) async {
    await attempt.wait(_attachControl());
    if (!_bindingCurrent(binding) || _text == null || _controlDirty) throw StateError('CONTROL_SUBSCRIPTION_FAILED');
    final capabilities = Completer<bool>();
    _capabilities = capabilities;
    try {
      if (!await attempt.wait(_send(CompanionMessage('HELLO', binding.session, 0)))) {
        throw StateError('CONTROL_WRITE_FAILED');
      }
      return await attempt.wait(capabilities.future.timeout(controlResponseTimeout, onTimeout: () => false));
    } finally {
      if (identical(_capabilities, capabilities)) _capabilities = null;
    }
  }

  Future<bool> _refreshControl(Map<String, dynamic> wake) async {
    final binding = _captureBinding(), runtime = _runtime;
    if (binding == null || runtime == null || !_ota.beginCompanionConnection(runtime)) return false;
    final previousStatus = status.value;
    final previouslySupported = _supportsControl;
    final attempt = CompanionRecoveryAttempt(_nonce(), recoveryDeadline);
    attempt.stage = 'NEGOTIATING_CONTROL';
    _recovery = attempt;
    var releaseAdmission = false;
    try {
      await _diagnostic('CONTROL_CHECK_STARTED', attempt, trigger: wake['controlSource'] as String? ?? wake['reason'] as String?);
      if (!await attempt.wait(_state('NEGOTIATING_CONTROL', busy: true))) return false;
      if (!await attempt.wait(_ble.beginCompanionRecovery(binding.address, runtime, attempt.id))) throw StateError('LINK_OWNER_BUSY');
      // Same-session HELLO preserves the MCU offer, request sequence and explicit consent.
      _controlDirty = true;
      final supported = await _handshake(binding, attempt);
      if (!supported && previouslySupported) throw StateError('CONTROL_RESPONSE_TIMEOUT');
      if (!_bindingCurrent(binding)) throw StateError('LINK_GENERATION_CHANGED');
      if (!await attempt.wait(_ble.finishCompanionRecovery(binding.address, attempt.id))) throw StateError('GATT_RETIREMENT_UNCONFIRMED');
      _supportsControl = supported;
      _controlCheckedAt = _controlNow;
      attempt.finish();
      if (identical(_recovery, attempt)) _recovery = null;
      releaseAdmission = true;
      await _diagnostic(supported ? 'CONTROL_CHECK_READY' : 'CONTROL_CHECK_UNSUPPORTED', attempt);
      // Older firmware can still use the explicit App update path without a reconnect loop.
      if (!supported) return await _state('DEVICE_CONTROL_UNSUPPORTED', busy: false);
      return await _state(previousStatus == 'DEVICE_CONTROL_UNSUPPORTED' ? 'CONNECTED' : previousStatus,
        busy: false, controlOnly: true);
    } catch (error) {
      attempt.cancel();
      _invalidateLink();
      if (!_current(binding.epoch)) return false;
      if (_pendingWake?['reason'] == 'control' || _pendingWake?['reason'] == 'recovery') _pendingWake = null;
      await _diagnostic('CONTROL_CHECK_FAILED', attempt, error: error);
      await _state('RECOVERY_CLEANUP', busy: true, stage: attempt.stage);
      var cleaned = false;
      try { cleaned = await _cleanupRecovery(binding.address, runtime, attempt).timeout(const Duration(seconds: 4)); }
      catch (_) { cleaned = false; }
      _recoveryBlocked = !cleaned;
      releaseAdmission = cleaned;
      if (_current(binding.epoch)) await _state(cleaned ? 'CONNECTION_FAILED' : 'RECOVERY_CLEANUP_UNCONFIRMED', busy: false, stage: attempt.stage);
      return false;
    } finally {
      attempt.finish();
      if (identical(_recovery, attempt)) _recovery = null;
      if (releaseAdmission) _ota.endCompanionConnection(runtime);
    }
  }

  Future<void> _attachControl() {
    final binding = _captureBinding();
    if (binding == null || _ota.isUpgrading) return Future.value();
    final pending = _attachFlight;
    if (pending != null && _attachBinding == binding) return pending;
    late final Future<void> flight;
    flight = _attach(binding).catchError((Object _) {
      if (_bindingCurrent(binding)) { _decoder.reset(); _controlDirty = true; }
    }).whenComplete(() {
      if (identical(_attachFlight, flight)) { _attachFlight = null; _attachBinding = null; }
      if (!_bindingCurrent(binding) && _captureBinding() != null && _controlDirty && !_ota.isUpgrading) {
        unawaited(_attachControl());
      }
    });
    _attachBinding = binding;
    _attachFlight = flight;
    return flight;
  }

  Future<void> _attach(_ControlBinding binding) async {
    if (!_bindingCurrent(binding) || _ota.isUpgrading) return;
    if (_text != null && !_controlDirty) return;
    final old = _text;
    final chars = await _ble.findExactOtaCharacteristicsByAddress(binding.address);
    if (chars == null || !_bindingCurrent(binding) || _ota.isUpgrading) return;
    final stream = await _ble.subscribeOtaNotifyByAddress(binding.address, chars['serviceId']!, chars['notifyCharId']!);
    if (stream == null) return;
    late final StreamSubscription<List<int>> subscription;
    subscription = stream.listen((bytes) {
      if (!_bindingCurrent(binding) || _text == null || !identical(_text, subscription)) return;
      for (final message in _decoder.add(bytes, idleTextAllowed: _ota.companionTextAllowed)) {
        _message(message);
      }
    }, onError: (Object _) {
      if (_bindingCurrent(binding) && identical(_text, subscription)) _controlLost('notify_error');
    }, onDone: () {
      if (_bindingCurrent(binding) && identical(_text, subscription)) {
        _text = null;
        _controlLost('notify_closed');
      }
    });
    if (!_bindingCurrent(binding) || _ota.isUpgrading) { await subscription.cancel(); }
    else {
      _text = subscription; _controlDirty = false;
      // Acquire the replacement CCCD owner first; retiring the old reader must not disable it.
      await old?.cancel();
    }
  }

  void _controlLost(String reason) {
    _decoder.reset(); _controlDirty = true; _controlCheckedAt = null;
    unawaited(_journal('CONTROL_CHANNEL_LOST', {'reason': reason}));
    final capabilities = _capabilities;
    if (capabilities != null && !capabilities.isCompleted) capabilities.complete(false);
    _queueControlCheck(reason);
  }

  void _message(CompanionMessage message) {
    if (message.session != _session || !_sameLink()) return;
    if (message.kind == 'CAPS') {
      final capabilities = _capabilities;
      if (capabilities != null && !capabilities.isCompleted) {
        _controlCheckedAt = _controlNow;
        capabilities.complete(true);
      }
    } else if (message.kind == 'UID') {
      _ota.acceptHardwareUid(_address!, message.fields[0]);
    } else if (message.kind == 'CHECK' && message.request > _lastDeviceRequest) {
      _lastDeviceRequest = message.request;
      _pendingDeviceCheck = message.request;
      _drainWake();
    } else if (message.kind == 'SEEN' || message.kind == 'SHOWN') {
      final offer = _offer;
      if (offer != null && message.request == offer.request && message.fields[0] == offer.id && message.fields[1] == offer.packageSha) {
        unawaited(_journal(message.kind == 'SEEN' ? 'MCU_OFFER_RECEIVED' : 'MCU_OFFER_SHOWN',
          {'taskId': offer.id, 'reason': message.kind == 'SHOWN' ? 'presentation_origin_unknown' : 'received_not_presented'}));
        if (message.kind == 'SEEN') {
          final acknowledged = _offerAcknowledged;
          if (acknowledged != null && !acknowledged.isCompleted) acknowledged.complete(true);
        } else {
          unawaited(_preferences!.setString('companion_seen_${offer.address}', '${offer.identity}|${offer.packageSha}'));
        }
      }
    } else if (message.kind == 'CHOICE') {
      _pendingChoice ??= message;
      _drainWake();
    }
  }

  Future<bool> _send(CompanionMessage message) async {
    final binding = _captureBinding();
    if (_runtime == null || binding == null || message.session != binding.session || _ota.isUpgrading ||
        (message.kind != 'HELLO' && !_supportsControl)) { return false; }
    final sent = await _ota.sendCompanionMessage(binding.address, message, companionRuntimeId: _runtime!);
    if (_bindingCurrent(binding)) await _attachControl();
    return sent && _bindingCurrent(binding);
  }

  Future<void> _deviceState(String code, int request, {_ControlBinding? binding}) async {
    final current = binding ?? _captureBinding();
    if (current != null && _bindingCurrent(current)) {
      await _send(CompanionMessage('STATE', current.session, request, [code]));
    }
  }

  Future<void> manualCheck(String? address) async {
    if (handles(address)) {
      _queueWake({'runtimeId': _runtime, 'revision': _revision, 'address': _address,
        'reason': 'manual', 'checkPending': true});
      await (_wakeFlight ?? _checkFlight ?? _choiceFlight);
    }
    else { await _ota.checkFirmwareUpdate(); } // Explicit foreground/old-device fallback.
  }

  Future<void> _check(String source, int request) {
    final pending = _checkFlight;
    if (pending != null) return pending;
    if (_runtime == null || !_sameLink() || _ota.isUpgrading || _choiceFlight != null) return Future.value();
    late final Future<void> flight;
    final binding = _captureBinding();
    if (binding == null) return Future.value();
    flight = _prepare(source, request, binding).catchError((Object _) async {
      if (!_bindingCurrent(binding)) return;
      await _deviceState('FAILED', request, binding: binding);
      if (_bindingCurrent(binding)) await _state('FAILED', busy: false);
    }).whenComplete(() { if (identical(_checkFlight, flight)) _checkFlight = null; _drainWake(); });
    _checkFlight = flight;
    return flight;
  }

  Future<void> _prepare(String source, int request, _ControlBinding binding) async {
    final address = binding.address, runtime = _runtime!;
    final automatic = source != 'manual' && source != 'device';
    try { await _ota.accounts.requireLogin(); }
    on AccountException catch (e) {
      await _journal('CHECK_NOT_EXECUTED', {'source': source, 'reason': e.code});
      await _deviceState('PHONE_REQUIRED', request, binding: binding);
      if (_bindingCurrent(binding)) await _state('LOGIN_REQUIRED', busy: false, checkFinished: true);
      return;
    }
    if (_ota.hardwareUid == null) {
      await _ota.readHardwareUid(companionRuntimeId: runtime);
      if (!_bindingCurrent(binding)) return;
    }
    if (automatic) {
      final settings = await platform.snapshot();
      if (!_bindingCurrent(binding)) return;
      if (settings['networkAvailable'] != false && !_ota.canResumePreparation) {
        var retained = false;
        try { retained = await _ota.restorePreparation(companionRuntimeId: runtime); }
        catch (_) { await _journal('PREPARATION_RESTORE_FAILED', {'source': source}); }
        if (!_bindingCurrent(binding)) return;
        if (retained && !_ota.canResumePreparation) {
          await _state('PACKAGE_PREPARATION_FAILED', busy: false);
          return;
        }
      }
      // Only a request-saving cooldown is local. Daily counts live exclusively on the server.
      final lastAutomatic = _preferences!.getInt('account_auto_last_${_ota.accounts.accountId}') ?? 0;
      final elapsed = DateTime.now().millisecondsSinceEpoch - lastAutomatic;
      final now = DateTime.now().millisecondsSinceEpoch;
      final retryAt = _preferences!.getInt('account_auto_retry_${_ota.accounts.accountId}') ?? 0;
      final localDeadline = lastAutomatic > 0 && elapsed >= 0 ? lastAutomatic + const Duration(hours: 1).inMilliseconds : 0;
      final deadline = max(retryAt, localDeadline);
      final reason = settings['networkAvailable'] == false ? 'network_unavailable' :
          deadline > now && !_ota.canResumePreparation ? 'minimum_interval' : null;
      if (reason != null) {
        if (reason == 'minimum_interval') {
          await _deferCheck(binding, source, request, reason, deadline,
            clockSource: retryAt >= localDeadline ? 'persisted_deadline' : 'local_spacing');
          return;
        }
        await _scheduleOrdinaryCheck(binding, reason);
        if (!_bindingCurrent(binding)) return;
        await _journal('CHECK_NOT_EXECUTED', {'source': source, 'reason': reason});
        // Reoffer verified bytes without spending network quota.
        if (_bindingCurrent(binding)) await _state(reason == 'network_unavailable' ? 'NO_NETWORK' : 'CONNECTED', busy: false, checkFinished: true);
        if (_bindingCurrent(binding) && _preferences!.containsKey('companion_ready_$address') &&
            _ota.deviceInfo != null && _ota.verifiedPackageSha256 != null) {
          await _presentPrepared(source, request, binding, _ota.deviceInfo!);
        }
        return;
      }
    }
    _offer = null;
    await _deviceState('CHECKING', request, binding: binding);
    if (!_bindingCurrent(binding) || !await _state('CHECKING', busy: true) || !_bindingCurrent(binding)) return;
    final info = await _ota.readDeviceInfo(address, companionRuntimeId: runtime);
    if (!_ownsBinding(binding)) return;
    if (info == null) {
      await _deviceState('INCOMPATIBLE', request, binding: binding);
      if (_ownsBinding(binding)) await _state('DEVICE_IDENTITY_UNAVAILABLE', busy: false);
      return;
    }
    if (!_bindingCurrent(binding)) return;
    final resume = automatic && _ota.canResumePreparation;
    final latest = resume ? _ota.latestInfo : await _ota.checkFirmwareUpdate(companionRuntimeId: runtime, automatic: automatic);
    if (!_bindingCurrent(binding)) return;
    if (!resume && (latest != null || _ota.lastCheckWasNoUpdate)) {
      final now = DateTime.now().millisecondsSinceEpoch;
      await _preferences!.setInt('companion_attempt_$address', now);
      if (automatic) {
        await _preferences!.setInt('account_auto_last_${_ota.accounts.accountId}', now);
      }
      await _preferences!.remove('account_auto_retry_${_ota.accounts.accountId}');
      final settings = await platform.snapshot();
      if (!_bindingCurrent(binding)) return;
      await _scheduleCheck(binding, now + Duration(hours: settings['intervalHours'] as int? ?? 12).inMilliseconds);
      await _journal('CHECK_EXECUTED', {'executedAt': now, 'source': source});
    } else if (resume) {
      await _scheduleOrdinaryCheck(binding, 'prepared_cache');
      if (!_bindingCurrent(binding)) return;
    } else if (_ota.lastCloudError != null) {
      await _journal('CHECK_NOT_EXECUTED', {'source': source, 'reason': _ota.lastCloudError});
    }
    if (latest == null) {
      if (automatic && _ota.lastCloudError == 'CHECK_TOO_SOON') {
        final now = DateTime.now().millisecondsSinceEpoch;
        final returned = _ota.lastCloudRetryAt;
        final retryAt = returned != null && returned > now && returned <= now + const Duration(hours: 24).inMilliseconds
            ? returned : now + const Duration(hours: 1).inMilliseconds;
        if (_bindingCurrent(binding)) {
          await _deferCheck(binding, source, request, 'CHECK_TOO_SOON', retryAt,
            clockSource: returned == retryAt ? 'server_deadline' : 'fallback_hour');
        }
        return;
      }
      final noUpdate = _ota.lastCheckWasNoUpdate;
      if (noUpdate) await _preferences!.remove('companion_ready_$address');
      if (!_bindingCurrent(binding)) return;
      await _attachControl();
      await _deviceState(noUpdate ? 'NO_UPDATE' : 'FAILED', request, binding: binding);
      if (_bindingCurrent(binding)) await _state(noUpdate ? 'NO_UPDATE' : 'CHECK_FAILED', busy: false, checkFinished: noUpdate);
      return;
    }
    await _attachControl();
    if (!_bindingCurrent(binding)) return;
    if (_ota.verifiedPackageSha256 == null) {
      await _deviceState('DOWNLOADING', request, binding: binding);
      if (!_bindingCurrent(binding)) return;
      final downloaded = await _ota.downloadFirmware(companionRuntimeId: runtime);
      if (!_bindingCurrent(binding)) return;
      if (!downloaded) {
        await _attachControl(); await _deviceState('FAILED', request, binding: binding);
        if (_bindingCurrent(binding)) await _state('PACKAGE_PREPARATION_FAILED', busy: false);
        return;
      }
    }
    if (!_bindingCurrent(binding) || _ota.verifiedPackageSha256 == null) return;
    await _presentPrepared(source, request, binding, info);
  }

  Future<void> _presentPrepared(String source, int request, _ControlBinding binding, DeviceOtaInfo info) async {
    if (!_bindingCurrent(binding)) return;
    final address = binding.address;
    final automatic = source != 'manual' && source != 'device';
    // A URL refresh may have selected another asset. Bind the actual verified one.
    final verified = _ota.latestInfo;
    if (verified == null || verified.asset == null || verified.versionCode == null || verified.targetImageSha256 == null ||
        verified.asset!.sha256 != _ota.verifiedPackageSha256) { return; }
    await _preferences!.setString('companion_ready_$address', verified.asset!.sha256);
    if (!_bindingCurrent(binding)) return;
    final offer = CompanionOffer(session: binding.session, request: request, id: _nonce(),
      address: address, linkGeneration: binding.generation, identity: _identity(info),
      version: verified.versionCode!, packageSha: verified.asset!.sha256,
      targetSha: verified.targetImageSha256!, expiresAt: DateTime.now().add(const Duration(minutes: 5)));
    _offer = offer;
    final seen = _preferences!.getString('companion_seen_$address') == '${offer.identity}|${offer.packageSha}';
    if (automatic && seen) await _journal('POPUP_NOT_REQUESTED', {'reason': 'same_package_seen'});
    await _attachControl();
    if (!_bindingCurrent(binding)) return;
    final acknowledged = Completer<bool>();
    _offerAcknowledged = acknowledged;
    var sent = false;
    for (var attempt = 0; attempt < 3 && _bindingCurrent(binding); attempt++) {
      if (!await _send(CompanionMessage('OFFER', offer.session, request,
          [offer.id, '${offer.version}', offer.packageSha, offer.targetSha, !automatic || !seen ? '1' : '0']))) { break; }
      sent = await acknowledged.future.timeout(const Duration(seconds: 2), onTimeout: () => false);
      if (sent) break;
    }
    if (identical(_offerAcknowledged, acknowledged)) _offerAcknowledged = null;
    if (!_bindingCurrent(binding)) return;
    await _journal(sent ? 'OFFER_ACKNOWLEDGED' : 'OFFER_NOT_ACKNOWLEDGED',
      {'reason': sent ? 'awaiting_device_choice' : 'control_ack_missing', 'taskId': offer.id});
    await _state(sent ? 'READY_AWAITING_DEVICE_CHOICE' : 'READY_OPEN_APP', busy: false, checkFinished: sent || !_supportsControl);
  }

  Future<void> _choose(CompanionMessage message) {
    if (_choiceFlight != null) return _choiceFlight!;
    late final Future<void> flight;
    final binding = _captureBinding();
    if (binding == null || message.session != binding.session) return Future.value();
    flight = _acceptChoice(message).catchError((Object _) async {
      if (_bindingCurrent(binding)) await _state('UPGRADE_FAILED', busy: false);
    })
      .whenComplete(() { if (identical(_choiceFlight, flight)) _choiceFlight = null; _drainWake(); });
    _choiceFlight = flight;
    return flight;
  }

  Future<void> _acceptChoice(CompanionMessage message) async {
    final offer = _offer;
    final binding = _captureBinding();
    if (binding == null || offer == null || _address == null || !_sameLink() || _checkFlight != null || _ota.isUpgrading ||
        !offer.matches(message, _address!, _link, DateTime.now())) { return; }
    // Consume before any await. A replay can never start another sender.
    offer.consumed = true;
    if (message.fields[3] == 'LATER') {
      await _deviceState('DEFERRED', offer.request, binding: binding);
      if (_bindingCurrent(binding)) await _state('DEFERRED', busy: false);
      return;
    }
    final epoch = _epoch, runtime = _runtime!;
    try {
      await _deviceState('CHECKING', offer.request, binding: binding);
      if (!_bindingCurrent(binding)) return;
      final info = await _ota.readDeviceInfo(offer.address, companionRuntimeId: runtime);
      if (!_bindingCurrent(binding) || info == null || _identity(info) != offer.identity) return;
      final latest = await _ota.checkFirmwareUpdate(companionRuntimeId: runtime, refreshPrepared: true);
      if (!_bindingCurrent(binding)) return;
      if (!DateTime.now().isBefore(offer.expiresAt) ||
          latest?.versionCode != offer.version || latest?.asset?.sha256 != offer.packageSha ||
          latest?.targetImageSha256 != offer.targetSha || _ota.verifiedPackageSha256 != offer.packageSha) {
        await _attachControl(); await _deviceState('FAILED', offer.request, binding: binding); return;
      }
      await _attachControl();
      if (!await _send(CompanionMessage('STATE', offer.session, offer.request, ['STARTING']))) return;
      if (!_bindingCurrent(binding)) return;
      final success = await _ota.startOtaUpgrade(offer.address, companionRuntimeId: runtime,
        consent: OtaUpgradeConsent(address: offer.address, linkGeneration: offer.linkGeneration,
          baseImageSha256: info.currentImageSha256Hex, versionCode: offer.version,
          packageSha256: offer.packageSha, targetImageSha256: offer.targetSha,
          expiresAt: offer.expiresAt));
      if (_current(epoch)) {
        if (success) await _preferences!.remove('companion_ready_${offer.address}');
        // Reboot retires the control generation even after OTA verifies its target.
        // Keep execution ownership until ordinary control is re-established.
        final needsRecovery = !_sameLink();
        await _state(success ? 'TARGET_IDENTITY_VERIFIED' : 'UPGRADE_FAILED', busy: needsRecovery);
        if (_current(epoch) && needsRecovery) {
          _pendingWake ??= {'runtimeId': runtime, 'revision': _revision,
            'address': _address, 'reason': 'recovery'};
        }
      }
    } finally { _drainWake(); }
  }

  Future<bool> _state(String value, {required bool busy, bool checkFinished = false,
      bool controlOnly = false, String? stage}) async {
    final runtime = _runtime, address = _address;
    if (runtime == null || address == null) return false;
    final sequence = ++_stateSequence;
    status.value = value;
    var accepted = false;
    try {
      accepted = await platform.channel.invokeMethod<bool>('state', {'runtimeId': runtime, 'revision': _revision, 'stateSequence': sequence,
        'status': value, 'connected': _sameLink(), 'busy': busy,
        'recoveryBusy': _recovery?.current == true, 'recoveryId': _recovery?.id,
        'stage': stage ?? _recovery?.stage, 'elapsedMs': _recovery?.elapsedMs,
        'deviceKey': sha256.convert(utf8.encode(address.toLowerCase())).toString(),
        'deviceToken': sha256.convert(utf8.encode(address)).toString(),
        'checkFinished': checkFinished, 'controlOnly': controlOnly}) == true;
    } catch (_) { accepted = false; }
    if (_runtime != runtime) return false;
    if (sequence != _stateSequence) return false;
    if (!accepted) {
      await _stop();
      status.value = 'NATIVE_OWNER_UNAVAILABLE';
    }
    return accepted;
  }

  Future<void> _stop({bool disconnect = true}) {
    final pending = _stopFlight;
    if (pending != null) return pending;
    late final Future<void> flight;
    flight = _stopNow(disconnect: disconnect).whenComplete(() {
      if (identical(_stopFlight, flight)) _stopFlight = null;
    });
    _stopFlight = flight;
    return flight;
  }

  Future<void> _stopNow({required bool disconnect}) async {
    final address = _address, runtime = _runtime;
    final recovery = _recovery;
    _runtime = null; _revision = null; _address = null; _epoch++;
    recovery?.cancel();
    final epoch = _epoch;
    _telemetryTimer?.cancel(); _telemetryTimer = null;
    _ble.companionOwnerChanged(null);
    _pendingWake = null;
    _invalidateLink();
    final text = _text; _text = null;
    final connection = _connection; _connection = null;
    await text?.cancel();
    await connection?.cancel();
    if (disconnect && address != null && runtime != null) {
      status.value = 'STOPPING_TASK';
      try {
        if (recovery != null) {
          final released = await _cleanupRecovery(address, runtime, recovery).timeout(const Duration(seconds: 4));
          if (!released) { status.value = 'STOP_CLEANUP_UNCONFIRMED'; return; }
          if (epoch == _epoch) status.value = 'STOPPED';
          return;
        }
        final released = await _ota.releaseCompanionTask(runtime).timeout(const Duration(minutes: 5));
        if (epoch != _epoch || _runtime != null) return;
        if (released && !_ota.isUpgrading) await _ble.disconnectCompanionDeviceByAddress(address);
      } catch (_) {
        if (epoch == _epoch) status.value = 'STOP_CLEANUP_UNCONFIRMED';
        return;
      }
    }
    if (epoch == _epoch) status.value = 'STOPPED';
  }

  @override
  void onClose() {
    _closed = true;
    unawaited(_activity?.cancel());
    if (platform.supported) platform.channel.setMethodCallHandler(null);
    unawaited(_stop());
    super.onClose();
  }
}
