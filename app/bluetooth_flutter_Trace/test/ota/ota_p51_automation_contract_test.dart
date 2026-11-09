import 'dart:convert';
import 'dart:io';

import 'package:crypto/crypto.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ble_monitor/ota/ota_ble_transport.dart';
import 'package:ble_monitor/ota/ota_link_stats.dart';
import 'package:ble_monitor/ota/ota_p35_recorder.dart';
import 'package:ble_monitor/ota/ota_p35_stream.dart';

import 'ota_pipeline_transport_test.dart' as fixtures;

class _MemoryStream extends OtaP35Stream {
  final bytes = <int>[];
  @override
  Future<void> open() async {}
  @override
  Future<void> send(List<int> value) async { bytes.addAll(value); }
  @override
  Future<void> close() async {}
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  test('real V2 sender and recorder feed the actual P51 automation parser', () async {
    final parent = Directory('${Directory.current.path}/.dart_tool/p51-script-contract');
    await parent.create(recursive: true);
    final root = await parent.createTemp('case-');
    addTearDown(() => root.delete(recursive: true));
    final bytes = fixtures.package(4096);
    const address = 'aa:bb:cc:dd:ee:ff';
    final current = <String, Object?>{
      'phase': 'transferring', 'deviceAddress': address,
      'currentVersionCode': 30321, 'currentImageSha256': 'b' * 64,
      'targetVersionCode': 30322, 'targetImageSha256': 'c' * 64,
      'packageSha256': sha256.convert(bytes).toString(), 'packageBytes': bytes.length,
      'packageVerified': true, 'linkConnected': true, 'freshConnection': true,
      'releaseId': 'host-parser-fixture', 'latestUrl': 'https://fixture.invalid/latest',
      'protocol': null, 'session': 0, 'durable': 0, 'bitmap': null, 'sendOffset': null,
      'runtime': {'backgrounded': false, 'acquired': false, 'reason': null,
        'active': false, 'paused': false, 'ownerEpoch': 7, 'revision': 1, 'task': null},
    };
    final stream = _MemoryStream();
    final recorder = OtaP35Recorder(emit: (_) {}, directoryProvider: () async => root);
    expect(await recorder.start(() => {...current}, reliable: true, stream: stream,
        stateSchema: 2, linkTimings: true), isTrue);
    final stats = OtaLinkStats(label: 'upgrade', device: address,
      onObservation: recorder.bindLinkStats(ownerEpoch: 7, label: 'upgrade'),
      onTransferState: (row) {
        final state = Map<String, Object?>.of(row);
        final event = state.remove('event')! as String;
        current.addAll(state);
        recorder.record(event);
      });
    final peer = fixtures.TestPipelinePeer()..deferReplies = true..writeStats = stats;
    final transport = OtaBleTransport(channel: peer, stats: stats);
    stats.recordMtu(requested: 247, chunkBytes: 244, durationUs: 0, source: 'negotiated');
    stats.recordCharsDiscovery(durationUs: 0, found: true, writeMode: 'writeWithoutResponse');
    try {
      expect((await transport.transfer(package: bytes, packageSha256: sha256.convert(bytes).bytes,
          etuHeader: bytes.sublist(0, 64))).isOk, isTrue);
      expect(peer.received, bytes);
      expect(peer.frames.any((frame) => frame.cmd >= 1 && frame.cmd <= 4), isFalse);
      stats.emitSummary();
    } finally {
      await transport.dispose();
      await peer.events.close();
      await recorder.stop();
    }
    expect(recorder.error, isNull);
    final file = recorder.file!;
    expect(await file.readAsBytes(), stream.bytes);
    final checkout = Directory.current.parent.parent;
    Future<ProcessResult> inspect(File input) => Process.run(
      Platform.isWindows ? 'python' : 'python3', ['-I', '-S', '-B', '-X', 'utf8',
        'Tools/ota/p51-acceptance/v2.py', '--capture', input.path,
        '--capture-id', recorder.captureId!, '--expected-profile'],
      workingDirectory: checkout.path).timeout(const Duration(seconds: 20));
    final result = await inspect(file);
    expect(result.exitCode, 0, reason: '${result.stdout}\n${result.stderr}');
    expect(jsonDecode(result.stdout as String)['upgrades'], 1);

    // Valid seals on deliberately wrong wire/profile inputs must still fail.
    final original = await file.readAsLines();
    for (final fault in ['v1-state', 'v1-summary', 'window32', 'batch3']) {
      final lines = List<String>.of(original);
      for (var index = 1; index < lines.length - 1; index++) {
        final split = lines[index].indexOf(' ');
        final prefix = lines[index].substring(0, split);
        final row = jsonDecode(lines[index].substring(split + 1)) as Map<String, dynamic>;
        if (fault == 'v1-state' && prefix == 'OTA_P35_STATE' && row['protocol'] == 2) {
          row['protocol'] = 1;
          row['bitmap'] = 0;
          lines[index] = '$prefix ${jsonEncode(row)}';
          break;
        }
        if (prefix == 'OTA_P35_DIAGNOSTIC' &&
            (row['line'] as String).startsWith('OTA_LINK_STATS ')) {
          final summary = jsonDecode((row['line'] as String).substring('OTA_LINK_STATS '.length)) as Map;
          final transfer = summary['transfer'] as Map;
          if (fault == 'v1-summary') (transfer['begin']['first'] as Map)['protocol'] = 1;
          if (fault == 'window32') (transfer['begin']['first'] as Map)['windowSegments'] = 32;
          if (fault == 'batch3') (transfer['dataBatch'] as Map)['maxFrames'] = 3;
          row['line'] = 'OTA_LINK_STATS ${jsonEncode(summary)}';
          lines[index] = '$prefix ${jsonEncode(row)}';
        }
      }
      final footer = jsonDecode(lines.last.substring('OTA_P35_CAPTURE '.length)) as Map<String, dynamic>;
      footer['sha256'] = sha256.convert(utf8.encode('${lines.sublist(1, lines.length - 1).join('\n')}\n')).toString();
      lines[lines.length - 1] = 'OTA_P35_CAPTURE ${jsonEncode(footer)}';
      final bad = File('${root.path}/$fault.jsonl');
      await bad.writeAsString('${lines.join('\n')}\n', flush: true);
      expect((await inspect(bad)).exitCode, isNot(0), reason: fault);
    }
  });
}
