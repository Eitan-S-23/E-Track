import 'dart:async';

import 'package:flutter/material.dart';
import 'package:get/get.dart';
import '../services/account_service.dart';
import '../services/bluetooth_service.dart';
import '../services/ota_service.dart';
import 'trace_ui.dart';

/// Existing E-Track surfaces; new-api-style forms and server-owned registration switches.
class AccountPage extends StatefulWidget {
  const AccountPage({super.key});
  @override
  State<AccountPage> createState() => _AccountPageState();
}

class _AccountPageState extends State<AccountPage> {
  final _username = TextEditingController(), _password = TextEditingController();
  final _confirm = TextEditingController(), _email = TextEditingController(), _code = TextEditingController();
  final _form = GlobalKey<FormState>();
  AccountService get service => AccountService.to;
  String _mode = 'login', _message = '';
  String? _verificationId;
  Timer? _resendTimer;
  int _resendSeconds = 0;
  bool _busy = false, _hidden = true, _loaded = false;
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) { if (mounted) _run(_load); });
  }
  Future<void> _load() async {
    await service.initialize();
    if (service.loggedIn) { await service.refresh(); }
    else { await service.loadSettings(); }
    _loaded = true;
  }
  Future<void> _run(Future<void> Function() action) async {
    if (_busy) return;
    setState(() { _busy = true; _message = ''; });
    var failed = false;
    try { await action(); }
    on AccountException catch (e) { failed = true; if (mounted) _message = e.message; }
    catch (_) { failed = true; if (mounted) _message = '操作未完成，请稍后重试'; }
    finally { if (mounted) setState(() => _busy = false); }
    if (mounted && _message.isNotEmpty) {
      final message = _message;
      _message = '';
      await showDialog<void>(context: context, builder: (_) => TraceDialog(
        key: const ValueKey('account-result'), title: failed ? '操作未完成' : '操作完成',
        message: message, color: failed ? TraceColors.amber : TraceColors.cyan,
        icon: failed ? Icons.error_outline : Icons.check_circle_outline,
        actions: [TraceDialogAction(label: '知道了', isPrimary: true,
          onPressed: (context) => Navigator.of(context).pop())]));
    }
  }
  @override
  void dispose() {
    _resendTimer?.cancel();
    for (final controller in [_username, _password, _confirm, _email, _code]) { controller.dispose(); }
    super.dispose();
  }
  bool get _registerEnabled => service.settings['registrationEnabled'] == true && service.settings['passwordRegistrationEnabled'] == true;
  bool get _needsEmail => _mode == 'reset' || (_mode == 'register' && service.settings['emailVerificationEnabled'] == true);
  void _changeMode(String mode) {
    setState(() { _mode = mode; _message = ''; _verificationId = null; _password.clear(); _confirm.clear(); _code.clear(); });
  }
  Future<void> _submit() async {
    if (!_form.currentState!.validate()) return;
    await _run(() async {
      if (_mode == 'login') {
        await service.login(_username.text, _password.text);
        if (!mounted) return;
        _password.clear();
        await service.refresh();
        return;
      }
      if (_needsEmail && _verificationId == null) throw const AccountException('EMAIL_VERIFICATION_REQUIRED', '请先获取邮箱验证码');
      await service.call('/api/auth/${_mode == 'register' ? 'register' : 'reset-password'}', anonymous: true,
        body: {'username': _username.text.trim(), 'password': _password.text,
          if (_email.text.trim().isNotEmpty) 'email': _email.text.trim(), if (_needsEmail) 'code': _code.text.trim(),
          if (_needsEmail) 'verificationId': _verificationId});
      if (!mounted) return;
      final registered = _mode == 'register';
      _changeMode('login');
      _message = registered ? '账号已创建，请登录。' : '密码已重置，请使用新密码登录。';
    });
  }
  Future<void> _sendCode() async {
    final email = _email.text.trim();
    if (!RegExp(r'^[^\s@]+@[^\s@]+\.[^\s@]+$').hasMatch(email)) {
      throw const AccountException('INVALID_PARAMETER', '请输入有效邮箱后再获取验证码');
    }
    final result = await service.call('/api/auth/email-code', anonymous: true,
      body: {'email': email, 'purpose': _mode == 'reset' ? 'reset' : 'register'});
    if (!mounted) return;
    final id = result['verificationId'];
    if (id is! String || id.isEmpty) throw const AccountException('INVALID_RESPONSE', '未收到有效发送确认，请稍后重试');
    _verificationId = id;
    _resendSeconds = 60;
    _resendTimer?.cancel();
    _resendTimer = Timer.periodic(const Duration(seconds: 1), (timer) {
      if (!mounted) { timer.cancel(); return; }
      setState(() { _resendSeconds--; });
      if (_resendSeconds == 0) timer.cancel();
    });
    _message = '如邮箱符合条件，验证码将发送至该邮箱，10 分钟内有效。请检查收件箱和垃圾邮件。';
  }
  Widget _field(String label, TextEditingController controller, {bool secret = false, String? Function(String?)? validate}) =>
    Padding(padding: const EdgeInsets.only(bottom: 16), child: TextFormField(
      controller: controller, obscureText: secret && _hidden, enabled: !_busy,
      onChanged: controller == _email ? (_) { _verificationId = null; _code.clear(); } : null,
      autocorrect: false, enableSuggestions: !secret,
      style: const TextStyle(color: TraceColors.text),
      decoration: InputDecoration(labelText: label, labelStyle: const TextStyle(color: TraceColors.muted),
        filled: true, fillColor: TraceColors.deep,
        enabledBorder: const OutlineInputBorder(borderSide: BorderSide(color: TraceColors.ocean)),
        focusedBorder: const OutlineInputBorder(borderSide: BorderSide(color: TraceColors.cyan)),
        suffixIcon: secret ? IconButton(onPressed: () => setState(() => _hidden = !_hidden),
          color: TraceColors.muted, icon: Icon(_hidden ? Icons.visibility_outlined : Icons.visibility_off_outlined)) : null),
      validator: validate ?? (v) => (v ?? '').isEmpty ? '请填写$label' : null,
    ));

  @override
  Widget build(BuildContext context) => TextButtonTheme(
    data: TextButtonThemeData(style: TextButton.styleFrom(
      foregroundColor: TraceColors.cyanSoft, disabledForegroundColor: TraceColors.muted)),
    child: Scaffold(backgroundColor: TraceColors.ink,
    body: TracePageScaffold(child: SafeArea(child: Column(children: [
      Padding(padding: const EdgeInsets.symmetric(horizontal: 12), child: Row(children: [
        IconButton(onPressed: () => Navigator.of(context).pop(), icon: const Icon(Icons.arrow_back, color: TraceColors.text)),
        const Expanded(child: Text('账号与设备', maxLines: 1, overflow: TextOverflow.ellipsis,
          style: TextStyle(color: TraceColors.text, fontSize: 18, fontWeight: FontWeight.w700))),
        IconButton(onPressed: _busy ? null : () => _run(_load), icon: const Icon(Icons.refresh, color: TraceColors.muted)),
      ])),
      Expanded(child: Center(child: ConstrainedBox(constraints: const BoxConstraints(maxWidth: 520),
        child: SingleChildScrollView(padding: const EdgeInsets.fromLTRB(24, 24, 24, 36), child: Obx(() => Column(
          crossAxisAlignment: CrossAxisAlignment.stretch, children: [
            if (service.account.value == null) ..._authentication() else ..._profile(),
            if (_busy) const Padding(padding: EdgeInsets.symmetric(vertical: 18), child: LinearProgressIndicator(color: TraceColors.cyan)),
          ])),
        )))),
    ])))));

  List<Widget> _authentication() => [
    const Text('E-Track', style: TextStyle(color: TraceColors.cyan, fontSize: 30, fontWeight: FontWeight.w800)),
    const SizedBox(height: 28),
    Text(_mode == 'login' ? '登录账号' : _mode == 'register' ? '创建账号' : '重置密码',
      style: const TextStyle(color: TraceColors.text, fontSize: 24, fontWeight: FontWeight.w700)),
    const SizedBox(height: 8),
    const Text('登录后使用云端服务与固件更新。\n不登录也可以连接蓝牙、查看本地数据。', style: TextStyle(color: TraceColors.muted, height: 1.6)),
    const SizedBox(height: 28),
    Form(key: _form, child: Column(children: [
      if (_mode != 'reset') _field(_mode == 'login' ? '用户名或邮箱' : '用户名', _username,
        validate: (v) => _mode == 'register' && !RegExp(r'^[A-Za-z0-9_]{3,32}$').hasMatch(v ?? '')
          ? '使用 3 至 32 位字母、数字或下划线' : (v ?? '').trim().isEmpty ? '请输入账号' : null),
      if (_mode != 'login') _field(_needsEmail ? '邮箱' : '邮箱（选填，用于找回密码）', _email,
        validate: (v) => !_needsEmail && (v ?? '').trim().isEmpty ? null
          : RegExp(r'^[^\s@]+@[^\s@]+\.[^\s@]+$').hasMatch((v ?? '').trim()) ? null : '请输入有效邮箱'),
      _field(_mode == 'reset' ? '新密码' : '密码', _password, secret: true,
        validate: (v) => (v ?? '').length < 8 || (v ?? '').length > 128 ? '密码长度为 8 至 128 位' : null),
      if (_mode != 'login') _field('确认密码', _confirm, secret: true, validate: (v) => v != _password.text ? '两次密码不一致' : null),
      if (_needsEmail) ...[
        _field('验证码', _code),
        TextButton(onPressed: _busy || _resendSeconds > 0 ? null : () => _run(_sendCode),
          child: Text(_resendSeconds > 0 ? '$_resendSeconds 秒后可重新获取' : '获取邮箱验证码')),
      ],
    ])),
    FilledButton(style: FilledButton.styleFrom(backgroundColor: TraceColors.cyan, foregroundColor: TraceColors.ink,
      minimumSize: const Size.fromHeight(48)), onPressed: _busy || !_loaded ? null : _submit,
      child: Text(_mode == 'login' ? '登录' : _mode == 'register' ? '注册' : '确认重置')),
    const SizedBox(height: 12),
    Wrap(alignment: WrapAlignment.spaceBetween, children: [
      if (_mode != 'login') TextButton(onPressed: _busy ? null : () => _changeMode('login'), child: const Text('返回登录')),
      if (_mode == 'login' && _registerEnabled) TextButton(onPressed: _busy ? null : () => _changeMode('register'), child: const Text('创建账号')),
      if (_mode == 'login' && !_registerEnabled && _loaded) const Text('暂未开放注册', style: TextStyle(color: TraceColors.muted)),
      if (_mode == 'login' && service.settings['passwordResetAvailable'] == true)
        TextButton(onPressed: _busy ? null : () => _changeMode('reset'), child: const Text('忘记密码？')),
    ]),
    TextButton(onPressed: () => Navigator.of(context).pop(), child: const Text('暂不登录，继续使用蓝牙')),
  ];

  List<Widget> _profile() => [
    Text(service.account.value?['displayName']?.toString() ?? '',
      style: const TextStyle(color: TraceColors.text, fontSize: 26, fontWeight: FontWeight.w800)),
    const SizedBox(height: 8),
    const Text('今日检查额度 · 北京时间零点重置', style: TextStyle(color: TraceColors.muted)),
    const SizedBox(height: 16),
    Text('自动剩余 ${service.quota['automatic']?['remaining'] ?? '-'} / ${service.quota['automatic']?['limit'] ?? 5} 次    '
        '手动剩余 ${service.quota['manual']?['remaining'] ?? '-'} / ${service.quota['manual']?['limit'] ?? 5} 次',
        style: const TextStyle(color: TraceColors.cyan, fontSize: 16)),
    const SizedBox(height: 28), const Divider(color: TraceColors.ocean),
    Wrap(alignment: WrapAlignment.spaceBetween, crossAxisAlignment: WrapCrossAlignment.center, children: [
      const Text('绑定的码表', style: TextStyle(color: TraceColors.text, fontSize: 18)),
      TextButton(onPressed: _busy ? null : () => _run(_bind), child: const Text('绑定已连接设备'))]),
    if (service.devices.isEmpty) const Padding(padding: EdgeInsets.symmetric(vertical: 20),
      child: Text('尚未绑定码表。请先连接蓝牙，再选择绑定。', style: TextStyle(color: TraceColors.muted))),
    for (final device in service.devices) Padding(padding: const EdgeInsets.symmetric(vertical: 14), child: Column(
      crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text(device['name'].toString(), style: const TextStyle(color: TraceColors.text, fontWeight: FontWeight.w700)),
        const SizedBox(height: 6), SelectableText('UID ${device['uid']}', style: const TextStyle(color: TraceColors.cyanSoft, fontSize: 13)),
        Text('${device['model']} · 硬件 ${device['hardware_revision']} · 固件 ${device['firmware_version']}',
          style: const TextStyle(color: TraceColors.muted, fontSize: 12)),
        TextButton(onPressed: _busy ? null : () => _run(() => _unbind(device)), child: const Text('解绑')),
      ])),
    const Divider(color: TraceColors.ocean),
    const Text('登录终端', style: TextStyle(color: TraceColors.text, fontSize: 18)),
    const Text('登录有效不代表当前在线；旧版终端信息可能未知。最多显示最近 100 条。',
      style: TextStyle(color: TraceColors.muted, fontSize: 12)),
    if (service.terminalReportProblem.value != null)
      const Text('最近一次码表信息同步未完成，后台信息可能滞后。', style: TextStyle(color: TraceColors.amber)),
    SizedBox(height: service.sessions.isEmpty ? 48 : 240, child: SingleChildScrollView(child: Column(children: [
      for (final session in service.sessions) ListTile(
        title: Text('${session['model'] == null || session['model'] == '' ? '型号未知' : session['model']} · APP ${session['versionName'] ?? '未知'}',
          style: const TextStyle(color: TraceColors.text)),
        subtitle: Text('${session['current'] == 1 || session['current'] == true ? '本机 · ' : ''}'
          '${session['state'] == 'valid' ? '登录有效' : session['state'] == 'revoked' ? '已退出' : '已过期'}\n'
          '最近活动：${session['lastSeenAt'] is num ? DateTime.fromMillisecondsSinceEpoch((session['lastSeenAt'] as num).toInt()).toLocal().toString().split('.').first : '未知'}',
          style: const TextStyle(color: TraceColors.muted, fontSize: 12)),
        trailing: session['state'] == 'valid' ? TextButton(onPressed: _busy ? null : () => _run(() async {
          final confirmed = await showDialog<bool>(context: context, builder: (_) => TraceDialog(title: '退出该终端？',
            message: '该终端将不能继续使用账号云端功能，本地蓝牙不受影响。', actions: [
              TraceDialogAction(label: '取消', onPressed: (context) => Navigator.pop(context, false)),
              TraceDialogAction(label: '退出', isPrimary: true, onPressed: (context) => Navigator.pop(context, true))]));
          if (confirmed != true || !mounted) return;
          await service.revokeSession(session); _message = '该终端登录已撤销。';
        }), child: const Text('退出')) : null),
    ]))),
    const Divider(color: TraceColors.ocean),
    TextButton(onPressed: _busy ? null : () => _run(() async {
      await service.logout(); await service.loadSettings(); _loaded = true;
    }), child: const Text('退出登录')),
  ];

  Future<void> _bind() async {
    final ota = Get.find<OtaService>();
    if (ota.isUpgrading) throw const AccountException('BUSY', '请等待当前升级完成');
    final connected = Get.find<BluetoothService>().connectedDevices.toList();
    if (connected.isEmpty) throw const AccountException('DEVICE_OFFLINE', '请先连接码表蓝牙');
    final selected = await showDialog<String>(context: context, builder: (context) => TraceDialog(
      title: '选择已连接码表', content: Column(mainAxisSize: MainAxisSize.min, children: connected.map((device) => TextButton(
        style: TextButton.styleFrom(foregroundColor: TraceColors.cyanSoft),
        onPressed: () => Navigator.pop(context, device.remoteId.str.toLowerCase()),
        child: Text(device.platformName.isEmpty ? '蓝牙设备' : device.platformName))).toList()),
      actions: [TraceDialogAction(label: '取消', onPressed: (context) => Navigator.pop(context))]));
    if (selected == null || !mounted) return;
    final info = await ota.readDeviceInfo(selected);
    final uid = info == null ? null : await ota.readHardwareUid();
    if (info == null || uid == null) throw const AccountException('DEVICE_UID_UNAVAILABLE', '无法读取码表唯一识别码，请确认已安装支持账号绑定的固件');
    if (!mounted) return;
    final confirm = await showDialog<bool>(context: context, builder: (context) => TraceDialog(title: '确认绑定码表',
      content: SelectableText('设备：${info.deviceModel}\n唯一识别码：$uid\n\n绑定后由本账号使用云端 OTA。'),
      actions: [TraceDialogAction(onPressed: (context) => Navigator.pop(context, false), label: '取消'),
        TraceDialogAction(onPressed: (context) => Navigator.pop(context, true), label: '绑定', isPrimary: true)]));
    if (confirm != true) return;
    if (ota.hardwareUid != uid || !ota.hasCurrentDeviceIdentity(selected)) {
      throw const AccountException('DEVICE_CHANGED', '码表连接已变化，请重新选择设备后绑定');
    }
    final device = connected.firstWhere((d) => d.remoteId.str.toLowerCase() == selected);
    await service.call('/api/account/devices/bind', body: {'uid': uid, 'confirmed': true,
      'name': device.platformName.isEmpty ? 'E-Track' : device.platformName,
      'model': info.deviceModel, 'hardwareRevision': info.hardwareRevision,
      'firmwareVersion': info.currentVersionCode, 'imageSha256': info.currentImageSha256Hex});
    await service.observeDevice(uid, info.currentVersionCode, info.currentImageSha256Hex, force: true);
    await service.refresh();
    _message = '码表已绑定。';
  }
  Future<void> _unbind(Map<String, dynamic> device) async {
    var password = '';
      final confirmed = await showDialog<bool>(context: context, builder: (context) => TraceDialog(
        title: '解绑码表', color: TraceColors.amber, content: TextField(obscureText: true,
          onChanged: (value) => password = value,
          style: const TextStyle(color: TraceColors.text),
          decoration: const InputDecoration(labelText: '请输入账号密码', labelStyle: TextStyle(color: TraceColors.muted))),
        actions: [TraceDialogAction(onPressed: (context) => Navigator.pop(context, false), label: '取消'),
          TraceDialogAction(onPressed: (context) => Navigator.pop(context, true), label: '解绑', isPrimary: true, color: TraceColors.amber)]));
      if (confirmed != true || !mounted) return;
      await service.call('/api/account/devices/unbind', body: {'uid': device['uid'], 'password': password});
      await service.refresh();
      _message = '码表已解绑。';
  }
}
