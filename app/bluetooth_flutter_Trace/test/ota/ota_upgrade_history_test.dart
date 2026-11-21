import 'dart:io';
import 'package:flutter_test/flutter_test.dart';
import 'package:ble_monitor/ota/ota_upgrade_history.dart';
import 'package:ble_monitor/ota/ota_device_info.dart';

void main() {
  late Directory dir;
  late OtaUpgradeHistory history;
  DeviceOtaInfo info(int version, int digest) => DeviceOtaInfo.fromInfoPayload(buildInfoPayload(
      model: DeviceOtaInfo.wireModelETrack, hardwareRevision: 1, layoutId: 1,
      bootVersion: 1, currentVersionCode: version, imageSha256: List.filled(32, digest)));
  Future<String> begin([String initiator = 'app']) => history.begin(address: 'AA:BB',
      before: info(30341, 1), targetVersion: 30342, targetSha: info(30342, 2).currentImageSha256Hex,
      packageSha: 'a' * 64, kind: 'patch', initiator: initiator);
  setUp(() async {
    final parent = Directory('${Directory.current.path}/.dart_tool/history-tests');
    await parent.create(recursive: true);
    dir = await parent.createTemp('case-');
    history = OtaUpgradeHistory(() async => dir);
  });
  tearDown(() async { await dir.delete(recursive: true); });
  test('no fabricated history; both initiators persist without an address', () async {
    await history.load();
    expect(history.forDevice('AA:BB'), isEmpty);
    await begin(); await begin('mcu');
    final restored = OtaUpgradeHistory(() async => dir);
    await restored.load();
    expect(restored.forDevice('AA:BB').map((r) => r['initiator']), ['mcu', 'app']);
    expect(restored.forDevice('CC:DD'), isEmpty);
    expect(await File('${dir.path}/upgrade-history-v1.jsonl').readAsString(), isNot(contains('AA:BB')));
  });
  test('transfer completion and wrong identity cannot become success', () async {
    final id = await begin();
    await history.update(id, status: 'awaitingVerification', stage: 'waitingReboot');
    await history.reconcile('CC:DD', info(30342, 2));
    await history.reconcile('AA:BB', info(30342, 1));
    await history.reconcile('AA:BB', info(30341, 1));
    expect(history.forDevice('AA:BB').single['status'], 'awaitingVerification');
    await expectLater(history.update(id, status: 'success', stage: 'identityVerified'), throwsStateError);
    await history.reconcile('AA:BB', info(30342, 2));
    expect(history.forDevice('AA:BB').single['status'], 'success');
    expect(history.forDevice('AA:BB').single['afterVersion'], 30342);
  });
  test('restart keeps unknown elapsed time and allows fresh target reconciliation', () async {
    await begin();
    history = OtaUpgradeHistory(() async => dir);
    await history.load();
    expect(history.forDevice('AA:BB').single['status'], 'awaitingVerification');
    await history.reconcile('AA:BB', info(30342, 2));
    expect(history.forDevice('AA:BB').single['durationMs'], isNull);
  });
  test('failed and cancelled attempts never reconcile as success', () async {
    final failed = await begin();
    await history.update(failed, status: 'failed', stage: 'transfer', errorCode: 'TIMEOUT');
    final cancelled = await begin('mcu');
    await history.update(cancelled, status: 'cancelled', stage: 'transfer');
    await history.reconcile('AA:BB', info(30342, 2));
    expect(history.forDevice('AA:BB').map((r) => r['status']), ['cancelled', 'failed']);
  });
  test('torn append preserves prior real record and reports loss', () async {
    await begin();
    await File('${dir.path}/upgrade-history-v1.jsonl').writeAsString('{', mode: FileMode.append);
    history = OtaUpgradeHistory(() async => dir);
    await history.load();
    expect(history.forDevice('AA:BB'), hasLength(1));
    expect(history.problem.value, 'HISTORY_INCOMPLETE');
  });
  test('phase changes share the task and post-END state survives restart', () async {
    final id = await begin('mcu');
    await history.phase(id, 'applying');
    history = OtaUpgradeHistory(() async => dir);
    await history.load();
    expect(history.forDevice('AA:BB').single['taskId'], id);
    expect(history.forDevice('AA:BB').single['status'], 'awaitingVerification');
    await history.reconcile('AA:BB', info(30342, 2));
    expect(history.forDevice('AA:BB').single['status'], 'success');
  });
  test('same-process reconciliation requires a new connection generation', () async {
    final id = await history.begin(address: 'AA:BB', before: info(30341, 1),
      targetVersion: 30342, targetSha: info(30342, 2).currentImageSha256Hex,
      packageSha: 'a' * 64, kind: 'full', initiator: 'app', linkGeneration: 4);
    await history.phase(id, 'waitingReboot');
    await history.reconcile('AA:BB', info(30342, 2), linkGeneration: 4);
    expect(history.forDevice('AA:BB').single['status'], 'awaitingVerification');
    await history.reconcile('AA:BB', info(30342, 2), linkGeneration: 5);
    expect(history.forDevice('AA:BB').single['status'], 'success');
  });
}
