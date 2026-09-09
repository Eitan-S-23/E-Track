import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_blue_plus/flutter_blue_plus.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:get/get.dart';

import 'package:ble_monitor/ota/ota_device_info.dart';
import 'package:ble_monitor/ota/ota_firmware_latest.dart';
import 'package:ble_monitor/pages/ota_upgrade_page.dart';
import 'package:ble_monitor/services/ota_service.dart';

/// OTA 升级页 widget 测试（PR16：UI 由 OtaPhase 驱动）。
///
/// 通过 GetX 容器注入 fake OtaService 子类（页面内 Get.put 幂等返回已
/// 注册实例），手动驱动 Rx 阶段字段验证各状态渲染，不触发真实 BLE/HTTP。
void main() {
  setUp(() {
    Get.testMode = true;
  });

  tearDown(() {
    Get.reset();
  });

  DeviceOtaInfo deviceInfoOf({int vcode = 20801}) {
    return DeviceOtaInfo.fromInfoPayload(buildInfoPayload(
      model: DeviceOtaInfo.wireModelETrack,
      hardwareRevision: 3,
      layoutId: 5,
      bootVersion: 2,
      currentVersionCode: vcode,
      imageSha256: List<int>.generate(32, (i) => i * 3),
    ));
  }

  FirmwareLatestInfo latestOf() {
    return FirmwareLatestInfo.parse({
      'schemaVersion': 2,
      'requestId': 'req-1',
      'updateAvailable': true,
      'appId': 'trace',
      'deviceModel': 'e-track-at32f435',
      'channel': 'stable',
      'releaseId': 'rel-1',
      'versionName': '2.8.1',
      'versionCode': 20900,
      'releaseTag': 'mcu-e-track-at32f435-v2.8.1',
      'releaseNotes': '修复',
      'targetImageSha256': 'b' * 64,
      'targetHardware': 'AT32F435RGT7',
      'transport': 'ble',
      'minAppVersionCode': 0,
      'asset': {
        'assetId': 'asset-1',
        'kind': 'full',
        'fileName': 'e-track-at32f435-v2.8.1-full.etu',
        'sha256': 'c' * 64,
        'sizeBytes': 12345,
        'baseVersionCode': 0,
        'baseImageSha256': null,
        'downloadUrl': 'https://example.com/signed',
        'expiresAt': 1780000000,
      },
    });
  }

  Future<void> pumpPage(
    WidgetTester tester, {
    _FakeOtaService? fake,
    BluetoothDevice? connectedDevice,
  }) async {
    Get.put<OtaService>(fake ?? _FakeOtaService());
    // GetMaterialApp（非 MaterialApp）：Get.dialog 依赖 Get.key 挂载，
    // 取消对话框交互用例（RC3-05①）需要可用的根导航。
    await tester.pumpWidget(GetMaterialApp(
      home: OtaUpgradePage(connectedDevice: connectedDevice),
    ));
    // postFrameCallback（自动解析连接 + 读取身份）与入场动画。
    await tester.pump();
    await tester.pumpAndSettle();
  }

  ElevatedButton findButton(WidgetTester tester, String label) {
    final button = tester.widget<ElevatedButton>(
      find.ancestor(
        of: find.text(label),
        matching: find.byType(ElevatedButton),
      ),
    );
    return button;
  }

  group('连接与身份卡', () {
    testWidgets('未连接设备：显示未连接，检查更新按钮禁用', (tester) async {
      await pumpPage(tester);
      expect(find.text('未连接设备'), findsOneWidget);
      expect(find.text('连接码表后自动读取设备身份'), findsOneWidget);
      // 无设备无身份：按钮禁用。
      expect(findButton(tester, '检查更新').onPressed, isNull);
      // idle 且无固件：不渲染升级卡。
      expect(find.text('下载进度'), findsNothing);
      expect(find.text('固件就绪'), findsNothing);
    });

    testWidgets('传入设备且 GET_INFO 成功：身份确认卡 + 检查按钮可用',
        (tester) async {
      final fake = _FakeOtaService()
        ..readResult = deviceInfoOf(vcode: 20801);
      final device = BluetoothDevice(
        remoteId: const DeviceIdentifier('11:22:33:44:55:66'),
      );
      await pumpPage(tester, fake: fake, connectedDevice: device);
      expect(find.text('设备身份已确认'), findsOneWidget);
      expect(
        find.text('e-track-at32f435 • 固件 vcode 20801'),
        findsOneWidget,
      );
      expect(findButton(tester, '检查更新').onPressed, isNotNull);
    });

    testWidgets('传入设备但身份读取失败：待确认 + 重试读取入口',
        (tester) async {
      final fake = _FakeOtaService()..readResult = null;
      final device = BluetoothDevice(
        remoteId: const DeviceIdentifier('11:22:33:44:55:66'),
      );
      await pumpPage(tester, fake: fake, connectedDevice: device);
      expect(find.text('设备已连接，待确认身份'), findsOneWidget);
      expect(find.text('重试读取'), findsOneWidget);
      // 身份未确认：检查更新仍禁用。
      expect(findButton(tester, '检查更新').onPressed, isNull);
    });
  });

  group('升级进度卡（phase 驱动，PR16）', () {
    testWidgets('downloading：下载进度 + 网络下载行 + 取消下载', (tester) async {
      final fake = _FakeOtaService();
      await pumpPage(tester, fake: fake);
      fake.phase$.value = OtaPhase.downloading;
      fake.isUpgrading$.value = true;
      fake.status$.value = '下载中: 50.0%';
      fake.downloadProgress$.value = 0.5;
      // 忙碌阶段含无限动画（CircularProgressIndicator），
      // pumpAndSettle 永不静止：定量 pump 渲染 Obx 重建即可（RC3-02）。
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));
      expect(find.text('下载进度'), findsOneWidget);
      expect(find.text('网络下载'), findsOneWidget);
      expect(find.text('取消下载'), findsOneWidget);
      expect(find.text('下载中: 50.0%'), findsOneWidget);
      // 下载阶段不显示 durable 行。
      expect(find.text('设备已确认（durable）'), findsNothing);
    });

    testWidgets('transferring：传输卡 + durable/网络双行 + 取消升级',
        (tester) async {
      final fake = _FakeOtaService();
      await pumpPage(tester, fake: fake);
      fake.phase$.value = OtaPhase.transferring;
      fake.isUpgrading$.value = true;
      fake.durableProgress$.value = 0.25;
      fake.downloadProgress$.value = 1.0;
      fake.status$.value = '传输中: 1.0 KB/8.0 KB（MCU 落盘确认）';
      // 忙碌阶段无限动画：定量 pump（RC3-02）。
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));
      expect(find.text('固件传输（设备确认）'), findsOneWidget);
      expect(find.text('设备已确认（durable）'), findsOneWidget);
      expect(find.text('网络下载'), findsOneWidget);
      expect(find.text('取消升级'), findsOneWidget);
    });

    testWidgets('waitingReboot：仍按传输样式渲染等待重启', (tester) async {
      final fake = _FakeOtaService();
      await pumpPage(tester, fake: fake);
      fake.phase$.value = OtaPhase.waitingReboot;
      fake.isUpgrading$.value = true;
      fake.durableProgress$.value = 1.0;
      fake.status$.value = '升级包传输完成，等待设备重启...';
      // 忙碌阶段无限动画：定量 pump（RC3-02）。
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));
      expect(find.text('固件传输（设备确认）'), findsOneWidget);
      expect(find.text('升级包传输完成，等待设备重启...'), findsOneWidget);
    });

    testWidgets('reconnectVerify：复核阶段按传输样式渲染', (tester) async {
      final fake = _FakeOtaService();
      await pumpPage(tester, fake: fake);
      fake.phase$.value = OtaPhase.reconnectVerify;
      fake.isUpgrading$.value = true;
      fake.status$.value = '设备已重连，复核升级结果...';
      // 忙碌阶段无限动画：定量 pump（RC3-02）。
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));
      expect(find.text('固件传输（设备确认）'), findsOneWidget);
      expect(find.text('设备已重连，复核升级结果...'), findsOneWidget);
    });

    testWidgets('readyToInstall：固件就绪 + 开始 BLE 传输入口', (tester) async {
      final fake = _FakeOtaService();
      await pumpPage(tester, fake: fake);
      fake.phase$.value = OtaPhase.readyToInstall;
      fake.hasFile = true;
      fake.status$.value = '固件已下载并校验';
      await tester.pumpAndSettle();
      expect(find.text('固件就绪'), findsOneWidget);
      expect(find.text('开始 BLE 传输'), findsOneWidget);
      // 无连接设备：开始传输禁用（防未连接即传）。
      expect(findButton(tester, '开始 BLE 传输').onPressed, isNull);
    });

    testWidgets('cancelled：显示取消状态卡', (tester) async {
      final fake = _FakeOtaService();
      await pumpPage(tester, fake: fake);
      fake.phase$.value = OtaPhase.cancelled;
      fake.status$.value = '操作已取消';
      await tester.pumpAndSettle();
      expect(find.text('操作已取消'), findsOneWidget);
      // 取消后不提供继续按钮。
      expect(find.text('取消升级'), findsNothing);
      expect(find.text('开始 BLE 传输'), findsNothing);
    });

    testWidgets('completed：完成卡显示目标版本与设备 vcode（PR07）',
        (tester) async {
      final fake = _FakeOtaService();
      await pumpPage(tester, fake: fake);
      fake.latest = latestOf();
      fake.info = deviceInfoOf(vcode: 20900);
      fake.phase$.value = OtaPhase.completed;
      fake.status$.value = '固件升级完成: 设备已运行 2.8.1（vcode 20900）';
      await tester.pumpAndSettle();
      expect(find.text('固件升级完成'), findsOneWidget);
      expect(
        find.text('设备已重启并运行目标固件: 2.8.1（vcode 20900）'),
        findsOneWidget,
      );
    });
  });

  group('终止态卡（PR11）', () {
    testWidgets('CLIENT_TOO_OLD：无法升级 + 门槛文案', (tester) async {
      final fake = _FakeOtaService();
      await pumpPage(tester, fake: fake);
      fake.terminal$.value = OtaTerminalState(
        code: 'CLIENT_TOO_OLD',
        message: 'App 版本过低',
        minAppVersionCode: 60,
      );
      fake.phase$.value = OtaPhase.failed;
      await tester.pumpAndSettle();
      expect(find.text('无法升级'), findsOneWidget);
      expect(
        find.text('当前 App 版本过低（需 ≥ 60），请先升级 App'),
        findsOneWidget,
      );
    });

    testWidgets('retryableLater 终止态：暂不可更新样式', (tester) async {
      final fake = _FakeOtaService();
      await pumpPage(tester, fake: fake);
      fake.terminal$.value = OtaTerminalState(
        code: 'REBOOT_RECONNECT_FAILED',
        message: '设备重启后未能重连（60 秒内未发现 OTA 服务）',
        retryableLater: true,
      );
      fake.phase$.value = OtaPhase.failed;
      await tester.pumpAndSettle();
      expect(find.text('暂不可更新'), findsOneWidget);
      expect(
        find.text('设备重启后未能重连（60 秒内未发现 OTA 服务）'),
        findsOneWidget,
      );
      expect(find.text('无法升级'), findsNothing);
    });

    testWidgets('requestId 透出便于排查', (tester) async {
      final fake = _FakeOtaService();
      await pumpPage(tester, fake: fake);
      fake.terminal$.value = OtaTerminalState(
        code: 'UNKNOWN_DEVICE_MODEL',
        message: '无法识别设备型号',
        requestId: 'req-xyz',
      );
      fake.phase$.value = OtaPhase.failed;
      await tester.pumpAndSettle();
      expect(find.text('requestId: req-xyz'), findsOneWidget);
    });
  });

  group('固件信息卡（发现新版本）', () {
    testWidgets('hasUpdate 时渲染版本/大小/类型/SHA', (tester) async {
      final fake = _FakeOtaService();
      await pumpPage(tester, fake: fake);
      fake.latest = latestOf();
      fake.phase$.value = OtaPhase.idle;
      await tester.pumpAndSettle();
      expect(find.text('发现新版本'), findsOneWidget);
      expect(find.text('2.8.1'), findsOneWidget);
      expect(find.text('完整包'), findsOneWidget);
      expect(find.text('c' * 64), findsOneWidget);
      expect(find.text('下载固件'), findsOneWidget);
    });
  });

  group('取消对话框（RC3-05① 冻结删除策略）', () {
    testWidgets('BLE 阶段取消：保留固件包选项传递 keepPackage=true', (tester) async {
      final fake = _FakeOtaService();
      await pumpPage(tester, fake: fake);
      fake.phase$.value = OtaPhase.transferring;
      fake.isUpgrading$.value = true;
      fake.hasFile = true;
      fake.status$.value = '传输中';
      // 忙碌阶段无限动画：定量 pump（RC3-02）。
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));
      await tester.tap(find.text('取消升级'));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 300));
      expect(find.byType(AlertDialog), findsOneWidget);
      // 已校验完成包可选保留（冻结策略：partial 恒删，不在 UI 放宽）。
      expect(find.text('保留固件包并取消'), findsOneWidget);
      expect(find.text('取消并删除固件包'), findsOneWidget);
      await tester.tap(find.text('保留固件包并取消'));
      // 关闭动画 + cancelled 静止（无 spinner）后可 settle。
      await tester.pumpAndSettle();
      expect(fake.cancelCalls, 1);
      expect(fake.lastKeepPackage, isTrue);
      expect(fake.hasFile, isTrue);
      expect(fake.phase$.value, OtaPhase.cancelled);
    });

    testWidgets('BLE 阶段取消：删除固件包选项传递 keepPackage=false',
        (tester) async {
      final fake = _FakeOtaService();
      await pumpPage(tester, fake: fake);
      fake.phase$.value = OtaPhase.transferring;
      fake.isUpgrading$.value = true;
      fake.hasFile = true;
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));
      await tester.tap(find.text('取消升级'));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 300));
      await tester.tap(find.text('取消并删除固件包'));
      await tester.pumpAndSettle();
      expect(fake.cancelCalls, 1);
      expect(fake.lastKeepPackage, isFalse);
      expect(fake.hasFile, isFalse);
    });

    testWidgets('下载阶段取消：无保留 partial 选项，确认取消保留已校验包',
        (tester) async {
      final fake = _FakeOtaService();
      await pumpPage(tester, fake: fake);
      fake.phase$.value = OtaPhase.downloading;
      fake.isUpgrading$.value = true;
      fake.status$.value = '下载中: 30.0%';
      fake.downloadProgress$.value = 0.3;
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));
      await tester.tap(find.text('取消下载'));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 300));
      expect(find.byType(AlertDialog), findsOneWidget);
      // 未完成分片不支持保留续传：不出现保留按钮。
      expect(find.text('保留固件包并取消'), findsNothing);
      await tester.tap(find.text('确认取消'));
      await tester.pumpAndSettle();
      expect(fake.cancelCalls, 1);
      // 取消的是下载：已校验包（若有）不动。
      expect(fake.lastKeepPackage, isTrue);
    });

    testWidgets('cancelled 保留验证包：仍提供开始传输入口', (tester) async {
      final fake = _FakeOtaService();
      await pumpPage(tester, fake: fake);
      fake.hasFile = true;
      fake.phase$.value = OtaPhase.cancelled;
      fake.status$.value = '操作已取消';
      await tester.pumpAndSettle();
      expect(find.text('操作已取消'), findsOneWidget);
      // 保留的已校验包可直接重新发起传输（无连接设备时禁用但展示）。
      expect(find.text('开始 BLE 传输'), findsOneWidget);
      expect(findButton(tester, '开始 BLE 传输').onPressed, isNull);
      // 取消后不显示误导性进度快照（partial 已删）。
      expect(find.text('网络下载'), findsNothing);
    });
  });

  group('忽略与清理（RC3-12②）', () {
    testWidgets('readyToInstall 点忽略：清包后传输入口消失、下载入口恢复',
        (tester) async {
      final fake = _FakeOtaService();
      final device = BluetoothDevice(
        remoteId: const DeviceIdentifier('11:22:33:44:55:66'),
      );
      await pumpPage(tester, fake: fake, connectedDevice: device);
      fake.latest = latestOf();
      fake.info = deviceInfoOf(vcode: 20801);
      fake.hasFile = true;
      fake.phase$.value = OtaPhase.readyToInstall;
      fake.status$.value = '固件已下载并校验';
      await tester.pumpAndSettle();
      // 忽略前：就绪卡 + 传输入口；下载按钮因 phase 禁用。
      expect(find.text('开始 BLE 传输'), findsOneWidget);
      expect(findButton(tester, '下载固件').onPressed, isNull);
      await tester.tap(find.text('忽略'));
      await tester.pump();
      await tester.pumpAndSettle();
      // await 生效：cleanup 被调用且完成状态转换（readyToInstall→idle）。
      expect(fake.cleanupCalls, 1);
      expect(find.text('开始 BLE 传输'), findsNothing);
      expect(findButton(tester, '下载固件').onPressed, isNotNull);
    });

    testWidgets('忙碌时点忽略：清理被拒绝，不崩溃不转换', (tester) async {
      final fake = _FakeOtaService();
      await pumpPage(tester, fake: fake);
      fake.latest = latestOf();
      fake.hasFile = true;
      fake.phase$.value = OtaPhase.readyToInstall;
      fake.isUpgrading$.value = true;
      fake.cleanupResult = false; // 模拟 service 忙碌拒绝。
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));
      await tester.tap(find.text('忽略'));
      await tester.pump();
      expect(fake.cleanupCalls, 1);
      // 拒绝后不误报清理成功（状态未转换）。
      expect(fake.hasFile, isTrue);
      expect(fake.phase$.value, OtaPhase.readyToInstall);
    });
  });

  group('终止态入口闭锁（RC3-12③）', () {
    testWidgets('非 retryableLater 终止态：检查按钮禁用 + 解锁提示', (tester) async {
      final fake = _FakeOtaService()..readResult = deviceInfoOf();
      final device = BluetoothDevice(
        remoteId: const DeviceIdentifier('11:22:33:44:55:66'),
      );
      await pumpPage(tester, fake: fake, connectedDevice: device);
      fake.terminal$.value = OtaTerminalState(
        code: 'CLIENT_TOO_OLD',
        message: 'App 版本过低',
        minAppVersionCode: 60,
      );
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));
      expect(findButton(tester, '检查更新').onPressed, isNull);
      expect(
        find.text('已进入终止状态（CLIENT_TOO_OLD），重新读取设备身份后可解锁检查'),
        findsOneWidget,
      );
    });

    testWidgets('retryableLater 终止态：检查按钮仍可用', (tester) async {
      final fake = _FakeOtaService()..readResult = deviceInfoOf();
      final device = BluetoothDevice(
        remoteId: const DeviceIdentifier('11:22:33:44:55:66'),
      );
      await pumpPage(tester, fake: fake, connectedDevice: device);
      fake.terminal$.value = OtaTerminalState(
        code: 'REBOOT_RECONNECT_FAILED',
        message: '设备重启后未能重连',
        retryableLater: true,
      );
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));
      expect(findButton(tester, '检查更新').onPressed, isNotNull);
    });

    testWidgets('终止闭锁但身份快照仍在：提供可执行的重新读取身份解锁入口（RC3-12③）',
        (tester) async {
      final fake = _FakeOtaService()..readResult = deviceInfoOf();
      final device = BluetoothDevice(
        remoteId: const DeviceIdentifier('11:22:33:44:55:66'),
      );
      await pumpPage(tester, fake: fake, connectedDevice: device);
      fake.terminal$.value = OtaTerminalState(
        code: 'CLIENT_TOO_OLD',
        message: 'App 版本过低',
        minAppVersionCode: 60,
      );
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));
      // 恢复入口必须是实际可执行按钮，不只是文字提示。
      final unlock = find.widgetWithText(OutlinedButton, '重新读取身份解锁');
      expect(unlock, findsOneWidget);
      expect(tester.widget<OutlinedButton>(unlock).onPressed, isNotNull);

      await tester.tap(unlock);
      await tester.pump();
      await tester.pumpAndSettle();
      // 解锁入口真的重新读取设备身份（readDeviceInfo 再次调用）。
      expect(fake.readCalls, 2);
      // 读取成功清除终止态（与真实 service PR11 解锁对齐）：检查入口恢复。
      expect(findButton(tester, '检查更新').onPressed, isNotNull);
      expect(find.text('基于设备身份查询可用固件'), findsOneWidget);
    });
  });

  group('连接与生命周期（RC3-08④）', () {
    testWidgets('显式设备参数变化：重新解析并读取新地址身份', (tester) async {
      final fake = _FakeOtaService()..readResult = deviceInfoOf();
      final deviceA = BluetoothDevice(
        remoteId: const DeviceIdentifier('11:22:33:44:55:66'),
      );
      await pumpPage(tester, fake: fake, connectedDevice: deviceA);
      expect(fake.readCalls, 1);
      expect(fake.lastReadAddress, '11:22:33:44:55:66');
      // didUpdateWidget：同一 State 复用，目标设备变化触发重读。
      final deviceB = BluetoothDevice(
        remoteId: const DeviceIdentifier('AA:BB:CC:DD:EE:FF'),
      );
      await tester.pumpWidget(GetMaterialApp(
        home: OtaUpgradePage(connectedDevice: deviceB),
      ));
      await tester.pumpAndSettle();
      expect(fake.readCalls, 2);
      // DTO 地址绑定：读取请求携带新地址（小写化）。
      expect(fake.lastReadAddress, 'aa:bb:cc:dd:ee:ff');
    });

    testWidgets('后台暂停恢复：回前台重新读取设备身份', (tester) async {
      final fake = _FakeOtaService()..readResult = deviceInfoOf();
      final device = BluetoothDevice(
        remoteId: const DeviceIdentifier('11:22:33:44:55:66'),
      );
      await pumpPage(tester, fake: fake, connectedDevice: device);
      expect(fake.readCalls, 1);
      // 后台：页面停写（不主动发起 GET_INFO）。
      tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.paused);
      await tester.pump();
      expect(fake.readCalls, 1);
      // 回前台：重新解析连接并读取身份。
      tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
      await tester.pump();
      await tester.pumpAndSettle();
      expect(fake.readCalls, 2);
    });
  });
}

/// OtaService 测试替身：覆写 UI 读取的全部状态 getter，
/// Rx 字段可由测试直接驱动（Obx 订阅生效）。
class _FakeOtaService extends OtaService {
  _FakeOtaService() : super();

  final phase$ = Rx<OtaPhase>(OtaPhase.idle);
  final isUpgrading$ = false.obs;
  final status$ = ''.obs;
  final downloadProgress$ = 0.0.obs;
  final durableProgress$ = 0.0.obs;
  final terminal$ = Rxn<OtaTerminalState>();

  /// 手动设置的清单与设备快照（getter 返回）。
  FirmwareLatestInfo? latest;
  DeviceOtaInfo? info;
  bool hasFile = false;
  /// readDeviceInfo 的返回值（页面进入时自动调用）。
  DeviceOtaInfo? readResult;
  /// 交互记录：readDeviceInfo/cancelUpgrade/cleanupFirmware 调用参数。
  int readCalls = 0;
  String? lastReadAddress;
  int cancelCalls = 0;
  bool? lastKeepPackage;
  int cleanupCalls = 0;
  /// cleanupFirmware 结果（false 模拟忙碌拒绝或删除失败）。
  bool cleanupResult = true;

  @override
  Rx<OtaPhase> get phaseRx => phase$;
  @override
  OtaPhase get phase => phase$.value;
  @override
  bool get isUpgrading => isUpgrading$.value;
  @override
  String get upgradeStatus => status$.value;
  @override
  double get downloadProgress => downloadProgress$.value;
  @override
  double get durableProgress => durableProgress$.value;
  @override
  OtaTerminalState? get terminalState => terminal$.value;
  @override
  FirmwareLatestInfo? get latestInfo => latest;
  @override
  DeviceOtaInfo? get deviceInfo => info;
  @override
  File? get downloadedFirmwareFile => hasFile ? File('pkg.etu') : null;
  @override
  bool get isFirmwareServiceConfigured => true;
  @override
  List<Map<String, dynamic>> getUpgradeHistory() => const [];

  @override
  Future<DeviceOtaInfo?> readDeviceInfo(String deviceAddress) async {
    readCalls++;
    lastReadAddress = deviceAddress;
    // 页面自动读取：返回值同时驱动连接卡状态。
    final result = readResult;
    if (result != null) {
      info = result;
      // 与真实 service 对齐（PR11 解锁）：读取成功清除终止态。
      terminal$.value = null;
    }
    return result;
  }

  @override
  Future<void> cancelUpgrade({bool keepPackage = false}) async {
    cancelCalls++;
    lastKeepPackage = keepPackage;
    // 模拟真实取消发布（partial 恒删由 service 承担，此处只驱动 UI 状态）。
    isUpgrading$.value = false;
    phase$.value = OtaPhase.cancelled;
    status$.value = '操作已取消';
    if (!keepPackage) hasFile = false;
  }

  @override
  Future<bool> cleanupFirmware() async {
    cleanupCalls++;
    if (!cleanupResult) return false;
    // 模拟真实状态转换（RC3-12①：readyToInstall→idle + 复位文件）。
    hasFile = false;
    if (phase$.value == OtaPhase.readyToInstall) {
      phase$.value = OtaPhase.idle;
      status$.value = '固件包已清理';
    }
    return true;
  }
}
