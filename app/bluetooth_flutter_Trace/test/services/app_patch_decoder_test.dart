import 'dart:async';

import 'package:ble_monitor/services/app_patch_decoder.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  const channel = MethodChannel('trace/app_patch');
  const codec = StandardMethodCodec();
  final messenger = TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger;
  final oldSha = 'a' * 64, patchSha = 'b' * 64, newSha = 'c' * 64;

  Future<void> progress(String id, int completed, int total) async {
    final finished = Completer<void>();
    messenger.handlePlatformMessage(channel.name, codec.encodeMethodCall(MethodCall('progress',
        {'id': id, 'completed': completed, 'total': total})), (ByteData? _) => finished.complete());
    await finished.future;
  }

  Future<void> apply(AppPatchDecoder decoder, void Function(double) onProgress) => decoder.apply(
        oldApkPath: 'base.apk', patchPath: 'delta.patch', outputApkPath: 'new.apk',
        expectedOldSha256: oldSha, expectedPatchSha256: patchSha,
        expectedNewSha256: newSha, expectedNewSize: 100, onProgress: onProgress);

  tearDown(() => messenger.setMockMethodCallHandler(channel, null));

  test('format negotiation retains old clients and rejects unknown formats', () {
    expect(supportsAppPatch('vcdiff', 40), isFalse);
    expect(supportsAppPatch('vcdiff', 41), isTrue);
    expect(supportsAppPatch(appBsdiffLzmaFormat, 106), isFalse);
    expect(supportsAppPatch(appBsdiffLzmaFormat, 107), isTrue);
    expect(supportsAppPatch('future-codec', 107), isFalse);
    expect(supportsAppPatch('tracepatch', 40), isTrue);
  });

  test('production bridge binds identities and ignores stale or regressing progress', () async {
    final values = <double>[];
    messenger.setMockMethodCallHandler(channel, (call) async {
      expect(call.method, 'apply');
      final args = call.arguments as Map;
      expect(args['algorithm'], appBsdiffLzmaFormat);
      expect(args['oldSha256'], oldSha);
      expect(args['patchSha256'], patchSha);
      expect(args['newSha256'], newSha);
      final id = args['id'] as String;
      await progress('stale', 80, 100);
      await progress(id, 25, 100);
      await progress(id, 24, 100);
      await progress(id, 200, 100);
      await progress(id, 90, 99);
      return {'id': id, 'bytes': 100, 'sha256': newSha};
    });
    await apply(AppPatchDecoder(), values.add);
    expect(values, [0.25, 1.0]);
  });

  test('wrong completion identity and platform failures cannot signal success', () async {
    final decoder = AppPatchDecoder();
    messenger.setMockMethodCallHandler(channel, (call) async =>
        {'id': 'other', 'bytes': 100, 'sha256': newSha});
    await expectLater(apply(decoder, (_) => fail('Unexpected success')), throwsFormatException);
    messenger.setMockMethodCallHandler(channel, (_) async => throw PlatformException(code: 'PATCH_FAILED'));
    await expectLater(apply(decoder, (_) {}), throwsA(isA<PlatformException>()));
  });

  test('single owner cancellation is bound and a late native success is rejected', () async {
    final entered = Completer<Map>();
    final completed = Completer<void>();
    messenger.setMockMethodCallHandler(channel, (call) async {
      final args = call.arguments as Map;
      if (call.method == 'cancel') {
        expect(args['id'], (await entered.future)['id']);
        return true;
      }
      entered.complete(args);
      await completed.future;
      return {'id': args['id'], 'bytes': 100, 'sha256': newSha};
    });
    final decoder = AppPatchDecoder();
    final future = apply(decoder, (_) => fail('Cancelled progress'));
    final expectation = expectLater(future, throwsA(isA<PlatformException>().having((e) => e.code, 'code', 'PATCH_CANCELLED')));
    await entered.future;
    await expectLater(apply(decoder, (_) {}), throwsStateError);
    await decoder.cancel();
    await progress((await entered.future)['id'] as String, 50, 100);
    completed.complete();
    await expectation;
  });
}
