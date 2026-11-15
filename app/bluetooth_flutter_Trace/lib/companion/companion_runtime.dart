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

/// Page-independent gateway. Android owns scheduling/liveness; OtaService owns IO.
class CompanionRuntime extends GetxService {
  CompanionRuntime({CompanionPlatform? platform, BluetoothService? bluetooth, OtaService? ota, this.onShowUi})
      : platform = platform ?? CompanionPlatform(),
        _bluetooth = bluetooth, _otaService = ota;

  final CompanionPlatform platform;
  final void Function()? onShowUi;
  final BluetoothService? _bluetooth;
  final OtaService? _otaService;
  BluetoothService get _ble => _bluetooth ?? Get.find<BluetoothService>();
  OtaService get _ota => _otaService ?? Get.find<OtaService>();
  final status = 'DISABLED'.obs;
  final _decoder = CompanionDecoder();
  StreamSubscription<List<int>>? _text;
  StreamSubscription<BluetoothConnectionState>? _connection;
  StreamSubscription<bool>? _activity;
  Future<void>? _wakeFlight, _checkFlight, _attachFlight, _choiceFlight;
  Map<String, dynamic>? _pendingWake;
  CompanionMessage? _pendingChoice;
  int? _pendingDeviceCheck;
  String? _runtime, _revision, _address, _session;
  int _link = -1, _epoch = 0, _lastDeviceRequest = 0;
  bool _closed = false, _supportsControl = false, _ownsOta = false, _controlDirty = true;
  Completer<bool>? _capabilities;
  Completer<bool>? _offerAcknowledged;
  CompanionOffer? _offer;
  SharedPreferences? _preferences;
  Timer? _telemetryTimer;
  bool _telemetryBusy = false;

  static String _nonce() => List.generate(16, (_) => Random.secure().nextInt(256))
      .map((n) => n.toRadixString(16).padLeft(2, '0')).join();
  static String _identity(DeviceOtaInfo info) => [info.deviceModel, info.hardwareRevision,
    info.layoutId, info.bootVersion, info.protocolVersion, info.currentVersionCode,
    info.currentImageSha256Hex].join('|');

  bool handles(String? address) => _runtime != null && address?.toLowerCase() == _address;
  bool _current(int epoch) => !_closed && _runtime != null && epoch == _epoch;
  bool _sameLink() => _address != null && _link == _ble.otaLinkGeneration(_address!) &&
      _ota.hasCurrentDeviceIdentity(_address);

  @override
  void onInit() { super.onInit(); if (platform.supported) unawaited(_initialize()); }

  Future<void> _initialize() async {
    platform.channel.setMethodCallHandler(_handle);
    try {
      _preferences = await SharedPreferences.getInstance();
      await _ble.initBluetooth();
      if (_closed) return;
      _activity = _ota.taskActivity.listen((busy) {
        if (busy && !_ota.companionTextAllowed) { _decoder.reset(); _controlDirty = true; }
        if (!busy && _wakeFlight == null && _checkFlight == null && _choiceFlight == null) {
          if (_pendingChoice != null || _pendingDeviceCheck != null) { _drainWake(); return; }
          final pending = _pendingWake;
          if (pending != null) { _pendingWake = null; _queueWake(pending); }
          else if (_runtime != null) { unawaited(_attachControl()); }
        }
      });
      await platform.channel.invokeMethod<Object?>('ready');
    } catch (_) { status.value = 'RUNTIME_INITIALIZATION_FAILED'; }
  }

  Future<Object?> _handle(MethodCall call) async {
    if (_closed) return false;
    if (call.method == 'attachUi') { onShowUi?.call(); return true; }
    final args = call.arguments;
    if (args is! Map) return false;
    if (call.method == 'probe') return args['runtimeId'] == _runtime ? _runtime : null;
    if (call.method == 'lost') {
      if (args['runtimeId'] == _runtime) await _stop();
      return true;
    }
    if (call.method != 'wake' || args['runtimeId'] is! String || args['revision'] is! String ||
        args['address'] is! String || !RegExp(r'^[0-9a-fA-F]{2}(:[0-9a-fA-F]{2}){5}$').hasMatch(args['address'] as String)) { return false; }
    final wake = Map<String, dynamic>.from(args);
    if (_runtime != wake['runtimeId']) {
      if (_ota.isUpgrading || _wakeFlight != null || _checkFlight != null || _choiceFlight != null) return false;
      await _stop(disconnect: false);
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
    if (_wakeFlight != null || _checkFlight != null || _choiceFlight != null || _ota.isUpgrading) {
      // Preserve a manual/periodic request while another owner completes.
      if (_pendingWake == null || wake['reason'] == 'manual' || wake['checkPending'] == true) _pendingWake = wake;
      return;
    }
    late final Future<void> flight;
    flight = _wake(wake).catchError((Object _) async { await _state('FAILED', busy: false); }).whenComplete(() {
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
          snapshot['problem'] != null || !await PermissionHelper.checkBluetoothPermissions()) { return; }
      if (!_current(epoch) || _ota.isUpgrading || _wakeFlight != null || _checkFlight != null || _choiceFlight != null) return;
      await _ble.startCompanionScan(runtime);
    } catch (_) { if (_current(epoch)) status.value = 'DATA_SYNC_UNAVAILABLE'; }
    finally { _telemetryBusy = false; }
  }

  Future<void> _wake(Map<String, dynamic> wake) async {
    final epoch = _epoch;
    final address = _address!;
    await _ble.initBluetooth();
    if (!_current(epoch)) return;
    if (!await _state('CONNECTING', busy: true) || !_current(epoch)) return;
    if (!_sameLink()) {
      _invalidateLink();
      if (!await _ble.connectOtaDeviceByAddress(address) || !_current(epoch)) {
        await _state('DEVICE_OFFLINE', busy: false); return;
      }
      final info = await _ota.readDeviceInfo(address);
      if (!_current(epoch)) return;
      if (info == null) { await _state('DEVICE_IDENTITY_UNAVAILABLE', busy: false); return; }
      _link = _ble.otaLinkGeneration(address);
      _session = _nonce();
      _lastDeviceRequest = 0;
      await _connection?.cancel();
      _connection = _ble.otaDeviceForObservation(address).connectionState.listen((state) {
        if (!_current(epoch)) return;
        if (state == BluetoothConnectionState.disconnected || _ble.otaLinkGeneration(address) != _link) {
          _invalidateLink();
          _queueWake({...wake, 'reason': 'recovery'});
        }
      }, onError: (Object _) {
        if (_current(epoch)) { _invalidateLink(); _queueWake({...wake, 'reason': 'recovery'}); }
      });
      if (!await _state('CONNECTED', busy: true) || !_current(epoch)) return;
      await _attachControl();
      final capabilities = Completer<bool>();
      _capabilities = capabilities;
      await _send(CompanionMessage('HELLO', _session!, 0));
      _supportsControl = await capabilities.future.timeout(const Duration(seconds: 3), onTimeout: () => false);
      if (identical(_capabilities, capabilities)) _capabilities = null;
    }
    if (!_current(epoch) || !_sameLink()) return;
    final settings = await platform.snapshot();
    if (!_current(epoch)) return;
    final last = _preferences!.getInt('companion_attempt_$address') ?? 0;
    final interval = Duration(hours: settings['intervalHours'] as int? ?? 12);
    final manual = wake['reason'] == 'manual';
    final due = DateTime.now().millisecondsSinceEpoch - last >= interval.inMilliseconds;
    if (manual || wake['checkPending'] == true || wake['reason'] == 'periodic' || due) {
      await _check(manual ? 'manual' : 'periodic', 0);
    } else {
      await _state(_supportsControl ? 'CONNECTED' : 'DEVICE_CONTROL_UNSUPPORTED', busy: false);
    }
  }

  void _invalidateLink() {
    _offer = null; _supportsControl = false; _session = null; _link = -1;
    _decoder.reset(); _controlDirty = true;
    _pendingChoice = null; _pendingDeviceCheck = null;
    final capabilities = _capabilities;
    if (capabilities != null && !capabilities.isCompleted) capabilities.complete(false);
    final acknowledged = _offerAcknowledged;
    if (acknowledged != null && !acknowledged.isCompleted) acknowledged.complete(false);
  }

  Future<void> _attachControl() {
    final pending = _attachFlight;
    if (pending != null) return pending;
    late final Future<void> flight;
    flight = _attach().catchError((Object _) { _decoder.reset(); }).whenComplete(() {
      if (identical(_attachFlight, flight)) _attachFlight = null;
    });
    _attachFlight = flight;
    return flight;
  }

  Future<void> _attach() async {
    final epoch = _epoch;
    if (!_current(epoch) || !_sameLink() || _ota.isUpgrading) return;
    if (_text != null && !_controlDirty) return;
    final address = _address!;
    final session = _session;
    final old = _text; _text = null;
    await old?.cancel();
    if (!_current(epoch) || !_sameLink() || _ota.isUpgrading) return;
    final chars = await _ble.findExactOtaCharacteristicsByAddress(address);
    if (chars == null || !_current(epoch) || !_sameLink() || _ota.isUpgrading) return;
    final stream = await _ble.subscribeOtaNotifyByAddress(address, chars['serviceId']!, chars['notifyCharId']!);
    if (stream == null) return;
    final subscription = stream.listen((bytes) {
      if (!_current(epoch) || _session != session || !_sameLink()) { _decoder.reset(); return; }
      for (final message in _decoder.add(bytes, idleTextAllowed: _ota.companionTextAllowed)) {
        _message(message);
      }
    }, onError: (Object _) { _decoder.reset(); _controlDirty = true; });
    if (!_current(epoch) || !_sameLink() || _ota.isUpgrading) { await subscription.cancel(); }
    else { _text = subscription; _controlDirty = false; }
  }

  void _message(CompanionMessage message) {
    if (message.session != _session || !_sameLink()) return;
    if (message.kind == 'CAPS') {
      final capabilities = _capabilities;
      if (capabilities != null && !capabilities.isCompleted) capabilities.complete(true);
    } else if (message.kind == 'CHECK' && message.request > _lastDeviceRequest) {
      _lastDeviceRequest = message.request;
      _pendingDeviceCheck = message.request;
      _drainWake();
    } else if (message.kind == 'SEEN' || message.kind == 'SHOWN') {
      final offer = _offer;
      if (offer != null && message.request == offer.request && message.fields[0] == offer.id && message.fields[1] == offer.packageSha) {
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
    if (_runtime == null || !_sameLink() || _ota.isUpgrading ||
        (message.kind != 'HELLO' && !_supportsControl)) { return false; }
    final epoch = _epoch;
    final sent = await _ota.sendCompanionMessage(_address!, message);
    if (_current(epoch)) await _attachControl();
    return sent && _current(epoch) && _sameLink();
  }

  Future<void> _deviceState(String code, int request) async {
    final session = _session;
    if (session != null) await _send(CompanionMessage('STATE', session, request, [code]));
  }

  Future<void> manualCheck(String? address) async {
    if (handles(address)) { await _check('manual', 0); }
    else { await _ota.checkFirmwareUpdate(); } // Explicit foreground/old-device fallback.
  }

  Future<void> _check(String source, int request) {
    final pending = _checkFlight;
    if (pending != null) return pending;
    if (_runtime == null || !_sameLink() || _ota.isUpgrading || _choiceFlight != null) return Future.value();
    late final Future<void> flight;
    flight = _prepare(source, request).catchError((Object _) async {
      await _deviceState('FAILED', request);
      await _state('FAILED', busy: false);
    }).whenComplete(() { if (identical(_checkFlight, flight)) _checkFlight = null; _drainWake(); });
    _checkFlight = flight;
    return flight;
  }

  Future<void> _prepare(String source, int request) async {
    final epoch = _epoch, generation = _link;
    final address = _address!;
    _offer = null;
    await _deviceState('CHECKING', request);
    if (!await _state('CHECKING', busy: true) || !_current(epoch)) return;
    final info = await _ota.readDeviceInfo(address);
    if (!_current(epoch)) return;
    if (info == null) { await _deviceState('INCOMPATIBLE', request); await _state('DEVICE_IDENTITY_UNAVAILABLE', busy: false); return; }
    if (!_sameLink() || _link != generation) return;
    await _preferences!.setInt('companion_attempt_$address', DateTime.now().millisecondsSinceEpoch);
    final latest = await _ota.checkFirmwareUpdate();
    if (!_current(epoch) || !_sameLink()) return;
    if (latest == null) {
      final noUpdate = _ota.lastCheckWasNoUpdate;
      await _attachControl();
      await _deviceState(noUpdate ? 'NO_UPDATE' : 'FAILED', request);
      await _state(noUpdate ? 'NO_UPDATE' : 'CHECK_FAILED', busy: false, checkFinished: noUpdate);
      return;
    }
    final settings = await platform.snapshot();
    if (!_current(epoch) || !_sameLink()) return;
    if (settings['wifiOnly'] != false && settings['unmetered'] != true && _ota.verifiedPackageSha256 == null) {
      await _attachControl(); await _deviceState('WAIT_WIFI', request);
      await _state('WAIT_UNMETERED_NETWORK', busy: false); return;
    }
    await _attachControl();
    if (_ota.verifiedPackageSha256 == null) {
      await _deviceState('DOWNLOADING', request);
      _ownsOta = true;
      bool downloaded;
      try { downloaded = await _ota.downloadFirmware(companionRuntimeId: _runtime); }
      finally { _ownsOta = false; }
      if (!_current(epoch)) return;
      if (!downloaded) {
        await _attachControl(); await _deviceState('FAILED', request);
        await _state('PACKAGE_PREPARATION_FAILED', busy: false); return;
      }
    }
    if (!_sameLink() || _ota.verifiedPackageSha256 == null) return;
    // A URL refresh may have selected another asset. Bind the actual verified one.
    final verified = _ota.latestInfo;
    if (verified == null || verified.asset == null || verified.versionCode == null || verified.targetImageSha256 == null ||
        verified.asset!.sha256 != _ota.verifiedPackageSha256) { return; }
    final offer = CompanionOffer(session: _session!, request: request, id: _nonce(),
      address: address, linkGeneration: _link, identity: _identity(info),
      version: verified.versionCode!, packageSha: verified.asset!.sha256,
      targetSha: verified.targetImageSha256!, expiresAt: DateTime.now().add(const Duration(minutes: 5)));
    _offer = offer;
    final seen = _preferences!.getString('companion_seen_$address') == '${offer.identity}|${offer.packageSha}';
    await _attachControl();
    final acknowledged = Completer<bool>();
    _offerAcknowledged = acknowledged;
    var sent = false;
    for (var attempt = 0; attempt < 3 && _current(epoch) && _sameLink(); attempt++) {
      if (!await _send(CompanionMessage('OFFER', offer.session, request,
          [offer.id, '${offer.version}', offer.packageSha, offer.targetSha, source != 'periodic' || !seen ? '1' : '0']))) { break; }
      sent = await acknowledged.future.timeout(const Duration(seconds: 2), onTimeout: () => false);
      if (sent) break;
    }
    if (identical(_offerAcknowledged, acknowledged)) _offerAcknowledged = null;
    if (!_current(epoch)) return;
    await _state(sent ? 'READY_AWAITING_DEVICE_CHOICE' : 'READY_OPEN_APP', busy: false, checkFinished: sent);
  }

  Future<void> _choose(CompanionMessage message) {
    if (_choiceFlight != null) return _choiceFlight!;
    late final Future<void> flight;
    flight = _acceptChoice(message).catchError((Object _) async { await _state('UPGRADE_FAILED', busy: false); })
      .whenComplete(() { if (identical(_choiceFlight, flight)) _choiceFlight = null; _drainWake(); });
    _choiceFlight = flight;
    return flight;
  }

  Future<void> _acceptChoice(CompanionMessage message) async {
    final offer = _offer;
    if (offer == null || _address == null || !_sameLink() || _checkFlight != null || _ota.isUpgrading ||
        !offer.matches(message, _address!, _link, DateTime.now())) { return; }
    // Consume before any await. A replay can never start another sender.
    offer.consumed = true;
    if (message.fields[3] == 'LATER') {
      await _deviceState('DEFERRED', offer.request);
      await _state('DEFERRED', busy: false); return;
    }
    final epoch = _epoch;
    _ownsOta = true;
    try {
      await _deviceState('CHECKING', offer.request);
      final info = await _ota.readDeviceInfo(offer.address);
      if (!_current(epoch) || !_sameLink() || _link != offer.linkGeneration || info == null || _identity(info) != offer.identity) return;
      final latest = await _ota.checkFirmwareUpdate();
      if (!_current(epoch) || !_sameLink() || _link != offer.linkGeneration || !DateTime.now().isBefore(offer.expiresAt) ||
          latest?.versionCode != offer.version || latest?.asset?.sha256 != offer.packageSha ||
          latest?.targetImageSha256 != offer.targetSha || _ota.verifiedPackageSha256 != offer.packageSha) {
        await _attachControl(); await _deviceState('FAILED', offer.request); return;
      }
      await _attachControl();
      if (!await _send(CompanionMessage('STATE', offer.session, offer.request, ['STARTING']))) return;
      final success = await _ota.startOtaUpgrade(offer.address, companionRuntimeId: _runtime,
        consent: OtaUpgradeConsent(address: offer.address, linkGeneration: offer.linkGeneration,
          baseImageSha256: info.currentImageSha256Hex, versionCode: offer.version,
          packageSha256: offer.packageSha, targetImageSha256: offer.targetSha,
          expiresAt: offer.expiresAt));
      if (_current(epoch)) await _state(success ? 'TARGET_IDENTITY_VERIFIED' : 'UPGRADE_FAILED', busy: false);
    } finally { _ownsOta = false; _drainWake(); }
  }

  Future<bool> _state(String value, {required bool busy, bool checkFinished = false}) async {
    status.value = value;
    final runtime = _runtime, address = _address;
    if (runtime == null || address == null) return false;
    var accepted = false;
    try {
      accepted = await platform.channel.invokeMethod<bool>('state', {'runtimeId': runtime, 'revision': _revision,
        'status': value, 'connected': _sameLink(), 'busy': busy,
        'deviceToken': sha256.convert(utf8.encode(address)).toString(), 'checkFinished': checkFinished}) == true;
    } catch (_) { accepted = false; }
    if (_runtime != runtime) return false;
    if (!accepted) {
      await _stop();
      status.value = 'NATIVE_OWNER_UNAVAILABLE';
    }
    return accepted;
  }

  Future<void> _stop({bool disconnect = true}) async {
    final address = _address;
    _runtime = null; _revision = null; _address = null; _epoch++;
    _telemetryTimer?.cancel(); _telemetryTimer = null;
    _ble.companionOwnerChanged(null);
    _pendingWake = null;
    _invalidateLink();
    await _text?.cancel(); _text = null;
    await _connection?.cancel(); _connection = null;
    if (_ownsOta && _ota.canCancelTask) await _ota.cancelCurrentTask(keepPackage: true);
    if (disconnect && address != null && !_ota.isUpgrading) await _ble.disconnectOtaDeviceByAddress(address);
    status.value = 'STOPPED';
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
