import 'dart:async';
import 'package:flutter/material.dart';
import 'package:get/get.dart';
import 'package:permission_handler/permission_handler.dart';
import '../companion/companion_platform.dart';
import '../companion/companion_runtime.dart';
import '../controllers/ble_controller.dart';
import '../services/bluetooth_service.dart';
import '../utils/permission_helper.dart';
import 'trace_ui.dart';
import 'companion_diagnostics_page.dart';

class CompanionSetupPage extends StatefulWidget {
  const CompanionSetupPage({super.key, this.platform, this.requiredBluetoothPermissions});
  final CompanionPlatform? platform;
  final Future<List<Permission>> Function()? requiredBluetoothPermissions;

  @override
  State<CompanionSetupPage> createState() => _CompanionSetupPageState();
}

class _CompanionSetupPageState extends State<CompanionSetupPage> with WidgetsBindingObserver {
  late final CompanionPlatform _platform;
  Map<String, dynamic> _snapshot = {};
  Map<Permission, PermissionStatus> _permissions = {};
  PermissionStatus _notification = PermissionStatus.denied;
  bool _busy = false;
  int _readEpoch = 0;
  String? _error, _selected;
  Worker? _statusWorker;
  Future<List<Permission>> _requiredBluetoothPermissions() =>
      (widget.requiredBluetoothPermissions ?? PermissionHelper.requiredBluetoothPermissions)();

  @override
  void initState() {
    super.initState();
    _platform = widget.platform ?? CompanionPlatform();
    WidgetsBinding.instance.addObserver(this);
    if (Get.isRegistered<CompanionRuntime>()) {
      _statusWorker = debounce(Get.find<CompanionRuntime>().status, (_) => unawaited(_refresh()),
        time: const Duration(milliseconds: 200));
    }
    unawaited(_refresh());
  }

  @override
  void dispose() {
    _readEpoch++;
    _statusWorker?.dispose();
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) unawaited(_refresh());
  }

  Future<void> _refresh() async {
    final epoch = ++_readEpoch;
    try {
      final snapshot = await _platform.snapshot();
      final permissions = <Permission, PermissionStatus>{};
      if (_platform.supported) {
        for (final permission in await _requiredBluetoothPermissions()) {
          permissions[permission] = await permission.status;
        }
      }
      final notification = _platform.supported ? await Permission.notification.status : PermissionStatus.denied;
      if (!mounted || epoch != _readEpoch) return;
      setState(() {
        _snapshot = snapshot;
        _permissions = permissions;
        _notification = notification;
        _selected ??= snapshot['address'] as String?;
      });
    } catch (_) {
      if (mounted && epoch == _readEpoch) setState(() { _error = '\u65e0\u6cd5\u8bfb\u53d6\u6743\u9650\u72b6\u6001\uff0c\u8bf7\u7a0d\u540e\u91cd\u8bd5'; });
    }
  }

  Future<void> _run(Future<void> Function() action) async {
    if (_busy) return;
    setState(() { _busy = true; _error = null; });
    try { await action(); }
    catch (error) { if (mounted) setState(() { _error = error.toString(); }); }
    finally {
      await _refresh();
      if (mounted) setState(() { _busy = false; });
    }
  }

  Future<void> _settings(String kind) async {
    final opened = await _platform.openSettings(kind);
    if (!opened && mounted) { setState(() {
      _error = '\u8be5\u7cfb\u7edf\u6ca1\u6709\u53ef\u7528\u7684\u4e13\u7528\u5165\u53e3\u3002\u8bf7\u5728\u5e94\u7528\u4fe1\u606f\u3001\u7535\u6c60\u6216\u81ea\u542f\u52a8\u8bbe\u7f6e\u4e2d\u67e5\u627e E-Track\uff1b\u6253\u5f00\u8bbe\u7f6e\u4e0d\u4ee3\u8868\u5df2\u6388\u6743\u3002';
    }); }
  }

  Future<void> _configure({bool? enabled, int? hours, bool? wifi}) async {
    await _platform.configure(enabled: enabled ?? _snapshot['enabled'] == true,
      intervalHours: hours ?? (_snapshot['intervalHours'] as int? ?? 12),
      wifiOnly: wifi ?? _snapshot['wifiOnly'] != false);
  }

  Widget _section(String number, String title, String detail, List<Widget> children) => Padding(
    padding: const EdgeInsets.symmetric(vertical: 16),
    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Text('$number / $title', style: const TextStyle(color: TraceColors.cyan, fontSize: 20, fontWeight: FontWeight.w600)),
      const SizedBox(height: 10),
      Text(detail, style: const TextStyle(color: TraceColors.muted, height: 1.6)),
      const SizedBox(height: 12),
      ...children,
      const Divider(color: TraceColors.ocean, height: 32),
    ]),
  );

  Widget _button(String label, Future<void> Function() action) => OutlinedButton(
    onPressed: _busy ? null : () => _run(action),
    style: OutlinedButton.styleFrom(foregroundColor: TraceColors.cyan), child: Text(label),
  );

  @override
  Widget build(BuildContext context) {
    final granted = _permissions.isNotEmpty && _permissions.values.every((s) => s.isGranted);
    final permanent = _permissions.values.any((s) => s.isPermanentlyDenied || s.isRestricted);
    return TraceBackGesture(child: Scaffold(
      backgroundColor: TraceColors.ink,
      appBar: AppBar(title: const Text('\u540e\u53f0\u8fd0\u884c\u4e0e\u6743\u9650'), backgroundColor: TraceColors.ink,
        leading: IconButton(key: const ValueKey('detail-back'), tooltip: '\u8fd4\u56de',
          onPressed: () => TraceBackGesture.back(context), icon: const Icon(Icons.arrow_back)),
        foregroundColor: TraceColors.text,
        actions: [IconButton(tooltip: '\u91cd\u65b0\u68c0\u67e5', onPressed: _busy ? null : _refresh, icon: const Icon(Icons.refresh))]),
      body: TracePageScaffold(child: SafeArea(child: ListView(padding: const EdgeInsets.all(24), children: [
        const Text('\u8ba9\u624b\u673a\u6210\u4e3a\u8bbe\u5907\u7684\u8054\u7f51\u4f19\u4f34', style: TextStyle(color: TraceColors.text, fontSize: 26, fontWeight: FontWeight.w600)),
        const SizedBox(height: 12),
        const Text('\u81ea\u52a8\u68c0\u67e5\u548c\u51c6\u5907\u56fa\u4ef6\uff0c\u4e0d\u81ea\u52a8\u5237\u673a\u3002\u8bbe\u5907\u4e0a\u786e\u8ba4\u201c\u7acb\u5373\u66f4\u65b0\u201d\u540e\u624d\u5f00\u59cb\u5347\u7ea7\u3002\u53ef\u4ee5\u8df3\u8fc7\uff0c\u7a0d\u540e\u5728\u201c\u6211\u7684 / \u5e2e\u52a9\u4e0e\u53cd\u9988\u201d\u4e2d\u7ee7\u7eed\u3002',
          style: TextStyle(color: TraceColors.muted, height: 1.6)),
        if (!_platform.supported) const Padding(padding: EdgeInsets.symmetric(vertical: 24),
          child: Text('\u6b64\u540e\u53f0\u4f34\u4fa3\u529f\u80fd\u4ec5\u9002\u7528\u4e8e Android\u3002\u5176\u4ed6\u5e73\u53f0\u7ee7\u7eed\u4f7f\u7528\u524d\u53f0\u8fde\u63a5\u4e0e\u5347\u7ea7\u3002', style: TextStyle(color: TraceColors.amber))),
        if (_platform.supported) ...[
          _section('01', '\u84dd\u7259\u8fde\u63a5', 'Android 12 \u53ca\u4ee5\u4e0a\u53ea\u7533\u8bf7\u9644\u8fd1\u8bbe\u5907\u6743\u9650\uff1b\u65e7\u7cfb\u7edf\u626b\u63cf\u9700\u8981\u4f7f\u7528\u65f6\u5b9a\u4f4d\u3002\u9a91\u884c\u5b9a\u4f4d\u7531\u5bf9\u5e94\u529f\u80fd\u5355\u72ec\u7533\u8bf7\uff0c\u4e0d\u8981\u6c42\u540e\u53f0\u5b9a\u4f4d\u3002', [
            Text(granted ? '\u5fc5\u8981\u84dd\u7259\u6743\u9650\u5df2\u6388\u4e88' : permanent ? '\u5df2\u6c38\u4e45\u62d2\u7edd\uff0c\u8bf7\u524d\u5f80\u7cfb\u7edf\u8bbe\u7f6e' : '\u672a\u6388\u6743\u6216\u5df2\u64a4\u9500\uff0c\u53ef\u7ee7\u7eed\u4f7f\u7528\u65e0\u5173\u529f\u80fd', style: const TextStyle(color: TraceColors.text)),
            _button(permanent ? '\u6253\u5f00\u5e94\u7528\u6743\u9650\u8bbe\u7f6e' : '\u6388\u4e88\u84dd\u7259\u6743\u9650', () async {
              if (permanent) { await _settings('permissions'); }
              else { await (await _requiredBluetoothPermissions()).request(); }
            }),
            _button('\u68c0\u67e5\u84dd\u7259\u5f00\u5173', () => _settings('bluetooth')),
          ]),
          _section('02', '\u901a\u77e5\u4e0e\u8fdb\u5ea6', '\u7528\u4e8e\u5c55\u793a\u540e\u53f0\u8fde\u63a5\u548c\u771f\u5b9e\u5347\u7ea7\u8fdb\u5ea6\u3002\u62d2\u7edd\u901a\u77e5\u65f6\u4e0d\u627f\u8bfa\u540e\u53f0 OTA\uff0c\u524d\u53f0\u529f\u80fd\u4ecd\u53ef\u4f7f\u7528\u3002\u901a\u77e5\u6e20\u9053\u5173\u95ed\u4e5f\u9700\u8981\u5728\u7cfb\u7edf\u8bbe\u7f6e\u4e2d\u6062\u590d\u3002', [
            Text(_notification.isGranted ? '\u901a\u77e5\u6743\u9650\u5df2\u6388\u4e88\uff0c\u8bf7\u540c\u65f6\u68c0\u67e5\u6e20\u9053' : '\u901a\u77e5\u672a\u6388\u6743', style: const TextStyle(color: TraceColors.text)),
            _button(_notification.isGranted || _notification.isPermanentlyDenied ? '\u6253\u5f00\u901a\u77e5\u8bbe\u7f6e' : '\u6388\u4e88\u901a\u77e5\u6743\u9650', () async {
              if (_notification.isGranted || _notification.isPermanentlyDenied) { await _settings('notifications'); }
              else { await Permission.notification.request(); }
            }),
          ]),
          _section('03', '\u5173\u8054 E-Track \u4e3b\u63a7', '\u901a\u8fc7\u7cfb\u7edf\u4f34\u4fa3\u8bbe\u5907\u5bf9\u8bdd\u6846\u786e\u8ba4\u3002\u5173\u8054\u4e0d\u7b49\u4e8e\u8fde\u63a5\u6210\u529f\uff1b\u540e\u53f0\u4f1a\u91cd\u65b0\u8bfb\u53d6\u8bbe\u5907\u771f\u5b9e\u8eab\u4efd\uff0c\u672a\u77e5\u5916\u8bbe\u4e0d\u4f1a\u88ab\u5f53\u4f5c\u53ef\u5347\u7ea7\u8bbe\u5907\u3002\u66f4\u6362\u8bbe\u5907\u524d\u8bf7\u5148\u5173\u95ed\u540e\u53f0\u6a21\u5f0f\u3002', [
            if (Get.isRegistered<BluetoothService>()) Obx(() {
              final bluetooth = Get.find<BluetoothService>();
              final choices = <String, String>{};
              for (final device in [...bluetooth.discoveredDevices, ...bluetooth.connectedDevices]) {
                choices[device.remoteId.str.toLowerCase()] = device.platformName.isEmpty ? device.remoteId.str : device.platformName;
              }
              if (_selected != null) choices.putIfAbsent(_selected!, () => _selected!);
              return DropdownButton<String>(isExpanded: true, value: _selected, dropdownColor: TraceColors.deep,
                hint: const Text('\u5148\u626b\u63cf\uff0c\u518d\u9009\u62e9\u8bbe\u5907', style: TextStyle(color: TraceColors.muted)),
                style: const TextStyle(color: TraceColors.text),
                items: choices.entries.map((e) => DropdownMenuItem(value: e.key,
                  child: Text('${e.value} / ${e.key}', overflow: TextOverflow.ellipsis))).toList(),
                onChanged: _busy || _snapshot['enabled'] == true ? null : (value) => setState(() { _selected = value; }));
            }),
            Wrap(spacing: 12, children: [
              _button('\u626b\u63cf\u8bbe\u5907', () async {
                if (Get.isRegistered<BleController>()) await Get.find<BleController>().startScan();
              }),
              _button('\u901a\u8fc7\u7cfb\u7edf\u5173\u8054', () async {
                if (_selected == null) throw StateError('\u8bf7\u5148\u9009\u62e9\u8bbe\u5907');
                await _platform.associate(_selected!);
              }),
            ]),
            Text(_snapshot['associated'] == true ? '\u7cfb\u7edf\u5173\u8054\u5df2\u786e\u8ba4' : '\u5c1a\u672a\u786e\u8ba4\u7cfb\u7edf\u5173\u8054', style: const TextStyle(color: TraceColors.text)),
          ]),
          _section('04', '\u6309\u9700\u542f\u7528\u540e\u53f0\u4f34\u4fa3', '\u7cfb\u7edf\u8c03\u5ea6\u9ed8\u8ba4\u7ea6\u6bcf 12 \u5c0f\u65f6\u68c0\u67e5\u56fa\u4ef6\uff0c\u4e0d\u662f\u7cbe\u786e\u95f9\u949f\u3002\u8bbe\u5907\u4e0a\u7684\u201c\u68c0\u67e5\u66f4\u65b0\u201d\u53ef\u7acb\u5373\u53d1\u8d77\u67e5\u8be2\u3002\u624b\u673a\u5f3a\u884c\u505c\u6b62\u5e94\u7528\u3001\u64a4\u6743\u6216\u5173\u95ed\u84dd\u7259\u540e\uff0c\u9700\u8981\u6062\u590d\u6761\u4ef6\u624d\u80fd\u7ee7\u7eed\u3002', [
            SwitchListTile(contentPadding: EdgeInsets.zero,
              title: const Text('\u540e\u53f0\u8fde\u63a5\u4e0e\u56fa\u4ef6\u68c0\u67e5', style: TextStyle(color: TraceColors.text)),
              value: _snapshot['enabled'] == true,
              onChanged: _busy ? null : (value) => _run(() => _configure(enabled: value))),
            Text(_snapshot['serviceRunning'] == true ? '\u540e\u53f0\u6267\u884c\u6240\u6709\u8005\u5df2\u54cd\u5e94' : '\u540e\u53f0\u6267\u884c\u5c1a\u672a\u786e\u8ba4\uff0c\u6216\u8bbe\u5907\u6682\u4e0d\u53ef\u8fbe', style: const TextStyle(color: TraceColors.muted)),
            if (_snapshot['problem'] != null) Text('\u5f53\u524d\u9650\u5236\uff1a${_snapshot['problem']}', style: const TextStyle(color: TraceColors.amber)),
            if (_snapshot['lastResult'] != null) Text('\u6700\u8fd1\u72b6\u6001\uff1a${_snapshot['lastResult']}', style: const TextStyle(color: TraceColors.muted)),
            _button('\u67e5\u770b\u8fde\u63a5\u8bca\u65ad', () async { await Get.to<void>(() => const CompanionDiagnosticsPage()); }),
            DropdownButton<int>(value: _snapshot['intervalHours'] as int? ?? 12, dropdownColor: TraceColors.deep,
              style: const TextStyle(color: TraceColors.text),
              items: [6, 12, 24].map((n) => DropdownMenuItem(value: n, child: Text('\u7ea6\u6bcf $n \u5c0f\u65f6\u68c0\u67e5'))).toList(),
              onChanged: _busy ? null : (n) { if (n != null) _run(() => _configure(hours: n)); }),
            SwitchListTile(contentPadding: EdgeInsets.zero,
              title: const Text('\u4ec5\u5728\u975e\u8ba1\u8d39\u7f51\u7edc\u81ea\u52a8\u4e0b\u8f7d', style: TextStyle(color: TraceColors.text)),
              value: _snapshot['wifiOnly'] != false,
              onChanged: _busy ? null : (value) => _run(() => _configure(wifi: value))),
            _button('\u73b0\u5728\u68c0\u67e5\u4e3b\u63a7\u56fa\u4ef6', _platform.check),
          ]),
          _section('05', '\u7535\u6c60\u4e0e\u5382\u5546\u81ea\u542f\u52a8', '\u4ec5\u5728\u540e\u53f0\u8fde\u63a5\u53d7\u7cfb\u7edf\u9650\u5236\u65f6\u6309\u9700\u8c03\u6574\u3002\u65e0\u9700\u4e00\u5f8b\u5173\u95ed\u6240\u6709\u7701\u7535\u529f\u80fd\u3002\u5382\u5546\u81ea\u542f\u52a8\u5f00\u5173\u65e0\u6cd5\u53ef\u9760\u8bfb\u53d6\uff0c\u59cb\u7ec8\u9700\u8981\u4f60\u6838\u5bf9\uff1b\u8df3\u8f6c\u8fc7\u9875\u9762\u4e0d\u8868\u793a\u5df2\u6388\u6743\u3002', [
            Text(_snapshot['batteryUnrestricted'] == true ? '\u7cfb\u7edf\u7535\u6c60\u4f18\u5316\u5df2\u8c41\u514d' : '\u4ecd\u53d7\u7cfb\u7edf\u7535\u6c60\u7b56\u7565\u7ba1\u7406', style: const TextStyle(color: TraceColors.text)),
            const Text('\u5382\u5546\u81ea\u542f\u52a8\uff1a\u5f85\u4eba\u5de5\u6838\u5bf9 / \u5f85\u771f\u673a\u9a8c\u8bc1', style: TextStyle(color: TraceColors.amber)),
            Wrap(spacing: 12, children: [
              _button('\u7535\u6c60\u8bbe\u7f6e', () => _settings('battery')),
              _button('\u5382\u5546\u81ea\u542f\u52a8\u8bbe\u7f6e', () => _settings('autostart')),
            ]),
            if (_snapshot['presenceSupported'] == false) const Text('\u6b64\u7cfb\u7edf\u4e0d\u652f\u6301\u4f34\u4fa3\u5b58\u5728\u611f\u77e5\uff0c\u5c06\u6309\u7cfb\u7edf\u5141\u8bb8\u7684\u5468\u671f\u5c1d\u8bd5\u6062\u590d\u8fde\u63a5\u3002', style: TextStyle(color: TraceColors.muted)),
          ]),
        ],
        if (_error != null) Text(_error!, style: const TextStyle(color: TraceColors.amber)),
        if (_busy) const LinearProgressIndicator(),
        TextButton(onPressed: () => Navigator.of(context).maybePop(), child: const Text('\u8fd4\u56de / \u6682\u65f6\u8df3\u8fc7')),
      ]))),
    ));
  }
}
